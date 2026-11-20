#!/usr/bin/env python3
"""The held output: finding F17, closed.

docs/infrastructure-documents/proofs/v4-the-bars.md found that the
runner held all that a job wrote before it cut each stream to the
output cap. The rule that closes it: the runner holds at most a
fixed number of bytes of each stream of a job, whatever the job
writes, and the result is what it was.

This module holds the model of the reader, `held.tla`, by a twin
written apart from the checker, whose counts were the prediction
the checker met. It holds the reader itself against
communicate(), which it stands in for. And it holds the real
gate and the real execution: every result is what it was, and
the runner's memory no longer grows with what a job writes.
"""
import base64
import collections
import copy
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.guard import freebsd_confine  # noqa: E402
from runner.guard import windows_confine  # noqa: E402
from runner.ops import helpers as HELPERS  # noqa: E402
from runner.tests import test_v4_at_a_bound as RUNG  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-bars.md")
POSIX = os.name == "posix"
LINUX = sys.platform.startswith("linux")
# A real Windows, and not a POSIX host that the suite's simulated
# surface makes to look like 1: ctypes carries the system's own
# error call on Windows alone, and the surface does not lend it.
WINDOWS = sys.platform == "win32" and hasattr(ctypes, "get_last_error")
Held = HELPERS.Held

# ---- The model's twin
#
# The world of held.tla: what a job may write, what a pipe holds,
# the most 1 read takes, the output cap, and the bar.
WORLD = collections.OrderedDict((
    ("MaxWrite", 24), ("PipeRoom", 5), ("Chunk", 3), ("Cap", 6),
    ("Keep", 9)))
INVARIANTS = ("TypeOK", "NothingIsLost", "HeldUnderTheBar",
              "HeldIsTheFirstPart", "TheResultIsAsItWas",
              "ACutIsATruncation", "NeverHeldWhole")
CONFIGURATIONS = {
    "heldbar.cfg": (True, 9, INVARIANTS),
    "heldasitwas.cfg": (False, 9, tuple(
        name for name in INVARIANTS if name != "HeldUnderTheBar")),
    "heldwitnessasitwas.cfg": (False, 9, ("HeldUnderTheBar",)),
    "heldwitnessshortbar.cfg": (True, 4, ("TheResultIsAsItWas",)),
}


def broken_by(state, keep, bounded, world=WORLD):
    """The invariants of held.tla that 1 state breaks."""
    written, pipe, seen, held, job, result = state
    cap, most = world["Cap"], world["MaxWrite"]
    out = []
    if not (0 <= written <= most and 0 <= pipe <= world["PipeRoom"]
            and 0 <= seen <= most and 0 <= held <= most
            and job in ("running", "ended") and -1 <= result <= cap):
        out.append("TypeOK")
    if written != pipe + seen:
        out.append("NothingIsLost")
    if held > keep:
        out.append("HeldUnderTheBar")
    if held != (min(seen, keep) if bounded else seen):
        out.append("HeldIsTheFirstPart")
    if result != -1 and result != min(written, cap):
        out.append("TheResultIsAsItWas")
    if seen > held and not seen > cap:
        out.append("ACutIsATruncation")
    if bounded and seen > keep and not held < seen:
        out.append("NeverHeldWhole")
    return out


def steps(state, keep, bounded, world=WORLD):
    """Every state 1 step of held.tla leads to, with repeats."""
    written, pipe, seen, held, job, result = state
    chunk = world["Chunk"]
    out = []
    if job == "running":
        for more in range(1, chunk + 1):
            if written + more <= world["MaxWrite"] \
                    and pipe + more <= world["PipeRoom"]:
                out.append((written + more, pipe + more, seen, held, job,
                            result))
    if pipe > 0 and result == -1:
        took = min(pipe, chunk)
        out.append((written, pipe - took, seen + took,
                    min(keep, held + took) if bounded else held + took,
                    job, result))
    if job == "running":
        out.append((written, pipe, seen, held, "ended", result))
    if job == "ended" and pipe == 0 and result == -1:
        out.append((written, pipe, seen, held, job,
                    min(held, world["Cap"])))
    if result != -1:
        out.append(state)
    return out


def walk(keep, bounded, world=WORLD):
    """The whole of held.tla's world, breadth first: (distinct
    states, states generated, depth, {invariant: states that
    break it})."""
    start = (0, 0, 0, 0, "running", -1)
    depth_of = {start: 1}
    queue = collections.deque([start])
    generated = 1
    while queue:
        state = queue.popleft()
        for after in steps(state, keep, bounded, world):
            generated += 1
            if after not in depth_of:
                depth_of[after] = depth_of[state] + 1
                queue.append(after)
    broken = collections.Counter()
    for state in depth_of:
        broken.update(broken_by(state, keep, bounded, world))
    return (len(depth_of), generated, max(depth_of.values()),
            dict(broken))


def cfg_of(name):
    """A configuration of held.tla as its file states it:
    ({constant: value}, [invariants])."""
    with open(os.path.join(MODELS.PROOFS, name), encoding="utf-8") as handle:
        text = re.sub(r"\\\*.*", "", handle.read())
    constants = {key: value for key, value in re.findall(
        r"(?m)^\s*(\w+) = (\w+)\s*$", text)}
    invariants = text.split("INVARIANT", 1)[1].split()
    return constants, invariants


class TheModelOfTheReader(unittest.TestCase):
    """held.tla, walked by its twin."""

    def test_the_twin_counted_what_the_checker_then_counted(self):
        # The twin's counts stood first. TLC 2.19 then found the
        # same 295 distinct states among 665 generated, to a
        # depth of 19, with the bar and as it was.
        for bounded in (True, False):
            distinct, generated, depth, _broken = walk(WORLD["Keep"],
                                                       bounded)
            self.assertEqual((295, 665, 19), (distinct, generated, depth))

    def test_with_the_bar_every_invariant_holds(self):
        self.assertEqual({}, walk(WORLD["Keep"], True)[3])

    def test_the_reader_as_it_was_breaks_the_bar_and_nothing_else(self):
        self.assertEqual({"HeldUnderTheBar": 165},
                         walk(WORLD["Keep"], False)[3])
        # The first state past the bar: the job has written 10,
        # and all 10 are held.
        past = sorted(
            state for state in self._reached(WORLD["Keep"], False)
            if state[3] > WORLD["Keep"])
        self.assertEqual((10, 0, 10, 10, "ended", -1), past[0])

    def _reached(self, keep, bounded):
        seen, queue = set(), collections.deque([(0, 0, 0, 0, "running", -1)])
        while queue:
            state = queue.popleft()
            if state in seen:
                continue
            seen.add(state)
            queue.extend(steps(state, keep, bounded))
        return seen

    def test_a_bar_under_the_cap_changes_the_result(self):
        broken = walk(4, True)[3]
        self.assertEqual(["ACutIsATruncation", "TheResultIsAsItWas"],
                         sorted(broken))
        # The least such job writes 5, and its result carries 4.
        short = min(state for state in self._reached(4, True)
                    if "TheResultIsAsItWas" in broken_by(state, 4, True))
        self.assertEqual((5, 0, 5, 4, "ended", 4), short)

    def test_the_bar_is_not_passed_whatever_the_job_writes(self):
        # The job's writing has no size in the claim: in worlds
        # where the job may write 3 to 60, the most the reader
        # with the bar holds is the lesser of the bar and what
        # was written, and the reader as it was holds it all.
        for most in (3, 9, 24, 60):
            world = collections.OrderedDict(WORLD, MaxWrite=most)
            for bounded, top in ((True, min(most, WORLD["Keep"])),
                                 (False, most)):
                seen, queue = set(), collections.deque(
                    [(0, 0, 0, 0, "running", -1)])
                while queue:
                    state = queue.popleft()
                    if state in seen:
                        continue
                    seen.add(state)
                    queue.extend(steps(state, WORLD["Keep"], bounded, world))
                self.assertEqual(top, max(state[3] for state in seen),
                                 (most, bounded))

    def test_the_files_state_the_world_the_twin_walks(self):
        with open(os.path.join(MODELS.PROOFS, "held.tla"),
                  encoding="utf-8") as handle:
            model = handle.read()
        for name in INVARIANTS:
            self.assertRegex(model, r"(?m)^%s ==" % name)
        self.assertIn("CONSTANTS MaxWrite, PipeRoom, Chunk, Cap, Keep, "
                      "Bounded", model)
        for cfg, (bounded, keep, invariants) in sorted(
                CONFIGURATIONS.items()):
            constants, stated = cfg_of(cfg)
            wanted = {key: str(value) for key, value in WORLD.items()}
            wanted["Keep"] = str(keep)
            wanted["Bounded"] = "TRUE" if bounded else "FALSE"
            self.assertEqual(wanted, constants, cfg)
            self.assertEqual(list(invariants), stated, cfg)

    def test_each_witness_names_an_invariant_its_world_breaks(self):
        for cfg, (bounded, keep, invariants) in sorted(
                CONFIGURATIONS.items()):
            broken = walk(keep, bounded)[3]
            if "witness" in cfg:
                self.assertEqual(1, len(invariants), cfg)
                self.assertIn(invariants[0], broken, cfg)
            else:
                for name in invariants:
                    self.assertNotIn(name, broken, (cfg, name))


# ---- The reader, against communicate()

def writer(out=b"", err=b"", code=0, pause=0.0, more=b""):
    """A process that writes `out` and `err`, and then, after a
    pause, `more` on stdout, and ends with `code`. A number in
    the place of bytes asks for that many bytes of the cycle,
    made in the process itself, and a number under 0 for the
    cycle turned round. So nothing long stands on the command
    line: Windows takes 32,767 characters there."""
    program = (
        "import sys, time\n"
        "o, e = sys.stdout.buffer, sys.stderr.buffer\n"
        "def made(n):\n"
        "    if not isinstance(n, int):\n"
        "        return n\n"
        "    size = abs(n)\n"
        "    cycle = (bytes(range(256)) * (size // 256 + 1))[:size]\n"
        "    return cycle if n >= 0 else cycle[::-1]\n"
        "o.write(made(%r)); o.flush()\n"
        "e.write(made(%r)); e.flush()\n"
        "time.sleep(%r)\n"
        "o.write(%r); o.flush()\n"
        "sys.exit(%d)\n" % (out, err, pause, more, code))
    # The longest command line this module asks for is far under
    # what Windows takes.
    assert len(program) < 2000, len(program)
    return subprocess.Popen([sys.executable, "-c", program],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def cycle(size):
    return (bytes(range(256)) * (size // 256 + 1))[:size]


# The 2 ways the reader reads: in the calling thread, and by a
# thread for each stream. Windows has the second alone.
WAYS = (True,) if os.name == "nt" else (False, True)


class TheReader(unittest.TestCase):
    """Held, the reader with the bar, where communicate() stood."""

    def test_the_bar_s_size(self):
        bound = HELPERS.held_bound
        # 4 bytes for each character of the cap, and 4 more.
        self.assertEqual([4, 8, 4004, 400004],
                         [bound(cap) for cap in (0, 1, 1000, 100000)])
        # The log's size, and the tail its record leaves out,
        # where that is the larger.
        self.assertEqual(65536, HELPERS.HELD_TAIL)
        self.assertEqual(33816576, bound(100000, 33554432))
        self.assertEqual(400004, bound(100000, 1000))
        self.assertEqual(400004, bound(100000, 0))
        # What is no number counts as 0.
        self.assertEqual([4, 4, 4, 400004],
                         [bound(None), bound("x"), bound(-5),
                          bound(100000, "x")])
        self.assertEqual(0, Held("x").keep)
        self.assertEqual(0, Held(-1).keep)

    def test_it_reads_as_communicate_reads_on_each_system(self):
        # communicate() reads in the calling thread where the
        # system can wait on a pipe, and by threads on Windows.
        self.assertEqual(os.name == "nt", HELPERS.HELD_BY_THREADS)
        self.assertEqual(HELPERS.HELD_BY_THREADS, Held(1)._by_threads)
        self.assertTrue(Held(1, by_threads=True)._by_threads)
        self.assertFalse(Held(1, by_threads=False)._by_threads)

    def test_under_the_bar_it_hands_back_what_communicate_does(self):
        # The last row: 9,999 bytes of the cycle on 1 stream, and
        # 10,000 of it turned round on the other.
        self.assertEqual(
            (cycle(9999), cycle(10000)[::-1]),
            writer(9999, -10000, 0).communicate(timeout=60))
        for way in WAYS:
            for out, err, code in ((b"", b"", 0), (b"a", b"", 1),
                                   (b"line 1\nline 2\n", b"oops\n", 3),
                                   (9999, -10000, 0)):
                want = writer(out, err, code).communicate(timeout=60)
                proc = writer(out, err, code)
                held = Held(10000, by_threads=way)
                self.assertEqual(want, held(proc, 60), way)
                self.assertEqual(code, proc.returncode)
                self.assertEqual(
                    {"stdout": len(want[0]), "stderr": len(want[1])},
                    held.seen)
                self.assertEqual(held.seen, held.kept)
                self.assertFalse(held.cut("stdout") or held.cut("stderr"))
                # Both pipes are closed, as communicate() leaves them.
                self.assertTrue(proc.stdout.closed and proc.stderr.closed)

    def test_past_the_bar_it_holds_the_first_part_and_counts_the_rest(self):
        for way in WAYS:
            for keep, size in ((0, 1), (10, 11), (4096, 65537),
                               (1000, 5000000)):
                proc = writer(size, b"e" * 3, 0)
                held = Held(keep, by_threads=way)
                out, err = held(proc, 120)
                self.assertEqual(cycle(size)[:keep], out, (way, keep, size))
                self.assertEqual(b"e" * min(3, keep), err)
                self.assertEqual(size, held.seen["stdout"])
                self.assertEqual(keep, held.kept["stdout"])
                self.assertTrue(held.cut("stdout"))
                self.assertEqual(keep < 3, held.cut("stderr"))
                # The job was read to its end: it ended by itself.
                self.assertEqual(0, proc.returncode)

    def test_both_streams_past_the_bar_and_the_job_still_ends(self):
        # 2 megabytes on each stream, far past what a pipe
        # holds: a reader that stopped at its bar would leave
        # the job waiting on a full pipe.
        program = ("import sys\n"
                   "for _ in range(32):\n"
                   "    sys.stdout.buffer.write(b'o' * 65536)\n"
                   "    sys.stderr.buffer.write(b'e' * 65536)\n")
        for way in WAYS:
            proc = subprocess.Popen([sys.executable, "-c", program],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            held = Held(100, by_threads=way)
            self.assertEqual((b"o" * 100, b"e" * 100), held(proc, 120))
            self.assertEqual({"stdout": 2097152, "stderr": 2097152},
                             held.seen)
            self.assertEqual(0, proc.returncode)

    def test_a_timeout_is_raised_as_communicate_raises_it(self):
        # And the next call goes on where the first stopped.
        for read in ("communicate",) + WAYS:
            proc = writer(b"first ", b"", 0, pause=1.5, more=b"second")
            held = Held(100, by_threads=read is True)

            def collect(wait):
                if read == "communicate":
                    return proc.communicate(timeout=wait)
                return held(proc, wait)

            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired) as raised:
                collect(0.2)
            self.assertGreaterEqual(time.monotonic() - started, 0.19, read)
            self.assertEqual(0.2, raised.exception.timeout)
            self.assertIsNone(proc.returncode)
            # No time at all is a timeout too, and loses nothing.
            with self.assertRaises(subprocess.TimeoutExpired):
                collect(0)
            self.assertEqual((b"first second", b""), collect(60), read)
            self.assertEqual(0, proc.returncode)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_a_stream_a_child_of_the_job_holds_open_is_waited_for(self):
        # The job's own process ends at once and leaves a child
        # that holds the stream. communicate() waits for the
        # stream's end, and so does the reader.
        for read in ("communicate",) + WAYS:
            proc = subprocess.Popen(
                ["sh", "-c", "sleep 1.5 & echo hi"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            held = Held(100, by_threads=read is True)

            def collect(wait):
                if read == "communicate":
                    return proc.communicate(timeout=wait)
                return held(proc, wait)

            with self.assertRaises(subprocess.TimeoutExpired):
                collect(0.3)
            self.assertEqual((b"hi\n", b""), collect(60), read)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_a_job_that_writes_until_the_time_is_up(self):
        # 40 megabytes and then a long wait: the time limit ends
        # the reading on time though a stream is never idle, and
        # after the kill the rest is read and counted.
        size = 40000000
        for way in WAYS:
            proc = subprocess.Popen(
                ["sh", "-c", "head -c %d /dev/zero; sleep 60" % size],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True)
            held = Held(1000, by_threads=way)
            started = time.monotonic()
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    held(proc, 1.0)
                took = time.monotonic() - started
                self.assertTrue(0.99 <= took < 20, (way, took))
            finally:
                os.killpg(proc.pid, 9)
            out, _err = held(proc, 60)
            self.assertEqual(b"\0" * 1000, out)
            self.assertTrue(1000 < held.seen["stdout"] <= size, held.seen)
            self.assertTrue(held.cut("stdout"))

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_where_the_system_can_wait_on_a_pipe_no_thread_is_started(self):
        before = set(threading.enumerate())
        proc = writer(3000000, b"e", 0, pause=0.3, more=b"x")
        held = Held(10, by_threads=False)
        with self.assertRaises(subprocess.TimeoutExpired):
            held(proc, 0.1)
        self.assertEqual(set(), set(threading.enumerate()) - before)
        self.assertIsNone(held._threads)
        held(proc, 60)
        self.assertEqual(set(), set(threading.enumerate()) - before)
        self.assertEqual(3000001, held.seen["stdout"])

    def test_1_stream_alone_is_read_as_2_are(self):
        for way in WAYS:
            proc = subprocess.Popen(
                [sys.executable, "-c",
                 "import sys; sys.stdout.write('out'); sys.stdout.flush(); "
                 "sys.stderr.write('err')"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual((b"outerr", b""),
                             Held(100, by_threads=way)(proc, 60))
            # And a pipe the standard library does not buffer.
            proc = subprocess.Popen(
                [sys.executable, "-c", "print('out', end='')"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=0)
            self.assertEqual((b"out", b""),
                             Held(100, by_threads=way)(proc, 60))
            # With no time limit, as communicate() without one.
            proc = writer(b"abc", b"de", 2)
            self.assertEqual((b"abc", b"de"),
                             Held(100, by_threads=way)(proc))
            self.assertEqual(2, proc.returncode)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_a_pipe_closed_under_the_reader_is_its_stream_s_end(self):
        proc = writer(b"some", b"", 0, pause=0.5, more=b"more")
        held = Held(4000, by_threads=False)
        with self.assertRaises(subprocess.TimeoutExpired):
            held(proc, 0.2)
        proc.stdout.close()
        out, err = held(proc, 60)
        self.assertEqual(b"some", out)
        # The job met a closed pipe, and said so on its other
        # stream.
        self.assertIn(b"BrokenPipeError", err)

    def test_a_stand_in_is_read_by_its_own_communicate(self):
        class StandIn:
            args = ["x"]

            def communicate(self, timeout=None):
                self.asked = timeout
                return b"o" * 50, b"e"

        proc, held = StandIn(), Held(10)
        self.assertEqual((b"o" * 50, b"e"), held(proc, 7))
        self.assertEqual(7, proc.asked)
        self.assertEqual({"stdout": 50, "stderr": 1}, held.seen)
        self.assertFalse(held.cut("stdout"))
        # A stand-in put at subprocess.Popen does not change
        # what the reader takes for the real thing.
        with mock.patch.object(subprocess, "Popen", StandIn):
            self.assertIsNot(subprocess.Popen, HELPERS.POPEN)
            self.assertEqual((b"o" * 50, b"e"), Held(10)(StandIn(), 1))

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_a_job_given_up_leaves_nothing_behind(self):
        # The job's process is gone and a child of it holds the
        # stream for 3 seconds more. The executor gives such a
        # job up. Read in the calling thread, the reader closes
        # both pipes then and there, and no thread was started.
        before = set(threading.enumerate())
        proc = subprocess.Popen(
            ["sh", "-c", "sleep 3 & echo hi"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        held = Held(100, by_threads=False)
        with self.assertRaises(subprocess.TimeoutExpired):
            held(proc, 0.3)
        self.assertFalse(proc.stdout.closed)
        held.let_go()
        self.assertTrue(proc.stdout.closed and proc.stderr.closed)
        self.assertEqual(set(), set(threading.enumerate()) - before)
        self.assertEqual(({"stdout": 0, "stderr": 0},) * 2,
                         (held.seen, held.kept))
        self.assertFalse(held.cut("stdout"))
        proc.wait(timeout=60)

    def test_a_job_given_up_is_let_go_by_its_threads(self):
        proc = writer(b"some", b"", 0, pause=1.0, more=b"more")
        held = Held(100, by_threads=True)
        with self.assertRaises(subprocess.TimeoutExpired):
            held(proc, 0.2)
        held.let_go()
        self.assertEqual(({"stdout": 0, "stderr": 0},) * 2,
                         (held.seen, held.kept))
        self.assertFalse(held.cut("stdout"))
        proc.wait(timeout=60)
        for thread in held._threads:
            thread.join(60)
            self.assertFalse(thread.is_alive())
        # What came after the let go was not counted, and each
        # thread closed its pipe.
        self.assertEqual({"stdout": 0, "stderr": 0}, held.seen)
        self.assertTrue(proc.stdout.closed and proc.stderr.closed)

    def test_what_another_reader_hands_back_is_noted(self):
        held = Held(10)
        held.took("stdout", b"0123456789", 64)
        held.took("stderr", b"abc")
        self.assertEqual(({"stdout": 64, "stderr": 3},
                          {"stdout": 10, "stderr": 3}),
                         (held.seen, held.kept))
        self.assertTrue(held.cut("stdout"))
        self.assertFalse(held.cut("stderr"))
        held.took("stderr", None, 5)
        self.assertEqual((5, 0), (held.seen["stderr"], held.kept["stderr"]))


# ---- The real gate and the real execution

def job_with(files, script):
    """The honest job, carrying `files` ({name: bytes}) and
    `script`, asking for the whole of its result."""
    payload, job_id = RUNG.honest_job()
    payload = copy.deepcopy(payload)
    payload["files"] = [
        {"name": name, "content_b64":
         base64.b64encode(data).decode("ascii")}
        for name, data in sorted(files.items())]
    payload["result_policy"] = {"view": "full"}
    return payload, job_id


def as_it_was(data, cap):
    """What a result carried of a stream before there was a
    bar: all the bytes turned into text, then the first `cap`
    characters, marked when there were more."""
    text = data.decode("utf-8", errors="replace")
    return text[:cap], len(text) > cap


KINDS = collections.OrderedDict((
    ("plain", "ab cd\n".encode("ascii")),
    ("2 bytes a character", "\u00e9".encode("utf-8")),
    ("3 bytes a character", "\u20ac".encode("utf-8")),
    ("4 bytes a character", "\U0001f600".encode("utf-8")),
    ("not text", b"\xff"),
    ("mixed", "a\u00e9\u20ac\U0001f600".encode("utf-8") + b"\xff\xc3"),
))
CAP = 1000


def stream(kind, characters):
    """About `characters` characters of 1 kind of bytes."""
    unit = KINDS[kind]
    per = len(unit.decode("utf-8", errors="replace"))
    return unit * (characters // per + (1 if characters % per else 0))


class TheRealExecutorWithTheBar(unittest.TestCase):
    """H1 and H4: every result is what it was."""

    def ask(self, files, script, extra=None, timeout=None, log=None):
        """1 job through the real gate and the real execution.
        With no `log` the runner keeps none, so the bar is the
        output cap's own. With `log`, a file and its size, the
        bar is the log's."""
        payload, job_id = job_with(files, script)
        if timeout is not None:
            payload["timeout_sec"] = timeout
        cfg = dict(RUNG.OFF)
        cfg.update({"max_result_view": "full", "max_output_bytes": CAP,
                    "max_result_bytes": 0})
        cfg.update(extra or {})
        path, size = log or (None, RUNNER._LOG_MAX_BYTES)
        with mock.patch.object(RUNNER, "_LOG_FILE", path), \
                mock.patch.object(RUNNER, "_LOG_MAX_BYTES", size):
            got, _where = RUNG.ask_the_runner(
                payload, job_id, script, extra=cfg)
        return got

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_h1_the_same_result_for_every_job(self):
        self.assertEqual(4004, HELPERS.held_bound(CAP))
        sizes = (0, 1, 999, 1000, 1001, 1002, 3999, 4003, 4004, 4005,
                 5000, 20000)
        asked = differ = 0
        for kind in KINDS:
            other = "not text" if kind == "plain" else "plain"
            for size in sizes:
                out, err = stream(kind, size), stream(other, 4005 - size % 7)
                got = self.ask({"o": out, "e": err},
                               "cat o; cat e >&2; exit 3")
                self.assertIsNotNone(got, (kind, size))
                want_out, cut_out = as_it_was(out, CAP)
                want_err, cut_err = as_it_was(err, CAP)
                asked += 1
                if (want_out, want_err, cut_out, cut_err, 3, False) != (
                        got.get("stdout"), got.get("stderr"),
                        got.get("stdout_truncated"),
                        got.get("stderr_truncated"), got.get("exit_code"),
                        got.get("timed_out")):
                    differ += 1
        self.assertEqual((72, 0), (asked, differ))

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_h1_at_the_default_cap(self):
        # 100,000 characters for each stream, the bar at 400,004
        # bytes: 1 character under the cap, at it, and over it,
        # and a stream of 4 bytes a character that ends 1 byte
        # past the bar.
        for kind, size in (("plain", 99999), ("plain", 100000),
                           ("plain", 100002), ("4 bytes a character", 100001),
                           ("not text", 400005)):
            out = stream(kind, size)
            got = self.ask({"o": out}, "cat o", extra={
                "max_output_bytes": 100000})
            want, cut = as_it_was(out, 100000)
            self.assertEqual((want, cut, ""), (
                got.get("stdout"), got.get("stdout_truncated"),
                got.get("stderr")), (kind, size))

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_h1_with_a_log_kept_the_result_is_the_same(self):
        # A running runner keeps a log, and then the bar is the
        # share's: 1,048,576 bytes and the tail, 1,310,720. A
        # stream past the output cap's own bar and under the
        # share comes back as it did, and the log's record
        # carries the whole of it, as it did.
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "runner.log")
            with mock.patch.object(RUNNER, "_LOG_FILE", path), \
                    mock.patch.object(RUNNER, "_LOG_MAX_BYTES", 2097152):
                self.assertEqual(1310720, RUNNER._held_for_job(CAP).keep)
            for kind, size in (("plain", 999), ("plain", 1001),
                               ("4 bytes a character", 1001),
                               ("not text", 4005), ("mixed", 20000)):
                out = stream(kind, size)
                got = self.ask({"o": out}, "cat o; exit 3",
                               log=(path, 2097152))
                want, cut = as_it_was(out, CAP)
                self.assertEqual((want, cut, 3), (
                    got.get("stdout"), got.get("stdout_truncated"),
                    got.get("exit_code")), (kind, size))
            with open(path, encoding="utf-8") as handle:
                logged = handle.read()
        self.assertEqual(5, logged.count(") full output:\n"))
        self.assertNotIn("its first part", logged)
        whole = stream("mixed", 20000).decode("utf-8", errors="replace")
        self.assertIn("--- stdout ---\n" + whole + "\n--- stderr ---",
                      logged)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_h6_a_stream_past_the_log_s_bar_through_the_real_execution(
            self):
        # A log of 1,000 bytes makes the bar 263,144 bytes. A job
        # writes 300,000. Its result is what it was, and the
        # log's record says what the job wrote and what a record
        # carries: such a log's own size is the share.
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "runner.log")
            out = stream("plain", 300000)
            self.assertEqual(300000, len(out))
            got = self.ask({"o": out}, "cat o", log=(path, 1000))
            want, cut = as_it_was(out, CAP)
            self.assertEqual((want, cut, 0), (
                got.get("stdout"), got.get("stdout_truncated"),
                got.get("exit_code")))
            with open(path, "rb") as handle:
                logged = handle.read()
        self.assertEqual(1000, len(logged))
        self.assertIn(
            b"output, its first part (the job wrote 300000 bytes on "
            b"stdout and 0 on stderr; the record carries at most 1000 "
            b"characters of a stream):\n--- stdout ---\nab cd\n", logged)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_l6_what_1_job_adds_to_the_log(self):
        # A job writes 3,000,000 bytes of text on each stream,
        # with the log at its default size. Its result is what
        # it was. Its record carries the share of each stream,
        # in a frame of under 400 bytes: it was 6,000,000 and
        # the frame.
        share = RUNNER.JOB_LOG_SHARE
        script = ("head -c 3000000 /dev/zero | tr '\\0' a; "
                  "head -c 3000000 /dev/zero | tr '\\0' b >&2")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "runner.log")
            got = self.ask({}, script, log=(path, 33554432))
            self.assertEqual(("a" * CAP, "b" * CAP, True, True, 0), (
                got.get("stdout"), got.get("stderr"),
                got.get("stdout_truncated"), got.get("stderr_truncated"),
                got.get("exit_code")))
            with open(path, "rb") as handle:
                logged = handle.read()
        frame = len(logged) - 2 * share
        self.assertTrue(0 < frame < 400, frame)
        self.assertIn(
            b"output, its first part (the job wrote 3000000 bytes on "
            b"stdout and 3000000 on stderr; the record carries at most "
            b"1048576 characters of a stream):\n--- stdout ---\n"
            + b"a" * share + b"\n--- stderr ---\n" + b"b" * share
            + b"\n--- end of job ", logged)

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_h4_a_job_its_time_limit_ends_comes_back_as_before(self):
        started = time.monotonic()
        got = self.ask({}, "printf 'first words'; sleep 60", timeout=1)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(("first words", "", True, -1, False), (
            got.get("stdout"), got.get("stderr"), got.get("timed_out"),
            got.get("exit_code"), got.get("stdout_truncated")))
        # A job that writes far past the bar and then waits for
        # its limit: its first characters up to the cap, marked.
        got = self.ask({}, "head -c 3000000 /dev/zero | tr '\\0' a; "
                           "sleep 60", timeout=2)
        self.assertEqual(("a" * CAP, True, True, -1), (
            got.get("stdout"), got.get("stdout_truncated"),
            got.get("timed_out"), got.get("exit_code")))

    @unittest.skipIf(not POSIX, "POSIX only")
    def test_the_runner_says_when_a_stream_passed_the_bar(self):
        payload, job_id = job_with({"o": b"x" * 5000}, "cat o")
        cfg = dict(RUNG.OFF)
        cfg.update({"max_result_view": "full", "max_output_bytes": CAP})
        # The rig keeps the runner's lines: 1 of them names the
        # stream, how much the job wrote and how much was held.
        lines = self.lines(payload, job_id, "cat o", cfg)
        told = [line for line in lines if "the runner held the first" in line]
        self.assertEqual(
            ["job %s wrote 5000 bytes on stdout; the runner held the "
             "first 4004" % job_id], told)
        # A job under the bar gets no such line.
        lines = self.lines(payload, job_id, "head -c 4004 o", cfg)
        self.assertEqual([], [line for line in lines
                              if "the runner held the first" in line])

    def lines(self, payload, job_id, script, cfg):
        """The runner's own log lines for 1 job."""
        notes = []
        job = copy.deepcopy(payload)
        job["script"] = script
        job["interpreter"] = ["bash"]
        raw = RUNG.PRE._mail(RUNG.PRE._subject(job_id),
                             RUNG.BIND._signed(job))
        with tempfile.TemporaryDirectory() as folder:
            settings = {"mailbox_user": "t@example.com", "base_dir": folder,
                        "oracle_opinion_mode": "off"}
            settings.update(RUNG.BIND.KEYS)
            settings.update(cfg)
            RUNNER._set_allow_cleartext_jobs(True)
            try:
                with mock.patch.object(
                        RUNNER, "send_mail",
                        lambda _smtp, _cfg, subject, body, to=None: None), \
                    mock.patch.object(RUNNER, "_LOG_FILE", None), \
                    mock.patch.object(
                        RUNNER, "log",
                        lambda msg, level="INFO": notes.append(msg)):
                    RUNNER.handle_mail(
                        settings, RUNG.DOOR._IMAP2(), RUNG.DOOR._SMTP2(), 3,
                        raw, folder, {}, RUNNER.build_secrets(settings),
                        RUNG.Namespace(dry_run=False, no_send=False), None)
            finally:
                RUNNER._set_allow_cleartext_jobs(False)
        return notes


class TheLogsRecord(unittest.TestCase):
    """H5 and H6, and then L1, L4 and L5: the log's record of a
    job's output, and the share of the log that a job has."""

    def record(self, stdout, stderr, held=None, cfg=None, limit=33554432):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "runner.log")
            with mock.patch.object(RUNNER, "_LOG_FILE", path), \
                    mock.patch.object(RUNNER, "_LOG_MAX_BYTES", limit):
                bar = RUNNER._held_for_job(100000).keep
                RUNNER._log_job_output("j1", "exec", stdout, stderr,
                                       cfg or {}, held=held)
            with open(path, encoding="utf-8") as handle:
                return handle.read(), bar

    def test_l1_with_a_log_kept_the_bar_is_the_share_s(self):
        # H5 had the bar at the log's size, 33,816,576 bytes at
        # the default. A job's share of the log is 1,048,576
        # characters of each stream since, and the bar is the
        # share and the tail the record leaves out.
        share = RUNNER.JOB_LOG_SHARE
        self.assertEqual(1048576, share)
        for limit in (33554432, 2097152, 1048576):
            _text, bar = self.record("out", "err", limit=limit)
            self.assertEqual(1310720, bar, limit)
        self.assertEqual(1310720, share + 4 * HELPERS.HELD_TAIL)
        # A log smaller than the share: its own size is the
        # share, as it was.
        _text, bar = self.record("out", "err", limit=600000)
        self.assertEqual(600000 + 4 * 65536, bar)
        # And never under what the output cap needs.
        _text, bar = self.record("out", "err", limit=1000)
        self.assertEqual(400004, bar)
        # With no log the bar is the output cap's alone.
        with mock.patch.object(RUNNER, "_LOG_FILE", None):
            self.assertEqual(400004, RUNNER._held_for_job(100000).keep)

    def stream_of(self, record):
        """The stdout part of a record."""
        return record.split("--- stdout ---\n", 1)[1].split(
            "\n--- stderr ---\n", 1)[0]

    def test_l4_a_stream_of_at_most_the_share_is_recorded_whole(self):
        share = RUNNER.JOB_LOG_SHARE
        for size in (share - 1, share):
            text = ("line %d\n" * 7 % tuple(range(7)) * (size // 49 + 1))[
                :size]
            self.assertEqual(size, len(text))
            record, _bar = self.record(text, "e")
            self.assertIn(") full output:\n--- stdout ---\n", record)
            self.assertNotIn("its first part", record)
            self.assertEqual(text, self.stream_of(record))
            self.assertTrue(record.endswith(
                "\n--- stderr ---\ne\n--- end of job j1 output ---\n"))

    def test_l5_of_a_longer_stream_the_first_part(self):
        share = RUNNER.JOB_LOG_SHARE
        # 1 character over the share, with no reader's word: the
        # record carries the share and says so.
        text = "a" * (share + 1)
        record, _bar = self.record(text, "e")
        self.assertIn(
            "job j1 (kind=exec) output, its first part (the record "
            "carries at most 1048576 characters of a stream):\n", record)
        self.assertEqual("a" * share, self.stream_of(record))
        # The other stream is whole beside it.
        self.assertIn("\n--- stderr ---\ne\n--- end of job", record)
        # A stream the reader cut at its bar, in characters of 1,
        # 2, 3 and 4 bytes: the record carries its first
        # 1,048,576 bytes at least and its first 1,048,576
        # characters at most, and says what the job wrote.
        bar = HELPERS.held_bound(100000, share)
        self.assertEqual(1310720, bar)
        for unit in ("a", "\u00e9", "\u20ac", "\U0001f600"):
            wide = len(unit.encode("utf-8"))
            held_bytes = (unit * (bar // wide)).encode("utf-8")
            held = Held(bar)
            held.took("stdout", held_bytes, 63245986)
            held.took("stderr", b"")
            record, _bar = self.record(
                held_bytes.decode("utf-8"), "", held=held)
            self.assertIn(
                "output, its first part (the job wrote 63245986 bytes "
                "on stdout and 0 on stderr; the record carries at most "
                "1048576 characters of a stream):\n", record)
            carried = self.stream_of(record)
            self.assertEqual(unit * len(carried), carried)
            self.assertLessEqual(len(carried), share, wide)
            self.assertGreaterEqual(len(carried.encode("utf-8")), share,
                                    wide)
        # At 4 bytes a character it is the first 1,048,576 bytes
        # exactly: the tail the record leaves out is the rest.
        self.assertEqual(share, len(carried.encode("utf-8")))

    def test_l5_a_secret_at_the_share_s_cut_is_written_as_its_mark(self):
        share = RUNNER.JOB_LOG_SHARE
        cfg = {"redact_patterns_extra": {"badge": "BADGE-[0-9]{20}"}}
        secret = "BADGE-01234567890123456789"
        # The secret stands across the place where the share
        # cuts. The text is redacted whole first, so the cut
        # falls in the mark.
        text = "x" * (share - 10) + secret + "y" * 100000
        record, _bar = self.record(text, "", cfg=cfg)
        carried = self.stream_of(record)
        self.assertEqual(share, len(carried))
        self.assertEqual("x" * (share - 10) + "[REDACTED:", carried)
        self.assertNotIn("BADGE-", record)
        self.assertNotIn("0123456789", record)

    def test_h5_a_stream_under_the_bar_is_recorded_as_it_was(self):
        held = Held(1000)
        held.took("stdout", b"out words")
        held.took("stderr", b"err words")
        for reader in (None, held):
            text, _bar = self.record("out words", "err words", held=reader)
            self.assertRegex(text, (
                r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[INFO\] job j1 "
                r"\(kind=exec\) full output:\n--- stdout ---\nout words\n"
                r"--- stderr ---\nerr words\n--- end of job j1 output ---\n$"))

    def test_h6_a_stream_over_the_bar_is_recorded_without_its_end(self):
        tail = HELPERS.HELD_TAIL
        # The bar cut the stream inside a secret: the held text
        # ends with the first half of it, which the pattern for
        # the whole does not match.
        cfg = {"redact_patterns_extra": {"badge": "BADGE-[0-9]{20}"}}
        whole = "BADGE-01234567890123456789"
        text = ("kept line\n" + whole + "\n" + "x" * (tail + 500)
                + "BADGE-0123456")
        held = Held(len(text))
        held.took("stdout", text.encode("ascii"), 9000000)
        held.took("stderr", b"e")
        record, _bar = self.record(text, "e", held=held, cfg=cfg)
        self.assertIn(
            "job j1 (kind=exec) output, its first part (the job wrote "
            "9000000 bytes on stdout and 1 on stderr; the record carries "
            "at most 1048576 characters of a stream):\n", record)
        # The whole secret inside is redacted, as before.
        self.assertIn("kept line\n[REDACTED:badge]\n", record)
        self.assertNotIn("BADGE-", record)
        # The stream's end is left out: the last 65,536 characters
        # of what was held, redacted first.
        kept = record.split("--- stdout ---\n")[1].split(
            "\n--- stderr ---")[0]
        redacted = text.replace(whole, "[REDACTED:badge]")
        self.assertEqual(redacted[:len(redacted) - tail], kept)
        # Without the reader's word the same text is written
        # whole, half a secret and all: that is why the end is
        # left out.
        record, _bar = self.record(text, "e", cfg=cfg)
        self.assertIn("BADGE-0123456\n--- stderr ---", record)
        # A cut stream shorter than the tail leaves nothing.
        held = Held(10)
        held.took("stdout", b"x" * 10, 99)
        held.took("stderr", b"y" * 10, 10)
        record, _bar = self.record("x" * 10, "y" * 10, held=held)
        self.assertIn("--- stdout ---\n\n--- stderr ---\n" + "y" * 10,
                      record)

    def test_the_preview_line_leaves_the_same_end_out(self):
        source = _read(os.path.join(ROOT, "runner", "ops", "exec.py"))
        # And no more than the same number of characters is kept:
        # the preview is of the stream's first words.
        self.assertIn(
            "    if cut_out:\n"
            "        tail = _runner().HELD_TAIL\n"
            "        shown = shown[:max(0, min(len(shown) - tail, tail))]\n",
            source)


# ---- The ladder, once more

HELD_CHILD = r"""
import json, os, re, sys, tempfile, time
sys.path.insert(0, %(root)r)
from runner import runner as RUNNER
from runner.tests import test_v4_at_a_bound as RUNG
script, timeout, log = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
payload, job_id = RUNG.honest_job()
if timeout:
    payload["timeout_sec"] = timeout
with tempfile.TemporaryDirectory() as folder:
    if log:
        # A running runner keeps a log, at the size it has by
        # default.
        RUNNER._LOG_FILE = os.path.join(folder, "runner.log")
    started = time.monotonic()
    got, _where = RUNG.ask_the_runner(
        payload, job_id, script, extra=dict(RUNG.OFF))
    took = time.monotonic() - started
    logged = os.path.getsize(RUNNER._LOG_FILE) if log else 0
with open("/proc/self/status") as status:
    peak = int(re.search(r"VmHWM:\s+(\d+) kB", status.read()).group(1))
print(json.dumps({
    "peak": peak, "exit": got.get("exit_code"), "view": got.get("view"),
    "timed_out": got.get("timed_out"), "took": took,
    "job": got.get("duration_sec"), "logged": logged}))
"""


def runner_of_its_own(script, timeout=0, log=False):
    """1 job through the real gate and the real execution, in a
    runner of its own: that runner's memory at its highest, in
    kilobytes, by the kernel's high-water mark, and the result.
    With `log` the runner keeps a log, as a running runner
    does."""
    done = subprocess.run(
        [sys.executable, "-c", HELD_CHILD % {"root": ROOT}, script,
         str(timeout), "1" if log else "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return json.loads(done.stdout.decode("utf-8").strip().split("\n")[-1])


def writes(size, byte="a"):
    return "head -c %d /dev/zero | tr '\\0' '%s'" % (size, byte)


def writes_wide_on_both(size):
    """`size` letters behind 1 character of 4 bytes, on each of
    the 2 streams at once: the costliest kind of output found.
    The runner's text of such a stream is 4 bytes wide for each
    character."""
    one = "printf '\\360\\237\\230\\200'; " + writes(size)
    return "(%s) >&2 & (%s); wait" % (one, one)


class TheLadderIsFlat(unittest.TestCase):
    """H2 and H4: the runner's memory does not grow with what a
    job writes."""

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_h2_the_top_of_the_ladder(self):
        base = runner_of_its_own(":")
        self.assertEqual((0, "attested"), (base["exit"], base["view"]))
        # Steps 31, 36 and 39 of the series. At step 39 the
        # runner held 185,632 kilobytes of text before the bar,
        # and 246,772 where the bytes are not text.
        for size in (1346269, 14930352, 63245986):
            for byte in ("a", "\\377"):
                got = runner_of_its_own(writes(size, byte))
                self.assertEqual((0, "attested"), (got["exit"], got["view"]))
                self.assertLess(got["peak"] - base["peak"], 4000,
                                (size, byte))
        # The costliest kind found, which the ladder did not
        # have: 4,172 kilobytes at step 36 as measured, and flat.
        got = runner_of_its_own(writes_wide_on_both(14930352))
        self.assertEqual((0, "attested"), (got["exit"], got["view"]))
        self.assertLess(got["peak"] - base["peak"], 8000)

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_h4_a_job_that_writes_until_its_limit(self):
        base = runner_of_its_own(":")
        # 300 megabytes, and then the job waits for its limit of
        # 3 seconds. The writing is bounded, so that a reader
        # without a bar would be seen and not felt.
        got = runner_of_its_own(writes(300000000) + "; sleep 60", 3)
        self.assertEqual((True, -1), (got["timed_out"], got["exit"]))
        self.assertLess(got["peak"] - base["peak"], 4000)


class TheShareOfTheLog(unittest.TestCase):
    """L2: with a log kept, as a running runner keeps 1, the
    runner's memory is small since a job has a share of the
    log."""

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_l2_with_a_log_kept_the_runner_s_memory(self):
        base = runner_of_its_own(":", log=True)
        self.assertEqual((0, "attested"), (base["exit"], base["view"]))
        # Plain text on 1 stream, at step 36 of the series. With
        # the log's size for a bar it read 164,088 kilobytes at
        # the top step, and the same at every step past the bar.
        got = runner_of_its_own(writes(14930352), log=True)
        self.assertEqual((0, "attested"), (got["exit"], got["view"]))
        self.assertLess(got["peak"] - base["peak"], 10000)
        # The costliest kind found, on both streams: it read
        # 682,860.
        got = runner_of_its_own(writes_wide_on_both(14930352), log=True)
        self.assertEqual((0, "attested"), (got["exit"], got["view"]))
        self.assertLess(got["peak"] - base["peak"], 50000)
        # What that job's record is in the log: the share of each
        # stream, 1 wide character in each, and the frame.
        self.assertLess(got["logged"], 2 * RUNNER.JOB_LOG_SHARE + 600)
        self.assertGreater(got["logged"], 2 * RUNNER.JOB_LOG_SHARE)


# ---- The other 3 systems

class TheOtherSystems(unittest.TestCase):
    """H7: a wrapped process is lent to the same reader, and the
    Windows pumps keep a bar of their own."""

    def test_the_freebsd_wrapper_lends_its_process_to_the_reader(self):
        inner = writer(5000, b"e", 4)
        proc = freebsd_confine.FreeBSDConfinedProcess(
            ["x"], inner, None, None, None, None, None, None, "status", ())
        held = Held(100)
        self.assertEqual((cycle(5000)[:100], b"e"),
                         proc.communicate_held(held, 60))
        self.assertEqual(4, proc.returncode)
        self.assertEqual(5000, held.seen["stdout"])
        self.assertTrue(held.cut("stdout"))

    def test_the_2_wrappers_carry_the_same_method(self):
        lend = (
            "def communicate_held(self, held, timeout=None):",
            "out, err = held(self._inner, timeout)",
            "self.returncode = self._inner.returncode")
        for name in ("freebsd_confine.py", "macos_confine.py"):
            text = _read(os.path.join(ROOT, "runner", "guard", name))
            at = text.index(lend[0])
            for line in lend[1:]:
                self.assertIn(line, text[at:at + 700], (name, line))

    def test_the_executor_asks_a_wrapper_before_it_reads_itself(self):
        text = _read(os.path.join(ROOT, "runner", "ops", "exec.py"))
        self.assertIn(
            "    def collect(wait):\n"
            "        if getattr(type(proc), \"communicate_held\", None) "
            "is not None:\n"
            "            return proc.communicate_held(held, wait)\n"
            "        return held(proc, wait)\n", text)
        self.assertEqual(3, text.count("outs, errs = collect("))
        self.assertNotIn("proc.communicate(", text[
            text.index("held = _runner()._held_for_job(max_out)"):
            text.index("duration = round(time.monotonic() - t0, 3)")])

    def test_the_windows_pumps_carry_a_bar_from_the_first_byte(self):
        text = _read(os.path.join(ROOT, "runner", "guard",
                                  "windows_confine.py"))
        self.assertEqual(67108864, windows_confine.PUMP_HELD_BYTES)
        for line in (
                "            self._keep = PUMP_HELD_BYTES\n",
                "                self._seen[index] += got.value\n"
                "                room = self._keep - len(sink)\n"
                "                if room > 0:\n"
                "                    sink.extend(buf.raw[:min(got.value, "
                "room)])\n",
                "            self._keep = min(self._keep, held.keep)\n"
                "            out, err = self.communicate(timeout)\n"
                "            out, err = out[:self._keep], err[:self._keep]\n"
                "            held.took(\"stdout\", out, self._seen[0])\n"
                "            held.took(\"stderr\", err, self._seen[1])\n"):
            self.assertIn(line, text, line)
        # No pump holds without the bar any more.
        self.assertNotIn("sink.extend(buf.raw[:got.value])", text)

    @unittest.skipUnless(
        WINDOWS, "the Windows backend's pumps are read on Windows")
    def test_on_windows_a_real_pump_holds_the_first_part(self):
        program = ("import sys\n"
                   "sys.stdout.buffer.write(b'a' * 3000000)\n"
                   "sys.stderr.buffer.write(b'b' * 10)\n")
        proc = windows_confine.spawn_job_object_process(
            [sys.executable, "-c", program])
        try:
            held = Held(1000)
            out, err = proc.communicate_held(held, 120)
            self.assertEqual((b"a" * 1000, b"b" * 10), (out, err))
            self.assertEqual({"stdout": 3000000, "stderr": 10}, held.seen)
            self.assertTrue(held.cut("stdout"))
            self.assertFalse(held.cut("stderr"))
            self.assertEqual(0, proc.returncode)
        finally:
            proc.close()


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class ThePageRecordsTheModel(unittest.TestCase):
    """The figures of the model on the page are this module's."""

    def test_the_page_states_the_rule_the_bar_and_the_checker_s_word(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "**The rule.** The runner holds at most a fixed number of "
                "bytes of each stream of a job, whatever the job writes.",
                "4 bytes for each character of the output cap, and 4 more",
                "295 distinct states among 665 generated, to a depth of 19",
                "| `heldbar.cfg` | with the bar | 7 invariants hold on all "
                "295 states |",
                "| `heldasitwas.cfg` | as it was | the 6 that are not the "
                "bar hold |",
                "a job writes 10 and all 10 are held, past a bar of 9",
                "a job writes 5 and its result carries 4",
                "breaks the bar on 165 of its 295 states"):
            self.assertIn(stated, page, stated)
        self.assertEqual((7, 6), (
            len(CONFIGURATIONS["heldbar.cfg"][2]),
            len(CONFIGURATIONS["heldasitwas.cfg"][2])))
        # The bar with the log on at its default size.
        self.assertIn("33,816,576 bytes a stream", page)
        self.assertEqual(33816576, 33554432 + 4 * 65536)

    # The closing's measure, as taken for the page: the runner's
    # memory at its highest above its base, in kilobytes, for a
    # job that writes 63,245,986 bytes. The 4 kinds of output:
    # text, bytes that are not text, and each of them behind 1
    # character of 4 bytes. With no log: before the bar on 1
    # stream, and with the bar on 1 stream and on both.
    KINDS = ("Text", "Bytes that are not text",
             "Text behind 1 character of 4 bytes",
             "Not text, behind such a character")
    NO_LOG = ((185632, 500, 1280), (246772, 1320, 2964),
              (None, 2164, 4840), (None, 2092, 4076))
    # With a log kept: on 1 stream, and on both.
    WITH_LOG = (("33,554,432, the default", 33554432,
                 ((164088, 229096), (328088, 415940),
                  (492972, 682860), (558480, 657300))),
                ("2,097,152", 2097152,
                 ((10584, 13776), (21864, 26824),
                  (32492, 44360), (36476, 48720))))

    def test_the_page_states_the_measure_and_what_held(self):
        page = MODELS._flat(PAGE)
        self.assertIn("## F17 closed: the measure, and what held", page)
        comma = lambda number: (  # noqa: E731
            "not measured" if number is None else format(number, ","))
        for kind, row in zip(self.KINDS, self.NO_LOG):
            self.assertIn("| %s | %s |" % (
                kind, " | ".join(map(comma, row))), page)
        # H2, as it was supposed, is of the ladder's own 2 kinds
        # on 1 stream: with the bar each is under 4,000, where
        # each was over 10 times that.
        for before, one, _both in self.NO_LOG[:2]:
            self.assertLess(one, 4000)
            self.assertGreater(before, 10 * 4000)
        # The costliest kind is over the 4,000, and flat.
        self.assertEqual(4840, max(max(row[1:]) for row in self.NO_LOG))
        self.assertIn("read 4,056 for a job writing 1,346,269 bytes on "
                      "each stream, and 4,172 for 14,930,352", page)
        for name, size, rows in self.WITH_LOG:
            bar = HELPERS.held_bound(100000, size)
            for at, (kind, row) in enumerate(zip(self.KINDS, rows)):
                # The log's size stands in the first of its 4 rows.
                first = "| %s |" % name if at == 0 else "| |"
                self.assertIn("%s %s | %s |" % (
                    first, kind, " | ".join(map(comma, row))), page)
                # A fixed multiple of the bar, and never under it.
                for reading in row:
                    self.assertTrue(1 < reading * 1024 / bar < 22,
                                    (name, kind, reading))
        default = HELPERS.held_bound(100000, 33554432)
        ones = [row[0] * 1024 / default for row in self.WITH_LOG[0][2]]
        twos = [row[1] * 1024 / default for row in self.WITH_LOG[0][2]]
        self.assertEqual(("5", "17", "21"), (
            "%.0f" % min(ones), "%.0f" % max(ones), "%.0f" % max(twos)))
        # Letters behind 1 wide character cost 3 times the
        # letters alone, where a log is kept.
        for _name, _size, rows in self.WITH_LOG:
            self.assertEqual("3", "%.0f" % (rows[2][0] / rows[0][0]))
        for stated in (
                "At the default that is 5 to 17 times the bar for 1 "
                "stream, and up to 21 times for both",
                "33,816,576 bytes a stream at the default",
                "The 400,004 bytes of the output cap are the bar where no "
                "log is kept",
                "It is 0.007 and 0.011 now",
                "read 674,788 for a job writing 40,000,000 bytes on each "
                "stream, and 673,408 for 200,000,000",
                "the runner read 456 kilobytes above its base",
                "5 at the default cap, and 5 with a log kept: 0 differ. "
                "Held |",
                "| H2 | Under 4,000 kilobytes at every step | On the "
                "ladder's own 2 kinds, at most 1,320. Held. A kind the "
                "ladder did not have, text made wide on both streams, "
                "reads 4,840: flat, and over the 4,000 |",
                "is 5 to 21 times that bar",
                "at most 67,108,864 bytes of a stream",
                "The 4 bytes are a margin, and nothing rests on them",
                "cost 3 times what the letters cost alone"):
            self.assertIn(stated, page, stated)
        self.assertEqual(67108864, windows_confine.PUMP_HELD_BYTES)
        # The table of the bars carries the bar, on every system.
        self.assertNotIn("| What the runner holds while the job runs | "
                         "no bar |", page)

    # The measure of the log's share, as taken for the page: with
    # the log kept at its default size, the same job, in the same
    # 4 kinds. Kilobytes above the base on 1 stream and on both,
    # with the share; and the bytes the job's record added to the
    # log, on 1 stream and on both.
    SHARE = ((4352, 9568, 1048843, 2097426),
             (10448, 21556, 3145995, 6291730),
             (17068, 32448, 1048846, 2097432),
             (19152, 36884, 3145996, 6291732))

    def test_the_page_states_the_share_and_what_held(self):
        page = MODELS._flat(PAGE)
        self.assertIn(
            "## The log's share: the rule, and what is expected", page)
        self.assertIn(
            "## The log's share: the measure, and what held", page)
        self.assertLess(
            page.index("## The log's share: the rule"),
            page.index("## The log's share: the measure"))
        comma = lambda number: format(number, ",")  # noqa: E731
        share = RUNNER.JOB_LOG_SHARE
        before = self.WITH_LOG[0][2]
        for kind, was, row in zip(self.KINDS, before, self.SHARE):
            one, both, logged_one, logged_both = row
            self.assertIn("| %s | %s | %s | %s | %s |" % (
                kind, comma(was[0]), comma(one), comma(was[1]),
                comma(both)), page)
            self.assertIn("| %s | %s | %s |" % (
                kind, comma(logged_one), comma(logged_both)), page)
            # L2: under 50,000 kilobytes, where each was over
            # 160,000.
            self.assertLess(max(one, both), 50000)
            self.assertGreater(min(was), 160000)
            # What a record adds: the share of each stream in
            # characters, 1 or 3 bytes for each, and a frame.
            for logged, streams in ((logged_one, 1), (logged_both, 2)):
                wide = 3 if "ot text" in kind else 1
                frame = logged - streams * wide * share
                self.assertTrue(0 < frame < 400, (kind, frame))
        self.assertEqual(36884, max(max(row[:2]) for row in self.SHARE))
        self.assertLess(self.SHARE[0][0], 10000)
        for stated in (
                "**The owner's word, 20 November.** A job's share of the "
                "log is 1 megabyte for each of its streams.",
                "1,310,720 bytes a stream, where it was 33,816,576",
                "I expect about 35,000, and under 50,000",
                "The most on the table is 36,884, where it was 682,860",
                "read 32,676 for a job writing 1,346,269 bytes on each, "
                "32,520 for 14,930,352, 32,712 for 40,000,000 and 28,880 "
                "for 200,000,000",
                "It is 0.018 and 0.071 now",
                "| L2 | About 35,000 kilobytes for the costliest kind, and "
                "under 50,000. Under 10,000 for plain text on 1 stream | "
                "36,884 and 4,352. Held |",
                "| L6 | A job of text on both streams adds 2,097,152 bytes "
                "and a frame of under 400 | 2,097,426: a frame of 274. "
                "Held |",
                "1,820 kilobytes for text on 1 stream, where the table has "
                "4,352",
                "starts 6,940 kilobytes higher"):
            self.assertIn(stated, page, stated)
        # The table of the bars carries the bar as it is now, on
        # every system.
        self.assertIn(
            "| What the runner holds while the job runs | 1,310,720 "
            "bytes of a stream: a job's share of the log and the tail "
            "its record leaves out. 400,004 where no log is kept | the "
            "same | the same | the same |", page)
        self.assertEqual(1310720, HELPERS.held_bound(100000, share))


if __name__ == "__main__":
    unittest.main()
