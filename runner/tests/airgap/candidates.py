"""39 long strings from the flag321 files, to the local model.
The string is not printed. The reply is not printed.

    python candidates.py
    python candidates.py 90
    python candidates.py slow
"""

import ast
import glob
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SLOW = os.path.join(HERE, "candidates-slow.txt")
ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"
MODEL = "qwen2.5:3b"


def _say(line):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + line, flush=True)


def _slow():
    want = {}
    with open(SLOW, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, index = line.split("#")
            want.setdefault(name, set()).add(int(index))
    return want


def collect(only):
    items = []
    for path in sorted(glob.glob(os.path.join(ROOT, "runner", "tests", "test_flag321*.py"))):
        name = os.path.basename(path)
        tree = ast.parse(open(path, encoding="utf-8").read())
        i = 0
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 40):
                continue
            i += 1
            if only is not None and i not in only.get(name, ()):
                continue
            items.append((name, i, node.value))
    return items


def main(argv):
    cutoff = 30
    only = None
    if len(argv) == 2 and argv[1] == "slow":
        cutoff = 90
        only = _slow()
    elif len(argv) == 2:
        cutoff = int(argv[1])
    elif len(argv) != 1:
        _say("use: python candidates.py")
        _say("     python candidates.py 90")
        _say("     python candidates.py slow")
        return 2
    items = collect(only)
    _say("found %s  model %s  limit off  cutoff %ss" % (len(items), MODEL, cutoff))
    for n, (name, i, text) in enumerate(items, 1):
        _say("start %s/%s %s#%s %s" % (n, len(items), name, i, len(text)))
        body = json.dumps({
            "model": MODEL,
            "messages": [{"role": "user", "content": text}],
            "temperature": 0,
            "keep_alive": "30m",
        }).encode()
        t = time.perf_counter()
        try:
            req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cutoff) as resp:
                resp.read()
            _say("ok %s/%s %.1fs" % (n, len(items), time.perf_counter() - t))
        except Exception as e:
            _say("problem %s %s/%s %.1fs" % (type(e).__name__, n, len(items), time.perf_counter() - t))
    _say("done")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
