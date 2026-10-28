# Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c
"""Deterministic tests for code only a fuzz seed or another OS reached.

A local rig measurement (runner/tools/stdlib_coverage.py, no
hypothesis on the box) put these arms on the never-run list, most of
them also on CI's (docs/reports/v3.13.62/coverage-gaps.md). Each was
reached, if at all, by a random property example or on one platform
only, so a coverage number could move with a seed. Each test here
reaches its arm with one fixed input and asserts what the arm is for.
"""
import ctypes
import importlib.util
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.guard import extreview, sandbox  # noqa: E402
from runner.wire import dtlsproto, transports, verify  # noqa: E402


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, *rel.split("/")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Kernel32:
    """GlobalMemoryStatusEx, answering with the numbers it is given."""

    def __init__(self, ok=1, total=0, avail=0, raises=None):
        self.ok, self.total, self.avail, self.raises = ok, total, avail, raises
        self.calls = 0

    def GlobalMemoryStatusEx(self, ref):
        self.calls += 1
        if self.raises:
            raise self.raises
        status = ref._obj
        if status.dwLength != ctypes.sizeof(type(status)):
            return 0  # Windows refuses a struct whose length is wrong
        status.ullTotalPhys = self.total
        status.ullAvailPhys = self.avail
        return self.ok


class PiHealthWindowsMemoryTest(unittest.TestCase):
    """_mem_avail_pct_windows runs only where os.name is nt; CI's
    Windows legs do not run the pi-health extension, so it had never
    run anywhere. The kernel call is replaced, the rest is real."""

    @classmethod
    def setUpClass(cls):
        cls.ph = _load("runner/extensions/pi-health/pi_health.py",
                       "pi_health_local_rig")

    def _measure(self, kernel):
        windll = mock.Mock(kernel32=kernel)
        with mock.patch.object(self.ph.os, "name", "nt"), \
                mock.patch.object(ctypes, "windll", windll, create=True):
            return self.ph._mem_avail_pct_windows()

    def test_available_over_total_as_a_percent(self):
        k = _Kernel32(total=8 * 2 ** 30, avail=2 * 2 ** 30)
        self.assertEqual(self._measure(k), 25.0)
        self.assertEqual(k.calls, 1)

    def test_a_refused_call_is_unmeasurable(self):
        self.assertIsNone(self._measure(_Kernel32(ok=0, total=10, avail=5)))

    def test_a_zero_total_is_unmeasurable(self):
        self.assertIsNone(self._measure(_Kernel32(total=0, avail=0)))

    def test_a_raising_call_is_unmeasurable_not_a_crash(self):
        self.assertIsNone(self._measure(_Kernel32(raises=OSError("gone"))))

    def test_off_windows_it_answers_none_without_asking(self):
        k = _Kernel32(total=10, avail=5)
        with mock.patch.object(self.ph.os, "name", "posix"):
            self.assertIsNone(self.ph._mem_avail_pct_windows())
        self.assertEqual(k.calls, 0)


class SoftflowdMalformedDatagramTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sf = _load("runner/extensions/softflowd-feed/softflowd_feed.py",
                       "softflowd_feed_local_rig")

    def test_a_truncated_v5_header_is_no_flows_never_a_raise(self):
        for data in (b"\x00\x05", b"\x00\x05\x00\x01\x00",
                     b"\x00\x05" + b"\x00" * 21):
            flows, templates = self.sf.decode_datagram(data, {}, now=0)
            self.assertEqual(flows, [], data)
            self.assertEqual(templates, {})

    def test_a_decoder_that_raises_is_no_flows_never_a_raise(self):
        # Both decoders check every length first, so no datagram found
        # reaches this net; it is what keeps decode_datagram's "never
        # raises" when a decoder has a defect.
        import struct
        kept = {"k": "v"}
        for name, version, exc in (
                ("_decode_v5", 5, struct.error("short")),
                ("_decode_templated", 9, ValueError("odd field")),
                ("_decode_templated", 10, OverflowError("huge"))):
            with mock.patch.object(self.sf, name, side_effect=exc):
                flows, templates = self.sf.decode_datagram(
                    version.to_bytes(2, "big") + b"\x00" * 30, kept, now=0)
            self.assertEqual(flows, [], name)
            self.assertIs(templates, kept)

    def test_a_truncated_v9_header_keeps_the_templates(self):
        kept = {"k": "v"}
        flows, templates = self.sf.decode_datagram(b"\x00\x09\x00", kept,
                                                   now=0)
        self.assertEqual(flows, [])
        self.assertIs(templates, kept)


class DtlsShortRecordTest(unittest.TestCase):
    """Every "record too short" arm of _RecordSealer.open, by header
    flag: 0x04 a connection id, 0x10 a 16-bit sequence, 0x08 a length.
    The property suite reached these only by chance."""

    def setUp(self):
        self.opener = dtlsproto._RecordSealer(b"\x01" * 32)

    def _short(self, record):
        with self.assertRaises(dtlsproto.DtlsError) as cm:
            self.opener.open(1, record)
        self.assertEqual(str(cm.exception), "record too short")

    def test_empty(self):
        self._short(b"")

    def test_a_cid_flag_with_no_cid_length(self):
        self._short(bytes([0x24]))

    def test_a_16_bit_sequence_cut_after_one_octet(self):
        self._short(bytes([0x30, 0x00]))

    def test_an_8_bit_sequence_with_nothing_after_the_flags(self):
        self._short(bytes([0x20]))

    def test_a_length_flag_cut_before_the_length(self):
        self._short(bytes([0x28, 0x05, 0x00]))

    def test_an_implied_length_under_one_tag(self):
        # No length field: the body is the rest, and 16 octets cannot
        # hold a 16-octet tag and a content type.
        self._short(bytes([0x20, 0x05]) + b"\x00" * 16)

    def test_a_declared_length_past_the_end(self):
        self._short(bytes([0x28, 0x05, 0x00, 0x40]) + b"\x00" * 20)

    def test_a_record_that_is_long_enough_reaches_the_tag_check(self):
        sealer = dtlsproto._RecordSealer(b"\x01" * 32)
        record = sealer.seal(1, 23, b"hello", b"")
        tampered = record[:-1] + bytes([record[-1] ^ 1])
        with self.assertRaises(Exception) as cm:
            self.opener.open(1, tampered)
        self.assertNotEqual(str(cm.exception), "record too short")
        self.assertEqual(self.opener.open(1, record)[:2], (23, b"hello"))


class DoorPolicyArmsTest(unittest.TestCase):
    SECRETS = {"": "a" * 64, "ops": "b" * 64}

    def test_an_unknown_door_is_refused_before_anything_is_read(self):
        self.assertEqual(
            verify.check_door_policy({}, self.SECRETS, "ops", "shell"),
            "unknown door")

    def test_a_key_id_that_is_not_a_string_is_refused(self):
        for key_id in (None, 3, b"ops"):
            self.assertEqual(
                verify.check_door_policy({}, self.SECRETS, key_id, "query"),
                "invalid key id")

    def test_a_config_that_is_not_a_dict_reads_as_empty(self):
        self.assertIsNone(
            verify.check_door_policy(["not", "a", "dict"], self.SECRETS,
                                     "ops", "query"))
        self.assertEqual(
            verify.check_door_policy([], self.SECRETS, "ops", "query"),
            verify.check_door_policy({}, self.SECRETS, "ops", "query"))

    def test_unreadable_policies_refuse_and_say_why(self):
        with mock.patch.object(verify, "build_key_policies",
                               side_effect=ValueError("bad policy")):
            why = verify.check_door_policy(
                {"key_policies": {}}, self.SECRETS, "ops", "board")
        self.assertEqual(why, "key policies unreadable: bad policy")

    def test_the_owner_key_is_exempt_from_the_deny_flag_only(self):
        # Q103 item 2: default deny never refuses the owner's key, but
        # a key_policies[""] entry binds it at these doors as at jobs.
        deny = {"key_policies_default_deny": True}
        for door in verify.DOORS:
            self.assertIsNone(verify.check_door_policy(
                deny, self.SECRETS, "", door), door)
            self.assertIn("no key policy entry", verify.check_door_policy(
                deny, self.SECRETS, "ops", door))

class TransportApiMismatchTest(unittest.TestCase):
    """The loader admits any api_version >= 1 it provides, and today
    the transport and extension APIs are both 1, so a mismatch cannot
    reach discover_transport_extensions from a real folder. The
    refusal is what keeps a v2 transport off a v1 runner the day they
    differ; this pins it with the loader's answer stood in."""

    def test_a_transport_of_another_api_is_refused_readably(self):
        good = {"name": "mine", "api_version": transports.TRANSPORT_API_VERSION,
                "kind": "transport", "entry": ["x"], "dir": "/nonexistent"}
        newer = dict(good, name="later",
                     api_version=transports.TRANSPORT_API_VERSION + 1)
        with mock.patch.object(transports._extensions, "load_extensions",
                               return_value=({"mine": good, "later": newer},
                                             [])), \
                mock.patch.object(transports, "_extreview", None):
            registry, problems = transports.discover_transport_extensions(
                {}, ROOT)
        self.assertNotIn("later", registry)
        refusals = [p for p in problems if "'later'" in p]
        self.assertTrue(refusals, problems)
        self.assertIn("declares transport API v%d" % newer["api_version"],
                      refusals[0])
        self.assertIn("speaks v%d" % transports.TRANSPORT_API_VERSION,
                      refusals[0])


class SendJobInlineFileRefusalTest(unittest.TestCase):
    """`new --inline-file` refuses a bad spec before anything is
    signed: the author hears it at the keyboard and no job leaves.
    The suite drives send_job.py mostly as a child process, so these
    arms ran only where a child is measured."""

    SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))
        import send_job
        cls.SJ = send_job

    def _new(self, spec):
        import contextlib
        import io
        import tempfile
        d = tempfile.mkdtemp(prefix="hp-inline-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, True))
        script = os.path.join(d, "job.sh")
        with open(script, "w") as fh:
            fh.write("true\n")
        argv = ["send_job.py", "new", "--kind", "exec", "--script-file",
                script, "--inline-file", spec.replace("{d}", d),
                "--cleartext", "--secret", self.SECRET]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = self.SJ.main()
        return rc, out.getvalue(), err.getvalue()

    def test_a_spec_without_a_path_is_refused(self):
        rc, out, err = self._new("only-a-name")
        self.assertEqual(rc, 2)
        self.assertIn("bad --inline-file spec (want name=path)", err)
        self.assertEqual(out, "")

    def test_a_name_the_runner_would_reject_is_refused_here(self):
        rc, out, err = self._new("../escape={d}/job.sh")
        self.assertEqual(rc, 2)
        self.assertIn("bad --inline-file name '../escape'", err)
        self.assertEqual(out, "")

    def test_an_unreadable_path_is_refused(self):
        rc, out, err = self._new("data.bin={d}/no-such-file")
        self.assertEqual(rc, 2)
        self.assertIn("cannot read --inline-file", err)
        self.assertIn("no-such-file", err)
        self.assertEqual(out, "")


class ReadOutputReasonsTest(unittest.TestCase):
    """_read_output answers every failure with a reason, never an
    exception: a declared output that cannot be read safely comes
    home as `omitted`, and the job's result still goes out. The arms
    below need a filesystem that fails mid-read, so the OS calls are
    stood in for, one at a time, for the one path under test."""

    def setUp(self):
        import tempfile
        from runner.ops import exec as ex
        self.ex = ex
        # Resolved up front: realpath itself calls lstat, so a test
        # that patches lstat must not depend on realpath resolving a
        # symlinked temp folder (macOS /var).
        self.work = os.path.realpath(tempfile.mkdtemp(prefix="hp-out-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.work, True))
        self.root = self.work
        self.path = os.path.join(self.root, "out.txt")
        with open(self.path, "wb") as fh:
            fh.write(b"x" * 100)

    def _read(self, limit=1000):
        return self.ex._read_output(self.work, self.root, "out.txt", limit)

    def test_a_clean_read(self):
        self.assertEqual(self._read(), (b"x" * 100, 100, None))

    def test_a_path_realpath_cannot_resolve_is_unreadable(self):
        with mock.patch.object(self.ex.os.path, "realpath",
                               side_effect=ValueError("embedded null byte")):
            self.assertEqual(self._read(), (None, 0, "unreadable"))

    def test_an_lstat_refusal_other_than_missing_is_unreadable(self):
        with mock.patch.object(self.ex.os, "lstat",
                               side_effect=PermissionError("denied")):
            self.assertEqual(self._read(), (None, 0, "unreadable"))

    def test_an_open_refusal_is_unreadable(self):
        with mock.patch.object(self.ex.os, "open",
                               side_effect=PermissionError("denied")):
            self.assertEqual(self._read(), (None, 0, "unreadable"))

    def test_a_file_swapped_after_the_check_is_changed_while_read(self):
        real_fstat = os.fstat

        def other_inode(fd):
            st = real_fstat(fd)
            fields = list(st)
            fields[1] = st.st_ino + 1  # st_ino
            return os.stat_result(fields)

        with mock.patch.object(self.ex.os, "fstat", side_effect=other_inode):
            self.assertEqual(self._read(), (None, 0, "changed while read"))

    def test_a_file_that_grew_past_the_limit_while_read_is_too_large(self):
        real_lstat = os.lstat

        def looked_small(path, *a, **k):
            st = real_lstat(path, *a, **k)
            if path != self.path:
                return st
            fields = list(st)
            fields[6] = 10  # st_size, as checked before the read
            return os.stat_result(fields)

        with mock.patch.object(self.ex.os, "lstat", side_effect=looked_small):
            data, size, reason = self._read(limit=50)
        self.assertEqual((data, reason), (None, "too_large"))
        self.assertGreater(size, 50)

    def test_collect_omits_every_name_when_the_workdir_cannot_resolve(self):
        with mock.patch.object(self.ex.os.path, "realpath",
                               side_effect=OSError("gone")):
            got = self.ex._collect_outputs(self.work, ["a", "b/c"], {})
        self.assertEqual(got, [{"name": "a", "omitted": "unreadable"},
                               {"name": "b/c", "omitted": "unreadable"}])


class PanicNeverRaisesTest(unittest.TestCase):
    """The panic word stops the box even when the disk, a job or the
    event log fails underneath it: every failure inside fire() and
    kill() is swallowed, and the in-process flag holds."""

    def setUp(self):
        import tempfile
        from runner.guard import panic
        self.panic = panic
        panic._reset_for_tests()
        self.addCleanup(panic._reset_for_tests)
        self.base = tempfile.mkdtemp(prefix="hp-panic-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.base, True))

    def test_a_flag_write_that_fails_still_stops_every_job(self):
        killed, events = [], []
        self.panic.set_kill(killed.append)
        self.panic.register("job-1")
        with mock.patch.object(self.panic._atomicio, "write_json",
                               side_effect=OSError("disk full")):
            self.panic.fire(self.base, transport="email",
                            event_sink=events.append)
        self.assertEqual(killed, ["job-1"])
        self.assertIsNone(self.panic.flag(self.base))
        self.assertEqual([e["type"] for e in events], ["panic_fired"])
        self.assertEqual(events[0]["jobs_stopped"], 1)
        # The in-process flag holds: a second word changes nothing.
        self.panic.fire(self.base, event_sink=events.append)
        self.assertEqual(len(events), 1)

    def test_an_event_sink_that_raises_does_not_undo_the_stop(self):
        def broken(_event):
            raise RuntimeError("log gone")
        self.panic.fire(self.base, event_sink=broken)
        self.assertIsNotNone(self.panic.flag(self.base))

    def test_a_kill_that_raises_is_swallowed(self):
        def broken(_proc):
            raise ProcessLookupError("already gone")
        self.panic.set_kill(broken)
        self.panic.kill("job")  # no raise

    def test_without_a_kill_function_the_process_is_killed_directly(self):
        proc = mock.Mock()
        self.panic.set_kill(None)
        self.panic.kill(proc)
        proc.kill.assert_called_once_with()
        proc.kill.side_effect = OSError("gone")
        self.panic.kill(proc)  # no raise

    def test_a_subject_header_that_does_not_decode_is_taken_as_it_stands(self):
        with mock.patch.object(self.panic.email.header, "decode_header",
                               side_effect=ValueError("bad encoded word")):
            self.assertEqual(self.panic._subject_text("  a   b "), "a b")

    def test_unusable_state_files_read_as_not_armed(self):
        import json
        path = os.path.join(self.base, self.panic.STATE_FILE)
        for record in ({"v": 1, "salt": 7, "sha384": "0" * 96},
                       {"v": 1, "salt": "zz" * 16, "sha384": "0" * 96},
                       {"v": 1, "salt": "00" * 8, "sha384": "0" * 96},
                       {"v": 1, "salt": "00" * 16, "sha384": "0" * 95}):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh)
            self.assertIsNone(self.panic.load(self.base), record)

    def test_arming_with_a_word_off_the_list_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            self.panic.arm(self.base, word="not on the list at all xyzzy")
        self.assertIn("six words", str(cm.exception))
        self.assertIsNone(self.panic.load(self.base))


class SandboxOffLinuxTest(unittest.TestCase):
    def test_off_linux_names_the_platform_and_never_looks_for_bwrap(self):
        with mock.patch.object(sandbox.sys, "platform", "darwin"), \
                mock.patch.object(sandbox.shutil, "which",
                                  side_effect=AssertionError("looked")):
            why = sandbox.startup_problem()
        self.assertIn("Linux-only", why)
        self.assertIn("darwin", why)


class ExtreviewUnparsableTest(unittest.TestCase):
    """3.9 to 3.11 raise ValueError or RecursionError from ast.parse
    where 3.12 raises SyntaxError; the CI interpreter is 3.12, so the
    older arm ran only on the python-range leg."""

    def test_a_parser_value_error_is_a_high_syntax_finding(self):
        for exc in (ValueError("source code string cannot contain null "
                               "bytes"), RecursionError("too deep")):
            findings = []
            with mock.patch.object(extreview.ast, "parse", side_effect=exc):
                extreview._scan_python("pkg/mod.py", "x = 1\n", set(),
                                       findings, set())
            self.assertEqual(len(findings), 1, findings)
            text = repr(findings[0])
            self.assertIn("syntax", text)
            self.assertIn("high", text)
            self.assertIn("does not parse", text)


if __name__ == "__main__":
    unittest.main()
