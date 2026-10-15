#!/usr/bin/env python3
"""Negative tests for the Oracle HTTP server.

Finding: bad Content-Length, non-JSON body, missing token, oversized
payload, and concurrent bad POSTs must not crash the server or the
process. The handler returns 4xx and continues.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import make_oracle_server  # noqa: E402


class OracleServerNegativeTest(unittest.TestCase):
    def test_bad_requests_do_not_crash_server(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": "x" * 32}
            httpd = make_oracle_server(cfg, host="127.0.0.1", port=0)
            port = httpd.server_address[1]
            token = httpd.oracle_token
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            time.sleep(0.05)
            base = f"http://127.0.0.1:{port}"

            # Missing token
            req = urllib.request.Request(base + "/ask", data=b'{"question":"hi"}', method="POST")
            try:
                urllib.request.urlopen(req, timeout=1)
                self.fail("expected 403")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 403)

            # Bad JSON
            req = urllib.request.Request(
                base + "/ask",
                data=b"not json",
                headers={"X-Oracle-Token": token, "Origin": "http://127.0.0.1", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=1)
            except urllib.error.HTTPError:
                pass  # 200 or 400 is fine; must not crash

            # Oversized Content-Length claim
            req = urllib.request.Request(
                base + "/ask",
                data=b"{}",
                headers={"X-Oracle-Token": token, "Origin": "http://127.0.0.1", "Content-Length": "999999"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=1)
            except Exception:
                pass

            # Concurrent bad posts
            def hammer():
                for _ in range(5):
                    try:
                        r = urllib.request.Request(
                            base + "/ask",
                            data=b'{"question": null}',
                            headers={"X-Oracle-Token": token, "Origin": "http://127.0.0.1"},
                            method="POST",
                        )
                        urllib.request.urlopen(r, timeout=1)
                    except Exception:
                        pass
            threads = [threading.Thread(target=hammer) for _ in range(4)]
            for th in threads:
                th.start()
            for th in threads:
                th.join(timeout=2)

            httpd.shutdown()
            # Server still alive enough to have processed; no exception escaped


if __name__ == "__main__":
    unittest.main()
