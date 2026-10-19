"""Windows watch seams, driven with a fake platform.

reg.exe and wevtutil never run. The parser, the diff, and the event
XML collector are what get pinned: a baseline, an added value, a
removed value, a changed hash, and a tagged audit event.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr

_NS = "http://schemas.microsoft.com/win/2004/08/events/event"

_EVENT_XML = """<?xml version="1.0"?>
<Events xmlns="%s">
  <Event>
    <System>
      <Provider Name="Security"/>
      <EventID>4625</EventID>
      <Level>2</Level>
      <TimeCreated SystemTime="2026-01-01T00:00:00Z"/>
    </System>
    <EventData>
      <Data>alice</Data>
      <Data>bad password</Data>
    </EventData>
  </Event>
  <Event>
    <System>
      <Provider Name="App"/>
      <EventID>nope</EventID>
      <Level>9</Level>
      <TimeCreated>yesterday</TimeCreated>
    </System>
  </Event>
</Events>
""" % _NS


def _reg_out(key, values, subkeys=()):
    lines = [key]
    for name, data in values:
        lines.append(f"    {name}    REG_SZ    {data}")
    for sub in subkeys:
        lines.append(key + "\\" + sub)
    return "\n".join(lines) + "\n"


class RegistryParseTest(unittest.TestCase):
    def test_reg_query_splits_values_and_drops_the_key_itself(self):
        key = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        text = _reg_out(key, [("OneDrive", "onedrive.exe"), ("Empty", "")],
                        ("Sub",))
        # A two-field line is a value with no data.
        text += "    Flag    REG_DWORD\n"
        proc = mock.Mock(returncode=0, stdout=text)
        with mock.patch.object(rr.subprocess, "run", return_value=proc):
            values, subkeys = rr._reg_query(key)
        self.assertEqual(values["OneDrive"], "onedrive.exe")
        self.assertEqual(values["Empty"], "")
        self.assertEqual(values["Flag"], "")
        self.assertEqual(subkeys, [key + r"\Sub"])

    def test_a_failed_reg_query_is_none(self):
        proc = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(rr.subprocess, "run", return_value=proc):
            self.assertIsNone(rr._reg_query(r"HKLM\Nope"))
        with mock.patch.object(rr.subprocess, "run",
                               side_effect=OSError("no reg")):
            self.assertIsNone(rr._reg_query(r"HKLM\Nope"))

    def test_attack_tags_are_only_the_known_locations(self):
        self.assertEqual(rr._reg_attack(r"HKLM\...\Winlogon"), "T1547.004")
        self.assertEqual(rr._reg_attack(r"HKCU\...\Run"), "T1547.001")
        self.assertEqual(rr._reg_attack(r"HKLM\Somewhere\Else"), "")

    def test_a_snapshot_keeps_winlogon_down_to_the_interesting_names(self):
        def fake_run(cmd, **_kw):
            key = cmd[2]
            if key.endswith("Services"):
                return mock.Mock(returncode=0, stdout=_reg_out(
                    key, [], ("Spooler", "W32Time")))
            if "Winlogon" in key:
                return mock.Mock(returncode=0, stdout=_reg_out(
                    key, [("Shell", "explorer.exe"), ("Noise", "x")]))
            return mock.Mock(returncode=0, stdout=_reg_out(
                key, [("OneDrive", "od.exe")]))
        with mock.patch.object(rr.subprocess, "run", side_effect=fake_run):
            snap = rr._registry_snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(snap["services"]["count"], 2)
        win = [k for k in snap["keys"] if "Winlogon" in k and "\x00" not in k]
        self.assertEqual(list(snap["keys"][win[0] + "\x00raw"]), ["Shell"])

    def test_watch_is_none_off_windows(self):
        if sys.platform == "win32":
            self.skipTest("Windows reads the registry")
        self.assertIsNone(rr._registry_watch("/tmp"))

    def test_the_first_look_records_a_baseline_and_the_second_diffs(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = tmp.name
        run_key = rr._REG_WATCH_KEYS[0]

        def fake_run(cmd, **_kw):
            key = cmd[2]
            if key.endswith("Services"):
                return mock.Mock(returncode=0, stdout=_reg_out(
                    key, [], ("Spooler",)))
            if key == run_key:
                return mock.Mock(returncode=0, stdout=_reg_out(
                    key, [("OneDrive", "od.exe")]))
            return mock.Mock(returncode=0, stdout=_reg_out(key, []))

        with mock.patch.object(rr, "sys") as plat, \
                mock.patch.object(rr.subprocess, "run", side_effect=fake_run):
            plat.platform = "win32"
            first = rr._registry_watch(base)
        self.assertIn("baseline recorded", first)
        self.assertTrue(os.path.isfile(
            os.path.join(base, "oracle-regwatch.json")))

        def fake_run2(cmd, **_kw):
            key = cmd[2]
            if key.endswith("Services"):
                return mock.Mock(returncode=0, stdout=_reg_out(
                    key, [], ("Spooler", "Extra")))
            if key == run_key:
                return mock.Mock(returncode=0, stdout=_reg_out(
                    key, [("OneDrive", "CHANGED"), ("New", "n.exe")]))
            return mock.Mock(returncode=0, stdout=_reg_out(key, []))

        with mock.patch.object(rr, "sys") as plat, \
                mock.patch.object(rr.subprocess, "run",
                                  side_effect=fake_run2), \
                mock.patch.object(rr, "_file_registry_lines"):
            plat.platform = "win32"
            second = rr._registry_watch(base)
        self.assertIn("+ ", second)
        self.assertIn("changed", second)
        self.assertIn("services:", second)
        self.assertIn("T1547.001", second)

    def test_an_unreadable_services_key_is_none(self):
        with mock.patch.object(rr, "sys") as plat, \
                mock.patch.object(rr, "_registry_snapshot", return_value=None):
            plat.platform = "win32"
            self.assertIsNone(rr._registry_watch("/tmp/nope"))


class EventLogTest(unittest.TestCase):
    def test_eventlog_is_none_off_windows(self):
        if sys.platform == "win32":
            self.skipTest("Windows reads the event log")
        self.assertIsNone(rr._eventlog_tail())

    def test_a_wevtutil_failure_is_none_and_empty_stdout_is_empty(self):
        with mock.patch.object(rr.subprocess, "run",
                               side_effect=OSError("gone")):
            self.assertIsNone(rr._wevtutil_query("System", "*", 1))
        proc = mock.Mock(returncode=1, stdout="nope")
        with mock.patch.object(rr.subprocess, "run", return_value=proc):
            self.assertIsNone(rr._wevtutil_query("System", "*", 1))
        proc = mock.Mock(returncode=0, stdout="")
        with mock.patch.object(rr.subprocess, "run", return_value=proc):
            self.assertEqual(rr._wevtutil_query("System", "*", 1), "")

    def test_the_tail_tags_a_failed_logon_and_skips_junk_xml(self):
        def fake_query(logname, _xpath, _count, timeout=15):
            if logname == "System":
                return _EVENT_XML
            if logname == "Application":
                return "<not xml"
            return ""
        with mock.patch.object(rr, "sys") as plat, \
                mock.patch.object(rr, "_wevtutil_query",
                                  side_effect=fake_query), \
                mock.patch.object(rr, "_file_fresh_lines"):
            plat.platform = "win32"
            blob = rr._eventlog_tail(base_dir="/tmp")
        self.assertIn("T1110", blob)
        self.assertIn("Security", blob)
        self.assertIn("alice", blob)

    def test_every_channel_unreadable_is_none(self):
        with mock.patch.object(rr, "sys") as plat, \
                mock.patch.object(rr, "_wevtutil_query", return_value=None):
            plat.platform = "win32"
            self.assertIsNone(rr._eventlog_tail())


if __name__ == "__main__":
    unittest.main()
