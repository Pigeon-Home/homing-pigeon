"""Low-profile senses: ATT&CK labels, host-log tail, firewall posture,
and the on-demand artifact scan. No test starts yara, clamdscan,
netsh, or journalctl. A missing tool is a skip, not a clean bill.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner import runner as R


AUDIT_XML = """<Events xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
<System>
<Provider Name="Microsoft-Windows-Security-Auditing"/>
<EventID>4625</EventID>
<Level>0</Level>
<TimeCreated SystemTime="2026-10-16T20:01:00.0000000Z"/>
</System>
<EventData>
<Data>bad password</Data>
</EventData>
</Event>
</Events>"""

NETSH = """
Domain Profile Settings:
----------------------------------------------------------------------
State                                 ON
Private Profile Settings:
----------------------------------------------------------------------
State                                 ON
Public Profile Settings:
----------------------------------------------------------------------
State                                 OFF
"""


class AttackLabelTest(unittest.TestCase):
    def test_failed_logon_carries_brute_force(self):
        with mock.patch.object(R.sys, "platform", "win32"), \
             mock.patch.object(R, "_wevtutil_query", return_value=AUDIT_XML):
            out = R._eventlog_tail()
        self.assertIn("(4625) [T1110]", out)

    def test_autorun_change_carries_persistence(self):
        tmp = tempfile.mkdtemp()

        def fake(key):
            if key.endswith("Services"):
                return {}, ["HKLM\\x\\Dhcp"]
            if key.endswith("Run"):
                return {"Bad": "C:\\b.exe"}, []
            return {}, []

        with mock.patch.object(R.sys, "platform", "win32"):
            with mock.patch.object(R, "_reg_query", side_effect=fake):
                R._registry_watch(tmp)
            def fake2(key):
                if key.endswith("Services"):
                    return {}, ["HKLM\\x\\Dhcp"]
                if key.endswith("Run"):
                    return {"Bad": "C:\\c.exe"}, []
                return {}, []
            with mock.patch.object(R, "_reg_query", side_effect=fake2):
                second = R._registry_watch(tmp)
        self.assertIn("[T1547.001]", second)
        self.assertIn("changed", second)

    def test_canary_edit_and_delete_are_labeled(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        path = os.path.join(tmp, "canaries", "passwords.txt")
        with open(path, "ab") as fh:
            fh.write(b"\ntouched\n")
        edited = R._canary_watch(tmp)
        self.assertIn("[T1552.001]", edited)
        os.remove(path)
        gone = R._canary_watch(tmp)
        self.assertIn("[T1070.004]", gone)

    def test_trip_is_filed_once_and_again_after_restore(self):
        tmp = tempfile.mkdtemp()
        R._canary_watch(tmp)
        path = os.path.join(tmp, "canaries", "passwords.txt")
        with open(path, "rb") as fh:
            original = fh.read()
        with open(path, "ab") as fh:
            fh.write(b"\ntouched\n")
        R._canary_watch(tmp)
        R._canary_watch(tmp)
        filed = R._senses.load_alerts(tmp, sensor="canary")
        self.assertEqual(len(filed), 1)
        self.assertEqual(filed[0]["detail"]["attack"], "T1552.001")
        with open(path, "wb") as fh:
            fh.write(original)
        R._canary_watch(tmp)
        with open(path, "ab") as fh:
            fh.write(b"\nagain\n")
        R._canary_watch(tmp)
        filed = R._senses.load_alerts(tmp, sensor="canary")
        self.assertEqual(len(filed), 2)


class FreshLineTest(unittest.TestCase):
    def test_first_look_is_a_baseline_and_a_new_line_files_once(self):
        tmp = tempfile.mkdtemp()
        line = "Failed password for root [T1110]"
        R._file_fresh_lines(tmp, "hostlog", line + "\nkernel: error: disk full")
        self.assertEqual(R._senses.load_alerts(tmp, sensor="hostlog"), [])
        R._file_fresh_lines(tmp, "hostlog", line)
        R._file_fresh_lines(tmp, "hostlog", line + "\nMar 1 sudo: bob [T1548.003]")
        filed = R._senses.load_alerts(tmp, sensor="hostlog")
        self.assertEqual(len(filed), 1)
        self.assertEqual(filed[0]["detail"]["attack"], "T1548.003")

    def test_registry_quiet_look_is_not_an_alert(self):
        tmp = tempfile.mkdtemp()
        R._file_registry_lines(tmp, ["(no changes since last look)"])
        R._file_registry_lines(tmp, [
            r"+ HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\evil = calc [T1547.001]",
        ])
        filed = R._senses.load_alerts(tmp, sensor="registry")
        self.assertEqual(len(filed), 1)
        self.assertNotIn("calc", filed[0]["title"])
        self.assertEqual(filed[0]["detail"]["attack"], "T1547.001")


class FirewallParseTest(unittest.TestCase):
    def test_netsh_off_profile_is_labeled(self):
        line = R._parse_netsh_profiles(NETSH)
        self.assertIn("Domain=ON", line)
        self.assertIn("Public=OFF", line)
        self.assertIn("[T1562.004]", line)

    def test_netsh_garbage_is_unreadable(self):
        self.assertIsNone(R._parse_netsh_profiles("nope"))
        self.assertIsNone(R._parse_netsh_profiles(""))

    def test_ufw(self):
        self.assertIn("inactive", R._parse_ufw("Status: inactive"))
        self.assertIn("[T1562.004]", R._parse_ufw("Status: inactive"))
        self.assertNotIn("T1562", R._parse_ufw("Status: active"))
        self.assertIsNone(R._parse_ufw("usage"))

    def test_iptables_accept_is_labeled_drop_is_not(self):
        accept = R._parse_iptables_policy("-P INPUT ACCEPT\n-P OUTPUT ACCEPT\n")
        self.assertIn("INPUT=ACCEPT", accept)
        self.assertIn("[T1562.004]", accept)
        drop = R._parse_iptables_policy("-P INPUT DROP\n-P OUTPUT ACCEPT\n")
        self.assertNotIn("T1562", drop)

    def test_socketfilterfw(self):
        off = R._parse_socketfilterfw("Firewall is disabled. (State = 0)")
        on = R._parse_socketfilterfw("Firewall is enabled. (State = 1)")
        self.assertIn("off", off)
        self.assertIn("[T1562.004]", off)
        self.assertIn("=on", on)
        self.assertNotIn("T1562", on)

    def test_command_failure_is_none_not_off(self):
        with mock.patch.object(R.subprocess, "run", side_effect=OSError("no")):
            self.assertIsNone(R._run_text(["netsh"]))
        proc = mock.Mock(returncode=1, stdout="Status: inactive")
        with mock.patch.object(R.subprocess, "run", return_value=proc):
            self.assertIsNone(R._run_text(["ufw", "status"]))


class HostLogTest(unittest.TestCase):
    def test_windows_is_none(self):
        with mock.patch.object(R.sys, "platform", "win32"):
            self.assertIsNone(R._host_log_tail())

    def test_marks_auth_and_skips_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "auth.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("session opened for user bob\n")
                fh.write("Failed password for root from 10.0.0.8\n")
            with mock.patch.object(R, "_AUTH_LOG_PATHS", (path,)), \
                 mock.patch.object(R, "_SYS_LOG_PATHS", ()), \
                 mock.patch.object(R.sys, "platform", "linux"):
                out = R._host_log_tail()
        self.assertIn("Failed password", out)
        self.assertIn("[T1110]", out)
        self.assertNotIn("session opened", out)

    def test_sudo_is_labeled_and_a_plain_error_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = os.path.join(tmp, "auth.log")
            sys_log = os.path.join(tmp, "syslog")
            with open(auth, "w", encoding="utf-8") as fh:
                fh.write("sudo: bob : TTY=pts/0 ; COMMAND=/bin/id\n")
            with open(sys_log, "w", encoding="utf-8") as fh:
                fh.write("kernel: error: disk full\n")
            with mock.patch.object(R, "_AUTH_LOG_PATHS", (auth,)), \
                 mock.patch.object(R, "_SYS_LOG_PATHS", (sys_log,)), \
                 mock.patch.object(R.sys, "platform", "linux"):
                out = R._host_log_tail()
        self.assertIn("[T1548.003]", out)
        self.assertIn("disk full", out)
        self.assertNotIn("disk full [T", out)


class FirewallWatchTest(unittest.TestCase):
    def test_flip_is_a_change_and_unreadable_keeps_the_baseline(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.object(R, "_firewall_posture",
                               return_value="firewall: linux ufw=active"):
            first = R._firewall_watch(tmp)
            second = R._firewall_watch(tmp)
        self.assertIn("baseline", first)
        self.assertNotIn("changed", second)
        self.assertNotIn("baseline", second)
        with mock.patch.object(
                R, "_firewall_posture",
                return_value="firewall: linux ufw=inactive [T1562.004]"):
            third = R._firewall_watch(tmp)
        self.assertIn("(changed)", third)
        self.assertIn("[T1562.004]", third)
        snap = os.path.join(tmp, "oracle-firewall.json")
        with open(snap, encoding="utf-8") as fh:
            saved = json.load(fh)["line"]
        with mock.patch.object(R, "_firewall_posture", return_value=None):
            self.assertIsNone(R._firewall_watch(tmp))
        with open(snap, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["line"], saved)

    def test_flip_is_filed_once(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.object(R, "_firewall_posture",
                               return_value="firewall: linux ufw=active"):
            R._firewall_watch(tmp)
        self.assertEqual(R._senses.load_alerts(tmp, sensor="firewall"), [])
        off = "firewall: linux ufw=inactive [T1562.004]"
        with mock.patch.object(R, "_firewall_posture", return_value=off):
            R._firewall_watch(tmp)
            R._firewall_watch(tmp)
        filed = R._senses.load_alerts(tmp, sensor="firewall")
        self.assertEqual(len(filed), 1)
        self.assertEqual(filed[0]["severity"], "high")
        self.assertEqual(filed[0]["detail"]["attack"], "T1562.004")

    def test_nothing_readable_is_none_not_clean(self):
        with mock.patch.object(R, "_AUTH_LOG_PATHS", ("/no/such/auth",)), \
             mock.patch.object(R, "_SYS_LOG_PATHS", ("/no/such/syslog",)), \
             mock.patch.object(R.sys, "platform", "darwin"):
            self.assertIsNone(R._host_log_tail())

    def test_context_says_unreadable(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.object(R.sys, "platform", "linux"), \
             mock.patch.object(R, "_host_log_tail", return_value=None), \
             mock.patch.object(R, "_firewall_posture", return_value=None), \
             mock.patch.object(R, "_canary_watch", return_value=""):
            blob = R.oracle_context(tmp)
        self.assertIn("Host log tail: unreadable", blob)
        self.assertIn("Firewall posture: unreadable", blob)
        self.assertNotIn("Windows Event Log", blob)

    def test_watch_off_skips_both(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.object(R.sys, "platform", "linux"), \
             mock.patch.object(R, "_host_log_tail") as host, \
             mock.patch.object(R, "_firewall_posture") as fw:
            blob = R.oracle_context(tmp, watch=False)
        host.assert_not_called()
        fw.assert_not_called()
        self.assertNotIn("Host log tail", blob)
        self.assertNotIn("Firewall posture", blob)


class ArtifactScanTest(unittest.TestCase):
    def test_unchanged_files_are_not_scanned(self):
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "script.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("print(1)\n")
            before = R._work_files(work)
            with mock.patch.object(R, "_yara_hits") as yara, \
                 mock.patch.object(R, "_clam_hits") as clam:
                self.assertEqual(R._artifact_findings(work, before, {}), [])
            yara.assert_not_called()
            clam.assert_not_called()

    def test_oversize_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "big.bin")
            with open(path, "wb") as fh:
                fh.write(b"x" * 32)
            before = {}
            with mock.patch.object(R, "_ARTIFACT_MAX_BYTES", 8), \
                 mock.patch.object(R, "_yara_hits") as yara:
                self.assertEqual(R._artifact_findings(work, before, {}), [])
            yara.assert_not_called()

    def test_opt_out_scans_nothing(self):
        with tempfile.TemporaryDirectory() as work:
            with open(os.path.join(work, "a.txt"), "w", encoding="utf-8") as fh:
                fh.write("eval(base64_decode('x'))\n")
            with mock.patch.object(R, "_yara_hits") as yara:
                out = R._artifact_findings(
                    work, {}, {"inference": {"artifact_scan": False}})
            yara.assert_not_called()
            self.assertEqual(out, [])

    def test_yara_hit_is_labeled(self):
        def fake_run(argv, **kwargs):
            return mock.Mock(returncode=0, stdout="hp_webshell " + argv[-1] + "\n")

        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "drop.php")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("<?php system($_GET['c']);\n")
            with mock.patch.object(R.shutil, "which",
                                   side_effect=lambda n: "/usr/bin/yr" if n == "yr" else None), \
                 mock.patch.object(R.subprocess, "run", side_effect=fake_run):
                hits = R._artifact_findings(work, {}, {})
        self.assertEqual(len(hits), 1)
        self.assertIn("yara hp_webshell drop.php [T1505.003]", hits[0])

    def test_operator_rules_file_is_what_gets_scanned(self):
        seen = {}

        def fake_run(argv, **kwargs):
            with open(argv[-2], encoding="utf-8") as fh:
                seen["rules"] = fh.read()
            return mock.Mock(returncode=0, stdout="hp_custom " + argv[-1] + "\n")

        with tempfile.TemporaryDirectory() as tmp:
            rules = os.path.join(tmp, "local.yar")
            with open(rules, "w", encoding="utf-8") as fh:
                fh.write("rule hp_custom { condition: true }\n")
            work = os.path.join(tmp, "work")
            os.makedirs(work)
            with open(os.path.join(work, "drop.bin"), "w", encoding="utf-8") as fh:
                fh.write("x")
            cfg = {"inference": {"yara_rules": rules}}
            with mock.patch.object(R.shutil, "which",
                                   side_effect=lambda n: "/usr/bin/yr" if n == "yr" else None), \
                 mock.patch.object(R.subprocess, "run", side_effect=fake_run):
                hits = R._artifact_findings(work, {}, cfg)
        self.assertIn("hp_custom", seen["rules"])
        self.assertIn("[T1204.002]", hits[0])

    def test_missing_rules_file_falls_back(self):
        self.assertIn("hp_webshell", R._yara_rules_text(
            {"inference": {"yara_rules": "/no/such/rules.yar"}}))

    def test_note_reaches_the_oracle_without_the_output(self):
        note = R._artifact_note(
            "job1",
            {"kind": "exec", "script": "print(1)\n"},
            {"exit_code": 0, "stdout": "secret-output",
             "artifact_scan": ["yara hp_webshell drop.php [T1505.003]"]})
        self.assertNotIn("secret-output", json.dumps(note))
        self.assertIsNone(R._artifact_note("job1", {}, {"artifact_scan": []}))
        with tempfile.TemporaryDirectory() as base:
            R.save_retained(base, "job1", note)
            with mock.patch.object(R.sys, "platform", "linux"), \
                 mock.patch.object(R, "_host_log_tail", return_value=""), \
                 mock.patch.object(R, "_firewall_watch", return_value=""), \
                 mock.patch.object(R, "_canary_watch", return_value=""):
                blob = R.oracle_context(base, watch=False)
        self.assertIn("artifact scan", blob)
        self.assertIn("hp_webshell", blob)
        self.assertNotIn("secret-output", blob)

    def test_missing_tools_add_nothing(self):
        with tempfile.TemporaryDirectory() as work:
            with open(os.path.join(work, "a.txt"), "w", encoding="utf-8") as fh:
                fh.write("hello\n")
            with mock.patch.object(R.shutil, "which", return_value=None):
                self.assertEqual(R._artifact_findings(work, {}, {}), [])

    def test_clam_daemon_down_is_not_a_hit(self):
        proc = mock.Mock(returncode=2, stdout="")
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "a.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hello\n")
            with mock.patch.object(R.shutil, "which",
                                   side_effect=lambda n: "/usr/bin/clamdscan" if n == "clamdscan" else None), \
                 mock.patch.object(R.subprocess, "run", return_value=proc):
                self.assertEqual(R._clam_hits(work, [path]), [])

    def test_clam_found_line(self):
        with tempfile.TemporaryDirectory() as work:
            proc = mock.Mock(
                returncode=1,
                stdout=os.path.join(work, "a.txt")
                + ": Eicar-Test-Signature FOUND\n")
            with mock.patch.object(R.shutil, "which", return_value="clamdscan"), \
                 mock.patch.object(R.subprocess, "run", return_value=proc):
                hits = R._clam_hits(work, [os.path.join(work, "a.txt")])
        self.assertEqual(hits, ["clamav Eicar-Test-Signature a.txt [T1204.002]"])

    def test_execute_job_keeps_the_exit_code(self):
        from runner.runner import execute_job
        proc = mock.Mock()
        proc.pid = 3
        proc.returncode = 0
        proc.communicate.return_value = (b"ok\n", b"")
        with tempfile.TemporaryDirectory() as base:
            job = {"kind": "exec", "job_id": "scan1", "script": "print(1)\n",
                   "interpreter": ["python3"]}
            with mock.patch.object(R.subprocess, "Popen", return_value=proc), \
                 mock.patch.object(R, "_artifact_findings",
                                   return_value=["yara hp_webshell drop.php [T1505.003]"]):
                result = execute_job({}, job, base)
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["artifact_scan"],
                             ["yara hp_webshell drop.php [T1505.003]"])
            filed = R._senses.load_alerts(base, sensor="artifact")
            self.assertEqual(len(filed), 1)
            self.assertEqual(filed[0]["detail"]["attack"], "T1505.003")
            self.assertTrue(filed[0]["title"].startswith("scan1:"))

    def test_poll_look_files_a_trip_without_the_chat(self):
        tmp = tempfile.mkdtemp()
        R._local_watch({}, tmp)
        path = os.path.join(tmp, "canaries", "api-keys.txt")
        with open(path, "ab") as fh:
            fh.write(b"\nx\n")
        R._local_watch({}, tmp)
        filed = R._senses.load_alerts(tmp, sensor="canary")
        self.assertEqual(len(filed), 1)

    def test_watch_opt_out_does_not_plant(self):
        tmp = tempfile.mkdtemp()
        R._local_watch({"inference": {"watch_system": False}}, tmp)
        self.assertFalse(os.path.isdir(os.path.join(tmp, "canaries")))
        self.assertEqual(R._senses.load_alerts(tmp), [])


class PromptTest(unittest.TestCase):
    def test_prompts_name_the_new_sections(self):
        for prompt in (R.ASK_SYSTEM, R.ASK_AGENT_SYSTEM):
            self.assertIn("Host log tail", prompt)
            self.assertIn("Firewall posture", prompt)
            self.assertIn("AV posture", prompt)
            self.assertIn("artifact scan", prompt)


class AvPostureTest(unittest.TestCase):
    def test_missing_signatures_are_unreadable(self):
        with mock.patch.object(R, "_CLAM_SIG_PATHS", ("/no/such/daily.cvd",)), \
             mock.patch.object(R.sys, "platform", "linux"):
            self.assertIsNone(R._av_posture())

    def test_stale_signatures_are_labeled_and_filed_once(self):
        tmp = tempfile.mkdtemp()
        sig = os.path.join(tmp, "daily.cvd")
        with open(sig, "w", encoding="utf-8") as fh:
            fh.write("x")
        old = time.time() - (8 * 86400)
        os.utime(sig, (old, old))
        with mock.patch.object(R, "_CLAM_SIG_PATHS", (sig,)), \
             mock.patch.object(R.sys, "platform", "linux"):
            first = R._av_watch(tmp)
            second = R._av_watch(tmp)
        self.assertIn("stale", first)
        self.assertIn("[T1562.001]", first)
        self.assertIn("baseline", first)
        self.assertNotIn("changed", second)
        self.assertEqual(R._senses.load_alerts(tmp, sensor="av"), [])
        fresh = time.time()
        os.utime(sig, (fresh, fresh))
        with mock.patch.object(R, "_CLAM_SIG_PATHS", (sig,)), \
             mock.patch.object(R.sys, "platform", "linux"):
            third = R._av_watch(tmp)
            fourth = R._av_watch(tmp)
        self.assertIn("(changed)", third)
        self.assertNotIn("changed", fourth)
        filed = R._senses.load_alerts(tmp, sensor="av")
        self.assertEqual(len(filed), 1)
        self.assertEqual(filed[0]["severity"], "info")

    def test_stopped_defender_is_labeled(self):
        text = "SERVICE_NAME: WinDefend\n        STATE              : 1  STOPPED\n"
        self.assertIn("[T1562.001]", R._parse_defender_query(text))
        running = "SERVICE_NAME: WinDefend\n        STATE              : 4  RUNNING\n"
        self.assertEqual(
            R._parse_defender_query(running),
            "av: windows defender=running")
        self.assertIsNone(R._parse_defender_query(""))


if __name__ == "__main__":
    unittest.main()
