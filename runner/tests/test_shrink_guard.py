#!/usr/bin/env python3
"""runner/tools/shrink_guard.py: a tracked file cut to a fraction of
itself is named at the commit that did it.

The guard exists because two modules on main were rewritten to a
fraction of their lines on 2026-11-11 (runner/ops/install.py to
309 of 3,824; runner/guard/macos_confine.py to 219 of 798) by
edits that wrote a file's head and dropped the rest, and the
suite found each one leg at a time. Measured over the 500 commits
before the guard landed, it names those three commits (pyproject
was cut the same way between them) and three whole-file removals
that a Shrink-OK: trailer would have passed."""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "shrink_guard", os.path.join(REPO, "runner", "tools", "shrink_guard.py"))
sg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sg)


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True,
                   capture_output=True)


def _write(root, name, lines):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join("line %d\n" % i for i in range(lines)))


class _Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "config", "commit.gpgsign", "false")
        _write(self.root, "big.py", 400)
        _write(self.root, "small.py", 40)
        _write(self.root, "doc/notes.md", 200)
        with open(os.path.join(self.root, "blob.bin"), "wb") as fh:
            fh.write(bytes(range(256)) * 40)
        self.commit("first")

    def commit(self, message):
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", message)

    def run_guard(self, *argv):
        out = io.StringIO()
        env = dict(os.environ)
        env.pop("GITHUB_ACTIONS", None)
        with contextlib.redirect_stdout(out), \
                unittest_patch_env(env):
            rc = sg.main(["--root", self.root, *argv])
        return rc, out.getvalue()


@contextlib.contextmanager
def unittest_patch_env(env):
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


class ShrinkGuardTest(_Repo):
    def test_a_file_cut_to_a_fraction_is_named(self):
        _write(self.root, "big.py", 60)
        self.commit("edit the carrier")
        rc, out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 1)
        self.assertIn("big.py: 400 lines to 60", out)
        self.assertIn("Shrink-OK: big.py", out)

    def test_a_trim_below_the_bound_passes(self):
        _write(self.root, "big.py", 320)          # 80 lines, 20%
        _write(self.root, "small.py", 10)         # 75% but 30 lines
        self.commit("trim")
        rc, out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 0, out)
        self.assertIn("no tracked file lost", out)

    def test_growth_and_new_files_are_never_findings(self):
        _write(self.root, "big.py", 900)
        _write(self.root, "new.py", 5)
        self.commit("grow")
        rc, _out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 0)

    def test_a_whole_file_removal_is_a_finding_unless_said(self):
        os.remove(os.path.join(self.root, "doc/notes.md"))
        self.commit("retire the notes")
        rc, out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 1)
        self.assertIn("doc/notes.md: 200 lines to 0", out)
        _write(self.root, "doc/notes.md", 200)
        self.commit("bring them back")
        os.remove(os.path.join(self.root, "doc/notes.md"))
        self.commit("retire the notes\n\nShrink-OK: doc/notes.md\n")
        rc, out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 0, out)

    def test_the_trailer_takes_a_glob_and_allow_takes_a_path(self):
        _write(self.root, "big.py", 10)
        self.commit("split the module\n\nShrink-OK: *.py\n")
        rc, _out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 0)
        _write(self.root, "big.py", 400)
        self.commit("restore")
        _write(self.root, "big.py", 10)
        self.commit("split again")
        self.assertEqual(self.run_guard("--commit", "HEAD")[0], 1)
        self.assertEqual(
            self.run_guard("--commit", "HEAD", "--allow", "big.py")[0], 0)

    def test_binary_files_are_skipped(self):
        with open(os.path.join(self.root, "blob.bin"), "wb") as fh:
            fh.write(b"\x00\x01")
        self.commit("shrink the blob")
        rc, _out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 0)

    def test_the_working_tree_mode_reads_the_index_and_the_tree(self):
        _write(self.root, "big.py", 20)
        rc, out = self.run_guard("--working-tree")
        self.assertEqual(rc, 1)
        self.assertIn("in the working tree", out)
        _write(self.root, "big.py", 400)
        self.assertEqual(self.run_guard("--working-tree")[0], 0)

    def test_the_first_commit_has_nothing_to_compare(self):
        rc, out = self.run_guard("--commit", "HEAD")
        self.assertEqual(rc, 0)
        self.assertIn("no parent", out)

    def test_an_unknown_revision_is_a_usage_failure(self):
        rc, _out = self.run_guard("--commit", "no-such-rev")
        self.assertEqual(rc, 2)

    def test_under_actions_each_finding_is_an_error_annotation(self):
        _write(self.root, "big.py", 60)
        self.commit("edit the carrier")
        out = io.StringIO()
        env = dict(os.environ, GITHUB_ACTIONS="true")
        with contextlib.redirect_stdout(out), unittest_patch_env(env):
            rc = sg.main(["--root", self.root, "--commit", "HEAD"])
        self.assertEqual(rc, 1)
        self.assertIn("::error file=big.py,title=file cut down::", out.getvalue())

    def test_the_trailer_parser(self):
        self.assertEqual(
            sg.allowed_from_message("x\n\nShrink-OK: a/b.py\nshrink-ok: c*\n"),
            ["a/b.py", "c*"])
        self.assertEqual(sg.allowed_from_message(""), [])


class WorkflowTest(unittest.TestCase):
    def test_the_build_runs_the_guard_with_two_commits(self):
        with open(os.path.join(REPO, ".github", "workflows", "build.yml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        block = text.split("  shape:", 1)[1].split("\n  test:", 1)[0]
        self.assertIn("fetch-depth: 2", block)
        self.assertIn("python3 runner/tools/shrink_guard.py --commit HEAD",
                      block)


if __name__ == "__main__":
    unittest.main()
