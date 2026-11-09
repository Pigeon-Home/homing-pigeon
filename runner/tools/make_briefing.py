#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Build BRIEFING-DIGEST.md: the discovery surface, digested.

Stage 3 of the Oracle briefing (the design record is
docs/steady/design/oracle-briefing-design.md, shape 4). The
mailbox model's whole world is its prompt, so the discovery
surface it is briefed from is built ahead of time, once per
checkout, instead of being assembled live at every ask: the
manifest's extracts (runner/ops/briefing.py, the one curation
both forms share), stamped with the SHA-256 of every source
file they were drawn from and a combined hash over all of
them.

The build is deterministic: the same tree builds byte-
identical digest text wherever it stands -- no timestamps, no
absolute paths -- so two snapshots of the same commit carry
the same digest, and a changed source changes the combined
hash. The runner prefers the digest when it stands in the
resolved checkout (a deployment snapshot carries it) and
falls back to the live extracts everywhere else.

Usage: python3 -m runner.tools.make_briefing [ROOT] [--out P]
ROOT defaults to the tree this tool ships in; the digest is
written to ROOT/BRIEFING-DIGEST.md unless --out says otherwise.
"""
import argparse
import hashlib
import importlib.util
import os
import sys

DIGEST_NAME = "BRIEFING-DIGEST.md"


def _load_briefing():
    """The briefing module from the tree this tool ships in --
    the manifest has exactly one home, and this tool renders
    from it rather than restating it."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "ops", "briefing.py")
    spec = importlib.util.spec_from_file_location(
        "hp_make_briefing_manifest", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _file_hash(root, rel):
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        return "absent"


def build_digest(root, briefing=None):
    """(text, combined_hash) for the checkout at root. The text
    is the manifest's extracts under a provenance header that
    stamps each source's SHA-256; the combined hash is the
    SHA-256 of the per-source lines, in manifest order."""
    mod = briefing or _load_briefing()
    lines = ["# Briefing digest", "",
             "The project's discovery surface, digested from "
             "this checkout for the Oracle's briefing: the same "
             "texts a visiting system is briefed from, carried "
             "as the manifest's extracts (runner/ops/briefing.py) "
             "under a provenance header. Built deterministically "
             "-- the same tree always builds this same text.",
             "", "Sources (SHA-256 of each file as it stands "
             "in the checkout):", ""]
    stamps = []
    for entry in mod.BRIEFING_MANIFEST:
        digest = _file_hash(root, entry["path"])
        stamps.append(entry["path"] + ":" + digest)
        lines.append("- %s sha256:%s" % (entry["path"], digest))
    combined = hashlib.sha256(
        "\n".join(stamps).encode("utf-8")).hexdigest()
    lines += ["", "Combined source hash: sha256:" + combined, ""]
    text, _sources = mod.surface_extracts(root)
    lines.append(text)
    lines.append("")
    return "\n".join(lines), combined


def write_digest(root, out=None, briefing=None):
    """Write the digest for the checkout at root; returns
    (path, combined_hash)."""
    text, combined = build_digest(root, briefing=briefing)
    path = out or os.path.join(root, DIGEST_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path, combined


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build BRIEFING-DIGEST.md from a checkout's "
                    "discovery surface.")
    ap.add_argument("root", nargs="?", default=None,
                    help="checkout root (default: the tree this "
                         "tool ships in)")
    ap.add_argument("--out", default=None,
                    help="output path (default: "
                         "ROOT/BRIEFING-DIGEST.md)")
    args = ap.parse_args(argv)
    root = args.root or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    path, combined = write_digest(root, out=args.out)
    print("%s sha256:%s" % (path, combined))
    return 0


if __name__ == "__main__":
    sys.exit(main())
