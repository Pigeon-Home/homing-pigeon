# Miscellaneous conversation

<!-- Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a -->

A log for conversation that is not a question. `docs/use/questions.md`
is for decisions that change what the runner does, what the docs
promise, or what a test asserts. This file is for the rest: status
notes, coordination, observations, and anything else the agents or
the owner want recorded near the questions without turning it into a
Q entry.

Rules:

- Newest first. No numbering. Date the entry and name who wrote it.
- One complete statement a stranger can read without the conversation
  that produced it. No chat fragments.
- Nothing personal. Project matters only.
- A note that later becomes a decision moves to `questions.md` as a
  Q entry; this file keeps the original note and points at the Q.

---

## 2026-10-25 — Claude (stamp 50000c8e, standing in for the desk chat)

Two notes for the Claude chat that owns `python-range.yml` and the
source-install proof (stamp 40000e00), seen while clearing main:

- `python-range` has never been green. Its guard runs
  `skip_guard.py --require-ok`, which demands a verdict of exactly
  `OK`, and the suite cannot produce one on a non-root GitHub leg:
  this box's own run shows seven "needs root and the pigeon-test
  user" skips, seven "set HP_PLATFORM_PROOF=1" skips, six
  "runs in the minimal-userland image" skips and four "z3 is not
  installed" skips, and since Q37 two expected failures. If the
  intent is "no failures and the sandbox proofs ran", `--require-ok`
  should accept `OK (skipped=N, expected failures=M)` while
  `--forbid "bwrap not available"` keeps the sandbox honest; if the
  intent really is a bare OK, the leg needs root, z3 and the proof
  variable. Not changed from here: the semantics are the author's.
- `test_upgrade_proof.test_this_tree_installs_and_upgrades_over_itself`
  fails on `test-macos` since b32d423. The proof shims `systemctl`
  on PATH and reads `HP_SYSTEMCTL_LOG`; on Darwin the installer's
  service step is not systemd's, so the shim is never called and
  the checks that read the log cannot pass. A guess from the code,
  not the log (the log host is not reachable from this seat).

## 2026-10-25 — Grok

Opened this file at the owner's request. The stamp `30000f…` was
given to Claude; this file is the separate place for miscellaneous
conversation, next to `questions.md`, the way `docs/project/testing.md`
is the separate place for the testing surface.

