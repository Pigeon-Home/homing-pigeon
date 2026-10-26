# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""What a fresh machine runs to become a runner.

Two shapes, one meaning: a cloud-init `user_data` script for plain
VMs (Hetzner, DigitalOcean, any image that runs cloud-init) and an
environment block for image-based machines (Fly, a container). Both
install the pinned release, write the one-blob config, apply the
hosted profile and start the service. The blob is the only secret
that moves; nothing here embeds a provider token.
"""
from __future__ import annotations

import json
import shlex

PACKAGE = "pigeon-home-runner"
DEFAULT_IMAGE = "ghcr.io/pigeon-home/homing-pigeon"
BLOB_ENV = "HP_CONFIG_BLOB"


def pinned_requirement(version):
    if not isinstance(version, str) or not version.strip():
        raise ValueError("a release version is required")
    v = version.strip().lstrip("v")
    if not all(part.isdigit() for part in v.split(".")) or v.count(".") != 2:
        raise ValueError(f"not a release version: {version!r}")
    return f"{PACKAGE}=={v}"


def image_for(version, image=None):
    base = image or DEFAULT_IMAGE
    v = str(version).strip().lstrip("v")
    return base if ":" in base.rsplit("/", 1)[-1] else f"{base}:{v}"


def user_data(spec):
    """A cloud-init script: pip install the pinned wheel, write the
    blob to a root-only file, run the installer non-interactively
    with the hosted profile, no inference. Idempotent on re-run."""
    req = pinned_requirement(spec.version)
    blob = json.dumps(spec.blob, sort_keys=True)
    profile = spec.profile or "hosted"
    lines = [
        "#!/bin/sh",
        "# homing-pigeon hosted bootstrap -- written by the provisioner",
        "set -eu",
        "umask 077",
        "mkdir -p /etc/homing-pigeon",
        f"printf '%s' {shlex.quote(blob)} > /etc/homing-pigeon/blob.json",
        "if command -v apt-get >/dev/null 2>&1; then",
        "  export DEBIAN_FRONTEND=noninteractive",
        "  apt-get update -qq && apt-get install -y -qq python3 python3-pip bubblewrap",
        "elif command -v dnf >/dev/null 2>&1; then",
        "  dnf install -y -q python3 python3-pip bubblewrap",
        "elif command -v apk >/dev/null 2>&1; then",
        "  apk add --no-cache python3 py3-pip bubblewrap",
        "fi",
        f"python3 -m pip install --quiet --break-system-packages {shlex.quote(req)}"
        f" || python3 -m pip install --quiet {shlex.quote(req)}",
        "homing-pigeon-install --system --no-inference"
        f" --profile {shlex.quote(profile)}"
        " --config-json @/etc/homing-pigeon/blob.json",
        "",
    ]
    return "\n".join(lines)


def container_env(spec):
    """The environment an image-based machine starts with. The
    image's entrypoint runs the same installer against BLOB_ENV."""
    return {
        BLOB_ENV: json.dumps(spec.blob, sort_keys=True),
        "HP_PROFILE": spec.profile or "hosted",
        "HP_VERSION": str(spec.version).lstrip("v"),
    }


def ephemeral_command(spec, drain_jobs=1, drain_seconds=900):
    """What an ephemeral VM (a GitHub Actions job, a per-job box)
    runs: install, configure, drain, exit. Returns argv lists."""
    req = pinned_requirement(spec.version)
    blob = json.dumps(spec.blob, sort_keys=True)
    return [
        ["python3", "-m", "pip", "install", "--quiet", req],
        ["homing-pigeon-install", "--no-inference", "--profile",
         spec.profile or "hosted", "--config-json", blob],
        ["homing-pigeon", "--once", "--drain", str(int(drain_jobs)),
         "--drain-seconds", str(int(drain_seconds))],
    ]
