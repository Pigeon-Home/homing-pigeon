#!/usr/bin/env python3
"""Version 2 messages. Jobs stay version 1.

Version 2 adds three messages on top of a version 1 job:
a determination (what the runner expects, sent only when that
expectation is not a clean pass), a question (what a Pi Light
runner would have asked a local model), and an answer.

The answerer is any holder of a shared secret this runner
already trusts. It does not have to be the party that
submitted the job. The operator can narrow that set with
``v2_answerers`` (a list of key ids). One answer decides;
a late one is context, not a second vote.

Nothing here runs a job. ``answer_only`` is the laptop's
mode: it may answer a question, and the runner will not
execute. Emitting determinations and questions is the Pi's
mode, and it happens only when ``protocol_v2`` is true.

Context text is data. This module never interprets it.
"""

import json
import os
import re
import time
import uuid

V2 = 2
_ID = re.compile(r"\A[A-Za-z0-9._-]{1,128}\Z")
_KIND = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+"
    r"(determination|question|answer)\s+(\S+)",
    re.I)
_EXPECT = ("proceed", "fail", "unknown")
_DEADLINE_CAP = 30
_TEXT_CAP = 500


def enabled(cfg) -> bool:
    """The Pi emits version 2 messages only when this is on."""
    return isinstance(cfg, dict) and cfg.get("protocol_v2") is True


def answer_only(cfg) -> bool:
    """The laptop answers. It does not execute jobs."""
    return isinstance(cfg, dict) and cfg.get("answer_only") is True


def receiving(cfg) -> bool:
    """True when this process should open a version 2 message."""
    return enabled(cfg) or answer_only(cfg)


def answerer_allowed(cfg, key_id) -> bool:
    """A verified key may answer.

    Absent ``v2_answerers`` means every key this process
    already trusts: the signature check happened before
    this, so holding the secret is the credential. A list
    narrows that to those key ids. Anything else fails
    closed.
    """
    if not isinstance(key_id, str):
        return False
    if not isinstance(cfg, dict) or "v2_answerers" not in cfg:
        return True
    allowed = cfg.get("v2_answerers")
    if not isinstance(allowed, list):
        return False
    return key_id in allowed and all(isinstance(x, str) for x in allowed)


def subject_kind(subject):
    """(kind, msg_id) or None. Never matches a job subject."""
    if not isinstance(subject, str):
        return None
    m = _KIND.search(subject)
    if not m:
        return None
    return m.group(1).lower(), m.group(2)


def _safe_id(value, label):
    if not isinstance(value, str) or not _ID.match(value):
        raise ValueError(f"{label} is missing or not a safe id")
    return value


def _msg_id(prefix, job_id):
    _safe_id(job_id, "job_id")
    ident = prefix + "." + job_id[:120]
    _safe_id(ident, "msg_id")
    return ident


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def segment(by, kind, text):
    """One signed-onto-the-result fragment. Text is data."""
    if not isinstance(text, str):
        text = ""
    return {
        "seg_id": uuid.uuid4().hex,
        "by": str(by)[:64],
        "kind": str(kind)[:64],
        "text": text[:_TEXT_CAP],
    }


def clean_pass(plan) -> bool:
    """True when there is nothing the submitter would act on.

    No plan means the opinion had nothing to say. Findings,
    or a repair the opinion wants applied, are not a clean
    pass.
    """
    if not isinstance(plan, dict):
        return True
    findings = plan.get("findings") or []
    if findings:
        return False
    if plan.get("repair_action"):
        return False
    return True


def determination_for(job, plan):
    """The pre-execution message, or None on a clean pass."""
    if clean_pass(plan):
        return None
    job_id = _safe_id(job.get("job_id"), "job_id")
    findings = plan.get("findings") or []
    parts = []
    for f in findings:
        if isinstance(f, dict) and isinstance(f.get("detail"), str):
            parts.append(f["detail"])
    why = "; ".join(parts)[:_TEXT_CAP] or "expected trouble"
    return {
        "v": V2,
        "type": "determination",
        "job_id": job_id,
        "msg_id": _msg_id("d", job_id),
        "issued_at": _now(),
        "clean_pass": False,
        "expect": "fail" if findings else "unknown",
        "why": why,
    }


def should_ask(cfg, job) -> bool:
    """A deterministic Oracle asks the answerer instead of a model."""
    if not enabled(cfg) or answer_only(cfg):
        return False
    if not isinstance(cfg, dict):
        return False
    if cfg.get("oracle_mode") != "deterministic":
        return False
    return isinstance(job, dict) and job.get("kind") == "exec"


def question_for(cfg, job):
    job_id = _safe_id(job.get("job_id"), "job_id")
    script = job.get("script")
    hint = ""
    if isinstance(script, str) and script.strip():
        hint = " script=" + script.strip().splitlines()[0][:120]
    return {
        "v": V2,
        "type": "question",
        "job_id": job_id,
        "msg_id": _msg_id("q", job_id),
        "issued_at": _now(),
        "deadline_sec": deadline_of(cfg),
        "question": ("Would this job succeed on this host?"
                     + hint)[:_TEXT_CAP],
        "local_default": "proceed",
    }


def answer_for(question, text):
    """The signed reply. ``text`` is the answerer's decision."""
    if not isinstance(question, dict):
        raise ValueError("question must be an object")
    qid = _safe_id(question.get("msg_id"), "question msg_id")
    job_id = _safe_id(question.get("job_id"), "job_id")
    if not isinstance(text, str) or not text.strip():
        text = "proceed"
    return {
        "v": V2,
        "type": "answer",
        "job_id": job_id,
        "msg_id": _msg_id("a", qid[:120]),
        "question_id": qid,
        "issued_at": _now(),
        "answer": text.strip()[:_TEXT_CAP],
    }


def local_answer_text(question) -> str:
    """What the laptop says when it has no model to ask."""
    if isinstance(question, dict):
        default = question.get("local_default")
        if isinstance(default, str) and default.strip():
            return default.strip()[:64]
    return "proceed"


def deadline_of(cfg) -> int:
    raw = cfg.get("v2_answer_deadline_sec", 0) if isinstance(cfg, dict) else 0
    try:
        n = int(raw)
    except (TypeError, ValueError, OverflowError):
        return 0
    if n < 0:
        return 0
    if n > _DEADLINE_CAP:
        return _DEADLINE_CAP
    return n


def validate(obj):
    """Structural checks only. Freshness and the signature are the caller's."""
    if not isinstance(obj, dict):
        raise ValueError("version 2 message must be an object")
    v = obj.get("v")
    if not isinstance(v, int) or isinstance(v, bool) or v != V2:
        raise ValueError("unsupported version")
    kind = obj.get("type")
    if kind not in ("determination", "question", "answer"):
        raise ValueError("unsupported type")
    _safe_id(obj.get("job_id"), "job_id")
    _safe_id(obj.get("msg_id"), "msg_id")
    issued = obj.get("issued_at")
    if not isinstance(issued, str) or not issued.endswith("Z"):
        raise ValueError("issued_at must be UTC and end with Z")
    if kind == "determination":
        if obj.get("clean_pass") is not False:
            raise ValueError("a sent determination is not a clean pass")
        if obj.get("expect") not in _EXPECT:
            raise ValueError("expect is not proceed, fail, or unknown")
        why = obj.get("why")
        if not isinstance(why, str) or not why or len(why) > _TEXT_CAP:
            raise ValueError("why is missing or too long")
    elif kind == "question":
        q = obj.get("question")
        if not isinstance(q, str) or not q.strip() or len(q) > _TEXT_CAP:
            raise ValueError("question is missing or too long")
        d = obj.get("deadline_sec")
        if not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > _DEADLINE_CAP:
            raise ValueError("deadline_sec out of range")
        default = obj.get("local_default")
        if not isinstance(default, str) or not default.strip() or len(default) > 64:
            raise ValueError("local_default is missing or too long")
    else:
        _safe_id(obj.get("question_id"), "question_id")
        ans = obj.get("answer")
        if not isinstance(ans, str) or not ans.strip() or len(ans) > _TEXT_CAP:
            raise ValueError("answer is missing or too long")
    return obj


def outbound_for(cfg, job, plan):
    """Messages to send before execution. No waiting, no I/O."""
    if not enabled(cfg) or answer_only(cfg):
        return []
    if not isinstance(job, dict):
        return []
    out = []
    det = determination_for(job, plan)
    if det is not None:
        out.append((
            "[HOMING-PIGEON] determination " + det["msg_id"], det))
    if should_ask(cfg, job):
        q = question_for(cfg, job)
        out.append((
            "[HOMING-PIGEON] question " + q["msg_id"], q))
    return out


def _answer_path(base_dir, question_id):
    _safe_id(question_id, "question_id")
    folder = os.path.join(base_dir, "v2", "answers")
    return folder, os.path.join(folder, question_id + ".json")


def _read_answer_file(path):
    """(received_at, answer) or None. A half-written file is None."""
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict):
        return None
    ans = rec.get("answer")
    if not isinstance(ans, dict):
        return None
    try:
        got = float(rec.get("received_at"))
    except (TypeError, ValueError):
        return None
    return got, ans


def _publish_answer(path, tmp):
    """Move a finished answer into place. The first valid one stays.

    The bytes are already on disk in ``tmp``. Linking that file
    into ``path`` either wins the slot or loses it. A crash
    before the link leaves no answer, so the next one can try.
    A crash that left a half-written ``path`` is not an answer:
    it is moved aside and the slot is tried again.
    """
    for _ in range(3):
        try:
            os.link(tmp, path)
            return True
        except OSError:
            got = _read_answer_file(path)
            if got is not None:
                return False
            if not os.path.exists(path):
                continue
            aside = path + ".bad-" + uuid.uuid4().hex[:8]
            try:
                os.rename(path, aside)
            except OSError:
                continue
            try:
                os.unlink(aside)
            except OSError:
                pass
    return False


def store_answer(base_dir, obj):
    """File a verified answer where the job can find it.

    Keyed by question id. A second valid answer for the same
    question does not replace the first: one answer decides.
    A file that is not a readable answer does not count, so a
    crash mid-write cannot hold the slot forever.
    """
    validate(obj)
    if obj.get("type") != "answer":
        raise ValueError("not an answer")
    folder, path = _answer_path(base_dir, obj["question_id"])
    os.makedirs(folder, exist_ok=True)
    rec = {"received_at": time.time(), "answer": obj}
    tmp = path + ".tmp-" + uuid.uuid4().hex
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        return _publish_answer(path, tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _load_answer(base_dir, question_id):
    _folder, path = _answer_path(base_dir, question_id)
    return _read_answer_file(path)


def await_answer(base_dir, question, asked_at, pump=None):
    """Segments for the result. Never changes what will run.

    An answer already on disk, or one that arrives before
    the deadline, rides as an answer. A late one rides as
    a late answer beside the local default. No answer rides
    the local default alone.

    ``pump``, when given, is called once per look. The
    runner uses it to file version 2 messages that arrived
    after the question was sent. It must not run a job.
    """
    if not isinstance(question, dict):
        return []
    qid = question.get("msg_id")
    try:
        _safe_id(qid, "question msg_id")
    except ValueError:
        return []
    deadline = question.get("deadline_sec")
    if not isinstance(deadline, int) or isinstance(deadline, bool):
        deadline = 0
    deadline = max(0, min(deadline, _DEADLINE_CAP))
    default = local_answer_text(question)
    end = time.monotonic() + deadline
    while True:
        if pump is not None:
            try:
                pump()
            except Exception:
                pass
        hit = _load_answer(base_dir, qid)
        if hit is not None:
            received, ans = hit
            text = ans.get("answer")
            if not isinstance(text, str):
                text = ""
            if received <= asked_at + deadline + 1.0:
                return [segment("answerer", "answer", text)]
            return [
                segment("runner", "local_default", default),
                segment("answerer", "late_answer", text),
            ]
        if time.monotonic() >= end:
            return [segment("runner", "local_default", default)]
        time.sleep(0.05)
