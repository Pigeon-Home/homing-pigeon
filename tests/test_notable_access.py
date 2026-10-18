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

import json
import os
import tempfile
import time
import unittest
import unittest.mock

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


class SummaryFactTest(unittest.TestCase):
    def test_timed_out_and_unknown_status(self):
        record = _record("true")
        record["timed_out"] = True
        record["exit_code"] = "nope"
        s = R._retained_job_summary(record, "jobx", BASE)
        self.assertIn("timed out", s)
        record["timed_out"] = False
        s = R._retained_job_summary(record, "jobx", BASE)
        self.assertIn("status unknown", s)

    def test_bad_timestamp_stays_unknown(self):
        record = _record("true")
        record["saved_at"] = "yesterday"
        s = R._retained_job_summary(record, "jobx", BASE)
        self.assertIn("time unknown", s)

    def test_non_string_output_is_stringified(self):
        record = _record("true", stdout=321)
        s = R._retained_job_summary(record, "jobx", BASE)
        self.assertIn("321", s)
        self.assertNotIn("notable:", s)


class ContextGateTest(unittest.TestCase):
    """What reaches the Oracle record, and what is dropped first."""

    def _dir(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "retained"))
        return d

    def _plant(self, d, job_id, script=FLAG):
        R.save_retained(d, job_id, _record(script))
        return d

    def test_non_string_base_is_empty(self):
        self.assertEqual(R.oracle_context(None, watch=False), "")
        self.assertEqual(R.oracle_context(3, watch=False), "")

    def test_junk_names_symlink_and_bad_json_are_skipped(self):
        d = self._plant(self._dir(), "jobflag1")
        retained = os.path.join(d, "retained")
        with open(os.path.join(retained, "notes.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("not a job")
        with open(os.path.join(retained, "bad id.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{}")
        with open(os.path.join(retained, "corrupt1.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{")
        with open(os.path.join(retained, "notdict1.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("[1]")
        os.symlink(os.path.join(retained, "jobflag1.json"),
                   os.path.join(retained, "linkjob1.json"))
        ctx = R.oracle_context(d, watch=False)
        self.assertIn("jobflag1", ctx)
        self.assertIn("notable:", ctx)
        self.assertNotIn("bad id", ctx)
        self.assertNotIn("corrupt1", ctx)
        self.assertNotIn("notdict1", ctx)
        self.assertNotIn("linkjob1", ctx)

    def test_unreadable_mtime_is_skipped(self):
        d = self._plant(self._dir(), "jobflag1")
        real = os.path.getmtime

        def boom(path):
            if path.endswith("jobflag1.json"):
                raise OSError("gone")
            return real(path)

        with unittest.mock.patch("runner.runner.os.path.getmtime", boom):
            ctx = R.oracle_context(d, watch=False)
        self.assertNotIn("jobflag1", ctx)
        self.assertIn("(no job output retained yet)", ctx)

    def test_limit_and_cap_edges(self):
        d = self._dir()
        for i in range(4):
            self._plant(d, f"job{i:04d}", "true" if i else FLAG)
            path = os.path.join(d, "retained", f"job{i:04d}.json")
            os.utime(path, (1000 + i, 1000 + i))
        all_of_them = R.oracle_context(d, limit=None, watch=False)
        for i in range(4):
            self.assertIn(f"job{i:04d}", all_of_them)
        newest = R.oracle_context(d, limit=1, watch=False)
        self.assertIn("job0003", newest)
        self.assertNotIn("job0000", newest)
        self.assertEqual(R.oracle_context(d, limit=-5, watch=False),
                         "(no job output retained yet)")
        self.assertEqual(R.oracle_context(d, max_chars=0, watch=False), "")
        self.assertEqual(R.oracle_context(d, max_chars=-3, watch=False), "")
        # A bool is not a number. Both fall back to the defaults,
        # and the notable line is still in the record.
        ctx = R.oracle_context(d, limit=True, max_chars=True, watch=False)
        self.assertIn("notable:", ctx)
        ctx = R.oracle_context(d, limit="many", max_chars="lots",
                               watch=False)
        self.assertIn("notable:", ctx)

    def test_runner_log_rides_with_the_notable_line(self):
        d = self._plant(self._dir(), "jobflag1")
        with open(os.path.join(d, "runner.log"), "w",
                  encoding="utf-8") as fh:
            fh.write("jobflag1 done\n")
        ctx = R.oracle_context(d, watch=False)
        self.assertIn("notable:", ctx)
        self.assertIn("Recent runner log", ctx)
        self.assertIn("jobflag1 done", ctx)


class MarkerFuzzTest(unittest.TestCase):
    """Case and splitter mutations around one credential path."""

    def test_case_and_splitters_keep_the_marker(self):
        import random
        rng = random.Random(321)
        path = "/etc/shadow"
        splitters = list(" \t\r\n'\"`;|&<>(){}[]")
        for _ in range(200):
            noise = "".join(rng.choice(splitters) for _ in range(3))
            shown = "".join(rng.choice((c, c.upper())) for c in path)
            script = f"cat{noise}{shown}{noise}echo"
            got = findings(script)
            self.assertTrue(got, script)
            self.assertIn("credential", got[0][1], script)
            self.assertLessEqual(len(got), 3)

    def test_uppercase_home_prefix_is_not_the_home_reason(self):
        got = findings("cat /HOME/u/Desktop/flag.txt")
        self.assertEqual(len(got), 1)
        self.assertIn("outside the job's own workspace", got[0][1])
        self.assertNotIn("home", got[0][1])


class BoundaryTest(unittest.TestCase):
    def test_path_past_the_script_cut_still_flags(self):
        script = ("echo " + ("a" * 400) + " && cat /etc/shadow")
        s = R._retained_job_summary(_record(script), "jobx", BASE)
        self.assertIn("notable:", s)
        self.assertIn("/etc/shadow", s)
        shown = s.split("script: ", 1)[1].split("\n", 1)[0]
        self.assertEqual(len(shown), 400)
        self.assertNotIn("/etc/shadow", shown)

    def test_three_findings_are_joined_on_the_line(self):
        script = "cat /tmp/a /etc/shadow /home/u/Desktop/flag.txt"
        s = R._retained_job_summary(_record(script), "jobx", BASE)
        self.assertIn(
            "/tmp/a (a file outside the job's own workspace); "
            "/etc/shadow (a credential store or key material); "
            "/home/u/Desktop/flag.txt (a file under a user home "
            "directory, outside the job's own workspace)", s)

    def test_trailing_slash_on_the_state_dir_still_excludes_it(self):
        self.assertEqual(
            R._script_path_findings(
                f"cat {BASE}/config.json", BASE + "/", "jobx"), [])

    def test_path_buried_in_a_long_script_is_found(self):
        import random
        rng = random.Random(321)
        path = "/etc/shadow"
        for _ in range(120):
            pad = "a" * rng.randint(0, 500)
            script = pad + " " + path + " " + pad
            got = findings(script)
            self.assertEqual(len(got), 1, script[:40])
            self.assertEqual(got[0][0], path)
            self.assertIn("credential", got[0][1])


_WATCH = (
    "_canary_watch", "_host_log_tail", "_firewall_watch", "_av_watch",
    "_eventlog_tail", "_registry_watch",
)


def _watch_context(base, values, platform=None, **kwargs):
    """oracle_context with the collectors replaced by plain values."""
    patches = [
        unittest.mock.patch("runner.runner." + name, return_value=values.get(name, ""))
        for name in _WATCH
    ]
    if platform is not None:
        patches.append(unittest.mock.patch("runner.runner.sys.platform", platform))
    for p in patches:
        p.start()
    try:
        return R.oracle_context(base, watch=True, **kwargs)
    finally:
        for p in patches:
            p.stop()


class WatchRecordTest(unittest.TestCase):
    """The notable line stays put when the watch sections are appended."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "retained"))
        R.save_retained(self.base, "jobflag1", _record(FLAG))

    def test_each_collector_state_keeps_the_notable_line(self):
        states = (None, "", "sense-hit")
        for can in states:
            for host in states:
                for fw in states:
                    for av in states:
                        ctx = _watch_context(self.base, {
                            "_canary_watch": can,
                            "_host_log_tail": host,
                            "_firewall_watch": fw,
                            "_av_watch": av,
                        })
                        self.assertIn("notable:", ctx)
                        self.assertIn("Desktop/flag.txt", ctx)
                        self.assertIn("SUSPICIOUS ACCESS", ctx)
                        if can:
                            self.assertIn("Canary watch", ctx)
                            self.assertIn(can, ctx)
                        else:
                            self.assertNotIn("Canary watch", ctx)
                        if host is None:
                            self.assertIn("Host log tail: unreadable", ctx)
                        elif host:
                            self.assertIn(host, ctx)
                        else:
                            self.assertIn("no matching auth failures", ctx)
                        if fw is None:
                            self.assertIn("Firewall posture: unreadable", ctx)
                        elif fw:
                            self.assertIn("Firewall posture:\n" + fw, ctx)
                        else:
                            self.assertNotIn("Firewall posture", ctx)
                        if av is None:
                            self.assertIn("AV posture: unreadable", ctx)
                        elif av:
                            self.assertIn("AV posture:\n" + av, ctx)
                        else:
                            self.assertNotIn("AV posture", ctx)

    def test_windows_collectors(self):
        for ev in (None, "", "evt-1"):
            for reg in (None, "", "reg-1"):
                ctx = _watch_context(
                    self.base,
                    {"_eventlog_tail": ev, "_registry_watch": reg},
                    platform="win32")
                self.assertIn("notable:", ctx)
                self.assertNotIn("Host log tail", ctx)
                if ev is None:
                    self.assertIn("Event Log: unreadable", ctx)
                elif ev:
                    self.assertIn("evt-1", ctx)
                else:
                    self.assertIn("no Critical, Error", ctx)
                if reg is None:
                    self.assertIn("registry watch: unreadable", ctx)
                elif reg:
                    self.assertIn("reg-1", ctx)
                else:
                    self.assertNotIn("Windows registry watch", ctx)

    def test_a_full_job_budget_skips_the_watch(self):
        called = []

        def _no(*_a, **_k):
            called.append(1)
            return "should-not-appear"

        with unittest.mock.patch("runner.runner._canary_watch", _no), \
                unittest.mock.patch("runner.runner._host_log_tail", _no), \
                unittest.mock.patch("runner.runner._firewall_watch", _no), \
                unittest.mock.patch("runner.runner._av_watch", _no):
            ctx = R.oracle_context(self.base, max_chars=40, watch=True)
        self.assertEqual(called, [])
        self.assertLessEqual(len(ctx), 40)
        self.assertNotIn("should-not-appear", ctx)

    def test_watch_text_is_cut_by_the_final_cap(self):
        ctx = _watch_context(
            self.base, {"_canary_watch": "C" * 2000}, max_chars=500)
        self.assertEqual(len(ctx), 500)
        self.assertTrue(ctx.startswith("Job index"))
        self.assertIn("notable:", ctx)

    def test_denylist_failure_still_carries_the_line(self):
        script = "rm -rf /; cat /etc/shadow"
        verdict, reasons = R.judge_job({"judge": "advisory"}, {"script": script})
        self.assertEqual(verdict, "fail")
        self.assertIn("denylist: rm -rf /", reasons)
        s = R._retained_job_summary(_record(script), "jobx", BASE)
        self.assertIn("notable:", s)
        self.assertIn("/etc/shadow", s)
        verdict, reasons = R.judge_job({"judge": "enforce"}, {"script": script})
        self.assertEqual(verdict, "fail")
        self.assertTrue(reasons)


class _ModelResp:
    def __init__(self, message):
        self._body = json.dumps(
            {"choices": [{"message": message}]}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n=-1):
        return self._body


class HandedToTheModelTest(unittest.TestCase):
    """The notable line is in the message the model actually receives."""

    def _ask(self, question, ctx, base, replies=("noted",), max_chars=2000):
        seen = []
        script = list(replies)

        def opener(req, timeout=60):
            seen.append(json.loads(req.data.decode("utf-8")))
            msg = script.pop(0) if script else replies[-1]
            return _ModelResp({"role": "assistant", "content": msg})

        ans = R.ask_model_agent(
            {"endpoint": "http://127.0.0.1:11434/v1", "model": "m",
             "max_answer_chars": 12},
            question, ctx, max_chars, opener=opener, base_dir=base)
        return ans, seen

    def test_flag_record_is_the_user_message(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "retained"))
        R.save_retained(d, "jobflag1", _record(FLAG, stdout="321\n"))
        ctx = R.oracle_context(d, watch=False)
        ans, seen = self._ask("which jobs are malicious?", ctx, d)
        self.assertEqual(ans.get("answer"), "noted")
        self.assertEqual(len(seen), 1)
        system = seen[0]["messages"][0]["content"]
        user = seen[0]["messages"][1]["content"]
        self.assertIn("'notable:' line", system)
        self.assertIn("which jobs are malicious?", user)
        self.assertIn("notable: SUSPICIOUS ACCESS", user)
        self.assertIn("Desktop/flag.txt", user)
        self.assertIn("321", user)

    def test_question_mutations_do_not_drop_the_line(self):
        import random
        rng = random.Random(321)
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "retained"))
        R.save_retained(d, "jobflag1", _record(FLAG, stdout="321\n"))
        ctx = R.oracle_context(d, watch=False)
        words = ["malicious", "none", "flag", "?", "jobflag1", "321",
                 "notable", "clean", "all of them", ""]
        for _ in range(40):
            question = " ".join(rng.choice(words)
                                for _ in range(rng.randint(1, 6)))
            _ans, seen = self._ask(question or "?", ctx, d)
            user = seen[0]["messages"][1]["content"]
            self.assertIn("notable: SUSPICIOUS ACCESS", user)
            self.assertIn(question or "?", user)


_KEY = "AKIAIOSFODNN7EXAMPLE"


class ReplyGateTest(unittest.TestCase):
    """What comes back. The runner does not overrule the model."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "retained"))
        R.save_retained(self.base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        self.ctx = R.oracle_context(self.base, watch=False)
        self.ask = HandedToTheModelTest()._ask

    def test_a_denial_is_returned_unchanged(self):
        ans, seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=("none of the jobs are malicious.",))
        self.assertEqual(ans.get("answer"),
                         "none of the jobs are malicious.")
        self.assertIn("notable: SUSPICIOUS ACCESS",
                      seen[0]["messages"][1]["content"])
        self.assertIn(_KEY, seen[0]["messages"][1]["content"])

    def test_repeating_the_secret_is_rejected(self):
        ans, seen = self.ask(
            "what did it read?", self.ctx, self.base,
            replies=("the file held " + _KEY,))
        self.assertEqual(ans.get("rejected"), "sanitization")
        self.assertNotIn("answer", ans)
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_a_slice_of_the_secret_is_rejected(self):
        import random
        rng = random.Random(321)
        for _ in range(20):
            i = rng.randint(0, len(_KEY) - 8)
            slice_ = _KEY[i:i + 8]
            ans, _seen = self.ask(
                "what did it read?", self.ctx, self.base,
                replies=("saw " + slice_,))
            self.assertEqual(ans.get("rejected"), "sanitization", slice_)

    def test_clean_replies_pass_while_the_secret_stays_in_context(self):
        import random
        rng = random.Random(321)
        words = ["none", "malicious", "jobflag1", "read", "a", "file",
                 "outside", "the", "workspace", "321"]
        for _ in range(30):
            reply = " ".join(rng.choice(words)
                             for _ in range(rng.randint(3, 8)))
            ans, seen = self.ask(
                "which jobs are malicious?", self.ctx, self.base,
                replies=(reply,))
            self.assertEqual(ans.get("answer"), reply)
            self.assertIn(_KEY, seen[0]["messages"][1]["content"])

    def test_a_json_dump_is_withheld_and_the_line_survives_the_reask(self):
        dump = json.dumps({
            "job_status": "ok", "newest_job_index": "0",
            "job_ids": "jobflag1",
        })
        ans, seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=(dump, "jobflag1 read a file outside its workspace."))
        self.assertEqual(
            ans.get("answer"),
            "jobflag1 read a file outside its workspace.")
        self.assertEqual(len(seen), 2)
        for call in seen:
            self.assertIn("notable: SUSPICIOUS ACCESS",
                          call["messages"][1]["content"])
        self.assertIn("plain sentences", call["messages"][-1]["content"])

    def test_two_dumps_become_the_fallback(self):
        dump = json.dumps({
            "job_status": "ok", "newest_job_index": "0",
            "job_ids": "jobflag1",
        })
        ans, seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=(dump, dump))
        self.assertIn("withheld both replies", ans.get("answer", ""))
        self.assertEqual(len(seen), 2)
        self.assertIn("notable:", seen[1]["messages"][1]["content"])

    def test_a_bad_cap_uses_the_configured_one(self):
        ans, seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=("abcdefghijklmnopqrstuvwxyz",), max_chars="nope")
        self.assertEqual(ans.get("answer"), "abcdefghijkl")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_a_negative_cap_returns_an_empty_answer(self):
        ans, _seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=("none malicious",), max_chars=-1)
        self.assertEqual(ans.get("answer"), "")

    def test_tool_call_fragments_are_withheld(self):
        # A parseable {"name", "parameters"} object is executed, not
        # withheld. These are fragments: the name is there, the JSON
        # is not a call.
        import random
        rng = random.Random(321)
        shapes = ['{"parameters": {"command": "id"}}']
        for name in sorted(R._ORACLE_TOOL_NAMES):
            shapes.append('see {"name": "%s", "parameters": "nope"}' % name)
            shapes.append('see {"name": "%s", "arguments": "nope"}' % name)
        for _ in range(8):
            name = rng.choice(sorted(R._ORACLE_TOOL_NAMES))
            shapes.append("note " + '{"name": "%s", "parameters": "x"}' % name)
        for shape in shapes:
            self.assertTrue(R._answer_format_problem(shape), shape)
            ans, seen = self.ask(
                "which jobs are malicious?", self.ctx, self.base,
                replies=(shape, "jobflag1 is the one."))
            self.assertEqual(ans.get("answer"), "jobflag1 is the one.", shape)
            self.assertIn("notable:", seen[0]["messages"][1]["content"])
            self.assertIn("notable:", seen[-1]["messages"][1]["content"])
        self.assertEqual(R._answer_format_problem("{not json"), "")

    def test_two_index_fields_are_a_dump(self):
        dump = json.dumps({"job_status": "ok", "job_ids": "jobflag1"})
        ans, seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=(dump, "jobflag1 is the one."))
        self.assertEqual(ans.get("answer"), "jobflag1 is the one.")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_a_blank_reask_comes_back_empty(self):
        dump = json.dumps({
            "job_status": "ok", "newest_job_index": "0",
            "job_ids": "jobflag1",
        })
        ans, seen = self.ask(
            "which jobs are malicious?", self.ctx, self.base,
            replies=(dump, None))
        self.assertEqual(ans.get("answer"), "")
        self.assertIn("notable:", seen[1]["messages"][1]["content"])

    def test_redaction_that_creates_a_secret_is_rejected(self):
        with unittest.mock.patch(
                "runner.runner.redact_text", return_value=(_KEY, [])):
            ans, seen = self.ask(
                "which jobs are malicious?", self.ctx, self.base,
                replies=("the jobs look ordinary.",))
        self.assertEqual(ans.get("rejected"), "sanitization")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])


def _wire_call(name, args, call_id="call-1"):
    return {
        "role": "assistant", "content": "",
        "tool_calls": [{
            "id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }],
    }


class ToolRoundTest(unittest.TestCase):
    """A tool round does not drop the notable line, and does not run it."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "retained"))
        R.save_retained(self.base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        self.ctx = R.oracle_context(self.base, watch=False)

    def _ask(self, replies, tool_text="listed"):
        seen = []
        queue = list(replies)

        def opener(req, timeout=60):
            seen.append(json.loads(req.data.decode("utf-8")))
            msg = queue.pop(0) if queue else replies[-1]
            return _ModelResp(msg)

        with unittest.mock.patch(
                "runner.runner._run_oracle_tool", return_value=tool_text):
            ans = R.ask_model_agent(
                {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
                "which jobs are malicious?", self.ctx, 2000,
                opener=opener, base_dir=self.base)
        return ans, seen

    def test_a_wire_call_keeps_the_line_and_does_not_run(self):
        ans, seen = self._ask([
            _wire_call("read_file", {"path": "flag.txt"}),
            {"role": "assistant", "content": "jobflag1 is the one."},
        ])
        self.assertEqual(ans.get("answer"), "jobflag1 is the one.")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])
        self.assertIn("notable:", seen[1]["messages"][1]["content"])
        roles = [m["role"] for m in seen[1]["messages"]]
        self.assertIn("tool", roles)
        self.assertIn("listed", seen[1]["messages"][-1]["content"])

    def test_a_content_call_is_replayed_as_chat(self):
        ans, seen = self._ask([
            {"role": "assistant",
             "content": json.dumps(
                 {"name": "list_dir", "parameters": {"path": "."}})},
            {"role": "assistant", "content": "jobflag1 is the one."},
        ])
        self.assertEqual(ans.get("answer"), "jobflag1 is the one.")
        self.assertIn("notable:", seen[1]["messages"][1]["content"])
        self.assertIn("Tool 'list_dir' returned:",
                      seen[1]["messages"][-1]["content"])
        self.assertNotIn("tool_calls", seen[1]["messages"][2])

    def test_tool_output_that_repeats_the_secret_is_rejected(self):
        ans, seen = self._ask([
            _wire_call("read_file", {"path": "flag.txt"}),
            {"role": "assistant", "content": "saw " + _KEY[:8]},
        ], tool_text="secret " + _KEY)
        self.assertEqual(ans.get("rejected"), "sanitization")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_the_round_budget_stops_the_loop(self):
        ans, seen = self._ask([_wire_call("list_dir", {"path": "."})])
        self.assertEqual(ans.get("rejected"), "tool_budget")
        self.assertEqual(len(seen), R._ORACLE_AGENT_MAX_ROUNDS)
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_a_failed_call_still_sent_the_line(self):
        seen = []

        def opener(req, timeout=60):
            seen.append(json.loads(req.data.decode("utf-8")))
            raise RuntimeError("model down")

        ans = R.ask_model_agent(
            {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
            "which jobs are malicious?", self.ctx, 2000,
            opener=opener, base_dir=self.base)
        self.assertEqual(ans.get("rejected"), "inference_error")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_random_tools_keep_the_line(self):
        import random
        rng = random.Random(321)
        names = sorted(R._ORACLE_TOOL_NAMES)
        for _ in range(8):
            name = rng.choice(names)
            ans, seen = self._ask([
                _wire_call(name, {"path": "x"}),
                {"role": "assistant", "content": "jobflag1 is the one."},
            ], tool_text="ok")
            self.assertEqual(ans.get("answer"), "jobflag1 is the one.", name)
            self.assertIn("notable:", seen[0]["messages"][1]["content"])
            self.assertIn("notable:", seen[1]["messages"][1]["content"])

    def test_an_empty_error_gets_the_stock_detail(self):
        ans, seen = self._ask([{"role": "error", "content": ""}])
        self.assertEqual(ans.get("rejected"), "inference_error")
        self.assertEqual(ans.get("detail"), "The local model did not answer.")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_a_non_string_reply_is_stringified(self):
        ans, seen = self._ask([{"role": "assistant", "content": 3}])
        self.assertEqual(ans.get("answer"), "3")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])

    def test_out_of_time_still_has_the_line(self):
        seen = []
        queue = [
            _wire_call("list_dir", {"path": "."}),
            {"role": "assistant", "content": "jobflag1 is the one."},
        ]
        clock = {"n": 0}

        def opener(req, timeout=60):
            seen.append(json.loads(req.data.decode("utf-8")))
            return _ModelResp(queue.pop(0))

        def mono():
            clock["n"] += 1
            return 0 if clock["n"] == 1 else 100000

        progress = {}
        with unittest.mock.patch("runner.runner.time.monotonic", mono), \
                unittest.mock.patch(
                    "runner.runner._run_oracle_tool", return_value="listed"):
            ans = R.ask_model_agent(
                {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
                "which jobs are malicious?", self.ctx, 2000,
                opener=opener, base_dir=self.base, progress=progress)
        self.assertEqual(ans.get("answer"), "jobflag1 is the one.")
        self.assertIn("notable:", seen[0]["messages"][1]["content"])
        self.assertIn("out of investigation time",
                      seen[-1]["messages"][-1]["content"])
        self.assertEqual(progress.get("step"),
                         "Writing the answer from what it has")

    def _out_of_time(self, second):
        queue = [_wire_call("list_dir", {"path": "."}), second]
        clock = {"n": 0}

        def opener(req, timeout=60):
            return _ModelResp(queue.pop(0))

        def mono():
            clock["n"] += 1
            return 0 if clock["n"] == 1 else 100000

        with unittest.mock.patch("runner.runner.time.monotonic", mono), \
                unittest.mock.patch(
                    "runner.runner._run_oracle_tool", return_value="listed"):
            return R.ask_model_agent(
                {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
                "which jobs are malicious?", self.ctx, 2000,
                opener=opener, base_dir=self.base)

    def test_out_of_time_and_the_model_errors(self):
        ans = self._out_of_time({"role": "error", "content": ""})
        self.assertEqual(ans.get("rejected"), "inference_error")
        self.assertEqual(ans.get("detail"), "The local model did not answer.")

    def test_out_of_time_reply_that_is_not_text(self):
        ans = self._out_of_time({"role": "assistant", "content": 3})
        self.assertEqual(ans.get("answer"), "3")

    def test_an_unprintable_tool_argument_is_logged_as_unknown(self):
        class Bad:
            pass

        real = R._parse_tool_calls
        seen = {"n": 0}

        def parse(msg):
            seen["n"] += 1
            if seen["n"] == 1:
                return [("call-1", "list_dir", Bad())]
            return real(msg)

        with unittest.mock.patch("runner.runner._parse_tool_calls", parse), \
                unittest.mock.patch(
                    "runner.runner._run_oracle_tool", return_value="listed"):
            ans, calls = self._ask([
                _wire_call("list_dir", {"path": "."}),
                {"role": "assistant", "content": "jobflag1 is the one."},
            ])
        self.assertEqual(ans.get("answer"), "jobflag1 is the one.")
        self.assertIn("notable:", calls[0]["messages"][1]["content"])

    def test_trimming_keeps_the_question_and_drops_the_oldest_tool(self):
        fat = "x" * 8000
        ans, seen = self._ask([
            _wire_call("list_dir", {"path": "."}, "c1"),
            _wire_call("read_file", {"path": "a"}, "c2"),
            {"role": "assistant", "content": "jobflag1 is the one."},
        ], tool_text=fat)
        self.assertEqual(ans.get("answer"), "jobflag1 is the one.")
        last = seen[-1]["messages"]
        self.assertIn("notable:", last[1]["content"])
        self.assertEqual(last[0]["role"], "system")
        # The first tool pair is gone. The second result is still there.
        blob = json.dumps(last)
        self.assertNotIn('"c1"', blob)
        self.assertIn("read_file", blob)

    def test_trim_invariants(self):
        import random
        rng = random.Random(321)
        question = {"role": "user", "content": "notable: SUSPICIOUS ACCESS"}
        system = {"role": "system", "content": "rules"}
        for _ in range(40):
            pairs = []
            for i in range(rng.randint(0, 6)):
                pairs.append({"role": "assistant", "content": "c" * rng.randint(0, 9000)})
                pairs.append({"role": "tool", "content": "t" * rng.randint(0, 9000)})
            messages = [system, question] + pairs
            got = R._agent_trim(messages)
            self.assertEqual(got[:2], [system, question])
            tail = got[2:]
            self.assertEqual(len(tail) % 2, 0)
            if len(tail) > 2:
                self.assertLessEqual(
                    R._agent_context_size(got),
                    R._ORACLE_AGENT_CONTEXT_CHARS)
        odd = [system, question, "nope", {"role": "tool", "content": 3}]
        self.assertEqual(R._agent_trim(odd)[:2], [system, question])


def _chat_lines(base):
    path = os.path.join(base, "oracle-chat.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class ChatLogTest(unittest.TestCase):
    """The chat log stores the question and the answer, not the job record."""

    def setUp(self):
        self.base = tempfile.mkdtemp()

    def test_a_denial_is_logged_without_the_job_secret(self):
        R.record_oracle_turn(
            self.base, {}, "which jobs are malicious?",
            {"answer": "none of the jobs are malicious.", "model": "m",
             "tool_rounds": 1})
        rec = _chat_lines(self.base)[0]
        self.assertEqual(rec["question"], "which jobs are malicious?")
        self.assertEqual(rec["answer"], "none of the jobs are malicious.")
        self.assertEqual(rec["model"], "m")
        self.assertEqual(rec["tool_rounds"], 1)
        self.assertNotIn(_KEY, json.dumps(rec))

    def test_a_secret_in_the_question_or_the_answer_is_redacted(self):
        R.record_oracle_turn(
            self.base, {}, "the file held " + _KEY,
            {"answer": "saw " + _KEY, "detail": "detail " + _KEY,
             "rejected": "sanitization"})
        rec = _chat_lines(self.base)[0]
        blob = json.dumps(rec)
        self.assertNotIn(_KEY, blob)
        self.assertIn("[REDACTED:aws_key]", rec["question"])
        self.assertIn("[REDACTED:aws_key]", rec["answer"])
        self.assertIn("[REDACTED:aws_key]", rec["detail"])

    def test_bad_shapes_do_not_write_the_secret(self):
        R.record_oracle_turn(None, {}, "q", {"answer": _KEY})
        R.record_oracle_turn(3, {}, "q", {"answer": _KEY})
        R.record_oracle_turn(self.base, {}, "q", "not-a-record")
        R.record_oracle_turn(
            self.base, {}, "secret " + _KEY,
            {"answer": "clean", "detail": 5})
        R.record_oracle_turn(
            self.base, "nope", 321,
            {"answer": 5, "rejected": 9, "model": 8,
             "tool_rounds": "many", "detail": None},
            event=7)
        lines = _chat_lines(self.base)
        self.assertEqual(lines[0]["answer"], "")
        self.assertEqual(lines[1]["detail"], "")
        self.assertIn("[REDACTED:aws_key]", lines[1]["question"])
        rec = lines[2]
        self.assertEqual(rec["question"], "")
        self.assertEqual(rec["answer"], "")
        self.assertEqual(rec["rejected"], "")
        self.assertEqual(rec["model"], "")
        self.assertEqual(rec["detail"], "")
        self.assertEqual(rec["tool_rounds"], 0)
        self.assertEqual(rec["event"], "ask")
        for line in lines:
            self.assertNotIn(_KEY, json.dumps(line))

    def test_long_fields_are_cut(self):
        R.record_oracle_turn(
            self.base, {}, "q" * 3000,
            {"answer": "a" * 5000, "detail": "d" * 500})
        rec = _chat_lines(self.base)[0]
        self.assertEqual(len(rec["question"]), 2000)
        self.assertEqual(len(rec["answer"]), 4000)
        self.assertEqual(len(rec["detail"]), 300)

    def test_random_questions_never_store_the_key(self):
        import random
        rng = random.Random(321)
        words = ["which", "jobs", "are", "malicious", "none", "jobflag1",
                 _KEY, "321", "notable"]
        for _ in range(40):
            question = " ".join(rng.choice(words)
                                for _ in range(rng.randint(1, 8)))
            answer = " ".join(rng.choice(words)
                              for _ in range(rng.randint(1, 8)))
            base = tempfile.mkdtemp()
            R.record_oracle_turn(
                base, {}, question, {"answer": answer, "model": "m"})
            blob = json.dumps(_chat_lines(base)[0])
            self.assertNotIn(_KEY, blob)
            if _KEY in question or _KEY in answer:
                self.assertIn("[REDACTED:aws_key]", blob)


class HttpAskTest(unittest.TestCase):
    """POST /ask hands the model the notable line, then logs the answer."""

    def setUp(self):
        import threading
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "retained"))
        R.save_retained(self.base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        self.httpd = R.make_oracle_server(
            {}, "127.0.0.1", 0, base_dir=self.base)
        self.port = self.httpd.socket.getsockname()[1]
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _post(self, question, token=None, origin=True, raw=None):
        import urllib.error
        import urllib.request
        if token is None:
            token = self.httpd.oracle_token
        data = raw if raw is not None else json.dumps(
            {"question": question}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Oracle-Token": token,
        }
        if origin:
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/ask",
            data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def test_the_model_is_handed_the_notable_line(self):
        seen = {}

        def fake_ask(inf, question, output_text, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            seen["question"] = question
            seen["output"] = output_text
            return {"op": "ask", "answer": "jobflag1 is the one.",
                    "model": "m"}

        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask):
            status, body = self._post("which jobs are malicious?")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"answer": "jobflag1 is the one."})
        self.assertEqual(seen["question"], "which jobs are malicious?")
        self.assertIn("notable: SUSPICIOUS ACCESS", seen["output"])
        self.assertIn(_KEY, seen["output"])
        rec = _chat_lines(self.base)[0]
        self.assertEqual(rec["answer"], "jobflag1 is the one.")
        self.assertNotIn(_KEY, json.dumps(rec))

    def test_a_dropped_reply_is_the_sanitization_sentence(self):
        def fake_ask(*_a, **_k):
            return {"op": "ask", "rejected": "sanitization"}

        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask):
            status, body = self._post("what did it read?")
        self.assertEqual(status, 200)
        self.assertEqual(body["rejected"], "sanitization")
        self.assertIn("protected material", body["detail"])
        self.assertNotIn(_KEY, json.dumps(body))
        self.assertNotIn(_KEY, json.dumps(_chat_lines(self.base)[0]))

    def test_empty_and_junk_questions_do_not_ask(self):
        called = []

        def fake_ask(*_a, **_k):
            called.append(1)
            return {"answer": "no"}

        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask):
            for question in ("", "   ", 5, None, ["x"]):
                status, body = self._post(question)
                self.assertEqual(status, 200, question)
                self.assertEqual(body.get("detail"), "Ask something first.")
            status, body = self._post("q", raw=b"not json")
            self.assertEqual(body.get("detail"), "Ask something first.")
        self.assertEqual(called, [])

    def test_the_token_and_the_origin_are_required(self):
        status, _body = self._post("which jobs?", token="nope")
        self.assertEqual(status, 403)
        status, _body = self._post("which jobs?", origin=False)
        self.assertEqual(status, 403)

    def test_a_crashing_model_and_a_crashing_log_still_answer(self):
        def boom(*_a, **_k):
            raise RuntimeError("down")

        with unittest.mock.patch("runner.runner.ask_model_agent", boom):
            status, body = self._post("which jobs are malicious?")
        self.assertEqual(status, 200)
        self.assertEqual(body["rejected"], "inference_error")

        def fine(*_a, **_k):
            return {"answer": "jobflag1 is the one."}

        def log_boom(*_a, **_k):
            raise RuntimeError("disk")

        with unittest.mock.patch("runner.runner.ask_model_agent", fine), \
                unittest.mock.patch("runner.runner.record_oracle_turn", log_boom):
            status, body = self._post("which jobs are malicious?")
        self.assertEqual(body, {"answer": "jobflag1 is the one."})

    def test_random_questions_all_carry_the_line(self):
        import random
        rng = random.Random(321)
        words = ["which", "jobs", "malicious", "none", "jobflag1", "?"]
        seen = []

        def fake_ask(inf, question, output_text, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            seen.append(output_text)
            return {"answer": "jobflag1 is the one."}

        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask):
            for _ in range(12):
                question = " ".join(rng.choice(words)
                                    for _ in range(rng.randint(1, 5)))
                status, body = self._post(question)
                self.assertEqual(status, 200)
                self.assertEqual(body["answer"], "jobflag1 is the one.")
        self.assertEqual(len(seen), 12)
        for output in seen:
            self.assertIn("notable: SUSPICIOUS ACCESS", output)
            self.assertIn(_KEY, output)

    def test_the_handler_rejects_a_bad_request(self):
        import http.client
        headers = {
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-Oracle-Token": self.httpd.oracle_token,
            "Content-Type": "application/json",
        }
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/nope", b"{}", headers)
        self.assertEqual(conn.getresponse().status, 404)
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        bad = dict(headers)
        bad["Content-Length"] = "nope"
        conn.request("POST", "/ask", b"", bad)
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(body.get("detail"), "Ask something first.")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/ask", b"x" * 8001, headers)
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()

        def fake(*_a, **_k):
            return {"rejected": "inference_error", "detail": "disk full"}

        with unittest.mock.patch("runner.runner.ask_model_agent", fake):
            _status, body = self._post("which jobs are malicious?")
        self.assertEqual(body["detail"], "disk full")

    def test_the_page_and_status_do_not_carry_the_record(self):
        import urllib.request
        page = urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/", timeout=5).read().decode()
        self.assertNotIn(_KEY, page)
        self.assertNotIn("notable:", page)
        self.assertNotIn("SUSPICIOUS", page)
        self.assertIn(self.httpd.oracle_token, page)

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/status",
            headers={"X-Oracle-Token": self.httpd.oracle_token})
        status = json.loads(urllib.request.urlopen(req, timeout=5).read())
        self.assertIn("active", status)
        self.assertNotIn(_KEY, json.dumps(status))

        import urllib.error
        bad = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/status",
            headers={"X-Oracle-Token": "nope"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(bad, timeout=5)
        self.assertEqual(caught.exception.code, 403)

        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/nope", timeout=5)
        self.assertEqual(caught.exception.code, 404)


class PageTextTest(unittest.TestCase):
    def test_non_text_fields_do_not_leak(self):
        class Bad:
            def __str__(self):
                raise RuntimeError("no")

        page = R.oracle_page(None, Bad(), True)
        self.assertNotIn(_KEY, page)
        self.assertIn('"model": ""', page)
        page = R.oracle_page(3, 4, False)
        self.assertIn('"model": "4"', page)
        self.assertNotIn("notable:", page)


class CliNotableTest(unittest.TestCase):
    def test_the_terminal_is_handed_the_notable_line(self):
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "retained"))
        R.save_retained(base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        seen = []
        out = []
        lines = ["", "  ", "/help", "which jobs are malicious?", "/quit"]

        def fake_input(prompt=""):
            if not lines:
                raise EOFError
            return lines.pop(0)

        def fake_ask(inf, question, output_text, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            seen.append((question, output_text))
            return {"answer": "jobflag1 is the one.", "model": "m"}

        cfg = {"base_dir": base, "inference": {
            "endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask), \
                unittest.mock.patch("runner.runner._warm_oracle_model"):
            rc = R.oracle_cli(cfg, input_fn=fake_input, print_fn=out.append)
        self.assertEqual(rc, 0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], "which jobs are malicious?")
        self.assertIn("notable: SUSPICIOUS ACCESS", seen[0][1])
        self.assertIn(_KEY, seen[0][1])
        self.assertIn("jobflag1 is the one.", out)
        self.assertTrue(any("/quit ends" in line for line in out))
        blob = json.dumps(_chat_lines(base))
        self.assertNotIn(_KEY, blob)
        self.assertIn("jobflag1 is the one.", blob)

    def test_random_terminal_questions_keep_the_line(self):
        import random
        rng = random.Random(321)
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "retained"))
        R.save_retained(base, "jobflag1", _record(FLAG, stdout=_KEY + "\n"))
        words = ["which", "jobs", "malicious", "none", "jobflag1"]
        questions = [
            " ".join(rng.choice(words) for _ in range(rng.randint(1, 4)))
            for _ in range(8)
        ]
        lines = list(questions) + ["/exit"]
        seen = []

        def fake_input(prompt=""):
            return lines.pop(0)

        def fake_ask(inf, question, output_text, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            seen.append(output_text)
            return {"answer": "jobflag1 is the one."}

        cfg = {"base_dir": base, "inference": {
            "endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask), \
                unittest.mock.patch("runner.runner._warm_oracle_model"):
            rc = R.oracle_cli(cfg, input_fn=fake_input, print_fn=lambda _s: None)
        self.assertEqual(rc, 0)
        self.assertEqual(len(seen), 8)
        for output in seen:
            self.assertIn("notable:", output)
            self.assertIn(_KEY, output)
        self.assertNotIn(_KEY, json.dumps(_chat_lines(base)))

    def _base(self):
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "retained"))
        R.save_retained(base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        return base

    def test_eof_and_interrupt_end_the_chat(self):
        out = []
        cfg = {"base_dir": self._base()}
        rc = R.oracle_cli(
            cfg, input_fn=lambda prompt="": (_ for _ in ()).throw(EOFError),
            print_fn=out.append)
        self.assertEqual(rc, 0)
        self.assertTrue(any("not configured" in line for line in out))

        def interrupt(prompt=""):
            raise KeyboardInterrupt

        out = []
        cfg = {"base_dir": self._base(), "inference": {
            "endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with unittest.mock.patch("runner.runner._warm_oracle_model"):
            rc = R.oracle_cli(cfg, cfg_path=__file__,
                              input_fn=interrupt, print_fn=out.append)
        self.assertEqual(rc, 0)
        self.assertTrue(any("Config:" in line for line in out))
        rc = R.oracle_cli(
            "nope",
            input_fn=lambda prompt="": (_ for _ in ()).throw(EOFError),
            print_fn=lambda _s: None)
        self.assertEqual(rc, 0)
        rc = R.oracle_cli(
            {"base_dir": self._base()},
            input_fn=lambda prompt="": (_ for _ in ()).throw(EOFError))
        self.assertEqual(rc, 0)

    def test_a_refusal_a_crash_and_a_broken_log(self):
        base = self._base()
        cfg = {"base_dir": base, "inference": {
            "endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        answers = [
            {"rejected": "sanitization"},
            {"rejected": "inference_error", "detail": "disk full"},
            "not-a-record",
        ]
        seen = []

        def fake_input(prompt=""):
            if not answers:
                raise EOFError
            return "which jobs are malicious?"

        def fake_ask(inf, question, output_text, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            seen.append(output_text)
            ans = answers.pop(0)
            if ans == "raise":
                raise RuntimeError("down")
            return ans

        answers.append("raise")
        out = []
        with unittest.mock.patch("runner.runner.ask_model_agent", fake_ask), \
                unittest.mock.patch(
                    "runner.runner.record_oracle_turn",
                    side_effect=RuntimeError("disk")), \
                unittest.mock.patch("runner.runner._warm_oracle_model"):
            rc = R.oracle_cli(cfg, input_fn=fake_input, print_fn=out.append)
        self.assertEqual(rc, 0)
        self.assertEqual(len(seen), 4)
        for output in seen:
            self.assertIn("notable:", output)
            self.assertIn(_KEY, output)
        text = "\n".join(out)
        self.assertIn("protected material", text)
        self.assertIn("disk full", text)
        self.assertIn("did not answer", text)
        self.assertNotIn(_KEY, text)


class ExchangeLogTest(unittest.TestCase):
    """oracle.log is the full inference record. The chat log is not."""

    def setUp(self):
        self._saved = (
            R._ORACLE_LOG_ENABLED, R._ORACLE_LOG_PATH,
            R._ORACLE_LOG_ANNOUNCED, R._LOG_FILE)
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "retained"))
        R.save_retained(self.base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        self.ctx = R.oracle_context(self.base, watch=False)
        R._LOG_FILE = os.path.join(self.base, "runner.log")

    def tearDown(self):
        (R._ORACLE_LOG_ENABLED, R._ORACLE_LOG_PATH,
         R._ORACLE_LOG_ANNOUNCED, R._LOG_FILE) = self._saved

    def _ask(self, replies=("noted",)):
        queue = list(replies)

        def opener(req, timeout=60):
            msg = queue.pop(0) if queue else replies[-1]
            return _ModelResp(msg)

        return R.ask_model_agent(
            {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
            "which jobs are malicious?", self.ctx, 2000,
            opener=opener, base_dir=self.base)

    def _oracle_log(self):
        path = os.path.join(self.base, "oracle.log")
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_off_by_default_writes_nothing(self):
        R._refresh_log_settings({}, self.base)
        ans = self._ask()
        self.assertEqual(ans.get("answer"), "noted")
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "oracle.log")))

    def test_when_enabled_the_record_is_complete(self):
        R._refresh_log_settings({"oracle_log": True}, self.base)
        R._announce_oracle_log()
        R._announce_oracle_log()
        ans = self._ask()
        self.assertEqual(ans.get("answer"), "noted")
        rec = self._oracle_log()[0]
        blob = json.dumps(rec)
        self.assertIn("notable: SUSPICIOUS ACCESS", blob)
        self.assertIn(_KEY, blob)
        self.assertIn("noted", blob)
        with open(R._LOG_FILE, encoding="utf-8") as fh:
            runner = fh.read()
        self.assertEqual(runner.count("oracle log enabled"), 1)

    def test_a_failed_call_is_recorded_too(self):
        R._refresh_log_settings({"oracle_log": "yes"}, self.base)

        def opener(req, timeout=60):
            raise RuntimeError("model down")

        ans = R.ask_model_agent(
            {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"},
            "which jobs are malicious?", self.ctx, 2000,
            opener=opener, base_dir=self.base)
        self.assertEqual(ans.get("rejected"), "inference_error")
        rec = self._oracle_log()[0]
        blob = json.dumps(rec)
        self.assertIn("notable:", blob)
        self.assertIn(_KEY, blob)
        self.assertIn("error", rec)

    def test_the_flag_is_only_those_words(self):
        for value in (True, 1, "yes", "on", "true", "1", " YES "):
            R._refresh_log_settings({"oracle_log": value}, self.base)
            self.assertTrue(R._ORACLE_LOG_ENABLED, value)
        for value in (False, 0, "no", "off", "", None, 2, "maybe"):
            R._refresh_log_settings({"oracle_log": value}, self.base)
            self.assertFalse(R._ORACLE_LOG_ENABLED, value)
        R._refresh_log_settings("nope", self.base)
        self.assertFalse(R._ORACLE_LOG_ENABLED)

    def test_a_circular_record_is_dropped(self):
        R._refresh_log_settings({"oracle_log": True}, self.base)
        rec = {}
        rec["self"] = rec
        R._oracle_log_record(rec)
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "oracle.log")))

    def test_random_switches_match_the_flag(self):
        import random
        rng = random.Random(321)
        on = [True, 1, "yes", "on", "true", "1"]
        off = [False, 0, "no", None, "", "off", "maybe"]
        for _ in range(30):
            value = rng.choice(on + off)
            R._refresh_log_settings({"oracle_log": value}, self.base)
            self.assertEqual(R._ORACLE_LOG_ENABLED, value in on, value)

    def test_a_disabled_record_is_dropped_and_an_error_body_is_kept(self):
        R._refresh_log_settings({}, self.base)
        R._oracle_log_record({"request": _KEY})
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "oracle.log")))
        R._refresh_log_settings({"oracle_log": True}, self.base)
        R._oracle_log_exchange(
            "http://127.0.0.1:11434/v1", "m",
            {"messages": [{"content": self.ctx}]}, 0,
            error="HTTP 400", error_body="body " + _KEY)
        rec = self._oracle_log()[0]
        self.assertEqual(rec["error"], "HTTP 400")
        self.assertIn(_KEY, rec["error_body"])
        self.assertIn("notable:", json.dumps(rec["request"]))


class _BadEq:
    def __eq__(self, other):
        raise RuntimeError("no")


class _BadStr:
    def __str__(self):
        raise RuntimeError("no")


class _BadBool:
    def __bool__(self):
        raise RuntimeError("no")


class ResultPolicyTest(unittest.TestCase):
    """What of a flag job is retained, and what a later query can see."""

    def _job(self, view="attested", queries=None):
        policy = {"view": view}
        if queries is not None:
            policy["queries"] = queries
        return {"job_id": "jobflag1", "kind": "exec",
                "script": FLAG, "result_policy": policy}

    def _ran(self, exit_code=0):
        return {"stdout": _KEY + "\n", "stderr": "", "exit_code": exit_code,
                "timed_out": False, "duration_sec": 0.01}

    def test_full_is_not_retained_and_keeps_the_secret(self):
        result, retain = R.apply_result_policy(
            {}, self._job("full"), self._ran(),
            R.BUILTIN_REDACT_PATTERNS, None)
        self.assertFalse(retain)
        self.assertIn(_KEY, result["stdout"])

    def test_redacted_keeps_the_job_and_hides_the_secret(self):
        patterns = dict(R.BUILTIN_REDACT_PATTERNS)
        patterns["broken"] = "["
        patterns["not-a-pattern"] = 5
        result, retain = R.apply_result_policy(
            {"max_result_view": "redacted"}, self._job("full"),
            self._ran(), patterns, None)
        self.assertTrue(retain)
        self.assertEqual(result["view"], "redacted")
        self.assertNotIn(_KEY, result["stdout"])
        self.assertIn("[REDACTED:aws_key]", result["stdout"])
        self.assertIn("aws_key", result["redacted_families"])

    def test_summary_counts_bytes_and_does_not_keep_the_text(self):
        result, retain = R.apply_result_policy(
            {"max_result_view": "summary"}, self._job("full"),
            self._ran(), {}, None)
        self.assertTrue(retain)
        self.assertNotIn("stdout", result)
        self.assertEqual(result["result_class"], "ok")
        self.assertGreater(result["stdout_bytes"], 0)
        failed, _retain = R.apply_result_policy(
            {"max_result_view": "summary"}, self._job("summary"),
            self._ran(_BadEq()), {}, None)
        self.assertEqual(failed["result_class"], "fail")

    def test_attested_answers_the_declared_questions(self):
        queries = [
            {"op": "attest", "predicate": "exit_zero"},
            {"op": "attest", "predicate": "no_secrets"},
            {"op": "attest", "predicate": "output_digest"},
            {"op": "attest", "predicate": "confined_to_workspace"},
            {"op": "attest", "predicate": "made_up"},
            "not-a-query",
            {"op": "nope", "predicate": "exit_zero"},
        ]
        result, retain = R.apply_result_policy(
            {"max_result_view": "attested"}, self._job("full", queries),
            self._ran(), R.BUILTIN_REDACT_PATTERNS, None)
        self.assertTrue(retain)
        self.assertEqual(result["stdout"], "")
        by_pred = {a["predicate"]: a for a in result["attestations"]
                   if isinstance(a, dict)}
        self.assertTrue(by_pred["exit_zero"]["ok"])
        self.assertFalse(by_pred["no_secrets"]["ok"])
        self.assertIn("digest", by_pred["output_digest"])
        self.assertEqual(by_pred["confined_to_workspace"]["reason"],
                         "unconfigured")
        self.assertEqual(by_pred["made_up"]["reason"], "unknown")

    def test_bad_shapes_fall_closed(self):
        result, retain = R.apply_result_policy(
            "nope", "nope", "nope", "nope", None)
        self.assertFalse(retain)
        self.assertEqual(result["view"], "full")
        result, retain = R.apply_result_policy(
            {"max_result_view": 5},
            {"result_policy": {"view": 5}},
            self._ran(), {}, None)
        self.assertFalse(retain)
        self.assertEqual(result["view"], "full")

    def test_a_path_past_the_saved_script_cut_is_not_notable(self):
        early = "echo " + ("a" * 400) + " && cat /etc/shadow"
        late = "echo " + ("a" * 500) + " && cat /etc/shadow"
        for script, notable in ((early, True), (late, False)):
            saved = script[:500]
            summary = R._retained_job_summary(
                _record(saved, stdout=_KEY + "\n"), "jobx", BASE)
            self.assertEqual("notable:" in summary, notable, len(script))
            if notable:
                self.assertIn("/etc/shadow", summary)

    def test_no_log_file_writes_nothing(self):
        saved = R._LOG_FILE
        try:
            R._LOG_FILE = ""
            R._log_job_output("jobflag1", "exec", _KEY, "", {})
        finally:
            R._LOG_FILE = saved

    def test_the_job_log_redacts_the_secret(self):
        saved = R._LOG_FILE
        path = os.path.join(tempfile.mkdtemp(), "runner.log")
        try:
            R._LOG_FILE = path
            R._log_job_output("jobflag1", "exec", _KEY + "\n", "err", {})
        finally:
            R._LOG_FILE = saved
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn(_KEY, text)
        self.assertIn("[REDACTED:aws_key]", text)
        self.assertIn("jobflag1", text)

    def test_attestation_edges(self):
        ctx = {
            "exit_code": _BadEq(), "text": _KEY, "digest": "d",
            "confined": _BadBool(),
            "patterns": {
                _BadStr(): "AKIA[0-9A-Z]{16}", "ok": 5,
                "aws_key": R.BUILTIN_REDACT_PATTERNS["aws_key"],
            },
        }
        queries = [
            {"op": "attest", "predicate": _BadEq()},
            {"op": "attest", "predicate": "exit_zero"},
            {"op": "attest", "predicate": "no_secrets"},
            {"op": "attest", "predicate": "confined_to_workspace"},
        ]
        atts = R.build_attestations(queries, ctx)
        self.assertEqual(atts[0]["reason"], "unknown")
        self.assertFalse(atts[1]["ok"])
        self.assertFalse(atts[2]["ok"])
        self.assertEqual(atts[3]["reason"], "unconfigured")
        self.assertEqual(R.build_attestations("nope", {}), [])
        self.assertEqual(R.build_attestations([], "nope"), [])

        class On:
            def __bool__(self):
                return True

        class Off:
            def __bool__(self):
                return False

        on = R.build_attestations(
            [{"op": "attest", "predicate": "confined_to_workspace"}],
            {"confined": On()})
        off = R.build_attestations(
            [{"op": "attest", "predicate": "confined_to_workspace"}],
            {"confined": Off()})
        self.assertTrue(on[0]["ok"])
        self.assertEqual(off[0]["reason"], "violation_detected")
        bare = R.build_attestations(
            [{"op": "attest", "predicate": "no_secrets"}],
            {"text": _KEY, "patterns": "nope"})
        self.assertFalse(bare[0]["ok"])

    def test_random_predicates_do_not_raise(self):
        import random
        rng = random.Random(321)
        names = ["exit_zero", "no_secrets", "output_digest",
                 "confined_to_workspace", "made_up", "", _BadEq()]
        for _ in range(40):
            queries = [
                {"op": rng.choice(["attest", "nope"]),
                 "predicate": rng.choice(names)}
                for _ in range(rng.randint(0, 5))
            ]
            if rng.random() < 0.3:
                queries.append("junk")
            atts = R.build_attestations(queries, {
                "exit_code": rng.choice([0, 1, None]),
                "text": rng.choice(["ok", _KEY]),
                "digest": "d",
                "confined": rng.choice([None, True, False]),
                "patterns": R.BUILTIN_REDACT_PATTERNS,
            })
            self.assertIsInstance(atts, list)


class LaterQueryTest(unittest.TestCase):
    """A later query of a retained flag job, and what it may return."""

    def _save(self):
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "retained"))
        R.save_retained(base, "jobflag1",
                        _record(FLAG, stdout=_KEY + "\n"))
        return base

    def test_the_record_still_loads_and_is_still_notable(self):
        base = self._save()
        data = R.load_retained(base, "jobflag1")
        self.assertEqual(data["script"], FLAG)
        self.assertTrue(R.retained_expired(data, {}))
        text = R.oracle_context(base, watch=False)
        self.assertIn("notable:", text)
        self.assertIn(_KEY, text)

    def test_an_attested_query_cannot_read_the_lines(self):
        answers, spent = R.answer_queries(
            [{"op": "grep", "pattern": "AKIA"},
             {"op": "tail", "lines": 5},
             {"op": "ask", "question": "what did it read?"}],
            {"stdout": _KEY + "\n", "exit_code": 0},
            R.BUILTIN_REDACT_PATTERNS, 8, view="attested")
        self.assertEqual(spent, 3)
        blob = json.dumps(answers)
        self.assertNotIn(_KEY, blob)
        self.assertEqual(answers[0]["rejected"], "policy")
        self.assertEqual(answers[1]["rejected"], "policy")
        self.assertEqual(answers[2]["rejected"], "inference_unconfigured")

    def test_redacted_returns_the_marker_and_full_returns_the_key(self):
        red, _s = R.answer_queries(
            [{"op": "grep", "pattern": "AKIA"},
             {"op": "tail", "lines": 5}],
            {"stdout": _KEY + "\n", "exit_code": 0},
            R.BUILTIN_REDACT_PATTERNS, 8, view="redacted")
        self.assertNotIn(_KEY, json.dumps(red))
        self.assertIn("[REDACTED:aws_key]", json.dumps(red))
        full, _s = R.answer_queries(
            [{"op": "grep", "pattern": "AKIA"},
             {"op": "tail", "lines": 5}],
            {"stdout": _KEY + "\n", "exit_code": 0},
            R.BUILTIN_REDACT_PATTERNS, 8, view="full")
        self.assertIn(_KEY, json.dumps(full))

    def test_a_bad_query_spends_budget_and_returns_nothing_secret(self):
        answers, spent = R.answer_queries(
            ["junk", {"op": "grep", "pattern": "["},
             {"op": "made_up"}, {"op": "attest", "predicate": "nope"}],
            {"stdout": _KEY, "exit_code": 0},
            R.BUILTIN_REDACT_PATTERNS, 8, view="full")
        self.assertEqual(spent, 4)
        self.assertEqual(answers[0]["rejected"], "unknown_op")
        self.assertEqual(answers[1]["rejected"], "bad_pattern")
        self.assertEqual(answers[2]["rejected"], "unknown_op")
        self.assertEqual(answers[3]["reason"], "unknown")
        self.assertNotIn(_KEY, json.dumps(answers))

    def test_the_budget_stops_the_second_question(self):
        answers, spent = R.answer_queries(
            [{"op": "attest", "predicate": "exit_zero"},
             {"op": "tail", "lines": 1}],
            {"stdout": _KEY, "exit_code": 0},
            {}, 1, view="full")
        self.assertEqual(spent, 2)
        self.assertEqual(answers[1]["rejected"], "budget")
        self.assertNotIn(_KEY, answers[1].values())

    def test_unsafe_and_broken_records_do_not_load(self):
        self.assertIsNone(R.load_retained(None, "jobflag1"))
        self.assertIsNone(R.load_retained("/tmp", "../jobflag1"))
        self.assertIsNone(R.load_retained("/tmp", "a/b"))
        base = self._save()
        stored = os.path.join(base, "retained", "jobflag1.json")
        os.remove(stored)
        os.symlink("/etc/passwd", stored)
        self.assertIsNone(R.load_retained(base, "jobflag1"))
        os.remove(stored)
        with open(stored, "w", encoding="utf-8") as fh:
            fh.write("{")
        self.assertIsNone(R.load_retained(base, "jobflag1"))
        with open(stored, "w", encoding="utf-8") as fh:
            fh.write("[]")
        self.assertIsNone(R.load_retained(base, "jobflag1"))

    def test_retention_expiry(self):
        fresh = {"saved_at": time.time()}
        old = {"saved_at": time.time() - 10 * 86400}
        self.assertFalse(R.retained_expired(fresh, {}))
        self.assertTrue(R.retained_expired(old, {}))
        # 0 is falsy, so it falls through to the 7-day default.
        self.assertTrue(R.retained_expired(old, {"output_retention_days": 0}))
        self.assertFalse(R.retained_expired(
            old, {"output_retention_days": -1}))
        self.assertTrue(R.retained_expired({"saved_at": "nope"}, {}))
        self.assertTrue(R.retained_expired({"saved_at": float("nan")}, {}))
        self.assertTrue(R.retained_expired({"saved_at": float("inf")}, {}))
        self.assertTrue(R.retained_expired("nope", {}))
        self.assertTrue(R.retained_expired(fresh, "nope"))
        self.assertTrue(R.retained_expired(
            old, {"output_retention_days": "many"}))

    def test_the_budget_is_the_smaller_number(self):
        job = {"result_policy": {"query_budget": 3}}
        self.assertEqual(R.query_budget({"max_query_budget": 8}, job), 3)
        self.assertEqual(R.query_budget({"max_query_budget": 1}, job), 1)
        self.assertEqual(R.query_budget({}, "nope"), 8)
        self.assertEqual(R.query_budget(
            {"max_query_budget": "many"},
            {"result_policy": {"query_budget": -4}}), 0)
        self.assertEqual(R.query_budget(
            {}, {"result_policy": {"query_budget": float("inf")}}), 8)

    def test_random_queries_never_raise(self):
        import random
        rng = random.Random(321)
        ops = ["grep", "tail", "ask", "attest", "senses", "nope", None]
        for _ in range(30):
            queries = []
            for _ in range(rng.randint(0, 4)):
                queries.append({
                    "op": rng.choice(ops),
                    "pattern": rng.choice(["AKIA", "[", ""]),
                    "lines": rng.choice([0, 1, "nope", 500]),
                    "predicate": rng.choice(["exit_zero", "no_secrets", "nope"]),
                    "max_matches": rng.choice([0, 1, "nope"]),
                })
            if rng.random() < 0.2:
                queries.append("junk")
            answers, spent = R.answer_queries(
                queries, {"stdout": _KEY + "\n", "exit_code": 0},
                R.BUILTIN_REDACT_PATTERNS,
                rng.choice([0, 1, 8, "nope"]),
                view=rng.choice(["full", "redacted", "attested", "summary", ""]))
            self.assertEqual(spent, len(queries))
            blob = json.dumps(answers)
            if queries and all(
                    isinstance(q, dict) and q.get("op") in ("grep", "tail")
                    for q in queries):
                pass
            self.assertIsInstance(answers, list)

    def test_the_remaining_query_shapes(self):
        answers, spent = R.answer_queries(
            [{"op": "grep", "pattern": "AKIA", "max_matches": "nope"},
             {"op": "grep", "pattern": "AKIA", "max_matches": 0},
             {"op": "tail", "lines": "nope"},
             {"op": "tail", "lines": 0}],
            {"stdout": ""}, R.BUILTIN_REDACT_PATTERNS, 8, view=None)
        self.assertEqual(spent, 4)
        self.assertNotIn(_KEY, json.dumps(answers))
        stopped, spent = R.answer_queries(
            [{"op": "grep", "pattern": "AKIA"}],
            {"stdout": _KEY}, {}, -3, already_spent="many", view="full")
        self.assertEqual(stopped[0]["rejected"], "budget")
        blocked, _s = R.answer_queries(
            [{"op": "grep", "pattern": "AKIA"}],
            {"stdout": _KEY}, {}, 8, view=5)
        self.assertEqual(blocked[0]["rejected"], "policy")
        odd, _s = R.answer_queries(
            [{"op": "attest", "predicate": "exit_zero"}], "nope", {}, 8)
        self.assertIn("ok", odd[0])
        empty, spent = R.answer_queries("nope", {}, {}, 8)
        self.assertEqual((empty, spent), ([], 0))
        self.assertEqual(R.query_budget("nope", {}), 8)
        base = self._save()
        self.assertIsNone(R.load_retained(base, "jobmissing"))

    def test_an_ask_query_is_handed_the_output_and_scanned(self):
        seen = {}

        def fake_ask(inf, question, text, max_chars, patterns, **_k):
            seen["text"] = text
            seen["question"] = question
            return {"op": "ask", "answer": "none of it was malicious"}

        cfg = {"inference": {
            "endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with unittest.mock.patch("runner.runner.ask_model", fake_ask):
            answers, _s = R.answer_queries(
                [{"op": "ask", "question": "what did it read?",
                  "max_chars": "nope"}],
                {"stdout": _KEY + "\n", "exit_code": 0},
                R.BUILTIN_REDACT_PATTERNS, 8, cfg=cfg, view="attested")
        self.assertIn(_KEY, seen["text"])
        self.assertEqual(seen["question"], "what did it read?")
        self.assertEqual(answers[0]["answer"], "none of it was malicious")

        def boom(*_a, **_k):
            raise RuntimeError("down")

        with unittest.mock.patch("runner.runner.ask_model", boom):
            answers, _s = R.answer_queries(
                [{"op": "ask", "question": "again"}],
                {"stdout": _KEY}, {}, 8, cfg=cfg, view="full")
        self.assertEqual(answers[0]["rejected"], "inference_error")
        self.assertNotIn(_KEY, json.dumps(answers))

    def test_a_senses_query_redacts_the_secret(self):
        class Senses:
            def parse_sensors(self, cfg):
                if cfg.get("boom"):
                    raise RuntimeError("down")
                return {"eye": {"weight": "nope"}}

            def load_alerts(self, base_dir, **_k):
                return [
                    {"sensor": "eye", "title": "saw " + _KEY,
                     "detail": {"note": _KEY, "n": 1},
                     "severity": "high", "weight": float("nan")},
                    {"sensor": "eye", "title": "plain", "detail": _KEY,
                     "weight": 2},
                    {"sensor": "eye", "title": "other", "detail": 5,
                     "weight": float("inf")},
                ]

            def alert_score(self, rec, weight):
                return weight

        base = self._save()
        with unittest.mock.patch("runner.runner._senses", Senses()):
            answers, _s = R.answer_queries(
                [{"op": "senses", "sensor": "eye", "severity_floor": "high",
                  "since": "2020", "until": "2030", "limit": "nope"}],
                {"stdout": ""}, R.BUILTIN_REDACT_PATTERNS, 8,
                cfg={}, view="attested", base_dir=base)
        blob = json.dumps(answers)
        self.assertNotIn(_KEY, blob)
        self.assertIn("[REDACTED:aws_key]", blob)
        with unittest.mock.patch("runner.runner._senses", Senses()):
            answers, _s = R.answer_queries(
                [{"op": "senses"}], {"stdout": ""}, {}, 8,
                cfg={"boom": True}, base_dir=base)
        self.assertEqual(answers[0]["count"], 3)


class JudgeAndOutsideTest(unittest.TestCase):
    """The judge, and whether a job changed anything outside its workspace."""

    def test_the_denylist_fails_and_the_line_is_separate(self):
        script = "cat /etc/shadow; rm -rf /"
        for mode in ("advisory", "enforce"):
            verdict, reasons = R.judge_job({"judge": mode}, {"script": script})
            self.assertEqual(verdict, "fail")
            self.assertTrue(any("rm -rf /" in r for r in reasons))
        summary = R._retained_job_summary(
            _record(script), "jobx", BASE)
        self.assertIn("notable:", summary)
        self.assertIn("/etc/shadow", summary)
        verdict, reasons = R.judge_job({"judge": "off"}, {"script": script})
        self.assertEqual((verdict, reasons), ("pass", []))
        verdict, reasons = R.judge_job("nope", "nope")
        self.assertEqual(verdict, "pass")

    def test_each_denied_token(self):
        tokens = ["rm -rf /", "rm -rf ~", ":(){ :|:& };:", "mkfs",
                  "dd if=/dev/zero of=/dev/sda"]
        for token in tokens:
            verdict, reasons = R.judge_job(
                {"judge": "enforce"}, {"script": "echo ok; " + token})
            self.assertEqual(verdict, "fail", token)
            self.assertTrue(reasons)
        verdict, reasons = R.judge_job(
            {"judge": "enforce"},
            {"script": 5,
             "script_url": "http://example.com/a.sh",
             "files": [{"name": "../flag.txt"}, "nope", {"name": "ok.txt"}]})
        self.assertEqual(verdict, "fail")
        self.assertIn("non-https script_url", reasons)
        self.assertIn("path traversal in file name", reasons)
        verdict, reasons = R.judge_job(
            {"judge": "enforce"},
            {"script": "uname", "script_url": "https://example.com/a.sh",
             "files": [{"name": "ok.txt"}]})
        self.assertEqual(verdict, "pass")

    def test_random_scripts(self):
        import random
        rng = random.Random(321)
        denied = ["rm -rf /", "mkfs", "dd if=/dev/zero of=/dev/sda"]
        plain = ["uname", "echo hi", "cat /etc/shadow", ""]
        for _ in range(30):
            token = rng.choice(denied + plain)
            script = rng.choice(plain) + "\n" + token
            mode = rng.choice(["advisory", "enforce", "off"])
            verdict, _reasons = R.judge_job({"judge": mode}, {"script": script})
            hit = any(t in script for t in denied)
            if mode == "off":
                self.assertEqual(verdict, "pass")
            else:
                self.assertEqual(verdict == "fail", hit)
            summary = R._retained_job_summary(_record(script), "jobx", BASE)
            self.assertEqual("/etc/shadow" in script, "notable:" in summary)

    def test_a_change_outside_the_workspace_is_visible(self):
        parent = tempfile.mkdtemp()
        ws = os.path.join(parent, "ws")
        os.makedirs(ws)
        outside = os.path.join(parent, "flag.txt")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("321")
        with open(os.path.join(ws, "inside.txt"), "w", encoding="utf-8") as fh:
            fh.write("no")
        snap = R.snapshot_outside(ws)
        self.assertIn(os.path.abspath(outside), snap)
        self.assertNotIn(os.path.abspath(os.path.join(ws, "inside.txt")), snap)
        skip = os.path.join(parent, "skip")
        os.makedirs(skip)
        skipped = os.path.join(skip, "x.txt")
        with open(skipped, "w", encoding="utf-8") as fh:
            fh.write("x")
        pruned = R.snapshot_outside(ws, exclude=[skip, 5])
        self.assertNotIn(os.path.abspath(skipped), pruned)
        self.assertIn(os.path.abspath(outside), pruned)
        self.assertIn(os.path.abspath(outside),
                      R.snapshot_outside(ws, exclude="nope"))
        self.assertEqual(R.snapshot_outside("/no/such/dir"), {})
        self.assertEqual(R.snapshot_outside(None), {})
        self.assertEqual(R.snapshot_outside("/"), {})

    def test_protected_paths_and_a_comparison_that_raises(self):
        parent = tempfile.mkdtemp()
        flag = os.path.join(parent, "flag.txt")
        other = os.path.join(parent, "other.txt")
        before = {flag: (3, 1.0), other: (1, 1.0)}
        after = {flag: (3, 2.0), other: (1, 1.0)}
        changed = R.check_protected_paths(before, after, [parent])
        self.assertEqual(changed, [flag])
        self.assertEqual(R.check_protected_paths(before, after, "nope"), [])
        self.assertEqual(
            R.check_protected_paths("nope", "nope", [parent]), [])

        class Bad:
            def __eq__(self, other):
                raise RuntimeError("no")

        changed = R.check_protected_paths(
            {flag: Bad()}, {flag: (1, 1)}, [parent])
        self.assertEqual(changed, [flag])
        self.assertTrue(R.confinement_violated(
            {flag: Bad()}, {flag: (1, 1)}))
        self.assertTrue(R.confinement_violated({}, {flag: (1, 1)}))
        self.assertFalse(R.confinement_violated(
            {flag: (1, 1)}, {flag: (1, 1)}))
        self.assertFalse(R.confinement_violated("nope", {}))
        self.assertFalse(R.confinement_violated({}, "nope"))

    def test_random_snapshots_of_protected_paths(self):
        import random
        rng = random.Random(321)
        parent = tempfile.mkdtemp()
        flag = os.path.join(parent, "flag.txt")
        for _ in range(20):
            before = {flag: (rng.randint(0, 5), 1.0)}
            after = {flag: (rng.randint(0, 5), 1.0)}
            changed = R.check_protected_paths(before, after, [parent])
            self.assertEqual(changed == [flag], before[flag] != after[flag])
            self.assertEqual(
                R.confinement_violated(before, after),
                before[flag] != after[flag])

    def test_a_snapshot_that_cannot_be_read(self):
        parent = tempfile.mkdtemp()
        ws = os.path.join(parent, "ws")
        os.makedirs(ws)
        with unittest.mock.patch("runner.runner.os.walk",
                                 side_effect=OSError("no")):
            self.assertEqual(R.snapshot_outside(ws), {})

        def walk_then_fail(_parent):
            yield (parent, [], ["gone"])
            raise OSError("mid")

        with unittest.mock.patch("runner.runner.os.walk", walk_then_fail):
            self.assertEqual(R.snapshot_outside(ws), {})

        class BadAfter(dict):
            def items(self):
                raise RuntimeError("no")

        self.assertTrue(R.confinement_violated({}, BadAfter()))
        self.assertEqual(
            R.check_protected_paths({5: (1, 1)}, {5: (2, 1)}, [parent]),
            [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
