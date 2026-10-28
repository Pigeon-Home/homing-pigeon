# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""A signed cancel for a job (PROTOCOL.md section 3.4).

`[HOMING-PIGEON] cancel <job_id>`, signed by the key that signed the
job, kills the job when it is running here, is kept when the job has
not arrived yet (so the job is refused without running when it
does), and changes nothing when the job is done. Another key's
cancel is answered as if the job had not been seen and touches
nothing. The sender hears which in a signed cancel_ack.
"""
import io
import shutil
import sys
import threading
import time
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from email.message import EmailMessage
from unittest import mock

from runner import runner as R  # noqa: E402
from runner.cloud import send_job as SJ  # noqa: E402
from runner.ops import cancel as C  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: no re-collection)

OPS = "3b7d1f9a5c2e8046d9a3f1c7b5e2096a8d4c0f6b2e9a7c3d1f5b8e0a6c4d2f91"


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cancel_mail(job_id, secret=TR.SECRET, key_id="", over=None, **extra):
    obj = {"v": 1, "type": "cancel", "job_id": job_id, "issued_at": _now()}
    if key_id:
        obj["key_id"] = key_id
    obj.update(extra)
    obj.update(over or {})
    msg = EmailMessage()
    msg["From"] = TR.SENDER
    msg["To"] = TR.SENDER
    msg["Subject"] = f"[HOMING-PIGEON] cancel {job_id}"
    msg.set_content(jobcrypto.encrypt_body(
        R.sign_payload(obj, secret), secret, job_id=job_id, key_id=key_id,
        sign=R.sign_payload))
    return msg.as_bytes()


def ack_of(smtp, secret=TR.SECRET):
    msg = [m for m in smtp.sent if "cancelled" in m["Subject"]][-1]
    body = msg.get_content()
    outer = R.verify_body(body, secret)
    inner = jobcrypto.decrypt_body(outer, secret, msg["Subject"].split()[-1],
                                   outer.get("key_id") or "")
    return R.verify_body(inner, secret)


class _Rig(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.cfg["additional_secrets"] = {"ops": OPS}

    def tearDown(self):
        shutil.rmtree(self.h.tmp, ignore_errors=True)

    def cycle(self, *mails):
        return self.h.run_cycle(list(mails))[1]

    def slow(self, jid, **kw):
        return TR.job_payload(jid, kind="exec", interpreter=[sys.executable],
                              script="import time; time.sleep(30)", **kw)


class BeforeItArrivesTest(_Rig):
    def test_a_cancelled_job_is_refused_when_it_arrives(self):
        jid = str(uuid.uuid4())
        self.assertEqual(ack_of(self.cycle(cancel_mail(jid)))["status"], "will_refuse")
        smtp = self.cycle(TR.job_email(self.slow(jid)))
        r = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("cancelled by its sender", r["stderr"])

    def test_another_keys_cancel_leaves_the_job_alone(self):
        jid = str(uuid.uuid4())
        ack = ack_of(self.cycle(cancel_mail(jid, OPS, "ops")), OPS)
        self.assertEqual(ack["status"], "will_refuse")
        smtp = self.cycle(TR.job_email(TR.job_payload(jid)))
        r = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(r["stdout"], "pong")

    def test_a_finished_job_is_left_as_it_is(self):
        jid = str(uuid.uuid4())
        imap = TR.FakeIMAP([TR.job_email(TR.job_payload(jid))])
        smtp = TR.FakeSMTP()
        seen = {}
        R.poll_once(self.cfg, self.h.tmp, seen, self.h.seen_path, imap=imap, smtp=smtp)
        imap2, smtp2 = TR.FakeIMAP([cancel_mail(jid)]), TR.FakeSMTP()
        R.poll_once(self.cfg, self.h.tmp, seen, self.h.seen_path, imap=imap2, smtp=smtp2)
        self.assertEqual(ack_of(smtp2)["status"], "finished")

    def test_a_replayed_cancel_is_dropped(self):
        jid = str(uuid.uuid4())
        raw = cancel_mail(jid)
        imap = TR.FakeIMAP([raw])
        smtp = TR.FakeSMTP()
        seen = {}
        R.poll_once(self.cfg, self.h.tmp, seen, self.h.seen_path, imap=imap, smtp=smtp)
        R.poll_once(self.cfg, self.h.tmp, seen, self.h.seen_path,
                    imap=TR.FakeIMAP([raw]), smtp=smtp)
        self.assertEqual(len([m for m in smtp.sent if "cancelled" in m["Subject"]]), 1)


class RefusalsTest(_Rig):
    def acks(self, raw):
        return [m for m in self.cycle(raw).sent if "cancelled" in m["Subject"]]

    def test_what_is_not_a_cancel_for_this_job_gets_no_ack(self):
        jid = str(uuid.uuid4())
        for raw in (cancel_mail(jid, type="query"),
                    cancel_mail(jid, over={"job_id": "other-job"}),
                    cancel_mail(jid, issued_at="2020-01-01T00:00:00Z"),
                    cancel_mail(jid, v=9),
                    cancel_mail(jid, secret="f" * 64)):
            with self.subTest(raw=raw[-60:]):
                self.assertEqual(self.acks(raw), [])

    def test_the_deny_flag_holds_at_the_door(self):
        self.cfg["key_policies_default_deny"] = True
        self.assertEqual(self.acks(cancel_mail(str(uuid.uuid4()), OPS, "ops")), [])

    def test_a_subject_that_is_not_a_job_id_is_dropped(self):
        imap = mock.Mock()
        self.assertTrue(C.handle_cancel_mail(
            self.cfg, imap, None, b"1", b"", "[HOMING-PIGEON] cancel ..",
            R.build_secrets(self.cfg), None, self.h.tmp, {}))
        self.assertFalse(C.handle_cancel_mail(
            self.cfg, imap, None, b"1", b"", "[HOMING-PIGEON] job x",
            {}, None, self.h.tmp, {}))


class WhileItRunsTest(_Rig):
    def test_a_running_job_is_killed_and_says_so(self):
        jid = str(uuid.uuid4())
        job = self.slow(jid)
        box = {}
        t = threading.Thread(target=lambda: box.update(r=R.execute_job(self.cfg, job, self.h.tmp)))
        t.start()
        deadline = time.monotonic() + 10
        while jid not in C._RUNNING and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn(jid, C._RUNNING)
        # another key cannot see or stop it
        self.assertEqual(ack_of(self.cycle(cancel_mail(jid, OPS, "ops")), OPS)["status"],
                         "will_refuse")
        self.assertTrue(t.is_alive())
        self.assertEqual(ack_of(self.cycle(cancel_mail(jid)))["status"], "killed")
        t.join(15)
        self.assertFalse(t.is_alive())
        r = box["r"]
        self.assertTrue(r["cancelled"])
        self.assertEqual(r["exit_code"], -1)
        self.assertIn("cancelled by its sender", r["stderr"])
        self.assertNotIn(jid, C._RUNNING)


class KeptCancelsTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.base = tempfile.mkdtemp(prefix="hp-cancels-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_a_kept_cancel_is_spent_once_and_ages_out(self):
        cfg = {"max_job_age_sec": 10}
        C.keep_cancel(cfg, self.base, "", "j1", now=1000)
        self.assertFalse(C.take_cancel(cfg, self.base, "ops", "j1", now=1001))
        self.assertTrue(C.take_cancel(cfg, self.base, "", "j1", now=1001))
        self.assertFalse(C.take_cancel(cfg, self.base, "", "j1", now=1002))
        C.keep_cancel(cfg, self.base, "", "j2", now=1000)
        self.assertFalse(C.take_cancel(cfg, self.base, "", "j2", now=1021))

    def test_a_bad_file_is_no_cancels(self):
        import os
        with open(os.path.join(self.base, C.CANCELS_FILE), "w") as fh:
            fh.write("{not json")
        self.assertFalse(C.take_cancel({}, self.base, "", "j"))
        with open(os.path.join(self.base, C.CANCELS_FILE), "w") as fh:
            fh.write('{"": {"j": "yesterday"}, "x": 7}')
        self.assertFalse(C.take_cancel({"max_job_age_sec": "x"}, self.base, "", "j"))


class SenderTest(unittest.TestCase):
    def test_the_sender_builds_a_cancel_the_runner_admits(self):
        out = io.StringIO()
        argv = ["send_job.py", "cancel", "--job-id", "job-7", "--secret", TR.SECRET]
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(io.StringIO()):
            self.assertEqual(SJ.main(), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "[HOMING-PIGEON] cancel job-7")
        payload, *_ = R._admit_object("\n".join(lines[2:]),
                                      R.build_secrets({"shared_secret": TR.SECRET}),
                                      "job-7")
        self.assertEqual((payload["type"], payload["job_id"]), ("cancel", "job-7"))
        self.assertIn("issued_at", payload)

    def test_a_bad_job_id_is_refused(self):
        argv = ["send_job.py", "cancel", "--job-id", "../x", "--secret", TR.SECRET]
        with mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()):
            self.assertEqual(SJ.main(), 2)


if __name__ == "__main__":
    unittest.main()
