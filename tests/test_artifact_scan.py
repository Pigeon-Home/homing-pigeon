"""The YARA / ClamAV artifact scan, as a cross-platform suite.

The scan's own tests used to live only inside tests/test_linux_platform.py,
so they ran in the Linux job alone -- yet the scan itself is platform
neutral (shutil.which plus a subprocess per engine) and runs after every
job on every host, Windows included. This suite pins the seams with the
engines mocked: the enable gate, the rules fallback, both output
parsers, the changed-file selection with its caps, and the retained
note that carries a hit to the Oracle. Symlink cases stay in the Linux
suite, where symlink creation needs no privilege.
"""

import os
import re
import tempfile
import types
import unittest
from unittest import mock

from runner import runner as R


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class ScanEnabledTest(unittest.TestCase):
    def test_default_on(self):
        self.assertTrue(R._artifact_scan_enabled({}))
        self.assertTrue(R._artifact_scan_enabled(None))
        self.assertTrue(R._artifact_scan_enabled({"inference": []}))
        self.assertTrue(R._artifact_scan_enabled(
            {"inference": {"artifact_scan": True}}))

    def test_explicit_off(self):
        for off in (False, 0, "false", "No", "OFF", "0"):
            self.assertFalse(R._artifact_scan_enabled(
                {"inference": {"artifact_scan": off}}), off)


class RulesTextTest(unittest.TestCase):
    def test_default_rules_carry_every_tagged_rule(self):
        text = R._yara_rules_text({})
        for name in re.findall(r"rule (\w+)", text):
            self.assertIn(name, R._YARA_ATTACK)

    def test_attack_map_has_no_orphan_rules(self):
        names = set(re.findall(r"rule (\w+)", R._YARA_RULES))
        self.assertEqual(set(R._YARA_ATTACK), names)

    def test_operator_file_wins(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mine.yar")
            _write(path, "rule mine { condition: true }\n")
            got = R._yara_rules_text({"inference": {"yara_rules": path}})
            self.assertEqual(got, "rule mine { condition: true }\n")

    def test_missing_or_empty_file_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "nope.yar")
            self.assertEqual(
                R._yara_rules_text({"inference": {"yara_rules": missing}}),
                R._YARA_RULES)
            empty = os.path.join(d, "empty.yar")
            _write(empty, "   \n")
            self.assertEqual(
                R._yara_rules_text({"inference": {"yara_rules": empty}}),
                R._YARA_RULES)


class YaraHitsTest(unittest.TestCase):
    def test_no_engine_no_hits(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(R._yara_hits("/w", ["/w/a.txt"]), [])

    def test_classic_yara_output_is_parsed_and_tagged(self):
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"] = argv
            with open(argv[1], encoding="utf-8") as fh:
                seen["rules"] = fh.read()
            return types.SimpleNamespace(
                returncode=0,
                stdout=("hp_webshell /w/shell.php\n"
                        "hp_cred_dump /w/dump.txt\n"
                        "some_other_rule /w/x.bin\n"
                        "error: cannot open file\n"
                        "warning: something\n"))

        with mock.patch("shutil.which",
                        side_effect=lambda n: "/bin/yara" if n == "yara"
                        else None), \
                mock.patch("subprocess.run", side_effect=fake_run):
            hits = R._yara_hits("/w", ["/w/shell.php"], {})
        self.assertEqual(seen["argv"][0], "/bin/yara")
        self.assertIn("hp_webshell", seen["rules"])
        # Every output line is attributed to the file that was scanned;
        # the parser takes the rule name and the ATT&CK tag only.
        self.assertEqual(hits, [
            "yara hp_webshell shell.php [T1505.003]",
            "yara hp_cred_dump shell.php [T1003.001]",
            "yara some_other_rule shell.php [T1204.002]",
        ])

    def test_yara_x_is_preferred_and_uses_scan_subcommand(self):
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"] = argv
            return types.SimpleNamespace(returncode=0, stdout="")

        with mock.patch("shutil.which",
                        side_effect=lambda n: "/bin/" + n), \
                mock.patch("subprocess.run", side_effect=fake_run):
            self.assertEqual(R._yara_hits("/w", ["/w/a.txt"]), [])
        self.assertEqual(seen["argv"][:2], ["/bin/yr", "scan"])

    def test_engine_failure_is_quiet(self):
        with mock.patch("shutil.which", return_value="/bin/yara"), \
                mock.patch("subprocess.run",
                           side_effect=OSError("cannot start")):
            self.assertEqual(R._yara_hits("/w", ["/w/a.txt"]), [])


class ClamHitsTest(unittest.TestCase):
    def test_no_binary_no_hits(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(R._clam_hits("/w", ["/w/a.txt"]), [])

    def test_found_lines_are_parsed(self):
        def fake_run(argv, **kw):
            return types.SimpleNamespace(
                returncode=1,
                stdout=("/w/a.txt: Eicar-Test-Signature FOUND\n"
                        "/w/b.txt: OK\n"))

        with mock.patch("shutil.which", return_value="/bin/clamdscan"), \
                mock.patch("subprocess.run", side_effect=fake_run):
            hits = R._clam_hits("/w", ["/w/a.txt", "/w/b.txt"])
        self.assertEqual(
            hits, ["clamav Eicar-Test-Signature a.txt [T1204.002]"])

    def test_dead_daemon_is_quiet_not_clean(self):
        def fake_run(argv, **kw):
            return types.SimpleNamespace(returncode=2, stdout="")

        with mock.patch("shutil.which", return_value="/bin/clamdscan"), \
                mock.patch("subprocess.run", side_effect=fake_run):
            self.assertEqual(R._clam_hits("/w", ["/w/a.txt"]), [])


class FindingsTest(unittest.TestCase):
    def _scan(self, work, before, cfg, yara=(), clam=()):
        calls = {}

        def fy(w, targets, c=None):
            calls["yara_targets"] = list(targets)
            return list(yara)

        def fc(w, targets):
            calls["clam_targets"] = list(targets)
            return list(clam)

        with mock.patch.object(R, "_yara_hits", side_effect=fy), \
                mock.patch.object(R, "_clam_hits", side_effect=fc):
            return R._artifact_findings(work, before, cfg), calls

    def test_only_changed_files_are_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "old.txt"), "same")
            before = R._work_files(d)
            _write(os.path.join(d, "new.txt"), "fresh")
            with open(os.path.join(d, "old.txt"), "a",
                      encoding="utf-8") as fh:
                fh.write("-grown")
            hits, calls = self._scan(d, before, {}, yara=["yara x y [T1]"])
            self.assertEqual(hits, ["yara x y [T1]"])
            self.assertEqual(
                sorted(os.path.basename(p) for p in calls["yara_targets"]),
                ["new.txt", "old.txt"])

    def test_oversize_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            big = os.path.join(d, "big.bin")
            with open(big, "wb") as fh:
                fh.write(b"x" * (R._ARTIFACT_MAX_BYTES + 1))
            hits, calls = self._scan(d, {}, {})
            self.assertEqual(hits, [])
            self.assertNotIn("yara_targets", calls)

    def test_file_cap_and_hit_cap(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(R._ARTIFACT_MAX_FILES + 5):
                _write(os.path.join(d, "f%02d.txt" % i), "x")
            many = ["hit %02d" % i for i in range(25)]
            hits, calls = self._scan(d, {}, {}, yara=many)
            self.assertEqual(len(calls["yara_targets"]),
                             R._ARTIFACT_MAX_FILES)
            self.assertEqual(len(hits), 20)

    def test_disabled_scan_calls_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "a.txt"), "x")
            cfg = {"inference": {"artifact_scan": False}}
            hits, calls = self._scan(d, {}, cfg)
            self.assertEqual(hits, [])
            self.assertNotIn("yara_targets", calls)


class ArtifactNoteTest(unittest.TestCase):
    def test_no_scan_no_note(self):
        self.assertIsNone(R._artifact_note("j1", {}, {}))
        self.assertIsNone(R._artifact_note("j1", {}, {"artifact_scan": []}))

    def test_note_carries_hits_not_output(self):
        job = {"kind": "run", "script": "s" * 900}
        r = {"artifact_scan": ["yara hp_webshell a.php [T1505.003]"],
             "exit_code": 0, "timed_out": False}
        note = R._artifact_note("j1", job, r)
        self.assertEqual(note["artifact_scan"],
                         ["yara hp_webshell a.php [T1505.003]"])
        self.assertEqual(note["stdout"], "")
        self.assertEqual(len(note["script"]), 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
