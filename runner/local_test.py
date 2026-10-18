#!/usr/bin/env python3
"""Local SI test harness.

Acts as the cloud SI against a runner on the same machine. It ensures
the local model is up, then lets you chat: each line you type is an
`ask` from the SI. The harness builds a signed query, runs it through
the Oracle path, and prints the answer. No email is sent.

This is a development loop, not a unit test. Run it, talk to the
Oracle, change config or the system prompt, run it again.

    python3 runner/runner.py --config config.json --local-test
    python3 runner/runner.py --config config.json --local-test --browser

The browser mode serves a single loopback page so the chat opens in
a window. It binds 127.0.0.1 only and exits if the bind is not
loopback.
"""
import json
import os
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timezone

# Works both as a package module (CI) and as a sibling script.
try:
    from runner import runner as R  # package: runner/runner.py
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import runner as R  # script: python3 runner/local_test.py


SI_PORT = 11435
ORACLE_PORT = 11434
SI_SYSTEM = (
    "You are the cloud SI in a local test. You are a different model "
    "instance from the Oracle that runs on this box. You do not see the "
    "Oracle's context. When you want to learn something about a job on "
    "the box, say so plainly; the harness will send your question to the "
    "Oracle and bring the answer back. Do not pretend you already know "
    "the job output."
)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _port_up(port) -> bool:
    import socket
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def start_si_instance() -> bool:
    """Start a second Ollama process for the SI, on its own port.

    The Oracle keeps using its configured endpoint (usually 11434).
    The SI gets 11435. Separate process, separate context.
    """
    if _port_up(SI_PORT):
        print(f"SI instance already listening on 127.0.0.1:{SI_PORT}")
        return True
    import shutil
    import subprocess
    if not shutil.which("ollama"):
        print("ollama not found; cannot start a second instance")
        return False
    env = os.environ.copy()
    env["OLLAMA_HOST"] = f"127.0.0.1:{SI_PORT}"
    try:
        # start_new_session is POSIX-only. On Windows it raises
        # ValueError before the process is created, so the SI never
        # starts and the browser page never opens. Use the same
        # Windows-safe kwargs the installer uses.
        try:
            from runner.install import daemon_popen_kwargs
        except ImportError:
            from install import daemon_popen_kwargs
        subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            **daemon_popen_kwargs(os.name == "nt"),
        )
    except Exception as e:
        print(f"could not start SI instance: {e}")
        return False
    import time
    for _ in range(20):
        if _port_up(SI_PORT):
            print(f"SI instance started on 127.0.0.1:{SI_PORT}")
            return True
        time.sleep(0.5)
    print("SI instance did not become ready")
    return False


def ask_si(model: str, history: list, question: str) -> str:
    """Talk to the SI instance. history is a list of {role, content}."""
    from urllib.request import Request, urlopen
    if not isinstance(history, list):
        history = []
    messages = [{"role": "system", "content": SI_SYSTEM}] + history
    messages.append({"role": "user", "content": question})
    try:
        payload = json.dumps({"model": model, "messages": messages}).encode()
    except (TypeError, ValueError):
        return ""
    req = Request(
        f"http://127.0.0.1:{SI_PORT}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            parsed = json.loads(resp.read().decode())
        content = parsed["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            content = str(content)
        return content
    except Exception:
        return ""


def build_ask_job(question: str, secret: str, job_id=None) -> dict:
    """A signed job that declares a single ask query. The SI side."""
    job_id = job_id or str(uuid.uuid4())
    payload = {
        "v": R.PROTOCOL_VERSION,  # pyrefly: ignore[missing-attribute]  # R is runner.runner at runtime; pyrefly binds the package
        "type": "job",
        "job_id": job_id,
        "issued_at": _now(),
        "kind": "ping",
        "result_policy": {
            "view": "attested",
            "queries": [{"op": "ask", "question": question, "max_chars": 500}],
            "query_budget": 4,
        },
    }
    signed = R.sign_payload(payload, secret)
    return json.loads(signed)


def answer_as_oracle(cfg, question: str) -> dict:
    """Run one ask through the Oracle path and return the first answer dict.

    Builds the signed ask job the SI would send, verifies it exactly as
    the runner verifies an incoming job, then runs the declared queries
    through the result policy and the query machinery (budget, op policy,
    redaction). Nothing is emailed; this is the local equivalent of the
    SI -> signed job -> Oracle loop.
    """
    inf = R.inference_config(cfg)
    if not inf:
        return {"rejected": "inference_unconfigured"}
    secret = cfg.get("shared_secret") or ""
    if not secret:
        return {"rejected": "no shared_secret in config"}
    job = build_ask_job(question, secret)
    payload = {k: v for k, v in job.items() if k != "sig"}
    try:
        verified = R.verify_body(R.sign_payload(payload, secret), secret)
    except Exception as e:
        return {"rejected": f"signature: {e}"}
    patterns = R._redact_patterns(cfg)
    exec_result = {
        "stdout": "", "stderr": "", "exit_code": 0, "timed_out": False,
        "duration_sec": 0.0, "confined": True,
    }
    result, _retain = R.apply_result_policy(  # pyrefly: ignore[missing-attribute]  # R is runner.runner at runtime; pyrefly binds the package
        cfg, verified, exec_result, patterns, confined=True)
    declared = (verified.get("result_policy") or {}).get("queries") or []
    if not isinstance(declared, list):
        declared = []
    view = result.get("view") or "full"
    answers, _spent = R.answer_queries(  # pyrefly: ignore[missing-attribute]  # R is runner.runner at runtime; pyrefly binds the package
        declared, exec_result, patterns, R.query_budget(cfg, verified),  # pyrefly: ignore[missing-attribute]  # R is runner.runner at runtime
        cfg=cfg, view=view,
    )
    if not answers:
        return {"rejected": "no_queries"}
    return answers[0]


def repl(cfg) -> int:
    """Terminal chat. You are the cloud SI."""
    print("local SI test. You are the cloud SI. Type a question, or 'quit'.")
    print("The Oracle answers through the local model. Nothing is emailed.")
    if cfg.get("owner_instructions"):
        print(f"owner instructions: {cfg['owner_instructions'][:120]}")
    while True:
        try:
            line = input("SI> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            return 0
        ans = answer_as_oracle(cfg, line)
        if "answer" in ans:
            print(f"Oracle> {ans['answer']}")
        else:
            print(f"Oracle> rejected: {ans.get('rejected', ans)}")


def _open_webui_available() -> bool:
    import shutil
    return bool(shutil.which("open-webui"))


def browser_chat(cfg, port=8080) -> int:
    """Open the SI in Open WebUI, the chat interface people already use.

    Open WebUI is pointed at the SI Ollama instance (port 11435), not
    the Oracle. If open-webui is not installed, print how to get it
    and do not start a homemade page.
    """
    if not start_si_instance():
        return 2
    if not _open_webui_available():
        print("Open WebUI is not installed.")
        print("Install it with: pip install open-webui")
        print("Then re-run with --local-test --browser.")
        print(f"It should talk to the SI at http://127.0.0.1:{SI_PORT}")
        return 2
    import subprocess
    env = os.environ.copy()
    # Point Open WebUI at the SI instance, not the Oracle.
    env["OLLAMA_BASE_URL"] = f"http://127.0.0.1:{SI_PORT}"
    env["OPEN_WEBUI_PORT"] = str(port)
    print(f"starting Open WebUI on http://127.0.0.1:{port}")
    print(f"SI model is on port {SI_PORT}. The Oracle is separate.")
    try:
        proc = subprocess.Popen(
            ["open-webui", "serve", "--host", "127.0.0.1", "--port", str(port)],
            env=env,
        )
    except Exception as e:
        print(f"could not start Open WebUI: {e}")
        return 1
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    return 0



def send_via_email(cfg, question: str) -> str:
    """Send a signed ask job through the real email transport.

    Reads mailbox and SMTP settings from cfg. The runner must be
    polling that mailbox to pick it up. Returns a short status string.
    """
    secret = cfg.get("shared_secret") or ""
    if not secret:
        return "no shared_secret in config"
    job = build_ask_job(question, secret)
    body = json.dumps(job)
    subject = f"[HOMING-PIGEON] job {job['job_id']}"
    try:
        smtp = R.connect_smtp(cfg)
        try:
            R.send_mail(smtp, cfg, subject, body)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    except Exception as e:
        return f"email send failed: {e}"
    return f"emailed job {job['job_id']}"


def main(cfg, browser=False) -> int:
    R.ensure_inference_ready(cfg)
    R.update_llama_from_config(cfg)
    if not R.inference_config(cfg):
        print("inference is not configured or not loopback. "
              "Set inference.endpoint and inference.model in config.json, "
              "or run the installer without --no-inference.")
        return 2
    if browser:
        return browser_chat(cfg)
    return repl(cfg)


if __name__ == "__main__":
    print("run via: python3 runner/runner.py --config config.json --local-test")
    sys.exit(2)
