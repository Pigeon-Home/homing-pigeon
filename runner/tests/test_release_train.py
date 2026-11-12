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
import importlib.util
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
        runs = {"workflow_runs": [
            {"id": 1, "conclusion": "cancelled"},
            {"id": 3, "conclusion": "success"},
            {"id": 2, "conclusion": "failure"}]}
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
        with mock.patch.object(rt, "api", lambda path, **kw: {"workflow_runs": [{"id": 7, "conclusion": None}]} if "head_sha" in path else {"jobs": jobs}):
            state, detail = rt.gate_verdict("abc")
        self.assertEqual(state, "red")
        self.assertIn(need[0], detail)
        jobs[0]["conclusion"] = "success"
        with mock.patch.object(rt, "api", lambda path, **kw: {"workflow_runs": [{"id": 7, "conclusion": None}]} if "head_sha" in path else {"jobs": jobs}):
            state, detail = rt.gate_verdict("abc")
        self.assertEqual(state, "running")
        self.assertIn(need[1], detail)

    def test_no_run_is_no_verdict(self):
        with mock.patch.object(rt, "api", lambda path, **kw: {"workflow_runs": [{"id": 1, "conclusion": "cancelled"}]}):
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
                {"id": 2, "head_branch": "v3.16.21.1", "conclusion": None, "status": "in_progress",
                 "run_started_at": "2026-11-12T06:37:13Z", "created_at": "2026-11-12T06:37:13Z"},
                {"id": 1, "head_branch": "main", "conclusion": "success", "status": "completed",
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
