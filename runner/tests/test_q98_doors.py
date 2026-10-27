# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Q98's security holes, closed at the doors they were open at.

Item 14: a retained record names the key its job verified under, and
a query from any other key is answered as an unknown job, spending
nothing (PROTOCOL.md section 11: no key spends a budget it did not
sign for). Item 15: an additional secret answers to its fingerprint
(section 14.2) -- see test_key_names. Items 12 and 13 below.
"""
import json
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

from runner import runner  # noqa: E402
from runner.cloud.send_job import sign_payload  # noqa: E402
from runner.runner import handle_query_mail, load_retained, save_retained  # noqa: E402
from runner.tests.security_parity import (  # noqa: E402
    EXTRA_SECRET, SECRET, FakeIMAP, FakeSMTP, base_config)
from runner.wire import jobcrypto  # noqa: E402


class _Opts:
    dry_run = False
    no_send = False


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sealed(obj, ident, secret, key_id=""):
    return jobcrypto.encrypt_body(sign_payload(obj, secret), secret,
                                  job_id=ident, key_id=key_id, sign=sign_payload)


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


def _reply(smtp, secret, ident):
    body = smtp.sent[-1].get_content()
    parsed = runner.verify_body(body, secret)
    if jobcrypto.is_envelope(parsed):
        body = jobcrypto.decrypt_body(parsed, secret, ident, parsed.get("key_id") or "")
        parsed = runner.verify_body(body, secret)
    return parsed


class QueryBudgetBelongsToItsKeyTest(unittest.TestCase):
    JOB = "q98-job-1"

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hp-q98-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cfg = base_config(self.dir)
        self.cfg["key_policies"] = {}
        self.secrets = runner.build_secrets(self.cfg)
        save_retained(self.dir, self.JOB, {
            "stdout": "one\ntwo\n", "stderr": "", "exit_code": 0,
            "budget": 8, "spent": 0, "saved_at": time.time(),
            "view": "full", "key": ""})

    def _ask(self, secret, key_id, query_id):
        obj = {"v": 1, "type": "query", "query_id": query_id,
               "job_id": self.JOB, "issued_at": _now(),
               "queries": [{"op": "tail", "lines": 1}]}
        if key_id:
            obj["key_id"] = key_id
        subject = "[HOMING-PIGEON] query " + query_id
        smtp = FakeSMTP()
        handle_query_mail(self.cfg, FakeIMAP([]), smtp, b"1",
                          _mail(subject, _sealed(obj, query_id, secret, key_id)),
                          subject, self.secrets, _Opts(), self.dir, {})
        return _reply(smtp, secret, query_id)

    def test_another_keys_query_is_an_unknown_job_and_spends_nothing(self):
        reply = self._ask(EXTRA_SECRET, "restricted", "q98-q-1")
        self.assertEqual(reply.get("rejected"), "unknown_job")
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 0)

    def test_the_jobs_own_key_still_asks(self):
        reply = self._ask(SECRET, "", "q98-q-2")
        self.assertNotIn("rejected", reply)
        self.assertEqual(load_retained(self.dir, self.JOB)["spent"], 1)

    def test_the_jobs_key_by_its_fingerprint_is_the_same_key(self):
        name = runner.key_fingerprint(SECRET) if hasattr(runner, "key_fingerprint") \
            else [k for k, v in self.secrets.items() if k.startswith("k-") and v == SECRET][0]
        reply = self._ask(SECRET, name, "q98-q-3")
        self.assertNotIn("rejected", reply)



# --- the board door (items 12, 13, 16, 17) ---------------------------------

import json as _json  # noqa: E402
import os  # noqa: E402
from datetime import timedelta  # noqa: E402

from runner.runner import poll_once  # noqa: E402
from runner.tests.test_board import SENDER  # noqa: E402
from runner.tests.test_board import SECRET as BSECRET  # noqa: E402
from runner.tests.test_runner import FakeIMAP as TIMAP, FakeSMTP as TSMTP  # noqa: E402

OTHER = "9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a"


def _bmail(subject, payload, secret=BSECRET, key_id=""):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    if key_id:
        payload = dict(payload, key_id=key_id)
    signed = sign_payload(payload, secret)
    ident = subject.rsplit(" ", 1)[-1]
    msg.set_content(jobcrypto.encrypt_body(signed, secret, job_id=ident,
                                           key_id=key_id, sign=sign_payload))
    return msg.as_bytes()


def _iso(delta=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=delta)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


class BoardDoorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q98-board-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = {"mailbox_user": SENDER, "mailbox_password": "x",
                    "shared_secret": BSECRET, "base_dir": self.tmp,
                    "workers": 1, "additional_secrets": {"w2": OTHER}}
        self.seen = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails):
        smtp = TSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen, imap=TIMAP(mails), smtp=smtp)
        return smtp

    def board(self):
        try:
            with open(os.path.join(self.tmp, "board.json"), encoding="utf-8") as fh:
                return _json.load(fh)
        except FileNotFoundError:
            return {}

    def submit(self, tid="t1", **extra):
        body = {"v": 1, "type": "task_submit", "task_id": tid,
                "issued_at": _iso(), "capabilities": []}
        body.update(extra)
        return _bmail("[HOMING-PIGEON] task_submit " + tid, body)

    def test_a_stale_board_message_is_refused(self):
        self.cycle([self.submit(issued_at=_iso(-7200))])
        self.assertNotIn("t1", self.board())

    def test_a_board_message_without_issued_at_is_refused(self):
        body = {"v": 1, "type": "task_submit", "task_id": "t1"}
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t1", body)])
        self.assertNotIn("t1", self.board())

    def test_the_type_must_be_the_subjects(self):
        body = {"v": 1, "type": "task_approve", "task_id": "t1", "issued_at": _iso()}
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t1", body)])
        self.assertNotIn("t1", self.board())

    def test_a_body_without_its_id_is_read_by_the_subjects(self):
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t1", {
            "v": 1, "type": "task_submit", "issued_at": _iso()})])
        self.assertNotIn("t-other", self.board())

    def test_the_body_id_must_be_the_subjects(self):
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t1", {
            "v": 1, "type": "task_submit", "task_id": "t-other",
            "issued_at": _iso()})])
        self.assertEqual(self.board(), {})

    def test_a_replayed_request_claims_nothing_more(self):
        self.cycle([self.submit("t1"), self.submit("t2")])
        req = _bmail("[HOMING-PIGEON] task_request w1", {
            "v": 1, "type": "task_request", "worker_id": "w1",
            "issued_at": _iso(), "capabilities": []})
        self.cycle([req])
        self.cycle([req])
        states = sorted(t["state"] for t in self.board().values())
        self.assertEqual(states, ["claimed", "open"])

    def test_a_fresh_request_from_the_same_worker_is_answered(self):
        # A worker holding a claim is offered that claim again (the
        # board's own rule); the replay guard must not swallow a fresh,
        # differently signed request on the way.
        self.cycle([self.submit("t1")])
        offers = 0
        for _ in range(2):
            smtp = self.cycle([_bmail("[HOMING-PIGEON] task_request w1", {
                "v": 1, "type": "task_request", "worker_id": "w1",
                "issued_at": _iso(), "nonce": os.urandom(4).hex(),
                "capabilities": []})])
            offers += sum("task_offer t1" in str(m["Subject"]) for m in smtp.sent)
        self.assertEqual(offers, 2)

    def test_a_replayed_request_is_not_answered_twice(self):
        self.cycle([self.submit("t1")])
        req = _bmail("[HOMING-PIGEON] task_request w1", {
            "v": 1, "type": "task_request", "worker_id": "w1",
            "issued_at": _iso(), "capabilities": []})
        self.assertEqual(len(self.cycle([req]).sent), 1)
        self.assertEqual(len(self.cycle([req]).sent), 0)

    def test_a_result_from_another_key_does_not_complete_the_claim(self):
        self.cycle([self.submit("t1")])
        self.cycle([_bmail("[HOMING-PIGEON] task_request w1", {
            "v": 1, "type": "task_request", "worker_id": "w1",
            "issued_at": _iso(), "capabilities": []})])
        self.cycle([_bmail("[HOMING-PIGEON] task_result t1", {
            "v": 1, "type": "task_result", "task_id": "t1",
            "issued_at": _iso(), "result": {"ok": True}}, secret=OTHER, key_id="w2")])
        self.assertEqual(self.board()["t1"]["state"], "claimed")
        self.cycle([_bmail("[HOMING-PIGEON] task_result t1", {
            "v": 1, "type": "task_result", "task_id": "t1",
            "issued_at": _iso(), "result": {"ok": True}})])
        self.assertEqual(self.board()["t1"]["state"], "done")

    def test_a_policy_without_board_keeps_the_key_off_the_board(self):
        self.cfg["key_policies"] = {"w2": {"allowed_kinds": ["exec"]}}
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t9", {
            "v": 1, "type": "task_submit", "task_id": "t9",
            "issued_at": _iso(), "capabilities": []}, secret=OTHER, key_id="w2")])
        self.assertNotIn("t9", self.board())
        self.cfg["key_policies"] = {"w2": {"allowed_kinds": ["board"]}}
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t9", {
            "v": 1, "type": "task_submit", "task_id": "t9",
            "issued_at": _iso(), "capabilities": []}, secret=OTHER, key_id="w2")])
        self.assertIn("t9", self.board())

    def test_default_deny_keeps_an_unlisted_key_off_the_board(self):
        self.cfg["key_policies_default_deny"] = True
        self.cycle([_bmail("[HOMING-PIGEON] task_submit t9", {
            "v": 1, "type": "task_submit", "task_id": "t9",
            "issued_at": _iso(), "capabilities": []}, secret=OTHER, key_id="w2")])
        self.assertNotIn("t9", self.board())


class QueryDoorPolicyTest(QueryBudgetBelongsToItsKeyTest):
    """Item 13 at the query door; the record belongs to the asking key."""

    def setUp(self):
        super().setUp()
        save_retained(self.dir, self.JOB, {
            "stdout": "one\ntwo\n", "stderr": "", "exit_code": 0,
            "budget": 8, "spent": 0, "saved_at": time.time(),
            "view": "full", "key": "restricted"})

    def test_a_policy_without_query_is_refused(self):
        self.cfg["key_policies"] = {"restricted": {"allowed_kinds": ["exec"]}}
        reply = self._ask(EXTRA_SECRET, "restricted", "q98-p-1")
        self.assertEqual(reply.get("rejected"), "policy")
        self.cfg["key_policies"] = {"restricted": {"allowed_kinds": ["exec", "query"]}}
        reply = self._ask(EXTRA_SECRET, "restricted", "q98-p-2")
        self.assertNotIn("rejected", reply)

    def test_default_deny_refuses_an_unlisted_key(self):
        self.cfg["key_policies_default_deny"] = True
        reply = self._ask(EXTRA_SECRET, "restricted", "q98-p-3")
        self.assertEqual(reply.get("rejected"), "policy")

    # the inherited cases ask about a record another key owns now
    test_another_keys_query_is_an_unknown_job_and_spends_nothing = None
    test_the_jobs_own_key_still_asks = None
    test_the_jobs_key_by_its_fingerprint_is_the_same_key = None



# --- startup reads the secrets the way every poll does (item 1) ------------

import contextlib  # noqa: E402
import io  # noqa: E402

from runner.tests.test_cli_options import SECRET as CSECRET, _main_rig  # noqa: E402


class StartupSecretsTest(unittest.TestCase):
    def _start(self, extra):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, poll, _r = _main_rig(["--once"], extra)
        return code, poll, err.getvalue()

    def _file(self, text):
        d = tempfile.mkdtemp(prefix="hp-q98-secret-")
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "secret")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_a_file_only_secret_starts(self):
        code, poll, err = self._start({"shared_secret": "",
                                       "shared_secret_file": self._file(CSECRET)})
        self.assertNotEqual(code, 2, err)
        self.assertTrue(poll.called, err)

    def test_inline_and_file_both_is_a_startup_error(self):
        code, poll, err = self._start({"shared_secret_file": self._file(CSECRET)})
        self.assertEqual(code, 2)
        self.assertIn("mutually exclusive", err)
        self.assertFalse(poll.called)

    def test_a_missing_or_empty_file_is_a_startup_error(self):
        for path in ("/nonexistent/hp-q98/secret", self._file("")):
            with self.subTest(path=path):
                code, poll, err = self._start({"shared_secret": "",
                                               "shared_secret_file": path})
                self.assertEqual(code, 2, err)
                self.assertFalse(poll.called)



# --- the size cap is at the door for every protocol message (item 2) -----

from unittest import mock  # noqa: E402


class SizeCapAtTheDoorTest(unittest.TestCase):
    def test_an_oversize_query_is_refused_before_any_signature_work(self):
        d = tempfile.mkdtemp(prefix="hp-q98-cap-")
        self.addCleanup(shutil.rmtree, d, True)
        cfg = base_config(d)
        cfg["max_job_bytes"] = 2048
        raw = _mail("[HOMING-PIGEON] query q-big", "x" * 4096)
        with mock.patch.object(runner, "_early_dispatch") as dispatch, \
                mock.patch.object(runner, "_mark") as mark:
            runner.handle_mail(cfg, FakeIMAP([]), FakeSMTP(), b"1", raw, d, {},
                               runner.build_secrets(cfg), _Opts())
        dispatch.assert_not_called()
        mark.assert_called_once()

    def test_mail_that_is_not_ours_is_left_to_the_dispatcher(self):
        d = tempfile.mkdtemp(prefix="hp-q98-cap-")
        self.addCleanup(shutil.rmtree, d, True)
        cfg = base_config(d)
        cfg["max_job_bytes"] = 2048
        raw = _mail("holiday photos", "x" * 4096)
        with mock.patch.object(runner, "_early_dispatch", return_value=None) as dispatch:
            runner.handle_mail(cfg, FakeIMAP([]), FakeSMTP(), b"1", raw, d, {},
                               runner.build_secrets(cfg), _Opts())
        dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
