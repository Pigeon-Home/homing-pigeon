"""Linux security audit files: mode 0600, and no symlink is followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not written
through.
"""
import json
import os
import random
import tempfile
import unittest
from unittest import mock

from runner.security import (
    COUNTS_FILE, bump_evaluated, write_audit_entry)


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _counts_tmp(base):
    return os.path.join(base, COUNTS_FILE + ".tmp." + str(os.getpid()))


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class AuditFileTest(unittest.TestCase):
    def test_an_entry_is_owner_only_and_the_count_increments(self):
        with tempfile.TemporaryDirectory() as d:
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if str(path).endswith(("security-audit.jsonl",
                                       COUNTS_FILE + ".tmp." + str(os.getpid()))):
                    seen.append((os.path.basename(str(path)), flags))
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy):
                write_audit_entry(d, "audience", "denied", "why",
                                  key_id="k", job_id="job.1", mode="enforce")
                write_audit_entry(d, "audience", "denied", "again")
            audit = os.path.join(d, "security-audit.jsonl")
            counts_path = os.path.join(d, COUNTS_FILE)
            self.assertEqual(_mode(audit), 0o600)
            self.assertEqual(_mode(counts_path), 0o600)
            self.assertFalse(os.path.islink(audit))
            with open(audit, encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["decision"], "denied")
            with open(counts_path, encoding="utf-8") as fh:
                counts = json.load(fh)
            self.assertEqual(counts["audience"]["denied"], 2)
            audit_flags = [flags for name, flags in seen
                           if name == "security-audit.jsonl"]
            count_flags = [flags for name, flags in seen if name.startswith(COUNTS_FILE)]
            self.assertTrue(audit_flags)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in audit_flags))
            self.assertTrue(all(flags & os.O_APPEND for flags in audit_flags))
            self.assertTrue(count_flags)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in count_flags))
            self.assertTrue(all(flags & os.O_EXCL for flags in count_flags))
            self.assertFalse(os.path.exists(_counts_tmp(d)))

    def test_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            audit = os.path.join(d, "security-audit.jsonl")
            counts = os.path.join(d, COUNTS_FILE)
            os.symlink(target, audit)
            os.symlink(target, counts)
            link = _counts_tmp(d)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with mock.patch("os.unlink", side_effect=leave_the_link):
                write_audit_entry(d, "audience", "denied", "why")
                bump_evaluated(d, "audience")
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(audit))
            self.assertTrue(os.path.islink(counts))
            self.assertTrue(os.path.islink(link))


class AuditMutations(unittest.TestCase):
    def test_bad_inputs_do_not_raise_or_follow_a_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for base in (None, "", 5, os.path.join(d, "missing")):
                write_audit_entry(base, "audience", "denied", "why")
                bump_evaluated(base, "audience")
            self.assertFalse(os.path.exists("security-audit.jsonl"))
            self.assertFalse(os.path.exists(COUNTS_FILE))
            write_audit_entry(d, None, None, None, detail=object())
            path = os.path.join(d, "security-audit.jsonl")
            if os.path.isfile(path) and not os.path.islink(path):
                self.assertEqual(_mode(path), 0o600)
            os.symlink(target, os.path.join(d, "sub"))
            write_audit_entry(os.path.join(d, "sub"), "audience", "denied", "x")
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class AuditFuzzTest(unittest.TestCase):
    def test_random_entries_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            features = ["audience", "job_user", "confinement", "", None, 1]
            decisions = ["denied", "would_deny", "evaluated", "", None]
            for i in range(160):
                try:
                    write_audit_entry(
                        d,
                        rng.choice(features),
                        rng.choice(decisions),
                        rng.choice(["why", "", None, "a\nb"]),
                        key_id=rng.choice(["k", "", None]),
                        job_id=rng.choice(["job.1", "a/b", ""]),
                        detail=rng.choice(["d", "", None, {"n": i}]),
                        mode=rng.choice(["audit", "enforce", None, ""]),
                    )
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
            for name in ("security-audit.jsonl", COUNTS_FILE):
                path = os.path.join(d, name)
                if os.path.isfile(path) and not os.path.islink(path):
                    if _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
            counts_path = os.path.join(d, COUNTS_FILE)
            if os.path.isfile(counts_path):
                with open(counts_path, encoding="utf-8") as fh:
                    counts = json.load(fh)
                if not isinstance(counts, dict):
                    crashes.append(type(counts).__name__)
            planted = os.path.join(d, "planted")
            os.makedirs(planted)
            os.symlink(target, os.path.join(planted, "security-audit.jsonl"))
            os.symlink(target, os.path.join(planted, COUNTS_FILE))
            try:
                write_audit_entry(planted, "audience", "denied", "x")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
