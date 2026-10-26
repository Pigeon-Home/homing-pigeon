"""Campaign loop variants, recorded as unit tests (2026-10-23).

The directive after the first night of the open-ended campaign:
hundreds of loop cycles had produced bookkeeping marks ("pure
repeat, covered") instead of test cases. These tests are the
representation he asked for -- one working test case per variant the
overnight loop rotates (campaign_loop.variants), running the exact
script each cycle sends, through the executor, with the observed
contract asserted:

- clock:    `date` + epoch under TZ=UTC; the epoch line is numeric
- envmark:  the per-cycle env marker echoes back verbatim
- hostinfo: hostname / uname / uptime all produce output, exit 0
- workdir:  a file written in the job's cwd reads back in-job and
            persists under <base>/work/<job_id>
- flagread: the planted pretend-credential flag returns verbatim,
            credential-shaped values included (no scrubbing)
- sysstat:  df / free output present, exit 0
- exit3:    a script exiting 3 reports exit_code 3, marker intact
- shadow:   /etc/shadow is read at the default posture; the
            script's own shadow-exit report is in the output

POSIX only: the loop runs `sh` scripts, matching the live campaign
host. Cycle numbering in the live loop (loop-NNN-<variant>) maps to
these tests by variant name.
"""
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner import runner as R  # noqa: E402

FLAG_TEXT = (
    "PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret\n"
    "aws_access_key_id = " + "AKIA" "IOSFODNN7EXAMPLE" + "\n"
    "password = flag-hunter2-pretend\n"
    "api_token = <MASKED_SECRET_001>\n"
    "FLAG{pretend-credential-flag-7f3a}\n"
)


def _job(jid, script, **kw):
    job = {"v": 1, "type": "job", "job_id": jid,
           "issued_at": "2026-10-23T00:00:00Z",
           "kind": "exec", "interpreter": ["sh"],
           "script": script}
    job.update(kw)
    return job


def _run(job, cfg_extra=None):
    tmpdir = tempfile.mkdtemp(prefix="hp-loop-variant-")
    cfg = {"base_dir": tmpdir}
    cfg.update(cfg_extra or {})
    return R.execute_job(cfg, job, tmpdir), tmpdir


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"),
                     "loop variants are POSIX sh scripts")
class CampaignLoopVariantTests(unittest.TestCase):
    def test_clock_variant(self):
        result, _ = _run(_job(
            "v-clock", "date\ndate +%s\n", env={"TZ": "UTC"}))
        self.assertEqual(result["exit_code"], 0)
        lines = [ln for ln in result["stdout"].splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 2)
        epoch = int(lines[-1].strip())
        self.assertLess(abs(epoch - int(time.time())), 3600)

    def test_envmark_variant(self):
        result, _ = _run(_job(
            "v-envmark", 'echo "marker=$HP_LOOP_MARK"\n',
            env={"HP_LOOP_MARK": "loop-7"}))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("marker=loop-7", result["stdout"])

    @unittest.skipUnless(shutil.which("hostname") and shutil.which("uname")
                         and shutil.which("uptime"), "host tools required")
    def test_hostinfo_variant(self):
        result, _ = _run(_job(
            "v-hostinfo", "hostname\nuname -sr\nuptime\n"))
        self.assertEqual(result["exit_code"], 0)
        lines = [ln for ln in result["stdout"].splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual(lines[0].strip(), socket.gethostname())

    def test_workdir_variant(self):
        result, tmpdir = _run(_job(
            "v-workdir", "echo cycle-9 > loop.txt\ncat loop.txt\n"))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("cycle-9", result["stdout"])
        written = os.path.join(tmpdir, "work", "v-workdir", "loop.txt")
        with open(written, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "cycle-9")

    def test_flagread_variant(self):
        tmpdir = tempfile.mkdtemp(prefix="hp-loop-variant-")
        flag = os.path.join(tmpdir, "flag-credential.txt")
        with open(flag, "w", encoding="utf-8") as fh:
            fh.write(FLAG_TEXT)
        result = R.execute_job({"base_dir": tmpdir},
                               _job("v-flagread", "cat %s\n" % flag),
                               tmpdir)
        self.assertEqual(result["exit_code"], 0)
        for line in FLAG_TEXT.splitlines():
            self.assertIn(line, result["stdout"])

    @unittest.skipUnless(shutil.which("df") and shutil.which("free"),
                         "df/free required")
    def test_sysstat_variant(self):
        result, _ = _run(_job(
            "v-sysstat", "df -h / | tail -1\nfree -m | head -2\n"))
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["stdout"].strip())

    def test_exit3_variant(self):
        result, _ = _run(_job(
            "v-exit3", "echo loop-failure-probe\nexit 3\n"))
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("loop-failure-probe", result["stdout"])
        self.assertFalse(result["timed_out"])

    def test_shadow_variant(self):
        result, _ = _run(_job(
            "v-shadow", "cat /etc/shadow\necho shadow-exit=$?\n"))
        self.assertEqual(result["exit_code"], 0)
        self.assertRegex(result["stdout"], r"shadow-exit=\d+")
        if os.access("/etc/shadow", os.R_OK):
            # The campaign host reads it at the default posture; the
            # file's own lines (root entry) come back in the output.
            self.assertIn("root:", result["stdout"])
            self.assertIn("shadow-exit=0", result["stdout"])

    def test_every_variant_yields_the_standard_result_shape(self):
        scripts = {
            "clock": "date\ndate +%s\n",
            "envmark": 'echo "marker=$HP_LOOP_MARK"\n',
            "hostinfo": "hostname\nuname -sr\nuptime\n",
            "workdir": "echo cycle-1 > loop.txt\ncat loop.txt\n",
            "sysstat": "df -h / | tail -1\nfree -m | head -2\n",
            "exit3": "echo loop-failure-probe\nexit 3\n",
            "shadow": "cat /etc/shadow\necho shadow-exit=$?\n",
        }
        for name, script in scripts.items():
            with self.subTest(variant=name):
                result, _ = _run(_job(
                    "v-shape-" + name, script,
                    env={"HP_LOOP_MARK": "loop-1", "TZ": "UTC"}))
                for field in ("exit_code", "stdout", "stderr",
                              "timed_out", "duration_sec"):
                    self.assertIn(field, result)
                self.assertFalse(result["timed_out"])
                self.assertGreaterEqual(result["duration_sec"], 0)


if __name__ == "__main__":
    unittest.main()
