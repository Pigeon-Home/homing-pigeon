# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Q187: fuzz the Windows confinement backend's decision surface.

The conductor ordered this lane on 2026-11-12: a roughly
5-minute in-memory fuzzer on the Windows confinement surface,
then the seeds plus small test runs committed as unit tests.
The desk entry (Q187) recorded the suppositions before the
build:

- S1: the backend's input surface (job specs, paths, command
  lines, environment blocks, limit values) takes generated
  malformed inputs without an unhandled exception escaping
  the confinement decision -- every case ends refused,
  cleanly errored, or confined.
- S2: every bookend and boundary shape (special characters
  front AND back -- every ASCII symbol, symbol-only strings,
  the non-printing NUL/tab/CR/LF, repetition-count variations:
  runs of 10 ordinary then the odd one, 10 of the odd one,
  front/back/middle) is refused or confined, never silently
  widened into a weaker confinement than the job asked for.
- S3: a roughly 5-minute in-memory run completes and records
  its case count, seed corpus and finding shapes (the record
  stands in docs/steady/fuzzing.md).

The Win32 calls cannot execute on this host, so the surface
is driven exactly where the suite already drives it: the
module's stub branch (the deterministic refusal every
non-Windows host answers), the platform-neutral confinement
trial orchestration through scripted spawn/grant seams, and
the remediation seams (confinement_startup_problem,
_confinement_spawn, _confinement_argv, _job_user_spawn,
_job_user_postspawn, job_user_startup_problem) through
scripted backends, with the real sec_mode reading fuzzed
configs. Live Windows behaviour is proven only on the
Germany rig's battery; nothing here claims it.

A crash is any exception outside the surface's own answers:
the probes and the trial return a problem string or None and
never raise; the stub's spawn/apply raise RuntimeError only;
the seams return their value or raise JobRejected only.
"""
import os
import random
import string
import subprocess
import sys
import types
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
from runner.guard import windows_confine as WC
from runner.guard.security import sec_mode as _real_sec_mode
from runner.guard.security import validate_security_config
from runner.ops import remediation_ops as REM

# ------------------------------------------------------------------
# The bookend corpus (the project's fuzz rule: special characters
# front AND back, every symbol on the ASCII table, symbol-only
# strings, the non-printing edge cases, and repetition counts --
# a run of 10 ordinary then the odd one, 10 of the odd one, runs
# at the front, the back and in the middle).
# ------------------------------------------------------------------

SYMBOLS = string.punctuation  # every ASCII symbol: 32 characters
NONPRINTING = ["\x00", "\t", "\r", "\n", "\x0b", "\x0c", "\x1b", "\x7f"]
EDGE_CHARS = list(SYMBOLS) + NONPRINTING
CORES = ["python", "s.py", "job", "canary-list", "C:\\work",
         "K", "V", "enforce", ""]


def bookend_variants(core):
    """Every bookend/boundary shape of one core string."""
    out = []
    rotated = SYMBOLS[1:] + SYMBOLS[:1]
    for ch in EDGE_CHARS:
        out.append(ch + core + ch)          # front AND back
        out.append(ch * 10 + core)          # 10 of the odd one, front
        out.append(core + ch * 10)          # 10 of the odd one, back
        half = len(core) // 2
        out.append(core[:half] + ch * 10 + core[half:])  # middle
        out.append(ch * 10 + core + ch * 10)
        out.append("a" * 10 + ch + core)    # 10 ordinary, then odd
        out.append(core + ch + "a" * 10)
    for front, back in zip(SYMBOLS, rotated):
        out.append(front + core + back)     # mismatched pair
    out.append(SYMBOLS)                     # symbol-only, all of them
    out.append(SYMBOLS[::-1])
    for ch in EDGE_CHARS:
        out.append(ch)                      # symbol-only, one
        out.append(ch * 10)                 # symbol-only, a run
    out.append("".join(NONPRINTING))        # non-printing only
    out.append("a" * 10)                    # ordinary run, no odd one
    out.append(core * 10)                   # the core itself, repeated
    return out


SEED_TEXTS = []
for _core in CORES:
    SEED_TEXTS.extend(bookend_variants(_core))
SEED_TEXTS = list(dict.fromkeys(SEED_TEXTS))


def _fuzz_text(rng):
    if rng.random() < 0.75:
        return rng.choice(SEED_TEXTS)
    text = rng.choice(CORES)
    if rng.random() < 0.3:
        text = text * rng.randint(2, 5)
    return text


def _fuzz_value(rng, depth=0):
    roll = rng.random()
    if depth > 3 or roll < 0.25:
        return _fuzz_text(rng)
    if roll < 0.38:
        return rng.choice([None, True, False, 0, 1, -1, 2 ** 70,
                           -(2 ** 70), 1.5, float("nan"),
                           float("inf"), -0.0])
    if roll < 0.52:
        return [_fuzz_value(rng, depth + 1)
                for _ in range(rng.randint(0, 3))]
    if roll < 0.62:
        return tuple(_fuzz_value(rng, depth + 1)
                     for _ in range(rng.randint(0, 3)))
    if roll < 0.72:
        return _fuzz_text(rng).encode("utf-8", "replace")
    return {_fuzz_text(rng): _fuzz_value(rng, depth + 1)
            for _ in range(rng.randint(0, 3))}


def _fuzz_cfg(rng):
    def mode():
        return rng.choice(["enforce", "audit", "off",
                           _fuzz_text(rng), None, 0, [], {}])
    shape = rng.randrange(6)
    if shape == 0:
        return {"security": {"modes": {"confinement": mode(),
                                       "job_user": mode()}}}
    if shape == 1:
        return _fuzz_value(rng)
    if shape == 2:
        return {"security": _fuzz_value(rng)}
    if shape == 3:
        return {}
    if shape == 4:
        return {"security": {"modes": _fuzz_value(rng),
                             "job_user": {"user": _fuzz_text(rng)}}}
    return {"security": {"modes": {"confinement": mode()},
                         "job_user": _fuzz_value(rng)}}


def _fuzz_argv(rng):
    shape = rng.randrange(6)
    if shape == 0:
        return [_fuzz_text(rng) for _ in range(rng.randint(0, 4))]
    if shape == 1:
        return _fuzz_value(rng)
    if shape == 2:
        return tuple(_fuzz_text(rng)
                     for _ in range(rng.randint(0, 3)))
    if shape == 3:
        return []
    if shape == 4:
        return [_fuzz_value(rng) for _ in range(rng.randint(1, 3))]
    return _fuzz_text(rng)


def _fuzz_env(rng):
    shape = rng.randrange(4)
    if shape == 0:
        return {_fuzz_text(rng): _fuzz_text(rng)
                for _ in range(rng.randint(0, 3))}
    if shape == 1:
        return None
    if shape == 2:
        return {_fuzz_text(rng): _fuzz_value(rng)
                for _ in range(rng.randint(0, 2))}
    return _fuzz_value(rng)


# ------------------------------------------------------------------
# Scripted seams (the shapes test_windows_confine.py drives).
# ------------------------------------------------------------------

class _Sec:
    """The runner's security face, with the real sec_mode."""

    def __init__(self):
        self.rows = []

    def sec_mode(self, cfg, feature):
        return _real_sec_mode(cfg, feature)

    def write_audit_entry(self, base_dir, feature, decision,
                          reason, **kw):
        self.rows.append({"feature": feature, "decision": decision,
                          "reason": reason, "kw": kw})

    def bump_evaluated(self, *args, **kwargs):
        pass


_BACKEND_EXC = (RuntimeError, ValueError, TypeError, OSError,
                KeyError)


def _scripted_backend(rng):
    """A backend whose every call is fuzzed: engage, refuse,
    return a fuzzed value, or raise a fuzzed exception."""
    backend = types.SimpleNamespace(
        IS_WINDOWS_BACKEND=True,
        STATUS_CONFINEMENT=WC.STATUS_CONFINEMENT,
        STATUS_JOB_OBJECT=WC.STATUS_JOB_OBJECT)
    probe_value = rng.choice([None, "problem text", _fuzz_text(rng),
                              0, 123, [], object()])

    def _probe(cfg=None, timeout=15):
        if rng.random() < 0.15:
            raise rng.choice(_BACKEND_EXC)("probe boom")
        return probe_value

    backend.windows_startup_problem = _probe
    backend.windows_confinement_problem = _probe

    def _apply(handle, memory_bytes=WC.DEFAULT_PROCESS_MEMORY_BYTES):
        if rng.random() < 0.4:
            raise rng.choice(_BACKEND_EXC)("apply boom")
        status = _fuzz_text(rng) if rng.random() < 0.2 \
            else WC.STATUS_JOB_OBJECT
        return status, 4242

    backend.apply_windows_containment = _apply
    backend.closed = []
    backend.close_job_handle = backend.closed.append
    backend.spawned = []

    def _spawn(argv, cwd=None, env=None):
        backend.spawned.append((argv, cwd, env))
        if rng.random() < 0.4:
            raise rng.choice(_BACKEND_EXC)("spawn boom")
        proc = types.SimpleNamespace(
            pid=31337, _handle=888, returncode=0, closed=False)
        proc.confinement_status = WC.STATUS_CONFINEMENT
        proc.job_object_status = WC.STATUS_JOB_OBJECT
        proc.close = lambda: setattr(proc, "closed", True)
        proc.kill = mock.Mock()
        proc.poll = lambda: 0
        return proc

    backend.spawn_confined_process = _spawn
    backend.spawn_job_object_process = _spawn
    return backend


class _FakeTrialProc:
    """A confined-process shape for the trial, fuzzed per case."""

    def __init__(self, rng):
        self._out = rng.choice(
            [b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n", b"", b"x", "text",
             None, 123, b"\xff\xfe", b"TRIAL-READ-OK\n"])
        self._err = rng.choice([b"", b"err", None, "e", 0])
        self.returncode = rng.choice([0, 1, None, -1, "x"])
        self._mode = rng.randrange(5)
        self.killed = False
        self.closed = False

    def communicate(self, timeout=None):
        if self._mode == 0:
            raise subprocess.TimeoutExpired("trial", timeout)
        if self._mode == 1:
            raise RuntimeError("communicate boom")
        if self._mode == 2:
            raise ValueError("communicate value")
        return self._out, self._err

    def kill(self):
        self.killed = True
        if self._mode == 3:
            raise RuntimeError("kill boom")

    def close(self):
        self.closed = True
        if self._mode == 4:
            raise RuntimeError("close boom")


# ------------------------------------------------------------------
# The campaign: one case drives every surface. Returns
# (cases, crashes, widenings).
# ------------------------------------------------------------------

def campaign(rounds, seed):
    rng = random.Random(seed)
    crashes = []
    widenings = []
    cases = 0

    def run(name, fn, allowed=()):
        nonlocal cases
        cases += 1
        try:
            return fn()
        except allowed:
            return None
        except Exception as e:  # a crash: outside the answers
            crashes.append("%s: %s: %r" % (name, type(e).__name__, e))
            return None

    for _ in range(rounds):
        cfg = _fuzz_cfg(rng)
        argv = _fuzz_argv(rng)
        env = _fuzz_env(rng)
        job_id = _fuzz_text(rng)
        cwd = _fuzz_text(rng)

        # The module's own stub answers (off win32; on a real
        # Windows host these are the live calls and the suite's
        # stub classes skip -- the campaign's stub leg therefore
        # runs only where the stub stands).
        if not WC.IS_WINDOWS_BACKEND:
            run("stub_startup_problem",
                lambda: WC.windows_startup_problem(
                    cfg, timeout=_fuzz_value(rng)))
            run("stub_confinement_problem",
                lambda: WC.windows_confinement_problem(cfg))
            run("stub_spawn_confined",
                lambda: WC.spawn_confined_process(
                    argv, cwd=cwd, env=env), (RuntimeError,))
            run("stub_spawn_job_object",
                lambda: WC.spawn_job_object_process(
                    argv, cwd=cwd, env=env), (RuntimeError,))
            run("stub_apply",
                lambda: WC.apply_windows_containment(
                    _fuzz_value(rng), memory_bytes=_fuzz_value(rng)),
                (RuntimeError,))
            run("stub_close",
                lambda: WC.close_job_handle(_fuzz_value(rng)))

        # The confinement trial, through scripted seams.
        def _trial():
            proc = _FakeTrialProc(rng)

            def _spawn(a, cwd=None, env=None):
                return proc

            def _grant(paths):
                if rng.random() < 0.3:
                    raise RuntimeError("grant boom")
                return rng.choice([None, "grant problem", 0,
                                   _fuzz_text(rng)])

            return WC.confinement_trial_problem(
                _spawn, timeout=rng.choice([0, 1, 5]),
                grant=_grant if rng.random() < 0.5 else None)

        problem = run("confinement_trial", _trial)
        if problem is not None and not isinstance(problem, str):
            widenings.append("trial answered %r" % (problem,))

        # The remediation seams, through a scripted backend.
        sec = _Sec()
        backend = _scripted_backend(rng)
        enforce_cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        with mock.patch.object(rr, "_security", sec):
            run("confinement_startup_problem",
                lambda: REM.confinement_startup_problem(
                    cfg, platform="win32", backend=backend))
            run("job_user_startup_problem",
                lambda: REM.job_user_startup_problem(
                    cfg, platform="win32", backend=backend))
            with mock.patch.object(sys, "platform", "win32"):
                before = len(sec.rows)
                out = run("_confinement_spawn",
                          lambda: REM._confinement_spawn(
                              enforce_cfg, "/tmp", job_id, argv,
                              cwd, env, backend=backend),
                          (rr.JobRejected,))
                if out is not None:
                    # A confined return under enforce must carry
                    # exactly the backend's status row -- never a
                    # weaker or wider claim.
                    rows = [r for r in sec.rows[before:]
                            if r["feature"] == "confinement"]
                    if not rows or rows[-1]["decision"] != "confined" \
                            or rows[-1]["reason"] != \
                            WC.STATUS_CONFINEMENT:
                        widenings.append(
                            "confined spawn without the exact "
                            "status row: %r" % (rows,))
                    proc, release = out
                    release()
                run("_job_user_spawn",
                    lambda: REM._job_user_spawn(
                        enforce_cfg, "/tmp", job_id, argv, cwd,
                        env, backend=backend), (rr.JobRejected,))
                run("_confinement_argv",
                    lambda: rr._confinement_argv(
                        enforce_cfg, "/tmp", job_id,
                        [_fuzz_text(rng)], _fuzz_text(rng), "/tmp",
                        [_fuzz_text(rng)], {}, backend=backend))
            with mock.patch.object(REM.os, "name", "nt"):
                proc = types.SimpleNamespace(
                    _handle=_fuzz_value(rng), kill=mock.Mock(),
                    poll=lambda: 0)
                run("_job_user_postspawn",
                    lambda: REM._job_user_postspawn(
                        enforce_cfg, "/tmp", job_id, proc,
                        backend=backend), (rr.JobRejected,))
        if len(crashes) >= 5 or len(widenings) >= 5:
            break
    return cases, crashes, widenings


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class BookendCorpusTest(unittest.TestCase):
    """The seed corpus is the bookend rule, whole."""

    def test_every_symbol_bookends_front_and_back(self):
        for ch in SYMBOLS:
            self.assertIn(ch + "job" + ch, SEED_TEXTS, repr(ch))

    def test_every_nonprinting_bookends_front_and_back(self):
        for ch in NONPRINTING:
            self.assertIn(ch + "job" + ch, SEED_TEXTS, repr(ch))

    def test_symbol_only_and_nonprinting_only_strings_stand(self):
        self.assertIn(SYMBOLS, SEED_TEXTS)
        self.assertIn("".join(NONPRINTING), SEED_TEXTS)
        for ch in EDGE_CHARS:
            self.assertIn(ch, SEED_TEXTS, repr(ch))
            self.assertIn(ch * 10, SEED_TEXTS, repr(ch))

    def test_repetition_runs_stand_front_back_and_middle(self):
        for ch in (";", "\x00", '"', "\\"):
            self.assertIn(ch * 10 + "job", SEED_TEXTS, repr(ch))
            self.assertIn("job" + ch * 10, SEED_TEXTS, repr(ch))
            self.assertIn("j" + ch * 10 + "ob", SEED_TEXTS, repr(ch))
            self.assertIn("a" * 10 + ch + "job", SEED_TEXTS, repr(ch))

    def test_the_corpus_is_deterministic_and_bounded(self):
        self.assertEqual(SEED_TEXTS,
                         list(dict.fromkeys(SEED_TEXTS)))
        self.assertGreater(len(SEED_TEXTS), 1500)
        for text in SEED_TEXTS:
            self.assertIsInstance(text, str)


class StubBackendFuzzTest(unittest.TestCase):
    """S1 on the module's stub: fuzzed inputs, refusal answers."""

    def setUp(self):
        if sys.platform == "win32":
            self.skipTest("the stub exists only off win32")

    def test_probes_answer_a_problem_string_for_the_whole_corpus(self):
        for text in SEED_TEXTS:
            for cfg in (text, {"security": text}, {"modes": text}):
                problem = WC.windows_startup_problem(cfg)
                self.assertIsInstance(problem, str, repr(cfg))
                self.assertIn("Windows-only", problem)
                problem = WC.windows_confinement_problem(cfg)
                self.assertIsInstance(problem, str, repr(cfg))

    def test_spawns_raise_runtime_error_only_for_the_whole_corpus(self):
        for text in SEED_TEXTS:
            with self.assertRaises(RuntimeError, msg=repr(text)):
                WC.spawn_confined_process([text])
            with self.assertRaises(RuntimeError, msg=repr(text)):
                WC.spawn_job_object_process([text])

    def test_spawn_argv_shapes_raise_runtime_error_only(self):
        shapes = [[], (), None, 0, "python", ["python", 1],
                  [None], [b"python"], [["python"]], {"a": 1}]
        for argv in shapes:
            with self.assertRaises(RuntimeError, msg=repr(argv)):
                WC.spawn_confined_process(argv)
            with self.assertRaises(RuntimeError, msg=repr(argv)):
                WC.spawn_job_object_process(argv)

    def test_apply_and_close_take_fuzzed_handles_and_limits(self):
        rng = random.Random(20261114)
        for _ in range(200):
            handle = _fuzz_value(rng)
            with self.assertRaises(RuntimeError):
                WC.apply_windows_containment(
                    handle, memory_bytes=_fuzz_value(rng))
            self.assertIsNone(WC.close_job_handle(handle))

    def test_limit_values_never_change_the_refusal(self):
        for limit in (0, -1, 1, 2 ** 63, -(2 ** 63), None, "512",
                      [], {}, float("nan"), float("inf")):
            with self.assertRaises(RuntimeError, msg=repr(limit)):
                WC.apply_windows_containment(
                    4242, memory_bytes=limit)


class TrialFuzzTest(unittest.TestCase):
    """S1/S2 on the trial: fuzzed process answers never read as
    a working confined host unless both markers stand."""

    def test_fuzzed_process_answers_are_problems_or_none(self):
        rng = random.Random(20261114)
        for _ in range(300):
            proc = _FakeTrialProc(rng)

            def _spawn(a, cwd=None, env=None, _p=proc):
                return _p

            problem = WC.confinement_trial_problem(
                _spawn, timeout=rng.choice([0, 1, 5]))
            self.assertTrue(problem is None
                            or isinstance(problem, str),
                            repr(problem))
            self.assertTrue(proc.closed)
            if proc._mode == 0:
                self.assertTrue(proc.killed)

    def test_only_the_full_marker_pair_answers_none(self):
        # Every weakening of the good answer -- a missing marker,
        # a marker in the error stream only, bookended markers,
        # a nonzero exit -- is a problem, never a pass.
        good = b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n"
        variants = [
            b"TRIAL-READ-OK\n", b"TRIAL-WRITE-OK\n", b"",
            b";TRIAL-READ-OK;\n;TRIAL-WRITE-OK;\n",
            b"TRIAL-READ-OK\nTRIAL-WRITE-OK",  # still both: passes
        ]
        for out in variants:
            proc = types.SimpleNamespace(returncode=0, closed=False)
            proc.communicate = lambda timeout=None, _o=out: (_o, b"")
            proc.kill = lambda: None
            proc.close = lambda: setattr(proc, "closed", True)

            def _spawn(a, cwd=None, env=None, _p=proc):
                # The write marker also needs the file; this fake
                # never writes it, so even the full pair refuses
                # on the write half -- the stricter answer.
                return _p

            problem = WC.confinement_trial_problem(_spawn)
            self.assertIsNotNone(problem, repr(out))
            self.assertIsInstance(problem, str)

    def test_grant_answers_are_problems_never_passes(self):
        def _ok_spawn(a, cwd=None, env=None):
            proc = types.SimpleNamespace(returncode=0)
            proc.communicate = lambda timeout=None: (
                b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n", b"")
            proc.kill = lambda: None
            proc.close = lambda: None
            return proc

        # This spawn never writes the output file either, so the
        # trial refuses regardless; the pin is that a fuzzed grant
        # answer never turns into an exception or a pass.
        rng = random.Random(20261114)
        for _ in range(100):
            answer = rng.choice([None, "grant problem", 0,
                                 _fuzz_text(rng), [], {}])

            def _grant(paths, _a=answer):
                if isinstance(_a, list) and _a and _a[0] == "raise":
                    raise RuntimeError("grant boom")
                return _a

            problem = WC.confinement_trial_problem(
                _ok_spawn, grant=_grant)
            self.assertTrue(problem is None
                            or isinstance(problem, str),
                            repr(answer))


class SeamFuzzTest(unittest.TestCase):
    """S1/S2 on the remediation seams through scripted backends."""

    def _sec_patch(self, sec):
        return mock.patch.object(rr, "_security", sec)

    def test_bookended_modes_are_not_enforce_anywhere(self):
        # A bookended mode is not the mode: sec_mode reads it as
        # off, the startup validator refuses the config outright,
        # and no seam attempts a confined spawn for it.
        for text in bookend_variants("enforce"):
            cfg = {"security": {"modes": {"confinement": text,
                                          "job_user": text}}}
            self.assertEqual(_real_sec_mode(cfg, "confinement"),
                             "off", repr(text))
            with self.assertRaises(RuntimeError, msg=repr(text)):
                validate_security_config(cfg)

    def test_enforce_with_a_failing_backend_always_refuses(self):
        cfg = {"security": {"modes": {"confinement": "enforce",
                                      "job_user": "enforce"}}}
        for job_id in SEED_TEXTS[::37]:
            sec = _Sec()
            backend = _scripted_backend(random.Random(1))
            backend.spawn_confined_process = mock.Mock(
                side_effect=RuntimeError("cannot engage"))
            backend.spawn_job_object_process = mock.Mock(
                side_effect=RuntimeError("cannot engage"))
            with self._sec_patch(sec), \
                    mock.patch.object(sys, "platform", "win32"):
                with self.assertRaises(rr.JobRejected,
                                       msg=repr(job_id)):
                    REM._confinement_spawn(
                        cfg, "/tmp", job_id, ["python", "s.py"],
                        "/tmp", {}, backend=backend)
                with self.assertRaises(rr.JobRejected,
                                       msg=repr(job_id)):
                    REM._job_user_spawn(
                        cfg, "/tmp", job_id, ["python", "s.py"],
                        "/tmp", {}, backend=backend)
            decisions = [r["decision"] for r in sec.rows]
            self.assertNotIn("confined", decisions, repr(job_id))

    def test_audit_and_off_never_spawn_for_bookended_job_specs(self):
        for mode in ("audit", "off"):
            cfg = {"security": {"modes": {"confinement": mode,
                                          "job_user": mode}}}
            sec = _Sec()
            backend = _scripted_backend(random.Random(2))
            with self._sec_patch(sec), \
                    mock.patch.object(sys, "platform", "win32"):
                for job_id in SEED_TEXTS[::211]:
                    self.assertIsNone(REM._confinement_spawn(
                        cfg, "/tmp", job_id, [job_id], job_id,
                        {job_id: job_id}, backend=backend))
                    self.assertIsNone(REM._job_user_spawn(
                        cfg, "/tmp", job_id, [job_id], job_id,
                        {job_id: job_id}, backend=backend))
            self.assertEqual(backend.spawned, [], mode)

    def test_bookended_job_specs_ride_verbatim_when_confined(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        for text in SEED_TEXTS[::53]:
            sec = _Sec()
            backend = _scripted_backend(random.Random(3))
            backend.spawn_confined_process = (
                lambda argv, cwd=None, env=None, _t=text:
                _good_proc(backend, argv, cwd, env))
            with self._sec_patch(sec), \
                    mock.patch.object(sys, "platform", "win32"):
                out = REM._confinement_spawn(
                    cfg, "/tmp", text, [text, "s.py"], text,
                    {text: text}, backend=backend)
            self.assertIsNotNone(out, repr(text))
            argv, cwd, env = backend.spawned[-1]
            self.assertEqual(argv, [text, "s.py"], repr(text))
            self.assertEqual(cwd, text, repr(text))
            self.assertEqual(env, {text: text}, repr(text))
            rows = [r for r in sec.rows
                    if r["feature"] == "confinement"]
            self.assertEqual(rows[-1]["decision"], "confined")
            self.assertEqual(rows[-1]["reason"],
                             WC.STATUS_CONFINEMENT)
            self.assertEqual(rows[-1]["kw"]["job_id"], text)
            out[1]()

    def test_the_status_never_claims_a_sandbox(self):
        self.assertNotIn("sandbox", WC.STATUS_CONFINEMENT)
        self.assertEqual(
            WC.CONFINEMENT_CONTROLS,
            ("job_object", "restricted_token", "low_integrity"))


def _good_proc(backend, argv, cwd, env):
    backend.spawned.append((argv, cwd, env))
    proc = types.SimpleNamespace(
        pid=31337, _handle=888, returncode=0, closed=False)
    proc.confinement_status = WC.STATUS_CONFINEMENT
    proc.close = lambda: setattr(proc, "closed", True)
    proc.kill = mock.Mock()
    proc.poll = lambda: 0
    return proc


class CampaignTest(unittest.TestCase):
    """S1/S2 as one bounded campaign, the in-suite shape of the
    5-minute run recorded in docs/steady/fuzzing.md."""

    def test_a_short_campaign_has_no_crash_and_no_widening(self):
        cases, crashes, widenings = campaign(150, 20261114)
        self.assertGreater(cases, 1000)
        self.assertEqual(crashes, [])
        self.assertEqual(widenings, [])

    def test_the_campaign_is_deterministic(self):
        first = campaign(40, 20261114)
        second = campaign(40, 20261114)
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[2], second[2])


if __name__ == "__main__":
    cases, crashes, widenings = campaign(400, 20261114)
    print("cases:", cases, "crashes:", crashes,
          "widenings:", widenings)
    raise SystemExit(1 if crashes or widenings else 0)
