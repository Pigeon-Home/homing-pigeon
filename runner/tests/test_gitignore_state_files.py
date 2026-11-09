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


def _encode_paths(paths):
    """The exact bytes handed to git check-ignore --stdin.

    Bytes, never text: in text mode a Windows pipe translates
    each "\\n" to "\\r\\n" on the way in, and git then reads the
    "\\r" as part of the pathname -- the 3.15.20.10 release
    build's Windows leg matched almost nothing, its parsed keys
    arriving as '"outbox/result.json\\r"'. LF bytes are the wire
    format on every platform.
    """
    return ("\n".join(paths) + "\n").encode("utf-8")


def _parse_check_ignore(stdout_text):
    """git check-ignore -v output -> {pathname: pattern}."""
    matched = {}
    # Split on LF only: splitlines() also breaks on a bare CR,
    # which would cut a quoted pathname's CR adrift from its
    # closing quote and defeat the unquoting below.
    for line in stdout_text.split("\n"):
        # -v output: <source>:<linenum>:<pattern>\t<pathname>
        head, sep, pathname = line.partition("\t")
        if not sep:
            continue
        pathname = pathname.strip()
        if len(pathname) >= 2 and pathname.startswith('"') \
                and pathname.endswith('"'):
            # git C-quotes a pathname holding a character it
            # cannot print plainly (the stray CR above is one);
            # unquote, then drop the character that forced it.
            pathname = pathname[1:-1].encode("utf-8") \
                .decode("unicode_escape").rstrip("\r")
        matched[pathname] = head.rsplit(":", 1)[-1].strip()
    return matched


def _check_ignore(paths):
    """path -> matching pattern (or None), via git check-ignore."""
    proc = subprocess.run(
        ["git", "-C", REPO, "check-ignore", "-v", "--stdin"],
        input=_encode_paths(paths),
        capture_output=True)
    return _parse_check_ignore(
        proc.stdout.decode("utf-8", errors="replace"))


class CheckIgnoreWireTest(unittest.TestCase):
    """The stdin wire format and the -v parser, pinned apart
    from git itself: the Windows failure above lived in this
    seam, and it must be reachable from every platform's leg.
    """

    def test_encode_paths_is_bytes_with_lf_only(self):
        data = _encode_paths(["a/b.txt", "c.txt"])
        self.assertIsInstance(data, bytes)
        self.assertNotIn(b"\r", data)
        self.assertEqual(data, b"a/b.txt\nc.txt\n")

    def test_encode_paths_round_trips_every_name(self):
        data = _encode_paths(STATE_PATHS)
        self.assertEqual(data.decode("utf-8").splitlines(),
                         STATE_PATHS)

    def test_parse_a_plain_line(self):
        out = ".gitignore:31:outbox/\toutbox/result.json\n"
        self.assertEqual(_parse_check_ignore(out),
                         {"outbox/result.json": "outbox/"})

    def test_parse_a_quoted_cr_pathname(self):
        # The shape the Windows leg of the 3.15.20.10 build
        # actually produced: pathname C-quoted around a CR.
        out = '.gitignore:42:**/.claude/settings.local.json\t' \
              '".claude/settings.local.json\r"\n'
        self.assertEqual(
            _parse_check_ignore(out),
            {".claude/settings.local.json":
             "**/.claude/settings.local.json"})

    def test_parse_skips_blank_and_tabless_lines(self):
        self.assertEqual(_parse_check_ignore("\nnoise\n"), {})

    def test_check_ignore_sends_bytes_not_text(self):
        import unittest.mock as mock
        done = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"")
        with mock.patch.object(subprocess, "run",
                               return_value=done) as run:
            self.assertEqual(_check_ignore(["x/y.txt"]), {})
        kwargs = run.call_args.kwargs
        self.assertIsInstance(kwargs["input"], bytes)
        self.assertNotIn(b"\r", kwargs["input"])
        self.assertFalse(kwargs.get("text"))


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
