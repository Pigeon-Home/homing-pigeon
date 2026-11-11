# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""runner/tools/approvalguard.py: the agent-state guard's extensions.

The shipped guard (test_approvalguard.py) scans staged content for
agent-config paths, deployment state paths, ``allow`` grant state
and secret-shaped values inside command strings. The extensions
recorded as specified in docs/steady/security/agent-state-files.md
section 4 -- and queued in privacy-design.md sections 6 and 8 --
are pinned here:

- tool-server configuration as a category of its own: a staged
  file named ``mcp.json`` and any staged JSON carrying the
  ``mcpServers`` top-level key get their ``env`` and ``headers``
  maps scanned, wherever the file sits, including files designed
  to be committed -- the trigger is not itself a finding;
- grant state under its other names (``autoApprove``,
  ``allowedTools``, ``terminalAllowlist``, ``allowlist``, a
  ``permission`` map), entries scanned as command strings;
- the same content shapes in TOML and YAML;
- staged areas beyond git's: a Subversion working copy's
  scheduled additions fed to the same scan as the same
  (path, content) pairs, plus content rules for a Mercurial
  ``[auth]`` password line and a Subversion proxy password.

Every secret-shaped string in this file is fake, minted for these
tests. A real one never lives in the repository.
"""
import contextlib
import io
import json
import os
import string
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import approvalguard as AG  # noqa: E402

FAKE_PASSWORD = "fake-db-password-7f3a"
FAKE_KEY_ID = "AKIAFAKEFAKEFAKE1234"
BOOKENDS = string.punctuation + "\x00\t\r\n"
REG = AG.default_registry()


def _rules(path, content, tree_wide=False):
    scan = AG.scan_tree_content if tree_wide else AG.scan_content
    return [f.rule for f in scan(path, content, REG)]


def _mcp_doc(env=None, headers=None, top="mcpServers"):
    server = {}
    if env is not None:
        server["env"] = env
    if headers is not None:
        server["headers"] = headers
    return json.dumps({top: {"db": server}}).encode()


class ToolServerTest(unittest.TestCase):
    def test_mcp_filename_triggers_the_scan_at_any_depth(self):
        content = _mcp_doc(env={"DB_PASSWORD": FAKE_PASSWORD})
        for path in ("mcp.json", ".cursor/mcp.json",
                     ".cline/mcp.json", ".roo/mcp.json",
                     ".kiro/settings/mcp.json",
                     ".vscode/mcp.json"):
            self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                          _rules(path, content), path)

    def test_top_level_key_triggers_in_an_arbitrary_file(self):
        content = _mcp_doc(headers={"X-Api-Key": "fake-header-1234"})
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules("shared/team-settings.json", content))

    def test_vscode_servers_key_reached_through_the_filename(self):
        content = _mcp_doc(env={"DB_PASSWORD": FAKE_PASSWORD},
                           top="servers")
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules(".vscode/mcp.json", content))

    def test_key_format_value_under_a_plain_key_fires(self):
        content = _mcp_doc(env={"PLAIN": FAKE_KEY_ID})
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules("mcp.json", content))

    def test_command_shaped_value_in_a_header_fires(self):
        content = _mcp_doc(headers={
            "Authorization": "Bearer token=fake-token-1234"})
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules("mcp.json", content))

    def test_placeholders_and_plain_values_stay_silent(self):
        content = _mcp_doc(
            env={"DB_PASSWORD": "${DB_PASSWORD}",
                 "API_TOKEN": "${env:API_TOKEN}",
                 "MODE": "production"},
            headers={"Authorization": "<your-token>"})
        self.assertEqual([], _rules("mcp.json", content))

    def test_the_trigger_alone_is_not_a_finding(self):
        content = _mcp_doc(env={"MODE": "production"})
        self.assertEqual([], _rules("mcp.json", content))
        self.assertEqual([], _rules(
            "notes.json", b'{"mcpServers": {}}'))

    def test_env_map_outside_a_tool_server_context_is_silent(self):
        content = json.dumps(
            {"env": {"DB_PASSWORD": FAKE_PASSWORD}}).encode()
        self.assertNotIn(AG.RULE_TOOL_SERVER_SECRET,
                         _rules("app.json", content))

    def test_bookended_secret_in_an_env_map_fires(self):
        content = _mcp_doc(env={
            "DB_PASSWORD": BOOKENDS + FAKE_PASSWORD + BOOKENDS})
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules("mcp.json", content))

    def test_report_names_file_and_rule_never_the_value(self):
        repo_files = [("mcp.json",
                       _mcp_doc(env={"DB_PASSWORD": FAKE_PASSWORD}))]
        findings = AG.scan_entries(repo_files, REG)
        out = io.StringIO()
        AG._report(findings, False, out)
        text = out.getvalue()
        self.assertIn("mcp.json", text)
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET, text)
        self.assertNotIn(FAKE_PASSWORD, text)


class GrantNamesTest(unittest.TestCase):
    def test_each_other_name_fires(self):
        cases = [
            {"autoApprove": ["tool_a"]},
            {"autoApprove": [True, False]},
            {"allowedTools": ["Bash(npm test)"]},
            {"terminalAllowlist": ["ls -la"]},
            {"allowlist": ["tool_a"]},
            {"permission": {"bash": "allow"}},
            {"permission": ["bash"]},
            {"permission": "bash"},
        ]
        for doc in cases:
            rules = _rules("settings.json", json.dumps(doc).encode())
            self.assertIn(AG.RULE_GRANT_STATE, rules, doc)

    def test_empty_and_absent_forms_stay_silent(self):
        for doc in ({"autoApprove": []}, {"allowedTools": []},
                    {"terminalAllowlist": []}, {"allowlist": []},
                    {"permission": {}}, {"permission": []},
                    {"permission": ""}, {"theme": "dark"}):
            rules = _rules("settings.json", json.dumps(doc).encode())
            self.assertNotIn(AG.RULE_GRANT_STATE, rules, doc)

    def test_secret_inside_an_entry_fires_both_rules(self):
        doc = {"allowedTools": [
            "Bash(psql postgresql://svc:%s@db.invalid/app)"
            % FAKE_PASSWORD]}
        rules = _rules("settings.json", json.dumps(doc).encode())
        self.assertIn(AG.RULE_GRANT_STATE, rules)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)

    def test_nested_grant_state_fires(self):
        doc = {"outer": {"inner": {"autoApprove": ["tool_a"]}}}
        self.assertIn(AG.RULE_GRANT_STATE,
                      _rules("settings.json", json.dumps(doc).encode()))

    def test_bookended_entry_with_a_secret_fires_both_rules(self):
        entry = BOOKENDS + "run it password=%s" % FAKE_PASSWORD \
            + BOOKENDS
        doc = {"terminalAllowlist": [entry]}
        rules = _rules("settings.json", json.dumps(doc).encode())
        self.assertIn(AG.RULE_GRANT_STATE, rules)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)


class TomlYamlTest(unittest.TestCase):
    def test_toml_grant_key_fires(self):
        content = b'allowedTools = ["Bash(npm test)"]\n'
        self.assertIn(AG.RULE_GRANT_STATE,
                      _rules(".codex/config.toml", content))

    def test_toml_named_secret_fires(self):
        content = b'apiKey = "fake-provider-key-1234"\n'
        self.assertIn(AG.RULE_SECRET_IN_COMMAND,
                      _rules("config.toml", content))

    def test_toml_tool_server_env_fires(self):
        content = ("[mcpServers.db.env]\nDB_PASSWORD = \"%s\"\n"
                   % FAKE_PASSWORD).encode()
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules("servers.toml", content))

    def test_toml_placeholder_and_plain_stay_silent(self):
        content = b'apiKey = "${PROVIDER_KEY}"\nname = "x"\n'
        self.assertEqual([], _rules("config.toml", content))

    def test_yaml_grant_list_fires(self):
        content = ("permissions:\n  autoApprove:\n"
                   "    - tool_a\n").encode()
        self.assertIn(AG.RULE_GRANT_STATE,
                      _rules("blocks.yaml", content))

    def test_yaml_named_secret_fires(self):
        content = b"model:\n  apiKey: fake-provider-key-1234\n"
        self.assertIn(AG.RULE_SECRET_IN_COMMAND,
                      _rules("model.yaml", content))

    def test_yaml_tool_server_env_fires(self):
        content = ("mcpServers:\n  db:\n    env:\n"
                   "      DB_PASSWORD: %s\n" % FAKE_PASSWORD).encode()
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET,
                      _rules("servers.yaml", content))

    def test_yaml_workflow_shape_stays_silent(self):
        content = ("name: ci\non:\n  push:\n"
                   "    branches: [main]\npermissions:\n"
                   "  id-token: write\n").encode()
        self.assertEqual([], _rules("ci.yml", content))

    def test_yaml_placeholder_stays_silent(self):
        content = b"model:\n  apiKey: ${PROVIDER_KEY}\n"
        self.assertEqual([], _rules("model.yaml", content))

    def test_block_scalar_document_falls_back_to_the_line_scan(self):
        # A block scalar is outside the YAML subset: the document
        # is read by the line scan instead, and a grant key and a
        # named secret inside it still fire.
        content = ("config: |\n  allowedTools = [\"Bash(x)\"]\n"
                   "  shared_secret = \"fake-shared-1234\"\n"
                   ).encode()
        rules = _rules("flow.yaml", content)
        self.assertIn(AG.RULE_GRANT_STATE, rules)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)


class VcsCredentialTest(unittest.TestCase):
    def _text(self, *lines):
        return ("\n".join(lines) + "\n").encode()

    def test_mercurial_auth_password_fires(self):
        content = self._text("[auth]", "bb.password = fake-hg-pass")
        self.assertIn(AG.RULE_VCS_CREDENTIAL,
                      _rules(".hgrc", content))

    def test_mercurial_bare_password_key_under_auth_fires(self):
        content = self._text("[auth]", "password = fake-hg-pass")
        self.assertIn(AG.RULE_VCS_CREDENTIAL,
                      _rules("hgrc", content))

    def test_mercurial_password_outside_auth_is_not_a_vcs_hit(self):
        content = self._text("[ui]", "password = fake-hg-pass")
        self.assertNotIn(AG.RULE_VCS_CREDENTIAL,
                         _rules(".hgrc", content))

    def test_mercurial_section_after_auth_ends_the_shape(self):
        content = self._text("[auth]", "bb.prefix = https://x",
                             "[ui]", "password = fake-hg-pass")
        self.assertNotIn(AG.RULE_VCS_CREDENTIAL,
                         _rules(".hgrc", content))

    def test_mercurial_empty_and_placeholder_stay_silent(self):
        for line in ("bb.password =", "bb.password = ${HG_PASS}"):
            content = self._text("[auth]", line)
            self.assertNotIn(AG.RULE_VCS_CREDENTIAL,
                             _rules(".hgrc", content), line)

    def test_subversion_proxy_password_fires(self):
        content = self._text("[global]",
                             "http-proxy-password = fake-proxy-pw")
        self.assertIn(AG.RULE_VCS_CREDENTIAL,
                      _rules("servers", content))

    def test_subversion_proxy_empty_stays_silent(self):
        content = self._text("http-proxy-password =")
        self.assertNotIn(AG.RULE_VCS_CREDENTIAL,
                         _rules("servers", content))

    def test_bookended_vcs_values_fire(self):
        content = self._text(
            "[auth]", "bb.password = " + BOOKENDS + "fake-hg-pass"
            + BOOKENDS)
        self.assertIn(AG.RULE_VCS_CREDENTIAL,
                      _rules(".hgrc", content))

    def test_report_never_carries_the_vcs_value(self):
        content = self._text("[auth]", "bb.password = fake-hg-pass")
        findings = AG.scan_content(".hgrc", content, REG)
        out = io.StringIO()
        AG._report(findings, False, out)
        self.assertNotIn("fake-hg-pass", out.getvalue())
        self.assertIn(AG.RULE_VCS_CREDENTIAL, out.getvalue())


STATUS_TEXT = (
    "A       new/mcp.json\n"
    "M       changed.py\n"
    "?       unversioned.py\n"
    "!       missing.py\n"
    "A       dir/file with space.json\n"
    "A  +    moved.py\n"
)


class SvnDoorTest(unittest.TestCase):
    def test_status_reader_feeds_exactly_the_additions(self):
        seen = []

        def reader(path):
            seen.append(path)
            return path.encode()

        entries = AG.svn_scheduled_entries(STATUS_TEXT, reader)
        self.assertEqual([p for p, _ in entries],
                         ["new/mcp.json", "dir/file with space.json",
                          "moved.py"])
        self.assertEqual(seen, [p for p, _ in entries])

    def test_the_same_scan_answers_for_svn_pairs(self):
        files = {"new/mcp.json": _mcp_doc(
            env={"DB_PASSWORD": FAKE_PASSWORD}),
            "clean.py": b"print('ok')\n"}
        entries = AG.svn_scheduled_entries(
            "A       new/mcp.json\nA       clean.py\n",
            files.__getitem__)
        rules = [f.rule for f in AG.scan_entries(entries, REG)]
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET, rules)

    def test_svn_entries_reads_a_working_copy_via_status(self):
        wc = tempfile.mkdtemp(prefix="approvalguard-svn-")
        path = os.path.join(wc, "added.json")
        with open(path, "wb") as fh:
            fh.write(b'{"theme": "dark"}\n')
        done = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=b"A       added.json\nM       other.py\n")
        with mock.patch.object(AG.subprocess, "run",
                               return_value=done):
            entries = AG.svn_entries(wc)
        self.assertEqual(entries,
                         [("added.json", b'{"theme": "dark"}\n')])

    def test_missing_svn_is_a_guard_error_not_a_pass(self):
        with mock.patch.object(
                AG.subprocess, "run",
                side_effect=FileNotFoundError("svn")):
            with self.assertRaises(AG.GuardError):
                AG.svn_entries(".")

    def test_check_svn_cli_reports_and_stops(self):
        wc = tempfile.mkdtemp(prefix="approvalguard-svn-cli-")
        with open(os.path.join(wc, "mcp.json"), "wb") as fh:
            fh.write(_mcp_doc(env={"DB_PASSWORD": FAKE_PASSWORD}))
        done = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"A       mcp.json\n")
        out = io.StringIO()
        with mock.patch.object(AG.subprocess, "run",
                               return_value=done), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = AG.main(["check-svn", "--wc", wc])
        self.assertEqual(rc, 1)
        self.assertIn(AG.RULE_TOOL_SERVER_SECRET, out.getvalue())
        self.assertNotIn(FAKE_PASSWORD, out.getvalue())


if __name__ == "__main__":
    unittest.main()
