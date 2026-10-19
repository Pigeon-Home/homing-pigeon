#!/usr/bin/env python3
"""M7 tests: hardening templates render consistently and stay
out of the default install flow."""
import os
import re
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

HARDENING = os.path.join(REPO, "hardening")
PREFIX = "/tmp/fakeprefix"

# Absolute paths a template may reference outside the rendered
# prefix: system paths the runner genuinely needs (strace-derived).
ALLOWLIST = (
    "/usr", "/lib", "/bin", "/etc/ssl", "/etc/resolv.conf",
    "/etc/hosts", "/etc/nsswitch.conf", "/etc/ld.so.cache",
    "/etc/apparmor.d", "/proc", "/dev", "/tmp",
    "/home",  # referenced only by a deny rule
)


def _render(name):
    path = os.path.join(HARDENING, name)
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    # Drop comment lines: they document, they don't configure.
    lines = [line for line in lines
             if not line.lstrip().startswith(("#", "!"))]
    text = "\n".join(lines)
    return (text
            .replace("@RUNNER_DIR@", PREFIX + "/runner")
            .replace("@BASE_DIR@", PREFIX + "/base")
            .replace("@CONFIG@", PREFIX + "/config.json")
            .replace("@PYTHON@", PREFIX + "/python3")
            .replace("@USER@", "fakepigeon"))


def _absolute_paths(text):
    return re.findall(r"/(?:[\w.\-*]+/)*[\w.\-*]+", text)


class TemplateTest(unittest.TestCase):
    TEMPLATES = (
        "systemd/homing-pigeon.service",
        "apparmor/homing-pigeon",
        "selinux/homing_pigeon.te",
    )

    def test_templates_exist(self):
        for name in self.TEMPLATES:
            self.assertTrue(os.path.exists(os.path.join(HARDENING, name)),
                            name)

    def test_no_unrendered_placeholders(self):
        for name in self.TEMPLATES:
            rendered = _render(name)
            self.assertNotIn("@", rendered, name)

    def test_paths_consistent(self):
        for name in self.TEMPLATES:
            rendered = _render(name)
            for p in _absolute_paths(rendered):
                ok = p.startswith(PREFIX + "/") or p.startswith(ALLOWLIST)
                self.assertTrue(ok, "%s: %s escapes the prefix" % (name, p))

    def test_systemd_has_hardening_directives(self):
        rendered = _render("systemd/homing-pigeon.service")
        for directive in ("NoNewPrivileges=true",
                          "ProtectSystem=strict",
                          "ProtectHome=true",
                          "PrivateTmp=true",
                          "RestrictAddressFamilies="):
            self.assertIn(directive, rendered)

    def test_systemd_mirrors_installer_unit(self):
        # Same shape install.py writes: Description, network-online,
        # ExecStart with --config, Restart=always.
        rendered = _render("systemd/homing-pigeon.service")
        self.assertIn("Description=Homing Pigeon runner agent", rendered)
        self.assertIn("After=network-online.target", rendered)
        self.assertIn("--config %s/config.json" % PREFIX, rendered)
        self.assertIn("Restart=always", rendered)

    def test_selinux_module_name(self):
        with open(os.path.join(HARDENING, "selinux/homing_pigeon.te"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("policy_module(homing_pigeon,", text)

    def test_install_help_mentions_no_templates(self):
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "runner/install.py"),
             "--help"],
            capture_output=True, text=True, timeout=30).stdout.lower()
        for word in ("hardening/", "apparmor", "selinux",
                     "homing_pigeon.te"):
            self.assertNotIn(word, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
