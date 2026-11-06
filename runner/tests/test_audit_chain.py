#!/usr/bin/env python3
"""S4: the security audit log is a tamper-evident hash chain.

Each record written by runner.guard.security.write_audit_entry
carries a monotonic ``seq`` and a ``chain`` value: the SHA-256 hex
of the previous record's chain value concatenated with the
canonical JSON of the record without its ``chain`` field
(json.dumps with sort_keys=True, separators=(",", ":"),
ensure_ascii=False, encoded utf-8). The first record of a fresh
log chains from the genesis constant (SHA-256 of a fixed label).
Rollover carries the chain head into the new file. A log written
before chaining existed keeps its unchained prefix: the first
chained record records how many unchained records precede it in
``chain_start`` and chains from a genesis derived from that
count, and the verifier reports the legacy prefix honestly
instead of failing the whole log.

Tail truncation: the writer records the chain head (seq + chain)
in security-audit-counts.json under ``_audit_chain`` on every
write, and the verifier compares the log's tail against that
checkpoint, so deleting tail records is detected while the
counts file survives. Without a checkpoint the verifier can only
say the chain is intact to the end of the file, and its detail
says exactly that.
"""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.guard import security as S  # noqa: E402
from runner.ops import auditreport as AR  # noqa: E402


def _write(base, n, cfg=None, feature="policy_env"):
    for i in range(n):
        S.write_audit_entry(base, feature, "denied", "reason-%d" % i,
                            key_id="k1", job_id="j%d" % i, cfg=cfg,
                            mode="enforce")


def _rows(base, name=None):
    path = os.path.join(base, name or S.AUDIT_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _rewrite(base, rows, name=None):
    path = os.path.join(base, name or S.AUDIT_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _canonical(record):
    body = {k: v for k, v in record.items() if k != "chain"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


class ChainWriteTest(unittest.TestCase):
    def test_records_carry_seq_and_chain_and_verify_ok(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 3)
            rows = _rows(d)
            self.assertEqual([r["seq"] for r in rows], [1, 2, 3])
            for row in rows:
                self.assertRegex(row["chain"], r"^[0-9a-f]{64}$")
            self.assertEqual(len({r["chain"] for r in rows}), 3)
            ok, detail = AR.verify_audit_chain(d)
            self.assertTrue(ok, detail)

    def test_first_record_chains_from_the_documented_genesis(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 2)
            rows = _rows(d)
            genesis = hashlib.sha256(
                b"homing-pigeon security audit chain v1").hexdigest()
            expect = hashlib.sha256(
                genesis.encode("utf-8") + _canonical(rows[0])).hexdigest()
            self.assertEqual(rows[0]["chain"], expect)
            expect2 = hashlib.sha256(
                rows[0]["chain"].encode("utf-8")
                + _canonical(rows[1])).hexdigest()
            self.assertEqual(rows[1]["chain"], expect2)

    def test_checkpoint_head_matches_the_log_tail(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 3)
            rows = _rows(d)
            with open(os.path.join(d, S.COUNTS_FILE),
                      encoding="utf-8") as fh:
                counts = json.load(fh)
            head = counts["_audit_chain"]
            self.assertEqual(head["seq"], rows[-1]["seq"])
            self.assertEqual(head["chain"], rows[-1]["chain"])


class TamperTest(unittest.TestCase):
    def test_tampering_with_a_middle_record_fails_at_that_record(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 4)
            rows = _rows(d)
            rows[1]["reason"] = "forged"
            _rewrite(d, rows)
            ok, detail = AR.verify_audit_chain(d)
            self.assertFalse(ok)
            self.assertIn("seq 2", detail)

    def test_deleting_a_middle_record_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 4)
            rows = _rows(d)
            del rows[1]
            _rewrite(d, rows)
            ok, detail = AR.verify_audit_chain(d)
            self.assertFalse(ok)
            self.assertIn("seq", detail)

    def test_truncating_the_tail_is_detected_by_the_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 4)
            rows = _rows(d)
            _rewrite(d, rows[:3])
            ok, detail = AR.verify_audit_chain(d)
            self.assertFalse(ok)
            self.assertIn("checkpoint", detail)

    def test_without_a_checkpoint_truncation_is_reported_honestly(self):
        # The chain alone cannot detect pure tail truncation: with
        # the counts file (and its checkpoint) gone, the verifier
        # reports the chain intact to the end of the file and says
        # the tail cannot be checked.
        with tempfile.TemporaryDirectory() as d:
            _write(d, 4)
            rows = _rows(d)
            _rewrite(d, rows[:3])
            os.remove(os.path.join(d, S.COUNTS_FILE))
            ok, detail = AR.verify_audit_chain(d)
            self.assertTrue(ok, detail)
            self.assertIn("no checkpoint", detail)


class RolloverTest(unittest.TestCase):
    def test_rollover_keeps_the_chain_verifiable(self):
        cfg = {"security": {"audit_max_lines": 3}}
        with tempfile.TemporaryDirectory() as d:
            _write(d, 5, cfg=cfg)
            rolled = _rows(d, S.AUDIT_ROLLED_FILE)
            live = _rows(d)
            self.assertEqual([r["seq"] for r in rolled], [1, 2, 3])
            self.assertEqual([r["seq"] for r in live], [4, 5])
            ok, detail = AR.verify_audit_chain(d)
            self.assertTrue(ok, detail)


class LegacyLogTest(unittest.TestCase):
    def _legacy_row(self, reason):
        return {"ts": "2026-10-15T12:00:00Z", "feature": "policy_env",
                "decision": "denied", "reason": reason,
                "key_id": "k1", "job_id": "j0"}

    def test_new_records_chain_after_a_legacy_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            _rewrite(d, [self._legacy_row("old-1"),
                         self._legacy_row("old-2")])
            _write(d, 2)
            rows = _rows(d)
            self.assertNotIn("chain", rows[0])
            self.assertNotIn("chain", rows[1])
            self.assertEqual([r["seq"] for r in rows[2:]], [3, 4])
            self.assertEqual(rows[2]["chain_start"], 2)
            ok, detail = AR.verify_audit_chain(d)
            self.assertTrue(ok, detail)
            self.assertIn("legacy", detail)
            self.assertIn("2", detail)


class ReportCompatTest(unittest.TestCase):
    def test_audit_report_still_reads_a_chained_log(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 3)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = AR.main({}, d, since="30d")
            out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("policy_env", out)

    def test_verify_cli_entry_reports_ok_and_breakage(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, 2)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = AR.verify_main(d)
            self.assertEqual(rc, 0)
            self.assertIn("ok", buf.getvalue())
            rows = _rows(d)
            rows[0]["reason"] = "forged"
            _rewrite(d, rows)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = AR.verify_main(d)
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
