# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Chain relay handling.

Extracted from runner.py's dispatch the way query handling
was: a chain envelope is tried in early dispatch, before the
job path, and handled here. The design record is
docs/steady/design/tunnel-chaining-design.md.

The relay's discipline mirrors the job path's, in the order
the job path applies it:

- Admission first: the envelope's signature, its decryption,
  and the chain body's own signature, all under the one hop
  secret the envelope's key_id names. A failure is a refusal:
  logged, recorded as an auth_rejection in the security
  events, the envelope taken, nothing forwarded.
- The cleartext form is refused under the same rule as a
  cleartext job or query: admitted only when the runner was
  started with --allow-cleartext.
- Then the body's shape, its freshness, the audience binding,
  and the key's door policy for the chain door, each a refusal
  of the same shape.
- Replay: the chain id enters the replay cache namespaced as
  a chain's, beside the job ids. A second copy is a replay:
  logged, taken, not forwarded again.
- The forward itself follows the result discipline: the
  carried envelope is stashed in the outbox before the hop is
  committed as seen, then delivered. A stash that cannot be
  written leaves the envelope unconsumed, so the next cycle
  tries again; a delivery that fails stays in the outbox for
  the resend pass, and the channel's own requeue answers a
  channel write that fails after the delivery, exactly as it
  answers a result's.

The relay executes nothing, and it never opens the carried
envelope: the next hop's envelope is forwarded as the text
the chain body carried, byte for byte.
"""

import email
import os

try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore

try:
    from runner.wire import chain as _chain
except ImportError:  # running from inside runner/ as __main__
    from wire import chain as _chain  # type: ignore


def chain_seen_key(cfg, chain_id):
    """The replay cache key for a chain hop: the chain id,
    namespaced as a chain's so a chain and a job that share an
    id never answer for each other, then namespaced by
    runner_id the standing way."""
    R = _runner()
    return R._seen_key(cfg, "chain:" + str(chain_id))


def handle_chain_mail(cfg, imap, smtp, seq, raw, subject, secrets,
                      opts, base_dir, seen=None):
    """Handle [HOMING-PIGEON] chain <chain_id>. Returns True if
    handled: the message was a chain envelope, relayed or
    refused, and the caller should not treat it as a job."""
    R = _runner()
    m = _chain.CHAIN_SUBJECT_RE.search(subject or "")
    if not m:
        return False
    chain_id = m.group(2)

    def refuse(why, event_reason=None):
        R.log(f"chain {chain_id}: refused: {why}", "WARN")
        if event_reason:
            R._auth_reject_event(base_dir, event_reason)
        R._mark(imap, seq, opts)
        return True

    try:
        body = R.get_text_body(email.message_from_bytes(raw))
        payload, key_id, secret, encrypted = _chain.open_chain_body(
            body, secrets, chain_id)
    except R.JobCryptoError as e:
        return refuse(f"bad encrypted envelope: {e}",
                      "bad_encryption")
    except ValueError as e:
        return refuse(f"bad signature: {e}", "bad_signature")
    except RecursionError:
        # Finding F15, generalized: this door parses the raw
        # mail a second time, a few calls deeper than the gate's
        # own parse, and a shape nested in the narrow band
        # between the two crossed the call limit here alone and
        # raised out of the gate, unmarked. The door gives the
        # gate's answer in its own words: refused, and marked.
        return refuse("the mail's shape could not be read")
    if not encrypted and not R._cleartext_jobs_allowed():
        return refuse(
            "cleartext chain refused: the HMAC-only form is not "
            "accepted by default; send the chain encrypted "
            "(hp_enc), or start the runner with "
            "--allow-cleartext", "cleartext_not_supported")
    if not R._version_ok(payload.get("v")):
        return refuse("unsupported version")
    why = _chain.validate_chain_body(payload, chain_id)
    if why:
        return refuse(why)
    ok_ts, why = R._issued_at_ok(payload.get("issued_at"), cfg)
    if not ok_ts:
        return refuse(why)
    # Hardening M5: audience binding. The expected runner_id
    # comes from the loaded config, never from the signed body.
    if not R.audience_allows(cfg, base_dir, payload, key_id,
                             chain_id):
        return refuse("security policy (audience): runner_id "
                      "mismatch", "security_policy")
    door = R._verify.check_door_policy(cfg, secrets, key_id,
                                       "chain")
    if door:
        return refuse(f"key policy: {door}", "key_policy")

    skey = chain_seen_key(cfg, chain_id)
    if seen is not None and seen.get(skey):
        R.log(f"chain {chain_id}: replay; already relayed, not "
              f"forwarded again")
        R._mark(imap, seq, opts)
        return True
    if opts is not None and getattr(opts, "dry_run", False):
        # Dry run: fully non-mutating. Verify everything, change
        # nothing: no forward, no seen update.
        R.log(f"dry-run: would relay chain {chain_id} to its "
              f"next hop")
        return True

    transport = getattr(smtp, "transport", None)
    with R._MAIL_LOCK:
        if seen is not None and seen.get(skey):
            R.log(f"chain {chain_id}: replay; already relayed, "
                  f"not forwarded again")
            R._mark(imap, seq, opts)
            return True
        # The forward is stashed before the hop is committed as
        # seen, the result discipline: a stash that cannot be
        # written leaves the envelope unconsumed, so a crash
        # here is retried, never a lost hop.
        if not R.stash_result(base_dir, skey,
                              dict(payload, job_id=chain_id),
                              payload["next_subject"],
                              payload["next_body"],
                              transport=transport, key_id=key_id,
                              encrypted=False,
                              meta={"chain_id": chain_id}):
            R.log(f"chain {chain_id}: forward not stashed; "
                  f"will retry", "ERROR")
            return True
        if isinstance(seen, dict):
            seen[skey] = True
            R.save_seen(os.path.join(base_dir, "seen.json"), seen,
                        keep_sec=R.seen_keep_sec(cfg))

    def forward(subject, body, to=None):
        R.send_mail(smtp, cfg, subject, body, to=to)

    R.deliver_stash(base_dir, skey, forward, cfg=cfg)
    R.log(f"chain {chain_id}: relayed to its next hop "
          f"(key_id={key_id})")
    R._mark(imap, seq, opts)
    return True
