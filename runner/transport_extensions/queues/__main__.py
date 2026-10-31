# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The queues transport extension: a tenant's HTTP queue is the pipe.

Config (transport_queues block, handed over by the runner):
    url         the tenant's queue base, e.g.
                https://hp.example.workers.dev/t/alice
    token_env   name of the environment variable holding the
                runner token (preferred); `token` is accepted
                but lands in config.json, so avoid it
    max_jobs    jobs pulled per pass (default 8)
How long a pulled job stays leased before the queue may offer it
again is the Worker's setting (LEASE_MS, default 300 s), not this
block's.

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

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402
from runner.wire import subject as _subject  # noqa: E402

MAX_BYTES = ch.FILE_MAX_BYTES
_JOB_ID_RE = _subject.JOB_ID_RE        # the one grammar (Q121)
_RESULT_ID_RE = _subject.RESULT_ID_RE
# The writer names the first result "<id>.result.txt" and, while that
# file is still in the outbox, the next one "<id>.result-<n>.txt".
_RESULT_FILE_RE = re.compile(r"^(.+)\.result(?:-\d+)?\.txt$")


def _job_id(subject):
    m = _JOB_ID_RE.search(subject or "")
    return m.group(1) if m else None


def _result_id(subject):
    m = _RESULT_ID_RE.search(subject or "")
    return m.group(1) if m else None


def _result_file_id(fname):
    """The job a result file is named for. A collision name still
    names that job; the whole filename does not."""
    m = _RESULT_FILE_RE.match(fname or "")
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
        self._attempt = {}
        self._hand = {}

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
                attempt = item.get("attempt")
                if isinstance(attempt, int) and not isinstance(attempt, bool):
                    self._attempt[ident] = attempt
                hand = item.get("hand")
                if isinstance(hand, int) and not isinstance(hand, bool):
                    self._hand[ident] = hand
                out.append((ident, env))
        return out

    def _receipt(self, ident):
        """The pull this process was given, so a later pull's job is
        not acked or renewed. A worker that did not send a hand is
        the old call."""
        parts = []
        attempt = self._attempt.get(ident)
        hand = self._hand.get(ident)
        if isinstance(attempt, int) and not isinstance(attempt, bool):
            parts.append(f"attempt={attempt}")
        if isinstance(hand, int) and not isinstance(hand, bool):
            parts.append(f"hand={hand}")
        return ("?" + "&".join(parts)) if parts else ""

    def ack(self, ident):
        status, _ = self._request("POST", f"/jobs/{ident}/ack{self._receipt(ident)}")
        return status in (200, 204, 404)

    def renew(self, ident):
        """Renew the lease on a job this runner is still running. True
        when the queue renewed it; False when it no longer holds the
        job under a lease (acked, the lease lapsed, or a later pull
        took it). The attempt and the hand from the pull are sent
        when we have them, so a renew cannot extend a hand that
        moved on."""
        path = f"/jobs/{urllib.parse.quote(ident, safe='')}/lease{self._receipt(ident)}"
        status, _ = self._request("POST", path)
        return status in (200, 204)

    def post_result(self, envelope_text):
        status, payload = self._request(
            "POST", "/results", envelope_text.encode("utf-8"),
            "text/plain; charset=utf-8")
        if status == 202:
            return True
        if status == 200:
            # A retry of the bytes already stored may finish the job.
            # A different result for that id was not stored, and
            # finishing the job here would throw the new output away.
            # A 200 that names no hash is the old answer: treat it as
            # the same bytes, so a worker from before this field still
            # completes a retry.
            digest = None
            try:
                data = json.loads(payload.decode("utf-8"))
                if isinstance(data, dict) and isinstance(data.get("sha256"), str):
                    digest = data["sha256"]
            except (ValueError, UnicodeDecodeError):
                digest = None
            if digest is not None:
                got = hashlib.sha256(envelope_text.encode("utf-8")).hexdigest()
                if digest != got:
                    raise RuntimeError(
                        "post result: the queue kept a different envelope")
            return True
        raise RuntimeError(f"post result: HTTP {status}: "
                           f"{payload[:120]!r}")


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
        # Ids this process has delivered. A result for one of them is
        # still acked if it is no longer in _pending. It does not mean
        # "drop the next offer": a requeue, or the same id sent again
        # after an ack, is a new life. Dropping it here would still
        # lease it on every pull until it dead-letters, and the runner
        # would never see it.
        self._seen = set()

    def _refuse(self, ident, why):
        ch.log(f"queues transport: {ident}: refused: {why}", "WARN")
        # A malformed envelope will never verify; take it off the
        # queue so it does not come back every lease.
        self.client.ack(ident)

    def renew_leases(self):
        """A job still running keeps its lease, so a build longer than
        the lease is neither offered again nor dead-lettered."""
        for ident in list(self._pending):
            try:
                if not self.client.renew(ident):
                    ch.log(f"queues transport: {ident}: lease not renewed "
                           f"(the queue no longer holds it leased)", "WARN")
            except (RuntimeError, OSError) as e:
                ch.log(f"queues transport: {ident}: lease renewal failed: "
                       f"{e}", "WARN")

    def pull_jobs(self):
        for ident, text in self.client.pull(self.max_jobs):
            # Still in the inbox. pull() already stored the attempt
            # this lease handed out, so the next renew matches it.
            # A second file would clobber the one the core is reading.
            if ident in self._pending:
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
            path = ch.deliver_job(self.channel, ident, subject, body)
            # The previous life of this id left inbox/done/<id>.job.txt,
            # and that file means "this life finished, ack it". This
            # offer is not that life. Clear the marker before anything
            # acks, or the new job is dropped without running.
            done = os.path.join(os.path.dirname(path), "done",
                                os.path.basename(path))
            try:
                os.remove(done)
            except FileNotFoundError:
                pass
            self._pending[ident] = _job_id(subject)
            self._seen.add(ident)

    def push_results(self):
        unposted = set()
        # "<id>.result-2.txt" sorts before "<id>.result.txt". The
        # worker keeps the first envelope posted for an id, so the
        # name the writer used first has to be posted first.
        waiting = ch.pending_results(self.channel)
        waiting.sort(key=lambda row: (not row[0].endswith(".result.txt"), row[0]))
        for fname, subject, body in waiting:
            file_id = _result_file_id(fname)
            subject_id = _result_id(subject)
            if file_id and subject_id and file_id != subject_id:
                # The worker would file this under the subject and an
                # ack of the filename would finish a different job.
                ch.log(f"queues transport: result {fname} names {subject_id}, "
                       f"not {file_id}; left for a person", "WARN")
                unposted.add(file_id)
                continue
            ident = file_id or subject_id or fname
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
               "token, or token_env to the name of a variable that holds "
               "it", "ERROR")
        return 2
    client = QueueClient(url, token, opener=opener)
    pipe = QueuePipe(cfg, channel_dir, client)
    ch.log(f"queues transport: pulling from {url}")
    interval = ch.poll_interval(cfg)
    done = 0
    while passes is None or done < passes:
        try:
            pipe.renew_leases()
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
