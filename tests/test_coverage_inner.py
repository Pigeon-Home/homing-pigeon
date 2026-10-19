"""The branches the coverage run left in opinion and remediation.

Named behaviors, not random bytes. Probes are injected. The
Windows snapshot is a fake kernel, so this runs on Linux.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from runner import opinion as op
from runner import remediation as rem


class OpinionSettingsEdges(unittest.TestCase):
    def test_non_dicts_fall_back_to_the_defaults(self):
        self.assertEqual(op.ceiling_mode(None), "repair")
        self.assertIsNone(op.requested_mode(["repair"]))
        self.assertEqual(op.predict_setting("always"), "requested")
        self.assertEqual(op.repair_setting(None), "rejudge")
        self.assertFalse(op.model_enabled(None))

    def test_model_flag_accepts_the_true_spellings_only(self):
        for value in (True, 1, " true ", "YES", "on", "1"):
            self.assertTrue(op.model_enabled(
                {"oracle_opinion_model": value}), value)
        for value in (False, 0, "no", "off", "", None, []):
            self.assertFalse(op.model_enabled(
                {"oracle_opinion_model": value}), value)

    def test_a_non_dict_job_still_has_a_digest(self):
        self.assertEqual(len(op.received_digest("nope")), 96)


class ScriptHintEdges(unittest.TestCase):
    def test_shebang_and_export_are_the_shape_tells(self):
        self.assertEqual(op.script_shape(""), "neutral")
        self.assertEqual(
            op.script_shape("#!/usr/bin/python3\nprint(1)\n"),
            "neutral")
        self.assertEqual(
            op.script_shape("#!/usr/bin/pwsh\nGet-Date\n"),
            "powershell")
        self.assertEqual(
            op.script_shape("#!/bin/sh\necho hi\n"), "posix")
        self.assertEqual(
            op.script_shape("export PATH=/bin\n"), "posix")

    def test_tools_skip_prefixes_builtins_and_cmdlets(self):
        script = "\n".join([
            "# comment",
            "FOO=1 sudo curl",
            "echo skipped-builtin",
            "Get-Date",
            "a|b",
            "one", "two", "three", "four", "five",
            "six", "seven", "eight",
        ])
        names = op._candidate_tools(script)
        self.assertEqual(names[0], "curl")
        self.assertNotIn("echo", names)
        self.assertNotIn("Get-Date", names)
        self.assertNotIn("sudo", names)
        self.assertNotIn("a|b", names)
        self.assertEqual(len(names), 8)
        self.assertNotIn("eight", names)

    def test_paths_ignore_the_shebang_and_stop_at_eight(self):
        lines = ["#!/usr/bin/python3"]
        lines += ["/tmp/p%d" % i for i in range(10)]
        paths = op._candidate_paths("\n".join(lines))
        self.assertNotIn("/usr/bin/python3", paths)
        self.assertLessEqual(len(paths), 8)
        self.assertEqual(op.script_hints(""),
                         {"tools": [], "paths": [], "shape": "neutral"})

    def test_interpreter_family_reads_the_basename(self):
        self.assertEqual(op.interpreter_family(None), "other")
        self.assertEqual(op.interpreter_family([1, "sh"]), "other")
        self.assertEqual(
            op.interpreter_family([r"C:\Windows\System32\bash.exe"]),
            "posix-shell")
        self.assertEqual(
            op.interpreter_family(["/usr/bin/python3"]), "python")
        self.assertEqual(op.interpreter_family(["curl"]), "other")


class GatherFactsEdges(unittest.TestCase):
    def test_a_raising_probe_is_recorded_as_absent(self):
        def boom(*_a, **_k):
            raise OSError("no")

        facts = op.gather_facts(
            {"script": "cat /etc/hosts\n"},
            ["/no/such/interpreter"], ["sh"],
            which=lambda _n: None,
            exists=boom, os_name="posix")
        self.assertFalse(facts["interpreter_present"])
        self.assertIs(facts["paths"]["/etc/hosts"], False)
        facts = op.gather_facts(
            {"script": "wget https://example.test\n"},
            ["curl"], ["sh"], which=boom, exists=boom,
            os_name="posix")
        self.assertFalse(facts["interpreter_present"])
        self.assertIs(facts["tools"]["wget"], False)

    def test_a_foreign_posix_path_on_windows_is_not_probed(self):
        facts = op.gather_facts(
            {"script": "cat /etc/hosts\n"},
            ["powershell"], ["powershell"],
            which=lambda _n: "powershell",
            exists=lambda _p: True,
            os_name="nt")
        self.assertIn("/etc/hosts", facts["paths"])
        self.assertIsNone(facts["paths"]["/etc/hosts"])
        self.assertEqual(facts["tools"], {})

    def test_the_interpreter_itself_is_not_a_missing_tool(self):
        facts = op.gather_facts(
            {"script": "python3 job.py\n"},
            ["python3"], ["python3"],
            which=lambda name: name,
            exists=lambda _p: True,
            os_name="posix")
        self.assertNotIn("python3", facts["tools"])


class Tier1Edges(unittest.TestCase):
    def test_garbage_facts_find_nothing(self):
        self.assertEqual(op.tier1_findings({}, "nope"), [])
        odd = {"os_name": "posix", "interpreter": ["sh"],
               "interpreter_present": True, "shape": "other",
               "tools": {}, "paths": {}}
        self.assertEqual(op.tier1_findings({}, odd), [])

    def test_more_than_three_missing_tools_are_summarized(self):
        facts = {
            "os_name": "posix",
            "interpreter": ["sh"],
            "interpreter_present": True,
            "shape": "neutral",
            "tools": {name: False for name in
                      ("a", "b", "c", "d")},
            "paths": {"/etc/hosts": False, "/no/such": False},
        }
        findings = op.tier1_findings({}, facts)
        details = [f["detail"] for f in findings]
        self.assertEqual(
            sum(1 for f in findings if f["kind"] == "tool_missing"), 4)
        self.assertTrue(any("and 1 more" in d for d in details))
        self.assertTrue(any("does not exist" in d for d in details))

    def test_members_cover_the_note_edges(self):
        bare = op.form_member("advise", "likely_success", "",
                              model_note="looks fine")
        self.assertTrue(bare["note"].startswith("Model-formed note:"))
        repaired = op.form_member(
            "repair", "likely_failure", "fixed", repaired=True)
        self.assertTrue(repaired["repaired"])
        self.assertNotIn("received_digest", repaired)
        self.assertEqual(op.with_model_note("nope", "x"), "nope")
        self.assertEqual(op.with_model_note({}, ""), {})
        extended = op.extend_member_outcome(
            {"verdict": "likely_success", "note": "ok"}, [])
        self.assertIn("no obvious environmental cause", extended["note"])


class RemediationProbeEdges(unittest.TestCase):
    def test_clock_and_page_fall_back_when_sysconf_fails(self):
        with mock.patch.object(os, "sysconf", side_effect=AttributeError):
            self.assertEqual(rem._clk_tck(), 100.0)
            self.assertEqual(rem._page_size(), 4096)

    def test_proc_parents_skip_junk_and_a_missing_proc(self):
        with mock.patch.object(os, "listdir", side_effect=OSError):
            self.assertEqual(rem._proc_parents(), {})

        def listdir(path):
            self.assertEqual(path, "/proc")
            return ["self", "12"]

        def opener(path, *args, **kwargs):
            raise OSError("gone")

        with mock.patch.object(os, "listdir", listdir), \
                mock.patch("builtins.open", opener):
            self.assertEqual(rem._proc_parents(), {})

    def test_proc_usage_survives_a_missing_statm(self):
        real_open = open

        def opener(path, *args, **kwargs):
            if str(path).endswith("/stat"):
                return real_open(os.devnull, "r")
            raise OSError("no statm")

        # /dev/null is empty, so the stat parse fails closed.
        with mock.patch("builtins.open", opener):
            self.assertIsNone(rem._proc_usage(1, 100, 4096))

    def test_a_real_stat_line_and_a_bad_meminfo(self):
        text = "1 (python) S 0 1 1 0 -1 0 0 0 0 0 5 6 0\n"
        statm = "10 4 3 2 0 1 0\n"

        class _Buf:
            def __init__(self, body):
                self.body = body

            def read(self):
                return self.body

            def __iter__(self):
                return iter(self.body.splitlines(True))

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(path, *args, **kwargs):
            path = str(path)
            if path.endswith("/stat"):
                return _Buf(text)
            if path.endswith("/statm"):
                return _Buf(statm)
            if path == "/proc/meminfo":
                return _Buf("MemTotal: nope\n")
            raise OSError(path)

        with mock.patch("builtins.open", opener):
            usage = rem._proc_usage(7, 100, 4096)
        self.assertEqual(usage[0], 0.11)
        self.assertEqual(usage[1], 4 * 4096)
        with mock.patch("builtins.open", opener), \
                mock.patch.object(os, "sysconf",
                                  side_effect=OSError("no")):
            self.assertIsNone(rem.total_memory_bytes())

    def test_sample_tree_without_proc_is_just_the_root(self):
        with mock.patch.object(os.path, "isdir", return_value=False):
            self.assertEqual(rem.sample_tree(4), {4: (0.0, None)})


class QuarantineEdges(unittest.TestCase):
    def test_unreadable_files_do_not_stop_the_byte_count(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hi")
            with mock.patch.object(
                    os.path, "getsize", side_effect=OSError("no")):
                self.assertEqual(rem._dir_bytes(d), 0)

    def test_a_failed_move_returns_none_and_a_failed_marker_stays(self):
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, "work")
            os.makedirs(work)
            with mock.patch.object(os, "makedirs",
                                   side_effect=OSError("full")):
                self.assertIsNone(rem.quarantine_job(
                    d, "job-1", work, {}))
            dest = rem.quarantine_job(d, "job-1", work, {"why": "x"})
            self.assertTrue(dest)
            again = os.path.join(d, "work2")
            os.makedirs(again)
            second = rem.quarantine_job(d, "job-1", again, {})
            self.assertTrue(second.endswith("job-1-2"))

    def test_digest_rewrite_skips_a_match_and_swallows_a_bad_write(self):
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, "work")
            os.makedirs(work)
            dest = rem.quarantine_job(
                d, "job-1", work, {"received_digest": "abc"})
            self.assertTrue(dest)
            rem.fix_marker_digest(d, "job-1", "abc")
            with mock.patch("builtins.open", side_effect=OSError):
                rem.fix_marker_digest(d, "job-1", "def")


class AvReferralEdges(unittest.TestCase):
    def test_a_raising_scan_is_skipped_and_a_later_hit_confirms(self):
        calls = {"n": 0}

        def run(_argv, **_k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("down")

            class _Proc:
                returncode = 1
            return _Proc()

        verdict, detail = rem.av_referral(
            ["a.bin", "b.bin"], run=run,
            which=lambda _n: "/usr/bin/clamdscan",
            os_name="posix")
        self.assertEqual(verdict, "confirmed")
        self.assertIn("scan failed", detail)


class WindowsSnapshotEdges(unittest.TestCase):
    def test_the_fake_kernel_walks_parents_and_usage(self):
        import ctypes

        class Kernel:
            def __init__(self):
                self.nexts = 0

            def CreateToolhelp32Snapshot(self, _flags, _pid):
                self.nexts = 0
                return 7

            def Process32FirstW(self, _snap, ref):
                ref._obj.th32ProcessID = 10
                ref._obj.th32ParentProcessID = 1
                return 1

            def Process32NextW(self, _snap, ref):
                self.nexts += 1
                if self.nexts > 1:
                    return 0
                ref._obj.th32ProcessID = 11
                ref._obj.th32ParentProcessID = 10
                return 1

            def CloseHandle(self, _handle):
                return 1

            def OpenProcess(self, _access, _inherit, pid):
                return 3 if pid == 10 else 0

            def GetProcessTimes(self, _h, _c, _e, kern, user):
                kern._obj.hi = 0
                kern._obj.lo = 10_000_000
                user._obj.hi = 0
                user._obj.lo = 0
                return 1

            def GetProcessMemoryInfo(self, _h, counters, _cb):
                counters._obj.WorkingSetSize = 4096
                return 1

            def GlobalMemoryStatusEx(self, ref):
                ref._obj.ullTotalPhys = 1024
                return 1

        kernel = Kernel()

        def windll(name, use_last_error=True):
            if name == "psapi":
                raise OSError("no psapi")
            return kernel

        with mock.patch.object(ctypes, "WinDLL", windll, create=True):
            parents = rem._win_parents()
            usage = rem._win_usage(10)
            missing = rem._win_usage(99)
            total = rem._win_total_memory()
            sample = rem.sample_tree_windows(10)
        self.assertEqual(parents[11], 10)
        self.assertEqual(usage, (1.0, 4096))
        self.assertIsNone(missing)
        self.assertEqual(total, 1024)
        self.assertEqual(sample[10], (1.0, 4096))
        self.assertEqual(sample[11], (0.0, None))

    def test_a_failed_memory_status_is_none(self):
        import ctypes

        class Kernel:
            def GlobalMemoryStatusEx(self, _ref):
                return 0

            def CreateToolhelp32Snapshot(self, _flags, _pid):
                return 0

        with mock.patch.object(ctypes, "WinDLL",
                               lambda *a, **k: Kernel(), create=True):
            self.assertIsNone(rem._win_total_memory())
            self.assertEqual(rem._win_parents(), {})
