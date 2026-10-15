#!/usr/bin/env python3
"""Transport adapters.

The contract is in TRANSPORTS.md: send, poll, ack. Blobs are opaque
signed JSON. The runner does not open an inbound port.

Only two transports are on the code path:

- email: SMTP send and IMAP poll
- cloudflare: Cloudflare Queues over HTTP

Any other name is refused.
"""
import json


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
        """Pull messages. Returns list of body strings."""
        if not self.cfg.get("cf_api_token"):
            return []
        url = self._url() + "/pull"
        try:
            data = self._request("POST", url, {"visibility_timeout_ms": 30000, "batch_size": 10})
        except Exception:
            return []
        out = []
        for msg in (data.get("result") or {}).get("messages") or []:
            body = msg.get("body")
            if isinstance(body, str):
                out.append(body)
        return out

    def ack(self, blob_id: str) -> None:
        if not self.cfg.get("cf_api_token") or not blob_id:
            return
        url = self._url() + "/ack"
        try:
            self._request("POST", url, {"acks": [{"lease_id": blob_id}]})
        except Exception:
            pass



def get_transport(name: str, cfg, runner_mod=None):
    if name == "email":
        return EmailTransport(cfg, runner_mod)
    if name == "cloudflare":
        return CloudflareQueuesTransport(cfg)
    raise ValueError(f"unknown transport {name}")
