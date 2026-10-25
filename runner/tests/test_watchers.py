"""The two watcher examples: Resource Sentinel and Job Watcher.

Pins runner/extensions/resource-sentinel/ and
runner/extensions/job-watcher/ the way test_crash_watch.py
pins Crash Watch: the manifests through the real extension
loader, the pure decide() cores over fixture readings
(every declared signal firing, its restraint cases staying
quiet, state discipline), read_live() against fixture
sources, and one end-to-end per extension -- producer into
the local inbox, the real ingest files the alert, and the
high-severity signal wakes the gate and files a brief.

No live network and no live hardware anywhere: readings
are fixtures, and the end-to-end configs have no inference,
so the wake briefs are the deterministic fallback.
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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.oracle import senses as S  # noqa: E402
from runner.ops import extensions as E  # noqa: E402

RS_DIR = os.path.join(REPO, "runner", "extensions",
                      "resource-sentinel")
JW_DIR = os.path.join(REPO, "runner", "extensions", "job-watcher")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + \
    "9008dd09b3befd1b078a64781ac2f3e5"
RS_SECRET = "1a2b3c4d5e6f708192a3b4c5d6e7f809" + \
    "93a4b5c6d7e8f901a2b3c4d5e6f7081a"
JW_SECRET = "f0e1d2c3b4a5968778695a4b3c2d1e0f" + \
    "0a1b2c3d4e5f60718293a4b5c6d7e8f9"

T0 = 1_700_000_000.0


def _load(folder, filename, modname):
    spec = importlib.util.spec_from_file_location(
        modname, os.path.join(folder, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RS = _load(RS_DIR, "resource_sentinel.py", "resource_sentinel_example")
JW = _load(JW_DIR, "job_watcher.py", "job_watcher_example")


def _manifest(folder):
    with open(os.path.join(folder, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------
# Resource Sentinel

def _rs_readings(now, cpu_total=None, cpu_idle=None, disk_free=None,
                 processes=None, mem_pct=None):
    return {"now": now, "cpu_total": cpu_total,
            "cpu_idle": cpu_idle, "disk_free_bytes": disk_free,
            "processes": processes, "mem_avail_pct": mem_pct}


def _rs_run(passes, manifest=None):
    """Feed (now, kwargs) passes through decide, threading state."""
    manifest = manifest or _manifest(RS_DIR)
    state = {}
    alerts = []
    for now, kwargs in passes:
        fired, state = RS.decide(_rs_readings(now, **kwargs),
                                 manifest, state)
        alerts.extend(fired)
    return alerts, state


def _cpu_passes(busy_pct=98.0, steps=4, step_sec=300.0):
    """Passes whose cumulative counters give a flat busy share."""
    passes = []
    total = idle = 0.0
    for i in range(steps + 1):
        passes.append((T0 + i * step_sec,
                       {"cpu_total": total, "cpu_idle": idle}))
        total += 10000.0
        idle += 10000.0 * (100.0 - busy_pct) / 100.0
    return passes


class ResourceSentinelManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest(RS_DIR))
        self.assertEqual(clean["name"], "resource_sentinel")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["cpu_saturation_sustained", "disk_fill_velocity",
             "process_storm", "memory_exhaustion_trend"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(RS_DIR, os.path.join(d, "resource-sentinel"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("resource_sentinel", registry)


class ResourceSentinelDecideTest(unittest.TestCase):
    def test_sustained_cpu_fires_high_once(self):
        alerts, _state = _rs_run(_cpu_passes(98.0))
        self.assertEqual([a["signal"] for a in alerts],
                         ["cpu_saturation_sustained"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["sensor"], "resource_sentinel")
        self.assertGreaterEqual(alert["detail"]["cpu_busy_pct"], 95)

    def test_busy_below_threshold_and_short_windows_stay_quiet(self):
        alerts, _state = _rs_run(_cpu_passes(80.0))
        self.assertEqual(alerts, [])
        # A saturated window that has not spanned min_span_sec
        # yet is evidence of nothing.
        passes = _cpu_passes(99.0, steps=2, step_sec=100.0)
        alerts, _state = _rs_run(passes)
        self.assertEqual(alerts, [])

    def test_disk_fill_velocity_fires_high(self):
        gib = 1024.0 ** 3
        passes = [(T0 + i * 300.0,
                   {"disk_free": 100 * gib - i * 2 * gib})
                  for i in range(5)]  # 24 GB/hour
        alerts, _state = _rs_run(passes)
        self.assertEqual([a["signal"] for a in alerts],
                         ["disk_fill_velocity"])
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertGreaterEqual(alerts[0]["detail"]["gb_per_hour"], 10)

    def test_slow_fill_stays_quiet(self):
        gib = 1024.0 ** 3
        passes = [(T0 + i * 300.0, {"disk_free": 100 * gib - i * 100})
                  for i in range(5)]
        alerts, _state = _rs_run(passes)
        self.assertEqual(alerts, [])

    def test_process_storm_fires_medium(self):
        counts = [200, 400, 600, 600, 600]  # growth peaks at 400
        passes = [(T0 + i * 300.0, {"processes": n})
                  for i, n in enumerate(counts)]
        alerts, _state = _rs_run(passes)
        self.assertEqual([a["signal"] for a in alerts],
                         ["process_storm"])
        self.assertEqual(alerts[0]["severity"], "medium")
        self.assertEqual(alerts[0]["detail"]["growth"], 400)

    def test_memory_trend_fires_but_flat_low_memory_does_not(self):
        falling = [(T0 + i * 300.0, {"mem_pct": 60.0 - i * 12.0})
                   for i in range(5)]  # 60 -> 12, steady fall
        alerts, _state = _rs_run(falling)
        self.assertEqual([a["signal"] for a in alerts],
                         ["memory_exhaustion_trend"])
        self.assertEqual(alerts[0]["severity"], "medium")
        # Flat at the same low level pi-health would report is
        # a threshold, not a trend: no drop across the window.
        flat = [(T0 + i * 300.0, {"mem_pct": 10.0}) for i in range(5)]
        alerts, _state = _rs_run(flat)
        self.assertEqual(alerts, [])

    def test_episode_discipline_quiet_while_steady_fresh_after_clear(self):
        # (now offset, cpu_total, cpu_idle) -- one cumulative
        # counter story in four phases: saturate (fires once),
        # hold steady (quiet), clear (quiet), saturate again
        # once the clear sample ages out of the window (fires
        # fresh).
        story = [
            (0, 0, 0), (300, 10000, 200), (600, 20000, 400),
            (900, 30000, 600), (1200, 40000, 800),
            (1500, 50000, 1000), (1800, 60000, 1200),
            (2100, 70000, 20000),
            (2400, 80000, 20200), (2700, 90000, 20400),
            (3000, 100000, 20600), (3300, 110000, 20800),
            (3600, 120000, 21000), (3900, 130000, 21200),
        ]
        manifest = _manifest(RS_DIR)
        state = {}
        fired_at = []
        for offset, total, idle in story:
            fired, state = RS.decide(
                _rs_readings(T0 + offset, cpu_total=total,
                             cpu_idle=idle), manifest, state)
            if fired:
                fired_at.append((offset,
                                 [a["signal"] for a in fired]))
        self.assertEqual(
            fired_at,
            [(900, ["cpu_saturation_sustained"]),
             (3900, ["cpu_saturation_sustained"])])

    def test_none_sources_and_garbage_never_raise(self):
        alerts, _state = _rs_run([(T0 + i * 300.0, {})
                                  for i in range(6)])
        self.assertEqual(alerts, [])
        alerts, _state = RS.decide(None, _manifest(RS_DIR),
                                   {"samples": "junk", "fired": []})
        self.assertEqual(alerts, [])
        alerts, _state = RS.decide(_rs_readings(T0, cpu_total="x"),
                                   _manifest(RS_DIR), None)
        self.assertEqual(alerts, [])


class ResourceSentinelProducerTest(unittest.TestCase):
    def test_readings_mode_prints_and_saves_state(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            for i, (now, kwargs) in enumerate(_cpu_passes(98.0)):
                path = os.path.join(d, f"r{i}.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(_rs_readings(now, **kwargs), fh)
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = RS.main(["--readings", path,
                                  "--state", state])
                self.assertEqual(rc, 0)
                if i == 3:
                    # The fourth sample completes the minimum
                    # span at full saturation: the alert files.
                    printed = [json.loads(ln) for ln in
                               out.getvalue().splitlines()
                               if ln.strip()]
                    self.assertEqual([p["signal"] for p in printed],
                                     ["cpu_saturation_sustained"])
                else:
                    self.assertEqual(out.getvalue(), "")

    def test_unreadable_manifest_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                RS.main(["--manifest", os.path.join(d, "nope.json"),
                         "--state", os.path.join(d, "s.json")]), 2)


# ---------------------------------------------------------------------
# Job Watcher

def _obs(job_id, key="key-a", kind="exec", label="backup.sh",
         exit_code=0, duration=10.0, saved_at=T0, error=""):
    return {"job_id": job_id, "key": key, "kind": kind,
            "label": label, "exit_code": exit_code,
            "timed_out": False, "duration_sec": duration,
            "saved_at": saved_at, "error": error}


def _jw_readings(records, now=T0 + 1000.0):
    return {"now": now, "records": records, "truncated": 0}


def _jw_run(record_groups, manifest=None):
    """Feed groups of records through decide, threading state."""
    manifest = manifest or _manifest(JW_DIR)
    state = {}
    alerts = []
    for records in record_groups:
        fired, state = JW.decide(_jw_readings(records), manifest, state)
        alerts.extend(fired)
    return alerts, state


class JobWatcherManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest(JW_DIR))
        self.assertEqual(clean["name"], "job_watcher")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["job_failing_repeatedly", "job_flaky",
             "job_duration_anomaly", "failure_cluster"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(JW_DIR, os.path.join(d, "job-watcher"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("job_watcher", registry)


class JobWatcherDecideTest(unittest.TestCase):
    def test_repeated_failure_files_medium_with_dominant_exit(self):
        records = [
            _obs(f"j{i}", exit_code=2, saved_at=T0 + i * 60,
                 error="rsync: link_stat failed")
            for i in range(3)]
        alerts, _state = _jw_run([records])
        self.assertEqual([a["signal"] for a in alerts],
                         ["job_failing_repeatedly"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["failures"], 3)
        self.assertEqual(alert["detail"]["dominant_exit_code"], 2)
        self.assertEqual(alert["detail"]["dominant_error"],
                         "rsync: link_stat failed")

    def test_two_failures_stay_quiet_and_old_failures_age_out(self):
        records = [_obs(f"j{i}", exit_code=1, saved_at=T0 + i * 60)
                   for i in range(2)]
        alerts, _state = _jw_run([records])
        self.assertEqual(alerts, [])
        # Three failures, but all older than the failure window
        # relative to the pass's "now" (jw_readings now is
        # T0 + 1000; move the window with a custom manifest).
        manifest = _manifest(JW_DIR)
        manifest["tunables"] = dict(manifest["tunables"],
                                    failure_window_sec=100)
        records = [_obs(f"k{i}", exit_code=1, saved_at=T0 + i * 10)
                   for i in range(3)]
        alerts, _state = _jw_run([records], manifest=manifest)
        self.assertEqual(alerts, [])

    def test_flaky_files_info_and_steady_jobs_do_not(self):
        records = []
        for i, code in enumerate([1, 0, 1, 0, 1, 0]):
            records.append(_obs(f"f{i}", key="key-flaky",
                                exit_code=code,
                                saved_at=T0 + i * 60))
        alerts, _state = _jw_run([records])
        signals = [a["signal"] for a in alerts]
        self.assertIn("job_flaky", signals)
        flaky = alerts[signals.index("job_flaky")]
        self.assertEqual(flaky["severity"], "info")
        self.assertEqual(flaky["detail"]["pattern"], "FPFPFP")
        steady = [_obs(f"s{i}", key="key-steady", exit_code=0,
                       saved_at=T0 + i * 60) for i in range(6)]
        alerts, _state = _jw_run([steady])
        self.assertEqual(alerts, [])

    def test_duration_anomaly_needs_a_baseline(self):
        # Three prior runs only: below duration_min_baseline,
        # so even a huge run earns NO anomaly call.
        records = [_obs(f"b{i}", key="key-new", duration=10.0,
                        saved_at=T0 + i * 60) for i in range(3)]
        records.append(_obs("b9", key="key-new", duration=900.0,
                            saved_at=T0 + 240))
        alerts, _state = _jw_run([records])
        self.assertEqual(
            [a for a in alerts
             if a["signal"] == "job_duration_anomaly"], [])

    def test_duration_anomaly_fires_against_the_baseline(self):
        records = [_obs(f"d{i}", key="key-slow", duration=d,
                        saved_at=T0 + i * 60)
                   for i, d in enumerate([9.0, 10.0, 11.0, 10.0, 9.5])]
        records.append(_obs("d9", key="key-slow", duration=300.0,
                            saved_at=T0 + 300))
        alerts, _state = _jw_run([records])
        anomalies = [a for a in alerts
                     if a["signal"] == "job_duration_anomaly"]
        self.assertEqual(len(anomalies), 1)
        alert = anomalies[0]
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["baseline_runs"], 5)
        self.assertEqual(alert["detail"]["baseline_median_sec"], 10.0)
        # A job that has always taken an hour is not anomalous
        # for taking an hour.
        records = [_obs(f"h{i}", key="key-long", duration=3600.0,
                        saved_at=T0 + i * 60) for i in range(5)]
        records.append(_obs("h9", key="key-long", duration=3700.0,
                            saved_at=T0 + 300))
        alerts, _state = _jw_run([records])
        self.assertEqual(
            [a for a in alerts
             if a["signal"] == "job_duration_anomaly"], [])

    def test_failure_cluster_needs_distinct_jobs(self):
        records = [_obs(f"c{i}", key=f"key-{i}", exit_code=1,
                        saved_at=T0 + 900 + i * 10) for i in range(3)]
        alerts, _state = _jw_run([records])
        self.assertEqual([a["signal"] for a in alerts],
                         ["failure_cluster"])
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["detail"]["distinct_jobs"], 3)
        # One job failing three times is a repeat, not a cluster.
        records = [_obs(f"r{i}", key="key-solo", exit_code=1,
                        saved_at=T0 + 900 + i * 10) for i in range(3)]
        alerts, _state = _jw_run([records])
        self.assertNotIn("failure_cluster",
                         [a["signal"] for a in alerts])

    def test_seen_records_fold_once(self):
        records = [_obs(f"j{i}", exit_code=1, saved_at=T0 + i * 60)
                   for i in range(3)]
        alerts, state = _jw_run([records])
        self.assertEqual(len(alerts), 1)
        alerts2, _state = JW.decide(_jw_readings(records),
                                    _manifest(JW_DIR), state)
        self.assertEqual(alerts2, [])

    def test_score_duration_seam(self):
        history = [10.0, 11.0, 9.0, 10.0, 10.5]
        anomalous, stats = JW.score_duration(history, 12.0)
        self.assertFalse(anomalous)
        anomalous, stats = JW.score_duration(history, 300.0)
        self.assertTrue(anomalous)
        self.assertEqual(stats["median"], 10.0)
        # Zero spread: it takes twice the median to be called.
        anomalous, _stats = JW.score_duration([10.0] * 6, 30.0)
        self.assertTrue(anomalous)
        anomalous, _stats = JW.score_duration([10.0] * 6, 19.0)
        self.assertFalse(anomalous)
        # No baseline, no call.
        anomalous, stats = JW.score_duration([10.0] * 4, 300.0)
        self.assertFalse(anomalous)
        self.assertEqual(stats["baseline_runs"], 4)

    def test_garbage_never_raises(self):
        alerts, _state = JW.decide(None, _manifest(JW_DIR),
                                   {"seen": [], "jobs": "x"})
        self.assertEqual(alerts, [])
        alerts, _state = JW.decide(
            _jw_readings([{"job_id": 5}, "junk", _obs("ok")]),
            _manifest(JW_DIR), None)
        self.assertEqual(alerts, [])


class JobWatcherReadLiveTest(unittest.TestCase):
    def _write_record(self, retained, name, record):
        with open(os.path.join(retained, name), "w",
                  encoding="utf-8") as fh:
            if isinstance(record, str):
                fh.write(record)
            else:
                json.dump(record, fh)

    def test_reads_the_retained_store_tolerantly(self):
        with tempfile.TemporaryDirectory() as base:
            retained = os.path.join(base, "retained")
            os.makedirs(retained)
            self._write_record(retained, "job-1.json", {
                "job_id": "job-1", "kind": "exec",
                "script": "backup.sh\n",
                "exit_code": 0, "timed_out": False,
                "duration_sec": 12.5, "stderr": "",
                "saved_at": T0})
            # An artifact-scan note: no duration_sec at all.
            self._write_record(retained, "job-2.json", {
                "job_id": "job-2", "kind": "exec", "script": "x.sh",
                "exit_code": 3, "timed_out": False,
                "artifact_scan": ["hit"], "saved_at": T0 + 5})
            self._write_record(retained, "job-3.json",
                               "{partial write, not json")
            self._write_record(retained, "notes.txt", "ignored")
            manifest = _manifest(JW_DIR)
            manifest["tunables"] = dict(
                manifest["tunables"], runner_base_dir=base)
            readings = JW.read_live(manifest)
        self.assertEqual(readings["truncated"], 0)
        self.assertEqual(len(readings["records"]), 2)
        by_id = {r["job_id"]: r for r in readings["records"]}
        self.assertEqual(by_id["job-1"]["duration_sec"], 12.5)
        self.assertEqual(by_id["job-1"]["label"], "backup.sh")
        self.assertIsNone(by_id["job-2"]["duration_sec"])
        self.assertEqual(by_id["job-2"]["key"],
                         JW.job_key("exec", "x.sh"))

    def test_missing_store_reads_empty(self):
        manifest = _manifest(JW_DIR)
        manifest["tunables"] = dict(
            manifest["tunables"],
            runner_base_dir=os.path.join(
                tempfile.gettempdir(), "job-watcher-no-such-base"))
        readings = JW.read_live(manifest)
        self.assertEqual(readings["records"], [])
        self.assertEqual(readings["truncated"], 0)

    def test_an_unlistable_store_reads_empty(self):
        # Queue A refill: read_live's listing leg
        # (coverage run 40189711740: lines 321-322) -- a
        # retained store that exists but cannot be
        # listed reads as no records, never an error.
        from unittest import mock
        with tempfile.TemporaryDirectory() as base:
            retained = os.path.join(base, "retained")
            os.makedirs(retained)
            manifest = _manifest(JW_DIR)
            manifest["tunables"] = dict(
                manifest["tunables"], runner_base_dir=base)
            with mock.patch.object(
                    os, "listdir",
                    side_effect=OSError("cannot list")):
                readings = JW.read_live(manifest)
        self.assertEqual(readings["records"], [])
        self.assertEqual(readings["truncated"], 0)

    def test_a_record_that_cannot_be_statted_is_skipped(self):
        # Queue A refill: the per-record probe leg
        # (lines 331-332) -- one record whose mtime
        # cannot be read is passed over; its sibling
        # still reads.
        from unittest import mock
        with tempfile.TemporaryDirectory() as base:
            retained = os.path.join(base, "retained")
            os.makedirs(retained)
            for name, jid in (("job-1.json", "job-1"),
                              ("job-2.json", "job-2")):
                self._write_record(retained, name, {
                    "job_id": jid, "kind": "exec",
                    "script": "x.sh", "exit_code": 0,
                    "timed_out": False, "saved_at": T0})
            manifest = _manifest(JW_DIR)
            manifest["tunables"] = dict(
                manifest["tunables"], runner_base_dir=base)
            real = os.path.getmtime

            def flaky(path, *a, **kw):
                if str(path).endswith("job-2.json"):
                    raise OSError("gone")
                return real(path, *a, **kw)

            with mock.patch.object(os.path, "getmtime", flaky):
                readings = JW.read_live(manifest)
        self.assertEqual(
            [r["job_id"] for r in readings["records"]], ["job-1"])


class JobWatcherCleanStateTest(unittest.TestCase):
    """Queue A refill: _clean_state's trimming and
    repair legs (coverage run 40189711740: lines 378-
    379, 385, 388). A saved state is untrusted input:
    the seen map is capped to its newest entries, a
    job entry keyed or shaped wrong is dropped, and
    a fired map that is not a map reads as empty.
    """

    def test_the_seen_cap_keeps_the_newest(self):
        from unittest import mock
        state = {"seen": {"k%d" % i: float(i)
                          for i in range(1, 6)},
                 "jobs": {}}
        with mock.patch.object(JW, "_SEEN_CAP", 3):
            cleaned = JW._clean_state(state, 10)
        self.assertEqual(cleaned["seen"],
                         {"k3": 3.0, "k4": 4.0, "k5": 5.0})

    def test_misshapen_job_entries_drop_or_repair(self):
        state = {"seen": {}, "jobs": {
            "good": {"kind": "exec", "label": "x",
                     "fired": "not-a-map"},
            7: {"kind": "exec"},
            "bad": "not-a-dict",
        }}
        cleaned = JW._clean_state(state, 10)
        self.assertEqual(sorted(cleaned["jobs"]), ["good"])
        self.assertEqual(cleaned["jobs"]["good"]["fired"], {})
        self.assertEqual(cleaned["jobs"]["good"]["kind"], "exec")


# ---------------------------------------------------------------------
# End to ends

class WatcherFixture(unittest.TestCase):
    folder = None       # example folder name
    mod = None          # producer module
    sensor = None       # manifest sensor name
    secret = None
    key_id = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(os.path.join(REPO, "runner", "extensions",
                                     self.folder),
                        os.path.join(self.ext_root, self.folder))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {self.key_id: self.secret},
            "key_policies": {
                self.key_id: {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                self.sensor: {"enabled": True, "key_id": self.key_id,
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

    def readings_file(self, readings, name):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(readings, fh)
        return path

    def run_producer(self, readings, name="readings.json"):
        env = {"HOMING_PIGEON_SENSOR_SECRET": self.secret}
        with unittest.mock.patch.dict(os.environ, env):
            return self.mod.main(
                ["--readings", self.readings_file(readings, name),
                 "--local-dir", self.base,
                 "--key-id", self.key_id,
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


class ResourceSentinelEndToEndTest(WatcherFixture):
    folder = "resource-sentinel"
    mod = RS
    sensor = "resource_sentinel"
    secret = RS_SECRET
    key_id = "res-key"

    def test_sustained_cpu_files_and_wakes_a_brief(self):
        for i, (now, kwargs) in enumerate(_cpu_passes(98.0)):
            rc = self.run_producer(_rs_readings(now, **kwargs),
                                   name=f"r{i}.json")
            self.assertEqual(rc, 0)
            if i < 3:
                self.assertEqual(self.inbox_names(), [])
        self.assertEqual(len(self.inbox_names()), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "resource_sentinel")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "resource_sentinel")
        self.assertEqual(rec["signal"], "cpu_saturation_sustained")
        self.assertEqual(rec["severity"], "high")
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "cpu_saturation_sustained")
        self.assertEqual(brief["status"], "no_inference")


class JobWatcherEndToEndTest(WatcherFixture):
    folder = "job-watcher"
    mod = JW
    sensor = "job_watcher"
    secret = JW_SECRET
    key_id = "job-key"

    def test_failure_cluster_files_and_wakes_a_brief(self):
        records = [_obs(f"c{i}", key=f"key-{i}", exit_code=1,
                        saved_at=T0 + 950 + i * 10) for i in range(3)]
        rc = self.run_producer(_jw_readings(records))
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "job_watcher")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "job_watcher")
        self.assertEqual(rec["signal"], "failure_cluster")
        self.assertEqual(rec["severity"], "high")
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "failure_cluster")
        self.assertEqual(brief["status"], "no_inference")


if __name__ == "__main__":
    unittest.main()
