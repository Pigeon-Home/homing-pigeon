"""Signing, verification, secrets, key policies, and audience: what
authorizes a message before anything else happens (PROTOCOL.md
sections 4, 5, and 14).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Carved out of runner/runner.py, which binds every name here on
itself, so `runner.runner.verify_body` and the rest resolve as they
always did. Stdlib plus the sibling modules it leans on
(runner.guard.security for the entropy gate and the dangerous-env list,
runner.wire.jobcrypto for the result envelope, runner.wire.platformcard for
the platform's default interpreter); no import of runner.runner.
"""
import hashlib
import hmac
import json
import os
import re
import time

try:
    from runner.guard import security as _security
except ImportError:  # run as a script from the runner/ directory
    try:
        from guard import security as _security  # type: ignore
    except ImportError:  # pragma: no cover - fatal elsewhere
        _security = None
try:
    from runner.wire import jobcrypto as _jobcrypto
except ImportError:
    try:
        from wire import jobcrypto as _jobcrypto  # type: ignore
    except ImportError:
        _jobcrypto = None
try:
    from runner.wire.platformcard import platform_interpreter
except ImportError:
    from wire.platformcard import platform_interpreter  # type: ignore
try:
    from runner.guard.textutil import _json_safe
except ImportError:
    from guard.textutil import _json_safe  # type: ignore
try:
    from runner.guard import confval as _confval
except ImportError:
    from guard import confval as _confval  # type: ignore

PROTOCOL_VERSION = 1


SEEN_CAP = 2000


# ---------------------------------------------------------------- crypto
def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sign_payload(payload: dict, secret: str) -> str:
    if not isinstance(secret, str):
        raise ValueError("secret must be a string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    body = _normalize(json.dumps(_json_safe(payload), separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False))
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
    """Index of the `{` that opens the object ending at the sig marker.

    Every `{` before the marker is tried, newest first; the one taken
    is the first whose text up to the marker is a whole root object
    (the brace walk) and parses as a JSON object. That is the draft's
    step 6 stated as a check rather than as tracking: a `{` inside a
    string is never a valid root object on its own, so it fails the
    parse and the search moves on, whatever quote state a preamble
    put the body in.

    The earlier version tracked string state forward from offset 0
    and tried the braces it marked out-of-string first. A lopsided
    `"` in the preamble (a connector's quoted note) inverted that
    tracking for the whole body, its fallback then tried the in-string
    braces newest first, and a `{` inside a "{" key passed the brace
    walk: the extracted text was a fragment and a legitimately signed
    job was rejected as a signature mismatch (Q32, found by the
    preamble property under Hypothesis). A wrong candidate here fails
    the parse before any HMAC is computed; the HMAC still decides.
    """
    for start in range(sig_at - 1, -1, -1):
        if norm[start] != "{":
            continue
        if not _in_root_object_at(norm, start, sig_at):
            continue
        try:
            candidate = json.loads(norm[start:sig_at] + "}")
        except ValueError:
            continue
        if isinstance(candidate, dict):
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


def _strip_controls(text: str) -> str:
    """Drop raw control characters a mail transport may insert.

    Pretty-printed bodies sign their own newlines, so this is only used
    when the received form does not parse or does not verify. The
    signature is then checked against the cleaned form, which is what
    the sender signed.
    """
    return "".join(c for c in text if ord(c) >= 32 or c in "\t")


def verify_body(body: str, secret: str) -> dict:
    # Trailing whitespace is not signed. Surrounding text is ignored:
    # only the JSON object that ends in the signature is checked.
    if not isinstance(secret, str):
        raise ValueError("secret must be a string")
    norm = _normalize(body).rstrip()
    raw, sig = _extract_signed(norm)
    expect = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"),
                      hashlib.sha384).hexdigest()
    if not hmac.compare_digest(expect, sig.lower()):
        cleaned = _strip_controls(raw)
        expect = hmac.new(secret.encode("utf-8"), cleaned.encode("utf-8"),
                          hashlib.sha384).hexdigest()
        if not hmac.compare_digest(expect, sig.lower()):
            raise ValueError("signature mismatch")
        raw = cleaned
    job = json.loads(raw)
    if not isinstance(job, dict):
        raise ValueError("signed body is not a JSON object")
    return job


def _read_secret_file(path, label):
    """Read a secret from a file. Fails closed on any problem."""
    if not isinstance(path, str) or not path:
        raise RuntimeError(
            f"config error: {label} must be a path string")
    try:
        with open(path, encoding="utf-8") as fh:
            value = fh.read().strip()
    except OSError as e:
        raise RuntimeError(
            f"config error: cannot read {label} {path!r}: {e}")
    if not value:
        raise RuntimeError(
            f"config error: {label} {path!r} is empty")
    return value


def build_secrets(cfg) -> dict:
    """key_id -> secret. Default key is "". Every secret passes entropy gate.

    Secrets may come from files instead of inline config:
    shared_secret_file / additional_secrets_files. A secret may not be
    given both inline and via file.
    """
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config must be an object")
    secrets = {}
    inline = cfg.get("shared_secret") or ""
    secret_file = cfg.get("shared_secret_file")
    if inline and secret_file:
        raise RuntimeError("config error: shared_secret and "
                           "shared_secret_file are mutually exclusive")
    if secret_file:
        default = _read_secret_file(secret_file, "shared_secret_file")
    else:
        default = inline
    if not default:
        raise RuntimeError("config error: shared_secret is required "
                           "(or shared_secret_file)")
    validate_shared_secret(default)
    secrets[""] = default
    extra = cfg.get("additional_secrets") or {}
    if not isinstance(extra, dict):
        raise RuntimeError("config error: additional_secrets must be an object")
    extra_files = cfg.get("additional_secrets_files") or {}
    if not isinstance(extra_files, dict):
        raise RuntimeError(
            "config error: additional_secrets_files must be an object")
    for kid, sec in extra.items():
        if not isinstance(kid, str) or not isinstance(sec, str):
            raise RuntimeError("config error: additional_secrets keys and values must be strings")
        if kid == "":
            raise RuntimeError("config error: empty key_id reserved for default")
        validate_shared_secret(sec)
        secrets[kid] = sec
    for kid, path in extra_files.items():
        if not isinstance(kid, str) or not isinstance(path, str):
            raise RuntimeError("config error: additional_secrets_files keys and values must be strings")
        if kid == "":
            raise RuntimeError("config error: empty key_id reserved for default")
        if kid in secrets:
            raise RuntimeError(
                f"config error: key {kid!r} given both inline and via file")
        sec = _read_secret_file(path, f"additional_secrets_files[{kid!r}]")
        validate_shared_secret(sec)
        secrets[kid] = sec
    return secrets


def build_key_policies(cfg) -> dict:
    """key_id -> policy dict. Keys without an entry are unrestricted
    unless key_policies_default_deny is set (additional keys only;
    the default key "" is always unrestricted).

    A policy is opt-in least privilege for a key: allowed_kinds,
    allowed_interpreters, max_timeout_sec, allowed_script_sha384.
    Malformed policies fail closed at startup.
    """
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config must be an object")
    raw = cfg.get("key_policies") or {}
    if not isinstance(raw, dict):
        raise RuntimeError("config error: key_policies must be an object")
    policies = {}
    for kid, pol in raw.items():
        if not isinstance(kid, str):
            raise RuntimeError("config error: key_policies keys must be strings")
        if not isinstance(pol, dict):
            raise RuntimeError(
                f"config error: key_policies[{kid!r}] must be an object")
        clean: dict = {}
        if "allowed_kinds" in pol:
            kinds = pol["allowed_kinds"]
            if not isinstance(kinds, list) or not kinds or \
                    not all(isinstance(k, str) for k in kinds):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].allowed_kinds "
                    "must be a non-empty list of strings")
            clean["allowed_kinds"] = kinds
        if "allowed_interpreters" in pol:
            interps = pol["allowed_interpreters"]
            if not isinstance(interps, list) or not interps or not all(
                    isinstance(i, list) and i
                    and all(isinstance(x, str) for x in i)
                    for i in interps):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].allowed_interpreters "
                    "must be a non-empty list of string lists")
            clean["allowed_interpreters"] = interps
        if "max_timeout_sec" in pol:
            # A boolean is not a number here: `true` once became a
            # silent one-second cap for the key.
            if not _confval.is_number(pol["max_timeout_sec"]):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].max_timeout_sec "
                    "must be a number")
            mt = int(pol["max_timeout_sec"])
            if mt < 1:
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].max_timeout_sec "
                    "must be >= 1")
            clean["max_timeout_sec"] = mt
        if "allowed_script_sha384" in pol:
            hashes = pol["allowed_script_sha384"]
            if not isinstance(hashes, list) or not hashes or \
                    not all(isinstance(h, str) for h in hashes):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].allowed_script_sha384 "
                    "must be a non-empty list of strings")
            clean["allowed_script_sha384"] = [h.lower() for h in hashes]
        # Hardening M2: env/files/args constraints for pinned keys.
        if "allowed_env" in pol:
            allowed = pol["allowed_env"]
            if not isinstance(allowed, list) or not allowed or \
                    not all(isinstance(e, str) for e in allowed):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].allowed_env "
                    "must be a non-empty list of strings")
            clean["allowed_env"] = allowed
        if "denied_env" in pol:
            denied = pol["denied_env"]
            if not isinstance(denied, list) or \
                    not all(isinstance(e, str) for e in denied):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].denied_env "
                    "must be a list of strings")
            clean["denied_env"] = denied
        if "allow_dangerous_env" in pol:
            # Plan Appendix A gate: dangerous names stay refused even
            # when listed in allowed_env, unless this is boolean True.
            # Normalized fail-safe: anything that is not boolean True
            # (including truthy strings) keeps the gate shut.
            clean["allow_dangerous_env"] = pol["allow_dangerous_env"] is True
        if "allowed_files" in pol:
            allowed = pol["allowed_files"]
            if not isinstance(allowed, list) or not allowed or \
                    not all(isinstance(f, str) for f in allowed):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].allowed_files "
                    "must be a non-empty list of strings")
            clean["allowed_files"] = allowed
        if "allow_file_urls" in pol:
            # Plan M2: when false, any files entry with a URL is
            # refused. Default true when absent.
            if not isinstance(pol["allow_file_urls"], bool):
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].allow_file_urls "
                    "must be a boolean")
            clean["allow_file_urls"] = pol["allow_file_urls"]
        if "max_args" in pol:
            cap = pol["max_args"]
            if isinstance(cap, bool) or not isinstance(cap, int) \
                    or cap < 0:
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].max_args "
                    "must be an integer >= 0")
            clean["max_args"] = cap
        if "args_pattern" in pol:
            pattern = pol["args_pattern"]
            if not isinstance(pattern, str) or not pattern:
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].args_pattern "
                    "must be a non-empty string")
            try:
                rx = re.compile(pattern)
            except re.error as e:
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].args_pattern "
                    f"does not compile: {e}")
            # Bound probe: the pattern must handle a hostile input
            # quickly, since args are attacker-controlled. 30 a's makes
            # (a+)+$-style backtracking catastrophic on any machine.
            probe = "a" * 30 + "!"
            t0 = time.time()
            rx.fullmatch(probe)
            if time.time() - t0 > 1.0:
                raise RuntimeError(
                    f"config error: key_policies[{kid!r}].args_pattern "
                    "may backtrack catastrophically on hostile input")
            clean["args_pattern"] = pattern
        policies[kid] = clean
    return policies


def unrestricted_extra_keys(cfg) -> list:
    """key_ids in additional_secrets with no key_policies entry.

    The default key ("") is intentionally unrestricted and never
    listed. An entry here means a probably-forgotten policy: the key
    can do anything the default key can.
    """
    extra = cfg.get("additional_secrets") or {}
    policies = cfg.get("key_policies") or {}
    if not isinstance(extra, dict) or not isinstance(policies, dict):
        return []
    return sorted(k for k in extra
                  if isinstance(k, str) and k and k not in policies)


def check_key_policy(policies: dict, key_id: str, cfg, job):
    """Return None if the key's policy allows the job, else a reason string.

    Keys without a policy entry are unrestricted by default — the
    default stays loose. Set key_policies_default_deny to refuse
    everything from an additional key with no entry. The default key
    (key_id "") is always unrestricted: it is the owner.
    Every specified constraint must hold; the check runs on the
    effective interpreter and timeout (job value or configured
    default), mirroring execute_job.
    """
    if not isinstance(policies, dict):
        return "invalid key policy map"
    if not isinstance(job, dict):
        return "invalid job"
    if not isinstance(key_id, str):
        return "invalid key id"
    if not isinstance(cfg, dict):
        cfg = {}
    pol = policies.get(key_id)
    if not pol:
        if key_id != "" and cfg.get("key_policies_default_deny"):
            return ("no key policy entry for this key "
                    "(key_policies_default_deny)")
        return None
    if not isinstance(pol, dict):
        return "invalid key policy entry"
    kind = job.get("kind")
    if "allowed_kinds" in pol:
        kinds = pol["allowed_kinds"]
        if not isinstance(kinds, (list, tuple, set)):
            return "invalid key policy: allowed_kinds"
        if kind not in kinds:
            return f"job kind {kind!r} is not allowed for this key"
    interpreter = job.get("interpreter") or cfg.get("default_interpreter") \
        or platform_interpreter()
    if "allowed_interpreters" in pol:
        allowed = pol["allowed_interpreters"]
        if not isinstance(allowed, (list, tuple)) or not isinstance(interpreter, list) \
                or interpreter not in allowed:
            return f"interpreter {interpreter!r} is not allowed for this key"
    if "max_timeout_sec" in pol:
        # The job's own timeout, else the documented default of 300
        # (PROTOCOL.md). A default_timeout_sec present as null, a
        # non-number, or a boolean is not a timeout and must not turn
        # every timeout-less job away at this gate.
        default_timeout = _confval.integer(
            cfg.get("default_timeout_sec") if isinstance(cfg, dict) else None,
            300, lo=1)
        try:
            timeout = int(job.get("timeout_sec") or default_timeout)
        except (TypeError, ValueError, OverflowError):
            return "timeout_sec must be a number"
        if not _confval.is_number(pol["max_timeout_sec"]):
            return "invalid key policy: max_timeout_sec"
        cap = int(pol["max_timeout_sec"])
        if timeout > cap:
            return (f"timeout {timeout}s exceeds this key's limit "
                    f"of {cap}s")
    if "allowed_script_sha384" in pol and kind == "exec":
        # The allowlist pins exact scripts. script_url cannot be checked
        # before download, so it is not permitted under such a policy.
        script = job.get("script")
        if not isinstance(script, str):
            return ("this key may only run allowlisted scripts "
                    "(inline script required, script_url not permitted)")
        allow = pol["allowed_script_sha384"]
        if not isinstance(allow, (list, tuple, set)):
            return "invalid key policy: allowed_script_sha384"
        digest = hashlib.sha384(script.encode("utf-8")).hexdigest()
        if digest not in allow:
            return "script is not in this key's allowlist"
    return None


# Hardening M2/M4: moved to runner/guard/security.py; re-exported here so
# existing imports (runner.runner.validate_shared_secret, ...) keep
# working. If the security module failed to import, the stubs below
# fail closed instead of silently passing weak secrets.
DANGEROUS_ENV_NAMES = _security.DANGEROUS_ENV_NAMES \
    if _security is not None else frozenset()
if _security is not None:
    _estimate_secret_entropy = _security._estimate_secret_entropy
    _secret_pattern_reason = _security._secret_pattern_reason
    validate_shared_secret = _security.validate_shared_secret
else:  # pragma: no cover - import failure is already fatal elsewhere
    def _estimate_secret_entropy(secret):
        raise RuntimeError("security module unavailable")

    def _secret_pattern_reason(secret):
        raise RuntimeError("security module unavailable")

    def validate_shared_secret(secret):
        raise RuntimeError("security module unavailable")


def _env_name_in(name, lst):
    """Case-insensitive on Windows, exact elsewhere."""
    if not lst:
        return False
    if os.name == "nt":
        try:
            upper = name.upper()
            return any(isinstance(x, str) and x.upper() == upper for x in lst)
        except (AttributeError, TypeError):
            return False
    try:
        return name in lst
    except TypeError:
        return False


def check_policy_constraints(pol, key_id, cfg, job):
    """M2 constraints for env, files and args.

    Returns a list of (feature, reason, detail) findings. Only called
    for keys WITH a policy entry (D3): keys without an entry are
    unrestricted, and the default key ("") only when the owner adds
    an explicit "" entry. Never raises for a malformed job; bad job
    shapes are rejected elsewhere.
    """
    findings = []
    if not isinstance(pol, dict) or not isinstance(job, dict):
        return findings
    kind = job.get("kind")
    pinned = "allowed_script_sha384" in pol and kind == "exec"

    # --- policy_env ---
    env = job.get("env")
    if isinstance(env, dict) and env:
        denied = pol.get("denied_env") or []
        allowed = pol.get("allowed_env")  # None = not specified
        for name in env:
            if not isinstance(name, str):
                continue
            if _env_name_in(name, denied):
                findings.append(("policy_env", "denied_env",
                                 "env %r is denied for this key" % name))
            elif _security.is_dangerous_env_name(name) and not (
                    pol.get("allow_dangerous_env") is True
                    and _env_name_in(name, allowed)):
                # Plan Appendix A: dangerous names are refused even when
                # listed in allowed_env, unless the policy explicitly
                # opts in with allow_dangerous_env: true (boolean True
                # only — a truthy string does not open the gate).
                # The name must still be listed: the gate alone permits
                # nothing.
                findings.append(("policy_env", "dangerous_env",
                                 "env %r can subvert execution" % name))
            elif allowed is not None:
                if not _env_name_in(name, allowed):
                    findings.append(("policy_env", "env_not_allowed",
                                     "env %r is not in allowed_env" % name))
            elif pinned:
                findings.append(("policy_env", "pinned_script_with_env",
                                 "pinned script carries env that is not "
                                 "explicitly allowed"))

    # --- policy_files ---
    files = job.get("files")
    if isinstance(files, list) and files:
        allowed_files = pol.get("allowed_files")  # None = not specified
        for f in files:
            if not isinstance(f, dict):
                continue
            fname = f.get("name")
            if not isinstance(fname, str):
                continue
            if pol.get("allow_file_urls") is False and f.get("url"):
                findings.append(("policy_files", "file_url_not_allowed",
                                 "file %r carries a URL" % fname))
            elif isinstance(allowed_files, (list, tuple, set, frozenset)):
                if fname not in allowed_files:
                    findings.append(("policy_files", "file_not_allowed",
                                     "file %r is not in allowed_files"
                                     % fname))
            elif pinned:
                findings.append(("policy_files", "pinned_script_with_files",
                                 "pinned script stages files that are not "
                                 "explicitly allowed"))

    # --- policy_args ---
    args = job.get("args")
    if isinstance(args, list):
        max_args = pol.get("max_args")
        if isinstance(max_args, int) and not isinstance(max_args, bool) \
                and len(args) > max_args:
            findings.append(("policy_args", "args_too_many",
                             "more than %d args" % max_args))
    pattern = pol.get("args_pattern")
    if pattern and isinstance(args, list) and args:
        try:
            rx = re.compile(pattern)
        except (re.error, TypeError, ValueError):
            rx = None  # validated at startup; stay defensive
        if rx is not None:
            for a in args:
                if not isinstance(a, str):
                    continue
                if len(a) > 1024:
                    findings.append(("policy_args", "arg_too_long",
                                     "arg exceeds 1024 characters"))
                elif not rx.fullmatch(a):
                    findings.append(("policy_args", "arg_pattern_mismatch",
                                     "arg does not match args_pattern"))
    return findings


# Hardening M5: audience binding. The runner_id is read from the actual
# config the runner loaded, never from the signed body: the body only
# carries the *claimed* audience. A signed job for another runner is
# rejected in enforce mode, logged in audit mode, ignored when off.
def check_audience(cfg, payload):
    """Return 'runner_id mismatch' when the body's claimed audience does
    not match the configured runner_id, else None.

    Returns None when the feature is off or when no runner_id is
    configured (there is nothing to bind to).
    """
    if _security is None:
        return None
    if _security.sec_mode(cfg, "audience") == "off":
        return None
    expected = cfg.get("runner_id") if isinstance(cfg, dict) else None
    if not expected or not isinstance(expected, str):
        return None
    if not isinstance(payload, dict):
        return None
    # Plan M5: the signed audience field is `aud`. `runner_id` is also
    # accepted for jobs signed by older senders (v3.6.0); when both are
    # present, `aud` wins.
    claimed = payload.get("aud")
    if claimed is None:
        claimed = payload.get("runner_id")
    if claimed != expected:
        return "runner_id mismatch"
    return None


def audience_allows(cfg, base_dir, payload, key_id, ident):
    """Three-mode audience enforcement. Returns True when the message
    may proceed. In audit mode the decision is logged and processing
    continues; in enforce mode a mismatch denies."""
    if _security is not None and _security.sec_mode(cfg, "audience") != "off":
        _security.bump_evaluated(base_dir, "audience")
    if check_audience(cfg, payload) is None:
        return True
    if _security is None:
        return True
    decision = _security.sec_decide(
        cfg, base_dir, "audience", "runner_id_mismatch",
        {"key_id": key_id, "job_id": ident})
    return bool(decision)


def _seen_key(cfg, key):
    """Namespace a replay-cache (seen) key by runner_id when one is
    configured, so entries do not collide after the runner_id is set
    for the first time. Unchanged when no runner_id is configured."""
    rid = cfg.get("runner_id") if isinstance(cfg, dict) else None
    if isinstance(rid, str) and rid:
        return "%s:%s" % (rid, key)
    return key


def verify_body_keyed(body_text: str, secrets: dict):
    """Return (payload, key_id). Unknown key_id raises before any crypto."""
    if not isinstance(body_text, str):
        raise ValueError("body must be a string")
    if not isinstance(secrets, dict):
        raise ValueError("secrets must be an object")
    norm = _normalize(body_text).rstrip()
    raw, sig = _extract_signed(norm)
    # A mail transport may insert a control character (line wrap) into a
    # compact body. Try the received form first; if it does not parse or
    # the signature does not match, retry on the form with controls
    # removed. The signature is over the cleaned form.
    candidates = [raw]
    cleaned = _strip_controls(raw)
    if cleaned != raw:
        candidates.append(cleaned)
    last_err = None
    for cand in candidates:
        try:
            payload = json.loads(cand)
        except Exception as e:
            last_err = e
            continue
        if not isinstance(payload, dict):
            raise ValueError("signed body must be a JSON object")
        # Key selection follows the draft (Section 10) exactly:
        # absent selects the default secret; a present key_id
        # must be a string in the map (the empty string names
        # the default secret); anything else -- null, a boolean,
        # a number, an unknown string -- is rejected before any
        # MAC is computed, never silently mapped to the default.
        if "key_id" in payload:
            key_id = payload["key_id"]
        else:
            key_id = ""
        if not isinstance(key_id, str) or key_id not in secrets:
            raise ValueError(f"unknown key_id {key_id!r}")
        secret = secrets[key_id]
        if not isinstance(secret, str):
            raise ValueError("secret must be a string")
        expect = hmac.new(secret.encode("utf-8"), cand.encode("utf-8"),
                          hashlib.sha384).hexdigest()
        if hmac.compare_digest(expect, sig.lower()):
            payload["sig"] = sig
            return payload, key_id
        last_err = ValueError("bad signature")
    if last_err and not isinstance(last_err, ValueError):
        raise ValueError(f"invalid JSON: {last_err}") from last_err
    if isinstance(last_err, ValueError) and "bad signature" in str(last_err):
        raise last_err
    raise ValueError(f"invalid JSON: {last_err}")


def _job_encryption_setting(cfg):
    """The owner's job_encryption choice for RESULT encryption:
    True or False when the key is present in config, None when it
    is absent. Only the literal False counts as false (the same
    discipline as mail_tls_required). Absent means results mirror
    the job's own form: an encrypted job gets an encrypted result,
    a cleartext job a cleartext one. An explicit true encrypts
    every result (even a cleartext job's); an explicit false
    encrypts none."""
    if not isinstance(cfg, dict) or "job_encryption" not in cfg:
        return None
    return cfg.get("job_encryption") is not False


def _outgoing_result_body(result, secret, encrypt, job_id, key_id):
    """Sign a result body, and encrypt it when this job's result
    travels encrypted. The encrypted form encrypts the signed
    body whole and signs the envelope, exactly as job senders
    do, so a receiver verifies before it decrypts."""
    body = sign_payload(result, secret)
    if encrypt and _jobcrypto is not None:
        body = _jobcrypto.encrypt_body(body, secret, job_id=job_id,
                                       key_id=key_id,
                                       sign=sign_payload)
    return body
