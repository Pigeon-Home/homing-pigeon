# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""FreeBSD jail containment for confinement: the seams.

Backend (runner/guard/freebsd_confine.py) wired into the
confinement gates. The FreeBSD code cannot execute on this
host, so everything here runs through the injection seams: the
startup gate's decision table with a scripted backend, the argv
gate with sys.platform patched, and the spawn seam against a
fake backend. The live class runs only on a FreeBSD host as
root, where the backend is real.

The honesty pins matter most: no audit record may name a
control the backend does not apply (there is no rctl rule and
no Capsicum in this backend), and every failure lands in the
refuse direction.
"""
import os
import sys
import tempfile
import types
import unittest
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


def _backend(problem=None, apply_error=None):
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

    def _spawn(argv, cwd=None, env=None, user=None):
        if apply_error is not None:
            raise apply_error
        proc = types.SimpleNamespace(
            pid=31337, returncode=None,
            confinement_status=backend.STATUS_CONFINEMENT,
            closed=False)
        proc.close = lambda: setattr(proc, "closed", True)
        backend.spawned.append(
            {"argv": argv, "cwd": cwd, "env": env, "user": user,
             "proc": proc})
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

    def test_unengageable_backend_refuses_the_job(self):
        sink = []
        with mock.patch.object(sys, "platform", "freebsd14"), \
                mock.patch.object(rr, "_security",
                                  _sec("enforce", sink)):
            with self.assertRaises(rr.JobRejected):
                rr._confinement_argv(
                    _ccfg("enforce"), self.base, "j1", ["python"],
                    "script.py", self.base, [], {},
                    backend=_backend("not root"))
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


class SeedShapeTest(unittest.TestCase):
    """The seed keeps the Windows pattern: stated, not probed."""

    def test_platform_modes_states_confinement_audit_only(self):
        self.assertEqual(INS.platform_modes("freebsd14"),
                         {"confinement": "audit"})

    def test_a_fresh_freebsd_seed_states_confinement_audit(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        SU.seed_platform_modes(cfg, platform="freebsd14")
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        # job_user is a POSIX demote and engages on FreeBSD; the
        # seed does not state it down.
        self.assertEqual(cfg["security"]["modes"]["job_user"],
                         "enforce")


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
        with self.assertRaises(RuntimeError):
            FC.build_jail_argv(["/root/private/python3"], cwd=None)

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


if __name__ == "__main__":
    unittest.main()
