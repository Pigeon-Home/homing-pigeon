# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
"""Every skip in the suite is registered, with its reason to exist.

2026-10-21 found three kinds of skip the suite could not see: three
tests disabled with `if True: self.skipTest(...)` and left that way;
the bwrap sandbox proofs skipping on every CI run because nothing
installed bwrap; and a z3 proof that looked like coverage and was a
dev-time convenience. All three were green from the outside.

This test makes a skip a declared thing. Every literal reason passed
to skipUnless / skipIf / skipTest / SkipTest must appear below with
one line saying why that skip is legitimate and where the test DOES
run. A new skip fails here until it is written down; a registered
reason no test uses any more fails too, so the list cannot rot. The
reasons are matched exactly, so changing the wording is also a
deliberate act.

Where a reason says "runs in <job>", runner/tests/test_build_config.py or
the workflow in question is where that promise is kept.
"""
import ast
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TESTS = os.path.dirname(os.path.abspath(__file__))

# reason -> why this skip is legitimate, and where the test runs.
REGISTERED = {
    # ---- fixtures of the switch-proof tool (test_switch_proofs) -----
    # Fake test cases built inside a function, never collected by
    # discovery: they exist so the tool's SKIPPED verdict and its
    # "one skip beside a pass is still a proof" rule are pinned.
    "not on this leg": "a fake case the switch-proof tool judges, never expected to run as a test",
    "unix only": "a fake case the switch-proof tool judges, never expected to run as a test",
    "the sandbox probe is Linux-only":
        "test_confinement's scripted bwrap: startup_problem answers "
        "off Linux before it looks for bwrap; runs in the ubuntu jobs",
    "running as root":
        "test_switch_proofs: the --root refusal cannot be shown when the "
        "process is root; runs in every non-root job",
    "git is not on PATH":
        "test_regression_guard's temporary-repository tests; git is on "
        "every CI leg's PATH, so they run in every job",
    "no SIGALRM on this platform":
        "test_de_dust_survivors' timeout verdict rides on SIGALRM, "
        "which Windows does not have; the Linux and macOS legs run it",
    # ---- platform splits: each side runs in its own CI job ----------
    "Linux-only suite: it pins POSIX modes, nofollow opens, signals, "
    "and systemd units, and runs in the Linux test job":
        "the test_linux_* modules; run in the ubuntu test job",
    "POSIX installer path": "run on ubuntu and macOS; Windows has its own",
    "POSIX only": "run on ubuntu and macOS",
    "kill_tree's group and extra-pid legs are POSIX-only":
        "test_runner_last_edges; the legs drive POSIX process-group "
        "signalling and run on ubuntu and macOS -- the Windows "
        "kill_tree legs in the same module run in the Windows job",
    "needs a /proc to scan":
        "the service-watch live-read smoke test; runs in the Linux "
        "CI job, and the function's branches run everywhere via a "
        "scripted /proc",
    "needs bwrap on Linux":
        "test_confinement; the sandbox proofs run in the ubuntu test job, "
        "where bwrap is installed",
    "sandbox cannot engage on this machine (startup probe)":
        "test_confinement enforce classes (Q10); they run where the "
        "startup probe's trial run succeeds -- the env-axes job at "
        "restriction 0 and any host whose bwrap can start",
    "the startup probe's Linux branch":
        "test_confinement startup-problem scripts; run in the "
        "Linux test job -- the probe answers at its platform "
        "guard on every other platform",
    "uid reporting is POSIX":
        "test_secret_files_job_user; run on ubuntu and macOS",
    "git not installed": "test_make_snapshot builds throwaway repos; git is "
                         "on every CI runner, so this runs everywhere CI does",
    "POSIX quoting is the live shell here": "run on ubuntu and macOS",
    "POSIX-shaped fixture (/bin tools, LF offsets, /proc)":
        "test_doc_default_divergences hunt fixtures; run on POSIX",
    "Unix mode bits": "run on ubuntu and macOS",
    "entry kinds need POSIX links and fifos":
        "test_platinum_runner's workspace sweep plants symlinks and a "
        "fifo; run on ubuntu and macOS",
    "ACL home differs on Windows": "run on POSIX; Windows path tested separately",
    "AV path finding differs on Windows": "run on POSIX",
    "chmod behavior differs on Windows": "run on POSIX",
    "console behavior differs on Windows": "run on POSIX",
    "execute_job fixtures are POSIX shell": "run on POSIX",
    "exec jobs are POSIX sh scripts": "run on POSIX",
    "loop cycles are POSIX sh scripts":
        "test_campaign_loop_cycles; run on ubuntu and macOS",
    "loop variants are POSIX sh scripts":
        "test_campaign_loop_variants; run on ubuntu and macOS",
    "host tools required":
        "test_campaign_loop_variants needs uptime/hostname; runs on every "
        "POSIX CI runner, which all have them",
    "df/free required":
        "test_campaign_loop_variants needs df and free; runs in the ubuntu "
        "test job, which has both (macOS has no free)",
    "field scenarios use sh": "run on POSIX (and confined on ubuntu, with bwrap)",
    "frozen tree layout differs on Windows": "run on POSIX",
    "geteuid is POSIX": "run on POSIX",
    "cannot create a symlink here":
        "the host refuses symlink creation (a Windows "
        "privilege); run where symlinks can be created",
    "job_user audit is POSIX": "run on POSIX",
    "job_user face is POSIX syscalls": "run on POSIX",
    "job_user fallback is POSIX": "run on POSIX",
    "job_user is Unix-only": "run on POSIX",
    "launchd tests patch os.getuid, which Windows lacks": "run on POSIX",
    "mode bits are POSIX": "run on POSIX",
    "off-Windows check": "run on POSIX",
    "posix sampler": "run on POSIX",
    "proc parsing is POSIX": "run on POSIX",
    "quarantine path differs on Windows": "run on POSIX",
    "socket bind behavior differs on Windows": "run on POSIX",
    "these jobs use sh": "run on POSIX",
    "wipe unload differs on Windows": "run on POSIX",
    "clamdscan shim is a shell script": "run on POSIX",
    "Windows Defender is present": "run in the Windows job",
    "Windows reads the event log": "run in the Windows job",
    "Windows reads the registry": "run in the Windows job",
    "Windows shows registry watch": "run in the Windows job",
    "no /proc/meminfo": "run on Linux",
    "no /proc/stat": "run on Linux",
    "time.tzset is unavailable here": "run on POSIX",
    "socketpair unavailable": "run on POSIX",
    "posix spawn arm":
        "the relay launch sets start_new_session on POSIX; runs on "
        "ubuntu and macOS. The Windows arm is "
        "test_nt_spawn_uses_the_process_group_value, which patches os.name",
    "ps and a POSIX shell":
        "the live ps sampler test spawns a shell tree and reads it with "
        "ps; runs on every POSIX leg (Windows has neither)",
    "needs root and pigeon-test":
        "the Q26 draft cage test drops to the pigeon-test user; runs on "
        "the root switch-proof legs",
    "needs symlink": "run where symlinks exist (every CI leg but some Windows configs)",
    "sandbox cannot engage":
        "the Q26 draft cage test needs a working confinement; runs on "
        "the ubuntu legs with bwrap",
    "symlinks unavailable": "run where symlinks exist",
    "junctions exist on Windows only":
        "test_workspace_isolation's junction leg; runs in the Windows job",
    "cannot create a junction here":
        "the Windows runner refused mklink /J; runs where it is allowed",
    "temp test file leaks into discovery on Windows":
        "run on POSIX; the Windows guard is the one remaining follow-up "
        "from the 2026-10-21 re-enable",
    "strict growth is measured on Linux; another platform reaches a "
    "different platform-conditional line set": "run on Linux",
    # ---- interpreter version floors ---------------------------------
    "sys.monitoring needs 3.12+": "run on the 3.12 CI interpreter",
    "threading.gettrace needs 3.10+": "run on the 3.12 CI interpreter",
    "the Linux and macOS source install; Windows installs from the release binaries": "the Windows install is the binary one, proven by build.yml's windows smoke; run on every POSIX leg",
    "exec jobs run sh; the soak's own leg is Linux": "the soak drives sh exec jobs; soak.yml and every POSIX leg run it",
    "make_sbom runs on the build Python (tomllib, 3.11+)": "a release tool, never on a runner box; run on the 3.12 CI interpreter",
    "sys.stdlib_module_names is 3.10+; static check": "a static read of the source, so one Python proves it; run on the 3.12 CI interpreter",
    # ---- tools that must be present: forbidden to skip where installed
    "node is not installed":
        "GitHub hosted runners ship node, so these run in CI",
    "z3 is not installed":
        "deliberate dev-time proof; the ungated runner-side tests beside it "
        "run everywhere (owner decision 2026-10-21)",
    "needs root and the pigeon-test user":
        "a dedicated-user install; exercised by hand, not in CI",
    # ---- fixtures that must be absent -------------------------------
    "fixture interpreter unexpectedly present":
        "guards a fixture name that must not exist; never expected to fire",
    "jobcrypto not landed yet":
        "stale wording: jobcrypto shipped and these three run everywhere "
        "(the guard is a leftover from before it landed)",
    "setup module not importable": "guards an import; never expected to fire",
    "the documented default path exists on this box":
        "guards the falco-feed main() fallback probe, which needs "
        "Falco's default log absent; runs on every CI runner, none "
        "of which runs a live Falco file output",
    # ---- opt-in proof modules: run by their own workflow legs ------
    "runs in the .github/docker/minimal-userland image":
        "run by .github/workflows/minimal-userland.yml, which fails on any skip",
    "set HP_PLATFORM_PROOF=1 to run the portable proof":
        "run by .github/workflows/platform-matrix.yml on every leg, "
        "which fails on any skip",
    # ---- environment limits of a CI box ------------------------------
    "unconnected UDP sends are blocked in this environment; a DTLS server "
    "cannot run here (the pipe-level tests cover the same code over a "
    "connected socket)": "the pipe-level DTLS tests run everywhere",
}

_SKIP_CALLS = {"skipUnless": 1, "skipIf": 1, "skipTest": 0,
               "SkipTest": 0, "skip": 0}


def literal_skip_reasons():
    """{reason: sorted file names} for every literal reason in runner/tests/."""
    found = {}
    for name in sorted(os.listdir(TESTS)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(TESTS, name), encoding="utf-8") as fh:
            try:
                tree = ast.parse(fh.read())
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            callee = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if callee not in _SKIP_CALLS:
                continue
            idx = _SKIP_CALLS[callee]
            if len(node.args) > idx:
                arg = node.args[idx]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.setdefault(arg.value, set()).add(name)
    return {k: sorted(v) for k, v in found.items()}


class SkipRegistryTest(unittest.TestCase):
    def test_every_skip_reason_is_registered(self):
        found = literal_skip_reasons()
        missing = {r: f for r, f in found.items() if r not in REGISTERED}
        self.assertEqual(
            missing, {},
            "unregistered skip reason(s). Add each to REGISTERED in "
            "runner/tests/test_skip_registry.py with one line saying why the "
            "skip is legitimate and where the test runs:\n" +
            "\n".join("  %r  in %s" % (r, ", ".join(f))
                      for r, f in sorted(missing.items())))

    def test_registry_carries_no_dead_entries(self):
        found = literal_skip_reasons()
        dead = sorted(r for r in REGISTERED if r not in found)
        self.assertEqual(dead, [],
                         "registered reason(s) no test uses any more; "
                         "remove them: %r" % dead)

    def test_every_entry_says_where_the_test_runs(self):
        for reason, why in REGISTERED.items():
            self.assertTrue(
                any(k in why.lower() for k in
                    ("run", "forbidden", "never expected", "exercised")),
                "entry for %r does not say where it runs: %r" % (reason, why))

    def test_no_unconditional_skip(self):
        # `if True: self.skipTest(...)` is how three tests died quietly.
        for name in sorted(os.listdir(TESTS)):
            if not name.endswith(".py"):
                continue
            path = os.path.join(TESTS, name)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.If) and isinstance(node.test, ast.Constant) \
                        and node.test.value is True:
                    body_src = ast.dump(node.body[0]) if node.body else ""
                    self.assertNotIn("skipTest", body_src,
                                     "%s:%d: unconditional skip" % (name, node.lineno))
                    self.assertNotIn("SkipTest", body_src,
                                     "%s:%d: unconditional skip" % (name, node.lineno))

    def test_the_registry_is_not_tiny(self):
        # If this number collapses, the scanner broke, not the suite.
        self.assertGreaterEqual(len(literal_skip_reasons()), 40)


if __name__ == "__main__":
    unittest.main()
