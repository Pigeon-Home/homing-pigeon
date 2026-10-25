# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The live capture: honest docs, a clean scrub, and the runner reads it.

docs/reports/live-2026-10-25/ is three days of a real box. This holds
it to four promises:

1. The capture stays small and whole. The release snapshot carries
   every tracked file onto every box, so the 19,227 campaign records
   are one gzipped line each, not 19,227 files, and the folder has a
   size budget.
2. The scrub holds across every file, not only runner.log: no address
   outside the example domains, no other home directory, no key but
   AWS's published dummy, no password hash.
3. docs/use/live-examples.md quotes, it does not paraphrase: every
   line in a sourced excerpt is a line of the file it names, and its
   facts block is what runner/tools/live_capture.py computes.
4. The runner's own readers take the real files: the learning ledger
   folds, the remediation window reader returns every pressure event,
   every result has the result fields the protocol sends, and the log
   has the shape the docs and the Oracle read.

(Replaces test_live_shapes.py; its shape checks are kept below.)
"""
import gzip
import importlib.util
import json
import math
import os
import re
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LIVE = os.path.join(ROOT, "docs", "reports", "live-2026-10-25")
PAGE = os.path.join(ROOT, "docs", "use", "live-examples.md")


def _load_tool():
    path = os.path.join(ROOT, "runner", "tools", "live_capture.py")
    spec = importlib.util.spec_from_file_location("live_capture", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LC = _load_tool()
RECORDS = LC.records()
SIZE_BUDGET = 8 * 1024 * 1024


def _all_files():
    for dirpath, _dirs, names in os.walk(LIVE):
        for name in names:
            yield os.path.join(dirpath, name)


def _text_of(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


class CaptureLayoutTest(unittest.TestCase):
    def test_the_records_are_one_file_in_loop_order(self):
        self.assertFalse(os.path.exists(os.path.join(LIVE, "campaign-results")))
        self.assertEqual(len(RECORDS), 19227)
        names = [r["name"] for r in RECORDS]
        self.assertEqual(len(set(names)), len(names))
        loops = [int(n.split("-")[1]) for n in names]
        self.assertEqual(loops, sorted(loops))

    def test_the_gzip_files_are_reproducible(self):
        # mtime 0 and no file name in the header: the same records
        # pack to the same bytes, so a re-pack is not a diff.
        for path in _all_files():
            if path.endswith(".gz"):
                with open(path, "rb") as fh:
                    head = fh.read(10)
                self.assertEqual(head[4:8], b"\0\0\0\0", path)

    def test_the_folder_keeps_its_size_budget(self):
        total = sum(os.path.getsize(p) for p in _all_files())
        self.assertLess(total, SIZE_BUDGET,
                        "the live capture is %d bytes; every release "
                        "snapshot carries it onto every box" % total)


class ScrubTest(unittest.TestCase):
    EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    HOME = re.compile(r"/home/(?!runner\b)[a-z][a-z0-9_-]*|/Users/[A-Za-z]")
    KEYS = re.compile(r"(ghp_|gho_|github_pat_|AKIA[0-9A-Z]{16}|xox[bpa]-|"
                      r"ya29\.|AIza[0-9A-Za-z_-]{20}|-----BEGIN [A-Z ]*PRIVATE)")
    HASH = re.compile(r":\$(1|2[aby]?|5|6|y|gy|7)\$[^:]{8,}")

    def test_every_file_is_scrubbed(self):
        for path in _all_files():
            text = _text_of(path)
            rel = os.path.relpath(path, LIVE)
            with self.subTest(file=rel):
                for m in self.EMAIL.finditer(text):
                    self.assertRegex(m.group(0), r"@example\.(test|com)$")
                self.assertIsNone(self.HOME.search(text))
                for m in self.KEYS.finditer(text):
                    # AWS's own published example key, which the
                    # flagread job plants on purpose.
                    self.assertEqual(m.group(0), "AKIAIOSFODNN7EXAMPLE")
                self.assertIsNone(self.HASH.search(text))


class LivePageTest(unittest.TestCase):
    BLOCK = re.compile(r"<!-- source: (?P<src>[^ ]+) -->\n```[a-z]*\n"
                       r"(?P<body>.*?)\n```", re.S)

    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()

    def test_every_excerpt_is_quoted_from_its_file(self):
        blocks = list(self.BLOCK.finditer(self.page))
        self.assertGreaterEqual(len(blocks), 10)
        for b in blocks:
            source = LC.read_text(b.group("src"))
            lines = set(source.splitlines())
            for line in b.group("body").splitlines():
                if not line.strip():
                    continue
                with self.subTest(src=b.group("src"), line=line[:60]):
                    if "\u2026" in line:
                        # A cut line: its kept part opens a real line.
                        kept = line.split("\u2026")[0]
                        self.assertTrue(any(s.startswith(kept)
                                            for s in lines), line[:60])
                    else:
                        self.assertIn(line, lines)

    def test_the_facts_block_is_what_the_tool_computes(self):
        self.assertIn(LC.markdown(LC.facts()), self.page,
                      "run runner/tools/live_capture.py --write-doc "
                      "docs/use/live-examples.md")

    def test_the_pointers_lead_to_the_page(self):
        for doc in ("docs/use/faq.md", "docs/use/runbook.md", "SECURITY.md",
                    "docs/oracle/configuring-oracle.md"):
            with open(os.path.join(ROOT, doc), encoding="utf-8") as fh:
                self.assertIn("live-examples.md", fh.read(), doc)


class TheRunnerReadsTheRealFilesTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-live-")
        for name in ("oracle-learning.jsonl", "security-events.jsonl"):
            shutil.copy(os.path.join(LIVE, name), self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_the_learning_ledger_folds(self):
        from runner.oracle import learning
        recs = learning.read_records(self.base)
        self.assertEqual(len(recs), len(LC.jsonl("oracle-learning.jsonl")))
        state = learning.load_state(self.base)
        self.assertIsInstance(state, dict)

    def test_the_window_reader_returns_every_pressure_event(self):
        from runner.oracle import remediation
        events = remediation.resource_events_in_window(self.base, 0.0)
        want = [e for e in LC.jsonl("security-events.jsonl")
                if e["type"] == "resource_pressure"]
        self.assertEqual(len(events), len(want))

    def test_every_result_has_the_result_fields(self):
        from runner.guard import textutil
        from runner.runner import VIEW_ORDER
        for r in RECORDS:
            res = r["result"]
            self.assertIsInstance(res["exit_code"], int, r["name"])
            self.assertIsInstance(res["timed_out"], bool, r["name"])
            self.assertTrue(math.isfinite(res["duration_sec"])
                            and res["duration_sec"] >= 0, r["name"])
            self.assertIn(res["view"], VIEW_ORDER, r["name"])
            done = textutil._fromiso(res["completed_at"])
            self.assertIsNotNone(done.tzinfo, r["name"])
            self.assertIsInstance(res["stdout"], str, r["name"])

    def test_every_exit_code_is_the_one_its_script_chose(self):
        for r in RECORDS:
            want = 3 if LC.kind_of(r) == "exit3" else 0
            self.assertEqual(r["result"]["exit_code"], want, r["name"])

    def test_the_log_is_stamped_leveled_and_in_order(self):
        stamp = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ")
        level = re.compile(r"^\S+ \S+ \[(DEBUG|INFO|WARN|ERROR)\] ")
        prev = ""
        stamped = 0
        for line in LC.read_text("runner.log").splitlines():
            m = stamp.match(line)
            if not m:
                continue  # a continuation line of a multi-line message
            stamped += 1
            self.assertRegex(line, level)
            self.assertGreaterEqual(m.group(1), prev, line[:80])
            prev = m.group(1)
        self.assertGreater(stamped, 10000)

    def test_the_log_redacts_what_the_full_result_carries(self):
        log = LC.read_text("runner.log")
        self.assertIn("[REDACTED:aws_key]", log)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", log)
        self.assertTrue(any("AKIAIOSFODNN7EXAMPLE" in r["result"]["stdout"]
                            for r in RECORDS if LC.kind_of(r) == "flagread"))


class ShapeTest(unittest.TestCase):
    """The shapes the docs quote (kept from test_live_shapes.py)."""

    def test_startup_lines(self):
        text = LC.read_text("runner.log")
        self.assertIn("homing-pigeon 3.12.51 starting", text)
        self.assertIn("auth=oauth mailbox=runner@example.test", text)
        self.assertIn("judge=advisory ceiling=attested", text)
        self.assertIn("judge=off ceiling=full", text)
        self.assertIn("[WARN] confinement is off; workspace_root is not set",
                      text)
        self.assertIn("oracle: deterministic mode (Pi Light)", text)

    def test_event_shapes(self):
        events = LC.jsonl("security-events.jsonl")
        pressure = next(e for e in events if e["type"] == "resource_pressure")
        rejection = next(e for e in events if e["type"] == "auth_rejection")
        self.assertEqual(set(pressure), {"type", "at", "threshold", "resources"})
        self.assertEqual(set(rejection), {"type", "at", "reason"})

    def test_ledger_shapes(self):
        ledger = LC.jsonl("oracle-learning.jsonl")
        prediction = next(x for x in ledger if x["type"] == "prediction")
        recon = next(x for x in ledger if x["type"] == "reconciliation")
        self.assertEqual(
            set(prediction),
            {"type", "at", "job_id", "received_digest", "host", "mode",
             "verdict", "findings", "features", "repair"})
        self.assertEqual(
            set(recon),
            {"type", "at", "job_id", "host", "classification",
             "predicted_verdict", "outcome", "lesson_selected"})

    def test_envelopes_are_hp_enc_with_a_gcm_nonce(self):
        import base64
        for name in sorted(os.listdir(os.path.join(LIVE, "envelopes"))):
            text = LC.read_text("envelopes/" + name)
            with self.subTest(envelope=name):
                self.assertRegex(text, r"^\[HOMING-PIGEON\] (job|result) "
                                       r"[0-9a-f-]{36}\n")
                enc = json.loads(text.split("\n\n", 1)[1])["hp_enc"]
                self.assertEqual(enc["alg"], "aes-256-gcm/hkdf-sha384")
                self.assertEqual(len(base64.b64decode(enc["nonce"])), 12)
                self.assertTrue(base64.b64decode(enc["ct"]))

    def test_posture_and_audit(self):
        posture = LC.read_text("posture.txt")
        self.assertIn("[OK  ] secrets        shared_secret: strong", posture)
        self.assertIn("[WARN] confinement    bwrap not installed", posture)
        audit = LC.read_text("audit-report.txt")
        self.assertIn("no audit entries in this window", audit)


if __name__ == "__main__":
    unittest.main()
