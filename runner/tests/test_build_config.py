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
import sys
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _dynamic_runner_modules():
    with open(os.path.join(_root(), "runner", "runner.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(
        r'_load_(?:mod|attr)\(\s*"runner\.([A-Za-z0-9_.]+)"', src))


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
    docs/steady/reports/ci-failures.md.
    """

    def test_mutation_runs_only_on_non_tag_dispatch(self):
        # cut-release starts the release with `gh workflow run
        # build.yml --ref <tag>`, a workflow_dispatch on a tag ref, so
        # gating on workflow_dispatch alone put mutation back on the
        # release (v3.12.68 ran it). It must gate on dispatch AND a
        # non-tag ref, so the release dispatch skips it.
        block = _job_block(_workflow(), "mutation")
        self.assertIn(
            "if: github.event_name == 'workflow_dispatch' "
            "&& !startsWith(github.ref, 'refs/tags/v')", block)
        # The tag reference it names is the one it excludes, so the
        # release dispatch (on refs/tags/v*) skips mutation while a
        # manual branch dispatch still runs it.
        self.assertIn("!startsWith(github.ref, 'refs/tags/v')", block)

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

    def test_rolling_builds_cancel_release_and_tag_never_do(self):
        # The posture since the relief window of 2026-11-12, kept at
        # its close (owner, 2026-11-12): the pin this replaced --
        # cancel-in-progress: false, a running build never
        # cancelled -- held from 2026-10-23, when a push every five
        # minutes against a seven-minute build meant no main commit
        # ever finished building. The four-day review's root cause
        # 5 is the same starvation from the other side: at the
        # window's landing rate the no-cancel queue starved the
        # verdicts the train gates on, and the window measured 77
        # per cent of finished builds green against none before.
        # A superseded ROLLING build cancels; a release commit (its
        # own group) and a tag build never do -- the expression is
        # false for both.
        workflow = _workflow()
        m = re.search(r"^concurrency:\n((?:  .*\n)+)", workflow, re.M)
        self.assertIsNotNone(m, "build.yml has no concurrency block")
        block = _uncommented(m.group(1))
        self.assertIn("group: build-${{ github.ref }}", block)
        self.assertIn("cancel-in-progress: ${{", block)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", block)
        self.assertIn("startsWith(github.event.head_commit.message, "
                      "'release:')", block)
        self.assertNotIn("cancel-in-progress: false", block)
        # Only the rolling group cancels: the docs group is named by
        # the head commit's message, and a push whose head is a desk
        # note can carry code beneath it, whose suites the next desk
        # note or web edit used to cancel (the builds of 0b59937c
        # and 644358bc on 2026-11-13). The cancelling rule excludes
        # exactly the head messages the group sends to 'docs'.
        group = [ln for ln in block.splitlines() if ln.strip().startswith("group:")][0]
        cancel = [ln for ln in block.splitlines() if ln.strip().startswith("cancel-in-progress:")][0]
        m = re.search(r"\|\| \((\(startsWith\(github\.event\.head_commit\.message, 'desk:'\).*'\.md'\)\)\)) && 'docs' \|\| 'rolling'\)", group)
        self.assertIsNotNone(m, "the group's docs condition")
        self.assertTrue(cancel.strip().startswith("cancel-in-progress: ${{ !(startsWith(github.ref, 'refs/tags/v') || "
                                                  "startsWith(github.event.head_commit.message, 'release:') || "), cancel)
        self.assertIn("|| " + m.group(1) + ") }}", cancel)

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
        # `python -m unittest` with a deadline that names the
        # running test and annotates it; the Windows shards get
        # the same through --wall-clock. The workflow's timer count
        # (the scarce-runner pin above) is unchanged by this. The
        # Linux deadline is 30 minutes since 3.15.111: the suite
        # outgrew 20 (the shotgun families took the identical
        # discover run to about 23 minutes, the size python-range
        # already budgets 30 for), and the pin moves with the
        # workflow in the same change, as a moved reader's
        # registry row does -- the gate is that the clock is
        # there and names the test, not the number it started at.
        # (Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c)
        # Since 2026-11-11 the Linux suite runs its shards through
        # the same parallel runner as the other two legs, with the
        # 30-minute clock per shard (--wall-clock runs each shard
        # under suite_wall_clock.py) and --full-log for the -v log
        # the skip guard and the release snapshot read.
        workflow = _workflow()
        linux = _uncommented(_job_block(workflow, "test"))
        self.assertIn("python runner/tools/run_tests_parallel.py --jobs 8 "
                      "--wall-clock 30 --durations 25 "
                      "--full-log test-output.log "
                      "--split runner/tools/split_modules.json", linux)
        self.assertNotIn("python -m unittest discover", linux)
        self.assertIn("skip_guard.py test-output.log", linux)
        # The macOS leg keeps its -v log too (a walled shard
        # names its test there), uploaded under its own name so
        # the release snapshot's merged download keeps the
        # Linux log at test-output.log.
        macos = _uncommented(_job_block(workflow, "test-macos"))
        self.assertIn("python runner/tools/run_tests_parallel.py --jobs 3 "
                      "--durations 15 --wall-clock 20 "
                      "--full-log test-output-macos.log "
                      "--split runner/tools/split_modules.json", macos)
        self.assertIn("name: ci-test-log-macos", macos)
        self.assertIn("path: test-output-macos.log", macos)
        # The Windows suite runs in its own job since 2026-11-12
        # (it ran as the first step of build-windows before, and
        # the release waited its 12.7 minutes on both sides of the
        # tag for an advisory verdict); the artifact leg no longer
        # runs it.
        # Two parts on two runners since 2026-11-12: every second
        # shard of the one packing each, under the packing's shard
        # numbers (one box ran all 28 at once and ended them
        # together 20 per cent under the wall).
        windows = _uncommented(_job_block(workflow, "test-windows"))
        self.assertIn("python runner/tools/run_tests_parallel.py "
                      "--duration-table "
                      "runner/tools/windows_durations.json "
                      "--durations 15 --wall-clock 20 "
                      "--full-log test-output-windows-${{ matrix.part }}.log "
                      "--split runner/tools/split_modules.json "
                      "--part ${{ matrix.part }}/2", windows)
        self.assertIn("part: [1, 2]", windows)
        self.assertIn("fail-fast: false", windows)
        # the split list every leg reads: a module whose tests cost
        # more than a shard can carry rides as its classes
        self.assertTrue(os.path.exists(
            os.path.join(_root(), "runner", "tools", "split_modules.json")))
        self.assertIn("name: ci-test-log-windows-${{ matrix.part }}", windows)
        self.assertIn("path: test-output-windows-${{ matrix.part }}.log", windows)
        self.assertNotIn("run_tests_parallel.py",
                         _uncommented(_job_block(workflow, "build-windows")))
        self.assertTrue(os.path.exists(
            os.path.join(_root(), "runner", "tools", "suite_wall_clock.py")))

    def test_real_gates_are_not_continue_on_error(self):
        # The mirror image of the pin above: if a job that gates
        # the release ever grows continue-on-error, a red suite
        # would publish. Only the signal job may carry it.
        # The three suite jobs (`test`, `test-macos`, `test-windows`)
        # were advisory for the relief window of 2026-11-12 and are
        # back in this list since its close; the artifact legs
        # (build-windows among them, since the suite left it on
        # 2026-11-12), typecheck and the publish chain were real
        # gates throughout.
        workflow = _workflow()
        for job in ("typecheck", "build-linux", "build-linux-arm64",
                    "build-macos", "build-macos-x86_64", "build-windows",
                    "build-windows-arm64", "build-python", "build-pi-light",
                    "test", "test-macos", "test-windows",
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
                 "minimal-userland.yml", "platform-matrix.yml",
                 "env-axes.yml", "coverage.yml", "switch-proofs.yml",
                 "freebsd.yml", "python-range.yml", "upgrade-proof.yml", "soak.yml", "queues-worker.yml",
                 "hardware.yml", "cut-release.yml", "job-user.yml",
                 "mutation-seeded.yml", "upstream-pins.yml",
                 "stamp-audit.yml")

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
        for job in ("test", "typecheck", "mutation", "test-macos",
                    "test-windows", "build-windows",
                    "build-windows-arm64", "build-linux", "build-linux-arm64",
                    "build-pi-light", "build-macos", "build-macos-x86_64",
                    "build-python"):
            self.assertEqual(read_only,
                             _perm_entries(_job_block(workflow, job)),
                             "%s grants more than checkout" % job)
        # actions: read on the two jobs that download artifacts:
        # a promoted tag build reads the gate build's run (since
        # 2026-11-12), which the default token cannot do without it.
        self.assertEqual(
            {("contents", "write"), ("id-token", "write"),
             ("attestations", "write"), ("actions", "read")},
            _perm_entries(_job_block(workflow, "release")))
        self.assertEqual({("id-token", "write"), ("actions", "read")},
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

    def test_the_briefing_whole_sweep_rides_the_nightly_soak(self):
        # The desk's Q166 answer (2026-11-12): the briefing
        # guard's whole bookended sweep runs nightly on the
        # soak workflow's own schedule, under the whole-sweep
        # switch, and the per-push test-heavy leg is retired --
        # the module rides the ordinary suites again, sampled.
        soak = self._wf("soak.yml")
        self.assertIn("schedule:", soak)
        block = _job_block(soak, "briefing-whole-sweep")
        self.assertIn('HP_BOOKENDED_WHOLE: "1"', block)
        self.assertIn("Q165PolarityGuardTest", block)
        self.assertIn("Q166SampleTest", block)
        self.assertEqual({("contents", "read")},
                         _perm_entries(block))
        self.assertNotIn("test-heavy", _uncommented(_workflow()))
        import json
        with open(os.path.join(
                _root(), "runner", "tools",
                "split_modules.json"), encoding="utf-8") as fh:
            split = json.load(fh)
        self.assertEqual([], split["own_job"])
        self.assertIn("runner.tests.test_briefing_contradiction",
                      split["modules"])

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
        self.assertIn("- runner/extensions/**", config)
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
        from runner.tests._compat import project_version
        self.assertEqual(got["version"], project_version())

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

    # make_sbom is a release tool and reads pyproject with tomllib;
    # it runs on the build Python, never on a runner box.
    @unittest.skipIf(sys.version_info < (3, 11),
                     "make_sbom runs on the build Python (tomllib, 3.11+)")
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
                        "tests tools extensions".split()):
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
        with open(os.path.join(_root(), "docs", "steady", "verification.md"),
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
           "mutation-seeded.yml", "python-range.yml", "upgrade-proof.yml",
           "soak.yml", "coverage.yml",
           "cut-release.yml", "env-axes.yml", "freebsd.yml", "hardware.yml",
           "job-user.yml", "queues-worker.yml", "switch-proofs.yml",
           "upstream-pins.yml", "stamp-audit.yml")

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

    def test_the_platform_fan_out_is_capped(self):
        # The nine container legs and the native legs start a few
        # at a time since 2026-11-12: all at once, with the other
        # proof workflows a release tag starts, they held the
        # account's job concurrency and queued the next cycle's
        # gate legs for minutes. The proofs run after the mirrors;
        # a slower fan-out costs the release nothing.
        wf = _workflow_text("platform-matrix.yml")
        container = wf.split("\n  container:\n", 1)[1].split("\n  native:\n", 1)[0]
        native = wf.split("\n  native:\n", 1)[1].split("\n  vm:\n", 1)[0]
        self.assertIn("max-parallel: 3", _uncommented(container))
        self.assertIn("max-parallel: 2", _uncommented(native))

    def test_platform_proof_finds_a_versioned_bsd_python(self):
        # vm-netbsd-10 failed every nightly from 2026-10-24: the
        # workflow's prepare step installs python312 (python3.12, no
        # python3), the script saw no python3 and ran OpenBSD's
        # `pkg_add -I python%3`, which NetBSD refuses. The script must
        # link a versioned python3.X it can already see before it
        # installs anything, and NetBSD's pkg_add must ask for python312.
        import shutil
        import subprocess
        import tempfile
        path = os.path.join(_root(), "runner", "tools", "platform_proof.sh")
        with open(path, encoding="utf-8") as fh:
            script = fh.read()
        self.assertIn('[ "$(uname -s)" = NetBSD ]; then pkg_add -I python312', script)
        start = script.index('STAGE="install python3"')
        end = script.index("# ---- 1b.")
        stage = script[start:end]
        self.assertLess(stage.index("_link_versioned_python3\nif ! command -v python3"),
                        stage.index('say "installing python3"'))
        sh = shutil.which("sh")
        if sh is None or os.name == "nt":
            return  # the static checks above are the Windows half
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "fakebin")
            link = os.path.join(tmp, "link")
            os.mkdir(fake)
            log = os.path.join(tmp, "pkg_add.log")
            def tool(name, body):
                p = os.path.join(fake, name)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write("#!/bin/sh\n" + body + "\n")
                os.chmod(p, 0o755)
            tool("python3.12", "exit 0")
            tool("pkg_add", 'echo "$*" >> %s; exit 1' % log)
            tool("uname", "echo NetBSD")
            # a PATH with no python3 anywhere: only the fakes and the
            # handful of tools the stage itself needs
            sysbin = os.path.join(tmp, "sysbin")
            os.mkdir(sysbin)
            for t in ("mkdir", "ln"):
                os.symlink(shutil.which(t), os.path.join(sysbin, t))
            env = {"PATH": os.pathsep.join([link, fake, sysbin]),
                   "HP_PYBIN": link}
            body = "set -eu\nsay() { :; }\n" + stage + "\ncommand -v python3\n"
            r = subprocess.run([sh, "-c", body], env=env,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), os.path.join(link, "python3"))
            self.assertFalse(os.path.exists(log),
                             "pkg_add ran although python3.12 was on PATH")

    def test_readme_lists_every_matrix_leg(self):
        # Claims track proof: every leg name in the matrix appears in
        # docs/steady/use/platforms.md's Proven platforms table, and nothing in that
        # table is a leg the matrix does not run.
        legs = _matrix_leg_names("platform-matrix.yml")
        self.assertGreaterEqual(len(legs), 40, legs)
        self.assertEqual(len(legs), len(set(legs)), "duplicate leg names")
        with open(os.path.join(_root(), "docs", "steady", "use", "platforms.md"),
                  encoding="utf-8") as fh:
            table = fh.read()
        self.assertIn("# Proven platforms", table)
        for leg in legs:
            self.assertIn("`%s`" % leg, table,
                          "docs/steady/use/platforms.md lacks leg %s" % leg)
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
        # read "EnforceTest alone: passes" off exactly that. The
        # allowed use is build.yml's release-only mutation job,
        # whose comment explains it is a signal, not a gate. (The
        # three suite surfaces carried it for the relief window of
        # 2026-11-12 and dropped it at the window's close.)
        # Anywhere else it hides a failure.
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
        for name in ("minimal-userland.yml", "platform-matrix.yml", "build.yml",
                     "python-range.yml", "hardware.yml"):
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


class PipelinePostureTest(unittest.TestCase):
    """The pipeline's posture since the relief window of 2026-11-12
    closed (owner, 2026-11-12; the window's suppositions, its
    numbers and the accepted risk are recorded in
    docs/steady/reports/ci-failures.md).

    What the window measured and the posture keeps: the nine proof
    workflows beside build.yml do not fire on pushes to main (a
    release tag whose tree changed under runner/, a nightly and a
    dispatch run them); a superseded rolling build cancels (release
    and tag builds never do). What the window suspended and the
    close restored: the suites are real jobs again (no
    continue-on-error), the Linux suite and both parts of the
    Windows suite gate a release that carries core code by the cut
    gate's rule (runner/tools/cut_gate.py: the legs alone for a
    release of docs, tests or a corpus), the release job waits for
    them on a full tag build, and the hourly seeded mutation walk
    is back on its schedule. No workflow carries a RELIEF-48H
    marker any more: the window's forcing test is gone with it.
    """

    PROOF_WORKFLOWS = ("platform-matrix.yml", "python-range.yml",
                       "switch-proofs.yml", "minimal-userland.yml",
                       "env-axes.yml", "job-user.yml",
                       "queues-worker.yml", "upgrade-proof.yml",
                       "freebsd.yml")
    TOUCHED_FILES = PROOF_WORKFLOWS + ("build.yml", "cut-release.yml",
                                       "mutation-seeded.yml")

    def test_no_workflow_carries_a_relief_marker(self):
        for name in self.TOUCHED_FILES:
            self.assertNotIn("RELIEF-48H expires", _workflow_text(name),
                             "%s still carries the window's marker" % name)

    def test_the_mutation_walk_is_hourly_again(self):
        wf = _workflow_text("mutation-seeded.yml")
        live = "\n".join(line for line in wf.splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn('- cron: "17 * * * *"', live)

    def test_proof_workflows_do_not_fire_on_pushes_to_main(self):
        for name in self.PROOF_WORKFLOWS:
            wf = _workflow_text(name)
            live = "\n".join(
                line for line in wf.splitlines()
                if not line.lstrip().startswith("#"))
            self.assertNotIn("branches: [main]", live,
                             "%s still fires on pushes to main" % name)
            # no push trigger at all since the cut pushes tags with
            # RELEASE_TOKEN (2026-11-12): the tag build dispatches
            # the proofs when the tag's tree changed under runner/
            self.assertNotIn("\n  push:", live,
                             "%s fires on a push of its own" % name)
            self.assertNotIn('tags: ["v*"]', live,
                             "%s fires on every release tag" % name)
            self.assertIn("schedule:", wf,
                          "%s lost its nightly" % name)
            self.assertIn("workflow_dispatch:", wf,
                          "%s lost manual dispatch" % name)

    def test_the_tag_build_dispatches_every_proof_workflow_after_the_mirrors(self):
        # A tag cut-release places with GITHUB_TOKEN fires no
        # push-triggered run (GitHub's rule against workflows
        # triggering workflows): v3.16.20.10 and v3.16.21.2 ran
        # build.yml and docker.yml alone, both dispatched by name,
        # while the hand-placed v3.16.21.1 ran all nine proofs.
        # With the proofs off pushes to main for the window, the
        # release tag is where they run, so the tag build's last
        # job dispatches each one by name once the mirrors are done
        # (dispatched at tag time, they held the runners the
        # release and the next gate were waiting for) -- this list
        # and PROOF_WORKFLOWS are the same set, and the cut itself
        # names none of them.
        block = _uncommented(_job_block(_workflow(), "proofs"))
        named = set(re.findall(r"\b([a-z-]+\.yml)\b", block))
        self.assertEqual(named, set(self.PROOF_WORKFLOWS))
        self.assertIn('gh workflow run "$wf" --repo "$REPO" --ref "$TAG"', block)
        self.assertIn("needs: [release, pypi-publish, sourceforge, gitlab]", block)
        # pushed or dispatched: the proof workflows carry no push
        # trigger of their own, so this job is the one place a
        # release tag starts them
        self.assertNotIn("github.event_name == 'workflow_dispatch'", block)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", block)
        self.assertIn("needs.release.result == 'success'", block)
        self.assertEqual({("actions", "write"), ("contents", "read")}, _perm_entries(block))
        # the runner/ filter, read against the previous tag by the
        # cut gate's proofs-due: the release's own carrier lines do
        # not count, and anything but a plain "false" starts them
        self.assertIn('python3 runner/tools/cut_gate.py proofs-due --prev "$prev" --tag "$TAG"', block)
        self.assertIn('|| due=true', block)
        self.assertIn('if [ "$due" = "false" ]; then', block)
        self.assertIn("fetch-depth: 0", block)
        cut = _uncommented(_workflow_text("cut-release.yml"))
        step = cut.split("start the release pipeline on the tag", 1)[1]
        # each dispatch through the retrying wrapper (a 502 on the
        # 3.16.24.11 cut left a tag with no build)
        self.assertIn('dispatch 1 build.yml --ref "$TAG"', step)
        self.assertIn('dispatch 2 docker.yml --ref "$TAG" -f tag=latest', step)
        self.assertIn("for n in 1 2 3; do", step)
        self.assertIn('if gh workflow run "$wf" "$@"; then return 0; fi', step)
        # a failed answer to a dispatch that was made is not retried
        # into a second tag build: the runs on the tag are counted
        self.assertIn('if dispatched "$wf" "$want"; then', step)
        self.assertIn('event=workflow_dispatch', step)
        self.assertNotIn('\n            gh workflow run build.yml', step)
        self.assertEqual(set(re.findall(r"\b([a-z-]+\.yml)\b", step)) - {"build.yml", "docker.yml"}, set())

    def test_a_running_tag_proof_finishes_and_the_newest_waits(self):
        # One concurrency group per proof workflow for every release
        # tag, and no cancelling inside it: the run that is going
        # gives its verdict, the newest tag's run waits behind it
        # (one running, one waiting at most). The newest tag
        # cancelling the run before it left the Python range proof
        # with 26 cancelled runs in 39 and no verdict to read; a
        # group per tag had piled the runs up. The nightly and a
        # branch dispatch keep their own groups.
        for name in self.PROOF_WORKFLOWS:
            wf = _workflow_text(name)
            self.assertIn("startsWith(github.ref, 'refs/tags/v') && 'tags' ||", wf, name)
            line = [ln.strip() for ln in wf.splitlines() if ln.strip().startswith("cancel-in-progress:")]
            self.assertEqual(len(line), 1, name)
            if name == "platform-matrix.yml":
                # pushes and pull requests still replace their own
                # matrix; a tag never cancels
                self.assertEqual(line[0], "cancel-in-progress: ${{ !startsWith(github.ref, 'refs/tags/v') && "
                                          "(github.event_name == 'push' || github.event_name == 'pull_request') }}")
            else:
                self.assertEqual(line[0], "cancel-in-progress: false", name)

    def test_the_suites_are_real_jobs_again(self):
        workflow = _workflow()
        for job in ("test", "test-macos", "test-windows"):
            block = _job_block(workflow, job)
            self.assertIn("run_tests_parallel.py", block)
            self.assertNotIn("continue-on-error", _uncommented(block),
                             "%s is still advisory" % job)

    def test_the_gates_are_ungated_and_real(self):
        # Scope, shape and typecheck gate with the artifact legs:
        # none may be advisory or tag-gated.
        workflow = _workflow()
        for job in ("scope", "shape", "typecheck"):
            block = _job_block(workflow, job)
            self.assertNotIn("continue-on-error", block, job)
            self.assertNotIn("if: startsWith(github.ref, 'refs/tags", block, job)
            self.assertNotIn("if: >-\n      startsWith(github.ref, 'refs/tags", block, job)

    def test_the_cut_reads_the_cut_gates_rule(self):
        # One rule for the cut, the promotion check and the train
        # (runner/tools/cut_gate.py): the eight legs always, the
        # Linux suite and both Windows parts when the release
        # carries core code since the previous published release,
        # the suites too when the record cannot be read.
        with open(os.path.join(_root(), ".github", "workflows",
                               "cut-release.yml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("import cut_gate", text)
        self.assertIn("cut_gate.need(os.environ[\"SHA\"], os.environ[\"VERSION\"])", text)
        self.assertNotIn("need = {", text, "cut-release carries a need set of its own")
        # loaded by its path: an entry left on sys.path is a leak the
        # pre-push guard names on whichever module runs next
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cut_gate", os.path.join(_root(), "runner", "tools", "cut_gate.py"))
        cut_gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cut_gate)
        self.assertFalse(cut_gate.relief_active(_root()), "build.yml still carries a live relief marker")
        legs = set(cut_gate.LEGS)
        both = legs | set(cut_gate.SUITES)
        self.assertEqual(set(cut_gate.SUITES), {"test", "test-windows"})
        rels = [{"tag_name": "v0.0.0.9", "draft": False, "published_at": "2026-11-12T00:00:00Z"}]

        def api_for(files):
            return lambda path: rels if path.startswith("/releases") else {"files": [{"filename": f} for f in files]}
        need, why = cut_gate.need("0" * 40, "0.0.0.10", api=api_for(["runner/ops/exec.py", "docs/a.md"]), root=_root())
        self.assertEqual(need, both, why)
        need, why = cut_gate.need("0" * 40, "0.0.0.10", api=api_for(["docs/a.md", "runner/tests/test_a.py", "runner/_version.py"]), root=_root())
        self.assertEqual(need, legs, why)
        need, why = cut_gate.need("0" * 40, "0.0.0.10", api=lambda path: None, root=_root())
        self.assertEqual(need, both, why)
        for leg in ("build-python", "build-linux", "build-linux-arm64",
                    "build-windows", "build-windows-arm64", "build-macos",
                    "build-macos-x86_64", "build-pi-light"):
            self.assertIn(leg, legs, "the gate no longer reads %s" % leg)

    def test_a_full_tag_build_waits_on_the_suites(self):
        # On a promoted tag build the suites are skipped and the
        # promotion check reads them on the gate build; on a full
        # build (a tag placed by hand) the release job waits for
        # the Linux suite and both Windows parts and runs only if
        # none failed.
        block = _job_block(_workflow(), "release")
        m = re.search(r"needs: \[([^\]]+)\]", block)
        self.assertIsNotNone(m, "release job has no needs list")
        needs = [part.strip() for part in m.group(1).split(",")]
        self.assertIn("test", needs, "the release does not wait on the suite")
        self.assertIn("test-windows", needs, "the release does not wait on the Windows suite")
        self.assertNotIn("test-macos", needs, "the macOS suite is a signal, not a gate")
        for leg in ("build-python", "build-windows",
                    "build-windows-arm64", "build-linux",
                    "build-linux-arm64", "build-macos",
                    "build-macos-x86_64", "build-pi-light"):
            self.assertIn(leg, needs,
                          "the release no longer waits on %s" % leg)


class FreeBSDWorkflowEvidenceTest(unittest.TestCase):
    """Q175: the FreeBSD proof's evidence reaches the run page.

    For the workflow's whole history its artifact total was 0:
    the report files were copied inside the VM to a workspace
    path the host-side upload never saw, and the upload's
    if-no-files-found: ignore kept the loss invisible. The vmactions
    step's structure decides what can carry the evidence -- a
    copy-based sync (rsync, the first method for 15.0 on x86_64)
    reaches the host only through the action's copy-back phase,
    while the step's stdout is the run page's own log -- so the
    workflow asks for both, in the open, and these pins keep the
    asking from quietly un-landing.
    """

    def _wf(self):
        return _workflow_text("freebsd.yml")

    def _live(self):
        return _uncommented(self._wf())

    def test_bash_is_installed_in_prepare(self):
        # Suite tests exec bash; FreeBSD's base carries sh only.
        live = self._live()
        pkg_lines = [ln for ln in live.splitlines()
                     if "pkg install -y" in ln and "python" not in ln]
        self.assertTrue(pkg_lines, "no base pkg install line found")
        for token in ("git", "node", "bash"):
            self.assertIn(token, pkg_lines[0])
        self.assertIn("git/node/bash did not install", live)

    def test_the_copy_back_is_requested_explicitly(self):
        live = self._live()
        self.assertIn("sync: rsync", live)
        self.assertIn("copyback: true", live)
        self.assertNotIn("copyback: false", live)

    def test_the_upload_names_the_three_reports_and_warns(self):
        live = self._live()
        for name in ("suite-freebsd.log",
                     "switch-proofs-freebsd-root.md",
                     "freebsd-sh.log"):
            self.assertIn(name, live)
        self.assertIn("if-no-files-found: warn", live)
        self.assertNotIn("if-no-files-found: ignore", live)

    def test_the_failing_ids_are_printed_into_the_step_log(self):
        live = self._live()
        self.assertIn('grep -E "^(FAIL|ERROR): " /tmp/suite-freebsd.log',
                      live)
        self.assertIn('grep -E "^(Ran [0-9]+ tests|OK|FAILED)" '
                      '/tmp/suite-freebsd.log', live)
        # The naming stands after the suite runs and before the
        # step's verdict is returned, so a red suite is named on
        # the run page of the very run that produced it.
        self.assertLess(live.index("suite_wall_clock.py"),
                        live.index('grep -E "^(FAIL|ERROR): "'))
        self.assertLess(live.index('grep -E "^(FAIL|ERROR): "'),
                        live.index('cp /tmp/suite-freebsd.log'))
