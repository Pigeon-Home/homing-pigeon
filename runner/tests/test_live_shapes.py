#!/usr/bin/env python3
"""Pin the shapes of the live capture in docs/reports/live-2026-10-25.

These tests do not re-run the rig. They assert that the captured
files still have the shapes the documentation quotes, so a later
change to the log or event format is visible here before the docs
drift.
"""
import json
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LIVE = os.path.join(REPO, "docs", "reports", "live-2026-10-25")


def _read(name):
    with open(os.path.join(LIVE, name), encoding="utf-8") as fh:
        return fh.read()


class RunnerLogShapeTest(unittest.TestCase):
    def test_startup_block_is_present(self):
        text = _read("runner.log")
        self.assertIn("homing-pigeon 3.12.51 starting", text)
        self.assertIn("auth=oauth mailbox=runner@example.test", text)
        self.assertIn("judge=advisory ceiling=attested", text)
        self.assertIn("[WARN] confinement is off; workspace_root is not set",
                      text)
        self.assertIn("oracle: deterministic mode (Pi Light)", text)

    def test_job_finish_line_shape(self):
        text = _read("runner.log")
        self.assertRegex(
            text,
            r"\[INFO\] job [0-9a-f-]{36} process finished exit=0")

    def test_transport_warn_shape(self):
        text = _read("runner.log")
        self.assertIn("[WARN] transport email: email transport: pass failed:",
                      text)

    def test_no_real_email_addresses(self):
        text = _read("runner.log")
        self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@(?!example\.test)\S+")


class SecurityEventsShapeTest(unittest.TestCase):
    def test_resource_pressure_and_auth_rejection(self):
        types = set()
        pressure = None
        rejection = None
        with open(os.path.join(LIVE, "security-events.jsonl"),
                  encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                event = json.loads(line)
                types.add(event["type"])
                if event["type"] == "resource_pressure" and pressure is None:
                    pressure = event
                if event["type"] == "auth_rejection" and rejection is None:
                    rejection = event
        self.assertIn("resource_pressure", types)
        self.assertIn("auth_rejection", types)
        self.assertEqual(set(pressure), {"type", "at", "threshold", "resources"})
        self.assertIn("mem", pressure["resources"])
        self.assertGreater(pressure["resources"]["mem"], 0.9)
        self.assertEqual(set(rejection), {"type", "at", "reason"})
        self.assertEqual(rejection["reason"], "bad_signature")


class OracleLearningShapeTest(unittest.TestCase):
    def test_prediction_and_reconciliation_shapes(self):
        prediction = None
        reconciliation = None
        with open(os.path.join(LIVE, "oracle-learning.jsonl"),
                  encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec["type"] == "prediction" and prediction is None:
                    prediction = rec
                if rec["type"] == "reconciliation" and reconciliation is None:
                    reconciliation = rec
                if prediction and reconciliation:
                    break
        self.assertIsNotNone(prediction)
        self.assertIsNotNone(reconciliation)
        self.assertEqual(
            set(prediction),
            {"type", "at", "job_id", "received_digest", "host", "mode",
             "verdict", "findings", "features", "repair"})
        self.assertEqual(prediction["mode"], "repair")
        self.assertEqual(
            set(reconciliation),
            {"type", "at", "job_id", "host", "classification",
             "predicted_verdict", "outcome", "lesson_selected"})
        self.assertIn("exit_code", reconciliation["outcome"])


class EnvelopeShapeTest(unittest.TestCase):
    def test_job_envelope_is_hp_enc(self):
        text = _read(os.path.join("envelopes", "job-campaign.txt"))
        self.assertTrue(text.startswith("[HOMING-PIGEON] job "))
        body = text.split("\n\n", 1)[1]
        enc = json.loads(body)
        self.assertIn("hp_enc", enc)
        self.assertEqual(enc["hp_enc"]["alg"], "aes-256-gcm/hkdf-sha384")
        self.assertIn("nonce", enc["hp_enc"])
        self.assertIn("ct", enc["hp_enc"])


class PostureAndAuditShapeTest(unittest.TestCase):
    def test_posture_card_has_expected_lines(self):
        text = _read("posture.txt")
        self.assertIn("Security posture", text)
        self.assertIn("[OK  ] secrets        shared_secret: strong", text)
        self.assertIn("[WARN] confinement    bwrap not installed", text)
        self.assertIn("[OK  ] audit log      no audit entries yet", text)

    def test_audit_report_is_empty(self):
        text = _read("audit-report.txt")
        self.assertIn("no audit entries in this window", text)
        self.assertIn("none", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
