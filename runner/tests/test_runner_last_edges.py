"""The last dark lines in runner.py: platform flags, swallowed
errors, and the local-signal front end.

O_BINARY is set to 0 so the Windows flag line runs without
changing the open flags on Linux. No mailbox and no model.
"""

import json
import os
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
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(
                    rr, "_json_safe",
                    side_effect=ValueError("bad payload")), \
                mock.patch.object(
                    os, "close", side_effect=OSError("stuck")):
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


if __name__ == "__main__":
    unittest.main()
