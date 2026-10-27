"""CLI, v2 mail, and variant helpers.

Extracted from runner.py.
"""
import email
import hashlib
import json
import os
import sys
import threading


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore
import email

def oracle_cli(cfg, cfg_path=None, input_fn=None, print_fn=None) -> int:
    """Chat with the Oracle in the terminal. Does not poll the mailbox.

    The same ask pipeline as the --oracle window -- _runner().ask_model_agent
    over the live Oracle context, answers and rejects rendered the
    same way, turns recorded to the same chat log -- with no HTTP
    server and no browser. /quit or /exit ends it, as do EOF and
    Ctrl+C. input_fn / print_fn are seams for tests.
    """
    R = _runner()
    if input_fn is None:
        input_fn = input
    if print_fn is None:
        print_fn = print
    if not isinstance(cfg, dict):
        cfg = {}
    base = R._base_dir_for(cfg, cfg_path)
    R._LOG_FILE = os.path.join(base, "runner.log")
    R._refresh_log_settings(cfg, base)
    R._announce_oracle_log()
    print_fn(f"homing-pigeon {R.__version__} --oracle-cli")
    print_fn(f"Chat log: {os.path.join(base, 'oracle-chat.jsonl')}")
    if cfg_path:
        print_fn(f"Config: {os.path.abspath(cfg_path)}")
    inf = _runner().inference_config(cfg) or {}
    if R._oracle_mode(cfg) == "deterministic":
        print_fn("Oracle mode: deterministic (Pi Light) -- no local "
                 "model; answers are this box's records, un-narrated")
        warm_thread = None
    elif inf.get("model"):
        print_fn(f"Inference: local model {inf['model']} "
                 f"({inf['endpoint']})")
        warm_thread = threading.Thread(
            target=R._warm_oracle_model, args=(inf,), daemon=True)
        warm_thread.start()
    else:
        print_fn("Inference: not configured (Ask stays off)")
        warm_thread = None
    print_fn("Terminal chat; the Oracle may run tools on this box. "
             "/quit ends it.")
    try:
        _runner().record_oracle_turn(base, cfg, "", {}, event="open")
    except Exception as e:
        R.log(f"oracle open not recorded: {e}", "WARN")
    try:
        while True:
            try:
                line = input_fn("oracle> ")
            except (EOFError, KeyboardInterrupt):
                print_fn("")
                break
            question = (line or "").strip()
            if not question:
                continue
            if question in ("/quit", "/exit"):
                break
            if question == "/help":
                print_fn("Ask a question and the Oracle answers with "
                         "this box's board, jobs, and host state as "
                         "context. /quit ends the chat.")
                continue
            question = question[:4000]
            if R._oracle_mode(cfg) == "deterministic":
                ans = {"answer": R._deterministic_oracle_answer(cfg, base)}
            else:
                try:
                    ans = _runner().ask_model_agent(
                        inf, question,
                        _runner().oracle_context(base,
                                       watch=R._oracle_watch_enabled(cfg)),
                        (inf or {}).get("max_answer_chars") or 2000,
                        R._redact_patterns(cfg),
                        instructions=cfg.get("owner_instructions"),
                        base_dir=base,
                    )
                except Exception as e:
                    R.log(f"oracle ask failed: {e}", "WARN")
                    ans = None
            if not isinstance(ans, dict):
                ans = {"rejected": "inference_error"}
            try:
                _runner().record_oracle_turn(base, cfg, question, ans)
            except Exception as e:
                R.log(f"oracle chat log failed: {e}", "WARN")
            if isinstance(ans.get("answer"), str) and ans.get("answer"):
                print_fn(ans["answer"][:4000])
            else:
                why = ans.get("rejected") \
                    if isinstance(ans.get("rejected"), str) else ""
                why = why or "inference_error"
                detail = R._ORACLE_REJECTS.get(
                    why, "The Oracle did not answer.")
                if why == "inference_error" \
                        and isinstance(ans.get("detail"), str) \
                        and ans["detail"]:
                    detail = ans["detail"]
                print_fn(detail)
    except KeyboardInterrupt:
        pass
    finally:
        if warm_thread is not None:
            # Same courtesy as the window: never leave the warm-up
            # writing into a directory being torn down.
            warm_thread.join(timeout=5)
        try:
            _runner().record_oracle_turn(base, cfg, "", {}, event="close")
        except Exception:
            pass
    return 0


def handle_v2_mail(cfg, imap, smtp, seq, raw, subject, secrets, opts,
                   base_dir, seen=None):
    """Determination, question, or answer. Never a job.

    Returns True when the subject is one of those three, so
    the caller does not try to execute it. A process that has
    not turned version 2 on drops the message. ``answer_only``
    answers a question and does not run anything.

    Replay and freshness follow the job path (the version 2
    draft's section 5; Q86): ``issued_at`` is held to the job
    window, and a message's ``msg_id`` is recorded in the replay
    cache (``seen``, the poll's dict, or the file when the caller
    has none) once the message is acted on -- an answer stored, a
    question answered, a determination logged -- under the
    runner's namespace with a ``v2:`` prefix, so a copy of it is
    dropped without acting again. A question this process leaves
    for another reader is not acted on and is not recorded.
    """
    R = _runner()
    if R._protocol_v2 is None:
        return False
    found = R._protocol_v2.subject_kind(subject)
    if found is None:
        return False
    kind, ident = found

    def reject(why):
        _runner().vlog(f"ingest: seq {seq}: rejected: {why}")
        R.log(f"rejecting seq {seq}: {why}", "WARN")
        R._mark(imap, seq, opts)

    if not R._protocol_v2.receiving(cfg):
        _runner().vlog(f"ingest: seq {seq}: version 2 message ignored; "
             f"protocol_v2 is off")
        R._mark(imap, seq, opts)
        return True
    try:
        body = _runner().get_text_body(email.message_from_bytes(raw))
        payload, key_id, secret, encrypted = R._admit_object(
            body, secrets, ident)
    except _runner().JobCryptoError as e:
        reject(f"bad envelope: {e}")
        return True
    except Exception as e:
        reject(f"bad signature: {e}")
        return True
    if not encrypted and not R._cleartext_jobs_allowed():
        reject("cleartext version 2 message refused")
        return True
    door = R._verify.check_door_policy(cfg, secrets, key_id, "v2")
    if door:
        reject(f"key policy: {door}")
        return True
    # The answerer list names keys; a key answers under any of its
    # names (Q94: the default key's fingerprint is the default key).
    if not any(R._protocol_v2.answerer_allowed(cfg, name)
               for name in R.key_names(secrets, key_id)):
        reject("answerer is not enabled for this key")
        return True
    try:
        R._protocol_v2.validate(payload)
    except ValueError as e:
        reject(str(e))
        return True
    if payload.get("type") != kind or payload.get("msg_id") != ident:
        reject("version 2 subject does not match the body")
        return True
    fresh, why = R._issued_at_ok(payload.get("issued_at"), cfg)
    if not fresh:
        reject(why)
        return True
    seen_path = os.path.join(base_dir, "seen.json") \
        if isinstance(base_dir, str) and base_dir else ""
    if not isinstance(seen, dict):
        seen = R.load_seen(seen_path)
    skey = R._seen_key(cfg, "v2:" + ident)
    if seen.get(skey):
        _runner().vlog(f"ingest: seq {seq}: version 2 {kind} {ident}: "
                       "skipped; already seen")
        R._mark(imap, seq, opts)
        return True
    dry = opts is not None and opts.dry_run

    def acted():
        if dry:
            return
        seen[skey] = True
        R.save_seen(seen_path, seen)

    if kind == "answer":
        if not dry:
            stored = R._protocol_v2.store_answer(base_dir, payload)
            R.log(f"version 2 answer for {payload.get('question_id')}: "
                f"{'stored' if stored else 'already stored'}")
        acted()
        if not dry:
            _runner().mark_seen(imap, seq)
        return True
    if kind == "question":
        if not R._protocol_v2.answer_only(cfg):
            # This process asked, or it is not the laptop. The
            # question has to stay unseen so another reader of
            # this mailbox can answer it. Marking it seen here
            # is how a shared pipe loses the question.
            R._v2_leave_unseen(ident)
            return True
        text = R._protocol_v2.local_answer_text(payload)
        if R._oracle_mode(cfg) != "deterministic":
            inf = _runner().inference_config(cfg)
            if inf is not None:
                try:
                    res = _runner().ask_model(
                        inf,
                        "Answer in one short sentence. You are "
                        "deciding for another machine. Do not "
                        "write a script and do not give "
                        "instructions to run.",
                        str(payload.get("question") or ""),
                        500, R._redact_patterns(cfg))
                    if isinstance(res, dict) and isinstance(
                            res.get("answer"), str) and res["answer"].strip():
                        text = res["answer"].strip()[:500]
                except Exception as e:
                    R.log(f"version 2 answerer model failed: {e}", "WARN")
        try:
            ans = R._protocol_v2.answer_for(payload, text)
        except ValueError as e:
            reject(str(e))
            return True
        no_send = opts is not None and opts.no_send
        if not dry and not no_send:
            _runner().send_mail(
                smtp, cfg,
                "[HOMING-PIGEON] answer " + ans["msg_id"],
                R._seal_reply(ans, secret, ans["msg_id"], key_id,
                            encrypted))
        R.log(f"version 2 answerer replied to {ident}")
        acted()
        if not dry:
            _runner().mark_seen(imap, seq)
        return True
    # A determination is the Pi telling the answerer what it
    # expects. File nothing executable. The answerer only needed
    # to see it.
    R.log(f"version 2 determination {ident} for job "
        f"{payload.get('job_id')}: {payload.get('expect')}")
    acted()
    if not dry:
        _runner().mark_seen(imap, seq)
    return True


def run_variant(cfg, args) -> int:
    """Run ONE locally supplied fuzz variant and print its outcome.

    The job-fuzz sense's execution door. A variant is a mutation
    of a job this box already ran; its signature no longer
    verifies by construction, so it is never admitted through
    the job path -- this mode is a local operator act, like
    --inspect or --diagnose, that takes a variant file the
    operator's own process wrote, runs its script through the
    same validation and confined execution as a real exec job,
    and prints one JSON report:

    - {"stage": "refused", "reason": ...} -- the core's own
      validation refused the shape before anything ran,
    - {"stage": "ran", "exit_code": ..., "timed_out": ...,
      "duration_sec": ..., "stdout_bytes": ..., "stderr_bytes":
      ..., "digest": ...} -- the variant executed in the bucket,
    - {"stage": "error", "reason": ...} -- the execution path
      itself failed around the run.

    Work lands under <base_dir>/fuzz-work, never the live work
    tree; every run leaves an audit entry; nothing is mailed,
    marked seen, or retained as a job. The variant's timeout
    is capped at R._VARIANT_TIMEOUT_CAP_SEC whatever the file
    asks for. Exit code 0 means a report was printed; 2 is a
    usage or config error, reported on stderr like the other
    one-shot modes.
    """
    R = _runner()
    base_dir = R._base_dir_for(cfg, args.config)
    try:
        with open(args.run_variant, encoding="utf-8") as fh:
            variant = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"run-variant: cannot read variant "
              f"{args.run_variant}: {e}", file=sys.stderr)
        return 2
    report = {"stage": "refused", "reason": "variant is not a "
              "JSON object"}
    if isinstance(variant, dict):
        mutator = variant.get("mutator")
        job = {k: variant[k] for k in R._VARIANT_KEYS
               if k in variant}
        if job.get("kind", "exec") != "exec":
            report = {"stage": "refused",
                      "reason": "variant kind is not exec"}
        else:
            job["kind"] = "exec"
            try:
                job["timeout_sec"] = min(
                    int(job.get("timeout_sec") or R._default_timeout_sec(cfg)),
                    R._VARIANT_TIMEOUT_CAP_SEC)
            except (TypeError, ValueError, OverflowError):
                job["timeout_sec"] = R._VARIANT_TIMEOUT_CAP_SEC
            job_id = job.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                job["job_id"] = "fuzz-variant"
            work_base = os.path.join(base_dir, "fuzz-work")
            try:
                os.makedirs(work_base, exist_ok=True)
            except OSError as e:
                print(f"run-variant: cannot create {work_base}: "
                      f"{e}", file=sys.stderr)
                return 2
            if R._security is not None:
                R._security.write_audit_entry(
                    base_dir, "fuzz", "variant_run", "local_variant",
                    job_id=str(job.get("job_id")),
                    detail=mutator if isinstance(mutator, str)
                    else "", cfg=cfg)
            try:
                r = _runner().execute_job(cfg, job, work_base)
                digest = hashlib.sha384(
                    (R._as_str(r.get("stdout"))
                     + R._as_str(r.get("stderr"))).encode(
                        "utf-8")).hexdigest()
                report = {
                    "stage": "ran",
                    "exit_code": R._as_int(r.get("exit_code"), -1),
                    "timed_out": bool(r.get("timed_out")),
                    "duration_sec": R._as_float(
                        r.get("duration_sec"), 0.0),
                    "stdout_bytes": len(R._as_str(
                        r.get("stdout")).encode("utf-8")),
                    "stderr_bytes": len(R._as_str(
                        r.get("stderr")).encode("utf-8")),
                    "digest": digest,
                }
            except _runner().JobRejected as e:
                report = {"stage": "refused", "reason": str(e)}
            except Exception as e:  # the path around the run
                report = {"stage": "error",
                          "reason": f"{type(e).__name__}: {e}"}
        if isinstance(mutator, str) and mutator:
            report["mutator"] = mutator
    print(json.dumps(report, sort_keys=True))
    return 0


