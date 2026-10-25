#!/usr/bin/env python3
# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Run the runner's poll loop for a long time and fail on growth.

    python3 runner/tools/soak.py --minutes 120
    python3 runner/tools/soak.py --cycles 200 --jobs-per-cycle 4

Every cycle is a real poll_once against an in-memory mailbox that
holds fresh signed jobs (pings and short scripts, so real child
processes start and finish), plus the mail a public inbox gets: a
bad signature, a body that is not a job, a replay of an earlier
job. Nothing is mocked inside the runner.

After each cycle the process is measured: resident memory, open file
descriptors, live threads, child processes, the state folder's size
and file count, and runner.log with its rotations. The first part
of the run is warm-up. After it, the median of the last window is
compared with the median of the first window, and the run fails
when any of these rises past its limit:

    memory    --rss-mb (default 24)
    fds       2
    threads   1
    children  0 (every job's process is reaped)
    results   every fresh job in a cycle gets its result
    log       runner.log and its backups stay within their cap

The state folder grows with retained results by design. Its growth
per job is reported, not judged.

Exit 0 when nothing grew, 1 with each growth named. --json FILE
writes every sample for the run's artifact.
"""
import argparse
import contextlib
import io
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

SENDER = "soak@example.com"
PASSWORD = "soak-mailbox-password"
SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"
LOG_CAP = 64 * 1024
LOG_BACKUPS = 2


class Mailbox:
    """IMAP and SMTP in memory, as runner/tests/test_runner.py fakes them."""

    def __init__(self, mails):
        self.mails = mails
        self.sent = []

    # IMAP
    def login(self, user, password):
        return ("OK", [])

    def select(self, box):
        return ("OK", [])

    def search(self, *args):
        return ("OK", [b" ".join(str(i + 1).encode()
                                 for i in range(len(self.mails)))])

    def fetch(self, num, _spec):
        raw = self.mails[int(num) - 1]
        head = ("%s (RFC822 {%d}" % (num.decode(), len(raw))).encode()
        return ("OK", [(head, raw), b")"])

    def store(self, seq, _op, _flags):
        return ("OK", [])

    def logout(self):
        return ("OK", [])

    # SMTP
    def starttls(self):
        pass

    def send_message(self, msg):
        self.sent.append(len(msg.as_bytes()))

    def quit(self):
        pass


def _mail(payload, secret=SECRET, body=None):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = "[HOMING-PIGEON] job %s" % payload["job_id"]
    if body is None:
        body = jobcrypto.encrypt_body(
            R.sign_payload(payload, secret), secret,
            job_id=payload["job_id"], key_id="", sign=R.sign_payload)
    msg.set_content(body)
    return msg.as_bytes()


def _job(job_id, n):
    p = {"v": 1, "type": "job", "job_id": job_id, "kind": "ping",
         "issued_at": datetime.now(timezone.utc).strftime(
             "%Y-%m-%dT%H:%M:%SZ")}
    if n % 2:
        p.update(kind="exec", script="echo soak-%d" % n)
    return p


def cycle_mail(cycle, jobs, replay):
    mails = []
    for i in range(jobs):
        mails.append(_mail(_job("soak-%d-%d" % (cycle, i), i)))
    mails.append(_mail(_job("soak-badsig-%d" % cycle, 0),
                       secret="f" * 64))
    mails.append(_mail({"job_id": "soak-junk-%d" % cycle},
                       body="not a job at all\n" * 20))
    if replay is not None:
        mails.append(replay)
    return mails


def _fds():
    for path in ("/proc/self/fd", "/dev/fd"):
        try:
            return len(os.listdir(path))
        except OSError:
            continue
    return -1


def _rss_mb():
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1024.0 * 1024.0 if sys.platform == "darwin"
                       else 1024.0)
    except Exception:
        return -1.0


def _children():
    try:
        me = str(os.getpid())
        count = 0
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % pid, encoding="ascii") as fh:
                    fields = fh.read().rsplit(")", 1)[1].split()
            except OSError:
                continue
            if fields[1] == me:
                count += 1
        return count
    except OSError:
        return 0


def _tree(base):
    size = files = 0
    for dirpath, _dirs, names in os.walk(base):
        for name in names:
            try:
                size += os.path.getsize(os.path.join(dirpath, name))
                files += 1
            except OSError:
                pass
    return size, files


def _log_bytes(base):
    total = 0
    for name in os.listdir(base):
        if name.startswith("runner.log"):
            total += os.path.getsize(os.path.join(base, name))
    return total


def sample(base, cycle, jobs_done, t0, sent=0):
    size, files = _tree(base)
    return {"cycle": cycle, "jobs": jobs_done, "sent": sent,
            "elapsed_sec": round(time.monotonic() - t0, 1),
            "rss_mb": round(_rss_mb(), 2), "fds": _fds(),
            "threads": threading.active_count(), "children": _children(),
            "state_bytes": size, "state_files": files,
            "log_bytes": _log_bytes(base)}


def judge(samples, rss_mb=24.0, warmup=0.2, window=0.15, jobs_per_cycle=1):
    """Growth past the limits between the first and last windows."""
    rest = samples[int(len(samples) * warmup):]
    if len(rest) < 4:
        return ["too few cycles to judge (%d after warm-up)" % len(rest)]
    w = max(2, int(len(rest) * window))
    first, last = rest[:w], rest[-w:]

    def med(rows, key):
        return statistics.median(r[key] for r in rows)

    failures = []
    limits = (("rss_mb", rss_mb, "MB of resident memory"),
              ("fds", 2, "open file descriptors"),
              ("threads", 1, "live threads"))
    for key, limit, label in limits:
        grew = med(last, key) - med(first, key)
        if grew > limit:
            failures.append("%s grew by %s (%s -> %s; limit %s)"
                            % (label, round(grew, 2), med(first, key),
                               med(last, key), limit))
    short = [r["cycle"] for r in samples if r["sent"] < jobs_per_cycle]
    if short:
        failures.append("%d cycle(s) sent fewer results than they had "
                        "fresh jobs (first: cycle %d)" % (len(short), short[0]))
    if max(r["children"] for r in last) > 0:
        failures.append("a job's process was not reaped (%d children "
                        "after the cycle)" % max(r["children"] for r in last))
    cap = LOG_CAP * (LOG_BACKUPS + 1) + 4096
    worst = max(r["log_bytes"] for r in samples)
    if worst > cap:
        failures.append("runner.log and backups reached %d bytes (cap %d)"
                        % (worst, cap))
    return failures


def run(minutes=None, cycles=None, jobs_per_cycle=3, base=None):
    """Soak; returns (samples, per-job state growth in bytes)."""
    base = base or tempfile.mkdtemp(prefix="hp-soak-")
    cfg = {"mailbox_user": SENDER, "mailbox_password": PASSWORD,
           "shared_secret": SECRET, "imap_host": "soak", "imap_port": 993,
           "smtp_host": "soak", "smtp_port": 587, "base_dir": base,
           "poll_interval_sec": 1, "max_job_age_sec": 3600,
           "max_output_bytes": 4096, "default_timeout_sec": 30,
           "workers": 1}
    R._LOG_FILE = os.path.join(base, "runner.log")
    R._LOG_MAX_BYTES = LOG_CAP
    R._LOG_BACKUPS = LOG_BACKUPS
    seen_path = os.path.join(base, "seen.json")
    seen = R.load_seen(seen_path)
    samples = []
    t0 = time.monotonic()
    deadline = t0 + minutes * 60 if minutes else None
    replay = None
    jobs_done = 0
    cycle = 0
    while True:
        if cycles is not None and cycle >= cycles:
            break
        if deadline is not None and time.monotonic() >= deadline:
            break
        mails = cycle_mail(cycle, jobs_per_cycle, replay)
        box = Mailbox(mails)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            R.poll_once(cfg, base, seen, seen_path, imap=box, smtp=box)
        replay = mails[0]
        jobs_done += jobs_per_cycle
        cycle += 1
        samples.append(sample(base, cycle, jobs_done, t0, len(box.sent)))
    growth = 0.0
    if len(samples) > 1 and samples[-1]["jobs"] > samples[0]["jobs"]:
        growth = ((samples[-1]["state_bytes"] - samples[0]["state_bytes"])
                  / float(samples[-1]["jobs"] - samples[0]["jobs"]))
    return samples, growth


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--cycles", type=int, default=None)
    ap.add_argument("--jobs-per-cycle", type=int, default=3)
    ap.add_argument("--rss-mb", type=float, default=24.0)
    ap.add_argument("--json", metavar="FILE")
    a = ap.parse_args(argv)
    if a.minutes is None and a.cycles is None:
        a.cycles = 200
    samples, growth = run(a.minutes, a.cycles, a.jobs_per_cycle)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"samples": samples, "state_bytes_per_job": growth},
                      fh, indent=1)
    first, last = samples[0], samples[-1]
    print("soak: %d cycles, %d jobs, %.0fs" % (last["cycle"], last["jobs"],
                                               last["elapsed_sec"]))
    print("  results sent per cycle: %s" % sorted(
        set(r["sent"] for r in samples)))
    for key in ("rss_mb", "fds", "threads", "children", "state_files",
                "log_bytes"):
        print("  %-12s %s -> %s" % (key, first[key], last[key]))
    print("  state grows %.0f bytes per job (retained results; reported, "
          "not judged)" % growth)
    failures = judge(samples, a.rss_mb, jobs_per_cycle=a.jobs_per_cycle)
    for f in failures:
        print("FAIL: " + f)
    print("soak: %s" % ("FAILED" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
