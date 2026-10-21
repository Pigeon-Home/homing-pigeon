"""The file transport extension: a watched folder is the pipe.

Config (transport_file block, handed over by the runner):
    inbox_dir   directory job envelope files arrive in
                (relative values resolve against the runner
                base dir); `inbox` is accepted too
    outbox_dir  directory result envelopes are written to;
                `outbox` is accepted too

A job file is the send_job envelope as text (subject line,
blank line, signed body); `cloud/send_job.py new --to-file`
writes exactly that. Each job is processed once: after the
runner's result comes back through the channel, the job file
moves to <inbox>/done/ and the result envelope lands in the
outbox as <job_id>.result.txt. A redelivered duplicate (same
job_id, already in done/) is acked without a second execution:
the transport deduplicates, the runner never sees a job
twice. The first authorization gate on this pipe is the inbox
directory's OS access control: whoever can write there can
offer jobs. The HMAC signature stays the runner's gate.

A job file that is a symlink, oversize, or malformed is
refused with the reason left in <inbox>/done/<name>.refused.txt
-- never silently dropped, never executed.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402

MAX_BYTES = ch.FILE_MAX_BYTES
_JOB_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)


def _job_id(subject):
    m = _JOB_ID_RE.search(subject or "")
    return m.group(1) if m else None


def _safe(name):
    return "".join(c if (c.isalnum() or c in "._-") else "_"
                   for c in name)


class FilePipe:
    """One pass = scan the watched inbox, deliver new jobs to
    the channel, route channel results to the watched outbox."""

    def __init__(self, cfg, channel_dir):
        base = cfg.get("base_dir") or os.getcwd()
        inbox = cfg.get("inbox") or cfg.get("inbox_dir") \
            or "transport-file/inbox"
        outbox = cfg.get("outbox") or cfg.get("outbox_dir") \
            or "transport-file/outbox"
        if not os.path.isabs(inbox):
            inbox = os.path.join(base, inbox)
        if not os.path.isabs(outbox):
            outbox = os.path.join(base, outbox)
        self.inbox = inbox
        self.outbox = outbox
        self.done = os.path.join(inbox, "done")
        for path in (inbox, outbox, self.done):
            os.makedirs(path, exist_ok=True)
        self.channel = channel_dir
        self._pending = {}  # channel ident -> (watched fname, jid)

    def _refuse(self, fname, why):
        ch.log(f"file transport: {fname}: refused: {why}", "WARN")
        src = os.path.join(self.inbox, fname)
        try:
            os.replace(src, os.path.join(self.done, fname))
        except OSError as e:
            ch.log(f"file transport: cannot move {fname} to "
                   f"done: {e}", "WARN")
            return
        try:
            with open(os.path.join(
                    self.done, fname + ".refused.txt"),
                    "w", encoding="utf-8") as f:
                f.write(f"{fname}: refused: {why}\n")
        except OSError:
            pass

    def scan_jobs(self):
        for fname in sorted(os.listdir(self.inbox)):
            if fname == "done":
                continue
            path = os.path.join(self.inbox, fname)
            if os.path.isdir(path) and not os.path.islink(path):
                continue
            if os.path.islink(path):
                self._refuse(fname, "symlink job files are not read")
                continue
            try:
                size = os.path.getsize(path)
            except OSError as e:
                self._refuse(fname, f"cannot stat: {e}")
                continue
            if size > MAX_BYTES:
                self._refuse(fname, f"{size} bytes exceeds the "
                                    f"{MAX_BYTES}-byte cap")
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError) as e:
                self._refuse(fname, f"cannot read as UTF-8: {e}")
                continue
            parsed = ch.parse_envelope(text)
            if parsed is None:
                self._refuse(fname, "malformed envelope (no blank "
                                    "line between subject and body)")
                continue
            subject, body = parsed
            stem = fname[:-4] if fname.endswith(".txt") else fname
            # Process-once: a job whose file already sits in done/
            # (same name, or same job_id from an earlier name) is a
            # redelivery -- ack the copy, never re-offer it.
            if os.path.exists(os.path.join(self.done, fname)):
                self._consume(fname)
                continue
            jid = _job_id(subject)
            if jid and os.path.exists(os.path.join(
                    self.done, jid + ".job-seen")):
                self._consume(fname)
                continue
            if stem in self._pending:
                continue  # already delivered; awaiting the core
            ch.deliver_job(self.channel, stem, subject, body)
            self._pending[stem] = (fname, jid)

    def _consume(self, fname):
        try:
            os.replace(os.path.join(self.inbox, fname),
                       os.path.join(self.done, fname))
        except OSError:
            pass

    def scan_results(self):
        for fname, subject, body in ch.pending_results(self.channel):
            ident = fname[:-len(".result.txt")] \
                if fname.endswith(".result.txt") else fname
            entry = self._pending.pop(ident, None)
            watched = entry[0] if entry else None
            jid = _job_id_from_result(subject) or ident
            name = _safe(jid) + ".result.txt"
            path = os.path.join(self.outbox, name)
            n = 2
            while os.path.exists(path):
                path = os.path.join(
                    self.outbox, f"{_safe(jid)}.result-{n}.txt")
                n += 1
            text = ch.envelope(subject, body)
            if body and not body.endswith("\n"):
                text += "\n"
            ch._atomic_write(path, text)
            ch.ack_result(self.channel, fname)
            if watched:
                self._consume(watched)
                if jid:
                    self._mark_seen(jid, watched)
        # Reconcile deliveries the runner consumed without a
        # result coming back (a rejected job sends nothing):
        # the channel's inbox/done is the consumption signal,
        # so the watched file is finished too. A retryable
        # failure does not move that channel file, so this
        # loop does not see it and the watched job stays.
        chan_done = os.path.join(self.channel, "inbox", "done")
        for ident, (watched, jid) in list(self._pending.items()):
            if os.path.exists(os.path.join(
                    chan_done, ident + ".job.txt")):
                del self._pending[ident]
                self._consume(watched)
                if jid:
                    self._mark_seen(jid, watched)

    def _mark_seen(self, jid, watched):
        try:
            with open(os.path.join(self.done, jid + ".job-seen"),
                      "w", encoding="utf-8") as f:
                f.write(watched + "\n")
        except OSError:
            pass


def _job_id_from_result(subject):
    m = re.search(r"\[HOMING-PIGEON\](?:\s+\S+)*\s+"
                  r"(?:result|qresult)\s+(\S+)", subject or "",
                  re.I)
    return m.group(1) if m else None


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    channel_dir, cfg = ch.load_runtime_config(argv)
    if not channel_dir:
        ch.log("file transport: no channel directory given",
               "ERROR")
        return 2
    pipe = FilePipe(cfg, channel_dir)
    ch.log(f"file transport: watching {pipe.inbox}; results "
           f"to {pipe.outbox}")
    interval = ch.poll_interval(cfg)
    while True:
        try:
            pipe.scan_jobs()
            pipe.scan_results()
        except Exception as e:  # the pipe must not die on a file
            ch.log(f"file transport: pass failed: {e!r}", "ERROR")
        ch.nap(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
