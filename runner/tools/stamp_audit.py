#!/usr/bin/env python3
# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Audit the agent stamps in git history against the stamp record.

    python3 runner/tools/stamp_audit.py                 # the report, as text
    python3 runner/tools/stamp_audit.py --markdown      # the report, as markdown
    python3 runner/tools/stamp_audit.py --check         # exit 1 on a violation
    python3 runner/tools/stamp_audit.py --authors       # plus unstamped commits by author

Every commit an agent chat makes carries its stamp (an `Agent-Stamp:`
or `Agent-Chat-Stamp:` trailer) and, when the chat runs in Claude
Code, the session it ran in (`Claude-Session:`). The record of who
holds which stamp is `docs/archive/RESEARCHER_IDENT.md`. A stamp is
there so the conductor can trace a line to the chat that wrote it;
a stamp signed from two sessions, or one session signing as two
stamps, breaks that trace without any file looking wrong.

The rules, held from ENFORCED_FROM on (history before it is reported,
never failed, since the rules did not exist when it was written):

1. one stamp, one session: every commit carrying a stamp that also
   names a session names the same session;
2. one session, one stamp: a session signs with one stamp;
3. a recycled stamp signs nothing new;
4. a stamp that signs a commit is on the record.

A commit with no session line (a seat outside Claude Code) is held
to rules 3 and 4 only. A shallow clone is audited as far as it
reaches; the stamp-audit workflow fetches the whole history.
"""
import argparse
import collections
import datetime
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDENT = os.path.join(ROOT, "docs", "archive", "RESEARCHER_IDENT.md")

# The rules hold for every commit from this moment (the conductor's
# word, 2026-10-27); everything earlier is the audit's history.
ENFORCED_FROM = datetime.datetime(2026, 10, 27, 23, 0, tzinfo=datetime.timezone.utc)

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
NAMED = r"00000000-muse-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
STAMP = r"(?:%s|%s)" % (NAMED, UUID)
TRAILER = re.compile(r"^(?:Agent-Stamp|Agent-Chat-Stamp):\s*(\S+)\s*$", re.M | re.I)
SESSION = re.compile(r"^Claude-Session:\s*\S*?(session_[A-Za-z0-9]+)", re.M)
ROW = re.compile(r"\|[^|]*\|\s*`(%s)`\s*\|\s*(\w+)\s*\|" % STAMP)

Commit = collections.namedtuple("Commit", "sha when author stamps session subject")


def record(path=IDENT):
    """{stamp: status} from the record's status table."""
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = ROW.match(line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


SESSION_ROW = re.compile(
    r"^\|\s*`(%s)`\s*\|\s*((?:session_[A-Za-z0-9]+[,\s]*)+)\|" % STAMP, re.M)


def sessions_on_record(path=IDENT, known=None):
    """{stamp: {session, ...}} from the record's sessions table: the
    session ids a stamp's one chat has run under, written down when
    the runtime reissued one. A stamp with no row has no allowance;
    rule 1 holds it to one session."""
    known = record(path) if known is None else known
    out = {}
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for m in SESSION_ROW.finditer(text):
        stamp = resolve(m.group(1), known)
        if stamp:
            out.setdefault(stamp, set()).update(re.findall(r"session_[A-Za-z0-9]+", m.group(2)))
    return out


def resolve(token, known):
    """A trailer's stamp as the record names it: the full stamp, or the
    one stamp it is a prefix of (some trailers carry the first block
    only). None when it names no stamp on the record."""
    token = token.strip().strip("`").lower()
    if token in known:
        return token
    hits = [s for s in known if s.startswith(token)] if len(token) >= 8 else []
    return hits[0] if len(hits) == 1 else None


def parse_log(text):
    """Commits from `git log --format=%H%x1f%aI%x1f%an%x1f%B%x1e`."""
    out = []
    for rec in text.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f", 3)
        if len(parts) != 4:
            continue
        sha, when, author, body = parts
        when = when.strip()
        if when.endswith("Z"):
            # RFC 3339's Z: fromisoformat reads it only from 3.11.
            when = when[:-1] + "+00:00"
        try:
            stamp_time = datetime.datetime.fromisoformat(when)
        except ValueError:
            continue
        stamps = [t for t in TRAILER.findall(body)]
        sm = SESSION.search(body)
        out.append(Commit(sha.strip(), stamp_time, author.strip(), stamps,
                          sm.group(1) if sm else None,
                          body.strip().split("\n", 1)[0]))
    return out


def git_log(root=ROOT):
    """The history this clone holds, oldest last. None without git."""
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%H%x1f%aI%x1f%an%x1f%B%x1e"],
            cwd=root, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace")
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return parse_log(proc.stdout)


def audit(commits, known, enforced_from=ENFORCED_FROM, sessions=None):
    """(summary, violations, history). summary maps stamp -> facts;
    violations are rule breaks at or after enforced_from; history is
    the same breaks before it. `sessions` is the record's sessions
    table ({stamp: {session, ...}}, sessions_on_record): a stamp that
    signs from several sessions all on its row is one chat under
    reissued ids, not a rule 1 break."""
    sessions = sessions or {}
    by_stamp = collections.defaultdict(lambda: {
        "commits": 0, "sessions": collections.Counter(), "authors": collections.Counter(),
        "first": None, "last": None})
    findings = []
    stamp_sessions = collections.defaultdict(set)   # enforced window only
    session_stamps = collections.defaultdict(set)
    for c in sorted(commits, key=lambda c: c.when):
        live = c.when >= enforced_from
        for token in c.stamps:
            stamp = resolve(token, known)
            if stamp is None:
                findings.append((live, c, "rule 4",
                                 f"stamp {token!r} is not on the record"))
                continue
            s = by_stamp[stamp]
            s["commits"] += 1
            s["sessions"][c.session or "(no session)"] += 1
            s["authors"][c.author] += 1
            s["first"] = s["first"] or c.when
            s["last"] = c.when
            if known.get(stamp) == "recycled" and live:
                findings.append((live, c, "rule 3",
                                 f"recycled stamp {stamp[:8]} signed a new commit"))
            if c.session and live:
                stamp_sessions[stamp].add(c.session)
                session_stamps[c.session].add(stamp)
                if len(stamp_sessions[stamp]) > 1 and not (
                        stamp_sessions[stamp] <= sessions.get(stamp, set())):
                    findings.append((live, c, "rule 1",
                                     f"stamp {stamp[:8]} signed from a second session "
                                     f"({', '.join(sorted(stamp_sessions[stamp]))})"))
                if len(session_stamps[c.session]) > 1:
                    findings.append((live, c, "rule 2",
                                     f"session {c.session} signs as "
                                     f"{', '.join(sorted(x[:8] for x in session_stamps[c.session]))}"))
    # the same rules over the whole history, for the report
    hist_ss = collections.defaultdict(set)
    hist_st = collections.defaultdict(set)
    for c in commits:
        if c.when >= enforced_from or not c.session:
            continue
        for token in c.stamps:
            stamp = resolve(token, known)
            if stamp:
                hist_ss[stamp].add(c.session)
                hist_st[c.session].add(stamp)
    history = []
    for stamp, sessions in sorted(hist_ss.items()):
        if len(sessions) > 1:
            history.append(("rule 1", f"stamp {stamp[:8]} was signed from "
                            f"{len(sessions)} sessions: {', '.join(sorted(sessions))}"))
    for session, stamps in sorted(hist_st.items()):
        if len(stamps) > 1:
            history.append(("rule 2", f"session {session} signed as "
                            f"{', '.join(sorted(s[:8] for s in stamps))}"))
    history.extend((rule, f"{c.sha[:9]} {msg}") for live, c, rule, msg in findings if not live)
    violations = [(c, rule, msg) for live, c, rule, msg in findings if live]
    return dict(by_stamp), violations, history


def unstamped(commits):
    """Commits that carry no stamp, counted by author, with the newest."""
    out = {}
    for c in commits:
        if c.stamps:
            continue
        n, newest = out.get(c.author, (0, None))
        out[c.author] = (n + 1, newest if newest and newest > c.when else c.when)
    return out


def report(summary, violations, history, known, markdown=False, commits=0,
           bare=None):
    lines = []
    h = "## " if markdown else ""
    lines.append(("# " if markdown else "") + "Stamp audit")
    lines.append("")
    lines.append(f"<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->" if markdown else "")
    lines.append(f"{commits} commits read; rules enforced from "
                 f"{ENFORCED_FROM.isoformat()} (runner/tools/stamp_audit.py).")
    lines.append("")
    lines.append(h + "Stamps")
    lines.append("")
    if markdown:
        lines.append("| Stamp | Record | Commits | Sessions | First | Last |")
        lines.append("|---|---|---:|---|---|---|")
    for stamp in sorted(known, key=lambda s: (s.startswith("0000"), s)):
        s = summary.get(stamp)
        n = s["commits"] if s else 0
        sess = ", ".join(f"{k[-6:] if k.startswith('session_') else k} x{v}"
                         for k, v in s["sessions"].most_common()) if s else "-"
        first = s["first"].date().isoformat() if s and s["first"] else "-"
        last = s["last"].date().isoformat() if s and s["last"] else "-"
        if markdown:
            lines.append(f"| `{stamp[:8]}` | {known[stamp]} | {n} | {sess} | {first} | {last} |")
        else:
            lines.append(f"{stamp[:8]}  {known[stamp]:9} {n:5}  {first}..{last}  {sess}")
    lines.append("")
    lines.append(h + "Violations (enforced window)")
    lines.append("")
    if violations:
        for c, rule, msg in violations:
            lines.append(f"- {rule}: {c.sha[:9]} {msg} ({c.subject[:70]})")
    else:
        lines.append("- none")
    lines.append("")
    if bare:
        lines.append(h + "Commits with no stamp, by author")
        lines.append("")
        for author, (n, newest) in sorted(bare.items(), key=lambda x: -x[1][0]):
            lines.append(f"- {author}: {n} (newest {newest.date().isoformat()})")
        lines.append("")
    lines.append(h + "History (before the rules; reported, never failed)")
    lines.append("")
    if history:
        for rule, msg in history:
            lines.append(f"- {rule}: {msg}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--authors", action="store_true",
                    help="also count the commits that carry no stamp, by "
                         "author (a local look: it prints account names, "
                         "so the committed and published reports leave it out)")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when the enforced window has a violation")
    args = ap.parse_args(argv)
    commits = git_log()
    if commits is None:
        print("stamp audit: no git history here", file=sys.stderr)
        return 2
    known = record()
    summary, violations, history = audit(commits, known,
                                         sessions=sessions_on_record(known=known))
    print(report(summary, violations, history, known, args.markdown,
                 len(commits), unstamped(commits) if args.authors else None))
    if args.check and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
