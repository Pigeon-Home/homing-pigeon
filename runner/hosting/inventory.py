"""The control plane's memory: which machine belongs to which tenant.

A JSON file, one record per machine, written atomically. The one rule
it enforces is the isolation rule: a tenant has at most one resident
machine per provider, and a machine never changes tenant.
"""
from __future__ import annotations

import json
import os
import tempfile
import time


class IsolationError(Exception):
    """Two tenants on one machine, or two machines for one tenant."""


class Inventory:
    def __init__(self, path):
        self.path = path
        self.machines = {}
        self.dispatches = []
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            m = data.get("machines")
            if isinstance(m, dict):
                self.machines = {str(k): v for k, v in m.items()
                                 if isinstance(v, dict)}
            d = data.get("dispatches")
            if isinstance(d, list):
                self.dispatches = [x for x in d if isinstance(x, dict)]

    def save(self):
        folder = os.path.dirname(os.path.abspath(self.path)) or "."
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".inventory-", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"machines": self.machines,
                           "dispatches": self.dispatches}, fh, indent=2,
                          sort_keys=True)
                fh.write("\n")
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def key(provider, machine_id):
        return f"{provider}:{machine_id}"

    def resident_for(self, tenant, provider=None):
        """The tenant's resident machine record(s)."""
        out = []
        for rec in self.machines.values():
            if rec.get("tenant") == tenant and rec.get("state") != "gone" \
                    and (provider is None or rec.get("provider") == provider):
                out.append(rec)
        return out

    def place(self, machine, tenant):
        """Record a machine for a tenant, refusing a second resident
        machine for that tenant on that provider, or a tenant change."""
        key = self.key(machine.provider, machine.id)
        existing = self.machines.get(key)
        if existing and existing.get("tenant") not in (None, tenant):
            raise IsolationError(
                f"machine {key} belongs to tenant {existing.get('tenant')!r}, "
                f"not {tenant!r}")
        others = [r for r in self.resident_for(tenant, machine.provider)
                  if self.key(r["provider"], r["id"]) != key]
        if others:
            raise IsolationError(
                f"tenant {tenant!r} already has a resident machine on "
                f"{machine.provider}: {others[0]['id']}; destroy it first")
        rec = machine.to_record()
        rec["tenant"] = tenant
        rec["placed_at"] = existing.get("placed_at") if existing else \
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rec["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.machines[key] = rec
        return rec

    def update(self, machine):
        key = self.key(machine.provider, machine.id)
        rec = self.machines.get(key)
        if rec is None:
            return None
        rec.update({"state": machine.state, "ip": machine.ip or rec.get("ip"),
                    "version": machine.version or rec.get("version"),
                    "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())})
        return rec

    def forget(self, provider, machine_id):
        return self.machines.pop(self.key(provider, machine_id), None)

    def record_dispatch(self, dispatch, tenant):
        rec = dispatch.to_record()
        rec["tenant"] = tenant
        rec["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.dispatches.append(rec)
        return rec
