"""Sysmon Feed: the example sense that feeds Sysmon Event ID 1.

Pins the Sysmon Feed example
(runner/extensions/sysmon-feed/): the manifest through
the real extension loader, the pure parse_event() over
BOTH artifact shapes (Sysmon for Linux XML on a syslog
line, and Windows Sysmon exported as text blocks), the
read_new_events() reader plumbing -- including a Windows
block held whole across a chunk boundary in the reader
state's partial entry -- and the pure decide() episode
machine: an episode files once per (signal, image,
parent_image, rule-matched detail).

The fixtures are synthetic, crafted from the documented
field layout: Sysmon for Linux never ran in the
measurement sandbox (the host denied BPF), so no captured
sample exists. No live Sysmon anywhere.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(
    REPO, "runner", "extensions", "sysmon-feed")
FIXTURES = os.path.join(EXAMPLE_DIR, "fixtures")
B64 = "QUJD" * 30


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "sysmon_feed_example",
        os.path.join(EXAMPLE_DIR, "sysmon_feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SM = _load_example_module()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _xml(image="/usr/bin/ls", command="ls -la", eid=1,
         parent="/bin/bash", user="alice"):
    return (
        "Oct 19 03:00:01 host sysmon[214]: <Event><System>"
        f"<EventID>{eid}</EventID></System><EventData>"
        '<Data Name="UtcTime">2026-10-19 03:00:01.000</Data>'
        '<Data Name="ProcessId">4101</Data>'
        f'<Data Name="Image">{image}</Data>'
        f'<Data Name="CommandLine">{command}</Data>'
        f'<Data Name="User">{user}</Data>'
        '<Data Name="ParentProcessId">900</Data>'
        f'<Data Name="ParentImage">{parent}</Data>'
        "</EventData></Event>")


def _block(image=r"C:\Windows\System32\notepad.exe",
           command="notepad.exe notes.txt", eid=1,
           parent=r"C:\Windows\explorer.exe"):
    return "\n".join([
        "Log Name: Microsoft-Windows-Sysmon/Operational",
        "Source: Microsoft-Windows-Sysmon",
        f"Event ID: {eid}",
        "UtcTime: 2026-10-19 03:00:01.000",
        "ProcessId: 4101",
        f"Image: {image}",
        f"CommandLine: {command}",
        "User: CONTOSO\\alice",
        "ParentProcessId: 900",
        f"ParentImage: {parent}",
        "ParentCommandLine: explorer.exe",
        "Hashes: SHA256=AAAA"])


def _event(image="/usr/bin/ls", command="ls -la",
           parent="/bin/bash"):
    return {"event_id": 1, "image": image,
            "command_line": command, "parent_image": parent,
            "user": "alice"}


def _readings(events):
    return {"now": 1792375201.0, "events": list(events)}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "sysmon_feed")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["sysmon_process_from_temp", "sysmon_encoded_command"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "sysmon-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("sysmon_feed", registry)


class ParseXmlTest(unittest.TestCase):
    def test_linux_xml_event_parses_the_field_model(self):
        ev = SM.parse_event(_xml(image="/tmp/.cache/update",
                                 command="/tmp/.cache/update --quiet"))
        self.assertEqual(ev["event_id"], 1)
        self.assertEqual(ev["image"], "/tmp/.cache/update")
        self.assertEqual(ev["command_line"],
                         "/tmp/.cache/update --quiet")
        self.assertEqual(ev["process_id"], 4101)
        self.assertEqual(ev["parent_image"], "/bin/bash")
        self.assertEqual(ev["user"], "alice")
        self.assertEqual(ev["utc_time"], "2026-10-19 03:00:01.000")

    def test_other_event_ids_parse_to_nothing(self):
        self.assertIsNone(SM.parse_event(_xml(eid=3)))
        self.assertIsNone(SM.parse_event(_xml(eid=11)))

    def test_malformed_xml_answers_none(self):
        for text in ("", "hello world",
                     "<Event><System><EventID>1</EventID>",
                     "<Event><EventData></EventData></Event>"):
            self.assertIsNone(SM.parse_event(text), text)
        self.assertIsNone(SM.parse_event(None))
        self.assertIsNone(SM.parse_event(42))


class ParseTextTest(unittest.TestCase):
    def test_windows_text_block_parses_the_same_model(self):
        ev = SM.parse_event(_block(
            image=r"C:\Users\alice\AppData\Local\Temp\drop.exe",
            command=r"C:\Users\alice\AppData\Local\Temp\drop.exe /s"))
        self.assertEqual(ev["event_id"], 1)
        self.assertEqual(ev["image"],
                         r"C:\Users\alice\AppData\Local\Temp\drop.exe")
        self.assertEqual(ev["parent_image"], r"C:\Windows\explorer.exe")
        self.assertEqual(ev["process_id"], 4101)

    def test_block_without_event_id_or_other_id_is_none(self):
        self.assertIsNone(SM.parse_event("Image: C:\\x.exe\n"
                                         "CommandLine: x.exe"))
        self.assertIsNone(SM.parse_event(_block(eid=3)))


class FixtureTest(unittest.TestCase):
    def test_linux_fixture_parses_and_decides(self):
        with open(os.path.join(FIXTURES, "synthetic-linux-sysmon.log"),
                  encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        events = [ev for ev in (SM.parse_event(ln) for ln in lines)
                  if ev is not None]
        self.assertEqual(len(events), 3)  # ID 3 and noise drop out
        alerts, _state = SM.decide(_readings(events), _manifest(), {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["sysmon_process_from_temp",
                          "sysmon_encoded_command"])

    def test_windows_fixture_blocks_parse_and_decide(self):
        path = os.path.join(FIXTURES, "synthetic-windows-sysmon.txt")
        with open(path, encoding="utf-8") as fh:
            texts, rem = SM._split_text(fh.read(), flush=True)
        self.assertEqual(rem, "")
        events = [ev for ev in (SM.parse_event(t) for t in texts)
                  if ev is not None]
        self.assertEqual(len(events), 3)
        alerts, _state = SM.decide(_readings(events), _manifest(), {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["sysmon_process_from_temp",
                          "sysmon_encoded_command"])


class ReaderTest(unittest.TestCase):
    def test_tails_xml_lines_incrementally(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysmon.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_xml() + "\n")
                fh.write(_xml(image="/tmp/x") + "\n")
            events, reader = SM.read_new_events([path], {})
            self.assertEqual(len(events), 2)
            self.assertEqual(reader[path]["offset"],
                             os.path.getsize(path))
            self.assertEqual(reader[path]["partial"], "")
            events, reader = SM.read_new_events([path], reader)
            self.assertEqual(events, [])
            missing = os.path.join(d, "nope.log")
            kept = {missing: {"inode": 4242, "offset": 99,
                              "partial": "half"}}
            events, new_reader = SM.read_new_events([missing], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[missing], kept[missing])

    def test_partial_xml_line_is_held_across_chunks(self):
        line = _xml(image="/tmp/held")
        cut = len(line) // 2
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysmon.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(line[:cut])
            events, reader = SM.read_new_events([path], {})
            self.assertEqual(events, [])
            self.assertEqual(reader[path]["partial"], line[:cut])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line[cut:] + "\n")
            events, _reader = SM.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["image"], "/tmp/held")

    def test_partial_windows_block_is_held_across_chunks(self):
        block = _block(image=r"C:\Users\a\AppData\Local\Temp\d.exe",
                       command="d.exe")
        cut = block.index("CommandLine:")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysmon.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(block[:cut])
            events, reader = SM.read_new_events([path], {})
            self.assertEqual(events, [])
            self.assertEqual(reader[path]["partial"], block[:cut])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(block[cut:] + "\n\n")
            events, reader = SM.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["image"],
                             r"C:\Users\a\AppData\Local\Temp\d.exe")
            self.assertEqual(reader[path]["partial"], "")

    def test_block_header_terminates_the_previous_block(self):
        first = _block()
        second = _block(image=r"C:\Windows\System32\cmd.exe",
                        command="cmd.exe")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysmon.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(first + "\n" + second)  # no blank line
            events, reader = SM.read_new_events([path], {})
            self.assertEqual(len(events), 1)  # second still held
            self.assertIn("cmd.exe", reader[path]["partial"])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("\n\n")
            events, _reader = SM.read_new_events([path], reader)
            self.assertEqual(len(events), 1)

    def test_an_unreadable_file_keeps_its_entry(self):
        # Queue A refill: read_new_events' open-failure leg
        # (coverage run 40189711740: 4 lines; the same leg
        # across the tailing senses). A missing or
        # unreadable file yields no events and keeps its
        # previous entry -- partial line included; a
        # directory stats fine but cannot be opened as a
        # file.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysmon.log")
            os.mkdir(path)
            kept = {path: {"inode": os.stat(path).st_ino,
                           "offset": 0, "partial": "<Event>"}}
            events, new_reader = SM.read_new_events([path], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[path], kept[path])

    def test_shrunk_file_restarts_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysmon.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_xml() + "\n" + _xml() + "\n")
            _events, reader = SM.read_new_events([path], {})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_xml(image="/tmp/new") + "\n")
            events, _reader = SM.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["image"], "/tmp/new")


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None):
        return SM.decide(readings, _manifest(),
                         state if state is not None else {})

    def test_temp_paths_fire_medium(self):
        for image in ("/tmp/x/run", "/dev/shm/run", "/var/tmp/run",
                      r"C:\Users\bob\AppData\Local\Temp\run.exe",
                      r"C:\staging\%TEMP%\run.exe"):
            with self.subTest(image=image):
                alerts, _s = self.decide(_readings([_event(image=image)]))
                self.assertEqual(len(alerts), 1)
                self.assertEqual(alerts[0]["signal"],
                                 "sysmon_process_from_temp")
                self.assertEqual(alerts[0]["severity"], "medium")
                self.assertEqual(alerts[0]["sensor"], "sysmon_feed")
                self.assertEqual(alerts[0]["detail"]["image"], image)
                self.assertEqual(alerts[0]["detail"]["parent_image"],
                                 "/bin/bash")

    def test_non_temp_paths_are_quiet(self):
        for image in ("/usr/bin/ls", "/tmpfoo/run",
                      r"C:\Users\bob\Downloads\run.exe",
                      r"C:\Windows\Temp\run.exe"):
            with self.subTest(image=image):
                alerts, _s = self.decide(_readings([_event(image=image)]))
                self.assertEqual(alerts, [])

    def test_encoded_flag_fires_case_insensitively(self):
        for command in ("powershell -enc AAA", "powershell -ENC AAA",
                        "powershell -EncodedCommand AAA"):
            with self.subTest(command=command):
                alerts, _s = self.decide(
                    _readings([_event(command=command)]))
                self.assertEqual([a["signal"] for a in alerts],
                                 ["sysmon_encoded_command"])
                self.assertEqual(alerts[0]["severity"], "medium")

    def test_base64_token_fires_and_short_tokens_do_not(self):
        alerts, _s = self.decide(
            _readings([_event(command=f"python3 -c exec {B64}")]))
        self.assertEqual([a["signal"] for a in alerts],
                         ["sysmon_encoded_command"])
        self.assertEqual(alerts[0]["detail"]["matched"], B64)
        alerts, _s = self.decide(
            _readings([_event(command="echo " + "QUJD" * 10)]))
        self.assertEqual(alerts, [])

    def test_both_rules_fire_on_one_event(self):
        ev = _event(image="/tmp/x", command="powershell -enc AAA")
        alerts, _s = self.decide(_readings([ev]))
        self.assertEqual([a["signal"] for a in alerts],
                         ["sysmon_process_from_temp",
                          "sysmon_encoded_command"])

    def test_episode_files_once_across_passes(self):
        readings = _readings([_event(image="/tmp/x")])
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, _s = self.decide(readings, state=state)
        self.assertEqual(alerts, [])
        # Same image and parent, a new encoded command: new episode.
        ev = _event(image="/tmp/x", command="powershell -enc BBB")
        alerts, _s = self.decide(_readings([ev]), state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["sysmon_encoded_command"])
        # Same temp image, different parent: new episode.
        ev = _event(image="/tmp/x", parent="/usr/bin/cron")
        alerts, _s = self.decide(_readings([ev]), state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["sysmon_process_from_temp"])

    def test_non_id1_and_unusable_events_are_ignored(self):
        readings = {"now": 1.0, "events": [
            None, {}, {"event_id": 3, "image": "/tmp/x"},
            {"event_id": 1}, {"image": "", "command_line": ""},
            _event(image="/tmp/x")]}
        alerts, _s = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, state = self.decide({"now": 1.0, "events": []})
        self.assertEqual(alerts, [])
        self.assertEqual(state, {"filed": {}})

    def test_reader_subdict_is_preserved_and_ignored(self):
        state = {"filed": {}, "_reader": {"/var/log/syslog":
                                          {"inode": 7, "offset": 42,
                                           "partial": ""}}}
        alerts, new_state = self.decide(
            _readings([_event(image="/tmp/x")]), state=state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"], state["_reader"])


class MainTest(unittest.TestCase):
    def test_log_file_fixture_files_both_signals_once(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            fixture = os.path.join(FIXTURES,
                                   "synthetic-windows-sysmon.txt")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = SM.main(["--log-file", fixture,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["sysmon_process_from_temp",
                              "sysmon_encoded_command"])
            # Second pass over the same fixture: episodes filed.
            out = io.StringIO()
            with redirect_stdout(out):
                rc = SM.main(["--log-file", fixture,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(
                SM.main(["--log-file", os.path.join(d, "missing.log"),
                         "--state", state_path]), 2)


class SysmonMainDeliveryTest(unittest.TestCase):
    """Queue A refill: sysmon-feed main's local-delivery
    legs and live defaults (coverage run 40187685363: 8
    lines on both platforms). The contract main's own
    comments state: local delivery that is not set up is
    exit 2; a delivery short of the alert count leaves
    the state unwritten, so the offsets do not advance
    and the next pass re-reads the events; a manifest
    whose tunables are absent or not an object reads as
    the defaults, log paths included.
    """

    ENV = "HP_SYSMAIN_SECRET"

    def _drive(self, d, extra, manifest=None):
        readings = os.path.join(d, "readings.json")
        with open(readings, "w", encoding="utf-8") as fh:
            json.dump(_readings([_event(
                image="/tmp/.cache/update")]), fh)
        state = os.path.join(d, "state.json")
        argv = ["--readings", readings, "--state", state,
                "--secret-env", self.ENV] + extra
        if manifest is not None:
            mpath = os.path.join(d, "extension.json")
            with open(mpath, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            argv += ["--manifest", mpath]
        err = io.StringIO()
        with redirect_stderr(err):
            rc = SM.main(argv)
        return rc, state, err.getvalue()

    def test_local_delivery_success_writes_state(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ[self.ENV] = "ab" * 32
            try:
                rc, state, _err = self._drive(
                    d, ["--local-dir", d])
            finally:
                os.environ.pop(self.ENV, None)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(state))
            inbox = os.path.join(d, "local-inbox")
            self.assertEqual(len(os.listdir(inbox)), 1)

    def test_local_delivery_not_set_up_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ.pop(self.ENV, None)
            rc, state, _err = self._drive(d, ["--local-dir", d])
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state))

    def test_short_delivery_is_exit_2_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = os.path.join(d, "blocker")
            with open(blocker, "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            os.environ[self.ENV] = "ab" * 32
            try:
                rc, state, err = self._drive(
                    d, ["--local-dir", blocker])
            finally:
                os.environ.pop(self.ENV, None)
            self.assertEqual(rc, 2)
            self.assertIn("state not saved", err)
            self.assertFalse(os.path.exists(state))

    def test_a_manifest_without_tunables_uses_live_defaults(self):
        manifest = _manifest()
        manifest.pop("tunables", None)
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            mpath = os.path.join(d, "extension.json")
            with open(mpath, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            err = io.StringIO()
            with redirect_stderr(err):
                rc = SM.main(["--manifest", mpath,
                              "--state", state])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(state))


if __name__ == "__main__":
    unittest.main()
