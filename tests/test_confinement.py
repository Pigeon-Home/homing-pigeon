#!/usr/bin/env python3
"""M6 tests: Linux confinement (bwrap sandbox builder)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))
)
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
