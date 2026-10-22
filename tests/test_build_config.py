"""The frozen builds must actually contain what runner.py loads.

runner.py loads its sibling modules dynamically (``_load_mod`` /
``_load_attr`` with ``importlib.import_module``) so the same file runs
as a package member and as ``__main__`` from inside runner/. Dynamic
imports are invisible to PyInstaller's static analysis: without a
``--hidden-import`` per module, the one-file executables silently ship
without them -- _version most visibly, which made the Windows exe print
"unknown" for --version (CI run 39076097325); the other modules would
have degraded silently. This test keeps build.yml's hidden imports in
sync with every dynamic load in runner.py, and checks that the Linux
and macOS jobs smoke the built binaries' --version like Windows does.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _dynamic_runner_modules():
    with open(os.path.join(_root(), "runner", "runner.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(
        r'_load_(?:mod|attr)\(\s*"runner\.([A-Za-z0-9_]+)"', src))


def _workflow():
    with open(os.path.join(_root(), ".github", "workflows", "build.yml"),
              encoding="utf-8") as fh:
        return fh.read()


def _job_block(workflow, job):
    m = re.search(r"^  %s:\n(.*?)(?=^  [a-z-]+:|\Z)" % re.escape(job),
                  workflow, re.M | re.S)
    assert m, "no %s job in build.yml" % job
    return m.group(1)


class HiddenImportSyncTest(unittest.TestCase):
    def test_scan_finds_the_dynamic_loads(self):
        # Self-check: if the scan ever matches nothing, the sync test
        # below would pass vacuously. The loader set is in double
        # digits by design (one face per sibling module).
        self.assertGreaterEqual(len(_dynamic_runner_modules()), 10)

    def test_every_dynamic_load_is_a_hidden_import(self):
        workflow = _workflow()
        build_lines = [ln for ln in workflow.splitlines()
                       if "pyinstaller" in ln and "runner/runner.py" in ln]
        self.assertEqual(len(build_lines), 4,
                         "expected one runner build line per OS job")
        for line in build_lines:
            for mod in sorted(_dynamic_runner_modules()):
                self.assertIn("--hidden-import runner.%s" % mod, line,
                              "build line misses hidden import for %s" % mod)


class UnixVersionSmokeTest(unittest.TestCase):
    """Every POSIX archive is smoked by the one shared script, at the
    depth the Windows job already had: --version against pyproject,
    a planted credential that --inspect redact must not echo, the
    board inspector, and a --once --dry-run startup. Until this
    script existed, Linux, Pi Light and macOS checked --version
    and nothing else."""

    SMOKE = "tools/smoke_posix_binaries.sh ./dist/homing-pigeon ./dist/install"

    def test_every_posix_job_runs_the_shared_smoke(self):
        workflow = _workflow()
        for job in ("build-linux", "build-pi-light", "build-macos"):
            block = _job_block(workflow, job)
            self.assertIn(self.SMOKE, block,
                          "%s does not smoke its built binaries" % job)

    def test_the_shared_smoke_checks_what_windows_checks(self):
        with open(os.path.join(_root(), "tools",
                               "smoke_posix_binaries.sh"),
                  encoding="utf-8") as fh:
            script = fh.read()
        for needle in ("$RUNNER --version", "$INSTALL --version",
                       "--inspect redact", "--inspect board",
                       "--once --dry-run", "FLAG-CRED-", "REDACTED"):
            self.assertIn(needle, script, "smoke lacks %s" % needle)
        # The flag must be asserted absent, not merely present.
        self.assertIn("flag leaked", script)
        self.assertTrue(os.access(os.path.join(
            _root(), "tools", "smoke_posix_binaries.sh"), os.X_OK),
            "smoke script is not executable")


class MutationGateTest(unittest.TestCase):
    """Mutation is release-only (owner's call, 2026-10-17).

    The job is a signal, not a block, so it is
    gated on the ref: version tags run it, branch pushes and PRs
    skip it. The rule lives in build.yml so nobody has to remember
    to ask for it -- and this test is the proof of work for the
    change that put it there (verified live on run 39101780439:
    mutation skipped on a branch push, everything else green).
    """

    def test_mutation_runs_only_on_version_tags(self):
        block = _job_block(_workflow(), "mutation")
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", block)

    def test_the_gate_jobs_stay_ungated(self):
        # The jobs that gate everything else must run on every push;
        # a stray tag-only condition on one of them would silently
        # stop branch CI from meaning anything.
        workflow = _workflow()
        for job in ("test", "typecheck", "build-linux", "build-macos",
                    "build-windows", "build-python", "build-pi-light"):
            block = _job_block(workflow, job)
            self.assertNotIn("refs/tags", block,
                             "%s must not be tag-gated" % job)

    def test_mutation_is_a_signal_not_a_block(self):
        # "Signal, not a block" must hold in the run conclusion.
        # The mirror jobs need the release, not this job, so a
        # failed mutation cannot hold SourceForge or GitLab. It
        # still must not stamp the whole tag run 'failure' --
        # that is how v3.7.29 never reached either mirror, back
        # when they keyed off workflow_run.conclusion.
        block = _job_block(_workflow(), "mutation")
        self.assertIn("continue-on-error: true", block)

    def test_mutation_cannot_hold_a_tag_run_for_hours(self):
        # A stuck mutmut used to leave the tag run in_progress for
        # the platform default of 6 hours after the mirrors had
        # already published. The measured run is about 25 minutes;
        # the cap is that plus headroom, not the platform default.
        block = _job_block(_workflow(), "mutation")
        self.assertIn("timeout-minutes: 40", block)

    def test_real_gates_are_not_continue_on_error(self):
        # The mirror image of the pin above: if a job that gates
        # the release ever grows continue-on-error, a red suite
        # would publish. Only the signal job may carry it.
        workflow = _workflow()
        for job in ("test", "typecheck", "build-linux", "build-macos",
                    "build-windows", "build-python", "build-pi-light",
                    "release", "pypi-publish", "sourceforge", "gitlab"):
            block = _job_block(workflow, job)
            self.assertNotIn("continue-on-error", block,
                             "%s must stay a real gate" % job)


class PiLightArchiveTest(unittest.TestCase):
    """The release ships an archive that IS Pi Light, not only one
    that can be told to be (owner's ask, 2026-10-18: an artifact
    specifically called raspberry pi light). The build-pi-light
    job stages the ARM64 Linux tree with a default_profile marker
    naming pi-light; the installer honors the marker when the user
    names no profile (pinned in tests/test_pi_light.py). These
    pins keep the job, the marker, the archive name, and the
    release job's dependency from drifting apart.
    """

    def test_the_job_stages_the_marker_in_the_archive(self):
        block = _job_block(_workflow(), "build-pi-light")
        self.assertIn('name="homing-pigeon-pi-light-arm64-$ver"', block)
        self.assertIn('printf \'pi-light\\n\' > "pkg/$name/default_profile"',
                      block)
        self.assertIn("path: ${{ env.PKG_NAME }}.tar.gz", block)

    def test_the_job_builds_for_arm(self):
        head = _job_block(_workflow(), "build-pi-light").split("steps:")[0]
        self.assertIn("arm", head)

    def test_the_release_needs_the_job(self):
        # Without the dependency the release job can run before
        # the pi-light artifact exists and silently ship without it.
        block = _job_block(_workflow(), "release")
        self.assertIn("build-pi-light", block)

    def test_the_archive_name_trips_no_mirror_classifier(self):
        # The sourceforge job marks a release file as a platform's
        # default download when its name contains windows, linux,
        # or macos/darwin, and expects exactly 3 marks. The
        # pi-light archive must contain none of those words, or
        # the mirror publish fails on the next tag.
        for word in ("windows", "linux", "macos", "darwin"):
            self.assertNotIn(word, "homing-pigeon-pi-light-arm64-")

    def test_the_mirrors_count_four_install_archives(self):
        workflow = _workflow()
        for job in ("sourceforge", "gitlab"):
            self.assertIn("the four install archives",
                          _job_block(workflow, job), job)


def _also_copy():
    with open(os.path.join(_root(), "pyproject.toml"),
              encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"^also_copy = \[(.*?)\]", src, re.M | re.S)
    assert m, "no also_copy list in pyproject.toml [tool.mutmut]"
    # Strip TOML comments before harvesting the quoted entries: the
    # block's own comments quote a filename ("INSTALL.md not found"
    # is prose about the v3.7.29 failure, not an entry).
    body = []
    for line in m.group(1).splitlines():
        out, in_str = [], False
        for ch in line:
            if ch == '"':
                in_str = not in_str
            if ch == "#" and not in_str:
                break
            out.append(ch)
        body.append("".join(out))
    return set(re.findall(r'"([^"]+)"', "\n".join(body)))


class MutationTreeTest(unittest.TestCase):
    """mutmut runs the suite in a copied tree, not the checkout.

    Only source_paths, tests, and also_copy make the trip. A test
    that reads repo files the copy does not carry fails mutmut's
    baseline stats collection before a single mutant runs -- which
    is exactly how the v3.7.29 tag build's mutation job died: the
    live-docs guard asserts INSTALL.md and friends are scanned,
    but also_copy carried only docs/ and PROTOCOL.md, so the guard
    (correctly, in the real tree) reported them missing there.
    The doc guards' world and the mutant tree must stay the same
    world; these tests pin that.
    """

    def test_every_root_live_doc_is_copied(self):
        copied = _also_copy()
        root = _root()
        for name in sorted(os.listdir(root)):
            if name.endswith(".md") and name != "CHANGELOG.md":
                self.assertIn(name, copied,
                              "%s is a live root doc the mutant tree "
                              "never sees; add it to also_copy" % name)

    def test_the_doc_guards_expected_docs_are_copied(self):
        copied = _also_copy()
        for expected in ("README.md", "INSTALL.md", "AGENTS.md",
                         "PROTOCOL.md", "RUNBOOK.md"):
            self.assertIn(expected, copied)

    def test_the_ci_pin_file_is_copied(self):
        # PipelineLiftsTest reads requirements-ci.txt from the tree;
        # without a copy the v3.8.5 tag build's mutation job died in
        # baseline stats collection on exactly that missing file.
        self.assertIn("requirements-ci.txt", _also_copy())

    def test_the_sharded_runner_is_copied(self):
        # test_parallel_runner imports this file at load time.
        # A missing copy fails stats collection before any mutant.
        self.assertIn("tools/", _also_copy())

    def test_also_copy_file_entries_exist(self):
        root = _root()
        for entry in _also_copy():
            if not entry.endswith("/"):
                self.assertTrue(
                    os.path.exists(os.path.join(root, entry)),
                    "also_copy names %s, which is not on disk" % entry)


def _load_tool(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_root(), "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _perm_entries(block):
    """The permission grants in a job block, as 'key: value'."""
    return set(re.findall(
        r"(?m)^\s+(contents|id-token|attestations|packages|"
        r"security-events|actions|pull-requests):\s*(\S+)$", block))


class PipelineLiftsTest(unittest.TestCase):
    """The OneFuzz pipeline lifts (2026-10-18, lifts 1-6).

    OneFuzz's public pipeline had locked inputs and provenance
    stamped into the artifact; the audit found HP ahead on
    attestation machinery but floating its action refs and tool
    installs, granting default token permissions in build.yml,
    shipping no SBOM, and documenting no verification path. These
    pins keep the six lifts from quietly un-landing.
    """

    WORKFLOWS = ("build.yml", "docker.yml", "security.yml",
                 "minimal-userland.yml")

    def _wf(self, name):
        with open(os.path.join(_root(), ".github", "workflows", name),
                  encoding="utf-8") as fh:
            return fh.read()

    # Lift 3: every action ref is a full SHA, version in a comment.
    def test_every_action_is_sha_pinned_with_a_version_comment(self):
        pin = re.compile(r"uses:\s*\S+@[0-9a-f]{40}\s+#\s*\S+")
        checked = 0
        for name in self.WORKFLOWS:
            for line in self._wf(name).splitlines():
                if "uses:" in line:
                    checked += 1
                    self.assertRegex(
                        line, pin,
                        "%s: action not SHA-pinned with a version "
                        "comment: %s" % (name, line.strip()))
        self.assertGreaterEqual(checked, 30)

    # Lift 5: default-deny everywhere; grants are per-job and exact.
    def test_every_workflow_denies_by_default(self):
        for name in self.WORKFLOWS:
            top = self._wf(name).split("jobs:")[0]
            self.assertTrue(
                "permissions: {}" in top
                or "permissions:\n  contents: read" in top,
                "%s has no default-deny top-level permissions" % name)

    def test_build_grants_are_exact_per_job(self):
        workflow = _workflow()
        read_only = {("contents", "read")}
        for job in ("test", "typecheck", "mutation", "build-windows",
                    "build-linux", "build-pi-light", "build-macos",
                    "build-python"):
            self.assertEqual(read_only,
                             _perm_entries(_job_block(workflow, job)),
                             "%s grants more than checkout" % job)
        self.assertEqual(
            {("contents", "write"), ("id-token", "write"),
             ("attestations", "write")},
            _perm_entries(_job_block(workflow, "release")))
        self.assertEqual({("id-token", "write")},
                         _perm_entries(_job_block(workflow,
                                                  "pypi-publish")))

    def test_the_other_workflows_grants_are_exact(self):
        docker = self._wf("docker.yml")
        self.assertEqual(
            {("contents", "read"), ("packages", "write"),
             ("id-token", "write"), ("attestations", "write")},
            _perm_entries(_job_block(docker, "build-and-push")))
        workflow = _workflow()
        for job in ("sourceforge", "gitlab"):
            block = _job_block(workflow, job)
            self.assertEqual({("contents", "read")},
                             _perm_entries(block), job)
            self.assertIn("refs/tags/v", block)
            self.assertIn("needs: [release]", block)

    def test_codeql_ignores_tests_and_examples_only(self):
        workflow = self._wf("security.yml")
        self.assertIn("config-file: ./.github/codeql/codeql-config.yml",
                      workflow)
        self.assertNotIn("queries:", workflow)
        with open(os.path.join(_root(), ".github", "codeql",
                               "codeql-config.yml"),
                  encoding="utf-8") as fh:
            config = fh.read()
        self.assertIn("- tests/**", config)
        self.assertIn("- examples/**", config)
        self.assertIn("py/clear-text-logging-sensitive-data", config)
        self.assertIn("py/polynomial-redos", config)
        self.assertIn("py/bind-socket-all-network-interfaces", config)
        self.assertNotIn("py/sql-injection", config)

    # Lift 6: CI installs resolve through the one pin file.
    def test_ci_installs_come_from_the_pin_file(self):
        for line in _workflow().splitlines():
            if "pip install" in line:
                self.assertIn("-c requirements-ci.txt", line,
                              "unconstrained install: %s" % line)
        with open(os.path.join(_root(), "requirements-ci.txt"),
                  encoding="utf-8") as fh:
            pins = fh.read()
        for tool in ("hypothesis", "pytest", "build", "mutmut",
                     "pyrefly", "pyinstaller"):
            self.assertRegex(pins, r"(?m)^%s==\d" % tool,
                             "%s is not pinned" % tool)
        # The version used to live in a workflow env var as a
        # second source of truth; the pin file is the only one now.
        self.assertNotIn("PYINSTALLER_VERSION", _workflow())

    # Lift 4: provenance is stamped into every staged tree, before
    # the archive is made, and into the Python dist.
    def test_every_packaging_step_stamps_provenance(self):
        workflow = _workflow()
        for job, packer in (("build-windows", "Compress-Archive"),
                            ("build-linux", "tar czf"),
                            ("build-pi-light", "tar czf"),
                            ("build-macos", "tar czf")):
            block = _job_block(workflow, job)
            stamp = "tools/stamp_provenance.py --job %s" % job
            self.assertIn(stamp, block, "%s never stamps" % job)
            self.assertLess(block.index(stamp), block.index(packer),
                            "%s stamps after archiving" % job)
        self.assertIn("tools/stamp_provenance.py --job build-python",
                      _job_block(workflow, "build-python"))

    def test_the_stamp_carries_the_build_identity(self):
        import datetime
        stamp = _load_tool("stamp_provenance")
        env = {"GITHUB_SHA": "a" * 40, "GITHUB_REF": "refs/tags/vX",
               "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1",
               "GITHUB_WORKFLOW": "build", "RUNNER_OS": "Linux"}
        out = os.path.join(_root(), "pkg", "probe",
                           "BUILD-PROVENANCE.json")
        got = stamp.provenance(_root(), "build-linux", out, env=env,
                               now=datetime.datetime(2026, 1, 2, 3, 4, 5))
        self.assertEqual(got["commit"], "a" * 40)
        self.assertEqual(got["run_id"], "42/1")
        self.assertEqual(got["product"], "probe")
        self.assertEqual(got["built_at"], "2026-01-02T03:04:05Z")
        import tomllib
        with open(os.path.join(_root(), "pyproject.toml"), "rb") as fh:
            self.assertEqual(got["version"],
                             tomllib.load(fh)["project"]["version"])

    # Lift 2: the SBOM is generated into the artifact set before
    # the sums, so the sums cover it and the attestation covers
    # the sums; the publish job keeps non-distributions out.
    def test_release_generates_the_sbom_before_the_sums(self):
        block = _job_block(_workflow(), "release")
        self.assertIn("tools/make_sbom.py "
                      "--out artifacts/SBOM.spdx.json", block)
        self.assertLess(block.index("actions/checkout@"),
                        block.index("actions/download-artifact@"))
        self.assertLess(block.index("make_sbom"),
                        block.index("sha384sum"))
        self.assertLess(block.index("sha384sum"),
                        block.index("attest-build-provenance"))

    def test_pypi_publish_keeps_the_stamp_out_of_the_upload(self):
        block = _job_block(_workflow(), "pypi-publish")
        self.assertIn("rm -f dist/BUILD-PROVENANCE.json", block)

    def test_the_sbom_describes_the_tree(self):
        import datetime
        import hashlib
        import tomllib
        sbom = _load_tool("make_sbom")
        doc = sbom.build_sbom(
            _root(), env={},
            now=datetime.datetime(2026, 1, 2, 3, 4, 5))
        self.assertEqual(doc["spdxVersion"], "SPDX-2.3")
        by_name = {p["name"]: p for p in doc["packages"]}
        with open(os.path.join(_root(), "pyproject.toml"), "rb") as fh:
            project = tomllib.load(fh)["project"]
        root_pkg = by_name[project["name"]]
        self.assertEqual(root_pkg["versionInfo"], project["version"])
        self.assertEqual(root_pkg["licenseConcluded"], "Apache-2.0")
        self.assertEqual(by_name["CPython"]["versionInfo"],
                         project["requires-python"])
        self.assertEqual(by_name["PyInstaller"]["versionInfo"],
                         sbom._ci_pin(_root(), "pyinstaller"))
        expected = set()
        for top in ("runner", "cloud"):
            for dirpath, _dirs, names in os.walk(
                    os.path.join(_root(), top)):
                for name in names:
                    if name.endswith(".py"):
                        expected.add("./" + os.path.relpath(
                            os.path.join(dirpath, name),
                            _root()).replace(os.sep, "/"))
        files = {f["fileName"]: f for f in doc["files"]}
        self.assertEqual(set(files), expected)
        self.assertEqual(set(root_pkg["hasFiles"]),
                         {f["SPDXID"] for f in doc["files"]})
        probe = files["./runner/runner.py"]
        with open(os.path.join(_root(), "runner", "runner.py"),
                  "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        self.assertIn({"algorithm": "SHA256", "checksumValue": digest},
                      probe["checksums"])
        sha1s = sorted(next(c["checksumValue"] for c in f["checksums"]
                            if c["algorithm"] == "SHA1")
                       for f in doc["files"])
        code = hashlib.sha1("".join(sha1s).encode("ascii")).hexdigest()
        self.assertEqual(
            root_pkg["packageVerificationCode"]
                    ["packageVerificationCodeValue"], code)

    # Lift 1: the verification chain is documented, with commands.
    def test_verification_doc_carries_the_chain(self):
        with open(os.path.join(_root(), "docs", "verification.md"),
                  encoding="utf-8") as fh:
            doc = fh.read()
        for needle in ("gh attestation verify",
                       "sha384sum -c SHA384SUMS",
                       "imagetools inspect",
                       "integrity/pigeon-home-runner",
                       "SBOM.spdx.json", "BUILD-PROVENANCE.json"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
