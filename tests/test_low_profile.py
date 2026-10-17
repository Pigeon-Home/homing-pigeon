"""Low-profile senses: ATT&CK labels, host-log tail, firewall posture,
and the on-demand artifact scan. No test starts yara, clamdscan,
netsh, or journalctl. A missing tool is a skip, not a clean bill.
"""

import os
import sys
import tempfile
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
        self.assertNotIn("session opened", out)

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


class PromptTest(unittest.TestCase):
    def test_prompts_name_the_new_sections(self):
        for prompt in (R.ASK_SYSTEM, R.ASK_AGENT_SYSTEM):
            self.assertIn("Host log tail", prompt)
            self.assertIn("Firewall posture", prompt)
            self.assertIn("artifact scan", prompt)


if __name__ == "__main__":
    unittest.main()
