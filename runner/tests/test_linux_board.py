"""Linux board file: mode 0600, and the temp name is not a symlink.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not written
through.
"""
import json
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner.guard import atomicio as _atomicio

from runner.runner import Board


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _tmp_for(path):
    return path + ".tmp.pinned"

# The atomic writer (runner/guard/atomicio.py) picks a random temp
# name; these tests plant symlinks at the exact name, so the name is
# pinned for the module (Agent-Chat-Stamp
# 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f).
_PIN = mock.patch.object(_atomicio, "_temp_name", lambda p: p + ".tmp.pinned")


def setUpModule():
    _PIN.start()


def tearDownModule():
    _PIN.stop()


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class BoardFileTest(unittest.TestCase):
    def test_a_save_is_owner_only_and_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            board = Board(path)
            ok, _ = board.submit({"task_id": "job.1", "priority": 2,
                                  "requires": ["a"]})
            self.assertTrue(ok)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            again = Board(path)
            self.assertEqual(again.tasks["job.1"]["state"], "open")
            self.assertEqual(again.tasks["job.1"]["requires"], ["a"])
            self.assertFalse(os.path.exists(_tmp_for(path)))

    def test_a_symlink_at_the_temp_name_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            link = _tmp_for(path)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            board = Board(path)
            board.tasks = {"job.1": {"task_id": "job.1", "state": "open"}}
            with mock.patch("os.unlink", side_effect=leave_the_link):
                board.save()
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(link))
            self.assertFalse(os.path.exists(path))

    def test_a_symlink_at_the_board_path_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            os.symlink(target, path)
            board = Board(path)
            board.tasks = {"job.1": {"task_id": "job.1", "state": "open"}}
            board.save()
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            with open(path, encoding="utf-8") as fh:
                saved = json.loads(fh.read())
            self.assertIn("job.1", saved)


class BoardMutations(unittest.TestCase):
    def test_task_id_and_field_mutations(self):
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            good = {"task_id": "ok", "priority": 1,
                    "requires": [], "capabilities": [], "compartments": []}
            self.assertTrue(board.submit(dict(good))[0])
            for bad_id in ("", "../x", "a/b", "a\\b", "a\x00b", "a b",
                           "x" * 129, 1, None):
                task = dict(good)
                task["task_id"] = bad_id
                ok, reason = board.submit(task)
                self.assertFalse(ok, bad_id)
                self.assertIn("task_id", reason)
            for field in ("requires", "capabilities", "compartments"):
                task = dict(good)
                task["task_id"] = "f-" + field
                task[field] = "nope"
                self.assertFalse(board.submit(task)[0])
            task = dict(good)
            task["task_id"] = "nan"
            task["priority"] = float("nan")
            self.assertFalse(board.submit(task)[0])
            self.assertFalse(board.submit("nope")[0])
            missing = Board(os.path.join(d, "missing", "board.json"))
            missing.tasks = {"a": {"task_id": "a"}}
            missing.save()
            self.assertFalse(os.path.exists(missing.path))


class BoardFuzzTest(unittest.TestCase):
    def test_random_tasks_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            board = Board(path)
            for i in range(200):
                tid = rng.choice([
                    "job-%d" % i, "", "../x", "a/b", "x" * 200, None,
                ])
                task = {
                    "task_id": tid,
                    "priority": rng.choice([0, 1, -1, float("nan"), "n"]),
                    "requires": rng.choice([[], ["a"], "nope", None]),
                }
                try:
                    board.submit(task)
                    if rng.randrange(5) == 0:
                        board.tasks = {
                            "k": rng.choice([
                                {"task_id": "k", "state": "open", "n": i},
                                {"n": float("nan")},
                                {"bag": {1, 2}},
                            ])
                        }
                        board.save()
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if os.path.isfile(path) and not os.path.islink(path):
                    if _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
                        break
                    try:
                        with open(path, encoding="utf-8") as fh:
                            data = json.loads(fh.read())
                    except ValueError as exc:
                        crashes.append(type(exc).__name__)
                        break
                    if not isinstance(data, dict):
                        crashes.append(type(data).__name__)
                        break
            link = _tmp_for(path)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            try:
                board.save()
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
            # The planted name is refused (O_EXCL | O_NOFOLLOW), never
            # written through: the link is still a link, the target is
            # untouched, and the save is the one that lost.
            self.assertTrue(os.path.islink(link))
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
