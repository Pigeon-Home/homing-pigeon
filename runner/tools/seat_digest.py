#!/usr/bin/env python3
"""Where each seat's work went, read from the repository's own record.

    python3 runner/tools/seat_digest.py [--hours 72] [--until ISO-TIME]
                                        [--seat NAME ...] [--top 8] [--json]

One window of history, per author: the commits, the lines, the
files the lines went to and their share, the commits by kind (the
subject's prefix), the questions filed in the window and who they
were addressed to, the longest chain of questions that each answer
the one before ("the Q<n> guard's residual ..."), and, for a
question one seat asked another, the hours until the other seat's
first commit that names it.

It is the release train's `clock` turned on the work itself: the
cycle stopped being hours of attention once its timeline was read
from the hosted record instead of from memory, and the same holds
for what a seat is spending its hours on. The digest decides
nothing and judges nothing; it prints what the history holds, so a
change of direction can be read against the window before it and
the window after it.
"""
import argparse
import collections
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUESTIONS = "docs/steady/seats/questions.md"
_HEAD = re.compile(r"^## (Q\d+\w*) \((.*?),? (\d{4}-\d{2}-\d{2})\):\s*(.*)$")
_RESIDUAL = re.compile(r"\bthe (Q\d+\w*)\b.{0,40}?\bresidual\b")


def _git(*args):
    proc = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args[:2]), proc.stderr.strip()[:300]))
    return proc.stdout


def kind(subject):
    """The subject's prefix, lowercased: 'desk', 'release', 'q168'
    becomes 'question fix'; a subject with no prefix is 'other'."""
    m = re.match(r"^([A-Za-z0-9_+.-]{1,24})\s*:", subject)
    if not m:
        return "other"
    word = m.group(1).lower()
    return "question fix" if re.fullmatch(r"q\d+\w*", word) else word


def parse_log(text):
    """[{sha, at, author, subject, files: [(added, deleted, path)]}]
    from `git log --numstat --format=@%h%x09%ct%x09%an%x09%s`."""
    commits = []
    for line in text.splitlines():
        if line.startswith("@"):
            sha, at, author, subject = (line[1:].split("\t", 3) + ["", "", ""])[:4]
            commits.append({"sha": sha, "at": int(at or 0), "author": author, "subject": subject, "files": []})
            continue
        m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", line)
        if m and commits:
            added = 0 if m.group(1) == "-" else int(m.group(1))
            deleted = 0 if m.group(2) == "-" else int(m.group(2))
            commits[-1]["files"].append((added, deleted, m.group(3)))
    return commits


def questions(text):
    """[{q, who, date, title}] from the questions file, newest first
    as the file holds them. A heading that wraps is read whole."""
    out, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("## Q"):
            continue
        head = [line]
        for nxt in lines[i + 1:i + 12]:
            if not nxt.strip():
                break
            head.append(nxt.strip())
        m = _HEAD.match(" ".join(head))
        if m:
            out.append({"q": m.group(1), "who": m.group(2), "date": m.group(3), "title": m.group(4)})
    return out


def addressed(who):
    """(asker, kind of addressee): 'self' for a seat writing to the
    desk it carries, 'owner', or 'seat'."""
    asker = re.split(r",| asks | to ", who, maxsplit=1)[0].strip()
    low = who.lower()
    if re.search(r"\b(owner|conductor)\b", low) and re.search(r"asks the owner|to the (owner|conductor)|owner and", low):
        return asker, "owner"
    if asker == "Muse" and "to the desk" in low:
        return asker, "self"
    return asker, "seat"


def longest_chain(qs):
    """The longest run of questions that each name the one before as
    the guard whose residual they carry: (length, first, last)."""
    link = {}
    for q in qs:
        m = _RESIDUAL.search(q["title"])
        if m:
            link[q["q"]] = m.group(1)
    best = (0, "", "")
    for start in link:
        seen, cur = [start], start
        while cur in link and link[cur] not in seen:
            cur = link[cur]
            seen.append(cur)
        if len(seen) > best[0]:
            best = (len(seen), seen[-1], seen[0])
    return best


def digest(commits, qs, since_day, until_day, top=8):
    seats = collections.OrderedDict()
    for c in commits:
        s = seats.setdefault(c["author"], {"commits": 0, "added": 0, "deleted": 0,
                                           "paths": collections.Counter(), "kinds": collections.Counter()})
        s["commits"] += 1
        s["kinds"][kind(c["subject"])] += 1
        for added, deleted, path in c["files"]:
            s["added"] += added
            s["deleted"] += deleted
            s["paths"][path] += added
    for s in seats.values():
        total = max(1, s["added"])
        s["top"] = [(path, n, round(100.0 * n / total, 1)) for path, n in s["paths"].most_common(top)]
        del s["paths"]
    filed = [q for q in qs if since_day <= q["date"] <= until_day]
    to = collections.Counter()
    for q in filed:
        asker, kind_ = addressed(q["who"])
        to[(asker, kind_)] += 1
    return {"seats": seats, "filed": len(filed),
            "addressed": sorted(("%s -> %s" % k, n) for k, n in to.items()),
            "chain": longest_chain(filed)}


def answer_hours(commits, qs, since_day, until_day):
    """For a question one seat asked another in the window: hours
    from the first commit that names it to the first commit by a
    different author that names it. None while unanswered."""
    rows = []
    ordered = sorted(commits, key=lambda c: c["at"])
    for q in qs:
        asker, kind_ = addressed(q["who"])
        if kind_ != "seat" or not (since_day <= q["date"] <= until_day):
            continue
        named = [c for c in ordered if re.search(r"\b%s\b" % re.escape(q["q"]), c["subject"])]
        if not named:
            continue
        first = named[0]
        other = [c for c in named if c["author"] != first["author"]]
        rows.append((q["q"], first["author"], other[0]["author"] if other else None,
                     round((other[0]["at"] - first["at"]) / 3600.0, 1) if other else None))
    return rows


def render(d, hours_rows, since, until):
    out = ["seat digest: %s .. %s" % (since, until)]
    for name, s in d["seats"].items():
        out.append("%s: %d commits, %s lines added, %s deleted"
                   % (name, s["commits"], format(s["added"], ","), format(s["deleted"], ",")))
        for path, n, share in s["top"]:
            out.append("    %5.1f%%  %9s  %s" % (share, format(n, ","), path))
        out.append("    by kind: " + ", ".join("%s %d" % kv for kv in s["kinds"].most_common(8)))
    out.append("questions filed in the window: %d (%s)"
               % (d["filed"], ", ".join("%s %d" % kv for kv in d["addressed"]) or "none"))
    n, first, last = d["chain"]
    if n > 1:
        out.append("longest chain of residual questions: %d, %s .. %s" % (n, first, last))
    for q, asker, answerer, hours in hours_rows:
        out.append("%s: named first by %s; %s" % (
            q, asker, "first named by %s %.1f hours later" % (answerer, hours) if answerer else "no other seat has named it"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--until", default=None, help="the window's end, ISO (default: now, UTC)")
    ap.add_argument("--seat", action="append", default=[], help="an author to print (repeatable; default: all)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    end = (datetime.datetime.fromisoformat(args.until.replace("Z", "+00:00")) if args.until
           else datetime.datetime.now(datetime.timezone.utc))
    start = end - datetime.timedelta(hours=args.hours)
    iso = lambda t: t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits = parse_log(_git("log", "--since=" + iso(start), "--until=" + iso(end),
                             "--numstat", "--format=@%h%x09%ct%x09%an%x09%s"))
    if args.seat:
        commits_shown = [c for c in commits if c["author"] in args.seat]
    else:
        commits_shown = commits
    with open(os.path.join(ROOT, QUESTIONS), encoding="utf-8") as fh:
        qs = questions(fh.read())
    days = (iso(start)[:10], iso(end)[:10])
    d = digest(commits_shown, qs, days[0], days[1], args.top)
    rows = answer_hours(commits, qs, days[0], days[1])
    if args.json:
        print(json.dumps({"since": iso(start), "until": iso(end), "digest": d, "answers": rows}, indent=1))
    else:
        print(render(d, rows, iso(start), iso(end)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
