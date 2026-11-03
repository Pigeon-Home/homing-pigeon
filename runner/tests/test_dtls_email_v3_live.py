#!/usr/bin/env python3
"""Version 3: the recorded live mailbox runs, replayed offline.

runner/tests/fixtures/dtls_email_v3_live/ holds the exact
flight mail of the 2 live runs of the DTLS via email
carriage (manifest.json there names the run, the session
id, and the job id for every file). These tests run the
recorded mail through the real receiver path -- the
carriage parser and classifier in runner/wire/dtls_mailbox
-- and assert the recorded outcomes: every flight classifies
and parses under its own session, the handshake sequence
assembles in the recorded order (the stateless cookie in
the HelloRetryRequest is the SHA-384 of the first
ClientHello, and the cookied ClientHello carries the same
cookie back), and the job and result flights bind to their
session. Deterministic and offline: fixtures only, no
network, and the runs' shared secrets are never needed --
the replay works at the carriage layer, below the keys.
"""
import email
import email.policy
import hashlib
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtls_mailbox, dtlsproto  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    flight_subject, parse_message)
from runner.tests.test_dtls import _ch_exts  # noqa: E402

FIXTURES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures", "dtls_email_v3_live")
with open(os.path.join(FIXTURES, "manifest.json"),
          encoding="utf-8") as handle:
    MANIFEST = json.load(handle)
RUNS = {run["name"]: run for run in MANIFEST["runs"]}


def _raw(entry):
    with open(os.path.join(FIXTURES, entry["file"]), "rb") as f:
        return f.read()


def _subject(raw):
    message = email.message_from_bytes(
        raw, policy=email.policy.default)
    return str(message.get("Subject") or "")


def _first_record(datagram):
    records = dtlsproto._split_records(datagram)
    return records[0] if records else b""


def _handshake(datagram):
    """(msg_type, raw message, {ext type: value}) when the
    datagram's first record is a plaintext handshake record,
    else None."""
    record = _first_record(datagram)
    if not record or not dtlsproto._is_plaintext_record(record):
        return None
    if record[0] != dtlsproto.CT_HANDSHAKE:
        return None
    length = int.from_bytes(record[11:13], "big")
    parsed = dtlsproto._parse_handshake(record[13:13 + length])
    if parsed is None or parsed[0] == "fragment":
        return None
    _raw_message, exts = _ch_exts(datagram)
    return parsed[0], parsed[3], exts


def _cookie(datagram):
    handshake = _handshake(datagram)
    if handshake is None:
        return None
    value = handshake[2].get(dtlsproto.EXT_COOKIE)
    if value is None:
        return None
    return value[2:2 + int.from_bytes(value[0:2], "big")]


def _logical_key(datagram):
    """One entry per logical flight: retransmissions of a
    plaintext handshake message key on the message itself
    (the record sequence bytes advance between sends);
    protected datagrams key on their bytes."""
    handshake = _handshake(datagram)
    if handshake is not None:
        return ("hs", handshake[1])
    return ("dg", datagram)


def _logical_sequence(run):
    seen = set()
    sequence = []
    for entry in run["files"]:
        datagram = parse_message(_raw(entry)).datagram
        key = _logical_key(datagram)
        if key in seen:
            continue
        seen.add(key)
        sequence.append(datagram)
    return sequence


def _by_role(run, role):
    return [entry for entry in run["files"]
            if entry["role"] == role]


class RecordedLiveRunsTest(unittest.TestCase):
    def test_the_fixtures_match_the_recorded_manifest(self):
        self.assertEqual(sorted(RUNS), ["run1", "run4"])
        counts = {"run1": 18, "run4": 38}
        for name, run in sorted(RUNS.items()):
            with self.subTest(run=name):
                self.assertEqual(len(run["files"]), counts[name])
                on_disk = sorted(
                    f for f in os.listdir(FIXTURES)
                    if f.startswith(name + "-")
                    and f.endswith(".eml"))
                self.assertEqual(
                    on_disk,
                    sorted(e["file"] for e in run["files"]))
                for entry in run["files"]:
                    raw = _raw(entry)
                    self.assertEqual(
                        hashlib.sha384(raw).hexdigest(),
                        entry["fixture_sha384"], entry["file"])

    def test_every_recorded_mail_parses_as_a_flight_of_its_session(
            self):
        for name, run in sorted(RUNS.items()):
            session = run["session_id"]
            for entry in run["files"]:
                with self.subTest(run=name, file=entry["file"]):
                    raw = _raw(entry)
                    self.assertEqual(
                        _subject(raw), flight_subject(session))
                    parsed = parse_message(raw)
                    self.assertEqual(parsed.session_id, session)
                    self.assertIsNotNone(parsed.datagram)
                    role = entry["role"]
                    if role.startswith(
                            ("client-hello", "cookied-client-hello")):
                        self.assertEqual(parsed.kind, "dtls-init")
                    else:
                        self.assertEqual(parsed.kind, "dtls")
                    handshake = _handshake(parsed.datagram)
                    if role.startswith("client-hello"):
                        self.assertIsNotNone(handshake)
                        self.assertEqual(
                            handshake[0], dtlsproto.HS_CLIENT_HELLO)
                        self.assertIsNone(_cookie(parsed.datagram))
                    elif role.startswith("cookied-client-hello"):
                        self.assertIsNotNone(handshake)
                        self.assertEqual(
                            handshake[0], dtlsproto.HS_CLIENT_HELLO)
                        cookie = _cookie(parsed.datagram)
                        self.assertIsNotNone(cookie)
                        self.assertEqual(len(cookie), 64)
                    elif role.startswith("hello-retry-request"):
                        self.assertIsNotNone(handshake)
                        cookie = _cookie(parsed.datagram)
                        self.assertIsNotNone(cookie)
                        self.assertEqual(len(cookie), 64)
                    elif role == "server-hello":
                        self.assertIsNotNone(handshake)
                        self.assertIsNone(_cookie(parsed.datagram))

    def test_the_handshake_sequence_assembles_in_recorded_order(
            self):
        for name, run in sorted(RUNS.items()):
            with self.subTest(run=name):
                sequence = _logical_sequence(run)
                # The first ClientHello: no cookie extension.
                hello = _handshake(sequence[0])
                self.assertIsNotNone(hello)
                self.assertEqual(
                    hello[0], dtlsproto.HS_CLIENT_HELLO)
                self.assertIsNone(_cookie(sequence[0]))
                # The HelloRetryRequest: the engine's own
                # deterministic bytes for its cookie, and the
                # cookie binds the first hello by SHA-384.
                cookie = _cookie(sequence[1])
                self.assertIsNotNone(cookie)
                self.assertEqual(len(cookie), 64)
                self.assertEqual(
                    hashlib.sha384(hello[1]).digest(), cookie[:48])
                self.assertEqual(
                    sequence[1],
                    dtlsproto._plaintext_record(
                        dtlsproto.CT_HANDSHAKE, 0, 0,
                        dtlsproto._hello_retry_request(cookie)))
                # The cookied ClientHello carries the same
                # cookie back, whole.
                second = _handshake(sequence[2])
                self.assertIsNotNone(second)
                self.assertEqual(
                    second[0], dtlsproto.HS_CLIENT_HELLO)
                self.assertEqual(_cookie(sequence[2]), cookie)
                # The ServerHello follows; after it, every
                # logical flight is a protected record, except
                # retransmissions of that same ServerHello.
                server_hello = _handshake(sequence[3])
                self.assertIsNotNone(server_hello)
                self.assertIsNone(_cookie(sequence[3]))
                for datagram in sequence[4:]:
                    later = _handshake(datagram)
                    if later is not None:
                        self.assertEqual(later[1], server_hello[1])

    def test_the_job_and_result_flights_bind_to_their_session(
            self):
        for name, run in sorted(RUNS.items()):
            with self.subTest(run=name):
                files = run["files"]
                roles = [entry["role"] for entry in files]
                job_at = roles.index("job-flight")
                result_at = roles.index("result-flight")
                # The job crossed only after the client's own
                # flight (the session stood established), and
                # the result flight is the run's last mail.
                self.assertGreater(
                    job_at, roles.index("client-flight"))
                self.assertEqual(result_at, len(files) - 1)
                self.assertLess(job_at, result_at)
                for at, sender in ((job_at, "client"),
                                   (result_at, "server")):
                    entry = files[at]
                    self.assertEqual(entry["direction"], sender)
                    parsed = parse_message(_raw(entry))
                    self.assertEqual(parsed.kind, "dtls")
                    self.assertEqual(
                        parsed.session_id, run["session_id"])
                    self.assertIsNone(_handshake(parsed.datagram))
                if "job_envelope_bytes" in run:
                    # The recorded payload sizes plus the
                    # record overhead are the recorded
                    # datagram sizes, for both flights.
                    job = parse_message(
                        _raw(files[job_at])).datagram
                    result = parse_message(
                        _raw(files[result_at])).datagram
                    self.assertEqual(
                        len(job) - run["job_envelope_bytes"], 31)
                    self.assertEqual(
                        len(result) - run["result_payload_bytes"],
                        31)


if __name__ == "__main__":
    unittest.main()
