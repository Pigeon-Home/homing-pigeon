# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The 4-component release version: MAJOR.MINOR.TOKENS.COUNTER.

The scheme (owner's words, 3-Nov-2026):

- MAJOR stays 3. It never moves; it is exempt from the odometer rule.
- MINOR is the line as before (the 15 in 3.15.x). It moves only when
  a release is deliberately cut on a new minor line.
- TOKENS is the size of this repository in tokens, in whole
  millions: the measured token count of the tracked tree, divided
  by 1,000,000 and rounded down. It can only move when the tree is
  measured, and measuring happens at most once every 24 hours — a
  release inside that window reuses the figure the last release
  used (see next_version and the measure cache below).
- COUNTER is the release counter (the 148 position in the old
  3-component shape).

Odometer rule: when a number increases, the numbers to its right
restart, so any reader can order 2 versions at a glance. Here the
restart lands on the counter: when the minor increases, or when the
token figure increases, the counter restarts at 1; otherwise it
increments by 1. MAJOR is exempt and is carried through unchanged.
The token figure never decreases inside a minor line: a fresh
measurement lower than the current figure is held (the current
figure stays, the counter increments), so the ordering a reader
sees never runs backwards.

Token counting is an ESTIMATOR, not a BPE tokenizer. tiktoken is
not a dependency of this project, so count_text_tokens applies a
fixed, documented rule: each maximal run of ASCII letters is 1
token, each maximal run of digits is 1 token, and each other
non-whitespace character is 1 token. The count is deterministic
and grows monotonically with the tree, which is all the scheme
needs; it is not cl100k_base and must not be quoted as one.

Only git-tracked files are counted (git ls-files). A file is
skipped as binary when its extension is a known binary extension
or its first bytes contain a NUL.

The release machinery's single entry point is the CLI:

    python3 runner/ops/version4.py measure [--root .]
        Print "<tokens> <millions>" for the tree at --root.

    python3 runner/ops/version4.py next CURRENT [--root .]
            [--cache PATH] [--minor N] [--now EPOCH]
        Print the next version after CURRENT, measuring the tree
        at --root only when the measure cache at --cache is
        missing or older than 24 hours (and rewriting the cache
        when it measures). The cache file is 2 lines: the epoch
        seconds of the measurement, then the millions figure.

Everything except measure_repo_tokens and the cache file helpers
is a pure function.
"""

import os
import re
import subprocess
import sys
import time
from typing import List, Optional, Tuple

Version = Tuple[int, int, int, int]

MEASURE_WINDOW_SEC = 24 * 60 * 60

_TOKEN_RE = re.compile(r"[A-Za-z]+|[0-9]+|[^\sA-Za-z0-9]")

_BINARY_EXTENSIONS = frozenset([
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".whl",
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".dat",
    ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".mov",
    ".sqlite", ".db",
])

_SNIFF_BYTES = 8192


def parse(version: str) -> Version:
    """Parse "MAJOR.MINOR.TOKENS.COUNTER" into a 4-tuple of ints.

    Strict on purpose: exactly 4 dot-separated components, each a
    run of decimal digits with no sign, no whitespace and no
    leading zero (a bare "0" is fine), so each version has exactly
    1 spelling. Raises ValueError on anything else.
    """
    if not isinstance(version, str):
        raise ValueError("version must be a string, got %r" % (version,))
    parts = version.split(".")
    if len(parts) != 4:
        raise ValueError(
            "version %r does not have exactly 4 components" % (version,))
    numbers = []
    for part in parts:
        if not part or not part.isascii() or not part.isdigit():
            raise ValueError(
                "version %r has a non-numeric component %r"
                % (version, part))
        if len(part) > 1 and part.startswith("0"):
            raise ValueError(
                "version %r component %r has a leading zero"
                % (version, part))
        numbers.append(int(part))
    return (numbers[0], numbers[1], numbers[2], numbers[3])


def format_version(parts: Version) -> str:
    """The canonical string for a parsed 4-tuple; parse's inverse."""
    major, minor, tokens, counter = parts
    for component in parts:
        if not isinstance(component, int) or component < 0:
            raise ValueError(
                "version components must be non-negative ints, got %r"
                % (parts,))
    return "%d.%d.%d.%d" % (major, minor, tokens, counter)


def convert_legacy(version: str, measured_millions: int) -> str:
    """Convert a 3-component version to the 4-component shape.

    The legacy patch number becomes the counter, carried over
    unchanged, and the measured token figure takes the third
    position: convert_legacy("3.15.148", 6) == "3.15.6.148". This
    is a one-time conversion; future releases go through
    next_version, where the restart rule applies.
    """
    if not isinstance(version, str):
        raise ValueError("version must be a string, got %r" % (version,))
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(
            "legacy version %r does not have exactly 3 components"
            % (version,))
    numbers = []
    for part in parts:
        if not part or not part.isascii() or not part.isdigit():
            raise ValueError(
                "legacy version %r has a non-numeric component %r"
                % (version, part))
        if len(part) > 1 and part.startswith("0"):
            raise ValueError(
                "legacy version %r component %r has a leading zero"
                % (version, part))
        numbers.append(int(part))
    if not isinstance(measured_millions, int) or measured_millions < 0:
        raise ValueError(
            "measured millions must be a non-negative int, got %r"
            % (measured_millions,))
    return format_version(
        (numbers[0], numbers[1], measured_millions, numbers[2]))


def count_text_tokens(text: str) -> int:
    """Estimate the token count of one text file's content.

    The estimator rule, in full: each maximal run of ASCII letters
    is 1 token, each maximal run of digits is 1 token, and each
    other non-whitespace character is 1 token. See the module
    docstring — this is not a BPE tokenizer.
    """
    return len(_TOKEN_RE.findall(text))


def _tracked_files(root: str) -> List[str]:
    """git ls-files under root; RuntimeError when git cannot read it."""
    proc = subprocess.run(
        ["git", "-C", root, "ls-files", "-z"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(
            "git ls-files failed in %r: %s"
            % (root, proc.stderr.decode("utf-8", "replace").strip()))
    names = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [name for name in names if name]


def measure_repo_tokens(root: str) -> int:
    """Total estimated tokens over the tracked text files of root.

    Binary files (known binary extension, or a NUL in the first
    bytes) and entries that are not plain files (submodule
    gitlinks, files deleted from the worktree) are skipped.
    """
    total = 0
    for name in _tracked_files(root):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() in _BINARY_EXTENSIONS:
            continue
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\0" in data[:_SNIFF_BYTES]:
            continue
        total += count_text_tokens(data.decode("utf-8", "replace"))
    return total


def tokens_millions(tokens: int) -> int:
    """Whole millions in a token count: 6,412,908 tokens -> 6."""
    if not isinstance(tokens, int) or tokens < 0:
        raise ValueError(
            "token count must be a non-negative int, got %r" % (tokens,))
    return tokens // 1000000


def next_version(current: str,
                 now: float,
                 last_measured_at: Optional[float],
                 last_tokens_millions: Optional[int],
                 fresh_tokens_millions: Optional[int] = None,
                 new_minor: Optional[int] = None) -> str:
    """The version after `current`, under the scheme's rules.

    now and last_measured_at are epoch seconds. The 24-hour rule:
    when last_measured_at is set and now is less than
    MEASURE_WINDOW_SEC past it (a clock reading before
    last_measured_at counts as inside the window), the token
    figure is last_tokens_millions, reused — fresh_tokens_millions
    is ignored. Outside the window (or when nothing was ever
    measured), fresh_tokens_millions is required and becomes the
    figure; passing none raises ValueError.

    The odometer rule: new_minor above the current minor restarts
    the counter at 1 on the new line; a token figure above the
    current one restarts the counter at 1; anything else
    increments the counter, and a lower fresh figure is held (the
    current figure stays). MAJOR is carried through, never moved.
    """
    major, minor, cur_tokens, counter = parse(current)
    if last_tokens_millions is not None:
        if not isinstance(last_tokens_millions, int) \
                or last_tokens_millions < 0:
            raise ValueError(
                "last tokens millions must be a non-negative int, got %r"
                % (last_tokens_millions,))
    if fresh_tokens_millions is not None:
        if not isinstance(fresh_tokens_millions, int) \
                or fresh_tokens_millions < 0:
            raise ValueError(
                "fresh tokens millions must be a non-negative int, got %r"
                % (fresh_tokens_millions,))
    if last_measured_at is not None \
            and now - last_measured_at < MEASURE_WINDOW_SEC:
        if last_tokens_millions is None:
            raise ValueError(
                "inside the 24-hour window but no last figure to reuse")
        figure = last_tokens_millions
    else:
        if fresh_tokens_millions is None:
            raise ValueError(
                "outside the 24-hour window: a fresh measurement is "
                "required (fresh_tokens_millions is None)")
        figure = fresh_tokens_millions
    if new_minor is not None:
        if not isinstance(new_minor, int) or new_minor < 0:
            raise ValueError(
                "new minor must be a non-negative int, got %r"
                % (new_minor,))
        if new_minor < minor:
            raise ValueError(
                "new minor %d is below the current minor %d"
                % (new_minor, minor))
        if new_minor > minor:
            return format_version((major, new_minor, figure, 1))
    if figure > cur_tokens:
        return format_version((major, minor, figure, 1))
    return format_version((major, minor, cur_tokens, counter + 1))


def read_measure_cache(path: str) -> Optional[Tuple[float, int]]:
    """(epoch seconds, millions) from a measure cache file, or None.

    The file is 2 lines: the epoch seconds of the measurement and
    the millions figure it produced. A missing or malformed file
    reads as None — no usable measurement — never as an error.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        return (float(lines[0].strip()), int(lines[1].strip()))
    except (OSError, ValueError, IndexError):
        return None


def write_measure_cache(path: str, measured_at: float,
                        millions: int) -> None:
    """Write the measure cache file read_measure_cache reads."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("%s\n%d\n" % (measured_at, millions))


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: `measure` prints a tree's count; `next` prints a version."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: version4.py measure [--root .] | "
              "next CURRENT [--root .] [--cache PATH] [--minor N] "
              "[--now EPOCH]", file=sys.stderr)
        return 2
    command, rest = args[0], args[1:]
    root = "."
    cache = None
    minor = None
    now = None
    positional = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--root" and i + 1 < len(rest):
            root = rest[i + 1]
            i += 2
        elif arg == "--cache" and i + 1 < len(rest):
            cache = rest[i + 1]
            i += 2
        elif arg == "--minor" and i + 1 < len(rest):
            minor = int(rest[i + 1])
            i += 2
        elif arg == "--now" and i + 1 < len(rest):
            now = float(rest[i + 1])
            i += 2
        else:
            positional.append(arg)
            i += 1
    if command == "measure":
        tokens = measure_repo_tokens(root)
        print("%d %d" % (tokens, tokens_millions(tokens)))
        return 0
    if command == "next":
        if len(positional) != 1:
            print("version4.py next: exactly 1 CURRENT version is "
                  "required", file=sys.stderr)
            return 2
        if now is None:
            now = time.time()
        cached = read_measure_cache(cache) if cache else None
        last_at, last_millions = cached if cached else (None, None)
        fresh = None
        measured = last_at is None \
            or now - last_at >= MEASURE_WINDOW_SEC
        if measured:
            fresh = tokens_millions(measure_repo_tokens(root))
        result = next_version(positional[0], now, last_at, last_millions,
                              fresh_tokens_millions=fresh, new_minor=minor)
        if measured and cache:
            write_measure_cache(cache, now, parse(result)[2])
        print(result)
        return 0
    print("version4.py: unknown command %r" % (command,), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
