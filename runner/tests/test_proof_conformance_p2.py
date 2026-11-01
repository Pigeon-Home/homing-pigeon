#!/usr/bin/env python3
"""Stage 5 conformance for P2: a job can only narrow what an
execution may disclose.

The pinning test in test_proof_constraints.py holds the values
at the function level. These tests drive the ceilings where the
property lives: the result view and the query answers are read
out of the actual result a real handle_mail run commits and
delivers; the confinement chain is driven through the runner's
own _confinement_argv and the sandbox builder; the watched-set
functions run against a real temp tree. Clause numbers are
properties.md's P2 clauses.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

try:
    from runner.tests import test_proof_conformance as base
except ImportError:  # pragma: no cover - direct-file runs
    import test_proof_conformance as base

SECRET = base.SECRET

_EXEC = {
    "exit_code": 0, "stdout": "hello world", "stderr": "",
    "timed_out": False, "duration_sec": 0.01,
    "stdout_truncated": False, "stderr_truncated": False,
}


def _result_of(out, job_id):
    """The result dict the run committed, read out of the
    delivered result mail."""
    body = out.sent[-1][1]
    envelope, _end = json.JSONDecoder().raw_decode(
        body[body.index("{"):])
    plain = jobcrypto.decrypt_body(envelope, SECRET, job_id, "")
    return json.loads(plain)


def _run_result(job_id, job_extra=None, cfg_extra=None,
                exec_result=None):
    job = {"kind": "exec", "script": "echo hi"}
    if job_extra:
        job.update(job_extra)
    out = base._run(base._job2(job_id, **job),
                    cfg_extra=cfg_extra,
                    exec_result=_EXEC if exec_result is None
                    else exec_result)
    return _result_of(out, job_id)


class ResultViewCeilingTest(base._GateCase):
    """Clauses 1 and 2: the view on the delivered result is the
    narrower of what the job asked and what the owner allows,
    and a member of the job shaped like a ceiling is read
    nowhere."""

    def test_the_owner_ceiling_caps_the_jobs_ask(self):
        result = _run_result(
            "view-1", job_extra={"result_policy": {"view": "full"}},
            cfg_extra={"max_result_view": "summary"})
        self.assertEqual(result["view"], "summary")
        self.assertNotIn("stdout", result)
        self.assertEqual(result["stdout_bytes"],
                         len("hello world".encode("utf-8")))

    def test_the_job_may_narrow_below_the_ceiling(self):
        result = _run_result(
            "view-2", job_extra={"result_policy": {"view": "summary"}})
        self.assertEqual(result["view"], "summary")
        self.assertNotIn("stdout", result)

    def test_a_ceiling_shaped_member_of_the_job_widens_nothing(self):
        result = _run_result(
            "view-3",
            job_extra={"max_result_view": "full",
                       "result_policy": {"view": "full"}},
            cfg_extra={"max_result_view": "summary"})
        self.assertEqual(result["view"], "summary")

    def test_an_unrecognised_ask_reads_as_the_documented_default(self):
        result = _run_result(
            "view-4", job_extra={"result_policy": {"view": "bogus"}})
        self.assertEqual(result["view"], "full")
        self.assertEqual(result["stdout"], "hello world")

    def test_the_full_view_carries_the_output_verbatim(self):
        result = _run_result(
            "view-5", job_extra={"result_policy": {"view": "full"}})
        self.assertEqual(result["view"], "full")
        self.assertEqual(result["stdout"], "hello world")


class RedactionTest(base._GateCase):
    """Clause 2 (patterns): the redaction patterns are built
    from the owner's configuration only."""

    _KEY = "AKIAIOSFODNN7EXAMPLE"
    _EXEC_KEY = dict(_EXEC, stdout="key is " + _KEY + " ok")

    def test_the_redacted_view_applies_the_builtin_patterns(self):
        result = _run_result(
            "redact-1",
            job_extra={"result_policy": {"view": "redacted"}},
            exec_result=self._EXEC_KEY)
        self.assertNotIn(self._KEY, result["stdout"])
        self.assertIn("[REDACTED:aws_key]", result["stdout"])

    def test_a_pattern_named_by_the_job_does_not_apply(self):
        result = _run_result(
            "redact-2",
            job_extra={"result_policy": {"view": "redacted"},
                       "redact_patterns_extra": ["hello"]},
            exec_result=dict(_EXEC, stdout="hello world"))
        self.assertEqual(result["stdout"], "hello world")

    def test_a_pattern_named_by_the_owner_applies(self):
        result = _run_result(
            "redact-3",
            job_extra={"result_policy": {"view": "redacted"}},
            cfg_extra={"redact_patterns_extra":
                       {"greeting": "hello"}},
            exec_result=dict(_EXEC, stdout="hello world"))
        self.assertNotIn("hello", result["stdout"])
        self.assertIn("[REDACTED:greeting]", result["stdout"])


class QueryCeilingTest(base._GateCase):
    """Clauses 2 and 3: queries ride the result's effective
    view, raw lines only leave under full or redacted, redacted
    lines pass through the patterns, and the budget is the
    smaller of the job's ask and the owner's cap."""

    def _answers(self, job_id, result_policy, cfg_extra=None,
                 exec_result=None):
        result = _run_result(
            job_id, job_extra={"result_policy": result_policy},
            cfg_extra=cfg_extra,
            exec_result=_EXEC if exec_result is None else exec_result)
        return result.get("answers") or []

    def test_grep_answers_under_the_full_view(self):
        answers = self._answers("q-1", {
            "view": "full",
            "queries": [{"op": "grep", "pattern": "hello"}]})
        self.assertEqual(len(answers), 1)
        self.assertNotIn("rejected", answers[0])
        self.assertIn("hello world", answers[0]["matches"])

    def test_grep_is_refused_under_the_summary_view(self):
        answers = self._answers("q-2", {
            "view": "summary",
            "queries": [{"op": "grep", "pattern": "hello"}]})
        self.assertEqual(answers,
                         [{"op": "grep", "rejected": "policy"}])

    def test_grep_is_refused_under_the_attested_view(self):
        answers = self._answers("q-3", {
            "view": "attested",
            "queries": [{"op": "grep", "pattern": "hello"}]})
        self.assertEqual(answers,
                         [{"op": "grep", "rejected": "policy"}])

    def test_tail_lines_pass_through_the_patterns_when_redacted(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        answers = self._answers(
            "q-4",
            {"view": "redacted",
             "queries": [{"op": "tail", "lines": 5}]},
            exec_result=dict(_EXEC, stdout="key is " + key + " ok"))
        self.assertEqual(len(answers), 1)
        dumped = json.dumps(answers)
        self.assertNotIn(key, dumped)
        self.assertIn("[REDACTED:aws_key]", dumped)

    def test_the_jobs_own_budget_bounds_it(self):
        answers = self._answers("q-5", {
            "view": "full", "query_budget": 1,
            "queries": [{"op": "grep", "pattern": "hello"},
                        {"op": "grep", "pattern": "world"}]})
        self.assertEqual(len(answers), 2)
        self.assertEqual(answers[1], {"rejected": "budget"})

    def test_the_owners_cap_bounds_the_job(self):
        answers = self._answers(
            "q-6",
            {"view": "full", "query_budget": 5,
             "queries": [{"op": "grep", "pattern": "hello"},
                         {"op": "grep", "pattern": "world"}]},
            cfg_extra={"max_query_budget": 1})
        self.assertEqual(answers[1], {"rejected": "budget"})

    def test_a_rejected_query_still_spends(self):
        # Direct drive of the answering step: the first query is
        # refused on policy, spends its one unit anyway, and the
        # second dies on the budget it left behind.
        answers, spent = runner.answer_queries(
            [{"op": "grep", "pattern": "hello"},
             {"op": "grep", "pattern": "world"}],
            {"stdout": "hello world", "stderr": "",
             "exit_code": 0, "confined": None, "digest": "x"},
            {}, 1, cfg={}, view="summary")
        self.assertEqual(answers[0],
                         {"op": "grep", "rejected": "policy"})
        self.assertEqual(answers[1], {"rejected": "budget"})
        self.assertEqual(spent, 2)


def _audit_entries(base_dir):
    path = os.path.join(base_dir, runner._security.AUDIT_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class ConfinementChainTest(unittest.TestCase):
    """Clauses 1 and 4: the confinement chain is computed from
    the owner's configuration; audit records the decision
    enforce would have made; an unavailable sandbox in enforce
    mode falls back loudly, on the record."""

    def _argv(self, cfg, base_dir, **over):
        call = {"interpreter": ["sh"], "script_path": "/w/job.sh",
                "work": "/w", "args": [], "env": {}}
        call.update(over)
        return runner._confinement_argv(
            cfg, base_dir, "job-x", call["interpreter"],
            call["script_path"], call["work"], call["args"],
            call["env"])

    def test_off_runs_normally(self):
        with tempfile.TemporaryDirectory() as td:
            argv, host_env, sandboxed = self._argv({}, td)
            self.assertEqual(argv, ["sh", "/w/job.sh"])
            self.assertTrue(host_env)
            self.assertFalse(sandboxed)

    def test_audit_runs_normally_and_records_the_decision(self):
        cfg = {"security": {"modes": {"confinement": "audit"}}}
        with tempfile.TemporaryDirectory() as td:
            argv, _host, sandboxed = self._argv(cfg, td)
            self.assertEqual(argv, ["sh", "/w/job.sh"])
            self.assertFalse(sandboxed)
            entries = _audit_entries(td)
            self.assertTrue(any(
                e.get("feature") == "confinement"
                and e.get("decision") == "would_sandbox"
                for e in entries), entries)

    def test_enforce_without_a_sandbox_falls_back_on_the_record(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(runner._sandbox,
                                   "sandbox_available",
                                   return_value=False):
                argv, _host, sandboxed = self._argv(cfg, td)
            self.assertEqual(argv, ["sh", "/w/job.sh"])
            self.assertFalse(sandboxed)
            entries = _audit_entries(td)
            self.assertTrue(any(
                e.get("decision") == "fallback" for e in entries),
                entries)

    def test_enforce_with_a_sandbox_wraps_the_job(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "work")
            os.mkdir(work)
            with mock.patch.object(runner._sandbox,
                                   "sandbox_available",
                                   return_value=True):
                argv, host_env, sandboxed = self._argv(
                    cfg, td, work=work)
            self.assertTrue(sandboxed)
            self.assertFalse(host_env)
            self.assertIn("bwrap", argv[0])
            entries = _audit_entries(td)
            self.assertTrue(any(
                e.get("decision") == "sandboxed" for e in entries),
                entries)


class SandboxShapeTest(unittest.TestCase):
    """Clause 4, and stage 4's finding F1 pinned at the builder:
    the only read-write bind is the workdir itself; an
    interpreter outside /usr brings its install prefix as a
    read-only bind, never shallower than two components, and
    the bind is named in the caller's notes."""

    def _build(self, cfg, interpreter, work, notes=None):
        return runner._sandbox.build_bwrap_command(
            cfg, interpreter, "job.sh", work, [], {},
            notes=notes)

    def test_the_workdir_is_the_only_read_write_bind(self):
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "work")
            os.mkdir(work)
            argv = self._build({}, ["sh"], work)
            binds = [i for i, a in enumerate(argv) if a == "--bind"]
            self.assertEqual(len(binds), 1)
            self.assertEqual(argv[binds[0] + 1], work)

    def test_an_outside_interpreter_brings_its_prefix_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "work")
            os.mkdir(work)
            prefix = os.path.join(td, "opt", "x64")
            os.makedirs(os.path.join(prefix, "bin"))
            interp = os.path.join(prefix, "bin", "python3")
            with open(interp, "w", encoding="utf-8") as fh:
                fh.write("")
            os.chmod(interp, 0o755)
            notes = []
            argv = self._build({}, [interp], work, notes=notes)
            ro = [i for i, a in enumerate(argv) if a == "--ro-bind"]
            pairs = {(argv[i + 1], argv[i + 2]) for i in ro}
            self.assertIn((prefix, prefix), pairs)
            self.assertTrue(any(prefix in n for n in notes), notes)

    def test_a_usr_interpreter_brings_no_prefix_bind(self):
        # /usr is already visible inside the sandbox, so the
        # builder's own computation adds no prefix bind for an
        # interpreter that lives there -- while one outside it
        # brings exactly its install prefix.
        binds = runner._sandbox.interpreter_binds
        self.assertEqual(binds("/usr/bin/python3"), [])
        self.assertEqual(binds("/opt/x64/bin/python3"),
                         [("/opt/x64", "/opt/x64")])
        # The floor F1 states -- never shallower than two
        # components -- holds on the bin layouts: /snap/bin
        # binds /snap/bin, not all of /snap, and a bin layout
        # too shallow for its grandparent falls back to the
        # bin directory itself.
        self.assertEqual(binds("/snap/bin/tool"),
                         [("/snap/bin", "/snap/bin")])
        self.assertEqual(binds("/x/bin/tool"),
                         [("/x/bin", "/x/bin")])

    def test_a_root_level_interpreter_binds_the_root(self):
        # EXHIBIT, not endorsement -- stage 5 finding F1.
        # F1's floor ("never shallower than two components")
        # is enforced only on the bin/grandparent path of
        # _install_prefix; its parent fallback returns the
        # parent unchecked, so an interpreter resolved
        # directly in the filesystem root binds the whole
        # root read-only, and one in a top-level directory
        # binds that whole tree. This test pins the current
        # behavior so the divergence cannot drift silently;
        # stage5.md records it against F1's statement.
        binds = runner._sandbox.interpreter_binds
        self.assertEqual(binds("/tool"), [("/", "/")])
        self.assertEqual(binds("/x/tool"), [("/x", "/x")])


class WatchedSetTest(unittest.TestCase):
    """Clause 5: the watched set is the workspace's parent, the
    comparison names what changed, and a change under a
    protected path is always named."""

    def test_a_change_outside_is_a_violation(self):
        with tempfile.TemporaryDirectory() as td:
            ws = os.path.join(td, "ws")
            os.mkdir(ws)
            outside = os.path.join(td, "outside.txt")
            with open(outside, "w", encoding="utf-8") as fh:
                fh.write("one")
            before = runner.snapshot_outside(ws)
            self.assertIn(outside, before)
            with open(outside, "w", encoding="utf-8") as fh:
                fh.write("one-two-three")
            after = runner.snapshot_outside(ws)
            self.assertTrue(runner.confinement_violated(before, after))

    def test_no_change_is_no_violation(self):
        with tempfile.TemporaryDirectory() as td:
            ws = os.path.join(td, "ws")
            os.mkdir(ws)
            with open(os.path.join(td, "a.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("x")
            before = runner.snapshot_outside(ws)
            after = runner.snapshot_outside(ws)
            self.assertFalse(runner.confinement_violated(before, after))

    def test_the_workspace_itself_is_not_watched(self):
        with tempfile.TemporaryDirectory() as td:
            ws = os.path.join(td, "ws")
            os.mkdir(ws)
            inside = os.path.join(ws, "inner.txt")
            with open(inside, "w", encoding="utf-8") as fh:
                fh.write("x")
            snap = runner.snapshot_outside(ws)
            self.assertNotIn(inside, snap)

    def test_a_protected_path_change_is_named(self):
        with tempfile.TemporaryDirectory() as td:
            guarded = os.path.join(td, "guarded")
            os.mkdir(guarded)
            target = os.path.join(guarded, "keep.txt")
            before = {target: (3, 1.0)}
            after = {target: (4, 2.0)}
            changed = runner.check_protected_paths(
                before, after, [guarded])
            self.assertEqual(changed, [target])
            other = {os.path.join(td, "free.txt"): (3, 1.0)}
            other_after = {os.path.join(td, "free.txt"): (4, 2.0)}
            self.assertEqual(runner.check_protected_paths(
                other, other_after, [guarded]), [])


if __name__ == "__main__":
    unittest.main()
