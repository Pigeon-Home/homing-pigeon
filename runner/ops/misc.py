"""Window, ask, v2, and disk helpers.

Extracted from runner.py.
"""

def oracle_window(cfg, port=11436, open_browser=True, cfg_path=None) -> int:
    """Open the Oracle chat and wait. Does not poll the mailbox."""
    from runner import runner as R

    try:
        port = int(port)
    except (TypeError, ValueError):
        print("error: --oracle-port must be an integer", file=sys.stderr)
        return 2
    if port < 0 or port > 65535:
        print("error: --oracle-port is out of range", file=sys.stderr)
        return 2
    if not isinstance(cfg, dict):
        cfg = {}
    base = _base_dir_for(cfg, cfg_path)
    global _LOG_FILE
    R._LOG_FILE = os.path.join(base, "runner.log")
    _refresh_log_settings(cfg, base)
    _announce_oracle_log()
    try:
        httpd = make_oracle_server(cfg, "127.0.0.1", port, base_dir=base)
    except OSError as e:
        print(f"oracle chat could not listen: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    bound = httpd.socket.getsockname()[1]
    url = f"http://127.0.0.1:{bound}/"
    print(f"homing-pigeon {__version__} --oracle")
    print(f"Oracle chat on {url}")
    print(f"Chat log: {os.path.join(base, 'oracle-chat.jsonl')}")
    if cfg_path:
        print(f"Config: {os.path.abspath(cfg_path)}")
    inf = inference_config(cfg) or {}
    if _oracle_mode(cfg) == "deterministic":
        print("Oracle mode: deterministic (Pi Light) -- no local model; "
              "answers are this box's records, un-narrated")
    elif inf.get("model"):
        print(f"Inference: local model {inf['model']} ({inf['endpoint']})")
    else:
        print("Inference: not configured (Ask stays off)")
    print("Loopback only. Leave this process running. Ctrl+C closes it.")
    print("The chat does not poll the mailbox; run the runner without "
          "--oracle (or the installed service) to handle email jobs.")
    try:
        record_oracle_turn(base, cfg, "", {}, event="open")
    except Exception as e:
        R.log(f"oracle open not recorded: {e}", "WARN")
    if inf.get("model"):
        warm_thread = threading.Thread(
            target=_warm_oracle_model, args=(inf,), daemon=True)
        warm_thread.start()
    else:
        warm_thread = None
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if warm_thread is not None:
            # The warm-up logs through the inference path, into the
            # base dir. Give it a bounded moment to finish so it
            # never writes after the window has closed -- a racing
            # writer in a directory being torn down is exactly what
            # Windows refuses to delete around (WinError 145 in the
            # --oracle diagnostics test). The daemon flag still caps
            # the wait if the endpoint hangs.
            warm_thread.join(timeout=5)
        record_oracle_turn(base, cfg, "", {}, event="close")
        httpd.server_close()
    return 0


def _ask_model_once(cfg, question, output_text, max_chars, patterns=None, opener=None, instructions=None):
    """POST a constrained question to a loopback OpenAI-compatible endpoint.

    cfg is the dict from inference_config. The reply is truncated, redacted,
    and secret-scanned before it can be emailed. A hit returns
    {"rejected": "sanitization"} and the model text is dropped.
    """
    from runner import runner as R

    patterns = patterns if patterns is not None else BUILTIN_REDACT_PATTERNS
    if not isinstance(cfg, dict):
        return {"op": "ask", "rejected": "inference_unconfigured"}
    endpoint = cfg.get("endpoint") or ""
    model = cfg.get("model") or ""
    if not isinstance(endpoint, str) or not isinstance(model, str):
        return {"op": "ask", "rejected": "inference_unconfigured"}
    if not endpoint or not model or not _endpoint_is_loopback(endpoint):
        return {"op": "ask", "rejected": "inference_unconfigured"}
    try:
        cap = int(max_chars)
    except (TypeError, ValueError, OverflowError):
        try:
            cap = int(cfg.get("max_answer_chars") or 2000)
        except (TypeError, ValueError, OverflowError):
            cap = 2000
    if cap < 0:
        cap = 0
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ASK_SYSTEM + (("\n\nOwner instructions for this box:\n" + _as_text(instructions).strip()) if instructions and _as_text(instructions).strip() else "")},
            {"role": "user", "content":
             "Question:\n" + _as_text(question) + "\n\nOutput:\n" + _as_text(output_text)},
        ],
    }
    _apply_keep_alive(cfg, payload)
    req = Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    open_fn = opener or _default_inference_open
    # PROTOCOL.md and docs/oracle/configuring-oracle.md: timeout_sec default
    # 180. Anything that is not a positive finite number gets that,
    # not a second fallback of 60 that the docs never named.
    timeout = _inference_timeout(cfg)
    R.log(f"ask: calling model {model}")
    started = time.monotonic()
    raw_text = None
    try:
        with open_fn(req, timeout=timeout) as resp:
            raw = resp.read(1_000_000)
        raw_text = raw.decode("utf-8", "replace")
        parsed = json.loads(raw.decode("utf-8"))
        reply = parsed["choices"][0]["message"]["content"]
    except Exception as e:
        err_body = None
        if isinstance(e, HTTPError):
            try:
                err_body = e.read().decode("utf-8", "replace")
            except Exception:
                err_body = None
        _oracle_log_exchange(endpoint, model, payload, started,
                             error=str(e), error_body=err_body,
                             raw=raw_text)
        R.log(f"inference call failed: {e}", "WARN")
        return {"op": "ask", "rejected": "inference_error"}
    _oracle_log_exchange(endpoint, model, payload, started,
                         response=reply, raw=raw_text)
    if not isinstance(reply, str):
        reply = str(reply)
    return _sanitize_model_reply(reply, cap, output_text, patterns, model)


def _v2_ingest(cfg, imap, base_dir, seen, secrets, opts):
    """File version 2 messages that arrived while a question is open.

    Jobs stay where they are. A second job must not start on
    top of the one that asked. ``seen`` is unused; the mail
    core's own mark is what records a message.
    """
    from runner import runner as R

    del seen
    if _protocol_v2 is None:
        return
    if imap is not None and not isinstance(imap, _NullIMAP):
        fetch = globals().get("fetch_job_mails")
        if fetch is None:
            return
        try:
            mails = fetch(imap)
        except Exception as e:
            R.log(f"version 2 ingest failed: {e}", "WARN")
            return
        for seq, raw in mails:
            try:
                msg = email.message_from_bytes(raw)
                subject = str(msg["Subject"] or "")
            except Exception:
                continue
            if _protocol_v2.subject_kind(subject) is None:
                continue
            handle_v2_mail(cfg, imap, None, seq, raw, subject,
                           secrets, opts, base_dir)
        return
    if _transports is None:
        return
    try:
        names = _enabled_transports(cfg)
    except Exception as e:
        R.log(f"version 2 ingest failed: {e}", "WARN")
        return
    for name in names:
        try:
            messages = _transports.fetch_channel_messages(
                base_dir, name, log=log)
        except Exception as e:
            R.log(f"version 2 ingest {name} failed: {e}", "WARN")
            continue
        for msg in messages:
            if _protocol_v2.subject_kind(msg.subject) is None:
                continue
            safe = str(msg.subject).replace("\r", " ").replace("\n", " ")
            raw = ("Subject: " + safe + "\r\n"
                   "From: transport\r\n"
                   'Content-Type: text/plain; charset="utf-8"\r\n'
                   "\r\n" + str(msg.body)).encode("utf-8")
            try:
                box = _NullIMAP()
                handle_v2_mail(
                    cfg, box, _CaptureSMTP(), "transport",
                    raw, msg.subject, secrets, opts, base_dir)
            except Exception as e:
                R.log(f"version 2 ingest message failed: {e}", "WARN")
                continue
            if not box.marked:
                # A question this process is not answering stays
                # in the inbox. Acking it would mark the mail seen.
                continue
            try:
                msg.ack()
            except Exception as e:
                R.log(f"version 2 ingest ack failed: {e}", "WARN")


def _disk_owns(base_dir, skey, seen):
    """Claim skey on disk, or report that someone else holds it.

    Returns True when this process may execute. A seen.json that
    already has the key, or a live claim file, returns False and
    records the key in the in-memory cache when it is already done.
    """
    from runner import runner as R

    if not _valid_base(base_dir):
        return True
    seen_path = os.path.join(base_dir, "seen.json")
    folder, claim = _claim_path(base_dir, skey)
    decision = {"ok": False}

    def mutate(disk):
        if skey in disk:
            if isinstance(seen, dict):
                seen[skey] = True
            decision["ok"] = False
            return disk
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            decision["ok"] = False
            return disk
        if os.path.exists(claim):
            pid = None
            try:
                with open(claim, encoding="utf-8") as fh:
                    pid = int(fh.readline().strip() or "0")
            except (OSError, ValueError):
                pid = None
            try:
                age = time.time() - os.path.getmtime(claim)
            except OSError:
                age = 0
            if pid == os.getpid():
                if isinstance(seen, dict) and seen.get(skey):
                    decision["ok"] = False
                    return disk
            elif _pid_alive(pid):
                decision["ok"] = False
                return disk
            elif not pid and age < R._CLAIM_STALE_SEC:
                decision["ok"] = False
                return disk
            try:
                os.unlink(claim)
            except OSError:
                decision["ok"] = False
                return disk
        try:
            fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError:
            decision["ok"] = False
            return disk
        try:
            os.write(fd, f"{os.getpid()}\n{time.time()}\n{skey}\n".encode("utf-8"))
        finally:
            os.close(fd)
        decision["ok"] = True
        return disk

    _with_seen_file(seen_path, mutate)
    return decision["ok"]


