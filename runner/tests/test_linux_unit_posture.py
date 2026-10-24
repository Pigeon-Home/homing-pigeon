"""Linux systemd unit posture. A symlink unit is not read.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here calls systemctl or starts a service. A planted
symlink is not opened.
"""
import os
import random
import tempfile
import unittest
from unittest import mock

from runner.ops.posture import _check_service_unit


def _check(path, exists=True):
    results = []

    def _exists(candidate):
        return exists and candidate == path

    with mock.patch("runner.ops.posture.os.path.exists", side_effect=_exists), \
         mock.patch("runner.ops.posture.os.path.expanduser", return_value=path):
        _check_service_unit(results)
    return results[0]


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class UnitPostureTest(unittest.TestCase):
    def test_hardening_directives_are_read_from_a_regular_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "homing-pigeon.service")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("NoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\n")
            level, topic, detail = _check(path)
            self.assertEqual(level, "OK")
            self.assertEqual(topic, "service")
            self.assertIn("NoNewPrivileges", detail)
            self.assertIn("ProtectHome", detail)

    def test_a_symlink_is_not_opened(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("NoNewPrivileges=yes\nProtectSystem=strict\n"
                         "ProtectHome=yes\nPrivateTmp=yes\nsecret\n")
            link = os.path.join(d, "homing-pigeon.service")
            os.symlink(target, link)
            opened = []
            real_open = open

            def spy(file_path, *args, **kwargs):
                opened.append(file_path)
                return real_open(file_path, *args, **kwargs)

            results = []

            def _exists(candidate):
                return candidate == link

            with mock.patch("builtins.open", side_effect=spy), \
                 mock.patch("runner.ops.posture.os.path.exists", side_effect=_exists), \
                 mock.patch("runner.ops.posture.os.path.expanduser", return_value=link):
                _check_service_unit(results)
            level, _topic, detail = results[0]
            self.assertEqual(level, "WARN")
            self.assertIn("symlink", detail)
            self.assertNotIn("secret", detail)
            self.assertNotIn("NoNewPrivileges", detail)
            self.assertEqual(opened, [])
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class UnitPostureMutations(unittest.TestCase):
    def test_missing_one_directive_and_unreadable(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "homing-pigeon.service")
            level, _topic, detail = _check(path, exists=False)
            self.assertEqual(level, "OK")
            self.assertIn("no homing-pigeon", detail)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("NoNewPrivileges=yes\n")
            level, _topic, detail = _check(path)
            self.assertEqual(level, "WARN")
            self.assertIn("lacks hardening", detail)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("")
            level, _topic, detail = _check(path)
            self.assertEqual(level, "WARN")
            with mock.patch("builtins.open", side_effect=OSError("busy")):
                level, _topic, detail = _check(path)
            self.assertEqual(level, "WARN")
            self.assertIn("cannot read", detail)


class UnitPostureFuzzTest(unittest.TestCase):
    def test_random_unit_text_does_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        directives = ["NoNewPrivileges", "ProtectSystem", "ProtectHome", "PrivateTmp"]
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "homing-pigeon.service")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for _ in range(80):
                body = "\n".join(
                    name + "=yes" for name in directives if rng.randrange(2))
                body += "\n" + "".join(rng.choice("abc= \n")
                                       for _ in range(rng.randrange(0, 20)))
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    level, topic, detail = _check(path)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if level not in ("OK", "WARN") or topic != "service":
                    crashes.append(level)
                    break
                if not isinstance(detail, str):
                    crashes.append(type(detail).__name__)
                    break
                present = sum(1 for name in directives if name in body)
                if present >= 2 and level != "OK":
                    crashes.append(present)
                    break
                if present < 2 and level != "WARN":
                    crashes.append(present)
                    break
            link = os.path.join(d, "link.service")
            os.symlink(target, link)
            try:
                level, _topic, detail = _check(link)
            except Exception as exc:
                crashes.append(type(exc).__name__)
                level, detail = "ERR", ""
            if level != "WARN" or "symlink" not in detail:
                crashes.append(detail)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
