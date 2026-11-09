# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The shipped .gitignore keeps the agent's papers out of commits.

Agent permission and config state -- an agent's approval memory
(the saved record of what its operator approved and need not be
asked again), a deployment's config, the runner's state files --
is private-shelf material. The protection that failed publicly
in November 2026 was an exclude living in one machine's global
git configuration, which does not travel with a project; this
suite ships the patterns in the root .gitignore instead, so the
protection clones with the tree (the design record is
docs/steady/security/privacy-design.md, section 8).

These tests pin the list. Dropping a pattern fails here, and so
does a pattern that reaches a file the tree tracks on purpose --
the negative controls are the tracked lookalikes
(runner/config.example.json, the de_dust board.jsonl fixtures).

The list grew by a second block when the cross-tool survey
(docs/steady/security/agent-state-files.md) catalogued the same
papers kept by other agents: another vendor's local settings
sibling, home-state filenames, transcript shapes, one editor's
per-user state, and the other version-control systems' admin
folders. Those patterns are pinned here the same way.
"""
import os
import shutil
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
GITIGNORE = os.path.join(REPO, ".gitignore")

HAVE_GIT = shutil.which("git") is not None

# The state shapes the root .gitignore must carry, exactly as
# written there. .claude/settings.json is absent on purpose: it
# is shareable project settings by design; it must never hold a
# secret, which is a documentation rule, not an ignore rule.
STATE_PATTERNS = [
    "**/.claude/settings.local.json",
    "**/config.json",
    "seen.json",
    "board.json",
    "oracle-chat.jsonl",
    "oracle-briefs.jsonl",
    "outbox/",
    "work/",
    # The cross-tool block: the same papers under other agents'
    # names (the survey is docs/steady/security/
    # agent-state-files.md).
    "**/settings.local.json",
    ".aider.chat.history.md",
    ".aider.input.history",
    ".aider.llm.history",
    ".aider.tags.cache.v*/",
    ".aider.env",
    "**/auth.json",
    "**/providers.json",
    "**/oauth_creds.json",
    "**/trustedFolders.json",
    "**/permissions-config.json",
    "**/session-store.db",
    "**/opencode.db",
    "**/taskHistory.json",
    "**/history.jsonl",
    "**/rollout-*.jsonl",
    "**/events.jsonl",
    "**/*.chat.history.md",
    "**/api_conversation_history.json",
    "**/.idea/workspace.xml",
    "**/.idea/shelf/",
    "**/.svn/",
    "**/.hg/",
]

# Paths a state file would actually wear, and the tracked
# lookalikes that must stay committable.
STATE_PATHS = [
    ".claude/settings.local.json",
    "sub/.claude/settings.local.json",
    "config.json",
    "deploy/config.json",
    "seen.json",
    "board.json",
    "oracle-chat.jsonl",
    "oracle-briefs.jsonl",
    "outbox/result.json",
    "work/scratch.txt",
    ".github/copilot/settings.local.json",
    ".aider.chat.history.md",
    ".aider.input.history",
    ".aider.llm.history",
    ".aider.tags.cache.v3/tags",
    ".aider.env",
    ".codex/auth.json",
    "sweep/providers.json",
    "sweep/oauth_creds.json",
    "sweep/trustedFolders.json",
    "sweep/permissions-config.json",
    "sweep/session-store.db",
    "sweep/opencode.db",
    "sweep/taskHistory.json",
    "sessions/history.jsonl",
    "sessions/rollout-2026-11-08.jsonl",
    "sessions/events.jsonl",
    "notes.chat.history.md",
    "chat/api_conversation_history.json",
    ".idea/workspace.xml",
    ".idea/shelf/old.txt",
    "carried/.svn/entries",
    "carried/.hg/hgrc",
]
TRACKED_LOOKALIKES = [
    "runner/config.example.json",
    "runner/tests/de_dust/board.jsonl",
    "README.md",
]


def _gitignore_lines():
    with open(GITIGNORE, encoding="utf-8") as fh:
        return [line.strip() for line in fh
                if line.strip() and not line.strip().startswith("#")]


def _check_ignore(paths):
    """path -> matching pattern (or None), via git check-ignore."""
    proc = subprocess.run(
        ["git", "-C", REPO, "check-ignore", "-v", "--stdin"],
        input="\n".join(paths) + "\n",
        capture_output=True, text=True)
    matched = {}
    for line in proc.stdout.splitlines():
        # -v output: <source>:<linenum>:<pattern>\t<pathname>
        head, _, pathname = line.partition("\t")
        matched[pathname] = head.rsplit(":", 1)[-1]
    return matched


class GitignoreStatePatternsTest(unittest.TestCase):

    def test_every_state_pattern_is_shipped(self):
        lines = _gitignore_lines()
        for pattern in STATE_PATTERNS:
            self.assertIn(pattern, lines)

    def test_the_shared_settings_file_is_not_ignored_by_the_list(self):
        # The list names the local approval file only; a line
        # ignoring .claude/settings.json itself would hide
        # shareable project settings instead of protecting state.
        lines = _gitignore_lines()
        for line in lines:
            self.assertNotEqual(line.rstrip("/"),
                                "**/.claude/settings.json")
            self.assertNotEqual(line.rstrip("/"),
                                ".claude/settings.json")

    @unittest.skipUnless(HAVE_GIT, "git not installed")
    def test_state_paths_are_ignored_and_lookalikes_are_not(self):
        matched = _check_ignore(STATE_PATHS + TRACKED_LOOKALIKES)
        for path in STATE_PATHS:
            self.assertIn(path, matched)
            self.assertIn(matched[path], STATE_PATTERNS)
        for path in TRACKED_LOOKALIKES:
            self.assertNotIn(path, matched)

    @unittest.skipUnless(HAVE_GIT, "git not installed")
    def test_no_tracked_file_matches_a_state_pattern(self):
        proc = subprocess.run(["git", "-C", REPO, "ls-files"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        tracked = [p for p in proc.stdout.splitlines() if p]
        matched = _check_ignore(tracked)
        offenders = {p: pat for p, pat in matched.items()
                     if pat in STATE_PATTERNS}
        self.assertEqual(offenders, {})


if __name__ == "__main__":
    unittest.main()
