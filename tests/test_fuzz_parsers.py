"""Structured fuzz of the parser surfaces the transport migration
and per-job encryption added.

test_fuzz_surfaces campaigns the original parsers (verify, config
validators, the IMAP fetch). The surfaces here are the ones that
arrived after it:

- the transport envelope readers (runner.transports.parse_envelope,
  the extension-side twin in transport_extensions.channel, and the
  channel directory readers on both sides),
- the email extension's raw-message extraction (_subject_body,
  reply_target) -- the header/subject parsing an untrusted mail
  hits first,
- mailbox._valid_reply_to, the signed body's routing parser,
- runner.jobcrypto's envelope handling (per-job encryption):
  decrypt_body / is_envelope / aead_decrypt / hkdf under
  structured mutation of a valid envelope.

Mutations are structural, per the surfaces' shapes: truncation,
splice-point corruption (the `,"sig":"..."}` seam and the
envelope member boundaries), type swaps (str <-> list <-> dict),
unicode/encoding edges, and oversized fields -- not just byte
flips. The invariant per surface is its own error vocabulary:
the envelope readers and extractors return a value or None and
raise NOTHING; enabled_transports raises ValueError only;
jobcrypto raises JobCryptoError only (a ValueError). Anything
else -- AttributeError, TypeError where the module promises
none, RecursionError escaping a parser, a hang-sized input --
is a crash, reported with the input that caused it.

jobcrypto lands with the per-job-encryption build; until then
its campaign skips (the module import is guarded), and the
campaign activates unchanged the moment runner/jobcrypto.py
exists. Campaigns here were also run against the encryption
branch's copy during the pipeline-hardening pass.

Deterministic: one master seed, pinned per-surface rngs, the
same discipline as test_fuzz_surfaces. In-suite rounds are
bounded; a longer campaign runs standalone:

    python -m tests.test_fuzz_parsers [rounds] [seed]

Nothing here opens a socket, a mailbox, or a process. Channel
readers run against throwaway directories under the temp root.
"""
import base64
import json
import os
import random
import sys
import tempfile
import unittest

MASTER_SEED = 20261019
SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)

CRASH = (AttributeError, SystemExit, MemoryError, NameError,
         AssertionError, RecursionError, TypeError, KeyError,
         IndexError, OverflowError)

try:
    from runner import jobcrypto as _jobcrypto
except Exception:  # module not landed yet; campaign skips
    _jobcrypto = None


# ------------------------------------------------------------------
# Mutation helpers
# ------------------------------------------------------------------

def _type_swaps(rng, value):
    """The same shape with one member's type swapped out."""
    swaps = [None, True, 0, 1.5, "", "x", [], {}, [1], {"a": 1},
             "é", "\x00", ["hp_enc"]]
    return swaps[rng.randrange(len(swaps))]


def _mutate_text(rng, text):
    """One structural mutation of a text: truncate, splice-cut,
    insert, duplicate, or unicode-edge it."""
    if not text:
        return text + rng.choice(["", "\n\n", "{", '"', "é"])
    op = rng.randrange(6)
    if op == 0:  # truncate
        return text[: rng.randrange(len(text) + 1)]
    if op == 1:  # delete a span
        i = rng.randrange(len(text))
        return text[:i] + text[i + rng.randint(1, 8):]
    if op == 2:  # insert junk at a seam
        i = rng.randrange(len(text) + 1)
        junk = rng.choice(['",', ',"sig":"', "\n\n", "\r\n", "{}",
                           "[]", "null", '"hp_enc"', "é", "\x00"])
        return text[:i] + junk + text[i:]
    if op == 3:  # duplicate
        return text * rng.randint(2, 3)
    if op == 4:  # oversized field
        i = rng.randrange(len(text) + 1)
        return text[:i] + "A" * rng.randint(500, 4000) + text[i:]
    # byte-level damage, kept str-shaped via latin-1 round trip
    raw = bytearray(text.encode("utf-8", "replace"))
    for _ in range(rng.randint(1, 4)):
        raw[rng.randrange(len(raw))] = rng.randrange(256)
    return bytes(raw).decode("latin-1")


def _mutate_value(rng, value, depth=0):
    """One structural mutation of a parsed JSON value."""
    if isinstance(value, dict) and value and depth < 3:
        out = dict(value)
        key = rng.choice(list(out))
        op = rng.randrange(4)
        if op == 0:
            out[key] = _type_swaps(rng, out[key])
        elif op == 1:
            del out[key]
        elif op == 2:
            out[key] = _mutate_value(rng, out[key], depth + 1)
        else:
            out[rng.choice(["sig", "hp_enc", "key_id", "extra",
                            "", "alg"])] = _type_swaps(rng, None)
        return out
    if isinstance(value, str):
        return _mutate_text(rng, value)
    if isinstance(value, list) and value:
        out = list(value)
        out[rng.randrange(len(out))] = _type_swaps(rng, None)
        return out
    return _type_swaps(rng, value)


def _jsonish(rng, blob):
    try:
        return json.loads(blob.decode("utf-8"))
    except Exception:
        return {"blob": blob.decode("latin-1")}


# ------------------------------------------------------------------
# Surface exercises. Each returns a list of crash strings.
# ------------------------------------------------------------------

def _exercise_envelopes(rng, blob):
    from runner.transports import parse_envelope as core_parse
    from runner.transport_extensions.channel import (
        parse_envelope as ext_parse,
    )
    crashes = []
    text = blob.decode("latin-1")
    for name, fn in (("transports.parse_envelope", core_parse),
                     ("channel.parse_envelope", ext_parse)):
        for candidate in (text, _mutate_text(rng, text)):
            try:
                out = fn(candidate)
                if out is not None:
                    subject, body = out
                    if not isinstance(subject, str) \
                            or not isinstance(body, str):
                        crashes.append(
                            f"{name}: non-str parts {type(out)!r}")
            except CRASH as e:
                crashes.append(f"{name}: {type(e).__name__}: {e!r}")
            except Exception as e:  # the readers promise no raises
                crashes.append(f"{name}: {type(e).__name__}: {e!r}")
    # Type swaps: the core reader guards isinstance and must
    # return None; the channel reader's domain is str/None (its
    # callers read files), so only those are held to no-raise.
    for bad in (None, b"a\n\nb", 0, [], {}):
        try:
            if core_parse(bad) is not None:
                crashes.append(f"core parse_envelope({bad!r}) not None")
        except Exception as e:
            crashes.append(
                f"core parse_envelope type: {type(e).__name__}")
    try:
        ext_parse(None)
        ext_parse("")
    except Exception as e:
        crashes.append(f"channel parse_envelope(None/''): "
                       f"{type(e).__name__}")
    return crashes


def _exercise_config_surface(rng, blob):
    from runner.transports import enabled_transports
    crashes = []
    value = _jsonish(rng, blob)
    candidates = [value, _mutate_value(rng, value),
                  {"transports": value}, {"transports": [value]},
                  {"transports": "email, file,,nats"},
                  {"transports": ["ok-name", value]}]
    for cfg in candidates:
        try:
            out = enabled_transports(cfg)
            if not isinstance(out, list) \
                    or not all(isinstance(n, str) for n in out):
                crashes.append(f"enabled_transports: bad out {out!r}")
        except ValueError:
            pass  # the documented reject
        except Exception as e:
            crashes.append(
                f"enabled_transports: {type(e).__name__}: {e!r}")
    return crashes


def _exercise_mail_extract(rng, blob):
    from runner.transport_extensions.email.__main__ import (
        _subject_body, reply_target,
    )
    from runner.mailbox import _valid_reply_to
    crashes = []
    try:
        subject, body = _subject_body(blob)
        if not isinstance(subject, str) or not isinstance(body, str):
            crashes.append("_subject_body: non-str parts")
    except Exception as e:
        crashes.append(f"_subject_body: {type(e).__name__}: {e!r}")
    text = blob.decode("utf-8", "replace")
    for candidate in (text, _mutate_text(rng, text)):
        try:
            out = reply_target(candidate, "box@example.com")
            if not isinstance(out, str):
                crashes.append("reply_target: non-str out")
        except Exception as e:
            crashes.append(
                f"reply_target: {type(e).__name__}: {e!r}")
    value = _jsonish(rng, blob)
    for job in (value, _mutate_value(rng, value),
                {"reply_to": value}, {"reply_to": "a@b.co"},
                {"reply_to": "a" * 300 + "@b.co"}):
        try:
            out = _valid_reply_to(job)
            if out is not None and not isinstance(out, str):
                crashes.append("_valid_reply_to: non-str out")
        except Exception as e:
            crashes.append(
                f"_valid_reply_to: {type(e).__name__}: {e!r}")
    return crashes


def _exercise_channels(rng, blob):
    """The channel directory readers, against a throwaway tree
    whose inbox holds the mutated blob under several filenames."""
    from runner.transports import fetch_channel_messages
    from runner.transport_extensions.channel import (
        deliver_job, pending_results,
    )
    crashes = []
    text = blob.decode("utf-8", "replace")
    names = ["a.job.txt", "b.job.txt", "sp ace.job.txt",
             "ünïcode.job.txt", "noext", ".hidden.job.txt"]
    with tempfile.TemporaryDirectory() as base:
        channel = os.path.join(base, "transport-extensions", "file")
        inbox = os.path.join(channel, "inbox")
        os.makedirs(os.path.join(inbox, "done"))
        os.makedirs(os.path.join(channel, "outbox", "done"))
        for i, name in enumerate(names):
            path = os.path.join(inbox, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_mutate_text(rng, text) if i % 2 else text)
        # The extension side writes results into the same tree.
        for i, name in enumerate(names[:3]):
            with open(os.path.join(channel, "outbox", name),
                      "w", encoding="utf-8") as fh:
                fh.write(_mutate_text(rng, text) if i % 2 else text)
        try:
            messages = fetch_channel_messages(base, "file")
            if not isinstance(messages, list):
                crashes.append("fetch_channel_messages: not a list")
            for msg in messages:
                msg.ack()  # consumption must never raise either
        except Exception as e:
            crashes.append("fetch_channel_messages: "
                           f"{type(e).__name__}: {e!r}")
        try:
            results = pending_results(channel)
            if not isinstance(results, list):
                crashes.append("pending_results: not a list")
        except Exception as e:
            crashes.append(
                f"pending_results: {type(e).__name__}: {e!r}")
        # deliver_job ident containment: whatever the ident, the
        # file it writes must stay inside the channel inbox.
        for ident in ("../escape", "..\\escape", "/abs", "a/b",
                      "", ".", "..", "x" * 500, "ünïcödé",
                      "a\x00b"):
            try:
                path = deliver_job(channel, ident, "s", "b")
                inside = os.path.realpath(path).startswith(
                    os.path.realpath(inbox) + os.sep)
                if not inside:
                    crashes.append(
                        f"deliver_job escaped inbox: {ident!r}")
            except Exception as e:
                crashes.append("deliver_job(%r): %s: %r"
                               % (ident, type(e).__name__, e))
    return crashes


def _sign_stub(payload, _secret):
    """The splice discipline, minus the HMAC: serialize, cut the
    closing brace, splice the sig member in."""
    text = json.dumps(payload, separators=(",", ":"))
    return text[:-1] + ',"sig":"' + "ab" * 48 + '"}'


def _exercise_jobcrypto(rng, blob):
    jc = _jobcrypto
    crashes = []
    if jc is None:
        return crashes
    # A valid envelope, then structural mutations at both the
    # text level (re-parsed) and the value level.
    valid_text = jc.encrypt_body(
        '{"v":1,"type":"job","kind":"ping"}', SECRET, "job-1", "",
        _sign_stub)
    valid = json.loads(valid_text)
    candidates = [valid, _mutate_value(rng, valid),
                  _mutate_value(rng, _mutate_value(rng, valid))]
    mutated_text = _mutate_text(rng, valid_text)
    try:
        candidates.append(json.loads(mutated_text))
    except Exception:
        pass
    for payload in candidates:
        try:
            out = jc.is_envelope(payload)
            if not isinstance(out, bool):
                crashes.append("is_envelope: non-bool out")
        except Exception as e:
            crashes.append(
                f"is_envelope: {type(e).__name__}: {e!r}")
        try:
            plain = jc.decrypt_body(payload, SECRET, "job-1", "")
            if not isinstance(plain, str):
                crashes.append("decrypt_body: non-str out")
        except jc.JobCryptoError:
            pass  # the module's one documented reject
        except Exception as e:
            crashes.append(
                f"decrypt_body: {type(e).__name__}: {e!r}")
    # Raw AEAD with mutated ciphertext/AAD, at the construction's
    # own sizes (32-octet key, 12-octet nonce -- the only sizes
    # decrypt_body can ever present: the key comes from the HKDF
    # at _KEY_LEN and the nonce is length-checked before the
    # call). Out-of-size keys/nonces are a separate, reported
    # finding: aead_decrypt raises IndexError from the block
    # function's word packing instead of JobCryptoError, outside
    # the envelope path (which never presents such sizes).
    key = bytes(rng.randrange(256) for _ in range(32))
    nonce = bytes(rng.randrange(256) for _ in range(12))
    ct = bytes(rng.randrange(256) for _ in range(rng.choice(
        [0, 8, 15, 16, 17, 64, 256])))
    aad = blob[:64]
    try:
        jc.aead_decrypt(key, nonce, ct, aad)
    except jc.JobCryptoError:
        pass
    except Exception as e:
        crashes.append(f"aead_decrypt: {type(e).__name__}: {e!r}")
    try:
        jc.hkdf(blob[:32], blob[32:64], b"info",
                rng.choice([0, 1, 32, 255 * 48 + 1]))
    except jc.JobCryptoError:
        pass
    except Exception as e:
        crashes.append(f"hkdf: {type(e).__name__}: {e!r}")
    return crashes


_EXERCISES = (
    _exercise_envelopes,
    _exercise_config_surface,
    _exercise_mail_extract,
    _exercise_channels,
    _exercise_jobcrypto,
)

SEEDS = [
    b"",
    b"Subject only, no blank line",
    b"[HOMING-PIGEON] job abc\n\n{\"v\":1}",
    b"[HOMING-PIGEON] job abc\r\n\r\n{\"v\":1}\r\n",
    b"Subject: [HOMING-PIGEON] job x\nContent-Type: text/plain\n"
    b"\n{\"v\":1,\"type\":\"job\"}",
    b"From: a@b.co\nSubject: =?utf-8?b?44GT44KT44Gr44Gh?=\n\nbody",
    b'{"transports": ["email", "file"]}',
    b'{"reply_to": "owner@example.com"}',
    b'{"a":' * 40 + b"1" + b"}" * 40,
    "é\n\nünïcode body".encode(),
    b"\xff\xfe\n\n\x00\x01",
    b"A" * 5000 + b"\n\n" + b"B" * 5000,
]


def campaign(rounds, seed=MASTER_SEED):
    rng = random.Random(seed)
    crashes = []
    for i in range(rounds):
        blob = rng.choice(SEEDS)
        if i % 3:
            blob = _mutate_text(rng, blob.decode("latin-1")).encode(
                "latin-1")[:8000]
        for exercise in _EXERCISES:
            found = exercise(rng, blob)
            if found:
                crashes.append((blob[:80], found))
                if len(crashes) >= 5:
                    return crashes
    return crashes


class FuzzParsersTest(unittest.TestCase):
    def test_a_short_campaign_has_no_crash(self):
        self.assertEqual(campaign(60, MASTER_SEED), [])

    def test_envelope_readers_agree_on_the_canonical_shape(self):
        from runner.transports import parse_envelope as core_parse
        from runner.transport_extensions.channel import (
            parse_envelope as ext_parse,
        )
        text = "[HOMING-PIGEON] job abc\n\n{\"v\":1}\n"
        self.assertEqual(core_parse(text), ext_parse(text))
        self.assertEqual(core_parse(text),
                         ("[HOMING-PIGEON] job abc", "{\"v\":1}\n"))

    def test_deliver_job_ident_cannot_escape_the_inbox(self):
        from runner.transport_extensions.channel import deliver_job
        with tempfile.TemporaryDirectory() as base:
            channel = os.path.join(base, "chan")
            for ident in ("../escape", "..\\escape", "/abs", "..",
                          "a/b", "a\\b"):
                path = deliver_job(channel, ident, "s", "b")
                self.assertTrue(
                    os.path.realpath(path).startswith(
                        os.path.realpath(
                            os.path.join(channel, "inbox")) + os.sep),
                    ident)

    def test_reply_target_survives_deep_nesting(self):
        from runner.transport_extensions.email.__main__ import (
            reply_target,
        )
        deep = '{"a":' * 300 + "1" + "}" * 300
        self.assertEqual(reply_target(deep, "box@example.com"),
                         "box@example.com")

    @unittest.skipUnless(_jobcrypto, "jobcrypto not landed yet")
    def test_jobcrypto_campaign_has_no_crash(self):
        rng = random.Random(MASTER_SEED)
        crashes = []
        for blob in SEEDS:
            crashes.extend(_exercise_jobcrypto(rng, blob))
        self.assertEqual(crashes, [])

    @unittest.skipUnless(_jobcrypto, "jobcrypto not landed yet")
    def test_jobcrypto_roundtrip_and_tamper(self):
        jc = _jobcrypto
        text = jc.encrypt_body('{"v":1}', SECRET, "job-9", "k",
                               _sign_stub)
        payload = json.loads(text)
        self.assertTrue(jc.is_envelope(payload))
        self.assertEqual(
            jc.decrypt_body(payload, SECRET, "job-9", "k"),
            '{"v":1}')
        payload["hp_enc"]["ct"] = base64.b64encode(
            b"\x00" * 32).decode("ascii")
        with self.assertRaises(jc.JobCryptoError):
            jc.decrypt_body(payload, SECRET, "job-9", "k")


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else MASTER_SEED
    found = campaign(rounds, seed)
    if found:
        for blob, crashes in found:
            print(crashes, blob)
        raise SystemExit(1)
    print("parser campaign ok")
