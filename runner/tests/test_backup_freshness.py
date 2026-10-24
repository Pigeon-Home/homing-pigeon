"""Backup Freshness: the example sense that files backup staleness.

Pins the Backup Freshness example
(runner/extensions/backup-freshness/): the manifest through
the real extension loader and the pure decide() state machine --
arrival, stale, critical, the empty-directory clock, and the
tier discipline -- across scripted readings fixtures.

No live network and no live hardware anywhere: every reading
is a fixture dict, and the live directory read is never used.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "backup-freshness")

T0 = 1700000000.0
STALE = 90000.0


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "backup_freshness_example",
        os.path.join(EXAMPLE_DIR, "backup_freshness.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BF = _load_example_module()


def _manifest(**tunable_overrides):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    tunables = dict(manifest["tunables"])
    tunables.update(tunable_overrides)
    manifest["tunables"] = tunables
    return manifest


def _readings(now, newest):
    return {"now": float(now), "newest": newest}


def _newest(name="backup-1.tar", mtime=T0, size=4096):
    return {"name": name, "mtime": float(mtime), "size": size}


class ManifestTest(unittest.TestCase):
    def test_shipped_manifest_parses(self):
        with open(os.path.join(EXAMPLE_DIR, "extension.json"),
                  encoding="utf-8") as fh:
            raw = json.load(fh)
        clean = E.parse_manifest(raw)
        self.assertEqual(clean["name"], "backup_freshness")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["backup_arrived", "backup_critical", "backup_stale"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertIn("watch_dir", clean["tunables"])
        self.assertIn("glob", clean["tunables"])
        self.assertIn("stale_after_sec", clean["tunables"])
        self.assertEqual(clean["tunables"]["stale_after_sec"], 90000)
        self.assertEqual(clean["tunables"]["poll_interval_sec"], 3600)

    def test_loads_via_load_extensions_from_copied_tree(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR,
                            os.path.join(d, "backup-freshness"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("backup_freshness", registry)
        self.assertEqual(registry["backup_freshness"]["version"], "0.1.0")
        self.assertEqual(
            sorted(registry["backup_freshness"]["signal_descriptions"]),
            ["backup_arrived", "backup_critical", "backup_stale"])


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest()

    def test_backup_arrived_fires_info(self):
        alerts, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "backup_arrived")
        self.assertEqual(alerts[0]["severity"], "info")
        self.assertEqual(alerts[0]["sensor"], "backup_freshness")
        self.assertEqual(alerts[0]["detail"]["name"], "backup-1.tar")
        self.assertEqual(alerts[0]["detail"]["mtime"], T0)
        self.assertEqual(alerts[0]["detail"]["size"], 4096)
        self.assertEqual(state["last_seen_name"], "backup-1.tar")
        self.assertEqual(state["last_seen_mtime"], T0)
        self.assertEqual(state["tier"], "ok")

    def test_quiet_case_fresh_backup_files_nothing_after_arrival(self):
        _a, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        alerts, state = BF.decide(
            _readings(T0 + 3600, _newest(mtime=T0)), self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["tier"], "ok")

    def test_backup_stale_fires_medium(self):
        _a, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        now = T0 + STALE + 100
        alerts, state = BF.decide(
            _readings(now, _newest(mtime=T0)), self.manifest, state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "backup_stale")
        self.assertEqual(alerts[0]["severity"], "medium")
        self.assertEqual(alerts[0]["detail"]["age_sec"], STALE + 100)
        self.assertEqual(alerts[0]["detail"]["threshold_sec"], STALE)
        self.assertEqual(alerts[0]["detail"]["last_seen_name"],
                         "backup-1.tar")
        self.assertEqual(state["tier"], "stale")

    def test_backup_critical_fires_high_after_stale(self):
        _a, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        _a, state = BF.decide(
            _readings(T0 + STALE + 100, _newest(mtime=T0)),
            self.manifest, state)
        self.assertEqual(state["tier"], "stale")
        now = T0 + 2 * STALE + 100
        alerts, state = BF.decide(
            _readings(now, _newest(mtime=T0)), self.manifest, state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "backup_critical")
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["detail"]["age_sec"],
                         2 * STALE + 100)
        self.assertEqual(alerts[0]["detail"]["threshold_sec"], STALE)
        self.assertEqual(alerts[0]["detail"]["last_seen_name"],
                         "backup-1.tar")
        self.assertEqual(state["tier"], "critical")

    def test_jump_straight_from_ok_files_critical_only(self):
        _a, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        now = T0 + 2 * STALE + 5000
        alerts, state = BF.decide(
            _readings(now, _newest(mtime=T0)), self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["backup_critical"])
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(state["tier"], "critical")

    def test_never_seen_and_no_newest_is_quiet(self):
        alerts, state = BF.decide(_readings(T0, None), self.manifest, {})
        self.assertEqual(alerts, [])
        self.assertEqual(state["tier"], "ok")
        self.assertIsNone(state["last_seen_name"])
        # Still quiet far in the future: nothing ever backed up
        # is a configuration fact, not this sense's alert.
        alerts, state = BF.decide(
            _readings(T0 + 10 * STALE, None), self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["tier"], "ok")

    def test_empty_directory_clock_keeps_running(self):
        _a, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        now = T0 + STALE + 50
        alerts, state = BF.decide(_readings(now, None),
                                  self.manifest, state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "backup_stale")
        self.assertEqual(alerts[0]["detail"]["last_seen_name"],
                         "backup-1.tar")
        self.assertEqual(state["tier"], "stale")

    def test_same_readings_twice_files_nothing_second_time(self):
        readings = _readings(T0 + 10, _newest(mtime=T0))
        alerts, state = BF.decide(readings, self.manifest, {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["backup_arrived"])
        alerts2, state = BF.decide(readings, self.manifest, state)
        self.assertEqual(alerts2, [])
        # The stale tier also files only once for the same age.
        stale_readings = _readings(T0 + STALE + 100, _newest(mtime=T0))
        alerts3, state = BF.decide(stale_readings, self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts3],
                         ["backup_stale"])
        alerts4, state = BF.decide(stale_readings, self.manifest, state)
        self.assertEqual(alerts4, [])

    def test_moved_reading_refiles(self):
        # A fresh arrival after stale resets the tier and files
        # arrived again; a later stall files stale again.
        _a, state = BF.decide(
            _readings(T0 + 10, _newest(mtime=T0)), self.manifest, {})
        _a, state = BF.decide(
            _readings(T0 + STALE + 100, _newest(mtime=T0)),
            self.manifest, state)
        self.assertEqual(state["tier"], "stale")
        t1 = T0 + STALE + 200
        alerts, state = BF.decide(
            _readings(t1, _newest(name="backup-2.tar", mtime=t1)),
            self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["backup_arrived"])
        self.assertEqual(alerts[0]["detail"]["name"], "backup-2.tar")
        self.assertEqual(state["tier"], "ok")
        alerts, state = BF.decide(
            _readings(t1 + STALE + 10,
                      _newest(name="backup-2.tar", mtime=t1)),
            self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["backup_stale"])

    def test_arrival_without_size_omits_size(self):
        newest = {"name": "backup-x.tar", "mtime": T0}
        alerts, _state = BF.decide(_readings(T0 + 5, newest),
                                   self.manifest, {})
        self.assertEqual(len(alerts), 1)
        self.assertNotIn("size", alerts[0]["detail"])
        self.assertEqual(alerts[0]["detail"]["name"], "backup-x.tar")

    def test_every_signal_table(self):
        # Table-driven sweep: each signal with its severity.
        table = []
        _a, st = BF.decide(_readings(T0 + 10, _newest(mtime=T0)),
                           self.manifest, {})
        table.append((_a, "backup_arrived", "info"))
        stale_alerts, st = BF.decide(
            _readings(T0 + STALE + 1, _newest(mtime=T0)),
            self.manifest, st)
        table.append((stale_alerts, "backup_stale", "medium"))
        crit_alerts, _st = BF.decide(
            _readings(T0 + 2 * STALE + 1, _newest(mtime=T0)),
            self.manifest, st)
        table.append((crit_alerts, "backup_critical", "high"))
        for alerts, signal, severity in table:
            self.assertEqual(len(alerts), 1, signal)
            self.assertEqual(alerts[0]["signal"], signal)
            self.assertEqual(alerts[0]["severity"], severity)
            self.assertEqual(alerts[0]["sensor"], "backup_freshness")


if __name__ == "__main__":
    unittest.main()
