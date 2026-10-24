"""Latency Post: the example sense that probes targets.

Pins the Latency Post example
(extensions/latency-post/): the manifest through the
real extension loader, and the pure decide() state machine --
a down target files once, recovery is silent, a spike files
once against the median of its prior samples and re-files
after an in-band reading clears it.

No live network anywhere: decide() is driven with fixture
readings dicts, exactly the shape read_live() returns.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "extensions", "latency-post")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "latency_post_example", os.path.join(EXAMPLE_DIR, "latency_post.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LP = _load_example_module()

NOW = 1_800_000_000.0
TARGET = "192.0.2.10:443"


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _probe(target=TARGET, ok=True, latency_ms=10.0, error=None):
    probe = {"target": target, "ok": ok, "latency_ms": latency_ms}
    if error is not None:
        probe["error"] = error
    return probe


def _readings(*probes):
    return {"now": NOW, "probes": list(probes)}


def _state_with_samples(samples, target=TARGET):
    return {"targets": {target: {"samples": list(samples),
                                 "down": False, "spike_active": False}}}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "latency_post")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["latency_spike", "target_down"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "latency-post"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("latency_post", registry)
        self.assertEqual(registry["latency_post"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return LP.decide(readings, manifest or _manifest(),
                         state if state is not None else {})

    def test_target_down_fires_high_with_key_details(self):
        alerts, state = self.decide(
            _readings(_probe(ok=False, latency_ms=None, error="timeout")))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "latency_post")
        self.assertEqual(alert["signal"], "target_down")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["target"], TARGET)
        self.assertEqual(alert["detail"]["error"], "timeout")
        self.assertTrue(state["targets"][TARGET]["down"])

    def test_refused_target_is_down(self):
        alerts, _state = self.decide(
            _readings(_probe(ok=False, latency_ms=None, error="refused")))
        self.assertEqual([a["signal"] for a in alerts], ["target_down"])
        self.assertEqual(alerts[0]["detail"]["error"], "refused")

    def test_latency_spike_fires_medium_with_key_details(self):
        state = _state_with_samples([10.0, 11.0, 9.0, 10.0])
        alerts, state = self.decide(_readings(_probe(latency_ms=300.0)),
                                    state=state)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["signal"], "latency_spike")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["target"], TARGET)
        self.assertEqual(alert["detail"]["latency_ms"], 300.0)
        self.assertEqual(alert["detail"]["median_ms"], 10.0)
        self.assertTrue(state["targets"][TARGET]["spike_active"])

    def test_spike_needs_the_factor_not_just_the_floor(self):
        # Median 100: the factor threshold is 300, above the
        # 250 floor, so 260 -- over the floor alone -- is quiet.
        state = _state_with_samples([100.0, 100.0, 100.0])
        alerts, _state = self.decide(_readings(_probe(latency_ms=260.0)),
                                     state=state)
        self.assertEqual(alerts, [])
        state = _state_with_samples([100.0, 100.0, 100.0])
        alerts, _state = self.decide(_readings(_probe(latency_ms=400.0)),
                                     state=state)
        self.assertEqual([a["signal"] for a in alerts], ["latency_spike"])

    def test_spike_needs_three_prior_samples(self):
        state = _state_with_samples([10.0, 10.0])
        alerts, _state = self.decide(_readings(_probe(latency_ms=900.0)),
                                     state=state)
        self.assertEqual(alerts, [])

    def test_quiet_case_files_nothing(self):
        alerts, state = self.decide(_readings(_probe(latency_ms=12.0)))
        self.assertEqual(alerts, [])
        self.assertEqual(state["targets"][TARGET]["samples"], [12.0])
        alerts, _state = self.decide(_readings())
        self.assertEqual(alerts, [])

    def test_same_readings_twice_files_nothing_second_time(self):
        readings = _readings(_probe(ok=False, latency_ms=None,
                                    error="timeout"))
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])
        # Same discipline for a spike reading.
        state = _state_with_samples([10.0, 11.0, 9.0, 10.0])
        readings = _readings(_probe(latency_ms=300.0))
        alerts, state = self.decide(readings, state=state)
        self.assertEqual(len(alerts), 1)
        alerts, state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])

    def test_recovery_is_silent_and_refiles_on_next_outage(self):
        readings = _readings(_probe(ok=False, latency_ms=None,
                                    error="timeout"))
        _alerts, state = self.decide(readings)
        alerts, state = self.decide(_readings(_probe(latency_ms=10.0)),
                                    state=state)
        self.assertEqual(alerts, [])  # no recovery signal is declared
        self.assertFalse(state["targets"][TARGET]["down"])
        alerts, _state = self.decide(readings, state=state)
        self.assertEqual([a["signal"] for a in alerts], ["target_down"])

    def test_moved_reading_refiles_a_spike(self):
        state = _state_with_samples([10.0, 11.0, 9.0, 10.0])
        alerts, state = self.decide(_readings(_probe(latency_ms=300.0)),
                                    state=state)
        self.assertEqual(len(alerts), 1)
        # An in-band reading clears the spike flag quietly...
        alerts, state = self.decide(_readings(_probe(latency_ms=12.0)),
                                    state=state)
        self.assertEqual(alerts, [])
        self.assertFalse(state["targets"][TARGET]["spike_active"])
        # ...so a fresh, moved spike files again.
        alerts, state = self.decide(_readings(_probe(latency_ms=450.0)),
                                    state=state)
        self.assertEqual([a["signal"] for a in alerts], ["latency_spike"])
        self.assertEqual(alerts[0]["detail"]["latency_ms"], 450.0)

    def test_samples_are_capped_at_twenty(self):
        state = _state_with_samples([float(i) for i in range(20)])
        _alerts, state = self.decide(_readings(_probe(latency_ms=5.0)),
                                     state=state)
        samples = state["targets"][TARGET]["samples"]
        self.assertEqual(len(samples), 20)
        self.assertEqual(samples[-1], 5.0)

    def test_unusable_probes_are_ignored(self):
        alerts, state = self.decide({"now": NOW, "probes": [
            None, {}, {"target": TARGET}, {"target": 7, "ok": True},
            {"target": TARGET, "ok": "yes"}]})
        self.assertEqual(alerts, [])
        self.assertEqual(state, {"targets": {}})


class MainTest(unittest.TestCase):
    def test_readings_fixture_prints_alerts_and_saves_state(self):
        with tempfile.TemporaryDirectory() as d:
            readings_path = os.path.join(d, "readings.json")
            state_path = os.path.join(d, "state.json")
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump(_readings(_probe(ok=False, latency_ms=None,
                                           error="timeout")), fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = LP.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["target_down"])
            with open(state_path, encoding="utf-8") as fh:
                self.assertTrue(json.load(fh)["targets"][TARGET]["down"])
            # A second pass over the same fixture is quiet, and
            # an unreadable readings file exits 2.
            out = io.StringIO()
            with redirect_stdout(out):
                rc = LP.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(
                LP.main(["--readings", os.path.join(d, "missing.json"),
                         "--state", state_path]), 2)


if __name__ == "__main__":
    unittest.main()
