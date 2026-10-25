# The Windows-portability lint for the suite itself: the fixture
# shapes that pass on Linux and fail on Windows, caught on Linux.
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""On 2026-10-25 the campaign landed a test a minute and four
release builds in a row went red on Windows, each time on a fixture
that only works on POSIX: a counter of os.stat calls meant to catch
a path probe (Python 3.12+ answers os.path.isfile in C on Windows,
so the probe never shows), a patch of an os attribute Windows does
not have (getuid, getloadavg, setgroups) without create=True, a
fake os.close that never releases the descriptor (Windows then
cannot remove the file), and chmod 000 standing in for an
unreadable file (not unreadable there). Shell scripts and `sleep`
are not flagged: Git for Windows puts sh, bash and the coreutils on
the runner's PATH, and those fixtures do run there; what fails is
a script on PATH under a bare binary name, which which() cannot
find without an extension, and that one needs a POSIX skip.

Windows takes ten minutes to say so; this says so in the Linux
test job and on the campaign rig before the push. Each rule names
the shape and the portable form. A line that is right for a reason
the rule cannot see carries `# portable: <why>` and is skipped.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SUITE = os.path.join(ROOT, "runner", "tests")

# os attributes that do not exist on Windows: a patch of one needs
# create=True or the test errors there before it asserts anything.
POSIX_ONLY_OS = (
    "getuid", "geteuid", "getgid", "getegid", "getgroups", "getloadavg",
    "setgroups", "setuid", "setgid", "seteuid", "setegid", "initgroups",
    "killpg", "fork", "chown", "lchown", "chroot", "mkfifo", "mknod",
    "statvfs", "getpgid", "setsid", "getpgrp", "setpgid", "uname",
    "fchmod", "fchown", "nice", "openpty", "forkpty", "WEXITSTATUS",
)

_PATCH_OBJ = re.compile(
    r'patch\.object\(\s*(?:rr\.|runner\.|JF\.|inst\.)?os\s*,\s*"(%s)"'
    % "|".join(POSIX_ONLY_OS))
_PATCH_STR = re.compile(r'patch\(\s*"os\.(%s)"' % "|".join(POSIX_ONLY_OS))
_SKIP = re.compile(
    r'skip(?:Unless|If)\(.*(?:"nt"|POSIX|win32|WINDOWS|symlink|needs)')
_CHMOD_ZERO = re.compile(r'chmod\([^)]*,\s*0(?:o0+)?\s*\)')
_STAT_PATCH = re.compile(r'patch\.object\(\s*os\s*,\s*"stat"')
_COUNTER = re.compile(r'(?:\["n"\]|len\(\w+\))\s*>\s*1')
_CLOSE_FAKE = re.compile(r'patch\.object\(\s*os\s*,\s*"close"\s*,\s*(\w+)\s*\)')
_CLOSE_SIDE_EFFECT = re.compile(
    r'patch\.object\(\s*os\s*,\s*"close"\s*,\s*side_effect\s*=\s*'
    r'(?:OSError|IOError|PermissionError|Exception|RuntimeError)\b')


def _call_text(src, start):
    """The source of one call, from its opening paren to the match."""
    i = src.index("(", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    return src[start:]


def _line_no(src, pos):
    return src.count("\n", 0, pos) + 1


def _guarded(lines, line_no):
    """True when the test or class above line_no is skipped off POSIX,
    the module skips off POSIX, or the body skips itself first."""
    i = line_no - 1
    # the enclosing def and class, and the decorators above each
    for kind in (r"^\s+def test_", r"^class "):
        k = i
        while k >= 0 and not re.match(kind, lines[k]):
            if kind.startswith("^\\s+def") and re.match(r"^class ", lines[k]):
                break
            k -= 1
        if k >= 0 and re.match(kind, lines[k]):
            if kind.startswith("^\\s+def"):
                body = "\n".join(lines[k:i + 1])
                if "skipTest(" in body:
                    return True
            m = k - 1
            while m >= 0 and lines[m].strip().startswith("@"):
                if _SKIP.search(lines[m]) or "skip" in lines[m]:
                    return True
                m -= 1
    # A module that skips itself off Windows at import.
    for j, line in enumerate(lines[:80]):
        if 'os.name == "nt"' in line or "platform.startswith(\"win" in line:
            if any("SkipTest" in l for l in lines[j:j + 4]):
                return True
    return False


def _test_body_above(lines, line_no):
    """The enclosing test method's lines from its def to line_no."""
    i = line_no - 1
    k = i
    while k >= 0 and not re.match(r"^\s+def test_|^class ", lines[k]):
        k -= 1
    return "\n".join(lines[max(k, 0):i])


def findings_in(path):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()
    out = []

    def flag(pos, what, instead):
        n = _line_no(src, pos)
        if "# portable:" in lines[n - 1]:
            return
        out.append("%s:%d: %s; %s" % (os.path.basename(path), n, what, instead))

    for m in _PATCH_OBJ.finditer(src):
        call = _call_text(src, m.start())
        if "create=True" not in call and not _guarded(lines, _line_no(src, m.start())):
            flag(m.start(), "patches os.%s, which Windows does not have"
                 % m.group(1), "add create=True and make the "
                 "post-condition the platform's, or skip off POSIX")
    for m in _PATCH_STR.finditer(src):
        call = _call_text(src, m.start())
        if "create=True" not in call and not _guarded(lines, _line_no(src, m.start())):
            flag(m.start(), "patches os.%s, which Windows does not have"
                 % m.group(1), "add create=True, or skip off POSIX")
    for m in _STAT_PATCH.finditer(src):
        n = _line_no(src, m.start())
        window = _test_body_above(lines, n)
        if _COUNTER.search(window) and 'os.path, "isfile"' not in window \
                and 'os.path, "isdir"' not in window and not _guarded(lines, n):
            flag(m.start(), "counts os.stat calls to catch a path probe "
                 "(os.path.isfile is C on Windows and never calls os.stat)",
                 "stub os.path.isfile for the target and let os.stat raise "
                 "on every call")
    for m in _CLOSE_SIDE_EFFECT.finditer(src):
        if not _guarded(lines, _line_no(src, m.start())):
            flag(m.start(), "fakes os.close without releasing the descriptor "
                 "(Windows cannot then remove the file)",
                 "a fake that calls the real os.close first, then raises")
    for m in _CLOSE_FAKE.finditer(src):
        name = m.group(1)
        d = re.search(r"^([ \t]*)def %s\(fd[^)]*\):\n((?:\1[ \t]+.*\n|[ \t]*\n)*)" % name, src, re.M)
        if d and not re.search(r"real_close|os\.close\(|_close\(", d.group(2)) \
                and not _guarded(lines, _line_no(src, m.start())):
            flag(m.start(), "fakes os.close with %s, which never releases "
                 "the descriptor (Windows cannot then remove the file)" % name,
                 "have the fake call the real os.close before it raises")
    for m in _CHMOD_ZERO.finditer(src):
        if not _guarded(lines, _line_no(src, m.start())):
            flag(m.start(), "chmod 000 as an unreadable file (not "
                 "unreadable on Windows)", "a refusing open, or a POSIX skip")
    return out


class WindowsPortabilityTest(unittest.TestCase):

    def test_the_suite_has_no_posix_only_fixture_shapes(self):
        found = []
        for name in sorted(os.listdir(SUITE)):
            if name.startswith("test_") and name.endswith(".py") \
                    and name != os.path.basename(__file__):
                found.extend(findings_in(os.path.join(SUITE, name)))
        self.assertEqual(found, [], "fixture shapes that fail on Windows "
                         "(the standing orders, 'The loop'):\n  "
                         + "\n  ".join(found))

    def test_the_rules_catch_the_shapes(self):
        import tempfile
        samples = {
            "getuid": 'with mock.patch.object(os, "getuid", None):\n    pass\n',
            "counter": ('calls = {"n": 0}\nif calls["n"] > 1:\n    raise OSError\n'
                        'with mock.patch.object(os, "stat", flaky):\n    pass\n'),
            "close": 'with mock.patch.object(os, "close", side_effect=OSError("x")):\n    pass\n',
            "fake_close": ('def broken(fd):\n    seen.append(fd)\n    raise OSError("x")\n'
                           'with mock.patch.object(os, "close", broken):\n    pass\n'),
            "chmod": 'class T(unittest.TestCase):\n    def test_x(self):\n        os.chmod(p, 0)\n',
        }
        clean = {
            "getuid": 'with mock.patch.object(os, "getuid", None, create=True):\n    pass\n',
            "probe": ('with mock.patch.object(os.path, "isfile", ok), \\\n'
                      '        mock.patch.object(os, "stat", flaky):\n    pass\n'),
            "skipped": ('class T(unittest.TestCase):\n    @unittest.skipUnless(os.name != "nt", "POSIX only")\n'
                        '    def test_x(self):\n        with mock.patch.object(os, "getuid", None):\n            pass\n'),
            "body_skip": ('class T(unittest.TestCase):\n    def test_x(self):\n'
                          '        if os.name == "nt":\n            self.skipTest("posix")\n'
                          '        with mock.patch.object(os, "chown") as c:\n            pass\n'),
            "real_close": ('def close(fd):\n    real_close(fd)\n    raise OSError("x")\n'
                           'with mock.patch.object(os, "close", side_effect=close):\n    pass\n'),
            "marked": 'os.chmod(p, 0)  # portable: Windows leg asserts the other branch\n',
        }
        with tempfile.TemporaryDirectory() as d:
            for name, text in samples.items():
                path = os.path.join(d, "test_%s.py" % name)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.assertTrue(findings_in(path), "rule missed: " + name)
            for name, text in clean.items():
                path = os.path.join(d, "test_ok_%s.py" % name)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.assertEqual(findings_in(path), [], "false positive: " + name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
