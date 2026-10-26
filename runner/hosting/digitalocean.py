"""DigitalOcean adapter: one Droplet per tenant, cloud-init bootstrap.

API: https://api.digitalocean.com/v2 (Bearer token). Shapes recorded
in runner/tests/hosting_fixtures/digitalocean.json.
"""
from __future__ import annotations

from . import base, bootstrap

API = "https://api.digitalocean.com/v2"
_STATES = {"new": "starting", "active": "running", "off": "stopped",
           "archive": "gone"}


class DigitalOcean(base.Provider):
    name = "digitalocean"

    def __init__(self, http, token, image="ubuntu-24-04-x64", api=API):
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
            code = message = None
            if isinstance(data, dict):
                code, message = data.get("id"), data.get("message")
            base.raise_for(resp, self.name, what or path, code=code,
                           message=message)
        return resp

    def _machine(self, droplet):
        if not isinstance(droplet, dict):
            raise base.ProviderError(f"{self.name}: malformed droplet record")
        ip = None
        nets = droplet.get("networks") if isinstance(
            droplet.get("networks"), dict) else {}
        for entry in nets.get("v4") or []:
            if isinstance(entry, dict) and entry.get("type") == "public":
                ip = entry.get("ip_address")
                break
        region = droplet.get("region") if isinstance(
            droplet.get("region"), dict) else {}
        tags = [t for t in (droplet.get("tags") or []) if isinstance(t, str)]
        tenant = version = None
        for t in tags:
            if t.startswith("hp-tenant-"):
                tenant = t[len("hp-tenant-"):]
            elif t.startswith("hp-version-"):
                version = t[len("hp-version-"):].replace("-", ".")
        return base.Machine(
            self.name, droplet.get("id"), name=droplet.get("name"),
            region=region.get("slug"),
            state=_STATES.get(str(droplet.get("status")), "created"),
            ip=ip, tenant=tenant, version=version, raw=droplet)

    def create(self, spec):
        # Droplet tags allow letters, digits, : - _ ; a version's dots
        # become dashes and are folded back in _machine.
        body = {
            "name": spec.name,
            "region": spec.region,
            "size": spec.size or "s-1vcpu-512mb-10gb",
            "image": self.image,
            "user_data": bootstrap.user_data(spec),
            "tags": [f"hp-tenant-{spec.tenant}",
                     f"hp-version-{str(spec.version).replace('.', '-')}"],
            "monitoring": False, "backups": False, "ipv6": True,
        }
        resp = self._call("POST", "/droplets", body, "create droplet")
        return self._machine((resp.json() or {}).get("droplet"))

    def get(self, machine_id):
        try:
            resp = self._call("GET", f"/droplets/{machine_id}",
                              what="get droplet")
        except base.NotFound:
            return base.Machine(self.name, machine_id, state="gone")
        return self._machine((resp.json() or {}).get("droplet"))

    def destroy(self, machine_id):
        try:
            self._call("DELETE", f"/droplets/{machine_id}",
                       what="delete droplet")
        except base.NotFound:
            return None
        return None
