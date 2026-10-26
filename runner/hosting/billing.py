# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Metering and prepaid billing (Phase 4): one usage event per job,
a per-target price table, a prepaid balance per tenant, and a Stripe
webhook handler that only ever adds credit. Nothing here charges a
card after the fact.

DORMANT. Nothing in the runner, the Worker or the CLI calls this
module yet; it is tested so it is ready, not because it runs. It is
wired in only when a user asks to pay (docs/project/hosting.md,
"Not yet"), and the price table is a placeholder until then.

Amounts are integer cents. Stripe signatures are verified with the
standard library (HMAC-SHA-256 over `t.payload`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time

# Cents. Linux resident is a flat monthly rate per machine; ephemeral
# targets are per minute. Placeholder values: the operator sets the
# real table outside the code (docs/project/hosting.md, "Billing").
PRICES = {
    "linux-resident": {"unit": "month", "cents": 500},
    "linux-ephemeral": {"unit": "minute", "cents": 1},
    "windows-ephemeral": {"unit": "minute", "cents": 2},
    "macos-ephemeral": {"unit": "minute", "cents": 10},
}
# What a job on an ephemeral target must be able to cover before it
# boots: the drain window at the target's rate.
RESERVE_MINUTES = 15


def price_for(target, quantity):
    """Cents for `quantity` units of `target`. Unknown target raises."""
    row = PRICES.get(target)
    if row is None:
        raise ValueError(f"unknown target {target!r}")
    q = int(quantity)
    if q < 0:
        raise ValueError("quantity must be non-negative")
    return q * int(row["cents"])


def reserve_for(target, minutes=RESERVE_MINUTES):
    row = PRICES.get(target)
    if row is None:
        raise ValueError(f"unknown target {target!r}")
    if row["unit"] == "month":
        return int(row["cents"])
    return int(minutes) * int(row["cents"])


class Ledger:
    """Per-tenant prepaid balances and the usage events against them.
    A JSON file; every mutation is appended as an event so the
    balance can be rebuilt from the events alone."""

    def __init__(self, path):
        self.path = path
        self.events = []
        self.frozen = set()
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            ev = data.get("events")
            if isinstance(ev, list):
                self.events = [e for e in ev if isinstance(e, dict)]
            fr = data.get("frozen")
            if isinstance(fr, list):
                self.frozen = {t for t in fr if isinstance(t, str)}

    def save(self):
        folder = os.path.dirname(os.path.abspath(self.path)) or "."
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".ledger-", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"events": self.events,
                           "frozen": sorted(self.frozen)}, fh, indent=2,
                          sort_keys=True)
                fh.write("\n")
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _append(self, kind, tenant, cents, **extra):
        rec = {"kind": kind, "tenant": tenant, "cents": int(cents),
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        rec.update(extra)
        self.events.append(rec)
        return rec

    def balance(self, tenant):
        total = 0
        for e in self.events:
            if e.get("tenant") != tenant:
                continue
            c = e.get("cents")
            if not isinstance(c, int):
                continue
            if e.get("kind") in ("topup",):
                total += c
            elif e.get("kind") in ("usage", "refund", "adjust"):
                total -= c
        return total

    def seen(self, stripe_event_id):
        return any(e.get("stripe_event") == stripe_event_id
                   for e in self.events)

    def topup(self, tenant, cents, stripe_event=None):
        if int(cents) <= 0:
            raise ValueError("a top-up must be positive")
        if stripe_event and self.seen(stripe_event):
            return None  # Stripe retries; the first delivery won
        return self._append("topup", tenant, cents, stripe_event=stripe_event)

    def refund(self, tenant, cents, stripe_event=None):
        if int(cents) <= 0:
            raise ValueError("a refund must be positive")
        if stripe_event and self.seen(stripe_event):
            return None
        return self._append("refund", tenant, cents, stripe_event=stripe_event)

    def freeze(self, tenant, reason, stripe_event=None):
        self.frozen.add(tenant)
        return self._append("freeze", tenant, 0, reason=reason,
                            stripe_event=stripe_event)

    def can_cover(self, tenant, target):
        """Whether a job on `target` may start: not frozen, and the
        balance covers the target's reserve."""
        if tenant in self.frozen:
            return False, "tenant is frozen (dispute open)"
        need = reserve_for(target)
        have = self.balance(tenant)
        if have < need:
            return False, (f"balance {have} cents is under the {target} "
                           f"reserve of {need} cents")
        return True, "ok"

    def usage(self, tenant, target, quantity, job_id=None, **extra):
        cents = price_for(target, quantity)
        return self._append("usage", tenant, cents, target=target,
                            quantity=int(quantity), job_id=job_id, **extra)

    def statement(self, tenant):
        rows = [e for e in self.events if e.get("tenant") == tenant]
        return {"tenant": tenant, "balance_cents": self.balance(tenant),
                "frozen": tenant in self.frozen, "events": rows}


# --- Stripe webhooks: top-ups in, nothing out ---------------------------

class SignatureError(Exception):
    pass


def verify_stripe_signature(payload, sig_header, secret, tolerance=300,
                            now=None):
    """Stripe's scheme: `Stripe-Signature: t=<ts>,v1=<hex>[,v1=...]`,
    HMAC-SHA-256 of `<ts>.<payload>` under the endpoint secret, and a
    timestamp inside `tolerance` seconds of now."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not isinstance(sig_header, str):
        raise SignatureError("missing Stripe-Signature header")
    parts = {}
    sigs = []
    for item in sig_header.split(","):
        k, _, v = item.strip().partition("=")
        if k == "v1":
            sigs.append(v)
        elif k:
            parts[k] = v
    ts = parts.get("t")
    if not ts or not ts.isdigit() or not sigs:
        raise SignatureError("malformed Stripe-Signature header")
    now = time.time() if now is None else now
    if abs(now - int(ts)) > tolerance:
        raise SignatureError("Stripe-Signature timestamp outside tolerance")
    want = hmac.new(secret.encode("utf-8"), ts.encode("ascii") + b"." + payload,
                    hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(want, s) for s in sigs):
        raise SignatureError("Stripe-Signature does not match")
    return True


def handle_stripe_event(ledger, payload, sig_header, secret, now=None):
    """Verify, then apply the one thing each event means. Returns a
    short dict saying what happened; unknown events are ignored, a
    repeated event id is a no-op."""
    verify_stripe_signature(payload, sig_header, secret, now=now)
    try:
        event = json.loads(payload)
    except ValueError:
        raise SignatureError("payload is not JSON")
    if not isinstance(event, dict):
        raise SignatureError("payload is not an event object")
    kind = event.get("type")
    eid = event.get("id")
    obj = ((event.get("data") or {}).get("object") or {}) \
        if isinstance(event.get("data"), dict) else {}
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) \
        else {}
    tenant = meta.get("tenant")
    if kind in ("checkout.session.completed", "payment_intent.succeeded"):
        if not tenant:
            return {"applied": False, "why": "no tenant in metadata"}
        if kind == "checkout.session.completed" \
                and obj.get("payment_status") not in (None, "paid"):
            return {"applied": False, "why": "session not paid"}
        cents = obj.get("amount_total") if kind == "checkout.session.completed" \
            else obj.get("amount_received")
        if not isinstance(cents, int) or cents <= 0:
            return {"applied": False, "why": "no positive amount"}
        rec = ledger.topup(tenant, cents, stripe_event=eid)
        return {"applied": rec is not None, "kind": "topup",
                "tenant": tenant, "cents": cents,
                "why": "duplicate" if rec is None else "ok"}
    if kind == "charge.refunded":
        if not tenant:
            return {"applied": False, "why": "no tenant in metadata"}
        cents = obj.get("amount_refunded")
        if not isinstance(cents, int) or cents <= 0:
            return {"applied": False, "why": "no positive amount"}
        rec = ledger.refund(tenant, cents, stripe_event=eid)
        return {"applied": rec is not None, "kind": "refund",
                "tenant": tenant, "cents": cents,
                "why": "duplicate" if rec is None else "ok"}
    if kind == "charge.dispute.created":
        if not tenant:
            return {"applied": False, "why": "no tenant in metadata"}
        ledger.freeze(tenant, "dispute", stripe_event=eid)
        return {"applied": True, "kind": "freeze", "tenant": tenant}
    return {"applied": False, "why": f"ignored event type {kind!r}"}
