# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Windows Job Object containment for job_user: the seams.

Phase 1 backend (runner/guard/windows_confine.py) wired into the
job_user gates. The Win32 code cannot execute on this host, so
everything here runs through the injection seams: the startup
gate's decision table with a scripted backend, the preexec
hook's win32 record with os.name patched, and the postspawn
application against a fake process and a fake backend.

The honesty pins matter most: no audit record may name a control
the backend does not apply (there is no restricted token in
Phase 1), and every failure lands in the refuse direction.
"""
import ctypes
import importlib
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
from runner.guard import windows_confine as WC
from runner.ops import remediation_ops as REM
from runner.ops import setup as SU


def _cfg(mode):
    return {"security": {"modes": {"job_user": mode}}}


def _sec(mode, sink):
    sec = mock.Mock()
    sec.sec_mode.return_value = mode

    def _write(base_dir, feature, decision, reason, **kw):
        sink.append({"feature": feature, "decision": decision,
                     "reason": reason, "kw": kw})
    sec.write_audit_entry.side_effect = _write
    return sec


def _backend(problem=None, status="windows_job_object",
             job_handle=4242, apply_error=None):
    backend = types.SimpleNamespace()

    def _probe(cfg=None, timeout=15):
        if isinstance(problem, Exception):
            raise problem
        return problem

    def _apply(handle, memory_bytes=WC.DEFAULT_PROCESS_MEMORY_BYTES
               if hasattr(WC, "DEFAULT_PROCESS_MEMORY_BYTES")
               else 512 * 1024 * 1024):
        if apply_error is not None:
            raise apply_error
        if not handle:
            raise RuntimeError("no process handle")
        return status, job_handle

    backend.windows_startup_problem = _probe
    backend.windows_confinement_problem = _probe
    backend.apply_windows_containment = _apply
    backend.closed = []
    backend.close_job_handle = backend.closed.append
    backend.IS_WINDOWS_BACKEND = True
    backend.STATUS_CONFINEMENT = WC.STATUS_CONFINEMENT \
        if hasattr(WC, "STATUS_CONFINEMENT") else \
        "windows: job_object + restricted_token + low_integrity"
    backend.spawned = []

    def _spawn(argv, cwd=None, env=None):
        if apply_error is not None:
            raise apply_error
        proc = types.SimpleNamespace(
            pid=31337, _handle=888, returncode=None,
            confinement_status=backend.STATUS_CONFINEMENT,
            closed=False)
        proc.close = lambda: setattr(proc, "closed", True)
        backend.spawned.append((argv, cwd, proc))
        return proc

    backend.spawn_confined_process = _spawn
    return backend


def _ccfg(mode):
    return {"security": {"modes": {"confinement": mode}}}


class BackendStubTest(unittest.TestCase):
    """The module itself, on a host that is not Windows."""

    def setUp(self):
        if sys.platform == "win32":
            self.skipTest("the stub exists only off win32")

    def test_import_is_safe_and_the_probe_refuses(self):
        problem = WC.windows_startup_problem()
        self.assertIsInstance(problem, str)
        self.assertIn("Windows-only", problem)

    def test_apply_raises_and_close_is_a_noop(self):
        with self.assertRaises(RuntimeError):
            WC.apply_windows_containment(1234)
        self.assertIsNone(WC.close_job_handle(1234))
        self.assertIsNone(WC.close_job_handle(None))

    def test_the_status_names_only_the_job_object(self):
        self.assertEqual(WC.STATUS_JOB_OBJECT, "windows_job_object")
        self.assertNotIn("token", WC.STATUS_JOB_OBJECT)
        self.assertNotIn("restricted", WC.STATUS_JOB_OBJECT)


class SimulatedPlatformImportTest(unittest.TestCase):
    """The backend branch follows the host's ctypes surface.

    The suite's win32 simulation patches sys.platform (the seam
    test_decision1_startup and test_require_posture use). A first
    import of this module inside such a patch must still land
    on the stub: the platform string is simulated, but the host
    has no ctypes.WinDLL, and binding it at import raised
    AttributeError on POSIX hosts -- through main(), in the
    simulated-win32 startup tests. The branch is taken for real
    exactly when the platform is win32 AND the Windows ctypes
    surface is present; on a real Windows host both hold, so
    nothing there changes.
    """

    def setUp(self):
        if sys.platform == "win32":
            self.skipTest("the simulation is only meaningful off win32")

    def _fresh_import(self):
        key = "runner.guard.windows_confine"
        saved = sys.modules.get(key)
        sys.modules.pop(key, None)
        try:
            return importlib.import_module(key)
        finally:
            # Leave the module the rest of the suite imported
            # cached, exactly as it was.
            if saved is not None:
                sys.modules[key] = saved
            else:
                sys.modules.pop(key, None)

    def test_fresh_import_under_simulated_win32_gets_the_stub(self):
        with mock.patch.object(sys, "platform", "win32"):
            mod = self._fresh_import()
        self.assertFalse(mod.IS_WINDOWS_BACKEND)
        problem = mod.windows_confinement_problem()
        self.assertIsInstance(problem, str)
        self.assertIn("Windows-only", problem)

    def test_the_startup_gate_refuses_deterministically_under_simulation(self):
        with mock.patch.object(sys, "platform", "win32"):
            self._fresh_import()
            problem = REM.confinement_startup_problem(
                _ccfg("enforce"), platform="win32")
        self.assertEqual(
            "confinement (bwrap) is Linux-only; "
            "this machine is win32", problem)

    def test_a_windows_ctypes_surface_takes_the_real_branch(self):
        # The other direction of the branch: platform win32 and
        # the WinDLL surface present (faked here, real on a
        # Windows host) imports the real backend.
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(
                    ctypes, "WinDLL",
                    lambda *a, **k: mock.MagicMock(), create=True):
            mod = self._fresh_import()
        self.assertTrue(mod.IS_WINDOWS_BACKEND)


class StartupGateTableTest(unittest.TestCase):
    """job_user_startup_problem: win32 consults the backend."""

    def test_engageable_backend_lets_enforce_start(self):
        self.assertIsNone(rr._job_user_startup_problem(
            _cfg("enforce"), platform="win32",
            backend=_backend(None)))

    def test_unengageable_backend_refuses_and_names_why(self):
        problem = rr._job_user_startup_problem(
            _cfg("enforce"), platform="win32",
            backend=_backend("CreateJobObjectW failed: 5"))
        self.assertIsNotNone(problem)
        self.assertIn("job_user", problem)
        self.assertIn("win32", problem)
        self.assertIn("CreateJobObjectW failed: 5", problem)

    def test_a_backend_that_raises_still_refuses(self):
        problem = rr._job_user_startup_problem(
            _cfg("enforce"), platform="win32",
            backend=_backend(RuntimeError("dll gone")))
        self.assertIsNotNone(problem)
        self.assertIn("dll gone", problem)

    def test_audit_and_off_are_never_refused_by_the_gate(self):
        for mode in ("audit", "off"):
            self.assertIsNone(rr._job_user_startup_problem(
                _cfg(mode), platform="win32",
                backend=_backend("cannot engage")), mode)

    def test_non_win32_is_untouched_by_the_backend(self):
        # No configured user: the POSIX path has nothing to gate,
        # and the backend is never the reason either way.
        self.assertIsNone(rr._job_user_startup_problem(
            _cfg("enforce"), platform="linux",
            backend=_backend("cannot engage")))

    def test_simulated_win32_refusal_is_deterministic(self):
        # No backend injected and the platform simulated: the
        # gate cannot probe a machine this is not, so the
        # long-standing refusal stands, on any host.
        if sys.platform == "win32":
            self.skipTest("the host platform is the real one here")
        problem = rr._job_user_startup_problem(
            _cfg("enforce"), platform="win32")
        self.assertIsNotNone(problem)
        self.assertIn("job_user", problem)
        self.assertIn("win32", problem)


class PreexecWin32Test(unittest.TestCase):
    """_job_user_preexec on a simulated Windows host."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.work = os.path.join(self.base, "work")
        os.makedirs(self.work)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, mode, backend="unset"):
        sink = []
        if backend == "unset":
            # Scripted as a real backend that cannot engage, so
            # the legacy record is what every host answers.
            backend = _backend("cannot engage (scripted)")
        kw = {"backend": backend}
        with mock.patch.object(rr.os, "name", "nt"), \
                mock.patch.object(rr, "_security", _sec(mode, sink)):
            fn = REM._job_user_preexec(
                _cfg(mode), self.base, "j1", self.work, **kw)
        return fn, sink

    def test_audit_when_backend_cannot_engage_keeps_the_legacy_record(self):
        fn, sink = self._run("audit")
        self.assertIsNone(fn)
        self.assertEqual(sink[0]["decision"], "unsupported_platform")
        self.assertEqual(sink[0]["reason"], "job_user_posix_only")

    def test_enforce_when_backend_cannot_engage_refuses(self):
        with self.assertRaises(rr.JobRejected):
            self._run("enforce")

    def test_enforce_with_an_engageable_backend_defers(self):
        fn, sink = self._run("enforce", backend=_backend(None))
        self.assertIsNone(fn)
        self.assertEqual(sink[0]["decision"], "would_contain")
        self.assertEqual(sink[0]["reason"], "windows_job_object")

    def test_audit_with_an_engageable_backend_records_honestly(self):
        fn, sink = self._run("audit", backend=_backend(None))
        self.assertIsNone(fn)
        self.assertEqual(sink[0]["decision"], "would_contain")
        self.assertEqual(sink[0]["reason"], "windows_job_object")

    def test_enforce_with_a_broken_backend_still_refuses(self):
        sink = []
        with mock.patch.object(rr.os, "name", "nt"), \
                mock.patch.object(rr, "_security",
                                  _sec("enforce", sink)):
            with self.assertRaises(rr.JobRejected):
                REM._job_user_preexec(
                    _cfg("enforce"), self.base, "j1", self.work,
                    backend=_backend("cannot engage"))
        self.assertEqual(sink[0]["decision"], "unsupported_platform")


class PostspawnTest(unittest.TestCase):
    """_job_user_postspawn: the assignment itself, scripted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _proc(self, handle=777):
        proc = mock.Mock()
        proc._handle = handle
        return proc

    def _run(self, mode, proc, backend="unset", nt=True):
        sink = []
        kw = {} if backend == "unset" else {"backend": backend}
        with mock.patch.object(REM.os, "name",
                               "nt" if nt else "posix"), \
                mock.patch.object(rr, "_security", _sec(mode, sink)):
            out = REM._job_user_postspawn(
                _cfg(mode), self.base, "j1", proc, **kw)
        return out, sink

    def test_off_windows_is_a_noop(self):
        proc = self._proc()
        out, sink = self._run("enforce", proc, backend=_backend(None),
                              nt=False)
        self.assertIsNone(out)
        self.assertEqual(sink, [])

    def test_audit_applies_nothing(self):
        backend = _backend(None)
        backend.apply_windows_containment = mock.Mock(
            side_effect=AssertionError("must not apply under audit"))
        out, _sink = self._run("audit", self._proc(), backend=backend)
        self.assertIsNone(out)

    def test_enforce_applies_and_records_only_what_was_applied(self):
        backend = _backend(None)
        proc = self._proc()
        release, sink = self._run("enforce", proc, backend=backend)
        self.assertTrue(callable(release))
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["decision"], "contained")
        self.assertEqual(sink[0]["reason"], "windows_job_object")
        self.assertNotIn("token", sink[0]["reason"])
        release()
        self.assertEqual(backend.closed, [4242])

    def test_enforce_failure_kills_and_refuses(self):
        backend = _backend(None, apply_error=RuntimeError("assign 5"))
        proc = self._proc()
        sink = []
        with mock.patch.object(REM.os, "name", "nt"), \
                mock.patch.object(rr, "_security",
                                  _sec("enforce", sink)):
            with self.assertRaises(rr.JobRejected):
                REM._job_user_postspawn(
                    _cfg("enforce"), self.base, "j1", proc,
                    backend=backend)
        proc.kill.assert_called_once()
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"],
                         "windows_containment_failed")

    def test_enforce_without_a_process_handle_refuses(self):
        proc = types.SimpleNamespace(_handle=None, kill=mock.Mock())
        sink = []
        with mock.patch.object(REM.os, "name", "nt"), \
                mock.patch.object(rr, "_security",
                                  _sec("enforce", sink)):
            with self.assertRaises(rr.JobRejected):
                REM._job_user_postspawn(
                    _cfg("enforce"), self.base, "j1", proc,
                    backend=_backend(None))
        proc.kill.assert_called_once()

    def test_the_real_backend_off_windows_refuses(self):
        if sys.platform == "win32":
            self.skipTest("the real backend engages or not live")
        sink = []
        proc = self._proc()
        with mock.patch.object(REM.os, "name", "nt"), \
                mock.patch.object(rr, "_security",
                                  _sec("enforce", sink)):
            with self.assertRaises(rr.JobRejected):
                REM._job_user_postspawn(
                    _cfg("enforce"), self.base, "j1", proc)
        proc.kill.assert_called_once()


class ConfinementStubTest(unittest.TestCase):
    """The confinement half of the stub, on a non-Windows host."""

    def setUp(self):
        if sys.platform == "win32":
            self.skipTest("the stub exists only off win32")

    def test_the_confinement_probe_refuses_off_windows(self):
        self.assertIn("Windows-only", WC.windows_confinement_problem())

    def test_the_confined_spawn_raises_off_windows(self):
        with self.assertRaises(RuntimeError):
            WC.spawn_confined_process(["python", "script.py"])

    def test_the_status_names_exactly_the_three_controls(self):
        self.assertEqual(
            WC.STATUS_CONFINEMENT,
            "windows: job_object + restricted_token + low_integrity")
        self.assertEqual(
            WC.CONFINEMENT_CONTROLS,
            ("job_object", "restricted_token", "low_integrity"))
        self.assertNotIn("sandbox", WC.STATUS_CONFINEMENT)


class ConfinementStartupGateTest(unittest.TestCase):
    """confinement_startup_problem: win32 consults the backend."""

    def test_engageable_backend_lets_enforce_start(self):
        self.assertIsNone(rr._confinement_startup_problem(
            _ccfg("enforce"), platform="win32",
            backend=_backend(None)))

    def test_unengageable_backend_refuses_and_names_why(self):
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="win32",
            backend=_backend("CreateRestrictedToken failed: 5"))
        self.assertIsNotNone(problem)
        self.assertIn("confinement cannot engage on win32", problem)
        self.assertIn("CreateRestrictedToken failed: 5", problem)

    def test_a_backend_that_raises_still_refuses(self):
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="win32",
            backend=_backend(RuntimeError("dll gone")))
        self.assertIsNotNone(problem)
        self.assertIn("dll gone", problem)

    def test_audit_and_off_are_never_refused_by_the_gate(self):
        for mode in ("audit", "off"):
            self.assertIsNone(rr._confinement_startup_problem(
                _ccfg(mode), platform="win32",
                backend=_backend("cannot engage")), mode)

    def test_non_win32_is_untouched_by_the_backend(self):
        self.assertIsNone(rr._confinement_startup_problem(
            _ccfg("enforce"), platform="linux",
            backend=_backend("cannot engage")))

    def test_simulated_win32_refusal_is_deterministic(self):
        if sys.platform == "win32":
            self.skipTest("the host platform is the real one here")
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="win32")
        self.assertEqual(
            problem,
            "confinement (bwrap) is Linux-only; this machine is win32")


class ConfinementArgvTest(unittest.TestCase):
    """_confinement_argv on a simulated win32: the argv gate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, mode, backend):
        sink = []
        with mock.patch.object(sys, "platform", "win32"), \
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
        out, sink = self._run("enforce",
                              _backend("no token for you"))
        self.assertEqual(out, ([], True, False))
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"], "confinement_unavailable")


class ConfinementSpawnTest(unittest.TestCase):
    """_confinement_spawn: the creation-time application."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, mode, backend="unset", nt=True):
        sink = []
        kw = {} if backend == "unset" else {"backend": backend}
        with mock.patch.object(REM.os, "name", "nt" if nt else "posix"), \
                mock.patch.object(rr, "_security", _sec(mode, sink)):
            out = REM._confinement_spawn(
                _ccfg(mode), self.base, "j1", ["python", "s.py"],
                self.base, {}, **kw)
        return out, sink

    def test_off_windows_is_a_noop(self):
        out, sink = self._run("enforce", backend=_backend(None),
                              nt=False)
        self.assertIsNone(out)
        self.assertEqual(sink, [])

    def test_audit_and_off_spawn_nothing(self):
        for mode in ("audit", "off"):
            out, _sink = self._run(mode, backend=_backend(None))
            self.assertIsNone(out, mode)

    def test_enforce_spawns_and_records_exactly_the_controls(self):
        backend = _backend(None)
        (proc, release), sink = self._run("enforce", backend=backend)
        self.assertEqual(proc.pid, 31337)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["feature"], "confinement")
        self.assertEqual(sink[0]["decision"], "confined")
        self.assertEqual(
            sink[0]["reason"],
            "windows: job_object + restricted_token + low_integrity")
        self.assertNotIn("sandbox", sink[0]["reason"])
        release()
        self.assertTrue(proc.closed)

    def test_enforce_spawn_failure_refuses_and_records_fallback(self):
        backend = _backend(None, apply_error=RuntimeError("spawn 5"))
        sink = []
        with mock.patch.object(REM.os, "name", "nt"), \
                mock.patch.object(rr, "_security",
                                  _sec("enforce", sink)):
            with self.assertRaises(rr.JobRejected):
                REM._confinement_spawn(
                    _ccfg("enforce"), self.base, "j1",
                    ["python", "s.py"], self.base, {}, backend=backend)
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"],
                         "windows_confinement_failed")


class SeedShapeUnchangedTest(unittest.TestCase):
    """This landing does not move the seeded platform gates."""

    def test_a_fresh_win32_seed_still_states_audit(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        SU.seed_platform_modes(cfg, platform="win32")
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        self.assertEqual(cfg["security"]["modes"]["job_user"],
                         "audit")


if __name__ == "__main__":
    unittest.main()
