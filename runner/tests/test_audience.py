#!/usr/bin/env python3
"""M5 tests: audience binding (runner_id).

UID (phase 2.3): audience binding names WHICH runner a job
is for, not who it runs as; jobs here run as the same uid
as the runner on both sides. The off / audit / enforce mode
tests are each other's negative controls (phase 2.2): the
wrong-runner job runs with the protection off and is
rejected with it enforced.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "tests"))

from runner.runner import poll_once  # noqa: E402
from runner.tests.security_parity import (  # noqa: E402
    SECRET,
    FakeIMAP,
    FakeSMTP,
    _email,
    _payload,
    base_config,
    build_corpus,
    normalize,
    read_audit_lines,
    run_variant,
)

RID = "runner-aaa-111"


def run_job(cfg_extra, payload, secret=SECRET):
    tmpdir = tempfile.mkdtemp(prefix="hp-m5-")
    cfg = base_config(tmpdir)
    cfg.update(cfg_extra)
    mail = _email(payload, secret)
    imap = FakeIMAP([mail])
    smtp = FakeSMTP()
    seen_path = os.path.join(tmpdir, "seen.json")
    poll_once(cfg, tmpdir, {}, seen_path, imap=imap, smtp=smtp)
    jid = payload["job_id"]
    executed = any(jid in (m["Subject"] or "") for m in smtp.sent)
    audit = []
    for line in read_audit_lines(tmpdir) or []:
        audit.append(json.loads(line))
    seen = {}
    try:
        seen = json.load(open(seen_path))
    except (OSError, ValueError):
        pass
    return executed, audit, seen, tmpdir


def aud_cfg(mode, runner_id=RID):
    cfg = {"runner_id": runner_id}
    if mode is not None:
        cfg["security"] = {"modes": {"audience": mode}}
    return cfg


class AudienceModesTest(unittest.TestCase):
    def _job(self, jid, runner_id="MISSING"):
        kw = {} if runner_id == "MISSING" else {"runner_id": runner_id}
        return _payload(jid, kind="ping", **kw)

    def test_off_missing_runner_id_runs(self):
        executed, audit, _, _ = run_job(
            aud_cfg("off"), self._job("a-off-01"))
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_off_wrong_runner_id_runs(self):
        executed, audit, _, _ = run_job(
            aud_cfg("off"), self._job("a-off-02", runner_id="other"))
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_audit_wrong_runner_id_runs_and_logs(self):
        executed, audit, _, _ = run_job(
            aud_cfg("audit"), self._job("a-audit-01", runner_id="other"))
        self.assertTrue(executed)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["decision"], "would_deny")
        self.assertEqual(audit[0]["feature"], "audience")
        self.assertEqual(audit[0]["reason"], "runner_id_mismatch")

    def test_enforce_correct_runner_id_runs(self):
        executed, audit, _, _ = run_job(
            aud_cfg("enforce"), self._job("a-enf-01", runner_id=RID))
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_enforce_aud_field_accepted(self):
        # Plan M5: the signed audience field is `aud`.
        payload = _payload("a-enf-aud", kind="ping")
        payload["aud"] = RID
        executed, audit, _, _ = run_job(aud_cfg("enforce"), payload)
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_enforce_aud_wrong_rejected(self):
        payload = _payload("a-enf-aud2", kind="ping")
        payload["aud"] = "other"
        executed, audit, _, _ = run_job(aud_cfg("enforce"), payload)
        self.assertFalse(executed)
        self.assertEqual(audit[0]["reason"], "runner_id_mismatch")

    def test_enforce_aud_wins_over_runner_id(self):
        # When both are present, `aud` decides.
        payload = _payload("a-enf-aud3", kind="ping", runner_id="other")
        payload["aud"] = RID
        executed, audit, _, _ = run_job(aud_cfg("enforce"), payload)
        self.assertTrue(executed)
        self.assertEqual(audit, [])

    def test_enforce_missing_runner_id_rejected(self):
        executed, audit, _, _ = run_job(
            aud_cfg("enforce"), self._job("a-enf-02"))
        self.assertFalse(executed)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["decision"], "denied")

    def test_enforce_wrong_runner_id_rejected(self):
        executed, audit, _, _ = run_job(
            aud_cfg("enforce"),
            self._job("a-enf-03", runner_id="runner-bbb-222"))
        self.assertFalse(executed)
        self.assertEqual(audit[0]["decision"], "denied")

    def test_no_runner_id_configured_skips_check(self):
        # Feature on but nothing to bind to: no finding, no crash.
        cfg = {"security": {"modes": {"audience": "enforce"}}}
        executed, audit, _, _ = run_job(cfg, self._job("a-nc-01"))
        self.assertTrue(executed)
        self.assertEqual(audit, [])


class CrossRunnerTest(unittest.TestCase):
    """A job signed for runner A is rejected by runner B in enforce."""

    def test_cross_runner_rejected(self):
        job = _payload("x-01", kind="ping", runner_id=RID)
        executed_a, _, _, _ = run_job(aud_cfg("enforce", RID), job)
        self.assertTrue(executed_a)
        executed_b, audit_b, _, _ = run_job(
            aud_cfg("enforce", "runner-bbb-222"), job)
        self.assertFalse(executed_b)
        self.assertEqual(audit_b[0]["reason"], "runner_id_mismatch")


class SeenNamespacingTest(unittest.TestCase):
    def test_seen_key_namespaced(self):
        _, _, seen, _ = run_job(
            aud_cfg("enforce"), _payload("s-01", kind="ping",
                                         runner_id=RID))
        self.assertIn("%s:%s" % (RID, "s-01"), seen)
        self.assertNotIn("s-01", seen)

    def test_no_namespace_without_runner_id(self):
        _, _, seen, _ = run_job({}, _payload("s-02", kind="ping"))
        self.assertIn("s-02", seen)

    def test_replay_suppressed_with_runner_id(self):
        tmpdir = tempfile.mkdtemp(prefix="hp-m5r-")
        cfg = base_config(tmpdir)
        cfg.update(aud_cfg("enforce"))
        payload = _payload("s-03", kind="ping", runner_id=RID)
        mail = _email(payload)
        seen_path = os.path.join(tmpdir, "seen.json")
        seen = {}
        imap = FakeIMAP([mail])
        smtp = FakeSMTP()
        poll_once(cfg, tmpdir, seen, seen_path, imap=imap, smtp=smtp)
        first = len(smtp.sent)
        # Same job again: suppressed by the namespaced seen key.
        imap2 = FakeIMAP([mail])
        smtp2 = FakeSMTP()
        poll_once(cfg, tmpdir, seen, seen_path, imap=imap2, smtp=smtp2)
        self.assertEqual(first, 1)
        self.assertEqual(len(smtp2.sent), 0)


class QueryAudienceTest(unittest.TestCase):
    def _query_mail(self, qid, runner_id="MISSING"):
        from datetime import datetime, timezone
        from email.message import EmailMessage
        from runner.wire import jobcrypto
        from runner.tests.security_parity import SENDER, sign_payload
        p = {"v": 1, "type": "query", "query_id": qid,
             "issued_at": datetime.now(timezone.utc).strftime(
                 "%Y-%m-%dT%H:%M:%SZ"),
             "queries": [{"op": "ask", "question": "hi",
                          "view": "summary"}]}
        if runner_id != "MISSING":
            p["runner_id"] = runner_id
        signed = sign_payload(p, SECRET)
        wire = jobcrypto.encrypt_body(
            signed, SECRET, job_id=qid, key_id="", sign=sign_payload)
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = "[HOMING-PIGEON] query %s" % qid
        msg.set_content(wire)
        return msg.as_bytes()

    def _run_query(self, cfg_extra, raw):
        tmpdir = tempfile.mkdtemp(prefix="hp-m5q-")
        cfg = base_config(tmpdir)
        cfg.update(cfg_extra)
        imap = FakeIMAP([raw])
        smtp = FakeSMTP()
        poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
                  imap=imap, smtp=smtp)
        answered = any("qresult" in (m["Subject"] or "") for m in smtp.sent)
        audit = []
        for line in read_audit_lines(tmpdir) or []:
            audit.append(json.loads(line))
        return answered, audit

    def test_query_with_a_broken_envelope_is_handled(self):
        # Queue A refill: handle_query_mail's bad-envelope
        # leg (coverage run 40189711740: lines
        # 4193-4195). A query whose envelope verifies but
        # cannot be decrypted (here the ciphertext is not
        # even base64) is logged, marked seen, and handled
        # -- never answered, never retried forever, never
        # a crash in the poll.
        from runner.tests.security_parity import sign_payload
        raw = self._query_mail("q-bad")
        import email as _email
        msg = _email.message_from_bytes(raw)
        wire = json.loads(msg.get_payload(decode=True).decode())
        wire["hp_enc"]["ct"] = "!!!not-base64!!!"
        body = sign_payload(wire, SECRET)
        from email.message import EmailMessage
        from runner.tests.security_parity import SENDER
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = "[HOMING-PIGEON] query q-bad"
        msg.set_content(body)
        tmpdir = tempfile.mkdtemp(prefix="hp-m5q-")
        cfg = base_config(tmpdir)
        imap = FakeIMAP([msg.as_bytes()])
        smtp = FakeSMTP()
        poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
                  imap=imap, smtp=smtp)
        self.assertEqual(len(imap.flagged), 1)
        self.assertFalse(any("qresult" in (m["Subject"] or "")
                             for m in smtp.sent))

    def test_query_wrong_audience_enforce_rejected(self):
        answered, audit = self._run_query(
            aud_cfg("enforce"), self._query_mail("q-01", runner_id="other"))
        self.assertFalse(answered)
        self.assertEqual(audit[0]["reason"], "runner_id_mismatch")

    def test_query_correct_audience_enforce_answered(self):
        answered, audit = self._run_query(
            aud_cfg("enforce"), self._query_mail("q-02", runner_id=RID))
        self.assertTrue(answered)
        self.assertEqual(audit, [])


class BoardAudienceTest(unittest.TestCase):
    def _board(self, subject, payload):
        from email.message import EmailMessage
        from runner.wire import jobcrypto
        from runner.tests.security_parity import SENDER, sign_payload
        signed = sign_payload(payload, SECRET)
        ident = subject.rsplit(" ", 1)[-1]
        key_id = payload.get("key_id") if isinstance(payload, dict) else ""
        wire = jobcrypto.encrypt_body(
            signed, SECRET, job_id=ident, key_id=key_id or "",
            sign=sign_payload)
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = subject
        msg.set_content(wire)
        return msg.as_bytes()

    def _run(self, cfg_extra, raw):
        tmpdir = tempfile.mkdtemp(prefix="hp-m5b-")
        cfg = base_config(tmpdir)
        cfg.update(cfg_extra)
        imap = FakeIMAP([raw])
        smtp = FakeSMTP()
        poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
                  imap=imap, smtp=smtp)
        acked = any("task_ack" in (m["Subject"] or "")
                    for m in smtp.sent)
        audit = []
        for line in read_audit_lines(tmpdir) or []:
            audit.append(json.loads(line))
        return acked, audit

    def _payload(self, runner_id="MISSING"):
        from datetime import datetime, timezone
        p = {"v": 1, "type": "task_submit", "task_id": "t-aud",
             "issued_at": datetime.now(timezone.utc).strftime(
                 "%Y-%m-%dT%H:%M:%SZ"),
             "priority": 3, "capabilities": ["py"],
             "payload": {"kind": "ping"}}
        if runner_id != "MISSING":
            p["runner_id"] = runner_id
        return p

    def test_board_wrong_audience_enforce_rejected(self):
        acked, audit = self._run(
            aud_cfg("enforce"),
            self._board("[HOMING-PIGEON] task_submit t-aud",
                        self._payload(runner_id="other")))
        self.assertFalse(acked)
        self.assertEqual(audit[0]["reason"], "runner_id_mismatch")

    def test_board_correct_audience_enforce_accepted(self):
        acked, audit = self._run(
            aud_cfg("enforce"),
            self._board("[HOMING-PIGEON] task_submit t-aud",
                        self._payload(runner_id=RID)))
        self.assertTrue(acked)
        self.assertEqual(audit, [])


class ParityWithRunnerIdTest(unittest.TestCase):
    """Corpus jobs carry no runner_id; with the feature off and a
    runner_id configured, outcomes must match the no-block baseline."""

    def test_off_with_runner_id_matches_baseline(self):
        corpus = build_corpus()
        base = run_variant(None, corpus)

        # Same as run_variant but with a runner_id in cfg.
        tmpdir = tempfile.mkdtemp(prefix="hp-parity-")
        cfg = base_config(tmpdir)
        cfg["runner_id"] = RID
        cfg["security"] = {"modes": {"audience": "off"}}
        mails = [raw for _, raw in corpus]
        imap = FakeIMAP(mails)
        smtp = FakeSMTP()
        seen_path = os.path.join(tmpdir, "seen.json")
        poll_once(cfg, tmpdir, {}, seen_path, imap=imap, smtp=smtp)
        sent = [(m["Subject"], normalize(
            m.get_content(), tmpdir,
            job_id=str(m["Subject"]).rsplit(" ", 1)[-1]))
            for m in smtp.sent]
        flagged = list(imap.flagged)
        seen = json.load(open(seen_path))
        off = {"sent": sent, "flagged": flagged, "seen": seen}

        self.assertEqual(base["sent"], off["sent"])
        self.assertEqual(base["flagged"], off["flagged"])
        # Seen keys are namespaced by runner_id (M5); the underlying
        # job ids must match.
        self.assertEqual(
            sorted(base["seen"]),
            sorted(k.split(":", 1)[1] for k in off["seen"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
