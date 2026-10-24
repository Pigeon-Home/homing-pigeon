"""Linux diagnose report: mode 0600, and a symlink is not followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Sections are stubs. Nothing here sends mail or starts a process.
A planted symlink is not written through.
"""
import glob
import os
import random
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from runner.ops import harness as H


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _ok(ctx, sec):
    sec.verdict(H.PASS, "fine")
    sec.note("evidence")


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class _Clock:
    @staticmethod
    def now(tz=None):
        return datetime(2026, 10, 17, 0, 0, 0, tzinfo=timezone.utc)


class ReportFileTest(unittest.TestCase):
    def test_the_report_is_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            lines = []
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if str(path).endswith(".txt"):
                    seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy):
                fails = H.run_diagnose(
                    {}, out=lines.append, base_dir=d, sections=[("first", _ok)])
            self.assertEqual(fails, 0)
            reports = glob.glob(os.path.join(d, "harness-report-*.txt"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(_mode(reports[0]), 0o600)
            self.assertFalse(os.path.islink(reports[0]))
            with open(reports[0], encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("== first — PASS", text)
            self.assertIn("evidence", text)
            self.assertTrue(any("report written" in line for line in lines))
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))

    def test_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            link = os.path.join(d, "harness-report-20261017T000000Z.txt")
            os.symlink(target, link)
            lines = []
            with mock.patch("runner.ops.harness.datetime", _Clock):
                fails = H.run_diagnose(
                    {}, out=lines.append, base_dir=d, sections=[("first", _ok)])
            self.assertEqual(fails, 0)
            self.assertTrue(os.path.islink(link))
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(any("could not write report file" in line for line in lines))
            self.assertTrue(any("evidence" in line for line in lines))


class ReportMutations(unittest.TestCase):
    def test_bad_dirs_and_sections_do_not_raise(self):
        lines = []

        def boom(ctx, sec):
            raise RuntimeError("kaboom")

        def odd(ctx, sec):
            sec.note("a\nb")
            sec.verdict(H.INFO, "odd")

        with tempfile.TemporaryDirectory() as d:
            blocked = os.path.join(d, "blocked")
            with open(blocked, "w", encoding="utf-8") as fh:
                fh.write("not a dir")
            fails = H.run_diagnose(
                None, out=lines.append, base_dir=blocked,
                sections=[("bad", boom), ("odd", odd)])
            self.assertEqual(fails, 1)
            self.assertTrue(any("kaboom" in line for line in lines))
            self.assertEqual(glob.glob(os.path.join(d, "harness-report-*.txt")), [])
            fails = H.run_diagnose(
                {"shared_secret": "nope"}, out=lines.append, base_dir=d,
                sections=[])
            self.assertEqual(fails, 0)
            reports = glob.glob(os.path.join(d, "harness-report-*.txt"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(_mode(reports[0]), 0o600)
            with open(reports[0], encoding="utf-8") as fh:
                self.assertNotIn("nope", fh.read())


class ReportFuzzTest(unittest.TestCase):
    def test_random_sections_stay_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(40):
                base = os.path.join(d, "r%d" % i)
                status = rng.choice([H.PASS, H.FAIL, H.INFO])
                note = "".join(rng.choice("abc \t") for _ in range(rng.randrange(0, 12)))

                def section(ctx, sec, status=status, note=note):
                    if rng.random() < 0.1:
                        raise RuntimeError("boom")
                    sec.note(note)
                    sec.verdict(status, "s")

                lines = []
                try:
                    H.run_diagnose({}, out=lines.append, base_dir=base,
                                   sections=[("s%d" % i, section)])
                    reports = glob.glob(os.path.join(base, "harness-report-*.txt"))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if len(reports) != 1 or _mode(reports[0]) != 0o600:
                    crashes.append("mode")
                    break
                if os.path.islink(reports[0]):
                    crashes.append("link")
                    break
            link = os.path.join(d, "r0", "harness-report-20261017T000000Z.txt")
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(target, link)
            try:
                with mock.patch("runner.ops.harness.datetime", _Clock):
                    H.run_diagnose({}, out=lambda _line: None, base_dir=os.path.join(d, "r0"),
                                   sections=[("first", _ok)])
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
