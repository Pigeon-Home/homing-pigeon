"""Query handling.

Extracted from runner.py.
"""
import email
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
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
            # A reply that cannot be sealed or sent (Q93: the signer
            # refusing what a record a crash left put in it) is logged
            # and the query taken, never raised into the poll, where
            # the message would come back on every pass.
            try:
                _runner().send_mail(smtp, cfg, f"[HOMING-PIGEON] qresult {query_id}",
                          _runner()._seal_reply(reply, secret, query_id, key_id,
                                      encrypted))
            except Exception as e:
                R.log(f"could not send query result {query_id}: {e}", "ERROR")
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
    # A dry run verifies and answers in the log only: it takes no
    # slot of the hourly window and spends no budget of the retained
    # record (--dry-run: execute nothing, send nothing, change
    # nothing). It still says when the sender would be over the cap.
    dry = bool(opts is not None and getattr(opts, "dry_run", False))
    # "" is the default secret. Do not replace it with query_id or each
    # query gets its own bucket and the cap never trips. PROTOCOL section 11
    # is per sender.
    if not _runner().check_rate_limit(
            key_id, cfg, os.path.join(base_dir, "query_times.json"), peek=dry):
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
                if not dry:
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


def _carriable(text):
    """Text the wire can carry: a stream that is not text is nothing
    (Q90), and a lone surrogate in one -- the escape a record a crash
    left can hold, which no UTF-8 encoder and so no signer accepts
    (Q93) -- is the replacement character, as the executor's own
    decoding would have made it."""
    if not isinstance(text, str):
        return ""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-16", "surrogatepass").decode("utf-16",
                                                             "replace")


def _stream_text(exec_result):
    """The output the queries read: stdout then stderr, each text the
    wire can carry or nothing (Q90, Q93). The executor writes text;
    a stream of any other type is a record a crash left or a hand
    wrote, and the text form of a list or a number is not output --
    tail handed it back as the output's last line. The Oracle's own
    reading of a record (_output_blob) keeps the text form, since
    the owner is shown what the record holds."""
    if not isinstance(exec_result, dict):
        return ""
    return _carriable(exec_result.get("stdout")) \
        + _carriable(exec_result.get("stderr"))


# Two seconds. A plain pattern over the output cap finishes well
# under it. A polynomial one the shape check cannot name does not,
# and this engine cannot be interrupted in the process that owns
# the mailbox, so the match runs in another process (Q84).
_GREP_DEADLINE = 2.0
_worker = None
_worker_lock = threading.Lock()


def _query_worker_argv():
    """The runner, again. A frozen exe re-enters on --query-worker,
    the same way it re-enters for a transport extension. A source
    tree runs this module with -m, because executing runner.py
    as a file makes `runner` the script and not the package."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--query-worker"]
    return [sys.executable, "-m", "runner.ops.queries"]


def _stop_worker(proc):
    if proc is None:
        return
    if proc.poll() is None:
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def _drop_worker():
    """The worker is one process for a batch of greps, not a child
    a job left behind. A cycle that ends with it still running is
    a process the soak reports as not reaped."""
    global _worker
    proc = _worker
    _worker = None
    _stop_worker(proc)


def _start_worker():
    env = dict(os.environ)
    # A child that inherits mutmut's stats variable takes the stats
    # path and dies on the first call. The worker runs the real code.
    env.pop("MUTANT_UNDER_TEST", None)
    if not getattr(sys, "frozen", False):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        existing = env.get("PYTHONPATH", "")
        parts = existing.split(os.pathsep) if existing else []
        if root not in parts:
            env["PYTHONPATH"] = os.pathsep.join([root] + parts)
    kw = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
          "stderr": subprocess.DEVNULL, "env": env}
    if os.name == "posix":
        kw["start_new_session"] = True
    elif os.name == "nt":
        kw["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(_query_worker_argv(), **kw)


def _read_line(stream, deadline):
    """One line, or None when the deadline passes. select() does
    not work on a pipe on Windows, so the read sits in a thread
    the kill below unblocks."""
    box = []

    def _read():
        try:
            box.append(stream.readline())
        except Exception:
            box.append(b"")

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(deadline)
    if t.is_alive():
        return None
    return box[0] if box else b""


def grep_matches(pattern, lines, limit, deadline=None):
    """Match in the query worker. ("ok", matches, truncated) or
    ("timeout",). One worker for this process; a late reply is
    killed and the next call starts another."""
    global _worker
    if deadline is None:
        deadline = _GREP_DEADLINE
    payload = (json.dumps({"pattern": pattern, "lines": lines,
                           "limit": limit}) + "\n").encode("utf-8")
    with _worker_lock:
        try:
            if _worker is None or _worker.poll() is not None:
                _worker = _start_worker()
            proc = _worker
            try:
                proc.stdin.write(payload)
                proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                _stop_worker(proc)
                _worker = _start_worker()
                proc = _worker
                proc.stdin.write(payload)
                proc.stdin.flush()
        except OSError as e:
            _runner().log(f"query worker did not start: {e}", "WARN")
            _worker = None
            return ("timeout",)
        raw = _read_line(proc.stdout, deadline)
        if raw is None or (proc.poll() is not None and not raw):
            _stop_worker(proc)
            _worker = None
            return ("timeout",)
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, ValueError):
            _stop_worker(proc)
            _worker = None
            return ("timeout",)
        if not isinstance(msg, dict):
            return ("timeout",)
        if msg.get("rejected"):
            return ("bad_pattern",)
        matches = msg.get("matches")
        if not isinstance(matches, list):
            return ("timeout",)
        return ("ok", [m for m in matches if isinstance(m, str)],
                bool(msg.get("truncated")))


def worker_main():
    """One JSON request a line, one JSON reply a line. The parent
    kills this process when a reply is late."""
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            return 0
        try:
            req = json.loads(raw.decode("utf-8"))
            pattern = req.get("pattern") if isinstance(req, dict) else None
            lines = req.get("lines") if isinstance(req, dict) else None
            limit = req.get("limit") if isinstance(req, dict) else 0
            if not isinstance(pattern, str) or not isinstance(lines, list):
                raise ValueError("shape")
            limit = int(limit)
            cre = re.compile(pattern)
        except Exception:
            sys.stdout.buffer.write(b'{"rejected":"bad_pattern"}\n')
            sys.stdout.buffer.flush()
            continue
        matches = []
        truncated = False
        for line in lines:
            if not isinstance(line, str):
                continue
            if cre.search(line):
                if len(matches) >= limit:
                    truncated = True
                    break
                matches.append(line)
        body = json.dumps(
            {"matches": matches, "truncated": truncated}).encode("utf-8")
        sys.stdout.buffer.write(body + b"\n")
        sys.stdout.buffer.flush()


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
    text = _stream_text(exec_result)
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
                # Whatever the engine refuses is a bad pattern: a
                # syntax error, and a repetition count past what it
                # can hold (OverflowError, Q92) the same.
                try:
                    re.compile(pattern)
                except Exception:
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
                # The match itself is the other process. A reply that
                # does not come back within the deadline is a kill,
                # and the answer is timeout, not a wedged mail cycle.
                found = grep_matches(pattern, text.splitlines(), limit)
                if found[0] == "timeout":
                    answers.append({"op": "grep", "rejected": "timeout"})
                elif found[0] == "bad_pattern":
                    answers.append({"op": "grep", "rejected": "bad_pattern"})
                else:
                    matches, truncated = found[1], found[2]
                    if view == "redacted":
                        matches = [_runner().redact_text(line, patterns)[0]
                                   for line in matches]
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
    _drop_worker()
    return answers, spent


if __name__ == "__main__":
    raise SystemExit(worker_main())


