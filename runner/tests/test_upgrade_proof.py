# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""A real install, then a real upgrade over it, on this box.

runner/tools/upgrade_proof.py does the work: no mocks of the
installer, a stand-in systemctl, a throwaway HOME. Here it runs this
tree over itself on every Python the suite runs on;
.github/workflows/upgrade-proof.yml runs it from the last release.

The first run found that a source install could not start: the
installer's file list predated the role folders, so runner.py was
copied without runner/guard/textutil.py and refused to import.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _load_tool():
    path = os.path.join(ROOT, "runner", "tools", "upgrade_proof.py")
    spec = importlib.util.spec_from_file_location("upgrade_proof", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UP = _load_tool()


@unittest.skipIf(os.name == "nt", "the Linux and macOS source install; "
                 "Windows installs from the release binaries")
class UpgradeProofTest(unittest.TestCase):
    def test_this_tree_installs_and_upgrades_over_itself(self):
        self.assertEqual(UP.prove(ROOT, ROOT), [])

    def test_a_tree_that_cannot_start_is_caught(self):
        tmp = tempfile.mkdtemp(prefix="hp-upgrade-broken-")
        try:
            broken = os.path.join(tmp, "tree")
            shutil.copytree(
                os.path.join(ROOT, "runner"), os.path.join(broken, "runner"),
                ignore=shutil.ignore_patterns("tests", "__pycache__"))
            os.remove(os.path.join(broken, "runner", "guard", "textutil.py"))
            # Both installs from the broken tree: an upgrade leaves the
            # files a good first install wrote, so ROOT -> broken passes.
            failures = UP.prove(broken, broken)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertTrue(any("does not report" in f for f in failures),
                        failures)
        self.assertTrue(any("posture" in f for f in failures), failures)

    def test_the_previous_release_is_the_highest_tag_below(self):
        tags = ["v3.12.9", "v3.12.68", "v3.12.69", "v3.12.70", "v3.11.99",
                "v3.12.68-rc1", "latest", ""]
        self.assertEqual(UP.previous_release(tags, "3.12.69"), "v3.12.68")
        self.assertEqual(UP.previous_release(tags, "3.12.10"), "v3.12.9")
        self.assertIsNone(UP.previous_release(tags, "3.0.0"))

    def test_the_owner_edits_are_ones_the_installer_writes_around(self):
        # The proof only means something if the keys it seeds are ones
        # a fresh install does not already set to the same value.
        import json
        with open(os.path.join(ROOT, "runner", "config.example.json"),
                  encoding="utf-8") as fh:
            example = json.load(fh)
        for key, value in UP.OWNER_EDITS.items():
            self.assertNotEqual(example.get(key), value, key)


class PreviousReleaseCrossSchemeTest(unittest.TestCase):
    """previous_release across the 3- and 4-component tag schemes.

    Release tags come in 2 schemes: legacy 3-component
    MAJOR.MINOR.COUNTER and the current 4-component
    MAJOR.MINOR.TOKENS.COUNTER (runner/ops/version4.py; a legacy
    tag's 3rd component was the counter, see convert_legacy).
    previous_release used to keep only tags matching exactly
    3 components, so with the tree at 3.15.17.160 it returned the
    legacy v3.15.17 instead of v3.15.17.159, and upgrade-proof.yml
    proofed upgrades from that ancient tree. These tests pin the
    cross-scheme ordering the fix uses -- the same normalization
    as build.yml's vkey (runner/tests/test_sourceforge_vkey.py).
    previous_release is platform-independent, so this class stands
    outside UpgradeProofTest's Windows skip.
    """

    def test_key_normalizes_both_schemes_to_4_tuples(self):
        self.assertEqual(UP._key("v3.15.148"), (3, 15, 0, 148))
        self.assertEqual(UP._key("v3.15.17.160"), (3, 15, 17, 160))
        self.assertEqual(UP._key("3.12.69"), (3, 12, 0, 69))
        self.assertEqual(UP._key("3.15.17.160"), (3, 15, 17, 160))

    def test_the_defect_pair_both_ways(self):
        tags = ["v3.15.17", "v3.15.148",
                "v3.15.17.149", "v3.15.17.159", "v3.15.17.160"]
        # The verified defect: the previous release of a current
        # release is the 4-component tag before it, not v3.15.17.
        self.assertEqual(UP.previous_release(tags, "3.15.17.160"),
                         "v3.15.17.159")
        self.assertEqual(UP.previous_release(tags, "3.15.17.161"),
                         "v3.15.17.160")
        # And the other way: the previous release of the first
        # 4-component tag is the last legacy tag -- v3.15.148's
        # counter (148) outranks v3.15.17's (17) in the counter slot.
        self.assertEqual(UP.previous_release(tags, "3.15.17.149"),
                         "v3.15.148")

    def test_legacy_only_tag_lists(self):
        tags = ["v3.15.99", "v3.15.147", "v3.15.148"]
        self.assertEqual(UP.previous_release(tags, "3.15.148"),
                         "v3.15.147")
        self.assertEqual(UP.previous_release(tags, "3.15.149"),
                         "v3.15.148")
        self.assertIsNone(UP.previous_release(tags, "3.15.1"))

    def test_mixed_list_with_a_legacy_current(self):
        # A legacy current still sees only legacy tags below it:
        # every 4-component tag on the line outranks it.
        tags = ["v3.15.147", "v3.15.148", "v3.15.17.149"]
        self.assertEqual(UP.previous_release(tags, "3.15.148"),
                         "v3.15.147")

    def test_counter_restarts_when_the_token_figure_rises(self):
        # Odometer rule: the token figure increasing restarts the
        # counter at 1, and the new line still outranks the old.
        tags = ["v3.15.17.160", "v3.15.18.1", "v3.15.18.2"]
        self.assertEqual(UP.previous_release(tags, "3.15.18.2"),
                         "v3.15.18.1")
        self.assertEqual(UP.previous_release(tags, "3.15.18.1"),
                         "v3.15.17.160")

    def test_non_release_shapes_are_ignored(self):
        tags = ["v3.15.17.160.1", "v3.15", "v3.15.17.161-rc1",
                "latest", "", " v3.15.17.159 "]
        self.assertEqual(UP.previous_release(tags, "3.15.17.160"),
                         "v3.15.17.159")


class ServiceDefinitionPlatformTest(unittest.TestCase):
    """Q175: the service check branches the way install.py installs.

    install.py writes a systemd user unit on Linux, a launchd
    plist on macOS, and a cron @reboot entry -- no service file
    at all -- on FreeBSD. upgrade_proof's check used to read the
    systemd path on every non-macOS platform, so it failed on
    FreeBSD by construction. The helper takes the platform as an
    argument, so every branch is pinned here on any host.
    """

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="hp-upgrade-svc-")
        self.addCleanup(shutil.rmtree, self.work, True)
        self.home = os.path.join(self.work, "home")
        os.makedirs(self.home)
        self.runner = os.path.join(self.home, ".homing-pigeon",
                                   "runner.py")
        self.cfg = os.path.join(self.home, ".homing-pigeon",
                                "config.json")
        self.crontab = os.path.join(self.work, "crontab.txt")

    def _failures(self, platform):
        return UP._service_definition_failures(
            platform, self.home, self.runner, self.cfg, self.crontab)

    def _entry(self, when="@reboot", runner=None, cfg=None, extra=""):
        return "%s %s --config %s%s" % (
            when, runner or self.runner, cfg or self.cfg, extra)

    def _write_crontab(self, text):
        with open(self.crontab, "w", encoding="utf-8") as fh:
            fh.write(text)

    # The FreeBSD branch.

    def test_freebsd_the_installers_reboot_entry_passes(self):
        self._write_crontab(self._entry() + "\n")
        for spelling in ("freebsd", "freebsd13", "freebsd14",
                         "freebsd15"):
            self.assertEqual(self._failures(spelling), [], spelling)

    def test_freebsd_a_missing_crontab_is_a_missing_definition(self):
        failures = self._failures("freebsd14")
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith(
            "service definition missing"), failures)

    def test_freebsd_no_crontab_path_is_a_missing_definition(self):
        failures = UP._service_definition_failures(
            "freebsd14", self.home, self.runner, self.cfg, None)
        self.assertTrue(failures[0].startswith(
            "service definition missing"), failures)

    def test_freebsd_an_entry_for_another_config_fails(self):
        self._write_crontab(self._entry(
            cfg=os.path.join(self.home, "other.json")) + "\n")
        failures = self._failures("freebsd14")
        self.assertEqual(len(failures), 1)
        self.assertIn("does not start the installed runner",
                      failures[0])
        self.assertIn(self.crontab, failures[0])

    def test_freebsd_an_entry_for_another_runner_fails(self):
        self._write_crontab(self._entry(
            runner=os.path.join(self.home, "other.py")) + "\n")
        self.assertEqual(len(self._failures("freebsd14")), 1)

    def test_freebsd_a_scheduled_line_is_not_the_entry(self):
        # install.py writes @reboot and nothing else starts the
        # runner at boot; a plain schedule line naming the same
        # command is not the installer's definition.
        self._write_crontab(self._entry(when="0 3 * * *") + "\n")
        self.assertEqual(len(self._failures("freebsd14")), 1)

    def test_freebsd_the_entry_among_other_lines_passes(self):
        # Bookends in the table itself: comments, a neighbour's
        # job and a trailing line around the entry change nothing.
        self._write_crontab(
            "# the owner's crontab\n"
            "0 3 * * * /usr/bin/true\n"
            + self._entry(extra=" --flag") + "\n"
            "# end\n")
        self.assertEqual(self._failures("freebsd14"), [])

    def test_freebsd_an_indented_or_ornamented_entry_fails(self):
        for line in (" " + self._entry(), "-" + self._entry(),
                     "# " + self._entry()):
            self._write_crontab(line + "\n")
            self.assertEqual(len(self._failures("freebsd14")), 1,
                             line)

    def test_freebsd_an_empty_crontab_fails_as_no_entry(self):
        self._write_crontab("")
        failures = self._failures("freebsd14")
        self.assertEqual(len(failures), 1)
        self.assertIn("does not start", failures[0])

    # The branches that stood before: read as they read today.

    def _write_unit(self, rel, text):
        path = os.path.join(self.home, *rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_the_systemd_branch_is_unchanged(self):
        rel = (".config", "systemd", "user", "homing-pigeon.service")
        missing = self._failures("linux")
        self.assertTrue(missing[0].startswith(
            "service definition missing"), missing)
        self._write_unit(rel, "ExecStart=%s --config %s\n"
                         % (self.runner, self.cfg))
        self.assertEqual(self._failures("linux"), [])
        self._write_unit(rel, "ExecStart=/bin/true\n")
        failures = self._failures("linux")
        self.assertEqual(len(failures), 1)
        self.assertIn("does not start the installed runner",
                      failures[0])

    def test_the_launchd_branch_is_unchanged(self):
        rel = ("Library", "LaunchAgents",
               "com.homing-pigeon.runner.plist")
        missing = self._failures("darwin")
        self.assertTrue(missing[0].startswith(
            "service definition missing"), missing)
        self._write_unit(rel, "<string>%s</string><string>%s</string>"
                         % (self.runner, self.cfg))
        self.assertEqual(self._failures("darwin"), [])
        self._write_unit(rel, "<string>/bin/true</string>")
        self.assertEqual(len(self._failures("darwin")), 1)


@unittest.skipIf(os.name == "nt", "the crontab stand-in is a sh script")
class CrontabStandinTest(unittest.TestCase):
    """The proof's crontab shim keeps the table it is handed.

    install_freebsd reads `crontab -l`, decides the entry is
    absent, and installs the new table with `crontab -`; the
    stand-in has to round-trip that or the FreeBSD branch of
    prove() would check a table the installer never wrote.
    """

    def test_install_then_list_round_trips(self):
        import subprocess
        work = tempfile.mkdtemp(prefix="hp-crontab-shim-")
        self.addCleanup(shutil.rmtree, work, True)
        shim = os.path.join(work, "crontab")
        with open(shim, "w", encoding="utf-8") as fh:
            fh.write(UP._FAKE_CRONTAB_TOOL)
        os.chmod(shim, 0o755)
        env = dict(os.environ,
                   HP_CRONTAB_FILE=os.path.join(work, "table"))
        # -l before any install: no table yet, a failing read --
        # the shape install.py reads as "no existing crontab".
        first = subprocess.run([shim, "-l"], env=env,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               universal_newlines=True)
        self.assertNotEqual(first.returncode, 0)
        line = "@reboot /home/x/runner.py --config /home/x/cfg.json\n"
        fed = subprocess.run([shim, "-"], env=env, input=line,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True)
        self.assertEqual(fed.returncode, 0, fed.stdout)
        listed = subprocess.run([shim, "-l"], env=env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                universal_newlines=True)
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(listed.stdout, line)


if __name__ == "__main__":
    unittest.main()
