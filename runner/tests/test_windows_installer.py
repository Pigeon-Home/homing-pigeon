#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Pins on the one-directory Windows build and its installer draft.

The Microsoft Store's unpackaged route (policy 10.2.9) takes a
single installer .exe, and an installer is compiled from a
laid-out tree. The build-windows-onedir job in
.github/workflows/build.yml freezes that tree, and the draft
Inno Setup script at packaging/windows/homing-pigeon.iss is
what compiles it. The reasoning stands in
docs/steady/design/app-stores-design.md.

These tests read the three files as text and hold the lines a
later editor must not undo by accident: the onedir freeze is
the onefile freeze with only the layout changed (the same
hidden imports and data, line for line), its artifact stays
out of the release set, the installer lays the tree into a
versioned folder and seeds the config without overwriting
one, and the startup task it registers is the one
runner/ops/install.py registers today, the same name, the
same trigger, the same account, the same command. Nothing
here builds, compiles or submits anything.
"""

import fnmatch
import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _read(rel):
    with open(os.path.join(_root(), rel), encoding="utf-8") as fh:
        return fh.read()


BUILD = os.path.join(".github", "workflows", "build.yml")
ISS = os.path.join("packaging", "windows", "homing-pigeon.iss")
INSTALL = os.path.join("runner", "ops", "install.py")
DOC = os.path.join("docs", "steady", "design", "app-stores-design.md")


def _job_block(workflow, job):
    m = re.search(r"^  %s:\n(.*?)(?=^  [a-z0-9][a-z0-9_-]*:|\Z)"
                  % re.escape(job), workflow, re.M | re.S)
    assert m, "no %s job in build.yml" % job
    return m.group(1)


def _pyinstaller_lines(block):
    return [ln.strip() for ln in block.splitlines()
            if ln.strip().startswith("- run: pyinstaller")]


class OnedirJobTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workflow = _read(BUILD)
        cls.block = _job_block(cls.workflow, "build-windows-onedir")

    def test_the_job_is_a_windows_leg_with_checkout_only_grants(self):
        self.assertIn("runs-on: windows-latest", self.block)
        self.assertRegex(self.block,
                         r"permissions:\n      contents: read\n")

    def test_the_job_runs_under_the_legs_conditions(self):
        for output in ("corpus_only", "docs_only", "promote"):
            self.assertIn("needs.scope.outputs.%s != 'true'" % output,
                          self.block)

    def test_both_programs_freeze_onedir_and_nothing_freezes_onefile(self):
        lines = _pyinstaller_lines(self.block)
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertIn("--onedir", line)
            self.assertNotIn("--onefile", line)
        named = {ln.split("--name ", 1)[1].split(" ", 1)[0]
                 for ln in lines}
        self.assertEqual(named, {"homing-pigeon", "install"})

    def test_the_onedir_lines_are_the_onefile_lines_with_the_mode_swapped(self):
        win = _job_block(self.workflow, "build-windows")
        for target in ("runner/runner.py", "runner/ops/install.py"):
            theirs = [ln for ln in _pyinstaller_lines(win)
                      if target in ln]
            ours = [ln for ln in _pyinstaller_lines(self.block)
                    if target in ln]
            self.assertEqual(len(theirs), 1, target)
            self.assertEqual(len(ours), 1, target)
            self.assertEqual(
                ours[0],
                theirs[0].replace("pyinstaller --onefile",
                                  "pyinstaller --onedir", 1),
                "the %s freeze drifted from the onefile line "
                "by more than the layout" % target)

    def test_tools_come_from_the_pin_file_with_certifi(self):
        self.assertIn(
            "pip install -c .github/requirements-ci.txt "
            "pyinstaller certifi", self.block)

    def test_the_smoke_runs_the_frozen_pair(self):
        for exe in (r"dist\homing-pigeon\homing-pigeon.exe",
                    r"dist\install\install.exe"):
            self.assertIn(exe + " --help", self.block)
            self.assertIn(exe + " --version", self.block)

    def test_the_package_is_the_versioned_tree_stamped_before_archiving(self):
        self.assertIn('"homing-pigeon-windows-x86_64-onedir-$ver"',
                      self.block)
        self.assertIn("Copy-Item dist/homing-pigeon, dist/install, "
                      "runner/config.example.json", self.block)
        stamp = "stamp_provenance.py --job build-windows-onedir"
        self.assertIn(stamp, self.block)
        self.assertLess(self.block.index(stamp),
                        self.block.index("Compress-Archive"))
        self.assertIn("entries outside top dir", self.block)

    def test_the_artifact_stays_out_of_the_release_download(self):
        m = re.search(r"uses: actions/upload-artifact@.*\n"
                      r"\s+with:\n\s+name: (\S+)", self.block)
        self.assertIsNotNone(m, "the job uploads no artifact")
        name = m.group(1)
        # The release job downloads the homing-pigeon-* artifacts
        # (and the suites' ci-test-log*); this tree is an
        # installer's input, not a release asset.
        self.assertFalse(fnmatch.fnmatch(name, "homing-pigeon-*"), name)
        self.assertFalse(fnmatch.fnmatch(name, "ci-test-log*"), name)
        release = _job_block(self.workflow, "release")
        self.assertNotIn("build-windows-onedir", release)


class InnoDraftTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ISS)
        cls.install = _read(INSTALL)

    def test_marked_as_a_draft_and_stamped(self):
        self.assertIn("DRAFT", self.text[:1500])
        self.assertIn("00000000-muse-7e57-d0c5-58316a922026", self.text)

    def test_no_signature_is_applied(self):
        self.assertIn("UNSIGNED", self.text[:2600])
        self.assertIsNone(re.search(r"(?m)^\s*SignTool\s*=", self.text))
        self.assertNotIn("SignedUninstaller", self.text)

    def test_the_version_is_a_compile_time_input(self):
        self.assertIn("#define AppVersion", self.text)
        self.assertIn("AppVersion={#AppVersion}", self.text)
        self.assertIn("OutputBaseFilename=HomingPigeon-Setup-{#AppVersion}",
                      self.text)
        self.assertIn("iscc /DAppVersion=", self.text)

    def test_the_layout_is_versioned_and_elevated(self):
        self.assertIn(r"DefaultDirName={autopf}\Homing Pigeon\{#AppVersion}",
                      self.text)
        self.assertIn("UsePreviousAppDir=no", self.text)
        self.assertIn("PrivilegesRequired=admin", self.text)

    def test_the_files_carry_the_whole_staged_tree(self):
        for folder in ("homing-pigeon", "install"):
            self.assertIn('Source: "{#SourceDir}\\%s\\*"' % folder,
                          self.text)
            self.assertIn('DestDir: "{app}\\%s"' % folder, self.text)
        self.assertGreaterEqual(self.text.count("recursesubdirs"), 2)
        self.assertIn('Source: "{#SourceDir}\\config.example.json"',
                      self.text)
        self.assertIn('Source: "{#SourceDir}\\BUILD-PROVENANCE.json"',
                      self.text)

    def test_config_is_seeded_and_never_overwritten(self):
        seeded = [ln for ln in self.text.splitlines()
                  if 'DestName: "config.json"' in ln]
        self.assertEqual(len(seeded), 1)
        self.assertIn("onlyifdoesntexist", seeded[0])
        self.assertIn("uninsneveruninstall", seeded[0])

    def test_config_home_is_stable_across_versions(self):
        # The seeded config used to live in {app}, the versioned
        # program folder, so every upgrade stranded the operator's
        # edited config in the previous version's folder. It now
        # seeds into one fixed home no version number enters, and
        # the programs themselves stay versioned.
        seeded = [ln for ln in self.text.splitlines()
                  if 'DestName: "config.json"' in ln]
        self.assertEqual(len(seeded), 1)
        self.assertIn(r'DestDir: "{commonappdata}\Homing Pigeon"',
                      seeded[0])
        self.assertNotIn('DestDir: "{app}"', seeded[0])
        self.assertIn(r"DefaultDirName={autopf}\Homing Pigeon\{#AppVersion}",
                      self.text)

    def test_config_home_is_access_controlled(self):
        self.assertIn("[Dirs]", self.text)
        dirs = [ln for ln in self.text.splitlines()
                if ln.startswith('Name: "{commonappdata}')]
        self.assertEqual(len(dirs), 1)
        self.assertIn("Permissions: admins-full system-full", dirs[0])

    def test_the_legacy_config_gets_a_manual_copy_note(self):
        # Installs from the earlier draft shape hold their config
        # in a versioned folder; the header names the one time
        # hand copy instead of migrating silently.
        flat = " ".join(self.text.split())
        self.assertIn("copies that file once by hand", flat)

    def test_the_task_is_the_one_the_install_program_registers(self):
        m = re.search(r'"/TN",\s*"([^"]+)"', self.install)
        self.assertIsNotNone(m, "install.py registers no task by name")
        name = m.group(1)
        self.assertIn("/TN " + name, self.text)
        self.assertIn('"/SC", "ONSTART"', self.install)
        self.assertIn("/SC ONSTART", self.text)
        self.assertIn('run_as="SYSTEM"', self.install)
        self.assertIn("/RU SYSTEM", self.text)
        self.assertIn('"/RL", level', self.install)
        self.assertIn('"HIGHEST" if', self.install)
        self.assertIn("/RL HIGHEST", self.text)
        # The task command: the installed runner exe, --config
        # at the seeded config, quoted the way install.py's
        # windows_task_command quotes it (the /TR value opens
        # with an escaped quote around the exe path).
        self.assertIn('RUNNER_BIN = "homing-pigeon.exe"', self.install)
        self.assertIn("/TR ", self.text)
        self.assertIn(r'"{app}\homing-pigeon\homing-pigeon.exe', self.text)
        self.assertIn("--config", self.text)
        # The task reads the config from its stable home, the
        # same fixed path the seed writes (see the config home
        # tests above); it used to point into {app}, the
        # versioned folder, which is what stranded the config.
        self.assertIn(r'"{commonappdata}\Homing Pigeon\config.json',
                      self.text)
        self.assertNotIn(r'"{app}\config.json', self.text)
        # And it starts at once, as it does under install.py.
        self.assertIn('"/Run", "/TN", "HomingPigeon"', self.install)
        self.assertIn("/Run /TN " + name, self.text)

    def _run_lines(self):
        block = self.text.split("[Run]", 1)[1].split("[", 1)[0]
        return [ln for ln in block.splitlines() if ln.strip()]

    def test_both_task_entries_are_gated_on_completed_setup(self):
        # A config still carrying the example's placeholder
        # values is not a setup: neither registering the task
        # nor starting it may happen against one.
        lines = self._run_lines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertIn("Check: ConfigIsSetUp", line)

    def test_no_run_entry_is_ungated(self):
        for line in self._run_lines():
            self.assertIn("Check:", line)

    def test_the_gate_names_the_placeholder_values(self):
        self.assertIn("function ConfigIsSetUp", self.text)
        for placeholder in ("paste-app-password-here-in-plaintext",
                            "generate-with-openssl-rand-hex-32",
                            "homing-pigeon-runner@gmail.com"):
            self.assertIn(placeholder, self.text)

    def test_the_system_choice_is_visible_before_install(self):
        # The task runs as SYSTEM at the highest run level
        # whether or not anyone is signed in; a wizard page
        # says so, and what follows from it, before anything
        # is installed.
        self.assertIn("CreateOutputMsgPage", self.text)
        self.assertIn("runs as SYSTEM", self.text)
        self.assertIn("whether or not anyone is signed in", self.text)

    def test_unfinished_setup_gets_a_closing_message(self):
        self.assertIn("CurStepChanged", self.text)
        self.assertIn("Setup is not finished", self.text)
        self.assertIn("run this installer again", self.text)

    def test_uninstall_deletes_the_task(self):
        self.assertIn("[UninstallRun]", self.text)
        self.assertIn("/Delete /TN HomingPigeon /F", self.text)
        self.assertIn('"/Delete", "/TN", "HomingPigeon", "/F"',
                      self.install)

    def test_the_script_names_its_input_and_its_silence(self):
        self.assertIn("build-windows-onedir", self.text)
        self.assertIn("windows-onedir-installer-input", self.text)
        self.assertIn("VERYSILENT", self.text)


class DesignNotesTest(unittest.TestCase):

    def test_the_notes_record_the_route_a_preparation(self):
        text = _read(DOC)
        self.assertIn("build-windows-onedir", text)
        self.assertIn("homing-pigeon.iss", text)


if __name__ == "__main__":
    unittest.main()
