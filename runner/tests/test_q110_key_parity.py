# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Q110: the key-parity probes -- one family, every door.

The coverage seat's parity proof (the forum, 28-Oct): every door
walked with a superseded key expects the same refusal. The doors
are the mailbox, the five transport channels (email, file, nats,
dtls, queues), the board, the query door, protocol v2, the hosted
queue's Worker, and the DTLS resumption ticket.

"Superseded" is operationalized the way a rotation leaves the
world: the runner's current key map (build_secrets over the
current config) no longer holds the old key under any name, while
the sender still holds it and signs with it under its key id
"old". That is the state the key directory's refusal has to
produce at every door, whatever shape the directory takes; this
family does not build the directory, does not decide it, and does
not presume its config shape.

Honest accounting of what fails today, and why:

- Every signed-object door already refuses the superseded key,
  because admission runs through the one keyed verifier and the
  key is simply not in the map. Those probes pass unmarked; they
  are the parity the odd door is measured against.
- The DTLS resumption ticket is the exception, and both resume
  probes are @unittest.expectedFailure naming Q110. A ticket
  records no key id at issue (the ticket table in
  runner/wire/dtlsproto.py maps ticket bytes to (psk, expiry)
  only), so a resume never consults the key map at all: a resume
  carrying no key id is accepted, and a ticket issued by a key
  that has since been superseded still resumes after that key
  leaves the map. The body signature still refuses such a
  session's jobs, so this is a parity gap, not a hole. When the
  directory lands, the desk removes these two markers in the fix
  commit; if the fix makes tickets carry their issuing key id,
  the no-key-id probe is re-pointed at a ticket with no recorded
  key in that commit.

The two controls at the top prove the rig is not vacuous: the
current key is answered at the mailbox, and the old key was
answered while it still stood in the map.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
if os.path.join(REPO, "runner", "cloud") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner import runner as R  # noqa: E402
from runner.wire import dtlsproto, jobcrypto, protocol_v2 as v2  # noqa: E402
from runner.wire import transports  # noqa: E402
from send_job import sign_payload  # noqa: E402
from runner.tests.test_runner import (  # noqa: E402
    SECRET as CURRENT, FakeIMAP, FakeSMTP, job_email, job_payload)
OLD = "9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a"
SENDER = "runner@example.com"
CHANNELS = ("email", "file", "nats", "dtls", "queues")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cfg(base, **over):
    cfg = {
        "mailbox_user": SENDER,
        "mailbox_password": "test-password",
        "shared_secret": CURRENT,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "poll_interval_sec": 20,
        "max_job_age_sec": 3600,
        "max_output_bytes": 100000,
        "base_dir": base,
        "default_timeout_sec": 30,
        "workers": 1,
    }
    cfg.update(over)
    return cfg


def _result(sent_msg, secret, ident):
    """A sent result's signed inner body, read with the given key."""
    body = sent_msg.get_content()
    parsed = R.verify_body(body, secret)
    if jobcrypto.is_envelope(parsed):
        body = jobcrypto.decrypt_body(
            parsed, secret, ident, parsed.get("key_id") or "")
    return R.verify_body(body, secret)


def _sealed(obj, ident, secret, key_id=""):
    return jobcrypto.encrypt_body(
        sign_payload(obj, secret), secret, job_id=ident,
        key_id=key_id, sign=sign_payload)


def _mail(subject, body):
    msg = EmailMessage()
    msg["From"] = "si@example.com"
    msg["To"] = SENDER
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


class _Opts:
    dry_run = False
    no_send = False


class _Rig(unittest.TestCase):
    """A temp runner home whose key map holds only CURRENT."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q110-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = _cfg(self.tmp)
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, cfg=None):
        imap, smtp, seen = FakeIMAP(mails), FakeSMTP(), {}
        R.poll_once(cfg or self.cfg, self.tmp, seen, self.seen_path,
                    imap=imap, smtp=smtp)
        return imap, smtp, seen


class ControlsTest(_Rig):
    """The rig answers keys that stand; only supersession refuses."""

    def test_the_current_key_is_answered_at_the_mailbox(self):
        jid = "q110-control-current"
        _, smtp, seen = self.cycle([job_email(job_payload(jid))])
        self.assertEqual(len(smtp.sent), 1)
        result = _result(smtp.sent[0], CURRENT, jid)
        self.assertEqual(result["stdout"], "pong")
        self.assertIn(jid, seen)

    def test_the_old_key_was_answered_while_it_stood(self):
        cfg = _cfg(self.tmp, additional_secrets={"old": OLD})
        jid = "q110-control-old"
        _, smtp, _seen = self.cycle(
            [job_email(job_payload(jid, key_id="old"), secret=OLD)],
            cfg=cfg)
        self.assertEqual(len(smtp.sent), 1)
        result = _result(smtp.sent[0], OLD, jid)
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["key_id"], "old")


class MailboxParityTest(_Rig):
    """Q110, the mailbox door (the injected IMAP/SMTP path)."""

    def test_the_mailbox_refuses_the_superseded_key(self):
        jid = "q110-mailbox-1"
        _, smtp, seen = self.cycle(
            [job_email(job_payload(jid, key_id="old"), secret=OLD)])
        self.assertEqual(smtp.sent, [])
        self.assertNotIn(jid, seen)


class ChannelParityTest(_Rig):
    """Q110, the five channel doors: one envelope per transport
    channel, serviced by the core exactly as a poll cycle does."""

    def _channel_refuses(self, name):
        base = tempfile.mkdtemp(prefix=f"hp-q110-{name}-")
        self.addCleanup(shutil.rmtree, base, True)
        cfg = _cfg(base, transports=[name])
        secrets = R.build_secrets(cfg)
        policies = R.build_key_policies(cfg)
        paths = transports.ensure_channel_dirs(base, name)
        jid = f"q110-{name}-1"
        body = _sealed(job_payload(jid, key_id="old"), jid, OLD, "old")
        with open(os.path.join(paths["inbox"], jid + ".job.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write(f"[HOMING-PIGEON] job {jid}\n\n{body}\n")
        seen = {}
        R._service_transports(cfg, base, seen,
                              os.path.join(base, "seen.json"), [name],
                              secrets, policies, None)
        out = [f for f in os.listdir(paths["outbox"])
               if os.path.isfile(os.path.join(paths["outbox"], f))]
        self.assertEqual(out, [], name)
        self.assertNotIn(jid, seen, name)

    def test_the_email_channel_refuses_the_superseded_key(self):
        self._channel_refuses("email")

    def test_the_file_channel_refuses_the_superseded_key(self):
        self._channel_refuses("file")

    def test_the_nats_channel_refuses_the_superseded_key(self):
        self._channel_refuses("nats")

    def test_the_dtls_channel_refuses_the_superseded_key(self):
        self._channel_refuses("dtls")

    def test_the_queues_channel_refuses_the_superseded_key(self):
        self._channel_refuses("queues")


class BoardParityTest(_Rig):
    """Q110, the board door: a task_submit from the superseded key
    lands nothing on the board and is answered with silence."""

    def test_the_board_refuses_the_superseded_key(self):
        tid = "q110-task-1"
        payload = {"v": 1, "type": "task_submit", "task_id": tid,
                   "issued_at": _now(), "capabilities": [],
                   "key_id": "old"}
        raw = _mail(f"[HOMING-PIGEON] task_submit {tid}",
                    _sealed(payload, tid, OLD, "old"))
        _, smtp, _seen = self.cycle([raw])
        self.assertEqual(smtp.sent, [])
        board_path = os.path.join(self.tmp, "board.json")
        tasks = {}
        if os.path.exists(board_path):
            with open(board_path, encoding="utf-8") as fh:
                tasks = json.load(fh)
        self.assertNotIn(tid, tasks)


class QueryParityTest(_Rig):
    """Q110, the query door: no reply, and the retained record's
    budget is unspent."""

    def test_the_query_door_refuses_the_superseded_key(self):
        job_id, qid = "q110-job", "q110-query-1"
        R.save_retained(self.tmp, job_id, {
            "stdout": "one\ntwo\n", "stderr": "", "exit_code": 0,
            "budget": 8, "spent": 0, "view": "full", "key": "",
            "saved_at": time.time()})
        payload = {"v": 1, "type": "query", "query_id": qid,
                   "job_id": job_id, "issued_at": _now(),
                   "queries": [{"op": "tail", "lines": 1}],
                   "key_id": "old"}
        smtp = FakeSMTP()
        handled = R.handle_query_mail(
            self.cfg, FakeIMAP([]), smtp, b"1",
            _mail(f"[HOMING-PIGEON] query {qid}",
                  _sealed(payload, qid, OLD, "old")),
            f"[HOMING-PIGEON] query {qid}",
            R.build_secrets(self.cfg), _Opts(), self.tmp, {})
        self.assertTrue(handled)
        self.assertEqual(smtp.sent, [])
        self.assertEqual(R.load_retained(self.tmp, job_id)["spent"], 0)


class V2ParityTest(_Rig):
    """Q110, the protocol v2 door: an answer signed by the
    superseded key is not stored."""

    def test_the_v2_door_refuses_the_superseded_key(self):
        cfg = _cfg(self.tmp, protocol_v2=True, v2_answerers=[""])
        question = v2.question_for(
            {"protocol_v2": True, "oracle_mode": "deterministic"},
            {"job_id": "q110-job", "kind": "exec", "script": "echo ok"})
        ans = dict(v2.answer_for(question, "proceed"), key_id="old")
        raw = _mail("[HOMING-PIGEON] answer " + ans["msg_id"],
                    _sealed(ans, ans["msg_id"], OLD, "old"))
        self.cycle([raw], cfg=cfg)
        stored = []
        for root, _dirs, files in os.walk(os.path.join(self.tmp, "v2")):
            stored.extend(files)
        self.assertEqual(stored, [])


_WORKER_SCRIPT = r"""
import worker, { TenantQueue } from "./src/index.js";
import fs from "node:fs";
const [recPath, slug, si, runner, envelope] =
  JSON.parse(fs.readFileSync(0, "utf8"));
class Store { constructor() { this.m = new Map(); }
  async get(k) { return this.m.has(k) ? structuredClone(this.m.get(k)) : undefined; }
  async put(k, v) { this.m.set(k, structuredClone(v)); }
  async delete(k) { return this.m.delete(k); }
  async list({ prefix = "", limit = Infinity } = {}) { const o = new Map();
    for (const k of [...this.m.keys()].sort()) { if (o.size >= limit) break;
      if (k.startsWith(prefix)) o.set(k, structuredClone(this.m.get(k))); } return o; } }
const objs = new Map();
const env = { TENANTS: { async get(k) { return k === slug ? fs.readFileSync(recPath, "utf8") : null; } },
  TENANT_QUEUE: { idFromName: (n) => n, get(id) { if (!objs.has(id)) objs.set(id, new TenantQueue({ storage: new Store() }, env)); return objs.get(id); } } };
const call = (path, method, token, body) => worker.fetch(
  new Request("https://w.test" + path,
    { method, body, headers: { authorization: "Bearer " + token } }), env);
const out = [];
out.push((await call(`/t/${slug}/jobs`, "POST", si, envelope)).status);
out.push((await call(`/t/${slug}/jobs`, "GET", runner)).status);
console.log(JSON.stringify(out));
"""


def _node():
    """The node binary, or None. Probed lazily inside the test:
    shutil.which touches the Windows API surface at import time
    under the guard's simulated Windows run and raises there, so
    it must not be evaluated while the module is being defined."""
    try:
        return shutil.which("node")
    except Exception:
        return None


class WorkerParityTest(_Rig):
    """Q110, the hosted queue's Worker: the tenant record has
    rotated to the current secret, so a job signed with the
    superseded one is refused at the edge (403) and nothing is
    queued for the runner to pull (204)."""

    def test_the_worker_refuses_the_superseded_key(self):
        if _node() is None:
            self.skipTest("node is not installed")
        si, runner_token = "q110-si-token", "q110-runner-token"
        record = {
            "si_token_sha256": hashlib.sha256(
                si.encode("utf-8")).hexdigest(),
            "runner_token_sha256": hashlib.sha256(
                runner_token.encode("utf-8")).hexdigest(),
            "hmac_secret": CURRENT,
            "quota": {"jobs_per_hour": 10, "bytes_per_day": 1000000},
        }
        rec_path = os.path.join(self.tmp, "alice.kv.json")
        with open(rec_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh)
        jid = "q110-worker-1"
        body = sign_payload(
            {"v": 1, "type": "job", "job_id": jid, "kind": "ping"}, OLD)
        envelope = f"[HOMING-PIGEON] job {jid}\n\n{body}\n"
        worker_dir = os.path.join(REPO, "runner", "cloud", "queues-worker")
        script = os.path.join(self.tmp, "q110-roundtrip.mjs")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(_WORKER_SCRIPT.replace(
                "./src/index.js",
                Path(worker_dir, "src", "index.js").resolve().as_uri()))
        r = subprocess.run(
            ["node", script], capture_output=True, text=True, timeout=60,
            input=json.dumps([rec_path, "alice", si, runner_token,
                              envelope]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), [403, 204])


# ------------------------------------------------------------------
# The DTLS resume door (Q110's odd door, in this same family)
# ------------------------------------------------------------------

ADDR = ("127.0.0.1", 50001)
NOW = 1000.0


def _pump(client, server, addr=ADDR, now=NOW):
    """Shuttle datagrams between two cores until quiet."""
    out = client.start(now)
    for _ in range(60):
        if not out:
            break
        nxt = []
        for dg in out:
            nxt += server.feed(dg, addr, now)
        out = []
        for dg in nxt:
            out += client.feed(dg, now)
    return out


class DtlsResumeParityTest(unittest.TestCase):
    """Q110, the DTLS door. The baseline first: a fresh handshake
    naming the superseded key is refused by the ordinary secret
    lookup, exactly like every other door. The two resume probes
    below it are the family's expected failures."""

    def _established(self, server):
        client = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(client, server)
        self.assertEqual(client.state, "established")
        self.assertIsNotNone(client.ticket)
        return client

    def _resumed_events(self, server, before):
        return [e for e in server.events[before:]
                if e[0] == "established" and e[2].get("resumed")]

    def test_a_fresh_handshake_naming_the_superseded_key_is_refused(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(CURRENT))
        client = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(client, server)
        self.assertNotEqual(client.state, "established")
        self.assertFalse(any(e[0] == "established"
                             for e in server.events))

    # Q110: a resume carrying no key id is refused, same as a
    # superseded key. Today the ticket table hit comes first and
    # the resume is accepted; the marker comes off in the fix
    # commit that makes a resume check its issuing key.
    @unittest.expectedFailure
    def test_a_resume_carrying_no_key_id_is_refused(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(
                CURRENT, {"old": OLD}),
            greeting_for=lambda s: b'{"type":"greeting","v":1}')
        first = self._established(server)
        before = len(server.events)
        # The resuming client presents only the ticket: it names
        # no key, and the ticket it carries records none either.
        client = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        _pump(client, server)
        self.assertEqual(self._resumed_events(server, before), [])

    # Q110: a ticket issued by a key that has since been
    # superseded stops resuming once that key leaves the map.
    # Today the ticket table never consults the map, so the
    # resume below is accepted; expectedFailure until the fix.
    @unittest.expectedFailure
    def test_a_resume_whose_issuing_key_was_superseded_is_refused(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(
                CURRENT, {"old": OLD}),
            greeting_for=lambda s: b'{"type":"greeting","v":1}')
        first = self._established(server)
        # Rotation: the runner's key map no longer holds "old".
        # (make_secret_lookup over the new config is exactly the
        # lookup the transport is handed; the ticket table, in
        # the same live process, is untouched.)
        server._secret_lookup = dtlsproto.make_secret_lookup(CURRENT)
        before = len(server.events)
        client = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        _pump(client, server)
        self.assertEqual(self._resumed_events(server, before), [])


if __name__ == "__main__":
    unittest.main()
