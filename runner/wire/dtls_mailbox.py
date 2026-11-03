"""DTLS datagrams carried as mailbox messages.

Version 3 carriage: the version 1 DTLS profile, carried over the
store-and-forward email binding instead of a live UDP path.

Wire shape
----------
A flight is one DTLS datagram. The legacy harness shape is a
message whose subject is "[HOMING-PIGEON] dtls" and whose body is
the base64 of the datagram; it is still accepted. The version 3
shape names a session in the subject, under the one subject
grammar (runner/wire/subject.py):

    [HOMING-PIGEON] dtls <session-id>

and frames the datagram so it can be segmented across messages
and reassembled exactly. The frame --

    HP-DTLS/3 transfer=<16 hex> part=<n> parts=<m> bytes=<total>
        sha384=<hex digest of the whole datagram>
    <one base64 chunk>

-- travels in its own MIME part (content type
application/hp-dtls3, base64 transfer encoding), so text a
provider adds around it, a footer in the text part above all,
is not the frame and cannot break it. A message with no typed
part is read in the original naked shape, the frame as the
text/plain body; a message with a typed part is read from
that part alone.

Subjects route; they never authenticate. A datagram still has to
parse and authenticate under runner/wire/dtlsproto.py. A message
with a DTLS subject whose frame does not yield a datagram is
"dtls-invalid": it is consumed as DTLS input or dropped, and it
is never reinterpreted as a job.

The server and client wrappers in this module own the carriage
rules the DTLS core does not: segmentation and reassembly,
exact-duplicate mail suppression split by phase (a replayed
handshake flight re-posts the saved answer; a replayed
application record is dropped), binding a mail session-id to
the DTLS connection ID it establishes (a record addressed to
one session is not accepted under another session's mail), and
expiry of partial state.

The box at the bottom is in-process. It speaks the UID commands
fetch_job_mails uses. It is not an IMAP server, and nothing in
this module opens a socket.
"""
from __future__ import annotations

import base64
import email
import email.policy
from email.message import EmailMessage
import hashlib
import json
import re
import secrets as _secrets
from collections import OrderedDict, namedtuple

from runner.wire import dtlsproto
from runner.wire import subject as _subject_grammar
from runner.wire.mailbox import (
    fetch_job_mails, mark_seen, send_built_message, send_mail)

FLIGHT_SUBJECT = "[HOMING-PIGEON] dtls"

# The MIME content type of the part that carries one flight
# frame. A private type in a local, unsubmitted draft: it
# requests no registration, and a receiver treats a part of
# this type as the only frame source in its message.
FLIGHT_CONTENT_TYPE = "application/hp-dtls3"

_FLIGHT_NOTE = (
    "This message carries one DTLS flight in its "
    "application/hp-dtls3 part. The flight is data for the "
    "Homing Pigeon runner's DTLS-over-mail carriage; this "
    "text part is not the flight.")

DEFAULT_MAX_DATAGRAM_BYTES = 256 * 1024
DEFAULT_CHUNK_CHARS = 32768
_MAX_PARTS = 1024
_MAX_CHUNK_CHARS = 1024 * 1024

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_V3_SUBJECT_RE = re.compile(
    _subject_grammar.MARKER
    + _subject_grammar.SPACE_CLASS + "+dtls"
    + _subject_grammar.SPACE_CLASS + "+("
    + _subject_grammar.TOKEN_CLASS + "+)"
    + _subject_grammar.SPACE_CLASS + "*$",
    re.I)
_HEADER_RE = re.compile(
    r"^HP-DTLS/3 transfer=([0-9a-f]{16}) part=([0-9]+) "
    r"parts=([0-9]+) bytes=([0-9]+) sha384=([0-9a-f]{96})$")

FlightPart = namedtuple(
    "FlightPart",
    ["session_id", "transfer_id", "index", "count", "total_bytes",
     "sha384", "chunk"])
ClassifiedMail = namedtuple(
    "ClassifiedMail",
    ["kind", "subject", "body", "session_id", "datagram", "part",
     "reason"])


def _log_noop(msg, level="INFO"):
    return None


def valid_session_id(session_id):
    return (isinstance(session_id, str)
            and session_id not in (".", "..")
            and _SESSION_ID_RE.match(session_id) is not None)


def flight_subject(session_id):
    """The version 3 subject for one mail session."""
    if not valid_session_id(session_id):
        raise ValueError("bad dtls mail session id: %r" % (session_id,))
    return FLIGHT_SUBJECT + " " + session_id


def _typed_flight_text(message):
    """The flight frame's text when the message carries a
    dedicated flight part, else None. A present flight part is
    authoritative: its content is the frame source even when it
    is unusable -- a non-base64 transfer encoding, an
    undecodable payload -- in which case the frame is empty
    and the message fails closed downstream. Nothing outside
    the part, a provider footer in the text part above all, is
    ever the frame."""
    for part in message.walk():
        if part.get_content_type() != FLIGHT_CONTENT_TYPE:
            continue
        cte = str(part.get("Content-Transfer-Encoding")
                  or "").strip().lower()
        if cte != "base64":
            return ""
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        return payload.decode("utf-8", "replace")
    return None


def _subject_body(raw):
    """(subject, text body) from one raw RFC822 message: the
    Subject header, and the body the carriage reads -- the
    dedicated flight part's text when the message carries one,
    else the first text/plain part's text, the extraction the
    email extension applies to ordinary mail."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8", "replace")
    try:
        message = email.message_from_bytes(
            raw, policy=email.policy.default)
    except Exception:
        return "", ""
    subject = str(message.get("Subject") or "")
    try:
        typed = _typed_flight_text(message)
        if typed is not None:
            return subject, typed
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain" \
                        and not part.get_filename():
                    payload = part.get_payload(decode=True)
                    if payload:
                        return subject, payload.decode(
                            "utf-8", "replace")
            return subject, ""
        payload = message.get_payload(decode=True)
    except Exception:
        return subject, ""
    if isinstance(payload, bytes):
        return subject, payload.decode("utf-8", "replace")
    return subject, str(message.get_payload() or "")


def _flight_subject_match(subject):
    """The regex match when a subject is exactly a flight
    subject, else None. At most 1 leading "Re:" or "Fwd:"
    (any case) is stripped first, and only when the remainder
    is exactly the flight subject: a chain of prefixes, or
    any other text before the marker, is not flight mail."""
    text = (subject or "").strip()
    lowered = text.lower()
    for prefix in ("re:", "fwd:"):
        if lowered.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return _V3_SUBJECT_RE.fullmatch(text)


def _is_client_hello(datagram):
    records = dtlsproto._split_records(datagram)
    if not records:
        return False
    record = records[0]
    if not dtlsproto._is_plaintext_record(record):
        return False
    if record[0] != dtlsproto.CT_HANDSHAKE:
        return False
    length = int.from_bytes(record[11:13], "big")
    parsed = dtlsproto._parse_handshake(record[13:13 + length])
    if parsed is None:
        return False
    if parsed[0] == "fragment":
        # A fragmented first message is not an initialization
        # (draft Sections 8.2 and 16.4); _datagram_kind names
        # it malformed flight mail instead.
        return False
    return parsed[0] == dtlsproto.HS_CLIENT_HELLO


def _is_fragmented_client_hello(datagram):
    records = dtlsproto._split_records(datagram)
    if not records:
        return False
    record = records[0]
    if not dtlsproto._is_plaintext_record(record):
        return False
    if record[0] != dtlsproto.CT_HANDSHAKE:
        return False
    length = int.from_bytes(record[11:13], "big")
    parsed = dtlsproto._parse_handshake(record[13:13 + length])
    return (parsed is not None and parsed[0] == "fragment"
            and parsed[1] == dtlsproto.HS_CLIENT_HELLO)


def _looks_like_dtls(datagram):
    records = dtlsproto._split_records(datagram)
    if not records:
        return False
    record = records[0]
    if dtlsproto._is_plaintext_record(record):
        return record[0] in (dtlsproto.CT_ALERT, dtlsproto.CT_HANDSHAKE,
                             dtlsproto.CT_APPDATA, dtlsproto.CT_ACK)
    return bool(record and record[0] & 0xE0 == 0x20)


def _datagram_kind(datagram):
    if _is_client_hello(datagram):
        return "dtls-init"
    if _is_fragmented_client_hello(datagram):
        # Malformed flight mail on this carriage: consumed,
        # dropped, worth no answer -- refused here, in the
        # carriage's own fail-closed path, not by the engine.
        return "dtls-invalid"
    if _looks_like_dtls(datagram):
        return "dtls"
    return "dtls-invalid"


def encode_flight(datagram, session_id, transfer_id=None,
                  max_chunk_chars=DEFAULT_CHUNK_CHARS):
    """[(subject, body)] carrying one datagram, segmented when the
    base64 form exceeds one chunk. Chunk boundaries fall on base64
    group boundaries, so each chunk decodes on its own and the
    decoded chunks concatenate to the datagram exactly."""
    if not datagram:
        raise ValueError("an empty datagram is not a flight")
    if len(datagram) > DEFAULT_MAX_DATAGRAM_BYTES:
        raise ValueError("datagram exceeds the carriage size limit")
    subject = flight_subject(session_id)
    transfer_id = transfer_id or _secrets.token_hex(8)
    if re.match(r"^[0-9a-f]{16}$", transfer_id) is None:
        raise ValueError("bad transfer id: %r" % (transfer_id,))
    chunk_chars = max(4, (int(max_chunk_chars) // 4) * 4)
    blob = base64.b64encode(datagram).decode("ascii")
    chunks = [blob[i:i + chunk_chars]
              for i in range(0, len(blob), chunk_chars)]
    digest = hashlib.sha384(datagram).hexdigest()
    out = []
    for index, chunk in enumerate(chunks):
        header = (
            "HP-DTLS/3 transfer=%s part=%d parts=%d bytes=%d "
            "sha384=%s" % (transfer_id, index, len(chunks),
                           len(datagram), digest))
        out.append((subject, header + "\n" + chunk))
    return out


def _parse_framed_body(session_id, body):
    """(ClassifiedMail, None) for a version 3 body, or
    (None, reason). Single-part bodies complete here; a part of a
    larger transfer comes back as kind "dtls-part" for the
    reassembler."""
    text = (body or "").strip()
    head, _sep, rest = text.partition("\n")
    match = _HEADER_RE.match(head.strip())
    if match is None:
        return None, "body carries no HP-DTLS/3 header"
    transfer_id, part_s, parts_s, bytes_s, digest = match.groups()
    index, count, total = int(part_s), int(parts_s), int(bytes_s)
    if count < 1 or count > _MAX_PARTS or index >= count:
        return None, "part numbering is out of range"
    if total < 1 or total > DEFAULT_MAX_DATAGRAM_BYTES:
        return None, "declared datagram size is out of range"
    chunk_text = "".join(rest.split())
    if len(chunk_text) > _MAX_CHUNK_CHARS:
        return None, "part chunk is too large"
    try:
        chunk = base64.b64decode(chunk_text, validate=True)
    except Exception:
        return None, "part chunk is not base64"
    if len(chunk) > total:
        return None, "part chunk exceeds the declared datagram size"
    part = FlightPart(session_id, transfer_id, index, count, total,
                      digest, chunk)
    if count > 1:
        return ClassifiedMail(
            "dtls-part", None, None, session_id, None, part, None), None
    if len(chunk) != total or hashlib.sha384(chunk).hexdigest() != digest:
        return None, "single-part datagram fails its digest"
    kind = _datagram_kind(chunk)
    if kind == "dtls-invalid":
        return None, "datagram is not a DTLS record"
    return ClassifiedMail(
        kind, None, None, session_id, chunk, None, None), None


def parse_message(raw):
    """Classify one raw RFC822 message for the mail parser.

    Kinds: "dtls-init" (a ClientHello flight), "dtls" (any other
    complete DTLS datagram), "dtls-part" (one segment of a larger
    datagram), "dtls-invalid" (DTLS-shaped but malformed -- fail
    closed), "job" (an ordinary job subject), and "other".
    """
    subject, body = _subject_body(raw)

    def classified(kind, session_id=None, datagram=None, part=None,
                   reason=None):
        return ClassifiedMail(kind, subject, body, session_id,
                              datagram, part, reason)

    match = _flight_subject_match(subject)
    if match is not None:
        session_id = match.group(1)
        if not valid_session_id(session_id):
            return classified("dtls-invalid", session_id,
                              reason="bad session id in subject")
        parsed, reason = _parse_framed_body(session_id, body)
        if parsed is None:
            return classified("dtls-invalid", session_id,
                              reason=reason)
        return parsed._replace(subject=subject, body=body)
    if (subject or "").startswith(FLIGHT_SUBJECT):
        if (subject or "").strip() != FLIGHT_SUBJECT:
            return classified("dtls-invalid",
                              reason="unreadable dtls subject")
        try:
            datagram = base64.b64decode(
                "".join((body or "").split()), validate=True)
        except Exception:
            return classified("dtls-invalid",
                              reason="legacy flight body is not base64")
        if not datagram or len(datagram) > DEFAULT_MAX_DATAGRAM_BYTES:
            return classified("dtls-invalid",
                              reason="legacy flight body is out of range")
        kind = _datagram_kind(datagram)
        if kind == "dtls-invalid":
            return classified("dtls-invalid",
                              reason="datagram is not a DTLS record")
        return classified(kind, None, datagram)
    if _subject_grammar.JOB_ID_RE.search(subject or ""):
        return classified("job")
    return classified("other")


class FlightReassembler:
    """Bounded, expiring reassembly of segmented datagrams.

    Duplicate parts are idempotent. A part that contradicts the
    transfer it names (different part bytes, or different header
    fields) destroys that transfer: the sender starts again or
    the input was forged, and neither is completed here.
    """

    def __init__(self, max_transfers=64,
                 max_total_bytes=DEFAULT_MAX_DATAGRAM_BYTES,
                 ttl_sec=3600, deadline_sec=None):
        self.max_transfers = max_transfers
        self.max_total_bytes = max_total_bytes
        self.ttl_sec = ttl_sec
        # An absolute deadline from a transfer's first part,
        # never longer than the idle timeout: a caller's longer
        # value is clamped to it. The idle timer alone is not a
        # bound: a sender dripping 1 part just inside it would
        # hold a transfer slot for as long as it cared to drip.
        self.deadline_sec = ttl_sec if deadline_sec is None \
            else min(deadline_sec, ttl_sec)
        self._transfers = OrderedDict()

    @property
    def pending(self):
        return len(self._transfers)

    def _expire(self, now):
        stale = [key for key, entry in self._transfers.items()
                 if now - entry["updated"] > self.ttl_sec
                 or now - entry["created"] > self.deadline_sec]
        for key in stale:
            del self._transfers[key]

    def offer(self, part, now):
        """One FlightPart in; the whole datagram out, or None."""
        self._expire(now)
        if part is None or part.count < 1 or part.index >= part.count \
                or part.total_bytes < 1 \
                or part.total_bytes > self.max_total_bytes \
                or len(part.chunk) > part.total_bytes:
            return None
        key = (part.session_id, part.transfer_id)
        entry = self._transfers.get(key)
        if entry is None:
            while len(self._transfers) >= self.max_transfers:
                self._transfers.popitem(last=False)
            entry = {"count": part.count, "total": part.total_bytes,
                     "sha384": part.sha384, "parts": {},
                     "created": now, "updated": now}
            self._transfers[key] = entry
        if (entry["count"] != part.count
                or entry["total"] != part.total_bytes
                or entry["sha384"] != part.sha384
                or (part.index in entry["parts"]
                    and entry["parts"][part.index] != part.chunk)):
            del self._transfers[key]
            return None
        entry["parts"][part.index] = part.chunk
        entry["updated"] = now
        self._transfers.move_to_end(key)
        if len(entry["parts"]) < entry["count"]:
            return None
        data = b"".join(entry["parts"][i]
                        for i in range(entry["count"]))
        del self._transfers[key]
        if len(data) != entry["total"] \
                or hashlib.sha384(data).hexdigest() != entry["sha384"]:
            return None
        return data


class _DigestCache:
    """Exact-duplicate suppression, bounded and FIFO."""

    def __init__(self, max_entries=4096):
        self.max_entries = max_entries
        self._seen = OrderedDict()

    def accept(self, data):
        digest = hashlib.sha384(data).digest()
        if digest in self._seen:
            self._seen.move_to_end(digest)
            return False
        self._seen[digest] = True
        while len(self._seen) > self.max_entries:
            self._seen.popitem(last=False)
        return True


def _encode_outgoing(datagram, session_id):
    if session_id is None:
        body = base64.b64encode(datagram).decode("ascii")
        return [(FLIGHT_SUBJECT, body)]
    return encode_flight(datagram, session_id)


class DtlsMailServer:
    """The responder side of the carriage: one DtlsServerCore,
    fed datagrams recovered from mail, answering in mail.

    The carriage is the hybrid profile's home: the core is
    built with hybrid=True unless told otherwise, so a
    client offering X25519MLKEM768 (RFC 10024) negotiates
    the hybrid group on this carriage, and X25519 otherwise."""

    def __init__(self, secret_lookup=None, platform_payload=None,
                 platform_for=None, log=None, rng=None,
                 max_datagram_bytes=DEFAULT_MAX_DATAGRAM_BYTES,
                 dedup_entries=4096, hybrid=True,
                 poll_period_sec=None):
        self.log = log or _log_noop
        if platform_for is None:
            if callable(platform_payload):
                platform_for = platform_payload
            elif platform_payload is None:
                platform_for = lambda session: None
            elif isinstance(platform_payload, (bytes, bytearray)):
                payload = bytes(platform_payload)
                platform_for = lambda session: payload
            elif isinstance(platform_payload, str):
                payload = platform_payload.encode("utf-8")
                platform_for = lambda session: payload
            else:
                payload = json.dumps(
                    platform_payload, sort_keys=True).encode("utf-8")
                platform_for = lambda session: payload
        # Section 7.1 of the draft: on this carriage the
        # retransmission timers stretch to the poll rhythm.
        # A driver that knows its poll period hands it over;
        # without one the core keeps its datagram profile.
        profile = None
        if poll_period_sec is not None:
            profile = dtlsproto.mail_retransmit_profile(
                poll_period_sec)
        self.core = dtlsproto.DtlsServerCore(
            secret_lookup=secret_lookup, platform_for=platform_for,
            log=self.log, rng=rng, hybrid=hybrid,
            retransmit_profile=profile)
        self.max_datagram_bytes = max_datagram_bytes
        self.reassembler = FlightReassembler(
            max_total_bytes=max_datagram_bytes)
        self._dedup = _DigestCache(dedup_entries)
        self._hint_cid = {}
        self._cid_hint = {}
        self.established = {}
        self._app = []
        # peer addr -> [datagram]: the last outbound flight per
        # peer, kept so a duplicate of the flight it answered
        # can re-post it. Bounded first in first out, because a
        # fresh hello under a fresh session-id is free to
        # anyone who can deposit mail and the core keeps no
        # state for it; an evicted entry costs only the re-post
        # (a real retransmission is a new record and is
        # answered by the stack regardless).
        self.max_saved_flights = dedup_entries
        self._last_flight = OrderedDict()
        # peer addr -> True while the saved flight still has its
        # 1 re-post. A re-post costs an outbound mail that an
        # unauthenticated sender can provoke with a captured
        # hello, so each generation of a saved flight is good
        # for 1 re-post; only a new flight from the stack arms
        # another.
        self._repost_armed = {}

    def _save_flight(self, addr, datagrams):
        self._last_flight[addr] = list(datagrams)
        self._last_flight.move_to_end(addr)
        self._repost_armed[addr] = True
        while len(self._last_flight) > self.max_saved_flights:
            old, _flight = self._last_flight.popitem(last=False)
            self._repost_armed.pop(old, None)

    # -- intake ----------------------------------------------------

    def receive_raw(self, raw, now):
        return self.receive_classified(parse_message(raw), now)

    def receive_classified(self, classified, now):
        if classified.kind == "dtls-invalid":
            self.log("dtls-mail: invalid dtls mail dropped: %s"
                     % (classified.reason or "malformed"), "WARN")
            return []
        if classified.kind == "dtls-part":
            datagram = self.reassembler.offer(classified.part, now)
            if datagram is None:
                return []
            return self._receive_datagram(
                datagram, classified.session_id, now)
        if classified.kind in ("dtls", "dtls-init"):
            return self._receive_datagram(
                classified.datagram, classified.session_id, now)
        return []

    @staticmethod
    def _addr_for(session_id):
        return "email:" + (session_id or "legacy")

    @staticmethod
    def _hint_for(addr):
        """The mail session-id an address was made from, or None
        for the unaddressed harness shape. Derived, not stored:
        an address is a function of the session-id and nothing
        else, so no table grows with the hellos a stranger
        deposits."""
        if not isinstance(addr, str) or not addr.startswith("email:"):
            return None
        hint = addr[len("email:"):]
        return None if hint == "legacy" else hint

    def _receive_datagram(self, datagram, session_id, now):
        if not datagram or len(datagram) > self.max_datagram_bytes:
            return []
        cid = dtlsproto._record_cid(datagram)
        if cid is not None:
            bound = self._hint_cid.get(session_id)
            if bound is not None and bound != cid:
                self.log("dtls-mail: record for one session "
                         "arrived under another session's mail; "
                         "dropped", "WARN")
                return []
            owner = self._cid_hint.get(cid)
            if owner is not None and owner != session_id:
                self.log("dtls-mail: record's session does not "
                         "match its mail session; dropped", "WARN")
                return []
        # The binding check runs before duplicate suppression:
        # a misaddressed copy must not poison the digest cache
        # against the same record arriving under its own
        # session's mail, where it is legitimate.
        addr = self._addr_for(session_id)
        if not self._dedup.accept(datagram):
            return self._repost_last_flight(session_id, addr)
        try:
            out = self.core.feed(datagram, addr, now)
        except Exception as e:
            self.log("dtls-mail: session input failed: %r" % (e,),
                     "WARN")
            return []
        if out:
            self._save_flight(addr, out)
        session = self.core.by_addr.get(addr)
        if session is not None and session.session_id is not None:
            self._bind(session_id, session.session_id)
        self._drain_events(session_id)
        mails = []
        for datagram_out in out:
            mails.extend(_encode_outgoing(datagram_out, session_id))
        return mails

    def _repost_last_flight(self, session_id, addr):
        """A bit-identical duplicate of a handshake-phase
        datagram. The duplicate is the signal the peer's
        retransmission gives that our answer was lost
        (RFC 9147 Section 5.8.1), so the saved last outbound
        flight is posted again -- re-encoded under fresh
        transfer identifiers, and the duplicate itself is
        never fed to the stack again, so nothing is derived
        twice. The re-post is budgeted: each generation of a
        saved flight is re-posted at most once, and further
        bit-identical copies are dropped, so a captured hello
        is worth at most 1 extra outbound mail and never a
        mail per copy. Once the session is established, a
        duplicate is application data or a replay of it: it
        is dropped and does nothing."""
        session = self.core.by_addr.get(addr)
        if session is not None and session.established:
            self.log("dtls-mail: duplicate application record "
                     "suppressed", "WARN")
            return []
        saved = self._last_flight.get(addr)
        if not saved:
            return []
        if not self._repost_armed.get(addr):
            self.log("dtls-mail: duplicate handshake flight; the "
                     "saved flight was already re-posted once; "
                     "dropped", "WARN")
            return []
        self._repost_armed[addr] = False
        self.log("dtls-mail: duplicate handshake flight; "
                 "re-posting the last flight", "WARN")
        mails = []
        for datagram_out in saved:
            mails.extend(_encode_outgoing(datagram_out,
                                          session_id))
        return mails

    def _bind(self, session_id, cid):
        self._hint_cid[session_id] = cid
        self._cid_hint[cid] = session_id

    def _drain_events(self, default_hint):
        events, self.core.events = self.core.events, []
        for event in events:
            if event[0] == "established":
                cid = event[1]
                info = event[2] or {}
                hint = self._hint_for(info.get("addr")) \
                    if info.get("addr") is not None else default_hint
                self._bind(hint, cid)
                self.established[hint] = cid
            elif event[0] == "app":
                cid = event[1]
                hint = self._cid_hint.get(cid, default_hint)
                self._app.append((hint, cid, event[2]))

    def drain_app_messages(self):
        """[(mail session-id, DTLS session CID, message bytes)]."""
        out, self._app = self._app, []
        return out

    # -- driving and sending -------------------------------------

    def tick_mails(self, now):
        mails = []
        flights = {}
        for addr, datagram in self.core.tick(now):
            flights.setdefault(addr, []).append(datagram)
            mails.extend(_encode_outgoing(datagram,
                                          self._hint_for(addr)))
        for addr, datagrams in flights.items():
            self._save_flight(addr, datagrams)
        self._drain_events(None)
        return mails

    def send_app_mails(self, session_cid, data):
        hint = self._cid_hint.get(session_cid)
        mails = []
        for _addr, datagram in self.core.send_app(session_cid, data):
            mails.extend(_encode_outgoing(datagram, hint))
        return mails


class DtlsMailClient:
    """The initiator side of the carriage: one DtlsClientCore,
    fed datagrams recovered from mail, answering in mail.

    The core is built with hybrid=True unless told otherwise:
    this carriage offers the X25519MLKEM768 hybrid share
    beside the X25519 share (see DtlsMailServer)."""

    def __init__(self, secret, session_id=None, key_id=None,
                 log=None, rng=None, ticket=None,
                 max_datagram_bytes=DEFAULT_MAX_DATAGRAM_BYTES,
                 dedup_entries=4096, hybrid=True,
                 poll_period_sec=None):
        self.log = log or _log_noop
        self.session_id = session_id or _secrets.token_hex(16)
        if not valid_session_id(self.session_id):
            raise ValueError(
                "bad dtls mail session id: %r" % (session_id,))
        # The Section 7.1 stretch, as on the server: with a
        # poll period the timers follow the poll rhythm.
        profile = None
        if poll_period_sec is not None:
            profile = dtlsproto.mail_retransmit_profile(
                poll_period_sec)
        self.core = dtlsproto.DtlsClientCore(
            secret, key_id=key_id, log=self.log, rng=rng,
            ticket=ticket, hybrid=hybrid,
            retransmit_profile=profile)
        self.max_datagram_bytes = max_datagram_bytes
        self.reassembler = FlightReassembler(
            max_total_bytes=max_datagram_bytes)
        self._dedup = _DigestCache(dedup_entries)
        self._last_flight = []   # [datagram] of the last flight
        # True while the saved flight still has its 1 re-post
        # (the same budget the responder keeps).
        self._repost_armed = False

    @property
    def state(self):
        return self.core.state

    @property
    def greeting(self):
        return self.core.greeting

    @property
    def app_messages(self):
        return self.core.app_messages

    def _wrap(self, datagrams, fresh=True):
        if fresh and datagrams and self.core.state != "established":
            self._last_flight = list(datagrams)
            self._repost_armed = True
        mails = []
        for datagram in datagrams:
            mails.extend(encode_flight(datagram, self.session_id))
        return mails

    def start_mails(self, now):
        return self._wrap(self.core.start(now))

    def tick_mails(self, now):
        return self._wrap(self.core.tick(now))

    def send_app_mails(self, data):
        return self._wrap(self.core.send_app(data))

    def receive_raw(self, raw, now):
        return self.receive_classified(parse_message(raw), now)

    def receive_classified(self, classified, now):
        if classified.kind in ("job", "other"):
            return []
        if classified.session_id is not None \
                and classified.session_id != self.session_id:
            return []
        if classified.kind == "dtls-invalid":
            self.log("dtls-mail: invalid dtls mail dropped: %s"
                     % (classified.reason or "malformed"), "WARN")
            return []
        if classified.kind == "dtls-part":
            datagram = self.reassembler.offer(classified.part, now)
            if datagram is None:
                return []
            return self._receive_datagram(datagram, now)
        if classified.kind in ("dtls", "dtls-init"):
            return self._receive_datagram(classified.datagram, now)
        return []

    def _receive_datagram(self, datagram, now):
        if not datagram or len(datagram) > self.max_datagram_bytes:
            return []
        if not self._dedup.accept(datagram):
            # The split, on the initiator side: a duplicate
            # from the handshake phase re-posts the saved last
            # flight (the responder's answer was likely lost),
            # once per generation of that flight; a duplicate
            # at or after establishment does nothing.
            if self.core.state == "established" \
                    or not self._last_flight:
                return []
            if not self._repost_armed:
                self.log("dtls-mail: duplicate handshake flight; "
                         "the saved flight was already re-posted "
                         "once; dropped", "WARN")
                return []
            self._repost_armed = False
            self.log("dtls-mail: duplicate handshake flight; "
                     "re-posting the last flight", "WARN")
            return self._wrap(list(self._last_flight), fresh=False)
        try:
            out = self.core.feed(datagram, now)
        except Exception as e:
            self.log("dtls-mail: session input failed: %r" % (e,),
                     "WARN")
            return []
        return self._wrap(out)


# ------------------------------------------------------------------
# The local harness box (unchanged shape, kept for the proof tests)
# ------------------------------------------------------------------

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
        self.messages.append({"uid": uid, "raw": bytes(raw),
                              "seen": False})
        return uid

    def uid(self, command, *args):
        command = str(command).upper()
        if command == "SEARCH":
            ids = [m["uid"] for m in self.messages
                   if not m["seen"]
                   and b"[HOMING-PIGEON]" in m["raw"][:2000]]
            blob = b" ".join(str(i).encode("ascii") for i in ids)
            return ("OK", [blob])
        if command == "FETCH":
            uid = int(args[0])
            for message in self.messages:
                if message["uid"] == uid:
                    raw = message["raw"]
                    head = ("%s (RFC822 {%s}"
                            % (uid, len(raw))).encode("ascii")
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


def build_flight_message(cfg, subject, body):
    """One flight mail as a message object: a short text part
    a human can read, and the frame in its own
    application/hp-dtls3 part with base64 transfer encoding.
    Text a provider adds anywhere else in the message -- a
    footer in the text part above all -- is not the frame and
    cannot break the flight.

    The frame part is attached as bytes, so it lands as a
    direct leaf part of the multipart. Attaching a whole
    message object instead would wrap it in a message/rfc822
    container, one level down from where the draft puts it:
    a receiver reading the message's own parts would not
    find it there, and a gateway that treats the container
    as an opaque attachment can drop the flight with it."""
    msg = EmailMessage()
    msg["From"] = str(cfg.get("mailbox_user") or "")
    msg["To"] = str(cfg.get("mailbox_user") or "")
    msg["Subject"] = " ".join(str(subject or "").splitlines())
    msg.set_content(_FLIGHT_NOTE)
    msg.add_attachment((body or "").encode("utf-8"),
                       maintype="application", subtype="hp-dtls3")
    return msg


def send_flight(smtp, cfg, datagram, session_id=None, transfer_id=None,
                max_chunk_chars=DEFAULT_CHUNK_CHARS):
    """One datagram, as mail, into whatever smtp deposits.

    Without a session id this is the legacy harness shape: one
    message, subject "[HOMING-PIGEON] dtls", body the base64 of
    the datagram. With one, it is the version 3 shape of
    encode_flight, one message per part, each carrying its
    frame in the dedicated MIME part."""
    if session_id is None:
        body = base64.b64encode(datagram).decode("ascii")
        send_mail(smtp, cfg, FLIGHT_SUBJECT, body)
        return
    for subject, body in encode_flight(
            datagram, session_id, transfer_id=transfer_id,
            max_chunk_chars=max_chunk_chars):
        send_built_message(
            smtp, build_flight_message(cfg, subject, body))


def classify(raw):
    """('flight', datagram) or ('other', raw).

    A job object, a result, a segmented flight (which needs the
    reassembler's state), and a body that is not a datagram are
    'other'. They are not complete datagrams."""
    parsed = parse_message(raw)
    if parsed.kind in ("dtls", "dtls-init") \
            and parsed.datagram is not None:
        return ("flight", parsed.datagram)
    return ("other", raw)


def take_flights(imap):
    """The complete datagrams in the unseen pigeon mail. Jobs and
    segmented flights stay unseen."""
    flights = []
    for ident, raw in fetch_job_mails(imap):
        kind, value = classify(raw)
        if kind != "flight":
            continue
        flights.append(value)
        mark_seen(imap, ident)
    return flights
