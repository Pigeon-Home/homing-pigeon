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
import subprocess
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


class _FakeTrialProc:
    """The confined-process shape the trial drives, scripted."""

    def __init__(self, out=b"", err=b"", returncode=0, work=None,
                 write_file=False, timeout=False):
        self._out = out
        self._err = err
        self.returncode = returncode
        self._work = work
        self._write_file = write_file
        self._timeout = timeout
        self.killed = False
        self.closed = False

    def communicate(self, timeout=None):
        if self._timeout:
            raise subprocess.TimeoutExpired("trial", timeout)
        if self._write_file and self._work is not None:
            with open(os.path.join(self._work, "trial-out.txt"),
                      "w") as fh:
                fh.write("hp-confinement-trial\n")
        return self._out, self._err

    def kill(self):
        self.killed = True

    def close(self):
        self.closed = True


class ConfinementTrialProblemTest(unittest.TestCase):
    """confinement_trial_problem through scripted spawn seams.

    The trial orchestration is platform-neutral (it stages
    files and drives a spawn callable), so it is exercised
    here on any host; the real backend wires it to
    spawn_confined_process on Windows and caches the verdict.
    """

    def _spawn(self, proc_factory, record):
        def _spawn(argv, cwd=None, env=None):
            record["argv"] = argv
            record["cwd"] = cwd
            record["staged_existed"] = all(
                os.path.exists(p) for p in argv[1:])
            return proc_factory(cwd)
        return _spawn

    def test_trial_ok_answers_none_and_cleans_up(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n",
                work=work, write_file=True), record)
        self.assertIsNone(WC.confinement_trial_problem(spawn))
        self.assertTrue(record["staged_existed"])
        # The staged tree is the trial's own temp tree, removed
        # after the run.
        self.assertFalse(os.path.exists(record["argv"][2]))

    def test_trial_read_failure_names_the_staged_read(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=b"", err=b"PermissionError: [Errno 13] denied",
                returncode=1), record)
        problem = WC.confinement_trial_problem(spawn)
        self.assertIsNotNone(problem)
        self.assertIn("could not read its staged file", problem)
        self.assertIn("exit 1", problem)

    def test_trial_write_failure_names_the_work_write(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=b"TRIAL-READ-OK\n",
                err=b"PermissionError: [Errno 13] denied",
                returncode=1), record)
        problem = WC.confinement_trial_problem(spawn)
        self.assertIsNotNone(problem)
        self.assertIn("could not write its work directory", problem)

    def test_trial_spawn_failure_names_the_spawn(self):
        def _spawn(argv, cwd=None, env=None):
            raise RuntimeError("CreateProcessAsUserW failed: 5")
        problem = WC.confinement_trial_problem(_spawn)
        self.assertIsNotNone(problem)
        self.assertIn("confined trial spawn failed", problem)
        self.assertIn("CreateProcessAsUserW failed: 5", problem)

    def test_trial_timeout_names_the_timeout_and_kills(self):
        record = {}
        holder = {}

        def _factory(work):
            holder["proc"] = _FakeTrialProc(timeout=True)
            return holder["proc"]

        spawn = self._spawn(_factory, record)
        problem = WC.confinement_trial_problem(spawn, timeout=3)
        self.assertIsNotNone(problem)
        self.assertIn("timed out", problem)
        self.assertTrue(holder["proc"].killed)
        self.assertTrue(holder["proc"].closed)


class ConfinementTrialStagingTest(unittest.TestCase):
    """The trial's staging shape (the Q134 addendum).

    The trial first staged with tempfile.mkdtemp, whose
    directory carries a DACL naming only SYSTEM,
    Administrators and OWNER RIGHTS. Under an elevated
    administrator the confined token holds none of those
    enabled, and the trial refused the host at the staged
    read for a reason that was the staging's, not the host's
    -- found by the rig battery (Q134's second-seat re-test)
    after the unelevated field verification had passed. These
    tests pin the replacement shape through the
    platform-neutral seams: the tree is created with
    os.makedirs at the default mode, and a grant callable
    assures the token-carried Users group read+execute on
    the staged paths before the spawn. The real DACL call
    cannot execute off Windows, and nothing here pretends it
    does; what is pinned is the staging helper's behavior,
    the grant contract, and the SDDL the real grant applies,
    which stands in the module where any host can read it.
    """

    def _ok_spawn(self, record):
        def _spawn(argv, cwd=None, env=None):
            record["argv"] = argv
            record["cwd"] = cwd
            return _FakeTrialProc(
                out=b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n",
                work=cwd, write_file=True)
        return _spawn

    def test_staging_never_calls_mkdtemp(self):
        record = {}
        with mock.patch.object(
                tempfile, "mkdtemp",
                side_effect=AssertionError("mkdtemp was called")):
            self.assertIsNone(WC.confinement_trial_problem(
                self._ok_spawn(record)))
        root = os.path.dirname(record["argv"][2])
        self.assertTrue(os.path.basename(root).startswith(
            "hp-confinement-trial-"))
        self.assertEqual(
            os.path.realpath(os.path.dirname(root)),
            os.path.realpath(tempfile.gettempdir()))
        # The tree is still the trial's own, removed afterwards.
        self.assertFalse(os.path.exists(root))

    def test_staging_root_is_created_with_makedirs(self):
        record = {}
        made = []
        real_makedirs = os.makedirs

        def _spy(path, *args, **kwargs):
            made.append(path)
            return real_makedirs(path, *args, **kwargs)

        with mock.patch.object(os, "makedirs", _spy):
            self.assertIsNone(WC.confinement_trial_problem(
                self._ok_spawn(record)))
        root = os.path.dirname(record["argv"][2])
        self.assertIn(root, made)
        self.assertIn(record["cwd"], made)

    def test_grant_runs_on_the_staged_paths_before_the_spawn(self):
        events = []

        def _grant(paths):
            events.append(("grant", list(paths), all(
                os.path.exists(p) for p in paths)))
            return None

        def _spawn(argv, cwd=None, env=None):
            events.append(("spawn", argv))
            return _FakeTrialProc(
                out=b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n",
                work=cwd, write_file=True)

        self.assertIsNone(WC.confinement_trial_problem(
            _spawn, grant=_grant))
        self.assertEqual([e[0] for e in events],
                         ["grant", "spawn"])
        self.assertTrue(events[0][2])
        paths = events[0][1]
        self.assertEqual(len(paths), 4)
        root, staged, program, work = paths
        self.assertEqual(os.path.dirname(staged), root)
        self.assertEqual(os.path.dirname(program), root)
        self.assertEqual(os.path.dirname(work), root)
        self.assertEqual(events[1][1][1:],
                         [program, staged, work])

    def test_grant_problem_is_the_trials_answer(self):
        spawned = []

        def _grant(paths):
            return "SetNamedSecurityInfoW failed: 5"

        def _spawn(argv, cwd=None, env=None):
            spawned.append(argv)
            raise AssertionError("spawn must not run")

        problem = WC.confinement_trial_problem(
            _spawn, grant=_grant)
        self.assertIsNotNone(problem)
        self.assertIn("staged tree", problem)
        self.assertIn("SetNamedSecurityInfoW failed: 5", problem)
        self.assertEqual(spawned, [])

    def test_grant_exception_is_a_problem_not_a_crash(self):
        def _grant(paths):
            raise RuntimeError("advapi32 unavailable")

        problem = WC.confinement_trial_problem(
            self._ok_spawn({}), grant=_grant)
        self.assertIsNotNone(problem)
        self.assertIn("advapi32 unavailable", problem)

    def test_the_grant_sddl_names_users_read_execute(self):
        # The SDDL the real backend's grant applies stands in
        # the platform-neutral section so any host can pin it:
        # an inheriting allow ACE for BUILTIN\\Users
        # (S-1-5-32-545) at generic read+execute, and no write
        # for the group -- the work-directory write rides the
        # spawn's own labelling, as the field test showed.
        self.assertIn("S-1-5-32-545", WC.TRIAL_GRANT_SDDL)
        self.assertIn("A;OICI;GRGX", WC.TRIAL_GRANT_SDDL)
        self.assertNotIn("GW", WC.TRIAL_GRANT_SDDL)
        self.assertEqual(WC.TRIAL_USERS_SID, "S-1-5-32-545")

    def test_the_backend_wires_the_grant_into_the_trial(self):
        # POSIX cannot execute the real branch, so the wiring
        # is pinned at the source: windows_confinement_problem
        # must hand its DACL grant to the trial, or an elevated
        # host silently loses the fix.
        with open(WC.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("grant=_grant_users_read_execute", src)
        self.assertIn("TRIAL_GRANT_SDDL", src)


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
