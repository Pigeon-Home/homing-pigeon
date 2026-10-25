#!/usr/bin/env python3
"""Generate the release SBOM: SPDX 2.3 JSON, stdlib only.

The runtime is stdlib-only, so the honest SBOM is short:

  - the project itself, with every shipped Python module under
    runner/ (the cloud helpers in runner/cloud/ included) listed
    as an SPDX file (SHA-1 + SHA-256 checksums, and the package
    verification code the spec asks of a files-analyzed package);
  - CPython, the only runtime dependency, at the version range
    pyproject.toml declares (requires-python);
  - PyInstaller, the build tool that froze the executables, at
    the version pinned in .github/requirements-ci.txt -- the same file
    CI installs from, so the SBOM cannot drift from the build.

Component licenses are stated where the tree states them (the
project's own, CPython's) and NOASSERTION where it does not
(PyInstaller's), rather than guessed. The release job runs this
into artifacts/ BEFORE SHA384SUMS is generated, so the sums
cover the SBOM and the build attestation covers both; the
mirrors then carry it like every other release asset.

Usage: python runner/tools/make_sbom.py --out artifacts/SBOM.spdx.json
"""

import argparse
import datetime
import hashlib
import json
import os
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 hosts
    tomllib = None

SPDX_VERSION = "SPDX-2.3"
SOURCE_DIRS = ("runner",)
REPO_URL = "https://github.com/Pigeon-Home/homing-pigeon"


def _project(root):
    """(name, version, requires-python, license) from pyproject."""
    if tomllib is None:
        raise SystemExit("make_sbom needs Python 3.11+ (tomllib)")
    with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
        project = tomllib.load(fh)["project"]
    return (project["name"], project["version"],
            project.get("requires-python", ""),
            project.get("license", {}).get("text", "NOASSERTION"))


def _ci_pin(root, package):
    """The exact version .github/requirements-ci.txt pins for a tool."""
    path = os.path.join(root, ".github/requirements-ci.txt")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line.lower().startswith(package.lower() + "=="):
                # The first pin is the build Python's; an environment
                # marker ("; python_version ...") is not the version.
                return line.split("==", 1)[1].split(";", 1)[0].strip()
    raise SystemExit("no pin for %s in .github/requirements-ci.txt" % package)


def _source_files(root):
    """Every shipped module, sorted, with both checksums."""
    found = []
    for top in SOURCE_DIRS:
        base = os.path.join(root, top)
        for dirpath, dirnames, filenames in os.walk(base):
            # The suite, the CI scripts and the example extensions
            # (runner/tests/, runner/tools/, runner/extensions/) are
            # not shipped.
            dirnames[:] = [d for d in dirnames if d != "__pycache__"
                           and not (dirpath == base
                                    and d in "tests tools extensions".split())]
            for name in filenames:
                if name.endswith(".py"):
                    found.append(os.path.join(dirpath, name))
    files = []
    for path in sorted(found):
        with open(path, "rb") as fh:
            blob = fh.read()
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        files.append({
            "SPDXID": "SPDXRef-File-" + rel.replace("/", "-"),
            "fileName": "./" + rel,
            "checksums": [
                {"algorithm": "SHA1",
                 "checksumValue": hashlib.sha1(blob).hexdigest()},
                {"algorithm": "SHA256",
                 "checksumValue": hashlib.sha256(blob).hexdigest()},
            ],
        })
    return files


def _verification_code(files):
    """SPDX package verification code: SHA-1 over the sorted,
    concatenated per-file SHA-1 checksums (spec, SPDX 2.3)."""
    sha1s = sorted(
        next(c["checksumValue"] for c in f["checksums"]
             if c["algorithm"] == "SHA1")
        for f in files)
    return hashlib.sha1("".join(sha1s).encode("ascii")).hexdigest()


def build_sbom(root, env=None, now=None):
    """The SBOM document as a dict. Pure: env/clock injectable."""
    env = os.environ if env is None else env
    now = now or datetime.datetime.now(datetime.timezone.utc)
    name, version, requires_python, license_id = _project(root)
    files = _source_files(root)
    run = env.get("GITHUB_RUN_ID") or "local"
    ref = env.get("GITHUB_REF_NAME") or "local"
    root_pkg = "SPDXRef-Package-" + name
    return {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "%s-%s-sbom" % (name, version),
        "documentNamespace": "%s/releases/%s/sbom-%s"
                             % (REPO_URL, ref, run),
        "creationInfo": {
            "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: homing-pigeon runner/tools/make_sbom.py"],
        },
        "documentDescribes": [root_pkg],
        "packages": [
            {
                "SPDXID": root_pkg,
                "name": name,
                "versionInfo": version,
                "supplier": "Organization: Pigeon-Home",
                "downloadLocation": REPO_URL,
                "filesAnalyzed": True,
                "hasFiles": [f["SPDXID"] for f in files],
                "packageVerificationCode": {
                    "packageVerificationCodeValue":
                        _verification_code(files),
                },
                "licenseConcluded": license_id,
                "licenseDeclared": license_id,
                "copyrightText": "NOASSERTION",
                "externalRefs": [{
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": "pkg:pypi/%s@%s"
                                        % (name, version),
                }],
            },
            {
                "SPDXID": "SPDXRef-Package-CPython",
                "name": "CPython",
                "versionInfo": requires_python,
                "supplier": "Organization: Python Software Foundation",
                "downloadLocation": "https://www.python.org/",
                "filesAnalyzed": False,
                "licenseConcluded": "Python-2.0",
                "licenseDeclared": "Python-2.0",
                "copyrightText": "NOASSERTION",
                "comment": "The only runtime dependency: the "
                           "interpreter itself. versionInfo is "
                           "the range pyproject.toml declares.",
            },
            {
                "SPDXID": "SPDXRef-Package-PyInstaller",
                "name": "PyInstaller",
                "versionInfo": _ci_pin(root, "pyinstaller"),
                "supplier": "NOASSERTION",
                "downloadLocation":
                    "https://pypi.org/project/pyinstaller/",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "comment": "Build tool only: it freezes the "
                           "executables in the install archives "
                           "and is not part of the runtime.",
            },
        ],
        "files": files,
        "relationships": [
            {"spdxElementId": "SPDXRef-DOCUMENT",
             "relationshipType": "DESCRIBES",
             "relatedSpdxElement": root_pkg},
            {"spdxElementId": root_pkg,
             "relationshipType": "DEPENDS_ON",
             "relatedSpdxElement": "SPDXRef-Package-CPython"},
            {"spdxElementId": root_pkg,
             "relationshipType": "GENERATED_FROM",
             "relatedSpdxElement": "SPDXRef-Package-PyInstaller"},
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True,
                    help="where the SPDX JSON goes")
    ap.add_argument("--root", default=".",
                    help="checkout root holding pyproject.toml")
    args = ap.parse_args(argv)
    sbom = build_sbom(args.root)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(sbom, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("wrote %s: %d packages, %d files"
          % (args.out, len(sbom["packages"]), len(sbom["files"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
