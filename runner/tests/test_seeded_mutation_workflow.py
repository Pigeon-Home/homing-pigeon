"""The seeded mutation pipeline (mutation-seeded.yml).

The release mutation job in build.yml is the deterministic gate
signal: same seed surface every tag, so its results compare across
releases. The seeded twin explores: a per-run seed varies the
Hypothesis draws and the hash seed under the same mutmut scope, on a
schedule, gating nothing. These tests pin the properties that make
it safe to have both -- the seeded workflow can never fire on a tag
or a push, it reads with the least privilege, its seed is
recoverable from the run's own log, and the conftest hook that
carries the seed into Hypothesis takes effect only when the seed
variable is set (and refuses a malformed one loudly rather than
silently exploring unseeded).

The workflow is asserted as text, the same convention as
runner/tests/test_build_config.py: the CI test environment installs only
the pinned tools in .github/requirements-ci.txt, which carries no YAML
library, and a test that cannot run in CI pins nothing.
"""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "mutation-seeded.yml")
CONFTEST = os.path.join(ROOT, "runner", "tests", "conftest.py")


def _workflow_text():
    with open(WORKFLOW, encoding="utf-8") as f:
        return f.read()


def _section(text, start, end):
    """The lines from the `start` line up to (excluding) `end`."""
    lines = text.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith(start))
    j = next(n for n in range(i + 1, len(lines)) if lines[n].startswith(end))
    return lines[i:j]


def _on_block():
    return _section(_workflow_text(), "on:", "permissions:")


def _dispatch_block():
    text = _workflow_text()
    lines = text.splitlines()
    i = next(n for n, line in enumerate(lines)
             if line.startswith("  workflow_dispatch:"))
    j = next(n for n in range(i + 1, len(lines)) if lines[n].startswith("permissions:"))
    return lines[i:j]


class SeededWorkflowShapeTests(unittest.TestCase):
    def test_triggers_are_schedule_and_dispatch_only(self):
        on = _on_block()
        keys = [line.strip().rstrip(":") for line in on
                if re.match(r"^  [a-z_]+:$", line)]
        self.assertEqual(sorted(keys), ["schedule", "workflow_dispatch"])

    def test_schedule_has_a_cron_entry(self):
        self.assertTrue(any("- cron:" in line for line in _on_block()))

    def test_dispatch_takes_an_optional_seed_for_reproduction(self):
        block = _dispatch_block()
        self.assertTrue(any(line.strip() == "seed:" for line in block))
        self.assertTrue(any("required: false" in line for line in block))

    def test_seed_defaults_to_the_run_number(self):
        self.assertIn("github.run_number", _workflow_text())

    def test_seed_is_printed_where_a_reader_can_find_it(self):
        text = _workflow_text()
        self.assertIn("::notice title=mutation seed::", text)
        self.assertIn("GITHUB_STEP_SUMMARY", text)

    def test_mutmut_step_carries_the_seed_in_both_channels(self):
        text = _workflow_text()
        self.assertIn("PYTHONHASHSEED: ${{ steps.seed.outputs.seed }}", text)
        self.assertIn("HP_MUTATION_SEED: ${{ steps.seed.outputs.seed }}", text)
        self.assertIn("mutmut run", text)

    def test_same_scope_and_tools_as_the_release_job(self):
        installs = [line for line in _workflow_text().splitlines()
                    if "pip install" in line]
        self.assertTrue(any("mutmut" in line and "hypothesis" in line
                            for line in installs))

    def test_permissions_are_read_only(self):
        block = _section(_workflow_text(), "permissions:", "jobs:")
        body = [line for line in block if line.strip()]
        self.assertEqual(body, ["permissions:", "  contents: read"])

    def test_nothing_in_the_workflow_publishes_or_pushes(self):
        text = _workflow_text()
        self.assertNotIn("git push", text)
        self.assertNotIn("contents: write", text)


class ConftestSeedHookTests(unittest.TestCase):
    def _global_force_seed(self, env_extra):
        env = dict(os.environ)
        env.pop("HP_MUTATION_SEED", None)
        env.update(env_extra)
        code = (
            "import importlib.util, hypothesis.core;"
            "spec = importlib.util.spec_from_file_location("
            f"'hp_conftest', r'{CONFTEST}');"
            "m = importlib.util.module_from_spec(spec);"
            "spec.loader.exec_module(m);"
            "print(hypothesis.core.global_force_seed)"
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, env=env, cwd=ROOT,
        )

    def test_seed_variable_sets_the_hypothesis_seed(self):
        r = self._global_force_seed({"HP_MUTATION_SEED": "424242"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "424242")

    def test_unset_seed_variable_leaves_runs_untouched(self):
        r = self._global_force_seed({})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "None")

    def test_malformed_seed_fails_loudly(self):
        r = self._global_force_seed({"HP_MUTATION_SEED": "not-a-seed"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ValueError", r.stderr)


if __name__ == "__main__":
    unittest.main()
