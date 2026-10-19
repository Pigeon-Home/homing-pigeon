"""Dark branches of the local SI harness.

No live model, no SMTP, and no browser process. The package-import
fallback is reached by reloading under a guarded __import__, then the
module is reloaded cleanly so later tests still see the package.
"""
import importlib
import io
import json
import os
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import local_test as LT  # noqa: E402

SECRET = "0123456789abcdef" * 4


def _resume_coverage_tracer():
    """Put coverage's tracer back after the fuzz tests drop it.

    test_fuzz_guided installs its own sys.settrace and some cases
    clear it with settrace(None). Coverage's C tracer does not come
    back on its own, so a full-suite run stops recording this file
    before these tests execute. Re-arm the same tracer object.
    """
    try:
        import coverage
    except ImportError:
        return
    cov = coverage.Coverage.current()
    if cov is None:
        return
    collector = getattr(cov, "_collector", None)
    tracers = getattr(collector, "tracers", None) or []
    if not tracers:
        return
    tracers[-1].start()


def setUpModule():
    _resume_coverage_tracer()


def _cfg():
    return {
        "shared_secret": SECRET,
        "inference": {
            "endpoint": "http://127.0.0.1:9/v1",
            "model": "m",
        },
    }


def _reply(content):
    raw = json.dumps(
        {"choices": [{"message": {"content": content}}]}
    ).encode()

    class Resp:
        def read(self):
            return raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return Resp()


class ImportFallbackTest(unittest.TestCase):
    def test_the_script_import_is_the_fallback(self):
        import builtins
        real = builtins.__import__
        runner_dir = os.path.dirname(os.path.abspath(LT.__file__))
        before = sys.path.count(runner_dir)

        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "runner" and fromlist:
                raise ImportError("script")
            return real(name, globals, locals, fromlist, level)

        try:
            with mock.patch("builtins.__import__", guarded):
                importlib.reload(LT)
            self.assertTrue(callable(LT.repl))
            self.assertGreater(sys.path.count(runner_dir), before)
        finally:
            try:
                importlib.reload(LT)
            finally:
                while sys.path.count(runner_dir) > before:
                    sys.path.remove(runner_dir)
        import runner
        self.assertTrue(hasattr(runner, "__path__"))
        self.assertTrue(callable(LT.R.sign_payload))


class PortUpTest(unittest.TestCase):
    def test_an_open_port_is_up(self):
        sock = mock.Mock()
        with mock.patch("socket.socket", return_value=sock):
            self.assertTrue(LT._port_up(9))
        sock.settimeout.assert_called_once_with(0.5)
        sock.connect.assert_called_once_with(("127.0.0.1", 9))
        sock.close.assert_called_once()

    def test_a_closed_port_is_down(self):
        sock = mock.Mock()
        sock.connect.side_effect = OSError("closed")
        with mock.patch("socket.socket", return_value=sock):
            self.assertFalse(LT._port_up(9))
        sock.close.assert_called_once()


class StartSiPathsTest(unittest.TestCase):
    def test_already_listening_does_not_spawn(self):
        with mock.patch.object(LT, "_port_up", return_value=True), \
                mock.patch("subprocess.Popen") as popen, \
                redirect_stdout(io.StringIO()):
            self.assertTrue(LT.start_si_instance())
        popen.assert_not_called()

    def test_missing_ollama_returns_false(self):
        with mock.patch.object(LT, "_port_up", return_value=False), \
                mock.patch("shutil.which", return_value=None), \
                redirect_stdout(io.StringIO()):
            self.assertFalse(LT.start_si_instance())

    def test_popen_failure_returns_false(self):
        with mock.patch.object(LT, "_port_up", return_value=False), \
                mock.patch("shutil.which", return_value="ollama"), \
                mock.patch("subprocess.Popen", side_effect=OSError("no")), \
                redirect_stdout(io.StringIO()):
            self.assertFalse(LT.start_si_instance())

    def test_instance_becomes_ready(self):
        with mock.patch.object(LT, "_port_up", side_effect=[False, True]), \
                mock.patch("shutil.which", return_value="ollama"), \
                mock.patch("subprocess.Popen") as popen, \
                mock.patch("time.sleep"), \
                redirect_stdout(io.StringIO()):
            self.assertTrue(LT.start_si_instance())
        env = popen.call_args.kwargs["env"]
        self.assertIn("11435", env["OLLAMA_HOST"])

    def test_instance_never_becomes_ready(self):
        with mock.patch.object(LT, "_port_up", return_value=False), \
                mock.patch("shutil.which", return_value="ollama"), \
                mock.patch("subprocess.Popen"), \
                mock.patch("time.sleep") as sleep, \
                redirect_stdout(io.StringIO()):
            self.assertFalse(LT.start_si_instance())
        self.assertEqual(sleep.call_count, 20)


class StartSiImportTest(unittest.TestCase):
    def test_install_import_falls_back_to_the_script(self):
        import builtins
        real = builtins.__import__
        fake = types.ModuleType("install")
        seen = {}

        def daemon_popen_kwargs(windows):
            seen["windows"] = windows
            return {"_fallback": True}

        fake.daemon_popen_kwargs = daemon_popen_kwargs
        previous = sys.modules.get("install")

        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "runner.install":
                raise ImportError("script")
            return real(name, globals, locals, fromlist, level)

        sys.modules["install"] = fake
        try:
            with mock.patch("builtins.__import__", guarded), \
                    mock.patch.object(
                        LT, "_port_up", side_effect=[False, True]), \
                    mock.patch("shutil.which", return_value="ollama"), \
                    mock.patch("subprocess.Popen") as popen, \
                    mock.patch("time.sleep"), \
                    redirect_stdout(io.StringIO()):
                ok = LT.start_si_instance()
        finally:
            if previous is None:
                sys.modules.pop("install", None)
            else:
                sys.modules["install"] = previous
        self.assertTrue(ok)
        self.assertIn("windows", seen)
        self.assertTrue(popen.call_args.kwargs.get("_fallback"))


class AskSiGapTest(unittest.TestCase):
    def test_a_non_list_history_is_dropped(self):
        captured = {}

        def urlopen(req, timeout=120):
            captured["body"] = json.loads(req.data.decode())
            return _reply("ok")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            self.assertEqual(LT.ask_si("m", {"not": "a list"}, "q"), "ok")
        roles = [m["role"] for m in captured["body"]["messages"]]
        self.assertEqual(roles, ["system", "user"])

    def test_a_non_string_reply_is_stringified(self):
        with mock.patch(
                "urllib.request.urlopen", return_value=_reply(7)):
            self.assertEqual(LT.ask_si("m", [], "q"), "7")

    def test_an_unencodable_history_returns_empty(self):
        history = [{"role": "user", "content": {1, 2}}]
        self.assertEqual(LT.ask_si("m", history, "q"), "")

    def test_an_http_error_returns_empty(self):
        with mock.patch(
                "urllib.request.urlopen", side_effect=OSError("down")):
            self.assertEqual(LT.ask_si("m", [], "q"), "")


class AnswerGapTest(unittest.TestCase):
    def test_a_signature_failure_is_rejected(self):
        with mock.patch.object(
                LT.R, "verify_body", side_effect=ValueError("mismatch")):
            ans = LT.answer_as_oracle(_cfg(), "hello")
        self.assertEqual(ans, {"rejected": "signature: mismatch"})

    def test_queries_that_are_not_a_list_have_no_answers(self):
        verified = {"result_policy": {"queries": "ask"}}
        with mock.patch.object(LT.R, "verify_body", return_value=verified):
            ans = LT.answer_as_oracle(_cfg(), "hello")
        self.assertEqual(ans, {"rejected": "no_queries"})

    def test_an_empty_answer_list_is_rejected(self):
        with mock.patch.object(
                LT.R, "answer_queries", return_value=([], 0)):
            ans = LT.answer_as_oracle(_cfg(), "hello")
        self.assertEqual(ans, {"rejected": "no_queries"})


class ReplGapTest(unittest.TestCase):
    def _run(self, cfg, lines):
        queued = iter(lines)

        def fake_input(prompt=""):
            try:
                return next(queued)
            except StopIteration:
                raise EOFError

        buf = io.StringIO()
        with mock.patch("builtins.input", side_effect=fake_input), \
                redirect_stdout(buf):
            code = LT.repl(cfg)
        return code, buf.getvalue()

    def test_instructions_blank_answer_reject_and_quit(self):
        answers = iter([{"answer": "fine"}, {"rejected": "no"}])

        def answer(cfg, question):
            return next(answers)

        cfg = {"owner_instructions": "I" * 200}
        with mock.patch.object(LT, "answer_as_oracle", side_effect=answer):
            code, out = self._run(cfg, ["", "hello", "bad", "quit"])
        self.assertEqual(code, 0)
        self.assertIn("I" * 120, out)
        self.assertNotIn("I" * 121, out)
        self.assertIn("Oracle> fine", out)
        self.assertIn("Oracle> rejected: no", out)

    def test_eof_returns_zero(self):
        code, out = self._run({}, [])
        self.assertEqual(code, 0)
        self.assertIn("local SI test", out)
        self.assertNotIn("owner instructions", out)

    def test_keyboard_interrupt_returns_zero(self):
        def fake_input(prompt=""):
            raise KeyboardInterrupt

        buf = io.StringIO()
        with mock.patch("builtins.input", side_effect=fake_input), \
                redirect_stdout(buf):
            code = LT.repl({})
        self.assertEqual(code, 0)


class BrowserGapTest(unittest.TestCase):
    def test_open_webui_follows_which(self):
        with mock.patch("shutil.which", return_value="/bin/open-webui"):
            self.assertTrue(LT._open_webui_available())
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(LT._open_webui_available())

    def test_a_spawn_error_returns_1(self):
        with mock.patch.object(LT, "start_si_instance", return_value=True), \
                mock.patch.object(
                    LT, "_open_webui_available", return_value=True), \
                mock.patch(
                    "subprocess.Popen", side_effect=OSError("missing")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(LT.browser_chat({}), 1)

    def test_interrupt_terminates_the_chat(self):
        proc = mock.Mock()
        proc.wait.side_effect = KeyboardInterrupt
        with mock.patch.object(LT, "start_si_instance", return_value=True), \
                mock.patch.object(
                    LT, "_open_webui_available", return_value=True), \
                mock.patch("subprocess.Popen", return_value=proc), \
                mock.patch.object(LT.webbrowser, "open"), \
                mock.patch.object(LT.threading, "Timer"), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(LT.browser_chat({}), 0)
        proc.terminate.assert_called_once()

    def test_a_ready_chat_opens_the_browser(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        opened = []

        class Now:
            def __init__(self, delay, fn):
                self.fn = fn

            def start(self):
                self.fn()

        with mock.patch.object(LT, "start_si_instance", return_value=True), \
                mock.patch.object(
                    LT, "_open_webui_available", return_value=True), \
                mock.patch("subprocess.Popen", return_value=proc), \
                mock.patch.object(LT.threading, "Timer", Now), \
                mock.patch.object(
                    LT.webbrowser, "open", side_effect=opened.append), \
                redirect_stdout(io.StringIO()):
            code = LT.browser_chat({}, port=9090)
        self.assertEqual(code, 0)
        self.assertEqual(opened, ["http://127.0.0.1:9090/"])
        proc.terminate.assert_not_called()
        self.assertEqual(proc.wait.call_count, 1)


class EmailGapTest(unittest.TestCase):
    def test_no_secret(self):
        self.assertIn("shared_secret", LT.send_via_email({}, "q"))

    def test_a_quit_error_is_ignored(self):
        class SMTP:
            def quit(self):
                raise OSError("bye")

        with mock.patch.object(LT.R, "connect_smtp", return_value=SMTP()), \
                mock.patch.object(LT.R, "send_mail"):
            status = LT.send_via_email(_cfg(), "why?")
        self.assertTrue(status.startswith("emailed job "))

    def test_a_send_error_is_reported(self):
        smtp = mock.Mock()
        with mock.patch.object(LT.R, "connect_smtp", return_value=smtp), \
                mock.patch.object(
                    LT.R, "send_mail", side_effect=OSError("no")):
            status = LT.send_via_email(_cfg(), "why?")
        self.assertIn("email send failed", status)
        self.assertIn("no", status)
        smtp.quit.assert_called_once()


class MainGuardTest(unittest.TestCase):
    def test_unconfigured_main_returns_2(self):
        with mock.patch.object(LT.R, "ensure_inference_ready"), \
                mock.patch.object(LT.R, "update_llama_from_config"), \
                mock.patch.object(
                    LT.R, "inference_config", return_value=None), \
                redirect_stdout(io.StringIO()) as buf:
            code = LT.main({}, browser=False)
        self.assertEqual(code, 2)
        self.assertIn("not configured", buf.getvalue())

    def test_main_opens_the_browser_or_the_repl(self):
        ready = {"model": "m"}
        with mock.patch.object(LT.R, "ensure_inference_ready"), \
                mock.patch.object(LT.R, "update_llama_from_config"), \
                mock.patch.object(
                    LT.R, "inference_config", return_value=ready), \
                mock.patch.object(LT, "browser_chat", return_value=0) as bc, \
                mock.patch.object(LT, "repl", return_value=0) as repl:
            self.assertEqual(LT.main(_cfg(), browser=True), 0)
            self.assertEqual(LT.main(_cfg(), browser=False), 0)
        bc.assert_called_once()
        repl.assert_called_once()

    def test_running_the_file_as_main_exits_2(self):
        import runpy
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(LT.__file__, run_name="__main__")
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--local-test", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
