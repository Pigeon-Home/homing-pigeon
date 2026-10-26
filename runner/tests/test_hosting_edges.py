"""The hosting code's refusal and failure arms the player never reaches.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

Coverage (2026-10-25, the Platinum baseline) left these never
executed: the webhook's refusals of a payload that is signed but is
not an event, or an event with no tenant or no positive amount; the
two state writers' failure arm, which must leave no temp file behind
and must still raise; and protocol_v2's device-tree read. Each is one
input or one failing call away.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.hosting import base, billing, inventory  # noqa: E402
from runner.wire import protocol_v2  # noqa: E402

SECRET = "whsec_test_0123456789abcdef"


def _signed(payload, ts=1_000_000):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + body,
                   hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


def _event(kind, obj, eid="evt_x"):
    return {"id": eid, "object": "event", "type": kind,
            "data": {"object": obj}}


class WebhookRefusalsTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.led = billing.Ledger(os.path.join(self.td.name, "ledger.json"))

    def tearDown(self):
        self.td.cleanup()

    def _handle(self, payload):
        body, header = _signed(payload)
        return billing.handle_stripe_event(self.led, body, header, SECRET,
                                           now=1_000_100)

    def test_a_signed_payload_that_is_not_an_event_is_refused(self):
        with self.assertRaises(billing.SignatureError):
            self._handle(b"not json at all")
        with self.assertRaises(billing.SignatureError):
            self._handle(b"[1, 2, 3]")
        self.assertEqual(self.led.events, [])

    def test_a_topup_without_a_tenant_or_amount_applies_nothing(self):
        r = self._handle(_event("payment_intent.succeeded",
                                {"amount_received": 500, "metadata": {}}))
        self.assertEqual(r, {"applied": False, "why": "no tenant in metadata"})
        r = self._handle(_event("payment_intent.succeeded",
                                {"amount_received": 0,
                                 "metadata": {"tenant": "alice"}}))
        self.assertEqual(r["why"], "no positive amount")
        r = self._handle(_event("checkout.session.completed",
                                {"amount_total": 500, "payment_status": "unpaid",
                                 "metadata": {"tenant": "alice"}}))
        self.assertEqual(r["why"], "session not paid")
        self.assertEqual(self.led.balance("alice"), 0)

    def test_a_refund_or_dispute_without_a_tenant_applies_nothing(self):
        r = self._handle(_event("charge.refunded",
                                {"amount_refunded": 500, "metadata": {}}))
        self.assertEqual(r["why"], "no tenant in metadata")
        r = self._handle(_event("charge.refunded",
                                {"amount_refunded": "500",
                                 "metadata": {"tenant": "alice"}}))
        self.assertEqual(r["why"], "no positive amount")
        r = self._handle(_event("charge.dispute.created",
                                {"amount": 500, "metadata": {}}))
        self.assertEqual(r["why"], "no tenant in metadata")
        self.assertEqual(self.led.events, [])
        self.assertEqual(self.led.frozen, set())


class StateWriterFailureTest(unittest.TestCase):
    """A write that fails mid-way raises, and leaves no `.ledger-*` or
    `.inventory-*` temp file beside the state file."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.td.cleanup()

    def _leftovers(self):
        return sorted(n for n in os.listdir(self.td.name) if n.startswith("."))

    def test_ledger_save_cleans_its_temp_file_and_raises(self):
        led = billing.Ledger(os.path.join(self.td.name, "ledger.json"))
        led.topup("alice", 100)
        with mock.patch.object(billing.json, "dump",
                               side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                led.save()
        self.assertEqual(self._leftovers(), [])
        self.assertFalse(os.path.exists(led.path))

    def test_inventory_save_cleans_its_temp_file_and_raises(self):
        inv = inventory.Inventory(os.path.join(self.td.name, "hosting.json"))
        inv.place(base.Machine("fly", "m1", name="hp-a", region="iad",
                               state="created", tenant="a", version="1"), "a")
        with mock.patch.object(inventory.json, "dump",
                               side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                inv.save()
        self.assertEqual(self._leftovers(), [])

    def test_a_vanished_temp_file_does_not_mask_the_real_error(self):
        led = billing.Ledger(os.path.join(self.td.name, "ledger.json"))
        real_unlink = os.unlink

        def dump(*a, **k):
            # the temp file is gone before the handler reaches it
            for n in os.listdir(self.td.name):
                if n.startswith(".ledger-"):
                    real_unlink(os.path.join(self.td.name, n))
            raise ValueError("boom")

        with mock.patch.object(billing.json, "dump", side_effect=dump):
            with self.assertRaises(ValueError):
                led.save()
        self.assertEqual(self._leftovers(), [])


class PlatformFactsTest(unittest.TestCase):
    def test_the_device_tree_model_is_appended_when_present(self):
        with mock.patch.object(protocol_v2.os.path, "exists", return_value=True), \
                mock.patch("builtins.open",
                           mock.mock_open(read_data=b"Raspberry Pi 4 Model B\0junk")):
            facts = protocol_v2.platform_facts()
        self.assertTrue(facts.endswith("Raspberry Pi 4 Model B"), facts)
        self.assertIn("py%d.%d" % sys.version_info[:2], facts)

    def test_an_empty_or_unreadable_model_leaves_the_triple(self):
        with mock.patch.object(protocol_v2.os.path, "exists", return_value=True), \
                mock.patch("builtins.open", mock.mock_open(read_data=b"\0")):
            plain = protocol_v2.platform_facts()
        with mock.patch.object(protocol_v2.os.path, "exists", return_value=True), \
                mock.patch("builtins.open", side_effect=OSError("denied")):
            denied = protocol_v2.platform_facts()
        self.assertEqual(plain, denied)
        self.assertEqual(len(plain.split()), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
