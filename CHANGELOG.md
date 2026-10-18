# Changelog

## Unreleased

### Features

- User extensions. An extension is a folder holding an
  `extension.json` manifest: the sensor name it files as, its own
  semver (the author's number, revved freely), the extension API
  version it was written against, and the declared list of signals
  it may send the Oracle, each with a one-line description. The
  loader validates manifests strictly (unknown fields refused by
  name), enforces the API rule (current loads, newer refused with
  a readable reason, older accepted under an additive-only
  promise), and reports loads and refusals at startup; a broken
  extension is refused and logged and never affects the agent.
  Ingest rejects an undeclared signal (or none) from an
  extension-backed sense; a declared signal is stored with its
  declared description and the extension's version attached, and
  `senses` answers carry a `declared_signals` glossary — the
  declaration is the context the Oracle receives. Extensions live
  in `<base_dir>/extensions` or the `extensions_dir` config key.
  Ships with a lab-results example sense under
  `examples/extensions/lab-results/` and the full walkthrough in
  docs/extensions.md.

## 3.7.37 - 2026-10-18

### Security

- `output_retention_days: 0` now means no expiry everywhere. The
  prune path already treated 0 as "keep forever"; the expiry check
  treated an explicit 0 as the 7-day default through `or 7`, so a
  record the prune would keep was reported expired after a week.
  Absent, None, or unparseable still falls back to 7. A negative
  value still never expires and prunes nothing.

### Tests

- A coverage-guided campaign over the parser surfaces. Each
  candidate is exercised under a line tracer scoped to `runner/`,
  and it joins the corpus only when it adds coverage. The in-suite
  run is 150 rounds. Growth past the seeds is required on Linux,
  where it was measured; every platform keeps the construction
  contracts (coverage includes the seeds-only baseline, the corpus
  never drops a seated seed or passes the cap, same seed gives the
  same corpus). The tracer matches a runner path case-insensitively,
  because Windows does not always spell the path the way `abspath`
  does.

### CI

- The Windows sharded-suite reporter can no longer be crashed by
  shard output. Printing a failed shard used to raise
  UnicodeEncodeError on the cp1252 console, the reporting loop
  aborted with a log still open, and tempdir cleanup then died
  with a sharing violation, so the real failure never appeared.
  Shard output is written as UTF-8, a shard is counted failed
  before its log is printed, and cleanup tolerates a directory it
  cannot remove.
- Shard children write UTF-8 on stdio. The reporter reads their
  logs as UTF-8; a Windows child on the ANSI code page either
  failed while printing a character outside that page or delivered
  the dump as backslash escapes. `PYTHONIOENCODING=utf-8` is stdio
  only, so `open()` keeps the locale encoding.
