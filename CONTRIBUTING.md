# Contributing to Homing Pigeon

Thanks for stopping by. This is a small, security-sensitive project —
a tool that runs code on people's machines — so contributions are
welcome but held to a high bar. Here's how to do it well.

## Before you write code

- **Read PROTOCOL.md first.** The wire protocol is the contract. If
  your change alters what goes over the wire, the protocol doc changes
  with it, in the same pull request.
- **Read the security model** (PROTOCOL.md §7 and SECURITY.md). If your
  change touches authentication, signature verification, process
  execution, or credential handling, say so explicitly in your PR
  description so it gets the right scrutiny.

## Ground rules

1. **Standard library only.** The runner and installer ship as frozen
   binaries and must run on machines with nothing installed. No new
   third-party dependencies, ever. If you think you need one, open an
   issue first and make the case.
2. **Cross-platform or it doesn't ship.** Every change must work on
   Linux, macOS, FreeBSD, and Windows. Use `os.name` / `sys.platform`
   branches, and think about what each branch does on the other three.
3. **Tests or it didn't happen.** `python -m unittest discover -s tests`
   must pass. New behavior gets a new test with the fake IMAP/SMTP
   harness in `tests/test_runner.py`.
4. **No secrets in the repo.** Not in code, not in tests, not in docs,
   not in commit messages. Test credentials stay obviously fake
   (`runner@example.com` and friends).

## How to contribute

1. Fork the repo and create a branch with a descriptive name
   (`fix-timeout-race`, `add-heartbeat`, ...).
2. Make your change, add tests, update docs (README, PROTOCOL.md,
   RUNBOOK.md — whichever your change affects).
3. Run the full suite: `python -m unittest discover -s tests -v`.
4. Open a pull request against `main`. Describe **what** changed,
   **why**, and **what you tested**. If it touches anything listed
   under "Before you write code," flag it in the description.

## Style

- Plain, readable Python. Type hints where they help, not everywhere.
- Comments explain *why*, not *what*. Security-critical code gets
  a comment saying what attack it prevents.
- Keep the security warning in the README loud. PRs that soften it
  will be asked to put it back.

## Reporting bugs

Use the bug report template. Include: platform, Python version (or
which release binary), what you did, what you expected, what happened,
and the relevant log lines. If it's a security issue, **do not** open
a public issue — see SECURITY.md.
