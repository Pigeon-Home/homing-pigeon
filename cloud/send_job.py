#!/usr/bin/env python3
"""Cloud-side helper for homing-pigeon (see PROTOCOL.md).

Builds signed job emails and verifies signed result emails using the
exact same signature scheme as runner/runner.py:

    sig = HEX(HMAC_SHA384(secret, payload_json_with_LF_line_endings))
    body = payload_json with the trailing "}" replaced by ',"sig":"<sig>"}'

The --secret is the shared secret string, used directly (UTF-8) as the
HMAC-SHA-384 key. In this deployment it is the runner's Gmail app password
itself (user's explicit choice: dedicated throwaway account). This helper
is SI-agnostic: anything that can run it and send the resulting email as
the runner's Gmail account — any SI, a cron job — can drive
the runner. Keep the secret out of logs and files; pass it only when needed.

Usage:
    python3 send_job.py new --kind ping --secret <hex-or-text-secret>
    python3 send_job.py new --kind exec --script-file job.ps1 --timeout 300 \\
        --file input.csv=https://... --secret <secret>
    python3 send_job.py verify --secret <secret> < result_email_body.txt

`new` prints the email subject on the first line, a blank line, then the body.
`verify` reads a signed body from stdin (or a file), verifies it, and pretty-prints.
"""

import argparse
import hashlib
import hmac
import json
import sys
import uuid
from datetime import datetime, timezone


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sign_payload(payload: dict, secret: str) -> str:
    body = normalize(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    if not body.endswith("}"):
        raise ValueError("payload must serialize to a JSON object")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"),
                   hashlib.sha384).hexdigest()
    return body[:-1] + ',"sig":"' + sig + '"}'


def _extract_signed(norm: str):
    """Pull the signed JSON object out of a body that may have a preamble
    or trailer (connector notes, signatures, blank lines).

    The signed form is a single JSON object whose final `}` was replaced
    by `,"sig":"<96 hex>"}`. We find that tail, then the `{` that opens
    the object, and return (raw_object_with_closing_brace, sig).
    """
    marker = ',"sig":"'
    i = norm.rfind(marker)
    if i < 0:
        raise ValueError("no signature marker found")
    tail = norm[i + len(marker):]
    if len(tail) < 98 or tail[96:98] != '"}' or tail[:96].lower().strip("0123456789abcdef") != "":
        raise ValueError("malformed signature tail")
    sig = tail[:96]
    start = _object_start(norm, i)
    return norm[start:i] + "}", sig


def _object_start(norm: str, sig_at: int) -> int:
    """Index of the `{` that opens the object ending at the sig marker."""
    j = 0
    candidates = []
    while True:
        j = norm.find("{", j, sig_at)
        if j < 0:
            break
        candidates.append(j)
        j += 1
    for start in reversed(candidates):
        if _in_root_object_at(norm, start, sig_at):
            return start
    raise ValueError("no JSON object before signature")


def _in_root_object_at(norm: str, start: int, sig_at: int) -> bool:
    depth = 0
    in_str = False
    escape = False
    for k in range(start, sig_at):
        c = norm[k]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return False
    return depth == 1 and not in_str


def verify_body(body: str, secret: str) -> dict:
    # Trailing whitespace is not signed. Surrounding text is ignored:
    # only the JSON object that ends in the signature is checked.
    norm = normalize(body).rstrip()
    raw, sig = _extract_signed(norm)
    expect = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"),
                      hashlib.sha384).hexdigest()
    if not hmac.compare_digest(expect, sig.lower()):
        raise ValueError("signature mismatch")
    job = json.loads(raw)
    if not isinstance(job, dict):
        raise ValueError("signed body is not a JSON object")
    return job


def cmd_new(args) -> int:
    payload = {
        "v": 1,
        "type": "job",
        "job_id": args.job_id or str(uuid.uuid4()),
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": args.kind,
    }
    if args.key_id:
        payload["key_id"] = args.key_id
    if args.aud:
        payload["aud"] = args.aud
    if args.reply_to:
        payload["reply_to"] = args.reply_to
    if args.kind == "exec":
        if args.script_url:
            payload["script_url"] = args.script_url
        if args.script_sha384:
            payload["script_sha384"] = args.script_sha384
        if args.script_file:
            with open(args.script_file, encoding="utf-8") as f:
                payload["script"] = f.read()
        if not payload.get("script") and not payload.get("script_url"):
            print("exec jobs need --script-file or --script-url", file=sys.stderr)
            return 2
        if args.file:
            files = []
            for spec in args.file:
                name, _, url = spec.partition("=")
                if not url:
                    print(f"bad --file spec (want name=url): {spec}", file=sys.stderr)
                    return 2
                files.append({"name": name, "url": url})
            payload["files"] = files
        if args.arg:
            payload["args"] = args.arg
        if args.env:
            env = {}
            for spec in args.env:
                k, _, v = spec.partition("=")
                env[k] = v
            payload["env"] = env
        if args.interpreter:
            payload["interpreter"] = json.loads(args.interpreter)
        payload["timeout_sec"] = args.timeout
    body = sign_payload(payload, args.secret)
    print(f"[HOMING-PIGEON] job {payload['job_id']}")
    print()
    print(body)
    return 0


def cmd_verify(args) -> int:
    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    try:
        payload = verify_body(text, args.secret)
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0



def cmd_task_submit(args) -> int:
    payload = {"v": 1, "type": "task", "task_id": args.task_id, "priority": args.priority}
    body = sign_payload(payload, args.secret)
    print(f"[HOMING-PIGEON] task_submit {args.task_id}")
    print()
    print(body)
    return 0


def cmd_task_request(args) -> int:
    payload = {"v": 1, "type": "task_request", "worker_id": args.worker_id, "capabilities": []}
    body = sign_payload(payload, args.secret)
    print(f"[HOMING-PIGEON] task_request {args.worker_id}")
    print()
    print(body)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="homing-pigeon cloud-side helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="build a signed job email")
    n.add_argument("--kind", choices=["exec", "ping"], default="exec")
    n.add_argument("--job-id", default=None)
    n.add_argument("--script-file", default=None)
    n.add_argument("--script-url", default=None)
    n.add_argument("--script-sha384", default=None)
    n.add_argument("--file", action="append", default=[],
                   help="name=url, repeatable")
    n.add_argument("--arg", action="append", default=[],
                   help="script argument, repeatable")
    n.add_argument("--env", action="append", default=[],
                   help="KEY=value, repeatable")
    n.add_argument("--interpreter", default=None,
                   help='JSON list overriding the runner\'s interpreter, e.g. '
                        '\'["pwsh", "-File"]\' or \'["bash"]\'')
    n.add_argument("--timeout", type=int, default=300)
    n.add_argument("--key-id", default=None, help="key_id for multi-secret (Piece 1)")
    n.add_argument("--aud", default=None,
                   help="audience: runner_id the job is addressed to (M5)")
    n.add_argument("--reply-to", default=None, metavar="ADDRESS",
                   help="email the result to this address instead of the "
                        "runner mailbox (must be inside the signed body)")
    n.add_argument("--secret", required=True)
    n.set_defaults(func=cmd_new)


    ts = sub.add_parser("task-submit", help="build a signed task_submit email")
    ts.add_argument("--task-id", required=True)
    ts.add_argument("--priority", type=int, default=0)
    ts.add_argument("--secret", required=True)
    ts.set_defaults(func=cmd_task_submit)

    tr = sub.add_parser("task-request", help="build a signed task_request email")
    tr.add_argument("--worker-id", required=True)
    tr.add_argument("--secret", required=True)
    tr.set_defaults(func=cmd_task_request)
    v = sub.add_parser("verify", help="verify a signed result body")
    v.add_argument("--secret", required=True)
    v.add_argument("file", nargs="?", default=None)
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
