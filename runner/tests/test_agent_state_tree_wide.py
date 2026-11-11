# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The general tree-wide value-confinement test for agent state.

privacy-design.md section 6 item 4 queues the boundary-test
technique generalised: a test that proves named sensitive values
appear only in allowlisted files. The staged guard
(runner/tools/approvalguard.py) is that test's first concrete
form, at the commit boundary. This family is the general form:
the guard's agent-state rules -- its path rules, grant state
under every name, tool-server env/headers secrets, the other
version-control systems' credential shapes, secret-shaped values
in structured documents, and known key formats anywhere -- are
applied to the whole tracked tree, and a finding is a failure
unless the file stands on the allowlist below with the rule
named and the reason recorded.

One scope line is the guard's own design, read tree-wide:
secret-in-command is a rule about command strings, and command
strings are data inside structured documents (JSON, TOML, YAML).
Source code and prose handle credentials as variables by trade;
a raw line scan over a whole tree fires on that ordinary work
(measured in the desk record for this lane: 223 files under the
staged scan's raw form, against the structured form's handful,
each one a fixture, a specimen or a declared fake). The tree-wide
scan therefore reads secret-in-command only where the guard's
designed context holds, and reads every other agent-state rule
over every tracked file.

The allowlist is pinned both ways, like the skip registry: an
allowlisted (file, rule) pair that no longer fires fails here
too, so the list cannot rot into a blanket exemption.

Every secret-shaped string in this file is fake, minted for
these tests. A real one never lives in the repository.
"""
import json
import os
import shutil
import string
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import approvalguard as AG  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
REG = AG.default_registry()
BOOKENDS = string.punctuation + "\x00\t\r\n"
FAKE_PASSWORD = "fake-tree-password-9c2e"

_EXAMPLE_KEY = ("the canonical published example key id, "
                "carried as a specimen or fixture")
ALLOWLIST = {
    ("AGENTS.md", AG.RULE_SECRET_VALUE):
        "a hyphenated heading anchor (the task-board and "
        "key-ids section) matches the sk- key format's shape; "
        "it is an English phrase, not a key",
    ("docs/steady/security/security-test-plan.md",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("docs/steady/use/live-examples.md",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/airgap/interesting.example/OVERVIEW.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_approvalguard.py",
     AG.RULE_SECRET_VALUE):
        "the guard family's own minted fake key id, in its "
        "fixtures",
    ("runner/tests/test_approvalguard_extensions.py",
     AG.RULE_SECRET_VALUE):
        "the extensions family's own minted fake key id, in "
        "its fixtures",
    ("runner/tests/test_campaign_canary.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_flag321.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_followups.py",
     AG.RULE_SECRET_VALUE):
        _EXAMPLE_KEY + "; the same file names the private-key "
        "header marker as a test subject",
    ("runner/tests/test_live_capture.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_negative_concurrency.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_notable_access.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_oracle.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_proof_conformance_p2.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_protocol_and_edges.py",
     AG.RULE_SECRET_VALUE): _EXAMPLE_KEY,
    ("runner/tests/test_v31_verify.py",
     AG.RULE_SECRET_VALUE):
        "a minted fake key id and the private-key header "
        "marker, both named as test subjects",
    ("runner/tools/soak.py", AG.RULE_SECRET_VALUE):
        _EXAMPLE_KEY,
    (".github/workflows/build.yml",
     AG.RULE_SECRET_IN_COMMAND):
        "a CI fixture config literal in the workflow's steps: "
        "its password is declared not-a-real in the file, and "
        "its shared secret is a synthetic patterned test value "
        "for throwaway rigs",
    (".github/workflows/docker.yml",
     AG.RULE_SECRET_IN_COMMAND):
        "the same CI fixture config literal as build.yml",
}


def _rules(path, content):
    return {f.rule for f in AG.scan_tree_content(path, content, REG)}


class FixtureTreeTest(unittest.TestCase):
    """Both ways, on fixture (path, content) pairs: the guard's
    shapes planted in a tree fire; the same tree without them
    is silent."""

    def test_planted_agent_state_path_fires(self):
        self.assertIn("agent-config-path", _rules(
            ".claude/settings.local.json", b"{}\n"))
        self.assertIn("deployment-state-path", _rules(
            "deploy/config.json", b"{}\n"))

    def test_planted_grant_with_a_secret_fires_both_rules(self):
        doc = {"permissions": {"allow": [
            "Bash(psql postgresql://svc:%s@db.invalid/app)"
            % FAKE_PASSWORD]}}
        rules = _rules("notes.json", json.dumps(doc).encode())
        self.assertIn(AG.RULE_GRANT_STATE, rules)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)

    def test_planted_tool_server_secret_fires(self):
        doc = {"mcpServers": {"db": {
            "env": {"DB_PASSWORD": FAKE_PASSWORD}}}}
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET, _rules(
            "team/mcp.json", json.dumps(doc).encode()))

    def test_planted_vcs_credential_fires(self):
        content = ("\n".join(
            ["[auth]", "bb.password = %s" % FAKE_PASSWORD])
            + "\n").encode()
        self.assertIn(AG.RULE_VCS_CREDENTIAL,
                      _rules("home/.hgrc", content))

    def test_bookended_planted_shapes_fire(self):
        doc = {"allowlist": [
            BOOKENDS + "run it password=%s" % FAKE_PASSWORD
            + BOOKENDS]}
        rules = _rules("notes.json", json.dumps(doc).encode())
        self.assertIn(AG.RULE_GRANT_STATE, rules)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)
        content = ("\n".join(
            ["[auth]", "bb.password = " + BOOKENDS
             + FAKE_PASSWORD + BOOKENDS]) + "\n").encode()
        self.assertIn(AG.RULE_VCS_CREDENTIAL,
                      _rules("home/.hgrc", content))

    def test_clean_fixture_tree_is_silent(self):
        entries = [
            ("src/app.py", b"print('hello')\n"),
            ("notes.json", b'{"theme": "dark"}\n'),
            ("team/mcp.json",
             b'{"mcpServers": {"db": {"env": '
             b'{"MODE": "production"}}}}\n'),
            ("README.md", b"# a project\n"),
        ]
        for path, content in entries:
            self.assertEqual(set(), _rules(path, content), path)

    def test_secret_in_command_context_line(self):
        # The tree-wide scope line, pinned: a password assignment
        # as a line of source code is the staged scan's business
        # and not the tree-wide scan's; the same value as a JSON
        # string is both scans' business.
        line = ("password=%s\n" % FAKE_PASSWORD).encode()
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, {
            f.rule for f in AG.scan_content("src/app.py", line, REG)})
        self.assertNotIn(AG.RULE_SECRET_IN_COMMAND,
                         _rules("src/app.py", line))
        doc = json.dumps({"cmd": "run password=%s"
                          % FAKE_PASSWORD}).encode()
        self.assertIn(AG.RULE_SECRET_IN_COMMAND,
                      _rules("notes.json", doc))


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class WholeTreeTest(unittest.TestCase):
    def test_the_tracked_tree_carries_no_unlisted_agent_state(self):
        findings = AG.scan_tree(REPO, REG)
        found = {(f.path, f.rule) for f in findings}
        offenders = found - set(ALLOWLIST)
        self.assertEqual(offenders, set(),
                         "tree-wide findings not on the allowlist")
        stale = set(ALLOWLIST) - found
        self.assertEqual(stale, set(),
                         "allowlisted pairs that no longer fire; "
                         "the list may not rot")

    def test_every_allowlist_reason_is_recorded(self):
        for pair, reason in ALLOWLIST.items():
            self.assertIsInstance(pair[0], str)
            self.assertTrue(pair[0])
            self.assertTrue(reason.strip(), pair)


if __name__ == "__main__":
    unittest.main()
