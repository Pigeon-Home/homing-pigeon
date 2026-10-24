#!/usr/bin/env python3
"""M6 tests: Linux confinement (bwrap sandbox builder)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))
))
sys.path.insert(0, REPO)

from runner import sandbox as SB  # noqa: E402
from runner import security as S  # noqa: E402
from runner.runner import execute_job  # noqa: E402

BWRAP_HERE = SB.sandbox_available()


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
        with mock.patch.object(SB, "sandbox_available", return_value=True), \
             mock.patch.object(SB.shutil, "which", return_value=hosted), \
             mock.patch.object(SB.os.path, "realpath", return_value=hosted), \
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


@unittest.skipUnless(BWRAP_HERE and sys.platform.startswith("linux"),
                     "bwrap not available on this machine")
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

    def test_enforce_result_matches_unsandboxed(self):
        script = "print(6 * 7)"
        r1, _, _ = _run({}, _job("m6-c1", script))
        r2, _, _ = _run(_conf("enforce"), _job("m6-c2", script))
        self.assertEqual(r1["stdout"], r2["stdout"])
        self.assertEqual(r1["exit_code"], r2["exit_code"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
