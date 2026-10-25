"""Agent and job execution.

Extracted from runner.py.
"""
import email

def ask_model_agent(cfg, question, output_text, max_chars, patterns=None,
                    opener=None, instructions=None, base_dir=None,
                    progress=None):
    """Agentic Oracle loop for the interactive --oracle chat.

    The model may call read_file, list_dir, write_file, and run while
    it works through the question. Bounded: a round cap, a per-round
    tool cap, bounded tool results, and a context trim. The final
    answer goes through the same sanitization as ask_model.

    base_dir names this box's state directory: the model is told its
    real path, tool commands run with it as the working directory,
    and relative tool paths resolve against it.
    """
    from runner import runner as R

    patterns = patterns if patterns is not None else BUILTIN_REDACT_PATTERNS
    if not isinstance(cfg, dict):
        return {"op": "ask", "rejected": "inference_unconfigured"}
    # One read of the disclosure rule per question: the file tools
    # refuse what it withholds for the whole exchange.
    withheld = _withheld_for_tools(base_dir)
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
    timeout = _inference_timeout(cfg)
    # docs/oracle/configuring-oracle.md: agent_wall_clock_sec default 300. A
    # boolean is not a wall clock (true once gave the agent loop one
    # second).
    wall_clock = _confval.integer(cfg.get("agent_wall_clock_sec"),
                                  R._ORACLE_AGENT_WALL_CLOCK_SEC, lo=1)
    system = ASK_AGENT_SYSTEM + (
        ("\n\nOwner instructions for this box:\n" + _as_text(instructions).strip())
        if instructions and _as_text(instructions).strip() else "")
    state = _tool_base_dir(base_dir)
    if state:
        system += (
            "\n\nThis box's state directory: " + state +
            "\n- Finished job files live in: " + os.path.join(state, "retained") +
            "\n- The runner log is: " + os.path.join(state, "runner.log") +
            "\nOpen a file there only when you need that specific file; "
            "relative paths resolve against the state directory.")
    proto = _bundled_doc_path("PROTOCOL.md")
    if proto:
        system += (
            "\n\nThe Homing Pigeon protocol reference is at: " + proto +
            "\nRead it with your file tools when you need exact message "
            "shapes; it is the authoritative spec.")
    prior = recent_chat(base_dir)
    user = "Question:\n" + _as_text(question) + "\n\nOutput:\n" + _as_text(output_text)
    if prior:
        user = ("Recent chat, older turns dropped:\n" + prior
                + "\n\n" + user)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    scan_text = _as_text(output_text)
    _watch = _withheld_scan_text(base_dir)
    if _watch:
        # Scan-only: the withheld outputs join the gate's reference
        # text, never the messages above. See _withheld_scan_text.
        scan_text += "\n" + _watch
    tool_rounds = 0
    kind = _oracle_instruction_kind(question)
    reasked = False
    started = time.monotonic()

    def _progress(step):
        if progress is not None:
            progress["step"] = step

    for _round in range(R._ORACLE_AGENT_MAX_ROUNDS):
        messages = _agent_trim(messages)
        if tool_rounds and time.monotonic() - started >= wall_clock:
            # Out of investigation time: one last call, tools off, and
            # the model answers from what it has already seen. Without
            # this, a slow local model can stack round after round of
            # multi-minute calls while the chat shows nothing.
            _progress("Writing the answer from what it has")
            messages.append({
                "role": "user",
                "content": "(You are out of investigation time. Answer "
                           "the question now, in plain text, from what "
                           "you have already seen. Do not call tools.)",
            })
            msg = _inference_chat(cfg, messages, None, opener, timeout)
            if not isinstance(msg, dict) or msg.get("role") == "error":
                detail = msg.get("content") if isinstance(msg, dict) else ""
                if not isinstance(detail, str) or not detail:
                    detail = "The local model did not answer."
                return {"op": "ask", "rejected": "inference_error",
                        "detail": detail}
            reply = msg.get("content")
            if not isinstance(reply, str):
                reply = "" if reply is None else str(reply)
            return _agent_finish(cfg, messages, reply, cap, scan_text,
                                 patterns, model, opener, timeout,
                                 tool_rounds)
        _progress(f"Thinking (step {tool_rounds + 1})")
        msg = _inference_chat(cfg, messages, R._ORACLE_TOOLS, opener, timeout)
        if not isinstance(msg, dict) or msg.get("role") == "error":
            detail = msg.get("content") if isinstance(msg, dict) else ""
            if not isinstance(detail, str) or not detail:
                detail = "The local model did not answer."
            return {"op": "ask", "rejected": "inference_error", "detail": detail}
        calls = _parse_tool_calls(msg)
        if not calls and kind == "action" and not reasked \
                and tool_rounds == 0:
            # Action dispatch: an instruction's first reply must
            # be a tool call. Return the prose once with the
            # directive; a second prose reply is accepted as the
            # answer (the model naming what blocks it is a
            # legitimate outcome, endlessly re-asking is not).
            reasked = True
            R.log("oracle agent: instruction drew a prose reply; "
                "re-asking for the tool call")
            _progress("Asking her to act on the instruction")
            messages.append({"role": "assistant",
                             "content": msg.get("content") or ""})
            messages.append({
                "role": "user",
                "content": "(That was an instruction, not a "
                           "question. Call the tool that carries "
                           "it out now -- run, write_file, or "
                           "whichever fits. If one specific thing "
                           "blocks you, name that thing instead.)",
            })
            continue
        if not calls:
            note = _unparsed_tool_note(msg.get("content"))
            if note:
                R.log("oracle agent: reply looked like a tool call but did "
                    "not parse: " + note, "WARN")
            reply = msg.get("content")
            if not isinstance(reply, str):
                reply = "" if reply is None else str(reply)
            return _agent_finish(cfg, messages, reply, cap, scan_text,
                                 patterns, model, opener, timeout,
                                 tool_rounds)
        tool_rounds += 1
        R.log(f"oracle agent: round {tool_rounds}, "
            f"{len(calls)} tool call(s): "
            + ", ".join(n for _, n, _ in calls))
        executed = []
        for call_id, name, fargs in calls:
            try:
                preview = json.dumps(fargs)[:120]
            except (TypeError, ValueError):
                preview = "?"
            R.log(f"oracle tool: {name} {preview}")
            _progress(f"Running {name}")
            result_text = _run_oracle_tool(name, fargs, base_dir,
                                           withheld=withheld)
            scan_text += "\n" + result_text
            executed.append((call_id, name, fargs, result_text))
        if executed and executed[0][0].startswith(R._CONTENT_CALL_ID_PREFIX):
            # Content-embedded calls were never issued as wire
            # tool_calls. Fabricating tool_calls/tool history for them
            # makes some endpoints (Ollama) reject the next request
            # with HTTP 400, so replay the exchange as plain chat.
            R.log("oracle agent: replaying tool results as plain chat "
                "(content-embedded calls, no wire tool_calls)")
            messages.append({"role": "assistant",
                             "content": msg.get("content") or ""})
            for _, name, _, result_text in executed:
                messages.append({
                    "role": "user",
                    "content": f"Tool '{name}' returned:\n{result_text or '(no output)'}",
                })
        else:
            assistant_msg = {"role": "assistant",
                             "content": msg.get("content") or ""}
            assistant_msg["tool_calls"] = [
                {"id": call_id, "type": "function",
                 "function": {"name": name,
                              "arguments": _wire_tool_arguments(fargs)}}
                for call_id, name, fargs, _ in executed
            ]
            messages.append(assistant_msg)
            for call_id, name, _, result_text in executed:
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": result_text if result_text else "(no output)",
                })
    R.log("oracle agent: round budget exhausted", "WARN")
    return {"op": "ask", "rejected": "tool_budget"}


def execute_job(cfg, job: dict, base_dir: str) -> dict:
    from runner import runner as R
    if not isinstance(job, dict):
        raise JobRejected("job must be an object")
    if not isinstance(cfg, dict):
        cfg = {}
    job_id = _safe_job_id(job.get("job_id", ""))
    if not isinstance(base_dir, str) or not base_dir or "\x00" in base_dir:
        raise JobRejected("base_dir must be a path without a null byte")
    work = os.path.join(base_dir, "work", job_id)
    try:
        # A retry must not see files left by a previous attempt.
        if os.path.isdir(work):
            shutil.rmtree(work)
        os.makedirs(work)
    except (OSError, ValueError) as e:
        # e.g. Windows reserved names (CON, NUL, ...) or work path blocked
        # by a file, or a null in the path: poison, not transient.
        raise JobRejected(f"cannot create work dir: {e}")
    kind = job.get("kind")

    if kind == "ping":
        out = {"stdout": "pong", "stderr": "", "exit_code": 0,
               "timed_out": False, "stdout_truncated": False,
               "stderr_truncated": False, "duration_sec": 0.0}
        card = pong_platform(cfg)
        if card:
            out["platform"] = card
        return out

    if kind != "exec":
        raise JobRejected(f"unknown kind: {kind}")

    # --- validate job shape. Anything malformed here is poison (it can
    # never succeed), so reject it instead of letting a TypeError/KeyError
    # escape as transient and retry forever.
    files = job.get("files") or []
    if not isinstance(files, list):
        raise JobRejected("files must be a list")
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("name"), str) \
                or not isinstance(f.get("url"), str):
            raise JobRejected("each file needs string 'name' and 'url'")
        if "sha384" in f and not isinstance(f["sha384"], str):
            raise JobRejected("file 'sha384' must be a string")
        if os.name == "nt" and windows_reserved_name(f["name"]):
            raise JobRejected(f"unsafe file name: {f['name']}")
    args = job.get("args") or []
    if not isinstance(args, list):
        raise JobRejected("args must be a list")
    env_in = job.get("env") or {}
    if not isinstance(env_in, dict):
        raise JobRejected("env must be an object")
    script = job.get("script")
    script_url = job.get("script_url")
    if script is not None and not isinstance(script, str):
        raise JobRejected("script must be a string")
    if script_url is not None and not isinstance(script_url, str):
        raise JobRejected("script_url must be a string")
    if job.get("script_sha384") is not None \
            and not isinstance(job["script_sha384"], str):
        raise JobRejected("script_sha384 must be a string")
    try:
        timeout = int(job.get("timeout_sec") or _default_timeout_sec(cfg))
    except (TypeError, ValueError, OverflowError):
        raise JobRejected("timeout_sec must be a number")
    timeout = min(max(timeout, 1), 3600)

    # --- stage input files
    for f in files:
        dest = _staged_dest(work, f["name"])
        R.log(f"downloading {f['url']}")
        try:
            download(f["url"], dest)
        except JobRejected:
            raise  # oversize is poison, not transient
        except Exception as e:
            raise RuntimeError(f"download failed for {f['name']}: {e}")
        if f.get("sha384") and sha384_of(dest).lower() != f["sha384"].lower():
            raise JobRejected(f"SHA384 mismatch for {f['name']}")

    # --- stage script
    # Interpreter is resolved first so the filename matches it.
    # PowerShell -File requires .ps1; a bare "script" is rejected.
    # Only an ABSENT interpreter falls back to the configured or
    # platform default: a present-but-empty one is the malformed
    # value the check below exists to refuse, and an `or` chain
    # would silently substitute the default for it.
    interpreter = job.get("interpreter")
    if interpreter is None:
        interpreter = cfg.get("default_interpreter") \
            or platform_interpreter()
    if not isinstance(interpreter, list) or not interpreter or \
            not all(isinstance(x, str) for x in interpreter):
        raise JobRejected("interpreter must be a non-empty list of strings")
    if any("\x00" in x for x in interpreter):
        raise JobRejected("interpreter must not contain a null byte")
    script_path = os.path.join(work, script_filename(interpreter))
    if script_url:
        R.log(f"downloading script {script_url}")
        try:
            download(script_url, script_path)
        except JobRejected:
            raise  # oversize is poison, not transient
        except Exception as e:
            raise RuntimeError(f"script download failed: {e}")
        if job.get("script_sha384") and \
                sha384_of(script_path).lower() != job["script_sha384"].lower():
            raise JobRejected("script SHA384 mismatch")
    elif script:
        # A number is truthy. write() raises TypeError and the job
        # retried forever. A script that is not a string can never run.
        if not isinstance(script, str):
            raise JobRejected("script must be a string")
        if job.get("script_sha384") and \
                hashlib.sha384(script.encode("utf-8")).hexdigest() \
                != job["script_sha384"].lower():
            raise JobRejected("script SHA384 mismatch")
        with open(script_path, "w", encoding="utf-8") as fh:
            # The job has to be a file to run. This is not a password store.
            # codeql[py/clear-text-storage-sensitive-data]
            fh.write(script)
    else:
        raise JobRejected("exec job requires script or script_url")

    timeout = min(max(timeout, 1), 3600)
    safe_args = []
    for a in args:
        try:
            text = a if isinstance(a, str) else str(a)
        except Exception:
            raise JobRejected("args must be text")
        if "\x00" in text:
            raise JobRejected("args must not contain a null byte")
        safe_args.append(text)
    args = safe_args
    env = _scrub_env(os.environ.copy())
    for k, v in env_in.items():
        try:
            key = k if isinstance(k, str) else str(k)
            val = v if isinstance(v, str) else str(v)
        except Exception:
            raise JobRejected("env names and values must be text")
        # Popen raises ValueError on a null or an '=' in a name.
        # That is not transient. Reject it.
        if not key or "\x00" in key or "=" in key:
            raise JobRejected(f"unsafe env name: {key!r}")
        env[key] = val
    env = _scrub_env(env)  # job must not smuggle the runner's credentials back in
    before_files = _work_files(work)

    # Documented default 100000; a boolean or a value under 1 is not
    # a byte cap (True once truncated every result to one byte).
    max_out = _confval.integer(cfg.get("max_output_bytes"), 100000, lo=1)
    t0 = time.monotonic()
    # Hardening M6: confinement wraps the argv in bwrap when the
    # feature is in enforce mode and bwrap is available. With the
    # feature off (default) this is exactly the old behavior.
    c_argv, use_host_env, sandboxed = _confinement_argv(
        cfg, base_dir, job.get("job_id", ""), interpreter, script_path,
        work, args, env)
    # Hardening M8: drop to the job user when configured (POSIX,
    # root only). None when off or unavailable.
    preexec = _job_user_preexec(cfg, base_dir, job.get("job_id", ""), work)
    try:
        proc = subprocess.Popen(
            c_argv,
            cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env if use_host_env else None,
            start_new_session=(os.name != "nt"),
            preexec_fn=preexec,
        )
        R.log(f"job {job['job_id']} process started pid={proc.pid} "
            f"interpreter={interpreter[0]}"
            f"{' sandboxed' if sandboxed else ''}")
        R.log(f"job {job['job_id']} cwd={work} args={args}", "DEBUG")
    except (OSError, ValueError) as e:
        # Missing binary, a null in argv, or an unusable interpreter
        # fails the same way every cycle. Poison, not transient.
        raise JobRejected(f"cannot start interpreter: {e}")
    # Remediation watches the run (docs/design/remediation-design.md).
    # A monitor that fails to start changes nothing: the job runs
    # exactly as it did before remediation existed.
    monitor = None
    rem_st = None
    if _remediation is not None:
        try:
            rem_st = _remediation.settings(cfg)
            monitor = _start_job_monitor(
                cfg, rem_st, job_id, proc, work, base_dir,
                script_path, before_files)
        except Exception:
            monitor = None
    try:
        outs, errs = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        R.log(f"job {job['job_id']} timed out after {timeout}s; killing tree", "WARN")
        kill_tree(proc)
        outs, errs = proc.communicate()
        timed_out = True
    finally:
        if monitor is not None:
            try:
                monitor.stop()
            except Exception:
                pass
    duration = round(time.monotonic() - t0, 3)

    stdout = outs.decode("utf-8", errors="replace") if isinstance(outs, (bytes, bytearray)) else ""
    stderr = errs.decode("utf-8", errors="replace") if isinstance(errs, (bytes, bytearray)) else ""
    shown, _families = redact_text(stdout, _redact_patterns(cfg))
    R.log(f"job {job['job_id']} process finished exit={proc.returncode} "
        f"stdout={_preview(shown)!r}")
    # The full output goes to runner.log before the bounded copies
    # below are cut for the result email.
    _log_job_output(job_id, kind, stdout, stderr, cfg)
    trunc_out, trunc_err = False, False
    if len(stdout) > max_out:
        stdout, trunc_out = stdout[:max_out], True
    if len(stderr) > max_out:
        stderr, trunc_err = stderr[:max_out], True
    try:
        findings = _artifact_findings(work, before_files, cfg)
    except Exception:
        findings = []
    if findings:
        R.log(f"job {job['job_id']} artifact scan: " + "; ".join(findings),
            "WARN")
        _file_artifact_hits(base_dir, job.get("job_id"), findings)

    rem_member = None
    if monitor is not None:
        try:
            rem_member = _finish_remediation(
                cfg, rem_st, monitor, job, job_id,
                work, base_dir, script_path, proc=proc)
        except Exception as e:
            R.log(f"job {job_id} remediation failed: {e}", "WARN")
            rem_member = None

    result = {"stdout": stdout, "stderr": stderr,
              "exit_code": -1 if timed_out else (proc.returncode if proc.returncode is not None else -1),
              "timed_out": timed_out,
              "stdout_truncated": trunc_out, "stderr_truncated": trunc_err,
              "duration_sec": duration,
              "artifact_scan": findings}
    if rem_member is not None:
        result["remediation"] = rem_member
    return result


