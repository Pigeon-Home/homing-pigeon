"""Pins on the app store packaging drafts.

The drafts in packaging/ carry two decisions a later editor must
not undo by accident. The Snap package asks for classic
confinement, because strict confinement cannot hold a runner that
executes the operator's own commands on the host with the host's
interpreters, confining each job with bubblewrap as it goes; the
reasoning stands in docs/steady/design/app-stores-design.md. And
the MSIX manifest's identity values are placeholders until
Partner Center issues the real ones from the conductor's account,
so a real looking identity in the draft would mean values that
did not come from Partner Center. These tests read the drafts as
text and as XML and hold those lines. The drafts themselves are
not built or submitted by anything here.
"""

import os
import re
import unittest
import xml.etree.ElementTree as ET


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _read(rel):
    with open(os.path.join(_root(), rel), encoding="utf-8") as fh:
        return fh.read()


SNAP = os.path.join("packaging", "snap", "snapcraft.yaml")
MSIX = os.path.join("packaging", "msix", "Package.appxmanifest")
DOC = os.path.join("docs", "steady", "design", "app-stores-design.md")


def _top_level(text, key):
    m = re.search(r"^%s:\s*(\S+)\s*$" % re.escape(key), text, re.M)
    return m.group(1) if m else None


class SnapDraftTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SNAP)

    def test_marked_as_a_draft(self):
        self.assertIn("DRAFT", self.text[:1200])

    def test_name_is_the_store_name(self):
        self.assertEqual("homing-pigeon", _top_level(self.text, "name"))

    def test_base_is_core24(self):
        self.assertEqual("core24", _top_level(self.text, "base"))

    def test_grade_is_stable(self):
        self.assertEqual("stable", _top_level(self.text, "grade"))

    def test_confinement_is_classic(self):
        self.assertEqual("classic", _top_level(self.text, "confinement"))

    def test_confinement_is_never_strict_or_devmode(self):
        self.assertIsNone(re.search(
            r"^confinement:\s*(strict|devmode)\s*$", self.text, re.M))

    def test_runner_is_a_daemon(self):
        self.assertRegex(self.text, r"(?m)^\s+daemon:\s*simple\s*$")

    def test_console_script_apps_are_exposed(self):
        for app in ("homing-pigeon-install", "homing-pigeon-send-job",
                    "homing-pigeon-auth", "homing-pigeon-host"):
            self.assertRegex(self.text, r"(?m)^  %s:\s*$" % app)

    def test_part_bundles_python_and_bubblewrap(self):
        self.assertRegex(self.text, r"(?m)^\s+plugin:\s*python\s*$")
        self.assertIn("- python3-venv", self.text)
        self.assertIn("- bubblewrap", self.text)
        self.assertIn("- certifi", self.text)


class MsixDraftTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tree = ET.fromstring(_read(MSIX))

    def _all(self, local):
        return [el for el in self.tree.iter()
                if el.tag.rsplit("}", 1)[-1] == local]

    def test_identity_values_are_placeholders(self):
        (identity,) = self._all("Identity")
        for attr in ("Name", "Publisher", "PublisherDisplayName"):
            self.assertIn("PLACEHOLDER", identity.get(attr, ""), attr)

    def test_run_full_trust_is_declared(self):
        names = [el.get("Name") for el in self._all("Capability")]
        self.assertIn("runFullTrust", names)

    def test_targets_desktop(self):
        fams = [el.get("Name") for el in self._all("TargetDeviceFamily")]
        self.assertIn("Windows.Desktop", fams)

    def test_version_is_four_part(self):
        (identity,) = self._all("Identity")
        self.assertRegex(identity.get("Version", ""), r"^\d+\.\d+\.\d+\.\d+$")


class DesignNotesTest(unittest.TestCase):

    def test_notes_exist_and_name_both_stores(self):
        text = _read(DOC)
        self.assertIn("Snap Store", text)
        self.assertIn("Microsoft Store", text)

    def test_notes_record_the_owner_only_steps(self):
        self.assertIn("Owner only", _read(DOC))

    def test_notes_give_the_confinement_verdict(self):
        self.assertIn("Strict confinement cannot hold the runner",
                      _read(DOC))


if __name__ == "__main__":
    unittest.main()
