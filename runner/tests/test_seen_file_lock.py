#!/usr/bin/env python3
"""Queue A: `_with_seen_file`, the seen cache's locked
read-modify-write.

The coverage map (run 40180268696) showed the branches
around the lock itself never running on Linux: the
bad-path answer, the best-effort lock seeding, the msvcrt
fallback (the Windows half of the function), a mutator
that answers a non-dict, the lock-open failure that falls
back to a plain read, and the unlock/close failure
swallows in the finally. The contract is the docstring's:
the mutation lands under a lock other processes see, and
every failure around the lock degrades to the safest read
available -- it never raises into the poll and never
loses what is already on disk.
"""
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import _with_seen_file, load_seen  # noqa: E402
from runner.tests._compat import lenient_tempdir  # noqa: E402


def _add(key):
    def mutate(disk):
        disk = dict(disk)
        disk[key] = True
        return disk
    return mutate


class WithSeenFileTest(unittest.TestCase):
    def test_a_bad_path_answers_empty(self):
        for bad in (None, "", 5):
            self.assertEqual(_with_seen_file(bad, _add("x")), {})

    def test_mutations_accumulate_across_calls(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            _with_seen_file(path, _add("one"))
            got = _with_seen_file(path, _add("two"))
            self.assertEqual(got, {"one": True, "two": True})
            self.assertEqual(load_seen(path), got)

    def test_threads_do_not_lose_each_others_writes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")

            def worker(n):
                for i in range(25):
                    _with_seen_file(path, _add("%d-%d" % (n, i)))

            threads = [threading.Thread(target=worker, args=(n,))
                       for n in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(load_seen(path)), 100)

    def test_a_non_dict_answer_keeps_what_is_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            _with_seen_file(path, _add("kept"))
            got = _with_seen_file(path, lambda disk: "not a dict")
            self.assertEqual(got, {"kept": True})
            self.assertEqual(load_seen(path), {"kept": True})

    def test_an_unopenable_lock_falls_back_to_a_plain_read(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            _with_seen_file(path, _add("kept"))
            os.unlink(path + ".lock")
            os.makedirs(path + ".lock")
            got = _with_seen_file(path, _add("lost"))
            self.assertEqual(got, {"kept": True})
            self.assertEqual(load_seen(path), {"kept": True})

    def test_a_failed_seed_write_does_not_stop_the_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            real_write = os.write

            def flaky(fd, data):
                if data == b"\0":
                    raise OSError("seed refused")
                return real_write(fd, data)

            with mock.patch.object(os, "write", side_effect=flaky):
                got = _with_seen_file(path, _add("seeded-anyway"))
            self.assertEqual(got, {"seeded-anyway": True})

    def test_the_msvcrt_fallback_locks_and_unlocks(self):
        calls = []
        fake = types.ModuleType("msvcrt")
        fake.LK_LOCK = 2
        fake.LK_UNLCK = 0

        def locking(fd, mode, n):
            calls.append((fd, mode, n))
        fake.locking = locking
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with mock.patch.dict(sys.modules,
                                 {"fcntl": None, "msvcrt": fake}):
                got = _with_seen_file(path, _add("via-msvcrt"))
            self.assertEqual(got, {"via-msvcrt": True})
            self.assertEqual([c[1] for c in calls],
                             [fake.LK_LOCK, fake.LK_UNLCK])

    def test_an_unlock_failure_is_swallowed(self):
        fake = types.ModuleType("msvcrt")
        fake.LK_LOCK = 2
        fake.LK_UNLCK = 0

        def locking(fd, mode, n):
            if mode == fake.LK_UNLCK:
                raise OSError("unlock refused")
        fake.locking = locking
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with mock.patch.dict(sys.modules,
                                 {"fcntl": None, "msvcrt": fake}):
                got = _with_seen_file(path, _add("unlocked-anyway"))
            self.assertEqual(got, {"unlocked-anyway": True})

    def test_a_close_failure_is_swallowed(self):
        real_close = os.close
        state = {"raised": False}

        def close(fd):
            if not state["raised"]:
                state["raised"] = True
                raise OSError("close refused")
            return real_close(fd)

        # ignore_cleanup_errors: the scripted close failure
        # leaks the lock fd on purpose, and Windows will
        # not unlink a file this process still holds open.
        with lenient_tempdir() as d:
            path = os.path.join(d, "seen.json")
            with mock.patch.object(os, "close", side_effect=close):
                got = _with_seen_file(path, _add("closed-anyway"))
            self.assertEqual(got, {"closed-anyway": True})
            self.assertTrue(state["raised"])


if __name__ == "__main__":
    unittest.main()
