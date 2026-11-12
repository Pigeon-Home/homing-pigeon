#!/usr/bin/env python3
"""Parity tests for the hardening milestones (M0).

Two parities are pinned. Audit never changes an outcome: all
features off and all features audit produce identical mail
outputs. And the lockdown default is real end to end: no
security block at all produces exactly the all-features-enforce
outputs. At M0 no feature calls sec_decide, so with every
feature off the audit log must stay absent. From M6, confinement
in audit mode logs would_* decisions; the mail outputs must
still be identical.

The all-enforce leg (AllEnforceParityTest) is the locked-down
posture as the shipped default: all six modes at enforce, with
the binding config that gives two of them something to bind (a
runner_id for audience, a user for job_user). Its expectations
are recorded per job, not snapshotted: compliant jobs still
execute, and each violating job is refused by the one mode it
violates.
"""
import copy
import json
import os
import string
import sys
import tempfile
import types
import unittest
from collections import OrderedDict
from unittest import mock

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
    read_audit_lines,
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
    def test_no_block_is_all_enforce_and_off_audit_identical(self):
        corpus = build_corpus()
        base = run_variant(None, corpus)
        off = run_variant(all_off_block(), corpus)
        audit = run_variant(all_audit_block(), corpus)
        enforce = run_variant(all_enforce_block(), corpus)
        # The lockdown default, end to end: a config with no
        # security block behaves exactly as the explicit
        # all-enforce block, in mail, flags, and the seen set.
        self.assertEqual(base["sent"], enforce["sent"])
        self.assertEqual(base["flagged"], enforce["flagged"])
        self.assertEqual(base["seen"], enforce["seen"])
        # Audit never changes an outcome: off and audit agree.
        self.assertEqual(off["sent"], audit["sent"])
        self.assertEqual(off["flagged"], audit["flagged"])
        self.assertEqual(off["seen"], audit["seen"])
        # M0: nothing calls sec_decide yet; with every feature off
        # no audit log may exist.
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
      reaches execution (ENFORCE_EXEC_JOBS). Since phase 2 of the
      default-posture work they are refusal gates at execution
      time: when the mechanism cannot engage -- the sandbox
      unavailable or unbuildable, the demote impossible (no root,
      no such user, an unchownable workdir, or a platform with no
      setuid demote, where the entry is "unsupported_platform") --
      the fallback is recorded and the job is refused (a
      rejection result, exit -2), never run weaker. The expected
      outcomes are therefore keyed to the same capability probes
      the runner itself uses: where both mechanisms can engage,
      the jobs run; where one cannot, the exec jobs are refused
      by the first wrap that cannot engage (confinement is
      consulted before job_user).
    - On Windows the capability question is the platform
      backend's, not bwrap's: where the runner's own startup
      gates say both mechanisms engage, the exec jobs run
      confined -- a result is delivered for each, and none is
      the wrap's rejection -- the confinement record says
      "confined", and job_user's record is its two-step win32
      shape (the preexec "would_contain" deferral and the
      postspawn "contained"). What a confined process prints
      on a given Windows host is the backend's field behavior
      (the rig battery's ground), not this test's recorded
      expectation, so the byte-equality leg above stays keyed
      to the POSIX wraps.
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

        # Whether the two execution wraps can engage on this
        # machine, by the runner's own probes. Confinement has
        # three shapes: unavailable (its refusal ends the job),
        # available and engaging (the job runs sandboxed), and
        # the middle shape -- bwrap present but the startup
        # trial fails -- where the argv is built and audited
        # "sandboxed" and bwrap then fails at start, so neither
        # the recorded results nor the refusal leg describes the
        # exec jobs and only their audit decisions are asserted.
        conf_avail = _sandbox.sandbox_available()
        conf_refuses = not conf_avail
        conf_runs = conf_avail and ENGAGES
        ju_ok = os.name != "nt" and IS_ROOT and HAS_TEST_USER
        wraps_run = conf_runs and ju_ok
        exec_refused = conf_refuses or (conf_runs and not ju_ok)

        # Windows, macOS and FreeBSD since their confinement
        # backends landed: the capability probes are the runner's
        # own startup gates -- the bwrap probe above is Linux-only
        # and reads "unavailable" on those hosts whether or not
        # the platform backend can engage, so keying the
        # expectations to it recorded refusals on a host where
        # the exec jobs run confined (win32 first; then darwin,
        # when the macOS backend engaged on the CI runners on
        # 2026-11-12). Where both gates engage, the backend arm
        # below carries the expectations; where confinement
        # engages and job_user cannot (a runner that is not
        # root), job_user refuses the exec jobs before the spawn
        # seam, which is where a platform backend writes its
        # confinement row, so those jobs carry a job_user
        # fallback row and no confinement row; where confinement
        # cannot engage, the refusal shapes above are what
        # production does there too (the argv gate refuses
        # before job_user is reached).
        backend_host = (sys.platform == "win32"
                        or sys.platform == "darwin"
                        or sys.platform.startswith("freebsd"))
        backend_conf = backend_ju = False
        if backend_host:
            from runner import runner as _runner_mod
            enf_cfg = {"security": self._enforce_block()}
            backend_conf = _runner_mod._confinement_startup_problem(
                enf_cfg) is None
            backend_ju = _runner_mod._job_user_startup_problem(
                enf_cfg) is None
        win_engages = backend_conf and backend_ju

        # Compliant jobs: the same result as with the features off,
        # byte for byte after normalization (the denied jobs sit
        # after every compliant one in the corpus, so no result
        # sequence number shifts), carrying the recorded exit code
        # and output. The exec jobs are the exception when a wrap
        # cannot engage here: the wrap refuses them, and their
        # expectation is the rejection leg below.
        off_sent = _sent_by_id(off)
        for job_id, (exit_code, text) in self.ENFORCE_RESULTS.items():
            if job_id in self.ENFORCE_EXEC_JOBS and not wraps_run:
                continue
            with self.subTest(job_id=job_id):
                self.assertIn(job_id, enf_sent)
                self.assertEqual(enf_sent[job_id], off_sent[job_id])
                self.assertIn('"exit_code":%d' % exit_code,
                              enf_sent[job_id])
                if text is not None:
                    self.assertIn(text, enf_sent[job_id])
                self.assertIn(job_id, enf_seen)
        if exec_refused and not win_engages:
            # The refused exec jobs: a rejection result (exit -2,
            # "job rejected: ..."), still delivered and seen --
            # refused by the wrap, not dropped.
            for job_id in self.ENFORCE_EXEC_JOBS:
                with self.subTest(job_id=job_id):
                    self.assertIn(job_id, enf_sent)
                    self.assertIn('"exit_code":-2', enf_sent[job_id])
                    self.assertIn("job rejected", enf_sent[job_id])
                    self.assertIn(job_id, enf_seen)
        if win_engages:
            # The exec jobs ran confined: each delivered a result
            # and was seen, and none of the results is the wrap's
            # rejection -- the modes engaged instead of refusing.
            for job_id in self.ENFORCE_EXEC_JOBS:
                with self.subTest(job_id=job_id):
                    self.assertIn(job_id, enf_sent)
                    self.assertNotIn('"exit_code":-2',
                                     enf_sent[job_id])
                    self.assertNotIn("job rejected",
                                     enf_sent[job_id])
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
        would = [e for e in enf_entries
                 if str(e.get("decision", "")).startswith("would_")]
        if win_engages:
            # job_user's win32 preexec record is a would_ entry
            # by design: it is the deferral half of an
            # enforce-mode application whose other half is the
            # postspawn "contained" record, not an audit-mode
            # decision leaking into the enforce run.
            would = [e for e in would
                     if not (e.get("feature") == "job_user"
                             and e.get("decision") == "would_contain")]
        self.assertFalse(would)

        # The seen set is the off variant's, minus the refused
        # jobs, under the runner_id namespace.
        self.assertEqual(
            enf_seen,
            sorted(j for j in off["seen"]
                   if j not in self.ENFORCE_REFUSED))

        # confinement and job_user wrapped every exec job that
        # reached execution, with the decision this machine's
        # capabilities dictate. Confinement is consulted first:
        # where it cannot engage, its refusal ends the job before
        # job_user is reached, so job_user leaves no entries.
        conf = {e["job_id"]: e["decision"] for e in enf_entries
                if e.get("feature") == "confinement"}
        ju = {e["job_id"]: e["decision"] for e in enf_entries
              if e.get("feature") == "job_user"}
        if win_engages:
            self.assertEqual(set(conf), self.ENFORCE_EXEC_JOBS)
            self.assertEqual(set(conf.values()), {"confined"})
            self.assertEqual(set(ju), self.ENFORCE_EXEC_JOBS)
            # job_user's own record: the Job Object's "contained"
            # on win32; the POSIX demote's "run_as" under a
            # Seatbelt or jail backend.
            want_ju = "contained" if sys.platform == "win32" else "run_as"
            self.assertEqual(set(ju.values()), {want_ju})
        elif backend_conf:
            # The backend engages and job_user cannot: refused at
            # job_user's gate, before the spawn seam where the
            # backend would write its confinement row.
            self.assertEqual(conf, {})
            self.assertEqual(set(ju), self.ENFORCE_EXEC_JOBS)
            self.assertEqual(set(ju.values()), {"fallback"})
        elif conf_refuses:
            self.assertEqual(set(conf), self.ENFORCE_EXEC_JOBS)
            self.assertEqual(set(conf.values()), {"fallback"})
            self.assertEqual(ju, {})
        else:
            self.assertEqual(set(conf), self.ENFORCE_EXEC_JOBS)
            self.assertEqual(set(conf.values()), {"sandboxed"})
            self.assertEqual(set(ju), self.ENFORCE_EXEC_JOBS)
            want_ju = "run_as" if ju_ok else "fallback"
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


class _ScriptedMacBackend:
    """A macOS confinement backend whose probe answers as scripted."""

    IS_MACOS_BACKEND = True

    def __init__(self, problem):
        self._problem = problem

    def macos_confinement_problem(self, cfg=None):
        return self._problem

    def macos_startup_problem(self, cfg=None):
        return self._problem


class _NonRootFace:
    """The job_user face of a runner that is not root."""

    def euid(self):
        return 1000


class _RootFace:
    """The job_user face of a root runner whose test user exists."""

    def euid(self):
        return 0

    def getpwnam(self, user):
        return types.SimpleNamespace(
            pw_name=user, pw_uid=4242, pw_gid=4242)

    def walk(self, path):
        return iter(())

    def realpath(self, path):
        return os.path.realpath(path)

    def dirname(self, path):
        return os.path.dirname(path)

    def stat(self, path):
        return types.SimpleNamespace(st_mode=0o777)

    def chmod(self, path, mode):
        raise AssertionError("a world-traversable chain needs no chmod")


class DarwinParitySubstrateTest(unittest.TestCase):
    """The substrate the darwin arm of AllEnforceParityTest keys
    on, pinned on scripted seams so it runs on every host.

    The test-macos failure at the confinement-row assertion was
    this shape: on a darwin host whose Seatbelt backend can
    engage, the argv gate returns the normal argv and writes NO
    confinement row (that row is the spawn seam's, written when
    a confined process is actually created); where the runner
    is not root, the job_user preexec then refuses the job
    before the spawn seam is reached, so the job carries a
    job_user fallback row and no confinement row at all. The
    bwrap-keyed expectations read that as six missing parity
    points. These tests pin the three darwin shapes at the
    seams themselves: the engageable gate's silence, the dead
    gate's fallback row and denial, and the composed refusal
    the hosted shape produces, per exec job.
    """

    def _enforce_cfg(self):
        block = all_enforce_block()
        block["job_user"] = {"user": "pigeon-test"}
        return {"security": block}

    def _rows(self, base):
        return [json.loads(line)
                for line in read_audit_lines(base) or []]

    def _argv_gate(self, cfg, base, job_id, problem):
        from runner import runner as _runner_mod
        work = os.path.join(base, "work")
        os.makedirs(work, exist_ok=True)
        with mock.patch.object(sys, "platform", "darwin"):
            return _runner_mod._confinement_argv(
                cfg, base, job_id, ["/usr/bin/python3"],
                "/work/script.py", work, [], {},
                backend=_ScriptedMacBackend(problem))

    def _preexec(self, cfg, base, job_id, work, face):
        # A darwin host presents two platform signals, and the
        # seams read different ones: _confinement_argv reads
        # sys.platform, _job_user_preexec reads os.name. The
        # simulation patches both, to the pair a real darwin
        # host presents (darwin, posix); patching sys.platform
        # alone left os.name at the host's value, so on a
        # Windows host the preexec took its Windows arm and
        # recorded unsupported_platform -- the test-windows
        # failures named in the desk's W-S record. The
        # Windows-host shape itself is pinned, unmoved, in
        # DarwinParityHostSignalTest below.
        from runner import runner as _runner_mod
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(os, "name", "posix"):
            return _runner_mod._job_user_preexec(
                cfg, base, job_id, work, face=face)

    def test_engageable_darwin_gate_writes_no_confinement_row(self):
        with tempfile.TemporaryDirectory() as base:
            argv, _host_env, _boxed = self._argv_gate(
                self._enforce_cfg(), base, "parity-02", None)
            self.assertEqual(argv, ["/usr/bin/python3",
                                    "/work/script.py"])
            self.assertEqual(
                [e for e in self._rows(base)
                 if e.get("feature") == "confinement"], [])

    def test_dead_darwin_gate_denies_and_writes_the_fallback_row(self):
        with tempfile.TemporaryDirectory() as base:
            argv, _host_env, _boxed = self._argv_gate(
                self._enforce_cfg(), base, "parity-02",
                "scripted problem")
            self.assertEqual(argv, [])
            conf = [e for e in self._rows(base)
                    if e.get("feature") == "confinement"]
            self.assertEqual(len(conf), 1)
            self.assertEqual(conf[0]["decision"], "fallback")
            self.assertEqual(conf[0]["reason"],
                             "confinement_unavailable")
            self.assertEqual(conf[0]["job_id"], "parity-02")

    def test_ci_shape_refuses_at_job_user_with_no_confinement_row(self):
        # The hosted shape, per exec job: the backend engages,
        # the runner is not root, and the job is refused at the
        # job_user gate (exec.py's order: argv gate, preexec,
        # spawn) before any confinement row can be written.
        from runner import runner as _runner_mod
        cfg = self._enforce_cfg()
        for job_id in sorted(
                AllEnforceParityTest.ENFORCE_EXEC_JOBS):
            with self.subTest(job_id=job_id):
                with tempfile.TemporaryDirectory() as base:
                    argv, _h, _b = self._argv_gate(
                        cfg, base, job_id, None)
                    self.assertNotEqual(argv, [])
                    work = os.path.join(base, "work")
                    with self.assertRaises(
                            _runner_mod.JobRejected):
                        self._preexec(cfg, base, job_id, work,
                                      _NonRootFace())
                    entries = self._rows(base)
                    ju = [e for e in entries
                          if e.get("feature") == "job_user"]
                    self.assertEqual(len(ju), 1)
                    self.assertEqual(ju[0]["decision"], "fallback")
                    self.assertEqual(ju[0]["reason"],
                                     "job_user_needs_root")
                    self.assertEqual(
                        [e for e in entries
                         if e.get("feature") == "confinement"], [])

    def test_root_shape_passes_the_preexec_gate_with_a_run_as_row(self):
        # The both-engage shape's job_user half: root, the user
        # resolvable -- the preexec records run_as and returns
        # the demote, so under the backend arm the exec jobs
        # carry run_as rows beside the spawn seam's confined
        # rows.
        from runner import runner as _runner_mod
        cfg = self._enforce_cfg()
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work)
            demote = self._preexec(cfg, base, "parity-02", work,
                                   _RootFace())
            self.assertTrue(callable(demote))
            ju = [e for e in self._rows(base)
                  if e.get("feature") == "job_user"]
            self.assertEqual([e["decision"] for e in ju],
                             ["run_as"])


class _ScriptedWinBackend:
    """A Windows backend whose startup probe answers as scripted."""

    IS_WINDOWS_BACKEND = True

    def __init__(self, problem):
        self._problem = problem

    def windows_startup_problem(self, cfg=None):
        return self._problem


class DarwinParityHostSignalTest(unittest.TestCase):
    """The other host-signal shape, pinned so it cannot drift.

    _job_user_preexec keys its Windows arm on os.name, by its
    own documented contract (the demote it guards is a POSIX
    syscall surface, and its dedicated win32 tests simulate
    the arm by patching os.name). A simulated darwin
    (sys.platform patched) running on a Windows host therefore
    reaches the preexec's Windows arm, not its POSIX one: that
    is the shape the test-windows leg runs, and the shape whose
    record the substrate family originally misread as the
    darwin record. These tests pin the Windows-host record
    exactly as production writes it -- unsupported_platform
    under enforce, refused; the audit-mode record without a
    refusal; the engageable backend's deferral -- so completing
    the substrate family's darwin simulation (both signals
    patched, in DarwinParitySubstrateTest) is a keying fix,
    not a moved expectation: on a real Windows host nothing
    here changes.
    """

    def _cfg(self, job_user_mode="enforce"):
        block = all_enforce_block()
        block["modes"]["job_user"] = job_user_mode
        block["job_user"] = {"user": "pigeon-test"}
        return {"security": block}

    def _rows(self, base):
        return [json.loads(line)
                for line in read_audit_lines(base) or []]

    def _preexec_on_windows_host(self, cfg, base, job_id, work,
                                 face, backend=None):
        from runner import runner as _runner_mod
        kw = {} if backend is None else {"backend": backend}
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(os, "name", "nt"):
            return _runner_mod._job_user_preexec(
                cfg, base, job_id, work, face=face, **kw)

    def test_windows_host_ci_shape_records_unsupported_platform(self):
        # Per exec job: the argv gate, keyed on sys.platform,
        # still answers the darwin shape (normal argv, no
        # confinement row); the preexec, keyed on os.name,
        # records the Windows arm's unsupported_platform and
        # refuses under enforce, before any face is consulted.
        from runner import runner as _runner_mod
        substrate = DarwinParitySubstrateTest(
            "test_ci_shape_refuses_at_job_user_with_no_"
            "confinement_row")
        cfg = self._cfg()
        for job_id in sorted(
                AllEnforceParityTest.ENFORCE_EXEC_JOBS):
            with self.subTest(job_id=job_id):
                with tempfile.TemporaryDirectory() as base:
                    argv, _h, _b = substrate._argv_gate(
                        cfg, base, job_id, None)
                    self.assertNotEqual(argv, [])
                    work = os.path.join(base, "work")
                    with self.assertRaises(
                            _runner_mod.JobRejected):
                        self._preexec_on_windows_host(
                            cfg, base, job_id, work,
                            _NonRootFace())
                    entries = self._rows(base)
                    ju = [e for e in entries
                          if e.get("feature") == "job_user"]
                    self.assertEqual(len(ju), 1)
                    self.assertEqual(ju[0]["decision"],
                                     "unsupported_platform")
                    self.assertEqual(ju[0]["reason"],
                                     "job_user_posix_only")
                    self.assertEqual(
                        [e for e in entries
                         if e.get("feature") == "confinement"], [])

    def test_windows_host_root_shape_records_unsupported_platform(self):
        # The root face changes nothing on the Windows arm: the
        # branch is taken before the face is consulted, the
        # record is unsupported_platform, and the job is
        # refused -- no demote, no run_as row.
        from runner import runner as _runner_mod
        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work)
            with self.assertRaises(_runner_mod.JobRejected):
                self._preexec_on_windows_host(
                    cfg, base, "parity-02", work, _RootFace())
            ju = [e for e in self._rows(base)
                  if e.get("feature") == "job_user"]
            self.assertEqual([e["decision"] for e in ju],
                             ["unsupported_platform"])

    def test_windows_host_audit_mode_records_without_refusing(self):
        # In audit mode the Windows arm records the same
        # unsupported_platform entry and lets the job proceed:
        # the record is the mode's, not a refusal.
        cfg = self._cfg(job_user_mode="audit")
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work)
            out = self._preexec_on_windows_host(
                cfg, base, "parity-02", work, _NonRootFace())
            self.assertIsNone(out)
            ju = [e for e in self._rows(base)
                  if e.get("feature") == "job_user"]
            self.assertEqual([e["decision"] for e in ju],
                             ["unsupported_platform"])

    def test_windows_host_engageable_backend_defers(self):
        # With an engageable Windows backend injected, the
        # Windows arm defers to the postspawn application: the
        # record is would_contain / windows_job_object and the
        # job is not refused at the preexec.
        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work)
            out = self._preexec_on_windows_host(
                cfg, base, "parity-02", work, _NonRootFace(),
                backend=_ScriptedWinBackend(None))
            self.assertIsNone(out)
            ju = [e for e in self._rows(base)
                  if e.get("feature") == "job_user"]
            self.assertEqual(len(ju), 1)
            self.assertEqual(ju[0]["decision"], "would_contain")
            self.assertEqual(ju[0]["reason"],
                             "windows_job_object")

    def test_completed_simulation_audit_mode_records_would_run_as(self):
        # The completed darwin simulation's audit shape: both
        # signals patched to the darwin pair, job_user in audit
        # mode -- the POSIX arm records would_run_as and
        # returns without refusing, at either face.
        substrate = DarwinParitySubstrateTest(
            "test_root_shape_passes_the_preexec_gate_with_a_"
            "run_as_row")
        cfg = self._cfg(job_user_mode="audit")
        for face in (_NonRootFace(), _RootFace()):
            with self.subTest(face=type(face).__name__):
                with tempfile.TemporaryDirectory() as base:
                    work = os.path.join(base, "work")
                    os.makedirs(work)
                    out = substrate._preexec(
                        cfg, base, "parity-02", work, face)
                    self.assertIsNone(out)
                    ju = [e for e in self._rows(base)
                          if e.get("feature") == "job_user"]
                    self.assertEqual([e["decision"] for e in ju],
                                     ["would_run_as"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
