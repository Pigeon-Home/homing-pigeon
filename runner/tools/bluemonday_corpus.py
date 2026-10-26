#!/usr/bin/env python3
# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Project blueMonday: the fuzz corpus against the verifiers (Q62).

    python runner/tools/bluemonday_corpus.py seed   [--target T]
    python runner/tools/bluemonday_corpus.py grow   [--target T] [--rounds N]
                                                    [--seed S] [--jobs J]
                                                    [--minutes M]
    python runner/tools/bluemonday_corpus.py replay [--target T]
    python runner/tools/bluemonday_corpus.py promote [--target T]
    python runner/tools/bluemonday_corpus.py stats  [--target T]

A coverage-guided seed corpus, kept under runner/tests/bluemonday/
as replayable fixtures, against the readers that stand between a
delivered body and the agent's trust in it:

    wire    runner/wire/verify.py        verify_body, verify_body_keyed
    cloud   runner/cloud/send_job.py     verify_body (the front-end's copy)
    v2      runner/wire/protocol_v2.py   validate
    crypto  runner/wire/jobcrypto.py     decrypt_body
    local   runner/runner.py             _ingest_local_envelope_inner,
            runner/wire/transports.py    parse_envelope
    stash   runner/runner.py             _record_payload (a stashed
                                         record's body, its three key slots)

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
keepers; with --jobs J (HP_BLUEMONDAY_JOBS) the targets grow J at
a time in their own processes, the next one starting the moment
any one finishes, which is how the rig keeps every core busy; with
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
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402
from runner.ops.extensions import build_sensor_alert  # noqa: E402
from runner.wire import jobcrypto as JC  # noqa: E402
from runner.wire import protocol_v2 as P2  # noqa: E402
from runner.wire import transports as TR  # noqa: E402
from runner.wire import verify as V  # noqa: E402
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


def _short(exc):
    text = str(exc)
    return text if len(text) <= 200 else text[:200] + "..."


def _unsigned(payload):
    """The payload without the protocol's own member: `sig` is the
    signature's slot on the wire, so a payload that carries one of
    its own is read back with the slot overwritten by the keyed
    reader and kept by the plain one; neither is a disagreement."""
    return {k: v for k, v in payload.items() if k != "sig"}


def _verify_text(text):
    """wire: both readers of runner/wire/verify.py on one received
    body, each to its contract, and the two in agreement."""
    got, exc = _call(V.verify_body, text, SECRET)
    if exc is not None:
        _expect_refusal(exc, ValueError, "verify_body")
    elif not isinstance(got, dict):
        raise Crash("shape", f"verify_body returned {type(got).__name__}")
    keyed, kexc = _call(V.verify_body_keyed, text, SECRETS)
    if kexc is not None:
        _expect_refusal(kexc, ValueError, "verify_body_keyed")
    elif not (isinstance(keyed, tuple) and len(keyed) == 2
              and isinstance(keyed[0], dict)
              and isinstance(keyed[1], str)):
        raise Crash("shape", "verify_body_keyed returned "
                    f"{type(keyed).__name__}")
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
    returns a dict; whatever it trusts, the agent's verifier trusts
    too, and reads the same payload (the agent's is the superset:
    it also survives a mail transport's control characters)."""
    got, exc = _call(SJ.verify_body, text, SECRET)
    if exc is not None:
        _expect_refusal(exc, ValueError, "send_job.verify_body")
        return "refused"
    if not isinstance(got, dict):
        raise Crash("shape", f"send_job.verify_body returned "
                    f"{type(got).__name__}")
    agent, aexc = _call(V.verify_body, text, SECRET)
    if aexc is not None:
        raise Crash("agreement", "the front-end trusts a body the agent "
                    f"refuses: {_short(aexc)}")
    if agent != got:
        raise Crash("agreement", "the front-end and the agent read "
                    "different payloads from one body")
    return "accepted"


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


def _local_ingest(text):
    got, exc = _call(R._ingest_local_envelope_inner, LOCAL_CFG, _RIG.dir,
                     text, "bluemonday")
    if exc is not None:
        raise Crash("exception", "_ingest_local_envelope_inner raised "
                    f"{type(exc).__name__}: {_short(exc)}")
    if got is not None and not isinstance(got, dict):
        raise Crash("shape", "_ingest_local_envelope_inner returned "
                    f"{type(got).__name__}")
    return "accepted" if got is not None else "refused"


def check_local(entry):
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
        return _local_ingest(body)
    payload = _stamp_issued_at(entry["data"])
    secret, _key_id = _signing_secret(payload)
    body, exc = _call(V.sign_payload, payload, secret or SECRET)
    if exc is not None:
        _expect_refusal(exc, ValueError, "sign_payload")
        return "refused"
    return _local_ingest(body)


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
        ("empty", {}),
        ("big_int", _job(size=2 ** 63)),
    ]


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
        ("no_marker", json.dumps(_job())),
        ("short_tail", exec_body[:-10] + "\"}"),
        ("pretty", json.dumps(_job(), indent=2)),
        ("empty", ""),
        ("bom", "﻿" + exec_body),
        ("wrong_secret", V.sign_payload(_job(), WRONG)),
    ]
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
    out += [("v1", {"v": 1, "type": "answer"}), ("empty", {}),
            ("list", []), ("string", "answer"), ("none", None),
            ("number", 2)]
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


TEXT_MUTATORS = [t_truncate, t_drop, t_insert, t_replace_char, t_duplicate,
                 t_splice, t_sig_tamper, t_fake_marker, t_wrap, t_crlf,
                 t_control, t_case, t_number, t_brace, t_resign]

_VALUES = [None, True, False, 0, -1, 1, 2 ** 31, 2 ** 63, 2 ** 64, -2 ** 63,
           1.5, -0.0, 1e308, "", " ", "x", "0", "Z", "job", "sensor_alert",
           "proceed", "2026-10-26T12:00:00Z", "2026-10-26T12:00:00",
           "2026-13-01T00:00:00Z", "\u0000", "\ud800", "﻿", " ",
           "a" * 65, "a" * 129, "b" * 4000, "../x", ".", "..", "x/y",
           [], {}, [None], {"": ""}, [[]], {"a": {"b": {"c": []}}}, "@now"]
_KEYS = ["v", "type", "job_id", "msg_id", "issued_at", "kind", "key_id",
         "sig", "hp_enc", "alg", "nonce", "ct", "sensor", "severity",
         "title", "signal", "detail", "observed_at", "api_version",
         "script", "shell", "expect", "why", "clean_pass", "question",
         "deadline_sec", "local_default", "context", "question_id",
         "answer", "text", "", " ", "Key_Id", "KEY_ID", "kéy",
         "\u0000", "a" * 200]


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
                    p_number, p_nest, p_splice, p_swap]


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


def mutate(rng, entry, corpus, target):
    """One child of an entry: (data, mutator name), or None when the
    mutation is a no-op or breaks the size caps."""
    if entry["kind"] == "text":
        mut = rng.choice(TEXT_MUTATORS)
        data = mut(rng, entry["data"], corpus)
        name = mut.__name__
        if len(data.encode("utf-8", "surrogatepass")) > MAX_TEXT:
            return None
    elif target == "crypto":
        data = _crypto_mutate(rng, entry["data"], corpus)
        name = "crypto"
    else:
        mut = rng.choice(PAYLOAD_MUTATORS)
        data = mut(rng, entry["data"], corpus)
        name = mut.__name__
    if entry["kind"] == "payload":
        try:
            size = len(json.dumps(data, ensure_ascii=True))
        except (TypeError, ValueError, RecursionError):
            return None
        if size > MAX_PAYLOAD:
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
    "wire": {"files": [_src("wire", "verify.py")], "check": check_wire,
             "seeds": seeds_wire},
    "cloud": {"files": [_src("cloud", "send_job.py")], "check": check_cloud,
              "seeds": seeds_cloud},
    "v2": {"files": [_src("wire", "protocol_v2.py")], "check": check_v2,
           "seeds": seeds_v2},
    "crypto": {"files": [_src("wire", "jobcrypto.py")],
               "check": check_crypto, "seeds": seeds_crypto},
    "local": {"files": [_src("runner.py"), _src("wire", "transports.py")],
              "check": check_local, "seeds": seeds_local},
    "stash": {"files": [_src("runner.py")], "check": check_stash,
              "seeds": seeds_stash},
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


def check(target, entry):
    """Run one entry against its target's contract: "accepted" or
    "refused" when the contract held, or a Crash."""
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


def _run_record(kind, target, session, before, added, seconds, **extra):
    record = {
        "kind": kind, "target": target,
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": head_sha()[:12],
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

    def grow(self, rng, rounds, log=None):
        """Mutate from the corpus for `rounds` children; keep each one
        that reaches a new arc. Returns the entries added."""
        added = []
        self.tried = 0
        self.mutators_tried = {}
        self.mutators_kept = {}
        if not self.entries:
            return added
        for n in range(rounds):
            parent = rng.choice(self.entries)
            child = mutate(rng, parent, self.entries, self.target)
            if child is None:
                continue
            data, name = child
            entry = make_entry(parent["kind"], data, parent["id"], name)
            if entry["id"] in self.ids:
                continue
            self.tried += 1
            self.mutators_tried[name] = self.mutators_tried.get(name, 0) + 1
            outcome, new, _dt = self.run(entry)
            if outcome == "crash":
                if log:
                    log(f"  crash at round {n}: {self.crashes[-1][1]}")
                continue
            if new:
                entry["arcs"] = new
                self.entries.append(entry)
                self.ids.add(entry["id"])
                added.append(entry)
                self.mutators_kept[name] = self.mutators_kept.get(name, 0) + 1
                if log:
                    log(f"  +{new:3d} arcs  {name:14s} {entry['id']}  "
                        f"({outcome})")
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


def grow_commands(targets, rounds, seed, verbose):
    """One `grow` subprocess command per target, for --jobs."""
    out = []
    for target in targets:
        cmd = [sys.executable, os.path.abspath(__file__), "grow",
               "--target", target, "--rounds", str(rounds),
               "--seed", str(seed), "--jobs", "1"]
        if verbose:
            cmd.append("--verbose")
        out.append((target, cmd))
    return out


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
                                          args.verbose), args.jobs,
                            out=out, minutes=minutes)
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

        def work():
            session.baseline()
            before = len(session.tracer.arcs)
            added = session.grow(rng, rounds, log=out if args.verbose
                                 else None)
            return before, added
        before, added = _with_rig(work)
        if added:
            save(corpus_path(target), target, session.entries)
        write_arcs(target, session.tracer.arcs)
        record_run(_run_record(
            "grow", target, session,
            {"entries": len(entries), "arcs": before}, added,
            time.perf_counter() - t0, rounds=rounds, seed=seed,
            tried=session.tried, mutators_tried=session.mutators_tried,
            mutators_kept=session.mutators_kept))
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
        out(f"{target}: {len(entries)} entries ({kinds}), "
            f"{len(crashes)} crashes on file; mutators: {top}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("seed", cmd_seed), ("grow", cmd_grow),
                     ("replay", cmd_replay), ("promote", cmd_promote),
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
                               "HP_BLUEMONDAY_JOBS", "1")),
                           help="targets grown at a time, each in its own "
                                "process (HP_BLUEMONDAY_JOBS, default 1; "
                                "the rig's core count keeps it busy)")
            p.add_argument("--minutes", type=float, default=0.0,
                           help="keep cycling the targets, --jobs at a "
                                "time, until this many minutes have "
                                "passed; a running grow finishes "
                                "(default 0: one pass over the targets)")
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
