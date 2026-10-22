"""Nominal function when the runner is dropped into a directory.

The hypothetical is docs/drop-in-hypothetical.md. Stage 2 (a
process that cannot exec) is a refusal. Stages 3 and 4 are one
child process: no home directory, a PATH that holds only this
Python, standard input closed, and a signed job that runs. A bad
signature still produces nothing. Nothing here is an exploit.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import install as I  # noqa: E402


_PROBE = textwrap.dedent(r'''
    import os, sys
    root, drop = sys.argv[1], sys.argv[2]
    sys.path.insert(0, root)
    os.chdir(drop)
    from runner import runner
    from tests import test_oracle_opinion as oo

    def once(payload, secret):
        cfg = {
            "mailbox_user": oo.SENDER,
            "mailbox_password": oo.SECRET,
            "shared_secret": oo.SECRET,
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "max_job_age_sec": 3600,
            "default_timeout_sec": 60,
            "base_dir": drop,
        }
        smtp = oo._FakeSMTP()
        runner.poll_once(
            cfg, drop, {}, os.path.join(drop, "seen.json"),
            imap=oo._FakeIMAP([oo._job_email(payload, secret)]),
            smtp=smtp)
        if not smtp.sent:
            return None
        return oo._read_result(smtp.sent[-1])

    good = oo._exec_payload(interpreter=[sys.executable],
                            script="print('drop-in-ok')")
    result = once(good, oo.SECRET)
    if result is None or result.get("exit_code") != 0:
        sys.stderr.write("good job failed: %r\n" % (result,))
        sys.exit(2)
    if "drop-in-ok" not in (result.get("stdout") or ""):
        sys.stderr.write("marker missing: %r\n" % (result,))
        sys.exit(3)
    bad = oo._exec_payload(interpreter=[sys.executable],
                           script="print('should-not-run')")
    if once(bad, "wrong-" + oo.SECRET2) is not None:
        sys.stderr.write("bad signature produced a result\n")
        sys.exit(4)
    print("DROP-IN-OK")
''')


class DropInTests(unittest.TestCase):
    def test_a_process_that_cannot_exec_is_a_refusal(self):
        # Stage 2 of the hypothetical. An application sandbox and
        # a television are the same answer.
        decision = I.host_decision({
            "platform": "darwin",
            "machine": "arm64",
            "device_model": "",
            "in_container": False,
            "accelerators": [],
            "can_exec": False,
        })
        self.assertEqual(decision["action"], "refuse")
        self.assertEqual(decision["case"], "no-exec")

    def test_nominal_drop_in_with_a_stripped_surrounding(self):
        # Stages 3 and 4. The child is the drop: one directory,
        # this Python, no home, stdin closed.
        drop = tempfile.mkdtemp(prefix="hp-drop-")
        probe = os.path.join(drop, "probe.py")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write(_PROBE)
        missing = os.path.join(drop, "no-such-home")
        env = os.environ.copy()
        env["HOME"] = missing
        env["USERPROFILE"] = missing
        env["PATH"] = os.path.dirname(sys.executable)
        env["PYTHONPATH"] = REPO
        env["PYTHONNOUSERSITE"] = "1"
        env.pop("HP_PLATFORM_PROOF", None)
        proc = subprocess.run(
            [sys.executable, probe, REPO, drop],
            cwd=drop, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DROP-IN-OK", proc.stdout)
        self.assertNotIn("should-not-run", proc.stdout)
        self.assertTrue(os.path.isfile(os.path.join(drop, "seen.json")))
        self.assertFalse(os.path.exists(missing))


if __name__ == "__main__":
    unittest.main()
