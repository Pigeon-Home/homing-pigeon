"""Execution at most once, delivery at least once: the outbox stash.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

The moment a result is built and signed it is written under
<base_dir>/outbox/ and the job is committed as seen -- on disk --
before the first send (PROTOCOL.md sections 5 and 6). A send that
fails leaves the record waiting; later polls resend it, at least
result_resend_backoff_sec apart, byte for byte, and give it up into
outbox/failed/ with an audit entry after result_stash_retention_sec.
The script is never run twice. These tests drive the mail core
against the fake mailbox with a sender that fails on demand and an
injected clock; the window that remains (a crash during the stash
write itself) is pinned by test, not assumed away.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest import mock

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    given = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))

from runner import runner as R  # noqa: E402
from runner.guard import security as S  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (by name, not `from`:
#                                        the harness class is not re-collected)


class FlakySMTP(TR.FakeSMTP):
    """Fails the first N sends, then delivers; every attempt is kept."""

    def __init__(self, fail_first=1):
        super().__init__()
        self.fail_first = fail_first
        self.attempts = 0
        self.bodies = []

    def send_message(self, msg):
        self.attempts += 1
        self.bodies.append(msg.get_content())
        if self.attempts <= self.fail_first:
            raise OSError("smtp: connection reset")
        super().send_message(msg)


class Clock:
    """An injected clock for time.time: starts now, moves on demand."""

    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class StashHarness(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.tmp = self.h.tmp
        self.seen_path = self.h.seen_path
        self.clock = Clock()
        self._clock_patch = mock.patch.object(R.time, "time", self.clock)
        self._clock_patch.start()

    def tearDown(self):
        self._clock_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cycle(self, mails, smtp, seen):
        imap = TR.FakeIMAP(mails)
        R.poll_once(self.cfg, self.tmp, seen, self.seen_path,
                    imap=imap, smtp=smtp)
        return imap

    def _counter_job(self, jid, marker):
        script = 'echo run >> "%s"\necho hello' % marker
        return TR.job_payload(jid, kind="exec", script=script,
                              interpreter=["sh"])

    def _runs(self, marker):
        if not os.path.exists(marker):
            return 0
        with open(marker) as f:
            return f.read().count("run")

    def _outbox(self):
        d = R._outbox_dir(self.tmp)
        if not os.path.isdir(d):
            return []
        return sorted(n for n in os.listdir(d) if n.endswith(".json"))

    def _failed(self):
        d = os.path.join(R._outbox_dir(self.tmp), R.OUTBOX_FAILED_DIRNAME)
        if not os.path.isdir(d):
            return []
        return sorted(os.listdir(d))

    def _record(self):
        names = self._outbox()
        self.assertEqual(len(names), 1, names)
        with open(os.path.join(R._outbox_dir(self.tmp), names[0])) as f:
            return json.load(f)

    def _audit(self):
        path = os.path.join(self.tmp, S.AUDIT_FILE)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]


class ExecuteOnceTest(StashHarness):
    def test_send_failure_does_not_reexecute(self):
        jid = str(uuid.uuid4())
        marker = os.path.join(self.tmp, "runs.txt")
        mail = TR.job_email(self._counter_job(jid, marker))
        smtp = FlakySMTP(fail_first=1)
        seen = {}
        # Cycle one: the job runs, the stash is written, the job is
        # committed as seen (memory and disk) and the mail marked, the
        # first send fails and the record waits with one attempt.
        imap = self._cycle([mail], smtp, seen)
        self.assertEqual(self._runs(marker), 1)
        self.assertEqual(smtp.sent, [])
        self.assertTrue(any(jid in k for k in seen))
        self.assertTrue(any(jid in k for k in R.load_seen(self.seen_path)))
        self.assertEqual([str(x) for x in imap.flagged], ["1"])
        rec = self._record()
        self.assertEqual(rec["job_id"], jid)
        self.assertEqual(rec["attempts"], 1)
        self.assertIn("connection reset", rec["last_error"])
        # Cycle two, past the backoff: the resend pass delivers the
        # stash; the script did not run again; the outbox is empty
        # and the record moved to sent/.
        self.clock.advance(120)
        self._cycle([], smtp, seen)
        self.assertEqual(self._runs(marker), 1)
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, smtp.sent[0]["Subject"])
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello", result["stdout"])
        self.assertEqual(self._outbox(), [])
        self.assertTrue(os.path.isfile(R._sent_path(self.tmp, rec["skey"])))

    def test_stash_is_resent_byte_identical(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid))
        smtp = FlakySMTP(fail_first=1)
        seen = {}
        self._cycle([mail], smtp, seen)
        rec = self._record()
        self.clock.advance(120)
        self._cycle([], smtp, seen)
        self.assertEqual(len(smtp.bodies), 2)
        self.assertEqual(smtp.bodies[0], smtp.bodies[1])
        self.assertEqual(smtp.bodies[1].strip(), rec["body"].strip())
        self.assertEqual(self._outbox(), [])

    def test_the_same_mail_again_is_a_replay_while_the_record_waits(self):
        # The job is seen the moment it is stashed: a redelivered copy
        # of the mail is skipped, not re-executed, and not re-sent by
        # the ingest path -- the resend pass owns delivery.
        jid = str(uuid.uuid4())
        marker = os.path.join(self.tmp, "runs.txt")
        mail = TR.job_email(self._counter_job(jid, marker))
        smtp = FlakySMTP(fail_first=10)
        seen = {}
        self._cycle([mail], smtp, seen)
        self._cycle([mail], smtp, seen)
        self.assertEqual(self._runs(marker), 1)
        self.assertEqual(len(self._outbox()), 1)
        self.assertEqual(self._record()["attempts"], 1)   # backoff held

    def test_backoff_is_honored(self):
        self.cfg["result_resend_backoff_sec"] = 60
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid))
        smtp = FlakySMTP(fail_first=10)
        seen = {}
        self._cycle([mail], smtp, seen)
        self.assertEqual(smtp.attempts, 1)
        self.clock.advance(10)
        self._cycle([], smtp, seen)
        self.assertEqual(smtp.attempts, 1)      # inside the backoff
        self.clock.advance(55)
        self._cycle([], smtp, seen)
        self.assertEqual(smtp.attempts, 2)      # past it
        self.assertEqual(self._record()["attempts"], 2)

    def test_retention_moves_to_failed_with_audit(self):
        self.cfg["result_stash_retention_sec"] = 100
        self.cfg["result_resend_backoff_sec"] = 1
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid))
        smtp = FlakySMTP(fail_first=100)
        seen = {}
        self._cycle([mail], smtp, seen)
        self.clock.advance(50)
        self._cycle([], smtp, seen)
        self.assertEqual(smtp.attempts, 2)
        self.clock.advance(60)                   # 110 s old: past retention
        self._cycle([], smtp, seen)
        self.assertEqual(smtp.attempts, 2)       # no further attempt
        self.assertEqual(self._outbox(), [])
        self.assertEqual(len(self._failed()), 1)
        rows = [a for a in self._audit() if a.get("feature") == "delivery"]
        self.assertEqual(len(rows), 1, self._audit())
        self.assertEqual(rows[0]["decision"], "failed")
        self.assertEqual(rows[0]["job_id"], jid)
        self.assertIn("retention", rows[0]["reason"])
        # Nothing touches it again.
        self.clock.advance(1000)
        self._cycle([], smtp, seen)
        self.assertEqual(smtp.attempts, 2)
        self.assertEqual(len(self._failed()), 1)

    def test_two_callers_send_one_stash_once(self):
        skey = "bm-stash-0001"
        self.assertTrue(R.stash_result(
            self.tmp, skey, {"job_id": skey, "kind": "exec"},
            "[HOMING-PIGEON] result " + skey, "alpha"))
        sent = []

        def sender(subject, body, to):
            time.sleep(0.05)
            sent.append(body)

        threads = [threading.Thread(target=R.deliver_stash,
                                    args=(self.tmp, skey, sender))
                   for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
            self.assertFalse(t.is_alive())
        self.assertEqual(sent, ["alpha"])

    def test_crash_between_execute_and_stash_is_the_only_window(self):
        # The stash write is the one window: a job whose record cannot
        # be written is NOT committed and WILL run again. This pins
        # that the window is the write itself and nothing wider.
        jid = str(uuid.uuid4())
        marker = os.path.join(self.tmp, "runs.txt")
        mail = TR.job_email(self._counter_job(jid, marker))
        smtp = TR.FakeSMTP()
        seen = {}
        with mock.patch.object(R, "stash_result", return_value=False):
            imap = self._cycle([mail], smtp, seen)
        self.assertEqual(self._runs(marker), 1)
        self.assertFalse(any(jid in k for k in seen))
        self.assertEqual(imap.flagged, [])
        self.assertEqual(smtp.sent, [])
        # The stash works again: the redelivered mail runs the script a
        # second time (the window), stashes, commits and delivers.
        imap = self._cycle([mail], smtp, seen)
        self.assertEqual(self._runs(marker), 2)
        self.assertTrue(any(jid in k for k in seen))
        self.assertEqual(len(smtp.sent), 1)

    def test_a_rejection_goes_through_the_same_stash(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid, kind="no-such-kind"))
        smtp = FlakySMTP(fail_first=1)
        seen = {}
        imap = self._cycle([mail], smtp, seen)
        self.assertEqual(smtp.sent, [])
        self.assertTrue(any(jid in k for k in seen))
        self.assertEqual([str(x) for x in imap.flagged], ["1"])
        self.assertEqual(self._record()["job_id"], jid)
        self.clock.advance(120)
        self._cycle([], smtp, seen)
        self.assertEqual(len(smtp.sent), 1)
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertEqual(self._outbox(), [])

    def test_a_delivery_failure_is_never_a_job_failure(self):
        # deliver_stash never raises; the record carries the error.
        jid = str(uuid.uuid4())
        skey = R._seen_key(self.cfg, jid)
        self.assertTrue(R.stash_result(self.tmp, skey, TR.job_payload(jid),
                                       "s", "b"))

        def boom(subject, body, to):
            raise ValueError("header")

        self.assertFalse(R.deliver_stash(self.tmp, skey, boom))
        rec = R.load_stash(self.tmp, skey)
        self.assertEqual(rec["attempts"], 1)
        self.assertEqual(rec["last_error"], "header")
        self.assertTrue(R.deliver_stash(self.tmp, skey, lambda s, b, to: None))
        self.assertIsNone(R.load_stash(self.tmp, skey))
        self.assertFalse(R.deliver_stash(self.tmp, skey, lambda s, b, to: None))

    def test_the_pass_is_capped_and_ordered_oldest_first(self):
        skeys = []
        for i in range(5):
            jid = "job-%d" % i
            skey = R._seen_key(self.cfg, jid)
            self.clock.advance(1)
            R.stash_result(self.tmp, skey, TR.job_payload(jid), "s", "b%d" % i)
            skeys.append(skey)
        sent = []
        self.clock.advance(100)
        counts = R.resend_stashed(self.tmp, self.cfg,
                                  lambda s, b, to: sent.append(b), limit=3)
        self.assertEqual(sent, ["b0", "b1", "b2"])
        self.assertEqual(counts["delivered"], 3)
        self.assertEqual(len(self._outbox()), 2)


class RecordTest(StashHarness):
    def test_a_committed_id_is_a_replay_not_a_resend(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(TR.job_payload(jid))
        smtp = TR.FakeSMTP()
        seen = {}
        self._cycle([mail], smtp, seen)
        self.assertEqual(len(smtp.sent), 1)
        self._cycle([mail], smtp, seen)
        self.assertEqual(len(smtp.sent), 1)

    def test_a_redelivery_after_the_seen_set_is_lost_is_answered_from_sent(self):
        # The delivered record lives on in sent/: a copy that arrives
        # after the seen-set was pruned or lost is answered from it,
        # not executed again; a different job under the same id (the
        # digest differs) runs on its own.
        jid = str(uuid.uuid4())
        marker = os.path.join(self.tmp, "runs.txt")
        mail = TR.job_email(self._counter_job(jid, marker))
        smtp = TR.FakeSMTP()
        seen = {}
        self._cycle([mail], smtp, seen)
        self.assertEqual(self._runs(marker), 1)
        self.assertEqual(len(smtp.sent), 1)
        os.unlink(self.seen_path)
        self._cycle([mail], smtp, {})
        self.assertEqual(self._runs(marker), 1)
        self.assertEqual(len(smtp.sent), 2)
        self.assertEqual(smtp.sent[0].get_content(), smtp.sent[1].get_content())
        other = TR.job_payload(jid, kind="exec",
                               script='echo other >> "%s"' % marker,
                               interpreter=["sh"])
        os.unlink(self.seen_path)
        self._cycle([TR.job_email(other)], smtp, {})
        with open(marker) as f:
            text = f.read()
        self.assertEqual(text.count("run"), 1)
        self.assertEqual(text.count("other"), 1)

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
        self.assertTrue(R.stash_result(self.tmp, skey, job, "s", "b"))
        rec = R.load_sent_result(self.tmp, skey, job)   # the waiting record
        self.assertEqual((rec["subject"], rec["body"]), ("s", "b"))
        self.assertFalse(R.stash_result("", skey, job, "s", "b"))
        self.assertIsNone(R.load_sent_result("", skey, job))
        self.assertIsNone(R.load_stash("", skey))

    def test_prune_skips_an_entry_it_cannot_remove(self):
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

    def test_a_failed_stash_is_logged_and_never_raises(self):
        job = TR.job_payload("j1")
        skey = R._seen_key(self.cfg, "j1")
        blocker = R._outbox_dir(self.tmp)
        with open(blocker, "w") as f:
            f.write("a file where the outbox belongs")
        lines = []
        with mock.patch.object(
                R, "log",
                lambda msg, level="INFO": lines.append((level, msg))):
            self.assertFalse(R.stash_result(self.tmp, skey, job, "s", "b"))
        self.assertTrue(any(level == "ERROR" and "not stashed" in msg
                            and "j1" in msg for level, msg in lines), lines)
        self.assertIsNone(R.load_sent_result(self.tmp, skey, job))

    def test_the_record_carries_what_a_stub_would_need(self):
        job = TR.job_payload("j1")
        skey = R._seen_key(self.cfg, "j1")
        meta = R._result_meta({"v": 1, "type": "result", "job_id": "j1",
                               "exit_code": 3, "stdout": "big",
                               "judgment": {"verdict": "pass"}})
        self.assertNotIn("stdout", meta)
        self.assertEqual(meta["exit_code"], 3)
        R.stash_result(self.tmp, skey, job, "s", "b", to="a@example.com",
                       transport="file", key_id="k1", encrypted=True,
                       meta=meta)
        rec = R.load_stash(self.tmp, skey)
        self.assertEqual(rec["to"], "a@example.com")
        self.assertEqual(rec["transport"], "file")
        self.assertEqual(rec["key_id"], "k1")
        self.assertTrue(rec["encrypted"])
        self.assertEqual(rec["meta"]["judgment"], {"verdict": "pass"})
        self.assertNotIn("secret", json.dumps(rec).lower().replace(
            "shared_secret", ""))


class InspectAndStartupTest(StashHarness):
    def test_inspect_outbox_lists_records(self):
        skey = R._seen_key(self.cfg, "j1")
        R.stash_result(self.tmp, skey, TR.job_payload("j1"), "s", "b")
        R.deliver_stash(self.tmp, skey, lambda s, b, to: (_ for _ in ()).throw(
            OSError("down")))
        skey2 = R._seen_key(self.cfg, "j2")
        R.stash_result(self.tmp, skey2, TR.job_payload("j2"), "s", "b")
        R._stash_fail(self.tmp, skey2, R.load_stash(self.tmp, skey2),
                      "gave up", self.cfg)
        report = R.outbox_report(self.tmp)
        self.assertEqual([r["job_id"] for r in report["waiting"]], ["j1"])
        self.assertEqual(report["waiting"][0]["attempts"], 1)
        self.assertEqual(report["waiting"][0]["last_error"], "down")
        self.assertEqual([r["job_id"] for r in report["failed"]], ["j2"])
        lines = R.outbox_lines(self.tmp)
        self.assertEqual(lines[0], "waiting: 1")
        self.assertIn("j1", lines[1])
        self.assertIn("down", lines[1])
        self.assertEqual(lines[2], "failed: 1")
        # The CLI door.
        import io
        args = mock.Mock(inspect="outbox", config=None)
        out = io.StringIO()
        with mock.patch.object(sys, "stdout", out):
            rc = R.run_inspect({"base_dir": self.tmp}, args)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["waiting"][0]["job_id"],
                         "j1")
        self.assertEqual(R.outbox_report(""), {"waiting": [], "failed": []})

    def test_the_cli_knows_the_outbox_inspection(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "runner",
                                                         "runner.py"),
                            "--help"], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True,
                           cwd=ROOT, timeout=120)
        self.assertEqual(r.returncode, 0)
        self.assertIn("outbox", r.stdout)

    def test_the_config_keys_read_as_documented(self):
        self.assertEqual(R._stash_retention_sec({}), 86400)
        self.assertEqual(R._resend_backoff_sec({}), 60)
        self.assertEqual(R._stash_retention_sec({"result_stash_retention_sec": "x"}),
                         86400)
        self.assertEqual(R._resend_backoff_sec({"result_resend_backoff_sec": 0}),
                         60)
        self.assertEqual(R._resend_backoff_sec({"result_resend_backoff_sec": 5}),
                         5)
        self.assertIn("result_stash_retention_sec", R.HOT_KEYS)
        self.assertIn("result_resend_backoff_sec", R.HOT_KEYS)
        self.assertEqual(R.HOT_DEFAULTS["result_stash_retention_sec"], 86400)
        self.assertEqual(R.HOT_DEFAULTS["result_resend_backoff_sec"], 60)


class TransportPathTest(StashHarness):
    def test_a_channel_result_is_stashed_delivered_and_marked(self):
        # Through a transport extension's channel the "send" is the
        # capture into the channel outbox, which never fails: the
        # record is delivered at once and moves to sent/, carrying the
        # transport name it came through.
        jid = str(uuid.uuid4())
        job = TR.job_payload(jid)
        from runner.wire import jobcrypto
        from send_job import sign_payload
        body = jobcrypto.encrypt_body(sign_payload(job, TR.SECRET), TR.SECRET,
                                      job_id=jid, key_id="",
                                      sign=sign_payload)
        seen = {}
        out = R.process_transport_message(
            self.cfg, self.tmp, seen, R.build_secrets(self.cfg), {},
            "[HOMING-PIGEON] job " + jid, body, transport="file")
        self.assertEqual(len(out), 1)
        self.assertTrue(out.consume)
        self.assertTrue(any(jid in k for k in seen))
        self.assertEqual(self._outbox(), [])
        skey = [k for k in seen if jid in k][0]
        with open(R._sent_path(self.tmp, skey)) as f:
            rec = json.load(f)
        self.assertEqual(rec["transport"], "file")

    def test_a_waiting_channel_record_goes_back_out_its_channel(self):
        skey = R._seen_key(self.cfg, "j1")
        R.stash_result(self.tmp, skey, TR.job_payload("j1"),
                       "[HOMING-PIGEON] result j1", "signed", to="a@example.com",
                       transport="file")
        self.clock.advance(100)
        counts = R.resend_stashed(self.tmp, self.cfg, None)
        self.assertEqual(counts["delivered"], 1)
        outbox = R._transports.channel_paths(self.tmp, "file")["outbox"]
        names = sorted(os.listdir(outbox))
        self.assertIn("j1.result.txt", names)
        self.assertIn("j1.target.txt", names)
        self.assertEqual(self._outbox(), [])

    def test_a_mailbox_record_waits_for_a_cycle_with_a_mailbox(self):
        skey = R._seen_key(self.cfg, "j1")
        R.stash_result(self.tmp, skey, TR.job_payload("j1"), "s", "b")
        self.clock.advance(100)
        counts = R.resend_stashed(self.tmp, self.cfg, None)
        self.assertEqual(counts["attempted"], 0)
        self.assertEqual(len(self._outbox()), 1)


if given is not None:
    _STEP = st.sampled_from(["send ok", "send fail", "poll", "advance"])

    class NeverTwiceProperty(unittest.TestCase):
        @settings(max_examples=25, deadline=None)
        @given(steps=st.lists(_STEP, min_size=1, max_size=14),
               retention=st.integers(min_value=30, max_value=400))
        def test_never_two_executions_and_never_a_lost_result(self, steps,
                                                             retention):
            h = TR.RunnerTest("test_ping_roundtrip")
            h.setUp()
            clock = Clock()
            patch = mock.patch.object(R.time, "time", clock)
            patch.start()
            try:
                h.cfg["result_resend_backoff_sec"] = 20
                h.cfg["result_stash_retention_sec"] = retention
                jid = str(uuid.uuid4())
                marker = os.path.join(h.tmp, "runs.txt")
                mail = TR.job_email(TR.job_payload(
                    jid, kind="exec", script='echo run >> "%s"' % marker,
                    interpreter=["sh"]))
                mode = {"fail": False}

                class Switch(TR.FakeSMTP):
                    def send_message(self, msg):
                        if mode["fail"]:
                            raise OSError("down")
                        super().send_message(msg)

                smtp = Switch()
                seen = {}
                delivered = False
                for step in steps:
                    if step == "send ok":
                        mode["fail"] = False
                    elif step == "send fail":
                        mode["fail"] = True
                    elif step == "advance":
                        clock.advance(25)
                    else:
                        imap = TR.FakeIMAP([mail] if not delivered else [])
                        R.poll_once(h.cfg, h.tmp, seen, h.seen_path,
                                    imap=imap, smtp=smtp)
                    delivered = delivered or bool(smtp.sent)
                runs = 0
                if os.path.exists(marker):
                    with open(marker) as f:
                        runs = f.read().count("run")
                self.assertLessEqual(runs, 1)
                self.assertLessEqual(len(smtp.sent), 1)
                if runs == 1:
                    outbox = R._outbox_dir(h.tmp)
                    waiting = [n for n in os.listdir(outbox)
                               if n.endswith(".json")] if os.path.isdir(outbox) else []
                    failed_dir = os.path.join(outbox, R.OUTBOX_FAILED_DIRNAME)
                    failed = os.listdir(failed_dir) if os.path.isdir(failed_dir) else []
                    skey = [k for k in seen if jid in k][0]
                    sent = os.path.isfile(R._sent_path(h.tmp, skey))
                    # executed: delivered (sent/), still waiting, or given up
                    self.assertEqual(
                        (len(smtp.sent) == 1 and sent)
                        or (len(waiting) == 1) or (len(failed) == 1), True)
            finally:
                patch.stop()
                shutil.rmtree(h.tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
