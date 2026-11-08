#!/usr/bin/env python3
"""Scan text for declared protected terms (the name guard).

The suite's security policy (SECURITY.md, "Spillage: when private
material is published") rests on a two-shelf boundary: a public
shelf (this repository and everything published from it) and a
private shelf (what is being examined, engagement and case records,
unfixed findings, crash data, clients' names and systems). A code
name that lives only in conversation protects nothing: no machine
can scan for a string nobody declared. This tool is the declaration
made mechanical. An operator writes the protected terms down in a
registry file, in the format declared below, and the guard scans
candidate public text — files, standard input, a change about to be
committed — and reports every place a declared term appears.

The registry NEVER lives in the repository. A registry names the
very material the private shelf exists to protect, so it is itself
private-shelf material: kept beside the private notes, readable
only by the operator, and handed to this tool by path. The copy of
the format that ships here (``nameguard-registry.example.json``,
beside this file) carries the schema and obviously fake example
entries only, so the format can be read, tested, and adopted
without anything real crossing the boundary.

Registry format (declared here; the loader enforces it exactly):

    {
      "format": "hp-nameguard-registry",
      "version": 1,
      "private_refs": "off",
      "terms": [
        {"term": "Project Fake Lantern",
         "match": "word", "case": "fold", "marking": 2,
         "note": "what this term is, in the operator's own words"}
      ]
    }

- ``format`` must be the string above and ``version`` the integer
  1. Anything else is refused: a registry in a shape this tool does
  not know is a registry it must not guess at.
- ``terms`` is a list, possibly empty. Each entry is an object with
  a required ``term`` (a non-empty string with no leading or
  trailing whitespace and no control characters) and optional
  ``match``, ``case``, ``marking``, and ``note``. No other keys are
  allowed, at any level: an unrecognized key is almost always a
  typo, and a typo in a guard's registry must fail loudly rather
  than silently unscanned. Two entries with the same term, match
  rule, and case rule are a duplicate and are refused.
- ``marking`` is the sensitivity marking of the term itself, an
  integer 0-3 in the cs_office scheme (see runner/tools/codename.py);
  it is carried into the report so a finding says how private the
  term that crossed is. It does not change matching.
- ``private_refs`` is ``"off"`` (the default) or ``"flag"``. At
  ``"flag"``, the guard also reports any syntactically valid
  code-name reference (the hp<marking>-<guid> shape declared by
  runner/tools/codename.py) whose marking is 2 or 3: those
  references are private-shelf material in themselves, and no real
  one belongs in public text. References at markings 0 and 1 are
  public by design and are never reported by this rule.

Matching rules (explicit, and the same for every operator):

- Normalization runs first, over both the text and every term:
  Unicode NFKC (fullwidth and compatibility forms fold to their
  ordinary equivalents), zero-width characters are removed
  (U+200B, U+200C, U+200D, U+2060, U+FEFF), and a fixed table of
  lookalike letters is folded to the ASCII letter it imitates
  (Cyrillic а е о р с у х ѕ і ј һ and capitals, Greek ο ρ χ and
  capitals). A term written with a lookalike letter is the term;
  treating it as a different string is how a scanner gets walked
  around. The table is the one in ``_LOOKALIKES`` below — fixed in
  code, not configurable, so two operators scanning the same text
  get the same answer.
- ``case: "fold"`` (the default) compares with Unicode casefolding
  applied after normalization. ``case: "exact"`` compares the
  normalized strings as they stand. Normalization applies under
  both: "exact" governs case only.
- ``match: "word"`` (the default) requires the term to stand as
  its own word: where the term begins with a word character, the
  character before it must not be one; where it ends with a word
  character, the character after it must not be one. Word
  characters are the Unicode word characters (letters, digits,
  underscore). Punctuation, whitespace, and string edges are
  boundaries, so a term wrapped in punctuation — quoted, bracketed,
  dashed — still matches. A term whose edge is itself punctuation
  takes no boundary condition on that edge.
- ``match: "substring"`` drops the boundary conditions: the term
  matches anywhere it occurs, including inside a larger word. For
  terms that are fragments by nature — a host name inside a longer
  address, a build string — and noisy by the same nature.
- Whitespace inside a multi-word term matches any run of
  whitespace, including a line break: a phrase split across two
  lines of a file is still the phrase. A single word split by a
  line break is not rejoined; hyphenation is a writing decision,
  not an encoding trick, and the guard does not guess at it.

Findings are reported as where (the file path, or ``<stdin>``),
the 1-based line and column of the match, and the declared term.
Line and column are counted in the normalized text; normalization
never adds or removes a line break, so line numbers are the
file's own. The matched text itself is never printed: the report
names the declared term, and the place, and nothing else crosses
into a log.

Files are read as UTF-8; undecodable bytes are replaced, so a
binary file handed to the guard scans as its decodable text rather
than crashing the scan.

    python3 runner/tools/nameguard.py validate --registry R.json
    python3 runner/tools/nameguard.py check --registry R.json FILE...
    python3 runner/tools/nameguard.py check --registry R.json --stdin

Exit codes: 0 = clean (or the registry is valid), 1 = findings,
2 = the registry or an input could not be read or is malformed.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from typing import NamedTuple

REGISTRY_FORMAT = "hp-nameguard-registry"
REGISTRY_VERSION = 1

MATCH_RULES = ("word", "substring")
CASE_RULES = ("fold", "exact")
PRIVATE_REF_RULES = ("off", "flag")
MARKINGS = (0, 1, 2, 3)

_TOP_KEYS = frozenset({"format", "version", "private_refs", "terms"})
_TERM_KEYS = frozenset({"term", "match", "case", "marking", "note"})

_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\u2060\ufeff")

# Lookalike letters folded to the ASCII letter they imitate. Fixed
# in code on purpose: the table is part of the matching rules, and
# two operators must scan identically. Cyrillic first, then Greek.
_LOOKALIKES = {
    # Cyrillic small letters: а е о р с у х ѕ і ј һ
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p",
    "\u0441": "c", "\u0443": "y", "\u0445": "x", "\u0455": "s",
    "\u0456": "i", "\u0458": "j", "\u04bb": "h",
    # Cyrillic capital letters: А В Е К М Н О Р С Т Х У (У folds to Y)
    "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K",
    "\u041c": "M", "\u041d": "H", "\u041e": "O", "\u0420": "P",
    "\u0421": "C", "\u0422": "T", "\u0425": "X", "\u0423": "Y",
    # Greek letters: ο ρ χ and capitals Ο Ρ Χ
    "\u03bf": "o", "\u03c1": "p", "\u03c7": "x",
    "\u039f": "O", "\u03a1": "P", "\u03a7": "X",
}

# The code-name reference shape, mirroring the grammar declared in
# runner/tools/codename.py (kept as a token finder here; validity is
# judged by the same strict rules codename.parse applies, restated
# in _REF_TOKEN's checks in scan_text's private-ref pass).
_GUID_SHAPE = (r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}"
               r"-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_REF_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])hp([0-3])-(%s)(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?"
    r"(?![A-Za-z0-9-])" % _GUID_SHAPE)

_WORD_CHAR = re.compile(r"\w")


class RegistryError(ValueError):
    """The registry is unreadable or outside the declared format."""


class Term(NamedTuple):
    """One declared protected term and its matching rules."""

    term: str
    match: str = "word"
    case: str = "fold"
    marking: int | None = None
    note: str | None = None


class Registry(NamedTuple):
    """A validated registry: the terms and the private-ref rule."""

    terms: tuple
    private_refs: str = "off"


class Finding(NamedTuple):
    """One match: what was declared, and where it was found."""

    term: str
    line: int
    column: int
    marking: int | None = None
    kind: str = "term"


def normalize(text):
    """The normalization every comparison runs under.

    NFKC, zero-width characters removed, lookalike letters folded
    to ASCII. Never adds or removes a line break.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str, not %s"
                        % type(text).__name__)
    text = unicodedata.normalize("NFKC", text)
    out = []
    for ch in text:
        if ch in _ZERO_WIDTH:
            continue
        out.append(_LOOKALIKES.get(ch, ch))
    return "".join(out)


def _check_term_entry(entry, where):
    if not isinstance(entry, dict):
        raise RegistryError("%s: a term entry must be an object, not %s"
                            % (where, type(entry).__name__))
    unknown = sorted(set(entry) - _TERM_KEYS)
    if unknown:
        raise RegistryError("%s: unknown key(s) %s; allowed keys are %s"
                            % (where, ", ".join(unknown),
                               ", ".join(sorted(_TERM_KEYS))))
    if "term" not in entry:
        raise RegistryError("%s: a term entry needs a 'term'" % where)
    term = entry["term"]
    if not isinstance(term, str):
        raise RegistryError("%s: 'term' must be a str, not %s"
                            % (where, type(term).__name__))
    if not term:
        raise RegistryError("%s: 'term' must not be empty" % where)
    if term != term.strip():
        raise RegistryError(
            "%s: 'term' %r has leading or trailing whitespace; "
            "declare the term itself" % (where, term))
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in term):
        raise RegistryError(
            "%s: 'term' %r contains a control character; whitespace "
            "inside a term is a plain space" % (where, term))
    match = entry.get("match", "word")
    if match not in MATCH_RULES:
        raise RegistryError("%s: 'match' must be one of %s, not %r"
                            % (where, ", ".join(MATCH_RULES), match))
    case = entry.get("case", "fold")
    if case not in CASE_RULES:
        raise RegistryError("%s: 'case' must be one of %s, not %r"
                            % (where, ", ".join(CASE_RULES), case))
    marking = entry.get("marking")
    if marking is not None:
        if isinstance(marking, bool) or not isinstance(marking, int):
            raise RegistryError("%s: 'marking' must be an int, not %s"
                                % (where, type(marking).__name__))
        if marking not in MARKINGS:
            raise RegistryError("%s: 'marking' must be one of %s, not %r"
                                % (where,
                                   ", ".join(str(m) for m in MARKINGS),
                                   marking))
    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        raise RegistryError("%s: 'note' must be a str, not %s"
                            % (where, type(note).__name__))
    return Term(term, match, case, marking, note)


def parse_registry(data):
    """A Registry for parsed JSON `data`, held to the declared format.

    RegistryError names the first way `data` falls outside the
    format; nothing is guessed at and nothing is skipped.
    """
    if not isinstance(data, dict):
        raise RegistryError("the registry must be a JSON object, not %s"
                            % type(data).__name__)
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
    private_refs = data.get("private_refs", "off")
    if private_refs not in PRIVATE_REF_RULES:
        raise RegistryError("'private_refs' must be one of %s, not %r"
                            % (", ".join(PRIVATE_REF_RULES), private_refs))
    if "terms" not in data:
        raise RegistryError("the registry needs a 'terms' list "
                            "(an empty one is a valid registry)")
    raw_terms = data["terms"]
    if not isinstance(raw_terms, list):
        raise RegistryError("'terms' must be a list, not %s"
                            % type(raw_terms).__name__)
    terms = []
    seen = set()
    for i, entry in enumerate(raw_terms):
        term = _check_term_entry(entry, "terms[%d]" % i)
        key = (term.term, term.match, term.case)
        if key in seen:
            raise RegistryError(
                "terms[%d]: duplicate entry for term %r (match %r, "
                "case %r)" % (i, term.term, term.match, term.case))
        seen.add(key)
        terms.append(term)
    return Registry(tuple(terms), private_refs)


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


def _fold(text, case):
    return text.casefold() if case == "fold" else text


def _term_pattern(term):
    """The compiled pattern for one Term, under the matching rules."""
    prepared = _fold(normalize(term.term), term.case)
    body = r"\s+".join(re.escape(part) for part in prepared.split())
    if term.match == "substring":
        return re.compile(body)
    left = r"(?<!\w)" if _WORD_CHAR.match(prepared[0]) else ""
    right = r"(?!\w)" if _WORD_CHAR.match(prepared[-1]) else ""
    return re.compile(left + body + right)


def _line_col(text, offset):
    line = text.count("\n", 0, offset) + 1
    col = offset - text.rfind("\n", 0, offset)
    return line, col


def scan_text(text, registry):
    """Every Finding in `text` under `registry`, in reading order.

    Findings are sorted by line, then column, then term. The text is
    normalized once; each term is searched under its own rules.
    """
    if not isinstance(registry, Registry):
        raise TypeError("registry must be a Registry, not %s"
                        % type(registry).__name__)
    normed = normalize(text)
    findings = []
    for term in registry.terms:
        haystack = _fold(normed, term.case)
        for m in _term_pattern(term).finditer(haystack):
            line, col = _line_col(haystack, m.start())
            findings.append(Finding(term.term, line, col,
                                    term.marking, "term"))
    if registry.private_refs == "flag":
        base_len = len("hp0-") + 36  # marking prefix + the GUID
        for m in _REF_TOKEN.finditer(normed):
            marking = int(m.group(1))
            if marking not in (2, 3):
                continue
            whole = m.group(0)
            # codename.py caps a whole reference at 128 characters
            # and a sub-name at 32; a longer string in this shape is
            # not a reference and is not reported as one.
            sub = whole[base_len + 1:] if len(whole) > base_len else None
            if len(whole) > 128 or (sub is not None and len(sub) > 32):
                continue
            line, col = _line_col(normed, m.start())
            findings.append(Finding("hp%d reference" % marking,
                                    line, col, marking, "private-ref"))
    findings.sort(key=lambda f: (f.line, f.column, f.term))
    return findings


def scan_file(path, registry):
    """Every Finding in the file at `path`, read as UTF-8.

    Undecodable bytes are replaced rather than raising, so a binary
    file scans as its decodable text. OSError propagates.
    """
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", errors="replace")
    return scan_text(text, registry)


def _report(where, findings, out):
    for f in findings:
        if f.kind == "private-ref":
            print("%s:%d:%d: private code-name reference (marking hp%d)"
                  % (where, f.line, f.column, f.marking), file=out)
        elif f.marking is not None:
            print("%s:%d:%d: protected term %r (marking hp%d)"
                  % (where, f.line, f.column, f.term, f.marking),
                  file=out)
        else:
            print("%s:%d:%d: protected term %r"
                  % (where, f.line, f.column, f.term), file=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_val = sub.add_parser("validate",
                           help="check a registry against the format")
    p_val.add_argument("--registry", required=True)
    p_check = sub.add_parser("check", help="scan files or stdin")
    p_check.add_argument("--registry", required=True)
    p_check.add_argument("--stdin", action="store_true",
                         help="scan standard input instead of files")
    p_check.add_argument("files", nargs="*")
    args = ap.parse_args(argv)

    try:
        registry = load_registry(args.registry)
    except RegistryError as exc:
        print("nameguard: %s" % exc, file=sys.stderr)
        return 2

    if args.cmd == "validate":
        print("valid: %d term(s), private_refs=%s"
              % (len(registry.terms), registry.private_refs))
        return 0

    if args.stdin and args.files:
        print("nameguard: --stdin takes no files", file=sys.stderr)
        return 2
    if not args.stdin and not args.files:
        print("nameguard: nothing to scan: name files or pass --stdin",
              file=sys.stderr)
        return 2

    total = 0
    if args.stdin:
        findings = scan_text(sys.stdin.read(), registry)
        _report("<stdin>", findings, sys.stdout)
        total += len(findings)
    for path in args.files:
        try:
            findings = scan_file(path, registry)
        except OSError as exc:
            print("nameguard: cannot read %s: %s" % (path, exc),
                  file=sys.stderr)
            return 2
        _report(path, findings, sys.stdout)
        total += len(findings)
    if total:
        print("nameguard: %d finding(s)" % total, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
