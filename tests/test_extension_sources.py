#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""Extension sources: each extension brings its own code for the Oracle.

The contract under test (runner/extsources.py, docs/extensions.md
"Sources"):

- sources.json is validated like a manifest: unknown fields refused
  by name, paths that could escape or not exist on every platform
  refused, a newer sources_version refused and an older accepted;
- the first run of an extension fetches what it declares, and a
  second run fetches nothing: work done stays done until the
  declaration (or its pin) changes;
- "latest" means the highest-versioned non-prerelease release, then
  tag, then the default branch;
- a build pin is enforced: bytes whose digest differs are refused and
  nothing is stored;
- archives land as plain files only, inside the target, bounded;
- an offline box records the failure, backs off, and never raises;
- the disclosure rule decides what the Oracle sees: withheld material
  is never listed and the Oracle's file tools refuse it;
- the build's pin tool writes a lock the box accepts.
"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock
from urllib.error import HTTPError, URLError

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extsources as X  # noqa: E402
from runner import runner as R  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "pin_extension_sources",
    os.path.join(REPO, "tools", "pin_extension_sources.py"))
PIN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PIN)
_spec2 = importlib.util.spec_from_file_location(
    "make_snapshot", os.path.join(REPO, "tools", "make_snapshot.py"))
SNAP = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(SNAP)

SHA = "a" * 40
SHA2 = "b" * 40
API = "https://api.github.com/repos/o/up"
RAW = "https://raw.githubusercontent.com/o/up/%s/" % SHA
ASSET = "https://github.com/o/up/releases/download/v1.10.2/up-1.10.2.tar.gz"
RFC = "https://www.rfc-editor.org/rfc/rfc5321.txt"


def _can_symlink():
    probe = tempfile.mkdtemp()
    try:
        os.symlink(probe, os.path.join(probe, "link"))
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


CAN_SYMLINK = _can_symlink()


def tgz(files, top="up-1.10.2", extra=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo("%s/%s" % (top, name) if top else name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))
        for info in extra:
            t.addfile(info, io.BytesIO(b"x" * info.size) if info.size
                      else None)
    return buf.getvalue()


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeOpener:
    """URL -> bytes / JSON-able / exception. Records every request."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.seen = []

    def open(self, req, timeout=None):
        url = req.full_url
        self.seen.append(req)
        if url not in self.routes:
            raise HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
        val = self.routes[url]
        if isinstance(val, BaseException):
            raise val
        if not isinstance(val, bytes):
            val = json.dumps(val).encode()
        return Resp(val)

    def urls(self):
        return [r.full_url for r in self.seen]


def upstream_routes(archive=None, license_text=b"MIT\n"):
    return {
        API + "/releases?per_page=100": [
            {"tag_name": "v2.0.0-rc1", "prerelease": True},
            {"tag_name": "v1.9.0", "assets": []},
            {"tag_name": "v1.10.2", "assets": [
                {"name": "up-1.10.2.tar.gz",
                 "browser_download_url": ASSET},
                {"name": "up-1.10.2.tar.gz.asc",
                 "browser_download_url": ASSET + ".asc"}]},
            {"tag_name": "v3.0.0", "draft": True},
        ],
        API + "/commits/v1.10.2": SHA.encode(),
        RAW + "LICENSE": license_text,
        RAW + "doc/schema.json": b'{"type": "object"}\n',
        ASSET: archive if archive is not None else tgz(
            {"README": b"hello\n", "src/a.c": b"int a;\n"}),
        RFC: b"Simple Mail Transfer Protocol\n",
    }


def upstream_decl(**over):
    entry = {"id": "up", "role": "upstream", "license": "MIT",
             "description": "The project this extension wraps.",
             "github": "o/up", "ref": "latest", "tag_match": "^v",
             "asset_match": "^up-.*\\.tar\\.gz$", "archive": True,
             "files": ["LICENSE", "doc/schema.json"]}
    entry.update(over)
    return {"sources_version": 1, "sources": [
        entry,
        {"id": "rfc5321", "role": "spec", "url": RFC,
         "description": "SMTP."}]}


def write_ext(folder, decl=None, name="feed", kind="sense", files=None):
    os.makedirs(folder, exist_ok=True)
    manifest = {"name": name, "version": "0.1.0", "api_version": 1,
                "kind": kind,
                "description": "A test extension."}
    if kind == "sense":
        manifest["signals"] = [{"name": "s", "description": "A signal."}]
    else:
        manifest["entry"] = ["{python}", "x.py"]
        manifest["publisher"] = "Tests"
    with open(os.path.join(folder, "extension.json"), "w") as fh:
        json.dump(manifest, fh)
    if decl is not None:
        with open(os.path.join(folder, X.SOURCES_FILE), "w") as fh:
            json.dump(decl, fh)
    for rel, data in (files or {"feed.py": b"print('feed')\n"}).items():
        path = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    return folder


def target(folder, name="feed", kind="sense"):
    return {"kind": kind, "name": name, "version": "0.1.0", "dir": folder,
            "description": "A test extension."}


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base = os.path.join(self.tmp, "state")
        os.makedirs(self.base)
        self.ext = os.path.join(self.base, "extensions", "feed")
        self.opener = FakeOpener(upstream_routes())
        self.logs = []
        self.now = 1_800_000_000.0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def policy(self, cfg=None, model=True):
        return X.owner_policy(cfg or {}, model_oracle=model)

    def run_pass(self, targets=None, policy=None, now=None, force=False,
                 opener=None, **kw):
        fetcher = X.Fetcher(opener=opener or self.opener)
        return X.provision(
            self.base, targets if targets is not None else
            [target(self.ext)], policy or self.policy(), fetcher=fetcher,
            now=self.now if now is None else now,
            log=lambda m, level="INFO": self.logs.append((level, m)),
            force=force, **kw)

    def state(self, kind="sense", name="feed"):
        with open(os.path.join(self.base, X.STATE_DIRNAME, kind, name,
                               X.STATE_FILE)) as fh:
            return json.load(fh)

    def index(self):
        with open(os.path.join(self.base, X.STATE_DIRNAME,
                               X.INDEX_FILE)) as fh:
            return fh.read()

    def entry_dir(self, eid, name="feed", kind="sense"):
        return os.path.join(self.base, X.STATE_DIRNAME, kind, name, eid)


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

class DeclarationTest(unittest.TestCase):
    def parse(self, data):
        return X.parse_declaration(data, where="t")

    def entry(self, **kw):
        e = {"id": "x", "role": "upstream", "github": "o/r",
             "archive": True}
        e.update(kw)
        return {"sources_version": 1, "sources": [e]}

    def test_full_declaration_parses_with_defaults(self):
        d = self.parse({"sources_version": 1, "oracle": "withhold",
                        "sources": [
                            {"id": "up", "role": "upstream",
                             "github": "o/up", "files": ["a/b.txt"]},
                            {"id": "doc", "role": "spec",
                             "url": "https://example.org/rfc.txt"},
                            {"id": "code", "role": "self",
                             "project": ["runner/transports.py"]}]})
        self.assertEqual(d["oracle"], "withhold")
        up, doc, code = d["sources"]
        self.assertEqual((up["ref"], up["archive"], up["max_mb"]),
                         ("latest", False, X.DEFAULT_ENTRY_MB))
        self.assertEqual(doc["location"], "url")
        self.assertEqual(code["project"], ["runner/transports.py"])
        self.assertIsNone(up["oracle"])

    def test_unknown_fields_are_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "unknown field.*sorces"):
            self.parse({"sources_version": 1, "sorces": []})
        with self.assertRaisesRegex(ValueError, "unknown field.*branch"):
            self.parse(self.entry(branch="main"))

    def test_newer_version_refused_older_accepted(self):
        with self.assertRaisesRegex(ValueError, "update the agent"):
            self.parse({"sources_version": 2})
        with mock.patch.object(X, "SOURCES_API_VERSION", 2):
            self.assertEqual(self.parse({"sources_version": 1})
                             ["sources_version"], 1)
        for bad in (0, True, "1", None):
            with self.assertRaises(ValueError):
                self.parse({"sources_version": bad})
        with self.assertRaisesRegex(ValueError, "missing"):
            self.parse({"sources": []})

    def test_exactly_one_location(self):
        with self.assertRaisesRegex(ValueError, "exactly one location"):
            self.parse({"sources_version": 1, "sources": [
                {"id": "x", "role": "spec"}]})
        with self.assertRaisesRegex(ValueError, "exactly one location"):
            self.parse(self.entry(url="https://example.org/x"))

    def test_paths_that_escape_or_cannot_exist_are_refused(self):
        for bad in ("../x", "/etc/passwd", "a\\b", "a/../b", "a/./b",
                    "con.txt", "a/NUL", "c:x", "x.", "x ", "", "a//b",
                    "a" * 301):
            with self.assertRaises(ValueError, msg=bad):
                self.parse(self.entry(files=[bad]))
        self.assertEqual(self.parse(self.entry(files=["a/b/"]))
                         ["sources"][0]["files"], ["a/b"])

    def test_ids_are_unique_without_case_and_installed_is_reserved(self):
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            self.parse({"sources_version": 1, "sources": [
                {"id": "Up", "role": "spec", "url": "https://e.org/a"},
                {"id": "up", "role": "spec", "url": "https://e.org/b"}]})
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.parse(self.entry(id="installed"))
        for bad in ("", ".hidden", "a/b", "x" * 65):
            with self.assertRaises(ValueError, msg=bad):
                self.parse(self.entry(id=bad))

    def test_github_rules(self):
        with self.assertRaisesRegex(ValueError, "archive, its files"):
            self.parse(self.entry(archive=False))
        with self.assertRaisesRegex(ValueError, "set archive true"):
            self.parse(self.entry(archive=False, files=["x"],
                                  asset_match="x"))
        with self.assertRaisesRegex(ValueError, 'ref "latest"'):
            self.parse(self.entry(ref="v1", tag_match="^v"))
        with self.assertRaisesRegex(ValueError, "regular expression"):
            self.parse(self.entry(tag_match="("))
        for repo in ("o", "o/r/s", "../r", "o/..", "-o/r"):
            with self.assertRaises(ValueError, msg=repo):
                self.parse(self.entry(github=repo))
        for ref in ("a..b", "x/", "x.lock", "-x", ""):
            with self.assertRaises(ValueError, msg=ref):
                self.parse(self.entry(ref=ref))

    def test_url_and_project_rules(self):
        for url in ("http://e.org/x", "file:///etc/passwd", "https://",
                    "https://e.org/a b"):
            with self.assertRaises(ValueError, msg=url):
                self.parse({"sources_version": 1, "sources": [
                    {"id": "x", "role": "spec", "url": url}]})
        with self.assertRaisesRegex(ValueError, "does not apply to a url"):
            self.parse({"sources_version": 1, "sources": [
                {"id": "x", "role": "spec", "url": "https://e.org/x",
                 "files": ["a"]}]})
        with self.assertRaisesRegex(ValueError, "does not apply to a project"):
            self.parse({"sources_version": 1, "sources": [
                {"id": "x", "role": "self", "project": ["a"],
                 "archive": True}]})

    def test_limits_and_values(self):
        for bad in (0, X.MAX_ENTRY_MB + 1, True, 1.5):
            with self.assertRaises(ValueError, msg=bad):
                self.parse(self.entry(max_mb=bad))
        with self.assertRaises(ValueError):
            self.parse(self.entry(role="malware"))
        with self.assertRaises(ValueError):
            self.parse(self.entry(oracle="maybe"))
        with self.assertRaises(ValueError):
            self.parse({"sources_version": 1, "oracle": "yes"})
        with self.assertRaises(ValueError):
            self.parse({"sources_version": 1, "sources": [
                {"id": "e%d" % i, "role": "spec",
                 "url": "https://e.org/%d" % i}
                for i in range(X.MAX_ENTRIES + 1)]})
        with self.assertRaises(ValueError):
            self.parse(self.entry(description="two\nlines"))

    def test_digest_is_over_the_parsed_form(self):
        tmp = tempfile.mkdtemp()
        try:
            a = os.path.join(tmp, "a")
            b = os.path.join(tmp, "b")
            os.makedirs(a)
            os.makedirs(b)
            decl = upstream_decl()
            with open(os.path.join(a, X.SOURCES_FILE), "w") as fh:
                json.dump(decl, fh)
            with open(os.path.join(b, X.SOURCES_FILE), "w",
                      newline="\r\n") as fh:
                fh.write(json.dumps(decl, indent=4))
            da, pa = X.load_declaration(a)
            db, pb = X.load_declaration(b)
            self.assertIsNone(pa)
            self.assertIsNone(pb)
            self.assertEqual(X.declaration_digest(da),
                             X.declaration_digest(db))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_declaration_outcomes(self):
        tmp = tempfile.mkdtemp()
        try:
            self.assertEqual(X.load_declaration(tmp), (None, None))
            path = os.path.join(tmp, X.SOURCES_FILE)
            with open(path, "w") as fh:
                fh.write("{not json")
            decl, problem = X.load_declaration(tmp)
            self.assertIsNone(decl)
            self.assertIn("not valid JSON", problem)
            with open(path, "w") as fh:
                fh.write(" " * (X.MAX_DECLARATION_BYTES + 1))
            self.assertIn("larger than", X.load_declaration(tmp)[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipUnless(CAN_SYMLINK, "needs symlink")
    def test_symlinked_declaration_is_refused(self):
        tmp = tempfile.mkdtemp()
        try:
            real = os.path.join(tmp, "real.json")
            with open(real, "w") as fh:
                json.dump({"sources_version": 1}, fh)
            os.symlink(real, os.path.join(tmp, X.SOURCES_FILE))
            decl, problem = X.load_declaration(tmp)
            self.assertIsNone(decl)
            self.assertIn("symlink", problem)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ShippedDeclarationsTest(unittest.TestCase):
    """The declarations that ship: the eight upstream adapters and the
    four first-party transports."""

    ADAPTERS = ("aide-feed", "falco-feed", "osquery-feed", "softflowd-feed",
                "suricata-feed", "sysmon-feed", "wazuh-feed", "zeek-feed")
    TRANSPORTS = ("dtls", "email", "file", "nats")

    def folders(self):
        return [os.path.join(REPO, "examples", "extensions", a)
                for a in self.ADAPTERS] + [
            os.path.join(REPO, "runner", "transport_extensions", t)
            for t in self.TRANSPORTS]

    def test_every_shipped_declaration_is_the_expected_set(self):
        found = sorted(os.path.relpath(d, REPO).replace(os.sep, "/")
                       for d in PIN.shipped_dirs(REPO))
        want = sorted(os.path.relpath(d, REPO).replace(os.sep, "/")
                      for d in self.folders())
        self.assertEqual(found, want)

    def test_each_parses_next_to_a_valid_manifest(self):
        from runner import extensions as E
        for folder in self.folders():
            decl, problem = X.load_declaration(folder)
            self.assertIsNone(problem, folder)
            self.assertIsNotNone(decl, folder)
            with open(os.path.join(folder, "extension.json")) as fh:
                E.parse_manifest(json.load(fh))

    def test_adapters_bring_their_upstream_source(self):
        for name in self.ADAPTERS:
            decl, _ = X.load_declaration(
                os.path.join(REPO, "examples", "extensions", name))
            ups = [e for e in decl["sources"] if e["role"] == "upstream"]
            self.assertTrue(ups, name)
            for e in ups:
                self.assertEqual(e["location"], "github", name)
                self.assertEqual(e["ref"], "latest", name)
                self.assertTrue(e["archive"], name)
                self.assertTrue(e["license"], name)

    def test_transports_bring_their_code_and_the_paths_exist(self):
        for name in self.TRANSPORTS:
            decl, _ = X.load_declaration(
                os.path.join(REPO, "runner", "transport_extensions", name))
            code = [e for e in decl["sources"] if e["location"] == "project"]
            self.assertEqual(len(code), 1, name)
            for path in code[0]["project"]:
                self.assertTrue(os.path.exists(
                    os.path.join(REPO, *path.split("/"))), path)

    def test_declarations_stay_tiny(self):
        # The distribution grows by declarations and code only; the
        # sources themselves arrive on the box. The whole feature has
        # 5 MB to spend; the declarations get a few kilobytes of it.
        total = sum(os.path.getsize(os.path.join(f, X.SOURCES_FILE))
                    for f in self.folders())
        self.assertLess(total, 64 * 1024)


# ---------------------------------------------------------------------------
# The owner's policy and the disclosure rule
# ---------------------------------------------------------------------------

class PolicyTest(unittest.TestCase):
    def test_every_box_fetches_by_default_and_auto_follows_the_model(self):
        # The owner's call (2026-10-22): a Pi Light box with no model
        # fetches too. "auto" is the opt-in for model-only fetching.
        self.assertTrue(X.owner_policy({}, model_oracle=True)["enabled"])
        self.assertTrue(X.owner_policy({}, model_oracle=False)["enabled"])
        self.assertTrue(X.owner_policy({"extension_sources": True},
                                       model_oracle=False)["enabled"])
        self.assertTrue(X.owner_policy({"extension_sources": "auto"},
                                       model_oracle=True)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": "auto"},
                                        model_oracle=False)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": {
            "fetch": "auto"}}, model_oracle=False)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": False},
                                        model_oracle=True)["enabled"])
        pol = X.owner_policy({"extension_sources": {"max_mb": 10}})
        self.assertEqual(pol["max_bytes"], 10 << 20)

    def test_malformed_settings_fail_closed(self):
        for bad in ("yes", 1, [], {"fetch": "sometimes"},
                    {"oracle": "share"}, {"max_mb": 0}, {"budget": 1},
                    {"extensions": []}, {"extensions": {"a b": {}}},
                    {"extensions": {"x": {"fetch": "yes"}}},
                    {"extensions": {"x": {"share": True}}}):
            pol = X.owner_policy({"extension_sources": bad})
            self.assertFalse(pol["valid"], bad)
            self.assertFalse(pol["enabled"], bad)
            self.assertIn("extension_sources", pol["problem"])
            self.assertEqual(X.disclosure(pol, "x"), "withhold")
            self.assertFalse(X.fetch_allowed(pol, "x"))

    def test_disclosure_rule_order(self):
        decl_w = {"oracle": "withhold"}
        entry_p = {"oracle": "provide"}
        entry_w = {"oracle": "withhold"}
        pol = X.owner_policy({})
        # 5. default
        self.assertEqual(X.disclosure(pol, "x"), "provide")
        # 4. the author, for the extension
        self.assertEqual(X.disclosure(pol, "x", decl_w), "withhold")
        # 3. the author, for the entry, beats the extension-wide line
        self.assertEqual(X.disclosure(pol, "x", decl_w, entry_p), "provide")
        # 2. the owner's global withhold beats the author
        pol_w = X.owner_policy({"extension_sources": {"oracle": "withhold"}})
        self.assertEqual(X.disclosure(pol_w, "x", None, entry_p), "withhold")
        # ...but the owner's global provide defers to the author
        pol_p = X.owner_policy({"extension_sources": {"oracle": "provide"}})
        self.assertEqual(X.disclosure(pol_p, "x", None, entry_w), "withhold")
        # 1. the owner, for this extension, beats everything
        pol_x = X.owner_policy({"extension_sources": {
            "oracle": "withhold",
            "extensions": {"x": {"oracle": "provide"}}}})
        self.assertEqual(X.disclosure(pol_x, "x", decl_w, entry_w), "provide")
        self.assertEqual(X.disclosure(pol_x, "y"), "withhold")

    def test_fetch_overrides_per_extension(self):
        pol = X.owner_policy({"extension_sources": {
            "fetch": False, "extensions": {"a": {"fetch": True}}}})
        self.assertTrue(X.fetch_allowed(pol, "a"))
        self.assertFalse(X.fetch_allowed(pol, "b"))
        pol = X.owner_policy({"extension_sources": {
            "extensions": {"a": {"fetch": False}}}}, model_oracle=True)
        self.assertFalse(X.fetch_allowed(pol, "a"))
        self.assertTrue(X.fetch_allowed(pol, "b"))


# ---------------------------------------------------------------------------
# Resolving and fetching
# ---------------------------------------------------------------------------

class ResolveTest(unittest.TestCase):
    def fetcher(self, routes):
        self.opener = FakeOpener(routes)
        return X.Fetcher(opener=self.opener)

    def test_version_tuple(self):
        self.assertEqual(X.version_tuple("suricata-8.0.1"), (8, 0, 1))
        self.assertEqual(X.version_tuple("v1.10.2"), (1, 10, 2))
        for tag in ("v2.0.0-rc1", "v4.13.0-alpha1", "nightly-1.2",
                    "v1.0-beta", "1.2-dev", "release", "v8"):
            self.assertIsNone(X.version_tuple(tag), tag)
        self.assertEqual(X.version_tuple("predict-1.0"), (1, 0))

    def test_latest_is_the_highest_released_version(self):
        f = self.fetcher(upstream_routes())
        res = X.resolve_github(f, "o/up", "latest", "^v", "^up-.*\\.tar\\.gz$")
        self.assertEqual((res["tag"], res["commit"], res["version"],
                          res["how"]), ("v1.10.2", SHA, "1.10.2",
                                        "latest-release"))
        self.assertEqual(res["asset"]["url"], ASSET)
        commit_req = [r for r in self.opener.seen
                      if r.full_url.endswith("/commits/v1.10.2")][0]
        self.assertEqual(commit_req.get_header("Accept"),
                         "application/vnd.github.sha")

    def test_tag_match_narrows_the_release_line(self):
        routes = upstream_routes()
        routes[API + "/commits/v1.9.0"] = SHA2.encode()
        f = self.fetcher(routes)
        res = X.resolve_github(f, "o/up", "latest", "^v1\\.9\\.")
        self.assertEqual((res["tag"], res["commit"]), ("v1.9.0", SHA2))

    def test_no_releases_falls_back_to_tags_then_the_branch(self):
        routes = {API + "/releases?per_page=100": [],
                  API + "/tags?per_page=100&page=1": [
                      {"name": "v1.2.0", "commit": {"sha": SHA2}},
                      {"name": "v1.10.0", "commit": {"sha": SHA}},
                      {"name": "v2.0.0-rc2", "commit": {"sha": "c" * 40}}]}
        f = self.fetcher(routes)
        res = X.resolve_github(f, "o/up")
        self.assertEqual((res["tag"], res["commit"], res["how"]),
                         ("v1.10.0", SHA, "latest-tag"))
        routes = {API + "/releases?per_page=100": [],
                  API + "/tags?per_page=100&page=1": [],
                  API: {"default_branch": "main"},
                  API + "/commits/main": SHA.encode()}
        res = X.resolve_github(self.fetcher(routes), "o/up")
        self.assertEqual((res["branch"], res["commit"], res["how"]),
                         ("main", SHA, "default-branch"))

    def test_named_ref_resolves_to_its_commit(self):
        f = self.fetcher({API + "/commits/v0.3.0": SHA.encode()})
        res = X.resolve_github(f, "o/up", "v0.3.0")
        self.assertEqual((res["commit"], res["tag"], res["how"]),
                         (SHA, "v0.3.0", "named"))

    def test_remote_urls(self):
        entry = X.parse_declaration(upstream_decl())["sources"][0]
        files, archive = X.remote_urls(entry, {"commit": SHA,
                                               "asset": {"url": ASSET}})
        self.assertEqual(files["LICENSE"], RAW + "LICENSE")
        self.assertEqual(archive, ASSET)
        files, archive = X.remote_urls(entry, {"commit": SHA})
        self.assertEqual(archive,
                         "https://codeload.github.com/o/up/tar.gz/" + SHA)


class FetcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_https_only_before_any_request(self):
        opener = FakeOpener({})
        f = X.Fetcher(opener=opener)
        for url in ("http://e.org/x", "file:///etc/passwd", "ftp://e.org/x"):
            with self.assertRaises(X.SourceError):
                f.download(url, os.path.join(self.tmp, "x"), 10)
        self.assertEqual(opener.seen, [])

    def test_redirect_off_https_is_refused(self):
        handler = X._HttpsOnlyRedirect()
        req = X.Request("https://e.org/x")
        with self.assertRaisesRegex(X.SourceError, "off https"):
            handler.redirect_request(req, None, 302, "Found", {},
                                     "http://e.org/y")

    def test_token_goes_to_the_github_api_only_and_never_follows(self):
        opener = FakeOpener({"https://api.github.com/x": b"{}",
                             "https://raw.githubusercontent.com/x": b"y"})
        f = X.Fetcher(opener=opener, token="t0ken")
        f.get_json("https://api.github.com/x")
        f.download("https://raw.githubusercontent.com/x",
                   os.path.join(self.tmp, "y"), 10)
        api, raw = opener.seen
        self.assertEqual(api.unredirected_hdrs.get("Authorization"),
                         "Bearer t0ken")
        self.assertNotIn("Authorization", api.headers)
        self.assertIsNone(raw.get_header("Authorization"))

    def test_size_cap_and_error_classes(self):
        opener = FakeOpener({"https://e.org/big": b"x" * 100,
                             "https://e.org/down": URLError("offline")})
        f = X.Fetcher(opener=opener)
        dest = os.path.join(self.tmp, "big")
        with self.assertRaisesRegex(X.SourceError, "larger than") as cm:
            f.download("https://e.org/big", dest, 10)
        self.assertTrue(cm.exception.permanent)
        self.assertFalse(os.path.exists(dest))
        with self.assertRaises(X.SourceError) as cm:
            f.download("https://e.org/missing", dest, 10)
        self.assertTrue(cm.exception.permanent)
        with self.assertRaises(X.SourceError) as cm:
            f.download("https://e.org/down", dest, 10)
        self.assertFalse(cm.exception.permanent)
        sha, n = f.download("https://e.org/big", dest, 100)
        self.assertEqual((sha, n), (hashlib.sha384(b"x" * 100).hexdigest(),
                                    100))


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dest = os.path.join(self.tmp, "out")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, data, name="a.tar.gz"):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def all_files(self):
        out = []
        for dp, _dn, fn in os.walk(self.tmp):
            out += [os.path.relpath(os.path.join(dp, f), self.tmp)
                    .replace(os.sep, "/") for f in fn]
        return sorted(out)

    def test_plain_files_only_inside_the_target(self):
        evil = []
        for name, kind in (("../evil", tarfile.REGTYPE),
                           ("/abs/evil", tarfile.REGTYPE),
                           ("up-1.10.2/link", tarfile.SYMTYPE),
                           ("up-1.10.2/hard", tarfile.LNKTYPE),
                           ("up-1.10.2/dev", tarfile.CHRTYPE),
                           ("up-1.10.2/fifo", tarfile.FIFOTYPE),
                           ("up-1.10.2/con.txt", tarfile.REGTYPE)):
            info = tarfile.TarInfo(name)
            info.type = kind
            if kind == tarfile.REGTYPE:
                info.size = 4
            else:
                info.linkname = "/etc/passwd"
            evil.append(info)
        path = self.write(tgz({"README": b"hi", "src/a.c": b"int a;"},
                              extra=evil))
        stats = X.extract_archive(path, self.dest, 1 << 20)
        self.assertEqual(stats["files"], 2)
        self.assertEqual(stats["skipped"], 7)
        self.assertEqual(self.all_files(), ["a.tar.gz", "out/README",
                                            "out/src/a.c"])

    @unittest.skipIf(os.name == "nt", "Unix mode bits")
    def test_no_mode_bits_survive(self):
        path = self.write(tgz({"run.sh": b"#!/bin/sh\n"}))
        X.extract_archive(path, self.dest, 1 << 20)
        mode = os.stat(os.path.join(self.dest, "run.sh")).st_mode
        self.assertEqual(mode & 0o111, 0)

    def test_caps(self):
        path = self.write(tgz({"big": b"x" * 5000}))
        with self.assertRaisesRegex(X.SourceError, "unpacks past"):
            X.extract_archive(path, self.dest, 1000)
        path = self.write(tgz({"f%d" % i: b"x" for i in range(5)}), "b.tgz")
        with mock.patch.object(X, "MAX_ARCHIVE_MEMBERS", 3):
            with self.assertRaisesRegex(X.SourceError, "more than 3"):
                X.extract_archive(path, os.path.join(self.tmp, "o2"), 1 << 20)

    def test_zip_traversal_and_links_are_skipped(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("top/ok.txt", "fine")
            zf.writestr("../evil.txt", "no")
            link = zipfile.ZipInfo("top/link")
            link.external_attr = (0o120777 << 16)
            zf.writestr(link, "/etc/passwd")
        path = self.write(buf.getvalue(), "a.zip")
        stats = X.extract_archive(path, self.dest, 1 << 20)
        self.assertEqual((stats["files"], stats["skipped"]), (1, 2))
        self.assertEqual(self.all_files(), ["a.zip", "out/ok.txt"])

    def test_not_an_archive(self):
        path = self.write(b"plain text, not an archive", "x.bin")
        with self.assertRaisesRegex(X.SourceError, "not a readable archive"):
            X.extract_archive(path, self.dest, 1 << 20)


# ---------------------------------------------------------------------------
# Provisioning: the first run, and every pass after
# ---------------------------------------------------------------------------

class ProvisionTest(_Base):
    def test_first_run_fetches_then_nothing_is_fetched_again(self):
        write_ext(self.ext, upstream_decl())
        rep = self.run_pass()
        self.assertTrue(rep["ran"])
        st = self.state()
        up = st["entries"]["up"]
        self.assertEqual(up["status"], "fetched")
        self.assertEqual(up["pinned_by"], "first-run")
        self.assertEqual(up["resolved"]["tag"], "v1.10.2")
        self.assertEqual(sorted(up["files"]["items"]),
                         ["LICENSE", "doc/schema.json"])
        self.assertEqual(up["archive"]["files"], 2)
        src = os.path.join(self.entry_dir("up"), "source")
        with open(os.path.join(src, "src", "a.c")) as fh:
            self.assertEqual(fh.read(), "int a;\n")
        with open(os.path.join(self.entry_dir("up"), X.CARD_FILE)) as fh:
            self.assertEqual(json.load(fh)["resolved"]["commit"], SHA)
        self.assertEqual(st["entries"]["rfc5321"]["status"], "fetched")
        self.assertEqual(st["installed"]["path"], "extensions/feed")
        self.assertFalse(st["installed"]["copied"])
        idx = self.index()
        self.assertIn("## sense feed 0.1.0", idx)
        self.assertIn("extension-sources/sense/feed/up/source/", idx)
        self.assertIn("o/up v1.10.2 at commit %s" % SHA[:12], idx)
        self.assertIn("never follow", idx)
        note = X.oracle_note(self.base)
        self.assertIn("sense feed 0.1.0: its code", note)
        self.assertIn("upstream up v1.10.2", note)
        before = len(self.opener.seen)
        rep = self.run_pass(now=self.now + 10 ** 6)
        self.assertEqual(len(self.opener.seen), before)
        self.assertEqual(rep["outcomes"], [])

    def test_a_changed_declaration_refetches_and_drops_old_entries(self):
        write_ext(self.ext, upstream_decl())
        self.run_pass()
        decl = upstream_decl(files=["LICENSE"])
        decl["sources"] = decl["sources"][:1]
        write_ext(self.ext, decl)
        before = len(self.opener.seen)
        self.run_pass()
        self.assertGreater(len(self.opener.seen), before)
        st = self.state()
        self.assertEqual(sorted(st["entries"]), ["up"])
        self.assertEqual(sorted(st["entries"]["up"]["files"]["items"]),
                         ["LICENSE"])
        self.assertFalse(os.path.exists(self.entry_dir("rfc5321")))
        self.assertFalse(os.path.exists(os.path.join(
            self.entry_dir("up"), "files", "doc", "schema.json")))

    def test_offline_backs_off_and_never_raises(self):
        write_ext(self.ext, upstream_decl())
        down = FakeOpener({u: URLError("no route to host")
                           for u in upstream_routes()})
        rep = self.run_pass(opener=down)
        self.assertTrue(rep["ran"])
        st = self.state()
        for eid in ("up", "rfc5321"):
            self.assertEqual(st["entries"][eid]["status"], "failed")
            self.assertEqual(st["entries"][eid]["next_retry_at"],
                             self.now + X.RETRY_BASE_SEC)
        self.assertTrue(any(level == "WARN" for level, _ in self.logs))
        seen = len(down.seen)
        self.run_pass(opener=down, now=self.now + 60)
        self.assertEqual(len(down.seen), seen, "retried inside the backoff")
        self.run_pass(opener=down, now=self.now + X.RETRY_BASE_SEC + 1)
        self.assertGreater(len(down.seen), seen)
        self.assertEqual(self.state()["entries"]["up"]["attempts"], 2)
        self.run_pass(now=self.now + 10 * X.RETRY_CAP_SEC)
        self.assertEqual(self.state()["entries"]["up"]["status"], "fetched")
        idx = self.index()
        self.assertNotIn("not here yet", idx)

    def test_force_retries_inside_the_backoff(self):
        write_ext(self.ext, upstream_decl())
        down = FakeOpener({u: URLError("down") for u in upstream_routes()})
        self.run_pass(opener=down)
        self.run_pass(force=True, now=self.now + 1)
        self.assertEqual(self.state()["entries"]["up"]["status"], "fetched")

    def test_a_missing_file_is_noted_not_retried(self):
        write_ext(self.ext, upstream_decl(files=["LICENSE", "gone.txt"]))
        self.run_pass()
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "fetched")
        self.assertIn("gone.txt", up["detail"])
        self.assertIn("missing: gone.txt", self.index())
        before = len(self.opener.seen)
        self.run_pass(now=self.now + 10 * X.RETRY_CAP_SEC)
        self.assertEqual(len(self.opener.seen), before)

    def _lock_for(self, decl, routes, tamper=False):
        fetcher = X.Fetcher(opener=FakeOpener(routes))
        tmp = tempfile.mkdtemp()
        try:
            block = X.pin_declaration(fetcher, X.parse_declaration(decl),
                                      tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if tamper:
            block["entries"]["up"]["files"]["LICENSE"]["sha384"] = "0" * 96
        return {"lock_version": 1, "extensions": {"sense/feed": block}}

    def test_a_build_pin_is_used_and_enforced(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        proj = os.path.join(self.base, "project")
        os.makedirs(proj)
        with open(os.path.join(proj, X.PROJECT_LOCK_FILE), "w") as fh:
            json.dump(self._lock_for(decl, upstream_routes()), fh)
        self.run_pass()
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "fetched")
        self.assertEqual(up["pinned_by"], "build")
        self.assertFalse([u for u in self.opener.urls()
                          if "api.github.com" in u],
                         "a pinned box asked GitHub to resolve")
        self.assertIn("pinned by the build", self.index())
        self.assertIn("when this Homing Pigeon release was built",
                      self.index())

    def test_bytes_that_differ_from_the_pin_are_refused(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        with open(os.path.join(self.ext, X.LOCK_FILE), "w") as fh:
            json.dump(self._lock_for(decl, upstream_routes(), tamper=True),
                      fh)
        self.run_pass()
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "mismatch")
        self.assertIn("digest mismatch", up["detail"])
        self.assertEqual(up["next_retry_at"], self.now + X.RETRY_CAP_SEC)
        self.assertFalse(os.path.exists(os.path.join(
            self.entry_dir("up"), "files", "LICENSE")))
        self.assertFalse(os.path.exists(os.path.join(
            self.entry_dir("up"), "source")))
        self.assertNotIn("upstream up", X.oracle_note(self.base))

    def test_a_tampered_archive_is_refused(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        lock = self._lock_for(decl, upstream_routes())
        with open(os.path.join(self.ext, X.LOCK_FILE), "w") as fh:
            json.dump(lock, fh)
        self.opener.routes[ASSET] = tgz({"README": b"swapped"})
        self.run_pass()
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "mismatch")
        self.assertFalse(os.path.exists(os.path.join(
            self.entry_dir("up"), "source")))

    def test_the_extension_lock_wins_and_a_stale_lock_is_ignored(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        proj = os.path.join(self.base, "project")
        os.makedirs(proj)
        with open(os.path.join(proj, X.PROJECT_LOCK_FILE), "w") as fh:
            json.dump(self._lock_for(decl, upstream_routes(), tamper=True),
                      fh)
        with open(os.path.join(self.ext, X.LOCK_FILE), "w") as fh:
            json.dump(self._lock_for(decl, upstream_routes()), fh)
        self.run_pass()
        self.assertEqual(self.state()["entries"]["up"]["pinned_by"],
                         "extension")
        # A lock made from another declaration does not apply.
        other = upstream_decl(files=["LICENSE"])
        lock = self._lock_for(other, upstream_routes(), tamper=True)
        os.unlink(os.path.join(self.ext, X.LOCK_FILE))
        with open(os.path.join(proj, X.PROJECT_LOCK_FILE), "w") as fh:
            json.dump(lock, fh)
        write_ext(self.ext, upstream_decl(files=["doc/schema.json"]))
        self.run_pass()
        up = self.state()["entries"]["up"]
        self.assertEqual((up["status"], up["pinned_by"]),
                         ("fetched", "first-run"))

    def test_the_budget_skips_archives_and_a_raised_budget_retries(self):
        big = tgz({"blob": os.urandom(3 << 20)})
        self.opener.routes[ASSET] = big
        write_ext(self.ext, upstream_decl())
        small = self.policy({"extension_sources": {"max_mb": 2}})
        self.run_pass(policy=small)
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "skipped")
        self.assertIn("extension_sources.max_mb", up["detail"])
        self.assertEqual(sorted(up["files"]["items"]),
                         ["LICENSE", "doc/schema.json"])
        self.assertEqual(self.state()["entries"]["rfc5321"]["status"],
                         "fetched")
        bigger = self.policy({"extension_sources": {"max_mb": 64}})
        self.run_pass(policy=bigger, now=self.now + 60)
        self.assertEqual(self.state()["entries"]["up"]["status"], "fetched")

    def test_installed_code_outside_the_state_dir_is_copied_safely(self):
        outside = os.path.join(self.tmp, "elsewhere", "feed")
        write_ext(outside, None, files={
            "feed.py": b"print(1)\n", "README.md": b"# feed\n",
            ".env": b"TOKEN=x\n", "api_token.txt": b"x\n",
            "server.key": b"k\n", "__pycache__/feed.cpython-313.pyc": b"x",
            "big.bin": b"x" * (X.LOCAL_FILE_CAP + 1)})
        self.run_pass(targets=[target(outside)])
        st = self.state()
        inst = st["installed"]
        self.assertTrue(inst["copied"])
        self.assertEqual(inst["path"], "extension-sources/sense/feed/installed")
        copied = sorted(os.listdir(os.path.join(self.base, *inst["path"]
                                                .split("/"))))
        self.assertEqual(copied, ["README.md", "extension.json", "feed.py"])
        self.assertEqual(sorted(inst["files"]),
                         ["README.md", "extension.json", "feed.py"])
        self.assertIn("(copied from", self.index())

    def test_project_paths_are_referenced_in_place_or_copied(self):
        decl = {"sources_version": 1, "sources": [
            {"id": "code", "role": "self",
             "project": ["runner/mailbox.py", "runner/transport_extensions"
                         "/email"]}]}
        write_ext(self.ext, decl)
        self.run_pass(project_root=REPO)
        code = self.state()["entries"]["code"]
        self.assertEqual(code["status"], "fetched")
        items = code["project"]["items"]
        self.assertEqual(items["runner/mailbox.py"],
                         "extension-sources/sense/feed/code/files/runner/"
                         "mailbox.py")
        self.assertTrue(items["runner/transport_extensions/email"]
                        .endswith("/email/"))
        self.assertTrue(os.path.isfile(os.path.join(
            self.entry_dir("code"), "files", "runner", "mailbox.py")))
        # An installed project snapshot inside the state dir is read
        # where it sits.
        snap = os.path.join(self.base, "project", "runner")
        os.makedirs(snap)
        shutil.copy(os.path.join(REPO, "runner", "mailbox.py"), snap)
        decl["sources"][0]["project"] = ["runner/mailbox.py"]
        write_ext(self.ext, decl)
        self.run_pass()
        code = self.state()["entries"]["code"]
        self.assertEqual(code["project"]["items"]["runner/mailbox.py"],
                         "project/runner/mailbox.py")

    def test_a_pi_light_box_fetches_under_the_default(self):
        write_ext(self.ext, upstream_decl())
        rep = self.run_pass(policy=self.policy(
            {"oracle_mode": "deterministic"}, model=False))
        self.assertTrue(rep["ran"])
        self.assertEqual(self.state()["entries"]["up"]["status"], "fetched")

    def test_fetch_off_for_one_extension_fetches_nothing(self):
        write_ext(self.ext, upstream_decl())
        pol = self.policy({"extension_sources": {
            "extensions": {"feed": {"fetch": False}}}})
        self.run_pass(policy=pol)
        self.assertEqual(self.opener.seen, [])
        st = self.state()
        self.assertEqual({e["status"] for e in st["entries"].values()},
                         {"off"})
        self.assertIsNone(st["installed"])

    def test_auto_leaves_a_box_without_a_model_untouched(self):
        write_ext(self.ext, upstream_decl())
        rep = self.run_pass(policy=self.policy(
            {"extension_sources": "auto"}, model=False))
        self.assertFalse(rep["ran"])
        self.assertFalse(os.path.exists(os.path.join(self.base,
                                                     X.STATE_DIRNAME)))
        self.assertEqual(self.opener.seen, [])

    def test_a_broken_setting_withholds_everything_and_fetches_nothing(self):
        write_ext(self.ext, upstream_decl())
        self.run_pass()
        self.assertTrue(X.oracle_note(self.base))
        bad = self.policy({"extension_sources": "sometimes"})
        before = len(self.opener.seen)
        self.run_pass(policy=bad, now=self.now + 10 ** 6, force=True)
        self.assertEqual(len(self.opener.seen), before)
        self.assertEqual(X.oracle_note(self.base), "")
        self.assertNotIn("## sense feed", self.index())
        root = os.path.join(self.base, X.STATE_DIRNAME, "sense", "feed")
        self.assertTrue(X.is_withheld(os.path.join(root, "up", "source",
                                                   "README"),
                                      X.withheld_paths(self.base)))

    def test_an_extension_that_left_goes_inactive(self):
        write_ext(self.ext, upstream_decl())
        self.run_pass()
        self.run_pass(targets=[])
        self.assertFalse(self.state()["active"])
        self.assertNotIn("## sense feed", self.index())
        self.assertEqual(X.oracle_note(self.base), "")

    def test_one_pass_at_a_time(self):
        write_ext(self.ext, upstream_decl())
        root = os.path.join(self.base, X.STATE_DIRNAME)
        os.makedirs(root)
        lock = os.path.join(root, ".pass.lock")
        with open(lock, "w") as fh:
            fh.write("{}")
        rep = self.run_pass(now=time.time())
        self.assertTrue(rep["busy"])
        self.assertFalse(rep["ran"])
        old = time.time() - X.PASS_LOCK_STALE_SEC - 10
        os.utime(lock, (old, old))
        rep = self.run_pass(now=time.time())
        self.assertTrue(rep["ran"])
        self.assertFalse(os.path.exists(lock))

    def test_an_offline_box_can_be_seeded_by_copying_the_folder(self):
        write_ext(self.ext, upstream_decl())
        self.run_pass()
        # A second, offline box with the same extension: copy the
        # folder over, and its first pass keeps what arrived.
        other = os.path.join(self.tmp, "offline")
        other_ext = os.path.join(other, "extensions", "feed")
        shutil.copytree(self.ext, other_ext)
        shutil.copytree(os.path.join(self.base, X.STATE_DIRNAME),
                        os.path.join(other, X.STATE_DIRNAME))
        down = FakeOpener({})
        X.provision(other, [target(other_ext)], self.policy(),
                    fetcher=X.Fetcher(opener=down), now=self.now + 60)
        self.assertEqual(down.seen, [])
        with open(os.path.join(other, X.STATE_DIRNAME, "sense", "feed",
                               X.STATE_FILE)) as fh:
            st = json.load(fh)
        self.assertEqual(st["entries"]["up"]["status"], "fetched")
        self.assertEqual(st["installed"]["path"], "extensions/feed")
        self.assertIn("upstream up", X.oracle_note(other))

    def test_a_refused_declaration_still_brings_the_installed_code(self):
        write_ext(self.ext, {"sources_version": 1, "sorces": []})
        rep = self.run_pass()
        st = self.state()
        self.assertIn("unknown field", st["declaration_problem"])
        self.assertEqual(st["installed"]["path"], "extensions/feed")
        self.assertEqual(rep["outcomes"][0]["status"], "refused")


class DisclosureTest(_Base):
    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())

    def test_an_owner_withheld_extension_is_invisible(self):
        pol = self.policy({"extension_sources": {
            "extensions": {"feed": {"oracle": "withhold"}}}})
        self.run_pass(policy=pol)
        self.assertEqual(self.state()["entries"]["up"]["status"], "fetched")
        self.assertNotIn("feed", self.index())
        self.assertEqual(X.oracle_note(self.base), "")
        held = X.withheld_paths(self.base)
        root = os.path.join(self.base, X.STATE_DIRNAME, "sense", "feed")
        for path in (os.path.join(root, "up", "source", "README"),
                     os.path.join(root, X.STATE_FILE),
                     os.path.join(self.ext, "feed.py"), root):
            self.assertTrue(X.is_withheld(path, held), path)
        self.assertFalse(X.is_withheld(
            os.path.join(self.base, X.STATE_DIRNAME, X.INDEX_FILE), held))

    def test_an_author_withheld_entry_hides_only_itself(self):
        decl = upstream_decl()
        decl["sources"][0]["oracle"] = "withhold"
        write_ext(self.ext, decl)
        self.run_pass()
        idx = self.index()
        self.assertIn("`rfc5321`", idx)
        self.assertNotIn("`up`", idx)
        note = X.oracle_note(self.base)
        self.assertIn("spec rfc5321", note)
        self.assertNotIn("upstream up", note)
        held = X.withheld_paths(self.base)
        root = os.path.join(self.base, X.STATE_DIRNAME, "sense", "feed")
        self.assertTrue(X.is_withheld(os.path.join(root, "up", "CARD.json"),
                                      held))
        self.assertFalse(X.is_withheld(os.path.join(
            root, "rfc5321", "files", "rfc5321.txt"), held))
        self.assertFalse(X.is_withheld(os.path.join(self.ext, "feed.py"),
                                       held))

    def test_the_owner_global_withhold_beats_the_author(self):
        decl = upstream_decl()
        decl["oracle"] = "provide"
        write_ext(self.ext, decl)
        self.run_pass(policy=self.policy({"extension_sources": {
            "oracle": "withhold"}}))
        self.assertEqual(X.oracle_note(self.base), "")
        self.assertIn("(Nothing is provided yet.)", self.index())


# ---------------------------------------------------------------------------
# The runner wiring
# ---------------------------------------------------------------------------

class RunnerWiringTest(_Base):
    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())

    def test_the_file_tools_refuse_withheld_material(self):
        pol = self.policy({"extension_sources": {
            "extensions": {"feed": {"oracle": "withhold"}}}})
        self.run_pass(policy=pol)
        src = "extension-sources/sense/feed/up/source/README"
        self.assertEqual(R._run_oracle_tool("read_file", {"path": src},
                                            self.base),
                         R._WITHHELD_TOOL_ERROR)
        self.assertEqual(R._run_oracle_tool(
            "read_file", {"path": "extensions/feed/feed.py"}, self.base),
            R._WITHHELD_TOOL_ERROR)
        self.assertEqual(R._run_oracle_tool(
            "write_file", {"path": src, "content": "x"}, self.base),
            R._WITHHELD_TOOL_ERROR)
        listing = R._run_oracle_tool("list_dir",
                                     {"path": "extension-sources/sense"},
                                     self.base)
        self.assertNotIn("feed", listing)
        listing = R._run_oracle_tool("list_dir", {"path": "extensions"},
                                     self.base)
        self.assertNotIn("feed", listing)

    def test_the_file_tools_read_provided_material(self):
        self.run_pass()
        out = R._run_oracle_tool(
            "read_file",
            {"path": "extension-sources/sense/feed/up/source/README"},
            self.base)
        self.assertEqual(out, "hello\n")
        listing = R._run_oracle_tool(
            "list_dir", {"path": "extension-sources/sense/feed"}, self.base)
        self.assertIn("up/", listing)

    def test_the_oracle_context_names_provided_sources_only(self):
        self.run_pass()
        ctx = R.oracle_context(self.base, watch=False)
        self.assertIn("Extension sources:", ctx)
        self.assertIn("extension-sources/INDEX.md", ctx)
        pol = self.policy({"extension_sources": {"oracle": "withhold"}})
        self.run_pass(policy=pol, now=self.now + 1)
        self.assertNotIn("Extension sources:",
                         R.oracle_context(self.base, watch=False))

    def test_inspect_sources_prints_the_state(self):
        self.run_pass()
        args = mock.Mock(inspect="sources", config=os.path.join(
            self.base, "config.json"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(R.run_inspect({"base_dir": self.base}, args), 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["extensions"][0]["name"], "feed")
        self.assertEqual(data["extensions"][0]["entries"]["up"]["status"],
                         "fetched")

    def test_fetch_sources_runs_in_the_foreground(self):
        cfg = {"base_dir": self.base, "transports": ["file"],
               "extension_sources": "auto"}
        args = mock.Mock(config=os.path.join(self.base, "config.json"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = R.run_fetch_sources(cfg, args,
                                     fetcher=X.Fetcher(opener=self.opener))
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("INDEX.md", buf.getvalue())
        st = self.state()
        self.assertEqual(st["entries"]["up"]["status"], "fetched")
        file_state = self.state(kind="transport", name="file")
        self.assertEqual(file_state["entries"]["code"]["status"], "fetched")
        cfg["extension_sources"] = False
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(R.run_fetch_sources(cfg, args), 0)
        self.assertIn("nothing to fetch", buf.getvalue())

    def test_targets_are_loaded_senses_and_enabled_transports(self):
        names = [(t["kind"], t["name"]) for t in R._extension_source_targets(
            {"base_dir": self.base}, self.base)]
        self.assertIn(("sense", "feed"), names)
        self.assertIn(("transport", "email"), names)
        self.assertNotIn(("transport", "nats"), names)

    def test_the_tick_runs_one_background_pass_when_due(self):
        started = []

        def fake_pass(cfg, base_dir, force=False, fetcher=None):
            started.append(base_dir)
            time.sleep(0.2)

        with mock.patch.object(R, "_extension_sources_pass", fake_pass), \
                mock.patch.dict(R._EXTSOURCES_PASS,
                                {"thread": None, "next_due": 0.0,
                                 "since": None}):
            # No loop started: no pass, ever.
            self.assertFalse(R._extension_sources_tick({}, self.base,
                                                       now=1000.0,
                                                       due_now=True))
            # Inside the startup grace: no pass, not even on a
            # config edit.
            R._extension_sources_start(now=1000.0 - 30)
            self.assertFalse(R._extension_sources_tick({}, self.base,
                                                       now=1000.0,
                                                       due_now=True))
            R._extension_sources_start(
                now=1000.0 - R.EXTSOURCES_STARTUP_GRACE_SEC)
            self.assertTrue(R._extension_sources_tick({}, self.base,
                                                      now=1000.0))
            self.assertFalse(R._extension_sources_tick({}, self.base,
                                                       now=1001.0,
                                                       due_now=True))
            R._EXTSOURCES_PASS["thread"].join(5)
            self.assertFalse(R._extension_sources_tick({}, self.base,
                                                       now=1002.0))
            self.assertTrue(R._extension_sources_tick({}, self.base,
                                                      now=1003.0,
                                                      due_now=True))
            R._EXTSOURCES_PASS["thread"].join(5)
        self.assertEqual(len(started), 2)

    def test_the_setting_is_live(self):
        self.assertIn("extension_sources", R.LIVE_KEYS)
        path = os.path.join(self.base, "config.json")
        with open(path, "w") as fh:
            json.dump({"extension_sources": False}, fh)
        cfg = {"extension_sources": "auto"}

        def load(p):
            with open(p) as fh:
                return json.load(fh)

        with mock.patch.object(R, "load_config", load):
            changed = R.reload_hot_config(cfg, path, {"mtime": 0})
        self.assertIn("extension_sources", changed)
        self.assertIs(cfg["extension_sources"], False)

    def test_model_oracle_detection(self):
        loop = {"inference": {"endpoint": "http://127.0.0.1:11434/v1",
                              "model": "m"}}
        self.assertTrue(R._model_oracle_configured(loop))
        self.assertFalse(R._model_oracle_configured(
            dict(loop, oracle_mode="deterministic")))
        self.assertFalse(R._model_oracle_configured(
            {"inference": {"endpoint": "http://10.0.0.5:11434/v1",
                           "model": "m"}}))
        self.assertFalse(R._model_oracle_configured({}))


# ---------------------------------------------------------------------------
# The build's pin tool and the snapshot
# ---------------------------------------------------------------------------

class PinToolTest(_Base):
    def test_pin_dirs_writes_a_lock_the_box_accepts(self):
        write_ext(self.ext, upstream_decl(files=["LICENSE", "gone.txt"]))
        fetcher = X.Fetcher(opener=FakeOpener(upstream_routes()))
        lines = []
        lock, problems = PIN.pin_dirs([self.ext], fetcher, out=lines.append)
        self.assertEqual(problems, 1)
        block = lock["extensions"]["sense/feed"]
        up = block["entries"]["up"]
        self.assertEqual(up["resolved"]["commit"], SHA)
        self.assertEqual(up["files"]["LICENSE"]["sha384"],
                         hashlib.sha384(b"MIT\n").hexdigest())
        self.assertIn("archive", up)
        self.assertTrue(any("gone.txt" in p for p in up["problems"]))
        self.assertTrue(any("v1.10.2 @ %s" % SHA[:12] in ln for ln in lines))
        proj = os.path.join(self.base, "project")
        os.makedirs(proj)
        with open(os.path.join(proj, X.PROJECT_LOCK_FILE), "w") as fh:
            json.dump(lock, fh)
        self.run_pass()
        st = self.state()["entries"]["up"]
        self.assertEqual((st["status"], st["pinned_by"]), ("fetched", "build"))
        self.assertIn("unavailable when this build was made", st["detail"])

    def test_no_archives_records_urls_only(self):
        write_ext(self.ext, upstream_decl())
        opener = FakeOpener(upstream_routes())
        lock, _ = PIN.pin_dirs([self.ext], X.Fetcher(opener=opener),
                               hash_archives=False, out=lambda s: None)
        arch = lock["extensions"]["sense/feed"]["entries"]["up"]["archive"]
        self.assertEqual(arch, {"url": ASSET})
        self.assertNotIn(ASSET, opener.urls())

    def test_the_snapshot_ships_and_indexes_the_lock(self):
        lock = {"lock_version": 1, "generated_at": "2026-10-22T00:00:00Z",
                "extensions": {"sense/feed": {"declaration_sha384": "x",
                                              "entries": {"up": {
                                                  "problems": ["a"]}}}}}
        path = os.path.join(self.tmp, "lock.json")
        with open(path, "w") as fh:
            json.dump(lock, fh)
        facts = SNAP.sources_lock_facts(path)
        self.assertEqual((facts["extensions"], facts["entries"],
                          facts["problems"]), (1, 1, 1))
        snap = {"commit": SHA, "version": "9.9.9", "run_url": None,
                "workflows": [], "tests": None,
                "extension_sources_lock": facts}
        md = SNAP.index_markdown(snap, "n", False, 3)
        self.assertIn("`EXTENSION-SOURCES.lock.json`", md)
        snap["extension_sources_lock"] = None
        self.assertNotIn("EXTENSION-SOURCES", SNAP.index_markdown(
            snap, "n", False, 3))


def _package_data(path):
    """[tool.setuptools.package-data] from pyproject.toml, without a
    TOML parser (3.9 has none): its arrays of strings are JSON."""
    out = {}
    section = False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                section = line == "[tool.setuptools.package-data]"
                continue
            if section and "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                out[key.strip().strip('"')] = json.loads(value.strip())
    return out


class PackagingTest(unittest.TestCase):
    def test_the_wheel_carries_every_transport_manifest_and_declaration(self):
        # A wheel without a shipped transport's extension.json has no
        # transport at all: discovery finds folders by their manifests.
        data = _package_data(os.path.join(REPO, "pyproject.toml"))
        root = os.path.join(REPO, "runner", "transport_extensions")
        for name in sorted(os.listdir(root)):
            folder = os.path.join(root, name)
            for fname in ("extension.json", X.SOURCES_FILE):
                if os.path.isfile(os.path.join(folder, fname)):
                    self.assertIn(
                        fname, data.get("runner.transport_extensions."
                                        + name, []), (name, fname))


class DocsTest(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_the_extensions_doc_states_the_rule(self):
        doc = " ".join(self.read("docs", "extensions.md").split())
        self.assertIn("## Sources", doc)
        for phrase in ("sources.json", "extension_sources",
                       "--fetch-sources", "--inspect sources",
                       "EXTENSION-SOURCES.lock.json", "sources.lock.json",
                       "provide", "withhold", "not a confidentiality "
                       "boundary"):
            self.assertIn(phrase, doc)

    def test_the_protocol_names_the_rule(self):
        self.assertIn("disclosure rule", self.read("PROTOCOL.md"))

    def test_the_example_config_documents_the_key(self):
        cfg = json.loads(self.read("runner", "config.example.json"))
        self.assertIs(cfg["extension_sources"], True)
        self.assertIn("docs/extensions.md", cfg["_extension_sources"])


if __name__ == "__main__":
    unittest.main()
