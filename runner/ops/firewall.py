"""Platform firewall posture.

Extracted from runner.py.
"""
import re
import shutil
import subprocess
import sys


def _runner():
    """The live runner module, looked up at call time (`runner.runner`
    under the suite, `__main__` when runner.py runs as a script or
    frozen, where `from runner import runner` cannot work)."""
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "_load_mod", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R


def _firewall_posture():
    """One line: is the host firewall on. None if it cannot be read.

    Not a packet capture and not a ruleset dump. Windows uses netsh
    profile state. Linux prefers ufw status, else the iptables policy
    lines only. macOS uses the Application Firewall state and does not
    call pfctl. Never raises.
    """
    if _runner().sys.platform == "win32":
        return _runner()._parse_netsh_profiles(_runner()._run_text(
            ["netsh", "advfirewall", "show", "allprofiles"]))
    if _runner().sys.platform == "darwin":
        return _runner()._parse_socketfilterfw(_runner()._run_text([
            "/usr/libexec/ApplicationFirewall/socketfilterfw",
            "--getglobalstate"]))
    if shutil.which("ufw"):
        parsed = _runner()._parse_ufw(_runner()._run_text(["ufw", "status"]))
        if parsed:
            return parsed
    if shutil.which("iptables"):
        return _runner()._parse_iptables_policy(
            _runner()._run_text(["iptables", "-S"], timeout=3))
    return None


def _parse_netsh_profiles(text):
    """'firewall: windows Domain=ON ...' from netsh, or None."""
    if not isinstance(text, str) or not text.strip():
        return None
    profiles = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.endswith("Profile Settings:"):
            current = line[: -len("Profile Settings:")].strip()
            continue
        if current and line.lower().startswith("state"):
            state = line.split()[-1].upper() if line.split() else ""
            if state in ("ON", "OFF"):
                profiles.append((current, state))
            current = None
    if not profiles:
        return None
    bits = [name + "=" + state for name, state in profiles]
    line = "firewall: windows " + " ".join(bits)
    if any(state == "OFF" for _name, state in profiles):
        line += " [T1562.004]"
    return line


def _parse_socketfilterfw(text):
    if not isinstance(text, str):
        return None
    low = text.lower()
    # "disabled" contains the letters "enabled", and "state = 10"
    # contains "state = 1". Match the words, not the substrings.
    if re.search(r"\bdisabled\b", low) or re.search(r"state\s*=\s*0\b", low):
        return "firewall: macos application-firewall=off [T1562.004]"
    if re.search(r"\benabled\b", low) or re.search(r"state\s*=\s*1\b", low):
        return "firewall: macos application-firewall=on"
    return None


def _parse_ufw(text):
    if not isinstance(text, str):
        return None
    low = text.lower()
    if "status: active" in low:
        return "firewall: linux ufw=active"
    if "status: inactive" in low:
        return "firewall: linux ufw=inactive [T1562.004]"
    return None


def _parse_iptables_policy(text):
    """Policy lines only. A full ruleset is not the posture."""
    if not isinstance(text, str) or not text.strip():
        return None
    policies = []
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) >= 3 and parts[0] == "-P":
            policies.append((parts[1], parts[2]))
    if not policies:
        return None
    bits = [chain + "=" + policy for chain, policy in policies]
    line = "firewall: linux iptables " + " ".join(bits)
    protected = any(
        policy in ("DROP", "REJECT") and chain in ("INPUT", "FORWARD")
        for chain, policy in policies)
    if not protected:
        line += " [T1562.004]"
    return line


