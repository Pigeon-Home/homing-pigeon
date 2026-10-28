# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The lines the coverage map last reported as never run, held in process.

The query worker (`runner.ops.queries.worker_main`) runs in a child
the parent kills with SIGKILL when a reply is late, and a process
killed that way never writes its coverage data, so the map showed the
loop as unrun though `test_query_pattern_bound` drives it end to end.
Here the loop runs in this process over byte streams, and the parent's
reply handling meets every malformed reply through a stand-in child.
The rest are the sender's hosted-queue edges: a body that names no
key, a queue URL that is not https, an error whose body cannot be
read, a results answer that is not a list, an item with no envelope,
and the ack that follows only a verified result. Last, two arms the
Linux leg cannot reach on its own: the extension scanner's parse
failure that only 3.9 to 3.11 raise, and the Pi Health sense's
firmware reader and Windows memory reader, each over a stand-in.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import types
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import extreview as XR  # noqa: E402
from runner.ops import exec as EX  # noqa: E402
from runner.wire import verify as V  # noqa: E402
from runner.ops import queries as Q  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"


def _drive_worker(*requests):
    """worker_main over stdin lines; the reply lines, parsed."""
    data = b"".join(r if isinstance(r, bytes) else (json.dumps(r) + "\n").encode()
                    for r in requests)
    stdin = types.SimpleNamespace(buffer=io.BytesIO(data))
    out = io.BytesIO()
    stdout = types.SimpleNamespace(buffer=out)
    with mock.patch.object(Q.sys, "stdin", stdin), \
            mock.patch.object(Q.sys, "stdout", stdout):
        rc = Q.worker_main()
    return rc, [json.loads(line) for line in out.getvalue().splitlines()]


class WorkerLoopTest(unittest.TestCase):
    def test_matches_in_order_and_the_limit_truncates(self):
        rc, replies = _drive_worker(
            {"pattern": "a", "lines": ["a1", "b", "a2", 7, "a3"], "limit": 2})
        self.assertEqual(rc, 0)
        self.assertEqual(replies, [{"matches": ["a1", "a2"], "truncated": True}])

    def test_under_the_limit_is_not_truncated(self):
        _rc, replies = _drive_worker(
            {"pattern": "^x$", "lines": ["x", "xx"], "limit": "5"})
        self.assertEqual(replies, [{"matches": ["x"], "truncated": False}])

    def test_every_bad_request_is_rejected_and_the_loop_goes_on(self):
        _rc, replies = _drive_worker(
            b"not json\n",
            ["a list"],
            {"pattern": 7, "lines": []},
            {"pattern": "a", "lines": "abc"},
            {"pattern": "(", "lines": []},
            {"pattern": "a", "lines": [], "limit": "many"},
            {"pattern": "a", "lines": ["a"], "limit": 1})
        self.assertEqual(replies[:6], [{"rejected": "bad_pattern"}] * 6)
        self.assertEqual(replies[6], {"matches": ["a"], "truncated": False})

    def test_end_of_input_ends_the_loop(self):
        self.assertEqual(_drive_worker(), (0, []))


class _Child:
    """A stand-in for the worker process: stdout replies as given."""

    def __init__(self, reply=b"", alive=True, write_fails=False):
        self.stdin = mock.Mock()
        if write_fails:
            self.stdin.write.side_effect = BrokenPipeError()
        self.stdout = io.BytesIO(reply)
        self.stderr = None
        self.pid = 999999
        self._alive = alive
        self.killed = False

    def poll(self):
        return None if self._alive else 1

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


class GrepRepliesTest(unittest.TestCase):
    def setUp(self):
        Q._drop_worker()
        self.addCleanup(setattr, Q, "_worker", None)

    def grep(self, *children):
        it = iter(children)
        with mock.patch.object(Q, "_start_worker", lambda: next(it)), \
                mock.patch.object(Q, "_stop_worker", lambda proc: None):
            return Q.grep_matches("a", ["a"], 5)   # the module's deadline

    def test_a_good_reply_is_ok(self):
        self.assertEqual(self.grep(_Child(b'{"matches":["a",3],"truncated":1}\n')),
                         ("ok", ["a"], True))

    def test_a_rejection_is_a_bad_pattern(self):
        self.assertEqual(self.grep(_Child(b'{"rejected":"bad_pattern"}\n')),
                         ("bad_pattern",))

    def test_every_malformed_reply_is_a_timeout(self):
        for raw in (b"\xff\xfe\n", b"not json\n", b"[1]\n", b'{"matches":"a"}\n'):
            with self.subTest(raw=raw):
                Q._worker = None
                self.assertEqual(self.grep(_Child(raw)), ("timeout",))

    def test_a_dead_child_with_no_reply_is_a_timeout(self):
        self.assertEqual(self.grep(_Child(b"", alive=False), _Child(b"", alive=False)),
                         ("timeout",))

    def test_a_broken_pipe_starts_a_new_worker(self):
        self.assertEqual(
            self.grep(_Child(write_fails=True), _Child(b'{"matches":[]}\n')),
            ("ok", [], False))

    def test_a_worker_that_cannot_start_is_a_timeout(self):
        def boom():
            raise OSError("no fork")
        with mock.patch.object(Q, "_start_worker", boom), \
                mock.patch.object(Q._runner(), "log", lambda *a, **k: None):
            self.assertEqual(Q.grep_matches("a", ["a"], 1, deadline=1), ("timeout",))
        self.assertIsNone(Q._worker)

    def test_a_late_reply_is_a_timeout(self):
        with mock.patch.object(Q, "_read_line", lambda stream, deadline: None):
            self.assertEqual(self.grep(_Child(b"")), ("timeout",))


class StopWorkerTest(unittest.TestCase):
    def test_none_is_nothing(self):
        Q._stop_worker(None)

    def test_a_finished_child_has_its_streams_closed(self):
        child = _Child(alive=False)
        child.stdin = mock.Mock()
        child.stdin.close.side_effect = ValueError("closed")
        Q._stop_worker(child)
        self.assertTrue(child.stdout.closed)

    def test_a_live_child_is_killed_even_when_the_group_is_gone(self):
        child = _Child()
        child.wait = mock.Mock(side_effect=subprocess.TimeoutExpired("w", 2))
        with mock.patch.object(Q.os, "killpg", side_effect=ProcessLookupError()), \
                mock.patch.object(Q.os, "name", "posix"):
            Q._stop_worker(child)
        child.wait.assert_called_once()

    def test_off_posix_the_child_itself_is_killed(self):
        child = _Child()
        with mock.patch.object(Q.os, "name", "nt"):
            Q._stop_worker(child)
        self.assertTrue(child.killed)


class WorkerArgvTest(unittest.TestCase):
    def test_a_frozen_runner_re_enters_itself(self):
        with mock.patch.object(Q.sys, "frozen", True, create=True):
            self.assertEqual(Q._query_worker_argv(), [sys.executable, "--query-worker"])
        self.assertEqual(Q._query_worker_argv()[1:], ["-m", "runner.ops.queries"])


class NamedKeyTest(unittest.TestCase):
    def test_a_body_names_its_key_or_nothing(self):
        named = SJ.sign_payload({"v": 1, "key_id": "ops"}, SECRET)
        self.assertEqual(SJ._named_key_in(named), "ops")
        self.assertIsNone(SJ._named_key_in(SJ.sign_payload({"key_id": 7}, SECRET)))
        self.assertIsNone(SJ._named_key_in("no signature here"))

    def test_no_secret_and_no_key_is_said(self):
        args = types.SimpleNamespace(secret=None, key_id=None)
        with self.assertRaises(ValueError) as cm:
            SJ._open_body(SJ.sign_payload({"v": 1}, SECRET), args)
        self.assertIn("no --secret", str(cm.exception))


class _Resp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class QueueCallTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"HP_SI_TOKEN": "tok"})
        p.start()
        self.addCleanup(p.stop)

    def test_only_https_or_loopback(self):
        for url in ("http://q.example.test", "ftp://x", 7):
            with self.subTest(url=url), self.assertRaises(SystemExit):
                SJ._queue_call(url, "GET", "/results", opener=lambda *a, **k: None)

    def test_an_http_error_is_its_status_and_body(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 403, "no", {},
                                         io.BytesIO(b"denied"))
        self.assertEqual(SJ._queue_call("https://q.example.test", "GET", "/r",
                                        opener=opener), (403, "denied"))

    def test_an_unreadable_error_body_is_empty(self):
        class Bad(urllib.error.HTTPError):
            def read(self, *a):
                raise OSError("gone")

        def opener(req, timeout):
            raise Bad(req.full_url, 500, "x", {}, None)
        self.assertEqual(SJ._queue_call("http://127.0.0.1:1", "POST", "/r",
                                        opener=opener), (500, ""))

    def test_the_token_goes_in_the_header(self):
        seen = {}

        def opener(req, timeout):
            seen["auth"] = req.get_header("Authorization")
            seen["data"] = req.data
            return _Resp(204, b"")
        SJ._queue_call("https://q.example.test/", "POST", "/a", opener=opener)
        self.assertEqual(seen, {"auth": "Bearer tok", "data": b""})


class ResultsTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"HP_SI_TOKEN": "tok"})
        p.start()
        self.addCleanup(p.stop)

    def run_results(self, answers, ack=False):
        calls = []
        it = iter(answers)

        def opener(req, timeout):
            calls.append((req.get_method(), req.full_url))
            status, body = next(it)
            return _Resp(status, body.encode() if isinstance(body, str) else body)
        args = types.SimpleNamespace(from_queue="https://q.example.test", max=0,
                                     queue_token_env=None, ack=ack,
                                     secret=SECRET, key_id=None)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = SJ.cmd_results(args, opener=opener)
        return rc, [json.loads(x) for x in out.getvalue().splitlines()], calls

    def test_an_answer_that_is_not_a_list_is_two(self):
        for body in ("not json", "[1]"):
            with self.subTest(body=body):
                self.assertEqual(self.run_results([(200, body)])[0], 2)

    def test_a_refused_read_is_two(self):
        self.assertEqual(self.run_results([(500, "boom")])[0], 2)

    def test_items_with_no_envelope_or_a_bad_one_are_named_and_kept(self):
        rc, lines, calls = self.run_results(
            [(200, json.dumps({"results": ["x", {"id": "b", "envelope": 7},
                                          {"id": "c", "envelope": "S: x\n\nnope"}]}))],
            ack=True)
        self.assertEqual(rc, 1)
        self.assertEqual([ln["ok"] for ln in lines], [False, False, False])
        self.assertEqual(lines[1]["error"], "the result carries no envelope")
        self.assertEqual(len(calls), 1)      # nothing unverified is acked

    def test_a_verified_result_is_acked(self):
        body = SJ.sign_payload({"v": 1, "type": "result", "job_id": "j1",
                                "exit_code": 0}, SECRET)
        envelope = "Subject: [HOMING-PIGEON] result j1\n\n" + body
        rc, lines, calls = self.run_results(
            [(200, json.dumps({"results": [{"id": "r/1", "envelope": envelope}]})),
             (204, "")], ack=True)
        self.assertEqual(rc, 0)
        self.assertTrue(lines[0]["acked"])
        self.assertEqual(lines[0]["job_id"], "j1")
        self.assertEqual(calls[0][1], "https://q.example.test/results?max=20")   # no --max is 20
        self.assertEqual(calls[1], ("POST", "https://q.example.test/results/r%2F1/ack"))

    def test_the_subject_names_the_job(self):
        self.assertEqual(SJ._result_job_id("[HOMING-PIGEON] qresult q9"), "q9")
        self.assertIsNone(SJ._result_job_id("[HOMING-PIGEON] result"))
        self.assertIsNone(SJ._result_job_id(None))


class ScannerParseFailureTest(unittest.TestCase):
    def test_a_value_error_from_the_parser_is_a_finding(self):
        for exc in (ValueError("source code string cannot contain null bytes"),
                    RecursionError("too deep")):
            with self.subTest(exc=exc):
                observed, findings, signals = {}, [], {}
                with mock.patch.object(XR.ast, "parse", side_effect=exc):
                    XR._scan_python("x.py", "import socket\n", observed,
                                    findings, signals)
                self.assertEqual(findings[0]["code"], "syntax")
                self.assertIn("does not parse", findings[0]["detail"])
                # the text scan still runs with no tree
                self.assertNotIn("import socket", " ".join(observed.get("network", [])))


def _pi_health():
    path = os.path.join(REPO, "runner", "extensions", "pi-health", "pi_health.py")
    spec = importlib.util.spec_from_file_location("pi_health_cov", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PiHealthReadersTest(unittest.TestCase):
    def setUp(self):
        self.mod = _pi_health()

    def throttled(self, stdout=None, raises=None, exe="/usr/bin/vcgencmd"):
        run = mock.Mock(side_effect=raises) if raises else \
            mock.Mock(return_value=types.SimpleNamespace(stdout=stdout))
        with mock.patch.object(self.mod.shutil, "which", return_value=exe), \
                mock.patch.object(self.mod.subprocess, "run", run):
            return self.mod._read_throttled()

    def test_the_firmware_bitmask_is_read(self):
        self.assertEqual(self.throttled("throttled=0x50005\n"), 0x50005)

    def test_no_tool_no_answer_and_bad_output_are_none(self):
        self.assertIsNone(self.throttled(exe=None))
        self.assertIsNone(self.throttled(raises=OSError("gone")))
        self.assertIsNone(self.throttled(raises=subprocess.TimeoutExpired("v", 5)))
        self.assertIsNone(self.throttled("error=1"))
        self.assertIsNone(self.throttled(None))

    def test_windows_memory_is_a_percent_of_the_total(self):
        import ctypes

        def fill(total, avail, ok=1):
            def call(ref):
                st = ref._obj
                st.ullTotalPhys, st.ullAvailPhys = total, avail
                return ok
            return call
        cases = ((fill(1000, 250), 25.0), (fill(0, 0), None), (fill(10, 5, ok=0), None))
        for fn, want in cases:
            with self.subTest(want=want):
                windll = types.SimpleNamespace(
                    kernel32=types.SimpleNamespace(GlobalMemoryStatusEx=fn))
                with mock.patch.object(self.mod.os, "name", "nt"), \
                        mock.patch.object(ctypes, "windll", windll, create=True):
                    self.assertEqual(self.mod._mem_avail_pct_windows(), want)

    def test_windows_memory_with_no_kernel32_is_none(self):
        import ctypes
        with mock.patch.object(self.mod.os, "name", "nt"), \
                mock.patch.object(ctypes, "windll", types.SimpleNamespace(), create=True):
            self.assertIsNone(self.mod._mem_avail_pct_windows())

    def test_off_windows_is_none(self):
        with mock.patch.object(self.mod.os, "name", "posix"):
            self.assertIsNone(self.mod._mem_avail_pct_windows())


class DoorPolicyEdgesTest(unittest.TestCase):
    """The arms of check_door_policy the door tests do not reach: each
    malformed input is a reason (a refusal), never a pass."""

    def test_an_unknown_door_or_a_bad_key_id_is_refused(self):
        self.assertEqual(V.check_door_policy({}, {"": "s"}, "", "jobs"), "unknown door")
        self.assertEqual(V.check_door_policy({}, {"": "s"}, 7, "query"), "invalid key id")

    def test_a_config_that_is_not_an_object_reads_as_empty(self):
        self.assertIsNone(V.check_door_policy(None, None, "ops", "board"))

    def test_unreadable_policies_refuse(self):
        why = V.check_door_policy({"key_policies": ["not", "a", "map"]}, None,
                                  "ops", "v2")
        self.assertTrue(why.startswith("key policies unreadable"), why)

    def test_with_no_secrets_map_the_name_is_the_entry(self):
        cfg = {"key_policies": {"ops": {"allowed_kinds": ["exec"]}}}
        self.assertEqual(V.check_door_policy(cfg, None, "ops", "query"),
                         "query is not in this key's allowed_kinds")
        cfg["key_policies"]["ops"]["allowed_kinds"].append("query")
        self.assertIsNone(V.check_door_policy(cfg, None, "ops", "query"))


class ReadOutputEdgesTest(unittest.TestCase):
    """_read_output names every failure; none of them raises."""

    def setUp(self):
        import tempfile
        self.work = os.path.realpath(tempfile.mkdtemp(prefix="hp-readout-"))
        self.addCleanup(__import__("shutil").rmtree, self.work, True)
        with open(os.path.join(self.work, "f"), "wb") as fh:
            fh.write(b"0123456789")

    def read(self, limit=100):
        return EX._read_output(self.work, self.work, "f", limit)

    def test_a_plain_file_is_read(self):
        self.assertEqual(self.read(), (b"0123456789", 10, None))

    def test_a_path_that_cannot_resolve_is_unreadable(self):
        with mock.patch.object(EX.os.path, "realpath", side_effect=ValueError("nul")):
            self.assertEqual(self.read(), (None, 0, "unreadable"))

    def test_a_stat_or_open_failure_is_unreadable(self):
        with mock.patch.object(EX.os, "lstat", side_effect=PermissionError()):
            self.assertEqual(self.read(), (None, 0, "unreadable"))
        with mock.patch.object(EX.os, "open", side_effect=PermissionError()):
            self.assertEqual(self.read(), (None, 0, "unreadable"))

    def test_a_file_swapped_between_check_and_open_is_refused(self):
        real = os.fstat

        def other(fd):
            st = real(fd)
            return os.stat_result((st.st_mode, st.st_ino + 1) + tuple(st)[2:])
        with mock.patch.object(EX.os, "fstat", other):
            self.assertEqual(self.read(), (None, 0, "changed while read"))

    def test_a_file_that_grows_past_the_limit_while_read_is_too_large(self):
        real = os.lstat

        def small(path):
            st = real(path)
            t = list(st)
            t[6] = 1                        # st_size as checked
            return os.stat_result(t)
        with mock.patch.object(EX.os, "lstat", small):
            self.assertEqual(self.read(limit=4), (None, 10, "too_large"))


class DtlsRecordTruncationTest(unittest.TestCase):
    """Every header form _RecordSealer.open reads, cut short, is a
    DtlsError; a sealed record still opens."""

    def setUp(self):
        from runner.wire import dtlsproto
        self.D = dtlsproto
        self.sealer = dtlsproto._RecordSealer(b"\x11" * 48)

    def test_a_sealed_record_opens(self):
        rec = self.sealer.seal(3, 23, b"hello", b"\x01\x02")
        opener = self.D._RecordSealer(b"\x11" * 48)
        ctype, content, _seq = opener.open(3, rec)
        self.assertEqual((ctype, content), (23, b"hello"))

    def test_each_short_header_is_refused(self):
        cid, seq16, length = 0x04, 0x10, 0x08
        base = 0x20 | 3
        for rec in (b"",
                    bytes([base | cid]),                  # cid flag, no cid length
                    bytes([base | seq16, 0]),             # 16-bit seq cut
                    bytes([base]),                        # 8-bit seq missing
                    bytes([base | length, 0, 0]),         # 8-bit seq, length cut
                    bytes([base, 0]) + b"x" * 5,          # no length field, body short
                    bytes([base | seq16 | length, 0, 0, 0, 40]) + b"x" * 20):
            with self.subTest(rec=rec), self.assertRaises(self.D.DtlsError):
                self.sealer.open(3, rec)


if __name__ == "__main__":
    unittest.main()
