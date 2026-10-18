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
            self.assertTrue(
                any("credential" in reason for _p, reason in got),
                script)

    def test_windows_home_file_is_flagged(self):
        got = findings("type C:\\Users\\DRU\\Desktop\\flag.txt")
        self.assertEqual(len(got), 1)
        self.assertIn("home", got[0][1])

    def test_etc_config_is_flagged(self):
        got = findings("cat /etc/nginx/nginx.conf")
        self.assertEqual(len(got), 1)
        self.assertIn("system configuration", got[0][1])

    def test_outside_workspace_paths_are_flagged(self):
        for script in (
            "cat /tmp/staging/loot.txt",
            "cat /var/log/auth.log",
            "cp /srv/share/report.csv .",
            "cat /home/u",  # the home dir itself, not a file in it
        ):
            got = findings(script)
            self.assertTrue(got, script)
            self.assertIn("outside the job's own workspace",
                          got[0][1], script)

    def test_benign_scripts_are_silent(self):
        for script in (
            "uname -a; id; df -h / | tail -1",
            "echo quarterly-report-draft > notes.txt && ls -la "
            "&& cat notes.txt",
            "/usr/bin/python3 -c 'print(1)'",
            "ls /usr/share/doc && cat /proc/cpuinfo",
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


# One row: script, the reason fragment that must appear, or None
# when the script must stay silent. Paths are absolute on purpose
# so a mutation of a prefix is visible as a wrong reason.
_REASON_CASES = [
    ("cat /etc/shadow", "credential"),
    ("cat /etc/gshadow", "credential"),
    ("cat /etc/passwd", "credential"),
    ("cat /etc/master.passwd", "credential"),
    ("cp ~/.ssh/id_rsa .", "credential"),
    ("cat /home/u/.aws/credentials", "credential"),
    ("ls /home/u/.gnupg/pubring.kbx", "credential"),
    ("cat /home/u/.azure/token", "credential"),
    ("cat /home/u/.kube/config", "credential"),
    ("cat /srv/keys/id_ed25519", "credential"),
    ("cat /srv/keys/id_ecdsa", "credential"),
    ("cat /srv/keys/id_dsa", "credential"),
    ("cat /srv/keys/site.pem", "credential"),
    ("cat /srv/keys/site.key", "credential"),
    ("cat /home/u/.env", "credential"),
    ("cat /home/u/keychain", "credential"),
    ("cat /home/u/Library/Keychains/login.keychain", "credential"),
    ("cat /home/u/NTUSER.DAT", "credential"),
    ("cat /root/.bashrc", "credential"),
    ("cat /home/u/Desktop/flag.txt", "home"),
    ("cat /Users/dru/Desktop/flag.txt", "home"),
    ("cat ~/Desktop/flag.txt", "home"),
    ("type C:\\Users\\DRU\\Desktop\\flag.txt", "home"),
    ("type C:/Users/DRU/Desktop/flag.txt", "home"),
    ("cat /etc/nginx/nginx.conf", "system configuration"),
    ("cat /tmp/staging/loot.txt", "outside the job's own workspace"),
    ("cat /var/log/auth.log", "outside the job's own workspace"),
    ("cat /opt/app/secret.txt", "outside the job's own workspace"),
    ("cat /srv/share/report.csv", "outside the job's own workspace"),
    ("cat /home/u", "outside the job's own workspace"),
    ("uname -a", None),
    ("echo hi > notes.txt", None),
    ("/usr/bin/python3 -c 'print(1)'", None),
    ("ls /usr/share/doc && cat /proc/cpuinfo", None),
    ("ls /bin/ls /sbin/init /lib/x /lib64/x /sys/x /dev/null", None),
    ("C:\\Windows\\System32\\cmd.exe", None),
    ("", None),
    ("   \t  ", None),
]


class ReasonMatrixTest(unittest.TestCase):
    def test_each_path_lands_on_its_reason(self):
        for script, fragment in _REASON_CASES:
            got = findings(script)
            if fragment is None:
                self.assertEqual(got, [], script)
            else:
                self.assertTrue(got, script)
                self.assertIn(fragment, got[0][1], script)

    def test_sensitive_marker_wins_inside_an_ordinary_prefix(self):
        got = findings("cat /usr/local/share/site.pem")
        self.assertEqual(len(got), 1)
        self.assertIn("credential", got[0][1])

    def test_quoted_and_trailing_punctuation_still_match(self):
        for script in (
            "cat '/etc/shadow'",
            'cat "/etc/shadow"',
            "cat /etc/shadow;",
            "cat /etc/shadow,",
            "cat /etc/shadow:",
        ):
            got = findings(script)
            self.assertEqual(got[0][0], "/etc/shadow", script)

    def test_flag_form_of_a_home_path(self):
        got = findings("tool --input=/home/u/Desktop/flag.txt --fast")
        self.assertEqual(len(got), 1)
        self.assertIn("home", got[0][1])

    def test_relative_and_short_tokens_are_silent(self):
        for script in ("cat notes.txt", "cat /", "cat C:", "echo a=b"):
            self.assertEqual(findings(script), [], script)

    def test_non_strings_are_silent(self):
        for script in (None, 0, ["cat", "/etc/shadow"], b"cat /etc/shadow"):
            self.assertEqual(
                R._script_path_findings(script, BASE, "jobx"), [])

    def test_no_job_id_still_flags_and_still_skips_the_state_dir(self):
        self.assertTrue(
            R._script_path_findings("cat /etc/shadow", BASE, None))
        self.assertEqual(
            R._script_path_findings(
                f"cat {BASE}/config.json", BASE, None), [])

    def test_no_base_dir_still_flags(self):
        got = R._script_path_findings("cat /etc/shadow", None, None)
        self.assertEqual(len(got), 1)
        self.assertIn("credential", got[0][1])

    def test_exact_workspace_directory_is_silent(self):
        work = os.path.join(BASE, "work", "jobx")
        self.assertEqual(findings(f"cd {work}"), [])

    def test_mixed_reasons_keep_script_order_and_the_cap(self):
        script = (
            "cat /tmp/a /etc/shadow /home/u/Desktop/flag.txt "
            "/etc/nginx/nginx.conf /opt/b"
        )
        got = findings(script)
        self.assertEqual(
            [path for path, _reason in got],
            ["/tmp/a", "/etc/shadow", "/home/u/Desktop/flag.txt"])


class AnalyzerFuzzTest(unittest.TestCase):
    """Seeded mutations of the tokenizer. Invariants, not snapshots."""

    def test_seeded_scripts_obey_the_invariants(self):
        import random
        rng = random.Random(321)
        work = os.path.join(BASE, "work", "jobx")
        atoms = [
            "uname", "-a", "cat", "echo", "notes.txt", ">", "|", ";",
            "'", '"', "&&", "/usr/bin/python3", "/bin/ls",
            "/etc/shadow", "/etc/nginx/nginx.conf", "/tmp/loot",
            "/var/log/auth.log", "/opt/app/x", "/home/u/Desktop/flag.txt",
            "/Users/dru/x", "~/.ssh/id_rsa", "/root/.ssh/id_rsa",
            "C:\\Users\\DRU\\a.txt", "C:\\Windows\\System32\\cmd.exe",
            "C:\\Program Files\\Git\\bin\\bash.exe",
            "--in=/etc/passwd", f"{work}/input.txt",
            f"{BASE}/config.json", "/proc/cpuinfo", "",
        ]
        reasons = {
            "a credential store or key material",
            "a file under a user home directory, outside "
            "the job's own workspace",
            "a system configuration file, outside the "
            "job's own workspace",
            "a file outside the job's own workspace",
        }
        ordinary = R._ORDINARY_PREFIXES
        for i in range(400):
            script = " ".join(rng.choice(atoms)
                              for _ in range(rng.randint(0, 14)))
            got = findings(script)
            self.assertLessEqual(len(got), 3, script)
            self.assertEqual(len(got), len({p for p, _r in got}), script)
            for path, reason in got:
                self.assertIn(reason, reasons, script)
                self.assertIn(path, script, script)
                self.assertFalse(
                    path.startswith(work), script)
                self.assertFalse(
                    path.startswith(BASE + os.sep)
                    or path == BASE, script)
                low = path.replace("\\", "/").lower()
                norm = path.replace("\\", "/")
                marked = any(m in low for m in R._SENSITIVE_MARKERS)
                if norm.startswith(ordinary) and not marked:
                    self.fail(f"ordinary path flagged: {path} in {script}")


class SummaryBranchTest(unittest.TestCase):
    def test_blank_script_has_no_script_line(self):
        s = R._retained_job_summary(_record("   \n"), "jobx", BASE)
        self.assertNotIn("script:", s)
        self.assertNotIn("notable:", s)

    def test_missing_or_non_string_script(self):
        for record in ({"stdout": "ok"}, {"script": None, "stdout": "ok"},
                       {"script": 3, "stdout": "ok"}):
            s = R._retained_job_summary(record, "jobx", BASE)
            self.assertNotIn("notable:", s)
            self.assertIn("kind not recorded", s)

    def test_long_output_is_cut(self):
        s = R._retained_job_summary(
            _record("true", stdout="x" * 900), "jobx", BASE)
        self.assertIn("\n...", s)
        self.assertLess(len(s.split("output:\n", 1)[1]), 900)

    def test_empty_output(self):
        s = R._retained_job_summary(
            _record("true", stdout=""), "jobx", BASE)
        self.assertIn("output: (empty)", s)

    def test_artifact_scan_is_included_and_capped(self):
        record = _record("true")
        record["artifact_scan"] = [f"hit-{i}" for i in range(25)]
        s = R._retained_job_summary(record, "jobx", BASE)
        self.assertIn("artifact scan:", s)
        self.assertIn("hit-0", s)
        self.assertNotIn("hit-20", s)

    def test_non_list_scan_is_ignored(self):
        record = _record("true")
        record["artifact_scan"] = "hit"
        s = R._retained_job_summary(record, "jobx", BASE)
        self.assertNotIn("artifact scan:", s)


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
