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
"""
import os
import subprocess
import sys
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "mutation-seeded.yml")
CONFTEST = os.path.join(ROOT, "tests", "conftest.py")


def _workflow_text():
    with open(WORKFLOW, encoding="utf-8") as f:
        return f.read()


def _workflow():
    # PyYAML reads the bare `on:` key as boolean True (YAML 1.1).
    doc = yaml.safe_load(_workflow_text())
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


class SeededWorkflowShapeTests(unittest.TestCase):
    def test_triggers_are_schedule_and_dispatch_only(self):
        on = _workflow()["on"]
        self.assertIn("schedule", on)
        self.assertIn("workflow_dispatch", on)
        self.assertNotIn("push", on)
        self.assertNotIn("pull_request", on)

    def test_schedule_has_a_cron_entry(self):
        schedule = _workflow()["on"]["schedule"]
        self.assertTrue(any("cron" in entry for entry in schedule))

    def test_dispatch_takes_an_optional_seed_for_reproduction(self):
        seed = _workflow()["on"]["workflow_dispatch"]["inputs"]["seed"]
        self.assertFalse(seed["required"])

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
        doc = _workflow()
        steps = doc["jobs"]["mutation-seeded"]["steps"]
        runs = [s.get("run", "") for s in steps]
        self.assertTrue(any("mutmut" in r and "hypothesis" in r for r in runs))

    def test_permissions_are_read_only(self):
        self.assertEqual(_workflow()["permissions"], {"contents": "read"})

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
