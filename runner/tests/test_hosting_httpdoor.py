"""UrllibHttp against a loopback server: the one HttpClient that talks.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

Every hosting test plays recorded exchanges through the Player, so the
real client (22 of 28 lines, coverage 2026-10-25) never ran. The
contract it has to keep: a dict or list body goes as JSON with the
content type set, a str as UTF-8, bytes as they are; a 4xx or 5xx is a
Response carrying the status and the server's payload, never an
exception; only a transport failure raises TransportError. Nothing
leaves the box: the server is 127.0.0.1 on an ephemeral port.
"""
import http.server
import json
import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.hosting.httpdoor import TransportError, UrllibHttp  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def _take(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        _Handler.seen.append({"method": self.command, "path": self.path,
                              "type": self.headers.get("Content-Type"),
                              "agent": self.headers.get("User-Agent"),
                              "body": body})
        return body

    def _reply(self, status, payload, ctype="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("X-Echo", self.path)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self._take()
        if self.path.startswith("/missing"):
            self._reply(404, b'{"error": "no such machine"}')
        elif self.path.startswith("/boom"):
            self._reply(503, b"", "text/plain")
        else:
            self._reply(200, json.dumps({"path": self.path}).encode())

    def do_POST(self):
        body = self._take()
        self._reply(201, body or b"{}")

    do_DELETE = do_GET
    do_PUT = do_POST

    def log_message(self, *a):
        pass


class UrllibHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _Handler.seen.clear()
        self.http = UrllibHttp(user_agent="hp-test/1")

    def test_get_returns_status_headers_and_body(self):
        resp = self.http.request("GET", self.base + "/v1/apps")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.json(), {"path": "/v1/apps"})
        self.assertEqual(resp.header("X-Echo"), "/v1/apps")
        self.assertEqual(_Handler.seen[0]["agent"], "hp-test/1")
        self.assertEqual(_Handler.seen[0]["body"], b"")

    def test_dict_body_goes_as_json_with_the_content_type(self):
        resp = self.http.request("POST", self.base + "/v1/machines",
                                 headers={"Authorization": "Bearer t"},
                                 body={"name": "hp-alice", "n": 1})
        self.assertEqual(resp.status, 201)
        sent = _Handler.seen[0]
        self.assertEqual(sent["type"], "application/json")
        self.assertEqual(json.loads(sent["body"]), {"name": "hp-alice", "n": 1})
        self.assertEqual(resp.json(), {"name": "hp-alice", "n": 1})

    def test_list_str_and_bytes_bodies(self):
        self.http.request("POST", self.base + "/l", body=[1, 2])
        self.http.request("POST", self.base + "/s", body="plain text",
                          headers={"Content-Type": "text/plain"})
        self.http.request("PUT", self.base + "/b", body=bytearray(b"\x00\x01"))
        kinds = [(s["path"], s["type"], s["body"]) for s in _Handler.seen]
        self.assertEqual(kinds, [
            ("/l", "application/json", b"[1, 2]"),
            ("/s", "text/plain", b"plain text"),
            # urllib's own default for a body with no type named
            ("/b", "application/x-www-form-urlencoded", b"\x00\x01"),
        ])

    def test_a_caller_content_type_is_kept_for_json(self):
        self.http.request("POST", self.base + "/j", body={"a": 1},
                          headers={"Content-Type": "application/vnd.api+json"})
        self.assertEqual(_Handler.seen[0]["type"], "application/vnd.api+json")

    def test_4xx_is_a_response_with_the_payload(self):
        resp = self.http.request("GET", self.base + "/missing/m1")
        self.assertEqual(resp.status, 404)
        self.assertFalse(resp.ok)
        self.assertEqual(resp.json(), {"error": "no such machine"})
        self.assertEqual(resp.header("X-Echo"), "/missing/m1")

    def test_5xx_with_an_empty_body_is_a_response_too(self):
        resp = self.http.request("DELETE", self.base + "/boom")
        self.assertEqual((resp.status, resp.body), (503, b""))

    def test_connection_refused_is_a_transport_error(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()  # nothing listens here now
        with self.assertRaises(TransportError) as cm:
            self.http.request("GET", "http://127.0.0.1:%d/x" % port,
                              timeout=5)
        self.assertIn("GET http://127.0.0.1:%d/x" % port, str(cm.exception))

    def test_a_bad_url_is_a_transport_error(self):
        # Request() raised ValueError before the try, so a malformed
        # URL escaped the contract (found 2026-10-25).
        with self.assertRaises(TransportError):
            self.http.request("GET", "http://[not-a-host/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
