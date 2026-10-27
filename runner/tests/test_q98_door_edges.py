#!/usr/bin/env python3
"""Q98 door edges (Muse, 2026-10-27): the shapes the
desk's own door pins do not cover.

Written against the unfixed code as nine expected-failure
pins for Q98 items 12, 13 and 15 (each verified to fail on
the behavior: the denied key's board submit applied and
acked, the seven-day-old submit likewise). The desk landed
the fixes and its own module, `runner/tests/test_q98_doors.py`,
in `146c558c4` before these pins reached main, so this module
keeps only the shapes that module does not pin:

- item 12: a board submit dated in the future, and a
  replayed submit applying once (the desk pins staleness,
  a missing issued_at, the type check, and request replay);
- item 13: the control -- the default key stays
  unrestricted under `key_policies_default_deny`
  (the desk pins the refusals);
- item 15: an additional secret answers to its
  fingerprint, and -- still open -- one secret under two
  names is refused, as item 15's recommendation words it
  ("refusing two secrets that share one"). The desk's fix
  registers the fingerprint once and keeps both names, so
  that test carries @unittest.expectedFailure until the
  desk rules on it; the Q98 reply in the landing commit
  names it.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.wire import jobcrypto
from runner.wire.verify import build_secrets
from runner.guard.security import key_fingerprint
from runner.runner import poll_once
from send_job import sign_payload
from runner.tests.test_runner import FakeIMAP, FakeSMTP

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
SECRET2 = "7a1f09c4d83b4e6aa05c19d27f34b68e01cd59284f76a3b90d15e6c2f48a09d3"
SENDER = "runner@example.com"


def _issued(days=0):
    when = datetime.now(timezone.utc) + timedelta(days=days)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, payload, secret=SECRET):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    signed = sign_payload(payload, secret)
    ident = subject.rsplit(" ", 1)[-1]
    key_id = payload.get("key_id") if isinstance(payload, dict) else ""
    wire = jobcrypto.encrypt_body(
        signed, secret, job_id=ident, key_id=key_id or "",
        sign=sign_payload)
    msg.set_content(wire)
    return msg.as_bytes()


def _submit(task_id, issued, secret=SECRET, key_id=None):
    payload = {
        "v": 1, "type": "task_submit", "task_id": task_id,
        "issued_at": issued, "priority": 3, "capabilities": ["py"],
        "payload": {"kind": "ping"},
    }
    if key_id:
        payload["key_id"] = key_id
    return _mail(f"[HOMING-PIGEON] task_submit {task_id}", payload, secret)


class _DoorCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q98e-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp,
            "workers": 1,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def run_mails(self, mails):
        smtp = FakeSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        return smtp

    def board_tasks(self):
        path = os.path.join(self.tmp, "board.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def acks(self, smtp, task_id):
        return [m["Subject"] for m in smtp.sent
                if f"task_ack {task_id}" in m["Subject"]]


class BoardFreshnessEdgesTest(_DoorCase):
    """Q98 item 12, the edges: the future bound and a
    replayed submit."""

    def test_future_board_submit_is_refused(self):
        smtp = self.run_mails([_submit("t-future", _issued(days=7))])
        self.assertNotIn("t-future", self.board_tasks())
        self.assertEqual(self.acks(smtp, "t-future"), [])

    def test_replayed_board_submit_applies_once(self):
        raw = _submit("t-replay", _issued())
        smtp = self.run_mails([raw, raw])
        self.assertEqual(len(self.acks(smtp, "t-replay")), 1)
        self.assertIn("t-replay", self.board_tasks())


class DefaultKeyControlTest(_DoorCase):
    """Q98 item 13, the control: build_key_policies documents
    the default key as always unrestricted; the shared door
    must not over-refuse it."""

    def test_default_key_stays_unrestricted_under_default_deny(self):
        self.cfg["additional_secrets"] = {"worker1": SECRET2}
        self.cfg["key_policies_default_deny"] = True
        smtp = self.run_mails([_submit("t-open", _issued())])
        self.assertIn("t-open", self.board_tasks())
        self.assertEqual(len(self.acks(smtp, "t-open")), 1)


class FingerprintNamesTest(unittest.TestCase):
    """Q98 item 15: every secret answers to its fingerprint
    name (PROTOCOL 14.2), and one fingerprint names one
    secret."""

    def test_an_additional_secret_answers_to_its_fingerprint(self):
        secrets = build_secrets({
            "shared_secret": SECRET,
            "additional_secrets": {"worker1": SECRET2},
        })
        self.assertEqual(secrets[key_fingerprint(SECRET2)], SECRET2)

    @unittest.expectedFailure  # Q98 item 15: two names, one secret, no refusal yet
    def test_one_secret_under_two_names_is_refused(self):
        with self.assertRaises(RuntimeError):
            build_secrets({
                "shared_secret": SECRET,
                "additional_secrets": {"a": SECRET2, "b": SECRET2},
            })


if __name__ == "__main__":
    unittest.main()
