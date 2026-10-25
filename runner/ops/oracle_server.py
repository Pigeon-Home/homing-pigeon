"""Oracle loopback chat server.

Extracted from runner.py. Lazy-imports runner internals to avoid
circular imports.
"""
import json
import sys
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _runner():
    """The live runner module, looked up at call time.

    `runner.runner` when the suite or a package import loaded it,
    `__main__` when runner.py was started as a script (an install,
    the one-file binaries), where `runner` is the file itself and
    `from runner import runner` raises "'runner' is not a package".
    """
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "handle_mail", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R


class _OracleServer(ThreadingHTTPServer):
    allow_reuse_address = False
    request_queue_size = 32
    daemon_threads = True


def make_oracle_server(cfg, host="127.0.0.1", port=11436, base_dir=None):
    """Loopback chat server. Refuses any other bind."""
    R = _runner()
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError("oracle chat refuses a non-loopback bind")
    token = secrets.token_urlsafe(24)
    if not isinstance(cfg, dict):
        cfg = {}
    base = base_dir or R._base_dir_for(cfg)
    progress = {"active": False, "step": "", "started": 0.0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send(self, code, body, content_type):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _take_body(self, limit=8000):
            """Read the POST body before any status is sent.

            On Windows, answering while the body is still unread
            aborts the socket (WinError 10053). The browser then
            sees silence instead of 403. Oversized bodies are
            discarded only up to the cap and reported as None.
            """
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                # Same as the old handler: a garbage length is an
                # empty body, and the ask answers "Ask something
                # first" instead of a bare 400.
                n = 0
            if n < 0:
                self.close_connection = True
                return None
            to_read = n if n <= limit else limit
            got = b""
            while len(got) < to_read:
                chunk = self.rfile.read(to_read - len(got))
                if not chunk:
                    break
                got += chunk
            if n > limit:
                self.close_connection = True
                return None
            return got

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/status":
                if not R._oracle_host_ok(self):
                    self._send(403, "forbidden", "text/plain; charset=utf-8")
                    return
                got = self.headers.get("X-Oracle-Token") or ""
                if not R._oracle_token_ok(got, token):
                    self._send(403, "forbidden", "text/plain; charset=utf-8")
                    return
                elapsed = 0
                if progress.get("active") and progress.get("started"):
                    elapsed = max(0, int(time.time() - progress["started"]))
                self._send(200, json.dumps({
                    "active": bool(progress.get("active")),
                    "step": progress.get("step") or "",
                    "elapsed_sec": elapsed,
                }), "application/json")
                return
            if self.path.split("?", 1)[0] != "/":
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            if not R._oracle_host_ok(self):
                self._send(403, "forbidden", "text/plain; charset=utf-8")
                return
            inf = _runner().inference_config(cfg) or {}
            if R._oracle_mode(cfg) == "deterministic":
                page = R.oracle_page(
                    token, "deterministic (Pi Light), no local model",
                    True)
            else:
                page = R.oracle_page(token, inf.get("model") or "",
                                   bool(inf))
            self._send(200, page, "text/html; charset=utf-8")

        def do_POST(self):
            raw = self._take_body()
            if self.path.split("?", 1)[0] != "/ask":
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            if raw is None:
                self._send(400, "bad request", "text/plain; charset=utf-8")
                return
            # A missing Origin is allowed on loopback: some Windows
            # WebViews and same-origin POSTs omit it, and rejecting
            # them made Send look dead. A present Origin that is not
            # loopback still fails in R._oracle_host_ok.
            if not R._oracle_host_ok(self):
                self._send(403, "forbidden", "text/plain; charset=utf-8")
                return
            got = self.headers.get("X-Oracle-Token") or ""
            if not R._oracle_token_ok(got, token):
                self._send(403, "forbidden", "text/plain; charset=utf-8")
                return
            try:
                body = json.loads(raw.decode("utf-8"))
                question = body.get("question") if isinstance(body, dict) else ""
            except Exception:
                question = ""
            if not isinstance(question, str):
                question = ""
            question = question.strip()[:4000]
            if not question:
                self._send(200, json.dumps({"detail": "Ask something first."}),
                           "application/json")
                return
            inf = _runner().inference_config(cfg)
            progress["active"] = True
            progress["step"] = "Thinking"
            progress["started"] = time.time()
            if R._oracle_mode(cfg) == "deterministic":
                ans = {"answer": R._deterministic_oracle_answer(cfg, base)}
            else:
                try:
                    ans = _runner().ask_model_agent(
                        inf, question, _runner().oracle_context(base, watch=R._oracle_watch_enabled(cfg)),
                        (inf or {}).get("max_answer_chars") or 2000,
                        R._redact_patterns(cfg),
                        instructions=cfg.get("owner_instructions"),
                        base_dir=base,
                        progress=progress,
                    )
                except Exception as e:
                    R.log(f"oracle ask failed: {e}", "WARN")
                    ans = None
            progress["active"] = False
            if not isinstance(ans, dict):
                ans = {"rejected": "inference_error"}
            if isinstance(ans.get("answer"), str) and ans.get("answer"):
                payload = {"answer": ans["answer"][:4000]}
            else:
                why = ans.get("rejected") if isinstance(ans.get("rejected"), str) else ""
                why = why or "inference_error"
                detail = R._ORACLE_REJECTS.get(why, "The Oracle did not answer.")
                if why == "inference_error" and isinstance(ans.get("detail"), str) and ans["detail"]:
                    detail = ans["detail"]
                payload = {"rejected": why, "detail": detail}
            try:
                _runner().record_oracle_turn(base, cfg, question, ans)
            except Exception as e:
                R.log(f"oracle chat log failed: {e}", "WARN")
            try:
                body = json.dumps(payload)
            except (TypeError, ValueError):
                body = json.dumps({"rejected": "inference_error"})
            self._send(200, body, "application/json")

    bind_host = "127.0.0.1" if host == "localhost" else host
    try:
        port_n = int(port)
    except (TypeError, ValueError):
        raise ValueError("oracle chat port must be an integer")

    class _OracleServer(ThreadingHTTPServer):
        # The default backlog is 5. Eight asks at once, which the
        # send-button contract does, fill it. Windows then aborts
        # the extra localhost sockets (WinError 10053) and the
        # page looks dead. 32 covers that burst plus the status poll.
        request_queue_size = 32
        daemon_threads = True

    httpd = _OracleServer((bind_host, port_n), Handler)
    bound = httpd.socket.getsockname()[0]
    if not R._is_loopback_ip(bound):
        httpd.server_close()
        raise ValueError("oracle chat bound a non-loopback address")
    httpd.oracle_token = token
    return httpd

