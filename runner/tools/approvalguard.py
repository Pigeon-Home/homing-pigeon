#!/usr/bin/env python3
"""Scan staged content for agent permission/config state (the approval guard).

# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

An agent's approval memory is private-shelf material. When a coding
agent saves a "don't ask again" approval, it persists the approved
command string -- verbatim, secret included, in plain text -- into a
project-shaped settings file. When that file is committed, the secret
is published, and deleting the file afterwards does not take it back
(git history and forks keep it; rotation must come first). This is
not a hypothetical: in November 2026 a security firm found over a
thousand public copies of one agent's local settings file holding
real passwords and API keys, roughly half of them carried across the
boundary by the agent's own commits, and roughly one in five of the
leaking files was flagged by neither of the two best-known secret
scanners -- usually because the secret was a password typed inside an
approved command, not a key in a recognizable format.

This guard is the boundary test for that category, in the shape the
privacy design declares (docs/steady/security/privacy-design.md):
agent permission/config state is the agent's papers, and its shelter
is exclusion from the publication scope. The tool scans what is
about to be published -- the staged content of a change -- and fails
closed on:

- any staged path matching a declared agent-config or deployment
  state shape (an agent's settings file, a deployment config, the
  runner's own state and chat-log files, its outbox and work dirs);
- permission-grant state in staged JSON: ``allow`` arrays and saved
  command strings of the shape an approval flow persists;
- secret-shaped values inside those command strings specifically --
  credential assignments, passwords inside URLs, password flags --
  and known key formats anywhere in staged text: the class generic
  scanners missed, checked where approvals actually put secrets.

The report follows split-existence-from-value, the house rule: it
names the file and the rule it tripped, and never the value. A
finding proves a shape crossed, and nothing about the secret itself
enters a log.

The registry of forbidden shapes is declared in code, below, in a
fixed format (``hp-approvalguard-registry``); an operator may add
path shapes of their own with a registry file in the same format,
validated exactly and refused when malformed, in the discipline of
runner/tools/nameguard.py. The registry names shapes, never
secrets, so unlike a name guard's registry it is not itself
private-shelf material -- but nothing forces an operator to publish
their copy either.

The extensions recorded as specified in agent-state-files.md
section 4 stand built here, in the same shapes: tool-server
configuration as a category of its own (a staged file named
``mcp.json``, and any staged JSON carrying the ``mcpServers``
top-level key, gets its ``env`` and ``headers`` maps scanned
wherever the file sits -- the filename and the key trigger the
deeper scan, they are not findings in themselves, because those
files are shareable by design and the content is what needs
guarding); grant state under its other names (``autoApprove``,
``allowedTools``, ``terminalAllowlist``, ``allowlist``, and a
``permission`` map), with entries scanned as the command strings
they can be; the same content shapes in TOML and YAML, where two
vendors' configuration lives; and staged areas beyond git's, as
this guard's second front door -- a Subversion working copy's
scheduled additions fed to the same scan -- plus content rules
for a Mercurial ``[auth]`` password line and a Subversion proxy
password. The general tree-wide form of the boundary test lives
in ``scan_tree_content``: the guard's agent-state rules applied
to a whole tree, where secret-in-command is read in its designed
context (structured documents' string values) rather than as a
raw line scan over source code that handles credentials as
variables by trade.

The rules are VCS-agnostic: they speak of paths and content, never
of git, so another front door (an svn working copy's status, say)
can feed the same scan the same (path, content) pairs. Two front
doors ship here: the git index, and a Subversion working copy's
scheduled additions (``check-svn``).

Like the personal-documents shelter, this tool is invoked, never
ambient: it runs when an operator -- or their agent -- runs it, at
the pre-commit / pre-push moment, and NOTHING here wires it into a
hook or into CI. Wiring it in is a deliberate operator-adoption
step, the operator's own, exactly as with the name guard.

When a runner config is handed to the tool (--config), the config
security mode for the feature ``agent_state_guard`` gates it, in
the privacy family's semantics for operator-invoked behaviours
(privacy-design.md section 2): off refuses (the guard does not
run), audit reports what would be stopped and stops nothing,
enforce lets the guard stop the commit. With no config the mode
defaults to enforce, like every feature in the family; a
misspelled mode is refused at config validation, as the family's
are. Nothing here acts at startup, and nothing moves or deletes
any file: the guard only reads staged content and reports.

    python3 runner/tools/approvalguard.py check [--repo DIR]
        [--config CONFIG.json] [--registry EXTRA.json]
    python3 runner/tools/approvalguard.py check-svn [--wc DIR]
        [--config CONFIG.json] [--registry EXTRA.json]
    python3 runner/tools/approvalguard.py validate --registry R.json

Exit codes: 0 = clean (audit mode: also 0, findings reported as
what would be stopped), 1 = findings under enforce, 2 = the guard
could not run (not a repository, unreadable input, a malformed
registry or config, or the feature's mode is off).

Stdlib only. Python 3.9 compatible.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import NamedTuple

# The feature this tool serves, in runner/guard/security.py's
# security.modes family.
FEATURE = "agent_state_guard"

REGISTRY_FORMAT = "hp-approvalguard-registry"
REGISTRY_VERSION = 1

# Path rule kinds. A rule matches a staged path ("/"-separated,
# relative to the tree root) when:
#   basename:        the path's last component equals the value.
#   basename-under:  the last component equals the part of the
#                    value after the final "/", and some earlier
#                    component equals the part before it
#                    (".claude/settings.local.json" reads as the
#                    file settings.local.json under a .claude dir).
#   component:       any component of the path equals the value.
#   first-component: the first component equals the value.
PATH_RULE_KINDS = ("basename", "basename-under", "component",
                   "first-component")

_TOP_KEYS = frozenset({"format", "version", "rules"})
_RULE_KEYS = frozenset({"id", "kind", "value", "note"})

# The declared registry: the forbidden shapes, in code, so two
# operators scanning the same staged change get the same answer.
# The ids are what a report names; keep them stable.
DEFAULT_REGISTRY_DATA = {
    "format": REGISTRY_FORMAT,
    "version": REGISTRY_VERSION,
    "rules": [
        {"id": "agent-config-path", "kind": "basename-under",
         "value": ".claude/settings.local.json",
         "note": "an agent's local settings: where 'don't ask "
                 "again' approvals are persisted"},
        {"id": "agent-config-path", "kind": "basename-under",
         "value": ".claude/settings.json",
         "note": "an agent's shared project settings: shareable "
                 "only when it holds no secret and no grant"},
        {"id": "deployment-state-path", "kind": "basename",
         "value": "config.json",
         "note": "a deployment config: holds the shared secret "
                 "and mailbox credentials in plaintext"},
        {"id": "deployment-state-path", "kind": "basename",
         "value": "seen.json",
         "note": "runner state: the seen-jobs record"},
        {"id": "deployment-state-path", "kind": "basename",
         "value": "board.json",
         "note": "runner state: the task board"},
        {"id": "deployment-state-path", "kind": "basename",
         "value": "oracle-chat.jsonl",
         "note": "the Oracle's chat log: an agent transcript"},
        {"id": "deployment-state-path", "kind": "basename",
         "value": "oracle-briefs.jsonl",
         "note": "the Oracle's briefs log"},
        {"id": "deployment-state-path", "kind": "component",
         "value": "outbox",
         "note": "the result outbox: staged results awaiting send"},
        {"id": "deployment-state-path", "kind": "first-component",
         "value": "work",
         "note": "per-job workspaces: job bodies and outputs"},
    ],
}

# Content rule ids (fixed behaviours, not registry data).
RULE_GRANT_STATE = "permission-grant-state"
RULE_SECRET_IN_COMMAND = "secret-in-command"
RULE_SECRET_VALUE = "secret-value"
RULE_TOOL_SERVER_SECRET = "tool-server-secret"
RULE_VCS_CREDENTIAL = "vcs-credential"

_RULE_DESCRIPTIONS = {
    "agent-config-path": "agent permission/config file",
    "deployment-state-path": "deployment state file",
    RULE_GRANT_STATE: "permission-grant state (an allow array or "
                      "a saved approved command)",
    RULE_SECRET_IN_COMMAND: "a secret-shaped value inside a "
                            "command string",
    RULE_SECRET_VALUE: "a secret-shaped value",
    RULE_TOOL_SERVER_SECRET: "a secret-shaped value inside a "
                             "tool-server env or headers map",
    RULE_VCS_CREDENTIAL: "a credential value in another version-"
                         "control system's own configuration shape",
}


class RegistryError(ValueError):
    """The registry is unreadable or outside the declared format."""


class GuardError(Exception):
    """The scan could not run (no repository, git failed)."""


class PathRule(NamedTuple):
    """One declared forbidden path shape."""

    id: str
    kind: str
    value: str
    note: str | None = None


class Registry(NamedTuple):
    """A validated registry: the declared path rules."""

    rules: tuple


class Finding(NamedTuple):
    """One match: the staged path, and the rule it tripped.

    Nothing else is carried: no line, no matched text, no value.
    Split existence from value, as the house rule has it.
    """

    path: str
    rule: str


def _check_rule_entry(entry, where):
    if not isinstance(entry, dict):
        raise RegistryError("%s: a rule entry must be an object, "
                            "not %s" % (where, type(entry).__name__))
    unknown = sorted(set(entry) - _RULE_KEYS)
    if unknown:
        raise RegistryError("%s: unknown key(s) %s; allowed keys "
                            "are %s" % (where, ", ".join(unknown),
                                        ", ".join(sorted(_RULE_KEYS))))
    for key in ("id", "kind", "value"):
        if key not in entry:
            raise RegistryError("%s: a rule entry needs %r"
                                % (where, key))
    rule_id = entry["id"]
    if not isinstance(rule_id, str) or not rule_id \
            or rule_id != rule_id.strip():
        raise RegistryError("%s: 'id' must be a non-empty string "
                            "with no leading or trailing whitespace"
                            % where)
    kind = entry["kind"]
    if kind not in PATH_RULE_KINDS:
        raise RegistryError("%s: 'kind' must be one of %s, not %r"
                            % (where, ", ".join(PATH_RULE_KINDS),
                               kind))
    value = entry["value"]
    if not isinstance(value, str) or not value:
        raise RegistryError("%s: 'value' must be a non-empty string"
                            % where)
    if kind == "basename-under" and "/" not in value:
        raise RegistryError("%s: a 'basename-under' value names a "
                            "directory and a file, joined by '/': "
                            "%r" % (where, value))
    if kind != "basename-under" and "/" in value:
        raise RegistryError("%s: a %r value is a single path "
                            "component, with no '/': %r"
                            % (where, kind, value))
    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        raise RegistryError("%s: 'note' must be a str, not %s"
                            % (where, type(note).__name__))
    return PathRule(rule_id, kind, value, note)


def parse_registry(data):
    """A Registry for parsed JSON `data`, held to the declared format.

    RegistryError names the first way `data` falls outside the
    format; nothing is guessed at and nothing is skipped.
    """
    if not isinstance(data, dict):
        raise RegistryError("the registry must be a JSON object, "
                            "not %s" % type(data).__name__)
    unknown = sorted(set(data) - _TOP_KEYS)
    if unknown:
        raise RegistryError("unknown key(s) %s; allowed keys are %s"
                            % (", ".join(unknown),
                               ", ".join(sorted(_TOP_KEYS))))
    if data.get("format") != REGISTRY_FORMAT:
        raise RegistryError("'format' must be %r, not %r"
                            % (REGISTRY_FORMAT, data.get("format")))
    version = data.get("version")
    if (isinstance(version, bool) or not isinstance(version, int)
            or version != REGISTRY_VERSION):
        raise RegistryError("'version' must be %d, not %r"
                            % (REGISTRY_VERSION, version))
    if "rules" not in data:
        raise RegistryError("the registry needs a 'rules' list "
                            "(an empty one is a valid registry)")
    raw_rules = data["rules"]
    if not isinstance(raw_rules, list):
        raise RegistryError("'rules' must be a list, not %s"
                            % type(raw_rules).__name__)
    rules = []
    seen = set()
    for i, entry in enumerate(raw_rules):
        rule = _check_rule_entry(entry, "rules[%d]" % i)
        key = (rule.id, rule.kind, rule.value)
        if key in seen:
            raise RegistryError(
                "rules[%d]: duplicate entry for rule %r (kind %r, "
                "value %r)" % (i, rule.id, rule.kind, rule.value))
        seen.add(key)
        rules.append(rule)
    return Registry(tuple(rules))


def default_registry():
    """The Registry declared in code in DEFAULT_REGISTRY_DATA."""
    return parse_registry(DEFAULT_REGISTRY_DATA)


def load_registry(path):
    """The Registry stored at `path`; RegistryError on any failure."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise RegistryError("cannot read registry %s: %s" % (path, exc))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegistryError("registry %s is not valid JSON: %s"
                            % (path, exc))
    return parse_registry(data)


def merge_registries(base, extra):
    """`base`'s rules with `extra`'s added; a duplicate is refused."""
    seen = {(r.id, r.kind, r.value) for r in base.rules}
    rules = list(base.rules)
    for rule in extra.rules:
        key = (rule.id, rule.kind, rule.value)
        if key in seen:
            raise RegistryError(
                "duplicate rule %r (kind %r, value %r) across "
                "registries" % (rule.id, rule.kind, rule.value))
        seen.add(key)
        rules.append(rule)
    return Registry(tuple(rules))


def _path_matches(rule, path):
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if not parts:
        return False
    if rule.kind == "basename":
        return parts[-1] == rule.value
    if rule.kind == "component":
        return rule.value in parts
    if rule.kind == "first-component":
        return parts[0] == rule.value
    # basename-under: "<dir>/<base>"
    directory, _, base = rule.value.rpartition("/")
    return parts[-1] == base and directory in parts[:-1]


# ---- the content rules

# Known key formats and secret-bearing shapes, anywhere in staged
# text. Fixed in code, like the name guard's lookalike table: two
# operators scanning the same content get the same answer.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS key id
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),          # GitHub token
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),        # GitHub PAT
    re.compile(r"glpat-[A-Za-z0-9_-]{15,}"),            # GitLab PAT
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),           # Anthropic
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),               # OpenAI-style
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),              # Google API
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),        # Slack
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # private key
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
               r"[A-Za-z0-9_-]{10,}"),                  # a JWT
)

# Secret shapes inside a command string: the password typed next to
# the thing it unlocks. This is the class that generic scanners
# missed in the incident this guard answers, so it is checked
# against every string a staged JSON document carries (approval
# files are JSON) and against every line of any other staged text.
_COMMAND_SECRET_PATTERNS = (
    # scheme://user:password@host -- a credential inside a URL.
    re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:[^\s/@]{3,}@"),
    # NAME=value where the name says the value is a secret.
    re.compile(r"(?i)(?:password|passwd|pwd|secret|token|api[-_]?key"
               r"|auth)[A-Za-z0-9_]*\s*=\s*[^\s\"']{4,}"),
    # --flag value where the flag says the value is a secret.
    re.compile(r"(?i)--(?:password|passwd|secret|token|api[-_]?key)"
               r"(?:\s+|=)[^\s\"']{4,}"),
    # sshpass -p <password>: the server login inside the command.
    re.compile(r"sshpass\s+-p\s+\S{3,}"),
    # mysql-style -p<password> attached to the flag.
    re.compile(r"(?:^|\s)-p\S{4,}"),
)

# A saved approved command, in the shape approval flows persist:
# a tool name and the command in parentheses, Bash(npm test) and
# its kin.
_SAVED_COMMAND = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*\(.+\)$",
                            re.DOTALL)

# Staged content past this size is path-checked only: approval and
# state files are small, and a guard at the commit boundary must
# stay fast. The cap is a named constant, not a heuristic.
CONTENT_SCAN_MAX_BYTES = 8 * 1024 * 1024


def _json_strings(node, out):
    """Every string in a parsed JSON document, keys included."""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            out.append(key)
            _json_strings(value, out)
    elif isinstance(node, list):
        for value in node:
            _json_strings(value, out)


def _grant_state_findings(path, data):
    """permission-grant-state findings in a parsed document.

    A grant key (``allow`` and its other names, in
    GRANT_LIST_KEYS) holding a non-empty list of strings is grant
    state wherever it sits; so are a non-empty ``autoApprove``
    list of any items and a non-empty ``permission`` map, list or
    string; and a string in the saved-command shape is grant
    state wherever it sits. The values themselves are never
    carried into a finding.
    """
    findings = []

    def walk(node):
        if isinstance(node, dict):
            for key in GRANT_LIST_KEYS:
                value = node.get(key)
                if isinstance(value, list) and value and all(
                        isinstance(item, str) for item in value):
                    findings.append(Finding(path, RULE_GRANT_STATE))
            auto = node.get("autoApprove")
            if isinstance(auto, list) and auto:
                findings.append(Finding(path, RULE_GRANT_STATE))
            perm = node.get("permission")
            if (isinstance(perm, dict) and perm) or (
                    isinstance(perm, list) and perm) or (
                    isinstance(perm, str) and perm.strip()):
                findings.append(Finding(path, RULE_GRANT_STATE))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            if _SAVED_COMMAND.match(node.strip()):
                findings.append(Finding(path, RULE_GRANT_STATE))

    walk(data)
    return findings


# ---- the extensions: grant names, tool-server maps, TOML/YAML,
# ---- the other version-control systems' credential shapes

# Grant state under its other names (agent-state-files.md section
# 3's survey): the allowlist keys whose entries can be the full
# command strings themselves. ``allow`` is the shipped member;
# the rest are the same shape under other vendors' names.
GRANT_LIST_KEYS = ("allow", "allowedTools", "terminalAllowlist",
                   "allowlist")

# A key whose name says the value it holds is a secret. Used only
# where a value's *position* is the evidence -- inside a
# tool-server env/headers map, or as a named scalar in a TOML/YAML
# document -- never as a bare word search over text.
_SECRET_KEY_NAME = re.compile(
    r"(?i)password|passwd|secret|token|api[-_]?key|access[-_]?key"
    r"|private[-_]?key|credential|auth")

# Values that name a secret without holding one: an environment
# reference is the safe pattern for exactly the maps this guard
# scans, and a declared placeholder holds nothing to publish.
_PLACEHOLDER_WORDS = frozenset({
    "changeme", "change-me", "placeholder", "example", "redacted",
    "none", "null", "true", "false", "xxxx", "********",
})


def _is_placeholder(value):
    """True when `value` names a secret without holding one."""
    stripped = value.strip().strip("\"'").strip()
    if not stripped:
        return True
    if stripped.startswith("${") or stripped.startswith("$"):
        return True
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    return stripped.lower() in _PLACEHOLDER_WORDS


def _secret_shaped(value):
    """True when `value` matches a known key format or a
    command-secret shape."""
    return any(p.search(value) for p in _SECRET_VALUE_PATTERNS) \
        or any(p.search(value) for p in _COMMAND_SECRET_PATTERNS)


# Basenames that name a file as tool-server configuration, and
# the top-level key that names it in any JSON document whatever
# the file is called (the shape every surveyed vendor's examples
# use; VS Code's own ``servers`` key is reached through the
# filename trigger, which scans the whole file's maps).
MCP_BASENAMES = ("mcp.json", ".mcp.json")
MCP_TOP_KEYS = ("mcpServers",)


def _scan_secret_map(path, mapping, findings):
    """One env/headers map: a secret-shaped value fires, and so
    does a plain value sitting under a secret-named key."""
    for key, value in mapping.items():
        if isinstance(value, dict):
            _scan_secret_map(path, value, findings)
            continue
        if not isinstance(value, str):
            continue
        if _secret_shaped(value) or (
                _SECRET_KEY_NAME.search(str(key))
                and not _is_placeholder(value)
                and len(value.strip()) >= 4):
            findings.append(Finding(path, RULE_TOOL_SERVER_SECRET))
            return


def _tool_server_findings(path, data):
    """tool-server-secret findings in a parsed document.

    The trigger is position: the file is named for tool-server
    configuration, or the document carries the tool-server
    top-level key. Under a trigger, every ``env`` and ``headers``
    map in the document is scanned; outside one, those map names
    are ordinary configuration and stay silent.
    """
    basename = path.replace("\\", "/").rsplit("/", 1)[-1]
    triggered = basename in MCP_BASENAMES or (
        isinstance(data, dict)
        and any(key in data for key in MCP_TOP_KEYS))
    if not triggered:
        return []
    findings = []

    def walk(node):
        if isinstance(node, dict):
            for key in ("env", "headers"):
                mapping = node.get(key)
                if isinstance(mapping, dict):
                    _scan_secret_map(path, mapping, findings)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    seen = []
    for finding in findings:
        if finding not in seen:
            seen.append(finding)
    return seen[:1]


# The exact key names that make a TOML/YAML scalar a named
# secret: the whole key, separators and case aside, is the
# secret's name (``apiKey``, ``shared_secret``,
# ``mailbox_password``). A compound name that merely contains
# one of these words -- a script called ``homing-pigeon-auth``,
# a workflow's ``id-token`` permission -- is a different thing
# wearing a similar name, and stays silent.
_NAMED_SECRET_KEYS = frozenset({
    "password", "passwd", "pwd", "secret", "token",
    "apikey", "api_key", "api-key", "accesskey", "access_key",
    "access-key", "privatekey", "private_key", "private-key",
    "credential", "credentials", "clientsecret", "client_secret",
    "client-secret", "sharedsecret", "shared_secret",
    "shared-secret", "mailboxpassword", "mailbox_password",
    "mailbox-password", "authtoken", "auth_token", "auth-token",
})


def _is_named_secret_key(key):
    return str(key).strip().strip("\"'").lower() \
        in _NAMED_SECRET_KEYS


def _named_secret_findings(path, data):
    """secret-in-command findings for named scalars in a parsed
    TOML/YAML document: a secret-named key holding a plain value
    (a provider ``apiKey`` field is the survey's shape). One
    finding per document is the whole report."""
    findings = []

    def walk(node):
        if findings:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) \
                        and _is_named_secret_key(key) \
                        and not _is_placeholder(value) \
                        and len(value.strip()) >= 4:
                    findings.append(
                        Finding(path, RULE_SECRET_IN_COMMAND))
                    return
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return findings


def _parse_toml(text):
    """A TOML document as data, or None: `tomllib` where the
    interpreter carries it (3.11+), else the caller's line
    fallback -- the fallback narrows the read, never the rules."""
    try:
        import tomllib
    except ImportError:
        return None
    try:
        return tomllib.loads(text)
    except ValueError:
        return None


_YAML_KEY = re.compile(r"^([^:]+):\s*(.*)$")


def _yaml_scalar(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_yaml_scalar(part) for part in inner.split(",")]
    if raw.startswith("{") and raw.endswith("}"):
        out = {}
        inner = raw[1:-1].strip()
        if inner:
            for part in inner.split(","):
                key, _, value = part.partition(":")
                out[key.strip().strip("\"'")] = _yaml_scalar(value)
        return out
    return raw


def _parse_yaml_subset(text):
    """A bounded YAML subset as data, or None outside it.

    Nested maps and scalar lists by indentation, inline lists
    and maps, quoted and plain scalars -- the shape vendor
    configuration files are written in. Anchors, block scalars
    and multi-line strings are outside the subset: the caller
    falls back to the line scan for those documents, so a shape
    the subset cannot hold is read by the other reader, not
    skipped.
    """
    rows = []
    for raw_line in text.splitlines():
        if "\t" in raw_line[:len(raw_line) - len(raw_line.lstrip())]:
            return None
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") \
                or stripped in ("---", "..."):
            continue
        if stripped.endswith("|") or stripped.endswith(">") \
                or "&" in stripped.split(":", 1)[0] \
                or "*" == stripped[:1]:
            return None
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        rows.append((indent, stripped))
    if not rows:
        return {}

    def parse_block(index, indent):
        if index >= len(rows):
            return None, index
        is_list = rows[index][1].startswith("- ") \
            or rows[index][1] == "-"
        if is_list:
            out = []
            while index < len(rows) and rows[index][0] == indent \
                    and (rows[index][1].startswith("- ")
                         or rows[index][1] == "-"):
                item = rows[index][1][1:].strip()
                index += 1
                if not item:
                    value, index = parse_block(index, indent + 1) \
                        if index < len(rows) else (None, index)
                    out.append(value)
                    continue
                match = _YAML_KEY.match(item)
                if match and not item.startswith(("\"", "'")):
                    entry = {}
                    key = match.group(1).strip().strip("\"'")
                    rest = match.group(2)
                    if rest:
                        entry[key] = _yaml_scalar(rest)
                    elif index < len(rows) \
                            and rows[index][0] > indent:
                        value, index = parse_block(
                            index, rows[index][0])
                        entry[key] = value
                    else:
                        entry[key] = {}
                    while index < len(rows) \
                            and rows[index][0] > indent:
                        more, index = parse_block(
                            index, rows[index][0])
                        if isinstance(more, dict):
                            entry.update(more)
                        else:
                            break
                    out.append(entry)
                else:
                    out.append(_yaml_scalar(item))
            return out, index
        out = {}
        while index < len(rows) and rows[index][0] == indent \
                and not rows[index][1].startswith("- "):
            match = _YAML_KEY.match(rows[index][1])
            if not match:
                return None, index
            key = match.group(1).strip().strip("\"'")
            rest = match.group(2)
            index += 1
            if rest:
                out[key] = _yaml_scalar(rest)
            elif index < len(rows) and rows[index][0] > indent:
                value, index = parse_block(index, rows[index][0])
                out[key] = value
            else:
                out[key] = {}
        return out, index

    data, end = parse_block(0, rows[0][0])
    if data is None or end != len(rows):
        return None
    return data


_STRUCTURED_SUFFIXES = (".toml", ".yaml", ".yml")
_GRANT_LINE = re.compile(
    r"^\s*[\"']?(allow|autoApprove|allowedTools|"
    r"terminalAllowlist|allowlist|permission)[\"']?\s*[:=]\s*"
    r"(\S.*)$")
_NAMED_SECRET_LINE = re.compile(
    r"^\s*[\"']?([A-Za-z0-9_.-]+)[\"']?\s*[:=]\s*"
    r"[\"']?([^\s\"'#]{4,})")


def _text_structure_findings(path, text):
    """The structured shapes read off raw lines, for a TOML/YAML
    document the parsers could not hold: grant keys with a
    non-empty value, and secret-named assignments with a plain
    value. Placeholder values stay silent, as they do in the
    parsed read."""
    findings = []
    for line in text.splitlines():
        match = _GRANT_LINE.match(line)
        if match and match.group(2) not in ("[]", "{}", '""', "''"):
            findings.append(Finding(path, RULE_GRANT_STATE))
        match = _NAMED_SECRET_LINE.match(line)
        if match and _is_named_secret_key(match.group(1)) \
                and not _is_placeholder(match.group(2)):
            findings.append(
                Finding(path, RULE_SECRET_IN_COMMAND))
        if findings and len(set(findings)) >= 2:
            break
    unique = []
    for finding in findings:
        if finding not in unique:
            unique.append(finding)
    return unique


_HG_AUTH_PASSWORD = re.compile(
    r"(?i)^(?:[A-Za-z0-9_*-]+\.)?password\s*=\s*(\S.*)$")
_SVN_PROXY_PASSWORD = re.compile(
    r"(?i)^http-proxy-password\s*=\s*(\S.*)$")
_INI_HEADER = re.compile(r"^\[(.+)\]\s*$")


def _vcs_credential_findings(path, text):
    """vcs-credential findings in raw text: a Mercurial ``[auth]``
    section's password line, and a Subversion proxy password.
    The key named with no value, a placeholder value, and (for
    Mercurial) a password line outside an ``[auth]`` section all
    stay silent."""
    in_auth = False
    for line in text.splitlines():
        stripped = line.strip()
        header = _INI_HEADER.match(stripped)
        if header:
            in_auth = header.group(1).strip().lower() == "auth"
            continue
        match = _SVN_PROXY_PASSWORD.match(stripped)
        if match and not _is_placeholder(match.group(1)):
            return [Finding(path, RULE_VCS_CREDENTIAL)]
        if in_auth:
            match = _HG_AUTH_PASSWORD.match(stripped)
            if match and not _is_placeholder(match.group(1)):
                return [Finding(path, RULE_VCS_CREDENTIAL)]
    return []


# Every command-secret pattern needs one of these substrings, so
# a candidate without one cannot match: the pre-check keeps a
# whole-tree scan fast without changing any answer.
_COMMAND_HINTS = ("password", "passwd", "pwd", "secret", "token",
                  "api", "auth", "sshpass", "://", "-p")


def _command_secret_hit(candidate):
    lowered = candidate.lower()
    if not any(hint in lowered for hint in _COMMAND_HINTS):
        return False
    return any(p.search(candidate)
               for p in _COMMAND_SECRET_PATTERNS)


def _scan(path, content, registry, tree_wide):
    findings = []
    for rule in registry.rules:
        if _path_matches(rule, path):
            findings.append(Finding(path, rule.id))
    if len(content) > CONTENT_SCAN_MAX_BYTES:
        return findings
    text = content.decode("utf-8", errors="replace")
    data = None
    structured = None
    try:
        data = json.loads(text)
        structured = "json"
    except ValueError:
        data = None
    lowered_path = path.lower()
    if data is None and lowered_path.endswith(".toml"):
        data = _parse_toml(text)
        if data is not None:
            structured = "toml"
    if data is None and lowered_path.endswith((".yaml", ".yml")):
        data = _parse_yaml_subset(text)
        if data is not None:
            structured = "yaml"
    if data is not None:
        findings.extend(_grant_state_findings(path, data))
        findings.extend(_tool_server_findings(path, data))
        if structured in ("toml", "yaml"):
            findings.extend(_named_secret_findings(path, data))
        strings = []
        _json_strings(data, strings)
    else:
        if lowered_path.endswith(_STRUCTURED_SUFFIXES):
            findings.extend(_text_structure_findings(path, text))
        strings = text.splitlines()
    findings.extend(_vcs_credential_findings(path, text))
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append(Finding(path, RULE_SECRET_VALUE))
            break
    if tree_wide and structured is None:
        # The general form reads secret-in-command only in its
        # designed context -- a structured document's values.
        # Source and prose that handle credentials as variables
        # are not agent-state material, and a raw line scan over
        # a whole tree answers a different question (measured
        # in the desk record for this lane).
        return findings
    for candidate in strings:
        if _command_secret_hit(candidate):
            findings.append(Finding(path, RULE_SECRET_IN_COMMAND))
            break
    return findings


def scan_content(path, content, registry):
    """Every Finding in one staged (path, content) pair.

    `content` is bytes; undecodable bytes are replaced, so a binary
    file scans as its decodable text rather than crashing the scan.
    The path rules run on every pair; the content rules run on the
    decoded text within the size cap.
    """
    return _scan(path, content, registry, tree_wide=False)


def scan_tree_content(path, content, registry):
    """Every Finding in one (path, content) pair of a whole tree:
    the guard's agent-state rules in their general form, for the
    tree-wide value-confinement test. Identical to the staged
    scan except that secret-in-command is read only inside
    structured documents, where command strings are data."""
    return _scan(path, content, registry, tree_wide=True)


def scan_entries(entries, registry):
    """Every Finding over (path, content) pairs, in entry order.

    The VCS-agnostic heart of the guard: any front door that can
    list what is about to be published, as (path, content) pairs,
    gets the same scan and the same answer.
    """
    findings = []
    for path, content in entries:
        findings.extend(scan_content(path, content, registry))
    return findings


# ---- the git front door

def _git(repo, args):
    proc = subprocess.run(
        ["git", "-C", repo] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise GuardError("git %s failed in %s: %s"
                         % (args[0], repo,
                            proc.stderr.decode("utf-8", "replace")
                            .strip()))
    return proc.stdout


def staged_entries(repo):
    """The git index at `repo`, as (path, content) pairs.

    Added, copied, modified and renamed entries (a rename is read
    under its new name); deletions stage no content and are not
    scanned. Content is the staged blob, read from the index --
    what would actually be committed, not the working tree.
    """
    try:
        raw = _git(repo, ["diff", "--cached", "--name-only", "-z",
                          "--diff-filter=ACMR"])
    except FileNotFoundError:
        raise GuardError("git is not available on this machine")
    entries = []
    for name in raw.decode("utf-8", "surrogateescape").split("\0"):
        if not name:
            continue
        entries.append((name, _git(repo, ["show", ":" + name])))
    return entries


def scan_staged(repo, registry):
    """Every Finding in the staged content of the repo at `repo`."""
    return scan_entries(staged_entries(repo), registry)


# ---- the Subversion front door: the same guard's second door,
# ---- not a second tool (agent-state-files.md section 4)

def svn_scheduled_entries(status_text, read_content):
    """(path, content) pairs for a working copy's scheduled
    additions, read off `svn status` output.

    A scheduled addition carries status code ``A`` in the first
    column; the path starts after the eighth column, the status
    field's fixed width. Modified, missing, unversioned and
    every other entry is not a pre-commit crossing and is not
    fed to the scan. `read_content` takes a path and returns its
    bytes, so the reader is pinned without a Subversion binary.
    """
    entries = []
    for line in status_text.splitlines():
        if len(line) < 9 or line[0] != "A":
            continue
        path = line[8:].strip()
        if path:
            entries.append((path, read_content(path)))
    return entries


def svn_entries(wc):
    """A Subversion working copy's scheduled additions at `wc`,
    as (path, content) pairs read from the working copy itself --
    what its pre-commit is about to carry."""
    try:
        proc = subprocess.run(
            ["svn", "status", wc],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise GuardError("svn is not available on this machine")
    if proc.returncode != 0:
        raise GuardError("svn status failed in %s: %s"
                         % (wc, proc.stderr.decode(
                             "utf-8", "replace").strip()))
    status_text = proc.stdout.decode("utf-8", "surrogateescape")

    def read_content(path):
        with open(os.path.join(wc, path), "rb") as fh:
            return fh.read()

    return svn_scheduled_entries(status_text, read_content)


def scan_svn(wc, registry):
    """Every Finding in a Subversion working copy's scheduled
    additions at `wc`."""
    return scan_entries(svn_entries(wc), registry)


# ---- the whole tree, for the general tree-wide test

def tracked_entries(repo):
    """The tracked tree at `repo`, as (path, content) pairs: the
    `git ls-files` list, each file read from the working tree."""
    try:
        raw = _git(repo, ["ls-files", "-z"])
    except FileNotFoundError:
        raise GuardError("git is not available on this machine")
    entries = []
    for name in raw.decode("utf-8", "surrogateescape").split("\0"):
        if not name:
            continue
        with open(os.path.join(repo, name), "rb") as fh:
            entries.append((name, fh.read()))
    return entries


def scan_tree(repo, registry):
    """Every tree-wide Finding in the tracked tree at `repo`."""
    findings = []
    for path, content in tracked_entries(repo):
        findings.extend(scan_tree_content(path, content, registry))
    return findings


# ---- the command line

def _load_security():
    """runner.guard.security, imported from the tree this tool
    ships in; None when the tree is not importable."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from runner.guard import security
        return security
    except ImportError:
        return None


def _load_config(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return data


def _report(findings, audit, out):
    for f in findings:
        desc = _RULE_DESCRIPTIONS.get(f.rule, f.rule)
        if audit:
            print("%s: would stop: %s (%s)" % (f.path, desc, f.rule),
                  file=out)
        else:
            print("%s: %s (%s)" % (f.path, desc, f.rule), file=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_val = sub.add_parser("validate",
                           help="check a registry against the format")
    p_val.add_argument("--registry", required=True)
    p_check = sub.add_parser(
        "check", help="scan the staged content of a repository")
    p_check.add_argument("--repo", default=".",
                         help="repository to scan (default: .)")
    p_check.add_argument("--config", default=None,
                         help="runner config.json; its security mode "
                              "for %s gates this tool" % FEATURE)
    p_check.add_argument("--registry", default=None,
                         help="an extra registry file: its path "
                              "rules are added to the declared ones")
    p_svn = sub.add_parser(
        "check-svn", help="scan a Subversion working copy's "
                          "scheduled additions")
    p_svn.add_argument("--wc", default=".",
                       help="working copy to scan (default: .)")
    p_svn.add_argument("--config", default=None,
                       help="runner config.json; its security mode "
                            "for %s gates this tool" % FEATURE)
    p_svn.add_argument("--registry", default=None,
                       help="an extra registry file: its path "
                            "rules are added to the declared ones")
    args = ap.parse_args(argv)

    if args.cmd == "validate":
        try:
            registry = load_registry(args.registry)
        except RegistryError as exc:
            print("approvalguard: %s" % exc, file=sys.stderr)
            return 2
        print("valid: %d rule(s)" % len(registry.rules))
        return 0

    registry = default_registry()
    if args.registry:
        try:
            registry = merge_registries(
                registry, load_registry(args.registry))
        except RegistryError as exc:
            print("approvalguard: %s" % exc, file=sys.stderr)
            return 2

    mode = "enforce"
    if args.config:
        security = _load_security()
        if security is None:
            print("approvalguard: --config was given but the "
                  "security modes module is not importable from "
                  "this tree; refusing rather than guessing a mode",
                  file=sys.stderr)
            return 2
        try:
            cfg = _load_config(args.config)
            security.validate_security_config(cfg)
        except (OSError, ValueError, RuntimeError) as exc:
            print("approvalguard: %s" % exc, file=sys.stderr)
            return 2
        mode = security.sec_mode(cfg, FEATURE)
    if mode == "off":
        print("approvalguard: the %s security mode is off; the "
              "guard did not run." % FEATURE, file=sys.stderr)
        return 2

    try:
        if args.cmd == "check-svn":
            findings = scan_svn(args.wc, registry)
        else:
            findings = scan_staged(args.repo, registry)
    except GuardError as exc:
        print("approvalguard: %s" % exc, file=sys.stderr)
        return 2

    if not findings:
        print("approvalguard: staged content is clean.")
        return 0
    _report(findings, mode == "audit", sys.stdout)
    if mode == "audit":
        print("approvalguard: %d finding(s); the %s security mode "
              "is audit, so nothing was stopped."
              % (len(findings), FEATURE), file=sys.stderr)
        return 0
    print("approvalguard: %d finding(s); nothing here was "
          "committed by this tool -- unstage the file(s) above, "
          "and if one was ever committed, rotate its secrets "
          "first: deleting the file does not take it back."
          % len(findings), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
