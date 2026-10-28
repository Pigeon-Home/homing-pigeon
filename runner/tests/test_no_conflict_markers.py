# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""No tracked file carries a merge conflict marker.

A stash popped over a rebase can leave its markers in a file that is
then committed whole: `bfe0157` put three conflict blocks into
runner/cloud/send_job.py, every module that imports it stopped
parsing, and main stayed broken until the next commit took them out.
This reads every file git tracks and fails on a line that opens,
divides or closes a conflict block, naming the file and line. The
markers are built from their characters here, so this file never
matches itself.
"""
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_OPEN, _MID, _CLOSE = "<" * 7, "=" * 7, ">" * 7
MARKER = re.compile(r"^(?:%s(?: |$)|%s$|%s(?: |$))"
                    % (re.escape(_OPEN), re.escape(_MID), re.escape(_CLOSE)),
                    re.M)


def markers(text):
    """(line number, line) for each conflict marker in text."""
    out = []
    for m in MARKER.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        end = text.find("\n", m.start())
        out.append((line, text[m.start():end if end >= 0 else None]))
    return out


def tracked():
    if shutil.which("git") is None:
        return None
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                          capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


class MarkerShapeTest(unittest.TestCase):
    def test_the_three_markers_are_found(self):
        text = ("ok\n" + _OPEN + " Updated upstream\nmine\n" + _MID
                + "\ntheirs\n" + _CLOSE + " Stashed changes\nok\n")
        self.assertEqual([n for n, _l in markers(text)], [2, 4, 6])
        self.assertEqual(markers(text)[0][1], _OPEN + " Updated upstream")

    def test_lookalikes_are_not_markers(self):
        for text in ("x = 1  # " + _OPEN + "\n", "a " + _CLOSE + " b\n",
                     _MID + "=\n", "=" * 6 + "\n", " " + _OPEN + " HEAD\n",
                     "<<<<<<<<< x\n"):
            with self.subTest(text=text):
                self.assertEqual(markers(text), [])


class TreeTest(unittest.TestCase):
    def test_no_tracked_file_carries_a_conflict_marker(self):
        files = tracked()
        if files is None:
            self.skipTest("git is not on PATH")
        found = []
        for rel in files:
            path = os.path.join(ROOT, rel)
            try:
                if not os.path.isfile(path) or os.path.islink(path) \
                        or os.path.getsize(path) > 8_000_000:
                    continue
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            if b"\0" in data[:8192]:
                continue
            for line, text in markers(data.decode("utf-8", "replace")):
                found.append("%s:%d: %s" % (rel, line, text[:60]))
        self.assertEqual(found, [], "conflict markers committed:\n"
                         + "\n".join(found[:40]))


if __name__ == "__main__":
    unittest.main()
