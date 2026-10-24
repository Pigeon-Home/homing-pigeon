"""Linux log-seen file. A symlink is not the baseline.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not read,
so it cannot hide a line or force an alert.
"""
import hashlib
import json
import os
import random
import tempfile
import unittest

from runner.runner import _file_fresh_lines
from runner.oracle.senses import load_alerts


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _digest(line):
    return hashlib.sha1(line.encode("utf-8", "replace")).hexdigest()[:16]


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class LogSeenTest(unittest.TestCase):
    def test_a_first_look_is_a_baseline_and_a_symlink_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as d:
            line = "Failed password for bob [T1110]"
            _file_fresh_lines(d, "auth", line + "\n")
            self.assertEqual(load_alerts(d, sensor="auth"), [])
            path = os.path.join(d, "oracle-logseen.json")
            self.assertEqual(_mode(path), 0o600)
            _file_fresh_lines(d, "auth", line + "\n")
            self.assertEqual(load_alerts(d, sensor="auth"), [])
            fresh = "sudo: bob [T1548.003]"
            _file_fresh_lines(d, "auth", fresh + "\n")
            self.assertEqual(len(load_alerts(d, sensor="auth")), 1)

            target = os.path.join(d, "target")
            hidden = "useradd mallory [T1136]"
            with open(target, "w", encoding="utf-8") as fh:
                json.dump({"auth": [_digest(hidden)]}, fh)
            os.remove(path)
            os.symlink(target, path)
            before = len(load_alerts(d, sensor="auth"))
            _file_fresh_lines(d, "auth", hidden + "\n")
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            self.assertEqual(len(load_alerts(d, sensor="auth")), before)
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["auth"], [_digest(hidden)])
            with open(target, encoding="utf-8") as fh:
                self.assertIn(_digest(hidden), fh.read())


class LogSeenMutations(unittest.TestCase):
    def test_untagged_and_bad_inputs_do_not_file(self):
        _file_fresh_lines(None, "auth", "sudo: bob [T1548.003]")
        _file_fresh_lines("", "auth", "sudo: bob [T1548.003]")
        with tempfile.TemporaryDirectory() as d:
            _file_fresh_lines(d, "auth", None)
            _file_fresh_lines(d, "auth", "plain error with no tag\n")
            _file_fresh_lines(d, "auth", "noise [not-an-id]\n")
            self.assertEqual(load_alerts(d, sensor="auth"), [])
            _file_fresh_lines(d, "", "sudo: bob [T1548.003]\n")
            path = os.path.join(d, "oracle-logseen.json")
            if os.path.isfile(path):
                self.assertEqual(_mode(path), 0o600)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[]")
            _file_fresh_lines(d, "auth", "sudo: bob [T1548.003]\n")
            self.assertEqual(load_alerts(d, sensor="auth"), [])


class LogSeenFuzzTest(unittest.TestCase):
    def test_random_lines_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        attacks = ("T1110", "T1548.003", "T1136", "nope", "")
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            hidden = "useradd mallory [T1136]"
            with open(target, "w", encoding="utf-8") as fh:
                json.dump({"auth": [_digest(hidden), "secret"]}, fh)
            for i in range(60):
                attack = rng.choice(attacks)
                text = rng.choice([
                    "line %d [%s]\n" % (i, attack),
                    "plain\n",
                    None,
                    "",
                ])
                try:
                    before = len(load_alerts(d, sensor="auth"))
                    _file_fresh_lines(d, "auth", text)
                    after = len(load_alerts(d, sensor="auth"))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if after - before > 1:
                    crashes.append(after - before)
                    break
            path = os.path.join(d, "oracle-logseen.json")
            if os.path.isfile(path) and not os.path.islink(path):
                if _mode(path) != 0o600:
                    crashes.append(oct(_mode(path)))
            if os.path.lexists(path):
                os.remove(path)
            os.symlink(target, path)
            try:
                _file_fresh_lines(d, "auth", hidden + "\n")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                body = fh.read()
            if "secret" not in body:
                crashes.append("followed")
            if os.path.islink(path):
                crashes.append("still-link")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
