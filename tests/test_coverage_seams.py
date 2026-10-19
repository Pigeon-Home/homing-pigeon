import io
import json
import os
import tempfile
import unittest
from unittest import mock


class PkceTest(unittest.TestCase):
    def test_challenge_is_s256_of_the_verifier(self):
        import base64
        import hashlib
        from runner.oauth import _pkce

        verifier, challenge = _pkce()
        self.assertIsInstance(verifier, str)
        self.assertIsInstance(challenge, str)
        self.assertTrue(verifier)
        self.assertTrue(challenge)
        self.assertNotEqual(verifier, challenge)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        self.assertEqual(challenge, expected)

    def test_two_calls_do_not_reuse_the_verifier(self):
        from runner.oauth import _pkce

        first, _ = _pkce()
        second, _ = _pkce()
        self.assertNotEqual(first, second)


class AuthorizeUrlTest(unittest.TestCase):
    def test_url_carries_the_pkce_and_offline_params(self):
        import urllib.parse
        from runner.oauth import AUTH_URL, REDIRECT_URI, SCOPE, build_authorize_url

        url = build_authorize_url(
            {"oauth_client_id": "cid"}, "ver", "chal", "st")
        self.assertTrue(url.startswith(AUTH_URL + "?"))
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["client_id"], ["cid"])
        self.assertEqual(query["redirect_uri"], [REDIRECT_URI])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["scope"], [SCOPE])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertEqual(query["code_challenge"], ["chal"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["state"], ["st"])

    def test_a_second_state_is_not_the_first(self):
        import urllib.parse
        from runner.oauth import build_authorize_url

        first = build_authorize_url({}, "ver", "chal", "one")
        second = build_authorize_url({}, "ver", "chal", "two")
        q1 = urllib.parse.parse_qs(
            urllib.parse.urlparse(first).query, keep_blank_values=True)
        q2 = urllib.parse.parse_qs(urllib.parse.urlparse(second).query)
        self.assertEqual(q1["state"], ["one"])
        self.assertEqual(q2["state"], ["two"])
        self.assertEqual(q1["client_id"], [""])


class _Body:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ExchangeCodeTest(unittest.TestCase):
    def _opener(self, raw, seen):
        def opener(req, timeout=30):
            seen.append((req.data, timeout))
            return _Body(raw)
        return opener

    def test_refresh_token_is_returned(self):
        import urllib.parse
        from runner.oauth import exchange_code

        seen = []
        token = exchange_code(
            {"oauth_client_id": "cid", "oauth_client_secret": "sek"},
            "code", "ver", opener=self._opener(b'{"refresh_token":"rtok"}', seen))
        self.assertEqual(token, "rtok")
        form = urllib.parse.parse_qs(seen[0][0].decode("ascii"))
        self.assertEqual(form["client_secret"], ["sek"])
        self.assertEqual(form["code"], ["code"])
        self.assertEqual(form["code_verifier"], ["ver"])
        self.assertEqual(form["grant_type"], ["authorization_code"])
        self.assertEqual(seen[0][1], 30)

    def test_secret_is_omitted_when_empty(self):
        import urllib.parse
        from runner.oauth import exchange_code

        seen = []
        exchange_code(
            {"oauth_client_id": "cid"},
            "code", "ver", opener=self._opener(b'{"refresh_token":"rtok"}', seen))
        form = urllib.parse.parse_qs(seen[0][0].decode("ascii"))
        self.assertNotIn("client_secret", form)

    def test_http_error_with_bad_json_is_system_exit(self):
        import io
        import urllib.error
        from runner.oauth import TOKEN_URL, exchange_code

        def opener(req, timeout=30):
            raise urllib.error.HTTPError(
                TOKEN_URL, 400, "bad", {}, io.BytesIO(b"not-json"))

        with self.assertRaises(SystemExit):
            exchange_code({"oauth_client_id": "cid"}, "code", "ver", opener=opener)

    def test_a_list_body_is_system_exit(self):
        from runner.oauth import exchange_code

        with self.assertRaises(SystemExit):
            exchange_code(
                {"oauth_client_id": "cid"}, "code", "ver",
                opener=self._opener(b"[1]", []))

    def test_missing_refresh_token_is_system_exit(self):
        from runner.oauth import exchange_code

        with self.assertRaises(SystemExit):
            exchange_code(
                {"oauth_client_id": "cid"}, "code", "ver",
                opener=self._opener(b'{"access_token":"x"}', []))


class CatchHandlerTest(unittest.TestCase):
    def setUp(self):
        from runner.oauth import _Catch
        _Catch.code = None
        _Catch.error = None

    def _handler(self, path):
        from runner.oauth import _Catch
        handler = _Catch.__new__(_Catch)
        handler.path = path
        handler.request_version = "HTTP/1.1"
        handler.requestline = "GET " + path + " HTTP/1.1"
        handler.wfile = io.BytesIO()
        return handler

    def test_code_is_stored_and_the_page_is_200(self):
        from runner.oauth import _Catch
        handler = self._handler("/?code=abc")
        handler.do_GET()
        self.assertEqual(_Catch.code, "abc")
        self.assertIsNone(_Catch.error)
        page = handler.wfile.getvalue()
        self.assertIn(b"200", page)
        self.assertIn(b"Signed in", page)

    def test_error_is_stored_and_code_stays_unset(self):
        from runner.oauth import _Catch
        handler = self._handler("/?error=access_denied")
        handler.do_GET()
        self.assertEqual(_Catch.error, "access_denied")
        self.assertIsNone(_Catch.code)
        self.assertIn(b"access_denied", handler.wfile.getvalue())

    def test_a_bare_path_is_an_unknown_error(self):
        from runner.oauth import _Catch
        handler = self._handler("/")
        handler.do_GET()
        self.assertEqual(_Catch.error, "unknown")
        self.assertIsNone(_Catch.code)
        self.assertIn(b"unknown", handler.wfile.getvalue())

    def test_log_message_is_silent(self):
        handler = self._handler("/")
        self.assertIsNone(handler.log_message("x"))


class MailboxProbeTest(unittest.TestCase):
    def test_a_missing_helper_is_a_string(self):
        from runner import setup
        with mock.patch.object(setup, "refresh_access_token", None):
            text = setup._mailbox_probe({"mailbox_user": "a@b.c"})
        self.assertIsInstance(text, str)
        self.assertIn("oauth", text)

    def test_a_failed_refresh_names_the_token(self):
        from runner import setup
        with mock.patch.object(setup, "refresh_access_token",
                               side_effect=RuntimeError("nope")):
            text = setup._mailbox_probe({"mailbox_user": "a@b.c"})
        self.assertIsInstance(text, str)
        self.assertIn("token", text)

    def test_a_failed_constructor_names_imap(self):
        from runner import setup
        with mock.patch.object(setup, "refresh_access_token", return_value="tok"), \
             mock.patch.object(setup.imaplib, "IMAP4_SSL",
                               side_effect=OSError("down")):
            text = setup._mailbox_probe({"mailbox_user": "a@b.c"})
        self.assertIsInstance(text, str)
        self.assertIn("IMAP", text)

    def test_a_failed_authenticate_names_imap(self):
        from runner import setup

        class Boom:
            def __init__(self, host, port, ssl_context=None):
                self.host = host
            def authenticate(self, mech, callback):
                raise RuntimeError("bad sasl")
            def logout(self):
                raise AssertionError("logout after a failed login")

        with mock.patch.object(setup, "refresh_access_token", return_value="tok"), \
             mock.patch.object(setup.imaplib, "IMAP4_SSL", Boom):
            text = setup._mailbox_probe({"mailbox_user": "a@b.c"})
        self.assertIsInstance(text, str)
        self.assertIn("IMAP", text)

    def test_a_successful_login_returns_none_and_logs_out(self):
        from runner import setup
        seen = []

        class Ok:
            def __init__(self, host, port, ssl_context=None):
                seen.append(("host", host, port))
            def authenticate(self, mech, callback):
                seen.append(("auth", mech))
            def logout(self):
                seen.append(("logout",))

        with mock.patch.object(setup, "refresh_access_token", return_value="tok"), \
             mock.patch.object(setup.imaplib, "IMAP4_SSL", Ok):
            self.assertIsNone(setup._mailbox_probe({"mailbox_user": "a@b.c"}))
        self.assertEqual(seen[0], ("host", "imap.gmail.com", 993))
        self.assertIn(("logout",), seen)


class SharedSecretTest(unittest.TestCase):
    def _write(self, directory, secret):
        path = os.path.join(directory, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": secret, "mailbox_user": "a@b.c"}, fh)
        return path

    def test_a_real_secret_is_left_alone(self):
        from runner.install import ensure_shared_secret
        real = "ab" * 32
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, real)
            before = open(path, "rb").read()
            ensure_shared_secret(path, None)
            self.assertEqual(open(path, "rb").read(), before)

    def test_a_placeholder_is_replaced(self):
        from runner.install import ensure_shared_secret
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, "changeme")
            ensure_shared_secret(path, None)
            written = json.load(open(path, encoding="utf-8"))
            secret = written["shared_secret"]
            self.assertEqual(len(secret), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in secret))
            self.assertEqual(written["mailbox_user"], "a@b.c")

    def test_a_weak_provided_secret_exits(self):
        from runner.install import ensure_shared_secret
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, "")
            before = open(path, "rb").read()
            with self.assertRaises(SystemExit) as raised:
                ensure_shared_secret(path, "aaaa")
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(open(path, "rb").read(), before)

    def test_an_empty_secret_is_generated(self):
        from runner.install import ensure_shared_secret
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, "")
            ensure_shared_secret(path, None)
            secret = json.load(open(path, encoding="utf-8"))["shared_secret"]
            self.assertEqual(len(secret), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in secret))
            if os.name != "nt":
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


class InstallMainTest(unittest.TestCase):
    _SIDES = (
        "install_files",
        "ensure_shared_secret",
        "store_additional_secret",
        "install_ollama_and_model",
        "apply_profile",
        "apply_instruction_flags",
        "install_windows",
        "install_macos",
        "install_linux",
        "install_freebsd",
        "uninstall_windows",
        "uninstall_macos",
        "uninstall_linux",
        "uninstall_freebsd",
    )

    def _run(self, argv):
        import contextlib
        import sys
        from runner import install
        stack = contextlib.ExitStack()
        for name in self._SIDES:
            stack.enter_context(mock.patch.object(install, name))
        stack.enter_context(mock.patch.object(sys.stdin, "isatty", return_value=False))
        stack.enter_context(mock.patch.object(sys, "argv", ["install", *argv]))
        try:
            code = install.main()
            recorded = {
                "ollama": install.install_ollama_and_model.call_args,
                "files_called": install.install_files.called,
                "secret": install.ensure_shared_secret.call_args,
                "install_count": self._installer(install).call_count,
                "uninstall_count": self._uninstaller(install).call_count,
            }
        finally:
            stack.close()
        return code, recorded

    def _installer(self, install):
        import sys
        plat = sys.platform
        if plat == "win32":
            return install.install_windows
        if plat == "darwin":
            return install.install_macos
        if plat.startswith("linux"):
            return install.install_linux
        if plat.startswith("freebsd"):
            return install.install_freebsd
        self.fail("unsupported platform " + plat)

    def _uninstaller(self, install):
        import sys
        plat = sys.platform
        if plat == "win32":
            return install.uninstall_windows
        if plat == "darwin":
            return install.uninstall_macos
        if plat.startswith("linux"):
            return install.uninstall_linux
        if plat.startswith("freebsd"):
            return install.uninstall_freebsd
        self.fail("unsupported platform " + plat)

    def test_no_inference_still_installs_this_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            code, recorded = self._run([
                "--dir", directory, "--no-inference", "--no-profile"])
        self.assertEqual(code, 0)
        self.assertTrue(recorded["ollama"][0][2])
        self.assertEqual(recorded["install_count"], 1)

    def test_pi_profiles_download_no_model(self):
        # Pi Light: the Ollama/model path is never invoked -- no
        # Ollama install, no model pull, nothing downloaded. Both
        # the current name and the former one mean the light install.
        for profile in ("pi-light", "raspberry-pi-home"):
            with tempfile.TemporaryDirectory() as directory:
                code, recorded = self._run([
                    "--dir", directory, "--profile", profile])
            self.assertEqual(code, 0)
            self.assertIsNone(recorded["ollama"])

    def test_uninstall_does_not_copy_files(self):
        code, recorded = self._run(["--uninstall"])
        self.assertEqual(code, 0)
        self.assertFalse(recorded["files_called"])
        self.assertEqual(recorded["uninstall_count"], 1)

    def test_shared_secret_is_handed_to_the_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            code, recorded = self._run([
                "--dir", directory, "--no-profile",
                "--shared-secret", "supplied-secret-value"])
        self.assertEqual(code, 0)
        self.assertEqual(recorded["secret"][0][1], "supplied-secret-value")


class _OracleServer:
    def __init__(self):
        self.socket = self
        self.closed = False

    def getsockname(self):
        return ("127.0.0.1", 11436)

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


class _RecordedTimer:
    started = []

    def __init__(self, delay, fn):
        self.delay = delay
        self.fn = fn
        _RecordedTimer.started.append((delay, fn))

    def start(self):
        return None


class OracleWindowTest(unittest.TestCase):
    def test_a_word_port_does_not_listen(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(runner, "make_oracle_server") as made:
            code = runner.oracle_window({"base_dir": directory}, port="nope")
        self.assertEqual(code, 2)
        self.assertFalse(made.called)

    def test_an_out_of_range_port_does_not_listen(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(runner, "make_oracle_server") as made:
            code = runner.oracle_window({"base_dir": directory}, port=70000)
        self.assertEqual(code, 2)
        self.assertFalse(made.called)

    def test_a_bind_error_returns_1(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(runner, "make_oracle_server",
                               side_effect=OSError("busy")):
            code = runner.oracle_window({"base_dir": directory})
        self.assertEqual(code, 1)

    def test_a_bad_server_returns_2(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(runner, "make_oracle_server",
                               side_effect=ValueError("bad")):
            code = runner.oracle_window({"base_dir": directory})
        self.assertEqual(code, 2)

    def test_ctrl_c_records_open_and_close_without_a_browser(self):
        from runner import runner
        server = _OracleServer()
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(runner, "make_oracle_server", return_value=server), \
             mock.patch.object(runner.webbrowser, "open") as opened:
            code = runner.oracle_window(
                {"base_dir": directory}, open_browser=False)
            log = open(os.path.join(directory, "oracle-chat.jsonl"),
                       encoding="utf-8").read()
        self.assertEqual(code, 0)
        self.assertTrue(server.closed)
        self.assertFalse(opened.called)
        self.assertIn('"event": "open"', log)
        self.assertIn('"event": "close"', log)

    def test_the_browser_is_scheduled_not_waited_on(self):
        from runner import runner
        _RecordedTimer.started = []
        server = _OracleServer()
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(runner, "make_oracle_server", return_value=server), \
             mock.patch.object(runner.webbrowser, "open") as opened, \
             mock.patch.object(runner.threading, "Timer", _RecordedTimer):
            code = runner.oracle_window(
                {"base_dir": directory}, open_browser=True)
        self.assertEqual(code, 0)
        self.assertEqual(len(_RecordedTimer.started), 1)
        self.assertEqual(_RecordedTimer.started[0][0], 0.4)
        self.assertFalse(opened.called)


class RunnerMainTest(unittest.TestCase):
    _VALID = {
        "shared_secret": "0123456789abcdef" * 4,
        "mailbox_user": "a@b.c",
        "mailbox_password": "pw",
    }

    def _main(self, argv, text=None, present=True):
        import contextlib
        import sys
        from runner import runner
        from runner import setup
        stack = contextlib.ExitStack()
        oracle = stack.enter_context(
            mock.patch.object(runner, "oracle_window", return_value=7))
        imap = stack.enter_context(mock.patch.object(runner, "connect_imap"))
        stack.enter_context(mock.patch.object(runner, "connect_smtp"))
        stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
        stack.enter_context(mock.patch.object(runner, "update_llama_from_config"))
        stack.enter_context(mock.patch.object(setup, "is_tty", return_value=False))
        stack.enter_context(mock.patch.object(setup, "needs_setup", return_value=None))
        stack.enter_context(mock.patch.object(setup, "prompt_yes_no", return_value=False))
        local = stack.enter_context(
            mock.patch("runner.local_test.main", return_value=4))
        stack.enter_context(mock.patch.object(
            runner, "poll_once", side_effect=AssertionError("poll")))
        stack.enter_context(mock.patch.object(
            runner.time, "sleep", side_effect=AssertionError("sleep")))
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        path = os.path.join(directory, "config.json")
        if present:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text if text is not None else json.dumps(self._VALID))
        stack.enter_context(mock.patch.object(
            sys, "argv", ["runner", "--config", path, *argv]))
        try:
            code = runner.main()
        finally:
            stack.close()
        return code, oracle, imap, local

    def test_a_missing_config_returns_2(self):
        code, oracle, imap, _local = self._main([], present=False)
        self.assertEqual(code, 2)
        self.assertFalse(oracle.called)
        self.assertFalse(imap.called)

    def test_a_list_config_returns_2(self):
        code, oracle, imap, _local = self._main([], text="[]")
        self.assertEqual(code, 2)
        self.assertFalse(oracle.called)
        self.assertFalse(imap.called)

    def test_zero_workers_returns_2(self):
        code, oracle, imap, _local = self._main(["--workers", "0"])
        self.assertEqual(code, 2)
        self.assertFalse(oracle.called)
        self.assertFalse(imap.called)

    def test_oracle_does_not_open_a_mailbox(self):
        code, oracle, imap, local = self._main(["--oracle"])
        self.assertEqual(code, 7)
        self.assertEqual(oracle.call_count, 1)
        self.assertEqual(oracle.call_args[0][1], 11436)
        self.assertEqual(oracle.call_args[0][0]["mailbox_user"], "a@b.c")
        self.assertFalse(imap.called)
        self.assertFalse(local.called)

    def test_oracle_port_is_passed_through(self):
        code, oracle, imap, _local = self._main(
            ["--oracle", "--oracle-port", "11437"])
        self.assertEqual(code, 7)
        self.assertEqual(oracle.call_args[0][1], 11437)
        self.assertFalse(imap.called)

    def test_local_test_does_not_open_a_mailbox(self):
        code, oracle, imap, local = self._main(["--local-test"])
        self.assertEqual(code, 4)
        self.assertEqual(local.call_count, 1)
        self.assertFalse(oracle.called)
        self.assertFalse(imap.called)


class _FakeIMAP:
    select_result = ("OK", [b"1"])
    tagged = ("OK", [b"ok"])
    built = []

    def __init__(self, host, port=993, timeout=30):
        _FakeIMAP.built.append(self)
        self.host = host
        self.port = port
        self.timeout = timeout
        self.state = "NONAUTH"
        self.login_args = None
        self.selected = None
        self.sent = []

    def login(self, user, password):
        self.login_args = (user, password)

    def select(self, mailbox):
        self.selected = mailbox
        return type(self).select_result

    def _new_tag(self):
        return b"A001"

    def send(self, data):
        self.sent.append(data)

    def _get_tagged_response(self, tag):
        return type(self).tagged


class _FakeSMTP:
    built = []

    def __init__(self, host, port=587, timeout=30):
        _FakeSMTP.built.append(self)
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started = False
        self.login_args = None
        self.auth_mech = None
        self.callback_result = None

    def starttls(self, *args, **kwargs):
        self.started = True

    def login(self, user, password):
        self.login_args = (user, password)

    def auth(self, mech, callback, *args):
        self.auth_mech = mech
        self.callback_result = callback()


class ConnectMailTest(unittest.TestCase):
    def setUp(self):
        _FakeIMAP.built = []
        _FakeIMAP.select_result = ("OK", [b"1"])
        _FakeIMAP.tagged = ("OK", [b"ok"])
        _FakeSMTP.built = []

    def _imap_cfg(self, **extra):
        cfg = {
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "mailbox_user": "a@b.c",
            "mailbox_password": "pw",
        }
        cfg.update(extra)
        return cfg

    def _smtp_cfg(self, **extra):
        cfg = {
            "smtp_host": "smtp.example.test",
            "smtp_port": 587,
            "mailbox_user": "a@b.c",
            "mailbox_password": "pw",
        }
        cfg.update(extra)
        return cfg

    def test_password_login_selects_the_inbox(self):
        from runner import runner
        with mock.patch.object(runner.imaplib, "IMAP4_SSL", _FakeIMAP):
            conn = runner.connect_imap(self._imap_cfg())
        self.assertIs(conn, _FakeIMAP.built[0])
        self.assertEqual(conn.host, "imap.example.test")
        self.assertEqual(conn.port, 993)
        self.assertEqual(conn.timeout, 30)
        self.assertEqual(conn.login_args, ("a@b.c", "pw"))
        self.assertEqual(conn.selected, "INBOX")

    def test_a_non_string_password_does_not_login(self):
        from runner import runner
        with mock.patch.object(runner.imaplib, "IMAP4_SSL", _FakeIMAP):
            with self.assertRaises(RuntimeError):
                runner.connect_imap(self._imap_cfg(mailbox_password=5))
        self.assertIsNone(_FakeIMAP.built[0].login_args)

    def test_a_failed_select_is_a_runtime_error(self):
        from runner import runner
        _FakeIMAP.select_result = ("NO", [])
        with mock.patch.object(runner.imaplib, "IMAP4_SSL", _FakeIMAP):
            with self.assertRaises(RuntimeError):
                runner.connect_imap(self._imap_cfg())

    def test_oauth_sends_the_sasl_line_and_marks_auth(self):
        import base64
        from runner import runner
        with mock.patch.object(runner.imaplib, "IMAP4_SSL", _FakeIMAP), \
             mock.patch.object(runner, "_xoauth2_raw", return_value="raw-token"):
            conn = runner.connect_imap(self._imap_cfg(auth="oauth"))
        sent = b"".join(conn.sent)
        self.assertIn(b"AUTHENTICATE XOAUTH2", sent)
        self.assertIn(base64.b64encode(b"raw-token"), sent)
        self.assertEqual(conn.state, "AUTH")
        self.assertIsNone(conn.login_args)

    def test_a_rejected_xoauth2_is_an_imap_error(self):
        import imaplib
        from runner import runner
        _FakeIMAP.tagged = ("NO", [b"bad"])
        with mock.patch.object(runner.imaplib, "IMAP4_SSL", _FakeIMAP), \
             mock.patch.object(runner, "_xoauth2_raw", return_value="raw-token"):
            with self.assertRaises(imaplib.IMAP4.error):
                runner.connect_imap(self._imap_cfg(auth="oauth"))

    def test_smtp_password_starts_tls_and_logs_in(self):
        from runner import runner
        with mock.patch.object(runner.smtplib, "SMTP", _FakeSMTP):
            smtp = runner.connect_smtp(self._smtp_cfg())
        self.assertTrue(smtp.started)
        self.assertEqual(smtp.login_args, ("a@b.c", "pw"))
        self.assertEqual(smtp.host, "smtp.example.test")

    def test_smtp_oauth_calls_the_callback_with_no_arguments(self):
        from runner import runner
        with mock.patch.object(runner.smtplib, "SMTP", _FakeSMTP), \
             mock.patch.object(runner, "_xoauth2_raw", return_value="raw-token"):
            smtp = runner.connect_smtp(self._smtp_cfg(auth="oauth"))
        self.assertEqual(smtp.auth_mech, "XOAUTH2")
        self.assertEqual(smtp.callback_result, "raw-token")
        self.assertIsNone(smtp.login_args)

    def test_a_non_string_smtp_password_does_not_login(self):
        from runner import runner
        with mock.patch.object(runner.smtplib, "SMTP", _FakeSMTP):
            with self.assertRaises(RuntimeError):
                runner.connect_smtp(self._smtp_cfg(mailbox_password=5))
        self.assertTrue(_FakeSMTP.built[0].started)
        self.assertIsNone(_FakeSMTP.built[0].login_args)


class AnswerAsOracleTest(unittest.TestCase):
    def test_no_inference_is_rejected(self):
        from runner.local_test import answer_as_oracle
        self.assertEqual(
            answer_as_oracle({}, "hello"),
            {"rejected": "inference_unconfigured"})

    def test_no_secret_is_rejected(self):
        from runner.local_test import answer_as_oracle
        cfg = {"inference": {
            "endpoint": "http://127.0.0.1:9/v1",
            "model": "m",
        }}
        self.assertEqual(
            answer_as_oracle(cfg, "hello"),
            {"rejected": "no shared_secret in config"})

    def test_a_signed_ask_returns_the_model_answer(self):
        from runner import runner
        from runner.local_test import answer_as_oracle
        cfg = {
            "inference": {
                "endpoint": "http://127.0.0.1:9/v1",
                "model": "m",
            },
            "shared_secret": "0123456789abcdef" * 4,
        }
        answer = {"op": "ask", "answer": "fine", "model": "m"}
        with mock.patch.object(runner, "ask_model", return_value=answer):
            result = answer_as_oracle(cfg, "what time is it")
        self.assertEqual(result.get("answer"), "fine")

    def test_a_model_error_is_a_dict(self):
        from runner import runner
        from runner.local_test import answer_as_oracle
        cfg = {
            "inference": {
                "endpoint": "http://127.0.0.1:9/v1",
                "model": "m",
            },
            "shared_secret": "0123456789abcdef" * 4,
        }
        with mock.patch.object(runner, "ask_model",
                               side_effect=RuntimeError("down")):
            result = answer_as_oracle(cfg, "hello")
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("rejected"), "inference_error")


class ReplTest(unittest.TestCase):
    def _run(self, cfg, lines, answer):
        import contextlib
        from runner import local_test
        buf = io.StringIO()
        queued = iter(lines)

        def fake_input(prompt=""):
            try:
                return next(queued)
            except StopIteration:
                raise EOFError

        with mock.patch.object(local_test, "answer_as_oracle",
                               return_value=answer) as asked, \
             mock.patch("builtins.input", side_effect=fake_input), \
             contextlib.redirect_stdout(buf):
            code = local_test.repl(cfg)
        return code, buf.getvalue(), asked

    def test_an_answer_is_printed(self):
        code, out, asked = self._run({}, ["hello", "quit"], {"answer": "hi"})
        self.assertEqual(code, 0)
        self.assertIn("Oracle> hi", out)
        self.assertEqual(asked.call_count, 1)
        self.assertEqual(asked.call_args[0][1], "hello")

    def test_a_rejection_is_printed(self):
        code, out, asked = self._run({}, ["hello", "q"], {"rejected": "no"})
        self.assertEqual(code, 0)
        self.assertIn("Oracle> rejected:", out)
        self.assertEqual(asked.call_count, 1)

    def test_eof_returns_zero(self):
        code, out, asked = self._run({}, [], {"answer": "hi"})
        self.assertEqual(code, 0)
        self.assertEqual(asked.call_count, 0)

    def test_a_blank_line_is_not_a_question(self):
        code, out, asked = self._run(
            {}, ["", "hello", "exit"], {"answer": "hi"})
        self.assertEqual(code, 0)
        self.assertEqual(asked.call_count, 1)
        self.assertEqual(asked.call_args[0][1], "hello")

    def test_owner_instructions_are_truncated(self):
        text = "I" * 200
        code, out, asked = self._run(
            {"owner_instructions": text}, ["quit"], {"answer": "hi"})
        self.assertEqual(code, 0)
        self.assertIn(text[:120], out)
        self.assertNotIn(text, out)
        self.assertEqual(asked.call_count, 0)


class _ChatTimer:
    started = []

    def __init__(self, delay, fn):
        self.delay = delay
        self.fn = fn
        _ChatTimer.started.append((delay, fn))

    def start(self):
        return None


class _ChatProc:
    built = []

    def __init__(self, args, env=None, **kwargs):
        self.args = args
        self.env = env or {}
        self.terminated = False
        _ChatProc.built.append(self)

    def wait(self):
        raise KeyboardInterrupt

    def terminate(self):
        self.terminated = True


class BrowserChatTest(unittest.TestCase):
    def setUp(self):
        _ChatTimer.started = []
        _ChatProc.built = []

    def _patches(self, stack, start=True, webui=True, popen=None):
        import subprocess
        from runner import local_test
        stack.enter_context(mock.patch.object(
            local_test, "start_si_instance", return_value=start))
        stack.enter_context(mock.patch.object(
            local_test, "_open_webui_available", return_value=webui))
        # browser_chat imports subprocess inside the function. Patch the
        # module attribute, not a name on local_test.
        stack.enter_context(mock.patch.object(
            subprocess, "Popen", popen if popen is not None else _ChatProc))
        stack.enter_context(mock.patch.object(
            local_test.threading, "Timer", _ChatTimer))
        stack.enter_context(mock.patch.object(local_test.webbrowser, "open"))

    def test_a_missing_si_does_not_spawn(self):
        import contextlib
        from runner.local_test import browser_chat
        with contextlib.ExitStack() as stack:
            self._patches(stack, start=False)
            code = browser_chat({})
        self.assertEqual(code, 2)
        self.assertEqual(_ChatProc.built, [])

    def test_a_missing_webui_does_not_spawn(self):
        import contextlib
        from runner.local_test import browser_chat
        buf = io.StringIO()
        with contextlib.ExitStack() as stack, contextlib.redirect_stdout(buf):
            self._patches(stack, start=True, webui=False)
            code = browser_chat({})
        self.assertEqual(code, 2)
        self.assertIn("open-webui", buf.getvalue())
        self.assertEqual(_ChatProc.built, [])

    def test_a_ready_chat_terminates_on_interrupt(self):
        import contextlib
        from runner.local_test import browser_chat
        with contextlib.ExitStack() as stack:
            self._patches(stack)
            code = browser_chat({})
        self.assertEqual(code, 0)
        self.assertEqual(len(_ChatProc.built), 1)
        proc = _ChatProc.built[0]
        self.assertEqual(proc.args, [
            "open-webui", "serve", "--host", "127.0.0.1", "--port", "8080"])
        self.assertIn("11435", proc.env.get("OLLAMA_BASE_URL", ""))
        self.assertTrue(proc.terminated)
        self.assertEqual(len(_ChatTimer.started), 1)
        self.assertEqual(_ChatTimer.started[0][0], 1.5)

    def test_a_custom_port_is_passed_through(self):
        import contextlib
        from runner.local_test import browser_chat
        with contextlib.ExitStack() as stack:
            self._patches(stack)
            code = browser_chat({}, port=9090)
        self.assertEqual(code, 0)
        self.assertEqual(_ChatProc.built[0].args[-1], "9090")

    def test_a_spawn_error_returns_1(self):
        import contextlib
        from runner.local_test import browser_chat
        with contextlib.ExitStack() as stack:
            self._patches(stack, popen=mock.Mock(side_effect=OSError("missing")))
            code = browser_chat({})
        self.assertEqual(code, 1)
        self.assertEqual(_ChatTimer.started, [])












