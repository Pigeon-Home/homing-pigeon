# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Files in the job and files back in the result (PROTOCOL.md section 6).

The loop the README describes is "send the change, read the result".
Two members close it without a new message: a `files[]` entry may
carry its bytes inline (`content_b64`, covered by the job's signature)
instead of a URL, and `outputs` names files under the workdir that
come home in the result, by view: the bytes under `full`, the name,
size and SHA-384 under `redacted` and `summary`, nothing under
`attested`. The sender writes them out with `verify --outputs-dir`,
each checked against its digest.
"""
import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from runner import runner as R  # noqa: E402
from runner.cloud import send_job as SJ  # noqa: E402
from runner.ops import exec as EX  # noqa: E402
from runner.ops import policy as POL  # noqa: E402

PY = [sys.executable]


def b64(data):
    return base64.b64encode(data).decode("ascii")


def _job(script, **extra):
    job = {"v": 1, "type": "job", "job_id": "files-1", "kind": "exec",
           "interpreter": PY, "script": script}
    job.update(extra)
    return job


class InlineFilesTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-files-")

    def run_job(self, job, cfg=None):
        return R.execute_job(cfg or {}, job, self.base)

    def test_inline_bytes_are_staged_exactly(self):
        data = b"\x00\xffpatch\r\nbody\n"
        out = self.run_job(_job(
            "import hashlib;print(hashlib.sha384(open('in/p.diff','rb').read()).hexdigest())",
            files=[{"name": "in/p.diff", "content_b64": b64(data),
                    "sha384": hashlib.sha384(data).hexdigest()}]))
        self.assertEqual(out["exit_code"], 0, out)
        self.assertEqual(out["stdout"].strip(), hashlib.sha384(data).hexdigest())

    def test_an_inline_digest_that_does_not_match_is_refused(self):
        with self.assertRaises(R.JobRejected):
            self.run_job(_job("pass", files=[{
                "name": "a", "content_b64": b64(b"x"), "sha384": "0" * 96}]))

    def test_exactly_one_source(self):
        for f in ({"name": "a"},
                  {"name": "a", "url": "https://x/a", "content_b64": b64(b"x")}):
            with self.subTest(f=f), self.assertRaises(R.JobRejected):
                self.run_job(_job("pass", files=[f]))

    def test_not_strict_base64_is_refused(self):
        for raw in ("eA", "e A==", "eA==\n", "***", 7, "é"):
            with self.subTest(raw=raw), self.assertRaises(R.JobRejected):
                self.run_job(_job("pass", files=[{"name": "a", "content_b64": raw}]))

    def test_a_name_staged_twice_is_refused(self):
        with self.assertRaises(R.JobRejected):
            self.run_job(_job("pass", files=[
                {"name": "a", "content_b64": b64(b"1")},
                {"name": "a", "content_b64": b64(b"2")}]))

    def test_the_name_rules_hold_for_inline_files(self):
        for name in ("../x", "/etc/x", "a/../b", ""):
            with self.subTest(name=name), self.assertRaises(R.JobRejected):
                self.run_job(_job("pass", files=[{"name": name, "content_b64": b64(b"x")}]))

    def test_the_description_names_an_inline_file_without_its_bytes(self):
        text = R._describe_job(_job("pass", files=[
            {"name": "p.diff", "content_b64": b64(b"secret-bytes")}]))
        self.assertIn("inline:p.diff", text)
        self.assertNotIn(b64(b"secret-bytes"), text)


class OutputsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-outputs-")

    def run_job(self, script, outputs, cfg=None):
        return R.execute_job(cfg or {}, _job(script, outputs=outputs), self.base)

    def test_named_files_come_home_with_their_digest(self):
        out = self.run_job(
            "import os;os.makedirs('r',exist_ok=True);"
            "open('r/junit.xml','wb').write(b'<testsuite/>');"
            "open('log.bin','wb').write(bytes(range(256)))",
            ["r/junit.xml", "log.bin"])
        self.assertEqual([o["name"] for o in out["outputs"]], ["r/junit.xml", "log.bin"])
        got = base64.b64decode(out["outputs"][1]["content_b64"])
        self.assertEqual(got, bytes(range(256)))
        self.assertEqual(out["outputs"][1]["sha384"], hashlib.sha384(got).hexdigest())
        self.assertEqual(out["outputs"][1]["size"], 256)

    def test_a_missing_file_is_named_not_raised(self):
        out = self.run_job("pass", ["nope.txt"])
        self.assertEqual(out["outputs"], [{"name": "nope.txt", "omitted": "missing"}])

    @unittest.skipIf(os.name == "nt", "POSIX symlink fixture")
    def test_a_symlink_out_of_the_workdir_is_not_followed(self):
        secret = os.path.join(self.base, "outside.txt")
        with open(secret, "w") as fh:
            fh.write("runner state")
        out = self.run_job(
            "import os;os.symlink(%r,'leak.txt')" % secret, ["leak.txt"])
        self.assertEqual(out["outputs"][0]["omitted"], "outside the workdir")
        self.assertNotIn("content_b64", out["outputs"][0])

    def test_a_directory_is_not_a_file(self):
        out = self.run_job("import os;os.mkdir('d')", ["d"])
        self.assertEqual(out["outputs"][0]["omitted"], "not a regular file")

    def test_one_budget_for_every_file(self):
        out = self.run_job(
            "open('a','wb').write(b'x'*60);open('b','wb').write(b'y'*60)",
            ["a", "b"], cfg={"max_output_file_bytes": 100})
        self.assertIn("content_b64", out["outputs"][0])
        self.assertEqual(out["outputs"][1], {"name": "b", "omitted": "too_large", "size": 60})

    def test_the_outputs_list_is_bounded_and_named_by_the_rules(self):
        for bad in (["a"] * 2, [str(i) for i in range(9)], ["../x"], [7], "a"):
            with self.subTest(bad=bad), self.assertRaises(R.JobRejected):
                self.run_job("pass", bad)


class OutputsByViewTest(unittest.TestCase):
    EXEC = {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False,
            "duration_sec": 0.1,
            "outputs": [{"name": "a", "size": 1, "sha384": "ab" * 48,
                         "content_b64": "eA=="},
                        {"name": "b", "omitted": "missing"}]}

    def view(self, name):
        job = {"job_id": "j", "kind": "exec", "result_policy": {"view": name}}
        result, _retain = POL.apply_result_policy({}, job, dict(self.EXEC), {}, True)
        return result.get("outputs")

    def test_full_carries_the_bytes(self):
        self.assertEqual(self.view("full")[0]["content_b64"], "eA==")

    def test_redacted_and_summary_carry_the_commitment_only(self):
        for name in ("redacted", "summary"):
            with self.subTest(view=name):
                outs = self.view(name)
                self.assertEqual(outs[0], {"name": "a", "size": 1, "sha384": "ab" * 48})
                self.assertEqual(outs[1], {"name": "b", "omitted": "missing"})

    def test_attested_carries_nothing(self):
        self.assertIsNone(self.view("attested"))


class SenderTest(unittest.TestCase):
    SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"

    def test_new_carries_inline_files_and_outputs_in_the_signed_job(self):
        d = tempfile.mkdtemp(prefix="hp-sender-")
        script = os.path.join(d, "job.sh")
        patch = os.path.join(d, "p.diff")
        with open(script, "w") as fh:
            fh.write("true\n")
        with open(patch, "wb") as fh:
            fh.write(b"--- a\n+++ b\n")
        out = io.StringIO()
        argv = ["send_job.py", "new", "--kind", "exec", "--script-file", script,
                "--inline-file", "p.diff=" + patch,
                "--output", "junit.xml", "--cleartext",
                "--secret", self.SECRET]
        with mock.patch.object(sys, "argv", argv), \
                redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = SJ.main()
        self.assertEqual(rc, 0)
        body = out.getvalue()
        self.assertIn(b64(b"--- a\n+++ b\n"), body)
        self.assertIn('"outputs":["junit.xml"]', body.replace(" ", ""))

    def test_verify_writes_outputs_and_refuses_a_bad_digest(self):
        d = tempfile.mkdtemp(prefix="hp-verify-out-")
        good = {"name": "r/junit.xml", "content_b64": b64(b"<x/>"),
                "sha384": hashlib.sha384(b"<x/>").hexdigest(), "size": 4}
        bad = {"name": "b", "content_b64": b64(b"y"), "sha384": "0" * 96}
        payload = {"outputs": [good, bad, {"name": "c", "omitted": "missing"}]}
        with redirect_stderr(io.StringIO()):
            rc = SJ.write_outputs(payload, d)
        self.assertEqual(rc, 1)
        with open(os.path.join(d, "r", "junit.xml"), "rb") as fh:
            self.assertEqual(fh.read(), b"<x/>")
        self.assertFalse(os.path.exists(os.path.join(d, "b")))
        self.assertNotIn("content_b64", payload["outputs"][0])

    def test_verify_keeps_names_inside_the_directory(self):
        d = tempfile.mkdtemp(prefix="hp-verify-name-")
        payload = {"outputs": [{"name": "../escape", "content_b64": b64(b"x"),
                                "sha384": hashlib.sha384(b"x").hexdigest()}]}
        with redirect_stderr(io.StringIO()):
            self.assertEqual(SJ.write_outputs(payload, d), 1)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(d), "escape")))


if __name__ == "__main__":
    unittest.main()
