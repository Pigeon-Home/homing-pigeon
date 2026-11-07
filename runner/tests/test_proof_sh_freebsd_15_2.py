#!/usr/bin/env python3
"""Content checks with the FreeBSD 15.2 shell.

The 15.0 record (`content-sh-freebsd.md`) asked FreeBSD's
`/bin/sh` to parse the content-series rungs, inside the
guest `freebsd.yml` boots, and it did. This harness is
the same series aimed at the next shell: FreeBSD 15.2,
whose BETA1 builds began on 2026-11-06. The target is
that release's `/bin/sh` only. A 15.0 shell is a different
program for this record, and so are dash and bash: none
of them is run in its place, and a run of any of them is
not a result here.

Two halves, the split `content-sh-freebsd-design.md`
settled for 15.0:

- The parser half: `sh -n` over the same catalog the
  macOS and 15.0 files use (the 49-character set, then
  5,000, 50,000, 500,000, and the production cap, one
  command per line, and one byte over each rung).
- The execution half: the catalog actually runs under
  the 15.2 shell -- the first rung whole, a set of atoms
  whose output is pinned, and the 5,000 rung -- because
  parsing a script and running it are different things
  a new shell can disagree on.

The gate half is not asked again. `handle_mail` does not
parse the script, and its answers on these same texts
stand in the content series.

Where the shell comes from, in order:
`HP_FREEBSD_15_2_SH`, `HP_FREEBSD_SH`,
`/tmp/freebsd-sh-15.2`, and -- only on a FreeBSD host,
where the name means the base-system shell -- `/bin/sh`.
On any other host `/bin/sh` is never taken: on Linux it
is dash, and dash was not used in its place.

The release gate is as strict as the binary gate. The
release text is read from `HP_FREEBSD_15_2_RELEASE` when
set, else from `freebsd-version`, else from `uname -r`
on a FreeBSD host, and it must be a bare 15.2 version
(`15.2-BETA1`, `15.2-RELEASE-p1`, and their kin). Any
other release skips, with the reason stated, instead of
letting an older shell answer for 15.2.

The target and catalog tests below run on every machine
and pin the shape of this harness itself. The shell
tests skip where no 15.2 shell is present. A skip is
not a pass, and the first-run record in
`content-sh-freebsd-15-2.md` says plainly what ran.
"""
import os
import re
import shutil
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.tests.proof_sh_build import (  # noqa: E402
    at_length, enumerate49)

CAP = 1048576
TARGET = "15.2"

_BARE_15_2 = re.compile(r"15\.2(-[A-Za-z0-9]+)*\Z")


def release_is_15_2(text):
    """True only for a bare 15.2 release string.

    `freebsd-version` and `uname -r` answer with the bare
    string and nothing else, so anything longer -- a full
    `uname -v`, a sentence -- is not evidence and is
    refused rather than searched for a hopeful substring.
    """
    if not text:
        return False
    return bool(_BARE_15_2.match(text.strip()))


def _host_is_freebsd():
    uname = getattr(os, "uname", None)
    return bool(uname) and uname().sysname == "FreeBSD"


def host_release():
    """The release text this machine offers as evidence."""
    stated = os.environ.get("HP_FREEBSD_15_2_RELEASE")
    if stated:
        return stated.strip()
    if not _host_is_freebsd():
        return ""
    tool = shutil.which("freebsd-version")
    if tool:
        proc = subprocess.run(
            [tool], text=True, capture_output=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    proc = subprocess.run(
        ["uname", "-r"], text=True, capture_output=True)
    if proc.returncode == 0:
        return proc.stdout.strip()
    return ""


def find_15_2_sh():
    """The 15.2 shell binary, or None. Never a substitute."""
    for candidate in (os.environ.get("HP_FREEBSD_15_2_SH"),
                      os.environ.get("HP_FREEBSD_SH"),
                      "/tmp/freebsd-sh-15.2"):
        if candidate and os.path.isfile(candidate) \
                and os.access(candidate, os.X_OK):
            return candidate
    if _host_is_freebsd() and os.path.isfile("/bin/sh") \
            and os.access("/bin/sh", os.X_OK):
        return "/bin/sh"
    return None


class TargetShapeTest(unittest.TestCase):
    """The harness's own shape. These run on every machine."""

    def test_bare_15_2_release_strings_are_the_target(self):
        for text in ("15.2", "15.2-BETA1", "15.2-BETA2",
                     "15.2-PRERELEASE", "15.2-STABLE",
                     "15.2-RELEASE", "15.2-RELEASE-p1",
                     " 15.2-BETA1 \n"):
            self.assertTrue(release_is_15_2(text), text)

    def test_other_releases_are_not_the_target(self):
        for text in ("15.0-RELEASE-p13", "15.1-RELEASE",
                     "14.3-RELEASE", "15.20-BETA1",
                     "115.2-BETA1", "13.5-RELEASE", ""):
            self.assertFalse(release_is_15_2(text), text)

    def test_prose_is_not_release_evidence(self):
        self.assertFalse(release_is_15_2("FreeBSD 15.2-BETA1"))
        self.assertFalse(release_is_15_2(
            "FreeBSD hostname 15.2-BETA1 FreeBSD 15.2-BETA1 "
            "amd64"))
        self.assertFalse(release_is_15_2(None))

    def test_the_catalog_is_the_series_catalog(self):
        scripts = enumerate49()
        self.assertEqual(len(scripts), 3269)
        self.assertTrue(all(len(s) <= 49 for s in scripts))
        for n in (5000, 50000, 500000, CAP, CAP + 1):
            for start in (0, 5, 11):
                self.assertEqual(len(at_length(n, start)), n)

    def test_a_non_freebsd_host_never_offers_its_bin_sh(self):
        if _host_is_freebsd():
            self.skipTest("this leg pins the non-FreeBSD "
                          "finder rule and runs on the other hosts")
        self.assertNotEqual(find_15_2_sh(), "/bin/sh")


class FreeBSD15_2ShTest(unittest.TestCase):
    """The 15.2 shell itself. Skips where it is absent."""

    @classmethod
    def setUpClass(cls):
        cls.binary = find_15_2_sh()
        cls.release = host_release()

    def setUp(self):
        if not self.binary:
            self.skipTest(
                "FreeBSD sh is not on this machine. Its sources "
                "are the FreeBSD base system and do not build "
                "with the Linux toolchain here, and qemu-user "
                "runs Linux binaries, not FreeBSD ones. dash "
                "was not used in its place")
        if not release_is_15_2(self.release):
            self.skipTest(
                "the FreeBSD release here is not 15.2, so its "
                "sh is not the 15.2 shell this harness targets")

    def _syntax(self, script):
        return subprocess.run(
            [self.binary, "-n"], input=script + "\n",
            text=True, capture_output=True)

    def _execute(self, script, **kw):
        return subprocess.run(
            [self.binary], input=script + "\n",
            text=True, capture_output=True, **kw)

    def test_the_release_is_the_target(self):
        self.assertTrue(self.release.startswith(TARGET),
                        self.release)
        self.assertTrue(release_is_15_2(self.release),
                        self.release)

    def test_parser_first_rung(self):
        scripts = enumerate49()
        self.assertEqual(len(scripts), 3269)
        self.assertTrue(all(len(s) <= 49 for s in scripts))
        joined = self._syntax("\n".join(scripts))
        self.assertEqual(joined.returncode, 0, joined.stderr[-300:])

    def test_parser_the_long_rungs(self):
        for n in (5000, 50000, 500000, CAP):
            texts = []
            for start in (0, 5, 11):
                script = at_length(n, start)
                texts.append(script)
                self.assertEqual(len(script), n)
                proc = self._syntax(script)
                self.assertEqual(
                    proc.returncode, 0,
                    "%d %s" % (n, proc.stderr[-200:]))
            self.assertEqual(len(set(texts)), 3)
            over = at_length(n + 1, 0)
            self.assertEqual(len(over), n + 1)
            proc = self._syntax(over)
            self.assertEqual(proc.returncode, 0, proc.stderr[-200:])

    def test_execution_first_rung(self):
        scripts = enumerate49()
        joined = self._execute("\n".join(scripts))
        self.assertEqual(joined.returncode, 0, joined.stderr[-300:])

    def test_execution_outputs_are_pinned(self):
        cases = (
            ("echo a", "a\n"),
            ("echo 'a b'", "a b\n"),
            ('echo "x y"', "x y\n"),
            ("echo $((1+2))", "3\n"),
            ("printf x", "x"),
            (":", ""),
            ("true", ""),
            ("for i in a; do echo $i; done", "a\n"),
            ("f(){ echo a; }; f", "a\n"),
            ("(echo a)", "a\n"),
            ("echo a && echo b", "a\nb\n"),
            ("echo a || true", "a\n"),
        )
        for script, want in cases:
            proc = subprocess.run(
                [self.binary, "-c", script],
                text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, script)
            self.assertEqual(proc.stdout, want, script)

    def test_execution_the_5000_rung(self):
        script = at_length(5000, 0)
        self.assertEqual(len(script), 5000)
        proc = subprocess.run(
            [self.binary], input=script + "\n",
            text=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr[-200:])


if __name__ == "__main__":
    unittest.main()
