"""Workspace isolation, pinned (review item 5).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

`_staged_dest` was right; this module makes the rest of the story a
proof an auditor can read: the canonical root is computed once per
job and a symlinked work directory is refused; a sweep after staging
and another right before the process starts refuse any symlink, any
entry that is not a regular file or directory, and anything whose
real path leaves the root; the download lands whole or not at all,
capped while streaming; and after any job, valid or not, nothing new
exists outside the work tree and the runner's own state files.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest import mock

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    given = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.tests.test_file_names import REJECTED  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402

# Where the runner's own state lives under base_dir: a job may make
# names appear here (its claim, its sent record, its retained output),
# never anywhere else.
STATE = ("work", "inflight", "sent", "outbox", "retained", "quarantine",
         "released", "transport-extensions")
STATE_FILES = ("seen.json", "seen.json.lock")
# The runner's own records, created lazily by a poll (a resource
# threshold crossed under load writes the first security event). A
# staged file that escaped the work tree would carry the author's
# name, not one of these.
LATE_STATE = {"security-events.jsonl", "security-audit.jsonl",
              "security-audit-counts.json", "resources.json",
              "security-audit.jsonl.1",
              "detection-baseline.json", "dri-state.json",
              "oracle-learning.jsonl", "runner.log", "board.json",
              "extension-review.json", "oracle-chat.jsonl",
              "canary-watch.json", "canaries"}
RECORD_PREFIXES = ("security-", "runner.log", "oracle-", "resources",
                   "detection-", "dri-", "board", "extension-",
                   "canary-watch")
# The canaries the local watch plants under canaries/ on a poll.
CANARIES = set(getattr(R, "_CANARY_NAMES", ()))
# A record's writer temp (runner/guard/atomicio.py names it
# <path>.tmp.<pid>.<thread>.<hex>) is the record's, not a job's: on
# Windows a scanner can hold the fresh file while it is renamed and
# again while the refused rename is cleaned up, leaving the temp.
_WRITER_TEMP = re.compile(r"\.tmp\.\d+\.\d+\.[0-9a-f]+$")


def _runner_record(n, leaf):
    """True when a name outside the state tree is plainly one of the
    runner's own records (or a record's writer temp)."""
    base = _WRITER_TEMP.sub("", leaf)
    if base in LATE_STATE or base in STATE_FILES \
            or base.startswith(RECORD_PREFIXES):
        return True
    parent = n.replace("\\", "/").rsplit("/", 1)[0] if "/" in \
        n.replace("\\", "/") else ""
    return parent == "canaries" and base in CANARIES


def _names_outside_state(base_dir):
    out = set()
    for dirpath, dirnames, filenames in os.walk(base_dir):
        rel = os.path.relpath(dirpath, base_dir)
        if rel == ".":
            dirnames[:] = [d for d in dirnames if d not in STATE]
            rel = ""
        for name in dirnames + filenames:
            if rel == "" and name in STATE_FILES:
                continue
            out.add(os.path.join(rel, name))
    return out


def _nothing_new_outside(before, after, names=()):
    """The names that appeared outside the state tree that a job could
    have put there: anything carrying one of the job's own file names
    (the vector or its last component), or any name that is not one of
    the runner's own records. The runner writes its records lazily
    under load (a resource event, a rolled audit log), so a name that
    is plainly the runner's never counts; a name that matches the
    job's files always does."""
    leaves = set()
    for n in names:
        if isinstance(n, str) and n:
            leaves.add(n)
            leaves.add(n.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1])
    out = []
    for n in sorted(after - before):
        leaf = n.replace("\\", "/").rsplit("/", 1)[-1]
        if n in leaves or leaf in leaves:
            out.append(n)
        elif _runner_record(n, leaf):
            continue
        else:
            out.append(n)
    return out


def _payload_outside_work(base_dir, job_id):
    """Files outside work/<job_id> carrying the fake download's text."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(base_dir):
        rel = os.path.relpath(dirpath, base_dir)
        if rel == ".":
            dirnames[:] = [d for d in dirnames if d != "work"]
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as fh:
                    if b"payload from " in fh.read(200000):
                        hits.append(os.path.relpath(path, base_dir))
            except OSError:
                continue
    return hits


def _fake_download(url, dest, max_bytes=0):
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("payload from %s\n" % url)


class Harness(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.tmp = self.h.tmp
        self.seen_path = self.h.seen_path

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cycle(self, mails, seen=None):
        imap, smtp = TR.FakeIMAP(mails), TR.FakeSMTP()
        seen = {} if seen is None else seen
        R.poll_once(self.cfg, self.tmp, seen, self.seen_path,
                    imap=imap, smtp=smtp)
        return imap, smtp, seen

    def _result(self, smtp):
        return TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)

    def _job(self, jid, files, script="ls -R"):
        return TR.job_payload(jid, kind="exec", script=script,
                              interpreter=["sh"], files=files)


class RejectionVectorsEndToEnd(Harness):
    def test_every_rejected_name_is_refused_before_a_download(self):
        # One warm-up exec job so the runner's lazily created state
        # files (the learning ledger among them) exist before the
        # snapshot.
        self._cycle([TR.job_email(self._job(str(uuid.uuid4()), []))])
        before = _names_outside_state(self.tmp)
        for vector, rule in REJECTED:
            if not isinstance(vector, str):
                continue   # the mail form cannot carry a non-string name
            with self.subTest(vector=vector):
                jid = str(uuid.uuid4())
                mail = TR.job_email(self._job(
                    jid, [{"name": vector, "url": "https://example.com/x"}]))

                def never(*_a, **_k):
                    self.fail("download called for %r" % (vector,))

                with mock.patch.object(R, "download", never):
                    imap, smtp, seen = self._cycle([mail])
                # One line per check, naming the vector: the run page
                # shows a failed test's last exception line and the
                # log itself is not always within reach.
                self.assertEqual(len(smtp.sent), 1,
                                 "results sent for %r" % (vector,))
                result = self._result(smtp)
                self.assertEqual(result["exit_code"], -2, repr(vector))
                self.assertIn("(rule %d)" % rule, result["stderr"],
                              repr(vector))
                self.assertEqual([str(x) for x in imap.flagged], ["1"],
                                 repr(vector))
                self.assertTrue(any(jid in k for k in seen),
                                "job not in seen for %r" % (vector,))
                work = os.path.join(self.tmp, "work", jid)
                left = os.listdir(work) if os.path.isdir(work) else []
                self.assertFalse(left, "left in work for %r: %r"
                                 % (vector, left))
                outside = _nothing_new_outside(
                    before, _names_outside_state(self.tmp), [vector])
                self.assertFalse(outside, "new outside the state tree for "
                                 "%r: %r" % (vector, outside))
                payload = _payload_outside_work(self.tmp, jid)
                self.assertFalse(payload, "payload outside work for %r: %r"
                                 % (vector, payload))


class SweepTest(Harness):
    def test_symlink_planted_after_stage_is_caught_by_pre_exec_sweep(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(self._job(
            jid, [{"name": "in.txt", "url": "https://example.com/in"}]))
        victim = os.path.join(self.tmp, "config.json")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("keep")
        real_preexec = R._job_user_preexec

        def plant(cfg, base_dir, job_id, work, *a, **k):
            # Between the post-stage sweep and the start of the
            # process: the window the pre-exec sweep exists for.
            try:
                os.symlink(victim, os.path.join(work, "late"))
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlinks unavailable")
            return real_preexec(cfg, base_dir, job_id, work, *a, **k)

        with mock.patch.object(R, "download", _fake_download), \
                mock.patch.object(R, "_job_user_preexec", plant), \
                mock.patch.object(R.subprocess, "Popen",
                                  side_effect=AssertionError("started")):
            _imap, smtp, _seen = self._cycle([mail])
        result = self._result(smtp)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("workspace integrity (before execution)",
                      result["stderr"])
        self.assertIn("late", result["stderr"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "work", jid)))
        with open(victim, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "keep")

    def test_a_staged_symlink_is_caught_by_the_post_stage_sweep(self):
        jid = str(uuid.uuid4())
        mail = TR.job_email(self._job(
            jid, [{"name": "in.txt", "url": "https://example.com/in"}]))
        victim = os.path.join(self.tmp, "config.json")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("keep")

        def plant(url, dest, max_bytes=0):
            try:
                os.symlink(victim, dest)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlinks unavailable")

        with mock.patch.object(R, "download", plant), \
                mock.patch.object(R.subprocess, "Popen",
                                  side_effect=AssertionError("started")):
            _imap, smtp, _seen = self._cycle([mail])
        result = self._result(smtp)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("workspace integrity (after staging)", result["stderr"])
        self.assertIn("in.txt", result["stderr"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "work", jid)))

    def test_a_script_that_is_a_symlink_is_refused(self):
        jid = str(uuid.uuid4())
        job = TR.job_payload(jid, kind="exec",
                             script_url="https://example.com/s.sh",
                             interpreter=["sh"])
        victim = os.path.join(self.tmp, "config.json")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("echo must-not-run\n")

        def plant(url, dest, max_bytes=0):
            try:
                os.symlink(victim, dest)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlinks unavailable")

        with mock.patch.object(R, "download", plant), \
                mock.patch.object(R.subprocess, "Popen",
                                  side_effect=AssertionError("started")):
            _imap, smtp, _seen = self._cycle([TR.job_email(job)])
        result = self._result(smtp)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("workspace integrity", result["stderr"])

    def test_the_sweep_names_an_entry_that_is_not_a_regular_file(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("POSIX only")
        work = os.path.join(self.tmp, "work", "j")
        os.makedirs(work)
        os.mkfifo(os.path.join(work, "pipe"))
        with self.assertRaises(R.JobRejected) as cm:
            R._sweep_workspace(work, os.path.realpath(work), "after staging")
        self.assertIn("pipe", str(cm.exception))
        self.assertIn("not a regular file", str(cm.exception))

    @unittest.skipUnless(os.name == "nt", "junctions exist on Windows only")
    def test_a_junction_in_the_work_tree_is_refused(self):
        # No bwrap on Windows: the real-path checks and the sweeps are
        # the isolation, and a junction is a reparse point the sweep
        # reads from lstat, whichever way it points.
        import subprocess
        work = os.path.join(self.tmp, "work", "j")
        os.makedirs(work)
        inside = os.path.join(work, "inside")
        os.makedirs(inside)
        for target, name in ((self.tmp, "out"), (inside, "in")):
            link = os.path.join(work, name)
            try:
                r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            except OSError:
                self.skipTest("cannot create a junction here")
            if r.returncode != 0:
                self.skipTest("cannot create a junction here")
            with self.assertRaises(R.JobRejected) as cm:
                R._sweep_workspace(work, os.path.realpath(work),
                                   "after staging")
            self.assertIn(name, str(cm.exception))
            os.rmdir(link)

    def test_a_reparse_point_reads_as_a_link(self):
        class St:
            st_mode = 0o040755
            st_file_attributes = 0x400   # FILE_ATTRIBUTE_REPARSE_POINT
        self.assertTrue(R._reparse_point(St()))
        self.assertFalse(R._reparse_point(os.lstat(self.tmp)))

    def test_a_clean_tree_passes_both_sweeps(self):
        work = os.path.join(self.tmp, "work", "j")
        os.makedirs(os.path.join(work, "data", "deep"))
        for rel in ("a.txt", "data/b.txt", "data/deep/c.txt"):
            with open(os.path.join(work, rel), "w") as fh:
                fh.write("x")
        root = os.path.realpath(work)
        R._sweep_workspace(work, root, "after staging")
        R._sweep_workspace(work, root, "before execution")
        R._check_script_path(os.path.join(work, "a.txt"), root)
        with self.assertRaises(R.JobRejected):
            R._check_script_path(os.path.join(work, "missing"), root)
        with self.assertRaises(R.JobRejected):
            R._check_script_path(os.path.join(work, "data"), root)


class WorkDirTest(Harness):
    def test_work_dir_that_is_a_symlink_is_refused(self):
        jid = str(uuid.uuid4())
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        os.makedirs(os.path.join(self.tmp, "work"))
        try:
            os.symlink(elsewhere, os.path.join(self.tmp, "work", jid))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable")
        mail = TR.job_email(self._job(jid, [], script="echo hi > out.txt"))
        _imap, smtp, _seen = self._cycle([mail])
        result = self._result(smtp)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("symlink", result["stderr"])
        self.assertEqual(os.listdir(elsewhere), [])

    def test_the_root_is_the_real_path(self):
        work = os.path.join(self.tmp, "work", "j")
        os.makedirs(work)
        self.assertEqual(R._workspace_root(work), os.path.realpath(work))
        link = os.path.join(self.tmp, "work", "link")
        try:
            os.symlink(work, link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(R.JobRejected):
            R._workspace_root(link)


class _Endless:
    """A response that never stops sending."""

    def __init__(self, chunk=65536):
        self.chunk = chunk
        self.reads = 0

    def read(self, n):
        self.reads += 1
        return b"x" * min(n, self.chunk)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-dl-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _temps(self):
        return [n for n in os.listdir(self.tmp) if ".tmp." in n]

    def test_download_streams_and_stops_at_cap(self):
        resp = _Endless()
        dest = os.path.join(self.tmp, "big.bin")
        with mock.patch.object(R, "_open_download", return_value=resp):
            with self.assertRaises(R.JobRejected) as cm:
                R.download("https://example.com/big", dest, max_bytes=200000)
        self.assertIn("exceeded 200000", str(cm.exception))
        self.assertLessEqual(resp.reads, 5)     # stopped at the cap, not after
        self.assertFalse(os.path.exists(dest))
        self.assertEqual(self._temps(), [])      # the partial temp is gone

    def test_download_lands_whole_or_not_at_all(self):
        class Flaky:
            def __init__(self):
                self.n = 0

            def read(self, n):
                self.n += 1
                if self.n == 1:
                    return b"half"
                raise OSError("connection reset")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        dest = os.path.join(self.tmp, "in.txt")
        with mock.patch.object(R, "_open_download", return_value=Flaky()):
            with self.assertRaises(OSError):
                R.download("https://example.com/in", dest)
        self.assertFalse(os.path.exists(dest))
        self.assertEqual(self._temps(), [])

        class Whole:
            def __init__(self):
                self.parts = [b"ab", b"cd", b""]

            def read(self, n):
                return self.parts.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(R, "_open_download", return_value=Whole()):
            R.download("https://example.com/in", dest)
        with open(dest, "rb") as fh:
            self.assertEqual(fh.read(), b"abcd")
        self.assertEqual(self._temps(), [])

    def test_a_symlink_at_the_destination_is_replaced_not_followed(self):
        victim = os.path.join(self.tmp, "victim")
        with open(victim, "w") as fh:
            fh.write("keep")
        dest = os.path.join(self.tmp, "in.txt")
        try:
            os.symlink(victim, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable")

        class Whole:
            def __init__(self):
                self.parts = [b"new", b""]

            def read(self, n):
                return self.parts.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(R, "_open_download", return_value=Whole()):
            R.download("https://example.com/in", dest)
        self.assertFalse(os.path.islink(dest))
        with open(victim) as fh:
            self.assertEqual(fh.read(), "keep")
        with open(dest) as fh:
            self.assertEqual(fh.read(), "new")


if given is not None:
    _GOOD = st.sampled_from(["a.txt", "data/in.csv", "deep/er/x.bin",
                             "A_B-C.d", "x"])
    _BAD = st.sampled_from([v for v, _r in REJECTED if isinstance(v, str)])
    _NAME = st.one_of(_GOOD, _BAD)

    class NothingOutsideWorkProperty(unittest.TestCase):
        @settings(max_examples=20, deadline=None)
        @given(names=st.lists(_NAME, min_size=0, max_size=4))
        def test_nothing_outside_work_after_any_job(self, names):
            # A fresh base dir per example: hypothesis reuses the
            # instance, so the harness is built and torn down here.
            h = TR.RunnerTest("test_ping_roundtrip")
            h.setUp()
            try:
                def cycle(mails):
                    imap, smtp = TR.FakeIMAP(mails), TR.FakeSMTP()
                    seen = {}
                    R.poll_once(h.cfg, h.tmp, seen, h.seen_path,
                                imap=imap, smtp=smtp)
                    return smtp, seen

                def job(jid, files):
                    return TR.job_payload(jid, kind="exec", script="ls -R",
                                          interpreter=["sh"], files=files)

                cycle([TR.job_email(job(str(uuid.uuid4()), []))])
                before = _names_outside_state(h.tmp)
                jid = str(uuid.uuid4())
                files = [{"name": n, "url": "https://example.com/%d" % i}
                         for i, n in enumerate(names)]
                with mock.patch.object(R, "download", _fake_download):
                    smtp, seen = cycle([TR.job_email(job(jid, files))])
                result = TR.verify_body(TR.result_body(smtp.sent[0]),
                                        TR.SECRET)
                bad = [n for n in names if any(n == v for v, _ in REJECTED)]
                if bad:
                    self.assertEqual(result["exit_code"], -2)
                else:
                    self.assertEqual(result["exit_code"], 0, result["stderr"])
                    for n in names:
                        self.assertIn(n.rsplit("/", 1)[-1], result["stdout"])
                self.assertTrue(any(jid in k for k in seen))
                self.assertEqual(_nothing_new_outside(
                    before, _names_outside_state(h.tmp), names), [])
                self.assertEqual(_payload_outside_work(h.tmp, jid), [])
            finally:
                shutil.rmtree(h.tmp, ignore_errors=True)


class OutsideCheckTest(unittest.TestCase):
    """The sweep's classifier: a job's name always counts, a runner
    record (or its writer temp) never does, anything else counts."""

    def test_a_record_and_its_writer_temp_are_the_runners(self):
        before = set()
        after = {"seen.json.tmp.4242.139.0a1b2c3d",
                 "canary-watch.json.tmp.1.2.ff",
                 "security-events.jsonl", "runner.log.1",
                 os.path.join("canaries", "passwords.txt"), "canaries"}
        self.assertEqual(_nothing_new_outside(before, after, ["CON"]), [])

    def test_anything_else_counts(self):
        after = {"x", os.path.join("canaries", "evil"),
                 "report.txt.tmp.1.2.ab", "notes.tmp.1.2.ab"}
        self.assertEqual(_nothing_new_outside(set(), after, []),
                         sorted(after))

    def test_the_jobs_own_name_counts_even_shaped_like_a_record(self):
        vector = "seen.json.tmp.1.2.ab"
        after = {vector, os.path.join("deep", "runner.log")}
        self.assertEqual(
            _nothing_new_outside(set(), after, [vector, "a/runner.log"]),
            sorted(after))


if __name__ == "__main__":
    unittest.main()
