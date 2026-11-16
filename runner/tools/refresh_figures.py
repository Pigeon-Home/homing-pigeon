"""Refresh the project's headline figures from their one source.

The canonical record, docs/infrastructure-documents/project/
statistics.md, carries a fenced JSON block: the facts. The
evergreen docs (AGENTS.md, PROTOCOL.md, docs/steady/
fuzzing.md) do not restate the volatile figures by hand; they
carry marked slots --

    <!--hp-fig:tokens_exact-->20,163,806<!--/hp-fig-->

-- whose contents this tool fills from the facts, and the
record's own display line is rendered from the same facts.

    python3 runner/tools/refresh_figures.py --check
        Verify every slot and the display line against the
        facts; exit 1 and name each mismatch. This is what
        the guard test runs.

    python3 runner/tools/refresh_figures.py --write
        Take a fresh measure of the tree at the current HEAD
        (the version4 estimator's whole-tree count, the
        tracked-line count, the commit count, and the core
        figures exported from runner/ops/core.py, which stays
        their source of truth), rewrite the facts block, the
        record's header and display line, and every slot.
        The latent percentages are the duplication audit's,
        not a tree measure: they are carried forward from the
        standing facts, and a fresh audit updates them by
        hand. The record's basis prose is likewise reviewed
        by hand in the same commit; this tool owns the
        mechanical surfaces only.

The commit count is taken only from a complete history.
rev-list on a shallow checkout counts the clone's depth,
not the project, and the 3.16.25.27 refresh published
exactly that -- 170 commits, display 0, over standing
facts of 5,836 (Q193). A measure therefore refuses a
shallow checkout loudly, before anything is written, and
refuses a fresh count below the standing facts' count:
the project's count only grows, so either shape is a
broken measure, never a publishable fact.

The release procedure runs --write on the measured tree as
the last content step before a release commit: measure
first, statistics write last, and every figure cites the
measured commit it was taken at.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys

STATISTICS_REL = os.path.join(
    "docs", "infrastructure-documents", "project", "statistics.md")
SLOT_FILES = (
    "AGENTS.md",
    "PROTOCOL.md",
    os.path.join("docs", "steady", "fuzzing.md"),
)
SLOT_RE = re.compile(
    r"<!--hp-fig:([a-z0-9_]+)-->(.*?)<!--/hp-fig-->", re.S)
FACTS_RE = re.compile(r"```json\n(.*?)```", re.S)
# The as-assembled core set is the canonical list plus the
# suite's own 3 test runners (runner/ops/core.py's docstring
# names them; the canonical list leaves them out by design).
ASSEMBLED_EXTRA = (
    "runner/tools/run_tests_parallel.py",
    "runner/tools/run_tests_shuffled.py",
    "runner/tools/run_tests_windows_sim.py",
)
FACT_KEYS = (
    "as_of", "commit", "counter", "tokens", "lines_tracked",
    "commits", "display_commits", "display_lines",
    "non_latent_percent", "latent_near_percent",
    "latent_exact_percent", "audit_date", "core_files",
    "core_lines", "core_lines_nonblank", "core_tokens",
    "core_assembled_lines", "core_assembled_nonblank",
    "core_assembled_zip_bytes", "core_assembled_tokens",
)


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def parse_facts(statistics_text):
    """The facts dict from the record's fenced JSON block."""
    match = FACTS_RE.search(statistics_text)
    if not match:
        raise ValueError("statistics.md carries no fenced json block")
    return json.loads(match.group(1))


def _percent(value):
    return ("%f" % value).rstrip("0").rstrip(".")


def display_line(facts):
    """The record's display line, rendered from the facts."""
    return "%d mil security tokens, %s commits, %s lines at %s%% " \
        "non-latent code" % (
            facts["tokens"] // 1_000_000,
            format(facts["display_commits"], ","),
            format(facts["display_lines"], ","),
            _percent(facts["non_latent_percent"]))


def renderings(facts):
    """Slot name -> the exact text the facts put in the slot."""
    millions = facts["tokens"] // 1_000_000
    return {
        "tokens_exact": format(facts["tokens"], ","),
        "tokens_millions": str(millions),
        "tokens_millions_word": "%d million" % millions,
        "as_of": facts["as_of"],
        "lines_tracked": format(facts["lines_tracked"], ","),
        "core_files": str(facts["core_files"]),
        "core_lines": format(facts["core_lines"], ","),
        "core_lines_nonblank": format(
            facts["core_lines_nonblank"], ","),
        "core_tokens": format(facts["core_tokens"], ","),
        "core_assembled_lines": format(
            facts["core_assembled_lines"], ","),
        "core_assembled_nonblank": format(
            facts["core_assembled_nonblank"], ","),
        "core_assembled_zip_bytes": format(
            facts["core_assembled_zip_bytes"], ","),
        "core_assembled_tokens": format(
            facts["core_assembled_tokens"], ","),
    }


def find_slots(text):
    return [(m.group(1), m.group(2)) for m in SLOT_RE.finditer(text)]


def check(root):
    """Problems: each slot or the display line out of step
    with the facts. An empty list is a clean tree."""
    problems = []
    try:
        facts = parse_facts(_read(os.path.join(root, STATISTICS_REL)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ["statistics.md: facts unreadable (%s)" % exc]
    for key in FACT_KEYS:
        if key not in facts:
            problems.append("statistics.md: facts lack %r" % key)
    if problems:
        return problems
    text = _read(os.path.join(root, STATISTICS_REL))
    if display_line(facts) not in text.splitlines():
        problems.append(
            "statistics.md: display line is not the facts' line "
            "(%s)" % display_line(facts))
    wanted = renderings(facts)
    for rel in SLOT_FILES:
        path = os.path.join(root, rel)
        try:
            slots = find_slots(_read(path))
        except OSError:
            problems.append("%s: unreadable" % rel)
            continue
        if not slots:
            problems.append("%s: no figure slots found" % rel)
        for name, value in slots:
            if name not in wanted:
                problems.append(
                    "%s: unknown figure slot %r" % (rel, name))
            elif value != wanted[name]:
                problems.append(
                    "%s: slot %s holds %r, the facts say %r"
                    % (rel, name, value, wanted[name]))
    return problems


def _load_ops(root):
    """version4 and core from this tree, by path (the house
    pattern for tools; core's own sibling import of version4
    resolves with the ops directory on sys.path)."""
    ops = os.path.join(root, "runner", "ops")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    loaded = {}
    for name in ("version4", "core"):
        spec = importlib.util.spec_from_file_location(
            "hp_refresh_" + name, os.path.join(ops, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        loaded[name] = mod
    return loaded["version4"], loaded["core"]


def _git(root, *args):
    out = subprocess.run(
        ["git", "-C", root] + list(args),
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


class ShallowHistoryError(RuntimeError):
    """A commit count was asked of an incomplete history."""


def display_commits_for(commits):
    """The display rounding for a commit count: the count
    to the nearest 1,000, halves away from zero (the shape
    that has always stood in the facts: 5,836 reads 6,000,
    and 170 reads 0 -- which is how the shallow figure of
    Q193 showed itself in the display line)."""
    return int((commits + 500) // 1000) * 1000


def is_shallow_history(root):
    """True when the checkout at root holds incomplete
    history. `git rev-parse --is-shallow-repository` is the
    authority; a git without the verb falls back to the
    shallow file in the git directory, which a .git file or
    a linked worktree still resolves through --git-dir. A
    root git cannot speak for at all reads as not shallow
    here, and count_commits' own rev-list fails on its own
    terms there."""
    try:
        return _git(root, "rev-parse",
                    "--is-shallow-repository") == "true"
    except subprocess.CalledProcessError:
        pass
    try:
        git_dir = _git(root, "rev-parse", "--git-dir")
    except subprocess.CalledProcessError:
        return False
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(root, git_dir)
    return os.path.exists(os.path.join(git_dir, "shallow"))


def count_commits(root):
    """The HEAD commit count of a complete history, or a
    refusal. rev-list counts what it can reach; on a
    shallow checkout that is the depth of the clone, not
    the project. The statistics record's own basis states
    the rule -- the count rests on a complete clone, and
    any future count is taken the same way -- so a shallow
    history refuses here, naming what it can see, instead
    of letting a partial count be published as the
    project's (Q193)."""
    if is_shallow_history(root):
        try:
            seen = int(_git(root, "rev-list", "--count", "HEAD"))
            detail = ("it can reach only %d commit(s) from HEAD"
                      % seen)
        except (subprocess.CalledProcessError, ValueError):
            detail = "its reachable history is incomplete"
        raise ShallowHistoryError(
            "the checkout at %s is shallow: %s; refusing to "
            "publish a partial commit count -- take the "
            "measure from a complete clone, or fetch "
            "--unshallow first" % (root, detail))
    return int(_git(root, "rev-list", "--count", "HEAD"))


def validate_commit_count(commits, previous):
    """A fresh count answers to the standing facts: the
    project's count only grows, so a smaller fresh count
    is a broken measure (a truncated history that slipped
    its marker, a wrong root), never a publishable fact.
    Returns the count it was handed."""
    if commits < 0:
        raise ValueError(
            "commit count is negative: %d" % commits)
    standing = previous.get("commits")
    if isinstance(standing, int) and commits < standing:
        raise ValueError(
            "fresh commit count %d is below the standing "
            "facts' %d; the count only grows, so the measure "
            "is broken -- refusing to publish it"
            % (commits, standing))
    return commits


def measure_facts(root, previous):
    """Fresh facts for the tree at root's HEAD. The audit's
    percentages carry forward; everything else is measured.
    The commit count is taken first, so an incomplete
    history refuses before any measuring work is done."""
    commits = validate_commit_count(count_commits(root), previous)
    version4, core = _load_ops(root)
    tokens = version4.measure_repo_tokens(root)
    lines = 0
    for rel in _git(root, "ls-files").splitlines():
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                lines += len(
                    fh.read().decode("utf-8", "replace").splitlines())
        except OSError:
            continue
    core_lines, core_nonblank = core.measure_core_lines(root)
    assembled = list(core.CORE_FILES) + list(ASSEMBLED_EXTRA)
    facts = {
        # the UTC day, the hosted record's clock: a seat's local
        # day ran the figure's date backwards between two cuts
        "as_of": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "commit": _git(root, "rev-parse", "HEAD"),
        "counter": previous.get("counter", "runner/ops/version4.py"),
        "tokens": tokens,
        "lines_tracked": lines,
        "commits": commits,
        "display_commits": display_commits_for(commits),
        "display_lines": int((lines + 50_000) // 100_000) * 100_000,
        "non_latent_percent": previous["non_latent_percent"],
        "latent_near_percent": previous["latent_near_percent"],
        "latent_exact_percent": previous["latent_exact_percent"],
        "audit_date": previous["audit_date"],
        "core_files": len(core.CORE_FILES),
        "core_lines": core_lines,
        "core_lines_nonblank": core_nonblank,
        "core_tokens": core.measure_core_tokens(root),
        "core_assembled_lines": core.AS_ASSEMBLED_LINES,
        "core_assembled_nonblank": core.AS_ASSEMBLED_NONBLANK_LINES,
        "core_assembled_zip_bytes": core.AS_ASSEMBLED_ZIP_BYTES,
        "core_assembled_tokens": core.measure_core_tokens(
            root, assembled),
    }
    return {key: facts[key] for key in FACT_KEYS}


def write(root):
    """Rewrite the facts, the record's mechanical surfaces,
    and every slot, from a fresh measure. Returns the list of
    files changed."""
    stats_path = os.path.join(root, STATISTICS_REL)
    text = _read(stats_path)
    previous = parse_facts(text)
    facts = measure_facts(root, previous)
    block = "```json\n%s\n```" % json.dumps(facts, indent=2)
    text = FACTS_RE.sub(lambda _: block, text, count=1)
    old_line = display_line(previous)
    if old_line in text:
        text = text.replace(old_line, display_line(facts), 1)
    text = re.sub(
        r"^Dated \d{4}-\d{2}-\d{2}\. Measured on main at commit\n"
        r"[0-9a-f]{40}",
        "Dated %s. Measured on main at commit\n%s"
        % (facts["as_of"], facts["commit"]),
        text, count=1, flags=re.M)
    text = re.sub(
        r"the \d+-million-token measure",
        "the %d-million-token measure"
        % (facts["tokens"] // 1_000_000), text, count=1)
    changed = []
    if text != _read(stats_path):
        _write(stats_path, text)
        changed.append(STATISTICS_REL)
    wanted = renderings(facts)
    for rel in SLOT_FILES:
        path = os.path.join(root, rel)
        original = _read(path)

        def fill(match):
            name = match.group(1)
            if name not in wanted:
                raise ValueError("%s: unknown figure slot %r"
                                 % (rel, name))
            return "<!--hp-fig:%s-->%s<!--/hp-fig-->" % (
                name, wanted[name])

        updated = SLOT_RE.sub(fill, original)
        if updated != original:
            _write(path, updated)
            changed.append(rel)
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Refresh or check the headline figures "
                    "against the statistics record's facts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="verify slots and the display line "
                            "against the facts")
    group.add_argument("--write", action="store_true",
                       help="take a fresh measure and rewrite "
                            "the facts and every slot")
    parser.add_argument("--root", default=None,
                        help="the checkout to work on "
                             "(default: the tree this tool "
                             "ships in)")
    args = parser.parse_args(argv)
    root = args.root or repo_root()
    if args.check:
        problems = check(root)
        for problem in problems:
            print(problem)
        if problems:
            return 1
        print("figure slots and the display line match the facts")
        return 0
    try:
        changed = write(root)
    except (ShallowHistoryError, ValueError) as exc:
        print("refresh refused: %s" % exc, file=sys.stderr)
        return 2
    for rel in changed:
        print("updated %s" % rel)
    if not changed:
        print("already current; nothing rewritten")
    print("review the record's basis prose in the same commit; "
          "it is not generated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
