# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""FreeBSD jail containment for confinement.

Three layers, one module:

- The seams. The backend (runner/guard/freebsd_confine.py) wired
  into the confinement gates: the startup gate's decision table
  with a scripted backend, the argv gate with sys.platform
  patched, and the spawn seam against a fake backend.
- The backend's own logic, on every platform. Everything below
  the public names is written against a host object -- the
  commands it runs and the few facts it reads -- and the classes
  here hand it a host that exists only as its own record (a
  mount table, a set of jails, a list of rctl rules). What a
  jail is built from, in what order, what the record names, what
  the release removes and what it must never remove are pinned
  without a FreeBSD kernel.
- The kernel, where it is real. The live classes run only on a
  FreeBSD host as root (the freebsd-confinement workflow's
  guests, and the fleet node) and read the boundary from inside
  a job.

The mode a fresh install states rides the same three layers: the
seed asks the backend's probe before it writes
(runner/ops/install.py, fresh_platform_modes), with a scripted
probe on every platform and the real one where the kernel is.

The honesty pins matter most: no audit record may name a
control that was not applied to that job (the rctl rules are
named only where RACCT can hold them, and there is no Capsicum
in this backend), and every failure lands in the refuse
direction.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
from runner.guard import freebsd_confine as FC
from runner.ops import remediation_ops as REM
from runner.ops import install as INS
from runner.ops import setup as SU


def _ccfg(mode):
    return {"security": {"modes": {"confinement": mode}}}


def _sec(mode, sink):
    sec = mock.Mock()
    sec.sec_mode.return_value = mode

    def _write(base_dir, feature, decision, reason, **kw):
        sink.append({"feature": feature, "decision": decision,
                     "reason": reason, "kw": kw})
    sec.write_audit_entry.side_effect = _write
    return sec


def _backend(problem=None, apply_error=None, status=None, notes=()):
    backend = types.SimpleNamespace()

    def _probe(cfg=None, timeout=15):
        if isinstance(problem, Exception):
            raise problem
        return problem

    backend.freebsd_startup_problem = _probe
    backend.freebsd_confinement_problem = _probe
    backend.IS_FREEBSD_BACKEND = True
    backend.STATUS_CONFINEMENT = FC.STATUS_CONFINEMENT \
        if hasattr(FC, "STATUS_CONFINEMENT") else \
        "freebsd: jail + no_network + spawn_resource_limits"
    backend.spawned = []

    def _spawn(argv, cwd=None, env=None, user=None, cfg=None):
        if apply_error is not None:
            raise apply_error
        proc = types.SimpleNamespace(
            pid=31337, returncode=None,
            confinement_status=status or backend.STATUS_CONFINEMENT,
            confinement_notes=list(notes),
            closed=False)
        proc.close = lambda: setattr(proc, "closed", True)
        backend.spawned.append(
            {"argv": argv, "cwd": cwd, "env": env, "user": user,
             "cfg": cfg, "proc": proc})
        return proc

    backend.spawn_confined_process = _spawn
    return backend


class BackendStubTest(unittest.TestCase):
    """The module itself, on a host that is not FreeBSD."""

    def setUp(self):
        if FC.IS_FREEBSD_BACKEND:
            self.skipTest("the stub exists only off freebsd")

    def test_import_is_safe_and_the_probe_refuses(self):
        problem = FC.freebsd_startup_problem()
        self.assertIsInstance(problem, str)
        self.assertIn("FreeBSD-only", problem)
        self.assertIn("FreeBSD-only", FC.freebsd_confinement_problem())

    def test_spawn_and_translation_raise_off_freebsd(self):
        with self.assertRaises(RuntimeError):
            FC.spawn_confined_process(["/bin/sh", "-c", "true"])
        with self.assertRaises(RuntimeError):
            FC.build_jail_argv(["/bin/sh"])

    def test_the_status_names_exactly_the_three_controls(self):
        self.assertEqual(
            FC.STATUS_CONFINEMENT,
            "freebsd: jail + no_network + spawn_resource_limits")
        self.assertEqual(
            FC.CONFINEMENT_CONTROLS,
            ("jail", "no_network", "spawn_resource_limits"))

    def test_the_status_names_nothing_the_backend_does_not_apply(self):
        # RACCT/RCTL is disabled on the fleet node, and Capsicum
        # does not fit the launcher shape: neither may be named.
        self.assertNotIn("rctl", FC.STATUS_CONFINEMENT)
        self.assertNotIn("capsicum", FC.STATUS_CONFINEMENT.lower())
        self.assertNotIn("sandbox", FC.STATUS_CONFINEMENT)


class ConfinementStartupGateTest(unittest.TestCase):
    """confinement_startup_problem: FreeBSD consults the backend."""

    def test_engageable_backend_lets_enforce_start(self):
        self.assertIsNone(rr._confinement_startup_problem(
            _ccfg("enforce"), platform="freebsd14",
            backend=_backend(None)))

    def test_unengageable_backend_refuses_and_names_why(self):
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="freebsd14",
            backend=_backend("jail -c failed (exit 1): jail: "
                             "name is too long"))
        self.assertIsNotNone(problem)
        self.assertIn("confinement cannot engage on freebsd", problem)
        self.assertIn("jail -c failed", problem)

    def test_a_backend_that_raises_still_refuses(self):
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="freebsd14",
            backend=_backend(RuntimeError("module gone")))
        self.assertIsNotNone(problem)
        self.assertIn("module gone", problem)

    def test_audit_and_off_are_never_refused_by_the_gate(self):
        for mode in ("audit", "off"):
            self.assertIsNone(rr._confinement_startup_problem(
                _ccfg(mode), platform="freebsd14",
                backend=_backend("cannot engage")), mode)

    def test_non_freebsd_is_untouched_by_the_backend(self):
        self.assertIsNone(rr._confinement_startup_problem(
            _ccfg("enforce"), platform="linux",
            backend=_backend("cannot engage")))

    def test_simulated_freebsd_refusal_is_deterministic(self):
        # No backend injected and the platform simulated: the
        # gate cannot probe a machine this is not, so the
        # deterministic refusal stands, on any host.
        if FC.IS_FREEBSD_BACKEND:
            self.skipTest(
                "the simulated FreeBSD refusal is deterministic "
                "off FreeBSD")
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="freebsd14")
        self.assertEqual(
            problem,
            "confinement (bwrap) is Linux-only; "
            "this machine is freebsd14")


class ConfinementArgvTest(unittest.TestCase):
    """_confinement_argv on a simulated FreeBSD: the argv gate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, mode, backend):
        sink = []
        with mock.patch.object(sys, "platform", "freebsd14"), \
                mock.patch.object(rr, "_security", _sec(mode, sink)):
            out = rr._confinement_argv(
                _ccfg(mode), self.base, "j1", ["python"], "script.py",
                self.base, [], {}, backend=backend)
        return out, sink

    def test_engageable_backend_returns_the_normal_argv(self):
        out, _sink = self._run("enforce", _backend(None))
        self.assertEqual(out, (["python", "script.py"], True, False))

    def test_unengageable_backend_denies_the_job(self):
        # Q135: the decision answers a denial -- the empty
        # argv -- and the job boundary refuses on it; the
        # decision itself never raises. The record is the
        # fallback row, exactly as the raising shape left it.
        out, sink = self._run("enforce", _backend("not root"))
        self.assertEqual(out, ([], True, False))
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"], "confinement_unavailable")


class ConfinementSpawnTest(unittest.TestCase):
    """_confinement_spawn: the jail creation-time application."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _secmap(self, modes, sink):
        sec = mock.Mock()
        sec.sec_mode.side_effect = lambda cfg, name: modes.get(
            name, "off")

        def _write(base_dir, feature, decision, reason, **kw):
            sink.append({"feature": feature, "decision": decision,
                         "reason": reason, "kw": kw})
        sec.write_audit_entry.side_effect = _write
        return sec

    def _run(self, cfg, modes, backend="unset"):
        sink = []
        kw = {} if backend == "unset" else {"backend": backend}
        with mock.patch.object(sys, "platform", "freebsd14"), \
                mock.patch.object(REM.os, "name", "posix"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(modes, sink)):
            out = REM._confinement_spawn(
                cfg, self.base, "j1", ["/bin/sh", "s.sh"],
                self.base, {}, **kw)
        return out, sink

    def test_other_platforms_are_a_noop(self):
        sink = []
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(REM.os, "name", "posix"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(
                                      {"confinement": "enforce"}, sink)):
            out = REM._confinement_spawn(
                _ccfg("enforce"), self.base, "j1", ["/bin/sh", "s.sh"],
                self.base, {}, backend=_backend(None))
        self.assertIsNone(out)
        self.assertEqual(sink, [])

    def test_audit_and_off_spawn_nothing(self):
        for mode in ("audit", "off"):
            out, _sink = self._run(
                _ccfg(mode), {"confinement": mode},
                backend=_backend(None))
            self.assertIsNone(out, mode)

    def test_enforce_spawns_and_records_exactly_the_controls(self):
        backend = _backend(None)
        (proc, release), sink = self._run(
            _ccfg("enforce"), {"confinement": "enforce"},
            backend=backend)
        self.assertEqual(proc.pid, 31337)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["feature"], "confinement")
        self.assertEqual(sink[0]["decision"], "confined")
        self.assertEqual(
            sink[0]["reason"],
            "freebsd: jail + no_network + spawn_resource_limits")
        self.assertNotIn("rctl", sink[0]["reason"])
        release()
        self.assertTrue(proc.closed)

    def test_the_record_carries_the_job_s_own_controls_and_notes(self):
        # The process object's string, not the floor: a job
        # whose jail carried more is recorded as carrying more,
        # and a read-only mount added for its interpreter is in
        # the record's detail.
        status = ("freebsd: jail + no_network + no_superuser + "
                  "rctl_resource_limits + spawn_resource_limits")
        backend = _backend(None, status=status, notes=[
            "interpreter prefix /opt/py311 mounted read-only"])
        (_proc, _release), sink = self._run(
            _ccfg("enforce"), {"confinement": "enforce"},
            backend=backend)
        self.assertEqual(sink[0]["reason"], status)
        self.assertEqual(
            sink[0]["kw"]["detail"],
            "interpreter prefix /opt/py311 mounted read-only")

    def test_the_config_rides_to_the_spawn(self):
        backend = _backend(None)
        cfg = {"security": {
            "modes": {"confinement": "enforce"},
            "confinement": {"work_mount": "/job"}}}
        self._run(cfg, {"confinement": "enforce"}, backend=backend)
        self.assertIs(backend.spawned[0]["cfg"], cfg)

    def test_enforce_hands_the_job_user_to_the_spawn(self):
        backend = _backend(None)
        cfg = {"security": {
            "modes": {"confinement": "enforce",
                      "job_user": "enforce"},
            "job_user": {"user": "nobody"}}}
        self._run(cfg, {"confinement": "enforce",
                        "job_user": "enforce"}, backend=backend)
        self.assertEqual(backend.spawned[0]["user"], "nobody")

    def test_no_user_is_handed_over_when_job_user_is_not_enforce(self):
        backend = _backend(None)
        cfg = {"security": {
            "modes": {"confinement": "enforce"},
            "job_user": {"user": "nobody"}}}
        self._run(cfg, {"confinement": "enforce"}, backend=backend)
        self.assertIsNone(backend.spawned[0]["user"])

    def test_enforce_spawn_failure_refuses_and_records_fallback(self):
        backend = _backend(None, apply_error=RuntimeError("jail 1"))
        sink_modes = {"confinement": "enforce"}
        sink = []
        with mock.patch.object(sys, "platform", "freebsd14"), \
                mock.patch.object(REM.os, "name", "posix"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(sink_modes, sink)):
            with self.assertRaises(rr.JobRejected):
                REM._confinement_spawn(
                    _ccfg("enforce"), self.base, "j1",
                    ["/bin/sh", "s.sh"], self.base, {},
                    backend=backend)
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"],
                         "freebsd_confinement_failed")


_EXAMPLE_CONFIG = os.path.join(_REPO, "runner", "config.example.json")
_INSTALL_PY = os.path.join(_REPO, "runner", "ops", "install.py")

_PASS_LINES = ("FreeBSD jail backend: freebsd: jail + no_network + "
               "no_superuser + spawn_resource_limits",
               "RACCT is not enabled on this host")
_ROOT_REASON = ("creating a jail needs root; the runner is not "
                "running as root")


def _seeded_config(folder, modes=None, confinement=None):
    """The example config as a fresh install leaves it in
    `folder`, with a mode or a confinement block laid over it."""
    with open(_EXAMPLE_CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if modes:
        cfg["security"]["modes"].update(modes)
    if confinement:
        cfg["security"]["confinement"] = confinement
    path = os.path.join(folder, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return path


def _modes_in(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["security"]["modes"]


class _Probe:
    """A scripted answer to the seed's question, and what it
    was asked with."""

    def __init__(self, problem=None, lines=_PASS_LINES, error=None):
        self.problem, self.lines, self.error = problem, lines, error
        self.asked = []

    def __call__(self, cfg):
        self.asked.append(cfg)
        if self.error is not None:
            raise self.error
        if self.problem is not None:
            return (self.problem, ())
        return (None, self.lines)


class SeedTest(unittest.TestCase):
    """The mode a fresh FreeBSD config states: the machine's
    answer where it is asked, the stated map where it is not."""

    def _apply(self, path, platform="freebsd14", probe=None):
        out = io.StringIO()
        with redirect_stdout(out):
            applied = INS.apply_platform_modes(path, platform,
                                               probe=probe)
        return applied, out.getvalue()

    # --- the map, where nothing is asked -----------------------

    def test_the_map_states_confinement_audit_only(self):
        self.assertEqual(INS.platform_modes("freebsd14"),
                         {"confinement": "audit"})

    def test_a_named_platform_is_not_asked(self):
        # A platform the caller names is a question about that
        # platform, not about this machine: the stated map, and
        # no answer because no question was put -- on a real
        # FreeBSD host too.
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        with mock.patch.object(INS, "freebsd_seed_probe",
                               side_effect=AssertionError("asked")):
            modes, asked = INS.fresh_platform_modes(cfg, "freebsd14")
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertIsNone(asked)

    def test_a_named_platform_s_wizard_seed_states_audit(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        SU.seed_platform_modes(cfg, platform="freebsd14")
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        # job_user is a POSIX demote and engages on FreeBSD; the
        # seed does not state it down.
        self.assertEqual(cfg["security"]["modes"]["job_user"],
                         "enforce")

    def test_a_simulated_freebsd_is_not_asked(self):
        # sys.platform says FreeBSD and the process did not start
        # on one: the backend is never reached from the seed.
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        with mock.patch.object(INS, "_HOST_PLATFORM", "linux"), \
                mock.patch.object(INS.sys, "platform", "freebsd14"), \
                mock.patch.object(
                    INS, "_import_freebsd_confine",
                    side_effect=AssertionError("imported")):
            modes, asked = INS.fresh_platform_modes(cfg)
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertIsNone(asked)

    def test_a_freebsd_host_is_asked_through_the_backend_s_probe(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        probe = _Probe()
        with mock.patch.object(INS, "_HOST_PLATFORM", "freebsd14"), \
                mock.patch.object(INS.sys, "platform", "freebsd14"), \
                mock.patch.object(INS, "freebsd_seed_probe", probe):
            modes, asked = INS.fresh_platform_modes(cfg)
        self.assertEqual(probe.asked, [cfg])
        self.assertEqual(modes, {})
        self.assertEqual(asked, (None, _PASS_LINES))

    def test_other_platforms_are_never_asked(self):
        probe = _Probe()
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        for platform, want in (
                ("linux", {}),
                ("darwin", {"confinement": "audit"}),
                ("win32", {"confinement": "audit",
                           "job_user": "audit"})):
            modes, asked = INS.fresh_platform_modes(cfg, platform,
                                                    probe)
            self.assertEqual(modes, want, platform)
            self.assertIsNone(asked, platform)
        self.assertEqual(probe.asked, [])

    # --- the installer's seed ----------------------------------

    def test_a_passing_probe_leaves_enforce_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            with open(path, "rb") as fh:
                before = fh.read()
            applied, out = self._apply(path, probe=_Probe())
            with open(path, "rb") as fh:
                after = fh.read()
            modes = _modes_in(path)
        self.assertEqual(applied, {})
        self.assertEqual(before, after)
        self.assertEqual(modes["confinement"], "enforce")
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, out)
        self.assertIn("passed", out)
        # What a job's jail carries on this host, as the posture
        # report words it.
        for line in _PASS_LINES:
            self.assertIn("platform: " + line, out)
        self.assertNotIn("stated as audit", out)

    def test_a_failing_probe_states_audit_with_its_reason(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            applied, out = self._apply(
                path, probe=_Probe(problem=_ROOT_REASON))
            modes = _modes_in(path)
        self.assertEqual(applied, {"confinement": "audit"})
        self.assertEqual(modes["confinement"], "audit")
        self.assertEqual(modes["job_user"], "enforce")
        self.assertIn("security.modes.confinement stated as audit "
                      "in %s" % path, out)
        self.assertIn("did not pass: " + _ROOT_REASON, out)
        self.assertNotIn("left at enforce", out)

    def test_the_probe_is_asked_about_the_config_as_written(self):
        block = {"freebsd": {"loopback": True, "job_processes": 64}}
        probe = _Probe()
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d, confinement=block)
            self._apply(path, probe=probe)
        self.assertEqual(len(probe.asked), 1)
        self.assertEqual(
            probe.asked[0]["security"]["confinement"], block)

    def test_a_mode_stated_lower_is_the_operator_s_and_not_asked(self):
        for mode in ("audit", "off"):
            probe = _Probe()
            with tempfile.TemporaryDirectory() as d:
                path = _seeded_config(d, modes={"confinement": mode})
                with open(path, "rb") as fh:
                    before = fh.read()
                applied, out = self._apply(path, probe=probe)
                with open(path, "rb") as fh:
                    after = fh.read()
            self.assertEqual(applied, {}, mode)
            self.assertEqual(before, after, mode)
            self.assertEqual(probe.asked, [], mode)
            self.assertEqual(out, "", mode)

    def test_a_probe_that_cannot_answer_is_a_reason_never_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            applied, out = self._apply(
                path, probe=_Probe(error=OSError("jail: gone")))
            modes = _modes_in(path)
        self.assertEqual(applied, {"confinement": "audit"})
        self.assertEqual(modes["confinement"], "audit")
        self.assertIn("did not pass: jail: gone", out)

    def test_a_missing_config_follows_the_answer_too(self):
        # No config on disk yet: a pass leaves it missing, as the
        # Linux seed does; a refusal seeds the statement.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            applied, _out = self._apply(path, probe=_Probe())
            self.assertEqual(applied, {})
            self.assertFalse(os.path.exists(path))
            applied, _out = self._apply(
                path, probe=_Probe(problem=_ROOT_REASON))
            self.assertEqual(applied, {"confinement": "audit"})
            self.assertEqual(_modes_in(path),
                             {"confinement": "audit"})

    def test_the_seed_is_stable_under_a_second_asking(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            self._apply(path, probe=_Probe(problem=_ROOT_REASON))
            with open(path, "rb") as fh:
                before = fh.read()
            probe = _Probe()
            applied, _out = self._apply(path, probe=probe)
            with open(path, "rb") as fh:
                after = fh.read()
        # Stated at audit by the first install: that is now the
        # file's word, and a second pass neither asks nor moves it.
        self.assertEqual(applied, {})
        self.assertEqual(before, after)
        self.assertEqual(probe.asked, [])

    def test_a_later_run_over_enforce_asks_again(self):
        # The installer takes one path on FreeBSD for a first
        # install and a later run: a config the seed left at
        # enforce is asked again, stays where the probe passes,
        # and is stated down, with the reason, where it does not.
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            first, second = _Probe(), _Probe()
            self._apply(path, probe=first)
            with open(path, "rb") as fh:
                before = fh.read()
            applied, out = self._apply(path, probe=second)
            with open(path, "rb") as fh:
                after = fh.read()
            self.assertEqual((len(first.asked), len(second.asked)),
                             (1, 1))
            self.assertEqual(applied, {})
            self.assertEqual(before, after)
            self.assertIn("left at enforce", out)
            applied, out = self._apply(
                path, probe=_Probe(problem="jail(8) is gone"))
            self.assertEqual(applied, {"confinement": "audit"})
            self.assertEqual(_modes_in(path)["confinement"], "audit")
            self.assertIn("did not pass: jail(8) is gone", out)

    # --- the setup wizard's seed -------------------------------

    def test_the_wizard_s_seed_takes_the_same_answer(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        answers = []
        stated = SU.seed_platform_modes(
            cfg, "freebsd14", probe=_Probe(), asked=answers)
        self.assertEqual(stated, {})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "enforce")
        self.assertEqual(answers, [(None, _PASS_LINES)])
        answers = []
        stated = SU.seed_platform_modes(
            cfg, "freebsd14", probe=_Probe(problem=_ROOT_REASON),
            asked=answers)
        self.assertEqual(stated, {"confinement": "audit"})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        self.assertEqual(answers, [(_ROOT_REASON, ())])

    def _fresh_wizard(self, statement):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            out = io.StringIO()
            with mock.patch.object(SU, "_fresh_platform_modes",
                                   return_value=statement), \
                 mock.patch("builtins.input", side_effect=[
                     "runner@example.com", "", "my-client-id", "y"]), \
                 mock.patch.object(SU, "browser_consent",
                                   return_value="refresh-123"), \
                 mock.patch.object(SU, "_mailbox_probe",
                                   return_value=None), \
                 redirect_stdout(out):
                SU.run_setup_wizard(path)
            return _modes_in(path), out.getvalue(), path

    def test_the_wizard_says_the_jail_stays_on(self):
        modes, out, path = self._fresh_wizard(
            ({}, (None, _PASS_LINES)))
        self.assertEqual(modes["confinement"], "enforce")
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, out)
        self.assertIn("platform: " + _PASS_LINES[0], out)
        self.assertNotIn("stated as audit", out)

    def test_the_wizard_says_why_the_jail_is_stated_down(self):
        modes, out, path = self._fresh_wizard(
            ({"confinement": "audit"}, (_ROOT_REASON, ())))
        self.assertEqual(modes["confinement"], "audit")
        self.assertIn("security.modes.confinement stated as audit "
                      "in %s" % path, out)
        self.assertIn("did not pass: " + _ROOT_REASON, out)
        self.assertNotIn("cannot engage on", out)

    # --- the question itself -----------------------------------

    def _ask(self, backend, cfg=None):
        with mock.patch.object(INS, "_import_freebsd_confine",
                               return_value=backend):
            return INS.freebsd_seed_probe(cfg or {})

    def _scripted(self, problem=None, lines=None, real=True):
        backend = types.SimpleNamespace(IS_FREEBSD_BACKEND=real)
        backend.asked = []

        def _probe(cfg=None, timeout=15):
            backend.asked.append(cfg)
            if isinstance(problem, Exception):
                raise problem
            return problem

        def _posture(cfg=None):
            if isinstance(lines, Exception):
                raise lines
            return list(lines or [("OK", _PASS_LINES[0])])

        backend.freebsd_confinement_problem = _probe
        backend.posture_lines = _posture
        return backend

    def test_the_question_is_the_startup_gate_s_own(self):
        cfg = {"security": {"confinement": {"work_mount": "/job"}}}
        backend = self._scripted(
            lines=[("OK", _PASS_LINES[0]), ("OK", _PASS_LINES[1])])
        self.assertEqual(self._ask(backend, cfg), (None, _PASS_LINES))
        self.assertEqual(backend.asked, [cfg])

    def test_the_backend_s_reason_comes_back_in_its_own_words(self):
        backend = self._scripted(problem=_ROOT_REASON)
        self.assertEqual(self._ask(backend), (_ROOT_REASON, ()))

    def test_a_backend_that_is_not_there_is_a_reason(self):
        for backend in (None, self._scripted(real=False)):
            problem, lines = self._ask(backend)
            self.assertIn("could not be loaded", problem)
            self.assertEqual(lines, ())
        self.assertEqual(self._scripted(real=False).asked, [])

    def test_a_backend_that_raises_is_a_reason(self):
        problem, lines = self._ask(
            self._scripted(problem=RuntimeError("no jls")))
        self.assertEqual(problem,
                         "the jail backend could not answer: no jls")
        self.assertEqual(lines, ())

    def test_a_pass_stands_when_the_posture_lines_cannot_be_read(self):
        backend = self._scripted(lines=RuntimeError("no sysctl"))
        self.assertEqual(self._ask(backend), (None, ()))

    # --- reaching the backend ----------------------------------

    def test_the_packaged_installer_reaches_this_backend(self):
        self.assertIs(INS._import_freebsd_confine(), FC)

    def test_a_frozen_installer_does_not_reach_for_it(self):
        with mock.patch.object(INS.sys, "_MEIPASS", "/frozen",
                               create=True):
            self.assertIsNone(INS._import_freebsd_confine())

    def test_the_installer_started_by_path_reaches_the_backend(self):
        # `python3 runner/ops/install.py` from a source tree: no
        # package, no install layout on the import path. The
        # backend and its sibling are reached through the tree's
        # guard directory alone: the import path is left as it
        # was found, the runner itself is not pulled in, and
        # once the question has been asked nothing stays loaded.
        driver = (
            "import json, runpy, sys\n"
            "def loaded():\n"
            "    return sorted(m for m in sys.modules\n"
            "                  if m.split('.')[0] == 'guard')\n"
            "before = list(sys.path)\n"
            "ns = runpy.run_path(sys.argv[1], "
            "run_name='hp_install_by_path')\n"
            "mod = ns['_import_freebsd_confine']()\n"
            "held = loaded()\n"
            "block = {'security': {'confinement': {\n"
            "    'freebsd': {'loopback': True}}}}\n"
            "reached = mod.confinement_settings(block)['loopback']\n"
            "ns['_release_freebsd_confine']()\n"
            "released = loaded()\n"
            "answer = ns['freebsd_seed_probe'](block)\n"
            "applied = ns['apply_platform_modes'](\n"
            "    sys.argv[2], 'freebsd14',\n"
            "    probe=lambda cfg: (None, ('carried',)))\n"
            "print(json.dumps({\n"
            "    'probe': hasattr(mod, 'freebsd_confinement_problem'),\n"
            "    'posture': hasattr(mod, 'posture_lines'),\n"
            "    'file': getattr(mod, '__file__', ''),\n"
            "    'held': held, 'released': released,\n"
            "    'reached_back': reached,\n"
            "    'answered': isinstance(answer, tuple)\n"
            "                and len(answer) == 2,\n"
            "    'after_asking': loaded(),\n"
            "    'path_restored': sys.path == before,\n"
            "    'pulled_in': sorted(\n"
            "        m for m in ('runner', 'ops', 'ops.install')\n"
            "        if m in sys.modules),\n"
            "    'applied': applied}))\n")
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            done = subprocess.run(
                [sys.executable, "-I", "-c", driver, _INSTALL_PY,
                 path],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=120, cwd=d)
            modes = _modes_in(path)
        self.assertEqual(done.returncode, 0,
                         done.stderr.decode("utf-8", "replace"))
        lines = done.stdout.decode("utf-8", "replace").splitlines()
        said = json.loads(lines[-1])
        self.assertTrue(said["probe"] and said["posture"], said)

        def same(path):
            return os.path.normcase(os.path.realpath(path))
        self.assertEqual(same(said["file"]),
                         same(os.path.join(_REPO, "runner", "guard",
                                           "freebsd_confine.py")))
        self.assertEqual(said["held"], [
            "guard", "guard.freebsd_confine", "guard.sandbox"], said)
        # A config with a freebsd block of its own is read while
        # the backend is held: the sibling reaching back for the
        # backend finds it.
        self.assertIs(said["reached_back"], True, said)
        self.assertEqual(said["released"], [], said)
        # The question itself, by path: an answer came back and
        # nothing stayed loaded.
        self.assertTrue(said["answered"], said)
        self.assertEqual(said["after_asking"], [], said)
        self.assertTrue(said["path_restored"], said)
        self.assertEqual(said["pulled_in"], [], said)
        self.assertEqual(said["applied"], {})
        self.assertEqual(modes["confinement"], "enforce")
        self.assertIn("left at enforce", lines[0])
        self.assertEqual(lines[1], "platform: carried")

    def test_the_release_takes_out_only_what_the_seed_loaded(self):
        # A `guard` some other import put there is not the
        # seed's to unload.
        other = types.ModuleType("guard")
        with mock.patch.dict(sys.modules, {"guard": other}):
            INS._release_freebsd_confine()
            self.assertIs(sys.modules.get("guard"), other)
            setattr(other, INS._BY_PATH_MARK, True)
            INS._release_freebsd_confine()
            self.assertNotIn("guard", sys.modules)


class FakeProcess:
    """What the fake host hands back for a started process."""

    def __init__(self, pid=31337):
        self.pid = pid
        self.returncode = None
        self.killed = False
        self.waited = False

    def communicate(self, timeout=None):
        self.returncode = 0
        return b"out", b"err"

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.waited = True
        self.returncode = 0
        return 0


class FakeHost:
    """A FreeBSD host that exists only as its own record.

    It keeps a mount table, a set of jails and a list of rctl
    rules, and answers the backend's commands from them, so a
    test reads the state the backend left as well as the
    commands it sent. The trial inside a jail answers from that
    same state: a jail that kept the super-user reports the
    privilege, a root that was not mounted read-only reports
    the write, a /dev without the jail ruleset reports the
    host's devices.
    """

    def __init__(self, folder, racct=False, vimage=True, euid=0,
                 pid=4242):
        self.folder = folder
        self.racct = racct
        self.vimage = vimage
        self._euid = euid
        self._pid = pid
        self.calls = []
        self.popens = []
        self.table = []     # (source, point, fstype, options)
        self.jails = {}     # name -> {"path", "params", "suser", "lo"}
        self.rules = []
        self.alive = {pid}
        self.missing = set()
        self.devices = {}
        self.refuse = {}    # (tool, argument) -> (rc, out, err)
        self.refuse_if = []  # (predicate over argv, answer)
        self.busy = {}      # point -> busy answers still to give
        self.stuck = set()  # points that never unmount
        self.trial_out = None
        self.slept = 0.0
        self.reaper_fds = []
        self.popen_error = None

    # -- the facts ------------------------------------------
    def euid(self):
        return self._euid

    def pid(self):
        return self._pid

    def executable(self, path):
        return path not in self.missing

    def is_dir(self, path):
        return path not in self.missing

    def device(self, path):
        return self.devices.get(path, 1)

    def which(self, name):
        return {"sh": "/bin/sh",
                "python3": "/usr/local/bin/python3"}.get(name)

    def pid_alive(self, pid):
        return pid in self.alive

    def sleep(self, seconds):
        self.slept += seconds

    def temp_folder(self):
        return self.folder

    # -- the commands ---------------------------------------
    def mounted(self):
        return [point for _src, point, _type, _opts in self.table]

    def ran(self, tool, *words):
        """The calls of one tool whose argv holds every word as
        a whole argument."""
        return [c for c in self.calls if c[0] == tool
                and all(w in c for w in words)]

    def run(self, argv, timeout=30):
        argv = list(argv)
        self.calls.append(argv)
        for (tool, word), answer in self.refuse.items():
            if argv[0] == tool and word in argv:
                return answer
        for predicate, answer in self.refuse_if:
            if predicate(argv):
                return answer
        tool = argv[0]
        if tool == FC.MOUNT_BIN:
            if argv[1:] == ["-p"]:
                return (0, "".join(
                    "%s\t%s %s\t%s\t0 0\n" % (src, point, fstype, opts)
                    for src, point, fstype, opts in self.table), "")
            self.table.append((argv[-2], argv[-1], argv[2], argv[4]))
            return (0, "", "")
        if tool == FC.UMOUNT_BIN:
            point = argv[-1]
            if point in self.stuck:
                return (1, "", "umount: %s: Device busy" % point)
            if "-f" not in argv and self.busy.get(point, 0) > 0:
                self.busy[point] -= 1
                return (1, "", "umount: %s: Device busy" % point)
            if point not in self.mounted():
                return (1, "", "umount: %s: not a file system root "
                        "directory" % point)
            self.table = [row for row in self.table if row[1] != point]
            return (0, "", "")
        if tool == FC.JAIL_BIN:
            params = dict(p.split("=", 1) for p in argv[2:] if "=" in p)
            if argv[1] == "-c":
                self.jails[params["name"]] = {
                    "path": params["path"], "params": argv[2:],
                    "suser": "allow.nosuser" not in argv,
                    "lo": False}
                return (0, "", "")
            if argv[1] == "-m":
                if "allow.nosuser" in argv:
                    self.jails[params["name"]]["suser"] = False
                return (0, "", "")
            if argv[1] == "-r":
                if argv[2] in self.jails:
                    del self.jails[argv[2]]
                    return (0, "", "")
                return (1, "", 'jail: jail "%s" not found' % argv[2])
        if tool == FC.JLS_BIN:
            if argv[1] == "-j":
                return (0 if argv[2] in self.jails else 1, "", "")
            if argv[1] == "name":
                return (0, "".join(n + "\n" for n in self.jails), "")
            if argv[1] == "path":
                return (0, "".join(j["path"] + "\n"
                                   for j in self.jails.values()), "")
        if tool == FC.RCTL_BIN:
            if not self.racct:
                return (1, "", "rctl: RACCT/RCTL present, but disabled; "
                        "enable using kern.racct.enable=1 tunable")
            if argv[1:2] == ["-a"]:
                self.rules.append(argv[2])
                return (0, "", "")
            if argv[1:2] == ["-r"]:
                self.rules = [r for r in self.rules
                              if not r.startswith(argv[2] + ":")]
                return (0, "", "")
            shown = [r for r in self.rules
                     if len(argv) == 1 or r.startswith(argv[1] + ":")]
            return (0, "".join(r + "\n" for r in shown), "")
        if tool == FC.SYSCTL_BIN:
            if argv[-1] == "kern.racct.enable":
                return (0, "1\n" if self.racct else "0\n", "")
            if argv[-1] == "kern.features.vimage":
                return (0, "1\n", "") if self.vimage else (
                    1, "", "sysctl: unknown oid")
        if tool == FC.JEXEC_BIN:
            name = [a for a in argv[1:] if a in self.jails]
            jail = self.jails[name[0]] if name else None
            if FC.IFCONFIG_BIN in argv:
                if jail is None:
                    return (1, "", "jexec: jail not found")
                if "up" in argv:
                    jail["lo"] = True
                    return (0, "", "")
                return (0, "lo0: flags=8049<UP,LOOPBACK,RUNNING>\n"
                        + ("\tinet 127.0.0.1 netmask 0xff000000\n"
                           if jail["lo"] else ""), "")
            if FC.TRIAL_SCRIPT in argv:
                if self.trial_out is not None:
                    return (0, self.trial_out, "")
                if jail is None:
                    return (1, "", "jexec: jail not found")
                return (0, self._trial(jail), "")
        raise AssertionError("the fake host has no answer for %r" % argv)

    def _trial(self, jail):
        rows = {point: (fstype, opts)
                for _src, point, fstype, opts in self.table}
        root = jail["path"]
        words = ["trial", "WORK-OK", "TMP-OK"]
        if "ro" not in rows.get(root, ("", ""))[1].split(","):
            words.append("ROOT-WRITABLE")
        if jail["suser"]:
            words.append("PRIVILEGED")
        words.append("NULL-OK")
        if "ruleset=4" not in rows.get(root + "/dev", ("", ""))[1]:
            words.append("DEVICES-EXPOSED")
        words.append("END")
        return "\n".join(words) + "\n"

    def popen(self, argv, **kwargs):
        argv = list(argv)
        if not [a for a in argv if a in self.jails]:
            raise AssertionError(
                "a process was started with no jail standing: %r"
                % argv)
        if self.popen_error is not None and argv[0] == FC.JEXEC_BIN:
            raise self.popen_error
        self.popens.append((argv, kwargs))
        if argv[0] == FC.SH_BIN and FC.REAPER_SCRIPT in argv:
            # The backend closes its copy of the read end; keep
            # one, to read what the release wrote.
            self.reaper_fds.append(os.dup(kwargs["stdin"]))
            return FakeProcess(pid=27000 + len(self.reaper_fds))
        return FakeProcess()

    def close(self):
        for fd in self.reaper_fds:
            try:
                os.close(fd)
            except OSError:
                pass


class _FakeHostCase(unittest.TestCase):
    """A temporary folder, a fake host standing on it, and the
    probe's process-wide memory cleared before and after."""

    racct = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = os.path.realpath(self.tmp.name)
        self.host = FakeHost(self.folder, racct=self.racct)
        self.addCleanup(self.host.close)
        self._forget()
        self.addCleanup(self._forget)
        self.work = os.path.join(self.folder, "job-work")
        os.mkdir(self.work)

    def _forget(self):
        FC._trial_passed.clear()
        del FC._swept[:]

    def skeletons(self):
        return sorted(n for n in os.listdir(self.folder)
                      if n.startswith(FC.SKELETON_PREFIX))

    def root(self):
        """The jail root of the one skeleton standing."""
        (base,) = self.skeletons()
        return os.path.join(self.folder, base) + "/root"

    def skel(self):
        (base,) = self.skeletons()
        return os.path.join(self.folder, base) + "/skel"

    def spawn(self, argv=("/bin/sh", "-c", "true"), cfg=None,
              user=None, **kw):
        return FC._spawn(list(argv), cwd=self.work, env={},
                         user=user, cfg=cfg, host=self.host, **kw)

    def job_command(self):
        return [argv for argv, _kw in self.host.popens
                if argv[0] == FC.JEXEC_BIN][-1]


def _fcfg(**freebsd):
    return {"security": {"confinement": {"freebsd": freebsd}}}


class SettingsTest(unittest.TestCase):
    """What a jail is built from, read out of the config."""

    def test_an_empty_config_reads_the_defaults(self):
        st = FC.confinement_settings({})
        self.assertEqual(st["work_mount"], "/work")
        self.assertEqual(st["extra_ro_binds"], [])
        self.assertIs(st["loopback"], False)
        self.assertEqual(st["process_memory_bytes"], 512 * 1024 * 1024)
        self.assertEqual(st["tmp_bytes"], 512 * 1024 * 1024)
        self.assertIsNone(st["job_memory_bytes"])
        self.assertIsNone(st["job_processes"])
        for cfg in (None, [], {"security": None},
                    {"security": {"confinement": None}}):
            self.assertEqual(FC.confinement_settings(cfg), st, cfg)

    def test_the_freebsd_block_is_read(self):
        st = FC.confinement_settings(_fcfg(
            loopback=True, process_memory_bytes=1 << 30,
            tmp_bytes=1 << 20, job_memory_bytes=1 << 31,
            job_processes=32))
        self.assertIs(st["loopback"], True)
        self.assertEqual(st["process_memory_bytes"], 1 << 30)
        self.assertEqual(st["tmp_bytes"], 1 << 20)
        self.assertEqual(st["job_memory_bytes"], 1 << 31)
        self.assertEqual(st["job_processes"], 32)

    def test_a_malformed_freebsd_block_is_a_config_error(self):
        bad = ([], "x", 3,
               {"lopback": True},
               {"loopback": "yes"}, {"loopback": 1},
               {"job_processes": 0}, {"job_processes": -4},
               {"job_processes": True}, {"job_processes": "64"},
               {"tmp_bytes": 1.5}, {"process_memory_bytes": None},
               {"job_memory_bytes": [1]})
        for block in bad:
            with self.subTest(block=block):
                with self.assertRaises(RuntimeError) as caught:
                    FC.validate_freebsd_block(block)
                self.assertIn("security.confinement.freebsd",
                              str(caught.exception))

    def test_an_unknown_setting_is_named(self):
        with self.assertRaises(RuntimeError) as caught:
            FC.validate_freebsd_block({"job_proceses": 64})
        self.assertIn("job_proceses", str(caught.exception))
        self.assertIn("job_processes", str(caught.exception))

    def test_the_security_validator_reads_the_block_everywhere(self):
        # The schema is checked on every platform: a config is
        # right or wrong the same way wherever it is read.
        from runner.guard import security as S
        S.validate_security_config(_fcfg(job_processes=64))
        with self.assertRaises(RuntimeError) as caught:
            S.validate_security_config(_fcfg(job_processes=0))
        self.assertIn("security.confinement.freebsd.job_processes",
                      str(caught.exception))

    def test_bwrap_flags_are_refused_by_name(self):
        cfg = {"security": {"confinement": {
            "extra_flags": ["--unshare-pid"]}}}
        with self.assertRaises(RuntimeError) as caught:
            FC.confinement_settings(cfg)
        self.assertIn("--unshare-pid", str(caught.exception))
        self.assertIn("bwrap", str(caught.exception))

    def test_the_work_mount_is_a_directory_of_its_own(self):
        for mount in ("/job", "/srv/job/work", "/work/"):
            st = FC.confinement_settings(
                {"security": {"confinement": {"work_mount": mount}}})
            self.assertEqual(st["work_mount"], mount.rstrip("/"))
        for mount in ("/", "/usr", "/usr/local/work", "/tmp",
                      "/tmp/work", "/dev", "/etc", "/var/run", "/bin"):
            with self.subTest(mount=mount):
                with self.assertRaises(RuntimeError) as caught:
                    FC.confinement_settings({"security": {
                        "confinement": {"work_mount": mount}}})
                self.assertIn("work_mount", str(caught.exception))

    def test_a_bind_may_not_land_on_a_writable_tree_or_the_root(self):
        ok = FC.confinement_settings({"security": {"confinement": {
            "extra_ro_binds": [["/opt/data", "/data/"],
                               ["/srv/x", "/etc/x"]]}}})
        self.assertEqual(ok["extra_ro_binds"],
                         [("/opt/data", "/data"), ("/srv/x", "/etc/x")])
        for dst in ("/", "/tmp", "/tmp/in", "/dev", "/work",
                    "/work/in"):
            with self.subTest(dst=dst):
                with self.assertRaises(RuntimeError) as caught:
                    FC.confinement_settings({"security": {
                        "confinement": {
                            "extra_ro_binds": [["/opt/data", dst]]}}})
                self.assertIn("extra_ro_binds", str(caught.exception))
        with self.assertRaises(RuntimeError):
            FC.confinement_settings({"security": {"confinement": {
                "work_mount": "/data/job",
                "extra_ro_binds": [["/opt/data", "/data"]]}}})

    def test_the_shared_keys_keep_the_sandbox_s_own_refusals(self):
        for conf in ({"work_mount": "work"},
                     {"work_mount": "/a/../b"},
                     {"extra_ro_binds": [["/a"]]},
                     {"extra_ro_binds": "x"},
                     {"extra_flags": "x"}):
            with self.subTest(conf=conf):
                with self.assertRaises(RuntimeError):
                    FC.confinement_settings(
                        {"security": {"confinement": conf}})


class StatusTest(unittest.TestCase):
    """The record's string names exactly the controls applied."""

    def test_the_floor_is_the_floor_s_three_names(self):
        self.assertEqual(
            FC.confinement_status(FC.CONFINEMENT_CONTROLS),
            FC.STATUS_CONFINEMENT)
        self.assertEqual(
            FC.STATUS_CONFINEMENT,
            "freebsd: jail + no_network + spawn_resource_limits")

    def test_the_names_keep_one_order(self):
        self.assertEqual(
            FC.confinement_status(
                ["spawn_resource_limits", "rctl_resource_limits",
                 "no_superuser", "no_network", "jail"]),
            "freebsd: jail + no_network + no_superuser + "
            "rctl_resource_limits + spawn_resource_limits")
        self.assertEqual(
            FC.confinement_status(
                ["jail", "private_loopback", "spawn_resource_limits"]),
            "freebsd: jail + private_loopback + spawn_resource_limits")

    def test_a_name_the_backend_does_not_know_is_an_error(self):
        with self.assertRaises(RuntimeError):
            FC.confinement_status(["jail", "capsicum"])

    def test_no_name_claims_what_the_backend_does_not_do(self):
        for name in FC.CONTROL_ORDER:
            self.assertNotIn("capsicum", name)
            self.assertNotIn("sandbox", name)


class PlanTest(unittest.TestCase):
    """The commands one jail is made of, as pure text."""

    def setUp(self):
        self.st = FC.confinement_settings({})

    def test_the_root_is_first_and_read_only(self):
        plan = FC.mount_plan("/b/skel", "/b/root", "/w", self.st)
        first = plan[0]
        self.assertEqual(first["kind"], "root")
        self.assertEqual(
            first["argv"],
            [FC.MOUNT_BIN, "-t", "nullfs", "-o", "ro,nosuid",
             "/b/skel", "/b/root"])

    def test_every_mount_is_nosuid_and_one_host_tree_is_writable(self):
        plan = FC.mount_plan("/b/skel", "/b/root", "/w", self.st)
        writable = []
        for entry in plan:
            options = entry["argv"][4].split(",")
            if entry["kind"] != "dev":
                self.assertIn("nosuid", options, entry)
            if entry["argv"][2] == "nullfs" and "ro" not in options:
                writable.append(entry["argv"][-2:])
        self.assertEqual(writable, [["/w", "/b/root/work"]])

    def test_the_host_trees_mirror_their_own_paths(self):
        plan = FC.mount_plan("/b/skel", "/b/root", "/w", self.st)
        mirrors = [(e["mirror"], e["point"]) for e in plan
                   if e["kind"] == "ro"]
        self.assertEqual(
            mirrors, [(t, "/b/root" + t) for t in FC.RO_MOUNTS])

    def test_the_scratch_tree_is_bounded_and_dev_is_the_jail_ruleset(self):
        st = FC.confinement_settings(_fcfg(tmp_bytes=4096))
        plan = FC.mount_plan("/b/skel", "/b/root", "/w", st)
        tmp = [e for e in plan if e["kind"] == "tmp"][0]
        self.assertEqual(
            tmp["argv"],
            [FC.MOUNT_BIN, "-t", "tmpfs", "-o",
             "nosuid,size=4096,mode=1777", "tmpfs", "/b/root/tmp"])
        dev = [e for e in plan if e["kind"] == "dev"][0]
        self.assertEqual(
            dev["argv"],
            [FC.MOUNT_BIN, "-t", "devfs", "-o", "ruleset=4", "devfs",
             "/b/root/dev"])

    def test_binds_and_prefixes_are_read_only_and_the_work_is_last(self):
        st = FC.confinement_settings({"security": {"confinement": {
            "work_mount": "/job",
            "extra_ro_binds": [["/opt/data", "/data"]]}}})
        plan = FC.mount_plan("/b/skel", "/b/root", "/w", st,
                             prefixes=["/opt/py"])
        kinds = [e["kind"] for e in plan]
        self.assertEqual(kinds[-1], "work")
        self.assertEqual(plan[-1]["point"], "/b/root/job")
        bind = [e for e in plan if e["kind"] == "bind"][0]
        self.assertEqual(bind["argv"][4:], ["ro,nosuid", "/opt/data",
                                            "/b/root/data"])
        self.assertNotIn("mirror", bind)
        prefix = [e for e in plan if e["kind"] == "prefix"][0]
        self.assertEqual(prefix["argv"][4:], ["ro,nosuid", "/opt/py",
                                              "/b/root/opt/py"])
        self.assertEqual(prefix["mirror"], "/opt/py")

    def test_a_trial_s_work_mount_is_a_small_tmpfs(self):
        plan = FC.mount_plan("/b/skel", "/b/root", None, self.st)
        self.assertEqual(plan[-1]["argv"][2], "tmpfs")
        self.assertEqual(plan[-1]["point"], "/b/root/work")

    def test_the_jail_has_no_network_and_mounts_no_devfs_of_its_own(self):
        argv = FC.jail_parameters("hpjob7x1", "/b/root")
        self.assertEqual(argv[:2], [FC.JAIL_BIN, "-c"])
        self.assertIn("name=hpjob7x1", argv)
        self.assertIn("path=/b/root", argv)
        self.assertIn("ip4=disable", argv)
        self.assertIn("ip6=disable", argv)
        self.assertIn("persist=true", argv)
        self.assertNotIn("mount.devfs", argv)
        self.assertNotIn("allow.nosuser", argv)
        self.assertFalse([a for a in argv if a.startswith("vnet")])

    def test_the_jail_s_other_shapes(self):
        argv = FC.jail_parameters("hpjob7x1", "/b/root",
                                  superuser=False)
        self.assertIn("allow.nosuser", argv)
        argv = FC.jail_parameters("hpjob7x1", "/b/root", loopback=True)
        self.assertIn("vnet=new", argv)
        self.assertNotIn("ip4=disable", argv)
        self.assertNotIn("ip6=disable", argv)

    def test_the_rules_hold_the_jail_as_a_whole(self):
        self.assertEqual(
            FC.rctl_rules("hpjob7x1", self.st),
            ["jail:hpjob7x1:maxproc:deny=256",
             "jail:hpjob7x1:vmemoryuse:deny=2147483648"])
        st = FC.confinement_settings(_fcfg(
            job_processes=12, job_memory_bytes=4096))
        self.assertEqual(
            FC.rctl_rules("hpjob7x1", st),
            ["jail:hpjob7x1:maxproc:deny=12",
             "jail:hpjob7x1:vmemoryuse:deny=4096"])

    def test_a_jail_name_carries_its_runner(self):
        name = FC.jail_name("job", 4242)
        match = FC._JAIL_NAME.match(name)
        self.assertTrue(match, name)
        self.assertEqual(match.group(2), "4242")
        self.assertTrue(name.isalnum())
        self.assertNotEqual(name, FC.jail_name("job", 4242))


class TranslateTest(unittest.TestCase):
    """A host command becomes the command that runs in-jail."""

    def setUp(self):
        self.st = FC.confinement_settings({})
        self.which = {"sh": "/bin/sh",
                      "python3": "/usr/local/bin/python3"}.get

    def test_a_bare_name_is_resolved_and_the_work_tree_is_moved(self):
        out, prefixes = FC.translate_argv(
            ["sh", "/w/job/s.sh", "/w/job", "/w/jobs/x", "plain"],
            "/w/job", self.st, which=self.which)
        self.assertEqual(
            out, ["/bin/sh", "/work/s.sh", "/work", "/w/jobs/x",
                  "plain"])
        self.assertEqual(prefixes, [])

    def test_the_work_mount_is_the_config_s(self):
        st = FC.confinement_settings(
            {"security": {"confinement": {"work_mount": "/job"}}})
        out, _prefixes = FC.translate_argv(
            ["/bin/sh", "/w/s.sh"], "/w", st, which=self.which)
        self.assertEqual(out, ["/bin/sh", "/job/s.sh"])

    def test_an_interpreter_outside_the_trees_brings_its_prefix(self):
        notes = []
        out, prefixes = FC.translate_argv(
            ["/opt/py311/bin/python3", "/w/s.py"], "/w", self.st,
            which=self.which, notes=notes)
        self.assertEqual(out, ["/opt/py311/bin/python3", "/work/s.py"])
        self.assertEqual(prefixes, ["/opt/py311"])
        self.assertEqual(
            notes, ["interpreter prefix /opt/py311 mounted read-only"])

    def test_an_interpreter_under_an_operator_bind_needs_nothing(self):
        st = FC.confinement_settings({"security": {"confinement": {
            "extra_ro_binds": [["/srv/tools", "/opt/tools"]]}}})
        out, prefixes = FC.translate_argv(
            ["/opt/tools/bin/run"], None, st, which=self.which)
        self.assertEqual(out, ["/opt/tools/bin/run"])
        self.assertEqual(prefixes, [])

    def test_a_link_out_of_a_mounted_tree_brings_its_target(self):
        # /usr/local/bin/python3 is visible, and here it is a
        # link to an interpreter under /srv: the target's prefix
        # is mounted too, as the Linux sandbox binds it.
        def _real(path):
            if path == "/usr/local/bin/python3":
                return "/srv/py311/bin/python3"
            return path
        notes = []
        with mock.patch.object(FC._sandbox.os.path, "realpath", _real):
            out, prefixes = FC.translate_argv(
                ["python3"], None, self.st, which=self.which,
                notes=notes)
        self.assertEqual(out, ["/usr/local/bin/python3"])
        self.assertEqual(prefixes, ["/srv/py311"])
        self.assertEqual(
            notes, ["interpreter prefix /srv/py311 mounted read-only"])

    def test_a_prefix_the_jail_replaces_is_refused(self):
        st = FC.confinement_settings(
            {"security": {"confinement": {"work_mount": "/job"}}})
        for path in ("/tmp/toolchain/bin/python3",
                     "/dev/tools/bin/python3",
                     "/job/venv/bin/python3"):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError) as caught:
                    FC.translate_argv([path], None, st,
                                      which=self.which)
                self.assertIn("would not exist inside the jail",
                              str(caught.exception))

    def test_a_home_and_a_shallow_tree_are_never_mounted(self):
        for path in ("/python3", "/opt/python3",
                     "/home/someone/python3", "/root/python3"):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError) as caught:
                    FC.translate_argv([path], None, self.st,
                                      which=self.which)
                self.assertIn("would not exist inside the jail",
                              str(caught.exception))
        # A bin directory inside a home is mounted, never the
        # home: the rule the Linux sandbox applies.
        _out, prefixes = FC.translate_argv(
            ["/home/someone/bin/python3"], None, self.st,
            which=self.which)
        self.assertEqual(prefixes, ["/home/someone/bin"])

    def test_what_is_not_a_command_is_refused(self):
        for argv in ((), [], None, "sh", ["sh", 3], [b"sh"]):
            with self.subTest(argv=argv):
                with self.assertRaises(RuntimeError):
                    FC.translate_argv(argv, None, self.st,
                                      which=self.which)
        with self.assertRaises(RuntimeError) as caught:
            FC.translate_argv(["nosuchtool"], None, self.st,
                              which=self.which)
        self.assertIn("cannot resolve interpreter", str(caught.exception))


class ControlsTest(_FakeHostCase):
    """Which controls a job on this host gets, and when the
    config asks for one the host cannot hold."""

    def controls(self, cfg=None, user=None):
        return FC.controls_for(
            self.host, FC.confinement_settings(cfg), user)

    def test_the_default_on_a_host_without_racct(self):
        controls, rctl = self.controls()
        self.assertEqual(controls, ["jail", "no_network",
                                    "no_superuser",
                                    "spawn_resource_limits"])
        self.assertFalse(rctl)

    def test_a_job_user_is_not_named_as_no_superuser(self):
        controls, _rctl = self.controls(user="pigeon-jobs")
        self.assertEqual(controls, list(FC.CONFINEMENT_CONTROLS))

    def test_racct_names_the_rules(self):
        self.host.racct = True
        controls, rctl = self.controls()
        self.assertIn("rctl_resource_limits", controls)
        self.assertTrue(rctl)

    def test_a_ceiling_the_operator_wrote_must_engage_or_refuse(self):
        for block in ({"job_processes": 64},
                      {"job_memory_bytes": 1 << 30}):
            with self.subTest(block=block):
                with self.assertRaises(RuntimeError) as caught:
                    self.controls(_fcfg(**block))
                text = str(caught.exception)
                self.assertIn("kern.racct.enable=1", text)
                self.assertIn("/boot/loader.conf", text)
        self.host.racct = True
        controls, rctl = self.controls(_fcfg(job_processes=64))
        self.assertTrue(rctl)

    def test_racct_without_the_tool_refuses(self):
        self.host.racct = True
        self.host.missing.add(FC.RCTL_BIN)
        with self.assertRaises(RuntimeError) as caught:
            self.controls()
        self.assertIn(FC.RCTL_BIN, str(caught.exception))

    def test_a_loopback_needs_vimage(self):
        controls, _rctl = self.controls(_fcfg(loopback=True))
        self.assertIn("private_loopback", controls)
        self.assertNotIn("no_network", controls)
        self.host.vimage = False
        with self.assertRaises(RuntimeError) as caught:
            self.controls(_fcfg(loopback=True))
        self.assertIn("VIMAGE", str(caught.exception))


class SpawnTest(_FakeHostCase):
    """One job's jail, built and released against the fake host."""

    def test_the_default_job(self):
        proc = self.spawn(["sh", self.work + "/s.sh", "a"])
        self.assertEqual(
            proc.confinement_status,
            "freebsd: jail + no_network + no_superuser + "
            "spawn_resource_limits")
        self.assertEqual(proc.confinement_notes, [])
        self.assertEqual(proc.pid, 31337)
        (name, jail), = self.host.jails.items()
        self.assertTrue(FC._JAIL_NAME.match(name), name)
        self.assertFalse(jail["suser"])
        self.assertIn("ip4=disable", jail["params"])
        root = self.root()
        self.assertEqual(jail["path"], root)
        # The mounts stand in plan order, the root first, and
        # /usr/local rides /usr's mount (one filesystem here).
        self.assertEqual(
            self.host.mounted(),
            [root, root + "/usr", root + "/bin", root + "/lib",
             root + "/libexec", root + "/sbin", root + "/tmp",
             root + "/dev", root + "/work"])
        self.assertEqual(
            self.job_command(),
            [FC.JEXEC_BIN, "-d", "/work", name, FC.LIMITS_BIN,
             "-v", "536870912", "-d", "536870912",
             "/bin/sh", "/work/s.sh", "a"])
        # (The fake host refuses to start a process that names
        # no standing jail: the jail stood before the job.)
        self.assertEqual(len(self.host.ran(FC.RCTL_BIN)), 0)
        proc.close()
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])
        self.assertTrue(os.path.isdir(self.work))

    def test_the_job_starts_in_its_own_session_with_the_scrubbed_env(self):
        self.spawn()
        argv, kw = [p for p in self.host.popens
                    if p[0][0] == FC.JEXEC_BIN][0]
        self.assertTrue(kw["start_new_session"])
        self.assertEqual(kw["stdin"], subprocess.DEVNULL)
        self.assertEqual(kw["stdout"], subprocess.PIPE)
        self.assertEqual(kw["stderr"], subprocess.PIPE)
        self.assertEqual(kw["env"], {"PATH": FC.JAIL_PATH})
        FC._spawn(["/bin/sh"], cwd=self.work,
                  env={"PATH": "/x", "A": "b"}, host=self.host)
        self.assertEqual(self.host.popens[-1][1]["env"],
                         {"PATH": "/x", "A": "b"})

    def test_a_job_user_goes_in_at_the_door(self):
        proc = self.spawn(user="pigeon-jobs")
        self.assertEqual(proc.confinement_status, FC.STATUS_CONFINEMENT)
        (name, jail), = self.host.jails.items()
        # The door's demote needs the privilege; the user has
        # none once through it.
        self.assertTrue(jail["suser"])
        cmd = self.job_command()
        self.assertEqual(cmd[:6], [FC.JEXEC_BIN, "-d", "/work", "-u",
                                   "pigeon-jobs", name])

    def test_the_ceilings_are_the_config_s(self):
        self.spawn(cfg=_fcfg(process_memory_bytes=1 << 20))
        cmd = self.job_command()
        self.assertEqual(cmd[cmd.index(FC.LIMITS_BIN):][:5],
                         [FC.LIMITS_BIN, "-v", "1048576", "-d",
                          "1048576"])
        self.spawn(memory_bytes=4096)
        cmd = self.job_command()
        self.assertIn("4096", cmd)

    def test_the_work_mount_and_the_binds_are_the_config_s(self):
        cfg = {"security": {"confinement": {
            "work_mount": "/job",
            "extra_ro_binds": [["/opt/data", "/data"]]}}}
        self.spawn(["/bin/sh", self.work + "/s.sh"], cfg=cfg)
        root = self.root()
        self.assertIn(root + "/job", self.host.mounted())
        self.assertIn(root + "/data", self.host.mounted())
        self.assertNotIn(root + "/work", self.host.mounted())
        row = [r for r in self.host.table if r[1] == root + "/data"][0]
        self.assertEqual((row[0], row[3]), ("/opt/data", "ro,nosuid"))
        cmd = self.job_command()
        self.assertEqual(cmd[1:3], ["-d", "/job"])
        self.assertEqual(cmd[-1], "/job/s.sh")
        # The mount points were made in the skeleton.
        self.assertTrue(os.path.isdir(self.skel() + "/job"))
        self.assertTrue(os.path.isdir(self.skel() + "/data"))

    def test_an_interpreter_s_prefix_is_mounted_and_noted(self):
        proc = self.spawn(["/opt/py311/bin/python3", "-c", "pass"])
        root = self.root()
        row = [r for r in self.host.table
               if r[1] == root + "/opt/py311"][0]
        self.assertEqual((row[0], row[3]), ("/opt/py311", "ro,nosuid"))
        self.assertEqual(
            proc.confinement_notes,
            ["interpreter prefix /opt/py311 mounted read-only"])

    def test_a_child_tree_on_its_own_filesystem_is_mounted(self):
        self.host.devices["/usr/local"] = 2
        self.spawn()
        root = self.root()
        self.assertIn(root + "/usr/local", self.host.mounted())

    def test_racct_writes_the_rules_before_the_job_and_removes_them(self):
        self.host.racct = True
        proc = self.spawn(cfg=_fcfg(job_processes=12))
        (name,) = self.host.jails
        self.assertEqual(
            self.host.rules,
            ["jail:%s:maxproc:deny=12" % name,
             "jail:%s:vmemoryuse:deny=2147483648" % name])
        self.assertEqual(
            proc.confinement_status,
            "freebsd: jail + no_network + no_superuser + "
            "rctl_resource_limits + spawn_resource_limits")
        proc.close()
        self.assertEqual(self.host.rules, [])
        self.assertEqual(self.host.jails, {})
        # The rules went while the jail's name still stood.
        calls = self.host.calls
        removed = calls.index([FC.RCTL_BIN, "-r", "jail:" + name])
        self.assertLess(removed, calls.index([FC.JAIL_BIN, "-r", name]))

    def test_a_private_loopback(self):
        proc = self.spawn(cfg=_fcfg(loopback=True))
        (name, jail), = self.host.jails.items()
        self.assertIn("vnet=new", jail["params"])
        self.assertNotIn("ip4=disable", jail["params"])
        self.assertTrue(jail["lo"])
        # Brought up with the privilege, which is then taken
        # away before the job exists.
        self.assertFalse(jail["suser"])
        calls = self.host.calls
        up = calls.index([FC.JEXEC_BIN, name, FC.IFCONFIG_BIN, "lo0",
                          "inet", "127.0.0.1/8", "up"])
        drop = calls.index([FC.JAIL_BIN, "-m", "name=" + name,
                            "allow.nosuser"])
        self.assertLess(up, drop)
        self.assertEqual(
            proc.confinement_status,
            "freebsd: jail + private_loopback + no_superuser + "
            "spawn_resource_limits")

    def test_a_loopback_under_a_job_user_keeps_the_door(self):
        proc = self.spawn(cfg=_fcfg(loopback=True), user="pigeon-jobs")
        (_name, jail), = self.host.jails.items()
        self.assertTrue(jail["lo"])
        self.assertTrue(jail["suser"])
        self.assertEqual(self.host.ran(FC.JAIL_BIN, "-m"), [])
        self.assertEqual(
            proc.confinement_status,
            "freebsd: jail + private_loopback + spawn_resource_limits")

    def _nothing_left(self):
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.host.rules, [])
        self.assertEqual(self.skeletons(), [])

    def test_a_mount_that_fails_refuses_and_leaves_nothing(self):
        self.host.refuse[(FC.MOUNT_BIN, "/libexec")] = (
            1, "", "mount_nullfs: Operation not permitted")
        with self.assertRaises(RuntimeError) as caught:
            self.spawn()
        self.assertIn("/libexec failed (exit 1)", str(caught.exception))
        self.assertIn("Operation not permitted", str(caught.exception))
        self.assertEqual(self.host.ran(FC.JAIL_BIN, "-c"), [])
        self.assertEqual(self.host.popens, [])
        self._nothing_left()

    def test_a_jail_that_cannot_be_made_refuses_and_leaves_nothing(self):
        self.host.refuse[(FC.JAIL_BIN, "-c")] = (
            1, "", "jail: unknown parameter: allow.suser")
        with self.assertRaises(RuntimeError) as caught:
            self.spawn()
        self.assertIn("jail -c failed (exit 1)", str(caught.exception))
        self.assertIn("allow.suser", str(caught.exception))
        self.assertEqual(self.host.popens, [])
        self._nothing_left()

    def test_a_rule_that_does_not_take_refuses_and_leaves_nothing(self):
        self.host.racct = True
        self.host.refuse_if.append((
            lambda argv: argv[:2] == [FC.RCTL_BIN, "-a"]
            and "vmemoryuse" in argv[2],
            (1, "", "rctl: failed to add rule")))
        with self.assertRaises(RuntimeError) as caught:
            self.spawn()
        self.assertIn("rctl -a", str(caught.exception))
        self.assertEqual(self.host.popens, [])
        self._nothing_left()

    def test_a_loopback_that_does_not_come_up_refuses(self):
        self.host.refuse[(FC.JEXEC_BIN, "up")] = (
            1, "", "ifconfig: ioctl (SIOCAIFADDR): Operation not "
            "permitted")
        with self.assertRaises(RuntimeError) as caught:
            self.spawn(cfg=_fcfg(loopback=True))
        self.assertIn("loopback could not be brought up",
                      str(caught.exception))
        self._nothing_left()

    def test_a_superuser_that_cannot_be_dropped_refuses(self):
        self.host.refuse[(FC.JAIL_BIN, "-m")] = (1, "", "jail: no")
        with self.assertRaises(RuntimeError) as caught:
            self.spawn(cfg=_fcfg(loopback=True))
        self.assertIn("allow.nosuser", str(caught.exception))
        self._nothing_left()

    def test_a_job_that_cannot_be_started_leaves_nothing(self):
        self.host.popen_error = OSError("jexec: gone")
        with self.assertRaises(OSError):
            self.spawn()
        self._nothing_left()
        # The reaper was told the release had the jail.
        (fd,) = self.host.reaper_fds
        self.assertEqual(os.read(fd, 16), b"done\n")

    def test_no_jail_is_made_by_a_runner_that_is_not_root(self):
        self.host._euid = 1001
        with self.assertRaises(RuntimeError) as caught:
            self.spawn()
        self.assertIn("needs root", str(caught.exception))
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.skeletons(), [])

    def test_a_missing_tool_or_tree_refuses_before_anything_is_made(self):
        for path in (FC.JAIL_BIN, FC.JEXEC_BIN, FC.JLS_BIN,
                     FC.LIMITS_BIN, FC.MOUNT_BIN, FC.UMOUNT_BIN,
                     FC.SYSCTL_BIN, FC.SH_BIN, "/libexec"):
            host = FakeHost(self.folder)
            host.missing.add(path)
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError) as caught:
                    FC._spawn(["/bin/sh"], cwd=self.work, env={},
                              host=host)
                self.assertIn(path, str(caught.exception))
                self.assertEqual(host.calls, [])
        host = FakeHost(self.folder)
        host.missing.add(FC.IFCONFIG_BIN)
        FC._spawn(["/bin/sh"], cwd=self.work, env={}, host=host)
        with self.assertRaises(RuntimeError) as caught:
            FC._spawn(["/bin/sh"], cwd=self.work, env={},
                      cfg=_fcfg(loopback=True), host=host)
        self.assertIn(FC.IFCONFIG_BIN, str(caught.exception))

    def test_a_config_the_backend_cannot_honour_refuses_the_job(self):
        with self.assertRaises(RuntimeError):
            self.spawn(cfg={"security": {"confinement": {
                "extra_flags": ["--unshare-pid"]}}})
        with self.assertRaises(RuntimeError):
            self.spawn(cfg=_fcfg(job_processes=8))
        self.assertEqual(self.host.popens, [])
        self.assertEqual(self.skeletons(), [])

    def test_the_process_object_is_the_popen_subset(self):
        proc = self.spawn()
        self.assertIsNone(proc.poll())
        self.assertEqual(proc.communicate(timeout=5), (b"out", b"err"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.poll(), 0)
        proc.kill()
        self.assertTrue(proc._inner.killed)
        proc.close()
        calls = len(self.host.calls)
        proc.close()
        self.assertEqual(len(self.host.calls), calls)


class ReaperTest(_FakeHostCase):
    """The watcher that removes a job's jail when its runner is
    gone."""

    def test_the_watcher_sits_on_a_pipe_in_its_own_session(self):
        proc = self.spawn()
        (name,) = self.host.jails
        argv, kw = self.host.popens[0]
        self.assertEqual(
            argv, [FC.SH_BIN, "-c", FC.REAPER_SCRIPT, "hp-reaper", name])
        self.assertTrue(kw["start_new_session"])
        self.assertEqual(kw["cwd"], "/")
        self.assertEqual(kw["stdout"], subprocess.DEVNULL)
        self.assertEqual(kw["stderr"], subprocess.DEVNULL)
        # Started before the job, so no job runs unwatched.
        self.assertEqual(self.host.popens[1][0][0], FC.JEXEC_BIN)
        # The runner's end of the pipe is not inherited.
        _reaper, write_end = proc._reaper
        self.assertFalse(os.get_inheritable(write_end))

    def test_the_release_tells_the_watcher_and_reaps_it(self):
        proc = self.spawn()
        watcher, _write_end = proc._reaper
        proc.close()
        (fd,) = self.host.reaper_fds
        self.assertEqual(os.read(fd, 16), b"done\n")
        # The runner's end is closed: the next read is the end.
        self.assertEqual(os.read(fd, 16), b"")
        self.assertTrue(watcher.waited)

    def test_a_watcher_that_will_not_end_is_killed(self):
        proc = self.spawn()
        watcher, _write_end = proc._reaper

        def _hang(timeout=None):
            raise subprocess.TimeoutExpired("sh", timeout)
        watcher.wait = _hang
        proc.close()
        self.assertTrue(watcher.killed)

    def test_a_watcher_that_cannot_start_refuses_the_job(self):
        real = self.host.popen

        def _popen(argv, **kw):
            if argv[0] == FC.SH_BIN:
                raise OSError("no sh")
            return real(argv, **kw)
        self.host.popen = _popen
        with self.assertRaises(OSError):
            self.spawn()
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])

    @unittest.skipIf(os.name == "nt",
                     "the jail backend's host calls are POSIX")
    def test_the_line_itself_under_a_real_shell(self):
        # The same line, with a stand-in for jail(8) that
        # records how it was called. A pipe that closes without
        # the word removes the jail; the word does not.
        shell = shutil.which("sh")
        stand_in = os.path.join(self.folder, "jail-stand-in")
        record = os.path.join(self.folder, "removed.txt")
        with open(stand_in, "w") as fh:
            fh.write('#!/bin/sh\necho "$@" > "%s"\n' % record)
        os.chmod(stand_in, 0o755)
        line = FC.reaper_script(stand_in)

        def watch(word):
            read_end, write_end = os.pipe()
            proc = subprocess.Popen(
                [shell, "-c", line, "hp-reaper", "hpjob1x2"],
                stdin=read_end, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            os.close(read_end)
            if word:
                os.write(write_end, word)
            os.close(write_end)
            proc.wait(timeout=30)

        watch(b"done\n")
        self.assertFalse(os.path.exists(record))
        watch(b"")
        with open(record) as fh:
            self.assertEqual(fh.read().strip(), "-r hpjob1x2")
        os.unlink(record)
        watch(b"something else\n")
        self.assertTrue(os.path.exists(record))


class TeardownTest(_FakeHostCase):
    """The release never removes a skeleton through a mount."""

    def test_a_busy_mount_is_tried_again_before_it_is_forced(self):
        proc = self.spawn()
        root = self.root()
        self.host.busy[root + "/work"] = 3
        proc.close()
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])
        self.assertEqual(len(self.host.ran(FC.UMOUNT_BIN, root + "/work")),
                         4)
        self.assertEqual(self.host.ran(FC.UMOUNT_BIN, "-f"), [])
        self.assertGreater(self.host.slept, 0)

    def test_a_mount_that_stays_busy_is_forced(self):
        proc = self.spawn()
        root = self.root()
        self.host.busy[root + "/work"] = 99
        proc.close()
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])
        self.assertTrue(self.host.ran(FC.UMOUNT_BIN, "-f", root + "/work"))

    def test_a_mount_that_cannot_be_removed_keeps_the_skeleton(self):
        # The work mount will not let go. The job's files are
        # behind it: nothing below the skeleton is removed, and
        # the skeleton stays for the sweep.
        proc = self.spawn()
        root = self.root()
        (base,) = self.skeletons()
        self.host.stuck.add(root + "/work")
        marker = os.path.join(self.work, "result.txt")
        with open(marker, "w") as fh:
            fh.write("keep")
        proc.close()
        self.assertEqual(self.host.mounted(), [root + "/work"])
        self.assertEqual(self.skeletons(), [base])
        self.assertTrue(os.path.isdir(self.skel() + "/work"))
        self.assertTrue(os.path.exists(marker))
        self.assertEqual(self.host.jails, {})

    def test_an_unreadable_mount_table_keeps_the_skeleton(self):
        proc = self.spawn()
        (base,) = self.skeletons()
        self.host.refuse[(FC.MOUNT_BIN, "-p")] = (1, "", "mount: no")
        proc.close()
        self.assertEqual(self.skeletons(), [base])

    def test_a_mount_the_backend_did_not_make_is_seen_and_removed(self):
        # The mount table, not the backend's own list, decides
        # whether the skeleton is clear.
        proc = self.spawn()
        extra = self.root() + "/dev/fd"
        self.host.table.append(("fdescfs", extra, "fdescfs", "rw"))
        proc.close()
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])

    def test_the_removal_stops_at_another_filesystem(self):
        base = os.path.join(self.folder, "tree")
        inner = os.path.join(base, "skel", "work")
        os.makedirs(inner)
        kept = os.path.join(inner, "result.txt")
        with open(kept, "w") as fh:
            fh.write("keep")
        with open(os.path.join(base, "skel", "note"), "w") as fh:
            fh.write("x")
        real = os.lstat
        dev = real(base).st_dev

        def _lstat(path):
            st = real(path)
            if path == inner:
                # As a mount would answer: another device.
                return os.stat_result(
                    st[:2] + (dev + 1,) + st[3:])
            return st
        with mock.patch.object(FC.os, "lstat", _lstat):
            self.assertFalse(FC._remove_one_fs(base, dev))
        self.assertTrue(os.path.exists(kept))
        # What was on the skeleton's own filesystem went.
        self.assertFalse(os.path.exists(
            os.path.join(base, "skel", "note")))
        self.assertTrue(FC._remove_one_fs(base, dev))
        self.assertFalse(os.path.exists(base))
        self.assertTrue(FC._remove_one_fs(base, dev))

    def test_an_unmount_of_nothing_is_not_a_failure(self):
        self.assertTrue(FC._unmount(self.host, "/nowhere"))
        self.host.refuse[(FC.UMOUNT_BIN, "/gone")] = (
            1, "", "umount: /gone: statfs: No such file or directory")
        self.assertTrue(FC._unmount(self.host, "/gone"))
        self.assertEqual(self.host.slept, 0.0)

    def test_a_tool_that_cannot_be_run_is_an_answer(self):
        def _boom(argv, timeout=30):
            raise OSError("exec format error")
        self.host.run = _boom
        self.assertEqual(FC._quiet(self.host, ["/x"])[0], -1)
        self.assertFalse(FC._racct_enabled(self.host))
        self.assertIsNone(FC._mounted_below(self.host, "/b"))
        self.assertFalse(FC._remove_skeleton(self.host, self.work))
        self.assertTrue(os.path.isdir(self.work))


class SweepTest(_FakeHostCase):
    """What a dead runner left is removed; what a live runner
    holds is never touched."""

    racct = True

    def _stale_job(self, pid, alive=False):
        """A job as the runner `pid` would have left it."""
        other = FakeHost(self.folder, racct=True, pid=pid)
        other.table, other.jails, other.rules = (
            self.host.table, self.host.jails, self.host.rules)
        FC._spawn(["/bin/sh"], cwd=self.work, env={}, host=other)
        self.addCleanup(other.close)
        if alive:
            self.host.alive.add(pid)
        return [n for n in self.host.jails
                if n.startswith("hpjob%dx" % pid)][0]

    def test_a_dead_runner_s_job_is_removed_whole(self):
        name = self._stale_job(777)
        self.assertEqual(len(self.skeletons()), 1)
        removed = FC.sweep_stale(self.host)
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.host.rules, [])
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])
        self.assertIn("jail %s" % name, removed)
        self.assertTrue([r for r in removed if r.startswith("skeleton ")])

    def test_a_live_runner_s_job_is_not_touched(self):
        name = self._stale_job(888, alive=True)
        mounts = list(self.host.table)
        self.assertEqual(FC.sweep_stale(self.host), [])
        self.assertIn(name, self.host.jails)
        self.assertEqual(self.host.table, mounts)
        self.assertEqual(len(self.skeletons()), 1)
        self.assertEqual(len(self.host.rules), 2)

    def test_this_runner_s_own_job_is_not_touched(self):
        proc = self.spawn()
        self.assertEqual(FC.sweep_stale(self.host), [])
        self.assertEqual(len(self.host.jails), 1)
        proc.close()

    def test_rules_whose_jail_is_gone_are_removed(self):
        # The reaper removed the jail; the rules outlived it.
        name = self._stale_job(777)
        del self.host.jails[name]
        removed = FC.sweep_stale(self.host)
        self.assertEqual(self.host.rules, [])
        self.assertIn("rctl rules of %s" % name, removed)

    def test_a_skeleton_from_before_the_names_carried_a_runner(self):
        # The old shape: the skeleton was the jail root itself,
        # and its /dev stayed mounted after every job.
        old = os.path.join(self.folder, "hp-jail-ab12cd34")
        os.makedirs(os.path.join(old, "dev"))
        os.makedirs(os.path.join(old, "etc"))
        self.host.table.append(
            ("devfs", old + "/dev", "devfs", "rw"))
        removed = FC.sweep_stale(self.host)
        self.assertEqual(self.host.table, [])
        self.assertFalse(os.path.exists(old))
        self.assertEqual(removed, ["skeleton %s" % old])

    def test_a_skeleton_a_jail_still_stands_on_is_left(self):
        old = os.path.join(self.folder, "hp-jail-ab12cd34")
        os.makedirs(os.path.join(old, "dev"))
        self.host.jails["hpjob0123456789ab"] = {
            "path": old, "params": [], "suser": True, "lo": False}
        self.assertEqual(FC.sweep_stale(self.host), [])
        self.assertTrue(os.path.isdir(old))
        # A jail under a name this backend does not write is
        # not this backend's to remove.
        self.assertIn("hpjob0123456789ab", self.host.jails)

    def test_a_name_the_backend_does_not_recognise_is_left(self):
        for entry in ("hp-jail-notanumber-x", "hp-jail-12-34-56x"):
            os.makedirs(os.path.join(self.folder, entry))
        self.host.alive.add(12)
        self.assertEqual(FC.sweep_stale(self.host), [])
        self.assertEqual(len(self.skeletons()), 2)

    def test_unreadable_jails_keep_every_skeleton(self):
        old = os.path.join(self.folder, "hp-jail-ab12cd34")
        os.makedirs(old)
        self.host.refuse[(FC.JLS_BIN, "path")] = (1, "", "jls: no")
        self.assertEqual(FC.sweep_stale(self.host), [])
        self.assertTrue(os.path.isdir(old))

    def test_a_host_without_racct_is_swept_without_rctl(self):
        self.host.racct = False
        old = os.path.join(self.folder, "hp-jail-ab12cd34")
        os.makedirs(old)
        FC.sweep_stale(self.host)
        self.assertEqual(self.host.ran(FC.RCTL_BIN), [])
        self.assertFalse(os.path.exists(old))


class ProbeTest(_FakeHostCase):
    """The trial proves the controls the record will name."""

    def probe(self, cfg=None, cached=False):
        return FC._startup_problem(cfg, host=self.host, cached=cached)

    def test_a_host_that_holds_the_controls_passes_and_keeps_nothing(self):
        self.assertIsNone(self.probe())
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])
        (made,) = self.host.ran(FC.JAIL_BIN, "-c")
        self.assertIn("allow.nosuser", made)
        self.assertTrue(
            [a for a in made if a.startswith("name=hpprobe4242x")])
        (trial,) = self.host.ran(FC.JEXEC_BIN, FC.SH_BIN)
        self.assertEqual(trial[1:3], ["-d", "/work"])
        self.assertIn(FC.LIMITS_BIN, trial)

    def test_the_gate_s_probe_keeps_a_passing_verdict(self):
        self.assertIsNone(self.probe(cached=True))
        made = len(self.host.ran(FC.JAIL_BIN, "-c"))
        self.assertIsNone(self.probe(cached=True))
        self.assertEqual(len(self.host.ran(FC.JAIL_BIN, "-c")), made)
        # The startup probe runs the trial whenever it is asked.
        self.assertIsNone(self.probe())
        self.assertEqual(len(self.host.ran(FC.JAIL_BIN, "-c")), made + 1)

    def test_other_settings_are_another_trial(self):
        self.assertIsNone(self.probe(cached=True))
        self.assertIsNone(self.probe(_fcfg(tmp_bytes=4096), cached=True))
        self.assertEqual(len(self.host.ran(FC.JAIL_BIN, "-c")), 2)

    def test_a_failing_verdict_is_not_kept(self):
        self.host.trial_out = "trial\nWORK-OK\nTMP-OK\nPRIVILEGED\n" \
            "NULL-OK\nEND\n"
        self.assertIsNotNone(self.probe(cached=True))
        self.host.trial_out = None
        self.assertIsNone(self.probe(cached=True))

    def test_the_cheap_checks_run_every_time(self):
        self.assertIsNone(self.probe(cached=True))
        self.host._euid = 1001
        self.assertIn("needs root", self.probe(cached=True))

    def test_each_way_a_trial_fails_is_named(self):
        ok = ["trial", "WORK-OK", "TMP-OK", "NULL-OK", "END"]
        cases = (
            (ok + ["ROOT-WRITABLE"], "read-only root did not engage"),
            (ok + ["PRIVILEGED"], "allow.nosuser did not engage"),
            (ok + ["DEVICES-EXPOSED"], "devfs ruleset 4"),
            ([w for w in ok if w != "NULL-OK"], "devfs ruleset 4"),
            ([w for w in ok if w != "WORK-OK"], "could not write"),
            ([w for w in ok if w != "TMP-OK"], "could not write"),
            ([w for w in ok if w != "END"], "trial run failed"),
        )
        for words, expect in cases:
            with self.subTest(expect=expect, words=words):
                self.host.trial_out = "\n".join(words) + "\n"
                problem = self.probe()
                self.assertIsNotNone(problem)
                self.assertIn(expect, problem)
                self.assertEqual(self.host.jails, {})
                self.assertEqual(self.host.table, [])
                self.assertEqual(self.skeletons(), [])

    def test_the_fake_host_answers_from_what_was_built(self):
        # The pins above script the trial's words; this one
        # lets the fake answer from its own state, with the
        # super-user left in place by a patched jail command.
        with mock.patch.object(
                FC, "jail_parameters",
                lambda name, root, loopback=False, superuser=True: [
                    FC.JAIL_BIN, "-c", "name=" + name, "path=" + root]):
            self.assertIn("allow.nosuser did not engage", self.probe())
        real = FC.mount_plan

        def _writable_root(*a, **kw):
            plan = real(*a, **kw)
            plan[0]["argv"][4] = "nosuid"
            return plan
        with mock.patch.object(FC, "mount_plan", _writable_root):
            self.assertIn("read-only root did not engage", self.probe())

    def test_a_trial_that_exits_non_zero_is_named(self):
        self.host.refuse[(FC.JEXEC_BIN, FC.SH_BIN)] = (
            1, "", "limits: setrlimit vmemoryuse: Invalid argument")
        problem = self.probe()
        self.assertIn("in-jail trial run failed (exit 1)", problem)
        self.assertIn("Invalid argument", problem)
        self.assertEqual(self.host.jails, {})

    def test_the_rules_are_read_back_on_a_host_with_racct(self):
        self.host.racct = True
        self.assertIsNone(self.probe())
        self.assertEqual(self.host.rules, [])
        self.assertEqual(len(self.host.ran(FC.RCTL_BIN, "-a")), 2)
        # A listing that answers empty: the rules did not take.
        self.host.refuse_if.append((
            lambda argv: argv[0] == FC.RCTL_BIN and len(argv) == 2
            and argv[1].startswith("jail:hpprobe"),
            (0, "", "")))
        self.assertIn("rctl rules did not take", self.probe())
        self.assertEqual(self.host.rules, [])

    def test_a_loopback_is_read_back(self):
        self.assertIsNone(self.probe(_fcfg(loopback=True)))
        self.assertTrue(self.host.ran(FC.JAIL_BIN, "vnet=new"))
        self.assertTrue(self.host.ran(FC.JAIL_BIN, "-m"))
        real = self.host.run

        def _run(argv, timeout=30):
            if argv[0] == FC.JEXEC_BIN and argv[-1] == "lo0":
                return (0, "lo0: flags=8008<LOOPBACK>\n", "")
            return real(argv, timeout)
        self.host.run = _run
        self.assertIn("does not carry 127.0.0.1",
                      self.probe(_fcfg(loopback=True)))

    def test_a_config_the_backend_cannot_honour_is_the_problem(self):
        problem = self.probe({"security": {"confinement": {
            "extra_flags": ["--unshare-pid"]}}})
        self.assertIn("--unshare-pid", problem)
        problem = self.probe(_fcfg(job_processes=8))
        self.assertIn("kern.racct.enable=1", problem)
        problem = self.probe(_fcfg(nonsense=1))
        self.assertIn("nonsense", problem)
        self.assertEqual(self.host.ran(FC.JAIL_BIN, "-c"), [])

    def test_a_build_that_fails_is_the_problem_and_leaves_nothing(self):
        self.host.refuse[(FC.MOUNT_BIN, "tmpfs")] = (
            1, "", "mount: tmpfs: Operation not supported by device")
        problem = self.probe()
        self.assertIn("/tmp failed (exit 1)", problem)
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])

    def test_the_sweep_rides_the_first_probe_only(self):
        old = os.path.join(self.folder, "hp-jail-ab12cd34")
        os.makedirs(old)
        self.assertIsNone(self.probe())
        self.assertFalse(os.path.exists(old))
        os.makedirs(old)
        self.assertIsNone(self.probe())
        self.assertTrue(os.path.isdir(old))

    def test_a_sweep_that_fails_does_not_fail_the_probe(self):
        with mock.patch.object(FC, "sweep_stale",
                               side_effect=RuntimeError("no")):
            self.assertIsNone(self.probe())


class EdgeTest(_FakeHostCase):
    """The branches a healthy host never takes: each one lands
    in the refuse direction or leaves the tree as it was."""

    def test_a_skeleton_without_the_host_s_account_files(self):
        def _no_copy(src, dst):
            raise OSError("no such file")
        with mock.patch.object(FC.shutil, "copyfile", _no_copy):
            proc = self.spawn()
        self.assertEqual(os.listdir(self.skel() + "/etc"), [])
        proc.close()
        self.assertEqual(self.skeletons(), [])

    def test_a_skeleton_that_cannot_be_made_leaves_no_half(self):
        def _no_dirs(path, *a, **kw):
            raise OSError("disk full")
        with mock.patch.object(FC.os, "makedirs", _no_dirs):
            with self.assertRaises(OSError):
                self.spawn()
            self.assertIn("confinement trial failed",
                          FC._startup_problem(host=self.host))
        self.assertEqual(self.skeletons(), [])
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.host.jails, {})

    def test_a_tool_that_cannot_be_started_is_the_problem(self):
        real = self.host.run

        def _run(argv, timeout=30):
            if argv[0] == FC.MOUNT_BIN and argv[1] != "-p":
                raise OSError("mount: exec format error")
            return real(argv, timeout)
        self.host.run = _run
        with self.assertRaises(RuntimeError) as caught:
            self.spawn()
        self.assertIn("exec format error", str(caught.exception))
        self.assertEqual(self.skeletons(), [])

        def _run2(argv, timeout=30):
            if argv[:2] == [FC.JAIL_BIN, "-c"]:
                raise subprocess.TimeoutExpired(argv, timeout)
            return real(argv, timeout)
        self.host.run = _run2
        with self.assertRaises(RuntimeError) as caught:
            self.spawn()
        self.assertIn("jail -c failed", str(caught.exception))
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])

    def test_a_trial_that_hangs_is_the_problem_and_leaves_nothing(self):
        real = self.host.run

        def _run(argv, timeout=30):
            if argv[0] == FC.JEXEC_BIN:
                raise subprocess.TimeoutExpired(argv, timeout)
            return real(argv, timeout)
        self.host.run = _run
        self.assertIn("confinement trial failed",
                      FC._startup_problem(host=self.host))
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.host.table, [])
        self.assertEqual(self.skeletons(), [])

    def test_a_jail_that_is_slow_to_go_is_waited_for(self):
        proc = self.spawn()
        (name,) = self.host.jails
        real = self.host.run
        lingering = [3]

        def _run(argv, timeout=30):
            if argv[:2] == [FC.JLS_BIN, "-j"] and lingering[0] > 0:
                lingering[0] -= 1
                self.host.calls.append(list(argv))
                return (0, "7\n", "")
            return real(argv, timeout)
        self.host.run = _run
        proc.close()
        self.assertEqual(lingering[0], 0)
        self.assertGreater(self.host.slept, 0)
        self.assertEqual(self.skeletons(), [])
        self.assertNotIn(name, self.host.jails)

    def test_the_mount_table_s_odd_lines_are_passed_over(self):
        self.host.refuse[(FC.MOUNT_BIN, "-p")] = (
            0, "\nshort\ndevfs\t/b/x/dev devfs\trw\t0 0\n"
            "tmpfs\t/b/x devfs\trw\t0 0\n/dev/ada0p2\t/ ufs rw 1 1\n",
            "")
        self.assertEqual(FC._mounted_below(self.host, "/b/x"),
                         ["/b/x/dev", "/b/x"])

    def test_a_tree_that_resists_is_reported_not_forced(self):
        base = os.path.join(self.folder, "tree")
        os.makedirs(os.path.join(base, "skel"))
        with open(os.path.join(base, "skel", "f"), "w") as fh:
            fh.write("x")
        dev = os.lstat(base).st_dev

        def _refuse(path, *a, **kw):
            raise OSError("busy")
        for name in ("unlink", "listdir"):
            with mock.patch.object(FC.os, name, _refuse):
                self.assertFalse(FC._remove_one_fs(base, dev), name)
        os.unlink(os.path.join(base, "skel", "f"))
        with mock.patch.object(FC.os, "rmdir", _refuse):
            self.assertFalse(FC._remove_one_fs(base, dev))
        self.assertTrue(os.path.isdir(base))
        self.assertTrue(FC._remove_skeleton(self.host, base))
        # Already gone is gone.
        self.assertTrue(FC._remove_skeleton(self.host, base))
        self.assertTrue(FC._teardown(self.host, None, None, []))

    def test_a_folder_that_cannot_be_listed_is_swept_as_empty(self):
        def _refuse(path):
            raise OSError("no")
        with mock.patch.object(FC.os, "listdir", _refuse):
            self.assertEqual(FC.sweep_stale(self.host), [])

    def test_the_release_does_not_raise_over_a_watcher_or_a_job(self):
        proc = self.spawn()
        watcher, write_end = proc._reaper
        os.close(write_end)
        # A descriptor that is no descriptor: the write and the
        # close both fail, and neither may reach the caller.
        proc._reaper = (watcher, -1)

        def _no_kill():
            raise OSError("gone")

        def _hang(timeout=None):
            raise subprocess.TimeoutExpired("sh", timeout)
        watcher.wait = _hang
        watcher.kill = _no_kill
        proc._inner.kill = _no_kill
        proc.kill()
        proc.close()
        self.assertEqual(self.host.jails, {})
        self.assertEqual(self.skeletons(), [])
        FC._stop_reaper(None)

    def test_a_process_this_one_may_not_signal_is_alive(self):
        def _denied(pid, sig):
            raise PermissionError("not yours")
        with mock.patch.object(FC.os, "kill", _denied):
            self.assertTrue(FC._Host().pid_alive(1))


class PostureTest(_FakeHostCase):
    """The posture report's FreeBSD line: what a job's jail
    would carry on this host, read without building one."""

    def lines(self, cfg=None):
        return FC.posture_lines(cfg, host=self.host)

    def test_a_host_that_can_engage_names_its_controls(self):
        lines = self.lines()
        self.assertEqual(lines[0], (
            "OK", "FreeBSD jail backend: freebsd: jail + no_network "
            "+ no_superuser + spawn_resource_limits"))
        # Without RACCT the report says how to get the rules.
        self.assertEqual(lines[1][0], "OK")
        self.assertIn("kern.racct.enable=1", lines[1][1])
        self.assertIn("/boot/loader.conf", lines[1][1])
        # Nothing was built to say so.
        self.assertEqual(self.host.ran(FC.JAIL_BIN), [])
        self.assertEqual(self.host.ran(FC.MOUNT_BIN), [])
        self.assertEqual(self.skeletons(), [])

    def test_racct_is_named_and_the_hint_goes(self):
        self.host.racct = True
        self.assertEqual(self.lines(), [(
            "OK", "FreeBSD jail backend: freebsd: jail + no_network "
            "+ no_superuser + rctl_resource_limits + "
            "spawn_resource_limits")])

    def test_what_would_refuse_the_start_is_a_warning(self):
        cases = (
            ({"security": {"confinement": {
                "extra_flags": ["--unshare-pid"]}}}, "--unshare-pid"),
            (_fcfg(job_processes=8), "kern.racct.enable=1"),
            (_fcfg(nonsense=1), "nonsense"),
        )
        for cfg, expect in cases:
            with self.subTest(expect=expect):
                ((level, text),) = self.lines(cfg)
                self.assertEqual(level, "WARN")
                self.assertIn(expect, text)
                self.assertIn("would refuse to start", text)
        self.host._euid = 1001
        ((level, text),) = self.lines()
        self.assertEqual(level, "WARN")
        self.assertIn("needs root", text)

    def test_the_platform_page_shows_the_seed_s_lines_as_printed(self):
        # The operator's page quotes what a fresh install prints
        # where the probe passes on a host without RACCT: the
        # seed's own line, and the report's lines beneath it.
        page = os.path.join(_REPO, "docs", "steady", "security",
                            "freebsd.md")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        answer = (None, tuple(t for _level, t in self.lines()))
        printed = INS.seed_kept_lines(
            answer, "/root/.homing-pigeon/config.json")
        self.assertEqual(len(printed), 3)
        for line in printed:
            self.assertIn("\n  " + line + "\n", text)

    def test_the_report_asks_the_backend_on_freebsd_only(self):
        from runner.ops import posture as P
        seen = []

        def _lines(cfg):
            seen.append(cfg)
            return [("OK", "FreeBSD jail backend: x"), ("WARN", "y")]
        cfg = {"security": {}}
        results = []
        with mock.patch.object(P.sys, "platform", "freebsd14"), \
                mock.patch.object(P, "_freebsd_confinement_lines",
                                  _lines):
            P._check_confinement_backend(results, cfg)
        self.assertEqual(results, [
            ("OK", "confinement", "FreeBSD jail backend: x"),
            ("WARN", "confinement", "y")])
        self.assertIs(seen[0], cfg)

        def _boom(cfg):
            raise RuntimeError("module gone")
        results = []
        with mock.patch.object(P.sys, "platform", "freebsd14"), \
                mock.patch.object(P, "_freebsd_confinement_lines",
                                  _boom):
            P._check_confinement_backend(results)
        self.assertEqual(results[0][0], "WARN")
        self.assertIn("module gone", results[0][2])
        # Elsewhere the backend is not asked.
        results = []
        with mock.patch.object(P.sys, "platform", "darwin"), \
                mock.patch.object(P, "_freebsd_confinement_lines",
                                  _boom):
            P._check_confinement_backend(results, cfg)
        self.assertEqual(results[0][0], "OK")

    def test_the_report_s_own_reader_reaches_the_backend(self):
        from runner.ops import posture as P
        with mock.patch.object(FC, "posture_lines",
                               return_value=[("OK", "z")]) as lines:
            self.assertEqual(P._freebsd_confinement_lines({"a": 1}),
                             [("OK", "z")])
        lines.assert_called_once_with({"a": 1})


class HostFaceTest(unittest.TestCase):
    """The real host object, where this machine can answer."""

    def test_the_facts_are_this_process_s(self):
        host = FC._Host()
        self.assertEqual(host.pid(), os.getpid())
        self.assertEqual(host.temp_folder(), tempfile.gettempdir())
        self.assertTrue(host.is_dir(tempfile.gettempdir()))
        self.assertFalse(host.is_dir(os.path.join(
            tempfile.gettempdir(), "hp-no-such-folder")))
        self.assertIsNone(host.device(os.path.join(
            tempfile.gettempdir(), "hp-no-such-folder")))
        self.assertIsNotNone(host.device(tempfile.gettempdir()))
        self.assertFalse(host.executable(tempfile.gettempdir()))
        host.sleep(0)

    @unittest.skipIf(os.name == "nt",
                     "the jail backend's host calls are POSIX")
    def test_a_command_and_a_process(self):
        host = FC._Host()
        self.assertEqual(host.euid(), os.geteuid())
        self.assertTrue(host.pid_alive(os.getpid()))
        shell = host.which("sh")
        self.assertTrue(host.executable(shell))
        self.assertIsNone(host.which("hp-no-such-tool"))
        rc, out, err = host.run([shell, "-c", "echo out; echo err >&2"])
        self.assertEqual((rc, out, err), (0, "out\n", "err\n"))
        proc = host.popen([shell, "-c", "exit 3"])
        self.assertEqual(proc.wait(timeout=30), 3)
        # A process that has ended and been reaped is not alive.
        self.assertFalse(host.pid_alive(proc.pid))


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LiveBackendTest(unittest.TestCase):
    """The real backend, on a FreeBSD host as root (the node)."""

    def test_the_probe_engages(self):
        self.assertIsNone(FC.freebsd_confinement_problem())

    def test_jail_argv_translation(self):
        with tempfile.TemporaryDirectory() as work:
            script = os.path.join(work, "s.sh")
            out = FC.build_jail_argv(["sh", script], cwd=work)
            self.assertEqual(out[0], "/bin/sh")
            self.assertEqual(out[1], "/work/s.sh")
        # An interpreter no mount can show: a home is never
        # mounted, and neither is the filesystem root.
        for path in ("/root/python3", "/python3"):
            with self.assertRaises(RuntimeError):
                FC.build_jail_argv([path], cwd=None)

    def test_a_spawn_runs_inside_the_jail(self):
        with tempfile.TemporaryDirectory() as work:
            proc = FC.spawn_confined_process(
                ["/bin/sh", "-c",
                 "echo IN-JAIL; test -d /work && echo WORK-OK; "
                 "echo x > /tmp/escape-note.txt"],
                cwd=work, env={})
            out, _err = proc.communicate(timeout=30)
            rc = proc.returncode
            proc.close()
            self.assertEqual(rc, 0)
            self.assertIn(b"IN-JAIL", out)
            self.assertIn(b"WORK-OK", out)
            # The write landed in the jail's tmpfs, not the host's.
            self.assertFalse(os.path.exists("/tmp/escape-note.txt"))

    def test_a_spawn_as_the_job_user(self):
        # The runner's contract: the workdir is chowned to the
        # job user before the spawn (the job_user seam), and
        # the spawn applies that user at the jail door. The job
        # must run AS that user, in /work, able to write a
        # relative path there.
        import pwd
        nobody = pwd.getpwnam("nobody")
        with tempfile.TemporaryDirectory() as work:
            os.chown(work, nobody.pw_uid, nobody.pw_gid)
            proc = FC.spawn_confined_process(
                ["/bin/sh", "-c",
                 "id; pwd; echo x > rel-note.txt"],
                cwd=work, env={}, user="nobody")
            out, _err = proc.communicate(timeout=30)
            rc = proc.returncode
            proc.close()
            self.assertEqual(rc, 0)
            self.assertIn(b"uid=%d" % nobody.pw_uid, out)
            self.assertIn(b"/work", out)
            self.assertTrue(
                os.path.exists(os.path.join(work, "rel-note.txt")))

    def test_a_local_binary_runs_inside_the_jail(self):
        # A binary linked against /usr/local libraries (the
        # pkg-installed python3) must actually run inside the
        # jail: the loader's hints ride in the skeleton's
        # /var/run. A job that cannot start its interpreter is
        # the failure this pins.
        with tempfile.TemporaryDirectory() as work:
            proc = FC.spawn_confined_process(
                ["/usr/local/bin/python3", "-c",
                 "print('PY-IN-JAIL')"],
                cwd=work, env={})
            out, err = proc.communicate(timeout=30)
            rc = proc.returncode
            proc.close()
            self.assertEqual(rc, 0, err)
            self.assertIn(b"PY-IN-JAIL", out)

    def test_the_memory_ceiling_refuses_a_700mb_job(self):
        with tempfile.TemporaryDirectory() as work:
            proc = FC.spawn_confined_process(
                ["/usr/local/bin/python3", "-c",
                 "a = bytearray(700 * 1024 * 1024); "
                 "a[::4096] = b'1' * 179200; print('MEM-DONE')"],
                cwd=work, env={})
            out, err = proc.communicate(timeout=60)
            rc = proc.returncode
            proc.close()
            self.assertNotEqual(rc, 0)
            self.assertNotIn(b"MEM-DONE", out)
            # The refusal must be the ceiling's -- an allocation
            # failure -- not the job failing to start at all.
            self.assertIn(b"MemoryError", err)


# The interpreter the live jobs run: the pkg-installed python3,
# which the skeleton's loader hints let run inside the jail.
_LIVE_PYTHON = "/usr/local/bin/python3"


def _leftovers():
    """What a finished job may have left on the host: the
    mounts below a jail skeleton, the skeleton directories,
    the jails still standing under this backend's name, and
    the rctl rules written for them."""
    prefix = getattr(FC, "SKELETON_PREFIX", "hp-jail-")
    mounts = set()
    try:
        out = subprocess.run(
            ["/sbin/mount", "-p"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        out = ""
    for line in out.splitlines():
        fields = line.split()
        if len(fields) > 1 and prefix in fields[1]:
            mounts.add(fields[1])
    folder = getattr(FC, "SKELETON_DIR", None) or tempfile.gettempdir()
    try:
        dirs = {n for n in os.listdir(folder) if n.startswith(prefix)}
    except OSError:
        dirs = set()
    jails = set()
    try:
        out = subprocess.run(
            ["/usr/sbin/jls", "name"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        out = ""
    for name in out.split():
        if name.startswith("hp"):
            jails.add(name)
    rules = set()
    try:
        out = subprocess.run(
            ["/usr/bin/rctl"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        out = ""
    for line in out.splitlines():
        if line.startswith("jail:hp"):
            rules.add(line.strip())
    return {"mounts": mounts, "dirs": dirs, "jails": jails,
            "rules": rules}


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LiveBoundaryTest(unittest.TestCase):
    """What a confined job can and cannot do, on a real kernel.

    Each test starts a real job through the backend's own spawn
    and reads what the job itself reports from inside its jail.
    The claims are the ones the platform page makes: two trees
    are writable and no others, the ceiling cannot be lifted by
    the job it holds, a set-user-ID bit buys nothing, the
    scratch tree is bounded, the host's processes and network
    do not exist in there, and a finished job leaves nothing
    behind on the host.
    """

    def _job(self, argv, user=None, timeout=120):
        """Run argv confined in a fresh work directory; return
        (exit code, stdout, stderr, work directory)."""
        work = tempfile.mkdtemp(prefix="hp-live-")
        self.addCleanup(shutil.rmtree, work, True)
        os.chmod(work, 0o755)
        if user is not None:
            import pwd
            rec = pwd.getpwnam(user)
            os.chown(work, rec.pw_uid, rec.pw_gid)
        proc = FC.spawn_confined_process(
            list(argv), cwd=work, env={}, user=user)
        try:
            out, err = proc.communicate(timeout=timeout)
        finally:
            proc.close()
        return proc.returncode, out, err, work

    def _sh(self, script, user=None, timeout=120):
        return self._job(["/bin/sh", "-c", script], user=user,
                         timeout=timeout)

    def _py(self, source, user=None, timeout=120):
        return self._job([_LIVE_PYTHON, "-c", source], user=user,
                         timeout=timeout)

    def test_two_trees_are_writable_and_no_others(self):
        _rc, out, err, work = self._sh(
            "echo x > /work/in-work.txt && echo WROTE-WORK; "
            "echo x > /tmp/in-tmp.txt && echo WROTE-TMP; "
            "echo x > /escape-root.txt && echo WROTE-ROOT; "
            "echo x > /etc/escape.txt && echo WROTE-ETC; "
            "echo x > /var/run/escape.txt && echo WROTE-VAR; "
            "mkdir /newdir && echo MADE-DIR; "
            "echo x > /usr/escape.txt && echo WROTE-USR; "
            "echo x > /bin/escape.txt && echo WROTE-BIN; "
            "echo DONE")
        self.assertIn(b"DONE", out, err)
        self.assertIn(b"WROTE-WORK", out, err)
        self.assertIn(b"WROTE-TMP", out, err)
        for word in (b"WROTE-ROOT", b"WROTE-ETC", b"WROTE-VAR",
                     b"MADE-DIR", b"WROTE-USR", b"WROTE-BIN"):
            self.assertNotIn(word, out, (word, err))
        self.assertTrue(
            os.path.exists(os.path.join(work, "in-work.txt")))

    def test_a_job_cannot_lift_its_memory_ceiling(self):
        # A resource limit is the job's own to raise when the
        # job holds the privilege to raise it. The job asks for
        # an unlimited address space and then for 700 MiB; the
        # ceiling must answer both.
        _rc, out, err, _work = self._py(
            "import resource\n"
            "inf = resource.RLIM_INFINITY\n"
            "for name in ('RLIMIT_AS', 'RLIMIT_DATA'):\n"
            "    try:\n"
            "        resource.setrlimit(getattr(resource, name), "
            "(inf, inf))\n"
            "        print('LIFTED', name)\n"
            "    except (ValueError, OSError) as e:\n"
            "        print('HELD', name, e)\n"
            "try:\n"
            "    a = bytearray(700 * 1024 * 1024)\n"
            "    a[::4096] = b'1' * 179200\n"
            "    print('ALLOCATED')\n"
            "except MemoryError:\n"
            "    print('REFUSED')\n")
        self.assertIn(b"HELD RLIMIT_AS", out, (out, err))
        self.assertIn(b"HELD RLIMIT_DATA", out, (out, err))
        self.assertNotIn(b"LIFTED", out, (out, err))
        self.assertIn(b"REFUSED", out, (out, err))
        self.assertNotIn(b"ALLOCATED", out, (out, err))

    def test_root_inside_the_jail_holds_no_privilege(self):
        # Without a job user the job is uid 0 in its jail. The
        # number is all it keeps: an act that needs the
        # super-user's privilege is refused.
        _rc, out, err, _work = self._sh(
            "id -u; touch /work/f; "
            "chown 65534 /work/f && echo CHOWNED || "
            "echo CHOWN-REFUSED")
        self.assertEqual(out.split()[0], b"0", (out, err))
        self.assertIn(b"CHOWN-REFUSED", out, (out, err))
        self.assertNotIn(b"CHOWNED", out, (out, err))

    def test_a_set_user_id_bit_buys_nothing(self):
        # A root-owned set-user-ID program inside the one tree
        # a job can stage files into. Run by the job user it
        # must report the job user, not root.
        import pwd
        nobody = pwd.getpwnam("nobody")
        work = tempfile.mkdtemp(prefix="hp-live-")
        self.addCleanup(shutil.rmtree, work, True)
        os.chmod(work, 0o755)
        os.chown(work, nobody.pw_uid, nobody.pw_gid)
        target = os.path.join(work, "suid-id")
        shutil.copyfile("/usr/bin/id", target)
        os.chown(target, 0, 0)
        os.chmod(target, 0o4755)
        proc = FC.spawn_confined_process(
            ["/bin/sh", "-c", "/work/suid-id -u"],
            cwd=work, env={}, user="nobody")
        try:
            out, err = proc.communicate(timeout=60)
        finally:
            proc.close()
        self.assertEqual(out.strip(), b"%d" % nobody.pw_uid,
                         (out, err))

    def test_the_scratch_tree_is_bounded(self):
        # /tmp is memory. A job that could fill it without
        # bound would hold the host's memory outside every
        # ceiling a process carries.
        _rc, out, err, _work = self._sh(
            "dd if=/dev/zero of=/tmp/big bs=1048576 count=640 "
            "> /dev/null 2>&1; "
            "ls -l /tmp/big | awk '{print \"SIZE\", $5}'",
            timeout=300)
        words = out.split()
        self.assertIn(b"SIZE", words, (out, err))
        size = int(words[words.index(b"SIZE") + 1])
        self.assertLess(size, 640 * 1024 * 1024, (out, err))

    def test_the_host_s_processes_do_not_exist_inside(self):
        _rc, out, err, _work = self._sh("ps -ax -o pid=")
        pids = {int(tok) for tok in out.split() if tok.isdigit()}
        self.assertTrue(pids, (out, err))
        self.assertNotIn(os.getpid(), pids, (out, err))
        self.assertNotIn(1, pids, (out, err))
        self.assertLess(len(pids), 10, (out, err))

    def test_there_is_no_network_at_all(self):
        _rc, out, err, _work = self._py(
            "import socket\n"
            "def attempt(label, fam, addr):\n"
            "    try:\n"
            "        s = socket.socket(fam, socket.SOCK_STREAM)\n"
            "        s.settimeout(5)\n"
            "        s.bind(addr)\n"
            "        print(label, 'BOUND')\n"
            "    except OSError as e:\n"
            "        print(label, 'NO-BIND', e)\n"
            "attempt('V4', socket.AF_INET, ('127.0.0.1', 0))\n"
            "attempt('V6', socket.AF_INET6, ('::1', 0))\n"
            "try:\n"
            "    s = socket.socket(socket.AF_INET, "
            "socket.SOCK_STREAM)\n"
            "    s.settimeout(5)\n"
            "    s.connect(('1.1.1.1', 53))\n"
            "    print('OUT CONNECTED')\n"
            "except OSError as e:\n"
            "    print('OUT NO-CONNECT', e)\n",
            timeout=60)
        self.assertIn(b"V4 NO-BIND", out, (out, err))
        self.assertIn(b"V6 NO-BIND", out, (out, err))
        self.assertIn(b"OUT NO-CONNECT", out, (out, err))

    def test_a_finished_job_leaves_nothing_on_the_host(self):
        before = _leftovers()
        rc, out, err, _work = self._sh("echo DONE")
        self.assertEqual(rc, 0, (out, err))
        after = _leftovers()
        for what in ("mounts", "dirs", "jails", "rules"):
            self.assertEqual(after[what] - before[what], set(),
                             "%s left behind" % what)

    def test_a_straggler_does_not_cost_the_job_its_files(self):
        # A job that leaves a process behind, sitting in the
        # work directory: the release ends the process, and the
        # files the job wrote must still be on the host after.
        before = _leftovers()
        rc, out, err, work = self._sh(
            "echo keep > /work/result.txt; cd /work; "
            "sleep 600 > /dev/null 2>&1 < /dev/null & "
            "echo STARTED")
        self.assertEqual(rc, 0, (out, err))
        self.assertIn(b"STARTED", out, (out, err))
        path = os.path.join(work, "result.txt")
        self.assertTrue(os.path.exists(path),
                        "the release removed the job's own file")
        with open(path, encoding="ascii") as fh:
            self.assertEqual(fh.read().strip(), "keep")
        after = _leftovers()
        for what in ("mounts", "dirs", "jails", "rules"):
            self.assertEqual(after[what] - before[what], set(),
                             "%s left behind" % what)


def _host_says(*argv):
    """One host command's (exit code, stdout)."""
    try:
        done = subprocess.run(
            list(argv), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return done.returncode, done.stdout.decode("utf-8", "replace")


def _racct_live():
    return _host_says(FC.SYSCTL_BIN, "-n",
                      "kern.racct.enable")[1].strip() == "1"


def _vimage_live():
    return _host_says(FC.SYSCTL_BIN, "-n",
                      "kern.features.vimage")[1].strip() == "1"


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LiveControlsTest(unittest.TestCase):
    """The controls a config or a host adds, on a real kernel:
    the record's names, the jail-wide rules, the private
    loopback, the operator's binds and work mount, the
    interpreter's prefix, and what stands behind the release
    when the runner itself is gone."""

    def _job(self, argv, cfg=None, user=None, timeout=120, work=None):
        if work is None:
            work = tempfile.mkdtemp(prefix="hp-live-")
            self.addCleanup(shutil.rmtree, work, True)
            os.chmod(work, 0o755)
        if user is not None:
            import pwd
            rec = pwd.getpwnam(user)
            os.chown(work, rec.pw_uid, rec.pw_gid)
        proc = FC.spawn_confined_process(
            list(argv), cwd=work, env={}, user=user, cfg=cfg)
        try:
            out, err = proc.communicate(timeout=timeout)
        finally:
            proc.close()
        return proc, out, err, work

    def test_the_record_names_the_controls_this_host_holds(self):
        proc, out, err, _work = self._job(["/bin/sh", "-c", "echo OK"])
        self.assertIn(b"OK", out, err)
        want = ["jail", "no_network", "no_superuser"]
        if _racct_live():
            want.append("rctl_resource_limits")
        want.append("spawn_resource_limits")
        self.assertEqual(proc.confinement_status,
                         "freebsd: " + " + ".join(want))
        proc, out, err, _work = self._job(
            ["/bin/sh", "-c", "id -u"], user="nobody")
        self.assertNotIn("no_superuser", proc.confinement_status)
        self.assertNotEqual(out.strip(), b"0", (out, err))

    def test_a_job_user_cannot_lift_its_ceiling_either(self):
        _proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c",
             "import resource\n"
             "inf = resource.RLIM_INFINITY\n"
             "try:\n"
             "    resource.setrlimit(resource.RLIMIT_AS, (inf, inf))\n"
             "    print('LIFTED')\n"
             "except (ValueError, OSError) as e:\n"
             "    print('HELD', e)\n"
             "try:\n"
             "    a = bytearray(700 * 1024 * 1024)\n"
             "    print('ALLOCATED')\n"
             "except MemoryError:\n"
             "    print('REFUSED')\n"],
            user="nobody")
        self.assertIn(b"HELD", out, (out, err))
        self.assertIn(b"REFUSED", out, (out, err))

    def test_the_jail_holds_a_ceiling_on_processes(self):
        if not _racct_live():
            self.skipTest("RACCT is not enabled on this host")
        cfg = {"security": {"confinement": {"freebsd": {
            "job_processes": 20}}}}
        proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c",
             "import os, time\n"
             "kids = []\n"
             "refused = None\n"
             "for i in range(60):\n"
             "    try:\n"
             "        pid = os.fork()\n"
             "    except OSError as e:\n"
             "        refused = e\n"
             "        break\n"
             "    if pid == 0:\n"
             "        time.sleep(30)\n"
             "        os._exit(0)\n"
             "    kids.append(pid)\n"
             "print('STARTED', len(kids))\n"
             "print('REFUSED' if refused else 'UNBOUNDED', refused)\n"
             "for k in kids:\n"
             "    os.kill(k, 9)\n"],
            cfg=cfg)
        self.assertIn("rctl_resource_limits", proc.confinement_status)
        words = out.split()
        self.assertIn(b"REFUSED", words, (out, err))
        started = int(words[words.index(b"STARTED") + 1])
        self.assertLess(started, 20, (out, err))
        self.assertGreater(started, 5, (out, err))

    def test_the_jail_holds_a_ceiling_on_memory_across_processes(self):
        # Four processes, each well under the per-process
        # ceiling, together over the jail's. A per-process limit
        # cannot see the sum; the jail-wide rule does.
        if not _racct_live():
            self.skipTest("RACCT is not enabled on this host")
        cfg = {"security": {"confinement": {"freebsd": {
            "job_memory_bytes": 400 * 1024 * 1024}}}}
        _proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c",
             "import os, select, time\n"
             "r, w = os.pipe()\n"
             "kids = []\n"
             "marks = b''\n"
             "for i in range(4):\n"
             "    try:\n"
             "        pid = os.fork()\n"
             "    except OSError:\n"
             "        marks += b'F'\n"
             "        continue\n"
             "    if pid == 0:\n"
             "        try:\n"
             "            a = bytearray(150 * 1024 * 1024)\n"
             "            os.write(w, b'A')\n"
             "        except MemoryError:\n"
             "            os.write(w, b'R')\n"
             "        time.sleep(20)\n"
             "        os._exit(0)\n"
             "    kids.append(pid)\n"
             "    ready = select.select([r], [], [], 30)[0]\n"
             "    marks += os.read(r, 1) if ready else b'T'\n"
             "print('MARKS', marks.decode())\n"
             "for k in kids:\n"
             "    os.kill(k, 9)\n"],
            cfg=cfg)
        words = out.split()
        self.assertIn(b"MARKS", words, (out, err))
        marks = words[words.index(b"MARKS") + 1]
        self.assertEqual(len(marks), 4, (out, err))
        self.assertIn(b"A", marks, (out, err))
        self.assertLess(marks.count(b"A"), 4, (out, err))

    def test_a_private_loopback_reaches_itself_and_nothing_else(self):
        if not _vimage_live():
            self.skipTest("this kernel has no VIMAGE")
        import socket
        # A listener on the host's own loopback: the jail's
        # 127.0.0.1 is another stack and must not reach it.
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        cfg = {"security": {"confinement": {"freebsd": {
            "loopback": True}}}}
        proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c",
             "import socket, sys\n"
             "port = int(sys.argv[1])\n"
             "srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
             "srv.bind(('127.0.0.1', 0))\n"
             "srv.listen(1)\n"
             "c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
             "c.settimeout(5)\n"
             "c.connect(srv.getsockname())\n"
             "peer, _ = srv.accept()\n"
             "c.sendall(b'ping')\n"
             "print('LOOP', peer.recv(4).decode())\n"
             "for label, addr in (('HOST', ('127.0.0.1', port)),\n"
             "                    ('OUT', ('1.1.1.1', 53))):\n"
             "    try:\n"
             "        s = socket.socket(socket.AF_INET, "
             "socket.SOCK_STREAM)\n"
             "        s.settimeout(5)\n"
             "        s.connect(addr)\n"
             "        print(label, 'CONNECTED')\n"
             "    except OSError as e:\n"
             "        print(label, 'NO-CONNECT', e)\n",
             str(port)],
            cfg=cfg)
        self.assertIn(b"LOOP ping", out, (out, err))
        self.assertIn(b"HOST NO-CONNECT", out, (out, err))
        self.assertIn(b"OUT NO-CONNECT", out, (out, err))
        self.assertIn("private_loopback", proc.confinement_status)
        self.assertNotIn("no_network", proc.confinement_status)

    def test_a_private_loopback_keeps_no_privilege(self):
        if not _vimage_live():
            self.skipTest("this kernel has no VIMAGE")
        cfg = {"security": {"confinement": {"freebsd": {
            "loopback": True}}}}
        proc, out, err, _work = self._job(
            ["/bin/sh", "-c",
             "/sbin/ifconfig lo0 inet 10.9.8.7/32 alias "
             "> /dev/null 2>&1 && echo ADDRESS-SET || "
             "echo ADDRESS-REFUSED"],
            cfg=cfg)
        self.assertIn(b"ADDRESS-REFUSED", out, (out, err))
        self.assertIn("no_superuser", proc.confinement_status)

    def test_the_operator_s_binds_and_work_mount(self):
        data = tempfile.mkdtemp(prefix="hp-live-data-")
        self.addCleanup(shutil.rmtree, data, True)
        os.chmod(data, 0o755)
        with open(os.path.join(data, "hello.txt"), "w") as fh:
            fh.write("HELLO-FROM-THE-BIND\n")
        cfg = {"security": {"confinement": {
            "work_mount": "/job",
            "extra_ro_binds": [[data, "/data"]]}}}
        _proc, out, err, work = self._job(
            ["/bin/sh", "-c",
             "cat /data/hello.txt; "
             "echo x > /data/new.txt && echo WROTE-DATA; "
             "pwd; echo y > out.txt && echo WROTE-JOB; "
             "test -d /work && echo HAS-WORK; echo DONE"],
            cfg=cfg)
        self.assertIn(b"DONE", out, err)
        self.assertIn(b"HELLO-FROM-THE-BIND", out, err)
        self.assertNotIn(b"WROTE-DATA", out, err)
        self.assertIn(b"/job", out.split(), err)
        self.assertIn(b"WROTE-JOB", out, err)
        self.assertNotIn(b"HAS-WORK", out, err)
        self.assertTrue(os.path.exists(os.path.join(work, "out.txt")))
        self.assertFalse(os.path.exists(os.path.join(data, "new.txt")))

    def test_an_interpreter_outside_the_trees_runs_from_its_prefix(self):
        prefix = os.path.realpath(tempfile.mkdtemp(
            prefix="hp-live-prefix-", dir="/var/tmp"))
        self.addCleanup(shutil.rmtree, prefix, True)
        os.chmod(prefix, 0o755)
        os.mkdir(os.path.join(prefix, "bin"))
        tool = os.path.join(prefix, "bin", "sh")
        shutil.copyfile("/bin/sh", tool)
        os.chmod(tool, 0o755)
        proc, out, err, _work = self._job(
            [tool, "-c",
             "echo PREFIX-OK; echo x > %s/bin/new && echo WROTE-PREFIX"
             % prefix])
        self.assertIn(b"PREFIX-OK", out, err)
        self.assertNotIn(b"WROTE-PREFIX", out, err)
        self.assertEqual(
            proc.confinement_notes,
            ["interpreter prefix %s mounted read-only" % prefix])

    def test_a_runner_that_dies_takes_its_job_with_it(self):
        # A runner of its own: a process that starts a confined
        # job and is then killed outright. The watcher removes
        # the jail, which ends the job; the next sweep removes
        # the mounts and the skeleton the dead runner left.
        work = tempfile.mkdtemp(prefix="hp-live-")
        self.addCleanup(shutil.rmtree, work, True)
        runner = subprocess.Popen(
            [sys.executable, "-c",
             "import sys, time\n"
             "sys.path.insert(0, sys.argv[1])\n"
             "from runner.guard import freebsd_confine as FC\n"
             "p = FC.spawn_confined_process("
             "['/bin/sh', '-c', 'sleep 600'], cwd=sys.argv[2], env={})\n"
             "print(p._name, flush=True)\n"
             "time.sleep(600)\n",
             _REPO, work],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        try:
            name = runner.stdout.readline().decode().strip()
            self.assertTrue(FC._JAIL_NAME.match(name),
                            (name, runner.stderr.read()
                             if runner.poll() is not None else b""))
            self.assertEqual(
                _host_says(FC.JLS_BIN, "-j", name, "jid")[0], 0)
            before = _leftovers()
            self.assertTrue(
                [m for m in before["mounts"]
                 if "-%d-" % runner.pid in m], before)
        finally:
            runner.kill()
            runner.wait(timeout=30)
            runner.stdout.close()
            runner.stderr.close()
        import time
        gone = False
        for _attempt in range(60):
            if _host_says(FC.JLS_BIN, "-j", name, "jid")[0] != 0:
                gone = True
                break
            time.sleep(0.25)
        self.assertTrue(gone, "the jail outlived its runner")
        removed = FC.sweep_stale()
        self.assertTrue([r for r in removed if r.startswith("skeleton ")],
                        removed)
        after = _leftovers()
        mine = "-%d-" % runner.pid
        self.assertEqual([m for m in after["mounts"] if mine in m], [])
        self.assertEqual([d for d in after["dirs"] if mine in d], [])
        self.assertEqual(
            [r for r in after["rules"] if ("%dx" % runner.pid) in r], [])

    def test_a_sweep_leaves_a_live_runner_s_job_alone(self):
        work = tempfile.mkdtemp(prefix="hp-live-")
        self.addCleanup(shutil.rmtree, work, True)
        proc = FC.spawn_confined_process(
            ["/bin/sh", "-c", "sleep 5; echo STILL-HERE"],
            cwd=work, env={})
        try:
            self.assertEqual(
                [r for r in FC.sweep_stale()
                 if ("%dx" % os.getpid()) in r
                 or ("-%d-" % os.getpid()) in r], [])
            out, err = proc.communicate(timeout=60)
        finally:
            proc.close()
        self.assertIn(b"STILL-HERE", out, err)


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LiveRunnerTest(unittest.TestCase):
    """A job through the runner itself, on a real kernel: the
    gate, the seam, the backend, the record and the collected
    output, end to end at confinement enforce."""

    def _run(self, script, confinement=None, outputs=(),
             job_user=None):
        import json
        from runner.guard import security as S
        base = tempfile.mkdtemp(prefix="hp-live-runner-")
        self.addCleanup(shutil.rmtree, base, True)
        cfg = {"base_dir": base, "security": {"modes": {
            "confinement": "enforce", "job_user": "off"}}}
        if confinement:
            cfg["security"]["confinement"] = confinement
        if job_user:
            cfg["security"]["modes"]["job_user"] = "enforce"
            cfg["security"]["job_user"] = {"user": job_user}
        job = {"v": 1, "type": "job", "job_id": "fbsd-live",
               "issued_at": "2026-11-14T12:00:00Z", "kind": "exec",
               "interpreter": ["python3"], "script": script}
        if outputs:
            job["outputs"] = list(outputs)
        result = rr.execute_job(cfg, job, base)
        audit = []
        path = os.path.join(base, S.AUDIT_FILE)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        audit.append(json.loads(line))
                    except ValueError:
                        pass
        return result, audit, cfg, base

    def test_a_job_is_confined_recorded_and_its_output_collected(self):
        outside = tempfile.mkdtemp(prefix="hp-live-outside-")
        self.addCleanup(shutil.rmtree, outside, True)
        planted = os.path.join(outside, "outside.txt")
        with open(planted, "w") as fh:
            fh.write("outside-data")
        script = (
            "import os\n"
            "print('cwd:', os.getcwd())\n"
            "open('out.txt', 'w').write('wrote-ok')\n"
            "for label, path in (('root', '/escape.txt'),\n"
            "                    ('etc', '/etc/escape.txt')):\n"
            "    try:\n"
            "        open(path, 'w').write('x')\n"
            "        print(label + ': wrote')\n"
            "    except OSError:\n"
            "        print(label + ': blocked')\n"
            "try:\n"
            "    print('outside:', open(%r).read().strip())\n"
            "except OSError:\n"
            "    print('outside: blocked')\n" % planted)
        before = _leftovers()
        result, audit, _cfg, _base = self._run(
            script, outputs=["out.txt"])
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn("cwd: /work", result["stdout"])
        self.assertIn("root: blocked", result["stdout"])
        self.assertIn("etc: blocked", result["stdout"])
        self.assertIn("outside: blocked", result["stdout"])
        self.assertEqual(len(result["outputs"]), 1, result)
        import base64
        self.assertEqual(
            base64.b64decode(result["outputs"][0]["content_b64"]),
            b"wrote-ok")
        rows = [a for a in audit if a.get("decision") == "confined"]
        self.assertEqual(len(rows), 1, audit)
        reason = rows[0].get("reason", "")
        self.assertTrue(reason.startswith(
            "freebsd: jail + no_network + no_superuser"), reason)
        self.assertTrue(reason.endswith("spawn_resource_limits"), reason)
        after = _leftovers()
        for what in ("mounts", "dirs", "jails", "rules"):
            self.assertEqual(after[what] - before[what], set(),
                             "%s left behind" % what)

    def test_a_job_user_through_the_runner_goes_in_at_the_door(self):
        import pwd
        nobody = pwd.getpwnam("nobody")
        result, audit, _cfg, _base = self._run(
            "import os\n"
            "print('uid:', os.getuid())\n"
            "open('out.txt', 'w').write('as-the-user')\n",
            outputs=["out.txt"], job_user="nobody")
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn("uid: %d" % nobody.pw_uid, result["stdout"])
        self.assertEqual(len(result["outputs"]), 1, result)
        rows = [a for a in audit if a.get("decision") == "confined"]
        self.assertEqual(len(rows), 1, audit)
        self.assertNotIn("no_superuser", rows[0].get("reason", ""))
        self.assertTrue(rows[0].get("reason", "").startswith(
            "freebsd: jail + no_network"), rows)

    def test_the_config_s_work_mount_reaches_the_job(self):
        result, _audit, _cfg, _base = self._run(
            "import os\nprint('cwd:', os.getcwd())\n",
            confinement={"work_mount": "/job"})
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn("cwd: /job", result["stdout"])

    def test_the_startup_gate_reads_the_config(self):
        good = {"security": {"modes": {"confinement": "enforce"}}}
        self.assertIsNone(rr._confinement_startup_problem(good))
        flagged = {"security": {
            "modes": {"confinement": "enforce"},
            "confinement": {"extra_flags": ["--unshare-pid"]}}}
        problem = rr._confinement_startup_problem(flagged)
        self.assertIn("confinement cannot engage on freebsd", problem)
        self.assertIn("--unshare-pid", problem)


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LiveSeedTest(unittest.TestCase):
    """The mode a fresh install states, on a real kernel: the
    seed puts the real probe the startup gate's question and
    writes what the machine answers -- as root, as an ordinary
    user, for a config that asks more than the host holds, by
    the installer's file path, and through the wizard -- and a
    runner started on the seeded config confines its first job."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="hp-live-seed-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.before = _leftovers()

    def _nothing_left(self):
        after = _leftovers()
        for what in ("mounts", "dirs", "jails", "rules"):
            self.assertEqual(after[what] - self.before[what], set(),
                             "%s left behind" % what)

    def _seed(self, path):
        out = io.StringIO()
        with redirect_stdout(out):
            applied = INS.apply_platform_modes(path)
        return applied, out.getvalue()

    def test_as_root_the_seed_leaves_the_jail_on(self):
        path = _seeded_config(self.folder)
        with open(path, "rb") as fh:
            before = fh.read()
        applied, out = self._seed(path)
        with open(path, "rb") as fh:
            after = fh.read()
        self.assertEqual(applied, {}, out)
        self.assertEqual(before, after)
        self.assertEqual(_modes_in(path)["confinement"], "enforce")
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, out)
        # The controls a job's jail carries on this host, named
        # as the audit record will name them.
        self.assertIn("platform: FreeBSD jail backend: freebsd: "
                      "jail + no_network + no_superuser", out)
        self.assertEqual("rctl_resource_limits" in out,
                         _racct_live(), out)
        self.assertEqual("kern.racct.enable=1" in out,
                         not _racct_live(), out)
        self.assertNotIn("stated as audit", out)
        # A later run over the same config asks again and
        # changes nothing.
        applied, out = self._seed(path)
        with open(path, "rb") as fh:
            again = fh.read()
        self.assertEqual(applied, {}, out)
        self.assertEqual(again, before)
        self.assertIn("left at enforce", out)
        self._nothing_left()

    def test_a_runner_on_the_seeded_config_confines_its_first_job(self):
        from runner.guard import security as S
        path = _seeded_config(self.folder)
        applied, out = self._seed(path)
        self.assertEqual(applied, {}, out)
        with open(path, encoding="utf-8") as fh:
            seeded = json.load(fh)
        base = os.path.join(self.folder, "base")
        os.mkdir(base)
        # The security block exactly as the seed left it, on a
        # runner of its own.
        cfg = {"base_dir": base, "security": seeded["security"]}
        self.assertIsNone(rr._confinement_startup_problem(cfg))
        job = {"v": 1, "type": "job", "job_id": "fbsd-seeded",
               "issued_at": "2026-11-14T12:00:00Z", "kind": "exec",
               "interpreter": ["python3"],
               "script": ("import os\n"
                          "print('cwd:', os.getcwd())\n"
                          "try:\n"
                          "    open('/escape.txt', 'w').write('x')\n"
                          "    print('root: wrote')\n"
                          "except OSError:\n"
                          "    print('root: blocked')\n")}
        result = rr.execute_job(cfg, job, base)
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn("cwd: /work", result["stdout"])
        self.assertIn("root: blocked", result["stdout"])
        rows = []
        with open(os.path.join(base, S.AUDIT_FILE),
                  encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
        confined = [r for r in rows
                    if r.get("feature") == "confinement"
                    and r.get("decision") == "confined"]
        self.assertEqual(len(confined), 1, rows)
        # The record carries the names the seed printed.
        self.assertIn("platform: FreeBSD jail backend: "
                      + confined[0].get("reason", "<none>"), out)
        self._nothing_left()

    def test_an_ordinary_user_s_seed_states_audit_and_names_root(self):
        import pwd
        nobody = pwd.getpwnam("nobody")
        path = _seeded_config(self.folder)
        os.chown(self.folder, nobody.pw_uid, nobody.pw_gid)
        os.chown(path, nobody.pw_uid, nobody.pw_gid)
        # Everything the seed loads is loaded here first, as
        # root: the child below reads no source file as the
        # ordinary user, only its own config.
        warm = os.path.join(self.folder, "warm")
        os.mkdir(warm)
        with redirect_stdout(io.StringIO()):
            INS.apply_platform_modes(
                _seeded_config(warm), "freebsd14",
                probe=_Probe(problem="warm"))
            INS.freebsd_seed_probe({})
        read_end, write_end = os.pipe()
        pid = os.fork()
        if pid == 0:
            # The child: an ordinary user from here to its exit.
            code = 1
            try:
                os.close(read_end)
                os.setgroups([])
                os.setgid(nobody.pw_gid)
                os.setuid(nobody.pw_uid)
                out = io.StringIO()
                with redirect_stdout(out):
                    applied = INS.apply_platform_modes(path)
                said = {"uid": os.geteuid(), "applied": applied,
                        "modes": _modes_in(path),
                        "out": out.getvalue()}
                os.write(write_end, json.dumps(said).encode("utf-8"))
                code = 0
            except BaseException as e:  # reported, never raised here
                try:
                    os.write(write_end, json.dumps(
                        {"error": repr(e)}).encode("utf-8"))
                except OSError:
                    pass
            finally:
                os._exit(code)
        os.close(write_end)
        # The child answers and exits, which closes the pipe; one
        # that does neither inside a minute is ended and named.
        import select
        import signal
        import time
        chunks, deadline, answered = [], time.time() + 60, False
        while True:
            ready = select.select(
                [read_end], [], [], max(0.0, deadline - time.time()))[0]
            if not ready:
                break
            chunk = os.read(read_end, 65536)
            if not chunk:
                answered = True
                break
            chunks.append(chunk)
        os.close(read_end)
        if not answered:
            os.kill(pid, signal.SIGKILL)
        status = os.waitpid(pid, 0)[1]
        self.assertTrue(answered, "the ordinary user's seed did not "
                        "answer inside a minute")
        said = json.loads(b"".join(chunks).decode("utf-8"))
        self.assertEqual(status, 0, said)
        self.assertNotIn("error", said)
        self.assertEqual(said["uid"], nobody.pw_uid, said)
        self.assertEqual(said["applied"], {"confinement": "audit"},
                         said)
        self.assertEqual(said["modes"]["confinement"], "audit")
        self.assertEqual(said["modes"]["job_user"], "enforce")
        self.assertIn("security.modes.confinement stated as audit "
                      "in %s" % path, said["out"])
        self.assertIn("did not pass: creating a jail needs root",
                      said["out"])
        self.assertNotIn("left at enforce", said["out"])
        self._nothing_left()

    def test_named_ceilings_are_seeded_by_what_the_host_holds(self):
        path = _seeded_config(
            self.folder, confinement={"freebsd": {"job_processes": 64}})
        applied, out = self._seed(path)
        if _racct_live():
            self.assertEqual(applied, {}, out)
            self.assertEqual(_modes_in(path)["confinement"],
                             "enforce")
            self.assertIn("rctl_resource_limits", out)
        else:
            self.assertEqual(applied, {"confinement": "audit"}, out)
            self.assertEqual(_modes_in(path)["confinement"], "audit")
            self.assertIn("did not pass: ", out)
            self.assertIn("RACCT is not enabled on this host", out)
            self.assertIn("kern.racct.enable=1", out)
        self._nothing_left()

    def test_the_installer_started_by_path_seeds_the_same(self):
        path = _seeded_config(self.folder)
        with open(path, "rb") as fh:
            before = fh.read()
        driver = (
            "import json, runpy, sys\n"
            "ns = runpy.run_path(sys.argv[1], "
            "run_name='hp_install_by_path')\n"
            "applied = ns['apply_platform_modes'](sys.argv[2])\n"
            "print(json.dumps({'applied': applied, 'pulled_in': "
            "sorted(m for m in sys.modules if m.split('.')[0] "
            "in ('runner', 'ops', 'guard'))}))\n")
        done = subprocess.run(
            [sys.executable, "-I", "-c", driver, _INSTALL_PY, path],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=300, cwd=self.folder)
        text = done.stdout.decode("utf-8", "replace")
        self.assertEqual(done.returncode, 0,
                         done.stderr.decode("utf-8", "replace"))
        lines = text.splitlines()
        said = json.loads(lines[-1])
        self.assertEqual(said, {"applied": {}, "pulled_in": []}, text)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), before)
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, lines[0])
        self.assertIn("platform: FreeBSD jail backend: freebsd: "
                      "jail + no_network + no_superuser", text)
        self._nothing_left()

    def test_the_wizard_s_seed_asks_the_same_machine(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        answers = []
        stated = SU.seed_platform_modes(cfg, asked=answers)
        self.assertEqual(stated, {})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "enforce")
        self.assertEqual(len(answers), 1)
        self.assertIsNone(answers[0][0])
        self.assertTrue(answers[0][1][0].startswith(
            "FreeBSD jail backend: freebsd: jail + no_network"),
            answers)
        self._nothing_left()


if __name__ == "__main__":
    unittest.main()
