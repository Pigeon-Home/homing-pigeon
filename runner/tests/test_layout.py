#!/usr/bin/env python3
# Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""The tree's layout: what the root holds, and no path to a retired
folder anywhere in the living tree.

AGENTS.md, "Where things live", is the map. The root keeps the
manuals, pyproject.toml, and three folders (runner, docs, assets)
beside .github/ and .gitignore. The folders and
files below were moved, with no shims, so a new path written
against the old layout is a bug this file names before a test trips
over the missing file.
"""
import os
import re
import unittest

# This file lives in runner/tests/: the tree is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# The runner modules, by role folder (runner/<group>/<module>.py).
_ROLES = {
    "oracle": "opinion learning review remediation detection dri senses "
              "resources personal_docs",
    "wire": "transports mailbox dtlsproto protocol_v2 jobcrypto oauth "
            "verify board platformcard",
    "guard": "security sandbox confval textutil",
    "ops": "install setup extensions extsources harness local_test "
           "posture auditreport winlog",
}
_MODULES = "|".join(m for ms in _ROLES.values() for m in ms.split())

# Retired root entry -> where it lives now.
RETIRED = {
    "examples": "runner/extensions/",
    "extensions": "runner/extensions/",
    "cloud": "runner/cloud/",
    "cloudflare": "runner/cloud/queues-worker/",
    "hardening": "docs/security/hardening/",
    "docker": ".github/docker/",
    "Dockerfile": ".github/docker/Dockerfile",
    ".dockerignore": ".github/docker/Dockerfile.dockerignore",
    ".gitattributes": "runner/extensions/.gitattributes",
    "requirements-ci.txt": ".github/requirements-ci.txt",
    "pyrefly.toml": "[tool.pyrefly] in pyproject.toml",
    "CONTRIBUTING.md": "docs/CONTRIBUTING.md",
    "CHANGELOG.md": "docs/CHANGELOG.md",
    "tests": "runner/tests/",
    "tools": "runner/tools/ (the CI scripts), runner/tests/airgap/ (the work area)",
    ".github/tools": "runner/tools/",
    "topaz": "runner/tests/airgap/",
}

# A path into a retired folder, written the ways the tree writes paths.
_EDGE = r"(?<![\w./\\-])"
STALE = [
    # a runner module at the top of runner/ instead of its role folder
    (re.compile(_EDGE + r"runner/(?:" + _MODULES + r")\.py\b"),
     "runner/<oracle|wire|guard|ops>/<module>.py"),
    (re.compile(r"(?<![\w.])runner\.(?:" + _MODULES + r")\b(?!\.py)"),
     "runner.<oracle|wire|guard|ops>.<module>"),
    (re.compile(r"examples/extensions"), "runner/extensions/"),
    (re.compile(r"[\"']examples[\"'],\s*[\"']extensions[\"']"),
     '"runner", "extensions"'),
    # the tree's shipped extensions, joined from the repo root
    (re.compile(r"(?:\b(?:REPO|ROOT|_ROOT|_REPO)\s*,\s*|_root\(\)\s*,\s*)"
                r"[\"']extensions[\"']"), '"runner", "extensions"'),
    (re.compile(_EDGE + r"cloud/send_"), "runner/cloud/"),
    (re.compile(r"(?<![\w.])cloud\.send_(job|dtls)\b"), "runner.cloud"),
    (re.compile(_EDGE + r"tools/\w+\.(py|sh)\b"), "runner/tools/"),
    (re.compile(r"\.github/tools\b"), "runner/tools/"),
    (re.compile(r'["\']\.github["\'],\s*["\']tools["\']'),
     '"runner", "tools"'),
    (re.compile(_EDGE + r"hardening/(systemd|apparmor|selinux|README|windows)"),
     "docs/security/hardening/"),
    (re.compile(_EDGE + r"docker/(entrypoint|minimal-userland)"),
     ".github/docker/"),
    # the FAQ moved to the root (the owner's own page, 2026-10-26)
    (re.compile(_EDGE + r"docs/use/faq\.md\b"), "FAQ.md"),
    # pip's -c/-r and a path string; prose may name the file
    (re.compile(r'(?:-[cr]\s+|(?<!"\.github", )["\'])requirements-ci\.txt'),
     ".github/requirements-ci.txt"),
    # os.path.join(ROOT, "tools", ...) and its kin
    (re.compile(r'(?<!"runner", )(?<=, )["\']tools["\'](?=\s*[,)])'),
     '"runner", "tools"'),
    (re.compile(r'(?<!"runner", )(?:(?<=, )|(?<=join\())["\']cloud["\']'
                r'(?=\s*[,)])'), '"runner", "cloud"'),
    (re.compile(r'(?<!"docs", )(?<!"security", )(?<=, )["\']hardening["\'](?=\s*[,)])'),
     '"docs", "security", "hardening"'),
    # the suite: a file path, a module id, a discovery start, a join
    (re.compile(_EDGE + r"tests/(test_\w+\.py|defaults_registry|conftest"
                r"|security_parity|archive/|airgap/)"), "runner/tests/"),
    (re.compile(r"(?<![\w./-])tests\.(test_\w+|defaults_registry"
                r"|security_parity)\b"), "runner.tests."),
    (re.compile(r"(?:-s|--start-dir|--start-directory)\s+tests\b(?!/)"),
     "-s runner/tests"),
    (re.compile(r'(?<!"runner", )(?<=, )["\']tests["\'](?=\s*[,)])'),
     '"runner", "tests"'),
]

# History is kept as it was written; vendored upstream bytes are pinned.
_SKIP_DIRS = {".git", "__pycache__", "mutants", "build", "dist",
              ".hypothesis", ".mypy_cache", ".ruff_cache"}
_SKIP_PREFIXES = ("docs/archive/", "docs/reports/",
                  "runner/tests/airgap/archive/")
_SKIP_FILES = {"docs/CHANGELOG.md", "runner/tests/test_layout.py"}
_TEXT = (".py", ".md", ".sh", ".yml", ".yaml", ".toml", ".json", ".txt",
         ".cmd", ".ps1", ".cfg", ".ini", ".te", ".service")


def _living_files():
    for dirpath, dirnames, filenames in os.walk(REPO):
        rel_dir = os.path.relpath(dirpath, REPO).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in _SKIP_DIRS
            and not (rel_dir.startswith("runner/extensions/")
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

    def test_doc_names_are_lowercase_kebab(self):
        """Case-only renames break on macOS/Windows checkouts; one rule
        for docs: lowercase-kebab, except the root conventions and
        historical records."""
        import subprocess
        out = subprocess.run(["git", "ls-files", "docs"], cwd=REPO,
                             capture_output=True, text=True).stdout.split()
        skip = ("docs/archive/", "docs/reports/", "docs/ietf/",
                "docs/design/idea321/", "docs/security/hardening/",
                "docs/specimens/")
        bad = [f for f in out if f.endswith(".md")
               and not f.startswith(skip)
               and os.path.basename(f) not in ("CHANGELOG.md", "CONTRIBUTING.md")
               and os.path.basename(f) != os.path.basename(f).lower()]
        self.assertEqual(bad, [])

    def test_the_moved_homes_exist(self):
        for rel in ("runner/extensions", "runner/cloud/send_job.py",
                    "runner/tools", "docs/security/hardening",
                    ".github/docker/Dockerfile",
                    ".github/requirements-ci.txt",
                    "runner/extensions/.gitattributes",
                    "docs/CONTRIBUTING.md", "docs/CHANGELOG.md",
                    "runner/tests/__init__.py", "runner/tests/airgap"):
            with self.subTest(path=rel):
                self.assertTrue(os.path.exists(
                    os.path.join(REPO, *rel.split("/"))), rel)


class RunnerRootTest(unittest.TestCase):
    def test_runner_holds_the_entry_script_and_folders(self):
        allowed = {"runner.py", "__init__.py", "_version.py",
                   "config.example.json"}
        root = os.path.join(REPO, "runner")
        files = {n for n in os.listdir(root)
                 if os.path.isfile(os.path.join(root, n))}
        self.assertEqual(files - allowed, set(),
                         "a module at the top of runner/; it belongs in "
                         "oracle/, wire/, guard/ or ops/")

    def test_every_module_is_in_its_role_folder(self):
        for group, names in sorted(_ROLES.items()):
            for name in names.split():
                with self.subTest(module=name):
                    self.assertTrue(os.path.isfile(os.path.join(
                        REPO, "runner", group, name + ".py")), name)


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
