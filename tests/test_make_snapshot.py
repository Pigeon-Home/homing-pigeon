#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""tools/make_snapshot.py: the project ships inside every release.

Each test builds a small throwaway git repo, so the tool is proven on
history it can see end to end: the tree export is exact, the bundle
clones back to the same commit, a shallow checkout says so instead of
pretending, and the index links every path it names to the commit.
"""

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "make_snapshot", os.path.join(ROOT, "tools", "make_snapshot.py"))
snap_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snap_mod)

def _has_git():
    try:
        return shutil.which("git") is not None
    except Exception:  # the simulated Windows surface breaks which()
        return False


HAS_GIT = _has_git()

WORKFLOW = """\
name: CI

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions: {}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
  build-linux:
    runs-on: ubuntu-22.04
    needs: test
    steps:
      - run: echo hi
"""

LOG = """\
test_a (tests.test_x.T.test_a) ... ok
test_b (tests.test_x.T.test_b) ... skipped 'bwrap not available'
test_c (tests.test_y.U) ... skipped "no model"

----------------------------------------------------------------------
Ran 3 tests in 0.042s

OK (skipped=2)
"""


def _git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
    return subprocess.run(["git", "-C", repo, *args], check=True,
                          capture_output=True, text=True,
                          env=env).stdout.strip()


@unittest.skipUnless(HAS_GIT, "git not installed")
class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-snap-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, ".github", "workflows"))
        os.makedirs(os.path.join(self.repo, "runner"))
        _git(self.tmp, "init", "-q", "-b", "main", self.repo)
        self._write("pyproject.toml",
                    '[project]\nname = "x"\nversion = "9.8.7"\n')
        self._write("PROTOCOL.md", "# spec\n")
        self._write("runner/runner.py", "print('hi')\n")
        self._write(".github/workflows/build.yml", WORKFLOW)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "one")
        self._write("runner/runner.py", "print('two')\n")
        _git(self.repo, "commit", "-q", "-am", "two")
        _git(self.repo, "tag", "v9.8.7")
        self._write("untracked.txt", "never shipped\n")
        self.sha = _git(self.repo, "rev-parse", "HEAD")
        self.log = os.path.join(self.tmp, "test.log")
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write(LOG)
        self.out = os.path.join(self.tmp, "out")

    def _write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def _make(self, repo=None, env=None):
        return snap_mod.make_snapshot(repo or self.repo, self.out, self.log,
                                      env=env or {})

    def test_the_tree_is_exactly_the_tracked_files(self):
        project, snap = self._make()
        self.assertEqual(snap["files"], 4)
        with open(os.path.join(project, "runner", "runner.py")) as fh:
            self.assertEqual(fh.read(), "print('two')\n")
        self.assertFalse(os.path.exists(os.path.join(project,
                                                     "untracked.txt")))
        self.assertFalse(os.path.exists(os.path.join(project, ".git")))

    def test_the_bundle_clones_back_to_the_same_commit(self):
        project, snap = self._make()
        bundle = os.path.join(project, snap_mod.BUNDLE)
        self.assertTrue(os.path.isfile(bundle))
        clone = os.path.join(self.tmp, "clone")
        _git(self.tmp, "clone", "-q", bundle, clone)
        self.assertEqual(_git(clone, "rev-parse", "HEAD"), self.sha)
        self.assertEqual(_git(clone, "rev-list", "--count", "HEAD"), "2")
        self.assertIn("v9.8.7", _git(clone, "tag"))

    def test_a_shallow_checkout_says_so_instead_of_bundling(self):
        shallow = os.path.join(self.tmp, "shallow")
        # as_uri, not "file://" + path: on Windows that builds
        # file://C:\..., which is not a file URL; git wants file:///C:/...
        _git(self.tmp, "clone", "-q", "--depth", "1",
             pathlib.Path(self.repo).resolve().as_uri(), shallow)
        project, snap = self._make(repo=shallow)
        self.assertIsNone(snap["history"]["bundle"])
        self.assertIn("shallow", snap["history"]["note"])
        self.assertFalse(os.path.exists(os.path.join(project,
                                                     snap_mod.BUNDLE)))
        with open(os.path.join(project, "PROJECT-SNAPSHOT.md")) as fh:
            index = fh.read()
        self.assertNotIn("the full history, and", index)

    def test_ci_facts_name_the_workflows_jobs_and_tests(self):
        project, _ = self._make(env={"GITHUB_RUN_ID": "77",
                                     "GITHUB_RUN_ATTEMPT": "2",
                                     "GITHUB_REF": "refs/tags/v9.8.7"})
        with open(os.path.join(project, "CI-SNAPSHOT.json")) as fh:
            ci = json.load(fh)
        self.assertEqual(ci["version"], "9.8.7")
        self.assertEqual(ci["commit"], self.sha)
        self.assertEqual(ci["run"], "77/2")
        self.assertTrue(ci["run_url"].endswith("/actions/runs/77"))
        (wf,) = ci["workflows"]
        self.assertEqual(wf["file"], ".github/workflows/build.yml")
        self.assertEqual(wf["on"], ["push", "workflow_dispatch"])
        self.assertEqual(wf["jobs"]["build-linux"],
                         {"runs-on": "ubuntu-22.04", "needs": "test"})
        self.assertEqual(ci["tests"]["ran"], 3)
        self.assertEqual(ci["tests"]["result"], "OK")
        self.assertEqual(ci["tests"]["detail"], "skipped=2")
        self.assertEqual(ci["tests"]["skips"], [
            {"test": "tests.test_x.T.test_b",
             "reason": "bwrap not available"},
            {"test": "tests.test_y.U.test_c", "reason": "no model"}])

    def test_the_index_links_every_entry_to_the_commit(self):
        project, _ = self._make()
        with open(os.path.join(project, "PROJECT-SNAPSHOT.md")) as fh:
            index = fh.read()
        self.assertIn("Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854",
                      index)
        for label, path in snap_mod._INDEX:
            self.assertIn("`%s`" % path, index, label)
            kind = "tree" if path.endswith("/") else "blob"
            self.assertIn("/%s/%s/%s" % (kind, self.sha, path.rstrip("/")),
                          index, label)
        self.assertIn("releases/tag/v9.8.7", index)

    def test_a_non_empty_destination_is_refused(self):
        os.makedirs(os.path.join(self.out, "project"))
        with open(os.path.join(self.out, "project", "x"), "w") as fh:
            fh.write("x")
        with self.assertRaises(SystemExit):
            self._make()


@unittest.skipUnless(HAS_GIT, "git not installed")
class InjectTest(unittest.TestCase):
    """The release job adds project/ to finished archives."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-inject-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.project = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.project, "runner"))
        for rel, text in (("PROTOCOL.md", "# spec\n"),
                          ("runner/runner.py", "x = 1\n")):
            with open(os.path.join(self.project, rel), "w") as fh:
                fh.write(text)
        self.stage = os.path.join(self.tmp, "stage", "homing-pigeon-x-1")
        os.makedirs(self.stage)
        self.binary = os.path.join(self.stage, "homing-pigeon")
        with open(self.binary, "wb") as fh:
            fh.write(b"\x7fELF" + bytes(range(256)))
        os.chmod(self.binary, 0o755)

    def test_a_tarball_gains_project_and_keeps_its_binary(self):
        import io
        import tarfile
        payload = b"\x7fELF" + bytes(range(256))
        arc = os.path.join(self.tmp, "homing-pigeon-x-1.tar.gz")
        # The exec bit has to be in the tar header. On Windows,
        # chmod + tar.add never writes it, so the assertion was
        # failing before inject ran and the release job never
        # started. That is what kept 3.12.27 off the mirrors.
        with tarfile.open(arc, "w:gz") as tar:
            info = tarfile.TarInfo("homing-pigeon-x-1/homing-pigeon")
            info.size = len(payload)
            info.mode = 0o755
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(payload))
        self.assertEqual(snap_mod.inject(self.project, arc), 2)
        with tarfile.open(arc) as tar:
            names = tar.getnames()
            binary = tar.getmember("homing-pigeon-x-1/homing-pigeon")
            data = tar.extractfile(binary).read()
        self.assertIn("homing-pigeon-x-1/project/PROTOCOL.md", names)
        self.assertIn("homing-pigeon-x-1/project/runner/runner.py", names)
        self.assertEqual(data, payload)
        self.assertTrue(binary.mode & 0o100, "binary lost its exec bit")
        with self.assertRaises(SystemExit):
            snap_mod.inject(self.project, arc)  # twice is refused

    def test_a_zip_gains_project(self):
        import zipfile
        arc = os.path.join(self.tmp, "homing-pigeon-x-1.zip")
        with zipfile.ZipFile(arc, "w") as zf:
            zf.write(self.binary, "homing-pigeon-x-1/homing-pigeon.exe")
        self.assertEqual(snap_mod.inject(self.project, arc), 2)
        with zipfile.ZipFile(arc) as zf:
            names = zf.namelist()
        self.assertIn("homing-pigeon-x-1/homing-pigeon.exe", names)
        self.assertIn("homing-pigeon-x-1/project/runner/runner.py", names)


class WorkflowParseTest(unittest.TestCase):
    def test_the_real_build_workflow_parses(self):
        facts = snap_mod.workflow_facts(
            os.path.join(ROOT, ".github", "workflows", "build.yml"))
        self.assertIn("push", facts["on"])
        self.assertIn("release", facts["jobs"])
        self.assertIn("runs-on", facts["jobs"]["build-linux"])


if __name__ == "__main__":
    unittest.main()


class InstallAndOracleTest(unittest.TestCase):
    """The installer lands project/ in the state dir; the Oracle sees it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-snapinst-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "archive")
        proj = os.path.join(self.src, "project")
        os.makedirs(os.path.join(proj, "runner"))
        with open(os.path.join(proj, "PROJECT-SNAPSHOT.md"), "w") as fh:
            fh.write("# index\n")
        with open(os.path.join(proj, "runner", "runner.py"), "w") as fh:
            fh.write("x = 2\n")
        with open(os.path.join(proj, "CI-SNAPSHOT.json"), "w") as fh:
            json.dump({"version": "9.8.7", "commit": "a" * 40,
                       "tests": {"ran": 4321, "result": "OK",
                                 "skips": [{"test": "t", "reason": "r"}]}},
                      fh)
        self.base = os.path.join(self.tmp, "state")

    def test_install_places_and_replaces_the_snapshot(self):
        from runner import install
        self.assertTrue(install.install_project_snapshot(self.src, self.base))
        dst = os.path.join(self.base, "project")
        stale = os.path.join(dst, "stale.txt")
        with open(stale, "w") as fh:
            fh.write("from the last release")
        self.assertTrue(install.install_project_snapshot(self.src, self.base))
        self.assertFalse(os.path.exists(stale), "upgrade must replace whole")
        with open(os.path.join(dst, "runner", "runner.py")) as fh:
            self.assertEqual(fh.read(), "x = 2\n")
        self.assertEqual(sorted(os.listdir(self.base)), ["project"])

    def test_no_snapshot_in_the_archive_is_not_an_error(self):
        from runner import install
        self.assertFalse(install.install_project_snapshot(
            os.path.join(self.tmp, "nothing"), self.base))
        self.assertFalse(os.path.exists(os.path.join(self.base, "project")))

    def test_the_cfg_base_dir_matches_the_runner(self):
        from runner import install
        from runner.runner import _base_dir_for
        cfg_path = os.path.join(self.tmp, "home", "config.json")
        os.makedirs(os.path.dirname(cfg_path))
        for cfg in ({}, {"base_dir": os.path.join(self.tmp, "elsewhere")}):
            with open(cfg_path, "w") as fh:
                json.dump(cfg, fh)
            self.assertEqual(install._cfg_base_dir(cfg_path),
                             _base_dir_for(cfg, cfg_path))

    def test_the_oracle_context_points_at_the_snapshot(self):
        from runner import install
        from runner.runner import _project_snapshot_note, oracle_context
        self.assertEqual(_project_snapshot_note(self.base), "")
        install.install_project_snapshot(self.src, self.base)
        note = _project_snapshot_note(self.base)
        self.assertIn("9.8.7", note)
        self.assertIn("project/PROJECT-SNAPSHOT.md", note)
        self.assertIn("project/CI-SNAPSHOT.json", note)
        self.assertIn("4321 tests, OK, 1 skipped", note)
        ctx = oracle_context(self.base, watch=False)
        self.assertIn("Project snapshot:", ctx)

    def test_a_broken_ci_file_still_points_at_the_index(self):
        from runner import install
        from runner.runner import _project_snapshot_note
        install.install_project_snapshot(self.src, self.base)
        with open(os.path.join(self.base, "project", "CI-SNAPSHOT.json"),
                  "w") as fh:
            fh.write("{not json")
        note = _project_snapshot_note(self.base)
        self.assertIn("project/PROJECT-SNAPSHOT.md", note)
        self.assertIn("unknown", note)
