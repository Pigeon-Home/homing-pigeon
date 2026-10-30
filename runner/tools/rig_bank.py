#!/usr/bin/env python3
"""Bank one rig's de_dust corpus into main, under the bank contract.

The contract is section M item 7 of the campaign standing orders
(docs/project/campaign-standing-orders.md): corpus entry files
merge by union on the entry id; runs.jsonl merges by union,
stable-sorted on when, with exactly one header line; totals
quoted in a ledger line come from the merged tree; grow numbers
are per rig; every ledger line names its rig; a bank that cannot
meet the shape refuses and says so in its ledger line.

This tool is the mechanical half of that contract, so a rig with
no seat at the keyboard (the Germany rig, whose grow keeps its
corpus on the box) banks the same way the VM rig's seat banks by
hand. It reads the rig's corpus directory, merges it into a
throwaway clone of origin/main -- entry files and crash files by
id, arc sidecars by set union, runs by union on the whole record
-- appends the grow's ledger block to the standing orders in that
clone, commits as Muse with the campaign stamp, and pushes
HEAD:main, verifying the push at the remote ref before it calls
the bank landed. State files that belong to a seat's own passes
(survivors.json, grammar.json) are not merged: two rigs must
never overwrite each other's pass state with a stale copy.

Reads are torn-tolerant in one direction only. A corpus file is
append-only, so a bank that races a grow may catch its last line
half-written; that line is dropped for this bank and read whole
on the next one. A bad line anywhere else means the file's shape
is not what the contract promises, and the bank refuses.

The PAT is read from a file at use time and never printed; git's
own output is captured and never forwarded, because a git error
can echo the URL the credential rides in.

Usage:
    python runner/tools/rig_bank.py --rig "Germany rig" \
        --corpus /path/to/runner/tests/de_dust \
        --pat-file /path/to/github-pat.txt \
        [--resources "box cpu 84% | wall 1h32m"] [--dry-run]

Exit codes: 0 banked (or nothing new to bank), 2 refusal of
shape, 3 torn read past the tail, 4 the push did not land,
75 a muster holds (docs/use/muster.hold stands on main): nothing
merged, nothing pushed, retry next cycle (Q109).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

STAMP = "00000000-muse-7e57-d0c5-58316a922026"
REPO_URL = "https://github.com/Pigeon-Home/homing-pigeon.git"
ORDERS_REL = "docs/project/campaign-standing-orders.md"
CORPUS_REL = "runner/tests/de_dust"


class Refusal(Exception):
    """The bank cannot meet the contract's shape; exit 2."""


class TornRead(Exception):
    """A corpus file is torn past its tail; exit 3."""


def _is_header(obj):
    return (
        isinstance(obj, dict)
        and "id" not in obj
        and ("file" in obj or set(obj) <= {"Agent-Stamp", "de_dust", "target", "file"})
    )


def read_jsonl(path, torn_ok=True):
    """Read a JSONL corpus file as (header, [objects]).

    The header is the first object when it has the header shape.
    A final line that does not parse is dropped when torn_ok; a
    bad line anywhere else raises TornRead.
    """
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    objs = []
    for i, ln in enumerate(lines):
        try:
            objs.append(json.loads(ln))
        except json.JSONDecodeError:
            if torn_ok and i == len(lines) - 1:
                break
            raise TornRead(f"{path}: line {i + 1} does not parse")
    header = None
    if objs and _is_header(objs[0]):
        header, objs = objs[0], objs[1:]
    return header, objs


def write_jsonl(path, header, objs):
    with open(path, "w", encoding="utf-8") as fh:
        if header is not None:
            fh.write(json.dumps(header) + "\n")
        for obj in objs:
            fh.write(json.dumps(obj) + "\n")


def retired_in_tree(tree_path):
    """The tree's retired list beside a crash or slow file
    (<target>.retired.json, written by de_dust_corpus.py promote):
    id -> {"on", "why"}. A slow finding retired as fast (de_dust2)
    is kept out the way a fixed crash is."""
    for suffix in (".crashes.jsonl", ".slow.jsonl"):
        if tree_path.endswith(suffix):
            side = tree_path[: -len(suffix)] + ".retired.json"
            break
    else:
        return {}
    if not os.path.exists(side):
        return {}
    try:
        with open(side, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    rows = data.get("retired") if isinstance(data, dict) else None
    return rows if isinstance(rows, dict) else {}


def _is_ancestor(older, newer, cwd):
    """True, False, or None when git cannot say."""
    if not (isinstance(older, str) and isinstance(newer, str)
            and 7 <= len(older) <= 40 and 7 <= len(newer) <= 40):
        return None
    try:
        proc = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer],
                              cwd=cwd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return {0: True, 1: False}.get(proc.returncode)


def retired_stale(obj, retired, cwd=None):
    """A crash record the tree retired, found on a tree at or before
    the retirement: a rig's stale copy or an echo from an older head,
    not the crash found again after the fix (a regression, banked).
    The record's `head` against the retirement's decides when git can
    compare them (the clone is full); else the `found` date against
    the retirement's, a day at a time."""
    row = retired.get(obj.get("id"))
    if not isinstance(row, dict):
        return False
    verdict = _is_ancestor(obj.get("head"), row.get("head"), cwd)
    if verdict is not None:
        return verdict
    found, on = obj.get("found"), row.get("on")
    if not isinstance(found, str) or not isinstance(on, str):
        return True
    return found <= on


def merge_id_file(tree_path, bank_path):
    """Union one entry or crash file by id. Returns (ids added, echoes).

    A crash record the tree retired (promote, after a fix) is not
    re-added from a rig's stale copy: it would come back as an
    expectedFailure probe that passes, and the build would go red
    (Q106). `echoes` is how many of the bank's records that rule
    dropped, so a ledger line can say the rate (Muse, the echo
    problem, item 3).
    """
    b_header, b_objs = read_jsonl(bank_path)
    if os.path.exists(tree_path):
        t_header, t_objs = read_jsonl(tree_path)
    else:
        t_header, t_objs = None, []
    retired = retired_in_tree(tree_path)
    by_id = {}
    for obj in t_objs:
        by_id[obj["id"]] = obj
    added = []
    echoes = 0
    for obj in b_objs:
        if obj["id"] in by_id:
            continue
        # The tree path sits in the clone, whose git holds the full
        # history the ancestry check needs.
        if retired_stale(obj, retired, cwd=os.path.dirname(tree_path)):
            echoes += 1
            continue
        by_id[obj["id"]] = obj
        added.append(obj["id"])
    if added:
        write_jsonl(tree_path, t_header if t_header is not None else b_header,
                    list(by_id.values()))
    return added, echoes


def merge_arcs(tree_path, bank_path):
    """Union one arc sidecar's arc set. Returns arcs added."""
    if not (os.path.exists(tree_path) and os.path.exists(bank_path)):
        return 0
    with open(tree_path, encoding="utf-8") as fh:
        tree = json.load(fh)
    with open(bank_path, encoding="utf-8") as fh:
        bank = json.load(fh)
    if "arcs" not in tree or "arcs" not in bank:
        return 0
    have = {tuple(a) for a in tree["arcs"]}
    new = {tuple(a) for a in bank["arcs"]} - have
    if new:
        tree["arcs"] = [list(a) for a in sorted(have | new)]
        with open(tree_path, "w", encoding="utf-8") as fh:
            json.dump(tree, fh, indent=1)
    return len(new)


def merge_runs(tree_path, bank_path):
    """Union runs.jsonl, stable-sorted on when, one header.

    Returns (records added, all merged records). Raises Refusal
    when either side lacks the header or the two headers differ:
    the merged file must carry exactly one, and it must be the
    contract's.
    """
    t_header, t_objs = read_jsonl(tree_path)
    b_header, b_objs = read_jsonl(bank_path)
    if t_header is None or b_header is None:
        raise Refusal("runs.jsonl on one side has no header line")
    if json.dumps(t_header, sort_keys=True) != json.dumps(b_header, sort_keys=True):
        raise Refusal("runs.jsonl headers differ between the trees")
    seen = set()
    merged = []
    for obj in t_objs + b_objs:
        key = json.dumps(obj, sort_keys=True)
        if key not in seen:
            seen.add(key)
            merged.append(obj)
    added = len(merged) - len(t_objs)
    merged.sort(key=lambda o: o.get("when", ""))
    write_jsonl(tree_path, t_header, merged)
    return added, merged


def latest_totals(run_objs):
    """Corpus totals: the latest entries_after / arcs_after per target."""
    latest = {}
    for obj in run_objs:
        if "target" in obj:
            latest[obj["target"]] = obj
    return (
        sum(o.get("entries_after", 0) for o in latest.values()),
        sum(o.get("arcs_after", 0) for o in latest.values()),
    )


def merge_corpus(tree_dir, bank_dir):
    """Merge bank_dir's corpus into tree_dir. Returns a report dict."""
    report = {"entries": {}, "crashes": {}, "arcs": 0, "runs_added": 0}
    for name in sorted(os.listdir(bank_dir)):
        bank_path = os.path.join(bank_dir, name)
        tree_path = os.path.join(tree_dir, name)
        if name == "runs.jsonl":
            added, merged = merge_runs(tree_path, bank_path)
            report["runs_added"] = added
            report["run_objs"] = merged
        elif name.endswith((".crashes.jsonl", ".slow.jsonl")):
            added, echoes = merge_id_file(tree_path, bank_path)
            if added:
                report["crashes"][name] = added
            report["echoes"] = report.get("echoes", 0) + echoes
        elif name.endswith(".jsonl"):
            added, echoes = merge_id_file(tree_path, bank_path)
            if added:
                report["entries"][name] = added
        elif name.endswith(".arcs.json"):
            report["arcs"] += merge_arcs(tree_path, bank_path)
    if "run_objs" not in report:
        _, report["run_objs"] = read_jsonl(os.path.join(tree_dir, "runs.jsonl"))
    report["totals"] = latest_totals(report["run_objs"])
    return report


def tree_head(corpus_dir):
    """The short head of the tree the rig banks from, so the ledger
    says which rig_bank and which readers the rig ran; None when the
    corpus dir is not inside a git tree."""
    try:
        proc = subprocess.run(["git", "-C", corpus_dir, "rev-parse", "--short=12", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    head = proc.stdout.decode("ascii", "replace").strip() if proc.returncode == 0 else ""
    return head or None


def settle_crashes(clone, report, run=subprocess.run, timeout=900):
    """Replay the crash records this bank merged at main's own head,
    inside the clone, with the tool's `promote`: a record that still
    crashes stays a crash (the suite carries it as an expectedFailure
    probe that fails, as it should); one that passes was found by a
    grow on a tree older than the fix, and `promote` moves it into the
    corpus or retires it, so it never lands on main as a probe that
    passes and reddens the build (Q108). Returns {target: summary}.
    A promote that cannot run leaves the merge as it was: the bank
    still lands, and the suite says what promote would have."""
    out = {}
    for name in sorted(report.get("crashes") or {}):
        target = name.rsplit(".", 2)[0]
        try:
            proc = run([sys.executable, os.path.join("runner", "tools", "de_dust_corpus.py"),
                        "promote", "--target", target],
                       cwd=clone, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout, check=False)
            text = proc.stdout.decode("utf-8", "replace") if isinstance(
                proc.stdout, bytes) else str(proc.stdout or "")
            line = [ln for ln in text.strip().splitlines() if ln.startswith(target + ":")]
            out[target] = line[-1] if line else f"{target}: promote exit {proc.returncode}"
        except (OSError, subprocess.SubprocessError) as e:
            out[target] = f"{target}: promote did not run ({type(e).__name__})"
    return out


def banked_records(run_objs, known_keys):
    """Run records in the merged list that were not in the tree before."""
    return [
        o for o in run_objs
        if json.dumps(o, sort_keys=True) not in known_keys and "target" in o
    ]


def ledger_block(rig, grow_no, report, new_records, resources=None):
    """The grow's ledger block for the standing orders, file-wrapped."""
    entries, arcs = report["totals"]
    crashes = sum(o.get("crashes", 0) for o in new_records)
    tried = sum(o.get("tried", 0) for o in new_records)
    seeds = sorted({o.get("seed") for o in new_records if o.get("seed") is not None})
    head = f"  de_dust2 {grow_no} ({rig}): {entries} entries, {arcs} arcs, {crashes} crashes filed."
    body = (
        f"  Banked by rig_bank from the rig's own tree under section M"
        f" item 7: {len(new_records)} run records, {tried:,} children"
        f" (seeds {', '.join(str(s) for s in seeds) if seeds else 'none recorded'});"
        f" totals from the merged tree."
    )
    if resources:
        body += f" Resources: {resources}."
    if report.get("rig_head"):
        body += f" The rig's tree at {report['rig_head']}."
    settled = report.get("settled") or {}
    if settled:
        body += " Crash records replayed at main's head: " + "; ".join(
            settled[k] for k in sorted(settled)) + "."
    echoes = report.get("echoes") or 0
    if echoes:
        body += f" Retired echoes not re-banked: {echoes}."
    return head + "\n" + body + "\n"


def commit_message(rig, grow_no, report, new_records):
    """The bank's commit message: the campaign's status, in plain words.

    The subject is what the conductor reads in the commits list, so
    it carries the status at a glance: which rig, how big the merged
    corpus now stands, how many crashes this bank filed, and how
    many new run records it brought. The body repeats the status in
    sentences, with the merge's bookkeeping lines after.
    """
    entries, arcs = report["totals"]
    crashes = sum(o.get("crashes", 0) for o in new_records)
    tried = sum(o.get("tried", 0) for o in new_records)
    subject = (
        f"{rig} bank {grow_no}: {entries:,} entries, "
        f"{crashes} crashes, {len(new_records)} new runs"
    )
    lines = [
        subject,
        "",
        f"Corpus banked from the {rig} rig.",
        "",
        f"Status after this bank: {entries:,} entries and {arcs:,}"
        " coverage edges in the merged corpus.",
        f"New in this bank: {len(new_records)} run records,"
        f" {tried:,} children tested.",
        f"Crashes filed in this bank: {crashes}.",
    ]
    settled = report.get("settled") or {}
    if settled:
        lines.append(
            "Crash records replayed at main's head: "
            + "; ".join(settled[k] for k in sorted(settled)) + "."
        )
    echoes = report.get("echoes") or 0
    if echoes:
        lines.append(f"Retired echoes not re-banked: {echoes}.")
    if report.get("rig_head"):
        lines.append(f"The rig's git head: {report['rig_head']}.")
    lines += ["", f"Agent-Stamp: {STAMP}"]
    return "\n".join(lines)


def next_grow_no(orders_text, rig):
    """Grow numbers are per rig: count this rig's ledger lines, add one."""
    marker = f"({rig}):"
    count = sum(1 for ln in orders_text.splitlines() if marker in ln and "de_dust" in ln)
    return count + 1


def insert_ledger(orders_text, block):
    """Insert a ledger block at the end of the ledger region.

    The ledger is the file's last region today; the anchor is the
    last grow summary line, so a section added after the ledger
    later does not swallow the block. The block goes after that
    summary's wrapped continuation lines.
    """
    lines = orders_text.splitlines(keepends=True)
    anchor = None
    for i, ln in enumerate(lines):
        if "de_dust" in ln and " entries, " in ln and " arcs, " in ln:
            anchor = i
    if anchor is None:
        return orders_text + block
    j = anchor + 1
    while j < len(lines) and lines[j].startswith("  "):
        j += 1
    lines.insert(j, block)
    return "".join(lines)


def _git(args, cwd, pat=None):
    url = REPO_URL
    if pat:
        url = f"https://x-access-token:{pat}@github.com/Pigeon-Home/homing-pigeon.git"
    args = [a.replace(REPO_URL, url) for a in args]
    proc = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=300
    )
    if proc.returncode != 0:
        raise Refusal(f"git {' '.join(args[:2])} failed (output withheld)")
    return proc.stdout


HOLD_EXIT = 75
"""Exit when docs/use/muster.hold stands on main: retry next cycle."""


def muster_holds(clone):
    """True when the conductor's muster flag stands in this clone of main.

    The flag is the file's presence (Q109). A line in status.txt is a
    seat's own line and does not carry a global hold.
    """
    return os.path.exists(os.path.join(clone, "docs", "use", "muster.hold"))


def bank(rig, corpus_dir, pat_file, resources=None, dry_run=False):
    with open(pat_file, encoding="utf-8") as fh:
        pat = fh.read().strip()
    # Snapshot the rig's corpus first: the bank then reads a still
    # copy even if the rig's grow resets its tree mid-bank.
    snap = tempfile.mkdtemp(prefix="rig-bank-snap-")
    work = tempfile.mkdtemp(prefix="rig-bank-")
    try:
        return _bank_inner(rig, corpus_dir, pat, snap, work,
                           resources, dry_run)
    finally:
        # A bank that leaves its throwaway clones behind fills the
        # rig's disk a timer tick at a time; both temp trees go on
        # every path out, banked, refused or dry.
        shutil.rmtree(snap, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def _bank_inner(rig, corpus_dir, pat, snap, work, resources, dry_run):
    snap_corpus = os.path.join(snap, "de_dust")
    shutil.copytree(corpus_dir, snap_corpus)
    _, snap_runs = read_jsonl(os.path.join(snap_corpus, "runs.jsonl"))
    snap_keys = {json.dumps(o, sort_keys=True) for o in snap_runs}

    clone = os.path.join(work, "clone")
    _git(["clone", "-q", REPO_URL, clone], cwd=work, pat=pat)
    if muster_holds(clone):
        print("rig_bank: muster holds, nothing merged, nothing pushed")
        return HOLD_EXIT
    orders_path = os.path.join(clone, ORDERS_REL)
    with open(orders_path, encoding="utf-8") as fh:
        orders_text = fh.read()
    grow_no = next_grow_no(orders_text, rig)

    tree_corpus = os.path.join(clone, CORPUS_REL)
    _, tree_runs_before = read_jsonl(os.path.join(tree_corpus, "runs.jsonl"))
    tree_keys = {json.dumps(o, sort_keys=True) for o in tree_runs_before}
    report = merge_corpus(tree_corpus, snap_corpus)
    new_records = banked_records(report["run_objs"], tree_keys)
    fresh = [o for o in new_records
             if json.dumps(o, sort_keys=True) in snap_keys]
    changed = report["entries"] or report["crashes"] or fresh
    if not changed:
        print("rig_bank: nothing new to bank")
        return 0
    if report["crashes"]:
        report["settled"] = settle_crashes(clone, report)
    report["rig_head"] = tree_head(corpus_dir)
    block = ledger_block(rig, grow_no, report, fresh, resources)
    with open(orders_path, "w", encoding="utf-8") as fh:
        fh.write(insert_ledger(orders_text, block))
    if dry_run:
        print(block)
        print("rig_bank: dry run, nothing pushed")
        return 0
    _git(["add", "-A"], cwd=clone)
    _git(
        ["-c", "user.name=Muse", "-c", "user.email=muse@localhost",
         "commit", "-q", "-m",
         commit_message(rig, grow_no, report, fresh)],
        cwd=clone,
    )
    for _ in range(4):
        try:
            _git(["push", "-q", REPO_URL, "HEAD:main"], cwd=clone, pat=pat)
            break
        except Refusal:
            _git(["fetch", "-q", REPO_URL, "main"], cwd=clone, pat=pat)
            _git(["reset", "--hard", "FETCH_HEAD", "-q"], cwd=clone)
            # A muster called while this bank ran lands as the commit
            # that refused the push: read the new head before merging
            # on it, or the retry banks straight through the hold.
            if muster_holds(clone):
                print("rig_bank: muster holds, nothing merged, nothing pushed")
                return HOLD_EXIT
            # The merge is idempotent; redo it on the new head.
            with open(orders_path, encoding="utf-8") as fh:
                orders_text = fh.read()
            grow_no = next_grow_no(orders_text, rig)
            _, tree_runs_before = read_jsonl(os.path.join(tree_corpus, "runs.jsonl"))
            tree_keys = {json.dumps(o, sort_keys=True) for o in tree_runs_before}
            report = merge_corpus(tree_corpus, snap_corpus)
            new_records = banked_records(report["run_objs"], tree_keys)
            fresh = [o for o in new_records
                     if json.dumps(o, sort_keys=True) in snap_keys]
            if report["crashes"]:
                report["settled"] = settle_crashes(clone, report)
            report["rig_head"] = tree_head(corpus_dir)
            block = ledger_block(rig, grow_no, report, fresh, resources)
            with open(orders_path, "w", encoding="utf-8") as fh:
                fh.write(insert_ledger(orders_text, block))
            _git(["add", "-A"], cwd=clone)
            _git(
                ["-c", "user.name=Muse", "-c", "user.email=muse@localhost",
                 "commit", "-q", "-m",
                 commit_message(rig, grow_no, report, fresh)],
                cwd=clone,
            )
    else:
        print("rig_bank: the push did not land after retries", file=sys.stderr)
        return 4
    remote = _git(["ls-remote", REPO_URL, "main"], cwd=work, pat=pat).split()[0]
    head = _git(["rev-parse", "HEAD"], cwd=clone).strip()
    if remote != head:
        print("rig_bank: the push did not land (remote ref differs)", file=sys.stderr)
        return 4
    print(block)
    print(f"rig_bank: banked as {head[:9]}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rig", required=True, help='ledger rig name, e.g. "Germany rig"')
    ap.add_argument("--corpus", required=True, help="the rig's runner/tests/de_dust directory")
    ap.add_argument("--pat-file", required=True, help="file holding the GitHub PAT (read at use time)")
    ap.add_argument("--resources", help="the grow's resources line, quoted into the ledger")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        return bank(args.rig, args.corpus, args.pat_file, args.resources, args.dry_run)
    except Refusal as exc:
        print(f"rig_bank: refusal: {exc}", file=sys.stderr)
        return 2
    except TornRead as exc:
        print(f"rig_bank: torn read: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
