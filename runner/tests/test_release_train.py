#!/usr/bin/env python3
"""runner/tools/release_train.py: the release cycle's mechanical
steps, pinned on scratch trees and sample logs.

The tool exists because the 3.16.20.10 cycle of 2026-11-11 took
three hours of attention for steps a tool can take: the version
moves one step on its rightmost component in three carriers, the
changelog takes its entry before the newest heading, the gate's
job names come from one rule (runner/tools/cut_gate.py, which the
cut and the promotion check read too) rather than a second place,
and a mirror's own words are read out of its publish job's log."""
import contextlib
import importlib.util
import io
import json
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

    def test_next_version_asks_version4_and_falls_back_to_the_counter(self):
        with mock.patch.object(rt.subprocess, "run",
                               lambda *a, **k: mock.Mock(returncode=0, stdout="measuring...\n3.16.22.1\n", stderr="")):
            self.assertEqual(rt.next_version("3.16.21.10"), "3.16.22.1")
        with mock.patch.object(rt.subprocess, "run",
                               lambda *a, **k: mock.Mock(returncode=1, stdout="", stderr="boom")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rt.next_version("3.16.21.10"), "3.16.21.11")
        self.assertIn("moving the counter alone", out.getvalue())

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
    def test_the_gate_jobs_are_the_cut_gates_legs(self):
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
        # the cut gate's rule: a docs-only release, the legs alone
        if path.startswith("/releases?"):
            return [{"tag_name": "v3.16.20.10", "draft": False, "published_at": "2026-11-12T04:29:30Z"}]
        if path.startswith("/compare/"):
            return {"files": [{"filename": "docs/infrastructure-documents/changelog.md"}]}
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
        self.assertIn("gate green (%d legs)" % len(rt.gate_jobs()), labels)
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
        self.assertRegex(text, r"gate green \(\d+ legs\)\s+06:27:51Z\s+\+[\d.]+\s+10\.5 min")


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
            if path.startswith("/releases?"):
                return [{"tag_name": "v3.16.21.2", "draft": False, "published_at": "2026-11-12T07:21:18Z"}]
            if path.startswith("/compare/"):
                return {"files": [{"filename": "docs/steady/overview.md"}]}
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


class RedMainWarningTest(unittest.TestCase):
    """A release of tests, tools or docs does not wait for the
    suites, so it can be prepared on a main whose suite is red; the
    train names that red where the seat preparing reads it, and
    never refuses on it."""

    def _api(self, runs, jobs):
        def api(path, *a, **k):
            if path.startswith("/actions/workflows/build.yml/runs?branch=main"):
                return {"workflow_runs": runs}
            for rid, js in jobs.items():
                if path.startswith("/actions/runs/%s/jobs" % rid):
                    return {"jobs": js}
            raise AssertionError(path)
        return api

    def _job(self, name, conclusion, status="completed"):
        return {"name": name, "status": status, "conclusion": conclusion}

    def test_the_newest_suite_verdict_is_named_when_red(self):
        # The record of 13 Nov 2026, in small: the head's suite is
        # still running, a docs landing skipped the suite, a
        # superseded head was cancelled before its suite finished,
        # and the newest verdict stands on a run a later head
        # cancelled after its Linux suite and one Windows part had
        # already failed.
        runs = [
            {"id": 6, "event": "push", "conclusion": None, "head_sha": "f" * 40},
            {"id": 5, "event": "push", "conclusion": "success", "head_sha": "e" * 40},
            {"id": 4, "event": "push", "conclusion": "cancelled", "head_sha": "d" * 40},
            {"id": 3, "event": "pull_request", "conclusion": "failure", "head_sha": "c" * 40},
            {"id": 2, "event": "push", "conclusion": "cancelled", "head_sha": "b" * 40},
            {"id": 1, "event": "push", "conclusion": "success", "head_sha": "a" * 40},
        ]
        jobs = {
            6: [self._job("test", None, "in_progress"), self._job("test-windows (1)", "failure")],
            5: [self._job("docs", "success"), self._job("test", "skipped")],
            4: [self._job("test", "cancelled"), self._job("test-windows", "cancelled")],
            2: [self._job("test", "failure"), self._job("test-windows (1)", "failure"),
                self._job("test-windows (2)", "success"), self._job("test-macos", "cancelled")],
            1: [self._job("test", "success")],
        }
        with mock.patch.object(rt, "api", self._api(runs, jobs)):
            text = rt.red_main_warning()
        self.assertIn("main's suite is red: test, test-windows (1) failed on bbbbbbbb (build run 2, the newest "
                      "build of main with a suite verdict; 3 newer builds of main carry none)", text)
        self.assertIn("never stops a cut", text)
        # the red on the newest build of all is named without the count
        with mock.patch.object(rt, "api", self._api(runs[4:], jobs)):
            self.assertIn("(build run 2, the newest build of main with a suite verdict).", rt.red_main_warning())
        # a pull request's build is another tree's: read past, uncounted
        with mock.patch.object(rt, "api", self._api(runs[3:], jobs)):
            self.assertIn("(build run 2, the newest build of main with a suite verdict).", rt.red_main_warning())
        with mock.patch.object(rt, "api", self._api(runs[2:], jobs)):
            self.assertIn("; 1 newer build of main carries none)", rt.red_main_warning())

    def test_a_green_newest_verdict_says_nothing_whatever_came_before(self):
        runs = [{"id": 2, "event": "push", "conclusion": None, "head_sha": "b" * 40},
                {"id": 1, "event": "push", "conclusion": "failure", "head_sha": "a" * 40}]
        jobs = {2: [self._job("test", "success"), self._job("test-windows (1)", None, "in_progress")],
                1: [self._job("test", "failure")]}
        with mock.patch.object(rt, "api", self._api(runs, jobs)):
            self.assertEqual(rt.red_main_warning(), "")
        with mock.patch.object(rt, "api", self._api([], {})):
            self.assertEqual(rt.red_main_warning(), "")

    def test_a_record_it_cannot_read_says_nothing(self):
        def down(path, *a, **k):
            raise RuntimeError("no GH_TOKEN/GITHUB_TOKEN and no gh on PATH")
        with mock.patch.object(rt, "api", down):
            self.assertEqual(rt.red_main_warning(), "")
        with mock.patch.object(rt, "api", lambda path, *a, **k: None):
            self.assertEqual(rt.red_main_warning(), "")

    def test_prepare_cut_and_status_carry_it(self):
        import inspect
        for fn in (rt.cmd_prepare, rt.cmd_cut, rt.cmd_status):
            self.assertIn("red_main_warning()", inspect.getsource(fn), fn.__name__)
        # and the release commit's message carries it beside the
        # latent-code warning
        self.assertIn('message += "\\n" + red + "\\n"', inspect.getsource(rt.cmd_prepare))


class ReleaseDayTest(unittest.TestCase):
    """A release is dated by the UTC day, whichever machine cuts:
    the changelog's dates ran 12, 13, 12 down one evening while two
    seats dated their cuts by two local clocks."""

    def test_the_day_is_the_utc_day_whatever_the_local_clock(self):
        import datetime
        west = datetime.timezone(datetime.timedelta(hours=-8))
        east = datetime.timezone(datetime.timedelta(hours=14))
        # 12 Nov, 8:57 in the evening eight hours behind UTC: the 13th
        self.assertEqual(rt.release_day(datetime.datetime(2026, 11, 12, 20, 57, tzinfo=west)), "2026-11-13")
        # 14 Nov, early morning fourteen hours ahead of UTC: still the 13th
        self.assertEqual(rt.release_day(datetime.datetime(2026, 11, 14, 5, 0, tzinfo=east)), "2026-11-13")
        self.assertEqual(rt.release_day(),
                         datetime.datetime.now(datetime.timezone.utc).date().isoformat())

    def test_no_tool_that_dates_a_release_reads_the_local_day(self):
        for rel in ("runner/tools/release_train.py", "runner/tools/refresh_figures.py"):
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                self.assertNotIn("date.today()", fh.read(), rel)


class HeadBuildLineTest(unittest.TestCase):
    """The loop's first step reads `status`; a head of docs alone
    built no legs, and the line must not call that a red build."""

    def test_skipped_legs_are_not_a_red_build(self):
        line = rt.head_build_line("46d03b067c1c", "red",
                                  "run 43369036184: build-linux=completed/skipped, build-macos=completed/skipped")
        self.assertEqual(line, "build on HEAD 46d03b06: no legs on this head (run 43369036184 skipped them: "
                               "a push of docs alone; a release commit builds its own)")
        self.assertNotIn("red", line)

    def test_a_leg_that_failed_is_red_and_the_rest_read_as_before(self):
        self.assertEqual(
            rt.head_build_line("0123456789", "red", "run 7: build-linux=completed/failure, build-macos=completed/skipped"),
            "build on HEAD 01234567: red (run 7: build-linux=completed/failure, build-macos=completed/skipped)")
        self.assertEqual(rt.head_build_line("0123456789", "green", "run 7: 8 gate jobs green"),
                         "build on HEAD 01234567: green (run 7: 8 gate jobs green)")
        self.assertEqual(rt.head_build_line("0123456789", "none", "no build run on this commit (cancelled runs are not verdicts)"),
                         "build on HEAD 01234567: none (no build run on this commit (cancelled runs are not verdicts))")


class ReferenceDeflateTest(unittest.TestCase):
    """The as-assembled zip figure is re-recorded only under the
    reference zlib: zlib-ng packs the same tree to another size
    (856,590 where the reference gives 855,207), and releases cut
    from a machine linking it carried that machine's figure."""

    def test_the_reference_names_itself_by_digits_alone(self):
        self.assertTrue(rt.reference_deflate("1.3.1"))
        self.assertTrue(rt.reference_deflate("1.2.13"))
        self.assertFalse(rt.reference_deflate("1.3.1.zlib-ng"))
        self.assertFalse(rt.reference_deflate("1.2.11.1-motley"))
        self.assertFalse(rt.reference_deflate("unknown"))
        self.assertFalse(rt.reference_deflate(""))

    def test_another_deflate_leaves_the_zip_figure_standing(self):
        import inspect
        src = inspect.getsource(rt.record_core_measure)
        self.assertIn("if reference_deflate():", src)
        self.assertIn("zip_bytes = core.AS_ASSEMBLED_ZIP_BYTES", src)
        self.assertIn("left at", src)


class MeasureTest(unittest.TestCase):
    def test_measure_re_records_and_reads_the_guards(self):
        calls = []
        with mock.patch.object(rt, "record_core_measure", lambda *a, **k: calls.append("measure") or {"runner/ops": 22585, "runner/runner.py": 7153}), \
                mock.patch.object(rt.subprocess, "run", lambda *a, **k: calls.append("figures") or mock.Mock(returncode=0, stdout="", stderr="")), \
                mock.patch.object(rt, "local_guards", lambda *a, **k: calls.append("guards") or ""), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            rc = rt.main(["measure"])
        self.assertEqual(rc, 0)
        self.assertEqual(calls, ["measure", "figures", "guards"])
        self.assertIn("runner/ops 22585", out.getvalue())
        self.assertIn("commit them with the landing", out.getvalue())

    def test_red_guards_name_themselves(self):
        with mock.patch.object(rt, "record_core_measure", lambda *a, **k: {}), \
                mock.patch.object(rt.subprocess, "run", lambda *a, **k: mock.Mock(returncode=0, stdout="", stderr="")), \
                mock.patch.object(rt, "local_guards", lambda *a, **k: "FAIL: test_x (runner.tests.test_core.CorePartsTest)"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            rc = rt.main(["measure"])
        self.assertEqual(rc, 1)
        self.assertIn("the local guards are red over the re-measure", err.getvalue())
        self.assertIn("test_core.CorePartsTest", err.getvalue())


class PreparePushRetryTest(unittest.TestCase):
    def test_a_rejected_push_rebases_and_pushes_again(self):
        calls = []
        pushes = iter([RuntimeError("git push origin HEAD:main: ! [rejected] HEAD -> main (fetch first)"), None])

        def fake_git(*args, check=True):
            calls.append(args)
            if args[:2] == ("push", "origin"):
                exc = next(pushes)
                if exc:
                    raise exc
                return ""
            if args[0] == "rev-parse":
                return "abc123def456"
            return ""
        args = mock.Mock(note=["x"], subject=None, trailer=[])
        with mock.patch.object(rt, "_git", fake_git), \
                mock.patch.object(rt, "carriers", lambda root=None: {"pyproject.toml": "3.16.24.5", "runner/_version.py": "3.16.24.5", "runner/ops/install.py": "3.16.24.5"}), \
                mock.patch.object(rt, "next_version", lambda v, root=None: "3.16.24.6"), \
                mock.patch.object(rt, "api", lambda path, **kw: {}), \
                mock.patch.object(rt, "write_carriers", lambda *a, **k: None), \
                mock.patch.object(rt, "write_changelog", lambda *a, **k: None), \
                mock.patch.object(rt, "record_core_measure", lambda *a, **k: None), \
                mock.patch.object(rt, "local_guards", lambda *a, **k: None), \
                mock.patch.object(rt.subprocess, "run", lambda *a, **k: mock.Mock(returncode=0, stdout="", stderr="")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            sha = rt.cmd_prepare(args)
        self.assertEqual(sha, "abc123def456")
        tail = [c for c in calls if c[0] in ("push", "fetch", "rebase")]
        self.assertEqual([c[0] for c in tail][-4:], ["push", "fetch", "rebase", "push"])
        self.assertIn("rebasing the release commit onto main", out.getvalue())


class RunRetryTest(unittest.TestCase):
    def test_run_prepares_again_when_main_moved_past_the_commit(self):
        calls = []

        def prepare(args):
            calls.append(("prepare", list(args.note)))
            return "sha%d" % sum(1 for c in calls if c[0] == "prepare")

        def cut(args, sha=None):
            calls.append(("cut", sha))
            if sha == "sha1":
                raise RuntimeError("cut-release 9 concluded failure at step 'tag': url; the workflow's "
                                   "token could not place the tag (main's head abcdef12 has moved past "
                                   "the commit; the token tags the head's tree, so cut the head or prepare again)")
            return 0
        args = mock.Mock(note=["Fix: a thing"], no_retry=False)
        with mock.patch.object(rt, "cmd_prepare", prepare), mock.patch.object(rt, "cmd_cut", cut), \
                mock.patch.object(rt, "carriers", lambda root=None: {"pyproject.toml": "3.16.21.4"}), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rt.cmd_run(args), 0)
        self.assertEqual([c[0] for c in calls], ["prepare", "cut", "prepare", "cut"])
        self.assertEqual(calls[3], ("cut", "sha2"))
        self.assertIn("Re-cut of 3.16.21.4, which never published", calls[2][1][-1])
        self.assertIn("preparing the next version at the head", out.getvalue())

    def test_any_other_refusal_and_no_retry_are_reported_as_they_stand(self):
        def cut(args, sha=None):
            raise RuntimeError("cut-release 9 concluded failure at step 'the build on this commit is green': url")
        args = mock.Mock(note=["x"], no_retry=False)
        with mock.patch.object(rt, "cmd_prepare", lambda a: "sha1"), mock.patch.object(rt, "cmd_cut", cut):
            with self.assertRaises(RuntimeError):
                rt.cmd_run(args)

        def cut2(args, sha=None):
            raise RuntimeError("... has moved past the commit ...")
        args = mock.Mock(note=["x"], no_retry=True)
        with mock.patch.object(rt, "cmd_prepare", lambda a: "sha1"), mock.patch.object(rt, "cmd_cut", cut2), \
                mock.patch.object(rt, "carriers", lambda root=None: {"pyproject.toml": "3.16.21.4"}):
            with self.assertRaises(RuntimeError):
                rt.cmd_run(args)


class LatentWarningTest(unittest.TestCase):
    """The latent-code warning: it warns, and it never refuses.

    The check reads the figure recorded in the statistics
    record (near copies plus exact copies). Under 4% it is
    silent; from 4% it warns and the cut proceeds; at or over
    the standing 5% limit it warns at its loudest and the cut
    still proceeds; a figure that cannot be read warns too.
    Every case returns a string — the function has no refusal
    path — and these tests pin exactly that.
    """

    def _root(self, facts=None, raw=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        if facts is not None or raw is not None:
            path = os.path.join(tmp.name, "docs",
                                "infrastructure-documents", "project")
            os.makedirs(path)
            with open(os.path.join(path, "statistics.md"), "w",
                      encoding="utf-8") as fh:
                if raw is not None:
                    fh.write(raw)
                else:
                    fh.write("# statistics\n\n```json\n%s\n```\n"
                             % json.dumps(facts))
        return tmp.name

    def _facts(self, near, exact):
        return {"latent_near_percent": near,
                "latent_exact_percent": exact,
                "audit_date": "2026-11-12"}

    def test_under_four_percent_is_silent(self):
        root = self._root(self._facts(3.1, 0.02))
        self.assertEqual("", rt.latent_warning(root))
        root = self._root(self._facts(3.97, 0.02))
        self.assertEqual("", rt.latent_warning(root))

    def test_from_four_percent_it_warns_and_proceeds(self):
        for near, exact in ((3.98, 0.02), (4.5, 0.25)):
            root = self._root(self._facts(near, exact))
            warn = rt.latent_warning(root)
            self.assertIn("WARNING", warn)
            self.assertIn("approaching the standing limit", warn)
            self.assertIn("proceeds", warn)

    def test_at_or_over_five_percent_it_warns_at_its_loudest(self):
        for near, exact in ((4.98, 0.02), (6.0, 0.3)):
            root = self._root(self._facts(near, exact))
            warn = rt.latent_warning(root)
            self.assertIn("AT OR OVER THE STANDING LIMIT", warn)
            self.assertIn("never stops shipping", warn)
            self.assertIn("duplication_audit.py", warn)

    def test_an_unreadable_figure_warns_and_proceeds(self):
        cases = [
            self._root(),                                   # no file at all
            self._root(raw="# statistics, no facts block\n"),
            self._root(raw="```json\nnot json\n```\n"),    # malformed facts
            self._root({"audit_date": "2026-11-12"}),       # keys missing
            self._root(self._facts("3.1", 0.02)),           # not a number
        ]
        for root in cases:
            warn = rt.latent_warning(root)
            self.assertIn("could not be read", warn)
            self.assertIn("proceeds", warn)

    def test_the_live_record_is_under_the_warning_line(self):
        self.assertEqual("", rt.latent_warning(REPO))


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



class CutWatchShaTest(unittest.TestCase):
    """The cut's --watch/--sha ordering, pinned (the fix of the
    5:29 PM PST landing, 2026-11-12).

    Suppositions, recorded before the tests ran:
    S1: watch with a sha, given as cmd_cut's parameter or as
        args.sha, does NOT take the watch-only early return: the
        gate is read for that sha, cut-release is dispatched with
        that sha, and only then is the tag build watched, once,
        for the carriers' version; the watch's result is returned.
    S2: watch with no sha anywhere takes the watch-only path: it
        returns watch_tag_build's result for the version it is
        handed (args.version with a leading "v" stripped, else the
        carriers'), and it cuts nothing -- no gate read, no
        dispatch, and (the early return now stands before the sha
        is resolved) no git call at all.
    S3: no watch with a sha takes the plain cut path, unchanged.
    S4: an empty-string sha is no sha, from either seat; a real
        sha on the other seat still cuts.
    Against the pre-fix shape (the watch checked after the sha was
    resolved, whatever sha there was) S1 and the cutting half of
    S4 fail: the watch returned at once and nothing was cut. S2's
    no-git-call half fails there too -- the sha was resolved
    first. The heavy seams (the gate rule, the API, git, the
    watch itself) are stubbed in the file's established style, so
    the pin is the ordering, not the hosted record."""

    VERSION = "3.16.21.4"
    SHA = "0123456789abcdef0123456789abcdef01234567"
    WATCH_RC = 7

    def _drive(self, watch, sha_param, args_sha, args_version=None):
        """Run cmd_cut over stubbed seams; return (rc, calls).

        sha_param is cmd_cut's own argument (None calls it the way
        main does, with no parameter); args_sha is args.sha."""
        calls = {"git": [], "need": [], "gate": [], "dispatch": [],
                 "watch": [], "order": []}
        state = {"dispatched": False}

        def fake_git(*a, **k):
            calls["git"].append(a)
            if a and a[0] == "rev-parse" and len(a) > 1:
                return self.SHA if a[1] == "HEAD" else a[1]
            return ""

        def fake_api(path, method="GET", body=None, raw=False):
            if path.startswith("/git/ref/tags/"):
                return None
            if "cut-release.yml/dispatches" in path:
                state["dispatched"] = True
                calls["dispatch"].append(body)
                calls["order"].append("dispatch")
                return {}
            if "cut-release.yml/runs" in path:
                if state["dispatched"]:
                    return {"workflow_runs": [
                        {"id": 999, "status": "completed",
                         "conclusion": "success",
                         "html_url": "https://example.invalid/cut/999"}]}
                return {"workflow_runs": []}
            raise AssertionError(path)

        def fake_watch(version, limit):
            calls["watch"].append((version, limit))
            calls["order"].append("watch")
            return self.WATCH_RC

        def fake_need(sha, version, api=None):
            calls["need"].append((sha, version))
            calls["order"].append("need")
            return set(), "the legs"

        def fake_gate(sha, version=None):
            calls["gate"].append((sha, version))
            return "green", "run 1: green"

        args = mock.Mock(watch=watch, sha=args_sha,
                         version=args_version, limit=5)
        with mock.patch.object(rt, "latent_warning", lambda *a, **k: ""), \
                mock.patch.object(rt, "red_main_warning", lambda *a, **k: ""), \
                mock.patch.object(rt, "carriers",
                                  lambda root=None: {"pyproject.toml": self.VERSION}), \
                mock.patch.object(rt, "_git", fake_git), \
                mock.patch.object(rt, "api", fake_api), \
                mock.patch.object(rt, "watch_tag_build", fake_watch), \
                mock.patch.object(rt, "gate_verdict", fake_gate), \
                mock.patch.object(rt.cut_gate, "need", fake_need), \
                mock.patch.object(rt, "_wait",
                                  lambda label, probe, interval, limit: probe()), \
                contextlib.redirect_stdout(io.StringIO()):
            if sha_param is None:
                rc = rt.cmd_cut(args)
            else:
                rc = rt.cmd_cut(args, sha=sha_param)
        return rc, calls

    def _assert_cut_then_watch(self, rc, calls):
        self.assertEqual(rc, self.WATCH_RC)
        self.assertEqual(calls["need"], [(self.SHA, self.VERSION)])
        self.assertEqual(len(calls["gate"]), 1)
        self.assertEqual(len(calls["dispatch"]), 1)
        self.assertEqual(calls["dispatch"][0]["inputs"]["sha"], self.SHA)
        self.assertEqual(calls["watch"], [(self.VERSION, 5)])
        self.assertEqual(calls["order"], ["need", "dispatch", "watch"])

    def _assert_watch_only(self, rc, calls, version=None):
        self.assertEqual(rc, self.WATCH_RC)
        self.assertEqual(calls["watch"], [(version or self.VERSION, 5)])
        self.assertEqual(calls["need"], [])
        self.assertEqual(calls["gate"], [])
        self.assertEqual(calls["dispatch"], [])

    def test_watch_with_a_sha_parameter_cuts_first_then_watches(self):
        self._assert_cut_then_watch(*self._drive(True, self.SHA, None))

    def test_watch_with_a_sha_on_the_args_cuts_first_then_watches(self):
        self._assert_cut_then_watch(*self._drive(True, None, self.SHA))

    def test_watch_without_a_sha_only_watches(self):
        rc, calls = self._drive(True, None, None)
        self._assert_watch_only(rc, calls)
        # The early return stands before the sha is resolved: a
        # watch alone never reaches for git.
        self.assertEqual(calls["git"], [])

    def test_no_watch_with_a_sha_takes_the_cut_path(self):
        # The cut's own last step watches the tag build it placed;
        # what pins "no early watch" here is that the gate was read
        # and the dispatch sent before that one watch.
        self._assert_cut_then_watch(*self._drive(False, self.SHA, None))

    def test_an_empty_sha_is_no_sha(self):
        for sha_param, args_sha, cuts in (
                ("", None, False),
                (None, "", False),
                ("", self.SHA, True),
                (self.SHA, "", True)):
            with self.subTest(sha_param=sha_param, args_sha=args_sha):
                rc, calls = self._drive(True, sha_param, args_sha)
                if cuts:
                    self._assert_cut_then_watch(rc, calls)
                else:
                    self._assert_watch_only(rc, calls)

    def test_watch_only_strips_a_leading_v_from_the_version(self):
        rc, calls = self._drive(True, None, None, args_version="v3.16.21.9")
        self._assert_watch_only(rc, calls, version="3.16.21.9")

    def test_a_cut_with_a_sha_watches_the_carriers_version(self):
        # args.version names what a watch ALONE watches; a cut
        # watches the version it cut, the carriers'.
        rc, calls = self._drive(True, self.SHA, None, args_version="v9.9.9.9")
        self._assert_cut_then_watch(rc, calls)


if __name__ == "__main__":
    unittest.main()
