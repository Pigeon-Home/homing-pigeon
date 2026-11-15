# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The build identity banner: full identity in --version, at the
head of every log, and once per module on first use.

The conductor's requirement (2026-11-14): --version on every CLI
prints the full identity -- the version, the entire platform
architecture, the compile/build info, and the full git build
stamp -- never the bare version alone. Every log in the system
opens with that identity at CRITICAL level: printed to the
terminal always, never rate-limited, never suppressed by quiet
or non-verbose settings. And the first time a code module is
used in a process, it emits its provenance once: environment,
versioning, and the hash of where it came from -- the build
stamp plus a single SHA-384 checksum over the runner tree's
manifest, written by runner/tools/build_stamp.py at packaging
time, from which the tree's rich history can be derived.

Suppositions, recorded before the deciding runs (2026-11-14):

S1. --version on all 4 CLIs (runner, install, send-job, oauth)
    exits 0 and prints, on separate lines, the full version,
    the platform system, release, machine and platform string,
    the Python version, a build stamp line and a build checksum
    line. (Before this change it printed the bare version only,
    so these assertions start red.)
S2. With the log's minute budget exhausted (INFO lines being
    dropped), a CRITICAL line still reaches the console and the
    log file, and it consumes no budget: the count of budgeted
    lines is unchanged by it.
S3. announce() emits exactly once per module name per process;
    a second call for the same module emits nothing, and a
    different module gets its own emit.
S4. log_startup's first emitted line is the identity block at
    CRITICAL, ahead of the "starting" line, which still stands;
    with a stamp patched into the runner module, the block
    names that stamp and checksum.
S5. build_stamp.write_build_stamp writes __checksum__ equal to
    build_stamp.tree_checksum(tree) recomputed after stamping
    (the stamp carrier, runner/_build.py, is excluded from the
    manifest, so restamping a tree with a different commit
    leaves the checksum unchanged), and changing one covered
    file changes the checksum. __pycache__ and .pyc files are
    not covered.
S6. A plain checkout's identity still prints the full platform
    and Python lines, with the stamp and checksum reading
    "unknown".

Conclusions (recorded after the deciding runs): see the
companion commit; the runs are named in the desk record.
"""
import argparse
import hashlib
import io
import os
import platform
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from runner import identity
import runner.runner as rr
from runner.tools import build_stamp as BS


def _run_version_flag(main, prog):
    buf = io.StringIO()
    with mock.patch("sys.argv", [prog, "--version"]), redirect_stdout(buf):
        with unittest.TestCase().assertRaises(SystemExit) as cm:
            main()
    return cm.exception.code, buf.getvalue()


class IdentityTextTest(unittest.TestCase):
    def test_identity_names_every_field(self):
        text = identity.identity_text("homing-pigeon")
        self.assertIn("homing-pigeon " + identity.__version__, text)
        self.assertIn(platform.system(), text)
        self.assertIn(platform.release(), text)
        self.assertIn(platform.machine(), text)
        self.assertIn(platform.platform(), text)
        self.assertIn(platform.python_version(), text)
        self.assertIn("build stamp:", text)
        self.assertIn("build checksum (sha384):", text)

    def test_first_line_is_prog_and_version(self):
        first = identity.identity_text("demo").splitlines()[0]
        self.assertEqual("demo " + identity.__version__, first)

    def test_identity_is_a_block_not_a_line(self):
        self.assertGreaterEqual(
            len(identity.identity_text("x").splitlines()), 5)

    def test_plain_checkout_stamp_and_checksum_read_unknown(self):
        # This suite runs on a plain checkout: nothing stamped it.
        self.assertEqual("unknown", identity.build_stamp())
        self.assertEqual("unknown", identity.build_checksum())
        text = identity.identity_text("homing-pigeon")
        self.assertIn("build stamp: unknown", text)
        self.assertIn("build checksum (sha384): unknown", text)

    def test_frozen_or_source_is_named(self):
        word = "frozen" if getattr(sys, "frozen", False) else "source"
        self.assertIn(word, identity.identity_text("x"))


class VersionFlagIdentityTest(unittest.TestCase):
    def _assert_full_identity(self, main, prog):
        code, out = _run_version_flag(main, prog)
        self.assertEqual(0, code)
        self.assertIn(identity.__version__, out)
        self.assertIn("build stamp:", out)
        self.assertIn("build checksum (sha384):", out)
        self.assertIn(platform.machine(), out)
        self.assertIn(platform.python_version(), out)
        # The block keeps its lines: argparse's own version action
        # collapses newlines, so a surviving line break ahead of
        # the stamp line proves the custom action printed it.
        self.assertIn("\nbuild stamp:", out)

    def test_runner_version(self):
        from runner.runner import main
        self._assert_full_identity(main, "homing-pigeon")

    def test_install_version(self):
        from runner.ops.install import main
        self._assert_full_identity(main, "install")

    def test_send_job_version(self):
        from runner.cloud.send_job import main
        self._assert_full_identity(main, "send-job")

    def test_oauth_version(self):
        from runner.wire.oauth import main
        self._assert_full_identity(main, "oauth")


class CriticalLogTest(unittest.TestCase):
    def setUp(self):
        self._saved = (rr._LOG_MINUTE, rr._LOG_COUNT, rr._LOG_DROPPED,
                       rr._LOG_FILE, rr._VERBOSE)
        rr._LOG_FILE = None
        rr._VERBOSE = False

    def tearDown(self):
        (rr._LOG_MINUTE, rr._LOG_COUNT, rr._LOG_DROPPED,
         rr._LOG_FILE, rr._VERBOSE) = self._saved

    def test_critical_prints_with_the_budget_exhausted(self):
        import time
        rr._LOG_MINUTE = time.time()
        rr._LOG_COUNT = 10 ** 9  # far past any minute cap
        rr._LOG_DROPPED = 0
        buf = io.StringIO()
        with redirect_stdout(buf):
            rr.log("budgeted line that must drop")
            rr.log("critical line that must print", "CRITICAL")
        out = buf.getvalue()
        self.assertNotIn("budgeted line that must drop", out)
        self.assertIn("[CRITICAL] critical line that must print", out)

    def test_critical_consumes_no_budget(self):
        import time
        rr._LOG_MINUTE = time.time()
        rr._LOG_COUNT = 7
        rr._LOG_DROPPED = 0
        with redirect_stdout(io.StringIO()):
            rr.log("one critical", "CRITICAL")
            rr.log("two critical", "CRITICAL")
        self.assertEqual(7, rr._LOG_COUNT)
        self.assertEqual(0, rr._LOG_DROPPED)

    def test_critical_reaches_the_log_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "runner.log")
            rr._LOG_FILE = path
            with redirect_stdout(io.StringIO()):
                rr.log("critical for the file", "CRITICAL")
            with open(path, encoding="utf-8") as fh:
                self.assertIn("[CRITICAL] critical for the file",
                              fh.read())


class AnnounceTest(unittest.TestCase):
    def setUp(self):
        identity._reset_announced()

    def tearDown(self):
        identity._reset_announced()

    def test_announce_fires_exactly_once_per_module(self):
        seen = []
        self.assertTrue(identity.announce("mod.one", emit=seen.append))
        self.assertFalse(identity.announce("mod.one", emit=seen.append))
        self.assertFalse(identity.announce("mod.one", emit=seen.append))
        self.assertEqual(1, len(seen))
        self.assertIn("build stamp:", seen[0])

    def test_each_module_gets_its_own_emit(self):
        seen = []
        identity.announce("mod.one", emit=seen.append)
        identity.announce("mod.two", emit=seen.append)
        self.assertEqual(2, len(seen))

    def test_default_emit_prints_at_critical(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            identity.announce("mod.loud")
        self.assertIn("[CRITICAL]", buf.getvalue())


class StartupIdentityTest(unittest.TestCase):
    def setUp(self):
        identity._reset_announced()
        rr._LOG_MINUTE = 0.0
        rr._LOG_COUNT = 0
        rr._LOG_DROPPED = 0

    def tearDown(self):
        identity._reset_announced()

    def _startup_output(self):
        with tempfile.TemporaryDirectory() as d:
            args = argparse.Namespace(
                verbose=False, workers=None, poll_interval=None,
                max_output_bytes=None, timeout=None,
                dry_run=False, once=False, no_send=False)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rr.log_startup({}, args, d)
            return buf.getvalue()

    def test_identity_opens_the_startup_block(self):
        out = self._startup_output()
        first = out.splitlines()[0]
        self.assertIn("[CRITICAL]", first)
        self.assertIn("homing-pigeon " + identity.__version__, first)
        self.assertIn("build stamp:", out)
        self.assertLess(out.index("build stamp:"),
                        out.index(" starting"))
        # The standing starting line still stands.
        self.assertIn("homing-pigeon %s starting" % rr.__version__, out)

    def test_identity_names_a_patched_stamp_and_checksum(self):
        checksum = "ab" * 48
        with mock.patch.object(rr, "__build__", "c0ba079d1234"), \
                mock.patch.object(rr, "__checksum__", checksum):
            out = self._startup_output()
        self.assertIn("build stamp: c0ba079d1234", out)
        self.assertIn("build checksum (sha384): " + checksum, out)


class BuildStampChecksumTest(unittest.TestCase):
    def _tree(self, d):
        runner_dir = os.path.join(d, "runner")
        os.makedirs(os.path.join(runner_dir, "sub"))
        with open(os.path.join(runner_dir, "a.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("x = 1\n")
        with open(os.path.join(runner_dir, "sub", "b.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("y = 2\n")
        return runner_dir

    def _stamped_ns(self, d, commit):
        path = BS.write_build_stamp(d, commit)
        ns = {}
        with open(path, encoding="utf-8") as fh:
            exec(fh.read(), ns)
        return ns

    def test_stamp_writes_the_tree_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            ns = self._stamped_ns(d, "6697271c3b7a")
            self.assertEqual("6697271c3b7a", ns["__build__"])
            self.assertEqual(BS.tree_checksum(d), ns["__checksum__"])
            self.assertEqual(96, len(ns["__checksum__"]))
            int(ns["__checksum__"], 16)  # hex, or this raises

    def test_checksum_matches_a_hand_recompute(self):
        with tempfile.TemporaryDirectory() as d:
            runner_dir = self._tree(d)
            lines = []
            for rel in ("runner/a.py", "runner/sub/b.py"):
                with open(os.path.join(d, rel), "rb") as fh:
                    digest = hashlib.sha384(fh.read()).hexdigest()
                lines.append("%s %s\n" % (rel, digest))
            expect = hashlib.sha384(
                "".join(sorted(lines)).encode("utf-8")).hexdigest()
            self.assertEqual(expect, BS.tree_checksum(d))

    def test_restamping_with_another_commit_keeps_the_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            first = self._stamped_ns(d, "6697271c3b7a")["__checksum__"]
            second = self._stamped_ns(d, "aaaaaaa1111")["__checksum__"]
            self.assertEqual(first, second)

    def test_changing_a_covered_file_changes_the_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            runner_dir = self._tree(d)
            before = BS.tree_checksum(d)
            with open(os.path.join(runner_dir, "a.py"), "a",
                      encoding="utf-8") as fh:
                fh.write("x = 2\n")
            self.assertNotEqual(before, BS.tree_checksum(d))

    def test_pycache_and_pyc_are_not_covered(self):
        with tempfile.TemporaryDirectory() as d:
            runner_dir = self._tree(d)
            before = BS.tree_checksum(d)
            cache = os.path.join(runner_dir, "__pycache__")
            os.makedirs(cache)
            with open(os.path.join(cache, "a.cpython-312.pyc"),
                      "wb") as fh:
                fh.write(b"\x00\x01\x02")
            with open(os.path.join(runner_dir, "a.pyc"), "wb") as fh:
                fh.write(b"\x03\x04")
            self.assertEqual(before, BS.tree_checksum(d))


if __name__ == "__main__":
    unittest.main()
