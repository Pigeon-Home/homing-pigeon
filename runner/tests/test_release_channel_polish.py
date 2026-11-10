# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Release-channel polish: nothing on the channels reads as pre-release.

Settled 2026-11-09, at the conductor's word: the project is a
full release, and the metadata the distribution channels display
must say so. The PyPI classifier is the channel-facing marker
this file pins -- PyPI renders the Trove Development Status
classifier on the project page and in the JSON API -- together
with the GitHub release step, which must not mark releases as
drafts or prereleases.

The live channels were audited the same day: the GitHub release
v3.15.20.19 is neither draft nor prerelease and is the API's
latest release; GHCR's latest tag resolves to the same digest
as v3.15.20.19; the GitLab releases are published, not upcoming.
Those are live facts, not tree facts, so they are not pinned
here -- what is pinned is everything the tree itself controls.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def _classifiers():
    text = _read("pyproject.toml")
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.9/3.10: no tomllib
        m = re.search(r"classifiers\s*=\s*\[(.*?)\]", text, re.S)
        return re.findall(r'"([^"]+)"', m.group(1))
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)["project"]["classifiers"]


class DevelopmentStatusClassifierTest(unittest.TestCase):
    def test_development_status_is_production_stable(self):
        statuses = [c for c in _classifiers()
                    if c.startswith("Development Status ::")]
        self.assertEqual(
            statuses,
            ["Development Status :: 5 - Production/Stable"])

    def test_no_beta_or_alpha_classifier(self):
        for classifier in _classifiers():
            self.assertNotIn("Beta", classifier)
            self.assertNotIn("Alpha", classifier)


class GithubReleaseStepTest(unittest.TestCase):
    def test_release_step_never_marks_prerelease_or_draft(self):
        build = _read(os.path.join(".github", "workflows", "build.yml"))
        self.assertNotIn("prerelease: true", build)
        self.assertNotIn("draft: true", build)


if __name__ == "__main__":
    unittest.main()
