"""The email transport extension: the mailbox is the pipe.

This process owns the mailbox lifecycle -- IMAP connect, poll,
mark-seen, SMTP send -- and nothing else. Job handling stays
in the runner core: a fetched message's (subject, signed body)
crosses the channel as a job envelope, the core verifies and
executes, and the signed result comes back through the channel
for this process to send. The mailbox credentials live in this
extension's runtime config (the runner hands them over from
config.json); the core never opens the mailbox for the poll
loop any more.

Delivery discipline mirrors the pre-extension mail path:
  - a message is marked seen only after its result has been
    sent (or the delivery itself is acked in the channel);
  - a job whose channel file already sits in the channel's
    done/ was delivered before -- re-offering it would only
    duplicate work the runner already dedupes by seen-set, so
    it is marked seen and not re-delivered;
  - results are sent to the mailbox itself unless the job's
    signed body names a valid reply_to, exactly the routing
    the mail path has always applied.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402
from runner import mailbox as _mailbox  # noqa: E402

_mailbox.set_logger(ch.log)

def _subject_body(raw):
    """(subject, text body) from one raw RFC822 message -- the
    same extraction the core applies to mail it handles: the
    Subject header, and the first text/plain part's text."""
    import email as _email
    msg = _email.message_from_bytes(raw)
    subject = str(msg["Subject"] or "")
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" \
                    and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    return subject, payload.decode(
                        "utf-8", errors="replace")
        return subject, ""
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        return subject, payload.decode("utf-8", errors="replace")
    return subject, msg.get_payload() or ""


def reply_target(body, mailbox_addr):
    """Where a result goes: the job's signed reply_to when it
    validates (the core's own rule, applied to the job object
    parsed out of the body), else the mailbox itself -- exactly
    the routing the mail path has always used. Only a single
    plain address from inside the signed body is honored, so a
    spoofed From header can never steer results."""
    job = None
    text = body or ""
    start = text.find("{")
    if start >= 0:
        try:
            job, _end = json.JSONDecoder().raw_decode(text[start:])
        except ValueError:
            job = None
    rt = _mailbox._valid_reply_to(job)
    return rt if rt else mailbox_addr


class EmailPipe:
    """One connection pair per pass: fetch, deliver, send the
    results that are ready, mark seen what is fully carried."""

    def __init__(self, cfg, channel_dir, imap_factory=None,
                 smtp_factory=None):
        self.cfg = cfg
        self.channel = channel_dir
        self._imap_factory = imap_factory or _mailbox.connect_imap
        self._smtp_factory = smtp_factory or _mailbox.connect_smtp
        self.mailbox_addr = _mailbox._mailbox(cfg)
        self._delivered = {}  # seq -> channel ident
        self._targets = {}    # channel ident -> result address

    def pass_once(self):
        imap = self._imap_factory(self.cfg)
        try:
            mails = _mailbox.fetch_job_mails(imap)
            outbox = os.path.join(self.channel, "outbox")
            for seq, raw in mails:
                subject, body = _subject_body(raw)
                ident = f"mail-{seq}"
                done = os.path.join(
                    self.channel, "inbox", "done",
                    ident + ".job.txt")
                if os.path.exists(done):
                    # Already carried once. Mark seen -- unless
                    # its result is still waiting in the outbox,
                    # in which case the flush below marks it when
                    # the result actually goes out.
                    if not os.path.exists(os.path.join(
                            outbox, ident + ".result.txt")):
                        _mailbox.mark_seen(imap, seq)
                    continue
                ch.deliver_job(self.channel, ident, subject, body)
                self._delivered[seq] = ident
                # The result's destination is decided by the
                # JOB's signed reply_to, which the result body
                # does not carry -- remember it from delivery.
                self._targets[ident] = reply_target(
                    body, self.mailbox_addr)
            self.flush_results(imap)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def flush_results(self, imap):
        pending = ch.pending_results(self.channel)
        if not pending:
            return
        smtp = self._smtp_factory(self.cfg)
        try:
            for fname, subject, body in pending:
                ident = fname[:-len(".result.txt")] \
                    if fname.endswith(".result.txt") else fname
                to = self._targets.pop(ident, self.mailbox_addr)
                _mailbox.send_mail(smtp, self.cfg, subject, body,
                                   to=to)
                ch.ack_result(self.channel, fname)
                for seq, dident in list(self._delivered.items()):
                    if dident == ident:
                        _mailbox.mark_seen(imap, seq)
                        del self._delivered[seq]
        finally:
            try:
                smtp.quit()
            except Exception:
                pass

    def run(self):
        try:
            interval = max(
                1.0, float(self.cfg.get("poll_interval_sec")
                           or 20))
        except (TypeError, ValueError):
            interval = 20.0
        ch.log(f"email transport: polling "
               f"{self.mailbox_addr or 'mailbox'} every "
               f"{interval:.0f}s")
        while True:
            try:
                self.pass_once()
            except Exception as e:  # a dead connection fails the
                # pass; the next pass reconnects. Nothing here
                # may take the runner down with it.
                ch.log(f"email transport: pass failed: {e!r}",
                       "WARN")
            ch.nap(interval)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    channel_dir, cfg = ch.load_runtime_config(argv)
    if not channel_dir:
        ch.log("email transport: no channel directory given",
               "ERROR")
        return 2
    EmailPipe(cfg, channel_dir).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
