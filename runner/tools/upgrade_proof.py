#!/usr/bin/env python3
# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Install one source tree, upgrade it with another, prove nothing was lost.

    python3 runner/tools/upgrade_proof.py OLD_TREE NEW_TREE

OLD_TREE and NEW_TREE are repository checkouts (the folder holding
runner/). The proof runs in a throwaway HOME with a stand-in
systemctl on PATH, so it needs no root, no systemd and no mailbox:

1. OLD_TREE's installer installs into HOME/.homing-pigeon with a
   fresh shared secret, as a first install does.
2. The owner's hand edits and the runner's state are seeded: keys
   the owner set in config.json, and files in the state folder.
3. NEW_TREE's installer runs over it with no secret, as an upgrade
   does.
4. Every key the owner had keeps its value, every state file keeps
   its bytes, the installed runner reports NEW_TREE's version, its
   posture report loads the upgraded config to the end, and the
   service unit starts the installed runner with that config.

Exit 0 when every check holds; 1 with each failed check named.

    git ls-remote --tags --refs origin 'v*' | sed 's#.*refs/tags/##' \
      | python3 runner/tools/upgrade_proof.py --previous-of runner/_version.py

prints the last release before this tree's version.
The suite runs it tree-to-itself (runner/tests/test_upgrade_proof.py);
.github/workflows/upgrade-proof.yml runs it from the last release.
"""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

_FAKE_SYSTEMCTL = """#!/bin/sh
echo "systemctl $*" >> "$HP_SYSTEMCTL_LOG"
exit 0
"""

# What an owner sets by hand after the first install, and must
# still find after an upgrade.
OWNER_EDITS = {
    "mailbox_user": "pigeon-upgrade@example.com",
    "owner_instructions": "upgrade proof: keep this sentence",
    "poll_interval_sec": 47,
}
STATE_FILES = {
    "seen.json": '{"upgrade-proof-job": 1}',
    "audit.log": "upgrade proof audit line\n",
    os.path.join("results", "upgrade-proof.json"): '{"exit_code": 0}',
}


def _version(tree):
    with open(os.path.join(tree, "runner", "_version.py"),
              encoding="utf-8") as fh:
        m = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read())
    return m.group(1) if m else None


def _install(tree, home, env, extra):
    cmd = [sys.executable, os.path.join(tree, "runner", "ops", "install.py"),
           "--dir", os.path.join(home, ".homing-pigeon"),
           "--no-inference", "--no-profile"] + extra
    return subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=600)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def prove(old_tree, new_tree, keep=None):
    """Run the proof; return a list of failed checks (empty: proven)."""
    failures = []
    work = keep or tempfile.mkdtemp(prefix="hp-upgrade-proof-")
    home = os.path.join(work, "home")
    shims = os.path.join(work, "bin")
    os.makedirs(home)
    os.makedirs(shims)
    systemctl = os.path.join(shims, "systemctl")
    with open(systemctl, "w", encoding="utf-8") as fh:
        fh.write(_FAKE_SYSTEMCTL)
    os.chmod(systemctl, 0o755)
    log = os.path.join(work, "systemctl.log")
    env = dict(os.environ, HOME=home, HP_SYSTEMCTL_LOG=log,
               PATH=shims + os.pathsep + os.environ.get("PATH", ""))
    env.pop("PYTHONPATH", None)
    dst = os.path.join(home, ".homing-pigeon")
    cfg_path = os.path.join(dst, "config.json")
    try:
        first = _install(old_tree, home, env,
                         ["--shared-secret", secrets.token_hex(32),
                          "--no-collector"])
        if first.returncode != 0 or not os.path.isfile(cfg_path):
            return ["old install failed (exit %d):\n%s"
                    % (first.returncode, first.stdout[-2000:])]
        cfg = _load(cfg_path)
        cfg.update(OWNER_EDITS)
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        before = _load(cfg_path)
        state = cfg.get("base_dir") or dst
        if not os.path.isabs(state):
            state = os.path.join(dst, state)
        for rel, text in STATE_FILES.items():
            path = os.path.join(state, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

        # No --no-collector here: on an existing install that flag
        # means "set up the collectors and stop", not an upgrade.
        second = _install(new_tree, home, env, [])
        if second.returncode != 0:
            failures.append("upgrade install failed (exit %d):\n%s"
                            % (second.returncode, second.stdout[-2000:]))
        after = _load(cfg_path)
        for key, value in before.items():
            if after.get(key) != value:
                failures.append("config key %r changed: %r -> %r"
                                % (key, value, after.get(key)))
        for rel, text in STATE_FILES.items():
            path = os.path.join(state, rel)
            try:
                with open(path, encoding="utf-8") as fh:
                    got = fh.read()
            except OSError as e:
                failures.append("state file %s lost: %s" % (rel, e))
                continue
            if got != text:
                failures.append("state file %s rewritten" % rel)

        runner = os.path.join(dst, "runner.py")
        want = _version(new_tree)
        ver = subprocess.run([sys.executable, runner, "--version"], env=env,
                             cwd=work, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True, timeout=120)
        if ver.returncode != 0 or want not in ver.stdout:
            failures.append("installed runner does not report %s:\n%s"
                            % (want, ver.stdout[-2000:]))
        posture = subprocess.run(
            [sys.executable, runner, "--config", cfg_path, "--posture"],
            env=env, cwd=work, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True, timeout=300)
        # --posture exits 1 on any warning; the proof is that it loaded
        # the upgraded config and every module and reached its end.
        if "Traceback" in posture.stdout \
                or "config file readable" not in posture.stdout:
            failures.append("posture on the upgraded install broke:\n%s"
                            % posture.stdout[-2000:])

        unit = os.path.join(home, ".config", "systemd", "user",
                            "homing-pigeon.service")
        try:
            with open(unit, encoding="utf-8") as fh:
                exec_start = [ln for ln in fh.read().splitlines()
                              if ln.startswith("ExecStart=")]
        except OSError as e:
            exec_start = []
            failures.append("service unit missing: %s" % e)
        if exec_start and (runner not in exec_start[0]
                           or cfg_path not in exec_start[0]):
            failures.append("service unit does not start the installed "
                            "runner with its config: %s" % exec_start[0])
        return failures
    finally:
        if keep is None:
            shutil.rmtree(work, ignore_errors=True)


def _key(tag):
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def previous_release(tags, current):
    """The highest vX.Y.Z tag below `current` (X.Y.Z), or None."""
    tags = [t.strip() for t in tags
            if re.match(r"^v\d+\.\d+\.\d+$", t.strip())]
    below = [t for t in tags if _key(t) < _key(current)]
    return max(below, key=_key) if below else None


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--previous-of"]:
        # tags on stdin, one per line; prints the release before the
        # version in the named _version.py (upgrade-proof.yml).
        with open(argv[1], encoding="utf-8") as fh:
            current = re.search(r'__version__\s*=\s*"([^"]+)"',
                                fh.read()).group(1)
        prev = previous_release(sys.stdin.read().split(), current)
        if prev is None:
            print("no release before %s" % current, file=sys.stderr)
            return 1
        print(prev)
        return 0
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old_tree")
    ap.add_argument("new_tree")
    ap.add_argument("--keep", metavar="DIR",
                    help="work in DIR and leave it for inspection")
    a = ap.parse_args(argv)
    print("upgrade proof: %s (%s) -> %s (%s)"
          % (a.old_tree, _version(a.old_tree), a.new_tree,
             _version(a.new_tree)))
    failures = prove(os.path.abspath(a.old_tree),
                     os.path.abspath(a.new_tree), a.keep)
    for f in failures:
        print("FAIL: " + f)
    print("upgrade proof: %s" % ("FAILED" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
