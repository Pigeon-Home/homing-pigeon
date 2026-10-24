#!/usr/bin/env python3
"""Stamp a BUILD-PROVENANCE.json into a built artifact tree.

OneFuzz stamped its CI run id and git SHA into the shipped
artifact (ApiService/onefuzzlib/build.id, git.version); this is
the same move for Homing Pigeon's staged trees. The GitHub
attestation proves a release on the release page, but a file
that arrives via a mirror -- or attached to a support email --
carries nothing. The stamp is a small JSON object placed in the
staged tree before archiving, so every archive can answer
"which build am I?" on its own:

    product     artifact name (the archive's directory name)
    version     the project version from pyproject.toml
    commit      GITHUB_SHA of the build
    ref         GITHUB_REF (a tag ref on release builds)
    workflow    GITHUB_WORKFLOW that built it
    run_id      GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT
    job         the build job, passed as --job
    builder     "GitHub Actions (<job>) on <RUNNER_OS>"
    built_at    UTC timestamp, ISO 8601 with a Z suffix

Every field degrades to "unknown" outside CI (a local stamp is
still a stamp), except the version, which is read from the
tree being stamped. Stdlib only, like the rest of the project.

Usage: python .github/tools/stamp_provenance.py --job build-linux \
           --out pkg/<name>/BUILD-PROVENANCE.json
"""

import argparse
import datetime
import json
import os
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 hosts
    tomllib = None


def _version(root):
    """The project version, from the tree being stamped."""
    if tomllib is not None:
        with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    # Stdlib-only fallback for old interpreters: the version line
    # is a plain assignment in [project]; read just that.
    in_project = False
    with open(os.path.join(root, "pyproject.toml"),
              encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                in_project = line == "[project]"
            elif in_project and line.startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no [project] version in pyproject.toml")


def provenance(root, job, out_path, env=None, now=None):
    """Build the stamp dict. Pure: env and clock are injectable."""
    env = os.environ if env is None else env
    now = now or datetime.datetime.now(datetime.timezone.utc)
    run_id = env.get("GITHUB_RUN_ID") or "unknown"
    attempt = env.get("GITHUB_RUN_ATTEMPT") or "unknown"
    return {
        "product": os.path.basename(
            os.path.dirname(os.path.abspath(out_path))),
        "version": _version(root),
        "commit": env.get("GITHUB_SHA") or "unknown",
        "ref": env.get("GITHUB_REF") or "unknown",
        "workflow": env.get("GITHUB_WORKFLOW") or "unknown",
        "run_id": "%s/%s" % (run_id, attempt),
        "job": job,
        "builder": "GitHub Actions (%s) on %s"
                   % (job, env.get("RUNNER_OS") or "unknown"),
        "built_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--job", required=True,
                    help="the build job doing the stamping")
    ap.add_argument("--out", required=True,
                    help="where BUILD-PROVENANCE.json goes")
    ap.add_argument("--root", default=".",
                    help="checkout root holding pyproject.toml")
    args = ap.parse_args(argv)
    stamp = provenance(args.root, args.job, args.out)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(stamp, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("stamped %s: %s %s @ %s"
          % (args.out, stamp["product"], stamp["version"],
             stamp["commit"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
