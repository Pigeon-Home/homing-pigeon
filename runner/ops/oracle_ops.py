"""Oracle brief and tool helpers.

Extracted from runner.py.
"""
from datetime import datetime, timezone, timedelta
import os
import subprocess
import sys


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore

def _oracle_brief(cfg, base_dir, record, opener=None):
    """Assess one woken signal and file the brief. Never raises.

    Runs on a daemon thread after the wake gate fires. With a local
    model configured, the Oracle itself (_runner().ask_model_agent, the same
    path the interactive doors use) assesses the signal against the
    box's current context. Without one, the brief is a deterministic
    note saying so -- the mechanism stays honest and testable with
    no model. In deterministic mode (Pi Light) the brief is
    explicitly that note, labeled as such, and no model is called
    even if one is configured. The brief lands in
    oracle-briefs.jsonl and in the runner _runner().log, where later Oracle
    context reads it back.
    """
    R = _runner()
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
        elif _runner().inference_config(cfg) is None:
            brief["assessment"] = (
                "No local model is configured on this box, so the "
                "Oracle made no assessment. The alert was filed in "
                "the senses store; review it there.")
        else:
            inf = _runner().inference_config(cfg)
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
            ans = _runner().ask_model_agent(
                inf, "\n".join(lines),
                _runner().oracle_context(base_dir,
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
    _runner().log(f"oracle brief ({sensor}/{signal or '-'}): {brief['assessment']}")
    return brief


# ---- the run tool's operator mode (F2) --------------------------------
#
# The interactive Oracle's charter (runner/ops/oracle_tools.py, pinned
# by test_oracle_charter.py) gives the owner's local debugging partner
# full hands, and that does not change here. What an operator CAN do
# is tune the run tool per deployment, the way every other control in
# this codebase is tuned: a config knob with a CLI override.
#
# oracle_tool_mode (also spelled oracle.tool_mode, the nested form)
# takes one of ORACLE_TOOL_MODES; the default is full, the charter
# behavior. readonly refuses the run tool. confirm asks at the
# runner's terminal before each command and refuses when there is no
# terminal to ask at. confined refuses with a not-available error:
# the job sandbox (runner/guard/sandbox.py) confines staged job
# scripts -- an interpreter, a script file, a bound workdir -- and
# that shape cannot be applied to an interactive shell command
# without pretending, so the mode says so instead of running the
# command unconfined under a confined label.
#
# In every mode that executes, the child gets a scrubbed environment
# (see _oracle_tool_env): the runner's environment is never inherited
# whole, because untrusted content the Oracle reads can steer the
# model, and a child that can print its environment would hand the
# runner's secrets to whatever steered it.
ORACLE_TOOL_MODES = ("full", "confirm", "confined", "readonly")


def _oracle_tool_mode(cfg) -> str:
    """The configured run-tool mode: the flat key wins (the CLI
    override writes it, and a flag beats the file), then the nested
    oracle.tool_mode, then the charter default, full. A non-string
    value reads as unset here; _validate_oracle_tool_mode refuses it
    at startup, naming the key."""
    if isinstance(cfg, dict):
        flat = cfg.get("oracle_tool_mode")
        if isinstance(flat, str) and flat:
            return flat
        oracle = cfg.get("oracle")
        if isinstance(oracle, dict):
            nested = oracle.get("tool_mode")
            if isinstance(nested, str) and nested:
                return nested
    return "full"


def _validate_oracle_tool_mode(cfg):
    """Raise RuntimeError for a present-but-invalid tool mode.

    Names the key and the bad value. Call at startup, before any
    model or tool work: a value that is not one of the four modes
    decides what the run tool may do on this box, so it is refused,
    never silently read as full.
    """
    if not isinstance(cfg, dict):
        return
    oracle = cfg.get("oracle")
    if oracle is not None and not isinstance(oracle, dict):
        raise RuntimeError(
            "config error: oracle must be an object, got %s"
            % type(oracle).__name__)
    choices = ", ".join(ORACLE_TOOL_MODES)
    flat = cfg.get("oracle_tool_mode")
    if flat is not None and flat not in ORACLE_TOOL_MODES:
        raise RuntimeError(
            "config error: oracle_tool_mode must be one of %s "
            "(got %r)" % (choices, flat))
    if isinstance(oracle, dict) and "tool_mode" in oracle:
        nested = oracle["tool_mode"]
        if nested not in ORACLE_TOOL_MODES:
            raise RuntimeError(
                "config error: oracle.tool_mode must be one of %s "
                "(got %r)" % (choices, nested))


# The explicit minimal environment a run-tool child may see. Anything
# not named here does not cross, however benign it looks: an allowlist
# is the only shape that stays closed when the runner's own
# environment grows a new variable nobody reviewed.
_ENV_ALLOWLIST = frozenset({
    "PATH", "HOME", "LANG", "LANGUAGE", "TERM", "TMPDIR", "TZ",
    "USER", "LOGNAME",
})
_ENV_ALLOWLIST_WIN32 = frozenset({
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE",
    "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA",
})
# Name fragments that mark a variable as secret-bearing wherever it
# appears in the name. Compared uppercase, so the match is
# case-insensitive on every platform.
_SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH",
                       "CREDENTIAL")


def _env_name_is_secret(name) -> bool:
    upper = name.upper()
    if upper.startswith("PIGEON_"):
        # The runner's own credential prefix (runner.py's
        # _SENSITIVE_ENV_PREFIXES), named rather than imported so
        # this module keeps loading without the runner module.
        return True
    return any(marker in upper for marker in _SECRET_ENV_MARKERS)


def _oracle_tool_env(source=None) -> dict:
    """The scrubbed environment for a run-tool child.

    Built from `source` (default os.environ): only the allowlisted
    names cross (plus LC_* locale names, and the Windows shell
    essentials on win32), and a secret-marked name never crosses
    even if a future allowlist edit names it.
    """
    if source is None:
        source = os.environ
    out = {}
    try:
        items = source.items()
    except AttributeError:
        return out
    for key, value in items:
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if _env_name_is_secret(key):
            continue
        upper = key.upper()
        if upper in _ENV_ALLOWLIST or upper.startswith("LC_"):
            out[key] = value
        elif os.name == "nt" and upper in _ENV_ALLOWLIST_WIN32:
            out[key] = value
    return out


def _oracle_run_confirmed(command, confirm_fn=None) -> bool:
    """The confirm mode's gate: True only on an affirmative answer.

    confirm_fn (a test seam) answers for the operator when given.
    Otherwise the runner's own terminal is asked, in the setup
    wizard's yes/no shape; no terminal, a closed stdin, or anything
    but an explicit yes refuses -- a confirmation that cannot be
    asked for is a no.
    """
    if confirm_fn is not None:
        try:
            return bool(confirm_fn(command))
        except Exception:
            return False
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
    except Exception:
        return False
    try:
        answer = input(
            "oracle run tool (confirm mode): allow this command?\n"
            f"  {command}\n[y/N] ")
    except (EOFError, KeyboardInterrupt, OSError):
        return False
    return isinstance(answer, str) \
        and answer.strip().lower() in ("y", "yes")


def _run_oracle_tool(name, args, base_dir=None, withheld=None,
                     cfg=None, tool_mode=None, confirm_fn=None) -> str:
    """Execute one Oracle agent tool call. Never raises.

    The model is untrusted input here, same class as job JSON: names
    and args are validated strictly, everything is bounded, and
    failures come back as an error string the model can read.

    withheld: the real paths the extension sources disclosure rule
    keeps from the Oracle (computed per call when None). read_file,
    list_dir, and write_file refuse them, and list_dir leaves them
    out of a listing. The run tool is a shell and is not path
    filtered; it is gated by the operator's tool mode instead (see
    ORACLE_TOOL_MODES above): tool_mode, when given, wins over the
    mode cfg names, and both default to the charter's full.
    """
    R = _runner()
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
        mode = tool_mode if tool_mode is not None \
            else _oracle_tool_mode(cfg)
        if mode not in ORACLE_TOOL_MODES:
            return (f"error: oracle tool mode {mode!r} is not one of "
                    + ", ".join(ORACLE_TOOL_MODES)
                    + "; refusing to run (fix oracle_tool_mode)")
        if mode == "readonly":
            return ("error: the run tool is disabled by oracle tool "
                    "mode 'readonly' (set oracle_tool_mode to full "
                    "or confirm to allow commands)")
        if mode == "confined":
            return ("error: oracle tool mode 'confined' is not "
                    "available: the job sandbox confines staged job "
                    "scripts and cannot be applied to the interactive "
                    "run tool; refusing to run the command unconfined")
        if mode == "confirm" \
                and not _oracle_run_confirmed(command, confirm_fn):
            return ("error: the operator did not confirm this "
                    "command (oracle tool mode 'confirm'); not run")
        try:
            timeout = int(args.get("timeout_sec", 30))
        except (TypeError, ValueError, OverflowError):
            timeout = 30
        timeout = max(1, min(timeout, 120))
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout, cwd=R._tool_base_dir(base_dir) or None,
                env=_oracle_tool_env())
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


