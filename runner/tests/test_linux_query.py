"""Linux query window. A symlink is not the rate-limit store.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not read.
"""
import json
import os
import random
import tempfile
import time
import unittest

from runner.runner import budget_status, check_rate_limit


def _mode(path):
    return os.stat(path).st_mode & 0o777


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class QueryReadTest(unittest.TestCase):
    def test_a_symlink_window_does_not_deny_the_query(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "queries.json")
            target = os.path.join(d, "target")
            now = time.time()
            with open(target, "w", encoding="utf-8") as fh:
                json.dump({"owner": [now, now], "secret": [now]}, fh)
            os.symlink(target, path)
            self.assertEqual(budget_status(path, {"max_queries_per_hour": 1}), [])
            allowed = check_rate_limit(
                "owner", {"max_queries_per_hour": 1}, path)
            self.assertTrue(allowed)
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertNotIn("secret", saved)
            self.assertEqual(len(saved["owner"]), 1)
            with open(target, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("secret", body)
            denied = check_rate_limit(
                "owner", {"max_queries_per_hour": 1}, path)
            self.assertFalse(denied)


class QueryMutations(unittest.TestCase):
    def test_bad_stores_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "queries.json")
            cfg = {"max_queries_per_hour": 2}
            self.assertTrue(check_rate_limit("owner", cfg, path))
            self.assertEqual(budget_status(path, cfg)[0]["spent"], 1)
            for body in ("[]", "null", "1", "nope"):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
                self.assertEqual(budget_status(path, cfg), [])
                self.assertTrue(check_rate_limit("other", cfg, path))
            self.assertEqual(budget_status("", cfg), [])
            self.assertEqual(budget_status(None, cfg), [])
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            link = os.path.join(d, "link.json")
            os.symlink(target, link)
            self.assertTrue(check_rate_limit(
                "owner", {"max_queries_per_hour": 0}, link))
            self.assertTrue(os.path.islink(link))
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class QueryFuzzTest(unittest.TestCase):
    def test_random_windows_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "queries.json")
            target = os.path.join(d, "target")
            now = time.time()
            with open(target, "w", encoding="utf-8") as fh:
                json.dump({"owner": [now] * 5, "secret": True}, fh)
            for i in range(80):
                body = rng.choice([
                    json.dumps({"k%d" % i: [now]}),
                    "[]",
                    "null",
                    "nope",
                    json.dumps({"owner": "bad"}),
                ])
                limit = rng.choice([1, 2, 5])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    allowed = check_rate_limit(
                        "owner", {"max_queries_per_hour": limit}, path)
                    rows = budget_status(path, {"max_queries_per_hour": limit})
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(allowed, bool) or not isinstance(rows, list):
                    crashes.append("shape")
                    break
                if os.path.isfile(path) and not os.path.islink(path):
                    if _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
                        break
            os.remove(path)
            os.symlink(target, path)
            try:
                if budget_status(path, {"max_queries_per_hour": 1}) != []:
                    crashes.append("status")
                if not check_rate_limit("owner", {"max_queries_per_hour": 1}, path):
                    crashes.append("denied")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if "secret" not in fh.read():
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
