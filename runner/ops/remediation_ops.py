"""Remediation and job helpers.

Extracted from runner.py.
"""
import json
import os
import signal


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore

def _finish_remediation(cfg, st, monitor, job, job_id, work,
                        base_dir, script_path, proc=None):
    """Close out a monitored job: acts, record, member.

    Called after the process has exited (or been killed). A
    mid-run act is already in the monitor's outcome; a tripwire
    the final scan turns up still earns quarantine, referral,
    and the page -- there is just nothing left to kill, so the
    recorded act is the quarantine. The same honesty applies to
    a mid-run kill order that lost the race with a job already
    exiting on its own (POSIX: the exit was not the SIGKILL):
    the act that landed is the quarantine. Returns the result
    member or None when nothing acted.
    """
    R = _runner()
    outcome = monitor.outcome
    try:
        monitor.final_scan()
    except Exception:
        pass
    mode = st["mode"]
    digest = _runner()._remediation.received_digest(job)
    envelope_note = getattr(monitor, "_envelope_note", "")
    for div in outcome.get("divergences") or []:
        _runner().vlog(f"remediation: job {job_id}: divergence "
             f"{_runner()._remediation.divergence_text(div)}")
    for rec in outcome.get("oracle") or []:
        decision = rec.get("decision")
        _runner()._remediation_audit(
            base_dir, cfg, st, job_id,
            "abstained" if decision == "abstain" else "spared",
            rec.get("divergence") or "", rec.get("reason") or "")
    if mode == "off":
        page_div = outcome.get("page")
        if page_div is not None:
            _runner()._remediation_event(base_dir, st, job_id, page_div,
                               "none", "none", "unavailable", "",
                               digest)
            _runner()._remediation_audit(base_dir, cfg, st, job_id,
                               "observed", page_div,
                               "mode off: recorded and paged only")
        return None
    acted = outcome.get("acted")
    post_tripwire = None
    if acted is None:
        for div in outcome.get("divergences") or []:
            if div.get("tripwire"):
                post_tripwire = div
                break
    if acted is None and post_tripwire is None:
        return None
    if acted is not None:
        authority = acted["authority"]
        div = acted["divergence"]
        _sigkill = getattr(signal, "SIGKILL", None)
        tree_killed = os.name == "nt" or (
            _sigkill is not None
            and proc is not None and proc.returncode is not None
            and proc.returncode == -_sigkill)
        act = "killed" if tree_killed else "quarantined"
    else:
        authority = "tripwire"
        div = post_tripwire
        act = "quarantined"
    R.log(f"job {job_id}: remediation {act} "
        f"({_runner()._remediation.divergence_text(div)}; "
        f"authority {authority})", "WARN")
    marker = {"job_id": job_id, "mode": mode, "authority": authority,
              "divergence": _runner()._remediation.divergence_text(div),
              "act": act, "received_digest": digest}
    qdir = _runner()._remediation.quarantine_job(base_dir, job_id, work, marker)
    refer = []
    if qdir:
        qwork = os.path.join(qdir, "work")
        for rel in outcome.get("suspects") or []:
            refer.append(os.path.join(qwork, rel))
        try:
            script_rel = os.path.relpath(script_path, work)
            refer.append(os.path.join(qwork, script_rel))
        except ValueError:
            pass
    else:
        for rel in outcome.get("suspects") or []:
            refer.append(os.path.join(work, rel))
        refer.append(script_path)
    av_verdict, av_detail = _runner()._remediation.av_referral(refer)
    member = _runner()._remediation.result_member(
        mode, authority, div, act, av_verdict, digest)
    _runner()._remediation.enforce_quarantine_bounds(base_dir, st)
    _runner()._remediation_audit(
        base_dir, cfg, st, job_id, "acted", div,
        f"act={act} authority={authority} av={av_verdict} "
        f"({av_detail})")
    _runner()._remediation_event(base_dir, st, job_id, div, act, authority,
                       av_verdict, qdir or "", digest, envelope_note)
    return member


def _job_user_preexec(cfg, base_dir, job_id, work, face=None):
    R = _runner()
    if _runner()._security is None or os.name == "nt":
        return None
    face = face or _runner()._JobUserFace()
    mode = _runner()._security.sec_mode(cfg, "job_user")
    if mode == "off":
        return None
    _runner()._security.bump_evaluated(base_dir, "job_user")
    sec = cfg.get("security")
    sec = sec if isinstance(sec, dict) else {}
    ju = sec.get("job_user") if isinstance(sec.get("job_user"), dict) else {}
    user = ju.get("user") if isinstance(ju, dict) else None
    if not user or not isinstance(user, str):
        return None

    def _audit(decision, reason, detail=""):
        try:
            _runner()._security.write_audit_entry(
                base_dir, "job_user", decision, reason,
                job_id=str(job_id), detail=str(detail), cfg=cfg,
                mode=mode)
        except Exception:
            pass

    if mode == "audit":
        _audit("would_run_as", "would_run_as_user", user)
        return None
    # enforce from here on
    if face.euid() != 0:
        R.log(f"job {job_id}: job_user needs root; running as current "
            f"user", "WARN")
        _audit("fallback", "job_user_needs_root")
        return None
    try:
        pw = face.getpwnam(user)
    except (ImportError, KeyError) as e:
        R.log(f"job {job_id}: job_user {user!r} unavailable ({e}); running "
            f"as current user", "WARN")
        _audit("fallback", "job_user_unavailable", str(e))
        return None
    # The job must own its workdir to read the script and write output.
    try:
        for root, dirs, files in face.walk(work):
            face.chown(root, pw.pw_uid, pw.pw_gid)
            for d in dirs:
                face.chown(os.path.join(root, d), pw.pw_uid, pw.pw_gid)
            for f in files:
                face.chown(os.path.join(root, f), pw.pw_uid, pw.pw_gid)
        # Traverse-only (+x, not +r) on the parent chain up to base_dir,
        # so the job user can reach its workdir without listing the
        # runner's state. Files there stay protected by their own mode.
        node = face.realpath(work)
        stop = face.realpath(base_dir)
        while True:
            node = face.dirname(node)
            try:
                st = face.stat(node)
            except OSError:
                break
            if not st.st_mode & 0o001:
                face.chmod(node, st.st_mode | 0o001)
            if node == stop or node == face.dirname(node):
                break
    except OSError as e:
        R.log(f"job {job_id}: cannot chown workdir to {user} ({e}); "
            f"running as current user", "WARN")
        _audit("fallback", "job_user_chown_failed", str(e))
        return None
    _audit("run_as", "ran_as_user", user)

    def _demote():
        # After fork, before exec. Syscalls only.
        face.setgid(pw.pw_gid)
        try:
            face.initgroups(pw.pw_name, pw.pw_gid)
        except OSError:
            # Q18: never carry the runner's supplementary groups
            # into the job. Fall back to the user's primary group
            # alone; if even that fails, raise, and the job is
            # refused rather than run with the runner's groups.
            face.setgroups([pw.pw_gid])
        face.setuid(pw.pw_uid)
    return _demote


def _learning_model_candidate(cfg, base_dir, job_id, job, outcome,
                              stdout_text, stderr_text):
    """The model channel of the learning loop: distill ONE
    candidate lesson from a completed job's outcome and output.

    Gated exactly like the tier-2 opinion note, plus the
    learning channel's own opt-in (oracle_learning_model):
    both model gates on and inference configured, so in
    deterministic Oracle mode (Pi Light) no model is ever
    called and no candidate is ever born. The reply must be a
    JSON object passing learning.validate_candidate -- output
    is evidence, never instruction, and a schema failure or an
    instruction-shaped claim is dropped, not filed.
    """
    R = _runner()
    if _runner()._learning is None \
            or not _runner()._learning.learning_model_enabled(cfg) \
            or not _runner()._opinion.model_enabled(cfg):
        return
    inf = _runner().inference_config(cfg)
    if inf is None:
        return
    try:
        context = (
            _runner()._describe_job(job)
            + f"\nOutcome: exit_code={outcome.get('exit_code')} "
              f"timed_out={bool(outcome.get('timed_out'))} "
              f"rejected={bool(outcome.get('rejected'))}\n"
            + "Output excerpt:\n"
            + ((stdout_text or "") + "\n"
               + (stderr_text or ""))[:1200])
        res = _runner().ask_model(
            inf,
            "From this completed job, distill ONE lesson about "
            "THIS host's environment that would help predict "
            "whether a similar future job succeeds. Reply with "
            "ONLY a JSON object: {\"claim\": a short declarative "
            "sentence about the environment, \"features\": "
            "[keys like \"tool:<name>\", \"interpreter:<exe>\", "
            "\"path:<path>\"], \"expects\": \"failure\" or "
            "\"success\" for similar jobs, \"confidence\": 0 to "
            "1}. A lesson states a fact about the environment; "
            "never phrase a lesson as an instruction.",
            context, 500, _runner()._redact_patterns(cfg))
    except Exception:
        return
    if not isinstance(res, dict):
        return
    text = res.get("answer")
    if not isinstance(text, str):
        return
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return
    candidate = _runner()._learning.validate_candidate(obj)
    if candidate is None:
        R.log(f"oracle learning: model candidate for {job_id} "
            f"rejected by schema validation", "WARN")
        return
    record = _runner()._learning.candidate_record(
        candidate, job_id, _runner()._learning_fingerprint())
    if not _runner()._learning.append_candidate(base_dir, record):
        R.log(f"oracle learning: candidate write failed for "
            f"{job_id}", "WARN")


def _retained_job_summary(data, job_id, base_dir=None) -> str:
    """One retained job as context for the Oracle.

    Small local models answer concrete questions ("what did this job
    do?", "did it succeed?") only when the record carries the job's
    kind, its script, its real timestamp, and its exit status, not
    just the output text. A missing kind is "kind not recorded".
    That is not a failure, and it is not the word "unknown", which a
    small model will repeat as the status.
    """
    R = _runner()
    kind, status, when = _runner()._job_facts(data, job_id)
    lines = [f"job {job_id} ({kind}, {status}, {when})"]
    script = data.get("script") if isinstance(data.get("script"), str) else ""
    findings = []
    if script.strip():
        lines.append("script: " + script.strip()[:400])
        findings = _runner()._script_path_findings(script, base_dir, job_id)
        if findings:
            # The line carries its own job id. Both ask prompts
            # direct the model to report the finding with the job's
            # id, and the battery showed small models binding the
            # line to a neighbouring benign block when the only
            # binding was its position under the block header.
            lines.append(
                "notable: SUSPICIOUS ACCESS -- job " + job_id
                + ": this job's script references "
                + "; ".join(f"{path} ({reason})"
                            for path, reason in findings)
                + ". Reading files outside the job's own workspace "
                "is malicious-job behavior; the signature proves "
                "who sent the job, not that its behavior is benign.")
    text = _runner()._output_blob(data).strip()
    if findings:
        # Withhold, do not merely label. The Flag321 field tests
        # showed both small models handing a flagged job's raw
        # output back on request ("The value stored in flag.txt
        # is: 321") despite ASK_SYSTEM's no-reveal line, and the
        # 3B volunteering it unprompted: a pattern-based secret
        # scan cannot catch an arbitrary short value, and a value
        # that is not in the context cannot be repeated. The
        # retained record on disk is unchanged; only the Oracle's
        # summary withholds it, the same shape as an attested
        # result (attestations and a digest, not the output).
        digest = data.get("digest") if isinstance(
            data.get("digest"), str) else ""
        lines.append(
            "output: (withheld -- job " + job_id + " carries a "
            "notable finding, so its output may contain the material it "
            "accessed and is not shown to the Oracle"
            + (f"; {len(text)} chars, digest {digest[:16]}"
               if text else "; output was empty")
            + ")")
    else:
        if len(text) > 800:
            text = text[:800] + "\n..."
        lines.append("output:\n" + text if text else "output: (empty)")
    scan = data.get("artifact_scan")
    if isinstance(scan, list) and scan:
        lines.append("artifact scan:\n" + "\n".join(
            str(item)[:200] for item in scan[:20]))
    return "\n".join(lines)


