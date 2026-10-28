# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Named recipes: what an owner lets a key run, by name (PROTOCOL 3.3).

`allowed_script_sha384` pins exact scripts, and a pin breaks the
moment an argument changes. A recipe is a script the owner writes in
the runner's own config, with the arguments a job may pass held to a
pattern:

    "recipes": {
      "tests": {"script": "python3 -m pytest -q \"$@\"",
                "interpreter": ["sh"],
                "args_pattern": "[A-Za-z0-9_./:-]{1,200}",
                "max_args": 8, "max_timeout_sec": 900}
    }

A job names one, `{"kind": "recipe", "recipe": "tests", "args":
["test_app.py"]}`, and the runner runs the owner's script
with those arguments exactly as it would run an exec job carrying it,
confinement, timeout and the result's view included. A job can add
`files` (inline or fetched) and `outputs`; it cannot bring a script,
a script_url, an interpreter or an environment, since each of those
would be code the owner did not write. A key policy with
`allowed_kinds: ["recipe"]` and `allowed_recipes: ["tests"]` means
"this key may run the tests and nothing else", and holds.

The runner hands in its own JobRejected.
"""
import re

try:
    from runner.guard import security as _security
except ImportError:  # running from inside runner/ as __main__
    from guard import security as _security  # type: ignore

RECIPE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
DEFAULT_MAX_ARGS = 16
MAX_ARG_CHARS = 1024      # as a key policy's args_pattern holds them
HARD_MAX_ARGS = 256
# The members a recipe job may carry beside the envelope's own; the
# rest are what the recipe stands in for and are refused by name.
_REFUSED = ("script", "script_url", "script_sha384", "interpreter", "env")


def validate_recipes(cfg):
    """None when cfg's recipes are well formed, else the config error.
    Read at startup, so a recipe the runner could not run is refused
    before any job names it."""
    raw = cfg.get("recipes") if isinstance(cfg, dict) else None
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return "recipes must be an object of name -> recipe"
    for name, rec in raw.items():
        where = f"recipes[{name!r}]"
        if not isinstance(name, str) or not RECIPE_NAME.match(name):
            return f"{where}: a recipe name is 1 to 64 of A-Z a-z 0-9 _ . -"
        if not isinstance(rec, dict):
            return f"{where} must be an object"
        script = rec.get("script")
        if not isinstance(script, str) or not script.strip() or "\x00" in script:
            return f"{where}.script must be non-empty text"
        interp = rec.get("interpreter")
        if interp is not None and not (
                isinstance(interp, list) and interp
                and all(isinstance(x, str) and x and "\x00" not in x for x in interp)):
            return f"{where}.interpreter must be a non-empty list of strings"
        pat = rec.get("args_pattern")
        if pat is not None:
            if not isinstance(pat, str):
                return f"{where}.args_pattern must be a regular expression"
            try:
                re.compile(pat)
            except re.error as e:
                return f"{where}.args_pattern does not compile: {e}"
            shape = _security.regex_backtracks(pat)
            if shape:
                # The arguments are the sender's text: a pattern that
                # can take exponential time on them is refused here.
                return f"{where}.args_pattern may backtrack: {shape}"
        for key, lo, hi in (("max_args", 0, HARD_MAX_ARGS),
                            ("max_timeout_sec", 1, 3600)):
            v = rec.get(key)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int)
                                  or not lo <= v <= hi):
                return f"{where}.{key} must be a whole number from {lo} to {hi}"
    return None


def expand(cfg, job, rejected):
    """The exec job a recipe job stands for, or raise rejected(why).
    The recipe's script, interpreter and caps are the owner's; the
    job's args are held to the recipe's pattern (with no pattern, a
    recipe takes no arguments)."""
    name = job.get("recipe")
    if not isinstance(name, str) or not RECIPE_NAME.match(name):
        raise rejected("a recipe job names its recipe in 'recipe'")
    recipes = cfg.get("recipes") if isinstance(cfg, dict) else None
    rec = recipes.get(name) if isinstance(recipes, dict) else None
    if not isinstance(rec, dict):
        raise rejected(f"no recipe named {name!r} on this runner")
    for member in _REFUSED:
        if job.get(member) is not None:
            raise rejected(f"a recipe job may not carry {member!r}: "
                           "the recipe is the owner's")
    args = job.get("args") or []
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise rejected("recipe args must be a list of strings")
    pat = rec.get("args_pattern")
    limit = rec.get("max_args")
    if limit is None:
        limit = DEFAULT_MAX_ARGS if pat is not None else 0
    if len(args) > limit:
        raise rejected(f"recipe {name!r} takes at most {limit} argument(s)")
    if args:
        cre = re.compile(pat)
        for a in args:
            if len(a) > MAX_ARG_CHARS or "\x00" in a or not cre.fullmatch(a):
                raise rejected(f"argument {a[:80]!r} does not match recipe "
                               f"{name!r}'s args_pattern")
    out = dict(job)
    out.pop("recipe", None)
    out["kind"] = "exec"
    out["script"] = rec["script"]
    out["args"] = list(args)
    if rec.get("interpreter") is not None:
        out["interpreter"] = list(rec["interpreter"])
    cap = rec.get("max_timeout_sec")
    if cap is not None:
        try:
            asked = int(job.get("timeout_sec") or cap)
        except (TypeError, ValueError, OverflowError):
            raise rejected("timeout_sec must be a number")
        out["timeout_sec"] = min(asked, cap)
    return out
