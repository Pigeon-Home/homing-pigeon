"""Startup and board helpers.

Extracted from runner.py.
"""
import email

def log_startup(cfg, args, base_dir):
    """One block: what is configured, what is running, what it expects.

    Never prints a secret. Prints the absence of one.
    A personal-documents hit prints a fixed banner and one WARN
    line. The name that matched is not logged.
    """
    from runner import runner as R

    if (not getattr(args, "ignore_personal_documents", False)
            and _personal_docs is not None):
        try:
            if _personal_docs.warn_if_personal_documents():
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
    auth = "oauth" if _use_oauth(cfg) else "password"
    inf = inference_config(cfg)
    keys = sorted((cfg.get("additional_secrets") or {}).keys())
    R.log(f"homing-pigeon {__version__} invocation: "
        f"{_invocation_line()}")
    R.log(f"homing-pigeon {__version__} starting "
        f"(base={base_dir}, platform={sys.platform})")
    R.log(f"auth={auth} mailbox={cfg.get('mailbox_user')} "
        f"poll={cfg.get('poll_interval_sec', 20)}s "
        f"workers={_worker_count(cfg, args)} "
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
    for kid in unrestricted_extra_keys(cfg):
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
    if _cleartext_jobs_allowed():
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
    from runner import runner as R

    m = re.search(r"\[HOMING-PIGEON\].*?(task_submit|task_request|task_result|task_approve)\s+(\S+)", subject, re.I)
    if not m:
        return False
    kind, ident = m.group(1).lower(), m.group(2)
    def reject(why):
        R.log(f"board reject seq {seq}: {why}", "WARN")
        _mark(imap, seq, opts)
    try:
        body = get_text_body(email.message_from_bytes(raw))
        payload, key_id, secret, encrypted = _admit_object(
            body, secrets, ident)
    except JobCryptoError as e:
        reject(f"bad envelope: {e}")
        _auth_reject_event(base_dir, "bad_encryption", feature="board")
        return True
    except Exception as e:
        reject(f"bad signature: {e}")
        _auth_reject_event(base_dir, "bad_signature")
        return True
    if not encrypted and not _cleartext_jobs_allowed():
        reject("cleartext board message refused")
        _auth_reject_event(base_dir, "cleartext_not_supported", feature="board")
        return True
    # Hardening M5: audience binding for every board message type
    # (task_submit, task_request, task_result, task_approve).
    if not audience_allows(cfg, base_dir, payload, key_id, ident):
        reject("audience mismatch")
        _auth_reject_event(base_dir, "security_policy", feature="audience")
        return True
    if not _version_ok(payload.get("v")):
        reject("unsupported version")
        return True
    try:
        with R._BOARD_LOCK:
            board.reoffer_expired(cfg.get("task_timeout", 86400))
        if kind == "task_submit":
            ok, reason = board.submit(payload)
            reply_subj = f"[HOMING-PIGEON] task_ack {ident}"
            reply_body = {"v": PROTOCOL_VERSION, "type": "task_ack", "task_id": ident, "ok": ok, "reason": reason}
        elif kind == "task_request":
            caps = payload.get("capabilities") or []
            offered = board.offer(ident, caps, key_id, cfg)
            tid = offered.get("task_id") if isinstance(offered, dict) else None
            if offered and tid:
                reply_subj = f"[HOMING-PIGEON] task_offer {tid}"
                reply_body = {"v": PROTOCOL_VERSION, "type": "task_offer", "task": offered}
            else:
                reply_subj = "[HOMING-PIGEON] task_offer empty"
                reply_body = {"v": PROTOCOL_VERSION, "type": "task_offer", "empty": True}
        elif kind == "task_result":
            require_review = cfg.get("require_review", False)
            status, reason = board.complete(ident, payload.get("result"), require_review)
            reply_subj = f"[HOMING-PIGEON] task_ack {ident}"
            reply_body = {"v": PROTOCOL_VERSION, "type": "task_ack", "task_id": ident, "status": status, "reason": reason}
        elif kind == "task_approve":
            ok, reason = board.approve(ident)
            reply_subj = f"[HOMING-PIGEON] task_ack {ident}"
            reply_body = {"v": PROTOCOL_VERSION, "type": "task_ack", "task_id": ident, "ok": ok, "reason": reason}
        else:
            reject("unknown board kind")
            return True
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
        send_mail(smtp, cfg, reply_subj, _seal_reply(
            reply_body, secret, reply_subj.rsplit(" ", 1)[-1],
            key_id, encrypted), to=_valid_reply_to(payload))
    _mark(imap, seq, opts)
    return True


