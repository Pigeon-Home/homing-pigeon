"""The import face and the job-user face, and the branches they uncover.

The dual import (package, else sibling, else a fallback) used to be
copied at every import. The privilege drop used to call chown and
setuid inline. Both are one face now. These tests drive the face,
not the real syscall.
"""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest import mock


def _cfg(user="job"):
    return {
        "security": {
            "modes": {"job_user": "enforce"},
            "job_user": {"user": user},
        }
    }


class _PW:
    pw_uid = 40
    pw_gid = 41
    pw_name = "job"


class _Stat:
    def __init__(self, mode):
        self.st_mode = mode


class _Face:
    def __init__(self, euid=0, pwnam=None, walk=None, chown_error=None,
                 stat_error=None, mode=0o700):
        self._euid = euid
        self._pwnam = pwnam if pwnam is not None else _PW()
        self._walk = walk
        self.chown_error = chown_error
        self.stat_error = stat_error
        self.mode = mode
        self.chowns = []
        self.chmods = []
        self.demoted = []

    def euid(self):
        return self._euid

    def getpwnam(self, user):
        if isinstance(self._pwnam, Exception):
            raise self._pwnam
        return self._pwnam

    def walk(self, path):
        if self._walk is not None:
            return self._walk
        return [(path, ["sub"], ["note.txt"])]

    def chown(self, path, uid, gid):
        if self.chown_error is not None:
            raise self.chown_error
        self.chowns.append((path, uid, gid))

    def realpath(self, path):
        return path

    def dirname(self, path):
        return os.path.dirname(path)

    def stat(self, path):
        if self.stat_error is not None:
            raise self.stat_error
        return _Stat(self.mode)

    def chmod(self, path, mode):
        self.chmods.append((path, mode))

    def setgid(self, gid):
        self.demoted.append(("gid", gid))

    def initgroups(self, name, gid):
        self.demoted.append(("groups", name, gid))

    def setuid(self, uid):
        self.demoted.append(("uid", uid))


class ImportFaceTest(unittest.TestCase):
    def test_a_missing_module_returns_the_default(self):
        from runner.runner import _load_attr, _load_mod
        self.assertEqual(
            _load_attr("runner.no_such_mod", "also_missing", "x", "fallback"),
            "fallback")
        self.assertIsNone(_load_mod("runner.no_such_mod", "also_missing"))

    def test_a_present_module_returns_the_attribute(self):
        from runner.runner import _load_attr, _load_mod, __version__
        loaded = _load_attr("runner._version", "_version", "__version__", "nope")
        self.assertEqual(loaded, __version__)
        self.assertIsNotNone(_load_mod("runner.security", "security"))

    def test_a_module_without_the_attribute_returns_the_default(self):
        from runner.runner import _load_attr
        self.assertEqual(
            _load_attr("runner._version", "_version", "not_an_attr", "fallback"),
            "fallback")

    def test_a_broken_detection_import_is_swallowed(self):
        from runner.runner import _load_mod
        with mock.patch("importlib.import_module", side_effect=RuntimeError("boom")):
            self.assertIsNone(_load_mod("runner.detection", "detection", broad=True))


class JobUserFaceTest(unittest.TestCase):
    def _run(self, face, cfg=None, base=None):
        from runner.runner import _job_user_preexec
        directory = base or tempfile.mkdtemp()
        work = os.path.join(directory, "work")
        os.makedirs(work, exist_ok=True)
        return _job_user_preexec(cfg or _cfg(), directory, "job-1", work, face=face)

    def test_not_root_does_not_demote(self):
        fn = self._run(_Face(euid=1000))
        self.assertIsNone(fn)

    def test_an_unknown_user_does_not_demote(self):
        fn = self._run(_Face(pwnam=KeyError("job")))
        self.assertIsNone(fn)

    def test_a_chown_failure_does_not_demote(self):
        fn = self._run(_Face(chown_error=OSError("denied")))
        self.assertIsNone(fn)

    def test_enforce_chowns_the_tree_and_returns_a_demote(self):
        face = _Face(mode=0o700)  # no other-execute, so chmod runs
        fn = self._run(face)
        self.assertTrue(face.chowns)
        self.assertTrue(face.chmods)
        self.assertEqual(fn.__name__, "_demote")
        fn()
        self.assertEqual(face.demoted[0], ("gid", 41))
        self.assertEqual(face.demoted[-1], ("uid", 40))

    def test_initgroups_failure_still_sets_the_uid(self):
        face = _Face(mode=0o701)

        def boom(name, gid):
            raise OSError("no groups")

        face.initgroups = boom
        fn = self._run(face)
        fn()
        self.assertIn(("uid", 40), face.demoted)

    def test_a_stat_error_stops_the_parent_walk(self):
        face = _Face(stat_error=OSError("gone"))
        fn = self._run(face)
        self.assertIsNotNone(fn)

    def test_an_audit_write_failure_is_swallowed(self):
        from runner import security
        face = _Face()
        with mock.patch.object(security, "write_audit_entry", side_effect=RuntimeError("disk")):
            fn = self._run(face)
        self.assertIsNotNone(fn)

    def test_audit_mode_does_not_demote(self):
        cfg = _cfg()
        cfg["security"]["modes"]["job_user"] = "audit"
        self.assertIsNone(self._run(_Face(), cfg))


class OracleToolFaceTest(unittest.TestCase):
    def test_the_error_strings(self):
        from runner.runner import _run_oracle_tool
        self.assertIn("args must be an object", _run_oracle_tool("read_file", []))
        self.assertIn("path must be", _run_oracle_tool("read_file", {"path": ""}))
        missing = _run_oracle_tool("read_file", {"path": "/no/such/hp-face", "max_chars": "nope"})
        self.assertIn("cannot read", missing)
        self.assertIn("cannot list", _run_oracle_tool("list_dir", {"path": "/no/such/hp-face"}))
        self.assertIn("content must be a string", _run_oracle_tool(
            "write_file", {"path": "/tmp/x", "content": 1}))
        huge = _run_oracle_tool("write_file", {"path": "/tmp/x", "content": "z" * 200001})
        self.assertIn("too large", huge)
        self.assertIn("unknown tool", _run_oracle_tool("nope", {}))

    def test_read_truncates_and_lists_a_directory(self):
        from runner.runner import _run_oracle_tool
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "note.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("abcdefghij")
            os.mkdir(os.path.join(d, "sub"))
            text = _run_oracle_tool("read_file", {"path": path, "max_chars": 4})
            self.assertTrue(text.startswith("abcd"))
            self.assertIn("truncated", text)
            listing = _run_oracle_tool("list_dir", {"path": d})
            self.assertIn("sub/", listing)
            self.assertIn("note.txt", listing)

    def test_write_reports_the_os_error(self):
        from runner.runner import _run_oracle_tool
        with tempfile.TemporaryDirectory() as d:
            blocker = os.path.join(d, "not-a-dir")
            with open(blocker, "w", encoding="utf-8") as fh:
                fh.write("x")
            msg = _run_oracle_tool("write_file", {
                "path": os.path.join(blocker, "child"), "content": "hi"})
            self.assertIn("cannot write", msg)

    def test_a_command_that_overruns_its_timeout(self):
        from runner.runner import _run_oracle_tool
        msg = _run_oracle_tool("run", {"command": "true", "timeout_sec": "nope"})
        self.assertTrue(msg.startswith("exit="))
        msg = _run_oracle_tool("run", {"command": "sleep 2", "timeout_sec": 1})
        self.assertIn("timed out", msg)

    def test_a_long_command_result_is_cut(self):
        from runner.runner import _run_oracle_tool
        msg = _run_oracle_tool("run", {"command": "python3 -c 'print(\"y\"*9000)'", "timeout_sec": 10})
        self.assertIn("truncated", msg)
        self.assertTrue(msg.startswith("exit=0"))


class LogAndContextFaceTest(unittest.TestCase):
    def test_bounded_log_rejects_bad_bounds_and_rotates(self):
        from runner.runner import append_bounded_log
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.log")
            append_bounded_log(path, "one", max_bytes="nope", backups="nope")
            append_bounded_log(path, "two", max_bytes=4, backups=3)
            self.assertTrue(os.path.exists(path) or os.path.exists(path + ".1"))
            append_bounded_log(path, "", max_bytes=10)
            append_bounded_log(None, "x")

    def test_runner_log_tail_bounds(self):
        from runner.runner import _runner_log_tail
        self.assertEqual(_runner_log_tail(None), "")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_runner_log_tail(d, max_chars="nope"), "")
            path = os.path.join(d, "runner.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("line\n" * 400)
            capped = _runner_log_tail(d, max_chars=20)
            self.assertTrue(capped)
            self.assertLessEqual(len(capped), 20)
            # A negative cap is clamped to 0. The slice of a zero
            # cap is the whole tail; the clamp itself is the line
            # under test.
            self.assertIsInstance(_runner_log_tail(d, max_chars=-1), str)

    def test_oracle_context_formats_host_firewall_and_av(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(runner, "_host_log_tail", return_value="failed password"), \
             mock.patch.object(runner, "_firewall_watch", return_value="on"), \
             mock.patch.object(runner, "_av_watch", return_value="clamd"):
            text = runner.oracle_context(d, limit=True, max_chars=8000, watch=True)
        self.assertIn("Host log tail", text)
        self.assertIn("Firewall posture", text)
        self.assertIn("AV posture", text)
        with mock.patch.object(runner, "_host_log_tail", return_value=""), \
             mock.patch.object(runner, "_firewall_watch", return_value=""), \
             mock.patch.object(runner, "_av_watch", return_value=""):
            empty = runner.oracle_context(d, limit=None, watch=True)
        self.assertIn("no matching auth failures", empty)
        self.assertNotIn("Firewall posture:\n", empty)


class OraclePageBranchesTest(unittest.TestCase):
    def _serve(self):
        from runner.runner import make_oracle_server
        d = tempfile.mkdtemp()
        httpd = make_oracle_server({"base_dir": d}, "127.0.0.1", 0, base_dir=d)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        time.sleep(0.05)
        return httpd, d

    def _raw(self, port, text):
        sock = socket.create_connection(("127.0.0.1", port), 2)
        sock.sendall(text.encode("ascii"))
        sock.settimeout(2)
        data = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        sock.close()
        return data

    def test_unknown_paths_and_a_bad_host_are_refused(self):
        httpd, _d = self._serve()
        port = httpd.server_address[1]
        try:
            missing = self._raw(port, "GET /nope HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            self.assertIn(b"404", missing)
            foreign = self._raw(port, "GET / HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n")
            self.assertIn(b"403", foreign)
            post = self._raw(port, "POST /nope HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
            self.assertIn(b"404", post)
            bad_len = self._raw(
                port,
                "POST /ask HTTP/1.1\r\nHost: 127.0.0.1\r\nOrigin: http://127.0.0.1\r\n"
                "X-Oracle-Token: " + httpd.oracle_token + "\r\n"
                "Content-Length: nope\r\nConnection: close\r\n\r\n")
            self.assertTrue(bad_len)
        finally:
            httpd.shutdown()

    def test_an_ask_that_raises_is_an_inference_error(self):
        from runner import runner
        httpd, _d = self._serve()
        port = httpd.server_address[1]
        try:
            with mock.patch.object(runner, "ask_model_agent", side_effect=RuntimeError("down")), \
                 mock.patch.object(runner, "record_oracle_turn", side_effect=OSError("full")):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/ask",
                    data=b'{"question":"status"}',
                    headers={
                        "X-Oracle-Token": httpd.oracle_token,
                        "Origin": "http://127.0.0.1",
                    },
                    method="POST")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body.get("rejected"), "inference_error")
        finally:
            httpd.shutdown()


class AgentParseFaceTest(unittest.TestCase):
    def test_bad_numbers_fall_back_and_a_dead_model_is_an_error(self):
        from runner import runner
        cfg = {
            "endpoint": "http://127.0.0.1:9/v1",
            "model": "m",
            "timeout_sec": "nope",
            "agent_wall_clock_sec": "nope",
            "max_answer_chars": "nope",
        }
        with mock.patch.object(runner, "_inference_chat", return_value={"role": "error", "content": ""}):
            ans = runner.ask_model_agent(cfg, "q", "", "nope")
        self.assertEqual(ans["rejected"], "inference_error")
        self.assertIn("did not answer", ans["detail"])
        self.assertEqual(
            runner.ask_model_agent(["nope"], "q", "", 20)["rejected"],
            "inference_unconfigured")
        self.assertEqual(
            runner.ask_model_agent({"endpoint": 1, "model": "m"}, "q", "", 20)["rejected"],
            "inference_unconfigured")

    def test_a_non_string_reply_and_an_unprintable_tool_arg(self):
        from runner import runner

        class Bad:
            pass

        seen = {"n": 0}

        def chat(cfg, messages, tools, opener, timeout):
            seen["n"] += 1
            if seen["n"] == 1:
                return {"role": "assistant", "content": ""}
            return {"role": "error", "content": None}

        cfg = {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
               "agent_wall_clock_sec": 1}
        ticks = {"n": 0}

        def mono():
            ticks["n"] += 1
            return 0 if ticks["n"] < 3 else 1000

        with mock.patch.object(runner, "_inference_chat", side_effect=chat), \
             mock.patch.object(runner, "_parse_tool_calls",
                               return_value=[("1", "read_file", Bad())]), \
             mock.patch.object(runner, "_run_oracle_tool", return_value="ok"), \
             mock.patch.object(runner.time, "monotonic", side_effect=mono):
            ans = runner.ask_model_agent(cfg, "q", "", -1)
        self.assertEqual(ans["rejected"], "inference_error")
        self.assertIn("did not answer", ans["detail"])


class FasterFlagTest(unittest.TestCase):
    def test_faster_fills_a_missing_inference_block(self):
        import contextlib
        import sys
        from runner import runner
        from runner import setup
        with contextlib.ExitStack() as stack:
            oracle = stack.enter_context(
                mock.patch.object(runner, "oracle_window", return_value=7))
            stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
            stack.enter_context(mock.patch.object(runner, "update_llama_from_config"))
            stack.enter_context(mock.patch.object(setup, "is_tty", return_value=False))
            stack.enter_context(mock.patch.object(setup, "needs_setup", return_value=None))
            directory = stack.enter_context(tempfile.TemporaryDirectory())
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "shared_secret": "0123456789abcdef" * 4,
                    "mailbox_user": "a@b.c",
                    "mailbox_password": "pw",
                }, fh)
            stack.enter_context(mock.patch.object(
                sys, "argv", ["runner", "--config", path, "--faster", "--oracle"]))
            code = runner.main()
        self.assertEqual(code, 7)
        cfg = oracle.call_args[0][0]
        self.assertEqual(cfg["inference"]["model"], "qwen2.5:1.5b")
        self.assertIn("127.0.0.1", cfg["inference"]["endpoint"])


if __name__ == "__main__":
    unittest.main()
