#!/usr/bin/env python3
"""runner/tools/release_train.py: the release cycle's mechanical
steps, pinned on scratch trees and sample logs.

The tool exists because the 3.16.20.10 cycle of 2026-11-11 took
three hours of attention for steps a tool can take: the version
moves one step on its rightmost component in three carriers, the
changelog takes its entry before the newest heading, the gate's
job names are read from cut-release.yml rather than kept in a
second place, and a mirror's own words are read out of its publish
job's log."""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "release_train", os.path.join(REPO, "runner", "tools", "release_train.py"))
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)


class VersionTest(unittest.TestCase):
    def test_bump_moves_the_rightmost_component(self):
        self.assertEqual(rt.bump("3.16.20.10"), "3.16.20.11")
        self.assertEqual(rt.bump("3.16.20.9"), "3.16.20.10")
        self.assertEqual(rt.bump("3.15.18.5"), "3.15.18.6")

    def test_the_carriers_are_read_and_written_together(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "runner", "ops"))
            with open(os.path.join(d, "pyproject.toml"), "w") as fh:
                fh.write('[project]\nname = "x"\nversion = "3.16.20.10"\n')
            with open(os.path.join(d, "runner", "_version.py"), "w") as fh:
                fh.write('"""doc"""\n\n__version__ = "3.16.20.10"\n')
            with open(os.path.join(d, "runner", "ops", "install.py"), "w") as fh:
                fh.write('# frozen\n__version__ = "3.16.20.10"\n\nSERVICE = "hp"\n')
            self.assertEqual(set(rt.carriers(d).values()), {"3.16.20.10"})
            rt.write_carriers("3.16.20.11", d)
            self.assertEqual(set(rt.carriers(d).values()), {"3.16.20.11"})
            with open(os.path.join(d, "runner", "ops", "install.py")) as fh:
                self.assertIn('SERVICE = "hp"', fh.read())

    def test_the_live_carriers_agree(self):
        self.assertEqual(len(set(rt.carriers(REPO).values())), 1)


class ChangelogTest(unittest.TestCase):
    def test_the_entry_lands_before_the_newest_heading(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, rt.CHANGELOG)
            os.makedirs(os.path.dirname(path))
            with open(path, "w") as fh:
                fh.write("# Changelog\n\nIntro.\n\n## 3.16.20.10 - 2026-11-11\n\n- old\n")
            rt.write_changelog("3.16.20.11", ["Fix: a thing", " Fix: another "], "2026-11-12", d)
            with open(path) as fh:
                text = fh.read()
            self.assertIn("Intro.\n\n## 3.16.20.11 - 2026-11-12\n\n- Fix: a thing\n- Fix: another\n\n## 3.16.20.10", text)
            with self.assertRaises(RuntimeError):
                rt.write_changelog("3.16.20.11", ["again"], "2026-11-12", d)


class GateTest(unittest.TestCase):
    def test_the_gate_jobs_are_read_from_cut_release(self):
        need = rt.gate_jobs()
        self.assertIn("build-windows", need)
        self.assertIn("build-python", need)
        self.assertGreaterEqual(len(need), 8)

    def test_the_verdict_reads_the_newest_uncancelled_run(self):
        # ... of main, by a push or a dispatch: a pull_request run
        # (its tree is the head merged into the base) and a tag build
        # on the same sha are not the gate's build, however new.
        runs = {"workflow_runs": [
            {"id": 1, "conclusion": "cancelled", "event": "push", "head_branch": "main"},
            {"id": 5, "conclusion": "success", "event": "pull_request", "head_branch": "work/next"},
            {"id": 4, "conclusion": "success", "event": "workflow_dispatch", "head_branch": "v3.16.21.4"},
            {"id": 3, "conclusion": "success", "event": "push", "head_branch": "main"},
            {"id": 2, "conclusion": "failure", "event": "push", "head_branch": "main"}]}
        jobs = {"jobs": [{"name": n, "status": "completed", "conclusion": "success"}
                         for n in rt.gate_jobs()]}

        def fake_api(path, method="GET", body=None, raw=False):
            if "/runs?head_sha" in path:
                return runs
            if "/runs/3/jobs" in path:
                return jobs
            raise AssertionError(path)
        with mock.patch.object(rt, "api", fake_api):
            state, detail = rt.gate_verdict("abc")
        self.assertEqual(state, "green")
        self.assertIn("run 3", detail)

    def test_a_red_gate_job_and_a_pending_one(self):
        need = sorted(rt.gate_jobs())
        jobs = [{"name": n, "status": "completed", "conclusion": "success"} for n in need]
        jobs[0]["conclusion"] = "failure"
        jobs[1]["status"] = "in_progress"
        main_run = {"workflow_runs": [{"id": 7, "conclusion": None, "event": "push", "head_branch": "main"}]}
        with mock.patch.object(rt, "api", lambda path, **kw: main_run if "head_sha" in path else {"jobs": jobs}):
            state, detail = rt.gate_verdict("abc")
        self.assertEqual(state, "red")
        self.assertIn(need[0], detail)
        jobs[0]["conclusion"] = "success"
        with mock.patch.object(rt, "api", lambda path, **kw: main_run if "head_sha" in path else {"jobs": jobs}):
            state, detail = rt.gate_verdict("abc")
        self.assertEqual(state, "running")
        self.assertIn(need[1], detail)

    def test_no_run_is_no_verdict(self):
        with mock.patch.object(rt, "api", lambda path, **kw: {"workflow_runs": [
                {"id": 1, "conclusion": "cancelled", "event": "push", "head_branch": "main"},
                {"id": 2, "conclusion": "success", "event": "pull_request", "head_branch": "work/next"}]}):
            self.assertEqual(rt.gate_verdict("abc")[0], "none")


class MirrorEvidenceTest(unittest.TestCase):
    PYPI = ("2026-11-12T04:29:40Z Uploading pigeon_home_runner-3.16.20.10-py3-none-any.whl\n"
            "2026-11-12T04:29:41Z Uploading pigeon_home_runner-3.16.20.10.tar.gz\n"
            "2026-11-12T04:29:42Z View at:\n2026-11-12T04:29:42Z https://pypi.org/project/pigeon-home-runner/3.16.20.10/\n")
    SF = ('2026-11-12T04:30:00Z {"result": {"crtime": 1, "name": "homing-pigeon-linux-x86_64-3.16.20.10.tar.gz", "path": "/v3.16.20.10", "size": 1}}'
          "default linux -> homing-pigeon-linux-x86_64-3.16.20.10.tar.gz\n"
          "2026-11-12T04:30:30Z  * [new tag]           v3.16.20.10 -> v3.16.20.10\n"
          "2026-11-12T04:30:31Z source mirrored to SourceForge git (main + tags)\n")
    GL = "2026-11-12T04:30:00Z uploaded SHA384SUMS\n2026-11-12T04:30:01Z uploaded x.whl\n2026-11-12T04:30:02Z gitlab release v3.16.20.10 created\n"

    def test_each_mirrors_own_lines_are_read(self):
        self.assertEqual(rt.mirror_evidence("pypi-publish", self.PYPI),
                         ["https://pypi.org/project/pigeon-home-runner/3.16.20.10/",
                          "Uploading pigeon_home_runner-3.16.20.10-py3-none-any.whl",
                          "Uploading pigeon_home_runner-3.16.20.10.tar.gz"])
        sf = rt.mirror_evidence("sourceforge", self.SF)
        self.assertIn("default linux -> homing-pigeon-linux-x86_64-3.16.20.10.tar.gz", sf)
        self.assertIn("source mirrored to SourceForge git", sf)
        self.assertTrue(any("v3.16.20.10 -> v3.16.20.10" in x for x in sf))
        self.assertTrue(any('"name": "homing-pigeon-linux-x86_64-3.16.20.10.tar.gz"' in x for x in sf))
        self.assertEqual(rt.mirror_evidence("gitlab", self.GL),
                         ["uploaded SHA384SUMS", "uploaded x.whl", "gitlab release v3.16.20.10 created"])
        self.assertEqual(rt.mirror_evidence("release", self.GL), [])

    def test_image_tags(self):
        self.assertEqual(rt.image_tags("pushing ghcr.io/pigeon-home/homing-pigeon:v3.16.20.10 and ghcr.io/pigeon-home/homing-pigeon:latest ghcr.io/pigeon-home/homing-pigeon:latest"),
                         ["ghcr.io/pigeon-home/homing-pigeon:latest", "ghcr.io/pigeon-home/homing-pigeon:v3.16.20.10"])


class ClockTest(unittest.TestCase):
    """One cycle's timeline, read from a scripted record: the main
    build (not the tag build on the same sha) gives the gate time,
    the cut-release dispatches between the commit and the tag are
    the cycle's, and rows the record lacks read as owed."""
    SHA = "8ef9627fe5a1e9fb5f5ec2513db95f9a39a6a12e"

    def _record(self, path, **kw):
        if path.startswith("/git/ref/tags/"):
            return {"object": {"type": "tag", "sha": "t" * 40}}
        if path.startswith("/git/tags/"):
            return {"tagger": {"date": "2026-11-12T06:37:07Z"}, "object": {"sha": self.SHA}}
        if path.startswith("/commits/"):
            return {"commit": {"committer": {"date": "2026-11-12T06:17:22Z"}}}
        if "/build.yml/runs?head_sha" in path:
            return {"workflow_runs": [
                {"id": 2, "head_branch": "v3.16.21.1", "event": "workflow_dispatch", "conclusion": None,
                 "status": "in_progress",
                 "run_started_at": "2026-11-12T06:37:13Z", "created_at": "2026-11-12T06:37:13Z"},
                {"id": 1, "head_branch": "main", "event": "push", "conclusion": "success", "status": "completed",
                 "run_started_at": "2026-11-12T06:17:27Z", "updated_at": "2026-11-12T06:38:09Z"}]}
        if "/build.yml/runs?branch=v3.16.21.1" in path:
            return {"workflow_runs": [{"id": 2, "status": "in_progress",
                                       "run_started_at": "2026-11-12T06:37:13Z"}]}
        if path.startswith("/actions/runs/1/jobs"):
            return {"jobs": [{"name": n, "status": "completed", "conclusion": "success",
                              "completed_at": "2026-11-12T06:2%d:51Z" % (i % 10)}
                             for i, n in enumerate(sorted(rt.gate_jobs()))]}
        if path.startswith("/actions/runs/2/jobs"):
            return {"jobs": [{"name": "release", "status": "in_progress", "conclusion": None,
                              "completed_at": None}]}
        if path.startswith("/actions/runs/7/jobs"):
            return {"jobs": [{"name": "cut", "steps": [{"name": "the build on this commit is green",
                                                        "conclusion": "failure"}]}]}
        if "/cut-release.yml/runs" in path:
            return {"workflow_runs": [
                {"id": 9, "created_at": "2026-11-12T09:00:00Z", "conclusion": "success"},   # a later cycle
                {"id": 7, "created_at": "2026-11-12T06:30:00Z", "conclusion": "failure"},
                {"id": 5, "created_at": "2026-11-12T05:00:00Z", "conclusion": "success"}]}  # the cycle before
        if path.startswith("/releases/tags/"):
            return {}
        raise AssertionError(path)

    def test_the_timeline_reads_the_record(self):
        with mock.patch.object(rt, "api", self._record):
            rows = rt.cycle_clock("3.16.21.1", since="2026-11-12T06:19:58Z")
        labels = [r[0] for r in rows]
        self.assertEqual(labels[0], "asked for")
        self.assertIn("release commit 8ef9627f", labels)
        self.assertIn("build 1 started", labels)
        self.assertIn("gate green (%d jobs)" % len(rt.gate_jobs()), labels)
        self.assertIn("cut-release 7: failure at 'the build on this commit is green'", labels)
        self.assertFalse(any(l.startswith("cut-release 9") or l.startswith("cut-release 5") for l in labels))
        self.assertIn("tag v3.16.21.1", labels)
        self.assertIn("tag build 2 started", labels)
        self.assertIn("release: in_progress", labels)
        self.assertIn("pypi-publish: pending", labels)
        self.assertEqual(dict(rows)["release published (0 assets)"], None)
        text = rt.clock_report(rows)
        # chronological: the commit and its build came before the ask
        self.assertIn("asked for", text.splitlines()[2])
        self.assertRegex(text, r"release published \(0 assets\)\s+--$")
        self.assertRegex(text, r"gate green \(\d+ jobs\)\s+06:27:51Z\s+\+[\d.]+\s+10\.5 min")


class PromoteCheckTest(unittest.TestCase):
    """The tag build's reading of the gate build it promotes: a
    build.yml run on exactly the tag's commit, not cancelled, every
    gate job green. Anything less is named and refused, and a record
    that cannot be read refuses too."""
    SHA = "ea071cb16745efe6032ceefb9564c71b3681239f"

    def _run(self, **kw):
        run = {"id": 43179987340, "head_sha": self.SHA, "path": ".github/workflows/build.yml",
               "conclusion": "success", "event": "push", "head_branch": "main"}
        run.update(kw)
        return run

    def _jobs(self, **kw):
        jobs = {n: {"name": n, "status": "completed", "conclusion": "success"}
                for n in rt.gate_jobs()}
        for n, v in kw.items():
            jobs[n].update(v)
        return jobs

    def _artifacts(self, drop=None, expire=None):
        names = ["ci-test-log", "ci-test-log-macos", "homing-pigeon-python"] + [
            p + "3.16.21.4" for p in rt.PROMOTED_ARTIFACTS if p.endswith("-")]
        out = [{"name": n, "expired": n == expire} for n in names if n != drop]
        return out

    def _ok(self, **kw):
        args = dict(run=self._run(), jobs=self._jobs(), artifacts=self._artifacts())
        args.update(kw)
        return rt.promote_problem("43179987340", self.SHA, **args)

    def test_a_green_build_of_the_commit_passes(self):
        self.assertIsNone(self._ok())
        # the whole run may still be going (the advisory suites), or
        # have been cancelled after the legs completed: the legs are
        # the verdict
        self.assertIsNone(self._ok(run=self._run(conclusion=None, status="in_progress")))
        self.assertIsNone(self._ok(run=self._run(conclusion="cancelled")))
        self.assertIsNone(self._ok(run=self._run(event="workflow_dispatch")))

    def test_every_refusal_is_named(self):
        need = sorted(rt.gate_jobs())
        self.assertIn("not a run id", rt.promote_problem("latest", self.SHA))
        self.assertIn("not a run id", rt.promote_problem("\u0663", self.SHA))
        self.assertIn("cannot be read", rt.promote_problem("1", self.SHA, run={}, jobs={}))
        self.assertIn("is on ", self._ok(run=self._run(head_sha="f" * 40)))
        self.assertIn("not build.yml", self._ok(run=self._run(path=".github/workflows/docker.yml")))
        # a pull_request run's tree is the head merged into the base
        self.assertIn("pull_request run", self._ok(run=self._run(event="pull_request")))
        # a tag build on the same sha, or a branch build
        self.assertIn("build of v3.16.21.4, not of main", self._ok(run=self._run(head_branch="v3.16.21.4")))
        jobs = self._jobs(); del jobs[need[0]]
        self.assertIn("no job for: " + need[0], self._ok(jobs=jobs))
        self.assertIn("%s=completed/failure" % need[1],
                      self._ok(jobs=self._jobs(**{need[1]: {"conclusion": "failure"}})))
        self.assertIn("%s=in_progress/None" % need[2],
                      self._ok(jobs=self._jobs(**{need[2]: {"status": "in_progress", "conclusion": None}})))
        with mock.patch.object(rt, "api", lambda path, **kw: {}):
            self.assertIn("artifacts cannot be read", self._ok(artifacts=None))
        self.assertIn("no artifact for: homing-pigeon-python",
                      self._ok(artifacts=self._artifacts(drop="homing-pigeon-python")))
        self.assertIn("no artifact for: homing-pigeon-windows-x86_64-",
                      self._ok(artifacts=self._artifacts(expire="homing-pigeon-windows-x86_64-3.16.21.4")))

    def test_the_command_reads_the_record_and_exits_by_the_verdict(self):
        def fake_api(path, method="GET", body=None, raw=False):
            if path == "/actions/runs/43179987340":
                return self._run()
            if path.startswith("/actions/runs/43179987340/jobs"):
                return {"jobs": list(self._jobs().values())}
            if path.startswith("/actions/runs/43179987340/artifacts"):
                return {"artifacts": self._artifacts()}
            raise AssertionError(path)
        with mock.patch.object(rt, "api", fake_api), contextlib.redirect_stdout(io.StringIO()) as out:
            rc = rt.main(["promote-check", "--run", "43179987340", "--sha", self.SHA])
        self.assertEqual(rc, 0)
        self.assertIn("promoting its artifacts", out.getvalue())
        with mock.patch.object(rt, "api", fake_api), contextlib.redirect_stdout(io.StringIO()) as out:
            rc = rt.main(["promote-check", "--run", "43179987340", "--sha", "0" * 40])
        self.assertEqual(rc, 1)
        self.assertIn("::error title=promotion::run 43179987340 is on ea071cb16745, not 000000000000", out.getvalue())


class WatchTest(unittest.TestCase):
    def test_the_publish_jobs_are_the_verdict_while_an_advisory_suite_still_runs(self):
        jobs = [{"name": n, "id": i, "status": "completed", "conclusion": "success"}
                for i, n in enumerate(("release", "pypi-publish", "sourceforge", "gitlab"))]
        jobs.append({"name": "test-macos", "id": 9, "status": "in_progress", "conclusion": None})

        def fake_api(path, method="GET", body=None, raw=False):
            if "/build.yml/runs?branch=" in path:
                return {"workflow_runs": [{"id": 5, "status": "in_progress", "conclusion": None}]}
            if "/runs/5/jobs" in path:
                return {"jobs": jobs}
            if "/logs" in path:
                return b""
            if path.startswith("/releases/tags/"):
                return {"assets": [{"name": "homing-pigeon-windows-x86_64-3.16.21.2.zip"}]}
            if "/docker.yml/runs" in path:
                return {"workflow_runs": []}
            raise AssertionError(path)
        out = io.StringIO()
        with mock.patch.object(rt, "api", fake_api), mock.patch.object(rt.time, "sleep"), \
                contextlib.redirect_stdout(out):
            rc = rt.watch_tag_build("3.16.21.2", 1)
        self.assertEqual(rc, 0)
        self.assertIn("tag build 5: in_progress (publish jobs done)", out.getvalue())
        self.assertIn("release: 1 assets", out.getvalue())
        jobs[1]["conclusion"] = "failure"
        with mock.patch.object(rt, "api", fake_api), mock.patch.object(rt.time, "sleep"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rt.watch_tag_build("3.16.21.2", 1), 1)


class WaitTest(unittest.TestCase):
    def test_wait_returns_the_first_value_and_gives_up_on_time(self):
        hits = iter([None, None, "done"])
        with mock.patch.object(rt.time, "sleep"):
            self.assertEqual(rt._wait("x", lambda: next(hits), 1, 5), "done")
        clock = iter([0, 1000, 2000, 3000])
        with mock.patch.object(rt.time, "sleep"), \
                mock.patch.object(rt.time, "monotonic", lambda: next(clock)):
            with self.assertRaises(RuntimeError):
                rt._wait("x", lambda: None, 1, 1)


if __name__ == "__main__":
    unittest.main()
