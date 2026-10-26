#!/usr/bin/env python3
"""Remediation tests (docs/design/remediation-design.md).

The trigger is a divergence from the job's intent envelope;
the tripwire list is closed; the Oracle's layer abstains on
anything but an affirmative order; the acts are kill,
quarantine (a move, never a delete), antivirus referral, and
the DRI page. Sender surface: none -- pinned behaviorally.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner.oracle import remediation as rem
from runner.oracle import opinion as op
from runner import runner
from runner.oracle import dri

POSIX = os.name != "nt"
CRED = "/home/user/.aws/credentials"
CRED_FINDING = (CRED, rem.CREDENTIAL_REASON)


def _iso(ts=None):
    ts = time.time() if ts is None else ts
    return datetime.fromtimestamp(ts, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _settings(**over):
    cfg = {"remediation_mode": over.pop("mode", "deterministic")}
    for key, val in over.items():
        cfg["remediation_" + key] = val
    return rem.settings(cfg)


class SettingsTest(unittest.TestCase):
    def test_default_mode_is_deterministic(self):
        self.assertEqual(rem.mode_of({}), "deterministic")
        self.assertEqual(rem.mode_of({"remediation_mode": "bogus"}),
                         "deterministic")
        self.assertEqual(rem.mode_of({"remediation_mode": "off"}), "off")
        self.assertEqual(rem.mode_of({"remediation_mode": "oracle"}),
                         "oracle")
        self.assertEqual(rem.mode_of(None), "deterministic")

    def test_settings_defaults_and_overrides(self):
        st = rem.settings({})
        self.assertEqual(st["storm_ceiling"], 64)
        self.assertEqual(st["sample_sec"], 1.0)
        self.assertEqual(st["oracle_timeout_sec"], 20)
        st = rem.settings({"remediation_storm_ceiling": 5,
                           "remediation_sample_sec": 0.1,
                           "remediation_storm_ceiling_x": 1})
        self.assertEqual(st["storm_ceiling"], 5)
        self.assertEqual(st["sample_sec"], 0.1)
        st = rem.settings({"remediation_storm_ceiling": -3,
                           "remediation_sample_sec": "fast"})
        self.assertEqual(st["storm_ceiling"], 64)
        self.assertEqual(st["sample_sec"], 1.0)


class CliOverrideTest(unittest.TestCase):
    def _args(self, **over):
        ns = Namespace()
        for dest, _key in runner._CLI_OVERRIDES:
            setattr(ns, dest, None)
        for dest, val in over.items():
            setattr(ns, dest, val)
        return ns

    def test_remediation_mode_lands_and_pins(self):
        cfg = {}
        applied = runner.apply_cli_overrides(
            cfg, self._args(remediation_mode="oracle"))
        self.assertEqual(cfg["remediation_mode"], "oracle")
        self.assertIn("remediation_mode", applied)

    def test_oracle_opinion_string_no_longer_raises(self):
        # Regression: --oracle-opinion is a string flag that the
        # counts check treated as a number and rejected at
        # startup. String mode dests are not counts.
        cfg = {}
        runner.apply_cli_overrides(
            cfg, self._args(oracle_opinion="advise"))
        self.assertEqual(cfg["oracle_opinion_mode"], "advise")

    def test_help_lists_the_new_flags(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        proc = subprocess.run(
            [sys.executable, os.path.join(root, "runner", "runner.py"),
             "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--remediation-mode", proc.stdout)
        self.assertIn("--remediation-release", proc.stdout)


class DigestTest(unittest.TestCase):
    def test_matches_the_opinion_definition(self):
        jobs = [
            {"job_id": "a", "kind": "exec", "script": "echo hi"},
            {"job_id": "b", "kind": "exec", "script": "echo ü",
             "sig": "deadbeef", "args": ["--x", "1"]},
            {"job_id": "c", "kind": "ping", "sig": "00"},
            {},
        ]
        for job in jobs:
            self.assertEqual(rem.received_digest(job),
                             op.received_digest(job), job)

    def test_sig_is_excluded_and_content_counts(self):
        a = {"job_id": "x", "script": "echo 1", "sig": "aa"}
        b = {"job_id": "x", "script": "echo 1", "sig": "bb"}
        c = {"job_id": "x", "script": "echo 2", "sig": "aa"}
        self.assertEqual(rem.received_digest(a),
                         rem.received_digest(b))
        self.assertNotEqual(rem.received_digest(a),
                            rem.received_digest(c))


class TreeTest(unittest.TestCase):
    def test_tree_pids_walks_descendants(self):
        parents = {1: 0, 2: 1, 3: 1, 4: 2, 5: 4, 9: 0}
        self.assertEqual(sorted(rem.tree_pids(1, parents)),
                         [1, 2, 3, 4, 5])
        self.assertEqual(rem.tree_pids(9, parents), [9])
        self.assertEqual(rem.tree_pids(7, parents), [7])

    def test_tree_pids_survives_a_cycle(self):
        self.assertEqual(sorted(rem.tree_pids(1, {1: 2, 2: 1})),
                         [1, 2])

    def test_posix_sample_includes_self(self):
        if not POSIX:
            self.skipTest("posix sampler")
        sample = rem.sample_tree_posix(os.getpid())
        self.assertIn(os.getpid(), sample)
        cpu, _rss = sample[os.getpid()]
        self.assertGreaterEqual(cpu, 0.0)


class TreeSignalsTest(unittest.TestCase):
    def test_saturation_needs_a_sustained_run(self):
        sig = rem.TreeSignals(total_mem=None)
        sample = {1: (0.0, None)}
        self.assertEqual(sig.feed(sample, 0.0), [])
        sample = {1: (1.0, None)}
        self.assertEqual(sig.feed(sample, 1.0), [])
        self.assertEqual(sig.feed({1: (2.0, None)}, 2.0), [])
        fired = sig.feed({1: (3.0, None)}, 3.0)
        self.assertEqual([d["kind"] for d in fired],
                         ["tree_saturation"])
        self.assertEqual(sig.feed({1: (4.0, None)}, 4.0), [])

    def test_a_quiet_sample_resets_the_run(self):
        sig = rem.TreeSignals(total_mem=None)
        sig.feed({1: (0.0, None)}, 0.0)
        sig.feed({1: (1.0, None)}, 1.0)
        sig.feed({1: (1.1, None)}, 2.0)   # rate 0.1: run resets
        sig.feed({1: (2.1, None)}, 3.0)
        sig.feed({1: (3.1, None)}, 4.0)
        self.assertEqual(sig.feed({1: (4.1, None)}, 5.0)[0]["kind"],
                         "tree_saturation")

    def test_memory_share_needs_two_samples(self):
        sig = rem.TreeSignals(total_mem=1000)
        self.assertEqual(sig.feed({1: (0.0, 600)}, 0.0), [])
        fired = sig.feed({1: (0.0, 600)}, 1.0)
        self.assertEqual([d["kind"] for d in fired], ["tree_memory"])
        self.assertFalse(fired[0]["tripwire"])

    def test_disk_fill(self):
        sig = rem.TreeSignals(total_mem=None)
        sig.feed({1: (0.0, None)}, 0.0, workdir_bytes=100)
        self.assertEqual(
            sig.feed({1: (0.0, None)}, 1.0, workdir_bytes=200), [])
        fired = sig.feed({1: (0.0, None)}, 2.0,
                         workdir_bytes=100 + rem.DISK_FILL_BYTES)
        self.assertEqual([d["kind"] for d in fired], ["disk_fill"])


class ClassifyFindingsTest(unittest.TestCase):
    def test_undeclared_credential_is_the_tripwire(self):
        trip, divs = rem.classify_findings([CRED_FINDING], [], [])
        self.assertIsNotNone(trip)
        self.assertEqual(trip["kind"], "credential_artifact")
        self.assertTrue(trip["tripwire"])
        self.assertEqual(divs, [])

    def test_declared_credential_is_not_a_finding(self):
        trip, divs = rem.classify_findings(
            [("~/.aws/credentials", rem.CREDENTIAL_REASON)],
            [], ["~/.aws/credentials"])
        self.assertIsNone(trip)
        self.assertEqual(
            [d["kind"] for d in divs], ["undeclared_path_artifact"])

    def test_envelope_declared_path_is_never_a_finding(self):
        trip, divs = rem.classify_findings(
            [CRED_FINDING], [CRED], [])
        self.assertIsNone(trip)
        self.assertEqual(divs, [])

    def test_other_undeclared_paths_are_divergences(self):
        trip, divs = rem.classify_findings(
            [("/etc/cron.d/x", "a system configuration file, "
              "outside the job's own workspace")], [], [])
        self.assertIsNone(trip)
        self.assertEqual([d["kind"] for d in divs],
                         ["undeclared_path_artifact"])
        self.assertFalse(divs[0]["tripwire"])

    def test_windows_shapes_normalize(self):
        trip, _divs = rem.classify_findings(
            [("C:\\Users\\u\\.aws\\credentials",
              rem.CREDENTIAL_REASON)],
            ["C:/Users/u/.aws/credentials"], [])
        self.assertIsNone(trip)


class OracleOrderTest(unittest.TestCase):
    def test_parse_requires_a_leading_kill(self):
        self.assertTrue(rem.parse_oracle_order("KILL: it is exfil"))
        self.assertTrue(rem.parse_oracle_order("kill it now"))
        self.assertFalse(rem.parse_oracle_order("SPARE: it is fine"))
        self.assertFalse(rem.parse_oracle_order("I would KILL it"))
        self.assertFalse(rem.parse_oracle_order(""))
        self.assertFalse(rem.parse_oracle_order(None))

    def test_abstention_paths(self):
        self.assertEqual(rem.ask_oracle_order(None, "ctx")[0],
                         "abstain")

        def boom(_q, _c):
            raise TimeoutError("too slow")
        self.assertEqual(rem.ask_oracle_order(boom, "ctx")[0],
                         "abstain")
        self.assertEqual(
            rem.ask_oracle_order(lambda _q, _c: "", "ctx")[0],
            "abstain")
        self.assertEqual(
            rem.ask_oracle_order(lambda _q, _c: None, "ctx")[0],
            "abstain")

    def test_kill_and_spare(self):
        self.assertEqual(
            rem.ask_oracle_order(lambda _q, _c: "KILL: bad", "c")[0],
            "kill")
        self.assertEqual(
            rem.ask_oracle_order(lambda _q, _c: "SPARE: ok", "c")[0],
            "spare")


class AvReferralTest(unittest.TestCase):
    def test_verdict_maps(self):
        self.assertEqual(rem.mpcmdrun_verdict(0), "clean")
        self.assertEqual(rem.mpcmdrun_verdict(2), "confirmed")
        self.assertIsNone(rem.mpcmdrun_verdict(1))
        self.assertEqual(rem.clamdscan_verdict(0), "clean")
        self.assertEqual(rem.clamdscan_verdict(1), "confirmed")
        self.assertIsNone(rem.clamdscan_verdict(2))

    def test_no_tool_is_unavailable_not_an_error(self):
        verdict, _detail = rem.av_referral(
            ["/tmp/x"], which=lambda _n: None, os_name="posix")
        self.assertEqual(verdict, "unavailable")
        verdict, _ = rem.av_referral([], which=lambda _n: "/bin/true")
        self.assertEqual(verdict, "unavailable")

    def test_fake_run_maps_verdicts(self):
        def run_factory(code):
            def _run(_argv, **_kw):
                return subprocess.CompletedProcess([], code)
            return _run
        verdict, _ = rem.av_referral(
            ["/tmp/x"], run=run_factory(1),
            which=lambda _n: "/usr/bin/clamdscan", os_name="posix")
        self.assertEqual(verdict, "confirmed")
        verdict, _ = rem.av_referral(
            ["/tmp/x"], run=run_factory(0),
            which=lambda _n: "/usr/bin/clamdscan", os_name="posix")
        self.assertEqual(verdict, "clean")
        verdict, _ = rem.av_referral(
            ["/tmp/x"], run=run_factory(2),
            which=lambda _n: "/usr/bin/clamdscan", os_name="posix")
        self.assertEqual(verdict, "unavailable")

    def test_defender_branch_and_search(self):
        def _run(_argv, **_kw):
            return subprocess.CompletedProcess([], 2)
        verdict, detail = rem.av_referral(
            ["C:/work/x"], run=_run, which=lambda _n: None,
            os_name="nt", mpcmdrun_path="C:/def/MpCmdRun.exe")
        self.assertEqual(verdict, "confirmed")
        self.assertIn("defender", detail)
        found = rem.find_mpcmdrun(
            environ={"ProgramFiles": "C:/Program Files"},
            which=lambda _n: None,
            exists=lambda p: p.endswith("MpCmdRun.exe"))
        self.assertTrue(found.endswith("MpCmdRun.exe"))
        plat = rem.find_mpcmdrun(
            environ={"ProgramData": "C:/ProgramData"},
            which=lambda _n: None,
            exists=lambda p: "4.18" in p,
            listdir=lambda _p: ["4.17.1", "4.18.2"])
        self.assertIn("4.18.2", plat)

    @unittest.skipIf(not POSIX, "clamdscan shim is a shell script")
    def test_real_clamdscan_shim_on_path(self):
        with tempfile.TemporaryDirectory() as d:
            shim = os.path.join(d, "clamdscan")
            with open(shim, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\nexit 1\n")
            os.chmod(shim, 0o755)
            target = os.path.join(d, "evil.bin")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("x")
            env = dict(os.environ)
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
            with mock.patch.dict(os.environ, env):
                verdict, detail = rem.av_referral([target])
            self.assertEqual(verdict, "confirmed")
            self.assertIn("clamdscan", detail)


class QuarantineTest(unittest.TestCase):
    def _stage(self, base, job_id="job-1", files=("out.txt",)):
        work = os.path.join(base, "work", job_id)
        os.makedirs(work)
        for name in files:
            with open(os.path.join(work, name), "w",
                      encoding="utf-8") as fh:
                fh.write("data " + name)
        return work

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as base:
            work = self._stage(base)
            dest = rem.quarantine_job(base, "job-1", work, {
                "mode": "deterministic", "authority": "tripwire",
                "divergence": "process_storm: 90 processes",
                "act": "killed", "received_digest": "ab" * 48})
            self.assertIsNotNone(dest)
            self.assertFalse(os.path.exists(work))
            marker = rem.load_marker(base, "job-1")
            self.assertEqual(marker["authority"], "tripwire")
            self.assertEqual(marker["files"], ["out.txt"])
            info = rem.release_quarantine(base, "job-1")
            self.assertEqual(info["restored_to"],
                             os.path.join(base, "work", "job-1"))
            self.assertTrue(os.path.exists(
                os.path.join(info["restored_to"], "out.txt")))
            self.assertTrue(os.path.exists(os.path.join(
                info["restored_to"], "remediation-marker.json")))
            self.assertIsNone(rem.load_marker(base, "job-1"))

    def test_release_never_clobbers_a_new_workdir(self):
        with tempfile.TemporaryDirectory() as base:
            work = self._stage(base)
            rem.quarantine_job(base, "job-1", work, {})
            self._stage(base)  # a retry already recreated it
            info = rem.release_quarantine(base, "job-1")
            self.assertIn("released", info["restored_to"])
            self.assertTrue(os.path.exists(
                os.path.join(info["restored_to"], "out.txt")))

    def test_bounds_archive_oldest_moves_never_deletes(self):
        st = _settings(quarantine_max_jobs=2,
                       quarantine_max_bytes=10 ** 9)
        with tempfile.TemporaryDirectory() as base:
            for i, jid in enumerate(("job-a", "job-b", "job-c")):
                work = self._stage(base, jid)
                dest = rem.quarantine_job(base, jid, work, {})
                self.assertIsNotNone(dest)
                # Age them in creation order.
                os.utime(dest, (1000 + i, 1000 + i))
            archived = rem.enforce_quarantine_bounds(base, st)
            self.assertEqual(archived, ["job-a"])
            root = rem.quarantine_root(base)
            self.assertEqual(sorted(os.listdir(root)),
                             ["job-b", "job-c"])
            archive = os.path.join(base, "quarantine-archive")
            self.assertEqual(len(os.listdir(archive)), 1)

    def test_bounds_an_unmtimeable_entry_sorts_oldest(self):
        # Queue A refill: enforce_quarantine_bounds' Windows
        # residue (coverage run 40189711740) -- the branches
        # the Windows leg cannot reach with its fixtures,
        # driven here with stubs that run on both platforms.
        # An entry whose mtime cannot be read sorts as
        # epoch 0 -- oldest -- so it is archived first,
        # never skipped or fatal.
        st = _settings(quarantine_max_jobs=1,
                       quarantine_max_bytes=10 ** 9)
        with tempfile.TemporaryDirectory() as base:
            dests = {}
            for jid in ("job-a", "job-b"):
                work = self._stage(base, jid)
                dests[jid] = rem.quarantine_job(base, jid, work, {})
                os.utime(dests[jid], (5000, 5000))
            real = os.path.getmtime

            def flaky(path, *a, **kw):
                if path == dests["job-b"]:
                    raise OSError("cannot stat")
                return real(path, *a, **kw)

            with mock.patch.object(os.path, "getmtime", flaky):
                archived = rem.enforce_quarantine_bounds(base, st)
            self.assertEqual(archived, ["job-b"])

    def test_bounds_a_taken_archive_name_takes_a_suffix(self):
        # The archive destination is name + timestamp; a
        # name already taken (two seizures archived in the
        # same second) suffixes -2, -3 rather than
        # clobbering the earlier archive. (The byte ceiling
        # does the forcing: _pos_int reads a zero job cap
        # as unset.)
        st = _settings(quarantine_max_jobs=100,
                       quarantine_max_bytes=1)
        with tempfile.TemporaryDirectory() as base:
            work = self._stage(base, "job-a")
            rem.quarantine_job(base, "job-a", work, {})
            archive = os.path.join(base, "quarantine-archive")
            os.makedirs(archive)
            for taken in ("job-a-STAMP", "job-a-STAMP-2"):
                with open(os.path.join(archive, taken), "w") as fh:
                    fh.write("earlier")
            with mock.patch.object(
                    rem.time, "strftime", lambda fmt, t: "STAMP"):
                archived = rem.enforce_quarantine_bounds(base, st)
            self.assertEqual(archived, ["job-a"])
            self.assertTrue(os.path.isdir(
                os.path.join(archive, "job-a-STAMP-3")))

    def test_bounds_a_failed_move_stops_and_keeps_the_entry(self):
        # A move that fails ends the pass: the entry stays
        # seized, nothing is reported archived, and the
        # function still does not raise.
        st = _settings(quarantine_max_jobs=100,
                       quarantine_max_bytes=1)
        with tempfile.TemporaryDirectory() as base:
            work = self._stage(base, "job-a")
            rem.quarantine_job(base, "job-a", work, {})
            with mock.patch.object(
                    rem.shutil, "move",
                    side_effect=OSError("disk gone")):
                archived = rem.enforce_quarantine_bounds(base, st)
            self.assertEqual(archived, [])
            self.assertEqual(
                sorted(os.listdir(rem.quarantine_root(base))),
                ["job-a"])

    def test_bad_job_ids_go_nowhere(self):
        with tempfile.TemporaryDirectory() as base:
            work = self._stage(base, "ok")
            self.assertIsNone(
                rem.quarantine_job(base, "../evil", work, {}))
            self.assertTrue(os.path.isdir(work))
            self.assertIsNone(rem.release_quarantine(base, ".."))


class MonitorUnitTest(unittest.TestCase):
    def _monitor(self, work, st=None, **kw):
        kw.setdefault("sampler", lambda _pid: {4242: (0.0, None)})
        kw.setdefault("kill_fn", lambda _extra: None)
        return rem.JobMonitor(st or _settings(), "job-m", 4242,
                              work, **kw)

    def test_storm_trips_and_kills(self):
        kills = []
        many = {1000 + i: (0.0, None) for i in range(10)}
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(
                work, _settings(storm_ceiling=4),
                sampler=lambda _pid: many,
                kill_fn=lambda extra: kills.append(extra))
            mon.sample_once()
            self.assertEqual(mon.outcome["acted"]["authority"],
                             "tripwire")
            self.assertEqual(mon.outcome["acted"]["divergence"]
                             ["kind"], "process_storm")
            self.assertEqual(len(kills), 1)
            self.assertEqual(len(kills[0]), 10)

    def test_credential_artifact_trips(self):
        with tempfile.TemporaryDirectory() as work:
            with open(os.path.join(work, "leak.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("payload")
            mon = self._monitor(
                work, findings_fn=lambda _t: [CRED_FINDING])
            mon.sample_once()
            self.assertEqual(mon.outcome["acted"]["divergence"]
                             ["kind"], "credential_artifact")
            self.assertEqual(mon.outcome["suspects"], ["leak.txt"])

    def test_declared_credential_does_not_trip(self):
        with tempfile.TemporaryDirectory() as work:
            with open(os.path.join(work, "note.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("payload")
            mon = self._monitor(
                work, findings_fn=lambda _t: [CRED_FINDING],
                declared_paths=[CRED])
            mon.sample_once()
            self.assertIsNone(mon.outcome["acted"])
            self.assertEqual(mon.outcome["divergences"], [])

    def test_off_mode_never_kills_only_pages(self):
        kills = []
        many = {1000 + i: (0.0, None) for i in range(10)}
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(
                work, _settings(mode="off", storm_ceiling=4),
                sampler=lambda _pid: many,
                kill_fn=lambda extra: kills.append(extra))
            mon.sample_once()
            self.assertEqual(kills, [])
            self.assertIsNone(mon.outcome["acted"])
            self.assertEqual(mon.outcome["page"]["kind"],
                             "process_storm")



class MonitorOracleTest(unittest.TestCase):
    """The Oracle layer at monitor level: a sense alert naming
    the job is a divergence; the model's word decides."""

    def _monitor(self, work, ask_fn, mode="oracle"):
        alert = {"sensor": "watcher", "severity": "high",
                 "title": "job job-m is mining",
                 "observed_at": _iso()}
        return rem.JobMonitor(
            _settings(mode=mode, sample_sec=0.05), "job-m", 4242,
            work, sampler=lambda _pid: {4242: (0.0, None)},
            kill_fn=lambda _extra: None, ask_fn=ask_fn,
            alerts_fn=lambda _since: [alert], base_dir=work)

    def test_affirmative_order_kills_as_oracle(self):
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work, lambda _q, _c: "KILL: mining")
            mon.sample_once()
            self.assertEqual(mon.outcome["acted"]["authority"],
                             "oracle")
            self.assertEqual(mon.outcome["oracle"][0]["decision"],
                             "kill")

    def test_refusal_spares_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work, lambda _q, _c: "SPARE: fine")
            mon.sample_once()
            self.assertIsNone(mon.outcome["acted"])
            self.assertEqual(mon.outcome["oracle"][0]["decision"],
                             "spare")

    def test_timeout_is_an_abstention(self):
        def slow(_q, _c):
            raise TimeoutError("model too slow")
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work, slow)
            mon.sample_once()
            self.assertIsNone(mon.outcome["acted"])
            self.assertEqual(mon.outcome["oracle"][0]["decision"],
                             "abstain")

    def test_no_inference_is_an_abstention(self):
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work, None)
            mon.sample_once()
            self.assertIsNone(mon.outcome["acted"])
            self.assertEqual(mon.outcome["oracle"][0]["decision"],
                             "abstain")

    def test_deterministic_mode_never_asks(self):
        calls = []

        def ask(_q, _c):
            calls.append(1)
            return "KILL: should never be asked"
        with tempfile.TemporaryDirectory() as work:
            mon = self._monitor(work, ask, mode="deterministic")
            mon.sample_once()
            self.assertEqual(calls, [])
            self.assertIsNone(mon.outcome["acted"])
            self.assertEqual(
                [d["kind"] for d in mon.outcome["divergences"]],
                ["sense_alert"])


class WindowEvidenceTest(unittest.TestCase):
    def test_alert_names_job_by_id_path_or_pid(self):
        self.assertTrue(rem.alert_names_job(
            {"title": "job job-9 misbehaving"}, "job-9", "/w", []))
        self.assertTrue(rem.alert_names_job(
            {"detail": "wrote to /base/work/job-9/x"}, "job-9",
            "/base/work/job-9", []))
        self.assertTrue(rem.alert_names_job(
            {"title": "pid=777 is hot"}, "job-9", "/w", [777]))
        self.assertFalse(rem.alert_names_job(
            {"title": "some other job"}, "job-9", "/w", [1]))

    def test_confinement_fallback_is_strain(self):
        with tempfile.TemporaryDirectory() as base:
            path = os.path.join(base, "security-audit.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": _iso(), "feature": "confinement",
                    "decision": "fallback", "reason": "no bwrap",
                    "job_id": "job-9"}) + "\n")
                fh.write(json.dumps({
                    "ts": _iso(), "feature": "confinement",
                    "decision": "sandboxed", "job_id": "other"}) +
                    "\n")
            recs = rem.confinement_events_in_window(
                base, "job-9", time.time() - 60)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["decision"], "fallback")
            mon = rem.JobMonitor(
                _settings(), "job-9", 4242, base,
                sampler=lambda _pid: {4242: (0.0, None)},
                base_dir=base)
            mon.sample_once()
            self.assertEqual(
                [d["kind"] for d in mon.outcome["divergences"]],
                ["confinement_strain"])

    def test_member_shape_is_exactly_the_designs(self):
        div = rem.divergence("process_storm", "90 processes")
        member = rem.result_member("deterministic", "tripwire", div,
                                   "killed", "unavailable", "ab" * 48)
        self.assertEqual(set(member), {
            "mode", "authority", "divergence", "act", "av_verdict",
            "received_digest"})
        self.assertTrue(member["divergence"].startswith(
            "process_storm"))


@unittest.skipIf(not POSIX, "execute_job fixtures are POSIX shell")
class ExecuteJobTest(unittest.TestCase):
    """Real subprocesses through runner.execute_job."""

    def _run(self, cfg, job):
        base = tempfile.mkdtemp(prefix="hp-rem-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            base, ignore_errors=True))
        return base, runner.execute_job(cfg, job, base)

    def test_benign_job_is_untouched(self):
        base, r = self._run({}, {
            "job_id": "benign-1", "kind": "exec",
            "script": "echo hello; touch mine.txt; rm mine.txt"})
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)
        self.assertTrue(os.path.isdir(
            os.path.join(base, "work", "benign-1")))

    def test_benign_job_in_every_mode(self):
        for mode in ("off", "deterministic", "oracle"):
            _base, r = self._run({"remediation_mode": mode}, {
                "job_id": "benign-" + mode, "kind": "exec",
                "script": "echo fine"})
            self.assertEqual(r["exit_code"], 0, mode)
            self.assertNotIn("remediation", r, mode)

    def test_declared_credential_twin_is_not_tripped(self):
        # The script itself names the credential path (the
        # envelope declares it) and a produced file repeats it:
        # the job is doing what it said. No tripwire, no member.
        _base, r = self._run({"remediation_sample_sec": 0.1}, {
            "job_id": "twin-1", "kind": "exec",
            "script": "printf 'see ~/.aws/credentials here' "
                      "> note.txt; cat ~/.aws/credentials "
                      "2>/dev/null; echo ok"})
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)

    def test_undeclared_credential_artifact_quarantines(self):
        cfg = {"remediation_sample_sec": 0.1}
        with mock.patch.object(rem, "av_referral",
                               return_value=("clean", "fake scan")):
            base, r = self._run(cfg, {
                "job_id": "leak-1", "kind": "exec",
                "script": "printf 'read /home/user/.aws/cre%s' "
                          "'dentials now' > leak.txt; echo done"})
        member = r["remediation"]
        self.assertEqual(member["mode"], "deterministic")
        self.assertEqual(member["authority"], "tripwire")
        self.assertTrue(member["divergence"].startswith(
            "credential_artifact"))
        # The script exits in milliseconds. Whether the sampler's
        # kill lands before the shell's own exit is a race the
        # runner reports as it fell (remediation_ops: the act that
        # landed), so either act is the right record; what must
        # hold is that the recorded act matches what happened to
        # the process -- a clean exit for a quarantine, a signal
        # for a kill. A loaded macOS runner took the kill branch
        # where Linux takes the quarantine.
        self.assertIn(member["act"], ("quarantined", "killed"))
        self.assertEqual(r["exit_code"] == 0,
                         member["act"] == "quarantined")
        self.assertEqual(member["av_verdict"], "clean")
        self.assertEqual(member["received_digest"],
                         rem.received_digest({
                             "job_id": "leak-1", "kind": "exec",
                             "script": "printf 'read /home/user/"
                                       ".aws/cre%s' 'dentials now' > "
                                       "leak.txt; echo done"}))
        # The workdir moved; the marker and the records exist.
        self.assertFalse(os.path.exists(
            os.path.join(base, "work", "leak-1")))
        marker = rem.load_marker(base, "leak-1")
        self.assertEqual(marker["act"], member["act"])
        events = rem._read_jsonl_window(
            os.path.join(base, "security-events.jsonl"), 0)
        self.assertTrue(any(e.get("type") == "remediation"
                            for e in events))
        audit = rem._read_jsonl_window(
            os.path.join(base, "security-audit.jsonl"), 0)
        self.assertTrue(any(
            e.get("feature") == "remediation"
            and e.get("decision") == "acted" for e in audit))

    def test_mid_run_tripwire_kills_the_tree(self):
        cfg = {"remediation_sample_sec": 0.1}
        t0 = time.monotonic()
        _base, r = self._run(cfg, {
            "job_id": "leak-2", "kind": "exec", "timeout_sec": 60,
            "script": "printf 'read /home/user/.aws/cre%s' "
                      "'dentials' > leak.txt; sleep 30"})
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 20)
        self.assertNotEqual(r["exit_code"], 0)
        self.assertFalse(r["timed_out"])
        self.assertEqual(r["remediation"]["act"], "killed")
        self.assertEqual(r["remediation"]["authority"], "tripwire")

    def test_process_storm_kills_the_whole_tree(self):
        cfg = {"remediation_sample_sec": 0.1,
               "remediation_storm_ceiling": 5}
        t0 = time.monotonic()
        _base, r = self._run(cfg, {
            "job_id": "storm-1", "kind": "exec", "timeout_sec": 60,
            "script": "for i in 1 2 3 4 5 6 7 8 9 10 11 12; do "
                      "sleep 25 & done; wait"})
        # The bound is promptness, not a documented promise:
        # off Linux the sampler shells out to ps per pass, and a
        # shared runner's fork/exec is slower, so the same kill
        # took 25s on macOS and on FreeBSD where Linux does it
        # in a few. The substance -- killed, named a process
        # storm -- is asserted below at every bound.
        bound = 20 if sys.platform == "linux" else 60
        self.assertLess(time.monotonic() - t0, bound)
        self.assertEqual(r["remediation"]["act"], "killed")
        self.assertTrue(r["remediation"]["divergence"].startswith(
            "process_storm"))

    def test_off_mode_watches_and_pages_only(self):
        cfg = {"remediation_mode": "off",
               "remediation_sample_sec": 0.1}
        t0 = time.monotonic()
        base, r = self._run(cfg, {
            "job_id": "leak-off", "kind": "exec",
            "script": "printf 'read /home/user/.aws/cre%s' "
                      "'dentials' > leak.txt; sleep 2"})
        # Not killed: the job ran its full sleep.
        self.assertGreaterEqual(time.monotonic() - t0, 2.0)
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)
        self.assertTrue(os.path.isdir(
            os.path.join(base, "work", "leak-off")))
        events = rem._read_jsonl_window(
            os.path.join(base, "security-events.jsonl"), 0)
        rem_events = [e for e in events
                      if e.get("type") == "remediation"]
        self.assertEqual(len(rem_events), 1)
        self.assertEqual(rem_events[0]["act"], "none")

    def test_sender_member_cannot_narrow_remediation(self):
        # A job carrying remediation: "off" is still tripped --
        # the member is ignored, per the unknown-fields rule.
        cfg = {"remediation_sample_sec": 0.1}
        _base, r = self._run(cfg, {
            "job_id": "leak-3", "kind": "exec",
            "remediation": "off",
            "script": "printf 'read /home/user/.aws/cre%s' "
                      "'dentials' > leak.txt; echo done"})
        self.assertIn("remediation", r)
        # Tripped either way; the act is the one that landed (see
        # test_undeclared_credential_artifact_quarantines).
        self.assertIn(r["remediation"]["act"], ("quarantined", "killed"))
        self.assertEqual(r["remediation"]["authority"], "tripwire")
        src = open(runner.__file__, encoding="utf-8").read()
        self.assertNotIn('job.get("remediation"', src)
        self.assertNotIn("job['remediation']", src)

    def test_sender_member_cannot_widen_remediation(self):
        _base, r = self._run({}, {
            "job_id": "plain-1", "kind": "exec",
            "remediation": "oracle", "script": "echo harmless"})
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)


@unittest.skipIf(not POSIX, "execute_job fixtures are POSIX shell")
class ExecuteJobOracleTest(unittest.TestCase):
    """The Oracle layer end to end, inference faked at ask_model."""

    def _stage_alert(self, base, job_id):
        path = os.path.join(base, "senses.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "sensor": "watcher", "severity": "high",
                "title": f"job {job_id} is doing something odd",
                "observed_at": _iso()}) + "\n")

    def _cfg(self):
        return {"remediation_mode": "oracle",
                "remediation_sample_sec": 0.1,
                "inference": {"endpoint": "http://127.0.0.1:11434/v1",
                              "model": "fake-model",
                              "timeout_sec": 5}}

    def test_oracle_order_kills(self):
        base = tempfile.mkdtemp(prefix="hp-rem-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            base, ignore_errors=True))
        self._stage_alert(base, "oracle-1")
        with mock.patch.object(
                runner, "ask_model",
                return_value={"answer": "KILL: it is odd"}) as ask:
            t0 = time.monotonic()
            r = runner.execute_job(self._cfg(), {
                "job_id": "oracle-1", "kind": "exec",
                "timeout_sec": 60, "script": "sleep 10"}, base)
        self.assertLess(time.monotonic() - t0, 8)
        self.assertTrue(ask.called)
        self.assertEqual(r["remediation"]["authority"], "oracle")
        self.assertEqual(r["remediation"]["act"], "killed")

    def test_oracle_spare_lets_the_job_finish(self):
        base = tempfile.mkdtemp(prefix="hp-rem-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            base, ignore_errors=True))
        self._stage_alert(base, "oracle-2")
        with mock.patch.object(
                runner, "ask_model",
                return_value={"answer": "SPARE: it is fine"}):
            r = runner.execute_job(self._cfg(), {
                "job_id": "oracle-2", "kind": "exec",
                "script": "sleep 1"}, base)
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)
        audit = rem._read_jsonl_window(
            os.path.join(base, "security-audit.jsonl"), 0)
        self.assertTrue(any(
            e.get("feature") == "remediation"
            and e.get("decision") == "spared" for e in audit))

    def test_oracle_timeout_abstains(self):
        base = tempfile.mkdtemp(prefix="hp-rem-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            base, ignore_errors=True))
        self._stage_alert(base, "oracle-3")
        with mock.patch.object(
                runner, "ask_model",
                side_effect=TimeoutError("slow model")):
            r = runner.execute_job(self._cfg(), {
                "job_id": "oracle-3", "kind": "exec",
                "script": "sleep 1"}, base)
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)
        audit = rem._read_jsonl_window(
            os.path.join(base, "security-audit.jsonl"), 0)
        self.assertTrue(any(
            e.get("feature") == "remediation"
            and e.get("decision") == "abstained" for e in audit))

    def test_deterministic_mode_makes_zero_inference_calls(self):
        base = tempfile.mkdtemp(prefix="hp-rem-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            base, ignore_errors=True))
        self._stage_alert(base, "det-1")
        cfg = self._cfg()
        cfg["remediation_mode"] = "deterministic"
        with mock.patch.object(
                runner, "ask_model",
                side_effect=AssertionError("called")) as ask:
            r = runner.execute_job(cfg, {
                "job_id": "det-1", "kind": "exec",
                "script": "sleep 1"}, base)
        self.assertEqual(ask.call_count, 0)
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("remediation", r)


class ConfinementFollowupTest(unittest.TestCase):
    def test_escape_at_result_time_quarantines(self):
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work", "esc-1")
            os.makedirs(work)
            with open(os.path.join(work, "loot.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("x")
            job = {"job_id": "esc-1", "kind": "exec",
                   "script": "echo x"}
            member = runner._remediation_confinement_followup(
                {}, job, "esc-1", base)
            self.assertEqual(member["authority"], "tripwire")
            self.assertEqual(member["act"], "quarantined")
            self.assertTrue(member["divergence"].startswith(
                "confinement_escape"))
            self.assertFalse(os.path.exists(work))
            self.assertIsNotNone(rem.load_marker(base, "esc-1"))

    def test_escape_with_an_unmeasurable_file_still_quarantines(self):
        # Queue A refill: the followup's sample
        # loop (coverage run 40189711740: lines
        # 3375-3376). A quarantined file whose
        # size cannot be read -- here a symlink
        # whose target is gone -- is skipped for
        # the referral list, not fatal to the
        # quarantine.
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work", "esc-3")
            os.makedirs(work)
            with open(os.path.join(work, "loot.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("x")
            try:
                os.symlink(os.path.join(base, "gone-target"),
                           os.path.join(work, "ghost.txt"))
            except (OSError, NotImplementedError):
                self.skipTest("needs symlink")
            job = {"job_id": "esc-3", "kind": "exec",
                   "script": "echo x"}
            member = runner._remediation_confinement_followup(
                {}, job, "esc-3", base)
            self.assertEqual(member["act"], "quarantined")
            self.assertFalse(os.path.exists(work))

    def test_escape_in_off_mode_only_records(self):
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work", "esc-2")
            os.makedirs(work)
            member = runner._remediation_confinement_followup(
                {"remediation_mode": "off"},
                {"job_id": "esc-2"}, "esc-2", base)
            self.assertIsNone(member)
            self.assertTrue(os.path.isdir(work))


class DriRemediationTest(unittest.TestCase):
    def _dcfg(self):
        return dri.parse_dri({"dri": {
            "enabled": True, "triggers": {"remediation": True}}})

    def _write_event(self, base, act):
        path = os.path.join(base, "security-events.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "type": "remediation", "at": _iso(),
                "job_id": "job-7", "mode": "deterministic",
                "authority": "tripwire",
                "divergence": "process_storm: 90 processes",
                "act": act, "av_verdict": "unavailable",
                "quarantine": "/base/quarantine/job-7",
                "envelope": "declared paths: none"}) + "\n")

    def test_trigger_is_accepted(self):
        self.assertIs(self._dcfg()["triggers"]["remediation"], True)

    def test_acted_event_pages_as_an_act(self):
        with tempfile.TemporaryDirectory() as base:
            self._write_event(base, "killed")
            events = dri.evaluate_page_triggers(
                self._dcfg(), base, 0, now=time.time())
            rem_events = [e for e in events
                          if e["trigger"] == "remediation"]
            self.assertEqual(len(rem_events), 1)
            self.assertTrue(rem_events[0]["acted"])
            text = dri.format_page(rem_events)
            self.assertIn("remediation acted as recorded above",
                          text)
            self.assertNotIn("the Oracle took no action.", text)
            self.assertIn("process_storm", text)

    def test_observed_event_pages_as_no_action(self):
        with tempfile.TemporaryDirectory() as base:
            self._write_event(base, "none")
            events = dri.evaluate_page_triggers(
                self._dcfg(), base, 0, now=time.time())
            rem_events = [e for e in events
                          if e["trigger"] == "remediation"]
            self.assertEqual(len(rem_events), 1)
            text = dri.format_page(rem_events)
            self.assertIn("the Oracle took no action.", text)


class ReleaseDoorTest(unittest.TestCase):
    def test_main_release_door_round_trip(self):
        from runner.ops import setup
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work", "job-rel")
            os.makedirs(work)
            with open(os.path.join(work, "out.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("data")
            rem.quarantine_job(base, "job-rel", work,
                               {"authority": "tripwire"})
            cfg_path = os.path.join(base, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump({"shared_secret": "x" * 32,
                           "base_dir": base}, fh)
            with mock.patch.object(setup, "is_tty",
                                   return_value=False), \
                    mock.patch.object(sys, "argv", [
                        "runner", "--config", cfg_path,
                        "--remediation-release", "job-rel"]):
                code = runner.main()
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(
                os.path.join(base, "work", "job-rel", "out.txt")))
            audit = rem._read_jsonl_window(
                os.path.join(base, "security-audit.jsonl"), 0)
            self.assertTrue(any(
                e.get("feature") == "remediation"
                and e.get("decision") == "released" for e in audit))

    def test_main_release_door_unknown_job(self):
        from runner.ops import setup
        with tempfile.TemporaryDirectory() as base:
            cfg_path = os.path.join(base, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump({"shared_secret": "x" * 32,
                           "base_dir": base}, fh)
            with mock.patch.object(setup, "is_tty",
                                   return_value=False), \
                    mock.patch.object(sys, "argv", [
                        "runner", "--config", cfg_path,
                        "--remediation-release", "nope-1"]):
                code = runner.main()
            self.assertEqual(code, 1)


class FixMarkerDigestWriteTest(unittest.TestCase):
    """Queue A: fix_marker_digest's write path never ran
    on Windows (coverage run 40183585961: 10 lines) --
    the one caller-side test patches open to raise, so
    the rewrite that lands was asserted nowhere. The
    contract (the ingest handler holds the job as
    received; the marker must name the same digest as
    the result): a differing digest is rewritten in
    place, a matching one leaves the file alone, and a
    write that fails is swallowed -- never raises. Two
    lines stay uncovered by construction: the second
    _safe_job_id gate cannot fire, because load_marker
    only loads under an id that already passed it.
    """

    def _quarantine(self, base, digest="abc"):
        work = os.path.join(base, "work")
        os.makedirs(work)
        with open(os.path.join(work, "out.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("x")
        dest = rem.quarantine_job(
            base, "job-1", work, {"received_digest": digest})
        self.assertTrue(dest)
        return os.path.join(dest, "remediation.json")

    def test_a_differing_digest_is_rewritten_in_place(self):
        with tempfile.TemporaryDirectory() as base:
            marker_path = self._quarantine(base)
            rem.fix_marker_digest(base, "job-1", "def")
            marker = rem.load_marker(base, "job-1")
            self.assertEqual(marker["received_digest"], "def")
            with open(marker_path, encoding="utf-8") as fh:
                self.assertEqual(
                    json.load(fh)["received_digest"], "def")

    def test_a_matching_digest_leaves_the_file_alone(self):
        with tempfile.TemporaryDirectory() as base:
            marker_path = self._quarantine(base)
            with open(marker_path, "rb") as fh:
                before = fh.read()
            rem.fix_marker_digest(base, "job-1", "abc")
            with open(marker_path, "rb") as fh:
                self.assertEqual(fh.read(), before)

    def test_a_failed_write_is_swallowed(self):
        with tempfile.TemporaryDirectory() as base:
            self._quarantine(base)
            with mock.patch("builtins.open",
                            side_effect=OSError("read-only")):
                rem.fix_marker_digest(base, "job-1", "def")
            marker = rem.load_marker(base, "job-1")
            self.assertEqual(marker["received_digest"], "abc")

    def test_a_write_failure_after_a_good_read_is_swallowed(self):
        # The except pair itself (coverage run 40186330078:
        # still unrun on Windows, because the only other
        # selective-write leg lives inside an AV test that
        # skips on Windows). Reads pass, the rewrite's open
        # raises: the function swallows it and the marker
        # keeps the digest it had.
        with tempfile.TemporaryDirectory() as base:
            self._quarantine(base)
            # The rewrite is the atomic writer's os.open of the temp
            # name (guard/atomicio); the marker read is builtins.open.
            with mock.patch.object(rem._atomicio, "_open_new",
                                   side_effect=OSError("read-only")):
                rem.fix_marker_digest(base, "job-1", "def")
            marker = rem.load_marker(base, "job-1")
            self.assertEqual(marker["received_digest"], "abc")


class TotalMemoryWindowsBranchTest(unittest.TestCase):
    """Queue A: total_memory_bytes' Windows branch --
    its failure leg never ran anywhere (the branch only
    runs on Windows, and there the read succeeds). A
    Windows read that raises answers None: the box's RAM
    is unknown, never a made-up number. Scripted through
    the platform names the function itself consults.
    """

    def test_a_windows_read_answers_and_fails_to_none(self):
        with mock.patch.object(rem.sys, "platform", "win32"), \
                mock.patch.object(rem.os, "name", "nt"), \
                mock.patch.object(
                    rem, "_win_total_memory",
                    return_value=17179869184):
            self.assertEqual(rem.total_memory_bytes(),
                             17179869184)
        with mock.patch.object(rem.sys, "platform", "win32"), \
                mock.patch.object(rem.os, "name", "nt"), \
                mock.patch.object(
                    rem, "_win_total_memory",
                    side_effect=OSError("no route")):
            self.assertIsNone(rem.total_memory_bytes())


class WinCreatedTicksLegTest(unittest.TestCase):
    """Queue A refill: _win_created_ticks'
    unreadable-times answer (coverage run
    40189711740: remediation.py line 368). A
    process whose times cannot be read has no
    known birthday -- None, never a guess.
    The kernel32 seam is a fake, so the leg
    runs on any platform.
    """

    def test_unreadable_times_are_none(self):
        import ctypes
        kernel32 = mock.Mock()
        kernel32.OpenProcess.return_value = 1234
        kernel32.GetProcessTimes.return_value = 0
        with mock.patch.object(
                ctypes, "WinDLL", return_value=kernel32,
                create=True):
            self.assertIsNone(rem._win_created_ticks(42))
        kernel32.CloseHandle.assert_called_once_with(1234)


if __name__ == "__main__":
    unittest.main()
