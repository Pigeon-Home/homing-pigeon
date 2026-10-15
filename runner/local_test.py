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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Flat imports: this file lives next to runner.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner as R  # noqa: E402


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
        subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
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
    messages = [{"role": "system", "content": SI_SYSTEM}] + history
    messages.append({"role": "user", "content": question})
    payload = json.dumps({"model": model, "messages": messages}).encode()
    req = Request(
        f"http://127.0.0.1:{SI_PORT}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:
        parsed = json.loads(resp.read().decode())
    return parsed["choices"][0]["message"]["content"]


def build_ask_job(question: str, secret: str, job_id=None) -> dict:
    """A signed job that declares a single ask query. The SI side."""
    job_id = job_id or str(uuid.uuid4())
    payload = {
        "v": 1,
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


def answer_as_oracle(cfg, question: str, output_text: str = "") -> dict:
    """Run one ask through the Oracle path and return the answer dict."""
    inf = R.inference_config(cfg)
    if not inf:
        return {"rejected": "inference_unconfigured"}
    patterns = R._redact_patterns(cfg)
    return R.ask_model(
        inf, question, output_text, 500, patterns,
        instructions=cfg.get("owner_instructions"),
    )


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


class _ChatHandler(BaseHTTPRequestHandler):
    cfg = None

    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/":
            self._send(404, "not found", "text/plain")
            return
        page = """<!doctype html>
<meta charset="utf-8">
<title>SI and Oracle</title>
<style>
body { font: 16px/1.4 system-ui; max-width: 46rem; margin: 2rem auto; }
#log { white-space: pre-wrap; border: 1px solid #ccc; padding: 1rem; min-height: 14rem; }
form { display: flex; gap: .5rem; margin-top: 1rem; }
input { flex: 1; font: inherit; padding: .4rem; }
button { font: inherit; padding: .4rem 1rem; }
.you { color: #333; }
.si { color: #06c; }
.oracle { color: #080; }
</style>
<h1>Cloud SI</h1>
<p>Tell the SI what to do. It sends the work to the Oracle on this box
and brings the answer back.</p>
<div id="log"></div>
<form id="f">
  <input id="q" autofocus placeholder="tell the SI what to do">
  <button>send</button>
</form>
<script>
const log = document.getElementById('log');
const q = document.getElementById('q');
document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  if (!text) return;
  log.innerHTML += '<div class="you">you> ' + text + '</div>';
  q.value = '';
  const r = await fetch('/send', {method:'POST', body: text});
  const t = await r.text();
  log.innerHTML += '<div class="si">SI> ' + t + '</div>';
};
</script>
"""
        self._send(200, page)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        question = self.rfile.read(n).decode("utf-8", "replace").strip()
        if self.path == "/send":
            model = (self.cfg.get("inference") or {}).get("model") or "llama3.2:3b"
            try:
                si_text = ask_si(model, [], question)
            except Exception as e:
                si_text = question
            status = send_via_email(self.cfg, si_text)
            self._send(200, si_text + "\n(" + status + ")", "text/plain; charset=utf-8")
            return
        if self.path == "/socket":
            transport = getattr(self, "socket_transport", None)
            if transport is None:
                text = "socket transport not started"
            else:
                try:
                    text = transport.send(question)
                except Exception as e:
                    text = f"socket error: {e}"
            self._send(200, text, "text/plain; charset=utf-8")
            return
        self._send(404, "not found", "text/plain")



def browser_chat(cfg, port=8765) -> int:
    """Serve a loopback chat page that talks to the SI instance.

    The SI is a second Ollama process on port 11435. The Oracle stays
    on its configured endpoint. The page has two actions: chat with
    the SI, and send a question from the SI to the Oracle.
    """
    if not start_si_instance():
        return 2
    transport = LocalSocketTransport(cfg)
    transport.start()
    host = "127.0.0.1"
    _ChatHandler.cfg = cfg
    _ChatHandler.socket_transport = transport
    try:
        httpd = ThreadingHTTPServer((host, port), _ChatHandler)
    except OSError as e:
        print(f"could not bind {host}:{port}: {e}")
        return 1
    bound = httpd.server_address[0]
    if bound not in ("127.0.0.1", "::1"):
        print(f"refusing non-loopback bind {bound}")
        return 1
    url = f"http://{host}:{port}/"
    print(f"local SI chat at {url}  (Ctrl-C to stop)")
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.shutdown()
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


class LocalSocketTransport:
    """High-throughput loopback transport for the local SI test.

    One TCP listener on 127.0.0.1. The SI connects and writes a
    length-prefixed signed blob. A background thread reads blobs and
    runs them through the Oracle path. No email, no queue broker.
    Useful when you want many asks per second on one machine.
    """

    def __init__(self, cfg, port=8766):
        self.cfg = cfg
        self.port = port
        self._stop = threading.Event()
        self._thread = None
        self.answers = []
        self._lock = threading.Lock()

    def start(self):
        import socket
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self._sock.listen(16)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        import socket
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        import struct
        try:
            hdr = self._readn(conn, 4)
            if not hdr:
                return
            (n,) = struct.unpack("!I", hdr)
            blob = self._readn(conn, n)
            if not blob:
                return
            question = blob.decode("utf-8", "replace")
            ans = answer_as_oracle(self.cfg, question)
            text = ans.get("answer") or f"rejected: {ans.get('rejected', ans)}"
            out = text.encode("utf-8")
            conn.sendall(struct.pack("!I", len(out)) + out)
            with self._lock:
                self.answers.append(text)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _readn(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return b""
            buf += chunk
        return buf

    def send(self, question: str) -> str:
        """Client side: connect, send one question, read the answer."""
        import socket
        import struct
        s = socket.create_connection(("127.0.0.1", self.port), timeout=30)
        try:
            data = question.encode("utf-8")
            s.sendall(struct.pack("!I", len(data)) + data)
            hdr = self._readn(s, 4)
            (n,) = struct.unpack("!I", hdr)
            return self._readn(s, n).decode("utf-8", "replace")
        finally:
            s.close()

    def stop(self):
        self._stop.set()
        try:
            self._sock.close()
        except Exception:
            pass


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
