"""Phase 2.1: the credential canary (the phase-2 order, 2026-10-24).

One unique fake credential is planted everywhere a real one
lives -- a file under a fake home, an environment variable, a
config key, shell history -- and after every job every sink is
swept for it: each result view, the runner log, the oracle log,
the outbox (the serialized result the transports carry), and
the workspace tree. The runner must never copy a credential
into its own outputs.

UID: SAME-UID corpus (phase 2.3). Jobs run as the same uid as
the runner, so a job that goes looking can read the planted
file and its own environment; that is a design fact of the
same-uid posture, recorded as such in
TestCanaryDesignFactsSameUid, not a failure. What this corpus
fails on is the RUNNER leaking the canary on its own: into a
view the job did not produce, a log line, or a file in the
workspace the job did not write.

Negative controls (phase 2.2) live here too: the sweep itself
is proven non-vacuous against a deliberately planted leak, and
the redacted view is proven by a pair -- the same job output
must carry the canary in the full view and must not carry it
in the redacted view, so neither side can pass vacuously.

Environment axis (phase 2.4): the apparmor userns setting in
force is printed with the run so the setting is recorded next
to the results.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner import runner as R  # noqa: E402

CANARY = "CANARY-CREDENTIAL-p2-9e41f7-DO-NOT-LEAK"


def _axis_value():
    return _sysctl_value(
        "/proc/sys/kernel/apparmor_restrict_unprivileged_userns")


def _sysctl_value(path):
    try:
        with open(path, encoding="ascii") as fh:
            return fh.read().strip()
    except OSError:
        return "absent"


def _hidepid_value():
    """The hidepid option on /proc, as the mount table spells it.

    "0" when the proc entry carries no hidepid option (the
    kernel default), "absent" when the mount table cannot be
    read. Newer kernels spell 2 as "invisible"; the value is
    recorded as read, never normalized.
    """
    try:
        with open("/proc/mounts", encoding="ascii") as fh:
            for line in fh:
                fields = line.split()
                if len(fields) >= 4 and fields[1] == "/proc":
                    for opt in fields[3].split(","):
                        if opt.startswith("hidepid="):
                            return opt.split("=", 1)[1]
                    return "0"
    except OSError:
        pass
    return "absent"


def setUpModule():
    print("AXIS apparmor_restrict_unprivileged_userns=%s"
          % _axis_value())
    # The queue-B axes (Q20): recorded by the module itself, so
    # any run of the canary -- the env-axes sysctl legs included
    # -- carries every axis value beside its results, not only
    # in the workflow's own log line.
    print("AXIS kernel.yama.ptrace_scope=%s" % _sysctl_value(
        "/proc/sys/kernel/yama/ptrace_scope"))
    print("AXIS fs.protected_symlinks=%s" % _sysctl_value(
        "/proc/sys/fs/protected_symlinks"))
    print("AXIS fs.protected_regular=%s" % _sysctl_value(
        "/proc/sys/fs/protected_regular"))
    print("AXIS hidepid=%s" % _hidepid_value())


def _job(jid, script, **kw):
    job = {"v": 1, "type": "job", "job_id": jid,
           "issued_at": "2026-10-24T12:00:00Z",
           "kind": "exec", "interpreter": ["python3"],
           "script": script}
    job.update(kw)
    return job


def _sweep(sinks):
    """Return the names of sinks whose text contains the canary."""
    return sorted(name for name, text in sinks.items()
                  if text and CANARY in text)


class _CanaryBase(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.mkdtemp(prefix="hp-canary-")
        self.home = os.path.join(self.sandbox, "fake-home")
        os.makedirs(os.path.join(self.home, ".config"))
        # Planted: a credential file under the fake home.
        self.cred_file = os.path.join(
            self.home, ".config", "pretend-credential.txt")
        with open(self.cred_file, "w", encoding="utf-8") as fh:
            fh.write("pretend credential: %s\n" % CANARY)
        # Planted: shell history.
        with open(os.path.join(self.home, ".bash_history"),
                  "w", encoding="utf-8") as fh:
            fh.write("export TOKEN=%s\n" % CANARY)
        # Planted: a config key in a runner-style config file.
        with open(os.path.join(self.home, "config.json"),
                  "w", encoding="utf-8") as fh:
            json.dump({"mailbox_password": CANARY}, fh)
        # Planted: an environment variable for the job processes.
        self._env = mock.patch.dict(os.environ, {
            "HOME": self.home, "HP_CANARY_CREDENTIAL": CANARY})
        self._env.start()
        self.addCleanup(self._env.stop)
        # Planted: config keys on the runner config itself.
        self.base = os.path.join(self.sandbox, "base")
        os.makedirs(self.base)
        self.cfg = {"base_dir": self.base,
                    "mailbox_password": CANARY,
                    "canary_config_key": CANARY}
        # The runner log file sink lives in the base dir.
        self._old_log_file = R._LOG_FILE
        R._LOG_FILE = os.path.join(self.base, "runner.log")
        self.addCleanup(setattr, R, "_LOG_FILE", self._old_log_file)

    def _run_and_collect(self, job):
        """Run one job; return (exec_result, sinks) with every
        sink's text as it stands right after the job."""
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            result = R.execute_job(self.cfg, job, self.base)
        sinks = {"job stdout (redirected log)": out.getvalue(),
                 "result dict": json.dumps(result, default=str)}
        patterns = R._redact_patterns(self.cfg)
        for view in ("full", "redacted", "summary", "attested"):
            rendered, _retain = R.apply_result_policy(
                self.cfg,
                dict(job, result_policy={"view": view}),
                result, patterns, confined=False)
            sinks["view:" + view] = json.dumps(rendered,
                                               default=str)
        # The outbox sink is the serialized result: the file
        # transport writes exactly this JSON (signed) to its
        # outbox, so a canary absent here cannot ride the outbox.
        sinks["outbox (serialized result)"] = sinks["result dict"]
        for name, path in (
                ("runner log file",
                 os.path.join(self.base, "runner.log")),
                ("oracle log",
                 os.path.join(self.base, "oracle.log"))):
            if os.path.isfile(path):
                with open(path, encoding="utf-8",
                          errors="replace") as fh:
                    sinks[name] = fh.read()
        # The workspace sink: every file under the base dir the
        # job did not itself write in its own work dir is still
        # swept -- a leak into ANY of them is the runner's doing
        # only if the job never named the canary, which the
        # ordinary jobs below never do.
        tree = []
        for root, _dirs, files in os.walk(self.base):
            for fn in files:
                p = os.path.join(root, fn)
                if p == R._LOG_FILE:
                    continue
                with open(p, encoding="utf-8",
                          errors="replace") as fh:
                    tree.append(fh.read())
        sinks["workspace tree"] = "\n".join(tree)
        return result, sinks


class TestCredentialCanarySameUid(_CanaryBase):
    """UID: same-uid. Ordinary jobs that never touch the canary
    must leave every sink clean."""

    def test_planted_homes_really_hold_the_canary(self):
        # Fixture sanity: the plant is real, so a clean sweep
        # below means the runner kept it out, not that the
        # canary was never there.
        with open(self.cred_file, encoding="utf-8") as fh:
            self.assertIn(CANARY, fh.read())
        with open(os.path.join(self.home, ".bash_history"),
                  encoding="utf-8") as fh:
            self.assertIn(CANARY, fh.read())
        with open(os.path.join(self.home, "config.json"),
                  encoding="utf-8") as fh:
            self.assertIn(CANARY, fh.read())
        self.assertEqual(os.environ.get("HP_CANARY_CREDENTIAL"),
                         CANARY)
        self.assertIn(CANARY, json.dumps(self.cfg))

    def test_ordinary_jobs_leak_nothing_into_any_sink(self):
        jobs = [
            _job("canary-echo", "print('hello-canary')"),
            _job("canary-write",
                 "open('note.txt', 'w').write('job data')\n"
                 "print(open('note.txt').read())"),
            _job("canary-list",
                 "import os; print(sorted(os.listdir('.')))"),
        ]
        for job in jobs:
            with self.subTest(job=job["job_id"]):
                result, sinks = self._run_and_collect(job)
                self.assertEqual(result["exit_code"], 0)
                self.assertEqual(
                    _sweep(sinks), [],
                    "canary leaked into sinks (axis "
                    "apparmor_restrict_unprivileged_userns=%s)"
                    % _axis_value())


class TestCanaryNegativeControls(_CanaryBase):
    """Phase 2.2 controls: each protection claim is run once
    with the protection off and must fail there."""

    def test_sweep_detects_a_deliberate_leak(self):
        # Protection off: the canary is written straight into
        # two sinks by hand. The sweep MUST flag exactly those;
        # a sweep that cannot see this sees nothing.
        sinks = {"clean sink": "nothing here",
                 "runner log file": "line with %s in it" % CANARY,
                 "view:full": "{\"stdout\": \"%s\"}" % CANARY}
        self.assertEqual(_sweep(sinks),
                         ["runner log file", "view:full"])

    def test_redacted_view_pair(self):
        # The job prints a bearer-shaped canary. Full view
        # (redaction off) MUST show it -- otherwise the job
        # never emitted it and the redacted assertion is
        # vacuous. Redacted view (protection on) MUST NOT.
        job = _job("canary-bearer",
                   "print('Authorization: Bearer %s')" % CANARY)
        _result, sinks = self._run_and_collect(job)
        self.assertIn(CANARY, sinks["view:full"])
        self.assertNotIn(CANARY, sinks["view:redacted"])
        self.assertIn("[REDACTED:bearer_token]",
                      sinks["view:redacted"])


class TestCanaryDesignFactsSameUid(_CanaryBase):
    """DESIGN FACTS, same-uid (phase 2.3): a job that goes
    looking CAN read the planted credential file and its own
    environment, because job and runner share a uid and no
    confinement is configured. These tests pass by asserting
    the disclosure happens; they record the posture, they are
    not failures and not leaks by the runner."""

    def test_job_can_read_the_planted_file(self):
        job = _job("canary-cat",
                   "print(open(%r).read())" % self.cred_file)
        result, _sinks = self._run_and_collect(job)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn(CANARY, result["stdout"])

    def test_job_can_read_its_own_environment(self):
        job = _job("canary-env",
                   "import os; "
                   "print(os.environ.get('HP_CANARY_CREDENTIAL'))")
        result, _sinks = self._run_and_collect(job)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn(CANARY, result["stdout"])


class AxisRecorderTest(unittest.TestCase):
    """The AXIS lines the module prints at setup: each reader
    answers the value as read, or "absent" when the file is
    not there -- a recorded axis is never a guessed one."""

    def _open_for(self, files):
        real_open = open

        def fake(path, *a, **k):
            if path in files:
                return io.StringIO(files[path])
            if str(path).startswith("/proc/"):
                raise OSError("no such file")
            return real_open(path, *a, **k)

        return fake

    def test_a_sysctl_value_is_read_and_stripped(self):
        with mock.patch("builtins.open", self._open_for(
                {"/proc/sys/kernel/yama/ptrace_scope": "2\n"})):
            self.assertEqual(_sysctl_value(
                "/proc/sys/kernel/yama/ptrace_scope"), "2")

    def test_a_missing_sysctl_reads_absent(self):
        with mock.patch("builtins.open", self._open_for({})):
            self.assertEqual(_sysctl_value(
                "/proc/sys/kernel/yama/ptrace_scope"), "absent")

    def test_hidepid_is_read_from_the_mount_table(self):
        mounts = ("proc /proc proc rw,nosuid,nodev,hidepid=2 0 0\n"
                  "sysfs /sys sysfs rw 0 0\n")
        with mock.patch("builtins.open",
                        self._open_for({"/proc/mounts": mounts})):
            self.assertEqual(_hidepid_value(), "2")

    def test_hidepid_spelled_invisible_is_recorded_as_read(self):
        mounts = "proc /proc proc rw,hidepid=invisible 0 0\n"
        with mock.patch("builtins.open",
                        self._open_for({"/proc/mounts": mounts})):
            self.assertEqual(_hidepid_value(), "invisible")

    def test_no_hidepid_option_reads_as_the_default_0(self):
        mounts = "proc /proc proc rw,nosuid,nodev 0 0\n"
        with mock.patch("builtins.open",
                        self._open_for({"/proc/mounts": mounts})):
            self.assertEqual(_hidepid_value(), "0")

    def test_an_unreadable_mount_table_reads_absent(self):
        with mock.patch("builtins.open", self._open_for({})):
            self.assertEqual(_hidepid_value(), "absent")


if __name__ == "__main__":
    unittest.main()
