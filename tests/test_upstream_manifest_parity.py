# agent-ident: 200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d
"""Keep the two upstream-source manifests from drifting apart.

An extension can carry both descriptions of the same upstream:
  * upstream.json  -- the committed provenance bundle + size cap
                      (tools/vendor_upstreams.py), and
  * sources.json   -- the runtime fetch-and-verify lock
                      (tools/pin_extension_sources.py / extsources).
They deliberately track different things (a branch commit vs a
latest release tag), so their commits are NOT expected to match. But
when both name the same upstream they must agree on the facts that
are not a matter of tracking: the repository and the license. A
repo repointed or a license relabelled in one file but not the other
is the drift this catches -- the mismatch that would otherwise ship
two contradictory claims about the same dependency.
"""

import glob
import json
import os
import re
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm_repo(repo):
    repo = (repo or "").strip().rstrip("/")
    repo = re.sub(r"^https?://github\.com/", "", repo)
    return repo.lower()


def _sources_by_repo(sources_path):
    with open(sources_path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    for s in data.get("sources", []):
        key = _norm_repo(s.get("github", ""))
        if key:
            out[key] = s
    return out


class ManifestParityTest(unittest.TestCase):
    def test_twin_manifests_agree_on_repo_and_license(self):
        checked = 0
        for up_path in sorted(glob.glob(
                os.path.join(_ROOT, "examples", "extensions",
                             "*", "upstream.json"))):
            ext_dir = os.path.dirname(up_path)
            src_path = os.path.join(ext_dir, "sources.json")
            if not os.path.isfile(src_path):
                continue  # only the overlap is constrained
            with open(up_path, encoding="utf-8") as fh:
                up = json.load(fh)
            by_repo = _sources_by_repo(src_path)
            ext = os.path.basename(ext_dir)
            for u in up["upstreams"]:
                repo = _norm_repo(u["repo"])
                self.assertIn(
                    repo, by_repo,
                    "%s: upstream.json names %s but sources.json has no "
                    "source for it" % (ext, repo))
                self.assertEqual(
                    u.get("license"), by_repo[repo].get("license"),
                    "%s: license drift for %s (upstream.json=%r, "
                    "sources.json=%r)" % (ext, repo, u.get("license"),
                                          by_repo[repo].get("license")))
                checked += 1
        self.assertGreater(checked, 0, "no twin manifests found to check")


if __name__ == "__main__":
    unittest.main()
