"""Oracle brief and tool helpers.

Extracted from runner.py.
"""

def _oracle_brief(cfg, base_dir, record, opener=None):
    """Assess one woken signal and file the brief. Never raises.

    Runs on a daemon thread after the wake gate fires. With a local
    model configured, the Oracle itself (ask_model_agent, the same
    path the interactive doors use) assesses the signal against the
    box's current context. Without one, the brief is a deterministic
    note saying so -- the mechanism stays honest and testable with
    no model. In deterministic mode (Pi Light) the brief is
    explicitly that note, labeled as such, and no model is called
    even if one is configured. The brief lands in
    oracle-briefs.jsonl and in the runner log, where later Oracle
    context reads it back.
    """
    from runner import runner as R

    record = record if isinstance(record, dict) else {}
    sensor = record.get("sensor")
    sensor = sensor if isinstance(sensor, str) and sensor else "?"
    signal = record.get("signal")
    signal = signal if isinstance(signal, str) and signal else None
    severity = record.get("severity")
    severity = severity if isinstance(severity, str) else "info"
    title = record.get("title")
    title = title if isinstance(title, str) else ""
    brief = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sensor": sensor,
        "signal": signal,
        "severity": severity,
        "title": title,
        "status": "no_inference",
        "assessment": "",
    }
    try:
        if R._oracle_mode(cfg) == "deterministic":
            brief["status"] = "deterministic"
            brief["mode"] = "deterministic"
            brief["assessment"] = (
                "Deterministic brief (Pi Light): the Oracle on this "
                "box runs without a local model, so this brief is "
                "assembled from the alert itself, not a model "
                f"assessment. {severity} alert from sensor {sensor}"
                + (f", signal {signal}" if signal else "")
                + (f": {title}" if title else "")
                + ". The alert was filed in the senses store; "
                "review it there.")
        elif inference_config(cfg) is None:
            brief["assessment"] = (
                "No local model is configured on this box, so the "
                "Oracle made no assessment. The alert was filed in "
                "the senses store; review it there.")
        else:
            inf = inference_config(cfg)
            lines = [
                "A sensor signal just arrived on this box and crossed "
                "the wake threshold.",
                f"Sensor: {sensor}",
                f"Signal: {signal or '(no signal named)'}",
            ]
            desc = record.get("signal_description")
            if isinstance(desc, str) and desc:
                lines.append(
                    f"What the signal means (declared by its "
                    f"extension): {desc}")
            lines.append(f"Severity: {severity}")
            lines.append(f"Title: {title}")
            lines.append(
                "Assess what happened, using the box context "
                "provided, and state plainly what happened and what, "
                "if anything, the owner should do.")
            ans = ask_model_agent(
                inf, "\n".join(lines),
                oracle_context(base_dir,
                               watch=R._oracle_watch_enabled(cfg)),
                inf.get("max_answer_chars") or 2000,
                R._redact_patterns(cfg),
                opener=opener,
                instructions=cfg.get("owner_instructions")
                if isinstance(cfg, dict) else None,
                base_dir=base_dir,
            )
            if isinstance(ans, dict) and isinstance(ans.get("answer"), str) \
                    and ans["answer"]:
                brief["status"] = "assessed"
                brief["assessment"] = ans["answer"]
            else:
                why = ans.get("rejected") if isinstance(ans, dict) else None
                brief["status"] = "inference_failed"
                brief["assessment"] = (
                    "The local model produced no assessment"
                    + (f" ({why})" if isinstance(why, str) and why else "")
                    + ". The alert was filed in the senses store.")
    except Exception as e:
        brief["status"] = "inference_failed"
        brief["assessment"] = (
            f"The briefing attempt failed: {e}. "
            f"The alert was filed in the senses store.")
    R._append_brief(base_dir, brief)
    log(f"oracle brief ({sensor}/{signal or '-'}): {brief['assessment']}")
    return brief


def _run_oracle_tool(name, args, base_dir=None, withheld=None) -> str:
    """Execute one Oracle agent tool call. Never raises.

    The model is untrusted input here, same class as job JSON: names
    and args are validated strictly, everything is bounded, and
    failures come back as an error string the model can read.

    withheld: the real paths the extension sources disclosure rule
    keeps from the Oracle (computed per call when None). read_file,
    list_dir, and write_file refuse them, and list_dir leaves them
    out of a listing. The run tool is a shell and is not filtered.
    """
    from runner import runner as R

    if not isinstance(args, dict):
        return "error: args must be an object"
    if name in ("read_file", "list_dir", "write_file") and withheld is None:
        withheld = R._withheld_for_tools(base_dir)
    if name == "read_file":
        path = args.get("path")
        if not isinstance(path, str) or not path:
            return "error: path must be a non-empty string"
        path = R._resolve_tool_path(path, base_dir)
        if not R._tool_stays_inside(path, base_dir):
            return "error: path leaves the state dir"
        if R._tool_withheld(path, base_dir, withheld):
            return R._WITHHELD_TOOL_ERROR
        raw_cap = args.get("max_chars", 4000)
        if isinstance(raw_cap, bool):
            max_chars = 4000
        else:
            try:
                max_chars = int(raw_cap)
            except (TypeError, ValueError, OverflowError):
                max_chars = 4000
        max_chars = max(1, min(max_chars, 20000))
        try:
            with open(path, "rb") as fh:
                raw = fh.read(max_chars * 4)
        except OSError as e:
            return f"error: cannot read {path!r}: {e.strerror or e}"
        except Exception as e:
            return f"error: cannot read {path!r}: {e}"
        text = raw.decode("utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        return text if text else "(empty file)"
    if name == "list_dir":
        path = args.get("path")
        if not isinstance(path, str) or not path:
            return "error: path must be a non-empty string"
        path = R._resolve_tool_path(path, base_dir)
        if not R._tool_stays_inside(path, base_dir):
            return "error: path leaves the state dir"
        if R._tool_withheld(path, base_dir, withheld):
            return R._WITHHELD_TOOL_ERROR
        try:
            entries = os.listdir(path)
        except OSError as e:
            return f"error: cannot list {path!r}: {e.strerror or e}"
        except Exception as e:
            return f"error: cannot list {path!r}: {e}"
        if withheld:
            entries = [e for e in entries if not R._tool_withheld(
                os.path.join(path, e), base_dir, withheld)]
        out = []
        for entry in sorted(entries)[:200]:
            full = os.path.join(path, entry)
            try:
                suffix = "/" if os.path.isdir(full) else ""
            except OSError:
                suffix = ""
            out.append(entry + suffix)
        if len(entries) > 200:
            out.append(f"...[{len(entries) - 200} more]")
        return "\n".join(out) if out else "(empty directory)"
    if name == "write_file":
        path = args.get("path")
        content = args.get("content")
        if not isinstance(path, str) or not path:
            return "error: path must be a non-empty string"
        if not isinstance(content, str):
            return "error: content must be a string"
        path = R._resolve_tool_path(path, base_dir)
        if not R._tool_stays_inside(path, base_dir):
            return "error: path leaves the state dir"
        if R._tool_withheld(path, base_dir, withheld):
            return R._WITHHELD_TOOL_ERROR
        if len(content) > 200000:
            return "error: content too large (200000 char cap)"
        try:
            parent = os.path.dirname(os.path.abspath(path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = R._safe_open(path, flags, 0o600)
            try:
                os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)
        except OSError as e:
            return f"error: cannot write {path!r}: {e.strerror or e}"
        except Exception as e:
            return f"error: cannot write {path!r}: {e}"
        return f"wrote {len(content)} chars to {path}"
    if name == "run":
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            return "error: command must be a non-empty string"
        if len(command) > 8000:
            return "error: command too long (8000 char cap)"
        try:
            timeout = int(args.get("timeout_sec", 30))
        except (TypeError, ValueError, OverflowError):
            timeout = 30
        timeout = max(1, min(timeout, 120))
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout, cwd=R._tool_base_dir(base_dir) or None)
        except subprocess.TimeoutExpired:
            return f"error: command timed out after {timeout}s"
        except Exception as e:
            return f"error: cannot run command: {e}"
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
        blob = (out + ("\n" + err if err else "")).strip()
        if len(blob) > 8000:
            blob = blob[:8000] + "\n...[truncated]"
        return f"exit={proc.returncode}\n{blob if blob else '(no output)'}"
    return f"error: unknown tool {name!r}"


