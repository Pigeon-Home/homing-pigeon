"""Port Watch: the example sense that diffs listening sockets.

Pins the Port Watch example (runner/extensions/port-watch/):
the manifest through the real extension loader, and the pure
decide() diff -- the first pass learns quietly, a new listener
files once at the severity its binding earns, high_only
suppresses the medium signal but still absorbs the listener,
and a vanished listener that returns files again.

No live sockets anywhere: decide() is driven with fixture
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

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "port-watch")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "port_watch_example", os.path.join(EXAMPLE_DIR, "port_watch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PW = _load_example_module()

NOW = 1_800_000_000.0
BASE = {"proto": "tcp", "addr": "127.0.0.1", "port": 22}


def _manifest(**tunable_overrides):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["tunables"] = dict(manifest["tunables"], **tunable_overrides)
    return manifest


def _readings(*listeners):
    return {"now": NOW, "listeners": [dict(x) for x in listeners]}


def _learned_state(*listeners):
    """A state whose baseline is exactly `listeners`."""
    _alerts, state = PW.decide(_readings(*listeners), _manifest(), {})
    return state


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "port_watch")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["exposed_listener", "new_listener"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "port-watch"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("port_watch", registry)
        self.assertEqual(registry["port_watch"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def test_first_pass_learns_quietly(self):
        alerts, state = PW.decide(
            _readings(BASE, {"proto": "tcp", "addr": "0.0.0.0",
                             "port": 8080}),
            _manifest(), {})
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        self.assertEqual(len(state["seen"]), 2)

    def test_first_pass_files_when_learning_is_off(self):
        manifest = _manifest(learn_first_pass=False)
        alerts, _state = PW.decide(_readings(BASE), manifest, {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["exposed_listener"])  # port 22 < 1024

    def test_new_listener_fires_medium_with_key_details(self):
        state = _learned_state(BASE)
        new = {"proto": "tcp", "addr": "127.0.0.1", "port": 8080}
        alerts, _state = PW.decide(_readings(BASE, new), _manifest(), state)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "port_watch")
        self.assertEqual(alert["signal"], "new_listener")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"],
                         {"proto": "tcp", "addr": "127.0.0.1",
                          "port": 8080})

    def test_exposed_listener_fires_high_for_wildcard_and_low_port(self):
        cases = [
            {"proto": "tcp", "addr": "0.0.0.0", "port": 8080},
            {"proto": "tcp", "addr": "::", "port": 8080},
            {"proto": "udp", "addr": "127.0.0.1", "port": 53},
        ]
        for new in cases:
            with self.subTest(new=new):
                state = _learned_state(BASE)
                alerts, _state = PW.decide(
                    _readings(BASE, new), _manifest(), state)
                self.assertEqual(len(alerts), 1)
                self.assertEqual(alerts[0]["signal"], "exposed_listener")
                self.assertEqual(alerts[0]["severity"], "high")
                self.assertEqual(alerts[0]["detail"]["proto"],
                                 new["proto"])
                self.assertEqual(alerts[0]["detail"]["addr"], new["addr"])
                self.assertEqual(alerts[0]["detail"]["port"], new["port"])

    def test_quiet_case_files_nothing(self):
        state = _learned_state(BASE)
        alerts, _state = PW.decide(_readings(BASE), _manifest(), state)
        self.assertEqual(alerts, [])
        alerts, _state = PW.decide(_readings(), _manifest(), state)
        self.assertEqual(alerts, [])

    def test_same_readings_twice_files_nothing_second_time(self):
        state = _learned_state(BASE)
        new = {"proto": "tcp", "addr": "127.0.0.1", "port": 8080}
        readings = _readings(BASE, new)
        alerts, state = PW.decide(readings, _manifest(), state)
        self.assertEqual(len(alerts), 1)
        alerts, _state = PW.decide(readings, _manifest(), state)
        self.assertEqual(alerts, [])

    def test_moved_reading_files_the_next_new_listener(self):
        state = _learned_state(BASE)
        first = {"proto": "tcp", "addr": "127.0.0.1", "port": 8080}
        alerts, state = PW.decide(_readings(BASE, first),
                                  _manifest(), state)
        self.assertEqual(len(alerts), 1)
        second = {"proto": "udp", "addr": "127.0.0.1", "port": 5353}
        alerts, _state = PW.decide(_readings(BASE, first, second),
                                   _manifest(), state)
        self.assertEqual([a["signal"] for a in alerts], ["new_listener"])
        self.assertEqual(alerts[0]["detail"]["port"], 5353)

    def test_vanished_listener_leaves_state_and_refiles_on_return(self):
        state = _learned_state(BASE)
        new = {"proto": "tcp", "addr": "127.0.0.1", "port": 8080}
        alerts, state = PW.decide(_readings(BASE, new), _manifest(), state)
        self.assertEqual(len(alerts), 1)
        # It vanishes: no alert, and its key leaves the state.
        alerts, state = PW.decide(_readings(BASE), _manifest(), state)
        self.assertEqual(alerts, [])
        self.assertNotIn("tcp/127.0.0.1/8080", state["seen"])
        # It returns: a moved reading, so it files again.
        alerts, _state = PW.decide(_readings(BASE, new),
                                   _manifest(), state)
        self.assertEqual([a["signal"] for a in alerts], ["new_listener"])

    def test_high_only_suppresses_medium_but_absorbs(self):
        state = _learned_state(BASE)
        new = {"proto": "tcp", "addr": "127.0.0.1", "port": 8080}
        readings = _readings(BASE, new)
        alerts, state = PW.decide(readings, _manifest(high_only=True),
                                  state)
        self.assertEqual(alerts, [])
        self.assertIn("tcp/127.0.0.1/8080", state["seen"])
        # Absorbed: even with high_only off, the same reading is
        # quiet now -- but an exposed listener still files high.
        alerts, state = PW.decide(readings, _manifest(), state)
        self.assertEqual(alerts, [])
        exposed = {"proto": "tcp", "addr": "0.0.0.0", "port": 9000}
        alerts, _state = PW.decide(_readings(BASE, new, exposed),
                                   _manifest(high_only=True), state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["exposed_listener"])

    def test_unusable_listeners_are_ignored(self):
        state = _learned_state(BASE)
        readings = {"now": NOW, "listeners": [
            None, {}, {"proto": "sctp", "addr": "127.0.0.1", "port": 9},
            {"proto": "tcp", "addr": "", "port": 9},
            {"proto": "tcp", "addr": "127.0.0.1", "port": 70000}]}
        alerts, _state = PW.decide(readings, _manifest(), state)
        self.assertEqual(alerts, [])


class ProcParsingTest(unittest.TestCase):
    def test_address_decoders(self):
        self.assertEqual(PW._ipv4_from_hex("0100007F"), "127.0.0.1")
        self.assertEqual(PW._ipv4_from_hex("00000000"), "0.0.0.0")
        self.assertIsNone(PW._ipv4_from_hex("zz"))
        self.assertEqual(PW._ipv6_from_hex("00" * 16), "::")
        self.assertIsNone(PW._ipv6_from_hex("00"))


class MainTest(unittest.TestCase):
    def test_readings_fixture_prints_and_learns(self):
        with tempfile.TemporaryDirectory() as d:
            readings_path = os.path.join(d, "readings.json")
            state_path = os.path.join(d, "state.json")
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump(_readings(BASE), fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = PW.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")  # first pass learns
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump(_readings(
                    BASE, {"proto": "tcp", "addr": "0.0.0.0",
                           "port": 8080}), fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = PW.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["exposed_listener"])
            self.assertEqual(
                PW.main(["--readings", os.path.join(d, "missing.json"),
                         "--state", state_path]), 2)


if __name__ == "__main__":
    unittest.main()
