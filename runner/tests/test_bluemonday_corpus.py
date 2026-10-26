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
            self.assertIn(rec["kind"], ("seed", "grow"))
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
                              ("dtls", B.seeds_dtls())):
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
        for seeds in (B.seeds_crypto, B.seeds_stash, B.seeds_dtls):
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
