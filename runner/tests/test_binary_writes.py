"""Raw os.open writes must not be text-translated on Windows.

On Windows, os.open without os.O_BINARY opens the file in text mode
and the C runtime translates "\\n" to "\\r\\n" in os.write -- the
runner's private-file writers (O_EXCL | O_NOFOLLOW, mode 0600) all
grew from one idiom, and none of them set O_BINARY. The visible
victim was the canary plant: the file landed on disk with CRLF
endings while its snapshot hash folds CRLF, so a later CRLF rewrite
of the file hashed differently and tripped a healthy canary
(build-windows CI failure, 2026-10-17). Bytes the runner writes
must be the bytes on disk, on every platform. This test keeps the
pairing -- every O_NOFOLLOW flag block also sets O_BINARY -- in
sync across the runner sources.
"""

import os
import unittest


def _sources():
    import runner
    root = os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))
    pkg = os.path.join(root, "runner")
    for dirpath, dirnames, filenames in os.walk(pkg):
        # The suite and the example extensions are not the runner.
        if dirpath == pkg:
            skip = "tests extensions tools __pycache__".split()
            dirnames[:] = [d for d in dirnames if d not in skip]
        for name in sorted(filenames):
            if name.endswith(".py"):
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    yield os.path.relpath(path, pkg), fh.read()


class BinaryWriteFlagsTest(unittest.TestCase):
    def test_every_nofollow_block_also_sets_binary(self):
        total = 0
        for name, text in _sources():
            lines = text.splitlines()
            for i, ln in enumerate(lines):
                if ln.strip() != "flags |= os.O_NOFOLLOW":
                    continue
                total += 1
                following = [x.strip() for x in lines[i + 1:i + 3]]
                self.assertIn(
                    "flags |= os.O_BINARY", following,
                    "%s:%d sets O_NOFOLLOW without O_BINARY" % (name, i + 1))
        # Self-check: the idiom is used across the package; if the
        # scan ever matches nothing, this test would pass vacuously.
        self.assertGreaterEqual(total, 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
