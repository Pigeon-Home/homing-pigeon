import json
import sys


def _runner():
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
"""Oracle context builder.

Extracted from runner.py.
"""

def oracle_context(base_dir, limit=6, max_chars=8000, log_chars=2000,
                   watch=True) -> str:
    """Recent retained job output plus the runner log tail, for a local
    Oracle question.

    Only safe job ids. Bounded. This is data for the model, not a
    dashboard, and it is not written back to the page. The Oracle also
    watches the box by default, unless watch is False: canary tripwire
    files on every platform, and on Windows a bounded tail of the
    Event Log and a diff of registry persistence locations.
    """
    R = _runner()
    if not isinstance(base_dir, str):
        return ""
    chosen = R._chosen_retained_rows(base_dir, limit)
    if isinstance(max_chars, bool):
        cap = 4000
    else:
        try:
            cap = int(max_chars)
        except (TypeError, ValueError, OverflowError):
            cap = 4000
        if cap < 0:
            cap = 0
    parts = []
    facts = []
    for _mtime, path, job_id in chosen:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        kind, status, when = R._job_facts(data, job_id)
        facts.append(f"job {job_id} ({kind}, {status}, {when})")
        parts.append(R._retained_job_summary(data, job_id, base_dir))
    if facts:
        # The index comes first on purpose: it is the whole job
        # record in a few short lines a small model can read back,
        # it survives the max_chars cap that may cut the detailed
        # blocks below, and it keeps a summary question from being
        # answered out of the log tail's noise instead.
        parts.insert(0, "Job index (newest first; this is the record "
                        "for summary and status questions):\n"
                        + "\n".join(facts))
    blob = "\n\n".join(parts).strip()
    if not blob:
        blob = "(no job output retained yet)"
    else:
        blob = blob[:cap]
    job_blob_len = len(blob)
    log_tail = R._runner_log_tail(base_dir, log_chars)
    if log_tail:
        blob += ("\n\n---\nRecent runner log "
                 "(last lines of runner.log):\n" + log_tail)
    if job_blob_len < cap:
        snap = R._project_snapshot_note(base_dir)
        if snap:
            blob += "\n\n---\nProject snapshot:\n" + snap
    if watch and job_blob_len < cap:
        # The canary section is telemetry, not job output: it yields
        # when the job portion alone already filled the max_chars
        # budget (or the budget is zero), so the cap stays a cap.
        can = R._canary_watch(base_dir if isinstance(base_dir, str) else "")
        if can:
            blob += ("\n\n---\nCanary watch (tripwire files planted by "
                     "the runner):\n" + can)
    if watch and _runner().sys.platform == "win32" and job_blob_len < cap:
        ev = R._eventlog_tail(base_dir=base_dir if isinstance(base_dir, str) else "")
        if ev is None:
            blob += ("\n\n---\nWindows Event Log: unreadable by the runner "
                     "(no entries shown; do not claim the log is clean).")
        elif ev:
            blob += ("\n\n---\nRecent Windows Event Log (System/Application "
                     "errors and warnings, Security audit failures):\n" + ev)
        else:
            blob += ("\n\n---\nRecent Windows Event Log: no Critical, Error "
                     "or Warning events and no audit failures in the "
                     "recent window.")
        reg = R._registry_watch(base_dir if isinstance(base_dir, str) else "")
        if reg is None:
            blob += ("\n\n---\nWindows registry watch: unreadable by the "
                     "runner (nothing shown; do not claim the registry "
                     "is clean).")
        elif reg:
            blob += ("\n\n---\nWindows registry watch (autorun and "
                     "persistence locations, services):\n" + reg)
    if watch and job_blob_len < cap and _runner().sys.platform != "win32":
        host = R._host_log_tail(base_dir=base_dir if isinstance(base_dir, str) else "")
        if host is None:
            blob += ("\n\n---\nHost log tail: unreadable by the runner "
                     "(no lines shown; do not claim the log is clean).")
        elif host:
            blob += ("\n\n---\nHost log tail (auth failures and error "
                     "lines only):\n" + host)
        else:
            blob += ("\n\n---\nHost log tail: no matching auth failures "
                     "or error lines in the recent window.")
    if watch and job_blob_len < cap:
        fw = R._firewall_watch(base_dir if isinstance(base_dir, str) else "")
        if fw is None:
            blob += ("\n\n---\nFirewall posture: unreadable by the runner "
                     "(nothing shown; do not claim the firewall is on "
                     "or off).")
        elif fw:
            blob += "\n\n---\nFirewall posture:\n" + fw
        av = R._av_watch(base_dir if isinstance(base_dir, str) else "")
        if av is None:
            blob += ("\n\n---\nAV posture: unreadable by the runner "
                     "(nothing shown; do not claim antivirus is on "
                     "or off).")
        elif av:
            blob += "\n\n---\nAV posture:\n" + av
    if job_blob_len < cap:
        # Last on purpose: reference material yields to the watch
        # sections above when the cap bites. Only what the
        # disclosure rule provides is named; a withheld extension
        # source never reaches the context.
        srcs = R._extension_sources_note(base_dir)
        if srcs:
            blob += "\n\n---\n" + srcs
    # max_chars caps the whole context, not just the job portion.
    # A zero cap (zero or negative max_chars) means no context at all.
    if cap <= 0:
        return ""
    return blob[:cap] if len(blob) > cap else blob
