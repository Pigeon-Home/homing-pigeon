"""Hetzner Cloud adapter: one VM per tenant, cloud-init bootstrap.

API: https://api.hetzner.cloud/v1 (Bearer token). Shapes recorded in
runner/tests/hosting_fixtures/hetzner.json.
"""
from __future__ import annotations

from . import base, bootstrap

API = "https://api.hetzner.cloud/v1"
_STATES = {"initializing": "starting", "starting": "starting",
           "running": "running", "stopping": "stopped", "off": "stopped",
           "deleting": "gone", "migrating": "starting",
           "rebuilding": "starting", "unknown": "created"}


class HetznerCloud(base.Provider):
    name = "hetzner"

    def __init__(self, http, token, image="ubuntu-24.04", api=API):
        self.http = http
        self.token = token
        self.image = image
        self.api = api.rstrip("/")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/json"}

    def _call(self, method, path, body=None, what=""):
        resp = self.http.request(method, self.api + path,
                                 headers=self._headers(), body=body)
        if not resp.ok:
            data = resp.json() or {}
            err = data.get("error") if isinstance(data, dict) else None
            code = message = None
            if isinstance(err, dict):
                code, message = err.get("code"), err.get("message")
            base.raise_for(resp, self.name, what or path, code=code,
                           message=message)
        return resp

    def _machine(self, server):
        if not isinstance(server, dict):
            raise base.ProviderError(f"{self.name}: malformed server record")
        net = server.get("public_net") if isinstance(
            server.get("public_net"), dict) else {}
        v4 = net.get("ipv4") if isinstance(net.get("ipv4"), dict) else {}
        labels = server.get("labels") if isinstance(
            server.get("labels"), dict) else {}
        dc = server.get("datacenter") if isinstance(
            server.get("datacenter"), dict) else {}
        loc = dc.get("location") if isinstance(dc.get("location"), dict) \
            else {}
        return base.Machine(
            self.name, server.get("id"), name=server.get("name"),
            region=loc.get("name"),
            state=_STATES.get(str(server.get("status")), "created"),
            ip=v4.get("ip"), tenant=labels.get("homing-pigeon.tenant"),
            version=labels.get("homing-pigeon.version"), raw=server)

    def create(self, spec):
        body = {
            "name": spec.name,
            "server_type": spec.size or "cx23",
            "image": self.image,
            "location": spec.region,
            "user_data": bootstrap.user_data(spec),
            "labels": {k: str(v) for k, v in spec.labels.items()},
            "public_net": {"enable_ipv4": True, "enable_ipv6": True},
            "start_after_create": True,
        }
        resp = self._call("POST", "/servers", body, "create server")
        data = resp.json() or {}
        return self._machine(data.get("server"))

    def get(self, machine_id):
        try:
            resp = self._call("GET", f"/servers/{machine_id}",
                              what="get server")
        except base.NotFound:
            return base.Machine(self.name, machine_id, state="gone")
        return self._machine((resp.json() or {}).get("server"))

    def destroy(self, machine_id):
        try:
            self._call("DELETE", f"/servers/{machine_id}",
                       what="delete server")
        except base.NotFound:
            return None
        return None
