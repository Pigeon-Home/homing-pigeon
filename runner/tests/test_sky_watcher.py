"""Sky Watcher: the example sense that files ISS passes.

Pins the Sky Watcher example (runner/extensions/sky-watcher/)
the way test_local_signals.py pins Lab Results: the geometry
against known values, the pass state machine across scripted
great-circle tracks (the shape a real ground track takes over
one pass), the manifest through the real extension loader, and
one end-to-end run -- producer replays a recorded pass into the
local inbox, the real ingest files it, and the high-severity
bright_pass wakes the gate and files a brief.

No live network and no live model anywhere: samples are
synthetic feed responses, and the end-to-end config has no
inference, so the wake brief is the deterministic fallback.
"""
import importlib.util
import io
import json
import math
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from contextlib import redirect_stdout
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.oracle import senses as S  # noqa: E402
from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "sky-watcher")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
SKY_SECRET = "3f7a1c9e5b2d48a0f6c1e9b3d5a7082" + "c4e6f1a9b0d2e4f6a8c1b3d5e7f9a0b2"

NIGHT_TS = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc).timestamp()
DAY_TS = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc).timestamp()


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "sky_watcher_example", os.path.join(EXAMPLE_DIR, "sky_watcher.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SW = _load_example_module()


def _manifest(observer=True):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    if observer:
        manifest["tunables"] = dict(manifest["tunables"],
                                    observer_lat=0.0, observer_lon=0.0)
    return manifest


def _gc_track(psi_min_deg, ts0, sunlit=True, alt_km=420.0,
              step_deg=3.9, span_deg=70.0):
    """Feed-shaped samples along a great circle.

    The track's closest approach to an observer at (0, 0) is
    psi_min_deg of central angle, so its culmination elevation
    is elevation_deg(psi_min_deg) by construction -- the shape
    a real ISS ground track takes over one pass. Steps of
    3.9 degrees are one 60-second poll at the station's rate.
    """
    psi = math.radians(psi_min_deg)
    p0 = (math.cos(psi), 0.0, -math.sin(psi))
    samples = []
    theta = -span_deg
    i = 0
    while theta <= span_deg:
        t = math.radians(theta)
        v = (math.cos(t) * p0[0], math.sin(t),
             math.cos(t) * p0[2])
        lat = math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))
        lon = math.degrees(math.atan2(v[1], v[0]))
        samples.append({
            "latitude": lat, "longitude": lon, "altitude": alt_km,
            "velocity": 27576.0,
            "visibility": "daylight" if sunlit else "eclipsed",
            "timestamp": ts0 + i * 60,
        })
        theta += step_deg
        i += 1
    return samples


def _run_track(feed_samples, manifest=None, state=None):
    """Drive samples through update(); returns (alerts, state)."""
    manifest = manifest or _manifest()
    state = state or {}
    alerts = []
    for raw in feed_samples:
        sample = SW.sample_from_feed(raw)
        fired, state = SW.update(sample, manifest, state)
        alerts.extend(fired)
    return alerts, state


class GeometryTest(unittest.TestCase):
    def test_overhead_is_90_and_horizon_is_0(self):
        self.assertAlmostEqual(SW.elevation_deg(0.0, 420.0), 90.0,
                               places=6)
        horizon = math.acos(6371.0 / (6371.0 + 420.0))
        self.assertAlmostEqual(SW.elevation_deg(horizon, 420.0), 0.0,
                               delta=0.05)

    def test_elevation_at_ten_degrees_central(self):
        # atan2(cos10 - 6371/6791, sin10), computed independently.
        self.assertAlmostEqual(
            SW.elevation_deg(math.radians(10), 420.0), 15.04, delta=0.05)

    def test_psi_for_elevation_inverts_elevation(self):
        for el in (0.0, 10.0, 33.0, 65.0, 89.0):
            psi = SW.psi_for_elevation_deg(el, 420.0)
            self.assertAlmostEqual(SW.elevation_deg(psi, 420.0), el,
                                   delta=0.01, msg=f"el={el}")

    def test_station_geometry_components(self):
        psi, el, dist = SW.station_geometry(0.0, 0.0, 0.0, 10.0, 420.0)
        self.assertAlmostEqual(psi, math.radians(10), delta=1e-9)
        self.assertAlmostEqual(el, 15.04, delta=0.05)
        self.assertAlmostEqual(dist, 6371.0 * math.radians(10),
                               delta=1.0)

    def test_culmination_estimate_on_great_circles(self):
        for psi_min, want in ((0.0, 90.0), (9.0, 17.56), (16.0, 4.79)):
            track = _gc_track(psi_min, NIGHT_TS)
            samples = [SW.sample_from_feed(r) for r in track]
            mid = len(samples) // 2
            est = SW.culmination_estimate_deg(
                samples[mid - 1], samples[mid], 0.0, 0.0)
            self.assertAlmostEqual(est, want, delta=0.5,
                                   msg=f"psi_min={psi_min}")

    def test_culmination_needs_two_distinct_samples(self):
        track = _gc_track(0.0, NIGHT_TS)
        sample = SW.sample_from_feed(track[0])
        self.assertIsNone(
            SW.culmination_estimate_deg(None, sample, 0.0, 0.0))
        self.assertIsNone(
            SW.culmination_estimate_deg(sample, sample, 0.0, 0.0))


class SunTest(unittest.TestCase):
    def test_equator_midnight_and_noon(self):
        self.assertLess(SW.sun_elevation_deg(0.0, 0.0, NIGHT_TS), -20.0)
        self.assertGreater(SW.sun_elevation_deg(0.0, 0.0, DAY_TS), 20.0)

    def test_london_solstice_and_winter_noons(self):
        summer = datetime(2026, 6, 21, 12, 0,
                          tzinfo=timezone.utc).timestamp()
        winter = datetime(2026, 12, 21, 12, 0,
                          tzinfo=timezone.utc).timestamp()
        self.assertGreater(
            SW.sun_elevation_deg(51.5, 0.0, summer), 55.0)
        el = SW.sun_elevation_deg(51.5, 0.0, winter)
        self.assertGreater(el, 5.0)
        self.assertLess(el, 20.0)


class FeedSampleTest(unittest.TestCase):
    def test_real_feed_shape(self):
        raw = {"name": "iss", "id": 25544, "latitude": -9.65,
               "longitude": 177.47, "altitude": 422.3,
               "velocity": 27570.9, "visibility": "daylight",
               "footprint": 4519.2, "timestamp": 1792375113,
               "units": "kilometers"}
        s = SW.sample_from_feed(raw)
        self.assertEqual(s["lat"], -9.65)
        self.assertEqual(s["lon"], 177.47)
        self.assertEqual(s["alt_km"], 422.3)
        self.assertEqual(s["velocity_kmh"], 27570.9)
        self.assertIs(s["sunlit"], True)
        self.assertEqual(s["ts"], 1792375113.0)

    def test_fetch_position_reads_the_feed(self):
        # Queue A refill: fetch_position's body (coverage
        # run 40189711740: 4 lines) -- the one live seam,
        # driven here with the transport faked: the
        # request carries the watcher's user agent, the
        # body parses as a feed payload, and the sample
        # is sample_from_feed's.
        import io
        import json as _json
        from unittest import mock
        raw = {"name": "iss", "id": 25544, "latitude": -9.65,
               "longitude": 177.47, "altitude": 422.3,
               "velocity": 27570.9, "visibility": "daylight",
               "footprint": 4519.2, "timestamp": 1792375113,
               "units": "kilometers"}
        seen = {}

        def fake_urlopen(req, timeout=None):
            seen["url"] = req.full_url
            seen["ua"] = req.headers.get("User-agent")
            seen["timeout"] = timeout
            return io.BytesIO(_json.dumps(raw).encode("utf-8"))

        with mock.patch.object(SW.urllib.request, "urlopen",
                               fake_urlopen):
            sample = SW.fetch_position("http://feed.invalid/iss")
        self.assertEqual(sample["lat"], -9.65)
        self.assertEqual(sample["alt_km"], 422.3)
        self.assertEqual(seen["url"], "http://feed.invalid/iss")
        self.assertIn("homing-pigeon-sky-watcher",
                      seen["ua"])
        self.assertEqual(seen["timeout"], 10)

    def test_eclipsed_and_missing_visibility(self):
        base = {"latitude": 0.0, "longitude": 0.0, "altitude": 420.0,
                "timestamp": 1000}
        self.assertIs(SW.sample_from_feed(
            dict(base, visibility="eclipsed"))["sunlit"], False)
        self.assertIsNone(SW.sample_from_feed(base)["sunlit"])

    def test_miles_units_convert(self):
        s = SW.sample_from_feed(
            {"latitude": 0.0, "longitude": 0.0, "altitude": 261.0,
             "velocity": 17130.0, "timestamp": 1000, "units": "miles"})
        self.assertAlmostEqual(s["alt_km"], 261.0 * 1.609344, places=6)
        self.assertAlmostEqual(s["velocity_kmh"], 17130.0 * 1.609344,
                               places=4)

    def test_unusable_responses_answer_none(self):
        for raw in (None, "iss", {}, {"latitude": 0.0},
                    {"latitude": "0", "longitude": 0.0,
                     "altitude": 420.0, "timestamp": 1}):
            self.assertIsNone(SW.sample_from_feed(raw), raw)


class PassStateMachineTest(unittest.TestCase):
    def signals(self, feed_samples, **kw):
        alerts, state = _run_track(feed_samples, **kw)
        return [a["signal"] for a in alerts], alerts, state

    def test_zenith_pass_fires_each_stage_once_in_order(self):
        seq, alerts, state = self.signals(_gc_track(0.0, NIGHT_TS))
        self.assertEqual(seq, ["station_approaching",
                               "visible_pass_starting", "bright_pass"])
        sev = {a["signal"]: a["severity"] for a in alerts}
        self.assertEqual(sev, {"station_approaching": "info",
                               "visible_pass_starting": "medium",
                               "bright_pass": "high"})
        for a in alerts:
            self.assertEqual(a["sensor"], "sky_watcher")
        self.assertEqual(state["stage"], "out")
        self.assertEqual(state["pass_id"], 1)

    def test_visible_detail_carries_the_lead_and_culmination(self):
        _seq, alerts, _state = self.signals(_gc_track(0.0, NIGHT_TS))
        visible = alerts[1]
        self.assertGreater(visible["detail"]["starts_in_sec"], 0)
        self.assertLessEqual(visible["detail"]["starts_in_sec"], 600)
        bright = alerts[2]
        self.assertGreaterEqual(bright["detail"]["culmination_deg"],
                                65.0)

    def test_second_orbit_fires_the_whole_pass_again(self):
        _seq, _a, state = self.signals(_gc_track(0.0, NIGHT_TS))
        seq2, _a2, state2 = self.signals(
            _gc_track(0.0, NIGHT_TS + 5400), state=state)
        self.assertEqual(seq2, ["station_approaching",
                                "visible_pass_starting", "bright_pass"])
        self.assertEqual(state2["pass_id"], 2)

    def test_repeated_sample_mid_pass_refires_nothing(self):
        track = _gc_track(0.0, NIGHT_TS)
        samples = [SW.sample_from_feed(r) for r in track]
        manifest = _manifest()
        state = {}
        seen = []
        for s in samples[:8]:  # through corridor entry
            fired, state = SW.update(s, manifest, state)
            seen.extend(a["signal"] for a in fired)
        # A zenith pass meets every condition at corridor entry
        # (the estimate is already 90 deg and the window opens
        # inside the lead), so all three stages have filed.
        self.assertEqual(seen, ["station_approaching",
                                "visible_pass_starting", "bright_pass"])
        # The same position reported again (a duplicated poll):
        # the pass is already open and every stage already filed.
        for bump in (60, 120, 180):
            dupe = dict(samples[7])
            dupe["ts"] = samples[7]["ts"] + bump
            fired, state = SW.update(dupe, manifest, state)
            self.assertEqual(fired, [])
        self.assertEqual(state["stage"], "visible")

    def test_visible_but_not_bright_pass(self):
        seq, _a, _s = self.signals(_gc_track(9.0, NIGHT_TS))
        self.assertEqual(seq, ["station_approaching",
                               "visible_pass_starting"])

    def test_low_pass_never_reaches_visible_or_bright(self):
        seq, _a, _s = self.signals(_gc_track(16.0, NIGHT_TS))
        self.assertEqual(seq, ["station_approaching"])

    def test_eclipsed_pass_files_approaching_only(self):
        seq, _a, _s = self.signals(
            _gc_track(0.0, NIGHT_TS, sunlit=False))
        self.assertEqual(seq, ["station_approaching"])

    def test_daylight_sky_files_approaching_only(self):
        seq, _a, _s = self.signals(_gc_track(0.0, DAY_TS))
        self.assertEqual(seq, ["station_approaching"])

    def test_unknown_sunlit_never_files_visible(self):
        track = _gc_track(0.0, NIGHT_TS)
        for raw in track:
            del raw["visibility"]
        seq, _a, _s = self.signals(track)
        self.assertEqual(seq, ["station_approaching"])

    def test_no_observer_no_alerts(self):
        manifest = _manifest(observer=False)
        alerts, _state = _run_track(_gc_track(0.0, NIGHT_TS),
                                    manifest=manifest)
        self.assertEqual(alerts, [])

    def test_bad_samples_are_ignored(self):
        state = {}
        for bad in (None, {}, {"lat": "x"}, {"lat": 0.0, "lon": 0.0,
                                            "alt_km": -1.0, "ts": 5}):
            alerts, state = SW.update(bad, _manifest(), state)
            self.assertEqual(alerts, [])
        self.assertEqual(state["stage"], "out")

    def test_long_silence_starts_a_fresh_pass(self):
        track = _gc_track(0.0, NIGHT_TS)
        samples = [SW.sample_from_feed(r) for r in track]
        manifest = _manifest()
        state = {}
        for s in samples[:8]:  # well into the corridor
            _a, state = SW.update(s, manifest, state)
        self.assertNotEqual(state["stage"], "out")
        self.assertEqual(state["pass_id"], 1)
        resumed = dict(samples[10])
        resumed["ts"] = samples[7]["ts"] + 7200  # two hours later
        alerts, state = SW.update(resumed, manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["station_approaching"])
        self.assertEqual(state["pass_id"], 2)


class ManifestLoaderTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest(observer=False))
        self.assertEqual(clean["name"], "sky_watcher")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["bright_pass", "station_approaching",
             "visible_pass_starting"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "sky-watcher"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("sky_watcher", registry)
        self.assertEqual(registry["sky_watcher"]["version"], "0.1.0")


class SkyFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "sky-watcher"))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {"sky-key": SKY_SECRET},
            "key_policies": {
                "sky-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "sky_watcher": {"enabled": True, "key_id": "sky-key",
                                "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.state_path = os.path.join(self._tmp.name, "state.json")
        # The shipped manifest leaves the observer unset (it
        # files nothing until configured); producer tests run
        # against a copy whose observer is the test's sky.
        self.manifest_path = os.path.join(self._tmp.name,
                                          "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(_manifest(), fh)

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
    def samples_file(self, feed_samples, name="samples.json"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(feed_samples, fh)
        return path

    def run_producer(self, feed_samples, with_secret=True,
                     name="samples.json"):
        env = {"HOMING_PIGEON_SENSOR_SECRET": SKY_SECRET} \
            if with_secret else {}
        with unittest.mock.patch.dict(os.environ, env):
            if not with_secret:
                os.environ.pop("HOMING_PIGEON_SENSOR_SECRET", None)
            return SW.main(["--manifest", self.manifest_path,
                            "--samples",
                            self.samples_file(feed_samples, name),
                            "--local-dir", self.base,
                            "--key-id", "sky-key",
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


class ProducerTest(SkyFixture):
    def test_replay_prints_the_pass_in_order(self):
        path = self.samples_file(_gc_track(0.0, NIGHT_TS))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = SW.main(["--manifest", self.manifest_path,
                          "--samples", path,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        printed = [json.loads(ln) for ln in
                   out.getvalue().splitlines() if ln.strip()]
        self.assertEqual([p["signal"] for p in printed],
                         ["station_approaching",
                          "visible_pass_starting", "bright_pass"])
        with open(self.state_path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["pass_id"], 1)
        self.assertEqual(saved["stage"], "out")

    def test_failed_delivery_leaves_the_state_unwritten(self):
        rc = self.run_producer(_gc_track(0.0, NIGHT_TS),
                               with_secret=False)
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.state_path))
        self.assertEqual(self.inbox_names(), [])
        # With the secret present the same pass files in full:
        # nothing was marked reported by the failed pass.
        rc = self.run_producer(_gc_track(0.0, NIGHT_TS))
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 3)

    def test_feed_outage_is_a_quiet_noop(self):
        manifest_path = os.path.join(self._tmp.name, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(_manifest(), fh)
        out = io.StringIO()
        with unittest.mock.patch.object(
                SW, "fetch_position",
                side_effect=OSError("no route to host")):
            with redirect_stdout(out):
                rc = SW.main(["--manifest", manifest_path,
                              "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")
        self.assertFalse(os.path.exists(self.state_path))

    def test_no_observer_files_nothing_and_says_so(self):
        path = self.samples_file(_gc_track(0.0, NIGHT_TS))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = SW.main(["--samples", path,
                          "--state", self.state_path])
        # The shipped manifest has observer_lat/lon null.
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")


class EndToEndTest(SkyFixture):
    def test_bright_pass_files_and_wakes_a_brief(self):
        rc = self.run_producer(_gc_track(0.0, NIGHT_TS))
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 3)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 3)
        self.assertEqual(self.inbox_names(), [])
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 3)
        manifest = _manifest(observer=False)
        declared = {s["name"]: s["description"]
                    for s in manifest["signals"]}
        by_signal = {}
        for rec in recs:
            self.assertEqual(rec["sensor"], "sky_watcher")
            self.assertEqual(rec["source"], "local")
            self.assertEqual(rec["extension"], "sky_watcher")
            self.assertEqual(rec["extension_version"], "0.1.0")
            self.assertEqual(rec["signal_description"],
                             declared[rec["signal"]])
            by_signal[rec["signal"]] = rec
        self.assertEqual(sorted(by_signal),
                         ["bright_pass", "station_approaching",
                          "visible_pass_starting"])
        self.assertEqual(by_signal["bright_pass"]["severity"], "high")
        # Only the high signal wakes; with no inference configured
        # the brief is the deterministic fallback.
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "bright_pass")
        self.assertEqual(brief["sensor"], "sky_watcher")
        self.assertEqual(brief["status"], "no_inference")

    def test_second_pass_files_again_but_cooldown_holds_the_wake(self):
        self.assertEqual(self.run_producer(_gc_track(0.0, NIGHT_TS)), 0)
        R._scan_local_inbox(self.cfg, self.base)
        self.wait_briefs(1)
        deadline = time.time() + 5
        while R._LOCAL_WAKE_INFLIGHT and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(
            self.run_producer(_gc_track(0.0, NIGHT_TS + 5400),
                              name="samples2.json"), 0)
        R._scan_local_inbox(self.cfg, self.base)
        self.assertEqual(len(S.load_alerts(self.base)), 6)
        time.sleep(0.3)
        self.assertEqual(len(self.brief_lines()), 1)


if __name__ == "__main__":
    unittest.main()
