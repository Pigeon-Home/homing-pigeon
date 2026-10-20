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
import tempfile
import unittest

from hypothesis import given, settings, strategies as st

from runner.extensions import (
    api_refusal,
    load_extensions,
    parse_manifest,
    signal_description,
    build_sensor_alert,
    sign_envelope,
)
from runner.runner import (
    _ingest_local_envelope_inner,
    check_key_policy,
)
from runner.senses import (
    file_sensor_alert,
    gate_alert,
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
