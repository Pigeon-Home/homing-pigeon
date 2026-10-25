"""Evergreen docs must not hardcode the current product version.

A procedure that says "type a title like `Version 3.7.28`" is
correct only until the next tag lands; then it is quietly wrong
forever (field catch, 2026-10-18: the release procedure in
docs/use/runbook.md carried the then-current version as its example).
Evergreen docs use placeholders (X.Y.Z) and point at
pyproject.toml for the number. Dated records are exempt by
design: CHANGELOG.md, docs/archive/, the dated reports under
docs/reports/, and the IETF draft under docs/ietf/ are supposed
to carry the versions they describe.
"""

import os
import tomllib
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _current_version():
    with open(os.path.join(_root(), "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _evergreen_docs():
    root = _root()
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        parts = set(rel.split(os.sep))
        if ".git" in parts or "__pycache__" in parts:
            dirnames[:] = []
            continue
        # Dated reports under docs/reports/ are snapshots of a
        # measured run, like the archive: exempt, not evergreen.
        if parts & {"archive", "ietf", "reports"}:
            dirnames[:] = []
            continue
        for name in filenames:
            if name.endswith(".md") and name != "CHANGELOG.md":
                found.append(os.path.join(dirpath, name))
    # The two logs cite releases by number the way the CHANGELOG
    # does: the questions file records which release applied an
    # answer, the standing orders' ledger which release proved an
    # item. Records, not evergreen prose.
    logs = {os.path.join(root, "docs", "use", "questions.md"),
            os.path.join(root, "docs", "project",
                         "campaign-standing-orders.md")}
    return [p for p in found if p not in logs]


class NoVersionRotTest(unittest.TestCase):
    def test_scan_is_not_vacuous(self):
        self.assertGreater(len(_evergreen_docs()), 10)

    def test_current_version_appears_in_no_evergreen_doc(self):
        version = _current_version()
        offenders = []
        for path in _evergreen_docs():
            with open(path, encoding="utf-8") as fh:
                if version in fh.read():
                    offenders.append(os.path.relpath(path, _root()))
        self.assertEqual([], offenders,
                         "current version %s hardcoded in evergreen "
                         "docs (use an X.Y.Z placeholder): %s"
                         % (version, offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
