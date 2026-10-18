#!/usr/bin/env python3
"""User extensions: packaged senses with a declared signal contract.

An extension is a folder holding one manifest, `extension.json`. The
manifest names the sense it files as, carries the extension's OWN
version (the author's inner-loop number, revved as often as they
like), the extension API version it was written against, and the
list of signals it may send the Oracle -- each signal named, with a
one-line description.

The declaration is the point. The agent never imports extension
code; the manifest and the signed sensor_alert envelope are the
whole surface the agent consumes. The declared signal names and
descriptions are surfaced to the Oracle alongside the sense's
alerts, so the model is never handed a signal nobody defined. An
alert from an extension-backed sense that names an undeclared
signal (or no signal) is rejected at ingest and logged.

Versioning is three distinct numbers, and only one of them is
expected to move:

- the agent version (the release number; the extension author
  does not control it and the manifest never mentions it),
- the extension's own `version` (semver; the author's number),
- `api_version` (the contract below).

EXTENSION_API_VERSION is 1 and is designed to stay 1. The promise:
manifest fields may be added, never removed or reinterpreted, so a
version-1 extension keeps loading on future agents. A manifest
naming a NEWER api_version than the agent provides is refused with
a readable reason; an older one is accepted. Unknown manifest
fields are refused by name, so a typo never silently does nothing.

Loading never raises: a broken or incompatible extension is
refused, reported, and the agent runs without it.

This module is deliberately free of runner imports, like senses.py:
runner.py calls in here.
"""
import hashlib
import hmac
import json
import os
import re
import socket
import uuid
from datetime import datetime, timezone

EXTENSION_API_VERSION = 1
MANIFEST_FILE = "extension.json"

KINDS = ("sense",)

_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_VERSION_RE = re.compile(
    r"\A\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z")

_REQUIRED_FIELDS = ("name", "version", "api_version", "kind", "signals")
_OPTIONAL_FIELDS = ("description", "tunables")
MAX_SIGNALS = 64
MAX_DESCRIPTION_CHARS = 200


def parse_manifest(data, where=MANIFEST_FILE) -> dict:
    """Validate one manifest. Returns the cleaned manifest dict.

    Raises ValueError with a readable reason on any problem. The
    cleaned dict carries exactly the manifest fields (defaults
    filled); the loader adds "dir" and "signal_descriptions".
    """
    if not isinstance(data, dict):
        raise ValueError(f"{where}: manifest must be a JSON object")
    unknown = sorted(set(data) - set(_REQUIRED_FIELDS) - set(_OPTIONAL_FIELDS))
    if unknown:
        raise ValueError(
            f"{where}: unknown field(s) {', '.join(unknown)} "
            f"(known: {', '.join(sorted(_REQUIRED_FIELDS + _OPTIONAL_FIELDS))})")
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"{where}: missing required field(s) {', '.join(missing)}")
    name = data["name"]
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(
            f"{where}: name must be a non-empty string of letters, "
            f"digits, '.', '_' or '-', starting with a letter or digit")
    version = data["version"]
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        raise ValueError(
            f"{where}: version must be the extension's own semver "
            f"string, like '0.3.0'")
    api_version = data["api_version"]
    if isinstance(api_version, bool) or not isinstance(api_version, int) \
            or api_version < 1:
        raise ValueError(f"{where}: api_version must be an integer >= 1")
    kind = data["kind"]
    if kind not in KINDS:
        raise ValueError(
            f"{where}: kind must be one of {sorted(KINDS)} "
            f"(the only extension kind today)")
    description = data.get("description", "")
    if not isinstance(description, str) \
            or len(description) > MAX_DESCRIPTION_CHARS \
            or "\n" in description or "\r" in description:
        raise ValueError(
            f"{where}: description must be a single line of at most "
            f"{MAX_DESCRIPTION_CHARS} characters")
    tunables = data.get("tunables", {})
    if not isinstance(tunables, dict):
        raise ValueError(f"{where}: tunables must be an object")
    signals = data["signals"]
    if not isinstance(signals, list) or not signals:
        raise ValueError(
            f"{where}: signals must be a non-empty list of "
            f"{{name, description}} objects")
    if len(signals) > MAX_SIGNALS:
        raise ValueError(
            f"{where}: signals is capped at {MAX_SIGNALS} entries; "
            f"the list is Oracle context, keep it small")
    clean_signals = []
    seen = set()
    for i, entry in enumerate(signals):
        ewhere = f"{where}: signals[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(ewhere + " must be an object")
        extra = sorted(set(entry) - {"name", "description"})
        if extra:
            raise ValueError(
                ewhere + f": unknown field(s) {', '.join(extra)}")
        if "name" not in entry or "description" not in entry:
            raise ValueError(ewhere + " needs both name and description")
        sname = entry["name"]
        if not isinstance(sname, str) or not _NAME_RE.match(sname):
            raise ValueError(
                ewhere + ".name must be a non-empty string of letters, "
                "digits, '.', '_' or '-'")
        if sname in seen:
            raise ValueError(ewhere + f": duplicate signal name {sname!r}")
        seen.add(sname)
        sdesc = entry["description"]
        if not isinstance(sdesc, str) or not sdesc.strip() \
                or len(sdesc) > MAX_DESCRIPTION_CHARS \
                or "\n" in sdesc or "\r" in sdesc:
            raise ValueError(
                ewhere + ".description must be one non-empty line of "
                f"at most {MAX_DESCRIPTION_CHARS} characters; it is "
                "the context the Oracle receives for this signal")
        clean_signals.append({"name": sname, "description": sdesc})
    return {
        "name": name,
        "version": version,
        "api_version": api_version,
        "kind": kind,
        "description": description,
        "tunables": dict(tunables),
        "signals": clean_signals,
    }


def api_refusal(manifest: dict):
    """None if this agent can load the manifest, else the reason.

    Newer than the agent provides: refused (the extension was
    written against a contract this agent does not have). Older:
    accepted -- the additive-only promise means an old manifest's
    fields all still mean what they meant. While
    EXTENSION_API_VERSION is 1 there is no older, but the rule is
    the contract, so it is stated and tested now.
    """
    try:
        wanted = manifest.get("api_version")
    except AttributeError:
        return "manifest is not an object"
    if isinstance(wanted, bool) or not isinstance(wanted, int):
        return "api_version is not an integer"
    if wanted > EXTENSION_API_VERSION:
        return (f"extension requires extension API v{wanted}; this agent "
                f"provides v{EXTENSION_API_VERSION} (update the agent)")
    return None


def signal_description(manifest, signal):
    """The declared one-line description for a signal, or None.

    None means the signal is not declared (or the manifest is not
    usable). Defensive like the senses plumbing: bad extension
    data answers None, never raises.
    """
    if not isinstance(manifest, dict) or not isinstance(signal, str):
        return None
    by_name = manifest.get("signal_descriptions")
    if isinstance(by_name, dict):
        desc = by_name.get(signal)
        return desc if isinstance(desc, str) else None
    for entry in manifest.get("signals") or []:
        if isinstance(entry, dict) and entry.get("name") == signal:
            desc = entry.get("description")
            return desc if isinstance(desc, str) else None
    return None


def extensions_dir_for(cfg, base_dir):
    """Resolve the extensions directory from config.

    cfg["extensions_dir"] wins; a relative value resolves against
    the base dir. With neither, the default is <base_dir>/extensions.
    Returns "" when there is nowhere to look.
    """
    raw = cfg.get("extensions_dir") if isinstance(cfg, dict) else None
    if isinstance(raw, str) and raw.strip():
        if os.path.isabs(raw) or not isinstance(base_dir, str) or not base_dir:
            return raw
        return os.path.join(base_dir, raw)
    if isinstance(base_dir, str) and base_dir:
        return os.path.join(base_dir, "extensions")
    return ""


def load_extensions(ext_dir):
    """Discover and validate every extension under ext_dir.

    Returns (registry, problems): registry maps sensor name ->
    cleaned manifest (plus "dir" and "signal_descriptions");
    problems is a list of readable refusal lines, one per folder
    that was skipped. A missing directory is normal -- most
    installs have no extensions -- and reports nothing. Never
    raises: extension data must not be able to abort the agent.
    """
    registry = {}
    problems = []
    if not isinstance(ext_dir, str) or not ext_dir:
        return registry, problems
    try:
        entries = sorted(os.listdir(ext_dir))
    except OSError:
        return registry, problems
    for entry in entries:
        if entry.startswith("."):
            continue
        folder = os.path.join(ext_dir, entry)
        try:
            if not os.path.isdir(folder):
                continue
        except OSError:
            continue
        mpath = os.path.join(folder, MANIFEST_FILE)
        where = f"extension folder {entry!r}"
        if not os.path.isfile(mpath):
            problems.append(f"{where}: no {MANIFEST_FILE}; skipped")
            continue
        if os.path.islink(mpath):
            problems.append(f"{where}: {MANIFEST_FILE} is a symlink; refused")
            continue
        try:
            with open(mpath, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, UnicodeDecodeError) as e:
            problems.append(f"{where}: cannot read {MANIFEST_FILE}: {e}")
            continue
        except ValueError as e:
            problems.append(f"{where}: {MANIFEST_FILE} is not valid JSON: {e}")
            continue
        try:
            manifest = parse_manifest(data, where=MANIFEST_FILE)
        except ValueError as e:
            problems.append(f"{where}: {e}")
            continue
        refusal = api_refusal(manifest)
        if refusal:
            problems.append(
                f"{where} ({manifest['name']!r} v{manifest['version']}): "
                f"refused: {refusal}")
            continue
        name = manifest["name"]
        if name in registry:
            problems.append(
                f"{where}: duplicate extension name {name!r}; "
                f"already loaded from {registry[name]['dir']!r}; skipped")
            continue
        manifest["dir"] = folder
        manifest["signal_descriptions"] = {
            s["name"]: s["description"] for s in manifest["signals"]}
        registry[name] = manifest
    return registry, problems


# ---------------------------------------------------------------------------
# Producing signals: the local delivery helpers.
#
# An extension author codes against the ENVELOPE, not the pipe.
# build_sensor_alert composes the one envelope; sign_envelope
# seals it with the sense's restricted key, byte-for-byte the
# scheme the agent verifies (the same construction as
# cloud/send_job.py). Two interchangeable front-ends then carry
# the identical signed text to a runner on the same machine:
#
# - drop_local_signal: the periodic style. The signed envelope
#   lands as one file in <base_dir>/local-inbox/ and the runner
#   files it within about a second. The filename is the
#   envelope's job_id, so re-dropping the same envelope rewrites
#   the same file: a producer on a timer needs no state beyond
#   its key, and each pass just builds fresh envelopes and drops
#   them.
# - send_local_signal: the direct style. The signed envelope is
#   pushed over one loopback TCP connection to the runner's
#   listener, for extensions whose own event machinery fires and
#   sends at once. No file is involved.
#
# Both envelopes carry "api_version": the extension API contract
# they were written against, validated by the agent on arrival
# exactly as a manifest's is (newer refused, older accepted). A
# future transport is new plumbing under the same contract; it
# changes nothing an author has written.

LOCAL_INBOX_DIRNAME = "local-inbox"
LOCAL_SIGNAL_DEFAULT_PORT = 39271


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sign_envelope(payload, secret) -> str:
    """Sign a payload dict; returns the signed envelope text.

    The signature is HMAC-SHA-384 over the compact JSON body,
    carried in the body itself as a trailing ,"sig":"..." field --
    the exact construction the agent's verify accepts on every
    path (mail included). Kept in step with cloud/send_job.py.
    """
    if not isinstance(payload, dict):
        raise ValueError("envelope payload must be an object")
    if not isinstance(secret, str) or not secret:
        raise ValueError("a signing secret is required")
    body = _normalize(json.dumps(payload, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False))
    if not body.endswith("}"):
        raise ValueError("envelope payload must serialize to a JSON object")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"),
                   hashlib.sha384).hexdigest()
    return body[:-1] + ',"sig":"' + sig + '"}'


def build_sensor_alert(sensor, severity, title, *, key_id="",
                       signal=None, detail=None, observed_at=None,
                       job_id=None, api_version=None) -> dict:
    """Compose one sensor_alert envelope payload (unsigned).

    The fields are the contract's fields: the protocol version
    ("v", the message protocol's number -- not the extension's,
    not the API's), the job envelope every delivery path carries,
    and the alert itself. "api_version" states the extension API
    the envelope was written against; it defaults to this
    module's EXTENSION_API_VERSION. Sign the result with
    sign_envelope, then deliver it by either front-end.
    """
    payload = {
        "v": 1,
        "type": "job",
        "job_id": job_id or uuid.uuid4().hex,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": "sensor_alert",
        "api_version": EXTENSION_API_VERSION
        if api_version is None else api_version,
        "sensor": sensor,
        "severity": severity,
        "title": title,
    }
    if key_id:
        payload["key_id"] = key_id
    if signal:
        payload["signal"] = signal
    if detail is not None:
        payload["detail"] = detail
    if observed_at:
        payload["observed_at"] = observed_at
    return payload


def drop_local_signal(base_dir, payload, secret) -> str:
    """Periodic style: drop the signed envelope into the inbox.

    Writes <base_dir>/local-inbox/<job_id>.json (atomically, via a
    temp file in the same directory) and returns its path. The
    producer's whole state is its key and this base_dir; dropping
    is safe to repeat on any cadence.
    """
    if not isinstance(base_dir, str) or not base_dir:
        raise ValueError("base_dir must be the runner's base directory")
    text = sign_envelope(payload, secret)
    inbox = os.path.join(base_dir, LOCAL_INBOX_DIRNAME)
    os.makedirs(inbox, exist_ok=True)
    job_id = payload.get("job_id") if isinstance(payload, dict) else None
    if not isinstance(job_id, str) or not _NAME_RE.match(job_id):
        job_id = uuid.uuid4().hex
    path = os.path.join(inbox, job_id + ".json")
    tmp = os.path.join(inbox, "." + job_id + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return path


def send_local_signal(payload, secret, port=LOCAL_SIGNAL_DEFAULT_PORT,
                      host="127.0.0.1", timeout=5.0) -> None:
    """Direct style: push the signed envelope to the listener.

    One connection, the envelope text, write side closed, done.
    Raises OSError when the runner is not listening, so the
    producer learns the delivery failed instead of assuming it.
    """
    text = sign_envelope(payload, secret)
    with socket.create_connection((host, int(port)),
                                  timeout=timeout) as conn:
        conn.sendall(text.encode("utf-8"))
        try:
            conn.shutdown(socket.SHUT_WR)
        except OSError:
            pass
