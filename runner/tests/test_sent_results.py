"""A job executes at most once per job_id; its result is kept and
resent (PROTOCOL.md sections 5 and 6).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Delivery stays at-least-once: the seen-set commits only after a
successful send. What changed is what a redelivery does. The result,
as it goes on the wire, is recorded under <base_dir>/sent/ before the
send, and a redelivered job whose record exists is answered with
those bytes and executed again never. The record is bound to the
job's received digest, so a different job under a reused id runs on
its own merits, and it ages out with output_retention_days.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))

from runner import runner as R  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (by name, not `from`:
#                                        the harness class is not re-collected)


class FlakySMTP(TR.FakeSMTP):
    """Fails the first N sends, then delivers."""

    def __init__(self, fail_first=1):
        super().__init__()
        self.fail_first = fail_first
        self.attempts = 0

    def send_message(self, msg):
        self.attempts += 1
        if self.attempts <= self.fail_first:
            raise OSError("smtp: connection reset")
        super().send_message(msg)


class SentResultTest(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.tmp = self.h.tmp
        self.seen_path = self.h.seen_path

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cycle(self, mails, smtp, seen):
        imap = TR.FakeIMAP(mails)
        R.poll_once(self.cfg, self.tmp, seen, self.seen_path,
                    imap=imap, smtp=smtp)
        return imap

    def _counter_job(self, jid, marker):
        # A script that leaves a count of its executions on disk.
        script = f'echo run >> "{marker}"\necho hello'
        return TR.job_payload(jid, kind="exec", script=script,
                              interpreter=["sh"])

    def test_a_failed_send_resends_without_a_second_execution(self):
        jid = str(uuid.uuid4())
        marker = os.path.join(self.tmp, "runs.txt")
        mail = TR.job_email(self._counter_job(jid, marker))
        smtp = FlakySMTP(fail_first=1)
        seen = {}
        # First cycle: the job runs, the send fails, the mail stays
        # unseen and the id is not committed. That is at-least-once
        # delivery, as before.
        imap = self._cycle([mail], smtp, seen)
        with open(marker) as f:
            self.assertEqual(f.read().count("run"), 1)
        self.assertEqual(smtp.sent, [])
        self.assertNotIn(jid, " ".join(seen))
        self.assertEqual(imap.flagged, [])
        rec_dir = os.path.join(self.tmp, R.SENT_DIRNAME)
        self.assertEqual(len(os.listdir(rec_dir)), 1)
        # Second cycle: the same mail again. The recorded result is
        # sent, the script does not run a second time, and the id is
        # committed.
        imap = self._cycle([mail], smtp, seen)
        with open(marker) as f:
            self.assertEqual(f.read().count("run"), 1)
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, smtp.sent[0]["Subject"])
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello", result["stdout"])
        self.assertTrue(any(jid in k for k in seen))
        self.assertEqual([str(x) for x in imap.flagged], ["1"])

    def test_the_resent_bytes_are_the_recorded_bytes(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid))
        smtp = FlakySMTP(fail_first=1)
        seen = {}
        self._cycle([mail], smtp, seen)
        with open(os.path.join(
            self.tmp, R.SENT_DIRNAME,
            os.listdir(os.path.join(self.tmp, R.SENT_DIRNAME))[0])) as f:
            rec = json.load(f)
        self.assertEqual(rec["job_id"], jid)
        self.assertTrue(rec["completed_at"].endswith("Z"))
        self._cycle([mail], smtp, seen)
        self.assertEqual(smtp.sent[0].get_content().strip(),
                         rec["body"].strip())

    def test_a_different_job_under_the_same_id_runs_on_its_own(self):
        # The record is bound to the job's received digest. A sender
        # that reuses an id for another script (before the first was
        # acknowledged) gets that script run, not the old result.
        jid = str(uuid.uuid4())
        marker = os.path.join(self.tmp, "runs.txt")
        first = TR.job_email(self._counter_job(jid, marker))
        smtp = FlakySMTP(fail_first=1)
        seen = {}
        self._cycle([first], smtp, seen)
        with open(marker) as f:
            self.assertEqual(f.read().count("run"), 1)
        other = TR.job_payload(jid, kind="exec",
                               script=f'echo other >> "{marker}"',
                               interpreter=["sh"])
        self._cycle([TR.job_email(other)], smtp, seen)
        with open(marker) as f:
            text = f.read()
        self.assertEqual(text.count("run"), 1)
        self.assertEqual(text.count("other"), 1)
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], 0)

    def test_a_committed_id_is_a_replay_not_a_resend(self):
        # Once the send succeeded and the id is in the seen-set, a
        # third copy is the replay the seen-set exists for: nothing
        # is sent, nothing runs.
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid))
        smtp = TR.FakeSMTP()
        seen = {}
        self._cycle([mail], smtp, seen)
        self.assertEqual(len(smtp.sent), 1)
        self._cycle([mail], smtp, seen)
        self.assertEqual(len(smtp.sent), 1)

    def test_records_age_out_with_retention(self):
        d = os.path.join(self.tmp, R.SENT_DIRNAME)
        os.makedirs(d)
        old = os.path.join(d, "old.json")
        new = os.path.join(d, "new.json")
        for p in (old, new):
            with open(p, "w") as f:
                f.write("{}")
        past = time.time() - 10 * 86400
        os.utime(old, (past, past))
        self.assertEqual(R.prune_sent(self.tmp, 7), 1)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new))
        self.assertEqual(R.prune_sent(self.tmp, 0), 0)
        self.assertEqual(R.prune_sent(self.tmp, "x"), 0)
        self.assertEqual(R.prune_sent("", 7), 0)

    def test_a_broken_record_is_ignored(self):
        job = TR.job_payload("j1")
        skey = R._seen_key(self.cfg, "j1")
        self.assertIsNone(R.load_sent_result(self.tmp, skey, job))
        path = R._sent_path(self.tmp, skey)
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write("{not json")
        self.assertIsNone(R.load_sent_result(self.tmp, skey, job))
        with open(path, "w") as f:
            json.dump({"subject": "s"}, f)   # no body
        self.assertIsNone(R.load_sent_result(self.tmp, skey, job))
        self.assertTrue(R.save_sent_result(self.tmp, skey, job, "s", "b"))
        rec = R.load_sent_result(self.tmp, skey, job)
        self.assertEqual((rec["subject"], rec["body"]), ("s", "b"))
        # A record is for one base dir; none means no claim.
        self.assertFalse(R.save_sent_result("", skey, job, "s", "b"))
        self.assertIsNone(R.load_sent_result("", skey, job))

    def test_prune_skips_an_entry_it_cannot_remove(self):
        # Queue A: prune_sent's silent-skip arm -- an entry
        # that cannot be removed (here a directory old
        # enough to qualify) is passed over, the count
        # reflects only real removals, and nothing raises.
        d = os.path.join(self.tmp, R.SENT_DIRNAME)
        os.makedirs(d)
        old_file = os.path.join(d, "old.json")
        with open(old_file, "w") as f:
            f.write("{}")
        stuck = os.path.join(d, "stuck")
        os.makedirs(stuck)
        past = time.time() - 10 * 86400
        os.utime(old_file, (past, past))
        os.utime(stuck, (past, past))
        self.assertEqual(R.prune_sent(self.tmp, 7), 1)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.isdir(stuck))

    def test_a_failed_record_is_logged_and_never_raises(self):
        # Queue A: the best-effort promise in save_sent_result's
        # docstring -- a failure to record is logged at WARN
        # and the send proceeds (the caller sees False), it
        # never raises into the send path.
        job = TR.job_payload("j1")
        skey = R._seen_key(self.cfg, "j1")
        blocker = os.path.join(self.tmp, R.SENT_DIRNAME)
        with open(blocker, "w") as f:
            f.write("a file where the sent directory belongs")
        lines = []
        with mock.patch.object(
                R, "log",
                lambda msg, level="INFO": lines.append((level, msg))):
            self.assertFalse(
                R.save_sent_result(self.tmp, skey, job, "s", "b"))
        self.assertTrue(any(level == "WARN"
                            and "sent-result record failed" in msg
                            and "j1" in msg
                            for level, msg in lines), lines)
        self.assertIsNone(R.load_sent_result(self.tmp, skey, job))


if __name__ == "__main__":
    unittest.main()
