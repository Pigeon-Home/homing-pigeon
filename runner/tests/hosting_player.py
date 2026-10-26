# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""A recorder-player HttpClient for the hosting adapters.

The suite never reaches a real API. A `Player` is loaded with named
exchanges from runner/tests/hosting_fixtures/<provider>.json and a
script: the sequence of exchange names it should answer with. Each
call is checked against the recorded request (method, URL suffix,
body keys) and answered with the recorded response; every call is
kept in `calls` so a test can assert what the adapter sent.

Not a test module itself (no test_ prefix); imported by the hosting
tests.
"""
import json
import os

from runner.hosting.httpdoor import HttpClient, Response, TransportError

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "hosting_fixtures")


def load(provider):
    with open(os.path.join(FIXTURES, provider + ".json"),
              encoding="utf-8") as fh:
        data = json.load(fh)
    return {entry["name"]: entry for entry in data}


class Player(HttpClient):
    def __init__(self, provider, script):
        self.exchanges = load(provider)
        self.script = list(script)
        self.calls = []
        self.cursor = 0

    def request(self, method, url, headers=None, body=None, timeout=30):
        if self.cursor >= len(self.script):
            raise AssertionError(
                f"unexpected call {method} {url}: script exhausted after "
                f"{len(self.script)} exchange(s)")
        step = self.script[self.cursor]
        self.cursor += 1
        if step == "TRANSPORT-FAIL":
            raise TransportError(f"{method} {url}: connection refused")
        entry = self.exchanges[step]
        want = entry["request"]
        if want.get("method") and want["method"] != method:
            raise AssertionError(f"{step}: expected {want['method']}, got "
                                 f"{method} {url}")
        if want.get("url") and not url.endswith(want["url"]):
            raise AssertionError(f"{step}: url {url!r} does not end with "
                                 f"{want['url']!r}")
        sent = body if isinstance(body, dict) else (
            json.loads(body) if isinstance(body, (str, bytes)) and body
            else {})
        for key in want.get("body_has") or []:
            if key not in sent:
                raise AssertionError(f"{step}: request body lacks {key!r}: "
                                     f"{sorted(sent)}")
        self.calls.append({"name": step, "method": method, "url": url,
                           "headers": dict(headers or {}), "body": sent})
        resp = entry["response"]
        if "json" in resp:
            payload = json.dumps(resp["json"]).encode("utf-8")
        else:
            payload = str(resp.get("body", "")).encode("utf-8")
        return Response(resp["status"], resp.get("headers") or {}, payload)

    def exhausted(self):
        return self.cursor == len(self.script)
