#!/usr/bin/env python3
"""Job Fuzz: a Homing Pigeon user extension (example sense).

A sense that fuzzes the jobs this box has already run. Every
other sense observes the box; this one probes it, patiently,
in the background: it keeps a corpus of real verified jobs
(the runner's retained records), mutates them with
grammar-shaped mutations, and runs the variants through the
runner's own validation and confined execution -- the bucket
-- to learn where the neighborhood of a real job stops
behaving like the job itself. The findings file as Oracle
signals, and because they arrive whenever they arrive, they
serve as context for future opinions, never as a gate on the
job that seeded them. The Oracle is always some jobs ahead
of the campaign; that lag is the design, not a defect.

The machinery is the fuzzing half of a platform fuzzer
(DRU's note: OneFuzz is a platform as a service as it stands;
what an extension needs is its components, lifted to run
locally): a mutation engine, a corpus that distills, crash
triage that dedupes. The service half -- scale-out, corpus
sync across machines, scheduling planes, notifications --
stays behind. What remains fits in one small process the
operator runs on their own cadence, like every sense.

Each alert names one of the signals declared in
extension.json:

- variant_hard_failure (high)  a variant broke the run
                    itself: the confined execution timed
                    out, or the execution path errored
                    around the run. A hang is a hard
                    failure; so is a variant the tooling
                    could not carry.
- variant_divergence (medium)  a variant ran and its
                    outcome class differs from the seed
                    job's recorded outcome class -- zero
                    vs nonzero exit, ran vs refused at
                    validation, finished vs timed out. The
                    detail names the mutator and both
                    classes.
- coverage_novelty (info)  the first time a (mutator,
                    stage, outcome class) combination is
                    observed, ever: the campaign reached a
                    region it had not reached before.
                    Filed once per combination; the triage
                    memory is state, bounded like
                    everything else here.

The corpus discipline: seeds are the runner's retained
job records under <runner base dir>/retained -- kind
"exec", with a script and a recorded exit code. The
retained script is what the runner retained (its records
cap scripts at 500 characters; a variant fuzzes the
retained text, which is stated here rather than hidden).
The corpus is bounded both ways, by count
(corpus_max_jobs, default 200) and by age
(corpus_max_age_days, default 30), both operator-tunable;
the oldest seeds fall off first. A seed's recorded outcome
class is the divergence baseline, so a record the runner
prunes is still baselined from the sense's own state until
the corpus bound evicts it.

The idle discipline: a campaign runs only when the box is
idle -- no job record has landed within idle_after_sec
(default 600) and, where the platform offers it, the
one-minute load average sits under idle_load_max (default
1.0). Idleness is re-checked before every variant; a fresh
job landing mid-campaign stops the campaign where it
stands. Variants per pass are capped (max_variants_per_pass,
default 8) across a few seeds (max_seeds_per_pass, default
3, variants_per_seed, default 4), and each variant run is
bounded by variant_timeout_sec (default 30).

The variant discipline: a variant is a mutation of a
verified job, so its signature no longer verifies BY
CONSTRUCTION. Variants are never admitted through the job
path, never mailed, never signed. The sense writes each
variant to its archive (see below) and hands the file to
the runner's --run-variant mode through the runner_cmd
tunable: that mode is a local operator door in the core
that copies an allowlist of job keys (script, interpreter,
args, env, a capped timeout), drops everything else --
files, script_url, signatures, delivery fields -- and runs
what remains through the same validation and confined
execution as a real exec job, printing the outcome as JSON.
The sense never holds the shared secret and never needs it.

The triage discipline: everything the campaign observes is
a candidate finding -- hard failures, divergence, coverage
novelties -- and the triage memory decides what files.
Hard failures file once per REASON BUCKET -- the
normalized refusal/error reason, so ten seeds that hit
the same validation hole file one signal whose detail
carries the bucket's count and example variants -- and
divergences file once per (seed, mutator, class); both
may file again after filed_cooldown_sec (default a week);
a novelty files once per combination, ever. Alerts per
pass are capped (max_alerts_per_pass, default 20), hard
failures first, then divergences, then novelties, so a
rich pass cannot flood the ingest caps; what the cap
drops is counted in the pass's state, not lost silently.
Every variant the campaign runs is archived under the
work dir (default: .job-fuzz-variants next to this
script; pruned to max_archived_variants, default 200,
oldest first) so any finding reproduces by handing the
same file to --run-variant again.

The corpus learns. A variant that reaches a coverage
novelty is PROMOTED into a distilled tier of the corpus
(bounded by distilled_max_jobs, default 50, and the same
age bound as seeds): later campaigns mutate the distilled
variants as seeds in their own right, so a campaign starts
from everything earlier campaigns discovered instead of
from the same retained jobs forever. Two mutators widen
the neighborhood further: splice recombines lines from
two different seeds, and dictionary injects tokens
harvested from the corpus's own scripts -- the commands,
flags, and paths this box actually runs.

Two mutators are relation probes. blank_line and
trailing_blank are semantics-preserving by construction,
so they carry an EXPECTED relation: same outcome class
and same output digest as the seed. A probe whose promise
breaks files a divergence that names the broken relation
-- a much sharper fact than an unexplained class change.

Findings shrink before they file. A variant whose outcome
is interesting (a hard failure, or a class change) is
minimized in the campaign: lines are dropped while the
outcome's stage and class persist, bounded by
minimize_max_steps (default 12) re-runs, and the archived
variant is the minimized one -- the repro the Oracle
reads is the smallest one the campaign could make.

Seeds earn energy. The state remembers, per seed, how
many variants ran and how many produced novelties, hard
failures, and divergences; seed selection spends the
pass's budget on the seeds with the best yield first,
with recency as the tiebreak, instead of always taking
the newest few.

With runner_cmd empty (the default) there is nothing to
execute variants with: the sense still maintains its
corpus from the retained records and files nothing -- the
same graceful half-configured shape as a watcher whose
watched path is unset.

The machinery is deliberately boring, in the Job Watcher
example's shape. read_live() is the only function that
touches the machine (the corpus scan, the idle probe, the
campaign itself); decide() -- readings plus manifest plus
last pass's state, out come alerts and the new state -- is
pure, so the whole decision surface is testable against
fixture readings. Current time arrives as readings["now"],
never from a clock inside decide(). A missing retained
directory, an unreadable or half-written record, a runner
that will not answer: each is skipped quietly -- absence
is a normal case, not an error.

Run on the same machine as the runner, it delivers
locally: --local-dir <runner base dir> signs each payload
with this sense's key (read from the environment variable
named by --secret-env) and drops it into the runner's
local inbox, or pushes it to the runner's loopback
listener when --local-port is given. Same envelope, same
signature -- only the transport differs
(docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line.

--samples FILE reads a readings dict from a JSON file
instead of the machine: the way to try the sense (and test
it) against known campaign outcomes, on any box at all.
The retained directory it reads comes from the
runner_base_dir tunable (or --runner-dir, which wins);
the campaign's runner command from the runner_cmd tunable
(or --runner-cmd, which wins).
"""
import argparse
import hashlib
import json
import os
import random
import shlex
import subprocess
import sys
import time

_MAX_RECORD_BYTES = 1 << 20
_SEED_SCRIPT_CAP = 500
_FILER_CAP = 1000
_NOVELTY_CAP = 2000
_BUCKET_CAP = 200
_ENERGY_CAP = 1000
_DICTIONARY_CAP = 256
_CLASSES = ("refused", "error", "timeout", "exit0", "nonzero")


# --- small tolerant helpers (the sibling shape) --------------------

def _is_number(value):
    """A finite int or float, never a bool.

    Infinity and NaN are floats, and an integer too large for a float
    is an int, but none of them is a usable tunable: a 10**400
    corpus_max_age_days reached float() in _tunable and crashed
    decide() with OverflowError where inf already read as the
    documented default. Each reads as "not a number" so the default
    applies (the shape every other example extension carries).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def _num(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    f = float(value)
    return str(int(f)) if f == int(f) else ("%g" % f)


def _tunables(manifest):
    t = manifest.get("tunables") if isinstance(manifest, dict) \
        else None
    return t if isinstance(t, dict) else {}


def _tunable(tunables, key, default):
    v = tunables.get(key)
    return float(v) if _is_number(v) else float(default)


def _positive_tunable(tunables, key, default):
    """A strictly positive number; zero and below read as the default.

    A zero age bound disabled the corpus age limit and a zero cooldown
    refiled a finding at once; neither is a duration.
    """
    v = tunables.get(key)
    return float(v) if _is_number(v) and v > 0 else float(default)


def _int_tunable(tunables, key, default):
    v = tunables.get(key)
    return int(v) if _is_number(v) else int(default)


def _str_tunable(tunables, key, default=""):
    v = tunables.get(key)
    return v if isinstance(v, str) else default


def _exit_class(stage, exit_code, timed_out):
    """One outcome -> its class, the divergence currency.

    refused / error / timeout / exit0 / nonzero. The seed
    baseline uses the same classes (a retained record's
    stage is "ran" unless it timed out).
    """
    if stage == "refused":
        return "refused"
    if stage == "error":
        return "error"
    if timed_out:
        return "timeout"
    if _is_number(exit_code) and int(exit_code) == 0:
        return "exit0"
    return "nonzero"


# --- the mutation engine --------------------------------------------
#
# Pure and seeded: a variant is a function of the seed job,
# the mutator, and a per-campaign seed, so any finding
# reproduces by re-running the same triple. Mutators return
# a dict of job fields to REPLACE on the seed's job, or None
# when the seed offers nothing for them to bite on.

def _script_lines(script):
    return script.split("\n")


def _mut_truncate(job, rng, ctx):
    lines = _script_lines(job.get("script") or "")
    if len(lines) < 2:
        return None
    cut = rng.randrange(1, len(lines))
    return {"script": "\n".join(lines[:cut])}


def _mut_duplicate_line(job, rng, ctx):
    lines = _script_lines(job.get("script") or "")
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    if not nonempty:
        return None
    i = rng.choice(nonempty)
    lines.insert(i, lines[i])
    return {"script": "\n".join(lines)}


def _mut_drop_line(job, rng, ctx):
    lines = _script_lines(job.get("script") or "")
    if len(lines) < 2:
        return None
    i = rng.randrange(len(lines))
    del lines[i]
    return {"script": "\n".join(lines)}


_BOUNDARY_NUMBERS = ("0", "-1", "2147483647",
                     "9223372036854775807",
                     "99999999999999999999999999")


def _mut_boundary_number(job, rng, ctx):
    script = job.get("script") or ""
    spots = []
    cur = ""
    for idx, ch in enumerate(script):
        if ch.isdigit():
            cur += ch
            if idx == len(script) - 1 or not script[idx + 1].isdigit():
                spots.append((idx - len(cur) + 1, idx + 1))
                cur = ""
        else:
            cur = ""
    if not spots:
        return None
    start, end = rng.choice(spots)
    return {"script": script[:start]
            + rng.choice(_BOUNDARY_NUMBERS) + script[end:]}


def _mut_quote_break(job, rng, ctx):
    script = job.get("script") or ""
    quotes = [i for i, ch in enumerate(script) if ch in "\"'"]
    if quotes:
        i = rng.choice(quotes)
        flip = "'" if script[i] == '"' else '"'
        return {"script": script[:i] + flip + script[i + 1:]}
    lines = _script_lines(script)
    lines.append('echo "unterminated')
    return {"script": "\n".join(lines)}


def _mut_unicode_edge(job, rng, ctx):
    script = job.get("script") or ""
    lines = _script_lines(script)
    lines.append("# edge: é​\U0001F600")
    return {"script": "\n".join(lines)}


def _mut_empty_script(job, rng, ctx):
    if not (job.get("script") or ""):
        return None
    return {"script": ""}


def _mut_oversized_line(job, rng, ctx):
    lines = _script_lines(job.get("script") or "")
    lines.append("echo " + "a" * 65536)
    return {"script": "\n".join(lines)}


def _mut_null_byte(job, rng, ctx):
    script = job.get("script") or ""
    if len(script) < 2:
        return None
    i = rng.randrange(1, len(script))
    return {"script": script[:i] + "\x00" + script[i:]}


def _mut_interpreter_string(job, rng, ctx):
    """The classic malformed shape: interpreter as a bare
    string. Validation must refuse it; if it ever runs, the
    refusal path has a hole and the divergence is the news."""
    return {"interpreter": "sh"}


def _mut_blank_line(job, rng, ctx):
    """Relation probe: an inserted blank line preserves a
    script's meaning in every interpreter this box runs,
    so the variant PROMISES the seed's class and digest."""
    lines = _script_lines(job.get("script") or "")
    if not lines:
        return None
    lines.insert(rng.randrange(len(lines) + 1), "")
    return {"script": "\n".join(lines)}


def _mut_trailing_blank(job, rng, ctx):
    """Relation probe: trailing blank lines are inert."""
    script = job.get("script") or ""
    if not script:
        return None
    return {"script": script + "\n" * (1 + rng.randrange(3))}


def _mut_splice(job, rng, ctx):
    """Crossover: a segment of a second seed's script lands
    inside this one. Single-seed mutation cannot recombine;
    this is the operator that can."""
    donor = ctx.get("donor") if isinstance(ctx, dict) else None
    if not isinstance(donor, dict):
        return None
    mine = _script_lines(job.get("script") or "")
    theirs = [ln for ln in _script_lines(
        donor.get("script") or "") if ln.strip()]
    if not mine or not theirs:
        return None
    start = rng.randrange(len(theirs))
    take = 1 + rng.randrange(min(3, len(theirs) - start))
    segment = theirs[start:start + take]
    at = rng.randrange(len(mine) + 1)
    return {"script": "\n".join(mine[:at] + segment + mine[at:])}


_TOKEN_SPLIT = (" \t\"'=;|&<>(){}[]`$#")


def _mut_dictionary(job, rng, ctx):
    """Inject one token harvested from the corpus's own
    scripts: the vocabulary this box actually runs with."""
    tokens = ctx.get("dictionary") if isinstance(ctx, dict) \
        else None
    if not tokens:
        return None
    token = rng.choice(list(tokens))
    lines = _script_lines(job.get("script") or "")
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    if nonempty and rng.random() < 0.5:
        i = rng.choice(nonempty)
        lines[i] = lines[i] + " " + token
    else:
        lines.insert(rng.randrange(len(lines) + 1), token)
    return {"script": "\n".join(lines)}


MUTATORS = {
    "truncate": _mut_truncate,
    "duplicate_line": _mut_duplicate_line,
    "drop_line": _mut_drop_line,
    "boundary_number": _mut_boundary_number,
    "quote_break": _mut_quote_break,
    "unicode_edge": _mut_unicode_edge,
    "empty_script": _mut_empty_script,
    "oversized_line": _mut_oversized_line,
    "null_byte": _mut_null_byte,
    "interpreter_string": _mut_interpreter_string,
    "blank_line": _mut_blank_line,
    "trailing_blank": _mut_trailing_blank,
    "splice": _mut_splice,
    "dictionary": _mut_dictionary,
}

# Mutators whose output carries an expected relation to the
# seed's outcome: "identity" means same outcome class AND
# same output digest. decide() checks the promise.
RELATION_MUTATORS = {"blank_line": "identity",
                     "trailing_blank": "identity"}


def _build_dictionary(seeds):
    """The corpus's own vocabulary: tokens from every seed
    script, deduped, sorted, capped. Deterministic in the
    seed set, so a campaign's variants reproduce."""
    tokens = set()
    for seed in seeds:
        if not isinstance(seed, dict):
            continue
        script = seed.get("script") or ""
        word = ""
        for ch in script + " ":
            if ch in _TOKEN_SPLIT or ch == "\n":
                if 3 <= len(word) <= 40 and any(
                        c.isalnum() for c in word):
                    tokens.add(word)
                word = ""
            else:
                word += ch
    return sorted(tokens)[:_DICTIONARY_CAP]


def build_variant(seed_job, mutator, campaign_seed,
                  donor_job=None, dictionary=()):
    """One variant job dict, or None when the mutator cannot
    bite. Deterministic in (seed job, mutator, campaign_seed)
    plus, for splice and dictionary, the donor and the
    dictionary -- the extra inputs are hashed into the same
    material, so a variant's id names everything it came
    from.
    """
    fn = MUTATORS.get(mutator)
    if fn is None:
        return None
    extra = ""
    if mutator == "splice" and isinstance(donor_job, dict):
        extra = "|donor:" + (donor_job.get("job_id") or "") \
            + "|" + (donor_job.get("script") or "")
    elif mutator == "dictionary" and dictionary:
        extra = "|dict:" + hashlib.sha384(
            "\n".join(dictionary).encode(
                "utf-8", "surrogateescape")).hexdigest()[:16]
    material = (str(campaign_seed) + "|" + mutator + "|"
                + (seed_job.get("job_id") or "") + "|"
                + (seed_job.get("script") or "")
                + extra).encode("utf-8", "surrogateescape")
    rng = random.Random(
        int.from_bytes(hashlib.sha384(material).digest()[:8],
                       "big"))
    ctx = {"donor": donor_job, "dictionary": dictionary}
    fields = fn(seed_job, rng, ctx)
    if fields is None:
        return None
    variant = {"job_id": "fuzz-" + hashlib.sha384(
        material).hexdigest()[:24],
        "kind": "exec",
        "script": seed_job.get("script") or "",
        "mutator": mutator}
    variant.update(fields)
    return variant


# --- reading the machine ---------------------------------------------

def _record_seed(path, fallback_mtime):
    """One retained record -> one corpus seed, or None.

    Tolerant by design: only kind "exec" records carrying a
    script and a recorded exit code seed the corpus. The
    job's stdout is never touched.
    """
    try:
        if os.path.getsize(path) > _MAX_RECORD_BYTES:
            return None
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("kind") != "exec":
        return None
    script = record.get("script")
    if not isinstance(script, str) or not script:
        return None
    exit_code = record.get("exit_code")
    if not _is_number(exit_code):
        return None
    saved_at = record.get("saved_at")
    if not _is_number(saved_at):
        saved_at = fallback_mtime
    if not _is_number(saved_at):
        return None
    job_id = record.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        job_id = os.path.basename(path)
        if job_id.endswith(".json"):
            job_id = job_id[:-5]
    return {"job_id": job_id,
            "script": script[:_SEED_SCRIPT_CAP],
            "exit_code": int(exit_code),
            "timed_out": bool(record.get("timed_out")),
            "digest": record.get("digest")
            if isinstance(record.get("digest"), str) else "",
            "saved_at": float(saved_at)}


def _scan_retained(base, cap):
    """(seeds, newest_mtime) from <base>/retained, oldest
    first. A missing store reads as empty. Never raises."""
    seeds = []
    newest = 0.0
    retained = os.path.join(base, "retained") if base else ""
    if retained and os.path.isdir(retained):
        try:
            names = sorted(os.listdir(retained))
        except OSError:
            names = []
        paths = []
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(retained, name)
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    paths.append((os.path.getmtime(path), path))
            except OSError:
                continue
        paths.sort()
        for mtime, _p in paths:
            if mtime > newest:
                newest = mtime
        if len(paths) > cap:
            paths = paths[-cap:]
        for mtime, path in paths:
            seed = _record_seed(path, mtime)
            if seed is not None:
                seeds.append(seed)
        seeds.sort(key=lambda s: s["saved_at"])
    return seeds, newest


def _box_idle(now, newest_job_at, idle_after_sec):
    """Idle = no fresh job AND (where offered) a quiet load."""
    if newest_job_at and now - newest_job_at < idle_after_sec:
        return False
    return True


def _load_quiet(idle_load_max):
    try:
        load1 = os.getloadavg()[0]
    except (OSError, AttributeError):
        return True  # the platform offers no load: no vote
    return load1 < idle_load_max


def _split_cmd(cmd):
    """Split an operator's runner_cmd for THIS platform.
    POSIX shlex eats backslashes, which mangles every
    Windows path in the command before it can run; the
    Windows split keeps backslashes and leaves the quotes
    on, so they come off here instead."""
    if os.name != "nt":
        return shlex.split(cmd)
    return _split_cmd_windows(cmd)


def _split_cmd_windows(cmd):
    parts = []
    for part in shlex.split(cmd, posix=False):
        if len(part) >= 2 and part[0] == part[-1] \
                and part[0] in "\"'":
            part = part[1:-1]
        parts.append(part)
    return parts


def _run_one_variant(runner_cmd, variant, work_dir, timeout_sec):
    """Write the variant, hand it to the runner's door, and
    read the outcome. Never raises: every failure shape is
    itself an outcome."""
    name = (variant.get("job_id") or "fuzz-variant") + ".json"
    path = os.path.join(work_dir, name)
    try:
        os.makedirs(work_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(variant, fh, sort_keys=True)
    except OSError as e:
        return {"stage": "error",
                "reason": f"cannot archive variant: {e}",
                "variant_file": name}
    cmd = []
    try:
        for part in _split_cmd(runner_cmd):
            cmd.append(part.replace("{variant}", path))
    except ValueError as e:
        return {"stage": "error",
                "reason": f"bad runner_cmd: {e}",
                "variant_file": name}
    if not any(path in part for part in cmd):
        cmd.append(path)
    try:
        proc = subprocess.run(cmd, capture_output=True,
                              text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return {"stage": "error",
                "reason": "variant run timed out (hang)",
                "variant_file": name}
    except OSError as e:
        return {"stage": "error",
                "reason": f"cannot run runner_cmd: {e}",
                "variant_file": name}
    report = None
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and "stage" in parsed:
            report = parsed
            break
    if report is None:
        return {"stage": "error",
                "reason": "runner printed no outcome "
                          f"(exit {proc.returncode})",
                "variant_file": name}
    report["variant_file"] = name
    return report


def _prune_archive(work_dir, cap):
    try:
        names = sorted(
            (os.path.getmtime(os.path.join(work_dir, n)), n)
            for n in os.listdir(work_dir) if n.endswith(".json"))
    except OSError:
        return
    for _mtime, name in names[:max(0, len(names) - cap)]:
        try:
            os.unlink(os.path.join(work_dir, name))
        except OSError:
            pass


def _seed_class(seed):
    forced = seed.get("force_class")
    if forced in _CLASSES:
        return forced
    return _exit_class("ran", seed.get("exit_code"),
                       seed.get("timed_out"))


def _distilled_seed(entry_id, entry):
    """One distilled-tier entry -> a seed in the scan's
    shape, or None. A distilled seed's recorded class is
    authoritative (a promoted refusal has no exit code to
    derive one from), so it rides as force_class."""
    if not isinstance(entry, dict):
        return None
    script = entry.get("script")
    if not isinstance(script, str) or not script:
        return None
    exit_code = entry.get("exit_code")
    saved_at = entry.get("saved_at")
    return {"job_id": entry_id, "script": script,
            "exit_code": int(exit_code)
            if _is_number(exit_code) else None,
            "timed_out": bool(entry.get("timed_out")),
            "force_class": entry.get("exit_class")
            if entry.get("exit_class") in _CLASSES else "",
            "digest": entry.get("digest")
            if isinstance(entry.get("digest"), str) else "",
            "saved_at": float(saved_at)
            if _is_number(saved_at) else 0.0,
            "distilled": True}


def _seed_score(entry):
    """A seed's energy: yield per run, smoothed so an
    untried seed starts near the middle of the pack."""
    if not isinstance(entry, dict):
        return 0.5
    def _n(k):
        v = entry.get(k)
        return int(v) if _is_number(v) else 0
    return (3.0 * _n("novel") + 2.0 * _n("hard")
            + _n("diverged") + 1.0) / (_n("runs") + 2.0)


def _minimize_variant(runner_cmd, variant, report, work_dir,
                      timeout_sec, budget):
    """Shrink an interesting variant while its outcome's
    stage and class persist: drop one line at a time, keep
    a drop only when a re-run through the door lands in the
    same stage and class. Returns (variant, report, steps).
    The archived file ends up holding the minimized
    variant, so the finding's repro is the smallest one
    the campaign could make. Trials run under the same
    timeout as the original run -- a shorter leash would
    misread slow scripts as hangs.
    """
    stage0 = report.get("stage") or "error"
    cls0 = _exit_class(stage0, report.get("exit_code"),
                       report.get("timed_out"))
    lines = (variant.get("script") or "").split("\n")
    if len(lines) < 2 or budget < 1:
        return variant, report, 0
    cur_variant, cur_report = variant, report
    cur_lines = lines
    steps = 0
    i = 0
    while i < len(cur_lines) and steps < budget \
            and len(cur_lines) > 1:
        trial = dict(cur_variant)
        trial["script"] = "\n".join(
            cur_lines[:i] + cur_lines[i + 1:])
        trial["job_id"] = cur_variant["job_id"] + "-min"
        rep = _run_one_variant(runner_cmd, trial, work_dir,
                               timeout_sec)
        steps += 1
        stage = rep.get("stage") or "error"
        if stage == stage0 and _exit_class(
                stage, rep.get("exit_code"),
                rep.get("timed_out")) == cls0:
            cur_lines = trial["script"].split("\n")
            cur_variant = dict(cur_variant)
            cur_variant["script"] = trial["script"]
            cur_report = rep
        else:
            i += 1
    if cur_variant["script"] != variant.get("script"):
        name = (variant.get("job_id") or "fuzz-variant") \
            + ".json"
        try:
            with open(os.path.join(work_dir, name), "w",
                      encoding="utf-8") as fh:
                json.dump(cur_variant, fh, sort_keys=True)
        except OSError:
            pass
        cur_report = dict(cur_report)
        cur_report["variant_file"] = name
    return cur_variant, cur_report, steps


def read_live(manifest, reader_state=None):
    """One snapshot: corpus seeds, the idle verdict, and --
    when the box is idle and a runner command is configured
    -- one campaign's outcomes.

    Returns {"now", "idle", "seeds", "outcomes"}. The
    campaign is bounded by the tunables and re-checks
    idleness before every variant; a fresh job landing
    mid-campaign stops it where it stands. Never raises.
    """
    tunables = _tunables(manifest)
    now = time.time()
    base = _str_tunable(tunables, "runner_base_dir")
    cap = _int_tunable(tunables, "max_records_per_pass", 500)
    if cap < 1:
        cap = 500
    seeds, newest = _scan_retained(base, cap)
    idle_after = _tunable(tunables, "idle_after_sec", 600.0)
    idle = _box_idle(now, newest, idle_after) and _load_quiet(
        _tunable(tunables, "idle_load_max", 1.0))
    readings = {"now": now, "idle": idle, "seeds": seeds,
                "outcomes": []}
    runner_cmd = _str_tunable(tunables, "runner_cmd")
    if not idle or not runner_cmd:
        return readings
    campaign_seed = reader_state.get("campaign_seed") \
        if isinstance(reader_state, dict) else None
    if not _is_number(campaign_seed):
        campaign_seed = int(now)
    readings["campaign_seed"] = campaign_seed
    here = os.path.dirname(os.path.abspath(__file__))
    work_dir = _str_tunable(tunables, "work_dir") or os.path.join(
        here, ".job-fuzz-variants")
    max_seeds = _int_tunable(tunables, "max_seeds_per_pass", 3)
    per_seed = _int_tunable(tunables, "variants_per_seed", 4)
    max_variants = _int_tunable(
        tunables, "max_variants_per_pass", 8)
    timeout_sec = _tunable(tunables, "variant_timeout_sec", 30.0)
    min_budget = _int_tunable(
        tunables, "minimize_max_steps", 12)
    # The pool: fresh retained seeds plus the distilled
    # tier the state carries (promoted variants from
    # earlier campaigns). A retained record wins a job_id
    # collision -- it is the fresher truth.
    pool = list(seeds)
    seen_ids = {s["job_id"] for s in pool}
    if isinstance(reader_state, dict):
        distilled = reader_state.get("distilled")
        if isinstance(distilled, dict):
            for entry_id, entry in distilled.items():
                seed = _distilled_seed(entry_id, entry)
                if seed is not None \
                        and entry_id not in seen_ids:
                    pool.append(seed)
                    seen_ids.add(entry_id)
    if not pool:
        return readings
    dictionary = _build_dictionary(pool)
    energy = reader_state.get("energy") \
        if isinstance(reader_state, dict) else None
    if not isinstance(energy, dict):
        energy = {}
    # Energy first, recency as the tiebreak: the pass's
    # budget goes to the seeds that have produced before.
    order = sorted(
        range(len(pool)),
        key=lambda i: (-_seed_score(energy.get(
            pool[i]["job_id"])), -pool[i]["saved_at"]))
    chosen = [pool[i] for i in order[:max_seeds]] \
        if max_seeds > 0 else []
    mutator_names = sorted(MUTATORS)
    ran = 0
    for seed in chosen:
        if ran >= max_variants:
            break
        picks = mutator_names[
            int(campaign_seed) % len(mutator_names):] \
            + mutator_names[:int(campaign_seed)
                              % len(mutator_names)]
        for mutator in picks[:per_seed]:
            if ran >= max_variants:
                break
            # Idleness is re-earned before every variant.
            _s, freshest = _scan_retained(base, 1)
            if not _box_idle(time.time(), freshest, idle_after):
                return readings
            seed_job = {"job_id": seed["job_id"],
                        "script": seed["script"]}
            donor = None
            if len(pool) > 1:
                at = pool.index(seed)
                donor = pool[(at + 1) % len(pool)]
            variant = build_variant(
                seed_job, mutator, campaign_seed,
                donor_job={"job_id": donor["job_id"],
                           "script": donor["script"]}
                if donor else None,
                dictionary=dictionary)
            if variant is None:
                continue
            report = _run_one_variant(
                runner_cmd, variant, work_dir, timeout_sec)
            var_cls = _exit_class(
                report.get("stage") or "error",
                report.get("exit_code"),
                report.get("timed_out"))
            interesting = report.get("stage") == "error" \
                or var_cls == "timeout" \
                or var_cls != _seed_class(seed)
            steps = 0
            if interesting and min_budget > 0:
                variant, report, steps = _minimize_variant(
                    runner_cmd, variant, report, work_dir,
                    timeout_sec, min_budget)
            outcome = report
            outcome["job_id"] = seed["job_id"]
            outcome["mutator"] = mutator
            outcome["orig_stage"] = "ran"
            outcome["orig_exit_code"] = seed.get("exit_code")
            outcome["orig_timed_out"] = seed.get("timed_out")
            if seed.get("force_class"):
                outcome["orig_class"] = seed["force_class"]
            outcome["orig_digest"] = seed.get("digest") or ""
            outcome["variant_id"] = variant["job_id"]
            outcome["variant_script"] = variant.get(
                "script") or ""
            if steps:
                outcome["min_steps"] = steps
            readings["outcomes"].append(outcome)
            ran += 1
    _prune_archive(work_dir, _int_tunable(
        tunables, "max_archived_variants", 200))
    return readings


# --- the decision: readings in, signals out (pure) -------------------

def _fresh_state():
    return {"corpus": {}, "novelty": [], "filed": {},
            "distilled": {}, "energy": {}, "buckets": {},
            "campaign_seed": 0, "campaigns": 0, "dropped_total": 0}


def _clean_distilled(raw, cap):
    distilled = {}
    if isinstance(raw, dict):
        for entry_id, entry in raw.items():
            if not isinstance(entry_id, str) \
                    or not isinstance(entry, dict):
                continue
            script = entry.get("script")
            saved_at = entry.get("saved_at")
            if not isinstance(script, str) or not script \
                    or not _is_number(saved_at):
                continue
            exit_code = entry.get("exit_code")
            distilled[entry_id] = {
                "script": script[:_SEED_SCRIPT_CAP],
                "exit_code": int(exit_code)
                if _is_number(exit_code) else None,
                "timed_out": bool(entry.get("timed_out")),
                "exit_class": entry.get("exit_class")
                if entry.get("exit_class") in _CLASSES else "",
                "digest": entry.get("digest")
                if isinstance(entry.get("digest"), str) else "",
                "saved_at": float(saved_at)}
    if len(distilled) > cap:
        keep = sorted(distilled.items(),
                      key=lambda kv: kv[1]["saved_at"])[-cap:]
        distilled = dict(keep)
    return distilled


def _clean_energy(raw):
    energy = {}
    if isinstance(raw, dict):
        for job_id, entry in raw.items():
            if not isinstance(job_id, str) \
                    or not isinstance(entry, dict):
                continue
            clean = {}
            for key in ("runs", "novel", "hard", "diverged"):
                v = entry.get(key)
                clean[key] = int(v) if _is_number(v) else 0
            energy[job_id] = clean
    if len(energy) > _ENERGY_CAP:
        keep = sorted(energy.items(),
                      key=lambda kv: kv[1]["runs"])[-_ENERGY_CAP:]
        energy = dict(keep)
    return energy


def _clean_buckets(raw):
    buckets = {}
    if isinstance(raw, dict):
        for key, entry in raw.items():
            if not isinstance(key, str) \
                    or not isinstance(entry, dict):
                continue
            count = entry.get("count")
            last = entry.get("last")
            examples = entry.get("examples")
            buckets[key] = {
                "count": int(count) if _is_number(count) else 0,
                "last": float(last) if _is_number(last) else 0.0,
                "examples": [e for e in examples
                             if isinstance(e, str)][:3]
                if isinstance(examples, list) else []}
    if len(buckets) > _BUCKET_CAP:
        keep = sorted(buckets.items(),
                      key=lambda kv: kv[1]["last"])[-_BUCKET_CAP:]
        buckets = dict(keep)
    return buckets


def _clean_state(state, corpus_cap, distilled_cap=50):
    if not isinstance(state, dict):
        return _fresh_state()
    corpus = {}
    raw = state.get("corpus")
    if isinstance(raw, dict):
        for job_id, entry in raw.items():
            if not isinstance(job_id, str) \
                    or not isinstance(entry, dict):
                continue
            saved_at = entry.get("saved_at")
            if not _is_number(saved_at):
                continue
            corpus[job_id] = {
                "saved_at": float(saved_at),
                "exit_class": entry.get("exit_class")
                if isinstance(entry.get("exit_class"), str)
                else "",
                "digest": entry.get("digest")
                if isinstance(entry.get("digest"), str) else ""}
    if len(corpus) > corpus_cap:
        keep = sorted(corpus.items(),
                      key=lambda kv: kv[1]["saved_at"])[-corpus_cap:]
        corpus = dict(keep)
    novelty = state.get("novelty")
    if not isinstance(novelty, list):
        novelty = []
    novelty = [k for k in novelty if isinstance(k, str)]
    filed = state.get("filed")
    if not isinstance(filed, dict):
        filed = {}
    filed = {k: float(v) for k, v in filed.items()
             if isinstance(k, str) and _is_number(v)}
    if len(filed) > _FILER_CAP:
        keep = sorted(filed.items(),
                      key=lambda kv: kv[1])[-_FILER_CAP:]
        filed = dict(keep)
    seed = state.get("campaign_seed")
    campaigns = state.get("campaigns")
    dropped = state.get("dropped_total")
    return {"corpus": corpus, "novelty": novelty[-_NOVELTY_CAP:],
            "filed": filed,
            "distilled": _clean_distilled(
                state.get("distilled"), distilled_cap),
            "energy": _clean_energy(state.get("energy")),
            "buckets": _clean_buckets(state.get("buckets")),
            "campaign_seed": int(seed) if _is_number(seed) else 0,
            "campaigns": int(campaigns)
            if _is_number(campaigns) else 0,
            "dropped_total": int(dropped)
            if _is_number(dropped) else 0}


def _normalize_reason(reason, cls):
    """A hard failure's bucket key: the reason with its
    variable parts flattened -- case folded, whitespace
    collapsed, every digit run replaced -- so the same
    hole found through different seeds and numbers lands
    in one bucket. No reason at all buckets by class."""
    if not isinstance(reason, str) or not reason.strip():
        return cls
    out = []
    digit = False
    for ch in reason.lower():
        if ch.isdigit():
            if not digit:
                out.append("#")
            digit = True
        else:
            digit = False
            out.append(ch)
    return " ".join("".join(out).split())[:80] or cls


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is
    readings["now"]. See the module docstring for the
    corpus, idle, and triage rules this implements. The
    corpus folds and evicts on every pass, idle or not;
    findings file only from campaign outcomes, and a pass
    that was not idle carries none.
    """
    tunables = _tunables(manifest)
    corpus_cap = _int_tunable(tunables, "corpus_max_jobs", 200)
    if corpus_cap < 1:
        corpus_cap = 200
    distilled_cap = _int_tunable(
        tunables, "distilled_max_jobs", 50)
    if distilled_cap < 1:
        distilled_cap = 50
    state = _clean_state(state, corpus_cap, distilled_cap)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) \
        else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "job_fuzz"
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    age_cap = _positive_tunable(
        tunables, "corpus_max_age_days", 30.0) * 86400.0
    cooldown = _positive_tunable(
        tunables, "filed_cooldown_sec", 604800.0)
    max_alerts = _int_tunable(tunables, "max_alerts_per_pass", 20)
    if max_alerts < 1:
        max_alerts = 20

    corpus = state["corpus"]
    seeds = readings.get("seeds")
    if isinstance(seeds, list):
        for seed in seeds:
            if not isinstance(seed, dict):
                continue
            job_id = seed.get("job_id")
            saved_at = seed.get("saved_at")
            if not isinstance(job_id, str) or not job_id \
                    or not _is_number(saved_at):
                continue
            corpus[job_id] = {
                "saved_at": float(saved_at),
                "exit_class": _exit_class(
                    "ran", seed.get("exit_code"),
                    seed.get("timed_out")),
                "digest": seed.get("digest")
                if isinstance(seed.get("digest"), str) else ""}
    if age_cap > 0:
        corpus = {k: v for k, v in corpus.items()
                  if now - v["saved_at"] <= age_cap}
    if len(corpus) > corpus_cap:
        keep = sorted(corpus.items(),
                      key=lambda kv: kv[1]["saved_at"])[-corpus_cap:]
        corpus = dict(keep)
    state["corpus"] = corpus
    if age_cap > 0:
        state["distilled"] = {
            k: v for k, v in state["distilled"].items()
            if now - v["saved_at"] <= age_cap}

    outcomes = readings.get("outcomes")
    if not readings.get("idle") or not isinstance(outcomes, list) \
            or not outcomes:
        return [], state
    state["campaigns"] += 1
    seed_now = readings.get("campaign_seed")
    if _is_number(seed_now):
        state["campaign_seed"] = int(seed_now) + 1

    filed = state["filed"]
    novelty = state["novelty"]
    novelty_known = set(novelty)
    distilled = state["distilled"]
    energy = state["energy"]
    buckets = state["buckets"]
    new_keys_seen = set()
    candidates = []  # (priority, alert, file_key, nkey, bucket)
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        job_id = outcome.get("job_id")
        mutator = outcome.get("mutator")
        if not isinstance(job_id, str) or not job_id \
                or not isinstance(mutator, str) or not mutator:
            continue
        stage = outcome.get("stage")
        if stage not in ("ran", "refused", "error"):
            stage = "error"
        cls = _exit_class(stage, outcome.get("exit_code"),
                          outcome.get("timed_out"))
        orig_cls = outcome.get("orig_class")
        if orig_cls not in _CLASSES:
            orig_cls = _exit_class(
                "ran", outcome.get("orig_exit_code"),
                outcome.get("orig_timed_out"))
        detail = {"job_id": job_id, "mutator": mutator,
                  "stage": stage, "variant_class": cls,
                  "original_class": orig_cls}
        if isinstance(outcome.get("variant_file"), str):
            detail["variant_file"] = outcome["variant_file"]
        if _is_number(outcome.get("min_steps")):
            detail["min_steps"] = int(outcome["min_steps"])
        stats = energy.setdefault(
            job_id, {"runs": 0, "novel": 0, "hard": 0,
                     "diverged": 0})
        stats["runs"] += 1
        hard = stage == "error" or cls == "timeout"
        diverged = False
        if hard:
            stats["hard"] += 1
            reason = outcome.get("reason")
            detail["reason"] = reason if isinstance(reason, str) \
                else "variant timed out in the bucket"
            bucket = _normalize_reason(
                outcome.get("reason"), cls)
            detail["bucket"] = bucket
            candidates.append((0, {
                "sensor": sensor,
                "signal": "variant_hard_failure",
                "severity": "high",
                "title": f"variant of job {job_id} hard-failed "
                         f"under {mutator} ({cls})",
                "detail": detail}, None, None, bucket))
        else:
            violation = ""
            if cls != orig_cls:
                diverged = True
                if mutator in RELATION_MUTATORS:
                    violation = "outcome class changed under " \
                        "a semantics-preserving mutation"
            elif mutator in RELATION_MUTATORS \
                    and stage == "ran":
                od = outcome.get("orig_digest")
                vd = outcome.get("digest")
                if isinstance(od, str) and od \
                        and isinstance(vd, str) and vd \
                        and od != vd:
                    diverged = True
                    violation = "output digest changed under " \
                        "a semantics-preserving mutation"
                    detail["original_digest"] = od
                    detail["variant_digest"] = vd
            if diverged:
                stats["diverged"] += 1
                title = f"variant of job {job_id} diverged " \
                        f"under {mutator}: {orig_cls} -> {cls}"
                if violation:
                    detail["relation"] = "identity"
                    detail["relation_violation"] = violation
                    title = f"variant of job {job_id} broke " \
                            f"the identity relation under " \
                            f"{mutator}: {violation}"
                candidates.append((1, {
                    "sensor": sensor,
                    "signal": "variant_divergence",
                    "severity": "medium",
                    "title": title,
                    "detail": detail},
                    f"dv|{job_id}|{mutator}|{cls}", None, None))
        nkey = f"{mutator}|{stage}|{cls}"
        if nkey not in novelty_known:
            if nkey not in new_keys_seen:
                new_keys_seen.add(nkey)
                stats["novel"] += 1
                # Promotion: the variant that first reached
                # this region joins the distilled corpus, so
                # later campaigns start from it.
                vid = outcome.get("variant_id")
                vscript = outcome.get("variant_script")
                if isinstance(vid, str) and vid \
                        and isinstance(vscript, str) and vscript:
                    distilled[vid] = {
                        "script": vscript[:_SEED_SCRIPT_CAP],
                        "exit_code": int(outcome["exit_code"])
                        if _is_number(outcome.get("exit_code"))
                        else None,
                        "timed_out": bool(
                            outcome.get("timed_out")),
                        "exit_class": cls,
                        "digest": outcome.get("digest")
                        if isinstance(outcome.get("digest"),
                                      str) else "",
                        "saved_at": now}
            candidates.append((2, {
                "sensor": sensor,
                "signal": "coverage_novelty",
                "severity": "info",
                "title": f"job fuzz reached new coverage: "
                         f"{mutator} -> {stage}/{cls}",
                "detail": detail}, None, nkey, None))

    candidates.sort(key=lambda c: c[0])
    alerts = []
    for _prio, alert, file_key, nkey, bucket in candidates:
        if bucket is not None:
            entry = buckets.setdefault(
                bucket, {"count": 0, "last": 0.0,
                         "examples": []})
            entry["count"] += 1
            vf = alert["detail"].get("variant_file")
            if isinstance(vf, str) and vf \
                    and vf not in entry["examples"]:
                entry["examples"] = (
                    entry["examples"] + [vf])[-3:]
            if entry["last"] \
                    and now - entry["last"] <= cooldown:
                continue
        if file_key is not None:
            last = filed.get(file_key)
            if last is not None and now - last <= cooldown:
                continue
        if nkey is not None and nkey in novelty_known:
            # A duplicate combination inside this same pass:
            # the first filing already recorded it. (Keys in
            # the state's set never became candidates at all.)
            continue
        if len(alerts) >= max_alerts:
            state["dropped_total"] += 1
            continue
        if bucket is not None:
            entry = buckets[bucket]
            alert["detail"]["bucket_count"] = entry["count"]
            alert["detail"]["bucket_examples"] = list(
                entry["examples"])
            entry["last"] = now
        alerts.append(alert)
        if file_key is not None:
            filed[file_key] = now
        if nkey is not None:
            novelty.append(nkey)
            novelty_known.add(nkey)
    state["novelty"] = novelty[-_NOVELTY_CAP:]
    if len(filed) > _FILER_CAP:
        keep = sorted(filed.items(),
                      key=lambda kv: kv[1])[-_FILER_CAP:]
        state["filed"] = dict(keep)
    if len(distilled) > distilled_cap:
        keep = sorted(distilled.items(),
                      key=lambda kv: kv[1]["saved_at"])[-distilled_cap:]
        state["distilled"] = dict(keep)
    state["energy"] = _clean_energy(energy)
    state["buckets"] = _clean_buckets(buckets)
    return alerts, state


# --- delivery and the main loop, in the Lab Results shape -------------

def _deliver_local(alerts, args):
    """Sign and deliver each alert to a runner on this machine.

    Returns how many alerts were delivered, or None when local
    delivery is not set up (the reason is printed). Uses the
    runner's own producer helpers, so the envelope and signature
    are the contract's, not a re-implementation.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(
        os.path.join(here, "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from runner.ops import extensions as hp_extensions
    except ImportError as e:
        print(f"job-fuzz: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    env = os.environ
    secret = env.get(args.secret_env, "")
    if not secret:
        print(f"job-fuzz: no signing secret in "
              f"${args.secret_env}; set it to this sense's key "
              f"secret", file=sys.stderr)
        return None
    delivered = 0
    for alert in alerts:
        payload = hp_extensions.build_sensor_alert(
            alert["sensor"], alert["severity"], alert["title"],
            key_id=args.key_id, signal=alert.get("signal"),
            detail=alert.get("detail"))
        try:
            if args.local_port:
                hp_extensions.send_local_signal(
                    payload, secret, port=args.local_port)
                where = f"127.0.0.1:{args.local_port}"
            else:
                where = hp_extensions.drop_local_signal(
                    args.local_dir, payload, secret)
        except (OSError, ValueError) as e:
            print(f"job-fuzz: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"job-fuzz: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Job Fuzz extension watcher: on idle "
                    "cycles, mutate retained jobs and run the "
                    "variants through the runner's confined "
                    "execution, filing what the campaign finds "
                    "as sensor alert payloads.")
    ap.add_argument("--manifest", default=os.path.join(
                        here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".job-fuzz-state.json"),
                    help="state file (default: "
                         ".job-fuzz-state.json next to "
                         "this script)")
    ap.add_argument("--samples", default=None,
                    help="read a readings dict from this JSON "
                         "file instead of the machine (trying "
                         "the sense against known campaign "
                         "outcomes, on any box)")
    ap.add_argument("--runner-dir", default=None,
                    help="runner base dir whose retained/ "
                         "records seed the corpus (wins over "
                         "the runner_base_dir tunable)")
    ap.add_argument("--runner-cmd", default=None,
                    help="command that runs one variant file "
                         "through the runner's --run-variant "
                         "door; {variant} is replaced with the "
                         "file path (wins over the runner_cmd "
                         "tunable)")
    ap.add_argument("--local-dir", default=None,
                    help="runner base dir: deliver alerts "
                         "locally (signed, into its local "
                         "inbox) instead of printing payloads")
    ap.add_argument("--local-port", type=int, default=None,
                    help="with --local-dir: push to the "
                         "runner's loopback listener on this "
                         "port instead of dropping files")
    ap.add_argument("--key-id", default="",
                    help="key id this sense signs as (its "
                         "sensors.<name>.key_id in the runner "
                         "config)")
    ap.add_argument("--secret-env",
                    default="HOMING_PIGEON_SENSOR_SECRET",
                    help="environment variable holding the "
                         "signing secret (default: "
                         "HOMING_PIGEON_SENSOR_SECRET)")
    args = ap.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"job-fuzz: cannot read manifest "
              f"{args.manifest}: {e}", file=sys.stderr)
        return 2
    overrides = {}
    if args.runner_dir:
        overrides["runner_base_dir"] = args.runner_dir
    if args.runner_cmd:
        overrides["runner_cmd"] = args.runner_cmd
    if overrides:
        manifest = dict(manifest)
        tunables = dict(_tunables(manifest))
        tunables.update(overrides)
        manifest["tunables"] = tunables
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    if args.samples:
        try:
            with open(args.samples, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"job-fuzz: cannot read samples "
                  f"{args.samples}: {e}", file=sys.stderr)
            return 2
    else:
        # The reader sees the whole state: the campaign
        # seed, the distilled tier, and the energy memory
        # all shape the next campaign.
        readings = read_live(manifest, state)
    alerts, state = decide(readings, manifest, state)
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the next pass reports these conditions again.
            print(f"job-fuzz: {len(alerts) - delivered} of "
                  f"{len(alerts)} alert(s) not delivered; state "
                  f"not saved, will retry next pass",
                  file=sys.stderr)
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"job-fuzz: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
