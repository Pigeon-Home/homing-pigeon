"""The cut gate's rule (runner/tools/cut_gate.py): the legs
always, the Linux and Windows suites when the release carries core
code since the previous published release, the legs alone while the
relief window's marker stands; a record that cannot be read refuses.
One rule for the cut, the promotion check and the train."""
import contextlib
import datetime
import importlib.util
import io
import os
import tempfile
import unittest
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_spec = importlib.util.spec_from_file_location(
    "cut_gate",
    os.path.join(REPO, "runner", "tools", "cut_gate.py"))
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)

SHA = "ea071cb16745" + "0" * 28
LEGS = set(rg.LEGS)
BOTH = LEGS | set(rg.SUITES)


def _api(releases=None, files=None, truncated=False):
    def api(path):
        if path.startswith("/releases"):
            return releases
        if path.startswith("/compare/"):
            if files is None:
                return None
            fs = [{"filename": f, "patch": None} for f in files]
            if truncated:
                fs = fs * (300 // max(1, len(fs)) + 1)
            return {"files": fs}
        raise AssertionError(path)
    return api


def _releases(*tags):
    # the listing's order is by tag name as text; published_at
    # descends with the position here so the first is the newest
    return [{"tag_name": t, "draft": False, "published_at": "2026-11-12T%02d:00:00Z" % (23 - i)}
            for i, t in enumerate(tags)]


class RuleTest(unittest.TestCase):
    def test_what_is_code(self):
        core = frozenset({"runner/ops/exec.py", "runner/tools/ci_scope.py", "runner/_version.py", "runner/__init__.py"})
        self.assertTrue(rg.is_code("runner/ops/exec.py", core))
        self.assertTrue(rg.is_code("runner/tools/ci_scope.py", core))
        self.assertFalse(rg.is_code("runner/tools/release_train.py", core), "a tool outside the core")
        self.assertFalse(rg.is_code("runner/tests/test_exec.py", core))
        self.assertFalse(rg.is_code("runner/_version.py", core), "the carrier every release moves")
        self.assertFalse(rg.is_code("runner/__init__.py", core))
        self.assertFalse(rg.is_code("runner/ops/core.py", core | {"runner/ops/core.py"}),
                         "the measure every release re-records")
        # install.py is a carrier and code: its version line counts
        # for nothing, any other line counts, no patch counts
        inst = core | {"runner/ops/install.py"}
        self.assertFalse(rg.is_code("runner/ops/install.py", inst,
                                    '@@ -1 +1 @@\n-__version__ = "3.16.24.10"\n+__version__ = "3.16.24.11"\n'))
        self.assertTrue(rg.is_code("runner/ops/install.py", inst,
                                   '@@ -1 +1 @@\n-__version__ = "3.16.24.10"\n+__version__ = "3.16.24.11"\n+    return path\n'))
        self.assertTrue(rg.is_code("runner/ops/install.py", inst, None))
        self.assertFalse(rg.carries_runner_code(["runner/ops/install.py"], inst,
                                                {"runner/ops/install.py": '-__version__ = "1"\n+__version__ = "2"\n'}))
        self.assertFalse(rg.is_code("docs/steady/overview.md", core))
        self.assertFalse(rg.is_code("pyproject.toml", core))
        # no core list to read: everything under runner/ but the tests
        self.assertTrue(rg.is_code("runner/tools/release_train.py", None))
        self.assertFalse(rg.is_code("runner/tests/test_exec.py", None))
        self.assertTrue(rg.carries_runner_code(["docs/a.md", "runner/ops/exec.py"], core))
        self.assertFalse(rg.carries_runner_code(["docs/a.md", "runner/tests/t.py"], core))

    def test_the_core_list_is_read_from_the_tree(self):
        core = rg.core_files(REPO)
        self.assertIsNotNone(core)
        self.assertIn("runner/runner.py", core)
        self.assertIn("runner/ops/exec.py", core)
        self.assertNotIn("runner/tools/run_tests_parallel.py", core)
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(rg.core_files(d))

    def test_the_relief_marker_holds_until_its_instant(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".github", "workflows"))
            path = os.path.join(d, ".github", "workflows", "build.yml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# RELIEF-48H expires 2026-11-14T03:45Z: for the window\n")
            before = datetime.datetime(2026, 11, 14, 3, 44, tzinfo=datetime.timezone.utc)
            after = datetime.datetime(2026, 11, 14, 3, 46, tzinfo=datetime.timezone.utc)
            self.assertTrue(rg.relief_active(d, now=before))
            self.assertFalse(rg.relief_active(d, now=after))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("jobs:\n  test:\n")
            self.assertTrue(not rg.relief_active(d, now=before))
            self.assertFalse(rg.relief_active(os.path.join(d, "missing")))


class NeedTest(unittest.TestCase):
    def _need(self, api, relief=False, root=None):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "runner", "ops"))
            with open(os.path.join(d, "runner", "ops", "core.py"), "w", encoding="utf-8") as fh:
                fh.write('CORE_FILES = (\n    "runner/runner.py",\n    "runner/ops/exec.py",\n    "runner/_version.py",\n)\n')
            return rg.need(SHA, "3.16.24.11", api=api, relief=relief, root=root or d)

    def test_the_window_is_the_legs_alone_whatever_the_release_carries(self):
        need, why = self._need(_api(_releases("v3.16.24.10"), ["runner/ops/exec.py"]), relief=True)
        self.assertEqual(need, LEGS)
        self.assertIn("relief window", why)

    def test_core_code_since_the_previous_release_brings_the_suites(self):
        need, why = self._need(_api(_releases("v3.16.24.11", "v3.16.24.10", "v3.16.24.9"),
                                    ["docs/a.md", "runner/ops/exec.py", "runner/_version.py"]))
        self.assertEqual(need, BOTH)
        self.assertIn("runner code since v3.16.24.10 (runner/ops/exec.py)", why)

    def test_docs_tests_and_tools_outside_the_core_keep_the_short_path(self):
        need, why = self._need(_api(_releases("v3.16.24.10"),
                                    ["docs/a.md", "runner/tests/test_x.py", "runner/tools/release_train.py",
                                     "runner/_version.py", "pyproject.toml", ".github/workflows/build.yml"]))
        self.assertEqual(need, LEGS)
        self.assertIn("no runner code since v3.16.24.10", why)

    def test_a_record_that_cannot_be_read_refuses_into_the_suites(self):
        need, why = self._need(_api(None, ["docs/a.md"]))
        self.assertEqual(need, BOTH)
        self.assertIn("no previous release", why)
        need, why = self._need(_api(_releases("v3.16.24.10"), None))
        self.assertEqual(need, BOTH)
        self.assertIn("cannot be read whole", why)
        need, why = self._need(_api(_releases("v3.16.24.10"), ["docs/a.md"], truncated=True))
        self.assertEqual(need, BOTH)
        # drafts and unpublished releases are not the previous release
        rels = [{"tag_name": "v9", "draft": True, "published_at": None}] + _releases("v3.16.24.10")
        need, why = self._need(_api(rels, ["docs/a.md"]))
        self.assertEqual(need, LEGS)
        self.assertIn("v3.16.24.10", why)
        # the newest by published_at, not the first row: the listing
        # sorts tag names as text, v3.16.24.9 before v3.16.24.11
        rels = _releases("v3.16.24.9", "v3.16.24.8") + [
            {"tag_name": "v3.16.24.10", "draft": False, "published_at": "2026-11-12T23:30:00Z"}]
        need, why = self._need(_api(rels, ["docs/a.md"]))
        self.assertIn("since v3.16.24.10", why)


class VerdictTest(unittest.TestCase):
    def _jobs(self, **over):
        jobs = {n: {"name": n, "status": "completed", "conclusion": "success"} for n in LEGS | {"test"}}
        for part in (1, 2):
            n = "test-windows (%d)" % part
            jobs[n] = {"name": n, "status": "completed", "conclusion": "success"}
        for n, o in over.items():
            jobs[n].update(o)
        return jobs

    def test_a_matrix_job_is_every_leg_of_its_name(self):
        jobs = self._jobs()
        self.assertEqual([j["name"] for j in rg.match("test-windows", jobs)],
                         ["test-windows (1)", "test-windows (2)"])
        self.assertEqual([j["name"] for j in rg.match("build-windows", jobs)], ["build-windows"])
        self.assertEqual(rg.match("build-windows-arm64", {"build-windows": jobs["build-windows"]}), [])
        self.assertEqual(rg.verdict(BOTH, jobs), ([], [], []))

    def test_missing_bad_and_pending_are_named(self):
        jobs = self._jobs(**{"test-windows (2)": {"conclusion": "failure"},
                             "build-macos": {"status": "in_progress", "conclusion": None}})
        del jobs["build-pi-light"]
        missing, bad, pending = rg.verdict(BOTH, jobs)
        self.assertEqual(missing, ["build-pi-light"])
        self.assertEqual(bad, ["test-windows (2)=completed/failure"])
        self.assertEqual(pending, ["build-macos"])
        # the legs alone do not read the suites
        missing, bad, pending = rg.verdict(LEGS, jobs)
        self.assertEqual(bad, [])


RELEASE_DIFF = """diff --git a/runner/_version.py b/runner/_version.py
index 1..2 100644
--- a/runner/_version.py
+++ b/runner/_version.py
@@ -3 +3 @@
-__version__ = "3.16.24.18"
+__version__ = "3.16.24.19"
diff --git a/runner/ops/core.py b/runner/ops/core.py
--- a/runner/ops/core.py
+++ b/runner/ops/core.py
@@ -40 +40 @@
-AS_ASSEMBLED_ZIP_BYTES = 855207
+AS_ASSEMBLED_ZIP_BYTES = 856590
diff --git a/runner/ops/install.py b/runner/ops/install.py
--- a/runner/ops/install.py
+++ b/runner/ops/install.py
@@ -9 +9 @@
-__version__ = "3.16.24.18"
+__version__ = "3.16.24.19"
diff --git a/runner/tests/test_core.py b/runner/tests/test_core.py
--- a/runner/tests/test_core.py
+++ b/runner/tests/test_core.py
@@ -80 +80 @@
-        self.assertEqual(855207, core.AS_ASSEMBLED_ZIP_BYTES)
+        self.assertEqual(856590, core.AS_ASSEMBLED_ZIP_BYTES)
"""


class ProofsDueTest(unittest.TestCase):
    """The tag build starts the nine proofs only when something
    under runner/ changed beyond the release's own carrier lines:
    with them, every tag started the proofs and the next tag
    cancelled them."""

    def test_a_release_commits_own_lines_start_nothing(self):
        self.assertEqual(rg.runner_changes(RELEASE_DIFF), [])

    def test_any_other_line_under_runner_starts_them(self):
        more = RELEASE_DIFF + """diff --git a/runner/tests/test_parallel_runner.py b/runner/tests/test_parallel_runner.py
--- a/runner/tests/test_parallel_runner.py
+++ b/runner/tests/test_parallel_runner.py
@@ -796 +796 @@
-        self.assertIn("x", text)
+        self.assertRegex(text, r"x")
"""
        self.assertEqual(rg.runner_changes(more), ["runner/tests/test_parallel_runner.py"])
        # a second line in a carrier file counts the file
        extra = RELEASE_DIFF.replace('+__version__ = "3.16.24.19"\ndiff --git a/runner/ops/core.py',
                                     '+__version__ = "3.16.24.19"\n+BUILD = 7\ndiff --git a/runner/ops/core.py')
        self.assertEqual(rg.runner_changes(extra), ["runner/_version.py"])
        # a measure of the core's parts moving is a core change
        parts = RELEASE_DIFF + """diff --git a/runner/ops/core.py b/runner/ops/core.py
--- a/runner/ops/core.py
+++ b/runner/ops/core.py
@@ -60 +60 @@
-    "runner/ops": 22585,
+    "runner/ops": 22703,
"""
        self.assertEqual(rg.runner_changes(parts), ["runner/ops/core.py"])

    def test_files_added_deleted_or_outside_runner(self):
        added = """diff --git a/runner/tools/seat_digest.py b/runner/tools/seat_digest.py
new file mode 100644
--- /dev/null
+++ b/runner/tools/seat_digest.py
@@ -0,0 +1 @@
+__version__ = "1"
diff --git a/docs/a.md b/docs/a.md
--- a/docs/a.md
+++ b/docs/a.md
@@ -1 +1 @@
-old
+new
diff --git a/runner/tests/old.py b/runner/tests/old.py
deleted file mode 100644
"""
        self.assertEqual(rg.runner_changes(added),
                         ["runner/tools/seat_digest.py", "runner/tests/old.py"])
        self.assertEqual(rg.runner_changes(""), [])

    def test_an_unreadable_diff_is_due_and_the_command_ends_on_one_word(self):
        with tempfile.TemporaryDirectory() as d:
            due, paths = rg.proofs_due("v1", "v2", root=d)
        self.assertTrue(due)
        self.assertIn("could not be read", paths[0])
        with mock.patch.object(rg, "proofs_due", lambda prev, tag: (False, [])), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rg.main(["proofs-due", "--prev", "v1", "--tag", "v2"]), 0)
        self.assertEqual(out.getvalue().splitlines()[-1], "false")
        self.assertIn("nothing", out.getvalue())
        with mock.patch.object(rg, "proofs_due", lambda prev, tag: (True, ["runner/ops/exec.py"])), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            rg.main(["proofs-due", "--prev", "v1", "--tag", "v2"])
        self.assertEqual(out.getvalue().splitlines()[-1], "true")
        self.assertIn("runner/ops/exec.py", out.getvalue())


class CommandTest(unittest.TestCase):
    def test_need_prints_the_set_and_check_reads_the_run(self):
        jobs = {"jobs": [{"name": n, "status": "completed", "conclusion": "success"} for n in LEGS]}

        def api(path):
            if path.startswith("/actions/runs/7/jobs"):
                return jobs
            raise AssertionError(path)
        with mock.patch.object(rg, "api", api), \
                mock.patch.object(rg, "need", lambda sha, v, **k: (set(LEGS), "the relief window: the legs alone")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rg.main(["need", "--sha", SHA, "--version", "v3.16.24.11"]), 0)
            self.assertEqual(rg.main(["check", "--sha", SHA, "--version", "3.16.24.11", "--run", "7"]), 0)
        text = out.getvalue()
        self.assertIn("build-pi-light build-python", text)
        self.assertIn("cut gate: run 7: 8 job(s) green", text)
        jobs["jobs"][0]["conclusion"] = "failure"
        with mock.patch.object(rg, "api", api), \
                mock.patch.object(rg, "need", lambda sha, v, **k: (set(LEGS), "")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rg.main(["check", "--sha", SHA, "--version", "3.16.24.11", "--run", "7"]), 1)
        self.assertIn("::error title=cut gate::%s=completed/failure" % jobs["jobs"][0]["name"], out.getvalue())


if __name__ == "__main__":
    unittest.main()
