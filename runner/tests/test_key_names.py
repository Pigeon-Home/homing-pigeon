# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Every secret has a name (Q94, 3.14.2).

A secret's default name is its fingerprint: `k-` and the first eight
hex digits of SHA-384 over a fixed label and the secret. Anyone who
holds the secret can compute it, so the installer prints it beside
the secret, a sender's keyring stores the two together, `send_job.py
key-id` recovers it from a bare secret, and the runner's default key
answers to it as well as to the empty key id senders used before.
The name travels in the open: the pong's platform card lists the
key ids a runner accepts, and every result names the key that
verified its job. Names only, never a value -- the tests here hold
that line as much as the feature."""

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.cloud import send_job  # noqa: E402
from runner.guard import security  # noqa: E402
from runner.ops import install as inst  # noqa: E402
from runner.ops.policy import apply_result_policy  # noqa: E402
from runner.wire import jobcrypto, protocol_v2 as v2, verify as V  # noqa: E402
from runner.tests.security_parity import FakeIMAP, FakeSMTP  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: the
# harness class would run its own tests again under this module's name)

SECRET = "3a7f0c91d2e45b68f1a2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718"
OTHER = "9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a"
CANARY = "c0ffee5417b2a9d3e8f1046c5b7a2d9e3f8c1b6a5d4e7f2093a1b8c5d6e4f7a2"
NAME = re.compile(r"^k-[0-9a-f]{8}$")


def _result(sent, secret):
    """A sent result's signed inner body, read with the key named."""
    body = sent.get_content()
    parsed = send_job.verify_body(body, secret)
    if jobcrypto.is_envelope(parsed):
        jid = str(sent["Subject"]).rsplit(" ", 1)[-1]
        body = jobcrypto.decrypt_body(parsed, secret, jid,
                                      parsed.get("key_id") or "")
    return send_job.verify_body(body, secret)


class FingerprintTest(unittest.TestCase):
    def test_the_three_copies_agree_and_are_the_labelled_hash(self):
        # The runner, the sender and the installer each carry the
        # function (the last two run by path); one secret, one name.
        by_hand = "k-" + hashlib.sha384(
            b"homing-pigeon key id v1\n" + SECRET.encode("utf-8")
        ).hexdigest()[:8]
        for copy in (security.key_fingerprint, send_job.key_fingerprint,
                     inst.key_fingerprint, R.key_fingerprint):
            self.assertEqual(copy(SECRET), by_hand, copy.__module__)
        self.assertEqual(security.KEY_ID_LABEL, send_job.KEY_ID_LABEL)
        self.assertEqual(security.KEY_ID_LABEL, inst._KEY_ID_LABEL)

    def test_the_name_is_short_fixed_and_fits_a_key_id(self):
        for secret in (SECRET, OTHER, "x" * 64, "é" * 40):
            name = security.key_fingerprint(secret)
            self.assertRegex(name, NAME)
            self.assertEqual(name, security.key_fingerprint(secret))
            self.assertTrue(inst._KEY_ID.match(name), name)
        self.assertNotEqual(security.key_fingerprint(SECRET),
                            security.key_fingerprint(OTHER))
        # The label keeps this hash apart from a bare hash of the
        # secret and from everything else the key derives.
        bare = hashlib.sha384(SECRET.encode("utf-8")).hexdigest()[:8]
        self.assertNotEqual(security.key_fingerprint(SECRET), "k-" + bare)

    def test_a_name_is_not_a_value(self):
        # Eight hex digits of a one-way function: the name does not
        # contain the secret, and a secret cannot be read back from
        # it. (A signed message is already the oracle a guesser
        # would use; the name adds none.)
        name = security.key_fingerprint(SECRET)
        self.assertNotIn(name[2:], SECRET)
        self.assertEqual(len(name), 10)

    def test_only_a_string_has_a_name(self):
        for bad in (None, 7, b"bytes", ["s"]):
            with self.assertRaises(TypeError):
                security.key_fingerprint(bad)
            with self.assertRaises(ValueError):
                send_job.key_fingerprint(bad)


class SecretsMapTest(unittest.TestCase):
    def test_the_default_key_answers_to_its_fingerprint_and_the_empty_id(self):
        secrets = V.build_secrets({"shared_secret": SECRET})
        name = security.key_fingerprint(SECRET)
        self.assertEqual(secrets, {"": SECRET, name: SECRET})
        with_more = V.build_secrets({"shared_secret": SECRET,
                                     "additional_secrets": {"ops": OTHER}})
        # Every secret answers to its fingerprint (section 14.2; Q98
        # item 15): a sender handed only OTHER names it the one way
        # it can, by computing the name.
        self.assertEqual(with_more, {"": SECRET, name: SECRET, "ops": OTHER,
                                     security.key_fingerprint(OTHER): OTHER})

    def test_an_additional_secret_answers_to_its_fingerprint(self):
        secrets = V.build_secrets({"shared_secret": SECRET,
                                   "additional_secrets": {"ops": OTHER}})
        fp = security.key_fingerprint(OTHER)
        self.assertEqual(V.secret_named(secrets, fp), OTHER)
        # The owner's name stays the count name: windows and retained
        # records keyed under "ops" do not move.
        self.assertEqual(V.canonical_key_id(secrets, fp), "ops")
        pols = V.build_key_policies({"shared_secret": SECRET,
                                     "additional_secrets": {"ops": OTHER},
                                     "key_policies": {"ops": {"allowed_kinds": ["ping"]}}})
        self.assertEqual(V.policy_for(pols, secrets, fp), {"allowed_kinds": ["ping"]})

    def test_a_name_that_is_another_secrets_fingerprint_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "names another secret"):
            V.build_secrets({"shared_secret": SECRET,
                             "additional_secrets": {
                                 "ops": OTHER,
                                 security.key_fingerprint(OTHER): CANARY}})

    def test_another_secret_cannot_take_the_default_keys_name(self):
        name = security.key_fingerprint(SECRET)
        with self.assertRaisesRegex(RuntimeError, "default key's own name"):
            V.build_secrets({"shared_secret": SECRET,
                             "additional_secrets": {name: OTHER}})
        # The same value under that name is the same key, not a clash.
        same = V.build_secrets({"shared_secret": SECRET,
                                "additional_secrets": {name: SECRET}})
        self.assertEqual(same[name], SECRET)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "k")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(OTHER + "\n")
            with self.assertRaisesRegex(RuntimeError, "default key's own name"):
                V.build_secrets({"shared_secret": SECRET,
                                 "additional_secrets_files": {name: path}})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(SECRET + "\n")
            self.assertEqual(V.build_secrets(
                {"shared_secret": SECRET,
                 "additional_secrets_files": {name: path}})[name], SECRET)

    def test_a_map_built_by_hand_names_its_default_the_same_way(self):
        name = security.key_fingerprint(SECRET)
        self.assertEqual(V.secret_named({"": SECRET}, name), SECRET)
        self.assertEqual(V.secret_named({"": SECRET}, ""), SECRET)
        self.assertEqual(V.secret_named({"": SECRET, "ops": OTHER}, "ops"),
                         OTHER)
        self.assertIsNone(V.secret_named({"": SECRET}, "k-00000000"))
        self.assertIsNone(V.secret_named({"": SECRET},
                                         security.key_fingerprint(OTHER)))
        self.assertIsNone(V.secret_named({"ops": OTHER}, name))
        self.assertIsNone(V.secret_named({"": SECRET}, None))
        self.assertIsNone(V.secret_named("not a map", name))
        self.assertIs(R.secret_named, V.secret_named)

    def test_a_body_named_by_fingerprint_verifies_against_a_bare_map(self):
        name = security.key_fingerprint(SECRET)
        body = send_job.sign_payload(
            {"v": 1, "type": "job", "job_id": "k-n-0001", "kind": "ping",
             "key_id": name}, SECRET)
        payload, key_id = V.verify_body_keyed(body, {"": SECRET})
        self.assertEqual(key_id, name)
        self.assertEqual(payload["kind"], "ping")
        with self.assertRaisesRegex(ValueError, "unknown key_id"):
            V.verify_body_keyed(body, {"": OTHER})


class _MailTest(unittest.TestCase):
    """Composition over the runner harness (as test_platformcard does):
    a subclass would run the harness's own tests again."""

    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.cfg["shared_secret"] = SECRET
        self.addCleanup(shutil.rmtree, self.h.tmp, True)

    def _send(self, payload, secret=SECRET):
        _, smtp, _ = self.h.run_cycle([TR.job_email(payload, secret=secret)])
        self.assertEqual(len(smtp.sent), 1)
        return _result(smtp.sent[0], secret)


class ResultNamesItsKeyTest(_MailTest):
    def test_an_unnamed_job_learns_the_default_keys_name(self):
        result = self._send(TR.job_payload(str(uuid.uuid4())))
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["key_id"], security.key_fingerprint(SECRET))

    def test_a_job_named_by_fingerprint_is_answered_under_it(self):
        name = security.key_fingerprint(SECRET)
        result = self._send(TR.job_payload(str(uuid.uuid4()), key_id=name))
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["key_id"], name)

    def test_an_additional_key_is_named_as_configured(self):
        self.cfg["additional_secrets"] = {"ops": OTHER}
        result = self._send(TR.job_payload(str(uuid.uuid4()), key_id="ops"),
                            secret=OTHER)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["key_id"], "ops")
        self.assertNotIn(OTHER, json.dumps(result))

    def test_a_rejection_names_the_key_too(self):
        result = self._send(TR.job_payload(str(uuid.uuid4()),
                                           kind="definitely-not-a-kind"))
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("job rejected", result["stderr"])
        self.assertEqual(result["key_id"], security.key_fingerprint(SECRET))

    def test_a_result_under_a_narrow_view_still_names_the_key(self):
        # The policy rebuilds the result for the view it asks for;
        # the name rides every view (a ping, so the simulated surface
        # runs it too).
        for view in ("redacted", "summary", "attested"):
            result = self._send(TR.job_payload(
                str(uuid.uuid4()), result_policy={"view": view}))
            self.assertEqual(result["view"], view)
            self.assertEqual(result["key_id"], security.key_fingerprint(SECRET),
                             view)
            self.assertNotIn(SECRET, json.dumps(result))

    def test_the_policy_views_keep_the_name(self):
        exec_result = {"exit_code": 0, "timed_out": False, "stdout": "x\n",
                       "stderr": "", "duration_sec": 0.1, "key_id": "ops"}
        for view in sorted(R.VIEW_ORDER):
            cfg = {"max_result_view": view}
            job = {"job_id": "k-v-0001", "kind": "exec",
                   "result_policy": {"view": view}}
            out, _retain = apply_result_policy(cfg, job, dict(exec_result),
                                               {}, False)
            self.assertEqual(out.get("key_id"), "ops", view)
            self.assertEqual(out["view"], view)
        bare, _retain = apply_result_policy(
            {}, {"job_id": "k-v-0002"},
            {"exit_code": 0, "stdout": "", "stderr": ""}, {}, False)
        self.assertNotIn("key_id", bare)

    def test_the_name_helper_never_hands_out_a_value(self):
        name = security.key_fingerprint(SECRET)
        self.assertEqual(R._key_name("ops", SECRET), "ops")
        self.assertEqual(R._key_name("", SECRET), name)
        self.assertEqual(R._key_name(None, SECRET), name)
        self.assertEqual(R._key_name("", None), "")
        self.assertNotIn(SECRET, R._key_name("", SECRET))


class PongListsTheKeyIdsTest(_MailTest):
    def test_the_card_names_every_key_and_no_value(self):
        self.cfg["additional_secrets"] = {"ops": OTHER, "canary-key": CANARY}
        result = self._send(TR.job_payload(str(uuid.uuid4())))
        card = result["platform"]
        self.assertEqual(card["key_ids"], sorted(
            [security.key_fingerprint(SECRET), "canary-key", "ops",
             security.key_fingerprint(OTHER), security.key_fingerprint(CANARY)]))
        self.assertNotIn("", card["key_ids"])
        text = json.dumps(result)
        for value in (SECRET, OTHER, CANARY):
            self.assertNotIn(value, text)

    def test_the_card_lists_the_name_at_every_tier_that_sends_one(self):
        # (`full` reads the PATH, which the simulated Windows surface
        # cannot; test_platformcard covers that tier's own members.)
        for tier in ("family", "standard"):
            self.cfg["pong_platform"] = tier
            result = self._send(TR.job_payload(str(uuid.uuid4())))
            self.assertEqual(result["platform"]["key_ids"],
                             [security.key_fingerprint(SECRET)], tier)
        self.cfg["pong_platform"] = "none"
        self.assertNotIn("platform",
                         self._send(TR.job_payload(str(uuid.uuid4()))))

    def test_an_unreadable_key_map_lists_nothing_rather_than_failing(self):
        with mock.patch.object(R, "build_secrets",
                               side_effect=RuntimeError("config error")):
            card = R.pong_platform({"shared_secret": SECRET})
        self.assertEqual(card["key_ids"], [])


class OneKeyManyNamesTest(unittest.TestCase):
    """A key is its value (Q94): the default key's empty id, its
    fingerprint and any additional name the installer stored the
    same secret under are one key, and every rule that knows a key
    by name reads it so. Without this, naming the default key by
    fingerprint would have changed what the rules did -- the deny
    flag would have refused the owner's own jobs."""

    # An additional key's second name is its fingerprint: one secret
    # under two configured names is refused (Q98 item 15, the
    # conductor's ruling), so no config gives it two of its own.
    CFG = {"shared_secret": SECRET,
           "additional_secrets": {"ops": OTHER, "prod-1": SECRET}}
    FO = security.key_fingerprint(OTHER)

    def setUp(self):
        self.secrets = V.build_secrets(self.CFG)
        self.fp = security.key_fingerprint(SECRET)

    def test_the_names_of_a_key(self):
        self.assertEqual(V.key_names(self.secrets, ""), ("", self.fp, "prod-1"))
        self.assertEqual(V.key_names(self.secrets, self.fp),
                         (self.fp, "", "prod-1"))
        self.assertEqual(V.key_names(self.secrets, "prod-1"),
                         ("prod-1", "", self.fp))
        self.assertEqual(V.key_names(self.secrets, "ops"), ("ops", self.FO))
        self.assertEqual(V.key_names(self.secrets, self.FO), (self.FO, "ops"))
        self.assertEqual(V.key_names(self.secrets, "nobody"), ("nobody",))
        self.assertEqual(V.key_names(self.secrets, None), (None,))
        self.assertEqual(V.key_names("not a map", "ops"), ("ops",))
        # A map built by hand names its default the same way.
        self.assertEqual(V.key_names({"": SECRET}, self.fp), (self.fp, ""))
        self.assertEqual(V.key_names({"": SECRET}, ""), ("", self.fp))
        for name in ("", self.fp, "prod-1"):
            self.assertTrue(V.is_default_key(self.secrets, name), name)
        for name in ("ops", self.FO, "nobody", None):
            self.assertFalse(V.is_default_key(self.secrets, name), name)
        self.assertIs(R.key_names, V.key_names)

    def test_one_name_to_count_under(self):
        for name in ("", self.fp, "prod-1"):
            self.assertEqual(V.canonical_key_id(self.secrets, name), "")
        self.assertEqual(V.canonical_key_id(self.secrets, "ops"), "ops")
        self.assertEqual(V.canonical_key_id(self.secrets, self.FO), "ops")
        self.assertEqual(V.canonical_key_id(self.secrets, "nobody"), "nobody")
        self.assertEqual(V.canonical_key_id(self.secrets, None), None)

    def test_a_policy_under_any_name_is_the_keys_policy(self):
        pol = {"allowed_kinds": ["ping"]}
        for under in ("", self.fp, "prod-1"):
            policies = {under: pol}
            for name in ("", self.fp, "prod-1"):
                self.assertIs(V.policy_for(policies, self.secrets, name), pol,
                              (under, name))
                self.assertEqual(V.check_key_policy(
                    policies, name, self.CFG, {"kind": "exec"},
                    secrets=self.secrets),
                    "job kind 'exec' is not allowed for this key", (under, name))
                self.assertIsNone(V.check_key_policy(
                    policies, name, self.CFG, {"kind": "ping"},
                    secrets=self.secrets), (under, name))
            self.assertIsNone(V.policy_for(policies, self.secrets, "ops"))
        self.assertIs(V.policy_for({"ops": pol}, self.secrets, self.FO), pol)
        self.assertIsNone(V.policy_for("junk", self.secrets, "ops"))
        # Without the map, the check reads the name alone, as before.
        self.assertIsNone(V.check_key_policy({"": pol}, self.fp, self.CFG,
                                             {"kind": "exec"}))

    def test_the_deny_flag_never_touches_the_owner_under_any_name(self):
        cfg = dict(self.CFG, key_policies_default_deny=True)
        for name in ("", self.fp, "prod-1"):
            self.assertIsNone(V.check_key_policy({}, name, cfg, {"kind": "ping"},
                                                 secrets=self.secrets), name)
        for name in ("ops", self.FO, "nobody"):
            self.assertEqual(V.check_key_policy({}, name, cfg, {"kind": "ping"},
                                                secrets=self.secrets),
                             "no key policy entry for this key "
                             "(key_policies_default_deny)", name)

    def test_a_key_policed_under_two_of_its_names_is_a_config_error(self):
        pol = {"allowed_kinds": ["ping"]}
        for pair in (("", self.fp), ("", "prod-1"), (self.fp, "prod-1"),
                     ("ops", self.FO)):
            cfg = dict(self.CFG, key_policies={pair[0]: pol, pair[1]: pol})
            with self.assertRaisesRegex(RuntimeError,
                                        "names one key twice", msg=pair):
                V.build_key_policies(cfg)
        cfg = dict(self.CFG, key_policies={self.fp: pol, "ops": pol})
        # (the two pairs above are one key each; these are two keys)
        self.assertEqual(set(V.build_key_policies(cfg)), {self.fp, "ops"})
        # A config whose secrets do not build reports that elsewhere.
        self.assertEqual(V.build_key_policies({"key_policies": {"": pol,
                                                                "x": pol}}),
                         {"": pol, "x": pol})

    def test_the_owners_names_are_never_warned_as_unrestricted(self):
        self.assertEqual(V.unrestricted_extra_keys(self.CFG), ["ops"])
        cfg = dict(self.CFG, key_policies={"ops": {"allowed_kinds": ["ping"]}})
        self.assertEqual(V.unrestricted_extra_keys(cfg), [])

    def test_a_sensor_bound_to_a_key_takes_it_under_any_name(self):
        sensors = {"canary": {"enabled": True, "key_id": "ops"},
                   "door": {"enabled": True, "key_id": ""}}
        for name, want in (("ops", "canary"), (self.FO, "canary"),
                           ("", "door"), (self.fp, "door"), ("prod-1", "door"),
                           ("nobody", None)):
            bound = None
            for candidate in V.key_names(self.secrets, name):
                bound = R._senses.sensor_for_key(sensors, candidate)
                if bound is not None:
                    break
            self.assertEqual(bound, want, name)


    def test_one_secret_under_two_configured_names_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "under two key ids"):
            V.build_secrets({"shared_secret": SECRET,
                             "additional_secrets": {"ops": OTHER, "ops-too": OTHER}})

class RulesReadTheKeyNotTheNameTest(unittest.TestCase):
    """The wired rules, end to end: one hourly window for the default
    key under both names, and the answerer list naming the default
    key by either name."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-key-rules-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = {
            "mailbox_user": "runner@example.com",
            "mailbox_password": "test-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp, "workers": 1,
            "max_job_age_sec": 3600, "default_timeout_sec": 30,
            "oracle_opinion_mode": "off",
            "max_queries_per_hour": 1, "output_retention_days": 7,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")
        self.fp = security.key_fingerprint(SECRET)

    def _mail(self, subject, payload, ident, key_id):
        if key_id:
            payload = dict(payload, key_id=key_id)
        signed = send_job.sign_payload(payload, SECRET)
        body = jobcrypto.encrypt_body(signed, SECRET, job_id=ident,
                                      key_id=key_id, sign=send_job.sign_payload)
        msg = EmailMessage()
        msg["From"] = "si@example.com"
        msg["To"] = "runner@example.com"
        msg["Subject"] = subject
        msg.set_content(body)
        return msg.as_bytes()

    def _poll(self, mails, **cfg):
        smtp = FakeSMTP()
        R.poll_once(dict(self.cfg, **cfg), self.tmp, {}, self.seen_path,
                    imap=FakeIMAP(mails), smtp=smtp)
        return smtp

    def _open(self, msg):
        body = send_job.verify_body(msg.get_content(), SECRET)
        ident = str(msg["Subject"]).rsplit(" ", 1)[-1]
        if jobcrypto.is_envelope(body):
            body = send_job.verify_body(jobcrypto.decrypt_body(
                body, SECRET, ident, body.get("key_id") or ""), SECRET)
        return body

    def test_the_default_key_has_one_query_window_under_both_names(self):
        R.save_retained(self.tmp, "kw-job", {
            "stdout": "one\n", "stderr": "", "exit_code": 0, "budget": 8,
            "spent": 0, "view": "full", "saved_at": __import__("time").time()})
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        def query(qid):
            return {"v": 1, "type": "query", "query_id": qid, "job_id": "kw-job",
                    "issued_at": now, "queries": [{"op": "tail", "lines": 1}]}

        smtp = self._poll([
            self._mail("[HOMING-PIGEON] query kw-q1", query("kw-q1"), "kw-q1", ""),
            self._mail("[HOMING-PIGEON] query kw-q2", query("kw-q2"), "kw-q2",
                       self.fp)])
        self.assertEqual(len(smtp.sent), 2)
        first, second = (self._open(m) for m in smtp.sent)
        self.assertEqual(first.get("rejected"), None, first)
        self.assertEqual(second.get("rejected"), "rate_limit", second)
        with open(os.path.join(self.tmp, "query_times.json"),
                  encoding="utf-8") as fh:
            self.assertEqual(list(json.load(fh)), [""])
        # The reply is sealed under the name the query used.
        self.assertEqual(send_job.verify_body(
            smtp.sent[1].get_content(), SECRET)["key_id"], self.fp)

    def test_the_answerer_list_names_the_default_key_either_way(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec", "script": "echo ok"})
        ans = v2.answer_for(question, "proceed")
        stored = os.path.join(self.tmp, "v2", "answers", "q.j1.json")
        for listed, sent_as in ((self.fp, ""), ("", self.fp),
                                (self.fp, self.fp), ("", "")):
            if os.path.exists(stored):
                os.remove(stored)
            self._poll([self._mail("[HOMING-PIGEON] answer " + ans["msg_id"],
                                   ans, ans["msg_id"], sent_as)],
                       protocol_v2=True, v2_answerers=[listed])
            self.assertTrue(os.path.exists(stored), (listed, sent_as))
        os.remove(stored)
        self._poll([self._mail("[HOMING-PIGEON] answer " + ans["msg_id"],
                               ans, ans["msg_id"], self.fp)],
                   protocol_v2=True, v2_answerers=["someone-else"])
        self.assertFalse(os.path.exists(stored))


class SendJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-keyring-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ring = os.path.join(self.tmp, "ring", "keyring.json")

    def _run(self, argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["send_job.py"] + argv), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = send_job.main()
        return rc, out.getvalue(), err.getvalue()

    def _job_from(self, out):
        lines = out.splitlines()
        job_id = lines[0].rsplit(" ", 1)[1]
        body = "\n".join(lines[2:])
        job, key_id, _secret, _enc = R._admit_object(body, {"": SECRET}, job_id)
        return job, key_id, job_id, body

    def test_key_id_prints_the_name_of_a_bare_secret(self):
        rc, out, err = self._run(["key-id", "--secret", SECRET])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), security.key_fingerprint(SECRET))
        self.assertNotIn(SECRET, out + err)

    def test_the_keyring_keeps_the_pair_and_prints_only_names(self):
        rc, out, err = self._run(["keyring", "add", "--secret", SECRET,
                                  "--runner", "runner@example.com",
                                  "--keyring", self.ring])
        self.assertEqual(rc, 0, err)
        name = security.key_fingerprint(SECRET)
        self.assertEqual(out.strip(), name)
        mode = stat.S_IMODE(os.stat(self.ring).st_mode)
        if os.name != "nt":
            self.assertEqual(mode, 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(
                os.path.dirname(self.ring)).st_mode), 0o700)
        rc, out, err = self._run(["keyring", "add", "--secret", OTHER,
                                  "--key-id", "ops", "--keyring", self.ring])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), "ops")
        rc, out, err = self._run(["keyring", "list", "--keyring", self.ring])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.splitlines(), [f"{name}  runner@example.com", "ops"])
        self.assertNotIn(SECRET, out + err)
        self.assertNotIn(OTHER, out + err)
        with open(self.ring, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {
                name: {"secret": SECRET, "runner": "runner@example.com"},
                "ops": {"secret": OTHER}})
        rc, out, err = self._run(["keyring", "remove", "--key-id", "ops",
                                  "--keyring", self.ring])
        self.assertEqual(rc, 0, err)
        rc, out, _err = self._run(["keyring", "list", "--keyring", self.ring])
        self.assertEqual(out.splitlines(), [f"{name}  runner@example.com"])
        rc, _out, err = self._run(["keyring", "remove", "--key-id", "ops",
                                   "--keyring", self.ring])
        self.assertEqual(rc, 2)
        self.assertIn("holds no key id 'ops'", err)
        rc, _out, err = self._run(["keyring", "add", "--keyring", self.ring])
        self.assertEqual(rc, 2)
        self.assertIn("needs --secret", err)

    def test_the_keyring_is_found_by_flag_then_environment_then_home(self):
        self.assertEqual(send_job.keyring_path(mock.Mock(keyring="/x/r.json")),
                         "/x/r.json")
        with mock.patch.dict(os.environ, {"HP_KEYRING": "/env/r.json"}):
            self.assertEqual(send_job.keyring_path(mock.Mock(keyring=None)),
                             "/env/r.json")
            self.assertEqual(send_job.keyring_path(), "/env/r.json")
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("HP_KEYRING", None)
            self.assertTrue(send_job.keyring_path().endswith(
                os.path.join(".homing-pigeon", "keyring.json")))

    def test_a_keyring_that_does_not_read_is_named(self):
        os.makedirs(os.path.dirname(self.ring))
        with open(self.ring, "w", encoding="utf-8") as fh:
            fh.write('{"ops": "bare"}')
        with self.assertRaisesRegex(ValueError, "not a map of key ids"):
            send_job.keyring_load(self.ring)
        with open(self.ring, "w", encoding="utf-8") as fh:
            fh.write("{")
        with self.assertRaisesRegex(ValueError, "does not read"):
            send_job.keyring_load(self.ring)
        self.assertEqual(send_job.keyring_load(self.ring + ".absent"), {})

    def test_new_names_the_default_key_by_fingerprint(self):
        rc, out, err = self._run(["new", "--secret", SECRET, "--kind", "ping"])
        self.assertEqual(rc, 0, err)
        job, key_id, _jid, body = self._job_from(out)
        name = security.key_fingerprint(SECRET)
        self.assertEqual(key_id, name)
        self.assertEqual(job["key_id"], name)
        # The envelope names the key the same way as the body inside.
        envelope = json.loads(send_job._extract_signed(
            send_job.normalize(body).rstrip())[0])
        self.assertEqual(envelope["key_id"], name)

    def test_new_sends_the_unnamed_form_on_an_empty_key_id(self):
        rc, out, err = self._run(["new", "--secret", SECRET, "--kind", "ping",
                                  "--key-id", ""])
        self.assertEqual(rc, 0, err)
        job, key_id, _jid, body = self._job_from(out)
        self.assertEqual(key_id, "")
        self.assertNotIn("key_id", job)
        envelope = json.loads(send_job._extract_signed(
            send_job.normalize(body).rstrip())[0])
        self.assertEqual(envelope.get("key_id", ""), "")

    def test_new_signs_from_the_keyring_when_no_secret_is_given(self):
        self._run(["keyring", "add", "--secret", SECRET, "--keyring", self.ring])
        name = security.key_fingerprint(SECRET)
        rc, out, err = self._run(["new", "--kind", "ping", "--key-id", name,
                                  "--keyring", self.ring])
        self.assertEqual(rc, 0, err)
        job, key_id, _jid, _body = self._job_from(out)
        self.assertEqual((key_id, job["key_id"]), (name, name))
        self.assertNotIn(SECRET, out + err)
        rc, _out, err = self._run(["new", "--kind", "ping", "--key-id", "ops",
                                   "--keyring", self.ring])
        self.assertEqual(rc, 2)
        self.assertIn("holds no key id 'ops'", err)
        rc, _out, err = self._run(["new", "--kind", "ping", "--keyring", self.ring])
        self.assertEqual(rc, 2)
        self.assertIn("give --secret, or --key-id", err)

    def test_a_chosen_key_id_with_the_keyring_names_the_entry(self):
        self._run(["keyring", "add", "--secret", OTHER, "--key-id", "ops",
                   "--keyring", self.ring])
        rc, out, err = self._run(["new", "--kind", "ping", "--key-id", "ops",
                                  "--keyring", self.ring])
        self.assertEqual(rc, 0, err)
        lines = out.splitlines()
        job_id = lines[0].rsplit(" ", 1)[1]
        job, key_id, _s, _e = R._admit_object("\n".join(lines[2:]),
                                              {"": SECRET, "ops": OTHER}, job_id)
        self.assertEqual((key_id, job["key_id"]), ("ops", "ops"))

    def test_verify_looks_the_bodys_key_up_in_the_keyring(self):
        self._run(["keyring", "add", "--secret", SECRET, "--keyring", self.ring])
        name = security.key_fingerprint(SECRET)
        result = send_job.sign_payload(
            {"v": 1, "type": "result", "job_id": "k-r-0001", "key_id": name,
             "exit_code": 0, "stdout": "pong", "stderr": ""}, SECRET)
        rc, out, err = self._run(["verify", "--keyring", self.ring], stdin=result)
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out)["key_id"], name)
        # A body that names no key cannot be looked up.
        unnamed = send_job.sign_payload(
            {"v": 1, "type": "result", "job_id": "k-r-0002", "exit_code": 0,
             "stdout": "pong", "stderr": ""}, SECRET)
        rc, _out, err = self._run(["verify", "--keyring", self.ring],
                                  stdin=unnamed)
        self.assertEqual(rc, 1)
        self.assertIn("names no key_id", err)
        # --key-id picks the entry when the body names another or none.
        rc, out, err = self._run(["verify", "--keyring", self.ring,
                                  "--key-id", name], stdin=unnamed)
        self.assertEqual(rc, 0, err)
        # A key the keyring does not hold is said by name.
        other = send_job.sign_payload(
            {"v": 1, "type": "result", "job_id": "k-r-0003", "key_id": "ops",
             "exit_code": 0, "stdout": "", "stderr": ""}, OTHER)
        rc, _out, err = self._run(["verify", "--keyring", self.ring], stdin=other)
        self.assertEqual(rc, 1)
        self.assertIn("holds no key id 'ops'", err)
        # --secret still wins outright.
        rc, out, err = self._run(["verify", "--secret", OTHER], stdin=other)
        self.assertEqual(rc, 0, err)

    def test_the_board_messages_name_their_key_too(self):
        for argv in (["task-submit", "--task-id", "t-1", "--secret", SECRET],
                     ["task-request", "--worker-id", "w-1", "--secret", SECRET]):
            rc, out, err = self._run(argv)
            self.assertEqual(rc, 0, err)
            lines = out.splitlines()
            ident = lines[0].rsplit(" ", 1)[1]
            payload, key_id, _s, _e = R._admit_object(
                "\n".join(lines[2:]), {"": SECRET}, ident)
            name = security.key_fingerprint(SECRET)
            self.assertEqual((key_id, payload["key_id"]), (name, name), argv[0])


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-install-key-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = os.path.join(self.tmp, "config.json")
        with open(self.cfg, "w", encoding="utf-8") as fh:
            fh.write("{}\n")

    def _config(self):
        with open(self.cfg, encoding="utf-8") as fh:
            return json.load(fh)

    def _ensure(self, provided=None, key_id=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            inst.ensure_shared_secret(self.cfg, provided, key_id)
        return out.getvalue()

    def test_a_generated_secret_is_printed_with_its_name_as_a_pair(self):
        text = self._ensure()
        secret = self._config()["shared_secret"]
        name = inst.key_fingerprint(secret)
        self.assertIn(f"key id {name} -- give your cloud SI the pair", text)
        self.assertIn("the shared_secret value in config.json", text)
        self.assertNotIn(secret, text)
        self.assertNotIn("additional_secrets", self._config())

    def test_a_chosen_name_is_stored_beside_the_fingerprint(self):
        text = self._ensure(key_id="prod-1")
        cfg = self._config()
        secret = cfg["shared_secret"]
        self.assertEqual(cfg["additional_secrets"], {"prod-1": secret})
        self.assertIn(f"key id {inst.key_fingerprint(secret)} (and prod-1)", text)
        self.assertNotIn(secret, text)
        # The config the runner builds from this names the key twice
        # and both names are the one key.
        secrets = V.build_secrets(cfg)
        self.assertEqual(secrets["prod-1"], secrets[inst.key_fingerprint(secret)])
        self.assertEqual(secrets[""], secret)

    def test_a_provided_secret_is_named_the_same_way(self):
        text = self._ensure(provided=OTHER, key_id="edition-a")
        self.assertIn("wrote --shared-secret into config.json: key id "
                      f"{inst.key_fingerprint(OTHER)} (and edition-a)", text)
        self.assertEqual(self._config()["additional_secrets"],
                         {"edition-a": OTHER})

    def test_a_real_secret_already_set_is_named_not_replaced(self):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": SECRET}, fh)
        text = self._ensure(key_id="prod-1")
        self.assertEqual(self._config()["shared_secret"], SECRET)
        self.assertEqual(self._config()["additional_secrets"], {"prod-1": SECRET})
        self.assertIn(f"named {inst.key_fingerprint(SECRET)} (and prod-1)", text)
        self.assertNotIn(SECRET, text)
        # Naming it again is idempotent; a second name is added.
        self._ensure(key_id="prod-1")
        self._ensure(key_id="prod-2")
        self.assertEqual(self._config()["additional_secrets"],
                         {"prod-1": SECRET, "prod-2": SECRET})

    def test_a_bad_or_taken_name_is_refused(self):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": SECRET,
                       "additional_secrets": {"ops": OTHER}}, fh)
        for bad in ("", "has space", "x" * 65, "k/y"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), \
                    self.assertRaises(SystemExit) as cm:
                inst.ensure_shared_secret(self.cfg, None, bad or "no name")
            if bad:
                self.assertEqual(cm.exception.code, 2, bad)
                self.assertIn("--key-id must match", err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(
                io.StringIO()), self.assertRaises(SystemExit) as cm:
            inst.ensure_shared_secret(self.cfg, None, "ops")
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("already holds a different key under ops", err.getvalue())
        self.assertNotIn(OTHER, err.getvalue())
        self.assertEqual(self._config()["additional_secrets"], {"ops": OTHER})

    def test_a_fresh_install_hands_the_flag_to_the_secret_step(self):
        seen = {}

        class _Stop(Exception):
            """Ends the install right after the step under test."""

        def fake(cfg_path, provided, key_id=None):
            seen["args"] = (provided, key_id)
            raise _Stop()

        # A parsed argv carries the flag or not; a harness Mock's
        # attribute is not a name, and is passed as none.
        for args, expect in (
                (mock.Mock(config_json=None, shared_secret=None,
                           key_id="prod-1"), (None, "prod-1")),
                (mock.Mock(config_json=None, shared_secret=None,
                           key_id=None), (None, None)),
                (mock.Mock(config_json=None, shared_secret=None), (None, None))):
            with mock.patch.object(inst, "ensure_shared_secret", fake), \
                    self.assertRaises(_Stop):
                inst._setup_fresh_config(args, self.cfg)
            self.assertEqual(seen["args"], expect)


class NearMissNamesTest(unittest.TestCase):
    """Q96.3. A name that is almost a fingerprint is an unknown key.
    It does not select the default secret."""

    def test_a_near_miss_is_unknown_and_not_the_default(self):
        fp = security.key_fingerprint(SECRET)
        digits = fp[2:]
        misses = (
            "k-" + digits[:7],
            "k-" + digits + "a",
            "k-" + digits.upper(),
            "k-zzzzzzzz",
            security.key_fingerprint(OTHER),
        )
        for name in misses:
            body = send_job.sign_payload(
                {"v": 1, "type": "job", "job_id": "k-n-miss",
                 "kind": "ping", "key_id": name}, SECRET)
            with self.assertRaisesRegex(ValueError, "unknown key_id"):
                V.verify_body_keyed(body, {"": SECRET})
        for name in (fp, None):
            payload = {"v": 1, "type": "job", "job_id": "k-n-ok",
                       "kind": "ping"}
            if name:
                payload["key_id"] = name
            body = send_job.sign_payload(payload, SECRET)
            got, key_id = V.verify_body_keyed(body, {"": SECRET})
            self.assertEqual(got["kind"], "ping", name)
            self.assertEqual(key_id, name or "")


class NamesStayPublicTest(_MailTest):
    """Q96.5. The card and the doctor name keys. Neither prints a
    value, nor a slice of one longer than the fingerprint."""

    def _no_value(self, text, *values):
        for value in values:
            self.assertNotIn(value, text)
            self.assertNotIn(value[:16], text)

    def test_the_card_and_the_doctor_print_names_only(self):
        self.cfg["additional_secrets"] = {"ops": OTHER}
        result = self._send(TR.job_payload(str(uuid.uuid4())))
        text = json.dumps(result)
        self.assertIn(security.key_fingerprint(SECRET), text)
        self._no_value(text, SECRET, OTHER)
        with tempfile.TemporaryDirectory() as root:
            home = os.path.join(root, "home")
            bind = os.path.join(home, "bin")
            os.makedirs(bind)
            cfg = os.path.join(home, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                json.dump({"shared_secret": SECRET,
                           "additional_secrets": {"ops": OTHER}}, fh)
            with open(os.path.join(home, "install-receipt.json"), "w",
                      encoding="utf-8") as fh:
                fh.write('{"version": "3"}\n')
            out = io.StringIO()
            with mock.patch.object(inst, "collector_health_rows",
                                   return_value=[]), \
                    contextlib.redirect_stdout(out):
                inst.do_check(home, bind, cfg, os.path.join(home, "state"))
            doctor = out.getvalue()
        self.assertIn(security.key_fingerprint(SECRET), doctor)
        self.assertIn("ops", doctor)
        self._no_value(doctor, SECRET, OTHER)


if __name__ == "__main__":
    unittest.main()
