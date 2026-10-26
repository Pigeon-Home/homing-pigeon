"""pytest-only helpers.

When the suite runs under mutmut, each test executes in forked worker
processes. Hypothesis's differing_executors health check treats that as
a flaw and fails the run; under mutation testing the forking is
expected, so the check is suppressed only then (detected via the
MUTANT_UNDER_TEST env var mutmut sets). Normal runs keep every check.
"""
import os
import subprocess

# mutmut's stats pass sets MUTANT_UNDER_TEST=stats, and every call
# through a trampoline then records a hit by way of mutmut's own
# config(), which reads pyproject.toml from the current directory.
# The suite's subprocesses (a runner started under a temp dir, a tool
# run from a scratch tree) inherit the variable, import the mutated
# module, hit a trampoline, and die in mutmut's config loader
# ("Could not figure out where the code to mutate is"): the test
# fails and the stats pass exits 1 (the v3.12.67 and v3.12.68 tag
# runs, 2026-10-25). A child cannot report hits to the parent anyway,
# so for the stats pass alone the children run without the variable
# and take the trampoline's plain path. Mutant runs are untouched: a
# child under a mutant must see the mutant, and that branch never
# touches the config.
if os.environ.get("MUTANT_UNDER_TEST") == "stats":
    _real_popen_init = subprocess.Popen.__init__

    def _popen_without_stats(self, *args, **kwargs):
        env = kwargs.get("env")
        env = dict(os.environ if env is None else env)
        env.pop("MUTANT_UNDER_TEST", None)
        kwargs["env"] = env
        return _real_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _popen_without_stats

try:
    from hypothesis import HealthCheck, settings
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    pass
else:
    # Project Platinum (campaign-standing-orders.md, queue P):
    # HP_PLATINUM_EXAMPLES=N widens every property test that names no
    # max_examples of its own, so an idle rig spends its cycles on
    # more examples without a test edit. Unset, nothing changes. The
    # mutation profile below still wins when both are set.
    if os.environ.get("HP_PLATINUM_EXAMPLES"):
        settings.register_profile(
            "platinum", deadline=None,
            max_examples=int(os.environ["HP_PLATINUM_EXAMPLES"]))
        settings.load_profile("platinum")
    if os.environ.get("MUTANT_UNDER_TEST"):
        settings.register_profile(
            "mutation",
            suppress_health_check=[HealthCheck.differing_executors],
        )
        settings.load_profile("mutation")

    # The seeded mutation workflow (mutation-seeded.yml) sets
    # HP_MUTATION_SEED so each scheduled run draws different
    # Hypothesis examples while staying reproducible from its
    # printed seed. The assignment is the same mechanism the pytest
    # plugin's --hypothesis-seed option uses. Unset, nothing
    # changes: normal runs and the deterministic release mutation
    # job are untouched. A malformed value fails loudly -- a seed
    # that silently did not take would make the run's log lie
    # about what it explored.
    if os.environ.get("HP_MUTATION_SEED") is not None:
        import hypothesis.core

        hypothesis.core.global_force_seed = int(os.environ["HP_MUTATION_SEED"])
