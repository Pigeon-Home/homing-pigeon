#!/usr/bin/env python3
"""M8 tests: secret files and job_user.

UID (phase 2.3): SecretFilesTest is pre-execution -- it
tests what the runner accepts as its own credential, before
any job exists, so no uid is in play. JobUserTest is the
suite's OTHER-uid corpus: with job_user off (the default) a
job runs as the runner's own uid, recorded below as a design
fact; with job_user enforce (and root, and the pigeon-test
user present) the job runs as that other uid, and the pair
is the negative control for the feature (phase 2.2).
"""
import json
import os
import secrets
import sys
import tempfile
import unittest
from unittest import mock

try:
    import pwd
except ImportError:  # Windows has no pwd
    pwd = None

try:
    import grp
except ImportError:  # Windows has no grp
    grp = None

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard import security as S  # noqa: E402
from runner.runner import (  # noqa: E402
    _JobUserFace, _job_user_preexec, build_secrets, execute_job)

STRONG = secrets.token_hex(32)
STRONG2 = secrets.token_hex(32)

if pwd is None:
    HAS_TEST_USER = False
else:
    try:
        pwd.getpwnam("pigeon-test")
        HAS_TEST_USER = True
    except KeyError:
        HAS_TEST_USER = False
IS_ROOT = os.geteuid() == 0 if hasattr(os, "geteuid") else False
POSIX = os.name != "nt"


def _secret_file(d, name, content):
    path = os.path.join(d, name)
    with open(path, "w") as fh:
        fh.write(content)
    return path


class SecretFilesTest(unittest.TestCase):
    def test_shared_secret_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", STRONG + "\n")
            secrets = build_secrets({"shared_secret_file": p})
        self.assertEqual(secrets[""], STRONG)

    def test_both_inline_and_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", STRONG)
            with self.assertRaises(RuntimeError):
                build_secrets({"shared_secret": STRONG,
                               "shared_secret_file": p})

    def test_missing_file_rejected(self):
        with self.assertRaises(RuntimeError):
            build_secrets(
                {"shared_secret_file": "/nonexistent/secret"})

    def test_empty_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", "  \n")
            with self.assertRaises(RuntimeError):
                build_secrets({"shared_secret_file": p})

    def test_weak_file_secret_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", "password")
            with self.assertRaises(RuntimeError):
                build_secrets({"shared_secret_file": p})

    def test_additional_secrets_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "k1", STRONG2)
            secrets = build_secrets({
                "shared_secret": STRONG,
                "additional_secrets_files": {"k1": p},
            })
        self.assertEqual(secrets["k1"], STRONG2)
        self.assertEqual(secrets[""], STRONG)

    def test_key_both_inline_and_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "k1", STRONG2)
            with self.assertRaises(RuntimeError):
                build_secrets({
                    "shared_secret": STRONG,
                    "additional_secrets": {"k1": STRONG2},
                    "additional_secrets_files": {"k1": p},
                })

    def test_inline_still_works(self):
        secrets = build_secrets({"shared_secret": STRONG})
        self.assertEqual(secrets[""], STRONG)


def _job(jid, script):
    return {"v": 1, "type": "job", "job_id": jid,
            "issued_at": "2026-10-15T12:00:00Z",
            "kind": "exec", "interpreter": ["python3"],
            "script": script}


def _run(cfg_extra, job):
    tmpdir = tempfile.mkdtemp(prefix="hp-m8-")
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
    return result, audit


def _ju(mode, user="pigeon-test"):
    return {"security": {"modes": {"job_user": mode},
                         "job_user": {"user": user}}}


class JobUserTest(unittest.TestCase):
    def test_off_by_default(self):
        result, audit = _run({}, _job("m8-off", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit, [])

    @unittest.skipUnless(POSIX, "uid reporting is POSIX")
    def test_off_runs_as_the_runner_uid(self):
        # Design fact / negative control (phases 2.2/2.3):
        # with job_user off, the job's uid IS the runner's uid
        # -- the same-uid side of the pair whose other side is
        # test_enforce_runs_as_job_user. If this ever failed
        # with the feature off, the enforce test's other-uid
        # result would prove nothing.
        script = chr(10).join(
            ["import os", "print('uid:', os.getuid())", ""])
        result, _audit = _run({}, _job("m8-off-uid", script))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("uid: %d" % os.getuid(), result["stdout"])

    @unittest.skipUnless(POSIX, "job_user audit is POSIX")
    def test_audit_logs_and_runs(self):
        result, audit = _run(
            _ju("audit"), _job("m8-audit", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["feature"], "job_user")
        self.assertEqual(audit[0]["decision"], "would_run_as")
        self.assertEqual(audit[0]["reason"], "would_run_as_user")

    def test_bad_config_rejected(self):
        for bad in ({"user": ""}, {"user": 123}, "pigeon-test"):
            with self.assertRaises(RuntimeError, msg=str(bad)):
                S.validate_security_config(
                    {"security": {"job_user": bad}})
        # Existence is checked with pwd, which Windows does not have.
        if os.name != "nt":
            with self.assertRaises(RuntimeError):
                S.validate_security_config(
                    {"security": {"job_user": {"user": "no-such-user-zzz"}}})

    @unittest.skipUnless(POSIX, "job_user fallback is POSIX")
    def test_non_root_falls_back(self):
        with mock.patch.object(os, "geteuid", return_value=1000):
            result, audit = _run(
                _ju("enforce"), _job("m8-nr", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit[0]["decision"], "fallback")
        self.assertEqual(audit[0]["reason"], "job_user_needs_root")

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_enforce_runs_as_job_user(self):
        script = ("import os, pwd\n"
                  "print('uid:', os.getuid())\n"
                  "print('user:', pwd.getpwuid(os.getuid()).pw_name)\n")
        result, audit = _run(_ju("enforce"), _job("m8-enf", script))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        pw = pwd.getpwnam("pigeon-test")
        self.assertIn("uid: %d" % pw.pw_uid, result["stdout"])
        self.assertIn("user: pigeon-test", result["stdout"])
        self.assertEqual(audit[0]["decision"], "run_as")

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_enforce_result_matches(self):
        script = "print(6 * 7)"
        r1, _ = _run({}, _job("m8-c1", script))
        r2, _ = _run(_ju("enforce"), _job("m8-c2", script))
        self.assertEqual(r1["stdout"], r2["stdout"])
        self.assertEqual(r1["exit_code"], r2["exit_code"])

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_enforce_identity_complete(self):
        # Q12: SECURITY.md promises the job runs AS the
        # configured user. That is the whole identity: real and
        # effective uid and gid, and the supplementary groups --
        # the user's groups, not the runner's.
        script = chr(10).join([
            "import json, os",
            "print(json.dumps({'ruid': os.getuid(),"
            " 'euid': os.geteuid(), 'rgid': os.getgid(),"
            " 'egid': os.getegid(),"
            " 'groups': sorted(os.getgroups())}))",
            "",
        ])
        result, _audit = _run(_ju("enforce"), _job("m8-ident", script))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        ident = json.loads(result["stdout"].strip())
        pw = pwd.getpwnam("pigeon-test")
        self.assertEqual(ident["ruid"], pw.pw_uid)
        self.assertEqual(ident["euid"], pw.pw_uid)
        self.assertEqual(ident["rgid"], pw.pw_gid)
        self.assertEqual(ident["egid"], pw.pw_gid)
        # The user's groups as the OS resolves them (getgrouplist
        # reads Open Directory on Darwin, where grp.getgrall()'s
        # member lists do not). Linux's credential is exactly what
        # the drop set; Darwin's kernel may add the user's own
        # memberships after setuid, never the runner's, so there
        # the proof is "a subset of the user's, and never root's".
        expected = set(os.getgrouplist("pigeon-test", pw.pw_gid)) | {pw.pw_gid}
        got = set(ident["groups"])
        self.assertNotIn(0, got)
        if sys.platform.startswith("linux"):
            self.assertEqual(got, expected)
        else:
            self.assertLessEqual(got, expected)

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_enforce_canary_unreadable_workdir_owned(self):
        # Q12: the credential canary as the other uid. A secret
        # planted in the runner's state dir (owner-only) must be
        # unreadable to the job and the state dir unlistable
        # (SECURITY.md: traverse-only parents), while the job's
        # own workdir is fully usable and owned by the job user.
        canary = "CANARY-Q12-" + secrets.token_hex(8)
        base = tempfile.mkdtemp(prefix="hp-q12-")
        cfg_path = os.path.join(base, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"shared_secret": canary}))
        os.chmod(cfg_path, 0o600)
        script = chr(10).join([
            "import os",
            "base = %r" % base,
            "try:",
            "    open(os.path.join(base, 'config.json')).read()",
            "    print('READ-OK')",
            "except OSError:",
            "    print('READ-DENIED')",
            "try:",
            "    os.listdir(base)",
            "    print('LIST-OK')",
            "except OSError:",
            "    print('LIST-DENIED')",
            "with open('mine.txt', 'w') as fh:",
            "    fh.write('job-owned')",
            "print('WRITE-OK')",
            "",
        ])
        cfg = {"base_dir": base}
        cfg.update(_ju("enforce"))
        result = execute_job(cfg, _job("q12-canary", script), base)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        out = result["stdout"]
        self.assertIn("READ-DENIED", out)
        self.assertIn("LIST-DENIED", out)
        self.assertIn("WRITE-OK", out)
        self.assertNotIn(canary, json.dumps(result))
        pw = pwd.getpwnam("pigeon-test")
        written = None
        for root, _dirs, files in os.walk(base):
            if "mine.txt" in files:
                written = os.path.join(root, "mine.txt")
        self.assertIsNotNone(written)
        self.assertEqual(os.stat(written).st_uid, pw.pw_uid)

    @unittest.skipUnless(IS_ROOT and POSIX,
                         "needs root and the pigeon-test user")
    def test_enforce_user_gone_at_job_time_falls_back(self):
        # Startup refuses a user that does not exist
        # (test_bad_config_rejected); a user deleted after
        # startup reaches the job-time path instead, which
        # audits a fallback and runs as the current user --
        # never silently as the missing user.
        result, audit = _run(
            _ju("enforce", user="pigeon-ghost-zzz"),
            _job("m8-ghost", "import os; print('uid:', os.getuid())"))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("uid: %d" % os.getuid(), result["stdout"])
        self.assertEqual(audit[0]["decision"], "fallback")
        self.assertEqual(audit[0]["reason"], "job_user_unavailable")


class JobUserGroupsProbe(unittest.TestCase):
    """The Q18 finding (docs/seats/questions.md), fixed in _demote and
    pinned here; it failed by design until the fix landed.

    (a) Claim: SECURITY.md, "Running jobs as another user
    (M8)": with job_user enforce "each exec job runs as that
    POSIX user", and Q12's assertion list: the job's
    supplementary groups are the configured user's, not the
    runner's.
    (b) Scenario: the runner runs as root with supplementary
    group 0; inside the demote, os.initgroups fails (the
    failure _demote catches and swallows).
    (c) Observed: the child runs with the right uid and gid
    but keeps the runner's supplementary group 0 -- it is a
    member of the root group while supposedly running as an
    unprivileged user.
    (d) Do not make this pass by editing the test to expect
    the retained group. The fix is in _demote (Claude's lane):
    a failed initgroups must not leave the runner's groups in
    place -- clear them (setgroups to the user's set) or
    refuse the drop.
    """

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_groups_are_the_users_when_initgroups_fails(self):
        import shutil
        import subprocess

        class BadGroups(_JobUserFace):
            def initgroups(self, name, gid):
                raise OSError("simulated initgroups failure")

        os.setgroups([0])
        base = tempfile.mkdtemp(prefix="hp-q18-")
        work = os.path.join(base, "work")
        os.mkdir(work)
        cfg = {"security": {"modes": {"job_user": "enforce"},
                            "job_user": {"user": "pigeon-test"}}}
        fn = _job_user_preexec(cfg, base, "q18", work, face=BadGroups())
        self.assertIsNotNone(fn)
        try:
            proc = subprocess.run(
                [shutil.which("python3") or sys.executable, "-c",
                 "import json, os; print(json.dumps("
                 "{'uid': os.getuid(), 'groups': os.getgroups()}))"],
                preexec_fn=fn, capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            # The drop refused: no job ran under the wrong
            # groups. That satisfies the invariant too.
            return
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ident = json.loads(proc.stdout.strip())
        pw = pwd.getpwnam("pigeon-test")
        self.assertEqual(ident["uid"], pw.pw_uid)
        self.assertNotIn(0, ident["groups"])
        if sys.platform.startswith("linux"):
            self.assertEqual(set(ident["groups"]), {pw.pw_gid})
        else:
            # Darwin may add the user's own memberships after
            # setuid; the invariant is that none of the runner's
            # (root's) groups survive.
            self.assertLessEqual(
                set(ident["groups"]),
                set(os.getgrouplist("pigeon-test", pw.pw_gid)) | {pw.pw_gid})


if __name__ == "__main__":
    unittest.main(verbosity=2)
