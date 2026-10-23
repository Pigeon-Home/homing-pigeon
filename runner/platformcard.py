"""The platform card: what a box says about itself, at the tier its
owner chose.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

A remote sender rarely knows the box: the OS family, the default
interpreter, which protocol versions the runner speaks. Guessing
wrong costs a round trip and a rejection (a job naming ["sh"] at a
Windows runner). The card answers that before the first real job.
It rides in two places, built here so they agree:

- the `platform` member of the result to a `ping` job, tiered by
  the owner's `pong_platform` (PROTOCOL.md 3.2);
- the DTLS session's greeting, tiered by `dtls_greeting`
  (draft-homing-pigeon-00 Section 20).

Tiers, from least to most:

    none      no card at all
    family    os_family, default_interpreter, protocol_versions
    standard  + os_release, python_version, runner_version
    full      + path_tools (which of a fixed list are on PATH)

The default is `family` in both places: enough to pick an
interpreter and a protocol version, nothing a port scan would not
tell. Disclosure happens only in an authenticated reply -- a pong
answers a verified job, a greeting follows the handshake -- so an
unauthenticated peer harvests nothing.

Stdlib only; no runner imports, so the DTLS program and the core
can both load it.
"""
import os
import platform
import shutil
import sys

TIERS = ("none", "family", "standard", "full")
DEFAULT_TIER = "family"
PATH_TOOLS = ("sh", "bash", "powershell", "pwsh", "python3",
              "python", "curl", "git", "tar")


def os_family() -> str:
    p = sys.platform
    if p.startswith("win"):
        return "windows"
    if p == "darwin":
        return "macos"
    if p.startswith("linux"):
        return "linux"
    return "other"


def platform_interpreter() -> list:
    """The interpreter a job without one runs under on this OS."""
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File"]
    return ["sh"]


def tier_of(cfg, key, default=DEFAULT_TIER):
    """The configured tier under `key`, or (None, problem) when the
    value is not a tier. Returns (tier, None) otherwise."""
    raw = cfg.get(key, default) if isinstance(cfg, dict) else default
    if raw is None:
        return default, None
    if not isinstance(raw, str) or raw not in TIERS:
        return None, (f"{key} must be one of {list(TIERS)}, "
                      f"not {raw!r}")
    return raw, None


def build_card(tier, cfg=None, protocol_versions=None,
               runner_version=None) -> dict:
    """The card for a tier, or None at `none`.

    `cfg` supplies `default_interpreter` when the owner set one;
    `protocol_versions` is the list the runner speaks (the caller
    knows whether version 2 is on); `runner_version` is the
    release number, shown from `standard` up.
    """
    if tier == "none" or tier not in TIERS:
        return None
    cfg = cfg if isinstance(cfg, dict) else {}
    interp = cfg.get("default_interpreter")
    if not (isinstance(interp, list) and interp
            and all(isinstance(x, str) for x in interp)):
        interp = platform_interpreter()
    versions = [v for v in (protocol_versions or [1])
                if isinstance(v, int) and not isinstance(v, bool)]
    card = {
        "disclosure": tier,
        "os_family": os_family(),
        "default_interpreter": list(interp),
        "protocol_versions": sorted(set(versions)) or [1],
    }
    if tier in ("standard", "full"):
        card["os_release"] = platform.release()
        card["python_version"] = platform.python_version()
        if isinstance(runner_version, str) and runner_version:
            card["runner_version"] = runner_version
    if tier == "full":
        card["path_tools"] = {name: bool(shutil.which(name))
                              for name in PATH_TOOLS}
    return card
