#!/usr/bin/env python3
# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Project blueMonday: the fuzz corpus against the verifiers (Q62).

    python runner/tools/bluemonday_corpus.py seed   [--target T]
    python runner/tools/bluemonday_corpus.py grow   [--target T] [--rounds N]
                                                    [--seed S] [--jobs J]
                                                    [--minutes M]
    python runner/tools/bluemonday_corpus.py replay [--target T]
    python runner/tools/bluemonday_corpus.py platform [--target T]
    python runner/tools/bluemonday_corpus.py promote [--target T]
    python runner/tools/bluemonday_corpus.py stats  [--target T]

A coverage-guided seed corpus, kept under runner/tests/bluemonday/
as replayable fixtures, against the readers that stand between a
delivered body and the agent's trust in it:

    wire    runner/wire/verify.py        verify_body, verify_body_keyed;
            runner/wire/mailbox.py       _valid_reply_to and send_mail on
                                         every trusted body (provenance)
    cloud   runner/cloud/send_job.py     verify_body (the front-end's copy)
    v2      runner/wire/protocol_v2.py   validate
    crypto  runner/wire/jobcrypto.py     decrypt_body
    local   runner/runner.py             _ingest_local_envelope_inner,
            runner/wire/transports.py    parse_envelope
    stash   runner/runner.py             _record_payload (a stashed
                                         record's body, its three key slots)
    mail    runner/runner.py             get_text_body, _bounce_of, the
            runner/ops/mail.py           subject's job id; the email
            transport_extensions/email   extension's _subject_body and
            runner/wire/mailbox.py       reply_target (_valid_reply_to)
    dtls    runner/wire/dtlsproto.py     _split_records, _parse_handshake,
                                         _parse_extensions, the hello,
                                         key-share and PSK readers,
                                         DtlsServerCore.feed
    board   runner/wire/board.py         submit, offer, complete,
                                         approve, reoffer_expired
    board_ops  runner/wire/board.py      Board: load, submit, offer,
                                         complete, approve,
                                         reoffer_expired -- a board
                                         file and a sequence of peer
                                         operations on it
    channels runner/wire/transports.py   fetch_channel_messages over
                                         a throwaway directory; the
                                         entry is the pair
    manifest runner/ops/extensions.py    parse_manifest
    inbox    runner/wire/transports.py   fetch_channel_messages and
                                         service_channel over a whole
                                         inbox of files, links and dirs
                                         as a peer left them, the core's
                                         side in five shapes
    secret   runner/cloud/send_job.py    require_signable_secret and
             runner/guard/security.py    validate_shared_secret on one
                                         candidate secret: the sender's
                                         rule and the runner's agree
    local_inbox  runner/runner.py        _scan_local_inbox over a whole
                                         local inbox as a peer left it:
                                         each .json read once, filed or
                                         refused, removed either way;
                                         the store holds what was filed

The contract each target is held to is the one its docstrings
state, never its implementation: a bad body is refused with the
refusal type (ValueError, or JobCryptoError for the envelope
reader) and nothing else; a good body round-trips; the two signers
agree, and the two verifiers of one module agree on what they
trust. An exception of any other type, a return of the wrong
shape, or a disagreement is a crash: it is written to
<target>.crashes.jsonl, shrunk, and the command exits 1. The
campaign files each crash as an expectedFailure probe with a Q
(see runner/tests/test_bluemonday_corpus.py), and this lane fixes
the reader.

The corpus grows the way the job-fuzz extension's mutators grow a
job: an entry is kept when its execution reaches a line arc no
earlier entry reached, measured with sys.settrace over the target's
own files only. `seed` writes the suite-style fixtures (signed
jobs, an exec job, a sensor alert, v2 messages, an encryption
envelope, and the preamble, trailer, CRLF and control-character
forms the mail path must survive) and, on a corpus that exists,
adds only the seeds it lacks. `grow` mutates from the corpus
for N rounds (HP_BLUEMONDAY_ROUNDS, default 400) and appends the
keepers; the targets grow --jobs at a time in their own processes
(HP_BLUEMONDAY_JOBS; the default is the box's core count), the
next one starting the moment any one finishes, so a plain grow
keeps every core busy; with
--minutes M the targets cycle until the time is up, the continuous
grow that fills the gap between a measure and a pass (each cycle
moves a target's seed on by one, so no cycle repeats the last).
`replay` runs every entry against its contract, which is what the
test does on every leg, without the tracer. `promote`,
after a fix, moves the crashes that now refuse properly into the
corpus. `stats` prints the sizes.

Stdlib only; no hypothesis, no new CI leg. Every entry is a JSON
line: {"id", "kind": "text"|"payload", "data", "from",
"mutator", "arcs"}. The first line of each file is a header
carrying the chat stamp. The work itself is data in the tree too:
runs.jsonl gets one line per seed or grow (the head, the seed, the
rounds, what was tried, what was kept, what crashed, how long),
and <target>.arcs.json is the arc map the corpus reaches after it,
so every run is in the history and replayable from its seed.
"""
import argparse
import copy
import hashlib
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import security as SEC  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402
from runner.ops import extensions as EX  # noqa: E402
from runner.ops.extensions import build_sensor_alert  # noqa: E402
from runner.wire import jobcrypto as JC  # noqa: E402
from runner.wire import protocol_v2 as P2  # noqa: E402
from runner.wire import transports as TR  # noqa: E402
from runner.wire import verify as V  # noqa: E402
from runner.wire import board as BD  # noqa: E402
from runner.wire import dtlsproto as DT  # noqa: E402
from runner.wire import mailbox as MB  # noqa: E402
import runner.runner as R  # noqa: E402

STAMP = "50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f"
CORPUS_DIR = os.path.join(ROOT, "runner", "tests", "bluemonday")
DEFAULT_ROUNDS = 400
MAX_TEXT = 16 * 1024          # bytes of a text entry after mutation
MAX_PAYLOAD = 16 * 1024       # bytes of a payload entry's JSON
MAX_DEPTH = 24                # nesting a payload mutator may add to
SHRINK_BUDGET = 240           # checks a crash's shrink may spend

# Invented secrets for invented fixtures: 64 hex digits each, the
# shape validate_shared_secret accepts. Nothing here is a real key.
SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"
SENSE = "9c4e1b7a2d5f8036b1e4c7a9d2f5083a6c9e1b4d7f0a3c6e9b2d5f8a1c4e7b0d"
OPS = "3b7d1f9a5c2e8046d9a3f1c7b5e2096a8d4c0f6b2e9a7c3d1f5b8e0a6c4d2f91"
WRONG = "0000000000000000000000000000000000000000000000000000000000000001"
SECRETS = {"": SECRET, "canary-key": SENSE, "ops": OPS}
LOCAL_CFG = {
    "shared_secret": SECRET,
    "additional_secrets": {"canary-key": SENSE, "ops": OPS},
    "mailbox_user": "runner@example.com",
    "max_job_age_sec": 3600,
    "sensors": {"canary": {"enabled": True, "key_id": "canary-key"}},
}
NOW = "@now"      # a payload issued_at the checker stamps at check time
FIXED_AT = "2026-10-26T12:00:00Z"


class Crash(Exception):
    """The contract was broken: carries the kind and the detail."""

    def __init__(self, kind, detail):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


# ------------------------------------------------------------------
# The arc tracer
# ------------------------------------------------------------------

class ArcTracer:
    """Collect (file, from_line, to_line) arcs inside the given files.

    settrace's global function sees every call; it hands a local
    tracer only to frames whose code lives in one of the target's
    files, so the cost is the target's own lines and nothing else.
    Whatever tracer was installed before (a coverage run's) is put
    back when the traced call returns.
    """

    def __init__(self, files):
        self.files = {os.path.normcase(os.path.abspath(f)) for f in files}
        self.arcs = set()
        self.new = 0
        self._last = {}
        self._known = {}

    def _mine(self, filename):
        hit = self._known.get(filename)
        if hit is None:
            hit = os.path.normcase(os.path.abspath(filename)) in self.files
            self._known[filename] = hit
        return hit

    def _global(self, frame, event, arg):
        if event != "call" or not self._mine(frame.f_code.co_filename):
            return None
        self._last[id(frame)] = 0
        self.arcs.add((frame.f_code.co_filename, 0, frame.f_lineno))
        return self._local

    def _local(self, frame, event, arg):
        if event == "line":
            key = id(frame)
            prev = self._last.get(key, 0)
            line = frame.f_lineno
            self.arcs.add((frame.f_code.co_filename, prev, line))
            self._last[key] = line
        elif event == "return":
            self._last.pop(id(frame), None)
        return self._local

    def run(self, fn, *args):
        """fn(*args) under the tracer; afterwards `new` is the count of
        arcs the call added. Whatever fn raises propagates."""
        before = len(self.arcs)
        previous = sys.gettrace()
        sys.settrace(self._global)
        try:
            return fn(*args)
        finally:
            sys.settrace(previous)
            self.new = len(self.arcs) - before


# ------------------------------------------------------------------
# Entries
# ------------------------------------------------------------------

def entry_id(kind, data):
    blob = json.dumps([kind, data], sort_keys=True, ensure_ascii=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def make_entry(kind, data, origin, mutator, arcs=0):
    return {"id": entry_id(kind, data), "kind": kind, "data": data,
            "from": origin, "mutator": mutator, "arcs": arcs}


def _stamp_issued_at(payload):
    """A payload whose issued_at is the NOW token is stamped with the
    present, so a stored alert's path stays reachable on replay."""
    if isinstance(payload, dict) and payload.get("issued_at") == NOW:
        payload = dict(payload)
        payload["issued_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    return payload


def _signing_secret(payload):
    """The secret a payload's key_id selects, or None when the keyed
    verifier must refuse it (a key_id that is not a known string)."""
    key_id = payload.get("key_id", "") if isinstance(payload, dict) else ""
    if isinstance(key_id, str) and key_id in SECRETS:
        return SECRETS[key_id], key_id
    return None, key_id


# ------------------------------------------------------------------
# Contracts
# ------------------------------------------------------------------

def _call(fn, *args):
    """(result, exception) of one call; a non-Exception BaseException
    (KeyboardInterrupt, SystemExit) still propagates."""
    try:
        return fn(*args), None
    except Exception as e:  # the contract decides what is allowed
        return None, e


def _expect_refusal(exc, allowed, what):
    if not isinstance(exc, allowed):
        raise Crash("exception", f"{what} raised {type(exc).__name__}: "
                    f"{_short(exc)}")
    # Which refusal, not only that one came: two readers that refuse
    # the same entry for different reasons are told apart.
    note("refusal", what, type(exc).__name__, str(exc)[:80])


def _short(exc):
    text = str(exc)
    return text if len(text) <= 200 else text[:200] + "..."


def _unsigned(payload):
    """The payload without the protocol's own member: `sig` is the
    signature's slot on the wire, so a payload that carries one of
    its own is read back with the slot overwritten by the keyed
    reader and kept by the plain one; neither is a disagreement."""
    return {k: v for k, v in payload.items() if k != "sig"}


def _differential(text, agent, aexc):
    """The two verifiers of one body, the agent's and the front-end's,
    either both trust it and read the same dict or both refuse (Q65).
    The one difference by design (Q61): the agent retries a body
    with a transport's control characters stripped and the
    front-end does not, so the agent trusting what the front-end
    refuses is a finding only when the signed object carries no
    control character to explain it."""
    cloud, cexc = _call(SJ.verify_body, text, SECRET)
    if cexc is not None:
        _expect_refusal(cexc, ValueError, "send_job.verify_body")
    elif not isinstance(cloud, dict):
        raise Crash("shape", "send_job.verify_body returned "
                    f"{type(cloud).__name__}")
    if aexc is None and cexc is None:
        if agent != cloud:
            raise Crash("agreement", "the agent and the front-end read "
                        "different payloads from one body")
    elif aexc is None:
        raw, _rexc = _call(lambda: V._extract_signed(
            V._normalize(text).rstrip())[0])
        if raw is None or V._strip_controls(raw) == raw:
            raise Crash("agreement", "the agent trusts a body the "
                        "front-end refuses, and no control character "
                        f"explains it: {_short(cexc)}")
    elif cexc is None:
        raise Crash("agreement", "the front-end trusts a body the agent "
                    f"refuses: {_short(aexc)}")


class _FakeSmtp:
    """An SMTP connection that keeps what it was given to send."""

    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


def _provenance(job):
    """Provenance: where a trusted job's result goes is decided by
    _valid_reply_to on the signed dict alone -- None, or a single
    plain address the dict itself carries under reply_to, stripped,
    no longer than 254 characters, matching the one pattern -- and
    send_mail addresses the result there or to the runner's own
    mailbox, with the subject on one line, never raising on what
    _valid_reply_to chose."""
    target, exc = _call(MB._valid_reply_to, job)
    if exc is not None:
        raise Crash("exception", "_valid_reply_to raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if target is not None:
        raw = job.get("reply_to")
        if (not isinstance(target, str) or not isinstance(raw, str)
                or target != raw.strip() or len(target) > 254
                or not MB._REPLY_TO_RE.match(target)):
            raise Crash("provenance", f"_valid_reply_to chose {target!r}, "
                        "not a single plain address from the signed body")
    smtp = _FakeSmtp()
    # The subject the core would build: a job_id that failed the
    # safe-id check never reaches a result, so the token stands in.
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or not R._SAFE_JOB_ID.match(job_id):
        job_id = "bm-unsafe-id"
    subject = "[HOMING-PIGEON] result " + job_id
    _r, exc = _call(MB.send_mail, smtp, LOCAL_CFG, subject, "{}", target)
    if exc is not None:
        raise Crash("exception", "send_mail raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if len(smtp.sent) != 1:
        raise Crash("provenance", f"send_mail sent {len(smtp.sent)} messages")
    msg = smtp.sent[0]
    if msg["To"] != (target or LOCAL_CFG["mailbox_user"]):
        raise Crash("provenance", f"the result is addressed to {msg['To']!r}")
    if len(str(msg["Subject"]).splitlines()) > 1:
        raise Crash("provenance", "the result subject spans lines")
    note("reply_to", target, msg["From"], msg["To"], msg["Subject"],
         _digest(msg.get_content()))
    # Any text in the subject slot, the unsafe id included, is sent
    # on one line rather than dropped.
    smtp = _FakeSmtp()
    raw_id = job.get("job_id")
    if isinstance(raw_id, str) and raw_id != job_id:
        _r, exc = _call(MB.send_mail, smtp, LOCAL_CFG,
                        "[HOMING-PIGEON] result " + raw_id, "{}", target)
        if exc is not None:
            raise Crash("exception", "send_mail raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if len(smtp.sent) != 1:
            raise Crash("provenance", "send_mail dropped a result over "
                        "its subject text")


def _verify_text(text):
    """wire: both readers of runner/wire/verify.py on one received
    body, each to its contract, the two in agreement, and the
    front-end's verifier in agreement with them (the differential);
    a trusted body's reply target is held to provenance."""
    got, exc = _call(V.verify_body, text, SECRET)
    if exc is not None:
        _expect_refusal(exc, ValueError, "verify_body")
    elif not isinstance(got, dict):
        raise Crash("shape", f"verify_body returned {type(got).__name__}")
    _differential(text, got, exc)
    if exc is None:
        _provenance(got)
    keyed, kexc = _call(V.verify_body_keyed, text, SECRETS)
    if kexc is not None:
        _expect_refusal(kexc, ValueError, "verify_body_keyed")
    elif not (isinstance(keyed, tuple) and len(keyed) == 2
              and isinstance(keyed[0], dict)
              and isinstance(keyed[1], str)):
        raise Crash("shape", "verify_body_keyed returned "
                    f"{type(keyed).__name__}")
    if exc is None:
        note("dict", _digest(got))
    if kexc is None:
        note("key", keyed[1], _digest(keyed[0]))
    if exc is None and got.get("key_id", "") == "":
        # Trusted under the default secret by one reader: the keyed
        # reader selects the same secret and must trust it too.
        if kexc is not None:
            raise Crash("agreement", "verify_body trusts a body "
                        f"verify_body_keyed refuses: {_short(kexc)}")
        payload, key_id = keyed
        if key_id != "":
            raise Crash("agreement", f"keyed reader chose key {key_id!r} "
                        "for a body the default secret verifies")
        if _unsigned(payload) != _unsigned(got):
            raise Crash("agreement", "the two readers disagree on the "
                        "payload of one body")
    return "accepted" if exc is None else "refused"


def _cloud_text(text):
    """cloud: the front-end's verifier refuses with ValueError or
    returns a dict, and the agent's verifier agrees with it both
    ways (the differential, with Q61's one difference by design)."""
    got, exc = _call(SJ.verify_body, text, SECRET)
    if exc is not None:
        _expect_refusal(exc, ValueError, "send_job.verify_body")
    elif not isinstance(got, dict):
        raise Crash("shape", f"send_job.verify_body returned "
                    f"{type(got).__name__}")
    agent, aexc = _call(V.verify_body, text, SECRET)
    if aexc is not None:
        _expect_refusal(aexc, ValueError, "verify_body")
    _differential(text, agent, aexc)
    if exc is None:
        note("dict", _digest(got))
    return "accepted" if exc is None else "refused"


def _signed_payload(payload, signer, who):
    """Sign a payload with the secret its key_id selects (the default
    when it names none) and hold the result to the round-trip: both
    verifiers trust the body under that secret and read the payload
    back; the keyed reader agrees or refuses the unknown key; the
    wrong secret is refused."""
    secret, key_id = _signing_secret(payload)
    body, exc = _call(signer, payload, secret or SECRET)
    if exc is not None:
        _expect_refusal(exc, ValueError, who)
        return "refused"
    if not isinstance(body, str):
        raise Crash("shape", f"{who} returned {type(body).__name__}")
    expect = TU._json_safe(payload) if signer is V.sign_payload else payload
    for verifier, name in ((V.verify_body, "verify_body"),
                           (SJ.verify_body, "send_job.verify_body")):
        got, vexc = _call(verifier, body, secret or SECRET)
        if vexc is not None:
            raise Crash("roundtrip", f"{name} refuses what {who} signed: "
                        f"{_short(vexc)}")
        if got != expect:
            raise Crash("roundtrip", f"{name} reads back a payload "
                        f"{who} did not sign")
        wrong, wexc = _call(verifier, body, WRONG)
        if wexc is None:
            raise Crash("forgery", f"{name} trusts the body under the "
                        "wrong secret")
        _expect_refusal(wexc, ValueError, name + " (wrong secret)")
    keyed, kexc = _call(V.verify_body_keyed, body, SECRETS)
    if secret is None:
        if kexc is None:
            raise Crash("forgery", "verify_body_keyed trusts a body whose "
                        f"key_id {key_id!r} names no secret")
        _expect_refusal(kexc, ValueError, "verify_body_keyed")
    else:
        if kexc is not None:
            raise Crash("roundtrip", "verify_body_keyed refuses what "
                        f"{who} signed under {key_id!r}: {_short(kexc)}")
        got, chosen = keyed
        if chosen != key_id:
            raise Crash("agreement", f"verify_body_keyed chose {chosen!r} "
                        f"for a body signed under {key_id!r}")
        if _unsigned(got) != _unsigned(expect):
            raise Crash("roundtrip", "verify_body_keyed reads back a "
                        f"payload {who} did not sign")
    if isinstance(expect, dict):
        _provenance(expect)
    return "accepted"


def check_wire(entry):
    if entry["kind"] == "text":
        return _verify_text(entry["data"])
    both = (_signed_payload(entry["data"], V.sign_payload, "sign_payload"),
            _signed_payload(entry["data"], SJ.sign_payload,
                            "send_job.sign_payload"))
    if both[0] != both[1]:
        raise Crash("agreement", "the two signers disagree on whether "
                    f"the payload can be signed ({both[0]}/{both[1]})")
    return both[0]


def check_cloud(entry):
    if entry["kind"] == "text":
        return _cloud_text(entry["data"])
    return _signed_payload(entry["data"], SJ.sign_payload,
                           "send_job.sign_payload")


def check_v2(entry):
    obj = entry["data"]
    got, exc = _call(P2.validate, obj)
    if exc is not None:
        _expect_refusal(exc, ValueError, "protocol_v2.validate")
        return "refused"
    if got != obj:
        raise Crash("roundtrip", "validate returned an object other than "
                    "the one it was given")
    return "accepted"


def check_crypto(entry):
    spec = entry["data"]
    if not isinstance(spec, dict):
        raise Crash("corpus", "a crypto entry's data must be an object")
    args = (spec.get("envelope"), SECRET, spec.get("job_id"),
            spec.get("key_id"))
    got, exc = _call(JC.decrypt_body, *args)
    if exc is not None:
        _expect_refusal(exc, JC.JobCryptoError, "decrypt_body")
        if spec.get("expect") is not None:
            raise Crash("roundtrip", "decrypt_body refuses an envelope "
                        f"encrypt_body made: {_short(exc)}")
        return "refused"
    if not isinstance(got, str):
        raise Crash("shape", f"decrypt_body returned {type(got).__name__}")
    note("plain", _digest(got))
    if spec.get("expect") is not None and got != spec["expect"]:
        raise Crash("roundtrip", "decrypt_body returned a body other "
                    "than the one encrypt_body sealed")
    return "accepted"


class _LocalRig:
    """A scratch base_dir for the local-signal reader, with the
    runner's log and the Oracle wake-up quiet for the run."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="hp-bluemonday-")
        self._patches = [
            mock.patch.object(R, "log", lambda *a, **k: None),
            mock.patch.object(R, "_maybe_wake_oracle",
                              lambda *a, **k: False),
        ]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


_RIG = None


def _senses_bytes(base):
    """The senses store in one base directory, or empty when the
    directory has not filed an alert. A refusal must leave this
    untouched (Q70)."""
    path = os.path.join(base, "senses.jsonl")
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _local_neighbor():
    """One known-good alert into the same directory the entry just
    used. It must be stored, whatever the entry did. The title is
    unique for the run so a previous neighbor is not this one."""
    n = getattr(_local_neighbor, "n", 0) + 1
    _local_neighbor.n = n
    title = f"bm-neighbor-{n}"
    payload = _stamp_issued_at(_alert(
        title=title, job_id=f"bm-n-{n:08d}",
        detail={"path": "/srv/example/neighbor.txt"}))
    body, exc = _call(V.sign_payload, payload, SENSE)
    if exc is not None:
        raise Crash("exception", "the neighbor alert would not sign: "
                    f"{type(exc).__name__}: {_short(exc)}")
    got, exc = _call(R._ingest_local_envelope_inner, LOCAL_CFG,
                     _RIG.dir, body, "bluemonday-neighbor")
    if exc is not None:
        raise Crash("exception", "the neighbor alert raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if not isinstance(got, dict) or got.get("title") != title \
            or got.get("sensor") != "canary":
        raise Crash("contract", "the next good alert in the same "
                    "directory was not stored")
    if title.encode("ascii") not in _senses_bytes(_RIG.dir):
        raise Crash("contract", "the neighbor was returned but not "
                    "written to the senses store")


def _local_ingest(text):
    before = _senses_bytes(_RIG.dir)
    got, exc = _call(R._ingest_local_envelope_inner, LOCAL_CFG, _RIG.dir,
                     text, "bluemonday")
    if exc is not None:
        raise Crash("exception", "_ingest_local_envelope_inner raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if got is not None and not isinstance(got, dict):
        raise Crash("shape", "_ingest_local_envelope_inner returned "
                    f"{type(got).__name__}")
    if got is None and _senses_bytes(_RIG.dir) != before:
        raise Crash("contract", "a refused local alert stored a record")
    return "accepted" if got is not None else "refused"


def check_local(entry):
    """local: one envelope, then a known-good neighbor in the same
    directory (Q70). A refusal stores nothing. The neighbor is
    stored either way."""
    if entry["kind"] == "text":
        text = entry["data"]
        parsed, exc = _call(TR.parse_envelope, text)
        if exc is not None:
            raise Crash("exception", "parse_envelope raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if parsed is not None and not (isinstance(parsed, tuple)
                                       and len(parsed) == 2
                                       and isinstance(parsed[0], str)
                                       and isinstance(parsed[1], str)):
            raise Crash("shape", "parse_envelope returned "
                        f"{type(parsed).__name__}")
        body = parsed[1] if parsed is not None else text
        outcome = _local_ingest(body)
    else:
        payload = _stamp_issued_at(entry["data"])
        secret, _key_id = _signing_secret(payload)
        body, exc = _call(V.sign_payload, payload, secret or SECRET)
        if exc is not None:
            _expect_refusal(exc, ValueError, "sign_payload")
            outcome = "refused"
        else:
            outcome = _local_ingest(body)
    _local_neighbor()
    return outcome


def check_stash(entry):
    """stash: a stashed record {body, key_id, job_id} read back by
    _record_payload -- the signed payload, decrypted when the body
    is an envelope -- which answers a dict or None and never raises,
    whatever the record's three key slots (the body's own key_id,
    the envelope's, the record's) say to each other (Q63)."""
    rec = entry["data"]
    got, exc = _call(R._record_payload, rec, SECRETS)
    if exc is not None:
        raise Crash("exception", "_record_payload raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if got is not None and not isinstance(got, dict):
        raise Crash("shape", f"_record_payload returned {type(got).__name__}")
    return "accepted" if got is not None else "refused"


_JOB_SUBJECT = re.compile(r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)",
                          re.I)
MAILBOX = "runner@example.com"


def _email_extension():
    """The email transport extension's readers, imported once.

    The extension's script header inserts its parents onto
    sys.path so it can run as a program. The corpus is not that
    program: the insertion is undone, or the next test in the
    process inherits a path it did not set.
    """
    global _EMAIL_EXT
    if _EMAIL_EXT is None:
        import importlib
        before = list(sys.path)
        _EMAIL_EXT = importlib.import_module(
            "runner.transport_extensions.email.__main__")
        sys.path[:] = before
    return _EMAIL_EXT


_EMAIL_EXT = None


def _raw_bytes(text):
    """A mail entry's data is the raw message as text; bytes that are
    not UTF-8 ride as surrogate escapes, so the corpus can hold any
    message and give the readers the exact bytes back."""
    return text.encode("utf-8", "surrogateescape")


def check_mail(entry):
    """mail: the readers that choose the text a verifier will see,
    on one raw RFC 822 message -- the core's subject, bounce check
    and text body, the extension's own extraction of the same two
    things, and the reply-target rule. Contract: none of them
    raises; the extension reads the same subject and body as the
    core (the differential); the reply target is the mailbox or a
    single plain address from inside the body's JSON, never
    anything a header said."""
    import email
    raw = _raw_bytes(entry["data"])
    msg, exc = _call(email.message_from_bytes, raw)
    if exc is not None:
        raise Crash("exception", "email.message_from_bytes raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    subject, exc = _call(lambda: str(msg["Subject"] or ""))
    if exc is not None:
        raise Crash("exception", "the Subject header raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    bounce, exc = _call(R._bounce_of, subject, raw)
    if exc is not None:
        raise Crash("exception", f"_bounce_of raised {type(exc).__name__}: "
                    f"{_short(exc)}")
    if bounce is not None and not isinstance(bounce, str):
        raise Crash("shape", f"_bounce_of returned {type(bounce).__name__}")
    body, exc = _call(R.get_text_body, msg)
    if exc is not None:
        raise Crash("exception", "get_text_body raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if not isinstance(body, str):
        raise Crash("shape", f"get_text_body returned {type(body).__name__}")
    ext = _email_extension()
    got, exc = _call(ext._subject_body, raw)
    if exc is not None:
        raise Crash("exception", "_subject_body raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if not (isinstance(got, tuple) and len(got) == 2
            and all(isinstance(x, str) for x in got)):
        raise Crash("shape", "_subject_body returned "
                    f"{type(got).__name__}")
    if got != (subject, body):
        raise Crash("agreement", "the email extension reads a different "
                    "subject or body than the core from one message")
    target, exc = _call(ext.reply_target, body, MAILBOX)
    if exc is not None:
        raise Crash("exception", "reply_target raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if not isinstance(target, str):
        raise Crash("shape", f"reply_target returned {type(target).__name__}")
    if target != MAILBOX and (len(target) > 254
                              or not MB._REPLY_TO_RE.match(target)):
        raise Crash("contract", "reply_target returned an address that "
                    f"is neither the mailbox nor a valid reply_to: "
                    f"{target[:60]!r}")
    if target != MAILBOX and target not in body:
        raise Crash("contract", "reply_target returned an address that "
                    "is not inside the body")
    accepted = bool(_JOB_SUBJECT.search(subject)) and bool(body.strip()) \
        and bounce is None
    return "accepted" if accepted else "refused"


_DTLS_ALLOWED = (DT.DtlsError, JC.JobCryptoError)
_DTLS_ADDR = ("192.0.2.1", 4430)   # TEST-NET-1, an invented peer
_DTLS_NOW = 1_700_000_000.0
_DTLS_IDENTITY = b"bm-psk-0001"


def _dtls_text(data):
    """A datagram as corpus text: every byte, including those that
    are not UTF-8, rides as a surrogate escape."""
    return bytes(data).decode("utf-8", "surrogateescape")


def _only_dtls(fn, *args, what):
    """Run one DTLS reader. DtlsError and JobCryptoError are the
    refusal; anything else is a crash. The result is returned."""
    got, exc = _call(fn, *args)
    if exc is not None and not isinstance(exc, _DTLS_ALLOWED):
        raise Crash("exception", f"{what} raised {type(exc).__name__}: "
                    f"{_short(exc)}")
    return got


def _dtls_readers(body):
    """The handshake readers on one body: extensions, both hellos,
    the key-share and the PSK, and again on whatever a hello
    actually carried. Each may refuse; none may raise anything else."""
    _only_dtls(DT._parse_extensions, body, 0, what="_parse_extensions")
    client = _only_dtls(DT._parse_client_hello, body,
                        what="_parse_client_hello")
    server = _only_dtls(DT._parse_server_hello, body,
                        what="_parse_server_hello")
    _only_dtls(DT._key_share_entry, body, False, what="_key_share_entry")
    _only_dtls(DT._key_share_entry, body, True, what="_key_share_entry")
    _only_dtls(DT._parse_psk_extension, body, what="_parse_psk_extension")
    for fields in (client, server):
        if not isinstance(fields, dict):
            continue
        exts = fields.get("exts") or {}
        share = exts.get(DT.EXT_KEY_SHARE)
        if share is not None:
            _only_dtls(DT._key_share_entry, share, False,
                       what="_key_share_entry")
            _only_dtls(DT._key_share_entry, share, True,
                       what="_key_share_entry")
        psk = exts.get(DT.EXT_PRE_SHARED_KEY)
        if psk is not None:
            _only_dtls(DT._parse_psk_extension, psk,
                       what="_parse_psk_extension")


def _complete_handshake(parsed):
    """A whole handshake message, not a fragment and not a short
    buffer. _parse_handshake's complete form is four fields and
    its fragment form starts with the string "fragment"."""
    return (isinstance(parsed, tuple) and len(parsed) == 4
            and parsed[0] != "fragment"
            and isinstance(parsed[2], (bytes, bytearray)))


def check_dtls(entry):
    """dtls: one datagram (Q66). The splitter returns a list and
    never raises; each record goes through the handshake parser,
    which returns a parse or None and never raises; a complete
    handshake message is then handed to the extension, hello,
    key-share and PSK readers, which raise DtlsError or
    JobCryptoError and nothing else. DtlsServerCore.feed takes
    the datagram and returns datagrams, and never raises: the
    core is built in memory, with an invented secret map and no
    socket. Accepted when a complete handshake message parses,
    refused otherwise."""
    data = _raw_bytes(entry["data"])
    records, exc = _call(DT._split_records, data)
    if exc is not None:
        raise Crash("exception", "_split_records raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if not isinstance(records, list):
        raise Crash("shape", "_split_records returned "
                    f"{type(records).__name__}")
    accepted = False
    for rec in records:
        if not isinstance(rec, (bytes, bytearray)) or not rec:
            raise Crash("shape", "a split record is empty or not bytes")
        payloads = [bytes(rec)]
        if DT._is_plaintext_record(rec) and len(rec) >= 13:
            length = int.from_bytes(rec[11:13], "big")
            payloads.append(bytes(rec[13:13 + length]))
        for payload in payloads:
            parsed, exc = _call(DT._parse_handshake, payload)
            if exc is not None:
                raise Crash("exception", "_parse_handshake raised "
                            f"{type(exc).__name__}: {_short(exc)}")
            if not _complete_handshake(parsed):
                continue
            accepted = True
            _dtls_readers(bytes(parsed[2]))

    def _feed():
        core = DT.DtlsServerCore(
            secrets_map={_DTLS_IDENTITY: "bm-secret-0001"},
            rng=lambda n: b"\x5a" * n)
        return core.feed(data, _DTLS_ADDR, _DTLS_NOW)

    out, exc = _call(_feed)
    if exc is not None:
        raise Crash("exception", "DtlsServerCore.feed raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if (not isinstance(out, list)
            or not all(isinstance(dg, (bytes, bytearray)) for dg in out)):
        raise Crash("shape", "DtlsServerCore.feed returned "
                    f"{type(out).__name__}")
    return "accepted" if accepted else "refused"
_BOARD_STATUSES = {"not_found", "duplicate", "not_claimed", "pending_review",
                   "done"}
_BOARD_OPS = ("submit", "offer", "complete", "approve", "reoffer")


def check_board_ops(entry):
    """board_ops: a board file as a peer or a crash may have left it, then
    a sequence of peer operations on it -- submit(task),
    offer(worker_id, capabilities, key_id, cfg), complete(task_id,
    result, require_review), approve(task_id),
    reoffer(task_timeout) -- on a throwaway board path. Contract:
    loading never raises and leaves a dict of dict tasks, each
    carrying its key as task_id; submit and approve answer (bool,
    str); offer answers a task dict or None, and a task it hands
    out is claimed on the board under the id it carries and is a
    copy; complete answers (status, str) with a known status;
    reoffer_expired answers a count; nothing raises; the board file
    reads back as the board in memory after every step."""
    spec = entry["data"]
    if not isinstance(spec, dict):
        raise Crash("corpus", "a board_ops entry's data must be an object")
    _StepClock._tick = 0
    with mock.patch.object(BD, "log", lambda *a, **k: None), \
            mock.patch.object(BD, "vlog", lambda *a, **k: None), \
            mock.patch.object(BD, "datetime", _StepClock):
        return _board_sequence(spec)


_BOARD_CLOCKS = ("submitted_at", "claimed_at", "completed_at")


class _StepClock(datetime):
    """The board's clock for a check: one second per reading, from
    a fixed start, so a lease of zero has always expired by the
    next operation and a tie between two submissions is the same
    on every platform. A wall clock read twice in the same
    millisecond (Windows) made the same sequence answer two ways."""

    _tick = 0

    @classmethod
    def now(cls, tz=None):
        cls._tick += 1
        base = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
        when = base + timedelta(seconds=cls._tick)
        return when if tz is None else when.astimezone(tz)


def _timeless(value):
    """A board value with the clock fields taken out, so a note
    about it is the same on every run."""
    if isinstance(value, dict):
        return {k: _timeless(v) for k, v in value.items()
                if k not in _BOARD_CLOCKS}
    if isinstance(value, (list, tuple)):
        return [_timeless(v) for v in value]
    return value


def _board_sequence(spec):
    base = tempfile.mkdtemp(prefix="hp-bluemonday-board-")
    try:
        path = os.path.join(base, "board.json")
        text = spec.get("file")
        if isinstance(text, str):
            # Bytes that are not UTF-8 ride as surrogates in the
            # corpus; the board reads the file as UTF-8 and must
            # treat what does not decode as no board at all.
            with open(path, "wb") as fh:
                fh.write(text.encode("utf-8", "surrogatepass"))
        board, exc = _call(BD.Board, path)
        if exc is not None:
            raise Crash("exception", f"Board() raised {type(exc).__name__}: "
                        f"{_short(exc)}")
        if not isinstance(board.tasks, dict) or not all(
                isinstance(k, str) and isinstance(v, dict)
                for k, v in board.tasks.items()):
            raise Crash("shape", "the board loaded something other than "
                        "a dict of dict tasks")
        ops = spec.get("ops")
        if not isinstance(ops, list):
            ops = []
        accepted = False
        for op in ops:
            if not isinstance(op, list) or not op or op[0] not in _BOARD_OPS:
                continue
            name, args = op[0], op[1:]
            if name == "submit":
                got, exc = _call(board.submit, *args[:1])
                if exc is not None:
                    raise Crash("exception", "submit raised "
                                f"{type(exc).__name__}: {_short(exc)}")
                if not (isinstance(got, tuple) and len(got) == 2
                        and isinstance(got[0], bool)
                        and isinstance(got[1], str)):
                    raise Crash("shape", f"submit returned {got!r}"[:200])
                if got[0]:
                    accepted = True
                    task = args[0] if args else None
                    tid = task.get("task_id") if isinstance(task, dict) \
                        else None
                    stored = board.tasks.get(tid)
                    if not isinstance(stored, dict) \
                            or stored.get("state") != "open":
                        raise Crash("contract", "submit said ok but the "
                                    "task is not open on the board")
            elif name == "offer":
                got, exc = _call(board.offer, *args[:4])
                if exc is not None:
                    raise Crash("exception", "offer raised "
                                f"{type(exc).__name__}: {_short(exc)}")
                if got is not None:
                    if not isinstance(got, dict):
                        raise Crash("shape", "offer returned "
                                    f"{type(got).__name__}")
                    tid = got.get("task_id")
                    stored = board.tasks.get(tid)
                    if not isinstance(stored, dict) \
                            or stored.get("state") != "claimed":
                        raise Crash("contract", "offer handed out a task "
                                    "that is not claimed on the board")
                    if stored is got:
                        raise Crash("contract", "offer handed out the "
                                    "board's own task object, not a copy")
                    accepted = True
            elif name == "complete":
                got, exc = _call(board.complete, *args[:3])
                if exc is not None:
                    raise Crash("exception", "complete raised "
                                f"{type(exc).__name__}: {_short(exc)}")
                if not (isinstance(got, tuple) and len(got) == 2
                        and got[0] in _BOARD_STATUSES
                        and isinstance(got[1], str)):
                    raise Crash("shape", f"complete returned {got!r}"[:200])
                if got[0] == "done":
                    accepted = True
            elif name == "approve":
                got, exc = _call(board.approve, *args[:1])
                if exc is not None:
                    raise Crash("exception", "approve raised "
                                f"{type(exc).__name__}: {_short(exc)}")
                if not (isinstance(got, tuple) and len(got) == 2
                        and isinstance(got[0], bool)
                        and isinstance(got[1], str)):
                    raise Crash("shape", f"approve returned {got!r}"[:200])
                if got[0]:
                    accepted = True
            elif name == "reoffer":
                got, exc = _call(board.reoffer_expired, *args[:1])
                if exc is not None:
                    raise Crash("exception", "reoffer_expired raised "
                                f"{type(exc).__name__}: {_short(exc)}")
                if not isinstance(got, int) or isinstance(got, bool) \
                        or got < 0:
                    raise Crash("shape", "reoffer_expired returned "
                                f"{got!r}"[:200])
            note(name, _digest(_timeless(got)), _digest(_timeless(board.tasks)))
            again, exc = _call(BD.Board, path)
            if exc is not None:
                raise Crash("exception", "the board file no longer loads "
                            f"after {name}: {type(exc).__name__}: "
                            f"{_short(exc)}")
            if again.tasks != board.tasks and os.path.exists(path):
                # What save wrote is what load reads back.
                raise Crash("roundtrip", f"the board file after {name} "
                            "does not read back as the board in memory")
        return "accepted" if accepted else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)


_CHANNEL = "bm-chan"
_CHANNEL_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_NEIGHBOR = "zz-neighbor.job.txt"
_NEIGHBOR_SUBJECT = "[HOMING-PIGEON] job bm-neighbor-0001"
_NEIGHBOR_BODY = '{"job_id": "bm-neighbor-0001", "type": "ping"}\n'
_RESULT_SUBJECT = "[HOMING-PIGEON] result bm-result-0001"
_RESULT_BODY = '{"job_id": "bm-result-0001", "exit_code": 0}\n'
_RESULT_TARGET = "ops@example.com"


def check_inbox(entry):
    """inbox: an extension's inbox as a peer or a crash may have
    left it -- files, symlinks, directories, in the names they were
    given -- read by fetch_channel_messages and then serviced by
    service_channel, with a known-good envelope beside them. Contract:
    neither raises; every file and link in the inbox comes back as
    one message, in name order, a well-formed envelope as its
    (subject, body) from parse_envelope and anything else as the
    empty ack-only refusal; a reply lands in the outbox as an
    envelope that reads back; an ack moves the file to done; after
    the service pass the inbox holds nothing but done, every name is
    in done, and the neighbor was served and answered."""
    spec = entry["data"]
    if not isinstance(spec, dict):
        raise Crash("corpus", "an inbox entry's data must be an object")
    return _channel_sequence(spec)


_CHANNEL_MODES = ("reply", "reply2", "raise", "none", "hold", "badreply")


class _Replies(list):
    """A processor's replies as the core returns them: a sequence
    with `consume` and a `requeue` the channel runs when the
    envelope is to stay for the next cycle."""

    consume = True

    def __init__(self, calls, replies=()):
        super().__init__(replies)
        self.calls = calls

    def requeue(self):
        self.calls.append(1)


class _Held(_Replies):
    consume = False


def _channel_processor(mode, served, calls):
    """The core's side of service_channel, in one of six shapes:
    reply (a result per parsed envelope, with its target), reply2
    (the same reply as a pair, no target), raise (every callback
    fails), none (no replies), hold (consume off), badreply (a
    reply whose write raises)."""

    def process(subject, body):
        served.append((subject, body))
        if mode == "raise":
            raise RuntimeError("the processor failed")
        if mode == "none":
            return None
        if mode == "hold":
            return _Held(calls)
        if subject == "":
            return []
        if mode == "badreply":
            # A body that is not text: the outbox writer raises on
            # it, which is the reply-did-not-land path.
            return _Replies(calls, [(_RESULT_SUBJECT, 123)])
        if mode == "reply2":
            return [(_RESULT_SUBJECT, _RESULT_BODY)]
        # The reply carries the job's validated reply_to as the
        # core would pass it; the channel writes it beside the
        # result and derives none of its own (provenance).
        return [(_RESULT_SUBJECT, _RESULT_BODY, _RESULT_TARGET)]

    return process


def _channel_files(spec, reserved=("done", _NEIGHBOR)):
    """The inbox files an entry describes, in a shape the checker
    can write: (name, kind, payload) with the names that cannot be
    a file in that inbox left out."""
    out = []
    seen = set()
    for item in spec.get("files") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if (not isinstance(name, str) or not _CHANNEL_NAME_RE.match(name)
                or name in reserved or name in seen):
            continue
        seen.add(name)
        if isinstance(item.get("text"), str):
            out.append((name, "text", item["text"]))
        elif isinstance(item.get("link"), str):
            out.append((name, "link", item["link"]))
        elif item.get("dir") is True:
            out.append((name, "dir", None))
        elif isinstance(item.get("fill"), int) and not isinstance(
                item["fill"], bool) and 0 <= item["fill"] <= 2 * TR.FILE_MAX_BYTES:
            out.append((name, "fill", item["fill"]))
    return out


def _channel_sequence(spec):
    base = tempfile.mkdtemp(prefix="hp-bluemonday-chan-")
    try:
        paths = TR.ensure_channel_dirs(base, _CHANNEL)
        inbox = paths["inbox"]
        expected = {}
        dirs = ["done"]
        for name, kind, payload in _channel_files(spec):
            path = os.path.join(inbox, name)
            if kind == "text":
                raw = payload.encode("utf-8", "surrogatepass")
                with open(path, "wb") as fh:
                    fh.write(raw)
            elif kind == "fill":
                with open(path, "wb") as fh:
                    fh.write(b"x" * payload)
                raw = None
            elif kind == "dir":
                # A directory is not a message; it stays where it is.
                os.makedirs(path, exist_ok=True)
                dirs.append(name)
                continue
            else:
                try:
                    os.symlink(payload, path)
                except (OSError, NotImplementedError):
                    continue    # a platform without links: not a file
                raw = None
            expected[name] = raw
        with open(os.path.join(inbox, _NEIGHBOR), "wb") as fh:
            fh.write(TR.format_envelope(_NEIGHBOR_SUBJECT,
                                        _NEIGHBOR_BODY).encode("utf-8"))
        expected[_NEIGHBOR] = None
        logged = []

        def record(message, level="INFO"):
            logged.append(f"{level}:{message}")

        msgs, exc = _call(TR.fetch_channel_messages, base, _CHANNEL, record)
        if exc is not None:
            raise Crash("exception", "fetch_channel_messages raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if not isinstance(msgs, list):
            raise Crash("shape", "fetch_channel_messages returned "
                        f"{type(msgs).__name__}")
        idents = [getattr(m, "ident", None) for m in msgs]
        if idents != sorted(expected):
            raise Crash("contract", "the inbox holds "
                        f"{sorted(expected)!r} and the fetch returned "
                        f"{idents!r}"[:300])
        accepted = False
        for msg in msgs:
            if not (isinstance(msg.subject, str)
                    and isinstance(msg.body, str)):
                raise Crash("shape", f"{msg.ident}: subject or body is "
                            "not a string")
            note("msg", msg.ident, _digest([msg.subject, msg.body]))
            raw = expected.get(msg.ident)
            want = None
            if raw is not None and len(raw) <= TR.FILE_MAX_BYTES:
                try:
                    want = TR.parse_envelope(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    want = None
            if msg.ident == _NEIGHBOR:
                want = (_NEIGHBOR_SUBJECT, _NEIGHBOR_BODY)
            if want is None:
                if (msg.subject, msg.body) != ("", ""):
                    raise Crash("contract", f"{msg.ident}: a refusal must "
                                "be the empty message")
            else:
                if (msg.subject, msg.body) != want:
                    raise Crash("contract", f"{msg.ident}: the message is "
                                "not what parse_envelope reads")
                accepted = accepted or msg.ident != _NEIGHBOR
        # Service the same inbox with the core's side in the shape
        # the entry names: what is consumed, what stays, what lands
        # in the outbox and what is re-queued follow from it, the
        # neighbor served either way.
        mode = spec.get("mode")
        if mode not in _CHANNEL_MODES:
            mode = "reply"
        served, calls = [], []
        count, exc = _call(TR.service_channel, base, _CHANNEL,
                           _channel_processor(mode, served, calls), record)
        if exc is not None:
            raise Crash("exception", "service_channel raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if count != len(msgs):
            raise Crash("contract", f"service_channel visited {count} of "
                        f"{len(msgs)} messages")
        if (_NEIGHBOR_SUBJECT, _NEIGHBOR_BODY) not in served:
            raise Crash("contract", "the neighbor envelope was not served")
        parsed = {m.ident for m in msgs if m.subject != ""}
        if mode == "hold":
            stay = set(expected)
        elif mode == "badreply":
            stay = parsed
        else:
            stay = set()
        replying = mode in ("reply", "reply2")
        left = sorted(os.listdir(inbox))
        if left != sorted(set(dirs) | stay):
            raise Crash("contract", f"after {mode}, the inbox holds "
                        f"{left!r}, not {sorted(set(dirs) | stay)!r}"[:300])
        done = set(os.listdir(paths["inbox_done"]))
        if done != set(expected) - stay:
            raise Crash("contract", f"after {mode}, done holds "
                        f"{sorted(done)!r}"[:300])
        if len(calls) != len(stay):
            raise Crash("contract", f"after {mode}, requeue ran "
                        f"{len(calls)} times for {len(stay)} held envelopes")
        outbox = sorted(f for f in os.listdir(paths["outbox"])
                        if f.endswith(".txt"))
        targets = [f for f in outbox if f.endswith(".target.txt")]
        results = [f for f in outbox if f not in targets]
        want = len(parsed) if replying else 0
        want_targets = len(parsed) if mode == "reply" else 0
        if len(results) != want or len(targets) != want_targets:
            raise Crash("contract", f"after {mode}, {want} result files "
                        f"with {want_targets} target sidecars expected and "
                        f"{len(results)} + {len(targets)} in the outbox")
        for fname in targets:
            with open(os.path.join(paths["outbox"], fname),
                      encoding="utf-8") as fh:
                if fh.read() != _RESULT_TARGET + "\n":
                    raise Crash("provenance", f"the sidecar {fname} does not "
                                "carry the reply target it was given")
        note("after", mode, _digest([left, sorted(done), outbox, served]))
        texts = []
        for fname in results:
            with open(os.path.join(paths["outbox"], fname),
                      encoding="utf-8") as fh:
                text = fh.read()
            texts.append(text)
            back = TR.parse_envelope(text)
            if back is None or back[0] != _RESULT_SUBJECT:
                raise Crash("roundtrip", f"the result file {fname} does "
                            "not read back as the reply")
        note("log", _digest(logged))
        note("results", _digest(texts))
        return "accepted" if accepted else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)


_LOCAL_NEIGHBOR = "zz-neighbor.json"


def check_local_inbox(entry):
    """local_inbox: the local signal inbox as a peer or a crash may
    have left it -- .json envelopes, other files, symlinks, fillers,
    in the names they were given, with a known-good alert beside
    them -- scanned once by _scan_local_inbox. Contract: the scan
    never raises and answers how many .json entries it handled;
    every .json entry is handled once and removed either way, a
    symlink or a file that is not UTF-8 without an ingest call, a
    file that decodes with one call carrying its text (at most the
    size cap plus one byte); anything not named .json is left
    alone; the ingest answers a record or None and never raises;
    the store holds exactly the records the ingests answered, in
    inbox order, the neighbor's among them whatever came before."""
    spec = entry["data"]
    if not isinstance(spec, dict):
        raise Crash("corpus", "a local_inbox entry's data must be an object")
    return _local_inbox_sequence(spec)


def _local_inbox_sequence(spec):
    base = tempfile.mkdtemp(prefix="hp-bluemonday-lin-")
    try:
        inbox = os.path.join(base, R.LOCAL_INBOX_DIRNAME)
        os.makedirs(inbox)
        expected = {}      # name -> the text the ingest must see, or None
        stays = set()
        cap = R._LOCAL_ENVELOPE_MAX_BYTES
        for name, kind, payload in _channel_files(spec, (_LOCAL_NEIGHBOR,)):
            path = os.path.join(inbox, name)
            if kind == "text":
                if payload == "@alert":
                    # A live alert, signed at check time: the store's
                    # path needs a fresh issued_at.
                    payload = V.sign_payload(_stamp_issued_at(_alert(
                        job_id="bm-" + name[:-5].replace(".", "-"),
                        title="alert " + name)), SENSE)
                raw = payload.encode("utf-8", "surrogatepass")
            elif kind == "fill":
                raw = b"x" * payload
            elif kind == "dir":
                os.makedirs(path, exist_ok=True)
                stays.add(name)
                continue
            else:
                try:
                    os.symlink(payload, path)
                except (OSError, NotImplementedError):
                    continue
                if name.endswith(".json"):
                    expected[name] = None
                else:
                    stays.add(name)
                continue
            with open(path, "wb") as fh:
                fh.write(raw)
            if not name.endswith(".json"):
                stays.add(name)
                continue
            try:
                expected[name] = raw[:cap + 1].decode("utf-8")
            except UnicodeDecodeError:
                expected[name] = None
        good = V.sign_payload(_stamp_issued_at(_alert(
            job_id="bm-neighbor-0001", title="neighbor")), SENSE)
        with open(os.path.join(inbox, _LOCAL_NEIGHBOR), "w",
                  encoding="utf-8") as fh:
            fh.write(good)
        expected[_LOCAL_NEIGHBOR] = good
        calls = []
        inner = R._ingest_local_envelope_inner

        def recording(cfg, base_dir, text, source):
            got, exc = _call(inner, cfg, base_dir, text, source)
            calls.append((text, got, exc))
            if exc is not None:
                raise exc
            return got

        with _LocalRig() as rig, \
                mock.patch.object(R, "_ingest_local_envelope_inner",
                                  recording):
            del rig  # the patches are what the rig is for here
            count, exc = _call(R._scan_local_inbox, LOCAL_CFG, base)
        if exc is not None:
            raise Crash("exception", "_scan_local_inbox raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if count != len(expected):
            raise Crash("contract", f"the scan handled {count} of "
                        f"{len(expected)} .json entries")
        for text, got, exc in calls:
            if exc is not None:
                raise Crash("exception", "_ingest_local_envelope_inner "
                            f"raised {type(exc).__name__}: {_short(exc)}")
            if got is not None and not isinstance(got, dict):
                raise Crash("shape", "_ingest_local_envelope_inner returned "
                            f"{type(got).__name__}")
        want = [expected[n] for n in sorted(expected) if expected[n] is not None]
        if [c[0] for c in calls] != want:
            raise Crash("contract", f"the ingest saw {len(calls)} envelopes, "
                        f"the inbox held {len(want)} it could read")
        left = sorted(os.listdir(inbox))
        if left != sorted(stays):
            raise Crash("contract", f"after the scan the inbox holds "
                        f"{left!r}, not {sorted(stays)!r}"[:300])
        stored = R._senses.load_alerts(base, limit=10000)
        filed = [got for _t, got, _e in calls if got is not None]
        if not any(r.get("title") == "neighbor" for r in filed):
            raise Crash("contract", "the neighbor alert was not filed")
        if [r.get("title") for r in stored] != [r.get("title") for r in filed]:
            raise Crash("contract", f"the store holds {len(stored)} records "
                        f"and the ingests filed {len(filed)}")
        note("scan", count, _digest([c[0] for c in calls]),
             _digest([r.get("title") for r in filed]), _digest(sorted(left)))
        return "accepted" if len(filed) > 1 else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def check_secret(entry):
    """secret: one candidate shared secret, as text, before the two
    strength rules that must stay in step (send_job.py's comment):
    the sender's require_signable_secret refuses with ValueError and
    nothing else, the runner's validate_shared_secret with
    RuntimeError and nothing else, and the two agree -- both refuse,
    naming the same fault, or both accept; the two entropy estimates
    are one number."""
    secret = entry["data"]
    sender, sexc = _call(SJ.require_signable_secret, secret)
    if sexc is not None:
        _expect_refusal(sexc, ValueError, "require_signable_secret")
    runner_, rexc = _call(SEC.validate_shared_secret, secret)
    if rexc is not None:
        _expect_refusal(rexc, RuntimeError, "validate_shared_secret")
    if (sexc is None) != (rexc is None):
        raise Crash("agreement", "the sender and the runner disagree on "
                    f"the secret: {_short(sexc or rexc)}")
    if sexc is not None:
        fault = [_fault(str(sexc)), _fault(str(rexc))]
        if fault[0] != fault[1]:
            raise Crash("agreement", "the sender and the runner refuse the "
                        f"secret for different faults: {fault}")
    bits = (_call(SJ._estimate_secret_entropy, secret)[0],
            _call(SEC._estimate_secret_entropy, secret)[0])
    if bits[0] != bits[1]:
        raise Crash("agreement", f"the two entropy estimates differ: {bits}")
    note("bits", round(bits[0] or 0.0, 3))
    return "accepted" if sexc is None else "refused"


def _fault(message):
    """The fault a refusal names, without the hint that follows it:
    'placeholder', 'repeats', 'bits', or 'required'."""
    text = message.lower()
    for word in ("placeholder", "repeats", "bits", "required"):
        if word in text:
            return word
    return text[:60]


# ------------------------------------------------------------------
# Seeds: suite-style fixtures, invented names only
# ------------------------------------------------------------------

def _job(kind="exec", **extra):
    payload = {"v": 1, "type": "job", "job_id": "bm-" + kind + "-0001",
               "issued_at": FIXED_AT, "kind": kind}
    payload.update(extra)
    return payload


def _alert(**extra):
    payload = build_sensor_alert(
        "canary", "high", "tripwire", signal="canary.changed",
        detail={"path": "/srv/example/watched.txt"}, key_id="canary-key",
        job_id="bm-alert-0001")
    payload["issued_at"] = NOW
    payload.update(extra)
    return payload


def _frozen_alert():
    payload = _alert()
    payload["issued_at"] = FIXED_AT
    return payload


def _v2(kind):
    base = {"v": 2, "type": kind, "job_id": "bm-job-0001",
            "msg_id": "bm-msg-0001", "issued_at": FIXED_AT}
    if kind == "determination":
        base.update({"clean_pass": False, "expect": "proceed",
                     "why": "the verifier said so"})
    elif kind == "question":
        base.update({"question": "which path", "deadline_sec": 5,
                     "local_default": "the quiet one",
                     "context": [{"text": "a line of context"}]})
    else:
        base.update({"question_id": "bm-msg-0000", "answer": "the left"})
    return base


def _payload_seeds():
    return [
        ("exec_job", _job(script="echo hello", shell="sh")),
        ("exec_job_keyed", _job(key_id="ops", script="true")),
        ("alert", _frozen_alert()),
        ("unknown_key", _job(key_id="nobody")),
        ("null_key", _job(key_id=None)),
        ("empty_key", _job(key_id="")),
        ("own_sig_member", _job(sig="0" * 96)),
        ("unicode", _job(title="café — 中文 \U0001f426")),
        ("escapes", _job(note="a\"quote\\slash\nnewline\ttab")),
        ("nested", _job(detail={"a": [1, 2.5, None, True, {"b": []}]})),
        ("nested_sig", _job(detail={"v": 1, "key_id": "ops",
                                    "sig": "0" * 96})),
        ("nested_sig_outer_ops",
         _job(key_id="ops", detail={"v": 1, "sig": "f" * 96})),
        ("empty", {}),
        ("big_int", _job(size=2 ** 63)),
        # Keys and values made of the JSON delimiters themselves: the
        # brace walk's hardest shape (Q61, Q65).
        ("brace_quote_keys", _job(detail={"{": {"\"": "}"}, "a\"b": "{\"}",
                                          "\\": "\\{"})),
        ("brace_key_at_top", {"v": 1, "type": "job", "{": "x", "\"}": "{",
                              "job_id": "bm-brace-0001",
                              "issued_at": FIXED_AT, "kind": "exec"}),
        # Provenance: where the result goes is read from the signed
        # body alone, one plain address or nothing.
        ("reply_to", _job(reply_to="ops@example.com")),
        ("reply_to_padded", _job(reply_to="  ops@example.com\t")),
        ("reply_to_named", _job(reply_to="Ops <ops@example.com>")),
        ("reply_to_two", _job(reply_to="a@example.com, b@example.com")),
        ("reply_to_header_line", _job(reply_to="ops@example.com\nBcc: x@example.com")),
        ("reply_to_no_tld", _job(reply_to="ops@example")),
        ("reply_to_long", _job(reply_to="o" * 250 + "@example.com")),
        ("reply_to_254", _job(reply_to="o" * 242 + "@example.com")),
        ("reply_to_255", _job(reply_to="o" * 243 + "@example.com")),
        ("reply_to_unicode", _job(reply_to="öps@example.com")),
        ("reply_to_not_text", _job(reply_to=["ops@example.com"])),
        ("reply_to_mailbox", _job(reply_to="runner@example.com")),
        # The version 1 draft's job (Section 11), invented ids, and
        # the identifier boundaries its ABNF states: 128, 129, ".", "..".
        ("draft_exec", _job(
            job_id="bm-draft-0001", script="date\n", timeout_sec=60,
            key_id="", reply_to="submitter@example.com",
            runner_id="bm-runner",
            script_sha384="f" * 96)),
        ("draft_job_id_cap", _job(job_id="d" * 128)),
        ("draft_job_id_over", _job(job_id="d" * 129)),
        ("draft_job_id_dot", _job(job_id=".")),
        ("draft_job_id_dotdot", _job(job_id="..")),
    ] + _draft_examples("draft-homing-pigeon-00.md")


def _draft_examples(name):
    """The JSON examples of one draft, from the dictionary, as
    (name, value) seeds with the stale issued_at the draft prints
    (the window refuses it; the signature path still runs)."""
    out = []
    for ex in grammar().get("examples") or []:
        src = ex.get("from", "")
        if src.startswith(name) and isinstance(ex.get("value"), dict):
            out.append(("draft_" + src.split("#")[-1], ex["value"]))
    return out


def _pretty_signed(payload):
    """A body signed in its pretty-printed form: the newlines are
    inside the signature, so both verifiers take it raw."""
    import hashlib as _h
    import hmac as _hmac
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    sig = _hmac.new(SECRET.encode("utf-8"), body.encode("utf-8"),
                    _h.sha384).hexdigest()
    return body[:-1] + ',"sig":"' + sig + '"}'


def _text_bodies():
    """Received forms of signed bodies: the mail path's wrappings."""
    exec_body = V.sign_payload(_job(script="echo hello"), SECRET)
    keyed_body = V.sign_payload(_job(key_id="ops"), OPS)
    alert_body = V.sign_payload(_frozen_alert(), SENSE)
    out = [
        ("compact", exec_body),
        ("keyed", keyed_body),
        ("alert", alert_body),
        ("crlf", exec_body.replace(",", ",\r\n", 2) + "\r\n"),
        ("preamble", "On Monday the connector wrote:\n\n" + exec_body),
        ("trailer", exec_body + "\n\n-- \nsent from an example client\n"),
        ("quoted", "> " + exec_body + "\n> \n"),
        ("control", exec_body[:40] + "\x0b" + exec_body[40:]),
        ("upper_sig", exec_body[:-98] + exec_body[-98:].upper()),
        ("two_objects", "{\"v\":0}\n" + exec_body),
        ("brace_in_string",
         V.sign_payload(_job(script="x = '{'"), SECRET)),
        ("pretty_signed", _pretty_signed(_job(script="echo pretty"))),
        ("brace_quote_signed",
         V.sign_payload(_job(detail={"{": {"\"": "}"}, "a\"b": "{\"}"}),
                        SECRET)),
        ("no_marker", json.dumps(_job())),
        ("short_tail", exec_body[:-10] + "\"}"),
        ("pretty", json.dumps(_job(), indent=2)),
        ("empty", ""),
        # The survivors' lines (section 8, step 5): the marker at
        # the very start, the tail one short and one long, a tail
        # closed by the wrong character, a sig of 95 hex and one
        # with a non-hex digit, an empty object signed (the opener
        # is the character before the marker), a brace-balanced
        # candidate that is not JSON (the walk's first candidate
        # is handed on), an object closed twice, a nested object
        # before the marker, a tab in a string, a control
        # character in a string.
        ("marker_first", ',"sig":"' + "0" * 96 + '"}'),
        ("tail_97", exec_body[:-1]),
        ("tail_99", exec_body + "}"),
        ("tail_bracket", exec_body[:-1] + "]"),
        ("sig_95", exec_body[:-98] + exec_body[-97:]),
        ("sig_not_hex", exec_body[:-98] + "g" + exec_body[-97:]),
        ("empty_object_signed", V.sign_payload({}, SECRET)),
        ("one_member_signed", V.sign_payload({"x": 1}, SECRET)),
        ("walk_not_json", '{"v": 1, "x": ,"sig":"' + "0" * 96 + '"}'),
        ("closed_twice", exec_body[:-98] + "}" + exec_body[-98:]),
        ("nested_before_marker",
         V.sign_payload(_job(detail={"inner": {"deep": {}}}), SECRET)),
        ("tab_in_string", V.sign_payload(_job(script="a\tb"), SECRET)),
        ("control_in_string",
         exec_body.replace('"script"', '"scr\x01ipt"', 1)),
        ("bom", "﻿" + exec_body),
        ("wrong_secret", V.sign_payload(_job(), WRONG)),
        # The draft's subject: a decoration word, then job, then the id.
        ("draft_subject",
         "[HOMING-PIGEON] TEST job bm-draft-0001\n\n"
         + V.sign_payload(_job(job_id="bm-draft-0001", script="date\n"),
                          SECRET)),
    ]
    # The live capture's shape (docs/reports/live-2026-10-25/),
    # rebuilt. Invented ids, the corpus secret, a fixed nonce.
    # Not the capture's own bytes: those were sealed under the
    # rig's secret.
    with _FixedNonces():
        job_inner = V.sign_payload(
            _job(job_id="bm-live-0001", script="true"), SECRET)
        result_inner = V.sign_payload(
            {"v": 1, "type": "result", "job_id": "bm-live-0001",
             "kind": "exec", "exit_code": 0}, SECRET)
        out.append(("live_job", TR.format_envelope(
            "[HOMING-PIGEON] job bm-live-0001",
            JC.encrypt_body(job_inner, SECRET, "bm-live-0001", "",
                            V.sign_payload))))
        out.append(("live_result", TR.format_envelope(
            "[HOMING-PIGEON] result bm-live-0001",
            JC.encrypt_body(result_inner, SECRET, "bm-live-0001", "",
                            V.sign_payload))))
    return out


def seeds_wire():
    return ([make_entry("text", t, "seed:" + n, "seed")
             for n, t in _text_bodies()]
            + [make_entry("payload", p, "seed:" + n, "seed")
               for n, p in _payload_seeds()])


seeds_cloud = seeds_wire


def seeds_v2():
    out = [("determination", _v2("determination")),
           ("question", _v2("question")),
           ("answer", _v2("answer"))]
    q = _v2("question")
    q["context"] = [{"text": "l%d" % i} for i in range(8)]
    out.append(("context_full", q))
    q = _v2("question")
    q["deadline_sec"] = P2._DEADLINE_CAP
    out.append(("deadline_cap", q))
    q = _v2("question")
    del q["context"]
    out.append(("no_context", q))
    d = _v2("determination")
    d["expect"] = "unknown"
    out.append(("expect_unknown", d))
    # The version 2 draft's own examples and the caps it states:
    # why 500, deadline 30, local_default 64.
    d = _v2("determination")
    d.update({"job_id": "bm-draft-0017", "msg_id": "d.bm-draft-0017",
              "expect": "fail",
              "why": "the script references /srv/example/missing"})
    out.append(("draft_determination", d))
    d = _v2("determination")
    d["why"] = "w" * 500
    out.append(("draft_why_cap", d))
    d = _v2("determination")
    d["why"] = "w" * 501
    out.append(("draft_why_over", d))
    q = _v2("question")
    q.update({"job_id": "bm-draft-0017", "msg_id": "q.bm-draft-0017",
              "deadline_sec": 15,
              "question": "Would this job succeed on this host?",
              "local_default": "proceed"})
    out.append(("draft_question", q))
    q = _v2("question")
    q["deadline_sec"] = 31
    out.append(("draft_deadline_over", q))
    q = _v2("question")
    q["local_default"] = "p" * 65
    out.append(("draft_default_over", q))
    out += [("v1", {"v": 1, "type": "answer"}), ("empty", {}),
            ("list", []), ("string", "answer"), ("none", None),
            ("number", 2)]
    # The boundaries the survivors named (section 8, step 5): each
    # cap at itself and one past it, the floor at itself and one
    # below, so a reader off by one at any of them is told apart.
    for n in (-1, 0, P2._DEADLINE_CAP + 1):
        q = _v2("question")
        q["deadline_sec"] = n
        out.append((f"deadline_{n}", q))
    for n in (P2._TEXT_CAP, P2._TEXT_CAP + 1):
        q = _v2("question")
        q["question"] = "q" * n
        out.append((f"question_{n}", q))
        a = _v2("answer")
        a["answer"] = "a" * n
        out.append((f"answer_{n}", a))
        q = _v2("question")
        q["context"] = [{"text": "c" * n}]
        out.append((f"segment_{n}", q))
    for n in (64, 65):
        q = _v2("question")
        q["local_default"] = "d" * n
        out.append((f"default_{n}", q))
    q = _v2("question")
    q["context"] = [{"text": "l%d" % i} for i in range(9)]
    out.append(("context_over", q))
    q = _v2("question")
    q["context"] = []
    out.append(("context_empty", q))
    for name, v in (("v_true", True), ("v_text", "2"), ("v_float", 2.0),
                    ("v_one", 1)):
        q = _v2("question")
        q["v"] = v
        out.append((name, q))
    q = _v2("question")
    q["type"] = "job"
    out.append(("type_job", q))
    a = _v2("answer")
    a["type"] = "result"
    out.append(("type_result_answer_shape", a))
    q = _v2("question")
    q["issued_at"] = "2026-10-26T12:00:00+00:00"
    out.append(("issued_offset", q))
    d = _v2("determination")
    d["clean_pass"] = True
    out.append(("clean_pass_sent", d))
    out += _draft_examples("draft-homing-pigeon-v2-00.md")
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


class _FixedNonces:
    """encrypt_body draws its nonce from secrets.token_bytes; the
    seeds draw from a counter instead, so a seed's id is the same on
    every run and `seed` can tell an old seed from a new one."""

    def __init__(self):
        self.n = 0

    def __call__(self, size):
        self.n += 1
        return hashlib.sha256(b"bluemonday-nonce-%d" % self.n).digest()[:size]

    def __enter__(self):
        self._patch = mock.patch.object(JC.secrets, "token_bytes", self)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        return False


def seeds_crypto():
    with _FixedNonces():
        return _seeds_crypto()


def _seeds_crypto():
    inner = V.sign_payload(_job(script="echo sealed"), SECRET)
    sealed = V.verify_body(JC.encrypt_body(inner, SECRET, "bm-exec-0001",
                                           "", V.sign_payload), SECRET)
    keyed_inner = V.sign_payload(_job(key_id="ops"), OPS)
    keyed = V.verify_body(JC.encrypt_body(keyed_inner, SECRET, "bm-exec-0001",
                                          "ops", V.sign_payload), SECRET)
    out = [
        ("sealed", {"envelope": sealed, "job_id": "bm-exec-0001",
                    "key_id": "", "expect": inner}),
        ("keyed", {"envelope": keyed, "job_id": "bm-exec-0001",
                   "key_id": "ops", "expect": keyed_inner}),
        ("other_job", {"envelope": sealed, "job_id": "bm-exec-0002",
                       "key_id": ""}),
        ("other_key", {"envelope": sealed, "job_id": "bm-exec-0001",
                       "key_id": "ops"}),
        ("not_envelope", {"envelope": _job(), "job_id": "bm-exec-0001",
                          "key_id": ""}),
        ("extra_member", {"envelope": dict(sealed, note="x"),
                          "job_id": "bm-exec-0001", "key_id": ""}),
        ("none", {"envelope": None, "job_id": None, "key_id": None}),
    ]
    # Key slots that disagree (Q63): the body under one key, the
    # envelope's AAD and member under another, each alone and paired.
    crossed = V.verify_body(JC.encrypt_body(keyed_inner, SECRET,
                                            "bm-exec-0001", "",
                                            V.sign_payload), SECRET)
    out.append(("body_ops_envelope_default",
                {"envelope": crossed, "job_id": "bm-exec-0001",
                 "key_id": "", "expect": keyed_inner}))
    crossed = V.verify_body(JC.encrypt_body(inner, SECRET, "bm-exec-0001",
                                            "ops", V.sign_payload), SECRET)
    out.append(("body_default_envelope_ops",
                {"envelope": crossed, "job_id": "bm-exec-0001",
                 "key_id": "ops", "expect": inner}))
    out.append(("member_ops_aad_default",
                {"envelope": keyed, "job_id": "bm-exec-0001", "key_id": ""}))
    out.append(("member_default_aad_gone",
                {"envelope": sealed, "job_id": "bm-exec-0001",
                 "key_id": "gone"}))
    enc = dict(sealed)
    enc["hp_enc"] = dict(sealed["hp_enc"], alg="none")
    out.append(("alg", {"envelope": enc, "job_id": "bm-exec-0001",
                        "key_id": ""}))
    enc = dict(sealed)
    enc["hp_enc"] = dict(sealed["hp_enc"], ct="AAAA")
    out.append(("short_ct", {"envelope": enc, "job_id": "bm-exec-0001",
                             "key_id": ""}))
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def seeds_local():
    alert = _alert()
    body = V.sign_payload(_frozen_alert(), SENSE)
    texts = [
        ("alert_frozen", body),
        ("envelope", TR.format_envelope("sensor alert", body)),
        ("envelope_crlf", "subject\r\n\r\n" + body + "\r\n"),
        ("no_blank_line", "subject\n" + body),
        ("exec_job", V.sign_payload(_job(script="true"), SECRET)),
        ("default_key_alert",
         V.sign_payload(dict(_frozen_alert(), key_id=""), SECRET)),
        ("unknown_key", V.sign_payload(dict(_frozen_alert(), key_id="gone"),
                                       SENSE)),
        ("empty", ""),
        ("spaces", "   \n\t"),
        ("not_json", "hello pigeon"),
    ]
    with _FixedNonces():
        job_inner = V.sign_payload(
            _job(job_id="bm-live-0001", script="true"), SECRET)
        texts.append(("live_job", TR.format_envelope(
            "[HOMING-PIGEON] job bm-live-0001",
            JC.encrypt_body(job_inner, SECRET, "bm-live-0001", "",
                            V.sign_payload))))
    payloads = [
        ("alert_now", alert),
        ("alert_low", dict(alert, severity="low")),
        ("alert_no_signal", {k: v for k, v in alert.items()
                             if k != "signal"}),
        ("alert_unknown_sensor", dict(alert, sensor="nobody")),
        ("alert_ops_key", dict(alert, key_id="ops")),
        ("alert_future", dict(alert, issued_at="2099-01-01T00:00:00Z")),
        ("alert_naive", dict(alert, issued_at="2026-10-26T12:00:00")),
        ("alert_v2", dict(alert, v=2)),
        ("alert_api_version", dict(alert, api_version=99)),
        ("alert_bad_id", dict(alert, job_id="../x")),
    ]
    return ([make_entry("text", t, "seed:" + n, "seed") for n, t in texts]
            + [make_entry("payload", p, "seed:" + n, "seed")
               for n, p in payloads])


def seeds_stash():
    with _FixedNonces():
        return _seeds_stash()


def _seeds_stash():
    """Records with their three key slots agreeing and disagreeing:
    the body's own key_id member, the envelope's (the AAD and the
    member), and the record's. Q63's family, each alone and paired."""
    plain = V.sign_payload(_job(script="echo stashed"), SECRET)
    plain_ops = V.sign_payload(_job(key_id="ops"), OPS)
    plain_gone = V.sign_payload(_job(key_id="gone"), SECRET)

    def sealed(inner, key_id, secret):
        return JC.encrypt_body(inner, secret, "bm-exec-0001", key_id,
                               V.sign_payload)

    def rec(body, key_id, job_id="bm-exec-0001"):
        return {"body": body, "key_id": key_id, "job_id": job_id}

    out = [
        ("plain_default", rec(plain, "")),
        ("plain_ops", rec(plain_ops, "ops")),
        ("plain_record_gone", rec(plain, "gone")),
        ("plain_body_gone", rec(plain_gone, "")),
        ("sealed_default", rec(sealed(plain, "", SECRET), "")),
        ("sealed_ops", rec(sealed(plain_ops, "ops", OPS), "ops")),
        ("sealed_record_gone", rec(sealed(plain, "", SECRET), "gone")),
        ("sealed_envelope_gone", rec(sealed(plain, "gone", SECRET), "")),
        ("sealed_body_gone", rec(sealed(plain_gone, "", SECRET), "")),
        ("sealed_body_ops_envelope_default",
         rec(sealed(plain_ops, "", SECRET), "")),
        ("sealed_body_default_envelope_ops",
         rec(sealed(plain, "ops", OPS), "ops")),
        ("sealed_record_none", {"body": sealed(plain, "", SECRET),
                                "key_id": None, "job_id": None}),
        ("sealed_other_job", rec(sealed(plain, "", SECRET), "",
                                 "bm-exec-0002")),
        ("no_body", {"key_id": "", "job_id": "bm-exec-0001"}),
        ("body_not_text", rec(7, "")),
        ("empty", rec("", "")),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def _mail(subject, body, *, headers=(), multipart=False,
          attachment=None, nested=False, encoding=None):
    """One RFC 822 message as text, built by hand so the shapes are
    the shapes a provider delivers: the Subject, an invented sender
    and recipient, a Message-ID, then the body as a single part, a
    multipart/alternative, a multipart with an attachment, or a
    part nested one level down."""
    lines = ["From: Sender <sender@example.com>",
             "To: Runner <runner@example.com>",
             "Message-ID: <bm-0001@example.com>",
             "Date: Mon, 26 Oct 2026 12:00:00 +0000",
             "Subject: " + subject, "MIME-Version: 1.0"]
    lines.extend(headers)
    if not multipart and attachment is None and not nested:
        if encoding == "base64":
            import base64
            lines.append("Content-Type: text/plain; charset=utf-8")
            lines.append("Content-Transfer-Encoding: base64")
            data = base64.b64encode(body.encode("utf-8")).decode("ascii")
            return "\r\n".join(lines) + "\r\n\r\n" + data + "\r\n"
        lines.append("Content-Type: text/plain; charset=utf-8")
        return "\r\n".join(lines) + "\r\n\r\n" + body + "\r\n"
    boundary = "bm-boundary-0001"
    lines.append(f'Content-Type: multipart/mixed; boundary="{boundary}"')
    parts = []
    if nested:
        inner = "bm-boundary-0002"
        parts.append(f'Content-Type: multipart/alternative; '
                     f'boundary="{inner}"\r\n\r\n--{inner}\r\n'
                     f'Content-Type: text/plain; charset=utf-8\r\n\r\n'
                     f'{body}\r\n--{inner}\r\n'
                     f'Content-Type: text/html\r\n\r\n<p>{body}</p>'
                     f'\r\n--{inner}--\r\n')
    else:
        parts.append("Content-Type: text/plain; charset=utf-8\r\n\r\n"
                     + body + "\r\n")
        if multipart:
            parts.append("Content-Type: text/html\r\n\r\n<p>" + body
                         + "</p>\r\n")
    if attachment is not None:
        parts.append('Content-Type: application/octet-stream\r\n'
                     'Content-Disposition: attachment; filename="a.bin"\r\n'
                     'Content-Transfer-Encoding: base64\r\n\r\n'
                     + attachment + "\r\n")
    text = "\r\n".join(lines) + "\r\n\r\n"
    for part in parts:
        text += f"--{boundary}\r\n" + part
    return text + f"--{boundary}--\r\n"


def seeds_mail():
    signed = V.sign_payload(_job(script="echo mail"), SECRET)
    with_reply = V.sign_payload(_job(reply_to="ops@example.com"), SECRET)
    subject = "[HOMING-PIGEON] job bm-exec-0001"
    out = [
        ("plain", _mail(subject, signed)),
        ("multipart", _mail(subject, signed, multipart=True)),
        ("nested", _mail(subject, signed, nested=True)),
        ("attachment", _mail(subject, signed, attachment="AAEC")),
        ("base64_body", _mail(subject, signed, encoding="base64")),
        ("truncated_base64", _mail(subject, signed,
                                   attachment="AAECAwQFBgcICQ")),
        ("encoded_word_subject",
         _mail("=?utf-8?q?=5BHOMING-PIGEON=5D_job_bm-exec-0001?=", signed)),
        ("encoded_word_b64",
         _mail("=?utf-8?b?W0hPTUlORy1QSUdFT05dIGpvYiBibS1leGVjLTAwMDE=?=",
               signed)),
        ("duplicate_headers",
         _mail(subject, signed,
               headers=["Subject: [HOMING-PIGEON] job bm-exec-0002",
                        "Content-Type: text/html"])),
        ("reply_to_inside", _mail(subject, with_reply)),
        ("reply_to_header_only",
         _mail(subject, signed, headers=["Reply-To: spoof@example.net"])),
        ("result_subject",
         _mail("[HOMING-PIGEON] result bm-exec-0001", signed)),
        ("bounce_subject",
         _mail("Undeliverable: [HOMING-PIGEON] result bm-exec-0001",
               "The message could not be delivered.")),
        ("bounce_report",
         _mail("Returned mail", "delivery-status",
               headers=["Content-Type: multipart/report; "
                        "report-type=delivery-status; boundary=\"x\""])),
        ("no_subject", _mail("", signed)),
        ("empty_body", _mail(subject, "")),
        ("latin1_bytes", _mail(subject, signed) + "\udce9\udce8\r\n"),
        ("preamble_and_quote",
         _mail(subject, "On Monday the connector wrote:\n\n> " + signed)),
        ("not_mail", "just some text, no headers at all"),
        ("empty", ""),
    ]
    return [make_entry("text", t, "seed:" + n, "seed") for n, t in out]


def _dtls_fragment(message, off, chunk):
    """One handshake fragment of `message`, in the header shape
    `_hs_message` writes: total length, then this piece's offset
    and length."""
    msg_type = message[0]
    total = int.from_bytes(message[1:4], "big")
    msg_seq = int.from_bytes(message[4:6], "big")
    return (bytes([msg_type]) + total.to_bytes(3, "big")
            + msg_seq.to_bytes(2, "big") + off.to_bytes(3, "big")
            + len(chunk).to_bytes(3, "big") + chunk)


def _dtls_flight():
    """A sealed flight from the module's own constructors, under
    invented keys: a ClientHello carrying a key share and a PSK
    extension, a ServerHello, and a Finished sealed for epoch 2.
    Returns the three datagrams."""
    public = b"\x42" * 32
    share = (DT.GROUP_X25519.to_bytes(2, "big")
             + (32).to_bytes(2, "big") + public)
    shares = len(share).to_bytes(2, "big") + share
    # The reader's own parse is what the seed claims to be.
    group, got = DT._key_share_entry(shares)
    if (group, got) != (DT.GROUP_X25519, public):
        raise RuntimeError("dtls seed key share did not parse back")
    identity = _DTLS_IDENTITY
    id_entry = (len(identity).to_bytes(2, "big") + identity
                + (0).to_bytes(4, "big"))
    psk = (len(id_entry).to_bytes(2, "big") + id_entry
           + bytes([1 + DT.HASH_LEN]) + bytes([DT.HASH_LEN])
           + b"\x11" * DT.HASH_LEN)
    identities, binders = DT._parse_psk_extension(psk)
    if identities != [identity] or len(binders) != 1:
        raise RuntimeError("dtls seed PSK extension did not parse back")
    extensions = DT._extensions_bytes([
        (DT.EXT_KEY_SHARE, shares),
        (DT.EXT_PSK_MODES, bytes([1, DT.PSK_MODE_DHE_KE])),
        (DT.EXT_PRE_SHARED_KEY, psk),
    ])
    hello_body = (DT.LEGACY_VERSION.to_bytes(2, "big") + b"\x22" * 32
                  + b"\x00" + b"\x00"
                  + (2).to_bytes(2, "big")
                  + DT.SUITE_AES256.to_bytes(2, "big")
                  + b"\x01\x00" + extensions)
    hello = DT._hs_message(DT.HS_CLIENT_HELLO, hello_body, 0)
    server_share = (DT.GROUP_X25519.to_bytes(2, "big")
                    + (32).to_bytes(2, "big") + b"\x43" * 32)
    server_body = (DT.LEGACY_VERSION.to_bytes(2, "big") + b"\x44" * 32
                   + b"\x00" + DT.SUITE_AES256.to_bytes(2, "big")
                   + b"\x00" + DT._extensions_bytes([
                       (DT.EXT_SUPPORTED_VERSIONS,
                        DT.DTLS_1_3.to_bytes(2, "big")),
                       (DT.EXT_KEY_SHARE, server_share),
                       (DT.EXT_PRE_SHARED_KEY, (0).to_bytes(2, "big")),
                   ]))
    server = DT._hs_message(DT.HS_SERVER_HELLO, server_body, 0)
    finished = DT._hs_message(DT.HS_FINISHED, b"\x66" * DT.HASH_LEN, 1)
    sealer = DT._RecordSealer(b"\x55" * DT.HASH_LEN)
    sealed = sealer.seal(2, DT.CT_HANDSHAKE, finished, cid=b"bm01")
    client_dg = DT._plaintext_record(DT.CT_HANDSHAKE, 0, 0, hello)
    server_dg = DT._plaintext_record(DT.CT_HANDSHAKE, 0, 1, server)
    return hello, client_dg, server_dg, sealed


def seeds_dtls():
    """One datagram per entry (Q66): the flight's three datagrams,
    the two-fragment pair of the ClientHello, an empty datagram,
    and a plaintext record whose length field claims more bytes
    than the datagram holds. Invented names and keys only."""
    hello, client_dg, server_dg, sealed = _dtls_flight()
    mid = len(hello[12:]) // 2
    body = hello[12:]
    frag_a = _dtls_fragment(hello, 0, body[:mid])
    frag_b = _dtls_fragment(hello, mid, body[mid:])
    overrun = bytearray(DT._plaintext_record(DT.CT_HANDSHAKE, 0, 2, b"bm"))
    overrun[11:13] = (len(overrun) + 40).to_bytes(2, "big")
    out = [
        ("client_hello", client_dg),
        ("server_hello", server_dg),
        ("finished", sealed),
        ("fragment_a", DT._plaintext_record(DT.CT_HANDSHAKE, 0, 3, frag_a)),
        ("fragment_b", DT._plaintext_record(DT.CT_HANDSHAKE, 0, 4, frag_b)),
        ("empty", b""),
        ("length_overrun", bytes(overrun)),
    ]
    return [make_entry("text", _dtls_text(blob), "seed:" + name, "seed")
            for name, blob in out]
def _task(tid="bm-task-0001", **extra):
    task = {"task_id": tid, "priority": 1, "requires": [],
            "capabilities": ["shell"], "compartments": [],
            "payload": {"script": "echo task"}}
    task.update(extra)
    return task


def _board_file(*tasks):
    return json.dumps({t["task_id"]: t for t in tasks}, indent=2)


def seeds_board_ops():
    cfg = {"worker_allowlist": ["worker-a", "worker-b"],
           "worker_compartments": {"worker-a": ["blue"]},
           "dag_mode": "enforce"}
    claimed = dict(_task(), state="claimed", claimed_by="worker-a",
                   submitted_at="2026-10-26T12:00:00+00:00")
    done = dict(_task("bm-task-0000"), state="done",
                submitted_at="2026-10-26T11:00:00+00:00")
    out = [
        ("happy_path", {"file": None, "ops": [
            ["submit", _task()],
            ["offer", "worker-a", ["shell"], "ops", cfg],
            ["complete", "bm-task-0001", {"exit_code": 0, "stdout": "task"}]]}),
        ("duplicate_submit", {"file": None, "ops": [
            ["submit", _task()], ["submit", _task()]]}),
        ("not_claimed", {"file": None, "ops": [
            ["submit", _task()], ["complete", "bm-task-0001", {}]]}),
        ("review", {"file": None, "ops": [
            ["submit", _task()], ["offer", "worker-b", ["shell"], "", cfg],
            ["complete", "bm-task-0001", {"exit_code": 0}, True]]}),
        ("allowlist_refuses", {"file": None, "ops": [
            ["submit", _task()], ["offer", "nobody", ["shell"], "", cfg]]}),
        ("capability_gap", {"file": None, "ops": [
            ["submit", _task(capabilities=["gpu"])],
            ["offer", "worker-a", ["shell"], "", cfg]]}),
        # The second offer is another worker's: the first worker
        # would only be handed its outstanding claim again.
        ("compartment", {"file": None, "ops": [
            ["submit", _task(compartments=["blue"])],
            ["submit", _task("bm-task-0002", compartments=["red"])],
            ["offer", "worker-a", ["shell"], "", cfg],
            ["offer", "worker-b", ["shell"], "", cfg],
            ["offer", "worker-a", ["shell"], "", cfg]]}),
        ("dag_enforce", {"file": _board_file(done), "ops": [
            ["submit", _task(requires=["bm-task-0000"])],
            ["submit", _task("bm-task-0002", requires=["bm-task-0009"])],
            ["offer", "worker-a", ["shell"], "", cfg],
            ["offer", "worker-b", ["shell"], "", cfg],
            ["complete", "bm-task-0001", {"exit_code": 0}],
            ["offer", "worker-b", ["shell"], "", dict(cfg, dag_mode="advisory")]]}),
        ("dag_withheld_then_done", {"file": None, "ops": [
            ["submit", _task("bm-task-0002", requires=["bm-task-0001"])],
            ["offer", "worker-a", ["shell"], "", cfg],
            ["submit", _task()],
            ["offer", "worker-a", ["shell"], "", cfg],
            ["complete", "bm-task-0001", {"exit_code": 0}],
            ["offer", "worker-b", ["shell"], "", cfg]]}),
        ("priority_shapes", {"file": None, "ops": [
            ["submit", {"task_id": "bm-task-p0", "capabilities": []}],
            ["submit", _task("bm-task-p1", priority=0)],
            ["submit", _task("bm-task-p2", priority=0.5)],
            ["submit", _task("bm-task-p3", priority=float("nan"))],
            ["submit", _task("bm-task-p4", priority=float("inf"))],
            ["submit", _task("bm-task-p5", priority=-float("inf"))],
            ["submit", _task("bm-task-p6", priority=True)],
            ["submit", _task("bm-task-p7", priority=2 ** 63)],
            ["offer", "worker-a", ["shell"], "", {}],
            ["offer", "worker-b", ["shell"], "", {}],
            ["offer", "worker-c", ["shell"], "", {}]]}),
        ("dag_advisory", {"file": None, "ops": [
            ["submit", _task(requires=["bm-task-0009"])],
            ["offer", "worker-a", ["shell"], "", dict(cfg, dag_mode="advisory")]]}),
        ("reoffer_claim", {"file": _board_file(claimed), "ops": [
            ["offer", "worker-a", [], "", {}],
            ["complete", "bm-task-0001", "a string result"]]}),
        ("priorities", {"file": None, "ops": [
            ["submit", _task("bm-task-low", priority=0)],
            ["submit", _task("bm-task-high", priority=9.5)],
            ["submit", _task("bm-task-neg", priority=-3)],
            ["offer", "worker-a", ["shell"], "", {}]]}),
        ("bad_shapes", {"file": None, "ops": [
            ["submit", "not a task"], ["submit", {"task_id": "../x"}],
            ["submit", _task(requires="shell")],
            ["submit", _task(priority="high")],
            ["offer", {"id": 1}, "shell", None, "cfg"],
            ["complete", {"task_id": 1}, None],
            ["complete", "nope", {}]]}),
        ("file_is_a_list", {"file": "[1, 2, 3]", "ops": [["submit", _task()]]}),
        ("file_is_garbage", {"file": "{not json", "ops": [
            ["submit", _task()], ["offer", "worker-a", ["shell"], "", {}]]}),
        ("file_task_not_dict", {"file": json.dumps({"bm-task-0001": 7,
                                                    "bm-task-0002": _task(
                                                        "bm-task-0002")}),
                               "ops": [["offer", "worker-a", ["shell"], "",
                                        {}]]}),
        ("file_requires_dict", {"file": _board_file(
            _task(requires=[{"x": 1}])), "ops": [
            ["offer", "worker-a", ["shell"], "", dict(cfg, dag_mode="enforce")]]}),
        ("approve_review", {"file": None, "ops": [
            ["submit", _task()], ["offer", "worker-a", ["shell"], "", {}],
            ["complete", "bm-task-0001", {"exit_code": 0}, True],
            ["approve", "bm-task-0001"], ["approve", "bm-task-0001"],
            ["approve", "bm-task-0009"], ["approve", {"task_id": 1}]]}),
        ("lease_expires", {"file": _board_file(dict(
            claimed, claimed_at="2020-01-01T00:00:00+00:00")), "ops": [
            ["reoffer", 60], ["offer", "worker-b", ["shell"], "", {}],
            ["reoffer", 0], ["reoffer", None], ["reoffer", -5],
            ["reoffer", True], ["reoffer", "soon"]]}),
        ("lease_unreadable", {"file": _board_file(dict(
            claimed, claimed_at="yesterday")), "ops": [
            ["reoffer", 0], ["offer", "worker-b", ["shell"], "", {}]]}),
        ("refusals_then_good", {"file": "{not json", "ops": [
            ["submit", "not a task"], ["submit", {"task_id": "../x"}],
            ["complete", "bm-task-0001", {}], ["approve", {"task_id": 1}],
            ["offer", "nobody", ["shell"], "", cfg],
            ["submit", _task()],
            ["offer", "worker-a", ["shell"], "ops", cfg],
            ["complete", "bm-task-0001", {"exit_code": 0}]]}),
        ("empty", {"file": None, "ops": []}),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


_BOARD_WORKER = "bm-worker-0001"
_BOARD_NEIGHBOR = "bm-board-neighbor"
_BOARD_CFG = {"dag_mode": "off"}


def _board_pair(got, what):
    """(bool or str, str) from submit, offer's neighbors, complete."""
    if not (isinstance(got, tuple) and len(got) == 2
            and isinstance(got[1], str)):
        raise Crash("shape", f"{what} returned {type(got).__name__}")
    return got


def _board_offer(board, caps):
    got, exc = _call(board.offer, _BOARD_WORKER, caps, "", _BOARD_CFG)
    if exc is not None:
        raise Crash("exception", "offer raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    return got


def _board_finish(board, task_id, review, caps):
    """Claim, expire the zero lease and claim again, then complete.
    A review task stops at pending_review until approve."""
    offered = _board_offer(board, caps)
    if not isinstance(offered, dict) or offered.get("task_id") != task_id:
        raise Crash("contract", "an open task was not offered")
    if board.tasks[task_id].get("state") != "claimed":
        raise Crash("contract", "offer did not claim the task")
    offered["state"] = "tampered"
    if board.tasks[task_id].get("state") == "tampered":
        raise Crash("contract", "offer handed out the live record")
    # A stale claim, not the clock: a lease of zero reopens a
    # claimed_at that is already in the past.
    board.tasks[task_id]["claimed_at"] = "2020-01-01T00:00:00+00:00"
    n, exc = _call(board.reoffer_expired, 0)
    if exc is not None:
        raise Crash("exception", "reoffer_expired raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if not isinstance(n, int) or n < 1:
        raise Crash("contract", "a zero lease did not reopen the claim")
    if board.tasks[task_id].get("state") != "open":
        raise Crash("contract", "reoffer left the task claimed")
    offered = _board_offer(board, caps)
    if not isinstance(offered, dict) or offered.get("task_id") != task_id:
        raise Crash("contract", "a reopened task was not offered")
    got, exc = _call(board.complete, task_id, {"text": "bm-result"},
                     review)
    if exc is not None:
        raise Crash("exception", "complete raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    status, _msg = _board_pair(got, "complete")
    if review:
        if status != "pending_review":
            raise Crash("contract", f"review complete returned {status!r}")
        approved, exc = _call(board.approve, task_id)
        if exc is not None:
            raise Crash("exception", "approve raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        flag, _why = _board_pair(approved, "approve")
        if flag is not True or board.tasks[task_id].get("state") != "done":
            raise Crash("contract", "approve did not finish the task")
    elif status != "done":
        raise Crash("contract", f"complete returned {status!r}")
    again, exc = _call(board.complete, task_id, {"text": "again"}, False)
    if exc is not None:
        raise Crash("exception", "a second complete raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    status, _msg = _board_pair(again, "complete")
    if status != "duplicate":
        raise Crash("contract", f"a second complete returned {status!r}")


def _board_offer_cfg(board, caps, cfg):
    got, exc = _call(board.offer, _BOARD_WORKER, caps, "", cfg)
    if exc is not None:
        raise Crash("exception", "offer raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    return got


def _board_gates(directory):
    """The board's own gates, on a second file in the same temp:
    an allowlist miss, a compartment miss, enforce withholding an
    unmet requirement, and advisory handing it out with the
    warning. A poison entry must not be what reaches these."""
    board = BD.Board(os.path.join(directory, "gates.json"))
    task = {"task_id": "bm-task-gates", "priority": 1,
            "requires": ["bm-missing"], "capabilities": ["code"],
            "compartments": ["lab"], "payload": {"note": "gates"}}
    got, exc = _call(board.submit, task)
    if exc is not None:
        raise Crash("exception", "the gates submit raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    ok, _msg = _board_pair(got, "submit")
    if ok is not True:
        raise Crash("contract", "the gates task was refused")
    tid = task["task_id"]
    blocked = _board_offer_cfg(board, ["code"], {
        "dag_mode": "off", "worker_allowlist": ["bm-other"]})
    if blocked is not None or board.tasks[tid].get("state") != "open":
        raise Crash("contract", "an allowlist miss still offered")
    hidden = _board_offer_cfg(board, ["code"], {
        "dag_mode": "off",
        "worker_allowlist": [_BOARD_WORKER],
        "worker_compartments": {_BOARD_WORKER: ["other"]}})
    if hidden is not None or board.tasks[tid].get("state") != "open":
        raise Crash("contract", "a compartment miss still offered")
    held = _board_offer_cfg(board, ["code"], {
        "dag_mode": "enforce",
        "worker_allowlist": [_BOARD_WORKER],
        "worker_compartments": {_BOARD_WORKER: ["lab"]}})
    if held is not None or board.tasks[tid].get("state") != "open":
        raise Crash("contract", "enforce offered a task whose "
                    "requirement is not done")
    weird, exc = _call(board.offer, {"not": "text"}, ["code"], "",
                       {"dag_mode": "off",
                        "worker_allowlist": ["bm-other"]})
    if exc is not None:
        raise Crash("exception", "offer of a non-string worker raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if weird is not None:
        raise Crash("contract", "a non-string worker was offered a task")
    warned = _board_offer_cfg(board, ["code"], {
        "dag_mode": "advisory",
        "worker_allowlist": [_BOARD_WORKER],
        "worker_compartments": {_BOARD_WORKER: ["lab"]}})
    if not isinstance(warned, dict) or warned.get("task_id") != tid:
        raise Crash("contract", "advisory did not hand out the task")
    warning = warned.get("dag_warning") or {}
    missing = warning.get("incomplete_requires")
    if missing != ["bm-missing"]:
        raise Crash("contract", "advisory warning did not name the "
                    f"missing requirement: {missing!r}")
    if board.tasks[tid].get("state") != "claimed":
        raise Crash("contract", "advisory did not claim the task")


def _board_neighbor(board, task):
    """A known-good task after the entry, whatever the entry did.
    A poison task must not stop the next one (the sequence)."""
    nid = _BOARD_NEIGHBOR
    if isinstance(task, dict) and task.get("task_id") == nid:
        nid = nid + "-2"
    good = {"task_id": nid, "priority": 0, "capabilities": ["code"],
            "payload": {"note": "neighbor"}}
    got, exc = _call(board.submit, good)
    if exc is not None:
        raise Crash("exception", "the neighbor submit raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    ok, _msg = _board_pair(got, "submit")
    if ok is not True:
        raise Crash("contract", "the neighbor task was refused")
    _board_finish(board, nid, False, ["code"])


def check_board(entry):
    """board: one task dict (Q67). submit, offer, complete, approve
    and reoffer_expired never raise. A task that is not a usable
    submission is refused and stores nothing. A task that is
    accepted is offered to a worker who holds its capabilities,
    completed once (the second complete is a duplicate), and a
    known-good neighbor submitted after it still runs. Invented
    ids only; the board file is a private temp and does not
    outlive the check."""
    task = entry["data"]
    directory = tempfile.mkdtemp(prefix="hp-bm-board-")
    previous = BD._LOGGER
    try:
        BD.set_logger(lambda *_a, **_k: None)
        board = BD.Board(os.path.join(directory, "board.json"))
        got, exc = _call(board.submit, task)
        if exc is not None:
            raise Crash("exception", "submit raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        ok, _msg = _board_pair(got, "submit")
        if ok is True:
            if not isinstance(task, dict):
                raise Crash("contract", "submit accepted a non-object")
            tid = task.get("task_id")
            stored = board.tasks.get(tid)
            if not isinstance(stored, dict) or stored.get("state") != "open":
                raise Crash("contract", "an accepted task is not open")
            again, exc = _call(board.submit, task)
            if exc is not None:
                raise Crash("exception", "a duplicate submit raised "
                            f"{type(exc).__name__}: {_short(exc)}")
            dup, why = _board_pair(again, "submit")
            if (dup, why) != (False, "duplicate task_id"):
                raise Crash("contract", "a second submit returned "
                            f"{dup!r} {why!r}")
            if board.tasks[tid] is not stored:
                raise Crash("contract", "a duplicate submit replaced "
                            "the first task")
            review = (isinstance(task.get("payload"), dict)
                      and task["payload"].get("bm_review") is True)
            caps = list(task.get("capabilities") or [])
            _board_finish(board, tid, review, caps)
            _board_neighbor(board, task)
            _board_gates(directory)
            return "accepted"
        if board.tasks:
            raise Crash("contract", "a refused task was stored")
        missed, exc = _call(board.complete, "bm-task-missing",
                            {"text": "x"}, False)
        if exc is not None:
            raise Crash("exception", "complete on an empty board raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        status, _msg = _board_pair(missed, "complete")
        if status != "not_found":
            raise Crash("contract", "complete on an empty board returned "
                        f"{status!r}")
        if _board_offer(board, ["code"]) is not None:
            raise Crash("contract", "offer returned a task from an "
                        "empty board")
        _board_neighbor(board, task)
        _board_gates(directory)
        return "refused"
    finally:
        BD._LOGGER = previous
        shutil.rmtree(directory, True)


def _board_task(**extra):
    task = {"task_id": "bm-task-0001", "priority": 1, "requires": [],
            "capabilities": ["code"], "compartments": [],
            "payload": {"script": "echo board"}}
    task.update(extra)
    return task


def seeds_board():
    """Task dicts a worker could submit. The ids are invented.
    A `bm_review` payload is the one that completes through
    pending_review. NaN and Infinity are the finite-number
    refusals; they are JSON values the loader accepts."""
    out = [
        ("open", _board_task()),
        ("minimal", {"task_id": "bm-task-0002"}),
        ("high_priority", _board_task(task_id="bm-task-0003", priority=100)),
        ("negative_priority", _board_task(task_id="bm-task-0004",
                                          priority=-3)),
        ("requires", _board_task(task_id="bm-task-0005",
                                 requires=["bm-task-0001"])),
        ("two_capabilities", _board_task(
            task_id="bm-task-0006", capabilities=["review", "code"])),
        ("compartments", _board_task(task_id="bm-task-0007",
                                     compartments=["lab"])),
        ("empty_capabilities", _board_task(task_id="bm-task-0008",
                                           capabilities=[])),
        ("review", _board_task(task_id="bm-task-0009",
                               payload={"bm_review": True})),
        ("bad_id", _board_task(task_id="../x")),
        ("empty_id", _board_task(task_id="")),
        ("long_id", _board_task(task_id="b" * 129)),
        ("id_not_text", {"task_id": 7}),
        ("not_object", ["bm-task-0001"]),
        ("null", None),
        ("empty_object", {}),
        ("requires_not_list", _board_task(task_id="bm-task-0010",
                                          requires="code")),
        ("requires_dict", _board_task(task_id="bm-task-0011",
                                      requires=[{"a": 1}])),
        ("caps_not_strings", _board_task(task_id="bm-task-0012",
                                        capabilities=[1, "code"])),
        ("priority_text", _board_task(task_id="bm-task-0013",
                                      priority="high")),
        ("priority_bool", _board_task(task_id="bm-task-0014", priority=True)),
        ("nan_priority", _board_task(task_id="bm-task-0015",
                                     priority=float("nan"))),
        ("inf_priority", _board_task(task_id="bm-task-0016",
                                     priority=float("inf"))),
        ("nested_payload", _board_task(
            task_id="bm-task-0017",
            payload={"a": {"b": [1, None, True]}})),
    ]
    return [make_entry("payload", task, "seed:" + name, "seed")
            for name, task in out]


_CHANNEL_NAME = "bmch"
_CHANNEL_NEIGHBOR = (
    "[HOMING-PIGEON] job bm-job-neighbor\n\n"
    "{\"note\":\"neighbor\"}\n")
_CHANNEL_GOOD = (
    "[HOMING-PIGEON] job bm-job-0001\n\n"
    "{\"note\":\"bm\"}\n")


def _channel_bytes(payload):
    """The bytes one inbox file holds. A string is written as
    UTF-8, surrogatepass so a lone surrogate becomes a refusal
    the reader meets as bad bytes. A list of byte values is
    written raw. Anything else is JSON, which has no blank line
    and so cannot be an envelope."""
    if isinstance(payload, str):
        return payload.encode("utf-8", "surrogatepass")
    if (isinstance(payload, list) and payload
            and all(isinstance(x, int) and not isinstance(x, bool)
                    and 0 <= x <= 255 for x in payload)):
        return bytes(payload)
    try:
        return json.dumps(payload, ensure_ascii=True).encode("ascii")
    except (TypeError, ValueError, RecursionError):
        return b"?"


def _channel_expect(raw):
    """("job", subject, body) or ("refuse",) for the bytes the
    reader will see. The reader's own parse, so the two cannot
    disagree about what a blank line means."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ("refuse",)
    parsed = TR.parse_envelope(text)
    if parsed is None:
        return ("refuse",)
    return ("job", parsed[0], parsed[1])


def _channel_outbox(path):
    return [name for name in os.listdir(path)
            if os.path.isfile(os.path.join(path, name))]


def _channel_place(inbox, name, payload):
    raw = _channel_bytes(payload)
    with open(os.path.join(inbox, name), "wb") as fh:
        fh.write(raw)
    return raw


def _channel_check_message(msg, outbox, expect):
    """One fetched message. A job's reply stores one result
    inside the outbox. A refusal's reply stores nothing."""
    if not isinstance(msg, TR.IncomingMessage):
        raise Crash("shape", "fetch returned "
                    f"{type(msg).__name__}")
    before = set(_channel_outbox(outbox))
    _got, exc = _call(msg.reply, "bm-result", "bm-body")
    if exc is not None:
        raise Crash("exception", "reply raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    new = set(_channel_outbox(outbox)) - before
    root = os.path.realpath(outbox) + os.sep
    for name in new:
        real = os.path.realpath(os.path.join(outbox, name))
        if not real.startswith(root):
            raise Crash("contract", "a reply left the outbox")
    if expect[0] == "job":
        if msg.subject != expect[1] or msg.body != expect[2]:
            raise Crash("contract", "a parsed envelope was not "
                        "returned as its subject and body")
        if len(new) != 1:
            raise Crash("contract", "a job reply stored "
                        f"{len(new)} results")
    else:
        if msg.subject or msg.body:
            raise Crash("contract", "a refusal carried a subject "
                        "or a body")
        if new:
            raise Crash("contract", "a refusal stored a result")
    _got, exc = _call(msg.ack)
    if exc is not None:
        raise Crash("exception", "ack raised "
                    f"{type(exc).__name__}: {_short(exc)}")


def check_channels(entry):
    """channels: a pair of inbox files, plus a known-good
    neighbor the entry cannot change (Q68).
    fetch_channel_messages never raises. A file that is not an
    envelope is an ack-only refusal and stores nothing. A file
    that is an envelope comes back as that subject and body, and
    its reply stays inside the outbox. The neighbor in the same
    directory is still a job either way. A symlink and a
    non-UTF-8 file are refused unread. An oversize file is
    refused unread, probed with the cap lowered and put back."""
    data = entry["data"] if isinstance(entry["data"], dict) else {}
    poison = data.get("poison", entry["data"])
    other = data.get("other", "")
    directory = tempfile.mkdtemp(prefix="hp-bm-channel-")
    saved_cap = TR.FILE_MAX_BYTES
    try:
        paths = TR.ensure_channel_dirs(directory, _CHANNEL_NAME)
        inbox = paths["inbox"]
        os.mkdir(os.path.join(inbox, "notes"))
        placed = {
            "a-poison.job.txt": _channel_place(inbox, "a-poison.job.txt",
                                               poison),
            "b-other.job.txt": _channel_place(inbox, "b-other.job.txt",
                                              other),
            "c-neighbor.job.txt": _channel_place(
                inbox, "c-neighbor.job.txt", _CHANNEL_NEIGHBOR),
        }
        with open(os.path.join(inbox, "e-bad.job.txt"), "wb") as fh:
            fh.write(b"\xff\xfe not utf-8")
        linked = False
        try:
            os.symlink(os.path.join(directory, "outside"),
                       os.path.join(inbox, "z-link.job.txt"))
            linked = True
        except OSError:
            linked = False
        messages, exc = _call(TR.fetch_channel_messages, directory,
                              _CHANNEL_NAME, lambda *_a, **_k: None)
        if exc is not None:
            raise Crash("exception", "fetch_channel_messages raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if not isinstance(messages, list):
            raise Crash("shape", "fetch returned "
                        f"{type(messages).__name__}")
        by_ident = {}
        for msg in messages:
            ident = getattr(msg, "ident", None)
            if ident in by_ident:
                raise Crash("contract", f"two messages for {ident}")
            by_ident[ident] = msg
        expected = {
            "a-poison.job.txt": _channel_expect(placed["a-poison.job.txt"]),
            "b-other.job.txt": _channel_expect(placed["b-other.job.txt"]),
            "c-neighbor.job.txt": ("job",) + TR.parse_envelope(
                _CHANNEL_NEIGHBOR),
            "e-bad.job.txt": ("refuse",),
        }
        if linked:
            expected["z-link.job.txt"] = ("refuse",)
        if set(by_ident) != set(expected):
            raise Crash("contract", "the poll dropped or invented a "
                        f"file: {sorted(by_ident)} != {sorted(expected)}")
        if "notes" in by_ident:
            raise Crash("contract", "a directory was returned as a job")
        for ident, want in expected.items():
            _channel_check_message(by_ident[ident], paths["outbox"], want)
        neighbor = os.path.join(paths["inbox_done"], "c-neighbor.job.txt")
        if not os.path.isfile(neighbor):
            raise Crash("contract", "acking the neighbor did not "
                        "consume it")
        # The cap, lowered only for this probe and put back. The
        # file is a real envelope, so a reader that skipped the
        # size check would trust it.
        TR.FILE_MAX_BYTES = 8
        cap_root = os.path.join(directory, "cap")
        cap_paths = TR.ensure_channel_dirs(cap_root, _CHANNEL_NAME)
        with open(os.path.join(cap_paths["inbox"], "big.job.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write("SS\n\nbody\n")
        capped, exc = _call(TR.fetch_channel_messages, cap_root,
                            _CHANNEL_NAME, lambda *_a, **_k: None)
        if exc is not None:
            raise Crash("exception", "an oversize fetch raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if not isinstance(capped, list) or len(capped) != 1:
            raise Crash("shape", "an oversize inbox did not yield "
                        "one refusal")
        _channel_check_message(capped[0], cap_paths["outbox"], ("refuse",))
        poison_expect = expected["a-poison.job.txt"]
        return "accepted" if poison_expect[0] == "job" else "refused"
    finally:
        TR.FILE_MAX_BYTES = saved_cap
        shutil.rmtree(directory, True)


def seeds_channels():
    """Pairs of inbox texts. The neighbor the contract requires
    is planted by the check, so a mutation of this pair cannot
    erase it. Invented job ids only. The raw list is the
    non-UTF-8 seed."""
    other = ("[HOMING-PIGEON] job bm-job-0002\n\n"
             "{\"note\":\"two\"}\n")
    pairs = [
        ("two_jobs", _CHANNEL_GOOD, other),
        ("no_blank", "no blank line here", _CHANNEL_GOOD),
        ("empty", "", _CHANNEL_GOOD),
        ("crlf", "[HOMING-PIGEON] job bm-job-0003\r\n\r\n"
                 "{\"note\":\"crlf\"}\r\n", _CHANNEL_GOOD),
        ("only_subject", "[HOMING-PIGEON] job bm-job-0004\n",
         _CHANNEL_GOOD),
        ("both_bad", "nope", "also nope"),
        ("nul", "[HOMING-PIGEON] job bm-job-0005\n\n"
                "{\"note\":\"a\u0000b\"}\n", _CHANNEL_GOOD),
        ("padded_subject", "  [HOMING-PIGEON] job bm-job-0006  \n\n"
                           "body\n", _CHANNEL_GOOD),
        ("two_blanks", "[HOMING-PIGEON] job bm-job-0007\n\n\nbody\n",
         _CHANNEL_GOOD),
        ("raw_bytes", [255, 254, 0], _CHANNEL_GOOD),
        ("subject_only_blank", "\n\nbody\n", _CHANNEL_GOOD),
    ]
    return [make_entry("payload", {"poison": poison, "other": other},
                       "seed:" + name, "seed")
            for name, poison, other in pairs]


_MANIFEST_KEYS = {
    "name", "version", "api_version", "kind", "description", "tunables",
    "signals", "entry", "publisher", "startup_settle_ms", "upstream",
    "capabilities",
}
_MANIFEST_PIN = "a" * 40


def _sense(**extra):
    manifest = {
        "name": "bm-sense",
        "version": "0.3.0",
        "api_version": 1,
        "kind": "sense",
        "signals": [{"name": "bm_done",
                     "description": "A blueMonday run finished."}],
    }
    manifest.update(extra)
    return manifest


def _transport(**extra):
    manifest = {
        "name": "bm-pipe",
        "version": "0.1.0",
        "api_version": 1,
        "kind": "transport",
        "entry": ["bm-pipe", "--once"],
        "publisher": "bm.example",
    }
    manifest.update(extra)
    return manifest


def _manifest_clean(data, got):
    """The cleaned dict is the manifest's own fields, defaults
    filled, and a copy: editing it does not edit the input."""
    if set(got) != _MANIFEST_KEYS:
        raise Crash("contract", "cleaned manifest keys "
                    f"{sorted(set(got) - _MANIFEST_KEYS) or 'missing'}")
    for field in ("name", "version", "api_version", "kind"):
        if got[field] != data[field]:
            raise Crash("contract", f"{field} was not read back")
    if got["description"] != data.get("description", ""):
        raise Crash("contract", "description was not read back")
    tunables = data.get("tunables", {})
    if got["tunables"] != tunables or got["tunables"] is tunables:
        raise Crash("contract", "tunables was not copied")
    if data.get("kind") == "sense":
        want = [{"name": s["name"], "description": s["description"]}
                for s in data["signals"]]
        if got["signals"] != want:
            raise Crash("contract", "signals were not read back")
    elif got["signals"]:
        raise Crash("contract", "a transport kept signals")
    caps = data.get("capabilities") or []
    if set(got["capabilities"]) != set(caps) \
            or len(got["capabilities"]) != len(set(got["capabilities"])):
        raise Crash("contract", "capabilities were not the declared set")
    entry = data.get("entry")
    want_entry = list(entry) if isinstance(entry, list) else []
    if got["entry"] != want_entry:
        raise Crash("contract", "entry was not read back")
    if isinstance(entry, list) and got["entry"] is entry:
        raise Crash("contract", "entry was the live list")
    publisher = data.get("publisher", "")
    if not isinstance(publisher, str):
        publisher = ""
    if got["publisher"] != publisher:
        raise Crash("contract", "publisher was not read back")
    settle = data.get("startup_settle_ms", 0)
    if isinstance(settle, bool) or not isinstance(settle, int):
        settle = 0
    if got["startup_settle_ms"] != settle:
        raise Crash("contract", "startup_settle_ms was not read back")
    block = data.get("upstream")
    if block is None:
        if got["upstream"] is not None:
            raise Crash("contract", "an absent upstream was stored")
        return
    want = {"repo": block["repo"], "ref": block["ref"], "pin": block["pin"],
            "paths": list(block["paths"]),
            "license": block.get("license", "")}
    if got["upstream"] != want:
        raise Crash("contract", "upstream was not read back")
    if got["upstream"]["paths"] is block["paths"]:
        raise Crash("contract", "upstream paths were the live list")


def check_manifest(entry):
    """manifest: one extension.json object (Q69). parse_manifest
    returns the cleaned manifest or raises ValueError and nothing
    else. A manifest it accepts is read back with defaults filled
    and the caller's objects left alone. A newer api_version than
    this agent provides is still accepted here; api_refusal is
    the later check, and it is not this target."""
    got, exc = _call(EX.parse_manifest, entry["data"])
    if exc is not None:
        _expect_refusal(exc, ValueError, "parse_manifest")
        if not str(exc).strip():
            raise Crash("contract", "ValueError with no reason")
        return "refused"
    if not isinstance(got, dict):
        raise Crash("shape", "parse_manifest returned "
                    f"{type(got).__name__}")
    _manifest_clean(entry["data"], got)
    note("clean", _digest(got))
    return "accepted"


def seeds_manifest():
    """extension.json objects, invented names only. A sense, a
    transport, the optional blocks, and the refusals the
    docstring names. api_version 2 is accepted by this reader."""
    upstream = {
        "repo": "https://github.com/bm-owner/bm-repo",
        "ref": "main",
        "pin": _MANIFEST_PIN,
        "paths": ["schema/record.json"],
        "license": "MIT",
    }
    many = [{"name": f"bm_sig_{i}", "description": "A declared signal."}
            for i in range(65)]
    out = [
        ("sense", _sense()),
        ("sense_described", _sense(
            description="A blueMonday sense.",
            tunables={"threshold": 1})),
        ("sense_two_signals", _sense(signals=[
            {"name": "bm_done", "description": "Finished."},
            {"name": "bm_wait", "description": "Still running."},
        ])),
        ("sense_capabilities", _sense(
            capabilities=["network", "listen"])),
        ("sense_upstream", _sense(upstream=upstream)),
        ("sense_entry_ignored", _sense(entry=["bm-sense"])),
        ("sense_long_name", _sense(name="b" * 64)),
        ("sense_prerelease", _sense(version="0.3.0-bm.1")),
        ("sense_build", _sense(version="0.3.0+bm")),
        ("sense_newer_api", _sense(api_version=2)),
        ("sense_long_description", _sense(description="d" * 200)),
        ("sense_settle_kept", _sense(startup_settle_ms=9000)),
        ("transport", _transport()),
        ("transport_settle", _transport(startup_settle_ms=5000)),
        ("transport_caps", _transport(
            capabilities=["subprocess", "native"])),
        ("not_object", ["bm-sense"]),
        ("null", None),
        ("unknown_field", _sense(script="echo")),
        ("missing_version", {"name": "bm-sense", "api_version": 1,
                             "kind": "sense", "signals": [
                                 {"name": "bm_done",
                                  "description": "Finished."}]}),
        ("bad_name", _sense(name="../x")),
        ("empty_name", _sense(name="")),
        ("bad_version", _sense(version="1")),
        ("api_zero", _sense(api_version=0)),
        ("api_bool", _sense(api_version=True)),
        ("api_text", _sense(api_version="1")),
        ("bad_kind", _sense(kind="oracle")),
        ("description_newline", _sense(description="a\nb")),
        ("description_long", _sense(description="d" * 201)),
        ("no_signals", _sense(signals=[])),
        ("duplicate_signal", _sense(signals=[
            {"name": "bm_done", "description": "Finished."},
            {"name": "bm_done", "description": "Again."},
        ])),
        ("signal_extra", _sense(signals=[{
            "name": "bm_done", "description": "Finished.",
            "level": "info"}])),
        ("bad_capability", _sense(capabilities=["shell"])),
        ("too_many_signals", _sense(signals=many)),
        ("transport_no_entry", _transport(entry=[])),
        ("transport_nul", _transport(entry=["bm-pipe", "a\x00b"])),
        ("transport_settle_high", _transport(startup_settle_ms=5001)),
        ("upstream_repo", _sense(upstream=dict(
            upstream, repo="https://example.com/bm/repo"))),
        ("upstream_pin", _sense(upstream=dict(upstream, pin="abcd"))),
        ("upstream_path", _sense(upstream=dict(
            upstream, paths=["../secret"]))),
    ]
    return [make_entry("payload", manifest, "seed:" + name, "seed")
            for name, manifest in out]
def _chan(name, text):
    return {"name": name, "text": text}


def seeds_inbox():
    good = TR.format_envelope("[HOMING-PIGEON] job bm-job-0001",
                              _job_body())
    out = [
        ("one_good", {"files": [_chan("bm-0001.job.txt", good)]}),
        ("crlf", {"files": [_chan("bm-0002.job.txt",
                                  good.replace("\n", "\r\n"))]}),
        ("no_blank_line", {"files": [_chan("bm-0003.job.txt",
                                           good.replace("\n\n", "\n", 1))]}),
        ("empty_file", {"files": [_chan("bm-0004.job.txt", "")]}),
        ("subject_only", {"files": [_chan("bm-0005.job.txt",
                                          "[HOMING-PIGEON] job bm-0005\n\n")]}),
        ("not_utf8", {"files": [_chan("bm-0006.job.txt",
                                      "[HOMING-PIGEON] job x\n\n\udcff\udcfe")]}),
        ("bom", {"files": [_chan("bm-0007.job.txt", "\ufeff" + good)]}),
        ("many_blank_lines", {"files": [_chan("bm-0008.job.txt",
                                              good.replace("\n\n", "\n\n\n\n"))]}),
        ("poison_then_good", {"files": [
            _chan("bm-0009-a.job.txt", "no envelope here"),
            _chan("bm-0009-b.job.txt", good),
            _chan("bm-0009-c.job.txt", "\udc80\udc81"),
            _chan("bm-0009-d.job.txt", good)]}),
        # Two different poisons, then the good one: the first
        # refusal must leave nothing the second trips on.
        ("poison_poison_good", {"files": [
            _chan("bm-0016-a.job.txt", "no envelope here"),
            _chan("bm-0016-b.job.txt", "\udc80\udc81"),
            {"name": "bm-0016-c.job.txt", "link": "/srv/example/nowhere"},
            {"name": "bm-0016-d.job.txt", "fill": TR.FILE_MAX_BYTES + 1},
            _chan("bm-0016-e.job.txt", good)]}),
        ("no_suffix", {"files": [_chan("bm-0010", good),
                                 _chan("bm-0010.txt", good),
                                 _chan("bm-0010.job", good)]}),
        ("symlinks", {"files": [{"name": "bm-0011.job.txt",
                                 "link": "/srv/example/nowhere"},
                                {"name": "bm-0011-b.job.txt",
                                 "link": "bm-0011-c.job.txt"},
                                _chan("bm-0011-c.job.txt", good)]}),
        ("subdir", {"files": [{"name": "bm-0012", "dir": True},
                              _chan("bm-0012.job.txt", good)]}),
        ("oversize", {"files": [{"name": "bm-0013.job.txt",
                                 "fill": TR.FILE_MAX_BYTES + 1},
                                _chan("bm-0013-b.job.txt", good)]}),
        ("at_the_cap", {"files": [{"name": "bm-0014.job.txt",
                                   "fill": TR.FILE_MAX_BYTES}]}),
        ("odd_names", {"files": [_chan("a", good), _chan("A.job.txt", good),
                                 _chan("9.job.txt", good),
                                 _chan("x" * 64, good),
                                 _chan("bm.job.txt.job.txt", good),
                                 _chan("done.job.txt", good)]}),
        ("same_stem", {"files": [_chan("bm-0021", good),
                                 _chan("bm-0021.job.txt", good)]}),
        ("empty_inbox", {"files": []}),
    ]
    pair = [_chan("bm-0020-a.job.txt", "no envelope here"),
            _chan("bm-0020-b.job.txt", good)]
    for mode in _CHANNEL_MODES[1:]:
        out.append(("core_" + mode, {"files": pair, "mode": mode}))
    out.append(("core_reply2_same_stem", {"files": [
        _chan("bm-0022", good), _chan("bm-0022.job.txt", good)],
        "mode": "reply2"}))
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def _job_body():
    return V.sign_payload(_job(), SECRET) + "\n"


def seeds_local_inbox():
    good = V.sign_payload(_frozen_alert(), SENSE)
    live = {"name": "bm-0001.json", "text": "@alert"}
    out = [
        ("one_good", {"files": [live]}),
        ("frozen", {"files": [_chan("bm-0002.json", good)]}),
        ("wrong_key", {"files": [_chan("bm-0003.json",
                                       V.sign_payload(_frozen_alert(),
                                                      SECRET))]}),
        ("not_an_alert", {"files": [_chan("bm-0004.json",
                                          V.sign_payload(_job(), SECRET))]}),
        ("not_json", {"files": [_chan("bm-0005.json", "not json at all")]}),
        ("empty", {"files": [_chan("bm-0006.json", "")]}),
        ("not_utf8", {"files": [_chan("bm-0007.json", "\udcff\udcfe{}")]}),
        ("too_large", {"files": [{"name": "bm-0008.json",
                                  "fill": R._LOCAL_ENVELOPE_MAX_BYTES + 1}]}),
        ("at_the_cap", {"files": [{"name": "bm-0009.json",
                                   "fill": R._LOCAL_ENVELOPE_MAX_BYTES}]}),
        ("poison_then_good", {"files": [
            _chan("bm-0010-a.json", "{"), dict(live, name="bm-0010-b.json"),
            _chan("bm-0010-c.json", "\udc80"), dict(live, name="bm-0010-d.json")]}),
        ("poison_poison_good", {"files": [
            _chan("bm-0017-a.json", "{"), _chan("bm-0017-b.json", "\udc80"),
            {"name": "bm-0017-c.json", "link": "/srv/example/nowhere"},
            _chan("bm-0017-d.json", V.sign_payload(_job(), SECRET)),
            dict(live, name="bm-0017-e.json")]}),
        ("not_json_names", {"files": [_chan("bm-0011.txt", good),
                                      _chan("bm-0011", good),
                                      _chan("bm-0011.JSON", good),
                                      _chan("bm-0011.json.bak", good)]}),
        ("symlinks", {"files": [{"name": "bm-0012.json",
                                 "link": "/srv/example/nowhere"},
                                {"name": "bm-0012-b.json",
                                 "link": "bm-0012-c.json"},
                                dict(live, name="bm-0012-c.json"),
                                {"name": "bm-0012.txt", "link": "bm-0012-c.json"}]}),
        ("subdir", {"files": [{"name": "bm-0013.json", "dir": True},
                              dict(live, name="bm-0013-b.json")]}),
        ("twice", {"files": [dict(live, name="bm-0014-a.json"),
                             dict(live, name="bm-0014-b.json")]}),
        ("stale", {"files": [_chan("bm-0015.json", V.sign_payload(
            _alert(issued_at="2020-01-01T00:00:00Z"), SENSE))]}),
        ("empty_inbox", {"files": []}),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def seeds_secret():
    hexes = "0123456789abcdef"
    out = [
        ("hex_64", SECRET),
        ("hex_32", SECRET[:32]),              # 128 bits by the estimate
        ("hex_31", SECRET[:31]),              # just under
        ("hex_33", SECRET[:33]),
        ("one_char", "a"),
        ("two_chars", "ab"),
        ("repeat_unit", "abcd" * 16),
        ("repeat_unit_cut", ("abcd" * 17)[:66]),
        ("almost_repeat", "abcd" * 15 + "abce"),
        ("placeholder", "please-generate-a-real-secret-here-0123456789"),
        ("placeholder_case", "CHANGEME" + hexes * 4),
        ("todo_inside", hexes * 2 + "todo" + hexes * 2),
        ("xxx_inside", hexes * 2 + "xxx" + hexes * 2),
        ("empty", ""),
        ("spaces", " " * 64),
        ("mixed_64", "Aa0!" * 16),
        ("unicode_32", "\u00e9\u00e8\u00ea\u00eb" * 8),
        ("single_alphabet", "a" * 200),
        ("binary_alphabet", "ab" * 64),
        ("long_low_alphabet", "abc" * 100),
        ("hex_upper", SECRET.upper()),
        ("with_newline", SECRET[:40] + "\n" + SECRET[40:]),
        ("tab_and_space", SECRET[:20] + "\t " + SECRET[22:]),
        ("palindrome", "abcdefgh" + "hgfedcba" + "abcdefgh" + "hgfedcba"),
        # 30 characters over 19 symbols: 127.4 bits by the estimate,
        # the one value between the floor and the floor less one.
        ("bits_127", "abcdefghijklmnopqrs" + "kjihgfedcba"),
        ("bits_128_mixed", "abcdefghijklmnopqrstuvwxyz0123456"),
    ]
    return [make_entry("text", t, "seed:" + n, "seed") for n, t in out]


# ------------------------------------------------------------------
# Mutators: the job-fuzz vocabulary, on text and on JSON values
# ------------------------------------------------------------------

_DICT = ['"sig":"', ',"sig":"', '"key_id":', '"hp_enc":', '"v":', '"type":',
         '"job"', '"job_id":', '"issued_at":', '"kind":', '"sensor_alert"',
         '"alg":', '"nonce":', '"ct":', '"context":', '"deadline_sec":',
         'null', 'true', 'false', 'NaN', 'Infinity', '-Infinity', '1e999',
         '\\u0000', '\\ud800', '\\"', '{}', '[]', '{', '}', '[', ']', ',',
         ':', '"', '\n', '\r\n', '\x00', '\x1f', '\x7f', '﻿', ' ',
         '\ud800', '́', 'Z', '"2026-10-26T12:00:00Z"', '"sensor":',
         '"canary"', '"canary-key"', '"ops"', '"severity":', '"high"',
         '"title":', '"script":', '"expect":', '"question":', '"answer":']
# The IETF drafts' own literals (docs/ietf/, Q72): member names,
# enumerated values, and the subject marker, as insertion tokens.
# A token already in the list above is not repeated.
_DICT.extend([
    '"reply_to":', '"runner_id":', '"timeout_sec":', '"script_url":',
    '"script_sha384":', '"stdout":', '"stderr":', '"exit_code":',
    '"kind":"ping"', '"kind":"exec"', '"type":"result"',
    '"type":"determination"', "[HOMING-PIGEON] TEST job ",
    "[HOMING-PIGEON] result ",
])
_HEX = "0123456789abcdef"
_SIG_TAIL = 98


def _pos(rng, text):
    return rng.randint(0, len(text)) if text else 0


def t_truncate(rng, text, corpus):
    return text[:_pos(rng, text)]


def t_drop(rng, text, corpus):
    if not text:
        return text
    i = rng.randrange(len(text))
    n = rng.randint(1, min(8, len(text) - i))
    return text[:i] + text[i + n:]


def t_insert(rng, text, corpus):
    i = _pos(rng, text)
    return text[:i] + rng.choice(_DICT) + text[i:]


def t_replace_char(rng, text, corpus):
    if not text:
        return rng.choice(_DICT)
    i = rng.randrange(len(text))
    return text[:i] + rng.choice(_DICT) + text[i + 1:]


def t_duplicate(rng, text, corpus):
    if not text:
        return text
    i = rng.randrange(len(text))
    j = min(len(text), i + rng.randint(1, 64))
    k = _pos(rng, text)
    return text[:k] + text[i:j] + text[k:]


def t_splice(rng, text, corpus):
    others = [e["data"] for e in corpus if e["kind"] == "text"]
    if not others:
        return text
    other = rng.choice(others)
    return text[:_pos(rng, text)] + other[_pos(rng, other):]


def t_sig_tamper(rng, text, corpus):
    i = text.rfind(',"sig":"')
    if i < 0:
        return text
    j = i + 8 + rng.randrange(96)
    if j >= len(text):
        return text
    return text[:j] + rng.choice(_HEX) + text[j + 1:]


def t_fake_marker(rng, text, corpus):
    sig = "".join(rng.choice(_HEX) for _ in range(96))
    i = _pos(rng, text)
    return text[:i] + ',"sig":"' + sig + '"}' + text[i:]


def t_wrap(rng, text, corpus):
    wraps = [("> ", ""), ("", "\n-- \nexample signature\n"),
             ("Fwd:\n\n", ""), ("{", "}"), ('{"a":"', '"}'), ("[", "]"),
             ("﻿", ""), ("\r\n", "\r\n"), ("   ", "   ")]
    head, tail = rng.choice(wraps)
    return head + text + tail


def t_crlf(rng, text, corpus):
    if "\r\n" in text:
        return text.replace("\r\n", "\n")
    return text.replace("\n", "\r\n") if "\n" in text else \
        text.replace(",", ",\r\n", rng.randint(1, 3))


def t_control(rng, text, corpus):
    i = _pos(rng, text)
    return text[:i] + chr(rng.choice([0, 1, 7, 8, 11, 12, 13, 27, 31, 127])) \
        + text[i:]


def t_case(rng, text, corpus):
    i = _pos(rng, text)
    j = min(len(text), i + rng.randint(1, 32))
    return text[:i] + text[i:j].swapcase() + text[j:]


def t_number(rng, text, corpus):
    digits = [k for k, c in enumerate(text) if c.isdigit()]
    if not digits:
        return text
    i = rng.choice(digits)
    j = i
    while j < len(text) and text[j].isdigit():
        j += 1
    pick = rng.choice(["0", "-1", "1", "9" * 20, "1e309", "0.0", "-0",
                       "01", "1.5", "2147483648", "9223372036854775808"])
    return text[:i] + pick + text[j:]


def t_brace(rng, text, corpus):
    i = _pos(rng, text)
    return text[:i] + rng.choice(["{", "}", "{{", "}}", '{"', '"}']) + text[i:]


def t_resign(rng, text, corpus):
    """Parse the signed object out of the text if it parses, perturb
    it as JSON, and sign again: a validly signed near-miss."""
    try:
        norm = V._normalize(text).rstrip()
        raw, _sig = V._extract_signed(norm)
        obj = json.loads(raw)
    except Exception:
        return text
    if not isinstance(obj, dict):
        return text
    obj = p_mutate(rng, obj, corpus)
    if not isinstance(obj, dict):
        return text
    secret, _key = _signing_secret(obj)
    try:
        return V.sign_payload(obj, secret or SECRET)
    except Exception:
        return text


# ------------------------------------------------------------------
# The grammar dictionary: the IETF drafts' own words (phase 4)
# ------------------------------------------------------------------

IETF_DIR = os.path.join(ROOT, "docs", "ietf")
GRAMMAR_PATH = os.path.join(CORPUS_DIR, "grammar.json")
_GRAMMAR = None


def build_grammar(paths):
    """The dictionary the drafts dictate: every backticked token
    without a space (member names, literals, enumerated values,
    patterns), every number the text states, with its neighbours
    on both sides as the boundaries a reader may get wrong, and
    every JSON example, sig removed, as a seed. Sorted, so the file
    is the same for the same drafts."""
    tokens, numbers, examples = set(), set(), []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for tok in re.findall(r"`([^`\n]{1,64})`", text):
            if " " not in tok:
                tokens.add(tok)
        for num in re.findall(r"(?<![\w.])(-?\d{1,7})(?![\w.])", text):
            n = int(num)
            numbers.update((n - 1, n, n + 1))
        # A fenced block that parses as JSON is an example, tagged
        # ```json or not.
        for i, block in enumerate(re.findall(r"```\w*\n(.*?)```", text,
                                            re.S)):
            if not block.lstrip().startswith(("{", "[")):
                continue
            try:
                value = json.loads(block)
            except ValueError:
                continue
            if isinstance(value, dict):
                value.pop("sig", None)
            examples.append({"from": os.path.basename(path) + "#%d" % (i + 1),
                             "value": value})
    return {"bluemonday": 1, "Agent-Stamp": STAMP,
            "tokens": sorted(tokens), "numbers": sorted(numbers),
            "examples": examples}


LEARN_CAP = 400            # learned tokens kept, newest grows first
_LEARN_RE = re.compile(r'"([^"\\]{1,32})"')


def harvest(entries, target, known):
    """Tokens the search found: the keys and short string values of
    every grown (not seeded) entry that is not already a word of
    the drafts, each with where it came from (Muse, 2026-10-26: the
    kept entries are the other half of the evidence)."""
    out = {}
    for e in entries:
        if e.get("mutator") == "seed":
            continue
        found = []
        if e.get("kind") == "payload":
            for _path, v in _paths(e["data"]):
                if isinstance(v, dict):
                    found.extend(k for k in v if isinstance(k, str))
                elif isinstance(v, str):
                    found.append(v)
        elif isinstance(e.get("data"), str):
            found.extend(_LEARN_RE.findall(e["data"]))
        for tok in found:
            if (0 < len(tok) <= 32 and tok.isascii() and tok.isprintable()
                    and " " not in tok and tok not in known
                    and tok not in out):
                out[tok] = f"{target}:{e['id']}"
    return out


def learn(grammar_doc, corpora):
    """The dictionary with its learned section rebuilt from the
    corpora {target: entries}: tokens the grows found, capped."""
    known = set(grammar_doc.get("tokens") or [])
    learned = {}
    for target in sorted(corpora):
        for tok, src in harvest(corpora[target], target, known).items():
            learned.setdefault(tok, src)
    rows = sorted(learned.items())[:LEARN_CAP]
    doc = dict(grammar_doc)
    doc["learned"] = [{"token": t, "from": src} for t, src in rows]
    return doc


def grammar():
    """The committed dictionary, read once; empty when absent."""
    global _GRAMMAR
    if _GRAMMAR is None:
        try:
            with open(GRAMMAR_PATH, encoding="utf-8") as fh:
                _GRAMMAR = json.load(fh)
        except (OSError, ValueError):
            _GRAMMAR = {"tokens": [], "numbers": [], "examples": []}
        _GRAMMAR["words"] = list(_GRAMMAR.get("tokens") or []) + [
            r["token"] for r in _GRAMMAR.get("learned") or []
            if isinstance(r, dict) and isinstance(r.get("token"), str)]
    return _GRAMMAR


def t_grammar(rng, text, corpus):
    """A word of the drafts dropped into the text: at a random
    position, or in place of the content of a quoted string."""
    tokens = grammar().get("words") or []
    if not tokens:
        return text
    tok = rng.choice(tokens)
    quoted = [m for m in re.finditer(r'"([^"\\]{0,64})"', text)]
    if quoted and rng.random() < 0.5:
        m = rng.choice(quoted)
        return text[:m.start(1)] + tok + text[m.end(1):]
    i = _pos(rng, text)
    return text[:i] + tok + text[i:]


def p_grammar(rng, value, corpus):
    """A member of the drafts set on an object, to a word or a
    boundary number of the drafts; or a number anywhere moved to a
    boundary; or a key respelled as a draft member name."""
    g = grammar()
    tokens, numbers = g.get("words") or [], g.get("numbers") or []
    if not tokens or not numbers:
        return value
    objects = [(p, v) for p, v in _paths(value) if isinstance(v, dict)]
    which = rng.random()
    if which < 0.5 and objects:
        path, obj = rng.choice(objects)
        obj = dict(obj)
        key = rng.choice(tokens)
        obj[key] = rng.choice([rng.choice(tokens), rng.choice(numbers),
                               True, None, [rng.choice(tokens)]])
        return _set_path(value, path, obj)
    numeric = [(p, v) for p, v in _paths(value)
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if which < 0.75 and numeric:
        path, _old = rng.choice(numeric)
        return _set_path(value, path, rng.choice(numbers))
    if objects:
        path, obj = rng.choice(objects)
        if obj:
            old = rng.choice(list(obj))
            obj = dict(obj)
            obj[rng.choice(tokens)] = obj.pop(old)
            return _set_path(value, path, obj)
    return value


TEXT_MUTATORS = [t_truncate, t_drop, t_insert, t_replace_char, t_duplicate,
                 t_splice, t_sig_tamper, t_fake_marker, t_wrap, t_crlf,
                 t_control, t_case, t_number, t_brace, t_resign, t_grammar]

_MAIL_DICT = ["Subject: ", "Content-Type: text/plain", "Content-Type: "
              "multipart/mixed; boundary=\"bm-boundary-0001\"",
              "Content-Transfer-Encoding: base64", "Content-Transfer-"
              "Encoding: quoted-printable", "charset=utf-8",
              "charset=iso-8859-1", "=?utf-8?q?", "=?utf-8?b?", "?=",
              "--bm-boundary-0001", "--bm-boundary-0001--", "\r\n\r\n",
              "\r\n", "\n", ": ", ";", "boundary=", "filename=\"x\"",
              "Content-Disposition: attachment", "Reply-To: ",
              "[HOMING-PIGEON]", " job ", " result ", " TEST ",
              "Undeliverable: ",
              "multipart/report; report-type=delivery-status",
              "MIME-Version: 1.0", "=\r\n", "=E2=80=8B", "\x00", "\udcff"]


def _mail_lines(text):
    return text.split("\r\n") if "\r\n" in text else text.split("\n")


def m_drop_header(rng, text, corpus):
    head, sep, body = text.partition("\r\n\r\n")
    if not sep:
        return text
    lines = head.split("\r\n")
    if len(lines) < 2:
        return text
    del lines[rng.randrange(len(lines))]
    return "\r\n".join(lines) + sep + body


def m_duplicate_header(rng, text, corpus):
    head, sep, body = text.partition("\r\n\r\n")
    if not sep:
        return text
    lines = head.split("\r\n")
    line = rng.choice(lines)
    lines.insert(rng.randint(0, len(lines)), line)
    return "\r\n".join(lines) + sep + body


def m_insert_header(rng, text, corpus):
    head, sep, body = text.partition("\r\n\r\n")
    if not sep:
        return rng.choice(_MAIL_DICT) + "\r\n\r\n" + text
    lines = head.split("\r\n")
    lines.insert(rng.randint(0, len(lines)), rng.choice(_MAIL_DICT)
                 + rng.choice(["", "x", "bm", "\"", "=", "?", " "]))
    return "\r\n".join(lines) + sep + body


def m_mail_token(rng, text, corpus):
    i = _pos(rng, text)
    return text[:i] + rng.choice(_MAIL_DICT) + text[i:]


def m_break_boundary(rng, text, corpus):
    if "bm-boundary" not in text:
        return text
    pick = rng.choice([("--bm-boundary-0001--", "--bm-boundary-0001"),
                       ("--bm-boundary-0001", "--bm-boundary-0002"),
                       ('boundary="bm-boundary-0001"', 'boundary=""'),
                       ("--bm-boundary-0001\r\n", "")])
    return text.replace(pick[0], pick[1], 1)


def m_truncate_part(rng, text, corpus):
    head, sep, body = text.partition("\r\n\r\n")
    if not sep or not body:
        return text
    return head + sep + body[:rng.randrange(len(body))]


def m_fold_header(rng, text, corpus):
    head, sep, body = text.partition("\r\n\r\n")
    if not sep:
        return text
    lines = head.split("\r\n")
    i = rng.randrange(len(lines))
    if len(lines[i]) < 4:
        return text
    j = rng.randrange(1, len(lines[i]))
    lines[i] = lines[i][:j] + "\r\n " + lines[i][j:]
    return "\r\n".join(lines) + sep + body


def m_blank_line(rng, text, corpus):
    """Move or remove the header/body blank line."""
    if "\r\n\r\n" not in text:
        return text
    head, sep, body = text.partition("\r\n\r\n")
    pick = rng.random()
    if pick < 0.5:
        return head + "\r\n" + body
    return head + sep + "\r\n" + body


MAIL_MUTATORS = [m_drop_header, m_duplicate_header, m_insert_header,
                 m_mail_token, m_break_boundary, m_truncate_part,
                 m_fold_header, m_blank_line, t_truncate, t_duplicate,
                 t_splice, t_control, t_case, t_crlf]


def d_flip_length(rng, text, corpus):
    """Flip a length the record or the handshake message states:
    the plaintext record's 13-byte header, or a handshake
    message's length or fragment offset."""
    data = bytearray(_raw_bytes(text))
    if len(data) >= 13 and DT._is_plaintext_record(data):
        cur = int.from_bytes(data[11:13], "big")
        pick = rng.choice([0, 1, 0xFFFF, (cur + 1) & 0xFFFF,
                           (cur - 1) & 0xFFFF, cur ^ 0x00FF])
        data[11:13] = pick.to_bytes(2, "big")
        return _dtls_text(data)
    if len(data) >= 12:
        if rng.random() < 0.5:
            cur = int.from_bytes(data[1:4], "big")
            pick = rng.choice([0, 1, 0xFFFFFF, (cur + 1) & 0xFFFFFF,
                               (cur - 1) & 0xFFFFFF])
            data[1:4] = pick.to_bytes(3, "big")
        else:
            cur = int.from_bytes(data[6:9], "big")
            pick = rng.choice([0, 1, 0xFFFFFF, (cur + 8) & 0xFFFFFF])
            data[6:9] = pick.to_bytes(3, "big")
            frag = rng.choice([0, 1, min(len(data), 0xFFFFFF)])
            data[9:12] = frag.to_bytes(3, "big")
        return _dtls_text(data)
    return text


def d_truncate(rng, text, corpus):
    """Cut a datagram in the middle of a record."""
    data = _raw_bytes(text)
    if len(data) < 2:
        return text
    return _dtls_text(data[:rng.randrange(1, len(data))])


def d_overlap_fragments(rng, text, corpus):
    """Two handshake fragments of one message whose ranges overlap,
    each in its own plaintext record, one datagram."""
    data = _raw_bytes(text)
    body = data
    if len(data) >= 13 and DT._is_plaintext_record(data):
        length = int.from_bytes(data[11:13], "big")
        body = data[13:13 + length] or data
    if len(body) < 4:
        body = (b"\x01" + (8).to_bytes(3, "big") + b"\x00\x07"
                + b"abcdEFGH")
    msg_type = body[0]
    if len(body) >= 12:
        stated = int.from_bytes(body[1:4], "big")
        msg_seq = int.from_bytes(body[4:6], "big")
        if stated and 12 + stated <= len(body):
            real = body[12:12 + stated]
        else:
            real = body[12:] or body
    else:
        msg_seq = 1
        real = body
    if not real:
        real = b"\x00"
    total = len(real)
    mid = rng.randint(1, total)
    first = real[:min(total, mid + 1)]
    off = max(0, mid - 1)

    def frag(start, chunk):
        return (bytes([msg_type]) + total.to_bytes(3, "big")
                + msg_seq.to_bytes(2, "big") + start.to_bytes(3, "big")
                + len(chunk).to_bytes(3, "big") + chunk)

    blob = (DT._plaintext_record(DT.CT_HANDSHAKE, 0, 0, frag(0, first))
            + DT._plaintext_record(DT.CT_HANDSHAKE, 0, 1,
                                   frag(off, real[off:])))
    out = _dtls_text(blob)
    return out if out != text else text + _dtls_text(b"\x00")


def d_wrap_seq(rng, text, corpus):
    """Put a sequence number on the wrap: the plaintext record's
    6-byte sequence, or the unified header's low sequence."""
    data = bytearray(_raw_bytes(text))
    if len(data) >= 13 and DT._is_plaintext_record(data):
        data[5:11] = rng.choice([b"\xff" * 6,
                                 b"\x00" * 4 + b"\xff\xff",
                                 b"\xff\xff" + b"\x00" * 4])
        return _dtls_text(data)
    if data and data[0] & 0xE0 == 0x20:
        pos = 1
        if data[0] & 0x04 and pos < len(data):
            pos += 1 + data[pos]
        width = 2 if data[0] & 0x10 else 1
        if pos + width <= len(data):
            data[pos:pos + width] = b"\xff" * width
            return _dtls_text(data)
    wrapped = DT._plaintext_record(
        DT.CT_HANDSHAKE, 0, 0xFFFFFFFFFFFF, data[:8] or b"\x00")
    return _dtls_text(wrapped)


def d_flip_unified_bits(rng, text, corpus):
    """Flip one unified-header bit: C, S, L, or the epoch, and
    force the unified-header marker so the byte is a record."""
    data = bytearray(_raw_bytes(text))
    bit = rng.choice([0x04, 0x10, 0x08, 0x01, 0x02])
    if not data:
        return _dtls_text(bytes([0x20 | bit]))
    data[0] = ((data[0] ^ bit) & 0x1F) | 0x20
    return _dtls_text(data)


def d_duplicate_record(rng, text, corpus):
    data = _raw_bytes(text)
    if not data:
        return text
    records = DT._split_records(data) or [data]
    return _dtls_text(data + rng.choice(records))


def d_drop_record(rng, text, corpus):
    data = _raw_bytes(text)
    if not data:
        return text
    records = DT._split_records(data)
    if len(records) >= 2:
        del records[rng.randrange(len(records))]
        return _dtls_text(b"".join(records))
    return ""


def d_splice_datagrams(rng, text, corpus):
    others = [e["data"] for e in corpus if isinstance(e.get("data"), str)]
    other = rng.choice(others) if others else text
    out = text + other if rng.random() < 0.5 else other + text
    return out if out != text else text + _dtls_text(b"\x01")


def d_random_byte(rng, text, corpus):
    data = bytearray(_raw_bytes(text))
    if not data:
        return _dtls_text(bytes([rng.randrange(256)]))
    i = rng.randrange(len(data))
    nxt = rng.randrange(256)
    if nxt == data[i]:
        nxt ^= 0x01
    data[i] = nxt
    return _dtls_text(data)


DTLS_MUTATORS = [d_flip_length, d_truncate, d_overlap_fragments,
                 d_wrap_seq, d_flip_unified_bits, d_duplicate_record,
                 d_drop_record, d_splice_datagrams, d_random_byte]

_VALUES = [None, True, False, 0, -1, 1, 2 ** 31, 2 ** 63, 2 ** 64, -2 ** 63,
           1.5, -0.0, 1e308, "", " ", "x", "0", "Z", "job", "sensor_alert",
           "proceed", "2026-10-26T12:00:00Z", "2026-10-26T12:00:00",
           "2026-13-01T00:00:00Z", "\u0000", "\ud800", "﻿", " ",
           "a" * 65, "a" * 129, "b" * 4000, "../x", ".", "..", "x/y",
           [], {}, [None], {"": ""}, [[]], {"a": {"b": {"c": []}}}, "@now",
           # Draft enumerations and the boundaries the drafts state:
           # job-id 128, sig and script_sha384 96 hex, why 500, deadline 30.
           "exec", "ping", "result", "fail", "unknown", "determination",
           "submitter@example.com", "d" * 128, "f" * 96, "f" * 95,
           "w" * 500, "w" * 501, 30, 31, 60]
_KEYS = ["v", "type", "job_id", "msg_id", "issued_at", "kind", "key_id",
         "sig", "hp_enc", "alg", "nonce", "ct", "sensor", "severity",
         "title", "signal", "detail", "observed_at", "api_version",
         "script", "shell", "expect", "why", "clean_pass", "question",
         "deadline_sec", "local_default", "context", "question_id",
         "answer", "text", "", " ", "Key_Id", "KEY_ID", "kéy",
         "\u0000", "a" * 200,
         "reply_to", "runner_id", "timeout_sec", "script_url",
         "script_sha384", "stdout", "stderr", "exit_code", "timed_out",
         "completed_at", "duration_sec", "stdout_truncated",
         "stderr_truncated", "interpreter", "args", "env", "files",
         "sha384", "url", "name", "runner", "oracle_opinion"]


def _depth(value, d=0):
    if isinstance(value, dict):
        return max([d] + [_depth(v, d + 1) for v in value.values()])
    if isinstance(value, list):
        return max([d] + [_depth(v, d + 1) for v in value])
    return d


def _paths(value, prefix=()):
    """Every (path, value) in a JSON value, the root included."""
    yield prefix, value
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _paths(v, prefix + (k,))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _paths(v, prefix + (i,))


def _set_path(value, path, new):
    if not path:
        return new
    value = dict(value) if isinstance(value, dict) else list(value)
    head, rest = path[0], path[1:]
    value[head] = _set_path(value[head], rest, new)
    return value


def _del_path(value, path):
    if not path:
        return None
    parent = _get_path(value, path[:-1])
    parent = dict(parent) if isinstance(parent, dict) else list(parent)
    del parent[path[-1]]
    return _set_path(value, path[:-1], parent)


def _get_path(value, path):
    for p in path:
        value = value[p]
    return value


def _random_value(rng, corpus):
    pool = list(_VALUES)
    others = [e["data"] for e in corpus if e["kind"] == "payload"]
    if others:
        pick = rng.choice(others)
        pool += [v for _p, v in _paths(pick)][:40]
    return rng.choice(pool)


def p_replace(rng, value, corpus):
    paths = list(_paths(value))
    path, _old = rng.choice(paths)
    return _set_path(value, path, _random_value(rng, corpus))


def p_delete(rng, value, corpus):
    paths = [p for p, _v in _paths(value) if p]
    if not paths:
        return value
    return _del_path(value, rng.choice(paths))


def p_add_key(rng, value, corpus):
    dicts = [p for p, v in _paths(value) if isinstance(v, dict)]
    if not dicts:
        return {rng.choice(_KEYS): value}
    path = rng.choice(dicts)
    target = dict(_get_path(value, path))
    target[rng.choice(_KEYS)] = _random_value(rng, corpus)
    return _set_path(value, path, target)


def p_rename_key(rng, value, corpus):
    dicts = [(p, v) for p, v in _paths(value) if isinstance(v, dict) and v]
    if not dicts:
        return value
    path, target = rng.choice(dicts)
    target = dict(target)
    old = rng.choice(list(target))
    new = rng.choice([old.upper(), old.title(), old + " ", " " + old,
                      old + "\u0000", old[:-1] if old else "x",
                      rng.choice(_KEYS)])
    target[new] = target.pop(old)
    return _set_path(value, path, target)


def p_text(rng, value, corpus):
    strings = [p for p, v in _paths(value) if isinstance(v, str)]
    if not strings:
        return value
    path = rng.choice(strings)
    mut = rng.choice(TEXT_MUTATORS[:-1])
    return _set_path(value, path, mut(rng, _get_path(value, path), []))


def p_number(rng, value, corpus):
    nums = [p for p, v in _paths(value)
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return value
    path = rng.choice(nums)
    old = _get_path(value, path)
    pick = rng.choice([old + 1, old - 1, -old, old * 2, 0, 2 ** 31,
                       2 ** 63 - 1, 2 ** 63, float(old), 1e308, -1])
    return _set_path(value, path, pick)


def p_nest(rng, value, corpus):
    if _depth(value) >= MAX_DEPTH:
        return value
    paths = list(_paths(value))
    path, old = rng.choice(paths)
    wrap = rng.choice([lambda v: [v], lambda v: {"x": v},
                       lambda v: {"hp_enc": v}, lambda v: [v, v]])
    return _set_path(value, path, wrap(old))


def p_splice(rng, value, corpus):
    others = [e["data"] for e in corpus if e["kind"] == "payload"]
    if not others or not isinstance(value, dict):
        return value
    other = rng.choice(others)
    if not isinstance(other, dict) or not other:
        return value
    merged = dict(value)
    for k in rng.sample(list(other), rng.randint(1, len(other))):
        merged[k] = other[k]
    return merged


def p_swap(rng, value, corpus):
    if not isinstance(value, dict) or len(value) < 2:
        return value
    a, b = rng.sample(list(value), 2)
    out = dict(value)
    out[a], out[b] = value[b], value[a]
    return out


PAYLOAD_MUTATORS = [p_replace, p_delete, p_add_key, p_rename_key, p_text,
                    p_number, p_nest, p_splice, p_swap, p_grammar]


def p_mutate(rng, value, corpus):
    for _ in range(rng.randint(1, 3)):
        value = rng.choice(PAYLOAD_MUTATORS)(rng, value, corpus)
    return value


def _crypto_mutate(rng, spec, corpus):
    """A crypto entry's data is {envelope, job_id, key_id, expect}:
    the envelope and the AAD fields mutate, the expectation drops."""
    spec = dict(spec)
    spec.pop("expect", None)
    which = rng.random()
    if which < 0.7:
        spec["envelope"] = p_mutate(rng, spec.get("envelope"), [])
    elif which < 0.85:
        spec["job_id"] = rng.choice(_VALUES)
    else:
        spec["key_id"] = rng.choice(_VALUES)
    return spec


def _board_mutate(rng, spec, corpus):
    """A board_ops entry's data is {file, ops}. The file text takes the
    text set (over the ops' own tasks serialized when the entry has
    no file), an op's argument takes the payload set, and the
    sequence itself is edited: an op dropped, repeated, swapped with
    its neighbour, or borrowed from another entry. Answers (spec,
    name)."""
    spec = {"file": spec.get("file"), "ops": list(spec.get("ops") or [])}
    ops = spec["ops"]
    which = rng.random()
    if which < 0.25:
        text = spec["file"]
        if not isinstance(text, str):
            text = _board_file(*[op[1] for op in ops
                                 if len(op) > 1 and op[0] == "submit"
                                 and isinstance(op[1], dict)
                                 and isinstance(op[1].get("task_id"), str)])
        texts = [{"kind": "text", "data": e["data"]["file"]} for e in corpus
                 if isinstance(e.get("data"), dict)
                 and isinstance(e["data"].get("file"), str)]
        mut = rng.choice(TEXT_MUTATORS)
        spec["file"] = mut(rng, text, texts)
        return spec, "board_file"
    if which < 0.65 and ops:
        i = rng.randrange(len(ops))
        op = list(ops[i])
        if len(op) > 1:
            j = rng.randrange(1, len(op))
            op[j] = p_mutate(rng, op[j], [])
        else:
            op.append(rng.choice(_VALUES))
        ops[i] = op
        return spec, "board_arg"
    edit = rng.choice(("drop", "repeat", "swap", "borrow"))
    if edit == "drop" and ops:
        del ops[rng.randrange(len(ops))]
    elif edit == "repeat" and ops:
        i = rng.randrange(len(ops))
        ops.insert(i, copy.deepcopy(ops[i]))
    elif edit == "swap" and len(ops) > 1:
        i = rng.randrange(len(ops) - 1)
        ops[i], ops[i + 1] = ops[i + 1], ops[i]
    else:
        pool = [op for e in corpus if isinstance(e.get("data"), dict)
                for op in (e["data"].get("ops") or [])]
        if pool:
            ops.insert(rng.randint(0, len(ops)), copy.deepcopy(rng.choice(pool)))
        edit = "borrow"
    return spec, "board_" + edit


def _inbox_mutate(rng, spec, corpus, modes=True):
    """An inbox entry's data is {files: [...]}: one file's text
    takes the text set, a name is respelled, a file is dropped,
    repeated under another name, borrowed from another entry, or
    turned into a link, a directory or a filler of some size.
    Answers (spec, name)."""
    files = [dict(f) for f in (spec.get("files") or []) if isinstance(f, dict)]
    mode = spec.get("mode") if modes else None
    which = rng.random()
    if which < 0.08 and modes:
        return _chan_spec(files, rng.choice(_CHANNEL_MODES)), "chan_mode"
    if which < 0.45 and any("text" in f for f in files):
        i = rng.choice([i for i, f in enumerate(files) if "text" in f])
        texts = [{"kind": "text", "data": f["text"]}
                 for e in corpus if isinstance(e.get("data"), dict)
                 for f in (e["data"].get("files") or [])
                 if isinstance(f, dict) and isinstance(f.get("text"), str)]
        mut = rng.choice(TEXT_MUTATORS)
        files[i]["text"] = mut(rng, files[i]["text"], texts)
        return _chan_spec(files, mode), "chan_text"
    if which < 0.6 and files:
        i = rng.randrange(len(files))
        name = files[i].get("name") or "bm"
        edit = rng.choice(("suffix", "nosuffix", "case", "dots", "long",
                           "prefix"))
        if edit == "suffix":
            name = name + ".job.txt"
        elif edit == "nosuffix":
            name = name[:-len(".job.txt")] if name.endswith(".job.txt") \
                else name + ".txt"
        elif edit == "case":
            name = name.swapcase()
        elif edit == "dots":
            name = name.replace("-", ".")
        elif edit == "long":
            name = (name + "-" * 70)[:64]
        else:
            name = rng.choice("0aZ") + name
        files[i]["name"] = name
        return _chan_spec(files, mode), "chan_name"
    edit = rng.choice(("drop", "repeat", "borrow", "link", "dir", "fill"))
    if edit == "drop" and files:
        del files[rng.randrange(len(files))]
    elif edit == "repeat" and files:
        twin = dict(rng.choice(files))
        twin["name"] = "bm-twin-%04d" % rng.randrange(10000) + \
            rng.choice(("", ".job.txt"))
        files.append(twin)
    elif edit == "borrow":
        pool = [f for e in corpus if isinstance(e.get("data"), dict)
                for f in (e["data"].get("files") or []) if isinstance(f, dict)]
        if pool:
            files.append(dict(rng.choice(pool)))
    elif edit == "link" and files:
        f = files[rng.randrange(len(files))]
        f.pop("text", None); f.pop("dir", None); f.pop("fill", None)
        f["link"] = rng.choice(["/srv/example/nowhere", "done", ".",
                                "../outbox", rng.choice(files).get("name", "x")])
    elif edit == "dir" and files:
        f = files[rng.randrange(len(files))]
        f.pop("text", None); f.pop("link", None); f.pop("fill", None)
        f["dir"] = True
    elif files:
        f = files[rng.randrange(len(files))]
        f.pop("text", None); f.pop("link", None); f.pop("dir", None)
        f["fill"] = rng.choice([0, 1, 2, 1024, TR.FILE_MAX_BYTES - 1,
                                TR.FILE_MAX_BYTES, TR.FILE_MAX_BYTES + 1])
        edit = "fill"
    return _chan_spec(files, mode), "chan_" + edit


def _chan_spec(files, mode):
    spec = {"files": files}
    if mode in _CHANNEL_MODES:
        spec["mode"] = mode
    return spec


def pick(rng, pool, weights=None):
    """One mutator from a pool: uniformly, or by the weights a grow
    keeps per mutator name (a saturated mutator keeps a floor share,
    never none: steered, not abandoned)."""
    if not weights:
        return rng.choice(pool)
    ws = [weights.get(m.__name__, 1.0) for m in pool]
    return rng.choices(pool, weights=ws)[0]


def mutate(rng, entry, corpus, target, weights=None):
    """One child of an entry: (data, mutator name), or None when the
    mutation is a no-op or breaks the size caps. A payload child is
    read back through JSON before it is checked, so the checker sees
    exactly what the corpus file will carry. `weights`, when given,
    steer the choice within the text and payload pools."""
    if entry["kind"] == "text":
        if target == "mail":
            pool = MAIL_MUTATORS
        elif target == "dtls":
            pool = DTLS_MUTATORS
        else:
            pool = TEXT_MUTATORS
        mut = pick(rng, pool, weights)
        data = mut(rng, entry["data"], corpus)
        name = mut.__name__
        if len(data.encode("utf-8", "surrogatepass")) > MAX_TEXT:
            return None
    elif target == "crypto":
        data = _crypto_mutate(rng, entry["data"], corpus)
        name = "crypto"
    elif target == "board_ops":
        data, name = _board_mutate(rng, entry["data"], corpus)
    elif target == "inbox":
        data, name = _inbox_mutate(rng, entry["data"], corpus)
    elif target == "local_inbox":
        data, name = _inbox_mutate(rng, entry["data"], corpus, modes=False)
    else:
        mut = pick(rng, PAYLOAD_MUTATORS, weights)
        data = mut(rng, entry["data"], corpus)
        name = mut.__name__
    if entry["kind"] == "payload":
        try:
            text = json.dumps(data, ensure_ascii=True)
        except (TypeError, ValueError, RecursionError):
            return None
        if len(text) > MAX_PAYLOAD:
            return None
        data = json.loads(text)
    if data == entry["data"]:
        return None
    return data, name


# ------------------------------------------------------------------
# Targets
# ------------------------------------------------------------------

def _src(*parts):
    return os.path.join(ROOT, "runner", *parts)


TARGETS = {
    "wire": {"files": [_src("wire", "verify.py"), _src("wire", "mailbox.py")],
             "check": check_wire, "seeds": seeds_wire},
    "cloud": {"files": [_src("cloud", "send_job.py"),
                        _src("wire", "mailbox.py")],
              "check": check_cloud, "seeds": seeds_cloud},
    "v2": {"files": [_src("wire", "protocol_v2.py")], "check": check_v2,
           "seeds": seeds_v2},
    "crypto": {"files": [_src("wire", "jobcrypto.py")],
               "check": check_crypto, "seeds": seeds_crypto},
    "local": {"files": [_src("runner.py"), _src("wire", "transports.py")],
              "check": check_local, "seeds": seeds_local},
    "stash": {"files": [_src("runner.py")], "check": check_stash,
              "seeds": seeds_stash},
    "mail": {"files": [_src("runner.py"), _src("ops", "mail.py"),
                       _src("wire", "mailbox.py"),
                       _src("transport_extensions", "email", "__main__.py")],
             "check": check_mail, "seeds": seeds_mail},
    "dtls": {"files": [_src("wire", "dtlsproto.py")], "check": check_dtls,
             "seeds": seeds_dtls},
    "board": {"files": [_src("wire", "board.py")], "check": check_board,
              "seeds": seeds_board},
    "board_ops": {"files": [_src("wire", "board.py")],
                  "check": check_board_ops, "seeds": seeds_board_ops},
    "channels": {"files": [_src("wire", "transports.py")],
                 "check": check_channels, "seeds": seeds_channels},
    "manifest": {"files": [_src("ops", "extensions.py")],
                 "check": check_manifest, "seeds": seeds_manifest},
    "inbox": {"files": [_src("wire", "transports.py")],
              "check": check_inbox, "seeds": seeds_inbox},
    "local_inbox": {"files": [_src("runner.py"), _src("ops", "policy.py"),
                              _src("oracle", "senses.py")],
                    "check": check_local_inbox, "seeds": seeds_local_inbox},
    "secret": {"files": [_src("cloud", "send_job.py"),
                         _src("guard", "security.py")],
               "check": check_secret, "seeds": seeds_secret},
}


def corpus_path(target, crashes=False):
    name = target + (".crashes.jsonl" if crashes else ".jsonl")
    return os.path.join(CORPUS_DIR, name)


def header(target):
    return {"bluemonday": 1, "target": target, "Agent-Stamp": STAMP}


def load(path):
    """The entries in a corpus file (the header line dropped)."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "bluemonday" in obj and "data" not in obj:
                continue
            out.append(obj)
    return out


def save(path, target, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(header(target), ensure_ascii=True) + "\n")
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=True, sort_keys=True) + "\n")
    os.replace(tmp, path)


NOTES = []


def note(*parts):
    """What a checker saw beyond accepted or refused -- the key a
    reader chose, a digest of what it returned, an operation's
    answer -- for the instruments that compare one reader with
    another (the survivors tool): two readers that differ in a note
    are told apart even when both accept."""
    NOTES.append(":".join(str(p) for p in parts))


def _digest(value):
    """A short digest of a JSON value, for a note."""
    try:
        text = json.dumps(value, sort_keys=True, ensure_ascii=True,
                          default=str)
    except (TypeError, ValueError):
        text = repr(value)
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def check(target, entry):
    """Run one entry against its target's contract: "accepted" or
    "refused" when the contract held, or a Crash. NOTES holds what
    the checker saw on the way."""
    del NOTES[:]
    return TARGETS[target]["check"](entry)


def runs_path():
    return os.path.join(CORPUS_DIR, "runs.jsonl")


def arcs_path(target):
    return os.path.join(CORPUS_DIR, target + ".arcs.json")


def head_sha():
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=60)
        return out.stdout.decode("ascii", "replace").strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def write_arcs(target, arcs):
    """The arc map a target's corpus reaches, as data in the tree:
    sorted [file, from, to] with the file relative to the repository.
    It is the record of the last seed or grow, not an assertion --
    line numbers move with every edit of the reader."""
    rows = sorted([os.path.relpath(f, ROOT).replace(os.sep, "/"), a, b]
                  for f, a, b in arcs)
    path = arcs_path(target)
    os.makedirs(CORPUS_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"bluemonday": 1, "target": target, "Agent-Stamp": STAMP,
                   "arcs": rows}, fh, ensure_ascii=True, indent=0,
                  separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, path)


def record_run(record):
    """One line per seed or grow in runs.jsonl: what ran, with which
    seed, against which head, and what it found -- the proof of the
    work, replayable from the seed and the corpus before it."""
    path = runs_path()
    os.makedirs(CORPUS_DIR, exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write(json.dumps({"bluemonday": 1, "file": "runs",
                                 "Agent-Stamp": STAMP},
                                ensure_ascii=True) + "\n")
        fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True)
                 + "\n")


def _environment():
    """What produced a record: the interpreter and the platform, so a
    run can be read against the box that made it."""
    import platform
    return {"python": platform.python_version(),
            "platform": f"{platform.system()}-{platform.machine()}"}


def _run_record(kind, target, session, before, added, seconds, **extra):
    record = {
        "kind": kind, "target": target,
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": head_sha()[:12],
        **_environment(),
        "entries_before": before["entries"],
        "entries_after": len(session.entries),
        "arcs_before": before["arcs"],
        "arcs_after": len(session.tracer.arcs),
        "kept": [e["id"] for e in added],
        "crashes": len(session.crashes),
        "outcomes": dict(session.outcomes),
        "slowest_ms": round(session.slowest[0] * 1000),
        "slowest": session.slowest[1],
        "seconds": round(seconds, 1),
    }
    record.update(extra)
    return record


class Session:
    """One target's corpus in memory, with the tracer and the rig."""

    def __init__(self, target, entries=None):
        self.target = target
        self.spec = TARGETS[target]
        self.entries = list(entries or [])
        self.ids = {e["id"] for e in self.entries}
        self.tracer = ArcTracer(self.spec["files"])
        self.crashes = []
        self.slowest = (0.0, None)
        self.outcomes = {"accepted": 0, "refused": 0, "crash": 0}
        self.tried = 0
        self.mutators_tried = {}
        self.mutators_kept = {}

    def run(self, entry, trace=True):
        """(outcome, new_arcs, seconds) of one entry; a Crash is
        recorded and reported as the outcome "crash"."""
        t0 = time.perf_counter()
        try:
            if trace:
                outcome = self.tracer.run(check, self.target, entry)
                new = self.tracer.new
            else:
                outcome = check(self.target, entry)
                new = 0
        except Crash as c:
            outcome = "crash"
            new = 0
            self.crashes.append((entry, c))
        dt = time.perf_counter() - t0
        if dt > self.slowest[0]:
            self.slowest = (dt, entry["id"])
        self.outcomes[outcome] += 1
        return outcome, new, dt

    def baseline(self):
        """Replay the corpus under the tracer so growth measures
        against what the corpus already reaches."""
        for e in self.entries:
            self.run(e)

    def grow(self, rng, rounds, log=None, history=None, archive=None):
        """Mutate from the corpus for `rounds` children; keep each one
        that reaches a new arc. Returns the entries added. `history`
        is {name: (tried, kept)} from earlier grows of this target,
        and with it the choice of mutator is steered toward the ones
        still finding arcs (Muse, 2026-10-26: saturation is per
        mutator). `archive`, when given, is called with a record of
        every child tried, kept or not."""
        added = []
        self.tried = 0
        self.mutators_tried = {}
        self.mutators_kept = {}
        if not self.entries:
            return added
        history = dict(history or {})
        weights = steering(history) if history else None
        for n in range(rounds):
            parent = rng.choice(self.entries)
            child = mutate(rng, parent, self.entries, self.target, weights)
            if child is None:
                continue
            data, name = child
            entry = make_entry(parent["kind"], data, parent["id"], name)
            if entry["id"] in self.ids:
                continue
            self.tried += 1
            self.mutators_tried[name] = self.mutators_tried.get(name, 0) + 1
            outcome, new, dt = self.run(entry)
            if archive is not None:
                archive({"id": entry["id"], "from": parent["id"],
                         "mutator": name, "kind": entry["kind"],
                         "data": data, "outcome": outcome, "arcs": new,
                         "ms": round(dt * 1000, 3),
                         "crash": str(self.crashes[-1][1])
                         if outcome == "crash" else None})
            if outcome == "crash":
                if log:
                    log(f"  crash at round {n}: {self.crashes[-1][1]}")
                continue
            tried, kept = history.get(name, (0, 0))
            history[name] = (tried + 1, kept + (1 if new else 0))
            if new:
                entry["arcs"] = new
                self.entries.append(entry)
                self.ids.add(entry["id"])
                added.append(entry)
                self.mutators_kept[name] = self.mutators_kept.get(name, 0) + 1
                if log:
                    log(f"  +{new:3d} arcs  {name:14s} {entry['id']}  "
                        f"({outcome})")
            if weights is not None and self.tried % 200 == 0:
                weights = steering(history)
        return added

    def shrink(self, entry, crash):
        """Smaller inputs that still crash the same way, by greedy
        deletion within SHRINK_BUDGET checks (text entries only)."""
        if entry["kind"] != "text":
            return entry
        text = entry["data"]
        budget = SHRINK_BUDGET

        def still_crashes(candidate):
            try:
                check(self.target, make_entry("text", candidate,
                                              entry["from"], "shrink"))
            except Crash as c:
                return c.kind == crash.kind
            return False

        chunk = max(1, len(text) // 2)
        while chunk >= 1 and budget > 0:
            i = 0
            progressed = False
            while i < len(text) and budget > 0:
                candidate = text[:i] + text[i + chunk:]
                budget -= 1
                if candidate != text and still_crashes(candidate):
                    text = candidate
                    progressed = True
                else:
                    i += chunk
            if not progressed:
                chunk //= 2
        if text == entry["data"]:
            return entry
        return make_entry("text", text, entry["id"], "shrink")


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def _targets(arg):
    if arg in (None, "all"):
        return list(TARGETS)
    if arg not in TARGETS:
        sys.exit(f"unknown target {arg!r}; one of {', '.join(TARGETS)}")
    return [arg]


def _with_rig(fn):
    global _RIG
    with _LocalRig() as rig:
        _RIG = rig
        try:
            return fn()
        finally:
            _RIG = None


def _record_crashes(target, session, out):
    if not session.crashes:
        return 0
    path = corpus_path(target, crashes=True)
    existing = load(path)
    known = {e["id"] for e in existing}
    fresh = 0
    for entry, crash in session.crashes:
        small = session.shrink(entry, crash)
        record = dict(small)
        record.update({"crash": crash.kind, "detail": crash.detail,
                       "found": datetime.now(timezone.utc).strftime(
                           "%Y-%m-%d")})
        if record["id"] in known:
            continue
        known.add(record["id"])
        existing.append(record)
        fresh += 1
        out(f"  CRASH {target} {record['id']}: {crash}")
    if fresh:
        save(path, target, existing)
        out(f"  {fresh} crash(es) written to {os.path.relpath(path, ROOT)}")
    return fresh


def cmd_seed(args, out=print):
    """Write the seeds. An existing corpus keeps every entry it has;
    seeds it lacks are added (so a new seed function never discards
    what the grows found)."""
    for target in _targets(args.target):
        existing = load(corpus_path(target))
        session = Session(target, existing)
        names = {e["from"] for e in existing}
        fresh = [e for e in TARGETS[target]["seeds"]()
                 if e["id"] not in session.ids and e["from"] not in names]
        for e in fresh:
            session.entries.append(e)
            session.ids.add(e["id"])
        t0 = time.perf_counter()
        _with_rig(session.baseline)
        for e in fresh:
            e["arcs"] = 0
        save(corpus_path(target), target, session.entries)
        write_arcs(target, session.tracer.arcs)
        record_run(_run_record(
            "seed", target, session, {"entries": len(existing), "arcs": 0},
            fresh, time.perf_counter() - t0, seeds_added=len(fresh)))
        out(f"{target}: {len(fresh)} seeds added to {len(existing)} "
            f"entries, {len(session.tracer.arcs)} arcs, "
            f"{session.outcomes['accepted']} accepted, "
            f"{session.outcomes['refused']} refused, "
            f"{session.outcomes['crash']} crashes")
        _with_rig(lambda: _record_crashes(target, session, out))
    return 0


def grow_commands(targets, rounds, seed, verbose, archive=None,
                  no_steer=False):
    """One `grow` subprocess command per target, for --jobs."""
    out = []
    for target in targets:
        cmd = [sys.executable, os.path.abspath(__file__), "grow",
               "--target", target, "--rounds", str(rounds),
               "--seed", str(seed), "--jobs", "1"]
        if verbose:
            cmd.append("--verbose")
        if archive:
            cmd += ["--archive", archive]
        if no_steer:
            cmd.append("--no-steer")
        out.append((target, cmd))
    return out


class Archive:
    """Every child a grow tried, kept or not, as gzip JSON lines on a
    disk outside the tree (Muse's offer, 2026-10-26): the search
    itself, where the corpus keeps only what it found. The run
    record carries the file's name, size, digest and count, so the
    tree says where the rest of the proof is."""

    def __init__(self, directory, target, seed):
        import gzip
        os.makedirs(directory, exist_ok=True)
        when = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.name = f"{target}-{when}-{seed}.jsonl.gz"
        self.path = os.path.join(directory, self.name)
        self.count = 0
        self._fh = gzip.open(self.path, "wt", encoding="utf-8",
                             newline="\n")
        self._fh.write(json.dumps({"bluemonday": 1, "archive": target,
                                   "seed": seed, "Agent-Stamp": STAMP},
                                  ensure_ascii=True) + "\n")

    def add(self, record):
        self._fh.write(json.dumps(record, ensure_ascii=True,
                                  sort_keys=True) + "\n")
        self.count += 1

    def close(self):
        self._fh.close()
        digest = hashlib.sha384()
        with open(self.path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                digest.update(chunk)
        return {"file": self.name, "bytes": os.path.getsize(self.path),
                "sha384": digest.hexdigest(), "tried": self.count}


def run_parallel(commands, jobs, out=print, spawn=None, minutes=0.0,
                 clock=time.monotonic, nap=0.2):
    """Run the commands `jobs` at a time, launching the next the moment
    any one finishes, so every core stays busy; each command's output
    is printed whole when it finishes. With `minutes` > 0 the list is
    cycled -- a finished command goes back on the queue -- until the
    time is up, and nothing new is started after that; what is
    running finishes. Returns the worst exit status. `spawn` is
    subprocess.Popen unless a test hands in its own."""
    import subprocess
    spawn = spawn or (lambda cmd: subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
    deadline = clock() + minutes * 60.0 if minutes else None
    pending = list(commands)
    running = []
    status = 0
    while pending or running:
        while pending and len(running) < max(1, jobs) and (
                deadline is None or clock() < deadline):
            target, cmd = pending.pop(0)
            running.append((target, cmd, spawn(cmd)))
        finished = [r for r in running if r[2].poll() is not None]
        if not finished:
            if not running:
                break
            time.sleep(nap)
            continue
        for item in finished:
            running.remove(item)
            target, cmd, proc = item
            output, _ = proc.communicate()
            text = output.decode("utf-8", "replace") if isinstance(
                output, bytes) else (output or "")
            for line in text.rstrip().splitlines():
                out(line)
            status = max(status, proc.returncode or 0)
            if deadline is not None and clock() < deadline:
                pending.append((target, _next_seed(cmd)))
    return status


def _next_seed(cmd):
    """The same command with its --seed moved on by one, so a cycled
    target draws new children instead of the last cycle's."""
    cmd = list(cmd)
    if "--seed" in cmd:
        i = cmd.index("--seed") + 1
        cmd[i] = str(int(cmd[i]) + 1)
    return cmd


def cmd_grow(args, out=print):
    rounds = args.rounds
    if rounds is None:
        rounds = int(os.environ.get("HP_BLUEMONDAY_ROUNDS", DEFAULT_ROUNDS))
    seed = args.seed if args.seed is not None else \
        int.from_bytes(os.urandom(4), "big")
    targets = _targets(args.target)
    minutes = getattr(args, "minutes", 0) or 0
    if (args.jobs > 1 and len(targets) > 1) or minutes:
        # Each target owns its corpus file, so the targets grow in
        # parallel processes: on the rig that is the difference
        # between one core busy and all of them. With --minutes the
        # targets cycle until the time is up: the continuous grow
        # that fills the gap between a measure and a pass.
        out(f"blueMonday grow: {rounds} rounds, rng seed {seed}, "
            f"{min(args.jobs, len(targets))} targets at a time"
            + (f", for {minutes:g} minutes" if minutes else ""))
        return run_parallel(grow_commands(targets, rounds, seed,
                                          args.verbose,
                                          getattr(args, "archive", None),
                                          getattr(args, "no_steer", False)),
                            args.jobs, out=out, minutes=minutes)
    out(f"blueMonday grow: {rounds} rounds, rng seed {seed}")
    status = 0
    for target in targets:
        rng = random.Random(seed)
        entries = load(corpus_path(target))
        if not entries:
            out(f"{target}: no corpus; run `seed` first")
            status = 2
            continue
        session = Session(target, entries)
        t0 = time.perf_counter()
        no_steer = getattr(args, "no_steer", False)
        where = getattr(args, "archive", None)
        history = None if no_steer else mutator_history(target)
        archive = Archive(where, target, seed) if where else None

        def work():
            session.baseline()
            before = len(session.tracer.arcs)
            added = session.grow(rng, rounds, log=out if args.verbose
                                 else None, history=history,
                                 archive=archive.add if archive else None)
            return before, added
        try:
            before, added = _with_rig(work)
        finally:
            archived = archive.close() if archive else None
        if added:
            save(corpus_path(target), target, session.entries)
        write_arcs(target, session.tracer.arcs)
        extra = {}
        if archived:
            extra["archive"] = archived
        if history is not None:
            extra["steered"] = True
        record_run(_run_record(
            "grow", target, session,
            {"entries": len(entries), "arcs": before}, added,
            time.perf_counter() - t0, rounds=rounds, seed=seed,
            tried=session.tried, mutators_tried=session.mutators_tried,
            mutators_kept=session.mutators_kept, **extra))
        out(f"{target}: {len(entries)} -> {len(session.entries)} entries, "
            f"arcs {before} -> {len(session.tracer.arcs)}, "
            f"{session.outcomes['crash']} crashes, slowest "
            f"{session.slowest[0] * 1000:.0f} ms ({session.slowest[1]})")
        if _with_rig(lambda: _record_crashes(target, session, out)):
            status = 1
    return status


def cmd_replay(args, out=print):
    status = 0
    for target in _targets(args.target):
        entries = load(corpus_path(target))
        session = Session(target, entries)
        _with_rig(lambda: [session.run(e, trace=False) for e in entries])
        out(f"{target}: {len(entries)} entries, "
            f"{session.outcomes['accepted']} accepted, "
            f"{session.outcomes['refused']} refused, "
            f"{session.outcomes['crash']} crashes, slowest "
            f"{session.slowest[0] * 1000:.0f} ms ({session.slowest[1]})")
        for entry, crash in session.crashes:
            out(f"  CRASH {entry['id']} ({entry['from']}, "
                f"{entry['mutator']}): {crash}")
            status = 1
    return status


def _one_outcome(target, entry):
    """accepted, refused, or crash:<kind>. An unexpected exception
    is its type, so a surface that breaks the checker is visible."""
    try:
        return check(target, entry)
    except Crash as exc:
        return "crash:" + exc.kind
    except Exception as exc:
        return "error:" + type(exc).__name__


def platform_disagreements(target):
    """Entries whose answer changes under the simulated Windows
    surface (Q71). Empty means the reader agrees with itself.

    The surface is the host identity and the APIs Windows lacks
    (runner/tools/windows_surface.py). It does not swap in
    ntpath, so this is not a path-separator proof. When the
    surface is already on, the second pass is the same surface
    and this reports nothing new."""
    from runner.tools.windows_surface import apply_surface
    entries = load(corpus_path(target))
    host = {}

    def host_pass():
        for entry in entries:
            host[entry["id"]] = _one_outcome(target, entry)

    _with_rig(host_pass)
    windows = {}
    restore = apply_surface()
    try:
        def windows_pass():
            for entry in entries:
                windows[entry["id"]] = _one_outcome(target, entry)

        _with_rig(windows_pass)
    finally:
        restore()
    out = []
    for entry in entries:
        if host[entry["id"]] != windows[entry["id"]]:
            out.append((entry, host[entry["id"]], windows[entry["id"]]))
    return out


def cmd_platform(args, out=print):
    """Replay every committed entry on the host and again under
    the simulated Windows surface. A changed answer is a
    differential and a non-zero status."""
    status = 0
    for target in _targets(args.target):
        bad = platform_disagreements(target)
        entries = load(corpus_path(target))
        out(f"{target}: {len(entries)} entries, "
            f"{len(bad)} disagreements")
        for entry, host, windows in bad:
            out(f"  DIFFER {entry['id']} ({entry['from']}, "
                f"{entry['mutator']}): host {host}, windows {windows}")
            status = 1
    return status


def cmd_promote(args, out=print):
    """After a fix: a crash on file that now meets its contract and
    reaches an arc the corpus did not (the refusal the fix added)
    moves into the corpus; a fixed one reaching nothing new is
    dropped; the ones still crashing stay where they are."""
    status = 0
    for target in _targets(args.target):
        path = corpus_path(target, crashes=True)
        crashes = load(path)
        if not crashes:
            continue
        entries = load(corpus_path(target))
        session = Session(target, entries)
        keep, moved, redundant = [], [], []

        def work():
            session.baseline()
            for record in crashes:
                entry = {k: record[k] for k in
                         ("id", "kind", "data", "from", "mutator", "arcs")}
                if entry["id"] in session.ids:
                    continue
                outcome, new, _dt = session.run(entry)
                if outcome == "crash":
                    keep.append(record)
                    continue
                if not new:
                    redundant.append(entry)
                    continue
                entry["arcs"] = new
                entry["mutator"] = "promoted:" + record.get("crash", "")
                session.entries.append(entry)
                session.ids.add(entry["id"])
                moved.append(entry)
        _with_rig(work)
        session.crashes = []
        if moved:
            save(corpus_path(target), target, session.entries)
        if keep:
            save(path, target, keep)
        else:
            os.remove(path)
        out(f"{target}: {len(moved)} promoted, {len(redundant)} redundant "
            f"(fixed, reaching nothing new), {len(keep)} still crash")
        if keep:
            status = 1
    return status


def last_grow(target):
    """The newest grow record for a target in runs.jsonl (by the time
    it ran), or None."""
    last = None
    for record in load_runs():
        if record.get("kind") == "grow" and record.get("target") == target:
            if last is None or str(record.get("when", "")) >= str(
                    last.get("when", "")):
                last = record
    return last


def load_runs():
    path = runs_path()
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                obj = json.loads(line)
                if "kind" in obj:
                    out.append(obj)
    return out


STEER_FLOOR = 0.1          # a saturated mutator's share of the best one's


def steering(history):
    """Weights per mutator name from {name: (tried, kept)}: the keep
    rate with a prior, floored at STEER_FLOOR of the best, so the
    rounds go where the arcs still are and no mutator is abandoned."""
    rates = {name: (kept + 1) / (tried + 4) for name, (tried, kept)
             in history.items()}
    if not rates:
        return None
    best = max(rates.values())
    return {name: max(rate, best * STEER_FLOOR) for name, rate in rates.items()}


def mutator_history(target, grows=5):
    """{name: (tried, kept)} summed over the last `grows` grow records
    of a target, the memory a steered grow starts from."""
    # By the time each grow ran, not by its place in the file: the
    # records of several lanes merge in commit order.
    recs = sorted((r for r in load_runs()
                   if r.get("kind") == "grow" and r.get("target") == target),
                  key=lambda r: str(r.get("when", "")))
    history = {}
    for rec in recs[-grows:]:
        tried = rec.get("mutators_tried") or {}
        kept = rec.get("mutators_kept") or {}
        for name, n in tried.items():
            t, k = history.get(name, (0, 0))
            history[name] = (t + int(n), k + int(kept.get(name, 0)))
    return history


def mutator_saturation(target, grows=3, floor=100):
    """(live, saturated): the mutators that kept something over the
    last grows, and the ones tried at least `floor` times that kept
    nothing (Muse, 2026-10-26: saturation is per mutator, and a
    target reads unsaturated while one of its mutators is live)."""
    history = mutator_history(target, grows)
    live = sorted(n for n, (t, k) in history.items() if k)
    saturated = sorted(n for n, (t, k) in history.items()
                       if not k and t >= floor)
    return live, saturated


def saturation(target):
    """"saturated at <rounds> rounds" when the last grow kept nothing
    and reached no new arc (Q65's stop rule: point the next grow at
    the next reader), else what the last grow added."""
    rec = last_grow(target)
    if rec is None:
        return "no grow recorded"
    if not rec.get("kept") and rec.get("arcs_after") == rec.get("arcs_before"):
        return f"saturated at {rec.get('rounds')} rounds ({rec.get('when')})"
    return (f"last grow +{len(rec.get('kept', []))} entries, "
            f"+{rec.get('arcs_after', 0) - rec.get('arcs_before', 0)} arcs "
            f"at {rec.get('rounds')} rounds")


def cmd_stats(args, out=print):
    for target in _targets(args.target):
        entries = load(corpus_path(target))
        crashes = load(corpus_path(target, crashes=True))
        kinds = {}
        muts = {}
        for e in entries:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
            muts[e["mutator"]] = muts.get(e["mutator"], 0) + 1
        top = ", ".join(f"{m} {n}" for m, n in sorted(
            muts.items(), key=lambda kv: -kv[1])[:6])
        live, done = mutator_saturation(target)
        out(f"{target}: {len(entries)} entries ({kinds}), "
            f"{len(crashes)} crashes on file; {saturation(target)}; "
            f"mutators: {top}; live: {', '.join(live) or 'none'}; "
            f"saturated: {', '.join(done) or 'none'}")
    return 0


def cmd_dictionary(args, out=print):
    """Rebuild runner/tests/bluemonday/grammar.json from the drafts."""
    paths = sorted(os.path.join(IETF_DIR, f) for f in os.listdir(IETF_DIR)
                   if f.endswith(".md"))
    g = build_grammar(paths)
    corpora = {t: load(corpus_path(t)) for t in TARGETS}
    g = learn(g, corpora)
    os.makedirs(CORPUS_DIR, exist_ok=True)
    tmp = GRAMMAR_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(g, fh, ensure_ascii=True, indent=1)
        fh.write("\n")
    os.replace(tmp, GRAMMAR_PATH)
    out(f"grammar: {len(g['tokens'])} tokens, {len(g['numbers'])} numbers, "
        f"{len(g['examples'])} examples from {len(paths)} draft(s); "
        f"{len(g['learned'])} learned from the corpora")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("dictionary")
    p.set_defaults(fn=cmd_dictionary)
    for name, fn in (("seed", cmd_seed), ("grow", cmd_grow),
                     ("replay", cmd_replay), ("platform", cmd_platform),
                     ("promote", cmd_promote),
                     ("stats", cmd_stats)):
        p = sub.add_parser(name)
        p.add_argument("--target", default="all",
                       help="one of %s, or all" % ", ".join(TARGETS))
        p.set_defaults(fn=fn)
        if name == "grow":
            p.add_argument("--rounds", type=int, default=None,
                           help="children to try per target "
                                "(HP_BLUEMONDAY_ROUNDS, default %d)"
                                % DEFAULT_ROUNDS)
            p.add_argument("--seed", type=int, default=None,
                           help="rng seed (default: random, printed)")
            p.add_argument("--verbose", action="store_true",
                           help="print every keeper and crash")
            p.add_argument("--jobs", type=int,
                           default=int(os.environ.get(
                               "HP_BLUEMONDAY_JOBS", os.cpu_count() or 1)),
                           help="targets grown at a time, each in its own "
                                "process (HP_BLUEMONDAY_JOBS; the default "
                                "is this box's core count, so a plain grow "
                                "keeps every core busy)")
            p.add_argument("--minutes", type=float, default=0.0,
                           help="keep cycling the targets, --jobs at a "
                                "time, until this many minutes have "
                                "passed; a running grow finishes "
                                "(default 0: one pass over the targets)")
            p.add_argument("--archive", default=os.environ.get(
                               "HP_BLUEMONDAY_ARCHIVE") or None,
                           help="a directory outside the tree that keeps "
                                "every child tried, kept or not, one gzip "
                                "JSON-lines file per grow; the run record "
                                "names it (HP_BLUEMONDAY_ARCHIVE)")
            p.add_argument("--no-steer", action="store_true",
                           help="choose mutators uniformly instead of "
                                "steering toward the ones still finding "
                                "arcs in the last grows")
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
