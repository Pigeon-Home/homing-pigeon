#!/usr/bin/env python3
"""The wrong-audience refusal record, on the transport path.

The rig battery's wrong-audience-refused step checks that a job
addressed to a different runner is refused AND that the refusal
is recorded: the runner log line, the guard audit entry, and the
auth-rejection event. On 2026-11-11 that step failed on six
consecutive heads while the sibling tampered-refused step
passed. First-hand measurement on the Germany rig (a controlled
segment run, same config shape as the battery) showed the
product behaviour is correct: serviced by the core, the
wrong-audience envelope is rejected with

    rejecting seq transport: security policy (audience):
        runner_id mismatch

in the log, an ``auth_rejection`` / ``security_policy`` /
``audience`` entry in security-events.jsonl, and a
``feature=audience, decision=denied, reason=runner_id_mismatch``
entry in security-audit.jsonl. The battery step raced the core's
service cycle: on the loaded rig one cycle takes ~15-17 seconds
(against under a second on an idle Linux control run), and the
driver read the files after a fixed 15-second sleep, before the
core had serviced the envelope at all -- the envelope was still
sitting in the channel inbox, unconsumed. The driver now waits
for the record instead of sleeping a fixed time.

These tests pin the product half of that contract at the exact
acceptance point the battery exercises (process_transport_message,
cleartext under --allow-cleartext, audience enforce), so the
record the battery waits for can never silently stop being
written:

- wrong audience (the ``aud`` form, and the ``runner_id`` form):
  no result, envelope consumed, job not in the seen set, and all
  three records written;
- correct audience: the job executes, a result is sent, and no
  audience denial appears in any record;
- tampered signature (the sibling step): recorded as
  bad_signature, with no audience record -- the two refusals stay
  distinguishable in the files a checker reads;
- the mail path (poll_once) writes the same three records for a
  wrong-audience job, so the contract is the channel's, not the
  transport's.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))
sys.path.insert(0, os.path.join(REPO, "runner", "tests"))

from runner import runner as runner_mod  # noqa: E402
from runner.runner import poll_once, process_transport_message  # noqa: E402
from runner.tests.security_parity import (  # noqa: E402
    SECRET,
    FakeIMAP,
    FakeSMTP,
    _email,
    _payload,
    base_config,
    read_audit_lines,
)
import send_job  # noqa: E402

RID = "hp-rig-test"
OTHER = "some-other-runner"


class AudienceRecordBase(unittest.TestCase):
    def setUp(self):
        # The battery runs the runner with --allow-cleartext and
        # sends cleartext envelopes; mirror that process state.
        runner_mod._set_allow_cleartext_jobs(True)
        self.addCleanup(runner_mod._set_allow_cleartext_jobs, False)
        self.tmp = tempfile.mkdtemp(prefix="hp-aud-rec-")
        self.cfg = base_config(self.tmp)
        self.cfg.update({
            "runner_id": RID,
            "security": {"modes": {"audience": "enforce"}},
        })
        self.logs = []
        logs = self.logs

        def fake_log(msg, level="INFO"):
            logs.append(str(msg))

        fake_log.identity_logged = True
        self.fake_log = fake_log

    def transport(self, payload, secret=None):
        body = send_job.sign_payload(
            payload, SECRET if secret is None else secret)
        return self.transport_body(payload["job_id"], body)

    def transport_body(self, jid, body):
        seen = {}
        with mock.patch.object(runner_mod, "log", self.fake_log):
            out = process_transport_message(
                self.cfg, self.tmp, seen, {"": SECRET}, {},
                f"[HOMING-PIGEON] job {jid}", body,
                transport="file")
        return out, seen

    def events(self):
        path = os.path.join(self.tmp, "security-events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def audit(self):
        return [json.loads(line)
                for line in (read_audit_lines(self.tmp) or [])
                if line.strip()]

    def audience_denials(self):
        return [e for e in self.audit()
                if e.get("feature") == "audience"
                and e.get("decision") == "denied"]

    def audience_events(self):
        return [e for e in self.events()
                if e.get("type") == "auth_rejection"
                and e.get("reason") == "security_policy"
                and e.get("feature") == "audience"]

    def log_has_audience_reject(self):
        return any("security policy (audience): runner_id mismatch"
                   in line for line in self.logs)


class WrongAudienceTransportRecordTest(AudienceRecordBase):
    def test_wrong_audience_refusal_writes_all_three_records(self):
        payload = _payload("wa-aud-01", kind="ping", aud=OTHER)
        out, seen = self.transport(payload)
        # No execution, no result; the envelope is consumed (the
        # core marked it) and the job is not in the seen set.
        self.assertEqual(list(out), [])
        self.assertTrue(out.consume)
        self.assertFalse(any(k.endswith("wa-aud-01") for k in seen))
        # Record 1: the runner log line.
        self.assertTrue(self.log_has_audience_reject())
        # Record 2: the guard audit entry.
        denials = self.audience_denials()
        self.assertEqual(len(denials), 1)
        self.assertEqual(denials[0]["reason"], "runner_id_mismatch")
        self.assertEqual(denials[0]["job_id"], "wa-aud-01")
        self.assertEqual(denials[0]["mode"], "enforce")
        # Record 3: the auth-rejection event.
        events = self.audience_events()
        self.assertEqual(len(events), 1)

    def test_wrong_runner_id_field_form_writes_all_three_records(self):
        payload = _payload("wa-rid-01", kind="ping", runner_id=OTHER)
        out, seen = self.transport(payload)
        self.assertEqual(list(out), [])
        self.assertTrue(out.consume)
        self.assertTrue(self.log_has_audience_reject())
        self.assertEqual(len(self.audience_denials()), 1)
        self.assertEqual(len(self.audience_events()), 1)

    def test_correct_audience_executes_with_no_denial_records(self):
        payload = _payload("wa-ok-01", kind="ping", aud=RID)
        out, seen = self.transport(payload)
        self.assertEqual(len(out), 1)
        # Seen keys are namespaced by runner_id (M5).
        self.assertIn(f"{RID}:wa-ok-01", seen)
        self.assertEqual(self.audience_denials(), [])
        self.assertEqual(self.audience_events(), [])
        self.assertFalse(self.log_has_audience_reject())

    def test_tampered_signature_records_bad_signature_not_audience(self):
        payload = _payload("wa-tp-01", kind="ping", aud=RID)
        body = send_job.sign_payload(payload, SECRET)
        forged = body[:-20] + "0000000000" + body[-10:]
        out, seen = self.transport_body("wa-tp-01", forged)
        self.assertEqual(list(out), [])
        self.assertTrue(any("bad signature" in line
                            for line in self.logs))
        bad = [e for e in self.events()
               if e.get("type") == "auth_rejection"
               and e.get("reason") == "bad_signature"]
        self.assertEqual(len(bad), 1)
        self.assertEqual(self.audience_denials(), [])
        self.assertEqual(self.audience_events(), [])
        self.assertFalse(self.log_has_audience_reject())


class WrongAudienceMailRecordTest(AudienceRecordBase):
    def test_wrong_audience_mail_writes_all_three_records(self):
        payload = _payload("wa-mail-01", kind="ping", aud=OTHER)
        mail = _email(payload, SECRET)
        imap, smtp = FakeIMAP([mail]), FakeSMTP()
        seen_path = os.path.join(self.tmp, "seen.json")
        with mock.patch.object(runner_mod, "log", self.fake_log):
            poll_once(self.cfg, self.tmp, {}, seen_path,
                      imap=imap, smtp=smtp)
        self.assertEqual(len(smtp.sent), 0)
        self.assertIn("1", imap.flagged)
        self.assertTrue(self.log_has_audience_reject())
        self.assertEqual(len(self.audience_denials()), 1)
        self.assertEqual(len(self.audience_events()), 1)


if __name__ == "__main__":
    unittest.main()
