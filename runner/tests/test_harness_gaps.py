"""The diagnose harness branches the happy-path tests never take.

No live IMAP, SMTP, or model. Each of those is a stand-in
that answers the way a broken or a half-configured box does.
"""
import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import harness as H  # noqa: E402
from runner import runner as R  # noqa: E402

SECRET = ("9f2c41aa07b3e5d80192f4a6b8c3d5e7"
          "f0a1b2c3d4e5f60718293a4b5c6d7e8f")


def _cfg(**over):
    cfg = {
        "shared_secret": SECRET,
        "mailbox_user": "runner@example.com",
        "mailbox_password": "secret-value",
        "imap_host": "imap.example.com",
        "smtp_host": "smtp.example.com",
        "inference": {"endpoint": "http://127.0.0.1:11434/v1",
                      "model": "llama3.2:3b"},
    }
    cfg.update(over)
    return cfg


def _ctx(cfg, base, timeout=2):
    return {"cfg": cfg, "base_dir": base, "cfg_path": None,
            "roundtrip_timeout": timeout, "context": None,
            "retained_count": 0}


def _sec(name, fn, cfg, base, timeout=2):
    return H._run_section(name, fn, _ctx(cfg, base, timeout),
                          lambda _line: None)


class EntropyFallbackTest(unittest.TestCase):
    def test_the_formula_is_used_when_the_estimator_cannot_answer(self):
        def boom(_secret):
            raise RuntimeError("down")

        with mock.patch.object(R, "_estimate_secret_entropy", boom):
            self.assertAlmostEqual(H.estimate_entropy_bits("ab" * 32), 64.0)
        with mock.patch.object(R, "_estimate_secret_entropy", "no"):
            self.assertEqual(H.estimate_entropy_bits(None), 0.0)
            self.assertEqual(H.estimate_entropy_bits("a"), 0.0)


class ConfigEdgesTest(unittest.TestCase):
    def test_oauth_and_a_refused_endpoint_are_named(self):
        cfg = _cfg(auth="oauth", mailbox_password=None,
                   inference={"endpoint": "http://example.com/v1",
                              "model": "m"})
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    R, "validate_shared_secret",
                    side_effect=ValueError("weak")):
                bad = _sec("config", H._sec_config, cfg, d)
            self.assertEqual(bad.status, H.FAIL)
            self.assertIn("entropy gate", bad.summary)
            good = _sec("config", H._sec_config, cfg, d)
        text = "\n".join(good.evidence)
        self.assertIn("oauth", text)
        self.assertIn("REFUSED", text)
        self.assertEqual(good.status, H.PASS)


class MailboxEdgesTest(unittest.TestCase):
    def test_folders_are_decoded_and_a_logout_failure_is_ignored(self):
        class _IMAP:
            def list(self):
                return "OK", [
                    b'(\\HasNoChildren) "/" "INBOX"',
                    "not-bytes",
                ]

            def logout(self):
                raise RuntimeError("already gone")

        class _SMTP:
            def quit(self):
                raise RuntimeError("quit")

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(R, "connect_imap",
                                   return_value=_IMAP()), \
                    mock.patch.object(R, "connect_smtp",
                                      return_value=_SMTP()):
                sec = _sec("mailbox", H._sec_mailbox, _cfg(), d)
        self.assertEqual(sec.status, H.PASS)
        self.assertIn("INBOX", "\n".join(sec.evidence))


class ModelEdgesTest(unittest.TestCase):
    def test_names_skip_what_is_not_a_named_model(self):
        self.assertEqual(H._model_names({
            "data": ["x", {"id": 1}, {"id": "a"}],
            "models": [None, {"name": 2}, {"name": "b"}],
        }), ["a", "b"])
        self.assertEqual(H._model_names(["nope"]), [])

    def test_no_endpoint_an_empty_list_and_an_empty_answer(self):
        with tempfile.TemporaryDirectory() as d:
            sec = _sec("model", H._sec_model, _cfg(inference=None), d)
            self.assertEqual(sec.status, H.FAIL)
            self.assertIn("not loopback", sec.summary)

            def empty(_req, timeout=60):
                return {"data": []}

            with mock.patch.object(R, "_default_inference_open",
                                   return_value=_Resp(empty)):
                pass
            with mock.patch.object(H, "_http_json", return_value={"data": []}):
                sec = _sec("model", H._sec_model, _cfg(
                    inference={"endpoint": "http://127.0.0.1:9",
                               "model": "m"}), d)
            self.assertIn("could not list", sec.summary)
            answers = iter([
                {"data": [{"id": "other"}]},
                {"choices": "not-a-list"},
            ])
            with mock.patch.object(H, "_http_json",
                                   side_effect=lambda *_a, **_k: next(answers)):
                sec = _sec("model", H._sec_model, _cfg(
                    inference={"endpoint": "http://127.0.0.1:9/v1",
                               "model": "m"}), d)
            self.assertIn("not served", sec.summary)
            answers = iter([
                {"models": [{"name": "m"}]},
                {"choices": [{"message": {"content": "  "}}]},
            ])
            with mock.patch.object(H, "_http_json",
                                   side_effect=lambda *_a, **_k: next(answers)):
                sec = _sec("model", H._sec_model, _cfg(
                    inference={"endpoint": "http://127.0.0.1:9/v1",
                               "model": "m"}), d)
            self.assertIn("empty content", sec.summary)


class _Resp:
    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self):
        return b"{}"


class FindResultTest(unittest.TestCase):
    def _msg(self, subject):
        msg = EmailMessage()
        msg["Subject"] = subject
        msg.set_content("signed")
        return msg.as_bytes()

    def test_the_search_shapes_that_are_not_a_result(self):
        class _C:
            def search(self, *_a):
                return "NO", None

            def fetch(self, *_a):
                return "OK", []

        self.assertIsNone(H._find_result(_C(), SECRET, "job"))

        class _Str:
            def search(self, *_a):
                return "OK", ["1"]

            def fetch(self, *_a):
                return "NO", None

        self.assertIsNone(H._find_result(_Str(), SECRET, "job"))

        class _Odd:
            def search(self, *_a):
                return "OK", [1]

        self.assertIsNone(H._find_result(_Odd(), SECRET, "job"))

    def test_a_mail_that_does_not_verify_is_invalid(self):
        raw = self._msg("result JOB1")

        class _C:
            def search(self, *_a):
                return "OK", [b"1 2"]

            def fetch(self, num, _q):
                if num == b"1":
                    return "OK", [b"not-a-tuple"]
                return "OK", [(b"hdr", raw)]

        with mock.patch.object(R, "get_text_body", return_value="body"), \
                mock.patch.object(R, "verify_body",
                                  side_effect=ValueError("bad sig")):
            with self.assertRaises(H._ResultInvalid):
                H._find_result(_C(), SECRET, "JOB1")
        with mock.patch.object(R, "get_text_body", return_value="body"), \
                mock.patch.object(R, "verify_body",
                                  return_value={"exit_code": 0}):
            got = H._find_result(_C(), SECRET, "JOB1")
        self.assertEqual(got["exit_code"], 0)

    def test_a_poll_reconnects_and_a_bad_signature_escapes(self):
        state = {"n": 0}

        class _Up:
            def search(self, *_a):
                return "OK", [b"1"]

            def fetch(self, *_a):
                return "OK", [(b"h", b"raw")]

            def logout(self):
                raise RuntimeError("bye")

        def connect(_cfg):
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("down")
            return _Up()

        with mock.patch.object(R, "connect_imap", connect), \
                mock.patch.object(H, "_find_result",
                                  return_value={"ok": True}), \
                mock.patch.object(H.time, "sleep"):
            self.assertEqual(
                H._poll_for_result(_cfg(), SECRET, "j", 5)["ok"], True)
        with mock.patch.object(R, "connect_imap", return_value=_Up()), \
                mock.patch.object(
                    H, "_find_result",
                    side_effect=H._ResultInvalid("no")), \
                mock.patch.object(H.time, "sleep"):
            with self.assertRaises(H._ResultInvalid):
                H._poll_for_result(_cfg(), SECRET, "j", 1)
        with mock.patch.object(R, "connect_imap",
                               side_effect=RuntimeError("down")), \
                mock.patch.object(H.time, "sleep"):
            self.assertIsNone(H._poll_for_result(_cfg(), SECRET, "j", 0))


class RoundTripEdgesTest(unittest.TestCase):
    def test_no_secret_a_bad_signature_and_a_wrong_result(self):
        with tempfile.TemporaryDirectory() as d:
            sec = _sec("round-trip", H._sec_roundtrip,
                       _cfg(shared_secret=""), d)
            self.assertIn("no shared_secret", sec.summary)
            with mock.patch.object(R, "connect_smtp",
                                   return_value=mock.Mock()), \
                    mock.patch.object(R, "send_mail"), \
                    mock.patch.object(
                        H, "_poll_for_result",
                        side_effect=H._ResultInvalid("forged")):
                sec = _sec("round-trip", H._sec_roundtrip, _cfg(), d)
            self.assertIn("forged", sec.summary)
            with mock.patch.object(R, "connect_smtp",
                                   return_value=mock.Mock()), \
                    mock.patch.object(R, "send_mail"), \
                    mock.patch.object(
                        H, "_poll_for_result",
                        return_value={"exit_code": 1, "timed_out": False,
                                      "stdout": "nope", "kind": "exec"}):
                sec = _sec("round-trip", H._sec_roundtrip, _cfg(), d)
            self.assertIn("NOT echoed", sec.summary)


class ContextAndSensesTest(unittest.TestCase):
    def test_retained_jobs_without_an_index_fail(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "a.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            with mock.patch.object(R, "oracle_context",
                                   return_value="hello\n"):
                sec = _sec("oracle-context", H._sec_context, _cfg(), d)
            self.assertEqual(sec.status, H.FAIL)
            self.assertIn("no job index", sec.summary)
            with mock.patch.object(os, "listdir",
                                   side_effect=OSError("no")), \
                    mock.patch.object(R, "oracle_context",
                                      return_value="hello\n"):
                sec = _sec("oracle-context", H._sec_context, _cfg(), d)
            self.assertEqual(sec.status, H.INFO)

    def test_windows_senses_and_a_tripped_canary(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(H.sys, "platform", "win32"), \
                    mock.patch.object(R, "_canary_watch",
                                      return_value="TRIPPED line"), \
                    mock.patch.object(R, "_eventlog_tail",
                                      return_value=None), \
                    mock.patch.object(R, "_registry_watch",
                                      return_value=None):
                sec = _sec("senses", H._sec_senses, _cfg(), d)
            self.assertEqual(sec.status, H.FAIL)
            self.assertIn("UNREADABLE", "\n".join(sec.evidence))
            with mock.patch.object(H.sys, "platform", "win32"), \
                    mock.patch.object(R, "_canary_watch",
                                      return_value="quiet"), \
                    mock.patch.object(R, "_eventlog_tail",
                                      return_value="Error: disk"), \
                    mock.patch.object(R, "_registry_watch",
                                      return_value="Run key added"):
                sec = _sec("senses", H._sec_senses, _cfg(), d)
            self.assertEqual(sec.status, H.PASS)
            self.assertIn("disk", "\n".join(sec.evidence))
            with mock.patch.object(H.sys, "platform", "linux"), \
                    mock.patch.object(R, "_canary_watch",
                                      return_value="ok"), \
                    mock.patch.object(R, "_host_log_tail",
                                      return_value="auth failure"):
                sec = _sec("senses", H._sec_senses, _cfg(), d)
            self.assertIn("auth failure", "\n".join(sec.evidence))
            with mock.patch.object(H.sys, "platform", "linux"), \
                    mock.patch.object(R, "_canary_watch",
                                      return_value=None), \
                    mock.patch.object(R, "_host_log_tail",
                                      return_value=None):
                sec = _sec("senses", H._sec_senses, _cfg(), d)
            self.assertEqual(sec.status, H.FAIL)


class ReportEdgesTest(unittest.TestCase):
    def test_a_bad_timeout_and_a_report_that_cannot_be_written(self):
        seen = {}

        def grab(ctx, sec):
            seen["timeout"] = ctx["roundtrip_timeout"]
            sec.verdict(H.INFO, "noted")

        lines = []
        with tempfile.TemporaryDirectory() as d:
            H.run_diagnose("not-a-dict", out=lines.append, base_dir=d,
                           roundtrip_timeout="nope",
                           sections=[("only", grab)])
            self.assertEqual(seen["timeout"], 120)
            H.run_diagnose({}, out=lines.append, base_dir=d,
                           roundtrip_timeout=0,
                           sections=[("only", grab)])
            self.assertEqual(seen["timeout"], 120)
            with mock.patch.object(os, "makedirs",
                                   side_effect=OSError("full")):
                H.run_diagnose({}, out=lines.append, base_dir=d,
                               sections=[])
            self.assertTrue(any("could not write" in ln for ln in lines))

    def test_main_forwards_the_timeout(self):
        with mock.patch.object(H, "run_diagnose", return_value=4) as run:
            self.assertEqual(H.main({"a": 1}, "/tmp", cfg_path="c",
                                    roundtrip_timeout=9), 4)
        self.assertEqual(run.call_args.kwargs["roundtrip_timeout"], 9)
        with mock.patch.object(H, "run_diagnose", return_value=0) as run:
            H.main({}, "/tmp")
        self.assertEqual(run.call_args.kwargs["roundtrip_timeout"], 120)

    def test_running_the_file_as_main_points_at_diagnose(self):
        import runpy
        with mock.patch("builtins.print") as printed:
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(H.__file__, run_name="__main__")
        self.assertEqual(caught.exception.code, 2)
        text = " ".join(str(c) for c in printed.call_args_list)
        self.assertIn("--diagnose", text)


class LastHarnessBranchesTest(unittest.TestCase):
    def test_a_list_that_fails_and_a_model_call_that_raises(self):
        class _IMAP:
            def list(self):
                return "NO", None

            def logout(self):
                return "BYE", []

        class _SMTP:
            def quit(self):
                return None

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(R, "connect_imap",
                                   return_value=_IMAP()), \
                    mock.patch.object(R, "connect_smtp",
                                      return_value=_SMTP()):
                sec = _sec("mailbox", H._sec_mailbox, _cfg(), d)
            self.assertEqual(sec.status, H.PASS)
            with mock.patch.object(H, "_http_json",
                                   side_effect=RuntimeError("down")):
                sec = _sec("model", H._sec_model, _cfg(), d)
            self.assertIn("could not list", sec.summary)
            answers = iter([
                {"data": [{"id": "llama3.2:3b"}]},
                {"choices": "bad"},
            ])
            with mock.patch.object(
                    H, "_http_json",
                    side_effect=lambda *_a, **_k: next(answers)):
                sec = _sec("model", H._sec_model, _cfg(), d)
            self.assertIn("empty content", sec.summary)

    def test_an_unreadable_result_mail_is_skipped(self):
        class _C:
            def search(self, *_a):
                return "OK", [b"1"]

            def fetch(self, *_a):
                return "OK", [(b"h", b"raw")]

        with mock.patch("email.message_from_bytes",
                        side_effect=ValueError("bad")):
            self.assertIsNone(H._find_result(_C(), SECRET, "job"))

    def test_an_empty_windows_window_and_a_report_chmod_failure(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(H.sys, "platform", "win32"), \
                    mock.patch.object(R, "_canary_watch",
                                      return_value="ok"), \
                    mock.patch.object(R, "_eventlog_tail",
                                      return_value=""), \
                    mock.patch.object(R, "_registry_watch",
                                      return_value=""):
                sec = _sec("senses", H._sec_senses, _cfg(), d)
            text = "\n".join(sec.evidence)
            self.assertIn("no Critical", text)
            self.assertIn("no changes", text)
            self.assertEqual(sec.status, H.PASS)
            with mock.patch.object(R, "oracle_context",
                                   return_value="Job index\n"):
                sec = _sec("oracle-context", H._sec_context, _cfg(), d)
            self.assertIn("absent", "\n".join(sec.evidence))
            had = hasattr(os, "O_NOFOLLOW")
            saved = getattr(os, "O_NOFOLLOW", None)
            if had:
                delattr(os, "O_NOFOLLOW")
            os.O_BINARY = 0
            try:
                with mock.patch.object(os, "chmod", side_effect=OSError):
                    H.run_diagnose({}, out=lambda _l: None, base_dir=d,
                                   sections=[])
            finally:
                if had:
                    os.O_NOFOLLOW = saved
                del os.O_BINARY
            with mock.patch.object(R, "_base_dir_for", return_value=d):
                H.run_diagnose({}, out=lambda _l: None, base_dir=None,
                               sections=[])
            with mock.patch.object(R, "oracle_context",
                                   return_value="\n---\n"):
                sec = _sec("oracle-context", H._sec_context, _cfg(), d)
            self.assertIn("sections present", "\n".join(sec.evidence))

    def test_the_script_import_is_the_fallback(self):
        import builtins
        import importlib
        real = builtins.__import__

        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "runner" and fromlist:
                raise ImportError("script")
            return real(name, globals, locals, fromlist, level)

        try:
            with mock.patch("builtins.__import__", guarded):
                importlib.reload(H)
            self.assertTrue(callable(H.run_diagnose))
        finally:
            importlib.reload(H)

