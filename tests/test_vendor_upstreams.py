# agent-ident: 200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d
"""Guards for tools/vendor_upstreams.py and the committed bundles.

All offline: every test builds a synthetic extension tree or reads
the real committed one, and never touches the network. The lessons
pinned here are the ones a build must never regress:

  * the committed provenance bundles are internally consistent and
    stay under the 5 MB vendored-footprint cap (the real-tree test);
  * `verify` catches a tampered bundle, a pin bumped without a
    re-vendor, and a size blowout;
  * the manifest schema rejects the malformed shapes that would let
    a bad upstream.json through.
"""

import importlib.util
import json
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_tool():
    path = os.path.join(_ROOT, "tools", "vendor_upstreams.py")
    spec = importlib.util.spec_from_file_location("vendor_upstreams", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vu = _load_tool()

_FAKE_SHA = "a" * 40
_OTHER_SHA = "b" * 40


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if isinstance(data, (dict, list)):
            json.dump(data, fh, indent=2)
            fh.write("\n")
        else:
            fh.write(data)


def _build_tree(root, *, commit=_FAKE_SHA, body="hello\n",
                extra_file=None):
    """Make root/examples/extensions/foo with one consistent bundle.

    The provenance is produced by the tool's own helpers so the test
    can never disagree with the implementation about the hashing.
    """
    ext = os.path.join(root, "examples", "extensions", "foo")
    _write(os.path.join(ext, "upstream.json"), {
        "schema": 1,
        "upstreams": [{
            "name": "up", "repo": "https://example.invalid/up",
            "track": "branch:main", "commit": commit,
            "license": "MIT", "paths": ["A.txt"],
        }],
    })
    bundle = os.path.join(ext, vu.VENDOR_DIRNAME, "up")
    _write(os.path.join(bundle, "A.txt"), body)
    files = [("A.txt", vu._sha256_file(os.path.join(bundle, "A.txt")),
              os.path.getsize(os.path.join(bundle, "A.txt")))]
    if extra_file:
        _write(os.path.join(bundle, extra_file), "extra\n")
    upstream = {"name": "up", "repo": "https://example.invalid/up",
                "track": "branch:main", "commit": commit, "license": "MIT"}
    prov = vu._provenance(upstream, files, "2026-01-01T00:00:00Z")
    _write(os.path.join(bundle, vu.PROVENANCE), prov)
    return root


def _verify(root, max_bytes=vu.DEFAULT_MAX_BYTES):
    return vu.main(["--root", root, "verify", "--max-bytes", str(max_bytes)])


class RealTreeTest(unittest.TestCase):
    """The committed bundles must stay consistent and under budget."""

    def test_committed_bundles_verify_offline(self):
        self.assertEqual(_verify(_ROOT), 0)

    def test_committed_footprint_under_cap(self):
        total = 0
        base = os.path.join(_ROOT, "examples", "extensions")
        for ext in os.listdir(base):
            bundle = os.path.join(base, ext, vu.VENDOR_DIRNAME)
            if os.path.isdir(bundle):
                total += vu._dir_bytes(bundle)
        self.assertLessEqual(total, vu.DEFAULT_MAX_BYTES)

    def test_every_manifest_pins_a_commit(self):
        # A committed upstream.json with an empty commit would mean a
        # bundle nobody can reproduce; refresh must have run.
        base = os.path.join(_ROOT, "examples", "extensions")
        for ext in sorted(os.listdir(base)):
            mpath = os.path.join(base, ext, vu.MANIFEST)
            if not os.path.isfile(mpath):
                continue
            data = vu._load_manifest(mpath)
            for u in data["upstreams"]:
                self.assertTrue(
                    vu._HEX40.match(u.get("commit", "")),
                    "%s/%s is unpinned" % (ext, u["name"]))


class VerifyGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = __import__("tempfile").mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self._tmp)

    def test_clean_tree_passes(self):
        _build_tree(self._tmp)
        self.assertEqual(_verify(self._tmp), 0)

    def test_tampered_file_fails(self):
        _build_tree(self._tmp)
        bad = os.path.join(self._tmp, "examples", "extensions", "foo",
                           vu.VENDOR_DIRNAME, "up", "A.txt")
        with open(bad, "a", encoding="utf-8") as fh:
            fh.write("tampered")
        with self.assertRaises(SystemExit):
            _verify(self._tmp)

    def test_pin_bumped_without_revendor_fails(self):
        # Manifest says one commit; the bundle's provenance says
        # another -- exactly the state after a refresh with no vendor.
        _build_tree(self._tmp)
        mpath = os.path.join(self._tmp, "examples", "extensions", "foo",
                             vu.MANIFEST)
        with open(mpath, encoding="utf-8") as fh:
            data = json.load(fh)
        data["upstreams"][0]["commit"] = _OTHER_SHA
        _write(mpath, data)
        with self.assertRaises(SystemExit):
            _verify(self._tmp)

    def test_size_cap_enforced(self):
        _build_tree(self._tmp, body="x" * 4096)
        self.assertEqual(_verify(self._tmp), 0)  # fine under default cap
        with self.assertRaises(SystemExit):
            _verify(self._tmp, max_bytes=16)

    def test_missing_bundle_fails(self):
        _build_tree(self._tmp)
        import shutil
        shutil.rmtree(os.path.join(self._tmp, "examples", "extensions",
                                   "foo", vu.VENDOR_DIRNAME, "up"))
        with self.assertRaises(SystemExit):
            _verify(self._tmp)


class CompareDigestTest(unittest.TestCase):
    """The drift digest forgives the clock but nothing else."""

    def setUp(self):
        self._tmp = __import__("tempfile").mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self._tmp)

    def test_fetched_at_ignored_commit_not(self):
        base = {"commit": _FAKE_SHA, "tree_sha256": "x", "files": []}
        p1 = os.path.join(self._tmp, vu.PROVENANCE)
        _write(p1, dict(base, fetched_at="2026-01-01T00:00:00Z"))
        d1 = vu._compare_digest(p1)
        _write(p1, dict(base, fetched_at="2099-12-31T23:59:59Z"))
        d2 = vu._compare_digest(p1)
        self.assertEqual(d1, d2, "fetched_at must not affect the digest")
        _write(p1, dict(base, commit=_OTHER_SHA,
                        fetched_at="2026-01-01T00:00:00Z"))
        d3 = vu._compare_digest(p1)
        self.assertNotEqual(d1, d3, "a changed pin must change the digest")


class ManifestSchemaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = __import__("tempfile").mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self._tmp)

    def _load(self, obj):
        p = os.path.join(self._tmp, vu.MANIFEST)
        _write(p, obj)
        return vu._load_manifest(p)

    def test_good_manifest_loads(self):
        data = self._load({"schema": 1, "upstreams": [{
            "name": "up", "repo": "https://x/y", "track": "tag:v1",
            "commit": _FAKE_SHA, "paths": ["LICENSE"]}]})
        self.assertEqual(data["upstreams"][0]["name"], "up")

    def test_rejects(self):
        bad = [
            {"schema": 2, "upstreams": [{}]},                  # wrong schema
            {"schema": 1, "upstreams": []},                    # empty
            {"schema": 1, "upstreams": [{                      # bad repo
                "name": "u", "repo": "http://x", "track": "branch:m",
                "paths": ["L"]}]},
            {"schema": 1, "upstreams": [{                      # bad track
                "name": "u", "repo": "https://x", "track": "latest",
                "paths": ["L"]}]},
            {"schema": 1, "upstreams": [{                      # bad commit
                "name": "u", "repo": "https://x", "track": "branch:m",
                "commit": "nothex", "paths": ["L"]}]},
            {"schema": 1, "upstreams": [{                      # path escape
                "name": "u", "repo": "https://x", "track": "branch:m",
                "paths": ["../etc/passwd"]}]},
            {"schema": 1, "upstreams": [{                      # no paths
                "name": "u", "repo": "https://x", "track": "branch:m",
                "paths": []}]},
        ]
        for obj in bad:
            with self.assertRaises(SystemExit):
                self._load(obj)


if __name__ == "__main__":
    unittest.main()
