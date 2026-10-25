"""Local signal delivery: same-box senses and extensions.

Pins the local path end to end (docs/extend/extensions.md, "Local
delivery"): two front-ends -- the local-inbox file drop and the
loopback socket push -- carry the identical signed envelope into
the one ingest core the mail path uses. Same signature checks,
same key policy, same sensor binding, same declared-signal gate;
locally filed alerts carry source="local", and a high or
critical one can wake the Oracle through the deterministic wake
gate, which files its assessment in oracle-briefs.jsonl.

No live model and no real sleeping: the wake gate takes an
injected clock, briefings use a patched ask_model_agent, and the
socket tests bind an ephemeral loopback port.
"""
import importlib.util
import json
import os
import shutil
import socket
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

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "lab-results")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
LAB_SECRET = "9f86d081884c7d659a2feaa0c55ad015" + "a3bf4f1b2b0b822cd15d6c15b0f00a08"
IDS_SECRET = "6dcd4ce23d88e2ee78e0b4b0a24a1868" + "1b60b5b7e1f9a34b25aec5d66a5a04a42"
WRONG_SECRET = "44d578328548d5958e3672d110a23616" + "f232daea18b8ba13fc2c093b379e90f9"


def _base_cfg(ext_root):
    return {
        "shared_secret": DEFAULT_SECRET,
        "additional_secrets": {"lab-key": LAB_SECRET, "ids-key": IDS_SECRET},
        "key_policies": {
            "lab-key": {"allowed_kinds": ["sensor_alert"]},
            "ids-key": {"allowed_kinds": ["sensor_alert"]},
        },
        "sensors": {
            "lab_results": {"enabled": True, "key_id": "lab-key",
                            "weight": 1.0, "profile": {}},
            "host_ids": {"enabled": True, "key_id": "ids-key",
                         "weight": 1.0, "profile": {}},
        },
        "extensions_dir": ext_root,
    }


class LocalFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "lab-results"))
        self.cfg = _base_cfg(self.ext_root)
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)

    def tearDown(self):
        # A high alert starts the oracle-brief daemon, which still
        # has the brief file open when the temp dir is removed.
        # Windows then fails the test in cleanup (WinError 145)
        # even though the assertions passed.
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
    def drop(self, payload, secret):
        return E.drop_local_signal(self.base, payload, secret)

    def scan(self, cfg=None):
        return R._scan_local_inbox(cfg or self.cfg, self.base)

    def alerts(self):
        return S.load_alerts(self.base)

    def inbox_names(self):
        inbox = os.path.join(self.base, "local-inbox")
        if not os.path.isdir(inbox):
            return []
        return sorted(os.listdir(inbox))

    def lab_alert(self, severity="info", signal="experiment_finished",
                  title="experiment exp-041 finished", **kw):
        return E.build_sensor_alert(
            "lab_results", severity, title, key_id="lab-key",
            signal=signal, **kw)


class EnvelopeVerificationTest(LocalFixture):
    def test_valid_envelope_stored_with_local_marker(self):
        path = self.drop(self.lab_alert(), LAB_SECRET)
        self.assertEqual(self.scan(), 1)
        self.assertFalse(os.path.exists(path))
        recs = self.alerts()
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "lab_results")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["key_id"], "lab-key")
        self.assertEqual(rec["signal"], "experiment_finished")

    def test_wrong_secret_rejected(self):
        self.drop(self.lab_alert(), WRONG_SECRET)
        self.assertEqual(self.scan(), 1)
        self.assertEqual(self.alerts(), [])
        self.assertEqual(self.inbox_names(), [])  # removed, not retried

    def test_tampered_payload_rejected(self):
        payload = self.lab_alert(title="original title here")
        text = E.sign_envelope(payload, LAB_SECRET)
        tampered = text.replace("original title here", "forged title here!")
        self.assertNotEqual(text, tampered)
        inbox = os.path.join(self.base, "local-inbox")
        os.makedirs(inbox)
        with open(os.path.join(inbox, "x.json"), "w",
                  encoding="utf-8") as fh:
            fh.write(tampered)
        self.assertEqual(self.scan(), 1)
        self.assertEqual(self.alerts(), [])

    def test_unknown_key_rejected(self):
        payload = E.build_sensor_alert(
            "lab_results", "info", "t", key_id="ghost-key",
            signal="experiment_finished")
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_key_bound_to_another_sensor_rejected(self):
        # ids-key is a real key with a valid signature, but it is
        # bound to host_ids; it cannot file as lab_results.
        payload = self.lab_alert()
        self.drop(payload, IDS_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_key_policy_without_sensor_alert_rejected(self):
        cfg = _base_cfg(self.ext_root)
        cfg["key_policies"]["ids-key"] = {"allowed_kinds": ["ping"]}
        payload = E.build_sensor_alert("host_ids", "low", "ids event",
                                       key_id="ids-key")
        self.drop(payload, IDS_SECRET)
        self.scan(cfg)
        self.assertEqual(self.alerts(), [])

    def test_non_sensor_alert_kind_rejected(self):
        payload = self.lab_alert()
        payload["kind"] = "ping"
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_wrong_protocol_version_rejected(self):
        payload = self.lab_alert()
        payload["v"] = 99
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_stale_issued_at_rejected(self):
        payload = self.lab_alert()
        payload["issued_at"] = "2020-01-01T00:00:00Z"
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_unsafe_job_id_rejected(self):
        payload = self.lab_alert(job_id="../evil")
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_missing_api_version_rejected(self):
        payload = self.lab_alert()
        del payload["api_version"]
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_newer_api_version_rejected(self):
        payload = E.build_sensor_alert(
            "lab_results", "info", "t", key_id="lab-key",
            signal="experiment_finished", api_version=99)
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_oversize_envelope_rejected_and_removed(self):
        inbox = os.path.join(self.base, "local-inbox")
        os.makedirs(inbox)
        path = os.path.join(inbox, "big.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("a" * (R._LOCAL_ENVELOPE_MAX_BYTES + 10))
        self.assertEqual(self.scan(), 1)
        self.assertEqual(self.alerts(), [])
        self.assertFalse(os.path.exists(path))


class LocalExtensionGateTest(LocalFixture):
    def test_declared_signal_stored_with_description(self):
        self.drop(self.lab_alert(signal="result_anomaly",
                                 severity="high",
                                 title="experiment exp-041: anomaly"),
                  LAB_SECRET)
        self.scan()
        rec = self.alerts()[0]
        self.assertEqual(rec["signal"], "result_anomaly")
        self.assertEqual(rec["signal_description"],
                         "A finished run's headline metric sits far "
                         "outside this folder's earlier results.")
        self.assertEqual(rec["extension"], "lab_results")
        self.assertEqual(rec["extension_version"], "0.3.0")
        self.assertEqual(rec["source"], "local")

    def test_undeclared_signal_rejected_not_stored(self):
        self.drop(self.lab_alert(signal="total_explosion"), LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_missing_signal_rejected_for_extension_sense(self):
        payload = E.build_sensor_alert("lab_results", "info", "t",
                                       key_id="lab-key")
        self.drop(payload, LAB_SECRET)
        self.scan()
        self.assertEqual(self.alerts(), [])

    def test_plain_sense_needs_no_signal(self):
        payload = E.build_sensor_alert("host_ids", "low", "ids event",
                                       key_id="ids-key")
        self.drop(payload, IDS_SECRET)
        self.scan()
        recs = self.alerts()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["source"], "local")
        self.assertNotIn("signal_description", recs[0])


class InboxMechanicsTest(LocalFixture):
    def test_empty_inbox_is_a_noop(self):
        self.assertEqual(self.scan(), 0)

    def test_missing_inbox_is_a_noop(self):
        other = os.path.join(self._tmp.name, "no-base-here")
        self.assertEqual(R._scan_local_inbox(self.cfg, other), 0)

    def test_malformed_file_does_not_wedge_later_files(self):
        inbox = os.path.join(self.base, "local-inbox")
        os.makedirs(inbox)
        with open(os.path.join(inbox, "a-garbage.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{this is not json")
        self.drop(self.lab_alert(), LAB_SECRET)
        self.assertEqual(self.scan(), 2)
        self.assertEqual(len(self.alerts()), 1)
        self.assertEqual(self.inbox_names(), [])

    def test_invalid_file_removed_not_retried(self):
        path = self.drop(self.lab_alert(signal="nope"), LAB_SECRET)
        self.assertEqual(self.scan(), 1)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.scan(), 0)  # nothing left to retry

    def test_non_json_entries_left_alone(self):
        inbox = os.path.join(self.base, "local-inbox")
        os.makedirs(inbox)
        keep = os.path.join(inbox, "README.txt")
        with open(keep, "w", encoding="utf-8") as fh:
            fh.write("not an envelope")
        self.assertEqual(self.scan(), 0)
        self.assertTrue(os.path.exists(keep))


class SocketTransportTest(LocalFixture):
    def _serve(self, cfg=None):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        srv.settimeout(1.0)
        port = srv.getsockname()[1]
        th = threading.Thread(target=R._serve_local_signals,
                              args=(cfg or self.cfg, self.base, srv),
                              daemon=True)
        th.start()
        self.addCleanup(srv.close)
        return port

    def _wait_alerts(self, n, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.alerts()) >= n:
                return
            time.sleep(0.05)
        self.fail(f"expected {n} stored alert(s), got {self.alerts()}")

    def test_socket_push_stores_the_same_envelope(self):
        port = self._serve()
        E.send_local_signal(self.lab_alert(), LAB_SECRET, port=port)
        self._wait_alerts(1)
        rec = self.alerts()[0]
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["signal"], "experiment_finished")

    def test_bad_signature_dropped_listener_survives(self):
        port = self._serve()
        E.send_local_signal(self.lab_alert(), WRONG_SECRET, port=port)
        E.send_local_signal(self.lab_alert(title="second, valid"),
                            LAB_SECRET, port=port)
        self._wait_alerts(1)
        self.assertEqual(self.alerts()[0]["title"], "second, valid")

    def test_config_port_zero_disables_listener(self):
        self.assertEqual(R._local_signal_port({"local_signal_port": 0}), 0)
        self.assertIsNone(
            R._local_signal_server({"local_signal_port": 0}, self.base))

    def test_disabled_config_drops_at_the_connection(self):
        if not hasattr(socket, "socketpair"):
            self.skipTest("socketpair unavailable")
        try:
            client, server = socket.socketpair()
        except OSError:
            self.skipTest("socketpair unavailable")
        cfg = _base_cfg(self.ext_root)
        cfg["local_signals"] = False
        text = E.sign_envelope(self.lab_alert(), LAB_SECRET)
        client.sendall(text.encode("utf-8"))
        client.shutdown(socket.SHUT_WR)
        R._handle_local_signal_conn(cfg, self.base, server)
        client.close()
        server.close()
        self.assertEqual(self.alerts(), [])


class ServeLoopIsolationTest(unittest.TestCase):
    """Queue A refill: _serve_local_signals' isolation
    legs (coverage run 40189711740: lines 5365-5366
    and 5370-5371). The accept loop is failure-
    isolated by its docstring: a connection whose
    handling raises is dropped, a close that fails is
    ignored, and the loop keeps accepting.
    """

    def test_a_bad_connection_never_stops_the_loop(self):
        handled = []

        class Conn:
            def close(self):
                raise OSError("already gone")

        class Srv:
            def __init__(self):
                self.calls = 0

            def accept(self):
                self.calls += 1
                if self.calls == 1:
                    return Conn(), ("127.0.0.1", 1)
                raise KeyboardInterrupt

        def boom(_cfg, _base, conn):
            handled.append(conn)
            raise RuntimeError("handler broke")

        srv = Srv()
        with unittest.mock.patch.object(
                R, "_handle_local_signal_conn", boom):
            with self.assertRaises(KeyboardInterrupt):
                R._serve_local_signals({}, "/base", srv)
        self.assertEqual(len(handled), 1)
        self.assertEqual(srv.calls, 2)


class LocalConfigTest(unittest.TestCase):
    def test_enabled_by_default(self):
        self.assertTrue(R._local_signals_enabled({}))
        self.assertTrue(R._local_signals_enabled({"local_signals": True}))

    def test_disabled_forms(self):
        for v in (False, 0, "false", "off", "no", "0"):
            self.assertFalse(R._local_signals_enabled({"local_signals": v}),
                             v)

    def test_port_default_and_disable_forms(self):
        self.assertEqual(R._local_signal_port({}), 39271)
        self.assertEqual(R._local_signal_port({}),
                         R.LOCAL_SIGNAL_DEFAULT_PORT)
        for v in (0, False, None, "abc", 70000, -1):
            self.assertEqual(R._local_signal_port({"local_signal_port": v}),
                             0, v)
        self.assertEqual(
            R._local_signal_port({"local_signal_port": 40000}), 40000)

    def test_cooldown_default_and_bad_values(self):
        self.assertEqual(R._local_wake_cooldown({}), 900.0)
        self.assertEqual(
            R._local_wake_cooldown({"local_wake_cooldown_sec": 5}), 5.0)
        self.assertEqual(
            R._local_wake_cooldown({"local_wake_cooldown_sec": "x"}), 900.0)
        self.assertEqual(
            R._local_wake_cooldown({"local_wake_cooldown_sec": -3}), 900.0)
        self.assertEqual(
            R._local_wake_cooldown({"local_wake_cooldown_sec": 0}), 0.0)


def _record(severity="high", sensor="lab_results", signal="result_anomaly",
            title="t"):
    rec = {"sensor": sensor, "severity": severity, "title": title}
    if signal is not None:
        rec["signal"] = signal
    return rec


class WakeGateTest(unittest.TestCase):
    def setUp(self):
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.cfg = {"local_wake_cooldown_sec": 900}

    def decide(self, rec, now):
        return R._wake_gate_decide(self.cfg, rec, now=now)

    def test_high_fires(self):
        self.assertTrue(self.decide(_record("high"), 1000.0))
        R._wake_gate_release()

    def test_critical_also_fires(self):
        self.assertTrue(self.decide(_record("critical"), 1000.0))
        R._wake_gate_release()

    def test_medium_low_info_never_fire(self):
        for sev in ("medium", "low", "info"):
            self.assertFalse(self.decide(_record(sev), 1000.0), sev)

    def test_second_within_cooldown_suppressed(self):
        self.assertTrue(self.decide(_record(), 1000.0))
        R._wake_gate_release()
        self.assertFalse(self.decide(_record(), 1500.0))

    def test_cooldown_expiry_refires(self):
        self.assertTrue(self.decide(_record(), 1000.0))
        R._wake_gate_release()
        self.assertTrue(self.decide(_record(), 1000.0 + 900 + 1))
        R._wake_gate_release()

    def test_different_signal_not_held_by_cooldown(self):
        self.assertTrue(self.decide(_record(signal="a_signal"), 1000.0))
        R._wake_gate_release()
        self.assertTrue(self.decide(_record(signal="b_signal"), 1001.0))
        R._wake_gate_release()

    def test_title_discriminates_when_no_signal(self):
        self.assertTrue(
            self.decide(_record(signal=None, title="first"), 1000.0))
        R._wake_gate_release()
        self.assertFalse(
            self.decide(_record(signal=None, title="first"), 1001.0))
        self.assertTrue(
            self.decide(_record(signal=None, title="second"), 1001.0))
        R._wake_gate_release()

    def test_inflight_suppresses_everything(self):
        self.assertTrue(self.decide(_record(signal="a_signal"), 1000.0))
        # No release: a briefing is in flight.
        self.assertFalse(self.decide(_record(signal="b_signal"), 1001.0))
        R._wake_gate_release()
        # After release, the un-woken signal is not on cooldown.
        self.assertTrue(self.decide(_record(signal="b_signal"), 1002.0))
        R._wake_gate_release()

    def test_zero_cooldown_refires_immediately(self):
        cfg = {"local_wake_cooldown_sec": 0}
        self.assertTrue(R._wake_gate_decide(cfg, _record(), now=1000.0))
        R._wake_gate_release()
        self.assertTrue(R._wake_gate_decide(cfg, _record(), now=1000.0))
        R._wake_gate_release()

    def test_maybe_wake_spawns_once_then_gate_holds(self):
        spawned = []

        def fake_spawn(cfg, base_dir, record):
            spawned.append(record)
            R._wake_gate_release()

        with unittest.mock.patch.object(R, "_start_brief_thread",
                                        fake_spawn):
            self.assertTrue(
                R._maybe_wake_oracle(self.cfg, "/base", _record()))
            self.assertFalse(
                R._maybe_wake_oracle(self.cfg, "/base", _record()))
            self.assertFalse(
                R._maybe_wake_oracle(self.cfg, "/base", _record("low")))
        self.assertEqual(len(spawned), 1)


class BriefingTest(LocalFixture):
    def _inf_cfg(self):
        cfg = _base_cfg(self.ext_root)
        cfg["inference"] = {"endpoint": "http://127.0.0.1:11434/v1",
                            "model": "qwen3:1.7b"}
        return cfg

    def _brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def test_no_inference_writes_fallback_brief(self):
        brief = R._oracle_brief(self.cfg, self.base,
                                _record(signal="result_anomaly"))
        self.assertEqual(brief["status"], "no_inference")
        self.assertIn("No local model is configured",
                      brief["assessment"])
        lines = self._brief_lines()
        self.assertEqual(len(lines), 1)
        filed = json.loads(lines[0])
        self.assertEqual(filed["sensor"], "lab_results")
        self.assertEqual(filed["signal"], "result_anomaly")
        self.assertEqual(filed["severity"], "high")
        self.assertEqual(filed["assessment"], brief["assessment"])
        self.assertIn("time", filed)

    def test_assessed_brief_from_the_model(self):
        seen = {}

        def fake_ask(inf, question, context, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            seen["question"] = question
            return {"answer": "Assessment: the anomaly is real."}

        rec = _record(signal="result_anomaly")
        rec["signal_description"] = "A finished run's headline metric."
        with unittest.mock.patch.object(R, "ask_model_agent", fake_ask):
            brief = R._oracle_brief(self._inf_cfg(), self.base, rec)
        self.assertEqual(brief["status"], "assessed")
        self.assertEqual(brief["assessment"],
                         "Assessment: the anomaly is real.")
        self.assertIn("result_anomaly", seen["question"])
        self.assertIn("declared by its extension", seen["question"])
        self.assertIn("A finished run's headline metric.",
                      seen["question"])
        self.assertEqual(len(self._brief_lines()), 1)

    def test_model_rejection_becomes_failure_brief(self):
        def fake_ask(*a, **kw):
            return {"rejected": "inference_unconfigured"}

        with unittest.mock.patch.object(R, "ask_model_agent", fake_ask):
            brief = R._oracle_brief(self._inf_cfg(), self.base, _record())
        self.assertEqual(brief["status"], "inference_failed")
        self.assertIn("inference_unconfigured", brief["assessment"])
        self.assertEqual(len(self._brief_lines()), 1)

    def test_model_raising_becomes_failure_brief_not_exception(self):
        def fake_ask(*a, **kw):
            raise RuntimeError("endpoint down")

        with unittest.mock.patch.object(R, "ask_model_agent", fake_ask):
            brief = R._oracle_brief(self._inf_cfg(), self.base, _record())
        self.assertEqual(brief["status"], "inference_failed")
        self.assertIn("endpoint down", brief["assessment"])
        self.assertEqual(len(self._brief_lines()), 1)

    def test_briefing_thread_releases_the_gate(self):
        cfg = self._inf_cfg()
        cfg["local_wake_cooldown_sec"] = 900
        spawned = []
        with unittest.mock.patch.object(
                R, "_start_brief_thread",
                lambda c, b, r: spawned.append(r)):
            self.assertTrue(R._maybe_wake_oracle(cfg, self.base,
                                                 _record()))
        self.assertEqual(len(spawned), 1)
        self.assertTrue(R._LOCAL_WAKE_INFLIGHT)
        with unittest.mock.patch.object(
                R, "ask_model_agent",
                lambda *a, **kw: {"answer": "ok"}):
            R._start_brief_thread(cfg, self.base, _record())
            deadline = time.time() + 5
            while R._LOCAL_WAKE_INFLIGHT and time.time() < deadline:
                time.sleep(0.02)
        self.assertFalse(R._LOCAL_WAKE_INFLIGHT)
        self.assertEqual(len(self._brief_lines()), 1)


class PipelineTest(LocalFixture):
    def _brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def _wait_briefs(self, n, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self._brief_lines()
            if len(lines) >= n:
                return lines
            time.sleep(0.05)
        self.fail(f"expected {n} brief(s), got {self._brief_lines()}")

    def test_high_local_alert_wakes_and_files_fallback_brief(self):
        self.drop(self.lab_alert(severity="high",
                                 signal="result_anomaly",
                                 title="experiment exp-041: anomaly"),
                  LAB_SECRET)
        self.scan()
        lines = self._wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["status"], "no_inference")
        self.assertEqual(brief["signal"], "result_anomaly")

    def test_medium_local_alert_does_not_wake(self):
        self.drop(self.lab_alert(severity="medium",
                                 signal="metric_threshold_crossed",
                                 title="experiment exp-041: crossed"),
                  LAB_SECRET)
        self.scan()
        time.sleep(0.3)
        self.assertEqual(self._brief_lines(), [])
        self.assertEqual(len(self.alerts()), 1)  # filed, just no wake

    def test_cooldown_applies_end_to_end(self):
        for title in ("first anomaly", "second anomaly"):
            self.drop(self.lab_alert(severity="high",
                                     signal="result_anomaly",
                                     title=title), LAB_SECRET)
            self.scan()
            self._wait_briefs(1)
            deadline = time.time() + 5
            while R._LOCAL_WAKE_INFLIGHT and time.time() < deadline:
                time.sleep(0.02)
        self.assertEqual(len(self._brief_lines()), 1)
        self.assertEqual(len(self.alerts()), 2)  # both filed

    def test_wake_briefs_with_model_through_the_pipeline(self):
        cfg = _base_cfg(self.ext_root)
        cfg["inference"] = {"endpoint": "http://127.0.0.1:11434/v1",
                            "model": "qwen3:1.7b"}
        ask_called = threading.Event()
        release = threading.Event()

        def fake_ask(*a, **kw):
            ask_called.set()
            release.wait(30)
            return {"answer": "The anomaly is real; check exp-041."}

        with unittest.mock.patch.object(R, "ask_model_agent", fake_ask):
            self.drop(self.lab_alert(severity="high",
                                     signal="result_anomaly",
                                     title="experiment exp-041: anomaly"),
                      LAB_SECRET)
            R._scan_local_inbox(cfg, self.base)
            self.assertTrue(ask_called.wait(5))
            release.set()
            lines = self._wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["status"], "assessed")
        self.assertIn("check exp-041", brief["assessment"])


class ProducerHelperTest(unittest.TestCase):
    def test_build_sensor_alert_shape(self):
        p = E.build_sensor_alert("lab_results", "high", "t",
                                 key_id="lab-key", signal="result_anomaly")
        self.assertEqual(p["v"], 1)
        self.assertEqual(p["type"], "job")
        self.assertEqual(p["kind"], "sensor_alert")
        self.assertEqual(p["api_version"], E.EXTENSION_API_VERSION)
        self.assertEqual(p["key_id"], "lab-key")
        self.assertEqual(p["signal"], "result_anomaly")
        self.assertTrue(p["job_id"])
        self.assertTrue(p["issued_at"].endswith("Z"))

    def test_sign_and_verify_roundtrip(self):
        p = E.build_sensor_alert("lab_results", "info", "t",
                                 key_id="lab-key")
        text = E.sign_envelope(p, LAB_SECRET)
        job, key_id = R.verify_body_keyed(text, {"lab-key": LAB_SECRET})
        self.assertEqual(key_id, "lab-key")
        self.assertEqual(job["sensor"], "lab_results")

    def test_drop_is_idempotent_per_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            p = E.build_sensor_alert("lab_results", "info", "t",
                                     key_id="lab-key")
            first = E.drop_local_signal(d, p, LAB_SECRET)
            second = E.drop_local_signal(d, p, LAB_SECRET)
            self.assertEqual(first, second)
            inbox = os.path.join(d, "local-inbox")
            self.assertEqual(sorted(os.listdir(inbox)),
                             [os.path.basename(first)])

    def test_periodic_drops_accumulate(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                p = E.build_sensor_alert("lab_results", "info",
                                         f"pass {i}", key_id="lab-key")
                E.drop_local_signal(d, p, LAB_SECRET)
            inbox = os.path.join(d, "local-inbox")
            self.assertEqual(len(os.listdir(inbox)), 3)

    def test_send_to_dead_port_raises(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        p = E.build_sensor_alert("lab_results", "info", "t",
                                 key_id="lab-key")
        with self.assertRaises(OSError):
            E.send_local_signal(p, LAB_SECRET, port=port, timeout=2.0)


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "lab_results_example_local",
        os.path.join(EXAMPLE_DIR, "lab_results.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ExampleLocalDeliveryTest(LocalFixture):
    def test_example_local_dir_delivery(self):
        results = os.path.join(self._tmp.name, "results")
        os.makedirs(results)
        with open(os.path.join(results, "exp-041.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"run": "exp-041", "status": "finished",
                       "metrics": {"accuracy": 0.95}}, fh)
        mod = _load_example_module()
        env = {"HOMING_PIGEON_SENSOR_SECRET": LAB_SECRET}
        with unittest.mock.patch.dict(os.environ, env):
            rc = mod.main(["--watch-dir", results,
                           "--local-dir", self.base,
                           "--key-id", "lab-key"])
        self.assertEqual(rc, 0)
        names = self.inbox_names()
        self.assertTrue(names)  # envelopes waiting in the inbox
        self.scan()
        signals = sorted(r.get("signal") for r in self.alerts())
        self.assertIn("experiment_finished", signals)
        for rec in self.alerts():
            self.assertEqual(rec["source"], "local")


if __name__ == "__main__":
    unittest.main()
