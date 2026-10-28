# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The change kind: check out, apply a diff, run a recipe (PROTOCOL 3.5).

The loop the README describes is one shape every time: check out a
commit, apply a diff, run the tests, read the exit code, the output
and the diff that resulted. A `change` job is that loop in one
message:

    {"kind": "change", "repo": "app", "commit": "4f2a9c1",
     "diff_b64": "<strict base64 of a unified diff>",
     "recipe": "tests", "args": ["test_app.py"]}

`repo` names an entry of the owner's `change_repos` (name -> a local
git repository on the box); the job never names a path. The runner
clones that repository into the job's workdir (`src/`), checks out
`commit` (the repository's HEAD when absent), applies the diff with
`git apply`, and runs the named recipe (section 3.3) inside `src/`.
The diff of the tree against the commit afterwards, the job's change
and whatever the run changed, comes home as the output file
`change.diff`, shaped by the view like any output (section 6); the
job's own `outputs` name files under `src/` and come home as
`src/<name>`.

A diff that does not apply is a rejection (`exit_code` -2) naming
git's reason; nothing runs. A repository whose tree holds a symlink
is refused by the workspace sweep, as any staged symlink is.
"""
import base64
import binascii
import os
import re
import shutil
import subprocess

COMMIT = re.compile(r"^(?:[0-9a-fA-F]{7,64}|[A-Za-z0-9._][A-Za-z0-9._/-]{0,199})$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
SRC = "src"
RESULT_DIFF = "change.diff"
MAX_DIFF_BYTES = 4 * 1024 * 1024
_REFUSED = ("script", "script_url", "script_sha384", "interpreter", "env",
            "recipe_script")


def validate_repos(cfg):
    """None when change_repos is well formed, else the config error."""
    raw = cfg.get("change_repos") if isinstance(cfg, dict) else None
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return "change_repos must be an object of name -> repository path"
    for name, path in raw.items():
        if not isinstance(name, str) or not REPO_NAME.match(name):
            return (f"change_repos[{name!r}]: a name is 1 to 64 of "
                    "A-Z a-z 0-9 _ . -")
        if not isinstance(path, str) or not os.path.isabs(path) or "\x00" in path:
            return f"change_repos[{name!r}] must be an absolute path"
    return None


def prepare(cfg, job, rejected, expand_recipe):
    """(exec_job, spec) for a change job, or raise rejected(why). The
    exec job is the recipe's; spec says what to clone and apply."""
    for member in _REFUSED:
        if job.get(member) is not None:
            raise rejected(f"a change job may not carry {member!r}")
    name = job.get("repo")
    repos = cfg.get("change_repos") if isinstance(cfg, dict) else None
    path = repos.get(name) if isinstance(repos, dict) and isinstance(name, str) else None
    if not isinstance(path, str):
        raise rejected(f"no change repository named {name!r} on this runner")
    commit = job.get("commit")
    if commit is not None and (not isinstance(commit, str)
                               or not COMMIT.match(commit) or ".." in commit):
        raise rejected("commit must be a hex object name or a plain ref")
    raw = job.get("diff_b64")
    diff = b""
    if raw is not None:
        if not isinstance(raw, str):
            raise rejected("diff_b64 must be strict base64 text")
        try:
            diff = base64.b64decode(raw.encode("ascii"), validate=True)
        except (binascii.Error, ValueError, UnicodeEncodeError):
            raise rejected("diff_b64 is not strict base64")
        if len(diff) > MAX_DIFF_BYTES:
            raise rejected(f"the diff is over {MAX_DIFF_BYTES} bytes")
    outputs = job.get("outputs") or []
    if not isinstance(outputs, list):
        raise rejected("outputs must be a list")
    as_recipe = {k: v for k, v in job.items()
                 if k not in ("repo", "commit", "diff_b64")}
    as_recipe["kind"] = "recipe"
    out = expand_recipe(cfg, as_recipe, rejected)
    # The resulting diff comes home as an output, one name the job
    # cannot also claim.
    if RESULT_DIFF in outputs:
        raise rejected(f"{RESULT_DIFF!r} is the change's own output name")
    # The job's own outputs are files the run leaves under src/.
    names = []
    for n in outputs:
        if not isinstance(n, str):
            raise rejected("each output is a file name")
        names.append(SRC + "/" + n)
    out["outputs"] = names + [RESULT_DIFF]
    return out, {"repo": name, "path": path, "commit": commit, "diff": diff}


def _git(args, cwd, timeout=120):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, timeout=timeout,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0",
                                   GIT_CONFIG_NOSYSTEM="1"))


def stage(work, spec, rejected):
    """Clone, check out and apply into work/src. Returns the resolved
    commit. A missing git, a repository that cannot be cloned, a
    commit that is not there and a diff that does not apply are each
    a rejection naming git's reason."""
    if shutil.which("git") is None:
        raise rejected("git is not on this runner's PATH")
    src = os.path.join(work, SRC)
    try:
        # --no-hardlinks: a clone that shared the owner's object files
        # by hard link would let the run write through to them.
        r = _git(["clone", "--quiet", "--no-checkout", "--no-hardlinks", "--",
                  spec["path"], src], cwd=work)
        if r.returncode != 0:
            raise rejected(f"the change repository did not clone: "
                           f"{r.stderr.strip()[:300]}")
        target = spec["commit"] or "HEAD"
        r = _git(["rev-parse", "--verify", "--quiet", "--end-of-options",
                  target + "^{commit}"], cwd=src)
        if r.returncode != 0:
            raise rejected(f"commit {target!r} is not in the change repository")
        sha = r.stdout.strip()
        r = _git(["checkout", "--quiet", "--detach", sha], cwd=src)
        if r.returncode != 0:
            raise rejected(f"checkout failed: {r.stderr.strip()[:300]}")
        if spec["diff"]:
            patch = os.path.join(work, "change.in.diff")
            with open(patch, "wb") as fh:
                fh.write(spec["diff"])
            r = _git(["apply", "--whitespace=nowarn", "--", patch], cwd=src)
            os.remove(patch)
            if r.returncode != 0:
                raise rejected(f"the diff does not apply: {r.stderr.strip()[:300]}")
    except subprocess.TimeoutExpired:
        raise rejected("git did not finish staging the change in time")
    except OSError as e:
        raise rejected(f"the change could not be staged: {e}")
    return sha


def write_result_diff(work, sha):
    """The tree against the commit, after the run, as work/change.diff
    (untracked files included, through an intent-to-add pass)."""
    src = os.path.join(work, SRC)
    try:
        _git(["add", "--intent-to-add", "--all", "--", "."], cwd=src, timeout=60)
        r = subprocess.run(["git", "diff", "--binary", sha, "--"], cwd=src,
                           capture_output=True, timeout=60)
        data = r.stdout if r.returncode == 0 else b""
    except (OSError, subprocess.TimeoutExpired):
        data = b""
    try:
        with open(os.path.join(work, RESULT_DIFF), "wb") as fh:
            fh.write(data)
    except OSError:
        pass
