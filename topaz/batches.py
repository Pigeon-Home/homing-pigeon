"""Three sittings.

    python batches.py fast
    python batches.py each
    python batches.py rest

fast stops at 60 minutes. A file still going at 2 minutes is recorded and skipped.
each uses a 60 minute cutoff per file. The campaign file skips where sh is absent.
rest is the gated files and the flag321 files.
A passed file is not run again.
"""

import ast
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LISTS = os.path.join(HERE, "batches")
STATE = os.path.join(HERE, "batch-state")

SITTING = {
    "fast": {"budget": 60 * 60, "file_cutoff": 120},
    "each": {"budget": None, "file_cutoff": 60 * 60},
    "rest": {"budget": None, "file_cutoff": 120},
}


def _say(line):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + line, flush=True)


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row + "\n")
    os.replace(tmp, path)


def _pending(name):
    path = os.path.join(STATE, name + ".txt")
    if os.path.exists(path):
        return _read(path), path
    done = set(_read(os.path.join(STATE, name + "-done.txt")))
    fresh = [row for row in _read(os.path.join(LISTS, name + ".txt")) if row not in done]
    _write(path, fresh)
    return fresh, path


def _tests(path):
    if not os.path.exists(path):
        return 0
    tree = ast.parse(open(path, encoding="utf-8").read())
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))


def run_file(rel, cutoff):
    if not os.path.exists(os.path.join(ROOT, rel.replace("/", os.sep))):
        return "missing", 0.0
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    module = rel.replace("\\", ".").replace("/", ".")[:-3]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", module],
            cwd=ROOT,
            timeout=cutoff,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "timeout", time.monotonic() - started
    elapsed = time.monotonic() - started
    if proc.returncode == 0:
        return "ok", elapsed
    return "fail", elapsed


def sit(name):
    if name not in SITTING:
        _say("use: python batches.py fast")
        _say("     python batches.py each")
        _say("     python batches.py rest")
        return 2
    plan = SITTING[name]
    pending, path = _pending(name)
    done_path = os.path.join(STATE, name + "-done.txt")
    _say("batch " + name + "  files " + str(len(pending)))
    if plan["budget"]:
        _say("budget " + str(plan["budget"] // 60) + "m")
    _say("file cutoff " + str(plan["file_cutoff"]) + "s")
    start = time.monotonic()
    for rel in list(pending):
        used = time.monotonic() - start
        if plan["budget"] and used >= plan["budget"]:
            _say("budget reached  files left " + str(len(pending)))
            break
        n = _tests(os.path.join(ROOT, rel.replace("/", os.sep)))
        _say("start " + rel + "  tests " + str(n))
        verdict, elapsed = run_file(rel, plan["file_cutoff"])
        if verdict == "ok":
            done = _read(done_path)
            if rel not in done:
                done.append(rel)
            _write(done_path, done)
            pending = [row for row in pending if row != rel]
            _write(path, pending)
            _say("ok " + rel + "  %.0fs" % elapsed)
        else:
            pending = [row for row in pending if row != rel]
            held = _read(os.path.join(STATE, name + "-held.txt"))
            if rel not in held:
                held.append(rel)
            _write(os.path.join(STATE, name + "-held.txt"), held)
            _write(path, pending)
            _say("problem " + verdict + " " + rel + "  %.0fs" % elapsed)
        _say("left " + str(len(pending)))
    held = _read(os.path.join(STATE, name + "-held.txt"))
    if held:
        _say("held " + str(len(held)))
        for rel in held:
            _say(rel)
    elif not pending:
        _say("left 0")
    return 0


def main(argv):
    if len(argv) != 2 or argv[1] not in SITTING:
        _say("use: python batches.py fast")
        _say("     python batches.py each")
        _say("     python batches.py rest")
        return 2
    return sit(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
