"""The notable-access line: mechanical sensitive-access findings.

The Flag321 field tests (2026-10-17) showed the Oracle's small
local models do not reason "this job read a credential file" out
of a raw script, even when asked pointedly. _script_path_findings
computes that fact deterministically and _retained_job_summary
carries it as a "notable:" line; both ask prompts tell the model
to treat the line as a finding. These tests pin the analyzer's
precision (benign scripts stay silent) and recall (the Flag321
script and classic credential stores are flagged).
"""

import os
import tempfile
import unittest

from runner import runner as R

BASE = os.path.join(tempfile.gettempdir(), "hp-state")
FLAG = "cat /home/hatch/workspace/hp-vmtest/Desktop/flag.txt"


def findings(script, job_id="jobx"):
    return R._script_path_findings(script, BASE, job_id)


class ScriptPathFindingsTest(unittest.TestCase):
    def test_flag321_script_is_flagged_as_a_home_file(self):
        got = findings(FLAG)
        self.assertEqual(len(got), 1)
        path, reason = got[0]
        self.assertTrue(path.endswith("Desktop/flag.txt"))
        self.assertIn("home", reason)

    def test_credential_stores_are_flagged(self):
        for script in (
            "cat /etc/shadow",
            "cat /etc/passwd",
            "cp ~/.ssh/id_rsa /tmp/x",
            "tar czf /tmp/a.tgz /home/u/.aws/credentials",
            "cat 'C:\\Users\\DRU\\.ssh\\id_rsa'",
            "openssl rsa -in /srv/keys/site.key",
            "cat /home/u/.env",
        ):
            got = findings(script)
            self.assertTrue(got, script)
            self.assertIn("credential", got[0][1], script)

    def test_windows_home_file_is_flagged(self):
        got = findings("type C:\\Users\\DRU\\Desktop\\flag.txt")
        self.assertEqual(len(got), 1)
        self.assertIn("home", got[0][1])

    def test_etc_config_is_flagged(self):
        got = findings("cat /etc/nginx/nginx.conf")
        self.assertEqual(len(got), 1)
        self.assertIn("system configuration", got[0][1])

    def test_benign_scripts_are_silent(self):
        for script in (
            "uname -a; id; df -h / | tail -1",
            "echo quarterly-report-draft > notes.txt && ls -la "
            "&& cat notes.txt",
            "/usr/bin/python3 -c 'print(1)'",
            "ls /usr/share/doc && cat /proc/cpuinfo",
            "grep -r foo /tmp/scratch",
            "",
        ):
            self.assertEqual(findings(script), [], script)

    def test_own_workspace_and_state_dir_are_silent(self):
        work = os.path.join(BASE, "work", "jobx")
        self.assertEqual(findings(f"cat {work}/input.txt"), [])
        self.assertEqual(findings(f"cat {BASE}/config.json"), [])

    def test_findings_are_capped_and_deduped(self):
        script = " ".join(
            f"cat /home/u/f{i}.txt" for i in range(5))
        self.assertEqual(len(findings(script)), 3)
        self.assertEqual(
            len(findings("cat /etc/shadow; cat /etc/shadow")), 1)

    def test_flag_value_form_is_found(self):
        got = findings("run --input=/etc/shadow --fast")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][0], "/etc/shadow")


def _record(script, stdout="ok\n"):
    return {"kind": "exec", "script": script, "stdout": stdout,
            "stderr": "", "exit_code": 0, "saved_at": 1000.0,
            "view": "attested", "artifact_scan": []}


class NotableLineTest(unittest.TestCase):
    def test_flag_job_summary_carries_the_line(self):
        s = R._retained_job_summary(_record(FLAG), "jobx", BASE)
        self.assertIn("notable:", s)
        self.assertIn("Desktop/flag.txt", s)

    def test_benign_summary_has_no_line(self):
        s = R._retained_job_summary(
            _record("uname -a; id"), "jobx", BASE)
        self.assertNotIn("notable:", s)

    def test_context_carries_the_line(self):
        d = tempfile.mkdtemp()
        R.save_retained(d, "jobflag1", _record(FLAG))
        R.save_retained(d, "jobok001", _record("uname -a"))
        ctx = R.oracle_context(d, watch=False)
        self.assertIn("notable:", ctx)
        self.assertIn("Desktop/flag.txt", ctx)


class PromptDirectiveTest(unittest.TestCase):
    def test_both_prompts_carry_the_notable_directive(self):
        for prompt in (R.ASK_SYSTEM, R.ASK_AGENT_SYSTEM):
            self.assertIn("'notable:' line", prompt)
            self.assertIn("report every job with a", prompt)
            self.assertIn("never write one for it", prompt)

    def test_summary_line_classifies_the_access(self):
        s = R._retained_job_summary(_record(FLAG), "jobx", BASE)
        self.assertIn("SUSPICIOUS ACCESS", s)
        self.assertIn("malicious-job behavior", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
