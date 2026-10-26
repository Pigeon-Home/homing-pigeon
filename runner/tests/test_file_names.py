"""files[].name: one rule set, refused the same way on every platform.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

runner/guard/filenames.py numbers its rules; the table below pins
each vector to the rule its rejection names, on every CI platform
(nothing here branches on os.name). The end-to-end legs drive a job
through the mail core: a bad name is a -2 rejection result, marked
seen, never retried, and never costs a download.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))

from runner import runner as R  # noqa: E402
from runner.guard import filenames as F  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402

REJECTED = [
    # vector, rule
    ("C:\\Windows\\x", 2),
    ("c:/x", 3),
    ("C:x", 3),
    ("\\\\server\\share\\x", 2),
    ("//server/share/x", 3),
    ("/etc/passwd", 3),
    ("../x", 4),
    ("a/../../x", 4),
    ("a/./b", 4),
    ("./x", 4),
    ("a//b", 4),
    ("a/", 4),
    ("", 1),
    ("a\\b", 2),
    ("-rf", 5),
    ("a/-x", 5),
    ("...", 5),
    ("a/...", 5),
    ("CON", 6),
    ("nul.txt", 6),
    ("a/COM1", 6),
    ("x\x00y", 1),
    ("a" * 256, 1),
    (("a/" * 600) + "b", 1),
    # beyond the runbook's table
    ("a b", 5),
    ("caf\u00e9", 5),
    ("LPT9.log", 6),
    ("a/con/b", 6),
    ("con.sole", 6),               # any extension still opens the device
    (None, 1),
    (7, 1),
]

ACCEPTED = [
    ("report.txt", "report.txt"),
    ("data/in.csv", "data/in.csv"),
    ("a.b-c_d/e.f", "a.b-c_d/e.f"),
    ("A/B/C", "A/B/C"),
    ("a" * 255, "a" * 255),
    ("console/x", "console/x"),     # a device name is the whole stem
    ("x.CON", "x.CON"),
    ("comet", "comet"),
]


class RuleTableTest(unittest.TestCase):
    def test_rejected_vectors_name_their_rule(self):
        for vector, rule in REJECTED:
            with self.subTest(vector=vector):
                with self.assertRaises(F.BadFileName) as cm:
                    F.validate_file_name(vector)
                self.assertEqual(cm.exception.rule, rule, str(cm.exception))
                self.assertIn("(rule %d)" % rule, str(cm.exception))
                # The runner's gate carries the same message as a
                # rejection, so the result tells the author which rule.
                with self.assertRaises(R.JobRejected) as cm2:
                    R.validate_file_name(vector)
                self.assertIn("(rule %d)" % rule, str(cm2.exception))

    def test_accepted_vectors_normalize_to_themselves(self):
        for vector, want in ACCEPTED:
            with self.subTest(vector=vector):
                self.assertEqual(F.validate_file_name(vector), want)
                self.assertEqual(R.validate_file_name(vector), want)

    def test_every_rule_number_has_a_vector_and_a_text(self):
        self.assertEqual(sorted({rule for _v, rule in REJECTED}),
                         sorted(F.RULES))

    def test_script_filename_values_pass(self):
        for interp in (["sh"], ["bash", "-e"], ["python3"],
                       ["powershell", "-File"], ["pwsh"], [7], "odd"):
            self.assertEqual(
                F.validate_file_name(R.script_filename(interp)),
                R.script_filename(interp))

    def test_the_reserved_name_check_keeps_its_old_answers(self):
        self.assertTrue(R.windows_reserved_name("CON"))
        self.assertTrue(R.windows_reserved_name("a/nul.txt"))
        self.assertTrue(R.windows_reserved_name("trailing."))
        self.assertFalse(R.windows_reserved_name("console"))
        self.assertFalse(R.windows_reserved_name(None))
        self.assertIs(R._WIN_DEVICES, F._WIN_DEVICES)


class StagedDestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-names-")
        self.work = os.path.join(self.tmp, "work", "j1")
        os.makedirs(self.work)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_nested_name_gets_its_parents_made(self):
        dest = R._staged_dest(self.work, "data/raw/in.csv")
        self.assertTrue(os.path.isdir(os.path.join(self.work, "data", "raw")))
        self.assertEqual(dest, os.path.realpath(
            os.path.join(self.work, "data", "raw", "in.csv")))
        self.assertFalse(os.path.exists(dest))   # nothing downloaded

    def test_a_flat_name_creates_nothing(self):
        R._staged_dest(self.work, "in.csv")
        self.assertEqual(os.listdir(self.work), [])

    def test_the_realpath_gate_still_runs(self):
        for name in ("../x", "/etc/x", "a/../../x"):
            with self.assertRaises(R.JobRejected):
                R._staged_dest(self.work, name)
        self.assertEqual(os.listdir(self.work), [])

    def test_a_symlinked_parent_is_refused_before_anything_is_made(self):
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        try:
            os.symlink(elsewhere, os.path.join(self.work, "data"))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable")
        # Pointing outside: the real-path gate refuses it.
        with self.assertRaises(R.JobRejected):
            R._staged_dest(self.work, "data/in.csv")
        self.assertEqual(os.listdir(elsewhere), [])
        # Pointing inside the work tree: the real path is inside, so
        # the component walk is what names the planted link.
        inside = os.path.join(self.work, "inside")
        os.makedirs(inside)
        os.symlink(inside, os.path.join(self.work, "ok"))
        with self.assertRaises(R.JobRejected) as cm:
            R._staged_dest(self.work, "ok/deep/in.csv")
        self.assertIn("symlink", str(cm.exception))
        self.assertEqual(os.listdir(inside), [])

    def test_the_root_may_be_handed_in(self):
        root = os.path.realpath(self.work)
        self.assertEqual(R._staged_dest(self.work, "a.txt", root=root),
                         os.path.join(root, "a.txt"))


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.tmp = self.h.tmp
        self.seen_path = self.h.seen_path

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cycle(self, mails, seen=None):
        imap, smtp = TR.FakeIMAP(mails), TR.FakeSMTP()
        seen = {} if seen is None else seen
        R.poll_once(self.cfg, self.tmp, seen, self.seen_path,
                    imap=imap, smtp=smtp)
        return imap, smtp, seen

    def _job(self, jid, files):
        return TR.job_payload(jid, kind="exec", script="echo ran",
                              interpreter=["sh"], files=files)

    def test_rejection_is_poison_not_transient(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(self._job(
            jid, [{"name": "C:\\Windows\\x", "url": "https://example.com/x"}]))
        seen = {}
        imap, smtp, seen = self._cycle([mail], seen)
        self.assertEqual(len(smtp.sent), 1)
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("unsafe file name", result["stderr"])
        self.assertIn("(rule 2)", result["stderr"])
        self.assertEqual([str(x) for x in imap.flagged], ["1"])
        self.assertTrue(any(jid in k for k in seen))
        # The same mail again: a replay, not a second attempt.
        imap, smtp, seen = self._cycle([mail], seen)
        self.assertEqual(smtp.sent, [])

    def test_no_download_before_name_check(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(self._job(jid, [
            {"name": "good.txt", "url": "https://example.com/good"},
            {"name": "nul.txt", "url": "https://example.com/bad"},
        ]))

        def never(*_a, **_k):
            self.fail("download called before the names were checked")

        with mock.patch.object(R, "download", never):
            _imap, smtp, _seen = self._cycle([mail])
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("(rule 6)", result["stderr"])
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp, "work", jid, "good.txt")))

    def test_the_device_name_is_refused_on_this_platform_too(self):
        # The old check ran only when os.name == "nt"; this leg runs on
        # every CI platform and expects the same refusal.
        jid = str(uuid.uuid4())
        mail = TR.job_email(self._job(
            jid, [{"name": "COM1", "url": "https://example.com/x"}]))
        _imap, smtp, _seen = self._cycle([mail])
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("(rule 6)", result["stderr"])

    def test_a_nested_name_stages_into_a_made_directory(self):
        jid = str(uuid.uuid4())
        job = TR.job_payload(jid, kind="exec",
                             script="cat data/in.csv",
                             interpreter=["sh"],
                             files=[{"name": "data/in.csv",
                                     "url": "https://example.com/in.csv"}])

        def fake_download(url, dest, max_bytes=0):
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("a,b\n1,2\n")

        with mock.patch.object(R, "download", fake_download):
            _imap, smtp, _seen = self._cycle([TR.job_email(job)])
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("1,2", result["stdout"])


class SenderTest(unittest.TestCase):
    """runner/cloud/send_job.py applies the same rules at composition time."""

    def _run(self, name):
        import send_job
        argv = ["send_job.py", "new", "--kind", "exec",
                "--script-file", __file__,
                "--file", name + "=https://example.com/x",
                "--secret", "ab" * 32, "--to-file",
                os.path.join(tempfile.mkdtemp(prefix="hp-send-"), "out")]
        err = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sys, "stderr", err), \
                mock.patch.object(sys, "stdout", io.StringIO()):
            rc = send_job.main()
        return rc, err.getvalue()

    def test_a_bad_name_is_refused_before_signing(self):
        rc, err = self._run("../x")
        self.assertEqual(rc, 2)
        self.assertIn("(rule 4)", err)
        rc, err = self._run("nul.txt")
        self.assertEqual(rc, 2)
        self.assertIn("(rule 6)", err)

    def test_the_sender_and_the_runner_share_one_rule_set(self):
        import send_job
        self.assertEqual(send_job._filenames.RULES, F.RULES)
        for vector, rule in REJECTED:
            with self.assertRaises(ValueError) as cm:
                send_job._filenames.validate_file_name(vector)
            self.assertIn("(rule %d)" % rule, str(cm.exception))

    def test_the_sender_runs_by_path_with_the_rules(self):
        # python runner/cloud/send_job.py, no package on the path.
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "runner", "cloud",
                                          "send_job.py"),
             "new", "--kind", "exec", "--script-file", __file__,
             "--file", "CON=https://example.com/x", "--secret", "ab" * 32,
             "--to-file", os.path.join(tempfile.mkdtemp(), "out")],
            cwd=tempfile.gettempdir(), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True, timeout=120)
        self.assertEqual(r.returncode, 2, r.stdout[-1500:])
        self.assertIn("(rule 6)", r.stdout)


if __name__ == "__main__":
    unittest.main()
