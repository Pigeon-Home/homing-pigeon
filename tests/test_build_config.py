"""The frozen builds must actually contain what runner.py loads.

runner.py loads its sibling modules dynamically (``_load_mod`` /
``_load_attr`` with ``importlib.import_module``) so the same file runs
as a package member and as ``__main__`` from inside runner/. Dynamic
imports are invisible to PyInstaller's static analysis: without a
``--hidden-import`` per module, the one-file executables silently ship
without them -- _version most visibly, which made the Windows exe print
"unknown" for --version (CI run 39076097325); the other modules would
have degraded silently. This test keeps build.yml's hidden imports in
sync with every dynamic load in runner.py, and checks that the Linux
and macOS jobs smoke the built binaries' --version like Windows does.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _dynamic_runner_modules():
    with open(os.path.join(_root(), "runner", "runner.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(
        r'_load_(?:mod|attr)\(\s*"runner\.([A-Za-z0-9_]+)"', src))


def _workflow():
    with open(os.path.join(_root(), ".github", "workflows", "build.yml"),
              encoding="utf-8") as fh:
        return fh.read()


def _job_block(workflow, job):
    m = re.search(r"^  %s:\n(.*?)(?=^  [a-z-]+:|\Z)" % re.escape(job),
                  workflow, re.M | re.S)
    assert m, "no %s job in build.yml" % job
    return m.group(1)


class HiddenImportSyncTest(unittest.TestCase):
    def test_scan_finds_the_dynamic_loads(self):
        # Self-check: if the scan ever matches nothing, the sync test
        # below would pass vacuously. The loader set is in double
        # digits by design (one face per sibling module).
        self.assertGreaterEqual(len(_dynamic_runner_modules()), 10)

    def test_every_dynamic_load_is_a_hidden_import(self):
        workflow = _workflow()
        build_lines = [ln for ln in workflow.splitlines()
                       if "pyinstaller" in ln and "runner/runner.py" in ln]
        self.assertEqual(len(build_lines), 3,
                         "expected one runner build line per OS job")
        for line in build_lines:
            for mod in sorted(_dynamic_runner_modules()):
                self.assertIn("--hidden-import runner.%s" % mod, line,
                              "build line misses hidden import for %s" % mod)


class UnixVersionSmokeTest(unittest.TestCase):
    def test_linux_and_macos_smoke_the_built_version(self):
        workflow = _workflow()
        for job in ("build-linux", "build-macos"):
            block = _job_block(workflow, job)
            self.assertIn("./dist/homing-pigeon --version", block,
                          "%s never runs the built binary" % job)
            self.assertIn("./dist/install --version", block,
                          "%s never runs the built installer" % job)


class MutationGateTest(unittest.TestCase):
    """Mutation is release-only (owner's call, 2026-10-17).

    The job takes ~5 minutes and is a signal, not a block, so it is
    gated on the ref: version tags run it, branch pushes and PRs
    skip it. The rule lives in build.yml so nobody has to remember
    to ask for it -- and this test is the proof of work for the
    change that put it there (verified live on run 39101780439:
    mutation skipped on a branch push, everything else green).
    """

    def test_mutation_runs_only_on_version_tags(self):
        block = _job_block(_workflow(), "mutation")
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", block)

    def test_the_gate_jobs_stay_ungated(self):
        # The jobs that gate everything else must run on every push;
        # a stray tag-only condition on one of them would silently
        # stop branch CI from meaning anything.
        workflow = _workflow()
        for job in ("test", "typecheck", "build-linux", "build-macos",
                    "build-windows", "build-python"):
            block = _job_block(workflow, job)
            self.assertNotIn("refs/tags", block,
                             "%s must not be tag-gated" % job)

    def test_mutation_is_a_signal_not_a_block(self):
        # "Signal, not a block" must hold in the run conclusion,
        # not only in the comment: the mirror publishers key off
        # workflow_run.conclusion == 'success', and a failed
        # mutation job without continue-on-error stamps the whole
        # run 'failure' -- which is exactly how v3.7.29 never
        # reached SourceForge or GitLab.
        block = _job_block(_workflow(), "mutation")
        self.assertIn("continue-on-error: true", block)

    def test_real_gates_are_not_continue_on_error(self):
        # The mirror image of the pin above: if a job that gates
        # the release ever grows continue-on-error, a red suite
        # would publish. Only the signal job may carry it.
        workflow = _workflow()
        for job in ("test", "typecheck", "build-linux", "build-macos",
                    "build-windows", "build-python", "release",
                    "pypi-publish"):
            block = _job_block(workflow, job)
            self.assertNotIn("continue-on-error", block,
                             "%s must stay a real gate" % job)


def _also_copy():
    with open(os.path.join(_root(), "pyproject.toml"),
              encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"^also_copy = \[(.*?)\]", src, re.M | re.S)
    assert m, "no also_copy list in pyproject.toml [tool.mutmut]"
    # Strip TOML comments before harvesting the quoted entries: the
    # block's own comments quote a filename ("INSTALL.md not found"
    # is prose about the v3.7.29 failure, not an entry).
    body = []
    for line in m.group(1).splitlines():
        out, in_str = [], False
        for ch in line:
            if ch == '"':
                in_str = not in_str
            if ch == "#" and not in_str:
                break
            out.append(ch)
        body.append("".join(out))
    return set(re.findall(r'"([^"]+)"', "\n".join(body)))


class MutationTreeTest(unittest.TestCase):
    """mutmut runs the suite in a copied tree, not the checkout.

    Only source_paths, tests, and also_copy make the trip. A test
    that reads repo files the copy does not carry fails mutmut's
    baseline stats collection before a single mutant runs -- which
    is exactly how the v3.7.29 tag build's mutation job died: the
    live-docs guard asserts INSTALL.md and friends are scanned,
    but also_copy carried only docs/ and PROTOCOL.md, so the guard
    (correctly, in the real tree) reported them missing there.
    The doc guards' world and the mutant tree must stay the same
    world; these tests pin that.
    """

    def test_every_root_live_doc_is_copied(self):
        copied = _also_copy()
        root = _root()
        for name in sorted(os.listdir(root)):
            if name.endswith(".md") and name != "CHANGELOG.md":
                self.assertIn(name, copied,
                              "%s is a live root doc the mutant tree "
                              "never sees; add it to also_copy" % name)

    def test_the_doc_guards_expected_docs_are_copied(self):
        copied = _also_copy()
        for expected in ("README.md", "INSTALL.md", "AGENTS.md",
                         "PROTOCOL.md", "RUNBOOK.md"):
            self.assertIn(expected, copied)

    def test_the_sharded_runner_is_copied(self):
        # test_parallel_runner imports this file at load time.
        # A missing copy fails stats collection before any mutant.
        self.assertIn("tools/", _also_copy())

    def test_also_copy_file_entries_exist(self):
        root = _root()
        for entry in _also_copy():
            if not entry.endswith("/"):
                self.assertTrue(
                    os.path.exists(os.path.join(root, entry)),
                    "also_copy names %s, which is not on disk" % entry)


if __name__ == "__main__":
    unittest.main(verbosity=2)
