"""Latency Post: the example sense that probes targets.

Pins the Latency Post example
(runner/extensions/latency-post/): the manifest through the
real extension loader, and the pure decide() state machine --
a down target files once, recovery is silent, a spike files
once against the median of its prior samples and re-files
after an in-band reading clears it.

No live network anywhere: decide() is driven with fixture
readings dicts, exactly the shape read_live() returns. The
probe tests are the one exception, and they stay on
loopback sockets.
"""
import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "latency-post")


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


class ProbeTest(unittest.TestCase):
    """Queue A: `_probe` never ran anywhere (coverage run
    40180268696: 19 lines on both platforms) -- every other
    test fixtures the readings it returns. Its seam is one
    timed TCP connect. Loopback produces the success
    outcome for real (a listening port connects, ok, with
    a latency). The failure outcomes are scripted at the
    seam: what a real closed port does is the host's
    choice, not the probe's -- the Windows CI runner's
    firewall drops the SYN and the connect times out
    instead of refusing (coverage run 40183585961, where
    the loopback refusal test failed 'timeout' !=
    'refused'). Scripted: a refusal, which for the gateway
    still proves reachability (ok, with a latency) and for
    a configured target does not (not ok, "refused", no
    sample); a timeout; and the generic socket error,
    including an error with no message answering its type
    name.
    """

    def test_a_listening_port_connects_with_a_latency(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            got = LP._probe("127.0.0.1", port, 2.0,
                            is_gateway=False)
        self.assertEqual(got["target"], "127.0.0.1:%d" % port)
        self.assertTrue(got["ok"])
        self.assertIsInstance(got["latency_ms"], float)
        self.assertGreaterEqual(got["latency_ms"], 0.0)
        self.assertIsNone(got["error"])

    def test_a_refusal_is_a_failure_for_a_target(self):
        with mock.patch.object(
                LP.socket, "create_connection",
                side_effect=ConnectionRefusedError("refused")):
            got = LP._probe("192.0.2.10", 443, 0.1,
                            is_gateway=False)
        self.assertFalse(got["ok"])
        self.assertIsNone(got["latency_ms"])
        self.assertEqual(got["error"], "refused")

    def test_a_refusal_still_proves_the_gateway_answered(self):
        with mock.patch.object(
                LP.socket, "create_connection",
                side_effect=ConnectionRefusedError("refused")):
            got = LP._probe("192.0.2.10", 443, 0.1,
                            is_gateway=True)
        self.assertTrue(got["ok"])
        self.assertIsInstance(got["latency_ms"], float)
        self.assertIsNone(got["error"])

    def test_a_timeout_and_a_bare_socket_error(self):
        with mock.patch.object(
                LP.socket, "create_connection",
                side_effect=socket.timeout("timed out")):
            got = LP._probe("192.0.2.10", 443, 0.1,
                            is_gateway=False)
        self.assertFalse(got["ok"])
        self.assertIsNone(got["latency_ms"])
        self.assertEqual(got["error"], "timeout")
        with mock.patch.object(
                LP.socket, "create_connection",
                side_effect=OSError("no route")):
            got = LP._probe("192.0.2.10", 443, 0.1,
                            is_gateway=False)
        self.assertEqual(got["error"], "no route")
        with mock.patch.object(
                LP.socket, "create_connection",
                side_effect=OSError()):
            got = LP._probe("192.0.2.10", 443, 0.1,
                            is_gateway=False)
        self.assertEqual(got["error"], "OSError")

    def test_a_close_that_fails_keeps_the_sample(self):
        class Conn:
            def close(self):
                raise OSError("already gone")

        with mock.patch.object(
                LP.socket, "create_connection",
                return_value=Conn()):
            got = LP._probe("192.0.2.10", 443, 0.1,
                            is_gateway=False)
        self.assertTrue(got["ok"])
        self.assertIsInstance(got["latency_ms"], float)
        self.assertIsNone(got["error"])


class GatewayTest(unittest.TestCase):
    """Queue A: `_read_default_gateway` never ran anywhere
    (coverage run 40180268696) -- read_live's tests fixture
    its answer. Its seam is one file, /proc/net/route, so
    the file is scripted: the default route's gateway is
    little-endian hex and comes back dotted; a table with
    no default route, a gateway that is not hex, and one
    of the wrong length all answer None; short lines are
    skipped; a missing file answers None, never an error
    -- the docstring's guard, on every platform (on
    Windows the file is simply never there).
    """

    HEADER = "Iface\tDestination\tGateway\tFlags\tRefCnt\t" \
             "Use\tMetric\tMask\tMTU\tWindow\tIRTT"

    def _gateway(self, text):
        opener = mock.mock_open(read_data=text)
        with mock.patch("builtins.open", opener):
            return LP._read_default_gateway()

    def test_the_default_routes_gateway_comes_back_dotted(self):
        text = "\n".join([
            self.HEADER,
            "eth0\t0001A8C0\t00000000\t0001\t0\t0\t0\t00FFFFFF"
            "\t0\t0\t0",
            "eth0\t00000000\t0101A8C0\t0003\t0\t0\t0\t00000000"
            "\t0\t0\t0",
        ])
        self.assertEqual(self._gateway(text), "192.168.1.1")

    def test_no_default_route_answers_none(self):
        text = "\n".join([
            self.HEADER,
            "eth0\t0001A8C0\t0101A8C0\t0001\t0\t0\t0\t00FFFFFF"
            "\t0\t0\t0",
        ])
        self.assertIsNone(self._gateway(text))

    def test_an_unparseable_gateway_answers_none(self):
        text = "\n".join([
            self.HEADER,
            "eth0\t00000000\tZZZZZZZZ\t0003\t0\t0\t0\t00000000",
        ])
        self.assertIsNone(self._gateway(text))
        text = "\n".join([
            self.HEADER,
            "eth0\t00000000\t0101A8\t0003\t0\t0\t0\t00000000",
        ])
        self.assertIsNone(self._gateway(text))

    def test_short_lines_are_skipped(self):
        text = "\n".join([
            self.HEADER,
            "eth0\t00000000",
            "eth0\t00000000\t0101A8C0\t0003",
        ])
        self.assertEqual(self._gateway(text), "192.168.1.1")

    def test_no_route_file_answers_none(self):
        with mock.patch("builtins.open",
                        side_effect=OSError("no /proc here")):
            self.assertIsNone(LP._read_default_gateway())

    def test_the_host_answers_none_or_a_dotted_quad(self):
        got = LP._read_default_gateway()
        if got is not None:
            parts = got.split(".")
            self.assertEqual(len(parts), 4)
            for part in parts:
                self.assertTrue(0 <= int(part) <= 255)


class LatencyMainDeliveryTest(unittest.TestCase):
    """Queue A refill: latency-post main's live branch and
    local-delivery legs (coverage run 40187685363: 7
    lines on both platforms). Same contract as every
    sense main: the live snapshot is taken when no
    readings file is given (read_live itself is covered
    by ProbeTest/GatewayTest; here it is stubbed so the
    branch main takes is what is under test); delivery
    not set up is exit 2; a short delivery is exit 2
    with the state unwritten, so the next pass reports
    the conditions again.
    """

    ENV = "HP_LAT_SECRET"

    def _drive(self, d, extra, readings=None):
        state = os.path.join(d, "state.json")
        argv = ["--state", state, "--secret-env", self.ENV]
        if readings is not None:
            path = os.path.join(d, "readings.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(readings, fh)
            argv += ["--readings", path]
        err = io.StringIO()
        with redirect_stderr(err):
            rc = LP.main(argv + extra)
        return rc, state, err.getvalue()

    def _alert_readings(self):
        return _readings(_probe(ok=False, latency_ms=None,
                                error="timeout"))

    def test_the_live_branch_runs_without_a_readings_file(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    LP, "read_live",
                    return_value=self._alert_readings()):
                rc, state, _err = self._drive(d, [])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(state))

    def test_local_delivery_success_writes_state(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ[self.ENV] = "ab" * 32
            try:
                rc, state, _err = self._drive(
                    d, ["--local-dir", d],
                    readings=self._alert_readings())
            finally:
                os.environ.pop(self.ENV, None)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(state))
            inbox = os.path.join(d, "local-inbox")
            self.assertEqual(len(os.listdir(inbox)), 1)

    def test_local_delivery_not_set_up_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ.pop(self.ENV, None)
            rc, state, _err = self._drive(
                d, ["--local-dir", d],
                readings=self._alert_readings())
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
                    d, ["--local-dir", blocker],
                    readings=self._alert_readings())
            finally:
                os.environ.pop(self.ENV, None)
            self.assertEqual(rc, 2)
            self.assertIn("state not saved", err)
            self.assertFalse(os.path.exists(state))


if __name__ == "__main__":
    unittest.main()
