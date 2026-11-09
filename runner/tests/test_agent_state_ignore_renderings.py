# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The Subversion and Mercurial renderings agree with the git list.

The shipped .gitignore carries the agent-state patterns (the
pin test, runner/tests/test_gitignore_state_files.py, holds
that list). The same names are rendered for the other two
version-control systems in
docs/steady/security/agent-state-ignores.txt -- an
svn:global-ignores value and an .hgignore glob block -- so an
operator on those systems gets the travelling form of the
protection (agent-state-files.md, section 3: the travel test).

Two renderings of one list will drift unless something holds
them together. These tests are that something: the Subversion
section must carry exactly the git patterns' basenames (an
svn global ignore matches by name, not by path), and the
Mercurial section must carry the git patterns themselves under
its glob header. The one deliberate addition in both is the
.git admin folder: git never tracks its own, so the git list
does not name it, but the other systems' sets must (each system
protects its own admin folder and no other system's).
"""
import os
import unittest

from runner.tests.test_gitignore_state_files import STATE_PATTERNS

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TEMPLATE = os.path.join(REPO, "docs", "steady", "security",
                        "agent-state-ignores.txt")

EXTRA_ADMIN = {".git"}        # in the svn rendering
EXTRA_ADMIN_HG = {".git/"}    # in the hg rendering


def _basename(pattern):
    return pattern.rstrip("/").rsplit("/", 1)[-1]


def _sections():
    with open(TEMPLATE, encoding="utf-8") as fh:
        lines = [line.rstrip("\n") for line in fh]
    svn, hg = [], []
    mode = None
    for line in lines:
        if line.startswith("# Subversion:"):
            mode = "svn"
            continue
        if line.startswith("# Mercurial:"):
            mode = None
            continue
        if line.strip() == "syntax: glob":
            mode = "hg"
            continue
        if mode and line.strip() and not line.startswith("#"):
            (svn if mode == "svn" else hg).append(line.strip())
    return svn, hg


class AgentStateIgnoreRenderingsTest(unittest.TestCase):

    def test_svn_rendering_is_the_git_basenames(self):
        svn, _hg = _sections()
        expected = {_basename(p) for p in STATE_PATTERNS} | EXTRA_ADMIN
        self.assertEqual(expected, set(svn))
        self.assertEqual(len(svn), len(set(svn)), "duplicate svn names")

    def test_hg_rendering_is_the_git_patterns(self):
        _svn, hg = _sections()
        expected = set(STATE_PATTERNS) | EXTRA_ADMIN_HG
        self.assertEqual(expected, set(hg))
        self.assertEqual(len(hg), len(set(hg)), "duplicate hg patterns")

    def test_hg_block_carries_its_glob_header(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            self.assertIn("\nsyntax: glob\n", fh.read())


if __name__ == "__main__":
    unittest.main()
