"""The branches the coverage run left in opinion and remediation.

Named behaviors, not random bytes. Probes are injected. The
Windows snapshot is a fake kernel, so this runs on Linux.
"""
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

from runner.oracle import opinion as op
from runner.oracle import remediation as rem


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
        # os.sysconf is POSIX-only: create=True installs the
        # failing probe on platforms (Windows) that have no
        # such attribute, so the product's AttributeError
        # fallback is what is under test everywhere.
        with mock.patch.object(os, "sysconf", create=True,
                               side_effect=AttributeError):
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
                mock.patch.object(os, "sysconf", create=True,
                                  side_effect=OSError("no")), \
                mock.patch.object(rem, "_win_total_memory",
                                  return_value=None):
            self.assertIsNone(rem.total_memory_bytes())

    def test_sample_tree_without_proc_is_just_the_root(self):
        if os.name == "nt":
            # Windows never consults /proc: sample_tree
            # dispatches to the Toolhelp sampler instead.
            windows_tree = {4: (0.0, None), 5: (1.5, 4096)}
            with mock.patch.object(
                    rem, "sample_tree_windows",
                    return_value=windows_tree) as sampler:
                self.assertEqual(rem.sample_tree(4), windows_tree)
            sampler.assert_called_once_with(4)
            return
        with mock.patch.object(os.path, "isdir", return_value=False):
            self.assertEqual(rem.sample_tree(4), {4: (0.0, None)})

    def test_sample_tree_dispatch_keys_off_os_name(self):
        # Simulated on any host: "nt" must select the Windows
        # sampler even though this process is not on Windows.
        windows_tree = {4: (0.0, None), 5: (1.5, 4096)}
        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(
                    rem, "sample_tree_windows",
                    return_value=windows_tree) as sampler:
            self.assertEqual(rem.sample_tree(4), windows_tree)
        sampler.assert_called_once_with(4)
        with mock.patch.object(os, "name", "posix"), \
                mock.patch.object(os.path, "isdir",
                                   return_value=False):
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


class MonitorErrorEdges(unittest.TestCase):
    def _monitor(self, work, **kw):
        st = rem.settings({
            "remediation_mode": kw.pop("mode", "deterministic"),
            "remediation_sample_sec": 0.01,
            "remediation_storm_ceiling": 50,
        })
        kw.setdefault("sampler", lambda _pid: {7: (0.0, None)})
        kw.setdefault("kill_fn", lambda _extra: None)
        return rem.JobMonitor(st, "job-m", 7, work, **kw)

    def test_start_is_once_and_a_broken_pass_is_recorded(self):
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work)
            mon.start()
            mon.start()
            mon.stop()
            mon.stop()
            self.assertIsNone(mon._thread)

            def boom(_pid):
                raise OSError("sampler down")

            mon = self._monitor(work, sampler=boom)
            mon.sample_once()
            self.assertTrue(any("sampler down" in e
                                for e in mon.outcome["errors"]))

            mon = self._monitor(work)
            mon.sample_once = lambda: (_ for _ in ()).throw(
                RuntimeError("pass down"))
            mon.start()
            mon._stop.wait(0.2)
            mon.stop()
            self.assertTrue(any("pass down" in e
                                for e in mon.outcome["errors"]))

    def test_a_broken_workdir_does_not_become_a_finding(self):
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "note.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hello")
            mon = self._monitor(work, findings_fn=lambda _t: [])
            with mock.patch.object(os, "walk", side_effect=OSError):
                self.assertEqual(mon._scan_workdir(), 0)
            with mock.patch.object(os, "stat", side_effect=OSError):
                self.assertEqual(mon._scan_workdir(), 0)
            with mock.patch.object(
                    os.path, "getsize",
                    return_value=rem.ARTIFACT_READ_CAP + 1):
                mon._scan_file(path)
            with open(path, "wb") as fh:
                fh.write(b"\xff\xfe")
            mon._scan_file(path)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hello")
            mon = self._monitor(
                work, findings_fn=lambda _t: (_ for _ in ()).throw(
                    RuntimeError("parser")))
            mon._scan_file(path)
            self.assertTrue(any("parser" in e
                                for e in mon.outcome["errors"]))

    def test_a_relpath_failure_still_names_the_file(self):
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "leak.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x")
            mon = self._monitor(
                work, findings_fn=lambda _t: [(
                    "/home/user/.aws/credentials",
                    rem.CREDENTIAL_REASON)])
            with mock.patch.object(
                    os.path, "relpath", side_effect=ValueError):
                mon._scan_file(path)
            self.assertEqual(mon.outcome["suspects"], ["leak.txt"])

    def test_window_readers_that_raise_are_errors_not_kills(self):
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work)

            def alerts(_since):
                raise OSError("alerts down")

            mon = self._monitor(work, base_dir=base, alerts_fn=alerts)
            with mock.patch.object(
                    rem, "confinement_events_in_window",
                    side_effect=OSError("cage")), \
                    mock.patch.object(
                        rem, "resource_events_in_window",
                        side_effect=OSError("res")):
                mon.sample_once()
            text = " ".join(mon.outcome["errors"])
            self.assertIn("cage", text)
            self.assertIn("res", text)
            self.assertIn("alerts", text)
            self.assertIsNone(mon.outcome["acted"])

    def test_a_sense_that_names_the_job_is_a_divergence(self):
        with tempfile.TemporaryDirectory() as work:

            def alerts(_since):
                return [
                    {"title": "other box"},
                    {"title": "saw job-m"},
                ]

            mon = self._monitor(work, base_dir=work, alerts_fn=alerts)
            mon.sample_once()
            kinds = [d["kind"] for d in mon.outcome["divergences"]]
            self.assertIn("sense_alert", kinds)

    def test_a_sealed_off_mode_pages_and_a_second_act_does_not_kill(self):
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work, mode="off")
            mon._sealed = True
            mon._handle(rem.divergence("disk_fill", "grew"))
            self.assertEqual(mon.outcome["page"]["kind"], "disk_fill")
            self.assertIsNone(mon.outcome["acted"])

            mon = self._monitor(work)
            mon.outcome["acted"] = {"authority": "tripwire"}
            mon._handle(rem.divergence("disk_fill", "again"))
            self.assertEqual(mon.outcome["acted"]["authority"],
                             "tripwire")
            self.assertEqual(len(mon.outcome["divergences"]), 1)

            def boom(_pid):
                raise OSError("no tree")

            mon = self._monitor(
                work, sampler=boom,
                kill_fn=lambda _e: (_ for _ in ()).throw(
                    OSError("kill down")))
            mon._kill()
            self.assertTrue(any("kill down" in e
                                for e in mon.outcome["errors"]))


class RecordEdges(unittest.TestCase):
    def test_settings_reject_bools_and_infinities(self):
        st = rem.settings({
            "remediation_storm_ceiling": True,
            "remediation_sample_sec": float("inf"),
            "remediation_oracle_timeout_sec": "nope",
        })
        self.assertGreaterEqual(st["storm_ceiling"], 1)
        self.assertGreater(st["sample_sec"], 0)
        self.assertEqual(rem.divergence_text(None), "")
        self.assertIsNone(rem._parse_iso("not-a-date"))
        self.assertIsNone(rem._parse_iso(""))

    def test_a_torn_jsonl_tail_keeps_only_the_window(self):
        with tempfile.TemporaryDirectory() as base:
            path = os.path.join(base, rem.SECURITY_EVENTS_FILE)
            old = ('{"type":"resource_pressure",'
                   '"at":"2000-01-01T00:00:00Z"}\n')
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            good = ('{"type":"resource_pressure","at":"%s"}\n' % now)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(old + "\nnot-json\n[]\n" + good)
            events = rem.resource_events_in_window(
                base, time.time() - 60)
            self.assertEqual(len(events), 1)
            self.assertEqual(
                rem.resource_events_in_window(base + "-missing", 0),
                [])
            with mock.patch.object(os.path, "getsize",
                                   return_value=10 ** 9):
                tail = rem._read_jsonl_window(path, 0, cap_bytes=80)
            self.assertIsInstance(tail, list)

    def test_an_unserializable_alert_can_still_name_a_pid(self):
        self.assertFalse(rem.alert_names_job("nope", "j", "/w", [1]))
        alert = {"title": "cpu", "detail": {1, 2}}
        self.assertFalse(rem.alert_names_job(alert, "j", "/w", [1]))
        alert = {"title": "cpu pid=7"}
        self.assertTrue(rem.alert_names_job(
            alert, "other", "/no", [7]))

    def test_ask_that_raises_is_an_abstention(self):
        def boom(_q, _c):
            raise TimeoutError("slow")

        decision, reason = rem.ask_oracle_order(boom, "ctx")
        self.assertEqual(decision, "abstain")
        self.assertIn("slow", reason)

    def test_mpcmdrun_search_survives_a_broken_which(self):
        def which(_name):
            raise OSError("path")

        self.assertIsNone(rem.find_mpcmdrun(
            environ={}, which=which, exists=lambda _p: False,
            listdir=lambda _p: (_ for _ in ()).throw(OSError())))

        def exists(path):
            return "Platform" in path

        found = rem.find_mpcmdrun(
            environ={"ProgramFiles": "/pf", "ProgramData": "/pd"},
            which=lambda _n: None, exists=exists,
            listdir=lambda _p: ["1.0", "2.0"])
        self.assertIn("Platform", found)
        self.assertTrue(found.endswith("MpCmdRun.exe"))

    def test_release_and_bounds_fail_closed(self):
        with tempfile.TemporaryDirectory() as base:
            self.assertEqual(
                rem.enforce_quarantine_bounds(base, rem.settings({})),
                [])
            work = os.path.join(base, "work")
            os.makedirs(work)
            dest = rem.quarantine_job(
                base, "job-1", work, "not-a-dict")
            self.assertTrue(dest)
            with mock.patch.object(shutil, "move",
                                   side_effect=OSError("busy")):
                self.assertIsNone(
                    rem.release_quarantine(base, "job-1"))

