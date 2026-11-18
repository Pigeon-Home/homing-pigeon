# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Tunnel chaining: the chain body, its sealing, and its opening.

A chain carries one job envelope across two or more runners in
sequence, where no single network path joins the sender to the
final runner. Each leg is a hop, and a hop is a sealed envelope
addressed to the next runner: the chain body defined here,
signed, encrypted into the standing `hp_enc` envelope, and
signed again, exactly as a job is carried. The design record is
docs/steady/design/tunnel-chaining-design.md.

The chain body carries the next hop's envelope whole, as text:
its subject line and its body. A relay opens only its own hop,
with the hop secret the envelope's key_id names, and forwards
the carried text untouched. It never verifies, decrypts, or
judges the next hop's envelope, and it never needs the carried
job's secret.

This module is the sender's and the relay's shared shape: the
subject grammar, the body's members, the sealing a sender
applies, the opening a relay applies, and the structural
checks both sides agree on. Admission policy (freshness,
audience, the door policy, the replay cache) belongs to the
handler in runner/ops/chain.py, the way a query's does.

Stdlib only, Python 3.9+.
"""

import re
from datetime import datetime, timezone

try:
    from runner.wire import jobcrypto as _jobcrypto
    from runner.wire import subject as _subject
    from runner.wire.verify import (
        canonical_key_id, secret_named, sign_payload,
        verify_body_keyed)
except ImportError:  # running from inside runner/ as __main__
    from wire import jobcrypto as _jobcrypto  # type: ignore
    from wire import subject as _subject  # type: ignore
    from wire.verify import (  # type: ignore
        canonical_key_id, secret_named, sign_payload,
        verify_body_keyed)

CHAIN_KIND = "chain"

# The subject grammar for a chain envelope, from the one
# grammar module: the marker, any words, the kind, the id.
# Group 1 is the kind, group 2 the chain id.
CHAIN_SUBJECT_RE = re.compile(_subject.pattern_kind("chain"),
                              re.I)

# What a carried envelope's subject may be: a job for the final
# runner, or another chain hop for a longer chain.
_NEXT_SUBJECT_RE = re.compile(
    _subject.pattern_kind("job|chain"), re.I)


class ChainError(ValueError):
    """Any chain body defect. A ValueError so the mail path's
    existing rejection handling treats it as a bad body."""


def chain_subject(chain_id):
    """The subject line a chain envelope travels under."""
    return f"[HOMING-PIGEON] chain {chain_id}"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_chain_body(chain_id, next_subject, next_body, to=None,
                     issued_at=None, key_id=""):
    """The chain body a sender seals: the next hop's envelope,
    carried whole. `to` is an optional routing label for the
    operator's eye; no check reads it. `key_id` names the hop
    secret, as a job names its key."""
    if not isinstance(chain_id, str) or not chain_id:
        raise ChainError("chain_id must be a non-empty string")
    if not isinstance(next_subject, str) or not next_subject:
        raise ChainError("next_subject must be a non-empty string")
    if not isinstance(next_body, str) or not next_body:
        raise ChainError("next_body must be a non-empty string")
    body = {
        "v": 1,
        "type": CHAIN_KIND,
        "chain_id": chain_id,
        "issued_at": issued_at or _now(),
        "next_subject": next_subject,
        "next_body": next_body,
    }
    if to:
        body["to"] = to
    if key_id:
        body["key_id"] = key_id
    return body


def seal_chain_body(chain_body, secret, key_id=""):
    """Sign a chain body and encrypt it into its envelope, the
    standing two signature discipline: the envelope is verified
    before it is decrypted, and the body inside is verified
    again after. Returns the transmitted body text. The
    envelope's decryption is bound to the chain id, so an
    envelope replayed under a different subject does not open.
    """
    if not isinstance(chain_body, dict):
        raise ChainError("chain body must be an object")
    chain_id = chain_body.get("chain_id")
    if not isinstance(chain_id, str) or not chain_id:
        raise ChainError("chain body carries no chain_id")
    signed = sign_payload(dict(chain_body), secret)
    return _jobcrypto.encrypt_body(signed, secret,
                                   job_id=chain_id,
                                   key_id=key_id or "",
                                   sign=sign_payload)


def seal_chain(chain_id, next_subject, next_body, secret,
               key_id="", to=None, issued_at=None):
    """Build and seal a chain hop in one call. Returns the
    (subject, body) pair the sender drops on its transport."""
    body = build_chain_body(chain_id, next_subject, next_body,
                            to=to, issued_at=issued_at,
                            key_id=key_id)
    return chain_subject(chain_id), seal_chain_body(
        body, secret, key_id=key_id)


def open_chain_body(body_text, secrets, chain_id):
    """Verify a transmitted chain envelope and open it.

    Returns (payload, key_id, secret, encrypted), the admission
    shape every non job object in this suite comes back in: an
    `hp_enc` envelope is verified, decrypted under chain_id
    (the id in the subject), and the chain body inside is
    verified with the same key; a cleartext body comes back
    with encrypted False, and the caller decides whether that
    form is allowed. Raises ValueError on a bad signature and
    JobCryptoError on a bad envelope.
    """
    if not isinstance(chain_id, str):
        chain_id = ""
    payload, key_id = verify_body_keyed(body_text, secrets)
    secret = secret_named(secrets, key_id)
    enc = payload.get("hp_enc") if isinstance(payload, dict) \
        else None
    if not isinstance(enc, dict):
        return payload, key_id, secret, False
    if not _jobcrypto.is_envelope(payload):
        raise ChainError("malformed encryption envelope")
    inner_text = _jobcrypto.decrypt_body(
        payload, secret, job_id=chain_id, key_id=key_id)
    inner, inner_key = verify_body_keyed(inner_text, secrets)
    # The two key ids must name the same secret, the standing
    # rule for every encrypted object the suite admits.
    if canonical_key_id(secrets, inner_key) != \
            canonical_key_id(secrets, key_id):
        raise ChainError(
            "encrypted envelope key_id does not match its body")
    return inner, key_id, secret, True


def validate_chain_body(payload, chain_id):
    """The structural checks on an opened chain body. Returns a
    refusal reason, or None when the body is shaped as a hop.
    Freshness, audience, and policy are the handler's checks,
    not this module's."""
    if not isinstance(payload, dict):
        return "chain body must be a JSON object"
    if payload.get("type") != CHAIN_KIND:
        return "unsupported type (not a chain body)"
    if payload.get("chain_id") != chain_id:
        return "chain_id mismatch between subject and body"
    for name in ("next_subject", "next_body"):
        value = payload.get(name)
        if not isinstance(value, str) or not value:
            return f"{name} missing or not a string"
    if not _NEXT_SUBJECT_RE.search(payload["next_subject"]):
        return ("next_subject is not a job or chain envelope "
                "subject")
    return None
