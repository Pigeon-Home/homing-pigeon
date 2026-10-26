"""Main entry point.

Extracted from runner.py.
"""
from datetime import datetime, timezone, timedelta
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


def main() -> int:
    R = _runner()
    # --help is a document: the groups below are its chapters,
    # in reading order, and the epilog is its worked examples.
    # One deliberate scatter survives the grouping: --no-send
    # stays in "running", away from --quiet and the other
    # off-switches, so the page never reads as a
    # turn-everything-off menu.
    if R._cli is None:
        raise ImportError("runner/ops/cli.py is missing")
    ap = R._cli.build_parser()
    args = ap.parse_args()

    if args.workers is not None and args.workers < 1:
        print("error: --workers must be >= 1", file=sys.stderr)
        return 2

    cfg_path = args.config
    if R._setup is not None and args.setup:
        cfg = R._setup.run_setup_wizard(cfg_path)
    elif not os.path.exists(cfg_path):
        if R._setup is not None and R._setup.is_tty() and R._setup.prompt_yes_no(
                f"No config file at {cfg_path}. Run first-run setup? [Y/n] "):
            cfg = R._setup.run_setup_wizard(cfg_path)
        else:
            print(f"config error: no config file at {cfg_path} "
                  f"(run with --setup)", file=sys.stderr)
            return 2
    else:
        try:
            cfg = R.load_config(cfg_path)
        except Exception as e:
            print(f"config error: {e}", file=sys.stderr)
            return 2
    # Hardening M0: a malformed security block stops startup here,
    # before any mailbox, model, or job work. A missing block is
    # fine -- every security feature stays off.
    if R._security is not None:
        try:
            R._security.validate_security_config(cfg)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 2
        # Hardening M5: audience binding with no runner_id configured
        # has nothing to bind to. Warn instead of silently doing
        # nothing; the setup wizard generates one for fresh configs.
        # Q9 (Decision 1's refuse class): confinement on enforce
        # whose mechanism cannot engage changes what the box
        # protects, so the runner refuses to start and says why,
        # instead of every job finding out one at a time.
        if R._sandbox is not None \
                and R._security.sec_mode(cfg, "confinement") == "enforce":
            problem = R._sandbox.startup_problem()
            if problem:
                print("config error: security.modes.confinement is "
                      "enforce but the sandbox cannot engage: "
                      + problem + ". Refusing to start; fix the "
                      "sandbox, or set confinement to audit or off.",
                      file=sys.stderr)
                return 2
        if R._security.sec_mode(cfg, "audience") != "off" \
                and not cfg.get("runner_id"):
            R.log("WARN: security.modes.audience is not off but "
                "no runner_id is configured; the check is skipped. "
                "Set runner_id (the setup wizard generates one for "
                "fresh configs).", "WARN")
    # Hardening M1b: the size caps must be non-negative integers.
    # 0 means unlimited.
    _err = R._validate_size_caps(cfg)
    if _err:
        print(f"config error: {_err}", file=sys.stderr)
        return 2
    # Decision 1 ("default, not silent"): one line names every
    # present-but-unusable setting that reads as its default.
    if R._defaulted is not None:
        _line = R._defaulted.summary_line(R._defaulted.defaulted_keys(cfg))
        if _line:
            R.log(_line, "WARN")
    # A bad key policy or port is a config error. Checked here so the
    # poll loop is not the thing that discovers it, every cycle.
    try:
        R.build_key_policies(cfg)
        if "imap_port" in cfg:
            _runner()._port(cfg, "imap_port", 993)
        if "smtp_port" in cfg:
            _runner()._port(cfg, "smtp_port", 587)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 2
    if args.inspect:
        return R.run_inspect(cfg, args)
    if args.fetch_sources:
        return R.run_fetch_sources(cfg, args)
    if args.audit_report:
        # Read-only: works with a config that has no mailbox
        # credentials, and never touches the mailbox or config.json.
        _auditreport = R._load_mod("runner.ops.auditreport", "ops.auditreport")
        base_dir = R._base_dir_for(cfg, args.config)
        return _auditreport.main(cfg, base_dir, since=args.since,
                               key=args.key, feature=args.feature)
    if args.posture:
        # Read-only posture report; no mailbox needed.
        _posture = R._load_mod("runner.ops.posture", "ops.posture")
        base_dir = R._base_dir_for(cfg, args.config)
        return _posture.main(cfg, cfg_path, base_dir)
    if args.run_variant:
        # One local fuzz variant through validation and confined
        # execution, outcome as JSON. Deliberately before the
        # mailbox setup gate, like the other one-shot modes: a
        # variant run needs config and the bucket, never a
        # mailbox, and it must work on a box whose mail is not
        # (yet) configured.
        return _runner().run_variant(cfg, args)
    if args.remediation_release:
        # The owner's release door: restore a quarantined job's
        # outputs as one deliberate, recorded act. The Oracle
        # chat reaches the same door through its run tool --
        # one code path, one record, either way in.
        if R._remediation is None:
            print("error: remediation module unavailable",
                  file=sys.stderr)
            return 2
        base_dir = R._base_dir_for(cfg, args.config)
        info = R._remediation.release_quarantine(
            base_dir, args.remediation_release)
        if info is None:
            print(f"no quarantined job "
                  f"{args.remediation_release!r} to release",
                  file=sys.stderr)
            return 1
        if R._security is not None:
            R._security.write_audit_entry(
                base_dir, "remediation", "released", "owner_release",
                job_id=str(args.remediation_release),
                detail=str(info["restored_to"]), cfg=cfg)
        R._append_security_event(base_dir, {
            "type": "remediation_release",
            "at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "job_id": args.remediation_release,
            "restored_to": info["restored_to"],
        })
        print(f"released job {args.remediation_release} -> "
              f"{info['restored_to']}")
        return 0
    # Mailbox auth gate, before any model work. On a TTY the runner
    # offers the Thunderbird-style setup instead of dying; headless
    # (service, automation) keeps the fail-fast config error.
    if not args.local_test and not args.oracle and not args.oracle_cli \
            and R._setup is not None:
        reason = R._setup.needs_setup(cfg)
        if reason:
            if R._setup.is_tty() and R._setup.prompt_yes_no(
                    f"Mailbox auth not configured ({reason}). "
                    f"Run setup now? [Y/n] "):
                cfg = R._setup.run_setup_wizard(cfg_path, cfg)
            else:
                print(f"config error: {reason} (run with --setup)",
                      file=sys.stderr)
                return 2
    if args.diagnose:
        # Black-box gauntlet against the configured system. Runs
        # before any model warm-up or daemon spawning: the harness
        # measures the system as it is, it does not fix it up first.
        _harness = R._load_mod("runner.ops.harness", "ops.harness")
        base_dir = R._base_dir_for(cfg, args.config)
        return _harness.main(cfg, base_dir, cfg_path=args.config,
                           roundtrip_timeout=args.diagnose_timeout)
    if args.faster:
        inf = cfg.get("inference")
        if not isinstance(inf, dict):
            inf = {}
            cfg["inference"] = inf
        # --faster's model; keep in step with
        # install.FASTER_INFERENCE_MODEL. This process only.
        inf["model"] = "qwen2.5:3b"
        if not inf.get("endpoint"):
            inf["endpoint"] = "http://127.0.0.1:11434/v1"
        R.log("inference: --faster, using qwen2.5:3b")
    # One-process CLI overrides land before the R.log bounds load,
    # so the logging family (--R.log-max-bytes, --R.log-backups,
    # --oracle-R.log) takes effect for this process too. The keys
    # are pinned further down, next to the poll loop, so a hot
    # reload cannot undo a flag.
    try:
        overridden = R.apply_cli_overrides(cfg, args)
        # An unknown transport name is a startup error, not a
        # surprise at poll time (checked after the overrides so a
        # --transports flag is validated too).
        R._enabled_transports(cfg)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    # Log bounds (and the oracle.log switch) load before any daemon
    # is spawned, so a spawned daemon can write into oracle.log.
    R._refresh_log_settings(cfg, R._base_dir_for(cfg, args.config))
    R.ensure_inference_ready(cfg)
    # First start has no previous model id, so this pulls once.
    R.update_llama_from_config(cfg)
    if args.oracle:
        return _runner().oracle_window(cfg, args.oracle_port, cfg_path=args.config)
    if args.oracle_cli:
        return _runner().oracle_cli(cfg, cfg_path=args.config)
    if args.local_test:
        _lt = R._load_mod("runner.ops.local_test", "ops.local_test")
        return _lt.main(cfg, browser=args.browser)
    # The shared secret is required in all auth modes and must carry
    # enough entropy to resist offline brute force. It is separate from
    # the mailbox password (which is only a Gmail credential now).
    # Mailbox auth itself was gated (or set up) before the model work.
    try:
        R.validate_shared_secret(cfg.get("shared_secret") or "")
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 2
    # CLI overrides were applied to cfg above, before the R.log
    # bounds loaded; `overridden` names the keys they set.
    # Verbosity resolves here: the flag beats config "verbose",
    # which beats the base level. _runner().log_startup reads the level
    # back off args.
    R._set_verbosity(R._resolve_verbosity(cfg, args.verbose))
    args.verbose_level = R._VERBOSE_LEVEL
    # Cleartext acceptance resolves here, from the flag alone:
    # no config key is consulted, so a config file cannot turn
    # it on and a hot reload cannot change it. _runner().log_startup
    # announces it with a WARN line when it is on.
    R._set_allow_cleartext_jobs(
        bool(getattr(args, "allow_cleartext", False)))
    base_dir = R._base_dir_for(cfg, args.config)
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(os.path.join(base_dir, "work"), exist_ok=True)

    R._LOG_FILE = os.path.join(base_dir, "runner.log")
    R._announce_oracle_log()

    seen_path = os.path.join(base_dir, "seen.json")
    seen = R.load_seen(seen_path)

    _runner().log_startup(cfg, args, base_dir)
    R._report_extensions(cfg, base_dir)
    R._report_oracle_mode(cfg)
    # Local signal front-ends (inbox watcher + loopback listener).
    # Dry-run observes and changes nothing, so it starts neither.
    if getattr(args, "dry_run", False):
        R.log("local signals: not started (dry-run)")
    else:
        R._start_local_signals(cfg, base_dir)
    # Transport extensions: this process supervises the enabled
    # ones for its whole life -- starts them, restarts the dead,
    # stops them at exit. Dry-run observes and starts nothing:
    # a dry run does not even open the mailbox (the email
    # extension owns it now), so a dead mailbox cannot fail one.
    if getattr(args, "dry_run", False):
        R.log("transport extensions: not started (dry-run)")
    if not getattr(args, "dry_run", False) \
            and R._transports is not None:
        try:
            R._transports.start_supervisor(
                cfg, base_dir, log=R.log,
                event_sink=lambda ev: R._append_security_event(base_dir, ev))
            # Extensions live in their own sessions so a dead
            # one cannot take the runner down; the price is that
            # an abrupt exit (Ctrl+C converted by _run, say)
            # would orphan them without this hook. The normal
            # path stops them explicitly at the loop's end.
            import atexit
            atexit.register(R._transports.stop_supervisors,
                            base_dir)
        except Exception as e:
            R.log(f"transport supervisor failed to start: {e}",
                "ERROR")
    # Extension sources: the first run of each extension brings its
    # code and declared sources for the Oracle, in the background,
    # a minute in (the loop's tick starts the pass). A dry run
    # changes nothing and a single cycle has no time for it;
    # --fetch-sources is the foreground door for both.
    R._report_extension_sources(cfg, base_dir)
    if not getattr(args, "dry_run", False) \
            and not getattr(args, "once", False):
        R._extension_sources_start()
    # The outbox backlog, once, plainly: results executed earlier whose
    # delivery is still pending, and the ones given up on (review item
    # 1). An operator whose mail server was down sees it here.
    _backlog = R.outbox_report(base_dir)
    if _backlog["waiting"] or _backlog["failed"]:
        R.log(f"outbox: {len(_backlog['waiting'])} result(s) waiting for "
              f"delivery, {len(_backlog['failed'])} given up "
              f"(--inspect outbox lists them)", "WARN")
    auth_failed = False  # latch: report auth death once, not every 20s
    # Connection credentials (mailbox_user/password, oauth_*) are not
    # hot. Those still need a restart. CLI flags pin their key so a
    # later edit of config.json cannot silently undo them.
    pinned = set(overridden)
    if args.workers is not None:
        pinned.add("workers")
    if args.verbose is not None:
        # A -v/--quiet on the command line is this process's word;
        # a later config edit of "verbose" must not undo it.
        pinned.add("verbose")
    reload_state = {"mtime": os.path.getmtime(args.config)}
    drain = R.drain_plan(args, len(seen))
    try:
        while True:
            # Re-read config if the file changed. Edit config.json all you
            # want — the runner picks it up within one poll interval.
            changed = []
            try:
                previous = {"inference": cfg.get("inference")}
                changed = R.reload_hot_config(cfg, args.config, reload_state,
                                            pinned)
                if changed:
                    R.log(f"config reloaded: {', '.join(changed)} updated, "
                        f"no restart needed")
                    # Pull only when the model id changed. A poll-interval
                    # edit must not re-download the model.
                    if "inference" in changed:
                        R.update_llama_from_config(cfg, previous=previous)
                    # A live "verbose" edit re-resolves the level (the
                    # flag, if any was given, pinned the key, so this
                    # only fires for config-driven verbosity).
                    if "verbose" in changed:
                        R._set_verbosity(R._resolve_verbosity(cfg, args.verbose))
                        args.verbose_level = R._VERBOSE_LEVEL
            except Exception as e:
                R.log(f"config reload failed (keeping old values): {e}", "WARN")
            if not args.once and not getattr(args, "dry_run", False):
                # A config edit may flip the disclosure rule or
                # bring a model online: run the pass now, not later.
                R._extension_sources_tick(cfg, base_dir, due_now=bool(changed))
            try:
                _runner().poll_once(cfg, base_dir, seen, seen_path, opts=args)
                if auth_failed:
                    auth_failed = False
                    # WARN, not INFO. The per-minute cap drops INFO once a
                    # busy process is full, which hid this line from the
                    # mutation job's clean pytest run and can hide a real
                    # recovery on a chatty box.
                    R.log("gmail authentication recovered", "WARN")
            except R.OAuthRefreshError as e:
                # The refresh token is dead; only a human browser login fixes
                # it. Log locally every cycle, but shout to the Event Log once.
                R.log(f"poll cycle failed: {e}", "ERROR")
                if not auth_failed:
                    auth_failed = True
                    _runner().report_event(
                        f"Homing Pigeon: Gmail sign-in failed ({e}). "
                        f"The runner cannot fetch or send mail until someone "
                        f"signs in again on this machine (run the app with "
                        f"--setup, or re-run the OAuth browser login).")
                if args.pdb:
                    import pdb
                    pdb.post_mortem(sys.exc_info()[2])
            except Exception as e:
                R.log(f"poll cycle failed: {e}", "ERROR")
                if args.pdb:
                    import pdb
                    pdb.post_mortem(sys.exc_info()[2])
            if args.once:
                # --drain: an ephemeral box keeps polling until its
                # job count or its clock is spent, then exits like
                # a plain --once. A seen-set growth is a job run.
                if drain is None or not drain.more(len(seen)):
                    break
            try:
                delay = int(cfg.get("poll_interval_sec", 20))
            except (TypeError, ValueError, OverflowError):
                delay = 20
            if delay < 1:
                delay = 20
            time.sleep(delay)
    finally:
        # KeyboardInterrupt from the poll sleep (Ctrl+C, and the tests
        # that raise it) skips the statements after the loop. The
        # supervisor holds extension.log open for the child's stdout.
        # On Windows a still-open file cannot be deleted, so a test
        # TemporaryDirectory — and a real shutdown that removes state —
        # fails with WinError 32. atexit does not run inside a test.
        if R._transports is not None:
            R._transports.stop_supervisors(base_dir)
    R.log("homing-pigeon exiting")
    return 0
