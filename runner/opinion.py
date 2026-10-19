#!/usr/bin/env python3
"""The Oracle's opinion, carried on the result (PROTOCOL 3.2).

The Oracle reads a job against the box it is about to run on --
the OS, the interpreter, the tools on PATH, the files the job
names -- and forms an opinion: this will probably succeed here,
or this will faceplant, and the reason is obvious. The opinion
rides the result message as the OPTIONAL `oracle_opinion`
member; receivers that do not know the member ignore it.

Latitude is a small lattice, off < diagnose < advise < repair:

- The runner config key `oracle_opinion_mode` is both the
  default latitude for jobs that grant none and the owner's
  ceiling. A job may request a latitude with its own
  `oracle_opinion` member; a request above the ceiling is
  clamped to the ceiling. Default: diagnose.
- diagnose speaks only after a failure, attaching the obvious
  cause. It changes nothing and blocks nothing.
- advise computes a tier-1 prediction before the job runs; the
  job runs exactly as sent and the prediction rides the result.
- repair may additionally fix the one mechanical mismatch --
  a named interpreter that is absent, replaced with the
  platform default when the script's shape fits that default.
  A repair is never silent: the result states what changed
  and carries the digest of the job as received, and the
  repaired job goes back through the judge and the key policy
  before it runs (oracle_opinion_repair: rejudge | refuse).

Two tiers form the opinion, never blended into one
unattributed claim:

1. Deterministic checks (this module): interpreter presence,
   script-shape tells, named tools on PATH, referenced paths.
2. The local model, only when inference is configured AND
   oracle_opinion_model is true. The runner asks for it only
   when tier 1 found nothing, and its text rides in the note
   labeled "Model-formed note:". In deterministic Oracle mode
   (Pi Light) inference_config is None, so tier 2 stays dark
   and tier-1 opinions still file -- they need no model.

The opinion is not a gate: it never blocks, holds, or
approves a job by itself. The one refusal it can produce is
the re-judgment of a repaired job, and then the sender gets
the original job's failure result with the opinion explaining.

This module is free of runner imports: facts about the live
box are gathered by gather_facts with injectable probes, and
tier1_findings is a pure function of (job, facts).
"""
import hashlib
import json
import os
import re
import shutil

LEVELS = {"off": 0, "diagnose": 1, "advise": 2, "repair": 3}
DEFAULT_MODE = "diagnose"
PREDICT_VALUES = ("requested", "always", "never")
DEFAULT_PREDICT = "requested"
REPAIR_VALUES = ("rejudge", "refuse")
DEFAULT_REPAIR = "rejudge"
NOTE_CAP = 500
_MODEL_NOTE_CAP = 240

_CLEAN_NOTE = "tier-1 checks found no environment mismatch on this box"


# ------------------------------------------------------------ settings

def _clean(value, values, default):
    return value if isinstance(value, str) and value in values else default


def ceiling_mode(cfg):
    """The configured latitude: default and ceiling in one key."""
    if not isinstance(cfg, dict):
        return DEFAULT_MODE
    return _clean(cfg.get("oracle_opinion_mode"), LEVELS, DEFAULT_MODE)


def requested_mode(job):
    """The job's requested latitude, or None when it grants none."""
    if not isinstance(job, dict):
        return None
    value = job.get("oracle_opinion")
    return value if isinstance(value, str) and value in LEVELS else None


def effective_mode(cfg, job):
    """min(request, ceiling) when a request exists, else the ceiling."""
    ceiling = ceiling_mode(cfg)
    request = requested_mode(job)
    if request is None:
        return ceiling
    return request if LEVELS[request] <= LEVELS[ceiling] else ceiling


def predict_setting(cfg):
    if not isinstance(cfg, dict):
        return DEFAULT_PREDICT
    return _clean(cfg.get("oracle_opinion_predict"), PREDICT_VALUES,
                  DEFAULT_PREDICT)


def repair_setting(cfg):
    if not isinstance(cfg, dict):
        return DEFAULT_REPAIR
    return _clean(cfg.get("oracle_opinion_repair"), REPAIR_VALUES,
                  DEFAULT_REPAIR)


def model_enabled(cfg):
    """oracle_opinion_model: an opt-in boolean, default off."""
    if not isinstance(cfg, dict):
        return False
    value = cfg.get("oracle_opinion_model")
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "on", "1")
    return False


# ------------------------------------------------------------ job digest

def received_digest(job):
    """SHA-384 of the job as received, sig member excluded.

    The serialization is compact JSON with sorted keys, UTF-8 --
    a sender holding the job it sent can recompute the digest
    and diff the received job against what ran.
    """
    payload = {}
    if isinstance(job, dict):
        payload = {k: v for k, v in job.items() if k != "sig"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False)
    return hashlib.sha384(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------ script hints

_CMDLET_RE = re.compile(
    r"\b(?:Get|Set|New|Remove|Add|Clear|Copy|Move|Test|Write|Read|Out|"
    r"Start|Stop|Restart|Invoke|Import|Export|Select|Where|ForEach)-"
    r"[A-Z][A-Za-z]*\b")
_WIN_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:(?!//)[\\/][^\s'\"<>|]*")
_POSIX_PATH_RE = re.compile(r"(?<![\w:./-])/(?:[\w.\-]+/)*[\w.\-]+")
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\Z")

_POSIX_BUILTINS = frozenset("""
    . : [ alias bg break builtin caller cd command compgen complete
    compopt continue declare dirs disown echo enable eval exec exit
    export false fc fg getopts hash help history jobs kill let local
    logout mapfile popd printf pushd pwd read readarray readonly
    return set shift shopt source suspend test times trap true type
    typeset ulimit umask unalias unset wait
    """.split())
_SH_KEYWORDS = frozenset("""
    if then else elif fi for in while until do done case esac select
    function time coproc { } ! [[ ]]
    """.split())
_PREFIX_WORDS = frozenset(
    ("sudo", "env", "command", "time", "nice", "nohup", "exec"))


def script_shape(script):
    """A strong shape tell: "powershell", "posix", or "neutral".

    Only unmistakable tells count -- a shebang, PowerShell
    cmdlets / $env:, a POSIX export line. Anything weaker is
    neutral, and neutral scripts are never shape findings.
    """
    if not isinstance(script, str) or not script:
        return "neutral"
    first = script.split("\n", 1)[0]
    if first.startswith("#!"):
        low = first.lower()
        if "powershell" in low or "pwsh" in low:
            return "powershell"
        if "sh" in low:
            return "posix"
    if _CMDLET_RE.search(script) or "$env:" in script \
            or "Write-Host" in script:
        return "powershell"
    if re.search(r"(?m)^\s*export\s+[A-Za-z_][A-Za-z0-9_]*=", script):
        return "posix"
    return "neutral"


def _candidate_tools(script):
    """Bare command names in command position, conservatively.

    First token of each line after assignments and common
    prefixes; builtins and keywords are skipped, anything with
    punctuation beyond a name is skipped. At most 8 names --
    this is a tier-1 tell, not a parser.
    """
    names = []
    for line in script.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        tokens = text.split()
        i = 0
        while i < len(tokens) and (_ASSIGN_RE.match(tokens[i])
                                   or tokens[i] in _PREFIX_WORDS):
            i += 1
        if i >= len(tokens):
            continue
        token = tokens[i].strip(";|&")
        if not _TOKEN_RE.match(token):
            continue
        if token in _POSIX_BUILTINS or token in _SH_KEYWORDS:
            continue
        if re.match(r"[A-Z][a-z]+-[A-Z]", token):
            continue  # a PowerShell cmdlet is not a PATH tool
        if token not in names:
            names.append(token)
        if len(names) >= 8:
            break
    return names


def _candidate_paths(script):
    # The shebang line is consumed by the loader, not referenced at
    # runtime; its path is the shape logic's business, not this scan's.
    if script.startswith("#!"):
        script = script.split("\n", 1)[-1] if "\n" in script else ""
    paths = []
    for regex in (_WIN_PATH_RE, _POSIX_PATH_RE):
        for match in regex.finditer(script):
            path = match.group(0).rstrip(".,;:)")
            if path and path not in paths:
                paths.append(path)
        if len(paths) >= 8:
            break
    return paths[:8]


def script_hints(script):
    """What tier 1 can see in a script without running anything."""
    if not isinstance(script, str) or not script:
        return {"tools": [], "paths": [], "shape": "neutral"}
    return {
        "tools": _candidate_tools(script),
        "paths": _candidate_paths(script),
        "shape": script_shape(script),
    }


def interpreter_family(interpreter):
    """powershell | posix-shell | python | other, from argv."""
    if not isinstance(interpreter, (list, tuple)) or not interpreter:
        return "other"
    joined = " ".join(x for x in interpreter if isinstance(x, str)).lower()
    if "powershell" in joined or "pwsh" in joined:
        return "powershell"
    exe = interpreter[0] if isinstance(interpreter[0], str) else ""
    base = exe.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if base in ("sh", "bash", "zsh", "dash", "ash", "ksh", "sh.exe",
                "bash.exe"):
        return "posix-shell"
    if "python" in base:
        return "python"
    return "other"


# ------------------------------------------------------------ facts

def gather_facts(job, interpreter, platform_default, which=None,
                 exists=None, os_name=None):
    """Resolve a job's environment facts with live probes.

    which / exists / os_name are injectable so tests can stage
    any box. Existence of foreign-shaped paths is recorded as
    None: on the wrong platform the shape is the finding, not
    the existence.
    """
    if which is None:
        which = shutil.which
    if exists is None:
        exists = os.path.exists
    if os_name is None:
        os_name = "nt" if os.name == "nt" else "posix"
    job = job if isinstance(job, dict) else {}
    hints = script_hints(job.get("script"))
    interp = [x for x in interpreter if isinstance(x, str)] \
        if isinstance(interpreter, (list, tuple)) else []
    present = True
    if interp:
        exe = interp[0]
        try:
            if os.path.isabs(exe) or "/" in exe or "\\" in exe:
                present = bool(exists(exe))
            else:
                present = which(exe) is not None
        except Exception:
            present = False
    tools = {}
    if interpreter_family(interp) != "powershell":
        for name in hints["tools"]:
            if interp and name == interp[0]:
                continue
            try:
                tools[name] = which(name) is not None
            except Exception:
                tools[name] = False
    paths = {}
    for path in hints["paths"]:
        foreign = bool(re.match(r"^[A-Za-z]:[\\/]", path)) != (os_name == "nt")
        if foreign:
            paths[path] = None
        else:
            try:
                paths[path] = bool(exists(path))
            except Exception:
                paths[path] = False
    return {
        "os_name": os_name,
        "interpreter": interp,
        "interpreter_present": present,
        "platform_interpreter": [x for x in platform_default
                                 if isinstance(x, str)]
        if isinstance(platform_default, (list, tuple)) else [],
        "shape": hints["shape"],
        "tools": tools,
        "paths": paths,
    }


# ------------------------------------------------------------ tier 1

def _shape_fits(shape, platform_family):
    if shape == "neutral":
        return True
    if shape == "powershell":
        return platform_family == "powershell"
    if shape == "posix":
        return platform_family == "posix-shell"
    return True


def tier1_findings(job, facts):
    """Pure: (job, environment facts) -> ordered findings.

    Each finding is {"kind", "detail", "repair"}; repair is a
    descriptor for the one mechanical fix, or None. The job
    argument is accepted for symmetry with the caller and for
    future checks; today's checks read only the facts, which
    were gathered from the job.
    """
    out = []
    if not isinstance(facts, dict):
        return out
    os_name = facts.get("os_name")
    host = "Windows" if os_name == "nt" else "POSIX"
    interp = facts.get("interpreter") or []
    shape = facts.get("shape") or "neutral"
    family = interpreter_family(interp)
    platform_family = "powershell" if os_name == "nt" else "posix-shell"

    if interp and not facts.get("interpreter_present", True):
        detail = (f"interpreter {interp!r} is not present on this "
                  f"{host} host")
        repair = None
        if _shape_fits(shape, platform_family):
            repair = {
                "action": "platform_default_interpreter",
                "description": (
                    f"interpreter {interp!r} replaced with the "
                    f"platform default "
                    f"{facts.get('platform_interpreter')!r}"),
            }
            detail += "; the platform default would do"
        out.append({"kind": "interpreter_absent", "detail": detail,
                    "repair": repair})

    if shape == "powershell" and family == "posix-shell":
        out.append({
            "kind": "script_shape_mismatch",
            "detail": "the script is PowerShell-shaped (cmdlets, "
                      "$env:) but the interpreter is a POSIX shell",
            "repair": None})
    elif shape == "posix" and family == "powershell":
        out.append({
            "kind": "script_shape_mismatch",
            "detail": "the script is POSIX-shell-shaped (sh "
                      "shebang, export) but the interpreter is "
                      "PowerShell",
            "repair": None})

    tools = facts.get("tools") or {}
    missing = [name for name, ok in tools.items() if not ok]
    for name in missing[:3]:
        out.append({
            "kind": "tool_missing",
            "detail": f"the script invokes {name!r}, which is not "
                      f"on PATH on this box",
            "repair": None})
    if len(missing) > 3:
        out.append({
            "kind": "tool_missing",
            "detail": f"and {len(missing) - 3} more invoked tools "
                      f"are not on PATH",
            "repair": None})

    paths = facts.get("paths") or {}
    shape_noted = False
    missing_noted = 0
    for path, exists in paths.items():
        if exists is None:
            if not shape_noted:
                out.append({
                    "kind": "path_shape",
                    "detail": f"the script references {path!r}, a "
                              f"path shaped for a different platform "
                              f"than this {host} host",
                    "repair": None})
                shape_noted = True
        elif not exists and missing_noted < 3:
            out.append({
                "kind": "path_missing",
                "detail": f"the script references {path!r}, which "
                          f"does not exist on this box",
                "repair": None})
            missing_noted += 1
    return out


# ------------------------------------------------------------ members

def _note_text(findings):
    return "; ".join(f.get("detail", "") for f in findings
                     if isinstance(f, dict) and f.get("detail"))


def verdict_of(findings):
    return "likely_failure" if findings else "likely_success"


def form_member(mode, verdict, note, repaired=None, digest=None,
                model_note=None):
    """Assemble the oracle_opinion member. Note is bounded."""
    text = note or ""
    if model_note:
        label = "Model-formed note: " + str(model_note)
        text = (text + " " + label) if text else label
    member = {"mode": mode, "verdict": verdict,
              "note": text[:NOTE_CAP]}
    if repaired is not None:
        member["repaired"] = bool(repaired)
        if digest:
            member["received_digest"] = digest
    return member


def with_model_note(member, model_note):
    """Return the member with a labeled tier-2 note appended."""
    if not isinstance(member, dict) or not model_note:
        return member
    out = dict(member)
    text = out.get("note") or ""
    label = "Model-formed note: " + str(model_note)
    out["note"] = ((text + " " + label) if text else label)[:NOTE_CAP]
    return out


def diagnosis_member(mode, findings, model_note=None):
    """The diagnose member: a cause when tier 1 finds one, an
    honest no_opinion when it does not."""
    if findings:
        return form_member(mode, "likely_failure", _note_text(findings),
                           model_note=model_note)
    return form_member(
        mode, "no_opinion",
        "the job failed and tier-1 checks find no obvious "
        "environmental cause on this box",
        model_note=model_note)


def repair_member(plan, job, applied, refusal=None):
    """The member for a repair that ran, or one refusal stopped."""
    findings = (plan or {}).get("findings") or []
    action = (plan or {}).get("repair_action") or {}
    desc = action.get("description") or "the environment fix"
    note = _note_text(findings)
    if applied:
        note += (f" Repair applied: {desc}. The result below is "
                 f"from the repaired job.")
    else:
        note += (f" Repair attempted ({desc}) but the repaired "
                 f"job was refused on re-judgment: {refusal}. The "
                 f"job as received was not run.")
    return form_member("repair", "likely_failure", note,
                       repaired=applied, digest=received_digest(job))


def extend_member_outcome(member, findings):
    """Append the post-run sentence to a wrong likely_success call.

    The prediction stands -- it was the call -- but when the job
    failed anyway, the member says what a post-run tier-1 check
    finds. A likely_failure member already names its cause and
    is returned unchanged.
    """
    if not isinstance(member, dict) \
            or member.get("verdict") != "likely_success":
        return member
    out = dict(member)
    cause = _note_text(findings) if findings \
        else "no obvious environmental cause found"
    text = (out.get("note") or "") \
        + f" The job failed anyway; post-run tier-1 check: {cause}."
    out["note"] = text[:NOTE_CAP]
    return out


# ------------------------------------------------------------ planning

def plan_before(cfg, job, facts):
    """Pure pre-execution plan for one job.

    Returns the effective mode, whether tier-1 checks ran, their
    findings, a member to attach (prediction, or the advise
    degradation of a refused repair), and the repair action the
    runner may apply. Side effects (applying the repair,
    re-judging, asking the model) are the runner's.
    """
    mode = effective_mode(cfg, job)
    plan = {
        "mode": mode,
        "active": mode != "off",
        "requested": requested_mode(job),
        "checks_run": False,
        "findings": [],
        "attach": None,
        "repair_action": None,
        "repair_proposal": None,
    }
    if not plan["active"]:
        return plan
    setting = predict_setting(cfg)
    if setting == "always":
        want_attach = True
    elif setting == "requested":
        want_attach = plan["requested"] in ("advise", "repair")
    else:  # never
        want_attach = False
    if mode != "repair" and not want_attach:
        return plan
    findings = tier1_findings(job, facts)
    plan["checks_run"] = True
    plan["findings"] = findings
    repairable = next((f for f in findings if f.get("repair")), None)
    if mode == "repair" and repairable is not None:
        if repair_setting(cfg) == "refuse":
            desc = repairable["repair"]["description"]
            plan["repair_proposal"] = desc
            note = _note_text(findings) + (
                f" Proposed fix (not applied; oracle_opinion_repair "
                f"is refuse): {desc}.")
            plan["attach"] = form_member("advise", "likely_failure",
                                         note)
            return plan
        plan["repair_action"] = repairable["repair"]
        return plan
    if want_attach:
        note = _note_text(findings) or _CLEAN_NOTE
        plan["attach"] = form_member(mode, verdict_of(findings), note)
    return plan
