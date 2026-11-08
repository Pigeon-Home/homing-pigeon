"""Gather personal documents into one sheltered folder, on request.

The design, and why, are in docs/steady/security/
personal-documents-shelter.md. The companion check
(runner/oracle/personal_docs.py) only warns: it never opens a
document, never keeps a name, never moves anything. This module is
the operator's answer to that warning. Run by hand, it gathers the
files and folders the check would trip on -- the same name scan,
the same watched folders -- into a single folder on the Desktop,
out of the scattered places a job or a visitor might meet them.

The discipline, stated once here and held everywhere below:

- Nothing here runs at startup, and nothing moves unless the
  operator runs this tool with --apply. Planning is the default.
- Nothing is ever deleted, and nothing is ever overwritten. A
  name that is taken in the shelter gets a numbered suffix.
- Nothing leaves the machine. The only record is a manifest
  inside the shelter folder itself, on the operator's own disk,
  so the operator can put everything back with --restore. No
  name seen here is logged, printed anywhere but the operator's
  own terminal, or sent anywhere.
- The config security mode for the feature
  "personal_docs_shelter" gates the tool, in the family's usual
  shape: off refuses to plan or apply, audit plans only,
  enforce lets the operator's --apply move files.
"""

import argparse
import json
import os
import shutil
import sys

try:
    from runner.oracle import personal_docs as _pd
    from runner.guard import security as _security
    from runner.guard import atomicio as _atomicio
except ImportError:  # script mode: runner/ is on sys.path
    from oracle import personal_docs as _pd  # noqa: F401
    from guard import security as _security  # noqa: F401
    from guard import atomicio as _atomicio  # noqa: F401

FEATURE = "personal_docs_shelter"

MANIFEST_NAME = "shelter-manifest.json"
MANIFEST_FORMAT = "hp-personal-docs-shelter"
MANIFEST_VERSION = 1

# Planning walks the same shallow shape the check walks, but it
# collects instead of stopping at the first hit, so its budget is
# larger. Still bounded: a home directory can be huge.
_PLAN_ENTRY_CAP = 20000


class ShelterError(Exception):
    """A structural refusal: the shelter cannot proceed safely.
    Per-item failures are collected in results, never raised."""


def shelter_root(home):
    """The shelter folder: <Desktop>/Sheltered Documents when a
    Desktop folder exists, else directly under home."""
    desktop = os.path.join(home, "Desktop")
    base = desktop if os.path.isdir(desktop) else home
    return os.path.join(base, _pd.SHELTER_DIR_NAME)


def _watched_roots(home):
    """The same watched folders the check scans, as (label, path)
    pairs. The label names the folder's place under home and
    becomes the item's subfolder inside the shelter, so two
    watched folders never mix their contents."""
    out = []
    try:
        with os.scandir(home) as scan:
            top = list(scan)
    except OSError:
        return out
    for ent in top:
        if ent.name.startswith("."):
            continue
        try:
            if ent.is_symlink() or not ent.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        low = ent.name.lower()
        if low in _pd._WATCHED:
            out.append((ent.name, ent.path))
        elif low.startswith("onedrive"):
            for child in ("Documents", "Desktop", "Downloads"):
                path = os.path.join(ent.path, child)
                if os.path.isdir(path) and not os.path.islink(path):
                    out.append((os.path.join(ent.name, child), path))
    for extra in _pd._xdg_dirs(home):
        label = os.path.relpath(extra, home).replace(os.sep, "-")
        out.append((label, extra))
    seen = set()
    roots = []
    for label, path in out:
        real = os.path.realpath(path)
        if real in seen or not _pd._under_home(home, real):
            continue
        seen.add(real)
        roots.append((label, real))
    return roots


def _collect(root, label, depth, budget, home, skip_real, found):
    if depth > _pd._DEPTH:
        return
    try:
        entries = os.scandir(root)
    except OSError:
        return
    with entries:
        for ent in entries:
            budget[0] += 1
            if budget[0] > _PLAN_ENTRY_CAP:
                return
            if ent.name.startswith(".") or ent.name.lower() in _pd._SKIP_DIRS:
                continue
            try:
                if ent.is_symlink():
                    continue
                is_dir = ent.is_dir(follow_symlinks=False)
            except OSError:
                continue
            real = os.path.realpath(ent.path)
            if real == skip_real or real.startswith(skip_real + os.sep):
                continue
            if _pd._sensitive(ent.name):
                dest = os.path.join(label, ent.name)
                found.append({"source": ent.path, "dest": dest})
                continue
            if is_dir and depth < _pd._DEPTH:
                _collect(ent.path, os.path.join(label, ent.name),
                         depth + 1, budget, home, skip_real, found)


def plan_shelter(home):
    """What sheltering would move: a list of {"source", "dest"}
    where dest is relative to the shelter root. Changes nothing.
    A sensitive folder is one item: its contents move with it and
    are not listed separately."""
    if not home or not isinstance(home, str) or not os.path.isdir(home):
        return []
    root = shelter_root(home)
    skip_real = os.path.realpath(root)
    budget = [0]
    found = []
    for label, path in _watched_roots(home):
        _collect(path, label, 0, budget, home, skip_real, found)
    found.sort(key=lambda item: item["source"])
    return found


def _free_dest(root, rel):
    """A destination path for rel that overwrites nothing: the
    name itself, or with a numbered suffix before the extension."""
    dest = os.path.join(root, rel)
    if not os.path.lexists(dest):
        return dest
    folder, name = os.path.split(rel)
    stem, ext = os.path.splitext(name)
    n = 2
    while True:
        candidate = os.path.join(root, folder, "%s (%d)%s" % (stem, n, ext))
        if not os.path.lexists(candidate):
            return candidate
        n += 1


def _manifest_path(root):
    return os.path.join(root, MANIFEST_NAME)


def load_manifest(home):
    """The shelter's manifest entries, validated fail-closed.

    Every entry must name a sheltered path inside the shelter and
    an original path inside home, with no other keys. Anything
    else -- unparseable, wrong format, an escape in either
    direction -- raises ShelterError and nothing moves."""
    root = shelter_root(home)
    path = _manifest_path(root)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        raise ShelterError("shelter manifest is unreadable: %s" % (exc,))
    if not isinstance(data, dict) \
            or data.get("format") != MANIFEST_FORMAT \
            or data.get("version") != MANIFEST_VERSION \
            or not isinstance(data.get("entries"), list):
        raise ShelterError("shelter manifest has an unknown shape")
    root_real = os.path.realpath(root)
    seen_dest = set()
    entries = []
    for item in data["entries"]:
        if not isinstance(item, dict) or set(item) != {"from", "to"} \
                or not isinstance(item["from"], str) \
                or not isinstance(item["to"], str) \
                or "\x00" in item["from"] or "\x00" in item["to"]:
            raise ShelterError("shelter manifest holds a malformed entry")
        to_real = os.path.realpath(item["to"])
        if to_real == root_real \
                or not to_real.startswith(root_real + os.sep):
            raise ShelterError("shelter manifest points outside the shelter")
        if not _pd._under_home(home, item["from"]):
            raise ShelterError("shelter manifest points outside home")
        if to_real in seen_dest:
            raise ShelterError("shelter manifest names a destination twice")
        seen_dest.add(to_real)
        entries.append({"from": item["from"], "to": item["to"]})
    return entries


def _save_manifest(root, entries):
    data = {"format": MANIFEST_FORMAT, "version": MANIFEST_VERSION,
            "entries": entries}
    _atomicio.write_json(_manifest_path(root), data, indent=2,
                         sort_keys=True, newline=True)


def _ensure_shelter(root):
    os.makedirs(root, mode=0o700, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    marker = os.path.join(root, _pd.SHELTER_MARKER_NAME)
    if not os.path.exists(marker):
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(_pd.SHELTER_MARKER_MAGIC + "\n")
            fh.write("Files gathered here by the Homing Pigeon "
                     "personal-documents shelter. The manifest in "
                     "this folder records where each item came "
                     "from, so the shelter tool can put it back.\n")


def apply_shelter(home, plan=None):
    """Move every planned item into the shelter. Returns
    {"moved": [...], "errors": [{"source", "error"}]}.

    A manifest from an earlier sheltering is extended, never
    replaced blindly: if it cannot be read and validated, this
    refuses (ShelterError) rather than orphan what is already
    sheltered."""
    if plan is None:
        plan = plan_shelter(home)
    root = shelter_root(home)
    existing = load_manifest(home)
    _ensure_shelter(root)
    moved = []
    errors = []
    entries = list(existing)
    for item in plan:
        dest = _free_dest(root, item["dest"])
        try:
            os.makedirs(os.path.dirname(dest), mode=0o700, exist_ok=True)
            shutil.move(item["source"], dest)
        except (OSError, shutil.Error) as exc:
            errors.append({"source": item["source"], "error": str(exc)})
            continue
        record = {"from": item["source"], "to": dest}
        entries.append(record)
        moved.append(record)
    if moved:
        _save_manifest(root, entries)
    return {"moved": moved, "errors": errors}


def restore_shelter(home):
    """Put every sheltered item back where it came from. Never
    overwrites: an original place that is occupied again is an
    error entry, and that item stays sheltered and recorded.
    Returns {"restored": [...], "errors": [{"to", "error"}]}."""
    root = shelter_root(home)
    entries = load_manifest(home)
    restored = []
    errors = []
    remaining = []
    for entry in entries:
        src, dest = entry["to"], entry["from"]
        if not os.path.lexists(src):
            errors.append({"to": src, "error": "sheltered item is missing"})
            remaining.append(entry)
            continue
        if os.path.lexists(dest):
            errors.append({"to": src,
                           "error": "original place is occupied again"})
            remaining.append(entry)
            continue
        try:
            parent = os.path.dirname(dest)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.move(src, dest)
        except (OSError, shutil.Error) as exc:
            errors.append({"to": src, "error": str(exc)})
            remaining.append(entry)
            continue
        restored.append(entry)
    if restored:
        if remaining:
            _save_manifest(root, remaining)
        else:
            try:
                os.unlink(_manifest_path(root))
            except OSError:
                pass
    return {"restored": restored, "errors": errors}


def _load_config(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ShelterError("config must be a JSON object")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="personal_docs_shelter",
        description="Gather personal documents into one sheltered "
                    "folder on the Desktop, or put them back. "
                    "Planning is the default; nothing moves "
                    "without --apply.")
    parser.add_argument("--home", default=os.path.expanduser("~"),
                        help="home directory to shelter (default: ~)")
    parser.add_argument("--config", default=None,
                        help="runner config.json; its security mode "
                             "for personal_docs_shelter gates this tool")
    parser.add_argument("--apply", action="store_true",
                        help="move the planned items into the shelter")
    parser.add_argument("--restore", action="store_true",
                        help="put sheltered items back where they came from")
    args = parser.parse_args(argv)
    home = args.home
    try:
        cfg = _load_config(args.config)
        _security.validate_security_config(cfg)
    except (OSError, ValueError, RuntimeError, ShelterError) as exc:
        print("shelter: %s" % (exc,), file=sys.stderr)
        return 2
    mode = _security.sec_mode(cfg, FEATURE)
    if mode == "off":
        print("shelter: the personal_docs_shelter security mode is "
              "off; nothing was planned or moved.", file=sys.stderr)
        return 2
    try:
        if args.restore:
            result = restore_shelter(home)
            for entry in result["restored"]:
                print("restored: %s" % (entry["from"],))
            for entry in result["errors"]:
                print("not restored: %s (%s)"
                      % (entry["to"], entry["error"]), file=sys.stderr)
            print("shelter: %d restored, %d not restored."
                  % (len(result["restored"]), len(result["errors"])))
            return 1 if result["errors"] else 0
        plan = plan_shelter(home)
        if not plan:
            print("shelter: nothing to shelter.")
            return 0
        if args.apply and mode == "enforce":
            result = apply_shelter(home, plan)
            for record in result["moved"]:
                print("sheltered: %s -> %s"
                      % (record["from"], record["to"]))
            for entry in result["errors"]:
                print("not sheltered: %s (%s)"
                      % (entry["source"], entry["error"]), file=sys.stderr)
            print("shelter: %d sheltered into %s, %d not sheltered."
                  % (len(result["moved"]), shelter_root(home),
                     len(result["errors"])))
            return 1 if result["errors"] else 0
        for item in plan:
            print("would shelter: %s -> %s"
                  % (item["source"],
                     os.path.join(shelter_root(home), item["dest"])))
        if args.apply and mode == "audit":
            print("shelter: the personal_docs_shelter security mode "
                  "is audit, so this was a plan only; nothing moved.")
        else:
            print("shelter: %d item(s) planned; nothing moved. "
                  "Run with --apply to shelter them." % (len(plan),))
        return 0
    except ShelterError as exc:
        print("shelter: %s" % (exc,), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
