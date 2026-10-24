"""Tests for the strictness batch: the code brought up to
what the specification already states.

- II-3: `v` is the Integer 1 (draft Section 9). JSON true and
  1.0 are equal to 1 under == but they are not the integer,
  and they no longer pass as protocol version 1.
- II-4: key selection (draft Section 10). A present key_id
  that is not a string in the map is rejected before the MAC
  is computed; it no longer falls back to the default secret.
  Absent still selects the default, and the empty string --
  the default secret's own identifier -- still names it.
- II-5: the DTLS endpoints enforce the shared-secret entropy
  floor (draft Section 19.2). The sender's gate already
  existed (send_dtls.py via send_job.require_signable_secret)
  and is pinned here; the runner-side DTLS extension now
  refuses to start on sub-floor PSK material.
- II-6: malformed DTLS records that used to be dropped
  silently are logged at WARN. Wire behavior is unchanged:
  a drop is still a drop, and nothing is answered.
- BC-3: downloads are HTTPS only (PROTOCOL Sections 6/7,
  draft Section 11.4) at the one download() every route --
  files[] entries and script_url -- funnels through,
  redirects included.
"""

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.request import Request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.wire import dtlsproto  # noqa: E402
from runner.runner import (  # noqa: E402
    JobRejected, _NoForeignRedirect, _version_ok, download,
    execute_job, sign_payload, verify_body_keyed)
import send_dtls  # noqa: E402

dtls_ext = importlib.import_module(
    "runner.transport_extensions.dtls.__main__")

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
SECRET2 = "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
ADDR = ("127.0.0.1", 50001)
NOW = 1000.0


def _job(**over):
    payload = {"v": 1, "type": "job", "kind": "ping",
               "job_id": "strict-1"}
    payload.update(over)
    return payload


# ------------------------------------------------------------------
# II-3: the version member is the Integer 1
# ------------------------------------------------------------------

class VersionStrictnessTest(unittest.TestCase):
    def test_integer_one_is_accepted(self):
        self.assertTrue(_version_ok(1))

    def test_true_is_not_version_one(self):
        # JSON true == 1 in Python; it is not the Integer 1.
        self.assertFalse(_version_ok(True))

    def test_float_is_not_version_one(self):
        self.assertFalse(_version_ok(1.0))

    def test_other_shapes_are_not_version_one(self):
        for v in (False, 0, 2, -1, "1", None, [1], {"v": 1}, 1.5):
            self.assertFalse(_version_ok(v), repr(v))


# ------------------------------------------------------------------
# II-4: key selection follows draft Section 10
# ------------------------------------------------------------------

class KeySelectionStrictnessTest(unittest.TestCase):
    SECRETS = {"": SECRET, "field": SECRET2}

    def test_absent_key_id_selects_the_default(self):
        body = sign_payload(_job(), SECRET)
        payload, key_id = verify_body_keyed(body, self.SECRETS)
        self.assertEqual(key_id, "")
        self.assertEqual(payload["job_id"], "strict-1")

    def test_empty_key_id_names_the_default(self):
        # Draft Section 10: "The empty identifier names the
        # default secret" -- present-and-in-the-map selects it.
        body = sign_payload(_job(key_id=""), SECRET)
        _payload, key_id = verify_body_keyed(body, self.SECRETS)
        self.assertEqual(key_id, "")

    def test_valid_named_key_id_selects_its_secret(self):
        body = sign_payload(_job(key_id="field"), SECRET2)
        _payload, key_id = verify_body_keyed(body, self.SECRETS)
        self.assertEqual(key_id, "field")

    def test_null_key_id_is_rejected_not_defaulted(self):
        # Signed with the default secret: before the fix the
        # null silently selected that very secret and verified.
        body = sign_payload(_job(key_id=None), SECRET)
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(body, self.SECRETS)
        self.assertIn("unknown key_id", str(cm.exception))

    def test_falsy_and_nonstring_key_ids_are_rejected(self):
        for bad in (False, 0, 1, 1.5, [], {}, ["field"]):
            body = sign_payload(_job(key_id=bad), SECRET)
            with self.assertRaises(ValueError, msg=repr(bad)):
                verify_body_keyed(body, self.SECRETS)

    def test_a_rejected_key_id_never_falls_through_to_a_secret(self):
        # Signed with the NAMED secret under a null key_id: the
        # receiver must not try the named secret either.
        body = sign_payload(_job(key_id=None), SECRET2)
        with self.assertRaises(ValueError):
            verify_body_keyed(body, self.SECRETS)

    def test_unknown_string_key_id_is_rejected(self):
        body = sign_payload(_job(key_id="no-such-key"), SECRET)
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(body, self.SECRETS)
        self.assertIn("unknown key_id", str(cm.exception))


# ------------------------------------------------------------------
# BC-3: downloads are HTTPS only
# ------------------------------------------------------------------

class _Body:
    def __init__(self, data):
        self.data = data

    def read(self, n):
        chunk, self.data = self.data[:n], self.data[n:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class DownloadHttpsOnlyTest(unittest.TestCase):
    def test_http_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out")
            with self.assertRaises(JobRejected) as cm:
                download("http://example.test/a", dest)
            self.assertIn("unsupported url scheme",
                          str(cm.exception))
            self.assertFalse(os.path.exists(dest))

    def test_non_https_shapes_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out")
            for url in ("HTTP://example.test/a",
                        "ftp://example.test/a",
                        "file:///etc/passwd",
                        "https:example.test/a", "", None, 42):
                with self.assertRaises(JobRejected, msg=repr(url)):
                    download(url, dest)

    def test_https_still_downloads(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out")
            with mock.patch("runner.runner._open_download",
                            return_value=_Body(b"abcdef")):
                download("https://example.test/a", dest)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"abcdef")

    def test_a_redirect_may_not_downgrade_to_http(self):
        handler = _NoForeignRedirect()
        req = Request("https://example.test/a")
        for target in ("http://example.test/b",
                       "ftp://example.test/b", None):
            with self.assertRaises(JobRejected, msg=repr(target)):
                handler.redirect_request(
                    req, None, 302, "Found", {}, target)

    def test_a_redirect_to_https_is_allowed(self):
        handler = _NoForeignRedirect()
        req = Request("https://example.test/a")
        new = handler.redirect_request(
            req, None, 302, "Found", {}, "https://example.test/b")
        self.assertEqual(new.full_url, "https://example.test/b")

    def test_a_files_entry_with_an_http_url_fails_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(JobRejected) as cm:
                execute_job({}, {
                    "kind": "exec", "job_id": "dl-http",
                    "script": "echo hi",
                    "files": [{"name": "a.txt",
                               "url": "http://example.test/a"}],
                }, d)
            self.assertIn("unsupported url scheme",
                          str(cm.exception))

    def test_a_script_url_with_http_fails_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(JobRejected) as cm:
                execute_job({}, {
                    "kind": "exec", "job_id": "sdl-http",
                    "script_url": "http://example.test/s",
                }, d)
            self.assertIn("unsupported url scheme",
                          str(cm.exception))


# ------------------------------------------------------------------
# II-5: the DTLS endpoints enforce the entropy floor
# ------------------------------------------------------------------

class DtlsSecretFloorTest(unittest.TestCase):
    def test_the_sender_refuses_a_short_secret(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = send_dtls.main(
                ["--host", "127.0.0.1", "--secret", "weak"])
        self.assertEqual(rc, 2)
        self.assertIn("secret refused", err.getvalue())

    def test_the_sender_refuses_a_patterned_secret(self):
        # Long but periodic: the estimate alone would pass it,
        # the pattern check is part of the same floor.
        with contextlib.redirect_stderr(io.StringIO()):
            rc = send_dtls.main(
                ["--host", "127.0.0.1", "--secret", "abc" * 30])
        self.assertEqual(rc, 2)

    def test_the_extension_floor_accepts_strong_material(self):
        self.assertIsNone(
            dtls_ext._psk_floor_problem({"shared_secret": SECRET}))
        self.assertIsNone(dtls_ext._psk_floor_problem({
            "shared_secret": SECRET,
            "additional_secrets": {"field": SECRET2}}))

    def test_the_extension_floor_flags_a_weak_default(self):
        problem = dtls_ext._psk_floor_problem(
            {"shared_secret": "weak"})
        self.assertIsNotNone(problem)
        self.assertIn("shared_secret", problem)

    def test_the_extension_floor_flags_a_weak_additional(self):
        problem = dtls_ext._psk_floor_problem({
            "shared_secret": SECRET,
            "additional_secrets": {"field": "weak"}})
        self.assertIsNotNone(problem)
        self.assertIn("additional_secrets", problem)
        self.assertIn("field", problem)

    def test_the_extension_floor_flags_a_patterned_secret(self):
        self.assertIsNotNone(dtls_ext._psk_floor_problem(
            {"shared_secret": "abc" * 30}))

    def _run_extension(self, cfg_dict):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-floor-")
        cfg_path = os.path.join(tmp, "runtime-config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f)
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get(
            "PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m",
             "runner.transport_extensions.dtls", tmp, cfg_path],
            capture_output=True, text=True, timeout=30, env=env)

    def test_the_extension_process_refuses_a_weak_secret(self):
        proc = self._run_extension({"shared_secret": "weak"})
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("refusing to start", proc.stderr)

    def test_the_extension_process_refuses_a_weak_additional(self):
        proc = self._run_extension({
            "shared_secret": SECRET,
            "additional_secrets": {"field": "weak"}})
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("refusing to start", proc.stderr)


# ------------------------------------------------------------------
# II-6: malformed DTLS records are logged, not silently dropped
# ------------------------------------------------------------------

class _Log:
    def __init__(self):
        self.lines = []

    def __call__(self, msg, level="INFO"):
        self.lines.append((level, msg))

    def text(self):
        return "\n".join(msg for _level, msg in self.lines)

    def warned(self, needle):
        return any(level == "WARN" and needle in msg
                   for level, msg in self.lines)


def _pump(client, server, addr=ADDR, now=NOW):
    out = client.start(now)
    for _ in range(60):
        if not out:
            break
        nxt = []
        for dg in out:
            nxt += server.feed(dg, addr, now)
        out = []
        for dg in nxt:
            out += client.feed(dg, now)
    return out


def _established_pair(log=None):
    server = dtlsproto.DtlsServerCore(
        secret_lookup=dtlsproto.make_secret_lookup(SECRET),
        greeting_for=lambda s: b'{"type":"greeting","v":1}',
        log=log)
    client = dtlsproto.DtlsClientCore(SECRET)
    _pump(client, server)
    assert client.state == "established"
    return client, server


class DtlsDropLoggingTest(unittest.TestCase):
    def test_client_logs_a_record_that_does_not_decrypt(self):
        log = _Log()
        client = dtlsproto.DtlsClientCore(SECRET, log=log)
        client.start(NOW)
        record = (bytes([0x20 | 0x10 | 0x08 | 0x03])
                  + (1).to_bytes(2, "big")
                  + (40).to_bytes(2, "big") + b"\xaa" * 40)
        self.assertEqual(client.feed(record, NOW), [])
        self.assertTrue(log.warned("did not decrypt"))
        self.assertFalse(client.dead)

    def test_client_logs_a_plaintext_non_handshake_record(self):
        log = _Log()
        client = dtlsproto.DtlsClientCore(SECRET, log=log)
        record = dtlsproto._plaintext_record(23, 0, 0, b"junk")
        self.assertEqual(client.feed(record, NOW), [])
        self.assertTrue(log.warned("not a handshake or an alert"))

    def test_client_logs_a_malformed_key_update(self):
        log = _Log()
        client = dtlsproto.DtlsClientCore(SECRET, log=log)
        self.assertEqual(client._handle_key_update(3, b"\x07"), [])
        self.assertTrue(log.warned("KeyUpdate"))

    def test_client_logs_a_malformed_session_ticket(self):
        log = _Log()
        client = dtlsproto.DtlsClientCore(SECRET, log=log)
        client._on_ticket(b"\x00", NOW)
        self.assertTrue(log.warned("NewSessionTicket"))
        self.assertIsNone(client.ticket)

    def test_client_logs_an_unknown_handshake_type(self):
        log = _Log()
        client = dtlsproto.DtlsClientCore(SECRET, log=log)
        out = client._on_handshake_bytes(
            dtlsproto._hs_message(99, b"", 0), NOW, 0)
        self.assertEqual(out, [])
        self.assertTrue(log.warned("unexpected handshake"))

    def test_server_logs_a_plaintext_non_handshake_record(self):
        log = _Log()
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            log=log)
        record = dtlsproto._plaintext_record(23, 0, 0, b"x")
        self.assertEqual(server.feed(record, ADDR, NOW), [])
        self.assertTrue(log.warned("not a handshake"))

    def test_server_logs_a_malformed_client_hello(self):
        log = _Log()
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            log=log)
        record = dtlsproto._plaintext_record(
            22, 0, 0, dtlsproto._hs_message(1, b"\x00\x01", 0))
        self.assertEqual(server.feed(record, ADDR, NOW), [])
        self.assertTrue(log.warned("malformed ClientHello"))

    def test_server_logs_a_tampered_session_record(self):
        log = _Log()
        client, server = _established_pair(log=log)
        (session,) = list(server.sessions.values())
        record = bytearray(client.send_app(b"hello")[0])
        record[-1] ^= 0xFF
        self.assertEqual(server.feed(bytes(record), ADDR, NOW),
                         [])
        self.assertTrue(log.warned("did not decrypt"))
        # The drop is logged, the session survives: the next
        # well-formed record is delivered as an app event.
        before = len(server.events)
        server.feed(client.send_app(b"again")[0], ADDR, NOW)
        self.assertTrue(any(e[0] == "app"
                            for e in server.events[before:]))
        self.assertFalse(session.dead)

    def test_server_session_logs_an_unknown_handshake_type(self):
        log = _Log()
        _client, server = _established_pair(log=log)
        (session,) = list(server.sessions.values())
        out = session._on_handshake_bytes(
            dtlsproto._hs_message(99, b"", 0), NOW, 3)
        self.assertEqual(out, [])
        self.assertTrue(log.warned("unexpected handshake"))


if __name__ == "__main__":
    unittest.main()
