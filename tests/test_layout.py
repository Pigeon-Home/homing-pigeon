#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""The tree's layout: what the root holds, and no path to a retired
folder anywhere in the living tree.

AGENTS.md, "Where things live", is the map. The root keeps the
manuals, pyproject.toml, and six folders (runner, extensions, tests,
docs, assets, tools) beside .github/ and .gitignore. The folders and
files below were moved, with no shims, so a new path written
against the old layout is a bug this file names before a test trips
over the missing file.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Retired root entry -> where it lives now.
RETIRED = {
    "examples": "extensions/",
    "cloud": "runner/cloud/",
    "hardening": "docs/hardening/",
    "docker": ".github/docker/",
    "Dockerfile": ".github/docker/Dockerfile",
    ".dockerignore": ".github/docker/Dockerfile.dockerignore",
    ".gitattributes": "extensions/.gitattributes",
    "requirements-ci.txt": ".github/requirements-ci.txt",
    "pyrefly.toml": "[tool.pyrefly] in pyproject.toml",
    "CONTRIBUTING.md": "docs/CONTRIBUTING.md",
}

# A path into a retired folder, written the ways the tree writes paths.
_EDGE = r"(?<![\w./\\-])"
STALE = [
    (re.compile(r"examples/extensions"), "extensions/"),
    (re.compile(r"[\"']examples[\"'],\s*[\"']extensions[\"']"),
     '"extensions"'),
    (re.compile(_EDGE + r"cloud/send_"), "runner/cloud/"),
    (re.compile(r"(?<![\w.])cloud\.send_(job|dtls)\b"), "runner.cloud"),
    (re.compile(_EDGE + r"tools/\w+\.(py|sh)\b"), ".github/tools/"),
    (re.compile(_EDGE + r"hardening/(systemd|apparmor|selinux|README|windows)"),
     "docs/hardening/"),
    (re.compile(_EDGE + r"docker/(entrypoint|minimal-userland)"),
     ".github/docker/"),
    # pip's -c/-r and a path string; prose may name the file
    (re.compile(r'(?:-[cr]\s+|(?<!"\.github", )["\'])requirements-ci\.txt'),
     ".github/requirements-ci.txt"),
    # os.path.join(ROOT, "tools", ...) and its kin
    (re.compile(r'(?<!"\.github", )(?<=, )["\']tools["\'](?=\s*[,)])'),
     '".github", "tools"'),
    (re.compile(r'(?<!"runner", )(?:(?<=, )|(?<=join\())["\']cloud["\']'
                r'(?=\s*[,)])'), '"runner", "cloud"'),
    (re.compile(r'(?<!"docs", )(?<=, )["\']hardening["\'](?=\s*[,)])'),
     '"docs", "hardening"'),
]

# History is kept as it was written; vendored upstream bytes are pinned.
_SKIP_DIRS = {".git", "__pycache__", "mutants", "build", "dist",
              ".hypothesis", ".mypy_cache", ".ruff_cache"}
_SKIP_PREFIXES = ("docs/archive/", "docs/reports/",
                  "tools/airgap/archive/")
_SKIP_FILES = {"CHANGELOG.md", "tests/test_layout.py"}
_TEXT = (".py", ".md", ".sh", ".yml", ".yaml", ".toml", ".json", ".txt",
         ".cmd", ".ps1", ".cfg", ".ini", ".te", ".service")


def _living_files():
    for dirpath, dirnames, filenames in os.walk(REPO):
        rel_dir = os.path.relpath(dirpath, REPO).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in _SKIP_DIRS
            and not (rel_dir.startswith("extensions/")
                     and d in ("upstream", "provenance")))
        if any(rel_dir.startswith(p) for p in _SKIP_PREFIXES):
            continue
        for name in sorted(filenames):
            rel = rel_dir + name
            if rel in _SKIP_FILES:
                continue
            if name.endswith(_TEXT) or name in ("Dockerfile",):
                yield rel


class RootLayoutTest(unittest.TestCase):
    def test_retired_root_entries_are_gone(self):
        for name, now in sorted(RETIRED.items()):
            with self.subTest(name=name):
                self.assertFalse(
                    os.path.lexists(os.path.join(REPO, name)),
                    "%s is back at the root; it lives at %s now "
                    "(AGENTS.md, 'Where things live')" % (name, now))

    def test_ci_scripts_stay_out_of_the_root_tools(self):
        # The root tools/ is the agents' work areas (tools/airgap/).
        # The build and CI scripts are .github/tools/; one landing
        # back beside the work areas is a stale path in the making.
        ci = os.path.join(REPO, ".github", "tools")
        for name in sorted(os.listdir(ci)):
            if name.startswith(("_", ".")):
                continue
            with self.subTest(name=name):
                self.assertFalse(
                    os.path.lexists(os.path.join(REPO, "tools", name)),
                    "tools/%s is a CI script; it lives in .github/tools/"
                    % name)

    def test_the_moved_homes_exist(self):
        for rel in ("extensions", "runner/cloud/send_job.py",
                    ".github/tools", "docs/hardening",
                    ".github/docker/Dockerfile",
                    ".github/requirements-ci.txt",
                    "extensions/.gitattributes",
                    "docs/CONTRIBUTING.md"):
            with self.subTest(path=rel):
                self.assertTrue(os.path.exists(
                    os.path.join(REPO, *rel.split("/"))), rel)


class NoStalePathTest(unittest.TestCase):
    def test_no_living_file_names_a_retired_path(self):
        found = []
        for rel in _living_files():
            try:
                with open(os.path.join(REPO, *rel.split("/")),
                          encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for pat, now in STALE:
                for m in pat.finditer(text):
                    line = text.count("\n", 0, m.start()) + 1
                    found.append("%s:%d: %r (now %s)"
                                 % (rel, line, m.group(0), now))
        self.assertEqual(found, [],
                         "paths into retired folders; see AGENTS.md, "
                         "'Where things live':\n" + "\n".join(found[:40]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
