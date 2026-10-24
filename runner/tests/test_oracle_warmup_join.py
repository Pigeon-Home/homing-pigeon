#!/usr/bin/env python3
"""The --oracle warm-up thread is joined on shutdown (2026-10-16).

The warm-up calls the inference path, which logs into the base
dir. Left as a fire-and-forget daemon, it could still be writing
when oracle_window returned; on Windows that raced the diagnostics
test's temp-dir cleanup (WinError 145: directory not empty) and
failed build-windows while every other job stayed green. The
window now joins the warm-up (bounded) on the way out.
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


class _FakeServer:
    socket = type("S", (), {"getsockname":
                            lambda self: ("127.0.0.1", 11436)})()
    closed = False

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


class WarmupJoinTest(unittest.TestCase):
    def test_window_waits_for_the_warm_up(self):
        done = threading.Event()

        def slow_chat(inf, messages, opener, api_key, timeout):
            time.sleep(0.3)
            done.set()
            return {"role": "assistant", "content": "ok"}

        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434/v1",
                             "model": "llama3.2:3b"}}
        with tempfile.TemporaryDirectory() as d:
            cfg = dict(cfg, base_dir=d)
            buf = StringIO()
            with mock.patch.object(R, "make_oracle_server",
                                   return_value=_FakeServer()), \
                 mock.patch.object(R, "_inference_chat", slow_chat), \
                 redirect_stdout(buf):
                code = R.oracle_window(cfg, cfg_path=None,
                                       open_browser=False)
        self.assertEqual(code, 0)
        self.assertTrue(done.is_set(),
                        "oracle_window returned while its warm-up "
                        "thread was still running")


if __name__ == "__main__":
    unittest.main()
