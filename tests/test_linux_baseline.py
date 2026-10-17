"""Linux detection baseline: mode 0600, and a symlink is not followed.

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

from runner.detection import baseline_anomaly, update_baseline


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _path(base):
    return os.path.join(base, "detection-baseline.json")


def _tmp(base):
    return _path(base) + ".tmp." + str(threading.get_ident())


class BaselineFileTest(unittest.TestCase):
    def test_counts_are_owner_only_and_capped(self):
        with tempfile.TemporaryDirectory() as d:
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if str(path).endswith(".tmp." + str(threading.get_ident())):
                    seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy):
                got = update_baseline(d, {"kind": "ping"}, {"stdout": "hi"})
            self.assertEqual(got["kinds"]["ping"], 1)
            self.assertEqual(got["output_sizes"], [2])
            path = _path(d)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertFalse(os.path.exists(_tmp(d)))
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))
            for i in range(60):
                update_baseline(d, {"kind": "ping"}, {"stdout": "x" * (i + 1)})
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(len(saved["output_sizes"]), 50)
            self.assertEqual(saved["output_sizes"][-1], 60)
            self.assertEqual(saved["kinds"]["ping"], 61)
            self.assertEqual(_mode(path), 0o600)

    def test_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"kinds": {"ping": 99}, "secret": true}\n')
            path = _path(d)
            os.symlink(target, path)
            link = _tmp(d)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with mock.patch("os.unlink", side_effect=leave_the_link):
                got = update_baseline(d, {"kind": "ping"}, {"stdout": "a"})
            self.assertEqual(got["kinds"]["ping"], 1)
            self.assertNotIn("secret", got)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(path))
            os.unlink(link)
            got = update_baseline(d, {"kind": "exec"}, {"stdout": "ab"})
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            self.assertEqual(got["kinds"]["exec"], 1)
            self.assertNotIn("ping", got["kinds"])
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class BaselineMutations(unittest.TestCase):
    def test_bad_jobs_do_not_raise_or_escape(self):
        for base in (None, "", 5):
            self.assertEqual(update_baseline(base, {"kind": "ping"}), {})
        with tempfile.TemporaryDirectory() as d:
            got = update_baseline(d, None, None)
            self.assertEqual(got["kinds"], {"unknown": 1})
            got = update_baseline(d, {"kind": "a\x00b"}, {"stdout": b"nope"})
            self.assertIn("unknown", got["kinds"])
            self.assertNotIn("a\x00b", got["kinds"])
            self.assertEqual(got["output_sizes"], [])
            got = update_baseline(d, {"kind": 1}, {"stdout": "zz"})
            self.assertEqual(got["kinds"]["unknown"], 3)
            self.assertEqual(got["output_sizes"], [2])
            path = _path(d)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"kinds": {"ping": "nope"}, "output_sizes": ["x", 4]}\n')
            got = update_baseline(d, {"kind": "ping"}, {"stdout": "abcd"})
            self.assertEqual(got["kinds"]["ping"], 1)
            self.assertEqual(got["output_sizes"], [4, 4])
            sizes = [10] * 12
            reason = baseline_anomaly(
                {"output_sizes": sizes, "kinds": {"ping": 30}},
                {"kind": "other"},
                {"stdout": "y" * 200})
            self.assertEqual(reason, "output_size_anomaly")
            self.assertIsNone(baseline_anomaly("nope", {"kind": "ping"}))


class BaselineFuzzTest(unittest.TestCase):
    def test_random_jobs_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(160):
                job = rng.choice([
                    {"kind": rng.choice(["ping", "exec", "", "a\x00b", None])},
                    None,
                    {"kind": i},
                ])
                result = rng.choice([
                    {"stdout": "x" * rng.randrange(0, 30)},
                    {"stdout": b"no"},
                    None,
                    [],
                ])
                try:
                    got = update_baseline(d, job, result)
                    reason = baseline_anomaly(got, job if isinstance(job, dict) else {}, result)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(got, dict) or not isinstance(got.get("kinds"), dict):
                    crashes.append("shape")
                    break
                sizes = got.get("output_sizes") or []
                if len(sizes) > 50:
                    crashes.append(len(sizes))
                    break
                if reason is not None and not isinstance(reason, str):
                    crashes.append(reason)
                    break
            path = _path(d)
            if os.path.isfile(path) and not os.path.islink(path):
                if _mode(path) != 0o600:
                    crashes.append(oct(_mode(path)))
            link = _tmp(d)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            try:
                update_baseline(d, {"kind": "ping"}, {"stdout": "z"})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
