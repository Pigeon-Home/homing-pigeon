#!/usr/bin/env python3
"""Declare cs_office disclosure postures, and check tagging against them.

A cs_office project is not simply public or private. What may be
said publicly about it, and where its material may live, is its
**disclosure posture**, and a posture is declared data, not code:
an operator writes the postures down in a registry file, in the
format declared below, categorizes each project by writing a tag
beside it in a tagging file, and this tool reports what any
tagging comes to under the registry as declared. The design note
(docs/infrastructure-documents/project/cs_office-postures.md)
records the model and the extensibility rules; this file declares
the two formats and enforces them exactly.

Reworking the taxonomy is editing the registry, never the tool:
a posture is added by appending an entry, retired by marking it
so (with a successor where one exists), and a project is
re-categorized by editing its one tagging entry. The tool holds
no state between runs.

Registry format (declared here; the loader enforces it exactly):

    {
      "format": "hp-posture-registry",
      "version": 1,
      "postures": [
        {"id": "nothing-said", "tag": "A",
         "say": "Nothing. The project is not named, described,
                 or acknowledged in public writing.",
         "shelf": "Private shelf only.",
         "note": "what this posture is, in the operator's words"}
      ]
    }

- ``format`` must be the string above and ``version`` the
  integer 1. Anything else is refused: a registry in a shape
  this tool does not know is a registry it must not guess at.
- ``postures`` is a list, possibly empty. Each entry is an
  object. No keys are allowed beyond the ones below, at any
  level: an unrecognized key is almost always a typo, and a
  typo in a declaration must fail loudly rather than silently
  change what a tag permits.
- ``id`` is required: the posture's stable identity, issued
  once and never reused or renamed — lowercase ``[a-z0-9]``
  segments joined by single dashes, at most 64 characters. Two
  entries with the same id are refused.
- ``tag`` is required: the short token a tagging file writes —
  at most 16 characters, no whitespace, no control characters, and no zero-width
  characters anywhere in it. Tags are compared exactly, and
  are unique across the whole registry, retired postures
  included; two tags that differ only in case are also refused,
  because a tag that is nearly another tag is a tag that will
  be mistyped onto the wrong project.
- ``say`` and ``shelf`` are required: what may be said publicly
  about a project under this posture, and where the project's
  material may live, each a non-empty string with no leading
  or trailing whitespace and no control or zero-width characters.
- ``status`` is ``"active"`` (the default) or ``"retired"``.
  A retired posture stays in the registry so old references
  still resolve; it is never deleted and its tag is never
  reused.
- ``successor`` is allowed only on a retired posture: the id
  of the posture that replaces it. It must name a posture in
  the same registry, must not name the posture itself, and
  successor chains must not cycle. A chain may pass through
  further retired postures; where it ends is the posture a
  still-tagged project is re-categorized to.
- ``note`` is optional and is carried, not interpreted.

Tagging format (declared here; the loader enforces it exactly):

    {
      "format": "hp-posture-tagging",
      "version": 1,
      "projects": [
        {"project": "example-project-one", "posture": "A"}
      ]
    }

- ``format`` and ``version`` as above, for the tagging shape.
- ``projects`` is a list, possibly empty. Each entry is an
  object with a required ``project`` (a non-empty string with
  no leading or trailing whitespace and no control or zero-width characters,
  at most 128 characters) and a required ``posture`` (a tag,
  held to the tag shape above), plus an optional ``note``.
  No other keys are allowed. Two entries naming the same
  project are refused: a project has exactly one entry, so it
  has exactly one effective posture at a time.
- A ``posture`` value that no registry entry declares is NOT
  a format error. It is a finding, reported by ``check``:
  the tagging parses, and the check says the tag is unknown.

The check, for each project in tagging order, resolves the tag
against the registry and reports one of three outcomes:

- the posture is active: the project, its tag, the posture's id,
  and the posture's ``say`` and ``shelf`` — the effective
  disclosure rule the project sits under;
- the tag is unknown: reported as unknown. The tool never
  guesses which posture an undeclared tag was meant to be;
- the posture is retired: reported as retired, naming the
  successor the registry declares (the end of its chain) when
  one exists. The project's tagging is never silently
  rewritten to the successor: re-categorizing is an operator's
  edit, and the report is what prompts it.

Like the registry it reads, a real tagging file names what an
operator is working on, so it lives where the operator keeps
such data; the registry copy that ships in this repository
(``disclosure-registry.example.json``, beside this file) carries
the schema and obviously fake example entries only.

The stamp. A record that concerns a project — a log line, a
run record, a result envelope, a ledger entry — carries the
project's posture as a single token:

    hp-posture-<version>-<posture id>

as in ``hp-posture-1-named-only``. The stamp carries the
posture's stable id, never its tag (a tag may be re-lettered;
an id may not), and the registry format version it was minted
under, so a reader holding a registry of another version
fails closed instead of misreading. ``format_stamp`` mints a
stamp from a loaded registry, refusing an unknown id and a
retired posture — new records are not stamped with a posture
that has been replaced. ``parse_stamp`` reads a stamp
strictly: the whole string, exactly this shape, a canonical
version (no zero, no leading zeros), and an id inside the id
grammar. ``validate_stamp`` resolves a stamp against a
registry and raises on a version mismatch or an unknown id;
a stamp naming a retired posture still validates, because
old records stay readable, and the posture's status says
what it is.

    python3 runner/tools/disclosure.py validate --registry R.json
    python3 runner/tools/disclosure.py check --registry R.json T.json

Exit codes: 0 = the registry is valid, or every project in the
tagging resolves to an active posture; 1 = findings (an unknown
tag, or a project still assigned a retired posture); 2 = the
registry or an input could not be read or is malformed.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import NamedTuple

REGISTRY_FORMAT = "hp-posture-registry"
REGISTRY_VERSION = 1
TAGGING_FORMAT = "hp-posture-tagging"
TAGGING_VERSION = 1

STATUSES = ("active", "retired")

MAX_ID_LENGTH = 64
MAX_TAG_LENGTH = 16
MAX_PROJECT_LENGTH = 128

_REGISTRY_KEYS = frozenset({"format", "version", "postures"})
_POSTURE_KEYS = frozenset(
    {"id", "tag", "say", "shelf", "status", "successor", "note"})
_TAGGING_KEYS = frozenset({"format", "version", "projects"})
_ASSIGNMENT_KEYS = frozenset({"project", "posture", "note"})

_ID_SHAPE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

STAMP_PREFIX = "hp-posture-"
_STAMP_SHAPE = re.compile(r"hp-posture-([0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)")


class RegistryError(ValueError):
    """The posture registry is unreadable or outside the format."""


class TaggingError(ValueError):
    """The tagging file is unreadable or outside the format."""


class StampError(ValueError):
    """A posture stamp is malformed, or does not resolve."""


class Posture(NamedTuple):
    """One declared posture: what its tag permits, and where."""

    id: str
    tag: str
    say: str
    shelf: str
    status: str = "active"
    successor: str | None = None
    note: str | None = None


class Registry(NamedTuple):
    """A validated registry: the postures, with lookups."""

    postures: tuple

    def by_id(self, pid):
        """The Posture with id `pid`, or None."""
        for posture in self.postures:
            if posture.id == pid:
                return posture
        return None

    def by_tag(self, tag):
        """The Posture carrying `tag`, or None."""
        for posture in self.postures:
            if posture.tag == tag:
                return posture
        return None

    def successor_of(self, posture):
        """The active Posture at the end of `posture`'s successor
        chain, or None when the chain ends at a retired posture
        that declares no successor."""
        seen = set()
        current = posture
        while current is not None and current.status == "retired":
            if current.id in seen:  # refused at load; belt and braces
                return None
            seen.add(current.id)
            if current.successor is None:
                return None
            current = self.by_id(current.successor)
        return current


class Assignment(NamedTuple):
    """One project's categorization: its id and posture tag."""

    project: str
    posture: str
    note: str | None = None


class Tagging(NamedTuple):
    """A validated tagging file: the assignments, in file order."""

    assignments: tuple


class Resolution(NamedTuple):
    """One project's outcome under a registry.

    `problem` is None when the tag resolves to an active
    posture, "unknown-tag" when no posture declares the tag,
    and "retired" when the posture it names is retired.
    """

    project: str
    tag: str
    posture: Posture | None
    problem: str | None


class Stamp(NamedTuple):
    """A parsed log stamp: the registry version it was minted
    under, and the posture id it names."""

    version: int
    posture_id: str


_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\u2060\ufeff")


def _has_control(text):
    # Control characters, and the zero-width characters the name
    # guard's normalization removes: invisible in a declaration,
    # and a confusable wherever one slips in.
    return any(ord(ch) < 0x20 or ord(ch) == 0x7F or ch in _ZERO_WIDTH
               for ch in text)


def _check_text(value, where, field, error):
    if not isinstance(value, str):
        raise error("%s: %r must be a str, not %s"
                    % (where, field, type(value).__name__))
    if not value:
        raise error("%s: %r must not be empty" % (where, field))
    if value != value.strip():
        raise error("%s: %r %r has leading or trailing whitespace; "
                    "declare the value itself" % (where, field, value))
    if _has_control(value):
        raise error("%s: %r %r contains a control or zero-width character"
                    % (where, field, value))
    return value


def _check_id(value, where):
    _check_text(value, where, "id", RegistryError)
    if len(value) > MAX_ID_LENGTH:
        raise RegistryError("%s: 'id' is %d characters; the cap is %d"
                            % (where, len(value), MAX_ID_LENGTH))
    if not _ID_SHAPE.fullmatch(value):
        raise RegistryError(
            "%s: 'id' %r is not lowercase [a-z0-9] segments joined "
            "by single dashes" % (where, value))
    return value


def _check_tag(value, where, error):
    if not isinstance(value, str):
        raise error("%s: 'tag' must be a str, not %s"
                    % (where, type(value).__name__))
    if not value:
        raise error("%s: 'tag' must not be empty" % where)
    if len(value) > MAX_TAG_LENGTH:
        raise error("%s: 'tag' is %d characters; the cap is %d"
                    % (where, len(value), MAX_TAG_LENGTH))
    if any(ch.isspace() for ch in value) or _has_control(value):
        raise error("%s: 'tag' %r contains whitespace or a control "
                    "character; a tag is a single token" % (where, value))
    return value


def _check_posture_entry(entry, where):
    if not isinstance(entry, dict):
        raise RegistryError("%s: a posture entry must be an object, "
                            "not %s" % (where, type(entry).__name__))
    unknown = sorted(set(entry) - _POSTURE_KEYS)
    if unknown:
        raise RegistryError("%s: unknown key(s) %s; allowed keys are %s"
                            % (where, ", ".join(unknown),
                               ", ".join(sorted(_POSTURE_KEYS))))
    for field in ("id", "tag", "say", "shelf"):
        if field not in entry:
            raise RegistryError("%s: a posture entry needs %r"
                                % (where, field))
    pid = _check_id(entry["id"], where)
    tag = _check_tag(entry["tag"], where, RegistryError)
    say = _check_text(entry["say"], where, "say", RegistryError)
    shelf = _check_text(entry["shelf"], where, "shelf", RegistryError)
    status = entry.get("status", "active")
    if status not in STATUSES:
        raise RegistryError("%s: 'status' must be one of %s, not %r"
                            % (where, ", ".join(STATUSES), status))
    successor = entry.get("successor")
    if successor is not None:
        if status != "retired":
            raise RegistryError(
                "%s: 'successor' is declared only on a retired "
                "posture; this one is %r" % (where, status))
        _check_id(successor, where)
    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        raise RegistryError("%s: 'note' must be a str, not %s"
                            % (where, type(note).__name__))
    return Posture(pid, tag, say, shelf, status, successor, note)


def parse_registry(data):
    """A Registry for parsed JSON `data`, held to the declared format.

    RegistryError names the first way `data` falls outside the
    format; nothing is guessed at and nothing is skipped.
    """
    if not isinstance(data, dict):
        raise RegistryError("the registry must be a JSON object, not %s"
                            % type(data).__name__)
    unknown = sorted(set(data) - _REGISTRY_KEYS)
    if unknown:
        raise RegistryError("unknown key(s) %s; allowed keys are %s"
                            % (", ".join(unknown),
                               ", ".join(sorted(_REGISTRY_KEYS))))
    if data.get("format") != REGISTRY_FORMAT:
        raise RegistryError("'format' must be %r, not %r"
                            % (REGISTRY_FORMAT, data.get("format")))
    version = data.get("version")
    if (isinstance(version, bool) or not isinstance(version, int)
            or version != REGISTRY_VERSION):
        raise RegistryError("'version' must be %d, not %r"
                            % (REGISTRY_VERSION, version))
    if "postures" not in data:
        raise RegistryError("the registry needs a 'postures' list "
                            "(an empty one is a valid registry)")
    raw = data["postures"]
    if not isinstance(raw, list):
        raise RegistryError("'postures' must be a list, not %s"
                            % type(raw).__name__)
    postures = []
    ids = set()
    tags = set()
    folded = set()
    for i, entry in enumerate(raw):
        posture = _check_posture_entry(entry, "postures[%d]" % i)
        if posture.id in ids:
            raise RegistryError("postures[%d]: duplicate id %r"
                                % (i, posture.id))
        ids.add(posture.id)
        if posture.tag in tags:
            raise RegistryError("postures[%d]: duplicate tag %r"
                                % (i, posture.tag))
        if posture.tag.casefold() in folded:
            raise RegistryError(
                "postures[%d]: tag %r differs only in case from an "
                "earlier tag; tags that near each other will be "
                "mistyped onto the wrong project" % (i, posture.tag))
        tags.add(posture.tag)
        folded.add(posture.tag.casefold())
        postures.append(posture)
    registry = Registry(tuple(postures))
    for posture in postures:
        if posture.successor is None:
            continue
        if posture.successor == posture.id:
            raise RegistryError(
                "posture %r: 'successor' names the posture itself"
                % posture.id)
        if registry.by_id(posture.successor) is None:
            raise RegistryError(
                "posture %r: 'successor' %r is not a posture in "
                "this registry" % (posture.id, posture.successor))
    for posture in postures:
        seen = {posture.id}
        current = posture
        while current.successor is not None:
            current = registry.by_id(current.successor)
            if current.id in seen:
                raise RegistryError(
                    "posture %r: the successor chain cycles at %r"
                    % (posture.id, current.id))
            seen.add(current.id)
    return registry


def _load_json(path, error, what):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise error("cannot read %s %s: %s" % (what, path, exc))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise error("%s %s is not valid JSON: %s" % (what, path, exc))


def load_registry(path):
    """The Registry stored at `path`; RegistryError on any failure."""
    return parse_registry(_load_json(path, RegistryError, "registry"))


def _check_assignment(entry, where):
    if not isinstance(entry, dict):
        raise TaggingError("%s: a project entry must be an object, "
                           "not %s" % (where, type(entry).__name__))
    unknown = sorted(set(entry) - _ASSIGNMENT_KEYS)
    if unknown:
        raise TaggingError("%s: unknown key(s) %s; allowed keys are %s"
                           % (where, ", ".join(unknown),
                              ", ".join(sorted(_ASSIGNMENT_KEYS))))
    for field in ("project", "posture"):
        if field not in entry:
            raise TaggingError("%s: a project entry needs %r"
                               % (where, field))
    project = _check_text(entry["project"], where, "project",
                          TaggingError)
    if len(project) > MAX_PROJECT_LENGTH:
        raise TaggingError("%s: 'project' is %d characters; the cap "
                           "is %d" % (where, len(project),
                                      MAX_PROJECT_LENGTH))
    tag = _check_tag(entry["posture"], where, TaggingError)
    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        raise TaggingError("%s: 'note' must be a str, not %s"
                           % (where, type(note).__name__))
    return Assignment(project, tag, note)


def parse_tagging(data):
    """A Tagging for parsed JSON `data`, held to the declared format.

    TaggingError names the first way `data` falls outside the
    format. Whether a tag exists is the registry's business, not
    the format's: an undeclared tag parses here and is reported
    by check_tagging.
    """
    if not isinstance(data, dict):
        raise TaggingError("the tagging must be a JSON object, not %s"
                           % type(data).__name__)
    unknown = sorted(set(data) - _TAGGING_KEYS)
    if unknown:
        raise TaggingError("unknown key(s) %s; allowed keys are %s"
                           % (", ".join(unknown),
                              ", ".join(sorted(_TAGGING_KEYS))))
    if data.get("format") != TAGGING_FORMAT:
        raise TaggingError("'format' must be %r, not %r"
                           % (TAGGING_FORMAT, data.get("format")))
    version = data.get("version")
    if (isinstance(version, bool) or not isinstance(version, int)
            or version != TAGGING_VERSION):
        raise TaggingError("'version' must be %d, not %r"
                           % (TAGGING_VERSION, version))
    if "projects" not in data:
        raise TaggingError("the tagging needs a 'projects' list "
                           "(an empty one is a valid tagging)")
    raw = data["projects"]
    if not isinstance(raw, list):
        raise TaggingError("'projects' must be a list, not %s"
                           % type(raw).__name__)
    assignments = []
    seen = set()
    for i, entry in enumerate(raw):
        assignment = _check_assignment(entry, "projects[%d]" % i)
        if assignment.project in seen:
            raise TaggingError(
                "projects[%d]: duplicate entry for project %r; a "
                "project has exactly one posture at a time — edit "
                "its entry to re-categorize it"
                % (i, assignment.project))
        seen.add(assignment.project)
        assignments.append(assignment)
    return Tagging(tuple(assignments))


def load_tagging(path):
    """The Tagging stored at `path`; TaggingError on any failure."""
    return parse_tagging(_load_json(path, TaggingError, "tagging"))


def check_tagging(registry, tagging):
    """Every project's Resolution under `registry`, in tagging order."""
    if not isinstance(registry, Registry):
        raise TypeError("registry must be a Registry, not %s"
                        % type(registry).__name__)
    if not isinstance(tagging, Tagging):
        raise TypeError("tagging must be a Tagging, not %s"
                        % type(tagging).__name__)
    resolutions = []
    for assignment in tagging.assignments:
        posture = registry.by_tag(assignment.posture)
        if posture is None:
            resolutions.append(Resolution(assignment.project,
                                          assignment.posture,
                                          None, "unknown-tag"))
        elif posture.status == "retired":
            resolutions.append(Resolution(assignment.project,
                                          assignment.posture,
                                          posture, "retired"))
        else:
            resolutions.append(Resolution(assignment.project,
                                          assignment.posture,
                                          posture, None))
    return resolutions


def format_stamp(registry, posture_id):
    """The stamp for `posture_id` under `registry`, as a str.

    Refuses an id the registry does not declare, and a retired
    posture: new records are not stamped with a posture that
    has been replaced.
    """
    if not isinstance(registry, Registry):
        raise TypeError("registry must be a Registry, not %s"
                        % type(registry).__name__)
    posture = (registry.by_id(posture_id)
               if isinstance(posture_id, str) else None)
    if posture is None:
        raise StampError("no posture with id %r in the registry"
                         % (posture_id,))
    if posture.status == "retired":
        raise StampError("posture %r is retired; new records are "
                         "not stamped with it" % (posture_id,))
    return "%s%d-%s" % (STAMP_PREFIX, REGISTRY_VERSION, posture.id)


def parse_stamp(text):
    """Parse a stamp strictly: the whole string, exactly the
    declared shape. Anything else raises StampError."""
    if not isinstance(text, str):
        raise StampError("a stamp must be a str, not %s"
                         % type(text).__name__)
    match = _STAMP_SHAPE.fullmatch(text)
    if match is None:
        raise StampError("%r is not a posture stamp "
                         "(hp-posture-<version>-<posture id>)" % (text,))
    digits, pid = match.groups()
    if len(digits) > 1 and digits.startswith("0"):
        raise StampError("%r: version %r has a leading zero; "
                         "versions are canonical" % (text, digits))
    version = int(digits)
    if version < 1:
        raise StampError("%r: version must be at least 1" % (text,))
    if len(pid) > MAX_ID_LENGTH:
        raise StampError("%r: 'id' is %d characters; the cap is %d"
                         % (text, len(pid), MAX_ID_LENGTH))
    return Stamp(version, pid)


def validate_stamp(registry, stamp):
    """Resolve `stamp` (a Stamp, or a str to parse) against
    `registry`, returning its Posture.

    Fails closed: a version other than the registry format's
    own, or an id the registry does not declare, raises
    StampError. A retired posture resolves — old records stay
    readable — and its status says what it is.
    """
    if not isinstance(registry, Registry):
        raise TypeError("registry must be a Registry, not %s"
                        % type(registry).__name__)
    if isinstance(stamp, str):
        stamp = parse_stamp(stamp)
    if not isinstance(stamp, Stamp):
        raise TypeError("stamp must be a Stamp or a str, not %s"
                        % type(stamp).__name__)
    if stamp.version != REGISTRY_VERSION:
        raise StampError("stamp version %d does not match the "
                         "registry format version %d"
                         % (stamp.version, REGISTRY_VERSION))
    posture = registry.by_id(stamp.posture_id)
    if posture is None:
        raise StampError("no posture with id %r in the registry"
                         % (stamp.posture_id,))
    return posture


def _report(where, registry, resolutions, out):
    problems = 0
    for r in resolutions:
        if r.problem == "unknown-tag":
            problems += 1
            print("%s: %s: tag %r -> UNKNOWN TAG (not declared in "
                  "the registry)" % (where, r.project, r.tag), file=out)
        elif r.problem == "retired":
            problems += 1
            successor = registry.successor_of(r.posture)
            if successor is not None:
                tail = "successor: %s" % successor.id
            else:
                tail = "no successor declared"
            print("%s: %s: tag %r -> posture %s is RETIRED (%s)"
                  % (where, r.project, r.tag, r.posture.id, tail),
                  file=out)
        else:
            print("%s: %s: tag %r -> posture %s (active): say: %s; "
                  "shelf: %s" % (where, r.project, r.tag, r.posture.id,
                                 r.posture.say, r.posture.shelf),
                  file=out)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_val = sub.add_parser("validate",
                           help="check a registry against the format")
    p_val.add_argument("--registry", required=True)
    p_check = sub.add_parser("check",
                             help="resolve a tagging file's projects "
                                  "against a registry")
    p_check.add_argument("--registry", required=True)
    p_check.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    try:
        registry = load_registry(args.registry)
    except RegistryError as exc:
        print("disclosure: %s" % exc, file=sys.stderr)
        return 2

    if args.cmd == "validate":
        active = sum(1 for p in registry.postures
                     if p.status == "active")
        print("valid: %d posture(s), %d active, %d retired"
              % (len(registry.postures), active,
                 len(registry.postures) - active))
        return 0

    problems = 0
    for path in args.files:
        try:
            tagging = load_tagging(path)
        except TaggingError as exc:
            print("disclosure: %s" % exc, file=sys.stderr)
            return 2
        problems += _report(path, registry,
                            check_tagging(registry, tagging), sys.stdout)
    if problems:
        print("disclosure: %d problem(s)" % problems, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
