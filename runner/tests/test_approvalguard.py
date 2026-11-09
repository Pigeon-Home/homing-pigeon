# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""runner/tools/approvalguard.py: staged agent-state, kept off the public shelf.

The approval guard is the boundary test for agent permission/config
state (docs/steady/security/privacy-design.md): it scans staged
content and fails closed on agent-config paths, deployment state
paths, permission-grant state, and secret-shaped values inside
command strings -- the class generic scanners missed when an
agent's "don't ask again" file reached public repositories with
real credentials inside approved commands.

These tests hold: the registry format shut (every malformed shape
refused, by name); the declared path rules; the grant-state and
secret-shape content rules; split existence from value (a report
names the file and the rule, and provably never the secret); the
git front door end to end (a clean staged tree passes, a staged
settings.local.json fails); and the security-modes gate in the
privacy family's semantics -- off refuses, audit shows and stops
nothing, enforce stops, a misspelled mode is refused.

Every secret-shaped string in this file is fake, minted for these
tests. A real one never lives in the repository.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.guard import security as S  # noqa: E402
from runner.tools import approvalguard as AG  # noqa: E402

FAKE_DB_PASSWORD = "fake-db-password-7f3a"
FAKE_COMMAND = ("Bash(psql postgresql://svc:%s@db.invalid:5432/app)"
                % FAKE_DB_PASSWORD)
FAKE_AWS_KEY = "AKIAFAKEFAKEFAKE1234"


def _registry(*entries, **top):
    data = {"format": AG.REGISTRY_FORMAT, "version": 1,
            "rules": list(entries)}
    data.update(top)
    return AG.parse_registry(data)


def _rule(rule_id, kind, value, **kw):
    entry = {"id": rule_id, "kind": kind, "value": value}
    entry.update(kw)
    return entry


def _settings_local(command=FAKE_COMMAND):
    return json.dumps({"permissions": {"allow": [command]}}).encode()


class RegistryFormatTest(unittest.TestCase):
    def test_default_registry_parses_and_names_the_incident_shapes(self):
        reg = AG.default_registry()
        ids = {(r.id, r.value) for r in reg.rules}
        self.assertIn(("agent-config-path",
                       ".claude/settings.local.json"), ids)
        self.assertIn(("agent-config-path",
                       ".claude/settings.json"), ids)
        self.assertIn(("deployment-state-path", "config.json"), ids)
        self.assertIn(("deployment-state-path", "oracle-chat.jsonl"),
                      ids)

    def test_minimal_registry_parses(self):
        reg = _registry()
        self.assertEqual(reg.rules, ())

    def test_wrong_format_and_version_refused(self):
        with self.assertRaises(AG.RegistryError):
            AG.parse_registry({"format": "other", "version": 1,
                               "rules": []})
        with self.assertRaises(AG.RegistryError):
            AG.parse_registry({"format": AG.REGISTRY_FORMAT,
                               "version": 2, "rules": []})
        with self.assertRaises(AG.RegistryError):
            AG.parse_registry({"format": AG.REGISTRY_FORMAT,
                               "version": True, "rules": []})

    def test_unknown_keys_refused_at_both_levels(self):
        with self.assertRaises(AG.RegistryError):
            _registry(bogus=1)
        with self.assertRaises(AG.RegistryError):
            _registry(_rule("x", "basename", "a.json", bogus=1))

    def test_bad_kind_and_value_shapes_refused(self):
        with self.assertRaises(AG.RegistryError):
            _registry(_rule("x", "glob", "a.json"))
        with self.assertRaises(AG.RegistryError):
            _registry(_rule("x", "basename-under", "noslash.json"))
        with self.assertRaises(AG.RegistryError):
            _registry(_rule("x", "basename", "dir/a.json"))
        with self.assertRaises(AG.RegistryError):
            _registry(_rule("x", "basename", ""))

    def test_duplicate_rule_refused(self):
        with self.assertRaises(AG.RegistryError):
            _registry(_rule("x", "basename", "a.json"),
                      _rule("x", "basename", "a.json"))


class PathRuleTest(unittest.TestCase):
    def setUp(self):
        self.reg = AG.default_registry()

    def _rules(self, path, content=b"hello\n"):
        return [f.rule for f in AG.scan_content(path, content,
                                                self.reg)]

    def test_agent_config_paths_trip_at_any_depth(self):
        self.assertIn("agent-config-path",
                      self._rules(".claude/settings.local.json"))
        self.assertIn("agent-config-path",
                      self._rules("sub/.claude/settings.json"))

    def test_settings_json_outside_claude_is_clean(self):
        self.assertNotIn("agent-config-path",
                         self._rules("docs/settings.json"))

    def test_deployment_state_basenames_trip(self):
        for name in ("config.json", "seen.json", "board.json",
                     "oracle-chat.jsonl", "oracle-briefs.jsonl"):
            self.assertIn("deployment-state-path",
                          self._rules("deploy/" + name), name)

    def test_outbox_component_and_work_first_component_trip(self):
        self.assertIn("deployment-state-path",
                      self._rules("base/outbox/result.json"))
        self.assertIn("deployment-state-path",
                      self._rules("work/job-1/script.py"))

    def test_plain_files_are_clean(self):
        self.assertEqual([], self._rules("runner/runner.py"))
        self.assertEqual([], self._rules("README.md"))


class ContentRuleTest(unittest.TestCase):
    def setUp(self):
        self.reg = AG.default_registry()

    def _rules(self, path, content):
        return [f.rule for f in AG.scan_content(path, content,
                                                self.reg)]

    def test_allow_array_is_grant_state(self):
        rules = self._rules("notes.json",
                            b'{"permissions": {"allow": '
                            b'["Bash(npm test)"]}}')
        self.assertIn(AG.RULE_GRANT_STATE, rules)

    def test_saved_command_string_is_grant_state(self):
        rules = self._rules("notes.json",
                            b'{"history": ["Bash(npm test)"]}')
        self.assertIn(AG.RULE_GRANT_STATE, rules)

    def test_secret_inside_approved_command_trips_both_rules(self):
        rules = self._rules(".claude/settings.local.json",
                            _settings_local())
        self.assertIn(AG.RULE_GRANT_STATE, rules)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)

    def test_password_assignment_in_plain_text_is_in_command(self):
        rules = self._rules("notes.txt",
                            ("run it with password=%s\n"
                             % FAKE_DB_PASSWORD).encode())
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, rules)

    def test_known_key_format_is_a_secret_value(self):
        rules = self._rules("notes.txt",
                            ("key: %s\n" % FAKE_AWS_KEY).encode())
        self.assertIn(AG.RULE_SECRET_VALUE, rules)

    def test_clean_json_is_clean(self):
        self.assertEqual([], self._rules(
            "notes.json", b'{"permissions": {"allow": []}, '
                          b'"theme": "dark"}'))


def _git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _repo_with(files):
    repo = tempfile.mkdtemp(prefix="approvalguard-test-")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "guard@example.invalid")
    _git(repo, "config", "user.name", "Approval Guard Test")
    for name, content in files.items():
        path = os.path.join(repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)
    _git(repo, "add", "-A")
    return repo


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class StagedScanTest(unittest.TestCase):
    def test_staged_clean_tree_passes(self):
        repo = _repo_with({"src/app.py": b"print('hello')\n",
                           "notes.json": b'{"theme": "dark"}\n'})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = AG.main(["check", "--repo", repo])
        self.assertEqual(rc, 0, out.getvalue())

    def test_staged_settings_local_fails(self):
        repo = _repo_with({".claude/settings.local.json":
                           _settings_local()})
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = AG.main(["check", "--repo", repo])
        self.assertEqual(rc, 1)
        self.assertIn("agent-config-path", out.getvalue())

    def test_unstaged_working_tree_copy_does_not_trip(self):
        repo = _repo_with({"src/app.py": b"print('hello')\n"})
        path = os.path.join(repo, ".claude", "settings.local.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(_settings_local())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = AG.main(["check", "--repo", repo])
        self.assertEqual(rc, 0, out.getvalue())

    def test_report_names_file_and_rule_never_the_secret(self):
        repo = _repo_with({".claude/settings.local.json":
                           _settings_local()})
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = AG.main(["check", "--repo", repo])
        self.assertEqual(rc, 1)
        text = out.getvalue()
        self.assertIn(".claude/settings.local.json", text)
        self.assertIn(AG.RULE_SECRET_IN_COMMAND, text)
        self.assertNotIn(FAKE_DB_PASSWORD, text)
        self.assertNotIn("svc:", text)

    def test_not_a_repository_is_an_error_not_a_pass(self):
        plain = tempfile.mkdtemp(prefix="approvalguard-plain-")
        with contextlib.redirect_stderr(io.StringIO()):
            rc = AG.main(["check", "--repo", plain])
        self.assertEqual(rc, 2)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class ModeGateTest(unittest.TestCase):
    """privacy-design.md section 2: off refuses, audit shows and
    does nothing, enforce permits the explicit action -- here, the
    guard's stop. A misspelled mode is refused at validation."""

    def _repo_and_config(self, mode):
        repo = _repo_with({".claude/settings.local.json":
                           _settings_local()})
        cfg_path = os.path.join(repo, "guard-config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"security": {"modes": {AG.FEATURE: mode}}},
                      fh)
        return repo, cfg_path

    def _run(self, repo, cfg_path):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = AG.main(["check", "--repo", repo,
                          "--config", cfg_path])
        return rc, out.getvalue(), err.getvalue()

    def test_feature_is_in_the_family(self):
        self.assertIn(AG.FEATURE, S.FEATURES)
        self.assertEqual(S.sec_mode({}, AG.FEATURE), "enforce")

    def test_enforce_stops(self):
        repo, cfg = self._repo_and_config("enforce")
        rc, out, _ = self._run(repo, cfg)
        self.assertEqual(rc, 1)
        self.assertIn("agent-config-path", out)

    def test_audit_shows_and_stops_nothing(self):
        repo, cfg = self._repo_and_config("audit")
        rc, out, _ = self._run(repo, cfg)
        self.assertEqual(rc, 0)
        self.assertIn("would stop", out)
        self.assertIn("agent-config-path", out)

    def test_off_refuses(self):
        repo, cfg = self._repo_and_config("off")
        rc, out, err = self._run(repo, cfg)
        self.assertEqual(rc, 2)
        self.assertIn("off", err)
        self.assertEqual(out, "")

    def test_misspelled_mode_is_refused(self):
        repo, cfg = self._repo_and_config("loud")
        rc, _, err = self._run(repo, cfg)
        self.assertEqual(rc, 2)
        self.assertIn(AG.FEATURE, err)

    def test_example_config_states_the_feature(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "..", "config.example.json"),
                  encoding="utf-8") as fh:
            example = json.load(fh)
        self.assertEqual(
            example["security"]["modes"][AG.FEATURE], "enforce")
        S.validate_security_config(example)


class ValidateCommandTest(unittest.TestCase):
    def test_validate_accepts_the_declared_shape(self):
        path = os.path.join(tempfile.mkdtemp(), "reg.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"format": AG.REGISTRY_FORMAT, "version": 1,
                       "rules": [_rule("x", "basename", "a.json")]},
                      fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = AG.main(["validate", "--registry", path])
        self.assertEqual(rc, 0)
        self.assertIn("1 rule(s)", out.getvalue())

    def test_validate_refuses_a_malformed_registry(self):
        path = os.path.join(tempfile.mkdtemp(), "reg.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with contextlib.redirect_stderr(io.StringIO()):
            rc = AG.main(["validate", "--registry", path])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
