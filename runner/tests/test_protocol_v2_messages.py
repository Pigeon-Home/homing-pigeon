#!/usr/bin/env python3
"""Version 2 messages. Jobs stay version 1.

A determination and a question go out only when the operator
turned protocol_v2 on. An answer may come from any holder of
a trusted secret. It rides the version 1 result as context
and never decides what runs. answer_only answers and does
not execute.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
from unittest import mock
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "tests"))

from runner.wire import jobcrypto  # noqa: E402
from runner.wire import protocol_v2 as v2  # noqa: E402
from runner.runner import (  # noqa: E402
    _disk_owns, _disk_release, _pid_alive, load_seen, poll_once,
    process_transport_message, save_seen, sign_payload, verify_body)
from runner.tests.security_parity import SECRET, FakeIMAP, FakeSMTP  # noqa: E402


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seal(payload, ident):
    signed = sign_payload(payload, SECRET)
    return jobcrypto.encrypt_body(
        signed, SECRET, job_id=ident, key_id="", sign=sign_payload)


def _mail(subject, payload, ident):
    msg = EmailMessage()
    msg["From"] = "si@example.com"
    msg["To"] = "si@example.com"
    msg["Subject"] = subject
    msg.set_content(_seal(payload, ident))
    return msg.as_bytes()


def _open(msg):
    body = verify_body(msg.get_content(), SECRET)
    ident = str(msg["Subject"]).rsplit(" ", 1)[-1]
    if isinstance(body, dict) and isinstance(body.get("hp_enc"), dict):
        inner = jobcrypto.decrypt_body(
            body, SECRET, ident, body.get("key_id") or "")
        body = verify_body(inner, SECRET)
    return body


def _job(job_id, kind="ping", script=None):
    job = {"v": 1, "type": "job", "job_id": job_id,
           "issued_at": _now(), "kind": kind}
    if script is not None:
        job["script"] = script
    return job


class OtherAnswersLegsTest(unittest.TestCase):
    """Queue A refill: protocol_v2._other_answers'
    unsafe-id leg (coverage run 40189711740: lines
    431-432). A question id that is not a safe id
    names no answer file: the other-answers read
    answers empty rather than following the id out
    of the answers folder.
    """

    def test_an_unsafe_question_id_reads_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                v2._other_answers(d, "../evil", None), [])
            self.assertEqual(
                v2._other_answers(d, "a/b", None), [])


class BuildersTest(unittest.TestCase):
    def test_subject_kind_ignores_a_job(self):
        self.assertIsNone(v2.subject_kind("[HOMING-PIGEON] job abc"))
        self.assertEqual(
            v2.subject_kind("[HOMING-PIGEON] question q.abc"),
            ("question", "q.abc"))

    def test_clean_pass_and_determination(self):
        self.assertTrue(v2.clean_pass(None))
        self.assertTrue(v2.clean_pass({"findings": [], "repair_action": None}))
        self.assertFalse(v2.clean_pass({"findings": [{"detail": "no"}]}))
        self.assertFalse(v2.clean_pass(
            {"findings": [], "repair_action": {"action": "fix"}}))
        job = {"job_id": "j1"}
        self.assertIsNone(v2.determination_for(job, None))
        det = v2.determination_for(
            job, {"findings": [{"detail": "the path is missing"}]})
        self.assertEqual(det["v"], 2)
        self.assertEqual(det["type"], "determination")
        self.assertEqual(det["msg_id"], "d.j1")
        self.assertEqual(det["expect"], "fail")
        self.assertFalse(det["clean_pass"])
        v2.validate(det)

    def test_question_and_answer_ids_are_deterministic(self):
        cfg = {"protocol_v2": True, "oracle_mode": "deterministic",
               "v2_answer_deadline_sec": 5}
        job = {"job_id": "j1", "kind": "exec", "script": "echo ok"}
        self.assertTrue(v2.should_ask(cfg, job))
        self.assertFalse(v2.should_ask(
            dict(cfg, answer_only=True), job))
        self.assertFalse(v2.should_ask(cfg, {"job_id": "j1", "kind": "ping"}))
        q = v2.question_for(cfg, job)
        self.assertEqual(q["msg_id"], "q.j1")
        self.assertEqual(q["deadline_sec"], 5)
        self.assertEqual(q["local_default"], "proceed")
        ans = v2.answer_for(q, "it would succeed")
        self.assertEqual(ans["question_id"], "q.j1")
        self.assertEqual(ans["msg_id"], "a.q.j1")
        self.assertEqual(ans["answer"], "it would succeed")
        v2.validate(q)
        v2.validate(ans)

    def test_outbound_is_empty_unless_enabled(self):
        job = {"job_id": "j1", "kind": "exec", "script": "echo ok"}
        plan = {"findings": [{"detail": "missing"}]}
        self.assertEqual(v2.outbound_for({}, job, plan), [])
        self.assertEqual(
            v2.outbound_for({"protocol_v2": True, "answer_only": True,
                             "oracle_mode": "deterministic"}, job, plan),
            [])
        out = v2.outbound_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            job, plan)
        kinds = [obj["type"] for _subj, obj in out]
        self.assertEqual(kinds, ["determination", "question"])

    def test_validate_rejects_a_job_version_and_a_bool(self):
        with self.assertRaises(ValueError):
            v2.validate({"v": 1, "type": "answer"})
        with self.assertRaises(ValueError):
            v2.validate({"v": True, "type": "answer"})

    def test_answerer_allowed(self):
        self.assertTrue(v2.answerer_allowed({}, ""))
        self.assertTrue(v2.answerer_allowed({"v2_answerers": ["", "lap"]}, ""))
        self.assertFalse(v2.answerer_allowed({"v2_answerers": ["lap"]}, ""))
        self.assertFalse(v2.answerer_allowed({"v2_answerers": "lap"}, ""))
        self.assertFalse(v2.answerer_allowed({}, None))

    def test_deadline_is_capped(self):
        self.assertEqual(v2.deadline_of({}), 0)
        self.assertEqual(v2.deadline_of({"v2_answer_deadline_sec": 90}), 30)
        self.assertEqual(v2.deadline_of({"v2_answer_deadline_sec": -3}), 0)

    def test_first_answer_wins(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"v": 2, "type": "question", "job_id": "j1", "msg_id": "q.j1",
             "issued_at": _now(), "deadline_sec": 0,
             "question": "Would it?", "local_default": "proceed"}
        first = v2.answer_for(q, "first")
        second = v2.answer_for(q, "second")
        results = []

        def once(obj):
            results.append(v2.store_answer(tmp, obj))

        threads = [threading.Thread(target=once, args=(obj,))
                   for obj in (first, second)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), [False, True])
        with open(os.path.join(tmp, "v2", "answers", "q.j1.json"),
                  encoding="utf-8") as fh:
            saved = json.load(fh)["answer"]["answer"]
        self.assertIn(saved, ("first", "second"))
        more = os.path.join(tmp, "v2", "answers", "q.j1.json.more.jsonl")
        self.assertTrue(os.path.isfile(more))
        with open(more, encoding="utf-8") as fh:
            extra = json.loads(fh.readline())
        self.assertIn(extra["answer"], ("first", "second"))
        self.assertNotEqual(extra["answer"], saved)

    def test_long_job_ids_do_not_share_a_question_slot(self):
        cfg = {"protocol_v2": True, "oracle_mode": "deterministic"}
        left = "a" * 120 + "left"
        right = "a" * 120 + "right"
        one = v2.question_for(cfg, {"job_id": left, "kind": "exec"})
        two = v2.question_for(cfg, {"job_id": right, "kind": "exec"})
        self.assertNotEqual(one["msg_id"], two["msg_id"])
        self.assertLessEqual(len(one["msg_id"]), 128)
        self.assertLessEqual(len(two["msg_id"]), 128)
        short = v2.question_for(cfg, {"job_id": "j1", "kind": "exec"})
        self.assertEqual(short["msg_id"], "q.j1")

    def test_a_second_answer_rides_as_late_context(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-late-")
        q = {"v": 2, "type": "question", "job_id": "j1", "msg_id": "q.j1",
             "issued_at": _now(), "deadline_sec": 0,
             "question": "Would it?", "local_default": "proceed"}
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "first")))
        self.assertFalse(v2.store_answer(tmp, v2.answer_for(q, "second")))
        got = v2.await_answer(tmp, q, time.time())
        kinds = [(s["kind"], s["text"]) for s in got]
        self.assertEqual(kinds[0], ("answer", "first"))
        self.assertIn(("late_answer", "second"), kinds)

    def test_a_broken_answer_file_does_not_hold_the_slot(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        folder = os.path.join(tmp, "v2", "answers")
        os.makedirs(folder)
        path = os.path.join(folder, "q.j1.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{")
        q = {"v": 2, "type": "question", "job_id": "j1", "msg_id": "q.j1",
             "issued_at": _now(), "deadline_sec": 0,
             "question": "Would it?", "local_default": "proceed"}
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "recovered")))
        with open(path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["answer"]["answer"], "recovered")
        self.assertFalse(v2.store_answer(tmp, v2.answer_for(q, "later")))
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["answer"]["answer"], "recovered")

    def test_await_on_time_late_and_missing(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.j1", "deadline_sec": 0, "local_default": "proceed"}
        missing = v2.await_answer(tmp, q, time.time())
        self.assertEqual([(s["by"], s["kind"], s["text"]) for s in missing],
                         [("runner", "local_default", "proceed")])
        folder = os.path.join(tmp, "v2", "answers")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "q.j1.json"), "w", encoding="utf-8") as fh:
            json.dump({"received_at": time.time() - 5,
                       "answer": {"answer": "yes"}}, fh)
        on_time = v2.await_answer(tmp, q, time.time())
        self.assertEqual(on_time[0]["kind"], "answer")
        self.assertEqual(on_time[0]["text"], "yes")
        with open(os.path.join(folder, "q.late.json"), "w", encoding="utf-8") as fh:
            json.dump({"received_at": time.time() + 100,
                       "answer": {"answer": "too late"}}, fh)
        late = v2.await_answer(
            tmp, {"msg_id": "q.late", "deadline_sec": 0,
                  "local_default": "proceed"}, time.time())
        self.assertEqual([s["kind"] for s in late],
                         ["local_default", "late_answer"])

    def test_pump_can_file_the_answer_during_the_look(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.pump", "deadline_sec": 0,
             "local_default": "proceed"}

        def pump():
            folder = os.path.join(tmp, "v2", "answers")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "q.pump.json")
            if os.path.exists(path):
                return
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"received_at": time.time(),
                           "answer": {"answer": "from the pump"}}, fh)

        got = v2.await_answer(tmp, q, time.time(), pump=pump)
        self.assertEqual(got[0]["text"], "from the pump")
        self.assertEqual(got[0]["kind"], "answer")

    def test_deadline_zero_does_not_wait_for_a_stuck_outbox(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.stuck0", "deadline_sec": 0,
             "local_default": "proceed"}
        t0 = time.monotonic()
        got = v2.await_answer(tmp, q, time.time(), pending=lambda: True)
        self.assertLess(time.monotonic() - t0, 0.3)
        self.assertEqual(got[0]["kind"], "local_default")

    def test_a_stuck_outbox_pauses_only_for_the_deadline(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.stuck1", "deadline_sec": 1,
             "local_default": "proceed"}
        t0 = time.monotonic()
        got = v2.await_answer(tmp, q, time.time(), pending=lambda: True)
        elapsed = time.monotonic() - t0
        self.assertGreater(elapsed, 0.7)
        self.assertLess(elapsed, 3.0)
        self.assertEqual([s["kind"] for s in got], ["local_default"])

    def test_a_stuck_outbox_gives_up_on_a_scripted_clock(self):
        # The give-up exit of the outbox wait, driven by a
        # scripted clock instead of wall time: the timing
        # test above proves the pause is real, this one pins
        # the branch itself so its coverage does not depend
        # on the suite's timing or state. Each reading moves
        # two seconds; the five-second deadline's send
        # give-up passes on the fourth reading, and the job
        # proceeds on the local default alone.
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.stuckx", "deadline_sec": 5,
             "local_default": "proceed"}
        readings = {"n": 0}

        def mono():
            readings["n"] += 1
            return 1000.0 + 2.0 * readings["n"]

        with mock.patch(
                "runner.wire.protocol_v2.time.monotonic", mono), \
             mock.patch(
                "runner.wire.protocol_v2.time.sleep",
                lambda seconds: None):
            got = v2.await_answer(
                tmp, q, time.time(), pending=lambda: True)
        self.assertEqual([s["kind"] for s in got], ["local_default"])
        self.assertGreaterEqual(readings["n"], 4)

    def test_the_deadline_starts_when_the_question_leaves(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.leave", "deadline_sec": 2,
             "local_default": "proceed"}
        state = {"n": 0}

        def pending():
            state["n"] += 1
            return state["n"] < 3

        def pump():
            if state["n"] < 3:
                return
            folder = os.path.join(tmp, "v2", "answers")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "q.leave.json")
            if os.path.exists(path):
                return
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"received_at": time.time(),
                           "answer": {"answer": "after send"}}, fh)

        t0 = time.monotonic()
        got = v2.await_answer(tmp, q, time.time(), pump=pump,
                              pending=pending)
        self.assertLess(time.monotonic() - t0, 2.5)
        self.assertEqual(got[0]["kind"], "answer")
        self.assertEqual(got[0]["text"], "after send")

    def test_a_wall_clock_step_does_not_make_an_open_wait_late(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        q = {"msg_id": "q.jump", "deadline_sec": 2,
             "local_default": "proceed"}

        def pump():
            folder = os.path.join(tmp, "v2", "answers")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "q.jump.json")
            if os.path.exists(path):
                return
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"received_at": time.time() + 1000,
                           "answer": {"answer": "still open"}}, fh)

        got = v2.await_answer(tmp, q, time.time(), pump=pump)
        self.assertEqual(got[0]["kind"], "answer")
        self.assertEqual(got[0]["text"], "still open")


class MailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-v2m-")
        self.cfg = {
            "mailbox_user": "si@example.com",
            "mailbox_password": "test-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp,
            "workers": 1,
            "max_job_age_sec": 3600,
            "default_timeout_sec": 30,
            "oracle_opinion_mode": "off",
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def _poll(self, mails, **cfg):
        smtp = FakeSMTP()
        merged = dict(self.cfg, **cfg)
        poll_once(merged, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        return smtp

    def test_v2_job_is_still_rejected(self):
        job = _job("v2job")
        job["v"] = 2
        smtp = self._poll([_mail("[HOMING-PIGEON] job v2job", job, "v2job")],
                          protocol_v2=True)
        self.assertEqual(smtp.sent, [])

    def test_an_answer_is_stored_and_does_not_execute(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec", "script": "echo ok"})
        ans = v2.answer_for(question, "proceed")
        smtp = self._poll([
            _mail("[HOMING-PIGEON] answer " + ans["msg_id"],
                  ans, ans["msg_id"])], protocol_v2=True)
        self.assertEqual(smtp.sent, [])
        path = os.path.join(self.tmp, "v2", "answers", "q.j1.json")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["answer"]["answer"], "proceed")

    def test_a_disallowed_key_is_not_stored(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec"})
        ans = v2.answer_for(question, "proceed")
        self._poll([
            _mail("[HOMING-PIGEON] answer " + ans["msg_id"],
                  ans, ans["msg_id"])],
            protocol_v2=True, v2_answerers=["someone-else"])
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp, "v2", "answers", "q.j1.json")))

    def test_cleartext_version_2_is_refused(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec"})
        msg = EmailMessage()
        msg["Subject"] = "[HOMING-PIGEON] question " + question["msg_id"]
        msg["From"] = "si@example.com"
        msg["To"] = "si@example.com"
        msg.set_content(sign_payload(question, SECRET))
        smtp = self._poll([msg.as_bytes()], answer_only=True)
        self.assertEqual(smtp.sent, [])

    def test_answer_only_replies_and_does_not_run_the_question(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec", "script": "echo ok"})
        smtp = self._poll([
            _mail("[HOMING-PIGEON] question " + question["msg_id"],
                  question, question["msg_id"])], answer_only=True)
        self.assertEqual(len(smtp.sent), 1)
        body = _open(smtp.sent[0])
        self.assertEqual(body["v"], 2)
        self.assertEqual(body["type"], "answer")
        self.assertEqual(body["question_id"], question["msg_id"])
        self.assertEqual(body["answer"], "proceed")
        self.assertNotIn("result", smtp.sent[0]["Subject"])

    def test_a_runner_that_executes_does_not_answer(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec"})
        imap = FakeIMAP([
            _mail("[HOMING-PIGEON] question " + question["msg_id"],
                  question, question["msg_id"])])
        smtp = FakeSMTP()
        poll_once(dict(self.cfg, protocol_v2=True), self.tmp, {},
                  self.seen_path, imap=imap, smtp=smtp)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(imap.flagged, [])

    def test_answer_only_does_not_execute_a_ping(self):
        job = _job("ping-1")
        smtp = self._poll([
            _mail("[HOMING-PIGEON] job ping-1", job, "ping-1")],
            answer_only=True)
        self.assertEqual(smtp.sent, [])

    def test_preseeded_answer_rides_the_result_and_does_not_decide(self):
        job_id = "v2exec1"
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": job_id, "kind": "exec", "script": "echo ok"})
        folder = os.path.join(self.tmp, "v2", "answers")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, question["msg_id"] + ".json"),
                  "w", encoding="utf-8") as fh:
            json.dump({"received_at": time.time(),
                       "answer": {"answer": "do not run"}}, fh)
            fh.write("\n")
        job = _job(job_id, kind="exec", script="echo ok")
        smtp = self._poll([
            _mail("[HOMING-PIGEON] job " + job_id, job, job_id)],
            protocol_v2=True, oracle_mode="deterministic")
        subjects = [m["Subject"] for m in smtp.sent]
        self.assertTrue(any("question " + question["msg_id"] in s
                            for s in subjects))
        results = [m for m in smtp.sent if m["Subject"].endswith(
            "result " + job_id) or ("result " + job_id) in m["Subject"]]
        self.assertEqual(len(results), 1)
        body = _open(results[0])
        self.assertEqual(body["v"], 1)
        self.assertEqual(body["type"], "result")
        self.assertIn("ok", body["stdout"])
        self.assertEqual(body["exit_code"], 0)
        kinds = [(s["kind"], s["text"]) for s in body["context"]]
        self.assertIn(("answer", "do not run"), kinds)

    def test_transport_hands_the_question_off_before_the_job_returns(self):
        job_id = "v2chan1"
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": job_id, "kind": "exec", "script": "echo ok"})
        ans = v2.answer_for(question, "from the channel")
        from runner.transport_extensions import channel as ch
        channel = os.path.join(
            self.tmp, "transport-extensions", "email")
        ch.deliver_job(
            channel, "zzz-answer",
            "[HOMING-PIGEON] answer " + ans["msg_id"],
            _seal(ans, ans["msg_id"]))
        job = _job(job_id, kind="exec", script="echo ok")
        sent = process_transport_message(
            dict(self.cfg, protocol_v2=True, oracle_mode="deterministic"),
            self.tmp, {}, {"": SECRET}, {},
            "[HOMING-PIGEON] job " + job_id,
            _seal(job, job_id))
        subjects = [row[0] for row in sent]
        self.assertTrue(any("result " + job_id in s for s in subjects))
        self.assertFalse(any("question " in s for s in subjects))
        outbox = os.path.join(channel, "outbox")
        texts = []
        for name in os.listdir(outbox):
            if name == "done":
                continue
            with open(os.path.join(outbox, name), encoding="utf-8") as fh:
                texts.append(fh.read())
        self.assertTrue(any("question " + question["msg_id"] in t
                            for t in texts))
        result = next(row for row in sent if "result " + job_id in row[0])
        parsed = verify_body(result[1], SECRET)
        ident = result[0].rsplit(" ", 1)[-1]
        if isinstance(parsed, dict) and isinstance(parsed.get("hp_enc"), dict):
            inner = jobcrypto.decrypt_body(
                parsed, SECRET, ident, parsed.get("key_id") or "")
            parsed = verify_body(inner, SECRET)
        self.assertEqual(parsed["v"], 1)
        self.assertEqual(parsed["exit_code"], 0)
        self.assertIn(("answer", "from the channel"),
                      [(s["kind"], s["text"]) for s in parsed["context"]])

    def test_a_question_on_the_channel_stays_in_the_inbox(self):
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "j1", "kind": "exec"})
        from runner.transport_extensions import channel as ch
        channel = os.path.join(
            self.tmp, "transport-extensions", "email")
        path = ch.deliver_job(
            channel, "q-j1",
            "[HOMING-PIGEON] question " + question["msg_id"],
            _seal(question, question["msg_id"]))
        sent = process_transport_message(
            dict(self.cfg, protocol_v2=True, transports=["email"]),
            self.tmp, {}, {"": SECRET}, {},
            "[HOMING-PIGEON] question " + question["msg_id"],
            _seal(question, question["msg_id"]))
        self.assertEqual(list(sent), [])
        self.assertFalse(sent.consume)
        poll_once(
            dict(self.cfg, protocol_v2=True, transports=["email"]),
            self.tmp, {}, self.seen_path)
        self.assertTrue(os.path.isfile(path))
        done = os.path.join(channel, "inbox", "done")
        self.assertEqual(os.listdir(done), [])

    def test_the_deadline_starts_after_the_question_leaves_the_outbox(self):
        job_id = "v2wait1"
        job = _job(job_id, kind="exec", script="echo ok")
        channel = os.path.join(
            self.tmp, "transport-extensions", "email")
        outbox = os.path.join(channel, "outbox")
        os.makedirs(outbox, exist_ok=True)
        filed = {"ok": False}

        def watcher():
            found = None
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and found is None:
                try:
                    names = os.listdir(outbox)
                except OSError:
                    names = []
                for name in names:
                    if name == "done":
                        continue
                    full = os.path.join(outbox, name)
                    try:
                        with open(full, encoding="utf-8") as fh:
                            text = fh.read()
                    except OSError:
                        continue
                    if "question " in text:
                        found = full
                        break
                if found is None:
                    time.sleep(0.02)
            if found is None:
                return
            time.sleep(0.8)
            try:
                os.remove(found)
            except OSError:
                return
            time.sleep(2.4)
            question = v2.question_for(
                {"protocol_v2": True, "oracle_mode": "deterministic",
                 "v2_answer_deadline_sec": 3},
                {"job_id": job_id, "kind": "exec", "script": "echo ok"})
            folder = os.path.join(self.tmp, "v2", "answers")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, question["msg_id"] + ".json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"received_at": time.time(),
                           "answer": {"answer": "after the send"}}, fh)
            filed["ok"] = True

        thread = threading.Thread(target=watcher)
        thread.start()
        t0 = time.monotonic()
        try:
            sent = process_transport_message(
                dict(self.cfg, protocol_v2=True,
                     oracle_mode="deterministic",
                     v2_answer_deadline_sec=3, transports=["email"]),
                self.tmp, {}, {"": SECRET}, {},
                "[HOMING-PIGEON] job " + job_id,
                _seal(job, job_id))
        finally:
            thread.join(timeout=12)
        self.assertLess(time.monotonic() - t0, 8)
        self.assertTrue(filed["ok"])
        result = next(row for row in sent if "result " + job_id in row[0])
        parsed = verify_body(result[1], SECRET)
        ident = result[0].rsplit(" ", 1)[-1]
        if isinstance(parsed, dict) and isinstance(parsed.get("hp_enc"), dict):
            inner = jobcrypto.decrypt_body(
                parsed, SECRET, ident, parsed.get("key_id") or "")
            parsed = verify_body(inner, SECRET)
        kinds = [(s["kind"], s["text"]) for s in parsed["context"]]
        self.assertIn(("answer", "after the send"), kinds)


class SeenClaimTest(unittest.TestCase):
    def test_a_second_process_cannot_take_a_live_claim(self):
        tmp = tempfile.mkdtemp(prefix="hp-claim-")
        seen = {}
        self.assertTrue(_disk_owns(tmp, "job-1", seen))
        # Pid 1 is init on Linux and usually nobody on Windows, so
        # a claim written as pid 1 was stealable there. Hold a real
        # second process instead.
        other = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            folder = os.path.join(tmp, "inflight")
            name = os.listdir(folder)[0]
            with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                fh.write(f"{other.pid}\n0\njob-1\n")
            held = {}
            self.assertFalse(_disk_owns(tmp, "job-1", held))
        finally:
            other.kill()
            other.wait(timeout=10)
        save_seen(os.path.join(tmp, "seen.json"), {"job-1": True})
        self.assertIn("job-1", load_seen(os.path.join(tmp, "seen.json")))
        third = {}
        self.assertFalse(_disk_owns(tmp, "job-1", third))
        self.assertTrue(third.get("job-1"))

    def _dead_pid(self):
        """A pid that is not a running process.

        Windows rejects signal 0 with WinError 87, so os.kill is
        not a probe there. A pid this high is not in use, and the
        runner asks the process table instead of sending a signal.
        """
        if os.name == "nt":
            return 2 ** 22
        for cand in (999999, 2 ** 20, 2 ** 22):
            try:
                os.kill(cand, 0)
            except ProcessLookupError:
                return cand
            except PermissionError:
                continue
            except OSError:
                return cand
        self.fail("no unused pid")

    def test_a_pid_that_is_not_running_is_not_alive(self):
        self.assertFalse(_pid_alive(None))
        self.assertFalse(_pid_alive(0))
        self.assertFalse(_pid_alive(-3))
        self.assertTrue(_pid_alive(os.getpid()))
        self.assertFalse(_pid_alive(self._dead_pid()))
        if os.name == "nt":
            return
        with mock.patch("os.kill", side_effect=PermissionError):
            self.assertTrue(_pid_alive(4242))
        with mock.patch("os.kill", side_effect=OSError("errno")):
            self.assertFalse(_pid_alive(4242))


    def test_a_dead_claim_that_cannot_be_removed_stays(self):
        tmp = tempfile.mkdtemp(prefix="hp-claim-dead-")
        self.assertTrue(_disk_owns(tmp, "job-1", {}))
        claim = self._claim(tmp, "job-1")
        dead = self._dead_pid()
        with open(claim, "w", encoding="utf-8") as fh:
            fh.write(f"{dead}\n0\njob-1\n")
        real = os.unlink

        def boom(path):
            if path == claim:
                raise OSError("busy")
            return real(path)

        with mock.patch("os.unlink", boom):
            self.assertFalse(_disk_owns(tmp, "job-1", {}))
        self.assertTrue(os.path.exists(claim))

    def test_a_claim_that_cannot_be_created_is_not_ours(self):
        tmp = tempfile.mkdtemp(prefix="hp-claim-open-")
        real = os.open

        def boom(path, flags, mode=0o777, *args, **kwargs):
            if "inflight" in str(path):
                raise OSError("busy")
            return real(path, flags, mode, *args, **kwargs)

        with mock.patch("os.open", boom):
            self.assertFalse(_disk_owns(tmp, "job-2", {}))

    def test_release_does_not_take_someone_elses_claim(self):
        tmp = tempfile.mkdtemp(prefix="hp-claim-rel-")
        self.assertTrue(_disk_owns(tmp, "job-1", {}))
        claim = self._claim(tmp, "job-1")
        _disk_release(tmp, "missing")
        with open(claim, "w", encoding="utf-8") as fh:
            fh.write("1\n0\njob-1\n")
        _disk_release(tmp, "job-1")
        self.assertTrue(os.path.exists(claim))
        with open(claim, "w", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()}\n0\njob-1\n")
        real = os.unlink

        def boom(path):
            if path == claim:
                raise OSError("busy")
            return real(path)

        with mock.patch("os.unlink", boom):
            _disk_release(tmp, "job-1")
        self.assertTrue(os.path.exists(claim))

    def test_save_merges_instead_of_wiping(self):
        tmp = tempfile.mkdtemp(prefix="hp-seen-")
        path = os.path.join(tmp, "seen.json")
        save_seen(path, {"a": True})
        other = {"b": True}
        save_seen(path, other)
        self.assertEqual(set(load_seen(path)), {"a", "b"})
        self.assertIn("a", other)


    def _claim(self, tmp, skey):
        folder = os.path.join(tmp, "inflight")
        name = os.listdir(folder)[0]
        return os.path.join(folder, name)

    def test_our_own_claim_is_not_taken_twice(self):
        tmp = tempfile.mkdtemp(prefix="hp-claim-self-")
        seen = {}
        self.assertTrue(_disk_owns(tmp, "job-1", seen))
        seen["job-1"] = True
        self.assertFalse(_disk_owns(tmp, "job-1", seen))

    def test_a_claim_we_cannot_read_and_cannot_age_is_kept(self):
        tmp = tempfile.mkdtemp(prefix="hp-claim-age-")
        self.assertTrue(_disk_owns(tmp, "job-1", {}))
        claim = self._claim(tmp, "job-1")
        real_open = open
        real_mtime = os.path.getmtime

        def bad_open(path, *args, **kwargs):
            if path == claim:
                raise OSError("unreadable")
            return real_open(path, *args, **kwargs)

        def bad_mtime(path):
            if path == claim:
                raise OSError("no mtime")
            return real_mtime(path)

        with mock.patch("builtins.open", bad_open), \
                mock.patch("os.path.getmtime", bad_mtime):
            self.assertFalse(_disk_owns(tmp, "job-1", {}))
        self.assertTrue(os.path.exists(claim))


class PidAliveWindowsBranchTest(unittest.TestCase):
    """Queue A: _pid_alive's Windows branch (coverage run
    40183585961) -- on Linux the whole ctypes branch is
    platform-inapplicable, and on Windows only its
    failure fallback never ran. The branch is scripted
    here through a stand-in ctypes, so the semantics are
    pinned on every platform: a handle means alive,
    access denied means alive (the process is there),
    any other error means gone, and a probe that cannot
    even run answers alive -- a claim whose owner might
    be alive is never treated as dead.
    """

    def _probe(self, kernel32):
        fake = types.ModuleType("ctypes")
        if kernel32 is not None:
            fake.windll = types.SimpleNamespace(
                kernel32=kernel32)
        with mock.patch.object(os, "name", "nt"), \
                mock.patch.dict(sys.modules,
                                {"ctypes": fake}):
            return _pid_alive(4242)

    def test_a_handle_means_alive(self):
        closed = []
        kernel32 = types.SimpleNamespace(
            OpenProcess=lambda *a: 99,
            CloseHandle=lambda h: closed.append(h),
            GetLastError=lambda: 0)
        self.assertTrue(self._probe(kernel32))
        self.assertEqual(closed, [99])

    def test_access_denied_means_alive_and_other_errors_gone(self):
        kernel32 = types.SimpleNamespace(
            OpenProcess=lambda *a: 0,
            CloseHandle=lambda h: None,
            GetLastError=lambda: 5)
        self.assertTrue(self._probe(kernel32))
        kernel32.GetLastError = lambda: 87
        self.assertFalse(self._probe(kernel32))

    def test_a_probe_that_cannot_run_answers_alive(self):
        # No windll at all (what a non-Windows ctypes
        # looks like): the AttributeError lands in the
        # branch's except, which answers alive.
        self.assertTrue(self._probe(None))



class ReleaseSavedClaimsEdgesTest(unittest.TestCase):
    """Queue A refill: _release_saved_claims' failure
    legs (coverage run 40189711740: lines 6847-6848
    and 6853-6854). At startup the runner releases
    the claims a previous life saved as seen: a claim
    file it cannot read is passed over, and a claim
    file it cannot remove is left -- neither may stop
    the release of the rest.
    """

    def test_unreadable_and_unremovable_claims_are_passed_over(self):
        from runner import runner as RR
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "inflight")
            os.makedirs(folder)
            seen_path = os.path.join(d, "seen.json")

            def claim(name, key):
                p = os.path.join(folder, name)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write("1\n0\n%s\n" % key)
                return p

            gone = claim("a.claim", "k-gone")
            stuck = claim("c.claim", "k-stuck")
            kept = claim("d.claim", "k-not-seen")
            unreadable = os.path.join(folder, "b.claim")
            os.makedirs(unreadable)
            seen = {"k-gone": True, "k-stuck": True}
            real_unlink = os.unlink

            def flaky_unlink(path, *a, **kw):
                if path == stuck:
                    raise OSError("cannot remove")
                return real_unlink(path, *a, **kw)

            with mock.patch.object(RR.os, "unlink", flaky_unlink):
                RR._release_saved_claims(seen_path, seen)
            self.assertFalse(os.path.exists(gone))
            self.assertTrue(os.path.isfile(stuck))
            self.assertTrue(os.path.isfile(kept))
            self.assertTrue(os.path.isdir(unreadable))


class PublishAnswerRaceTest(unittest.TestCase):
    """Queue A refill: _publish_answer's race legs
    (coverage run 40189711740: lines 345, 349-350,
    355). The function's docstring: the first valid
    answer stays; a crash that left a half-written
    path is not an answer -- it is moved aside and
    the slot retried. Two edges the store_answer
    drives cannot reach: the slot vanishing between
    the lost link and the check (the retry then wins
    the slot), and the move-aside itself failing
    (the publisher gives up after its attempts and
    reports False, the bad file untouched).
    """

    def _pair(self, d):
        tmp = os.path.join(d, "answer.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write('{"answer": {}}')
        return tmp, os.path.join(d, "q.j1.json")

    def test_a_vanished_slot_is_retried_and_won(self):
        with tempfile.TemporaryDirectory() as d:
            tmp, path = self._pair(d)
            real_link = os.link
            calls = []

            def flaky_link(src, dst):
                calls.append(1)
                if len(calls) == 1:
                    raise OSError("lost the race")
                return real_link(src, dst)

            with mock.patch.object(v2.os, "link", flaky_link):
                self.assertTrue(v2._publish_answer(path, tmp))
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), '{"answer": {}}')

    def test_a_move_aside_that_fails_gives_up(self):
        with tempfile.TemporaryDirectory() as d:
            tmp, path = self._pair(d)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{")  # a half-written non-answer
            with mock.patch.object(
                    v2.os, "rename",
                    side_effect=OSError("cannot move it")):
                self.assertFalse(v2._publish_answer(path, tmp))
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "{")


class RememberOtherLegsTest(unittest.TestCase):
    """Queue A refill: _remember_other's blank
    answer (coverage run 40189711740: lines
    399-400) and store_answer's temp-cleanup
    swallow (387-388). A second answer with no
    text is not kept beside the first -- there
    is nothing to show -- and a temp file that
    cannot be removed does not fail the store.
    """

    def test_a_blank_second_answer_is_not_kept(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "q1.json")
            v2._remember_other(path, {"answer": "   "})
            self.assertFalse(
                os.path.exists(path + ".more.jsonl"))
            v2._remember_other(path, {"answer": "late one"})
            self.assertTrue(
                os.path.exists(path + ".more.jsonl"))

    def test_store_answer_survives_an_unremovable_temp(self):
        q = {"v": 2, "type": "question", "job_id": "j1",
             "msg_id": "q.j1", "issued_at": _now(),
             "deadline_sec": 0, "question": "Would it?",
             "local_default": "proceed"}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(
                    os, "unlink",
                    side_effect=OSError("stuck")):
            self.assertTrue(
                v2.store_answer(d, v2.answer_for(q, "first")))


class Version2EdgesTest(unittest.TestCase):
    """The branches a normal-length id and one late answer never touch."""

    def _q(self, job_id="j1"):
        return {"v": 2, "type": "question", "job_id": job_id,
                "msg_id": "q." + job_id, "issued_at": _now(),
                "deadline_sec": 0, "question": "Would it?",
                "local_default": "proceed"}

    def test_ids_past_128_characters_do_not_share_a_slot(self):
        # "q." plus a 128-character id is 130, so the id is hashed.
        # The first 109 characters of these two are the same. The
        # tail is what used to be cut off.
        cfg = {"protocol_v2": True, "oracle_mode": "deterministic"}
        left = "a" * 124 + "LEFT"
        right = "a" * 124 + "RGHT"
        self.assertEqual(len(left), 128)
        one = v2.question_for(cfg, {"job_id": left, "kind": "exec"})
        two = v2.question_for(cfg, {"job_id": right, "kind": "exec"})
        self.assertNotEqual(one["msg_id"], two["msg_id"])
        self.assertLessEqual(len(one["msg_id"]), 128)
        self.assertNotIn("LEFT", one["msg_id"])
        self.assertNotIn("RGHT", two["msg_id"])
        v2.validate(one)

    def test_the_ninth_answer_and_a_repeat_are_dropped(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-more-")
        q = self._q()
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "winner")))
        for i in range(8):
            self.assertFalse(v2.store_answer(
                tmp, v2.answer_for(q, "late-%d" % i)))
        self.assertFalse(v2.store_answer(
            tmp, v2.answer_for(q, "late-0")))
        self.assertFalse(v2.store_answer(
            tmp, v2.answer_for(q, "ninth-extra")))
        more = os.path.join(tmp, "v2", "answers", "q.j1.json.more.jsonl")
        with open(more, encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().splitlines()), 8)
        with open(more, "a", encoding="utf-8") as fh:
            fh.write("not-json\n")
            fh.write("{}\n")
        got = v2.await_answer(tmp, q, time.time())
        late = [s["text"] for s in got if s["kind"] == "late_answer"]
        self.assertEqual(late, ["late-%d" % i for i in range(8)])
        self.assertNotIn("ninth-extra", late)

    def test_a_late_file_that_cannot_be_opened_is_skipped(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-more-")
        q = self._q()
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "winner")))
        self.assertFalse(v2.store_answer(tmp, v2.answer_for(q, "second")))
        more = os.path.join(tmp, "v2", "answers", "q.j1.json.more.jsonl")
        os.remove(more)
        os.mkdir(more)
        self.assertFalse(v2.store_answer(tmp, v2.answer_for(q, "third")))
        got = v2.await_answer(tmp, q, time.time())
        self.assertEqual(
            [s["kind"] for s in got], ["answer"])

    def test_shapes_that_are_not_messages(self):
        self.assertIsNone(v2.subject_kind(None))
        self.assertEqual(v2.segment("x", "k", None)["text"], "")
        self.assertEqual(v2.local_answer_text("nope"), "proceed")
        self.assertEqual(v2.local_answer_text(
            {"local_default": "  wait  "}), "wait")
        self.assertEqual(v2.deadline_of(None), 0)
        self.assertEqual(v2.deadline_of(
            {"v2_answer_deadline_sec": "nope"}), 0)
        self.assertEqual(v2.outbound_for(
            {"protocol_v2": True}, None, None), [])
        det = v2.determination_for(
            {"job_id": "j1"}, {"findings": ["nope", {"detail": 3}]})
        self.assertEqual(det["why"], "expected trouble")
        det = v2.determination_for(
            {"job_id": "j1"}, {"repair_action": {"a": 1}})
        self.assertEqual(det["expect"], "unknown")
        cfg = {"protocol_v2": True, "oracle_mode": "deterministic"}
        q = v2.question_for(cfg, {"job_id": "j1", "kind": "exec",
                                  "script": ""})
        self.assertNotIn("script=", q["question"])
        q = v2.question_for(cfg, {"job_id": "j1", "kind": "exec",
                                  "script": 3})
        self.assertNotIn("script=", q["question"])
        blank = v2.answer_for(self._q(), "   ")
        self.assertEqual(blank["answer"], "proceed")
        with self.assertRaises(ValueError):
            v2.answer_for([], "x")
        with self.assertRaises(ValueError):
            v2.validate([])
        with self.assertRaises(ValueError):
            v2.validate({"v": 2, "type": "nope"})
        base = {"v": 2, "type": "determination", "job_id": "j1",
                "msg_id": "d.j1", "issued_at": "2026-10-22T00:00:00Z",
                "clean_pass": False, "expect": "fail", "why": "because"}
        v2.validate(base)
        for bad in (dict(base, issued_at="nope"),
                    dict(base, clean_pass=True),
                    dict(base, expect="maybe"),
                    dict(base, why=""),
                    dict(base, why="x" * 501)):
            with self.assertRaises(ValueError):
                v2.validate(bad)
        question = self._q()
        v2.validate(question)
        for bad in (dict(question, question="  "),
                    dict(question, deadline_sec=True),
                    dict(question, deadline_sec=99),
                    dict(question, local_default=""),
                    dict(question, local_default="x" * 65)):
            with self.assertRaises(ValueError):
                v2.validate(bad)
        ans = v2.answer_for(question, "ok")
        with self.assertRaises(ValueError):
            v2.validate(dict(ans, answer="  "))
        with self.assertRaises(ValueError):
            v2.store_answer(tempfile.mkdtemp(prefix="hp-v2-"), question)

    def test_a_bad_question_does_not_wait(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        self.assertEqual(v2.await_answer(tmp, None, 0), [])
        self.assertEqual(v2.await_answer(tmp, {"msg_id": "bad id"}, 0), [])

        def boom():
            raise RuntimeError("pump")

        q = self._q()
        q["deadline_sec"] = True
        got = v2.await_answer(tmp, q, "not-a-time", pump=boom)
        self.assertEqual(got[0]["kind"], "local_default")

    def test_a_raising_outbox_does_not_hold_the_job(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-")
        calls = {"n": 0}

        def pending():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("outbox")
            return False

        q = self._q()
        q["deadline_sec"] = 1
        started = time.monotonic()
        got = v2.await_answer(tmp, q, time.time(), pending=pending)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(got[0]["kind"], "local_default")
        self.assertGreaterEqual(calls["n"], 1)

    def test_a_ping_still_sends_the_determination_only(self):
        job = {"job_id": "j1", "kind": "ping"}
        plan = {"findings": [{"detail": "missing"}]}
        out = v2.outbound_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            job, plan)
        self.assertEqual([obj["type"] for _s, obj in out], ["determination"])
        self.assertEqual(v2.local_answer_text({"local_default": 5}), "proceed")
        self.assertEqual(v2.local_answer_text(
            {"local_default": "   "}), "proceed")

    def test_a_garbage_line_in_the_late_file_is_skipped_on_write(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-more-")
        q = self._q()
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "winner")))
        self.assertFalse(v2.store_answer(tmp, v2.answer_for(q, "second")))
        more = os.path.join(tmp, "v2", "answers", "q.j1.json.more.jsonl")
        with open(more, "a", encoding="utf-8") as fh:
            fh.write("not-json\n")
            fh.write("[]\n")
        self.assertFalse(v2.store_answer(tmp, v2.answer_for(q, "third")))
        with open(more, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertIn("third", lines[-1])

    def test_an_unreadable_slot_does_not_keep_the_answer(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-slot-")
        q = self._q()
        folder = os.path.join(tmp, "v2", "answers")
        os.makedirs(folder)
        slot = os.path.join(folder, "q.j1.json")
        os.mkdir(slot)
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "recovered")))
        with open(slot, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["answer"]["answer"], "recovered")

    def test_a_file_that_is_not_an_answer_does_not_hold_the_slot(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-bad-")
        q = self._q()
        folder = os.path.join(tmp, "v2", "answers")
        os.makedirs(folder)
        slot = os.path.join(folder, "q.j1.json")
        for junk in ("[]", '{"answer": "x", "received_at": 1}',
                     '{"answer": {}, "received_at": "nope"}'):
            with open(slot, "w", encoding="utf-8") as fh:
                fh.write(junk)
            self.assertTrue(v2.store_answer(
                tmp, v2.answer_for(q, "taken")))
            with open(slot, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["answer"]["answer"], "taken")

    def test_an_answer_already_waiting_ends_the_outbox_pause(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-pending-")
        q = self._q()
        q["deadline_sec"] = 5
        self.assertTrue(v2.store_answer(tmp, v2.answer_for(q, "early")))
        started = time.monotonic()
        got = v2.await_answer(tmp, q, time.time(), pending=lambda: True)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(got[0]["text"], "early")
        self.assertEqual(got[0]["kind"], "answer")

    def test_a_directory_in_the_answer_slot_is_moved_aside(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-dir-")
        q = self._q()
        obj = v2.answer_for(q, "yes")
        _folder, path = v2._answer_path(tmp, obj["question_id"])
        os.makedirs(path)
        self.assertTrue(v2.store_answer(tmp, obj))
        self.assertTrue(os.path.isfile(path))
        more = path + ".more.jsonl"
        with open(more, "w", encoding="utf-8") as fh:
            fh.write("not-json\n")
            fh.write("[]\n")
            fh.write(json.dumps({"answer": ""}) + "\n")
            fh.write(json.dumps({"answer": "yes"}) + "\n")
            fh.write(json.dumps({"answer": "later"}) + "\n")
        self.assertEqual(
            v2._other_answers(tmp, obj["question_id"], "yes"),
            ["later"])

    def test_an_empty_outbox_starts_the_deadline(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-empty-")
        q = self._q()
        q["deadline_sec"] = 30
        start = time.monotonic()
        jumps = {"n": 0}

        def mono():
            jumps["n"] += 1
            if jumps["n"] < 8:
                return start
            return start + 100

        with mock.patch("runner.wire.protocol_v2.time.monotonic", mono):
            got = v2.await_answer(
                tmp, q, time.time(), pending=lambda: False)
        self.assertEqual(got[0]["kind"], "local_default")


class AwaitAnswerNonStringLegTest(unittest.TestCase):
    """Queue A refill: await_answer's
    classification of a non-string answer
    (coverage run 40189711740:
    protocol_v2.py line 514). An answer whose
    text member is not a string rides as an
    empty answer -- the segment shape holds;
    the nonsense does not reach the result.
    """

    def test_a_non_string_answer_rides_empty(self):
        tmp = tempfile.mkdtemp(prefix="hp-v2-nonstr-")
        folder = os.path.join(tmp, "v2", "answers")
        os.makedirs(folder)
        with open(os.path.join(folder, "q.j1.json"),
                  "w", encoding="utf-8") as fh:
            json.dump({"received_at": time.time() - 5,
                       "answer": {"answer": 42}}, fh)
        q = {"msg_id": "q.j1", "deadline_sec": 0,
             "local_default": "proceed"}
        got = v2.await_answer(tmp, q, time.time())
        self.assertEqual(got[0]["kind"], "answer")
        self.assertEqual(got[0]["text"], "")


if __name__ == "__main__":
    unittest.main()
