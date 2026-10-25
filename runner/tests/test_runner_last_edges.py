"""The last dark lines in runner.py: platform flags, swallowed
errors, and the local-signal front end.

O_BINARY is set to 0 so the Windows flag line runs without
changing the open flags on Linux. No mailbox and no model.
"""

import contextlib
import io
import json
import os
import signal
import subprocess
import threading
import socket
import sys
import tempfile
import types
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
from runner.wire import jobcrypto  # noqa: E402

sys.path.insert(0, os.path.join(_REPO, "runner", "cloud"))
from send_job import sign_payload  # noqa: E402

KEY_A = "alpha-" + "a1" * 28
KEY_B = "bravo-" + "b2" * 28


class _Binary:
    def setUp(self):
        self._had = hasattr(os, "O_BINARY")
        os.O_BINARY = 0

    def tearDown(self):
        if not self._had and hasattr(os, "O_BINARY"):
            del os.O_BINARY


class PureEdgeTest(_Binary, unittest.TestCase):
    def test_small_refusals(self):
        self.assertIsNone(rr._report_event_fallback("x"))
        self.assertEqual(rr._normalize(3), "")
        with mock.patch.object(rr, "_append_security_event",
                               side_effect=OSError("disk")):
            rr._note_resource_event("/tmp", {
                "resources": {"cpu": "nope"}, "threshold": "x"})
        with self.assertRaises(RuntimeError):
            rr._host([], "imap_host")
        with self.assertRaises(RuntimeError):
            rr._mailbox([])
        self.assertEqual(rr._as_float(float("nan"), 1.0), 1.0)
        self.assertEqual(rr._as_float(float("inf"), 1.0), 1.0)
        self.assertEqual(rr._preview("abc", "nope"), "abc")
        self.assertEqual(rr._preview("abcdef", 0), "abcdef")
        self.assertTrue(rr._local_signals_enabled([]))
        self.assertEqual(rr._local_signal_port([]),
                         rr.LOCAL_SIGNAL_DEFAULT_PORT)
        self.assertEqual(rr._local_signal_port({"local_signal_port": True}),
                         rr.LOCAL_SIGNAL_DEFAULT_PORT)
        self.assertEqual(rr.apply_cli_overrides([], types.SimpleNamespace()),
                         [])
        with mock.patch.object(rr, "_transports", None):
            self.assertEqual(rr._enabled_transports({}), ["email"])
            with self.assertRaises(ValueError):
                rr._enabled_transports({"transports": ["file"]})
        with mock.patch.object(rr, "_security", None):
            self.assertIsNone(rr.check_audience({}, {}))
            with mock.patch.object(rr, "check_audience",
                                   return_value="runner_id mismatch"):
                self.assertTrue(rr.audience_allows({}, "/b", {}, "", "j"))
        with mock.patch.object(rr, "_extensions", None):
            self.assertEqual(rr._extension_registry({}, "/b"), {})
            rr._report_extensions({}, "/b")

    def test_the_real_job_user_face_calls_the_syscalls(self):
        if os.name == "nt":
            self.skipTest("job_user face is POSIX syscalls")
        face = rr._JobUserFace()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "f")
        open(path, "w").close()
        self.assertIsInstance(face.euid(), int)
        self.assertEqual(face.getpwnam("root").pw_name, "root")
        self.assertTrue(list(face.walk(tmp.name)))
        self.assertTrue(face.realpath(tmp.name))
        self.assertTrue(face.dirname(path))
        self.assertTrue(face.stat(path).st_mode)
        face.chmod(path, 0o600)
        with mock.patch.object(rr.os, "chown") as chown, \
                mock.patch.object(rr.os, "setgid") as setgid, \
                mock.patch.object(rr.os, "setuid") as setuid, \
                mock.patch.object(rr.os, "initgroups") as groups:
            face.chown(path, 0, 0)
            face.setgid(0)
            face.setuid(0)
            face.initgroups("root", 0)
        chown.assert_called_once()
        setgid.assert_called_once()
        setuid.assert_called_once()
        groups.assert_called_once()

    def test_a_signed_list_and_a_bad_secret_are_refused(self):
        with self.assertRaises(ValueError):
            rr.verify_body("{}", 3)
        secret = "s" * 32
        # sign_payload lives in runner/wire/verify.py now; patch the helper
        # where it is looked up.
        with mock.patch.object(rr._verify, "_json_safe", return_value=[1]):
            with self.assertRaises(ValueError):
                rr.sign_payload({"a": 1}, secret)
        with self.assertRaises(ValueError):
            rr.verify_body("{}", "t" * 32)

    def test_key_policy_keys_and_bool_fields(self):
        with self.assertRaises(RuntimeError):
            rr.build_key_policies({"key_policies": {1: {}}})
        with self.assertRaises(RuntimeError):
            rr.build_key_policies({"key_policies": {"k": {
                "allow_file_urls": "yes"}}})
        with self.assertRaises(RuntimeError):
            rr.build_key_policies({"key_policies": {"k": {
                "max_args": True}}})


class IoEdgeTest(_Binary, unittest.TestCase):
    def test_append_brief_trims_and_swallows_a_bad_record(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.assertIsNone(rr._append_brief("", {"a": 1}))
        with mock.patch.object(rr, "_json_safe",
                               side_effect=ValueError("bad")):
            self.assertIsNone(rr._append_brief(tmp.name, {"a": 1}))
        with mock.patch.object(rr, "_LOCAL_BRIEFS_CAP", 2), \
                mock.patch.object(rr, "_LOCAL_BRIEFS_KEEP", 1):
            for i in range(3):
                rr._append_brief(tmp.name, {"n": i})
        path = os.path.join(tmp.name, rr.LOCAL_BRIEFS_FILE)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '{"n": 2}\n')
        with mock.patch.object(rr.os, "chmod", side_effect=OSError("m")):
            rr._append_brief(tmp.name, {"n": 9})
        os.symlink(path + ".nope", path + ".link")
        # A symlink at the briefs path is not rewritten.
        with mock.patch.object(rr.os.path, "islink", return_value=True):
            rr._append_brief(tmp.name, {"n": 8})

    def test_seen_and_retained_close_failures_are_swallowed(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seen = os.path.join(tmp.name, "seen.json")
        real_open = os.open
        real_close = os.close
        opened = []

        def tracking_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened.append(fd)
            return fd

        def release():
            for fd in opened:
                try:
                    real_close(fd)
                except OSError:
                    pass
            opened.clear()

        with mock.patch.object(rr.os, "open", tracking_open), \
                mock.patch.object(rr.os, "fdopen", side_effect=OSError("fd")), \
                mock.patch.object(rr.os, "close", side_effect=OSError("c")):
            rr.save_seen(seen, {"a": True})
        # close() was simulated as broken. Windows cannot delete the
        # still-open temp file (WinError 32) when the directory goes.
        release()
        with mock.patch.object(rr.os, "unlink", side_effect=OSError("u")):
            rr.save_seen(seen, {"a": True})
        rr.save_retained(tmp.name, "job-1", {"a": 1})
        with mock.patch.object(rr.os, "open", tracking_open), \
                mock.patch.object(rr.os, "fdopen", side_effect=OSError("fd")), \
                mock.patch.object(rr.os, "close", side_effect=OSError("c")), \
                mock.patch.object(rr.os, "unlink", side_effect=OSError("u")):
            rr.save_retained(tmp.name, "job-2", {"a": 1})
        release()
        self.assertIsNone(rr.load_retained(tmp.name, "missing-job"))

    def test_a_canary_close_and_chmod_failure_still_returns(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "c.txt")
        real_close = os.close

        def close(fd):
            real_close(fd)
            raise OSError("late")

        with mock.patch.object(rr.os, "close", side_effect=close), \
                mock.patch.object(rr.os, "chmod", side_effect=OSError("m")):
            state = rr._plant_canary(path)
        self.assertTrue(state)

    def test_windows_creation_flags_are_passed_when_present(self):
        proc = mock.Mock(returncode=0, stdout="")
        with mock.patch.object(rr.sys, "platform", "win32"), \
                mock.patch.object(rr.subprocess, "CREATE_NO_WINDOW",
                                  1, create=True), \
                mock.patch.object(rr.subprocess, "run",
                                  return_value=proc) as run:
            self.assertEqual(rr._wevtutil_query("System", "*", 1), "")
            values, subkeys = rr._reg_query(r"HKLM\Run")
            self.assertEqual(values, {})
            self.assertEqual(subkeys, [])
            self.assertEqual(rr._run_text(["netsh"]), "")
        for call in run.call_args_list:
            self.assertEqual(call.kwargs.get("creationflags"), 1)

    def test_registry_and_posture_writes_that_fail_are_kept(self):
        if sys.platform == "win32":
            self.skipTest("Windows Defender is present")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        snap = {"keys": {}, "services": {"count": 0, "hash": "abc"}}
        for key in rr._REG_WATCH_KEYS:
            snap["keys"][key] = {}
            snap["keys"][key + "\x00raw"] = {}
        with mock.patch.object(rr.sys, "platform", "win32"), \
                mock.patch.object(rr, "_registry_snapshot",
                                  return_value=snap), \
                mock.patch.object(rr, "_write_json",
                                  side_effect=OSError("ro")), \
                mock.patch.object(rr, "_file_registry_lines"):
            text = rr._registry_watch(tmp.name, max_chars=8)
        self.assertTrue(text)
        self.assertLessEqual(len(text), 8)
        with mock.patch.object(rr, "_firewall_posture",
                               return_value="firewall: on"), \
                mock.patch.object(rr, "_write_json",
                                  side_effect=OSError("ro")):
            self.assertIn("baseline", rr._firewall_watch(tmp.name))
        with mock.patch.object(rr, "_av_posture", return_value="av: on"), \
                mock.patch.object(rr, "_write_json",
                                  side_effect=OSError("ro")):
            self.assertIn("baseline", rr._av_watch(tmp.name))
        with mock.patch.object(rr.sys, "platform", "darwin"):
            self.assertIsNone(rr._av_posture())
        with mock.patch.object(rr, "_clam_sig_line",
                               side_effect=RuntimeError("x")):
            self.assertIsNone(rr._av_posture())
        self.assertIsNone(rr._parse_defender_query(
            "STATE              : 4  START_PENDING"))

    def test_a_blank_reg_line_is_skipped(self):
        proc = mock.Mock(returncode=0, stdout="\n\nHKLM\\Run\n")
        with mock.patch.object(rr.subprocess, "run", return_value=proc):
            values, subkeys = rr._reg_query(r"HKLM\Run")
        self.assertEqual(values, {})
        self.assertEqual(subkeys, [])

    def test_flagged_and_withheld_rows_skip_junk(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        retained = os.path.join(tmp.name, "retained")
        os.makedirs(retained)
        with open(os.path.join(retained, "job-1.json"), "w") as fh:
            fh.write("{")
        with open(os.path.join(retained, "job-2.json"), "w") as fh:
            fh.write("[]")
        with open(os.path.join(retained, "job-3.json"), "w") as fh:
            json.dump({"script": "   "}, fh)
        self.assertEqual(rr._flagged_job_ids(tmp.name), set())
        self.assertEqual(rr._withheld_scan_text(tmp.name), "")

    def test_recent_chat_falls_back_when_the_cap_is_junk(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "oracle-chat.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "event": "ask", "question": "q", "answer": "a"}) + "\n")
        self.assertIn("q", rr.recent_chat(tmp.name, max_chars="nope"))
        # No ask rows at all.
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        self.assertEqual(rr.recent_chat(tmp.name), "")


class LocalSignalTest(unittest.TestCase):
    def test_the_inbox_refuses_a_symlink_and_bad_bytes(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.assertEqual(rr._local_inbox_dir(""), "")
        self.assertEqual(rr._scan_local_inbox({}, ""), 0)
        inbox = rr._local_inbox_dir(tmp.name)
        os.makedirs(inbox)
        open(os.path.join(inbox, "note.txt"), "w").close()
        link = os.path.join(inbox, "a.json")
        os.symlink("/etc/hostname", link)
        bad = os.path.join(inbox, "b.json")
        with open(bad, "wb") as fh:
            fh.write(b"\xff")
        boom = os.path.join(inbox, "c.json")
        open(boom, "w").close()
        real_open = open

        def opener(path, *a, **k):
            if path.endswith("c.json"):
                raise OSError("busy")
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", side_effect=opener), \
                mock.patch.object(rr.os, "unlink", side_effect=OSError("u")):
            n = rr._scan_local_inbox({}, tmp.name)
        self.assertGreaterEqual(n, 1)

    def test_a_socket_envelope_is_bounded(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = mock.Mock()
        conn.settimeout.side_effect = OSError("t")
        rr._handle_local_signal_conn({}, tmp.name, conn)

        conn = mock.Mock()
        conn.recv.side_effect = socket.timeout()
        rr._handle_local_signal_conn({}, tmp.name, conn)

        conn = mock.Mock()
        conn.recv.side_effect = OSError("rst")
        rr._handle_local_signal_conn({}, tmp.name, conn)

        conn = mock.Mock()
        conn.recv.side_effect = [b"x" * 100, b""]
        with mock.patch.object(rr, "_LOCAL_ENVELOPE_MAX_BYTES", 10):
            rr._handle_local_signal_conn({}, tmp.name, conn)

        conn = mock.Mock()
        conn.recv.return_value = b""
        rr._handle_local_signal_conn({}, tmp.name, conn)

        conn = mock.Mock()
        conn.recv.side_effect = [b"\xff", b""]
        rr._handle_local_signal_conn({"local_signals": True}, tmp.name, conn)

        conn = mock.Mock()
        conn.recv.side_effect = [b"{}", b""]
        rr._handle_local_signal_conn(
            {"local_signals": False}, tmp.name, conn)

    def test_the_listener_and_the_loops_stop_cleanly(self):
        if sys.platform == "win32":
            self.skipTest("socket bind behavior differs on Windows")
        self.assertIsNone(rr._local_signal_server(
            {"local_signal_port": 0}, "/tmp"))
        with mock.patch.object(rr.socket, "socket",
                               side_effect=OSError("no")):
            self.assertIsNone(rr._local_signal_server({}, "/tmp"))
        srv = rr._local_signal_server(
            {"local_signal_port": 0}, "/tmp")
        # port 0 is off. Bind a real ephemeral socket via the helper
        # by asking for an ephemeral port through a patched bind.
        real_socket = socket.socket

        def make(*a, **k):
            s = real_socket(*a, **k)
            return s

        with mock.patch.object(rr, "_local_signal_port", return_value=0):
            self.assertIsNone(rr._local_signal_server({}, "/tmp"))

        holder = {}

        def fake_socket(*a, **k):
            s = real_socket(*a, **k)
            holder["s"] = s
            return s

        # Occupy an ephemeral port, then ask the server for the
        # same one: the bind fails with EADDRINUSE on every
        # platform and at every privilege level. (The previous
        # shape bound port 1 and relied on it being privileged --
        # true for CI's unprivileged runners, false when the suite
        # runs as root, where the bind succeeds and the server
        # comes up.)
        squatter = real_socket()
        squatter.bind(("127.0.0.1", 0))
        taken_port = squatter.getsockname()[1]
        try:
            with mock.patch.object(rr.socket, "socket",
                                   side_effect=fake_socket):
                bound = rr._local_signal_server(
                    {"local_signal_port": taken_port}, "/tmp")
            self.assertIsNone(bound)
        finally:
            squatter.close()

        srv = mock.Mock()
        calls = {"n": 0}

        def accept():
            calls["n"] += 1
            if calls["n"] == 1:
                raise socket.timeout()
            raise OSError("closed")

        srv.accept.side_effect = accept
        with mock.patch.object(rr._LOCAL_TICK, "wait",
                               side_effect=RuntimeError("stop")):
            with self.assertRaises(RuntimeError):
                rr._serve_local_signals({}, "/tmp", srv)

        with mock.patch.object(rr, "_scan_local_inbox",
                               side_effect=RuntimeError("scan")), \
                mock.patch.object(rr._LOCAL_TICK, "wait",
                                  side_effect=RuntimeError("stop")):
            with self.assertRaises(RuntimeError):
                rr._local_inbox_watcher({}, "/tmp")

        rr._start_local_signals({"local_signals": False}, "/tmp")
        with mock.patch.object(rr.os, "makedirs", side_effect=OSError("ro")), \
                mock.patch.object(rr, "_local_signal_server",
                                  return_value=None), \
                mock.patch.object(rr.threading, "Thread") as thread:
            thread.return_value.start.return_value = None
            rr._start_local_signals({}, tempfile.mkdtemp())
        thread.return_value.start.side_effect = RuntimeError("thr")
        with mock.patch.object(rr.threading, "Thread", thread):
            rr._start_local_signals({}, tempfile.mkdtemp())


class _BindFailingSocket:
    """A listener-shaped fake whose bind always fails: the
    refusal path of _local_signal_server, driven the same
    on every platform (a real occupied port does not fail
    the second bind the same way on Windows)."""

    def __init__(self, close_raises=False):
        self.close_raises = close_raises
        self.closed = False

    def setsockopt(self, *a):
        pass

    def bind(self, addr):
        raise OSError("address already in use")

    def listen(self, n):
        pass

    def settimeout(self, t):
        pass

    def close(self):
        self.closed = True
        if self.close_raises:
            raise OSError("close says no")


class LocalSignalServerRefusalTest(unittest.TestCase):
    """Queue A refill: _local_signal_server's refusal
    block (coverage run 40187685363: the whole block
    unrun on Windows -- the one existing drive skips
    there -- and the close swallow unrun on both). The
    contract is the docstring's: a bound, listening
    socket, or None; never raises. A bind failure is
    logged, the half-made socket is closed, and even a
    close that fails changes nothing.
    """

    def _server_with(self, fake):
        with mock.patch.object(rr.socket, "socket",
                               lambda *a, **k: fake):
            return rr._local_signal_server(
                {"local_signal_port": 43117}, "/tmp")

    def test_a_bind_failure_closes_the_socket_and_refuses(self):
        fake = _BindFailingSocket()
        self.assertIsNone(self._server_with(fake))
        self.assertTrue(fake.closed)

    def test_a_failing_close_is_swallowed(self):
        fake = _BindFailingSocket(close_raises=True)
        self.assertIsNone(self._server_with(fake))
        self.assertTrue(fake.closed)


class RunnerFailSoftLegsTest(unittest.TestCase):
    """Queue A refill: runner.py's fail-soft legs
    (coverage run 40189711740): the withheld-path
    helpers when the sources module raises
    (_withheld_for_tools 1654-1655, _tool_withheld
    1660 and 1665-1666), _staged_dest when realpath
    itself fails (3099-3100), download's transient
    re-raise and bad-URL refusal (3028, 3032),
    save_retained's close-failure swallow
    (2788-2789), _append_brief's write swallow
    (5100-5101), the brief thread's opinion swallow
    (5048-5049), _file_fresh_lines' state-write
    swallow (8425-8426), _tail_marked's vanished
    file (8646-8647), _extension_registry's load
    failure (4429-4430) and _extension_sources_note's
    raise (4623-4624). Every one is a best-effort
    seam: a collaborator failing degrades the
    answer, never escapes.
    """

    def test_withheld_helpers_degrade(self):
        fake = types.SimpleNamespace(
            withheld_paths=mock.Mock(
                side_effect=RuntimeError("boom")),
            is_withheld=mock.Mock(
                side_effect=RuntimeError("boom")))
        with mock.patch.object(rr, "_extsources", fake):
            self.assertEqual(rr._withheld_for_tools("/base"), [])
            self.assertTrue(
                rr._tool_withheld("/p", "/base", ["/w"]))
        fake2 = types.SimpleNamespace(
            withheld_paths=lambda base: ["/w"],
            is_withheld=lambda path, w: True)
        with mock.patch.object(rr, "_extsources", fake2):
            self.assertTrue(rr._tool_withheld("/p", "/base", None))

    def test_staged_dest_realpath_failure_is_a_rejection(self):
        with mock.patch.object(
                os.path, "realpath",
                side_effect=ValueError("bad path")):
            with self.assertRaises(rr.JobRejected):
                rr._staged_dest("/w", "f.txt")

    def test_download_transient_and_bad_url(self):
        from urllib.error import URLError
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "f.bin")
            with mock.patch.object(
                    rr, "_open_download",
                    side_effect=URLError("Connection refused")):
                with self.assertRaises(URLError):
                    rr.download("https://x.test/f", dest)
            with mock.patch.object(
                    rr, "_open_download",
                    side_effect=ValueError("Invalid IPv6 URL")):
                with self.assertRaisesRegex(rr.JobRejected,
                                            "bad download url"):
                    rr.download("https://x.test/f", dest)

    def test_save_retained_close_failure_is_swallowed(self):
        real_close = os.close

        def stuck_close(fd):
            # close() releases the descriptor even when it reports
            # a failure; so does this fake, or the tmp stays open and
            # Windows cannot remove the directory afterwards.
            real_close(fd)
            raise OSError("stuck")

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(
                    rr, "_json_safe",
                    side_effect=ValueError("bad payload")), \
                mock.patch.object(os, "close", stuck_close):
            self.assertIsNone(
                rr.save_retained(d, "job1", {"a": 1}))
            self.assertFalse(os.path.exists(
                os.path.join(d, "retained", "job1.json")))

    def test_append_brief_write_failure_is_swallowed(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(
                    os, "open", side_effect=OSError("ro")):
            self.assertIsNone(rr._append_brief(d, {"k": "v"}))

    def test_brief_thread_releases_the_gate_on_failure(self):
        released = []
        with mock.patch.object(
                rr, "_oracle_brief",
                side_effect=RuntimeError("no model")), \
                mock.patch.object(
                    rr, "_wake_gate_release",
                    side_effect=lambda: released.append(1)):
            th = rr._start_brief_thread({}, "/base", {})
            th.join(5)
        self.assertEqual(released, [1])

    def test_fresh_lines_state_write_failure_is_quiet(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(
                    rr, "_write_json",
                    side_effect=OSError("ro")):
            self.assertIsNone(rr._file_fresh_lines(
                d, "sensor", "boom [T1059] happened"))

    def test_tail_marked_vanished_file(self):
        real_open = open

        def refusing(path, *a, **k):
            if str(path).endswith("gone.log"):
                raise OSError("vanished")
            return real_open(path, *a, **k)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "gone.log")
            with open(path, "w") as fh:
                fh.write("x [M] y\n")
            with mock.patch("builtins.open", refusing):
                self.assertIsNone(rr._tail_marked(path, ["[M]"]))

    def test_registry_and_note_failures_degrade(self):
        fake_ext = types.SimpleNamespace(
            extensions_dir_for=lambda cfg, base: "/x",
            load_extensions=mock.Mock(
                side_effect=RuntimeError("bad manifest")))
        with mock.patch.object(rr, "_extensions", fake_ext):
            self.assertEqual(rr._extension_registry({}, "/b"), {})
        fake_src = types.SimpleNamespace(
            oracle_note=mock.Mock(
                side_effect=RuntimeError("boom")))
        with mock.patch.object(rr, "_extsources", fake_src):
            self.assertEqual(rr._extension_sources_note("/b"), "")


class RunnerFailSoftLegs2Test(unittest.TestCase):
    """Queue A refill, second batch (coverage run
    40189711740): _extension_source_targets when
    transport discovery raises (4510-4511),
    _extension_sources_tick's absent-module guard
    and deepcopy fallback (4571, 4585-4586),
    _oracle_host_ok when urlparse itself fails
    (9963-9964), _take_body's negative length
    (10025-10026), and update_llama_from_config's
    failed pull (7445-7446).
    """

    def test_source_targets_survive_discovery_failure(self):
        fake = types.SimpleNamespace(
            enabled_transports=mock.Mock(
                side_effect=RuntimeError("bad transport")),
            discover_transport_extensions=mock.Mock())
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rr, "_transports", fake):
            self.assertEqual(
                rr._extension_source_targets({}, d), [])

    def test_sources_tick_guard_and_snapshot_fallback(self):
        with mock.patch.object(rr, "_extsources", None):
            self.assertFalse(
                rr._extension_sources_tick({}, "/b", now=1.0))
        saved = dict(rr._EXTSOURCES_PASS)
        seen = []
        try:
            rr._EXTSOURCES_PASS.update(
                {"since": 0.0, "thread": None, "next_due": 0.0})
            with mock.patch.object(
                    rr, "_extension_sources_pass",
                    side_effect=lambda snap, base:
                        seen.append(snap)), \
                    mock.patch.object(
                        rr.copy, "deepcopy",
                        side_effect=RuntimeError("unpicklable")):
                started = rr._extension_sources_tick(
                    {"a": 1}, "/b", now=10 ** 9)
            th = rr._EXTSOURCES_PASS.get("thread")
            if th is not None:
                th.join(5)
        finally:
            rr._EXTSOURCES_PASS.clear()
            rr._EXTSOURCES_PASS.update(saved)
        self.assertTrue(started)
        self.assertEqual(seen, [{"a": 1}])

    def test_oracle_host_ok_when_urlparse_fails(self):
        handler = types.SimpleNamespace(
            client_address=("127.0.0.1", 5000),
            headers={"Host": "localhost:11436",
                     "Origin": "http://localhost"})
        with mock.patch.object(
                rr, "urlparse",
                side_effect=ValueError("bad origin")):
            self.assertFalse(rr._oracle_host_ok(handler))

    def test_take_body_negative_length(self):
        httpd = rr.make_oracle_server({}, "127.0.0.1", 0)
        try:
            handler = object.__new__(httpd.RequestHandlerClass)
            handler.headers = {"Content-Length": "-5"}
            handler.rfile = io.BytesIO(b"")
            self.assertIsNone(handler._take_body())
            self.assertTrue(handler.close_connection)
        finally:
            httpd.server_close()

    def test_llama_pull_failure_is_logged_not_raised(self):
        import shutil
        import subprocess

        def inf(cfg):
            return {"model": cfg.get("m")} if cfg else None

        with mock.patch.object(rr, "inference_config",
                               side_effect=inf), \
                mock.patch.object(rr, "ensure_inference_ready",
                                  lambda cfg: None), \
                mock.patch.object(shutil, "which",
                                  lambda name: "/usr/bin/ollama"), \
                mock.patch.object(
                    subprocess, "run",
                    side_effect=OSError("no ollama")):
            self.assertIsNone(rr.update_llama_from_config(
                {"m": "new"}, previous={"m": "old"}))


class RunnerFailSoftLegs3Test(unittest.TestCase):
    """Queue A refill, third batch (coverage run
    40189711740): _admit_object's non-string id,
    malformed envelope and envelope/body key
    mismatch (3866, 3873, 3878),
    _learning_reconcile's two disabled gates
    (5537, 5539), _learning_model_candidate's
    unparseable reply and failed candidate write
    (5613-5614, 5623-5624), _wake_gate_decide's
    non-record and unconvertible clock (4984,
    4997-4998), and _write_seen_unlocked's
    cleanup swallow (6737-6738).
    """

    @staticmethod
    def _payload(job_id, **kw):
        from datetime import datetime, timezone
        p = {"v": 1, "type": "job", "job_id": job_id,
             "issued_at": datetime.now(timezone.utc).strftime(
                 "%Y-%m-%dT%H:%M:%SZ"),
             "kind": "ping"}
        p.update(kw)
        return p

    def test_admit_object_legs(self):
        body = sign_payload(self._payload("j1"), KEY_A)
        payload, key_id, secret, encrypted = rr._admit_object(
            body, {"": KEY_A}, 12345)
        self.assertEqual(payload["job_id"], "j1")
        self.assertFalse(encrypted)
        bogus = sign_payload(
            self._payload("j1", hp_enc={"bogus": 1}), KEY_A)
        with self.assertRaisesRegex(ValueError,
                                    "malformed encryption"):
            rr._admit_object(bogus, {"": KEY_A}, "j1")
        inner = sign_payload(
            self._payload("j2", key_id="B"), KEY_B)
        envelope = jobcrypto.encrypt_body(
            inner, KEY_A, job_id="j2", key_id="A",
            sign=sign_payload)
        with self.assertRaisesRegex(ValueError,
                                    "does not match"):
            rr._admit_object(
                envelope, {"A": KEY_A, "B": KEY_B}, "j2")

    def test_learning_reconcile_gates(self):
        off = types.SimpleNamespace(
            learning_enabled=lambda cfg: False)
        with mock.patch.object(rr, "_learning", off):
            self.assertIsNone(rr._learning_reconcile(
                {}, "/b", {"features": []}, "j", {}, {}, None))
        on = types.SimpleNamespace(
            learning_enabled=lambda cfg: True)
        with mock.patch.object(rr, "_learning", on):
            self.assertIsNone(rr._learning_reconcile(
                {}, "/b", None, "j", {}, {}, None))

    def test_learning_model_candidate_legs(self):
        learning = types.SimpleNamespace(
            learning_model_enabled=lambda cfg: True,
            validate_candidate=lambda obj: {"claim": "c"},
            candidate_record=lambda cand, jid, fp: {"r": 1},
            append_candidate=lambda base, rec: False,
            host_fingerprint=lambda *a: "fp")
        opinion = types.SimpleNamespace(
            model_enabled=lambda cfg: True)
        job = {"job_id": "j"}
        outcome = {"exit_code": 0, "timed_out": False,
                   "rejected": False}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rr, "_learning", learning), \
                mock.patch.object(rr, "_opinion", opinion), \
                mock.patch.object(rr, "inference_config",
                                  lambda cfg: {"model": "m"}), \
                mock.patch.object(
                    rr, "ask_model",
                    return_value={"answer": "{not json}"}):
            self.assertIsNone(rr._learning_model_candidate(
                {}, d, "j", job, outcome, "", ""))
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rr, "_learning", learning), \
                mock.patch.object(rr, "_opinion", opinion), \
                mock.patch.object(rr, "inference_config",
                                  lambda cfg: {"model": "m"}), \
                mock.patch.object(
                    rr, "ask_model",
                    return_value={"answer": '{"claim": "c"}'}):
            self.assertIsNone(rr._learning_model_candidate(
                {}, d, "j", job, outcome, "", ""))

    def test_wake_gate_decide_legs(self):
        self.assertFalse(rr._wake_gate_decide({}, "not-a-record"))
        try:
            decided = rr._wake_gate_decide(
                {}, {"severity": "high", "sensor": "s",
                     "signal": "sig"}, now=object())
            self.assertTrue(decided)
        finally:
            rr._wake_gate_release()

    def test_write_seen_cleanup_swallow(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with mock.patch.object(
                    os, "replace",
                    side_effect=OSError("busy")), \
                    mock.patch.object(
                        os, "unlink",
                        side_effect=OSError("stuck")):
                self.assertIsNone(
                    rr._write_seen_unlocked(path, {"a": True}))


class RunnerFailSoftLegs4Test(unittest.TestCase):
    """Queue A refill, fourth batch (coverage run
    40189711740): _ingest_local_envelope's
    catch-all (4886-4888), _local_watch's base
    guard and per-watch swallow (8442, 8454-8455),
    _transports_arg's two empty refusals (7078-7079,
    7083), and _append_security_event's rollover
    open under the Windows flag line (197, 220).
    """

    def test_ingest_wrapper_swallows_inner_failure(self):
        with mock.patch.object(
                rr, "_ingest_local_envelope_inner",
                side_effect=RuntimeError("bad envelope")):
            self.assertIsNone(rr._ingest_local_envelope(
                {}, "/b", "text", "file"))

    def test_local_watch_legs(self):
        self.assertIsNone(rr._local_watch({}, 123))
        ran = []
        # The log tail is the platform's: the event log on Windows,
        # the host log elsewhere; the registry diff exists only there.
        tail = "_eventlog_tail" if sys.platform == "win32" else "_host_log_tail"
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(
                    rr, "_canary_watch",
                    side_effect=RuntimeError("canary down")), \
                mock.patch.object(
                    rr, tail,
                    side_effect=lambda **kw: ran.append(1)), \
                mock.patch.object(rr, "_registry_watch",
                                  lambda base: None, create=True), \
                mock.patch.object(rr, "_firewall_watch",
                                  lambda base: None), \
                mock.patch.object(rr, "_av_watch",
                                  lambda base: None):
            self.assertIsNone(rr._local_watch({}, d))
        self.assertEqual(ran, [1])

    def test_transports_arg_empty_refusals(self):
        import argparse
        with mock.patch.object(rr, "_transports", None):
            with self.assertRaises(
                    argparse.ArgumentTypeError):
                rr._transports_arg("")
        fake = types.SimpleNamespace(
            enabled_transports=lambda probe: [])
        with mock.patch.object(rr, "_transports", fake):
            with self.assertRaises(
                    argparse.ArgumentTypeError):
                rr._transports_arg("")
            self.assertEqual(rr._transports_arg("file"),
                             ["file"])

    def test_security_event_rollover(self):
        had = hasattr(os, "O_BINARY")
        os.O_BINARY = 0
        try:
            with tempfile.TemporaryDirectory() as d, \
                    mock.patch.object(
                        rr, "_SECURITY_EVENTS_MAX", 2):
                for i in range(3):
                    rr._append_security_event(
                        d, {"kind": "k%d" % i})
                path = os.path.join(d, "security-events.jsonl")
                with open(path) as fh:
                    lines = fh.read().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn('"k2"', lines[-1])
        finally:
            if not had and hasattr(os, "O_BINARY"):
                del os.O_BINARY


class RunnerFailSoftLegs5Test(unittest.TestCase):
    """Queue A refill, fifth batch (coverage run
    40189711740): _v2_leave_unseen's non-string id
    and set cap (5747, 5751), _v2_before_execute's
    absent-module return and determination segment
    (5880, 5889-5890), and run_inspect's sources
    branch without the sources module (7553-7555).
    """

    def test_leave_unseen_legs(self):
        saved = set(rr._V2_LEFT_UNSEEN)
        try:
            rr._V2_LEFT_UNSEEN.clear()
            rr._v2_leave_unseen(12345)
            self.assertIn("12345", rr._V2_LEFT_UNSEEN)
            for i in range(300):
                rr._V2_LEFT_UNSEEN.add("x%d" % i)
            rr._v2_leave_unseen("fresh")
            self.assertEqual(rr._V2_LEFT_UNSEEN, {"fresh"})
        finally:
            rr._V2_LEFT_UNSEEN.clear()
            rr._V2_LEFT_UNSEEN.update(saved)

    def test_v2_before_execute_legs(self):
        with mock.patch.object(rr, "_protocol_v2", None):
            self.assertEqual(rr._v2_before_execute(
                {}, {}, {}, "s", "", False, "/b",
                lambda subj, body: []), [])
        fake = types.SimpleNamespace(
            outbound_for=lambda cfg, job, plan: [
                ("subj", {"type": "determination",
                          "why": "because", "msg_id": "m1"})],
            segment=lambda *a: ("segment", a))
        with mock.patch.object(rr, "_protocol_v2", fake), \
                mock.patch.object(rr, "_seal_reply",
                                  lambda *a: "sealed"):
            out = rr._v2_before_execute(
                {}, {}, {}, "s", "", False, "/b",
                lambda subj, body: [])
        self.assertEqual(out, [("segment",
                                 ("runner", "determination",
                                  "because"))])

    def test_run_inspect_sources_unavailable(self):
        args = types.SimpleNamespace(inspect="sources",
                                     config=None)
        with mock.patch.object(rr, "_extsources", None), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rr.run_inspect({}, args), 1)


class RunnerFailSoftLegs6Test(unittest.TestCase):
    """Queue A refill, sixth batch (coverage run
    40189711740): oracle_window's non-dict config
    and deterministic banner (10200, 10223),
    oracle_cli's Ctrl-C exit (10360-10361),
    do_POST's deterministic answer (10109), and
    poll_once's supervisor-check failure (7404-7405).
    """

    def test_oracle_window_legs(self):
        class FakeHttpd:
            socket = types.SimpleNamespace(
                getsockname=lambda: ("127.0.0.1", 11436))

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                pass

        out = io.StringIO()
        with mock.patch.object(rr, "make_oracle_server",
                               lambda *a, **k: FakeHttpd()), \
                mock.patch.object(rr, "record_oracle_turn",
                                  lambda *a, **k: None), \
                mock.patch.object(rr, "_refresh_log_settings",
                                  lambda *a: None), \
                mock.patch.object(rr, "_announce_oracle_log",
                                  lambda: None), \
                mock.patch.object(rr, "_oracle_mode",
                                  lambda cfg: "deterministic"), \
                contextlib.redirect_stdout(out):
            rc = rr.oracle_window("not-a-dict", port=0,
                                  open_browser=False)
        self.assertEqual(rc, 0)
        self.assertIn("deterministic (Pi Light)",
                      out.getvalue())

    def test_oracle_cli_ctrl_c(self):
        calls = []

        def interrupt_on_second(*a, **k):
            calls.append(1)
            if len(calls) == 2:
                raise KeyboardInterrupt

        printed = []
        with mock.patch.object(rr, "record_oracle_turn",
                               interrupt_on_second):
            rc = rr.oracle_cli(
                {"oracle_mode": "deterministic"},
                input_fn=lambda prompt="": "status?",
                print_fn=printed.append)
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(len(calls), 2)

    def test_do_post_deterministic_answer(self):
        import http.client
        cfg = {"oracle_mode": "deterministic"}
        httpd = rr.make_oracle_server(cfg, "127.0.0.1", 0,
                                      base_dir=None)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever,
                              daemon=True)
        th.start()
        try:
            conn = http.client.HTTPConnection(
                "127.0.0.1", port, timeout=10)
            conn.request(
                "POST", "/ask",
                body=json.dumps({"question": "status?"}),
                headers={"Content-Type": "application/json",
                         "X-Oracle-Token": httpd.oracle_token})
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", "replace")
            self.assertEqual(resp.status, 200)
            self.assertIn("answer", body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_poll_once_supervisor_failure(self):
        sup = types.SimpleNamespace(
            check=mock.Mock(
                side_effect=RuntimeError("sup down")),
            settle=lambda: None)
        fake = types.SimpleNamespace(
            active_supervisor=lambda cfg, base: sup,
            enabled_transports=lambda cfg: [])
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rr, "_transports", fake):
            self.assertIsNone(rr.poll_once(
                {"shared_secret": KEY_A}, d, {},
                os.path.join(d, "seen.json")))


class RunnerResidualLegsTest(unittest.TestCase):
    """Queue A refill: runner.py's residual
    guarded legs (coverage run 40189711740).
    Each test names the leg it closes in its
    docstring line; the contracts are the
    documented ones -- a guard that cannot
    prove its fact refuses, degrades, or stays
    silent, and never raises into the caller.
    """

    def test_load_mod_missing_local_returns_none(self):
        # _load_mod's local-import failure return:
        # neither spelling of a missing module
        # exists, broad or not.
        self.assertIsNone(
            rr._load_mod("runner.nope_xyz", "nope_xyz_local"))
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "brokenmod.py"),
                      "w", encoding="utf-8") as fh:
                fh.write("raise RuntimeError('broken')\n")
            sys.path.insert(0, d)
            try:
                self.assertIsNone(rr._load_mod(
                    "runner.nope_xyz", "brokenmod", broad=True))
            finally:
                sys.path.remove(d)
                sys.modules.pop("brokenmod", None)

    def test_load_mod_broken_package(self):
        # _load_mod's package-side guard: a
        # package import that raises something
        # other than ImportError is swallowed
        # only under broad; otherwise it raises.
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "brokenpkg.py"),
                      "w", encoding="utf-8") as fh:
                fh.write("raise RuntimeError('broken')\n")
            sys.path.insert(0, d)
            try:
                self.assertIsNone(rr._load_mod(
                    "brokenpkg", "nope_xyz_local",
                    broad=True))
                with self.assertRaises(RuntimeError):
                    rr._load_mod("brokenpkg",
                                 "nope_xyz_local")
            finally:
                sys.path.remove(d)
                sys.modules.pop("brokenpkg", None)

    def test_job_user_face_setgroups_delegates(self):
        # _JobUserFace.setgroups: the real face
        # passes the call to the OS unchanged.
        face = rr._JobUserFace()
        with mock.patch.object(os, "setgroups") as sg:
            face.setgroups([1000, 1001])
        sg.assert_called_once_with([1000, 1001])

    def test_write_json_with_the_binary_flag_present(self):
        # _write_json's O_BINARY flag line, run
        # under the _Binary trick (flag value 0).
        had = hasattr(os, "O_BINARY")
        os.O_BINARY = 0
        try:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "out.json")
                rr._write_json(path, {"a": 1})
                with open(path, encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh), {"a": 1})
        finally:
            if not had:
                del os.O_BINARY

    def test_get_text_body_with_no_payload(self):
        # get_text_body's last return: a message
        # carrying no payload at all reads as "".
        import email.message
        msg = email.message.Message()
        self.assertEqual(rr.get_text_body(msg), "")

    def test_remediation_audit_silent_without_modules(self):
        # _remediation_audit's absent-module
        # return: no security module, no entry,
        # no error.
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(rr, "_security", None):
                self.assertIsNone(rr._remediation_audit(
                    d, {}, {}, "j1", "dec", "div"))

    def test_sensor_alert_core_without_senses(self):
        # _sensor_alert_core's unavailable
        # return: no senses module, a rejection
        # that names why.
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(rr, "_senses", None):
                out = rr._sensor_alert_core({}, {}, None, d)
        self.assertEqual(
            out, ("rejected",
                  "rejected: senses module unavailable",
                  None))

    def test_sensor_alert_core_config_error(self):
        # _sensor_alert_core's RuntimeError leg:
        # an unparseable sensor config answers
        # ("config", the reason, None).
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    rr._senses, "parse_sensors",
                    side_effect=RuntimeError("bad sensors")):
                out = rr._sensor_alert_core({}, {}, None, d)
        self.assertEqual(out, ("config", "bad sensors", None))

    def test_remediation_ask_fn_blank_answers(self):
        # _remediation_ask_fn's ask: a non-dict
        # reply, a non-string answer, and a
        # blank answer are all None; a real
        # answer passes through unstripped.
        cfg = {"inference": {
            "endpoint": "http://127.0.0.1:11434",
            "model": "m"}}
        st = rr._remediation.settings(cfg)
        ask = rr._remediation_ask_fn(cfg, st)
        self.assertIsNotNone(ask)
        for reply in ("nope", {"answer": 42},
                      {"answer": "   "}):
            with mock.patch.object(
                    rr, "ask_model", return_value=reply):
                self.assertIsNone(ask("q", {}))
        with mock.patch.object(
                rr, "ask_model",
                return_value={"answer": " yes "}):
            self.assertEqual(ask("q", {}), " yes ")

    def test_opinion_model_note_truncates(self):
        # _opinion_model_note's success tail:
        # the note is the model's stripped
        # answer, cut to 240 characters.
        cfg = {"oracle_opinion_model": True,
               "inference": {
                   "endpoint": "http://127.0.0.1:11434",
                   "model": "m"}}
        with mock.patch.object(
                rr, "ask_model",
                return_value={"answer": "  " + "x" * 300}):
            note = rr._opinion_model_note(
                cfg, {"kind": "exec", "script": "true"})
        self.assertEqual(note, "x" * 240)
        job = {"kind": "exec", "script": "true"}
        with mock.patch.object(
                rr, "ask_model",
                side_effect=RuntimeError("down")):
            self.assertIsNone(
                rr._opinion_model_note(cfg, job))
        for reply in ("nope", {"answer": "   "},
                      {"answer": 42}):
            with mock.patch.object(
                    rr, "ask_model", return_value=reply):
                self.assertIsNone(
                    rr._opinion_model_note(cfg, job))

    def test_describe_job_names_the_timeout(self):
        # _describe_job's timeout member.
        text = rr._describe_job(
            {"kind": "exec", "script": "x",
             "timeout_sec": 30})
        self.assertIn("timeout_sec=30", text)

    def test_query_mail_unexpected_error_is_handled(self):
        # handle_query_mail's generic-except
        # leg: an admission failure that is not
        # a crypto error is still handled --
        # logged, marked, True -- never raised
        # into the poll.
        raw = (b"From: a@b.c\r\nSubject: hi\r\n\r\n"
               b"body\r\n")
        opts = types.SimpleNamespace(dry_run=True)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    rr, "_admit_object",
                    side_effect=RuntimeError("boom")):
                handled = rr.handle_query_mail(
                    {}, mock.Mock(), mock.Mock(), "1", raw,
                    "[HOMING-PIGEON] query q-z", {}, opts, d)
        self.assertTrue(handled)

    def test_kill_tree_takes_the_extra_pids(self):
        # kill_tree's extra-pids leg: a detached
        # process the monitor sampled still
        # dies, though it escaped the group.
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            proc = mock.Mock()
            proc.pid = 99999999
            rr.kill_tree(proc, extra_pids=[sleeper.pid])
            self.assertEqual(
                sleeper.wait(timeout=5), -signal.SIGKILL)
        finally:
            if sleeper.poll() is None:
                sleeper.kill()

    def test_kill_tree_swallows_a_failed_kill(self):
        # kill_tree's inner swallows: the
        # fallback kill raising, and an extra
        # pid that cannot be killed, are both
        # best effort -- neither escapes.
        proc = mock.Mock()
        proc.pid = 99999999
        proc.kill.side_effect = RuntimeError("gone")
        rr.kill_tree(proc, extra_pids=[2 ** 22 + 12345,
                                       "not-a-pid"])
        proc.kill.assert_called_once()

    def test_disk_claim_guards(self):
        # _disk_owns' bad-base return is True
        # (no disk, no claim -- the in-memory
        # cache decides), _disk_release's is a
        # silent None, and a claim folder that
        # cannot be created loses the claim.
        self.assertTrue(rr._disk_owns(None, "k", {}))
        self.assertTrue(rr._disk_owns("", "k", {}))
        self.assertIsNone(rr._disk_release(None, "k"))
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "inflight"),
                      "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            self.assertFalse(rr._disk_owns(d, "k", {}))

    def test_save_seen_merges_with_the_disk_keys(self):
        # save_seen's merge, over the on-disk
        # form (a list of keys): keys another
        # runner saved survive, the new keys
        # land, and the caller's dict learns
        # the disk's keys. (merge's own
        # not-a-dict reset cannot fire --
        # _with_seen_file coerces before the
        # mutator runs; probed 2026-10-25.)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('["1", "2"]')
            seen = {"job1": True}
            rr.save_seen(path, seen)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh),
                                 ["1", "2", "job1"])
            self.assertEqual(
                seen, {"job1": True, "1": True, "2": True})

    def test_load_retained_unprovable_containment(self):
        # load_retained's ValueError leg: where
        # containment cannot be proven (the
        # Windows cross-drive case raises it),
        # the retained record is refused.
        with tempfile.TemporaryDirectory() as d:
            kept = os.path.join(d, "retained")
            os.makedirs(kept)
            with open(os.path.join(kept, "jobx.json"),
                      "w", encoding="utf-8") as fh:
                fh.write("{}")
            with mock.patch.object(
                    os.path, "commonpath",
                    side_effect=ValueError("drives")):
                self.assertIsNone(
                    rr.load_retained(d, "jobx"))

    def test_inference_ready_when_already_listening(self):
        # ensure_inference_ready's dial-success
        # return: a daemon already listening is
        # left alone.
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        try:
            cfg = {"inference": {
                "endpoint": f"http://127.0.0.1:{port}",
                "model": "m"}}
            self.assertIsNone(
                rr.ensure_inference_ready(cfg))
        finally:
            sock.close()

    def test_monitor_alerts_fn_guards(self):
        # _start_job_monitor's alerts_fn: no
        # senses module, and a senses module
        # that raises, both answer [].
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, "work")
            os.makedirs(work)
            script = os.path.join(d, "job.sh")
            with open(script, "w", encoding="utf-8") as fh:
                fh.write("echo hi\n")
            proc = subprocess.Popen(["sleep", "5"])
            st = rr._remediation.settings({})
            monitor = rr._start_job_monitor(
                {}, st, "job-m1", proc, work, d, script, {})
            try:
                fn = monitor._alerts_fn
                with mock.patch.object(rr, "_senses", None):
                    self.assertEqual(fn("2026-01-01"), [])
                broken = types.SimpleNamespace(
                    load_alerts=mock.Mock(
                        side_effect=RuntimeError("no")))
                with mock.patch.object(rr, "_senses", broken):
                    self.assertEqual(fn("2026-01-01"), [])
            finally:
                monitor.stop()
                proc.kill()
                proc.wait()

    def test_oracle_token_ok_rejects_non_strings(self):
        # _oracle_token_ok's type guard: a
        # presented token that is not a string
        # never matches, and never reaches the
        # digest comparison.
        self.assertFalse(rr._oracle_token_ok(123, "tok"))
        self.assertFalse(rr._oracle_token_ok("tok", None))
        self.assertTrue(rr._oracle_token_ok("tok", "tok"))
        self.assertFalse(rr._oracle_token_ok("tok", "other"))

    def test_do_get_deterministic_page(self):
        # do_GET's deterministic branch: the
        # chat page on a Pi Light box says so,
        # over the real loopback server.
        import http.client
        cfg = {"oracle_mode": "deterministic"}
        httpd = rr.make_oracle_server(cfg, "127.0.0.1", 0,
                                      base_dir=None)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever,
                              daemon=True)
        th.start()
        try:
            conn = http.client.HTTPConnection(
                "127.0.0.1", port, timeout=10)
            conn.request("GET", "/")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", "replace")
            self.assertEqual(resp.status, 200)
            self.assertIn("deterministic", body)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_registry_watch_snapshot_write_swallowed(self):
        # _registry_watch's snapshot-write
        # swallow: an unwritable snapshot path
        # costs the diff memory, never the
        # report. Driven as on Windows (the
        # platform gate is the only thing
        # standing between Linux and this
        # code); the snapshot seam is a fake.
        snap = {"keys": {}, "services": {"count": 2,
                                         "hash": "h"}}
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "afile")
            with open(base, "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            with mock.patch.object(sys, "platform",
                                   "win32"), \
                    mock.patch.object(
                        rr, "_registry_snapshot",
                        return_value=snap):
                blob = rr._registry_watch(base)
        self.assertIn("baseline", blob)


if __name__ == "__main__":
    unittest.main()
