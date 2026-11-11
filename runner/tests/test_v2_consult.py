# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Q139: the determination decision point (consult).

The desk's supposition, pinned: the decision point is a pure
routing query computed once per job from config + job + the
already-formed opinion plan, the remote question goes out
first, the local consult runs inside the existing deadline
window, and the combined picture is recorded only on the
result (a consult segment) and in the audit -- never in the
wire determination, never in the execution decision. Legacy
mode (v2_consult absent, "remote") is byte-identical to the
suite before the decision point existed.
"""
import contextlib
import io
import json
import os
import random
import string
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.guard import security as SEC  # noqa: E402
from runner.wire import protocol_v2 as V  # noqa: E402

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)

REGISTRY = {
    "format": "hp-posture-registry",
    "version": 1,
    "postures": [
        {"id": "named-only", "tag": "C",
         "say": "The project may be named in public writing.",
         "shelf": "Public shelf."},
        {"id": "old-posture", "tag": "Z",
         "say": "The project could once be described.",
         "shelf": "Private shelf only.",
         "status": "retired", "successor": "named-only"},
    ],
}

TAGGING = {
    "format": "hp-posture-tagging",
    "version": 1,
    "projects": [{"project": "bookend", "posture": "C"}],
}

STAMP = "hp-posture-1-named-only"

PLAN_FAIL = {"mode": "repair", "active": True, "checks_run": True,
             "findings": [{"detail": "no interpreter on PATH"}],
             "repair_action": None, "attach": None}
PLAN_CLEAN = {"mode": "advise", "active": True, "checks_run": True,
              "findings": [], "repair_action": None, "attach": None}
PLAN_REPAIR = {"mode": "repair", "active": True, "checks_run": True,
               "findings": [],
               "repair_action": {"action": "swap",
                                 "description": "platform default"},
               "attach": None}
PLAN_OFF = {"mode": "off", "active": False, "checks_run": False,
            "findings": [], "repair_action": None, "attach": None}

JOB = {"job_id": "cj1", "kind": "exec", "script": "echo hi"}


def _cfg(**extra):
    cfg = {"protocol_v2": True, "oracle_mode": "deterministic",
           "v2_answer_deadline_sec": 0}
    cfg.update(extra)
    return cfg


def _both(**extra):
    return _cfg(v2_consult="both", **extra)


def _llm_cfg(**extra):
    cfg = {"protocol_v2": True, "oracle_mode": "llm",
           "v2_consult": "both", "v2_answer_deadline_sec": 5,
           "oracle_opinion_model": True,
           "inference": {"endpoint": "http://127.0.0.1:11434/v1",
                         "model": "m"}}
    cfg.update(extra)
    return cfg


def _file_answer(base_dir, cfg, job, text):
    q = V.question_for(cfg, job)
    V.store_answer(base_dir, V.answer_for(q, text))
    return q


def _consult_segments(segments):
    return [s for s in segments if s.get("kind") == "consult"]


def _audit_rows(base_dir, feature="v2_consult"):
    path = os.path.join(base_dir, "security-audit.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            if entry.get("feature") == feature:
                rows.append(entry)
    return rows


class _Guard(unittest.TestCase):
    """Save/restore the process posture resolution."""

    def setUp(self):
        self._saved = (runner._POSTURE_DECLARED,
                       runner._POSTURE_PROJECT, runner._POSTURE_STAMP)
        self._saved_cleartext = runner._ALLOW_CLEARTEXT_JOBS

    def tearDown(self):
        runner._set_posture_resolution(*self._saved)
        runner._set_allow_cleartext_jobs(self._saved_cleartext)


# ------------------------------------------------------------ the mode key

class ConsultModeOfTest(unittest.TestCase):
    def test_absent_is_remote(self):
        self.assertEqual(V.consult_mode_of({}), "remote")
        self.assertEqual(V.consult_mode_of({"protocol_v2": True}),
                         "remote")

    def test_each_valid_value(self):
        for mode in ("remote", "both", "local"):
            self.assertEqual(V.consult_mode_of({"v2_consult": mode}),
                             mode)

    def test_unknown_shapes_fall_back_to_remote_without_raising(self):
        for raw in ("sideways", "", None, True, 3, ["both"], {"m": 1}):
            self.assertEqual(V.consult_mode_of({"v2_consult": raw}),
                             "remote", repr(raw))

    def test_non_dict_config_is_remote(self):
        self.assertEqual(V.consult_mode_of(None), "remote")
        self.assertEqual(V.consult_mode_of("both"), "remote")


class ValidateConsultConfigTest(unittest.TestCase):
    def test_absent_keys_are_fine(self):
        self.assertIsNone(V.validate_consult_config({}))
        self.assertIsNone(V.validate_consult_config(None))

    def test_each_valid_mode_passes(self):
        for mode in ("remote", "both", "local"):
            self.assertIsNone(
                V.validate_consult_config({"v2_consult": mode}))

    def test_unknown_mode_string_refuses_naming_the_key(self):
        with self.assertRaises(RuntimeError) as cm:
            V.validate_consult_config({"v2_consult": "sideways"})
        self.assertIn("v2_consult", str(cm.exception))

    def test_empty_mode_string_refuses(self):
        with self.assertRaises(RuntimeError):
            V.validate_consult_config({"v2_consult": ""})

    def test_non_string_modes_refuse(self):
        for raw in (True, False, 0, 1, None, ["both"], {"m": "both"}):
            with self.assertRaises(RuntimeError, msg=repr(raw)):
                V.validate_consult_config({"v2_consult": raw})

    def _with_block(self, postures):
        return {"v2_question_postures": postures,
                "disclosure_posture": {"registry": "r.json",
                                       "tagging": "t.json",
                                       "project": "bookend"}}

    def test_postures_absent_is_fine(self):
        self.assertIsNone(V.validate_consult_config(
            {"disclosure_posture": {"registry": "r"}}))

    def test_postures_empty_list_is_valid_with_a_block(self):
        self.assertIsNone(V.validate_consult_config(
            self._with_block([]),
            active_ids={"named-only"}, retired_ids={"old-posture"}))

    def test_postures_active_ids_pass(self):
        self.assertIsNone(V.validate_consult_config(
            self._with_block(["named-only"]),
            active_ids={"named-only"}, retired_ids={"old-posture"}))

    def test_postures_unknown_id_refuses_naming_it(self):
        with self.assertRaises(RuntimeError) as cm:
            V.validate_consult_config(
                self._with_block(["never-declared"]),
                active_ids={"named-only"}, retired_ids=set())
        self.assertIn("never-declared", str(cm.exception))

    def test_postures_retired_id_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            V.validate_consult_config(
                self._with_block(["old-posture"]),
                active_ids={"named-only", "old-posture"},
                retired_ids={"old-posture"})
        self.assertIn("retired", str(cm.exception))

    def test_postures_non_list_refuses(self):
        for raw in ("named-only", 7, None, True, {"id": "named-only"}):
            with self.assertRaises(RuntimeError, msg=repr(raw)):
                V.validate_consult_config(self._with_block(raw))

    def test_postures_non_string_entry_refuses(self):
        for raw in ([7], [None], [True], [["named-only"]], [""]):
            with self.assertRaises(RuntimeError, msg=repr(raw)):
                V.validate_consult_config(self._with_block(raw))

    def test_postures_duplicate_entries_refuse(self):
        with self.assertRaises(RuntimeError) as cm:
            V.validate_consult_config(
                self._with_block(["named-only", "named-only"]),
                active_ids={"named-only"}, retired_ids=set())
        self.assertIn("v2_question_postures", str(cm.exception))

    def test_postures_without_a_posture_block_refuses(self):
        for cfg in ({"v2_question_postures": ["named-only"]},
                    {"v2_question_postures": [],
                     "disclosure_posture": {}},
                    {"v2_question_postures": [],
                     "disclosure_posture": "named-only"}):
            with self.assertRaises(RuntimeError, msg=repr(cfg)) as cm:
                V.validate_consult_config(cfg)
            self.assertIn("v2_question_postures", str(cm.exception))


# ------------------------------------------------------------ stances

class LocalStanceTest(unittest.TestCase):
    def test_no_plan_is_none(self):
        self.assertEqual(V.local_stance(None), "none")
        self.assertEqual(V.local_stance("plan"), "none")

    def test_findings_are_fail(self):
        self.assertEqual(V.local_stance(PLAN_FAIL), "fail")

    def test_repair_without_findings_is_unknown(self):
        self.assertEqual(V.local_stance(PLAN_REPAIR), "unknown")

    def test_clean_plan_is_proceed(self):
        self.assertEqual(V.local_stance(PLAN_CLEAN), "proceed")
        self.assertEqual(V.local_stance({}), "proceed")

    def test_inactive_plan_is_none(self):
        plan = dict(PLAN_FAIL)
        plan["active"] = False
        self.assertEqual(V.local_stance(plan), "none")


class CombinedOutcomeTest(unittest.TestCase):
    def test_matrix(self):
        present_local = ("fail", "unknown", "proceed")
        present_remote = ("proceed", "stated")
        for local in ("fail", "unknown", "proceed", "none"):
            for remote in ("proceed", "stated", "no_answer",
                           "not_asked", "none"):
                outcome, split = V.combined_outcome(local, remote)
                if local in present_local and remote in present_remote:
                    want = "both"
                elif local in present_local:
                    want = "local_only"
                elif remote in present_remote:
                    want = "remote_only"
                else:
                    want = "none"
                self.assertEqual(outcome, want, (local, remote))
                self.assertEqual(
                    split, local == "fail" and remote == "proceed",
                    (local, remote))

    def test_split_is_only_fail_against_proceed(self):
        self.assertTrue(V.combined_outcome("fail", "proceed")[1])
        self.assertFalse(V.combined_outcome("fail", "stated")[1])
        self.assertFalse(V.combined_outcome("unknown", "proceed")[1])
        self.assertFalse(V.combined_outcome("proceed", "proceed")[1])


class RemoteStanceTest(unittest.TestCase):
    def _q(self):
        return V.question_for(_cfg(), JOB)

    def test_timely_default_answer_is_proceed(self):
        segs = [V.segment("answerer", "answer", "proceed")]
        self.assertEqual(V.remote_stance_of(segs, self._q()),
                         ("proceed", False))

    def test_timely_default_answer_matching_is_case_and_space_tolerant(self):
        segs = [V.segment("answerer", "answer", "  PROCEED ")]
        self.assertEqual(V.remote_stance_of(segs, self._q())[0],
                         "proceed")

    def test_timely_free_text_is_stated_never_parsed(self):
        for text in ("proceed with care", "do not proceed",
                     "fail", "looks fine to me"):
            segs = [V.segment("answerer", "answer", text)]
            self.assertEqual(V.remote_stance_of(segs, self._q())[0],
                             "stated", text)

    def test_local_default_alone_is_no_answer(self):
        segs = [V.segment("runner", "local_default", "proceed")]
        self.assertEqual(V.remote_stance_of(segs, self._q()),
                         ("no_answer", False))

    def test_late_answer_is_flagged_and_not_the_stance(self):
        segs = [V.segment("runner", "local_default", "proceed"),
                V.segment("answerer", "late_answer", "proceed")]
        self.assertEqual(V.remote_stance_of(segs, self._q()),
                         ("no_answer", True))

    def test_no_segments_is_no_answer(self):
        self.assertEqual(V.remote_stance_of([], self._q()),
                         ("no_answer", False))
        self.assertEqual(V.remote_stance_of(None, None),
                         ("no_answer", False))


# ------------------------------------------------------------ the gate

class QuestionGateTest(_Guard):
    def test_no_allowlist_passes_under_every_mode(self):
        for mode in ("off", "audit", "enforce"):
            cfg = {"security": {"modes": {"v2_question": mode}}}
            if mode == "off":
                self.assertEqual(V.question_gate(cfg, None, False),
                                 (False, True, "v2_question_off"))
            else:
                self.assertEqual(V.question_gate(cfg, None, False),
                                 (True, False, None), mode)

    def test_unset_mode_reads_enforce_and_passes_without_allowlist(self):
        self.assertEqual(V.question_gate({}, "named-only", True),
                         (True, False, None))

    def test_the_feature_is_registered(self):
        self.assertIn("v2_question", SEC.FEATURES)
        self.assertEqual(SEC.sec_mode({}, "v2_question"), "enforce")
        self.assertEqual(
            SEC.sec_mode({"security": {"modes": {"v2_question": "off"}}},
                         "v2_question"), "off")

    def test_listed_posture_passes(self):
        cfg = {"v2_question_postures": ["named-only"]}
        self.assertEqual(V.question_gate(cfg, "named-only", True),
                         (True, False, None))

    def test_unlisted_posture_blocks_at_enforce(self):
        cfg = {"v2_question_postures": ["other"]}
        self.assertEqual(V.question_gate(cfg, "named-only", True),
                         (False, True, "posture_not_listed"))

    def test_unstamped_deployment_blocks_at_enforce(self):
        cfg = {"v2_question_postures": ["named-only"]}
        self.assertEqual(V.question_gate(cfg, None, True),
                         (False, True, "posture_unstamped"))
        self.assertEqual(V.question_gate(cfg, None, False),
                         (False, True, "posture_unstamped"))

    def test_empty_allowlist_permits_no_posture(self):
        cfg = {"v2_question_postures": []}
        self.assertEqual(V.question_gate(cfg, "named-only", True),
                         (False, True, "posture_not_listed"))

    def test_audit_sends_and_records_what_enforce_would_decide(self):
        cfg = {"v2_question_postures": ["other"],
               "security": {"modes": {"v2_question": "audit"}}}
        self.assertEqual(V.question_gate(cfg, "named-only", True),
                         (True, True, "posture_not_listed"))

    def test_off_disables_regardless_of_the_allowlist(self):
        cfg = {"v2_question_postures": ["named-only"],
               "security": {"modes": {"v2_question": "off"}}}
        self.assertEqual(V.question_gate(cfg, "named-only", True),
                         (False, True, "v2_question_off"))

    def test_malformed_allowlist_is_a_state_problem_not_a_block(self):
        cfg = {"v2_question_postures": "named-only"}
        self.assertEqual(V.question_gate(cfg, "named-only", True),
                         (True, False, "posture_state_unavailable"))


# ------------------------------------------------------------ routing

class ConsultPlanRoutingTest(_Guard):
    def test_v2_off_consults_nothing(self):
        plan = V.consult_plan({"protocol_v2": False}, JOB, PLAN_FAIL)
        self.assertEqual(plan["sources"], ())
        self.assertEqual(plan["reason"], "v2_off")

    def test_answer_only_consults_nothing(self):
        plan = V.consult_plan(_both(answer_only=True), JOB, PLAN_FAIL)
        self.assertEqual(plan["sources"], ())
        self.assertEqual(plan["reason"], "v2_off")

    def test_legacy_remote_asks_as_today(self):
        plan = V.consult_plan(_cfg(), JOB, PLAN_FAIL)
        self.assertEqual(plan["mode"], "remote")
        self.assertEqual(plan["sources"], ("remote",))
        self.assertEqual(plan["reason"], "legacy_remote")

    def test_legacy_remote_clean_pass_still_asks_as_today(self):
        # The clean-pass suppression is a property of both mode
        # only; legacy deployments are byte-identical.
        plan = V.consult_plan(_cfg(), JOB, PLAN_CLEAN)
        self.assertEqual(plan["sources"], ("remote",))
        self.assertEqual(plan["reason"], "legacy_remote")

    def test_legacy_remote_non_exec_does_not_ask(self):
        plan = V.consult_plan(_cfg(), {"job_id": "j", "kind": "ping"},
                              PLAN_FAIL)
        self.assertEqual(plan["sources"], ())
        self.assertEqual(plan["reason"], "legacy_no_ask")

    def test_legacy_remote_llm_does_not_ask(self):
        plan = V.consult_plan(_cfg(oracle_mode="llm"), JOB, PLAN_FAIL)
        self.assertEqual(plan["sources"], ())
        self.assertEqual(plan["reason"], "legacy_no_ask")

    def test_both_deterministic_consults_det_and_remote(self):
        plan = V.consult_plan(_both(), JOB, PLAN_FAIL)
        self.assertEqual(plan["sources"], ("oracle_det", "remote"))
        self.assertEqual(plan["reason"], "both_deterministic")
        self.assertEqual(plan["local_stance"], "fail")

    def test_both_clean_pass_is_settled_and_stays_nothing(self):
        plan = V.consult_plan(_both(), JOB, PLAN_CLEAN)
        self.assertEqual(plan["sources"], ())
        self.assertEqual(plan["reason"], "clean_pass_settled")

    def test_both_repair_plan_is_not_a_clean_pass(self):
        plan = V.consult_plan(_both(), JOB, PLAN_REPAIR)
        self.assertEqual(plan["sources"], ("oracle_det", "remote"))
        self.assertEqual(plan["local_stance"], "unknown")

    def test_both_llm_with_model_consults_all_three(self):
        plan = V.consult_plan(_llm_cfg(), JOB, PLAN_FAIL,
                              model_available=True)
        self.assertEqual(plan["sources"],
                         ("oracle_det", "oracle_model", "remote"))
        self.assertEqual(plan["reason"], "both_llm_model")

    def test_both_llm_without_model_is_det_and_remote(self):
        plan = V.consult_plan(_llm_cfg(), JOB, PLAN_FAIL,
                              model_available=False)
        self.assertEqual(plan["sources"], ("oracle_det", "remote"))
        self.assertEqual(plan["reason"], "both_det_remote")

    def test_both_no_plan_consults_remote_alone(self):
        plan = V.consult_plan(_both(), JOB, None)
        self.assertEqual(plan["sources"], ("remote",))
        self.assertEqual(plan["reason"], "no_plan")
        self.assertEqual(plan["local_stance"], "none")

    def test_both_inactive_plan_is_no_plan(self):
        plan = V.consult_plan(_both(), JOB, PLAN_OFF)
        self.assertEqual(plan["local_stance"], "none")
        self.assertEqual(plan["reason"], "no_plan")

    def test_both_non_exec_is_local_only(self):
        plan = V.consult_plan(_both(), {"job_id": "j", "kind": "ping"},
                              PLAN_FAIL)
        self.assertEqual(plan["sources"], ("oracle_det",))
        self.assertEqual(plan["reason"], "kind_not_exec")

    def test_local_mode_never_asks_remote(self):
        plan = V.consult_plan(_cfg(v2_consult="local"), JOB, PLAN_FAIL)
        self.assertEqual(plan["sources"], ("oracle_det",))
        self.assertEqual(plan["reason"], "local_only_mode")

    def test_local_mode_no_plan_consults_nothing(self):
        plan = V.consult_plan(_cfg(v2_consult="local"), JOB, None)
        self.assertEqual(plan["sources"], ())
        self.assertEqual(plan["reason"], "no_plan")

    def test_model_tier_is_skipped_at_deadline_zero(self):
        cfg = _llm_cfg(v2_answer_deadline_sec=0)
        plan = V.consult_plan(cfg, JOB, PLAN_FAIL, model_available=True)
        self.assertNotIn("oracle_model", plan["sources"])
        self.assertTrue(plan["model_skipped_deadline_zero"])

    def test_gate_block_removes_remote_at_enforce(self):
        plan = V.consult_plan(_both(v2_question_postures=["other"]),
                              JOB, PLAN_FAIL,
                              posture_id="named-only",
                              posture_declared=True)
        self.assertEqual(plan["sources"], ("oracle_det",))
        self.assertEqual(plan["reason"], "posture_not_listed")
        self.assertEqual(plan["gate_reason"], "posture_not_listed")

    def test_gate_audit_keeps_remote_and_flags_would_block(self):
        cfg = _both(v2_question_postures=["other"],
                    security={"modes": {"v2_question": "audit"}})
        plan = V.consult_plan(cfg, JOB, PLAN_FAIL,
                              posture_id="named-only",
                              posture_declared=True)
        self.assertIn("remote", plan["sources"])
        self.assertTrue(plan["gate_would_block"])
        self.assertEqual(plan["gate_reason"], "posture_not_listed")

    def test_gate_off_removes_remote(self):
        cfg = _both(security={"modes": {"v2_question": "off"}})
        plan = V.consult_plan(cfg, JOB, PLAN_FAIL)
        self.assertEqual(plan["sources"], ("oracle_det",))
        self.assertEqual(plan["reason"], "v2_question_off")

    def test_plan_never_raises_on_junk(self):
        for cfg, job, plan in ((None, None, None), ("x", [], "y"),
                               (_both(), None, PLAN_FAIL),
                               (_both(), JOB, "junk")):
            out = V.consult_plan(cfg, job, plan)
            self.assertIn(out["reason"], V.CONSULT_REASONS)


# ------------------------------------------------------------ the record text

class ConsultRecordTextTest(unittest.TestCase):
    def test_field_order_is_pinned(self):
        text = V.consult_record_text(
            "both", ("oracle_det", "remote"), "fail", "proceed",
            "both", True, 15)
        self.assertEqual(
            text,
            "v2_consult mode=both sources=det,remote local=fail "
            "remote=proceed outcome=both split=true deadline=15")

    def test_no_sources_reads_none(self):
        text = V.consult_record_text(
            "local", (), "none", "not_asked", "none", False, 0)
        self.assertIn("sources=none", text)
        self.assertIn("split=false", text)

    def test_optional_fields_come_last_in_order(self):
        text = V.consult_record_text(
            "both", ("oracle_det", "oracle_model", "remote"),
            "fail", "proceed", "both", True, 5,
            gate="posture_not_listed", local_model="ok", late=True)
        self.assertTrue(text.endswith(
            "deadline=5 gate=posture_not_listed local_model=ok "
            "late=true"), text)

    def test_text_is_capped(self):
        text = V.consult_record_text(
            "both", ("oracle_det", "remote"), "fail", "proceed",
            "both", True, 30, gate="x" * 900)
        self.assertLessEqual(len(text), 500)


# ------------------------------------------------------------ the seam

class _Send:
    def __init__(self, fail_questions=False):
        self.subjects = []
        self.fail_questions = fail_questions

    def __call__(self, subject, body):
        self.subjects.append(subject)
        if self.fail_questions and " question " in subject:
            raise RuntimeError("hand-off exploded")
        return []

    def asked(self):
        return any(" question " in s for s in self.subjects)


def _run_seam(cfg, job, plan, base_dir, send):
    return runner._v2_before_execute(
        cfg, job, plan, SECRET, "", False, base_dir, send)


class ConsultSeamTest(_Guard):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="hp-q139-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            self.tmp, ignore_errors=True))

    def test_legacy_mode_is_byte_identical_in_shape(self):
        cfg = _cfg()
        _file_answer(self.tmp, cfg, JOB, "proceed")
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertEqual([s["kind"] for s in segs],
                         ["determination", "answer"])
        self.assertEqual(_consult_segments(segs), [])
        self.assertEqual(_audit_rows(self.tmp), [])

    def test_legacy_clean_pass_still_asks(self):
        cfg = _cfg()
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_CLEAN, self.tmp, send)
        self.assertTrue(send.asked())
        self.assertEqual([s["kind"] for s in segs], ["local_default"])

    def test_both_split_is_recorded_not_voted(self):
        cfg = _both()
        _file_answer(self.tmp, cfg, JOB, "proceed")
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        consult = _consult_segments(segs)
        self.assertEqual(len(consult), 1)
        self.assertEqual(
            consult[0]["text"],
            "v2_consult mode=both sources=det,remote local=fail "
            "remote=proceed outcome=both split=true deadline=0")
        self.assertEqual(consult[0]["by"], "runner")
        rows = _audit_rows(self.tmp)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "both")
        self.assertEqual(rows[0]["reason"], "both_deterministic")
        self.assertEqual(rows[0]["job_id"], "cj1")
        self.assertEqual(rows[0]["detail"], consult[0]["text"])

    def test_both_free_text_answer_is_stated_and_preserved(self):
        cfg = _both()
        distinctive = "ZQX-hold-on-a-moment-987"
        _file_answer(self.tmp, cfg, JOB, distinctive)
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        answers = [s for s in segs if s["kind"] == "answer"]
        self.assertEqual(answers[0]["text"], distinctive)
        consult = _consult_segments(segs)[0]
        self.assertIn("remote=stated", consult["text"])
        self.assertIn("split=false", consult["text"])
        # The answer text never reaches the audit record.
        self.assertNotIn(distinctive, json.dumps(_audit_rows(self.tmp)))
        self.assertNotIn(distinctive, consult["text"])

    def test_both_no_answer_at_deadline_zero(self):
        cfg = _both()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        self.assertIn("local_default", [s["kind"] for s in segs])
        consult = _consult_segments(segs)[0]
        self.assertIn("remote=no_answer", consult["text"])
        self.assertIn("outcome=local_only", consult["text"])
        rows = _audit_rows(self.tmp)
        self.assertEqual(rows[0]["reason"], "deadline_zero_remote")
        self.assertEqual(rows[0]["decision"], "local_only")

    def test_both_no_answer_inside_a_wait(self):
        cfg = _both(v2_answer_deadline_sec=1)
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        consult = _consult_segments(segs)[0]
        self.assertIn("remote=no_answer", consult["text"])
        rows = _audit_rows(self.tmp)
        self.assertEqual(rows[0]["reason"], "no_answer")

    def test_both_clean_pass_emits_no_record(self):
        cfg = _both()
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_CLEAN, self.tmp, send)
        self.assertEqual(segs, [])
        self.assertFalse(send.asked())
        self.assertEqual(_audit_rows(self.tmp), [])

    def test_v2_off_with_both_emits_no_record(self):
        # Q141: version 2 off routes to v2_off -- "consults
        # nothing" -- so the seam must not record a consult
        # that never happened: no segments, nothing sent, no
        # audit row, whatever the chosen consult mode says.
        cfg = _cfg(protocol_v2=False, v2_consult="both")
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertEqual(segs, [])
        self.assertEqual(send.subjects, [])
        self.assertEqual(_audit_rows(self.tmp), [])

    def test_v2_off_with_local_emits_no_record(self):
        cfg = _cfg(protocol_v2=False, v2_consult="local")
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertEqual(segs, [])
        self.assertEqual(send.subjects, [])
        self.assertEqual(_audit_rows(self.tmp), [])

    def test_answer_only_with_both_emits_no_record(self):
        # An answer-only process routes to v2_off too: it
        # answers questions, it does not consult on jobs it
        # will never execute.
        cfg = _both(answer_only=True)
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertEqual(segs, [])
        self.assertEqual(send.subjects, [])
        self.assertEqual(_audit_rows(self.tmp), [])

    def test_v2_off_sweep_emits_no_record_in_any_combination(self):
        # The shotgun sweep over the same combinations the
        # routing family sweeps: every mode, every shape of
        # "protocol not exactly on", answer-only or not -- and
        # answer-only with the protocol on -- routes to
        # v2_off, and the seam records nothing for any of
        # them.
        for mode in ("remote", "both", "local"):
            for off in (False, None, 1, "yes", "absent"):
                for answer_only in (False, True):
                    with self.subTest(mode=mode, protocol_v2=off,
                                      answer_only=answer_only):
                        cfg = {"oracle_mode": "deterministic",
                               "v2_answer_deadline_sec": 0,
                               "v2_consult": mode,
                               "answer_only": answer_only}
                        if off != "absent":
                            cfg["protocol_v2"] = off
                        base = tempfile.mkdtemp(dir=self.tmp)
                        send = _Send()
                        segs = _run_seam(cfg, JOB, PLAN_FAIL, base,
                                         send)
                        self.assertEqual(segs, [])
                        self.assertEqual(send.subjects, [])
                        self.assertEqual(_audit_rows(base), [])
            with self.subTest(mode=mode, protocol_v2=True,
                              answer_only=True):
                base = tempfile.mkdtemp(dir=self.tmp)
                send = _Send()
                segs = _run_seam(
                    _cfg(v2_consult=mode, answer_only=True),
                    JOB, PLAN_FAIL, base, send)
                self.assertEqual(segs, [])
                self.assertEqual(send.subjects, [])
                self.assertEqual(_audit_rows(base), [])

    def test_protocol_module_without_consult_surface_is_legacy(self):
        # Q142: the dispatch head must answer for whatever
        # protocol module it is handed. A stand-in carrying
        # only the legacy surface (outbound_for + segment),
        # or a consult_mode_of that is not callable, reads as
        # the legacy remote path it always was -- it must not
        # raise AttributeError out of the seam.
        outbound = lambda cfg, job, plan: [  # noqa: E731
            ("subj", {"type": "determination",
                      "why": "because", "msg_id": "m1"})]
        segment = lambda *a: ("segment", a)  # noqa: E731
        shapes = (
            types.SimpleNamespace(outbound_for=outbound,
                                  segment=segment),
            types.SimpleNamespace(consult_mode_of="both",
                                  outbound_for=outbound,
                                  segment=segment),
        )
        for fake in shapes:
            with self.subTest(fake=sorted(vars(fake))):
                with mock.patch.object(runner, "_protocol_v2",
                                       fake), \
                        mock.patch.object(runner, "_seal_reply",
                                          lambda *a: "sealed"):
                    segs = runner._v2_before_execute(
                        {}, JOB, PLAN_FAIL, SECRET, "", False,
                        self.tmp, _Send())
                self.assertEqual(
                    segs, [("segment", ("runner", "determination",
                                        "because"))])

    def test_both_no_plan_remote_alone(self):
        cfg = _both()
        _file_answer(self.tmp, cfg, JOB, "looks fine")
        segs = _run_seam(cfg, JOB, None, self.tmp, _Send())
        consult = _consult_segments(segs)[0]
        self.assertIn("sources=remote", consult["text"])
        self.assertIn("local=none", consult["text"])
        self.assertIn("outcome=remote_only", consult["text"])
        rows = _audit_rows(self.tmp)
        self.assertEqual(rows[0]["reason"], "no_plan")

    def test_local_mode_records_without_asking(self):
        cfg = _cfg(v2_consult="local")
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertFalse(send.asked())
        consult = _consult_segments(segs)[0]
        self.assertIn("mode=local", consult["text"])
        self.assertIn("remote=not_asked", consult["text"])
        self.assertIn("outcome=local_only", consult["text"])

    def test_send_failure_degrades_to_local_only(self):
        cfg = _both()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp,
                         _Send(fail_questions=True))
        consult = _consult_segments(segs)[0]
        self.assertIn("remote=send_failed", consult["text"])
        self.assertIn("outcome=local_only", consult["text"])
        rows = _audit_rows(self.tmp)
        self.assertEqual(rows[0]["reason"], "send_failed")
        # The determination still rode out before the failure.
        self.assertIn("determination", [s["kind"] for s in segs])

    def test_gate_block_at_enforce_asks_nothing(self):
        runner._set_posture_resolution(True, "bookend", STAMP)
        cfg = _both(v2_question_postures=["other-posture"])
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertFalse(send.asked())
        consult = _consult_segments(segs)[0]
        self.assertIn("gate=posture_not_listed", consult["text"])
        self.assertIn("remote=not_asked", consult["text"])

    def test_gate_audit_asks_and_records_would_block(self):
        runner._set_posture_resolution(True, "bookend", STAMP)
        cfg = _both(v2_question_postures=["other-posture"],
                    security={"modes": {"v2_question": "audit"}})
        _file_answer(self.tmp, cfg, JOB, "proceed")
        send = _Send()
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, send)
        self.assertTrue(send.asked())
        consult = _consult_segments(segs)[0]
        self.assertIn("gate=audit_would_block:posture_not_listed",
                      consult["text"])

    def test_model_tier_engaged_in_llm_mode(self):
        cfg = _llm_cfg()
        _file_answer(self.tmp, cfg, JOB, "proceed")
        with mock.patch.object(runner, "_opinion_model_note",
                               return_value="model-formed words"):
            segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        consult = _consult_segments(segs)[0]
        self.assertEqual(
            consult["text"],
            "v2_consult mode=both sources=det,model,remote "
            "local=fail remote=proceed outcome=both split=true "
            "deadline=5 local_model=ok")
        # The model's text is not duplicated into the record.
        self.assertNotIn("model-formed words", consult["text"])
        self.assertNotIn("model-formed words",
                         json.dumps(_audit_rows(self.tmp)))

    def test_model_tier_skipped_at_deadline_zero(self):
        cfg = _llm_cfg(v2_answer_deadline_sec=0)
        _file_answer(self.tmp, cfg, JOB, "proceed")
        with mock.patch.object(runner, "_opinion_model_note",
                               return_value="unused") as note:
            segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        note.assert_not_called()
        consult = _consult_segments(segs)[0]
        self.assertIn("sources=det,remote", consult["text"])
        self.assertIn("local_model=skipped_deadline_zero",
                      consult["text"])

    def test_model_tier_error_degrades_to_tier1(self):
        cfg = _llm_cfg()
        _file_answer(self.tmp, cfg, JOB, "proceed")
        with mock.patch.object(runner, "_opinion_model_note",
                               side_effect=RuntimeError("model died")):
            segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        consult = _consult_segments(segs)[0]
        self.assertIn("local_model=error", consult["text"])
        self.assertIn("local=fail", consult["text"])

    def test_late_answer_is_recorded_as_late(self):
        cfg = _both()
        q = V.question_for(cfg, JOB)
        # An answer whose receive stamp lands past the deadline
        # (plus the one-second grace) reads as late beside the
        # local default at deadline 0.
        V.store_answer(self.tmp, V.answer_for(q, "proceed"))
        path = os.path.join(self.tmp, "v2", "answers",
                            q["msg_id"] + ".json")
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["received_at"] = rec["received_at"] + 10
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        segs = _run_seam(cfg, JOB, PLAN_FAIL, self.tmp, _Send())
        self.assertIn("late_answer", [s["kind"] for s in segs])
        consult = _consult_segments(segs)[0]
        self.assertIn("late=true", consult["text"])
        self.assertIn("remote=no_answer", consult["text"])

    def test_seam_never_raises_on_a_job_without_an_id(self):
        cfg = _both()
        segs = _run_seam(cfg, {"kind": "exec"}, PLAN_FAIL,
                         self.tmp, _Send())
        self.assertIsInstance(segs, list)

    def test_seam_does_not_mutate_job_or_plan(self):
        cfg = _both()
        job = dict(JOB)
        plan = json.loads(json.dumps(PLAN_FAIL))
        _run_seam(cfg, job, plan, self.tmp, _Send())
        self.assertEqual(job, JOB)
        self.assertEqual(plan, PLAN_FAIL)


# ------------------------------------------------------------ startup

def _write_posture_files(d):
    reg = os.path.join(d, "registry.json")
    tag = os.path.join(d, "tagging.json")
    with open(reg, "w", encoding="utf-8") as fh:
        json.dump(REGISTRY, fh)
    with open(tag, "w", encoding="utf-8") as fh:
        json.dump(TAGGING, fh)
    return {"registry": reg, "tagging": tag, "project": "bookend"}


class RunnerValidateTest(_Guard):
    def test_posture_id_comes_from_the_startup_stamp(self):
        runner._set_posture_resolution(True, "bookend", STAMP)
        self.assertEqual(runner._posture_id(), "named-only")
        runner._set_posture_resolution(True, "ghost", None)
        self.assertIsNone(runner._posture_id())
        runner._set_posture_resolution(False, "", None)
        self.assertIsNone(runner._posture_id())

    def test_validate_passes_a_plain_config(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(runner._validate_v2_consult({}, d))
            self.assertIsNone(runner._validate_v2_consult(
                {"v2_consult": "both"}, d))

    def test_validate_resolves_ids_against_the_registry(self):
        with tempfile.TemporaryDirectory() as d:
            block = _write_posture_files(d)
            cfg = {"disclosure_posture": block,
                   "v2_question_postures": ["named-only"]}
            self.assertIsNone(runner._validate_v2_consult(cfg, d))
            cfg["v2_question_postures"] = ["never-declared"]
            with self.assertRaises(RuntimeError):
                runner._validate_v2_consult(cfg, d)
            cfg["v2_question_postures"] = ["old-posture"]
            with self.assertRaises(RuntimeError):
                runner._validate_v2_consult(cfg, d)


class StartupGateTest(_Guard):
    def _main(self, d, cfg):
        cfg_path = os.path.join(d, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        out, err = io.StringIO(), io.StringIO()
        argv = ["runner", "--config", cfg_path, "--audit-report"]
        old = (runner._LOG_MINUTE, runner._LOG_COUNT,
               runner._LOG_DROPPED)
        runner._LOG_MINUTE = 0.0
        runner._LOG_COUNT = 0
        runner._LOG_DROPPED = 0
        try:
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(out), redirect_stderr(err):
                    rc = runner.main()
        finally:
            (runner._LOG_MINUTE, runner._LOG_COUNT,
             runner._LOG_DROPPED) = old
        return rc, out.getvalue(), err.getvalue()

    def _cfg(self, d, **extra):
        cfg = {"base_dir": d,
               "security": {"modes": {"confinement": "off",
                                      "job_user": "off",
                                      "audience": "off"}}}
        cfg.update(extra)
        return cfg

    def test_invalid_consult_mode_refuses_startup(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _out, err = self._main(
                d, self._cfg(d, v2_consult="sideways"))
            self.assertEqual(rc, 2)
            self.assertIn("v2_consult", err)

    def test_both_mode_starts_and_announces_once(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _err = self._main(
                d, self._cfg(d, v2_consult="both"))
            self.assertEqual(rc, 0)
            self.assertIn("version 2 consult: mode both", out)

    def test_remote_mode_announces_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _err = self._main(d, self._cfg(d))
            self.assertEqual(rc, 0)
            self.assertNotIn("version 2 consult", out)

    def test_allowlist_without_a_block_refuses_startup(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _out, err = self._main(
                d, self._cfg(d, v2_question_postures=["named-only"]))
            self.assertEqual(rc, 2)
            self.assertIn("v2_question_postures", err)

    def test_allowlist_with_a_block_starts(self):
        with tempfile.TemporaryDirectory() as d:
            block = _write_posture_files(d)
            rc, _out, _err = self._main(d, self._cfg(
                d, disclosure_posture=block,
                v2_question_postures=["named-only"]))
            self.assertEqual(rc, 0)

    def test_allowlist_unknown_id_refuses_startup(self):
        with tempfile.TemporaryDirectory() as d:
            block = _write_posture_files(d)
            rc, _out, err = self._main(d, self._cfg(
                d, disclosure_posture=block,
                v2_question_postures=["never-declared"]))
            self.assertEqual(rc, 2)
            self.assertIn("never-declared", err)

    def test_bad_v2_question_mode_refuses_startup(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._cfg(d)
            cfg["security"]["modes"]["v2_question"] = "loud"
            rc, _out, err = self._main(d, cfg)
            self.assertEqual(rc, 2)
            self.assertIn("v2_question", err)


# ------------------------------------------------------------ execution invariance

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP:
    def __init__(self, raws=()):
        self.raws = list(raws)

    def search(self, *a):
        ids = [str(i + 1).encode() for i in range(len(self.raws))]
        return "OK", [b" ".join(ids)] if ids else [b""]

    def fetch(self, num, what):
        idx = int(num) - 1
        if 0 <= idx < len(self.raws):
            return "OK", [(None, self.raws[idx])]
        return "NO", None

    def store(self, *a):
        return "OK", None

    def expunge(self):
        return "OK", None

    def logout(self):
        return "OK", None


class _SMTP:
    def send_message(self, *a, **k):
        return {}

    def quit(self):
        pass


class _Opts:
    workers = 1
    once = True
    dry_run = False
    verbose = False
    no_send = False
    inspect = False
    oracle = False
    pdb = False


@contextlib.contextmanager
def _captured_log():
    old_file = runner._LOG_FILE
    old_minute, old_count = runner._LOG_MINUTE, runner._LOG_COUNT
    runner._LOG_FILE = None
    runner._LOG_MINUTE = 0.0
    runner._LOG_COUNT = 0
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            yield buf
    finally:
        runner._LOG_FILE = old_file
        runner._LOG_MINUTE, runner._LOG_COUNT = old_minute, old_count


class ExecutionInvarianceTest(_Guard):
    def _run(self, d, cfg_extra):
        from runner.wire import jobcrypto
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET,
               "security": {"modes": {"confinement": "off",
                                      "job_user": "off",
                                      "audience": "off"}},
               "protocol_v2": True,
               "oracle_mode": "deterministic",
               "v2_answer_deadline_sec": 0}
        cfg.update(cfg_extra)
        # A script naming a tool this box does not have is a
        # tier-1 finding with no repair: the plan is not a
        # clean pass (so the decision point has something to
        # record), and the job itself runs exactly as sent in
        # both modes alike.
        job = {"v": 1, "type": "job", "job_id": "inv1",
               "issued_at": _now(), "kind": "exec",
               "script": "hp-no-such-tool-xyz 2>/dev/null; "
                         "echo hp-consult-ok",
               "interpreter": ["/bin/sh"]}
        body = jobcrypto.encrypt_body(
            runner.sign_payload(job, SECRET), SECRET,
            job_id="inv1", key_id="", sign=runner.sign_payload)
        raw = _mail("[HOMING-PIGEON] job inv1", body)
        sent = []

        def fake_send(smtp, c, subject, b, to=None):
            sent.append((subject, b))

        with mock.patch.object(runner, "send_mail", fake_send):
            with _captured_log():
                runner.handle_mail(
                    cfg, _IMAP(), _SMTP(), 7, raw, d, {},
                    runner.build_secrets(cfg), _Opts())
        results = [b for s, b in sent if " result " in s]
        self.assertEqual(len(results), 1, sent)
        payload = runner.verify_body_keyed(
            results[0], runner.build_secrets(cfg))
        if isinstance(payload, tuple):
            payload = payload[0]
        if jobcrypto.is_envelope(payload):
            inner = jobcrypto.decrypt_body(payload, SECRET, "inv1", "")
            payload = runner.verify_body(inner, SECRET)
        return payload

    def test_the_consult_never_changes_what_runs(self):
        with tempfile.TemporaryDirectory() as d1, \
                tempfile.TemporaryDirectory() as d2:
            legacy = self._run(d1, {})
            both = self._run(d2, {"v2_consult": "both"})
        for result in (legacy, both):
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("hp-consult-ok", result["stdout"])
        self.assertNotIn("consult",
                         [s["kind"] for s in legacy.get("context", [])])
        self.assertIn("consult",
                      [s["kind"] for s in both.get("context", [])])


# ------------------------------------------------------------ fuzz families

_BOOKEND_CORES = ["ZQX proceed", "ZQX hold on", "ZQX"]


def _bookended(core):
    out = []
    symbols = string.punctuation + " \t\r\n\x00"
    for sym in symbols:
        out.append(sym + core + sym)
        out.append(sym * 10 + core)
        out.append(core + sym * 10)
        out.append(core[:3] + sym * 10 + core[3:])
    out.append(symbols + core + symbols)
    out.append("!@#$%^&*()")
    out.append("\x00\t\r\n")
    return out


class ConsultFuzzTest(_Guard):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="hp-q139-fuzz-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            self.tmp, ignore_errors=True))

    def test_routing_fuzz_never_raises_and_stays_in_vocabulary(self):
        rng = random.Random(139)
        modes = [None, "remote", "both", "local", "junk", 3, True]
        kinds = ["exec", "ping", "query", None, 5]
        plans = [None, PLAN_FAIL, PLAN_CLEAN, PLAN_REPAIR, PLAN_OFF,
                 "junk", {}]
        for _ in range(400):
            cfg = {"protocol_v2": rng.choice([True, False, None]),
                   "oracle_mode": rng.choice(
                       ["deterministic", "llm", None]),
                   "v2_answer_deadline_sec": rng.choice(
                       [0, 1, 30, 99, -1, "x", None])}
            mode = rng.choice(modes)
            if mode is not None:
                cfg["v2_consult"] = mode
            if rng.random() < 0.3:
                cfg["v2_question_postures"] = rng.choice(
                    [[], ["named-only"], ["other"], "junk"])
            job = {"job_id": "fz", "kind": rng.choice(kinds)}
            plan = V.consult_plan(
                cfg, job, rng.choice(plans),
                posture_id=rng.choice([None, "named-only", "other"]),
                posture_declared=rng.choice([True, False]),
                model_available=rng.choice([True, False]))
            self.assertIn(plan["mode"], V.CONSULT_MODES)
            self.assertIn(plan["reason"], V.CONSULT_REASONS)
            self.assertTrue(set(plan["sources"]) <= {
                "oracle_det", "oracle_model", "remote"})
            self.assertIn(plan["local_stance"],
                          ("fail", "unknown", "proceed", "none"))

    def test_config_fuzz_refuses_or_accepts_never_crashes(self):
        rng = random.Random(1391)
        pool = [None, True, 0, 1, "", "both", "remote", "local",
                "junk", [], ["named-only"], ["named-only", 3],
                ["a", "a"], {}, {"x": 1}, "x" * 600,
                "\x00both\x00", "🔑", ["🔑"]]
        for _ in range(300):
            cfg = {}
            if rng.random() < 0.7:
                cfg["v2_consult"] = rng.choice(pool)
            if rng.random() < 0.7:
                cfg["v2_question_postures"] = rng.choice(pool)
            if rng.random() < 0.5:
                cfg["disclosure_posture"] = rng.choice(
                    [{}, {"registry": "r"}, "x", None])
            try:
                V.validate_consult_config(
                    cfg, active_ids={"named-only"},
                    retired_ids={"old-posture"})
            except RuntimeError:
                pass

    def test_answer_text_fuzz_is_data_and_never_leaks_to_the_record(self):
        cfg = _both()
        for i, core in enumerate(_BOOKEND_CORES):
            for j, text in enumerate(_bookended(core)):
                d = os.path.join(self.tmp, "%d-%d" % (i, j))
                os.makedirs(d)
                job = {"job_id": "fz%d-%d" % (i, j), "kind": "exec",
                       "script": "echo hi"}
                q = V.question_for(cfg, job)
                stored = V.answer_for(q, text)
                V.store_answer(d, stored)
                segs = _run_seam(cfg, job, PLAN_FAIL, d, _Send())
                answers = [s for s in segs if s["kind"] == "answer"]
                self.assertEqual(len(answers), 1)
                self.assertEqual(answers[0]["text"],
                                 stored["answer"])
                consult = _consult_segments(segs)[0]
                self.assertLessEqual(len(consult["text"]), 500)
                rows = _audit_rows(d)
                self.assertEqual(len(rows), 1)
                if len(stored["answer"]) > 12:
                    self.assertNotIn(stored["answer"],
                                     rows[0].get("detail", ""))
                    self.assertNotIn(stored["answer"],
                                     consult["text"])

    def test_pump_filed_answer_inside_the_wait_is_timely(self):
        cfg = _both(v2_answer_deadline_sec=5)
        q = V.question_for(cfg, JOB)
        state = {"filed": False}

        def pump():
            if not state["filed"]:
                state["filed"] = True
                V.store_answer(self.tmp, V.answer_for(q, "proceed"))

        segs = runner._v2_before_execute(
            cfg, JOB, PLAN_FAIL, SECRET, "", False, self.tmp,
            _Send(), pump=pump)
        kinds = [s["kind"] for s in segs]
        self.assertIn("answer", kinds)
        self.assertNotIn("late_answer", kinds)
        consult = _consult_segments(segs)[0]
        self.assertIn("remote=proceed", consult["text"])


if __name__ == "__main__":
    unittest.main()
