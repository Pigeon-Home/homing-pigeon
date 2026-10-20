#!/usr/bin/env python3
"""Diagnostic harness for a configured homing-pigeon runner.

One command exercises the REAL configured system from outside
(black-box style) and produces a verdict report:

    python3 runner/runner.py --config config.json --diagnose

Start the runner normally first (service or console); --diagnose is a
separate process that probes the same config, mailbox, model, and
state directory the live runner is using. Each section is fault
isolated: a section that raises is recorded as that section's FAIL
and the rest still run. Every network/mail/model call is bounded, so
the gauntlet terminates even when everything it touches is broken.

Sections: banner, config audit, mailbox, model, a signed round-trip
job through the real email transport, an Oracle context audit, the
five Oracle acceptance probes, and a senses snapshot (canary /
registry / event log, reported exactly as the Oracle context reports
them -- unreadable is reported as unreadable, never as clean).

The full report (all evidence, probe transcripts) is written to
harness-report-<UTC timestamp>.txt in the state/base dir. The exit
code is the number of FAIL sections. The shared secret and the
mailbox password are never printed, including in the report file.
"""
import email
import json
import math
import os
import platform
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request

# Works both as a package module (CI) and as a sibling script.
try:
    from runner import runner as R  # package: runner/runner.py
    from runner import local_test as LT
    from runner import jobcrypto as JC
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import runner as R  # script: python3 runner/harness.py
    import local_test as LT
    import jobcrypto as JC


PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"

_ROUNDTRIP_POLL_SEC = 5.0
_MODEL_LIST_TIMEOUT = 30
_MODEL_CHAT_TIMEOUT_CAP = 300

PROBES = (
    "What are you and what is your role here?",
    "What is a job, who sends them, and how do they arrive?",
    "What do you watch on this system?",
    "A script you have never seen arrives from a new sender. What happens?",
    "How do you differ from the cloud SI that sent the job?",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def estimate_entropy_bits(secret) -> float:
    """Rough entropy estimate in bits for a shared secret.

    Delegates to the runner's own estimator (the one the startup
    entropy gate uses) and falls back to the same formula --
    length x log2(distinct characters) -- when it is unavailable.
    """
    fn = getattr(R, "_estimate_secret_entropy", None)
    if callable(fn):
        try:
            return float(fn(secret))
        except Exception:
            pass
    if not isinstance(secret, str) or not secret:
        return 0.0
    alphabet = len(set(secret))
    if alphabet <= 1:
        return 0.0
    return len(secret) * math.log2(alphabet)


class Section:
    """One gauntlet section: a verdict plus the evidence behind it."""

    def __init__(self, name: str):
        self.name = name
        self.status = INFO
        self.summary = ""
        self.evidence = []
        self.elapsed = 0.0

    def note(self, line: str):
        self.evidence.append(line)

    def verdict(self, status: str, summary: str):
        self.status = status
        self.summary = summary


class _ResultInvalid(Exception):
    """A result mail for our job arrived but did not verify."""


# ---------------------------------------------------------------- sections

def _sec_banner(ctx, sec):
    cfg = ctx["cfg"]
    sec.note(f"homing-pigeon {getattr(R, '__version__', 'unknown')}")
    sec.note(f"protocol version: {R.PROTOCOL_VERSION}")
    sec.note(f"config path: {ctx['cfg_path'] or '(not given)'}")
    sec.note(f"state/base dir: {ctx['base_dir']}")
    sec.note(f"runner identity (mailbox_user): "
             f"{cfg.get('mailbox_user') or '(unset)'}")
    sec.note(f"python: {platform.python_version()} "
             f"({sys.platform}, {platform.machine() or 'unknown arch'})")
    sec.verdict(INFO, f"homing-pigeon {getattr(R, '__version__', 'unknown')}, "
                      f"protocol {R.PROTOCOL_VERSION}")


def _sec_config(ctx, sec):
    cfg = ctx["cfg"]
    bad = []
    secret = cfg.get("shared_secret")
    if isinstance(secret, str) and secret:
        bits = estimate_entropy_bits(secret)
        sec.note(f"shared_secret: present, length {len(secret)}, "
                 f"~{bits:.0f} bits estimated entropy "
                 f"(value never printed)")
        try:
            R.validate_shared_secret(secret)
            sec.note("shared_secret: passes the runner's startup "
                     "entropy gate (>= 128 bits, no known pattern)")
        except Exception as e:
            bad.append(f"shared_secret fails the startup entropy gate: {e}")
    else:
        bad.append("shared_secret: MISSING (the runner refuses to "
                   "start without one)")
    for key in ("mailbox_user", "imap_host", "smtp_host"):
        sec.note(f"{key}: {cfg.get(key) or '(unset)'}")
        if not cfg.get(key):
            bad.append(f"{key}: MISSING")
    if str(cfg.get("auth") or "password").lower() == "oauth":
        sec.note("mailbox auth: oauth (no mailbox_password needed)")
    elif cfg.get("mailbox_password"):
        sec.note("mailbox_password: present (value never printed)")
    else:
        bad.append("mailbox_password: MISSING (and auth is not oauth)")
    inf_raw = cfg.get("inference")
    if isinstance(inf_raw, dict) and inf_raw:
        sec.note(f"inference block: endpoint={inf_raw.get('endpoint')!r} "
                 f"model={inf_raw.get('model')!r}")
        inf = R.inference_config(cfg)
        if inf:
            sec.note("inference endpoint: loopback, accepted by "
                     "inference_config")
        else:
            sec.note("inference endpoint: REFUSED by inference_config "
                     "(not loopback, or malformed) -- ask stays off")
    else:
        sec.note("inference block: not configured (ask/Oracle model "
                 "features are off; the runner still runs jobs)")
    ws = cfg.get("workspace_root")
    sec.note(f"workspace_root: {ws if ws else '(not set)'} -- job "
             f"confinement is {'on' if ws else 'off'}")
    sec.note(f"judge mode: {cfg.get('judge') or '(default)'}")
    for line in bad:
        sec.note(line)
    if bad:
        sec.verdict(FAIL, f"config audit: {len(bad)} problem(s), "
                          f"first: {bad[0]}")
    else:
        sec.verdict(PASS, "config complete; secret passes the "
                          "entropy gate")


def _sec_mailbox(ctx, sec):
    cfg = ctx["cfg"]
    imap = R.connect_imap(cfg)
    try:
        typ, listing = imap.list()
        folders = []
        if typ == "OK" and isinstance(listing, (list, tuple)):
            for entry in listing[:25]:
                if isinstance(entry, bytes):
                    entry = entry.decode("utf-8", "replace")
                folders.append(str(entry).rsplit('"/"', 1)[-1]
                               .strip().strip('"'))
        sec.note(f"IMAP {cfg.get('imap_host')}:{cfg.get('imap_port', 993)} "
                 f"connect + login OK as {cfg.get('mailbox_user')}; "
                 f"INBOX selected")
        sec.note(f"folders ({len(folders)}): {', '.join(folders)}")
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    smtp = R.connect_smtp(cfg)
    try:
        sec.note(f"SMTP {cfg.get('smtp_host')}:{cfg.get('smtp_port', 587)} "
                 f"connect + STARTTLS + login OK (nothing sent)")
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    sec.verdict(PASS, "IMAP login + folder list OK; SMTP connect OK")


def _model_names(payload):
    """Model names from an OpenAI /models or Ollama /api/tags reply."""
    names = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    names.append(item["id"])
        models = payload.get("models")
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict) and isinstance(
                        item.get("name"), str):
                    names.append(item["name"])
    return names


def _http_json(req, timeout):
    with R._default_inference_open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _sec_model(ctx, sec):
    cfg = ctx["cfg"]
    inf = R.inference_config(cfg)
    if not inf:
        sec.verdict(FAIL, "inference not configured or endpoint "
                          "not loopback; no model to probe")
        return
    endpoint = inf["endpoint"]
    model = inf["model"]
    timeout = max(10, min(int(inf.get("timeout_sec") or 180),
                          _MODEL_CHAT_TIMEOUT_CAP))
    names = []
    list_err = ""
    urls = [endpoint + "/models"]
    parsed = urlparse(endpoint)
    if parsed.path.rstrip("/").endswith("/v1"):
        urls.append(f"{parsed.scheme}://{parsed.netloc}/api/tags")
    for url in urls:
        try:
            payload = _http_json(Request(url, method="GET"),
                                 min(timeout, _MODEL_LIST_TIMEOUT))
            names = _model_names(payload)
            if names:
                sec.note(f"model list from {url}: {len(names)} model(s): "
                         + ", ".join(names[:10]))
                break
            list_err = f"{url}: reply carried no model names"
        except Exception as e:
            list_err = f"{url}: {type(e).__name__}: {e}"
    if not names:
        sec.verdict(FAIL, f"could not list models at {endpoint} "
                          f"({list_err})")
        return
    present = model in names or any(
        n == model or n.startswith(model + ":") for n in names)
    sec.note(f"configured model {model!r}: "
             f"{'present' if present else 'NOT in the model list'}")
    if not present:
        sec.verdict(FAIL, f"configured model {model} is not served "
                          f"by {endpoint}")
        return
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user",
                      "content": "Reply with the single word: pong"}],
        "max_tokens": 8,
        "stream": False,
    }).encode()
    req = Request(endpoint + "/chat/completions", data=body,
                  headers={"Content-Type": "application/json"},
                  method="POST")
    t0 = time.monotonic()
    payload = _http_json(req, timeout)
    cold = time.monotonic() - t0
    content = ""
    try:
        content = payload["choices"][0]["message"]["content"] or ""
    except Exception:
        content = ""
    sec.note(f"chat completion in {cold:.1f}s (timeout {timeout}s): "
             f"{content.strip()[:120]!r}")
    if not content.strip():
        sec.verdict(FAIL, f"model {model} answered with empty content "
                          f"in {cold:.1f}s")
        return
    sec.verdict(PASS, f"{model} answered in {cold:.1f}s")


def _find_result(conn, secret, job_id):
    """Verified result payload from one IMAP connection, or None.

    Raises _ResultInvalid when a result mail for job_id is present
    but its signature does not verify.
    """
    typ, data = conn.search(None, "SUBJECT", f'"{job_id}"')
    if typ != "OK" or not data:
        return None
    blob = data[0]
    if isinstance(blob, str):
        blob = blob.encode("ascii", "replace")
    if not isinstance(blob, (bytes, bytearray)):
        return None
    for num in blob.split():
        typ, fetched = conn.fetch(num, "(BODY.PEEK[])")
        if typ != "OK" or not fetched:
            continue
        raw = None
        for part in fetched:
            if isinstance(part, tuple) and len(part) == 2 \
                    and isinstance(part[1], bytes):
                raw = part[1]
                break
        if raw is None:
            continue
        try:
            msg = email.message_from_bytes(raw)
        except Exception:
            continue
        subject = str(msg.get("Subject") or "")
        if "result" not in subject or job_id not in subject:
            continue
        try:
            payload = R.verify_body(R.get_text_body(msg), secret)
            if JC.is_envelope(payload):
                # The result mirrors the (encrypted) job: verify
                # the envelope -- just done -- then decrypt and
                # verify the recovered signed body, exactly as
                # send_job.py's verify does.
                inner = JC.decrypt_body(
                    payload, secret, job_id,
                    payload.get("key_id") or "")
                payload = R.verify_body(inner, secret)
            return payload
        except Exception as e:
            raise _ResultInvalid(f"result mail for job {job_id} "
                                 f"failed verification: {e}")
    return None


def _poll_for_result(cfg, secret, job_id, timeout):
    """Poll the mailbox for the round-trip result. Bounded.

    Returns the verified payload, or None on timeout. Raises
    _ResultInvalid for a present-but-unverifiable result.
    """
    deadline = time.monotonic() + timeout
    conn = None
    try:
        while True:
            try:
                if conn is None:
                    conn = R.connect_imap(cfg)
                found = _find_result(conn, secret, job_id)
                if found is not None:
                    return found
            except _ResultInvalid:
                raise
            except Exception:
                conn = None  # drop and reconnect next round
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(_ROUNDTRIP_POLL_SEC, remaining))
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass


def _sec_roundtrip(ctx, sec):
    cfg = ctx["cfg"]
    secret = cfg.get("shared_secret") or ""
    if not secret:
        sec.verdict(FAIL, "no shared_secret in config; cannot sign "
                          "the round-trip job")
        return
    timeout = ctx["roundtrip_timeout"]
    nonce = uuid.uuid4().hex[:12]
    job_id = str(uuid.uuid4())
    # The run-a-script kind is "exec". The interpreter is omitted on
    # purpose: the runner uses its platform default (PowerShell on
    # Windows, sh elsewhere), and `echo` works under both.
    payload = {
        "v": R.PROTOCOL_VERSION,
        "type": "job",
        "job_id": job_id,
        "issued_at": _now(),
        "kind": "exec",
        "script": f"echo {nonce}",
        "timeout_sec": 60,
    }
    body = R.sign_payload(payload, secret)
    # The round-trip job travels encrypted, like every job the
    # shipped senders build: the HMAC-only form is no longer
    # supported, and the runner would refuse the plain body.
    body = JC.encrypt_body(body, secret, job_id=job_id, key_id="",
                           sign=R.sign_payload)
    subject = f"[HOMING-PIGEON] job {job_id}"
    t0 = time.monotonic()
    smtp = R.connect_smtp(cfg)
    try:
        R.send_mail(smtp, cfg, subject, body)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    sec.note(f"sent signed exec job {job_id} (echo <nonce>) to "
             f"{cfg.get('mailbox_user')}; waiting up to {timeout}s "
             f"for the result")
    try:
        result = _poll_for_result(cfg, secret, job_id, timeout)
    except _ResultInvalid as e:
        sec.verdict(FAIL, str(e))
        return
    waited = time.monotonic() - t0
    if result is None:
        sec.note(f"no result for job {job_id} after {timeout}s. The "
                 f"job mail was delivered to the runner's mailbox, so "
                 f"the runner may not be polling (not running, wrong "
                 f"mailbox, or stuck) -- check the runner process and "
                 f"its log.")
        sec.verdict(FAIL, f"no result within {timeout}s; runner may "
                          f"not be polling")
        return
    sec.note(f"result received after {waited:.1f}s end to end; "
             f"signature verified")
    sec.note(f"result: exit_code={result.get('exit_code')} "
             f"timed_out={result.get('timed_out')} "
             f"kind={result.get('kind')!r} runner="
             f"{result.get('runner')!r}")
    stdout = result.get("stdout") or ""
    sec.note(f"result stdout: {stdout.strip()[:200]!r}")
    ok = result.get("exit_code") == 0 and not result.get("timed_out") \
        and nonce in stdout
    if not ok:
        sec.verdict(FAIL, "result verified but wrong: exit_code="
                          f"{result.get('exit_code')}, nonce "
                          f"{'echoed' if nonce in stdout else 'NOT echoed'}")
        return
    sec.verdict(PASS, f"signed job executed and result verified in "
                      f"{waited:.1f}s")


def _sec_context(ctx, sec):
    cfg = ctx["cfg"]
    base_dir = ctx["base_dir"]
    watch_fn = getattr(R, "_oracle_watch_enabled", None)
    watch = bool(watch_fn(cfg)) if callable(watch_fn) else True
    text = R.oracle_context(base_dir, watch=watch)
    ctx["context"] = text
    sec.note(f"oracle_context: {len(text)} chars "
             f"(watch={'on' if watch else 'off'})")
    headers = []
    for segment in text.split("\n---\n"):
        first = segment.strip().splitlines()
        if first:
            headers.append(first[0].strip()[:90])
    sec.note("sections present: " + " | ".join(headers))
    retained = 0
    rdir = os.path.join(base_dir, "retained")
    try:
        if os.path.isdir(rdir):
            retained = sum(1 for n in os.listdir(rdir)
                           if n.endswith(".json"))
    except OSError:
        retained = 0
    ctx["retained_count"] = retained
    index_lines = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("Job index"):
            for follow in lines[i + 1:]:
                if not follow.strip():
                    break
                index_lines.append(follow)
            break
    if index_lines:
        sec.note("job index (verbatim):")
        for ln in index_lines:
            sec.note(f"  {ln}")
    else:
        sec.note("job index: absent")
    if retained > 0 and index_lines:
        sec.verdict(PASS, f"context built; job index lists "
                          f"{len(index_lines)} job(s)")
    elif retained > 0:
        sec.verdict(FAIL, f"{retained} retained job(s) on disk but "
                          f"the context has no job index")
    else:
        sec.verdict(INFO, "no retained jobs yet; index absent "
                          "as expected")


def _sec_probes(ctx, sec):
    cfg = ctx["cfg"]
    failed = 0
    for i, question in enumerate(PROBES, 1):
        t0 = time.monotonic()
        ans = LT.answer_as_oracle(cfg, question)
        dt = time.monotonic() - t0
        sec.note(f"Q{i}: {question}")
        if isinstance(ans, dict) and isinstance(ans.get("answer"), str) \
                and ans["answer"].strip():
            sec.note(f"A{i} ({dt:.1f}s): {ans['answer']}")
        else:
            why = ans.get("rejected") if isinstance(ans, dict) else ans
            sec.note(f"A{i} ({dt:.1f}s): NO ANSWER "
                     f"(rejected: {why})")
            failed += 1
    if failed:
        sec.verdict(FAIL, f"{failed} of {len(PROBES)} probes came "
                          f"back empty or rejected")
    else:
        sec.verdict(PASS, f"all {len(PROBES)} probes answered")


def _sec_senses(ctx, sec):
    base_dir = ctx["base_dir"]
    problems = []
    canary = R._canary_watch(base_dir)
    if canary:
        for ln in canary.splitlines():
            sec.note(f"canary: {ln}")
        if "TRIPPED" in canary:
            sec.note("canary: a tripwire has TRIPPED (see lines above)")
    else:
        problems.append("canary watch produced nothing "
                        "(base dir unusable)")
        sec.note("canary: UNAVAILABLE (no usable base dir)")
    if sys.platform == "win32":
        ev = R._eventlog_tail(base_dir=base_dir)
        if ev is None:
            problems.append("Windows Event Log unreadable")
            sec.note("event log: UNREADABLE by the runner "
                     "(not reported as clean)")
        elif ev:
            sec.note("event log: readable; recent entries:")
            for ln in ev.splitlines():
                sec.note(f"  {ln}")
        else:
            sec.note("event log: readable; no Critical/Error/Warning "
                     "or audit failures in the recent window")
        reg = R._registry_watch(base_dir)
        if reg is None:
            problems.append("registry watch unreadable")
            sec.note("registry watch: UNREADABLE by the runner "
                     "(not reported as clean)")
        elif reg:
            sec.note("registry watch: readable; diff vs last look:")
            for ln in reg.splitlines():
                sec.note(f"  {ln}")
        else:
            sec.note("registry watch: readable; no changes vs "
                     "the last look")
    else:
        sec.note(f"event log / registry watch: Windows-only senses, "
                 f"not applicable on {sys.platform}; the context "
                 f"uses the host log tail here")
        host = R._host_log_tail(base_dir=base_dir)
        if host is None:
            problems.append("host log tail unreadable")
            sec.note("host log tail: UNREADABLE by the runner "
                     "(not reported as clean)")
        elif host:
            sec.note("host log tail: readable; matching lines:")
            for ln in host.splitlines():
                sec.note(f"  {ln}")
        else:
            sec.note("host log tail: readable; no matching auth "
                     "failures or error lines in the recent window")
    if problems:
        sec.verdict(FAIL, "; ".join(problems))
    else:
        sec.verdict(PASS, "senses readable and reported as the "
                          "context reports them")


_SECTIONS = (
    ("banner", _sec_banner),
    ("config", _sec_config),
    ("mailbox", _sec_mailbox),
    ("model", _sec_model),
    ("round-trip", _sec_roundtrip),
    ("oracle-context", _sec_context),
    ("oracle-probes", _sec_probes),
    ("senses", _sec_senses),
)


def _run_section(name, fn, ctx, out):
    """Run one section, fault-isolated, and stream its verdict line."""
    sec = Section(name)
    t0 = time.monotonic()
    try:
        fn(ctx, sec)
    except Exception as e:
        sec.status = FAIL
        sec.summary = f"section raised {type(e).__name__}: {e}"
        sec.note(f"section raised: {type(e).__name__}: {e}")
    sec.elapsed = time.monotonic() - t0
    if not sec.summary:
        sec.summary = sec.evidence[0] if sec.evidence else "done"
    out(f"[{sec.status}] {name} — {sec.summary} ({sec.elapsed:.1f}s)")
    return sec


def run_diagnose(cfg, out=print, base_dir=None, cfg_path=None,
                 roundtrip_timeout=120, sections=None) -> int:
    """Run the diagnostic gauntlet against a loaded config.

    Streams one verdict line per section to `out`, writes the full
    report into the base/state dir, and returns the number of FAIL
    sections (the process exit code).
    """
    if not isinstance(cfg, dict):
        cfg = {}
    if base_dir is None:
        base_dir = R._base_dir_for(cfg, cfg_path)  # pyrefly: ignore[missing-attribute]  # package __init__ does not re-export the private helper
    try:
        timeout = int(roundtrip_timeout)
    except (TypeError, ValueError, OverflowError):
        timeout = 120
    if timeout < 1:
        timeout = 120
    ctx = {
        "cfg": cfg,
        "base_dir": base_dir,
        "cfg_path": cfg_path,
        "roundtrip_timeout": timeout,
        "context": None,
        "retained_count": 0,
    }
    plan = list(sections) if sections is not None else list(_SECTIONS)
    done = []
    for name, fn in plan:
        done.append(_run_section(name, fn, ctx, out))
    fails = sum(1 for s in done if s.status == FAIL)
    passes = sum(1 for s in done if s.status == PASS)
    infos = sum(1 for s in done if s.status == INFO)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = [
        f"homing-pigeon diagnose report — {stamp} UTC",
        f"version {getattr(R, '__version__', 'unknown')}, "
        f"protocol {R.PROTOCOL_VERSION}, config "  # pyrefly: ignore[missing-attribute]  # not re-exported by the package __init__
        f"{cfg_path or '(not given)'}",
        "",
    ]
    for s in done:
        report.append(f"== {s.name} — {s.status} ({s.elapsed:.1f}s)")
        report.extend(s.evidence)
        report.append("")
    report.append(f"result: {fails} failed, {passes} passed, "
                  f"{infos} info, {len(done)} sections")
    path = os.path.join(base_dir, f"harness-report-{stamp}.txt")
    try:
        os.makedirs(base_dir, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        body = ("\n".join(report) + "\n").encode("utf-8")
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, body)
        finally:
            os.close(fd)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        out(f"report written to {path}")
    except Exception as e:
        out(f"could not write report file ({e}); full report follows:")
        for line in report:
            out(line)
    out(f"diagnose: {fails} section(s) failed, {passes} passed")
    return fails


def main(cfg, base_dir, cfg_path=None, roundtrip_timeout=None) -> int:
    """Entry point for `runner.py --diagnose`."""
    return run_diagnose(
        cfg, out=print, base_dir=base_dir, cfg_path=cfg_path,
        roundtrip_timeout=120 if roundtrip_timeout is None
        else roundtrip_timeout)


if __name__ == "__main__":
    print("run via: python3 runner/runner.py --config config.json "
          "--diagnose")
    sys.exit(2)
