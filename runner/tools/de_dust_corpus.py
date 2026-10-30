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
import atexit
import copy
import base64
import errno
import hashlib
import json
import ntpath
import os
import posixpath
import random
import email.utils
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
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
from runner.ops import exec as EXE  # noqa: E402
from runner.ops import handlers as HA  # noqa: E402
from runner.ops import policy as PO  # noqa: E402
from runner.ops import queries as QU  # noqa: E402
from runner.ops import startup as ST  # noqa: E402
from runner.ops.extensions import build_sensor_alert  # noqa: E402
from runner.wire import jobcrypto as JC  # noqa: E402
from runner.wire import protocol_v2 as P2  # noqa: E402
from runner.wire import transports as TR  # noqa: E402
from runner.wire import subject as SUBJ  # noqa: E402
from runner.wire import verify as V  # noqa: E402
from runner.wire import board as BD  # noqa: E402
from runner.wire import dtlsproto as DT  # noqa: E402
from runner.wire import mailbox as MB  # noqa: E402
import runner.runner as R  # noqa: E402

STAMP = "50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f"
# The corpus lives in the tree; HP_DE_DUST_CORPUS_DIR points the tool
# at another copy (a test's scratch tree, a rig's working copy).
CORPUS_DIR = os.environ.get("HP_DE_DUST_CORPUS_DIR") or os.path.join(
    ROOT, "runner", "tests", "de_dust")
DEFAULT_ROUNDS = 400
MAX_TEXT = 16 * 1024          # bytes of a text entry after mutation
MAX_PAYLOAD = 16 * 1024       # bytes of a payload entry's JSON
MAX_DEPTH = 24                # nesting a payload mutator may add to
SHRINK_BUDGET = 240           # checks a crash's shrink may spend
# de_dust2 (docs/project/de_dust2.md). P3: the parent choice.
ACCEPT_LOW = 0.20             # below this accepted share, boost accepted parents
ACCEPT_BOOST = 4.0            # by this much
# P4: the slow class. A try this many times the corpus replay's
# median, and at least this long, is a finding (Q84's class).
SLOW_FACTOR = 50.0
SLOW_FLOOR_SEC = 0.5
SLOW_PER_GROW = 5             # the slowest tries a grow files
# A slow child discounts its parent for the rest of this grow, so
# one expensive family does not spend the slice that was about to
# file it. The record is still filed. The next grow starts even.
SLOW_PARENT_DISCOUNT = 0.25
# P1/P2: the time slice a cycling grow gives each target, and the
# tilt by yield around it.
DEFAULT_SLICE_SEC = 120
SLICE_MIN_ROUNDS = 400
SLICE_MAX_ROUNDS = 2000000   # tries; the slice's seconds are the real bound
MISS_STREAK = 20000          # rounds in a row with no new child: exhausted
SLICE_FIRST_ROUNDS = 2000     # a target with no rate on record yet
# The campaign's name, as the ledger lines, the bank titles, the slice,
# plan and yield lines and the hourly note say it. The tool, the corpus
# directory, the environment variables and the tests keep their
# de_dust paths across a rename, as they did from de_dust to de_dust2
# (29-OCT) and from de_dust2 to de_aztec (30-OCT).
CAMPAIGN = "de_aztec"

TILT_FLOOR = 0.25             # a target with no yield keeps this much
TILT_MAX = 4.0                # the best target gets at most this much

# Invented secrets for invented fixtures: 64 hex digits each, the
# shape validate_shared_secret accepts. Nothing here is a real key.
SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"
SENSE = "9c4e1b7a2d5f8036b1e4c7a9d2f5083a6c9e1b4d7f0a3c6e9b2d5f8a1c4e7b0d"
OPS = "3b7d1f9a5c2e8046d9a3f1c7b5e2096a8d4c0f6b2e9a7c3d1f5b8e0a6c4d2f91"
WRONG = "0000000000000000000000000000000000000000000000000000000000000001"
# The default key answers to its fingerprint as well as to the empty
# key id (Q94): the name a sender computes from the secret it holds.
# The map is build_secrets' own (Q103 item 7), so a payload named by
# a fingerprint signs under the secret it names, and the keyed
# verifier is expected to choose that name back. Every additional
# key answers to its fingerprint too since Q98 item 15: a body
# naming FP_OPS is the ops key's.
FP = SEC.key_fingerprint(SECRET)
FP_OPS = SEC.key_fingerprint(OPS)
LOCAL_CFG = {
    "shared_secret": SECRET,
    "additional_secrets": {"canary-key": SENSE, "ops": OPS},
    "mailbox_user": "runner@example.com",
    "max_job_age_sec": 3600,
    "sensors": {"canary": {"enabled": True, "key_id": "canary-key"}},
}
SECRETS = V.build_secrets(LOCAL_CFG)
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
        self.hit = set()           # the arcs the last run touched (de_dust2)
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
        arc = (frame.f_code.co_filename, 0, frame.f_lineno)
        self.arcs.add(arc)
        self.hit.add(arc)
        return self._local

    def _local(self, frame, event, arg):
        if event == "line":
            key = id(frame)
            prev = self._last.get(key, 0)
            line = frame.f_lineno
            arc = (frame.f_code.co_filename, prev, line)
            self.arcs.add(arc)
            self.hit.add(arc)
            self._last[key] = line
        elif event == "return":
            self._last.pop(id(frame), None)
        return self._local

    def run(self, fn, *args):
        """fn(*args) under the tracer; afterwards `new` is the count of
        arcs the call added. Whatever fn raises propagates."""
        before = len(self.arcs)
        self.hit = set()
        previous = sys.gettrace()
        sys.settrace(self._global)
        # Threads a check starts (the race targets) are traced too.
        threading.settrace(self._global)
        try:
            return fn(*args)
        finally:
            sys.settrace(previous)
            threading.settrace(None)
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


def _sig_verdict(text, secret):
    """The core's signature and nothing past it: accept, accept-cleaned
    (the control-character retry, Q61), mismatch, or no-sig. Nesting,
    surrogates and the JSON parse are not this answer."""
    import hmac as _hmac
    if not isinstance(text, str) or not isinstance(secret, str):
        return "no-sig"
    try:
        raw, sig = V._extract_signed(V._normalize(text).rstrip())
    except ValueError:
        return "no-sig"
    try:
        raw_b = raw.encode("utf-8")
        key = secret.encode("utf-8")
    except UnicodeEncodeError:
        return "mismatch"
    expect = _hmac.new(key, raw_b, hashlib.sha384).hexdigest()
    if _hmac.compare_digest(expect, sig.lower()):
        return "accept"
    cleaned = V._strip_controls(raw)
    try:
        expect = _hmac.new(key, cleaned.encode("utf-8"),
                           hashlib.sha384).hexdigest()
    except UnicodeEncodeError:
        return "mismatch"
    if _hmac.compare_digest(expect, sig.lower()):
        return "accept-cleaned"
    return "mismatch"


class _Edge:
    """The Worker's signature gate, one node process for the run.
    None when node is not there: the campaign still replays."""

    proc = None
    skip = False
    lock = threading.Lock()
    script = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "cloud/queues-worker/src/edge_stdio.mjs")

    @classmethod
    def verdict(cls, text, secret):
        with cls.lock:
            if cls.skip:
                return None
            if cls.proc is None or cls.proc.poll() is not None:
                try:
                    cls.proc = subprocess.Popen(
                        ["node", cls.script],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
                except OSError:
                    cls.skip = True
                    return None
            try:
                cls.proc.stdin.write(json.dumps(
                    {"text": text, "secret": secret},
                    ensure_ascii=True) + "\n")
                cls.proc.stdin.flush()
                line = cls.proc.stdout.readline()
            except (OSError, UnicodeEncodeError, TypeError, ValueError):
                cls._drop()
                return None
            if not line:
                cls._drop()
                return None
            try:
                why = json.loads(line).get("why")
            except ValueError:
                cls._drop()
                return None
            if why not in ("accept", "no-sig", "mismatch"):
                cls._drop()
                return None
            return why

    @classmethod
    def _drop(cls):
        proc = cls.proc
        cls.proc = None
        if proc is not None and proc.poll() is None:
            proc.kill()


def _queued_body(text):
    """The body the runner's queue channel hands the core for `text`
    sent under a job subject, the frame edge_stdio.mjs puts on it."""
    framed = "[HOMING-PIGEON] job dust\n\n" + (text if isinstance(text, str) else "")
    return framed.replace("\r\n", "\n").partition("\n\n")[2]


def _edge_agrees(text, secret):
    """The edge gate and the core, on the signature alone. The edge
    accepts what the core accepts on the raw bytes, and refuses what
    the core refuses. The core's control-character retry is not the
    edge's job (Q61): both refusing is agreement. A signature the
    edge takes and the core does not is a job queued for a refusal.
    A signature the core takes and the edge does not is a lost job."""
    edge = _Edge.verdict(text, secret)
    if edge is None:
        note("edge", "skipped")
        return
    # Both sides read the body the queue delivers: the runner's
    # channel splits the framed envelope (one CRLF pass) before the
    # core normalizes, exactly as the gate's fetch does.
    py = _sig_verdict(_queued_body(text), secret)
    if edge == "accept" and py == "accept":
        note("edge", "accept")
        return
    if edge != "accept" and py != "accept":
        note("edge", "refuse")
        return
    if edge == "accept":
        raise Crash("agreement", "the edge accepts a signature the "
                    f"core refuses ({py})")
    raise Crash("agreement", "the edge refuses a signature the core "
                f"accepts ({edge})")


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
    body, each to its contract, the two in agreement, the front-end's
    verifier in agreement with them, and the Worker's signature gate
    in agreement with the core on the raw signature (the edge
    differential); a trusted body's reply target is held to provenance."""
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
    _edge_agrees(text, SECRET)
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
    _edge_agrees(body, secret or SECRET)
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
        self.dir = _tmpdir(prefix="hp-de_dust-")
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
        if self.dir in _TMP_MADE:
            _TMP_MADE.remove(self.dir)
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


# One prior neighbor is the store a refusal must leave untouched
# (Q70). Everything older is this grow's own log, and every later
# try reads the file whole. A refused local entry is under a
# millisecond on an empty store and about 18 ms at 5,000 lines, on
# a quiet box; a grow that averaged 113 ms a try was timing the log.
_SENSES_KEEP = 1


def _trim_senses(base, keep=_SENSES_KEEP):
    """Leave the last `keep` lines of the senses store. The rig's
    directory only. A symlink is left alone, and a short file is."""
    path = os.path.join(base, "senses.jsonl")
    if not path or os.path.islink(path):
        return
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return
    lines = data.splitlines(keepends=True)
    if len(lines) <= keep:
        return
    tmp = path + ".trim"
    with open(tmp, "wb") as fh:
        fh.write(b"".join(lines[-keep:]))
    os.replace(tmp, path)


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
    # The neighbor has been checked. The lines before it are this
    # grow's history, and the next try would time them.
    if _RIG is not None:
        _trim_senses(_RIG.dir)
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


_JOB_SUBJECT = SUBJ.JOB_ID_RE  # the one grammar (Q121)
# An id a target puts in a subject must be one token of that grammar:
# the gap class is the Worker's, not Python's isspace (Q121).
_SUBJECT_TOKEN = re.compile(SUBJ.TOKEN_CLASS + "+")
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

    cores = []

    def _feed():
        core = _dtls_core()
        cores.append(core)
        return core.feed(data, _DTLS_ADDR, _DTLS_NOW)

    out, exc = _call(_feed)
    if exc is not None:
        raise Crash("exception", "DtlsServerCore.feed raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if (not isinstance(out, list)
            or not all(isinstance(dg, (bytes, bytearray)) for dg in out)):
        raise Crash("shape", "DtlsServerCore.feed returned "
                    f"{type(out).__name__}")
    # Q110's invariant, on whatever the datagram did: a session the
    # core resumed names an issuing key that still stands in its map.
    for session in cores[0].sessions.values():
        if session.resumed and (session.issuer is None
                                or cores[0].secret_for(session.issuer) is None):
            raise Crash("contract", "a session resumed under a ticket whose "
                        f"issuing key is {session.issuer!r}, not in the map")
    return "accepted" if accepted else "refused"


_DTLS_TICKET_PSK = b"\x5c" * 48
# Three tickets every fresh core holds (de_dust2, P5): one issued
# under the key in the map, one under a key that has left it, and one
# table entry from before tickets recorded their issuer.
_DTLS_TICKETS = {
    b"\x7a" * 24: (_DTLS_TICKET_PSK, _DTLS_NOW + 600, _DTLS_IDENTITY),
    b"\x7b" * 24: (_DTLS_TICKET_PSK, _DTLS_NOW + 600, b"bm-psk-gone"),
    b"\x7c" * 24: (_DTLS_TICKET_PSK, _DTLS_NOW + 600),
}


def _dtls_core():
    """The server core the dtls target feeds: an invented secret map,
    a fixed rng (so a cookie-bearing ClientHello from the seeds is
    valid against every fresh core) and the three planted tickets."""
    core = DT.DtlsServerCore(
        secrets_map={_DTLS_IDENTITY: "bm-secret-0001"},
        rng=lambda n: b"\x5a" * n)
    for ticket, entry in _DTLS_TICKETS.items():
        core.tickets[ticket] = entry
    return core
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
    base = _tmpdir(prefix="hp-de_dust-board-")
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
    base = _tmpdir(prefix="hp-de_dust-chan-")
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
    base = _tmpdir(prefix="hp-de_dust-lin-")
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


# ------------------------------------------------------------------
# keydir: the key directory's three readers (Q114, de_dust2 P5)
# ------------------------------------------------------------------

_KEYDIR_SECRETS = {"": SECRET, "ops": OPS, "canary-key": SENSE}
_KEYDIR_CFG = {"shared_secret": SECRET,
               "additional_secrets": {"ops": OPS, "canary-key": SENSE}}
_KEYDIR_FAR = 4_000_000_000.0     # a bound the clock will not reach soon
_KEYDIR_PAST = 1.0                # a bound long closed
_KEYDIR_JOB = {"job_id": "bm-keydir-0001", "kind": "ping"}


def _keydir_parts(data):
    """(directory, key_id) from an entry: a payload {directory, key_id}
    or anything else as the directory itself with the default key."""
    if isinstance(data, dict) and "directory" in data:
        key_id = data.get("key_id", "")
        return data["directory"], key_id
    return data, ""


def check_keydir(entry):
    """keydir: a key directory as the config would carry it, read by
    load_key_directory, validate_key_directory and key_directory_verdict
    (PROTOCOL.md section 14.4), and the two doors that ask them --
    check_key_policy at the job's door and the DTLS pipe's lookup.
    Contract: the loader and the validator raise RuntimeError naming
    a config error and nothing else; the verdict never raises and
    answers None or a reason; a directory the validator passed gives,
    for every key the runner holds, the same verdict under each of
    the key's names, `compromised` ahead of every bound, `in_use`
    with no bound admitted, a missing entry refused; the job's door
    answers exactly the verdict when no policy stands, and the DTLS
    lookup answers the secret exactly when the verdict admits.
    Accepted when the entry's key is admitted."""
    directory, key_id = _keydir_parts(entry["data"])
    if TU._lone_surrogate(directory) or TU._lone_surrogate(key_id):
        note("gate", "lone surrogate")
        return "refused"
    cfg = dict(_KEYDIR_CFG, key_directory=directory)
    loaded, exc = _call(V.load_key_directory, cfg)
    if exc is not None:
        _expect_refusal(exc, RuntimeError, "load_key_directory")
        if "config error" not in str(exc):
            raise Crash("contract", "load_key_directory refused without "
                        f"naming a config error: {_short(exc)}")
        return "refused"
    if loaded is not directory:
        raise Crash("contract", "load_key_directory did not hand back the "
                    "inline directory")
    valid, exc = _call(V.validate_key_directory, cfg, _KEYDIR_SECRETS)
    valid_ok = exc is None
    if exc is not None:
        _expect_refusal(exc, RuntimeError, "validate_key_directory")
        if "config error" not in str(exc):
            raise Crash("contract", "validate_key_directory refused without "
                        f"naming a config error: {_short(exc)}")
    elif valid is not directory:
        raise Crash("contract", "validate_key_directory did not hand back "
                    "the directory it passed")
    names = list(_KEYDIR_SECRETS) + [V._key_fingerprint(SECRET)]
    if isinstance(key_id, str) and key_id not in names:
        names.append(key_id)
    # The doors read the clock; so does this table, once.
    now = time.time()
    verdicts = {}
    for name in names:
        got, exc = _call(V.key_directory_verdict, directory,
                         _KEYDIR_SECRETS, name, now)
        if exc is not None:
            raise Crash("exception", "key_directory_verdict raised "
                        f"{type(exc).__name__} for {name!r}: {_short(exc)}")
        if got is not None and not isinstance(got, str):
            raise Crash("shape", f"key_directory_verdict answered {got!r}"[:200])
        verdicts[name] = got
        note("verdict", name, got)
    # The default key under its two names: one key, one verdict.
    fp = V._key_fingerprint(SECRET)
    if verdicts[""] != verdicts[fp]:
        raise Crash("contract", "the default key's verdict differs under "
                    f"its fingerprint: {verdicts['']!r} vs {verdicts[fp]!r}")
    if valid_ok and isinstance(directory, dict):
        for name in _KEYDIR_SECRETS:
            entry_names = V.key_names(_KEYDIR_SECRETS, name)
            found = next((directory[n] for n in entry_names if n in directory),
                         None)
            v = verdicts[name]
            if found is None:
                if v is None or "no key directory entry" not in v:
                    raise Crash("contract", f"{name!r} has no entry and the "
                                f"verdict is {v!r}")
                continue
            state = found.get("state")
            if state == "compromised" and v != "key is compromised":
                raise Crash("contract", f"{name!r} is compromised and the "
                            f"verdict is {v!r}")
            if (state == "in_use" and found.get("not_before") is None
                    and found.get("not_after") is None
                    and found.get("fingerprint") is None and v is not None):
                raise Crash("contract", f"{name!r} is in_use with no bound "
                            f"and the verdict is {v!r}")
            if state in ("ordered", "generated", "distributed", "destroyed") \
                    and v is None:
                raise Crash("contract", f"{name!r} is {state} and admitted")
    # The job's door answers the verdict (no policy stands here): the
    # whole-directory check is the startup gate, the doors read each
    # key's own entry, so a live edit that breaks one entry locks out
    # that key and no other.
    for name in _KEYDIR_SECRETS:
        door, exc = _call(V.check_key_policy, {}, name, cfg, _KEYDIR_JOB,
                          _KEYDIR_SECRETS)
        if exc is not None:
            raise Crash("exception", "check_key_policy raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        want = verdicts[name]
        if door != want:
            raise Crash("contract", f"the job's door said {door!r} for "
                        f"{name!r}; the verdict is {want!r}")
    # The DTLS lookup answers the secret exactly when the verdict admits.
    look = _dtls_pipe().directory_lookup(
        cfg, DT.make_secret_lookup(SECRET, _KEYDIR_CFG["additional_secrets"]),
        now=lambda: now)
    for name in _KEYDIR_SECRETS:
        got, exc = _call(look, DT.identity_for(name))
        if exc is not None:
            raise Crash("exception", "the DTLS lookup raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        admits = verdicts[name] is None
        if admits and got != _KEYDIR_SECRETS[name]:
            raise Crash("contract", f"the DTLS lookup refused {name!r}, which "
                        "the verdict admits")
        if not admits and got is not None:
            raise Crash("contract", f"the DTLS lookup answered {name!r}, "
                        "which the verdict refuses")
    note("valid", valid_ok)
    asked = key_id if isinstance(key_id, str) else ""
    return "accepted" if verdicts.get(asked) is None else "refused"


def _dtls_pipe():
    """The DTLS transport's module, loaded once (it lives beside the
    extension, not in runner/wire)."""
    global _DTLS_PIPE
    if _DTLS_PIPE is None:
        import importlib
        _DTLS_PIPE = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
    return _DTLS_PIPE


_DTLS_PIPE = None


# ------------------------------------------------------------------
# address: the reply_to reader and the header it becomes (Q113)
# ------------------------------------------------------------------

class _CatchSmtp:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


_ADDRESS_CFG = {"mailbox_user": "runner@example.com"}
_ADDRESS_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def check_address(entry):
    """address: a job's reply_to through _valid_reply_to and, when it
    is honored, through send_mail into a To header (Q113: a mutated
    address once rendered as `<>`). Contract: _valid_reply_to never
    raises and answers None or the stripped text; an honored address
    is at most 254 characters, carries no control character, and
    the message send_mail builds carries it as its To header, which
    parses back to that one address and nothing else; a job that is
    not an object, or a reply_to that is not text, is None. Accepted
    when the address is honored."""
    data = entry["data"]
    job = data if isinstance(data, dict) else {"reply_to": data}
    if TU._lone_surrogate(job):
        note("gate", "lone surrogate")
        return "refused"
    got, exc = _call(MB._valid_reply_to, job)
    if exc is not None:
        raise Crash("exception", "_valid_reply_to raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    rt = job.get("reply_to") if isinstance(job, dict) else None
    if got is None:
        if isinstance(rt, str):
            note("refused", "text", len(rt))
        else:
            note("refused", "not text")
        return "refused"
    if not isinstance(got, str):
        raise Crash("shape", f"_valid_reply_to answered {type(got).__name__}")
    if not isinstance(rt, str):
        raise Crash("contract", "an address was honored from a reply_to "
                    "that is not text")
    if got != rt.strip():
        raise Crash("contract", "the honored address is not the stripped "
                    "reply_to")
    if len(got) > 254 or _ADDRESS_CTRL.search(got) or "@" not in got:
        raise Crash("contract", f"the honored address breaks the rules: "
                    f"{got[:60]!r}")
    smtp = _CatchSmtp()
    _, exc = _call(MB.send_mail, smtp, _ADDRESS_CFG, "[HOMING-PIGEON] result "
                   "bm-addr-0001", "ok\n", got)
    if exc is not None:
        raise Crash("exception", f"send_mail raised {type(exc).__name__}: "
                    f"{_short(exc)}")
    if len(smtp.sent) != 1:
        raise Crash("contract", "send_mail built no message for an honored "
                    "address")
    header = str(smtp.sent[0]["To"] or "")
    name, addr = email.utils.parseaddr(header)
    if addr != got or name:
        raise Crash("provenance", "the result is addressed to "
                    f"{header[:60]!r}, not the honored {got[:60]!r}")
    raw, exc = _call(smtp.sent[0].as_bytes)
    if exc is not None:
        raise Crash("exception", "the result message would not serialize: "
                    f"{_short(exc)}")
    note("to", header)
    return "accepted"


# ------------------------------------------------------------------
# dtls_session: stateful, in-memory protocol fuzzing (de_dust2)
# ------------------------------------------------------------------
#
# The dtls target feeds one datagram to a fresh core. This one runs
# a whole conversation in memory: up to two clients and one server,
# a script of steps that deliver, drop, duplicate, flip, cut and
# reorder the datagrams in flight, advance the clock, rebind an
# address, rotate a key, resume a ticket. No sockets, no threads, a
# fixed rng on every core, so a script replays the same way every
# time and a keeper is a keeper everywhere. The invariants hold on
# whatever a script does, which is what makes mutated scripts a
# fuzz and not a test: no core raises past its contract, nothing
# establishes under a key the server does not hold, a resumed
# session names a key still in the map, the server only holds a
# session established after its client sent Finished, and after
# the give-up and the ticket lifetime nothing half-open is left.

_SESSION_SECRETS = {"": "bm-secret-0001", "old": "bm-secret-old"}
_SESSION_WRONG = "bm-secret-wrong"
_SESSION_MAX_STEPS = 64
_SESSION_MAX_CLIENTS = 2
_SESSION_MAX_DELIVER = 16
_SESSION_MAX_DUP = 4
_SESSION_ADDRS = (("192.0.2.10", 40001), ("192.0.2.11", 40002))
_SESSION_RNGS = (b"\x33", b"\x44")
_SESSION_TICKETS = {
    "live": (b"\x7a" * 24, _DTLS_TICKET_PSK),
    "gone": (b"\x7b" * 24, _DTLS_TICKET_PSK),
    "unrecorded": (b"\x7c" * 24, _DTLS_TICKET_PSK),
}


def _session_server(secrets):
    table = {DT.identity_for(k): v for k, v in secrets.items()}
    server = DT.DtlsServerCore(secrets_map=table, rng=lambda n: b"\x5a" * n,
                               greeting_for=lambda s: b'{"type":"greeting","v":1}')
    server.tickets[b"\x7a" * 24] = (_DTLS_TICKET_PSK, _DTLS_NOW + 600,
                                   DT.identity_for(""))
    server.tickets[b"\x7b" * 24] = (_DTLS_TICKET_PSK, _DTLS_NOW + 600, b"bm-psk-gone")
    server.tickets[b"\x7c" * 24] = (_DTLS_TICKET_PSK, _DTLS_NOW + 600)
    return server


class _SessionRun:
    """One script, interpreted step by step."""

    def __init__(self, script):
        self.script = script
        self.secrets = dict(_SESSION_SECRETS)
        self.server = _session_server(self.secrets)
        self.clients = {}           # index -> dict(core, addr, key, ticket)
        self.c2s = []               # [(index, datagram)]
        self.s2c = []               # [(index, datagram)]
        self.now = _DTLS_NOW
        self.seen_events = 0
        self.established = set()    # client indexes that established
        self.begun = {}             # server cid -> (client index, key stood)
        self.replaced = set()       # server cids whose client was restarted
        self.steps = 0

    # -- helpers ---------------------------------------------------------

    def _client_at(self, addr):
        for i, c in self.clients.items():
            if addr in c["addrs"]:
                return i, c
        return None, None

    def _note_sessions(self):
        """A session the server began since the last look is tied to
        its client, with whether the client's key stood at that
        moment: that is when the server verified the binder, and what
        the established event is judged against."""
        for cid, sess in self.server.sessions.items():
            if cid in self.begun:
                continue
            i, c = self._client_at(sess.peer_addr)
            self.begun[cid] = (i, None if c is None else self._key_stands(c))

    def _key_stands(self, c):
        """Does the server hold the key this client signs with, now?"""
        key = c["key"]
        if key == "ticket":
            return c.get("ticket_ok", False)
        if key == "wrong":
            return False
        return key in self.secrets

    def _server(self, fn, *args):
        got, exc = _call(fn, *args)
        if exc is not None:
            raise Crash("exception", f"the server's {fn.__name__} raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        return got

    def _client(self, core, fn, *args):
        got, exc = _call(fn, *args)
        if exc is not None:
            if isinstance(exc, DT.DtlsError):
                note("client", "DtlsError", str(exc)[:60])
                return []
            raise Crash("exception", f"the client's {fn.__name__} raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        return got

    def _check_events(self):
        for ev in self.server.events[self.seen_events:]:
            if not isinstance(ev, tuple) or not ev:
                raise Crash("shape", "a server event is not a tuple")
            if ev[0] == "established":
                if ev[1] in self.replaced:
                    continue
                info = ev[2] if len(ev) > 2 and isinstance(ev[2], dict) else {}
                i, c = self._client_at(info.get("addr"))
                if c is None:
                    raise Crash("auth", "the server established a session "
                                "for an address no client holds")
                begun_i, stood = self.begun.get(ev[1], (i, None))
                if stood is None:
                    stood = self._key_stands(c)
                if not stood:
                    raise Crash("auth", f"the server established client {i} "
                                f"under a key it did not hold when the "
                                f"session began ({c['key']})")
                if not c["core"].finished_sent:
                    raise Crash("contract", f"the server established client {i} "
                                "before the client sent Finished")
                if info.get("resumed"):
                    sess = self.server.sessions.get(ev[1])
                    if sess is not None and (sess.issuer is None or
                                             self.server.secret_for(sess.issuer) is None):
                        raise Crash("contract", "a session resumed under a "
                                    "ticket whose issuing key is not in the map")
                note("established", i, bool(info.get("resumed")))
            elif ev[0] == "app":
                # The runner answers a job on its session; the script's
                # peer gets a result back.
                self.s2c.extend(self._deliverables(
                    self._server(self.server.send_app, ev[1], b"result\n")))
        self.seen_events = len(self.server.events)

    def _deliverables(self, pairs):
        out = []
        if not isinstance(pairs, list):
            raise Crash("shape", "the server returned no list of datagrams")
        for item in pairs:
            if not (isinstance(item, tuple) and len(item) == 2):
                raise Crash("shape", "a server datagram is not (addr, bytes)")
            addr, dg = item
            if not isinstance(dg, (bytes, bytearray)):
                raise Crash("shape", "a server datagram is not bytes")
            i, _c = self._client_at(addr)
            if i is not None:
                out.append((i, bytes(dg)))
        return out

    # -- steps -----------------------------------------------------------

    def op_start(self, step):
        i = self._index(step)
        if i is None:
            return
        key = step.get("key", "")
        if not isinstance(key, str):
            return
        ticket = None
        ticket_ok = False
        if isinstance(step.get("ticket"), str):
            name = step["ticket"]
            if name in _SESSION_TICKETS:
                ticket = _SESSION_TICKETS[name]
                ticket_ok = name == "live"
            elif name.startswith("own:"):
                src = self.clients.get(int(name[4:]) if name[4:].isdigit() else -1)
                if src is not None and src is self.clients.get(i):
                    return
                if src is None or src["core"].ticket is None:
                    return
                ticket = src["core"].ticket
                ticket_ok = self._key_stands(src)
            else:
                return
            secret = _SESSION_SECRETS[""]
            key = "ticket"
        elif key == "wrong":
            secret = _SESSION_WRONG
        elif key in _SESSION_SECRETS:
            secret = _SESSION_SECRETS[key]
        else:
            return
        rng_byte = _SESSION_RNGS[i]
        core = DT.DtlsClientCore(secret, key_id=(key if key not in ("", "wrong", "ticket") else None),
                                 ticket=ticket, rng=lambda n, b=rng_byte: b * n)
        if key == "wrong":
            core._identity = DT.identity_for("")
        if i in self.clients:
            # A restart replaces the client at that index. What the
            # old one left in flight is not the new one's, and a
            # session the server already holds for the address was
            # that client's: its events are not judged against the
            # new core (de_dust2: the "established before Finished"
            # echo was the old session's retransmitted Finished).
            self.c2s = [(j, dg) for j, dg in self.c2s if j != i]
            self.s2c = [(j, dg) for j, dg in self.s2c if j != i]
            self._check_events()
            for cid, sess in self.server.sessions.items():
                if self._client_at(sess.peer_addr)[0] == i:
                    self.begun[cid] = (i, None)
                    self.replaced.add(cid)
        self.clients[i] = {"core": core, "addr": _SESSION_ADDRS[i], "key": key,
                           "ticket_ok": ticket_ok, "addrs": {_SESSION_ADDRS[i]}}
        out = self._client(core, core.start, self.now)
        self.c2s.extend((i, bytes(dg)) for dg in out)

    def op_deliver(self, step):
        direction = step.get("dir")
        queue = self.s2c if isinstance(direction, str) and direction == "s2c" else self.c2s
        n = step.get("n", _SESSION_MAX_DELIVER)
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            n = _SESSION_MAX_DELIVER
        n = min(n, _SESSION_MAX_DELIVER, len(queue))
        batch = queue[:n]
        del queue[:n]
        if step.get("reverse"):
            batch.reverse()
        if step.get("drop"):
            note("deliver", "dropped", len(batch))
            return
        dup = step.get("dup", 1)
        if not isinstance(dup, int) or isinstance(dup, bool) or dup < 1:
            dup = 1
        dup = min(dup, _SESSION_MAX_DUP)
        flips = step.get("flip")
        cut = step.get("cut")
        for i, dg in batch:
            dg = bytearray(dg)
            if isinstance(flips, list):
                for off in flips[:8]:
                    if isinstance(off, int) and not isinstance(off, bool) and dg:
                        dg[off % len(dg)] ^= 0x01
            if isinstance(cut, int) and not isinstance(cut, bool) and cut >= 0:
                dg = dg[:cut]
            dg = bytes(dg)
            for _ in range(dup):
                self._feed(queue is self.c2s, i, dg)

    def _feed(self, to_server, i, dg):
        c = self.clients.get(i)
        if c is None:
            return
        if to_server:
            out = self._server(self.server.feed, dg, c["addr"], self.now)
            if not isinstance(out, list) or not all(
                    isinstance(x, (bytes, bytearray)) for x in out):
                raise Crash("shape", "the server's feed returned no list of bytes")
            self._note_sessions()
            self.s2c.extend((i, bytes(x)) for x in out)
        else:
            out = self._client(c["core"], c["core"].feed, dg, self.now)
            if not isinstance(out, list):
                raise Crash("shape", "the client's feed returned no list")
            self.c2s.extend((i, bytes(x)) for x in out)
        self._check_events()

    def op_tick(self, step):
        dt = step.get("dt", 1.0)
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or dt != dt or dt < 0:
            dt = 1.0
        self.now += min(float(dt), 86400.0)
        self.s2c.extend(self._deliverables(self._server(self.server.tick, self.now)))
        for i, c in self.clients.items():
            out = self._client(c["core"], c["core"].tick, self.now)
            self.c2s.extend((i, bytes(x)) for x in out)
        self._check_events()

    @staticmethod
    def _index(step):
        i = step.get("c", 0)
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < _SESSION_MAX_CLIENTS:
            return None
        return i

    def op_app(self, step):
        i = self._index(step)
        c = self.clients.get(i)
        if c is None:
            return
        text = step.get("data", "[HOMING-PIGEON] job bm-s-0001\n\n{}\n")
        data = (text if isinstance(text, str) else json.dumps(text, default=str))[:4096]
        out = self._client(c["core"], c["core"].send_app, data.encode("utf-8"))
        self.c2s.extend((i, bytes(x)) for x in out)

    def op_rebind(self, step):
        i = self._index(step)
        c = self.clients.get(i)
        if c is None:
            return
        host, port = c["addr"]
        c["addr"] = (host, port + 1000)
        c["addrs"].add(c["addr"])
        note("rebind", i)

    def op_rotate(self, step):
        self.secrets.pop("old", None)
        self.server._secret_lookup = DT.make_secret_lookup(
            self.secrets[""], {k: v for k, v in self.secrets.items() if k})
        note("rotate")

    OPS = {"start": op_start, "deliver": op_deliver, "tick": op_tick,
           "app": op_app, "rebind": op_rebind, "rotate": op_rotate}

    # -- the run ---------------------------------------------------------

    def run(self):
        steps = self.script if isinstance(self.script, list) else [self.script]
        for step in steps[:_SESSION_MAX_STEPS]:
            if not isinstance(step, dict) or not isinstance(step.get("op"), str):
                continue
            fn = self.OPS.get(step["op"])
            if fn is None:
                continue
            self.steps += 1
            fn(self, step)
            for i, c in self.clients.items():
                if c["core"].state == "established":
                    self.established.add(i)
                if c["core"].app_messages and not c["core"].finished_sent:
                    raise Crash("leak", f"client {i} holds application data "
                                "before its Finished went out")
        self._check_events()
        # Housekeeping: after the give-up and the ticket lifetime,
        # nothing half-open and nothing expired is left.
        later = self.now + DT.RETRANSMIT_GIVE_UP + DT.TICKET_LIFETIME + 5
        self._deliverables(self._server(self.server.tick, later))
        for cid, sess in self.server.sessions.items():
            if not sess.established:
                raise Crash("resource", "a half-open session outlived the "
                            "retransmit give-up")
        for ticket, entry in self.server.tickets.items():
            if later > DT.ticket_fields(entry)[1]:
                raise Crash("resource", "an expired ticket outlived housekeeping")
        for addr, sess in self.server.by_addr.items():
            if sess.dead:
                raise Crash("resource", "a dead session is still mapped by address")
        note("steps", self.steps, "established", len(self.established))
        return "accepted" if self.established else "refused"


def check_dtls_session(entry):
    """dtls_session: a script of steps over up to two clients and one
    server, in memory (see the section note above). Contract: no core
    raises past its contract (a client's DtlsError is a refusal); the
    server's feed and tick return lists in their shapes; the server
    establishes a session only for a client whose key it holds at
    that moment, only after that client sent Finished, and a resumed
    one only under a ticket whose issuing key is still in the map; a
    client holds no application data before its Finished; and after
    the give-up and the ticket lifetime no half-open session, no
    expired ticket and no dead address mapping remains. Accepted when
    a client established."""
    data = entry["data"]
    if TU._lone_surrogate(data):
        note("gate", "lone surrogate")
        return "refused"
    return _SessionRun(data).run()


def seeds_dtls_session():
    D = lambda **kw: dict(op="deliver", **kw)  # noqa: E731
    handshake = [dict(op="start", c=0), D(), D(dir="s2c"), D(), D(dir="s2c")]
    scripts = [
        ("handshake", handshake),
        ("handshake_and_job", handshake + [dict(op="app", c=0), D(), D(dir="s2c")]),
        ("two_clients_interleaved", [dict(op="start", c=0), dict(op="start", c=1, key="old"),
                                     D(n=1), D(n=1), D(dir="s2c", n=1), D(dir="s2c", n=1),
                                     D(), D(dir="s2c"), D(), D(dir="s2c")]),
        ("resume_own", handshake + [dict(op="start", c=1, ticket="own:0"),
                                    D(), D(dir="s2c"), D(), D(dir="s2c")]),
        ("resume_live_ticket", [dict(op="start", c=0, ticket="live"), D(), D(dir="s2c"),
                                D(), D(dir="s2c")]),
        ("resume_gone_ticket", [dict(op="start", c=0, ticket="gone"), D(), D(dir="s2c"),
                                D(), D(dir="s2c")]),
        ("resume_unrecorded_ticket", [dict(op="start", c=0, ticket="unrecorded"), D(),
                                      D(dir="s2c"), D(), D(dir="s2c")]),
        ("rotate_then_resume_old", [dict(op="start", c=0, key="old"), D(), D(dir="s2c"),
                                    D(), D(dir="s2c"), dict(op="rotate"),
                                    dict(op="start", c=1, ticket="own:0"), D(),
                                    D(dir="s2c"), D(), D(dir="s2c")]),
        ("wrong_key", [dict(op="start", c=0, key="wrong"), D(), D(dir="s2c"), D(),
                       D(dir="s2c")]),
        ("hrr_lost_then_retransmit", [dict(op="start", c=0), D(), D(dir="s2c", drop=True),
                                      dict(op="tick", dt=1.5), D(), D(dir="s2c"), D(),
                                      D(dir="s2c")]),
        ("server_flight_duplicated", [dict(op="start", c=0), D(), D(dir="s2c"), D(),
                                      D(dir="s2c", dup=3), D(), D(dir="s2c")]),
        ("client_hello_flipped", [dict(op="start", c=0), D(flip=[5, 20, 33]), D(dir="s2c"),
                                  D(), D(dir="s2c")]),
        ("finished_cut", [dict(op="start", c=0), D(), D(dir="s2c"), D(cut=40), D(dir="s2c"),
                          dict(op="tick", dt=2.0), D(), D(dir="s2c")]),
        ("reversed_flight", [dict(op="start", c=0), D(), D(dir="s2c", reverse=True), D(),
                             D(dir="s2c")]),
        ("rebind_mid_session", handshake + [dict(op="rebind", c=0), dict(op="app", c=0),
                                            D(), D(dir="s2c")]),
        ("give_up", [dict(op="start", c=0), D(), dict(op="tick", dt=61.0), D(), D(dir="s2c")]),
        ("ticks_only", [dict(op="start", c=0), dict(op="tick", dt=1.0), dict(op="tick", dt=2.0),
                        dict(op="tick", dt=4.0), D(), D(dir="s2c"), D(), D(dir="s2c")]),
        ("app_before_handshake", [dict(op="start", c=0), dict(op="app", c=0, data="early"),
                                  D(), D(dir="s2c")]),
        ("empty", []),
        ("not_a_list", {"op": "start"}),
        ("junk_steps", [7, "start", None, {"op": "nope"}, {"op": "deliver", "n": -1}]),
    ]
    return [make_entry("payload", script, "seed:" + name, "seed")
            for name, script in scripts]


# ------------------------------------------------------------------
# race_board: threads interleaved over one board (de_dust2)
# ------------------------------------------------------------------
#
# The board's peers arrive one at a time through the mail core, but
# the runner's workers finish jobs from a pool, the hosted queue's
# results land whenever they land, and BOARD_LOCK is what keeps the
# board one board. This target runs the board's operations from
# several threads at once, with the interpreter's switch interval
# forced small so the threads interleave inside every call, and
# holds the lease rules on whatever order the box produced: a task
# is held by one worker at a time, finished once, never handed to a
# second worker while its holder's lease stands, and the file on
# disk is the board in memory when the threads are done.

_RACE_MAX_THREADS = 4
_RACE_MAX_OPS = 32
_RACE_TASKS = ("bm-race-0001", "bm-race-0002", "bm-race-0003")
_RACE_WORKERS = ("worker-a", "worker-b", "worker-c", "worker-d")
_RACE_CFG = {"worker_allowlist": list(_RACE_WORKERS)}


def _race_ops(spec):
    """The per-thread op lists a spec names, bounded and typed."""
    threads = spec.get("threads") if isinstance(spec, dict) else None
    if not isinstance(threads, list):
        return []
    out = []
    for ops in threads[:_RACE_MAX_THREADS]:
        if not isinstance(ops, list):
            continue
        clean = []
        for op in ops[:_RACE_MAX_OPS]:
            if isinstance(op, dict) and isinstance(op.get("op"), str):
                clean.append(op)
        out.append(clean)
    return out


def check_race_board(entry):
    """race_board: up to four threads, each a list of board operations
    (submit, offer, complete, approve, reoffer) over one Board on a
    throwaway path, interleaved under a short switch interval.
    Contract: no thread raises; a fault is one claimed_at handed to
    two workers (one lease, dealt twice). A timeout of 0 ends the
    lease at once, and the next offer is a new lease. A task
    completes as done or pending_review exactly once, by a key the
    board still names; approve moves only a pending_review task; the
    board reloaded from its file after the threads join equals the
    board in memory; and the counts add up to the tasks on the
    board. Accepted when some task was done."""
    spec = entry["data"]
    if TU._lone_surrogate(spec):
        note("gate", "lone surrogate")
        return "refused"
    lanes = _race_ops(spec)
    if not lanes:
        return "refused"
    switch = spec.get("switch", 1e-5) if isinstance(spec, dict) else 1e-5
    if isinstance(switch, bool) or not isinstance(switch, (int, float)) \
            or switch != switch or not 1e-6 <= switch <= 1e-2:
        switch = 1e-5
    base = _tmpdir(prefix="hp-de_dust-race-")
    path = os.path.join(base, "board.json")
    board = BD.Board(path)
    log = []                  # (thread, op, task, result) in completion order
    log_lock = threading.Lock()
    errors = []
    holders = {}              # task_id -> (worker, claimed_at)
    holders_lock = threading.Lock()
    faults = []

    def record(t, op, task, result):
        with log_lock:
            log.append((t, op, task, result))

    def run_lane(t, ops):
        try:
            for op in ops:
                name = op["op"]
                task = op.get("task")
                task = task if isinstance(task, str) else _RACE_TASKS[0]
                worker = op.get("worker")
                worker = worker if isinstance(worker, str) else _RACE_WORKERS[t % len(_RACE_WORKERS)]
                if name == "submit":
                    ok, why = board.submit(_task(task, priority=op.get("priority", 1)))
                    record(t, name, task, "ok" if ok else why)
                elif name == "offer":
                    caps = op.get("capabilities", ["shell"])
                    # The worker's name is also its key id: the board
                    # binds a claim to the key it was offered under, and
                    # a completion by another key is refused.
                    got = board.offer(worker, caps, worker, _RACE_CFG)
                    tid = got.get("task_id") if isinstance(got, dict) else None
                    if isinstance(got, dict) and isinstance(tid, str):
                        claim_at = got.get("claimed_at")
                        with holders_lock:
                            other = holders.get(tid)
                            # One lease is one claimed_at. A timeout of
                            # 0 ends it at once, and the next offer is
                            # a new lease. The fault is the same instant
                            # handed to two workers, not a holder the
                            # checker recorded after the board had
                            # already reoffered.
                            if (other is not None and other[0] != worker
                                    and other[1] == claim_at
                                    and claim_at is not None):
                                faults.append(
                                    f"{tid} offered to {worker} while "
                                    f"{other[0]} held it")
                            if got.get("claimed_by") == worker:
                                holders[tid] = (worker, claim_at)
                    record(t, name, tid, worker)
                elif name == "complete":
                    status, why = board.complete(task, {"ok": True},
                                                 require_review=bool(op.get("review")),
                                                 holder=worker)
                    if status in ("done", "pending_review"):
                        with holders_lock:
                            held = holders.get(task)
                            holders.pop(task, None)
                        # The board accepted this key. A map entry
                        # from a lease a timeout-0 reoffer already
                        # ended is not a second holder.
                        if held is not None and held[0] != worker:
                            task_rec = board.tasks.get(task)
                            claimed = (task_rec.get("claimed_by")
                                       if isinstance(task_rec, dict) else None)
                            if claimed == held[0]:
                                faults.append(
                                    f"{task} completed by {worker}, "
                                    f"held by {held[0]}")
                    record(t, name, task, status)
                elif name == "approve":
                    ok, why = board.approve(task)
                    record(t, name, task, "ok" if ok else why)
                elif name == "reoffer":
                    timeout = op.get("timeout", 0)
                    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
                        timeout = 0
                    n = board.reoffer_expired(task_timeout=timeout)
                    if n:
                        with holders_lock:
                            # The lease is the board's to end; the
                            # holders it ended are free again.
                            for tid, tk in list(board.tasks.items()):
                                if isinstance(tk, dict) and tk.get("state") == "open":
                                    holders.pop(tid, None)
                    record(t, name, None, n)
                elif name == "yield":
                    time.sleep(0)
                time.sleep(0)
        except Exception as e:  # the contract: nothing raises
            errors.append(f"thread {t}: {type(e).__name__}: {_short(e)}")

    previous = sys.getswitchinterval()
    sys.setswitchinterval(float(switch))
    try:
        workers = [threading.Thread(target=run_lane, args=(t, ops), daemon=True)
                   for t, ops in enumerate(lanes)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=30)
        if any(w.is_alive() for w in workers):
            raise Crash("resource", "a board thread did not finish in 30 s")
    finally:
        sys.setswitchinterval(previous)
    try:
        if errors:
            raise Crash("exception", errors[0])
        if faults:
            raise Crash("contract", faults[0])
        # One completion per task.
        finished = {}
        for t, op, task, result in log:
            if op == "complete" and result in ("done", "pending_review"):
                finished[task] = finished.get(task, 0) + 1
        for task, n in finished.items():
            if n > 1:
                raise Crash("contract", f"{task} was completed {n} times")
        # The file is the board.
        again = BD.Board(path)
        if again.tasks != board.tasks:
            raise Crash("contract", "the board file does not read back as the "
                        "board in memory after the threads joined")
        counts = board.counts() if hasattr(board, "counts") else None
        if isinstance(counts, dict) and sum(v for v in counts.values()
                                            if isinstance(v, int)) != len(board.tasks):
            raise Crash("contract", "the counts do not add up to the tasks")
        note("race", len(lanes), "ops", sum(len(l) for l in lanes), "done",
             sum(1 for t in board.tasks.values()
                 if isinstance(t, dict) and t.get("state") == "done"))
        return "accepted" if any(isinstance(t, dict) and t.get("state") == "done"
                                 for t in board.tasks.values()) else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def seeds_race_board():
    S = lambda task, **kw: dict(op="submit", task=task, **kw)  # noqa: E731
    O = lambda worker, **kw: dict(op="offer", worker=worker, **kw)  # noqa: E731
    C = lambda task, worker, **kw: dict(op="complete", task=task, worker=worker, **kw)  # noqa: E731
    A = lambda task: dict(op="approve", task=task)  # noqa: E731
    R = lambda **kw: dict(op="reoffer", **kw)  # noqa: E731
    Y = {"op": "yield"}
    t1, t2, t3 = _RACE_TASKS
    specs = [
        ("one_task_two_workers", {"threads": [
            [S(t1), O("worker-a"), C(t1, "worker-a")],
            [Y, O("worker-b"), C(t1, "worker-b")]]}),
        ("three_tasks_three_workers", {"threads": [
            [S(t1), S(t2), S(t3), O("worker-a"), C(t1, "worker-a")],
            [Y, O("worker-b"), Y, C(t2, "worker-b"), O("worker-b")],
            [Y, Y, O("worker-c"), C(t3, "worker-c"), O("worker-c")]]}),
        ("reoffer_races_the_holder", {"threads": [
            [S(t1), O("worker-a"), Y, Y, C(t1, "worker-a")],
            [Y, R(timeout=0), O("worker-b"), C(t1, "worker-b")]]}),
        ("review_then_approve", {"threads": [
            [S(t1), O("worker-a"), C(t1, "worker-a", review=True)],
            [Y, Y, A(t1), A(t1)]]}),
        ("submit_twice", {"threads": [[S(t1), S(t1)], [S(t1), O("worker-b")]]}),
        ("complete_what_you_do_not_hold", {"threads": [
            [S(t1), O("worker-a")],
            [Y, C(t1, "worker-b"), C(t1, "worker-b")]]}),
        ("four_lanes_fast_switch", {"switch": 1e-6, "threads": [
            [S(t1), O("worker-a"), C(t1, "worker-a"), S(t2)],
            [O("worker-b"), C(t2, "worker-b"), O("worker-b")],
            [R(timeout=0), O("worker-c"), C(t1, "worker-c")],
            [S(t3), O("worker-d"), C(t3, "worker-d"), A(t3)]]}),
        ("priorities", {"threads": [
            [S(t1, priority=1), S(t2, priority=9), O("worker-a"), O("worker-a")],
            [S(t3, priority=5), O("worker-b"), C(t2, "worker-b"), C(t3, "worker-b")]]}),
        ("unknown_ops", {"threads": [[{"op": "nope"}, 7, "offer", S(t1)], "not a lane"]}),
        ("empty", {"threads": []}),
        ("not_an_object", ["submit"]),
    ]
    return [make_entry("payload", spec, "seed:" + name, "seed") for name, spec in specs]


# ------------------------------------------------------------------
# race_stash: threads over one outbox (de_dust2)
# ------------------------------------------------------------------
#
# The worker pool stashes a finished result and delivers it while a
# resend pass walks the same outbox. The record for one skey is one
# file. This target runs those operations from several threads and
# holds the file rules on whatever order the box produced: a body
# that was sent is a body that was stashed, and one skey is not
# delivered twice without an undeliver between the two. A second
# stash after a delivery leaves the sent copy where it is and a
# new record in the outbox; that is the next result, not two
# copies of one.

_STASH_KEYS = ("bm-stash-0001", "bm-stash-0002")


def check_race_stash(entry):
    """race_stash: up to four threads, each a list of outbox
    operations (stash, deliver, fail, undeliver, resend) over one
    base directory, interleaved under a short switch interval.
    Contract: no thread raises; every body a sender was handed was
    stashed for that key; the same key is not delivered twice with
    no undeliver between; every record left behind reads back.
    Accepted when some body was delivered."""
    spec = entry["data"]
    if TU._lone_surrogate(spec):
        note("gate", "lone surrogate")
        return "refused"
    lanes = _race_ops(spec)
    if not lanes:
        return "refused"
    switch = spec.get("switch", 1e-5) if isinstance(spec, dict) else 1e-5
    if isinstance(switch, bool) or not isinstance(switch, (int, float)) \
            or switch != switch or not 1e-6 <= switch <= 1e-2:
        switch = 1e-5
    base = _tmpdir(prefix="hp-de_dust-stash-")
    events = []
    lock = threading.Lock()
    errors = []

    def run_lane(t, ops):
        try:
            for op in ops:
                name = op["op"]
                skey = op.get("skey")
                if not isinstance(skey, str) or not skey:
                    skey = _STASH_KEYS[t % len(_STASH_KEYS)]
                if name == "stash":
                    body = op.get("body")
                    if not isinstance(body, str):
                        body = "body-" + skey
                    subject = op.get("subject")
                    if not isinstance(subject, str):
                        subject = "[HOMING-PIGEON] result " + skey
                    with lock:
                        events.append(("stash", skey, body))
                    R.stash_result(base, skey, {"job_id": skey, "kind": "exec"},
                                   subject, body)
                elif name == "deliver":
                    sent = []

                    def sender(subject, body, to, sent=sent):
                        sent.append(body)

                    ok = R.deliver_stash(base, skey, sender, cfg={})
                    with lock:
                        if sent:
                            events.append(("deliver", skey, sent[0], bool(ok)))
                elif name == "fail":
                    def bad(subject, body, to):
                        raise RuntimeError("down")

                    R.deliver_stash(base, skey, bad, cfg={})
                    with lock:
                        events.append(("fail", skey))
                elif name == "undeliver":
                    R.undeliver_stash(base, skey, "channel write failed")
                    with lock:
                        events.append(("undeliver", skey))
                elif name == "resend":
                    sent_bodies = []

                    def resender(subject, body, to, box=sent_bodies):
                        box.append(body)

                    R.resend_stashed(base, {}, resender, now=time.time() + 120)
                    with lock:
                        for body in sent_bodies:
                            events.append(("deliver", None, body, True))
                elif name == "yield":
                    time.sleep(0)
                time.sleep(0)
        except Exception as e:
            errors.append(f"thread {t}: {type(e).__name__}: {_short(e)}")

    previous = sys.getswitchinterval()
    sys.setswitchinterval(float(switch))
    try:
        workers = [threading.Thread(target=run_lane, args=(t, ops), daemon=True)
                   for t, ops in enumerate(lanes)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=30)
        if any(w.is_alive() for w in workers):
            raise Crash("resource", "a stash thread did not finish in 30 s")
    except Crash:
        shutil.rmtree(base, ignore_errors=True)
        raise
    finally:
        sys.setswitchinterval(previous)
    if errors:
        shutil.rmtree(base, ignore_errors=True)
        raise Crash("exception", errors[0])
    # The log holds each event in the order its thread took the
    # lock, after the operation returned, which is not the order the
    # operations touched the outbox: a stash can finish its write,
    # another thread deliver what it wrote, and the delivery be
    # logged before the stash. So the contract is read as counts,
    # not as a sequence: a delivered body must have been handed to
    # a stash for that key at some point, and a body is delivered
    # no more times than it was stashed plus the undelivers on its
    # key (an undeliver puts the record back for another go).
    faults = []
    stashed = {}            # (skey, body) -> stashes handed in
    undelivers = {}         # skey -> count
    delivers = {}           # (skey, body) -> deliveries
    delivered = 0
    for ev in events:
        if ev[0] == "stash":
            stashed[(ev[1], ev[2])] = stashed.get((ev[1], ev[2]), 0) + 1
        elif ev[0] == "undeliver":
            undelivers[ev[1]] = undelivers.get(ev[1], 0) + 1
    for ev in events:
        if ev[0] != "deliver":
            continue
        skey, body = ev[1], ev[2]
        delivered += 1
        if skey is None:
            owners = [k for (k, b) in stashed if b == body]
            if not owners:
                faults.append("delivered a body nobody stashed")
                continue
            skey = owners[0] if len(set(owners)) == 1 else None
            if skey is None:
                continue
        elif (skey, body) not in stashed:
            faults.append(f"{skey} delivered a body that was not stashed")
            continue
        delivers[(skey, body)] = delivers.get((skey, body), 0) + 1
        if delivers[(skey, body)] > (stashed[(skey, body)]
                                     + undelivers.get(skey, 0)):
            faults.append(f"{skey} delivered twice without an undeliver")
    if faults:
        shutil.rmtree(base, ignore_errors=True)
        raise Crash("contract", faults[0])
    for skey in stashed:
        paths = (
            ("outbox", R._stash_path(base, skey)),
            ("sent", R._sent_path(base, skey)),
            ("failed", os.path.join(R._outbox_dir(base), "failed",
                                    R._record_name(skey))),
        )
        for folder, path in paths:
            if os.path.exists(path) and R._read_record(path) is None:
                faults.append(f"{skey} left an unreadable record in {folder}")
    shutil.rmtree(base, ignore_errors=True)
    if faults:
        raise Crash("contract", faults[0])
    note("race", len(lanes), "delivered", delivered)
    return "accepted" if delivered else "refused"


def seeds_race_stash():
    K1, K2 = _STASH_KEYS
    S = lambda skey, body: {"op": "stash", "skey": skey, "body": body}  # noqa: E731
    D = lambda skey: {"op": "deliver", "skey": skey}  # noqa: E731
    F = lambda skey: {"op": "fail", "skey": skey}  # noqa: E731
    U = lambda skey: {"op": "undeliver", "skey": skey}  # noqa: E731
    Y = {"op": "yield"}
    specs = [
        ("two_keys", {"threads": [
            [S(K1, "one"), D(K1)],
            [S(K2, "two"), D(K2)]]}),
        ("fail_then_resend", {"threads": [
            [S(K1, "kept"), F(K1), {"op": "resend"}]]}),
        ("deliver_undeliver_deliver", {"threads": [
            [S(K1, "again"), D(K1), U(K1), D(K1)]]}),
        ("two_bodies_one_key", {"threads": [
            [S(K1, "alpha"), Y, D(K1)],
            [Y, S(K1, "beta")]]}),
        ("yield_only", {"threads": [[Y, Y], [Y]]}),
        ("empty", {"threads": []}),
        ("junk", {"threads": [[{"op": "nope"}], "nope"]}),
    ]
    return [make_entry("payload", spec, "seed:" + name, "seed") for name, spec in specs]


# ------------------------------------------------------------------
# race_state: threads over the pool's seen and retained files (de_dust2)
# ------------------------------------------------------------------
#
# race_stash holds the outbox; this holds the worker pool's other two
# shared files. The seen file is the replay cache and the claim
# ledger: save_seen merges under a file lock so two runners on one
# state directory cannot wipe each other's keys (the no-lost-update
# rule the merge was written for). The retained store is one file per
# job id, written O_EXCL to a temp name and renamed, so a reader sees
# the whole record or none of it. This target runs mark, load, save
# and prune from several threads over one base_dir under a short
# switch interval, and holds both: every key a thread marked is in
# the file after the join, and every record a thread saved reads back
# as exactly what it wrote.


def check_race_state(entry):
    """race_state: up to four threads, each a list of operations over
    one state directory's seen and retained files (mark a seen key,
    load the seen cache, save a retained record, load one, prune),
    interleaved under a short switch interval. Contract: no thread
    raises; after the join the seen file holds every key any thread
    marked (no lost update); a retained id reads back as one complete
    payload a thread saved for it, never a mix of two writes. Two
    saves of one id keep one of them. prune deletes retained files
    older than a day and rewrites the seen cache without dropping a
    fresh key. The directory is removed on every exit, including a
    crash. Accepted when a key was marked or a record saved."""
    spec = entry["data"]
    if TU._lone_surrogate(spec):
        note("gate", "lone surrogate")
        return "refused"
    lanes = _race_ops(spec)
    if not lanes:
        return "refused"
    switch = spec.get("switch", 1e-5) if isinstance(spec, dict) else 1e-5
    if isinstance(switch, bool) or not isinstance(switch, (int, float)) \
            or switch != switch or not 1e-6 <= switch <= 1e-2:
        switch = 1e-5
    base = _tmpdir(prefix="hp-de_dust-state-")
    try:
        seen_path = os.path.join(base, "seen.json")
        now = time.time()
        marked = {}               # key -> thread that marked it
        marked_lock = threading.Lock()
        saved = {}                # job_id -> payloads whose write returned
        saved_lock = threading.Lock()
        errors = []

        def run_lane(t, ops):
            try:
                for i, op in enumerate(ops):
                    name = op["op"]
                    if name == "mark":
                        tag = op.get("key")
                        key = tag if isinstance(tag, str) and tag else f"bm-seen-{t}-{i}"
                        R.save_seen(seen_path, {key: True},
                                    keep_sec=R.seen_keep_sec({}))
                        # A key with a NUL is dropped by the store's
                        # own rule (_write_seen_kept); the file is not
                        # held to it.
                        if "\x00" not in key:
                            with marked_lock:
                                marked[key] = t
                    elif name == "load_seen":
                        got = R.load_seen(seen_path)
                        if not isinstance(got, dict):
                            errors.append(f"thread {t}: load_seen returned "
                                          f"{type(got).__name__}, not a dict")
                    elif name == "save":
                        raw = op.get("id")
                        job_id = raw if isinstance(raw, str) and raw else f"bm-ret-{t}-{i}"
                        payload = {"v": job_id, "t": t, "i": i,
                                   "saved_at": now, "body": "x" * (i % 7)}
                        R.save_retained(base, job_id, payload)
                        if R._SAFE_JOB_ID.match(job_id) and job_id not in (".", ".."):
                            with saved_lock:
                                saved.setdefault(job_id, []).append(payload)
                    elif name == "load":
                        raw = op.get("id")
                        job_id = raw if isinstance(raw, str) and raw else f"bm-ret-{t}-{i}"
                        got = R.load_retained(base, job_id)
                        if got is not None and not isinstance(got, dict):
                            errors.append(f"thread {t}: load_retained returned "
                                          f"{type(got).__name__}")
                        elif isinstance(got, dict) and got.get("v") not in (None, job_id):
                            errors.append(f"thread {t}: load_retained({job_id}) "
                                          f"returned record for {got.get('v')}")
                    elif name == "prune":
                        raw = op.get("days", 1)
                        days = raw if isinstance(raw, int) \
                            and not isinstance(raw, bool) and raw > 0 else 1
                        R.prune_retained(base, days)
                        R.save_seen(seen_path, {},
                                    keep_sec=R.seen_keep_sec({}))
                    elif name == "yield":
                        time.sleep(0)
                    time.sleep(0)
            except Exception as e:  # the contract: nothing raises
                errors.append(f"thread {t}: {type(e).__name__}: {_short(e)}")

        previous = sys.getswitchinterval()
        sys.setswitchinterval(float(switch))
        try:
            workers = [threading.Thread(target=run_lane, args=(t, ops), daemon=True)
                       for t, ops in enumerate(lanes)]
            for w in workers:
                w.start()
            for w in workers:
                w.join(timeout=30)
            if any(w.is_alive() for w in workers):
                raise Crash("resource", "a state thread did not finish in 30 s")
        finally:
            sys.setswitchinterval(previous)
        if errors:
            raise Crash("exception", errors[0])
        final = R.load_seen(seen_path)
        if not isinstance(final, dict):
            raise Crash("shape", "the seen file does not read back as a dict")
        missing = [k for k in marked if k not in final]
        if missing:
            raise Crash("race", f"{len(missing)} seen key(s) a thread recorded "
                        f"are not in the file after the join, e.g. {missing[0]} "
                        f"(worker pool lost a claim)")
        for job_id, payloads in saved.items():
            got = R.load_retained(base, job_id)
            if got is None:
                raise Crash("race", f"the retained record {job_id} a thread saved "
                            "is absent after the join")
            if got not in payloads:
                raise Crash("race", f"the retained record {job_id} read back as "
                            f"a mix of writes (v={got.get('v')}, t={got.get('t')}, "
                            f"i={got.get('i')})")
        note("race_state", len(lanes), "marked", len(marked), "saved", len(saved))
        return "accepted" if (marked or saved) else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)

def seeds_race_state():
    M = lambda **kw: dict(op="mark", **kw)          # noqa: E731
    LS = {"op": "load_seen"}
    SV = lambda **kw: dict(op="save", **kw)         # noqa: E731
    LD = lambda **kw: dict(op="load", **kw)         # noqa: E731
    P = {"op": "prune"}
    Y = {"op": "yield"}
    specs = [
        ("two_markers_one_key", {"threads": [
            [M(key="bm-seen-shared"), LS],
            [Y, M(key="bm-seen-shared"), LS]]}),
        ("four_markers_distinct", {"switch": 1e-6, "threads": [
            [M(), M(), M(), LS], [M(), LS, M(), M()],
            [LS, M(), M(), M()], [M(), M(), LS, M()]]}),
        ("mark_and_load_interleaved", {"threads": [
            [M(key="bm-seen-a"), Y, M(key="bm-seen-b"), LS],
            [LS, M(key="bm-seen-c"), LS, M(key="bm-seen-d")]]}),
        ("save_and_load_same_id", {"threads": [
            [SV(id="bm-ret-shared"), LD(id="bm-ret-shared")],
            [Y, LD(id="bm-ret-shared"), SV(id="bm-ret-shared")]]}),
        ("save_distinct_records", {"switch": 1e-6, "threads": [
            [SV(), SV(), LD(), SV()], [SV(), LD(), SV(), SV()],
            [LD(), SV(), SV(), LD()]]}),
        ("seen_and_retained_together", {"threads": [
            [M(key="bm-seen-x"), SV(id="bm-ret-x"), LS, LD(id="bm-ret-x")],
            [SV(id="bm-ret-y"), M(key="bm-seen-y"), LD(id="bm-ret-y"), LS]]}),
        ("load_before_write", {"threads": [
            [LS, LD(id="bm-ret-absent")], [P, LD(id="bm-ret-missing")]]}),
        ("unsafe_ids", {"threads": [
            [SV(id=".."), SV(id="bad id with spaces"), SV(id="")],
            [SV(id="bm-ret-ok"), LD(id="..")]]}),
        ("marks_then_many_loads", {"threads": [
            [M(), M()], [LS, LS, LS], [P, P, P], [LS, LS]]}),
        ("unknown_ops", {"threads": [[{"op": "nope"}, 7, "mark", M()], "x"]}),
        ("empty", {"threads": []}),
        ("not_an_object", ["mark"]),
    ]
    return [make_entry("payload", spec, "seed:" + name, "seed") for name, spec in specs]


# ------------------------------------------------------------------
# dtls_hostile: the client against a server without the key (de_dust2)
# ------------------------------------------------------------------
#
# dtls_session runs a keyed server; here the server does not hold the
# client's PSK. That is the threat on the wire: a peer that never
# shared the key, trying to be taken for the runner. The sound
# invariant this target holds is the plain one -- a server that lacks
# the key cannot establish the client and cannot make it surface a
# message, whatever it sends. A script runs the client against such a
# server and mutates the wire in flight: flips, cuts, duplicates,
# reorders, drops, injects arbitrary bytes, moves the clock. The
# client must never reach "established", never append a server
# message, and raise nothing but DtlsError. (Whether a mutation is
# cosmetic or MAC-protected is the server's to judge; this target
# does not guess it -- it holds the one line that never moves: no
# key, no session.)

_HOSTILE_ADDR = ("192.0.2.5", 41000)
_HOSTILE_SECRET = "bm-secret-0001"
_HOSTILE_WRONG = "bm-secret-not-the-one-9"
_HOSTILE_CRNG = b"\x44"
_HOSTILE_MAX_STEPS = 64


def _hostile_client():
    return DT.DtlsClientCore(_HOSTILE_SECRET, rng=lambda n: _HOSTILE_CRNG * n)


def _hostile_server():
    return DT.DtlsServerCore(
        secrets_map={DT.identity_for(""): _HOSTILE_WRONG},
        rng=lambda n: b"\x5a" * n,
        greeting_for=lambda s: b'{"type":"greeting","v":1}')


def check_dtls_hostile(entry):
    """dtls_hostile: a script running the client against a server that
    does not hold its key, mutating the wire in flight (flip, cut,
    dup, reorder, drop, inject, tick). Contract: the client raises
    nothing but DtlsError, never reaches "established", and never
    surfaces a server message -- no key, no session, whatever the
    server sends. Accepted when the client engaged the handshake
    (left idle) before refusing."""
    script = entry["data"]
    if TU._lone_surrogate(script):
        note("gate", "lone surrogate")
        return "refused"
    steps = script if isinstance(script, list) else [script]
    client = _hostile_client()
    server = _hostile_server()
    now = _DTLS_NOW
    pending = []

    def drive_client(fn, *args):
        got, exc = _call(fn, *args)
        if exc is not None:
            if isinstance(exc, DT.DtlsError):
                return []
            raise Crash("exception", f"the client's {fn.__name__} raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        return got if isinstance(got, list) else []

    def to_server(dg):
        got, exc = _call(server.feed, dg, _HOSTILE_ADDR, now)
        if exc is not None:
            if isinstance(exc, DT.DtlsError):
                return
            raise Crash("exception", f"the server's feed raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if isinstance(got, list):
            pending.extend(bytes(x) for x in got if isinstance(x, (bytes, bytearray)))

    def feed_client(dg):
        before = len(client.app_messages)
        for out in drive_client(client.feed, dg, now):
            if isinstance(out, (bytes, bytearray)):
                to_server(bytes(out))
        if len(client.app_messages) > before:
            raise Crash("auth", "the client surfaced a server message from a "
                        "server that does not hold its key")
        _assert_hostile(client)

    for out in drive_client(client.start, now):
        if isinstance(out, (bytes, bytearray)):
            to_server(bytes(out))

    engaged = False
    for step in steps[:_HOSTILE_MAX_STEPS]:
        if not isinstance(step, dict) or not isinstance(step.get("op"), str):
            continue
        op = step["op"]
        if op == "deliver":
            n = step.get("n", 1)
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                n = 1
            batch = pending[:min(n, 8, len(pending))]
            del pending[:len(batch)]
            if step.get("reverse"):
                batch.reverse()
            if step.get("drop"):
                batch = []
            dup = step.get("dup", 1)
            if isinstance(dup, bool) or not isinstance(dup, int) or dup < 1:
                dup = 1
            for dg in batch:
                dg = bytearray(dg)
                ats = step.get("flip")
                if isinstance(ats, list):
                    for off in ats[:8]:
                        if isinstance(off, int) and not isinstance(off, bool) and dg:
                            dg[off % len(dg)] ^= 0x01
                cut = step.get("cut")
                if isinstance(cut, int) and not isinstance(cut, bool) and cut >= 0:
                    dg = dg[:cut]
                for _ in range(min(dup, 4)):
                    feed_client(bytes(dg))
        elif op == "inject":
            raw = step.get("bytes")
            data = None
            if isinstance(raw, str):
                try:
                    data = bytes.fromhex(raw)
                except ValueError:
                    data = raw.encode("utf-8", "surrogatepass")
            elif isinstance(raw, int) and not isinstance(raw, bool):
                data = bytes([raw & 0xFF]) * (abs(raw) % 64)
            if data is not None:
                feed_client(data)
        elif op == "tick":
            dt = step.get("dt", 1.0)
            if isinstance(dt, bool) or not isinstance(dt, (int, float)) \
                    or dt != dt or dt < 0:
                dt = 1.0
            now += min(float(dt), 86400.0)
            for out in drive_client(client.tick, now):
                if isinstance(out, (bytes, bytearray)):
                    to_server(bytes(out))
            _assert_hostile(client)
        elif op == "app":
            drive_client(client.send_app, b"[HOMING-PIGEON] early\n")
            _assert_hostile(client)
        if client.state not in ("idle", "new"):
            engaged = True

    _assert_hostile(client)
    note("hostile", "state", client.state, "engaged", engaged)
    return "accepted" if engaged else "refused"


def _assert_hostile(client):
    if client.state == "established":
        raise Crash("auth", "the client established with a server that does "
                    "not hold its key")
    if client.app_messages:
        raise Crash("auth", "the client holds a server message from a server "
                    "that does not hold its key")


def seeds_dtls_hostile():
    D = lambda **kw: dict(op="deliver", **kw)       # noqa: E731
    I = lambda h: dict(op="inject", bytes=h)        # noqa: E731
    run = [D(), D(), D(), D()]
    specs = [
        ("full_handshake", run),
        ("deliver_all_at_once", [D(n=8)]),
        ("flipped_flight", [D(flip=[6, 10]), D(flip=[6]), D(), D()]),
        ("cut_flight", [D(cut=8), D(), D(), D()]),
        ("duplicated_flight", [D(dup=3), D(dup=2), D(), D()]),
        ("reordered_flight", [D(n=8, reverse=True)]),
        ("dropped_first", [D(drop=True), D(), D(), D()]),
        ("junk_then_handshake", [I("deadbeef"), I("00" * 40)] + run),
        ("handshake_then_junk", run + [I("ff" * 50)]),
        ("only_junk", [I("00"), I("414243"), I(""), I("ff" * 64)]),
        ("app_midway", [D(), dict(op="app"), D(), D(), D()]),
        ("tick_through", [D(), dict(op="tick", dt=1.0), D(),
                          dict(op="tick", dt=61.0), D(), D()]),
        ("give_up_then_more", [D(), dict(op="tick", dt=120.0)] + run),
        ("empty", []),
        ("not_a_list", {"op": "deliver"}),
        ("junk_steps", [5, "deliver", None, {"op": "nope"}, {"op": "deliver", "n": -1}]),
    ]
    return [make_entry("payload", script, "seed:" + name, "seed")
            for name, script in specs]


class _EdgeSubject:
    """The Worker's subject router, one node process for the run
    (de_dust2). None when node is not there: the campaign still
    replays. Returns (job_id, result_id) as the gate reads them."""

    proc = None
    skip = False
    lock = threading.Lock()
    script = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "cloud/queues-worker/src/edge_subject_stdio.mjs")

    @classmethod
    def ids(cls, subject):
        with cls.lock:
            if cls.skip:
                return None
            if cls.proc is None or cls.proc.poll() is not None:
                try:
                    cls.proc = subprocess.Popen(
                        ["node", cls.script],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
                except OSError:
                    cls.skip = True
                    return None
            try:
                cls.proc.stdin.write(json.dumps(
                    {"subject": subject}, ensure_ascii=True) + "\n")
                cls.proc.stdin.flush()
                line = cls.proc.stdout.readline()
            except (OSError, UnicodeEncodeError, TypeError, ValueError):
                cls._drop()
                return None
            if not line:
                cls._drop()
                return None
            try:
                got = json.loads(line)
            except ValueError:
                cls._drop()
                return None
            if not isinstance(got, dict) or set(got) - {"job", "result"}:
                cls._drop()
                return None
            return (got.get("job"), got.get("result"))

    @classmethod
    def _drop(cls):
        proc = cls.proc
        cls.proc = None
        if proc is not None and proc.poll() is None:
            proc.kill()


def check_edge_subject(entry):
    """edge_subject: one subject line (de_dust2). The hosted queue's
    Worker routes a message by the id it reads from the subject with
    jobIdOf and resultIdOf; the runner reads the same subject with
    _JOB_ID_RE and _RESULT_ID_RE (runner/wire/transports.py), the
    same two patterns. Contract: the gate and the runner read the
    same job id and the same result id from every subject -- else a
    message is one id at the gate and another, or none, at the
    runner, and the job routes two ways. Neither extractor raises;
    a pathological subject that makes either regex backtrack is
    caught by the slow class. Accepted when an id was read, refused
    when neither side read one. Skipped (refused) when node is
    absent, so the campaign still replays."""
    subject = entry["data"]
    if not isinstance(subject, str):
        # A mutator may hand a non-string; that is not a subject, not
        # a fault. Both sides read nothing from it.
        return "refused"
    if TU._lone_surrogate(subject):
        note("edge_subject", "lone surrogate")
        return "refused"
    pj = TR._JOB_ID_RE.search(subject)
    pr = TR._RESULT_ID_RE.search(subject)
    py_job = pj.group(1) if pj else None
    py_result = pr.group(1) if pr else None
    pair = _EdgeSubject.ids(subject)
    if pair is None:
        note("edge_subject", "skipped")
        return "accepted" if (py_job or py_result) else "refused"
    edge_job, edge_result = pair
    if edge_job != py_job:
        raise Crash("agreement", "the gate and the runner read different "
                    f"job ids from the subject: gate {edge_job!r}, "
                    f"runner {py_job!r}")
    if edge_result != py_result:
        raise Crash("agreement", "the gate and the runner read different "
                    f"result ids from the subject: gate {edge_result!r}, "
                    f"runner {py_result!r}")
    note("edge_subject", "job" if py_job else "-", "result" if py_result else "-")
    return "accepted" if (py_job or py_result) else "refused"


def seeds_edge_subject():
    subjects = [
        "[HOMING-PIGEON] job bm-0001",
        "[HOMING-PIGEON] result bm-0001",
        "[HOMING-PIGEON] qresult q-0001",
        "[HOMING-PIGEON] TEST job bm-0002",
        "Re: [HOMING-PIGEON] job bm-0003",
        "[HOMING-PIGEON] job",                      # no id
        "[HOMING-PIGEON]   job   bm-0004",          # extra spaces
        "[HOMING-PIGEON]\tjob\tbm-0005",            # tabs
        "[homing-pigeon] JOB bm-0006",              # case
        "[HOMING-PIGEON] a b c job bm-0007",        # words between
        "[HOMING-PIGEON] job bm result r1",         # job wins, first match
        "[HOMING-PIGEON] result r1 job j1",         # both present
        "[HOMING-PIGEON] job ../escape",            # id the runner would reject later
        "[HOMING-PIGEON] job id two",          # nbsp inside
        "[HOMING-PIGEON] job  x",              # line separator
        "nothing to see here",
        "",
        "[HOMING-PIGEON]",
        "[HOMING-PIGEON] " + "word " * 40 + "job tail",   # many words
        "[HOMING-PIGEON]" + " " * 200 + "job spaced",      # long run of spaces
    ]
    return [make_entry("payload", subj, "seed:edge_subject_%d" % i, "seed")
            for i, subj in enumerate(subjects)]



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
# A member that is absent, told apart from one that is None.
_MISSING = object()
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


def _query_vocabulary(apply=PO.apply_result_policy):
    """The text a result carries when the job wrote nothing at all:
    the fixed exec members and the result the policy reader shapes
    from empty streams under every view (its member names,
    `output_digest` and `attestations` among them, and its fixed
    values). A stream line that is also in this text says nothing
    of the output, since the result says it with no output (Q112).
    Read once at import, from the reader as imported, so neither a
    replay's mutant nor a test's stand-in shapes it."""
    parts = [_QUERY_FIXED_TEXT]
    for view in R.VIEW_ORDER:
        job = {"job_id": "bm-q-0001", "kind": "exec",
               "result_policy": {"view": view}}
        for exe in (dict(_QUERY_EXEC, stdout="", stderr=""),
                    dict(_QUERY_EXEC, stdout="", stderr="", outputs=[])):
            try:
                result, _retain = apply({}, job, exe, _QUERY_PATTERNS, True)
                parts.append(json.dumps(result, sort_keys=True, default=str))
            except Exception:
                pass
    return "\n".join(parts)


_QUERY_VOCABULARY = _query_vocabulary()


def _query_pieces(out, err):
    """The parts of the output a non-full view must not carry: the
    whole of each stream and every line of them long enough to be
    recognized, less any that is also in the result's own vocabulary
    (the output may say the completion time, or name a member)."""
    pieces = set()
    for text in (out, err):
        if len(text) >= _LEAK_MIN:
            pieces.add(text)
        for line in text.splitlines():
            if len(line) >= _LEAK_MIN:
                pieces.add(line)
    return {p for p in pieces if p not in _QUERY_VOCABULARY}


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


def _query_outputs_view(view, outputs, result):
    """PROTOCOL section 6 on `outputs[]` (Q101, Q106): under `full`
    the entries come back as the exec result gave them; under
    `redacted` and `summary` each object entry is projected onto the
    commitment (`name`, `size`, `sha384`, `omitted`) and nothing else
    of it leaves, so a member the collector never writes cannot carry
    the job's output past the view; under `attested`, and whenever
    the exec result's member is not a list, there is no `outputs` at
    all."""
    got = result.get("outputs", _MISSING)
    if view == "attested" or not isinstance(outputs, list):
        if got is not _MISSING:
            raise Crash("leak" if view == "attested" else "contract",
                        f"a {view} result carries outputs it was not "
                        "given as a list" if view != "attested" else
                        "an attested result carries outputs")
        return
    if view == "full":
        if got != outputs:
            raise Crash("contract", "a full result's outputs are not the "
                        "exec result's")
        note("outputs", view, len(outputs))
        return
    want = [_output_commitment(o) for o in outputs if isinstance(o, dict)]
    if got != want:
        raise Crash("contract", f"a {view} result's outputs are not the "
                    "entries' commitment (name, size, sha384, omitted)")
    note("outputs", view, len(got))


def _output_commitment(o):
    """The checker's own reading of PROTOCOL section 6: what of an
    output entry may leave below full, each member in its shape."""
    want = {}
    if isinstance(o.get("name"), str):
        try:
            if FN.validate_file_name(o["name"]) == o["name"]:
                want["name"] = o["name"]
        except Exception:
            pass
    if isinstance(o.get("size"), int) and not isinstance(o.get("size"), bool) \
            and o["size"] >= 0:
        want["size"] = o["size"]
    d = o.get("sha384")
    if isinstance(d, str) and len(d) == 96 and all(
            c in "0123456789abcdef" for c in d.lower()):
        want["sha384"] = d.lower()
    if o.get("omitted") in ("missing", "too_large", "outside the workdir",
                            "not a regular file", "unreadable",
                            "changed while read"):
        want["omitted"] = o["omitted"]
    return want


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
    outputs = None
    if isinstance(data, dict):
        policy = data.get("policy")
        out = _query_text(data.get("output"))
        err = _query_text(data.get("stderr"))
        if "outputs" in data:
            # Q101: the files a job brought home ride the exec result
            # into every view (PROTOCOL section 6).
            outputs = data.get("outputs")
    else:
        policy, out, err = data, "", ""
    if len(out) + len(err) > QUERIES_MAX_TEXT:
        raise Crash("corpus", "a queries entry's output is over the cap")
    if TU._lone_surrogate(policy) or TU._lone_surrogate(outputs):
        # The verifier refuses a body with a lone surrogate (Q85), so
        # a policy carrying one never reaches these readers; and the
        # collector writes an output entry from a name the rules
        # accepted (no surrogate) and bytes it encoded, so neither does
        # an outputs list carrying one (Q106).
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
    if outputs is not None:
        exe["outputs"] = outputs
    pieces = _query_pieces(out, err)
    # An output's commitment leaves under every view by design
    # (PROTOCOL section 6): the name the job gave the file (Q106), and
    # the size and digest of the bytes the job wrote (Q111). A stream
    # line that is also one of them says nothing the commitment does
    # not, so the checker's own reading of the commitment is exempt.
    for o in outputs if isinstance(outputs, list) else []:
        if isinstance(o, dict):
            for member in _output_commitment(o).values():
                pieces.discard(member if isinstance(member, str)
                               else str(member))
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
        _query_outputs_view(view, outputs, result)
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
                     "query_error", "policy")
# The whole-query refusals that come before the record is read: they
# name no job and spend nothing (PROTOCOL.md section 10). Of them only
# rate_limit reads the hourly window.
_QUERY_BEFORE_RECORD = ("unsupported", "rate_limit", "policy")
_DEFAULT_RETAINED = {
    "job_id": "bm-job-0001", "kind": "exec", "script": "echo",
    "stdout": "ok\nERROR one\nERROR two\n", "stderr": "", "exit_code": 0,
    "timed_out": False, "duration_sec": 0.5, "view": "full", "budget": 8,
    "spent": 0, "patterns": _QUERY_PATTERNS, "confined": True,
    "digest": "d" * 96, "saved_at": NOW, "key": ""}


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
            or not _SUBJECT_TOKEN.fullmatch(subject_id):
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
    base = _tmpdir(prefix="hp-de_dust-query-")
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
        # The door's inputs (Q103 item 8): a key_policies map and the
        # deny flag, as an entry names them.
        if isinstance(data.get("key_policies"), dict):
            cfg["key_policies"] = data["key_policies"]
        if data.get("deny") is True:
            cfg["key_policies_default_deny"] = True
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
        if rejected not in _QUERY_BEFORE_RECORD and "job_id" not in reply:
            raise Crash("shape", "the reply does not name the job")
        if "job_id" in reply and isinstance(job_id, str) \
                and reply["job_id"] != job_id:
            raise Crash("contract", "the reply names a job other than the "
                        "query's")
        # PROTOCOL section 11: the hourly window is per sender. A
        # query refused before the window is read (unsupported) takes
        # no slot; one refused at the window took none and finds the
        # window full; every other query took exactly one.
        if rejected in ("unsupported", "policy"):
            if live_after != live_before:
                raise Crash("contract", f"a query refused as {rejected} "
                            "took a slot of the hourly window")
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
        # PROTOCOL.md section 11 (Q103 items 1 and 6): a retained
        # record is its owner's, a record with no owner the default
        # key's; another key's query that reaches the record is an
        # unknown job, never expired, never answered.
        if isinstance(before, dict) and rejected not in _QUERY_BEFORE_RECORD:
            owner = before.get("key") if isinstance(before.get("key"), str) else ""
            if R.canonical_key_id(secrets, key_id) != owner \
                    and rejected != "unknown_job":
                raise Crash("contract", "another key's query over a job it "
                            f"does not own was answered "
                            f"{rejected or 'with answers'}")
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
            or not _SUBJECT_TOKEN.fullmatch(ident):
        ident = "bm-task-0001"
    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {"v": 1, "type": kind, "task_id": ident, "result": payload}
    # A board message is fresh as a job is (Q98 item 12): an entry
    # written before that rule carries no issued_at and reads as sent
    # now; an entry that names one, stale, malformed or the NOW token,
    # keeps it, so those shapes still reach the door.
    if "issued_at" not in payload:
        payload = dict(payload, issued_at=NOW)
    payload = _stamp_issued_at(payload)
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
    base = _tmpdir(prefix="hp-de_dust-bmail-")
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
            or not _SUBJECT_TOKEN.fullmatch(ident):
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
    base = _tmpdir(prefix="hp-de_dust-v2-")
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
    work = _tmpdir(prefix="hp-de_dust-names-")
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
        # Q101: a file carried in the job (`content_b64`, strict
        # base64) and the files it asks home (`outputs`), in bodies
        # the verifiers trust, so the mutators reach those members.
        ("inline_file", _job(script="git apply fix.diff",
                             files=[{"name": "fix.diff",
                                     "content_b64": "LS0tIGEKKysrIGIK"}],
                             outputs=["reports/junit.xml"])),
        ("inline_file_empty", _job(files=[{"name": "e", "content_b64": ""}])),
        ("inline_file_no_padding", _job(files=[{"name": "p",
                                                "content_b64": "QQ"}])),
        ("inline_file_line_break", _job(files=[{"name": "l",
                                                "content_b64": "QQ==\n"}])),
        ("inline_file_non_ascii", _job(files=[{"name": "u",
                                               "content_b64": "Q\u00e9=="}])),
        ("inline_file_noncanonical_bits", _job(files=[{
            "name": "n", "content_b64": "QR=="}])),
        ("inline_file_and_url", _job(files=[{
            "name": "both", "content_b64": "QQ==",
            "url": "https://example.com/x"}])),
        ("inline_file_digest", _job(files=[{
            "name": "d", "content_b64": "QQ==",
            "sha384": hashlib.sha384(b"A").hexdigest()}])),
        ("outputs_nine", _job(outputs=[f"o{i}" for i in range(9)])),
        ("outputs_twice", _job(outputs=["a.txt", "a.txt"])),
        ("outputs_not_names", _job(outputs=["ok", 7, None, ["x"]])),
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
    out += _dtls_resume_seeds()
    return [make_entry("text", _dtls_text(blob), "seed:" + name, "seed")
            for name, blob in out]


def _dtls_resume_seeds():
    """Cookie-bearing second ClientHellos (de_dust2, P5): one that
    resumes each planted ticket, and one fresh handshake under the
    identity in the map. The core's rng is fixed, so the cookie a
    fresh core issues is the cookie it later accepts, and these
    datagrams reach `begin` and the ticket path on every replay."""
    out = []
    for name, ticket in (("resume_live", b"\x7a" * 24),
                         ("resume_gone", b"\x7b" * 24),
                         ("resume_unrecorded", b"\x7c" * 24),
                         ("hello_cookie", None)):
        server = _dtls_core()
        if ticket is None:
            client = DT.DtlsClientCore("bm-secret-0001", rng=lambda n: b"\x33" * n)
            client._identity = _DTLS_IDENTITY
        else:
            client = DT.DtlsClientCore("bm-secret-0001",
                                       ticket=(ticket, _DTLS_TICKET_PSK),
                                       rng=lambda n: b"\x33" * n)
        first = client.start(_DTLS_NOW)
        answer = []
        for dg in first:
            answer += server.feed(dg, _DTLS_ADDR, _DTLS_NOW)
        second = []
        for dg in answer:
            second += client.feed(dg, _DTLS_NOW)
        if second:
            out.append((name, second[0]))
    return out
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
    directory = _tmpdir(prefix="hp-bm-board-")
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
    directory = _tmpdir(prefix="hp-bm-channel-")
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


def seeds_keydir():
    fp = V._key_fingerprint(SECRET)
    fp_ops = V._key_fingerprint(OPS)
    far, past = _KEYDIR_FAR, _KEYDIR_PAST

    def d(**entries):
        return entries

    dirs = [
        ("all_in_use", d(**{"": {"state": "in_use"}, "ops": {"state": "in_use"},
                           "canary-key": {"state": "in_use"}})),
        ("default_by_fingerprint", d(**{fp: {"state": "in_use"},
                                        "ops": {"state": "in_use"},
                                        "canary-key": {"state": "in_use"}})),
        ("ops_superseded_open", d(**{"": {"state": "in_use"},
                                     "ops": {"state": "superseded",
                                             "not_after": far},
                                     "canary-key": {"state": "in_use"}})),
        ("ops_superseded_closed", d(**{"": {"state": "in_use"},
                                       "ops": {"state": "superseded",
                                               "not_after": past},
                                       "canary-key": {"state": "in_use"}})),
        ("ops_compromised", d(**{"": {"state": "in_use"},
                                 "ops": {"state": "compromised"},
                                 "canary-key": {"state": "in_use"}})),
        ("ops_destroyed", d(**{"": {"state": "in_use"},
                               "ops": {"state": "destroyed"},
                               "canary-key": {"state": "in_use"}})),
        ("ops_not_yet", d(**{"": {"state": "in_use"},
                             "ops": {"state": "in_use", "not_before": far},
                             "canary-key": {"state": "in_use"}})),
        ("ops_fingerprint_right", d(**{"": {"state": "in_use"},
                                       "ops": {"state": "in_use", "fingerprint": fp_ops},
                                       "canary-key": {"state": "in_use"}})),
        ("ops_fingerprint_wrong", d(**{"": {"state": "in_use"},
                                       "ops": {"state": "in_use", "fingerprint": fp},
                                       "canary-key": {"state": "in_use"}})),
        ("canary_missing", d(**{"": {"state": "in_use"}, "ops": {"state": "in_use"}})),
        ("empty", {}),
        ("ordered_next", d(**{"": {"state": "in_use"}, "ops": {"state": "in_use"},
                              "canary-key": {"state": "in_use"},
                              "next": {"state": "ordered", "fingerprint": "k-00000000"}})),
        ("bad_state", d(**{"": {"state": "live"}})),
        ("state_missing", d(**{"": {}})),
        ("entry_text", d(**{"": "in_use"})),
        ("bound_text", d(**{"": {"state": "in_use", "not_before": "soon"}})),
        ("bound_bool", d(**{"": {"state": "in_use", "not_after": True}})),
        ("bound_string_number", d(**{"": {"state": "superseded", "not_after": str(far)}})),
        ("in_use_expired", d(**{"": {"state": "in_use", "not_after": past}})),
        ("in_use_open", d(**{"": {"state": "in_use", "not_before": past, "not_after": far}})),
        ("bound_nested", d(**{"": {"state": "in_use", "not_before": {"at": far}}})),
        ("fingerprint_number", d(**{"": {"state": "in_use", "fingerprint": 7}})),
        ("extra_members", d(**{"": {"state": "in_use", "note": "x" * 40, "list": [1, 2]}})),
        ("not_an_object_list", [{"state": "in_use"}]),
        ("not_an_object_text", "in_use"),
        ("not_an_object_number", 1),
        ("not_an_object_null", None),
        ("unicode_name", d(**{"": {"state": "in_use"}, "op\u00e9ra": {"state": "in_use"}})),
    ]
    out = []
    for name, directory in dirs:
        out.append(make_entry("payload", {"directory": directory, "key_id": ""},
                              "seed:" + name, "seed"))
    for key_id in ("ops", "canary-key", fp, fp_ops, "nobody", 7, None):
        out.append(make_entry("payload", {"directory": dirs[0][1], "key_id": key_id},
                              "seed:key_" + str(key_id), "seed"))
    return out


def seeds_address():
    long_local = "l" * 64
    long_label = "d" * 63
    out = [
        ("plain", "submitter@example.com"),
        ("subdomain", "si.bot@mail.example.org"),
        ("plus", "si+runner@example.com"),
        ("dots_local", "first.last@example.com"),
        ("uppercase", "SI@EXAMPLE.COM"),
        ("digits", "1234@5678.example"),
        ("hyphen_label", "si@sub-example.com"),
        ("q113", "submitter@.comexample.com"),
        ("leading_dot", "si@.example.com"),
        ("double_dot", "si@example..com"),
        ("trailing_dot", "si@example.com."),
        ("hyphen_first", "si@-example.com"),
        ("hyphen_last", "si@example-.com"),
        ("no_tld", "si@localhost"),
        ("short_tld", "si@example.c"),
        ("numeric_tld", "si@example.123"),
        ("ip_literal", "si@[192.0.2.1]"),
        ("display_name", "SI <si@example.com>"),
        ("angle_only", "<si@example.com>"),
        ("two_addresses", "a@example.com, b@example.com"),
        ("space_inside", "s i@example.com"),
        ("padded", "  si@example.com  "),
        ("crlf", "si@example.com\r\nBcc: x@example.com"),
        ("lf", "si@example.com\nX: y"),
        ("tab", "si@exam\tple.com"),
        ("nul", "si@exam\x00ple.com"),
        ("unicode_local", "s\u00ed@example.com"),
        ("idn_domain", "si@b\u00fccher.example"),
        ("fullwidth_at", "si\uff20example.com"),
        ("quoted_local", '"si bot"@example.com'),
        ("empty", ""),
        ("at_only", "@"),
        ("no_at", "si.example.com"),
        ("two_at", "si@example@example.com"),
        ("long_local", long_local + "@example.com"),
        ("long_label", "si@" + long_label + ".example.com"),
        ("label_64", "si@" + long_label + "d.example.com"),
        ("len_254", "s" * (254 - len("@example.com")) + "@example.com"),
        ("len_255", "s" * (255 - len("@example.com")) + "@example.com"),
        ("many_labels", "si@" + ".".join(["a"] * 60) + ".example.com"),
        ("job_without_reply_to", {"job_id": "bm-addr-0002", "kind": "ping"}),
        ("reply_to_number", {"reply_to": 7}),
        ("reply_to_list", {"reply_to": ["si@example.com"]}),
        ("reply_to_object", {"reply_to": {"addr": "si@example.com"}}),
        ("reply_to_null", {"reply_to": None}),
        ("job_not_object", ["si@example.com"]),
    ]
    return [make_entry("text" if isinstance(t, str) else "payload", t,
                       "seed:" + n, "seed") for n, t in out]


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
    # Q101: the files a job brought home (`outputs[]`, PROTOCOL
    # section 6), under every view the entry asks for.
    hello = {"name": "reports/junit.xml", "size": 5,
             "sha384": hashlib.sha384(b"hello").hexdigest(),
             "content_b64": "aGVsbG8="}
    blob = bytes(range(256))
    binary = {"name": "out/blob.bin", "size": len(blob),
              "sha384": hashlib.sha384(blob).hexdigest(),
              "content_b64": base64.b64encode(blob).decode("ascii")}
    omitted = [{"name": "gone.txt", "omitted": "missing"},
               {"name": "big.log", "omitted": "too_large", "size": 2 << 20},
               {"name": "esc", "omitted": "outside the workdir"},
               {"name": "dir", "omitted": "not a regular file"},
               {"name": "locked", "omitted": "unreadable"},
               {"name": "moving", "omitted": "changed while read"}]
    for view in ("full", "redacted", "summary", "attested"):
        out.append(entry(f"outputs_one_{view}", {"view": view, "queries": [tail]}))
        out[-1][1]["outputs"] = [hello]
    for name, outs in (
            ("outputs_every_reason", omitted),
            ("outputs_binary", [binary]),
            ("outputs_eight", [dict(hello, name=f"r/{i}.xml") for i in range(8)]),
            ("outputs_not_objects", [hello, "stray", 7, None, ["x"]]),
            ("outputs_empty", []),
            ("outputs_not_a_list", {"name": "x"}),
            ("outputs_null", None),
            ("outputs_extra_member", [dict(hello, note="kept below full")])):
        for view in ("full", "summary"):
            out.append(entry(f"{name}_{view}", {"view": view}))
            out[-1][1]["outputs"] = outs
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
        # Q101: an `outputs[]` name is read by the same rules.
        ("output_report", "reports/junit.xml"), ("output_up", "../x"),
        ("output_device", "CON.txt"), ("output_255", "o" * 255),
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
        # Ownership (PROTOCOL.md section 11; Q103 items 1 and 6): a
        # record names its key; another key, by any of its names, is
        # told the job is unknown and spends nothing.
        entry("owned_by_ops_asked_by_ops", rec=retained(key="ops"), key_id="ops"),
        entry("owned_by_ops_asked_by_its_fingerprint", rec=retained(key="ops"),
              key_id=FP_OPS),
        entry("owned_by_ops_asked_by_the_owner", rec=retained(key="ops")),
        entry("owned_by_the_owner_asked_by_ops", rec=retained(key=""), key_id="ops"),
        entry("owner_not_text_asked_by_ops", rec=retained(key=7), key_id="ops"),
        entry("expired_owned_by_the_owner_asked_by_ops",
              rec=retained(key="", saved_at=1.0), key_id="ops"),
        # The door (section 14.1; Q103 item 8): allowed_kinds and the
        # deny flag at the query door, and the order before it.
        entry("door_kinds_without_query", key_id="ops",
              key_policies={"ops": {"allowed_kinds": ["exec"]}}),
        entry("door_kinds_with_query", rec=retained(key="ops"), key_id="ops",
              key_policies={"ops": {"allowed_kinds": ["exec", "query"]}}),
        entry("door_deny_no_entry", key_id="canary-key", deny=True),
        entry("door_deny_owner", deny=True),
        entry("door_policy_on_the_owner",
              key_policies={"": {"allowed_kinds": ["exec"]}}),
        entry("door_denied_and_stale", key_id="ops", deny=True,
              q=query(issued_at="2020-01-01T00:00:00Z")),
        entry("door_denied_version_2", key_id="ops", deny=True, q=query(v=2)),
        entry("door_denied_dry", key_id="ops", deny=True, dry=True),
        entry("door_denied_cleartext", key_id="ops", deny=True, cleartext=True),
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



# ------------------------------------------------------------------
# stage and collect: a job's inline files and the files it asks home
# (Q101, PROTOCOL section 6)
# ------------------------------------------------------------------

def check_stage(entry):
    """stage: one job's `files[]` and `outputs` before anything is
    staged -- _decode_inline over each inline file and
    _validate_outputs over the output names, the checks execute_job
    runs first. Contract: a bad member is refused with JobRejected
    and nothing else; an inline file that is accepted is canonical
    (its bytes re-encode to the very string the sender signed); an
    accepted output list is at most eight distinct names, each one a
    second pass of the name rules accepts unchanged. Accepted when
    every inline file and the output list are."""
    data = entry["data"]
    if not isinstance(data, dict):
        data = {"files": data}
    files = data.get("files")
    accepted = True
    for f in files if isinstance(files, list) else []:
        if not isinstance(f, dict) or "content_b64" not in f:
            continue
        got, exc = _call(EXE._decode_inline, f)
        if exc is not None:
            _expect_refusal(exc, R.JobRejected, "_decode_inline")
            accepted = False
            continue
        if not isinstance(got, bytes):
            raise Crash("shape", f"_decode_inline answered {type(got).__name__}")
        if base64.b64encode(got).decode("ascii") != f["content_b64"]:
            raise Crash("contract", "an accepted inline file is not the "
                        "canonical encoding of its bytes")
        note("inline", len(got))
    if "outputs" in data:
        got, exc = _call(EXE._validate_outputs, data.get("outputs"))
        if exc is not None:
            _expect_refusal(exc, R.JobRejected, "_validate_outputs")
            return "refused"
        if not isinstance(got, list) or len(got) > EXE.MAX_OUTPUTS \
                or len(set(got)) != len(got):
            raise Crash("contract", f"_validate_outputs answered {got!r}"[:200])
        for name in got:
            again, exc2 = _call(FN.validate_file_name, name)
            if exc2 is not None or again != name:
                raise Crash("contract", f"an accepted output name is not "
                            f"stable under the name rules: {name!r}"[:200])
        note("outputs", len(got))
    return "accepted" if accepted else "refused"


_COLLECT_KINDS = ("file", "dir", "link_in", "link_out", "fifo", "nothing")


def _lay_out(work, outside, item):
    """One item of a collect entry's work dir; False when this host
    cannot make it (no symlinks or FIFOs here)."""
    name = item.get("name")
    if not isinstance(name, str):
        return True
    try:
        name = FN.validate_file_name(name)
    except Exception:
        return True
    path = os.path.join(work, *name.split("/"))
    kind = item.get("kind")
    size = item.get("size")
    size = size if isinstance(size, int) and 0 <= size <= 1 << 20 else 5
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        if kind == "dir":
            os.makedirs(path, exist_ok=True)
        elif kind == "link_in":
            target = os.path.join(work, "_target")
            with open(target, "wb") as fh:
                fh.write(b"t" * size)
            os.symlink(target, path)
        elif kind == "link_out":
            os.symlink(outside, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "file":
            with open(path, "wb") as fh:
                fh.write(bytes((i * 7) & 0xFF for i in range(size)))
    except (OSError, NotImplementedError, AttributeError):
        return False
    return True


def check_collect(entry):
    """collect: _collect_outputs over a throwaway work dir the entry
    lays out (files, directories, a symlink inside, a symlink out, a
    FIFO), the names the job asked for, and the byte budget.
    Contract: it never raises; one entry per name, in the job's
    order, each naming it; a read entry's sha384 is the digest of its
    decoded content_b64 and its size that length; an entry not read
    names one of the six reasons and carries no bytes; the bytes read
    sum to at most max_output_file_bytes; nothing outside the work
    dir is read (its marker never appears)."""
    data = entry["data"]
    if not isinstance(data, dict):
        data = {"names": data}
    layout = data.get("layout")
    names = data.get("names")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        return "refused"
    budget = data.get("budget")
    cfg = {"max_output_file_bytes": budget} if budget is not None else {}
    limit = EXE._max_output_file_bytes(cfg)
    base = _tmpdir(prefix="hp-de_dust-collect-")
    try:
        work = os.path.join(base, "work")
        os.makedirs(work)
        outside = os.path.join(base, "outside")
        with open(outside, "wb") as fh:
            fh.write(b"OUTSIDE-MARKER")
        for item in layout if isinstance(layout, list) else []:
            if isinstance(item, dict) and not _lay_out(work, outside, item):
                note("host", "cannot make", item.get("kind"))
        got, exc = _call(EXE._collect_outputs, work, names, cfg)
        if exc is not None:
            raise Crash("exception", "_collect_outputs raised "
                        f"{type(exc).__name__}: {_short(exc)}")
        if not isinstance(got, list) or len(got) != len(names):
            raise Crash("shape", "_collect_outputs answered "
                        f"{type(got).__name__} of {len(got) if isinstance(got, list) else '?'}")
        total = 0
        for name, out in zip(names, got):
            if not isinstance(out, dict) or out.get("name") != name:
                raise Crash("contract", f"the entry for {name!r} is {out!r}"[:200])
            if "omitted" in out:
                if out["omitted"] not in ("missing", "too_large",
                                          "outside the workdir",
                                          "not a regular file", "unreadable",
                                          "changed while read"):
                    raise Crash("contract", f"an unknown reason {out['omitted']!r}")
                if "content_b64" in out:
                    raise Crash("contract", "an omitted entry carries bytes")
                note("omitted", out["omitted"])
                continue
            raw = base64.b64decode(out.get("content_b64", ""), validate=True)
            if b"OUTSIDE-MARKER" in raw:
                raise Crash("leak", f"{name!r} read the file outside the work dir")
            if out.get("size") != len(raw) \
                    or out.get("sha384") != hashlib.sha384(raw).hexdigest():
                raise Crash("contract", f"{name!r}: size or sha384 is not "
                            "its bytes'")
            total += len(raw)
            note("read", len(raw))
        if total > limit:
            raise Crash("contract", f"{total} bytes read over the {limit} budget")
        return "accepted" if any("content_b64" in o for o in got) else "refused"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def seeds_stage():
    def f(name, b64, **kw):
        return dict({"name": name, "content_b64": b64}, **kw)
    out = [
        ("one", {"files": [f("fix.diff", "LS0tIGEKKysrIGIK")],
                 "outputs": ["reports/junit.xml"]}),
        ("empty", {"files": [f("e", "")]}),
        ("canonical", {"files": [f("a", "QQ==")]}),
        ("noncanonical", {"files": [f("a", "QR==")]}),
        ("canonical_two", {"files": [f("a", "QUI=")], "outputs": []}),
        ("noncanonical_two_bits", {"files": [f("a", "QUJ=")]}),
        ("no_padding", {"files": [f("a", "QQ")]}),
        ("line_break", {"files": [f("a", "QQ==\n")]}),
        ("space", {"files": [f("a", "QQ ==")]}),
        ("urlsafe", {"files": [f("a", "-_8=")]}),
        ("non_ascii", {"files": [f("a", "Q\u00e9==")]}),
        ("not_text", {"files": [f("a", 7)]}),
        ("null", {"files": [f("a", None)]}),
        ("binary", {"files": [f("b", base64.b64encode(bytes(range(256))).decode())]}),
        ("outputs_eight", {"outputs": [f"o{i}" for i in range(8)]}),
        ("outputs_nine", {"outputs": [f"o{i}" for i in range(9)]}),
        ("outputs_twice", {"outputs": ["a", "a"]}),
        ("outputs_normalize_twice", {"outputs": ["a/b", "a//b"]}),
        ("outputs_up", {"outputs": ["../x"]}),
        ("outputs_device", {"outputs": ["CON"]}),
        ("outputs_not_names", {"outputs": ["ok", 7]}),
        ("outputs_not_a_list", {"outputs": "a"}),
        ("outputs_null", {"outputs": None}),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]


def seeds_collect():
    def it(name, kind="file", size=5):
        return {"name": name, "kind": kind, "size": size}
    out = [
        ("one", {"layout": [it("reports/junit.xml")],
                 "names": ["reports/junit.xml"]}),
        ("missing", {"layout": [], "names": ["gone"]}),
        ("dir", {"layout": [it("d", "dir")], "names": ["d"]}),
        ("link_in", {"layout": [it("l", "link_in")], "names": ["l"]}),
        ("link_out", {"layout": [it("x", "link_out")], "names": ["x"]}),
        ("fifo", {"layout": [it("p", "fifo")], "names": ["p"]}),
        ("too_large", {"layout": [it("big", size=200)], "names": ["big"],
                       "budget": 100}),
        ("budget_shared", {"layout": [it("a", size=60), it("b", size=60)],
                           "names": ["a", "b"], "budget": 100}),
        ("budget_zero", {"layout": [it("a")], "names": ["a"], "budget": 0}),
        ("budget_not_a_number", {"layout": [it("a")], "names": ["a"],
                                 "budget": "lots"}),
        ("budget_negative", {"layout": [it("a")], "names": ["a"],
                             "budget": -1}),
        ("nested", {"layout": [it("a/b/c.txt")], "names": ["a/b/c.txt"]}),
        ("order", {"layout": [it("b"), it("a")], "names": ["b", "gone", "a"]}),
        ("empty_file", {"layout": [it("z", size=0)], "names": ["z"]}),
        ("eight", {"layout": [it(f"o{i}") for i in range(8)],
                   "names": [f"o{i}" for i in range(8)]}),
    ]
    return [make_entry("payload", p, "seed:" + n, "seed") for n, p in out]

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
                "check": check_queries, "seeds": seeds_queries,
                # The reader runs a sender's grep pattern in its
                # worker under a deadline of its own (two seconds a
                # query, then the worker is killed and the answer is
                # timeout); a polynomial pattern such as `\s+\s+$`
                # over a long line spends up to that on each of the
                # six ceilings a try runs under. A try inside six
                # deadlines is the guard at work, not a slow reader.
                "slow_floor_sec": 6 * QU._GREP_DEADLINE + 1.0},
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
    "stage": {"files": [_src("ops", "exec.py"), _src("guard", "filenames.py")],
              "check": check_stage, "seeds": seeds_stage},
    "collect": {"files": [_src("ops", "exec.py")],
                "check": check_collect, "seeds": seeds_collect},
    # de_dust2, P5: readers with recent real bugs or new code.
    "keydir": {"files": [_src("wire", "verify.py"),
                         _src("transport_extensions", "dtls", "__main__.py")],
               "check": check_keydir, "seeds": seeds_keydir},
    "address": {"files": [_src("wire", "mailbox.py")],
                "check": check_address, "seeds": seeds_address},
    # de_dust2: stateful, in-memory protocol fuzzing (scripts, not bytes).
    "dtls_session": {"files": [_src("wire", "dtlsproto.py")],
                     "check": check_dtls_session, "seeds": seeds_dtls_session,
                     "technique": "protocol"},
    # de_dust2: threads interleaved over shared state.
    "race_board": {"files": [_src("wire", "board.py")],
                   "check": check_race_board, "seeds": seeds_race_board,
                   "technique": "race"},
    # de_dust2: the worker pool's outbox, the same technique.
    "race_stash": {"files": [_src("runner.py")],
                   "check": check_race_stash, "seeds": seeds_race_stash,
                   "technique": "race"},
    "race_state": {"files": [_src("runner.py")],
                   "check": check_race_state, "seeds": seeds_race_state,
                   "technique": "race"},
    "dtls_hostile": {"files": [_src("wire", "dtlsproto.py")],
                     "check": check_dtls_hostile, "seeds": seeds_dtls_hostile,
                     "technique": "protocol"},
    # de_dust2: the hosted queue's subject router vs the runner's.
    "edge_subject": {"files": [_src("wire", "transports.py")],
                     "check": check_edge_subject, "seeds": seeds_edge_subject,
                     "technique": "parity"},
}


def corpus_path(target, crashes=False, slow=False):
    name = target + (".crashes.jsonl" if crashes else
                     ".slow.jsonl" if slow else ".jsonl")
    return os.path.join(CORPUS_DIR, name)


def header(target):
    return {"de_dust": 1, "target": target, "Agent-Stamp": STAMP}


def retired_path(target):
    """The sidecar naming every crash record `promote` retired from
    <target>.crashes.jsonl: {id: {"on": date, "why": promoted or
    redundant}}. A rig that banks by union (runner/tools/rig_bank.py)
    reads it so a stale local copy of a fixed crash never comes back
    to the tree as a probe that passes (Q106)."""
    return os.path.join(CORPUS_DIR, target + ".retired.json")


def load_retired(target):
    path = retired_path(target)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    retired = data.get("retired") if isinstance(data, dict) else None
    return retired if isinstance(retired, dict) else {}


def save_retired(target, retired):
    path = retired_path(target)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = dict(header(target), retired=dict(sorted(retired.items())))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, ensure_ascii=True, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def is_ancestor(older, newer, cwd=None):
    """True, False, or None when git cannot say (no git, a shallow
    tree without the commits, a bad name)."""
    import subprocess
    if not (isinstance(older, str) and isinstance(newer, str)
            and 7 <= len(older) <= 40 and 7 <= len(newer) <= 40):
        return None
    try:
        proc = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer],
                              cwd=cwd or ROOT, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


def retired_stale(record, retired, cwd=None):
    """True when a crash record is one `promote` retired and was found
    on a tree at or before the retirement: a copy a rig kept, or the
    same crash found again by a grow on an older tree (an echo), not
    the crash found again after the fix (a regression, which stays a
    crash). The record's `head` against the retirement's `head`
    decides when git can compare them; otherwise the `found` date
    against the retirement's date, a day at a time."""
    if not isinstance(record, dict):
        return False
    row = retired.get(record.get("id"))
    if not isinstance(row, dict):
        return False
    verdict = is_ancestor(record.get("head"), row.get("head"), cwd)
    if verdict is not None:
        return verdict
    found = record.get("found")
    on = row.get("on")
    if not isinstance(found, str) or not isinstance(on, str):
        return True
    return found <= on


def prune_retired_crashes(target, out=print):
    """Drop from <target>.crashes.jsonl the records the tree retired
    and this copy kept (a rig's local file survives its resets). The
    grow calls it first, so a crash found again after a fix files
    under today's date and the bank takes it."""
    retired = load_retired(target)
    path = corpus_path(target, crashes=True)
    if not retired or not os.path.exists(path):
        return 0
    records = load(path)
    kept = [r for r in records if not retired_stale(r, retired)]
    dropped = len(records) - len(kept)
    if dropped:
        if kept:
            save(path, target, kept)
        else:
            os.remove(path)
        out(f"{target}: {dropped} retired crash record(s) dropped from "
            f"the local file")
    return dropped


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


# A write that a flickering disk refuses once is tried again (Menlo
# Park, 30-OCT: "operation not permitted" at random on temp files,
# the corpus and the ledger, landing on the next try). Five tries over
# about three seconds; past that the fault is the machine's and the
# OSError stands.
_PATIENT_ERRNOS = {errno.EPERM, errno.EACCES, errno.ENOENT, errno.EIO,
                   errno.EBUSY, errno.EAGAIN}
_PATIENT_TRIES = 5
_PATIENT_NAP = 0.1


def _patient(fn, *args, **kwargs):
    """fn(*args) with retries on the errnos a flaky disk answers."""
    nap = _PATIENT_NAP
    for attempt in range(_PATIENT_TRIES):
        try:
            return fn(*args, **kwargs)
        except OSError as e:
            if e.errno not in _PATIENT_ERRNOS or attempt == _PATIENT_TRIES - 1:
                raise
            time.sleep(nap)
            nap *= 2


def _tmpdir(prefix):
    """tempfile.mkdtemp, patiently, under this process's own directory.

    A grow that is killed cannot run its own cleanup. The next grow
    removes a directory whose pid is gone (Q126). A directory a check
    finishes is still removed by that check."""
    path = _patient(tempfile.mkdtemp, prefix=prefix, dir=_grow_tmp_root())
    # On the record, so check() removes what one try made when the
    # try ends, kept or crashed: a leaked directory then lives for
    # one try, not for the process, and a long slice on a crashing
    # family cannot fill the volume from inside one grow.
    _TMP_MADE.append(path)
    return path


_TMP_MADE = []


def _drop_tmp_since(mark):
    """Remove the temp directories made since `mark` entries stood."""
    while len(_TMP_MADE) > mark:
        shutil.rmtree(_TMP_MADE.pop(), ignore_errors=True)


_own_tmp = None


def _grow_tmp_root():
    """One directory for every temp this process opens, named with
    the pid so a later grow can tell a dead one's from a live one's."""
    global _own_tmp
    if _own_tmp is None:
        # HP_DE_DUST_TMP names the volume to put it on: a rig whose
        # /tmp is a small tmpfs (Nuremberg, 459 MB) points this at
        # its root volume and the snapshots and checks stay off it.
        _own_tmp = _patient(tempfile.mkdtemp,
                            prefix=f"hp-de_dust-{os.getpid()}-",
                            dir=os.environ.get("HP_DE_DUST_TMP") or None)
        atexit.register(_remove_own_tmp)
    return _own_tmp


def _remove_own_tmp():
    global _own_tmp
    if _own_tmp:
        shutil.rmtree(_own_tmp, ignore_errors=True)
        _own_tmp = None


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def sweep_dead_grow_temps(tmp=None, alive=None):
    """Remove grow temp directories whose process is gone.

    Only `hp-de_dust-<pid>-*`. A flat `hp-de_dust-*` can belong to
    another lane still running, and this does not touch it."""
    tmp = tmp or os.environ.get("HP_DE_DUST_TMP") or tempfile.gettempdir()
    alive = alive if alive is not None else _pid_alive
    removed = []
    try:
        names = os.listdir(tmp)
    except OSError:
        return removed
    me = os.getpid()
    for name in names:
        rest = name[len("hp-de_dust-"):] if name.startswith("hp-de_dust-") else ""
        pid_text, sep, _suffix = rest.partition("-")
        if not sep or not pid_text.isdigit():
            continue
        pid = int(pid_text)
        if pid == me or alive(pid):
            continue
        path = os.path.join(tmp, name)
        if not os.path.isdir(path):
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed.append(name)
    return removed


def _arm_term_cleanup():
    """A SIGTERM, the way a cycle stops a grow, removes this
    process's temp directory. A SIGKILL cannot; the next grow's
    sweep does."""
    if getattr(_arm_term_cleanup, "done", False) or os.name != "posix":
        return
    _arm_term_cleanup.done = True
    prev = signal.getsignal(signal.SIGTERM)

    def handler(signum, frame):
        _remove_own_tmp()
        if callable(prev) and prev not in (signal.SIG_DFL, signal.SIG_IGN):
            return prev(signum, frame)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, handler)


def save(path, target, entries):
    _patient(_save_once, path, target, entries)


def _save_once(path, target, entries):
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
    mark = len(_TMP_MADE)
    try:
        return TARGETS[target]["check"](entry)
    finally:
        _drop_tmp_since(mark)


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
    _patient(_write_arcs_once, target, rows)


def _write_arcs_once(target, rows):
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
    _patient(_record_run_once, record)


def _record_run_once(record):
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
        "slow": len(session.slow),
        "technique": TARGETS.get(target, {}).get("technique", "mutation"),
        "outcomes": dict(session.outcomes),
        "slowest_ms": round(session.slowest[0] * 1000),
        "slowest": session.slowest[1],
        "seconds": round(seconds, 1),
        "stopped": getattr(session, "stopped", None),
    }
    rig = os.environ.get("HP_DE_DUST_RIG")
    if rig:
        record["rig"] = rig
    # The box's memory as the run ended, so the fleet's floors (Q120)
    # read from the ledger: what was available, and this process's
    # peak (ru_maxrss is KiB on Linux, bytes on macOS).
    avail = memory_available_mb()
    if avail is not None:
        record["mem_available_mb"] = avail
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        record["peak_rss_mb"] = int(peak / 1024) if sys.platform != "darwin" \
            else int(peak / (1024 * 1024))
    except (ImportError, AttributeError, OSError, ValueError):
        pass
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
        self.slow = []             # (entry, Crash("slow", ...)) (de_dust2)
        self.slowest = (0.0, None)
        self.outcomes = {"accepted": 0, "refused": 0, "crash": 0, "slow": 0}
        self.tried = 0
        self.stopped = None        # why the last grow ended, if early
        self.mutators_tried = {}
        self.mutator_errors = {}
        self.mutators_kept = {}
        # de_dust2: what each entry reaches and whether the reader
        # took it, for the parent choice; and the slow bound, set
        # from the corpus replay's median.
        self.hits = {}
        self.accepted_ids = set()
        self.median = None
        self.slow_bound = None
        # Parents that produced a slow child this grow, id -> factor.
        # Applied in parent_weights, so the recount keeps it. The
        # live weight list is cut in the same turn (de_dust2).
        self.slow_parents = {}

    def run(self, entry, trace=True, remember=True):
        """(outcome, new_arcs, seconds) of one entry; a Crash is
        recorded and reported as the outcome "crash". A try over the
        slow bound (set after the baseline: SLOW_FACTOR times the
        corpus replay's median, and at least SLOW_FLOOR_SEC) is the
        outcome "slow", recorded apart from the crashes (de_dust2).
        `remember` stores the arcs this entry reached. A grow passes
        False and stores them only for a child it keeps (Q120): a
        discarded try's hit set is otherwise still here at the end of
        the slice, and a long slice is tens of thousands of them."""
        t0 = time.perf_counter()
        try:
            if trace:
                outcome = self.tracer.run(check, self.target, entry)
                new = self.tracer.new
                if remember:
                    self.hits[entry["id"]] = frozenset(self.tracer.hit)
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
        if outcome == "accepted" and remember:
            self.accepted_ids.add(entry["id"])
        if (outcome != "crash" and self.slow_bound is not None
                and dt > self.slow_bound):
            # A try over the bound is run twice more, untraced, and
            # the best time stands: a core stolen by a neighbour for
            # one try is the box's slowness, not the reader's.
            for _ in range(2):
                t1 = time.perf_counter()
                try:
                    check(self.target, entry)
                except Crash:
                    pass
                dt = min(dt, time.perf_counter() - t1)
        if (outcome != "crash" and self.slow_bound is not None
                and dt > self.slow_bound):
            crash = Crash("slow", f"{dt * 1000:.0f} ms, "
                          f"{dt / max(self.median, 1e-9):.0f}x the corpus "
                          f"median of {self.median * 1000:.1f} ms")
            crash.seconds = dt
            self.slow.append((entry, crash))
            outcome = "slow"
        self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1
        return outcome, new, dt

    def baseline(self):
        """Replay the corpus under the tracer so growth measures
        against what the corpus already reaches, and set the slow
        bound from the replay's median (de_dust2)."""
        times = []
        for e in self.entries:
            times.append(self.run(e)[2])
        if times:
            times.sort()
            self.median = times[len(times) // 2]
            self.slow_bound = max(slow_floor(self.target),
                                  SLOW_FACTOR * self.median)

    def distill(self):
        """A minimal corpus that reaches every arc the whole corpus
        reaches (de_dust2). Greedy set cover: the seeds are pinned
        (the readable baseline and the hand-written coverage), then
        the grown entry covering the most still-uncovered arcs is
        added until nothing new is covered, the smaller entry winning
        a tie so the kept corpus is fast for CI to replay. Returns
        (kept, dropped); call after baseline() so self.hits is
        filled. The kept entries' arcs equal the whole corpus's, by
        construction."""
        full = set()
        for e in self.entries:
            full |= self.hits.get(e["id"], frozenset())
        kept, covered = [], set()
        for e in self.entries:
            if e.get("mutator") == "seed":
                kept.append(e)
                covered |= self.hits.get(e["id"], frozenset())
        pool = [e for e in self.entries if e.get("mutator") != "seed"]

        def size(e):
            return len(json.dumps(e.get("data"), ensure_ascii=True,
                                  default=str))

        while covered != full:
            best, best_gain, best_size = None, 0, None
            for e in pool:
                gain = len(self.hits.get(e["id"], frozenset()) - covered)
                if gain == 0:
                    continue
                esize = size(e)
                if gain > best_gain or (gain == best_gain
                                        and best_size is not None
                                        and esize < best_size):
                    best, best_gain, best_size = e, gain, esize
            if best is None:
                break
            kept.append(best)
            covered |= self.hits.get(best["id"], frozenset())
            pool.remove(best)
        order = {e["id"]: i for i, e in enumerate(self.entries)}
        kept.sort(key=lambda e: order[e["id"]])
        kept_ids = {e["id"] for e in kept}
        dropped = [e for e in self.entries if e["id"] not in kept_ids]
        self._distill_full = full
        self._distill_covered = covered
        return kept, dropped

    def accepted_share(self):
        """The share of the corpus the reader accepts, from the last
        replay; None before one."""
        if not self.entries or not self.hits:
            return None
        return len(self.accepted_ids & {e["id"] for e in self.entries}) \
            / len(self.entries)

    def parent_weights(self):
        """One weight per corpus entry (de_dust2, P3): the AFL favored
        rule in two terms. An entry weighs one over the number of
        entries reaching its rarest arc, so the entries that alone
        hold an arc are mutated most; and on a target where the reader
        accepts under ACCEPT_LOW of the corpus, an accepted entry
        weighs ACCEPT_BOOST times a refused one, so the children reach
        past the first gate. Entries without a recorded run weigh as
        the median entry does. None when nothing is recorded."""
        if not self.hits:
            return None
        count = {}
        for e in self.entries:
            for arc in self.hits.get(e["id"], ()):
                count[arc] = count.get(arc, 0) + 1
        share = self.accepted_share()
        boost = share is not None and share < ACCEPT_LOW
        weights = []
        known = []
        for e in self.entries:
            hit = self.hits.get(e["id"])
            if not hit:
                weights.append(None)
                continue
            rarest = min(count[arc] for arc in hit)
            w = 1.0 / rarest
            if boost and e["id"] in self.accepted_ids:
                w *= ACCEPT_BOOST
            weights.append(w)
            known.append(w)
        if not known:
            return None
        known.sort()
        fill = known[len(known) // 2]
        out = [fill if w is None else w for w in weights]
        if self.slow_parents:
            out = [w * self.slow_parents.get(e["id"], 1.0)
                   for w, e in zip(out, self.entries)]
        return out

    def grow(self, rng, rounds, log=None, history=None, archive=None,
             uniform_parents=False, budget_sec=None, clock=None):
        """Mutate from the corpus for `rounds` children; keep each one
        that reaches a new arc. Returns the entries added. `history`
        is {name: (tried, kept)} from earlier grows of this target,
        and with it the choice of mutator is steered toward the ones
        still finding arcs (Muse, 2026-10-26: saturation is per
        mutator). Parents are drawn by `parent_weights` (de_dust2,
        P3) unless `uniform_parents`. `archive`, when given, is called
        with a record of every child tried, kept or not. `budget_sec`,
        when given, is the slice's planned time: rounds are the
        estimate, and the grow stops once that time is spent so a
        rate that was a lie cannot hold the core past the slice. The
        first completed try always runs."""
        added = []
        self.tried = 0
        self.stopped = None
        self.mutators_tried = {}
        self.mutators_kept = {}
        if not self.entries:
            return added
        history = dict(history or {})
        weights = steering(history) if history else None
        parents = None if uniform_parents else self.parent_weights()
        self.mutator_errors = {}
        clock = clock or time.perf_counter
        started = clock()
        # `rounds` is tries: children the reader runs. A round whose
        # mutator declines, raises, or hands back a child the corpus
        # already holds costs microseconds and does not count, and a
        # run of MISS_STREAK such rounds in a row ends the grow as
        # "exhausted": the mutators cannot make anything new from
        # this corpus (a small structured script hands back a
        # duplicate on 99 rounds in 100). Counting misses as rounds
        # let a 2,400-second slice end in three seconds with 400
        # tries, and the tilt was never applied where it mattered.
        n = 0
        misses = 0
        while self.tried < rounds:
            n += 1
            if (budget_sec is not None and self.tried > 0
                    and clock() - started >= budget_sec):
                self.stopped = "budget"
                if log:
                    log(f"  slice budget {budget_sec:g}s spent; "
                        f"the grow stops")
                break
            if misses >= MISS_STREAK:
                self.stopped = "exhausted"
                if log:
                    log(f"  {MISS_STREAK} rounds in a row made no new "
                        f"child; the mutators are exhausted on this "
                        f"corpus and the grow stops")
                break
            if parents is not None:
                parent = rng.choices(self.entries, parents)[0]
            else:
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
                misses += 1
                continue
            if child is None:
                misses += 1
                continue
            data, name = child
            entry = make_entry(parent["kind"], data, parent["id"], name)
            if entry["id"] in self.ids:
                misses += 1
                continue
            misses = 0
            self.tried += 1
            self.mutators_tried[name] = self.mutators_tried.get(name, 0) + 1
            # The tracer's hit set is still this child's until the next
            # run. Copy it only when the child stays in the corpus.
            outcome, new, dt = self.run(entry, remember=False)
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
            if outcome == "slow":
                # One family for the rest of this grow. The factor
                # sticks on the session so the 200-try recount, which
                # rebuilds the list, keeps it. The live list is cut
                # now: waiting out two hundred slow tries has already
                # spent the slice.
                self.slow_parents[parent["id"]] = (
                    self.slow_parents.get(parent["id"], 1.0)
                    * SLOW_PARENT_DISCOUNT)
                if parents is not None:
                    for i, held in enumerate(self.entries):
                        if held is parent and i < len(parents):
                            parents[i] *= SLOW_PARENT_DISCOUNT
                            break
                if log:
                    log(f"  slow at round {n}: {self.slow[-1][1]}")
                continue
            tried, kept = history.get(name, (0, 0))
            history[name] = (tried + 1, kept + (1 if new else 0))
            if new:
                self.hits[entry["id"]] = frozenset(self.tracer.hit)
                if outcome == "accepted":
                    self.accepted_ids.add(entry["id"])
                entry["arcs"] = new
                self.entries.append(entry)
                self.ids.add(entry["id"])
                added.append(entry)
                if parents is not None:
                    # A keeper holds arcs nothing else does: the top
                    # weight until the next recount.
                    parents.append(max(parents) if parents else 1.0)
                self.mutators_kept[name] = self.mutators_kept.get(name, 0) + 1
                if log:
                    log(f"  +{new:3d} arcs  {name:14s} {entry['id']}  "
                        f"({outcome})")
            if self.tried % 200 == 0:
                if weights is not None:
                    weights = steering(history)
                if parents is not None:
                    parents = self.parent_weights()
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
    """The targets an argument names: all, one, or a comma list
    (de_dust2: a rig's lane is a list)."""
    if arg in (None, "all"):
        return list(TARGETS)
    names = [a.strip() for a in str(arg).split(",") if a.strip()]
    for name in names:
        if name not in TARGETS:
            sys.exit(f"unknown target {name!r}; one of {', '.join(TARGETS)}")
    return names or list(TARGETS)


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
                           "%Y-%m-%d"),
                       # The tree the grow ran (Q108): a retired id
                       # found again on a head at or before its fix is
                       # an echo; on a head after it, a regression.
                       "head": head_sha()[:12]})
        if record["id"] in known:
            continue
        known.add(record["id"])
        existing.append(record)
        fresh += 1
        out(f"  CRASH {target} {record['id']}: {crash}")
    if fresh:
        save(path, target, existing)
        out(f"  {fresh} crash(es) written to {_shown(path)}")
    return fresh


def _record_slow(target, session, out):
    """The grow's slow findings (de_dust2, P4) to <target>.slow.jsonl:
    the entry as tried, its time against the corpus median, the day
    and the tree. Apart from the crash file on purpose: a time is a
    property of the box, so a slow record is a Q to file and a bound
    for the desk to write, never an expectedFailure probe that a fast
    runner would pass by accident. The id is the entry's, so the bank
    unions the file as it unions a corpus."""
    if not session.slow:
        return 0
    path = corpus_path(target, slow=True)
    existing = load(path)
    known = {e["id"] for e in existing}
    fresh = 0
    # The slowest SLOW_PER_GROW of a grow, not every try over the
    # bound: one shape over the floor would otherwise file dozens of
    # near-copies a grow.
    slowest = sorted(session.slow, key=lambda ec: -getattr(ec[1], "seconds", 0.0))
    for entry, crash in slowest[:SLOW_PER_GROW]:
        record = dict(entry)
        record.update({"crash": crash.kind, "detail": crash.detail,
                       "median_ms": round((session.median or 0) * 1000, 1),
                       "found": datetime.now(timezone.utc).strftime(
                           "%Y-%m-%d"),
                       "head": head_sha()[:12]})
        if record["id"] in known:
            continue
        known.add(record["id"])
        existing.append(record)
        fresh += 1
        out(f"  SLOW {target} {record['id']}: {crash}")
    if fresh:
        save(path, target, existing)
        out(f"  {fresh} slow finding(s) written to {_shown(path)}")
    return fresh


def _shown(path):
    """A path for a progress line: relative to the repo when it can
    be, else as given. On Windows a corpus on another drive than the
    checkout (a temp dir on C: under a D: workspace) has no relative
    path, and os.path.relpath raises ValueError rather than print."""
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path


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
                  no_steer=False, rounds_for=None, uniform_parents=False,
                  budget_for=None):
    """One `grow` subprocess command per target, for --jobs.
    `rounds_for(target)`, when given, names each target's rounds
    (de_dust2 slices) in place of the one `rounds`. `budget_for`
    names the slice's seconds, which the child spends as a wall
    budget rather than as a round count."""
    out = []
    for target in targets:
        n = rounds_for(target) if rounds_for else rounds
        cmd = [sys.executable, os.path.abspath(__file__), "grow",
               "--target", target, "--rounds", str(n),
               "--seed", str(seed), "--jobs", "1"]
        if budget_for:
            b = budget_for(target)
            if b is not None:
                cmd += ["--budget-sec", f"{float(b):.6g}"]
        if verbose:
            cmd.append("--verbose")
        if archive:
            cmd += ["--archive", archive]
        if uniform_parents:
            cmd.append("--uniform-parents")
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
                 clock=time.monotonic, nap=0.2, requeue=None,
                 floor_sec=None):
    """Run the commands `jobs` at a time, launching the next the moment
    any one finishes, so every core stays busy; each command's output
    is printed whole when it finishes. With `minutes` > 0 the list is
    cycled -- a finished command goes back on the queue -- until the
    time is up, and nothing new is started after that; what is
    running finishes. A command carrying `--budget-sec` is launched
    with no more budget than the minutes have left, and not at all
    with less than `floor_sec` left: a slice tilted to four times a
    600-second base is forty minutes, and a cycle of 55 that let it
    start at minute 54 ran to minute 94 and pulled its rules an hour
    late. Returns the worst exit status. `spawn` is subprocess.Popen
    unless a test hands in its own."""
    import subprocess
    spawn = spawn or (lambda cmd: subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
    deadline = clock() + minutes * 60.0 if minutes else None
    pending = list(commands)
    running = []
    status = 0

    def clipped(target, cmd):
        """The command, its budget clipped to the time left; None
        when less than the floor is left and the command has a
        budget to clip."""
        if deadline is None or "--budget-sec" not in cmd:
            return cmd
        left = deadline - clock()
        planned = float(cmd[cmd.index("--budget-sec") + 1])
        if planned <= left:
            return cmd
        if floor_sec is not None and left < floor_sec:
            out(f"{CAMPAIGN} slice: {target} not started, {left:.0f} s "
                f"left of the cycle, under the {floor_sec:.0f} s floor")
            return None
        out(f"{CAMPAIGN} slice: {target} clipped to {left:.0f} s, the "
            f"cycle's remainder, from {planned:.0f} s")
        return _set_budget(cmd, max(1.0, left))

    def _drain(proc):
        """A reader thread for the child's stdout, so a child that
        writes more than the pipe holds never blocks on the write
        while the parent polls (Q122, Muse's Menlo Park stall). The
        bytes are collected for the whole-output print at the end.
        A fake process without a pipe is left to communicate()."""
        stream = getattr(proc, "stdout", None)
        if stream is None or not hasattr(stream, "read"):
            return None
        chunks = []

        def pump():
            try:
                for chunk in iter(lambda: stream.read(65536), b""):
                    chunks.append(chunk)
            except (OSError, ValueError):
                pass
        t = threading.Thread(target=pump, daemon=True)
        t.start()
        return t, chunks

    while pending or running:
        while pending and len(running) < max(1, jobs) and (
                deadline is None or clock() < deadline):
            target, cmd = pending.pop(0)
            cmd = clipped(target, cmd)
            if cmd is None:
                continue
            proc = spawn(cmd)
            running.append((target, cmd, proc, _drain(proc)))
        finished = [r for r in running if r[2].poll() is not None]
        if not finished:
            if not running:
                break
            time.sleep(nap)
            continue
        for item in finished:
            running.remove(item)
            target, cmd, proc, drain = item
            if drain is not None:
                drain[0].join()
                proc.wait()
                output = b"".join(drain[1])
            else:
                output, _ = proc.communicate()
            text = output.decode("utf-8", "replace") if isinstance(
                output, bytes) else (output or "")
            for line in text.rstrip().splitlines():
                out(line)
            status = max(status, proc.returncode or 0)
            if deadline is not None and clock() < deadline:
                nxt = _next_seed(cmd)
                if requeue is not None:
                    nxt = requeue(target, nxt)
                pending.append((target, nxt))
    return status


def _next_seed(cmd):
    """The same command with its --seed moved on by one, so a cycled
    target draws new children instead of the last cycle's."""
    cmd = list(cmd)
    if "--seed" in cmd:
        i = cmd.index("--seed") + 1
        cmd[i] = str(int(cmd[i]) + 1)
    return cmd


def _set_rounds(cmd, rounds):
    """The same command with its --rounds set (de_dust2 slices)."""
    cmd = list(cmd)
    if "--rounds" in cmd:
        cmd[cmd.index("--rounds") + 1] = str(int(rounds))
    else:
        cmd += ["--rounds", str(int(rounds))]
    return cmd


def _set_budget(cmd, seconds):
    """The same command with its --budget-sec set to the slice's
    planned seconds."""
    cmd = list(cmd)
    text = f"{float(seconds):.6g}"
    if "--budget-sec" in cmd:
        cmd[cmd.index("--budget-sec") + 1] = text
    else:
        cmd += ["--budget-sec", text]
    return cmd


def memory_available_mb():
    """MemAvailable in MiB, or None where the kernel does not report
    it. The rigs read the floors from this number; the tool only
    says it."""
    try:
        fh = open("/proc/meminfo", encoding="ascii", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            if line.startswith("MemAvailable:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1]) // 1024
    return None


def footprint_line(target, entries):
    """What a lane holds before it mutates (Q120). Hit sets follow
    the entries loaded, not the tries. The available-memory suffix
    is present only where the kernel reports it."""
    path = corpus_path(target)
    try:
        nbytes = os.path.getsize(path)
    except OSError:
        nbytes = 0
    line = (f"{target}: corpus {len(entries)} entries, {nbytes} bytes; "
            f"hit sets follow the entries, not the tries")
    avail = memory_available_mb()
    if avail is not None:
        line += f"; MemAvailable {avail} MB"
    return line


def cmd_grow(args, out=print):
    sweep_dead_grow_temps()
    _arm_term_cleanup()
    for target in _targets(args.target):
        prune_retired_crashes(target, out)
    return _cmd_grow(args, out)


def _cmd_grow(args, out=print):
    rounds = args.rounds
    seed = args.seed if args.seed is not None else \
        int.from_bytes(os.urandom(4), "big")
    targets = _targets(args.target)
    minutes = getattr(args, "minutes", 0) or 0
    # de_dust2 (P1, P2): under --minutes a target's rounds come from
    # its time slice and its measured rate, tilted by its yield,
    # unless --rounds names a fixed count.
    slice_sec = getattr(args, "slice", None)
    if slice_sec is None and minutes and rounds is None:
        slice_sec = float(os.environ.get("HP_DE_DUST_SLICE", DEFAULT_SLICE_SEC))
    if rounds is None:
        rounds = int(os.environ.get("HP_DE_DUST_ROUNDS", DEFAULT_ROUNDS))
    if minutes and len(targets) > 1 and getattr(args, "order", "stale") != "fixed":
        targets = stale_order(targets)
        out("de_dust grow: targets by staleness, least recently grown "
            "first: " + ", ".join(targets[:4]) + (", ..." if len(targets) > 4 else ""))
    if (args.jobs > 1 and len(targets) > 1) or minutes:
        # Each target owns its corpus file, so the targets grow in
        # parallel processes: on the rig that is the difference
        # between one core busy and all of them. With --minutes the
        # targets cycle until the time is up: the continuous grow
        # that fills the gap between a measure and a pass.
        rounds_for = None
        requeue = None
        if slice_sec:
            plan = slice_plan(targets, slice_sec)
            for tg in targets:
                row = plan[tg]
                out(f"{CAMPAIGN} slice: {tg} {row['tilt']:.2f}x -> "
                    f"{row['seconds']:.0f} s, {row['rounds']} rounds"
                    + (f" at {row['rate']:.0f}/s" if row["rate"] else
                       " (no rate on record)"))
            # The decision, on the record: what each target was given
            # at the start of this cycling grow and why, so the next
            # reader of the ledger sees the schedule, not only its
            # effects (de_dust2 P10).
            plan_record = {
                "kind": "plan", "slice": slice_sec, "minutes": minutes,
                "jobs": min(args.jobs, len(targets)),
                "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "head": head_sha()[:12],
                "targets": {tg: {"tilt": round(plan[tg]["tilt"], 2),
                                 "seconds": round(plan[tg]["seconds"]),
                                 "rounds": plan[tg]["rounds"],
                                 "rate": (round(plan[tg]["rate"], 1)
                                          if plan[tg]["rate"] else None),
                                 "yield": plan[tg]["yield"],
                                 "technique": TARGETS[tg].get("technique", "mutation")}
                            for tg in targets}}
            rig = os.environ.get("HP_DE_DUST_RIG")
            if rig:
                plan_record["rig"] = rig
            record_run(plan_record)
            rounds_for = lambda tg: plan[tg]["rounds"]  # noqa: E731
            budget_for = lambda tg: plan[tg]["seconds"]  # noqa: E731

            def requeue(tg, cmd):
                # The ledger has this grow's record by now: the rate
                # and the yield move the next slice.
                row = slice_plan([tg], slice_sec)[tg]
                out(f"{CAMPAIGN} slice: {tg} {row['tilt']:.2f}x -> "
                    f"{row['seconds']:.0f} s, {row['rounds']} rounds")
                return _set_budget(_set_rounds(cmd, row["rounds"]),
                                   row["seconds"])
        else:
            budget_for = None
        out(f"de_dust grow: {'time slices of %g s' % slice_sec if slice_sec else '%d rounds' % rounds}, "
            f"rng seed {seed}, {min(args.jobs, len(targets))} targets at a time"
            + (f", for {minutes:g} minutes" if minutes else ""))
        return run_parallel(grow_commands(targets, rounds, seed,
                                          args.verbose,
                                          getattr(args, "archive", None),
                                          getattr(args, "no_steer", False),
                                          rounds_for=rounds_for,
                                          uniform_parents=getattr(
                                              args, "uniform_parents", False),
                                          budget_for=budget_for),
                            args.jobs, out=out, minutes=minutes,
                            requeue=requeue,
                            floor_sec=(slice_sec * TILT_FLOOR
                                       if slice_sec else None))
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
        # Before the replay. Flushed: a kill mid-grow still leaves
        # the line in the pipe, which is the trace the breadth lane
        # did not have (Q120).
        out(footprint_line(target, session.entries))
        if out is print:
            sys.stdout.flush()
        for e in fresh:
            e["arcs"] = 0
        t0 = time.perf_counter()
        no_steer = getattr(args, "no_steer", False)
        where = getattr(args, "archive", None)
        history = None if no_steer else mutator_history(target)
        archive = Archive(where, target, seed) if where else None

        uniform = getattr(args, "uniform_parents", False)
        budget = getattr(args, "budget_sec", None)

        def work():
            session.baseline()
            # The slice's seconds cover the replay and the mutation.
            # Rounds remain the estimate; the remainder is the budget.
            remain = None
            if budget is not None:
                remain = budget - (time.perf_counter() - t0)
            before = len(session.tracer.arcs)
            added = session.grow(rng, rounds, log=out if args.verbose
                                 else None, history=history,
                                 archive=archive.add if archive else None,
                                 uniform_parents=uniform,
                                 budget_sec=remain)
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
        if not uniform:
            extra["parents"] = "rarity"
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
            f"{session.outcomes['crash']} crashes, "
            f"{session.outcomes.get('slow', 0)} slow, slowest "
            f"{session.slowest[0] * 1000:.0f} ms ({session.slowest[1]})")
        if _with_rig(lambda: _record_crashes(target, session, out)):
            status = 1
        _with_rig(lambda: _record_slow(target, session, out))
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
    if TARGETS[target].get("technique") == "race":
        # A thread schedule is not a surface: the same entry can end
        # two ways on one box, and that is the technique, not a
        # disagreement.
        return []
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
        if moved or redundant:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            head = head_sha()[:12]
            retired = load_retired(target)
            for e in moved:
                retired[e["id"]] = {"on": today, "why": "promoted", "head": head}
            for e in redundant:
                retired[e["id"]] = {"on": today, "why": "redundant", "head": head}
            save_retired(target, retired)
        out(f"{target}: {len(moved)} promoted, {len(redundant)} redundant "
            f"(fixed, reaching nothing new), {len(keep)} still crash")
        if keep:
            status = 1
    for target in _targets(args.target):
        if _promote_slow(target, out):
            status = 1
    return status


def slow_floor(target):
    """The least time a try must take to be filed slow for `target`:
    SLOW_FLOOR_SEC, or the target's own `slow_floor_sec` where its
    reader runs a sender's input under a deadline of its own."""
    own = TARGETS.get(target, {}).get("slow_floor_sec") or 0.0
    return max(SLOW_FLOOR_SEC, float(own))


def _promote_slow(target, out):
    """The slow findings on file (de_dust2, P4), replayed after a
    fix: a record that now runs under half the slow floor (the best
    of three untraced runs) is fast, retired as such, and gone from
    `<target>.slow.jsonl`; one still over the floor stays. A time is
    the box's, so this is the promoting box's reading, and the
    retirement names its head like any other. Returns True when some
    record is still slow."""
    path = corpus_path(target, slow=True)
    records = load(path)
    if not records:
        return False
    fast, still = [], []

    def work():
        for record in records:
            entry = {k: record[k] for k in
                     ("id", "kind", "data", "from", "mutator", "arcs")}
            best = None
            for _ in range(3):
                t0 = time.perf_counter()
                try:
                    check(target, entry)
                except Crash:
                    pass
                dt = time.perf_counter() - t0
                best = dt if best is None else min(best, dt)
            (fast if best < slow_floor(target) / 2 else still).append((record, best))
    _with_rig(work)
    if fast:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        head = head_sha()[:12]
        retired = load_retired(target)
        for record, best in fast:
            retired[record["id"]] = {"on": today, "why": "fast", "head": head,
                                     "ms": round(best * 1000, 1)}
        save_retired(target, retired)
    if still:
        save(path, target, [r for r, _ in still])
    else:
        os.remove(path)
    out(f"{target}: {len(fast)} slow finding(s) now fast (retired), "
        f"{len(still)} still slow")
    return bool(still)


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


def stale_order(targets, runs=None):
    """The targets least recently grown first (Q107). A cycling grow
    on a rig (`--minutes`) used to start every cycle at the head of
    the list, so a one-core box with a thirty-minute cycle grew the
    first five targets over and over and the rest never; and two rigs
    on the same list spent the hour on the same targets. Ordering by
    the newest run record (seed or grow) across the merged
    `runs.jsonl` makes every cycle continue where the campaign is
    thinnest, and two rigs that read the same ledger pick apart as
    soon as one of them banks. A target never run comes first; ties
    keep the list's order."""
    if runs is None:
        runs = load_runs()
    newest = {}
    for record in runs:
        target = record.get("target")
        when = str(record.get("when", ""))
        if target in targets and when > newest.get(target, ""):
            newest[target] = when
    return sorted(targets, key=lambda tg: (newest.get(tg, ""),
                                           list(targets).index(tg)))


def _target_records(target, runs=None, kinds=("grow",)):
    """A target's run records of the given kinds, oldest first by the
    time each ran (the records of several lanes merge in commit
    order, not time order)."""
    recs = load_runs() if runs is None else runs
    return sorted((r for r in recs
                   if r.get("kind") in kinds and r.get("target") == target),
                  key=lambda r: str(r.get("when", "")))


def target_rate(target, runs=None, grows=5):
    """Tries per second over a target's last `grows` grow records, or
    None with no record (de_dust2, P1)."""
    recs = _target_records(target, runs)[-grows:]
    tried = sum(int(r.get("tried") or 0) for r in recs)
    seconds = sum(float(r.get("seconds") or 0) for r in recs)
    if tried <= 0 or seconds <= 0:
        return None
    return tried / seconds


def target_yield(target, runs=None, grows=5):
    """(yield, fresh) for a target (de_dust2, P2): yield is the
    entries kept plus the arcs gained over its last `grows` grows
    since its newest seed record, and fresh says fewer than `grows`
    grows have run since that seed (or ever), so the target has not
    had its full look yet."""
    recs = _target_records(target, runs, kinds=("grow", "seed"))
    cut = 0
    for i, r in enumerate(recs):
        if r.get("kind") == "seed":
            cut = i + 1
    grows_since = [r for r in recs[cut:] if r.get("kind") == "grow"]
    recent = grows_since[-grows:]
    total = 0
    for r in recent:
        total += len(r.get("kept") or [])
        total += max(0, int(r.get("arcs_after") or 0)
                     - int(r.get("arcs_before") or 0))
    return total, len(grows_since) < grows


YIELD_WINDOW_SEC = 3600.0     # the run time a target's yield is read over


def target_yield_per_slice(target, base_seconds, runs=None, grows=5,
                           window_seconds=YIELD_WINDOW_SEC):
    """(yield, fresh) as target_yield, with the yield projected onto
    one base slice and read over a window of run time: the count over
    the target's newest grows that together ran at least
    `window_seconds` (and at least `grows` of them), per second they
    ran, times `base_seconds`. A raw count over a fixed number of
    grows feeds back on itself twice -- a target on a long slice
    keeps more per grow and stays long, and its five grows are hours
    of evidence while a floor target's five are minutes -- whatever
    each returns per CPU-second (30-OCT: dtls_hostile at the floor on
    108 kept per CPU-hour, v2_mail at 2x on four stray arcs).
    Projected over a window of time, the tilt reads the rate and the
    slice length drops out."""
    recs = _target_records(target, runs, kinds=("grow", "seed"))
    cut = 0
    for i, r in enumerate(recs):
        if r.get("kind") == "seed":
            cut = i + 1
    grows_since = [r for r in recs[cut:] if r.get("kind") == "grow"]
    recent = []
    span = 0.0
    for r in reversed(grows_since):
        if len(recent) >= grows and span >= window_seconds:
            break
        recent.append(r)
        span += float(r.get("seconds") or 0)
    total = 0
    seconds = 0.0
    for r in recent:
        total += len(r.get("kept") or [])
        total += max(0, int(r.get("arcs_after") or 0)
                     - int(r.get("arcs_before") or 0))
        seconds += float(r.get("seconds") or 0)
    projected = total / seconds * base_seconds if seconds > 0 else float(total)
    return projected, len(grows_since) < grows


def slice_tilt(yield_, fresh):
    """The multiple of the base slice a target earns: a quarter with
    no yield, one plus a quarter per entry or arc up to TILT_MAX, and
    at least one for a target still owed its first look."""
    tilt = TILT_FLOOR if yield_ <= 0 else min(TILT_MAX, 1.0 + yield_ / 4.0)
    if fresh:
        tilt = max(1.0, tilt)
    return tilt


def slice_plan(targets, base_seconds, runs=None):
    """{target: {tilt, seconds, rounds, rate, yield}} for one cycle
    (de_dust2, P1 and P2): each target's rounds are its tilted slice
    times its measured rate, clamped, or SLICE_FIRST_ROUNDS with no
    rate on record."""
    runs = load_runs() if runs is None else runs
    plan = {}
    for target in targets:
        rate = target_rate(target, runs)
        got, fresh = target_yield_per_slice(target, base_seconds, runs)
        tilt = slice_tilt(got, fresh)
        seconds = base_seconds * tilt
        if rate is None:
            rounds = SLICE_FIRST_ROUNDS
        else:
            rounds = int(min(SLICE_MAX_ROUNDS,
                             max(SLICE_MIN_ROUNDS, seconds * rate)))
        plan[target] = {"tilt": tilt, "seconds": seconds, "rounds": rounds,
                        "rate": rate, "yield": round(got, 1)}
    return plan


def yield_table(hours=48, runs=None, now=None):
    """Per-target rows over the last `hours` of grow records (de_dust2,
    P10): cpu_h, tries per second, kept, arcs gained, accepted share,
    kept per CPU-hour; rows by CPU spent, then a fleet row."""
    runs = load_runs() if runs is None else runs
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = {}
    for r in runs:
        if r.get("kind") != "grow" or str(r.get("when", "")) < since:
            continue
        row = rows.setdefault(r.get("target"), {
            "runs": 0, "seconds": 0.0, "tried": 0, "kept": 0, "arcs": 0,
            "accepted": 0, "refused": 0, "crashes": 0, "slow": 0})
        row["runs"] += 1
        row["seconds"] += float(r.get("seconds") or 0)
        row["tried"] += int(r.get("tried") or 0)
        row["kept"] += len(r.get("kept") or [])
        row["arcs"] += max(0, int(r.get("arcs_after") or 0)
                           - int(r.get("arcs_before") or 0))
        o = r.get("outcomes") or {}
        row["accepted"] += int(o.get("accepted") or 0)
        row["refused"] += int(o.get("refused") or 0)
        row["crashes"] += int(o.get("crash") or 0)
        row["slow"] += int(o.get("slow") or 0)
    out = []
    for target, row in sorted(rows.items(), key=lambda kv: -kv[1]["seconds"]):
        out.append(_yield_row(target, row))
    keys = ("runs", "seconds", "tried", "kept", "arcs", "accepted",
            "refused", "crashes", "slow")
    # One row per technique, so the fleet's spread across mutation,
    # protocol and race fuzzing is read in one line each.
    by_technique = {}
    for target, row in rows.items():
        name = TARGETS.get(target, {}).get("technique", "mutation")
        acc = by_technique.setdefault(name, {k: 0 for k in keys})
        for k in keys:
            acc[k] += row[k]
    for name in sorted(by_technique):
        out.append(_yield_row("~" + name, by_technique[name]))
    # One row per rig, from the records that name one, so compute
    # from different places is read as the places it came from.
    by_rig = {}
    for r in runs:
        if r.get("kind") != "grow" or str(r.get("when", "")) < since or not r.get("rig"):
            continue
        acc = by_rig.setdefault(r["rig"], {k: 0 for k in keys})
        acc["runs"] += 1
        acc["seconds"] += float(r.get("seconds") or 0)
        acc["tried"] += int(r.get("tried") or 0)
        acc["kept"] += len(r.get("kept") or [])
        acc["arcs"] += max(0, int(r.get("arcs_after") or 0) - int(r.get("arcs_before") or 0))
        o = r.get("outcomes") or {}
        acc["accepted"] += int(o.get("accepted") or 0)
        acc["refused"] += int(o.get("refused") or 0)
        acc["crashes"] += int(o.get("crash") or 0)
        acc["slow"] += int(o.get("slow") or 0)
    for name in sorted(by_rig):
        out.append(_yield_row("@" + name, by_rig[name]))
    fleet = {k: sum(r[k] for r in rows.values()) for k in keys} if rows else None
    if fleet:
        out.append(_yield_row("fleet", fleet))
    return out


def _yield_row(target, row):
    cpu_h = row["seconds"] / 3600.0
    tries = row["accepted"] + row["refused"]
    return {"target": target, "runs": row["runs"], "cpu_h": cpu_h,
            "tries_per_s": row["tried"] / row["seconds"] if row["seconds"] else 0.0,
            "kept": row["kept"], "arcs": row["arcs"],
            "accepted_share": row["accepted"] / tries if tries else 0.0,
            "crashes": row["crashes"], "slow": row["slow"],
            "kept_per_cpu_h": row["kept"] / cpu_h if cpu_h else 0.0}


def format_yield(rows, hours):
    lines = [f"{CAMPAIGN} yield, last {hours:g} h: {'target':12} {'runs':>4} "
             f"{'cpu_h':>6} {'tries/s':>7} {'kept':>4} {'arcs+':>5} "
             f"{'acc%':>4} {'crash':>5} {'slow':>4} {'kept/cpu_h':>10}"]
    for r in rows:
        lines.append(f"{'':24} {r['target']:12} {r['runs']:4d} "
                     f"{r['cpu_h']:6.2f} {r['tries_per_s']:7.1f} "
                     f"{r['kept']:4d} {r['arcs']:5d} "
                     f"{r['accepted_share'] * 100:4.0f} {r['crashes']:5d} "
                     f"{r['slow']:4d} {r['kept_per_cpu_h']:10.2f}")
    return lines


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


def last_plan(runs=None):
    """The newest plan record in the ledger, or None."""
    plans = newest_plans(runs)
    return plans[-1] if plans else None


def newest_plans(runs=None):
    """Every plan tied for the newest timestamp.

    Two lanes write two plans at one moment. The later line in the
    file is not the newer plan, and a reading that keeps only one
    of them hides the lane with the long slices."""
    plans = [r for r in (load_runs() if runs is None else runs)
             if r.get("kind") == "plan"]
    if not plans:
        return []
    when = max(str(r.get("when", "")) for r in plans)
    return [r for r in plans if str(r.get("when", "")) == when]


def cmd_distill(args, out=print):
    """Trim each corpus to a minimal set that still reaches every arc
    it reaches now, so CI replays fewer entries as the corpus grows
    (de_dust2). A dry run by default: it reports what it would drop
    and proves the kept set covers the same arcs. With --write it
    rewrites the corpus file. Race targets are skipped -- their arc
    sets vary run to run, so a set cover over one replay is not
    sound. Crash and slow files are left alone."""
    status = 0
    for target in _targets(args.target):
        tech = TARGETS[target].get("technique")
        if tech == "race":
            out(f"{target}: skipped (a race target's arcs are not "
                "deterministic)")
            continue
        if tech == "parity":
            out(f"{target}: skipped (a parity target's coverage lives in "
                "the other implementation; there is no Python arc to cover)")
            continue
        entries = load(corpus_path(target))
        if not entries:
            out(f"{target}: empty")
            continue
        session = Session(target, entries)
        kept = dropped = None

        def work():
            nonlocal kept, dropped
            session.baseline()
            kept, dropped = session.distill()
        _with_rig(work)
        if session._distill_covered != session._distill_full:
            missing = len(session._distill_full - session._distill_covered)
            out(f"{target}: DID NOT COVER ({missing} arc(s) unreachable "
                "from the kept set); leaving it alone")
            status = 1
            continue
        seeds = sum(1 for e in kept if e.get("mutator") == "seed")
        out(f"{target}: {len(entries)} -> {len(kept)} entries "
            f"({seeds} seeds pinned, {len(kept) - seeds} grown kept, "
            f"{len(dropped)} dropped), {len(session._distill_full)} arcs held")
        if args.write and dropped:
            save(corpus_path(target), target, kept)
            record_run({"kind": "distill", "target": target,
                        "when": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"),
                        "head": head_sha()[:12],
                        "entries_before": len(entries),
                        "entries_after": len(kept),
                        "arcs": len(session._distill_full),
                        **({"rig": os.environ["HP_DE_DUST_RIG"]}
                           if os.environ.get("HP_DE_DUST_RIG") else {})})
    return status


def cmd_disk(args, out=print):
    """Put a number on a flickering disk: make, write, rename and
    remove `--writes` small files under the corpus directory (or
    --where), one try each, and report how many failed and with
    what errno. A healthy disk answers zero. For a rig that reports
    "operation not permitted" at random (Menlo Park, 30-OCT)."""
    where = args.where or CORPUS_DIR
    os.makedirs(where, exist_ok=True)
    failed = {}
    t0 = time.perf_counter()
    for i in range(args.writes):
        path = os.path.join(where, f".disk-probe-{os.getpid()}-{i}")
        try:
            with open(path + ".tmp", "w", encoding="utf-8") as fh:
                fh.write("x" * 512)
            os.replace(path + ".tmp", path)
            with open(path, encoding="utf-8") as fh:
                if len(fh.read()) != 512:
                    failed["short-read"] = failed.get("short-read", 0) + 1
            os.remove(path)
        except OSError as e:
            name = errno.errorcode.get(e.errno, str(e.errno))
            failed[name] = failed.get(name, 0) + 1
            for p in (path, path + ".tmp"):
                try:
                    os.remove(p)
                except OSError:
                    pass
    bad = sum(failed.values())
    out(f"disk probe at {where}: {args.writes} writes in "
        f"{time.perf_counter() - t0:.1f} s, {bad} failed"
        + (": " + ", ".join(f"{k} x{v}" for k, v in sorted(failed.items()))
           if failed else ""))
    return 1 if bad else 0


def hourly_note(runs=None, now=None, hours=24, rig=None, probe=True):
    """The hourly campaign note, as text, from the ledger and the box
    (de_dust2, for the rig seat): the 24-hour fleet line, the newest
    slice plan, the box's load and memory, what the last hour kept
    and filed, the mutators still finding arcs, and the disk probe.
    Everything a reader needs is in the ledger; this writes it in the
    note's shape so the hour is not assembled by hand."""
    runs = load_runs() if runs is None else runs
    now = now or datetime.now(timezone.utc)
    rows = {r["target"]: r for r in yield_table(hours, runs, now=now)}
    fleet = rows.get("fleet")
    out = []
    if fleet and fleet["cpu_h"]:
        out.append(f"In the last {hours} hours the fleet kept {fleet['kept']} "
                   f"entries and gained {fleet['arcs']} arcs over "
                   f"{fleet['cpu_h']:.2f} CPU-hours, at "
                   f"{fleet['kept_per_cpu_h']:.2f} kept per CPU-hour, with "
                   f"{fleet['crashes']} crash records and {fleet['slow']} slow "
                   "findings filed.")
    else:
        out.append(f"No grow in the last {hours} hours.")
    plans = newest_plans(runs)
    if len(plans) == 1:
        plan = plans[0]
        tg = sorted((plan.get("targets") or {}).items(),
                    key=lambda kv: -kv[1].get("seconds", 0))
        parts = [f"{name} at {row.get('seconds', 0):,} s with a "
                 f"{row.get('tilt', 0):.2f}x yield tilt" for name, row in tg]
        out.append(f"Slice plan: the newest plan, at {plan.get('when')}"
                   + (f" on {plan['rig']}" if plan.get("rig") else "")
                   + ", puts " + "; ".join(parts)
                   + f", {plan.get('jobs', 1)} at a time.")
    elif plans:
        sentences = []
        for plan in plans:
            tg = sorted((plan.get("targets") or {}).items(),
                        key=lambda kv: -kv[1].get("seconds", 0))
            parts = [f"{name} at {row.get('seconds', 0):,} s with a "
                     f"{row.get('tilt', 0):.2f}x yield tilt" for name, row in tg]
            sentences.append("one puts " + "; ".join(parts)
                             + f", {plan.get('jobs', 1)} at a time")
        head = plans[0]
        out.append(f"Slice plan: the newest plans, at {head.get('when')}"
                   + (f" on {head['rig']}" if head.get("rig") else "")
                   + ". " + " ".join(s[0].upper() + s[1:] + "." for s in sentences))
    loadavg = None
    try:
        loadavg = os.getloadavg()
    except (AttributeError, OSError):
        pass
    cores = os.cpu_count() or 1
    mem = memory_available_mb()
    if loadavg:
        out.append(f"CPU: load averages {loadavg[0]:.2f} over one minute and "
                   f"{loadavg[1]:.2f} over five on {cores} core(s), "
                   f"{loadavg[0] / cores * 100:.0f}% and {loadavg[1] / cores * 100:.0f}% "
                   f"of capacity" + (f"; {mem} MB available" if mem is not None else "") + ".")
    since = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hour = [r for r in runs if r.get("kind") == "grow" and str(r.get("when", "")) >= since
            and (rig is None or r.get("rig") == rig)]
    kept = sum(len(r.get("kept") or []) if isinstance(r.get("kept"), list)
               else int(r.get("kept") or 0) for r in hour)
    latest = {}
    for r in runs:
        if r.get("kind") in ("grow", "seed", "distill") and "entries_after" in r:
            latest[r["target"]] = r["entries_after"]
    out.append(f"Entries kept: {kept} in the last hour. The corpus totals "
               f"{sum(latest.values()):,} entries over {len(latest)} targets.")
    if hour:
        # How the hour's grows ended: on their budget (the slice ran
        # its seconds), on their rounds, or exhausted (the mutators
        # could make nothing new from that corpus, a finding of its
        # own). Records from before the field count as on rounds.
        ended = {"budget": 0, "exhausted": [], "rounds": 0}
        for r in hour:
            how = r.get("stopped")
            if how == "budget":
                ended["budget"] += 1
            elif how == "exhausted":
                ended["exhausted"].append(r.get("target", "?"))
            else:
                ended["rounds"] += 1
        tried = sum(int(r.get("tried") or 0) for r in hour)
        secs = sum(float(r.get("seconds") or 0) for r in hour)
        line = (f"Grows in the last hour: {len(hour)}, {tried:,} tries over "
                f"{secs / 3600:.2f} CPU-hours; {ended['budget']} ran their "
                f"budget out, {ended['rounds']} their rounds")
        if ended["exhausted"]:
            names = sorted(set(ended["exhausted"]))
            line += (f", and {len(ended['exhausted'])} ended exhausted, the "
                     f"mutators making nothing new from the corpus of "
                     f"{', '.join(names)}")
        out.append(line + ".")
    crashed = sorted({r["target"] for r in hour if (r.get("crashes") or 0) > 0})
    slowed = sorted({r["target"] for r in hour if (r.get("slow") or 0) > 0})
    out.append("Crashes filed: " + (f"{sum(1 for r in hour if (r.get('crashes') or 0) > 0)} "
               f"run record(s) in the last hour had crashes, on {', '.join(crashed)}."
               if crashed else "none in the last hour.")
               + (f" Slow findings on {', '.join(slowed)}." if slowed else " No slow finding."))
    standing = []
    for target in TARGETS:
        for flag, label in ((True, "crash"), (False, "slow")):
            path = corpus_path(target, crashes=flag, slow=not flag)
            n = len(load(path)) if os.path.exists(path) else 0
            if n:
                standing.append(f"{target} {n} {label}")
    out.append("Findings standing in the tree: " + (", ".join(standing) if standing
               else "none (every crash and slow file is retired or empty)")
               + ". The window counts above include records since retired.")
    live = {}
    for r in hour:
        for name, n in (r.get("mutators_kept") or {}).items():
            if n:
                live.setdefault(r["target"], set()).add(name)
    if live:
        out.append("Live mutators: " + "; ".join(
            f"{t} -- {', '.join(sorted(m))}" for t, m in sorted(live.items()))
            + ". Every other target in the hour: none.")
    else:
        out.append("Live mutators: none kept an arc in the last hour.")
    if probe:
        lines = []
        cmd_disk(argparse.Namespace(writes=100, where=None), out=lines.append)
        out.append(lines[0][0].upper() + lines[0][1:] + ".")
    return "\n\n".join(out)


def memory_total_mb():
    """MemTotal in MiB, or None off Linux."""
    try:
        fh = open("/proc/meminfo", encoding="ascii", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            if line.startswith("MemTotal:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1]) // 1024
    return None


def _temp_used_pct():
    """How full the temp volume is, or None when it is the corpus
    volume (one reading is enough) or it cannot be read.

    `HP_DE_DUST_TMP` is the volume the grow writes to when a rig
    sets it (Q126). Otherwise it is the process temp directory,
    and only when that is a different device from the corpus."""
    temp = os.environ.get("HP_DE_DUST_TMP") or tempfile.gettempdir()
    try:
        if os.stat(temp).st_dev == os.stat(CORPUS_DIR).st_dev:
            return None
        usage = shutil.disk_usage(temp)
    except OSError:
        return None
    if not usage.total:
        return None
    return usage.used / usage.total * 100.0


def grow_workers_live():
    """How many de_dust grow processes are running on this box, by
    their command lines (/proc; None where there is no /proc)."""
    try:
        pids = [n for n in os.listdir("/proc") if n.isdigit()]
    except OSError:
        return None
    me = str(os.getpid())
    live = 0
    for pid in pids:
        if pid == me:
            continue
        try:
            with open(os.path.join("/proc", pid, "cmdline"), "rb") as fh:
                argv = fh.read().split(b"\0")
        except OSError:
            continue
        if any(a.endswith(b"de_dust_corpus.py") for a in argv) and b"grow" in argv:
            live += 1
    return live


def watch_readings(runs=None, now=None, rig=None, disk_max=90.0, mem_min_mb=None,
                   stale_min=None, expect_workers=None, disk_used_pct=None,
                   mem_avail_mb=None, workers=None, temp_used_pct=None,
                   measure_temp=True):
    """The ten-minute watch (the rig seat's floors, Q120, and the
    stall shape, Q122), as (lines, breaches). Every reading can be
    handed in, for a test or another box's numbers; otherwise it is
    read here. The floors: disk used under `disk_max` percent, on
    the corpus volume and, when it is a different device, on the
    temp volume the bank and the grow write to (Q126); available
    memory over `mem_min_mb` (256 on a box of 4 GB or more, 128
    below, unless given); and, when a slice plan stands, grow
    workers live and a run record from this rig younger than
    `stale_min` (twice the plan's longest slice, 30 at least)."""
    runs = load_runs() if runs is None else runs
    now = now or datetime.now(timezone.utc)
    lines, breaches = [], []
    if disk_used_pct is None:
        try:
            usage = shutil.disk_usage(CORPUS_DIR)
            disk_used_pct = usage.used / usage.total * 100.0 if usage.total else None
        except OSError:
            disk_used_pct = None
    if disk_used_pct is not None:
        lines.append(f"disk: {disk_used_pct:.0f}% used of the corpus volume, "
                     f"line at {disk_max:.0f}%")
        if disk_used_pct >= disk_max:
            breaches.append(f"disk {disk_used_pct:.0f}% over the {disk_max:.0f}% line")
    if measure_temp and temp_used_pct is None:
        temp_used_pct = _temp_used_pct()
    if temp_used_pct is not None:
        lines.append(f"temp: {temp_used_pct:.0f}% used of the temp volume, "
                     f"line at {disk_max:.0f}%")
        if temp_used_pct >= disk_max:
            breaches.append(f"temp {temp_used_pct:.0f}% over the {disk_max:.0f}% line")
    if mem_avail_mb is None:
        mem_avail_mb = memory_available_mb()
    if mem_min_mb is None:
        total = memory_total_mb()
        mem_min_mb = 256 if (total or 0) >= 4096 else 128
    if mem_avail_mb is not None:
        lines.append(f"memory: {mem_avail_mb} MB available, floor {mem_min_mb} MB")
        if mem_avail_mb < mem_min_mb:
            breaches.append(f"memory {mem_avail_mb} MB under the {mem_min_mb} MB floor")
    plans = newest_plans(runs)
    if stale_min is None:
        longest = 0
        for plan in plans:
            longest = max(longest, max((row.get("seconds", 0)
                                        for row in (plan.get("targets") or {}).values()),
                                       default=0))
        stale_min = max(30, int(2 * longest / 60)) if plans else 60
    if expect_workers is None:
        expect_workers = 1 if plans else 0
    if workers is None:
        workers = grow_workers_live()
    mine = [r for r in runs if r.get("kind") in ("grow", "seed", "distill")
            and (rig is None or r.get("rig") == rig)]
    newest = max((str(r.get("when", "")) for r in mine), default="")
    age_min = None
    if newest:
        try:
            then = datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_min = int((now - then).total_seconds() // 60)
        except ValueError:
            pass
    if workers is not None:
        lines.append(f"workers: {workers} grow process(es) live"
                     + (f", last run record {age_min} min ago" if age_min is not None
                        else ", no run record" + (f" from {rig}" if rig else ""))
                     + f", stale past {stale_min} min")
    if expect_workers:
        if workers is not None and workers < expect_workers:
            breaches.append(f"stalled: {workers} grow worker(s) live, {expect_workers} "
                            "expected (Q122 shape: stop the tree, relaunch, report)")
        elif age_min is not None and age_min > stale_min:
            breaches.append(f"stalled: workers live but no run record in {age_min} min "
                            "(Q122 shape: a child blocked on its pipe; stop the tree, "
                            "relaunch, report)")
    return lines, breaches


def cmd_watch(args, out=print):
    """The ten-minute watch, one line per reading and a verdict; exit
    1 on a breach so a timer can act on it."""
    rig = args.rig or os.environ.get("HP_DE_DUST_RIG") or None
    lines, breaches = watch_readings(rig=rig, disk_max=args.disk_max,
                                     mem_min_mb=args.mem_min_mb,
                                     stale_min=args.stale_min,
                                     expect_workers=args.expect_workers)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for line in lines:
        out(f"watch {stamp}" + (f" {rig}" if rig else "") + f": {line}")
    if getattr(args, "record", False):
        # On the ledger, so a breach is proof of work the bank carries
        # and the table's fourth reading has something to read.
        record_run({"kind": "watch", "when": stamp, "head": head_sha()[:12],
                    "readings": lines, "breaches": breaches,
                    **({"rig": rig} if rig else {})})
    if breaches:
        out(f"watch {stamp}" + (f" {rig}" if rig else "") + ": BREACH " + "; ".join(breaches))
        return 1
    out(f"watch {stamp}" + (f" {rig}" if rig else "") + ": ok")
    return 0


def rig_table(runs=None, now=None, past=None, git=None):
    """One row per rig from the ledger (de_dust2, the rig seat's pull
    check): the newest run's time, head and target, runs in the last
    hour, and -- with `past`, a commit -- whether that head descends
    from it, by git ancestry in this tree ("unknown" when the head is
    not here)."""
    runs = load_runs() if runs is None else runs
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rigs = {}
    for r in runs:
        if r.get("kind") not in ("grow", "seed", "distill") or not r.get("rig"):
            continue
        row = rigs.setdefault(r["rig"], {"rig": r["rig"], "when": "", "head": "",
                                         "target": "", "last_hour": 0, "mem": None,
                                         "peak": None})
        if str(r.get("when", "")) > row["when"]:
            row.update(when=r["when"], head=str(r.get("head", "")), target=r.get("target", ""),
                       mem=r.get("mem_available_mb"), peak=r.get("peak_rss_mb"))
        if str(r.get("when", "")) >= since:
            row["last_hour"] += 1
    git = git or (lambda args: subprocess.run(["git"] + args, cwd=ROOT, capture_output=True,
                                              text=True, timeout=60).returncode)
    for row in rigs.values():
        try:
            then = datetime.strptime(row["when"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            row["age_min"] = int((now - then).total_seconds() // 60)
        except ValueError:
            row["age_min"] = None
        if past and row["head"]:
            known = (git(["cat-file", "-e", row["head"] + "^{commit}"]) == 0
                     and git(["cat-file", "-e", past + "^{commit}"]) == 0)
            row["past"] = (git(["merge-base", "--is-ancestor", past, row["head"]]) == 0
                           if known else None)
    return sorted(rigs.values(), key=lambda r: r["rig"])


def cmd_rigs(args, out=print):
    rows = rig_table(past=args.past)
    if not rows:
        out("no run record names a rig (HP_DE_DUST_RIG is not set on the grows)")
        return 0
    status = 0
    for row in rows:
        verdict = ""
        if args.past:
            verdict = (" past " + args.past[:12] if row.get("past") is True else
                       " NOT past " + args.past[:12] if row.get("past") is False else
                       " (head not in this tree)")
            if row.get("past") is False:
                status = 1
        memory = ""
        if row.get("mem") is not None:
            memory = f", {row['mem']} MB available"
            if row.get("peak") is not None:
                memory += f" (grow peak {row['peak']} MB)"
        out(f"{row['rig']:14} {row['head'][:12]:12} {row['when']} "
            f"({row['age_min']} min ago, {row['target']}), {row['last_hour']} run(s) "
            f"in the last hour{memory}{verdict}")
    return status


def tilt_history(target, runs=None, hours=48, now=None):
    """[(when, tilt)] for a target from the plan records in the window,
    oldest first."""
    runs = load_runs() if runs is None else runs
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for r in runs:
        if r.get("kind") != "plan" or str(r.get("when", "")) < since:
            continue
        row = (r.get("targets") or {}).get(target)
        if row is not None:
            out.append((r["when"], float(row.get("tilt", 0))))
    return sorted(out)


HOLD_SINCE = "2026-10-31T00:00:00Z"   # the first plans made with rounds as tries (the window restarted)


def verdict(runs=None, hours=None, baseline=3.55, now=None, since=HOLD_SINCE,
            lengthened=("dtls_hostile", "dtls_session", "race_stash"),
            saturated=("v2_mail", "board_mail", "query")):
    """The four readings of standing order M.8, in its order, from the
    ledger: fleet kept per CPU-hour against the baseline; the three
    targets the tilt lengthened, held or fallen on their own; the
    saturated mail targets at the floor or not; and the watch's
    breaches on the record. Written before the numbers were, so the
    table reads the rule and not the mood. Returns lines of text."""
    runs = load_runs() if runs is None else runs
    now = now or datetime.now(timezone.utc)
    if hours is None:
        # From 22:00Z, not from the hold's text. The text is 22:50Z.
        # A window that starts then never sees the 22:17Z plans, which
        # are the tilt, and the last plan under the old tilt is 21:39Z.
        start = datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        hours = max(0.1, (now - start).total_seconds() / 3600.0)
    rows = {r["target"]: r for r in yield_table(hours, runs, now=now)}
    lines = []
    fleet = rows.get("fleet")
    if fleet and fleet["cpu_h"]:
        kph = fleet["kept_per_cpu_h"]
        lines.append(f"1. fleet: {kph:.2f} kept per CPU-hour over {fleet['cpu_h']:.1f} "
                     f"CPU-hours in the last {hours:.2f} h, against {baseline:.2f} -> "
                     + ("held or better" if kph >= baseline else "below the baseline"))
    else:
        lines.append(f"1. fleet: no grow in the last {hours:.2f} h")
    for name in lengthened:
        hist = tilt_history(name, runs, hours, now)
        row = rows.get(name)
        if not hist:
            lines.append(f"2. {name}: no plan in the window")
            continue
        first, last = hist[0][1], hist[-1][1]
        peak = max(t for _w, t in hist)
        state = ("held 4x" if last >= TILT_MAX - 1e-9 else
                 "fell to the floor on its own" if last <= TILT_FLOOR + 1e-9 else
                 f"settled at {last:.2f}x")
        extra = (f"; {row['kept_per_cpu_h']:.1f} kept per CPU-hour on "
                 f"{row['cpu_h']:.2f} CPU-hours" if row else "")
        lines.append(f"2. {name}: {len(hist)} plan(s), first {first:.2f}x, peak {peak:.2f}x, "
                     f"last {last:.2f}x -> {state}{extra}")
    for name in saturated:
        hist = tilt_history(name, runs, hours, now)
        if not hist:
            lines.append(f"3. {name}: no plan in the window")
            continue
        above = sum(1 for _w, t in hist if t > TILT_FLOOR + 1e-9)
        row = rows.get(name)
        lines.append(f"3. {name}: {len(hist)} plan(s), {above} above the floor, last "
                     f"{hist[-1][1]:.2f}x -> " + ("at the floor" if above == 0 else
                                                  "lifted off the floor")
                     + (f"; {row['kept']} kept on {row['cpu_h']:.2f} CPU-hours" if row else ""))
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    watches = [r for r in runs if r.get("kind") == "watch" and str(r.get("when", "")) >= since]
    breached = [r for r in watches if r.get("breaches")]
    if not watches:
        lines.append(f"4. watch: no watch record in the last {hours:.2f} h (run `watch --record`)")
    else:
        by_rig = {}
        for r in breached:
            by_rig.setdefault(r.get("rig") or "?", []).extend(r["breaches"])
        lines.append(f"4. watch: {len(watches)} record(s), {len(breached)} with a breach"
                     + ("; " + "; ".join(f"{rig}: {len(b)} ({b[-1][:60]})"
                                         for rig, b in sorted(by_rig.items()))
                        if by_rig else " -> none"))
    return lines


def cmd_stats(args, out=print):
    if getattr(args, "yield_table", False):
        hours = getattr(args, "hours", 48) or 48
        for line in format_yield(yield_table(hours), hours):
            out(line)
        return 0
    if getattr(args, "note", False):
        out(hourly_note(rig=os.environ.get("HP_DE_DUST_RIG") or None))
        return 0
    if getattr(args, "verdict", False):
        hours = args.hours if args.hours_given else None
        out(f"{CAMPAIGN} verdict, standing order M.8, "
            + (f"last {hours:g} h:" if hours else f"since {HOLD_SINCE} (the tilt's plans):"))
        for line in verdict(hours=hours, baseline=args.baseline):
            out("  " + line)
        return 0
    if getattr(args, "plan", False):
        plans = newest_plans()
        if not plans:
            out("no plan on record")
            return 0
        for plan in plans:
            out(f"{CAMPAIGN} plan at {plan.get('when')} on {plan.get('head')}"
                + (f" ({plan['rig']})" if plan.get("rig") else "")
                + f": slice {plan.get('slice')} s, {plan.get('minutes')} min, "
                f"{plan.get('jobs')} at a time")
            for tg, row in sorted((plan.get("targets") or {}).items(),
                                  key=lambda kv: -kv[1].get("seconds", 0)):
                out(f"  {tg:14} {row.get('technique', 'mutation'):9} "
                    f"{row.get('tilt', 0):.2f}x {row.get('seconds', 0):6d} s "
                    f"{row.get('rounds', 0):6d} rounds  yield {row.get('yield', 0)}")
        return 0
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
    p = sub.add_parser("watch", help="the ten-minute watch: floors, workers, "
                                     "stall; exit 1 on a breach")
    p.add_argument("--rig", default=None, help="this rig's name (HP_DE_DUST_RIG)")
    p.add_argument("--disk-max", type=float, default=90.0)
    p.add_argument("--mem-min-mb", type=int, default=None,
                   help="available-memory floor (default 256 on 4 GB+, else 128)")
    p.add_argument("--stale-min", type=int, default=None,
                   help="minutes without a run record that mean a stall "
                        "(default twice the plan's longest slice, 30 at least)")
    p.add_argument("--expect-workers", type=int, default=None,
                   help="grow processes that should be live (default 1 when a "
                        "plan stands)")
    p.add_argument("--record", action="store_true",
                   help="write the readings and any breach to the ledger as a "
                        "watch record, so the bank carries it")
    p.set_defaults(fn=cmd_watch)
    p = sub.add_parser("rigs", help="one line per rig from the ledger; --past "
                                    "checks every rig's head descends from a commit")
    p.add_argument("--past", default=None, help="a commit every rig should have crossed")
    p.set_defaults(fn=cmd_rigs)
    p = sub.add_parser("disk", help="count failed writes on a flickering disk")
    p.add_argument("--writes", type=int, default=200)
    p.add_argument("--where", default=None,
                   help="directory to probe (default: the corpus directory)")
    p.set_defaults(fn=cmd_disk)
    for name, fn in (("seed", cmd_seed), ("grow", cmd_grow),
                     ("replay", cmd_replay), ("platform", cmd_platform),
                     ("promote", cmd_promote), ("distill", cmd_distill),
                     ("stats", cmd_stats)):
        p = sub.add_parser(name)
        p.add_argument("--target", default="all",
                       help="one of %s, or all" % ", ".join(TARGETS))
        p.set_defaults(fn=fn)
        if name == "distill":
            p.add_argument("--write", action="store_true",
                           help="rewrite the corpus to the minimal set; "
                                "without it, only report what would drop")
        if name == "stats":
            p.add_argument("--yield", dest="yield_table", action="store_true",
                           help="the per-target yield table over the last "
                                "--hours of grows: CPU, rate, kept, arcs, "
                                "accepted share, kept per CPU-hour")
            p.add_argument("--hours", type=float, default=48)
            p.add_argument("--hours-given", action="store_true", help=argparse.SUPPRESS)
            p.add_argument("--note", action="store_true",
                           help="the hourly campaign note, in its shape, "
                                "from the ledger, the box and the disk probe")
            p.add_argument("--plan", action="store_true",
                           help="the newest slice plan a cycling grow "
                                "recorded: what each target was given and why")
            p.add_argument("--verdict", action="store_true",
                           help="the four readings of standing order M.8, in "
                                "its order, from the ledger")
            p.add_argument("--baseline", type=float, default=3.55,
                           help="the fleet kept-per-CPU-hour the verdict "
                                "reads against (M.8: 3.55)")
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
            p.add_argument("--slice", type=float, default=None,
                           help="with --minutes: seconds of each target's "
                                "turn per cycle, tilted by its yield; its "
                                "rounds follow from its measured rate "
                                "(HP_DE_DUST_SLICE, default %d; --rounds "
                                "names a fixed count instead)"
                                % DEFAULT_SLICE_SEC)
            p.add_argument("--budget-sec", type=float, default=None,
                           help="stop this grow once it has run this many "
                                "seconds. A cycling grow sets it from the "
                                "slice's planned time, so a rate that was "
                                "a lie cannot hold the core past the slice. "
                                "A fixed --rounds grow leaves it unset")
            p.add_argument("--uniform-parents", action="store_true",
                           help="draw parents uniformly instead of by "
                                "rarity and acceptance")
            p.add_argument("--order", choices=("stale", "fixed"),
                           default="stale",
                           help="with --minutes: the order the targets "
                                "cycle in. stale (default) starts at the "
                                "target least recently grown in runs.jsonl, "
                                "so a short cycle reaches every target "
                                "over time and two rigs pick apart; fixed "
                                "is the list's own order")
    args = ap.parse_args(argv)
    if hasattr(args, "hours_given"):
        args.hours_given = any(a == "--hours" or a.startswith("--hours=")
                               for a in (argv if argv is not None else sys.argv[1:]))
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
