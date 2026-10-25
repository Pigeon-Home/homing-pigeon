"""Service Watch: the example sense that files service outages.

Pins the Service Watch example (runner/extensions/service-watch/):
the manifest through the real extension loader, the pure decide()
state machine across scripted process tables (learn pass, down,
recovery, silent recovery, flapping), and one end-to-end run --
producer drops a service_down into the local inbox, the real
ingest files it, and the high-severity signal wakes the gate and
files a deterministic brief.

No live network and no live hardware anywhere: every process
table is a fixture readings dict, except one shape-only smoke
read of the host's own /proc in ReadLiveTest.
"""
import contextlib
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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.oracle import senses as S  # noqa: E402
from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "service-watch")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
SVC_SECRET = "a1b2c3d4e5f60718293a4b5c6d7e8f90" + "1a2b3c4d5e6f708192a3b4c5d6e7f809"

T0 = 1700000000.0


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "service_watch_example", os.path.join(EXAMPLE_DIR, "service_watch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SW = _load_example_module()


def _manifest(services=None, **tunable_overrides):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    tunables = dict(manifest["tunables"])
    if services is not None:
        tunables["services"] = services
    tunables.update(tunable_overrides)
    manifest["tunables"] = tunables
    return manifest


def _readings(now, names):
    """Readings with one process per name in `names`."""
    return {"now": float(now),
            "processes": [{"name": n, "pid": 100 + i,
                           "cmdline": f"/usr/sbin/{n}"}
                          for i, n in enumerate(names)]}


class ManifestTest(unittest.TestCase):
    def test_shipped_manifest_parses(self):
        with open(os.path.join(EXAMPLE_DIR, "extension.json"),
                  encoding="utf-8") as fh:
            raw = json.load(fh)
        clean = E.parse_manifest(raw)
        self.assertEqual(clean["name"], "service_watch")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["service_down", "service_flapping", "service_recovered"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertIn("services", clean["tunables"])
        self.assertIn("flap_window_sec", clean["tunables"])
        self.assertIn("flap_count", clean["tunables"])
        self.assertIn("learn_first_pass", clean["tunables"])

    def test_loads_via_load_extensions_from_copied_tree(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "service-watch"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("service_watch", registry)
        self.assertEqual(registry["service_watch"]["version"], "0.1.0")
        self.assertEqual(
            sorted(registry["service_watch"]["signal_descriptions"]),
            ["service_down", "service_flapping", "service_recovered"])


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest(
            services=[{"name": "sshd", "match": "exact"}])

    def test_learn_pass_files_nothing(self):
        alerts, state = SW.decide(_readings(T0, ["sshd"]),
                                  self.manifest, {})
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        self.assertTrue(state["services"]["sshd"]["up"])

    def test_quiet_case_up_steady_files_nothing(self):
        _a, state = SW.decide(_readings(T0, ["sshd"]), self.manifest, {})
        for i in range(1, 4):
            alerts, state = SW.decide(
                _readings(T0 + i * 30, ["sshd"]), self.manifest, state)
            self.assertEqual(alerts, [])

    def test_service_down_fires_high(self):
        _a, state = SW.decide(_readings(T0, ["sshd"]), self.manifest, {})
        alerts, state = SW.decide(_readings(T0 + 30, []),
                                  self.manifest, state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "service_down")
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["sensor"], "service_watch")
        self.assertEqual(alerts[0]["detail"]["service"], "sshd")
        self.assertTrue(state["services"]["sshd"]["down_filed"])

    def test_service_recovered_fires_info_with_downtime(self):
        _a, state = SW.decide(_readings(T0, ["sshd"]), self.manifest, {})
        _a, state = SW.decide(_readings(T0 + 30, []), self.manifest, state)
        alerts, state = SW.decide(_readings(T0 + 150, ["sshd"]),
                                  self.manifest, state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "service_recovered")
        self.assertEqual(alerts[0]["severity"], "info")
        self.assertEqual(alerts[0]["detail"]["service"], "sshd")
        self.assertEqual(alerts[0]["detail"]["downtime_sec"], 120.0)
        self.assertFalse(state["services"]["sshd"]["down_filed"])

    def test_learned_down_recovers_silently(self):
        # Learned down on the first pass: its return was never a
        # filed outage, so the recovery files nothing.
        _a, state = SW.decide(_readings(T0, []), self.manifest, {})
        self.assertFalse(state["services"]["sshd"]["up"])
        alerts, state = SW.decide(_readings(T0 + 30, ["sshd"]),
                                  self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertTrue(state["services"]["sshd"]["up"])

    def test_service_flapping_fires_medium(self):
        manifest = _manifest(
            services=[{"name": "sshd", "match": "exact"}],
            flap_window_sec=600, flap_count=4)
        _a, state = SW.decide(_readings(T0, ["sshd"]), manifest, {})
        alerts = []
        # down, up, down, up -> 4 transitions inside the window.
        sequence = [([], 30), (["sshd"], 60), ([], 90), (["sshd"], 120)]
        for names, off in sequence:
            fired, state = SW.decide(_readings(T0 + off, names),
                                     manifest, state)
            alerts.extend(fired)
        flap = [a for a in alerts if a["signal"] == "service_flapping"]
        self.assertEqual(len(flap), 1)
        self.assertEqual(flap[0]["severity"], "medium")
        self.assertEqual(flap[0]["detail"]["service"], "sshd")
        self.assertEqual(flap[0]["detail"]["transitions"], 4)
        self.assertEqual(flap[0]["detail"]["window_sec"], 600.0)
        self.assertTrue(state["services"]["sshd"]["flap_fired"])

    def test_flap_fired_clears_after_full_quiet_window(self):
        manifest = _manifest(
            services=[{"name": "sshd", "match": "exact"}],
            flap_window_sec=600, flap_count=4)
        _a, state = SW.decide(_readings(T0, ["sshd"]), manifest, {})
        for names, off in [([], 30), (["sshd"], 60), ([], 90),
                           (["sshd"], 120)]:
            _f, state = SW.decide(_readings(T0 + off, names),
                                  manifest, state)
        self.assertTrue(state["services"]["sshd"]["flap_fired"])
        # A full window with no transitions rearms the flap signal.
        alerts, state = SW.decide(_readings(T0 + 120 + 601, ["sshd"]),
                                  manifest, state)
        self.assertEqual(alerts, [])
        self.assertFalse(state["services"]["sshd"]["flap_fired"])

    def test_same_readings_twice_files_nothing_second_time(self):
        _a, state = SW.decide(_readings(T0, ["sshd"]), self.manifest, {})
        alerts, state = SW.decide(_readings(T0 + 30, []),
                                  self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts], ["service_down"])
        alerts2, state = SW.decide(_readings(T0 + 30, []),
                                   self.manifest, state)
        self.assertEqual(alerts2, [])

    def test_moved_reading_refiles(self):
        _a, state = SW.decide(_readings(T0, ["sshd"]), self.manifest, {})
        _a, state = SW.decide(_readings(T0 + 30, []), self.manifest, state)
        _a, state = SW.decide(_readings(T0 + 60, ["sshd"]),
                              self.manifest, state)
        alerts, state = SW.decide(_readings(T0 + 90, []),
                                  self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts], ["service_down"])
        self.assertEqual(alerts[0]["severity"], "high")

    def test_substring_match_uses_cmdline(self):
        manifest = _manifest(
            services=[{"name": "oracle-helper", "match": "substring"}])
        readings = {"now": T0, "processes": [
            {"name": "python3", "pid": 7,
             "cmdline": "python3 /opt/oracle-helper/main.py"}]}
        _a, state = SW.decide(readings, manifest, {})
        self.assertTrue(state["services"]["oracle-helper"]["up"])
        alerts, state = SW.decide(_readings(T0 + 30, []), manifest, state)
        self.assertEqual([a["signal"] for a in alerts], ["service_down"])

    def test_exact_match_ignores_cmdline(self):
        manifest = _manifest(
            services=[{"name": "sshd", "match": "exact"}])
        readings = {"now": T0, "processes": [
            {"name": "bash", "pid": 7, "cmdline": "bash -c sshd"}]}
        _a, state = SW.decide(readings, manifest, {})
        self.assertFalse(state["services"]["sshd"]["up"])

    def test_signals_file_in_tunables_order(self):
        manifest = _manifest(services=[
            {"name": "alpha", "match": "exact"},
            {"name": "beta", "match": "exact"}])
        _a, state = SW.decide(_readings(T0, ["alpha", "beta"]),
                              manifest, {})
        alerts, state = SW.decide(_readings(T0 + 30, []), manifest, state)
        self.assertEqual([a["detail"]["service"] for a in alerts],
                         ["alpha", "beta"])
        self.assertEqual([a["signal"] for a in alerts],
                         ["service_down", "service_down"])

    def test_every_signal_table(self):
        # Table-driven: (scenario builder, signal, severity).
        cases = []
        # down
        _a, st = SW.decide(_readings(T0, ["sshd"]), self.manifest, {})
        down_alerts, _st = SW.decide(_readings(T0 + 30, []),
                                     self.manifest, st)
        cases.append((down_alerts, "service_down", "high"))
        for alerts, signal, severity in cases:
            self.assertEqual(alerts[0]["signal"], signal)
            self.assertEqual(alerts[0]["severity"], severity)


class FlapResetAndPartialDeliveryTest(unittest.TestCase):
    """Queue A refill: decide's flap reset
    (coverage run 40189711740: line 300) and
    main's partial delivery (431-434). A
    service that flapped and then stayed quiet
    past the window earns its flap flag back --
    the next flap is news again. And a local
    delivery that lands only some alerts
    leaves the state unwritten, so the next
    pass reports the changes again instead of
    losing them.
    """

    def test_a_quiet_service_gets_its_flap_flag_back(self):
        manifest = _manifest(
            services=[{"name": "oracle-helper",
                       "match": "exact"}],
            flap_window_sec=600, flap_count=3)
        readings = _readings(10000.0, ["oracle-helper"])
        state = {"learned": True,
                 "services": {"oracle-helper": {
                     "up": True, "transitions": [100.0, 200.0],
                     "flap_fired": True, "down_filed": False}}}
        _alerts, new_state = SW.decide(readings, manifest, state)
        entry = new_state["services"]["oracle-helper"]
        self.assertFalse(entry["flap_fired"])
        self.assertEqual(entry["transitions"], [])
        state2 = {"learned": True,
                  "services": {"oracle-helper": {
                      "up": True, "transitions": [],
                      "flap_fired": True, "down_filed": False}}}
        _a, new_state2 = SW.decide(readings, manifest, state2)
        self.assertFalse(
            new_state2["services"]["oracle-helper"]["flap_fired"])

    def test_a_partial_delivery_keeps_the_state(self):
        tmp = tempfile.mkdtemp(prefix="hp-svc-")
        manifest_path = os.path.join(tmp, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(_manifest(
                services=[{"name": "oracle-helper",
                           "match": "exact"}]), fh)
        readings_path = os.path.join(tmp, "readings.json")
        with open(readings_path, "w", encoding="utf-8") as fh:
            json.dump(_readings(1000.0, []), fh)
        state_path = os.path.join(tmp, "state.json")
        seeded = {"learned": True,
                  "services": {"oracle-helper": {
                      "up": True, "transitions": [],
                      "flap_fired": False,
                      "down_filed": False}}}
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump(seeded, fh)
        err = io.StringIO()
        with unittest.mock.patch.object(
                SW, "_deliver_local",
                return_value=0), \
                contextlib.redirect_stderr(err):
            rc = SW.main(["--manifest", manifest_path,
                          "--readings", readings_path,
                          "--local-dir", tmp,
                          "--state", state_path])
        self.assertEqual(rc, 2)
        self.assertIn("not delivered", err.getvalue())
        with open(state_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), seeded)


class SvcFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "service-watch"))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {"svc-key": SVC_SECRET},
            "key_policies": {
                "svc-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "service_watch": {"enabled": True, "key_id": "svc-key",
                                  "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.state_path = os.path.join(self._tmp.name, "state.json")
        self.manifest_path = os.path.join(self._tmp.name, "manifest.json")
        manifest = _manifest(
            services=[{"name": "oracle-helper", "match": "exact"}])
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

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

    def readings_file(self, readings, name="readings.json"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(readings, fh)
        return path

    def run_producer(self, readings, name="readings.json"):
        env = {"HOMING_PIGEON_SENSOR_SECRET": SVC_SECRET}
        with unittest.mock.patch.dict(os.environ, env):
            return SW.main(["--manifest", self.manifest_path,
                            "--readings",
                            self.readings_file(readings, name),
                            "--local-dir", self.base,
                            "--key-id", "svc-key",
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


class EndToEndTest(SvcFixture):
    def test_service_down_files_and_wakes_a_brief(self):
        present = {"now": T0, "processes": [
            {"name": "oracle-helper", "pid": 42,
             "cmdline": "/usr/local/bin/oracle-helper"}]}
        absent = {"now": T0 + 30, "processes": []}
        # Pass 1: the service is present -- learn pass, quiet.
        rc = self.run_producer(present, name="readings1.json")
        self.assertEqual(rc, 0)
        self.assertEqual(self.inbox_names(), [])
        # Pass 2: it is gone -- service_down files locally.
        rc = self.run_producer(absent, name="readings2.json")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        self.assertEqual(self.inbox_names(), [])
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "service_watch")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "service_watch")
        self.assertEqual(rec["extension_version"], "0.1.0")
        self.assertEqual(rec["signal"], "service_down")
        self.assertEqual(rec["severity"], "high")
        with open(os.path.join(EXAMPLE_DIR, "extension.json"),
                  encoding="utf-8") as fh:
            shipped = json.load(fh)
        declared = {s["name"]: s["description"]
                    for s in shipped["signals"]}
        self.assertEqual(rec["signal_description"],
                         declared["service_down"])
        # The high signal wakes the deterministic brief.
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "service_down")
        self.assertEqual(brief["sensor"], "service_watch")
        self.assertEqual(brief["status"], "no_inference")


class ReadLiveTest(unittest.TestCase):
    """Queue A: `read_live` never ran anywhere (coverage run
    40180268696: 30 lines on both platforms) -- every other
    test feeds decide() a fixture, so the one function that
    touches the real process table was the gap. Its seam is
    the /proc directory it scans; the tests below serve it a
    scripted /proc through listdir/open (the same fake-the-
    seam style as the install tests), plus one shape-only
    read of the host's real /proc where one exists.

    The docstring's promises under test: a process that
    exits mid-scan is skipped quietly; an unreadable cmdline
    reads as empty, never an error; a name that is not a pid
    is not a process; and where there is no /proc the
    snapshot is empty -- absent data, never an error.
    """

    def _scripted_proc(self):
        files = {
            "/proc/1/comm": "init\n",
            "/proc/1/cmdline": b"/sbin/init\x00--flag\x00",
            "/proc/7/comm": "worker",
            # A name isdigit() accepts but int() refuses:
            # read, then skipped at the pid conversion.
            "/proc/²/comm": "weird",
            "/proc/²/cmdline": b"",
        }
        real_open = open

        def fake_listdir(path):
            if path != "/proc":
                raise OSError("no such directory")
            return ["1", "42", "7", "self", "meminfo", "²"]

        def fake_open(path, mode="r", **kw):
            # os.path.join speaks the host's separators:
            # on Windows the scan builds /proc\1\comm, and
            # the scripted /proc is keyed in slashes.
            path = str(path).replace("\\", "/")
            if not path.startswith("/proc/"):
                return real_open(path, mode, **kw)
            if path == "/proc/42/comm":
                raise OSError("gone mid-scan")
            if path == "/proc/7/cmdline":
                raise OSError("not readable")
            data = files[path]
            if "b" in mode:
                return io.BytesIO(data)
            return io.StringIO(data)

        return fake_listdir, fake_open

    def test_a_scripted_proc_scans_like_the_real_one(self):
        listdir, fake_open = self._scripted_proc()
        with unittest.mock.patch.object(SW.os, "listdir", listdir), \
                unittest.mock.patch("builtins.open", fake_open):
            got = SW.read_live(_manifest())
        self.assertIsInstance(got["now"], float)
        self.assertEqual(got["processes"], [
            {"name": "init", "pid": 1,
             "cmdline": "/sbin/init --flag"},
            {"name": "worker", "pid": 7, "cmdline": ""},
        ])

    def test_no_proc_is_an_empty_snapshot_not_an_error(self):
        def no_proc(path):
            raise OSError("no /proc on this platform")

        with unittest.mock.patch.object(SW.os, "listdir", no_proc):
            got = SW.read_live(_manifest())
        self.assertIsInstance(got["now"], float)
        self.assertEqual(got["processes"], [])

    # Linux only, not merely /proc-shaped: FreeBSD mounts a
    # /proc whose per-pid entries are not the Linux comm/cmdline
    # shape read_live scans, so the isdir gate alone let this
    # smoke test run there and find no processes (Q35). The
    # parsing contract itself is platform-neutral above.
    @unittest.skipUnless(sys.platform == "linux"
                         and os.path.isdir("/proc"),
                         "needs a /proc to scan")
    def test_the_real_proc_names_this_process(self):
        got = SW.read_live(_manifest())
        mine = [p for p in got["processes"]
                if p["pid"] == os.getpid()]
        self.assertEqual(len(mine), 1)
        with open("/proc/self/comm", encoding="utf-8") as fh:
            self.assertEqual(mine[0]["name"], fh.read().strip())
        self.assertIsInstance(mine[0]["cmdline"], str)


if __name__ == "__main__":
    unittest.main()
