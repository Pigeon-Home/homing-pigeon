"""Mail handling.

Extracted from runner.py.
"""

def handle_mail(cfg, imap, smtp, seq, raw: bytes, base_dir: str,
                seen: dict, secrets: dict, opts=None, key_policies=None):
    from runner import runner as R
    msg = email.message_from_bytes(raw)
    subject = str(msg["Subject"] or "")
    from_header = str(msg["From"] or "")
    def reject(why: str):
        vlog(f"ingest: seq {seq}: rejected: {why}")
        R.log(f"rejecting seq {seq}: {why}", "WARN")
        # Dry-run is fully non-mutating: observe, change nothing.
        _mark(imap, seq, opts)

    dispatched = _early_dispatch(
        cfg, imap, smtp, seq, raw, subject, secrets, opts, base_dir, seen)
    if dispatched is None:
        return
    job_id, skey = dispatched

    # The HMAC signature is the sole authentication gate. Any sender
    # may submit jobs; only a valid signature authorizes execution.
    # The sender address is logged for audit but never trusted.
    from_addr = parseaddr(from_header)[1].strip()
    R.log(f"seq {seq}: job {job_id} submitted by {from_addr or '(no sender)'} "
        f"subject={subject!r}")

    # Hardening M1b: bound the raw mail before any signature work.
    try:
        max_job_bytes = int(cfg.get("max_job_bytes", 4194304))
    except (TypeError, ValueError, OverflowError):
        max_job_bytes = 4194304
    if max_job_bytes and len(raw) > max_job_bytes:
        reject(f"mail exceeds max_job_bytes ({len(raw)} > {max_job_bytes})")
        return

    try:
        job, key_id, secret, job_was_encrypted = _verify_and_decrypt(msg, secrets, job_id)
    except JobCryptoError as e:
        reject(f"bad encrypted envelope: {e}")
        _auth_reject_event(base_dir, "bad_encryption")
        return
    except ValueError as e:
        reject(f"bad signature: {e}")
        _auth_reject_event(base_dir, "bad_signature")
        return
    if not job_was_encrypted:
        if _cleartext_jobs_allowed():
            # This process was started with
            # --allow-cleartext: the signature above still
            # gated admission (cleartext never means
            # unauthenticated), and the readable arrival is
            # worth its line in the log, as it always was.
            R.log(f"job {job_id}: received in clear text (not "
                f"encrypted); accepted under "
                f"--allow-cleartext")
        else:
            # Secure by default: the HMAC-only (cleartext) form
            # does not admit a job. Acceptance is a command-line
            # decision only (--allow-cleartext); there is
            # no config key for it. The refusal mirrors a
            # key-policy reject of a signature-valid job exactly:
            # the reject is logged, the message is marked seen,
            # an auth_rejection event is recorded, no result is
            # sent, and the job_id is not recorded in the seen
            # set. The form decides, not the channel: a cleartext
            # object that arrived inside a DTLS session is
            # refused here just the same.
            reject("cleartext job refused: the HMAC-only form "
                   "is not accepted by default; send the job "
                   "encrypted (hp_enc), or start the runner "
                   "with --allow-cleartext")
            _append_security_event(base_dir, {
                "type": "auth_rejection",
                "at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "reason": "cleartext_not_supported",
            })
            return

    # Hardening M5: audience binding. The expected runner_id comes from
    # the loaded config, never from the signed body.
    if not audience_allows(cfg, base_dir, job, key_id, job_id):
        reject("security policy (audience): runner_id mismatch")
        _auth_reject_event(base_dir, "security_policy", feature="audience")
        return
    # Hardening M1b: bound the script after the signature is verified
    # (it lives inside the signed body). 0 means unlimited.
    try:
        max_script_bytes = int(cfg.get("max_script_bytes", 1048576))
    except (TypeError, ValueError, OverflowError):
        max_script_bytes = 1048576
    script = job.get("script")
    if max_script_bytes and isinstance(script, str) \
            and len(script.encode("utf-8")) > max_script_bytes:
        reject(f"script exceeds max_script_bytes "
               f"({len(script.encode('utf-8'))} > {max_script_bytes})")
        return
    if not _version_ok(job.get("v")) or job.get("type") != "job":
        reject("unsupported version/type")
        return
    if job.get("job_id") != job_id:
        reject("job_id mismatch between subject and body")
        return
    try:
        issued = _fromiso(job["issued_at"])
    except Exception:
        reject("unparseable issued_at")
        return
    # Naive timestamps make the age subtraction raise TypeError, which the
    # outer handler treats as transient and retries forever. Reject instead.
    if issued.tzinfo is None or issued.tzinfo.utcoffset(issued) is None:
        reject("issued_at missing timezone (must be UTC / end with Z)")
        return
    age = (datetime.now(timezone.utc) - issued).total_seconds()
    max_age = _confval.integer(cfg.get("max_job_age_sec"), 3600, lo=1)
    if age < -300 or age > max_age:
        reject(f"issued_at outside allowed window (age {age:.0f}s)")
        return

    violation = check_key_policy(key_policies or {}, key_id, cfg, job)
    if violation:
        reject(f"key policy: {violation}")
        _auth_reject_event(base_dir, "key_policy")
        return

    # Hardening M2: env/files/args constraints for keys with a policy
    # entry (D3). Each finding goes through sec_decide; enforce mode
    # denies through the existing reject path. When every feature is
    # off the check is skipped entirely, so off changes nothing.
    if _security is not None:
        _pol = (key_policies or {}).get(key_id)
        _m2_features = ("policy_env", "policy_files", "policy_args")
        if _pol and any(_security.sec_mode(cfg, f) != "off"
                        for f in _m2_features):
            for _f in _m2_features:
                if _security.sec_mode(cfg, _f) != "off":
                    _security.bump_evaluated(base_dir, _f)
            for _feature, _reason, _detail in check_policy_constraints(
                    _pol, key_id, cfg, job):
                _decision = _security.sec_decide(
                    cfg, base_dir, _feature, _reason,
                    {"key_id": key_id, "job_id": job_id,
                     "detail": _detail})
                if not _decision:
                    reject(f"security policy ({_feature}): {_reason}")
                    _append_security_event(base_dir, {
                        "type": "auth_rejection",
                        "at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"),
                        "reason": "security_policy",
                        "feature": _feature,
                    })
                    return

    if job.get("kind") == "sensor_alert":
        _ingest_sensor_alert(cfg, imap, seq, job_id, job, key_id,
                             secrets, opts, base_dir, seen)
        return

    # Advisory pre-execution review. The Oracle looks at the job and
    # attaches notes about likely failures. It never blocks: the job
    # runs regardless, because the Oracle can be wrong. A review that
    # raises, or that cannot be signed as JSON, is dropped.
    review = None
    if _review:
        try:
            review = _review.review_job(cfg, job)
        except Exception as e:
            R.log(f"review failed for {job_id}: {e}", "WARN")
            review = None
    if isinstance(review, dict):
        try:
            json.dumps(review)
        except (TypeError, ValueError):
            R.log(f"review for {job_id} was not JSON; dropped", "WARN")
            review = None
    else:
        review = None

    vlog(f"ingest: job {job_id}: accepted "
         f"(key_id={key_id}, kind={job.get('kind')})")
    R.log(f"executing job {job_id} (kind={job.get('kind')})")
    if opts is not None and opts.dry_run:
        # Dry run: fully non-mutating. Verify everything, change nothing:
        # no execution, no result message, no seen updates.
        desc = _describe_job(job)
        R.log(f"dry-run: would execute job {job_id}: {desc}")
        return
    no_send = opts is not None and opts.no_send
    # Result encryption mirrors this job's own form unless the
    # owner set job_encryption explicitly (_job_encryption_setting).
    _enc_setting = _job_encryption_setting(cfg)
    encrypt_result = job_was_encrypted \
        if _enc_setting is None else _enc_setting

    # Claim the job_id so a duplicate delivery on another worker thread
    # cannot double-execute it. The check-and-add is atomic under the lock.
    # The disk claim is the same rule across two processes: seen.json
    # and the inflight file are updated under a file lock, and the
    # claim is not dropped until the key is in seen.json.
    with R._MAIL_LOCK:
        if skey in seen or skey in R._IN_FLIGHT:
            vlog(f"ingest: job {job_id}: skipped; another "
                 f"worker claimed it first")
            mark_seen(imap, seq)
            return
        if not _disk_owns(base_dir, skey, seen):
            # Already in the replay cache: this copy is done.
            # A live claim in another process is not done. Leave
            # the message unseen so a crash there can be stolen
            # on the next poll instead of dropped.
            if seen.get(skey):
                vlog(f"ingest: job {job_id}: skipped; already seen")
                mark_seen(imap, seq)
            else:
                vlog(f"ingest: job {job_id}: skipped; another "
                     f"process holds it")
            return
        R._IN_FLIGHT.add(skey)
    try:
        def maybe_send(subject: str, body: str):
            if no_send:
                R.log(f"no-send: result message suppressed "
                    f"(subject={subject!r}, {len(body)} bytes)")
                return
            send_mail(smtp, cfg, subject, body, to=_valid_reply_to(job))

        # Executed before, result not yet acknowledged: resend the
        # bytes that were produced then and run nothing. The seen-set
        # commits below exactly as for a first delivery.
        cached = load_sent_result(base_dir, skey, job)
        if cached is not None:
            with R._MAIL_LOCK:
                maybe_send(cached["subject"], cached["body"])
                R.log(f"job {job_id}: result resent from the sent record "
                    f"(executed once, completed {cached.get('completed_at')})")
                seen[skey] = True
                mark_seen(imap, seq)
            return

        op_plan = None
        op_member = None
        run_job = job
        op_facts = None
        op_diag_facts = None
        op_repair_applied = False
        learn_relevant = None
        learn_frozen = None
        try:
            verdict, reasons = judge_job(cfg, job)
            _jmode = cfg.get("judge") or "off"
            if _jmode != "off":
                vlog(f"judge: job {job_id}: mode={_jmode} "
                     f"verdict={verdict}"
                     + (f" ({'; '.join(reasons)})" if reasons
                        else ""))
            if cfg.get("judge") == "enforce" and reasons:
                raise JobRejected("judge blocked: " + "; ".join(reasons))
            # The Oracle's opinion (PROTOCOL 3.2; runner/oracle/opinion.py):
            # tier-1 deterministic checks, an optional repair, and a
            # member on the result. Advisory by construction -- the
            # opinion never blocks a job by itself. The one refusal
            # it can produce is the re-judgment of a repaired job,
            # and then the sender gets the original job's failure
            # result with the opinion explaining.
            if _opinion is not None and job.get("kind") == "exec":
                try:
                    op_facts = _opinion_env_facts(cfg, job)
                    learn_notes = []
                    if _opinion.effective_mode(cfg, job) != "off":
                        learn_relevant, learn_notes = \
                            _learning_context(cfg, base_dir, op_facts)
                    op_plan = _opinion.plan_before(
                        cfg, job, op_facts, lessons=learn_notes)
                except Exception as e:
                    R.log(f"oracle opinion failed for {job_id}: {e}",
                        "WARN")
                    op_plan = None
                if op_plan is not None:
                    learn_frozen = _learning_freeze(
                        cfg, base_dir, job_id, job, op_plan,
                        op_facts, learn_relevant)
            if op_plan is not None and op_plan.get("repair_action"):
                repaired_job = dict(job)
                repaired_job["interpreter"] = platform_interpreter()
                # Rejudge (oracle_opinion_repair=rejudge, the
                # default): the repaired job goes back through the
                # dealing path exactly as a received job would.
                r_verdict, r_reasons = judge_job(cfg, repaired_job)
                r_violation = check_key_policy(
                    key_policies or {}, key_id, cfg, repaired_job)
                if r_violation or (cfg.get("judge") == "enforce"
                                   and r_reasons):
                    why = r_violation or (
                        "judge blocked: " + "; ".join(r_reasons))
                    op_member = _opinion.repair_member(
                        op_plan, job, applied=False, refusal=why)
                    raise JobRejected(
                        "repaired job refused on re-judgment: " + why)
                run_job = repaired_job
                op_repair_applied = True
                op_member = _opinion.repair_member(
                    op_plan, job, applied=True)
                R.log(f"job {job_id}: oracle opinion repaired the "
                    f"interpreter to the platform default")
            elif op_plan is not None and op_plan.get("attach") is not None:
                op_member = op_plan["attach"]
                if not op_plan["findings"]:
                    mnote = _opinion_model_note(cfg, job)
                    if mnote:
                        op_member = _opinion.with_model_note(
                            op_member, mnote)
            v2_segments = []
            if _protocol_v2 is not None and _protocol_v2.enabled(cfg):
                try:
                    def v2_send(subject, body):
                        return _v2_hand_off(
                            cfg, smtp, base_dir, subject, body,
                            _valid_reply_to(job))

                    def v2_pump():
                        _v2_ingest(
                            cfg, imap, base_dir, seen, secrets, opts)

                    v2_segments = _v2_before_execute(
                        cfg, job, op_plan, secret, key_id,
                        encrypt_result, base_dir, v2_send, v2_pump)
                except Exception as e:
                    R.log(f"version 2 exchange failed for {job_id}: {e}",
                        "WARN")
                    v2_segments = []
            # Confinement snapshots exclude the runner's own base_dir so
            # retained/, board.json, and seen.json do not false-positive.
            ws = cfg.get("workspace_root") or ""
            if not isinstance(ws, str):
                ws = ""
            before = snapshot_outside(ws, exclude=[base_dir]) if ws else {}
            r = execute_job(cfg, run_job, base_dir)
            after = snapshot_outside(ws, exclude=[base_dir]) if ws else {}
            # Three states: None (unconfigured), True (confined),
            # False (violation detected). Never conflate the first and last.
            confined = None if not ws else (not confinement_violated(before, after))
            protected = cfg.get("protected_paths") or []
            protected_changed = check_protected_paths(before, after, protected)
            result = {
                "v": PROTOCOL_VERSION, "type": "result", "job_id": job_id,
                "kind": job.get("kind"),
                "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "exit_code": _as_int(r.get("exit_code"), -1),
                "timed_out": bool(r.get("timed_out")),
                "stdout": _as_str(r.get("stdout")),
                "stderr": _as_str(r.get("stderr")),
                "stdout_truncated": bool(r.get("stdout_truncated")),
                "stderr_truncated": bool(r.get("stderr_truncated")),
                "duration_sec": _as_float(r.get("duration_sec"), 0.0),
                "runner": socket.gethostname(),
                "review": review,
            }
            # Oracle view
            patterns = _redact_patterns(cfg)
            result, retain_view = apply_result_policy(cfg, job, result, patterns, confined=confined)
            scan = r.get("artifact_scan")
            if isinstance(scan, list) and scan:
                result["artifact_scan"] = [str(item)[:200] for item in scan[:20]]
            # The platform card (PROTOCOL 3.2) answers a ping at the
            # owner's tier. It is not job output, so the result
            # policy's view does not shape it; the tier is the
            # owner's ceiling for it.
            card = r.get("platform")
            if job.get("kind") == "ping" and isinstance(card, dict):
                result["platform"] = card
            # Remediation (PROTOCOL 3.2): the member rides the
            # result when remediation acted on the job or its
            # outputs. A confinement escape the post-run snapshot
            # caught is handled here, as the escape tripwire at
            # result time (see _remediation_confinement_followup).
            rem = r.get("remediation")
            if isinstance(rem, dict):
                # execute_job saw the job it ran (post-repair, if
                # any); the member's digest must name the job as
                # RECEIVED. Correct it here, and in the quarantine
                # marker, when a repair made them differ.
                if _remediation is not None:
                    want = _remediation.received_digest(job)
                    if rem.get("received_digest") != want:
                        rem = dict(rem)
                        rem["received_digest"] = want
                        _remediation.fix_marker_digest(
                            base_dir, job_id, want)
                result["remediation"] = rem
            if _remediation is not None and (confined is False
                                             or protected_changed):
                try:
                    esc = _remediation_confinement_followup(
                        cfg, job, job_id, base_dir)
                    if esc is not None and "remediation" not in result:
                        result["remediation"] = esc
                except Exception:
                    pass
            # The opinion member rides the result, signed with it.
            # A prediction already formed rides as formed (a wrong
            # likely_success gains the post-run sentence, never a
            # rewrite); with no member formed, the diagnose
            # latitude speaks after a failure and stays silent
            # after a success.
            job_failed = _as_int(r.get("exit_code"), -1) != 0 \
                or bool(r.get("timed_out"))
            if op_member is not None:
                if job_failed and op_plan is not None:
                    op_member = _opinion.extend_member_outcome(
                        op_member, op_plan["findings"])
                result["oracle_opinion"] = op_member
            elif op_plan is not None and op_plan.get("active") \
                    and job_failed:
                findings = op_plan["findings"]
                if not op_plan.get("checks_run"):
                    try:
                        op_diag_facts = _opinion_env_facts(cfg, job)
                        findings = _opinion.tier1_findings(
                            job, op_diag_facts)
                    except Exception:
                        findings = []
                mnote = None
                if not findings:
                    mnote = _opinion_model_note(cfg, job)
                result["oracle_opinion"] = _opinion.diagnosis_member(
                    op_plan["mode"], findings, model_note=mnote)
            # Version 2 context rides the version 1 result.
            # apply_result_policy rebuilds the dict, so the
            # segments are attached after it, as the opinion is.
            if v2_segments:
                result["context"] = v2_segments
            # Self-learning (runner/oracle/learning.py): score the
            # frozen call against this outcome and persist what
            # it teaches BEFORE the result is sent, so the next
            # job's opinion evaluation reads it fresh from the
            # ledger. Best effort by design -- the helpers log
            # their own failures and never raise, so a learning
            # failure cannot delay or block the result.
            if learn_frozen is not None or op_diag_facts is not None:
                op_outcome = {
                    "exit_code": _as_int(r.get("exit_code"), -1),
                    "timed_out": bool(r.get("timed_out")),
                    "rejected": False,
                    "repair_applied": op_repair_applied,
                    "repair_attempted": op_repair_applied,
                }
                recon = _learning_reconcile(
                    cfg, base_dir, learn_frozen, job_id,
                    op_outcome, op_facts, op_diag_facts)
                if recon is not None and (
                        job_failed
                        or recon.get("classification")
                        in ("incorrect", "partial")):
                    _learning_model_candidate(
                        cfg, base_dir, job_id, job, op_outcome,
                        _as_str(r.get("stdout")),
                        _as_str(r.get("stderr")))
            # Optional low-overhead detection (rules, baseline, ATT&CK tags).
            # Canaries are handled separately by _canary_watch. Never raises.
            if _detection is not None and isinstance(base_dir, str) and base_dir:
                try:
                    hits = _detection.evaluate_rules(job, result)
                    if hits:
                        # Tag each hit with its ATT&CK technique when present.
                        tagged = []
                        for h in hits:
                            tech = h.get("technique") if isinstance(h, dict) else None
                            tagged.append(_detection.tag_alert(h, tech) if tech else h)
                        result["detection_hits"] = tagged
                    baseline = _detection.update_baseline(base_dir, job, result)
                    anomaly = _detection.baseline_anomaly(baseline, job, result)
                    if anomaly:
                        result["detection_anomaly"] = anomaly
                    # Optional multi-step plan budget check.
                    plan = job.get("plan") if isinstance(job, dict) else None
                    if isinstance(plan, list):
                        allowed, reason = _detection.check_plan_budget(plan, cfg or {})
                        result["plan_budget_ok"] = allowed
                        if not allowed and reason:
                            result["plan_budget_reason"] = reason
                except Exception:
                    pass
            declared = job.get("result_policy") if isinstance(job.get("result_policy"), dict) else {}
            declared = declared.get("queries") or []
            if not isinstance(declared, list):
                declared = []
            spent = 0
            digest = hashlib.sha384(
                (_as_str(r.get("stdout")) + _as_str(r.get("stderr"))).encode("utf-8")).hexdigest()
            if declared:
                view = result.get("view") or "full"
                answers, spent = answer_queries(
                    declared,
                    {"stdout": _as_str(r.get("stdout")), "stderr": _as_str(r.get("stderr")),
                     "exit_code": _as_int(r.get("exit_code"), -1), "confined": confined,
                     "digest": digest},
                    patterns, query_budget(cfg, job), cfg=cfg, view=view,
                    base_dir=base_dir,
                )
                result["answers"] = answers
            if retain_view or declared:
                save_retained(base_dir, job_id, {
                    "job_id": job_id,
                    "kind": job.get("kind"),
                    "script": _as_str(job.get("script") or "")[:500],
                    "stdout": _as_str(r.get("stdout")),
                    "stderr": _as_str(r.get("stderr")),
                    "exit_code": _as_int(r.get("exit_code"), -1),
                    "timed_out": bool(r["timed_out"]),
                    "duration_sec": _as_float(r.get("duration_sec"), 0.0),
                    "view": result.get("view") or "full",
                    "budget": query_budget(cfg, job),
                    "spent": spent,
                    "patterns": patterns,
                    "confined": confined,
                    "digest": digest,
                    "saved_at": time.time(),
                    "judgment": result.get("judgment"),
                    "artifact_scan": r.get("artifact_scan") or [],
                    "remediation": result.get("remediation"),
                })
            else:
                note = _artifact_note(job_id, job, r)
                if note:
                    save_retained(base_dir, job_id, note)
            if protected_changed:
                result.setdefault("confinement_detail", {})["protected_paths_changed"] = protected_changed
            if cfg.get("judge") in ("advisory", "enforce"):
                result["judgment"] = {"verdict": verdict, "reasons": reasons}
            with R._MAIL_LOCK:
                out_subject = f"{SUBJECT_RESULT}{job_id}"
                out_body = _outgoing_result_body(
                    result, secret, encrypt_result, job_id, key_id)
                # Recorded before the send: a redelivery resends
                # these bytes instead of executing again.
                save_sent_result(base_dir, skey, job, out_subject,
                                 out_body, to=_valid_reply_to(job))
                maybe_send(out_subject, out_body)
                R.log(f"job {job_id} done (exit={r['exit_code']})")
                seen[skey] = True  # only after the result is safely sent (at-least-once)
                mark_seen(imap, seq)
        except JobRejected as e:
            R.log(f"job {job_id} rejected: {e}", "WARN")
            try:
                result = {
                    "v": PROTOCOL_VERSION, "type": "result", "job_id": job_id,
                    "kind": job.get("kind"),
                    "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "exit_code": -2, "timed_out": False,
                    "stdout": "", "stderr": f"job rejected: {e}",
                    "stdout_truncated": False, "stderr_truncated": False,
                    "duration_sec": 0.0, "runner": socket.gethostname(),
                    "review": review,
                }
                # A rejection is a failure the sender sees: a formed
                # opinion rides it, and the diagnose latitude gets
                # its say (an unstartable interpreter is the classic
                # obvious cause).
                if op_member is not None:
                    result["oracle_opinion"] = op_member
                elif op_plan is not None and op_plan.get("active") \
                        and _opinion is not None:
                    try:
                        op_diag_facts = _opinion_env_facts(cfg, job)
                        findings = _opinion.tier1_findings(
                            job, op_diag_facts)
                        mnote = None
                        if not findings:
                            mnote = _opinion_model_note(cfg, job)
                        result["oracle_opinion"] = \
                            _opinion.diagnosis_member(
                                op_plan["mode"], findings,
                                model_note=mnote)
                    except Exception:
                        pass
                # A rejection is an outcome too: reconcile the
                # frozen call against it (a repair refused on
                # re-judgment scores partial) before the result
                # is sent. Best effort, as in the main path.
                if learn_frozen is not None \
                        or op_diag_facts is not None:
                    _learning_reconcile(
                        cfg, base_dir, learn_frozen, job_id,
                        {"exit_code": -2, "timed_out": False,
                         "rejected": True,
                         "repair_applied": False,
                         "repair_attempted": bool(
                             op_plan and op_plan.get("repair_action"))},
                        op_facts, op_diag_facts)
                with R._MAIL_LOCK:
                    maybe_send(f"{SUBJECT_RESULT}{job_id}",
                              _outgoing_result_body(
                                  result, secret, encrypt_result,
                                  job_id, key_id))
                    seen[skey] = True
                    mark_seen(imap, seq)
            except Exception as e2:
                R.log(f"could not send rejection result: {e2}", "ERROR")
        except Exception as e:
            # Transient (network, SMTP, ...): leave unseen -> retried next cycle.
            R.log(f"job {job_id} failed, will retry: {e}", "ERROR")
    finally:
        with R._MAIL_LOCK:
            R._IN_FLIGHT.discard(skey)
            if skey not in seen:
                _disk_release(base_dir, skey)
