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
the runner's Gmail account — Muse, ChatGPT, Grok, a cron job — can drive
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


def verify_body(body: str, secret: str) -> dict:
    # Trailing whitespace (e.g. a final newline from print/email transport)
    # is not part of the signed content.
    norm = normalize(body).rstrip()
    marker = ',"sig":"'
    i = norm.rfind(marker)
    if i < 0:
        raise ValueError("no signature marker found")
    tail = norm[i + len(marker):]
    if not (len(tail) == 98 and tail[:96].strip("0123456789abcdef") == ""
            and tail[96:] == '"}'):
        raise ValueError("malformed signature tail")
    sig = tail[:96]
    raw = norm[:i] + "}"
    expect = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"),
                      hashlib.sha384).hexdigest()
    if not hmac.compare_digest(expect, sig):
        raise ValueError("signature mismatch")
    return json.loads(raw)


def cmd_new(args) -> int:
    payload = {
        "v": 1,
        "type": "job",
        "job_id": args.job_id or str(uuid.uuid4()),
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": args.kind,
    }
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
    n.add_argument("--secret", required=True)
    n.set_defaults(func=cmd_new)

    v = sub.add_parser("verify", help="verify a signed result body")
    v.add_argument("--secret", required=True)
    v.add_argument("file", nargs="?", default=None)
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
