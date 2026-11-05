# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Paths named in workflow filters and triggers must be real paths.

2 verified defects of the same shape (a docs reorganization moved
files; 2 workflows kept naming the old homes):

- cut-release.yml's "same code as the last release?" step filters
  the release diff through a grep -v -E alternation naming the
  version carriers and the changelog. It named the installer at
  its pre-move home (the runner folder's root) and the changelog
  at the docs root in uppercase, neither of which exists any more;
  the installer lives at runner/ops/install.py and the changelog
  at docs/infrastructure-documents/changelog.md. A release diff
  touching only the real installer and the real changelog
  therefore survived the filter, and the same-code warning could
  never fire.
- job-user.yml's push trigger paths omitted
  runner/ops/remediation_ops.py, where the job_user implementation
  now lives (runner/runner.py only re-exports it), so an edit to
  the implementation alone never triggered the workflow.

These tests extract the path lists from the workflow files
themselves -- the extract-and-exercise pattern of
test_sourceforge_vkey.py -- and pin every named path to the tree,
plus the 2 homes the defects were about.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _workflow(name):
    with open(os.path.join(_root(), ".github", "workflows", name),
              encoding="utf-8") as fh:
        return fh.read()


def _cut_release_filter(workflow_text):
    """(raw regex body, [unescaped path, ...]) of the same-code grep."""
    matches = re.findall(r"grep -v -E '\^\(([^']+)\)\$'", workflow_text)
    assert len(matches) == 1, \
        "expected exactly 1 same-code filter, got %d" % len(matches)
    body = matches[0]
    paths = [re.sub(r"\\(.)", r"\1", part) for part in body.split("|")]
    return body, paths


def _push_paths(workflow_text):
    """The quoted entries of the workflow's push paths: list."""
    lines = workflow_text.splitlines()
    starts = [i for i, ln in enumerate(lines)
              if re.match(r"^\s*paths:\s*$", ln)]
    assert len(starts) == 1, \
        "expected exactly 1 paths: block, got %d" % len(starts)
    start = starts[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    paths = []
    for ln in lines[start + 1:]:
        if ln.strip() and len(ln) - len(ln.lstrip()) <= indent:
            break
        m = re.match(r'^\s*- "([^"]+)"\s*$', ln)
        if m:
            paths.append(m.group(1))
    return paths


class CutReleaseFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body, cls.paths = _cut_release_filter(
            _workflow("cut-release.yml"))

    def test_extraction_finds_the_filter_paths(self):
        # Self-check: a filter that extracts to nothing would make
        # the pins below pass vacuously.
        self.assertGreaterEqual(len(self.paths), 5)

    def test_every_filter_path_exists(self):
        for path in self.paths:
            self.assertTrue(
                os.path.exists(os.path.join(_root(), path)),
                "cut-release.yml filter names a missing path: %s" % path)

    def test_filter_names_the_real_carrier_homes(self):
        # The verified defect: the filter named the pre-move homes,
        # so these 2 real carriers were never filtered out.
        self.assertIn("runner/ops/install.py", self.paths)
        self.assertIn("docs/infrastructure-documents/changelog.md",
                      self.paths)

    def test_a_carriers_only_diff_filters_to_nothing(self):
        # The workflow's own semantics: grep -v drops every line the
        # anchored alternation matches, and an empty remainder is
        # what raises the same-code warning.
        keep = re.compile(r"^(?:%s)$" % self.body)
        changed = ["pyproject.toml", "runner/_version.py",
                   "runner/ops/install.py",
                   "runner/tests/test_install_edges.py",
                   "docs/infrastructure-documents/changelog.md"]
        self.assertEqual([p for p in changed if not keep.match(p)], [])

    def test_a_real_code_diff_survives_the_filter(self):
        keep = re.compile(r"^(?:%s)$" % self.body)
        changed = ["runner/ops/install.py", "runner/runner.py"]
        self.assertEqual([p for p in changed if not keep.match(p)],
                         ["runner/runner.py"])


class JobUserTriggerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = _push_paths(_workflow("job-user.yml"))

    def test_extraction_finds_the_trigger_paths(self):
        self.assertGreaterEqual(len(self.paths), 5)

    def test_every_trigger_path_exists(self):
        for path in self.paths:
            self.assertTrue(
                os.path.exists(os.path.join(_root(), path)),
                "job-user.yml trigger names a missing path: %s" % path)

    def test_trigger_covers_the_job_user_implementation(self):
        # The verified defect: the implementation moved to
        # runner/ops/remediation_ops.py (runner.py re-exports it),
        # and the trigger never followed.
        impl = os.path.join(_root(), "runner", "ops", "remediation_ops.py")
        with open(impl, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("def job_user_startup_problem", src)
        self.assertIn("def _job_user_preexec", src)
        self.assertIn("runner/ops/remediation_ops.py", self.paths)


if __name__ == "__main__":
    unittest.main()
