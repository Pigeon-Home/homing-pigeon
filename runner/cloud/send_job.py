#!/usr/bin/env python3
"""Cloud-side helper for homing-pigeon (see PROTOCOL.md).

Builds signed job emails and verifies signed result emails using the
exact same signature scheme as runner/runner.py:

    sig = HEX(HMAC_SHA384(secret, payload_json_with_LF_line_endings))
    body = payload_json with the trailing "}" replaced by ',"sig":"<sig>"}'

The --secret is the shared secret string, used directly (UTF-8) as the
HMAC-SHA-384 key. It is a dedicated high-entropy string, never the
mailbox's app password (PROTOCOL.md section 4). This helper
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
import base64
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
    from runner.guard import filenames as _filenames
except ImportError:  # run by path: the same rules the runner applies
    import importlib.util
    _fn_path = os.path.join(_RUNNER_DIR, "guard", "filenames.py")
    _fn_spec = importlib.util.spec_from_file_location(
        "hp_filenames", _fn_path)
    if _fn_spec is None or _fn_spec.loader is None:
        raise ImportError("runner/guard/filenames.py not loadable")
    _filenames = importlib.util.module_from_spec(_fn_spec)
    _fn_spec.loader.exec_module(_filenames)

try:
    from runner.guard import atomicio as _atomicio
except ImportError:  # run by path: the one writer of a state file
    import importlib.util
    _io_path = os.path.join(_RUNNER_DIR, "guard", "atomicio.py")
    _io_spec = importlib.util.spec_from_file_location(
        "hp_atomicio", _io_path)
    if _io_spec is None or _io_spec.loader is None:
        raise ImportError("runner/guard/atomicio.py not loadable")
    _atomicio = importlib.util.module_from_spec(_io_spec)
    _io_spec.loader.exec_module(_atomicio)

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
    """Index of the `{` that opens the object ending at the sig marker.

    Every `{` before the marker is tried, newest first; the one taken
    is the first whose text up to the marker is a whole root object
    (the brace walk) and parses as a JSON object. A `{` inside a
    string can pass the walk alone: a payload that nests an object
    keyed `"{"` and later carries an escaped quote walks balanced
    from the brace inside the key, and the brace walk alone returned
    a span starting mid-payload, so a body the runner's signer
    produced failed here as a signature mismatch (Q61, Project
    Platinum cycle 2). The parse check is the same one
    runner/wire/verify.py has carried since Q32: the two signers are
    one signer in two homes (Q48), and this keeps the extraction in
    step. A wrong candidate fails the parse before any HMAC is
    computed; the HMAC still decides.
    """
    first_walk = None
    for start in _root_candidates(norm, sig_at):
        if first_walk is None:
            first_walk = start
        try:
            candidate = json.loads(norm[start:sig_at] + "}")
        except (ValueError, RecursionError):
            continue
        if isinstance(candidate, dict):
            return start
    if first_walk is not None:
        # Nothing parses: hand the newest whole-object candidate on,
        # so the verifier names the real fault (invalid JSON, a
        # signature mismatch) as it always did.
        return first_walk
    raise ValueError("no JSON object before signature")


def _root_candidates(norm: str, sig_at: int):
    """The `{` positions before the marker whose text up to it is a
    whole root object by the brace walk (`_in_root_object_at`),
    newest first, found in one pass over the text instead of one walk
    per brace (de_dust2 slow records on wire and cloud, Q116: a body
    nested a few hundred levels deep cost a walk per level, each the
    length of the body, so a 16 KB nest took half a second and a
    4 MB one would take the rest of the day, before any MAC).

    A walk from a brace runs the same three-state string machine
    (out of a string, in one, in one after a backslash) whatever
    brace it starts at, so the suffix of the text after a position
    has one summary per starting state: the net brace depth it adds,
    the lowest depth it touches on the way, and the state it ends in.
    Scanning backward keeps the three summaries for the position
    after the current one; a brace at the current position walks
    true exactly when the suffix after it, entered out of a string,
    never closes the brace (lowest depth not below zero), adds no net
    depth (the walk ends at depth one), and ends out of a string. The
    results are the walk's, brace for brace; only the cost changed."""
    OUT, IN, ESC = 0, 1, 2
    delta = [0, 0, 0]
    low = [0, 0, 0]
    final = [OUT, IN, ESC]
    for p in range(sig_at - 1, -1, -1):
        c = norm[p]
        if c == "{":
            if low[OUT] >= 0 and delta[OUT] == 0 and final[OUT] == OUT:
                yield p
            n0, e0 = OUT, 1
        elif c == "}":
            n0, e0 = OUT, -1
        elif c == '"':
            n0, e0 = IN, 0
        else:
            n0, e0 = OUT, 0
        if c == "\\":
            n1 = ESC
        elif c == '"':
            n1 = OUT
        else:
            n1 = IN
        d0 = e0 + delta[n0]
        l0 = e0 + low[n0]
        if l0 > 0:
            l0 = 0
        delta = [d0, delta[n1], delta[IN]]
        low = [l0, low[n1], low[IN]]
        final = [final[n0], final[n1], final[IN]]


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
    # NaN, Infinity and a number that overflows a float are refused
    # by the parse itself; the runner's verifier does the same (Q89).
    try:
        job = json.loads(raw, parse_constant=_no_constant,
                         parse_float=_finite_float)
    except RecursionError:
        raise ValueError(f"signed body nests deeper than {NESTING_LIMIT} "
                         "levels") from None
    # _extract_signed returns text rooted at the "{" of a root object,
    # so json.loads here yields a dict or raises. The verifier keeps
    # its own shape check regardless of the extractor: it is the last
    # word before the body is trusted (Q48).
    if not isinstance(job, dict):
        raise ValueError("signed body is not a JSON object")
    # A body nested past the walks' bound is refused whole, as the
    # runner's verifier refuses it (Q89), measured without recursion.
    if _nests_deeper_than(job, NESTING_LIMIT):
        raise ValueError(f"signed body nests deeper than {NESTING_LIMIT} "
                         "levels")
    # A \\ud800 escape reads as a lone surrogate: valid JSON syntax,
    # not UTF-8 text. The runner's verifier refuses it (Q85); this
    # one does the same, in step.
    if _has_lone_surrogate(job):
        raise ValueError("signed body carries an unpaired UTF-16 surrogate")
    return job


NESTING_LIMIT = 200


def _no_constant(name):
    raise ValueError(f"signed body carries {name}, which is not JSON")


def _finite_float(text):
    value = float(text)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("signed body carries a number that is not finite")
    return value


def _nests_deeper_than(value, limit=NESTING_LIMIT) -> bool:
    """True when a container sits more than `limit` levels down (the
    root object is level 1); a stack, not recursion, so any depth is
    measured (runner/guard/textutil.py has the runner's copy)."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, dict):
            kids = item.values()
        elif isinstance(item, (list, tuple)):
            kids = item
        else:
            continue
        if depth > limit:
            return True
        for kid in kids:
            if isinstance(kid, (dict, list, tuple)):
                stack.append((kid, depth + 1))
    return False


def _has_lone_surrogate(value, _seen=None) -> bool:
    """True when a string anywhere in a JSON value cannot be encoded
    as UTF-8 (runner/guard/textutil.py has the runner's copy; this
    file runs by path too, so it carries its own)."""
    if isinstance(value, str):
        try:
            value.encode("utf-8")
            return False
        except UnicodeEncodeError:
            return True
    if isinstance(value, (dict, list, tuple)):
        if _seen is None:
            _seen = set()
        if id(value) in _seen:
            return False
        _seen.add(id(value))
        try:
            items = value.items() if isinstance(value, dict) else \
                enumerate(value)
            return any(_has_lone_surrogate(k, _seen)
                       or _has_lone_surrogate(v, _seen) for k, v in items)
        finally:
            _seen.discard(id(value))
    return False


KEY_ID_LABEL = b"homing-pigeon key id v1\n"


def key_fingerprint(secret: str) -> str:
    """The name a secret carries by default (Q94): `k-` and the first
    eight hex digits of SHA-384 over a fixed label and the secret,
    the same the runner computes (runner/guard/security.py; this
    file runs by path, so it carries its own copy). Anyone holding
    the secret can compute it, so a sender always has a name to
    give. The name is public by design, like a user name: a signed
    message is already an oracle for a guessed secret, and eight hex
    digits of a one-way function over 256 random bits add nothing
    to that; the label keeps this hash apart from everything else
    the key derives."""
    if not isinstance(secret, str):
        raise ValueError("secret must be a string")
    digest = hashlib.sha384(KEY_ID_LABEL + secret.encode("utf-8")).hexdigest()
    return "k-" + digest[:8]


def resolve_key_id(args) -> str:
    """The key id a message carries: --key-id as given (the empty
    string names the runner's unnamed default slot, the form senders
    used before keys had names), or by default the fingerprint of the secret
    in use, which the runner's default key answers to."""
    kid = getattr(args, "key_id", None)
    if kid is None:
        return key_fingerprint(args.secret)
    return kid


def keyring_path(args=None) -> str:
    given = getattr(args, "keyring", None) if args is not None else None
    return (given or os.environ.get("HP_KEYRING")
            or os.path.join(os.path.expanduser("~"), ".homing-pigeon",
                            "keyring.json"))


def keyring_load(path: str) -> dict:
    """{key_id: {"secret": ..., "runner": ...}}; absent is empty."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ValueError(f"keyring {path} does not read: {e}")
    if not isinstance(data, dict) or not all(
            isinstance(k, str) and isinstance(v, dict)
            and isinstance(v.get("secret"), str) for k, v in data.items()):
        raise ValueError(f"keyring {path} is not a map of key ids to "
                         "entries with a secret")
    return data


def keyring_save(path: str, data: dict) -> None:
    """The keyring is the sender's own copy of its secrets: a private
    file (0600 in a 0700 directory), written whole or not at all,
    never printed."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, mode=0o700, exist_ok=True)
    _atomicio.write_json(path, data, mode=0o600, indent=2, sort_keys=True,
                         newline=True)


def secret_for(args) -> str:
    """The secret a command signs with: --secret as given, else the
    keyring entry --key-id names."""
    secret = getattr(args, "secret", None)
    if secret:
        return secret
    kid = getattr(args, "key_id", None)
    if kid:
        entry = keyring_load(keyring_path(args)).get(kid)
        if entry is not None:
            return entry["secret"]
        raise ValueError(f"no --secret given and the keyring holds no "
                         f"key id {kid!r} (send_job.py keyring list)")
    raise ValueError("give --secret, or --key-id naming a keyring entry")


def cmd_key_id(args) -> int:
    """Print the name a secret carries by default."""
    print(key_fingerprint(secret_for(args)))
    return 0


def cmd_keyring(args) -> int:
    path = keyring_path(args)
    ring = keyring_load(path)
    if args.action == "add":
        if not args.secret:
            raise ValueError("keyring add needs --secret")
        kid = args.key_id if args.key_id is not None else \
            key_fingerprint(args.secret)
        entry = {"secret": args.secret}
        if args.runner:
            entry["runner"] = args.runner
        ring[kid] = entry
        keyring_save(path, ring)
        print(kid)
        return 0
    if args.action == "remove":
        if args.key_id is None or args.key_id not in ring:
            raise ValueError(f"the keyring holds no key id {args.key_id!r}")
        del ring[args.key_id]
        keyring_save(path, ring)
        return 0
    # list: the names and the runners, never a secret
    for kid in sorted(ring):
        runner = ring[kid].get("runner")
        print(kid + (f"  {runner}" if isinstance(runner, str) else ""))
    return 0


_VIEWS = ("full", "redacted", "summary", "attested")


def _query_spec(spec):
    """One --query: `attest:PREDICATE`, `tail` or `tail:N`,
    `grep:PATTERN` (everything after the first colon is the pattern),
    or a JSON object for anything else (PROTOCOL.md section 10)."""
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("an empty --query")
    if spec.lstrip().startswith("{"):
        q = json.loads(spec)
        if not isinstance(q, dict) or not isinstance(q.get("op"), str):
            raise ValueError(f"--query {spec!r}: a JSON query needs an op")
        return q
    op, sep, rest = spec.partition(":")
    if op == "attest" and rest:
        return {"op": "attest", "predicate": rest}
    if op == "tail":
        if not sep:
            return {"op": "tail"}
        if rest.isdigit():
            return {"op": "tail", "lines": int(rest)}
    if op == "grep" and rest:
        return {"op": "grep", "pattern": rest}
    raise ValueError(f"--query {spec!r}: want attest:PREDICATE, tail[:N], "
                     "grep:PATTERN or a JSON object")


def result_policy(args):
    """The job's result_policy from --result-policy, --view, --query
    and --query-budget (PROTOCOL.md section 9), or None when none was
    given (Q104). --result-policy is the base; --view and
    --query-budget replace its members and each --query is added to
    its queries."""
    base = getattr(args, "result_policy", None)
    views = getattr(args, "view", None)
    queries = getattr(args, "query", None) or []
    budget = getattr(args, "query_budget", None)
    if base is None and views is None and not queries and budget is None:
        return None
    policy = {}
    if base is not None:
        text = base
        if base.startswith("@"):
            with open(base[1:], encoding="utf-8") as fh:
                text = fh.read()
        policy = json.loads(text)
        if not isinstance(policy, dict):
            raise ValueError("--result-policy must be a JSON object")
    if views is not None:
        policy["view"] = views
    if policy.get("view") is not None and policy["view"] not in _VIEWS:
        raise ValueError(f"view {policy['view']!r}: want one of "
                         + ", ".join(_VIEWS))
    if queries:
        listed = policy.get("queries", [])
        if not isinstance(listed, list):
            raise ValueError("result_policy queries must be a list")
        policy["queries"] = listed + [_query_spec(s) for s in queries]
    if budget is not None:
        if budget < 0:
            raise ValueError("--query-budget must be 0 or more")
        policy["query_budget"] = budget
    if policy.get("view") in ("summary", "attested") and any(
            isinstance(q, dict) and q.get("op") in ("grep", "tail")
            for q in policy.get("queries") or []):
        print(f"note: under the {policy['view']} view the runner refuses "
              "grep and tail queries (PROTOCOL.md section 10); attest "
              "answers", file=sys.stderr)
    return policy


def cmd_new(args) -> int:
    args.secret = secret_for(args)
    key_id = resolve_key_id(args)
    payload = {
        "v": PROTOCOL_VERSION,
        "type": "job",
        "job_id": args.job_id or str(uuid.uuid4()),
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": args.kind,
    }
    if key_id:
        payload["key_id"] = key_id
    if args.aud:
        payload["aud"] = args.aud
    if args.reply_to:
        payload["reply_to"] = args.reply_to
    if args.kind == "change":
        # A change (PROTOCOL.md section 3.5): the owner's repository,
        # this diff, the owner's recipe run in the checked-out tree.
        if not getattr(args, "repo", None):
            print("change jobs need --repo NAME", file=sys.stderr)
            return 2
        payload["repo"] = args.repo
        if getattr(args, "commit", None):
            payload["commit"] = args.commit
        if getattr(args, "diff_file", None):
            with open(args.diff_file, "rb") as fh:
                payload["diff_b64"] = base64.b64encode(fh.read()).decode("ascii")
    if args.kind in ("recipe", "change"):
        # A named recipe (PROTOCOL.md section 3.3): the script, the
        # interpreter and the environment are the runner owner's.
        brought = [flag for flag, v in (
            ("--script-file", args.script_file), ("--script-url", args.script_url),
            ("--script-sha384", args.script_sha384),
            ("--interpreter", args.interpreter), ("--env", args.env)) if v]
        if brought:
            print(f"a {args.kind} job brings no {', '.join(brought)}: the "
                  "recipe is the runner owner's", file=sys.stderr)
            return 2
        if not getattr(args, "recipe", None):
            print(f"{args.kind} jobs need --recipe NAME", file=sys.stderr)
            return 2
        payload["recipe"] = args.recipe
    if args.kind in ("exec", "recipe", "change"):
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
        files = []
        if args.file:
            for spec in args.file:
                name, _, url = spec.partition("=")
                if not url:
                    print(f"bad --file spec (want name=url): {spec}", file=sys.stderr)
                    return 2
                try:
                    # The runner's own rules (runner/guard/filenames.py),
                    # applied here so the author hears it now, not from
                    # a rejection result.
                    name = _filenames.validate_file_name(name)
                except ValueError as e:
                    print(f"bad --file name {name!r}: {e}", file=sys.stderr)
                    return 2
                files.append({"name": name, "url": url})
        for spec in getattr(args, "inline_file", None) or []:
            name, _, path = spec.partition("=")
            if not path:
                print(f"bad --inline-file spec (want name=path): {spec}",
                      file=sys.stderr)
                return 2
            try:
                name = _filenames.validate_file_name(name)
            except ValueError as e:
                print(f"bad --inline-file name {name!r}: {e}", file=sys.stderr)
                return 2
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError as e:
                print(f"cannot read --inline-file {path}: {e}", file=sys.stderr)
                return 2
            # The bytes ride in the signed job (PROTOCOL.md section 6):
            # strict base64, and their digest so the runner checks the
            # staged file against what was read here.
            files.append({"name": name,
                          "content_b64": base64.b64encode(data).decode("ascii"),
                          "sha384": hashlib.sha384(data).hexdigest()})
        if files:
            payload["files"] = files
        if getattr(args, "outputs", None):
            payload["outputs"] = list(args.outputs)
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
    try:
        policy = result_policy(args)
    except (ValueError, OSError) as e:
        print(f"bad result policy: {e}", file=sys.stderr)
        return 2
    if policy is not None:
        payload["result_policy"] = policy
    body = sign_payload(payload, args.secret)
    if not getattr(args, "cleartext", False):
        # Per-job encryption is the default: encrypt the signed
        # body whole, then sign the envelope as transmitted.
        body = jobcrypto.encrypt_body(
            body, args.secret, job_id=payload["job_id"],
            key_id=key_id, sign=sign_payload)
    if getattr(args, "to_queue", None):
        # The hosted queue: POST the same envelope to the tenant's
        # Worker URL with the SI token from the environment.
        envelope = f"[HOMING-PIGEON] job {payload['job_id']}\n\n{body}"
        if not envelope.endswith("\n"):
            envelope += "\n"
        try:
            status, text = post_to_queue(
                args.to_queue, envelope,
                getattr(args, "queue_token_env", None))
        except QueueUnreachable as e:
            print(f"error: could not reach the queue ({e}); job "
                  f"{payload['job_id']} may or may not be queued. Send it "
                  f"again with --job-id {payload['job_id']}: the queue "
                  "answers a repeat of a queued job as a duplicate",
                  file=sys.stderr)
            return 2
        if status in (200, 202):
            dup = ""
            try:
                if json.loads(text).get("duplicate") is True:
                    dup = ", already queued"
            except (ValueError, AttributeError):
                pass
            print(f"queued job {payload['job_id']} at {args.to_queue} "
                  f"(HTTP {status}{dup})", file=sys.stderr)
            return 0
        print(f"queue refused job {payload['job_id']}: HTTP {status}: "
              f"{text[:200]}", file=sys.stderr)
        return 1
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


class QueueUnreachable(Exception):
    """The hosted queue could not be read or written after the bounded
    retries: a dropped connection, a truncated body, a timeout (Q105).
    The command prints one plain line and exits 2, never a traceback."""


# Seconds slept before the second and third attempt. A test sets the
# sleeper to a no-op.
_QUEUE_BACKOFF = (1.0, 3.0)
_queue_sleep = None


def _transient(exc):
    """True for the weather a queue call rides out: the connection
    dropped, the body arrived cut short, or the wait ran out. An HTTP
    status is an answer, never weather."""
    import http.client
    import socket
    import urllib.error
    if isinstance(exc, urllib.error.HTTPError):
        return False
    if isinstance(exc, urllib.error.URLError):
        exc = exc.reason if isinstance(exc.reason, BaseException) else exc
    return isinstance(exc, (http.client.IncompleteRead,
                            http.client.RemoteDisconnected,
                            ConnectionError, socket.timeout, TimeoutError))


def _send_with_retry(opener, req):
    """(status, text) for one queue request, retried on transient
    failures; QueueUnreachable when every attempt failed that way."""
    import time as _time
    import urllib.error
    sleep = _queue_sleep or _time.sleep
    last = None
    for attempt in range(len(_QUEUE_BACKOFF) + 1):
        if attempt:
            sleep(_QUEUE_BACKOFF[attempt - 1])
        try:
            with opener(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try:
                text = e.read().decode("utf-8", "replace")
            except Exception:
                text = ""
            return e.code, text
        except Exception as e:  # noqa: BLE001 -- sorted by _transient
            if not _transient(e):
                raise
            last = e
    raise QueueUnreachable(f"{type(last).__name__}: {last}"[:200])


def post_to_queue(url, envelope, token_env=None, opener=None):
    """POST an envelope to a tenant's hosted queue. The SI token is
    read from the environment variable named by `token_env`
    (default HP_SI_TOKEN); it is never taken from the command line.
    Returns (status, response_text). A dropped connection is retried
    with the same envelope, which the Worker answers as a duplicate
    when the first copy landed (Q105); QueueUnreachable when every
    attempt failed that way."""
    import os as _os
    import urllib.error
    import urllib.request
    name = token_env or "HP_SI_TOKEN"
    token = _os.environ.get(name)
    if not token:
        raise SystemExit(f"error: --to-queue needs the SI token in "
                         f"environment variable {name}")
    if not isinstance(url, str) or not (
            url.startswith("https://") or url.startswith("http://127.0.0.1")
            or url.startswith("http://localhost")):
        raise SystemExit("error: --to-queue must be an https URL "
                         "(loopback http is allowed for tests)")
    req = urllib.request.Request(
        url.rstrip("/") + "/jobs", data=envelope.encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "text/plain; charset=utf-8",
                 "User-Agent": "homing-pigeon-send-job"})
    return _send_with_retry(opener or urllib.request.urlopen, req)


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


def _named_key_in(text: str):
    """The key_id a body names, read before any verification so the
    keyring can supply the secret; nothing else is trusted from it."""
    try:
        raw, _sig = _extract_signed(normalize(text).rstrip())
        obj = json.loads(raw)
    except Exception:
        return None
    kid = obj.get("key_id") if isinstance(obj, dict) else None
    return kid if isinstance(kid, str) else None


def _open_body(text, args, job_id=None):
    """Verify one signed body and, when it is an encryption envelope,
    decrypt it under `job_id` and verify the inside. Returns the
    payload; raises ValueError naming what failed. With no --secret
    the keyring supplies the secret for the key the body names."""
    secret = args.secret
    if not secret:
        kid = args.key_id if args.key_id is not None else _named_key_in(text)
        if kid is None:
            raise ValueError("no --secret given and the body names no "
                             "key_id to look up in the keyring")
        saved = args.key_id
        try:
            args.key_id = kid
            secret = secret_for(args)
        finally:
            args.key_id = saved
    payload = verify_body(text, secret)
    if jobcrypto.is_envelope(payload):
        # The envelope's signature has just verified. Decryption
        # needs the job_id, which lives in the message subject, not
        # the envelope.
        if not job_id:
            raise ValueError("body is an encryption envelope; pass "
                             "--job-id <id> (from the subject) to "
                             "decrypt it")
        inner = jobcrypto.decrypt_body(
            payload, secret, job_id=job_id,
            key_id=payload.get("key_id") or "")
        payload = verify_body(inner, secret)
    return payload


def cmd_verify(args) -> int:
    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    try:
        payload = _open_body(text, args, args.job_id)
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    line = repair_line(payload)
    if line:
        print(line, file=sys.stderr)
    if getattr(args, "outputs_dir", None):
        rc = write_outputs(payload, args.outputs_dir)
        if rc:
            return rc
    chain_rc = 0
    if getattr(args, "chain", None):
        chain_rc = check_chain(payload, args.chain)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return chain_rc


def result_digest(payload):
    """SHA-384 over a result's signed JSON, as the runner computes the
    link (PROTOCOL.md section 3.2): the payload's own JSON, compact,
    in the order it was signed."""
    text = normalize(json.dumps(payload, separators=(",", ":"),
                                ensure_ascii=False, allow_nan=False))
    return hashlib.sha384(text.encode("utf-8")).hexdigest()


def check_chain(payload, path):
    """Hold a verified result against the chain this sender has seen,
    per key, in the JSON file at `path`, then record it. 0 when it is
    the next link (or the first this file has seen of its key), 3 on
    a gap or a break; a line on stderr says which. A stub stands for
    the result it replaced, so the link it records is that one's."""
    seq = payload.get("result_seq")
    if isinstance(seq, bool) or not isinstance(seq, int):
        print("chain: the result carries no result_seq", file=sys.stderr)
        return 0
    key = payload.get("key_id") if isinstance(payload.get("key_id"), str) else ""
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        if not isinstance(state, dict):
            state = {}
    except FileNotFoundError:
        state = {}
    except (OSError, ValueError) as e:
        print(f"chain: {path} unreadable ({e}); starting it again",
              file=sys.stderr)
        state = {}
    seen = state.get(key) if isinstance(state.get(key), dict) else None
    rc = 0
    prev = payload.get("prev_result_sha384")
    if seen is None:
        print(f"chain: first result seen for {key or 'the default key'} "
              f"(seq {seq})", file=sys.stderr)
    elif seq <= seen.get("seq", 0):
        print(f"chain: seq {seq} is not after {seen.get('seq')} already "
              "seen: a replay or an old copy", file=sys.stderr)
        return 3
    elif seq != seen.get("seq", 0) + 1:
        print(f"chain: gap, seq {seen.get('seq', 0) + 1} to {seq - 1} "
              "never reached this sender", file=sys.stderr)
        rc = 3
    elif prev != seen.get("last"):
        print(f"chain: break, seq {seq} does not follow the result "
              f"seen as seq {seen.get('seq')}", file=sys.stderr)
        rc = 3
    else:
        print(f"chain: ok, seq {seq}", file=sys.stderr)
    link = payload.get("replaces_result_sha384")
    if not (isinstance(link, str) and len(link) == 96):
        link = result_digest(payload)
    state[key] = {"seq": seq, "last": link}
    _atomicio.write_json(path, state)
    return rc


def write_outputs(payload, dest):
    """Write a verified result's `outputs` under dest, each checked
    against the SHA-384 the result carries. Names keep the runner's
    own rules, so nothing lands outside dest. Returns 0, or 1 when an
    entry's bytes do not match its digest (nothing is written for
    it). The printed result drops the bytes it wrote."""
    outs = payload.get("outputs")
    if not isinstance(outs, list):
        return 0
    rc = 0
    os.makedirs(dest, exist_ok=True)
    root = os.path.realpath(dest)
    written = set()
    for o in outs:
        if not isinstance(o, dict) or "content_b64" not in o:
            continue
        try:
            name = _filenames.validate_file_name(o.get("name"))
            data = base64.b64decode(str(o["content_b64"]).encode("ascii"),
                                    validate=True)
        except (ValueError, TypeError, UnicodeEncodeError) as e:
            print(f"output {o.get('name')!r} refused: {e}", file=sys.stderr)
            rc = 1
            continue
        # One file per name: a result that names an output twice is
        # refused for the second, not written over the first (Q101).
        if name in written:
            print(f"output {name!r} refused: named twice", file=sys.stderr)
            rc = 1
            continue
        if hashlib.sha384(data).hexdigest() != str(o.get("sha384", "")).lower():
            print(f"output {name!r}: bytes do not match their sha384",
                  file=sys.stderr)
            rc = 1
            continue
        path = os.path.join(dest, *name.split("/"))
        # The name rules keep the name inside dest; a symlink already
        # in dest could still lead out, so the folder it lands in must
        # resolve under dest and the file itself is never followed.
        os.makedirs(os.path.dirname(path), exist_ok=True)
        folder = os.path.realpath(os.path.dirname(path))
        if folder != root and not folder.startswith(root + os.sep):
            print(f"output {name!r} refused: its folder leads outside "
                  f"{dest}", file=sys.stderr)
            rc = 1
            continue
        if os.path.islink(path):
            print(f"output {name!r} refused: a symlink is in its place",
                  file=sys.stderr)
            rc = 1
            continue
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC \
            | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except OSError as e:
            print(f"output {name!r} refused: {e}", file=sys.stderr)
            rc = 1
            continue
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        written.add(name)
        o.pop("content_b64", None)
        o["written"] = path
        print(f"wrote {path} ({len(data)} bytes)", file=sys.stderr)
    return rc


def _queue_call(url, method, path, token_env=None, opener=None):
    """One SI call to a tenant's hosted queue: (status, text). The SI
    token comes from the environment, never the command line."""
    import os as _os
    import urllib.error
    import urllib.request
    name = token_env or "HP_SI_TOKEN"
    token = _os.environ.get(name)
    if not token:
        raise SystemExit(f"error: the queue needs the SI token in "
                         f"environment variable {name}")
    if not isinstance(url, str) or not (
            url.startswith("https://") or url.startswith("http://127.0.0.1")
            or url.startswith("http://localhost")):
        raise SystemExit("error: the queue URL must be https "
                         "(loopback http is allowed for tests)")
    req = urllib.request.Request(
        url.rstrip("/") + path, method=method,
        data=b"" if method == "POST" else None,
        headers={"Authorization": f"Bearer {token}",
                 "User-Agent": "homing-pigeon-send-job"})
    return _send_with_retry(opener or urllib.request.urlopen, req)


def _result_job_id(subject):
    """The job id a result subject names: the word after `result`
    (or `qresult`), as the Worker reads it. None otherwise."""
    words = subject.split() if isinstance(subject, str) else []
    for i, w in enumerate(words[:-1]):
        if w in ("result", "qresult"):
            return words[i + 1]
    return None


def _queue_plain(cmd):
    """A queue command that could not reach the queue after its
    retries prints one plain line and exits 2 (Q105)."""
    import functools

    @functools.wraps(cmd)
    def wrapped(args, opener=None):
        try:
            return cmd(args, opener)
        except QueueUnreachable as e:
            print(f"error: could not reach the queue ({e}); run it "
                  "again", file=sys.stderr)
            return 2
    return wrapped


@_queue_plain
def cmd_results(args, opener=None) -> int:
    """Read results from a hosted queue: one JSON line per result on
    stdout, verified (and decrypted under the job id in its subject).
    --ack removes a result from the queue only after it verified; a
    result that does not verify stays, so it can be looked at again.
    Exit 0 when every result verified (or none was waiting), 1 when
    any did not, 2 when the queue refused the read."""
    max_n = max(1, min(int(args.max or 20), 100))
    status, text = _queue_call(args.from_queue, "GET",
                               f"/results?max={max_n}",
                               args.queue_token_env, opener)
    if status == 204:
        print("no results waiting", file=sys.stderr)
        return 0
    if status != 200:
        print(f"error: the queue answered {status}: {text[:200]}",
              file=sys.stderr)
        return 2
    # The Worker answers an empty queue with 204 and a 200 only with a
    # list, so a 200 without one is neither an answer nor an empty
    # queue: exit 2, never "no results", so a watcher cannot read a
    # cut or rewritten body as a stopped runner (Q105).
    try:
        items = json.loads(text).get("results")
    except (ValueError, AttributeError):
        items = None
    if not isinstance(items, list):
        print("error: the queue's answer is not a results list",
              file=sys.stderr)
        return 2
    bad = 0
    for item in items:
        rid = item.get("id") if isinstance(item, dict) else None
        envelope = item.get("envelope") if isinstance(item, dict) else None
        line = {"id": rid}
        try:
            if not isinstance(envelope, str):
                raise ValueError("the result carries no envelope")
            subject, _, body = normalize(envelope).partition("\n\n")
            line["job_id"] = _result_job_id(subject)
            payload = _open_body(body, args, line["job_id"])
            line["ok"] = True
            line["payload"] = payload
        except ValueError as e:
            bad += 1
            line["ok"] = False
            line["error"] = str(e)
        if line["ok"] and args.ack and isinstance(rid, str):
            from urllib.parse import quote
            try:
                st, _t = _queue_call(args.from_queue, "POST",
                                     f"/results/{quote(rid, safe='')}/ack",
                                     args.queue_token_env, opener)
            except QueueUnreachable:
                st = None  # stays on the queue; the next read has it
            line["acked"] = st in (200, 204, 404)
        print(json.dumps(line, ensure_ascii=False))
    return 1 if bad else 0



@_queue_plain
def cmd_dlq(args, opener=None) -> int:
    """The hosted queue's dead-letter list: jobs that ran out of
    attempts without a result. Lists them (one JSON line each: id,
    attempts, subject, times), or with --drop ID removes one, or with
    --requeue ID offers it again with a fresh attempt count. A
    requeued job is the same signed job: a runner that already saw
    it, or that holds it past its freshness window, refuses it as it
    would any replay; send a new job instead. Exit 0 on success, 1
    when the id is not on the list, 2 when the queue refused."""
    from urllib.parse import quote
    for verb, ident in (("ack", args.drop), ("requeue", args.requeue)):
        if ident:
            st, text = _queue_call(args.from_queue, "POST",
                                   f"/dlq/{quote(ident, safe='')}/{verb}",
                                   args.queue_token_env, opener)
            if st in (200, 202, 204):
                print(json.dumps({"id": ident, verb if verb != "ack"
                                  else "dropped": True}))
                return 0
            if st == 404:
                print(f"error: {ident} is not on the dead-letter list",
                      file=sys.stderr)
                return 1
            print(f"error: the queue answered {st}: {text[:200]}",
                  file=sys.stderr)
            return 2
    max_n = max(1, min(int(args.max or 20), 100))
    st, text = _queue_call(args.from_queue, "GET", f"/dlq?max={max_n}",
                           args.queue_token_env, opener)
    if st == 204:
        print("the dead-letter list is empty", file=sys.stderr)
        return 0
    if st != 200:
        print(f"error: the queue answered {st}: {text[:200]}",
              file=sys.stderr)
        return 2
    try:
        dead = json.loads(text).get("dead")
    except (ValueError, AttributeError):
        dead = None
    if not isinstance(dead, list):
        print("error: the queue's answer is not a dead-letter list",
              file=sys.stderr)
        return 2
    for d in dead:
        print(json.dumps(d, ensure_ascii=False))
    return 0


def _board_body(payload, ident, args) -> str:
    """Sign a board message and, unless --cleartext, wrap it in the
    per-job envelope exactly as `new` does for a job. The runner
    refuses a cleartext board message unless it was started with
    --allow-cleartext, and it decrypts a board envelope under the
    identifier in the subject (the task id or the worker id), so
    that identifier is the envelope's object id here."""
    args.secret = secret_for(args)
    key_id = resolve_key_id(args)
    if key_id:
        payload["key_id"] = key_id
    # A board message is fresh as a job is (PROTOCOL.md section 13.7):
    # the runner refuses one with no issued_at, or outside the window.
    payload.setdefault("issued_at", datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"))
    body = sign_payload(payload, args.secret)
    if not getattr(args, "cleartext", False):
        body = jobcrypto.encrypt_body(
            body, args.secret, job_id=ident,
            key_id=key_id, sign=sign_payload)
    return body


def cmd_cancel(args) -> int:
    """A signed cancel for a job (PROTOCOL.md section 3.4), sealed under
    the job id as the job was. Only the key that signed the job may
    cancel it; the runner answers with a cancel_ack."""
    if not re.match(r"^[A-Za-z0-9._-]{1,128}$", args.job_id or "") \
            or args.job_id in (".", ".."):
        print("error: --job-id is not a job id", file=sys.stderr)
        return 2
    payload = {"v": PROTOCOL_VERSION, "type": "cancel", "job_id": args.job_id}
    body = _board_body(payload, args.job_id, args)
    print(f"[HOMING-PIGEON] cancel {args.job_id}")
    print()
    print(body)
    return 0


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
    g.add_argument("--kind", choices=["exec", "ping", "recipe", "change"],
                   default="exec",
                   help="job kind (default: exec); recipe runs a script "
                        "the runner owner named in its config; change "
                        "checks out an owner's repository, applies "
                        "--diff-file and runs --recipe in it")
    g.add_argument("--repo", default=None, metavar="NAME",
                   help="the owner's change repository a --kind change "
                        "job runs in")
    g.add_argument("--commit", default=None, metavar="REF",
                   help="the commit a change checks out (default: the "
                        "repository's HEAD)")
    g.add_argument("--diff-file", default=None, metavar="PATH",
                   help="the unified diff a change applies")
    g.add_argument("--recipe", default=None, metavar="NAME",
                   help="the recipe a --kind recipe job runs; --arg "
                        "passes its arguments")
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
    g.add_argument("--output", action="append", default=[],
                   metavar="NAME", dest="outputs",
                   help="a file under the job's workdir to bring home "
                        "in the result (at most 8; the bytes only under "
                        "the full view), repeatable")
    g.add_argument("--inline-file", action="append", default=[],
                   metavar="NAME=PATH",
                   help="input file carried in the signed job itself "
                        "(base64; counted against the runner's "
                        "max_job_bytes), repeatable")
    g.add_argument("--arg", action="append", default=[],
                   metavar="ARG",
                   help="script argument, repeatable")
    g.add_argument("--env", action="append", default=[],
                   metavar="KEY=VALUE",
                   help="environment entry as KEY=value, "
                        "repeatable")
    g = n.add_argument_group(
        "result policy (PROTOCOL.md sections 9 and 10)",
        "What the result may carry and the questions about the output\n"
        "it answers. The runner's max_result_view caps the view.")
    g.add_argument("--view", default=None, choices=_VIEWS,
                   help="the view the result is asked for (default: "
                        "full); the runner never widens it past its own "
                        "ceiling")
    g.add_argument("--query", action="append", default=[], metavar="SPEC",
                   help="a question answered inside the result: "
                        "attest:PREDICATE (exit_zero, no_secrets, "
                        "output_digest, confined_to_workspace), tail[:N], "
                        "grep:PATTERN, or a JSON object; repeatable")
    g.add_argument("--query-budget", type=int, default=None, metavar="N",
                   help="most queries answered for this job (the runner "
                        "caps it with max_query_budget)")
    g.add_argument("--result-policy", default=None, metavar="JSON|@FILE",
                   help="a whole result_policy object; --view, --query "
                        "and --query-budget add to it")
    g = n.add_argument_group("addressing and signing")
    g.add_argument("--key-id", default=None, metavar="KEY_ID",
                   help="the key id the job carries (default: the "
                        "fingerprint of the secret, k-<8 hex>, which "
                        "the runner's key answers to; an empty "
                        "string sends the unnamed form senders used "
                        "before keys had names; a keyring entry's id also "
                        "supplies the secret)")
    g.add_argument("--aud", default=None, metavar="RUNNER_ID",
                   help="audience: the runner_id this job is "
                        "addressed to")
    g.add_argument("--reply-to", default=None, metavar="ADDRESS",
                   help="email the result to this address "
                        "instead of the runner mailbox (must be "
                        "inside the signed body)")
    g.add_argument("--secret", default=None, metavar="SECRET",
                   help="the shared secret, used as-is as the "
                        "HMAC key; never logged (or --key-id naming "
                        "a keyring entry)")
    g.add_argument("--keyring", default=None, metavar="PATH",
                   help="the sender's keyring (default: $HP_KEYRING "
                        "or ~/.homing-pigeon/keyring.json)")
    g = n.add_argument_group("delivery")
    g.add_argument("--to-file", default=None, metavar="PATH",
                   help="write the envelope (subject, blank line, "
                        "signed body) to PATH for the runner's "
                        "file transport instead of printing it")
    g.add_argument("--to-queue", default=None, metavar="URL",
                   help="POST the envelope to a tenant's hosted queue "
                        "(the Worker URL ending in /t/<tenant>) instead "
                        "of printing it; the SI token comes from the "
                        "environment, see --queue-token-env")
    g.add_argument("--queue-token-env", default="HP_SI_TOKEN",
                   metavar="NAME",
                   help="environment variable holding the SI token for "
                        "--to-queue (default HP_SI_TOKEN)")
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
    ts.add_argument("--secret", default=None, metavar="SECRET",
                    help="the shared secret (or --key-id naming a "
                         "keyring entry)")
    ts.add_argument("--key-id", default=None, metavar="KEY_ID",
                    help="the key id the message carries (default: "
                         "the secret's fingerprint)")
    ts.add_argument("--keyring", default=None, metavar="PATH")
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
    tr.add_argument("--secret", default=None, metavar="SECRET",
                    help="the shared secret (or --key-id naming a "
                         "keyring entry)")
    tr.add_argument("--key-id", default=None, metavar="KEY_ID",
                    help="the key id the message carries (default: "
                         "the secret's fingerprint)")
    tr.add_argument("--keyring", default=None, metavar="PATH")
    tr.add_argument("--reply-to", default=None, metavar="ADDRESS",
                    help="email the task_offer to this address instead "
                         "of the runner mailbox (inside the signed body)")
    tr.add_argument("--cleartext", action="store_true",
                    help="do NOT encrypt: send the plain HMAC-signed "
                         "body (the runner refuses it unless started "
                         "with --allow-cleartext)")
    tr.set_defaults(func=cmd_task_request)
    c = sub.add_parser(
        "cancel", help="build a signed cancel for a job",
        description="Build a signed cancel email for a job this key "
                    "sent. A running job is killed; one not yet run is "
                    "refused when it arrives; a finished one is left "
                    "as it is. The runner answers with a cancel_ack.")
    c.add_argument("--job-id", required=True, metavar="ID")
    c.add_argument("--secret", default=None, metavar="SECRET",
                   help="the shared secret the job was signed with (or "
                        "--key-id naming a keyring entry)")
    c.add_argument("--key-id", default=None, metavar="KEY_ID",
                   help="the key id the message carries (default: the "
                        "secret's fingerprint)")
    c.add_argument("--keyring", default=None, metavar="PATH")
    c.add_argument("--cleartext", action="store_true",
                   help="do NOT encrypt (the runner refuses it unless "
                        "started with --allow-cleartext)")
    c.set_defaults(func=cmd_cancel)
    v = sub.add_parser(
        "verify", help="verify a signed result body",
        description="Verify a signed result body and "
                    "pretty-print it.")
    v.add_argument("--secret", default=None, metavar="SECRET",
                   help="the shared secret (default: the keyring entry "
                        "the body's key_id names)")
    v.add_argument("--key-id", default=None, metavar="KEY_ID",
                   help="the keyring entry to verify with (default: "
                        "the key_id the body names)")
    v.add_argument("--keyring", default=None, metavar="PATH")
    v.add_argument("--job-id", default=None, metavar="ID",
                   help="job id from the message subject; "
                        "required to decrypt an encrypted body")
    v.add_argument("--outputs-dir", default=None, metavar="DIR",
                   help="write the result's output files here, each "
                        "checked against its sha384")
    v.add_argument("--chain", default=None, metavar="PATH",
                   help="hold the result against the result chain kept "
                        "in this file, per key, and record it (exit 3 "
                        "on a gap or a break)")
    v.add_argument("file", nargs="?", default=None, metavar="PATH",
                   help="file to read (default: stdin)")
    v.set_defaults(func=cmd_verify)

    rs = sub.add_parser(
        "results", help="read and verify results from a hosted queue",
        description="Read the results waiting on a hosted queue, verify "
                    "each (decrypting under the job id in its subject), "
                    "and print one JSON line per result. The SI token "
                    "is read from the environment.")
    rs.add_argument("--from-queue", required=True, metavar="URL",
                    help="the tenant's queue base, e.g. "
                         "https://hp.example.workers.dev/t/you")
    rs.add_argument("--queue-token-env", default=None, metavar="NAME",
                    help="environment variable holding the SI token "
                         "(default HP_SI_TOKEN)")
    rs.add_argument("--max", type=int, default=20, metavar="N",
                    help="results to read in one call (1 to 100)")
    rs.add_argument("--ack", action="store_true",
                    help="remove each result from the queue once it "
                         "verified")
    rs.add_argument("--secret", default=None, metavar="SECRET",
                    help="the shared secret (default: the keyring entry "
                         "each body's key_id names)")
    rs.add_argument("--key-id", default=None, metavar="KEY_ID")
    rs.add_argument("--keyring", default=None, metavar="PATH")
    rs.set_defaults(func=cmd_results)

    dq = sub.add_parser(
        "dlq", help="the hosted queue's dead-letter list",
        description="List the jobs on a hosted queue's dead-letter list "
                    "(out of attempts, no result), drop one, or requeue "
                    "one with a fresh attempt count. The SI token is "
                    "read from the environment.")
    dq.add_argument("--from-queue", required=True, metavar="URL")
    dq.add_argument("--queue-token-env", default=None, metavar="NAME",
                    help="environment variable holding the SI token "
                         "(default HP_SI_TOKEN)")
    dq.add_argument("--max", type=int, default=20, metavar="N")
    act = dq.add_mutually_exclusive_group()
    act.add_argument("--drop", default=None, metavar="ID",
                     help="remove this job from the list")
    act.add_argument("--requeue", default=None, metavar="ID",
                     help="offer this job again (counts against the "
                          "hourly job quota)")
    dq.set_defaults(func=cmd_dlq)

    k = sub.add_parser(
        "key-id", help="print the name a secret carries by default",
        description="Print the key id a secret carries by default: "
                    "k- and the first eight hex digits of SHA-384 over "
                    "a fixed label and the secret. The runner's key "
                    "answers to it; the name is public, the secret "
                    "is not.")
    k.add_argument("--secret", default=None, metavar="SECRET")
    k.add_argument("--key-id", default=None, metavar="KEY_ID",
                   help="a keyring entry whose secret to name")
    k.add_argument("--keyring", default=None, metavar="PATH")
    k.set_defaults(func=cmd_key_id)

    r = sub.add_parser(
        "keyring", help="the sender's keyring: add, list, remove",
        description="Keep the key id and the secret together, so a "
                    "sender never holds a bare secret: `add` stores a "
                    "secret under its fingerprint (or --key-id) with "
                    "the runner it belongs to, `list` prints the names "
                    "and runners (never a secret), `remove` drops one. "
                    "The file is private to the sender (0600).")
    r.add_argument("action", choices=["add", "list", "remove"])
    r.add_argument("--secret", default=None, metavar="SECRET")
    r.add_argument("--key-id", default=None, metavar="KEY_ID")
    r.add_argument("--runner", default=None, metavar="ADDRESS",
                   help="the runner this key belongs to (its mailbox)")
    r.add_argument("--keyring", default=None, metavar="PATH")
    r.set_defaults(func=cmd_keyring)

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
