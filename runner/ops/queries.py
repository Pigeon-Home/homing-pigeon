"""Query handling.

Extracted from runner.py.
"""
import email
import hashlib
import os
import re
import time
try:
    from runner.guard import confval as _confval
    from runner.guard import security as _security
except ImportError:  # running from inside runner/ as __main__
    from guard import confval as _confval  # type: ignore
    from guard import security as _security  # type: ignore


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore
import email

def handle_query_mail(cfg, imap, smtp, seq, raw, subject, secrets, opts, base_dir, seen=None):
    """Handle [HOMING-PIGEON] query <query_id>. Returns True if handled."""
    R = _runner()
    m = re.search(r"\[HOMING-PIGEON\].*?query\s+(\S+)", subject, re.I)
    if not m:
        return False
    query_id = m.group(1)
    # Hardening M5: the replay-cache key is namespaced by runner_id
    # when one is configured.
    seen_key = _runner()._seen_key(cfg, "query:" + query_id)

    def finish(reply, secret, encrypted=False, key_id=""):
        if reply is not None and secret and opts is not None and (opts.dry_run or getattr(opts, "no_send", False)):
            reply = None
        if reply is not None and secret:
            _runner().send_mail(smtp, cfg, f"[HOMING-PIGEON] qresult {query_id}",
                      _runner()._seal_reply(reply, secret, query_id, key_id,
                                  encrypted))
        if isinstance(seen, dict) and (opts is None or not opts.dry_run):
            with R._MAIL_LOCK:
                seen[seen_key] = True
        _runner()._mark(imap, seq, opts)

    if seen is not None and seen.get(seen_key):
        _runner()._mark(imap, seq, opts)
        return True

    try:
        body = _runner().get_text_body(email.message_from_bytes(raw))
        payload, key_id, secret, encrypted = _runner()._admit_object(
            body, secrets, query_id)
    except _runner().JobCryptoError as e:
        R.log(f"query bad envelope seq {seq}: {e}", "WARN")
        _runner()._mark(imap, seq, opts)
        return True
    except Exception as e:
        R.log(f"query bad signature seq {seq}: {e}", "WARN")
        _runner()._mark(imap, seq, opts)
        return True
    if not encrypted and not _runner()._cleartext_jobs_allowed():
        R.log(f"query {query_id}: cleartext refused", "WARN")
        _runner()._auth_reject_event(base_dir, "cleartext_not_supported", feature="query")
        _runner()._mark(imap, seq, opts)
        return True

    # Hardening M5: audience binding. The expected runner_id comes from
    # the loaded config, never from the signed body. This covers the
    # ask op too: a spoofed audience cannot trick the model into
    # answering for the wrong identity.
    if not _runner().audience_allows(cfg, base_dir, payload, key_id, query_id):
        R.log(f"query rejected seq {seq}: runner_id mismatch", "WARN")
        _runner()._mark(imap, seq, opts)
        if isinstance(seen, dict) and (opts is None or not opts.dry_run):
            with R._MAIL_LOCK:
                seen[seen_key] = True
        return True

    if not _runner()._version_ok(payload.get("v")) or payload.get("type") != "query":
        R.log(f"query rejected (bad type) seq {seq}", "WARN")
        finish({
            "v": _runner().PROTOCOL_VERSION, "type": "qresult", "query_id": query_id,
            "rejected": "unsupported", "answers": [],
        }, secret, encrypted, key_id)
        return True
    ok_ts, why = _runner()._issued_at_ok(payload.get("issued_at"), cfg)
    if not ok_ts:
        R.log(f"query rejected seq {seq}: {why}", "WARN")
        _runner()._mark(imap, seq, opts)
        if isinstance(seen, dict) and (opts is None or not opts.dry_run):
            with R._MAIL_LOCK:
                seen[seen_key] = True
        return True
    # "" is the default secret. Do not replace it with query_id or each
    # query gets its own bucket and the cap never trips. PROTOCOL section 11
    # is per sender.
    if not _runner().check_rate_limit(key_id, cfg, os.path.join(base_dir, "query_times.json")):
        R.log(f"query rate limit exceeded seq {seq}", "WARN")
        finish({
            "v": _runner().PROTOCOL_VERSION, "type": "qresult", "query_id": query_id,
            "rejected": "rate_limit", "answers": [],
        }, secret, encrypted, key_id)
        return True

    job_id = payload.get("job_id")
    reply = None
    with R._RETAINED_LOCK:
        retained = _runner().load_retained(base_dir, job_id)
        if retained is None or _runner().retained_expired(retained, cfg):
            reason = "expired" if retained is not None else "unknown_job"
            R.log(f"query rejected seq {seq}: {reason} {job_id!r}", "WARN")
            reply = {
                "v": _runner().PROTOCOL_VERSION, "type": "qresult", "query_id": query_id,
                "job_id": job_id, "rejected": reason, "answers": [],
                "budget_remaining": 0,
            }
        else:
            try:
                budget = int(retained.get("budget"))
            except (TypeError, ValueError, OverflowError):
                try:
                    budget = int(cfg.get("max_query_budget", 8))
                except (TypeError, ValueError, OverflowError):
                    budget = 8
            try:
                already = int(retained.get("spent") or 0)
            except (TypeError, ValueError, OverflowError):
                already = 0
            patterns = retained.get("patterns") or _runner()._redact_patterns(cfg)
            if not isinstance(patterns, dict):
                patterns = _runner()._redact_patterns(cfg)
            view = retained.get("view") or "full"
            queries = payload.get("queries") or []
            if not isinstance(queries, list):
                queries = []
            exec_result = {
                "stdout": retained.get("stdout") or "",
                "stderr": retained.get("stderr") or "",
                "exit_code": retained.get("exit_code"),
                "confined": retained.get("confined"),
                "digest": retained.get("digest"),
            }
            try:
                answers, spent = _runner().answer_queries(
                    queries, exec_result, patterns, budget,
                    cfg=cfg, view=view, already_spent=already, base_dir=base_dir,
                )
            except Exception as e:
                # A bad query or a bad extension record rejects this
                # query. It does not retry forever and it does not
                # stop the poll.
                R.log(f"query failed: {e}", "WARN")
                reply = {
                    "v": _runner().PROTOCOL_VERSION, "type": "qresult", "query_id": query_id,
                    "job_id": job_id, "rejected": "query_error", "answers": [],
                }
            else:
                retained["spent"] = spent
                retained["saved_at"] = retained.get("saved_at") or time.time()
                _runner().save_retained(base_dir, job_id, retained)
                remaining = budget - spent
                if remaining < 0:
                    remaining = 0
                reply = {
                    "v": _runner().PROTOCOL_VERSION, "type": "qresult", "query_id": query_id,
                    "job_id": job_id, "answers": answers,
                    "budget_remaining": remaining,
                }
    finish(reply, secret, encrypted, key_id)
    return True


def answer_queries(queries, exec_result, patterns, budget, cfg=None, view="full",
                   already_spent=0, base_dir=None):
    """Answer declared queries. Every query spends 1, answered or rejected."""
    R = _runner()
    answers = []
    # A non-dict result is bad data from an extension or a corrupt retain.
    # Do not let it abort the query or the mail cycle.
    if not isinstance(exec_result, dict):
        exec_result = {}
    try:
        spent = int(already_spent or 0)
    except (TypeError, ValueError, OverflowError):
        spent = 0
    try:
        budget = int(budget)
    except (TypeError, ValueError, OverflowError):
        budget = 8
    if budget < 0:
        budget = 0
    text = _runner()._output_blob(exec_result)
    inf = _runner().inference_config(cfg) if cfg else None
    # A non-list (or non-iterable) from a poisoned job/extension must
    # not raise. Treat it as no queries.
    if not isinstance(queries, list):
        queries = []
    for q in queries:
        if spent >= budget or not isinstance(q, dict):
            if isinstance(q, dict):
                R.log(f"query op={q.get('op')} rejected: budget", "DEBUG")
                answers.append({"rejected": "budget"})
            else:
                answers.append({"rejected": "unknown_op"})
            spent += 1
            continue
        op = q.get("op")
        R.log(f"query op={op}", "DEBUG")
        if op == "attest":
            ctx = {
                "exit_code": exec_result.get("exit_code"),
                "digest": exec_result.get("digest") or hashlib.sha384(
                    text.encode("utf-8")).hexdigest(),
                "confined": exec_result.get("confined"),
                "patterns": patterns or {},
                "text": text,
            }
            atts = _runner().build_attestations([q], ctx)
            if not atts:
                answers.append({"op": "attest", "rejected": "policy"})
            else:
                item = {"op": "attest"}
                item.update(atts[0])
                if "ok" in atts[0]:
                    item["value"] = atts[0]["ok"]
                answers.append(item)
        elif op == "grep":
            if not _runner()._raw_lines_allowed(view):
                answers.append({"op": "grep", "rejected": "policy"})
            else:
                pattern = q.get("pattern") if isinstance(q.get("pattern"), str) else ""
                try:
                    cre = re.compile(pattern)
                except re.error:
                    answers.append({"op": "grep", "rejected": "bad_pattern"})
                    spent += 1
                    continue
                # The pattern and the text it runs over come from the
                # same sender, and the engine cannot be interrupted
                # mid-match: a shape that can take exponential time is
                # refused before it runs, with the shape named (Q84).
                why = _security.regex_backtracks(pattern)
                if why:
                    answers.append({"op": "grep", "rejected": "bad_pattern",
                                    "reason": why})
                    spent += 1
                    continue
                # Default 10 for an omitted, unparseable, or boolean
                # max_matches; a usable number is clamped to [0, 100].
                limit = _confval.integer(q.get("max_matches"), 10, lo=0)
                limit = min(limit, 100)
                matches = []
                truncated = False
                for line in text.splitlines():
                    if cre.search(line):
                        if len(matches) >= limit:
                            truncated = True
                            break
                        matches.append(line)
                if view == "redacted":
                    matches = [_runner().redact_text(line, patterns)[0] for line in matches]
                answers.append({
                    "op": "grep", "pattern": pattern,
                    "matches": matches, "truncated": truncated,
                })
        elif op == "tail":
            if not _runner()._raw_lines_allowed(view):
                answers.append({"op": "tail", "rejected": "policy"})
            else:
                n = min(_confval.integer(q.get("lines"), 20, lo=0), 200)
                lines = text.splitlines()[-n:] if n else []
                if view == "redacted":
                    lines = [_runner().redact_text(line, patterns)[0] for line in lines]
                answers.append({"op": "tail", "lines": lines})
        elif op == "ask":
            if inf is None:
                answers.append({"op": "ask", "rejected": "inference_unconfigured"})
            else:
                # The inference block's max_answer_chars (default 2000)
                # for an omitted, unparseable, or boolean max_chars.
                max_chars = _confval.integer(
                    q.get("max_chars"), inf["max_answer_chars"], lo=0)
                try:
                    answers.append(_runner().ask_model(
                        inf, q.get("question") or "", text, max_chars, patterns,
                        instructions=(cfg or {}).get("owner_instructions"),
                    ))
                    # A non-dict return is bad inference data. Do not let
                    # it become an answer that later .get calls crash on.
                    if not isinstance(answers[-1], dict):
                        answers[-1] = {"op": "ask", "rejected": "inference_error"}
                except Exception as e:
                    R.log(f"ask failed: {e}", "WARN")
                    answers.append({"op": "ask", "rejected": "inference_error"})
        elif op == "senses":
            if _runner()._senses is None or base_dir is None:
                answers.append({"op": "senses", "rejected": "senses_unavailable"})
            else:
                try:
                    sensors = _runner()._senses.parse_sensors(cfg or {})
                except RuntimeError:
                    sensors = {}
                recs = _runner()._senses.load_alerts(
                    base_dir,
                    sensor=q.get("sensor") if isinstance(q.get("sensor"), str) else None,
                    severity_floor=q.get("severity_floor") if isinstance(q.get("severity_floor"), str) else None,
                    since=q.get("since") if isinstance(q.get("since"), str) else None,
                    until=q.get("until") if isinstance(q.get("until"), str) else None,
                    limit=_confval.integer(q.get("limit"), 20, lo=0),
                )
                # Extension may return None or a non-iterable under fault.
                # Do not let that abort the query or the mail cycle.
                if not isinstance(recs, list):
                    R.log("senses load_alerts returned unusable data; ignoring", "WARN")
                    answers.append({"op": "senses", "rejected": "senses_unavailable"})
                    spent += 1
                    continue
                items = []
                for rec in recs:
                    # A non-dict in the list is bad extension data, not fatal.
                    if not isinstance(rec, dict):
                        continue
                    scfg = sensors.get(rec.get("sensor")) if isinstance(sensors, dict) else None
                    if not isinstance(scfg, dict):
                        scfg = {}
                    weight = scfg.get("weight", rec.get("weight", 1.0))
                    try:
                        weight = float(weight)
                    except (TypeError, ValueError, OverflowError):
                        weight = 1.0
                    if weight != weight or weight < 0 or weight in (
                            float("inf"), float("-inf")):
                        weight = 1.0
                    title_raw = rec.get("title") if isinstance(rec.get("title"), str) else ""
                    title, _ = _runner().redact_text(title_raw, patterns)
                    detail = rec.get("detail") if rec.get("detail") is not None else {}
                    if isinstance(detail, dict):
                        clean_detail = {}
                        for k, v in detail.items():
                            if isinstance(v, str):
                                v, _ = _runner().redact_text(v, patterns)
                            clean_detail[k] = v
                    elif isinstance(detail, str):
                        clean_detail, _ = _runner().redact_text(detail, patterns)
                    else:
                        clean_detail = ""
                    sig_desc = rec.get("signal_description")
                    if isinstance(sig_desc, str):
                        sig_desc, _ = _runner().redact_text(sig_desc, patterns)
                    items.append({
                        "sensor": rec.get("sensor"),
                        "severity": rec.get("severity"),
                        "title": title,
                        "detail": clean_detail,
                        "observed_at": rec.get("observed_at"),
                        "received_at": rec.get("received_at"),
                        "job_id_hint": rec.get("job_id_hint"),
                        "weight": weight,
                        "signal": rec.get("signal"),
                        "signal_description": sig_desc,
                        "extension_version": rec.get("extension_version"),
                    })
                    try:
                        items[-1]["score"] = _runner()._senses.alert_score(rec, weight)
                    except Exception:
                        # A raising scorer is bad extension data. Keep the
                        # alert with a neutral score rather than abort.
                        items[-1]["score"] = 0.0
                items.sort(key=lambda a: a["score"], reverse=True)
                # The declaration is context: for each extension-
                # backed sense in this answer, say which signals it
                # may send and what each one means, so the reader is
                # never handed a signal nobody defined.
                declared_signals = {}
                ext_registry = _runner()._extension_registry(cfg, base_dir)
                wanted = set()
                if isinstance(q.get("sensor"), str):
                    wanted.add(q["sensor"])
                wanted.update(it.get("sensor") for it in items)
                for sname in sorted(n for n in wanted
                                    if isinstance(n, str)):
                    m = ext_registry.get(sname)
                    if not isinstance(m, dict):
                        continue
                    sigs = []
                    for s in m.get("signals") or []:
                        if not isinstance(s, dict):
                            continue
                        desc = s.get("description")
                        if isinstance(desc, str):
                            desc, _ = _runner().redact_text(desc, patterns)
                        sigs.append({"name": s.get("name"),
                                     "description": desc})
                    declared_signals[sname] = {
                        "extension": m.get("name"),
                        "extension_version": m.get("version"),
                        "signals": sigs,
                    }
                senses_answer = {"op": "senses", "alerts": items,
                                 "count": len(items)}
                if declared_signals:
                    senses_answer["declared_signals"] = declared_signals
                answers.append(senses_answer)
        else:
            answers.append({"rejected": "unknown_op"})
        spent += 1
    return answers, spent


