# Style guide

## Base

- **PEP 8**, at **88 columns**. A short grandfather list in
- `pyproject.toml` (`per-file-ignores`) carries
  the exceptions that existed on day one — 79 lines, counted, in
  five files. New files conform from birth; the list only shrinks,
  and no file is ever added to it.
- **Double quotes**, as the tree already uses.
- **Types at the boundaries.** Function signatures that cross a
  module or wire boundary carry annotations; `pyrefly check runner
  cloud` is the type gate and it is green or the change is not done.
- **Standard library only** in `runner/` and `cloud/`. Tests may use
  what the test gate already uses (Hypothesis). If a change seems to
  need a third-party import, that need is the design smell — solve
  it with the library the project ships on.

## Enforcement

- **Ruff** is the lint tool, configured in `pyproject.toml`:
  `ruff check runner cloud tests tools examples` and the gate is
  green or the change is not done. Day-one rule set: pyflakes (`F`)
  everywhere, pycodestyle errors (`E`) outside the grandfathered
  files. The rule set grows only in a commit that keeps the gate
  green on the whole tree — never by aspiration.
- `ruff format` is the formatter of record for new and touched
  files. There is no tree-wide reformat commit: formatting lands
  file by file as files are touched, so diffs stay reviewable.

## House rules

- **Docstrings carry contracts** — what a function guarantees, what
  it refuses, what it never does ("Never prints a secret. Prints
  the absence of one."). **Comments carry why** — the rationale,
  the spec citation, the field report that forced the shape. A
  comment that restates the code is deleted on sight.
- **Proof of work.** A behavior change lands with its test in the
  same change. Tests are table-driven where the shape allows, named
  for the behavior they pin, and written to still mean something
  after the code around them changes.
- **Nothing raises across an ingest boundary.** Mail handling,
  local-signal handling, and extension output are hostile until
  proven otherwise: log the refusal with its reason and continue.
  Crashes are for programming errors, not for input.
- **Config is flat, defaults live at the read site**
  (`cfg.get("poll_interval_sec", 20)`), and any design question
  that can be a default plus a CLI or config option is resolved
  exactly that way — pick the intelligent default, ship the knob.
  The CLI could grow to fifty options; that is fine.
- **Operator-facing text** — help, log lines, error messages —
  speaks the operator's vocabulary, says what happened and what to
  do next, and is worth reading at 2 a.m. `--help` is a designed
  document, not an argparse accident.
- **Logging is one human-readable log** (`runner.log`, via `log()`),
  verbose by house preference, levels as inline words (`WARN`,
  `ERROR`) where a line is not routine. The direction of travel is
  the OneFuzz discipline: named lifecycle events, a level for each,
  fields over prose — adopted as that work lands, not before.
- **Protocol text is written in IETF dialect** — normative language
  per RFC 2119/8174, changes stated as deltas against the current
  specification. PROTOCOL.md is the specification of record; the
  code conforms to it, or the delta is written down in FUTURE.md.
