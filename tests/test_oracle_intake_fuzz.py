"""In-memory fuzz of everything a sensor or an extension can hand
the Oracle.

The intake is the trust boundary: a sense drops a signed
envelope, a folder drops a manifest, a profile arrives as
JSON. None of that is allowed to abort the runner. A refusal
is a string. A crash is a bug.

No socket, no mailbox, no model. The generators stand in for
the zillion inputs.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from unittest import mock

from hypothesis import given, settings, strategies as st

from runner.detection import baseline_anomaly
from runner.learning import feature_keys, touched_keys
from runner.extensions import (
    api_refusal,
    build_sensor_alert,
    load_extensions,
    parse_manifest,
    sign_envelope,
    signal_description,
)
from runner.review import review_job
from runner.jobcrypto import encrypt_body
from runner.runner import (
    _handle_local_signal_conn,
    _ingest_local_envelope_inner,
    _local_signal_port,
    _local_signals_enabled,
    _parse_content_tool_call,
    _run_oracle_tool,
    _scan_local_inbox,
    check_key_policy,
    process_transport_message,
    sign_payload,
)
from runner.security import validate_security_config
from runner.senses import (
    file_sensor_alert,
    gate_alert,
    load_alerts,
    parse_sensors,
    validate_sensor_alert,
)

SECRET = ("kX9f" "2vQz" "7Lp4" "Wd8s" "Rb3N" "j6Hc" "5Ty1" "Mx0G" "aVqP")
SENSE = ("Qp4n" "Lm8s" "2Wd6" "Hr1c" "9Ty3" "Vx7k" "0Ba5" "Zu2e" "Nf8j")
_FAST = dict(max_examples=60, deadline=None)

_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10 ** 6), max_value=10 ** 6),
    st.text(max_size=60),
)
_messy = st.recursive(
    st.one_of(_leaf, st.binary(max_size=24)),
    lambda kids: st.one_of(
        st.lists(kids, max_size=4),
        st.dictionaries(
            st.one_of(st.text(max_size=16), st.integers(0, 8)),
            kids, max_size=6),
    ),
    max_leaves=10,
)
_json = st.recursive(
    _leaf,
    lambda kids: st.one_of(
        st.lists(kids, max_size=4),
        st.dictionaries(st.text(max_size=16), kids, max_size=6),
    ),
    max_leaves=10,
)


def _quiet(reason):
    return reason is None or isinstance(reason, str)


class SensorShapeFuzzTest(unittest.TestCase):
    @settings(**_FAST)
    @given(job=_messy)
    def test_validate_never_raises(self, job):
        self.assertTrue(_quiet(validate_sensor_alert(job)))

    @settings(**_FAST)
    @given(cfg=_messy, alert=_messy, recent=_messy)
    def test_gate_never_raises(self, cfg, alert, recent):
        self.assertTrue(_quiet(gate_alert(cfg, alert, recent, now=0)))

    @settings(**_FAST)
    @given(record=_messy, cfg=_messy)
    def test_file_never_raises(self, record, cfg):
        base = tempfile.mkdtemp(prefix="hp-sense-fuzz-")
        self.assertTrue(_quiet(file_sensor_alert(base, cfg, record)))


class ExtensionManifestFuzzTest(unittest.TestCase):
    @settings(**_FAST)
    @given(manifest=_messy)
    def test_api_refusal_and_signal_lookup_never_raise(self, manifest):
        self.assertTrue(_quiet(api_refusal(manifest)))
        self.assertTrue(
            signal_description(manifest, "trip") is None
            or isinstance(signal_description(manifest, "trip"), str))

    @settings(**_FAST)
    @given(data=_json)
    def test_parse_manifest_refuses_or_returns(self, data):
        try:
            got = parse_manifest(data, where="fuzz.json")
        except ValueError:
            return
        self.assertIsInstance(got, dict)

    @settings(max_examples=30, deadline=None)
    @given(blob=st.one_of(_json, st.binary(max_size=200),
                          st.text(max_size=200)))
    def test_a_folder_of_garbage_does_not_abort_discovery(self, blob):
        root = tempfile.mkdtemp(prefix="hp-ext-fuzz-")
        folder = os.path.join(root, "sense-a")
        os.makedirs(folder)
        path = os.path.join(folder, "extension.json")
        if isinstance(blob, (bytes, bytearray)):
            with open(path, "wb") as f:
                f.write(blob)
        else:
            with open(path, "w", encoding="utf-8") as f:
                if isinstance(blob, str):
                    f.write(blob)
                else:
                    json.dump(blob, f)
        registry, problems = load_extensions(root)
        self.assertIsInstance(registry, dict)
        self.assertIsInstance(problems, list)


class KeyPolicyFuzzTest(unittest.TestCase):
    @settings(**_FAST)
    @given(policies=_messy, key_id=_messy, cfg=_messy, job=_messy)
    def test_policy_answers_a_reason_or_none(self, policies, key_id,
                                             cfg, job):
        self.assertTrue(_quiet(
            check_key_policy(policies, key_id, cfg, job)))


class LocalEnvelopeFuzzTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-local-fuzz-")
        self.cfg = {
            "shared_secret": SECRET,
            "additional_secrets": {"canary-key": SENSE},
            "mailbox_user": "runner@example.com",
            "max_job_age_sec": 3600,
            "sensors": {
                "canary": {"enabled": True, "key_id": "canary-key"},
            },
        }

    @settings(**_FAST)
    @given(text=st.text(max_size=400))
    def test_random_text_is_a_rejection(self, text):
        got = _ingest_local_envelope_inner(
            self.cfg, self.tmp, text, "fuzz")
        self.assertIsNone(got)

    @settings(max_examples=40, deadline=None)
    @given(raw=st.binary(min_size=1, max_size=80))
    def test_a_mutated_signed_alert_does_not_abort(self, raw):
        signed = sign_envelope(build_sensor_alert(
            "canary", "high", "tripwire", signal="canary.changed",
            detail={"path": "/tmp/x"}, key_id="canary-key"), SENSE)
        body = bytearray(signed.encode("utf-8"))
        for i, byte in enumerate(raw):
            body[i % len(body)] ^= byte
        text = body.decode("utf-8", "replace")
        got = _ingest_local_envelope_inner(
            self.cfg, self.tmp, text, "fuzz")
        self.assertTrue(got is None or isinstance(got, dict))

    def test_an_unmutated_alert_is_filed(self):
        signed = sign_envelope(build_sensor_alert(
            "canary", "high", "tripwire", signal="canary.changed",
            key_id="canary-key"), SENSE)
        got = _ingest_local_envelope_inner(
            self.cfg, self.tmp, signed, "fuzz")
        self.assertIsInstance(got, dict)
        self.assertEqual(got.get("sensor"), "canary")


class RingOneFuzzTest(unittest.TestCase):
    """The next functions whose docstring says they never raise,
    or that a bad config must come back as RuntimeError and
    nothing else."""

    @settings(**_FAST)
    @given(cfg=_messy, job=_messy)
    def test_review_never_raises(self, cfg, job):
        got = review_job(cfg, job)
        self.assertIsInstance(got, dict)
        self.assertIsInstance(got.get("notes"), list)

    @settings(**_FAST)
    @given(cfg=_messy)
    def test_parse_sensors_is_a_dict_or_a_config_error(self, cfg):
        try:
            got = parse_sensors(cfg)
        except RuntimeError:
            return
        self.assertIsInstance(got, dict)

    def test_a_list_severity_floor_is_a_config_error(self):
        cfg = {"sensors": {"canary": {
            "enabled": True,
            "key_id": "canary-key",
            "profile": {"severity_floor": ["high"]},
        }}}
        with self.assertRaises(RuntimeError):
            parse_sensors(cfg)

    @settings(**_FAST)
    @given(blob=st.one_of(st.binary(max_size=300), st.text(max_size=300)),
           sensor=_messy, floor=_messy)
    def test_a_poisoned_senses_store_reads_as_a_list(self, blob, sensor,
                                                     floor):
        base = tempfile.mkdtemp(prefix="hp-store-fuzz-")
        path = os.path.join(base, "senses.jsonl")
        mode = "wb" if isinstance(blob, (bytes, bytearray)) else "w"
        with open(path, mode) as f:
            f.write(blob)
        got = load_alerts(base, sensor=sensor, severity_floor=floor)
        self.assertIsInstance(got, list)

    @settings(max_examples=30, deadline=None)
    @given(name=_messy, args=_messy,
           body=st.one_of(st.binary(max_size=80), st.text(max_size=80)))
    def test_oracle_tools_return_a_string(self, name, args, body):
        base = tempfile.mkdtemp(prefix="hp-tool-fuzz-")
        inbox = os.path.join(base, "local-inbox")
        os.makedirs(inbox)
        path = os.path.join(inbox, "n.json")
        mode = "wb" if isinstance(body, (bytes, bytearray)) else "w"
        with open(path, mode) as f:
            f.write(body)

        def _no_shell(*_a, **_k):
            return subprocess.CompletedProcess([], 0, b"", b"")

        with mock.patch("runner.runner.subprocess.run", _no_shell):
            got = _run_oracle_tool(name, args, base_dir=base)
        self.assertIsInstance(got, str)
        n = _scan_local_inbox(
            {"shared_secret": SECRET, "mailbox_user": "r@example.com"},
            base)
        self.assertIsInstance(n, int)


class _Chunks:
    """A connection that yields a fixed list of recv results."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def settimeout(self, _seconds):
        return None

    def recv(self, _n):
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if chunk is None:
            raise TimeoutError("quiet")
        return chunk


class SocketIntakeFuzzTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-sock-fuzz-")
        self.cfg = {
            "shared_secret": SECRET,
            "mailbox_user": "runner@example.com",
        }

    @settings(max_examples=40, deadline=None)
    @given(chunks=st.lists(st.binary(max_size=200), max_size=4),
           cfg=_messy)
    def test_socket_bytes_never_raise(self, chunks, cfg):
        _handle_local_signal_conn(
            self.cfg, self.tmp, _Chunks(chunks))
        self.assertIsInstance(_local_signals_enabled(cfg), bool)
        port = _local_signal_port(cfg)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 0)
        self.assertLessEqual(port, 65535)


class NonStringKeyFuzzTest(unittest.TestCase):
    """The lookups a JSON value can reach. A list where a string
    belongs is a refusal, not a TypeError."""

    def test_a_list_severity_is_a_refusal(self):
        reason = validate_sensor_alert({
            "sensor": "canary",
            "severity": ["high"],
            "title": "trip",
        })
        self.assertIsInstance(reason, str)

    def test_a_list_kind_does_not_abort_discovery(self):
        with self.assertRaises(ValueError):
            parse_manifest({
                "name": "canary",
                "version": "1.0.0",
                "api_version": 1,
                "kind": ["sense"],
                "description": "x",
                "signals": [{"name": "trip", "description": "y"}],
            }, where="extension.json")
        root = tempfile.mkdtemp(prefix="hp-kind-fuzz-")
        folder = os.path.join(root, "canary")
        os.makedirs(folder)
        with open(os.path.join(folder, "extension.json"), "w",
                  encoding="utf-8") as f:
            json.dump({
                "name": "canary",
                "version": "1.0.0",
                "api_version": 1,
                "kind": ["sense"],
                "description": "x",
                "signals": [{"name": "trip", "description": "y"}],
            }, f)
        registry, problems = load_extensions(root)
        self.assertEqual(registry, {})
        self.assertTrue(problems)

    def test_a_list_tool_name_is_not_a_call(self):
        text = '{"name": ["read_file"], "arguments": {"path": "a"}}'
        self.assertEqual(_parse_content_tool_call(text), [])

    def test_a_list_security_mode_is_a_config_error(self):
        with self.assertRaises(RuntimeError):
            validate_security_config({
                "security": {"modes": {"audience": ["enforce"]}},
            })

    def test_a_list_greeting_tier_refuses_to_start(self):
        from runner.transport_extensions.dtls.__main__ import main
        root = tempfile.mkdtemp(prefix="hp-tier-fuzz-")
        cfg_path = os.path.join(root, "runtime.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({
                "shared_secret": SECRET,
                "dtls_greeting": ["family"],
                "channel_dir": root,
            }, f)
        os.environ["HOMING_PIGEON_TRANSPORT_CHANNEL"] = root
        os.environ["HOMING_PIGEON_TRANSPORT_CONFIG"] = cfg_path
        try:
            code = main(["dtls"])
        finally:
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CHANNEL", None)
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CONFIG", None)
        self.assertEqual(code, 2)

    def test_a_poisoned_baseline_does_not_raise(self):
        baseline = {"kinds": {"exec": "many", "ping": [1]}}
        self.assertIsNone(baseline_anomaly(
            baseline, {"kind": ["exec"]}))
        seen = {"kinds": {f"k{i}": 1 for i in range(21)}}
        self.assertEqual(
            baseline_anomaly(seen, {"kind": ["nope"]}),
            "new_job_kind")
        self.assertIsNone(baseline_anomaly(seen, {"kind": "k0"}))

    def test_a_probe_with_the_wrong_shape_files_nothing(self):
        facts = {
            "interpreter": "python",
            "tools": 1,
            "paths": ["not", "a", "map"],
        }
        self.assertEqual(feature_keys(facts), [])
        self.assertEqual(touched_keys(facts), set())
        facts = {"interpreter": ["python"], "interpreter_present": False,
                 "tools": {"curl": False}, "paths": {"/tmp": None}}
        self.assertIn("interpreter:python", feature_keys(facts))
        self.assertIn("tool:curl", touched_keys(facts))


class RingTwoAlertTest(unittest.TestCase):
    """A message that does not verify stores nothing. The next
    good one, in the same directory, still files."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-ring2-")
        self.cfg = {
            "shared_secret": SECRET,
            "additional_secrets": {"canary-key": SENSE},
            "mailbox_user": "runner@example.com",
            "max_job_age_sec": 3600,
            "sensors": {
                "canary": {"enabled": True, "key_id": "canary-key"},
            },
        }

    def _senses(self):
        return os.path.join(self.tmp, "senses.jsonl")

    def test_a_flipped_signature_stores_nothing(self):
        signed = sign_envelope(build_sensor_alert(
            "canary", "high", "tripwire", key_id="canary-key"), SENSE)
        flipped = signed[:-2] + ("0" if signed[-2] != "0" else "1") + signed[-1]
        got = _ingest_local_envelope_inner(
            self.cfg, self.tmp, flipped, "fuzz")
        self.assertIsNone(got)
        self.assertFalse(os.path.exists(self._senses()))

    def test_a_bad_alert_does_not_block_the_next_good_one(self):
        payload = build_sensor_alert(
            "canary", "high", "tripwire", key_id="canary-key")
        payload["severity"] = ["high"]
        bad = sign_envelope(payload, SENSE)
        self.assertIsNone(_ingest_local_envelope_inner(
            self.cfg, self.tmp, bad, "fuzz"))
        self.assertFalse(os.path.exists(self._senses()))
        good = sign_envelope(build_sensor_alert(
            "canary", "high", "tripwire", key_id="canary-key"), SENSE)
        got = _ingest_local_envelope_inner(
            self.cfg, self.tmp, good, "fuzz")
        self.assertEqual(got.get("sensor"), "canary")
        with open(self._senses(), encoding="utf-8") as f:
            stored = f.read()
        self.assertIn("tripwire", stored)


class RingTwoJobTest(unittest.TestCase):
    """Same rule on a job. A bad envelope does not run. The next
    good one, same directory, does."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-ring2-job-")
        self.cfg = {
            "mailbox_user": "runner@example.com",
            "shared_secret": SECRET,
            "max_job_age_sec": 3600,
            "default_timeout_sec": 30,
            "base_dir": self.tmp,
        }
        self.secrets = {"": SECRET}
        self.marker = os.path.join(self.tmp, "ran.txt")

    def _wire(self, job_id):
        payload = {
            "v": 1,
            "type": "job",
            "job_id": job_id,
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "kind": "exec",
            "interpreter": [sys.executable],
            "script": "open(%r, 'w').write('ran')\n" % self.marker,
        }
        return encrypt_body(
            sign_payload(payload, SECRET), SECRET,
            job_id=job_id, key_id="", sign=sign_payload)

    def _run(self, job_id, body):
        return process_transport_message(
            self.cfg, self.tmp, {}, self.secrets, {},
            "[HOMING-PIGEON] job " + job_id, body)

    def test_a_flipped_job_does_not_run_and_the_next_one_does(self):
        bad_id = uuid.uuid4().hex
        wire = self._wire(bad_id)
        flipped = wire[:-2] + ("0" if wire[-2] != "0" else "1") + wire[-1]
        self.assertEqual(self._run(bad_id, flipped), [])
        self.assertFalse(os.path.exists(self.marker))
        good_id = uuid.uuid4().hex
        out = self._run(good_id, self._wire(good_id))
        self.assertTrue(out)
        self.assertTrue(os.path.isfile(self.marker))
        with open(self.marker, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ran")

    def test_a_nested_envelope_and_a_dotdot_id_do_not_run(self):
        nested_id = uuid.uuid4().hex
        once = self._wire(nested_id)
        twice = encrypt_body(
            once, SECRET, job_id=nested_id, key_id="",
            sign=sign_payload)
        self._run(nested_id, twice)
        self.assertFalse(os.path.exists(self.marker))
        self._run("..", self._wire(".."))
        self.assertFalse(os.path.exists(self.marker))
        self.assertFalse(os.path.isdir(
            os.path.join(self.tmp, "work")))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))








