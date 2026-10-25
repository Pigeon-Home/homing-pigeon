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

Jobs are ENCRYPTED by default (per-job encryption: the signed body is
wrapped in a signed AES-256-GCM envelope keyed from the shared
secret -- see runner/wire/jobcrypto.py). `new --cleartext` produces the
plain HMAC-signed body instead. The runner refuses that body unless
it was started with --allow-cleartext. The shared secret is required
either way.
Encryption has no forward secrecy: the secret is static, so anyone
who later learns it can read every recorded envelope.
"""

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import sys
import uuid
from datetime import datetime, timezone

# This file lives in runner/cloud/: one level up is the runner
# package, two levels up is the tree that holds pyproject.toml.
_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from runner.wire import jobcrypto
except ImportError:  # run by path: load the one implementation by file
    import importlib.util
    _jc_path = os.path.join(_RUNNER_DIR, "wire", "jobcrypto.py")
    _jc_spec = importlib.util.spec_from_file_location(
        "hp_jobcrypto", _jc_path)
    if _jc_spec is None or _jc_spec.loader is None:
        raise ImportError("runner/wire/jobcrypto.py not loadable")
    jobcrypto = importlib.util.module_from_spec(_jc_spec)
    _jc_spec.loader.exec_module(jobcrypto)

try:
    from runner._version import __version__
except ImportError:  # run by path (python runner/cloud/send_job.py) instead of -m
    try:
        from _version import __version__
    except ImportError:
        __version__ = None
if not __version__:
    # Last resort for a bare checkout run by path: read pyproject.toml
    # next to this repo. Works on 3.9+ (no tomllib needed).
    try:
        _root = os.path.dirname(_RUNNER_DIR)
        with open(os.path.join(_root, "pyproject.toml"), encoding="utf-8") as _fh:
            _m = re.search(r'^version\s*=\s*"([^"]+)"', _fh.read(), re.M)
        __version__ = _m.group(1) if _m else "unknown"
    except Exception:
        __version__ = "unknown"


PROTOCOL_VERSION = 1


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


# The protocol requires the shared secret to carry at least 128 bits
# of entropy on the sender as well as the runner. The estimator and
# the pattern check mirror runner/guard/security.py (validate_shared_
# secret); the two implementations must stay in step.
def _estimate_secret_entropy(secret) -> float:
    """Rough entropy estimate in bits: length x log2(alphabet size)."""
    if not isinstance(secret, str) or not secret:
        return 0.0
    alphabet = len(set(secret))
    if alphabet <= 1:
        return 0.0
    return len(secret) * math.log2(alphabet)


def _secret_pattern_reason(secret):
    """Return a reason if the secret looks hand-patterned, else None."""
    if not isinstance(secret, str):
        return "secret must be a string"
    low = secret.lower()
    placeholders = ("generate", "changeme", "example", "placeholder",
                    "your-secret", "your_secret", "todo", "xxx")
    if any(p in low for p in placeholders):
        return "it looks like an example placeholder value"
    n = len(secret)
    for period in range(1, n // 2 + 1):
        unit = secret[:period]
        if secret == (unit * ((n // period) + 1))[:n]:
            return f"it repeats the {period}-character unit {unit!r}"
    return None


def require_signable_secret(secret) -> None:
    """Refuse to sign with a missing or weak shared secret."""
    hint = ("generate one with: openssl rand -hex 32  "
            "or: python3 -c \"import secrets; "
            "print(secrets.token_hex(32))\"")
    if not secret:
        raise ValueError(f"a shared secret is required. {hint}")
    reason = _secret_pattern_reason(secret)
    if reason is not None:
        raise ValueError(
            f"shared secret is too weak ({reason}). {hint}")
    bits = _estimate_secret_entropy(secret)
    if bits < 128:
        raise ValueError(
            f"shared secret is too weak (~{bits:.0f} bits estimated, "
            f"need at least 128). {hint}")


def sign_payload(payload: dict, secret: str) -> str:
    # The guard is on the payload itself: a dict's compact JSON is an
    # object by construction. Kept in step with runner/wire/verify.py
    # and runner/ops/extensions.py (Q48).
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    require_signable_secret(secret)
    body = normalize(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
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
    # _extract_signed returns text rooted at the "{" of a root object,
    # so json.loads here yields a dict or raises. The verifier keeps
    # its own shape check regardless of the extractor: it is the last
    # word before the body is trusted (Q48).
    if not isinstance(job, dict):
        raise ValueError("signed body is not a JSON object")
    return job


def cmd_new(args) -> int:
    payload = {
        "v": PROTOCOL_VERSION,
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
    if not getattr(args, "cleartext", False):
        # Per-job encryption is the default: encrypt the signed
        # body whole, then sign the envelope as transmitted.
        body = jobcrypto.encrypt_body(
            body, args.secret, job_id=payload["job_id"],
            key_id=args.key_id or "", sign=sign_payload)
    if getattr(args, "to_file", None):
        # The file transport's envelope is exactly what would
        # have been printed; write it instead of printing.
        with open(args.to_file, "w", encoding="utf-8") as f:
            f.write(f"[HOMING-PIGEON] job {payload['job_id']}\n\n")
            f.write(body)
            if not body.endswith("\n"):
                f.write("\n")
        print(f"wrote {args.to_file}", file=sys.stderr)
        return 0
    print(f"[HOMING-PIGEON] job {payload['job_id']}")
    print()
    print(body)
    return 0


def repair_line(payload):
    """One line for a sender reading a result.

    Stdout of `verify` stays the JSON. This line goes to stderr
    so a sender sees what was received and what ran without
    parsing the member. None when the result states no repair.
    """
    if not isinstance(payload, dict):
        return None
    member = payload.get("oracle_opinion")
    if not isinstance(member, dict) or "repaired" not in member:
        return None
    if member.get("repaired") is True:
        digest = member.get("received_digest") or ""
        stdout = payload.get("stdout") if isinstance(
            payload.get("stdout"), str) else ""
        first = stdout.strip().splitlines()
        ran = first[0][:200] if first else "(no stdout)"
        return f"repair: received {digest}  ran: {ran}"
    return "repair: refused; the job as received was not rewritten"


def cmd_verify(args) -> int:
    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    try:
        payload = verify_body(text, args.secret)
        if jobcrypto.is_envelope(payload):
            # An encrypted result (or job): the envelope's
            # signature has just verified. Decryption needs the
            # job_id, which lives in the message subject, not the
            # envelope -- hence --job-id.
            if not args.job_id:
                print("INVALID: body is an encryption envelope; "
                      "pass --job-id <id> (from the subject) to "
                      "decrypt it", file=sys.stderr)
                return 1
            inner = jobcrypto.decrypt_body(
                payload, args.secret, job_id=args.job_id,
                key_id=payload.get("key_id") or "")
            payload = verify_body(inner, args.secret)
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    line = repair_line(payload)
    if line:
        print(line, file=sys.stderr)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0



def _board_body(payload, ident, args) -> str:
    """Sign a board message and, unless --cleartext, wrap it in the
    per-job envelope exactly as `new` does for a job. The runner
    refuses a cleartext board message unless it was started with
    --allow-cleartext, and it decrypts a board envelope under the
    identifier in the subject (the task id or the worker id), so
    that identifier is the envelope's object id here."""
    body = sign_payload(payload, args.secret)
    if not getattr(args, "cleartext", False):
        body = jobcrypto.encrypt_body(
            body, args.secret, job_id=ident,
            key_id=getattr(args, "key_id", None) or "",
            sign=sign_payload)
    return body


def cmd_task_submit(args) -> int:
    payload = {"v": PROTOCOL_VERSION, "type": "task_submit", "task_id": args.task_id, "priority": args.priority}
    if getattr(args, "reply_to", None):
        payload["reply_to"] = args.reply_to
    body = _board_body(payload, args.task_id, args)
    print(f"[HOMING-PIGEON] task_submit {args.task_id}")
    print()
    print(body)
    return 0


def cmd_task_request(args) -> int:
    payload = {"v": PROTOCOL_VERSION, "type": "task_request", "worker_id": args.worker_id,
               "capabilities": list(getattr(args, "capability", None) or [])}
    if getattr(args, "reply_to", None):
        payload["reply_to"] = args.reply_to
    body = _board_body(payload, args.worker_id, args)
    print(f"[HOMING-PIGEON] task_request {args.worker_id}")
    print()
    print(body)
    return 0


def main() -> int:
    # --help is a document here too, same hand as the runner's:
    # a description in the project's voice, worked examples in
    # the epilog, and chapters inside `new`.
    ap = argparse.ArgumentParser(
        description=(
            "Build signed Homing Pigeon job emails and verify\n"
            "signed results -- the cloud side of the protocol.\n"
            "If it isn't signed, it isn't sent."),
        epilog=(
            "examples:\n"
            "  send_job.py new --kind ping --secret <secret>\n"
            "      a signed liveness check\n"
            "  send_job.py new --kind exec --script-file "
            "job.ps1 \\\n"
            "      --timeout 300 --secret <secret>\n"
            "      a signed script job\n"
            "  send_job.py verify --secret <secret> < "
            "result.txt\n"
            "      check a result body and pretty-print it\n"
            "\n"
            "new prints the subject line, a blank line, then "
            "the\n"
            "signed body: stdout is the email, so keep it "
            "clean."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version",
                    version="%(prog)s " + (__version__ or "unknown"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser(
        "new", help="build a signed job email",
        description="Build a signed job email. Prints the "
                    "subject line, a blank line, then the "
                    "signed body.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    g = n.add_argument_group("the job")
    g.add_argument("--kind", choices=["exec", "ping"], default="exec",
                   help="job kind (default: exec)")
    g.add_argument("--job-id", default=None, metavar="ID",
                   help="job id (default: a fresh UUID)")
    g.add_argument("--script-file", default=None, metavar="PATH",
                   help="read the script from this file")
    g.add_argument("--script-url", default=None, metavar="URL",
                   help="the runner downloads the script from "
                        "this URL")
    g.add_argument("--script-sha384", default=None, metavar="HEX",
                   help="expected SHA-384 of the script")
    g.add_argument("--interpreter", default=None, metavar="JSON",
                   help='JSON list overriding the runner\'s '
                        'interpreter, e.g. \'["pwsh", "-File"]\' '
                        'or \'["bash"]\'')
    g.add_argument("--timeout", type=int, default=300,
                   metavar="SECONDS",
                   help="per-job timeout in seconds "
                        "(default: 300)")
    g = n.add_argument_group("files, arguments, environment")
    g.add_argument("--file", action="append", default=[],
                   metavar="NAME=URL",
                   help="input file as name=url, repeatable")
    g.add_argument("--arg", action="append", default=[],
                   metavar="ARG",
                   help="script argument, repeatable")
    g.add_argument("--env", action="append", default=[],
                   metavar="KEY=VALUE",
                   help="environment entry as KEY=value, "
                        "repeatable")
    g = n.add_argument_group("addressing and signing")
    g.add_argument("--key-id", default=None, metavar="KEY_ID",
                   help="key_id for multi-secret setups")
    g.add_argument("--aud", default=None, metavar="RUNNER_ID",
                   help="audience: the runner_id this job is "
                        "addressed to")
    g.add_argument("--reply-to", default=None, metavar="ADDRESS",
                   help="email the result to this address "
                        "instead of the runner mailbox (must be "
                        "inside the signed body)")
    g.add_argument("--secret", required=True, metavar="SECRET",
                   help="the shared secret, used as-is as the "
                        "HMAC key; never logged")
    g = n.add_argument_group("delivery")
    g.add_argument("--to-file", default=None, metavar="PATH",
                   help="write the envelope (subject, blank line, "
                        "signed body) to PATH for the runner's "
                        "file transport instead of printing it")
    g.add_argument("--cleartext", action="store_true",
                   help="do NOT encrypt the job: send the plain "
                        "HMAC-signed body. The shared secret is "
                        "still required. The runner refuses this "
                        "unless it was started with "
                        "--allow-cleartext (the default is "
                        "encrypted)")
    n.set_defaults(func=cmd_new)

    ts = sub.add_parser(
        "task-submit", help="build a signed task_submit email",
        description="Build a signed board task_submit email.")
    ts.add_argument("--task-id", required=True, metavar="ID")
    ts.add_argument("--priority", type=int, default=0,
                    help="task priority (default: 0)")
    ts.add_argument("--secret", required=True, metavar="SECRET")
    ts.add_argument("--reply-to", default=None, metavar="ADDRESS",
                    help="email the task_ack to this address instead "
                         "of the runner mailbox (inside the signed body)")
    ts.add_argument("--cleartext", action="store_true",
                    help="do NOT encrypt: send the plain HMAC-signed "
                         "body (the runner refuses it unless started "
                         "with --allow-cleartext)")
    ts.set_defaults(func=cmd_task_submit)

    tr = sub.add_parser(
        "task-request", help="build a signed task_request email",
        description="Build a signed board task_request email.")
    tr.add_argument("--worker-id", required=True, metavar="ID")
    tr.add_argument("--capability", action="append", default=[],
                    metavar="TAG",
                    help="a capability tag this worker claims "
                         "(repeatable); a task is offered only when "
                         "the worker claims every tag it requires")
    tr.add_argument("--secret", required=True, metavar="SECRET")
    tr.add_argument("--reply-to", default=None, metavar="ADDRESS",
                    help="email the task_offer to this address instead "
                         "of the runner mailbox (inside the signed body)")
    tr.add_argument("--cleartext", action="store_true",
                    help="do NOT encrypt: send the plain HMAC-signed "
                         "body (the runner refuses it unless started "
                         "with --allow-cleartext)")
    tr.set_defaults(func=cmd_task_request)
    v = sub.add_parser(
        "verify", help="verify a signed result body",
        description="Verify a signed result body and "
                    "pretty-print it.")
    v.add_argument("--secret", required=True, metavar="SECRET")
    v.add_argument("--job-id", default=None, metavar="ID",
                   help="job id from the message subject; "
                        "required to decrypt an encrypted body")
    v.add_argument("file", nargs="?", default=None, metavar="PATH",
                   help="file to read (default: stdin)")
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    # stderr: stdout is the email body contract (subject + blank + body).
    print(f"send_job {__version__}", file=sys.stderr)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
