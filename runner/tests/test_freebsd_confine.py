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
import shutil
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
    and the jails still standing under this backend's name."""
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
    return mounts, dirs, jails


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
        self.assertEqual(after[0] - before[0], set(),
                         "mounts left behind")
        self.assertEqual(after[1] - before[1], set(),
                         "skeleton directories left behind")
        self.assertEqual(after[2] - before[2], set(),
                         "jails left standing")

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
        self.assertEqual(after[0] - before[0], set(),
                         "mounts left behind")
        self.assertEqual(after[2] - before[2], set(),
                         "jails left standing")


if __name__ == "__main__":
    unittest.main()
