# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/ci_run_report.py: the CI-health report from run history.

No test ran a line of it. The GitHub calls go through one seam, `_gh`
(and `git remote` for the repo name), so a scripted history drives the
whole tool here: the repo is found from the override, then gh, then
the origin remote, and a box with none of them is told what to set;
the runs list is paged and stops on a short page; a cancelled push is
out of the red rate and counted on its own; per-job stats split red
by platform and keep wall time from green runs only; the report says
each of those in its sections; and main prints, writes, or refuses
an empty history.
"""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from runner.tools import ci_run_report as CR  # noqa: E402


def _done(returncode=0, stdout=""):
    return subprocess.CompletedProcess(["gh"], returncode, stdout, "")


def _run(i, conclusion="success", event="push", branch="main",
         day="2026-10-27", status="completed", sha=None):
    return {"databaseId": i, "headSha": sha or ("%040x" % i),
            "headBranch": branch, "event": event, "status": status,
            "conclusion": conclusion,
            "createdAt": "%sT0%d:00:00Z" % (day, i % 10),
            "updatedAt": "%sT0%d:30:00Z" % (day, i % 10)}


def _job(name, conclusion="success", start="2026-10-27T01:00:00Z",
         end="2026-10-27T01:10:00Z"):
    return {"name": name, "conclusion": conclusion,
            "startedAt": start, "completedAt": end}


class GhSeamTest(unittest.TestCase):
    def test_json_out_or_none(self):
        cases = ((_done(0, '{"a": 1}'), {"a": 1}),
                 (_done(1, '{"a": 1}'), None),
                 (_done(0, "   \n"), None),
                 (_done(0, "not json"), None))
        for res, want in cases:
            with self.subTest(res=res), \
                    mock.patch.object(CR.subprocess, "run", return_value=res):
                self.assertEqual(CR._gh(["api", "x"]), want)


class RepoTest(unittest.TestCase):
    def test_the_override_wins(self):
        with mock.patch.dict(os.environ, {CR.REPO_ENV: "o/r"}), \
                mock.patch.object(CR, "_gh") as gh:
            self.assertEqual(CR._repo(), "o/r")
        gh.assert_not_called()

    def test_gh_names_the_repo(self):
        env = {k: v for k, v in os.environ.items() if k != CR.REPO_ENV}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(CR, "_gh",
                                  return_value={"nameWithOwner": "a/b"}):
            self.assertEqual(CR._repo(), "a/b")

    def test_the_origin_remote_is_the_fallback(self):
        env = {k: v for k, v in os.environ.items() if k != CR.REPO_ENV}
        for url, want in (("https://github.com/Pigeon-Home/homing-pigeon.git\n",
                           "Pigeon-Home/homing-pigeon"),
                          ("git@github.com:Pigeon-Home/homing-pigeon",
                           "Pigeon-Home/homing-pigeon")):
            with self.subTest(url=url), \
                    mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(CR, "_gh", return_value=None), \
                    mock.patch.object(CR.subprocess, "run",
                                      return_value=_done(0, url)):
                self.assertEqual(CR._repo(), want)

    def test_no_way_to_name_the_repo_says_what_to_set(self):
        env = {k: v for k, v in os.environ.items() if k != CR.REPO_ENV}
        # A remote that is not GitHub names no repo; split on a host
        # it does not contain, it came back whole as the "repo".
        for url in ("", "https://example.test/nothing",
                    "https://github.com/onlyowner"):
            with self.subTest(url=url):
                with mock.patch.dict(os.environ, env, clear=True), \
                        mock.patch.object(CR, "_gh", return_value={}), \
                        mock.patch.object(CR.subprocess, "run",
                                          return_value=_done(0, url)), \
                        self.assertRaises(SystemExit) as cm:
                    CR._repo()
                self.assertIn("set %s=owner/repo" % CR.REPO_ENV,
                              str(cm.exception))


class FetchTest(unittest.TestCase):
    def _api_run(self, i):
        return {"id": i, "head_sha": "s%d" % i, "head_branch": "main",
                "event": "push", "status": "completed",
                "conclusion": "success", "created_at": "c", "updated_at": "u"}

    def test_runs_are_paged_and_renamed(self):
        pages = [{"workflow_runs": [self._api_run(i) for i in range(100)]},
                 {"workflow_runs": [self._api_run(i) for i in range(100, 130)]}]
        calls = []

        def gh(args):
            calls.append(args[1])
            return pages[len(calls) - 1]

        with mock.patch.object(CR, "_gh", side_effect=gh):
            rows = CR.fetch_runs("o/r", 250)
        self.assertEqual(len(rows), 130)
        self.assertEqual(len(calls), 2)
        self.assertIn("per_page=100&page=1", calls[0])
        self.assertIn("per_page=100&page=2", calls[1])
        self.assertEqual(rows[0], {"databaseId": 0, "headSha": "s0",
                                   "headBranch": "main", "event": "push",
                                   "status": "completed",
                                   "conclusion": "success",
                                   "createdAt": "c", "updatedAt": "u"})

    def test_the_limit_caps_the_page_and_an_empty_answer_stops(self):
        with mock.patch.object(CR, "_gh", return_value={
                "workflow_runs": [self._api_run(i) for i in range(5)]}) as gh:
            self.assertEqual(len(CR.fetch_runs("o/r", 5)), 5)
        self.assertIn("per_page=5&page=1", gh.call_args[0][0][1])
        for answer in (None, {}, {"workflow_runs": []}):
            with self.subTest(answer=answer), \
                    mock.patch.object(CR, "_gh", return_value=answer):
                self.assertEqual(CR.fetch_runs("o/r", 300), [])

    def test_jobs_or_nothing(self):
        with mock.patch.object(CR, "_gh", return_value={"jobs": [1, 2]}):
            self.assertEqual(CR.fetch_jobs("o/r", 9), [1, 2])
        for answer in (None, {}):
            with mock.patch.object(CR, "_gh", return_value=answer):
                self.assertEqual(CR.fetch_jobs("o/r", 9), [])


class MetricsTest(unittest.TestCase):
    def test_platform_of_a_job_name(self):
        self.assertEqual(CR._platform_of("build-Windows (3.12)"), "windows")
        self.assertEqual(CR._platform_of("test-macos"), "macos")
        self.assertEqual(CR._platform_of("darwin-arm"), "macos")
        self.assertEqual(CR._platform_of("test-ubuntu"), "linux")

    def test_percentiles(self):
        self.assertEqual(CR._pct([], 90), 0.0)
        self.assertEqual(CR._pct([5.0], 50), 5.0)
        # The index rounds half to even: 4.5 picks the fifth value.
        self.assertEqual(CR._pct([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50), 5)
        self.assertEqual(CR._pct([10, 1, 5], 90), 10)

    def test_a_cancelled_push_is_out_of_the_red_rate(self):
        runs = [_run(1, "success"), _run(2, "failure"),
                _run(3, "cancelled"), _run(4, "skipped", day="2026-10-28"),
                _run(5, "failure", event="pull_request"),
                _run(6, "failure", branch="other"),
                _run(7, None, status="in_progress")]
        done, pushes, by_day, concl, cancelled = CR.run_level(runs)
        self.assertEqual(len(done), 6)
        self.assertEqual([r["databaseId"] for r in pushes], [1, 2, 4])
        self.assertEqual(dict(by_day), {"2026-10-27": [1, 2],
                                        "2026-10-28": [0, 1]})
        self.assertEqual(cancelled, 1)
        self.assertEqual(concl["failure"], 3)

    def test_jobs_split_red_by_platform_and_time_green_runs_only(self):
        runs = [_run(1, sha="a" * 40), _run(2, sha="b" * 40),
                _run(3, status="in_progress")]
        jobs = {1: [_job("test-ubuntu"), _job("build-windows", "failure"),
                    _job("test-macos", "skipped"), _job("lint", None)],
                2: [_job("test-ubuntu", "failure"),
                    _job("build-windows", "success",
                         end="2026-10-27T01:30:00Z"),
                    _job("test-macos", "success",
                         start=None)]}
        with mock.patch.object(CR, "fetch_jobs",
                               side_effect=lambda repo, i: jobs.get(i, [])):
            recent, durations, reds, totals, red_on, seen = \
                CR.job_level("o/r", runs, 5)
        self.assertEqual(len(recent), 2)
        self.assertEqual(seen, 2)
        self.assertEqual(dict(totals), {"test-ubuntu": 2, "build-windows": 2,
                                        "test-macos": 1})
        self.assertEqual(dict(reds), {"build-windows": 1, "test-ubuntu": 1})
        self.assertEqual(durations["test-ubuntu"], [10.0])
        self.assertEqual(durations["build-windows"], [30.0])
        self.assertNotIn("test-macos", durations)
        self.assertEqual(red_on["windows"], {"a" * 40})
        self.assertEqual(red_on["linux"], {"b" * 40})

    def test_the_version_comes_from_pyproject_or_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(CR._version(td), "unknown")
            with open(os.path.join(td, "pyproject.toml"), "w",
                      encoding="utf-8") as fh:
                fh.write('[project]\nname = "x"\nversion = "9.8.7"\n')
            self.assertEqual(CR._version(td), "9.8.7")


def _history():
    runs = [_run(1, "success", sha="a" * 40), _run(2, "failure", sha="b" * 40),
            _run(3, "cancelled"), _run(4, "timed_out", sha="c" * 40)]
    jobs = {1: [_job("test-ubuntu", end="2026-10-27T01:04:00Z"),
                _job("build-windows", end="2026-10-27T01:20:00Z"),
                _job("test-macos", end="2026-10-27T01:06:00Z")],
            2: [_job("test-ubuntu", "failure"),
                _job("build-windows", "failure")],
            4: [_job("build-windows", "failure")]}
    return runs, jobs


class ReportTest(unittest.TestCase):
    def _report(self):
        runs, jobs = _history()
        done, pushes, by_day, concl, cancelled = CR.run_level(runs)
        with mock.patch.object(CR, "fetch_jobs",
                               side_effect=lambda repo, i: jobs.get(i, [])):
            _r, durations, reds, totals, red_on, seen = \
                CR.job_level("o/r", runs, 10)
        return CR.build_report("o/r", runs, done, pushes, by_day, concl,
                               cancelled, durations, reds, totals, red_on,
                               seen, "3.14.6")

    def test_each_section_says_what_the_record_shows(self):
        text = self._report()
        self.assertTrue(text.startswith(
            "# CI health: the build pipeline, read from its own runs\n"))
        self.assertIn("for package 3.14.6", text)
        self.assertIn("Window: 4 completed runs, 2026-10-27 01:00Z to "
                      "2026-10-27 04:00Z.", text)
        self.assertIn("Of 3 completed (non-cancelled) pushes to main in the "
                      "window, 2 ended red (67%). A further 1 main pushes "
                      "were cancelled", text)
        self.assertIn("- 2026-10-27: 2 / 3", text)
        self.assertIn("| build-windows | 3 | 2 | 67% |", text)
        self.assertIn("Windows-only 1, Linux-only 0, both 1, macOS 0", text)
        self.assertIn("Long pole: **build-windows** at p90 20.0 min", text)
        self.assertIn("| test-macos | 60 | 58% |", text)
        self.assertIn("1 run(s) concluded `timed_out`", text)
        self.assertTrue(text.endswith("stays green.\n\n"))

    def test_an_empty_window_still_reads(self):
        text = CR.build_report("o/r", [], [], [], {}, {}, 0, {}, {}, {},
                               {"windows": set(), "linux": set(),
                                "macos": set()}, 0, "unknown")
        self.assertIn("Window: 0 completed runs, n/a.", text)
        self.assertIn("ended red (0%)", text)
        self.assertNotIn("Long pole", text)
        self.assertNotIn("By day", text)


class MainTest(unittest.TestCase):
    def _main(self, argv, runs, jobs):
        out = io.StringIO()
        with mock.patch.object(CR, "_repo", return_value="o/r"), \
                mock.patch.object(CR, "fetch_runs", return_value=runs), \
                mock.patch.object(CR, "fetch_jobs",
                                  side_effect=lambda repo, i: jobs.get(i, [])), \
                contextlib.redirect_stdout(out):
            rc = CR.main(argv)
        return rc, out.getvalue()

    def test_stdout_prints_the_report(self):
        runs, jobs = _history()
        rc, out = self._main(["--stdout", "--job-detail", "2"], runs, jobs)
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("# CI health"))
        self.assertIn("sampled from the 2 most recent runs", out)

    def test_out_writes_the_file_and_says_so(self):
        runs, jobs = _history()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "deep", "ci-health.md")
            rc, out = self._main(["--out", path], runs, jobs)
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as fh:
                self.assertTrue(fh.read().startswith("# CI health"))
        self.assertEqual(out, "wrote %s (4 runs, 3 sampled for jobs)\n" % path)

    def test_no_runs_is_refused_with_the_likely_cause(self):
        with self.assertRaises(SystemExit) as cm:
            self._main([], [], {})
        self.assertIn("no runs returned for o/r build.yml", str(cm.exception))
        self.assertIn("is gh authenticated?", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
