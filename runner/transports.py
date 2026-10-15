#!/usr/bin/env python3
"""Transport adapters.

The contract (TRANSPORTS.md): send(queue, blob), poll(queue) -> [blob],
ack(blob_id). Blobs are opaque signed JSON. The runner never opens an
inbound port for a deployment transport.

Implemented:
- email        — Transport #1, SMTP send + IMAP poll
- local_socket — loopback TCP for the local SI harness (test only)
- cloudflare   — Cloudflare Queues HTTP API (the documented pick)

The others (NATS, MQTT, Redis, Postgres, Durable Objects) share the
same interface and raise NotImplementedError until wired.
"""
import json
import os
import struct
import threading


class Transport:
    name = "base"

    def send(self, queue: str, blob: str) -> str:
        raise NotImplementedError

    def poll(self, queue: str):
        raise NotImplementedError

    def ack(self, blob_id: str) -> None:
        raise NotImplementedError


class EmailTransport(Transport):
    """Transport #1. Uses the runner's SMTP/IMAP helpers."""

    name = "email"

    def __init__(self, cfg, runner_mod):
        self.cfg = cfg
        self.R = runner_mod

    def send(self, queue: str, blob: str) -> str:
        subject = f"[HOMING-PIGEON] job {queue}"
        smtp = self.R.connect_smtp(self.cfg)
        try:
            self.R.send_mail(smtp, self.cfg, subject, blob)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        return queue

    def poll(self, queue: str):
        # The runner's poll_once is the poll. Exposed so the contract holds.
        return []

    def ack(self, blob_id: str) -> None:
        return None


class LocalSocketTransportAdapter(Transport):
    """Loopback TCP. Test harness only. Not a deployment transport.

    Framing: 4-byte big-endian length, then the blob. Bind 127.0.0.1.
    """

    name = "local_socket"

    def __init__(self, port=8766):
        self.port = port
        self._inbox = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sock = None

    def start(self):
        import socket
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self._sock.listen(32)
        self._sock.settimeout(0.3)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        import socket
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _read(self, conn):
        try:
            hdr = self._readn(conn, 4)
            if not hdr:
                return
            (n,) = struct.unpack("!I", hdr)
            blob = self._readn(conn, n)
            if blob:
                with self._lock:
                    self._inbox.append(blob.decode("utf-8", "replace"))
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _readn(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return b""
            buf += chunk
        return buf

    def send(self, queue: str, blob: str) -> str:
        import socket
        s = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            data = blob.encode("utf-8")
            s.sendall(struct.pack("!I", len(data)) + data)
        finally:
            s.close()
        return queue

    def poll(self, queue: str):
        with self._lock:
            items = list(self._inbox)
            self._inbox.clear()
        return items

    def ack(self, blob_id: str) -> None:
        return None

    def stop(self):
        self._stop.set()
        try:
            self._sock.close()
        except Exception:
            pass


class CloudflareQueuesTransport(Transport):
    """Cloudflare Queues over the HTTP API. Stdlib only.

    Config keys: cf_account_id, cf_api_token, cf_queue_id.
    """

    name = "cloudflare"

    def __init__(self, cfg, opener=None):
        self.cfg = cfg
        self.opener = opener

    def _request(self, method, url, body=None):
        from urllib.request import Request, urlopen
        data = None if body is None else json.dumps(body).encode()
        req = Request(
            url, data=data, method=method,
            headers={
                "Authorization": f"Bearer {self.cfg.get('cf_api_token', '')}",
                "Content-Type": "application/json",
            },
        )
        open_fn = self.opener or urlopen
        with open_fn(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def _url(self):
        acct = self.cfg.get("cf_account_id") or ""
        qid = self.cfg.get("cf_queue_id") or ""
        return (f"https://api.cloudflare.com/client/v4/accounts/{acct}"
                f"/queues/{qid}/messages")

    def send(self, queue: str, blob: str) -> str:
        if not self.cfg.get("cf_api_token"):
            raise RuntimeError("cf_api_token not set")
        self._request("POST", self._url(), {"body": blob})
        return queue

    def poll(self, queue: str):
        if not self.cfg.get("cf_api_token"):
            return []
        # Pull is a separate endpoint; return [] until the pull path is
        # configured. Send is the SI side this harness needs first.
        return []

    def ack(self, blob_id: str) -> None:
        return None


class NotYetTransport(Transport):
    def __init__(self, name):
        self.name = name

    def send(self, queue, blob):
        raise NotImplementedError(f"{self.name} transport not implemented")

    def poll(self, queue):
        raise NotImplementedError(f"{self.name} transport not implemented")

    def ack(self, blob_id):
        raise NotImplementedError(f"{self.name} transport not implemented")


def get_transport(name: str, cfg, runner_mod=None):
    if name == "email":
        return EmailTransport(cfg, runner_mod)
    if name == "local_socket":
        return LocalSocketTransportAdapter()
    if name == "cloudflare":
        return CloudflareQueuesTransport(cfg)
    if name in ("nats", "mqtt", "redis", "postgres", "durable_objects"):
        return NotYetTransport(name)
    raise ValueError(f"unknown transport {name}")
