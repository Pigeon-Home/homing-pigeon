"""Walk a case list. Restart the same command if this process dies.

A case leaves the list only after it exits clean. Anything else is
recorded as suspicious and is not retried. The question text is never
printed. The echo cases ask the named model one short question with
no project context.

    python sweep.py slow
    python sweep.py default
"""

import ast
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "cases")
STATE = os.path.join(HERE, "state")

# slow: qwen2.5:3b. default: qwen3:1.7b.
MODES = {
    "slow": {"model": "qwen2.5:3b", "timeout": 120},
    "default": {"model": "qwen3:1.7b", "timeout": 180},
}
ENDPOINT = "http://127.0.0.1:11434/v1"


def _say(line):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + line, flush=True)


def _read_ids(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def _write_ids(path, ids):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for case_id in ids:
            fh.write(case_id + "\n")
    os.replace(tmp, path)


def discover(cases_dir):
    """Test ids from source shape only. The files are not imported."""
    found = []
    if not os.path.isdir(cases_dir):
        return found
    for name in sorted(os.listdir(cases_dir)):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        path = os.path.join(cases_dir, name)
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=name)
        stem = name[:-3]
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    found.append(stem + "." + node.name + "." + item.name)
    return found


def ensure_pending(cases_dir, state_dir):
    """Create the list once. A later run keeps the list that remains."""
    pending_path = os.path.join(state_dir, "pending.txt")
    if os.path.exists(pending_path):
        return _read_ids(pending_path)
    done = set(_read_ids(os.path.join(state_dir, "done.txt")))
    suspicious = set(_read_ids(os.path.join(state_dir, "suspicious.txt")))
    fresh = [c for c in discover(cases_dir) if c not in done and c not in suspicious]
    _write_ids(pending_path, fresh)
    return fresh


def run_case(case_id, timeout, model, cases_dir=CASES):
    """Run one test in a child. Return (verdict, seconds).

    stdout is discarded. The child is told which model to ask.
    """
    target = "cases." + case_id
    env = os.environ.copy()
    env["TOPAZ_MODEL"] = model
    env["TOPAZ_ENDPOINT"] = os.environ.get("TOPAZ_ENDPOINT", ENDPOINT)
    env["TOPAZ_TIMEOUT"] = str(timeout)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", target],
            cwd=os.path.dirname(cases_dir),
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "timeout", time.monotonic() - started
    except OSError:
        return "no-return", time.monotonic() - started
    elapsed = time.monotonic() - started
    if proc.returncode == 0:
        return "ok", elapsed
    return "crash", elapsed


def _drop(ids, case_id):
    return [c for c in ids if c != case_id]


def sweep(mode, cases_dir=CASES, state_dir=STATE):
    if mode not in MODES:
        _say("use: python sweep.py slow")
        _say("     python sweep.py default")
        return 2
    choice = MODES[mode]
    _say("mode " + mode + " model " + choice["model"])
    pending = ensure_pending(cases_dir, state_dir)
    done_path = os.path.join(state_dir, "done.txt")
    suspicious_path = os.path.join(state_dir, "suspicious.txt")
    pending_path = os.path.join(state_dir, "pending.txt")
    _say("pending " + str(len(pending)))
    for case_id in list(pending):
        _say("start " + case_id)
        verdict, elapsed = run_case(
            case_id, choice["timeout"], choice["model"], cases_dir)
        seconds = f"{elapsed:.1f}s"
        if verdict == "ok":
            done = _read_ids(done_path)
            if case_id not in done:
                done.append(case_id)
            _write_ids(done_path, done)
            pending = _drop(pending, case_id)
            _write_ids(pending_path, pending)
            _say("ok " + case_id + " " + seconds)
        else:
            bad = _read_ids(suspicious_path)
            if case_id not in bad:
                bad.append(case_id)
            _write_ids(suspicious_path, bad)
            pending = _drop(pending, case_id)
            _write_ids(pending_path, pending)
            _say("problem " + verdict + " " + case_id + " " + seconds)
        _say("pending " + str(len(pending)))
    bad = _read_ids(suspicious_path)
    if bad:
        _say("suspicious " + str(len(bad)))
        for case_id in bad:
            _say(case_id)
    return 0


def main(argv):
    if len(argv) != 2 or argv[1] not in MODES:
        _say("use: python sweep.py slow")
        _say("     python sweep.py default")
        return 2
    return sweep(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
