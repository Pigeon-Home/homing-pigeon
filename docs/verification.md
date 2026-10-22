# Verifying a release

Every Homing Pigeon release carries the machinery to check that
the bits you downloaded are the bits the build produced — on
every outlet, not just GitHub. This page walks the chain from a
release tag to the files on your disk and gives the exact
command for each link. Nothing here needs project credentials;
the anchor of trust is a Sigstore attestation that anyone can
verify with the `gh` CLI.

The chain, in one paragraph: the tag build stamps a
`BUILD-PROVENANCE.json` into each archive, generates an SBOM,
hashes every release file into `SHA384SUMS`, and attests the
whole set — sums and SBOM included — with
`actions/attest-build-provenance`. PyPI publishing runs over
OIDC trusted publishing (no stored token exists) and uploads
its own provenance. The Docker image is attested by digest in
the registry. The SourceForge and GitLab mirrors copy the
GitHub release assets unchanged, sums file and SBOM included,
so the same checks work there — with one caution, stated in
the mirror section below.

Examples below use `vX.Y.Z` and `X.Y.Z` for the release; the
current version lives in `pyproject.toml`, never in this page.

## GitHub Release

Download the archive and `SHA384SUMS` from the release page,
then check the file against the sums:

```sh
sha384sum -c SHA384SUMS
```

(On macOS: `shasum -a 384 -c SHA384SUMS`.)

That proves the file matches what the release job hashed. The
sums file itself is covered by the build attestation, which is
the link that ties the set to the workflow run on the tag:

```sh
gh attestation verify homing-pigeon-linux-x86_64-X.Y.Z.tar.gz \
    --repo Pigeon-Home/homing-pigeon
```

The same command works for every file in the release —
archives, wheel, sdist, `SBOM.spdx.json`, and `SHA384SUMS`
itself — because the attestation's subject is the whole
artifact set. A successful verify reports the workflow
(`build.yml`), the repository, and the commit the tag points
at.

## PyPI

`pip install pigeon-home-runner` fetches the wheel (or sdist)
from PyPI. Two independent checks:

1. **Provenance.** Publishing uses OIDC trusted publishing:
   no PyPI token is stored anywhere, and each file carries a
   PEP 740 attestation naming the GitHub repository and
   workflow that published it. PyPI shows it on the project's
   release page, and serves it as JSON:

   ```text
   https://pypi.org/integrity/pigeon-home-runner/X.Y.Z/pigeon_home_runner-X.Y.Z-py3-none-any.whl/provenance
   ```

   The bundle's publisher block names kind `GitHub`,
   repository `Pigeon-Home/homing-pigeon`, workflow
   `build.yml`. If it names anything else, the file did not
   come from this pipeline.

2. **Sums.** The wheel and sdist on PyPI are the same files
   the GitHub release carries, so the attested `SHA384SUMS`
   from the GitHub release covers them:

   ```sh
   sha384sum pigeon_home_runner-X.Y.Z-py3-none-any.whl
   # compare against the line in SHA384SUMS
   ```

## Docker (GHCR)

The image workflow builds for the tag and pushes a Sigstore
attestation for the image digest to the registry alongside the
image. Get the digest for the tag, then verify it:

```sh
docker buildx imagetools inspect \
    ghcr.io/pigeon-home/homing-pigeon:vX.Y.Z
gh attestation verify \
    oci://ghcr.io/pigeon-home/homing-pigeon@sha256:<digest> \
    --owner Pigeon-Home
```

Verify by digest, not by tag: a tag can be re-pointed, a
digest cannot.

## SourceForge and GitLab mirrors

Both mirrors copy the published GitHub release assets —
archives, wheel, sdist, `SHA384SUMS`, and `SBOM.spdx.json` —
without repacking them, so after downloading from a mirror
the sums check works exactly as above:

```sh
sha384sum -c SHA384SUMS
```

The caution: a sums file is only as trustworthy as where you
got it. A `SHA384SUMS` downloaded from a mirror proves the
other mirror files match *it*; the attestation that anchors
the set to the tag build lives on GitHub. So either verify one
file (or the sums file) with `gh attestation verify` as in
the GitHub section, or compare the mirror's `SHA384SUMS`
against the one on the GitHub release page. After that single
anchored check, the sums verify everything else locally.

## Inside each archive: BUILD-PROVENANCE.json

Every install archive carries a stamp placed in the tree
before it was packed:

```sh
tar tzf homing-pigeon-linux-x86_64-X.Y.Z.tar.gz | grep PROVENANCE
tar xzf homing-pigeon-linux-x86_64-X.Y.Z.tar.gz -O \
    homing-pigeon-linux-x86_64-X.Y.Z/BUILD-PROVENANCE.json
```

(Windows: `tar -xzf ... -O` works the same way in a current
PowerShell, or read the file after extracting the zip.)

It names the product, the version, the commit SHA, the ref,
and the workflow run (`run_id`, as run/attempt) that built the
archive. A file that arrives detached from any release page —
a mirror, a forwarded email — can still say which build it
is, and the commit can be checked against the tag.

## The project snapshot

Every install archive carries `project/`, and the same snapshot
ships alone as `homing-pigeon-project-<version>.tar.gz`: every
tracked file at the tag, the full history as
`project/.history/homing-pigeon.bundle`, and `CI-SNAPSHOT.json`
(the workflows, the platform jobs, and the test results of the run
that built the release). It is added to the archives before
`SHA384SUMS` is computed, so the sums and the attestation above
cover it like everything else. To check the history against the tag:

```sh
git clone project/.history/homing-pigeon.bundle hp && cd hp
git rev-parse "vX.Y.Z^{commit}"   # matches "commit" in CI-SNAPSHOT.json
```

## The SBOM

`SBOM.spdx.json` (SPDX 2.3) ships with every release and is
covered by both the sums and the attestation. Because the
runtime is stdlib-only, it is short: the project with every
shipped `runner/` and `cloud/` module (per-file checksums),
CPython at the version range `pyproject.toml` declares, and
PyInstaller at the version pinned in `requirements-ci.txt` —
the one build tool whose output ships. Read it with any SPDX
tool, or as plain JSON:

```sh
python3 -m json.tool SBOM.spdx.json | head -40
```

## What the chain does not claim

- It proves a file is the file the tag build produced. It
  does not prove the build was benign — for that, the source
  is the tag itself, and the suite that ran on it is in the
  same workflow run the attestation names.
- The mirror check anchors on GitHub once, as described
  above; after that anchor, everything is local.
