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
ROOT_SNAP = os.path.join("snap", "snapcraft.yaml")
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

    def test_adopt_info_names_the_runner_part(self):
        # The snap carries no version of its own; adopt-info is
        # the promise that the runner part supplies it.
        self.assertEqual("runner", _top_level(self.text, "adopt-info"))
        self.assertIsNone(_top_level(self.text, "version"))

    def test_part_sets_the_version_adopt_info_reads(self):
        # The 2026-11-20 build spike's finding: Snapcraft adopts
        # a part's metadata only through parse-info or a craftctl
        # set call, and the draft had neither, so a build would
        # have failed at the prime step for want of a version.
        # The part now sets it in override-build, after the
        # plugin's own build step runs.
        self.assertIn("craftctl default", self.text)
        self.assertIn("craftctl set version=", self.text)

    def test_version_comes_from_the_installed_metadata(self):
        # The version is read from the metadata pip installed
        # for the project itself, never from a second copy of
        # the number typed into the packaging.
        self.assertIn("importlib.metadata", self.text)
        self.assertIn("pigeon-home-runner", self.text)

    def test_part_source_resolves_to_the_tree_root(self):
        # The runner part's source is resolved by craft-parts
        # from the folder this file sits in, packaging/snap, so
        # the line must climb exactly 2 levels to the tree root,
        # the folder holding pyproject.toml. The first real
        # build (2026-11-20, on the San Francisco rig) found the
        # draft 1 level too deep: the part pulled the folder
        # above the tree as its source, no pyproject.toml was
        # found where the plugin looked, the project was never
        # installed, and the adopted version came out empty.
        m = re.search(r"(?m)^\s+source:\s*(\S+)\s*$", self.text)
        self.assertIsNotNone(m)
        snap_dir = os.path.join(_root(), "packaging", "snap")
        resolved = os.path.realpath(os.path.join(snap_dir, m.group(1)))
        self.assertEqual(os.path.realpath(_root()), resolved)
        self.assertTrue(os.path.isfile(
            os.path.join(resolved, "pyproject.toml")))

    def test_stage_packages_name_the_interpreter_closure(self):
        # The interpreter closure is named package by package,
        # not left to python3-venv's dependency closure alone.
        # The first real build ran in destructive mode on a
        # working host, where the stage fetch skips the packages
        # the host already has installed; the host's own Python
        # meant the venv closure never entered the payload, and
        # the build died with "No suitable Python interpreter
        # found, giving up". A package named explicitly in
        # stage-packages is downloaded either way.
        m = re.search(r"(?ms)^\s+stage-packages:\s*\n"
                      r"((?:\s+- [^\n]*\n)+)", self.text)
        self.assertIsNotNone(m)
        staged = [line.strip() for line in m.group(1).splitlines()]
        for pkg in ("python3.12", "python3.12-minimal",
                    "libpython3.12-stdlib", "libpython3.12-minimal"):
            self.assertIn("- " + pkg, staged)


class SnapRootLayoutTest(unittest.TestCase):
    # The twin at snap/snapcraft.yaml exists for Canonical's
    # build service, which discovers the packaging only at the
    # tree root (/.snapcraft.yaml, /snapcraft.yaml or
    # /snap/snapcraft.yaml) and cannot see the packaging folder's
    # copy. The owner directed this one root placement on
    # 2026-11-20 ("Finish Ubuntu"), bending the no new root
    # files rule this once. The twin must build the same snap:
    # same name, base and confinement as the packaging copy,
    # with its part source climbing exactly 1 level from snap/
    # to the tree root.

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ROOT_SNAP)
        cls.packaging_text = _read(SNAP)

    def test_root_snap_file_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(_root(), ROOT_SNAP)))

    def test_root_snap_name_is_the_store_name(self):
        self.assertEqual("homing-pigeon", _top_level(self.text, "name"))

    def test_root_snap_part_source_resolves_to_the_tree_root(self):
        m = re.search(r"(?m)^\s+source:\s*(\S+)\s*$", self.text)
        self.assertIsNotNone(m)
        snap_dir = os.path.join(_root(), "snap")
        resolved = os.path.realpath(os.path.join(snap_dir, m.group(1)))
        self.assertEqual(os.path.realpath(_root()), resolved)
        self.assertTrue(os.path.isfile(
            os.path.join(resolved, "pyproject.toml")))

    def test_root_snap_confinement_is_classic(self):
        self.assertEqual("classic", _top_level(self.text, "confinement"))

    def test_root_snap_agrees_with_the_packaging_copy(self):
        for key in ("name", "base", "confinement"):
            self.assertEqual(_top_level(self.packaging_text, key),
                             _top_level(self.text, key), key)


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

    def test_readiness_page_records_the_build_spike(self):
        text = _read(os.path.join("docs", "steady", "project",
                                  "snap-store-readiness.md"))
        self.assertIn("The build spike, 2026-11-20", text)
        self.assertIn("18 checks", text)


if __name__ == "__main__":
    unittest.main()
