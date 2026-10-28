"""Time the first ping a new user sends: the README's "under 30 seconds".

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

The README's first prompt asks a cloud SI to email the runner a job
that reads the system clock, and promises the answer in under 30
seconds. That time is the sum of five legs:

    SI send -> runner inbox      the provider's delivery
    inbox   -> runner pickup     0 to poll_interval_sec (default 20)
    pickup  -> result sent       the runner's own work
    result  -> SI inbox          the provider's delivery
    SI inbox -> SI reads it      the SI's own polling

This tool measures the legs it can and keeps every run as data in
docs/reports/first-ping/runs.jsonl, one line per batch, with the
table in README.md beside it rebuilt from that file.

    python3 runner/tools/first_ping.py bench [--runs 50]
        The runner's own leg, on this box, through the real email
        code path (poll_once) with an in-memory mailbox: verify,
        decrypt, run the README's clock job, sign, encrypt, send.
        Needs no account and no network.

    python3 runner/tools/first_ping.py live --runner-email ADDR \\
            --user SI_ADDR --imap-host H --smtp-host H [--runs 5]
        The whole round trip over a real provider, timed from the
        SI's side: the job is built by send_job.py, sent over SMTP
        from the SI's mailbox, and the result is read back over IMAP
        and verified. The SI mailbox password comes from
        $HP_SI_PASSWORD and the shared secret from $HP_SECRET, never
        from argv. A runner must be running against ADDR.

    python3 runner/tools/first_ping.py table
        Rebuild the README table from runs.jsonl.

`--no-record` prints the row without writing it. Stdlib only.
"""
import argparse
import email
import imaplib
import json
import os
import platform
import smtplib
import statistics
import subprocess
import sys
import tempfile
import time
import types
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "reports", "first-ping")
SEND_JOB = os.path.join(REPO, "runner", "cloud", "send_job.py")
STAMP = "60000b3a-32a6-4847-996f-638cbcb6d854"
CLOCK_SCRIPT = "date -u"  # the README's "retrieve the system clock"
POLL_DEFAULT = 20.0  # runner/transport_extensions/email: poll_interval_sec


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _version():
    try:
        sys.path.insert(0, REPO)
        from runner._version import __version__
        return __version__
    except Exception:  # pragma: no cover - a broken tree
        return "unknown"


def summarize(seconds):
    """p50, p95 and max of a list of seconds, rounded to the ms."""
    s = sorted(seconds)
    if not s:
        return {"p50_s": None, "p95_s": None, "max_s": None}
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return {"p50_s": round(statistics.median(s), 3),
            "p95_s": round(p95, 3), "max_s": round(s[-1], 3)}


def record(row, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "runs.jsonl")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"first_ping": 1, "Agent-Stamp": STAMP}) + "\n")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    write_table(out_dir)


def load(out_dir=OUT_DIR):
    path = os.path.join(out_dir, "runs.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    return [r for r in rows if "mode" in r]


def _fmt(v):
    return "" if v is None else f"{v:.3f}"


def write_table(out_dir=OUT_DIR):
    rows = load(out_dir)
    lines = [
        "# First ping",
        "",
        f"<!-- Agent-Stamp: {STAMP} -->",
        "",
        "How long the README's first prompt takes to come back. Every",
        "row is one batch from `runner/tools/first_ping.py`, kept in",
        "[runs.jsonl](runs.jsonl); this table is rebuilt from that file",
        "on every record and is not edited by hand.",
        "",
        "`bench` rows are the runner's own leg on the named box: the",
        "email code path from fetched message to sent result, with an",
        "in-memory mailbox. `live` rows are the whole round trip timed",
        "from the SI's mailbox over the named provider.",
        "",
        "## The budget",
        "",
        "An email round trip is the provider's delivery twice, the wait",
        "for the runner's next poll, the runner's own work, and the SI's",
        "own polling. The poll wait is the large term: 0 to",
        "`poll_interval_sec`, 20 seconds by default, 10 on average. The",
        "runner's work is milliseconds (the `bench` rows), so under the",
        "default the two deliveries and the SI's read share the last 10",
        "seconds in the worst case. A box that must hold the 30 seconds",
        "every time sets `poll_interval_sec` lower.",
        "",
        "## Runs",
        "",
        "| When (UTC) | Mode | Provider | Kind | Runs | OK | p50 s | p95 s | max s | Version | Box |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('when', '')} | {r['mode']} | {r.get('provider', '')} "
            f"| {r.get('kind', '')} | {r.get('runs', '')} | {r.get('ok', '')} "
            f"| {_fmt(r.get('p50_s'))} | {_fmt(r.get('p95_s'))} "
            f"| {_fmt(r.get('max_s'))} | {r.get('version', '')} "
            f"| {r.get('platform', '')} |")
    lines += [
        "",
        "## Adding a row",
        "",
        "```sh",
        "python3 runner/tools/first_ping.py bench --runs 50",
        "HP_SI_PASSWORD=... HP_SECRET=... python3 runner/tools/first_ping.py live \\",
        "    --runner-email runner@example.test --user si@example.test \\",
        "    --imap-host imap.example.test --smtp-host smtp.example.test --runs 5",
        "```",
        "",
    ]
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ------------------------------------------------------------- bench
class _Inbox:
    """One message, served the way imaplib serves it."""

    def __init__(self, raw):
        self.raw = raw

    def login(self, *_):
        return ("OK", [])

    def select(self, *_):
        return ("OK", [])

    def search(self, *_):
        return ("OK", [b"1"])

    def fetch(self, num, _spec):
        head = f"{num.decode()} (RFC822 {{{len(self.raw)}}}".encode()
        return ("OK", [(head, self.raw), b")"])

    def store(self, *_):
        return ("OK", [])

    def logout(self):
        return ("OK", [])


class _Outbox:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


def bench(runs, kinds=("ping", "exec")):
    sys.path.insert(0, REPO)
    sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))
    from runner import runner as runner_mod
    from runner.wire import jobcrypto
    import send_job

    secret = "fp-" + uuid.uuid4().hex + uuid.uuid4().hex
    addr = "runner@example.test"
    rows = []
    quiet = lambda *a, **k: None  # noqa: E731
    quiet.identity_logged = True
    saved = runner_mod.log
    runner_mod.log = quiet
    try:
        for kind in kinds:
            times, ok = [], 0
            for n in range(runs):
                tmp = tempfile.mkdtemp(prefix="hp-first-ping-")
                cfg = {"mailbox_user": addr, "mailbox_password": "unused",
                       "shared_secret": secret, "imap_host": "memory",
                       "imap_port": 993, "smtp_host": "memory",
                       "smtp_port": 587, "max_job_age_sec": 3600,
                       "max_output_bytes": 100000,
                       "default_timeout_sec": 60}
                jid = f"fp-{kind}-{n}-{uuid.uuid4().hex[:8]}"
                payload = {"v": 1, "type": "job", "job_id": jid,
                           "issued_at": _now(), "kind": kind}
                if kind == "exec":
                    payload["script"] = CLOCK_SCRIPT
                signed = send_job.sign_payload(payload, secret)
                wire = jobcrypto.encrypt_body(signed, secret, job_id=jid,
                                              key_id="",
                                              sign=send_job.sign_payload)
                msg = EmailMessage()
                msg["From"] = msg["To"] = addr
                msg["Subject"] = f"[HOMING-PIGEON] job {jid}"
                msg.set_content(wire)
                out = _Outbox()
                t0 = time.perf_counter()
                runner_mod.poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"),
                                     imap=_Inbox(msg.as_bytes()), smtp=out)
                times.append(time.perf_counter() - t0)
                if out.sent and _result_ok(out.sent[0].get_content(), secret,
                                           jid, kind, send_job):
                    ok += 1
            row = {"when": _now(), "mode": "bench", "provider": "in-memory",
                   "transport": "email", "kind": kind, "runs": runs, "ok": ok,
                   "poll_interval_sec": POLL_DEFAULT, "version": _version(),
                   "platform": f"{platform.system()} {platform.machine()} "
                               f"py{platform.python_version()}"}
            row.update(summarize(times))
            rows.append(row)
    finally:
        runner_mod.log = saved
    return rows


def _result_ok(body, secret, jid, kind, send_job):
    try:
        p = send_job._open_body(body, types.SimpleNamespace(
            secret=secret, key_id=None), jid)
    except ValueError:
        return False
    if p.get("job_id") != jid:
        return False
    return kind != "exec" or p.get("exit_code") == 0


# -------------------------------------------------------------- live
def _build_job(kind, secret, reply_to):
    cmd = [sys.executable, SEND_JOB, "new", "--kind", kind,
           "--reply-to", reply_to]
    script = None
    if kind == "exec":
        fd, script = tempfile.mkstemp(suffix=".sh")
        with os.fdopen(fd, "w") as fh:
            fh.write(CLOCK_SCRIPT + "\n")
        cmd += ["--script-file", script]
    env = dict(os.environ, HP_SECRET=secret)
    try:
        out = subprocess.run(cmd + ["--secret", secret], capture_output=True,
                             text=True, env=env, check=True).stdout
    finally:
        if script:
            os.unlink(script)
    subject, _, body = out.replace("\r\n", "\n").partition("\n\n")
    return subject.strip(), body


def _verify(body, secret, jid):
    p = subprocess.run([sys.executable, SEND_JOB, "verify", "--secret", secret,
                        "--job-id", jid], input=body, capture_output=True,
                       text=True)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except ValueError:
        return None


def _wait_result(imap, jid, deadline):
    want = f"result {jid}"
    while time.monotonic() < deadline:
        imap.noop()
        imap.select("INBOX")
        typ, data = imap.search(None, "SUBJECT", f'"{want}"')
        nums = (data[0] or b"").split() if typ == "OK" else []
        if nums:
            typ, msg = imap.fetch(nums[-1], "(RFC822)")
            seen = time.monotonic()
            raw = next(p[1] for p in msg if isinstance(p, tuple))
            return seen, email.message_from_bytes(raw)
        time.sleep(1.0)
    return None, None


def _text_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode("utf-8", "replace")
        return ""
    return msg.get_payload(decode=True).decode("utf-8", "replace")


def live(args):
    password = os.environ.get("HP_SI_PASSWORD")
    secret = os.environ.get("HP_SECRET")
    if not password or not secret:
        print("set HP_SI_PASSWORD and HP_SECRET", file=sys.stderr)
        return None
    times, ok = [], 0
    imap = imaplib.IMAP4_SSL(args.imap_host, args.imap_port)
    imap.login(args.user, password)
    try:
        for _ in range(args.runs):
            subject, body = _build_job(args.kind, secret, args.user)
            jid = subject.split()[-1]
            msg = EmailMessage()
            msg["From"] = args.user
            msg["To"] = args.runner_email
            msg["Subject"] = subject
            msg.set_content(body)
            t0 = time.monotonic()
            with smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=30) as s:
                s.starttls()
                s.login(args.user, password)
                s.send_message(msg)
            seen, reply = _wait_result(imap, jid, t0 + args.timeout)
            if reply is None:
                print(f"{jid}: no result in {args.timeout}s", file=sys.stderr)
                continue
            times.append(seen - t0)
            p = _verify(_text_body(reply), secret, jid)
            if p and (args.kind != "exec" or p.get("exit_code") == 0):
                ok += 1
            print(f"{jid}: {seen - t0:.1f}s", file=sys.stderr)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    row = {"when": _now(), "mode": "live",
           "provider": args.provider or args.imap_host, "transport": "email",
           "kind": args.kind, "runs": args.runs, "ok": ok,
           "poll_interval_sec": args.poll_interval, "version": _version(),
           "platform": args.box or ""}
    row.update(summarize(times))
    return [row]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench", help="the runner's own leg, in memory")
    b.add_argument("--runs", type=int, default=50)
    lv = sub.add_parser("live", help="the whole round trip over a provider")
    lv.add_argument("--runner-email", required=True)
    lv.add_argument("--user", required=True, help="the SI's mailbox")
    lv.add_argument("--imap-host", required=True)
    lv.add_argument("--imap-port", type=int, default=993)
    lv.add_argument("--smtp-host", required=True)
    lv.add_argument("--smtp-port", type=int, default=587)
    lv.add_argument("--kind", choices=("ping", "exec"), default="exec")
    lv.add_argument("--runs", type=int, default=5)
    lv.add_argument("--timeout", type=float, default=120.0)
    lv.add_argument("--poll-interval", type=float, default=POLL_DEFAULT,
                    help="the runner's poll_interval_sec, for the record")
    lv.add_argument("--provider", default="", help="a label for the table")
    lv.add_argument("--box", default="", help="the runner's box, for the table")
    sub.add_parser("table", help="rebuild README.md from runs.jsonl")
    for p in (b, lv):
        p.add_argument("--no-record", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "table":
        write_table()
        return 0
    rows = bench(args.runs) if args.cmd == "bench" else live(args)
    if rows is None:
        return 2
    for row in rows:
        print(json.dumps(row, sort_keys=True))
        if not args.no_record:
            record(row)
    return 0 if all(r["ok"] == r["runs"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
