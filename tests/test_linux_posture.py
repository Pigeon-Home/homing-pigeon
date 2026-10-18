"""Linux firewall and antivirus snapshots. A symlink is not read.

Unit cases, one-field mutations, and a deterministic fuzz.
ufw, iptables, and clamav are not run. Nothing here starts a process.
A planted symlink is not written through.
"""
import json
import os
import random
import tempfile
import unittest
from unittest import mock

from runner.runner import _av_watch, _firewall_watch, _read_posture_line


def _mode(path):
    return os.stat(path).st_mode & 0o777


class PostureReadTest(unittest.TestCase):
    def test_a_json_symlink_is_not_the_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                json.dump({"line": "firewall: ufw=active", "secret": True}, fh)
            path = os.path.join(d, "oracle-firewall.json")
            os.symlink(target, path)
            self.assertIsNone(_read_posture_line(path))
            with mock.patch("runner.runner._firewall_posture",
                            return_value="firewall: ufw=active"):
                text = _firewall_watch(d)
            self.assertIn("baseline", text)
            self.assertNotIn("secret", text)
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["line"], "firewall: ufw=active")
            self.assertNotIn("secret", saved)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            with mock.patch("runner.runner._firewall_posture",
                            return_value="firewall: ufw=active"):
                again = _firewall_watch(d)
            self.assertEqual(again, "firewall: ufw=active")

    def test_an_antivirus_symlink_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"line": "av: clamav signatures current", "secret": true}\n')
            path = os.path.join(d, "oracle-av.json")
            os.symlink(target, path)
            with mock.patch("runner.runner._av_posture",
                            return_value="av: clamav signatures current"):
                text = _av_watch(d)
            self.assertIn("baseline", text)
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class PostureMutations(unittest.TestCase):
    def test_unreadable_posture_does_not_touch_a_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            path = os.path.join(d, "oracle-firewall.json")
            os.symlink(target, path)
            for value in (None, "", 1):
                with mock.patch("runner.runner._firewall_posture", return_value=value):
                    self.assertIsNone(_firewall_watch(d))
                with mock.patch("runner.runner._av_posture", return_value=value):
                    self.assertIsNone(_av_watch(os.path.join(d, "missing")))
            self.assertTrue(os.path.islink(path))
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            with mock.patch("runner.runner._firewall_posture",
                            return_value="firewall: ufw=active"):
                self.assertEqual(_firewall_watch(""), "firewall: ufw=active")
                self.assertEqual(_firewall_watch(None), "firewall: ufw=active")
            with mock.patch("runner.runner._av_posture",
                            return_value="av: clamav signatures current"):
                self.assertEqual(_av_watch(1), "av: clamav signatures current")


class PostureFuzzTest(unittest.TestCase):
    def test_random_lines_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            lines = [
                "firewall: linux ufw=active",
                "firewall: linux ufw=inactive [T1562.004]",
                "av: clamav signatures current",
                "av: clamav signatures stale (9d) [T1562.001]",
                "firewall: linux iptables INPUT=DROP",
            ]
            for i in range(80):
                line = rng.choice(lines)
                if rng.randrange(6) == 0:
                    line = rng.choice([None, "", "x" * rng.randrange(0, 8)])
                watch = _firewall_watch if i % 2 == 0 else _av_watch
                posture = ("runner.runner._firewall_posture" if watch is _firewall_watch
                           else "runner.runner._av_posture")
                try:
                    text = None
                    with mock.patch(posture, return_value=line):
                        text = watch(d)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if line and isinstance(line, str):
                    if not isinstance(text, str) or not text.startswith(line):
                        crashes.append(text)
                        break
                elif text is not None:
                    crashes.append(text)
                    break
            for name in ("oracle-firewall.json", "oracle-av.json"):
                path = os.path.join(d, name)
                if os.path.isfile(path) and not os.path.islink(path):
                    if _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
                    with open(path, encoding="utf-8") as fh:
                        saved = json.load(fh)
                    if not isinstance(saved.get("line"), str):
                        crashes.append("shape")
            fw = os.path.join(d, "oracle-firewall.json")
            if os.path.lexists(fw):
                os.remove(fw)
            os.symlink(target, fw)
            try:
                with mock.patch("runner.runner._firewall_posture",
                                return_value="firewall: linux ufw=active"):
                    _firewall_watch(d)
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
