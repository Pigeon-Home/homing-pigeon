"""Bounded fuzz of the parsers a bad mail or a bad config actually hits.

The runbook named Atheris. This tree stays stdlib-only, so the same
contract is a deterministic mutator: bytes in, expected errors out.
An AttributeError, a SystemExit, or a MemoryError is a crash.
ValueError and RuntimeError are the normal reject.

Nothing here starts a process, a sandbox, or a mailbox.
"""
import json
import os
import random
import tempfile
import unittest


SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)

# AttributeError, SystemExit, and MemoryError are crashes.
CRASH = (AttributeError, SystemExit, MemoryError, NameError, AssertionError)


def _expected():
    import re
    return (
        ValueError, TypeError, RuntimeError, KeyError, UnicodeError,
        OSError, OverflowError, ArithmeticError, json.JSONDecodeError,
        re.error, RecursionError,
    )


SEEDS = [
    b"",
    b"null",
    b"[]",
    b"{}",
    b"0",
    b'"x"',
    b'{"v":1,"type":"job","kind":"ping"}',
    b'{"shared_secret":"a","security":{"modes":{"audience":"off"}}}',
    b'{"sensors":{"disk":{"enabled":true,"key_id":"k","weight":1}}}',
    b'{"review_patterns_extra":[{"id":"x","pattern":"a","note":"n"}]}',
    b'{"resources":{"enabled":true,"threshold":0.9,"cooldown_sec":1}}',
    b'{"security":{"confinement":{"extra_flags":["--die-with-parent"],'
    b'"work_mount":"/work"}}}',
    "é".encode(),
    b"\xff\xfe",
    b'{"sig":"' + b"ab" * 48 + b'"}',
]


def _mutate(rng, blob):
    data = bytearray(blob)
    op = rng.randrange(6)
    if op == 0 or not data:
        data.extend(rng.randbytes(rng.randint(0, 24)))
    elif op == 1:
        i = rng.randrange(len(data))
        data[i] = rng.randrange(256)
    elif op == 2:
        i = rng.randrange(len(data) + 1)
        data[i:i] = rng.randbytes(rng.randint(1, 8))
    elif op == 3:
        i = rng.randrange(len(data))
        del data[i:i + rng.randint(1, 4)]
    elif op == 4:
        data = data[: rng.randint(0, max(1, len(data)))]
    else:
        data = data * rng.randint(1, 4)
    if len(data) > 4000:
        data = data[:4000]
    return bytes(data)


def _json_values(rng, blob):
    """A JSON value, or a stand-in when the bytes are not JSON."""
    try:
        text = blob.decode("utf-8")
    except UnicodeError:
        text = blob.decode("utf-8", "replace")
    try:
        return json.loads(text), text
    except Exception:
        choices = [text, None, [], {}, 0, True, blob]
        return choices[rng.randrange(len(choices))], text


def _nest(rng, depth):
    value = rng.choice([None, 0, "", "a", True])
    for _ in range(depth):
        value = {rng.choice(["a", "b", "self", "security"]): value}
    return value


class _Imap:
    def __init__(self, rng, blob):
        self.rng = rng
        self.blob = blob

    def search(self, *args):
        roll = self.rng.randrange(5)
        if roll == 0:
            raise RuntimeError("search")
        if roll == 1:
            return "NO", [self.blob]
        if roll == 2:
            return "OK", []
        if roll == 3:
            return "OK", [None]
        return "OK", [self.blob[:80]]

    def fetch(self, num, spec):
        roll = self.rng.randrange(4)
        if roll == 0:
            raise RuntimeError("fetch")
        if roll == 1:
            return "NO", []
        if roll == 2:
            return "OK", object()
        return "OK", [(num, self.blob)]


def _exercise(rng, blob):
    """One input against every surface. Returns a list of crash strings."""
    from runner.runner import (
        fetch_job_mails, load_config, reload_hot_config, verify_body,
        verify_body_keyed,
    )
    from runner.security import (
        validate_security_config, validate_shared_secret,
    )
    from runner.senses import gate_alert, parse_sensors
    from runner.review import parse_review_patterns
    from runner.sandbox import _validate_confinement_block, build_bwrap_command
    from runner.resources import parse_resources
    from cloud.send_job import verify_body as cloud_verify

    expected = _expected()
    crashes = []
    value, text = _json_values(rng, blob)

    def run(name, fn):
        try:
            fn()
        except CRASH as e:
            crashes.append("%s: %s: %r" % (name, type(e).__name__, e))
        except expected:
            return
        except Exception as e:
            crashes.append("%s: %s: %r" % (name, type(e).__name__, e))

    run("verify_body_keyed", lambda: verify_body_keyed(
        text, {"": SECRET, "k": SECRET}))
    run("verify_body", lambda: verify_body(text, SECRET))
    run("cloud_verify", lambda: cloud_verify(text, SECRET))
    run("validate_shared_secret", lambda: validate_shared_secret(
        text if isinstance(text, str) else ""))
    if isinstance(value, dict):
        run("validate_security_config",
            lambda: validate_security_config(value))
        run("parse_sensors", lambda: parse_sensors(value))
        run("parse_review_patterns", lambda: parse_review_patterns(value))
        run("parse_resources", lambda: parse_resources(value))
        block = value.get("security")
        if isinstance(block, dict):
            block = block.get("confinement", value)
        run("confinement", lambda: _validate_confinement_block(
            block if isinstance(block, dict) else value))
    else:
        run("parse_sensors", lambda: parse_sensors(value))
        run("parse_resources", lambda: parse_resources(value))
        run("confinement", lambda: _validate_confinement_block(value))

    run("gate_alert", lambda: gate_alert(value, value, value))
    run("fetch_job_mails", lambda: fetch_job_mails(_Imap(rng, blob)))

    # argv only. which() may fail. Never exec.
    env = value if isinstance(value, dict) else {}
    run("bwrap", lambda: build_bwrap_command(
        value if isinstance(value, dict) else {},
        ["not-a-real-interpreter-fuzz"], "job.sh", "/tmp", [], env))

    def _reload():
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "wb") as fh:
                fh.write(blob[:2000])
            try:
                load_config(path)
            except expected:
                pass
            reload_hot_config({"workers": 1}, path, {"mtime": 0})

    run("load_and_reload", _reload)
    return crashes


def campaign(rounds, seed):
    rng = random.Random(seed)
    crashes = []
    for i in range(rounds):
        blob = _mutate(rng, rng.choice(SEEDS))
        if i % 17 == 0:
            blob = json.dumps(_nest(rng, rng.randint(1, 40))).encode()
        found = _exercise(rng, blob)
        if found:
            crashes.append((blob[:80], found))
            if len(crashes) >= 5:
                break
    return crashes


class FuzzSurfacesTest(unittest.TestCase):
    def test_a_short_campaign_has_no_crash(self):
        crashes = campaign(200, 20261016)
        self.assertEqual(crashes, [])

    def test_user_error_seeds_do_not_crash(self):
        """The cases the coverage run already named, as fuzz seeds."""
        from runner.security import validate_shared_secret
        from runner.senses import store_alert
        from runner.runner import fetch_job_mails

        for secret in ("", "a", "aa", "0123456789abcdef" * 4, "Xxxĳ", "ėė"):
            with self.assertRaises(RuntimeError):
                validate_shared_secret(secret)

        class Imap:
            def search(self, *args):
                return "OK", [b"\xff 1"]

            def fetch(self, num, spec):
                return "OK", [(num, b"x")]

        self.assertEqual(fetch_job_mails(Imap()), [("1", b"x")])

        with tempfile.TemporaryDirectory() as directory:
            store_alert(directory, {"reading": float("nan"), "title": "t"})
            cycle = {}
            cycle["self"] = cycle
            store_alert(directory, cycle)


if __name__ == "__main__":
    found = campaign(400, 20261017)
    if found:
        for blob, crashes in found:
            print(crashes, blob)
        raise SystemExit(1)
    print("campaign ok")
