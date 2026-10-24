"""Crash Watch: the example sense that files crash dumps.

Pins the Crash Watch example (extensions/crash-watch/)
the way test_sky_watcher.py pins Sky Watcher: the manifest
through the real extension loader, the pure decide() state
machine over fixture readings (new dump, repeat inside the
window, repeat aged out of the window, changed file at the
same path), read_live()'s filename-to-binary rule and scan
cap, and one end-to-end run -- producer replays two crashes
of the same binary into the local inbox, the real ingest
files both, and the high-severity crash_repeated wakes the
gate and files a brief.

No live network and no live hardware anywhere: readings are
fixtures, and the end-to-end config has no inference, so the
wake brief is the deterministic fallback.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner import senses as S  # noqa: E402
from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "extensions", "crash-watch")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
CRASH_SECRET = "5c1d9a2e7f4b48a0b6d3e5f7a9c1b2d4" + "e6f8a0b2c4d6e8f0a2b4c6d8e0f2a4b6"

T0 = 1_700_000_000.0
WINDOW = 3600  # the shipped repeat_window_sec


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "crash_watch_example", os.path.join(EXAMPLE_DIR, "crash_watch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CW = _load_example_module()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _file(name="app.dmp", watch_dir="./crashes", size=4096,
          mtime=100.0, binary="app"):
    return {"name": name, "dir": watch_dir, "size": size,
            "mtime": mtime, "binary": binary}


def _readings(files, now=T0, truncated=0):
    return {"now": now, "files": files, "truncated": truncated}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "crash_watch")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["crash_dumped", "crash_repeated"])
        for knob in ("watch_dirs", "repeat_window_sec",
                     "poll_interval_sec", "max_files_per_pass"):
            self.assertIn(knob, clean["tunables"])
        self.assertEqual(clean["tunables"]["watch_dirs"], ["./crashes"])
        self.assertEqual(clean["tunables"]["repeat_window_sec"], 3600)
        self.assertEqual(clean["tunables"]["poll_interval_sec"], 60)
        self.assertEqual(clean["tunables"]["max_files_per_pass"], 1000)
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "crash-watch"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("crash_watch", registry)
        self.assertEqual(registry["crash_watch"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def decide(self, files, state=None, now=T0):
        return CW.decide(_readings(files, now=now), _manifest(),
                         state if state is not None else {})

    def test_new_dump_files_crash_dumped_medium(self):
        alerts, _state = self.decide([_file()])
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "crash_watch")
        self.assertEqual(alert["signal"], "crash_dumped")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"], {
            "binary": "app", "file": "app.dmp", "dir": "./crashes",
            "size": 4096})

    def test_repeat_inside_window_files_crash_repeated_high(self):
        _a, state = self.decide([_file(name="a.dmp", mtime=100.0)])
        alerts, _state = self.decide(
            [_file(name="b.dmp", mtime=200.0)], state=state,
            now=T0 + 600)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["signal"], "crash_repeated")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["binary"], "app")
        self.assertEqual(alert["detail"]["file"], "b.dmp")
        self.assertEqual(alert["detail"]["dir"], "./crashes")
        self.assertEqual(alert["detail"]["size"], 4096)
        self.assertEqual(alert["detail"]["count"], 2)

    def test_two_dumps_of_one_binary_in_one_pass(self):
        alerts, _state = self.decide([
            _file(name="a.dmp", mtime=100.0),
            _file(name="b.dmp", mtime=200.0),
        ])
        self.assertEqual([a["signal"] for a in alerts],
                         ["crash_dumped", "crash_repeated"])
        self.assertEqual([a["severity"] for a in alerts],
                         ["medium", "high"])
        self.assertEqual(alerts[1]["detail"]["count"], 2)

    def test_two_dumps_of_different_binaries_both_dumped(self):
        alerts, _state = self.decide([
            _file(name="a.dmp", binary="app"),
            _file(name="b.dmp", binary="other", mtime=200.0),
        ])
        self.assertEqual([a["signal"] for a in alerts],
                         ["crash_dumped", "crash_dumped"])

    def test_repeat_outside_window_is_a_fresh_dump(self):
        _a, state = self.decide([_file(name="a.dmp", mtime=100.0)])
        alerts, state = self.decide(
            [_file(name="b.dmp", mtime=200.0)], state=state,
            now=T0 + WINDOW + 1)
        self.assertEqual([a["signal"] for a in alerts], ["crash_dumped"])
        # The aged-out event was pruned from the state.
        self.assertEqual(state["events"], [["app", T0 + WINDOW + 1]])

    def test_each_signal_fires_with_its_spec_fields(self):
        # Table-driven: (files, want signal, want severity,
        # want detail items).
        cases = [
            ([_file()], "crash_dumped", "medium",
             {"binary": "app", "file": "app.dmp", "size": 4096}),
            ([_file(name="a.dmp"), _file(name="b.dmp", mtime=200.0)],
             "crash_repeated", "high",
             {"binary": "app", "file": "b.dmp", "count": 2}),
        ]
        for files, signal, severity, detail in cases:
            with self.subTest(signal=signal):
                alerts, _state = self.decide(files)
                alert = alerts[-1]
                self.assertEqual(alert["signal"], signal)
                self.assertEqual(alert["severity"], severity)
                for key, value in detail.items():
                    self.assertEqual(alert["detail"][key], value)

    def test_quiet_cases_file_nothing(self):
        for files in ([], None):
            with self.subTest(files=files):
                readings = _readings(files or [])
                if files is None:
                    readings = {"now": T0}
                alerts, _state = CW.decide(readings, _manifest(), {})
                self.assertEqual(alerts, [])

    def test_same_readings_twice_files_nothing_the_second_time(self):
        readings = _readings([_file()])
        alerts, state = CW.decide(readings, _manifest(), {})
        self.assertEqual(len(alerts), 1)
        alerts2, _state2 = CW.decide(readings, _manifest(), state)
        self.assertEqual(alerts2, [])

    def test_changed_file_at_same_path_refiles(self):
        _a, state = self.decide([_file(size=4096, mtime=100.0)])
        # Same path, changed size and mtime, after the window:
        # a fresh dump overwrote the old one and files again.
        alerts, _state = self.decide(
            [_file(size=8192, mtime=200.0)], state=state,
            now=T0 + WINDOW + 1)
        self.assertEqual([a["signal"] for a in alerts], ["crash_dumped"])
        self.assertEqual(alerts[0]["detail"]["size"], 8192)
        # Changed inside the window: still a new event, so it
        # files as the repeat it is.
        alerts, _state = self.decide(
            [_file(size=8192, mtime=200.0)], state=state, now=T0 + 60)
        self.assertEqual([a["signal"] for a in alerts],
                         ["crash_repeated"])

    def test_events_from_state_drive_the_repeat(self):
        state = {"seen": {}, "events": [["app", T0 - 10]]}
        alerts, _state = self.decide([_file()], state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["crash_repeated"])
        self.assertEqual(alerts[0]["detail"]["count"], 2)

    def test_garbage_state_and_readings_never_raise(self):
        for state in (None, "x", {"seen": [], "events": {}},
                      {"seen": {"p": "nope"}, "events": [["b"]]}):
            with self.subTest(state=state):
                alerts, clean = CW.decide(
                    _readings([_file()]), _manifest(), state)
                self.assertEqual(len(alerts), 1)
                self.assertIn(os.path.join("./crashes", "app.dmp"),
                              clean["seen"])
        alerts, _state = CW.decide(None, _manifest(), {})
        self.assertEqual(alerts, [])

    def test_missing_binary_is_derived_from_the_name(self):
        entry = _file(name="tool.core")
        del entry["binary"]
        alerts, _state = self.decide([entry])
        self.assertEqual(alerts[0]["detail"]["binary"], "tool")


class ReadLiveTest(unittest.TestCase):
    def _manifest_with(self, watch_dir, **tunables):
        manifest = _manifest()
        manifest["tunables"] = dict(manifest["tunables"],
                                    watch_dirs=[watch_dir], **tunables)
        return manifest

    def test_binary_rule(self):
        cases = {
            "app.dmp": "app",
            "app.mdmp": "app",
            "app.core": "app",
            "app.crash": "app",
            "app.exe.dmp": "app.exe",
            "notes.txt": "notes",
            "plainname": "plainname",
        }
        for name, want in cases.items():
            with self.subTest(name=name):
                self.assertEqual(CW._binary_for(name), want)

    def test_scan_lists_dumps_and_skips_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("app.dmp", ".hidden.dmp", "state.json",
                         "data.core"):
                with open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"x" * 10)
            os.makedirs(os.path.join(d, "subdir"))
            readings = CW.read_live(self._manifest_with(d))
        self.assertEqual(readings["truncated"], 0)
        by_name = {f["name"]: f for f in readings["files"]}
        self.assertEqual(sorted(by_name), ["app.dmp", "data.core"])
        self.assertEqual(by_name["app.dmp"]["binary"], "app")
        self.assertEqual(by_name["app.dmp"]["dir"], d)
        self.assertEqual(by_name["app.dmp"]["size"], 10)
        self.assertIn("now", readings)

    def test_missing_dir_is_empty_never_an_error(self):
        readings = CW.read_live(self._manifest_with(
            os.path.join(tempfile.gettempdir(),
                         "crash-watch-no-such-dir-xyz")))
        self.assertEqual(readings["files"], [])
        self.assertEqual(readings["truncated"], 0)

    def test_cap_counts_the_extras_and_they_file_next_pass(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.dmp", "b.dmp", "c.dmp"):
                with open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"dump")
            manifest = self._manifest_with(d, max_files_per_pass=2)
            readings = CW.read_live(manifest)
            self.assertEqual(len(readings["files"]), 2)
            self.assertEqual(readings["truncated"], 1)
            alerts, state = CW.decide(readings, manifest, {})
            self.assertEqual(len(alerts), 2)
            # The file beyond the cap was not marked seen: a
            # later uncapped pass files it as new.
            readings2 = CW.read_live(self._manifest_with(d))
            alerts2, _state = CW.decide(readings2, manifest, state)
            self.assertEqual([a["detail"]["file"] for a in alerts2],
                             ["c.dmp"])


class ProducerTest(unittest.TestCase):
    def test_unreadable_manifest_and_readings_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            self.assertEqual(
                CW.main(["--manifest", os.path.join(d, "nope.json"),
                         "--state", state]), 2)
            self.assertEqual(
                CW.main(["--readings", os.path.join(d, "nope.json"),
                         "--state", state]), 2)

    def test_readings_mode_prints_alerts_and_saves_state(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "readings.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(_readings([_file()]), fh)
            state = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = CW.main(["--readings", path, "--state", state])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["crash_dumped"])
            # A second identical pass prints nothing.
            out = io.StringIO()
            with redirect_stdout(out):
                rc = CW.main(["--readings", path, "--state", state])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")


class CrashFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "crash-watch"))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {"crash-key": CRASH_SECRET},
            "key_policies": {
                "crash-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "crash_watch": {"enabled": True, "key_id": "crash-key",
                                "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def tearDown(self):
        for th in threading.enumerate():
            if th.name == "oracle-brief":
                th.join(timeout=5)
        last = None
        for _ in range(20):
            try:
                self._tmp.cleanup()
                return
            except OSError as exc:
                last = exc
                time.sleep(0.05)
        if last is not None:
            raise last

    # -- helpers ------------------------------------------------------
    def readings_file(self, readings, name="readings.json"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(readings, fh)
        return path

    def run_producer(self, readings, with_secret=True):
        env = {"HOMING_PIGEON_SENSOR_SECRET": CRASH_SECRET} \
            if with_secret else {}
        with unittest.mock.patch.dict(os.environ, env):
            if not with_secret:
                os.environ.pop("HOMING_PIGEON_SENSOR_SECRET", None)
            return CW.main(["--readings", self.readings_file(readings),
                            "--local-dir", self.base,
                            "--key-id", "crash-key",
                            "--state", self.state_path])

    def inbox_names(self):
        inbox = os.path.join(self.base, "local-inbox")
        if not os.path.isdir(inbox):
            return []
        return sorted(os.listdir(inbox))

    def brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def wait_briefs(self, n, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.brief_lines()
            if len(lines) >= n:
                return lines
            time.sleep(0.05)
        self.fail(f"expected {n} brief(s), got {self.brief_lines()}")


class EndToEndTest(CrashFixture):
    def test_two_crashes_file_and_the_repeat_wakes_a_brief(self):
        readings = _readings([
            _file(name="a.dmp", mtime=100.0),
            _file(name="b.dmp", mtime=200.0),
        ])
        rc = self.run_producer(readings)
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 2)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 2)
        self.assertEqual(self.inbox_names(), [])
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 2)
        manifest = _manifest()
        declared = {s["name"]: s["description"]
                    for s in manifest["signals"]}
        by_signal = {}
        for rec in recs:
            self.assertEqual(rec["sensor"], "crash_watch")
            self.assertEqual(rec["source"], "local")
            self.assertEqual(rec["extension"], "crash_watch")
            self.assertEqual(rec["extension_version"], "0.1.0")
            self.assertEqual(rec["signal_description"],
                             declared[rec["signal"]])
            by_signal[rec["signal"]] = rec
        self.assertEqual(sorted(by_signal),
                         ["crash_dumped", "crash_repeated"])
        self.assertEqual(by_signal["crash_dumped"]["severity"], "medium")
        self.assertEqual(by_signal["crash_repeated"]["severity"], "high")
        # Only the high signal wakes; with no inference configured
        # the brief is the deterministic fallback.
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "crash_repeated")
        self.assertEqual(brief["sensor"], "crash_watch")
        self.assertEqual(brief["status"], "no_inference")

    def test_failed_delivery_leaves_the_state_unwritten(self):
        readings = _readings([_file()])
        rc = self.run_producer(readings, with_secret=False)
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.state_path))
        self.assertEqual(self.inbox_names(), [])
        # With the secret present the same dump files in full:
        # nothing was marked seen by the failed pass.
        rc = self.run_producer(readings)
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)


if __name__ == "__main__":
    unittest.main()
