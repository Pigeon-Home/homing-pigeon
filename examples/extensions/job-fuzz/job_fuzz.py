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
Hard failures and divergences file once per (seed,
mutator, class) and may file again after
filed_cooldown_sec (default a week); a novelty files once
per combination, ever. Alerts per pass are capped
(max_alerts_per_pass, default 20), hard failures first,
then divergences, then novelties, so a rich pass cannot
flood the ingest caps; what the cap drops is counted in
the pass's state, not lost silently. Every variant the
campaign runs is archived under the work dir (default:
.job-fuzz-variants next to this script; pruned to
max_archived_variants, default 200, oldest first) so any
finding reproduces by handing the same file to
--run-variant again.

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
(docs/extensions.md, "Local delivery"). Without
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


# --- small tolerant helpers (the sibling shape) --------------------

def _is_number(value):
    return isinstance(value, (int, float)) \
        and not isinstance(value, bool) and value == value \
        and value not in (float("inf"), float("-inf"))


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


def _mut_truncate(job, rng):
    lines = _script_lines(job.get("script") or "")
    if len(lines) < 2:
        return None
    cut = rng.randrange(1, len(lines))
    return {"script": "\n".join(lines[:cut])}


def _mut_duplicate_line(job, rng):
    lines = _script_lines(job.get("script") or "")
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    if not nonempty:
        return None
    i = rng.choice(nonempty)
    lines.insert(i, lines[i])
    return {"script": "\n".join(lines)}


def _mut_drop_line(job, rng):
    lines = _script_lines(job.get("script") or "")
    if len(lines) < 2:
        return None
    i = rng.randrange(len(lines))
    del lines[i]
    return {"script": "\n".join(lines)}


_BOUNDARY_NUMBERS = ("0", "-1", "2147483647",
                     "9223372036854775807",
                     "99999999999999999999999999")


def _mut_boundary_number(job, rng):
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


def _mut_quote_break(job, rng):
    script = job.get("script") or ""
    quotes = [i for i, ch in enumerate(script) if ch in "\"'"]
    if quotes:
        i = rng.choice(quotes)
        flip = "'" if script[i] == '"' else '"'
        return {"script": script[:i] + flip + script[i + 1:]}
    lines = _script_lines(script)
    lines.append('echo "unterminated')
    return {"script": "\n".join(lines)}


def _mut_unicode_edge(job, rng):
    script = job.get("script") or ""
    lines = _script_lines(script)
    lines.append("# edge: é​\U0001F600")
    return {"script": "\n".join(lines)}


def _mut_empty_script(job, rng):
    if not (job.get("script") or ""):
        return None
    return {"script": ""}


def _mut_oversized_line(job, rng):
    lines = _script_lines(job.get("script") or "")
    lines.append("echo " + "a" * 65536)
    return {"script": "\n".join(lines)}


def _mut_null_byte(job, rng):
    script = job.get("script") or ""
    if len(script) < 2:
        return None
    i = rng.randrange(1, len(script))
    return {"script": script[:i] + "\x00" + script[i:]}


def _mut_interpreter_string(job, rng):
    """The classic malformed shape: interpreter as a bare
    string. Validation must refuse it; if it ever runs, the
    refusal path has a hole and the divergence is the news."""
    return {"interpreter": "sh"}


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
}


def build_variant(seed_job, mutator, campaign_seed):
    """One variant job dict, or None when the mutator cannot
    bite. Deterministic in (seed job, mutator, campaign_seed).
    """
    fn = MUTATORS.get(mutator)
    if fn is None:
        return None
    material = (str(campaign_seed) + "|" + mutator + "|"
                + (seed_job.get("job_id") or "") + "|"
                + (seed_job.get("script") or "")).encode(
                    "utf-8", "surrogateescape")
    rng = random.Random(
        int.from_bytes(hashlib.sha384(material).digest()[:8],
                       "big"))
    fields = fn(seed_job, rng)
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
        for part in shlex.split(runner_cmd):
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
    if not idle or not runner_cmd or not seeds:
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
    mutator_names = sorted(MUTATORS)
    chosen = seeds[-max_seeds:] if max_seeds > 0 else []
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
            variant = build_variant(seed_job, mutator,
                                    campaign_seed)
            if variant is None:
                continue
            outcome = _run_one_variant(
                runner_cmd, variant, work_dir, timeout_sec)
            outcome["job_id"] = seed["job_id"]
            outcome["mutator"] = mutator
            outcome["orig_stage"] = "ran"
            outcome["orig_exit_code"] = seed["exit_code"]
            outcome["orig_timed_out"] = seed["timed_out"]
            readings["outcomes"].append(outcome)
            ran += 1
    _prune_archive(work_dir, _int_tunable(
        tunables, "max_archived_variants", 200))
    return readings


# --- the decision: readings in, signals out (pure) -------------------

def _fresh_state():
    return {"corpus": {}, "novelty": [], "filed": {},
            "campaign_seed": 0, "campaigns": 0, "dropped_total": 0}


def _clean_state(state, corpus_cap):
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
            "campaign_seed": int(seed) if _is_number(seed) else 0,
            "campaigns": int(campaigns)
            if _is_number(campaigns) else 0,
            "dropped_total": int(dropped)
            if _is_number(dropped) else 0}


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
    state = _clean_state(state, corpus_cap)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) \
        else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "job_fuzz"
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    age_cap = _tunable(tunables, "corpus_max_age_days", 30.0) \
        * 86400.0
    cooldown = _tunable(tunables, "filed_cooldown_sec", 604800.0)
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
    candidates = []  # (priority, alert, file_key, novelty_key)
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
        orig_cls = _exit_class(
            "ran", outcome.get("orig_exit_code"),
            outcome.get("orig_timed_out"))
        detail = {"job_id": job_id, "mutator": mutator,
                  "stage": stage, "variant_class": cls,
                  "original_class": orig_cls}
        if isinstance(outcome.get("variant_file"), str):
            detail["variant_file"] = outcome["variant_file"]
        hard = stage == "error" or cls == "timeout"
        if hard:
            reason = outcome.get("reason")
            detail["reason"] = reason if isinstance(reason, str) \
                else "variant timed out in the bucket"
            candidates.append((0, {
                "sensor": sensor,
                "signal": "variant_hard_failure",
                "severity": "high",
                "title": f"variant of job {job_id} hard-failed "
                         f"under {mutator} ({cls})",
                "detail": detail},
                f"hf|{job_id}|{mutator}", None))
        elif cls != orig_cls:
            candidates.append((1, {
                "sensor": sensor,
                "signal": "variant_divergence",
                "severity": "medium",
                "title": f"variant of job {job_id} diverged "
                         f"under {mutator}: {orig_cls} -> {cls}",
                "detail": detail},
                f"dv|{job_id}|{mutator}|{cls}", None))
        nkey = f"{mutator}|{stage}|{cls}"
        if nkey not in novelty_known:
            candidates.append((2, {
                "sensor": sensor,
                "signal": "coverage_novelty",
                "severity": "info",
                "title": f"job fuzz reached new coverage: "
                         f"{mutator} -> {stage}/{cls}",
                "detail": detail}, None, nkey))

    candidates.sort(key=lambda c: c[0])
    alerts = []
    for _prio, alert, file_key, nkey in candidates:
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
        from runner import extensions as hp_extensions
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
        reader = {"campaign_seed": state.get("campaign_seed")
                  if isinstance(state, dict) else None}
        readings = read_live(manifest, reader)
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
