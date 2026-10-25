"""Queue D, item 2: SECURITY.md and the threat model, claim by claim.

One test per claim that would fail if the claim were false, plus its
negative control. Claims already proven elsewhere are mapped here so
the pass is auditable; only the gaps get new tests in this module.

Mapped (proven in the named module):
- Audit log created 0600 on POSIX, counts file beside it, entries
  carry decision/mode and no secret material: test_linux_audit.
- Audit log rolls to one .1 file at audit_max_lines:
  test_security_config, test_mutated_guards.
- Audit mode proceeds and logs "would_deny"; enforce denies and
  logs "denied"; audit entries carry identifiers only; a malformed
  security block is refused naming the key: test_security_config.
- Confinement enforce refuses to start when the sandbox cannot
  engage, and a mid-run bwrap failure falls back loudly with a
  "fallback" audit decision: test_confinement (Q9 probes).
- job_user identity drop, canary unreadable to the job user, groups
  cleared on initgroups failure: test_secret_files_job_user (Q12/Q18).
- Secret files: inline-plus-file is a startup error, missing or
  empty file is a startup error, same entropy gate:
  test_secret_files_job_user, test_runner_more_edges.
- Unknown key IDs are rejected before any MAC is computed and never
  fall back to the default secret; a key with no policy entry is
  unrestricted unless key_policies_default_deny is set:
  test_multi_secret.
- --dry-run verifies signatures and changes nothing:
  test_protocol_and_edges.
- A same-box producer can still deliver signed sensor_alert
  envelopes through the local inbox with the mailbox gone:
  test_local_signals, test_sense_delivery.
- Threat model: the opinion is advisory (tier-1 findings, the
  model joins only on the oracle_opinion_model opt-in) and the
  judge gates only in enforce: test_oracle_opinion, test_oracle.

The rest of both documents is policy and process (how to report,
what is in scope, the dual-use framing, the appendix's outside
take) -- statements a test cannot falsify, so no test is owed.

Gap proven here first: SECURITY.md says changing a security mode
requires a restart -- "Poll interval, workers, timeouts, output
limits, and max job age reload when config.json changes. The
security block does not." No test pinned the second sentence.
"""
import json
import os
import tempfile
import unittest


class SecurityBlockNoReloadTest(unittest.TestCase):
    """The security block is read at startup and never hot-reloaded."""

    def _write(self, directory, obj):
        path = os.path.join(directory, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_a_mode_change_in_the_file_does_not_reach_the_running_cfg(self):
        from runner.guard.security import sec_mode
        from runner.runner import reload_hot_config

        running_security = {"modes": {"confinement": "off"}}
        cfg = {"poll_interval_sec": 20, "security": running_security}
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, {
                "poll_interval_sec": 5,
                "security": {"modes": {"confinement": "enforce"},
                             "audit_max_lines": 7},
            })
            changed = reload_hot_config(cfg, path, {"mtime": 0})
        # Positive control: the reload really ran -- the hot key moved.
        self.assertEqual(changed, ["poll_interval_sec"])
        self.assertEqual(cfg["poll_interval_sec"], 5)
        # The claim: the security block did not move with it.
        self.assertNotIn("security", changed)
        self.assertIs(cfg["security"], running_security)
        self.assertEqual(sec_mode(cfg, "confinement"), "off")

    def test_the_same_file_read_at_startup_does_enable_the_mode(self):
        # Negative control for the test above: the file is valid and
        # a fresh startup load sees enforce, so the running cfg's
        # "off" is the reload boundary, not a broken file.
        from runner.guard.security import sec_mode
        from runner.runner import load_config

        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, {
                "security": {"modes": {"confinement": "enforce"}},
            })
            fresh = load_config(path)
        self.assertEqual(sec_mode(fresh, "confinement"), "enforce")


if __name__ == "__main__":
    unittest.main()
