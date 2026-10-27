#!/usr/bin/env python3
# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Project de_dust: the fuzz corpus against the verifiers (Q62).

    python runner/tools/de_dust_corpus.py seed   [--target T]
    python runner/tools/de_dust_corpus.py grow   [--target T] [--rounds N]
                                                    [--seed S] [--jobs J]
                                                    [--minutes M]
    python runner/tools/de_dust_corpus.py replay [--target T]
    python runner/tools/de_dust_corpus.py platform [--target T]
    python runner/tools/de_dust_corpus.py promote [--target T]
    python runner/tools/de_dust_corpus.py stats  [--target T]

A coverage-guided seed corpus, kept under runner/tests/de_dust/
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
                                         side in nine shapes
    secret   runner/cloud/send_job.py    require_signable_secret and
             runner/guard/security.py    validate_shared_secret on one
                                         candidate secret: the sender's
                                         rule and the runner's agree
    local_inbox  runner/runner.py        _scan_local_inbox over a whole
                                         local inbox as a peer left it:
                                         each .json read once, filed or
                                         refused, removed either way;
                                         the store holds what was filed
    queries  runner/ops/policy.py        apply_result_policy and
             runner/ops/queries.py       answer_queries on a job's
                                         result_policy and its own
                                         output, under every ceiling
    names    runner/guard/filenames.py   validate_file_name and
             runner/runner.py            _safe_job_id on one name a
                                         sender chose; an accepted
                                         file name is staged
    query    runner/ops/queries.py       handle_query_mail on one
                                         query message over a retained
                                         record, through the mail rig
    board_mail runner/ops/startup.py     handle_board_mail on one board
                                         message over a board file,
                                         through the mail rig
    v2_mail  runner/ops/handlers.py      handle_v2_mail on one version 2
                                         message, through the mail rig,
                                         the process set to answer

The contract each target is held to is the one its docstrings
state, never its implementation: a bad body is refused with the
refusal type (ValueError, or JobCryptoError for the envelope
reader) and nothing else; a good body round-trips; the two signers
agree, and the two verifiers of one module agree on what they
trust. An exception of any other type, a return of the wrong
shape, or a disagreement is a crash: it is written to
<target>.crashes.jsonl, shrunk, and the command exits 1. The
campaign files each crash as an expectedFailure probe with a Q
(see runner/tests/test_de_dust_corpus.py), and this lane fixes
the reader.

The corpus grows the way the job-fuzz extension's mutators grow a
job: an entry is kept when its execution reaches a line arc no
earlier entry reached, measured with sys.settrace over the target's
own files only. `seed` writes the suite-style fixtures (signed
jobs, an exec job, a sensor alert, v2 messages, an encryption
envelope, and the preamble, trailer, CRLF and control-character
forms the mail path must survive) and, on a corpus that exists,
adds only the seeds it lacks. `grow` mutates from the corpus
for N rounds (HP_DE_DUST_ROUNDS, default 400) and appends the
keepers; the targets grow --jobs at a time in their own processes
(HP_DE_DUST_JOBS; the default is the box's core count), the
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
import ntpath
import os
import posixpath
import random
import re
import shutil
import sys
import tempfile
import time
import types
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import filenames as FN  # noqa: E402
from runner.guard import security as SEC  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402
from runner.ops import extensions as EX  # noqa: E402
from runner.ops import handlers as HA  # noqa: E402
from runner.ops import policy as PO  # noqa: E402
from runner.ops import queries as QU  # noqa: E402
from runner.ops import startup as ST  # noqa: E402
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
CORPUS_DIR = os.path.join(ROOT, "runner", "tests", "de_dust")
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
# The default key answers to its fingerprint as well as to the empty
# key id (Q94): the name a sender computes from the secret it holds.
# The map here mirrors build_secrets, so a payload named by that
# fingerprint signs under the default secret, and the keyed verifier
# is expected to choose that name back. Another key's fingerprint
# (FP_OPS) is registered nowhere: a body naming it must be refused.
FP = SEC.key_fingerprint(SECRET)
FP_OPS = SEC.key_fingerprint(OPS)
SECRETS = {"": SECRET, FP: SECRET, "canary-key": SENSE, "ops": OPS}
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
        # The subject is the text asked for, its line breaks (by the
        # header's rule, Python's splitlines) folded to single
        # spaces; nothing else of it is changed.
        folded = " ".join(("[HOMING-PIGEON] result " + raw_id).splitlines())
        if str(smtp.sent[0]["Subject"]) != folded:
            raise Crash("provenance", "the result subject is not the text "
                        "asked for with its line breaks folded: "
                        f"{str(smtp.sent[0]['Subject'])[:60]!r}")
        note("subject", _digest(folded))


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
    note("signed", who, _digest(body))
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
    # The envelope test the readers apply before decrypting: a
    # bool, never a raise, and part of what the entry pins.
    is_env, eexc = _call(JC.is_envelope, spec.get("envelope"))
    if eexc is not None:
        raise Crash("exception", "is_envelope raised "
                    f"{type(eexc).__name__}: {_short(eexc)}")
    if not isinstance(is_env, bool):
        raise Crash("shape", f"is_envelope returned {type(is_env).__name__}")
    note("envelope", is_env)
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
        self.dir = tempfile.mkdtemp(prefix="hp-de_dust-")
        self._patches = [
            mock.patch.object(R, "log", lambda *a, **k: None),
            mock.patch.object(R, "_maybe_wake_oracle",
                              lambda *a, **k: False),
        ]
        # The grep worker (Q84) is one process the runner drops at the
        # end of every query batch, a lifetime the soak holds it to;
        # the corpus holds the reader to its answers, so the rig keeps
        # the one worker for its whole run and drops it on the way out
        # (a replay of thousands of batches would otherwise start a
        # process for each).
        if hasattr(QU, "_drop_worker"):
            self._patches.append(
                mock.patch.object(QU, "_drop_worker", lambda: None))

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        drop = getattr(QU, "_drop_worker", None)
        if callable(drop):
            try:
                drop()
            except Exception:
                pass
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
                     _RIG.dir, body, "de_dust-neighbor")
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
                     text, "de_dust")
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
    with mock.patch.object(BD, "datetime", _StepClock):
        return _board_sequence(spec)


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


def _board_sequence(spec):
    base = tempfile.mkdtemp(prefix="hp-de_dust-board-")
    # What the board logs is part of what the sequence pins: the
    # host's log and vlog are handed in (the board's own seam), each
    # line recorded with the channel it took, the scratch path
    # scrubbed so two runs read the same.
    lines = []

    def _log(msg, level="INFO"):
        lines.append("log:%s:%s" % (level, str(msg).replace(base, "<base>")))

    def _vlog(msg, level=2):
        lines.append("vlog:%s:%s" % (level, str(msg).replace(base, "<base>")))

    BD.set_logger(_log, _vlog)
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
            note(name, _digest(got), _digest(board.tasks))
            again, exc = _call(BD.Board, path)
            if exc is not None:
                raise Crash("exception", "the board file no longer loads "
                            f"after {name}: {type(exc).__name__}: "
                            f"{_short(exc)}")
            if TU._json_safe(board.tasks) != again.tasks \
                    and os.path.exists(path):
                # What save wrote (the JSON-safe form of the board: a
                # NaN a hand-written file carried is null on disk) is
                # what load reads back.
                raise Crash("roundtrip", f"the board file after {name} "
                            "does not read back as the board in memory")
        note("log", _digest(lines))
        return "accepted" if accepted else "refused"
    finally:
        BD.set_logger(None)
        shutil.rmtree(base, ignore_errors=True)


_CHANNEL = "bm-chan"
# The names the checker will write on every platform: a space and
# the portable punctuation inside, so the result id's own cleaning
# (every other character to `_`) is reached.
_CHANNEL_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._ +=@-]{0,63}\Z")
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


_CHANNEL_MODES = ("reply", "reply2", "raise", "none", "hold", "badreply",
                  "bare", "two", "touch")


class _Replies(list):
    """A processor's replies as the core returns them: a sequence
    with `consume`, a `requeue` the channel runs when the envelope
    is to stay for the next cycle, and a `rollback` it runs when
    the ack fails after the replies landed (Q25). Each call is
    counted, so a run that happens where it must not is seen."""

    consume = True

    def __init__(self, calls, replies=(), rollbacks=None):
        super().__init__(replies)
        self.calls = calls
        self.rollbacks = rollbacks if rollbacks is not None else []

    def requeue(self):
        self.calls.append(1)

    def rollback(self):
        self.rollbacks.append(1)


class _Held(_Replies):
    consume = False


def _channel_processor(mode, served, calls, rollbacks=None, inbox=None):
    """The core's side of service_channel, in one of nine shapes:
    reply (a result per parsed envelope, with its target, as the
    core's sequence), reply2 (the same reply as a pair in a plain
    list, no target), raise (every callback fails), none (no
    replies), hold (consume off), badreply (a reply whose write
    raises), bare (a reply whose body has no final newline, the
    writer's to add), two (two replies per envelope, the second
    without a target), touch (every inbox file is rewritten while
    the core holds it, so every ack finds the bytes changed and
    the channel rolls back)."""

    def process(subject, body):
        served.append((subject, body))
        if mode == "touch" and inbox is not None:
            for fname in sorted(os.listdir(inbox)):
                path = os.path.join(inbox, fname)
                if os.path.isfile(path) and not os.path.islink(path):
                    with open(path, "ab") as fh:
                        fh.write(b"\n")
        if mode == "raise":
            raise RuntimeError("the processor failed")
        if mode == "none":
            return None
        if mode == "hold":
            return _Held(calls, rollbacks=rollbacks)
        if subject == "":
            return []
        if mode == "badreply":
            # A body that is not text: the outbox writer raises on
            # it, which is the reply-did-not-land path.
            return _Replies(calls, [(_RESULT_SUBJECT, 123)], rollbacks)
        if mode == "reply2":
            return [(_RESULT_SUBJECT, _RESULT_BODY)]
        if mode == "bare":
            return _Replies(calls, [(_RESULT_SUBJECT,
                                     _RESULT_BODY.rstrip("\n"))], rollbacks)
        if mode == "two":
            return _Replies(calls, [(_RESULT_SUBJECT, _RESULT_BODY,
                                     _RESULT_TARGET),
                                    (_RESULT_SUBJECT, _RESULT_BODY)],
                            rollbacks)
        # The reply carries the job's validated reply_to as the
        # core would pass it; the channel writes it beside the
        # result and derives none of its own (provenance).
        return _Replies(calls, [(_RESULT_SUBJECT, _RESULT_BODY,
                                 _RESULT_TARGET)], rollbacks)

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
    base = tempfile.mkdtemp(prefix="hp-de_dust-chan-")
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
        served, calls, rollbacks = [], [], []
        count, exc = _call(TR.service_channel, base, _CHANNEL,
                           _channel_processor(mode, served, calls,
                                              rollbacks, inbox), record)
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
        elif mode in ("badreply", "touch"):
            stay = parsed
        else:
            stay = set()
        replying = mode in ("reply", "reply2", "bare", "two", "touch")
        left = sorted(os.listdir(inbox))
        if left != sorted(set(dirs) | stay):
            raise Crash("contract", f"after {mode}, the inbox holds "
                        f"{left!r}, not {sorted(set(dirs) | stay)!r}"[:300])
        done = set(os.listdir(paths["inbox_done"]))
        if done != set(expected) - stay:
            raise Crash("contract", f"after {mode}, done holds "
                        f"{sorted(done)!r}"[:300])
        # A held envelope is re-queued; one whose ack found the bytes
        # changed is rolled back; neither runs for an envelope that
        # was consumed and acked.
        want_requeues = 0 if mode == "touch" else len(stay)
        if len(calls) != want_requeues:
            raise Crash("contract", f"after {mode}, requeue ran "
                        f"{len(calls)} times for {want_requeues} held "
                        "envelopes")
        want_rollbacks = len(parsed) if mode == "touch" else 0
        if len(rollbacks) != want_rollbacks:
            raise Crash("contract", f"after {mode}, rollback ran "
                        f"{len(rollbacks)} times, not {want_rollbacks}")
        outbox = sorted(f for f in os.listdir(paths["outbox"])
                        if f.endswith(".txt"))
        targets = [f for f in outbox if f.endswith(".target.txt")]
        results = [f for f in outbox if f not in targets]
        want = len(parsed) * (2 if mode == "two" else 1) if replying else 0
        want_targets = len(parsed) if mode in ("reply", "two", "touch") else 0
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
        layout = sorted(os.path.relpath(os.path.join(d, f), base)
                        .replace(os.sep, "/")
                        for d, _dirs, files in os.walk(base) for f in files)
        note("layout", _digest(layout))
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
    base = tempfile.mkdtemp(prefix="hp-de_dust-lin-")
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
# queries: the result policy and its queries (Q84)
# ------------------------------------------------------------------

_QUERY_PATTERNS = {"canary": r"SECRET-[0-9]+"}
_QUERY_EXEC = {"exit_code": 0, "timed_out": False, "duration_sec": 0.5,
               "runner": "bm-runner", "completed_at": FIXED_AT,
               "stdout_truncated": False, "stderr_truncated": False}
# The owner's ceilings the policy is read under: the four views, the
# ceiling absent, the ceiling not a view.
_QUERY_CEILINGS = ("attested", "summary", "redacted", "full", None, 7)
# The output a queries entry may carry. The grep op runs a pattern of
# the sender's over every line of it, and the plain repeats a pattern
# may keep are bounded only by the text (Q84), so the text is short.
QUERIES_MAX_TEXT = 1024
_LEAK_MIN = 12
# The pattern bound as it is at import, held in a container so a
# replay that puts a mutant of the bound in every module (the
# survivors instrument) leaves this one alone: an entry whose pattern
# the bound names runs over lines cut short, so a reader that fails
# to refuse it answers in bounded time and is still told apart.
_HOSTILE = {"names": SEC.regex_backtracks}
_HOSTILE_LINE = 16


def _query_hostile(declared):
    """True when a grep query in the list carries a pattern the bound
    names (a repeat nested in a repeat, an alternation under one)."""
    if not isinstance(declared, list):
        return False
    for q in declared:
        if isinstance(q, dict) and q.get("op") == "grep" \
                and isinstance(q.get("pattern"), str) \
                and _HOSTILE["names"](q["pattern"]):
            return True
    return False


def _cut_lines(text, width):
    lines = text.split("\n")
    return "\n".join(line[:width] for line in lines)


def _query_text(value):
    """What the job's output is for an entry: text as it is, anything
    else in its JSON form, so a mutated output still varies. The
    streams are what the runner decoded with replacement, so a lone
    surrogate a mutator plants reads as the replacement character."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=True, default=str)
    return value.encode("utf-8", "replace").decode("utf-8")


_QUERY_FIXED_TEXT = json.dumps(dict(_QUERY_EXEC, job_id="bm-q-0001",
                                    kind="exec"), sort_keys=True)


def _query_pieces(out, err):
    """The parts of the output a non-full view must not carry: the
    whole of each stream and every line of them long enough to be
    recognized, less any that is also a fixed member of the result
    (the output may say the completion time)."""
    pieces = set()
    for text in (out, err):
        if len(text) >= _LEAK_MIN:
            pieces.add(text)
        for line in text.splitlines():
            if len(line) >= _LEAK_MIN:
                pieces.add(line)
    return {p for p in pieces if p not in _QUERY_FIXED_TEXT}


def _query_no_leak(what, view, obj, pieces, policy_text):
    """Under summary and attested, nothing of the output is in what
    the runner answers -- unless the sender put it in the policy
    itself, which is the sender's own text coming back."""
    if view not in ("summary", "attested"):
        return
    blob = json.dumps(obj, sort_keys=True, default=str)
    for piece in pieces:
        if piece in blob and piece not in policy_text:
            raise Crash("leak", f"the {what} under {view} carries the "
                        "job's output")


def _query_no_canary(what, view, values):
    """Under redacted, no line handed back matches the owner's
    pattern (the pattern a query echoes is the sender's own)."""
    if view != "redacted":
        return
    pat = re.compile(_QUERY_PATTERNS["canary"])
    for value in values:
        if isinstance(value, str) and pat.search(value):
            raise Crash("leak", f"the {what} under redacted carries the "
                        "canary")


def _query_answers(declared, answers, spent, budget, view, text_lines):
    """The answer list against the query list (PROTOCOL.md section
    10): one answer per query in order, every query spending one,
    each answer a dict that says `op` or `rejected`, the budget's
    refusals after the budget, grep and tail refused as policy under
    the views that never hand lines back, their lines the output's
    own under full, the unavailable ops named as such."""
    if not isinstance(answers, list) or len(answers) != len(declared):
        raise Crash("contract", f"{len(declared)} queries got "
                    f"{len(answers) if isinstance(answers, list) else answers!r}"
                    " answers")
    if spent != len(declared):
        raise Crash("contract", f"{len(declared)} queries spent {spent!r}")
    handed = []
    refused = False
    for i, (q, a) in enumerate(zip(declared, answers)):
        if not isinstance(a, dict) or not ("op" in a or "rejected" in a):
            raise Crash("shape", f"answer {i} is {a!r}"[:200])
        if "rejected" in a:
            refused = True
        if not isinstance(q, dict):
            if a != {"rejected": "unknown_op"}:
                raise Crash("contract", f"a query that is not an object "
                            f"got {a!r}"[:200])
            continue
        if i >= budget:
            if a != {"rejected": "budget"}:
                raise Crash("contract", f"query {i} past the budget of "
                            f"{budget} got {a!r}"[:200])
            continue
        op = q.get("op")
        if op in ("grep", "tail"):
            if view in ("summary", "attested"):
                if a.get("rejected") != "policy":
                    raise Crash("contract", f"{op} under {view} answered "
                                f"{a!r}"[:200])
                continue
            if "rejected" in a:
                continue
            key = "matches" if op == "grep" else "lines"
            lines = a.get(key)
            if not isinstance(lines, list) or not all(
                    isinstance(x, str) for x in lines):
                raise Crash("shape", f"{op} answered {key}={lines!r}"[:200])
            if len(lines) > (100 if op == "grep" else 200):
                raise Crash("contract", f"{op} handed back {len(lines)} lines")
            if view == "full":
                if any(x not in text_lines for x in lines):
                    raise Crash("contract", f"{op} handed back a line the "
                                "output does not have")
                if op == "tail" and lines != text_lines[len(text_lines)
                                                       - len(lines):]:
                    raise Crash("contract", "tail's lines are not the "
                                "output's last lines")
            if op == "grep" and not isinstance(a.get("truncated"), bool):
                raise Crash("shape", "grep's truncated is not a bool")
            handed.extend(lines)
        elif op == "attest":
            if "rejected" not in a and "predicate" not in a:
                raise Crash("shape", f"attest answered {a!r}"[:200])
        elif op == "ask":
            if a.get("rejected") != "inference_unconfigured":
                raise Crash("contract", "ask without a model answered "
                            f"{a!r}"[:200])
        elif op == "senses":
            # Unavailable without a base directory (the queries target);
            # with one (the query target) the alerts filed, none here.
            alerts = a.get("alerts")
            if a.get("rejected") != "senses_unavailable" and not (
                    isinstance(alerts, list)
                    and a.get("count") == len(alerts)):
                raise Crash("contract", f"senses answered {a!r}"[:200])
        elif a != {"rejected": "unknown_op"}:
            raise Crash("contract", f"op {op!r} answered {a!r}"[:200])
    return handed, refused


def check_queries(entry):
    """queries: a job's result_policy -- the view it asks for, its
    queries, its query budget -- and the job's own output, read by
    apply_result_policy and answer_queries under every ceiling the
    owner can set. Contract: neither raises; the view handed back is
    the one asked for, capped at the ceiling, and an unknown or
    absent request is full; the retain flag follows the view; under
    summary and attested nothing of the output comes back, and
    attested blanks the streams; under redacted no line handed back
    matches the owner's pattern; the answers are one per query, each
    query spending one, with the budget's and the policy's refusals
    where section 10 puts them and the lines handed back the
    output's own; the result with its answers signs and verifies as
    a body. Accepted when every query under the full ceiling was
    answered, refused when one was rejected."""
    data = entry["data"]
    if isinstance(data, dict):
        policy = data.get("policy")
        out = _query_text(data.get("output"))
        err = _query_text(data.get("stderr"))
    else:
        policy, out, err = data, "", ""
    if len(out) + len(err) > QUERIES_MAX_TEXT:
        raise Crash("corpus", "a queries entry's output is over the cap")
    if TU._lone_surrogate(policy):
        # The verifier refuses a body with a lone surrogate (Q85), so
        # a policy carrying one never reaches these readers.
        note("gate", "lone surrogate")
        return "refused"
    declared = policy.get("queries") if isinstance(policy, dict) else None
    declared = declared or []
    if not isinstance(declared, list):
        declared = []
    if _query_hostile(declared):
        out, err = _cut_lines(out, _HOSTILE_LINE), _cut_lines(err, _HOSTILE_LINE)
        note("gate", "hostile pattern, lines cut")
    job = {"job_id": "bm-q-0001", "kind": "exec", "result_policy": policy}
    exe = dict(_QUERY_EXEC, stdout=out, stderr=err)
    pieces = _query_pieces(out, err)
    policy_text = json.dumps(policy, sort_keys=True, default=str)
    text_lines = (out + err).splitlines()
    want = policy.get("view") if isinstance(policy, dict) else None
    asked = want if isinstance(want, str) and want in R.VIEW_ORDER else "full"
    refused = False
    for ceiling in _QUERY_CEILINGS:
        cfg = {} if ceiling is None else {"max_result_view": ceiling}
        got, exc = _call(PO.apply_result_policy, cfg, job, exe,
                         _QUERY_PATTERNS, True)
        if exc is not None:
            raise Crash("exception", "apply_result_policy raised "
                        f"{type(exc).__name__} under ceiling {ceiling!r}: "
                        f"{_short(exc)}")
        if not (isinstance(got, tuple) and len(got) == 2
                and isinstance(got[0], dict) and isinstance(got[1], bool)):
            raise Crash("shape", "apply_result_policy returned "
                        f"{type(got).__name__}")
        result, retain = got
        top = ceiling if ceiling in R.VIEW_ORDER else "full"
        expect = asked if R.VIEW_ORDER[asked] <= R.VIEW_ORDER[top] else top
        view = result.get("view")
        if view != expect:
            raise Crash("contract", f"a request of {want!r} under ceiling "
                        f"{ceiling!r} got view {view!r}, not {expect!r}")
        if retain != (view != "full"):
            raise Crash("contract", f"retain is {retain!r} under {view}")
        if view == "attested":
            if result.get("stdout") != "" or result.get("stderr") != "":
                raise Crash("leak", "an attested result carries a stream")
            if not isinstance(result.get("attestations"), list):
                raise Crash("shape", "attested without an attestation list")
        if view == "summary" and "stdout" in result:
            raise Crash("leak", "a summary result carries stdout")
        _query_no_leak("result", view, result, pieces, policy_text)
        _query_no_canary("result", view, [result.get("stdout")])
        budget = R.query_budget(cfg, job)
        ctx = {"stdout": out, "stderr": err, "exit_code": 0,
               "confined": True, "digest": result.get("output_digest")}
        got, exc = _call(QU.answer_queries, declared, ctx, _QUERY_PATTERNS,
                         budget, cfg, view)
        if exc is not None:
            raise Crash("exception", "answer_queries raised "
                        f"{type(exc).__name__} under {view}: {_short(exc)}")
        if not (isinstance(got, tuple) and len(got) == 2):
            raise Crash("shape", f"answer_queries returned {type(got).__name__}")
        answers, spent = got
        handed, rejected = _query_answers(declared, answers, spent, budget,
                                          view, text_lines)
        if ceiling == "full":
            refused = rejected
        _query_no_leak("answers", view, answers, pieces, policy_text)
        _query_no_canary("answers", view, handed)
        signed = dict(result, answers=answers)
        body, exc = _call(V.sign_payload, signed, SECRET)
        if exc is not None:
            raise Crash("contract", "the result with its answers would not "
                        f"sign: {_short(exc)}")
        back, exc = _call(V.verify_body, body, SECRET)
        if exc is not None or not isinstance(back, dict):
            raise Crash("roundtrip", "the signed result does not verify: "
                        f"{_short(exc) if exc else type(back).__name__}")
        note("view", ceiling, view, budget)
        note("result", _digest(result))
        note("answers", _digest(answers))
    return "refused" if refused else "accepted"


# ------------------------------------------------------------------
# query: the query message handler over a retained record
# ------------------------------------------------------------------

_QUERY_CFG = {
    "shared_secret": SECRET,
    "additional_secrets": {"canary-key": SENSE, "ops": OPS},
    "mailbox_user": "runner@example.com",
    "max_job_age_sec": 3600,
    "max_queries_per_hour": 4,
    "output_retention_days": 7,
}
_QUERY_REJECTIONS = ("unsupported", "rate_limit", "expired", "unknown_job",
                     "query_error")
_DEFAULT_RETAINED = {
    "job_id": "bm-job-0001", "kind": "exec", "script": "echo",
    "stdout": "ok\nERROR one\nERROR two\n", "stderr": "", "exit_code": 0,
    "timed_out": False, "duration_sec": 0.5, "view": "full", "budget": 8,
    "spent": 0, "patterns": _QUERY_PATTERNS, "confined": True,
    "digest": "d" * 96, "saved_at": NOW}


class _FakeImap:
    """An IMAP connection that keeps the flags it was asked to store."""

    def __init__(self):
        self.marked = []

    def store(self, seq, flags, value):
        self.marked.append((seq, flags, value))
        return "OK", [b""]


def _query_retained(record):
    """The retained record as the runner would have saved it: the
    saved_at token stamped with the present (so the record is within
    the retention window at check time), anything else as it is."""
    if isinstance(record, dict) and record.get("saved_at") == NOW:
        record = dict(record)
        record["saved_at"] = time.time()
    return record


def _sealed_mail(subject, ident, payload, key_id):
    """A message as the sender seals it: the signed object, encrypted
    under the subject's id, the envelope signed. A sender signing
    under an additional key names it in the object (send_job.py's
    --key-id does), so an object without a key_id member gets the
    key's name; one that carries its own keeps it, mismatch and all."""
    import email.message as _em
    secret = SECRETS.get(key_id, SECRET) if isinstance(key_id, str) \
        else SECRET
    if key_id and isinstance(payload, dict) and "key_id" not in payload:
        payload = dict(payload, key_id=key_id)
    body = V.sign_payload(payload, secret)
    body = JC.encrypt_body(body, secret, ident, key_id or "", V.sign_payload)
    msg = _em.EmailMessage()
    msg["From"] = "si@example.com"
    msg["To"] = "runner@example.com"
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


def _query_mail(subject_id, payload, key_id):
    return _sealed_mail("[HOMING-PIGEON] query " + subject_id, subject_id,
                        payload, key_id)


def _query_open_reply(msg, subject_id, key_id):
    """The object inside a sent reply: verified, decrypted under the
    id the reply was sealed under, verified again."""
    secret = SECRETS.get(key_id, SECRET) if isinstance(key_id, str) \
        else SECRET
    text = msg.get_content()
    outer, exc = _call(V.verify_body, text, secret)
    if exc is not None:
        raise Crash("roundtrip", "the reply does not verify: "
                    f"{_short(exc)}")
    if not JC.is_envelope(outer):
        raise Crash("contract", "the reply to a sealed query is not sealed")
    inner, exc = _call(JC.decrypt_body, outer, secret, subject_id,
                       key_id or "")
    if exc is not None:
        raise Crash("roundtrip", "the reply does not open under the "
                    f"subject's id: {_short(exc)}")
    reply, exc = _call(V.verify_body, inner, secret)
    if exc is not None:
        raise Crash("roundtrip", "the reply's object does not verify: "
                    f"{_short(exc)}")
    return reply


def _query_window(path, spec, key_id):
    """The hourly window as the runner left it before the query, from
    the entry's `window`: a count n writes n live slots under the
    message's key (the sender's own bucket, PROTOCOL section 11);
    text is written as it is (its NOW tokens stamped), a window file
    as a crash left it; anything else leaves no file."""
    if isinstance(spec, bool) or spec is None:
        return
    if isinstance(spec, int):
        n = max(0, min(spec, 64))
        text = json.dumps({key_id or "": [time.time() - 1] * n})
    elif isinstance(spec, str):
        # The NOW token in the text is a slot taken a second ago.
        text = spec.replace(NOW, repr(time.time() - 1))
    else:
        return
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8", "surrogatepass"))


def _query_live(path, key_id):
    """How many live slots the window holds for the key, read as
    check_rate_limit reads it."""
    store = R._read_query_store(path)
    if not isinstance(store, dict):
        return 0
    return len(R._live_times(store.get(key_id or "", []), time.time()))


def _file_text(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _mail_opts(data):
    """The operator's flags an entry names: dry (the handler acks
    nothing and acts on nothing) and no_send (acts, sends nothing)."""
    return types.SimpleNamespace(dry_run=data.get("dry") is True,
                                 no_send=data.get("no_send") is True)


def _mail_form(subject, ident, payload, key_id, data):
    """The message as the entry sends it: sealed, or -- under the
    cleartext flag -- signed only, which the handlers refuse."""
    if data.get("cleartext") is True:
        import email.message as _em
        secret = SECRETS.get(key_id, SECRET) if isinstance(key_id, str) \
            else SECRET
        if key_id and isinstance(payload, dict) and "key_id" not in payload:
            payload = dict(payload, key_id=key_id)
        msg = _em.EmailMessage()
        msg["From"] = "si@example.com"
        msg["To"] = "runner@example.com"
        msg["Subject"] = subject
        msg.set_content(V.sign_payload(payload, secret))
        return msg.as_bytes()
    return _sealed_mail(subject, ident, payload, key_id)


class _MailLog:
    """What a handler logs and records: the log lines (the scratch
    path scrubbed), and the reason and feature of every security
    event it files, so a handler that says or files something else
    is told apart."""

    def __init__(self, base):
        self.base = base
        self.lines = []

    def log(self, msg, level="INFO", *a, **k):
        self.lines.append("%s:%s" % (level, str(msg).replace(self.base, "<base>")))

    def vlog(self, msg, *a, **k):
        self.lines.append("v:" + str(msg).replace(self.base, "<base>"))

    def events(self):
        out = []
        try:
            with open(os.path.join(self.base, "security-events.jsonl"),
                      encoding="utf-8") as fh:
                for line in fh:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        out.append("unreadable")
                        continue
                    out.append((ev.get("type"), ev.get("reason"),
                                ev.get("feature")))
        except OSError:
            pass
        return out

    def note(self):
        note("log", _digest(self.lines), _digest(self.events()))


def check_query(entry):
    """query: one query message -- the subject's id, the signed and
    sealed object a sender chose (its type, version, ids, issued_at
    and queries), under a key -- over the retained record of a job
    as the runner saved it or as a crash left it, through
    handle_query_mail with the mail rig. Contract: the handler
    takes the message (True) and never raises; the message is
    marked seen exactly once; at most one reply goes out, addressed
    to the mailbox under the subject's id, a qresult naming the
    subject's id that verifies and opens under the key, with a list
    of answers and either a known rejection or a budget that is not
    negative; a reply with answers follows the answer contract of
    the queries target (one per query, the lines handed back the
    retained output's own under the retained view, nothing of the
    output under summary or attested); the retained record after
    the query, if the job was known and in its window, is the same
    record with spent and saved_at kept, spent never over the
    budget; a copy of the message is taken without a second reply.
    Accepted when the reply carries no rejection."""
    data = entry["data"]
    if not isinstance(data, dict):
        # A mutator that wrapped or replaced the whole entry: what is
        # left is the message's queries, over the default record.
        data = {"query": data}
    subject_id = data.get("subject_id")
    if not isinstance(subject_id, str) or not subject_id \
            or any(c.isspace() for c in subject_id):
        subject_id = "bm-q-0001"
    payload = _stamp_issued_at(data.get("query"))
    if not isinstance(payload, dict):
        payload = {"v": 1, "type": "query", "query_id": subject_id,
                   "job_id": "bm-job-0001", "issued_at": FIXED_AT,
                   "queries": payload}
    key_id = data.get("key_id") if isinstance(data.get("key_id"), str) \
        and data.get("key_id") in SECRETS else ""
    record = _query_retained(data.get("retained", _DEFAULT_RETAINED))
    if TU._lone_surrogate(payload):
        note("gate", "lone surrogate")
        return "refused"
    subject = "[HOMING-PIGEON] query " + subject_id
    try:
        raw = _mail_form(subject, subject_id, payload, key_id, data)
    except ValueError as e:
        # The sender's own signer refuses the object; the runner
        # never sees it.
        note("gate", "unsignable", _short(e))
        return "refused"
    opts = _mail_opts(data)
    base = tempfile.mkdtemp(prefix="hp-de_dust-query-")
    try:
        planted = _query_plant_senses(base, data.get("senses"))
        if planted:
            note("senses", planted)
        job_id = payload.get("job_id")
        if record is not None and isinstance(job_id, str):
            R.save_retained(base, job_id, record)
        before = R.load_retained(base, job_id) if isinstance(job_id, str) \
            else None
        cfg = dict(_QUERY_CFG)
        secrets = R.build_secrets(cfg)
        window = os.path.join(base, "query_times.json")
        # The window is per key, not per name (Q94): the slots are
        # planted and counted under the one name the runner counts
        # the key under, whichever name the message carries.
        bucket = R.canonical_key_id(secrets, key_id) \
            if isinstance(key_id, str) else key_id
        _query_window(window, data.get("window"), bucket)
        window_before = _file_text(window)
        live_before = _query_live(window, bucket)
        seen = {}
        outs = []
        logbook = _MailLog(base)
        for attempt in (1, 2):
            imap, smtp = _FakeImap(), _FakeSmtp()
            with mock.patch.object(R, "log", logbook.log), \
                    mock.patch.object(R, "vlog", logbook.vlog):
                got, exc = _call(QU.handle_query_mail, cfg, imap, smtp,
                                 attempt, raw, subject, secrets, opts,
                                 base, seen)
            if exc is not None:
                raise Crash("exception", "handle_query_mail raised "
                            f"{type(exc).__name__}: {_short(exc)}")
            if got is not True:
                raise Crash("contract", f"handle_query_mail answered {got!r} "
                            "for a query subject")
            if len(imap.marked) != (0 if opts.dry_run else 1):
                raise Crash("contract", f"the message was marked "
                            f"{len(imap.marked)} times under dry "
                            f"{opts.dry_run}")
            if len(smtp.sent) > 1:
                raise Crash("contract", f"{len(smtp.sent)} replies went out")
            if smtp.sent and (opts.dry_run or opts.no_send):
                raise Crash("contract", "a reply went out under dry or "
                            "no_send")
            outs.append(smtp.sent)
        logbook.note()
        if opts.dry_run and seen:
            raise Crash("contract", "a dry run recorded the query")
        if opts.dry_run and _file_text(window) != window_before:
            raise Crash("contract", "a dry run touched the hourly window "
                        "(Q87)")
        if opts.dry_run and isinstance(job_id, str) \
                and R.load_retained(base, job_id) != before:
            raise Crash("contract", "a dry run spent the retained record's "
                        "budget (Q87)")
        live_after = _query_live(window, bucket)
        note("window", live_before, live_after)
        first, again = outs
        if again:
            raise Crash("contract", "a copy of the query was answered again")
        if not first:
            note("reply", "none", sorted(seen))
            after = R.load_retained(base, job_id) if isinstance(job_id, str) \
                else None
            if after != before and not opts.no_send:
                raise Crash("contract", "a query that got no reply changed "
                            "the retained record")
            return "refused"
        msg = first[0]
        if msg["To"] != _QUERY_CFG["mailbox_user"]:
            raise Crash("provenance", f"the reply is addressed to {msg['To']!r}")
        if str(msg["Subject"]) != "[HOMING-PIGEON] qresult " + subject_id:
            raise Crash("contract", f"the reply's subject is "
                        f"{str(msg['Subject'])[:60]!r}")
        reply = _query_open_reply(msg, subject_id, key_id)
        if not isinstance(reply, dict) or reply.get("type") != "qresult" \
                or reply.get("query_id") != subject_id \
                or not isinstance(reply.get("answers"), list):
            raise Crash("shape", f"the reply is {_short(reply)}"[:200])
        rejected = reply.get("rejected")
        if rejected is not None and rejected not in _QUERY_REJECTIONS:
            raise Crash("contract", f"the reply names rejection {rejected!r}")
        if reply.get("v") != R.PROTOCOL_VERSION:
            raise Crash("shape", f"the reply's version is {reply.get('v')!r}")
        if rejected not in ("unsupported", "rate_limit") \
                and "job_id" not in reply:
            raise Crash("shape", "the reply does not name the job")
        if "job_id" in reply and isinstance(job_id, str) \
                and reply["job_id"] != job_id:
            raise Crash("contract", "the reply names a job other than the "
                        "query's")
        # PROTOCOL section 11: the hourly window is per sender. A
        # query refused before the window is read (unsupported) takes
        # no slot; one refused at the window took none and finds the
        # window full; every other query took exactly one.
        if rejected == "unsupported":
            if live_after != live_before:
                raise Crash("contract", "an unsupported query took a slot "
                            "of the hourly window")
        elif rejected == "rate_limit":
            if live_after > live_before \
                    or live_after < _QUERY_CFG["max_queries_per_hour"]:
                raise Crash("contract", "a query refused at the window "
                            f"left it at {live_after} live of "
                            f"{live_before} (cap "
                            f"{_QUERY_CFG['max_queries_per_hour']})")
        elif live_after != live_before + 1:
            raise Crash("contract", "a query that reached the record took "
                        f"{live_after - live_before} slot(s) of the hourly "
                        "window")
        remaining = reply.get("budget_remaining")
        if remaining is not None and (not isinstance(remaining, int)
                                      or isinstance(remaining, bool)
                                      or remaining < 0):
            raise Crash("contract", f"budget_remaining is {remaining!r}")
        after = R.load_retained(base, job_id) if isinstance(job_id, str) \
            else None
        if rejected is None:
            _query_reply_answers(payload, record, reply, before, after)
            declared = payload.get("queries") \
                if isinstance(payload.get("queries"), list) else []
            _query_senses_rules(declared, reply["answers"], planted)
        elif after != before:
            raise Crash("contract", f"a query rejected as {rejected} changed "
                        "the retained record")
        note("reply", rejected or "answered", _digest(reply.get("answers")),
             remaining, sorted(seen))
        return "refused" if rejected is not None else "accepted"
    finally:
        shutil.rmtree(base, ignore_errors=True)


_SENSE_SCORES = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0,
                 "info": 0.5}


def _query_plant_senses(base, specs):
    """The senses store as the runner left it: the alerts the entry
    names, each through the local ingest under the rig's sensor
    config (what the ingest refuses is not stored); how many were
    stored."""
    if not isinstance(specs, list):
        return 0
    stored = 0
    for n, spec in enumerate(specs[:8]):
        if not isinstance(spec, dict):
            continue
        extra = {k: v for k, v in spec.items() if isinstance(k, str)}
        extra.setdefault("title", f"bm-sense-{n}")
        extra.setdefault("job_id", f"bm-sense-{n:04d}")
        try:
            payload = _stamp_issued_at(_alert(**extra))
        except TypeError:
            continue
        body, exc = _call(V.sign_payload, payload, SENSE)
        if exc is not None:
            continue
        got, exc = _call(R._ingest_local_envelope_inner, LOCAL_CFG, base,
                         body, f"de_dust-sense-{n}")
        if exc is not None:
            raise Crash("exception", "the senses ingest raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if isinstance(got, dict):
            stored += 1
    return stored


def _query_senses_rules(declared, answers, planted):
    """A senses answer against the query that asked it, by the
    checker's own reading of docs/extend/senses.md: never more
    alerts than the limit (20 unasked) or than were stored, each
    from the sensor asked, none below the floor asked (a missing
    severity is info), the list scored highest first, every alert
    carrying the members the Oracle reads."""
    for q, a in zip(declared, answers):
        if not isinstance(q, dict) or q.get("op") != "senses" \
                or not isinstance(a, dict) or "alerts" not in a:
            continue
        alerts = a["alerts"]
        limit = q.get("limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            limit = 20
        if len(alerts) > min(limit, planted):
            raise Crash("contract", f"senses handed back {len(alerts)} "
                        f"alerts over a limit of {limit} with {planted} "
                        "stored")
        want = q.get("sensor") if isinstance(q.get("sensor"), str) else None
        floor = q.get("severity_floor") \
            if isinstance(q.get("severity_floor"), str) else None
        floor_score = _SENSE_SCORES.get(floor, 0.0) if floor else 0.0
        last = None
        for it in alerts:
            if not isinstance(it, dict):
                raise Crash("shape", "a senses alert is not an object")
            for member in ("sensor", "severity", "title", "detail",
                           "observed_at", "received_at", "weight", "score"):
                if member not in it:
                    raise Crash("shape", f"a senses alert lacks {member}")
            if want is not None and it["sensor"] != want:
                raise Crash("contract", "senses handed back an alert of "
                            f"sensor {it['sensor']!r}, asked {want!r}")
            sev = it["severity"] if it["severity"] in _SENSE_SCORES \
                else "info"
            if _SENSE_SCORES[sev] < floor_score:
                raise Crash("contract", f"senses handed back severity {sev} "
                            f"under the floor {floor}")
            score = it["score"]
            if not isinstance(score, (int, float)) or isinstance(score, bool) \
                    or score != score:
                raise Crash("shape", f"a senses alert's score is {score!r}")
            if last is not None and score > last:
                raise Crash("contract", "senses alerts are not highest "
                            "first")
            last = score


def _query_carriable(text):
    """The checker's own rule for a retained stream on the wire: text
    or nothing, a lone surrogate the replacement character."""
    if not isinstance(text, str):
        return ""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-16", "surrogatepass").decode("utf-16",
                                                             "replace")


def _query_reply_answers(payload, record, reply, before, after):
    """A reply with answers against the retained record it read."""
    if not isinstance(before, dict):
        raise Crash("contract", "a query was answered with no retained "
                    "record to read")
    declared = payload.get("queries") or []
    if not isinstance(declared, list):
        declared = []
    answers = reply["answers"]
    view = before.get("view") or "full"
    if not isinstance(view, str) or view not in R.VIEW_ORDER:
        view = "full"
    # A stream is text the wire can carry, or nothing (Q90, Q93): the
    # record a crash left may hold a list or a number where the
    # executor wrote text, or a lone surrogate no signer accepts,
    # which is the replacement character on the wire.
    out = _query_carriable(before.get("stdout"))
    err = _query_carriable(before.get("stderr"))
    text_lines = (out + err).splitlines()
    try:
        budget = int(before.get("budget"))
    except (TypeError, ValueError, OverflowError):
        budget = int(_QUERY_CFG.get("max_query_budget", 8))
    try:
        already = int(before.get("spent") or 0)
    except (TypeError, ValueError, OverflowError):
        already = 0
    free = max(0, budget - already)
    handed, _rejected = _query_answers(declared, answers, len(declared),
                                       free, view, text_lines)
    pieces = _query_pieces(out, err)
    policy_text = json.dumps(payload, sort_keys=True, default=str)
    _query_no_leak("reply", view, reply, pieces, policy_text)
    # The record's own patterns redact its lines; a record without
    # any is redacted under the runner's current ones, which do not
    # know the canary.
    patterns = before.get("patterns")
    if not (isinstance(patterns, dict) and patterns):
        patterns = R._redact_patterns(_QUERY_CFG)
    if _QUERY_PATTERNS["canary"] in patterns.values():
        _query_no_canary("reply", view, handed)
    if not isinstance(after, dict):
        raise Crash("contract", "the retained record is gone after an "
                    "answered query")
    spent = after.get("spent")
    if not isinstance(spent, int) or isinstance(spent, bool) \
            or spent != already + len(declared):
        raise Crash("contract", f"spent is {spent!r} after {len(declared)} "
                    f"queries on {already}")
    if reply.get("budget_remaining") != max(0, budget - spent):
        raise Crash("contract", "budget_remaining does not follow the "
                    "record's budget and spent")
    kept = {k: v for k, v in after.items() if k not in ("spent", "saved_at")}
    was = {k: v for k, v in before.items() if k not in ("spent", "saved_at")}
    if kept != was:
        raise Crash("contract", "an answered query changed the retained "
                    "record beyond spent and saved_at")


# ------------------------------------------------------------------
# board_mail: the board message handler over a board file
# ------------------------------------------------------------------

_BOARD_MAIL_KINDS = ("task_submit", "task_request", "task_result",
                     "task_approve")
_BOARD_MAIL_CFG = {
    "shared_secret": SECRET,
    "additional_secrets": {"canary-key": SENSE, "ops": OPS},
    "mailbox_user": "runner@example.com",
    "max_job_age_sec": 3600,
    "worker_allowlist": ["worker-a", "worker-b"],
    "worker_compartments": {"worker-a": ["blue"]},
    "dag_mode": "enforce",
    "task_timeout": 86400,
}


def check_board_mail(entry):
    """board_mail: one board message -- its kind and subject id, the
    sealed object a sender chose, the key -- over a board file as the
    runner saved it or as a crash left it, through handle_board_mail
    with the mail rig, twice. Contract: the handler takes the message
    (True) and never raises; the message is marked seen exactly
    once; at most one reply goes out, addressed to a single plain
    address from inside the signed body or to the mailbox, sealed
    under its own subject's last word and opening under the key; the
    reply is the ack or offer section 13 describes for the kind (an
    ack naming the subject's id with ok and reason, or status and
    reason; an offer carrying a task whose id is the reply subject's,
    or empty under the empty subject); the board file reads back as a
    dict of dict tasks after the message, a task offered claimed on
    it under the id it carries; a second copy of the message is taken
    without raising. Accepted when the reply says ok, done,
    pending_review or carries a task."""
    data = entry["data"]
    if not isinstance(data, dict):
        data = {"payload": data}
    kind = data.get("kind")
    if kind not in _BOARD_MAIL_KINDS:
        kind = "task_submit"
    ident = data.get("ident")
    if not isinstance(ident, str) or not ident \
            or any(c.isspace() for c in ident):
        ident = "bm-task-0001"
    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {"v": 1, "type": kind, "task_id": ident, "result": payload}
    key_id = data.get("key_id") if isinstance(data.get("key_id"), str) \
        and data.get("key_id") in SECRETS else ""
    cfg = dict(_BOARD_MAIL_CFG)
    if data.get("review") is True:
        cfg["require_review"] = True
    if "timeout" in data:
        # The lease length as the owner wrote it, whatever that is:
        # the handler reads it through the board's own guard.
        cfg["task_timeout"] = data["timeout"]
    if TU._lone_surrogate(payload):
        note("gate", "lone surrogate")
        return "refused"
    subject = f"[HOMING-PIGEON] {kind} {ident}"
    try:
        raw = _mail_form(subject, ident, payload, key_id, data)
    except ValueError as e:
        note("gate", "unsignable", _short(e))
        return "refused"
    opts = _mail_opts(data)
    base = tempfile.mkdtemp(prefix="hp-de_dust-bmail-")
    _StepClock._tick = 0
    try:
        path = os.path.join(base, "board.json")
        text = data.get("file")
        if isinstance(text, str):
            with open(path, "wb") as fh:
                fh.write(text.encode("utf-8", "surrogatepass"))
        with mock.patch.object(BD, "datetime", _StepClock):
            board, exc = _call(BD.Board, path)
            if exc is not None:
                raise Crash("exception", f"Board() raised {type(exc).__name__}: "
                            f"{_short(exc)}")
            secrets = R.build_secrets(cfg)
            replies = []
            # The board as each reply left it: a reply is judged
            # against the board at the moment it went out, not after
            # the second copy moved it again (Q97: a zero lease
            # re-offers a claim at once).
            states = []
            logbook = _MailLog(base)
            start = _digest(board.tasks)
            for attempt in (1, 2):
                imap, smtp = _FakeImap(), _FakeSmtp()
                with mock.patch.object(R, "log", logbook.log), \
                        mock.patch.object(R, "vlog", logbook.vlog), \
                        mock.patch.object(BD, "log", lambda *a, **k: None), \
                        mock.patch.object(BD, "vlog", lambda *a, **k: None):
                    got, exc = _call(ST.handle_board_mail, cfg, imap, smtp,
                                     attempt, raw, subject, board, secrets,
                                     opts, base)
                if exc is not None:
                    raise Crash("exception", "handle_board_mail raised "
                                f"{type(exc).__name__}: {_short(exc)}")
                if got is not True:
                    raise Crash("contract", f"handle_board_mail answered "
                                f"{got!r} for a board subject")
                if len(imap.marked) != (0 if opts.dry_run else 1):
                    raise Crash("contract", "the message was marked "
                                f"{len(imap.marked)} times under dry "
                                f"{opts.dry_run}")
                if len(smtp.sent) > 1:
                    raise Crash("contract", f"{len(smtp.sent)} replies went out")
                if smtp.sent and (opts.dry_run or opts.no_send):
                    raise Crash("contract", "a reply went out under dry or "
                                "no_send")
                if opts.dry_run and _digest(board.tasks) != start:
                    raise Crash("contract", "a dry run moved the board (Q87)")
                replies.append(smtp.sent[0] if smtp.sent else None)
                states.append({k: v.get("state") for k, v
                               in board.tasks.items() if isinstance(v, dict)})
                again, exc = _call(BD.Board, path)
                if exc is not None:
                    raise Crash("exception", "the board file no longer loads: "
                                f"{type(exc).__name__}: {_short(exc)}")
                if not isinstance(again.tasks, dict) or not all(
                        isinstance(k, str) and isinstance(v, dict)
                        for k, v in again.tasks.items()):
                    raise Crash("shape", "the board file reads back as "
                                "something other than a dict of dict tasks")
                if os.path.exists(path) \
                        and TU._json_safe(board.tasks) != again.tasks:
                    raise Crash("roundtrip", "the board file does not read "
                                "back as the board in memory")
            logbook.note()
            outcome = "refused"
            for i, msg in enumerate(replies):
                if msg is None:
                    note("reply", i, "none")
                    continue
                target = MB._valid_reply_to(payload)
                if msg["To"] != (target or cfg["mailbox_user"]):
                    raise Crash("provenance", f"the reply is addressed to "
                                f"{msg['To']!r}")
                rsubject = str(msg["Subject"])
                words = rsubject.split()
                if len(words) != 3 or words[0] != "[HOMING-PIGEON]" \
                        or words[1] not in ("task_ack", "task_offer"):
                    raise Crash("contract", f"the reply's subject is "
                                f"{rsubject[:60]!r}")
                reply = _query_open_reply(msg, words[2], key_id)
                if not isinstance(reply, dict) or reply.get("v") != 1 \
                        or reply.get("type") != words[1]:
                    raise Crash("shape", f"the reply is {_short(reply)}"[:200])
                if words[1] == "task_ack":
                    if reply.get("task_id") != ident or words[2] != ident:
                        raise Crash("contract", "the ack names a task other "
                                    "than the subject's")
                    if not isinstance(reply.get("reason"), str):
                        raise Crash("shape", "the ack's reason is not text")
                    if "ok" in reply:
                        if not isinstance(reply["ok"], bool):
                            raise Crash("shape", "the ack's ok is not a bool")
                        good = reply["ok"]
                    else:
                        if reply.get("status") not in ("done", "pending_review",
                                                       "duplicate", "not_claimed",
                                                       "not_found"):
                            raise Crash("contract", "the ack's status is "
                                        f"{reply.get('status')!r}")
                        good = reply["status"] in ("done", "pending_review")
                else:
                    task = reply.get("task")
                    if reply.get("empty") is True:
                        if words[2] != "empty" or task is not None:
                            raise Crash("contract", "an empty offer under "
                                        f"subject {rsubject!r}")
                        good = False
                    else:
                        if not isinstance(task, dict) \
                                or task.get("task_id") != words[2]:
                            raise Crash("contract", "the offer's task is not "
                                        "the one its subject names")
                        if states[i].get(task["task_id"]) != "claimed":
                            raise Crash("contract", "a task offered is not "
                                        "claimed on the board")
                        good = True
                if i == 0 and good:
                    outcome = "accepted"
                note("reply", i, words[1], _digest(reply))
            note("board", _digest(board.tasks))
            return outcome
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ------------------------------------------------------------------
# v2_mail: the version 2 message handler (Q86's cache and window)
# ------------------------------------------------------------------

_V2_KINDS = ("determination", "question", "answer")
_V2_CFG = {
    "shared_secret": SECRET,
    "additional_secrets": {"canary-key": SENSE, "ops": OPS},
    "mailbox_user": "runner@example.com",
    "max_job_age_sec": 3600,
    "protocol_v2": True,
    "answer_only": True,
}


def _v2_answer_file(base, question_id):
    """The filed answer's text, by the checker's own idea of where it
    goes (the draft: v2/answers/<question id>.json under the base),
    or None when nothing is filed."""
    if not isinstance(question_id, str) or not P2._ID.match(question_id):
        return None
    path = os.path.join(base, "v2", "answers", question_id + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _v2_more_file(base, question_id):
    path = os.path.join(base, "v2", "answers", question_id + ".json.more.jsonl")
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _v2_leaving_is_moot(payload, ident, kind, key_id, cfg, data):
    """A question the process would leave for another reader is
    still refused -- and marked -- when it fails a check before
    that point: the seal (a cleartext form, a key the object names
    that is not the seal's), the answerer list, the validation, the
    subject against the body, the freshness window. The checker's
    own reading of those checks."""
    if data.get("cleartext") is True:
        return True
    named = payload.get("key_id")
    if "key_id" in payload and named != (key_id or ""):
        return True
    if "v2_answerers" in cfg:
        allowed = cfg["v2_answerers"]
        if not isinstance(allowed, list) or (key_id or "") not in allowed \
                or not all(isinstance(x, str) for x in allowed):
            return True
    try:
        P2.validate(payload)
    except Exception:
        return True
    if payload.get("type") != kind or payload.get("msg_id") != ident:
        return True
    ok, _why = R._issued_at_ok(payload.get("issued_at"), _V2_CFG)
    return not ok


def _v2_local_text(question):
    """The draft's rule for the laptop's answer with no model: the
    question's local_default, stripped, or proceed."""
    default = question.get("local_default") if isinstance(question, dict) \
        else None
    if isinstance(default, str) and default.strip():
        return default.strip()[:64]
    return "proceed"


def _v2_answer_id(question_id):
    """The draft's rule for an answer's id: a.<question id> when that
    is an id, else a.<head>.<digest> within the 128."""
    ident = "a." + question_id
    if len(ident) <= 128 and P2._ID.match(ident):
        return ident
    digest = hashlib.sha256(question_id.encode("utf-8")).hexdigest()[:16]
    return "a." + question_id[:max(1, 128 - 2 - 1 - len(digest))] + "." + digest


def _v2_filed_record(text, answer_obj):
    """A filed answer against the draft: one JSON object on one line
    ending in a newline, received_at a number, the answer the
    message as sent (its sig aside); the digest of what is fixed."""
    if not isinstance(text, str) or not text.endswith("\n") \
            or text.count("\n") != 1:
        raise Crash("shape", "the filed answer is not one JSON line")
    try:
        rec = json.loads(text)
    except ValueError:
        raise Crash("shape", "the filed answer does not parse")
    if not isinstance(rec, dict) or set(rec) != {"received_at", "answer"} \
            or not isinstance(rec["received_at"], (int, float)) \
            or isinstance(rec["received_at"], bool):
        raise Crash("shape", "the filed answer's record is not "
                    "{received_at, answer}")
    filed = rec["answer"]
    sent = {k: v for k, v in answer_obj.items() if k != "sig"}
    if not isinstance(filed, dict) \
            or {k: v for k, v in filed.items() if k != "sig"} != sent:
        raise Crash("contract", "the filed answer is not the answer sent")
    return _digest(sent)


def check_v2_mail(entry):
    """v2_mail: one version 2 message -- its kind and subject id, the
    sealed object a sender chose, the key -- through handle_v2_mail
    with the mail rig, twice, the process set to answer. Contract:
    the handler takes the message (True) and never raises; a
    message it acts on or refuses is marked seen exactly once, and
    the copy is marked once and acted on no further (Q86: recorded
    under v2:<msg_id> in the replay cache once acted on, a stale
    or future issued_at refused unread); at most one reply goes
    out, only to a question, addressed to the mailbox, sealed under
    the answer's own msg_id and opening under the key as a valid
    answer to that question's msg_id, carrying the question's
    local default; an answer message is filed once under its
    question id, and a second answer to the same question does not
    replace it; a determination sends nothing and files nothing.
    Accepted when the message was acted on (recorded)."""
    data = entry["data"]
    if not isinstance(data, dict):
        data = {"payload": data}
    kind = data.get("kind")
    if kind not in _V2_KINDS:
        kind = "question"
    ident = data.get("ident")
    if not isinstance(ident, str) or not ident \
            or any(c.isspace() for c in ident):
        ident = "q.bm-job-0001"
    payload = _stamp_issued_at(data.get("payload"))
    if not isinstance(payload, dict):
        payload = dict(_v2(kind), msg_id=ident, question=payload)
    key_id = data.get("key_id") if isinstance(data.get("key_id"), str) \
        and data.get("key_id") in SECRETS else ""
    cfg = dict(_V2_CFG)
    if isinstance(data.get("answerers"), list):
        cfg["v2_answerers"] = data["answerers"]
    if data.get("model_down") is True:
        # An answerer whose model is configured and not there: the
        # endpoint is a loopback port nothing listens on, so the
        # call fails at once and the local default answers.
        cfg["inference"] = {"endpoint": "http://127.0.0.1:1",
                            "model": "bm-model", "timeout_sec": 2}
    if isinstance(data.get("mode"), str):
        cfg["oracle_mode"] = data["mode"]
    # The two switches (the draft's section 2): the Pi emits with
    # protocol_v2, the laptop answers with answer_only; a process
    # with neither ignores a version 2 message, and one that emits
    # but does not answer leaves a question for another reader.
    if "v2" in data:
        cfg["protocol_v2"] = data["v2"]
    if "answer_only" in data:
        cfg["answer_only"] = data["answer_only"]
    receiving = cfg.get("protocol_v2") is True or cfg.get("answer_only") is True
    leaves = receiving and kind == "question" \
        and cfg.get("answer_only") is not True
    if TU._lone_surrogate(payload):
        note("gate", "lone surrogate")
        return "refused"
    subject = f"[HOMING-PIGEON] {kind} {ident}"
    try:
        raw = _mail_form(subject, ident, payload, key_id, data)
    except ValueError as e:
        note("gate", "unsignable", _short(e))
        return "refused"
    opts = _mail_opts(data)
    base = tempfile.mkdtemp(prefix="hp-de_dust-v2-")
    try:
        secrets = R.build_secrets(cfg)
        seen = {}
        outs = []
        logbook = _MailLog(base)
        left = []
        for attempt in (1, 2):
            imap, smtp = _FakeImap(), _FakeSmtp()
            left.append(0)
            with mock.patch.object(R, "log", logbook.log), \
                    mock.patch.object(R, "vlog", logbook.vlog), \
                    mock.patch.object(R, "_v2_leave_unseen",
                                      lambda *_a: left.__setitem__(
                                          -1, left[-1] + 1)):
                got, exc = _call(HA.handle_v2_mail, cfg, imap, smtp, attempt,
                                 raw, subject, secrets, opts, base, seen)
            if exc is not None:
                raise Crash("exception", "handle_v2_mail raised "
                            f"{type(exc).__name__}: {_short(exc)}")
            if got is not True:
                raise Crash("contract", f"handle_v2_mail answered {got!r} "
                            "for a version 2 subject")
            # A question this process leaves for another reader (it
            # emits, it does not answer) stays unseen, unanswered and
            # unrecorded; it is left only under that switch, and a
            # question that passes every check before that point is
            # left for sure. One refused before that point is marked.
            if left[-1] and not leaves:
                raise Crash("contract", "a question was left for another "
                            "reader by a process that answers")
            if leaves and not left[-1] and not _v2_leaving_is_moot(
                    payload, ident, kind, key_id, cfg, data):
                raise Crash("contract", "a question the process does not "
                            "answer was not left for another reader")
            marks = 0 if opts.dry_run or left[-1] else 1
            if len(imap.marked) != marks:
                raise Crash("contract", "the message was marked "
                            f"{len(imap.marked)} times under dry "
                            f"{opts.dry_run}, left {bool(left[-1])}")
            if len(smtp.sent) > 1:
                raise Crash("contract", f"{len(smtp.sent)} replies went out")
            if smtp.sent and (opts.dry_run or opts.no_send or not receiving
                              or left[-1]):
                raise Crash("contract", "a reply went out under dry, "
                            "no_send, the switches off or a question "
                            "left")
            outs.append(smtp.sent[0] if smtp.sent else None)
        logbook.note()
        if opts.dry_run and seen:
            raise Crash("contract", "a dry run recorded the message")
        if (not receiving or any(left)) and seen:
            raise Crash("contract", "a message ignored or left was recorded")
        first, again = outs
        if again is not None:
            raise Crash("contract", "a copy of the message was answered "
                        "again")
        recorded = sorted(seen)
        if seen and recorded != ["v2:" + ident]:
            raise Crash("contract", f"the replay cache holds {recorded!r}")
        on_disk = R.load_seen(os.path.join(base, "seen.json"))
        if seen and not (isinstance(on_disk, dict)
                         and on_disk.get("v2:" + ident)):
            raise Crash("contract", "a message acted on is not in the "
                        "replay cache on disk")
        if not seen and on_disk:
            raise Crash("contract", "the replay cache on disk holds "
                        f"{sorted(on_disk)!r} for a message not acted on")
        filed = _v2_answer_file(base, payload.get("question_id")
                                if kind == "answer" else None)
        accepted = False
        if first is not None:
            if kind != "question":
                raise Crash("contract", f"a {kind} got a reply")
            if not seen:
                raise Crash("contract", "a question was answered and not "
                            "recorded")
            if first["To"] != cfg["mailbox_user"]:
                raise Crash("provenance", f"the answer is addressed to "
                            f"{first['To']!r}")
            words = str(first["Subject"]).split()
            if len(words) != 3 or words[:2] != ["[HOMING-PIGEON]", "answer"]:
                raise Crash("contract", f"the answer's subject is "
                            f"{str(first['Subject'])[:60]!r}")
            answer = _query_open_reply(first, words[2], key_id)
            valid, exc = _call(P2.validate, answer)
            if exc is not None:
                raise Crash("contract", "the answer sent does not validate: "
                            f"{_short(exc)}")
            if answer.get("type") != "answer" \
                    or answer.get("msg_id") != words[2] \
                    or answer.get("question_id") != ident \
                    or answer.get("job_id") != payload.get("job_id"):
                raise Crash("contract", "the answer does not name the "
                            "question it answers")
            if answer.get("msg_id") != _v2_answer_id(ident):
                raise Crash("contract", "the answer's id is not the "
                            f"draft's: {answer.get('msg_id')!r}")
            if answer.get("v") != 2 or not isinstance(answer.get("issued_at"),
                                                      str):
                raise Crash("shape", "the answer's version or issued_at")
            if answer.get("answer") != _v2_local_text(payload):
                raise Crash("contract", "the answer is not the question's "
                            "local default")
            note("answer", _digest({k: v for k, v in answer.items()
                                    if k != "issued_at"}))
            accepted = True
        elif kind == "answer" and seen:
            if filed is None:
                raise Crash("contract", "an answer acted on was not filed")
            sent = dict(payload, key_id=key_id) \
                if key_id and "key_id" not in payload else payload
            note("filed", _v2_filed_record(filed, sent))
            # A second answer to the same question, under another
            # msg_id, does not replace the first; it is kept beside
            # it, the same text once, the file stopping at eight.
            qid = payload.get("question_id")
            texts = []
            for n in range(1, 11):
                text = "the other" if n == 10 else f"the other {n}"
                other = dict(payload, msg_id=f"{ident}-{n}", answer=text)
                other_raw = _sealed_mail(f"[HOMING-PIGEON] answer {ident}-{n}",
                                         f"{ident}-{n}", other, key_id)
                imap, smtp = _FakeImap(), _FakeSmtp()
                with mock.patch.object(R, "log", lambda *a, **k: None), \
                        mock.patch.object(R, "vlog", lambda *a, **k: None):
                    _got, exc = _call(HA.handle_v2_mail, cfg, imap, smtp,
                                      2 + n, other_raw,
                                      f"[HOMING-PIGEON] answer {ident}-{n}",
                                      secrets, opts, base, seen)
                if exc is not None:
                    raise Crash("exception", "handle_v2_mail raised on "
                                f"another answer: {_short(exc)}")
                if smtp.sent:
                    raise Crash("contract", "an answer got a reply")
                texts.append(text)
            if _v2_answer_file(base, qid) != filed:
                raise Crash("contract", "a second answer replaced the first")
            more = _v2_more_file(base, qid)
            kept = []
            for line in (more or "").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    raise Crash("shape", "a late answer's line does not parse")
                if not isinstance(rec, dict) \
                        or set(rec) != {"received_at", "answer"} \
                        or not isinstance(rec["answer"], str):
                    raise Crash("shape", "a late answer's record is not "
                                "{received_at, answer}")
                kept.append(rec["answer"])
            if kept != texts[:8]:
                raise Crash("contract", "the late answers kept are not the "
                            f"first eight distinct ones: {kept!r}"[:200])
            note("more", _digest(kept))
            accepted = True
        elif filed is not None:
            raise Crash("contract", "an answer was filed without being "
                        "acted on")
        note("seen", recorded, "filed" if filed else "none")
        return "accepted" if accepted or seen else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ------------------------------------------------------------------
# names: the two readers of a name a sender chose
# ------------------------------------------------------------------

def _stage_name(name):
    """An accepted file name through the staging check on this host:
    the destination's real path is under the work directory's, and
    the relative path is the name itself. A refusal there (a
    directory the host will not create) is a refusal, not a crash:
    the rules are the first gate and the staging check the second."""
    work = tempfile.mkdtemp(prefix="hp-de_dust-names-")
    try:
        root = os.path.realpath(work)
        dest, exc = _call(R._staged_dest, work, name, root)
        if exc is not None:
            _expect_refusal(exc, R.JobRejected, "_staged_dest")
            note("stage", "refused")
            return
        if not isinstance(dest, str) or not dest.startswith(root + os.sep):
            raise Crash("contract", f"an accepted name staged at {dest!r}, "
                        "outside the work directory"[:200])
        rel = os.path.relpath(dest, root).replace(os.sep, "/")
        if rel != name:
            raise Crash("contract", f"an accepted name staged at {rel!r}, "
                        f"not at {name!r}"[:200])
        note("stage", "ok")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_names(entry):
    """names: one text before the two readers of a name a sender
    chose -- `files[].name` through validate_file_name (the six
    rules of runner/guard/filenames.py, the same on every platform)
    and `job_id` through _safe_job_id. Contract: validate_file_name
    refuses with BadFileName naming one of the six rules and
    nothing else, or answers the normalized path, which a second
    pass accepts unchanged, which has no empty, dot, backslash or
    Windows-device component, is not absolute under either path
    flavour, and stages under a scratch work directory on this
    host or is refused there; _safe_job_id refuses with JobRejected
    and nothing else, or answers the same string, which is one
    safe component under either path flavour. Accepted when either
    reader accepts."""
    name = entry["data"]
    file_ok = False
    got, exc = _call(FN.validate_file_name, name)
    if exc is not None:
        _expect_refusal(exc, FN.BadFileName, "validate_file_name")
        rule = getattr(exc, "rule", None)
        if rule not in FN.RULES:
            raise Crash("contract", "validate_file_name refused with rule "
                        f"{rule!r}, which is not one of its six")
        note("file", "rule", rule)
    else:
        if not isinstance(got, str) or not got:
            raise Crash("shape", f"validate_file_name answered {got!r}"[:200])
        again, exc2 = _call(FN.validate_file_name, got)
        if exc2 is not None or again != got:
            raise Crash("contract", "the normalized name is not accepted "
                        "unchanged by a second pass")
        parts = got.split("/")
        if "\\" in got or "\x00" in got or any(
                p in ("", ".", "..") or FN.windows_reserved_name(p)
                for p in parts):
            raise Crash("contract", f"an accepted name carries a component "
                        f"the rules refuse: {got!r}"[:200])
        if posixpath.isabs(got) or ntpath.isabs(got) \
                or ntpath.splitdrive(got)[0]:
            raise Crash("contract", f"an accepted name is absolute under a "
                        f"path flavour: {got!r}"[:200])
        note("file", "ok", _digest(got), len(parts))
        _stage_name(got)
        file_ok = True
    jid, jexc = _call(R._safe_job_id, name)
    if jexc is not None:
        _expect_refusal(jexc, R.JobRejected, "_safe_job_id")
        note("job_id", "refused")
    else:
        if jid != name:
            raise Crash("contract", "_safe_job_id answered a string other "
                        "than the one it was given")
        if posixpath.basename(jid) != jid or ntpath.basename(jid) != jid \
                or jid in (".", "..") or "\x00" in jid:
            raise Crash("contract", f"an accepted job_id is not one safe "
                        f"component: {jid!r}"[:200])
        note("job_id", "ok", _digest(jid))
    return "accepted" if file_ok or jexc is None else "refused"


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
        # The default key by its own name (Q94), and a name no key
        # answers to though it has the shape of one.
        ("exec_job_fingerprint_key", _job(key_id=FP, script="true")),
        ("other_fingerprint_key", _job(key_id=FP_OPS)),
        ("alert", _frozen_alert()),
        ("unknown_key", _job(key_id="nobody")),
        ("null_key", _job(key_id=None)),
        ("empty_key", _job(key_id="")),
        ("own_sig_member", _job(sig="0" * 96)),
        ("unicode", _job(title="café — 中文 \U0001f426")),
        ("escapes", _job(note="a\"quote\\slash\nnewline\ttab")),
        # Ids with the header's line breaks in them: the result's
        # subject carries the text folded onto one line.
        ("id_with_newline", _job(job_id="bm-nl\n0001")),
        ("id_with_separators", _job(job_id="bm-\u2028sep\x0b\x0c\x85\r\n1")),
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


def _hmac_signed_text(text):
    """A text signed exactly as a body is -- the HMAC over the whole
    of it, then the sig tail in place of its last character --
    whatever the text is: the receiver must still refuse what is
    not a JSON object."""
    import hashlib as _h
    import hmac as _hmac
    sig = _hmac.new(SECRET.encode("utf-8"), text.encode("utf-8"),
                    _h.sha384).hexdigest()
    return text[:-1] + ',"sig":"' + sig + '"}'


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
        # The strip keeps a tab and drops the rest below 32: a raw
        # tab and a unit separator each dropped into the object.
        ("raw_tab", exec_body[:40] + "\t" + exec_body[40:]),
        ("raw_unit_separator", exec_body[:40] + "\x1f" + exec_body[40:]),
        ("raw_space_run", exec_body[:40] + "  " + exec_body[40:]),
        # The survivors' lines, second round: a pretty-printed body
        # whose line ends are a lone CR (normalized to the LF that
        # was signed) and CRLF; a sig whose last digit is not hex; a
        # body whose signed text is not JSON (the HMAC is right, the
        # opener search hands on its newest whole-object candidate,
        # and the real fault is named); a closed object before an
        # object the walk refuses in-string at the marker.
        ("pretty_cr", _pretty_signed(_job(script="echo cr")).replace(
            "\n", "\r")),
        ("pretty_crlf", _pretty_signed(_job(script="echo crlf")).replace(
            "\n", "\r\n")),
        ("sig_last_not_hex", exec_body[:-3] + "g" + exec_body[-2:]),
        ("signed_not_json", _hmac_signed_text('{"a":{"b":}')),
        ("closed_then_in_string",
         '{"a":1}{"b":"x,"sig":"' + "0" * 96 + '"}'),
        # A lone surrogate as the JSON escape (Q85): in the kind, in a
        # nested list, in a key; a surrogate pair is a character.
        ("surrogate_kind", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-s-0001","kind":"\\ud800"}')),
        ("surrogate_nested", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-s-0002","kind":"exec",'
            '"detail":{"a":["x","\\udfff"]}}')),
        ("surrogate_key", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-s-0003","kind":"exec",'
            '"\\ud83d":1}')),
        ("surrogate_pair", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-s-0004","kind":"exec",'
            '"note":"\\ud83d\\udc26 caf\\u00e9"}')),
        # The numbers and literals JSON does not have (Q89): NaN and
        # Infinity are the parser's extensions, 1e400 is syntax that
        # overflows; the largest finite number is a number. A body
        # nested past the walks' bound is refused whole; one at the
        # bound is read, and a lone surrogate at the bottom of it is
        # seen.
        ("nan_member", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-n-0001","kind":"exec",'
            '"x":NaN}')),
        ("infinity_member", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-n-0002","kind":"exec",'
            '"x":Infinity}')),
        ("negative_infinity_member", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-n-0003","kind":"exec",'
            '"x":[-Infinity]}')),
        ("overflow_number", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-n-0004","kind":"exec",'
            '"timeout_sec":1e400}')),
        ("largest_finite_number", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-n-0005","kind":"exec",'
            '"x":1.7976931348623157e308,"y":-1e308,"z":5e-324}')),
        ("nested_at_the_bound", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-d-0001","kind":"exec",'
            '"deep":' + "[" * 199 + "1" + "]" * 199 + "}")),
        ("nested_past_the_bound", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-d-0002","kind":"exec",'
            '"deep":' + "[" * 200 + "1" + "]" * 200 + "}")),
        ("nested_objects_past_the_bound", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-d-0003","kind":"exec",'
            '"deep":' + '{"a":' * 200 + "1" + "}" * 200 + "}")),
        ("surrogate_at_the_bound", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-d-0004","kind":"exec",'
            '"deep":' + "[" * 199 + '"\\ud800"' + "]" * 199 + "}")),
        ("nested_far_past_the_bound", _hmac_signed_text(
            '{"v":1,"type":"job","job_id":"bm-d-0005","kind":"exec",'
            '"deep":' + "[" * 1500 + '"\\ud800"' + "]" * 1500 + "}")),
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
    # The identifier checks after job_id's: a message id, and an
    # answer's question id, missing or not a safe id, each named in
    # the refusal (the survivors' lines).
    for field, kind in (("msg_id", "question"), ("question_id", "answer")):
        for word, bad in (("dotdot", "../x"), ("empty", ""), ("number", 7),
                          ("null", None), ("over", "m" * 129)):
            o = _v2(kind)
            o[field] = bad
            out.append((f"{field}_{word}", o))
        o = _v2(kind)
        del o[field]
        out.append((f"no_{field}", o))
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
        return hashlib.sha256(b"de_dust-nonce-%d" % self.n).digest()[:size]

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
    # The default key under its own name (Q94): the AAD binds the
    # name, so an envelope sealed under the fingerprint opens under
    # it and not under the empty key id, and the other way round.
    named_inner = V.sign_payload(_job(key_id=FP, script="echo named"),
                                 SECRET)
    named = V.verify_body(JC.encrypt_body(named_inner, SECRET,
                                          "bm-exec-0001", FP,
                                          V.sign_payload), SECRET)
    out.append(("fingerprint_keyed",
                {"envelope": named, "job_id": "bm-exec-0001",
                 "key_id": FP, "expect": named_inner}))
    out.append(("fingerprint_read_as_default",
                {"envelope": named, "job_id": "bm-exec-0001", "key_id": ""}))
    out.append(("default_read_as_fingerprint",
                {"envelope": sealed, "job_id": "bm-exec-0001", "key_id": FP}))
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
    # The survivors' lines: a ciphertext of exactly the tag and one
    # byte short of it, the real tag over an empty plaintext, a
    # nonce of 11 and 13 octets, each hp_enc member missing in
    # turn, a member that is not text, base64 that does not
    # validate, and the envelope's own member set one wider.
    import base64 as _b64
    for n, name in ((16, "ct_tag_only"), (15, "ct_15"), (17, "ct_17")):
        enc = dict(sealed)
        enc["hp_enc"] = dict(sealed["hp_enc"],
                             ct=_b64.b64encode(b"\x00" * n).decode("ascii"))
        out.append((name, {"envelope": enc, "job_id": "bm-exec-0001",
                           "key_id": ""}))
    nonce = _b64.b64decode(sealed["hp_enc"]["nonce"])
    empty_ct = JC.aead_encrypt(JC._job_key(SECRET, nonce), nonce, b"",
                               JC._aad("bm-exec-0001", ""))
    enc = dict(sealed)
    enc["hp_enc"] = dict(sealed["hp_enc"],
                         ct=_b64.b64encode(empty_ct).decode("ascii"))
    out.append(("empty_plaintext", {"envelope": enc, "job_id": "bm-exec-0001",
                                    "key_id": "", "expect": ""}))
    for n, name in ((11, "nonce_11"), (13, "nonce_13")):
        enc = dict(sealed)
        enc["hp_enc"] = dict(sealed["hp_enc"],
                             nonce=_b64.b64encode(b"\x01" * n).decode("ascii"))
        out.append((name, {"envelope": enc, "job_id": "bm-exec-0001",
                           "key_id": ""}))
    for member in ("alg", "nonce", "ct"):
        enc = dict(sealed)
        enc["hp_enc"] = {k: v for k, v in sealed["hp_enc"].items()
                         if k != member}
        out.append(("no_" + member, {"envelope": enc, "job_id": "bm-exec-0001",
                                     "key_id": ""}))
        enc = dict(sealed)
        enc["hp_enc"] = dict(sealed["hp_enc"], **{member: 7})
        out.append((member + "_not_text", {"envelope": enc,
                                           "job_id": "bm-exec-0001",
                                           "key_id": ""}))
    enc = dict(sealed)
    enc["hp_enc"] = dict(sealed["hp_enc"], ct=sealed["hp_enc"]["ct"] + "!")
    out.append(("ct_not_base64", {"envelope": enc, "job_id": "bm-exec-0001",
                                  "key_id": ""}))
    enc = dict(sealed)
    enc["hp_enc"] = dict(sealed["hp_enc"], extra="x")
    out.append(("hp_enc_extra", {"envelope": enc, "job_id": "bm-exec-0001",
                                 "key_id": ""}))
    out.append(("key_id_only", {"envelope": {"hp_enc": sealed["hp_enc"],
                                             "key_id": ""},
                                "job_id": "bm-exec-0001", "key_id": ""}))
    out.append(("hp_enc_not_object", {"envelope": {"hp_enc": "sealed"},
                                      "job_id": "bm-exec-0001", "key_id": ""}))
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
    plain_named = V.sign_payload(_job(key_id=FP), SECRET)
    plain_other_fp = V.sign_payload(_job(key_id=FP_OPS), OPS)

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
        # The default key under its own name (Q94), in each slot;
        # after the rest, so the earlier envelopes keep their nonces.
        ("plain_fingerprint", rec(plain_named, FP)),
        ("sealed_fingerprint", rec(sealed(plain_named, FP, SECRET), FP)),
        ("sealed_body_fingerprint_record_default",
         rec(sealed(plain_named, FP, SECRET), "")),
        ("sealed_default_record_fingerprint",
         rec(sealed(plain, "", SECRET), FP)),
        ("plain_other_fingerprint", rec(plain_other_fp, FP_OPS)),
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
        # A non-finite priority already on disk used to stay in
        # memory, and the next save then failed, so the file and
        # the board drifted.
        ("nonfinite_on_disk", {"file": _board_file(
            _task("bm-nan", priority=float("nan")),
            _task("bm-inf", priority=float("inf")),
            _task("bm-ninf", priority=-float("inf"))),
         "ops": [["submit", _task()]]}),
        # A non-finite float under some other key. save stores null
        # there; load does the same, so the file reads back.
        ("nonfinite_elsewhere", {"file": _board_file(
            _task("bm-stray", note=float("nan"))),
         "ops": [["submit", _task()]]}),
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
        # A lease of exactly one second is not expired one second on;
        # half a second is (the board's clock steps one second per
        # reading under the checker).
        ("lease_one_second", {"file": None, "ops": [
            ["submit", _task()], ["offer", "worker-a", ["shell"], "", {}],
            ["reoffer", 1], ["offer", "worker-b", ["shell"], "", {}],
            ["reoffer", 0.5], ["offer", "worker-b", ["shell"], "", {}]]}),
        # Tasks a hand-written file left without a priority, with
        # NaN, with a negative fraction: the offer order says what
        # each reads as.
        ("file_priorities", {"file": json.dumps({
            "bm-task-a": {"task_id": "bm-task-a", "state": "open",
                          "submitted_at": "2026-10-26T10:00:01+00:00"},
            "bm-task-b": dict(_task("bm-task-b", priority=0.5), state="open",
                              submitted_at="2026-10-26T10:00:02+00:00"),
            "bm-task-c": dict(_task("bm-task-c", priority=float("nan")),
                              state="open",
                              submitted_at="2026-10-26T10:00:03+00:00"),
            "bm-task-d": dict(_task("bm-task-d", priority=-0.5), state="open",
                              submitted_at="2026-10-26T10:00:04+00:00"),
            "bm-task-e": dict(_task("bm-task-e"), state="open",
                              submitted_at="2026-10-26T10:00:00"),
        }), "ops": [["offer", w, [], "", {}] for w in
                    ("worker-a", "worker-b", "worker-c", "worker-d",
                     "worker-e")]}),
        ("refusals_then_good", {"file": "{not json", "ops": [
            ["submit", "not a task"], ["submit", {"task_id": "../x"}],
            ["complete", "bm-task-0001", {}], ["approve", {"task_id": 1}],
            ["offer", "nobody", ["shell"], "", cfg],
            ["submit", _task()],
            ["offer", "worker-a", ["shell"], "ops", cfg],
            ["complete", "bm-task-0001", {"exit_code": 0}]]}),
        # The ranking's defaults, each against an explicit zero
        # submitted on the other side of the tie: a task without a
        # priority, a boolean priority, a text one. The earlier
        # submission wins a tie, so the order of each pair says what
        # the default is.
        ("rank_absent_then_zero", {"file": None, "ops": [
            ["submit", {"task_id": "bm-task-a", "capabilities": []}],
            ["submit", _task("bm-task-b", priority=0)],
            ["offer", "worker-a", ["shell"], "", {}]]}),
        ("rank_zero_then_absent", {"file": None, "ops": [
            ["submit", _task("bm-task-a", priority=0)],
            ["submit", {"task_id": "bm-task-b", "capabilities": []}],
            ["offer", "worker-a", ["shell"], "", {}]]}),
        ("rank_bool_then_zero", {"file": None, "ops": [
            ["submit", _task("bm-task-a", priority=True)],
            ["submit", _task("bm-task-b", priority=0)],
            ["offer", "worker-a", ["shell"], "", {}]]}),
        ("rank_text_on_disk", {"file": json.dumps({
            "bm-task-a": dict(_task("bm-task-a", priority="high"),
                              state="open",
                              submitted_at="2026-10-26T10:00:01+00:00"),
            "bm-task-b": dict(_task("bm-task-b", priority=0), state="open",
                              submitted_at="2026-10-26T10:00:02+00:00"),
        }), "ops": [["offer", "worker-a", ["shell"], "", {}]]}),
        # The same file-borne shapes handed to workers that can take
        # every task: the one without a priority is ranked against
        # the explicit ones, and the order of the hand-outs says
        # what it reads as.
        ("file_priorities_ranked", {"file": json.dumps({
            "bm-task-a": {"task_id": "bm-task-a", "state": "open",
                          "capabilities": ["shell"],
                          "submitted_at": "2026-10-26T10:00:01+00:00"},
            "bm-task-b": dict(_task("bm-task-b", priority=0.5), state="open",
                              submitted_at="2026-10-26T10:00:02+00:00"),
            "bm-task-d": dict(_task("bm-task-d", priority=-0.5), state="open",
                              submitted_at="2026-10-26T10:00:04+00:00"),
            "bm-task-e": dict(_task("bm-task-e"), state="open",
                              submitted_at="2026-10-26T10:00:00+00:00"),
        }), "ops": [["offer", w, ["shell"], "", {}] for w in
                    ("worker-a", "worker-b", "worker-c", "worker-d")]}),
        # Two tasks of one priority whose order in the file is not
        # their order of submission: the earlier submission is handed
        # out first, whatever the file's order.
        ("rank_tie_by_time_not_order", {"file": json.dumps({
            "bm-task-a": dict(_task("bm-task-a", priority=0), state="open",
                              submitted_at="2026-10-26T10:00:01+00:00"),
            "bm-task-z": dict(_task("bm-task-z", priority=0), state="open",
                              submitted_at="2026-10-26T10:00:00+00:00"),
        }), "ops": [["offer", "worker-a", ["shell"], "", {}],
                    ["offer", "worker-b", ["shell"], "", {}]]}),
        # A lease claimed one default lease length before the clock's
        # first reading: not expired under the default (the elapsed
        # time is exactly the default, not over it), expired under
        # any shorter length; a fresh claim and a length of -1, which
        # is not a length, so the default holds it.
        ("lease_default_edge", {"file": _board_file(dict(
            claimed, claimed_at="2026-10-25T12:00:01+00:00")), "ops": [
            ["reoffer", None], ["offer", "worker-b", ["shell"], "", {}],
            ["reoffer", 86399], ["offer", "worker-b", ["shell"], "", {}],
            ["reoffer", -1], ["offer", "worker-a", ["shell"], "", {}]]}),
        # An advisory hand-out carries its warning on the board
        # record; when the lease lapses, the dependency is finished
        # and the task goes out again, the warning is gone.
        ("dag_warning_cleared", {"file": None, "ops": [
            ["submit", _task("bm-task-a", requires=["bm-task-b"])],
            ["offer", "worker-a", ["shell"], "", dict(cfg, dag_mode="advisory")],
            ["reoffer", 0],
            ["submit", _task("bm-task-b")],
            ["offer", "worker-b", ["shell"], "", {}],
            ["complete", "bm-task-b", {"exit_code": 0}],
            ["offer", "worker-a", ["shell"], "", dict(cfg, dag_mode="advisory")]]}),
        # A requirement that is not text, on disk: unreadable, so the
        # task is withheld under enforce and warned under advisory.
        ("file_requires_number", {"file": _board_file(dict(
            _task(requires=[7]), state="open",
            submitted_at="2026-10-26T10:00:00+00:00")), "ops": [
            ["offer", "worker-a", ["shell"], "", dict(cfg, dag_mode="enforce")],
            ["offer", "worker-b", ["shell"], "", dict(cfg, dag_mode="advisory")]]}),
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
                     "description": "A de_dust run finished."}],
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
            description="A de_dust sense.",
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
    # The survivors' lines: every cap at itself and one past it.
    sig = {"name": "bm_sig", "description": "A declared signal."}
    out.append(("signals_64", _sense(signals=[
        dict(sig, name=f"bm_sig_{i}") for i in range(EX.MAX_SIGNALS)])))
    for n in (EX.MAX_DESCRIPTION_CHARS, EX.MAX_DESCRIPTION_CHARS + 1):
        out.append((f"signal_description_{n}", _sense(signals=[
            dict(sig, description="d" * n)])))
        out.append((f"publisher_{n}", _transport(publisher="p" * n)))
    for n in (100, 101):
        out.append((f"license_{n}", _sense(upstream=dict(
            upstream, license="L" * n))))
    for n in (128, 129):
        out.append((f"ref_{n}", _sense(upstream=dict(upstream, ref="r" * n))))
    for n in (EX.MAX_UPSTREAM_PATHS, EX.MAX_UPSTREAM_PATHS + 1):
        out.append((f"paths_{n}", _sense(upstream=dict(
            upstream, paths=[f"schema/p{i}.json" for i in range(n)]))))
    for n in (240, 241):
        out.append((f"path_{n}", _sense(upstream=dict(
            upstream, paths=["schema/" + "p" * (n - 7)]))))
    for n in (16, 17):
        out.append((f"entry_{n}", _transport(entry=["bm-pipe"] + [
            f"--flag{i}" for i in range(n - 1)])))
    for n in (500, 501):
        out.append((f"entry_part_{n}", _transport(entry=["bm-pipe", "x" * n])))
    for n in (-1, 0):
        out.append((f"settle_{n}", _transport(startup_settle_ms=n)))
    out.append(("settle_bool", _transport(startup_settle_ms=True)))
    out.append(("path_empty_part", _sense(upstream=dict(
        upstream, paths=["schema//record.json"]))))
    out.append(("path_dot_part", _sense(upstream=dict(
        upstream, paths=["schema/./record.json"]))))
    out.append(("publisher_two_lines", _transport(publisher="a\nb")))
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
        # Names the result id cleans: a space, the portable
        # punctuation, and two that clean to one id.
        ("cleaned_names", {"files": [_chan("bm 0024.job.txt", good),
                                     _chan("a+b=c@d.job.txt", good),
                                     _chan("bm_0024.job.txt", good)]}),
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
    # Two replies per envelope over two envelopes of one stem: four
    # result files of one name, so the third and fourth carry the
    # counter past its first step.
    out.append(("core_two_same_stem", {"files": [
        _chan("bm-0023", good), _chan("bm-0023.job.txt", good)],
        "mode": "two"}))
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


def seeds_queries():
    canary = "SECRET-12345 is the canary line of the output\n"
    output = ("ok\n" + canary + "ERROR one\nERROR two\nwarn: three\n"
              + "a" * 12 + "!\n")
    long_line = " " * 800 + "!"

    def entry(name, policy, output=output, stderr=None):
        data = {"policy": policy, "output": output}
        if stderr is not None:
            data["stderr"] = stderr
        return (name, data)

    grep = {"op": "grep", "pattern": "ERROR", "max_matches": 5}
    tail = {"op": "tail", "lines": 3}
    attest = {"op": "attest", "predicate": "exit_zero"}
    out = [
        entry("happy", {"view": "full", "queries": [attest, grep, tail]}),
        entry("views_attested", {"view": "attested", "queries": [
            attest, grep, tail, {"op": "attest", "predicate": "no_secrets"},
            {"op": "attest", "predicate": "output_digest"},
            {"op": "attest", "predicate": "confined_to_workspace"}]}),
        entry("views_summary", {"view": "summary", "queries": [grep, tail]}),
        entry("views_redacted", {"view": "redacted", "queries": [
            {"op": "grep", "pattern": "SECRET"}, {"op": "tail", "lines": 9}]}),
        entry("view_unknown", {"view": "wide", "queries": [grep]}),
        entry("view_empty", {"view": "", "queries": [tail]}),
        entry("view_number", {"view": 7}),
        entry("view_true", {"view": True}),
        entry("view_null", {"view": None}),
        entry("view_list", {"view": ["full"]}),
        entry("policy_list", [grep]),
        entry("policy_text", "full"),
        entry("policy_number", 7),
        entry("policy_null", None),
        entry("policy_empty", {}),
        entry("queries_object", {"queries": {"op": "grep"}}),
        entry("queries_text", {"queries": "grep ERROR"}),
        entry("queries_empty", {"queries": []}),
        entry("queries_not_objects", {"queries": [7, "grep", None, [], attest]}),
        entry("op_unknown", {"queries": [{"op": "count"}, {"op": None},
                                         {"op": 7}, {}]}),
        entry("grep_no_pattern", {"queries": [{"op": "grep"}]}),
        entry("grep_pattern_null", {"queries": [{"op": "grep", "pattern": None}]}),
        entry("grep_pattern_number", {"queries": [{"op": "grep", "pattern": 7}]}),
        entry("grep_not_compiling", {"queries": [{"op": "grep", "pattern": "("}]}),
        # A repetition count past what the engine holds is a bad
        # pattern too (Q92): the engine's OverflowError, not its
        # error class, and the refusal is the same.
        entry("grep_repeat_overflow", {"queries": [
            {"op": "grep", "pattern": "a{99999999999}"}, grep]}),
        entry("grep_repeat_overflow_range", {"queries": [
            {"op": "grep", "pattern": "a{1,99999999999}"}]}),
        entry("grep_repeat_overflow_nested", {"queries": [
            {"op": "grep", "pattern": "(?:a+){9223372036854775808}"}]}),
        entry("grep_repeat_large", {"queries": [
            {"op": "grep", "pattern": "a{65536}"}, {"op": "grep", "pattern": "a{2147483648}"}]}),
        entry("grep_nested_repeat", {"queries": [
            {"op": "grep", "pattern": "(a+)+$"}, grep]}),
        entry("grep_repeated_alternation", {"queries": [
            {"op": "grep", "pattern": "(a|aa)+$"}]}),
        entry("grep_two_wildcards", {"queries": [
            {"op": "grep", "pattern": "error.*timeout"}]}),
        entry("grep_three_repeats", {"queries": [
            {"op": "grep", "pattern": "^\\s*\\d+\\s+passed"}]}),
        entry("grep_empty_pattern", {"queries": [{"op": "grep", "pattern": ""}]}),
        entry("grep_every_line", {"queries": [
            {"op": "grep", "pattern": ".", "max_matches": 100}]}),
        entry("grep_max_zero", {"queries": [
            {"op": "grep", "pattern": "ERROR", "max_matches": 0}]}),
        entry("grep_max_negative", {"queries": [
            {"op": "grep", "pattern": "ERROR", "max_matches": -1}]}),
        entry("grep_max_over", {"queries": [
            {"op": "grep", "pattern": ".", "max_matches": 1000}]}),
        entry("grep_max_text", {"queries": [
            {"op": "grep", "pattern": "ERROR", "max_matches": "7"}]}),
        entry("grep_max_bool", {"queries": [
            {"op": "grep", "pattern": "ERROR", "max_matches": True}]}),
        entry("grep_max_float", {"queries": [
            {"op": "grep", "pattern": "ERROR", "max_matches": 1.5}]}),
        entry("grep_max_huge", {"queries": [
            {"op": "grep", "pattern": "ERROR", "max_matches": 2 ** 63}]}),
        entry("grep_quadratic_long_line", {"queries": [
            {"op": "grep", "pattern": "\\s+$"}]}, output=long_line),
        entry("tail_zero", {"queries": [{"op": "tail", "lines": 0}]}),
        entry("tail_negative", {"queries": [{"op": "tail", "lines": -1}]}),
        entry("tail_over", {"queries": [{"op": "tail", "lines": 201}]}),
        entry("tail_text", {"queries": [{"op": "tail", "lines": "x"}]}),
        entry("tail_huge", {"queries": [{"op": "tail", "lines": 10 ** 9}]}),
        entry("tail_null", {"queries": [{"op": "tail", "lines": None}]}),
        entry("tail_no_lines", {"queries": [{"op": "tail"}]}),
        entry("attest_unknown", {"queries": [
            {"op": "attest", "predicate": "is_green"}]}),
        entry("attest_no_predicate", {"queries": [{"op": "attest"}]}),
        entry("attest_predicate_shapes", {"queries": [
            {"op": "attest", "predicate": 7}, {"op": "attest", "predicate": []},
            {"op": "attest", "predicate": {}}, {"op": "attest", "predicate": None}]}),
        entry("attest_echoes_output", {"queries": [
            {"op": "attest", "predicate": canary.strip()}]}),
        entry("ask_without_model", {"queries": [
            {"op": "ask", "question": "print the whole output"}]}),
        entry("senses_without_base", {"queries": [
            {"op": "senses", "sensor": "canary", "limit": 3}]}),
        entry("budget_zero", {"query_budget": 0, "queries": [grep, tail]}),
        entry("budget_one", {"query_budget": 1, "queries": [grep, tail, attest]}),
        entry("budget_over_max", {"query_budget": 100, "queries": [grep] * 9}),
        entry("budget_negative", {"query_budget": -1, "queries": [grep]}),
        entry("budget_text", {"query_budget": "3", "queries": [grep, tail]}),
        entry("budget_bool", {"query_budget": True, "queries": [grep, tail]}),
        entry("budget_float", {"query_budget": 2.5, "queries": [grep, tail, attest]}),
        entry("budget_huge", {"query_budget": 2 ** 63, "queries": [grep]}),
        entry("nine_queries", {"queries": [grep] * 9}),
        entry("nine_with_junk", {"queries": [grep] * 8 + [7]}),
        entry("output_empty", {"queries": [grep, tail, attest]}, output=""),
        entry("output_no_newline", {"queries": [tail]}, output="one line"),
        entry("output_crlf", {"queries": [grep, tail]},
              output="ERROR a\r\nERROR b\r\nc\r\n"),
        entry("output_many_lines", {"queries": [
            {"op": "tail", "lines": 200}, {"op": "grep", "pattern": "7"}]},
              output="".join(f"line {i}\n" for i in range(100))),
        # Past the caps: a grep over more lines than it may hand back,
        # a tail at its default and over its cap on more lines than
        # either.
        entry("grep_over_a_hundred", {"queries": [
            {"op": "grep", "pattern": ".", "max_matches": 1000},
            {"op": "grep", "pattern": "."}]},
              output="".join(f"l{i}\n" for i in range(120))),
        entry("tail_over_two_hundred", {"queries": [
            {"op": "tail"}, {"op": "tail", "lines": 250},
            {"op": "tail", "lines": 200}]},
              output="".join(f"l{i}\n" for i in range(210))),
        # The bound's own edges: a repeat whose maximum is 2, 0 and 1
        # around a repeat.
        entry("grep_repeat_max_two", {"queries": [
            {"op": "grep", "pattern": "(?:a+){2}"}]}),
        entry("grep_repeat_max_zero", {"queries": [
            {"op": "grep", "pattern": "(?:a+){0}"}]}),
        entry("grep_repeat_optional", {"queries": [
            {"op": "grep", "pattern": "(?:a+)?b"}]}),
        entry("output_unicode", {"queries": [grep, tail]},
              output="caf\u00e9 \u2014 \u4e2d\u6587 \U0001f426\nERROR \u00e9\n"),
        entry("output_nul", {"queries": [grep, tail]},
              output="ERROR \x00 here\n\x00\n"),
        entry("output_number", {"queries": [tail]}, output=7),
        entry("output_object", {"queries": [tail]}, output={"a": 1}),
        entry("stderr_too", {"queries": [grep, tail]},
              stderr="ERROR on stderr\n" + canary),
        entry("policy_carries_output", {"view": "summary", "queries": [
            {"op": "attest", "predicate": canary.strip()}]}),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def seeds_names():
    long_part = "p" * FN.MAX_COMPONENT_BYTES
    out = [
        ("plain", "a"), ("file", "a.txt"), ("nested", "dir/sub/file.tar.gz"),
        ("deep", "/".join(["d"] * 32)), ("dot_file", ".hidden"),
        ("dot_dir", ".git/config"), ("dots_in_name", "a.b.c"),
        ("underscore", "_x_"), ("digits", "0123"),
        ("flag", "-x"), ("flag_inside", "a/-x"), ("flag_dot", "-"),
        ("dot", "."), ("dotdot", ".."), ("dotdot_inside", "a/../b"),
        ("dotdot_first", "../a"), ("dot_inside", "a/./b"),
        ("three_dots", "..."), ("dots_then_name", "...a"),
        ("trailing_dot", "a."), ("trailing_dots", "a.."),
        ("absolute", "/etc/passwd"), ("double_slash_first", "//server/share"),
        ("drive", "C:a"), ("drive_slash", "C:/a"), ("drive_lower", "c:x"),
        ("drive_inside", "a/C:b"), ("backslash", "a\\b"),
        ("backslash_abs", "C:\\x"), ("unc", "\\\\server\\share"),
        ("doubled_slash", "a//b"), ("trailing_slash", "a/"),
        ("leading_slash_name", "/a"), ("empty", ""),
        ("space", "a b"), ("tab", "a\tb"), ("newline", "a\nb"),
        ("nul", "a\x00b"), ("colon", "a:b"), ("tilde", "~"),
        ("home", "~/x"), ("dollar", "$HOME"), ("percent", "%2e%2e/x"),
        ("unicode", "caf\u00e9"), ("emoji", "\U0001f426.txt"),
        ("fullwidth_slash", "a\uff0fb"), ("lone_surrogate", "a\ud800b"),
        ("con", "CON"), ("con_lower", "con"), ("con_ext", "con.txt"),
        ("nul_inside", "a/NUL"), ("nul_ext_dir", "nul.d/x"),
        ("com1", "COM1"), ("com9_ext", "COM9.log"), ("com10", "COM10"),
        ("lpt1", "LPT1"), ("lpt0", "LPT0"), ("aux_tar", "aux.tar.gz"),
        ("prn_prefix", "PRNT"), ("conx", "CONX"),
        ("component_cap", long_part), ("component_over", long_part + "p"),
        ("component_cap_nested", long_part + "/" + long_part),
        ("name_cap", "/".join(["q" * 63] * 16)),
        ("name_over", "/".join(["q" * 63] * 16) + "/q"),
        ("name_cap_bytes", "/".join(["r" * 127] * 8)),
        ("name_over_bytes", "/".join(["r" * 127] * 8) + "r"),
        ("job_id_cap", "j" * 128), ("job_id_over", "j" * 129),
        # Refused names whose shown form sits at the cut of the
        # rejection's text (sixty characters of repr).
        ("shown_57", "-" + "s" * 56), ("shown_58", "-" + "s" * 57),
        ("shown_59", "-" + "s" * 58), ("shown_60", "-" + "s" * 59),
        ("shown_61", "-" + "s" * 60),
        ("job_id_uuid", "6f1d2c3b-4a5e-4f60-8a7b-9c0d1e2f3a4b"),
        ("job_id_dotted", "d.bm-draft-0017"),
        ("not_text_number", 7), ("not_text_list", ["a"]),
        ("not_text_null", None), ("not_text_object", {"name": "a"}),
    ]
    return [make_entry("text" if isinstance(t, str) else "payload", t,
                       "seed:" + n, "seed") for n, t in out]


def seeds_query():
    canary = "SECRET-12345 is the canary line of the output\n"
    output = "ok\n" + canary + "ERROR one\nERROR two\nwarn: three\n"
    grep = {"op": "grep", "pattern": "ERROR", "max_matches": 5}
    tail = {"op": "tail", "lines": 3}
    attest = {"op": "attest", "predicate": "exit_zero"}

    def retained(**extra):
        rec = {"job_id": "bm-job-0001", "kind": "exec", "script": "echo",
               "stdout": output, "stderr": "", "exit_code": 0,
               "timed_out": False, "duration_sec": 0.5, "view": "full",
               "budget": 8, "spent": 0, "patterns": _QUERY_PATTERNS,
               "confined": True, "digest": "d" * 96, "saved_at": NOW,
               "judgment": None, "artifact_scan": [], "remediation": None}
        rec.update(extra)
        return rec

    def query(**extra):
        q = {"v": 1, "type": "query", "query_id": "bm-q-0001",
             "job_id": "bm-job-0001", "issued_at": NOW,
             "queries": [attest, grep, tail]}
        q.update(extra)
        return q

    def entry(name, q=None, rec="default", **top):
        data = {"subject_id": "bm-q-0001", "query": q or query(),
                "retained": retained() if rec == "default" else rec}
        data.update(top)
        return (name, data)

    sense_set = [
        {"severity": "critical", "title": "bm-sense-crit",
         "observed_at": "2026-10-26T09:00:00Z"},
        {"severity": "high", "title": "bm-sense-high",
         "observed_at": "2026-10-26T10:00:00Z"},
        {"severity": "medium", "title": "bm-sense-med",
         "observed_at": "2026-10-26T11:00:00Z"},
        {"severity": "low", "title": "bm-sense-low",
         "observed_at": "2026-10-26T12:00:00Z",
         "detail": {"path": "/srv/example/low.txt", "count": 2}},
        {"severity": "info", "title": "bm-sense-info"},
    ]

    out = [
        entry("happy"),
        entry("keyed", key_id="ops"),
        entry("fingerprint_key", key_id=FP),
        entry("other_fingerprint_key", key_id=FP_OPS),
        entry("canary_key", key_id="canary-key"),
        entry("no_record", rec=None),
        entry("record_expired", rec=retained(saved_at=1.0)),
        entry("record_no_saved_at", rec=retained(saved_at=None)),
        entry("record_saved_at_text", rec=retained(saved_at="yesterday")),
        entry("record_summary", rec=retained(view="summary")),
        entry("record_attested", rec=retained(view="attested")),
        entry("record_redacted", rec=retained(view="redacted"),
              q=query(queries=[{"op": "grep", "pattern": "SECRET"}, tail])),
        entry("record_view_unknown", rec=retained(view="wide")),
        entry("record_view_number", rec=retained(view=7)),
        entry("record_budget_text", rec=retained(budget="eight")),
        entry("record_budget_null", rec=retained(budget=None)),
        entry("record_budget_zero", rec=retained(budget=0)),
        entry("record_spent_all", rec=retained(spent=8)),
        entry("record_spent_over", rec=retained(spent=9)),
        entry("record_spent_text", rec=retained(spent="three")),
        entry("record_spent_float", rec=retained(spent=2.5)),
        entry("record_no_stdout", rec=retained(stdout=None)),
        entry("record_stdout_number", rec=retained(stdout=7)),
        entry("record_stdout_list", rec=retained(stdout=["a", "b"])),
        # A stream that is not text is no text (Q90): an empty list or
        # object, a list of lines, a number, where the executor wrote
        # text; nothing of their text form is an output line.
        entry("record_stderr_empty_list", rec=retained(stderr=[]),
              q=query(queries=[attest, grep, tail])),
        entry("record_stderr_empty_object", rec=retained(stderr={}),
              q=query(queries=[tail])),
        entry("record_stderr_list", rec=retained(stderr=["warn: x", "warn: y"]),
              q=query(queries=[tail, grep])),
        entry("record_stderr_number", rec=retained(stderr=7),
              q=query(queries=[tail])),
        entry("record_streams_not_text", rec=retained(stdout=["a"], stderr={"b": 1}),
              q=query(queries=[tail, grep, attest])),
        # The senses store as the runner left it (docs/extend/senses.md):
        # alerts planted through the local ingest, then the senses op
        # with its filters -- the sensor, the severity floor, the
        # window, the limit -- and the answer's own shape.
        entry("senses_all", senses=sense_set, q=query(queries=[
            {"op": "senses"}])),
        entry("senses_canary", senses=sense_set, q=query(queries=[
            {"op": "senses", "sensor": "canary"}])),
        entry("senses_other_sensor", senses=sense_set, q=query(queries=[
            {"op": "senses", "sensor": "other"}])),
        entry("senses_floor_medium", senses=sense_set, q=query(queries=[
            {"op": "senses", "severity_floor": "medium"}])),
        entry("senses_floor_critical", senses=sense_set, q=query(queries=[
            {"op": "senses", "severity_floor": "critical"}])),
        entry("senses_floor_unknown", senses=sense_set, q=query(queries=[
            {"op": "senses", "severity_floor": "loud"}])),
        entry("senses_since", senses=sense_set, q=query(queries=[
            {"op": "senses", "since": "2026-10-26T10:30:00Z"}])),
        entry("senses_until", senses=sense_set, q=query(queries=[
            {"op": "senses", "until": "2026-10-26T10:30:00Z"}])),
        entry("senses_window", senses=sense_set, q=query(queries=[
            {"op": "senses", "since": "2026-10-26T09:30:00Z",
             "until": "2026-10-26T10:30:00Z"}])),
        entry("senses_since_junk", senses=sense_set, q=query(queries=[
            {"op": "senses", "since": "yesterday", "until": 7}])),
        entry("senses_limit_one", senses=sense_set, q=query(queries=[
            {"op": "senses", "limit": 1}])),
        entry("senses_limit_zero", senses=sense_set, q=query(queries=[
            {"op": "senses", "limit": 0}])),
        entry("senses_limit_junk", senses=sense_set, q=query(queries=[
            {"op": "senses", "limit": "many", "sensor": 7,
             "severity_floor": None}])),
        entry("senses_redacted", senses=sense_set, rec=retained(view="redacted"),
              q=query(queries=[{"op": "senses"}])),
        entry("senses_none_stored", senses=[{"sensor": "other"}, 7, None,
                                            {"detail": "a line"}],
              q=query(queries=[{"op": "senses"}])),
        entry("senses_no_severity", senses=[{"severity": None},
                                            {"severity": "loud"}],
              q=query(queries=[{"op": "senses", "severity_floor": "info"},
                               {"op": "senses", "severity_floor": "low"}])),
        entry("senses_many", senses=[{"severity": "low",
                                      "title": f"bm-s-{n}"} for n in range(8)],
              q=query(queries=[{"op": "senses", "limit": 5},
                               {"op": "senses"}])),
        # A lone surrogate in a retained stream (Q93): the escape a
        # record a crash left can hold, which no signer accepts; on
        # the wire it is the replacement character, in every op.
        entry("record_stderr_surrogate", rec=retained(stderr="\ud800"),
              q=query(queries=[attest, grep, tail])),
        entry("record_stdout_surrogate_line", rec=retained(
            stdout="ok\nbad \udfff line\nERROR one\n"),
            q=query(queries=[tail, grep, {"op": "attest",
                                          "predicate": "output_digest"}])),
        entry("record_stdout_surrogate_pair", rec=retained(
            stdout="ok\n\ud83d\udc26 bird\n"),
            q=query(queries=[{"op": "tail", "lines": 1}])),
        entry("record_pattern_overflow", rec=retained(
            view="redacted", patterns={"x": "a{99999999999}"}),
            q=query(queries=[tail, {"op": "grep", "pattern": "ERROR"}])),
        entry("record_patterns_list", rec=retained(patterns=["x"])),
        entry("record_patterns_bad", rec=retained(patterns={"x": "("})),
        entry("record_patterns_number_key", rec=retained(patterns={"1": "a"})),
        entry("record_digest_null", rec=retained(digest=None)),
        entry("record_exit_text", rec=retained(exit_code="zero")),
        entry("record_is_list", rec=[1, 2]),
        entry("record_is_text", rec="retained"),
        entry("record_empty", rec={}),
        entry("record_extra_members", rec=retained(note="x", nested={"a": 1})),
        entry("query_v2", q=query(v=2)),
        entry("query_v_text", q=query(v="1")),
        entry("query_type_job", q=query(type="job")),
        entry("query_no_type", q={k: v for k, v in query().items()
                                   if k != "type"}),
        entry("query_id_other", q=query(query_id="bm-q-0002")),
        entry("query_id_number", q=query(query_id=7)),
        entry("query_no_id", q={k: v for k, v in query().items()
                                 if k != "query_id"}),
        entry("job_id_unknown", q=query(job_id="bm-job-0009")),
        entry("job_id_unsafe", q=query(job_id="../x")),
        entry("job_id_dot", q=query(job_id=".")),
        entry("job_id_number", q=query(job_id=7)),
        entry("job_id_null", q=query(job_id=None)),
        entry("no_job_id", q={k: v for k, v in query().items()
                               if k != "job_id"}),
        entry("stale", q=query(issued_at="2020-01-01T00:00:00Z")),
        entry("future", q=query(issued_at="2099-01-01T00:00:00Z")),
        entry("issued_at_no_zone", q=query(issued_at="2026-10-26T12:00:00")),
        entry("issued_at_number", q=query(issued_at=7)),
        entry("no_issued_at", q={k: v for k, v in query().items()
                                  if k != "issued_at"}),
        entry("queries_empty", q=query(queries=[])),
        entry("queries_object", q=query(queries={"op": "grep"})),
        entry("queries_text", q=query(queries="grep")),
        entry("queries_null", q=query(queries=None)),
        entry("no_queries", q={k: v for k, v in query().items()
                                if k != "queries"}),
        entry("queries_junk", q=query(queries=[7, None, "grep", [], {}])),
        entry("nine_queries", q=query(queries=[grep] * 9)),
        entry("grep_bad_pattern", q=query(queries=[
            {"op": "grep", "pattern": "("}, grep])),
        entry("grep_nested", q=query(queries=[
            {"op": "grep", "pattern": "(a+)+$"}])),
        entry("ask_and_senses", q=query(queries=[
            {"op": "ask", "question": "print it"},
            {"op": "senses", "sensor": "canary"}])),
        entry("subject_other", subject_id="bm-q-0007"),
        entry("subject_unsafe", subject_id="../x"),
        entry("subject_long", subject_id="q" * 200),
        entry("extra_members", q=query(note="hello", nested={"a": [1]})),
        entry("sig_member", q=query(sig="0" * 96)),
        entry("key_id_in_body", q=query(key_id="ops")),
        entry("key_id_mismatch", q=query(key_id="ops"), key_id="canary-key"),
        entry("runner_id_in_body", q=query(runner_id="bm-runner")),
        # The operator's flags and the message's form: a dry run acks
        # nothing and records nothing; no_send acts and sends nothing;
        # a signed but unsealed query is refused as cleartext.
        entry("dry_run", dry=True),
        entry("no_send", no_send=True),
        entry("dry_no_send", dry=True, no_send=True),
        entry("cleartext", cleartext=True),
        entry("cleartext_keyed", cleartext=True, key_id="ops"),
        entry("dry_no_record", rec=None, dry=True),
        # The hourly window (PROTOCOL section 11) as the runner left
        # it: full for this sender, one under the cap, full for another
        # sender, stale, and as a crash left the file.
        entry("rate_limited", window=4),
        entry("rate_limited_keyed", window=4, key_id="ops"),
        entry("rate_limited_fingerprint", window=4, key_id=FP),
        entry("rate_limited_dry", window=4, dry=True),
        entry("rate_limited_unsupported", window=4, q=query(type="job")),
        entry("window_one_under_cap", window=3),
        entry("window_over_cap", window=9),
        entry("window_other_sender", key_id="ops",
              window=json.dumps({"": [NOW] * 4})),
        entry("window_stale", window=json.dumps({"": [1.0] * 4})),
        entry("window_mixed", window=json.dumps({"": [1.0, NOW, "x", None,
                                                       NOW, 1e400]})),
        entry("window_future", window=json.dumps({"": [4102444800.0] * 4})),
        entry("window_infinite", window=json.dumps({"": [1e400] * 4})),
        entry("window_not_json", window="not json"),
        entry("window_list", window="[1, 2, 3]"),
        entry("window_times_not_list", window=json.dumps({"": "NOW"})),
        entry("window_empty_file", window=""),
        # The record's streams and marks under the queries that read
        # them: stderr lines through tail and grep, the attestations
        # of the digest, the confinement and the exit.
        entry("record_stderr_tail", rec=retained(stderr="warn: a\nwarn: b\n"),
              q=query(queries=[{"op": "tail", "lines": 2}])),
        entry("record_stderr_grep", rec=retained(stderr="ERROR three\n"),
              q=query(queries=[grep])),
        entry("attest_digest", q=query(queries=[
            {"op": "attest", "predicate": "output_digest"}])),
        entry("attest_confined", q=query(queries=[
            {"op": "attest", "predicate": "confined_to_workspace"}])),
        entry("attest_unconfined", rec=retained(confined=None), q=query(
            queries=[{"op": "attest", "predicate": "confined_to_workspace"}])),
        entry("attest_no_secrets", q=query(queries=[
            {"op": "attest", "predicate": "no_secrets"}])),
        entry("attest_exit_nonzero", rec=retained(exit_code=3),
              q=query(queries=[attest])),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def seeds_board_mail():
    claimed = dict(_task(), state="claimed", claimed_by="worker-a",
                   submitted_at="2026-10-26T12:00:00+00:00",
                   claimed_at="2026-10-26T12:00:01+00:00")
    done = dict(_task("bm-task-0000"), state="done",
                submitted_at="2026-10-26T11:00:00+00:00")
    open_task = dict(_task(), state="open",
                     submitted_at="2026-10-26T12:00:00+00:00")
    stale_claim = dict(claimed, claimed_at="2026-10-26T11:00:00+00:00")

    def submit(tid="bm-task-0001", **extra):
        p = {"v": 1, "type": "task_submit"}
        p.update(_task(tid))
        p.update(extra)
        return p

    def request(worker="worker-a", caps=("shell",), **extra):
        p = {"v": 1, "type": "task_request", "worker_id": worker,
             "capabilities": list(caps)}
        p.update(extra)
        return p

    def result(tid="bm-task-0001", res=None, **extra):
        p = {"v": 1, "type": "task_result", "task_id": tid,
             "result": {"exit_code": 0, "stdout": "task"} if res is None
             else res}
        p.update(extra)
        return p

    def approve(tid="bm-task-0001", **extra):
        p = {"v": 1, "type": "task_approve", "task_id": tid}
        p.update(extra)
        return p

    def entry(name, kind, ident, payload, file=None, **top):
        d = {"kind": kind, "ident": ident, "payload": payload, "file": file}
        d.update(top)
        return (name, d)

    out = [
        entry("submit", "task_submit", "bm-task-0001", submit()),
        entry("submit_keyed", "task_submit", "bm-task-0001", submit(),
              key_id="ops"),
        entry("submit_fingerprint_key", "task_submit", "bm-task-0001",
              submit(), key_id=FP),
        entry("submit_other_fingerprint_key", "task_submit", "bm-task-0001",
              submit(), key_id=FP_OPS),
        entry("submit_reply_to", "task_submit", "bm-task-0001",
              submit(reply_to="worker@example.com")),
        entry("submit_reply_to_header_only", "task_submit", "bm-task-0001",
              submit(reply_to="not an address")),
        entry("submit_reply_to_long", "task_submit", "bm-task-0001",
              submit(reply_to="w" * 250 + "@example.com")),
        entry("submit_duplicate", "task_submit", "bm-task-0001", submit(),
              file=_board_file(open_task)),
        entry("submit_other_id", "task_submit", "bm-task-0002", submit()),
        entry("submit_bad_id", "task_submit", "bm-task-0001", submit("../x")),
        entry("submit_no_v", "task_submit", "bm-task-0001",
              {k: v for k, v in submit().items() if k != "v"}),
        entry("submit_v2", "task_submit", "bm-task-0001", submit(v=2)),
        entry("submit_priority_nan", "task_submit", "bm-task-0001",
              submit(priority=float("nan"))),
        entry("submit_priority_text", "task_submit", "bm-task-0001",
              submit(priority="high")),
        entry("submit_requires_number", "task_submit", "bm-task-0001",
              submit(requires=[7])),
        entry("submit_huge_payload", "task_submit", "bm-task-0001",
              submit(payload={"script": "x" * 4000})),
        entry("submit_type_job", "task_submit", "bm-task-0001",
              submit(type="job")),
        entry("submit_runner_id", "task_submit", "bm-task-0001",
              submit(runner_id="bm-runner")),
        entry("request_open", "task_request", "worker-a", request(),
              file=_board_file(open_task)),
        entry("request_empty_board", "task_request", "worker-a", request()),
        entry("request_not_allowed", "task_request", "nobody", request("nobody"),
              file=_board_file(open_task)),
        entry("request_no_caps", "task_request", "worker-a", request(caps=()),
              file=_board_file(open_task)),
        entry("request_caps_text", "task_request", "worker-a",
              request(capabilities="shell"), file=_board_file(open_task)),
        entry("request_caps_junk", "task_request", "worker-a",
              request(capabilities=[7, None, "shell"]),
              file=_board_file(open_task)),
        entry("request_compartment", "task_request", "worker-a", request(),
              file=_board_file(dict(open_task, compartments=["red"]))),
        entry("request_dag_withheld", "task_request", "worker-b",
              request("worker-b"),
              file=_board_file(dict(open_task, requires=["bm-task-0009"]))),
        entry("request_dag_done", "task_request", "worker-b",
              request("worker-b"),
              file=_board_file(done, dict(open_task, requires=["bm-task-0000"]))),
        entry("request_own_claim", "task_request", "worker-a", request(),
              file=_board_file(claimed)),
        entry("request_keyed", "task_request", "worker-a", request(),
              file=_board_file(open_task), key_id="ops"),
        entry("request_reply_to", "task_request", "worker-a",
              request(reply_to="worker@example.com"),
              file=_board_file(open_task)),
        entry("request_subject_mismatch", "task_request", "worker-b",
              request("worker-a"), file=_board_file(open_task)),
        entry("result_done", "task_result", "bm-task-0001", result(),
              file=_board_file(claimed)),
        entry("result_review", "task_result", "bm-task-0001", result(),
              file=_board_file(claimed), review=True),
        entry("result_not_claimed", "task_result", "bm-task-0001", result(),
              file=_board_file(open_task)),
        entry("result_unknown", "task_result", "bm-task-0009", result("bm-task-0009"),
              file=_board_file(claimed)),
        entry("result_text", "task_result", "bm-task-0001",
              result(res="a string result"), file=_board_file(claimed)),
        entry("result_null", "task_result", "bm-task-0001",
              {"v": 1, "type": "task_result", "task_id": "bm-task-0001",
               "result": None}, file=_board_file(claimed)),
        entry("result_no_member", "task_result", "bm-task-0001",
              {"v": 1, "type": "task_result", "task_id": "bm-task-0001"},
              file=_board_file(claimed)),
        entry("result_huge", "task_result", "bm-task-0001",
              result(res={"stdout": "o" * 8000}), file=_board_file(claimed)),
        entry("result_nested", "task_result", "bm-task-0001",
              result(res={"a": {"b": {"c": [1, {"d": None}]}}}),
              file=_board_file(claimed)),
        entry("result_nan", "task_result", "bm-task-0001",
              result(res={"score": float("nan")}), file=_board_file(claimed)),
        entry("result_bad_id", "task_result", "../x", result("../x"),
              file=_board_file(claimed)),
        entry("approve_pending", "task_approve", "bm-task-0001", approve(),
              file=_board_file(dict(claimed, state="pending_review"))),
        entry("approve_done", "task_approve", "bm-task-0001", approve(),
              file=_board_file(dict(claimed, state="done"))),
        entry("approve_unknown", "task_approve", "bm-task-0009",
              approve("bm-task-0009")),
        entry("approve_bad_id", "task_approve", "../x", approve("../x")),
        entry("file_garbage", "task_submit", "bm-task-0001", submit(),
              file="{not json"),
        entry("file_list", "task_request", "worker-a", request(),
              file="[1, 2]"),
        entry("file_task_not_dict", "task_request", "worker-a", request(),
              file=json.dumps({"bm-task-0001": 7})),
        entry("file_nonfinite", "task_request", "worker-a", request(),
              file=_board_file(dict(open_task, priority=float("inf")))),
        entry("file_lease_old", "task_request", "worker-b", request("worker-b"),
              file=_board_file(dict(claimed,
                                    claimed_at="2020-01-01T00:00:00+00:00"))),
        entry("payload_list", "task_submit", "bm-task-0001", [1, 2]),
        entry("payload_text", "task_result", "bm-task-0001", "done",
              file=_board_file(claimed)),
        entry("ident_long", "task_submit", "t" * 200, submit("t" * 200)),
        entry("ident_dot", "task_approve", ".", approve(".")),
        entry("key_mismatch", "task_submit", "bm-task-0001",
              submit(key_id="ops"), key_id="canary-key"),
        entry("sig_member", "task_submit", "bm-task-0001",
              submit(sig="0" * 96)),
        # The operator's flags and the message's form.
        entry("submit_dry", "task_submit", "bm-task-0001", submit(), dry=True),
        entry("submit_no_send", "task_submit", "bm-task-0001", submit(),
              no_send=True),
        entry("request_dry", "task_request", "worker-a", request(),
              file=_board_file(open_task), dry=True),
        entry("request_no_send", "task_request", "worker-a", request(),
              file=_board_file(open_task), no_send=True),
        entry("result_no_send", "task_result", "bm-task-0001", result(),
              file=_board_file(claimed), no_send=True),
        entry("submit_cleartext", "task_submit", "bm-task-0001", submit(),
              cleartext=True),
        entry("request_cleartext", "task_request", "worker-a", request(),
              file=_board_file(open_task), cleartext=True),
        # The lease (task_timeout) as the owner wrote it, over a claim
        # an hour old on the board's clock: a short lease hands the
        # task to the next worker, the default keeps the claim, and a
        # lease that is not a number is the default.
        entry("request_lease_expired", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim), timeout=60),
        entry("request_lease_default", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim)),
        entry("request_lease_zero", "task_request", "worker-b",
              request("worker-b"), file=_board_file(claimed), timeout=0),
        entry("request_lease_null", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim), timeout=None),
        entry("request_lease_text", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim),
              timeout="soon"),
        entry("request_lease_bool", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim), timeout=True),
        entry("request_lease_negative", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim), timeout=-5),
        entry("request_lease_float", "task_request", "worker-b",
              request("worker-b"), file=_board_file(stale_claim), timeout=0.5),
        entry("request_claim_time_junk", "task_request", "worker-b",
              request("worker-b"),
              file=_board_file(dict(claimed, claimed_at="yesterday")),
              timeout=60),
        # A capabilities member the board cannot read as a list: the
        # board's own error is the reader's rejection, not its crash.
        entry("request_caps_number", "task_request", "worker-a",
              request(capabilities=5), file=_board_file(open_task)),
        entry("request_caps_object", "task_request", "worker-a",
              request(capabilities={"shell": True}),
              file=_board_file(open_task)),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def seeds_v2_mail():
    def q(**extra):
        o = {"v": 2, "type": "question", "job_id": "bm-job-0001",
             "msg_id": "q.bm-job-0001", "issued_at": NOW,
             "question": "Would this job succeed on this host?",
             "deadline_sec": 5, "local_default": "proceed",
             "context": [{"text": "a line of context"}]}
        o.update(extra)
        return o

    def a(**extra):
        o = {"v": 2, "type": "answer", "job_id": "bm-job-0001",
             "msg_id": "a.q.bm-job-0001", "question_id": "q.bm-job-0001",
             "issued_at": NOW, "answer": "the left"}
        o.update(extra)
        return o

    def d(**extra):
        o = {"v": 2, "type": "determination", "job_id": "bm-job-0001",
             "msg_id": "d.bm-job-0001", "issued_at": NOW,
             "clean_pass": False, "expect": "fail",
             "why": "the script references a missing path"}
        o.update(extra)
        return o

    def entry(name, kind, ident, payload, **top):
        data = {"kind": kind, "ident": ident, "payload": payload}
        data.update(top)
        return (name, data)

    out = [
        entry("question", "question", "q.bm-job-0001", q()),
        entry("question_keyed", "question", "q.bm-job-0001", q(), key_id="ops"),
        entry("question_fingerprint_key", "question", "q.bm-job-0001", q(),
              key_id=FP),
        entry("answer_fingerprint_key", "answer", "a.q.bm-job-0001", a(),
              key_id=FP),
        entry("question_other_fingerprint_key", "question", "q.bm-job-0001",
              q(), key_id=FP_OPS),
        entry("question_canary_key", "question", "q.bm-job-0001", q(),
              key_id="canary-key"),
        entry("question_answerer_listed", "question", "q.bm-job-0001", q(),
              key_id="ops", answerers=["ops"]),
        entry("question_answerer_other", "question", "q.bm-job-0001", q(),
              answerers=["ops"]),
        entry("question_answerers_junk", "question", "q.bm-job-0001", q(),
              answerers=[7, None]),
        entry("question_default_long", "question", "q.bm-job-0001",
              q(local_default="d" * 64)),
        entry("question_default_spaces", "question", "q.bm-job-0001",
              q(local_default="   hold   ")),
        entry("question_no_context", "question", "q.bm-job-0001",
              {k: v for k, v in q().items() if k != "context"}),
        entry("question_stale", "question", "q.bm-job-0001",
              q(issued_at="2020-01-01T00:00:00Z")),
        entry("question_future", "question", "q.bm-job-0001",
              q(issued_at="2099-01-01T00:00:00Z")),
        entry("question_offset", "question", "q.bm-job-0001",
              q(issued_at="2026-10-26T12:00:00+00:00")),
        entry("question_subject_other", "question", "q.bm-job-0002", q()),
        entry("question_type_answer", "question", "q.bm-job-0001",
              q(type="answer")),
        entry("question_v1", "question", "q.bm-job-0001", q(v=1)),
        entry("question_deadline_over", "question", "q.bm-job-0001",
              q(deadline_sec=99)),
        entry("question_long", "question", "q.bm-job-0001",
              q(question="w" * 501)),
        entry("question_id_unsafe", "question", "q.bm-job-0001",
              q(msg_id="../x")),
        entry("question_job_unsafe", "question", "q.bm-job-0001",
              q(job_id="../x")),
        entry("question_extra", "question", "q.bm-job-0001",
              q(note="x", nested={"a": [1]})),
        entry("question_sig", "question", "q.bm-job-0001", q(sig="0" * 96)),
        entry("question_key_mismatch", "question", "q.bm-job-0001",
              q(key_id="ops"), key_id="canary-key"),
        entry("answer", "answer", "a.q.bm-job-0001", a()),
        entry("answer_keyed", "answer", "a.q.bm-job-0001", a(), key_id="ops"),
        entry("answer_long", "answer", "a.q.bm-job-0001", a(answer="a" * 500)),
        entry("answer_over", "answer", "a.q.bm-job-0001", a(answer="a" * 501)),
        entry("answer_empty", "answer", "a.q.bm-job-0001", a(answer="   ")),
        entry("answer_question_unsafe", "answer", "a.q.bm-job-0001",
              a(question_id="../x")),
        entry("answer_no_question", "answer", "a.q.bm-job-0001",
              {k: v for k, v in a().items() if k != "question_id"}),
        entry("answer_stale", "answer", "a.q.bm-job-0001",
              a(issued_at="2020-01-01T00:00:00Z")),
        entry("answer_subject_other", "answer", "a.q.bm-job-0009", a()),
        entry("answer_type_question", "answer", "a.q.bm-job-0001",
              a(type="question")),
        entry("determination", "determination", "d.bm-job-0001", d()),
        entry("determination_unknown", "determination", "d.bm-job-0001",
              d(expect="unknown")),
        entry("determination_proceed", "determination", "d.bm-job-0001",
              d(expect="proceed")),
        entry("determination_clean", "determination", "d.bm-job-0001",
              d(clean_pass=True)),
        entry("determination_why_over", "determination", "d.bm-job-0001",
              d(why="w" * 501)),
        entry("determination_stale", "determination", "d.bm-job-0001",
              d(issued_at="2020-01-01T00:00:00Z")),
        entry("determination_subject_other", "determination", "d.bm-job-0002",
              d()),
        entry("payload_list", "question", "q.bm-job-0001", [1, 2]),
        entry("payload_text", "question", "q.bm-job-0001", "which path"),
        entry("payload_empty", "question", "q.bm-job-0001", {}),
        entry("ident_long", "question", "q" * 200, q(msg_id="q" * 200)),
        entry("ident_dot", "question", ".", q(msg_id=".")),
        # The operator's flags and the message's form.
        entry("question_dry", "question", "q.bm-job-0001", q(), dry=True),
        entry("question_no_send", "question", "q.bm-job-0001", q(),
              no_send=True),
        entry("answer_dry", "answer", "a.q.bm-job-0001", a(), dry=True),
        entry("determination_dry", "determination", "d.bm-job-0001", d(),
              dry=True),
        entry("question_cleartext", "question", "q.bm-job-0001", q(),
              cleartext=True),
        entry("answer_cleartext", "answer", "a.q.bm-job-0001", a(),
              cleartext=True),
        # The answerer's model: configured and down (the local default
        # answers, the call logged), configured under the deterministic
        # Oracle (never called), and a mode that is not a mode.
        entry("question_model_down", "question", "q.bm-job-0001", q(),
              model_down=True),
        entry("question_model_down_deterministic", "question",
              "q.bm-job-0001", q(), model_down=True, mode="deterministic"),
        entry("question_mode_unknown", "question", "q.bm-job-0001", q(),
              model_down=True, mode="chatty"),
        entry("answer_model_down", "answer", "a.q.bm-job-0001", a(),
              model_down=True),
        # The two switches: a process with neither ignores the
        # message (marked, nothing else); one that emits but does not
        # answer leaves a question for another reader, unseen, and
        # still files an answer and reads a determination; a question
        # it would refuse before that point is refused as before.
        entry("question_v2_off", "question", "q.bm-job-0001", q(),
              v2=False, answer_only=False),
        entry("question_answer_only_off", "question", "q.bm-job-0001", q(),
              answer_only=False),
        entry("question_answer_only_off_keyed", "question", "q.bm-job-0001",
              q(), answer_only=False, key_id="ops"),
        entry("question_answer_only_off_stale", "question", "q.bm-job-0001",
              q(issued_at="2020-01-01T00:00:00Z"), answer_only=False),
        entry("question_answer_only_off_other_answerer", "question",
              "q.bm-job-0001", q(), answer_only=False, answerers=["ops"]),
        entry("question_answer_only_off_cleartext", "question",
              "q.bm-job-0001", q(), answer_only=False, cleartext=True),
        entry("question_answer_only_off_dry", "question", "q.bm-job-0001",
              q(), answer_only=False, dry=True),
        entry("question_switches_junk", "question", "q.bm-job-0001", q(),
              v2="yes", answer_only=1),
        entry("answer_answer_only_off", "answer", "a.q.bm-job-0001", a(),
              answer_only=False),
        entry("answer_v2_off", "answer", "a.q.bm-job-0001", a(),
              v2=False, answer_only=False),
        entry("determination_answer_only_off", "determination",
              "d.bm-job-0001", d(), answer_only=False),
        entry("determination_v2_off", "determination", "d.bm-job-0001", d(),
              v2=False, answer_only=False),
        # The answer's id at the bound: a.<question id> while that
        # fits the 128, the digest form past it.
        entry("question_id_126", "question", "q" * 126, q(msg_id="q" * 126)),
        entry("question_id_127", "question", "q" * 127, q(msg_id="q" * 127)),
        entry("question_id_128", "question", "q" * 128, q(msg_id="q" * 128)),
        # The filed record and the late answers: an answer whose text
        # is the cap, and one with every member the draft allows.
        entry("answer_at_cap", "answer", "a.q.bm-job-0001", a(answer="x" * 500)),
        entry("answer_unicode", "answer", "a.q.bm-job-0001",
              a(answer="the left \u2014 caf\u00e9 \U0001f426")),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


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
    return {"de_dust": 1, "Agent-Stamp": STAMP,
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


def _depth(value):
    """How deep a JSON value nests (a scalar 0, a list of scalars 1).
    A stack, not recursion: a child grafted deeper than the
    interpreter's recursion limit is measured, not a worker death
    (Q95)."""
    deepest = 0
    stack = [(value, 0)]
    while stack:
        item, d = stack.pop()
        if d > deepest:
            deepest = d
        if isinstance(item, dict):
            stack.extend((v, d + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, d + 1) for v in item)
    return deepest


def _paths(value, prefix=()):
    """Every (path, value) in a JSON value, the root included, in
    walk order; a stack, not recursion (Q95)."""
    stack = [(prefix, value)]
    while stack:
        path, item = stack.pop()
        yield path, item
        if isinstance(item, dict):
            stack.extend((path + (k,), v)
                         for k, v in reversed(list(item.items())))
        elif isinstance(item, list):
            stack.extend((path + (i,), v)
                         for i, v in reversed(list(enumerate(item))))


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
    # A value already past the bound is left alone (a no-op child,
    # which the session drops): the grafts of p_replace and p_splice
    # compound across generations, and the walks along a path are as
    # deep as the value (Q95).
    if _depth(value) > MAX_DEPTH:
        return value
    for _ in range(rng.randint(1, 3)):
        value = rng.choice(PAYLOAD_MUTATORS)(rng, value, corpus)
        if _depth(value) > MAX_DEPTH:
            return value
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
        if _depth(entry["data"]) > MAX_DEPTH:
            return None
        mut = pick(rng, PAYLOAD_MUTATORS, weights)
        data = mut(rng, entry["data"], corpus)
        name = mut.__name__
    if entry["kind"] == "payload":
        # The bound the mutators may nest to (p_nest keeps it; a
        # graft of a corpus value can pass it, and the grafts
        # compound across generations): a child past it is not a
        # child (Q95).
        if _depth(data) > MAX_DEPTH:
            return None
        try:
            text = json.dumps(data, ensure_ascii=True)
        except (TypeError, ValueError, RecursionError):
            return None
        if len(text) > MAX_PAYLOAD:
            return None
        data = json.loads(text)
    if target == "queries" and isinstance(data, dict) and (
            len(_query_text(data.get("output")))
            + len(_query_text(data.get("stderr"))) > QUERIES_MAX_TEXT):
        return None
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
    "queries": {"files": [_src("ops", "policy.py"), _src("ops", "queries.py"),
                          _src("ops", "attest.py"),
                          _src("guard", "security.py")],
                "check": check_queries, "seeds": seeds_queries},
    "names": {"files": [_src("guard", "filenames.py"), _src("runner.py")],
              "check": check_names, "seeds": seeds_names},
    "query": {"files": [_src("ops", "queries.py"), _src("runner.py"),
                        _src("ops", "policy.py"), _src("ops", "attest.py")],
              "check": check_query, "seeds": seeds_query},
    "board_mail": {"files": [_src("ops", "startup.py"), _src("wire", "board.py"),
                             _src("runner.py"), _src("wire", "mailbox.py")],
                   "check": check_board_mail, "seeds": seeds_board_mail},
    "v2_mail": {"files": [_src("ops", "handlers.py"),
                          _src("wire", "protocol_v2.py"), _src("runner.py")],
                "check": check_v2_mail, "seeds": seeds_v2_mail},
}


def corpus_path(target, crashes=False):
    name = target + (".crashes.jsonl" if crashes else ".jsonl")
    return os.path.join(CORPUS_DIR, name)


def header(target):
    return {"de_dust": 1, "target": target, "Agent-Stamp": STAMP}


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
            if "de_dust" in obj and "data" not in obj:
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
        json.dump({"de_dust": 1, "target": target, "Agent-Stamp": STAMP,
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
            fh.write(json.dumps({"de_dust": 1, "file": "runs",
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
        self.mutator_errors = {}
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
        self.mutator_errors = {}
        for n in range(rounds):
            parent = rng.choice(self.entries)
            try:
                child = mutate(rng, parent, self.entries, self.target,
                               weights)
            except Exception as e:
                # The mutator's fault, not the reader's: counted in the
                # run record, logged, and the grow goes on (Q95). A
                # reader's fault is a Crash from the checker, below.
                kind = type(e).__name__
                self.mutator_errors[kind] = \
                    self.mutator_errors.get(kind, 0) + 1
                if log:
                    log(f"  mutator raised at round {n}: {kind}: "
                        f"{_short(e)}")
                continue
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


def merge_seeds(session):
    """The seeds a session's corpus lacks, added by id, and returned.
    An existing corpus keeps every entry it has (so a new seed
    function never discards what the grows found), and a seed whose
    shape changed under a name the corpus already holds is added
    beside the old one; the seeds are deterministic, so the same
    shape is never added twice. `seed` and `grow` both call this,
    so a seed the desk writes reaches the corpus on the campaign's
    next grow, with no step between."""
    fresh = [e for e in TARGETS[session.target]["seeds"]()
             if e["id"] not in session.ids]
    for e in fresh:
        session.entries.append(e)
        session.ids.add(e["id"])
    return fresh


def cmd_seed(args, out=print):
    """Write the seeds (merge_seeds), with the corpus's baseline run
    and recorded."""
    for target in _targets(args.target):
        existing = load(corpus_path(target))
        session = Session(target, existing)
        fresh = merge_seeds(session)
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
        self._fh.write(json.dumps({"de_dust": 1, "archive": target,
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
        rounds = int(os.environ.get("HP_DE_DUST_ROUNDS", DEFAULT_ROUNDS))
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
        out(f"de_dust grow: {rounds} rounds, rng seed {seed}, "
            f"{min(args.jobs, len(targets))} targets at a time"
            + (f", for {minutes:g} minutes" if minutes else ""))
        return run_parallel(grow_commands(targets, rounds, seed,
                                          args.verbose,
                                          getattr(args, "archive", None),
                                          getattr(args, "no_steer", False)),
                            args.jobs, out=out, minutes=minutes)
    out(f"de_dust grow: {rounds} rounds, rng seed {seed}")
    status = 0
    for target in targets:
        rng = random.Random(seed)
        entries = load(corpus_path(target))
        session = Session(target, entries)
        # A target without a corpus yet (a reader the desk just put
        # on the surface) starts from its seeds here.
        fresh = merge_seeds(session)
        if not session.entries:
            out(f"{target}: no corpus and no seeds")
            status = 2
            continue
        for e in fresh:
            e["arcs"] = 0
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
        if added or fresh:
            save(corpus_path(target), target, session.entries)
        write_arcs(target, session.tracer.arcs)
        extra = {}
        if archived:
            extra["archive"] = archived
        if history is not None:
            extra["steered"] = True
        if fresh:
            extra["seeds_added"] = len(fresh)
        if getattr(session, "mutator_errors", None):
            extra["mutator_errors"] = dict(session.mutator_errors)
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
    """Rebuild runner/tests/de_dust/grammar.json from the drafts."""
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
                                "(HP_DE_DUST_ROUNDS, default %d)"
                                % DEFAULT_ROUNDS)
            p.add_argument("--seed", type=int, default=None,
                           help="rng seed (default: random, printed)")
            p.add_argument("--verbose", action="store_true",
                           help="print every keeper and crash")
            p.add_argument("--jobs", type=int,
                           default=int(os.environ.get(
                               "HP_DE_DUST_JOBS", os.cpu_count() or 1)),
                           help="targets grown at a time, each in its own "
                                "process (HP_DE_DUST_JOBS; the default "
                                "is this box's core count, so a plain grow "
                                "keeps every core busy)")
            p.add_argument("--minutes", type=float, default=0.0,
                           help="keep cycling the targets, --jobs at a "
                                "time, until this many minutes have "
                                "passed; a running grow finishes "
                                "(default 0: one pass over the targets)")
            p.add_argument("--archive", default=os.environ.get(
                               "HP_DE_DUST_ARCHIVE") or None,
                           help="a directory outside the tree that keeps "
                                "every child tried, kept or not, one gzip "
                                "JSON-lines file per grow; the run record "
                                "names it (HP_DE_DUST_ARCHIVE)")
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
