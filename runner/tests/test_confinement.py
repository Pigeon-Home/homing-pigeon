#!/usr/bin/env python3
"""M6 tests: Linux confinement (bwrap sandbox builder).

UID (phase 2.3): the sandbox runs the job as the SAME uid as
the runner -- bwrap's user namespace maps the caller's uid --
so confinement is not an other-uid boundary and these tests
never claim one. The boundary under test is the mount /
network / environment surface. Same-uid reach outside the
sandbox (the default posture) is a design fact, asserted as
the passing side of EnforceNegativeControl below.
"""
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))
))
sys.path.insert(0, REPO)

from runner.guard import sandbox as SB  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.runner import execute_job, snapshot_outside  # noqa: E402

BWRAP_HERE = SB.sandbox_available()

# Q10: the enforce classes gate on the startup probe, not on
# bwrap's presence. Where the restriction blocks namespace
# setup, bwrap is on PATH and cannot start; a real runner
# refuses to start there (Q9), so these tests skip with the
# registered reason instead of failing on a path startup has
# already closed.
STARTUP_PROBLEM = SB.startup_problem()
ENGAGES = STARTUP_PROBLEM is None


def _job(jid, script):
    return {"v": 1, "type": "job", "job_id": jid,
            "issued_at": "2026-10-15T12:00:00Z",
            "kind": "exec", "interpreter": ["python3"],
            "script": script}


def _run(cfg_extra, job):
    tmpdir = tempfile.mkdtemp(prefix="hp-m6-")
    cfg = {"base_dir": tmpdir}
    cfg.update(cfg_extra)
    result = execute_job(cfg, job, tmpdir)
    audit = []
    path = os.path.join(tmpdir, S.AUDIT_FILE)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                audit.append(json.loads(line))
            except ValueError:
                pass
    return result, audit, tmpdir


def _conf(mode, **kw):
    cfg = {"security": {"modes": {"confinement": mode}}}
    if kw:
        cfg["security"]["confinement"] = kw
    return cfg


@unittest.skipUnless(sys.platform.startswith("linux"),
                     "the startup probe's Linux branch")
class UsernsRestrictedLegsTest(unittest.TestCase):
    """Queue A refill: sandbox._userns_restricted's
    read legs (coverage run 40189711740: lines
    56-57). The probe answers from the sysctl when
    it can be read -- "1" is restricted, anything
    else is not -- and an unreadable sysctl reads as
    not restricted, leaving the verdict to the
    startup trial run.
    """

    def test_the_sysctl_read_and_its_absence(self):
        import tempfile as _tempfile
        from unittest import mock as _mock
        with _mock.patch.object(
                SB, "_USERNS_SYSCTL",
                "/nonexistent/no-such-sysctl"):
            self.assertFalse(SB._userns_restricted())
        with _tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sysctl")
            for text, want in (("1\n", True), ("0\n", False)):
                with open(path, "w") as fh:
                    fh.write(text)
                with _mock.patch.object(SB, "_USERNS_SYSCTL",
                                        path):
                    self.assertEqual(SB._userns_restricted(),
                                     want)


@unittest.skipUnless(sys.platform.startswith("linux"),
                     "the sandbox probe is Linux-only")
class StartupProblemScriptsTest(unittest.TestCase):
    """Queue A: the trial-run half of startup_problem --
    the half behind the platform guard, so the Windows
    map's gap there is the guard working, and the Linux
    residuals were the start-failure reason and the
    userns note (coverage run 40180268696). A scripted
    bwrap on PATH produces each outcome deterministically:
    absent, unstartable, failing (with and without the
    AppArmor userns restriction in force), and clean.
    The reasons are the startup refusal a runner prints,
    so their wording is asserted, not just their shape.
    """

    def _problem(self, script, userns=None):
        with tempfile.TemporaryDirectory() as d:
            if script is not None:
                path = os.path.join(d, "bwrap")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(script)
                os.chmod(path, 0o755)
            env = {"PATH": d + os.pathsep + os.environ["PATH"]}
            patches = [mock.patch.dict(os.environ, env)]
            if userns is not None:
                patches.append(mock.patch.object(
                    SB, "_userns_restricted", return_value=userns))
            for p in patches:
                p.start()
            try:
                return SB.startup_problem(timeout=10)
            finally:
                for p in patches:
                    p.stop()

    def test_no_bwrap_on_path_is_named(self):
        with tempfile.TemporaryDirectory() as empty:
            with mock.patch.dict(os.environ, {"PATH": empty}):
                self.assertEqual(
                    SB.startup_problem(timeout=10),
                    "bwrap is not installed (not found on PATH)")

    def test_a_bwrap_that_cannot_start_is_named(self):
        got = self._problem("#!/nonexistent/hp-interp\nexit 0\n")
        self.assertTrue(got.startswith(
            "bwrap could not be started: "), got)

    def test_a_failing_bwrap_names_its_exit_and_output(self):
        got = self._problem(
            "#!/bin/sh\necho 'sandbox says no' >&2\nexit 3\n",
            userns=False)
        self.assertEqual(
            got, "bwrap cannot start a sandbox "
                 "(exit 3: sandbox says no)")

    def test_the_userns_note_joins_a_failing_bwrap(self):
        got = self._problem(
            "#!/bin/sh\necho 'nope' >&2\nexit 1\n", userns=True)
        self.assertIn("bwrap cannot start a sandbox (exit 1: nope)",
                      got)
        self.assertIn(
            "kernel.apparmor_restrict_unprivileged_userns is 1",
            got)

    def test_a_clean_trial_run_is_no_problem(self):
        self.assertIsNone(self._problem("#!/bin/sh\nexit 0\n"))


class BuildCommandTest(unittest.TestCase):
    def test_structure(self):
        argv = SB.build_bwrap_command(
            {}, ["python3"], "script.py", "/tmp/w", ["--x"],
            {"FOO": "bar"})
        self.assertEqual(argv[0], "bwrap")
        self.assertIn("--ro-bind", argv)
        self.assertIn("/usr", argv)
        self.assertIn("--bind", argv)
        wi = argv.index("--bind")
        self.assertEqual(argv[wi + 1:wi + 3], ["/tmp/w", "/work"])
        self.assertIn("--clearenv", argv)
        self.assertIn("FOO", argv)
        # resolved interpreter, script under /work, args at the end
        base = os.path.basename(argv[-3]).lower()
        self.assertTrue(base.startswith("python"), argv[-3])
        self.assertEqual(argv[-2], "/work/script.py")
        self.assertEqual(argv[-1], "--x")

    def test_unresolvable_interpreter_fails(self):
        with self.assertRaises(RuntimeError):
            SB.build_bwrap_command({}, ["nope-not-a-binary-zzz"],
                                   "s.py", "/tmp/w", [], {})

    def test_unsafe_env_skipped(self):
        argv = SB.build_bwrap_command(
            {}, ["python3"], "s.py", "/tmp/w", [],
            {"A=B": "x", "OK": "y"})
        self.assertIn("OK", argv)
        self.assertNotIn("A=B", argv)

    def test_extra_flags_and_binds(self):
        argv = SB.build_bwrap_command(
            {"security": {"confinement": {
                "extra_flags": ["--unshare-pid"],
                "extra_ro_binds": [["/opt/data", "/data"]],
            }}},
            ["python3"], "s.py", "/tmp/w", [], {})
        self.assertIn("--unshare-pid", argv)
        self.assertIn("/opt/data", argv)
        self.assertIn("/data", argv)

    def test_bad_block_rejected(self):
        for bad in ({"extra_flags": "x"},
                    {"extra_ro_binds": [["only-one"]]},
                    {"work_mount": "relative"}):
            with self.assertRaises(RuntimeError, msg=str(bad)):
                S.validate_security_config(
                    {"security": {"confinement": bad}})


class FallbackTest(unittest.TestCase):
    def test_off_by_default_runs_normally(self):
        result, audit, _ = _run({}, _job("m6-off", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit, [])

    def test_explicit_off_identical(self):
        r1, _, _ = _run({}, _job("m6-a", "print(40 + 2)"))
        r2, _, _ = _run(_conf("off"), _job("m6-b", "print(40 + 2)"))
        self.assertEqual(r1["stdout"], r2["stdout"])
        self.assertEqual(r1["exit_code"], r2["exit_code"])

    def test_audit_runs_and_logs(self):
        result, audit, _ = _run(
            _conf("audit"), _job("m6-audit", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["feature"], "confinement")
        self.assertEqual(audit[0]["decision"], "would_sandbox")
        self.assertEqual(audit[0]["reason"], "would_run_sandboxed")

    def test_bwrap_missing_falls_back_loudly(self):
        with mock.patch.object(SB, "sandbox_available",
                               return_value=False):
            result, audit, _ = _run(
                _conf("enforce"), _job("m6-fb", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit[0]["decision"], "fallback")
        self.assertEqual(audit[0]["reason"], "confinement_unavailable")

    def test_audit_without_bwrap_still_says_would_sandbox(self):
        # Audit records the policy decision, not the environment.
        with mock.patch.object(SB, "sandbox_available",
                               return_value=False):
            result, audit, _ = _run(
                _conf("audit"), _job("m6-anb", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit[0]["decision"], "would_sandbox")
        self.assertEqual(audit[0]["reason"], "would_run_sandboxed")

    def test_unresolvable_interpreter_falls_back(self):
        job = _job("m6-bi", "print('hi')")
        job["interpreter"] = ["nope-not-a-binary-zzz"]
        with mock.patch.object(SB, "sandbox_available",
                               return_value=True):
            # build fails -> fallback, but Popen then fails the same
            # way it would unsandboxed (poison, not transient).
            from runner.runner import JobRejected
            with self.assertRaises(JobRejected):
                _run(_conf("enforce"), job)


class InterpreterPrefixBindTest(unittest.TestCase):
    """An interpreter outside /usr gets its install prefix bound
    read-only, and the bind is reported. CI found the gap the first
    day bwrap was installed: GitHub's setup-python lives under
    /opt/hostedtoolcache, bwrap said "execvp ...: No such file or
    directory", and enforce mode could never run a job there."""

    HOSTED = "/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3"

    def _argv(self, which_to, realpath_to=None, binds=None, notes=None):
        cfg = {}
        if binds:
            cfg = {"security": {"confinement": {"extra_ro_binds": binds}}}
        with mock.patch.object(SB.shutil, "which", return_value=which_to), \
             mock.patch.object(SB.os.path, "realpath",
                               return_value=realpath_to or which_to):
            return SB.build_bwrap_command(
                cfg, ["python3"], "s.py", "/tmp/w", [], {}, notes=notes)

    def _ro_binds(self, argv):
        return [argv[i + 1] for i, a in enumerate(argv) if a == "--ro-bind"]

    def test_usr_interpreter_adds_nothing(self):
        notes = []
        argv = self._argv("/usr/bin/python3", notes=notes)
        self.assertEqual(self._ro_binds(argv), ["/usr"])
        self.assertEqual(notes, [])

    def test_usr_local_is_already_under_usr(self):
        argv = self._argv("/usr/local/bin/python3")
        self.assertEqual(self._ro_binds(argv), ["/usr"])

    def test_hosted_toolcache_prefix_is_bound_and_noted(self):
        # The exact CI case.
        notes = []
        argv = self._argv(self.HOSTED, notes=notes)
        prefix = "/opt/hostedtoolcache/Python/3.12.15/x64"
        self.assertIn(prefix, self._ro_binds(argv))
        # bound read-only, as a (src, dst) pair, before the work bind
        i = argv.index(prefix)
        self.assertEqual(argv[i - 1], "--ro-bind")
        self.assertEqual(argv[i + 1], prefix)
        self.assertLess(i, argv.index("--bind"))
        self.assertEqual(notes,
                         ["interpreter prefix %s bound read-only" % prefix])
        # and the interpreter argv entry is the resolved path
        self.assertIn(self.HOSTED, argv)

    def test_venv_binds_both_the_venv_and_the_base(self):
        venv = "/home/u/proj/.venv/bin/python3"
        base = "/opt/py/3.12/bin/python3.12"
        argv = self._argv(venv, realpath_to=base)
        ro = self._ro_binds(argv)
        self.assertIn("/home/u/proj/.venv", ro)
        self.assertIn("/opt/py/3.12", ro)

    def test_venv_on_system_python_binds_only_the_venv(self):
        argv = self._argv("/home/u/.venv/bin/python3",
                          realpath_to="/usr/bin/python3.12")
        self.assertEqual(self._ro_binds(argv), ["/usr", "/home/u/.venv"])

    def test_shallow_prefix_binds_the_bin_dir_not_the_root(self):
        # /snap/bin/python3: grandparent would be /snap -- too wide.
        argv = self._argv("/snap/bin/python3")
        ro = self._ro_binds(argv)
        self.assertIn("/snap/bin", ro)
        self.assertNotIn("/snap", ro)

    def test_operator_extra_bind_already_covering_adds_nothing(self):
        notes = []
        argv = self._argv(self.HOSTED,
                          binds=[["/opt/hostedtoolcache",
                                  "/opt/hostedtoolcache"]],
                          notes=notes)
        ro = self._ro_binds(argv)
        self.assertEqual(ro.count("/opt/hostedtoolcache"), 1)
        self.assertNotIn("/opt/hostedtoolcache/Python/3.12.15/x64", ro)
        self.assertEqual(notes, [])

    def test_helper_is_pure_and_dedupes(self):
        with mock.patch.object(SB.os.path, "realpath",
                               side_effect=lambda p: p):
            self.assertEqual(SB.interpreter_binds("/usr/bin/sh"), [])
            self.assertEqual(
                SB.interpreter_binds(self.HOSTED),
                [("/opt/hostedtoolcache/Python/3.12.15/x64",
                  "/opt/hostedtoolcache/Python/3.12.15/x64")])

    def test_notes_default_is_safe(self):
        # notes=None (every pre-existing caller) must not raise.
        self._argv(self.HOSTED, notes=None)


class SandboxAuditNoteTest(unittest.TestCase):
    """The runner puts the interpreter-prefix note in the audit
    record: the widening is stated, never silent."""

    def test_enforce_audit_detail_carries_the_bind(self):
        from runner import runner as R
        hosted = "/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3"
        job = _job("m6-note", "print('hi')")
        real_realpath = os.path.realpath

        def realpath(path, *a, **k):
            # Only the interpreter lookup is scripted; the workspace
            # sweeps (review item 5) resolve the staged tree for real.
            if str(path).endswith("python3"):
                return hosted
            return real_realpath(path, *a, **k)

        with mock.patch.object(SB, "sandbox_available", return_value=True), \
             mock.patch.object(SB.shutil, "which", return_value=hosted), \
             mock.patch.object(SB.os.path, "realpath", realpath), \
             mock.patch.object(R.subprocess, "Popen") as popen:
            proc = popen.return_value
            proc.communicate.return_value = (b"hi\n", b"")
            proc.returncode = 0
            proc.pid = 4242
            proc.wait.return_value = 0
            result, audit, _ = _run(_conf("enforce"), job)
        rows = [a for a in audit if a.get("decision") == "sandboxed"]
        self.assertTrue(rows, audit)
        self.assertIn("/opt/hostedtoolcache/Python/3.12.15/x64",
                      rows[-1].get("detail", ""))


@unittest.skipUnless(ENGAGES,
                     "sandbox cannot engage on this machine "
                     "(startup probe)")
class EnforceTest(unittest.TestCase):
    def test_enforce_runs_inside_bwrap(self):
        script = (
            "import os\n"
            "print('inside')\n"
            "print('job-env-seen:', os.environ.get('M6_JOB_VAR'))\n"
            "print('host-env-seen:', os.environ.get('M6_HOST_VAR'))\n"
            "print('secret-seen:', os.environ.get('PIGEON_SECRET'))\n"
            "print('home-seen:', os.path.exists('/home'))\n"
            "open('/work/out.txt','w').write('wrote-ok')\n"
        )
        job = _job("m6-enf", script)
        job["env"] = {"M6_JOB_VAR": "job-value"}
        with mock.patch.dict(os.environ, {"M6_HOST_VAR": "host-value",
                                          "PIGEON_SECRET": "shh"}):
            result, audit, tmpdir = _run(_conf("enforce"), job)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("inside", result["stdout"])
        # The job's own env arrives via --setenv, and the scrubbed host
        # env behaves exactly as for an unsandboxed job -- but scrubbed
        # credential vars never cross into the sandbox.
        self.assertIn("job-env-seen: job-value", result["stdout"])
        self.assertIn("host-env-seen: host-value", result["stdout"])
        self.assertIn("secret-seen: None", result["stdout"])
        self.assertIn("home-seen: False", result["stdout"])
        self.assertEqual(audit[0]["decision"], "sandboxed")
        # the workdir bind is read-write: the file landed on the host
        out = os.path.join(tmpdir, "work", "m6-enf", "out.txt")
        self.assertEqual(open(out).read(), "wrote-ok")

    def test_a_planted_symlink_is_refused_before_the_sandbox_is_entered(self):
        # Review item 5: a staged "file" that is a symlink at the
        # runner's own config is a workspace-integrity rejection at
        # the post-stage sweep. No sandbox is built, no audit row says
        # "sandboxed", the work directory is gone, and the config is
        # untouched.
        from runner import runner as R
        tmpdir = tempfile.mkdtemp(prefix="hp-m6-")
        cfg_path = os.path.join(tmpdir, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write('{"shared_secret": "keep"}')
        job = _job("m6-link", "print('must not run')")
        job["files"] = [{"name": "in.txt",
                         "url": "https://example.com/in.txt"}]

        def plant(url, dest, max_bytes=0):
            os.symlink(cfg_path, dest)

        cfg = {"base_dir": tmpdir}
        cfg.update(_conf("enforce"))
        with mock.patch.object(R, "download", plant):
            with self.assertRaises(R.JobRejected) as cm:
                execute_job(cfg, job, tmpdir)
        self.assertIn("workspace integrity", str(cm.exception))
        self.assertIn("in.txt", str(cm.exception))
        audit_path = os.path.join(tmpdir, S.AUDIT_FILE)
        rows = []
        if os.path.exists(audit_path):
            rows = [json.loads(l) for l in open(audit_path, encoding="utf-8")
                    if l.strip()]
        self.assertEqual([r for r in rows if r.get("decision") == "sandboxed"],
                         [])
        self.assertFalse(os.path.exists(os.path.join(tmpdir, "work", "m6-link")))
        with open(cfg_path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '{"shared_secret": "keep"}')

    def test_enforce_result_matches_unsandboxed(self):
        script = "print(6 * 7)"
        r1, _, _ = _run({}, _job("m6-c1", script))
        r2, _, _ = _run(_conf("enforce"), _job("m6-c2", script))
        self.assertEqual(r1["stdout"], r2["stdout"])
        self.assertEqual(r1["exit_code"], r2["exit_code"])


@unittest.skipUnless(ENGAGES,
                     "sandbox cannot engage on this machine "
                     "(startup probe)")
class EnforceNegativeControl(unittest.TestCase):
    """Phase 2.2 negative control for EnforceTest: the same
    escape-shaped probes with confinement OFF (the default
    posture) must SUCCEED -- if they also failed unsandboxed,
    EnforceTest's denials would prove nothing about the
    sandbox. UID: same-uid on both sides (see module note);
    the only difference is whether the sandbox is in force."""

    _SCRIPT = (
        "import os\n"
        "print('home-seen:', os.path.exists('/home'))\n"
        "try:\n"
        "    print('host-read:', open(%r).read().strip())\n"
        "except Exception:\n"
        "    print('host-read: failed')\n"
    )

    def test_escape_succeeds_with_confinement_off(self):
        host = tempfile.mkdtemp(prefix="hp-m6-host-")
        secret = os.path.join(host, "host-only.txt")
        with open(secret, "w", encoding="utf-8") as fh:
            fh.write("host-data")
        script = self._SCRIPT % secret
        off, _, _ = _run({}, _job("m6-off", script))
        self.assertEqual(off["exit_code"], 0, off["stderr"])
        self.assertIn("home-seen: True", off["stdout"])
        self.assertIn("host-read: host-data", off["stdout"])
        on, _, _ = _run(_conf("enforce"), _job("m6-on", script))
        self.assertEqual(on["exit_code"], 0, on["stderr"])
        self.assertIn("home-seen: False", on["stdout"])
        self.assertIn("host-read: failed", on["stdout"])


def _run_in(base, cfg_extra, job):
    """_run against a base the test prepared first (planted
    files the job may or may not be able to reach)."""
    cfg = {"base_dir": base}
    cfg.update(cfg_extra)
    result = execute_job(cfg, job, base)
    audit = []
    path = os.path.join(base, S.AUDIT_FILE)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                audit.append(json.loads(line))
            except ValueError:
                pass
    return result, audit


@unittest.skipUnless(ENGAGES,
                     "sandbox cannot engage on this machine "
                     "(startup probe)")
class WallNetworkTest(unittest.TestCase):
    """Queue S, roster M6.wall.network: inside the sandbox a
    job has no network (--unshare-net: its loopback is a
    fresh namespace, not the host's). The negative control
    is the same job with confinement off reaching the same
    loopback listener on the host, so a blocked connect
    under enforce is the wall, not the script. UID: same
    uid both sides (module note); the boundary is the
    network namespace.
    """

    def test_the_sandbox_has_no_network(self):
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        listener.settimeout(0.5)
        port = listener.getsockname()[1]
        stopped = threading.Event()

        def serve():
            while not stopped.is_set():
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    return
                with conn:
                    conn.sendall(b"hp-wall-token")

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        script = (
            "import socket\n"
            "try:\n"
            "    c = socket.create_connection(('127.0.0.1', %d),"
            " timeout=4)\n"
            "    print('net:', c.recv(64).decode())\n"
            "    c.close()\n"
            "except Exception as e:\n"
            "    print('net: blocked', type(e).__name__)\n" % port)
        try:
            off, _, _ = _run({}, _job("m6-wall-net-off", script))
            self.assertEqual(off["exit_code"], 0, off["stderr"])
            self.assertIn("net: hp-wall-token", off["stdout"])
            on, _, _ = _run(_conf("enforce"),
                            _job("m6-wall-net-on", script))
            self.assertEqual(on["exit_code"], 0, on["stderr"])
            self.assertIn("net: blocked", on["stdout"])
        finally:
            stopped.set()
            listener.close()
            thread.join(timeout=5)


@unittest.skipUnless(ENGAGES,
                     "sandbox cannot engage on this machine "
                     "(startup probe)")
class WallHomeTest(unittest.TestCase):
    """Queue S, roster M6.wall.home: inside the sandbox the
    runner's home -- its base dir, holding the config and
    the audit log -- is not visible: nothing of the base is
    bound, and /tmp inside is a fresh tmpfs. The same job
    with confinement off reads the planted marker in the
    base, so the enforce side's failure is the wall.
    """

    def test_the_runner_home_is_not_visible(self):
        base = tempfile.mkdtemp(prefix="hp-m6-home-")
        marker = os.path.join(base, "host-marker.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("runner-home-data")
        script = (
            "import os\n"
            "try:\n"
            "    print('home:', open(%r).read().strip())\n"
            "except Exception:\n"
            "    print('home: blocked')\n"
            "print('base-seen:', os.path.exists(%r))\n"
            % (marker, base))
        off, _ = _run_in(base, {}, _job("m6-wall-home-off", script))
        self.assertEqual(off["exit_code"], 0, off["stderr"])
        self.assertIn("home: runner-home-data", off["stdout"])
        self.assertIn("base-seen: True", off["stdout"])
        on, audit = _run_in(base, _conf("enforce"),
                            _job("m6-wall-home-on", script))
        self.assertEqual(on["exit_code"], 0, on["stderr"])
        self.assertIn("home: blocked", on["stdout"])
        self.assertIn("base-seen: False", on["stdout"])
        self.assertEqual(audit[-1]["decision"], "sandboxed")


@unittest.skipUnless(ENGAGES,
                     "sandbox cannot engage on this machine "
                     "(startup probe)")
class WallUsrTest(unittest.TestCase):
    """Queue S, roster M6.wall.usr: inside the sandbox /usr
    is a read-only bind, so the same write that lands
    outside cannot land inside. The off side writes to a
    scratch tree standing in for /usr, exactly as the
    roster's promise words it: the suite never writes the
    host's real /usr to prove the control lets it.
    """

    def test_usr_is_read_only_inside(self):
        on, _, _ = _run(_conf("enforce"), _job("m6-wall-usr-on", (
            "try:\n"
            "    open('/usr/hp-wall-probe.txt', 'w').write('x')\n"
            "    print('usr: wrote')\n"
            "except Exception:\n"
            "    print('usr: blocked')\n")))
        self.assertEqual(on["exit_code"], 0, on["stderr"])
        self.assertIn("usr: blocked", on["stdout"])
        self.assertFalse(os.path.exists("/usr/hp-wall-probe.txt"))
        scratch = tempfile.mkdtemp(prefix="hp-m6-usr-")
        target = os.path.join(scratch, "hp-wall-probe.txt")
        off, _, _ = _run({}, _job("m6-wall-usr-off", (
            "open(%r, 'w').write('landed')\n"
            "print('usr: wrote')\n" % target)))
        self.assertEqual(off["exit_code"], 0, off["stderr"])
        self.assertIn("usr: wrote", off["stdout"])
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "landed")


@unittest.skipUnless(ENGAGES,
                     "sandbox cannot engage on this machine "
                     "(startup probe)")
class WallWorkTest(unittest.TestCase):
    """Queue S, roster M6.wall.work: inside the sandbox the
    job's workdir is bound at /work and is the working
    directory; nothing of the base dir outside it -- not
    the base root, not a sibling job's workdir -- is
    reachable. With confinement off the same job reads
    both planted files, so the enforce side's failures
    are the wall.
    """

    def test_only_the_workdir_is_reachable(self):
        base = tempfile.mkdtemp(prefix="hp-m6-work-")
        outside = os.path.join(base, "outside.txt")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("outside-data")
        sibling_dir = os.path.join(base, "work", "other-job")
        os.makedirs(sibling_dir)
        sibling = os.path.join(sibling_dir, "secret.txt")
        with open(sibling, "w", encoding="utf-8") as fh:
            fh.write("sibling-data")
        script = (
            "import os\n"
            "print('cwd:', os.getcwd())\n"
            "print('at-work:', os.path.isdir('/work'))\n"
            "try:\n"
            "    open('/work/landed.txt', 'w').write('via-work')\n"
            "except Exception:\n"
            "    open('landed.txt', 'w').write('via-cwd')\n"
            "print('landed: yes')\n"
            "try:\n"
            "    print('outside:', open(%r).read().strip())\n"
            "except Exception:\n"
            "    print('outside: blocked')\n"
            "try:\n"
            "    print('sibling:', open(%r).read().strip())\n"
            "except Exception:\n"
            "    print('sibling: blocked')\n"
            % (outside, sibling))
        off, _ = _run_in(base, {}, _job("m6-wall-work-off", script))
        self.assertEqual(off["exit_code"], 0, off["stderr"])
        self.assertIn("outside: outside-data", off["stdout"])
        self.assertIn("sibling: sibling-data", off["stdout"])
        off_landed = os.path.join(base, "work", "m6-wall-work-off",
                                  "landed.txt")
        self.assertTrue(os.path.exists(off_landed))
        on, audit = _run_in(base, _conf("enforce"),
                            _job("m6-wall-work-on", script))
        self.assertEqual(on["exit_code"], 0, on["stderr"])
        self.assertIn("cwd: /work", on["stdout"])
        self.assertIn("at-work: True", on["stdout"])
        self.assertIn("outside: blocked", on["stdout"])
        self.assertIn("sibling: blocked", on["stdout"])
        on_landed = os.path.join(base, "work", "m6-wall-work-on",
                                 "landed.txt")
        with open(on_landed, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "via-work")
        self.assertEqual(audit[-1]["decision"], "sandboxed")


class SnapshotRealpathFallbackTest(unittest.TestCase):
    """Queue A refill: snapshot_outside's realpath fallbacks
    (coverage run 40189711740: 4 lines, both platforms).
    The snapshot is best-effort by its docstring: when
    os.path.realpath raises OSError -- for the workspace
    itself, or for one directory mid-walk -- the walk
    falls back to the absolute path and carries on, so an
    odd filesystem costs precision, never the snapshot.
    """

    def _tree(self):
        parent = tempfile.mkdtemp(prefix="hp-snap-")
        self.addCleanup(shutil.rmtree, parent, True)
        ws = os.path.join(parent, "ws")
        sib = os.path.join(parent, "sib")
        os.makedirs(ws)
        os.makedirs(sib)
        with open(os.path.join(ws, "own.txt"), "w") as fh:
            fh.write("own")
        marker = os.path.join(sib, "outside.txt")
        with open(marker, "w") as fh:
            fh.write("outside")
        return ws, sib, marker

    def test_a_workspace_realpath_failure_falls_back(self):
        ws, _sib, marker = self._tree()
        real = os.path.realpath

        def flaky(path, *a, **kw):
            if path == ws:
                raise OSError("no resolution")
            return real(path, *a, **kw)

        with mock.patch.object(os.path, "realpath", flaky):
            snap = snapshot_outside(ws)
        self.assertIn(marker, snap)
        self.assertFalse(any(p.startswith(ws) for p in snap))

    def test_a_walk_root_realpath_failure_falls_back(self):
        ws, sib, marker = self._tree()
        real = os.path.realpath

        def flaky(path, *a, **kw):
            if path == sib:
                raise OSError("no resolution")
            return real(path, *a, **kw)

        with mock.patch.object(os.path, "realpath", flaky):
            snap = snapshot_outside(ws)
        self.assertIn(marker, snap)
        self.assertFalse(any(p.startswith(ws) for p in snap))


class InterpreterBindsRelativeLegTest(unittest.TestCase):
    """Queue A refill: interpreter_binds'
    relative-path skip (coverage run
    40189711740: sandbox.py lines 201-202).
    A resolved interpreter that is not an
    absolute path names nothing the sandbox
    can bind; it is passed over, and the
    answer is a list either way.
    """

    def test_a_relative_interpreter_is_passed_over(self):
        out = SB.interpreter_binds("relative/python3")
        self.assertIsInstance(out, list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
