#!/usr/bin/env python3
"""Assemble and check the release gate's candidate record.

# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

The design lives in docs/infrastructure-documents/project/
release-gate.md; this tool is its mechanical half. The desk's one
hard gate is the release gate (desk.md, Gate 5), and the gate
this project adds there is a human one: the conductor reads one
short checklist over one finished candidate and signs, or does
not sign, before the tag is cut. The checklist's gathering half
is mechanical, and this tool does it:

- ``checklist`` reads a git range (the previous release commit
  to the candidate's release commit), lists its content commits,
  classifies every changed path against the seven review classes
  declared below, and prints the candidate record: the ten-item
  checklist in reading order, the classes the range touched, and
  the sign-off block with the identity fields already filled.
- ``signoff-template`` prints just the sign-off block, for a
  record being assembled by hand.
- ``check-signoff`` validates a filled record and fails closed:
  fields present exactly once and in shape, the version a full
  four components, the commit a full SHA, the candidate form in
  agreement with the verdict form, and one reviewed line for
  every class the record's own checklist declares touched — and
  none for a class it does not, the copy-paste signature of a
  record filled from the previous release's.

The classes (protocol, execution, key handling, confinement,
job-user behavior, extension loading, disclosure controls) name
the change families an outside peer review held must have
explicit human review before release. The registry below
(``hp-release-gate-registry``) declares their path families in
code, in the discipline of runner/tools/approvalguard.py: exact
paths, path prefixes, and one file-name rule. A path in two
families asks for both reviews; over-inclusion is intended, and
the registry errs that way on purpose.

Two measured corrections shape the classification (the release
gate document carries the measurement):

- Release commits are never classified. A release commit carries
  the version carriers — pyproject.toml, runner/_version.py,
  runner/ops/install.py, the changelog and the version-pinning
  test — so classifying one flags key handling on every release
  there will ever be. Commits whose subject carries the release
  shape (``release: ``) are listed as release machinery and
  skipped; every other commit in the range is a content commit.
- A slot-only change is a figure refresh, not a class event.
  Three files carry generated figure slots (the SLOT_FILES of
  runner/tools/refresh_figures.py: AGENTS.md, PROTOCOL.md and
  docs/steady/fuzzing.md), and the trains' refresh commits refill
  those slots mechanically. For those files the tool compares the
  commit's removed and added lines with every slot's value
  masked: if the masked lines agree, the path is recorded as a
  figure refresh and takes no class; any other changed line
  gives the file its normal classes.

Tests are not classified by path: a test rides with its subject
and stands in the record's per-commit list. Documentation
outside the protocol's own documents is likewise unclassified.
Both still appear on the checklist, where the conductor sees
them; the classes name behaviour of the running system.

Like the approval guard and the name guard, this tool is
invoked, never ambient: it runs when an operator — or their
agent — runs it, and NOTHING here wires it into a hook, a
workflow, or a release train. The trains run exactly as they did
before it existed. Enforcement — a train refusing a tag without
a valid signed record — is a later phase, at the conductor's
word, and is deliberately not built here.
"""

import argparse
import re
import subprocess
import sys

# ------------------------------------------------------------------
# The class registry, declared in code (hp-release-gate-registry).
# Classes are named exactly as the design names them, in the
# order the checklist prints them.
# ------------------------------------------------------------------

CLASS_ORDER = (
    "protocol",
    "execution",
    "key handling",
    "confinement",
    "job-user behavior",
    "extension loading",
    "disclosure controls",
)

# Exact paths: the whole file belongs to the named classes.
EXACT_RULES = {
    "PROTOCOL.md": ("protocol",),
    "runner/runner.py": ("execution",),
    "runner/ops/exec.py": ("execution",),
    "runner/ops/main.py": ("execution",),
    "runner/ops/startup.py": ("execution",),
    "runner/ops/poll.py": ("execution",),
    "runner/ops/handlers.py": ("execution",),
    "runner/ops/cli.py": ("execution",),
    "runner/ops/install.py": ("key handling",),
    "runner/wire/jobcrypto.py": ("key handling", "protocol"),
    "runner/wire/mlkem.py": ("key handling", "protocol"),
    "runner/guard/confval.py": ("key handling",),
    "runner/config.example.json": ("key handling",),
    "runner/guard/sandbox.py": ("confinement",),
    "runner/ops/posture.py": ("confinement", "job-user behavior"),
    "docs/steady/security/homing_pigeon.te": ("confinement",),
    "docs/steady/security/homing-pigeon.service": ("confinement",),
    "runner/ops/extensions.py": ("extension loading",),
    "runner/ops/extsources.py": ("extension loading",),
    "runner/guard/extreview.py": ("extension loading",),
    "runner/tools/pin_extension_sources.py": ("extension loading",),
    "runner/guard/security.py": ("disclosure controls",),
    "runner/ops/briefing.py": ("disclosure controls",),
    "runner/tools/make_briefing.py": ("disclosure controls",),
    "runner/tools/disclosure.py": ("disclosure controls",),
}

# Path prefixes: everything under the prefix belongs to the
# named classes.
PREFIX_RULES = (
    ("docs/ietf/", ("protocol",)),
    ("runner/wire/", ("protocol",)),
    ("runner/cloud/", ("key handling",)),
    ("runner/extensions/", ("extension loading",)),
    ("runner/transport_extensions/", ("extension loading",)),
    ("runner/oracle/", ("disclosure controls",)),
)

# File-name rule: a file whose name carries either marker belongs
# to job-user behavior, wherever it lives (the startup gate's
# modules today, the workflow that exercises them, tomorrow's).
JOB_USER_NAME_MARKERS = ("job_user", "job-user")
JOB_USER_CLASS = "job-user behavior"

# Files carrying generated figure slots, mirrored from
# runner/tools/refresh_figures.py's SLOT_FILES: a change confined
# to the slots' values is a figure refresh, not a class event.
SLOT_FILES = (
    "AGENTS.md",
    "PROTOCOL.md",
    "docs/steady/fuzzing.md",
)
SLOT_RE = re.compile(r"<!--hp-fig:([a-z0-9_]+)-->(.*?)<!--/hp-fig-->")

# A release commit's subject carries this shape; such commits are
# release machinery and are never classified.
RELEASE_SUBJECT_RE = re.compile(r"^release: ")

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

VERDICT_SIGNED = "signed"
VERDICT_SIGNED_PROTECTED = "signed (protected candidate)"
VERDICT_NOT_SIGNED = "not signed"
VERDICTS = (VERDICT_SIGNED, VERDICT_SIGNED_PROTECTED, VERDICT_NOT_SIGNED)

CANDIDATE_STANDARD = "standard"
CANDIDATE_PROTECTED = "protected"
CANDIDATE_FORMS = (CANDIDATE_STANDARD, CANDIDATE_PROTECTED)


# ------------------------------------------------------------------
# Classification (pure).
# ------------------------------------------------------------------

def classify_path(path):
    """The review classes a repository path belongs to.

    Exact rules win first, then prefix rules, then the file-name
    rule; a path collects every class any rule gives it. Returns
    the classes as a tuple in the registry's declared order.
    """
    found = set()
    if path in EXACT_RULES:
        found.update(EXACT_RULES[path])
    for prefix, classes in PREFIX_RULES:
        if path.startswith(prefix):
            found.update(classes)
    name = path.rsplit("/", 1)[-1]
    if any(marker in name for marker in JOB_USER_NAME_MARKERS):
        found.add(JOB_USER_CLASS)
    return tuple(c for c in CLASS_ORDER if c in found)


def is_release_subject(subject):
    """True when a commit subject carries the release shape."""
    return bool(RELEASE_SUBJECT_RE.match(subject or ""))


def mask_slots(text):
    """A line with every figure slot's value masked out."""
    return SLOT_RE.sub(lambda m: "<!--hp-fig:%s--><!--/hp-fig-->" % m.group(1),
                       text)


def slot_only_change(removed_lines, added_lines):
    """True when two line sets differ only inside figure slots.

    The masked removed lines and the masked added lines must
    agree as multisets; any line added, dropped, or edited
    outside a slot's value makes the change a real one.
    """
    masked_removed = sorted(mask_slots(line) for line in removed_lines)
    masked_added = sorted(mask_slots(line) for line in added_lines)
    return masked_removed == masked_added


# ------------------------------------------------------------------
# The git front door: a range read into commits and paths.
# ------------------------------------------------------------------

def _git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", repo] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)
    if proc.returncode != 0:
        raise ValueError("git %s failed: %s" % (args[0], proc.stderr.strip()))
    return proc.stdout


def range_commits(repo, base, head):
    """(sha, subject) pairs in base..head, oldest first."""
    out = _git(repo, "log", "--format=%H%x00%s", "%s..%s" % (base, head))
    commits = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\x00")
        commits.append((sha, subject))
    commits.reverse()
    return commits


def commit_paths(repo, sha):
    """The paths one commit changed, in the order git names them."""
    out = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    return [line for line in out.splitlines() if line.strip()]


def commit_diff_lines(repo, sha, path):
    """(removed, added) content lines of one commit at one path."""
    out = _git(repo, "show", "--format=", "--no-ext-diff", sha, "--", path)
    removed, added = [], []
    for line in out.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return removed, added


def classify_commit(repo, sha, paths):
    """(classes, refresh paths) for one content commit.

    A path in a slot-carrying file whose change at this commit is
    confined to the slots' values is a figure refresh and takes
    no class; every other path takes its registry classes.
    """
    classes = set()
    refresh = []
    for path in paths:
        if path in SLOT_FILES:
            removed, added = commit_diff_lines(repo, sha, path)
            if slot_only_change(removed, added):
                refresh.append(path)
                continue
        classes.update(classify_path(path))
    ordered = tuple(c for c in CLASS_ORDER if c in classes)
    return ordered, refresh


def build_candidate(repo, base, head, version, tip=None):
    """The candidate record's data, read from the git range.

    Content commits carry their paths, classes and refresh paths;
    release commits are listed apart as machinery. When tip names
    a commit beyond the candidate, its content commits are the
    deferred set: not in this release, listed with the classes
    they will ask for at their own.
    """
    content, machinery = [], []
    touched = set()
    for sha, subject in range_commits(repo, base, head):
        if is_release_subject(subject):
            machinery.append((sha, subject))
            continue
        paths = commit_paths(repo, sha)
        classes, refresh = classify_commit(repo, sha, paths)
        touched.update(classes)
        content.append({
            "sha": sha, "subject": subject, "paths": paths,
            "classes": classes, "refresh": refresh,
        })
    deferred = []
    if tip and tip != head:
        for sha, subject in range_commits(repo, head, tip):
            if is_release_subject(subject):
                continue
            paths = commit_paths(repo, sha)
            classes, refresh = classify_commit(repo, sha, paths)
            deferred.append({
                "sha": sha, "subject": subject, "paths": paths,
                "classes": classes, "refresh": refresh,
            })
    return {
        "version": version, "base": base, "head": head,
        "tip": tip, "content": content, "machinery": machinery,
        "deferred": deferred,
        "classes_touched": tuple(c for c in CLASS_ORDER if c in touched),
    }


# ------------------------------------------------------------------
# Rendering: the candidate record and the sign-off block.
# ------------------------------------------------------------------

def render_signoff_block(version, release_commit, candidate_form, classes):
    """The sign-off block, identity fields filled, the rest blank."""
    lines = [
        "## Sign-off",
        "",
        "- Version: %s" % version,
        "- Release commit: %s" % release_commit,
        "- Candidate: %s" % candidate_form,
        "- Conductor:",
        "- Date:",
        "- Verdict:",
    ]
    for name in classes:
        lines.append("- Reviewed: %s" % name)
    return "\n".join(lines) + "\n"


def render_checklist(candidate):
    """The full candidate record: checklist, then the sign-off."""
    version = candidate["version"]
    head = candidate["head"]
    protected = bool(candidate["deferred"]) or (
        candidate["tip"] is not None and candidate["tip"] != head)
    form = CANDIDATE_PROTECTED if protected else CANDIDATE_STANDARD
    touched = candidate["classes_touched"]
    out = []
    out.append("# Release candidate record: %s" % version)
    out.append("")
    out.append("Generated by runner/tools/release_gate.py. The design, the")
    out.append("checklist's order and the sign-off's rules stand in")
    out.append("docs/infrastructure-documents/project/release-gate.md.")
    out.append("")
    out.append("## Checklist")
    out.append("")
    out.append("1. **Candidate identity.** Version %s; release commit %s;"
               % (version, head))
    out.append("   the tag names this commit and no other; the range is")
    out.append("   measured from %s." % candidate["base"])
    out.append("2. **The range at a glance.** Content commits, oldest first:")
    if candidate["content"]:
        for entry in candidate["content"]:
            out.append("   - %s %s" % (entry["sha"][:12], entry["subject"]))
            for path in entry["paths"]:
                note = ""
                if path in entry["refresh"]:
                    note = " (figure refresh)"
                else:
                    classes = classify_path(path)
                    if classes:
                        note = " (%s)" % ", ".join(classes)
                out.append("     - %s%s" % (path, note))
    else:
        out.append("   - (no content commits in the range)")
    if candidate["machinery"]:
        out.append("   Release machinery, not classified:")
        for sha, subject in candidate["machinery"]:
            out.append("   - %s %s" % (sha[:12], subject))
    out.append("   Dark landings in this range are named in the landing")
    out.append("   record and answered at item 7.")
    out.append("3. **Builds and publication.** Main build green on the exact")
    out.append("   release commit: _____. Tag build green: _____. Publish")
    out.append("   jobs successful: _____. Release published, draft=false,")
    out.append("   asset count: _____. (Transcribe from the ship record.)")
    out.append("4. **The stamp check.** Wheel SHA-384 match: _____. Sdist")
    out.append("   SHA-384 match: _____. Platform tarball SHA-384 match:")
    out.append("   _____. (Transcribe from the stamp folder's result.)")
    out.append("5. **The fresh measure.** Token component recounted fresh on")
    out.append("   the shipped tree: _____. Figure refresh committed as the")
    out.append("   last content commit, or the skip recorded with its reason:")
    out.append("   _____.")
    out.append("6. **The changelog.** The release's changelog section covers")
    out.append("   every content commit listed at item 2: _____.")
    out.append("7. **Dark landings.** Each dark landing named at item 2 is")
    out.append("   activated deliberately for this release or ships dark on")
    out.append("   purpose, stated per landing: _____.")
    out.append("8. **Class reviews.** Classes this range touched, one")
    out.append("   reviewed line each in the sign-off block:")
    if touched:
        for name in touched:
            out.append("   - %s" % name)
    else:
        out.append("   - (none)")
    untouched = [c for c in CLASS_ORDER if c not in touched]
    if untouched:
        out.append("   Not touched by this range, asking nothing: %s."
                   % ", ".join(untouched))
    out.append("- Classes touched: %s"
               % (", ".join(touched) if touched else "none"))
    if protected:
        out.append("9. **The state of main (protected candidate).** Main's")
        out.append("   tip %s is red; the red guard families or divergences"
                   % candidate["tip"])
        out.append("   are named here, as the ship record knows them: _____.")
        out.append("   The candidate is pinned to the recorded last-green")
        out.append("   commit above. Commits beyond the candidate, deferred")
        out.append("   to their own release:")
        for entry in candidate["deferred"]:
            classes = ", ".join(entry["classes"]) or "no class"
            out.append("   - %s %s (deferred: %s)"
                       % (entry["sha"][:12], entry["subject"], classes))
    else:
        out.append("9. **The state of main.** Main's tip is green at the")
        out.append("   candidate's commit: _____.")
    out.append("10. **The sign-off.** The block below, filled and signed.")
    out.append("")
    out.append(render_signoff_block(version, head, form, touched))
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------
# The sign-off record: parsing and validation (fails closed).
# ------------------------------------------------------------------

_FIELD_RE = re.compile(r"^- ([A-Za-z ]+):\s*(.*?)\s*$")
REQUIRED_FIELDS = ("Version", "Release commit", "Candidate",
                   "Conductor", "Date", "Verdict")


def parse_signoff(text):
    """The sign-off block's fields and reviewed lines, as written.

    Returns (fields, reviewed, problems): fields maps a field name
    to its list of values (a list, so a duplicated field is
    visible to the validator), reviewed lists the classes named
    on Reviewed lines in order, and problems carries any line
    inside the block that fits no field's shape.
    """
    fields = {}
    reviewed = []
    problems = []
    in_block = False
    for line in text.splitlines():
        if line.strip() == "## Sign-off":
            in_block = True
            continue
        if in_block and line.startswith("## "):
            break
        if not in_block:
            continue
        if not line.strip():
            continue
        m = _FIELD_RE.match(line)
        if not m:
            problems.append("line fits no field shape: %r" % line.strip())
            continue
        name, value = m.group(1), m.group(2)
        if name == "Reviewed":
            reviewed.append(value)
        else:
            fields.setdefault(name, []).append(value)
    return fields, reviewed, problems


def parse_classes_touched(text):
    """The classes the record's own checklist declares touched.

    Reads the generator's machine line (``- Classes touched:``);
    returns None when the line is absent, so the validator can
    refuse a record that does not declare its classes.
    """
    for line in text.splitlines():
        m = re.match(r"^- Classes touched:\s*(.*?)\s*$", line)
        if m:
            value = m.group(1)
            if value == "none":
                return ()
            names = tuple(v.strip() for v in value.split(",") if v.strip())
            return names
    return None


def validate_signoff(text, classes_touched=None):
    """Problems with a filled candidate record; [] means valid.

    Fails closed: every rule in the design's validation list is
    checked, and an empty classes declaration can come from the
    record itself (its Classes touched line) or from the caller.
    """
    problems = []
    fields, reviewed, parse_problems = parse_signoff(text)
    problems.extend(parse_problems)
    if not fields:
        problems.append("no sign-off block found")
        return problems
    for name in REQUIRED_FIELDS:
        values = fields.get(name, [])
        if not values:
            problems.append("missing field: %s" % name)
        elif len(values) > 1:
            problems.append("duplicated field: %s" % name)
        elif not values[0]:
            problems.append("empty field: %s" % name)
    for name in fields:
        if name not in REQUIRED_FIELDS:
            problems.append("unknown field: %s" % name)

    def one(name):
        values = fields.get(name, [])
        return values[0] if len(values) == 1 else None

    version = one("Version")
    if version is not None and not VERSION_RE.match(version):
        problems.append(
            "Version is not a full four-component version: %r" % version)
    sha = one("Release commit")
    if sha is not None and not SHA_RE.match(sha):
        problems.append("Release commit is not a full SHA: %r" % sha)
    form = one("Candidate")
    if form is not None and form not in CANDIDATE_FORMS:
        problems.append("Candidate is not a known form: %r" % form)
    date = one("Date")
    if date is not None and not DATE_RE.match(date):
        problems.append("Date is not an ISO date: %r" % date)
    verdict = one("Verdict")
    if verdict is not None and verdict not in VERDICTS:
        problems.append("Verdict is not a known verdict: %r" % verdict)
    if form in CANDIDATE_FORMS and verdict in VERDICTS \
            and verdict != VERDICT_NOT_SIGNED:
        if form == CANDIDATE_PROTECTED and verdict != VERDICT_SIGNED_PROTECTED:
            problems.append(
                "a protected candidate must be signed with the protected "
                "verdict form")
        if form == CANDIDATE_STANDARD and verdict != VERDICT_SIGNED:
            problems.append(
                "a standard candidate must be signed with the standard "
                "verdict form")

    if classes_touched is None:
        classes_touched = parse_classes_touched(text)
        if classes_touched is None:
            problems.append(
                "the record declares no Classes touched line; the "
                "reviewed lines cannot be checked")
            classes_touched = ()
    for name in classes_touched:
        if name not in CLASS_ORDER:
            problems.append("declared touched class is unknown: %r" % name)
    for name in reviewed:
        if name not in CLASS_ORDER:
            problems.append("reviewed line names an unknown class: %r" % name)
        elif name not in classes_touched:
            problems.append(
                "reviewed line for a class the range did not touch: %s"
                % name)
    if len(reviewed) != len(set(reviewed)):
        problems.append("duplicated reviewed line")
    for name in classes_touched:
        if name in CLASS_ORDER and name not in reviewed:
            problems.append(
                "touched class with no reviewed line: %s" % name)
    return problems


# ------------------------------------------------------------------
# The command line front door.
# ------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser(
        "checklist", help="generate a candidate record from a git range")
    p_list.add_argument("--repo", default=".")
    p_list.add_argument("--from", dest="base", required=True,
                        help="the previous release commit (range base)")
    p_list.add_argument("--to", dest="head", required=True,
                        help="the candidate's release commit")
    p_list.add_argument("--version", required=True,
                        help="the candidate's full version")
    p_list.add_argument("--tip", default=None,
                        help="main's tip, when red beyond the candidate")
    p_list.add_argument("--out", default=None,
                        help="write the record here instead of stdout")

    p_tmpl = sub.add_parser(
        "signoff-template", help="print just the sign-off block")
    p_tmpl.add_argument("--version", required=True)
    p_tmpl.add_argument("--sha", required=True)
    p_tmpl.add_argument("--candidate", default=CANDIDATE_STANDARD,
                        choices=CANDIDATE_FORMS)
    p_tmpl.add_argument("--classes", default="",
                        help="comma-separated touched classes")

    p_check = sub.add_parser(
        "check-signoff", help="validate a filled candidate record")
    p_check.add_argument("record")
    p_check.add_argument("--classes", default=None,
                         help="comma-separated touched classes; overrides "
                              "the record's own declaration")

    args = parser.parse_args(argv)

    if args.command == "checklist":
        if not VERSION_RE.match(args.version):
            print("refused: --version is not a full four-component "
                  "version: %r" % args.version, file=sys.stderr)
            return 2
        try:
            head_sha = _git(args.repo, "rev-parse", args.head).strip()
            base_sha = _git(args.repo, "rev-parse", args.base).strip()
            tip_sha = (_git(args.repo, "rev-parse", args.tip).strip()
                       if args.tip else None)
        except ValueError as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        candidate = build_candidate(args.repo, base_sha, head_sha,
                                     args.version, tip=tip_sha)
        text = render_checklist(candidate)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text)
        return 0

    if args.command == "signoff-template":
        classes = tuple(v.strip() for v in args.classes.split(",")
                        if v.strip())
        for name in classes:
            if name not in CLASS_ORDER:
                print("refused: unknown class: %r" % name, file=sys.stderr)
                return 2
        sys.stdout.write(render_signoff_block(
            args.version, args.sha, args.candidate, classes))
        return 0

    if args.command == "check-signoff":
        with open(args.record, encoding="utf-8") as fh:
            text = fh.read()
        touched = None
        if args.classes is not None:
            touched = tuple(v.strip() for v in args.classes.split(",")
                            if v.strip())
        problems = validate_signoff(text, classes_touched=touched)
        if problems:
            for problem in problems:
                print("PROBLEM: %s" % problem)
            return 1
        print("sign-off record valid")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
