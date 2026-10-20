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
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
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
from runner.jobcrypto import decrypt_body, encrypt_body
from runner.runner import (
    Board,
    _handle_local_signal_conn,
    _ingest_local_envelope_inner,
    _local_signal_port,
    _local_signals_enabled,
    _parse_content_tool_call,
    _run_oracle_tool,
    _scan_local_inbox,
    _set_allow_cleartext_jobs,
    check_key_policy,
    process_transport_message,
    sign_payload,
    verify_body,
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

    def _wire_as(self, job_id, secret, key_id, issued_at=None,
                 files=None):
        payload = {
            "v": 1,
            "type": "job",
            "job_id": job_id,
            "issued_at": issued_at or datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "kind": "exec",
            "interpreter": [sys.executable],
            "script": "open(%r, 'w').write('ran')\n" % self.marker,
        }
        if key_id:
            payload["key_id"] = key_id
        if files is not None:
            payload["files"] = files
        return encrypt_body(
            sign_payload(payload, secret), secret,
            job_id=job_id, key_id=key_id, sign=sign_payload)

    def _wire(self, job_id):
        return self._wire_as(job_id, SECRET, "")

    def _run(self, job_id, body, policies=None, secrets=None):
        return process_transport_message(
            self.cfg, self.tmp, {}, secrets or self.secrets,
            policies or {},
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

    def test_a_sensor_key_cannot_run_a_script(self):
        secrets = {"": SECRET, "sense-key": SENSE}
        policies = {"sense-key": {"allowed_kinds": ["sensor_alert"]}}
        bad_id = uuid.uuid4().hex
        self._run(
            bad_id, self._wire_as(bad_id, SENSE, "sense-key"),
            policies, secrets)
        self.assertFalse(os.path.exists(self.marker))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id), policies, secrets)
        self.assertTrue(os.path.isfile(self.marker))

    def test_an_oversized_script_does_not_run(self):
        self.cfg["max_script_bytes"] = 20
        bad_id = uuid.uuid4().hex
        self._run(bad_id, self._wire(bad_id))
        self.assertFalse(os.path.exists(self.marker))
        self.cfg["max_script_bytes"] = 1048576
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def test_a_stamp_outside_the_window_does_not_run(self):
        now = datetime.now(timezone.utc)
        stamps = (
            (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        for stamp in stamps:
            job_id = uuid.uuid4().hex
            self._run(job_id, self._wire_as(
                job_id, SECRET, "", stamp))
            self.assertFalse(os.path.exists(self.marker))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def test_a_file_named_dotdot_does_not_escape(self):
        outside = os.path.join(os.path.dirname(self.tmp), "escaped.txt")
        job_id = uuid.uuid4().hex
        self._run(job_id, self._wire_as(job_id, SECRET, "", files=[{
            "name": "../escaped.txt",
            "url": "https://example.com/escaped.txt",
        }]))
        self.assertFalse(os.path.exists(self.marker))
        self.assertFalse(os.path.exists(outside))
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp, "escaped.txt")))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def test_a_subject_that_disagrees_with_the_body_does_not_run(self):
        inner_id = uuid.uuid4().hex
        subject_id = uuid.uuid4().hex
        payload = {
            "v": 1,
            "type": "job",
            "job_id": inner_id,
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "kind": "exec",
            "interpreter": [sys.executable],
            "script": "open(%r, 'w').write('ran')\n" % self.marker,
        }
        wire = encrypt_body(
            sign_payload(payload, SECRET), SECRET,
            job_id=subject_id, key_id="", sign=sign_payload)
        self._run(subject_id, wire)
        self.assertFalse(os.path.exists(self.marker))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def _with_reply_to(self, job_id, reply_to):
        payload = {
            "v": 1,
            "type": "job",
            "job_id": job_id,
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "kind": "exec",
            "interpreter": [sys.executable],
            "script": "open(%r, 'w').write('ran')\n" % self.marker,
            "reply_to": reply_to,
        }
        return encrypt_body(
            sign_payload(payload, SECRET), SECRET,
            job_id=job_id, key_id="", sign=sign_payload)

    def test_a_reply_to_that_is_not_one_address_is_not_used(self):
        bad = (
            "a@b.com\r\nBcc: c@d.com",
            "not-an-email",
            "a@b.com, c@d.com",
            ["si@example.com"],
        )
        for reply_to in bad:
            job_id = uuid.uuid4().hex
            out = self._run(job_id, self._with_reply_to(job_id, reply_to))
            self.assertTrue(out)
            self.assertTrue(all(target is None for _s, _b, target in out))
        good_id = uuid.uuid4().hex
        out = self._run(
            good_id, self._with_reply_to(good_id, "si@example.com"))
        self.assertEqual(out[0][2], "si@example.com")

    def test_a_job_cannot_set_a_pigeon_variable(self):
        job_id = uuid.uuid4().hex
        payload = {
            "v": 1,
            "type": "job",
            "job_id": job_id,
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "kind": "exec",
            "interpreter": [sys.executable],
            "env": {
                "PIGEON_SECRET": "stolen",
                "pigeon_token": "stolen",
                "MARKER": "kept",
            },
            "script": (
                "import os\n"
                "open(%r, 'w').write("
                "repr(os.environ.get('PIGEON_SECRET')) + ' ' +"
                "repr(os.environ.get('pigeon_token')) + ' ' +"
                "repr(os.environ.get('MARKER')))\n" % self.marker
            ),
        }
        wire = encrypt_body(
            sign_payload(payload, SECRET), SECRET,
            job_id=job_id, key_id="", sign=sign_payload)
        self._run(job_id, wire)
        with open(self.marker, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("stolen", text)
        self.assertIn("kept", text)
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        with open(self.marker, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ran")

    def test_the_same_job_does_not_run_twice(self):
        job_id = uuid.uuid4().hex
        wire = self._wire(job_id)
        seen = {}
        process_transport_message(
            self.cfg, self.tmp, seen, self.secrets, {},
            "[HOMING-PIGEON] job " + job_id, wire)
        self.assertTrue(os.path.isfile(self.marker))
        os.remove(self.marker)
        process_transport_message(
            self.cfg, self.tmp, seen, self.secrets, {},
            "[HOMING-PIGEON] job " + job_id, wire)
        self.assertFalse(os.path.exists(self.marker))
        other = uuid.uuid4().hex
        self._run(other, self._wire(other))
        self.assertTrue(os.path.isfile(self.marker))

    def test_an_envelope_key_that_differs_from_the_body_does_not_run(self):
        job_id = uuid.uuid4().hex
        payload = {
            "v": 1,
            "type": "job",
            "job_id": job_id,
            "key_id": "sense-key",
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "kind": "exec",
            "interpreter": [sys.executable],
            "script": "open(%r, 'w').write('ran')\n" % self.marker,
        }
        wire = encrypt_body(
            sign_payload(payload, SENSE), SECRET,
            job_id=job_id, key_id="", sign=sign_payload)
        secrets = {"": SECRET, "sense-key": SENSE}
        self._run(job_id, wire, secrets=secrets)
        self.assertFalse(os.path.exists(self.marker))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id), secrets=secrets)
        self.assertTrue(os.path.isfile(self.marker))

    def _claiming(self, job_id, runner_id):
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
        if runner_id is not None:
            payload["runner_id"] = runner_id
        return encrypt_body(
            sign_payload(payload, SECRET), SECRET,
            job_id=job_id, key_id="", sign=sign_payload)

    def test_the_wrong_audience_does_not_run(self):
        self.cfg["runner_id"] = "this-runner"
        self.cfg["security"] = {"modes": {"audience": "enforce"}}
        for claim in (None, "someone-else"):
            job_id = uuid.uuid4().hex
            self._run(job_id, self._claiming(job_id, claim))
            self.assertFalse(os.path.exists(self.marker))
        good_id = uuid.uuid4().hex
        self._run(good_id, self._claiming(good_id, "this-runner"))
        self.assertTrue(os.path.isfile(self.marker))

    def test_a_file_url_is_not_the_script(self):
        for url in ("file:///etc/passwd", "File:///etc/shadow"):
            job_id = uuid.uuid4().hex
            payload = {
                "v": 1,
                "type": "job",
                "job_id": job_id,
                "issued_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "kind": "exec",
                "interpreter": [sys.executable],
                "script_url": url,
                "script": "open(%r, 'w').write('ran')\n" % self.marker,
            }
            wire = encrypt_body(
                sign_payload(payload, SECRET), SECRET,
                job_id=job_id, key_id="", sign=sign_payload)
            self._run(job_id, wire)
            self.assertFalse(os.path.exists(self.marker))
            work = os.path.join(self.tmp, "work", job_id)
            if os.path.isdir(work):
                for name in os.listdir(work):
                    with open(os.path.join(work, name), "rb") as f:
                        blob = f.read()
                    self.assertNotIn(b"root:", blob)
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def _poison(self, job_id, **extra):
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
        payload.update(extra)
        return encrypt_body(
            sign_payload(payload, SECRET), SECRET,
            job_id=job_id, key_id="", sign=sign_payload)

    def _opened(self, out, job_id):
        outer = verify_body(out[0][1], SECRET)
        inner = decrypt_body(outer, SECRET, job_id, "")
        return verify_body(inner, SECRET)

    def test_a_null_byte_does_not_run(self):
        for extra in (
            {"args": ["ok", "bad\x00byte"]},
            {"env": {"OK": "fine", "BAD\x00": "no"}},
        ):
            job_id = uuid.uuid4().hex
            out = self._run(job_id, self._poison(job_id, **extra))
            self.assertFalse(os.path.exists(self.marker))
            self.assertEqual(self._opened(out, job_id)["exit_code"], -2)
        job_id = uuid.uuid4().hex
        out = self._run(job_id, self._poison(
            job_id, interpreter=[sys.executable + "\x00"]))
        self.assertFalse(os.path.exists(self.marker))
        opened = self._opened(out, job_id)
        self.assertNotEqual(opened["exit_code"], -2)
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def test_a_ping_does_not_run_its_script(self):
        job_id = uuid.uuid4().hex
        out = self._run(job_id, self._poison(job_id, kind="ping"))
        self.assertFalse(os.path.exists(self.marker))
        self.assertEqual(self._opened(out, job_id)["stdout"], "pong")
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))

    def test_an_unknown_kind_does_not_run(self):
        for kind in ("sh", "", "Exec"):
            job_id = uuid.uuid4().hex
            out = self._run(job_id, self._poison(job_id, kind=kind))
            self.assertFalse(os.path.exists(self.marker))
            self.assertEqual(self._opened(out, job_id)["exit_code"], -2)
        good_id = uuid.uuid4().hex
        self._run(good_id, self._wire(good_id))
        self.assertTrue(os.path.isfile(self.marker))


_CANARY = "hp-canary-9f3c2a"


class RingTwoQueryTest(unittest.TestCase):
    """A query that does not verify learns nothing. A good query
    of the same retained output still gets the answer."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-ring2-query-")
        self.cfg = {
            "mailbox_user": "runner@example.com",
            "shared_secret": SECRET,
            "max_job_age_sec": 3600,
            "base_dir": self.tmp,
        }
        self.job_id = "retainedjob01"
        retained = os.path.join(self.tmp, "retained")
        os.makedirs(retained)
        with open(os.path.join(retained, self.job_id + ".json"),
                  "w", encoding="utf-8") as f:
            json.dump({
                "stdout": "secret " + _CANARY,
                "stderr": "",
                "exit_code": 0,
                "budget": 8,
                "spent": 0,
                "view": "full",
                "saved_at": time.time(),
            }, f)

    def _wire(self, query_id):
        payload = {
            "v": 1,
            "type": "query",
            "query_id": query_id,
            "job_id": self.job_id,
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "queries": [{"op": "grep", "pattern": _CANARY}],
        }
        return sign_payload(payload, SECRET)

    def _sealed(self, query_id):
        return encrypt_body(
            self._wire(query_id), SECRET, job_id=query_id,
            key_id="", sign=sign_payload)

    def _ask(self, query_id, body, seen=None):
        return process_transport_message(
            self.cfg, self.tmp, {} if seen is None else seen,
            {"": SECRET}, {},
            "[HOMING-PIGEON] query " + query_id, body)

    def test_cleartext_is_refused_and_the_encrypted_query_answers(self):
        bad_id = uuid.uuid4().hex
        wire = self._wire(bad_id)
        flipped = (
            wire[:-2] + ("0" if wire[-2] != "0" else "1") + wire[-1])
        self.assertEqual(self._ask(bad_id, flipped), [])
        plain_id = uuid.uuid4().hex
        self.assertEqual(self._ask(plain_id, self._wire(plain_id)), [])
        good_id = uuid.uuid4().hex
        good = self._ask(good_id, self._sealed(good_id))
        raw = " ".join(body for _s, body, _t in good)
        self.assertNotIn(_CANARY, raw)
        outer = verify_body(good[0][1], SECRET)
        inner = decrypt_body(outer, SECRET, good_id, "")
        opened = verify_body(inner, SECRET)
        self.assertIn(_CANARY, json.dumps(opened))

    def test_allow_cleartext_still_answers(self):
        _set_allow_cleartext_jobs(True)
        try:
            qid = uuid.uuid4().hex
            good = self._ask(qid, self._wire(qid))
            raw = " ".join(body for _s, body, _t in good)
            self.assertIn(_CANARY, raw)
        finally:
            _set_allow_cleartext_jobs(False)

    def test_the_same_query_is_not_answered_twice(self):
        qid = uuid.uuid4().hex
        wire = self._sealed(qid)
        seen = {}
        first = self._ask(qid, wire, seen)
        raw = " ".join(body for _s, body, _t in first)
        self.assertNotIn(_CANARY, raw)
        outer = verify_body(first[0][1], SECRET)
        inner = decrypt_body(outer, SECRET, qid, "")
        self.assertIn(_CANARY, json.dumps(verify_body(inner, SECRET)))
        self.assertEqual(self._ask(qid, wire, seen), [])


class RingTwoBoardTest(unittest.TestCase):
    """A board message that does not verify changes nothing. The
    next good submit still opens the task."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-ring2-board-")
        self.board = Board(os.path.join(self.tmp, "board.json"))
        self.cfg = {
            "mailbox_user": "runner@example.com",
            "shared_secret": SECRET,
            "max_job_age_sec": 3600,
            "base_dir": self.tmp,
            "board": self.board,
        }

    def _wire(self, task_id):
        payload = {
            "v": 1,
            "type": "task_submit",
            "task_id": task_id,
            "issued_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "payload": {"note": "file me"},
        }
        return sign_payload(payload, SECRET)

    def _sealed(self, task_id):
        return encrypt_body(
            self._wire(task_id), SECRET, job_id=task_id,
            key_id="", sign=sign_payload)

    def _send(self, task_id, body):
        return process_transport_message(
            self.cfg, self.tmp, {}, {"": SECRET}, {},
            "[HOMING-PIGEON] task_submit " + task_id, body)

    def test_cleartext_opens_nothing_and_the_envelope_does(self):
        bad_id = "task-bad-1"
        wire = self._wire(bad_id)
        flipped = (
            wire[:-2] + ("0" if wire[-2] != "0" else "1") + wire[-1])
        self.assertEqual(self._send(bad_id, flipped), [])
        self.assertNotIn(bad_id, self.board.tasks)
        plain_id = "task-plain-1"
        self.assertEqual(self._send(plain_id, self._wire(plain_id)), [])
        self.assertNotIn(plain_id, self.board.tasks)
        good_id = "task-good-1"
        out = self._send(good_id, self._sealed(good_id))
        self.assertEqual(self.board.tasks[good_id]["state"], "open")
        raw = " ".join(body for _s, body, _t in out)
        self.assertNotIn("file me", raw)
        self.assertIn("task_ack", " ".join(s for s, _b, _t in out))












