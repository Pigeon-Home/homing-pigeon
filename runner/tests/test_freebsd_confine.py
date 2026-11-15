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
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
# The suite's word for the seed's questions to the machine, set
# however this module is loaded -- by name, where the package
# has already set it, or by its file.
import runner.tests  # noqa: F401
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


def _machine_asked(word="1"):
    """The seed's questions to the machine, switched on for one
    test (or off, by `word`). The suite switches them off for
    every test that does not ask for them
    (runner/tests/__init__.py): a test run is not an install."""
    return mock.patch.dict(os.environ, {INS.SEED_SWITCH: word})


class _Probe:
    """A scripted answer to the seed's question, and what it
    was asked with."""

    def __init__(self, problem=None, lines=_PASS_LINES, error=None):
        self.problem, self.lines, self.error = problem, lines, error
        self.asked = []

    def __call__(self, cfg):
        # As it stood when asked: the seed writes into the same
        # object afterwards.
        self.asked.append(json.loads(json.dumps(cfg)))
        if self.error is not None:
            raise self.error
        if self.problem is not None:
            return (self.problem, ())
        return (None, self.lines)


_DOOR_LINES = ("FreeBSD jail backend: freebsd: jail + no_network + "
               "spawn_resource_limits",
               "a job goes in as nobody at the jail door "
               "(security.job_user) and reads what that user can read",
               "nobody is held to 256 processes across this host "
               "(limits -u at the jail door; no RACCT needed)",
               "RACCT is not enabled on this host")


def _door_lines(user):
    """The report's lines for a config that names `user`, on a
    host without RACCT."""
    return (_DOOR_LINES[0],
            _DOOR_LINES[1].replace("nobody", user),
            _DOOR_LINES[2].replace("nobody", user),
            _DOOR_LINES[3])


def _door_record(user="nobody", problem=None, notes=(), lines=None):
    """The record fresh_job_user hands back for one decision."""
    if lines is None:
        lines = () if problem is not None else _door_lines(user)
    return {"tried": user, "problem": problem, "lines": lines,
            "notes": list(notes)}


class _Trial:
    """A scripted answer to the seed's second question -- the
    throwaway job as the job user -- and what it was asked
    with. `problem` is one reason for every user, or a map of
    user to reason; a user with none passes, and the lines it
    hands back are the report's for that user."""

    def __init__(self, problem=None, lines=None, error=None):
        self.problem, self.lines, self.error = problem, lines, error
        self.asked = []

    def __call__(self, cfg, user):
        # As it stood when asked: the seed writes into the same
        # object afterwards.
        self.asked.append((json.loads(json.dumps(cfg)), user))
        if self.error is not None:
            raise self.error
        problem = self.problem
        if isinstance(problem, dict):
            problem = problem.get(user)
        if problem is not None:
            return (problem, ())
        return (None, self.lines if self.lines is not None
                else _door_lines(user))

    def users(self):
        return [user for _cfg, user in self.asked]


class _Account:
    """A scripted answer to "the account for jobs": what
    freebsd_job_account would hand back, and how often it was
    asked."""

    def __init__(self, user="pigeon-jobs", made=False, why=None,
                 error=None):
        self.answer, self.error, self.calls = (user, made, why), error, 0

    def __call__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.answer


class SeedTest(unittest.TestCase):
    """The mode a fresh FreeBSD config states: the machine's
    answer where it is asked, the stated map where it is not."""

    def _apply(self, path, platform="freebsd14", probe=None,
               trial=None, account=None):
        out = io.StringIO()
        with redirect_stdout(out):
            applied = INS.apply_platform_modes(
                path, platform, probe=probe, trial=trial,
                account=account)
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
        with _machine_asked(), \
                mock.patch.object(INS, "_HOST_PLATFORM", "freebsd14"), \
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

    # --- the job user the seed names ---------------------------

    def _security_in(self, path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["security"]

    def test_a_passing_trial_names_the_job_user(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            with open(path, encoding="utf-8") as fh:
                before = json.load(fh)
            trial = _Trial()
            applied, out = self._apply(path, probe=_Probe(),
                                       trial=trial)
            with open(path, encoding="utf-8") as fh:
                after = json.load(fh)
        # No mode moved; one block was added and nothing else.
        self.assertEqual(applied, {})
        self.assertEqual(after["security"]["job_user"],
                         {"user": "nobody"})
        del after["security"]["job_user"]
        self.assertEqual(after, before)
        self.assertEqual(len(trial.asked), 1)
        self.assertEqual(trial.asked[0][1], "nobody")
        lines = out.splitlines()
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, lines[0])
        self.assertIn("security.job_user names nobody in %s" % path,
                      lines[1])
        self.assertIn("a trial job as nobody inside a jail on this "
                      "machine passed", lines[1])
        self.assertIn("reads what root owns", lines[1])
        # The report's lines are the ones for the config as it
        # now stands: the trial's, not the probe's.
        self.assertEqual(lines[2:],
                         ["platform: " + t for t in _DOOR_LINES])
        self.assertNotIn("no_superuser", out)

    def test_a_failing_trial_names_no_one_and_says_why(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            with open(path, "rb") as fh:
                before = fh.read()
            applied, out = self._apply(
                path, probe=_Probe(),
                trial=_Trial(problem="jexec: nobody: no such user"))
            with open(path, "rb") as fh:
                after = fh.read()
        self.assertEqual(applied, {})
        self.assertEqual(before, after)
        lines = out.splitlines()
        self.assertIn("left at enforce", lines[0])
        self.assertIn("security.job_user left unnamed in %s" % path,
                      lines[1])
        self.assertIn("did not pass: jexec: nobody: no such user",
                      lines[1])
        self.assertIn("reads what root owns", lines[1])
        self.assertIn("name a user of the job's own", lines[1])
        # What a job's jail carries with no job user: the probe's
        # lines.
        self.assertEqual(lines[2:],
                         ["platform: " + t for t in _PASS_LINES])

    def test_a_trial_that_cannot_answer_names_no_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            applied, out = self._apply(
                path, probe=_Probe(),
                trial=_Trial(error=OSError("no jexec")))
            security = self._security_in(path)
        self.assertEqual(applied, {})
        self.assertNotIn("job_user", security)
        self.assertIn("did not pass: no jexec", out)

    def test_the_trial_is_asked_about_the_config_as_written(self):
        block = {"extra_ro_binds": [["/srv/tools", "/tools"]]}
        trial = _Trial()
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d, confinement=block)
            self._apply(path, probe=_Probe(), trial=trial)
        cfg, user = trial.asked[0]
        self.assertEqual(user, INS.FREEBSD_SHARED_JOB_USER)
        self.assertEqual(cfg["security"]["confinement"], block)
        self.assertNotIn("job_user", cfg["security"])

    def test_a_named_job_user_is_the_operator_s_and_not_asked(self):
        for block in ({"user": "pigeon-jobs"}, {"user": ""}, "odd"):
            trial = _Trial()
            with tempfile.TemporaryDirectory() as d:
                path = _seeded_config(d)
                with open(path, encoding="utf-8") as fh:
                    cfg = json.load(fh)
                cfg["security"]["job_user"] = block
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(cfg, fh)
                with open(path, "rb") as fh:
                    before = fh.read()
                applied, out = self._apply(path, probe=_Probe(),
                                           trial=trial)
                with open(path, "rb") as fh:
                    after = fh.read()
            self.assertEqual(applied, {}, block)
            self.assertEqual(before, after, block)
            self.assertEqual(trial.asked, [], block)
            self.assertNotIn("security.job_user names", out, block)

    def test_a_job_user_mode_stated_lower_is_not_asked(self):
        for mode in ("audit", "off"):
            trial = _Trial()
            with tempfile.TemporaryDirectory() as d:
                path = _seeded_config(d, modes={"job_user": mode})
                applied, out = self._apply(path, probe=_Probe(),
                                           trial=trial)
                security = self._security_in(path)
            self.assertEqual(applied, {}, mode)
            self.assertEqual(trial.asked, [], mode)
            self.assertNotIn("job_user", security, mode)
            self.assertIn("left at enforce", out, mode)

    def test_no_job_user_where_the_jail_is_not_on(self):
        # The second question follows a first one that passed: a
        # probe that did not pass, a mode the operator stated
        # down, and a seed that asked nothing each name no one.
        cases = (
            (_Probe(problem=_ROOT_REASON), None),
            (_Probe(), {"confinement": "audit"}),
            (None, None),
        )
        for probe, modes in cases:
            trial = _Trial()
            with tempfile.TemporaryDirectory() as d:
                path = _seeded_config(d, modes=modes)
                self._apply(path, probe=probe, trial=trial)
                security = self._security_in(path)
            self.assertEqual(trial.asked, [], (probe, modes))
            self.assertNotIn("job_user", security, (probe, modes))

    def test_a_named_platform_runs_no_trial_of_its_own(self):
        # A scripted probe and no scripted trial: nothing is run
        # on this machine for a platform the caller named.
        with mock.patch.object(INS, "freebsd_job_user_trial",
                               side_effect=AssertionError("run")):
            with tempfile.TemporaryDirectory() as d:
                path = _seeded_config(d)
                applied, out = self._apply(path, probe=_Probe())
                security = self._security_in(path)
        self.assertEqual(applied, {})
        self.assertNotIn("job_user", security)
        self.assertNotIn("security.job_user names", out)

    def test_a_freebsd_host_is_asked_through_the_door_trial(self):
        # On the machine itself the trial and the account are the
        # real ones, and who makes the account is the caller's
        # word: the installer says make, a seed that only writes
        # a config does not.
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        for make in (True, False):
            trial = _Trial()
            asked_to_make = []

            def _account(name=INS.FREEBSD_JOB_ACCOUNT, make=False):
                asked_to_make.append(make)
                if make:
                    return name, True, None
                return None, False, None
            with _machine_asked(), \
                    mock.patch.object(INS, "_HOST_PLATFORM",
                                      "freebsd14"), \
                    mock.patch.object(INS, "freebsd_job_user_trial",
                                      trial), \
                    mock.patch.object(INS, "freebsd_job_account",
                                      _account):
                user, door = INS.fresh_job_user(
                    cfg, (None, _PASS_LINES), make=make)
            self.assertEqual(asked_to_make, [make])
            want = "pigeon-jobs" if make else "nobody"
            self.assertEqual(user, want)
            self.assertEqual(trial.users(), [want])
            self.assertEqual(door["tried"], want)
            self.assertIsNone(door["problem"])
            self.assertEqual(door["lines"], _door_lines(want))
        # The installer is the caller that says make; the wizard's
        # seed is the one that does not.
        seen = []

        def _fresh(cfg, asked, platform=None, trial=None,
                   account=None, make=False):
            seen.append(make)
            return None, None
        with mock.patch.object(INS, "fresh_job_user", _fresh), \
                tempfile.TemporaryDirectory() as d:
            self._apply(_seeded_config(d), probe=_Probe())
        with mock.patch.object(SU, "_fresh_job_user", _fresh):
            SU.seed_platform_modes(
                {"security": {"modes": {"confinement": "enforce"}}},
                "freebsd14", probe=_Probe())
        self.assertEqual(seen, [True, False])

    def test_a_missing_config_takes_the_job_user_too(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            applied, _out = self._apply(path, probe=_Probe(),
                                        trial=_Trial())
            self.assertEqual(applied, {})
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {
                    "security": {"job_user": {"user": "nobody"}}})

    def test_a_later_run_names_no_second_user(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            self._apply(path, probe=_Probe(), trial=_Trial())
            with open(path, "rb") as fh:
                before = fh.read()
            trial = _Trial()
            applied, out = self._apply(path, probe=_Probe(),
                                       trial=trial)
            with open(path, "rb") as fh:
                after = fh.read()
        self.assertEqual(applied, {})
        self.assertEqual(before, after)
        self.assertEqual(trial.asked, [])
        self.assertIn("left at enforce", out)
        self.assertNotIn("security.job_user names", out)

    def test_the_trial_s_config_is_a_copy(self):
        cfg = {"security": {"confinement": {
            "extra_ro_binds": [["/srv/tools", "/tools"]]}}}
        bound = INS._seed_config_with(cfg, bind=["/x/shown", "/shown"])
        named = INS._seed_config_with(cfg, job_user="nobody")
        self.assertEqual(
            bound["security"]["confinement"]["extra_ro_binds"],
            [["/srv/tools", "/tools"], ["/x/shown", "/shown"]])
        self.assertEqual(named["security"]["job_user"],
                         {"user": "nobody"})
        self.assertEqual(cfg, {"security": {"confinement": {
            "extra_ro_binds": [["/srv/tools", "/tools"]]}}})
        # A config with no security block, or none at all.
        self.assertEqual(
            INS._seed_config_with(None, bind=["/a", "/b"]),
            {"security": {"confinement": {
                "extra_ro_binds": [["/a", "/b"]]}}})
        self.assertEqual(
            INS._seed_config_with({"security": "odd"},
                                  job_user="nobody"),
            {"security": {"job_user": {"user": "nobody"}}})

    # --- the account the installer makes -----------------------

    def _decide(self, account, trial=None, cfg=None):
        trial = trial if trial is not None else _Trial()
        cfg = cfg if cfg is not None else {
            "security": {"modes": {"confinement": "enforce"}}}
        removed = []

        def _remove(name):
            removed.append(name)
            return self.removal
        with mock.patch.object(INS, "freebsd_remove_job_account",
                               _remove):
            user, door = INS.fresh_job_user(
                cfg, (None, _PASS_LINES), "freebsd14", trial, account)
        return user, door, trial, removed

    removal = True

    def test_an_account_that_stands_is_named(self):
        account = _Account()
        user, door, trial, removed = self._decide(account)
        self.assertEqual(user, "pigeon-jobs")
        self.assertEqual(door, _door_record("pigeon-jobs"))
        self.assertEqual(trial.users(), ["pigeon-jobs"])
        self.assertEqual((account.calls, removed), (1, []))

    def test_an_account_the_seed_made_says_so(self):
        user, door, _trial, removed = self._decide(
            _Account(made=True))
        self.assertEqual(user, "pigeon-jobs")
        self.assertEqual(door["notes"], [
            "account pigeon-jobs made for the jail's jobs (pw "
            "useradd: no password, no login shell, no home "
            "directory)"])
        self.assertEqual(removed, [])

    def test_where_the_account_cannot_be_made_nobody_stands_in(self):
        why = "pw useradd exited 1: /etc is read-only"
        user, door, trial, removed = self._decide(
            _Account(user=None, why=why))
        self.assertEqual(user, "nobody")
        self.assertEqual(trial.users(), ["nobody"])
        self.assertEqual(door["notes"], [
            "account pigeon-jobs could not be made (%s)" % why,
            "nobody stands in"])
        self.assertEqual(door["lines"], _door_lines("nobody"))
        self.assertEqual(removed, [])
        # A maker that cannot answer is the same case.
        user, door, _trial, _removed = self._decide(
            _Account(error=OSError("no pw")))
        self.assertEqual(user, "nobody")
        self.assertEqual(door["notes"][0],
                         "account pigeon-jobs could not be made "
                         "(no pw)")

    def test_where_no_account_is_made_nobody_stands_in(self):
        # A seed that only writes a config: the account is not on
        # the machine and is not this seed's to make.
        user, door, trial, _removed = self._decide(
            _Account(user=None))
        self.assertEqual(user, "nobody")
        self.assertEqual(trial.users(), ["nobody"])
        self.assertEqual(door["notes"], [
            "account pigeon-jobs is not on this machine (the "
            "installer makes it)", "nobody stands in"])

    def test_an_account_made_and_not_usable_is_removed_again(self):
        trial = _Trial(problem={"pigeon-jobs": "jexec: no such user"})
        user, door, trial, removed = self._decide(
            _Account(made=True), trial)
        self.assertEqual(user, "nobody")
        self.assertEqual(trial.users(), ["pigeon-jobs", "nobody"])
        self.assertEqual(removed, ["pigeon-jobs"])
        self.assertEqual(door["notes"], [
            "account pigeon-jobs made for the jail's jobs (pw "
            "useradd: no password, no login shell, no home "
            "directory)",
            "a trial job as pigeon-jobs inside a jail on this "
            "machine did not pass: jexec: no such user",
            "account pigeon-jobs removed again",
            "nobody stands in"])
        # One that will not go is said, with the command.
        self.removal = False
        _user, door, _trial, _removed = self._decide(
            _Account(made=True),
            _Trial(problem={"pigeon-jobs": "no"}))
        self.assertEqual(
            door["notes"][2],
            "account pigeon-jobs could not be removed again (pw "
            "userdel -n pigeon-jobs removes it)")

    def test_an_account_that_was_there_is_never_removed(self):
        trial = _Trial(problem={"pigeon-jobs": "uid 0"})
        user, door, trial, removed = self._decide(_Account(), trial)
        self.assertEqual(user, "nobody")
        self.assertEqual(removed, [])
        self.assertEqual(door["notes"], [
            "a trial job as pigeon-jobs inside a jail on this "
            "machine did not pass: uid 0", "nobody stands in"])

    def test_where_no_trial_passes_no_one_is_named(self):
        trial = _Trial(problem="jail: gone")
        user, door, trial, removed = self._decide(
            _Account(made=True), trial)
        self.assertIsNone(user)
        self.assertEqual(removed, ["pigeon-jobs"])
        self.assertEqual((door["tried"], door["problem"],
                          door["lines"]),
                         ("nobody", "jail: gone", ()))
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            with mock.patch.object(INS, "freebsd_remove_job_account",
                                   return_value=True):
                applied, out = self._apply(
                    path, probe=_Probe(),
                    trial=_Trial(problem="jail: gone"),
                    account=_Account(made=True))
            security = self._security_in(path)
        self.assertEqual(applied, {})
        self.assertNotIn("job_user", security)
        lines = out.splitlines()
        self.assertIn("left at enforce", lines[0])
        self.assertEqual(lines[1:5], [
            "platform: account pigeon-jobs made for the jail's jobs "
            "(pw useradd: no password, no login shell, no home "
            "directory)",
            "platform: a trial job as pigeon-jobs inside a jail on "
            "this machine did not pass: jail: gone",
            "platform: account pigeon-jobs removed again",
            "platform: nobody stands in"])
        self.assertIn("security.job_user left unnamed in %s (a "
                      "trial job as nobody inside a jail on this "
                      "machine did not pass: jail: gone" % path,
                      lines[5])
        self.assertEqual(lines[6:],
                         ["platform: " + t for t in _PASS_LINES])

    def test_the_installer_writes_the_account_it_made(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            with open(path, encoding="utf-8") as fh:
                before = json.load(fh)
            account = _Account(made=True)
            applied, out = self._apply(path, probe=_Probe(),
                                       trial=_Trial(), account=account)
            with open(path, encoding="utf-8") as fh:
                after = json.load(fh)
            # A later run finds the name written and asks nothing.
            later = _Account(made=True)
            self._apply(path, probe=_Probe(), trial=_Trial(),
                        account=later)
        self.assertEqual(applied, {})
        self.assertEqual(after["security"]["job_user"],
                         {"user": "pigeon-jobs"})
        del after["security"]["job_user"]
        self.assertEqual(after, before)
        lines = out.splitlines()
        self.assertIn("left at enforce", lines[0])
        self.assertEqual(
            lines[1], "platform: account pigeon-jobs made for the "
            "jail's jobs (pw useradd: no password, no login shell, "
            "no home directory)")
        self.assertIn("security.job_user names pigeon-jobs in %s (a "
                      "trial job as pigeon-jobs inside a jail on "
                      "this machine passed" % path, lines[2])
        self.assertEqual(
            lines[3:],
            ["platform: " + t for t in _door_lines("pigeon-jobs")])
        self.assertEqual((account.calls, later.calls), (1, 0))

    def test_no_account_is_looked_for_where_nothing_is_asked(self):
        # The operator's own user, a mode stated down, a jail that
        # is not on: the account is not found, made or removed.
        cases = (
            ({"security": {"job_user": {"user": "mine"}}},
             (None, _PASS_LINES)),
            ({"security": {"modes": {"job_user": "audit"}}},
             (None, _PASS_LINES)),
            ({"security": {}}, (_ROOT_REASON, ())),
            ({"security": {}}, None),
        )
        for cfg, asked in cases:
            account = _Account(made=True)
            user, door = INS.fresh_job_user(
                cfg, asked, "freebsd14", _Trial(), account)
            self.assertEqual((user, door, account.calls),
                             (None, None, 0), (cfg, asked))

    # --- finding and making the account ------------------------

    def _pw(self, exists=(), results=()):
        """Script the user database and pw(8): `exists` answers
        each lookup in turn (the last one repeats), `results`
        each pw command."""
        state = {"lookups": list(exists) or [False],
                 "results": list(results), "ran": []}

        def _ids(name):
            found = state["lookups"][0]
            if len(state["lookups"]) > 1:
                state["lookups"].pop(0)
            if not found:
                raise KeyError(name)
            return (1001, 1001)

        def _run(args):
            state["ran"].append(list(args))
            return state["results"].pop(0) if state["results"] \
                else (0, "")
        return state, mock.patch.object(INS, "_user_ids", _ids), \
            mock.patch.object(INS, "_run_pw", _run)

    def test_an_account_already_there_is_used_as_it_stands(self):
        for make in (True, False):
            state, ids, run = self._pw(exists=[True])
            with ids, run:
                self.assertEqual(
                    INS.freebsd_job_account(make=make),
                    ("pigeon-jobs", False, None))
            self.assertEqual(state["ran"], [])

    def test_no_account_is_made_unless_asked(self):
        state, ids, run = self._pw(exists=[False])
        with ids, run:
            self.assertEqual(INS.freebsd_job_account(),
                             (None, False, None))
        self.assertEqual(state["ran"], [])

    def test_the_account_is_made_with_nothing_to_log_in_with(self):
        state, ids, run = self._pw(exists=[False, True])
        with ids, run:
            self.assertEqual(INS.freebsd_job_account(make=True),
                             ("pigeon-jobs", True, None))
        # No password, a shell that lets no one in, a home that
        # is not there and is not made (no -m), and no group
        # named: pw makes the account one of its own.
        self.assertEqual(state["ran"], [[
            "useradd", "-n", "pigeon-jobs",
            "-c", "homing-pigeon jobs", "-d", "/nonexistent",
            "-s", "/usr/sbin/nologin", "-w", "no"]])
        self.assertNotIn("-m", state["ran"][0])
        self.assertNotIn("-g", state["ran"][0])
        self.assertNotIn("-G", state["ran"][0])

    def test_a_pw_that_fails_is_a_reason(self):
        cases = (
            ((65, "pw: user 'x' disappeared"),
             "pw useradd exited 65: pw: user 'x' disappeared"),
            ((127, "/usr/sbin/pw could not be run: [Errno 2] no"),
             "/usr/sbin/pw could not be run: [Errno 2] no"),
        )
        for result, why in cases:
            state, ids, run = self._pw(exists=[False],
                                       results=[result])
            with ids, run:
                self.assertEqual(
                    INS.freebsd_job_account(make=True),
                    (None, False, why))
        # pw says done and the account is not there.
        state, ids, run = self._pw(exists=[False, False])
        with ids, run:
            user, made, why = INS.freebsd_job_account(make=True)
        self.assertEqual((user, made), (None, False))
        self.assertIn("not in the user database", why)

    def test_removing_the_account_is_judged_by_the_database(self):
        state, ids, run = self._pw(exists=[False])
        with ids, run:
            self.assertTrue(INS.freebsd_remove_job_account("hp-x"))
        self.assertEqual(state["ran"], [["userdel", "-n", "hp-x"]])
        state, ids, run = self._pw(exists=[True])
        with ids, run:
            self.assertFalse(INS.freebsd_remove_job_account("hp-x"))

    def test_pw_is_run_by_its_path_and_answers_or_says_why(self):
        calls = []

        def _run(argv, **kw):
            calls.append((argv, kw))
            return types.SimpleNamespace(returncode=3,
                                         stderr=b"pw: no\n")
        with mock.patch.object(INS.subprocess, "run", _run):
            self.assertEqual(INS._run_pw(["usershow", "x"]),
                             (3, "pw: no"))
        self.assertEqual(calls[0][0], ["/usr/sbin/pw", "usershow", "x"])
        self.assertEqual(calls[0][1]["stdin"], subprocess.DEVNULL)
        with mock.patch.object(INS.subprocess, "run",
                               side_effect=OSError("no such file")):
            code, said = INS._run_pw(["usershow", "x"])
        self.assertEqual(code, 127)
        self.assertEqual(said, "/usr/sbin/pw could not be run: "
                               "no such file")

    def test_uninstall_says_the_account_stays(self):
        done = types.SimpleNamespace(returncode=0, stdout="")
        for there in (True, False):
            state, ids, run = self._pw(exists=[there])
            out = io.StringIO()
            with ids, run, redirect_stdout(out), \
                    mock.patch.object(INS.subprocess, "run",
                                      return_value=done):
                INS.uninstall_freebsd()
            said = out.getvalue()
            self.assertEqual(
                "the jobs account pigeon-jobs is left in place; "
                "`pw userdel -n pigeon-jobs` removes it" in said,
                there)
            # Uninstall removes no account.
            self.assertEqual(state["ran"], [])

    # --- the door trial itself ---------------------------------

    def _door(self, out=b"65534\nWORK-OK\nPROCS 256\nEND\n", err=b"",
              ids=(65534, 65534), spawn_error=None, wait_error=None,
              backend="scripted", cfg=None, ceiling=256):
        """Run the trial against a scripted backend; return its
        answer and what the backend saw. `ceiling` is what the
        backend says it holds a job user's processes to (an
        exception is raised in its place)."""
        seen = {"spawned": [], "closed": 0, "posture": [],
                "ceiling": []}

        class _Job:
            def communicate(self, timeout=None):
                seen["timeout"] = timeout
                if wait_error is not None:
                    raise wait_error
                return out, err

            def close(self):
                seen["closed"] += 1

        def _spawn(argv, cwd=None, env=None, user=None, cfg=None):
            binds = cfg["security"]["confinement"]["extra_ro_binds"]
            shown = binds[-1][0]
            secret = os.path.join(shown, "root-only")
            seen["spawned"].append({
                "argv": argv, "cwd": cwd, "env": env, "user": user,
                "binds": binds, "work_is_dir": os.path.isdir(cwd),
                "secret_mode": os.stat(secret).st_mode & 0o777,
                "folder": os.path.dirname(shown)})
            if spawn_error is not None:
                raise spawn_error
            return _Job()

        def _posture(cfg=None):
            seen["posture"].append(cfg)
            return [("OK", t) for t in _DOOR_LINES]

        def _ceiling(cfg=None, user=None):
            seen["ceiling"].append((cfg, user))
            if isinstance(ceiling, Exception):
                raise ceiling
            return ceiling

        if backend == "scripted":
            backend = types.SimpleNamespace(
                IS_FREEBSD_BACKEND=True,
                spawn_confined_process=_spawn,
                posture_lines=_posture,
                job_user_process_ceiling=_ceiling)

        def _ids(user):
            if ids is None:
                raise KeyError(user)
            return ids
        given = []
        with mock.patch.object(INS, "_import_freebsd_confine",
                               return_value=backend), \
                mock.patch.object(INS, "_user_ids", _ids), \
                mock.patch.object(
                    INS, "_posix_chown",
                    lambda path, uid, gid: given.append(
                        (os.path.basename(path), uid, gid))):
            answer = INS.freebsd_job_user_trial(
                cfg if cfg is not None else {}, "nobody")
        seen["given"] = given
        return answer, seen

    def test_the_trial_job_goes_in_as_the_user_and_passes(self):
        cfg = {"security": {"confinement": {
            "extra_ro_binds": [["/srv/tools", "/tools"]]}}}
        answer, seen = self._door(cfg=cfg)
        self.assertEqual(answer, (None, _DOOR_LINES))
        (job,) = seen["spawned"]
        self.assertEqual(job["argv"],
                         ["/bin/sh", "-c", INS._DOOR_SCRIPT])
        self.assertEqual(job["user"], "nobody")
        self.assertEqual(job["env"], {})
        # Its work directory was handed to the user, and the tree
        # with the root-only file was shown beside the operator's
        # own binds.
        self.assertTrue(job["work_is_dir"])
        self.assertEqual(seen["given"], [("work", 65534, 65534)])
        self.assertEqual(job["binds"][0], ["/srv/tools", "/tools"])
        self.assertEqual(job["binds"][-1][1], INS._DOOR_MOUNT)
        if os.name != "nt":
            self.assertEqual(job["secret_mode"], 0o600)
        # The job was released, nothing of the trial is left, and
        # the caller's config is as it was.
        self.assertEqual(seen["closed"], 1)
        self.assertFalse(os.path.exists(job["folder"]))
        self.assertEqual(cfg["security"]["confinement"][
            "extra_ro_binds"], [["/srv/tools", "/tools"]])
        # The lines are the report's for the config with the user
        # named.
        (named,) = seen["posture"]
        self.assertEqual(named["security"]["job_user"],
                         {"user": "nobody"})
        # The backend was asked what it holds this user to under
        # the very config the trial's jail was built from.
        ((asked_cfg, asked_user),) = seen["ceiling"]
        self.assertEqual(asked_user, "nobody")
        self.assertEqual(
            asked_cfg["security"]["confinement"]["extra_ro_binds"],
            job["binds"])

    def test_the_trial_job_reads_its_ceiling_and_tries_to_raise_it(self):
        # What the job is told to do: the limit is read as the
        # hard one, the one that takes privilege to raise, and
        # the raise is tried where a refusal ends a subshell.
        script = INS._DOOR_SCRIPT
        self.assertIn("printf 'PROCS '; ulimit -H -u;", script)
        self.assertIn("( ulimit -H -u unlimited ) 2>/dev/null "
                      "&& echo PROCS-RAISED;", script)
        self.assertTrue(script.endswith("echo END"))
        self.assertLess(script.index("READ-ROOT"),
                        script.index("PROCS"))
        # The number is the backend's for this config and user.
        for ceiling, out in ((256, b"65534\nWORK-OK\nPROCS 256\nEND\n"),
                             (24, b"65534\nWORK-OK\nPROCS 24\nEND\n")):
            answer, _seen = self._door(out=out, ceiling=ceiling)
            self.assertEqual(answer, (None, _DOOR_LINES), ceiling)

    def test_what_the_trial_job_must_show(self):
        cases = (
            (b"0\nWORK-OK\nPROCS 256\nEND\n",
             "ran as uid 0, not as nobody"),
            (b"65534\nPROCS 256\nEND\n",
             "could not write its work mount"),
            (b"65534\nWORK-OK\nROOT-ONLY\nREAD-ROOT\nPROCS 256\nEND\n",
             "read a root-only file as nobody"),
            (b"65534\nWORK-OK\nPROCS 256\n",
             "did not finish: jexec: gone"),
            (b"", "did not finish: jexec: gone"),
            # the ceiling: not there, another number, no number,
            # the kernel's own limit showing through, and raised
            (b"65534\nWORK-OK\nEND\n",
             "read its process ceiling as nothing, not the 256 "
             "this config holds nobody to"),
            (b"65534\nWORK-OK\nPROCS 5547\nEND\n",
             "read its process ceiling as 5547, not the 256 this "
             "config holds nobody to"),
            (b"65534\nWORK-OK\nPROCS unlimited\nEND\n",
             "read its process ceiling as unlimited, not the 256"),
            (b"65534\nWORK-OK\nPROCS\nEND\n",
             "read its process ceiling as nothing, not the 256"),
            (b"65534\nWORK-OK\nPROCS\nPROCS-RAISED\nEND\n",
             "read its process ceiling as nothing, not the 256"),
            (b"65534\nWORK-OK\nPROCS 256\nPROCS-RAISED\nEND\n",
             "raised its process ceiling as nobody"),
        )
        for out, expect in cases:
            with self.subTest(expect=expect, out=out):
                (problem, lines), seen = self._door(
                    out=out, err=b"jexec: gone\n")
                self.assertIn(expect, problem)
                self.assertEqual(lines, ())
                self.assertEqual(seen["closed"], 1)
                self.assertFalse(
                    os.path.exists(seen["spawned"][0]["folder"]))

    def test_a_trial_that_cannot_run_is_a_reason(self):
        (problem, lines), seen = self._door(
            spawn_error=RuntimeError("jail: no such tool"))
        self.assertEqual(problem, "the trial job could not be run: "
                                  "jail: no such tool")
        self.assertEqual(lines, ())
        self.assertFalse(os.path.exists(seen["spawned"][0]["folder"]))
        # A ceiling the backend cannot give this config is the
        # reason, in the backend's words, and no job is started.
        (problem, lines), seen = self._door(ceiling=RuntimeError(
            "security.confinement.freebsd.job_user_processes (9000) "
            "is above the most processes this host lets any one "
            "user hold"))
        self.assertIn("the trial job could not be run: security."
                      "confinement.freebsd.job_user_processes (9000)",
                      problem)
        self.assertEqual(lines, ())
        self.assertEqual(seen["spawned"], [])
        self.assertEqual(
            [n for n in os.listdir(tempfile.gettempdir())
             if n.startswith("hp-seed-door-")], [])
        # A job that never ends is released and named.
        (problem, _lines), seen = self._door(
            wait_error=subprocess.TimeoutExpired("jexec", 30))
        self.assertIn("could not be run", problem)
        self.assertEqual(seen["closed"], 1)
        self.assertEqual(seen["timeout"], 30)
        self.assertFalse(os.path.exists(seen["spawned"][0]["folder"]))

    def test_a_user_the_machine_cannot_use_is_a_reason(self):
        (problem, _lines), seen = self._door(ids=None)
        self.assertIn("nobody is not in this machine's user "
                      "database", problem)
        self.assertEqual(seen["spawned"], [])
        (problem, _lines), seen = self._door(ids=(0, 0))
        self.assertEqual(problem, "nobody is uid 0 on this machine")
        self.assertEqual(seen["spawned"], [])

    def test_no_backend_no_trial(self):
        for backend in (None,
                        types.SimpleNamespace(IS_FREEBSD_BACKEND=False)):
            (problem, lines), seen = self._door(backend=backend)
            self.assertIn("could not be loaded", problem)
            self.assertEqual(lines, ())

    def test_a_pass_stands_without_the_report_s_lines(self):
        backend = types.SimpleNamespace(IS_FREEBSD_BACKEND=True)

        class _Job:
            def communicate(self, timeout=None):
                return b"65534\nWORK-OK\nPROCS 256\nEND\n", b""

            def close(self):
                pass
        backend.spawn_confined_process = lambda *a, **k: _Job()
        backend.job_user_process_ceiling = lambda *a, **k: 256

        def _posture(cfg=None):
            raise RuntimeError("no sysctl")
        backend.posture_lines = _posture
        answer, _seen = self._door(backend=backend)
        self.assertEqual(answer, (None, ()))

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
        # The probe's answer, and no job user: with a platform
        # named and no trial handed in, the second question is
        # not put.
        self.assertEqual(answers, [((None, _PASS_LINES), None, None)])
        self.assertNotIn("job_user", cfg["security"])
        answers = []
        stated = SU.seed_platform_modes(
            cfg, "freebsd14", probe=_Probe(problem=_ROOT_REASON),
            asked=answers)
        self.assertEqual(stated, {"confinement": "audit"})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        self.assertEqual(answers, [((_ROOT_REASON, ()), None, None)])

    def test_the_wizard_s_seed_names_the_job_user_too(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        answers = []
        stated = SU.seed_platform_modes(
            cfg, "freebsd14", probe=_Probe(), asked=answers,
            trial=_Trial())
        self.assertEqual(stated, {})
        self.assertEqual(cfg["security"]["job_user"],
                         {"user": "nobody"})
        self.assertEqual(cfg["security"]["modes"], {
            "confinement": "enforce", "job_user": "enforce"})
        self.assertEqual(answers, [(
            (None, _PASS_LINES), "nobody", _door_record("nobody"))])
        # A trial that does not pass names no one, and its reason
        # rides back.
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        answers = []
        SU.seed_platform_modes(
            cfg, "freebsd14", probe=_Probe(), asked=answers,
            trial=_Trial(problem="no door"))
        self.assertNotIn("job_user", cfg["security"])
        self.assertEqual(answers, [(
            (None, _PASS_LINES), None,
            _door_record("nobody", problem="no door"))])
        # The account, where one is handed in: found and named.
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        SU.seed_platform_modes(
            cfg, "freebsd14", probe=_Probe(), trial=_Trial(),
            account=_Account())
        self.assertEqual(cfg["security"]["job_user"],
                         {"user": "pigeon-jobs"})

    def _fresh_wizard(self, statement, job_user=(None, None)):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            out = io.StringIO()
            with mock.patch.object(SU, "_fresh_platform_modes",
                                   return_value=statement), \
                 mock.patch.object(SU, "_fresh_job_user",
                                   return_value=job_user), \
                 mock.patch("builtins.input", side_effect=[
                     "runner@example.com", "", "my-client-id", "y"]), \
                 mock.patch.object(SU, "browser_consent",
                                   return_value="refresh-123"), \
                 mock.patch.object(SU, "_mailbox_probe",
                                   return_value=None), \
                 redirect_stdout(out):
                SU.run_setup_wizard(path)
            with open(path, encoding="utf-8") as fh:
                security = json.load(fh)["security"]
            return security, out.getvalue(), path

    def test_the_wizard_says_the_jail_stays_on(self):
        security, out, path = self._fresh_wizard(
            ({}, (None, _PASS_LINES)))
        self.assertEqual(security["modes"]["confinement"], "enforce")
        self.assertNotIn("job_user", security)
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, out)
        self.assertIn("platform: " + _PASS_LINES[0], out)
        self.assertNotIn("stated as audit", out)

    def test_the_wizard_says_who_the_jobs_go_in_as(self):
        security, out, path = self._fresh_wizard(
            ({}, (None, _PASS_LINES)),
            job_user=("nobody", _door_record("nobody", notes=[
                "account pigeon-jobs is not on this machine (the "
                "installer makes it)", "nobody stands in"])))
        self.assertEqual(security["modes"]["confinement"], "enforce")
        self.assertEqual(security["job_user"], {"user": "nobody"})
        self.assertIn("security.job_user names nobody in %s" % path,
                      out)
        self.assertIn("platform: " + _DOOR_LINES[1], out)
        self.assertNotIn("no_superuser", out)
        # What became of the account is said before the name.
        lines = [ln for ln in out.splitlines()
                 if ln.startswith("platform: ")]
        self.assertEqual(lines[1:3], [
            "platform: account pigeon-jobs is not on this machine "
            "(the installer makes it)",
            "platform: nobody stands in"])
        self.assertIn("security.job_user names nobody", lines[3])

    def test_the_wizard_says_why_the_jail_is_stated_down(self):
        security, out, path = self._fresh_wizard(
            ({"confinement": "audit"}, (_ROOT_REASON, ())))
        self.assertEqual(security["modes"]["confinement"], "audit")
        self.assertNotIn("job_user", security)
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


class SeedSwitchTest(unittest.TestCase):
    """The switch that keeps the seed's questions off the machine.

    The suite drives the installer and the wizard on whatever
    host it runs on. On a FreeBSD host, as root, the seed's
    questions build a jail and the installer makes an account:
    an install changing its machine, which a test run is not.
    The word is carried in the environment, so every copy of the
    installer a test loads and every process a test starts reads
    the same one."""

    class _Doors:
        """The three doors to the machine, as ones that count."""

        def __init__(self):
            self.probe, self.trial = _Probe(), _Trial()
            self.made = []

        def account(self, name=INS.FREEBSD_JOB_ACCOUNT, make=False):
            self.made.append(make)
            return name, bool(make), None

        def reached(self):
            return [what for what, calls in (
                ("probe", self.probe.asked), ("trial", self.trial.asked),
                ("account", self.made)) if calls]

    @contextlib.contextmanager
    def _on_a_freebsd_host(self, word, module=INS):
        """`module`'s seed as it stands on a FreeBSD host with
        `word` in the environment (None: the word unset), its
        doors to the machine counting."""
        doors = self._Doors()
        with contextlib.ExitStack() as stack:
            if word is None:
                env = stack.enter_context(mock.patch.dict(os.environ))
                env.pop(INS.SEED_SWITCH, None)
            else:
                stack.enter_context(_machine_asked(word))
            stack.enter_context(mock.patch.object(
                module, "_HOST_PLATFORM", "freebsd14"))
            stack.enter_context(mock.patch.object(
                module.sys, "platform", "freebsd14"))
            stack.enter_context(mock.patch.object(
                module, "freebsd_seed_probe", doors.probe))
            stack.enter_context(mock.patch.object(
                module, "freebsd_job_user_trial", doors.trial))
            stack.enter_context(mock.patch.object(
                module, "freebsd_job_account", doors.account))
            yield doors

    # --- the word ------------------------------------------------

    def test_the_questions_are_on_unless_a_word_says_off(self):
        asks = INS.seed_asks_the_machine
        self.assertTrue(asks({}))
        for word in ("1", "yes", "on", "true", "", " ", "2", "enforce"):
            self.assertTrue(asks({INS.SEED_SWITCH: word}), repr(word))
        for word in ("0", "no", "off", "false", "OFF", "No", " 0 ",
                     "False\n"):
            self.assertFalse(asks({INS.SEED_SWITCH: word}), repr(word))
        self.assertEqual(INS.SEED_SWITCH, "HP_SEED_ASKS_MACHINE")
        # with nothing handed in it reads this process's environment
        with _machine_asked("0"):
            self.assertFalse(asks())
        with _machine_asked("1"):
            self.assertTrue(asks())

    def test_the_suite_runs_with_the_questions_off(self):
        # runner/tests/__init__.py sets the word for the run and
        # leaves a word the environment already carries
        self.assertIn(INS.SEED_SWITCH, os.environ)
        ask = ("import os, runner.tests; "
               "print(os.environ[%r])" % INS.SEED_SWITCH)
        for carried, want in ((None, "0"), ("1", "1"), ("0", "0"),
                              ("off", "off")):
            env = dict(os.environ)
            env.pop(INS.SEED_SWITCH, None)
            if carried is not None:
                env[INS.SEED_SWITCH] = carried
            out = subprocess.run(
                [sys.executable, "-c", ask], cwd=_REPO, env=env,
                capture_output=True, text=True, timeout=120)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), want, carried)

    def test_a_process_a_test_starts_reads_the_same_word(self):
        # the environment is what a child inherits: an installer
        # a test runs as a program is switched off with the rest
        out = subprocess.run(
            [sys.executable, "-I", "-c",
             "import os; print(os.environ.get(%r))" % INS.SEED_SWITCH],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), os.environ[INS.SEED_SWITCH])

    # --- the seed, switched off ------------------------------------

    def test_switched_off_a_freebsd_host_is_asked_nothing(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        for word in ("0", "off"):
            with self._on_a_freebsd_host(word) as doors:
                modes, asked = INS.fresh_platform_modes(cfg)
                # and the second question is not put either, even
                # behind a first one that passed
                user, door = INS.fresh_job_user(
                    cfg, (None, _PASS_LINES), make=True)
            self.assertEqual(modes, {"confinement": "audit"})
            self.assertEqual(asked, (INS.SEED_NOT_ASKED, ()))
            self.assertEqual((user, door), (None, None))
            self.assertEqual(doors.reached(), [], word)

    def test_switched_on_or_unset_the_same_host_is_asked(self):
        # the installer as an operator runs it: no word in the
        # environment, and the machine is asked
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        for word in (None, "1"):
            with self._on_a_freebsd_host(word) as doors:
                modes, asked = INS.fresh_platform_modes(cfg)
                user, door = INS.fresh_job_user(cfg, asked, make=True)
            self.assertEqual(modes, {}, word)
            self.assertEqual(asked, (None, _PASS_LINES))
            self.assertEqual(user, "pigeon-jobs")
            self.assertEqual(doors.reached(),
                             ["probe", "trial", "account"], word)
            self.assertEqual(doors.made, [True])

    def test_the_installer_says_the_machine_was_not_asked(self):
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            out = io.StringIO()
            with self._on_a_freebsd_host("0") as doors, \
                    redirect_stdout(out):
                applied = INS.apply_platform_modes(path)
            with open(path, encoding="utf-8") as fh:
                security = json.load(fh)["security"]
        self.assertEqual(doors.reached(), [])
        self.assertEqual(applied, {"confinement": "audit"})
        self.assertEqual(security["modes"]["confinement"], "audit")
        self.assertNotIn("job_user", security)
        said = out.getvalue()
        self.assertIn(
            "platform: security.modes.confinement stated as audit in "
            "%s (this machine was not asked: HP_SEED_ASKS_MACHINE is "
            "off in the environment; the mode is stated in the file "
            "rather than left to refuse the first start)" % path, said)
        # a probe that was not asked did not fail
        self.assertNotIn("did not pass", said)
        self.assertNotIn("left at enforce", said)
        self.assertNotIn("pigeon-jobs", said)

    def test_the_wizard_s_seed_is_switched_off_with_it(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        answers = []
        with self._on_a_freebsd_host("0") as doors:
            SU.seed_platform_modes(cfg, asked=answers)
        self.assertEqual(doors.reached(), [])
        self.assertEqual(cfg["security"]["modes"]["confinement"], "audit")
        self.assertNotIn("job_user", cfg["security"])
        self.assertEqual(answers, [((INS.SEED_NOT_ASKED, ()), None, None)])
        self.assertEqual(
            INS.seed_reason(answers[0][0], "confinement", "the default"),
            INS.SEED_NOT_ASKED)
        # another feature's reason is its own
        self.assertEqual(
            INS.seed_reason(answers[0][0], "job_user", "the default"),
            "the default")

    def test_the_pages_give_the_switch_as_it_is_read(self):
        # The operator's page quotes the line a switched-off seed
        # prints and names the words that switch it; the design
        # page names the switch. The line is the seed's own.
        with open(os.path.join(_REPO, "docs", "steady", "security",
                               "freebsd.md"), encoding="utf-8") as fh:
            page = fh.read()
        with open(os.path.join(_REPO, "docs", "steady", "design",
                               "freebsd-confinement-design.md"),
                  encoding="utf-8") as fh:
            design = fh.read()
        with tempfile.TemporaryDirectory() as d:
            path = _seeded_config(d)
            out = io.StringIO()
            with self._on_a_freebsd_host("0"), redirect_stdout(out):
                INS.apply_platform_modes(path)
        printed = [
            line.replace(path, "/root/.homing-pigeon/config.json")
            for line in out.getvalue().splitlines()
            if line.startswith("platform: ")]
        self.assertEqual(len(printed), 1, printed)
        self.assertIn("\n  " + printed[0] + "\n", page)
        self.assertIn("`%s=0`" % INS.SEED_SWITCH, page)
        for text in (page, design):
            for word in INS.SEED_SWITCH_OFF:
                self.assertIn("`%s`" % word, text)
        self.assertIn("`%s`" % INS.SEED_SWITCH, design)

    def test_a_door_handed_in_is_still_the_one_asked(self):
        # the switch closes the doors to the machine; a test that
        # hands in a door of its own is asking that door
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        probe, trial = _Probe(), _Trial()
        with self._on_a_freebsd_host("0") as doors:
            modes, asked = INS.fresh_platform_modes(cfg, probe=probe)
            user, door = INS.fresh_job_user(cfg, asked, trial=trial)
        self.assertEqual(asked, (None, _PASS_LINES))
        self.assertEqual(user, "nobody")
        self.assertEqual(len(probe.asked), 1)
        self.assertEqual(trial.users(), ["nobody"])
        self.assertEqual(doors.reached(), [])

    # --- every copy of the installer -------------------------------

    def _copy(self, name):
        """install.py loaded again under `name`, as the installer's
        own test modules load it: a module of its own, with its
        own doors."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, _INSTALL_PY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_every_copy_of_the_installer_reads_the_one_word(self):
        copy = self._copy("install_loaded_again_for_the_switch")
        self.assertIsNot(copy, INS)
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        with self._on_a_freebsd_host("0", copy) as doors:
            modes, asked = copy.fresh_platform_modes(cfg)
            user, door = copy.fresh_job_user(
                cfg, (None, _PASS_LINES), make=True)
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertEqual(asked, (copy.SEED_NOT_ASKED, ()))
        self.assertEqual((user, door), (None, None))
        self.assertEqual(doors.reached(), [])
        # and asked, the copy asks through its own doors
        with self._on_a_freebsd_host("1", copy) as doors:
            modes, asked = copy.fresh_platform_modes(cfg)
        self.assertEqual(doors.reached(), ["probe"])

    def _installer_main(self, word):
        """The installer's own main with its service steps
        replaced -- the way other modules' tests run it -- on a
        FreeBSD host whose probe would pass."""
        sides = ("install_files", "ensure_shared_secret",
                 "store_additional_secret", "install_ollama_and_model",
                 "apply_profile", "apply_instruction_flags",
                 "install_freebsd", "uninstall_freebsd")
        with tempfile.TemporaryDirectory() as d, \
                self._on_a_freebsd_host(word) as doors, \
                contextlib.ExitStack() as stack:
            for name in sides:
                stack.enter_context(mock.patch.object(INS, name))
            stack.enter_context(mock.patch.object(
                sys.stdin, "isatty", return_value=False))
            stack.enter_context(mock.patch.object(sys, "argv", [
                "install", "--dir", d, "--no-inference", "--no-profile"]))
            out = io.StringIO()
            with redirect_stdout(out):
                code = INS.main()
            installs = INS.install_freebsd.call_count
        return code, out.getvalue(), doors, installs

    def test_an_installer_run_as_another_module_runs_it_asks_nothing(self):
        # The shape that reaches pw(8) from another module's test
        # on a FreeBSD host, as root: main() with the service
        # steps replaced and the seed left as it is. Under the
        # suite's word the seed states audit and no door is
        # reached.
        code, said, doors, installs = self._installer_main("0")
        self.assertEqual(code, 0, said)
        self.assertEqual(installs, 1)
        self.assertEqual(doors.reached(), [])
        self.assertIn("this machine was not asked", said)
        self.assertNotIn("pigeon-jobs", said)

    def test_the_same_run_asks_and_makes_where_the_word_is_on(self):
        # what the switch is there for: the same call, asked, goes
        # through all three doors and tells the account door to
        # make
        code, said, doors, installs = self._installer_main("1")
        self.assertEqual(code, 0, said)
        self.assertEqual(installs, 1)
        self.assertEqual(doors.reached(), ["probe", "trial", "account"])
        self.assertEqual(doors.made, [True])
        self.assertIn("security.job_user names pigeon-jobs", said)


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
        # As Popen's: a process already collected keeps its
        # answer.
        self.waited = True
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


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
        # kern.maxprocperuid; None is a host that will not say.
        self.per_user = 5547

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
            if argv[-1] == "kern.maxprocperuid":
                if self.per_user is None:
                    return (1, "", "sysctl: unknown oid")
                return (0, "%s\n" % self.per_user, "")
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
        self.assertIsNone(st["job_user_processes"])
        for cfg in (None, [], {"security": None},
                    {"security": {"confinement": None}}):
            self.assertEqual(FC.confinement_settings(cfg), st, cfg)

    def test_the_freebsd_block_is_read(self):
        st = FC.confinement_settings(_fcfg(
            loopback=True, process_memory_bytes=1 << 30,
            tmp_bytes=1 << 20, job_memory_bytes=1 << 31,
            job_processes=32, job_user_processes=48))
        self.assertIs(st["loopback"], True)
        self.assertEqual(st["process_memory_bytes"], 1 << 30)
        self.assertEqual(st["tmp_bytes"], 1 << 20)
        self.assertEqual(st["job_memory_bytes"], 1 << 31)
        self.assertEqual(st["job_processes"], 32)
        self.assertEqual(st["job_user_processes"], 48)
        self.assertEqual(FC.FREEBSD_KEYS[-1], "job_user_processes")

    def test_a_malformed_freebsd_block_is_a_config_error(self):
        bad = ([], "x", 3,
               {"lopback": True},
               {"loopback": "yes"}, {"loopback": 1},
               {"job_processes": 0}, {"job_processes": -4},
               {"job_processes": True}, {"job_processes": "64"},
               {"tmp_bytes": 1.5}, {"process_memory_bytes": None},
               {"job_memory_bytes": [1]},
               {"job_user_processes": 0}, {"job_user_processes": -1},
               {"job_user_processes": "256"},
               {"job_user_processes": True},
               {"job_user_processes": 25.5},
               {"job_user_proceses": 256})
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
        S.validate_security_config(_fcfg(job_user_processes=64))
        with self.assertRaises(RuntimeError) as caught:
            S.validate_security_config(_fcfg(job_user_processes=0))
        self.assertIn(
            "security.confinement.freebsd.job_user_processes must "
            "be a positive integer", str(caught.exception))

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
        # The paths below describe a FreeBSD host, not the host
        # the suite runs on. That host's own links -- a /home or
        # a /tmp that leads elsewhere, as on macOS -- are not the
        # subject, so a path resolves to itself here unless a
        # test scripts a link of its own.
        resolved = mock.patch.object(
            FC._sandbox.os.path, "realpath",
            side_effect=lambda path, *a, **k: path)
        resolved.start()
        self.addCleanup(resolved.stop)
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

    def test_a_home_under_an_alias_spelling_is_never_mounted(self):
        # Q192: the jail backend shares sandbox.interpreter_binds,
        # so a host whose /home links elsewhere (the Darwin
        # firmlink shape, scripted here) mounts the bin
        # directory alone -- the alias candidate names no home.
        def _real(path, *args, **kwargs):
            if path == "/home" or path.startswith("/home/"):
                return "/System/Volumes/Data/home" + path[len("/home"):]
            return path
        with mock.patch.object(FC._sandbox.os.path, "realpath", _real):
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


class CeilingTest(_FakeHostCase):
    """The ceiling on the processes of the job user: who has
    one, what number it is, and the config that cannot have
    the one it names."""

    def ceiling(self, cfg=None, user="pigeon-jobs"):
        return FC.job_user_ceiling(
            self.host, FC.confinement_settings(cfg), user)

    def test_a_job_user_is_held_to_the_default(self):
        self.assertEqual(self.ceiling(), 256)
        self.assertEqual(FC.DEFAULT_JOB_USER_PROCESSES, 256)
        # Whoever the user is: the count is that account's.
        self.assertEqual(self.ceiling(user="nobody"), 256)
        # RACCT has no part in it.
        self.host.racct = True
        self.assertEqual(self.ceiling(), 256)
        self.assertEqual(self.host.ran(FC.RCTL_BIN), [])

    def test_a_job_with_no_job_user_has_none(self):
        self.assertIsNone(self.ceiling(user=None))
        # and the host is not asked anything for it
        self.assertEqual(
            self.host.ran(FC.SYSCTL_BIN, "kern.maxprocperuid"), [])

    def test_the_number_is_the_config_s(self):
        self.assertEqual(self.ceiling(_fcfg(job_user_processes=24)), 24)
        self.assertEqual(self.ceiling(_fcfg(job_user_processes=1)), 1)
        self.assertEqual(
            self.ceiling(_fcfg(job_user_processes=5547)), 5547)

    def test_the_default_follows_a_host_that_holds_fewer(self):
        # The kernel's own limit on one user's processes is the
        # most a limit at the door can ask for.
        self.host.per_user = 100
        self.assertEqual(self.ceiling(), 100)
        self.host.per_user = 256
        self.assertEqual(self.ceiling(), 256)
        self.host.per_user = 9000
        self.assertEqual(self.ceiling(), 256)

    def test_a_host_that_will_not_say_gets_the_default(self):
        for answer in (None, "", "many", "0", "-3"):
            with self.subTest(answer=answer):
                self.host.per_user = answer
                self.assertIsNone(FC._processes_per_user(self.host))
                self.assertEqual(self.ceiling(), 256)
                self.assertEqual(
                    self.ceiling(_fcfg(job_user_processes=9000)), 9000)
        self.host.per_user = 5547
        self.assertEqual(FC._processes_per_user(self.host), 5547)

    def test_a_number_above_the_host_s_own_is_refused_by_name(self):
        with self.assertRaises(RuntimeError) as caught:
            self.ceiling(_fcfg(job_user_processes=5548))
        text = str(caught.exception)
        self.assertIn(
            "security.confinement.freebsd.job_user_processes (5548) "
            "is above the most processes this host lets any one "
            "user hold (kern.maxprocperuid is 5547)", text)
        self.assertIn("Lower the setting or raise kern.maxprocperuid",
                      text)

    def test_a_number_with_no_job_user_is_refused_by_name(self):
        with self.assertRaises(RuntimeError) as caught:
            self.ceiling(_fcfg(job_user_processes=64), user=None)
        text = str(caught.exception)
        self.assertIn(
            "security.confinement.freebsd.job_user_processes is a "
            "ceiling on the job user's processes, and this config "
            "engages no job user", text)
        self.assertIn("security.job_user names none", text)
        self.assertIn("security.modes.job_user is not at enforce", text)
        self.assertIn("name a job user or remove the setting", text)

    def test_the_controls_refuse_what_the_ceiling_refuses(self):
        # Wherever the controls are read -- the spawn, the
        # probe, the report -- a config that cannot have its
        # ceiling is refused, and the ceiling adds no name.
        st = FC.confinement_settings(_fcfg(job_user_processes=64))
        with self.assertRaises(RuntimeError) as caught:
            FC.controls_for(self.host, st, None)
        self.assertIn("engages no job user", str(caught.exception))
        controls, _rctl = FC.controls_for(self.host, st, "pigeon-jobs")
        self.assertEqual(controls, list(FC.CONFINEMENT_CONTROLS))
        st = FC.confinement_settings(_fcfg(job_user_processes=9000))
        with self.assertRaises(RuntimeError) as caught:
            FC.controls_for(self.host, st, "pigeon-jobs")
        self.assertIn("kern.maxprocperuid is 5547",
                      str(caught.exception))

    def test_the_limits_command_carries_it_after_the_memory_limits(self):
        self.assertEqual(
            FC._limits(4096),
            [FC.LIMITS_BIN, "-v", "4096", "-d", "4096"])
        self.assertEqual(
            FC._limits(4096, 24),
            [FC.LIMITS_BIN, "-v", "4096", "-d", "4096", "-u", "24"])
        self.assertEqual(FC._limits(4096, None), FC._limits(4096))

    def test_the_public_name_reads_the_config(self):
        # On FreeBSD the public name answers for this machine;
        # elsewhere it refuses, as every public name does.
        if FC.IS_FREEBSD_BACKEND:
            self.assertIsNone(FC.job_user_process_ceiling({}, None))
        else:
            with self.assertRaises(RuntimeError) as caught:
                FC.job_user_process_ceiling({}, "nobody")
            self.assertIn("FreeBSD-only", str(caught.exception))


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
        # Behind the door, limits(1) sets the user's process
        # ceiling beside the memory ceiling, and the job's own
        # command follows.
        self.assertEqual(
            cmd[6:],
            [FC.LIMITS_BIN, "-v", "536870912", "-d", "536870912",
             "-u", "256", "/bin/sh", "-c", "true"])
        # The job's record says what its user was held to.
        self.assertEqual(
            proc.confinement_notes,
            ["job user pigeon-jobs held to 256 processes"])

    def test_a_job_with_no_job_user_carries_no_process_limit(self):
        proc = self.spawn()
        cmd = self.job_command()
        limits = cmd[cmd.index(FC.LIMITS_BIN):]
        self.assertEqual(limits[:5], [FC.LIMITS_BIN, "-v", "536870912",
                                      "-d", "536870912"])
        self.assertNotIn("-u", cmd)
        self.assertEqual(proc.confinement_notes, [])
        self.assertEqual(
            self.host.ran(FC.SYSCTL_BIN, "kern.maxprocperuid"), [])

    def test_the_job_user_s_ceiling_is_the_config_s(self):
        proc = self.spawn(cfg=_fcfg(job_user_processes=24),
                          user="pigeon-jobs")
        cmd = self.job_command()
        limits = cmd[cmd.index(FC.LIMITS_BIN):]
        self.assertEqual(limits[5:7], ["-u", "24"])
        self.assertEqual(proc.confinement_notes,
                         ["job user pigeon-jobs held to 24 processes"])
        # The record's names are the same: the ceiling is one of
        # the spawn's resource limits.
        self.assertEqual(proc.confinement_status, FC.STATUS_CONFINEMENT)
        # Beside an interpreter's prefix, both are noted.
        proc = self.spawn(["/opt/py311/bin/python3", "-c", "pass"],
                          user="nobody")
        self.assertEqual(
            proc.confinement_notes,
            ["interpreter prefix /opt/py311 mounted read-only",
             "job user nobody held to 256 processes"])

    def test_the_ceiling_stands_beside_the_jail_s_own_rule(self):
        # On a host with RACCT a job user's job has both: the
        # jail's rule and the account's limit.
        self.host.racct = True
        proc = self.spawn(cfg=_fcfg(job_processes=64,
                                    job_user_processes=24),
                          user="pigeon-jobs")
        (name, _jail), = self.host.jails.items()
        self.assertIn("jail:%s:maxproc:deny=64" % name, self.host.rules)
        cmd = self.job_command()
        self.assertEqual(cmd[cmd.index("-u", cmd.index(FC.LIMITS_BIN)):][:2],
                         ["-u", "24"])
        self.assertEqual(
            proc.confinement_status,
            "freebsd: jail + no_network + rctl_resource_limits + "
            "spawn_resource_limits")

    def test_a_ceiling_the_job_cannot_have_refuses_it_and_builds_nothing(self):
        cases = (
            (_fcfg(job_user_processes=64), None, "engages no job user"),
            (_fcfg(job_user_processes=9000), "pigeon-jobs",
             "kern.maxprocperuid is 5547"),
        )
        for cfg, user, expect in cases:
            with self.subTest(expect=expect):
                with self.assertRaises(RuntimeError) as caught:
                    self.spawn(cfg=cfg, user=user)
                self.assertIn(expect, str(caught.exception))
                self.assertEqual(self.host.jails, {})
                self.assertEqual(self.host.table, [])
                self.assertEqual(self.skeletons(), [])
                self.assertEqual(self.host.popens, [])

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


    def test_the_release_collects_the_job_s_first_process(self):
        # An ended job nobody collected is still one of its
        # account's processes, and those are counted. The
        # release collects it -- after the jail has gone, which
        # is what ended it.
        proc = self.spawn(user="pigeon-jobs")
        self.assertFalse(proc._inner.waited)
        self.assertIsNone(proc.returncode)
        seen = []
        real = proc._inner.wait

        def _wait(timeout=None):
            seen.append((dict(self.host.jails), timeout))
            return real(timeout=timeout)
        proc._inner.wait = _wait
        proc.close()
        self.assertEqual(seen, [({}, 2)])
        self.assertTrue(proc._inner.waited)
        self.assertEqual(proc.returncode, 0)
        # A job the caller collected keeps the answer it had.
        proc = self.spawn()
        proc.communicate(timeout=5)
        proc._inner.returncode = 7
        proc.close()
        self.assertEqual(proc.returncode, 7)

    def test_a_first_process_that_will_not_end_does_not_hold_the_release(self):
        for error in (subprocess.TimeoutExpired("jexec", 2),
                      OSError("no child processes"),
                      ValueError("odd")):
            with self.subTest(error=error):
                proc = self.spawn()

                def _hang(timeout=None, error=error):
                    raise error
                proc._inner.wait = _hang
                proc.close()
                self.assertIsNone(proc.returncode)
                self.assertEqual(self.host.jails, {})
                self.assertEqual(self.host.table, [])
                self.assertEqual(self.skeletons(), [])
                # Released once: a second release is nothing.
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

    def test_a_ceiling_on_the_job_user_is_asked_for_the_config_s_own(self):
        # The probe's jail is the one a job with no job user
        # gets, but what the config asks is asked for the jobs
        # it will run: with a job user engaged the ceiling
        # stands, and the trial still proves allow.nosuser.
        named = _fcfg(job_user_processes=64)
        named["security"]["job_user"] = {"user": "pigeon-jobs"}
        self.assertIsNone(self.probe(named))
        (made,) = self.host.ran(FC.JAIL_BIN, "-c")
        self.assertIn("allow.nosuser", made)
        (trial,) = self.host.ran(FC.JEXEC_BIN, FC.SH_BIN)
        self.assertNotIn("-u", trial)
        # No job user engaged: the ceiling the operator wrote is
        # not there, and the start is refused by name, with
        # nothing built.
        for cfg in (
                _fcfg(job_user_processes=64),
                dict(named, security=dict(
                    named["security"], modes={"job_user": "audit"})),
                dict(named, security=dict(
                    named["security"], modes={"job_user": "off"})),
                dict(named, security=dict(
                    named["security"], job_user={"user": ""}))):
            with self.subTest(cfg=cfg):
                before = len(self.host.ran(FC.JAIL_BIN, "-c"))
                problem = self.probe(cfg)
                self.assertIn(
                    "security.confinement.freebsd.job_user_processes "
                    "is a ceiling on the job user's processes, and "
                    "this config engages no job user", problem)
                self.assertEqual(
                    len(self.host.ran(FC.JAIL_BIN, "-c")), before)
                self.assertEqual(self.skeletons(), [])
        # A number the kernel would not let a user hold.
        above = _fcfg(job_user_processes=9000)
        above["security"]["job_user"] = {"user": "pigeon-jobs"}
        self.assertIn("kern.maxprocperuid is 5547", self.probe(above))

    def test_a_verdict_is_kept_for_the_job_user_it_was_asked_for(self):
        # The same settings with and without the job user are
        # two questions: a pass for one is not served to the
        # other.
        named = _fcfg(job_user_processes=64)
        named["security"]["job_user"] = {"user": "pigeon-jobs"}
        self.assertIsNone(self.probe(named, cached=True))
        made = len(self.host.ran(FC.JAIL_BIN, "-c"))
        self.assertIsNone(self.probe(named, cached=True))
        self.assertEqual(len(self.host.ran(FC.JAIL_BIN, "-c")), made)
        self.assertIn("engages no job user", self.probe(
            _fcfg(job_user_processes=64), cached=True))
        other = _fcfg(job_user_processes=64)
        other["security"]["job_user"] = {"user": "nobody"}
        self.assertIsNone(self.probe(other, cached=True))
        self.assertEqual(len(self.host.ran(FC.JAIL_BIN, "-c")), made + 1)
        # Without the setting a job user changes nothing the
        # probe builds: one trial for the settings, as before.
        plain = {"security": {"job_user": {"user": "pigeon-jobs"}}}
        self.assertIsNone(self.probe(plain, cached=True))
        self.assertIsNone(self.probe(plain, cached=True))
        self.assertEqual(len(self.host.ran(FC.JAIL_BIN, "-c")), made + 2)

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

    def test_a_named_job_user_is_who_the_report_says_goes_in(self):
        # With a job user engaged the record carries no
        # no_superuser -- the demote at the door is the job_user
        # record's -- and the report says who the job goes in as.
        cfg = {"security": {"job_user": {"user": "nobody"}}}
        lines = self.lines(cfg)
        self.assertEqual(lines[0], (
            "OK", "FreeBSD jail backend: freebsd: jail + no_network "
            "+ spawn_resource_limits"))
        self.assertEqual(lines[1], (
            "OK", "a job goes in as nobody at the jail door "
            "(security.job_user) and reads what that user can read"))
        # ... and how many processes that user is held to, which
        # needs nothing of the host: the line is there with RACCT
        # and without.
        held = ("OK", "nobody is held to 256 processes across this "
                      "host (limits -u at the jail door; no RACCT "
                      "needed)")
        self.assertEqual(lines[2], held)
        self.assertIn("kern.racct.enable=1", lines[3][1])
        self.assertEqual(len(lines), 4)
        self.host.racct = True
        lines = self.lines(cfg)
        self.assertEqual(lines[0], (
            "OK", "FreeBSD jail backend: freebsd: jail + no_network "
            "+ rctl_resource_limits + spawn_resource_limits"))
        self.assertEqual(lines[2], held)
        self.assertEqual(len(lines), 3)

    def test_the_report_states_the_ceiling_the_config_sets(self):
        cfg = _fcfg(job_user_processes=24)
        cfg["security"]["job_user"] = {"user": "pigeon-jobs"}
        lines = self.lines(cfg)
        self.assertEqual(lines[2], (
            "OK", "pigeon-jobs is held to 24 processes across this "
                  "host (limits -u at the jail door; no RACCT "
                  "needed)"))
        # A host whose own limit is lower: the default follows it.
        self.host.per_user = 100
        plain = {"security": {"job_user": {"user": "pigeon-jobs"}}}
        self.assertIn("is held to 100 processes", self.lines(plain)[2][1])
        # With no job user there is no such line.
        self.assertFalse(
            [t for _level, t in self.lines() if "is held to" in t])
        # Nothing was built to say any of it.
        self.assertEqual(self.host.ran(FC.JAIL_BIN), [])
        self.assertEqual(self.host.ran(FC.MOUNT_BIN), [])

    def test_a_job_user_that_is_not_engaged_changes_nothing(self):
        plain = self.lines()
        cases = (
            {"security": {"modes": {"job_user": "audit"},
                          "job_user": {"user": "nobody"}}},
            {"security": {"modes": {"job_user": "off"},
                          "job_user": {"user": "nobody"}}},
            {"security": {"job_user": {"user": ""}}},
            {"security": {"job_user": "nobody"}},
            {"security": {"modes": "odd",
                          "job_user": {"user": "nobody"}}},
            {"security": "odd"},
        )
        for cfg in cases:
            with self.subTest(cfg=cfg):
                self.assertEqual(self.lines(cfg), plain)
        self.assertEqual(FC._engaged_job_user(
            {"security": {"modes": {"job_user": "enforce"},
                          "job_user": {"user": "pigeon-jobs"}}}),
            "pigeon-jobs")
        self.assertIsNone(FC._engaged_job_user(None))

    def test_what_would_refuse_the_start_is_a_warning(self):
        above = _fcfg(job_user_processes=9000)
        above["security"]["job_user"] = {"user": "nobody"}
        cases = (
            ({"security": {"confinement": {
                "extra_flags": ["--unshare-pid"]}}}, "--unshare-pid"),
            (_fcfg(job_processes=8), "kern.racct.enable=1"),
            (_fcfg(nonsense=1), "nonsense"),
            (_fcfg(job_user_processes=64), "engages no job user"),
            (above, "kern.maxprocperuid is 5547"),
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
        # where the probe passes, the account is made and its
        # trial job passes, on a host without RACCT: the seed's
        # own lines, and the report's lines for the config with
        # the account named beneath them. The lines are the
        # ones the seed itself decides with a scripted machine.
        page = os.path.join(_REPO, "docs", "steady", "security",
                            "freebsd.md")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        answer = (None, tuple(t for _level, t in self.lines()))

        def _trial(cfg, user):
            named = {"security": {"job_user": {"user": user}}}
            return None, tuple(
                t for _level, t in self.lines(named))
        user, door = INS.fresh_job_user(
            {}, answer, "freebsd14", _trial,
            lambda: (INS.FREEBSD_JOB_ACCOUNT, True, None))
        self.assertEqual(user, "pigeon-jobs")
        printed = INS.seed_kept_lines(
            answer, "/root/.homing-pigeon/config.json", user, door)
        self.assertEqual(len(printed), 7)
        self.assertIn(
            "platform: pigeon-jobs is held to 256 processes across "
            "this host (limits -u at the jail door; no RACCT needed)",
            printed)
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


def _processes_of(user):
    """How many processes `user` holds on this host now, in
    every jail and outside them: the kernel's count is the
    same one. (pgrep answers 1 and prints nothing when there
    are none.)"""
    _rc, out = _host_says("/bin/pgrep", "-U", user)
    return len([line for line in out.splitlines() if line.strip()])


def _processes_settle(user, want, wait=15):
    """The count of `user`'s processes once a removed jail's
    processes have finished ending; the last count read."""
    deadline = time.time() + wait
    while True:
        count = _processes_of(user)
        if count == want or time.time() >= deadline:
            return count
        time.sleep(0.2)


# A job that starts children until a fork is refused, or until
# it has started as many as it was told to: it says the limit
# it reads on its own processes, how many children it started,
# and how the last fork ended. The children only sleep; the job
# ends them before it ends.
_FORK_UNTIL_REFUSED = (
    "import errno, os, resource, sys, time\n"
    "print('LIMIT', *resource.getrlimit(resource.RLIMIT_NPROC))\n"
    "kids = []\n"
    "refused = None\n"
    "for i in range(int(sys.argv[1])):\n"
    "    try:\n"
    "        pid = os.fork()\n"
    "    except OSError as e:\n"
    "        refused = e\n"
    "        break\n"
    "    if pid == 0:\n"
    "        time.sleep(120)\n"
    "        os._exit(0)\n"
    "    kids.append(pid)\n"
    "print('STARTED', len(kids))\n"
    "if refused is None:\n"
    "    print('UNBOUNDED')\n"
    "else:\n"
    "    print('REFUSED', errno.errorcode.get(refused.errno, '?'))\n"
    "sys.stdout.flush()\n"
    "for k in kids:\n"
    "    os.kill(k, 9)\n"
    "for k in kids:\n"
    "    os.waitpid(k, 0)\n")


def _forked(out):
    """What a _FORK_UNTIL_REFUSED job said: (soft limit, hard
    limit, children started, how the last fork ended)."""
    words = out.decode("utf-8", "replace").split()
    at = words.index("LIMIT")
    how = "UNBOUNDED" if "UNBOUNDED" in words \
        else words[words.index("REFUSED") + 1]
    return (int(words[at + 1]), int(words[at + 2]),
            int(words[words.index("STARTED") + 1]), how)


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

    def test_a_job_user_s_processes_are_held_with_racct_or_without(self):
        # The ceiling that needs nothing of the host: a job that
        # goes in as a job user starts children until the kernel
        # refuses the fork, and the account holds the ceiling's
        # number in all -- this job's first process, its
        # children, and whatever else the account ran here.
        before = _processes_of("nobody")
        proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "60"],
            cfg=_fcfg(job_user_processes=24), user="nobody")
        soft, hard, started, how = _forked(out)
        self.assertEqual((soft, hard), (24, 24), (out, err))
        self.assertEqual(how, "EAGAIN", (out, err))
        self.assertLessEqual(started, 23, (out, err))
        self.assertGreaterEqual(started, 23 - before, (out, err, before))
        if before == 0:
            self.assertEqual(started, 23, (out, err))
        # The record: the same names as any job user's job, the
        # ceiling in its notes -- and on a host as FreeBSD ships
        # no rctl rule had any part in it.
        self.assertIn("job user nobody held to 24 processes",
                      proc.confinement_notes)
        self.assertNotIn("no_superuser", proc.confinement_status)
        self.assertEqual(
            "rctl_resource_limits" in proc.confinement_status,
            _racct_live())
        # The jail went with the job, and its processes with it.
        self.assertEqual(_processes_settle("nobody", before), before)

    def test_a_job_user_cannot_raise_its_process_ceiling(self):
        _proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c",
             "import resource\n"
             "inf = resource.RLIM_INFINITY\n"
             "what = resource.RLIMIT_NPROC\n"
             "print('LIMIT', *resource.getrlimit(what))\n"
             "for want in ((inf, inf), (25, 25), (24, 25)):\n"
             "    try:\n"
             "        resource.setrlimit(what, want)\n"
             "        print('LIFTED', want)\n"
             "    except (ValueError, OSError) as e:\n"
             "        print('HELD', want)\n"
             "resource.setrlimit(what, (10, 24))\n"
             "print('LOWERED', *resource.getrlimit(what))\n"
             "try:\n"
             "    resource.setrlimit(what, (24, 24))\n"
             "    print('BACK', *resource.getrlimit(what))\n"
             "except (ValueError, OSError) as e:\n"
             "    print('STUCK', e)\n"],
            cfg=_fcfg(job_user_processes=24), user="nobody")
        self.assertIn(b"LIMIT 24 24", out, (out, err))
        self.assertEqual(out.count(b"HELD"), 3, (out, err))
        self.assertNotIn(b"LIFTED", out, (out, err))
        # Below the ceiling the limit is the job's own to move.
        self.assertIn(b"LOWERED 10 24", out, (out, err))
        self.assertIn(b"BACK 24 24", out, (out, err))

    def test_the_ceiling_is_the_account_s_across_jails(self):
        # One job of the account holds nine processes in its
        # jail; a second job, in a jail of its own, is refused
        # nine sooner. The count is the account's on the host.
        import pwd
        before = _processes_of("nobody")
        cfg = _fcfg(job_user_processes=24)
        rec = pwd.getpwnam("nobody")
        work = tempfile.mkdtemp(prefix="hp-live-")
        self.addCleanup(shutil.rmtree, work, True)
        os.chmod(work, 0o755)
        os.chown(work, rec.pw_uid, rec.pw_gid)
        first = FC.spawn_confined_process(
            [_LIVE_PYTHON, "-c",
             "import os, time\n"
             "kids = []\n"
             "for i in range(8):\n"
             "    pid = os.fork()\n"
             "    if pid == 0:\n"
             "        time.sleep(120)\n"
             "        os._exit(0)\n"
             "    kids.append(pid)\n"
             "open('ready', 'w').write(str(len(kids)))\n"
             "time.sleep(120)\n"],
            cwd=work, env={}, user="nobody", cfg=cfg)
        try:
            ready = os.path.join(work, "ready")
            deadline = time.time() + 60
            while not os.path.exists(ready) and time.time() < deadline:
                time.sleep(0.2)
            self.assertTrue(os.path.exists(ready),
                            "the first job never held its processes")
            self.assertEqual(_processes_of("nobody"), before + 9)
            first_jail = first._name
            proc, out, err, _work = self._job(
                [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "60"],
                cfg=cfg, user="nobody")
            soft, hard, started, how = _forked(out)
            self.assertEqual((soft, hard), (24, 24), (out, err))
            self.assertEqual(how, "EAGAIN", (out, err))
            # 24 in all: nine in the first jail, this job's own
            # first process, and its children.
            self.assertLessEqual(started, 14, (out, err))
            self.assertGreaterEqual(started, 14 - before,
                                    (out, err, before))
            if before == 0:
                self.assertEqual(started, 14, (out, err))
            # Two jails, one count.
            self.assertTrue(FC._JAIL_NAME.match(first_jail), first_jail)
            self.assertIsNone(first.poll())
        finally:
            # The first job is ended and collected, as a runner
            # collects every job: until it is, its first process
            # is still one of the account's, ended or not.
            first.kill()
            try:
                first.communicate(timeout=30)
            except (OSError, subprocess.SubprocessError):
                pass
            first.close()
        self.assertEqual(_processes_settle("nobody", before), before)

    def test_a_job_with_no_job_user_carries_no_such_ceiling(self):
        # The stated limit: uid 0's count is the host's own, so
        # no limit is set on it, and forty children start. Where
        # RACCT is enabled the jail's own rule (256) is the only
        # ceiling on this job's processes.
        proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "40"])
        soft, hard, started, how = _forked(out)
        self.assertEqual((started, how), (40, "UNBOUNDED"), (out, err))
        self.assertGreater(soft, 256, (out, err))
        self.assertIn("no_superuser", proc.confinement_status)
        self.assertEqual(proc.confinement_notes, [])

    def test_the_lower_of_the_two_ceilings_is_the_one_a_job_meets(self):
        if not _racct_live():
            self.skipTest("RACCT is not enabled on this host")
        before = _processes_of("nobody")
        # The jail's rule below the account's ceiling.
        proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "60"],
            cfg=_fcfg(job_processes=12, job_user_processes=24),
            user="nobody")
        _soft, hard, started, how = _forked(out)
        self.assertEqual(hard, 24, (out, err))
        self.assertEqual(how, "EAGAIN", (out, err))
        self.assertLess(started, 12, (out, err))
        self.assertGreater(started, 3, (out, err))
        self.assertIn("rctl_resource_limits", proc.confinement_status)
        # The account's ceiling below the jail's rule.
        proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "60"],
            cfg=_fcfg(job_processes=48, job_user_processes=24),
            user="nobody")
        _soft, hard, started, how = _forked(out)
        self.assertEqual(how, "EAGAIN", (out, err))
        self.assertLessEqual(started, 23, (out, err))
        self.assertGreaterEqual(started, 23 - before, (out, err))
        self.assertGreater(started, 11, (out, err))

    def test_a_ceiling_the_config_cannot_have_refuses_the_start(self):
        # On a real host: the startup gate's own probe, with
        # the config as written.
        self.assertIsNone(FC.freebsd_startup_problem(
            {"security": {
                "confinement": {"freebsd": {"job_user_processes": 64}},
                "job_user": {"user": "nobody"}}}))
        problem = FC.freebsd_startup_problem(
            _fcfg(job_user_processes=64))
        self.assertIn("engages no job user", problem or "")
        _rc, said = _host_says(FC.SYSCTL_BIN, "-n", "kern.maxprocperuid")
        per_user = int(said.strip())
        self.assertGreater(per_user, 256)
        problem = FC.freebsd_startup_problem({"security": {
            "confinement": {"freebsd": {
                "job_user_processes": per_user + 1}},
            "job_user": {"user": "nobody"}}})
        self.assertIn("kern.maxprocperuid is %d" % per_user,
                      problem or "")
        # At the kernel's own limit the ceiling is one a job can
        # be given: the door sets it.
        _proc, out, err, _work = self._job(
            [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "2"],
            cfg=_fcfg(job_user_processes=per_user), user="nobody")
        soft, hard, started, how = _forked(out)
        self.assertEqual((soft, hard, started, how),
                         (per_user, per_user, 2, "UNBOUNDED"), (out, err))
        # And the public name answers for this machine.
        self.assertEqual(FC.job_user_process_ceiling({}, "nobody"), 256)
        self.assertIsNone(FC.job_user_process_ceiling({}, None))

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

    def test_root_s_own_files_are_read_until_a_job_user_is_named(self):
        # The limit the platform page states. A job with no job
        # user is uid 0 inside its jail: no privilege, and still
        # the owner of what root owns, so a root-only file in a
        # tree the jail shows it is read. Under a job user the
        # same file is refused. The tree here is an operator's
        # bind; the host's own trees are shown the same way.
        shown = tempfile.mkdtemp(prefix="hp-live-shown-")
        self.addCleanup(shutil.rmtree, shown, True)
        os.chmod(shown, 0o755)
        secret = os.path.join(shown, "root-only.txt")
        with open(secret, "w") as fh:
            fh.write("ROOT-ONLY-DATA\n")
        os.chmod(secret, 0o600)
        cfg = {"security": {"confinement": {
            "extra_ro_binds": [[shown, "/shown"]]}}}
        argv = ["/bin/sh", "-c",
                "id -u; cat /shown/root-only.txt 2>/dev/null "
                "|| echo REFUSED; echo DONE"]
        _proc, out, err, _work = self._job(argv, cfg=cfg)
        self.assertIn(b"DONE", out, err)
        self.assertEqual(out.split()[0], b"0", out)
        self.assertIn(b"ROOT-ONLY-DATA", out, err)
        import pwd
        nobody = pwd.getpwnam("nobody")
        _proc, out, err, _work = self._job(argv, cfg=cfg,
                                           user="nobody")
        self.assertIn(b"DONE", out, err)
        self.assertEqual(out.split()[0],
                         str(nobody.pw_uid).encode(), out)
        self.assertIn(b"REFUSED", out, err)
        self.assertNotIn(b"ROOT-ONLY-DATA", out, err)

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


# Making an account is tested only on a guest that is thrown
# away afterwards: the freebsd-confinement workflow says so in
# its run step. On any other FreeBSD host -- the fleet node
# among them -- the live seed tests name a user without making
# one, and nothing is added to the machine's user database.
_DISPOSABLE_GUEST = os.environ.get("HP_LIVE_ACCOUNTS") == "1"


def _account_ids(name="pigeon-jobs"):
    """(uid, gid) of the jobs account on this host, or None."""
    try:
        return INS._user_ids(name)
    except KeyError:
        return None


class _LiveSeed(unittest.TestCase):
    """What the live seed classes share: a folder, what the
    host held before, and the seed, the config and a runner's
    first job read back."""

    def setUp(self):
        # These are the tests of the seed's questions to the
        # machine, so the questions are on for them.
        switch = _machine_asked()
        switch.start()
        self.addCleanup(switch.stop)
        self.folder = tempfile.mkdtemp(prefix="hp-live-seed-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.before = _leftovers()
        self.doors = self._doors()

    @staticmethod
    def _doors():
        try:
            return {n for n in os.listdir(tempfile.gettempdir())
                    if n.startswith("hp-seed-door-")}
        except OSError:
            return set()

    def _nothing_left(self):
        after = _leftovers()
        for what in ("mounts", "dirs", "jails", "rules"):
            self.assertEqual(after[what] - self.before[what], set(),
                             "%s left behind" % what)
        self.assertEqual(self._doors() - self.doors, set(),
                         "a door trial's folder left behind")

    def _seed(self, path, **doors):
        out = io.StringIO()
        with redirect_stdout(out):
            applied = INS.apply_platform_modes(path, **doors)
        return applied, out.getvalue()

    @staticmethod
    def _config(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _names(self, user, path, out, before):
        """The seed left the jail on and named `user`: one block
        added to the file and nothing else changed, and the
        lines say what was decided and what a job's jail
        carries now."""
        after = self._config(path)
        self.assertEqual(after["security"]["modes"]["confinement"],
                         "enforce")
        self.assertEqual(after["security"]["job_user"],
                         {"user": user})
        del after["security"]["job_user"]
        self.assertEqual(after, before)
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s" % path, out)
        self.assertIn("security.job_user names %s in %s (a trial "
                      "job as %s inside a jail on this machine "
                      "passed" % (user, path, user), out)
        # The controls a job's jail carries on this host under
        # the config as it now stands: no no_superuser, because
        # the job is not uid 0 any more.
        self.assertIn("platform: FreeBSD jail backend: freebsd: "
                      "jail + no_network + ", out)
        self.assertNotIn("no_superuser", out)
        self.assertIn("platform: a job goes in as %s at the jail "
                      "door" % user, out)
        # ... and how many processes the trial job read its user
        # held to.
        self.assertIn("platform: %s is held to 256 processes across "
                      "this host (limits -u at the jail door; no "
                      "RACCT needed)" % user, out)
        self.assertNotIn("stated as audit", out)

    def _shown_tree(self):
        """A tree an operator shows every job: one file only
        root may read in it, one all may read."""
        shown = os.path.join(self.folder, "shown")
        os.mkdir(shown)
        os.chmod(shown, 0o755)
        os.chmod(self.folder, 0o755)
        with open(os.path.join(shown, "root-only.txt"), "w") as fh:
            fh.write("ROOT-ONLY-DATA\n")
        os.chmod(os.path.join(shown, "root-only.txt"), 0o600)
        with open(os.path.join(shown, "for-all.txt"), "w") as fh:
            fh.write("FOR-ALL-DATA\n")
        os.chmod(os.path.join(shown, "for-all.txt"), 0o644)
        return shown

    def _first_job(self, security):
        """A runner of its own on the security block the seed
        left: its startup gate, its first job, and the records
        that job wrote."""
        from runner.guard import security as S
        base = os.path.join(self.folder, "base")
        os.mkdir(base)
        cfg = {"base_dir": base, "security": security}
        self.assertIsNone(rr._confinement_startup_problem(cfg))
        job = {"v": 1, "type": "job", "job_id": "fbsd-seeded",
               "issued_at": "2026-11-14T12:00:00Z", "kind": "exec",
               "interpreter": ["python3"],
               "script": (
                   "import os\n"
                   "print('uid:', os.getuid())\n"
                   "print('cwd:', os.getcwd())\n"
                   "open('out.txt', 'w').write('wrote-ok')\n"
                   "for label, name in (('root', '/escape.txt'),\n"
                   "                    ('shown', '/shown/x.txt')):\n"
                   "    try:\n"
                   "        open(name, 'w').write('x')\n"
                   "        print(label + ': wrote')\n"
                   "    except OSError:\n"
                   "        print(label + ': blocked')\n"
                   "print('for-all:',\n"
                   "      open('/shown/for-all.txt').read().strip())\n"
                   "try:\n"
                   "    print('root-only:',\n"
                   "          open('/shown/root-only.txt').read())\n"
                   "except OSError:\n"
                   "    print('root-only: refused')\n"),
               "outputs": ["out.txt"]}
        result = rr.execute_job(cfg, job, base)
        rows = []
        with open(os.path.join(base, S.AUDIT_FILE),
                  encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
        return result, rows

    def _job_ran_as(self, uid, result, rows, out):
        """The runner's first job ran confined as `uid`, read
        what all may read, and was refused what only root may;
        the records name what the seed printed."""
        self.assertEqual(result["exit_code"], 0, result)
        said = result["stdout"]
        self.assertIn("uid: %d" % uid, said)
        self.assertIn("cwd: /work", said)
        self.assertIn("root: blocked", said)
        self.assertIn("shown: blocked", said)
        self.assertIn("for-all: FOR-ALL-DATA", said)
        self.assertIn("root-only: refused", said)
        self.assertNotIn("ROOT-ONLY-DATA", said)
        self.assertEqual(len(result["outputs"]), 1, result)
        confined = [r for r in rows
                    if r.get("feature") == "confinement"
                    and r.get("decision") == "confined"]
        self.assertEqual(len(confined), 1, rows)
        reason = confined[0].get("reason", "<none>")
        self.assertNotIn("no_superuser", reason)
        self.assertIn("platform: FreeBSD jail backend: " + reason, out)
        # The job's own record says what its user was held to.
        self.assertIn("held to 256 processes",
                      confined[0].get("detail", ""), confined[0])
        self.assertTrue(any(
            r.get("feature") == "job_user"
            and r.get("decision") == "run_as" for r in rows), rows)


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LiveSeedTest(_LiveSeed):
    """What a fresh install states, on a real kernel: the seed
    asks the real probe the startup gate's question, runs the
    real trial job as the job user, and writes what the machine
    answers -- as root, as an ordinary user, for a config that
    asks more than the host holds, for a config that names its
    own job user, by the installer's file path, and through the
    wizard -- and a runner started on the seeded config runs
    its first job confined, as that user.

    No account is made here. The seed is handed the finder --
    the account where the host already has it, the shared user
    where it does not -- so these run on any FreeBSD host and
    add nothing to its user database. LiveAccountTest is where
    the installer's own maker runs.
    """

    @staticmethod
    def _find():
        return INS.freebsd_job_account(make=False)

    @staticmethod
    def _user():
        """Who the finder's seed names on this host."""
        return "pigeon-jobs" if _account_ids() else "nobody"

    def test_as_root_the_seed_leaves_the_jail_on_and_names_a_user(self):
        user = self._user()
        accounts = _account_ids()
        path = _seeded_config(self.folder)
        before = self._config(path)
        applied, out = self._seed(path, account=self._find)
        self.assertEqual(applied, {}, out)
        self._names(user, path, out, before)
        self.assertEqual("rctl_resource_limits" in out,
                         _racct_live(), out)
        self.assertEqual("kern.racct.enable=1" in out,
                         not _racct_live(), out)
        self.assertNotIn("made for the jail's jobs", out)
        if user == "nobody":
            self.assertIn("platform: account pigeon-jobs is not on "
                          "this machine (the installer makes it)",
                          out)
            self.assertIn("platform: nobody stands in", out)
        # A later run over the same config asks the first
        # question again, finds a job user named, and changes
        # nothing.
        with open(path, "rb") as fh:
            seeded = fh.read()
        applied, out = self._seed(path, account=self._find)
        with open(path, "rb") as fh:
            again = fh.read()
        self.assertEqual(applied, {}, out)
        self.assertEqual(again, seeded)
        self.assertIn("left at enforce", out)
        self.assertNotIn("security.job_user names", out)
        self.assertIn("platform: a job goes in as %s at the jail "
                      "door" % user, out)
        # The finder made nothing.
        self.assertEqual(_account_ids(), accounts)
        self._nothing_left()

    def test_a_runner_on_the_seeded_config_runs_its_job_as_that_user(self):
        import pwd
        user = self._user()
        shown = self._shown_tree()
        path = _seeded_config(self.folder, confinement={
            "extra_ro_binds": [[shown, "/shown"]]})
        applied, out = self._seed(path, account=self._find)
        self.assertEqual(applied, {}, out)
        seeded = self._config(path)
        self.assertEqual(seeded["security"]["job_user"],
                         {"user": user})
        result, rows = self._first_job(seeded["security"])
        self._job_ran_as(pwd.getpwnam(user).pw_uid, result, rows, out)
        self._nothing_left()

    def test_the_door_trial_on_this_machine(self):
        problem, lines = INS.freebsd_job_user_trial({})
        self.assertIsNone(problem)
        self.assertTrue(lines[0].startswith(
            "FreeBSD jail backend: freebsd: jail + no_network + "),
            lines)
        self.assertNotIn("no_superuser", lines[0])
        self.assertTrue(lines[1].startswith(
            "a job goes in as nobody at the jail door"), lines)
        # A user that would close nothing, and one that is not
        # there, are reasons; neither builds a jail.
        problem, lines = INS.freebsd_job_user_trial({}, "root")
        self.assertEqual(problem, "root is uid 0 on this machine")
        self.assertEqual(lines, ())
        problem, lines = INS.freebsd_job_user_trial(
            {}, "hp-no-such-user")
        self.assertIn("hp-no-such-user is not in this machine's "
                      "user database", problem)
        self._nothing_left()

    def test_a_config_that_names_its_own_job_user_keeps_it(self):
        path = _seeded_config(self.folder)
        cfg = self._config(path)
        cfg["security"]["job_user"] = {"user": "daemon"}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        with open(path, "rb") as fh:
            before = fh.read()

        def _never():
            raise AssertionError("the account was looked for")
        applied, out = self._seed(path, account=_never)
        with open(path, "rb") as fh:
            after = fh.read()
        self.assertEqual(applied, {}, out)
        self.assertEqual(before, after)
        self.assertIn("left at enforce", out)
        self.assertNotIn("security.job_user names", out)
        # The report reads the operator's user.
        self.assertIn("platform: a job goes in as daemon at the "
                      "jail door", out)
        self._nothing_left()

    def test_a_job_user_mode_stated_down_names_no_one(self):
        path = _seeded_config(self.folder, modes={"job_user": "off"})
        with open(path, "rb") as fh:
            before = fh.read()

        def _never():
            raise AssertionError("the account was looked for")
        applied, out = self._seed(path, account=_never)
        with open(path, "rb") as fh:
            after = fh.read()
        self.assertEqual(applied, {}, out)
        self.assertEqual(before, after)
        self.assertIn("left at enforce", out)
        self.assertNotIn("security.job_user names", out)
        self.assertIn("no_superuser", out)
        self._nothing_left()

    def test_an_ordinary_user_s_seed_states_audit_and_names_root(self):
        import pwd
        nobody = pwd.getpwnam("nobody")
        accounts = _account_ids()
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
            # The child: an ordinary user from here to its exit,
            # and the installer's seed with nothing handed in --
            # its own probe, its own trial, its own maker.
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
                        "security": self._config(path)["security"],
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
        modes = said["security"]["modes"]
        self.assertEqual(modes["confinement"], "audit")
        self.assertEqual(modes["job_user"], "enforce")
        # No jail, so no job user and no account: a demote needs
        # root too.
        self.assertNotIn("job_user", said["security"])
        self.assertIn("security.modes.confinement stated as audit "
                      "in %s" % path, said["out"])
        self.assertIn("did not pass: creating a jail needs root",
                      said["out"])
        self.assertNotIn("left at enforce", said["out"])
        self.assertNotIn("security.job_user names", said["out"])
        self.assertNotIn("account pigeon-jobs", said["out"])
        self.assertEqual(_account_ids(), accounts)
        self._nothing_left()

    def test_named_ceilings_are_seeded_by_what_the_host_holds(self):
        path = _seeded_config(
            self.folder, confinement={"freebsd": {"job_processes": 64}})
        before = self._config(path)
        applied, out = self._seed(path, account=self._find)
        if _racct_live():
            self.assertEqual(applied, {}, out)
            self._names(self._user(), path, out, before)
            self.assertIn("rctl_resource_limits", out)
        else:
            self.assertEqual(applied, {"confinement": "audit"}, out)
            security = self._config(path)["security"]
            self.assertEqual(security["modes"]["confinement"], "audit")
            self.assertNotIn("job_user", security)
            self.assertIn("did not pass: ", out)
            self.assertIn("RACCT is not enabled on this host", out)
            self.assertIn("kern.racct.enable=1", out)
            self.assertNotIn("security.job_user names", out)
        self._nothing_left()

    def test_the_installer_started_by_path_seeds_the_same(self):
        path = _seeded_config(self.folder)
        before = self._config(path)
        driver = (
            "import json, runpy, sys\n"
            "ns = runpy.run_path(sys.argv[1], "
            "run_name='hp_install_by_path')\n"
            "applied = ns['apply_platform_modes'](\n"
            "    sys.argv[2],\n"
            "    account=lambda: ns['freebsd_job_account'](make=False))\n"
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
        self._names(self._user(), path, text, before)
        self._nothing_left()

    def test_the_wizard_s_seed_asks_the_same_machine(self):
        user = self._user()
        accounts = _account_ids()
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        answers = []
        stated = SU.seed_platform_modes(cfg, asked=answers)
        self.assertEqual(stated, {})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "enforce")
        self.assertEqual(cfg["security"]["job_user"], {"user": user})
        ((answer, named, door),) = answers
        self.assertIsNone(answer[0])
        self.assertEqual(named, user)
        self.assertIsNone(door["problem"])
        self.assertTrue(door["lines"][0].startswith(
            "FreeBSD jail backend: freebsd: jail + no_network"),
            answers)
        self.assertNotIn("no_superuser", door["lines"][0])
        # The wizard's seed writes a config and nothing else.
        self.assertEqual(_account_ids(), accounts)
        self._nothing_left()


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0 and _DISPOSABLE_GUEST,
    "making an account is tested on a disposable FreeBSD guest")
class LiveAccountTest(_LiveSeed):
    """The account the installer makes for jobs, on a real
    kernel and a real user database -- on a guest that is
    thrown away afterwards, and nowhere else. The installer's
    seed runs here with nothing handed in: its own probe, its
    own maker, its own trial."""

    def setUp(self):
        super().setUp()
        # Each test starts with no such account and leaves none.
        self._clear()
        self.addCleanup(self._clear)

    @staticmethod
    def _clear():
        if _account_ids() is not None:
            INS.freebsd_remove_job_account("pigeon-jobs")

    def _made_line(self):
        return ("platform: account pigeon-jobs made for the jail's "
                "jobs (pw useradd: no password, no login shell, no "
                "home directory)")

    def test_the_installer_makes_the_account_and_names_it(self):
        import grp
        import pwd
        self.assertIsNone(_account_ids())
        path = _seeded_config(self.folder)
        before = self._config(path)
        applied, out = self._seed(path)
        self.assertEqual(applied, {}, out)
        self._names("pigeon-jobs", path, out, before)
        self.assertIn(self._made_line(), out)
        # The account as it was made: nothing to log in with, no
        # home, a group of its own with no one else in it.
        entry = pwd.getpwnam("pigeon-jobs")
        self.assertNotEqual(entry.pw_uid, 0)
        self.assertEqual(entry.pw_shell, "/usr/sbin/nologin")
        self.assertEqual(entry.pw_dir, "/nonexistent")
        self.assertFalse(os.path.exists("/nonexistent"))
        # A password field no hash can match.
        self.assertTrue(entry.pw_passwd.startswith("*"),
                        entry.pw_passwd)
        self.assertEqual(entry.pw_gecos, "homing-pigeon jobs")
        group = grp.getgrgid(entry.pw_gid)
        self.assertEqual(group.gr_name, "pigeon-jobs")
        self.assertEqual(group.gr_mem, [])
        self.assertEqual(
            [g.gr_name for g in grp.getgrall()
             if "pigeon-jobs" in g.gr_mem], [])
        # A later run finds the name written: no trial, no pw,
        # nothing changed.
        with open(path, "rb") as fh:
            seeded = fh.read()
        applied, out = self._seed(path)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), seeded)
        self.assertEqual(applied, {}, out)
        self.assertNotIn("made for the jail's jobs", out)
        self.assertNotIn("security.job_user names", out)
        self.assertEqual(pwd.getpwnam("pigeon-jobs").pw_uid,
                         entry.pw_uid)
        # A fresh config on a machine where the account stands
        # uses it as it is.
        other = os.path.join(self.folder, "other")
        os.mkdir(other)
        path2 = _seeded_config(other)
        before2 = self._config(path2)
        applied, out = self._seed(path2)
        self.assertEqual(applied, {}, out)
        self._names("pigeon-jobs", path2, out, before2)
        self.assertNotIn("made for the jail's jobs", out)
        self.assertEqual(pwd.getpwnam("pigeon-jobs").pw_uid,
                         entry.pw_uid)
        self._nothing_left()

    def test_a_runner_on_the_seeded_config_runs_its_job_as_the_account(self):
        shown = self._shown_tree()
        path = _seeded_config(self.folder, confinement={
            "extra_ro_binds": [[shown, "/shown"]]})
        applied, out = self._seed(path)
        self.assertEqual(applied, {}, out)
        seeded = self._config(path)
        self.assertEqual(seeded["security"]["job_user"],
                         {"user": "pigeon-jobs"})
        uid, _gid = _account_ids()
        result, rows = self._first_job(seeded["security"])
        self._job_ran_as(uid, result, rows, out)
        self._nothing_left()

    def test_the_account_s_processes_are_held_exactly(self):
        # Nothing else runs as the installer's account, so the
        # ceiling is the jobs' own to the last process: under a
        # ceiling of 24 a job holds 24, its first one and
        # twenty-three children, on every guest.
        self.assertEqual(INS.freebsd_job_account(make=True),
                         ("pigeon-jobs", True, None))
        self.assertEqual(_processes_of("pigeon-jobs"), 0)
        uid, gid = _account_ids()
        work = os.path.join(self.folder, "held")
        os.mkdir(work)
        os.chmod(self.folder, 0o755)
        os.chown(work, uid, gid)
        proc = FC.spawn_confined_process(
            [_LIVE_PYTHON, "-c", _FORK_UNTIL_REFUSED, "60"],
            cwd=work, env={}, user="pigeon-jobs",
            cfg=_fcfg(job_user_processes=24))
        try:
            out, err = proc.communicate(timeout=120)
        finally:
            proc.close()
        self.assertEqual(_forked(out), (24, 24, 23, "EAGAIN"),
                         (out, err))
        self.assertEqual(proc.confinement_notes,
                         ["job user pigeon-jobs held to 24 processes"])
        # The trial the installer runs reads the default back.
        problem, lines = INS.freebsd_job_user_trial({}, "pigeon-jobs")
        self.assertIsNone(problem)
        self.assertIn("pigeon-jobs is held to 256 processes across "
                      "this host (limits -u at the jail door; no "
                      "RACCT needed)", lines)
        self.assertEqual(_processes_settle("pigeon-jobs", 0), 0)
        self._nothing_left()

    def test_the_wizard_s_seed_makes_no_account(self):
        # Without the account the wizard's seed names the shared
        # user and makes nothing; with it, it names the account.
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        answers = []
        SU.seed_platform_modes(cfg, asked=answers)
        self.assertEqual(cfg["security"]["job_user"],
                         {"user": "nobody"})
        self.assertEqual(answers[0][2]["notes"], [
            "account pigeon-jobs is not on this machine (the "
            "installer makes it)", "nobody stands in"])
        self.assertIsNone(_account_ids())
        self.assertEqual(INS.freebsd_job_account(make=True),
                         ("pigeon-jobs", True, None))
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        answers = []
        SU.seed_platform_modes(cfg, asked=answers)
        self.assertEqual(cfg["security"]["job_user"],
                         {"user": "pigeon-jobs"})
        self.assertEqual(answers[0][2]["notes"], [])
        self._nothing_left()

    def test_an_account_made_and_not_usable_is_removed_again(self):
        # The real maker and the real trial, with the trial
        # refusing the account alone: the account is made,
        # cannot be used, and is gone again; the shared user
        # stands in on its own real trial.
        def _trial(cfg, user):
            if user == "pigeon-jobs":
                return ("scripted: this account is not to pass", ())
            return INS.freebsd_job_user_trial(cfg, user)
        path = _seeded_config(self.folder)
        before = self._config(path)
        applied, out = self._seed(
            path, trial=_trial,
            account=lambda: INS.freebsd_job_account(make=True))
        self.assertEqual(applied, {}, out)
        self._names("nobody", path, out, before)
        lines = out.splitlines()
        self.assertEqual(lines[1:5], [
            self._made_line(),
            "platform: a trial job as pigeon-jobs inside a jail on "
            "this machine did not pass: scripted: this account is "
            "not to pass",
            "platform: account pigeon-jobs removed again",
            "platform: nobody stands in"])
        self.assertIsNone(_account_ids())
        self._nothing_left()

    def test_where_the_account_cannot_be_made_nobody_stands_in(self):
        path = _seeded_config(self.folder)
        before = self._config(path)
        why = "pw useradd exited 1: scripted"
        applied, out = self._seed(
            path, trial=INS.freebsd_job_user_trial,
            account=lambda: (None, False, why))
        self.assertEqual(applied, {}, out)
        self._names("nobody", path, out, before)
        self.assertIn("platform: account pigeon-jobs could not be "
                      "made (%s)" % why, out)
        self.assertIn("platform: nobody stands in", out)
        self.assertIsNone(_account_ids())
        self._nothing_left()

    def test_the_installer_started_by_path_makes_the_account_too(self):
        path = _seeded_config(self.folder)
        before = self._config(path)
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
        said = json.loads(text.splitlines()[-1])
        self.assertEqual(said, {"applied": {}, "pulled_in": []}, text)
        self._names("pigeon-jobs", path, text, before)
        self.assertIn(self._made_line(), text)
        self.assertIsNotNone(_account_ids())
        self._nothing_left()

    def test_an_account_already_there_is_not_changed(self):
        import pwd
        # An account of the name, made another way: a real shell
        # and a comment of its own. The seed uses it as it
        # stands.
        code, said = INS._run_pw([
            "useradd", "-n", "pigeon-jobs", "-c", "made by hand",
            "-d", "/nonexistent", "-s", "/bin/sh", "-w", "no"])
        self.assertEqual(code, 0, said)
        before_entry = pwd.getpwnam("pigeon-jobs")
        path = _seeded_config(self.folder)
        before = self._config(path)
        applied, out = self._seed(path)
        self.assertEqual(applied, {}, out)
        self._names("pigeon-jobs", path, out, before)
        self.assertNotIn("made for the jail's jobs", out)
        after_entry = pwd.getpwnam("pigeon-jobs")
        self.assertEqual(tuple(after_entry), tuple(before_entry))
        self.assertEqual(after_entry.pw_gecos, "made by hand")
        self._nothing_left()


def _as_an_ordinary_user(work, wait=180):
    """Run `work` in a child that is `nobody` from its first
    line to its exit, and hand back what it said: (exit status,
    the dict `work` returned, or {"error": ...}). Whatever
    `work` loads is loaded by the caller first -- the child
    reads no source file as the ordinary user."""
    import pwd
    import select
    import signal
    import time
    nobody = pwd.getpwnam("nobody")
    read_end, write_end = os.pipe()
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            os.close(read_end)
            os.setgroups([])
            os.setgid(nobody.pw_gid)
            os.setuid(nobody.pw_uid)
            said = work()
            said["uid"] = os.geteuid()
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
    chunks, deadline, answered = [], time.time() + wait, False
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
    if not answered:
        return status, {"error": "no answer inside %d seconds" % wait}
    try:
        return status, json.loads(b"".join(chunks).decode("utf-8"))
    except ValueError as e:
        return status, {"error": "unreadable answer: %s" % e}


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0,
    "run on FreeBSD as root")
class LivePostureTest(unittest.TestCase):
    """The posture tests as the hosted suite runs them on
    FreeBSD: as an ordinary user, where the jail backend cannot
    engage and the report says so. A test that asks for a clean
    report answers for the backend, so the module reads clean
    there. Nothing is built and nothing is added to the host."""

    @staticmethod
    def _the_module():
        import runner.tests.test_posture as TP
        from runner.ops import posture as P
        stream = io.StringIO()
        with redirect_stdout(io.StringIO()):
            result = unittest.TextTestRunner(
                stream=stream, verbosity=0).run(
                    unittest.defaultTestLoader.loadTestsFromModule(TP))
        return {
            "ran": result.testsRun,
            "red": sorted(t.id().rsplit(".", 2)[-1] + ": "
                          + text.strip().splitlines()[-1][:200]
                          for t, text in result.failures + result.errors),
            "host": [list(line) for line
                     in P._freebsd_confinement_lines({})]}

    def test_the_posture_tests_read_clean_as_an_ordinary_user(self):
        # as root first: the module reads clean here too, and
        # everything it loads is loaded before the child starts
        as_root = self._the_module()
        self.assertEqual(as_root["red"], [])
        self.assertGreaterEqual(as_root["ran"], 24)
        self.assertEqual([level for level, _text in as_root["host"]][0],
                         "OK", as_root["host"])

        def work():
            tempfile.tempdir = "/tmp"
            return self._the_module()
        status, said = _as_an_ordinary_user(work)
        self.assertNotIn("error", said)
        self.assertEqual(status, 0, said)
        self.assertNotEqual(said["uid"], 0)
        self.assertEqual(said["ran"], as_root["ran"])
        self.assertEqual(said["red"], [])
        # the host's own word for this user is the warning the
        # clean reads are not: the report is right to give it
        self.assertEqual(len(said["host"]), 1, said["host"])
        level, text = said["host"][0]
        self.assertEqual(level, "WARN")
        self.assertIn("FreeBSD jail backend cannot engage: creating a "
                      "jail needs root", text)


@unittest.skipUnless(
    FC.IS_FREEBSD_BACKEND and os.geteuid() == 0 and _DISPOSABLE_GUEST,
    "making an account is tested on a disposable FreeBSD guest")
class LiveSuiteTest(_LiveSeed):
    """Other modules' tests run the installer and the wizard on
    whatever host the suite is on. This guest is the host where
    that matters: FreeBSD, root, a jail backend that engages --
    where the installer's seed, asked, makes the jobs account.
    The suite's word keeps those tests off the machine; the
    control shows what the same tests do without it."""

    # The tests that reach the seed from outside this module:
    # the installer's main with its service steps replaced, the
    # wizard, and the installer's own modules, which load copies
    # of it of their own.
    OTHERS = ("runner.tests.test_coverage_seams.InstallMainTest",
              "runner.tests.test_pi_light.InstallPiLightTest",
              "runner.tests.test_setup",
              "runner.tests.test_setup_gaps",
              "runner.tests.test_first_run_scenario",
              "runner.tests.test_first_ping",
              "runner.tests.test_install_edges",
              "runner.tests.test_install_onehome")
    MAIN = ("runner.tests.test_coverage_seams.InstallMainTest",)

    def setUp(self):
        super().setUp()
        # Each test starts with no such account and leaves none.
        LiveAccountTest._clear()
        self.addCleanup(LiveAccountTest._clear)

    def _run(self, names, word):
        """Those tests in a process of their own, as the suite
        starts them, with `word` in its environment (None: no
        word handed down, and the test package sets its own)."""
        env = dict(os.environ)
        env.pop(INS.SEED_SWITCH, None)
        if word is not None:
            env[INS.SEED_SWITCH] = word
        done = subprocess.run(
            [sys.executable, "-m", "unittest", *names], cwd=_REPO,
            env=env, capture_output=True, text=True, timeout=900)
        ran = re.search(r"^Ran (\d+) tests? in", done.stderr, re.M)
        return (int(ran.group(1)) if ran else 0), done.stderr[-3000:]

    def test_the_suite_s_own_tests_leave_the_user_database_alone(self):
        self.assertIsNone(_account_ids())
        ran, tail = self._run(self.OTHERS, None)
        self.assertGreaterEqual(ran, 100, tail)
        self.assertIsNone(
            _account_ids(), "the suite made the jobs account:\n" + tail)
        self._nothing_left()

    def test_the_same_tests_are_an_installer_where_the_word_is_on(self):
        # The control. With the questions on, the installer's
        # main as another module's tests run it is an install on
        # this machine: the probe passes here and the account is
        # made. It is removed again when this test ends.
        self.assertIsNone(_account_ids())
        ran, tail = self._run(self.MAIN, "1")
        self.assertGreaterEqual(ran, 3, tail)
        self.assertIsNotNone(
            _account_ids(),
            "the installer's main, asked, made no account:\n" + tail)
        self._nothing_left()
        # and switched off by a word handed down, it makes none
        LiveAccountTest._clear()
        self.assertIsNone(_account_ids())
        ran, tail = self._run(self.MAIN, "0")
        self.assertGreaterEqual(ran, 3, tail)
        self.assertIsNone(_account_ids(), tail)
        self._nothing_left()


if __name__ == "__main__":
    unittest.main()
