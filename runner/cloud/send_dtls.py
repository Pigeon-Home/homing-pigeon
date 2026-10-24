#!/usr/bin/env python3
"""Cloud-side client for the DTLS session binding
(a binding of protocol version 1).

Signs a job exactly as send_job.py does, opens a DTLS 1.3
session to the runner's dtls transport extension, prints the
runner's greeting (the session's first application message,
sent only after the handshake authenticates), sends the job
inside the session, and prints the result that returns on it.

The shared secret does double duty here, by design: it is the
HMAC key that signs the job AND the external PSK that
authenticates the session. The session adds confidentiality
and forward secrecy (psk_dhe_ke only -- see
runner/wire/dtlsproto.py); the signature stays the authorization,
exactly as on every other binding. A per-job encrypted job
(the hp_enc envelope) composes with the session unchanged:
--encrypt is the default, --cleartext selects the plain
signed form.

Usage:
    python3 send_dtls.py --host 192.0.2.10 --secret <secret> \
        --kind ping
    python3 send_dtls.py --host host.example --port 20220 \
        --secret <secret> --kind exec --script-file job.sh \
        --ticket-file ~/.hp-dtls-ticket.json

Exit codes: 0 result printed; 2 usage/secret problem;
3 timed out waiting; 4 the handshake failed; 5 the result did
not verify or decrypt.
"""

import argparse
import base64
import json
import os
import select
import socket
import sys
import time
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
# runner/cloud/ -> the tree that holds the runner package
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from send_job import (PROTOCOL_VERSION, require_signable_secret,  # noqa: E402
                      sign_payload, verify_body)
from runner.wire import dtlsproto, jobcrypto  # noqa: E402

DEFAULT_PORT = 20220


def _load_ticket(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return (base64.b64decode(data["ticket"]),
                base64.b64decode(data["psk"]))
    except Exception:
        return None


def _save_ticket(path, ticket):
    if not path or ticket is None:
        return
    data = {"ticket": base64.b64encode(ticket[0]).decode("ascii"),
            "psk": base64.b64encode(ticket[1]).decode("ascii")}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _build_body(args):
    payload = {
        "v": PROTOCOL_VERSION,
        "type": "job",
        "job_id": args.job_id or str(uuid.uuid4()),
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": args.kind,
    }
    if args.key_id:
        payload["key_id"] = args.key_id
    if args.kind == "exec":
        if args.script_file:
            with open(args.script_file, encoding="utf-8") as f:
                payload["script"] = f.read()
        if not payload.get("script"):
            print("exec jobs need --script-file", file=sys.stderr)
            return None, None
        payload["timeout_sec"] = args.timeout
    body = sign_payload(payload, args.secret)
    if not args.cleartext:
        body = jobcrypto.encrypt_body(body, args.secret,
                                      payload["job_id"],
                                      args.key_id, sign_payload)
    envelope = f"[HOMING-PIGEON] job {payload['job_id']}\n\n{body}"
    if not envelope.endswith("\n"):
        envelope += "\n"
    return payload["job_id"], envelope.encode("utf-8")


def _pump(sock, client, deadline):
    """Drive the client core until it produces a state change
    the caller waits on; returns False on timeout/death."""
    while time.monotonic() < deadline:
        for dg in client.tick(time.monotonic()):
            sock.send(dg)
        ready, _, _ = select.select([sock], [], [], 0.25)
        if not ready:
            continue
        try:
            data = sock.recv(65535)
        except OSError:
            continue
        for dg in client.feed(data, time.monotonic()):
            sock.send(dg)
        return True
    return False


def _wait_for(sock, client, predicate, deadline):
    while not predicate():
        if client.dead:
            return False
        if not _pump(sock, client, deadline):
            return predicate()
    return True


def _plain_result(text, secret, job_id, key_id):
    """A result envelope's signed body, decrypted first when
    the result mirrors an encrypted job's hp_enc form."""
    head, sep, body = text.replace("\r\n", "\n").partition("\n\n")
    if not sep:
        return None, "result is not an envelope"
    try:
        payload = verify_body(body.strip(), secret)
    except Exception as e:
        return None, f"result signature does not verify: {e}"
    if jobcrypto.is_envelope(payload):
        try:
            inner = jobcrypto.decrypt_body(
                payload, secret, job_id,
                payload.get("key_id") or key_id)
            payload = verify_body(inner.strip(), secret)
        except Exception as e:
            return None, f"result does not decrypt: {e}"
    return (head.strip(), payload), None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Send one signed job over the DTLS binding "
                    "and print its result.")
    ap.add_argument("--host", required=True,
                    help="the runner host running the dtls "
                         "transport extension")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"UDP port (default {DEFAULT_PORT})")
    ap.add_argument("--secret", required=True,
                    help="the shared secret (signs the job and "
                         "authenticates the session as its PSK)")
    ap.add_argument("--key-id", default=None,
                    help="sign with an additional secret named "
                         "by this key id")
    ap.add_argument("--kind", default="ping",
                    help="job kind (default ping)")
    ap.add_argument("--script-file",
                    help="script text for --kind exec")
    ap.add_argument("--timeout", type=int, default=300,
                    help="job timeout_sec for exec (default 300)")
    ap.add_argument("--job-id", default=None)
    ap.add_argument("--wait", type=float, default=120.0,
                    help="seconds to wait for the result "
                         "(default 120)")
    enc = ap.add_mutually_exclusive_group()
    enc.add_argument("--encrypt", dest="cleartext",
                     action="store_false",
                     help="per-job encrypt the job (default)")
    enc.add_argument("--cleartext", dest="cleartext",
                     action="store_true",
                     help="send the plain signed job instead")
    ap.add_argument("--ticket-file",
                    help="persist the resumption ticket here "
                         "and reuse it on the next run (0600)")
    args = ap.parse_args(argv)

    secret = args.secret
    try:
        require_signable_secret(secret)
    except Exception as e:
        print(f"secret refused: {e}", file=sys.stderr)
        return 2
    built = _build_body(args)
    if built[0] is None:
        return 2
    job_id, envelope = built

    ticket = _load_ticket(args.ticket_file)
    client = dtlsproto.DtlsClientCore(
        secret, key_id=args.key_id, ticket=ticket,
        log=lambda m, level="INFO": print(f"{level}: {m}",
                                          file=sys.stderr))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect((args.host, args.port))
    deadline = time.monotonic() + args.wait
    try:
        for dg in client.start(time.monotonic()):
            sock.send(dg)
        ok = _wait_for(sock, client,
                       lambda: client.greeting is not None
                       or client.app_messages,
                       deadline)
        if client.dead or not ok:
            print("the DTLS handshake failed or timed out",
                  file=sys.stderr)
            return 4
        print(json.dumps(client.greeting, indent=1, sort_keys=True))
        for dg in client.send_app(envelope):
            sock.send(dg)
        before = len(client.app_messages)
        ok = _wait_for(sock, client,
                       lambda: len(client.app_messages) > before,
                       deadline)
        if not ok:
            print("timed out waiting for the result",
                  file=sys.stderr)
            return 3
        result_text = client.app_messages[before].decode(
            "utf-8", "replace")
        plain, err = _plain_result(result_text, secret, job_id,
                                   args.key_id)
        if plain is None:
            print(err, file=sys.stderr)
            print(result_text)
            return 5
        subject, payload = plain
        print(subject)
        print(json.dumps(payload, indent=1, sort_keys=True))
        _save_ticket(args.ticket_file, client.ticket)
        return 0
    except dtlsproto.DtlsError as e:
        print(f"DTLS session failed: {e}", file=sys.stderr)
        return 4
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
