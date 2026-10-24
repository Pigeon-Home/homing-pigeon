"""Cert Sentinel: the example sense that files certificate expiry.

Pins the Cert Sentinel example (runner/extensions/cert-sentinel/)
the way test_sky_watcher.py pins Sky Watcher: the manifest through
the real extension loader, the band discipline across scripted
expiry fixtures (decide() is pure, so every boundary is a table
row), the identity-change signal, and the PEM file branch of
read_live() against a stubbed standard-library decoder.

No live network, no live files of consequence, and no openssl
dependency anywhere: the decoder stub returns the dict shape the
real decoder returns, and TLS targets are never probed here.
"""
import importlib.util
import json
import os
import shutil
import ssl
import sys
import tempfile
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "cert-sentinel")

NOW = 1_700_000_000.0
DAY = 86400.0


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "cert_sentinel_example",
        os.path.join(EXAMPLE_DIR, "cert_sentinel.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CS = _load_example_module()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _cert(days_left, source="/certs/site.pem", serial="0A1B",
          subject="CN=example.com", issuer="CN=Example CA"):
    return {"source": source, "subject": subject, "issuer": issuer,
            "serial": serial, "not_after": NOW + days_left * DAY}


def _readings(*certs):
    return {"now": NOW, "certs": list(certs)}


def _run(certs, state=None, manifest=None):
    return CS.decide(_readings(*certs), manifest or _manifest(),
                     state if state is not None else {})


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "cert_sentinel")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["cert_changed", "cert_critical", "cert_expiring"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "cert-sentinel"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("cert_sentinel", registry)
        self.assertEqual(registry["cert_sentinel"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def test_band_boundaries(self):
        # (days_left, expected [(signal, severity), ...]) from
        # a fresh state: first sight files its band alert.
        cases = [
            (31, []),
            (30, [("cert_expiring", "medium")]),
            (8, [("cert_expiring", "medium")]),
            (7, [("cert_critical", "high")]),
            (0, [("cert_critical", "high")]),
            (-1, [("cert_critical", "high")]),
        ]
        for days, expected in cases:
            with self.subTest(days_left=days):
                alerts, state = _run([_cert(days)])
                self.assertEqual(
                    [(a["signal"], a["severity"]) for a in alerts],
                    expected)
                for a in alerts:
                    self.assertEqual(a["sensor"], "cert_sentinel")
                    self.assertEqual(a["detail"]["source"],
                                     "/certs/site.pem")
                    self.assertEqual(a["detail"]["days_left"],
                                     float(days))
                band = {31: "ok", 30: "warn", 8: "warn"}.get(days)
                if days <= 7:
                    band = "critical"
                self.assertEqual(
                    state["seen"]["/certs/site.pem"]["band"], band)

    def test_warn_band_holds_quietly_then_critical_files(self):
        alerts, state = _run([_cert(30)])
        self.assertEqual([a["signal"] for a in alerts], ["cert_expiring"])
        # 8 days left is still the warn band: quiet while it holds.
        alerts, state = _run([_cert(8)], state=state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["seen"]["/certs/site.pem"]["band"], "warn")
        # Crossing into critical files the high signal, once.
        alerts, state = _run([_cert(7)], state=state)
        self.assertEqual([(a["signal"], a["severity"]) for a in alerts],
                         [("cert_critical", "high")])
        alerts, state = _run([_cert(3)], state=state)
        self.assertEqual(alerts, [])

    def test_jump_straight_from_ok_to_critical(self):
        _alerts, state = _run([_cert(90)])
        alerts, _state = _run([_cert(5)], state=state)
        self.assertEqual([a["signal"] for a in alerts], ["cert_critical"])

    def test_same_readings_twice_files_nothing_second_time(self):
        alerts, state = _run([_cert(20)])
        self.assertEqual([a["signal"] for a in alerts], ["cert_expiring"])
        alerts, state = _run([_cert(20)], state=state)
        self.assertEqual(alerts, [])

    def test_first_sight_files_no_cert_changed(self):
        for days in (20, -5):
            with self.subTest(days_left=days):
                alerts, _state = _run([_cert(days)])
                self.assertNotIn("cert_changed",
                                 [a["signal"] for a in alerts])

    def test_renewed_cert_files_changed_and_goes_quiet(self):
        _alerts, state = _run([_cert(20, serial="0A1B")])
        renewed = _cert(365, serial="0C2D")
        alerts, state = _run([renewed], state=state)
        self.assertEqual([(a["signal"], a["severity"]) for a in alerts],
                         [("cert_changed", "info")])
        self.assertEqual(alerts[0]["detail"]["serial"], "0C2D")
        self.assertEqual(alerts[0]["detail"]["previous_serial"], "0A1B")
        seen = state["seen"]["/certs/site.pem"]
        self.assertEqual(seen["serial"], "0C2D")
        self.assertEqual(seen["band"], "ok")
        # The renewed certificate, unchanged, files nothing more.
        alerts, _state = _run([renewed], state=state)
        self.assertEqual(alerts, [])

    def test_changed_cert_still_in_warn_files_both(self):
        _alerts, state = _run([_cert(90, serial="0A1B")])
        alerts, state = _run([_cert(20, serial="0C2D")], state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["cert_changed", "cert_expiring"])

    def test_issuer_or_subject_change_also_files_changed(self):
        _alerts, state = _run([_cert(90)])
        for changed in (_cert(90, issuer="CN=Other CA"),
                        _cert(90, subject="CN=other.example.com")):
            with self.subTest(changed=changed):
                alerts, _s = _run([changed], state=state)
                self.assertEqual([a["signal"] for a in alerts],
                                 ["cert_changed"])

    def test_quiet_case_files_nothing(self):
        alerts, state = _run([_cert(90), _cert(45, source="/certs/a.pem")])
        self.assertEqual(alerts, [])
        self.assertEqual(sorted(state["seen"]),
                         ["/certs/a.pem", "/certs/site.pem"])

    def test_bad_state_and_bad_records_are_cleaned(self):
        alerts, state = CS.decide(
            {"now": NOW, "certs": [{"source": "/x.pem"}, "junk", {}]},
            _manifest(), {"seen": {"bad": {"band": "loud"}}})
        self.assertEqual(alerts, [])
        self.assertEqual(state, {"seen": {}})


class ReadLiveFileTest(unittest.TestCase):
    DECODED = {
        "subject": ((("CN", "example.com"),), (("O", "Example Org"),)),
        "issuer": ((("CN", "Example CA"),),),
        "serialNumber": "0A1B",
        "notAfter": "Jan 15 00:00:00 2027 GMT",
    }

    def _manifest_with_files(self, files):
        manifest = _manifest()
        manifest["tunables"] = dict(manifest["tunables"],
                                    cert_files=files, tls_targets=[])
        return manifest

    def test_file_branch_record_shape(self):
        with unittest.mock.patch.object(
                CS.ssl._ssl, "_test_decode_cert",
                return_value=dict(self.DECODED)) as decode:
            readings = CS.read_live(
                self._manifest_with_files(["/certs/site.pem"]))
        decode.assert_called_once_with("/certs/site.pem")
        self.assertEqual(len(readings["certs"]), 1)
        rec = readings["certs"][0]
        self.assertEqual(rec["source"], "/certs/site.pem")
        self.assertEqual(rec["subject"], "CN=example.com, O=Example Org")
        self.assertEqual(rec["issuer"], "CN=Example CA")
        self.assertEqual(rec["serial"], "0A1B")
        self.assertEqual(
            rec["not_after"],
            ssl.cert_time_to_seconds("Jan 15 00:00:00 2027 GMT"))
        self.assertIsInstance(readings["now"], float)

    def test_unreadable_file_is_skipped_silently(self):
        with unittest.mock.patch.object(
                CS.ssl._ssl, "_test_decode_cert",
                side_effect=OSError("no such file")):
            readings = CS.read_live(
                self._manifest_with_files(["/certs/missing.pem"]))
        self.assertEqual(readings["certs"], [])

    def test_tls_probe_failure_is_no_data(self):
        manifest = _manifest()
        manifest["tunables"] = dict(
            manifest["tunables"], cert_files=[],
            tls_targets=[{"host": "192.0.2.1", "port": 443}])
        with unittest.mock.patch.object(
                CS.socket, "create_connection",
                side_effect=OSError("no route to host")):
            readings = CS.read_live(manifest)
        self.assertEqual(readings["certs"], [])


if __name__ == "__main__":
    unittest.main()
