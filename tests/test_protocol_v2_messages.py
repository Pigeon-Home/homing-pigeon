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
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

from runner import jobcrypto  # noqa: E402
from runner import protocol_v2 as v2  # noqa: E402
from runner.runner import (  # noqa: E402
    poll_once, process_transport_message, sign_payload, verify_body)
from tests.security_parity import SECRET, FakeIMAP, FakeSMTP  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
