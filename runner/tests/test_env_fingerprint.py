# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The environment fingerprint every result carries (PROTOCOL 3.2).

When a test passes on one run and fails on the next, the first
question is what changed on the box. `env_fingerprint` answers "same
environment?" in one comparison: `e-` and 24 hex digits, a digest
keyed by the runner's own salt over everything the full platform card
says (each PATH tool by its file, size and mtime), the interpreter
the runner runs under and the runner version. It rides every result
when the owner's `pong_platform` tier is `standard` or `full`, and
never discloses the list behind it: without the salt the few hundred
shapes a box can take cannot be tried back against it.
"""
import os
import re
import shutil
import stat
import tempfile
import unittest
import uuid
from unittest import mock

from runner import runner as R  # noqa: E402
from runner.wire import platformcard as PC  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: no re-collection)

SHAPE = re.compile(r"^e-[0-9a-f]{24}$")


class DigestTest(unittest.TestCase):
    SALT = b"\x01" * 32

    def test_the_shape_and_its_stability(self):
        a = PC.env_fingerprint(self.SALT, {}, [1], "3.14.7")
        self.assertRegex(a, SHAPE)
        self.assertEqual(a, PC.env_fingerprint(self.SALT, {}, [1], "3.14.7"))

    def test_each_input_moves_it(self):
        base = PC.env_fingerprint(self.SALT, {}, [1], "3.14.7")
        self.assertNotEqual(base, PC.env_fingerprint(b"\x02" * 32, {}, [1], "3.14.7"))
        self.assertNotEqual(base, PC.env_fingerprint(self.SALT, {}, [1], "3.14.8"))
        self.assertNotEqual(base, PC.env_fingerprint(self.SALT, {}, [1, 2], "3.14.7"))
        self.assertNotEqual(base, PC.env_fingerprint(
            self.SALT, {"default_interpreter": ["bash"]}, [1], "3.14.7"))
        with mock.patch.object(PC.platform, "release", return_value="0.0-other"):
            self.assertNotEqual(base, PC.env_fingerprint(self.SALT, {}, [1], "3.14.7"))

    def test_a_tool_upgraded_in_place_moves_it(self):
        d = tempfile.mkdtemp(prefix="hp-envfp-")
        self.addCleanup(shutil.rmtree, d, True)
        # Windows finds a tool on PATH by its PATHEXT suffix.
        tool = os.path.join(d, "git.exe" if os.name == "nt" else "git")
        with open(tool, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(tool, stat.S_IRWXU)
        with mock.patch.dict(os.environ, {"PATH": d}):
            before = PC.env_fingerprint(self.SALT, {}, [1], "v")
            with open(tool, "a") as fh:
                fh.write("echo upgraded\n")
            after = PC.env_fingerprint(self.SALT, {}, [1], "v")
            os.remove(tool)
            gone = PC.env_fingerprint(self.SALT, {}, [1], "v")
        self.assertEqual(len({before, after, gone}), 3)

    def test_no_salt_no_fingerprint(self):
        for salt in (None, b"", "text"):
            self.assertIsNone(PC.env_fingerprint(salt, {}, [1], "v"))


class SaltTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-envsalt-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_made_once_private_and_kept(self):
        a = R._env_salt(self.base)
        self.assertEqual(len(a), 32)
        self.assertEqual(R._env_salt(self.base), a)
        path = os.path.join(self.base, R.ENV_SALT_FILE)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_an_unreadable_salt_is_made_again(self):
        path = os.path.join(self.base, R.ENV_SALT_FILE)
        with open(path, "w") as fh:
            fh.write("not hex")
        salt = R._env_salt(self.base)
        self.assertEqual(len(salt), 32)
        with open(path) as fh:
            self.assertEqual(bytes.fromhex(fh.read().strip()), salt)

    def test_a_short_salt_is_made_again(self):
        with open(os.path.join(self.base, R.ENV_SALT_FILE), "w") as fh:
            fh.write("00ff\n")
        self.assertEqual(len(R._env_salt(self.base)), 32)

    def test_no_base_no_salt(self):
        self.assertIsNone(R._env_salt(os.path.join(self.base, "missing")))

    def test_the_tier_gates_it(self):
        for tier, want in (("none", False), ("family", False), (None, False),
                           ("standard", True), ("full", True), ("wide", False)):
            cfg = {} if tier is None else {"pong_platform": tier}
            with self.subTest(tier=tier):
                got = R.env_fingerprint(cfg, self.base)
                self.assertEqual(bool(got), want, got)
                if want:
                    self.assertRegex(got, SHAPE)

    def test_without_the_module_it_is_silent(self):
        with mock.patch.object(R, "_platformcard", None):
            self.assertIsNone(R.env_fingerprint({"pong_platform": "full"}, self.base))


class ResultTest(unittest.TestCase):
    """End to end through the mail path, on every kind of result."""

    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg

    def tearDown(self):
        shutil.rmtree(self.h.tmp, ignore_errors=True)

    def result(self, payload):
        _, smtp, _ = self.h.run_cycle([TR.job_email(payload)])
        return TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)

    def exec_job(self):
        return TR.job_payload(str(uuid.uuid4()), kind="exec", script="echo x",
                              interpreter=["sh"])

    def test_standard_puts_it_on_exec_and_ping_results_alike(self):
        self.cfg["pong_platform"] = "standard"
        ran = self.result(self.exec_job())
        pong = self.result(TR.job_payload(str(uuid.uuid4())))
        self.assertRegex(ran["env_fingerprint"], SHAPE)
        self.assertEqual(ran["env_fingerprint"], pong["env_fingerprint"])
        self.assertNotIn("path_tools", pong["platform"])

    def test_the_view_does_not_strip_it(self):
        self.cfg["pong_platform"] = "full"
        self.cfg["max_result_view"] = "attested"
        ran = self.result(self.exec_job())
        self.assertEqual(ran["view"], "attested")
        self.assertRegex(ran["env_fingerprint"], SHAPE)

    def test_a_rejection_carries_it_too(self):
        self.cfg["pong_platform"] = "standard"
        rej = self.result(TR.job_payload(str(uuid.uuid4()), kind="bogus"))
        self.assertEqual(rej["exit_code"], -2)
        self.assertRegex(rej["env_fingerprint"], SHAPE)

    def test_the_default_tier_sends_none(self):
        self.assertNotIn("env_fingerprint", self.result(self.exec_job()))


if __name__ == "__main__":
    unittest.main()
