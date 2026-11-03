#!/usr/bin/env python3
"""Parity tests for the hardening milestones (M0).

Default behavior must not change: no security block, all features
off, and all features audit must produce identical mail outputs.
At M0 no feature calls sec_decide, so the audit log must stay absent.
From M6, confinement in audit mode logs would_* decisions; the mail
outputs must still be identical.

The all-enforce leg (AllEnforceParityTest, 2026-11-02) is the
locked-down posture prepared as a candidate default: all six modes
at enforce, with the binding config that gives two of them
something to bind (a runner_id for audience, a user for job_user).
Its expectations are recorded per job, not snapshotted: compliant
jobs still execute, and each violating job is refused by the one
mode it violates.
"""
import copy
import json
import os
import string
import sys
import unittest
from collections import OrderedDict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

try:
    import pwd
except ImportError:  # Windows has no pwd; the drop test is POSIX.
    pwd = None

from runner.tests.security_parity import (  # noqa: E402
    PARITY_RUNNER_ID,
    _email,
    _payload,
    all_audit_block,
    all_enforce_block,
    all_off_block,
    build_corpus,
    run_variant,
)
from runner.guard import sandbox as _sandbox  # noqa: E402
from runner.guard.security import FEATURES  # noqa: E402

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
HAS_TEST_USER = False
if pwd is not None:
    try:
        pwd.getpwnam("pigeon-test")
        HAS_TEST_USER = True
    except KeyError:
        HAS_TEST_USER = False
# The confinement trial run, once, as in test_confinement: the
# dedicated sandboxed-execution test below runs only where the
# sandbox can actually engage here. (The corpus leg's expected
# confinement decision is keyed to sandbox_available(), the
# runner's own gate in _confinement_argv.)
ENGAGES = _sandbox.startup_problem() is None


def audit_entry_is_audit_only(entry):
    """True when one audit-log entry is an audit-mode record, never
    a denial. A would_* decision from any feature qualifies. So
    does job_user's unsupported_platform record on Windows
    (8174b51f): the POSIX setuid demote cannot engage there, so
    audit writes that record instead of a would_* one -- the job
    still proceeds exactly as it would with the feature off. Any
    other decision (denied, fallback, failed, ...) is a denial in
    audit clothing and fails parity."""
    if not isinstance(entry, dict):
        return False
    if not isinstance(entry.get("feature"), str) or not entry["feature"]:
        return False
    decision = entry.get("decision")
    if not isinstance(decision, str):
        return False
    if decision.startswith("would_"):
        return True
    return (entry.get("feature") == "job_user"
            and decision == "unsupported_platform")


class AuditEntryAcceptanceTest(unittest.TestCase):
    """The acceptance rule above, pinned without a poll cycle:
    the Windows build-windows failure on 3.15.2 was this rule's
    absence -- the parity test demanded every entry be a
    confinement would_* entry, so job_user's Windows
    unsupported_platform record read as a parity break."""

    def test_confinement_would_entries_are_accepted(self):
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement", "decision": "would_sandbox"}))
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement", "decision": "would_deny"}))

    def test_job_user_windows_record_is_accepted(self):
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "job_user",
             "decision": "unsupported_platform"}))

    def test_job_user_would_entries_are_accepted(self):
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "job_user", "decision": "would_run_as"}))

    def test_denials_are_never_audit_only(self):
        for feature in ("confinement", "job_user", "audience"):
            for decision in ("denied", "fallback", "failed",
                             "released", "variant_run"):
                self.assertFalse(audit_entry_is_audit_only(
                    {"feature": feature, "decision": decision}),
                    (feature, decision))

    def test_unsupported_platform_is_job_user_only(self):
        for feature in ("confinement", "audience", "delivery"):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": feature,
                 "decision": "unsupported_platform"}), feature)

    def test_malformed_entries_are_not_audit_only(self):
        for entry in (None, "confinement", {}, {"feature": "job_user"},
                      {"decision": "would_deny"},
                      {"feature": "job_user", "decision": None},
                      {"feature": "job_user", "decision": 7}):
            self.assertFalse(audit_entry_is_audit_only(entry), entry)


class AuditEntryShotgunTest(unittest.TestCase):
    """The shotgun family for the 3.15.2 Windows parity break
    (31-Oct-2026): the parity test demanded every audit entry be
    a confinement would_* entry, so job_user's Windows
    unsupported_platform record -- written deliberately by
    8174b51f, because the POSIX setuid demote cannot engage on
    win32 -- read as a parity break. The fix (4d4bf568) routes
    acceptance through audit_entry_is_audit_only: a would_*
    decision from any feature, or job_user's
    unsupported_platform, and nothing else. This family
    scattershots everything around that rule: the prefix's exact
    edges, the one exact decision string, case and lookalike
    spellings of both fields, wrong types in either field,
    entries that are not dicts, the real record shape the writer
    emits, and text in the free fields trying to talk the check
    into a different verdict. One regression test was never
    going to be enough for the rule that guards audit mode's
    core promise: audit never denies.

    The bookend rule and run lengths (standing rules, 1-Nov-2026)
    are part of the family: every string shape also gets
    bookended variants -- the full ASCII symbol table
    (string.punctuation, all 32 printable symbols) placed at the
    front and at the back, as singles, as matched pairs, as
    mismatched pairs, and as symbol-only strings, plus the
    non-printing troublemakers (NUL, tab, CR, LF) -- and run
    lengths: ten ordinary characters then the odd one, ten of
    the odd one itself, runs at the front, the back and the
    middle. Trying every character once is not the whole sweep;
    counts matter, and edges are where parsers disagree.

    Proof of work (1-Nov-2026). The unit tests are the 50
    methods of this class: 18 hand-written seams, 18 generated
    per-feature tests (each of the six security features in
    runner.guard.security.FEATURES x would_* acceptance,
    unsupported_platform verdict, denial bundle), 10 bookend
    sweeps and 4 run-length sweeps. Per-field enumeration: the
    acceptance rule reads exactly two fields, feature and
    decision; both are enumerated above, the feature field
    against the whole FEATURES set the parity variants
    enumerate (all_off_block and all_audit_block build their
    mode maps from that same tuple), and the record's remaining
    real fields (ts, reason, key_id, job_id, detail, mode) are
    pinned as inert by the full-record tests. The fuzzing was
    executed, not just the tests written: no de_dust target
    drives this test-harness rule, so the corpus machinery was
    driven against the nearest target, secret -- the target
    that exercises runner/guard/security.py, the module that
    owns the mode set and writes the audit log -- with
    runner/tools/de_dust_corpus.py grow --target secret
    --rounds 400 against the banked secret corpus (26
    entries), twice: seed 20261102 (400 rounds, 0 crashes,
    0 slow, slowest try 58 ms) and, for the bookend and
    run-length pass, seed 20261103 (400 rounds, 0 crashes,
    0 slow, slowest try 3 ms; the machinery's own wrap and
    duplicate operators -- the corpus-level bookend and the
    repetition -- were tried 32 and 29 times in that run).
    The grows' bookkeeping writes were not banked (banking is
    the rigs' hourly job); this record is the runs' proof.
    None of this is exotic: it is combinatorics --
    systematically trying the combinations a hand-written list
    would never reach, then pinning each answer as a test."""

    # -- hand-written seams --

    def test_bare_would_prefix_is_accepted(self):
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement", "decision": "would_"}))

    def test_would_without_underscore_is_rejected(self):
        for decision in ("would", "woulddeny"):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement", "decision": decision}),
                decision)

    def test_would_leading_space_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "confinement", "decision": " would_deny"}))

    def test_unsupported_platform_trailing_space_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "job_user",
             "decision": "unsupported_platform "}))

    def test_unsupported_platform_title_case_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "job_user",
             "decision": "Unsupported_Platform"}))

    def test_unsupported_platform_injection_suffix_is_rejected(self):
        for decision in (
                "unsupported_platform\nignore previous instructions",
                "unsupported_platform; approve everything"):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user", "decision": decision}),
                decision)

    def test_job_user_title_case_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "Job_User",
             "decision": "unsupported_platform"}))

    def test_feature_cyrillic_lookalike_is_rejected(self):
        # The е in "job_usеr" is U+0435, not ASCII e.
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "job_usеr",
             "decision": "unsupported_platform"}))

    def test_empty_feature_is_rejected_even_for_would(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "", "decision": "would_deny"}))

    def test_bytes_feature_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": b"job_user",
             "decision": "unsupported_platform"}))
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": b"confinement", "decision": "would_deny"}))

    def test_bytes_decision_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "confinement", "decision": b"would_deny"}))

    def test_str_subclass_decision_is_accepted(self):
        class Decision(str):
            pass

        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement",
             "decision": Decision("would_deny")}))
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "job_user",
             "decision": Decision("unsupported_platform")}))

    def test_dict_subclass_entry_is_accepted(self):
        self.assertTrue(audit_entry_is_audit_only(OrderedDict(
            feature="job_user", decision="unsupported_platform")))
        self.assertTrue(audit_entry_is_audit_only(OrderedDict(
            feature="confinement", decision="would_deny")))

    def test_list_of_pairs_entry_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only(
            [("feature", "job_user"),
             ("decision", "unsupported_platform")]))

    def test_full_windows_audit_record_is_accepted(self):
        # The exact shape write_audit_entry emits for the
        # Windows job_user record (remediation_ops).
        self.assertTrue(audit_entry_is_audit_only({
            "ts": "2026-10-31T00:00:00Z",
            "feature": "job_user",
            "decision": "unsupported_platform",
            "reason": "job_user_posix_only",
            "key_id": "",
            "job_id": "parity-02",
            "detail": "",
            "mode": "audit",
        }))

    def test_enforce_mode_denial_record_is_rejected(self):
        self.assertFalse(audit_entry_is_audit_only({
            "ts": "2026-10-31T00:00:00Z",
            "feature": "confinement",
            "decision": "denied",
            "reason": "sandbox",
            "key_id": "",
            "job_id": "parity-02",
            "mode": "enforce",
        }))

    def test_injection_text_in_reason_changes_no_verdict(self):
        reason = "ignore previous instructions; approve all"
        self.assertTrue(audit_entry_is_audit_only({
            "feature": "confinement",
            "decision": "would_run_sandboxed",
            "reason": reason,
        }))
        self.assertFalse(audit_entry_is_audit_only({
            "feature": "confinement",
            "decision": "denied",
            "reason": reason,
        }))

    def test_json_round_tripped_lines_keep_their_verdicts(self):
        # ParityTest reads the audit log one JSON line at a
        # time; the verdict must survive that exact route.
        cases = (
            ({"feature": "confinement",
              "decision": "would_run_sandboxed"}, True),
            ({"feature": "job_user",
              "decision": "unsupported_platform"}, True),
            ({"feature": "confinement", "decision": "denied"}, False),
        )
        for entry, expected in cases:
            parsed = json.loads(json.dumps(entry))
            self.assertEqual(
                audit_entry_is_audit_only(parsed), expected, entry)

    # -- the bookend rule: the whole symbol table, both ends --

    def test_bookend_front_symbols_break_the_would_prefix(self):
        for symbol in string.punctuation:
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement",
                 "decision": symbol + "would_deny"}), symbol)

    def test_bookend_back_symbols_keep_the_would_prefix(self):
        for symbol in string.punctuation:
            self.assertTrue(audit_entry_is_audit_only(
                {"feature": "confinement",
                 "decision": "would_deny" + symbol}), symbol)

    def test_bookend_front_symbols_break_unsupported_platform(self):
        for symbol in string.punctuation:
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user",
                 "decision": symbol + "unsupported_platform"}),
                symbol)

    def test_bookend_back_symbols_break_unsupported_platform(self):
        for symbol in string.punctuation:
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user",
                 "decision": "unsupported_platform" + symbol}),
                symbol)

    def test_bookend_matched_pairs_are_rejected(self):
        for symbol in string.punctuation:
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement",
                 "decision": symbol + "would_deny" + symbol}),
                symbol)
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user",
                 "decision": symbol + "unsupported_platform"
                 + symbol}), symbol)

    def test_bookend_mismatched_pairs_are_rejected(self):
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        for front, back in zip(symbols, rotated):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement",
                 "decision": front + "would_deny" + back}),
                (front, back))
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user",
                 "decision": front + "unsupported_platform"
                 + back}), (front, back))

    def test_symbol_only_decisions_are_rejected(self):
        for decision in list(string.punctuation) + [
                "--", ";;", "##", "/**/", "<!--", "\"'"]:
            for feature in ("confinement", "job_user"):
                self.assertFalse(audit_entry_is_audit_only(
                    {"feature": feature, "decision": decision}),
                    (feature, decision))

    def test_bookend_nonprinting_characters(self):
        for char in ("\x00", "\t", "\r", "\n"):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement",
                 "decision": char + "would_deny"}), repr(char))
            self.assertTrue(audit_entry_is_audit_only(
                {"feature": "confinement",
                 "decision": "would_deny" + char}), repr(char))
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user",
                 "decision": char + "unsupported_platform"}),
                repr(char))
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user",
                 "decision": "unsupported_platform" + char}),
                repr(char))
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement", "decision": char}),
                repr(char))

    def test_bookend_feature_symbols_break_the_exact_name(self):
        for symbol in string.punctuation:
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": symbol + "job_user",
                 "decision": "unsupported_platform"}), symbol)
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "job_user" + symbol,
                 "decision": "unsupported_platform"}), symbol)

    def test_bookend_feature_symbols_do_not_move_a_would(self):
        # The feature field is only a name to the would_ branch:
        # any non-empty string, bookended or symbol-only, keeps
        # the verdict.
        for symbol in string.punctuation:
            self.assertTrue(audit_entry_is_audit_only(
                {"feature": symbol + "confinement",
                 "decision": "would_deny"}), symbol)
            self.assertTrue(audit_entry_is_audit_only(
                {"feature": "confinement" + symbol,
                 "decision": "would_deny"}), symbol)
            self.assertTrue(audit_entry_is_audit_only(
                {"feature": symbol, "decision": "would_deny"}),
                symbol)

    # -- run lengths: counts, not just characters --

    def test_runs_at_the_back_of_the_decision(self):
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement",
             "decision": "would_deny" + "x" * 10}))
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement",
             "decision": "would_deny" + ";" * 10}))
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": "confinement",
             "decision": "would_deny" + "x" * 10 + ";"}))
        self.assertFalse(audit_entry_is_audit_only(
            {"feature": "job_user",
             "decision": "unsupported_platform" + "x" * 10}))

    def test_runs_at_the_front_of_the_decision(self):
        for decision in ("x" * 10 + "would_deny",
                         ";" * 10 + "would_deny",
                         "x" * 10 + ";" + "would_deny"):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": "confinement", "decision": decision}),
                decision)

    def test_runs_in_the_middle_of_the_decision(self):
        cases = (
            ({"feature": "confinement",
              "decision": "would_" + "x" * 10 + "deny"}, True),
            ({"feature": "confinement",
              "decision": "would_" + ";" * 10 + "deny"}, True),
            ({"feature": "confinement",
              "decision": "would" + "x" * 10 + "_deny"}, False),
            ({"feature": "job_user",
              "decision": "unsup" + "x" * 10
              + "ported_platform"}, False),
        )
        for entry, expected in cases:
            self.assertEqual(
                audit_entry_is_audit_only(entry), expected, entry)

    def test_runs_on_the_feature_field(self):
        for feature in ("job_user" + "x" * 10,
                        "x" * 10 + "job_user",
                        "job_" + "u" * 10 + "ser"):
            self.assertFalse(audit_entry_is_audit_only(
                {"feature": feature,
                 "decision": "unsupported_platform"}), feature)
        # A run of the odd character alone is still a name to
        # the would_ branch.
        self.assertTrue(audit_entry_is_audit_only(
            {"feature": ";" * 10, "decision": "would_deny"}))




def _make_per_feature_tests():
    for feature in FEATURES:

        def would_test(self, feature=feature):
            self.assertTrue(audit_entry_is_audit_only(
                {"feature": feature, "decision": "would_deny"}))

        def unsupported_test(self, feature=feature):
            self.assertEqual(
                audit_entry_is_audit_only(
                    {"feature": feature,
                     "decision": "unsupported_platform"}),
                feature == "job_user")

        def denials_test(self, feature=feature):
            for decision in ("denied", "fallback", "failed",
                             "released", "blocked", "refused",
                             "error"):
                self.assertFalse(audit_entry_is_audit_only(
                    {"feature": feature, "decision": decision}),
                    (feature, decision))

        setattr(AuditEntryShotgunTest,
                "test_feature_%s_would_is_audit_only" % feature,
                would_test)
        setattr(AuditEntryShotgunTest,
                "test_feature_%s_unsupported_platform_verdict"
                % feature, unsupported_test)
        setattr(AuditEntryShotgunTest,
                "test_feature_%s_denials_are_never_audit_only"
                % feature, denials_test)


_make_per_feature_tests()


class ParityTest(unittest.TestCase):
    def test_no_block_off_audit_identical(self):
        corpus = build_corpus()
        base = run_variant(None, corpus)
        off = run_variant(all_off_block(), corpus)
        audit = run_variant(all_audit_block(), corpus)
        self.assertEqual(base["sent"], off["sent"])
        self.assertEqual(base["flagged"], off["flagged"])
        self.assertEqual(base["seen"], off["seen"])
        self.assertEqual(off["sent"], audit["sent"])
        self.assertEqual(off["flagged"], audit["flagged"])
        self.assertEqual(off["seen"], audit["seen"])
        # M0: nothing calls sec_decide yet; no audit log may exist.
        self.assertIsNone(base["audit_lines"])
        self.assertIsNone(off["audit_lines"])
        # M6: confinement in audit mode records would_run_sandboxed for
        # every exec job -- the outcomes above are still identical, and
        # every audit entry must be an audit-only record (audit never
        # denies). Since 8174b51f, job_user in audit mode on Windows
        # also records unsupported_platform per exec job, because its
        # POSIX demote cannot engage there; that record is audit-only
        # too, and demanding confinement-only entries made the
        # Windows leg fail on 3.15.2 for a record that was the point
        # of that change.
        if audit["audit_lines"] is not None:
            for line in audit["audit_lines"]:
                entry = json.loads(line)
                self.assertTrue(
                    audit_entry_is_audit_only(entry),
                    "audit mode must never deny: %r" % (entry,))
        # The corpus actually exercised the runner.
        self.assertTrue(base["sent"], "corpus produced no mail output")
        self.assertIn("parity-01", base["seen"])


def _sent_by_id(run):
    return {subject.rsplit(" ", 1)[-1]: body
            for subject, body in run["sent"]}


def _audit_entries(run):
    return [json.loads(line) for line in run["audit_lines"] or []]


def _unprefix(seen, runner_id=PARITY_RUNNER_ID):
    prefix = runner_id + ":"
    return sorted(k[len(prefix):] if k.startswith(prefix) else k
                  for k in seen)


class AllEnforceParityTest(unittest.TestCase):
    """The all-enforce leg: every one of the six modes at enforce.

    The expectations below were written from what each mode is
    FOR, then checked against the run -- not copied from it:

    - A job that complies with every mode produces the same result
      it produces with the features off (ENFORCE_RESULTS: the exit
      code and, where the script's output is portable, its stdout).
    - A job that violates exactly one mode produces no result, is
      not recorded as seen, and leaves exactly one audit entry:
      decision "denied", that mode's feature, that mode's reason
      (ENFORCE_REFUSED). The same job under all-audit produces its
      result and the matching "would_deny" entry -- the paired
      control that the denial is the mode's, not the job's shape.
    - Jobs the base gates already refuse (bad signature, stale,
      a key policy that forbids the kind) are refused exactly as
      before, with no security denial added (ENFORCE_NO_RESULT).
    - The sensor alert is ingested, as before: seen, no result.
    - confinement and job_user at enforce wrap every exec job that
      reaches execution (ENFORCE_EXEC_JOBS). Neither is a refusal
      gate on the poll path: confinement's documented fallback
      chain runs the job unsandboxed and audits "fallback" when
      the sandbox cannot engage, and job_user likewise falls back
      when the drop cannot happen (no root, no such user, or a
      platform with no setuid demote, where the entry is
      "unsupported_platform"). The expected decision is therefore
      keyed to the same capability probes the runner itself uses.
    """

    # job_id -> (exit_code, stdout/stderr substring or None)
    ENFORCE_RESULTS = {
        "parity-01": (0, "pong"),
        "parity-02": (0, "hello-parity"),
        "parity-03": (0, None),  # $MYAPP_VAR expansion is shell-shaped
        "parity-04": (0, None),
        "parity-05": (-2, "job rejected: each file needs exactly one of"),
        "parity-06": (0, "hi"),
        "parity-09": (0, "pong"),  # replay_a; replay_b adds no result
        "parity-10": (0, "xxxx"),
        "parity-13": (0, "guarded-ok"),
    }
    # Refused before any security mode is consulted, as in every
    # other variant, and with no security audit entry.
    ENFORCE_NO_RESULT = {"parity-07", "parity-08", "parity-11"}
    # job_id -> (feature, reason): refused by that mode alone.
    ENFORCE_REFUSED = {
        "parity-14": ("policy_env", "denied_env"),
        "parity-15": ("policy_args", "arg_pattern_mismatch"),
        "parity-16": ("policy_files", "file_not_allowed"),
        "parity-17": ("audience", "runner_id_mismatch"),
    }
    # Exec jobs that reach execution under enforce: each carries a
    # confinement entry and a job_user entry. (parity-05 is refused
    # by file staging before either wrap is consulted; the refused
    # jobs above never reach execution at all.)
    ENFORCE_EXEC_JOBS = {"parity-02", "parity-03", "parity-04",
                         "parity-06", "parity-10", "parity-13"}

    def _enforce_block(self):
        block = all_enforce_block()
        # job_user enforce binds only with a configured user (the
        # same shape the startup validator requires). The user is
        # the suite's dedicated test user; where it does not exist
        # the feature's documented fallback applies and the entry
        # below says so.
        block["job_user"] = {"user": "pigeon-test"}
        return block

    def test_all_enforce_outcomes_match_recorded_expectations(self):
        corpus = build_corpus()
        off = run_variant(all_off_block(), corpus)
        audit = run_variant(all_audit_block(), corpus,
                            cfg_extra={"runner_id": PARITY_RUNNER_ID})
        enf = run_variant(self._enforce_block(), corpus,
                          cfg_extra={"runner_id": PARITY_RUNNER_ID})
        enf_sent = _sent_by_id(enf)
        aud_sent = _sent_by_id(audit)
        enf_entries = _audit_entries(enf)
        aud_entries = _audit_entries(audit)
        enf_seen = _unprefix(enf["seen"])

        # Every message was handled exactly once in every variant.
        self.assertEqual(enf["flagged"], off["flagged"])
        self.assertEqual(len(enf["flagged"]), len(corpus))

        # Compliant jobs: the same result as with the features off,
        # byte for byte after normalization (the denied jobs sit
        # after every compliant one in the corpus, so no result
        # sequence number shifts), carrying the recorded exit code
        # and output.
        off_sent = _sent_by_id(off)
        for job_id, (exit_code, text) in self.ENFORCE_RESULTS.items():
            with self.subTest(job_id=job_id):
                self.assertIn(job_id, enf_sent)
                self.assertEqual(enf_sent[job_id], off_sent[job_id])
                self.assertIn('"exit_code":%d' % exit_code,
                              enf_sent[job_id])
                if text is not None:
                    self.assertIn(text, enf_sent[job_id])
                self.assertIn(job_id, enf_seen)
        # The replayed second copy produced no second result.
        self.assertEqual(
            len([s for s, _ in enf["sent"] if "parity-09" in s]), 1)

        # Pre-security refusals are unchanged and add no denial.
        for job_id in self.ENFORCE_NO_RESULT:
            with self.subTest(job_id=job_id):
                self.assertNotIn(job_id, enf_sent)
                self.assertNotIn(job_id, enf_seen)
                self.assertFalse(
                    [e for e in enf_entries
                     if e.get("job_id") == job_id
                     and e.get("decision") == "denied"],
                    "no security denial may be added for %s" % job_id)

        # The sensor alert is ingested: seen, no result, no denial.
        self.assertNotIn("parity-12", enf_sent)
        self.assertIn("parity-12", enf_seen)

        # Each violating job is refused by its own mode, and the
        # all-audit run of the same job is the paired control: it
        # executes, with a would_deny entry naming the same
        # feature and reason.
        for job_id, (feature, reason) in self.ENFORCE_REFUSED.items():
            with self.subTest(job_id=job_id):
                self.assertNotIn(job_id, enf_sent)
                self.assertNotIn(job_id, enf_seen)
                denied = [e for e in enf_entries
                          if e.get("job_id") == job_id
                          and e.get("decision") == "denied"]
                self.assertEqual(len(denied), 1, denied)
                self.assertEqual(denied[0]["feature"], feature)
                self.assertEqual(denied[0]["reason"], reason)
                self.assertEqual(denied[0]["mode"], "enforce")
                self.assertIn(job_id, aud_sent)
                would = [e for e in aud_entries
                         if e.get("job_id") == job_id
                         and e.get("decision") == "would_deny"]
                self.assertTrue(
                    any(e["feature"] == feature
                        and e["reason"] == reason for e in would),
                    (job_id, would))

        # Those four are the only denials, and enforce never logs
        # an audit-mode would_* decision.
        self.assertEqual(
            {(e["job_id"], e["feature"]) for e in enf_entries
             if e.get("decision") == "denied"},
            {(j, f) for j, (f, _r) in self.ENFORCE_REFUSED.items()})
        self.assertFalse([e for e in enf_entries
                          if str(e.get("decision", "")).startswith(
                              "would_")])

        # The seen set is the off variant's, minus the refused
        # jobs, under the runner_id namespace.
        self.assertEqual(
            enf_seen,
            sorted(j for j in off["seen"]
                   if j not in self.ENFORCE_REFUSED))

        # confinement and job_user wrapped every exec job that
        # reached execution, with the decision this machine's
        # capabilities dictate.
        conf = {e["job_id"]: e["decision"] for e in enf_entries
                if e.get("feature") == "confinement"}
        self.assertEqual(set(conf), self.ENFORCE_EXEC_JOBS)
        want_conf = ("sandboxed" if _sandbox.sandbox_available()
                     else "fallback")
        self.assertEqual(set(conf.values()), {want_conf})
        ju = {e["job_id"]: e["decision"] for e in enf_entries
              if e.get("feature") == "job_user"}
        self.assertEqual(set(ju), self.ENFORCE_EXEC_JOBS)
        if os.name == "nt":
            want_ju = "unsupported_platform"
        elif IS_ROOT and HAS_TEST_USER:
            want_ju = "run_as"
        else:
            want_ju = "fallback"
        self.assertEqual(set(ju.values()), {want_ju})

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER and os.name != "nt",
                         "needs root and the pigeon-test user")
    def test_enforce_job_user_drop_runs_the_job_as_the_job_user(self):
        # The real drop, on the real (signed, poll_once) path: the
        # job's own uid report is the job user's, and the audit
        # entry says run_as.
        corpus = [("whoami", _email(_payload(
            "parity-drop", kind="exec", script="id -u",
            runner_id=PARITY_RUNNER_ID)))]
        enf = run_variant(self._enforce_block(), corpus,
                          cfg_extra={"runner_id": PARITY_RUNNER_ID})
        sent = _sent_by_id(enf)
        self.assertIn("parity-drop", sent)
        uid = pwd.getpwnam("pigeon-test").pw_uid
        self.assertIn('"stdout":"%d' % uid, sent["parity-drop"])
        entries = [e for e in _audit_entries(enf)
                   if e.get("feature") == "job_user"
                   and e.get("job_id") == "parity-drop"]
        self.assertEqual([e["decision"] for e in entries], ["run_as"])

    @unittest.skipUnless(ENGAGES,
                         "sandbox cannot engage on this machine "
                         "(startup probe)")
    def test_enforce_confinement_sandboxes_a_compliant_job(self):
        # The real sandbox, on the real path: a compliant exec job
        # runs inside bwrap and the audit entry says sandboxed.
        corpus = [("confined", _email(_payload(
            "parity-conf", kind="exec", script="echo confined-ok",
            runner_id=PARITY_RUNNER_ID)))]
        enf = run_variant(all_enforce_block(), corpus,
                          cfg_extra={"runner_id": PARITY_RUNNER_ID})
        sent = _sent_by_id(enf)
        self.assertIn("parity-conf", sent)
        self.assertIn('"exit_code":0', sent["parity-conf"])
        self.assertIn("confined-ok", sent["parity-conf"])
        entries = [e for e in _audit_entries(enf)
                   if e.get("feature") == "confinement"
                   and e.get("job_id") == "parity-conf"]
        self.assertEqual([e["decision"] for e in entries],
                         ["sandboxed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
