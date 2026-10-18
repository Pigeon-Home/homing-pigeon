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


if __name__ == "__main__":
    unittest.main(verbosity=2)
