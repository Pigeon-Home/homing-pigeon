# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The provider interface every adapter implements, and the errors
they all raise. The CLI and the tests speak only this vocabulary.
"""
from __future__ import annotations

import time


class ProviderError(Exception):
    """A provider said no. `status` is the HTTP status, `code` the
    provider's own error code when it has one."""

    def __init__(self, message, status=None, code=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after = retry_after


class AuthError(ProviderError):
    """401 or 403: the token is wrong, expired, or lacks a scope."""


class RateLimited(ProviderError):
    """429: back off for `retry_after` seconds (None when unknown)."""


class NotFound(ProviderError):
    """404: the machine or app is gone."""


class ProvisionTimeout(ProviderError):
    """The machine never reached `running` inside the wait budget."""


class MachineSpec:
    """What to build. `blob` is the one-blob config
    (`homing-pigeon-install --config-json`), `version` the release
    to pin, `image` the container image for image-based providers."""

    def __init__(self, tenant, region, size, version, blob,
                 profile="hosted", name=None, image=None, labels=None):
        if not isinstance(tenant, str) or not tenant.strip():
            raise ValueError("tenant is required")
        self.tenant = tenant.strip()
        self.region = region
        self.size = size
        self.version = version
        self.blob = dict(blob or {})
        self.profile = profile
        self.name = name or f"hp-{self.tenant}"
        self.image = image
        self.labels = dict(labels or {})
        self.labels.setdefault("homing-pigeon.tenant", self.tenant)
        self.labels.setdefault("homing-pigeon.version", str(version))


class Machine:
    """A provider's machine, normalised. `state` is one of
    created, starting, running, stopped, gone; `raw` is the
    provider's own record for anything the normal fields lack."""

    __slots__ = ("provider", "id", "name", "region", "state", "ip",
                 "tenant", "version", "raw")

    def __init__(self, provider, id, name=None, region=None,
                 state="created", ip=None, tenant=None, version=None,
                 raw=None):
        self.provider = provider
        self.id = str(id)
        self.name = name
        self.region = region
        self.state = state
        self.ip = ip
        self.tenant = tenant
        self.version = version
        self.raw = raw if isinstance(raw, dict) else {}

    def to_record(self):
        return {"provider": self.provider, "id": self.id,
                "name": self.name, "region": self.region,
                "state": self.state, "ip": self.ip,
                "tenant": self.tenant, "version": self.version}

    def __repr__(self):
        return (f"Machine({self.provider}:{self.id} {self.state}"
                f" {self.ip or '-'})")


class Provider:
    """What an adapter does. One machine per call; the one-tenant-per-
    machine rule is the inventory's to enforce, not the adapter's."""

    name = "abstract"

    def create(self, spec: MachineSpec) -> Machine:
        raise NotImplementedError

    def get(self, machine_id: str) -> Machine:
        raise NotImplementedError

    def destroy(self, machine_id: str) -> None:
        raise NotImplementedError

    def wait_running(self, machine_id, timeout=300, interval=5,
                     sleep=time.sleep, clock=time.monotonic) -> Machine:
        """Poll `get` until the machine is running or the budget is
        spent. Shared by every adapter; the clock and sleep are
        injectable so the suite can run it in no time."""
        t0 = clock()
        last = None
        while True:
            last = self.get(machine_id)
            if last.state == "running":
                return last
            if last.state == "gone":
                raise ProviderError(
                    f"{self.name}: machine {machine_id} vanished while "
                    f"starting", code="gone")
            if clock() - t0 >= timeout:
                raise ProvisionTimeout(
                    f"{self.name}: machine {machine_id} still "
                    f"{last.state} after {timeout}s")
            sleep(interval)


def raise_for(resp, provider, what, code=None, message=None):
    """Turn a non-2xx Response into the typed error the status
    means. `code`/`message` are the provider's own, already dug out
    of the body by the adapter."""
    msg = f"{provider}: {what}: HTTP {resp.status}"
    if message:
        msg += f": {message}"
    if resp.status in (401, 403):
        raise AuthError(msg, status=resp.status, code=code)
    if resp.status == 404:
        raise NotFound(msg, status=resp.status, code=code)
    if resp.status == 429:
        retry = resp.header("retry-after")
        try:
            retry = float(retry) if retry is not None else None
        except ValueError:
            retry = None
        raise RateLimited(msg, status=resp.status, code=code,
                          retry_after=retry)
    raise ProviderError(msg, status=resp.status, code=code)
