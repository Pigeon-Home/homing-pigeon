# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""GitHub Actions as an ephemeral target backend (Phase 3).

A dispatch boots a fresh GitHub-hosted VM of the target's platform,
runs `homing-pigeon --once --drain` against the tenant's queue, and
exits. No machine persists; the unit of cost is the run's billable
minutes, which the timing endpoint reports.

API: https://api.github.com (Bearer token). Shapes recorded in
runner/tests/hosting_fixtures/github_actions.json.
"""
from __future__ import annotations

import time
import uuid

from . import base

API = "https://api.github.com"
# The workflow's `run-name` must embed the ticket so the run can be
# found again: `run-name: hp ${{ inputs.ticket }}`.
TICKET_PREFIX = "hp "
RUNNER_LABELS = {"linux-ephemeral": "ubuntu-latest",
                 "windows-ephemeral": "windows-latest",
                 "macos-ephemeral": "macos-latest"}


class Dispatch:
    """One ephemeral run: the ticket we asked for, and what GitHub
    knows about it once the run exists."""

    __slots__ = ("ticket", "target", "run_id", "status", "conclusion",
                 "billable_ms", "raw")

    def __init__(self, ticket, target, run_id=None, status="requested",
                 conclusion=None, billable_ms=None, raw=None):
        self.ticket = ticket
        self.target = target
        self.run_id = run_id
        self.status = status
        self.conclusion = conclusion
        self.billable_ms = billable_ms
        self.raw = raw if isinstance(raw, dict) else {}

    @property
    def minutes(self):
        """Billable minutes, rounded up the way GitHub bills."""
        if self.billable_ms is None:
            return None
        return -(-int(self.billable_ms) // 60000)

    def to_record(self):
        return {"ticket": self.ticket, "target": self.target,
                "run_id": self.run_id, "status": self.status,
                "conclusion": self.conclusion, "minutes": self.minutes}


class GitHubActions:
    name = "github-actions"

    def __init__(self, http, token, owner, repo, workflow="hp-ephemeral.yml",
                 ref="main", api=API):
        self.http = http
        self.token = token
        self.owner = owner
        self.repo = repo
        self.workflow = workflow
        self.ref = ref
        self.api = api.rstrip("/")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"}

    def _repo(self):
        return f"{self.api}/repos/{self.owner}/{self.repo}"

    def _call(self, method, path, body=None, what=""):
        resp = self.http.request(method, self._repo() + path,
                                 headers=self._headers(), body=body)
        if not resp.ok:
            data = resp.json() or {}
            message = data.get("message") if isinstance(data, dict) else None
            if resp.status == 403 and resp.header("x-ratelimit-remaining") == "0":
                reset = resp.header("x-ratelimit-reset")
                try:
                    retry = max(0.0, float(reset) - time.time()) if reset else None
                except ValueError:
                    retry = None
                raise base.RateLimited(
                    f"{self.name}: {what or path}: rate limited: {message}",
                    status=403, retry_after=retry)
            base.raise_for(resp, self.name, what or path, message=message)
        return resp

    def dispatch(self, target, tenant, version, blob_ref, drain_jobs=1,
                 drain_seconds=900, ticket=None):
        """Ask for one run. `blob_ref` names the repository secret or
        the queue URL the workflow reads the tenant's blob from; the
        blob itself never travels through this API."""
        if target not in RUNNER_LABELS:
            raise ValueError(f"unknown ephemeral target {target!r}")
        ticket = ticket or uuid.uuid4().hex[:12]
        inputs = {"ticket": ticket, "target": target, "tenant": tenant,
                  "version": str(version).lstrip("v"),
                  "runs_on": RUNNER_LABELS[target],
                  "blob_ref": blob_ref,
                  "drain_jobs": str(int(drain_jobs)),
                  "drain_seconds": str(int(drain_seconds))}
        self._call("POST", f"/actions/workflows/{self.workflow}/dispatches",
                   {"ref": self.ref, "inputs": inputs}, "dispatch workflow")
        return Dispatch(ticket, target)

    def find_run(self, dispatch):
        """The run GitHub created for the ticket, by run-name. None
        until it appears (dispatch returns before the run exists)."""
        resp = self._call("GET", "/actions/runs?event=workflow_dispatch"
                                 "&per_page=30", what="list runs")
        data = resp.json() or {}
        want = TICKET_PREFIX + dispatch.ticket
        for run in data.get("workflow_runs") or []:
            if not isinstance(run, dict):
                continue
            title = run.get("display_title") or run.get("name") or ""
            if title.strip() == want:
                dispatch.run_id = run.get("id")
                dispatch.status = run.get("status") or dispatch.status
                dispatch.conclusion = run.get("conclusion")
                dispatch.raw = run
                return dispatch
        return None

    def refresh(self, dispatch):
        if dispatch.run_id is None:
            return self.find_run(dispatch) or dispatch
        resp = self._call("GET", f"/actions/runs/{dispatch.run_id}",
                          what="get run")
        run = resp.json() or {}
        dispatch.status = run.get("status") or dispatch.status
        dispatch.conclusion = run.get("conclusion")
        dispatch.raw = run
        return dispatch

    def timing(self, dispatch):
        """Billable milliseconds for a completed run, or None."""
        if dispatch.run_id is None:
            return None
        resp = self._call("GET", f"/actions/runs/{dispatch.run_id}/timing",
                          what="run timing")
        data = resp.json() or {}
        total = 0
        found = False
        billable = data.get("billable") if isinstance(
            data.get("billable"), dict) else {}
        for entry in billable.values():
            if isinstance(entry, dict) and isinstance(
                    entry.get("total_ms"), int):
                total += entry["total_ms"]
                found = True
        if not found and isinstance(data.get("run_duration_ms"), int):
            total, found = data["run_duration_ms"], True
        dispatch.billable_ms = total if found else None
        return dispatch.billable_ms

    def wait(self, dispatch, timeout=1800, interval=10, sleep=time.sleep,
             clock=time.monotonic):
        """Poll until the run completes; fills in timing. Raises
        ProvisionTimeout when the budget is spent first."""
        t0 = clock()
        while True:
            self.refresh(dispatch)
            if dispatch.status == "completed":
                self.timing(dispatch)
                return dispatch
            if clock() - t0 >= timeout:
                raise base.ProvisionTimeout(
                    f"{self.name}: run for ticket {dispatch.ticket} still "
                    f"{dispatch.status} after {timeout}s")
            sleep(interval)
