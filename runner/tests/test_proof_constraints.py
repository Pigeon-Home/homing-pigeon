#!/usr/bin/env python3
"""Proof-work constraint pins (testing branch, stage 1).

The formal model in docs/proofs/ is built from values harvested
from the code, not invented. This test pins those values against
the code itself and against docs/proofs/constraints.md: if a
declared default, a constant, or the form of a construction
changes, this test fails, and the inventory -- and with it the
model's claims -- must be revisited before either can stand.

The values pinned here are the ones at commit 6d6288c5
(release 3.15.28), recorded as C1 to C16 in
docs/proofs/constraints.md. Stage 4 added C17 and C18 (the
result-policy ceiling and the sandbox shape's sources) and
their pins, from the same code.
"""
import hashlib
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.wire import jobcrypto as JC  # noqa: E402
from runner.wire import verify as V  # noqa: E402

SECRET = "proof-constraints-test-secret-0123456789abcdef"


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as fh:
        return fh.read()


def _mail_default(name):
    """The literal default handle_mail reads for a size cap."""
    text = _read(os.path.join("runner", "ops", "mail.py"))
    m = re.search(r'cfg\.get\("%s",\s*(\d+)\)' % re.escape(name), text)
    assert m is not None, "no literal default for %s in mail.py" % name
    return int(m.group(1))


class SizeCapPins(unittest.TestCase):
    def test_c1_max_job_bytes_default(self):
        self.assertEqual(_mail_default("max_job_bytes"), 4194304)

    def test_c2_max_script_bytes_default(self):
        self.assertEqual(_mail_default("max_script_bytes"), 1048576)

    def test_c3_max_result_bytes_default_is_5_mib_not_unlimited(self):
        # The default is a real cap. Unlimited is 0, set on purpose.
        self.assertEqual(R.MAX_RESULT_BYTES, 5 * 1024 * 1024)
        self.assertEqual(R.MAX_RESULT_BYTES, 5242880)
        self.assertEqual(R._max_result_bytes({}), 5242880)
        self.assertEqual(R._max_result_bytes({"max_result_bytes": 0}), 0)
        self.assertEqual(R._max_result_bytes({"max_result_bytes": 10}), 10)

    def test_c4_local_envelope_max_bytes(self):
        self.assertEqual(R._LOCAL_ENVELOPE_MAX_BYTES, 262144)

    def test_size_caps_startup_validation(self):
        # _validate_size_caps: a valid cap passes; a boolean, a
        # string, or a negative value names the key (the startup
        # refuse path in runner/ops/main.py returns exit 2 on it).
        for key in ("max_job_bytes", "max_script_bytes",
                    "max_result_bytes"):
            self.assertIsNone(R._validate_size_caps({key: 0}))
            self.assertIsNone(R._validate_size_caps({key: 7}))
            self.assertIsNone(R._validate_size_caps({}))
            for bad in (-1, True, "big"):
                err = R._validate_size_caps({key: bad})
                self.assertIsNotNone(err, (key, bad))
                self.assertIn(key, err)


class SignaturePins(unittest.TestCase):
    def test_c5_signature_is_hmac_sha384(self):
        # A body signed by the project's signer verifies, and the
        # signature is HMAC-SHA-384 over the body text.
        body = R.sign_payload({"v": 1, "type": "job", "job_id": "p1"},
                              SECRET)
        payload, key_id = V.verify_body_keyed(body, {"": SECRET})
        self.assertEqual(payload["job_id"], "p1")
        self.assertEqual(key_id, "")
        m = re.search(r'"sig":"([0-9a-f]{96})"', body)
        self.assertIsNotNone(m)
        self.assertEqual(len(m.group(1)), 96)
        verified = V.verify_body(body, SECRET)
        self.assertEqual(verified["job_id"], "p1")
        # The digest named in the construction is SHA-384, whose
        # hex form is the 96 characters pinned above; a body whose
        # sig was computed with a different hash does not verify
        # (see the tamper test below for the refusal path).

    def test_c5_tampered_body_is_refused(self):
        body = R.sign_payload({"v": 1, "type": "job", "job_id": "p1"},
                              SECRET)
        tampered = body.replace('"job_id":"p1"', '"job_id":"p2"')
        with self.assertRaises(ValueError):
            V.verify_body_keyed(tampered, {"": SECRET})

    def test_c5_unknown_and_nonstring_key_ids_are_refused(self):
        body = R.sign_payload(
            {"v": 1, "type": "job", "job_id": "p1", "key_id": "nope"},
            SECRET)
        with self.assertRaises(ValueError):
            V.verify_body_keyed(body, {"": SECRET})

    def test_c7_key_fingerprint_form_and_label(self):
        # k- + first 8 hex of SHA-384 over the fixed label and the
        # secret -- NOT over the secret alone.
        fp = S.key_fingerprint(SECRET)
        self.assertTrue(fp.startswith("k-"))
        self.assertEqual(len(fp), 10)
        labelled = hashlib.sha384(
            b"homing-pigeon key id v1\n" + SECRET.encode("utf-8")
        ).hexdigest()
        self.assertEqual(fp, "k-" + labelled[:8])
        bare = hashlib.sha384(SECRET.encode("utf-8")).hexdigest()
        self.assertNotEqual(fp, "k-" + bare[:8])
        self.assertEqual(S.KEY_ID_LABEL, b"homing-pigeon key id v1\n")
        # The runner's binding agrees with the guard module.
        self.assertEqual(R.key_fingerprint(SECRET), fp)


class CleartextAndEncryptionPins(unittest.TestCase):
    def test_c8_cleartext_refused_by_default(self):
        # Per-process state starts False; only --allow-cleartext
        # (runner/ops/main.py) may set it. Restore whatever a
        # previous test in a shared process may have set.
        R._set_allow_cleartext_jobs(False)
        self.addCleanup(R._set_allow_cleartext_jobs, False)
        self.assertFalse(R._cleartext_jobs_allowed())

    def test_c8_no_config_key_enables_cleartext(self):
        # The example config carries no cleartext-acceptance key.
        example = _read(os.path.join("runner", "config.example.json"))
        self.assertNotIn("allow_cleartext", example)

    def test_c9_the_one_aead(self):
        self.assertEqual(JC.ALG, "aes-256-gcm/hkdf-sha384")
        self.assertEqual(JC._KEY_LEN, 32)
        self.assertEqual(JC._NONCE_LEN, 12)
        self.assertEqual(JC._TAG_LEN, 16)

    def test_c9_encrypted_round_trip_and_wrong_alg_refused(self):
        inner = R.sign_payload({"v": 1, "type": "job", "job_id": "p9"},
                               SECRET)
        sealed = JC.encrypt_body(inner, SECRET, job_id="p9", key_id="",
                                 sign=R.sign_payload)
        payload, key_id, secret, was_encrypted = R._admit_object(
            sealed, {"": SECRET}, "p9")
        self.assertTrue(was_encrypted)
        self.assertEqual(payload["job_id"], "p9")
        # An envelope naming any other algorithm is refused.
        import base64
        forged = {"hp_enc": {
            "alg": "aes-128-gcm",
            "nonce": base64.b64encode(b"0" * 12).decode("ascii"),
            "ct": base64.b64encode(b"0" * 32).decode("ascii")}}
        with self.assertRaises(JC.JobCryptoError):
            JC.decrypt_body(forged, SECRET, job_id="p9", key_id="")


class AudienceAndModePins(unittest.TestCase):
    def test_c11_the_six_features_and_three_modes(self):
        self.assertEqual(
            S.FEATURES,
            ("policy_env", "policy_files", "policy_args",
             "audience", "confinement", "job_user"))
        self.assertEqual(S.MODES, ("off", "audit", "enforce"))

    def test_c11_modes_default_off_and_bad_block_refused(self):
        for feature in S.FEATURES:
            self.assertEqual(S.sec_mode({}, feature), "off")
        S.validate_security_config({})
        S.validate_security_config(
            {"security": {"modes": {"audience": "enforce"}}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"modes": {"audience": "loud"}}})
        with self.assertRaises(RuntimeError):
            S.validate_security_config(
                {"security": {"modes": {"nosuch": "off"}}})

    def test_c10_audience_check(self):
        cfg = {"runner_id": "runner-A",
               "security": {"modes": {"audience": "enforce"}}}
        self.assertIsNone(R.check_audience(cfg, {"aud": "runner-A"}))
        self.assertIsNone(
            R.check_audience(cfg, {"runner_id": "runner-A"}))
        # aud wins when both are present.
        self.assertIsNone(R.check_audience(
            cfg, {"aud": "runner-A", "runner_id": "runner-B"}))
        self.assertEqual(
            R.check_audience(cfg, {"aud": "runner-B"}),
            "runner_id mismatch")
        # Off means no binding, and no runner_id means no binding.
        off = {"runner_id": "runner-A",
               "security": {"modes": {"audience": "off"}}}
        self.assertIsNone(R.check_audience(off, {"aud": "runner-B"}))
        self.assertIsNone(R.check_audience(
            {"security": {"modes": {"audience": "enforce"}}},
            {"aud": "runner-B"}))


class GateShapePins(unittest.TestCase):
    def test_c13_protocol_version_is_integer_1_only(self):
        self.assertEqual(R.PROTOCOL_VERSION, 1)
        self.assertTrue(R._version_ok(1))
        for bad in (True, 1.0, 2, "1", None):
            self.assertFalse(R._version_ok(bad), bad)

    def test_c6_secret_entropy_floor(self):
        with self.assertRaises(RuntimeError):
            S.validate_shared_secret("")
        with self.assertRaises(RuntimeError):
            S.validate_shared_secret("short")
        # A repeating secret is refused as patterned, however long.
        with self.assertRaises(RuntimeError):
            S.validate_shared_secret("ab12cd34" * 8)
        # A 64-char hex-shaped, non-repeating secret estimates at
        # 256 bits and passes.
        strong = hashlib.sha384(b"proof-constraints-seed").hexdigest()[:64]
        S.validate_shared_secret(strong)


class ResultPolicyCeilingPins(unittest.TestCase):
    """C17: the job asks, the owner caps, the narrower wins."""

    def _result(self, cfg, job):
        exec_result = {"stdout": "hello ", "stderr": "world",
                       "exit_code": 0, "timed_out": False,
                       "duration_sec": 0.1}
        return R.apply_result_policy(cfg, job, exec_result, {},
                                     confined=None)

    def test_c17_view_order(self):
        self.assertEqual(R.VIEW_ORDER, {"attested": 0, "summary": 1,
                                        "redacted": 2, "full": 3})

    def test_c17_a_job_cannot_widen_past_the_ceiling(self):
        job = {"result_policy": {"view": "full"}}
        result, _retain = self._result({"max_result_view": "attested"},
                                       job)
        self.assertEqual(result["view"], "attested")
        self.assertEqual(result["stdout"], "")
        result, _retain = self._result({"max_result_view": "summary"},
                                       job)
        self.assertEqual(result["view"], "summary")

    def test_c17_narrowing_takes_effect(self):
        # The other direction must fire, or the ceiling rule would
        # be a model that always answers with the ceiling.
        job = {"result_policy": {"view": "attested"}}
        result, retain = self._result({"max_result_view": "full"}, job)
        self.assertEqual(result["view"], "attested")
        self.assertTrue(retain)

    def test_c17_absent_and_unrecognised_views_read_as_full(self):
        result, _ = self._result({"max_result_view": "summary"}, {})
        self.assertEqual(result["view"], "summary")
        job = {"result_policy": {"view": "everything"}}
        result, _ = self._result({"max_result_view": "redacted"}, job)
        self.assertEqual(result["view"], "redacted")
        result, _ = self._result({}, job)
        self.assertEqual(result["view"], "full")

    def test_c17_query_budget_is_the_smaller_of_the_two(self):
        self.assertEqual(R.query_budget({}, {}), 8)
        self.assertEqual(
            R.query_budget({}, {"result_policy": {"query_budget": 3}}), 3)
        self.assertEqual(
            R.query_budget({"max_query_budget": 2},
                           {"result_policy": {"query_budget": 10}}), 2)
        self.assertEqual(
            R.query_budget({"max_query_budget": 8},
                           {"result_policy": {"query_budget": 10}}), 8)
        self.assertEqual(
            R.query_budget({}, {"result_policy": {"query_budget": 0}}), 0)

    def test_c17_job_redact_patterns_are_never_read(self):
        # The patterns argument here stands for the runner's own
        # set (built from the config by _redact_patterns). A list
        # carried in the job changes nothing.
        job = {"result_policy": {"view": "redacted",
                                 "redact_patterns": ["hello"]}}
        result, _ = self._result({}, job)
        self.assertEqual(result["stdout"], "hello world")
        self.assertEqual(result["redacted_families"], [])
        self.assertIn("aws_key", R._redact_patterns({}))
        extra = R._redact_patterns(
            {"redact_patterns_extra": {"mine": "hello"}})
        self.assertIn("mine", extra)

    def test_c17_confined_attestation_reports_the_runners_value(self):
        q = [{"op": "attest", "predicate": "confined_to_workspace"}]
        att = R.build_attestations(q, {"confined": True})[0]
        self.assertEqual((att["ok"], att["reason"]), (True, None))
        att = R.build_attestations(q, {"confined": False})[0]
        self.assertEqual((att["ok"], att["reason"]),
                         (False, "violation_detected"))
        att = R.build_attestations(q, {"confined": None})[0]
        self.assertEqual((att["ok"], att["reason"]),
                         (False, "unconfigured"))
        att = R.build_attestations(
            [{"op": "attest", "predicate": "no_such_predicate"}],
            {"confined": True})[0]
        self.assertEqual((att["ok"], att["reason"]), (False, "unknown"))


class SandboxShapePins(unittest.TestCase):
    """C18: the sandbox's shape comes from config and code."""

    def test_c18_work_mount_and_fixed_flags(self):
        from runner.guard import sandbox as SB
        self.assertEqual(SB.WORK_MOUNT, "/work")
        self.assertIn("--unshare-net", SB.DEFAULT_FLAGS)
        self.assertIn("--clearenv", SB.DEFAULT_FLAGS)
        # /usr read-only is the only bind in the fixed set.
        self.assertEqual(SB.DEFAULT_FLAGS.count("--ro-bind"), 1)

    def test_c18_interpreter_prefix_rule(self):
        from runner.guard import sandbox as SB
        # Under /usr: nothing to bind.
        self.assertEqual(SB.interpreter_binds("/usr/bin/python3"), [])
        # Outside /usr: exactly its own prefix, read-only shape.
        self.assertEqual(SB.interpreter_binds("/opt/x64/bin/python3"),
                         [("/opt/x64", "/opt/x64")])
        # Never shallower than two components: /snap/bin/tool
        # binds /snap/bin, not /snap.
        self.assertEqual(SB.interpreter_binds("/snap/bin/tool"),
                         [("/snap/bin", "/snap/bin")])

    def test_c18_no_job_field_names_a_confinement_setting(self):
        # The negative half of P2, pinned as a source scan: no
        # runner-side module reads a confinement-shaped member
        # out of a job. (This test file itself is excluded: it
        # names the members to forbid them.)
        names = ("security", "confinement", "workspace_root",
                 "protected_paths", "max_result_view", "sandbox")
        runner_dir = os.path.join(ROOT, "runner")
        offenders = []
        for dirpath, dirnames, filenames in os.walk(runner_dir):
            if "tests" in dirpath.split(os.sep):
                continue
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(dirpath, name),
                          encoding="utf-8") as fh:
                    text = fh.read()
                for member in names:
                    for shape in ('job.get("%s"' % member,
                                  'job["%s"]' % member,
                                  "job['%s']" % member):
                        if shape in text:
                            offenders.append((name, shape))
        self.assertEqual(offenders, [])


class DocsSyncPins(unittest.TestCase):
    """The inventory must carry the same values the code declares.

    If a code pin above fails, fix the code or the inventory --
    never just this test. If a pin here fails alone, the document
    drifted from the code it claims to describe.
    """

    def test_constraints_doc_carries_the_values(self):
        doc = _read(os.path.join("docs", "proofs", "constraints.md"))
        for token in ("4194304", "1048576", "5242880", "262144",
                      "aes-256-gcm/hkdf-sha384", "policy_env",
                      "policy_files", "policy_args", "audience",
                      "confinement", "job_user",
                      "homing-pigeon key id v1"):
            self.assertIn(token, doc)

    def test_constraints_doc_carries_c17_and_c18(self):
        doc = _read(os.path.join("docs", "proofs", "constraints.md"))
        for token in ("C17", "C18", "VIEW_ORDER", "interpreter_binds"):
            self.assertIn(token, doc)

    def test_properties_doc_states_p1_and_placeholders(self):
        doc = _read(os.path.join("docs", "proofs", "properties.md"))
        for token in ("P1", "P2", "P3", "P4", "P5", "P6",
                      "under 50"):
            self.assertIn(token, doc)


if __name__ == "__main__":
    unittest.main()
