# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""The panic word (questions.md Q100; PROTOCOL.md section 14.3).

A stop the owner can send from a phone that holds no secret, and that
the holder of a leaked shared secret cannot undo by message. The
installer generates a six-word phrase and prints it once; the box
keeps only a salted SHA-384 of it in ``panic.json`` beside the config.
A message on any transport whose subject is exactly
``[HOMING-PIGEON] panic <word>`` fires it, before any MAC work and
before the seen-set. Firing stops every running job, stops polling,
refuses every key, writes one security event, and writes
``panicked.json``, which the runner reads on every cycle and at
start, so a restart does not resume. No reply goes out. Only
``install.py --rearm``, on the box, clears it and prints a new word.

The protection is real only where the job cannot write to this file,
the flag or the runner (``job_user`` separation, a read-only install).
``protection()`` says which case a box is in.

stdlib only.
"""
from __future__ import annotations

import email.header
import hashlib
import hmac
import json
import os
import secrets as _secrets
import threading
import time

try:
    from runner.guard import atomicio as _atomicio
except ImportError:  # running from inside runner/ as __main__
    try:
        from guard import atomicio as _atomicio  # type: ignore
    except ImportError:  # loaded by path (the frozen installer)
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "hp_atomicio", os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "atomicio.py"))
        _atomicio = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
        _spec.loader.exec_module(_atomicio)  # type: ignore[union-attr]

LABEL = b"homing-pigeon panic v1\n"
PREFIX = "[homing-pigeon]"
VERB = "panic"
WORDS = 6
STATE_FILE = "panic.json"
FLAG_FILE = "panicked.json"

# The fixed list: every consonant-vowel-consonant-vowel word over
# these letters, 16 * 5 * 16 * 5 = 6400 words, about 12.6 bits each,
# about 75.8 bits for six. Short, pronounceable, no capitals, and
# nothing a phone's keyboard has to reach for.
_CONSONANTS = "bdfghjklmnprstvz"
_VOWELS = "aeiou"
WORDLIST = tuple(a + b + c + d for a in _CONSONANTS for b in _VOWELS
                 for c in _CONSONANTS for d in _VOWELS)
_WORDSET = frozenset(WORDLIST)

_LOCK = threading.Lock()
_LIVE = set()          # running job processes, killed when it fires
_FIRED = False         # this process saw the flag or fired it
_KILL = None           # kill function for one process (runner.kill_tree)
_ANNOUNCED = False     # the stopped-box line was logged in this process


def generate_word(choice=_secrets.choice) -> str:
    """Six words from the fixed list, chosen by the OS's CSPRNG."""
    return " ".join(choice(WORDLIST) for _ in range(WORDS))


def normalize(text) -> str | None:
    """The canonical form of a typed word, or None when it is not six
    words from the list. Case, hyphens, underscores, commas and runs
    of white space are what a phone's keyboard changes; they do not
    change the word."""
    if not isinstance(text, str):
        return None
    for sep in "-_,.":
        text = text.replace(sep, " ")
    parts = text.lower().split()
    if len(parts) != WORDS or any(p not in _WORDSET for p in parts):
        return None
    return " ".join(parts)


def _digest(salt: bytes, word: str) -> str:
    return hashlib.sha384(LABEL + salt + word.encode("ascii")).hexdigest()


def _subject_text(subject) -> str:
    """The subject as a person typed it: RFC 2047 words decoded, one
    line. Anything that does not decode is taken as it stands."""
    text = str(subject or "")
    try:
        text = str(email.header.make_header(email.header.decode_header(text)))
    except Exception:
        pass
    return " ".join(text.split())


def word_in_subject(subject) -> str | None:
    """The normalized word when the subject is exactly
    ``[HOMING-PIGEON] panic <word>`` (case-insensitive), else None.
    A reply or a forward (``Re:``, ``Fwd:``) is not a panic."""
    text = _subject_text(subject)
    low = text.lower()
    if not low.startswith(PREFIX):
        return None
    rest = text[len(PREFIX):].strip()
    head, _, tail = rest.partition(" ")
    if head.lower() != VERB:
        return None
    return normalize(tail)


def _path(base_dir, name):
    return os.path.join(base_dir, name)


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load(base_dir):
    """The stored salt and digest, or None when not armed or unusable."""
    data = _read_json(_path(base_dir, STATE_FILE))
    if not data or data.get("v") != 1:
        return None
    salt, digest = data.get("salt"), data.get("sha384")
    if not isinstance(salt, str) or not isinstance(digest, str):
        return None
    try:
        salt_b = bytes.fromhex(salt)
    except ValueError:
        return None
    if len(salt_b) < 16 or len(digest) != 96:
        return None
    return salt_b, digest.lower()


def arm(base_dir, word=None, now=None) -> str:
    """Store a new word's digest, clear the flag, and return the word
    for the installer to print once. Never called by a message."""
    word = normalize(word) if word is not None else generate_word()
    if word is None:
        raise ValueError("the panic word is six words from the list")
    salt = _secrets.token_bytes(32)
    record = {"v": 1, "salt": salt.hex(), "sha384": _digest(salt, word),
              "armed_at": _iso(now)}
    _atomicio.write_json(_path(base_dir, STATE_FILE), record, mode=0o600)
    try:
        os.unlink(_path(base_dir, FLAG_FILE))
    except FileNotFoundError:
        pass
    global _FIRED
    with _LOCK:
        _FIRED = False
    return word


def matches(base_dir, subject) -> bool:
    """True when the subject carries the armed word. One hash per
    message whose subject has the panic shape; nothing else is read."""
    word = word_in_subject(subject)
    if word is None:
        return False
    stored = load(base_dir)
    if stored is None:
        return False
    salt, digest = stored
    return hmac.compare_digest(_digest(salt, word), digest)


def fired(base_dir=None) -> bool:
    """True once this process fired, or when the flag is on disk."""
    global _FIRED
    if _FIRED:
        return True
    if base_dir and os.path.lexists(_path(base_dir, FLAG_FILE)):
        with _LOCK:
            _FIRED = True
        return True
    return False


def flag(base_dir):
    """What the flag file says (when, transport), or None."""
    return _read_json(_path(base_dir, FLAG_FILE))


def fire(base_dir, transport=None, now=None, event_sink=None) -> None:
    """Stop the box: write the flag, kill every live job, record one
    event. Idempotent: a second word on a stopped box changes nothing."""
    global _FIRED
    with _LOCK:
        already = _FIRED or os.path.lexists(_path(base_dir, FLAG_FILE))
        _FIRED = True
        live = list(_LIVE)
    if not already:
        record = {"v": 1, "fired_at": _iso(now),
                  "transport": transport if isinstance(transport, str) else ""}
        try:
            _atomicio.write_json(_path(base_dir, FLAG_FILE), record,
                                 mode=0o600, fsync=True)
        except Exception:
            pass  # the in-process flag still holds every later message
    for proc in live:
        kill(proc)
    if not already and event_sink is not None:
        try:
            event_sink({"type": "panic_fired", "ts": _iso(now),
                        "transport": transport or "",
                        "jobs_stopped": len(live)})
        except Exception:
            pass


def announce_once() -> bool:
    """True the first time a stopped box is reported in this process."""
    global _ANNOUNCED
    with _LOCK:
        first = not _ANNOUNCED
        _ANNOUNCED = True
    return first


def set_kill(fn) -> None:
    global _KILL
    _KILL = fn


def kill(proc) -> None:
    try:
        if _KILL is not None:
            _KILL(proc)
        else:
            proc.kill()
    except Exception:
        pass


def register(proc) -> None:
    """A job process started. If the box fired in the meantime it is
    killed at once."""
    with _LOCK:
        _LIVE.add(proc)
        stop = _FIRED
    if stop:
        kill(proc)


def unregister(proc) -> None:
    with _LOCK:
        _LIVE.discard(proc)


def protection(cfg) -> str:
    """Which case the box is in, for the doctor: the word holds against
    a leaked secret only when the job runs as another user."""
    sec = cfg.get("security") if isinstance(cfg, dict) else None
    sec = sec if isinstance(sec, dict) else {}
    modes = sec.get("modes") if isinstance(sec.get("modes"), dict) else {}
    ju = sec.get("job_user") if isinstance(sec.get("job_user"), dict) else {}
    user = ju.get("user")
    if os.name != "nt" and modes.get("job_user") == "enforce" \
            and isinstance(user, str) and user.strip():
        return ("jobs run as another user; a job cannot reach the "
                "panic file")
    return ("jobs run as the runner's user; a job sent before the word "
            "can remove it (security.job_user in enforce for the word "
            "to hold)")


def state(base_dir) -> str:
    """armed, fired, or not armed."""
    if os.path.lexists(_path(base_dir, FLAG_FILE)):
        return "fired"
    return "armed" if load(base_dir) is not None else "not armed"


def _iso(now=None) -> str:
    t = time.time() if now is None else now
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _reset_for_tests() -> None:
    global _FIRED, _KILL, _ANNOUNCED
    with _LOCK:
        _FIRED = False
        _ANNOUNCED = False
        _LIVE.clear()
    _KILL = None
