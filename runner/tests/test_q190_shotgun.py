#!/usr/bin/env python3
"""Q190 shotgun family: NUL-carrying paths at every sibling
path helper and call site of sandbox.interpreter_binds.

The Q190 fix answered no binds for a NUL-carrying path in
interpreter_binds itself. This family is the queued
scattershot pass around that shape: on the order of 100
derived cases over the sibling helpers and call sites that
hand generated or job-supplied paths to realpath or to a
path rule -- sandbox._install_prefix and _absolute_mount,
the FreeBSD backend's interpreter resolution
(translate_argv), the macOS backend's path rules
(_install_prefix, interpreter_read_paths, _profile_realpath,
build_profile, build_sandbox_argv), and
build_bwrap_command's own interpreter path.

The pinned verdict, everywhere: a path no filesystem can
hold is refused (RuntimeError, the confinement modules'
refusal shape) or skipped (no binds, no prefix), never an
unhandled exception -- in particular never the ValueError
os.path.realpath raises on an embedded NUL.

Cases are bookended per the standing bookend rule: every
printable ASCII symbol plus NUL, tab, CR and LF, at the
front, the back, both ends and the middle, at run lengths
1, 2 and 10 for the NUL runs. The clean-path controls stand
beside the family: a bookend character a filesystem CAN
hold (every symbol but NUL, and tab) never changes a clean
path's verdict class -- the helper answers, it does not
crash.

Suppositions for this family were recorded in
docs/steady/fuzzing.md before the family ran (the Q190
shotgun suppositions paragraph); the conclusions stand
there beside them.
"""
import os
import shutil
import string
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard import sandbox as SB  # noqa: E402
from runner.guard import macos_confine as MC  # noqa: E402
from runner.guard import freebsd_confine as FB  # noqa: E402

# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

HOSTED = "/opt/x64/bin/python3"
SYSTEM = "/usr/bin/python3"

# Every printable ASCII symbol, plus the non-printing edge
# cases the bookend rule names: NUL, tab, CR, LF.
BOOKEND_CHARS = string.punctuation + "\x00\t\r\n"


def bookended(base, ch, count=1):
    """`base` with a run of `ch` at each bookend position."""
    run = ch * count
    return (run + base, base + run, run + base + run,
            base[:6] + run + base[6:])


def nul_bookends(base):
    out = []
    for count in (1, 2, 10):
        out.extend(bookended(base, "\x00", count))
    out.append("\x00")
    out.append("/\x00")
    return out


class SandboxInstallPrefixNulTest(unittest.TestCase):
    """sandbox._install_prefix on a NUL-carrying path: no
    prefix (the skip shape), never a prefix string that
    itself carries the NUL out to a bind."""

    def test_nul_bookends_answer_no_prefix(self):
        cases = nul_bookends(HOSTED)
        self.assertGreaterEqual(len(cases), 12)
        for path in cases:
            with self.subTest(path=path):
                self.assertIsNone(SB._install_prefix(path))

    def test_symbol_bookends_never_crash(self):
        for ch in BOOKEND_CHARS:
            if ch == "\x00":
                continue
            for path in bookended(HOSTED, ch):
                with self.subTest(path=path):
                    # A symbol a filesystem can hold: the
                    # helper answers (a prefix or None).
                    result = SB._install_prefix(path)
                    self.assertTrue(result is None
                                    or isinstance(result, str))

    def test_clean_prefix_control(self):
        self.assertEqual(SB._install_prefix(HOSTED), "/opt/x64")
        self.assertIsNone(SB._install_prefix("/bin/sh"))


class SandboxAbsoluteMountNulTest(unittest.TestCase):
    """sandbox._absolute_mount on a NUL-carrying mount: the
    clean RuntimeError refusal it already gives."""

    def test_nul_bookends_refused(self):
        for path in nul_bookends("/work"):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    SB._absolute_mount(path, "work_mount")

    def test_cr_lf_bookends_refused(self):
        for ch in ("\r", "\n"):
            for path in bookended("/work", ch):
                with self.subTest(path=path):
                    with self.assertRaises(RuntimeError):
                        SB._absolute_mount(path, "work_mount")

    def test_clean_mount_control(self):
        self.assertIsNone(SB._absolute_mount("/work", "work_mount"))


class InterpreterBindsBookendFamilyTest(unittest.TestCase):
    """The Q190 seat's own helper, re-driven by this second
    seat with the full bookend alphabet: NUL answers no
    binds; every other bookend answers a list, never a
    ValueError out of realpath."""

    def test_nul_runs_answer_no_binds(self):
        for path in nul_bookends(HOSTED) + nul_bookends(SYSTEM):
            with self.subTest(path=path):
                self.assertEqual(SB.interpreter_binds(path, []), [])

    def test_every_bookend_char_answers_a_list(self):
        cases = 0
        for ch in BOOKEND_CHARS:
            for path in bookended(HOSTED, ch):
                cases += 1
                with self.subTest(ch=ch, path=path):
                    self.assertIsInstance(
                        SB.interpreter_binds(path, []), list)
        self.assertGreaterEqual(cases, 100)


class MacosPathRulesNulTest(unittest.TestCase):
    """The macOS backend's path rules: the mirror
    _install_prefix skips a NUL path, interpreter_read_paths
    and _profile_realpath refuse one with RuntimeError --
    never the ValueError realpath raises."""

    def test_install_prefix_nul_bookends_skip(self):
        for path in nul_bookends(HOSTED):
            with self.subTest(path=path):
                self.assertIsNone(MC._install_prefix(path))

    def test_install_prefix_clean_control(self):
        self.assertEqual(MC._install_prefix(HOSTED), "/opt/x64")

    def test_interpreter_read_paths_nul_path_refused(self):
        for path in nul_bookends(HOSTED):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    MC.interpreter_read_paths(path)

    def test_interpreter_read_paths_nul_bare_refused(self):
        for name in nul_bookends("python3"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    MC.interpreter_read_paths(name)

    def test_profile_realpath_nul_refused(self):
        for path in nul_bookends(HOSTED):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    MC._profile_realpath(path)

    def test_build_profile_nul_interpreter_refused(self):
        for path in nul_bookends(HOSTED):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    MC.build_profile("/work", interpreter=path)

    def test_build_profile_nul_workdir_refused(self):
        for path in nul_bookends("/work"):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    MC.build_profile(path)

    def test_build_sandbox_argv_nul_refused(self):
        for path in nul_bookends(HOSTED):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    MC.build_sandbox_argv([path, "s.py"], cwd="/work")
        for path in nul_bookends("/work"):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    MC.build_sandbox_argv([SYSTEM, "s.py"], cwd=path)

    def test_clean_controls(self):
        # The macOS hosted shape stands outside the system
        # trees (/opt is one of them there): /srv/x64.
        self.assertEqual(MC.interpreter_read_paths(SYSTEM), [])
        self.assertEqual(
            MC.interpreter_read_paths("/srv/x64/bin/python3"),
            ["/srv/x64"])
        profile = MC.build_profile(
            "/work", interpreter="/srv/x64/bin/python3")
        self.assertIn("/srv/x64", profile)


class FreeBsdInterpreterResolutionNulTest(unittest.TestCase):
    """The FreeBSD backend's interpreter resolution
    (translate_argv, the call site that hands a job's own
    argv[0] to interpreter_binds): a NUL-carrying
    interpreter is refused with RuntimeError, never an
    unhandled ValueError."""

    def setUp(self):
        self.st = FB.confinement_settings({})

    def test_nul_path_interpreter_refused(self):
        for path in nul_bookends(HOSTED) + nul_bookends(SYSTEM):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    FB.translate_argv([path], "/tmp/w", self.st)

    def test_nul_bare_interpreter_refused(self):
        for name in nul_bookends("python3"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    FB.translate_argv([name], "/tmp/w", self.st)

    def test_clean_control(self):
        out, prefixes = FB.translate_argv(
            [SYSTEM, "x"], "/tmp/w", self.st)
        self.assertEqual(out, [SYSTEM, "x"])
        self.assertEqual(prefixes, [])


class BuildBwrapInterpreterNulTest(unittest.TestCase):
    """build_bwrap_command's own interpreter path (and its
    workdir and script fields): a NUL anywhere in them is
    the clean RuntimeError refusal."""

    def test_nul_interpreter_refused(self):
        for name in nul_bookends("python3") + nul_bookends(SYSTEM):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    SB.build_bwrap_command(
                        {}, [name], "s.sh", "/tmp/w", [], {})

    def test_nul_workdir_and_script_refused(self):
        for path in nul_bookends("/tmp/w"):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    SB.build_bwrap_command(
                        {}, ["sh"], "s.sh", path, [], {})
        for name in nul_bookends("s.sh"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    SB.build_bwrap_command(
                        {}, ["sh"], name, "/tmp/w", [], {})

    def test_clean_control_still_builds(self):
        argv = SB.build_bwrap_command(
            {}, ["sh"], "s.sh", "/tmp/w", [], {})
        self.assertEqual(argv[0], SB.BWRAP_BIN)
        # The interpreter the host resolves is the one the
        # command carries: /usr/bin/sh on the POSIX legs, and
        # on a Windows host whatever sh the PATH offers (the
        # Git sh, on the hosted legs). The control is that a
        # clean name still builds -- not which sh the host
        # happens to have.
        self.assertIn(shutil.which("sh"), argv)


if __name__ == "__main__":
    unittest.main(verbosity=2)
