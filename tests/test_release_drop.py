"""Release Drop: the example sense that files release artifacts.

Pins the Release Drop example (extensions/release-drop/)
the way test_sky_watcher.py pins Sky Watcher: the manifest
through the real extension loader, the pure decide() state
machine over fixture readings (arrival attested by its digest,
a changed digest under a known name, a vanished name dropped
silently), and the real hashing path -- read_live() and main()
over small temp files, with expected digests computed
independently in the test with hashlib.sha384.

No live network and no live hardware anywhere: the drop folder
is a temp directory and every other pass runs on fixtures.
"""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "extensions", "release-drop")

T0 = 1_700_000_000.0

DIGEST_A = hashlib.sha384(b"artifact bytes, first spin").hexdigest()
DIGEST_B = hashlib.sha384(b"artifact bytes, second spin").hexdigest()


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "release_drop_example",
        os.path.join(EXAMPLE_DIR, "release_drop.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load_example_module()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _file(name="pkg.tar.gz", size=128, sha384=DIGEST_A):
    return {"name": name, "size": size, "sha384": sha384}


def _readings(files, now=T0, skipped_oversize=0):
    return {"now": now, "files": files,
            "skipped_oversize": skipped_oversize}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "release_drop")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["artifact_arrived", "artifact_changed"])
        for knob in ("watch_dir", "poll_interval_sec", "max_hash_mb"):
            self.assertIn(knob, clean["tunables"])
        self.assertEqual(clean["tunables"]["watch_dir"], "./drop")
        self.assertEqual(clean["tunables"]["poll_interval_sec"], 60)
        self.assertEqual(clean["tunables"]["max_hash_mb"], 512)
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "release-drop"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("release_drop", registry)
        self.assertEqual(registry["release_drop"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def decide(self, files, state=None, now=T0):
        return RD.decide(_readings(files, now=now), _manifest(),
                         state if state is not None else {})

    def test_arrival_files_artifact_arrived_info_with_digest(self):
        alerts, state = self.decide([_file()])
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "release_drop")
        self.assertEqual(alert["signal"], "artifact_arrived")
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["detail"], {
            "name": "pkg.tar.gz", "size": 128, "sha384": DIGEST_A})
        self.assertEqual(state["seen"], {
            "pkg.tar.gz": {"sha384": DIGEST_A, "size": 128}})

    def test_changed_digest_files_artifact_changed_high(self):
        _a, state = self.decide([_file()])
        alerts, _state = self.decide(
            [_file(size=256, sha384=DIGEST_B)], state=state)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["signal"], "artifact_changed")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"], {
            "name": "pkg.tar.gz", "old_sha384": DIGEST_A,
            "new_sha384": DIGEST_B, "size": 256})

    def test_each_signal_fires_with_its_spec_fields(self):
        # Table-driven: (passes, want signal, want severity,
        # want detail items on the last alert).
        cases = [
            ([[_file()]], "artifact_arrived", "info",
             {"name": "pkg.tar.gz", "sha384": DIGEST_A, "size": 128}),
            ([[_file()], [_file(sha384=DIGEST_B)]],
             "artifact_changed", "high",
             {"name": "pkg.tar.gz", "old_sha384": DIGEST_A,
              "new_sha384": DIGEST_B}),
        ]
        for passes, signal, severity, detail in cases:
            with self.subTest(signal=signal):
                state = {}
                alerts = []
                for files in passes:
                    alerts, state = self.decide(files, state=state)
                alert = alerts[-1]
                self.assertEqual(alert["signal"], signal)
                self.assertEqual(alert["severity"], severity)
                for key, value in detail.items():
                    self.assertEqual(alert["detail"][key], value)

    def test_quiet_case_files_nothing(self):
        alerts, _state = self.decide([])
        self.assertEqual(alerts, [])
        alerts, _state = RD.decide({"now": T0}, _manifest(), {})
        self.assertEqual(alerts, [])

    def test_same_readings_twice_files_nothing_the_second_time(self):
        readings = _readings([_file()])
        alerts, state = RD.decide(readings, _manifest(), {})
        self.assertEqual(len(alerts), 1)
        alerts2, _state2 = RD.decide(readings, _manifest(), state)
        self.assertEqual(alerts2, [])

    def test_moved_digest_refiles_as_changed(self):
        _a, state = self.decide([_file()])
        alerts, _state = self.decide([_file(sha384=DIGEST_B)],
                                     state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["artifact_changed"])
        # And back again is a change too, not an arrival.
        _a, state = self.decide([_file(sha384=DIGEST_B)], state=state)
        alerts, _state = self.decide([_file()], state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["artifact_changed"])
        self.assertEqual(alerts[0]["detail"]["old_sha384"], DIGEST_B)
        self.assertEqual(alerts[0]["detail"]["new_sha384"], DIGEST_A)

    def test_vanished_name_is_dropped_silently(self):
        _a, state = self.decide([_file(), _file(name="other.bin")])
        self.assertEqual(sorted(state["seen"]),
                         ["other.bin", "pkg.tar.gz"])
        alerts, state = self.decide([_file()], state=state)
        self.assertEqual(alerts, [])  # no departure signal exists
        self.assertEqual(sorted(state["seen"]), ["pkg.tar.gz"])
        # Everything gone: state empties, still nothing filed.
        alerts, state = self.decide([], state=state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["seen"], {})

    def test_vanished_then_returned_name_arrives_fresh(self):
        _a, state = self.decide([_file()])
        _a, state = self.decide([], state=state)
        alerts, _state = self.decide([_file()], state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["artifact_arrived"])

    def test_garbage_state_and_entries_never_raise(self):
        for state in (None, "x", {"seen": []},
                      {"seen": {"a": {"sha384": 5}, "b": "nope"}}):
            with self.subTest(state=state):
                alerts, clean = RD.decide(
                    _readings([_file()]), _manifest(), state)
                self.assertEqual(len(alerts), 1)
                self.assertIn("pkg.tar.gz", clean["seen"])
        alerts, _state = RD.decide(
            _readings([{"name": "x"}, {"sha384": "y"}, "junk", None]),
            _manifest(), {})
        self.assertEqual(alerts, [])


class HashingPathTest(unittest.TestCase):
    """The real hashing path, on small temp files."""

    def _manifest_with(self, watch_dir, **tunables):
        manifest = _manifest()
        manifest["tunables"] = dict(manifest["tunables"],
                                    watch_dir=watch_dir, **tunables)
        return manifest

    def _write(self, folder, name, data):
        path = os.path.join(folder, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_read_live_hashes_with_sha384(self):
        data = b"release bytes to attest" * 100
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "pkg.tar.gz", data)
            self._write(d, ".hidden", b"not an artifact")
            readings = RD.read_live(self._manifest_with(d))
        self.assertEqual(readings["skipped_oversize"], 0)
        self.assertEqual(len(readings["files"]), 1)
        entry = readings["files"][0]
        self.assertEqual(entry["name"], "pkg.tar.gz")
        self.assertEqual(entry["size"], len(data))
        self.assertEqual(entry["sha384"],
                         hashlib.sha384(data).hexdigest())

    def test_missing_dir_is_empty_never_an_error(self):
        readings = RD.read_live(self._manifest_with(
            os.path.join(tempfile.gettempdir(),
                         "release-drop-no-such-dir-xyz")))
        self.assertEqual(readings["files"], [])
        self.assertEqual(readings["skipped_oversize"], 0)

    def test_oversize_file_is_skipped_and_counted(self):
        with tempfile.TemporaryDirectory() as d:
            # Just over the 1 MB cap this test sets.
            self._write(d, "big.bin", b"z" * (1024 * 1024 + 1))
            self._write(d, "small.bin", b"small")
            manifest = self._manifest_with(d, max_hash_mb=1)
            readings = RD.read_live(manifest)
        self.assertEqual(readings["skipped_oversize"], 1)
        self.assertEqual([f["name"] for f in readings["files"]],
                         ["small.bin"])

    def test_main_watch_dir_attests_the_real_digest(self):
        data = b"the artifact that actually landed"
        want = hashlib.sha384(data).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            drop = os.path.join(d, "drop")
            os.makedirs(drop)
            self._write(drop, "release.zip", data)
            state = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = RD.main(["--watch-dir", drop, "--state", state])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual(len(printed), 1)
            alert = printed[0]
            self.assertEqual(alert["signal"], "artifact_arrived")
            self.assertEqual(alert["severity"], "info")
            self.assertEqual(alert["detail"]["name"], "release.zip")
            self.assertEqual(alert["detail"]["size"], len(data))
            self.assertEqual(alert["detail"]["sha384"], want)
            # The drop is quiet on the next pass, and a changed
            # file under the same name files artifact_changed
            # with both real digests.
            out = io.StringIO()
            with redirect_stdout(out):
                rc = RD.main(["--watch-dir", drop, "--state", state])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            data2 = b"the artifact, respun in place"
            self._write(drop, "release.zip", data2)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = RD.main(["--watch-dir", drop, "--state", state])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual(len(printed), 1)
            alert = printed[0]
            self.assertEqual(alert["signal"], "artifact_changed")
            self.assertEqual(alert["severity"], "high")
            self.assertEqual(alert["detail"]["old_sha384"], want)
            self.assertEqual(alert["detail"]["new_sha384"],
                             hashlib.sha384(data2).hexdigest())

    def test_main_names_oversize_files_on_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            drop = os.path.join(d, "drop")
            os.makedirs(drop)
            self._write(drop, "big.bin", b"z" * (1024 * 1024 + 1))
            manifest_path = os.path.join(d, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(self._manifest_with(drop, max_hash_mb=1), fh)
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = RD.main(["--manifest", manifest_path,
                              "--watch-dir", drop,
                              "--state", os.path.join(d, "state.json")])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("skipped this pass", err.getvalue())

    def test_unreadable_manifest_and_readings_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            self.assertEqual(
                RD.main(["--manifest", os.path.join(d, "nope.json"),
                         "--state", state]), 2)
            self.assertEqual(
                RD.main(["--readings", os.path.join(d, "nope.json"),
                         "--state", state]), 2)


if __name__ == "__main__":
    unittest.main()
