# Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c
"""Stand-ins for hypothesis on a box that cannot install it.

hypothesis is a test-only dependency (CI installs it from
.github/requirements-ci.txt). A box without it (an air-gapped bench,
a rig with no PyPI) still has to run the rest of the suite: a module
that builds its strategies at import would otherwise fail to load
and take its deterministic tests down with its property tests.

    try:
        from hypothesis import given, settings, strategies as st
    except ImportError:  # test-only dep: runner/tests/_hypothesis_shim.py
        from runner.tests._hypothesis_shim import given, settings, strategies as st

With the shim, every strategy expression evaluates to an inert
placeholder, ``@settings`` is a no-op, and ``@given`` turns its test
into a skip whose reason is ``SKIP_REASON``. Every test without
``@given`` runs as before. A leg that installs hypothesis forbids that
reason (``runner/tools/skip_guard.py --forbid``), so the shim never
lets a property test go missing where it must run.
"""
import functools
import unittest

SKIP_REASON = "hypothesis not installed"


class _Inert:
    """Any strategy, combinator or decorator built from ``st``."""

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and not kwargs and callable(args[0]) \
                and not isinstance(args[0], _Inert):
            return self  # st.composite and friends used as a decorator
        return self

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return self

    def __or__(self, other):
        return self

    __ror__ = __or__

    def __iter__(self):
        return iter(())

    def __repr__(self):
        return "<hypothesis shim strategy>"


strategies = _Inert()


def given(*_args, **_kwargs):
    def wrap(fn):
        @functools.wraps(fn)
        def skipped(*a, **k):
            raise unittest.SkipTest(SKIP_REASON)
        skipped.__unittest_skip__ = True
        skipped.__unittest_skip_why__ = SKIP_REASON
        return skipped
    return wrap


def settings(*_args, **_kwargs):
    def wrap(fn):
        return fn
    return wrap


def assume(condition):
    return True


def example(*_args, **_kwargs):
    return settings()


class HealthCheck:
    too_slow = filter_too_much = data_too_large = function_scoped_fixture = None
    large_base_example = differing_executors = None
