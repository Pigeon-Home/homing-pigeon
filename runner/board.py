"""The task board (PROTOCOL.md section 13): open -> claimed -> done,
plus pending_review.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

The Oracle is the sole arbiter of the board, so there is no
distributed consensus here: one writer, many readers, one lock.
Claims are exclusive and lease-bound (task_timeout); results are
idempotent (the first wins, a late duplicate is told so); a task
submitted twice keeps its first submission. The rules are 13.6.

This module is the first piece carved out of runner/runner.py.
It keeps runner's conventions: stdlib only, and no runner imports
(the lock, the text helpers, and the logger it needs are its own or
handed in), so it loads on its own and under the frozen binaries.
runner.py binds `Board` and `BOARD_LOCK` on itself and calls
set_logger() at startup, so every name callers and tests used
before (`runner.runner.Board`, `_BOARD_LOCK`) still resolves there.
"""
import copy
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone

try:
    from runner import confval as _confval
except ImportError:
    import confval as _confval  # type: ignore

try:
    from runner.textutil import _as_str, _json_safe
except ImportError:  # run as a script from the runner/ directory
    from textutil import _as_str, _json_safe  # type: ignore


def _noop(*_a, **_k):
    return None


_LOGGER = None  # (log, vlog) when a host set them explicitly


def set_logger(log_fn, vlog_fn=None):
    """A host other than runner.py hands in its own log and vlog.
    runner.py does not need to: its functions are found live."""
    global _LOGGER
    _LOGGER = (log_fn or _noop, vlog_fn or _noop) if log_fn else None


def _runner_logger():
    """The runner's live log and vlog, looked up at call time.

    Looked up, not bound: the suite loads runner.py a second time
    under another name in places, and a function bound at import
    would read that copy's verbosity instead of the real module's.
    The real module is `runner.runner`, or `__main__` when the
    runner was started as a script.
    """
    if _LOGGER is not None:
        return _LOGGER
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "log", None)) \
                and callable(getattr(m, "vlog", None)):
            return m.log, m.vlog
    return _noop, _noop


def log(msg, level="INFO"):
    _runner_logger()[0](msg, level)


def vlog(msg, level=2):
    _runner_logger()[1](msg, level)


BOARD_LOCK = threading.RLock()

class Board:
    """Task board: open -> claimed -> done (plus pending_review)."""

    def __init__(self, path):
        if not isinstance(path, str) or not path:
            raise ValueError("board path must be a non-empty string")
        self.path = path
        self.tasks = {}
        self.load()

    def load(self):
        self.tasks = {}
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        # A list, a string, or a task that is not an object used to
        # crash the next poll (tasks.values() / task.get).
        if not isinstance(data, dict):
            return
        self.tasks = {
            key: task for key, task in data.items()
            if isinstance(key, str) and isinstance(task, dict)
        }

    def save(self):
        # Unique tmp so concurrent saves cannot race on one .tmp name.
        # O_EXCL | O_NOFOLLOW: a symlink planted on that name is not
        # written through. The board file itself is mode 0600.
        tmp = self.path + f".tmp.{os.getpid()}.{threading.get_ident()}"
        fd = None
        try:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(tmp, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fd = None
                json.dump(_json_safe(self.tasks), f, indent=2, allow_nan=False)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except Exception as e:
            log(f"board save failed: {e}", "WARN")
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def submit(self, task):
        if not isinstance(task, dict):
            return False, "invalid task"
        tid = task.get("task_id")
        if not isinstance(tid, str) or not re.fullmatch(
                r"[A-Za-z0-9._-]{1,128}", tid):
            return False, "invalid task_id"
        for field in ("requires", "capabilities", "compartments"):
            v = task.get(field)
            if v is not None and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                return False, f"{field} must be a list of strings"
        if "priority" in task and not isinstance(task["priority"], (int, float)):
            return False, "priority must be numeric"
        if isinstance(task.get("priority"), float) and task["priority"] != task["priority"]:
            return False, "priority must be a finite number"
        if isinstance(task.get("priority"), float) and task["priority"] in (float("inf"), float("-inf")):
            return False, "priority must be a finite number"
        with BOARD_LOCK:
            if tid in self.tasks:
                return False, "duplicate task_id"
            self.tasks[tid] = {
                "task_id": tid,
                "state": "open",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "priority": task.get("priority", 0),
                "requires": task.get("requires") or [],
                "capabilities": task.get("capabilities") or [],
                "compartments": task.get("compartments") or [],
                "payload": task.get("payload"),
            }
            self.save()
        return True, "ok"

    def _dag_incomplete(self, t):
        """(blocked, names) for a task's requires (PROTOCOL 13.1).

        Blocked when any requirement is not a done task on this
        board. names lists the incomplete requirement ids, in
        requires order; a corrupt non-string entry blocks without
        contributing a name, exactly as enforce has always treated
        it. Shared by the enforce and advisory modes so the two
        can never disagree about what "incomplete" means.
        """
        reqs = t.get("requires") or []
        if not isinstance(reqs, list):
            reqs = []
        blocked = False
        names = []
        for req in reqs:
            # A dict in requires raises TypeError on get.
            # A corrupt board file must not stop the offer.
            if not isinstance(req, str):
                blocked = True
                continue
            dep = self.tasks.get(req)
            if not isinstance(dep, dict) or dep.get("state") != "done":
                blocked = True
                if req not in names:
                    names.append(req)
        return blocked, names

    def offer(self, worker_id, capabilities, key_id="", cfg=None):
        with BOARD_LOCK:
            return self._offer_unlocked(worker_id, capabilities, key_id, cfg)

    def _offer_unlocked(self, worker_id, capabilities, key_id="", cfg=None):
        if not isinstance(cfg, dict):
            cfg = {}
        allow = cfg.get("worker_allowlist") or []
        if not isinstance(allow, list):
            allow = []
        if allow:
            try:
                allowed = worker_id in allow
            except Exception:
                allowed = False
            if not allowed:
                return None
        raw_caps = capabilities if isinstance(capabilities, list) else []
        capabilities = [c for c in raw_caps if isinstance(c, str)]
        raw_comp = cfg.get("worker_compartments") or {}
        if not isinstance(raw_comp, dict):
            raw_comp = {}
        # A dict worker id raises TypeError on get. No compartments
        # for it. The offer itself still runs.
        if isinstance(worker_id, str):
            compartments = raw_comp.get(worker_id)
        else:
            compartments = None
        if not isinstance(compartments, list) or not all(
                isinstance(x, str) for x in compartments):
            compartments = None
        # re-offer outstanding claim
        for t in list(self.tasks.values()):
            if not isinstance(t, dict):
                continue
            if t.get("state") == "claimed":
                try:
                    same = t.get("claimed_by") == worker_id
                except Exception:
                    same = False
                if same:
                    return t
        dag_mode = cfg.get("dag_mode") or "off"
        incomplete_by_id = {}
        candidates = []
        for t in list(self.tasks.values()):
            if not isinstance(t, dict) or t.get("state") != "open":
                continue
            if not t.get("task_id"):
                continue
            # compartment visibility
            tcomps = t.get("compartments") or []
            if not isinstance(tcomps, list):
                tcomps = []
            if tcomps:
                if compartments is None:
                    pass  # no config = visible
                else:
                    # A dict in the list is bad data, not a crash.
                    left = {x for x in tcomps if isinstance(x, str)}
                    right = {x for x in compartments if isinstance(x, str)}
                    if not left & right:
                        continue
            # capability filter
            need = t.get("capabilities") or []
            if not isinstance(need, list):
                need = []
            need = {x for x in need if isinstance(x, str)}
            if need and not need <= set(capabilities or []):
                continue
            # DAG (PROTOCOL 13.1): enforce withholds a task whose
            # dependencies are incomplete; advisory hands it out
            # anyway, with the warning on the offer. Any other
            # dag_mode value is off, like an unknown judge value.
            if dag_mode in ("advisory", "enforce"):
                blocked, incomplete = self._dag_incomplete(t)
                if blocked:
                    if dag_mode == "enforce":
                        vlog(f"board: task "
                             f"{_as_str(t.get('task_id'))} "
                             f"withheld (dag_mode=enforce): "
                             f"incomplete requires: "
                             f"{', '.join(incomplete) or 'unreadable requirement'}")
                        continue
                    incomplete_by_id[id(t)] = incomplete
            candidates.append(t)
        if not candidates:
            vlog(f"board: nothing to offer "
                 f"{_as_str(worker_id)} (dag_mode={dag_mode})")
            return None
        def _rank(task):
            priority = task.get("priority", 0)
            if not isinstance(priority, (int, float)) or isinstance(priority, bool):
                priority = 0
            # NaN sorts anywhere. Treat it as zero so the order is stable.
            if priority != priority:
                priority = 0
            return (-priority, _as_str(task.get("submitted_at")))
        candidates.sort(key=_rank)
        chosen = candidates[0]
        incomplete = incomplete_by_id.get(id(chosen))
        if incomplete is not None:
            # Advisory hand-out (PROTOCOL 13.1): the task goes out
            # with its warning on the offer itself, and the warning
            # stays on the board record of the hand-out.
            chosen["dag_warning"] = {"incomplete_requires": incomplete}
            log(f"board: advisory: {_as_str(chosen.get('task_id'))} handed "
                f"out with incomplete dependencies: "
                f"{', '.join(incomplete) or 'unreadable requirement'}",
                "WARN")
        elif "dag_warning" in chosen:
            # A warning from an earlier hand-out must not outlive
            # the dependencies it named.
            del chosen["dag_warning"]
        chosen["state"] = "claimed"
        chosen["claimed_by"] = worker_id
        log(f"board: {_as_str(worker_id)} claimed {_as_str(chosen.get('task_id'))}")
        vlog(f"board: offered {_as_str(chosen.get('task_id'))} "
             f"to {_as_str(worker_id)} (dag_mode={dag_mode}, "
             f"{len(candidates)} candidate(s))")
        chosen["claimed_at"] = datetime.now(timezone.utc).isoformat()
        chosen["claimed_key_id"] = key_id
        self.save()
        return copy.deepcopy(chosen)

    def complete(self, task_id, result, require_review=False):
        with BOARD_LOCK:
            return self._complete_unlocked(task_id, result, require_review)

    def _complete_unlocked(self, task_id, result, require_review=False):
        # A dict id raises TypeError on get. That rejected the message.
        if not isinstance(task_id, str):
            return "not_found", "not found"
        t = self.tasks.get(task_id)
        if not isinstance(t, dict):
            return "not_found", "not found"
        if t.get("state") == "done":
            return "duplicate", "already done"
        if t.get("state") != "claimed":
            return "not_claimed", "not claimed"
        if require_review:
            t["state"] = "pending_review"
            t["result"] = _json_safe(result)
            self.save()
            return "pending_review", "awaiting review"
        t["state"] = "done"
        # A set in the result made json.dump raise and rejected the
        # message. Store a JSON-safe copy.
        t["result"] = _json_safe(result)
        t["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return "done", "ok"

    def approve(self, task_id):
        with BOARD_LOCK:
            return self._approve_unlocked(task_id)

    def _approve_unlocked(self, task_id):
        if not isinstance(task_id, str):
            return "not_found", "not found"
        t = self.tasks.get(task_id)
        if not isinstance(t, dict):
            return False, "not found"
        if t.get("state") != "pending_review":
            return False, "not pending_review"
        t["state"] = "done"
        t["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return True, "ok"

    def reoffer_expired(self, task_timeout=86400):
        with BOARD_LOCK:
            return self._reoffer_expired_unlocked(task_timeout)

    def _reoffer_expired_unlocked(self, task_timeout=86400):
        # docs/configuring-oracle.md: task_timeout default 86400. A
        # value present as null, a non-number, a boolean, or a
        # negative number is not a lease length; null once wedged
        # every claimed task forever (the comparison raised, and the
        # except swallowed it), and true stripped claims in a second.
        # Zero is a number: it reoffers at once, as documented.
        task_timeout = _confval.number(task_timeout, 86400, lo=0)
        now = datetime.now(timezone.utc)
        count = 0
        tasks = list(self.tasks.values())
        for t in tasks:
            if not isinstance(t, dict):
                continue
            if t.get("state") == "claimed" and t.get("claimed_at"):
                try:
                    claimed = datetime.fromisoformat(t["claimed_at"])
                    if (now - claimed).total_seconds() > task_timeout:
                        t["state"] = "open"
                        t.pop("claimed_by", None)
                        t.pop("claimed_at", None)
                        t.pop("claimed_key_id", None)
                        count += 1
                except Exception:
                    pass
        if count:
            self.save()
        return count

    def counts(self):
        c = {"open": 0, "claimed": 0, "done": 0, "pending_review": 0}
        with BOARD_LOCK:
            tasks = list(self.tasks.values())
        for t in tasks:
            if not isinstance(t, dict):
                continue
            s = t.get("state")
            if s in c:
                c[s] += 1
        return c
