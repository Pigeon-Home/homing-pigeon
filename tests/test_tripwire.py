"""Tripwire: the example sense that diffs a hashed tree.

Pins the Tripwire example (examples/extensions/tripwire/)
the way test_sky_watcher.py pins Sky Watcher: the manifest
through the real extension loader, the pure decide() diff
against fixture readings (learn pass, appeared / vanished /
changed, oversize-by-size, the alert cap that still absorbs
the baseline), the real SHA-384 hashing path on a small temp
tree, and one end-to-end run -- producer learns a baseline
quietly, a changed digest then files through the local inbox,
the real ingest files it, and the high-severity file_changed
wakes the gate and files a brief.

No live network and no live model anywhere: readings are
fixtures or a temp tree, and the end-to-end config has no
inference, so the wake brief is the deterministic fallback.
"""
import hashlib
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

EXAMPLE_DIR = os.path.join(REPO, "examples", "extensions", "tripwire")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
TRIP_SECRET = "5a2c8e1f4b7d4906a3c5e8f1b2d4a607" + "9c0e2f4a6b8d1c3e5f7a9b0d2e4f6a8c"


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "tripwire_example", os.path.join(EXAMPLE_DIR, "tripwire.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TW = _load_example_module()


def _manifest(**overrides):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    if overrides:
        manifest["tunables"] = dict(manifest["tunables"], **overrides)
    return manifest


def _entry(sha, size):
    return {"sha384": sha, "size": size}


def _readings(files, now=1000.0):
    return {"now": now, "files": files}


BASE_FILES = {
    "a.txt": _entry("a" * 96, 10),
    "sub/b.txt": _entry("b" * 96, 20),
}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "tripwire")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["file_appeared", "file_changed", "file_vanished"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "tripwire"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("tripwire", registry)
        self.assertEqual(registry["tripwire"]["version"], "0.1.0")

    def test_tunables_carry_the_cost_knobs(self):
        tunables = _manifest()["tunables"]
        for key in ("root", "excludes", "max_files", "max_file_mb",
                    "max_alerts_per_pass", "poll_interval_sec",
                    "learn_first_pass"):
            self.assertIn(key, tunables)
        self.assertEqual(tunables["poll_interval_sec"], 300)


class DecideTest(unittest.TestCase):
    def learned_state(self, files=BASE_FILES, **overrides):
        alerts, state = TW.decide(_readings(dict(files)),
                                  _manifest(**overrides), {})
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        return state

    def test_learn_first_pass_absorbs_and_files_nothing(self):
        state = self.learned_state()
        self.assertEqual(state["files"], BASE_FILES)

    def test_quiet_case_files_nothing(self):
        state = self.learned_state()
        alerts, state2 = TW.decide(_readings(dict(BASE_FILES)),
                                   _manifest(), state)
        self.assertEqual(alerts, [])
        self.assertEqual(state2["files"], BASE_FILES)

    def test_each_signal_fires_with_its_severity_and_detail(self):
        cases = [
            # (name, mutated files, signal, severity, detail bits)
            ("appeared",
             dict(BASE_FILES, **{"c.txt": _entry("c" * 96, 5)}),
             "file_appeared", "medium",
             {"path": "c.txt", "size": 5}),
            ("vanished",
             {"a.txt": BASE_FILES["a.txt"]},
             "file_vanished", "medium", {"path": "sub/b.txt"}),
            ("changed",
             dict(BASE_FILES, **{"a.txt": _entry("d" * 96, 11)}),
             "file_changed", "high",
             {"path": "a.txt", "old_sha384": "a" * 96,
              "new_sha384": "d" * 96, "size": 11}),
        ]
        for name, files, signal, severity, detail in cases:
            with self.subTest(case=name):
                state = self.learned_state()
                alerts, _s = TW.decide(_readings(files),
                                       _manifest(), state)
                self.assertEqual(len(alerts), 1)
                alert = alerts[0]
                self.assertEqual(alert["sensor"], "tripwire")
                self.assertEqual(alert["signal"], signal)
                self.assertEqual(alert["severity"], severity)
                self.assertEqual(alert["detail"], detail)

    def test_same_readings_twice_files_nothing_second_time(self):
        state = self.learned_state()
        changed = dict(BASE_FILES, **{"a.txt": _entry("d" * 96, 11)})
        alerts, state = TW.decide(_readings(changed), _manifest(), state)
        self.assertEqual([a["signal"] for a in alerts], ["file_changed"])
        alerts, _s = TW.decide(_readings(changed), _manifest(), state)
        self.assertEqual(alerts, [])

    def test_moved_reading_refiles(self):
        # The digest moves again after a change was absorbed:
        # a new change is a new alert, not a repeat of the old.
        state = self.learned_state()
        changed = dict(BASE_FILES, **{"a.txt": _entry("d" * 96, 11)})
        _a, state = TW.decide(_readings(changed), _manifest(), state)
        moved = dict(changed, **{"a.txt": _entry("e" * 96, 12)})
        alerts, _s = TW.decide(_readings(moved), _manifest(), state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["detail"]["old_sha384"], "d" * 96)
        self.assertEqual(alerts[0]["detail"]["new_sha384"], "e" * 96)

    def test_oversize_compares_by_size_only(self):
        big = {"sha384": None, "size": 100, "oversize": True}
        state = self.learned_state({"big.iso": big})
        same = {"big.iso": {"sha384": None, "size": 100,
                            "oversize": True}}
        alerts, state = TW.decide(_readings(same), _manifest(), state)
        self.assertEqual(alerts, [])
        grown = {"big.iso": {"sha384": None, "size": 101,
                             "oversize": True}}
        alerts, _s = TW.decide(_readings(grown), _manifest(), state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "file_changed")
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertIsNone(alerts[0]["detail"]["old_sha384"])
        self.assertIsNone(alerts[0]["detail"]["new_sha384"])
        self.assertEqual(alerts[0]["detail"]["size"], 101)

    def test_learn_first_pass_off_reports_everything_as_appeared(self):
        alerts, state = TW.decide(
            _readings(dict(BASE_FILES)),
            _manifest(learn_first_pass=False), {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["file_appeared", "file_appeared"])
        self.assertTrue(state["learned"])

    def test_alert_cap_still_absorbs_the_full_baseline(self):
        state = self.learned_state()
        changed = {p: _entry("z" * 96, 99) for p in BASE_FILES}
        changed["c.txt"] = _entry("c" * 96, 5)
        alerts, state = TW.decide(
            _readings(changed),
            _manifest(max_alerts_per_pass=2), state)
        self.assertEqual(len(alerts), 2)
        self.assertEqual(state["files"], _readings(changed)["files"])
        # The capped differences were absorbed, not re-filed.
        alerts, _s = TW.decide(_readings(changed), _manifest(), state)
        self.assertEqual(alerts, [])

    def test_bad_state_and_readings_are_quiet(self):
        alerts, state = TW.decide(None, _manifest(), "not a dict")
        self.assertEqual(alerts, [])
        self.assertEqual(state, {"learned": True, "files": {}})


class ReadLiveTest(unittest.TestCase):
    def _tree(self, root):
        with open(os.path.join(root, "a.txt"), "wb") as fh:
            fh.write(b"hello tripwire\n")
        os.makedirs(os.path.join(root, "sub"))
        with open(os.path.join(root, "sub", "b.txt"), "wb") as fh:
            fh.write(b"second file")
        with open(os.path.join(root, "skip.pyc"), "wb") as fh:
            fh.write(b"compiled")
        os.makedirs(os.path.join(root, "__pycache__"))
        with open(os.path.join(root, "__pycache__", "c.txt"),
                  "wb") as fh:
            fh.write(b"cached")

    def test_real_hashing_path_matches_hashlib(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            readings = TW.read_live(_manifest(root=d))
        self.assertEqual(sorted(readings["files"]),
                         ["a.txt", "sub/b.txt"])
        self.assertEqual(
            readings["files"]["a.txt"]["sha384"],
            hashlib.sha384(b"hello tripwire\n").hexdigest())
        self.assertEqual(
            readings["files"]["sub/b.txt"]["sha384"],
            hashlib.sha384(b"second file").hexdigest())
        self.assertEqual(readings["files"]["a.txt"]["size"], 15)
        self.assertEqual(readings["truncated"], 0)

    def test_oversize_file_records_no_digest(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "big.bin"), "wb") as fh:
                fh.write(b"x" * 4096)
            # 0.001 MB is ~1048 bytes: the file is over the cap.
            readings = TW.read_live(_manifest(root=d,
                                              max_file_mb=0.001))
        entry = readings["files"]["big.bin"]
        self.assertIsNone(entry["sha384"])
        self.assertEqual(entry["size"], 4096)
        self.assertTrue(entry["oversize"])

    def test_max_files_counts_the_truncated(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            readings = TW.read_live(_manifest(root=d, max_files=1))
        self.assertEqual(len(readings["files"]), 1)
        self.assertEqual(readings["truncated"], 1)

    def test_missing_root_is_empty_never_an_error(self):
        readings = TW.read_live(
            _manifest(root="/nonexistent/tripwire/root"))
        self.assertEqual(readings["files"], {})
        self.assertEqual(readings["truncated"], 0)


class TripwireFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "tripwire"))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {"trip-key": TRIP_SECRET},
            "key_policies": {
                "trip-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "tripwire": {"enabled": True, "key_id": "trip-key",
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

    def readings_file(self, files, name="readings.json"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_readings(files), fh)
        return path

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


class ProducerTest(TripwireFixture):
    def test_learn_pass_prints_nothing_then_change_prints(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = TW.main(["--readings",
                          self.readings_file(dict(BASE_FILES)),
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")
        changed = dict(BASE_FILES, **{"a.txt": _entry("d" * 96, 11)})
        out = io.StringIO()
        with redirect_stdout(out):
            rc = TW.main(["--readings",
                          self.readings_file(changed, "r2.json"),
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        printed = [json.loads(ln) for ln in
                   out.getvalue().splitlines() if ln.strip()]
        self.assertEqual([p["signal"] for p in printed],
                         ["file_changed"])

    def test_failed_delivery_leaves_the_state_unwritten(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(TW.main(
                ["--readings", self.readings_file(dict(BASE_FILES)),
                 "--state", self.state_path]), 0)
        changed = dict(BASE_FILES, **{"a.txt": _entry("d" * 96, 11)})
        with unittest.mock.patch.dict(os.environ, {}):
            os.environ.pop("HOMING_PIGEON_SENSOR_SECRET", None)
            rc = TW.main(["--readings",
                          self.readings_file(changed, "r2.json"),
                          "--local-dir", self.base,
                          "--key-id", "trip-key",
                          "--state", self.state_path])
        self.assertEqual(rc, 2)
        self.assertEqual(self.inbox_names(), [])
        with open(self.state_path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["files"], BASE_FILES)

    def test_unreadable_readings_is_exit_2(self):
        rc = TW.main(["--readings",
                      os.path.join(self._tmp.name, "nope.json"),
                      "--state", self.state_path])
        self.assertEqual(rc, 2)


class EndToEndTest(TripwireFixture):
    def test_changed_file_files_and_wakes_a_brief(self):
        # Pass 1: the baseline learns quietly.
        with redirect_stdout(io.StringIO()):
            rc = TW.main(["--readings",
                          self.readings_file(dict(BASE_FILES)),
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(self.inbox_names(), [])
        # Pass 2: one file's digest changed; deliver locally.
        changed = dict(BASE_FILES, **{"a.txt": _entry("d" * 96, 11)})
        with unittest.mock.patch.dict(
                os.environ,
                {"HOMING_PIGEON_SENSOR_SECRET": TRIP_SECRET}):
            rc = TW.main(["--readings",
                          self.readings_file(changed, "r2.json"),
                          "--local-dir", self.base,
                          "--key-id", "trip-key",
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        self.assertEqual(self.inbox_names(), [])
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "tripwire")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "tripwire")
        self.assertEqual(rec["extension_version"], "0.1.0")
        self.assertEqual(rec["signal"], "file_changed")
        self.assertEqual(rec["severity"], "high")
        declared = {s["name"]: s["description"]
                    for s in _manifest()["signals"]}
        self.assertEqual(rec["signal_description"],
                         declared["file_changed"])
        # The high signal wakes; with no inference configured
        # the brief is the deterministic fallback.
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "file_changed")
        self.assertEqual(brief["sensor"], "tripwire")
        self.assertEqual(brief["status"], "no_inference")


if __name__ == "__main__":
    unittest.main()
