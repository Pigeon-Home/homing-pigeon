"""Output files and inline files at their edges (PROTOCOL.md section 6).

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

The reader that brings a job's output file home checks the path,
the file type, the inode it opened against the one it checked, and
the size as it reads. Each refusal is a reason, never an exception
and never bytes from somewhere else. The sender refuses an inline
file it cannot name or read before anything is signed.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.cloud import send_job as SJ  # noqa: E402
from runner.ops import exec as EX  # noqa: E402

SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"


class ReadOutputEdgesTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="hp-out-edges-")
        self.addCleanup(shutil.rmtree, self.work, True)
        self.root = os.path.realpath(self.work)
        with open(os.path.join(self.work, "r.txt"), "wb") as fh:
            fh.write(b"abc")

    def read(self, name, limit=100):
        return EX._read_output(self.work, self.root, name, limit)

    def test_a_path_that_will_not_resolve_is_unreadable(self):
        with mock.patch.object(EX.os.path, "realpath",
                               side_effect=ValueError("embedded null")):
            self.assertEqual(self.read("r.txt"), (None, 0, "unreadable"))

    def test_an_lstat_that_fails_is_unreadable(self):
        # realpath itself calls lstat; pin its answer so only the
        # reader's own lstat fails (on macOS /var is a symlink, and an
        # unresolved path would read as outside the workdir).
        target = os.path.join(self.root, "r.txt")
        with mock.patch.object(EX.os.path, "realpath", return_value=target), \
                mock.patch.object(EX.os, "lstat",
                                  side_effect=PermissionError("denied")):
            self.assertEqual(self.read("r.txt"), (None, 0, "unreadable"))

    def test_an_open_that_fails_is_unreadable(self):
        with mock.patch.object(EX.os, "open", side_effect=OSError("ELOOP")):
            self.assertEqual(self.read("r.txt"), (None, 0, "unreadable"))

    def test_a_file_swapped_after_the_check_is_refused(self):
        other = os.path.join(self.work, "other.txt")
        with open(other, "wb") as fh:
            fh.write(b"secret")
        real_open = os.open

        def swapped(path, flags, *a):
            return real_open(other, flags, *a)
        with mock.patch.object(EX.os, "open", side_effect=swapped):
            self.assertEqual(self.read("r.txt"),
                             (None, 0, "changed while read"))

    def test_a_file_that_grows_past_the_limit_while_read_is_too_large(self):
        reads = iter([b"ab", b"cd", b""])
        with mock.patch.object(EX.os, "read", side_effect=lambda fd, n: next(reads)):
            data, size, why = self.read("r.txt", limit=3)
        self.assertEqual((data, size, why), (None, 4, "too_large"))

    def test_a_workdir_that_will_not_resolve_omits_every_file(self):
        with mock.patch.object(EX.os.path, "realpath",
                               side_effect=OSError("gone")):
            out = EX._collect_outputs(self.work, ["a", "b"], {})
        self.assertEqual(out, [{"name": "a", "omitted": "unreadable"},
                               {"name": "b", "omitted": "unreadable"}])


class InlineFileSenderEdgesTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="hp-inline-edges-")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.script = os.path.join(self.d, "job.sh")
        with open(self.script, "w") as fh:
            fh.write("true\n")

    def new(self, *extra):
        argv = ["send_job.py", "new", "--kind", "exec", "--script-file",
                self.script, "--cleartext", "--secret", SECRET, *extra]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                redirect_stdout(out), redirect_stderr(err):
            rc = SJ.main()
        return rc, out.getvalue(), err.getvalue()

    def test_a_spec_without_a_path(self):
        rc, out, err = self.new("--inline-file", "p.diff")
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("want name=path", err)

    def test_a_name_the_runner_would_refuse(self):
        rc, out, err = self.new("--inline-file", "../p.diff=" + self.script)
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("bad --inline-file name", err)

    def test_a_file_that_cannot_be_read(self):
        rc, out, err = self.new("--inline-file",
                                "p.diff=" + os.path.join(self.d, "nope"))
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("cannot read --inline-file", err)


if __name__ == "__main__":
    unittest.main()
