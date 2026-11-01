#!/usr/bin/env python3
"""Parity tests for the hardening milestones (M0).

Default behavior must not change: no security block, all features
off, and all features audit must produce identical mail outputs.
At M0 no feature calls sec_decide, so the audit log must stay absent.
From M6, confinement in audit mode logs would_* decisions; the mail
outputs must still be identical.
"""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.tests.security_parity import (  # noqa: E402
    all_audit_block,
    all_off_block,
    build_corpus,
    run_variant,
)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
