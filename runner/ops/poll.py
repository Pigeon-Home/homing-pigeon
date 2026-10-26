import os
import sys
import time


from typing import Any


def _runner() -> Any:
    """The live runner module, looked up at call time.

    `runner.runner` when the suite or a package import loaded it,
    `__main__` when runner.py was started as a script (an install,
    the one-file binaries), where `runner` is the file itself and
    `from runner import runner` raises "'runner' is not a package".
    """
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "_load_mod", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R
"""Poll helper.

Extracted from runner.py.
"""

def poll_once(cfg, base_dir: str, seen: dict, seen_path: str,
              imap=None, smtp=None, opts=None):
    """One poll cycle. imap/smtp may be injected (tests)."""
    R = _runner()
    if not isinstance(seen, dict):
        seen = {}
    t0 = time.monotonic()
    # The HMAC shared secret is always the dedicated shared_secret field,
    # separate from the mailbox password. Both sides use its UTF-8 bytes
    # as the HMAC-SHA-384 key. No hashing or derivation — the SI uses it
    # as-is.
    secrets = _runner().build_secrets(cfg)
    key_policies = _runner().build_key_policies(cfg)
    retain_days = _runner()._retention_days(cfg)
    _runner().prune_retained(base_dir, retain_days)
    _runner().prune_sent(base_dir, retain_days)
    # Built-in resource monitor: on by default. Threshold crossings
    # become security events for the DRI trigger evaluation.
    if _runner()._resources is not None:
        try:
            event = _runner()._resources.check_resources(cfg, base_dir)
            _runner()._note_resource_event(base_dir, event)
        except Exception as e:
            R.log(f"resource monitor failed: {e}", "WARN")
    # Local watches file alerts before the page check, so a trip that
    # happened since the last poll can page on this cycle.
    _runner()._local_watch(cfg, base_dir)
    # DRI playbook: evaluate page triggers once per cycle. Disabled
    # by default; needs a configured channel to actually send.
    if _runner()._dri is not None:
        try:
            _runner()._dri.maybe_page(cfg, base_dir)
        except Exception as e:
            R.log(f"DRI evaluation failed: {e}", "WARN")
    board = _runner().Board(os.path.join(base_dir, "board.json"))
    cfg["board"] = board
    if not getattr(_runner().log, "identity_logged", False):
        R.log(f"runner identity: {cfg.get('mailbox_user') or '(unset)'} -- accepting signed jobs from any sender")
        _runner().log.identity_logged = True  # pyrefly: ignore[missing-attribute]  # intentional monkey-patch: one _runner().log line per process
    transport_names = _runner()._enabled_transports(cfg)
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
                imap = _runner().connect_imap(cfg)
            if own_smtp:
                smtp = _runner().connect_smtp(cfg)
            try:
                mails = _runner().fetch_job_mails(imap)
                if mails:
                    R.log(f"poll: {len(mails)} message(s)")
                    workers = _runner()._worker_count(cfg, opts)
                    if workers > 1:
                        R.log(f"poll: {workers} workers")
                else:
                    workers = _runner()._worker_count(cfg, opts)
                    _runner().vlog(f"poll: no new messages "
                         f"(seen holds {len(seen)})")
                with _runner().ThreadPoolExecutor(max_workers=workers) as ex:
                    futs = [ex.submit(_runner().handle_mail, cfg, imap, smtp, seq, raw,
                                      base_dir, seen, secrets, opts,
                                      key_policies)
                            for seq, raw in mails]
                    for f in _runner().as_completed(futs):
                        exc = f.exception()
                        # One worker blowing up must not fail the cycle or
                        # throw away the messages the other workers finished.
                        if exc is not None:
                            R.log(f"worker raised: {exc!r}", "ERROR")
                # The resend pass (review item 1): results stashed by
                # an earlier cycle whose send failed go out again,
                # past their backoff, before the seen-set is saved.
                if not (opts is not None and getattr(opts, "dry_run", False)):
                    def resend(subject, body, to):
                        _runner().send_mail(smtp, cfg, subject, body, to=to)
                    _runner().resend_stashed(base_dir, cfg, resend)
                if len(seen) > _runner().SEEN_CAP:
                    # _runner().save_seen caps the disk copy; keep memory in step.
                    for k in list(seen.keys())[:-_runner().SEEN_CAP]:
                        del seen[k]
                _runner().save_seen(seen_path, seen)
                _runner().vlog(f"poll: {len(mails)} message(s) handled by "
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
        if _runner()._transports is not None:
            sup = _runner()._transports.active_supervisor(cfg, base_dir)
            if sup is not None:
                try:
                    sup.check()
                    sup.settle()
                except Exception as e:
                    R.log(f"transport supervisor check failed: {e}",
                        "WARN")
            else:
                _runner().vlog("transports: no supervisor in this process; "
                     "servicing channels only")
    # Every enabled transport, email included, is serviced
    # through its channel. The core never opens a pipe itself.
    if transport_names and _runner()._transports is not None:
        _runner()._service_transports(cfg, base_dir, seen, seen_path,
                            transport_names, secrets, key_policies,
                            opts)
