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


def _uncommented(text):
    """The YAML with its comment lines dropped: what Actions reads.

    A pin on a key's absence must not trip on prose that names the
    key while explaining why it is gone.
    """
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith("#"))


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
        self.assertEqual(len(build_lines), 7,
                         "expected one runner build line per binary job")
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

    SMOKE = "runner/tools/smoke_posix_binaries.sh ./dist/homing-pigeon ./dist/install"

    def test_every_posix_job_runs_the_shared_smoke(self):
        workflow = _workflow()
        for job in ("build-linux", "build-linux-arm64", "build-pi-light",
                    "build-macos", "build-macos-x86_64"):
            block = _job_block(workflow, job)
            self.assertIn(self.SMOKE, block,
                          "%s does not smoke its built binaries" % job)

    def test_the_shared_smoke_checks_what_windows_checks(self):
        with open(os.path.join(_root(), "runner", "tools",
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
            _root(), "runner", "tools", "smoke_posix_binaries.sh"), os.X_OK),
            "smoke script is not executable")


class MutationGateTest(unittest.TestCase):
    """Mutation is a non-gating signal, off the release path
    (owner's call, 2026-10-22).

    It is continue-on-error and runs only on manual dispatch (plus
    the scheduled mutation-seeded.yml), so no publish waits on it.
    It used to ride version tags, which is what made releases ~40
    minutes; the move is finding 4 of
    docs/reports/v3.12.56/ci-failures.md.
    """

    def test_mutation_runs_only_on_manual_dispatch(self):
        # Off the release critical path (2026-10-22): mutation is a
        # non-gating signal, so it runs only on manual dispatch (and
        # the scheduled mutation-seeded.yml), never on a tag or push.
        # That is the whole difference between a ~7-min and a ~40-min
        # release. docs/reports/v3.12.56/ci-failures.md, finding 4.
        block = _job_block(_workflow(), "mutation")
        self.assertIn("if: github.event_name == 'workflow_dispatch'", block)
        self.assertNotIn("refs/tags", block)

    def test_the_gate_jobs_stay_ungated(self):
        # The jobs that gate everything else must run on every push;
        # a stray tag-only condition on one of them would silently
        # stop branch CI from meaning anything.
        workflow = _workflow()
        for job in ("test", "typecheck", "build-linux", "build-linux-arm64",
                    "build-macos", "build-macos-x86_64", "build-windows",
                    "build-windows-arm64", "build-python", "build-pi-light"):
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

    def test_mutation_needs_no_timer_off_the_release_path(self):
        # Mutation no longer rides a tag run, so a slow mutmut can
        # only stretch a manual dispatch, never a publish; it carries
        # no job timer. The timers that came back live on the scarce
        # build runners instead (next test).
        block = _job_block(_workflow(), "mutation")
        self.assertNotIn("timeout-minutes", _uncommented(block))

    def test_a_running_build_is_never_cancelled_by_the_next_push(self):
        # Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c. With
        # cancel-in-progress on branch pushes, a push every five
        # minutes against a seven-minute build meant no main commit
        # ever finished building (six cancelled in a row on
        # 2026-10-23), so nothing could be green and cut-release
        # could never run. The group still serializes builds per
        # ref; the running one finishes and the newest push waits.
        workflow = _workflow()
        m = re.search(r"^concurrency:\n((?:  .*\n)+)", workflow, re.M)
        self.assertIsNotNone(m, "build.yml has no concurrency block")
        block = _uncommented(m.group(1))
        self.assertIn("group: build-${{ github.ref }}", block)
        self.assertIn("cancel-in-progress: false", block)

    def test_only_scarce_runners_carry_a_timer(self):
        # The measurement experiment is over. The one timer the
        # report argued for is back, and only there: the two
        # scarce-runner build jobs whose runner label GitHub can
        # retire (macos-15-intel, windows-11-arm). A retired label
        # parked release runs ~16 h (finding 3); 30 minutes fails
        # them fast instead. No other job -- in build.yml or any
        # other workflow -- carries one.
        workflow = _workflow()
        for job in ("build-macos-x86_64", "build-windows-arm64"):
            block = _uncommented(_job_block(workflow, job))
            self.assertIn("timeout-minutes: 30", block,
                          "%s should carry the scarce-runner timer" % job)
        # Exactly those two, nowhere else in build.yml.
        self.assertEqual(_uncommented(workflow).count("timeout-minutes"), 2,
                         "only the two scarce runners may carry a timer")
        # And no other workflow file carries one at all.
        folder = os.path.join(_root(), ".github", "workflows")
        names = sorted(n for n in os.listdir(folder)
                       if n.endswith((".yml", ".yaml")))
        self.assertGreaterEqual(len(names), 5, names)
        for name in names:
            if name == "build.yml":
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                self.assertNotIn("timeout-minutes", _uncommented(fh.read()),
                                 "%s carries a job timer" % name)

    def test_both_suites_run_under_a_wall_clock_that_names_the_test(self):
        # Not a timer. 2026-10-23: a test that looped forever held
        # the Linux suite and the Windows shards past 80 minutes,
        # the job had no clock, and the stuck test's name was the
        # unfinished line at the end of a log nobody could read
        # from the diagnosing seat. runner/tools/suite_wall_clock.py is
        # `python -m unittest` with a 20-minute deadline that names
        # the running test and annotates it; the Windows shards get
        # the same through --wall-clock. The workflow's timer count
        # (the scarce-runner pin above) is unchanged by this.
        # (Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c)
        workflow = _workflow()
        linux = _uncommented(_job_block(workflow, "test"))
        self.assertIn("python runner/tools/suite_wall_clock.py --minutes 20 -- "
                      "discover -s runner/tests -t . -v --durations 25", linux)
        self.assertNotIn("python -m unittest discover", linux)
        windows = _uncommented(_job_block(workflow, "build-windows"))
        self.assertIn("python runner/tools/run_tests_parallel.py --jobs 4 "
                      "--durations 15 --wall-clock 20", windows)
        self.assertTrue(os.path.exists(
            os.path.join(_root(), "runner", "tools", "suite_wall_clock.py")))

    def test_real_gates_are_not_continue_on_error(self):
        # The mirror image of the pin above: if a job that gates
        # the release ever grows continue-on-error, a red suite
        # would publish. Only the signal job may carry it.
        workflow = _workflow()
        for job in ("test", "typecheck", "build-linux", "build-linux-arm64",
                    "build-macos", "build-macos-x86_64", "build-windows",
                    "build-windows-arm64", "build-python", "build-pi-light",
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
    names no profile (pinned in runner/tests/test_pi_light.py). These
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
            self.assertIn("the install archives",
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
                         "PROTOCOL.md"):
            self.assertIn(expected, copied)

    def test_the_ci_pin_file_is_copied(self):
        # PipelineLiftsTest reads .github/requirements-ci.txt from the
        # tree; without a copy the v3.8.5 tag build's mutation job died
        # in baseline stats collection on exactly that missing file.
        # The .github/ entry carries it.
        self.assertIn(".github/", _also_copy())
        self.assertTrue(os.path.isfile(os.path.join(
            _root(), ".github", "requirements-ci.txt")))

    def test_the_sharded_runner_is_copied(self):
        # test_parallel_runner imports runner/tools/run_tests_parallel.py
        # at load time. A missing copy fails stats collection before any
        # mutant. The .github/ entry carries it.
        self.assertIn(".github/", _also_copy())
        self.assertTrue(os.path.isfile(os.path.join(
            _root(), "runner", "tools", "run_tests_parallel.py")))

    def test_also_copy_never_nests(self):
        # mutmut copies each entry in turn. An entry inside another
        # entry ("runner/tools/" beside ".github/") is a second copy
        # over the first, and source_paths (runner/) is copied anyway.
        entries = [e.rstrip("/") for e in _also_copy()] + ["runner"]
        for a in entries:
            for b in entries:
                if a != b:
                    self.assertFalse(b.startswith(a + "/"),
                                     "%s is inside %s" % (b, a))

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
        name, os.path.join(_root(), "runner", "tools", name + ".py"))
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
                 "minimal-userland.yml", "platform-matrix.yml")

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
                    "build-windows-arm64", "build-linux", "build-linux-arm64",
                    "build-pi-light", "build-macos", "build-macos-x86_64",
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

    def test_codeql_ignores_tests_and_extensions_only(self):
        workflow = self._wf("security.yml")
        self.assertIn("config-file: ./.github/codeql/codeql-config.yml",
                      workflow)
        self.assertNotIn("queries:", workflow)
        with open(os.path.join(_root(), ".github", "codeql",
                               "codeql-config.yml"),
                  encoding="utf-8") as fh:
            config = fh.read()
        self.assertIn("- runner/tests/**", config)
        self.assertIn("- extensions/**", config)
        self.assertIn("py/clear-text-logging-sensitive-data", config)
        self.assertIn("py/polynomial-redos", config)
        self.assertIn("py/bind-socket-all-network-interfaces", config)
        self.assertNotIn("py/sql-injection", config)

    # Lift 6: CI installs resolve through the one pin file.
    def test_ci_installs_come_from_the_pin_file(self):
        for line in _workflow().splitlines():
            if "pip install" in line:
                self.assertIn("-c .github/requirements-ci.txt", line,
                              "unconstrained install: %s" % line)
        with open(os.path.join(_root(), ".github/requirements-ci.txt"),
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
                            ("build-windows-arm64", "Compress-Archive"),
                            ("build-linux", "tar czf"),
                            ("build-linux-arm64", "tar czf"),
                            ("build-pi-light", "tar czf"),
                            ("build-macos", "tar czf"),
                            ("build-macos-x86_64", "tar czf")):
            block = _job_block(workflow, job)
            stamp = "runner/tools/stamp_provenance.py --job %s" % job
            self.assertIn(stamp, block, "%s never stamps" % job)
            self.assertLess(block.index(stamp), block.index(packer),
                            "%s stamps after archiving" % job)
        self.assertIn("runner/tools/stamp_provenance.py --job build-python",
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
        self.assertIn("runner/tools/make_sbom.py "
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
        for top in ("runner",):
            base = os.path.join(_root(), top)
            for dirpath, _dirs, names in os.walk(base):
                # runner/tests/ and runner/tools/ are the suite and the
                # CI scripts, not shipped modules.
                if os.path.relpath(dirpath, base).split(os.sep)[0] in (
                        "tests tools".split()):
                    continue
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


class NoPythonDropTest(unittest.TestCase):
    """A machine you own that does not have Python.

    The common one is a Windows PC. The frozen binary is the
    interpreter. The Linux proof is the same binary started in
    Debian bookworm slim, which has no python3 package. If that
    image grows a Python, the script fails closed.
    """

    def test_linux_job_drops_onto_a_machine_with_no_python(self):
        block = _job_block(_workflow(), "build-linux")
        self.assertIn(
            "runner/tools/smoke_no_python.sh ./dist/homing-pigeon", block)
        with open(os.path.join(_root(), "runner", "tools", "smoke_no_python.sh"),
                  encoding="utf-8") as fh:
            script = fh.read()
        for needle in ("debian:bookworm-slim", "command -v python3",
                       "--version", "no-python drop ok",
                       "has Python"):
            self.assertIn(needle, script, "no-python smoke lacks %s" % needle)
        self.assertTrue(os.access(os.path.join(
            _root(), "runner", "tools", "smoke_no_python.sh"), os.X_OK),
            "no-python smoke is not executable")

    def test_windows_job_runs_with_python_off_the_path(self):
        for job in ("build-windows", "build-windows-arm64"):
            block = _job_block(_workflow(), job)
            self.assertIn("no python on the machine", block, job)
            self.assertIn("SystemRoot\\System32", block, job)
            self.assertIn("python is still on PATH", block, job)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
def _workflow_text(name):
    with open(os.path.join(_root(), ".github", "workflows", name),
              encoding="utf-8") as fh:
        return fh.read()


def _legs():
    """The platform corpus: {job: [leg, ...]} from platform-legs.json."""
    import json
    with open(os.path.join(_root(), ".github", "platform-legs.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _matrix_leg_names(_name=None):
    return [e["name"] for entries in _legs().values() for e in entries]


class PipelineLessonsTest(unittest.TestCase):
    """What 2026-10-21 taught, pinned so it cannot un-learn itself.

    Each test here is a bug the pipeline actually had that day, or a
    way a proof silently stopped being one. They are cheap and they
    read the workflows as text, like the rest of this file."""

    ALL = ("build.yml", "docker.yml", "security.yml",
           "minimal-userland.yml", "platform-matrix.yml",
           "mutation-seeded.yml")

    def test_unittest_output_piped_to_tee_captures_stderr(self):
        # unittest writes its report to stderr. 8dc7ac7 piped
        # `docker run | tee` (stdout only) and then grepped the
        # file for `Ran N tests` / `OK`: the file was empty and both
        # minimal-userland legs were red for four commits.
        for name in self.ALL:
            for line in _workflow_text(name).splitlines():
                if "| tee" in line and ("unittest" in line
                                        or "docker run" in line):
                    self.assertIn("2>&1", line,
                                  "%s pipes a test report to tee "
                                  "without 2>&1: %s" % (name, line.strip()))

    def test_every_portable_proof_demands_a_full_ok(self):
        # A skipped proof is green from the outside. Wherever the
        # portable proof runs, the verdict step must forbid skips and
        # require a bare OK. Containers and VMs get it from the script;
        # the native job spells it out.
        with open(os.path.join(_root(), "runner", "tools", "platform_proof.sh"),
                  encoding="utf-8") as fh:
            script = fh.read()
        self.assertIn("skip_guard.py", script)
        self.assertIn("--no-skips --require-ok", script)
        wf = _workflow_text("platform-matrix.yml")
        self.assertIn("runner/tools/skip_guard.py proof.log --no-skips --require-ok", wf)
        self.assertIn("runner/tools/platform_proof.sh", wf)
        # and the proof module refuses to be a platform-conditional
        with open(os.path.join(_root(), "runner", "tests", "test_platform_proof.py"),
                  encoding="utf-8") as fh:
            proof = fh.read()
        self.assertEqual(proof.count("skipUnless"), 1,
                         "the portable proof may gate on HP_PLATFORM_PROOF "
                         "only; no per-platform skips")
        self.assertNotIn("skipIf", proof)

    def test_readme_lists_every_matrix_leg(self):
        # Claims track proof: every leg name in the matrix appears in
        # the README's Proven platforms table, and nothing in that
        # table is a leg the matrix does not run.
        legs = _matrix_leg_names("platform-matrix.yml")
        self.assertGreaterEqual(len(legs), 40, legs)
        self.assertEqual(len(legs), len(set(legs)), "duplicate leg names")
        with open(os.path.join(_root(), "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn("## Proven platforms", readme)
        table = readme.split("## Proven platforms", 1)[1].split("\n## ", 1)[0]
        for leg in legs:
            self.assertIn("`%s`" % leg, table,
                          "README Proven platforms lacks leg %s" % leg)
        listed = set(re.findall(r"`([A-Za-z0-9._-]+)`", table))
        extra = {x for x in listed if ("-x86_64" in x or "-arm64" in x
                                        or "-qemu" in x or x.startswith(
                                            ("fatfinger-", "native-", "vm-")))
                 } - set(legs)
        self.assertEqual(extra, set(),
                         "README lists legs the matrix does not run")

    def test_matrix_core_tier_is_small_and_runs_on_push(self):
        # Core must stay cheap enough to run on every push; the whole
        # corpus is for the nightly and the dispatch.
        wf = _workflow_text("platform-matrix.yml")
        legs = _legs()
        core = sum(1 for es in legs.values() for e in es
                   if e.get("tier") == "core")
        self.assertGreaterEqual(core, 8)
        self.assertLessEqual(core, 14, "core tier is growing; move legs to full")
        for es in legs.values():
            for e in es:
                self.assertIn(e.get("tier"), ("core", "full"), e)
        self.assertIn("schedule:", wf)
        self.assertIn("workflow_dispatch:", wf)
        # a job-level `if:` cannot read the matrix context (the first
        # push of this workflow died at validation on exactly that);
        # the plan job filters and the matrices come from fromJSON.
        self.assertNotIn("matrix.tier", wf)
        for job in ("container", "native", "vm"):
            self.assertIn("fromJSON(needs.plan.outputs.%s)" % job, wf)
            self.assertIn("needs.plan.outputs.%s_count != '0'" % job, wf)
        # and the plan itself: the full corpus is the schedule and
        # a manual dispatch. A push runs core legs on plentiful
        # runners only.
        with open(os.path.join(_root(), "runner", "tools", "platform_plan.py"),
                  encoding="utf-8") as fh:
            plan = fh.read()
        self.assertIn('("schedule", "workflow_dispatch")', plan)

    def test_a_push_does_not_queue_a_scarce_runner(self):
        # Measured 2026-10-22: every push started a matrix leg on
        # macos-13, which GitHub retired, so the workflow sat in
        # the queue and never finished. The same push also asked
        # for Windows and ARM runners the binary build was already
        # using. Those legs stay in the corpus. They run nightly.
        import importlib.util
        path = os.path.join(_root(), "runner", "tools", "platform_plan.py")
        spec = importlib.util.spec_from_file_location(
            "platform_plan", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        legs = _legs()
        push = mod.choose(legs, "push")
        names = [e["name"] for es in push.values() for e in es]
        self.assertIn("native-ubuntu-x86_64", names)
        self.assertIn("alpine-3-x86_64", names)
        self.assertIn("python-3.9-floor-x86_64", names)
        self.assertNotIn("native-macos-x86_64", names)
        self.assertNotIn("native-windows-arm64", names)
        self.assertNotIn("debian-13-arm64", names)
        for maker in ("debian-12-arm64-qemu", "ubuntu-22.04-arm64-qemu",
                      "alpine-3-armv7-qemu", "ros-humble-arm64-qemu",
                      "ros-jazzy-arm64-qemu"):
            self.assertNotIn(maker, names)
        for es in push.values():
            for entry in es:
                self.assertFalse(mod.is_scarce(entry), entry["name"])
        nightly = mod.choose(legs, "schedule")
        nightly_names = [e["name"] for es in nightly.values() for e in es]
        for maker in ("debian-12-arm64-qemu", "ubuntu-22.04-arm64-qemu",
                      "alpine-3-armv7-qemu", "ros-humble-arm64-qemu",
                      "ros-jazzy-arm64-qemu"):
            self.assertIn(maker, nightly_names)
        mac = [e for e in nightly["native"]
               if e["name"] == "native-macos-x86_64"]
        self.assertEqual(len(mac), 1)
        self.assertEqual(mac[0]["runner"], "macos-15-intel")
        self.assertGreater(
            sum(len(v) for v in nightly.values()),
            sum(len(v) for v in push.values()))
        with open(os.path.join(_root(), ".github", "platform-legs.json"),
                  encoding="utf-8") as fh:
            self.assertNotIn("macos-13", fh.read())

    def test_continue_on_error_only_where_documented(self):
        # continue-on-error reports the step as `success` in the API
        # even when the command failed. The bwrap diagnosis on PR #87
        # read "EnforceTest alone: passes" off exactly that. The one
        # allowed use is build.yml's release-only mutation job, whose
        # comment explains it is a signal, not a gate. Anywhere else
        # it hides a failure.
        for name in self.ALL:
            lines = [ln for ln in _workflow_text(name).splitlines()
                     if "continue-on-error" in ln
                     and not ln.strip().startswith("#")]
            if name == "build.yml":
                self.assertEqual(len(lines), 1, lines)
                block = _job_block(_workflow(), "mutation")
                self.assertIn("continue-on-error: true", block)
            else:
                self.assertEqual(lines, [], "%s uses continue-on-error" % name)

    def test_no_test_count_census_in_workflows(self):
        # `grep -q 'Ran 6 tests'` and `assertEqual(count, 1)` both
        # broke on 2026-10-21 the moment someone added a test or a
        # build. A verdict step asks for N > 0, a bare OK and no skip
        # (runner/tools/skip_guard.py --require-ok --no-skips), never a number.
        for name in self.ALL:
            for line in _workflow_text(name).splitlines():
                if line.strip().startswith("#"):
                    continue
                self.assertNotRegex(line, r"Ran \d+ tests?",
                                    "%s hardcodes a test count: %s"
                                    % (name, line.strip()))

    def test_verdict_steps_use_the_guard(self):
        # Wherever a workflow tees a test run into a file, the file is
        # read by the guard, not by ad-hoc greps.
        for name in ("minimal-userland.yml", "platform-matrix.yml", "build.yml"):
            wf = _workflow_text(name)
            if "| tee" in wf:
                self.assertIn("runner/tools/skip_guard.py", wf, name)


class PythonFloorTest(unittest.TestCase):
    """pyproject says requires-python >= 3.9. The platform matrix put
    the runner on Rocky 9 and python:3.9 for the first time and it
    could not import: `to: str | None` in a signature is evaluated at
    definition time before 3.10. The matrix leg proves the floor for
    real; this test keeps the one known way of breaking it out of the
    tree between runs."""

    def _pep604_runtime_sites(self, path):
        import ast
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        future = any(
            isinstance(n, ast.ImportFrom) and n.module == "__future__"
            and any(a.name == "annotations" for a in n.names)
            for n in tree.body)
        if future:
            return []

        def bitor(node):
            return node is not None and any(
                isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr)
                for x in ast.walk(node))

        sites = []
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = n.args
                anns = [x.annotation for x in
                        a.posonlyargs + a.args + a.kwonlyargs]
                anns += [n.returns,
                         a.vararg.annotation if a.vararg else None,
                         a.kwarg.annotation if a.kwarg else None]
                if any(bitor(x) for x in anns):
                    sites.append("%s:%d %s" % (path, n.lineno, n.name))
            elif isinstance(n, ast.AnnAssign) and bitor(n.annotation):
                sites.append("%s:%d" % (path, n.lineno))
        return sites

    def test_no_runtime_pep604_annotations_without_future_import(self):
        import glob
        # Shipped modules only: runner/tests/ is the suite.
        tests_dir = os.path.join(_root(), "runner", "tests") + os.sep
        files = sorted(f for f in glob.glob(
            os.path.join(_root(), "runner", "**", "*.py"), recursive=True)
            if not f.startswith(tests_dir))
        files += sorted(glob.glob(os.path.join(_root(), "runner", "tools", "*.py")))
        self.assertGreater(len(files), 30)
        sites = []
        for f in files:
            sites += self._pep604_runtime_sites(f)
        self.assertEqual(sites, [],
                         "PEP 604 annotation evaluated at definition time "
                         "breaks import on the 3.9 floor; add "
                         "`from __future__ import annotations`")

    def test_the_floor_is_claimed_and_proven(self):
        with open(os.path.join(_root(), "pyproject.toml"),
                  encoding="utf-8") as fh:
            self.assertIn('requires-python = ">=3.9"', fh.read())
        self.assertIn("python-3.9-floor-x86_64", _matrix_leg_names())
