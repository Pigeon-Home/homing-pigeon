#!/usr/bin/env python3
"""Heavy coverage for the local SI harness. No live model, no network.

These are more tests than a feature this size would normally get.
The point is to pin the two-instance contract: SI and Oracle stay
separate, signing works, rejections are clean, and the browser
handler routes correctly.
"""
import json
import os
import sys
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import local_test as LT
from runner.runner import sign_payload, verify_body

SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


class BuildAskJobTest(unittest.TestCase):
    def test_kind_is_ping(self):
        job = LT.build_ask_job("q", SECRET)
        self.assertEqual(job["kind"], "ping")

    def test_has_sig(self):
        job = LT.build_ask_job("q", SECRET)
        self.assertIn("sig", job)
        self.assertEqual(len(job["sig"]), 96)

    def test_query_op_is_ask(self):
        job = LT.build_ask_job("why?", SECRET)
        self.assertEqual(job["result_policy"]["queries"][0]["op"], "ask")

    def test_question_preserved(self):
        job = LT.build_ask_job("why did it fail?", SECRET)
        self.assertEqual(
            job["result_policy"]["queries"][0]["question"], "why did it fail?"
        )

    def test_view_is_attested(self):
        job = LT.build_ask_job("q", SECRET)
        self.assertEqual(job["result_policy"]["view"], "attested")

    def test_budget_is_set(self):
        job = LT.build_ask_job("q", SECRET)
        self.assertEqual(job["result_policy"]["query_budget"], 4)

    def test_job_id_generated(self):
        a = LT.build_ask_job("q", SECRET)
        b = LT.build_ask_job("q", SECRET)
        self.assertNotEqual(a["job_id"], b["job_id"])

    def test_job_id_respected(self):
        job = LT.build_ask_job("q", SECRET, job_id="fixed-id")
        self.assertEqual(job["job_id"], "fixed-id")

    def test_issued_at_present(self):
        job = LT.build_ask_job("q", SECRET)
        self.assertIn("T", job["issued_at"])
        self.assertTrue(job["issued_at"].endswith("Z"))

    def test_roundtrip_verify(self):
        job = LT.build_ask_job("hello", SECRET)
        signed = sign_payload({k: v for k, v in job.items() if k != "sig"}, SECRET)
        got = verify_body(signed, SECRET)
        self.assertEqual(got["result_policy"]["queries"][0]["question"], "hello")

    def test_unicode_question(self):
        job = LT.build_ask_job("why? パスワード", SECRET)
        self.assertIn("パスワード", job["result_policy"]["queries"][0]["question"])

    def test_empty_question_still_signed(self):
        job = LT.build_ask_job("", SECRET)
        self.assertIn("sig", job)
        self.assertEqual(job["result_policy"]["queries"][0]["question"], "")

    def test_long_question(self):
        q = "x" * 5000
        job = LT.build_ask_job(q, SECRET)
        self.assertEqual(len(job["result_policy"]["queries"][0]["question"]), 5000)

    def test_max_chars_default(self):
        job = LT.build_ask_job("q", SECRET)
        self.assertEqual(job["result_policy"]["queries"][0]["max_chars"], 500)


class AnswerAsOracleTest(unittest.TestCase):
    def test_unconfigured_rejects(self):
        self.assertEqual(LT.answer_as_oracle({}, "q").get("rejected"),
                         "inference_unconfigured")

    def test_missing_model_rejects(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1"}}
        self.assertEqual(LT.answer_as_oracle(cfg, "q").get("rejected"),
                         "inference_unconfigured")

    def test_non_loopback_rejects(self):
        cfg = {"inference": {"endpoint": "http://evil.example/v1", "model": "m"}}
        self.assertEqual(LT.answer_as_oracle(cfg, "q").get("rejected"),
                         "inference_unconfigured")

    def test_empty_cfg_rejects(self):
        self.assertIn("rejected", LT.answer_as_oracle({}, ""))

    def test_none_like_missing_inference(self):
        self.assertEqual(
            LT.answer_as_oracle({"inference": None}, "q").get("rejected"),
            "inference_unconfigured",
        )


class SIInstanceTest(unittest.TestCase):
    def test_si_system_mentions_separate(self):
        self.assertIn("different model", LT.SI_SYSTEM)
        self.assertIn("Oracle", LT.SI_SYSTEM)

    def test_si_port_is_not_oracle_port(self):
        self.assertNotEqual(LT.SI_PORT, LT.ORACLE_PORT)
        self.assertEqual(LT.SI_PORT, 11435)
        self.assertEqual(LT.ORACLE_PORT, 11434)

    def test_port_up_false_on_closed(self):
        self.assertFalse(LT._port_up(1))  # privileged, almost certainly closed

    def test_start_si_already_up(self):
        with mock.patch.object(LT, "_port_up", return_value=True):
            self.assertTrue(LT.start_si_instance())

    def test_start_si_no_ollama(self):
        with mock.patch.object(LT, "_port_up", return_value=False), \
             mock.patch("shutil.which", return_value=None):
            self.assertFalse(LT.start_si_instance())

    def test_start_si_becomes_ready(self):
        calls = {"n": 0}

        def up(port):
            calls["n"] += 1
            return calls["n"] > 2

        with mock.patch.object(LT, "_port_up", side_effect=up), \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.Popen") as popen, \
             mock.patch("time.sleep"):
            self.assertTrue(LT.start_si_instance())
            env = popen.call_args.kwargs.get("env") or popen.call_args[1].get("env")
            self.assertIn("11435", env["OLLAMA_HOST"])

    def test_start_si_times_out(self):
        with mock.patch.object(LT, "_port_up", return_value=False), \
             mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
             mock.patch("subprocess.Popen"), \
             mock.patch("time.sleep"):
            self.assertFalse(LT.start_si_instance())


class AskSITest(unittest.TestCase):
    def _fake_urlopen(self, content):
        class Resp:
            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": content}}]}
                ).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        return Resp()

    def test_ask_si_returns_content(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=self._fake_urlopen("si says hi")):
            self.assertEqual(LT.ask_si("m", [], "hello"), "si says hi")

    def test_ask_si_includes_system_and_history(self):
        captured = {}

        class Resp:
            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=120):
            captured["body"] = json.loads(req.data.decode())
            captured["url"] = req.full_url
            return Resp()

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            LT.ask_si("llama3.2:3b",
                      [{"role": "user", "content": "earlier"}],
                      "now")
        msgs = captured["body"]["messages"]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("cloud SI", msgs[0]["content"])
        self.assertEqual(msgs[1]["content"], "earlier")
        self.assertEqual(msgs[-1]["content"], "now")
        self.assertIn("11435", captured["url"])

    def test_ask_si_uses_given_model(self):
        captured = {}

        class Resp:
            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=120):
            captured["body"] = json.loads(req.data.decode())
            return Resp()

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            LT.ask_si("custom-model", [], "q")
        self.assertEqual(captured["body"]["model"], "custom-model")


class MainDispatchTest(unittest.TestCase):
    def test_main_unconfigured_returns_2(self):
        self.assertEqual(LT.main({}, browser=False), 2)

    def test_main_browser_starts_si(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with mock.patch.object(LT.R, "ensure_inference_ready"), \
             mock.patch.object(LT.R, "update_llama_from_config"), \
             mock.patch.object(LT.R, "inference_config", return_value={"model": "m"}), \
             mock.patch.object(LT, "browser_chat", return_value=0) as bc:
            self.assertEqual(LT.main(cfg, browser=True), 0)
            bc.assert_called_once()

    def test_main_terminal_calls_repl(self):
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}}
        with mock.patch.object(LT.R, "ensure_inference_ready"), \
             mock.patch.object(LT.R, "update_llama_from_config"), \
             mock.patch.object(LT.R, "inference_config", return_value={"model": "m"}), \
             mock.patch.object(LT, "repl", return_value=0) as repl:
            self.assertEqual(LT.main(cfg, browser=False), 0)
            repl.assert_called_once()


class ConcurrencyTest(unittest.TestCase):
    def test_many_signed_jobs_are_unique(self):
        ids = []
        lock = threading.Lock()

        def one():
            job = LT.build_ask_job("q", SECRET)
            with lock:
                ids.append(job["job_id"])

        threads = [threading.Thread(target=one) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)

    def test_concurrent_oracle_rejects_stay_clean(self):
        results = []
        lock = threading.Lock()

        def one():
            ans = LT.answer_as_oracle({}, "q")
            with lock:
                results.append(ans.get("rejected"))

        threads = [threading.Thread(target=one) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results, ["inference_unconfigured"] * 12)


class BrowserBindTest(unittest.TestCase):
    def test_browser_refuses_if_si_wont_start(self):
        with mock.patch.object(LT, "start_si_instance", return_value=False):
            self.assertEqual(LT.browser_chat({}), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
