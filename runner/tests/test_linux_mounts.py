"""Linux bwrap mounts: absolute, no null, no newline, no .. segment.

Unit cases, one-field mutations, and a deterministic fuzz. which()
is mocked. Nothing here execs bwrap or a job.
"""
import random
import unittest
from unittest import mock

from runner.guard import sandbox as SB


def _build(**conf):
    with mock.patch.object(SB.shutil, "which", return_value="/bin/sh"):
        return SB.build_bwrap_command(
            {"security": {"confinement": conf}},
            ["sh"], "job.sh", "/var/lib/pigeon", [], {})


class MountUnitTest(unittest.TestCase):
    def test_a_clean_mount_is_the_bind_and_the_script_prefix(self):
        argv = _build(
            work_mount="/job",
            extra_flags=["--unshare-pid"],
            extra_ro_binds=[["/opt/data", "/data"]],
        )
        self.assertEqual(argv[argv.index("--chdir") + 1], "/job")
        self.assertIn("/job/job.sh", argv)
        self.assertLess(argv.index("/opt/data"), argv.index("--bind"))
        self.assertNotIn("..", argv)

    def test_the_default_mount_stays_work(self):
        argv = _build()
        self.assertEqual(argv[argv.index("--chdir") + 1], "/work")
        self.assertIn("/work/job.sh", argv)


class MountMutations(unittest.TestCase):
    def _reject_block(self, **conf):
        with self.assertRaises(RuntimeError):
            SB._validate_confinement_block(conf)

    def _reject_build(self, **conf):
        with mock.patch.object(SB.shutil, "which",
                               side_effect=AssertionError("which")):
            with self.assertRaises(RuntimeError):
                SB.build_bwrap_command(
                    {"security": {"confinement": conf}},
                    ["sh"], "job.sh", "/work", [], {})

    def test_one_bad_field_is_refused_before_which(self):
        good = {
            "work_mount": "/job",
            "extra_flags": ["--die-with-parent"],
            "extra_ro_binds": [["/opt/data", "/data"]],
        }
        self.assertTrue(SB._validate_confinement_block(good))
        for bad in (
            {"work_mount": "/job/../etc"},
            {"work_mount": "/job\x00"},
            {"work_mount": "/job\n"},
            {"work_mount": "relative"},
            {"extra_flags": ["--ok\x00"]},
            {"extra_flags": ["--ok\n"]},
            {"extra_flags": ["/job/../etc"]},
            {"extra_flags": [""]},
            {"extra_ro_binds": [["../etc", "/data"]]},
            {"extra_ro_binds": [["/opt", "/data/../x"]]},
            {"extra_ro_binds": [["/opt\n", "/data"]]},
            {"extra_ro_binds": [["opt", "/data"]]},
        ):
            self._reject_block(**bad)
            self._reject_build(**bad)

    def test_a_dot_dot_inside_a_name_is_not_a_segment(self):
        self.assertTrue(SB._validate_confinement_block(
            {"work_mount": "/job..bak"}))
        argv = _build(work_mount="/job..bak")
        self.assertIn("/job..bak/job.sh", argv)


class MountFuzzTest(unittest.TestCase):
    def test_random_mounts_reject_or_stay_inside_the_argv(self):
        rng = random.Random(20261017)
        crashes = []

        def path():
            roll = rng.randrange(6)
            if roll == 0:
                return rng.choice([
                    "/job", "/work", "/", "/opt/data", "/data",
                    "/job/../etc", "relative", "", "/job\x00", "/a\nb",
                    "..", "/foo..bar",
                ])
            if roll == 1:
                return "/" + "".join(
                    chr(rng.randrange(32, 127)) for _ in range(rng.randrange(0, 8)))
            if roll == 2:
                return rng.choice([None, 1, True, [], {}])
            return "/" + rng.choice(["ok", "..", "a", ""])

        for _ in range(300):
            block = {
                "work_mount": path(),
                "extra_flags": [path() if rng.randrange(4) == 0 else "--die-with-parent"],
                "extra_ro_binds": [[path(), path()]],
            }
            if rng.randrange(5) == 0:
                block = rng.choice([None, [], "x", {}])
            try:
                ok = SB._validate_confinement_block(block)
            except RuntimeError:
                continue
            except Exception as exc:
                crashes.append(("validate", type(exc).__name__))
                break
            if ok is not True:
                crashes.append(("return", ok))
                break
            try:
                with mock.patch.object(SB.shutil, "which",
                                       return_value="/bin/sh"):
                    argv = SB.build_bwrap_command(
                        {"security": {"confinement": block}},
                        ["sh"], "job.sh", "/work", [], {})
            except RuntimeError:
                continue
            except Exception as exc:
                crashes.append(("build", type(exc).__name__))
                break
            if argv[0] != "bwrap" or not all(isinstance(x, str) for x in argv):
                crashes.append(("argv", argv[:4]))
                break
            if any("\x00" in x or "\n" in x or ".." in x.split("/") for x in argv):
                crashes.append(("escape", argv))
                break
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
