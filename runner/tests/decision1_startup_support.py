#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Shared fixtures for the Decision 1 startup family.

Split from runner/tests/test_decision1_startup.py in the
Q136 follow-on file split (2026-11-11): the original file's
97 tests burned past the Windows shard wall alone, so the
family now lives in eight sibling test files that share the
fixtures this module carries -- the base config whose
platform gates are stated off (an unstated audience reads
enforce and would mask the field each test is about), the
strong secret, the two scripted Windows backends, and
run_main, one real startup through main(). This module
holds no tests of its own; the pattern is the one
runner/tests already uses for shared fixtures
(security_parity, defaults_registry).
"""
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as RR  # noqa: E402
from runner.guard import defaulted  # noqa: E402
from runner.guard import sandbox as _sandbox  # noqa: E402
from runner.ops import remediation_ops as REM  # noqa: E402


def _backend_cannot_engage():
    """A real-marked Windows backend whose probe cannot engage,
    scripted so the job_user refusal answers identically on any
    host (a live backend on a real Windows host may engage)."""
    backend = mock.Mock()
    backend.IS_WINDOWS_BACKEND = True
    backend.windows_startup_problem.return_value = (
        "backend cannot engage (scripted)")
    return backend


def _backend_stub():
    """The off-Windows stub backend: never consulted by the
    gates, which answer the long-standing refusal for it."""
    backend = mock.Mock()
    backend.IS_WINDOWS_BACKEND = False
    backend.windows_startup_problem.return_value = (
        "windows_confine is Windows-only")
    return backend


def _confinement_backend(kind, problem):
    """A real-marked confinement backend for one platform,
    in the platform test files' established shape: a plain
    namespace (never a Mock, which would invent any probe a
    gate goes looking for) whose startup and confinement
    probes both answer `problem` -- a string for a backend
    that cannot engage, None for one that can."""
    backend = types.SimpleNamespace()

    def _probe(cfg=None, timeout=15):
        return problem

    if kind == "windows":
        backend.IS_WINDOWS_BACKEND = True
        backend.windows_startup_problem = _probe
        backend.windows_confinement_problem = _probe
    elif kind == "darwin":
        backend.IS_MACOS_BACKEND = True
        backend.macos_startup_problem = _probe
        backend.macos_confinement_problem = _probe
    elif kind == "freebsd":
        backend.IS_FREEBSD_BACKEND = True
        backend.freebsd_startup_problem = _probe
        backend.freebsd_confinement_problem = _probe
    else:
        raise ValueError("unknown confinement backend kind %r"
                         % (kind,))
    return backend


@contextlib.contextmanager
def scripted_confinement(problem):
    """Every confinement seam answers `problem` at once.

    The startup gate in ops/main.py routes by the host's
    platform -- the Windows, FreeBSD and macOS branches ask
    their platform backend's probe, and only the Linux
    branch asks the bwrap seam -- so a dead backend scripted
    on one seam alone is never consulted on the other
    platforms' hosts and the startup it was meant to refuse
    proceeds (Q159: the gates_strict dead-backend test
    scripted only the bwrap seam and started cleanly, exit
    0, on real Windows and macOS). Scripting every seam
    makes the construction hold on any host: whichever
    branch the host's platform takes, the backend it asks
    is the scripted one. `problem` is the probe answer: a
    string scripts a dead backend, None a live one.
    """
    with mock.patch.object(
            REM, "_windows_confine",
            lambda backend=None: _confinement_backend(
                "windows", problem)), \
            mock.patch.object(
                REM, "_macos_confine",
                lambda backend=None: _confinement_backend(
                    "darwin", problem)), \
            mock.patch.object(
                REM, "_freebsd_confine",
                lambda backend=None: _confinement_backend(
                    "freebsd", problem)), \
            mock.patch.object(
                RR._sandbox, "startup_problem",
                lambda *a, **k: problem):
        yield
from runner.guard.security import FEATURES  # noqa: E402
from runner.oracle.dri import parse_dri  # noqa: E402
from runner.oracle.resources import parse_resources  # noqa: E402


STRONG_SECRET = ("9f86d081884c7d659a2feaa0c55ad015"
                 "a3bf4f1b2b0b822cd15d6c15b0f00a08")
# The platform gates are stated off in the base config: under
# the lockdown default confinement and job_user read enforce and
# refuse first on a host that cannot enforce them, which would
# mask the field each test is about. A test whose extra carries
# its own security block replaces this one wholesale. The base
# config also carries a runner_id, as every config the installer
# or the setup wizard writes does: since phase 2 of the
# default-posture work, audience at enforce (its unset reading)
# with no runner_id refuses startup, which would mask the field
# each test is about in the same way.
BASE = {"mailbox_user": "a@b.c", "mailbox_password": "p",
        "shared_secret": STRONG_SECRET,
        "runner_id": "decision1-test-runner",
        "security": {"modes": {"confinement": "off",
                               "job_user": "off"}}}



def run_main(extra, argv_extra=(), platform=None, sandbox_problem=None):
    """One real startup through main(). Returns (rc, stdout, stderr).

    The config lives in a fresh temp dir whose path is also the
    runner's base_dir, so a startup that proceeds cannot touch
    real state; --audit-report (used by the default-class tests)
    returns before any mailbox work.

    platform patches sys.platform for the duration (the suite's
    win32 simulation seam); sandbox_problem scripts the sandbox
    module's startup_problem answer, so a backend failure can be
    constructed on a host whose sandbox works.
    """
    tmpdir = tempfile.mkdtemp(prefix="hp-d1-")
    cfg = dict(BASE, base_dir=tmpdir)
    cfg.update(extra)
    cfg_path = os.path.join(tmpdir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    out, err = io.StringIO(), io.StringIO()
    argv = ["runner", "--config", cfg_path, *argv_extra]
    with contextlib.ExitStack() as stack:
        if platform is not None:
            stack.enter_context(
                mock.patch.object(sys, "platform", platform))
        if sandbox_problem is not None:
            stack.enter_context(mock.patch.object(
                RR._sandbox, "startup_problem",
                lambda *a, **k: sandbox_problem))
        stack.enter_context(mock.patch.object(sys, "argv", argv))
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = RR.main()
    return rc, out.getvalue(), err.getvalue()

