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
import contextlib
import hmac
import io
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SUBJECT_SIZES = (1000, 10000, 100000)
BODY_SIZES = (10000, 100000)
EVENTS = "security-events.jsonl"


def _mail(subject, body):
    """1 mail as octets, under a subject given whole."""
    return (("Subject: %s\r\nFrom: si@example.com\r\n"
             "MIME-Version: 1.0\r\n"
             "Content-Type: text/plain; charset=utf-8\r\n"
             "Content-Transfer-Encoding: 8bit\r\n\r\n" % subject
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


def arrive(raw, folder, log_file=None):
    """1 arrival at handle_mail with cleartext allowed: what ran,
    what was sent, the seen set, the mailbox marks, the log's
    lines, and the counts of work. With a log file the runner's
    own log writes to it."""
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
    imap, seen = DOOR._IMAP2(), {}
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
    """S4: what 1 refused message adds to the runner's own log."""

    def added(self, subject_size):
        entry_id, payload, job_id = next(
            job for job in BIND.fresh_jobs()
            if BIND._signed(job[1]) is not None)
        text = RUNNER.sign_payload(payload, BIND.STRANGER)
        raw = _mail(_subject(job_id, subject_size), text)
        with tempfile.TemporaryDirectory() as folder:
            log_file = os.path.join(folder, "runner.log")
            out = arrive(raw, os.path.join(folder, "base"), log_file)
            written = os.path.getsize(log_file)
        return written, out.printed, len(raw)

    def test_s4_the_log_gains_the_subject_as_it_is_written(self):
        # A standing gap, pinned as it stands. The gate logs the
        # subject before the signature, so a refused message adds
        # to the log in step with its subject. A change that
        # bounds the line turns this pin, and the page with it.
        small, _, _ = self.added(None)
        for size in SUBJECT_SIZES:
            written, printed, _raw = self.added(size)
            self.assertGreaterEqual(written - small, size - 200, size)
            self.assertGreaterEqual(printed, size, size)

    def test_s4_what_it_gains_is_no_more_than_the_message_and_a_line(self):
        for size in (None,) + SUBJECT_SIZES:
            written, _printed, raw = self.added(size)
            self.assertLessEqual(written, raw + 2000, size)


if __name__ == "__main__":
    unittest.main()
