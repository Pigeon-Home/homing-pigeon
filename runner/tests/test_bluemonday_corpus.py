# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Project blueMonday: the fuzz corpus replays on every leg (Q62).

runner/tests/bluemonday/<target>.jsonl is the corpus the tool
runner/tools/bluemonday_corpus.py grew against the verifiers: the
seed fixtures and every mutation that reached a new arc. This
module runs each entry against its target's contract, with no
tracer and no hypothesis, so a leg that ships a reader which
raises the wrong thing, returns the wrong shape, or disagrees with
its twin goes red here before a Q is ever written.

A crash the tool wrote to <target>.crashes.jsonl is replayed too,
as an expectedFailure probe per entry: it stays red-as-expected
until the reader is fixed, and then turns into an unexpected
success, which is the signal to run `promote`.

The rest of the module tests the tool: the tracer gives back the
tracer it displaced (a coverage run's), a grow in memory writes
nothing, the mutators keep their caps, the checker catches a
broken reader, and the fixtures name nothing real.
"""
import argparse
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import bluemonday_corpus as B  # noqa: E402

_MAILBOX = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _replay(target):
    """[(entry, crash)] for the committed corpus of one target."""
    entries = B.load(B.corpus_path(target))
    session = B.Session(target, entries)
    B._with_rig(lambda: [session.run(e, trace=False) for e in entries])
    return entries, session


class CorpusReplayTest(unittest.TestCase):
    """Every committed entry meets its target's contract."""

    def _check(self, target):
        entries, session = _replay(target)
        self.assertTrue(entries, f"{target}: the corpus is empty; run "
                        "`python runner/tools/bluemonday_corpus.py seed`")
        crashes = [f"{e['id']} ({e['from']}, {e['mutator']}): {c}"
                   for e, c in session.crashes]
        self.assertEqual(crashes, [], f"{target}: contract broken by:\n  "
                         + "\n  ".join(crashes))
        # Both halves of each contract are exercised: something was
        # trusted and something was refused.
        self.assertGreater(session.outcomes["accepted"], 0, target)
        self.assertGreater(session.outcomes["refused"], 0, target)

    def test_wire(self):
        self._check("wire")

    def test_cloud(self):
        self._check("cloud")

    def test_v2(self):
        self._check("v2")

    def test_crypto(self):
        self._check("crypto")

    def test_local(self):
        self._check("local")

    def test_stash(self):
        self._check("stash")

    def test_mail(self):
        self._check("mail")

    def test_dtls(self):
        self._check("dtls")

    def test_board(self):
        self._check("board")

    def test_board_ops(self):
        self._check("board_ops")

    def test_channels(self):
        self._check("channels")

    def test_manifest(self):
        self._check("manifest")

    def test_queries(self):
        self._check("queries")

    def test_names(self):
        self._check("names")

    def test_query(self):
        self._check("query")

    def test_board_mail(self):
        self._check("board_mail")

    def test_v2_mail(self):
        self._check("v2_mail")

    def test_the_corpus_agrees_with_itself_on_the_windows_surface(self):
        bad = []
        for target in B.TARGETS:
            for entry, host, windows in B.platform_disagreements(target):
                bad.append(f"{target} {entry['id']} ({entry['from']}): "
                           f"host {host}, windows {windows}")
        self.assertEqual(bad, [])

    def test_the_grammar_dictionary_carries_the_drafts_members(self):
        for name in ("reply_to", "runner_id", "timeout_sec",
                     "script_sha384", "stdout", "exit_code"):
            self.assertIn(name, B._KEYS)
        for value in ("exec", "ping", "result", "fail"):
            self.assertIn(value, B._VALUES)
        self.assertIn("[HOMING-PIGEON] result ", B._DICT)
        self.assertIn('"kind":"ping"', B._DICT)

    def test_inbox(self):
        self._check("inbox")

    def test_local_inbox(self):
        self._check("local_inbox")

    def test_secret(self):
        self._check("secret")


class CrashProbesTest(unittest.TestCase):
    """One probe per crash on file, under expectedFailure: it passes
    only once the reader is fixed, and an unexpected success says
    to run `promote`."""


def _make_probe(target, record):
    def probe(self):
        entry = {k: record[k] for k in
                 ("id", "kind", "data", "from", "mutator", "arcs")}
        B._with_rig(lambda: B.check(target, entry))
    probe.__doc__ = f"{target} {record['id']}: {record.get('detail')}"
    return unittest.expectedFailure(probe)


for _target in B.TARGETS:
    for _record in B.load(B.corpus_path(_target, crashes=True)):
        setattr(CrashProbesTest, f"test_{_target}_{_record['id']}",
                _make_probe(_target, _record))


class CorpusFilesTest(unittest.TestCase):
    def _lines(self, target, crashes=False):
        path = B.corpus_path(target, crashes=crashes)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return [line.rstrip("\n") for line in fh if line.strip()]

    def test_every_target_has_a_stamped_corpus(self):
        for target in B.TARGETS:
            lines = self._lines(target)
            self.assertIsNotNone(lines, target)
            head = json.loads(lines[0])
            self.assertEqual(head, B.header(target), target)
            self.assertEqual(head["Agent-Stamp"], B.STAMP)

    def test_entries_are_well_formed_and_unique(self):
        for target in B.TARGETS:
            seen = set()
            for entry in B.load(B.corpus_path(target)):
                self.assertEqual(set(entry), {"id", "kind", "data", "from",
                                              "mutator", "arcs"}, target)
                self.assertIn(entry["kind"], ("text", "payload"))
                self.assertEqual(entry["id"],
                                 B.entry_id(entry["kind"], entry["data"]),
                                 f"{target}: id does not match the data")
                self.assertNotIn(entry["id"], seen, f"{target}: duplicate")
                seen.add(entry["id"])
            self.assertTrue(any(e["mutator"] == "seed" for e in
                                B.load(B.corpus_path(target))), target)

    def test_files_are_ascii_with_no_raw_control_in_an_entry(self):
        # ensure_ascii keeps lone surrogates and controls as escapes,
        # so the files survive every checkout and every editor. The
        # tool writes LF; a Windows checkout may turn that into CRLF
        # (autocrlf), which the loader strips, so the line end is
        # not asserted -- a CR anywhere else would be.
        for target in B.TARGETS:
            path = B.corpus_path(target)
            with open(path, "rb") as fh:
                blob = fh.read()
            blob.decode("ascii")
            self.assertNotIn(b"\r", blob.replace(b"\r\n", b"\n"), target)
            for raw in blob.split(b"\n"):
                self.assertFalse(any(c < 32 for c in raw.rstrip(b"\r")),
                                 f"{target}: a raw control in an entry")

    def test_runs_and_arc_maps_carry_the_stamp_and_parse(self):
        with open(B.runs_path(), encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        head = json.loads(lines[0])
        self.assertEqual(head.get("Agent-Stamp"), B.STAMP)
        self.assertGreater(len(lines), 1, "no run recorded yet")
        for line in lines[1:]:
            rec = json.loads(line)
            self.assertIn(rec["kind"], ("seed", "grow", "survivors"))
            if rec["kind"] == "survivors":
                # One line per survivors run: the readers mutated and
                # the tally for each (test_bluemonday_survivors holds
                # the report itself).
                for key in ("when", "head", "seed", "modules", "seconds"):
                    self.assertIn(key, rec, line[:120])
                for name, tally in rec["modules"].items():
                    self.assertEqual(set(tally), {"mutants", "killed",
                                                  "survived", "timeout",
                                                  "broken"}, name)
                continue
            self.assertIn(rec["target"], B.TARGETS)
            for key in ("when", "head", "entries_before", "entries_after",
                        "arcs_before", "arcs_after", "kept", "crashes",
                        "outcomes", "seconds"):
                self.assertIn(key, rec, line[:120])
            if rec["kind"] == "grow":
                for key in ("rounds", "seed", "tried", "mutators_tried",
                            "mutators_kept"):
                    self.assertIn(key, rec, line[:120])
        for target in B.TARGETS:
            with open(B.arcs_path(target), encoding="utf-8") as fh:
                arcs = json.load(fh)
            self.assertEqual(arcs["Agent-Stamp"], B.STAMP)
            self.assertEqual(arcs["target"], target)
            self.assertTrue(arcs["arcs"], target)
            for row in arcs["arcs"]:
                self.assertEqual(len(row), 3)
                self.assertIsInstance(row[0], str)
                self.assertFalse(row[0].startswith("/"), row[0])
                self.assertIsInstance(row[1], int)
                self.assertIsInstance(row[2], int)
            self.assertEqual(arcs["arcs"], sorted(arcs["arcs"]))

    def test_seed_and_grow_record_their_runs(self):
        tmp = tempfile.mkdtemp(prefix="hp-bluemonday-runs-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(B, "CORPUS_DIR", tmp):
            B.cmd_seed(argparse.Namespace(target="v2"), out=lambda s: None)
            B.cmd_grow(argparse.Namespace(target="v2", rounds=20, seed=3,
                                          verbose=False, jobs=1),
                       out=lambda s: None)
            with open(B.runs_path(), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            self.assertEqual(len(lines), 3)
            seed_rec, grow_rec = json.loads(lines[1]), json.loads(lines[2])
            self.assertEqual((seed_rec["kind"], grow_rec["kind"]),
                             ("seed", "grow"))
            self.assertEqual(grow_rec["seed"], 3)
            self.assertEqual(grow_rec["rounds"], 20)
            self.assertRegex(grow_rec["python"], r"^\d+\.\d+")
            self.assertIn("-", grow_rec["platform"])
            self.assertEqual(grow_rec["entries_before"],
                             seed_rec["entries_after"])
            self.assertTrue(os.path.exists(B.arcs_path("v2")))

    def test_fixtures_name_nothing_real(self):
        # Invented names only: no home directories, no mailboxes
        # outside example.com, no user names from any machine.
        for target in B.TARGETS:
            for line in self._lines(target):
                self.assertNotIn("/home/", line, target)
                self.assertNotIn("/Users/", line, target)
                self.assertNotIn("Users\\\\", line, target)
                for domain in _MAILBOX.findall(line):
                    # RFC 2606's reserved names only; a mutated entry
                    # may carry a broken form of one (the seeds are
                    # invented, the mutators are blind), so the test
                    # is that the reserved name is still in it.
                    self.assertTrue(
                        "example" in domain.lower()
                        or domain.lower().endswith((".invalid", ".test")),
                        f"{target}: a mailbox at {domain}")


class ToolTest(unittest.TestCase):
    def test_the_tracer_gives_back_the_tracer_it_displaced(self):
        def sentinel(frame, event, arg):
            return None
        tracer = B.ArcTracer([os.path.join(ROOT, "runner", "wire",
                                           "protocol_v2.py")])
        previous = sys.gettrace()
        sys.settrace(sentinel)
        try:
            got = tracer.run(B.P2.validate, B._v2("answer"))
            self.assertIs(sys.gettrace(), sentinel)
        finally:
            sys.settrace(previous)
        self.assertEqual(got["type"], "answer")
        self.assertGreater(tracer.new, 0)
        self.assertTrue(all(f.endswith("protocol_v2.py")
                            for f, _a, _b in tracer.arcs))

    def test_the_tracer_gives_back_the_tracer_when_the_call_raises(self):
        tracer = B.ArcTracer([os.path.join(ROOT, "runner", "wire",
                                           "protocol_v2.py")])
        previous = sys.gettrace()
        with self.assertRaises(ValueError):
            tracer.run(B.P2.validate, "not a message")
        self.assertIs(sys.gettrace(), previous)

    def test_a_grow_in_memory_writes_nothing(self):
        before = {}
        for name in os.listdir(B.CORPUS_DIR):
            with open(os.path.join(B.CORPUS_DIR, name), "rb") as fh:
                before[name] = fh.read()
        session = B.Session("v2", B.seeds_v2())
        B._with_rig(session.baseline)
        arcs = len(session.tracer.arcs)
        added = B._with_rig(lambda: session.grow(random.Random(5), 60))
        self.assertEqual(session.outcomes["crash"], 0, session.crashes)
        self.assertEqual(session.crashes, [])
        self.assertEqual(len(session.entries), len(B.seeds_v2()) + len(added))
        self.assertEqual(len(session.tracer.arcs),
                         arcs + sum(e["arcs"] for e in added))
        after = {}
        for name in os.listdir(B.CORPUS_DIR):
            with open(os.path.join(B.CORPUS_DIR, name), "rb") as fh:
                after[name] = fh.read()
        self.assertEqual(before, after)

    def test_mutators_keep_the_caps_and_change_something(self):
        rng = random.Random(11)
        for target, seeds in (("wire", B.seeds_wire()),
                              ("crypto", B.seeds_crypto()),
                              ("v2", B.seeds_v2()),
                              ("dtls", B.seeds_dtls()),
                              ("board", B.seeds_board()),
                              ("board_ops", B.seeds_board_ops()),
                              ("channels", B.seeds_channels()),
                              ("inbox", B.seeds_inbox()),
                              ("local_inbox", B.seeds_local_inbox()),
                              ("secret", B.seeds_secret()),
                              ("manifest", B.seeds_manifest()),
                              ("queries", B.seeds_queries()),
                              ("names", B.seeds_names()),
                              ("query", B.seeds_query()),
                              ("board_mail", B.seeds_board_mail()),
                              ("v2_mail", B.seeds_v2_mail())):
            for _ in range(150):
                parent = rng.choice(seeds)
                child = B.mutate(rng, parent, seeds, target)
                if child is None:
                    continue
                data, name = child
                self.assertNotEqual(data, parent["data"], name)
                if parent["kind"] == "text":
                    self.assertIsInstance(data, str, name)
                    self.assertLessEqual(
                        len(data.encode("utf-8", "surrogatepass")),
                        B.MAX_TEXT, name)
                else:
                    self.assertLessEqual(
                        len(json.dumps(data, ensure_ascii=True)),
                        B.MAX_PAYLOAD, name)
                    self.assertLessEqual(B._depth(data), B.MAX_DEPTH + 2)

    def test_seeds_are_the_same_on_every_run(self):
        # encrypt_body's nonce is drawn from a counter while seeding,
        # so a sealed seed's id is stable and `seed` adds nothing to
        # a corpus that already holds it.
        for seeds in (B.seeds_crypto, B.seeds_stash, B.seeds_dtls,
                      B.seeds_board, B.seeds_board_ops, B.seeds_channels,
                      B.seeds_inbox, B.seeds_local_inbox, B.seeds_manifest,
                      B.seeds_queries, B.seeds_names, B.seeds_query,
                      B.seeds_board_mail, B.seeds_v2_mail):
            first = [e["id"] for e in seeds()]
            self.assertEqual(first, [e["id"] for e in seeds()])
            self.assertEqual(len(first), len(set(first)))

    def test_seed_adds_only_what_the_corpus_lacks(self):
        tmp = tempfile.mkdtemp(prefix="hp-bluemonday-seed-")
        self.addCleanup(shutil.rmtree, tmp, True)
        lines = []
        with mock.patch.object(B, "CORPUS_DIR", tmp):
            B.cmd_seed(argparse.Namespace(target="v2"), out=lines.append)
            first = B.load(B.corpus_path("v2"))
            B.cmd_seed(argparse.Namespace(target="v2"), out=lines.append)
            second = B.load(B.corpus_path("v2"))
        self.assertEqual(len(first), len(B.seeds_v2()))
        self.assertEqual([e["id"] for e in first], [e["id"] for e in second])
        self.assertTrue(lines[-1].startswith("v2: 0 seeds added"))

    def test_parallel_grow_runs_targets_jobs_at_a_time(self):
        commands = B.grow_commands(["wire", "v2", "stash"], 50, 9, False)
        self.assertEqual([t for t, _c in commands], ["wire", "v2", "stash"])
        for target, cmd in commands:
            self.assertIn("--target", cmd)
            self.assertEqual(cmd[cmd.index("--target") + 1], target)
            self.assertEqual(cmd[cmd.index("--jobs") + 1], "1")
        live = []
        peak = []

        class Fake:
            def __init__(self, cmd):
                self.cmd = cmd
                self.returncode = 3 if "v2" in cmd else 0
                live.append(self)
                peak.append(len(live))

            def poll(self):
                return self.returncode

            def communicate(self):
                live.remove(self)
                return (f"{self.cmd[self.cmd.index('--target') + 1]}: "
                        f"done {self.cmd[self.cmd.index('--seed') + 1]}\n"
                        ).encode(), None
        lines = []
        status = B.run_parallel(commands, 2, out=lines.append, spawn=Fake)
        self.assertEqual(status, 3)
        self.assertEqual(lines, ["wire: done 9", "v2: done 9",
                                 "stash: done 9"])
        self.assertLessEqual(max(peak), 2)

    def test_a_timed_grow_cycles_the_targets_with_fresh_seeds(self):
        commands = B.grow_commands(["wire", "v2"], 50, 9, False)
        ticks = [0.0]

        def clock():
            ticks[0] += 10.0
            return ticks[0]

        class Fake:
            def __init__(self, cmd):
                self.cmd = cmd
                self.returncode = 0

            def poll(self):
                return 0

            def communicate(self):
                return (f"{self.cmd[self.cmd.index('--target') + 1]} "
                        f"{self.cmd[self.cmd.index('--seed') + 1]}"
                        ).encode(), None
        lines = []
        # One minute on a clock that moves ten seconds per look: the
        # targets cycle a few times, each with the seed moved on, and
        # nothing starts after the deadline.
        B.run_parallel(commands, 2, out=lines.append, spawn=Fake,
                       minutes=1.0, clock=clock, nap=0)
        self.assertGreater(len(lines), 2)
        self.assertEqual(lines[:2], ["wire 9", "v2 9"])
        self.assertIn("wire 10", lines)
        self.assertEqual(len(lines), len(set(lines)))

    def test_entry_ids_follow_the_data(self):
        a = B.make_entry("text", "abc", "seed:x", "seed")
        b = B.make_entry("text", "abc", "seed:y", "t_drop")
        c = B.make_entry("payload", "abc", "seed:x", "seed")
        self.assertEqual(a["id"], b["id"])
        self.assertNotEqual(a["id"], c["id"])
        self.assertEqual(len(a["id"]), 16)

    def test_the_checker_catches_a_reader_that_raises_the_wrong_thing(self):
        entry = B.seeds_crypto()[0]
        with mock.patch.object(B.JC, "decrypt_body",
                               side_effect=AttributeError("encode")):
            with self.assertRaises(B.Crash) as cm:
                B.check("crypto", entry)
        self.assertEqual(cm.exception.kind, "exception")
        self.assertIn("AttributeError", cm.exception.detail)

    def test_the_checker_catches_a_reader_of_the_wrong_shape(self):
        entry = [e for e in B.seeds_wire() if e["kind"] == "text"][0]
        with mock.patch.object(B.V, "verify_body", return_value=["x"]):
            with self.assertRaises(B.Crash) as cm:
                B.check("wire", entry)
        self.assertEqual(cm.exception.kind, "shape")

    def test_the_checker_catches_a_forgery(self):
        entry = [e for e in B.seeds_wire() if e["kind"] == "payload"][0]
        real = B.V.verify_body

        def trusting(body, secret):
            return real(body, B.SECRET)
        with mock.patch.object(B.V, "verify_body", trusting):
            with self.assertRaises(B.Crash) as cm:
                B.check("wire", entry)
        self.assertEqual(cm.exception.kind, "forgery")

    def test_the_checker_catches_the_twins_disagreeing(self):
        entry = [e for e in B.seeds_wire() if e["kind"] == "text"][0]
        with mock.patch.object(B.V, "verify_body",
                               side_effect=ValueError("no")):
            with self.assertRaises(B.Crash) as cm:
                B.check("cloud", entry)
        self.assertEqual(cm.exception.kind, "agreement")

    def test_the_differential_allows_only_the_control_character_arm(self):
        # Q65: the agent trusting what the front-end refuses is a
        # finding unless a control character in the signed object
        # explains it (Q61's one difference by design).
        clean = [e for e in B.seeds_wire() if e["from"] == "seed:compact"][0]
        control = [e for e in B.seeds_wire()
                   if e["from"] == "seed:control"][0]
        self.assertEqual(B.check("wire", control), "accepted")
        self.assertEqual(B.check("cloud", control), "refused")
        with mock.patch.object(B.SJ, "verify_body",
                               side_effect=ValueError("mismatch")):
            with self.assertRaises(B.Crash) as cm:
                B.check("wire", clean)
            self.assertEqual(cm.exception.kind, "agreement")
            self.assertIn("no control character explains it",
                          cm.exception.detail)
            # The same refusal on the control-character body is the
            # designed difference, not a finding.
            self.assertEqual(B.check("wire", control), "accepted")

    def test_the_mail_checker_catches_the_extension_disagreeing(self):
        entry = [e for e in B.seeds_mail() if e["from"] == "seed:plain"][0]
        self.assertEqual(B.check("mail", entry), "accepted")
        ext = B._email_extension()
        with mock.patch.object(ext, "_subject_body",
                               return_value=("[HOMING-PIGEON] job x", "")):
            with self.assertRaises(B.Crash) as cm:
                B.check("mail", entry)
        self.assertEqual(cm.exception.kind, "agreement")

    def test_the_mail_checker_catches_a_reply_target_from_a_header(self):
        entry = [e for e in B.seeds_mail()
                 if e["from"] == "seed:reply_to_header_only"][0]
        self.assertEqual(B.check("mail", entry), "accepted")
        ext = B._email_extension()
        with mock.patch.object(ext, "reply_target",
                               return_value="spoof@example.net"):
            with self.assertRaises(B.Crash) as cm:
                B.check("mail", entry)
        self.assertEqual(cm.exception.kind, "contract")
        inside = [e for e in B.seeds_mail()
                  if e["from"] == "seed:reply_to_inside"][0]
        self.assertEqual(B.check("mail", inside), "accepted")

    def test_mail_bytes_round_trip_through_the_corpus(self):
        raw = b"Subject: x\r\n\r\n\xe9\xe8 not utf-8\r\n"
        text = raw.decode("utf-8", "surrogateescape")
        line = json.dumps(text, ensure_ascii=True)
        self.assertEqual(B._raw_bytes(json.loads(line)), raw)

    def test_the_dtls_checker_accepts_a_hello_and_refuses_a_short_one(self):
        hello = [e for e in B.seeds_dtls()
                 if e["from"] == "seed:client_hello"][0]
        server = [e for e in B.seeds_dtls()
                  if e["from"] == "seed:server_hello"][0]
        empty = [e for e in B.seeds_dtls() if e["from"] == "seed:empty"][0]
        overrun = [e for e in B.seeds_dtls()
                   if e["from"] == "seed:length_overrun"][0]
        self.assertEqual(B.check("dtls", hello), "accepted")
        self.assertEqual(B.check("dtls", server), "accepted")
        self.assertEqual(B.check("dtls", empty), "refused")
        self.assertEqual(B.check("dtls", overrun), "refused")

    def test_the_dtls_checker_catches_a_parser_that_raises(self):
        hello = [e for e in B.seeds_dtls()
                 if e["from"] == "seed:client_hello"][0]
        with mock.patch.object(B.DT, "_split_records",
                               side_effect=RuntimeError("split")):
            with self.assertRaises(B.Crash) as cm:
                B.check("dtls", hello)
        self.assertEqual(cm.exception.kind, "exception")
        self.assertIn("RuntimeError", cm.exception.detail)

    def test_the_dtls_checker_catches_feed_raising(self):
        hello = [e for e in B.seeds_dtls()
                 if e["from"] == "seed:client_hello"][0]
        with mock.patch.object(B.DT.DtlsServerCore, "feed",
                               side_effect=TypeError("feed")):
            with self.assertRaises(B.Crash) as cm:
                B.check("dtls", hello)
        self.assertEqual(cm.exception.kind, "exception")
        self.assertIn("TypeError", cm.exception.detail)

    def test_dtls_bytes_round_trip_through_the_corpus(self):
        raw = bytes(range(256))
        text = B._dtls_text(raw)
        line = json.dumps(text, ensure_ascii=True)
        self.assertEqual(B._raw_bytes(json.loads(line)), raw)
        self.assertTrue(line.isascii())

    def test_the_board_checker_accepts_a_task_and_refuses_a_bad_id(self):
        good = [e for e in B.seeds_board() if e["from"] == "seed:open"][0]
        bad = [e for e in B.seeds_board() if e["from"] == "seed:bad_id"][0]
        review = [e for e in B.seeds_board() if e["from"] == "seed:review"][0]
        self.assertEqual(B.check("board", good), "accepted")
        self.assertEqual(B.check("board", review), "accepted")
        self.assertEqual(B.check("board", bad), "refused")

    def test_the_board_checker_catches_submit_raising(self):
        good = [e for e in B.seeds_board() if e["from"] == "seed:open"][0]
        with mock.patch.object(B.BD.Board, "submit",
                               side_effect=RuntimeError("submit")):
            with self.assertRaises(B.Crash) as cm:
                B.check("board", good)
        self.assertEqual(cm.exception.kind, "exception")
        self.assertIn("RuntimeError", cm.exception.detail)

    def test_the_channel_checker_keeps_the_neighbor(self):
        good = [e for e in B.seeds_channels()
                if e["from"] == "seed:two_jobs"][0]
        bad = [e for e in B.seeds_channels()
               if e["from"] == "seed:both_bad"][0]
        self.assertEqual(B.check("channels", good), "accepted")
        self.assertEqual(B.check("channels", bad), "refused")
        self.assertEqual(B.TR.FILE_MAX_BYTES, 4 * 1024 * 1024)

    def test_the_channel_checker_catches_fetch_raising(self):
        good = [e for e in B.seeds_channels()
                if e["from"] == "seed:two_jobs"][0]
        with mock.patch.object(B.TR, "fetch_channel_messages",
                               side_effect=RuntimeError("fetch")):
            with self.assertRaises(B.Crash) as cm:
                B.check("channels", good)
        self.assertEqual(cm.exception.kind, "exception")
        self.assertIn("RuntimeError", cm.exception.detail)
        self.assertEqual(B.TR.FILE_MAX_BYTES, 4 * 1024 * 1024)

    def test_the_manifest_checker_accepts_a_sense_and_refuses_a_typo(self):
        good = [e for e in B.seeds_manifest()
                if e["from"] == "seed:sense"][0]
        bad = [e for e in B.seeds_manifest()
               if e["from"] == "seed:unknown_field"][0]
        newer = [e for e in B.seeds_manifest()
                 if e["from"] == "seed:sense_newer_api"][0]
        self.assertEqual(B.check("manifest", good), "accepted")
        self.assertEqual(B.check("manifest", newer), "accepted")
        self.assertEqual(B.check("manifest", bad), "refused")

    def test_the_manifest_checker_catches_a_raise_that_is_not_valueerror(self):
        good = [e for e in B.seeds_manifest()
                if e["from"] == "seed:sense"][0]
        with mock.patch.object(B.EX, "parse_manifest",
                               side_effect=RuntimeError("manifest")):
            with self.assertRaises(B.Crash) as cm:
                B.check("manifest", good)
        self.assertEqual(cm.exception.kind, "exception")
        self.assertIn("RuntimeError", cm.exception.detail)

    def test_the_local_sequence_stores_the_neighbor_after_a_refusal(self):
        bad = [e for e in B.seeds_local() if e["from"] == "seed:empty"][0]
        good = [e for e in B.seeds_local()
                if e["from"] == "seed:alert_now"][0]
        out = {}

        def go():
            out["bad"] = B.check("local", bad)
            out["good"] = B.check("local", good)

        B._with_rig(go)
        self.assertEqual(out["bad"], "refused")
        self.assertEqual(out["good"], "accepted")

    def test_saturation_reads_the_last_grow(self):
        tmp = tempfile.mkdtemp(prefix="hp-bluemonday-sat-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(B, "CORPUS_DIR", tmp):
            self.assertEqual(B.saturation("v2"), "no grow recorded")
            B.cmd_seed(argparse.Namespace(target="v2"), out=lambda s: None)
            B.cmd_grow(argparse.Namespace(target="v2", rounds=5, seed=1,
                                          verbose=False, jobs=1, minutes=0),
                       out=lambda s: None)
            text = B.saturation("v2")
        self.assertTrue(text.startswith("saturated at 5 rounds")
                        or text.startswith("last grow +"), text)

    def test_a_reader_that_refuses_properly_is_a_refusal(self):
        # The jobcrypto finding that opened the campaign: a job_id
        # that is not text is the module's own refusal now.
        spec = {"envelope": B.seeds_crypto()[0]["data"]["envelope"],
                "job_id": 7, "key_id": ""}
        entry = B.make_entry("payload", spec, "test", "test")
        self.assertEqual(B.check("crypto", entry), "refused")
        spec = dict(spec, job_id="bm-exec-0001", key_id=["ops"])
        entry = B.make_entry("payload", spec, "test", "test")
        self.assertEqual(B.check("crypto", entry), "refused")

    def test_the_sig_slot_is_the_protocol_s(self):
        # A payload carrying its own sig member is read back with the
        # slot kept by one reader and overwritten by the other; the
        # checker compares the rest and calls neither a disagreement.
        entry = B.make_entry("payload", B._job(sig="0" * 96), "t", "t")
        self.assertEqual(B.check("wire", entry), "accepted")

    def test_replay_reports_and_exits_nonzero_on_a_crash(self):
        lines = []
        with mock.patch.object(B, "check",
                               side_effect=B.Crash("shape", "fake")):
            status = B.cmd_replay(
                argparse.Namespace(target="v2"),
                out=lines.append)
        self.assertEqual(status, 1)
        self.assertTrue(any("CRASH" in line for line in lines))

    def test_stats_names_every_target(self):
        lines = []
        status = B.cmd_stats(
            argparse.Namespace(target="all"),
            out=lines.append)
        self.assertEqual(status, 0)
        self.assertEqual([line.split(":")[0] for line in lines],
                         list(B.TARGETS))


if __name__ == "__main__":
    unittest.main()



class GrammarTest(unittest.TestCase):
    """The dictionary the drafts dictate (phase 4 of the plan)."""

    DRAFT = (
        "# A draft\n\nThe `job_id` member is 1*128 `job-id-char`. "
        "A `timeout_sec` above 3600 is reduced. `kind` is `exec` or "
        "`ping`; the spaced `not a token` is not one.\n\n"
        "```json\n{\"v\": 1, \"type\": \"job\", \"sig\": \"00\"}\n```\n"
        "```\nnot json\n```\n```\n{\"v\": 2, \"type\": \"answer\"}\n```\n")

    def test_build_grammar_reads_tokens_numbers_and_examples(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "draft-x-00.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.DRAFT)
            g = B.build_grammar([path])
            again = B.build_grammar([path])
        self.assertEqual(g, again)
        self.assertEqual(g["Agent-Stamp"], B.STAMP)
        self.assertEqual(g["tokens"], ["exec", "job-id-char", "job_id",
                                       "kind", "ping", "timeout_sec"])
        # 1*128, 3600, the examples' v values and the sig's 00, each
        # with its neighbours on both sides.
        self.assertEqual(g["numbers"], [-1, 0, 1, 2, 3, 127, 128, 129,
                                        3599, 3600, 3601])
        self.assertEqual(g["examples"], [
            {"from": "draft-x-00.md#1", "value": {"v": 1, "type": "job"}},
            {"from": "draft-x-00.md#3", "value": {"v": 2, "type": "answer"}}])

    def test_the_committed_dictionary_is_stamped_and_populated(self):
        with open(B.GRAMMAR_PATH, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertTrue(raw.isascii())
        g = json.loads(raw)
        self.assertEqual(g["Agent-Stamp"], B.STAMP)
        self.assertIn("job_id", g["tokens"])
        self.assertIn("[HOMING-PIGEON]", g["tokens"])
        self.assertIn(3600, g["numbers"])
        self.assertIn(-2, g["numbers"])
        sources = [e["from"] for e in g["examples"]]
        self.assertTrue(any(s.startswith("draft-homing-pigeon-00.md")
                            for s in sources))
        self.assertTrue(any(s.startswith("draft-homing-pigeon-v2-00.md")
                            for s in sources))
        for e in g["examples"]:
            self.assertNotIn("sig", e["value"])

    def test_grammar_mutators_use_the_drafts_words(self):
        rng = random.Random(4)
        tokens = set(B.grammar()["tokens"])
        text = '{"v": 1, "type": "job", "job_id": "bm-0001"}'
        hits = 0
        for _ in range(40):
            out = B.t_grammar(rng, text, [])
            self.assertNotEqual(out, text)
            if any(t in out and t not in text for t in tokens):
                hits += 1
        self.assertGreater(hits, 0)
        value = {"v": 1, "type": "job", "n": 5, "d": {"k": 1}}
        changed = 0
        for _ in range(60):
            out = B.p_grammar(rng, value, [])
            if out != value:
                changed += 1
                json.dumps(out)     # still a JSON value
                self.assertEqual(value, {"v": 1, "type": "job", "n": 5,
                                         "d": {"k": 1}})   # a copy, not it
        self.assertGreater(changed, 30)

    def test_draft_examples_seed_the_verifier_and_v2_targets(self):
        wire = {e["from"] for e in B.seeds_wire()}
        v2 = {e["from"] for e in B.seeds_v2()}
        self.assertTrue(any(f.startswith("seed:draft_") for f in wire))
        self.assertTrue(any(f.startswith("seed:draft_") for f in v2))


class SteeringTest(unittest.TestCase):
    """Saturation is per mutator, and a grow leans on the live ones
    (Muse, 2026-10-26)."""

    def test_weights_follow_the_keep_rate_with_a_floor(self):
        w = B.steering({"t_live": (100, 20), "t_dead": (1000, 0),
                        "t_new": (0, 0)})
        self.assertGreater(w["t_live"], w["t_dead"])
        self.assertGreaterEqual(w["t_dead"], w["t_live"] * B.STEER_FLOOR)
        self.assertGreater(w["t_new"], w["t_dead"])   # untried is not dead
        self.assertIsNone(B.steering({}))

    def test_pick_honours_the_weights(self):
        rng = random.Random(3)

        def a(rng, t, c):
            return t

        def b(rng, t, c):
            return t
        picks = [B.pick(rng, [a, b], {"a": 100.0, "b": 1.0}).__name__
                 for _ in range(300)]
        self.assertGreater(picks.count("a"), 250)
        self.assertIn("b", picks)
        self.assertIn(B.pick(rng, [a, b]).__name__, ("a", "b"))

    def test_history_and_saturation_read_the_records_by_time(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(B, "CORPUS_DIR", d):
            B.record_run({"kind": "grow", "target": "t", "when": "2026-01-02",
                          "mutators_tried": {"m1": 300, "m2": 50},
                          "mutators_kept": {"m2": 2}})
            B.record_run({"kind": "grow", "target": "t", "when": "2026-01-01",
                          "mutators_tried": {"m1": 10}, "mutators_kept": {}})
            B.record_run({"kind": "grow", "target": "u", "when": "2026-01-03",
                          "mutators_tried": {"m3": 500}, "mutators_kept": {}})
            self.assertEqual(B.mutator_history("t"),
                             {"m1": (310, 0), "m2": (50, 2)})
            self.assertEqual(B.mutator_history("t", grows=1),
                             {"m1": (300, 0), "m2": (50, 2)})
            self.assertEqual(B.mutator_saturation("t"), (["m2"], ["m1"]))
            self.assertEqual(B.last_grow("t")["when"], "2026-01-02")

    def test_a_steered_grow_records_it_and_keeps_every_mutator(self):
        entries = B.seeds_v2()
        session = B.Session("v2", entries)
        rng = random.Random(9)
        history = {m.__name__: (500, 0) for m in B.PAYLOAD_MUTATORS}
        history["p_text"] = (10, 5)
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(B, "CORPUS_DIR", d):
            B._with_rig(lambda: session.grow(rng, 400, history=history))
        self.assertGreater(session.mutators_tried.get("p_text", 0),
                           max(n for m, n in session.mutators_tried.items()
                               if m != "p_text"))
        self.assertGreater(len(session.mutators_tried), 3)


class ArchiveTest(unittest.TestCase):
    """Every child tried, on a disk outside the tree, named by the
    run record (Muse's hard drive, 2026-10-26)."""

    def test_the_archive_holds_every_child_and_the_record_names_it(self):
        import gzip
        entries = B.seeds_v2()
        session = B.Session("v2", entries)
        rng = random.Random(5)
        with tempfile.TemporaryDirectory() as d:
            archive = B.Archive(d, "v2", 5)
            with tempfile.TemporaryDirectory() as c, \
                    mock.patch.object(B, "CORPUS_DIR", c):
                B._with_rig(lambda: session.grow(rng, 120,
                                                 archive=archive.add))
            summary = archive.close()
            self.assertEqual(summary["tried"], session.tried)
            self.assertEqual(sorted(summary), ["bytes", "file", "sha384",
                                               "tried"])
            with gzip.open(os.path.join(d, summary["file"]), "rt",
                           encoding="utf-8") as fh:
                lines = [json.loads(l) for l in fh if l.strip()]
            self.assertEqual(lines[0]["Agent-Stamp"], B.STAMP)
            self.assertEqual(len(lines) - 1, session.tried)
            for row in lines[1:]:
                self.assertEqual(set(row), {"id", "from", "mutator", "kind",
                                            "data", "outcome", "arcs", "ms",
                                            "crash"})
                self.assertIn(row["outcome"], ("accepted", "refused",
                                               "crash"))
            self.assertEqual(sum(1 for r in lines[1:] if r["arcs"]),
                             len(session.mutators_kept) and sum(
                                 session.mutators_kept.values()))


class LearnTest(unittest.TestCase):
    """The dictionary learns from what the grows kept."""

    def test_harvest_takes_grown_tokens_only_with_provenance(self):
        entries = [
            {"id": "a1", "kind": "payload", "mutator": "seed",
             "data": {"seeded": "ignored"}},
            {"id": "b2", "kind": "payload", "mutator": "p_text",
             "data": {"found_key": "found value", "n": 1, "known": "x"}},
            {"id": "c3", "kind": "text", "mutator": "t_insert",
             "data": '{"job_id": "bm-}-0001", "sig": "ab"}'},
        ]
        got = B.harvest(entries, "t", known={"known", "sig", "job_id", "n"})
        self.assertEqual(got, {"found_key": "t:b2", "x": "t:b2",
                               "bm-}-0001": "t:c3", "ab": "t:c3"})
        doc = B.learn({"tokens": ["known", "n", "sig", "job_id"]},
                      {"t": entries})
        self.assertEqual([r["token"] for r in doc["learned"]],
                         ["ab", "bm-}-0001", "found_key", "x"])
        self.assertEqual(doc["learned"][0]["from"], "t:c3")

    def test_the_committed_dictionary_learned_from_the_corpora(self):
        with open(B.GRAMMAR_PATH, encoding="utf-8") as fh:
            g = json.load(fh)
        self.assertIn("learned", g)
        self.assertLessEqual(len(g["learned"]), B.LEARN_CAP)
        for row in g["learned"]:
            self.assertEqual(set(row), {"token", "from"})
            target, _id = row["from"].split(":")
            self.assertIn(target, B.TARGETS)
        self.assertTrue(set(r["token"] for r in g["learned"])
                        <= set(B.grammar()["words"]))
