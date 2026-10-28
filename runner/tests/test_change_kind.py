# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The change kind (PROTOCOL 3.5): check out, apply, run a recipe.

A `change` job names an owner's repository (`change_repos`), a commit,
a diff and a recipe. The runner clones the repository into the job's
workdir without sharing its object files, checks out the commit,
applies the diff and runs the recipe in `src/`; the tree's diff
against the commit afterwards comes home as `change.diff`. Held here
against a real repository made for the test.
"""
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

from runner import runner as R  # noqa: E402
from runner.ops import changes as CH  # noqa: E402
from runner.wire import verify as V  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: no re-collection)

HAVE_GIT = shutil.which("git") is not None
PY = [sys.executable]
RECIPES = {
    "show": {"script": "print(open('app.txt').read().strip())", "interpreter": PY},
    "edit": {"script": "open('new.txt','w').write('made by the run\\n')",
             "interpreter": PY},
    "fail": {"script": "import sys; sys.exit(3)", "interpreter": PY},
}


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x",
                           "-c", "commit.gpgsign=false"] + list(args),
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def b64(data):
    return base64.b64encode(data).decode("ascii")


DIFF = (b"--- a/app.txt\n+++ b/app.txt\n@@ -1 +1 @@\n-one\n+two\n")


@unittest.skipUnless(HAVE_GIT, "git is not on PATH")
class ChangeRunTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="hp-change-repo-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        _git(self.repo, "init", "-q")
        with open(os.path.join(self.repo, "app.txt"), "w") as fh:
            fh.write("one\n")
        _git(self.repo, "add", "app.txt")
        _git(self.repo, "commit", "-q", "-m", "first")
        self.first = _git(self.repo, "rev-parse", "HEAD").strip()
        with open(os.path.join(self.repo, "app.txt"), "w") as fh:
            fh.write("one\n")
        with open(os.path.join(self.repo, "other.txt"), "w") as fh:
            fh.write("x\n")
        _git(self.repo, "add", "other.txt")
        _git(self.repo, "commit", "-q", "-m", "second")
        self.base = tempfile.mkdtemp(prefix="hp-change-base-")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.cfg = {"recipes": RECIPES, "change_repos": {"app": self.repo}}

    def run_change(self, **job):
        job = dict({"job_id": "c-" + uuid.uuid4().hex[:8], "kind": "change",
                    "repo": "app"}, **job)
        return R.execute_job(self.cfg, job, self.base)

    def test_the_diff_is_applied_before_the_recipe_runs(self):
        r = self.run_change(recipe="show", diff_b64=b64(DIFF))
        self.assertEqual(r["exit_code"], 0, r["stderr"])
        self.assertEqual(r["stdout"].strip(), "two")
        self.assertEqual(r["change"]["repo"], "app")
        diff = [o for o in r["outputs"] if o["name"] == "change.diff"][0]
        self.assertIn(b"+two", base64.b64decode(diff["content_b64"]))

    def test_the_commit_is_checked_out_and_the_run_s_own_changes_come_home(self):
        r = self.run_change(recipe="edit", commit=self.first, outputs=["new.txt"])
        self.assertEqual(r["exit_code"], 0, r["stderr"])
        self.assertEqual(r["change"]["commit"], self.first)
        names = [o["name"] for o in r["outputs"]]
        self.assertEqual(names, ["src/new.txt", "change.diff"])
        diff = base64.b64decode(r["outputs"][1]["content_b64"])
        self.assertIn(b"made by the run", diff)
        self.assertNotIn(b"other.txt", diff)   # the first commit has no other.txt

    def test_the_recipe_s_exit_code_is_the_result_s(self):
        self.assertEqual(self.run_change(recipe="fail")["exit_code"], 3)

    def test_what_cannot_be_staged_is_a_rejection(self):
        bad = b"--- a/nope.txt\n+++ b/nope.txt\n@@ -1 +1 @@\n-a\n+b\n"
        for job, why in (({"recipe": "show", "diff_b64": b64(bad)}, "does not apply"),
                         ({"recipe": "show", "commit": "f" * 40}, "not in the change"),
                         ({"recipe": "show", "repo": "elsewhere"}, "no change repository"),
                         ({"recipe": "nope"}, "no recipe")):
            with self.subTest(why=why), self.assertRaises(R.JobRejected) as cm:
                self.run_change(**job)
            self.assertIn(why, str(cm.exception))

    def test_the_owner_s_repository_is_not_touched(self):
        before = _git(self.repo, "status", "--porcelain")
        self.run_change(recipe="edit", diff_b64=b64(DIFF))
        self.assertEqual(_git(self.repo, "status", "--porcelain"), before)
        with open(os.path.join(self.repo, "app.txt")) as fh:
            self.assertEqual(fh.read(), "one\n")

    def test_end_to_end_the_result_names_the_commit(self):
        h = TR.RunnerTest("test_ping_roundtrip")
        h.setUp()
        self.addCleanup(shutil.rmtree, h.tmp, True)
        h.cfg.update(self.cfg)
        p = TR.job_payload(str(uuid.uuid4()), kind="change", repo="app",
                           recipe="show", diff_b64=b64(DIFF))
        _, smtp, _ = h.run_cycle([TR.job_email(p)])
        r = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertEqual((r["kind"], r["exit_code"]), ("change", 0), r.get("stderr"))
        self.assertEqual(len(r["change"]["commit"]), 40)


class PrepareTest(unittest.TestCase):
    cfg = {"recipes": RECIPES, "change_repos": {"app": "/srv/app"}}

    def prepare(self, **job):
        job = dict({"kind": "change", "repo": "app", "recipe": "show"}, **job)
        return CH.prepare(self.cfg, job, R.JobRejected, R._recipes.expand)

    def test_the_job_becomes_the_recipe_s_exec_job(self):
        out, spec = self.prepare(diff_b64=b64(DIFF), commit="main", outputs=["r.xml"])
        self.assertEqual(out["kind"], "exec")
        self.assertEqual(out["outputs"], ["src/r.xml", "change.diff"])
        self.assertEqual(spec, {"repo": "app", "path": "/srv/app", "commit": "main",
                                "diff": DIFF})
        for member in ("repo", "commit", "diff_b64"):
            self.assertNotIn(member, out)

    def test_refusals(self):
        for job in ({"commit": "-x"}, {"commit": "a..b"}, {"commit": 7},
                    {"diff_b64": "not base64!"}, {"diff_b64": 7},
                    {"script": "id"}, {"interpreter": ["sh"]}, {"env": {"A": "1"}},
                    {"outputs": ["change.diff"]}, {"outputs": "x"}, {"outputs": [7]},
                    {"repo": 7}):
            with self.subTest(job=job), self.assertRaises(R.JobRejected):
                self.prepare(**job)

    def test_an_oversized_diff_is_refused(self):
        with mock_max(10), self.assertRaises(R.JobRejected):
            self.prepare(diff_b64=b64(b"x" * 11))

    def test_repos_are_validated_at_startup(self):
        self.assertIsNone(CH.validate_repos({}))
        self.assertIsNone(CH.validate_repos({"change_repos": {"a": "/srv/a"}}))
        for bad in ([1], {"bad name": "/x"}, {"a": "relative"}, {"a": 7}):
            with self.subTest(bad=bad):
                self.assertIsNotNone(CH.validate_repos({"change_repos": bad}))
        self.assertIn("change_repos", R._validate_size_caps({"change_repos": [1]}))

    def test_a_key_policy_names_the_recipe_a_change_runs(self):
        pol = V.build_key_policies({"key_policies": {"ci": {
            "allowed_kinds": ["change"], "allowed_recipes": ["show"],
            "allowed_interpreters": [["sh"]]}}})
        self.assertIsNone(V.check_key_policy(
            pol, "ci", {}, {"kind": "change", "recipe": "show"}))
        self.assertIn("not allowed", V.check_key_policy(
            pol, "ci", {}, {"kind": "change", "recipe": "edit"}))


class mock_max:
    def __init__(self, n):
        self.n = n

    def __enter__(self):
        self.old = CH.MAX_DIFF_BYTES
        CH.MAX_DIFF_BYTES = self.n

    def __exit__(self, *exc):
        CH.MAX_DIFF_BYTES = self.old


class SenderTest(unittest.TestCase):
    def test_the_sender_builds_a_change_and_needs_a_repo(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        from runner.cloud import send_job as SJ
        d = tempfile.mkdtemp(prefix="hp-change-send-")
        self.addCleanup(shutil.rmtree, d, True)
        patch = os.path.join(d, "p.diff")
        with open(patch, "wb") as fh:
            fh.write(DIFF)

        def new(*flags):
            o = io.StringIO()
            argv = ["send_job.py", "new", "--secret", TR.SECRET, "--kind", "change"]
            with mock.patch.object(sys, "argv", argv + list(flags)), \
                    redirect_stdout(o), redirect_stderr(io.StringIO()):
                return SJ.main(), o.getvalue()
        rc, out = new("--repo", "app", "--diff-file", patch, "--recipe", "show")
        self.assertEqual(rc, 0)
        lines = out.splitlines()
        job, *_ = R._admit_object("\n".join(lines[2:]),
                                  R.build_secrets({"shared_secret": TR.SECRET}),
                                  lines[0].rsplit(" ", 1)[1])
        self.assertEqual(base64.b64decode(job["diff_b64"]), DIFF)
        self.assertEqual(new("--recipe", "show")[0], 2)
        self.assertEqual(new("--repo", "app")[0], 2)


class NoGitTest(unittest.TestCase):
    def test_no_git_is_a_rejection(self):
        from unittest import mock
        with mock.patch.object(CH.shutil, "which", return_value=None), \
                self.assertRaises(R.JobRejected) as cm:
            CH.stage("/nowhere", {"path": "/x", "commit": None, "diff": b""},
                     R.JobRejected)
        self.assertIn("git is not", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
