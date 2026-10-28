"""Startup and board helpers.

Extracted from runner.py.
"""
import email
import json
import os
import re


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore
import email

def log_startup(cfg, args, base_dir):
    """One block: what is configured, what is running, what it expects.

    Never prints a secret. Prints the absence of one.
    A personal-documents hit prints a fixed banner and one WARN
    line. The name that matched is not logged.
    """
    R = _runner()
    if (not getattr(args, "ignore_personal_documents", False)
            and _runner()._personal_docs is not None):
        try:
            if _runner()._personal_docs.warn_if_personal_documents():
                R.log("personal-documents check tripped. "
                    "No file was opened and no name was recorded.",
                    "WARN")
        except Exception:
            pass
    # The verbosity level main() resolved (flag beats config).
    # Direct callers (tests, doors) may not carry one; fall back
    # to the old boolean reading of args.verbose.
    _lvl = getattr(args, "verbose_level", None)
    if _lvl is None:
        _lvl = 1 if getattr(args, "verbose", False) else 0
    auth = "oauth" if _runner()._use_oauth(cfg) else "password"
    inf = _runner().inference_config(cfg)
    keys = sorted((cfg.get("additional_secrets") or {}).keys())
    R.log(f"homing-pigeon {_runner().__version__} invocation: "
        f"{_runner()._invocation_line()}")
    R.log(f"homing-pigeon {_runner().__version__} starting "
        f"(base={base_dir}, platform={_runner().sys.platform})")
    R.log(f"auth={auth} mailbox={cfg.get('mailbox_user')} "
        f"poll={cfg.get('poll_interval_sec', 20)}s "
        f"workers={_runner()._worker_count(cfg, args)} "
        f"timeout={cfg.get('default_timeout_sec', 300)}s")
    R.log(f"judge={cfg.get('judge') or 'off'} "
        f"ceiling={cfg.get('max_result_view') or 'full'} "
        f"workspace={cfg.get('workspace_root') or '(none)'}")
    if inf:
        R.log(f"ask=on model={inf.get('model')} endpoint={inf.get('endpoint')}")
    else:
        R.log("ask=off; no loopback model in config. "
            "Installer sets this unless --no-inference was passed.")
    if keys:
        R.log(f"additional secrets: {', '.join(keys)}")
    for kid in _runner().unrestricted_extra_keys(cfg):
        R.log(f"key {kid!r} has no key_policies entry: it is unrestricted "
            f"(add a policy, or set key_policies_default_deny)", "WARN")
    flags = []
    if args.dry_run:
        flags.append("dry-run (will not execute)")
    if args.no_send:
        flags.append("no-send (will not mail results)")
    if args.once:
        flags.append("once")
    if _lvl >= 2:
        flags.append("verbose (decision lines on)")
    elif _lvl == 1:
        flags.append("verbose")
    if flags:
        R.log("flags: " + ", ".join(flags))
    R.log("expects: signed [HOMING-PIGEON] job messages. "
        "Signature is the only gate. Results return to this mailbox.")
    if not cfg.get("workspace_root"):
        R.log("confinement is off; workspace_root is not set", "WARN")
    if _runner()._cleartext_jobs_allowed():
        R.log("cleartext (HMAC-only) jobs are ACCEPTED by this "
            "process (--allow-cleartext): a signed job whose "
            "body is not encrypted will execute, and its result "
            "returns in cleartext. The HMAC signature is still "
            "required; every hop can read job and result bodies.",
            "WARN")
    if _lvl >= 1:
        safe = {k: cfg.get(k) for k in (
            "poll_interval_sec", "workers", "default_timeout_sec",
            "max_output_bytes", "max_job_age_sec", "max_result_view",
            "max_query_budget", "max_queries_per_hour",
            "output_retention_days", "judge", "workspace_root",
            "protected_paths", "dag_mode",
            "require_review", "worker_allowlist")}
        R.log(f"config: {json.dumps(safe, default=str)}")
        R.log("verbose: job lines, reject reasons, and query ops. "
            "Empty polls are silent. Cap is 200 lines a minute.")
        if _lvl >= 2:
            R.log("verbose: this run narrates its decisions: poll "
                "cycles, ingest, the wake gate, judge verdicts, "
                "and board offers.")


def handle_board_mail(cfg, imap, smtp, seq, raw, subject, board, secrets, opts, base_dir):
    """Handle task_submit / task_request / task_result / task_approve. Returns True if handled."""
    R = _runner()
    m = re.search(r"\[HOMING-PIGEON\].*?(task_submit|task_request|task_result|task_approve)\s+(\S+)", subject, re.I)
    if not m:
        return False
    kind, ident = m.group(1).lower(), m.group(2)
    def reject(why):
        R.log(f"board reject seq {seq}: {why}", "WARN")
        _runner()._mark(imap, seq, opts)
    try:
        body = _runner().get_text_body(email.message_from_bytes(raw))
        payload, key_id, secret, encrypted = _runner()._admit_object(
            body, secrets, ident)
    except _runner().JobCryptoError as e:
        reject(f"bad envelope: {e}")
        _runner()._auth_reject_event(base_dir, "bad_encryption", feature="board")
        return True
    except Exception as e:
        reject(f"bad signature: {e}")
        _runner()._auth_reject_event(base_dir, "bad_signature")
        return True
    if not encrypted and not _runner()._cleartext_jobs_allowed():
        reject("cleartext board message refused")
        _runner()._auth_reject_event(base_dir, "cleartext_not_supported", feature="board")
        return True
    # Hardening M5: audience binding for every board message type
    # (task_submit, task_request, task_result, task_approve).
    if not _runner().audience_allows(cfg, base_dir, payload, key_id, ident):
        reject("audience mismatch")
        _runner()._auth_reject_event(base_dir, "security_policy", feature="audience")
        return True
    if not _runner()._version_ok(payload.get("v")):
        reject("unsupported version")
        return True
    # Q98 items 12, 13, 16: a board message is held to a job's
    # authorization (PROTOCOL.md section 13.7). Its type is the one
    # the subject announces, its identifier is the subject's, its
    # key may use the board, it is fresh, and the same signed
    # message is acted on once.
    if payload.get("type") != kind:
        reject("board message type does not match the subject")
        return True
    id_field = "worker_id" if kind == "task_request" else "task_id"
    if id_field in payload and payload.get(id_field) != ident:
        reject(f"board {id_field} does not match the subject")
        return True
    fresh, why = _runner()._issued_at_ok(payload.get("issued_at"), cfg)
    if not fresh:
        reject(why)
        return True
    # Freshness before the key's door policy, as section 5 orders a
    # job's checks (Q103 item 3).
    why = _runner()._verify.check_door_policy(cfg, secrets, key_id, "board")
    if why:
        reject(f"key policy: {why}")
        _runner()._auth_reject_event(base_dir, "security_policy", feature="board")
        return True
    seen_path = os.path.join(base_dir, "seen.json") \
        if isinstance(base_dir, str) and base_dir else ""
    seen = _runner().load_seen(seen_path) if seen_path else {}
    sig = payload.get("sig") if isinstance(payload.get("sig"), str) else ""
    skey = _runner()._seen_key(cfg, f"board:{kind}:{ident}:{sig[:32]}")
    if seen.get(skey):
        R.log(f"board {kind} {ident}: the same signed message again; skipped")
        _runner()._mark(imap, seq, opts)
        return True
    holder = _runner().canonical_key_id(secrets, key_id)
    if opts is not None and getattr(opts, "dry_run", False):
        # A dry run verifies and says what it would do: the board is
        # not touched, no reply goes out, the message stays unseen
        # (--dry-run: execute nothing, send nothing, change nothing).
        R.log(f"dry run: board {kind} {ident} verified, not applied")
        return True
    try:
        with R._BOARD_LOCK:
            board.reoffer_expired(cfg.get("task_timeout", 86400))
        if kind == "task_submit":
            ok, reason = board.submit(payload)
            reply_subj = f"[HOMING-PIGEON] task_ack {ident}"
            reply_body = {"v": _runner().PROTOCOL_VERSION, "type": "task_ack", "task_id": ident, "ok": ok, "reason": reason}
        elif kind == "task_request":
            caps = payload.get("capabilities") or []
            offered = board.offer(ident, caps, holder, cfg)
            tid = offered.get("task_id") if isinstance(offered, dict) else None
            if offered and tid:
                reply_subj = f"[HOMING-PIGEON] task_offer {tid}"
                reply_body = {"v": _runner().PROTOCOL_VERSION, "type": "task_offer", "task": offered}
            else:
                reply_subj = "[HOMING-PIGEON] task_offer empty"
                reply_body = {"v": _runner().PROTOCOL_VERSION, "type": "task_offer", "empty": True}
        elif kind == "task_result":
            require_review = cfg.get("require_review", False)
            status, reason = board.complete(ident, payload.get("result"),
                                            require_review, holder=holder)
            reply_subj = f"[HOMING-PIGEON] task_ack {ident}"
            reply_body = {"v": _runner().PROTOCOL_VERSION, "type": "task_ack", "task_id": ident, "status": status, "reason": reason}
        elif kind == "task_approve":
            ok, reason = board.approve(ident)
            reply_subj = f"[HOMING-PIGEON] task_ack {ident}"
            reply_body = {"v": _runner().PROTOCOL_VERSION, "type": "task_ack", "task_id": ident, "ok": ok, "reason": reason}
        else:
            reject("unknown board kind")
            return True
        if seen_path:
            seen[skey] = True
            _runner().save_seen(seen_path, seen,
                                    keep_sec=_runner().seen_keep_sec(cfg))
    except Exception as e:
        # Bad board data must reject this message, not fail the cycle.
        R.log(f"board failed seq {seq}: {e}", "WARN")
        reject("board error")
        return True
    if opts is None or not getattr(opts, "no_send", False):
        # Board replies follow the same routing rule as results
        # (PROTOCOL 3.1 / 13.7): a valid reply_to inside the signed
        # body receives the offer or ack; otherwise the runner's own
        # mailbox does. The From header never chooses.
        # A reply that cannot be sealed or sent (a board file a hand
        # wrote or a crash left can hold text no signer accepts) is
        # logged and the message taken, never raised into the poll,
        # where it would come back on every pass (Q93's rule; Q106).
        # The board's change stands: an offer the worker never saw
        # lapses with its lease.
        try:
            _runner().send_mail(smtp, cfg, reply_subj, _runner()._seal_reply(
                reply_body, secret, reply_subj.rsplit(" ", 1)[-1],
                key_id, encrypted), to=_runner()._valid_reply_to(payload))
        except Exception as e:
            R.log(f"could not send board reply {reply_subj}: {e}", "ERROR")
    _runner()._mark(imap, seq, opts)
    return True


