"""The two files the 3.15.1 measurement left under 90%.

ops/oracle_server.py was 65.8% and ops/mail.py was 83.7%. The
handler lines run in the server's own thread, which that
measurement did not count, and a handful of mail rejects were
never built. These call the handler on this thread and send
the rejects the log already names.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import ExitStack
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.ops import oracle_server  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402
from runner.runner import handle_mail, sign_payload  # noqa: E402

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)


def _status(raw):
    line = raw.split(b"\r\n", 1)[0]
    return int(line.split()[1])


def _body(raw):
    return raw.split(b"\r\n\r\n", 1)[1]


class OracleFloorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-oracle-floor-")
        self.addCleanup(self._close)
        self.httpd = None

    def _close(self):
        if self.httpd is not None:
            self.httpd.server_close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _open(self, cfg=None):
        cfg = cfg if cfg is not None else {"base_dir": self.tmp}
        self.httpd = oracle_server.make_oracle_server(
            cfg, "127.0.0.1", 0, base_dir=self.tmp)
        return self.httpd

    def _handler(self, path, headers=None, body=b"",
                 peer=("127.0.0.1", 9)):
        handler = object.__new__(self.httpd.RequestHandlerClass)
        handler.path = path
        handler.headers = {} if headers is None else dict(headers)
        handler.client_address = peer
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        handler.close_connection = False
        handler.request_version = "HTTP/1.1"
        handler.requestline = "GET " + path + " HTTP/1.1"
        handler.command = "GET" if not path.startswith("/ask") else "POST"
        return handler

    def _ok_headers(self, extra=None):
        headers = {"Host": "127.0.0.1:9"}
        if extra:
            headers.update(extra)
        return headers

    def test_a_garbage_length_is_an_empty_question(self):
        self._open()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": "nope",
                "X-Oracle-Token": self.httpd.oracle_token,
            }))
        handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 200)
        self.assertIn(b"Ask something first", _body(handler.wfile.getvalue()))

    def test_an_oversized_body_is_a_bad_request(self):
        self._open()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": "9000",
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=b"{}")
        handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 400)
        self.assertTrue(handler.close_connection)
        self.assertIn(b"bad request", _body(handler.wfile.getvalue()))

    def test_a_post_that_is_not_an_ask_is_not_found(self):
        self._open()
        handler = self._handler(
            "/other",
            self._ok_headers({"Content-Length": "2"}),
            body=b"{}")
        handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 404)

    def test_a_post_from_anywhere_else_is_forbidden(self):
        self._open()
        handler = self._handler(
            "/ask",
            {"Host": "evil.example", "Content-Length": "2",
             "X-Oracle-Token": self.httpd.oracle_token},
            body=b"{}")
        handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 403)

    def test_a_post_with_the_wrong_token_is_forbidden(self):
        self._open()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": "2",
                "X-Oracle-Token": "nope",
            }),
            body=b"{}")
        handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 403)

    def test_a_question_that_is_not_text_is_empty(self):
        self._open({"base_dir": self.tmp, "oracle_mode": "deterministic"})
        raw = json.dumps({"question": 1}).encode()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 200)
        self.assertIn(b"Ask something first", _body(handler.wfile.getvalue()))

    def test_a_body_that_is_not_json_asks_for_a_question(self):
        self._open()
        raw = b"not json"
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        handler.do_POST()
        self.assertIn(b"Ask something first", _body(handler.wfile.getvalue()))

    def test_a_deterministic_ask_answers_and_a_stuck_log_still_does(self):
        self._open({"base_dir": self.tmp, "oracle_mode": "deterministic"})
        raw = json.dumps({"question": "status?"}).encode()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        with mock.patch.object(
                runner, "record_oracle_turn",
                side_effect=RuntimeError("the log is stuck")):
            handler.do_POST()
        self.assertEqual(_status(handler.wfile.getvalue()), 200)
        payload = json.loads(_body(handler.wfile.getvalue()))
        self.assertIn("answer", payload)
        self.assertIn("Deterministic", payload["answer"])

    def test_status_while_the_oracle_is_thinking(self):
        self._open({"base_dir": self.tmp, "oracle_mode": "deterministic"})
        raw = json.dumps({"question": "status?"}).encode()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        seen = {}

        def answer(cfg, base, watch=None):
            saved_path, saved_file = handler.path, handler.wfile
            handler.path = "/status"
            handler.wfile = io.BytesIO()
            handler.do_GET()
            seen["raw"] = handler.wfile.getvalue()
            handler.path = saved_path
            handler.wfile = saved_file
            return "the record"

        with mock.patch.object(
                runner, "_deterministic_oracle_answer", answer):
            handler.do_POST()
        self.assertEqual(_status(seen["raw"]), 200)
        status = json.loads(_body(seen["raw"]))
        self.assertTrue(status["active"])
        self.assertIsInstance(status["elapsed_sec"], int)
        self.assertGreaterEqual(status["elapsed_sec"], 0)

    def test_a_model_that_raises_is_an_inference_error(self):
        cfg = {
            "base_dir": self.tmp,
            "inference": {
                "endpoint": "http://127.0.0.1:11434",
                "model": "tiny",
            },
        }
        self._open(cfg)
        raw = json.dumps({"question": "status?"}).encode()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        with mock.patch.object(
                runner, "ask_model_agent",
                side_effect=RuntimeError("the model is down")):
            handler.do_POST()
        payload = json.loads(_body(handler.wfile.getvalue()))
        self.assertEqual(payload["rejected"], "inference_error")

    def test_a_model_detail_is_what_the_page_shows(self):
        cfg = {
            "base_dir": self.tmp,
            "inference": {
                "endpoint": "http://127.0.0.1:11434",
                "model": "tiny",
            },
        }
        self._open(cfg)
        raw = json.dumps({"question": "status?"}).encode()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        with mock.patch.object(
                runner, "ask_model_agent",
                return_value={"rejected": "inference_error",
                              "detail": "the model is down"}):
            handler.do_POST()
        payload = json.loads(_body(handler.wfile.getvalue()))
        self.assertEqual(payload["detail"], "the model is down")

    def test_a_reply_that_will_not_encode_is_an_inference_error(self):
        self._open({"base_dir": self.tmp, "oracle_mode": "deterministic"})
        raw = json.dumps({"question": "status?"}).encode()
        handler = self._handler(
            "/ask",
            self._ok_headers({
                "Content-Length": str(len(raw)),
                "X-Oracle-Token": self.httpd.oracle_token,
            }),
            body=raw)
        real = oracle_server.json.dumps

        def flaky(obj, **kwargs):
            if isinstance(obj, dict) and "answer" in obj and "ts" not in obj:
                raise TypeError("not this once")
            return real(obj, **kwargs)

        with mock.patch.object(oracle_server.json, "dumps", flaky):
            handler.do_POST()
        payload = json.loads(_body(handler.wfile.getvalue()))
        self.assertEqual(payload["rejected"], "inference_error")

    def test_status_without_the_token_is_forbidden(self):
        self._open()
        handler = self._handler("/status", self._ok_headers())
        handler.do_GET()
        self.assertEqual(_status(handler.wfile.getvalue()), 403)

    def test_status_when_idle_says_it_is_idle(self):
        self._open()
        handler = self._handler(
            "/status",
            self._ok_headers({"X-Oracle-Token": self.httpd.oracle_token}))
        handler.do_GET()
        status = json.loads(_body(handler.wfile.getvalue()))
        self.assertFalse(status["active"])
        self.assertEqual(status["elapsed_sec"], 0)
        self.assertEqual(status["step"], "")

    def test_status_from_anywhere_else_is_forbidden(self):
        self._open()
        handler = self._handler(
            "/status",
            {"Host": "evil.example",
             "X-Oracle-Token": self.httpd.oracle_token})
        handler.do_GET()
        self.assertEqual(_status(handler.wfile.getvalue()), 403)

    def test_an_unknown_page_is_not_found(self):
        self._open()
        handler = self._handler("/nope", self._ok_headers())
        handler.do_GET()
        self.assertEqual(_status(handler.wfile.getvalue()), 404)

    def test_the_page_itself_is_forbidden_off_the_loopback_name(self):
        self._open()
        handler = self._handler("/", {"Host": "evil.example"})
        handler.do_GET()
        self.assertEqual(_status(handler.wfile.getvalue()), 403)

    def test_the_deterministic_page_names_the_mode(self):
        self._open({"base_dir": self.tmp, "oracle_mode": "deterministic"})
        handler = self._handler("/", self._ok_headers())
        handler.do_GET()
        page = _body(handler.wfile.getvalue())
        self.assertEqual(_status(handler.wfile.getvalue()), 200)
        self.assertIn(b"deterministic", page.lower())
        self.assertIn(self.httpd.oracle_token.encode(), page)

    def test_the_model_page_names_the_model(self):
        self._open({
            "base_dir": self.tmp,
            "inference": {
                "endpoint": "http://127.0.0.1:11434",
                "model": "tiny",
            },
        })
        handler = self._handler("/", self._ok_headers())
        handler.do_GET()
        page = _body(handler.wfile.getvalue())
        self.assertEqual(_status(handler.wfile.getvalue()), 200)
        self.assertIn(b"tiny", page)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raw(job):
    body = jobcrypto.encrypt_body(
        sign_payload(job, SECRET), SECRET,
        job_id=job["job_id"], key_id="", sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


def _ping(job_id, **extra):
    job = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": _now(), "kind": "ping",
    }
    job.update(extra)
    return job


class _IMAP:
    def store(self, *args):
        return "OK", None


class _SMTP:
    transport = None


class MailFloorTest(unittest.TestCase):
    def _cfg(self, directory):
        return {
            "mailbox_user": "t@example.com",
            "shared_secret": SECRET,
            "base_dir": directory,
        }

    def _run(self, job_id, job=None, cfg_extra=None, opts=None,
             policies=None, patch=None):
        notes = []

        def grab(msg, level="INFO"):
            notes.append((level, msg))

        with tempfile.TemporaryDirectory() as directory:
            cfg = self._cfg(directory)
            if cfg_extra:
                cfg.update(cfg_extra)
            raw = _raw(job or _ping(job_id))
            secrets = runner.build_secrets(cfg)
            ctx = patch if patch is not None else mock.MagicMock()
            # MagicMock as a context manager is a no-op enter. Use null.
            if patch is None:
                ctx = mock.patch.object(runner, "log", grab)
            else:
                ctx = ExitStack()
            with ctx:
                if patch is not None:
                    ctx.enter_context(mock.patch.object(runner, "log", grab))
                    for item in patch:
                        ctx.enter_context(item)
                handle_mail(
                    cfg, _IMAP(), _SMTP(), 3, raw, directory, {},
                    secrets, opts, policies)
        return notes

    def _said(self, notes, fragment):
        self.assertTrue(
            any(fragment in msg for _level, msg in notes),
            notes)

    def test_a_torn_envelope_is_refused_once(self):
        def boom(msg, secrets, job_id):
            raise runner.JobCryptoError("torn")

        notes = self._run(
            "crypt1",
            patch=[mock.patch.object(
                runner, "_verify_and_decrypt", boom)])
        self._said(notes, "bad encrypted envelope")

    def test_a_lone_surrogate_in_the_job_is_refused(self):
        real_verify = runner._verify_and_decrypt
        real_lone = runner._textutil._lone_surrogate
        state = {"in": False}

        def verify(*args, **kwargs):
            out = real_verify(*args, **kwargs)
            state["in"] = True
            return out

        def lone(value, _depth=0):
            if state["in"]:
                return True
            return real_lone(value, _depth)

        notes = self._run(
            "surr1",
            patch=[
                mock.patch.object(runner, "_verify_and_decrypt", verify),
                mock.patch.object(runner._textutil, "_lone_surrogate", lone),
            ])
        self._said(notes, "job text carries an unpaired UTF-16 surrogate")

    def test_a_script_cap_that_is_not_a_number_uses_the_default(self):
        notes = self._run(
            "cap1",
            cfg_extra={"max_script_bytes": "nope"},
            opts=Namespace(dry_run=True, no_send=True))
        self._said(notes, "dry-run: would execute job cap1")

    def test_an_unparseable_issued_at_is_refused(self):
        notes = self._run(
            "when1",
            job=_ping("when1", issued_at="not-a-date"))
        self._said(notes, "unparseable issued_at")

    def test_an_issued_at_without_a_timezone_is_refused(self):
        notes = self._run(
            "when2",
            job=_ping("when2", issued_at="2026-10-31T12:00:00"))
        self._said(notes, "issued_at missing timezone")

    def test_a_denied_environment_name_is_refused(self):
        notes = self._run(
            "env1",
            job=_ping("env1", env={"LD_PRELOAD": "x"}),
            cfg_extra={"security": {"modes": {
                "policy_env": "enforce",
                "policy_files": "off",
                "policy_args": "off",
            }}},
            policies={"": {"denied_env": ["LD_PRELOAD"]}})
        self._said(notes, "security policy (policy_env)")

    def test_a_dry_run_does_not_execute(self):
        notes = self._run(
            "dry1",
            opts=Namespace(dry_run=True, no_send=True))
        self._said(notes, "dry-run: would execute job dry1")
        self.assertFalse(any("job dry1 done" in msg for _l, msg in notes))

    def test_a_job_another_worker_already_claimed_is_not_run(self):
        key = "busy1"
        runner._IN_FLIGHT.add(key)
        level = runner._VERBOSE_LEVEL
        runner._set_verbosity(2)
        try:
            notes = self._run("busy1")
        finally:
            runner._IN_FLIGHT.discard(key)
            runner._set_verbosity(level)
        self._said(notes, "another worker claimed it first")

    def test_a_result_already_on_record_is_resent_not_rerun(self):
        cached = {
            "subject": "[HOMING-PIGEON] result busy2",
            "body": "the old result",
            "to": None,
            "completed_at": "2026-10-31T00:00:00Z",
        }
        notes = self._run(
            "busy2",
            opts=Namespace(dry_run=False, no_send=True),
            patch=[mock.patch.object(
                runner, "load_sent_result", return_value=cached)])
        self._said(notes, "result resent from the record")


class CancelFloorTest(unittest.TestCase):
    def test_a_cleartext_cancel_is_refused(self):
        from runner.ops.cancel import handle_cancel_mail
        job_id = "cancel1"
        obj = {
            "v": 1, "type": "cancel", "job_id": job_id,
            "issued_at": _now(),
        }
        msg = EmailMessage()
        msg["Subject"] = "[HOMING-PIGEON] cancel " + job_id
        msg["From"] = "si@example.com"
        msg.set_content(sign_payload(obj, SECRET))
        notes = []
        with tempfile.TemporaryDirectory() as directory:
            cfg = {
                "mailbox_user": "t@example.com",
                "shared_secret": SECRET,
                "base_dir": directory,
            }
            with mock.patch.object(
                    runner, "log",
                    lambda text, level="INFO": notes.append(text)):
                handled = handle_cancel_mail(
                    cfg, _IMAP(), _SMTP(), 1, msg.as_bytes(),
                    msg["Subject"], runner.build_secrets(cfg),
                    Namespace(dry_run=False, no_send=True),
                    directory, {})
        self.assertTrue(handled)
        self.assertTrue(
            any("cleartext refused" in text for text in notes), notes)


if __name__ == "__main__":
    unittest.main()
