#!/usr/bin/env python3
# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Read the live capture, compute its facts, keep the docs honest.

    python3 runner/tools/live_capture.py              # the facts, as text
    python3 runner/tools/live_capture.py --markdown   # the facts block
    python3 runner/tools/live_capture.py --check-doc docs/use/live-examples.md
    python3 runner/tools/live_capture.py --write-doc docs/use/live-examples.md

The capture is docs/reports/live-2026-10-25/: three days of the
campaign rig, scrubbed (its README says how). Everything a page says
about that run is either a verbatim quote from these files or a
number this tool computes from them:

- A page's facts block sits between ``<!-- live-facts:begin -->`` and
  ``<!-- live-facts:end -->`` and is written by --write-doc;
  --check-doc fails when the block no longer matches the data.
- runner/tests/test_live_capture.py checks every quoted line in
  docs/use/live-examples.md against the files it says it came from.

Stdlib only. The 19,227 campaign records are one gzipped JSON line
each, in loop order (campaign-results.jsonl.gz), not 19,227 files:
the release snapshot carries every tracked file onto every box.
"""
import argparse
import collections
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CAPTURE = os.path.join(ROOT, "docs", "reports", "live-2026-10-25")
BEGIN = "<!-- live-facts:begin -->"
END = "<!-- live-facts:end -->"


_LEVELS = ("[DEBUG]", "[INFO]", "[WARN]", "[ERROR]")


def path(name, capture=CAPTURE):
    return os.path.join(capture, *name.split("/"))


def read_text(name, capture=CAPTURE):
    """A capture file's text; a .gz is read through gzip."""
    p = path(name, capture)
    if p.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            return fh.read()
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def jsonl(name, capture=CAPTURE):
    """Every JSON object in a .jsonl or .jsonl.gz capture file."""
    out = []
    for line in read_text(name, capture).splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def records(capture=CAPTURE):
    """The campaign's per-job records, in loop order."""
    return jsonl("campaign-results.jsonl.gz", capture)


def kind_of(record):
    """loop-012-workdir -> workdir."""
    return record["name"].split("-", 2)[2]


def _pct(values, p):
    ordered = sorted(values)
    return ordered[int(round(p * (len(ordered) - 1)))]


def facts(capture=CAPTURE):
    """The numbers the docs may quote, all computed here."""
    recs = records(capture)
    results = [r["result"] for r in recs if isinstance(r.get("result"), dict)]
    kinds = collections.Counter(kind_of(r) for r in recs)
    exits = collections.defaultdict(collections.Counter)
    for r in recs:
        exits[kind_of(r)][(r.get("result") or {}).get("exit_code")] += 1
    run = [x["duration_sec"] for x in results]
    trip = [r["elapsed_sec"] for r in recs
            if "elapsed_sec" in r and not r.get("result_email_sent")]
    mail = [r["elapsed_sec"] for r in recs
            if "elapsed_sec" in r and r.get("result_email_sent")]
    events = jsonl("security-events.jsonl", capture)
    pressure = [e for e in events if e.get("type") == "resource_pressure"]
    peaks = {}
    for e in pressure:
        for k, v in (e.get("resources") or {}).items():
            peaks[k] = max(peaks.get(k, 0.0), v)
    rejections = collections.Counter(
        e.get("reason") for e in events if e.get("type") == "auth_rejection")
    ledger = jsonl("oracle-learning.jsonl", capture)
    predictions = [x for x in ledger if x.get("type") == "prediction"]
    recon = [x for x in ledger if x.get("type") == "reconciliation"]
    classes = collections.Counter(x.get("classification") for x in recon)
    missed_exit = collections.Counter(
        (x.get("outcome") or {}).get("exit_code")
        for x in recon if x.get("classification") == "incorrect")
    log = read_text("runner.log", capture).splitlines()
    levels = collections.Counter()
    for line in log:
        parts = line.split(" ", 3)
        if len(parts) >= 3 and parts[2] in _LEVELS:
            levels[parts[2].strip("[]")] += 1
    succeeded = sum(1 for x in results if x.get("exit_code") == 0)
    return {
        "jobs": len(recs),
        "kinds": dict(sorted(kinds.items())),
        "exit_codes": {k: dict(v) for k, v in sorted(exits.items())},
        "results": len(results),
        "verified": sum(1 for r in recs if r.get("verify_rc") == 0),
        "timed_out": sum(1 for x in results if x.get("timed_out")),
        "views": dict(collections.Counter(x.get("view") for x in results)),
        "succeeded": succeeded,
        "run_sec": {"p50": _pct(run, .5), "p95": _pct(run, .95),
                    "max": max(run)},
        "round_trip_sec": {"p50": _pct(trip, .5), "p95": _pct(trip, .95),
                           "p99": _pct(trip, .99), "max": max(trip)},
        "mail_round_trips": len(mail),
        "mail_round_trip_sec": {"p50": _pct(mail, .5), "max": max(mail)}
        if mail else None,
        "first_completed": min(x["completed_at"] for x in results),
        "last_completed": max(x["completed_at"] for x in results),
        "resource_pressure": len(pressure),
        "pressure_by_resource": dict(collections.Counter(
            k for e in pressure for k in (e.get("resources") or {}))),
        "pressure_peaks": {k: round(v, 4) for k, v in sorted(peaks.items())},
        "auth_rejections": dict(rejections),
        "predictions": len(predictions),
        "prediction_verdicts": dict(collections.Counter(
            x.get("verdict") for x in predictions)),
        "reconciliations": len(recon),
        "reconciled": dict(classes),
        "missed_exit_codes": dict(missed_exit),
        "log_lines": len(log),
        "log_levels": dict(levels),
    }


def _n(x):
    return "{:,}".format(x)


def markdown(f):
    """The facts block, as the docs carry it."""
    rows = []
    for kind, count in f["kinds"].items():
        codes = ", ".join("exit %s x %s" % (c, _n(n)) for c, n in
                          sorted(f["exit_codes"][kind].items(),
                                 key=lambda kv: str(kv[0])))
        rows.append("| `%s` | %s | %s |" % (kind, _n(count), codes))
    rt, run = f["round_trip_sec"], f["run_sec"]
    acc = 100.0 * f["reconciled"].get("correct", 0) / max(1, f["reconciliations"])
    base = 100.0 * f["succeeded"] / max(1, f["results"])
    peaks = ", ".join("%s %.1f%%" % (k, 100 * v)
                      for k, v in f["pressure_peaks"].items())
    by_res = ", ".join("%s %s" % (_n(v), k) for k, v in
                       sorted(f["pressure_by_resource"].items()))
    rej = ", ".join("%s %s" % (_n(v), k) for k, v in
                    sorted(f["auth_rejections"].items()))
    verdicts = ", ".join("`%s` x %s" % (k, _n(v)) for k, v in
                         sorted(f["prediction_verdicts"].items()))
    missed = ", ".join("exit %s x %s" % (k, _n(v)) for k, v in
                       sorted(f["missed_exit_codes"].items(),
                              key=lambda kv: str(kv[0])))
    lines = [
        BEGIN,
        "<!-- Written by runner/tools/live_capture.py --write-doc; "
        "edit the tool, not this block. -->",
        "",
        "**%s jobs**, completed %s to %s. Every one came back: %s "
        "results, %s verified, %s timed out, every result at view `%s`."
        % (_n(f["jobs"]), f["first_completed"], f["last_completed"],
           _n(f["results"]), _n(f["verified"]), _n(f["timed_out"]),
           "`, `".join(sorted(f["views"]))),
        "",
        "| Job | Runs | Exit codes |",
        "|-----|------|------------|",
    ] + rows + [
        "",
        "- **Time on the box** (the script itself): median %.3f s, "
        "p95 %.3f s, longest %.3f s." % (run["p50"], run["p95"], run["max"]),
        "- **Round trip** (signed job handed over to verified result "
        "read), file transport: median %.1f s, p95 %.1f s, p99 %.1f s, "
        "longest %.1f s. The %s results that went back by mail, before "
        "the mail-off: median %.1f s, longest %.1f s."
        % (rt["p50"], rt["p95"], rt["p99"], rt["max"],
           _n(f["mail_round_trips"]), f["mail_round_trip_sec"]["p50"],
           f["mail_round_trip_sec"]["max"]),
        "- **Resource pressure**: %s events (%s), peaks %s."
        % (_n(f["resource_pressure"]), by_res, peaks),
        "- **Refused at the door**: %s." % rej,
        "- **Oracle predictions** (deterministic mode): %s, all %s. "
        "Of %s reconciled, %s were right (%.1f%%); that is the share of "
        "jobs that succeed (%.1f%%), and every miss was a failing job "
        "(%s). The ledger keeps its newest lines, so it covers the last "
        "%s jobs, not all %s."
        % (_n(f["predictions"]), verdicts, _n(f["reconciliations"]),
           _n(f["reconciled"].get("correct", 0)), acc, base, missed,
           _n(f["reconciliations"]), _n(f["jobs"])),
        "- **runner.log**: %s lines kept (%s)."
        % (_n(f["log_lines"]), ", ".join(
            "%s %s" % (_n(v), k) for k, v in
            sorted(f["log_levels"].items(), key=lambda kv: -kv[1]))),
        "",
        END,
    ]
    return "\n".join(lines)


def _replace_block(text, block):
    if BEGIN not in text or END not in text:
        raise SystemExit("no %s ... %s block in the page" % (BEGIN, END))
    head = text[:text.index(BEGIN)]
    tail = text[text.index(END) + len(END):]
    return head + block + tail


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--check-doc", metavar="PAGE")
    ap.add_argument("--write-doc", metavar="PAGE")
    a = ap.parse_args(argv)
    f = facts()
    if a.check_doc or a.write_doc:
        page = a.check_doc or a.write_doc
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        new = _replace_block(text, markdown(f))
        if a.check_doc:
            if new != text:
                print("%s: the live facts block is stale; run "
                      "runner/tools/live_capture.py --write-doc %s"
                      % (page, page))
                return 1
            print("%s: live facts current" % page)
            return 0
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(new)
        print("wrote the live facts block into %s" % page)
        return 0
    if a.markdown:
        print(markdown(f))
    else:
        print(json.dumps(f, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
