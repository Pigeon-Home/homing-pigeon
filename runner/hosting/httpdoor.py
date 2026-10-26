"""One HTTP door for every provider adapter.

Adapters never import urllib themselves: they take an `HttpClient`
and call `request`. Production hands them `UrllibHttp` (this module is named httpdoor so a
script-mode import never shadows the standard library's `http`); the suite
hands them a recorder-player (`runner/tests/test_hosting_providers.py`)
so no test ever reaches a real API.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class Response:
    """What a request came back with. `json()` parses lazily and
    returns None for an empty or non-JSON body."""

    __slots__ = ("status", "headers", "body")

    def __init__(self, status, headers=None, body=b""):
        self.status = int(status)
        self.headers = {str(k).lower(): str(v)
                        for k, v in (headers or {}).items()}
        self.body = body if isinstance(body, bytes) else \
            str(body or "").encode("utf-8")

    def json(self):
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def header(self, name, default=None):
        return self.headers.get(name.lower(), default)

    @property
    def ok(self):
        return 200 <= self.status < 300


class HttpClient:
    """The interface. `request` returns a Response for every HTTP
    status (a 4xx or 5xx is a Response, not an exception); only a
    transport failure (DNS, refused, timeout) raises `TransportError`."""

    def request(self, method, url, headers=None, body=None,
                timeout=30) -> Response:
        raise NotImplementedError


class TransportError(Exception):
    """The request never produced an HTTP status."""


class UrllibHttp(HttpClient):
    def __init__(self, user_agent="homing-pigeon-host"):
        self.user_agent = user_agent

    def request(self, method, url, headers=None, body=None,
                timeout=30) -> Response:
        data = None
        hdrs = {"User-Agent": self.user_agent}
        hdrs.update(headers or {})
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                hdrs.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                data = body.encode("utf-8")
            else:
                data = bytes(body)
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return Response(resp.status, dict(resp.headers.items()),
                                resp.read())
        except urllib.error.HTTPError as e:
            try:
                payload = e.read()
            except Exception:
                payload = b""
            return Response(e.code, dict(e.headers.items()) if e.headers
                            else {}, payload)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TransportError(f"{method} {url}: {e}")
