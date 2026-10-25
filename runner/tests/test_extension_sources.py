#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""Extension sources: each extension brings its own code for the Oracle.

The contract under test (runner/ops/extsources.py, docs/extend/extensions.md
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
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from urllib.error import HTTPError, URLError

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extsources as X  # noqa: E402
from runner import runner as R  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "pin_extension_sources",
    os.path.join(REPO, "runner", "tools", "pin_extension_sources.py"))
PIN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PIN)
_spec2 = importlib.util.spec_from_file_location(
    "make_snapshot", os.path.join(REPO, "runner", "tools", "make_snapshot.py"))
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


PINNED_SHA = "c" * 40
PINNED_RAW = "https://raw.githubusercontent.com/o/up/%s/" % PINNED_SHA
PINNED_FILES = {"LICENSE": b"MIT\n", "doc/schema.json": b'{"pinned": 1}\n'}


def manifest_upstream(license_="MIT"):
    return {"repo": "https://github.com/o/up", "ref": "main",
            "pin": PINNED_SHA, "paths": list(PINNED_FILES),
            "license": license_}


def pinned_routes():
    return {PINNED_RAW + k: v for k, v in PINNED_FILES.items()}


def write_pin_json(folder, pin=PINNED_SHA, files=PINNED_FILES):
    """What runner/tools/fetch_upstream.py writes beside the files it carries."""
    import hashlib
    updir = os.path.join(folder, "upstream")
    recs = {}
    for rel, data in files.items():
        path = os.path.join(updir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        recs[rel] = {"sha384": hashlib.sha384(data).hexdigest(),
                     "bytes": len(data)}
    with open(os.path.join(updir, "PIN.json"), "w") as fh:
        json.dump({"repo": "https://github.com/o/up", "ref": "main",
                   "pin": pin, "fetched_at": "2026-10-22T00:00:00Z",
                   "bytes": sum(len(v) for v in files.values()),
                   "files": recs}, fh)


def write_ext(folder, decl=None, name="feed", kind="sense", files=None,
              upstream=None):
    os.makedirs(folder, exist_ok=True)
    manifest = {"name": name, "version": "0.1.0", "api_version": 1,
                "kind": kind,
                "description": "A test extension."}
    if kind == "sense":
        manifest["signals"] = [{"name": "s", "description": "A signal."}]
    else:
        manifest["entry"] = ["{python}", "x.py"]
        manifest["publisher"] = "Tests"
    if upstream is not None:
        manifest["upstream"] = upstream
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
        # The harness default is the permissive owner: fetch on this
        # box, and trust what it fetches first. The defaults the
        # software ships ("auto", unpinned false) have their own tests.
        if cfg is None:
            cfg = {"extension_sources": {"fetch": True, "unpinned": True}}
        return X.owner_policy(cfg, model_oracle=model)

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
                             "project": ["runner/wire/transports.py"]}]})
        self.assertEqual(d["oracle"], "withhold")
        up, doc, code = d["sources"]
        self.assertEqual((up["ref"], up["archive"], up["max_mb"]),
                         ("latest", False, X.DEFAULT_ENTRY_MB))
        self.assertEqual(doc["location"], "url")
        self.assertEqual(code["project"], ["runner/wire/transports.py"])
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
    NAMED_REFS = {"softflowd": "master"}

    def folders(self):
        return [os.path.join(REPO, "runner", "extensions", a)
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
        from runner.ops import extensions as E
        for folder in self.folders():
            decl, problem = X.load_declaration(folder)
            self.assertIsNone(problem, folder)
            self.assertIsNotNone(decl, folder)
            with open(os.path.join(folder, "extension.json")) as fh:
                E.parse_manifest(json.load(fh))

    def test_adapters_bring_their_upstream_source(self):
        for name in self.ADAPTERS:
            decl, _ = X.load_declaration(
                os.path.join(REPO, "runner", "extensions", name))
            ups = [e for e in decl["sources"] if e["role"] == "upstream"]
            self.assertTrue(ups, name)
            for e in ups:
                self.assertEqual(e["location"], "github", name)
                # "latest", so each release pins the newest; softflowd
                # follows master because its last release predates
                # the record writers (compat/netflow5.c, netflow9.c)
                # the 3.12.53 pin found missing at that tag.
                self.assertEqual(e["ref"], self.NAMED_REFS.get(
                    e["id"], "latest"), name)
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
    def test_the_default_is_auto_and_follows_the_model(self):
        # Absent means "auto": a box whose Oracle runs a local model
        # fetches; a deterministic box makes no request. `true` is
        # the owner saying every box fetches, a Pi Light included.
        self.assertTrue(X.owner_policy({}, model_oracle=True)["enabled"])
        self.assertFalse(X.owner_policy({}, model_oracle=False)["enabled"])
        self.assertEqual(X.owner_policy({})["fetch"], "auto")
        self.assertTrue(X.owner_policy({"extension_sources": True},
                                       model_oracle=False)["enabled"])
        self.assertTrue(X.owner_policy({"extension_sources": "auto"},
                                       model_oracle=True)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": "auto"},
                                        model_oracle=False)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": {
            "fetch": "auto"}}, model_oracle=False)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": {}},
                                        model_oracle=False)["enabled"])
        self.assertFalse(X.owner_policy({"extension_sources": False},
                                        model_oracle=True)["enabled"])
        pol = X.owner_policy({"extension_sources": {"max_mb": 10}})
        self.assertEqual(pol["max_bytes"], 10 << 20)

    def test_unpinned_is_off_by_default_and_the_owner_turns_it_on(self):
        self.assertFalse(X.owner_policy({})["unpinned"])
        self.assertFalse(X.unpinned_allowed(X.owner_policy({}), "feed"))
        pol = X.owner_policy({"extension_sources": {"unpinned": True}})
        self.assertTrue(X.unpinned_allowed(pol, "feed"))
        pol = X.owner_policy({"extension_sources": {
            "extensions": {"feed": {"unpinned": True}}}})
        self.assertTrue(X.unpinned_allowed(pol, "feed"))
        self.assertFalse(X.unpinned_allowed(pol, "other"))
        pol = X.owner_policy({"extension_sources": {
            "unpinned": True, "extensions": {"feed": {"unpinned": False}}}})
        self.assertFalse(X.unpinned_allowed(pol, "feed"))
        self.assertTrue(X.unpinned_allowed(pol, "other"))
        for bad in ({"unpinned": "yes"},
                    {"extensions": {"feed": {"unpinned": 1}}}):
            pol = X.owner_policy({"extension_sources": bad})
            self.assertFalse(pol["valid"], bad)
            self.assertFalse(X.unpinned_allowed(pol, "feed"))

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


class FetcherOpenEdgesTest(unittest.TestCase):
    """Queue A refill: Fetcher._open's error legs (coverage
    run 40187685363: 6 lines on both platforms). The one
    network door classifies every failure as a
    SourceError: a SourceError raised by the opener
    itself passes through unchanged; an HTTP error is
    closed even when closing fails, and 403/429 are
    named as rate limiting; a transport-level OSError
    becomes "cannot fetch".
    """

    def test_a_source_error_from_the_opener_passes_through(self):
        err = X.SourceError("direct failure", kind="budget")
        f = X.Fetcher(opener=FakeOpener({"https://e.org/x": err}))
        with self.assertRaises(X.SourceError) as cm:
            f._open("https://e.org/x", "*/*")
        self.assertIs(cm.exception, err)

    def test_rate_limited_http_errors_close_even_if_close_fails(self):
        class BadClose(HTTPError):
            def close(self):
                raise RuntimeError("close failed")

        for code in (403, 429):
            url = "https://e.org/limited"
            err = BadClose(url, code, "Limited", {}, io.BytesIO(b""))
            f = X.Fetcher(opener=FakeOpener({url: err}))
            with self.assertRaises(X.SourceError) as cm:
                f._open(url, "*/*")
            self.assertIn("HTTP %d" % code, str(cm.exception))
            self.assertIn("rate limited", str(cm.exception))

    def test_a_transport_oserror_becomes_cannot_fetch(self):
        f = X.Fetcher(opener=FakeOpener(
            {"https://e.org/x": OSError("socket gone")}))
        with self.assertRaisesRegex(X.SourceError, "cannot fetch"):
            f._open("https://e.org/x", "*/*")


class _StubResp:
    def __init__(self, chunks, read_error=None, close_error=None):
        self._chunks = list(chunks)
        self._read_error = read_error
        self._close_error = close_error

    def read(self, _n):
        if self._read_error is not None:
            raise self._read_error
        return self._chunks.pop(0) if self._chunks else b""

    def close(self):
        if self._close_error is not None:
            raise self._close_error


class _StubOpener:
    def __init__(self, resp):
        self._resp = resp

    def open(self, _req, timeout=None):
        return self._resp


class FetcherStreamEdgesTest(unittest.TestCase):
    """Queue A refill: the fetcher's streaming legs --
    _read_capped and download (coverage run
    40189608702: 5 lines each on both platforms).
    The streaming contract: a body past the cap is a
    SourceError naming the cap; a read that fails
    mid-stream is a SourceError naming the read (and
    a download removes its partial file); a close
    that fails is swallowed in both readers, because
    the bytes, not the close, are the result.
    """

    def test_a_body_past_the_cap_is_refused(self):
        f = X.Fetcher(opener=FakeOpener({}))
        with self.assertRaisesRegex(X.SourceError,
                                    "larger than 10 bytes"):
            f._read_capped(_StubResp([b"x" * 100]),
                           10, "https://e.org/x")

    def test_a_failed_read_is_a_source_error(self):
        f = X.Fetcher(opener=FakeOpener({}))
        with self.assertRaisesRegex(X.SourceError,
                                    "read from .* failed"):
            f._read_capped(
                _StubResp([], read_error=OSError("cut")),
                10, "https://e.org/x")

    def test_a_failed_close_is_swallowed_by_both_readers(self):
        f = X.Fetcher(opener=_StubOpener(_StubResp(
            [b"abc"], close_error=OSError("stuck"))))
        self.assertEqual(
            f._read_capped(f._opener.open(None), 10,
                           "https://e.org/x"), b"abc")
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out")
            f2 = X.Fetcher(opener=_StubOpener(_StubResp(
                [b"abc"], close_error=OSError("stuck"))))
            sha, n = f2.download("https://e.org/x", dest, 10)
            self.assertEqual(n, 3)
            self.assertEqual(
                sha, hashlib.sha384(b"abc").hexdigest())

    def test_a_failed_download_read_removes_the_partial_file(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out")
            f = X.Fetcher(opener=_StubOpener(_StubResp(
                [], read_error=OSError("cut"))))
            with self.assertRaisesRegex(
                    X.SourceError, "download of .* failed"):
                f.download("https://e.org/x", dest, 10)
            self.assertFalse(os.path.exists(dest))


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

    def test_a_member_under_a_planted_symlink_is_skipped(self):
        # Queue A refill: extract_archive's write() escape
        # check (coverage run 40189711740: lines
        # 1073-1074). Member names are sanitized before
        # write() ever sees them, so the check's remaining
        # live case is a destination that already holds a
        # symlink: a member under it would land outside,
        # and is skipped while its siblings extract.
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(outside)
        os.makedirs(self.dest)
        try:
            os.symlink(outside, os.path.join(self.dest, "linked"))
        except OSError:
            self.skipTest("symlinks unavailable")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("top/linked/evil.txt", "no")
            zf.writestr("top/good.txt", "fine")
        path = self.write(buf.getvalue(), "a.zip")
        stats = X.extract_archive(path, self.dest, 1 << 20)
        self.assertEqual((stats["files"], stats["skipped"]), (1, 1))
        self.assertEqual(os.listdir(outside), [])
        self.assertTrue(os.path.isfile(
            os.path.join(self.dest, "good.txt")))

    def test_a_member_the_filesystem_refuses_is_skipped(self):
        # Queue A refill: write()'s OSError leg (coverage
        # run 40189711740: lines 1091-1094) -- a member
        # whose target name is already a directory cannot
        # be written; it is counted and skipped, and the
        # rest of the archive still extracts.
        os.makedirs(os.path.join(self.dest, "clash"))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("top/clash", "no")
            zf.writestr("top/good.txt", "fine")
        path = self.write(buf.getvalue(), "a.zip")
        stats = X.extract_archive(path, self.dest, 1 << 20)
        self.assertEqual((stats["files"], stats["skipped"]), (1, 1))
        self.assertTrue(os.path.isfile(
            os.path.join(self.dest, "good.txt")))

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
        small = self.policy({"extension_sources": {"max_mb": 2,
                                                   "unpinned": True}})
        self.run_pass(policy=small)
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "skipped")
        self.assertIn("extension_sources.max_mb", up["detail"])
        self.assertEqual(sorted(up["files"]["items"]),
                         ["LICENSE", "doc/schema.json"])
        self.assertEqual(self.state()["entries"]["rfc5321"]["status"],
                         "fetched")
        bigger = self.policy({"extension_sources": {"max_mb": 64,
                                                    "unpinned": True}})
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
             "project": ["runner/wire/mailbox.py", "runner/transport_extensions"
                         "/email"]}]}
        write_ext(self.ext, decl)
        self.run_pass(project_root=REPO)
        code = self.state()["entries"]["code"]
        self.assertEqual(code["status"], "fetched")
        items = code["project"]["items"]
        self.assertEqual(items["runner/wire/mailbox.py"],
                         "extension-sources/sense/feed/code/files/runner/"
                         "wire/mailbox.py")
        self.assertTrue(items["runner/transport_extensions/email"]
                        .endswith("/email/"))
        self.assertTrue(os.path.isfile(os.path.join(
            self.entry_dir("code"), "files", "runner", "wire", "mailbox.py")))
        # An installed project snapshot inside the state dir is read
        # where it sits.
        snap = os.path.join(self.base, "project", "runner", "wire")
        os.makedirs(snap)
        shutil.copy(os.path.join(REPO, "runner", "wire", "mailbox.py"), snap)
        decl["sources"][0]["project"] = ["runner/wire/mailbox.py"]
        write_ext(self.ext, decl)
        self.run_pass()
        code = self.state()["entries"]["code"]
        self.assertEqual(code["project"]["items"]["runner/wire/mailbox.py"],
                         "project/runner/wire/mailbox.py")

    def test_a_pi_light_box_fetches_nothing_under_the_default(self):
        # No model reads the material on a deterministic box, so the
        # default ("auto") makes no request there. The owner's `true`
        # fetches on every box, a Pi Light included.
        write_ext(self.ext, upstream_decl())
        rep = self.run_pass(policy=self.policy(
            {"oracle_mode": "deterministic"}, model=False))
        self.assertFalse(rep["ran"])
        self.assertEqual(self.opener.seen, [])
        rep = self.run_pass(policy=self.policy(
            {"oracle_mode": "deterministic",
             "extension_sources": {"fetch": True, "unpinned": True}},
            model=False))
        self.assertTrue(rep["ran"])
        self.assertEqual(self.state()["entries"]["up"]["status"], "fetched")

    def test_the_manifest_upstream_reaches_the_oracle_as_pinned(self):
        # The manifest's upstream block, with the PIN.json the build
        # wrote beside its files, is a source entry the Oracle gets:
        # id "pinned", vouched for by those digests, no lock and no
        # consent needed. The URLs are rebuilt from the pin commit.
        write_ext(self.ext, None, upstream=manifest_upstream())
        write_pin_json(self.ext)
        self.opener.routes.update(pinned_routes())
        rep = self.run_pass(policy=self.policy({"extension_sources": True}))
        self.assertTrue(rep["ran"])
        st = self.state()
        self.assertEqual(st["manifest_upstream"],
                         {"github": "o/up", "pin": PINNED_SHA, "pinned": True})
        rec = st["entries"]["pinned"]
        self.assertEqual((rec["status"], rec["pinned_by"]),
                         ("fetched", "manifest"))
        self.assertEqual(rec["license"], "MIT")
        self.assertEqual(rec["resolved"]["commit"], PINNED_SHA)
        self.assertEqual(sorted(rec["files"]["items"]),
                         ["LICENSE", "doc/schema.json"])
        self.assertEqual(sorted(self.opener.urls()),
                         sorted(pinned_routes()))
        with open(os.path.join(self.entry_dir("pinned"), "files",
                               "doc", "schema.json")) as fh:
            self.assertEqual(fh.read(), '{"pinned": 1}\n')
        self.assertIn("pinned by the manifest", self.index())
        self.assertIn("at commit %s" % PINNED_SHA[:12], self.index())

    def test_bytes_that_differ_from_the_manifest_pin_are_refused(self):
        write_ext(self.ext, None, upstream=manifest_upstream())
        write_pin_json(self.ext)
        routes = pinned_routes()
        routes[PINNED_RAW + "doc/schema.json"] = b'{"tampered": 1}\n'
        self.opener.routes.update(routes)
        self.run_pass(policy=self.policy({"extension_sources": True}))
        rec = self.state()["entries"]["pinned"]
        self.assertEqual(rec["status"], "mismatch")
        self.assertFalse(os.path.exists(os.path.join(
            self.entry_dir("pinned"), "files", "doc", "schema.json")))

    def test_a_manifest_upstream_without_pin_json_waits_like_any_unpinned(self):
        # A checkout that never ran the tool, or a third-party
        # extension: the block is there, the digests are not. No
        # request is made until the owner allows trust on first use.
        write_ext(self.ext, None, upstream=manifest_upstream())
        self.opener.routes.update(pinned_routes())
        self.run_pass(policy=self.policy({"extension_sources": True}))
        st = self.state()
        self.assertEqual(st["manifest_upstream"]["pinned"], False)
        self.assertEqual(st["entries"]["pinned"]["status"], "unpinned")
        self.assertEqual(self.opener.seen, [])
        self.run_pass(policy=self.policy(
            {"extension_sources": {"fetch": True, "unpinned": True}}),
            now=self.now + 5)
        rec = self.state()["entries"]["pinned"]
        self.assertEqual((rec["status"], rec["pinned_by"]),
                         ("fetched", "first-run"))

    def test_a_stale_pin_json_does_not_vouch(self):
        # PIN.json from an older pin: the manifest moved, the tool
        # has not run. Its digests are for other bytes and are not
        # used; the entry waits as unpinned.
        write_ext(self.ext, None, upstream=manifest_upstream())
        write_pin_json(self.ext, pin="d" * 40)
        self.run_pass(policy=self.policy({"extension_sources": True}))
        self.assertEqual(self.state()["entries"]["pinned"]["status"],
                         "unpinned")

    def test_a_sources_entry_inherits_the_manifest_upstream(self):
        # "upstream": true names the manifest's repository: the entry
        # resolves to the same github location and takes the
        # manifest's license unless it says otherwise. Without a
        # manifest block, or beside a github field, it is refused.
        decl = upstream_decl()
        e = decl["sources"][0]
        del e["github"]
        del e["license"]
        e["upstream"] = True
        write_ext(self.ext, decl, upstream=manifest_upstream("BSD-3-Clause"))
        parsed, problem = X.load_declaration(self.ext)
        self.assertIsNone(problem)
        up = parsed["sources"][0]
        self.assertEqual((up["location"], up["github"], up["license"]),
                         ("github", "o/up", "BSD-3-Clause"))
        self.assertEqual(up["ref"], "latest")
        e["license"] = "MIT"
        write_ext(self.ext, decl, upstream=manifest_upstream("BSD-3-Clause"))
        parsed, _ = X.load_declaration(self.ext)
        self.assertEqual(parsed["sources"][0]["license"], "MIT")
        write_ext(self.ext, decl)
        parsed, problem = X.load_declaration(self.ext)
        self.assertIsNone(parsed)
        self.assertIn("declares no upstream block", problem)
        e["github"] = "o/up"
        write_ext(self.ext, decl, upstream=manifest_upstream())
        parsed, problem = X.load_declaration(self.ext)
        self.assertIn("exclusive", problem)
        del e["github"]
        e["upstream"] = "yes"
        write_ext(self.ext, decl, upstream=manifest_upstream())
        parsed, problem = X.load_declaration(self.ext)
        self.assertIn("must be true", problem)

    def test_pinned_is_a_reserved_entry_id(self):
        decl = upstream_decl(id="pinned")
        write_ext(self.ext, decl)
        parsed, problem = X.load_declaration(self.ext)
        self.assertIsNone(parsed)
        self.assertIn("reserved", problem)

    def test_an_unpinned_entry_waits_until_the_owner_allows_it(self):
        # The shipped default: nothing pins the entry, the owner has
        # not said "unpinned", so the box makes no request for it and
        # the index says why. Project entries are local and unaffected.
        write_ext(self.ext, upstream_decl())
        rep = self.run_pass(policy=self.policy({"extension_sources": True}))
        self.assertTrue(rep["ran"])
        self.assertEqual(self.opener.seen, [])
        st = self.state()
        self.assertEqual(st["entries"]["up"]["status"], "unpinned")
        self.assertIn("unpinned", st["entries"]["up"]["detail"])
        self.assertEqual(st["entries"]["rfc5321"]["status"], "unpinned")
        self.assertIn("not here yet (unpinned", self.index())
        self.assertEqual([o["status"] for o in rep["outcomes"]],
                         ["unpinned", "unpinned"])
        # The same pass again reports nothing new and still asks nothing.
        rep = self.run_pass(policy=self.policy({"extension_sources": True}),
                            now=self.now + 10)
        self.assertEqual(rep["outcomes"], [])
        self.assertEqual(self.opener.seen, [])
        # The owner allows it for this extension: it fetches on the
        # next pass and is recorded as resolved on this box.
        rep = self.run_pass(policy=self.policy({"extension_sources": {
            "fetch": True, "extensions": {"feed": {"unpinned": True}}}}),
            now=self.now + 20)
        up = self.state()["entries"]["up"]
        self.assertEqual((up["status"], up["pinned_by"]),
                         ("fetched", "first-run"))

    def test_a_build_pin_needs_no_unpinned_consent(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        proj = os.path.join(self.base, "project")
        os.makedirs(proj)
        with open(os.path.join(proj, X.PROJECT_LOCK_FILE), "w") as fh:
            json.dump(self._lock_for(decl, upstream_routes()), fh)
        self.run_pass(policy=self.policy({"extension_sources": True}))
        up = self.state()["entries"]["up"]
        self.assertEqual((up["status"], up["pinned_by"]), ("fetched", "build"))

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


class SmallPartsProblemsTest(_Base):
    """Queue A: the problem paths of _small_parts (coverage
    run 40180268696: 17 lines on both platforms) -- a project
    path this install does not have, a project path with
    nothing copyable in it, a project entry with no usable
    path at all, a pin that recorded no archive, and an
    archive that already landed and must be kept rather
    than fetched again. Each is a documented shape of the
    record: problems are named in the entry's detail, a
    partial fetch says partial, and an entry with nothing
    is a failure, never a quiet success.
    """

    def _project_decl(self, paths):
        return {"sources_version": 1, "sources": [
            {"id": "code", "role": "self", "project": paths}]}

    def test_a_missing_project_path_is_a_named_problem(self):
        write_ext(self.ext, self._project_decl(
            ["runner/wire/mailbox.py", "runner/wire/no-such.py"]))
        self.run_pass(project_root=REPO)
        code = self.state()["entries"]["code"]
        self.assertEqual(code["status"], "partial")
        self.assertEqual(sorted(code["project"]["items"]),
                         ["runner/wire/mailbox.py"])
        self.assertIn("runner/wire/no-such.py: not in this "
                      "install's project snapshot or source tree",
                      code["project"]["problems"][0])
        self.assertIn("no-such.py", code["detail"])

    def test_a_project_path_with_nothing_copyable(self):
        proj = os.path.join(self.tmp, "projroot")
        os.makedirs(os.path.join(proj, "emptydir"))
        with open(os.path.join(proj, "real.txt"), "w") as fh:
            fh.write("real\n")
        write_ext(self.ext, self._project_decl(
            ["real.txt", "emptydir"]))
        self.run_pass(project_root=proj)
        code = self.state()["entries"]["code"]
        self.assertEqual(code["status"], "partial")
        self.assertIn("emptydir: nothing copyable there",
                      code["project"]["problems"])
        self.assertEqual(sorted(code["project"]["items"]),
                         ["real.txt"])

    def test_an_interrupted_copy_cleans_up_and_propagates(self):
        # The project phase guards its staging dir with a
        # BaseException cleanup: an interruption mid-copy
        # removes the staging dir and propagates, never
        # leaving a half copy for the next pass to trip
        # over. A real mid-copy crash is not reproducible
        # in a suite, so the module's own copy helper is
        # scripted to raise the interruption.
        proj = os.path.join(self.tmp, "projroot")
        os.makedirs(proj)
        with open(os.path.join(proj, "real.txt"), "w") as fh:
            fh.write("real\n")
        write_ext(self.ext, self._project_decl(["real.txt"]))
        with mock.patch.object(X, "_copy_files",
                               side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_pass(project_root=proj)
        tmp_parent = os.path.join(self.base, X.STATE_DIRNAME,
                                  "sense", "feed", ".tmp")
        leftovers = (os.listdir(tmp_parent)
                     if os.path.isdir(tmp_parent) else [])
        self.assertEqual(leftovers, [])

    def test_no_usable_project_path_fails_the_entry(self):
        write_ext(self.ext, self._project_decl(
            ["gone/one.py", "gone/two.py"]))
        self.run_pass(project_root=REPO)
        code = self.state()["entries"]["code"]
        self.assertEqual(code["status"], "failed")
        self.assertIn("gone/one.py", code["detail"])
        self.assertIn("gone/two.py", code["detail"])

    def _lock_for(self, decl, routes):
        fetcher = X.Fetcher(opener=FakeOpener(routes))
        tmp = tempfile.mkdtemp()
        try:
            block = X.pin_declaration(fetcher, X.parse_declaration(decl),
                                      tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return {"lock_version": 1, "extensions": {"sense/feed": block}}

    def _lock_without_archive(self, decl):
        lock = self._lock_for(decl, upstream_routes())
        block = lock["extensions"]["sense/feed"]
        self.assertIn("archive", block["entries"]["up"])
        del block["entries"]["up"]["archive"]
        with open(os.path.join(self.ext, X.LOCK_FILE), "w") as fh:
            json.dump(lock, fh)

    def test_a_pin_without_an_archive_still_files_its_files(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        self._lock_without_archive(decl)
        self.run_pass()
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "fetched")
        self.assertIn("archive: unavailable when this build "
                      "was made", up["detail"])
        self.assertEqual(sorted(up["files"]["items"]),
                         ["LICENSE", "doc/schema.json"])
        self.assertNotIn(ASSET, self.opener.urls())

    def test_a_pin_without_an_archive_and_no_files_fails(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        self._lock_without_archive(decl)
        routes = {u: v for u, v in upstream_routes().items()
                  if u == ASSET}
        self.run_pass(opener=FakeOpener(routes))
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "failed")
        self.assertIn("archive: unavailable when this build "
                      "was made", up["detail"])

    def test_an_archive_that_landed_is_kept_on_the_retry(self):
        decl = upstream_decl()
        write_ext(self.ext, decl)
        lock = self._lock_for(decl, upstream_routes())
        with open(os.path.join(self.ext, X.LOCK_FILE), "w") as fh:
            json.dump(lock, fh)
        routes = dict(upstream_routes())
        del routes[RAW + "LICENSE"]
        self.run_pass(opener=FakeOpener(routes))
        up = self.state()["entries"]["up"]
        # A file the server says is not there is noted, not
        # retried (its own test pins that); the entry counts
        # as fetched, with the gap in its detail -- which is
        # what lets a forced pass revisit it below.
        self.assertEqual(up["status"], "fetched")
        self.assertIn("LICENSE", up["detail"])
        self.assertTrue(os.path.isdir(os.path.join(
            self.entry_dir("up"), "source")))
        second = FakeOpener(upstream_routes())
        self.run_pass(opener=second, force=True, now=self.now + 10)
        up = self.state()["entries"]["up"]
        self.assertEqual(up["status"], "fetched")
        self.assertEqual(sorted(up["files"]["items"]),
                         ["LICENSE", "doc/schema.json"])
        self.assertNotIn(ASSET, second.urls(),
                         "the landed archive was fetched again")


class DisclosureTest(_Base):
    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())

    def test_an_owner_withheld_extension_is_invisible(self):
        pol = self.policy({"extension_sources": {
            "unpinned": True,
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

    def test_an_unresolvable_withheld_entry_is_passed_over(self):
        # Queue A: is_withheld's fallback arm -- a withheld
        # entry that cannot be resolved (here one carrying
        # a NUL, which realpath refuses) is compared as
        # given, matches nothing, and is passed over: it
        # neither raises, nor withholds everything, nor
        # stops a later good entry from matching.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kept.py")
            with open(path, "w") as f:
                f.write("x")
            self.assertFalse(X.is_withheld(path, ["bad\x00entry"]))
            self.assertTrue(
                X.is_withheld(path, ["bad\x00entry", path]))

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
               "extension_sources": {"fetch": "auto", "unpinned": True}}
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

class DeclarationRefusalsTest(unittest.TestCase):
    """Queue A refill: _parse_entry's remaining refusal
    lines (coverage run 40187685363: 7 on both
    platforms). A sources declaration is the owner's
    instruction for what code and material land on the
    box, so its validation is exact: each malformed
    shape below is refused with a ValueError naming the
    field, through parse_declaration, the seam every
    declaration enters by.
    """

    def _refused(self, entry, fragment):
        decl = {"sources_version": 1, "sources": [entry]}
        with self.assertRaises(ValueError) as cm:
            X.parse_declaration(decl)
        self.assertIn(fragment, str(cm.exception))

    def _github(self, **over):
        entry = {"id": "up", "role": "upstream",
                 "github": "o/up", "ref": "latest",
                 "archive": True, "files": ["LICENSE"]}
        entry.update(over)
        return entry

    def test_an_entry_must_be_an_object(self):
        self._refused("not-an-object", "must be an object")

    def test_upstream_must_be_exactly_true(self):
        self._refused(
            {"id": "u1", "role": "upstream", "upstream": "yes"},
            ".upstream must be true")

    def test_a_github_archive_must_be_a_bool(self):
        self._refused(self._github(archive="yes"),
                      ".archive must be true or false")

    def test_github_files_must_be_a_list(self):
        self._refused(self._github(files="LICENSE"),
                      ".files must be a list")

    def test_github_files_listed_twice_are_refused(self):
        self._refused(
            self._github(files=["LICENSE", "LICENSE"]),
            "twice")

    def test_a_url_archive_must_be_a_bool(self):
        self._refused(
            {"id": "u2", "role": "spec", "url": RFC,
             "archive": "yes"},
            ".archive must be true or false")

    def test_project_must_be_a_list(self):
        self._refused(
            {"id": "x", "role": "self", "project": "a.py"},
            ".project must be a list")

    def test_project_paths_listed_twice_are_refused(self):
        self._refused(
            {"id": "x", "role": "self",
             "project": ["a.py", "a.py"]},
            "twice")


class ExtensionSourcesPassTest(_Base):
    """Queue A refill: the runner's provisioning pass
    itself (runner._extension_sources_pass; coverage run
    40187685363: the whole body on both platforms). The
    tick tests substitute a fake pass, and the wiring
    tests call provision directly, so the real wrapper
    never ran: its contract is the docstring's -- one
    pass in the calling thread, the provision report
    returned, and never a raise: any failure inside is
    logged and comes back None, because a provisioning
    failure must not sink the runner's main loop.
    """

    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())
        self.cfg = {"base_dir": self.base,
                    "transports": ["file"],
                    "extension_sources": {"fetch": True,
                                          "unpinned": True}}

    def test_the_pass_provisions_and_returns_the_report(self):
        report = R._extension_sources_pass(
            self.cfg, self.base,
            fetcher=X.Fetcher(opener=self.opener))
        self.assertIsInstance(report, dict)
        self.assertEqual(
            self.state()["entries"]["up"]["status"], "fetched")

    def test_a_failing_pass_is_none_never_an_exception(self):
        logged = []
        with mock.patch.object(
                R._extsources, "provision",
                side_effect=RuntimeError("provision boom")), \
                mock.patch.object(
                R, "log",
                lambda m, level="INFO": logged.append((level, m))):
            got = R._extension_sources_pass(self.cfg, self.base)
        self.assertIsNone(got)
        self.assertTrue(
            any("pass failed" in m for _lvl, m in logged),
            logged)

    def test_no_sources_module_is_none(self):
        with mock.patch.object(R, "_extsources", None):
            self.assertIsNone(
                R._extension_sources_pass(self.cfg, self.base))


class PinDeclarationProblemsTest(_Base):
    """Queue A refill: pin_declaration's problem legs
    (coverage run 40189608702: 5 lines on both
    platforms). The pin tool's docstring fixes the
    shape: problems are recorded, never raised -- a
    pin that could not be made means the box
    resolves that entry itself. Project entries are
    not pinned at all (their bytes are the build's
    own), a failed archive download is an "archive:"
    problem on an otherwise pinned entry, and a
    failed resolution is a problem with no resolved
    block.
    """

    def _pin(self, decl, routes):
        fetcher = X.Fetcher(opener=FakeOpener(routes))
        tmp = tempfile.mkdtemp()
        try:
            return X.pin_declaration(
                fetcher, X.parse_declaration(decl), tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_project_entries_are_not_pinned(self):
        decl = {"sources_version": 1, "sources": [
            {"id": "code", "role": "self", "license": "MIT",
             "description": "The build's own code.",
             "project": ["runner/extensions/x/x.py"]},
            {"id": "rfc5321", "role": "spec", "url": RFC,
             "description": "SMTP."}]}
        block = self._pin(decl, upstream_routes())
        self.assertNotIn("code", block["entries"])
        self.assertIn("rfc5321", block["entries"])

    def test_a_failed_archive_download_is_a_problem(self):
        routes = upstream_routes()
        routes[ASSET] = URLError("down")
        block = self._pin(upstream_decl(), routes)
        rec = block["entries"]["up"]
        self.assertIn("LICENSE", rec["files"])
        self.assertTrue(any(p.startswith("archive:")
                            for p in rec["problems"]),
                        rec["problems"])
        self.assertNotIn("archive", rec)

    def test_a_failed_resolution_is_a_problem(self):
        block = self._pin(upstream_decl(), {})
        rec = block["entries"]["up"]
        self.assertTrue(rec["problems"])
        self.assertNotIn("files", rec)
        self.assertNotIn("resolved", rec)


class PassLockEdgesTest(unittest.TestCase):
    """Queue A refill: _acquire_pass_lock's give-up
    legs (coverage run 40189608702: 5 lines on both
    platforms). The lock's contract: one pass at a
    time per state root, and a lock that cannot be
    taken is an answer (None -- another pass is
    running, or the root is unusable), never a
    raise. A lock file whose age cannot be read is
    retried once, then given up on, not unlinked
    blind.
    """

    def test_a_lock_that_cannot_be_statted_is_given_up_on(self):
        with tempfile.TemporaryDirectory() as d:
            lock = os.path.join(d, ".pass.lock")
            with open(lock, "w", encoding="utf-8") as fh:
                fh.write("{}")
            real_mtime = os.path.getmtime

            def flaky(path, *a, **kw):
                if os.path.abspath(path) == os.path.abspath(lock):
                    raise OSError("cannot stat")
                return real_mtime(path, *a, **kw)

            with mock.patch.object(os.path, "getmtime", flaky):
                self.assertIsNone(X._acquire_pass_lock(d, 1000.0))
            self.assertTrue(os.path.exists(lock))

    def test_an_unusable_root_answers_none(self):
        with tempfile.TemporaryDirectory() as d:
            afile = os.path.join(d, "afile")
            with open(afile, "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            self.assertIsNone(X._acquire_pass_lock(afile, 1000.0))

    def test_a_free_root_takes_the_lock(self):
        with tempfile.TemporaryDirectory() as d:
            path = X._acquire_pass_lock(d, 1000.0)
            self.assertEqual(path, os.path.join(d, ".pass.lock"))
            with open(path, encoding="utf-8") as fh:
                self.assertIn("pid", json.load(fh))


class ExtractMemberEdgesTest(unittest.TestCase):
    """Queue A refill: extract_archive's member legs
    (coverage run 40189608702: 5 lines on both
    platforms). The extractor's docstring fixes the
    shape: only regular files and directories are
    written -- a directory entry, zip or tar, is
    passed over without being counted as a file or
    a skip; a member the reader cannot materialize
    is counted skipped; and an archive with more
    members than the cap is refused outright.
    """

    def _zip(self, d, members):
        path = os.path.join(d, "a.zip")
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in members:
                zf.writestr(name, data)
        return path

    def test_a_zip_directory_entry_is_not_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._zip(d, [("pkg/", ""),
                                 ("pkg/a.txt", "hi")])
            stats = X.extract_archive(
                path, os.path.join(d, "out"), 1 << 20)
            self.assertEqual(stats["files"], 1)
            self.assertEqual(stats["skipped"], 0)

    def test_a_tar_directory_member_is_not_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                dinfo = tarfile.TarInfo("pkg")
                dinfo.type = tarfile.DIRTYPE
                tf.addfile(dinfo)
                data = b"hi"
                finfo = tarfile.TarInfo("pkg/a.txt")
                finfo.size = len(data)
                tf.addfile(finfo, io.BytesIO(data))
            path = os.path.join(d, "a.tar.gz")
            with open(path, "wb") as fh:
                fh.write(buf.getvalue())
            stats = X.extract_archive(
                path, os.path.join(d, "out"), 1 << 20)
            self.assertEqual(stats["files"], 1)
            self.assertEqual(stats["skipped"], 0)

    def test_more_members_than_the_cap_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._zip(d, [("a", "1"), ("b", "2"),
                                 ("c", "3")])
            with mock.patch.object(X, "MAX_ARCHIVE_MEMBERS", 2):
                with self.assertRaisesRegex(
                        X.SourceError, "more than 2 members"):
                    X.extract_archive(
                        path, os.path.join(d, "out"), 1 << 20)

    def test_a_member_with_no_stream_is_counted_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                for name in ("pkg/a.txt", "pkg/b.txt"):
                    data = b"hi"
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
            path = os.path.join(d, "a.tar.gz")
            with open(path, "wb") as fh:
                fh.write(buf.getvalue())
            real_extract = tarfile.TarFile.extractfile

            def flaky(self, member):
                if member.name.endswith("b.txt"):
                    return None
                return real_extract(self, member)

            with mock.patch.object(
                    tarfile.TarFile, "extractfile", flaky):
                stats = X.extract_archive(
                    path, os.path.join(d, "out"), 1 << 20)
            self.assertEqual(stats["files"], 1)
            self.assertEqual(stats["skipped"], 1)


class FetchArchiveFailuresTest(_Base):
    """Queue A refill: _fetch_archive's budget and
    re-raise legs (coverage run 40187685363: 6 lines
    on both platforms). The archive phase's contract:
    a spent budget refuses before any download, as a
    budget failure; a download failure that is not
    the budget's doing passes through as itself; an
    archive that unpacks past the extraction cap
    passes through too -- unless what is left of the
    budget is what cut it short, in which case the
    failure is named as the budget's.
    """

    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())

    @staticmethod
    def _tgz(members):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    def test_a_spent_budget_refuses_before_downloading(self):
        self.run_pass(policy=self.policy(
            {"extension_sources": {"fetch": True,
                                   "unpinned": True,
                                   "max_mb": 1}}))
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "skipped")
        self.assertIn("the disk budget is spent",
                      entry["detail"])
        self.assertNotIn(ASSET, self.opener.urls())

    def test_a_download_failure_passes_through_as_itself(self):
        self.opener.routes[ASSET] = X.SourceError("weird fetch")
        self.run_pass()
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "partial")
        self.assertEqual(entry["detail"], "archive: weird fetch")

    def test_an_over_expanding_archive_passes_through(self):
        self.opener.routes[ASSET] = self._tgz(
            [("big.bin", b"\0" * (3 << 20))])
        self.run_pass()
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "partial")
        self.assertIn("unpacks past", entry["detail"])
        self.assertNotIn("what is left", entry["detail"])

    def test_an_over_expansion_the_budget_cut_short_is_budget(self):
        import random
        noise = random.Random(20261025).randbytes(150_000)
        self.opener.routes[ASSET] = self._tgz(
            [("zeros.bin", b"\0" * (2900 << 10)),
             ("noise.bin", noise)])
        self.run_pass(policy=self.policy(
            {"extension_sources": {"fetch": True,
                                   "unpinned": True,
                                   "max_mb": 2}}))
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "skipped")
        self.assertIn("unpacks past what is left",
                      entry["detail"])


class ProvisionFailureTest(_Base):
    """Queue A refill: provision's and _run_pass's
    failure legs (coverage run 40187685363: 6 lines
    each on both platforms). The pass contract:
    provisioning never takes the agent down -- bad
    arguments answer the bare report, an uncreatable
    state root is a recorded problem, an unexpected
    failure inside the pass is a recorded problem, and
    per-entry disk failures fail that entry with a
    "local disk" detail and a backoff while the pass
    goes on. An archive whose files landed but which
    itself fails is partial, not failed.
    """

    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())

    def test_bad_arguments_answer_the_bare_report(self):
        rep = X.provision(None, [], {})
        self.assertFalse(rep["ran"])
        rep = X.provision(self.base, [], "not-a-policy")
        self.assertFalse(rep["ran"])

    def test_an_uncreatable_state_root_is_a_problem(self):
        afile = os.path.join(self.tmp, "afile")
        with open(afile, "w", encoding="utf-8") as fh:
            fh.write("not a directory")
        rep = X.provision(afile, [], self.policy())
        self.assertFalse(rep["ran"])
        self.assertTrue(any("cannot create" in p
                            for p in rep["problems"]),
                        rep["problems"])

    def test_a_pass_failure_is_a_problem_never_a_raise(self):
        with mock.patch.object(
                X, "_run_pass",
                side_effect=RuntimeError("inner boom")):
            rep = X.provision(self.base, [target(self.ext)],
                              self.policy(),
                              fetcher=X.Fetcher(
                                  opener=self.opener),
                              now=self.now,
                              log=lambda m, level="INFO":
                              self.logs.append((level, m)))
        self.assertTrue(any("pass failed: inner boom" in p
                            for p in rep["problems"]),
                        rep["problems"])

    def test_an_installed_code_failure_is_logged_not_fatal(self):
        with mock.patch.object(
                X, "_installed_record",
                side_effect=RuntimeError("cannot read code")):
            self.run_pass()
        self.assertTrue(any("installed code" in m
                            for _lvl, m in self.logs),
                        self.logs)
        self.assertEqual(
            self.state()["entries"]["up"]["status"], "fetched")

    def test_a_small_parts_disk_failure_fails_the_entry(self):
        with mock.patch.object(
                X, "_small_parts",
                side_effect=OSError("disk full")):
            self.run_pass()
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "failed")
        self.assertIn("local disk: disk full", entry["detail"])

    def test_an_archive_disk_failure_is_partial_with_files(self):
        with mock.patch.object(
                X, "_fetch_archive",
                side_effect=OSError("disk full")):
            self.run_pass()
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "partial")
        self.assertIn("archive: local disk: disk full",
                      entry["detail"])

    def test_a_transient_archive_is_partial_and_backed_off(self):
        def transient(ctx, work, rec, budget):
            rec["files"] = {"items": {"LICENSE": {}},
                            "problems": [], "transient": True}

        with mock.patch.object(X, "_fetch_archive", transient):
            self.run_pass()
        entry = self.state()["entries"]["up"]
        self.assertEqual(entry["status"], "partial")
        self.assertIn("next_retry_at", entry)


class IsWithheldEdgesTest(unittest.TestCase):
    """Queue A refill: is_withheld's edge legs (coverage
    run 40187685363: 6 lines on both platforms). The
    withholding check fails closed, by its own
    comments: a path that cannot be resolved is
    withheld; a withheld entry that cannot be resolved
    is compared as given, never read as "not withheld".
    Empty inputs are the one open answer: nothing is
    withheld from nothing.
    """

    def test_empty_inputs_are_not_withheld(self):
        self.assertFalse(X.is_withheld("", ["/x"]))
        self.assertFalse(X.is_withheld("/x", []))
        self.assertFalse(X.is_withheld(None, ["/x"]))

    def test_an_unresolvable_path_is_withheld(self):
        with mock.patch.object(
                X, "_real", side_effect=OSError("cannot resolve")):
            self.assertTrue(X.is_withheld("/some/path", ["/w"]))

    def test_non_string_withheld_entries_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.txt")
            self.assertFalse(X.is_withheld(path, [42, None]))
            self.assertTrue(X.is_withheld(path, [42, d]))

    def test_an_unresolvable_entry_compares_as_given(self):
        real = X._real

        def picky(p):
            if p == "/withheld-root":
                raise OSError("cannot resolve")
            return real(p)

        with mock.patch.object(X, "_real", picky):
            self.assertTrue(X.is_withheld(
                "/withheld-root/child.txt", ["/withheld-root"]))


class FetchSourcesRefusalsTest(_Base):
    """Queue A refill: run_fetch_sources' refusal exits
    (coverage run 40187685363: 6 lines on both
    platforms). The foreground command's contract (its
    docstring): asking counts as wanting it, but three
    states still refuse -- the sources module
    unavailable (exit 1), the policy itself invalid
    (exit 2, the problem printed), and another pass
    already running (exit 1).
    """

    def setUp(self):
        super().setUp()
        write_ext(self.ext, upstream_decl())
        self.args = mock.Mock(config=os.path.join(
            self.base, "config.json"))

    def _run(self, cfg):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = R.run_fetch_sources(cfg, self.args)
        return rc, out.getvalue(), err.getvalue()

    def test_no_sources_module_is_exit_1(self):
        with mock.patch.object(R, "_extsources", None):
            rc, _out, err = self._run({"base_dir": self.base})
        self.assertEqual(rc, 1)
        self.assertIn("unavailable", err)

    def test_an_invalid_policy_is_exit_2_and_named(self):
        cfg = {"base_dir": self.base,
               "extension_sources": {"oracle": "sometimes"}}
        rc, _out, err = self._run(cfg)
        self.assertEqual(rc, 2)
        self.assertIn("extension_sources:", err)

    def test_a_busy_pass_is_exit_1(self):
        cfg = {"base_dir": self.base, "transports": ["file"],
               "extension_sources": {"fetch": True,
                                     "unpinned": True}}
        busy = {"busy": True, "outcomes": [], "problems": [],
                "used_bytes": 0, "budget_bytes": 0}
        with mock.patch.object(X, "provision",
                               return_value=busy):
            rc, _out, err = self._run(cfg)
        self.assertEqual(rc, 1)
        self.assertIn("another pass is running", err)


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
        doc = " ".join(self.read("docs", "extend", "extensions.md").split())
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
        self.assertEqual(cfg["extension_sources"], "auto")
        self.assertIn("docs/extend/extensions.md", cfg["_extension_sources"])
        self.assertIn("unpinned", cfg["_extension_sources"])


class LocalFilesEdgesTest(unittest.TestCase):
    """Queue A refill: _local_files' and _tree_bytes'
    remaining legs (coverage run 40189711740: 4 lines
    each). The local-copy walker never follows a link,
    stops at its visit budget however much tree is
    left, and skips a file it cannot size; the byte
    counter answers 0 for an unsizable non-directory
    and skips an unsizable member mid-walk -- a
    misplaced or racing tree costs entries, never the
    pass.
    """

    def test_a_symlink_source_yields_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            real = os.path.join(d, "real")
            os.makedirs(real)
            with open(os.path.join(real, "a.txt"), "w") as fh:
                fh.write("x")
            link = os.path.join(d, "link")
            try:
                os.symlink(real, link)
            except OSError:
                self.skipTest("symlinks unavailable")
            self.assertEqual(list(X._local_files(link)), [])

    def test_the_visit_budget_stops_the_walk(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.txt", "b.txt"):
                with open(os.path.join(d, name), "w") as fh:
                    fh.write("x")
            sub = os.path.join(d, "sub")
            os.makedirs(sub)
            for name in ("c.txt", "e.txt"):
                with open(os.path.join(sub, name), "w") as fh:
                    fh.write("x")
            with mock.patch.object(X, "LOCAL_MAX_VISITS", 2):
                got = [rel for _full, rel in X._local_files(d)]
            self.assertEqual(got, ["a.txt", "b.txt"])

    def test_a_file_that_cannot_be_sized_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.txt", "b.txt"):
                with open(os.path.join(d, name), "w") as fh:
                    fh.write("x")
            real = os.path.getsize

            def flaky(path, *a, **kw):
                if str(path).endswith("b.txt"):
                    raise OSError("gone")
                return real(path, *a, **kw)

            with mock.patch.object(os.path, "getsize", flaky):
                got = [rel for _full, rel in X._local_files(d)]
            self.assertEqual(got, ["a.txt"])

    def test_tree_bytes_unsizable_answers_zero_and_skips(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.txt"), "w") as fh:
                fh.write("12345")
            with open(os.path.join(d, "b.txt"), "w") as fh:
                fh.write("123")
            real = os.path.getsize

            def flaky(path, *a, **kw):
                if str(path).endswith("b.txt"):
                    raise OSError("gone")
                return real(path, *a, **kw)

            with mock.patch.object(os.path, "getsize", flaky):
                self.assertEqual(X._tree_bytes(d), 5)
            with mock.patch.object(os.path, "isfile",
                                   return_value=True), \
                    mock.patch.object(os.path, "getsize",
                                      side_effect=OSError("gone")):
                self.assertEqual(
                    X._tree_bytes(os.path.join(d, "nope")), 0)


class ExtsourcesSmallLegsTest(unittest.TestCase):
    """Queue A refill: extsources' small conversion
    and refusal legs (coverage run 40189711740:
    Fetcher.get_json 828-829, resolve_github 935
    and 998, remote_urls 1008 and 1012,
    owner_policy 674 and 683, manifest_upstream_of
    537 and 550, _clean_targets 1363 and 1368).
    Each is a fail-closed shape: a response that is
    not JSON, a ref that resolves nowhere, a URL
    whose name is not a safe segment, a policy
    override that is not an object or names an
    unknown disclosure, a manifest whose upstream
    block does not validate, and target entries
    that are not usable targets -- all refused or
    degraded, none fatal.
    """

    def test_get_json_refuses_a_non_json_response(self):
        url = "https://api.github.com/repos/o/r"
        fetcher = X.Fetcher(opener=FakeOpener({url: b"not json"}))
        with self.assertRaisesRegex(X.SourceError, "not JSON"):
            fetcher.get_json(url)

    def test_a_named_ref_that_resolves_nowhere_reraises(self):
        class Dead:
            def get_text(self, *a):
                raise X.SourceError("no such ref")

            def get_json(self, *a):
                return []
        with self.assertRaises(X.SourceError):
            X.resolve_github(Dead(), "o/r", ref="some-branch")

    def test_latest_without_a_default_branch_is_refused(self):
        class Empty:
            def get_json(self, url):
                return {} if url.endswith("/repos/o/r") else []

            def get_text(self, *a):
                raise X.SourceError("unused")
        with self.assertRaisesRegex(X.SourceError,
                                    "no default branch"):
            X.resolve_github(Empty(), "o/r", ref="latest")

    def test_remote_urls_shapes(self):
        files, archive = X.remote_urls(
            {"location": "url", "archive": True,
             "url": "https://x.test/a.zip"})
        self.assertEqual((files, archive),
                         ({}, "https://x.test/a.zip"))
        files, archive = X.remote_urls(
            {"location": "url",
             "url": "https://x.test/trailing."})
        self.assertEqual(files,
                         {"document": "https://x.test/trailing."})
        self.assertIsNone(archive)
        files, _a = X.remote_urls(
            {"location": "url", "url": "https://x.test/notes.txt"})
        self.assertEqual(files,
                         {"notes.txt": "https://x.test/notes.txt"})

    def test_owner_policy_refuses_bad_overrides(self):
        pol = X.owner_policy({"extension_sources": {
            "extensions": {"feed": "not-an-object"}}})
        self.assertFalse(pol["valid"])
        pol = X.owner_policy({"extension_sources": {
            "extensions": {"feed": {"oracle": "bogus"}}}})
        self.assertFalse(pol["valid"])

    def test_manifest_upstream_shapes(self):
        self.assertIsNone(X.manifest_upstream_of(None))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "extension.json")
            with open(path, "w") as fh:
                json.dump({"upstream": {"repo": "not a repo",
                                        "ref": "main",
                                        "pin": "a" * 40,
                                        "paths": ["x.py"]}}, fh)
            self.assertIsNone(X.manifest_upstream_of(d))
            with open(path, "w") as fh:
                json.dump({"upstream": {
                    "repo": "https://github.com/o/r",
                    "ref": "main", "pin": "a" * 40,
                    "paths": ["x.py"]}}, fh)
            got = X.manifest_upstream_of(d)
        self.assertEqual(got["github"], "o/r")

    def test_clean_targets_skips_the_unusable(self):
        good = {"kind": "sense", "name": "feed", "dir": "/x"}
        out = X._clean_targets([
            "not-a-dict",
            {"kind": "bogus", "name": "feed", "dir": "/x"},
            {"kind": "sense", "name": "bad name!", "dir": "/x"},
            good, dict(good)])
        self.assertEqual(len(out), 1)
        self.assertEqual(
            (out[0]["kind"], out[0]["name"], out[0]["dir"]),
            ("sense", "feed", "/x"))


class ExtsourcesSmallLegs2Test(unittest.TestCase):
    """Queue A refill, second extsources batch
    (coverage run 40189711740): _regex 285,
    parse_declaration 461, the redirect handler's
    https pass-through 752, _commit_for 912,
    _safe_member 1037, _strip_top 1054,
    load_states 1315, _entry_line 1965, and
    is_withheld's plain inside/outside answers
    2158-2160. Each is the small print of the
    sources contract: shapes refused in the
    owner's face, archive members kept
    portable, states read only under usable
    names, and withheld answers given by the
    resolved path.
    """

    def test_regex_and_declaration_guards(self):
        with self.assertRaises(ValueError):
            X._regex(123, "pattern")
        with self.assertRaises(ValueError):
            X._regex("x" * 201, "pattern")
        self.assertEqual(X._regex("a+", "pattern"), "a+")
        with self.assertRaisesRegex(ValueError,
                                    "must be a JSON object"):
            X.parse_declaration("nope")

    def test_redirect_stays_on_https(self):
        from urllib.request import Request
        handler = X._HttpsOnlyRedirect()
        req = Request("https://a.test/old")
        out = handler.redirect_request(
            req, None, 302, "Found", {},
            "https://b.test/new")
        self.assertEqual(out.full_url, "https://b.test/new")
        with self.assertRaises(X.SourceError):
            handler.redirect_request(
                req, None, 302, "Found", {},
                "http://b.test/new")

    def test_commit_for_refuses_a_non_sha(self):
        class Fetcher:
            def get_text(self, *a):
                return "not-a-sha"

        with self.assertRaisesRegex(X.SourceError,
                                    "did not resolve"):
            X._commit_for(Fetcher(), "o/r", "main")

    def test_safe_member_and_strip_top(self):
        self.assertIsNone(X._safe_member("a\\b.txt"))
        self.assertIsNone(X._safe_member("C:evil"))
        self.assertEqual(X._safe_member("a/b.txt"),
                         ["a", "b.txt"])
        self.assertEqual(X._strip_top([["top", "a"],
                                       ["top", "b"]]), 1)
        self.assertEqual(X._strip_top([["one", "a"],
                                       ["two", "b"]]), 0)

    def test_load_states_skips_unusable_names(self):
        with tempfile.TemporaryDirectory() as d:
            kdir = os.path.join(d, X.STATE_DIRNAME, "sense")
            os.makedirs(os.path.join(kdir, "bad name!"))
            good = os.path.join(kdir, "feed")
            os.makedirs(good)
            with open(os.path.join(good, X.STATE_FILE),
                      "w") as fh:
                json.dump({"state_version": X.STATE_VERSION,
                           "kind": "sense"}, fh)
            states = X.load_states(d)
        self.assertEqual(list(states), [("sense", "feed")])

    def test_entry_line_names_the_branch(self):
        lines = X._entry_line("/b", {
            "origin": {"github": "o/r"},
            "resolved": {"branch": "main",
                         "commit": "a" * 40}})
        self.assertTrue(
            any("o/r (main)" in line for line in lines))

    def test_is_withheld_plain_paths(self):
        with tempfile.TemporaryDirectory() as d:
            held = os.path.join(d, "held")
            os.makedirs(held)
            inside = os.path.join(held, "f.txt")
            with open(inside, "w") as fh:
                fh.write("x")
            outside = os.path.join(d, "free.txt")
            with open(outside, "w") as fh:
                fh.write("x")
            self.assertTrue(X.is_withheld(inside, [held]))
            self.assertFalse(X.is_withheld(outside, [held]))


class LoadDeclarationLegsTest(unittest.TestCase):
    """Queue A refill: load_declaration's quiet legs
    (coverage run 40189711740: lines 504, 513-514).
    The reader never raises: a non-path names no
    declaration, and a declaration file that exists
    but cannot be read comes back as a problem
    naming the failure, not a traceback.
    """

    def test_a_non_path_and_an_unreadable_file(self):
        self.assertEqual(X.load_declaration(None), (None, None))
        self.assertEqual(X.load_declaration(""), (None, None))
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, X.SOURCES_FILE)
            with open(path, "w") as fh:
                fh.write("{}")
            real_open = open

            def refusing(p, *a, **k):
                if str(p) == path:
                    raise OSError("gone")
                return real_open(p, *a, **k)

            with mock.patch("builtins.open", refusing):
                decl, problem = X.load_declaration(td)
        self.assertIsNone(decl)
        self.assertIn("cannot read", problem)


class ExtensionSourcesPolicyTest(unittest.TestCase):
    """Queue A refill: _extension_sources_policy's own
    legs (coverage run 40189711740: lines 4524,
    4529-4531). With the sources module missing the
    policy is None; a problem the pass has not
    already recorded is recorded and announced once,
    with what it means: nothing is fetched and every
    source is withheld until it is fixed.
    """

    def test_no_module_no_policy(self):
        with mock.patch.object(R, "_extsources", None):
            self.assertIsNone(R._extension_sources_policy({}))

    def test_a_new_problem_is_recorded_and_announced(self):
        import types
        fake = types.SimpleNamespace(
            owner_policy=lambda cfg, mo: {"problem": "bad policy"})
        lines = []
        with mock.patch.object(R, "_extsources", fake), \
                mock.patch.dict(R._EXTSOURCES_PASS,
                                {"problem": None}), \
                mock.patch.object(
                    R, "log",
                    lambda m, level="INFO": lines.append(m)):
            policy = R._extension_sources_policy({})
            again = R._extension_sources_policy({})
            recorded = R._EXTSOURCES_PASS["problem"]
        self.assertEqual(policy, {"problem": "bad policy"})
        self.assertEqual(again, {"problem": "bad policy"})
        self.assertEqual(len(lines), 1)
        self.assertIn("bad policy", lines[0])
        self.assertIn("nothing is fetched", lines[0])
        self.assertEqual(recorded, "bad policy")


class ReportExtensionSourcesTest(unittest.TestCase):
    """Queue A refill: _report_extension_sources' four
    outcomes (coverage run 40189711740: lines 4598,
    4601, 4605, 4614). The startup line has exactly
    four shapes: the sources module missing (silence),
    no valid policy (silence), sources on (the fetch
    line, naming the budget and the index), and
    sources off (the off line).
    """

    def _report(self, policy, extsources="present"):
        lines = []
        with mock.patch.object(R, "_extsources",
                               None if extsources is None
                               else X), \
                mock.patch.object(R, "_extension_sources_policy",
                                  return_value=policy), \
                mock.patch.object(
                    R, "log",
                    lambda m, level="INFO": lines.append(m)):
            R._report_extension_sources({}, "/base")
        return lines

    def test_no_module_and_no_policy_are_silent(self):
        self.assertEqual(self._report(None, extsources=None),
                         [])
        self.assertEqual(self._report(None), [])
        self.assertEqual(self._report({"valid": False}), [])

    def test_on_and_off_each_say_their_line(self):
        on = self._report({"valid": True, "enabled": True,
                           "extensions": {}, "fetch": True,
                           "max_bytes": 3 << 20})
        self.assertEqual(len(on), 1)
        self.assertIn("extension sources: on its first run",
                      on[0])
        self.assertIn("budget 3 MB", on[0])
        off = self._report({"valid": True, "enabled": False,
                            "extensions": {}, "fetch": False,
                            "max_bytes": 0})
        self.assertEqual(
            off, ["extension sources: off "
                  "(extension_sources is false)"])


class OracleNoteEdgesTest(unittest.TestCase):
    """Queue A refill: oracle_note's two remaining legs
    (coverage run 40189711740: 4 lines). The function's
    contract is in its docstring -- a few lines for the
    Oracle's context, or "", and never raises: a state
    store that fails to load yields the empty note, and
    more provided sources than the line budget fold
    into a counted trailer rather than a longer note.
    """

    def _states(self, names):
        return {(("sense", n)): {
            "version": "1", "disclosure": "provide",
            "installed": {"path": "/x"}, "entries": {}}
            for n in names}

    def test_an_unloadable_store_is_an_empty_note(self):
        with mock.patch.object(X, "load_states",
                               side_effect=RuntimeError("corrupt")):
            self.assertEqual(X.oracle_note("/base"), "")

    def test_more_sources_than_the_budget_fold_into_a_count(self):
        states = self._states(["alpha", "beta", "gamma"])
        with mock.patch.object(X, "load_states",
                               return_value=states):
            note = X.oracle_note("/base", max_lines=2)
        self.assertTrue(note.startswith("Extension sources:"))
        self.assertTrue(
            note.endswith("- ... 1 more in the index"))
        self.assertEqual(note.count("\n- sense"), 2)


class ReadJsonRefusalLegsTest(unittest.TestCase):
    # Queue A refill: _read_json's over-cap and unreadable
    # returns (lines 215, 217-218). A file bigger than the
    # cap, one whose JSON does not parse, and one that is
    # not UTF-8 all read as None -- never a raise, never a
    # partial value.
    def test_over_cap_malformed_and_non_utf8_all_read_none(self):
        with tempfile.TemporaryDirectory() as d:
            big = os.path.join(d, "big.json")
            with open(big, "w", encoding="utf-8") as fh:
                fh.write('{"a": 1234567890}')
            self.assertIsNone(X._read_json(big, 4))
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("{nope")
            self.assertIsNone(X._read_json(bad, 1024))
            raw = os.path.join(d, "raw.json")
            with open(raw, "wb") as fh:
                fh.write(b"\xff\xfe{}")
            self.assertIsNone(X._read_json(raw, 1024))
            good = os.path.join(d, "good.json")
            with open(good, "w", encoding="utf-8") as fh:
                fh.write('{"a": 1}')
            self.assertEqual(X._read_json(good, 1024), {"a": 1})


class ScanLocalLegsTest(unittest.TestCase):
    # Queue A refill: _scan_local's vanished-file pass-over
    # and its total-cap break (lines 1204-1205, 1207).
    def test_a_file_gone_before_its_stat_is_passed_over(self):
        with tempfile.TemporaryDirectory() as d:
            real = os.path.join(d, "real.txt")
            with open(real, "w", encoding="utf-8") as fh:
                fh.write("here")
            gone = os.path.join(d, "gone.txt")
            with mock.patch.object(
                    X, "_local_files",
                    return_value=[(gone, "gone.txt"),
                                  (real, "real.txt")]):
                out = X._scan_local(d)
            self.assertEqual([rel for _f, rel, _s, _m in out],
                             ["real.txt"])

    def test_the_cap_breaks_the_scan(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.txt", "b.txt"):
                with open(os.path.join(d, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("12345")
            self.assertEqual(X._scan_local(d, cap=0), [])
            self.assertEqual(len(X._scan_local(d, cap=5)), 1)


class InstalledRecordLegsTest(unittest.TestCase):
    # Queue A refill: _installed_record's unhashable-file
    # pass-over (lines 1260-1261) and its in-place stale-copy
    # removal (line 1268).
    def _ext(self, d, files):
        ext = os.path.join(d, "ext")
        os.makedirs(ext)
        for name, body in files.items():
            with open(os.path.join(ext, name), "w",
                      encoding="utf-8") as fh:
                fh.write(body)
        return ext

    def test_a_file_that_cannot_be_hashed_is_left_out(self):
        with tempfile.TemporaryDirectory() as d:
            ext = self._ext(d, {"good.py": "x = 1\n",
                                "bad.py": "y = 2\n"})
            real_sha = X._sha384_file

            def sha(path):
                if path.endswith("bad.py"):
                    raise OSError("gone mid-hash")
                return real_sha(path)

            with mock.patch.object(X, "_sha384_file", sha):
                rec = X._installed_record(
                    os.path.join(d, "base"), d,
                    os.path.join(d, "root"), ext, None)
            self.assertEqual(sorted(rec["files"]), ["good.py"])

    def test_an_in_place_record_removes_the_stale_copy(self):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "base")
            ext = self._ext(base, {"one.py": "x = 1\n"})
            ext_root = os.path.join(d, "root")
            copy_dir = os.path.join(ext_root, "installed")
            os.makedirs(copy_dir)
            with open(os.path.join(copy_dir, "stale.py"), "w",
                      encoding="utf-8") as fh:
                fh.write("old")
            rec = X._installed_record(base, d, ext_root, ext, None)
            self.assertFalse(rec["copied"])
            self.assertIn("path", rec)
            self.assertFalse(os.path.exists(copy_dir))


class SourcesPolicyNamingTest(unittest.TestCase):
    """Queue D1 (the documented-default hunt, refilled):
    extension_sources reached the docs after the defaults
    registry was built, so its Decision 1 behavior is
    pinned here instead. A malformed value fails closed in
    owner_policy (PolicyTest); at the runner seam it is
    also NAMED -- one WARN per distinct problem, never a
    repeat while the problem is unchanged, and named again
    after a fix lets it change."""

    def setUp(self):
        self._saved = R._EXTSOURCES_PASS.get("problem")
        R._EXTSOURCES_PASS["problem"] = None

    def tearDown(self):
        R._EXTSOURCES_PASS["problem"] = self._saved

    def test_a_malformed_setting_is_named_once_per_problem(self):
        lines = []

        def log(msg, level="INFO"):
            lines.append((level, msg))

        bad1 = {"extension_sources": "yes"}
        bad2 = {"extension_sources": {"oracle": "share"}}
        with mock.patch.object(R, "log", log):
            pol = R._extension_sources_policy(bad1)
            self.assertFalse(pol["valid"])
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0][0], "WARN")
            self.assertIn("extension_sources", lines[0][1])
            self.assertIn("nothing is fetched", lines[0][1])
            # The same problem again is not re-named.
            R._extension_sources_policy(bad1)
            self.assertEqual(len(lines), 1)
            # A different problem is a new naming.
            pol = R._extension_sources_policy(bad2)
            self.assertFalse(pol["valid"])
            self.assertEqual(len(lines), 2)
            # A fixed setting names nothing, and returning
            # to the first problem names it again.
            pol = R._extension_sources_policy({})
            self.assertTrue(pol["valid"])
            self.assertEqual(len(lines), 2)
            R._extension_sources_policy(bad1)
            self.assertEqual(len(lines), 3)


class InspectUnavailableTest(unittest.TestCase):
    """Queue A (coverage map, run_inspect): when the sources
    or review module failed to import, --inspect says so on
    stderr and exits 1 instead of crashing -- the defensive
    import's whole point."""

    def _inspect(self, which, global_name):
        args = mock.Mock(inspect=which, config=None)
        err = io.StringIO()
        with mock.patch.object(R, global_name, None), \
                redirect_stderr(err):
            code = R.run_inspect({"base_dir": tempfile.mkdtemp()},
                                 args)
        return code, err.getvalue()

    def test_inspect_sources_without_the_module(self):
        code, err = self._inspect("sources", "_extsources")
        self.assertEqual(code, 1)
        self.assertIn("extension sources", err)
        self.assertIn("unavailable", err)

    def test_inspect_review_without_the_module(self):
        code, err = self._inspect("review", "_extreview")
        self.assertEqual(code, 1)
        self.assertIn("extension review", err)
        self.assertIn("unavailable", err)


class StatusShapeTest(unittest.TestCase):
    """extsources.status against recorded states of wrong shape.

    status() documents "Never raises" -- it backs
    `runner --inspect sources`, whose branch calls it
    unguarded. load_states admits any state file that is a
    dict at state_version 1; the shape of its members is
    not checked there.
    """

    def _status_with_state(self, state):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        folder = os.path.join(tmp, X.STATE_DIRNAME, "sense", "demo")
        os.makedirs(folder)
        with open(os.path.join(folder, X.STATE_FILE), "w") as f:
            json.dump(state, f)
        return X.status(tmp)

    def test_a_well_formed_state_is_reported(self):
        out = self._status_with_state({
            "state_version": 1, "version": "1.0", "active": True,
            "installed": {"path": "/p"},
            "entries": {"e1": {"role": "code", "status": "ok"}}})
        self.assertEqual(len(out["extensions"]), 1)
        ext = out["extensions"][0]
        self.assertEqual(ext["installed"], "/p")
        self.assertEqual(ext["entries"]["e1"]["role"], "code")

    # Q44: status() raised AttributeError on these two shapes;
    # the members are now read for their shape and reported blank.
    def test_entries_recorded_as_a_list_do_not_raise(self):
        out = self._status_with_state({
            "state_version": 1, "entries": ["x"]})
        self.assertEqual(len(out["extensions"]), 1)

    # Q44: as above, for the installed member.
    def test_installed_recorded_as_a_list_does_not_raise(self):
        out = self._status_with_state({
            "state_version": 1, "installed": ["x"]})
        self.assertEqual(len(out["extensions"]), 1)


if __name__ == "__main__":
    unittest.main()
