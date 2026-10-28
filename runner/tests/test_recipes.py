# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Named recipes (PROTOCOL 3.3): the owner's script, the job's checked args.

A recipe is a script the owner writes in config, with the arguments a
job may pass held to a pattern. A `kind: "recipe"` job names one and
runs it as the exec job it stands for. It may add files and outputs
and may not bring a script, a script_url, an interpreter or an
environment. A key policy's `allowed_recipes` narrows which recipes a
key may name, so `allowed_kinds: ["recipe"]` with one recipe listed
is "this key runs the tests and nothing else".
"""
import os
import shutil
import sys
import unittest
import uuid

from runner import runner as R  # noqa: E402
from runner.ops import recipes as RC  # noqa: E402
from runner.wire import verify as V  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: no re-collection)

PY = [sys.executable]
RECIPES = {
    "echo": {"script": "import sys; print('args=' + ','.join(sys.argv[1:]))",
             "interpreter": PY, "args_pattern": "[a-z0-9_.-]{1,20}", "max_args": 3},
    "bare": {"script": "print('no args')", "interpreter": PY},
    "slow": {"script": "import time; time.sleep(30)", "interpreter": PY,
             "max_timeout_sec": 1},
}


def _rejected(msg):
    return R.JobRejected(msg)


class ExpandTest(unittest.TestCase):
    cfg = {"recipes": RECIPES}

    def expand(self, **job):
        job.setdefault("kind", "recipe")
        return RC.expand(self.cfg, job, _rejected)

    def test_the_recipe_becomes_the_exec_job_it_stands_for(self):
        out = self.expand(recipe="echo", args=["a", "b"], job_id="j",
                          outputs=["r.txt"])
        self.assertEqual(out["kind"], "exec")
        self.assertEqual(out["script"], RECIPES["echo"]["script"])
        self.assertEqual(out["interpreter"], PY)
        self.assertEqual(out["args"], ["a", "b"])
        self.assertEqual(out["outputs"], ["r.txt"])
        self.assertNotIn("recipe", out)

    def test_args_are_held_to_the_pattern_and_the_count(self):
        for args in (["A"], ["a;rm"], ["a", "b", "c", "d"], ["x" * 21], ["a\x00"], [7]):
            with self.subTest(args=args), self.assertRaises(R.JobRejected):
                self.expand(recipe="echo", args=args)

    def test_no_pattern_no_args(self):
        self.assertEqual(self.expand(recipe="bare")["args"], [])
        with self.assertRaises(R.JobRejected):
            self.expand(recipe="bare", args=["x"])

    def test_what_the_recipe_stands_in_for_is_refused(self):
        for member, value in (("script", "id"), ("script_url", "https://x/y"),
                              ("interpreter", ["sh"]), ("env", {"A": "1"}),
                              ("script_sha384", "0" * 96)):
            with self.subTest(member=member), self.assertRaises(R.JobRejected) as cm:
                self.expand(recipe="echo", **{member: value})
            self.assertIn(member, str(cm.exception))

    def test_an_unknown_or_malformed_name_is_refused(self):
        for name in ("nope", "", "../x", 7, None):
            with self.subTest(name=name), self.assertRaises(R.JobRejected):
                self.expand(recipe=name)
        with self.assertRaises(R.JobRejected):
            RC.expand({}, {"kind": "recipe", "recipe": "echo"}, _rejected)

    def test_the_owners_timeout_caps_the_jobs(self):
        self.assertEqual(self.expand(recipe="slow", timeout_sec=600)["timeout_sec"], 1)
        self.assertEqual(self.expand(recipe="slow")["timeout_sec"], 1)
        with self.assertRaises(R.JobRejected):
            self.expand(recipe="slow", timeout_sec="soon")


class ValidateTest(unittest.TestCase):
    def test_good_recipes_and_none_pass(self):
        self.assertIsNone(RC.validate_recipes({"recipes": RECIPES}))
        self.assertIsNone(RC.validate_recipes({}))

    def test_each_malformed_recipe_is_a_config_error(self):
        for recipes in ([1], {"bad name": {"script": "x"}}, {"a": "x"},
                        {"a": {"script": ""}}, {"a": {"script": 7}},
                        {"a": {"script": "x", "interpreter": "sh"}},
                        {"a": {"script": "x", "interpreter": []}},
                        {"a": {"script": "x", "args_pattern": "("}},
                        {"a": {"script": "x", "args_pattern": 7}},
                        {"a": {"script": "x", "args_pattern": "(a+)+"}},
                        {"a": {"script": "x", "max_args": -1}},
                        {"a": {"script": "x", "max_args": True}},
                        {"a": {"script": "x", "max_timeout_sec": 0}},
                        {"a": {"script": "x", "max_timeout_sec": 4000}}):
            with self.subTest(recipes=recipes):
                self.assertIsNotNone(RC.validate_recipes({"recipes": recipes}))

    def test_startup_refuses_a_bad_recipe(self):
        self.assertIn("recipes", R._validate_size_caps({"recipes": {"a": {}}}))


class KeyPolicyTest(unittest.TestCase):
    def check(self, pol, job):
        policies = V.build_key_policies({"key_policies": {"ci": pol}})
        return V.check_key_policy(policies, "ci", {}, job)

    def test_a_key_that_may_run_the_tests_and_nothing_else(self):
        pol = {"allowed_kinds": ["recipe"], "allowed_recipes": ["echo"],
               "allowed_interpreters": [["sh"]]}
        self.assertIsNone(self.check(pol, {"kind": "recipe", "recipe": "echo"}))
        self.assertIn("not allowed", self.check(pol, {"kind": "recipe", "recipe": "bare"}))
        self.assertIn("not allowed", self.check(pol, {"kind": "exec", "script": "id"}))

    def test_allowed_recipes_must_be_names(self):
        for bad in ([], "echo", [7]):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                V.build_key_policies({"key_policies": {"ci": {"allowed_recipes": bad}}})


class RunTest(unittest.TestCase):
    """End to end through the mail path."""

    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.h.cfg["recipes"] = RECIPES

    def tearDown(self):
        shutil.rmtree(self.h.tmp, ignore_errors=True)

    def result(self, **job):
        p = TR.job_payload(str(uuid.uuid4()), kind="recipe", **job)
        _, smtp, _ = self.h.run_cycle([TR.job_email(p)])
        return TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)

    def test_a_recipe_runs_with_its_args(self):
        r = self.result(recipe="echo", args=["one", "two"])
        self.assertEqual(r["exit_code"], 0, r.get("stderr"))
        self.assertEqual(r["stdout"].strip(), "args=one,two")
        self.assertEqual(r["kind"], "recipe")

    def test_a_refused_recipe_is_a_rejection_result(self):
        r = self.result(recipe="echo", args=["NOT;OK"])
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("args_pattern", r["stderr"])

    def test_the_owners_cap_stops_a_long_recipe(self):
        r = self.result(recipe="slow", timeout_sec=600)
        self.assertTrue(r["timed_out"])

    def test_the_sender_builds_a_recipe_job_and_refuses_what_it_cannot_bring(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        from runner.cloud import send_job as SJ

        def new(*flags):
            o, e = io.StringIO(), io.StringIO()
            argv = ["send_job.py", "new", "--secret", TR.SECRET, "--kind", "recipe"]
            with mock.patch.object(sys, "argv", argv + list(flags)), \
                    redirect_stdout(o), redirect_stderr(e):
                return SJ.main(), o.getvalue(), e.getvalue()
        rc, out, _err = new("--recipe", "echo", "--arg", "one")
        self.assertEqual(rc, 0)
        lines = out.splitlines()
        job, *_ = R._admit_object("\n".join(lines[2:]), R.build_secrets(self.h.cfg),
                                  lines[0].rsplit(" ", 1)[1])
        self.assertEqual((job["kind"], job["recipe"], job["args"]),
                         ("recipe", "echo", ["one"]))
        for flags in (["--recipe", "echo", "--interpreter", '["sh"]'],
                      ["--recipe", "echo", "--env", "A=1"], []):
            with self.subTest(flags=flags):
                self.assertEqual(new(*flags)[0], 2)

    def test_the_dry_run_names_the_recipe(self):
        self.assertIn("recipe=echo", R._describe_job(
            {"kind": "recipe", "recipe": "echo", "args": ["a"]}))


if __name__ == "__main__":
    unittest.main()
