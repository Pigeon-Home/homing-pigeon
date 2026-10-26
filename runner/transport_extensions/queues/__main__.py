# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The queues transport extension: a tenant's HTTP queue is the pipe.

Config (transport_queues block, handed over by the runner):
    url         the tenant's queue base, e.g.
                https://hp.example.workers.dev/t/alice
    token_env   name of the environment variable holding the
                runner token (preferred); `token` is accepted
                but lands in config.json, so avoid it
    lease_sec   how long a pulled job stays leased to this
                runner before the queue may offer it again
                (default 300)
    max_jobs    jobs pulled per pass (default 8)

The contract (docs/extend/transports.md, "Queues"):
    GET  {url}/jobs?max=N          -> {"jobs": [{"id", "envelope"}]}
    POST {url}/jobs/{id}/ack       -> 204   (the job is finished)
    POST {url}/results             <- envelope text, 202
Every call carries `Authorization: Bearer <runner token>`. The
envelope is the file transport's shape: a subject line, a blank
line, the signed body. The Worker verified the HMAC at the edge;
the runner verifies it again before anything runs, as always.

Outbound only: the runner polls, nothing listens. A job is acked
only after its result has been posted (or the core consumed it
without a result, a rejection), so a crash between pull and run
leaves the job on the queue for the next lease.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402

MAX_BYTES = ch.FILE_MAX_BYTES
_JOB_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)
_RESULT_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+(?:result|qresult)\s+(\S+)", re.I)


def _job_id(subject):
    m = _JOB_ID_RE.search(subject or "")
    return m.group(1) if m else None


def _result_id(subject):
    m = _RESULT_ID_RE.search(subject or "")
    return m.group(1) if m else None


def _int(value, default, lo=1, hi=None):
    """Decision 1: an unusable value reads as the default."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if n < lo or (hi is not None and n > hi):
        return default
    return n


class QueueClient:
    """The three calls, over urllib. `opener` is injectable."""

    def __init__(self, url, token, opener=None, timeout=20):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def _request(self, method, path, body=None, content_type=None):
        req = urllib.request.Request(
            self.url + path, data=body, method=method,
            headers={"Authorization": f"Bearer {self.token}",
                     "Accept": "application/json",
                     "User-Agent": "homing-pigeon-queues/1.0"})
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with self._open(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            try:
                payload = e.read()
            except Exception:
                payload = b""
            return e.code, payload

    def pull(self, max_jobs):
        status, payload = self._request("GET", f"/jobs?max={int(max_jobs)}")
        if status == 204:
            return []
        if status != 200:
            raise RuntimeError(f"pull: HTTP {status}: "
                               f"{payload[:120]!r}")
        try:
            data = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise RuntimeError("pull: response is not JSON")
        jobs = data.get("jobs") if isinstance(data, dict) else None
        out = []
        for item in jobs or []:
            if not isinstance(item, dict):
                continue
            ident = item.get("id")
            env = item.get("envelope")
            if isinstance(ident, str) and ident and isinstance(env, str):
                out.append((ident, env))
        return out

    def ack(self, ident):
        status, _ = self._request("POST", f"/jobs/{ident}/ack")
        return status in (200, 204, 404)

    def post_result(self, envelope_text):
        status, payload = self._request(
            "POST", "/results", envelope_text.encode("utf-8"),
            "text/plain; charset=utf-8")
        if status not in (200, 202):
            raise RuntimeError(f"post result: HTTP {status}: "
                               f"{payload[:120]!r}")
        return True


def resolve_token(cfg, environ=None):
    environ = os.environ if environ is None else environ
    name = cfg.get("token_env")
    if isinstance(name, str) and name.strip():
        tok = environ.get(name.strip())
        if tok:
            return tok
    tok = cfg.get("token")
    if isinstance(tok, str) and tok:
        return tok
    return None


class QueuePipe:
    """One pass = pull new jobs into the channel inbox, post the
    channel's results back and ack their jobs."""

    def __init__(self, cfg, channel_dir, client):
        self.channel = channel_dir
        self.client = client
        self.max_jobs = _int(cfg.get("max_jobs"), 8, lo=1, hi=100)
        self._pending = {}  # queue id -> job_id (or None)
        self._seen = set()  # queue ids delivered this process

    def _refuse(self, ident, why):
        ch.log(f"queues transport: {ident}: refused: {why}", "WARN")
        # A malformed envelope will never verify; take it off the
        # queue so it does not come back every lease.
        self.client.ack(ident)

    def pull_jobs(self):
        for ident, text in self.client.pull(self.max_jobs):
            if ident in self._pending or ident in self._seen:
                continue
            if len(text.encode("utf-8")) > MAX_BYTES:
                self._refuse(ident, f"exceeds the {MAX_BYTES}-byte cap")
                continue
            parsed = ch.parse_envelope(text)
            if parsed is None:
                self._refuse(ident, "malformed envelope (no blank line "
                                    "between subject and body)")
                continue
            subject, body = parsed
            ch.deliver_job(self.channel, ident, subject, body)
            self._pending[ident] = _job_id(subject)
            self._seen.add(ident)

    def push_results(self):
        unposted = set()
        for fname, subject, body in ch.pending_results(self.channel):
            ident = fname[:-len(".result.txt")] \
                if fname.endswith(".result.txt") else fname
            text = ch.envelope(subject, body)
            if body and not body.endswith("\n"):
                text += "\n"
            try:
                self.client.post_result(text)
            except RuntimeError as e:
                ch.log(f"queues transport: result {ident} not posted: {e}; "
                       f"will retry", "WARN")
                unposted.add(ident)
                continue
            ch.ack_result(self.channel, fname)
            if self._pending.pop(ident, None) is not None or \
                    ident in self._seen:
                self.client.ack(ident)
        # A job the core consumed without a result (a rejection)
        # is finished too: inbox/done is the signal.
        # A result still waiting to be posted keeps its job leased.
        chan_done = os.path.join(self.channel, "inbox", "done")
        for ident in list(self._pending):
            if ident in unposted:
                continue
            if os.path.exists(os.path.join(chan_done, ident + ".job.txt")):
                del self._pending[ident]
                self.client.ack(ident)


def main(argv=None, opener=None, passes=None):
    argv = list(sys.argv if argv is None else argv)
    channel_dir, cfg = ch.load_runtime_config(argv)
    if not channel_dir:
        ch.log("queues transport: no channel directory given", "ERROR")
        return 2
    url = cfg.get("url")
    if not isinstance(url, str) or not url.startswith("https://") \
            and not url.startswith("http://127.0.0.1") \
            and not url.startswith("http://localhost"):
        ch.log("queues transport: transport_queues.url must be an https "
               "URL (loopback http is allowed for tests)", "ERROR")
        return 2
    token = resolve_token(cfg)
    if not token:
        ch.log("queues transport: no runner token: set transport_queues."
               "token_env to the name of the variable holding it", "ERROR")
        return 2
    client = QueueClient(url, token, opener=opener)
    pipe = QueuePipe(cfg, channel_dir, client)
    ch.log(f"queues transport: pulling from {url}")
    interval = ch.poll_interval(cfg)
    done = 0
    while passes is None or done < passes:
        try:
            pipe.pull_jobs()
            pipe.push_results()
        except Exception as e:  # the pipe must not die on one pass
            ch.log(f"queues transport: pass failed: {e!r}", "ERROR")
        done += 1
        if passes is None or done < passes:
            ch.nap(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
