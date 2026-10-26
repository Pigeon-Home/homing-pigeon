# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Fly.io Machines adapter: one app per tenant, one Firecracker
microVM per app. Image-based: the runner image, the blob in env.

API: https://api.machines.dev/v1 (Bearer token). Shapes recorded in
runner/tests/hosting_fixtures/fly.json.
"""
from __future__ import annotations

from . import base, bootstrap

API = "https://api.machines.dev/v1"
# Fly's machine states, folded to ours.
_STATES = {"created": "created", "starting": "starting",
           "started": "running", "stopping": "stopped",
           "stopped": "stopped", "destroying": "gone",
           "destroyed": "gone", "replacing": "starting",
           "suspended": "stopped", "failed": "stopped"}


class FlyMachines(base.Provider):
    name = "fly"

    def __init__(self, http, token, app=None, org="personal", api=API):
        self.http = http
        self.token = token
        self.app = app
        self.org = org
        self.api = api.rstrip("/")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/json"}

    def _call(self, method, path, body=None, what=""):
        resp = self.http.request(method, self.api + path,
                                 headers=self._headers(), body=body)
        if not resp.ok:
            data = resp.json() or {}
            message = data.get("error") if isinstance(data, dict) else None
            base.raise_for(resp, self.name, what or path,
                           message=message)
        return resp

    def ensure_app(self, app_name):
        """Create the tenant's app unless it exists (422 = exists)."""
        resp = self.http.request(
            "POST", f"{self.api}/apps", headers=self._headers(),
            body={"app_name": app_name, "org_slug": self.org})
        if resp.ok:
            return True
        data = resp.json() or {}
        message = data.get("error") if isinstance(data, dict) else ""
        if resp.status == 422 and "already" in str(message).lower():
            return False
        base.raise_for(resp, self.name, "create app", message=message)
        return False

    def _app_for(self, spec):
        return self.app or f"hp-{spec.tenant}"

    def _machine(self, data):
        if not isinstance(data, dict):
            raise base.ProviderError(f"{self.name}: malformed machine record")
        cfg = data.get("config") if isinstance(data.get("config"), dict) \
            else {}
        meta = cfg.get("metadata") if isinstance(cfg.get("metadata"), dict) \
            else {}
        return base.Machine(
            self.name, data.get("id"), name=data.get("name"),
            region=data.get("region"),
            state=_STATES.get(str(data.get("state")), "created"),
            ip=data.get("private_ip"),
            tenant=meta.get("homing-pigeon.tenant"),
            version=meta.get("homing-pigeon.version"), raw=data)

    def create(self, spec):
        app = self._app_for(spec)
        self.ensure_app(app)
        self.app = app
        body = {
            "name": spec.name,
            "region": spec.region,
            "config": {
                "image": bootstrap.image_for(spec.version, spec.image),
                "env": bootstrap.container_env(spec),
                "guest": self._guest(spec.size),
                "restart": {"policy": "always"},
                "auto_destroy": False,
                "metadata": {k: str(v) for k, v in spec.labels.items()},
            },
        }
        resp = self._call("POST", f"/apps/{app}/machines", body,
                          "create machine")
        return self._machine(resp.json())

    @staticmethod
    def _guest(size):
        presets = {"shared-cpu-1x": (1, 256), "shared-cpu-1x-512": (1, 512),
                   "shared-cpu-2x": (2, 512)}
        cpus, mem = presets.get(size or "shared-cpu-1x", (1, 256))
        return {"cpu_kind": "shared", "cpus": cpus, "memory_mb": mem}

    def get(self, machine_id):
        try:
            resp = self._call("GET", f"/apps/{self.app}/machines/{machine_id}",
                              what="get machine")
        except base.NotFound:
            return base.Machine(self.name, machine_id, state="gone")
        return self._machine(resp.json())

    def destroy(self, machine_id):
        try:
            self._call("DELETE",
                       f"/apps/{self.app}/machines/{machine_id}?force=true",
                       what="destroy machine")
        except base.NotFound:
            return None
        return None
