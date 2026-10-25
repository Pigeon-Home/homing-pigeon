"""Poll helper.

Extracted from runner.py.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def poll_once(cfg, base_dir: str, seen: dict, seen_path: str,
              imap=None, smtp=None, opts=None):
    """One poll cycle. imap/smtp may be injected (tests)."""
    from runner import runner as R

    if not isinstance(seen, dict):
        seen = {}
    t0 = time.monotonic()
    # The HMAC shared secret is always the dedicated shared_secret field,
    # separate from the mailbox password. Both sides use its UTF-8 bytes
    # as the HMAC-SHA-384 key. No hashing or derivation — the SI uses it
    # as-is.
    secrets = R.build_secrets(cfg)
    key_policies = R.build_key_policies(cfg)
    retain_days = R._retention_days(cfg)
    R.prune_retained(base_dir, retain_days)
    R.prune_sent(base_dir, retain_days)
    # Built-in resource monitor: on by default. Threshold crossings
    # become security events for the DRI trigger evaluation.
    if R._resources is not None:
        try:
            event = R._resources.checkR._resources(cfg, base_dir)
            R._note_resource_event(base_dir, event)
        except Exception as e:
            R.log(f"resource monitor failed: {e}", "WARN")
    # Local watches file alerts before the page check, so a trip that
    # happened since the last poll can page on this cycle.
    R._local_watch(cfg, base_dir)
    # DRI playbook: evaluate page triggers once per cycle. Disabled
    # by default; needs a configured channel to actually send.
    if R._dri is not None:
        try:
            R._dri.maybe_page(cfg, base_dir)
        except Exception as e:
            R.log(f"DRI evaluation failed: {e}", "WARN")
    board = R.Board(os.path.join(base_dir, "board.json"))
    cfg["board"] = board
    if not getattr(R.log, "identity_logged", False):
        R.log(f"runner identity: {cfg.get('mailbox_user') or '(unset)'} -- accepting signed jobs from any sender")
        R.log.identity_logged = True  # pyrefly: ignore[missing-attribute]  # intentional monkey-patch: one log line per process
    transport_names = R._enabled_transports(cfg)
    if imap is not None or smtp is not None:
        # Injected-client compatibility path: the diagnostic
        # harness and the local SI test hand poll_once a mailbox
        # pair directly and expect the mail core to run on it.
        # Production never reaches here -- the email transport
        # extension owns the mailbox and jobs arrive through its
        # channel like every other transport's.
        own_imap = imap is None
        own_smtp = smtp is None
        try:
            if own_imap:
                imap = R.connect_imap(cfg)
            if own_smtp:
                smtp = R.connect_smtp(cfg)
            try:
                mails = R.fetch_job_mails(imap)
                if mails:
                    R.log(f"poll: {len(mails)} message(s)")
                    workers = R._worker_count(cfg, opts)
                    if workers > 1:
                        R.log(f"poll: {workers} workers")
                else:
                    workers = R._worker_count(cfg, opts)
                    vR.log(f"poll: no new messages "
                         f"(seen holds {len(seen)})")
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futs = [ex.submit(R.handle_mail, cfg, imap, smtp, seq, raw,
                                      base_dir, seen, secrets, opts,
                                      key_policies)
                            for seq, raw in mails]
                    for f in as_completed(futs):
                        exc = f.exception()
                        # One worker blowing up must not fail the cycle or
                        # throw away the messages the other workers finished.
                        if exc is not None:
                            R.log(f"worker raised: {exc!r}", "ERROR")
                if len(seen) > SEEN_CAP:
                    # save_seen caps the disk copy; keep memory in step.
                    for k in list(seen.keys())[:-SEEN_CAP]:
                        del seen[k]
                R.save_seen(seen_path, seen)
                vR.log(f"poll: {len(mails)} message(s) handled by "
                     f"{workers} worker(s) in "
                     f"{time.monotonic() - t0:.1f}s; "
                     f"seen holds {len(seen)} job id(s)")
            finally:
                if own_imap:
                    try:
                        imap.logout()
                    except Exception:
                        pass
        finally:
            if own_smtp and smtp is not None:
                try:
                    smtp.quit()
                except Exception:
                    pass
    elif not (opts is not None and getattr(opts, "dry_run", False)):
        # Production path: the supervisor (started by main())
        # owns the transport extension processes. A bare
        # poll_once without one still services the channels --
        # the envelopes are the contract, the processes are the
        # supervisor's concern -- but nothing new will arrive
        # until the extensions run.
        if R._transports is not None:
            sup = R._transports.active_supervisor(cfg, base_dir)
            if sup is not None:
                try:
                    sup.check()
                    sup.settle()
                except Exception as e:
                    R.log(f"transport supervisor check failed: {e}",
                        "WARN")
            else:
                vR.log("transports: no supervisor in this process; "
                     "servicing channels only")
    # Every enabled transport, email included, is serviced
    # through its channel. The core never opens a pipe itself.
    if transport_names and R._transports is not None:
        R._service_transports(cfg, base_dir, seen, seen_path,
                            transport_names, secrets, key_policies,
                            opts)
