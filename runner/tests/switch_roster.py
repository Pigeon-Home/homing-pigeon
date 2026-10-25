# The switch-proof roster: every security control the runner ships,
# what SECURITY.md promises when it is turned on, and the tests that
# prove the promise. Read by runner/tools/switch_proofs.py, which runs
# the proofs on every push and names the controls that have none.
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""The roster is the ledger for queues S and R of
docs/project/campaign-standing-orders.md (owner's target, Q24,
2026-10-25): an item there is done when its entry here lists tests
that run and pass on the leg where the control applies.

Each entry:

    id       the control, as the standing orders name it (M6.wall.network)
    promise  one line: what "on" has to prove, from SECURITY.md
    tests    unittest ids (module, module.Class or module.Class.test)
             that fail if the promise were false, plus the negative
             control that passes for no other reason. Empty = unproven.
    needs    what the leg must provide: "linux" (the control is
             Linux-only), "bwrap" (a working sandbox), "root" (the
             job_user drop needs a real second user). An entry whose
             needs the leg does not meet is not judged on that leg.

Adding a test here is Muse's lane; the controls, promises and needs
are the owner's and change only through the questions file. A test
listed here that is renamed or removed fails the roster loudly, which
is the point: a promise does not lose its proof by accident.
"""

ROSTER = [
    # --- S. The switches, on -------------------------------------------
    {
        "id": "M1.caps",
        "promise": "max_job_bytes and max_script_bytes are always on: over "
                   "the cap is rejected before anything runs; a non-number "
                   "refuses startup.",
        "tests": ["runner.tests.test_size_caps.SizeCapTest",
                  "runner.tests.test_size_caps.CapConfigTest"],
        "needs": [],
    },
    {
        "id": "M2.policy_env",
        "promise": "policy_env per pinned key: enforce denies the dangerous "
                   "name and writes denied; audit runs it and writes "
                   "would_deny; off allows it.",
        "tests": ["runner.tests.test_policy_constraints.PolicyEnvModesTest",
                  "runner.tests.test_policy_constraints.DangerousNamesTest",
                  "runner.tests.test_policy_constraints.Phase2NegativeControls"],
        "needs": [],
    },
    {
        "id": "M2.policy_files",
        "promise": "policy_files per pinned key: the three modes, with the "
                   "audit line's mode member recorded.",
        "tests": ["runner.tests.test_policy_constraints.PolicyFilesModesTest",
                  "runner.tests.test_policy_constraints.PinnedScriptTest"],
        "needs": [],
    },
    {
        "id": "M2.policy_args",
        "promise": "policy_args per pinned key: the three modes; a hostile "
                   "pattern is refused at parse, not matched at run time.",
        "tests": ["runner.tests.test_policy_constraints.PolicyArgsModesTest",
                  "runner.tests.test_policy_constraints.PolicyParseTest"],
        "needs": [],
    },
    {
        "id": "M2.modes",
        "promise": "sec_mode and sec_decide: off/audit/enforce decide the "
                   "same case three ways, and the default key is unaffected "
                   "by another key's policy.",
        "tests": ["runner.tests.test_security_config.SecModeTest",
                  "runner.tests.test_security_config.SecDecideTest",
                  "runner.tests.test_security_config.SecDecideNegativeControl",
                  "runner.tests.test_policy_constraints.DefaultKeyUnaffectedTest"],
        "needs": [],
    },
    {
        "id": "M3.audit_report",
        "promise": "--audit-report is read-only: it writes neither config.json "
                   "nor the audit log, and its counts equal the entries written.",
        "tests": ["runner.tests.test_audit_report.ReportTest",
                  "runner.tests.test_audit_report.FlagIntegrationTest"],
        "needs": [],
    },
    {
        "id": "M4.posture",
        "promise": "--posture is read-only and names every control's mode.",
        "tests": ["runner.tests.test_posture.PostureTest",
                  "runner.tests.test_posture.FlagIntegrationTest"],
        "needs": [],
    },
    {
        "id": "M5.audience",
        "promise": "audience enforce rejects a job whose audience is not this "
                   "runner_id; audit runs and records it; off ignores it; the "
                   "seen set is namespaced per runner.",
        "tests": ["runner.tests.test_audience.AudienceModesTest",
                  "runner.tests.test_audience.CrossRunnerTest",
                  "runner.tests.test_audience.SeenNamespacingTest"],
        "needs": [],
    },
    {
        "id": "M6.startup",
        "promise": "confinement enforce with a sandbox that does not work at "
                   "startup refuses to start, naming the key (Q9).",
        "tests": ["runner.tests.test_confinement.StartupProblemScriptsTest"],
        "needs": ["linux"],
    },
    {
        "id": "M6.enforce",
        "promise": "confinement enforce runs the job inside bwrap; the "
                   "negative control shows the same escape succeeding with "
                   "the mode off.",
        "tests": ["runner.tests.test_confinement.EnforceTest",
                  "runner.tests.test_confinement.EnforceNegativeControl",
                  "runner.tests.test_confinement.SandboxAuditNoteTest"],
        "needs": ["linux", "bwrap"],
    },
    {
        "id": "M6.wall.network",
        "promise": "inside the sandbox a job has no network; with the mode "
                   "off the same job reaches the loopback listener.",
        "tests": ["runner.tests.test_confinement.WallNetworkTest"],
        "needs": ["linux", "bwrap"],
    },
    {
        "id": "M6.wall.home",
        "promise": "inside the sandbox the runner's home and config are not "
                   "visible; off, the same job reads them.",
        "tests": ["runner.tests.test_confinement.WallHomeTest"],
        "needs": ["linux", "bwrap"],
    },
    {
        "id": "M6.wall.usr",
        "promise": "inside the sandbox /usr is read-only; off, the same write "
                   "lands (in a scratch tree bound as /usr for the test).",
        "tests": ["runner.tests.test_confinement.WallUsrTest"],
        "needs": ["linux", "bwrap"],
    },
    {
        "id": "M6.wall.work",
        "promise": "inside the sandbox the workdir is at /work and nothing of "
                   "the base dir outside it is reachable.",
        "tests": ["runner.tests.test_confinement.WallWorkTest"],
        "needs": ["linux", "bwrap"],
    },
    {
        "id": "M6.fallback",
        "promise": "a sandbox that fails after a good start lets the job run "
                   "unsandboxed with a WARN line and a fallback audit entry "
                   "(owner decision, 2026-10-15); audit mode records "
                   "would_run_sandboxed and runs normally.",
        "tests": ["runner.tests.test_confinement.FallbackTest"],
        "needs": ["linux"],
    },
    {
        "id": "M7.templates",
        "promise": "the AppArmor, SELinux and systemd templates parse, name "
                   "the install layout's paths, and nothing installs them.",
        "tests": ["runner.tests.test_hardening_templates.TemplateTest",
                  "runner.tests.test_hardening_templates.TemplateParseTest"],
        "needs": [],
    },
    {
        "id": "M8.drop",
        "promise": "job_user enforce runs the job as the second user: uid and "
                   "groups dropped, the workdir chowned to it; a failed "
                   "initgroups does not keep the runner's groups (Q18).",
        "tests": ["runner.tests.test_secret_files_job_user.JobUserTest",
                  "runner.tests.test_secret_files_job_user.JobUserGroupsProbe"],
        "needs": ["linux", "root"],
    },
    {
        "id": "M8.drop.face",
        "promise": "the drop against a fake OS face: not root, an unknown "
                   "user or a chown failure never demote; enforce chowns the "
                   "tree and returns the demote; a failed initgroups falls "
                   "back to setgroups, and both failing refuses the job.",
        "tests": ["runner.tests.test_runner_face.JobUserFaceTest"],
        "needs": [],
    },
    {
        "id": "M8.fallback",
        "promise": "job_user without root runs the job as the current user "
                   "with a WARN line and a job_user_needs_root audit entry "
                   "(owner decision, 2026-10-15); a user gone at job time "
                   "falls back the same way.",
        "tests": ["runner.tests.test_secret_files_job_user.JobUserTest.test_non_root_falls_back",
                  "runner.tests.test_runner_face.JobUserFaceTest.test_not_root_does_not_demote"],
        "needs": ["linux"],
    },
    {
        "id": "M8.secret_files",
        "promise": "a missing or world-readable secret file refuses startup; "
                   "the secret never reaches a job's environment or the "
                   "workdir (the credential canary).",
        "tests": ["runner.tests.test_secret_files_job_user.SecretFilesTest",
                  "runner.tests.test_credential_canary.TestCredentialCanarySameUid",
                  "runner.tests.test_credential_canary.TestCanaryNegativeControls"],
        "needs": ["linux"],
    },
    {
        "id": "SEC.no_hot_reload",
        "promise": "a config.json write during a run does not hot-reload the "
                   "security block; a bad value written live leaves the "
                   "current settings in force (Decision 1).",
        "tests": ["runner.tests.test_security_md_claims.SecurityBlockNoReloadTest"],
        "needs": [],
    },
    {
        "id": "ORACLE.latitude",
        "promise": "the Oracle, simulated: refuse and advise latitude refuse "
                   "what repair repairs (AGENTS.md's table), with fixtures "
                   "and a loopback fake model, never a live one.",
        "tests": ["runner.tests.test_protocol_examples.MissingBinaryRowAsAmended",
                  "runner.tests.test_protocol_examples.DoNotEmitTableTest"],
        "needs": [],
    },
    {
        "id": "ORACLE.no_widening",
        "promise": "an Oracle answer cannot widen a security decision made "
                   "above it: a denied job stays denied whatever the model "
                   "says; a repair never changes a pinned key's policy.",
        "tests": ["runner.tests.test_oracle_no_widening.NoWideningTest"],
        "needs": [],
    },
    # --- R. Races on the enforce path ------------------------------------
    {
        "id": "R1.two_jobs",
        "promise": "workers: 2 under enforce: each workdir is chowned to its "
                   "own job, never the other's; two sandboxes do not share "
                   "/work; the audit log holds both decisions, each whole.",
        "tests": ["runner.tests.test_enforce_races.TwoJobsRaceTest"],
        "needs": ["linux", "bwrap", "root"],
    },
    {
        "id": "R2.audit_rollover",
        "promise": "a rollover of security-audit.jsonl (_enforce_bound) while "
                   "a decision is being written loses no entry and splits none.",
        "tests": ["runner.tests.test_enforce_races.AuditRolloverRaceTest"],
        "needs": [],
    },
    {
        "id": "R3.seen_set",
        "promise": "a replayed job id and a fresh job hitting the seen set "
                   "together: the replay is rejected on both orderings.",
        "tests": ["runner.tests.test_enforce_races.SeenSetRaceTest"],
        "needs": [],
    },
    {
        "id": "R5.policies_concurrent",
        "promise": "workers: 2 under enforce: two jobs with different "
                   "pinned keys decided together: each denial names its "
                   "own key and job id, no decision crosses over, and the "
                   "same for two audiences (Q26 review, 2026-10-25).",
        "tests": [],
        "needs": [],
    },
    {
        "id": "R6.drop_concurrent",
        "promise": "workers: 2 under job_user enforce: each child runs as "
                   "the job user with its own workdir; the runner itself "
                   "never drops; a drop that fails for one job falls back "
                   "for that job only (Q26 review, 2026-10-25).",
        "tests": [],
        "needs": ["linux", "root"],
    },
    {
        "id": "ORACLE.no_widening.cage",
        "promise": "a fake model answer that proposes running unsandboxed, "
                   "as root, or outside /work changes neither the "
                   "confinement nor the job_user decision (Q26 review, "
                   "2026-10-25).",
        "tests": [],
        "needs": [],
    },
    {
        "id": "R4.config_write",
        "promise": "a config.json write during a job, driven with a real "
                   "second thread: the security block of the running job "
                   "does not change; a bad live value keeps the old binding.",
        "tests": ["runner.tests.test_enforce_races.ConfigWriteRaceTest"],
        "needs": [],
    },
]

KNOWN_NEEDS = ("linux", "bwrap", "root")
