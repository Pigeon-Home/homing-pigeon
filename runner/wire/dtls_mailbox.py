"""DTLS datagrams carried as mailbox messages.

A flight is one datagram. Its subject is "[HOMING-PIGEON] dtls"
and its body is the base64 of that datagram. send_mail builds
the message. fetch_job_mails reads the mailbox. A job object
in the same box is not a flight: its subject is a job subject,
and it is left unseen for the job poll.

The box here is in-process. It speaks the UID commands
fetch_job_mails uses. It is not an IMAP server, and nothing
in this module opens a socket.
"""
import base64
import email.policy

from runner.wire.mailbox import fetch_job_mails, mark_seen, send_mail

FLIGHT_SUBJECT = "[HOMING-PIGEON] dtls"


class LocalMailbox:
    """The subset of an IMAP connection fetch_job_mails calls."""

    def __init__(self):
        self.messages = []
        self._next = 1

    def add(self, raw):
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        uid = self._next
        self._next += 1
        self.messages.append({"uid": uid, "raw": bytes(raw), "seen": False})
        return uid

    def uid(self, command, *args):
        command = str(command).upper()
        if command == "SEARCH":
            ids = [m["uid"] for m in self.messages
                   if not m["seen"] and b"[HOMING-PIGEON]" in m["raw"][:2000]]
            blob = b" ".join(str(i).encode("ascii") for i in ids)
            return ("OK", [blob])
        if command == "FETCH":
            uid = int(args[0])
            for message in self.messages:
                if message["uid"] == uid:
                    raw = message["raw"]
                    head = ("%s (RFC822 {%s}" % (uid, len(raw))).encode("ascii")
                    return ("OK", [(head, raw), b")"])
            return ("OK", [None])
        if command == "STORE":
            uid = int(args[0])
            for message in self.messages:
                if message["uid"] == uid:
                    message["seen"] = True
            return ("OK", [None])
        raise AssertionError(command)


class Deposit:
    """An SMTP connection whose send_message lands in one box."""

    def __init__(self, box):
        self.box = box
        self.sent = 0

    def send_message(self, message):
        self.box.add(message.as_bytes())
        self.sent += 1


def send_flight(smtp, cfg, datagram):
    """One datagram, through send_mail, into whatever smtp deposits."""
    body = base64.b64encode(datagram).decode("ascii")
    send_mail(smtp, cfg, FLIGHT_SUBJECT, body)


def classify(raw):
    """('flight', datagram) or ('other', raw).

    A job object, a result, and a body that is not base64 are
    'other'. They are not datagrams.
    """
    try:
        message = email.message_from_bytes(raw, policy=email.policy.default)
    except Exception:
        return ("other", raw)
    subject = str(message.get("Subject") or "")
    if not subject.startswith(FLIGHT_SUBJECT):
        return ("other", raw)
    try:
        body = "".join(str(message.get_content()).split())
        datagram = base64.b64decode(body, validate=True)
    except Exception:
        return ("other", raw)
    if not datagram:
        return ("other", raw)
    return ("flight", datagram)


def take_flights(imap):
    """The datagrams in the unseen pigeon mail. Jobs stay unseen."""
    flights = []
    for ident, raw in fetch_job_mails(imap):
        kind, value = classify(raw)
        if kind != "flight":
            continue
        flights.append(value)
        mark_seen(imap, ident)
    return flights
