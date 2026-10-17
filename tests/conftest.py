"""pytest-only helpers.

When the suite runs under mutmut, each test executes in forked worker
processes. Hypothesis's differing_executors health check treats that as
a flaw and fails the run; under mutation testing the forking is
expected, so the check is suppressed only then (detected via the
MUTANT_UNDER_TEST env var mutmut sets). Normal runs keep every check.
"""
import os

try:
    from hypothesis import HealthCheck, settings
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    pass
else:
    if os.environ.get("MUTANT_UNDER_TEST"):
        settings.register_profile(
            "mutation",
            suppress_health_check=[HealthCheck.differing_executors],
        )
        settings.load_profile("mutation")
