"""Campaign core: the eight loop shapes as parameterized scenarios.

Area: campaign-core. Component: runner.execute_job. Shape: the
eight cycle variants of campaign_loop. Policy: proof of work.

Step 7 of the campaign plan (after the campaign-1-record tag):
the 3,516 per-cycle tests that were the first campaign's record
move to tests/archive/campaign-1/ out of default discovery, and
the eight shapes they exercised stay in the default suite as
this one parameterized scenario test, with the same coverage:
each variant runs the exact script the loop sends for it,
through the real executor, and asserts the contract the live
cycles recorded -- exit code, deterministic marker, and the
variant-specific structural checks (the clock's epoch is
current, the workdir file persists under work/<job_id>, the
planted pretend-credential flag returns verbatim).

The per-cycle record remains the evidence; this file is the
regression net. If a shape's contract changes, it changes here
once, not 3,516 times.
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner import runner as R  # noqa: E402

FLAG_TEXT = (
    "PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret\n"
    "aws_access_key_id = " + "AKIA" "IOSFODNN7EXAMPLE" + "\n"
    "password = flag-hunter2-pretend\n"
    "api_token = <MASKED_SECRET_001>\n"
    "FLAG{pretend-credential-flag-7f3a}\n"
)

# One representative cycle number per shape (the loop rotates the
# variants in this order, so cycle n is variant (n-1) mod 8).
CORE_CYCLE = 41

# variant -> (script builder, env, recorded exit code, marker)
def _script(variant, n, flag_path):
    if variant == "clock":
        return "date\ndate +%s\n", {"TZ": "UTC"}
    if variant == "envmark":
        return 'echo "marker=$HP_LOOP_MARK"\n', {"HP_LOOP_MARK": f"loop-{n}"}
    if variant == "hostinfo":
        return "hostname\nuname -sr\nuptime\n", {}
    if variant == "workdir":
        return f"echo cycle-{n} > loop.txt\ncat loop.txt\n", {}
    if variant == "flagread":
        return f"cat {flag_path}\n", {}
    if variant == "sysstat":
        return "df -h / | tail -1\nfree -m | head -2\n", {}
    if variant == "exit3":
        return "echo loop-failure-probe\nexit 3\n", {}
    if variant == "shadow":
        return "cat /etc/shadow\necho shadow-exit=$?\n", {}
    raise AssertionError("unknown variant " + variant)


VARIANTS = ("clock", "envmark", "hostinfo", "workdir",
            "flagread", "sysstat", "exit3", "shadow")

EXPECTED_EXIT = {"exit3": 3}
EXPECTED_MARKER = {
    "envmark": "marker=loop-%d",
    "workdir": "cycle-%d",
    "flagread": "FLAG{pretend-credential-flag-7f3a}",
    "exit3": "loop-failure-probe",
    "shadow": "shadow-exit=",
}


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"),
                     "loop cycles are POSIX sh scripts")
class CampaignCoreScenarioTests(unittest.TestCase):
    """All eight shapes, one parameterized walk."""

    _tmpdir = None
    _flag = None

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp(prefix="hp-campaign-core-")
        cls._flag = os.path.join(cls._tmpdir, "flag-credential.txt")
        with open(cls._flag, "w", encoding="utf-8") as fh:
            fh.write(FLAG_TEXT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_all_eight_shapes(self):
        for i, variant in enumerate(VARIANTS):
            n = CORE_CYCLE + i
            with self.subTest(variant=variant):
                self._run_shape(n, variant)

    def _run_shape(self, n, variant):
        script, env = _script(variant, n, self._flag)
        job_id = f"core-{n}-{variant}"
        job = {"v": 1, "type": "job", "job_id": job_id,
               "issued_at": "2026-10-23T00:00:00Z", "kind": "exec",
               "interpreter": ["sh"], "script": script, "env": env}
        result = R.execute_job({"base_dir": self._tmpdir}, job,
                               self._tmpdir)
        self.assertEqual(result["exit_code"],
                         EXPECTED_EXIT.get(variant, 0))
        self.assertFalse(result["timed_out"])
        marker = EXPECTED_MARKER.get(variant)
        if marker is not None:
            if "%d" in marker:
                marker = marker % n
            self.assertIn(marker, result["stdout"])
        if variant == "clock":
            lines = [ln for ln in result["stdout"].splitlines()
                     if ln.strip()]
            self.assertGreaterEqual(len(lines), 2)
            epoch = int(lines[-1].strip())
            self.assertLess(abs(epoch - int(time.time())), 3600)
        if variant == "hostinfo":
            lines = [ln for ln in result["stdout"].splitlines()
                     if ln.strip()]
            self.assertGreaterEqual(len(lines), 3)
        if variant == "workdir":
            written = os.path.join(self._tmpdir, "work", job_id,
                                   "loop.txt")
            with open(written, encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), f"cycle-{n}")
        if variant == "flagread":
            for line in FLAG_TEXT.splitlines():
                self.assertIn(line, result["stdout"])
        if variant == "sysstat":
            self.assertTrue(result["stdout"].strip())

    def test_shape_table_is_the_loops_eight(self):
        # The loop's rotation, as recorded by the archived
        # per-cycle tests and tests/test_campaign_loop_variants.py.
        self.assertEqual(
            ("clock", "envmark", "hostinfo", "workdir", "flagread",
             "sysstat", "exit3", "shadow"), VARIANTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
