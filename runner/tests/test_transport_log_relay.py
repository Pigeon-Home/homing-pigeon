#!/usr/bin/env python3
"""Transport extension output: the log relay (runner/transports.py).

Field failure behind this suite (2026-10-21): the email transport
failed every poll for an afternoon -- OAuth invalid_grant -- and
none of it reached runner.log or the console. The extension's
output went only to a sidecar file (transport-extensions/<name>/
extension.log) whose lines had no timestamps, so the runner
looked healthy while its only enabled transport was dead.

The supervisor now pumps each child's stdout: every line is
relayed into the runner log ("transport <name>: <line>", level
preserved) and appended to the sidecar with the runner log's
timestamp format. These tests pin that with a fake Popen whose
stdout is a byte stream: relay, levels, the timestamped sidecar,
restart, the full-pipe case, and the no-stdout case.
"""

import io
import os
import re
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import transports  # noqa: E402

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
SENDER = "runner@example.com"
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")


def _cfg(tmp, **over):
    cfg = {
        "mailbox_user": SENDER,
        "mailbox_password": "test-gmail-password",
        "shared_secret": SECRET,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "poll_interval_sec": 20,
        "max_job_age_sec": 3600,
        "max_output_bytes": 100000,
        "base_dir": tmp,
        "default_timeout_sec": 300,
        "transports": ["file"],
    }
    cfg.update(over)
    return cfg


class _PipeProc:
    """A supervised child with a stdout stream."""

    def __init__(self, argv, stdout=None, **kw):
        self.argv = argv
        self.kw = kw
        self.stdout = stdout
        self.pid = id(self) % 10000 + 1000
        self.dead = False
        self.code = None
        self.terminated = False

    def poll(self):
        return self.code if self.dead else None

    def terminate(self):
        self.terminated = True
        self.dead = True
        self.code = 0

    def kill(self):
        self.dead = True
        self.code = -9

    def wait(self, timeout=None):
        return self.code


class LinePartsTest(unittest.TestCase):
    def test_level_prefixes_are_parsed(self):
        self.assertEqual(
            transports._extension_line_parts("WARN: pass failed"),
            ("WARN", "pass failed"))
        self.assertEqual(
            transports._extension_line_parts("ERROR: boom"),
            ("ERROR", "boom"))
        self.assertEqual(
            transports._extension_line_parts("INFO: polling x"),
            ("INFO", "polling x"))

    def test_warning_normalizes_to_warn(self):
        self.assertEqual(
            transports._extension_line_parts("WARNING: slow"),
            ("WARN", "slow"))

    def test_unprefixed_lines_pass_through_as_info(self):
        frame = '  File "x.py", line 1, in <module>'
        self.assertEqual(
            transports._extension_line_parts(frame), ("INFO", frame))
        self.assertEqual(
            transports._extension_line_parts("plain print"),
            ("INFO", "plain print"))


class RelayTest(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.procs = []
        self.payloads = []
        self.next_stdout = None
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.clock = [1000.0]

    def _supervisor(self, cfg=None):
        def fake_popen(argv, **kw):
            kw.pop("stdout", None)   # ours replaces the PIPE
            if self.payloads:
                stream = io.BytesIO(self.payloads.pop(0))
            else:
                stream = self.next_stdout
            proc = _PipeProc(argv, stdout=stream, **kw)
            self.procs.append(proc)
            return proc

        return transports.TransportSupervisor(
            cfg or _cfg(self.tmp), self.tmp,
            log=lambda m, level="INFO":
            self.lines.append((level, m)),
            popen=fake_popen, clock=lambda: self.clock[0])

    def _pump(self, sup, name="file"):
        pump = sup.processes[name].get("pump")
        self.assertIsNotNone(pump)
        pump.join(timeout=10)
        self.assertFalse(pump.is_alive())

    def _sidecar(self, name="file"):
        path = os.path.join(
            transports.channel_paths(self.tmp, name)["root"],
            "extension.log")
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_extension_lines_reach_the_runner_log(self):
        self.payloads = [
            b"INFO: file transport: watching the inbox\n"
            b"hello from the child\n"]
        sup = self._supervisor()
        sup.start()
        self._pump(sup)
        self.assertIn(
            ("INFO", "transport file: file transport: "
                     "watching the inbox"), self.lines)
        self.assertIn(
            ("INFO", "transport file: hello from the child"),
            self.lines)
        sup.stop()

    def test_warn_and_failure_lines_keep_their_level(self):
        # The exact shape of the field failure: an OAuth
        # invalid_grant WARN from the email transport must land
        # in the runner log as a WARN, not be flattened to INFO.
        self.payloads = [
            b"WARN: email transport: pass failed: "
            b"OAuthRefreshError('Google rejected the refresh "
            b"token (HTTP 400: invalid_grant)')\n"
            b"ERROR: file transport: channel unreadable\n"
            b"WARNING: file transport: slow pass\n"]
        sup = self._supervisor()
        sup.start()
        self._pump(sup)
        self.assertIn(
            ("WARN", "transport file: email transport: "
                     "pass failed: OAuthRefreshError('Google "
                     "rejected the refresh token (HTTP 400: "
                     "invalid_grant)')"), self.lines)
        self.assertIn(
            ("ERROR", "transport file: file transport: "
                      "channel unreadable"), self.lines)
        self.assertIn(
            ("WARN", "transport file: file transport: "
                     "slow pass"), self.lines)
        sup.stop()

    def test_sidecar_lines_are_timestamped_not_double_stamped(
            self):
        self.payloads = [
            b"WARN: email transport: pass failed: nope\n"
            b"a raw traceback frame\n"]
        sup = self._supervisor()
        sup.start()
        self._pump(sup)
        side = self._sidecar()
        self.assertEqual(len(side), 2)
        for line in side:
            self.assertRegex(line, STAMP)
        self.assertIn("[WARN] email transport: pass failed: "
                      "nope", side[0])
        self.assertNotIn("WARN:", side[0])
        self.assertTrue(side[1].endswith("a raw traceback frame"))
        sup.stop()

    def test_restart_relays_the_new_childs_lines(self):
        self.payloads = [b"INFO: first incarnation\n",
                          b"INFO: second incarnation\n"]
        sup = self._supervisor()
        sup.start()
        self._pump(sup)
        first = self.procs[0]
        first.dead = True
        first.code = 1
        sup.check()               # death noticed, backoff set
        self.clock[0] += 2.0
        sup.check()               # restart fires
        self.assertEqual(len(self.procs), 2)
        self._pump(sup)
        relayed = [m for _level, m in self.lines]
        self.assertTrue(any("first incarnation" in m
                            for m in relayed), self.lines)
        self.assertTrue(any("second incarnation" in m
                            for m in relayed), self.lines)
        side = self._sidecar()
        self.assertTrue(any("first incarnation" in line
                            for line in side), side)
        self.assertTrue(any("second incarnation" in line
                            for line in side), side)
        sup.stop()

    def test_a_chatty_child_never_blocks_on_a_full_pipe(self):
        total = 3000
        read_fd, write_fd = os.pipe()
        self.next_stdout = os.fdopen(read_fd, "rb")
        sup = self._supervisor()
        sup.start()

        def flood():
            with os.fdopen(write_fd, "wb") as w:
                for i in range(total):
                    w.write(b"INFO: spam line %d %s\n"
                            % (i, b"x" * 60))

        writer = threading.Thread(target=flood)
        writer.start()
        writer.join(timeout=30)
        # Without a draining pump the writer blocks once the
        # pipe buffer fills (~64 KiB) and never finishes.
        self.assertFalse(writer.is_alive())
        self._pump(sup)
        relayed = [m for _level, m in self.lines
                   if "spam line" in m]
        self.assertEqual(len(relayed), total)
        self.assertEqual(len(self._sidecar()), total)
        sup.stop()

    def test_a_raising_log_call_does_not_stop_the_pump(self):
        self.payloads = [
            b"INFO: before the boom\n"
            b"INFO: boom line\n"
            b"INFO: after the boom\n"]
        sup = self._supervisor()

        def flaky(msg, level="INFO"):
            if "boom line" in msg:
                raise RuntimeError("log backend down")
            self.lines.append((level, msg))

        sup.log = flaky
        sup.start()
        self._pump(sup)
        relayed = [m for _level, m in self.lines]
        self.assertTrue(any("after the boom" in m
                            for m in relayed), self.lines)
        side = self._sidecar()
        self.assertEqual(len(side), 3)  # the sidecar kept all 3
        sup.stop()

    def test_a_child_without_stdout_starts_no_pump(self):
        class BareProc(_PipeProc):
            pass

        bare = []

        def fake_popen(argv, **kw):
            kw.pop("stdout", None)
            proc = BareProc(argv, stdout=None, **kw)
            del proc.stdout       # the old fake shape: no attr
            bare.append(proc)
            return proc

        sup = transports.TransportSupervisor(
            _cfg(self.tmp), self.tmp,
            log=lambda m, level="INFO":
            self.lines.append((level, m)),
            popen=fake_popen, clock=lambda: self.clock[0])
        sup.start()
        rec = sup.processes["file"]
        self.assertNotIn("pump", rec)
        sup.stop()
        self.assertTrue(bare[0].terminated)


if __name__ == "__main__":
    unittest.main()
