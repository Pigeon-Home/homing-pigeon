#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Prove a started runner is ready, instead of waiting a fixed time.

This is the repository home of the Windows rig battery fix for
the startup / build-stamp / clock trio. The old driver shape
waited 30 seconds for the runner log file to exist and slept a
fixed 6 seconds: it measured the driver's guess, not readiness.
On the saturated Germany rig the runner, healthy on every
failing run, took 139.7 to 154.4 seconds to reach its starting
line (measured cold and warm, with and without a Defender
exclusion for the test root; the exclusion changed nothing).
Startup failed on the guess, build-stamp failed because its
only input is that same log, and clock failed because its first
job sat behind a runner that was not polling yet.

Readiness here is proven in 3 stages, in order:

  1. the runner log carries its "starting" line for the commit
     under test (any starting line is also reported, so a build
     stamp check can fail on its own terms);
  2. the log carries the file transport's "watching" line (the
     starting line alone is not service: the transport creates
     and starts watching the inbox 1 to 2 seconds later, and a
     first envelope fired into that gap never reaches the
     runner);
  3. a probe job submitted through the real submission path
     returns a result that meets the same attestation bar as
     every battery job.

A probe whose envelope never appears is the transport race, not
a runner verdict: it is resubmitted, at most MAX_PROBE_ATTEMPTS
times, inside the one READINESS_BUDGET_SEC budget. The budget
is the harness figure: worst measured starting line 154 s plus
worst measured first service 136 s, times about 1.4. The clock
job keeps its own CLOCK_JOB_TIMEOUT_SEC window, unmoved; the
battery starts its clock only once readiness is proven, so the
120 seconds measures job service, not cold start. Nothing is
weakened: readiness still requires the process alive and the
log present, and now additionally the commit's starting line
and an attested probe result.

The decision is pure once its inputs are named, so any driver
(PowerShell on the rig, Python elsewhere) can implement its
side of the seams and share the rule: read_log() returns the
runner log's current text ("" while it does not exist), probe()
submits one probe job and returns a ProbeOutcome, or None when
the submission's envelope never appeared. The full record
(supposition, measurements, conclusions) stands in
docs/infrastructure-documents/project/rig-readiness-probe-2026-11-22.md.

Stdlib only.
"""
import time
from dataclasses import dataclass

READINESS_BUDGET_SEC = 420
CLOCK_JOB_TIMEOUT_SEC = 120
MAX_PROBE_ATTEMPTS = 3
PROBE_RESULT_TIMEOUT_SEC = 240

WATCHING_MARKER = "file transport: watching"


@dataclass(frozen=True)
class ProbeOutcome:
    """One probe job's round trip, as the submitter observed it."""

    arrived: bool
    attested: bool
    latency_sec: float


@dataclass(frozen=True)
class ReadinessResult:
    """The readiness verdict and the measurements behind it."""

    ready: bool
    starting_line: str
    seen_starting_line: str
    watching: bool
    probe_attempts: int
    ready_in_sec: float
    probe_sec: float


def _scan(log_text, commit):
    """(starting_line, seen_starting_line, watching) from log text."""
    seen = ""
    starting = ""
    for line in (log_text or "").splitlines():
        if not seen and "starting" in line:
            seen = line
            if ("build %s" % commit) in line:
                starting = line
    return starting, seen, (WATCHING_MARKER in (log_text or ""))


def wait_for_readiness(read_log, commit, probe, *,
                       budget_sec=READINESS_BUDGET_SEC,
                       alive=None, now=time.monotonic,
                       sleep=time.sleep, poll_interval_sec=0.5):
    """Wait until the runner proves it can service a job.

    read_log: callable returning the runner log's text (""
    while the file does not exist). probe: callable returning a
    ProbeOutcome, or None when the probe's envelope never
    appeared. alive: optional callable returning False once the
    started process has exited; an exited process fails
    readiness at once rather than burning the budget.
    """
    start = now()
    deadline = start + budget_sec
    starting = ""
    seen = ""
    watching = False
    attempts = 0
    probe_sec = -1.0
    ready = False

    def dead():
        return alive is not None and not alive()

    while now() < deadline:
        if dead():
            break
        text = read_log() or ""
        found, seen_found, watching_found = _scan(text, commit)
        if found:
            starting = found
        if seen_found:
            seen = seen_found
        if watching_found:
            watching = True
        if starting and watching:
            while attempts < MAX_PROBE_ATTEMPTS and now() < deadline:
                if dead():
                    break
                attempts += 1
                outcome = probe()
                if outcome is None:
                    continue
                if dead():
                    break
                if outcome.arrived and outcome.attested:
                    probe_sec = outcome.latency_sec
                    ready = True
                    break
            break
        sleep(poll_interval_sec)
    return ReadinessResult(
        ready=ready, starting_line=starting, seen_starting_line=seen,
        watching=watching, probe_attempts=attempts,
        ready_in_sec=round(now() - start, 1), probe_sec=probe_sec)


__all__ = ["READINESS_BUDGET_SEC", "CLOCK_JOB_TIMEOUT_SEC",
           "MAX_PROBE_ATTEMPTS", "PROBE_RESULT_TIMEOUT_SEC",
           "WATCHING_MARKER", "ProbeOutcome", "ReadinessResult",
           "wait_for_readiness"]
