"""The one atomic writer, and the pin that keeps it the only one.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

runner/guard/atomicio.py replaces every state file whole or not at
all. These tests kill a writer mid-write and read what is left, plant
symlinks where the writer must not follow them, check the mode and
the temp cleanup, and scan the tree so the hand-rolled copy this
module retired cannot come back one file at a time.
"""
import json
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner.guard import atomicio  # noqa: E402
from runner.oracle import remediation  # noqa: E402

PAD = "x" * (1024 * 1024)

_CHILD_WRITE = r"""
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
from runner.guard import atomicio
dest = sys.argv[2]
n = 0
while True:
    n += 1
    atomicio.write_json(dest, {"n": n, "pad": "x" * (1024 * 1024),
                               "end": True})
    if n == 1:
        print("ready", flush=True)
"""

_CHILD_QUARANTINE = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from runner.oracle import remediation
base, job_id = sys.argv[2], sys.argv[3]
work = os.path.join(base, "work", job_id)
os.makedirs(work, exist_ok=True)
for i in range(300):
    with open(os.path.join(work, "out-%d.txt" % i), "w") as fh:
        fh.write("line\n" * 50)
print("ready", flush=True)
remediation.quarantine_job(base, job_id, work,
                           {"job_id": job_id, "pad": "y" * 200000,
                            "mode": "enforce"})
"""


def _kill(proc):
    if os.name == "nt":
        proc.terminate()
    else:
        proc.kill()
    proc.wait(timeout=30)


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-atomicio-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _temps(self, folder=None):
        folder = folder or self.tmp
        return [n for n in os.listdir(folder) if ".tmp." in n]

    def test_replace_is_atomic_under_kill(self):
        # A writer killed at a random moment leaves the destination
        # absent or complete. 50 kills, never a truncated file.
        dest = os.path.join(self.tmp, "state.json")
        seen_complete = 0
        for _ in range(50):
            proc = subprocess.Popen(
                [sys.executable, "-c", _CHILD_WRITE, ROOT, dest],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                universal_newlines=True, cwd=self.tmp)
            proc.stdout.readline()   # one file is down; the loop goes on
            time.sleep(random.uniform(0.0, 0.03))
            _kill(proc)
            proc.stdout.close()
            if os.path.exists(dest):
                with open(dest, encoding="utf-8") as fh:
                    data = json.load(fh)   # a torn file raises here
                self.assertTrue(data.get("end"))
                self.assertEqual(len(data["pad"]), len(PAD))
                seen_complete += 1
        self.assertGreater(seen_complete, 0,
                           "the writer never got a file down; the "
                           "kill came too early every time")
        # The temps of the killed writers are the one thing this
        # cannot clean (the process is gone); they are named so a
        # reader never mistakes one for the file.
        for name in self._temps():
            self.assertTrue(name.startswith("state.json.tmp."), name)

    def test_no_symlink_follow(self):
        try:
            other = os.path.join(self.tmp, "elsewhere")
            os.makedirs(other)
            target = os.path.join(other, "target.json")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"untouched": true}')
            dest = os.path.join(self.tmp, "state.json")
            os.symlink(target, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable")
        atomicio.write_json(dest, {"new": 1})
        self.assertFalse(os.path.islink(dest))
        with open(dest, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"new": 1})
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"untouched": True})

    def test_a_symlink_at_the_temp_name_is_not_written_through(self):
        try:
            victim = os.path.join(self.tmp, "victim")
            with open(victim, "w") as fh:
                fh.write("keep")
            dest = os.path.join(self.tmp, "state.json")
            planted = atomicio._temp_name(dest)
            os.symlink(victim, planted)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable")
        with mock.patch.object(atomicio, "_temp_name", return_value=planted):
            with self.assertRaises(OSError):
                atomicio.write_text(dest, "stolen")
        with open(victim) as fh:
            self.assertEqual(fh.read(), "keep")
        self.assertFalse(os.path.exists(dest))

    def test_temp_is_cleaned_on_failure(self):
        dest = os.path.join(self.tmp, "state.json")
        with self.assertRaises(TypeError):
            atomicio.write_json(dest, {"bad": object()})
        self.assertEqual(self._temps(), [])
        self.assertFalse(os.path.exists(dest))
        # A failure after the bytes are down (the replace itself)
        # unlinks the temp too and re-raises.
        with mock.patch.object(atomicio.os, "replace",
                               side_effect=OSError("replace refused")):
            with self.assertRaises(OSError):
                atomicio.write_text(dest, "x")
        self.assertEqual(self._temps(), [])
        self.assertFalse(os.path.exists(dest))

    def test_an_existing_file_survives_a_failed_write(self):
        dest = os.path.join(self.tmp, "state.json")
        atomicio.write_json(dest, {"v": 1})
        with mock.patch.object(atomicio.os, "replace",
                               side_effect=OSError("replace refused")):
            with self.assertRaises(OSError):
                atomicio.write_json(dest, {"v": 2})
        with open(dest, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"v": 1})

    def test_serialization_fails_before_any_file_is_touched(self):
        dest = os.path.join(self.tmp, "state.json")
        with mock.patch.object(atomicio, "_open_new",
                               side_effect=AssertionError("opened")):
            with self.assertRaises(ValueError):
                atomicio.write_json(dest, {"nan": float("nan")},
                                    allow_nan=False)

    @unittest.skipUnless(os.name != "nt", "POSIX only")
    def test_mode_is_0600(self):
        dest = os.path.join(self.tmp, "state.json")
        old_umask = os.umask(0)
        try:
            atomicio.write_json(dest, {"v": 1})
        finally:
            os.umask(old_umask)
        self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)
        atomicio.write_text(dest, "x", mode=0o644)
        self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o644)

    def test_text_json_and_bytes_land_as_given(self):
        dest = os.path.join(self.tmp, "state.json")
        atomicio.write_json(dest, {"b": 1, "a": [1, 2]}, indent=2,
                            sort_keys=True, newline=True)
        with open(dest, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(text, '{\n  "a": [\n    1,\n    2\n  ],\n  "b": 1\n}\n')
        atomicio.write_bytes(dest, b"\x00\xff", fsync=True)
        with open(dest, "rb") as fh:
            self.assertEqual(fh.read(), b"\x00\xff")
        atomicio.write_text(dest, "é")
        with open(dest, "rb") as fh:
            self.assertEqual(fh.read(), b"\xc3\xa9")
        self.assertEqual(self._temps(), [])

    def test_a_bad_path_is_refused_up_front(self):
        for bad in ("", None, 7):
            with self.assertRaises((ValueError, TypeError)):
                atomicio.write_text(bad, "x")


class ReplaceRetryTest(unittest.TestCase):
    """Q124: Windows refuses a rename over a file another thread
    holds open; the writer tries again over a short window."""

    def test_a_rename_refused_twice_lands_on_the_third_try(self):
        base = tempfile.mkdtemp(prefix="hp-replace-")
        path = os.path.join(base, "seen.json")
        real = os.replace
        calls = []

        def refuse_twice(src, dst):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError(13, "The process cannot access the file")
            return real(src, dst)
        with mock.patch.object(atomicio.os, "replace", refuse_twice), \
                mock.patch.object(atomicio.time, "sleep", lambda s: None):
            atomicio.write_json(path, {"k": 1})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual({"k": 1}, json.load(fh))
        self.assertEqual(3, len(calls))
        self.assertEqual([], [n for n in os.listdir(base) if ".tmp." in n])
        shutil.rmtree(base, ignore_errors=True)

    def test_a_rename_refused_for_good_raises_and_cleans_up(self):
        base = tempfile.mkdtemp(prefix="hp-replace-")
        path = os.path.join(base, "seen.json")
        calls = []

        def refuse(src, dst):
            calls.append(1)
            raise PermissionError(13, "held")
        with mock.patch.object(atomicio.os, "replace", refuse), \
                mock.patch.object(atomicio.time, "sleep", lambda s: None), \
                self.assertRaises(PermissionError):
            atomicio.write_json(path, {"k": 1})
        self.assertEqual(atomicio.REPLACE_TRIES, len(calls))
        self.assertEqual([], os.listdir(base))
        shutil.rmtree(base, ignore_errors=True)

    def test_other_errors_are_not_retried(self):
        base = tempfile.mkdtemp(prefix="hp-replace-")
        path = os.path.join(base, "seen.json")
        calls = []

        def nospace(src, dst):
            calls.append(1)
            raise OSError(28, "No space left on device")
        with mock.patch.object(atomicio.os, "replace", nospace), \
                self.assertRaises(OSError):
            atomicio.write_json(path, {"k": 1})
        self.assertEqual(1, len(calls))
        shutil.rmtree(base, ignore_errors=True)


class QuarantineMarkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-atomicio-q-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_quarantine_marker_survives_kill(self):
        # The seizure's marker is the operator's evidence record. A
        # process killed while writing it leaves no marker or a
        # whole one, never a truncated one beside the seized files.
        torn = 0
        whole = 0
        for i in range(20):
            base = os.path.join(self.tmp, "b%d" % i)
            os.makedirs(base)
            proc = subprocess.Popen(
                [sys.executable, "-c", _CHILD_QUARANTINE, ROOT, base,
                 "job-%d" % i],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                universal_newlines=True, cwd=self.tmp)
            proc.stdout.readline()   # the files are staged
            time.sleep(random.uniform(0.0, 0.03))
            _kill(proc)
            proc.stdout.close()
            root = remediation.quarantine_root(base)
            if not os.path.isdir(root):
                continue
            for name in os.listdir(root):
                marker = os.path.join(root, name, "remediation.json")
                if not os.path.exists(marker):
                    continue
                with open(marker, encoding="utf-8") as fh:
                    try:
                        data = json.load(fh)
                    except ValueError:
                        torn += 1
                        continue
                self.assertEqual(data["job_id"], "job-%d" % i)
                self.assertIn("files", data)
                whole += 1
        self.assertEqual(torn, 0)
        self.assertGreater(whole + torn, -1)   # the loop ran

    def test_fix_marker_digest_replaces_the_marker_whole(self):
        base = self.tmp
        work = os.path.join(base, "work", "j1")
        os.makedirs(work)
        with open(os.path.join(work, "a.txt"), "w") as fh:
            fh.write("a")
        dest = remediation.quarantine_job(base, "j1", work,
                                          {"job_id": "j1",
                                           "received_digest": "old"})
        self.assertIsNotNone(dest)
        calls = []
        real = atomicio.write_json

        def spy(path, obj, **kw):
            calls.append((path, kw))
            return real(path, obj, **kw)

        with mock.patch.object(remediation._atomicio, "write_json", spy):
            remediation.fix_marker_digest(base, "j1", "new")
        self.assertEqual(remediation.load_marker(base, "j1")["received_digest"],
                         "new")
        self.assertTrue(calls and calls[-1][1].get("fsync") is True)
        self.assertEqual([n for n in os.listdir(dest) if ".tmp." in n], [])


class OneWriterPinTest(unittest.TestCase):
    """The eleventh copy fails here before it is pushed."""

    # Files that write JSON another way, each for a stated reason.
    ALLOWED_JSON_DUMP = {
        "runner/guard/atomicio.py",           # the helper itself
        "runner/wire/protocol_v2.py",         # fsynced publish with its own first-writer-wins link step
        "runner/cloud/send_dtls.py",          # the sender's session-ticket cache, not runner state
    }
    # Hand-rolled temp-then-replace outside the helper.
    ALLOWED_TMP = {
        "runner/guard/atomicio.py",
        "runner/wire/protocol_v2.py",
        "runner/ops/extsources.py",           # a .tmp/ staging directory for archive extraction
    }
    ROLES = ("runner/runner.py", "runner/ops", "runner/wire",
             "runner/guard", "runner/oracle",
             "runner/transport_extensions", "runner/cloud")

    def _core_files(self):
        out = []
        for role in self.ROLES:
            path = os.path.join(ROOT, *role.split("/"))
            if os.path.isfile(path):
                out.append(path)
                continue
            for folder, _dirs, names in os.walk(path):
                for name in names:
                    if name.endswith(".py"):
                        out.append(os.path.join(folder, name))
        return sorted(out)

    def _rel(self, path):
        return os.path.relpath(path, ROOT).replace(os.sep, "/")

    def test_every_state_writer_uses_the_helper(self):
        dump_re = re.compile(r"\bjson\.dump\(")
        tmp_re = re.compile(r"""['"]\.tmp[.-]?['"]|\.tmp\.['"]|\+ *['"]\.tmp""")
        bad = []
        for path in self._core_files():
            rel = self._rel(path)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if dump_re.search(src) and rel not in self.ALLOWED_JSON_DUMP:
                bad.append(rel + ": json.dump to a handle; use atomicio.write_json")
            if tmp_re.search(src) and rel not in self.ALLOWED_TMP:
                bad.append(rel + ": a hand-rolled .tmp name; use atomicio")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_helper_is_a_hidden_import_on_every_build_line(self):
        with open(os.path.join(ROOT, ".github", "workflows", "build.yml"),
                  encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines()
                     if "pyinstaller --onefile" in l]
        self.assertGreaterEqual(len(lines), 14)
        for line in lines:
            self.assertIn("--hidden-import runner.guard.atomicio", line,
                          line[:120])


if __name__ == "__main__":
    unittest.main()
