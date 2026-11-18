# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Tunnel chaining over air gaps: the chain hop and its relay.

The design record is docs/steady/design/tunnel-chaining-design.md
and the working record, with the supposition this suite answers,
is docs/infrastructure-documents/project/tunnel-chaining-2026-11-17.md.
This file pins the pass's proof:

- Wire level: a chain body seals and opens under its hop
  secret; a tampered envelope, a tampered signature, the wrong
  hop secret, and the wrong subject id are each refused; the
  structural checks refuse a body that is not a hop; bookended
  garbage never opens into a different payload.
- The relay cannot read the carried job: the final hop's
  envelope does not open under the relay's hop secret.
- Runner level, over two file transport fixtures: a 2 hop
  chain traverses (the relay forwards the job envelope byte
  for byte, the final runner runs the job, the result opens
  under the final hop's secret); a tampered chain envelope is
  refused with an auth_rejection in the security events and
  nothing forwarded; a replayed chain envelope is answered by
  the replay cache and not forwarded again; a chain under a
  key the relay does not hold, and a stale chain, are refused.
"""

import os
import shutil
import string
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import poll_once  # noqa: E402
from runner.transport_extensions.file import (  # noqa: E402
    __main__ as file_ext)
from runner.wire import chain as wire_chain  # noqa: E402
from runner.wire import jobcrypto, transports  # noqa: E402
from runner.wire.verify import (  # noqa: E402
    build_secrets, sign_payload, verify_body_keyed)

# Test secrets at full strength, derived from fixed seeds so
# no credential shaped literal sits in the file.
import hashlib  # noqa: E402

HOP1_SECRET = hashlib.sha384(b"chain test hop one").hexdigest()
HOP2_SECRET = hashlib.sha384(b"chain test hop two").hexdigest()
RELAY_SECRET = hashlib.sha384(b"chain test relay own").hexdigest()
SENDER = "runner@example.com"


def _now(offset_sec=0):
    when = datetime.now(timezone.utc) + timedelta(seconds=offset_sec)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _seal_job(jid, secret):
    """A ping job sealed for its runner, the standing envelope
    discipline, built by hand the way send_job builds it."""
    job = {"v": 1, "type": "job", "job_id": jid,
           "issued_at": _now(), "kind": "ping",
           "result_policy": {"view": "full"}}
    signed = sign_payload(job, secret)
    body = jobcrypto.encrypt_body(signed, secret, job_id=jid,
                                  key_id="", sign=sign_payload)
    return f"[HOMING-PIGEON] job {jid}", body


def _open_result(text, secret, jid):
    subject, body = transports.parse_envelope(text)
    payload, key_id = verify_body_keyed(body, {"": secret})
    inner = jobcrypto.decrypt_body(payload, secret, job_id=jid,
                                   key_id="")
    result, _ = verify_body_keyed(inner, {"": secret})
    return result


class WireChainTest(unittest.TestCase):
    def setUp(self):
        self.secrets = build_secrets({
            "shared_secret": RELAY_SECRET,
            "additional_secrets": {"hop1": HOP1_SECRET}})
        self.jid = str(uuid.uuid4())
        self.job_subject, self.job_body = _seal_job(
            self.jid, HOP2_SECRET)

    def _seal(self, **kw):
        return wire_chain.seal_chain(
            kw.pop("chain_id", "chain-1"), self.job_subject,
            self.job_body, HOP1_SECRET, key_id="hop1", **kw)

    def test_seal_and_open_round_trip(self):
        subject, body = self._seal()
        self.assertEqual(subject, "[HOMING-PIGEON] chain chain-1")
        payload, key_id, secret, encrypted = \
            wire_chain.open_chain_body(body, self.secrets,
                                       "chain-1")
        self.assertTrue(encrypted)
        self.assertEqual(key_id, "hop1")
        self.assertEqual(payload["type"], "chain")
        self.assertEqual(payload["chain_id"], "chain-1")
        self.assertEqual(payload["next_subject"], self.job_subject)
        self.assertEqual(payload["next_body"], self.job_body)
        self.assertIsNone(wire_chain.validate_chain_body(
            payload, "chain-1"))

    def test_open_under_a_different_subject_id_is_refused(self):
        _, body = self._seal()
        with self.assertRaises(ValueError):
            wire_chain.open_chain_body(body, self.secrets,
                                       "chain-2")

    def test_tampered_ciphertext_is_refused(self):
        _, body = self._seal()
        at = body.index('"ct":"') + 6
        flip = "A" if body[at] != "A" else "B"
        tampered = body[:at] + flip + body[at + 1:]
        with self.assertRaises(ValueError):
            wire_chain.open_chain_body(tampered, self.secrets,
                                       "chain-1")

    def test_tampered_signature_is_refused(self):
        _, body = self._seal()
        at = body.rindex('"sig":"') + 7
        flip = "0" if body[at] != "0" else "1"
        tampered = body[:at] + flip + body[at + 1:]
        with self.assertRaises(ValueError):
            wire_chain.open_chain_body(tampered, self.secrets,
                                       "chain-1")

    def test_the_wrong_hop_secret_is_refused(self):
        _, body = self._seal()
        wrong = build_secrets({
            "shared_secret": RELAY_SECRET,
            "additional_secrets": {"hop1": HOP2_SECRET}})
        with self.assertRaises(ValueError):
            wire_chain.open_chain_body(body, wrong, "chain-1")

    def test_an_unknown_key_id_is_refused(self):
        subject, body = wire_chain.seal_chain(
            "chain-1", self.job_subject, self.job_body,
            HOP1_SECRET, key_id="hop9")
        with self.assertRaises(ValueError):
            wire_chain.open_chain_body(body, self.secrets,
                                       "chain-1")

    def test_validate_refuses_a_body_that_is_not_a_hop(self):
        base = {"v": 1, "type": "chain", "chain_id": "chain-1",
                "issued_at": _now(),
                "next_subject": self.job_subject,
                "next_body": self.job_body}
        self.assertIsNone(wire_chain.validate_chain_body(
            base, "chain-1"))
        for change in ({"type": "job"},
                       {"chain_id": "chain-2"},
                       {"next_subject": ""},
                       {"next_body": ""},
                       {"next_subject": "a plain note"},
                       {"next_body": 42}):
            bad = dict(base, **change)
            self.assertIsNotNone(
                wire_chain.validate_chain_body(bad, "chain-1"),
                change)

    def test_a_chain_may_carry_another_chain(self):
        inner_subject, inner_body = self._seal(chain_id="chain-2")
        payload = wire_chain.build_chain_body(
            "chain-1", inner_subject, inner_body, key_id="hop1")
        self.assertIsNone(wire_chain.validate_chain_body(
            payload, "chain-1"))

    def test_bookended_garbage_never_opens_wrong(self):
        # The bookend rule: every ASCII symbol, plus the
        # non-printing edge cases, at the front and the back.
        # A bookended body either refuses outright or, where the
        # mail path's standing control tolerance cleans it, opens
        # into exactly the payload that was sealed. It never
        # opens into a different payload and never raises
        # anything but ValueError.
        _, body = self._seal()
        bookends = list(string.punctuation) + [
            "\x00", "\t", "\r", "\n", " ", "\x0b", "\x0c",
            "--", ";;", '""', "/*", "*/", "<!--", "%00"]
        for mark in bookends:
            for wrapped in (mark + body, body + mark,
                            mark + body + mark):
                try:
                    payload, _, _, _ = wire_chain.open_chain_body(
                        wrapped, self.secrets, "chain-1")
                except ValueError:
                    continue
                self.assertEqual(payload["chain_id"], "chain-1")
                self.assertEqual(payload["next_body"],
                                 self.job_body)

    def test_the_relay_cannot_read_the_carried_job(self):
        # The relay's whole key map: its own default and the
        # first hop's secret. The carried job envelope, sealed
        # under the final hop's secret, opens under neither.
        payload, _ = verify_body_keyed(
            self.job_body, {"": HOP2_SECRET})
        for secret in (RELAY_SECRET, HOP1_SECRET):
            with self.assertRaises(jobcrypto.JobCryptoError):
                jobcrypto.decrypt_body(payload, secret,
                                       job_id=self.jid, key_id="")


class _RunnerBox:
    """One runner on the file transport, the operator path
    fixture's shape: a watched folder, a channel, poll_once."""

    def __init__(self, root, name, cfg_extra):
        self.base = os.path.join(root, name, "state")
        os.makedirs(self.base)
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "poll_interval_sec": 20,
            "max_job_age_sec": 3600,
            "max_output_bytes": 100000,
            "max_result_view": "full",
            "base_dir": self.base,
            "default_timeout_sec": 300,
            "transports": ["file"],
            "security": {"modes": {"confinement": "off",
                                   "job_user": "off",
                                   "audience": "enforce"}},
        }
        self.cfg.update(cfg_extra)
        self.seen = {}
        self.seen_path = os.path.join(root, name, "seen.json")
        paths = transports.channel_paths(self.base, "file")
        transports.ensure_channel_dirs(self.base, "file")
        self.pipe = file_ext.FilePipe(
            {"base_dir": self.base,
             "inbox": "transport-file/inbox",
             "outbox": "transport-file/outbox"},
            paths["root"])

    def cycle(self):
        self.pipe.scan_jobs()
        poll_once(self.cfg, self.base, self.seen, self.seen_path)
        self.pipe.scan_results()

    def drop(self, fname, subject, body):
        path = os.path.join(self.pipe.inbox, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(transports.format_envelope(subject, body))
        return path

    def outbox_files(self):
        return sorted(os.listdir(self.pipe.outbox))

    def read_outbox(self, fname):
        with open(os.path.join(self.pipe.outbox, fname),
                  encoding="utf-8") as f:
            return f.read()

    def security_events(self):
        path = os.path.join(self.base, "security-events.jsonl")
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()


class TwoHopChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-chain-")
        self.addCleanup(shutil.rmtree, self.tmp,
                        ignore_errors=True)
        self.relay = _RunnerBox(self.tmp, "relay", {
            "shared_secret": RELAY_SECRET,
            "additional_secrets": {"hop1": HOP1_SECRET}})
        self.final = _RunnerBox(self.tmp, "final", {
            "shared_secret": HOP2_SECRET})
        self.jid = str(uuid.uuid4())
        self.job_subject, self.job_body = _seal_job(
            self.jid, HOP2_SECRET)
        self.chain_subject, self.chain_body = \
            wire_chain.seal_chain("chain-1", self.job_subject,
                                  self.job_body, HOP1_SECRET,
                                  key_id="hop1")

    def _carry(self, src_box, fname, dst_box, as_name):
        text = src_box.read_outbox(fname)
        with open(os.path.join(dst_box.pipe.inbox, as_name),
                  "w", encoding="utf-8") as f:
            f.write(text)
        return text

    def test_two_hop_traversal(self):
        self.relay.drop("chain-1.txt", self.chain_subject,
                        self.chain_body)
        self.relay.cycle()
        # The relay forwarded exactly one envelope, the job
        # envelope byte for byte, and ran nothing itself.
        out = self.relay.outbox_files()
        self.assertEqual(len(out), 1, out)
        subject, body = transports.parse_envelope(
            self.relay.read_outbox(out[0]))
        self.assertEqual(subject, self.job_subject)
        # The carried envelope byte for byte, up to the one
        # trailing newline the mail envelope round trip adds,
        # the tolerance every envelope in the suite travels
        # with.
        self.assertEqual(body.rstrip("\n"), self.job_body)
        self.assertFalse(os.path.exists(
            os.path.join(self.relay.base, "work", self.jid)))
        # Carried media: the file moves to the final runner.
        self._carry(self.relay, out[0], self.final,
                    "carried-1.txt")
        self.final.cycle()
        out = self.final.outbox_files()
        self.assertEqual(out, [self.jid + ".result.txt"], out)
        result = _open_result(self.final.read_outbox(out[0]),
                              HOP2_SECRET, self.jid)
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["job_id"], self.jid)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)

    def test_tampered_chain_is_refused_and_logged(self):
        at = self.chain_body.index('"ct":"') + 6
        flip = "A" if self.chain_body[at] != "A" else "B"
        tampered = self.chain_body[:at] + flip + \
            self.chain_body[at + 1:]
        self.relay.drop("chain-1.txt", self.chain_subject,
                        tampered)
        self.relay.cycle()
        self.assertEqual(self.relay.outbox_files(), [])
        self.assertIn("auth_rejection",
                      self.relay.security_events())
        # Taken, so the poison file cannot wedge the channel.
        self.assertIn("chain-1.txt", os.listdir(
            os.path.join(self.relay.pipe.inbox, "done")))

    def test_replayed_chain_is_not_forwarded_again(self):
        self.relay.drop("chain-1.txt", self.chain_subject,
                        self.chain_body)
        self.relay.cycle()
        self.assertEqual(len(self.relay.outbox_files()), 1)
        # The same envelope arrives again on later media, under
        # a new file name, as a replay on carried media does.
        self.relay.drop("chain-1-again.txt", self.chain_subject,
                        self.chain_body)
        self.relay.cycle()
        self.assertEqual(len(self.relay.outbox_files()), 1)

    def test_a_chain_under_an_unknown_key_is_refused(self):
        subject, body = wire_chain.seal_chain(
            "chain-1", self.job_subject, self.job_body,
            HOP1_SECRET, key_id="hop9")
        self.relay.drop("chain-1.txt", subject, body)
        self.relay.cycle()
        self.assertEqual(self.relay.outbox_files(), [])
        self.assertIn("auth_rejection",
                      self.relay.security_events())

    def test_a_stale_chain_is_refused(self):
        subject, body = wire_chain.seal_chain(
            "chain-1", self.job_subject, self.job_body,
            HOP1_SECRET, key_id="hop1", issued_at=_now(-7200))
        self.relay.drop("chain-1.txt", subject, body)
        self.relay.cycle()
        self.assertEqual(self.relay.outbox_files(), [])


if __name__ == "__main__":
    unittest.main()
