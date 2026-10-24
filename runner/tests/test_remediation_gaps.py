"""Pin the remediation branches the main suite never reaches."""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock
from runner.oracle import remediation as rem

class _S:
    def __init__(self, *a, **k):
        self.hi = self.lo = self.WorkingSetSize = self.ullTotalPhys = 0
        self.th32ProcessID, self.th32ParentProcessID = 7, 1

class _CT:
    Structure, c_size_t, c_ulonglong = _S, int, int
    class wintypes:
        DWORD = LONG = int
        WCHAR = type("W", (), {"__mul__": lambda s, n: str})()
    sizeof, byref = staticmethod(lambda o: 8), staticmethod(lambda o: o)
    def __init__(self, ctl):
        self.ctl = ctl
    def __getattr__(self, name):
        ctl = self.ctl
        def fn(*a, **k):
            if name == "WinDLL":
                if a and a[0] == "psapi" and ctl.get("psapi_fail"):
                    raise OSError("psapi")
                return self
            if name == "CreateToolhelp32Snapshot":
                return ctl["snap"]
            if name == "Process32FirstW":
                a[1].th32ProcessID, a[1].th32ParentProcessID = 7, 1
                return ctl["first"]
            if name == "Process32NextW":
                return 0
            if name == "OpenProcess":
                return ctl["handle"]
            if name == "GetProcessTimes":
                a[3].lo, a[4].lo = 10 ** 7, 2 * 10 ** 7
                return ctl["times"]
            if name == "GetProcessMemoryInfo":
                a[1].WorkingSetSize = 999
                return ctl["mem"]
            if name == "GlobalMemoryStatusEx":
                a[0].ullTotalPhys = 4096
                return ctl["gmem"]
            return 1
        return fn

def _mon(work, **kw):
    st = kw.pop("st", rem.settings({}))
    kw.setdefault("sampler", lambda _p: {1: (0.0, None)})
    kw.setdefault("kill_fn", lambda _e: None)
    return rem.JobMonitor(st, kw.pop("job", "j"), 1, work, **kw)

STAT = "9 (na me) " + " ".join("S 4 0 0 0 0 0 0 0 0 0 5 7".split())

class Gaps(unittest.TestCase):
    def test_scalars_orders_and_classify(self):
        st = rem.settings({"remediation_storm_ceiling": True,
                           "remediation_sample_sec": True})
        self.assertEqual(st["storm_ceiling"], rem.DEFAULT_STORM_CEILING)
        self.assertEqual(st["sample_sec"], rem.DEFAULT_SAMPLE_SEC)
        for bad in (float("nan"), float("inf"), float("-inf"), 0.01):
            self.assertEqual(rem.settings(
                {"remediation_sample_sec": bad})["sample_sec"], 1.0)
        self.assertEqual(rem.received_digest(None), rem.received_digest(5))
        self.assertNotEqual(rem.received_digest(None),
                            rem.received_digest({"a": 1}))
        self.assertEqual(rem.divergence_text(None), "")
        self.assertTrue(rem.parse_oracle_order("\n\nKILL: now"))
        self.assertFalse(rem.parse_oracle_order("\n \n"))
        self.assertIsNone(rem._parse_iso(None))
        self.assertIsNone(rem._parse_iso(""))
        self.assertIsNone(rem._parse_iso("1999-13-01T00:00:00Z"))
        trip, divs = rem.classify_findings([
            (None, "x"), ("", "y"), ("/a", rem.CREDENTIAL_REASON),
            ("/a", rem.CREDENTIAL_REASON),
            ("/b", rem.CREDENTIAL_REASON)], [], [])
        self.assertIn("/a", trip["detail"])
        self.assertNotIn("/b", trip["detail"])
        self.assertEqual(divs, [])
        sig = rem.TreeSignals(None)
        sig.feed({1: (0.0, None)}, 5.0)
        self.assertEqual(sig.feed({1: (9.0, None)}, 5.0), [])
        self.assertFalse(rem.alert_names_job("nope", "j", "/p", [1]))
        class B:
            pass
        self.assertTrue(rem.alert_names_job(
            {"title": "see /only/path"}, "", "/only/path", []))
        self.assertTrue(rem.alert_names_job(
            {"detail": B(), "title": "pid 9"}, "zz", "/absent", [9]))

    def test_proc_memory_and_windows(self):
        if os.name == "nt":
            self.skipTest("proc parsing is POSIX")
        real = open
        def opn(path, mode="r", *a, **k):
            path = str(path)
            if path in ("/proc/5/stat", "/proc/8/stat"):
                return io.StringIO(STAT)
            if path in ("/proc/6/stat", "/proc/5/statm"):
                raise OSError(path)
            if path == "/proc/7/stat":
                return io.StringIO("garbage")
            if path == "/proc/8/statm":
                return io.StringIO("nope")
            return real(path, mode, *a, **k)
        def listing(path):
            if path == "/proc":
                return ["zz", "5", "6", "7"]
            raise OSError(path)
        with mock.patch("builtins.open", opn), \
                mock.patch.object(os, "listdir", listing):
            self.assertEqual(rem._proc_parents(), {5: 4})
            self.assertEqual(rem._proc_usage(5, 100.0, 4096), (0.12, None))
            self.assertIsNone(rem._proc_usage(6, 100.0, 4096))
            self.assertIsNone(rem._proc_usage(8, 100.0, 4096)[1])
        with mock.patch.object(os, "listdir", side_effect=OSError):
            self.assertEqual(rem._proc_parents(), {})
        with mock.patch.object(os, "sysconf", side_effect=ValueError("no")):
            self.assertEqual(rem._clk_tck(), 100.0)
            self.assertEqual(rem._page_size(), 4096)
        with mock.patch.object(rem, "tree_pids", return_value=[]):
            self.assertEqual(rem.sample_tree_posix(42), {42: (0.0, None)})
        def mem_open(path, mode="r", *a, **k):
            if str(path) == "/proc/meminfo":
                if mem_open.mode == "raise":
                    raise OSError("mem")
                if mem_open.mode == "bad":
                    return io.StringIO("SwapFree: 1\nMemTotal: xyz\n")
                return io.StringIO("SwapFree: 1\n")
            return real(path, mode, *a, **k)
        mem_open.mode = "raise"
        with mock.patch("builtins.open", mem_open):
            self.assertGreater(rem.total_memory_bytes(), 0)
        mem_open.mode = "bad"
        with mock.patch("builtins.open", mem_open), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.object(rem, "_win_total_memory", return_value=77):
            self.assertEqual(rem.total_memory_bytes(), 77)
        with mock.patch("builtins.open", mem_open), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.object(rem, "_win_total_memory",
                                  side_effect=RuntimeError("w")):
            self.assertIsNone(rem.total_memory_bytes())
        mem_open.mode = "none"
        with mock.patch("builtins.open", mem_open):
            # No MemTotal line: scan ends, sysconf still answers.
            expect = int(os.sysconf("SC_PHYS_PAGES")) * rem._page_size()
            self.assertEqual(rem.total_memory_bytes(), expect)
        with mock.patch("builtins.open", mem_open), \
                mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(os, "name", "posix"), \
                mock.patch.object(os, "sysconf", return_value=3), \
                mock.patch.object(rem, "_page_size", return_value=100):
            self.assertEqual(rem.total_memory_bytes(), 300)
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(os, "name", "posix"), \
                mock.patch.object(os, "sysconf", side_effect=OSError("s")):
            self.assertIsNone(rem.total_memory_bytes())
        with mock.patch.object(os.path, "isdir", return_value=False), \
                mock.patch.object(os, "name", "posix"):
            self.assertEqual(rem.sample_tree(3), {3: (0.0, None)})
        ctl = {"snap": -1, "first": False, "handle": 0, "times": False,
               "mem": False, "gmem": False, "psapi_fail": True}
        with mock.patch.dict(sys.modules, {"ctypes": _CT(ctl)}):
            self.assertEqual(rem._win_parents(), {})
            ctl["snap"] = 0
            self.assertEqual(rem._win_parents(), {})
            ctl.update(snap=5, first=False)
            self.assertEqual(rem._win_parents(), {})
            ctl["first"] = True
            self.assertEqual(rem._win_parents(), {7: 1})
            self.assertIsNone(rem._win_usage(7))
            ctl.update(psapi_fail=False, handle=1, times=False, mem=False)
            self.assertIsNone(rem._win_usage(7))
            ctl["mem"] = True
            self.assertEqual(rem._win_usage(7), (0.0, 999))
            ctl["times"] = True
            self.assertEqual(rem._win_usage(7), (3.0, 999))
            self.assertIsNone(rem._win_total_memory())
            ctl["gmem"] = True
            self.assertEqual(rem._win_total_memory(), 4096)
            got = rem.sample_tree_windows(7)
            self.assertEqual(got[7], (3.0, 999))
            ctl["handle"] = 0
            self.assertEqual(rem.sample_tree_windows(7)[7], (0.0, None))
            with mock.patch.object(rem, "tree_pids", return_value=[]):
                self.assertEqual(rem.sample_tree_windows(99),
                                 {99: (0.0, None)})
            with mock.patch.object(os, "name", "nt"):
                ctl["handle"] = 1
                self.assertEqual(rem.sample_tree(7)[7][1], 999)

    def test_windows_sampler_does_not_adopt_a_reused_pid_tree(self):
        # 11 started before the job and still names the job's pid
        # as its parent. 12 is 11's child. Neither belongs to the
        # job. 15 cannot be opened, so it counts, but its child
        # 16 is not walked. 13 and 14 started after the job.
        parents = {10: 1, 11: 10, 12: 11, 13: 10, 14: 13, 15: 10, 16: 15}
        born = {10: 100, 11: 50, 12: 40, 13: 200, 14: 210, 15: None, 16: 300}
        with mock.patch.object(rem, "_win_parents", return_value=parents), \
                mock.patch.object(rem, "_win_created_ticks",
                                  side_effect=lambda pid: born.get(pid)), \
                mock.patch.object(rem, "_win_usage",
                                  return_value=(0.0, 1)):
            sample = rem.sample_tree_windows(10)
        self.assertEqual(set(sample), {10, 13, 14, 15})

    def test_jsonl_av_and_quarantine(self):
        if os.name == "nt":
            self.skipTest("AV path finding differs on Windows")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "log")
            blob = (b"Z" * 200 + b"\n\nnot-json\n[]\n"
                    + b'{"at":"nope"}\n'
                    + b'{"at":"1999-01-01T00:00:00Z"}\n'
                    + b'{"ts":"2099-01-01T00:00:00Z","ok":1}\n')
            with open(path, "wb") as fh:
                fh.write(blob)
            recs = rem._read_jsonl_window(path, time.time(), cap_bytes=120)
            self.assertEqual(recs, [{"ts": "2099-01-01T00:00:00Z", "ok": 1}])
            self.assertEqual(rem.find_mpcmdrun(
                environ={}, which=lambda _n: "C:/mp.exe"), "C:/mp.exe")
            self.assertIsNone(rem.find_mpcmdrun(
                environ={}, which=lambda _n: (_ for _ in ()).throw(RuntimeError())))
            self.assertIsNone(rem.find_mpcmdrun(
                environ={"ProgramFiles": "C:/PF", "ProgramData": "C:/PD"},
                which=lambda _n: None, exists=lambda _p: False,
                listdir=lambda _p: (_ for _ in ()).throw(OSError())))
            found = rem.find_mpcmdrun(
                environ={"ProgramData": "C:/PD"}, which=lambda _n: None,
                exists=lambda p: p.endswith("4.1/MpCmdRun.exe"),
                listdir=lambda _p: ["4.1", "4.2"])
            self.assertTrue(found.endswith("4.1/MpCmdRun.exe"))
            with mock.patch.object(rem, "find_mpcmdrun", return_value=None):
                verdict, detail = rem.av_referral(
                    ["C:/a"], os_name="nt", which=lambda _n: None)
            self.assertEqual(verdict, "unavailable")
            self.assertIn("Defender", detail)
            def boom(*_a, **_k):
                raise TimeoutError("slow")
            verdict, detail = rem.av_referral(
                ["/tmp/evil.bin", "/tmp/ok.bin"], run=boom,
                which=lambda _n: "/usr/bin/clamdscan", os_name="posix")
            self.assertEqual(verdict, "unavailable")
            self.assertIn("evil.bin", detail)
            self.assertIn("ok.bin", detail)
            self.assertIn("scan failed", detail)
            root = rem.quarantine_root(d)
            self.assertEqual(rem.enforce_quarantine_bounds(
                d, {"quarantine_max_jobs": 50, "quarantine_max_bytes": 0}), [])
            self.assertIsNone(rem.load_marker(d, "../x"))
            self.assertIsNone(rem.release_quarantine(d, ".."))
            self.assertIsNone(rem.fix_marker_digest(d, "missing", "d"))
            os.makedirs(root)
            open(os.path.join(root, "nota-dir"), "w").close()
            for name, payload in (("a", b"abcd"), ("b", b"ef")):
                wd = os.path.join(root, name, "work")
                os.makedirs(wd)
                open(os.path.join(wd, "f"), "wb").write(payload)
            os.symlink("missing", os.path.join(root, "a", "work", "gone"))
            self.assertEqual(rem._dir_bytes(os.path.join(root, "a")), 4)
            real_mt = os.path.getmtime
            arch = os.path.join(d, rem.QUARANTINE_ARCHIVE_DIR)
            os.makedirs(os.path.join(arch, "a-STAMP"))
            moves = {"n": 0}
            real_move = rem.shutil.move
            def move(src, dst):
                moves["n"] += 1
                if moves["n"] > 1:
                    raise rem.shutil.Error("stop")
                return real_move(src, dst)
            def gmt(p):
                if os.path.basename(p) == "a":
                    raise OSError("mt")
                return real_mt(p)
            with mock.patch.object(os.path, "getmtime", gmt), \
                    mock.patch.object(rem.time, "strftime", lambda *a, **k: "STAMP"), \
                    mock.patch.object(rem.shutil, "move", move):
                archived = rem.enforce_quarantine_bounds(
                    d, {"quarantine_max_jobs": 50, "quarantine_max_bytes": 0})
            self.assertEqual(archived, ["a"])
            self.assertTrue(os.path.isdir(os.path.join(arch, "a-STAMP-2")))
            self.assertTrue(os.path.isdir(os.path.join(root, "b")))
            work = os.path.join(d, "src", "job")
            os.makedirs(os.path.join(work, "sub"))
            open(os.path.join(work, "sub", "out.txt"), "w").write("zz")
            os.makedirs(os.path.join(root, "job"))
            with mock.patch.object(os.path, "relpath", side_effect=ValueError):
                dest = rem.quarantine_job(
                    d, "job", work, {"received_digest": "old"})
            self.assertTrue(dest.endswith(os.path.join("quarantine", "job-2")))
            self.assertEqual(rem.load_marker(d, "job-2")["files"], ["out.txt"])
            rem.fix_marker_digest(d, "job-2", "old")
            self.assertEqual(rem.load_marker(d, "job-2")["received_digest"], "old")
            rem.fix_marker_digest(d, "job-2", "new")
            self.assertEqual(rem.load_marker(d, "job-2")["received_digest"], "new")
            with mock.patch.object(rem, "load_marker",
                                   return_value={"received_digest": "new"}):
                rem.fix_marker_digest(d, "../evil", "other")
            self.assertEqual(rem.load_marker(d, "job-2")["received_digest"], "new")
            real_open = open
            def ro(path, mode="r", *a, **k):
                if "w" in str(mode):
                    raise OSError("ro")
                return real_open(path, mode, *a, **k)
            with mock.patch("builtins.open", ro):
                rem.fix_marker_digest(d, "job-2", "newer")
            self.assertEqual(rem.load_marker(d, "job-2")["received_digest"], "new")
            w2 = os.path.join(d, "src", "jobb")
            os.makedirs(w2)
            with mock.patch.object(rem.shutil, "move", side_effect=OSError("mv")):
                self.assertIsNone(rem.quarantine_job(d, "jobb", w2, {}))
            self.assertTrue(os.path.isdir(w2))
            w3 = os.path.join(d, "src", "jobc")
            os.makedirs(w3)
            open(os.path.join(w3, "z"), "w").write("q")
            def wo(path, mode="r", *a, **k):
                if str(path).endswith("remediation.json") and "w" in str(mode):
                    raise OSError("ro")
                return real_open(path, mode, *a, **k)
            with mock.patch("builtins.open", wo):
                dest = rem.quarantine_job(d, "jobc", w3, {"authority": "t"})
            self.assertTrue(os.path.isdir(os.path.join(dest, "work")))
            self.assertIsNone(rem.load_marker(d, "jobc"))
            rel = os.path.join(root, "rel")
            os.makedirs(os.path.join(rel, "work"))
            open(os.path.join(rel, "work", "f.txt"), "w").write("hi")
            open(os.path.join(rel, "extra"), "w").write("x")
            def mo(path, mode="r", *a, **k):
                if str(path).endswith("remediation-marker.json"):
                    raise OSError("ro")
                return real_open(path, mode, *a, **k)
            with mock.patch("builtins.open", mo):
                info = rem.release_quarantine(d, "rel")
            self.assertTrue(info["restored_to"].endswith(os.path.join("work", "rel")))
            self.assertTrue(os.path.exists(os.path.join(info["restored_to"], "f.txt")))
            self.assertFalse(os.path.exists(os.path.join(
                info["restored_to"], "remediation-marker.json")))
            self.assertTrue(os.path.isdir(rel))
            rel2 = os.path.join(root, "rel2")
            os.makedirs(os.path.join(rel2, "work"))
            with mock.patch.object(rem.shutil, "move", side_effect=OSError("mv")):
                self.assertIsNone(rem.release_quarantine(d, "rel2"))
            self.assertTrue(os.path.isdir(os.path.join(rel2, "work")))

    def test_monitor_edges(self):
        with tempfile.TemporaryDirectory() as work:
            mon = _mon(work, st=rem.settings({"remediation_sample_sec": 30}))
            mon.stop()
            self.assertIsNone(mon._thread)
            mon.start()
            thread = mon._thread
            mon.start()
            self.assertIs(mon._thread, thread)
            mon.stop()
            self.assertIsNone(mon._thread)
            for i in range(9):
                mon._error("e%d" % i)
            self.assertEqual(mon.outcome["errors"], ["e%d" % i for i in range(8)])
            def blind(_p):
                raise RuntimeError("blind")
            mon = _mon(work, sampler=blind)
            mon.sample_once()
            self.assertTrue(any("blind" in e for e in mon.outcome["errors"]))
            self.assertIsNone(mon.outcome["acted"])
            runner = _mon(work)
            def bad(_p):
                runner._stop.set()
                return {1: "xy"}
            runner._sampler = bad
            runner._run()
            self.assertTrue(runner.outcome["errors"])
            self.assertIsNone(runner.outcome["acted"])
            clk = {"t": 0.0}
            cpus = iter([0.0, 1.0, 2.0, 3.0])
            sat = _mon(work, sampler=lambda _p: {1: (next(cpus), None)})
            with mock.patch.object(rem.time, "monotonic", lambda: clk["t"]):
                for i in range(4):
                    clk["t"] = float(i)
                    sat.sample_once()
            self.assertEqual([d["kind"] for d in sat.outcome["divergences"]],
                             ["tree_saturation"])
            self.assertIsNone(sat.outcome["acted"])
            with mock.patch.object(os, "walk", side_effect=OSError("walk")):
                self.assertEqual(sat._scan_workdir(), 0)
            def findings(text):
                if "UNIQUEBIG" in text:
                    raise AssertionError("big file was scanned")
                if text == "boom":
                    raise RuntimeError("findings broke")
                if text.startswith("A"):
                    return [("/cred/A", rem.CREDENTIAL_REASON)]
                if text.startswith("B"):
                    return [("/cred/B", rem.CREDENTIAL_REASON)]
                return []
            for name, data in (("a.txt", b"A"), ("b.txt", b"B"),
                               ("boom.txt", b"boom"), ("bin.dat", b"\xff\xfe")):
                open(os.path.join(work, name), "wb").write(data)
            open(os.path.join(work, "big.dat"), "wb").write(
                b"UNIQUEBIG" + b"x" * rem.ARTIFACT_READ_CAP)
            os.symlink("missing", os.path.join(work, "gone"))
            off = _mon(work, st=rem.settings({"remediation_mode": "off"}),
                       findings_fn=findings)
            off.sample_once()
            self.assertEqual(off.outcome["page"]["detail"].split()[3], "/cred/A")
            self.assertEqual(off.outcome["suspects"], ["a.txt", "b.txt"])
            self.assertTrue(any("findings broke" in e for e in off.outcome["errors"]))
            self.assertIsNone(off.outcome["acted"])
            open(os.path.join(work, "a.txt"), "a").write("more")
            off.sample_once()
            self.assertEqual(off.outcome["suspects"], ["a.txt", "b.txt"])
            self.assertIn("/cred/A", off.outcome["page"]["detail"])
            os.makedirs(os.path.join(work, "sub"))
            nested = os.path.join(work, "sub", "c.txt")
            open(nested, "w").write("A-nested")
            with mock.patch.object(os.path, "relpath", side_effect=ValueError):
                off._scan_file(nested)
            self.assertIn("c.txt", off.outcome["suspects"])
            self.assertNotIn("sub/c.txt", off.outcome["suspects"])
            sealed = _mon(work, st=rem.settings({"remediation_mode": "off"}),
                          findings_fn=findings)
            sealed.final_scan()
            self.assertIn("/cred/A", sealed.outcome["page"]["detail"])
            self.assertIsNone(sealed.outcome["acted"])
            self.assertGreater(len(sealed.outcome["divergences"]), 1)
            killed = {}
            def kill(extra):
                killed["extra"] = list(extra)
            n = {"i": 0}
            def late(_p):
                n["i"] += 1
                if n["i"] > 1:
                    raise RuntimeError("late")
                return {1: (0.0, None), 2: (0.0, None)}
            def both(_t):
                return [("/c", rem.CREDENTIAL_REASON), ("/e/x", "config")]
            act = _mon(work, sampler=late, kill_fn=kill, findings_fn=both)
            act.sample_once()
            self.assertEqual(killed["extra"], [])
            self.assertEqual(act.outcome["acted"]["authority"], "tripwire")
            self.assertEqual([d["kind"] for d in act.outcome["divergences"]],
                             ["credential_artifact", "undeclared_path_artifact"])
            def deny(_e):
                raise RuntimeError("denied")
            nok = _mon(work, kill_fn=deny, findings_fn=both)
            nok.sample_once()
            self.assertTrue(any("denied" in e for e in nok.outcome["errors"]))
            self.assertEqual(nok.outcome["acted"]["authority"], "tripwire")
            bare = _mon(work, kill_fn=None, findings_fn=both)
            bare.sample_once()
            self.assertEqual(bare.outcome["errors"], [])
            self.assertIsNotNone(bare.outcome["acted"])
            base = os.path.join(work, "base")
            os.makedirs(base)
            def alerts(_since):
                return [{"title": "nothing"}, {"title": "pid 1 spinning"}]
            win = _mon(base, base_dir=base, alerts_fn=alerts, job="j")
            # Stamp from the monitor's own start. The resource window
            # only reaches one second before that. Writing the logs
            # first can take longer than that on Windows, so the
            # event falls out while confinement (five seconds of
            # slack) still matches. That failed build-windows on the
            # v3.11.17 main push; the tag of the same commit was
            # fast enough to pass.
            now = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(win._started_wall))
            with open(os.path.join(base, "security-audit.jsonl"), "w") as fh:
                for rec in (
                    {"ts": now, "feature": "other", "job_id": "j",
                     "decision": "denied"},
                    {"ts": now, "feature": "confinement",
                     "job_id": "nope", "decision": "denied"},
                    {"ts": now, "feature": "confinement",
                     "job_id": "j", "decision": "sandboxed"},
                    {"ts": now, "feature": "confinement",
                     "job_id": "j", "decision": "denied"},
                ):
                    fh.write(json.dumps(rec) + "\n")
            with open(os.path.join(base, "security-events.jsonl"), "w") as fh:
                fh.write(json.dumps({"at": now, "type": "resource_pressure"}) + "\n")
            win.sample_once()
            kinds = [d["kind"] for d in win.outcome["divergences"]]
            self.assertEqual(win.outcome["acted"]["divergence"]["kind"],
                             "confinement_escape")
            self.assertIn("resource_event", kinds)
            self.assertIn("sense_alert", kinds)
            self.assertIsNone(win.outcome["page"])
            def _alerts_fail(_since):
                raise RuntimeError("alerts")
            errm = _mon(base, base_dir=base, job="j",
                        alerts_fn=_alerts_fail)
            with mock.patch.object(rem, "confinement_events_in_window",
                                   side_effect=RuntimeError("cage")), \
                    mock.patch.object(rem, "resource_events_in_window",
                                      side_effect=RuntimeError("res")):
                errm.sample_once()
            text = " ".join(errm.outcome["errors"])
            self.assertIn("cage", text)
            self.assertIn("res", text)
            self.assertIn("alerts", text)

    def test_paths_owned_by_the_sorted_earlier_suite(self):
        # These are reached by runner/tests/test_remediation.py, which sorts
        # after test_fuzz_guided and therefore runs with no tracer.
        self.assertEqual(rem.mode_of(None), "deterministic")
        self.assertEqual(rem.mode_of({}), "deterministic")
        self.assertEqual(sorted(rem.tree_pids(1, {1: 2, 2: 1})), [1, 2])
        sig = rem.TreeSignals(total_mem=1000)
        self.assertEqual(sig.feed({1: (0.0, 600)}, 0.0), [])
        mem = sig.feed({1: (0.0, 600)}, 1.0)
        self.assertEqual([d["kind"] for d in mem], ["tree_memory"])
        self.assertFalse(mem[0]["tripwire"])
        quiet = rem.TreeSignals(total_mem=1000)
        quiet.feed({1: (0.0, 100)}, 0.0)
        self.assertEqual(quiet.feed({1: (0.0, 100)}, 1.0), [])
        disk = rem.TreeSignals(None)
        disk.feed({1: (0.0, None)}, 0.0, workdir_bytes=10)
        filled = disk.feed(
            {1: (0.0, None)}, 1.0,
            workdir_bytes=10 + rem.DISK_FILL_BYTES)
        self.assertEqual([d["kind"] for d in filled], ["disk_fill"])
        self.assertFalse(filled[0]["tripwire"])
        trip, divs = rem.classify_findings(
            [("/cred", rem.CREDENTIAL_REASON)], ["/cred"], [])
        self.assertIsNone(trip)
        self.assertEqual(divs, [])
        self.assertFalse(rem.parse_oracle_order(None))
        self.assertEqual(rem.ask_oracle_order(None, "ctx"),
                         ("abstain", "no inference configured"))
        self.assertEqual(
            rem.ask_oracle_order(lambda _q, _c: "  ", "ctx")[0],
            "abstain")
        self.assertEqual(rem.mpcmdrun_verdict(0), "clean")
        self.assertEqual(rem.mpcmdrun_verdict(2), "confirmed")
        self.assertIsNone(rem.mpcmdrun_verdict(1))
        self.assertEqual(rem.clamdscan_verdict(0), "clean")
        self.assertEqual(rem.clamdscan_verdict(1), "confirmed")
        self.assertIsNone(rem.clamdscan_verdict(2))
        found = rem.find_mpcmdrun(
            environ={"ProgramFiles": "C:/PF"},
            which=lambda _n: None,
            exists=lambda p: p.endswith("MpCmdRun.exe"))
        self.assertIn("Windows Defender", found)
        class Proc:
            def __init__(self, code):
                self.returncode = code
        codes = iter([5, 0])
        def run_mixed(_argv, **_k):
            return Proc(next(codes))
        verdict, detail = rem.av_referral(
            ["C:/a.bin", "C:/b.bin"], run=run_mixed, os_name="nt",
            mpcmdrun_path="C:/MpCmdRun.exe")
        self.assertEqual(verdict, "clean")
        self.assertIn("exit 5", detail)
        self.assertIn("exit 0", detail)
        self.assertIn("defender", detail)
        verdict, detail = rem.av_referral(
            ["C:/c.bin"], run=lambda *_a, **_k: Proc(9),
            os_name="nt", mpcmdrun_path="C:/MpCmdRun.exe")
        self.assertEqual(verdict, "unavailable")
        self.assertIn("exit 9", detail)
        verdict, detail = rem.av_referral(
            ["/tmp/x"], which=lambda _n: None, os_name="posix")
        self.assertEqual(verdict, "unavailable")
        self.assertIn("clamdscan", detail)
        with tempfile.TemporaryDirectory() as base:
            self.assertIsNone(rem.release_quarantine(base, "absent-1"))
            root = rem.quarantine_root(base)
            os.makedirs(root)
            open(os.path.join(root, "nota-dir"), "w").close()
            held = {"quarantine_max_jobs": 50,
                    "quarantine_max_bytes": 10 ** 18}
            self.assertEqual(
                rem.enforce_quarantine_bounds(base, held), [])
            self.assertTrue(os.path.isfile(
                os.path.join(root, "nota-dir")))
            q = os.path.join(root, "keep-1")
            os.makedirs(os.path.join(q, "work"))
            open(os.path.join(q, "work", "f.txt"), "w").write("kept")
            open(os.path.join(q, "remediation.json"), "w").write(
                '{"job_id":"keep-1","authority":"tripwire"}')
            os.makedirs(os.path.join(base, "work", "keep-1"))
            info = rem.release_quarantine(base, "keep-1")
            self.assertIn("released", info["restored_to"])
            self.assertIn("released_at", info["marker"])
            self.assertTrue(os.path.isfile(os.path.join(
                info["restored_to"], "remediation-marker.json")))
            self.assertTrue(os.path.isfile(os.path.join(
                info["restored_to"], "f.txt")))
            self.assertFalse(os.path.isdir(q))
            many = {i: (0.0, None) for i in range(4)}
            storm = os.path.join(base, "storm")
            os.makedirs(storm)
            open(os.path.join(storm, "note.txt"), "w").write("n")
            mon = _mon(
                storm,
                st=rem.settings({"remediation_mode": "off",
                                 "remediation_storm_ceiling": 1}),
                sampler=lambda _p: many,
                findings_fn=lambda _t: [("/etc/x", "a config file")])
            mon.sample_once()
            self.assertEqual(mon.outcome["page"]["kind"], "process_storm")
            self.assertIsNone(mon.outcome["acted"])
            kinds = [d["kind"] for d in mon.outcome["divergences"]]
            self.assertIn("undeclared_path_artifact", kinds)
            tripped = _mon(
                storm, findings_fn=lambda _t: [
                    ("/cred", rem.CREDENTIAL_REASON)])
            tripped.sample_once()
            suspects = list(tripped.outcome["suspects"])
            total = tripped._scan_workdir()
            self.assertEqual(tripped.outcome["suspects"], suspects)
            self.assertGreater(total, 0)
            self.assertEqual(
                tripped.outcome["acted"]["authority"], "tripwire")
            plain = os.path.join(base, "plain")
            os.makedirs(plain)
            quiet_mon = _mon(plain, base_dir=plain)
            quiet_mon.sample_once()
            quiet_mon.sample_once()
            self.assertEqual(quiet_mon.outcome["divergences"], [])
            self.assertEqual(quiet_mon.outcome["errors"], [])
        self.assertEqual(
            rem.ask_oracle_order(lambda _q, _c: "KILL: now", "c"),
            ("kill", "KILL: now"))
        spare = rem.ask_oracle_order(lambda _q, _c: "SPARE: fine", "c")
        self.assertEqual(spare, ("spare", "SPARE: fine"))
        self.assertIsNone(rem.quarantine_job(base, "../evil", plain, {}))
        self.assertIsNone(rem.quarantine_job(base, "ok-1", plain + "-no", {}))
        verdict, detail = rem.av_referral([], which=lambda _n: "/bin/x")
        self.assertEqual(verdict, "unavailable")
        self.assertIn("no suspect files", detail)
        member = rem.result_member(
            "deterministic", "tripwire",
            rem.divergence("process_storm", "9 processes"),
            "killed", "unavailable", "ab")
        self.assertEqual(member["authority"], "tripwire")
        self.assertTrue(member["divergence"].startswith("process_storm"))
        self.assertEqual(set(member), {
            "mode", "authority", "divergence", "act",
            "av_verdict", "received_digest"})
        many = {i: (0.0, None) for i in range(4)}
        seen = []
        storm = _mon(
            plain, sampler=lambda _p: many,
            st=rem.settings({"remediation_storm_ceiling": 1}),
            findings_fn=lambda _t: seen.append(_t) or [])
        storm.sample_once()
        self.assertEqual(seen, [])
        self.assertEqual(
            storm.outcome["acted"]["divergence"]["kind"], "process_storm")
        runner = _mon(
            plain, sampler=lambda _p: many,
            st=rem.settings({"remediation_storm_ceiling": 1,
                             "remediation_sample_sec": 30}))
        runner._run()
        self.assertEqual(runner.outcome["acted"]["authority"], "tripwire")
        asked = {}

        def ask_kill(_q, ctx):
            asked["kill"] = ctx
            return "KILL: stop"

        oracle = _mon(
            plain, base_dir=plain, job="j",
            st=rem.settings({"remediation_mode": "oracle"}),
            alerts_fn=lambda _s: [{"title": "job j is odd"}],
            ask_fn=ask_kill, envelope_note="paths: /work")
        oracle.sample_once()
        self.assertEqual(oracle.outcome["acted"]["authority"], "oracle")
        self.assertEqual(oracle.outcome["oracle"][0]["decision"], "kill")
        self.assertEqual(oracle.outcome["oracle"][0]["reason"], "KILL: stop")
        self.assertIn("paths: /work", asked["kill"])

        def ask_spare(_q, ctx):
            asked["spare"] = ctx
            return "SPARE: benign"

        spared = _mon(
            plain, base_dir=plain, job="j",
            st=rem.settings({"remediation_mode": "oracle"}),
            alerts_fn=lambda _s: [{"title": "job j is odd"}],
            ask_fn=ask_spare)
        spared.sample_once()
        self.assertIsNone(spared.outcome["acted"])
        self.assertEqual(spared.outcome["oracle"][0]["decision"], "spare")
        self.assertEqual(
            spared.outcome["oracle"][0]["reason"], "SPARE: benign")
        self.assertIn("no declared paths", asked["spare"])


def _prime_coverage():
    """Exercise the gaps while the coverage tracer is still up.

    Discover imports every test module before running any test.
    test_fuzz_guided then calls sys.settrace(None), so this file's
    tests -- which sort later -- would not be traced. Import-time
    execution is the window the tracer still records.
    """
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Gaps)
    with open(os.devnull, "w", encoding="utf-8") as sink:
        result = unittest.TextTestResult(
            sink, descriptions=False, verbosity=0)
        suite.run(result)
    if not result.wasSuccessful():
        bad = result.failures + result.errors
        raise AssertionError("gap prime failed: %s" % (bad,))


_prime_coverage()

