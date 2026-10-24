"""Linux canary files: mode 0600, and a symlink is not a canary.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not written
through, and it is reported as a trip.
"""
import os
import random
import tempfile
import unittest

from runner.runner import _CANARY_NAMES, _canary_state, _canary_watch


def _mode(path):
    return os.stat(path).st_mode & 0o777


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class CanaryFileTest(unittest.TestCase):
    def test_planted_canaries_are_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            text = _canary_watch(d)
            self.assertIn("planted", text)
            snap = os.path.join(d, "canary-watch.json")
            self.assertEqual(_mode(snap), 0o600)
            self.assertFalse(os.path.islink(snap))
            for name in _CANARY_NAMES:
                path = os.path.join(d, "canaries", name)
                self.assertFalse(os.path.islink(path))
                self.assertEqual(_mode(path), 0o600)
                with open(path, encoding="utf-8") as fh:
                    self.assertIn("CANARY", fh.read())
            again = _canary_watch(d)
            self.assertIn("untouched", again)
            self.assertNotIn("TRIPPED", again)

    def test_a_symlink_is_not_followed_and_is_a_trip(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            canaries = os.path.join(d, "canaries")
            os.makedirs(canaries)
            link = os.path.join(canaries, _CANARY_NAMES[0])
            os.symlink(target, link)
            os.symlink(target, os.path.join(d, "canary-watch.json"))
            text = _canary_watch(d)
            self.assertIn("symlink", text)
            self.assertIn("TRIPPED", text)
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(link))
            self.assertEqual(_canary_state(link), "?")
            again = _canary_watch(d)
            self.assertIn("symlink", again)
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class CanaryMutations(unittest.TestCase):
    def test_delete_edit_and_bad_bases(self):
        self.assertEqual(_canary_watch(""), "")
        self.assertEqual(_canary_watch(None), "")
        self.assertEqual(_canary_watch(1), "")
        with tempfile.TemporaryDirectory() as d:
            _canary_watch(d)
            name = _CANARY_NAMES[1]
            path = os.path.join(d, "canaries", name)
            with open(path, "ab") as fh:
                fh.write(b"\nchanged\n")
            edited = _canary_watch(d)
            self.assertIn("modified", edited)
            self.assertIn(name, edited)
            quiet = _canary_watch(d)
            self.assertIn("modified", quiet)
            os.remove(path)
            gone = _canary_watch(d)
            self.assertIn("missing", gone)
            self.assertIn(name, gone)
            for other in _CANARY_NAMES:
                if other == name:
                    continue
                self.assertEqual(
                    _mode(os.path.join(d, "canaries", other)), 0o600)


class CanaryFuzzTest(unittest.TestCase):
    def test_random_replacements_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            try:
                _canary_watch(d)
            except Exception as exc:
                crashes.append(type(exc).__name__)
            name = _CANARY_NAMES[0]
            path = os.path.join(d, "canaries", name)
            for i in range(80):
                kind = rng.choice(["keep", "edit", "delete", "symlink", "file"])
                try:
                    if os.path.lexists(path):
                        os.remove(path)
                    if kind == "edit":
                        with open(path, "w", encoding="utf-8") as fh:
                            fh.write("changed-%d\n" % i)
                    elif kind == "file":
                        with open(path, "wb") as fh:
                            fh.write(os.urandom(rng.randrange(0, 40)))
                    elif kind == "symlink":
                        os.symlink(target, path)
                    text = _canary_watch(d)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(text, str):
                    crashes.append(type(text).__name__)
                    break
                if kind == "symlink" and "symlink" not in text:
                    crashes.append("no-trip")
                    break
                with open(target, encoding="utf-8") as fh:
                    if fh.read() != "keep":
                        crashes.append("followed")
                        break
            for leftover in _CANARY_NAMES[1:]:
                other = os.path.join(d, "canaries", leftover)
                if os.path.isfile(other) and not os.path.islink(other):
                    if _mode(other) != 0o600:
                        crashes.append(oct(_mode(other)))
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
