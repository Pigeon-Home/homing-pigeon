#!/usr/bin/env python3
"""The work in front of the MAC, measured on the gate itself.

docs/infrastructure-documents/proofs/v4-before-the-mac.md states a
candidate constraint, C32: for a message whose signature does not
verify, the runner runs nothing, sends nothing, keeps nothing but
the seen mark and 1 refusal record of a fixed size, and does work
bounded by a count of the message's length. The page wrote 8
suppositions before anything was measured. This module is the
measure for S1 to S7, at handle_mail, on the fuzz corpus's own
messages and on their hostile growths.

Every message here fails at the signature: a corpus job signed by a
key the runner does not hold, the same job with 1 digit of its
signature turned, and those 2 grown in the subject and in the body.
"""
import base64
import contextlib
import copy
import email.header
import hmac
import io
import json
import os
import sys
import tempfile
import time
import unittest
from argparse import Namespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.guard import panic as PANIC  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SUBJECT_SIZES = (1000, 10000, 100000)
BODY_SIZES = (10000, 100000)
EVENTS = "security-events.jsonl"
# Finding F12, closed: what 1 refused message may add to the log,
# in bytes, whatever is grown; the sizes each text is grown to; and
# the texts a stranger chooses that the gate's lines name.
LOG_BOUND = 4096
GROWN = (1000, 100000, 1000000)
FIELDS = ("the subject", "the id", "the sender", "the key id",
          "a key id that is not a string", "the body, elsewhere")


def _mail(subject, body, sender="si@example.com"):
    """1 mail as octets, under a subject and a sender given whole."""
    return (("Subject: %s\r\nFrom: %s\r\n"
             "MIME-Version: 1.0\r\n"
             "Content-Type: text/plain; charset=utf-8\r\n"
             "Content-Transfer-Encoding: 8bit\r\n\r\n" % (subject, sender)
             ).encode("ascii")
            + body.encode("utf-8", "surrogatepass"))


def _subject(job_id, size=None):
    """A job's subject. With a size, a word between the marker
    and the job brings it to that many bytes: a word there is
    allowed."""
    plain = "[HOMING-PIGEON] job %s" % job_id
    if size is None:
        return plain
    return "[HOMING-PIGEON] %s job %s" % (
        "x" * (size - len(plain) - 1), job_id)


def _turned(text):
    mark = text.rindex('"sig"')
    digit = text.index('"', text.index(":", mark) + 1) + 1
    return text[:digit] + ("0" if text[digit] != "0" else "1") \
        + text[digit + 1:]


class _Count:
    """What the gate asked of the parser and of the MAC."""

    def __init__(self):
        self.parsed = 0
        self.macs = 0
        self.hashed = 0
        self.opened = 0


def arrive(raw, folder, log_file=None, cfg_extra=None, seen=None):
    """1 arrival at handle_mail with cleartext allowed: what ran,
    what was sent, the seen set, the mailbox marks, the log's
    lines, and the counts of work. With a log file the runner's
    own log writes to it. `cfg_extra` adds to the configuration,
    and `seen` is the seen set the arrival meets."""
    count = _Count()
    executed, sent, notes = [], [], []
    parse, mac, opener = json.loads, hmac.new, jobcrypto.decrypt_body

    def loads(text, *args, **kwargs):
        count.parsed += len(text)
        return parse(text, *args, **kwargs)

    def new(key, msg=None, digestmod=""):
        count.macs += 1
        count.hashed += len(msg or b"")
        return mac(key, msg, digestmod)

    def decrypt(*args, **kwargs):
        count.opened += 1
        return opener(*args, **kwargs)

    def execute(_cfg, job, _base):
        executed.append(job)
        return dict(DOOR._OK_RESULT)

    def send(_smtp, _cfg, subject, body, to=None):
        sent.append(subject)

    cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
           "oracle_opinion_mode": "off"}
    cfg.update(BIND.KEYS)
    cfg.update(cfg_extra or {})
    imap, seen = DOOR._IMAP2(), ({} if seen is None else seen)
    patches = [mock.patch.object(RUNNER, "execute_job", execute),
               mock.patch.object(RUNNER, "send_mail", send),
               mock.patch.object(json, "loads", loads),
               mock.patch.object(hmac, "new", new),
               mock.patch.object(jobcrypto, "decrypt_body", decrypt)]
    if log_file is None:
        patches.append(mock.patch.object(
            RUNNER, "log", lambda msg, level="INFO": notes.append(msg)))
    else:
        patches.append(mock.patch.object(RUNNER, "_LOG_FILE", log_file))
    RUNNER._set_allow_cleartext_jobs(True)
    try:
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            console = stack.enter_context(
                contextlib.redirect_stdout(io.StringIO()))
            secrets = RUNNER.build_secrets(cfg)
            count.parsed = count.macs = count.hashed = 0
            RUNNER.handle_mail(
                cfg, imap, DOOR._SMTP2(), 3, raw, folder, seen, secrets,
                Namespace(dry_run=False, no_send=False), None)
            printed = len(console.getvalue())
    finally:
        RUNNER._set_allow_cleartext_jobs(False)
    return Namespace(executed=executed, sent=sent, seen=seen,
                     marks=imap.store_calls, notes=notes, count=count,
                     printed=printed, keys=len(secrets))


def kept(folder):
    """{file under the runner's folder: its bytes}."""
    out = {}
    for base, _dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(base, name)
            out[os.path.relpath(path, folder)] = os.path.getsize(path)
    return out


class InFrontOfTheMac(unittest.TestCase):
    """S1 to S7, on messages that fail at the signature."""

    @classmethod
    def setUpClass(cls):
        # The corpus's fresh jobs that run when they are signed by
        # a key the runner holds, each made to fail 2 ways.
        cls.strangers = []
        for entry_id, payload, subject in BIND.fresh_jobs():
            text = BIND._signed(payload)
            if text is None:
                continue
            with tempfile.TemporaryDirectory() as folder:
                if not arrive(_mail(_subject(subject), text),
                              folder).executed:
                    continue
            cls.strangers.append((entry_id, subject, "a strange key",
                                  RUNNER.sign_payload(payload,
                                                      BIND.STRANGER)))
            cls.strangers.append((entry_id, subject, "1 digit turned",
                                  _turned(text)))

    def grown(self):
        """(name, subject, body, raw) for every failing message as
        it is, and grown in the subject and in the body."""
        for entry_id, job_id, how, text in self.strangers:
            yield (entry_id, how, "as it is"), _mail(_subject(job_id), text)
            for size in SUBJECT_SIZES:
                yield ((entry_id, how, "subject %d" % size),
                       _mail(_subject(job_id, size), text))
            for size in BODY_SIZES:
                yield ((entry_id, how, "body %d" % size),
                       BIND._octets(job_id, text, size))

    def test_the_corpus_gives_messages_that_fail_at_the_signature(self):
        self.assertGreaterEqual(len(self.strangers), 40)
        for entry_id, job_id, how, text in self.strangers:
            with tempfile.TemporaryDirectory() as folder:
                out = arrive(_mail(_subject(job_id), text), folder)
            refusals = [note for note in out.notes if "rejecting" in note]
            self.assertEqual(1, len(refusals), (entry_id, how))
            self.assertIn("bad signature", refusals[0], (entry_id, how))

    def test_s1_nothing_runs_and_nothing_is_sent(self):
        for name, raw in self.grown():
            with tempfile.TemporaryDirectory() as folder:
                out = arrive(raw, folder)
            self.assertEqual([], out.executed, name)
            self.assertEqual([], out.sent, name)

    def test_s2_and_s3_what_is_kept_is_1_record_of_a_fixed_size(self):
        sizes = set()
        for name, raw in self.grown():
            with tempfile.TemporaryDirectory() as folder:
                out = arrive(raw, folder)
                left = kept(folder)
                with open(os.path.join(folder, EVENTS),
                          encoding="utf-8") as fh:
                    record = fh.read()
            self.assertEqual({}, out.seen, name)
            self.assertEqual([EVENTS], sorted(left), name)
            self.assertEqual(1, record.count("\n"), name)
            self.assertEqual({"type": "auth_rejection",
                              "reason": "bad_signature"},
                             {key: value
                              for key, value in json.loads(record).items()
                              if key != "at"}, name)
            sizes.add(left[EVENTS])
        # The record is the same size whatever the message's size.
        self.assertEqual(1, len(sizes), sizes)

    def test_s5_the_work_is_bounded_by_a_count_of_the_length(self):
        worst = {"parsed": 0.0, "hashed": 0.0, "macs": 0}
        for name, raw in self.grown():
            with tempfile.TemporaryDirectory() as folder:
                out = arrive(raw, folder)
            count = out.count
            # The parser is given at most 16 times the message, and
            # the MAC is computed at most twice for each key held.
            self.assertLessEqual(count.parsed, 16 * len(raw), name)
            self.assertLessEqual(count.macs, 2 * out.keys, name)
            self.assertLessEqual(count.hashed, count.macs * len(raw), name)
            worst["parsed"] = max(worst["parsed"], count.parsed / len(raw))
            worst["hashed"] = max(worst["hashed"], count.hashed / len(raw))
            worst["macs"] = max(worst["macs"], count.macs)
        self.assertGreater(worst["macs"], 0)

    def test_s6_a_sealed_body_is_not_opened_before_its_signature(self):
        seen = 0
        for entry_id, job_id, how, text in self.strangers:
            if how != "a strange key":
                continue
            sealed = jobcrypto.encrypt_body(
                text, BIND.STRANGER, job_id=job_id, key_id="",
                sign=RUNNER.sign_payload)
            for body in (sealed, _turned(sealed)):
                with tempfile.TemporaryDirectory() as folder:
                    out = arrive(_mail(_subject(job_id), body), folder)
                self.assertEqual([], out.executed, entry_id)
                self.assertEqual(0, out.count.opened, entry_id)
                seen += 1
        self.assertGreaterEqual(seen, 40)

    def test_s7_a_refused_message_is_marked_seen_once(self):
        for name, raw in self.grown():
            with tempfile.TemporaryDirectory() as folder:
                out = arrive(raw, folder)
            self.assertEqual(1, out.marks, name)


class TheLogInFrontOfTheMac(unittest.TestCase):
    """S4 and finding F12, closed: what 1 refused message adds to
    the runner's own log is a fixed amount, whatever is grown."""

    @classmethod
    def setUpClass(cls):
        # The corpus's first fresh job that runs when it is signed
        # by the key it names.
        for entry_id, payload, job_id in BIND.fresh_jobs():
            text = BIND._signed(payload)
            if text is None:
                continue
            with tempfile.TemporaryDirectory() as folder:
                if arrive(_mail(_subject(job_id), text), folder).executed:
                    break
        cls.entry_id, cls.payload, cls.job_id = entry_id, payload, job_id

    def stranger(self, field=None, size=0, subject=None,
                 sender="si@example.com"):
        """A job signed by a key the runner does not hold, with 1
        of the texts a stranger chooses grown to `size`."""
        payload = copy.deepcopy(self.payload)
        if subject is None:
            subject = _subject(self.job_id)
        if field == "the subject":
            subject = _subject(self.job_id, size)
        elif field == "the id":
            subject = "[HOMING-PIGEON] job %s" % ("A" * size)
        elif field == "the sender":
            sender = "%s@example.com" % ("s" * (size - 12))
        elif field == "the key id":
            payload["key_id"] = "K" * size
        elif field == "a key id that is not a string":
            payload["key_id"] = ["K" * 10] * (size // 14)
        elif field == "the body, elsewhere":
            payload["pad"] = "P" * size
        return _mail(subject,
                     RUNNER.sign_payload(payload, BIND.STRANGER), sender)

    def logged(self, raw):
        """(the log file's bytes, the arrival) for 1 arrival, at
        the start of a minute of the log's budget."""
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(RUNNER, "_LOG_MINUTE", time.time()), \
                mock.patch.object(RUNNER, "_LOG_COUNT", 0), \
                mock.patch.object(RUNNER, "_LOG_DROPPED", 0):
            log_file = os.path.join(folder, "runner.log")
            base = os.path.join(folder, "base")
            os.mkdir(base)
            out = arrive(raw, base, log_file)
            with open(log_file, "rb") as handle:
                data = handle.read()
        return data, out

    def lines(self, raw):
        """The log's lines for 1 arrival, without their dates."""
        data, _out = self.logged(raw)
        return [line[20:] for line in data.decode("utf-8").split("\n")
                if line]

    def test_f12_a_refused_message_adds_a_fixed_amount(self):
        plain, _ = self.logged(self.stranger())
        for field in FIELDS:
            at = {}
            for size in GROWN:
                data, out = self.logged(self.stranger(field, size))
                self.assertEqual([], out.executed, (field, size))
                self.assertLessEqual(len(data), LOG_BOUND, (field, size))
                self.assertLessEqual(out.printed, LOG_BOUND, (field, size))
                self.assertEqual(plain.count(b"\n"), data.count(b"\n"),
                                 (field, size))
                at[size] = len(data)
            # Past the limit the line holds the cut text and the
            # length as a number: 10 times the text adds 1 digit to
            # each place the length is written, and nothing else.
            self.assertLessEqual(at[GROWN[-1]] - at[GROWN[0]], 8, field)

    def test_f12_the_most_it_adds_with_every_text_grown_at_once(self):
        # Every text grown in 1 message, in the characters the
        # quoting writes longest: an escape in the 2 headers, and a
        # 4 byte letter in the key id, which the refusal repeats.
        escape, wide = "\x1b", "\U0001d538"
        most = 0
        for size in (1000, 100000):
            payload = copy.deepcopy(self.payload)
            payload["key_id"] = wide * size
            raw = _mail("[HOMING-PIGEON] %s job %s"
                        % (escape * size, escape * size),
                        RUNNER.sign_payload(payload, BIND.STRANGER),
                        "%s@example.com" % (escape * size))
            data, out = self.logged(raw)
            self.assertEqual([], out.executed, size)
            self.assertNotIn(b"\x1b", data, size)
            self.assertEqual(2, data.count(b"\n"), size)
            self.assertLessEqual(len(data), LOG_BOUND, size)
            most = max(most, len(data))
        # The bound is not slack by much: this message comes
        # within half of it.
        self.assertGreater(most, LOG_BOUND // 2)

    def test_f12_the_cut_says_the_full_length(self):
        for field, where in (("the subject", "subject="),
                             ("the id", "job "),
                             ("the sender", "submitted by "),
                             ("the key id", "unknown key_id ")):
            lines = self.lines(self.stranger(field, 1000))
            named = [line for line in lines if where in line]
            self.assertEqual(1, len(named), field)
            self.assertIn("characters)", named[0], field)
            said = [int(part.split(" ")[0])
                    for part in named[0].split("... (")[1:]]
            self.assertTrue(said and min(said) >= 1000, (field, said))

    def test_f12_an_honest_job_s_lines_are_as_they_were(self):
        # The 2 lines of a job as it is sent, byte for byte the
        # lines the gate wrote before the bound.
        self.assertEqual(
            ["[INFO] seq 3: job %s submitted by si@example.com "
             "subject=%r" % (self.job_id, _subject(self.job_id)),
             "[WARN] rejecting seq 3: bad signature: bad signature"],
            self.lines(self.stranger()))
        # At each limit the text is still written whole.
        longest = "a" * RUNNER.LOG_ID_MAX
        subject = "[HOMING-PIGEON] job %s" % longest
        self.assertIn("job %s submitted by" % longest,
                      self.lines(self.stranger(subject=subject))[0])
        sender = "%s@example.com" % ("s" * (RUNNER.LOG_SENDER_MAX - 12))
        self.assertEqual(RUNNER.LOG_SENDER_MAX, len(sender))
        self.assertIn("submitted by %s subject=" % sender,
                      self.lines(self.stranger(sender=sender))[0])
        subject = _subject(self.job_id, RUNNER.LOG_SUBJECT_MAX)
        self.assertEqual(RUNNER.LOG_SUBJECT_MAX, len(subject))
        self.assertTrue(self.lines(self.stranger(subject=subject))[0]
                        .endswith("subject=%r" % subject))
        # 1 character past a limit, the cut begins.
        for field, limit in (("the subject", RUNNER.LOG_SUBJECT_MAX),
                             ("the id", RUNNER.LOG_ID_MAX),
                             ("the sender", RUNNER.LOG_SENDER_MAX)):
            line = self.lines(self.stranger(field, limit + 1))[0]
            self.assertIn("... (%d characters)" % (limit + 1), line, field)

    def test_f12_no_control_character_of_a_stranger_s_reaches_the_log(self):
        escape = "\x1b[2J"
        for name, raw in (
                ("the id", self.stranger(
                    subject="[HOMING-PIGEON] job ab%scd" % escape)),
                ("the subject", self.stranger(
                    subject="[HOMING-PIGEON] %s job %s"
                    % (escape, self.job_id))),
                ("the sender", self.stranger(
                    sender="x%sy@example.com" % escape)),
                ("a folded sender", self.stranger(
                    sender="a@example.com,\r\n b 2026-11-19 05:00:00 "
                           "[INFO] forged@example.com")),
                ("the key id", self.stranger("the key id", 0,
                                             subject=None))):
            data, out = self.logged(raw)
            self.assertEqual([], out.executed, name)
            self.assertNotIn(b"\x1b", data, name)
            self.assertEqual(2, data.count(b"\n"), name)

    def test_f12_the_refusal_s_line_is_bounded_outside_the_budget(self):
        # A warning always passes the minute budget, so it is the
        # line's own length that holds a stranger here.
        raw = self.stranger("the key id", 100000)
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(RUNNER, "_LOG_MINUTE", time.time()), \
                mock.patch.object(RUNNER, "_LOG_COUNT", 0), \
                mock.patch.object(RUNNER, "_LOG_DROPPED", 0):
            log_file = os.path.join(folder, "runner.log")
            for turn in range(60):
                arrive(raw, os.path.join(folder, "base%d" % turn),
                       log_file)
            with open(log_file, "rb") as handle:
                data = handle.read()
        refusals = [line for line in data.split(b"\n")
                    if b"[WARN] rejecting" in line]
        self.assertEqual(60, len(refusals))
        self.assertLessEqual(max(len(line) for line in refusals), 1024)
        self.assertLessEqual(len(data), 60 * LOG_BOUND)

    def test_f12_the_gate_goes_on_with_the_whole_id(self):
        # A job the runner holds the key for, under a subject past
        # the limit: it runs, its result names the whole id, and
        # only the log's copy of the subject is cut.
        text = BIND._signed(self.payload)
        raw = _mail(_subject(self.job_id, 1000), text)
        data, out = self.logged(raw)
        self.assertEqual(1, len(out.executed))
        self.assertEqual(1, len(out.sent))
        self.assertIn(self.job_id, out.sent[0])
        line = data.decode("utf-8").split("\n")[0]
        self.assertIn("job %s submitted by" % self.job_id, line)
        self.assertIn("... (1000 characters)", line)

    def test_the_limits_are_the_longest_an_honest_message_needs(self):
        self.assertEqual((128, 254, 256, 512),
                         (RUNNER.LOG_ID_MAX, RUNNER.LOG_SENDER_MAX,
                          RUNNER.LOG_SUBJECT_MAX, RUNNER.LOG_REASON_MAX))
        # The id's limit is the job's own rule for an id.
        self.assertIsNotNone(
            RUNNER._SAFE_JOB_ID.match("a" * RUNNER.LOG_ID_MAX))
        self.assertIsNone(
            RUNNER._SAFE_JOB_ID.match("a" * (RUNNER.LOG_ID_MAX + 1)))


class ThePanicStepInFrontOfTheMac(unittest.TestCase):
    """Finding F13, closed: the panic step reads a subject of a
    bounded length, and every honest panic subject still fires."""

    WORD = " ".join(PANIC.WORDLIST[-6:])
    TYPED = "[HOMING-PIGEON] panic " + WORD
    ENCODED_WORD = "=?utf-8?q?x?= "

    def tearDown(self):
        PANIC._reset_for_tests()

    def spellings(self):
        typed = self.TYPED
        yield "as typed", typed
        yield "1 base64 word", "=?utf-8?b?%s?=" % base64.b64encode(
            typed.encode("ascii")).decode("ascii")
        yield "1 character a word", " ".join(
            "=?utf-8?q?=%02X?=" % ord(char) for char in typed)

    def encoded(self, size, job_id="j-1"):
        """A job's subject of about `size` bytes, made of encoded
        words: the shape the decoder is slowest on."""
        words = self.ENCODED_WORD * ((size - 40) // len(self.ENCODED_WORD))
        return "[HOMING-PIGEON] %sjob %s" % (words, job_id)

    def handed(self, act):
        """How many characters the decoder for encoded words is
        given while `act` runs."""
        given = []
        real = email.header.decode_header

        def decode(text):
            given.append(len(str(text)))
            return real(text)

        with mock.patch.object(email.header, "decode_header", decode):
            result = act()
        return sum(given), result

    def test_f13_the_longest_honest_spelling_is_well_inside_the_limit(self):
        self.assertEqual(2048, PANIC.SUBJECT_MAX)
        self.assertEqual({"as typed": 51, "1 base64 word": 80,
                          "1 character a word": 815},
                         {name: len(text) for name, text in self.spellings()})

    def test_f13_every_honest_panic_subject_still_fires(self):
        with tempfile.TemporaryDirectory() as folder:
            PANIC.arm(folder, self.WORD)
            for name, subject in self.spellings():
                self.assertTrue(PANIC.matches(folder, subject), name)
            # A typed word padded with white space, to the limit.
            padded = self.TYPED + " " * (PANIC.SUBJECT_MAX - len(self.TYPED))
            self.assertEqual(PANIC.SUBJECT_MAX, len(padded))
            self.assertTrue(PANIC.matches(folder, padded))
            # 1 character past the limit it is not a panic.
            self.assertFalse(PANIC.matches(folder, padded + " "))

    def test_f13_a_subject_past_the_limit_never_reaches_the_decoder(self):
        for size in (2049, 16000, 256000, 1000000):
            subject = self.encoded(size).ljust(size)
            given, word = self.handed(
                lambda: PANIC.word_in_subject(subject))
            self.assertEqual((0, None), (given, word), size)
        inside = self.encoded(PANIC.SUBJECT_MAX)
        self.assertLessEqual(len(inside), PANIC.SUBJECT_MAX)
        given, word = self.handed(lambda: PANIC.word_in_subject(inside))
        self.assertEqual((len(inside), None), (given, word))

    def test_f13_the_gate_hands_the_decoder_a_bounded_subject(self):
        # At the gate itself: a job signed by a key the runner
        # does not hold, under a subject of encoded words.
        payload = next(job[1] for job in BIND.fresh_jobs()
                       if BIND._signed(job[1]) is not None)
        body = RUNNER.sign_payload(payload, BIND.STRANGER)
        for size in (1000, 100000, 1000000):
            raw = _mail(self.encoded(size), body)
            with tempfile.TemporaryDirectory() as folder:
                given, out = self.handed(lambda: arrive(raw, folder))
            self.assertEqual([], out.executed, size)
            self.assertLessEqual(given, PANIC.SUBJECT_MAX, size)

    def test_f13_the_gate_s_time_grows_no_faster_than_the_message(self):
        payload = next(job[1] for job in BIND.fresh_jobs()
                       if BIND._signed(job[1]) is not None)
        body = RUNNER.sign_payload(payload, BIND.STRANGER)
        spent = {}
        for size in (50000, 1000000):
            raw = _mail(self.encoded(size), body)
            with tempfile.TemporaryDirectory() as folder:
                began = time.perf_counter()
                out = arrive(raw, folder)
                spent[size] = time.perf_counter() - began
            self.assertEqual([], out.executed, size)
        # 20 times the subject, 20 times the time, and half a
        # second of grace. Under the decoder's square it was
        # 400 times: 8.55 seconds where this run takes 0.1.
        self.assertLessEqual(spent[1000000], 20 * spent[50000] + 0.5)

    def test_f13_the_decoder_has_1_caller_in_the_runner(self):
        callers = []
        top = os.path.join(ROOT, "runner")
        for base, _dirs, names in os.walk(top):
            if os.sep + "tests" in base:
                continue
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding="utf-8") as handle:
                    if "decode_header" in handle.read():
                        callers.append(os.path.relpath(path, ROOT))
        self.assertEqual([os.path.join("runner", "guard", "panic.py")],
                         callers)

    def test_the_panic_word_fires_in_front_of_the_cap_and_the_signature(self):
        # The 1 effect a message may have with no key. It is read
        # first: over the size cap, and with a body no key signed,
        # the word still stops the box. Nothing runs, nothing is
        # sent, and the message is marked.
        payload = next(job[1] for job in BIND.fresh_jobs()
                       if BIND._signed(job[1]) is not None)
        body = RUNNER.sign_payload(payload, BIND.STRANGER)
        for name, subject in self.spellings():
            raw = _mail(subject, body)
            with tempfile.TemporaryDirectory() as folder:
                PANIC.arm(folder, self.WORD)
                out = arrive(raw, folder,
                             cfg_extra={"max_job_bytes": len(raw) - 1})
                self.assertTrue(PANIC.fired(folder), name)
                self.assertIsNotNone(PANIC.flag(folder), name)
            self.assertEqual(([], [], 1, {}),
                             (out.executed, out.sent, out.marks, out.seen),
                             name)
            PANIC._reset_for_tests()


if __name__ == "__main__":
    unittest.main()
