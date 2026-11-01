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
their pins, from the same code, and then C19 and C20 (the
queues edge gates and the per-transport gate postures) with
theirs. P4's pass added the key-policy behaviour pins under
C14 and the new C21 and C22 (the key directory's precedence
and the upgrade key arrangement) with theirs. P5's pass added
the replay behaviour pins under C15 and the new C23, C24, and
C25 (the replay cache's keep horizon, the claim's stale rule,
and the record's retention and delivery window) with theirs.
P6's pass added C26 and C27 (the default-class reader and the
refuse class at startup) and the behaviour pins under them.
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


class KeyPolicyPins(unittest.TestCase):
    """C14/C21/C22: a key's policy binds exactly what it names.

    These are behaviour pins, not source scans: they drive the
    real check_key_policy and check_door_policy the way
    handle_mail and the other doors drive them, with policies
    built by the real build_key_policies.
    """

    PIN = hashlib.sha384(b"the pinned staging script").hexdigest()

    def _policies(self, entry, key="upgrade"):
        cfg = {"key_policies": {key: entry}}
        return V.build_key_policies(cfg), cfg

    def _upgrade(self):
        # The recorded arrangement (C22) with a stand-in digest:
        # execution only, one pinned script, a 300-second cap.
        return self._policies({
            "allowed_kinds": ["exec"],
            "allowed_script_sha384": [self.PIN],
            "max_timeout_sec": 300})

    def test_c22_upgrade_key_accepts_only_the_pinned_script(self):
        policies, cfg = self._upgrade()
        job = {"kind": "exec", "script": "the pinned staging script"}
        self.assertIsNone(
            V.check_key_policy(policies, "upgrade", cfg, job))
        # The clock job's shape: an execution job carrying any
        # other script is refused, with the recorded reason.
        clock = {"kind": "exec", "script": "date"}
        self.assertEqual(
            V.check_key_policy(policies, "upgrade", cfg, clock),
            "script is not in this key's allowlist")

    def test_c14_pinning_refuses_url_missing_and_beside(self):
        policies, cfg = self._upgrade()
        url_only = {"kind": "exec", "script_url": "https://x/y"}
        self.assertIsNotNone(
            V.check_key_policy(policies, "upgrade", cfg, url_only))
        # A script_url beside the pinned script is refused too:
        # the executor stages the URL first when both are present.
        beside = {"kind": "exec", "script": "the pinned staging script",
                  "script_url": "https://x/y"}
        self.assertIsNotNone(
            V.check_key_policy(policies, "upgrade", cfg, beside))
        missing = {"kind": "exec"}
        self.assertIsNotNone(
            V.check_key_policy(policies, "upgrade", cfg, missing))

    def test_c14_kinds_fence_refuses_every_other_kind(self):
        policies, cfg = self._upgrade()
        for kind in ("ping", "sensor_alert", "recipe", "change"):
            job = {"kind": kind, "script": "the pinned staging script"}
            self.assertIsNotNone(
                V.check_key_policy(policies, "upgrade", cfg, job), kind)
        # A job with no kind at all is refused by the same fence.
        self.assertIsNotNone(V.check_key_policy(
            policies, "upgrade", cfg,
            {"script": "the pinned staging script"}))

    def test_c14_timeout_cap_binds_the_pinned_key(self):
        policies, cfg = self._upgrade()
        over = {"kind": "exec", "script": "the pinned staging script",
                "timeout_sec": 301}
        self.assertIsNotNone(
            V.check_key_policy(policies, "upgrade", cfg, over))
        at = {"kind": "exec", "script": "the pinned staging script",
              "timeout_sec": 300}
        self.assertIsNone(V.check_key_policy(policies, "upgrade", cfg, at))

    def test_c14_no_entry_unrestricted_unless_default_deny(self):
        job = {"kind": "exec", "script": "anything at all"}
        self.assertIsNone(V.check_key_policy({}, "worker", {}, job))
        deny = {"key_policies_default_deny": True}
        self.assertIsNotNone(V.check_key_policy({}, "worker", deny, job))
        # The owner's key is exempt from the flag.
        self.assertIsNone(V.check_key_policy({}, "", deny, job))

    def test_c14_policy_is_the_keys_not_the_names(self):
        strong = hashlib.sha384(b"proof-constraints-seed").hexdigest()[:64]
        secrets = V.build_secrets({"shared_secret": strong})
        fp = S.key_fingerprint(strong)
        entry = {"allowed_kinds": ["exec"],
                 "allowed_script_sha384": [self.PIN]}
        policies = V.build_key_policies({"key_policies": {"": entry}})
        job = {"kind": "exec", "script": "some other script"}
        # An entry written for the default key binds it under its
        # fingerprint exactly as under the empty id: the policy is
        # read by the key's value, under any of its names.
        self.assertIsNotNone(V.check_key_policy(
            policies, fp, {}, job, secrets=secrets))
        self.assertIsNotNone(V.check_key_policy(
            policies, "", {}, job, secrets=secrets))
        good = {"kind": "exec", "script": "the pinned staging script"}
        self.assertIsNone(V.check_key_policy(
            policies, fp, {}, good, secrets=secrets))
        # And the deny flag never refuses the owner's key under
        # its fingerprint.
        deny = {"key_policies_default_deny": True}
        self.assertIsNone(V.check_key_policy(
            {}, fp, deny, good, secrets=secrets))

    def test_c14_recipes_and_interpreters_fences(self):
        policies, cfg = self._policies({
            "allowed_kinds": ["exec", "recipe"],
            "allowed_interpreters": [["sh"]],
            "allowed_recipes": ["nightly"]}, key="worker")
        bad = {"kind": "exec", "script": "x", "interpreter": ["bash"]}
        self.assertIsNotNone(
            V.check_key_policy(policies, "worker", cfg, bad))
        good = {"kind": "exec", "script": "x", "interpreter": ["sh"]}
        self.assertIsNone(
            V.check_key_policy(policies, "worker", cfg, good))
        # A recipe's interpreter is the owner's: the recipes list
        # governs it and the interpreter list does not bind it.
        rec = {"kind": "recipe", "recipe": "nightly",
               "interpreter": ["bash"]}
        self.assertIsNone(
            V.check_key_policy(policies, "worker", cfg, rec))
        rec2 = {"kind": "recipe", "recipe": "other"}
        self.assertIsNotNone(
            V.check_key_policy(policies, "worker", cfg, rec2))

    def test_c14_build_validates_and_lowercases(self):
        with self.assertRaises(RuntimeError):
            V.build_key_policies(
                {"key_policies": {"k": {"allowed_script_sha384": []}}})
        with self.assertRaises(RuntimeError):
            V.build_key_policies(
                {"key_policies": {"k": {"allowed_kinds": []}}})
        with self.assertRaises(RuntimeError):
            V.build_key_policies(
                {"key_policies": {"k": {"max_timeout_sec": True}}})
        policies, _cfg = self._policies(
            {"allowed_script_sha384": [self.PIN.upper()]}, key="k")
        self.assertEqual(policies["k"]["allowed_script_sha384"],
                         [self.PIN])

    def test_c14_build_refuses_one_key_entered_twice(self):
        strong = hashlib.sha384(b"proof-constraints-seed").hexdigest()[:64]
        fp = S.key_fingerprint(strong)
        cfg = {"shared_secret": strong,
               "key_policies": {"": {"allowed_kinds": ["exec"]},
                                fp: {"allowed_kinds": ["exec"]}}}
        with self.assertRaises(RuntimeError):
            V.build_key_policies(cfg)

    def test_c21_directory_speaks_before_the_policy(self):
        policies, _cfg = self._upgrade()
        job = {"kind": "exec", "script": "the pinned staging script"}
        # The policy allows this job; a directory that refuses
        # the key refuses it first.
        cfg = {"key_directory": {"upgrade": {"state": "compromised"}}}
        self.assertEqual(
            V.check_key_policy(policies, "upgrade", cfg, job),
            "key is compromised")
        # A held key with no entry in a configured directory is
        # refused as well.
        cfg2 = {"key_directory": {"other": {"state": "in_use"}}}
        self.assertEqual(
            V.check_key_policy(policies, "upgrade", cfg2, job),
            "no key directory entry for this key")

    def test_c14_door_policy_binds_the_other_doors(self):
        cfg = {"key_policies": {"upgrade": {
            "allowed_kinds": ["exec"],
            "allowed_script_sha384": [self.PIN]}}}
        for door in ("query", "board", "v2"):
            self.assertIsNotNone(
                V.check_door_policy(cfg, None, "upgrade", door), door)
        # The cancel door is exempt from the kinds list -- a key
        # cancels its own jobs -- but not from the deny flag.
        self.assertIsNone(
            V.check_door_policy(cfg, None, "upgrade", "cancel"))
        deny = {"key_policies_default_deny": True}
        self.assertIsNotNone(
            V.check_door_policy(deny, None, "worker", "query"))
        self.assertIsNone(V.check_door_policy(deny, None, "", "query"))


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


class TransportGatePins(unittest.TestCase):
    """C19/C20: the transport gates stand where P3 says they do.

    These are source-scan pins: each transport's gate lives in
    its extension, at the far end it talks to, or (file) in the
    operating system, and the core attests none of it. What can
    be pinned is that the gate sites the statement names are
    the sites the code has -- the refusal texts, the order of
    the queues edge checks, and the one write path into the
    core's gate.
    """

    def test_c20_nats_credentials_required_unless_literal_true(self):
        text = _read(os.path.join(
            "runner", "transport_extensions", "nats", "__main__.py"))
        # The waiver is the literal value True and nothing else.
        self.assertIn(
            'cfg.get("allow_unauthenticated") is True', text)
        # No credentials and no waiver is a refusal to start.
        self.assertIn("refuses to start: no broker", text)
        self.assertIn("first authorization gate", text)

    def test_c20_file_extension_has_no_credential_of_its_own(self):
        # The honest negative half of P3's file clause: nothing
        # in the extension's code checks a credential; the gate
        # is the inbox directory's OS access control.
        text = _read(os.path.join(
            "runner", "transport_extensions", "file", "__main__.py"))
        for word in ("password", "token", "credential"):
            self.assertNotIn(word, text)

    def test_c20_dtls_no_secret_no_start_and_established_only(self):
        ext = _read(os.path.join(
            "runner", "transport_extensions", "dtls", "__main__.py"))
        self.assertIn("no shared_secret was handed", ext)
        proto = _read(os.path.join("runner", "wire", "dtlsproto.py"))
        # Application data before the session is established is
        # dropped, in the server session's authenticated feed.
        self.assertIn("application data before the session", proto)
        self.assertIn("PSK binder mismatch", proto)
        self.assertIn("unknown PSK identity", proto)

    def test_c19_queues_extension_refuses_to_start_tokenless(self):
        text = _read(os.path.join(
            "runner", "transport_extensions", "queues", "__main__.py"))
        self.assertIn("no runner token", text)
        # Every call carries the bearer token.
        self.assertIn('"Authorization": f"Bearer {self.token}"', text)

    def test_c19_queues_edge_checks_bearer_before_signature(self):
        text = _read(os.path.join(
            "runner", "cloud", "queues-worker", "src", "index.js"))
        # The edge signature check is on by default.
        self.assertIn('env.REJECT_INVALID_HMAC ?? "true"', text)
        # In the submission route, the SI bearer check comes
        # before the edge signature verdict.
        block = text[text.index("// SI submits a job."):]
        bearer = block.index(
            "bearerMatches(request, tenant.si_token_sha256)")
        verdict = block.index("signatureVerdict")
        self.assertLess(bearer, verdict)
        # A role with no stored hash refuses every token.
        self.assertIn("if (!m || !wantHash) return false", text)

    def test_c20_channel_envelopes_face_the_core_gate(self):
        # The composition point: a transported envelope becomes a
        # synthetic message and handle_mail -- the whole of P1,
        # signature included -- is what it faces.
        text = _read(os.path.join("runner", "runner.py"))
        self.assertIn(
            'handle_mail(cfg, imap, cap, "transport", raw', text)
        # And only DTLS is handed secret material, because it
        # terminates authentication itself; only email is handed
        # the mailbox keys.
        wire = _read(os.path.join("runner", "wire", "transports.py"))
        dtls_at = wire.index('if name == "dtls":')
        handed = wire.index("out.update(_dtls_secret_material(cfg))")
        self.assertLess(dtls_at, handed)
        self.assertIn('if name == "email":', wire)


class ReplayPins(unittest.TestCase):
    """C15's mechanics against the real functions (P5): the
    cache's horizon, the claim's stale rule, and the record a
    redelivery is answered from, bound to the job's digest."""

    def test_c23_seen_keep_horizon_outlasts_freshness(self):
        # The floor: one day, whatever the freshness window is.
        self.assertEqual(R.seen_keep_sec({}), 86400)
        self.assertEqual(R.seen_keep_sec({"max_job_age_sec": 3600}),
                         86400)
        # Past the floor, the horizon is the window plus the
        # 300-second future bound, exactly.
        self.assertEqual(R.seen_keep_sec({"max_job_age_sec": 100000}),
                         100300)
        self.assertEqual(R.SEEN_KEEP_FLOOR, 86400)

    def test_c23_seen_cap(self):
        self.assertEqual(V.SEEN_CAP, 200_000)
        self.assertEqual(R.SEEN_CAP, 200_000)

    def test_c23_seen_write_drops_entries_past_the_horizon(self):
        import tempfile
        import time as _time
        old = R._SEEN_KEEP[0]
        R._SEEN_KEEP[0] = 86400
        try:
            with tempfile.TemporaryDirectory() as base:
                path = os.path.join(base, "seen.json")
                now = _time.time()
                kept = R._write_seen_kept(
                    path, {"fresh": now, "stale": now - 90000})
                self.assertIn("fresh", kept)
                self.assertNotIn("stale", kept)
        finally:
            R._SEEN_KEEP[0] = old

    def test_c24_claim_stale_constant(self):
        self.assertEqual(R._CLAIM_STALE_SEC, 86400)

    def test_c24_disk_claim_live_dead_and_unreadable(self):
        import subprocess
        import tempfile
        import time as _time
        with tempfile.TemporaryDirectory() as base:
            # A free id is claimed.
            self.assertTrue(R._disk_owns(base, "pin-claim", {}))
            folder, claim = R._claim_path(base, "pin-live")
            os.makedirs(folder, exist_ok=True)
            # A live holder's claim is never taken. The holder is
            # this interpreter sleeping, not a platform command:
            # "sleep" is not a Windows program name.
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                with open(claim, "w", encoding="utf-8") as fh:
                    fh.write("%d\n%f\npin-live\n" % (proc.pid,
                                                     _time.time()))
                self.assertFalse(R._disk_owns(base, "pin-live", {}))
            finally:
                proc.kill()
                proc.wait()
            # A dead holder's claim is stolen at once. On Windows
            # a just-killed child's process object can still be
            # opened through the handle Popen holds, and a handle
            # means alive (the PidAliveWindowsBranchTest pin), so
            # the dead holder named on Windows is a pid with no
            # process at all -- the dead-pid shape the v2 message
            # tests use there. Elsewhere the killed child's own
            # pid is the dead holder, as before.
            dead_pid = proc.pid
            if os.name == "nt":
                dead_pid = 2 ** 22
                self.assertFalse(R._pid_alive(dead_pid))
            with open(claim, "w", encoding="utf-8") as fh:
                fh.write("%d\n%f\npin-live\n" % (dead_pid,
                                                 _time.time()))
            self.assertTrue(R._disk_owns(base, "pin-live", {}))
            # An unreadable holder is taken only at the stale age.
            folder2, claim2 = R._claim_path(base, "pin-garbled")
            with open(claim2, "w", encoding="utf-8") as fh:
                fh.write("not-a-pid\n%f\npin-garbled\n" % _time.time())
            self.assertFalse(R._disk_owns(base, "pin-garbled", {}))
            old = _time.time() - 90000
            os.utime(claim2, (old, old))
            self.assertTrue(R._disk_owns(base, "pin-garbled", {}))

    def test_c25_retention_and_stash_window_defaults(self):
        self.assertEqual(R._retention_days({}), 7)
        self.assertEqual(R._retention_days(
            {"output_retention_days": 0}), 0)
        self.assertEqual(R._retention_days(
            {"output_retention_days": 3}), 3)
        self.assertEqual(R._stash_retention_sec({}), 86400)
        self.assertEqual(R._resend_backoff_sec({}), 60)

    def test_c15_record_answers_only_its_own_job(self):
        import tempfile
        job = {"job_id": "p5-pin-1", "kind": "exec", "script": "x"}
        with tempfile.TemporaryDirectory() as base:
            self.assertTrue(R.stash_result(
                base, "p5-key", job, "subject", "the result body"))
            rec = R.load_sent_result(base, "p5-key", job)
            self.assertIsNotNone(rec)
            self.assertEqual(rec["body"], "the result body")
            # A different job under the same id gets no record:
            # the digest does not match, so nothing is answered
            # from the first job's result.
            altered = dict(job, script="y")
            self.assertIsNone(R.load_sent_result(
                base, "p5-key", altered))
            # The same record answers from sent/ as from the
            # outbox.
            self.assertTrue(R._stash_move(
                base, "p5-key", os.path.join(base, "sent")))
            self.assertIsNotNone(R.load_sent_result(
                base, "p5-key", job))

    def test_c15_received_digest_excludes_only_the_signature(self):
        digest = R._opinion.received_digest
        self.assertEqual(digest({"a": 1, "sig": "x"}),
                         digest({"a": 1, "sig": "y"}))
        self.assertNotEqual(digest({"a": 1, "sig": "x"}),
                            digest({"a": 2, "sig": "x"}))


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

    def test_constraints_doc_carries_c19_and_c20(self):
        doc = _read(os.path.join("docs", "proofs", "constraints.md"))
        for token in ("C19", "C20", "REJECT_INVALID_HMAC",
                      "allow_unauthenticated"):
            self.assertIn(token, doc)

    def test_properties_doc_states_p3_in_full(self):
        doc = _read(os.path.join("docs", "proofs", "properties.md"))
        for token in ("TransGate.tla", "stage4-p3.md",
                      "A waived gate is a waived property"):
            self.assertIn(token, doc)

    def test_properties_doc_states_p4_in_full(self):
        doc = _read(os.path.join("docs", "proofs", "properties.md"))
        for token in ("KeyPolicy.tla", "stage4-p4.md",
                      "check_key_policy"):
            self.assertIn(token, doc)

    def test_constraints_doc_carries_c21_and_c22(self):
        doc = _read(os.path.join("docs", "proofs", "constraints.md"))
        for token in ("C21", "C22", "key_directory_verdict",
                      "max_timeout_sec", "SHA384SUMS"):
            self.assertIn(token, doc)

    def test_constraints_doc_carries_c23_to_c25(self):
        doc = _read(os.path.join("docs", "proofs", "constraints.md"))
        for token in ("C23", "C24", "C25", "seen_keep_sec",
                      "_CLAIM_STALE_SEC", "result_stash_retention_sec",
                      "200,000"):
            self.assertIn(token, doc)

    def test_properties_doc_states_p5_in_full(self):
        doc = _read(os.path.join("docs", "proofs", "properties.md"))
        for token in ("Replay.tla", "stage4-p5.md",
                      "load_sent_result"):
            self.assertIn(token, doc)

    def test_properties_doc_states_p6_in_full(self):
        doc = _read(os.path.join("docs", "proofs", "properties.md"))
        for token in ("Decision.tla", "stage4-p6.md",
                      "is_defaulted", "reload_hot_config"):
            self.assertIn(token, doc)

    def test_constraints_doc_carries_c26_and_c27(self):
        doc = _read(os.path.join("docs", "proofs", "constraints.md"))
        for token in ("C26", "C27", "summary_line", "HOT_KEYS",
                      "_validate_size_caps"):
            self.assertIn(token, doc)

    def test_properties_doc_states_p1_and_placeholders(self):
        doc = _read(os.path.join("docs", "proofs", "properties.md"))
        for token in ("P1", "P2", "P3", "P4", "P5", "P6",
                      "under 50"):
            self.assertIn(token, doc)


class DecisionPins(unittest.TestCase):
    """C26 and C27: the default class names its fallback, and the
    refuse class stops at startup and is not live-reloaded."""

    def test_a_bool_is_not_a_number_and_an_absent_key_is_not_named(self):
        from runner.guard import confval
        from runner.guard import defaulted

        self.assertEqual(confval.integer(True, 20), 20)
        self.assertEqual(confval.integer(None, 20), 20)
        self.assertEqual(confval.integer("nope", 20), 20)
        self.assertEqual(confval.integer(7, 20), 7)
        self.assertEqual(confval.port(0, 20220), 20220)
        self.assertEqual(confval.port(443, 20220), 443)
        self.assertFalse(defaulted.is_defaulted("poll_interval_sec", None))
        self.assertTrue(defaulted.is_defaulted("poll_interval_sec", True))
        self.assertTrue(defaulted.is_defaulted("poll_interval_sec", "nope"))
        self.assertFalse(defaulted.is_defaulted("poll_interval_sec", 7))
        line = defaulted.summary_line(["poll_interval_sec"])
        self.assertIn("poll_interval_sec", line)
        self.assertIn("1 setting", line)

    def test_a_bad_size_cap_and_a_bad_port_name_themselves(self):
        self.assertIsNone(R._validate_size_caps({}))
        self.assertIsNone(R._validate_size_caps({"max_job_bytes": 0}))
        err = R._validate_size_caps({"max_job_bytes": True})
        self.assertIn("max_job_bytes", err)
        err = R._validate_size_caps({"max_script_bytes": -1})
        self.assertIn("max_script_bytes", err)
        self.assertEqual(R._port({}, "imap_port", 993), 993)
        with self.assertRaises(RuntimeError) as raised:
            R._port({"imap_port": True}, "imap_port", 993)
        self.assertIn("imap_port", str(raised.exception))
        self.assertIn("config error", str(raised.exception))

    def test_a_live_reload_defaults_a_tunable_and_leaves_a_port(self):
        import json
        import tempfile
        from runner.runner import reload_hot_config

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "poll_interval_sec": "nope",
                    "imap_port": True,
                }, fh)
            cfg = {"poll_interval_sec": 7, "imap_port": 993}
            changed = reload_hot_config(cfg, path, {"mtime": 0})
        self.assertEqual(cfg["poll_interval_sec"], 20)
        self.assertIn("poll_interval_sec", changed)
        self.assertEqual(cfg["imap_port"], 993)
        self.assertNotIn("imap_port", changed)


if __name__ == "__main__":
    unittest.main()
