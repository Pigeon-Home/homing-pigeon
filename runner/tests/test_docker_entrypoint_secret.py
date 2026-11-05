# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The docker entrypoint's env-var branch must leave a real secret.

.github/docker/entrypoint.sh builds the config from env vars when no
config file exists and no HP_CONFIG_BLOB was handed over. Its heredoc
used to write "shared_secret" as "" when PIGEON_SHARED_SECRET was
unset, and the runner refuses exactly that config at startup
(runner/wire/verify.py: a shared_secret is required), so the
documented env-var path produced a container that could never start.
The blob branch never had the hole: it delegates to
runner/ops/install.py's ensure_shared_secret, which keeps a provided
secret or generates and persists one. These tests extract the heredoc
from the entrypoint itself and run it the way the entrypoint does,
pinning that the env branch ensures the same.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _heredoc():
    path = os.path.join(_root(), ".github", "docker", "entrypoint.sh")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"<<'PYEOF'\n(.*?)\nPYEOF", text, re.S)
    assert m, "entrypoint.sh no longer carries the env-branch heredoc"
    return m.group(1)


_PROVIDED = "provided-secret-0123456789abcdef-XYZ_0123456789abcdef"


class EntrypointEnvBranchSecretTest(unittest.TestCase):
    def _run(self, extra_env):
        env = {"PATH": os.environ.get("PATH", ""),
               "PIGEON_MAILBOX_USER": "runner@example.test",
               "PIGEON_MAILBOX_PASSWORD": "app-password"}
        env.update(extra_env)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        cfg_path = os.path.join(td.name, "config.json")
        proc = subprocess.run(
            [sys.executable, "-", cfg_path], input=_heredoc(),
            capture_output=True, text=True, env=env, cwd=_root())
        cfg = None
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        return proc, cfg

    def test_absent_env_secret_generates_and_persists_one(self):
        proc, cfg = self._run({})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNotNone(cfg)
        secret = cfg.get("shared_secret")
        self.assertIsInstance(secret, str)
        self.assertNotEqual(secret, "")
        self.assertGreaterEqual(len(secret), 32)

    def test_generated_secrets_differ_between_runs(self):
        _, cfg1 = self._run({})
        _, cfg2 = self._run({})
        self.assertNotEqual(cfg1["shared_secret"], cfg2["shared_secret"])

    def test_provided_secret_is_kept_verbatim(self):
        proc, cfg = self._run({"PIGEON_SHARED_SECRET": _PROVIDED})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(cfg["shared_secret"], _PROVIDED)

    def test_weak_provided_secret_is_refused_at_write_time(self):
        proc, _ = self._run({"PIGEON_SHARED_SECRET": "abc123"})
        self.assertNotEqual(proc.returncode, 0)

    def test_the_rest_of_the_env_config_still_lands(self):
        proc, cfg = self._run({})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(cfg["mailbox_user"], "runner@example.test")
        self.assertEqual(cfg["mailbox_password"], "app-password")
        self.assertEqual(cfg["imap_host"], "imap.gmail.com")
        self.assertEqual(cfg["base_dir"], "/data/work")


if __name__ == "__main__":
    unittest.main()
