# Local regression pass and line coverage (2026-10-27)

<!-- Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7 -->

The whole suite, every `runner/tests/test_*.py` module, run once in
one process under `runner/tools/linecov.py` with `--source runner`,
on a cloud box with Python 3.13, two cores and no package index (so
no `coverage.py` and no `hypothesis`). Lines only, no branches, no
child processes. The data beside this file is the tool's report in
coverage.py's JSON shape with `executed_lines` dropped to keep it
small; `runner/tools/coverage_gaps.py` reads it unchanged.

| Report | Tree | Tests run | Result |
|---|---|---:|---|
| `local-regression-before-2026-10-27.json` | `c6c1b73` | 7,308 | 15 red, all from the box: 13 need `hypothesis`, 2 were the skip registry's FIFO entry, which another seat closed during the run |
| `local-regression-after-2026-10-27.json` | `06888e0` | 7,360 | 1 red: `test_transports.NatsTransportExtensionTest.test_exec_round_trip_with_token`, whose 25 second wait ran out under the traced run on two cores; it passes three runs of three alone in 9 seconds |

## Result

| Scope | Before | After |
|---|---:|---:|
| Shipped code (`runner/` without `tests/` and `tools/`) | 99.00% (305 of 30,370 unrun) | 99.51% (148 of 30,370 unrun) |
| `runner/tools/stamp_audit.py` | 58.7% | 98.8% (measured on its own tests after `6a181b5`) |

The before figure is recounted without `global` and `nonlocal`
lines (see "The line counter" below); as first measured it read
98.92%. Other seats landed edge tests in the same window, so the
gain is the tree's, not one commit's.

## Tests added

- `runner/tests/test_script_mode.py` (15 tests). Every module split
  out of `runner.py` is loaded by its file with the `runner` package
  hidden, as `python3 runner/runner.py` sees the tree, and each
  fallback import is held to binding the same object by its bare
  name. Each sense, `send_job.py`, `send_dtls.py` and the host CLI
  answer `--help` as `__main__`; each transport refuses to start
  without a channel with exit 2; the queries worker answers a line
  per request. 109 lines that only a by-path run took.
- `runner/tests/test_refusal_edges.py` (14 tests). The sender's
  verifier shape and walk checks, a hosted queue's refusal, a result
  output whose bytes miss their digest, a file url that is not a
  string, a stage that cannot be written, a manifest that is not
  text or not an object, a config blob over a config that is not an
  object, a first-key name over a keyring that is not an object, and
  the Windows home under the system drive. 20 lines.
- `runner/tests/test_stamp_audit_report.py` (12 tests). The push
  gate's report, its unstamped count, `main` and the log parser's
  skips.

## The line counter

Two fixes to `runner/tools/linecov.py`, each with a test in
`runner/tests/test_linecov.py`:

- A source under a measured folder that does not parse
  (`runner/tests/airgap/interesting.example/OVERVIEW.py`) raised
  after the suite had run and no report was written. It is now
  listed under `meta.unparsed` and left out of the totals.
- `global` and `nonlocal` compile to no instruction, so no line
  event names them, and each read as unrun inside a function that
  ran: 26 such lines in the tree, nine of them in `runner.py`.

## Unrun lines no test can reach

- `runner/ops/exec.py:499`, `script must be a string`: the same
  check stands at the top of the shape checks, so a non-string
  script never gets this far.
- `runner/ops/extsources.py:289`, `names no path`: every value that
  would leave no segment is refused by the checks above it.

## Next targets

The largest remaining gaps in shipped code, from the after report:
`send_dtls.py:main` 248-252 (the verified-result tail, run today only
by the hypothesis suite), `ops/mail.py:handle_mail` 141-143 and 694,
`ops/main.py:main` 46, 61 and 335, `ops/install.py` (`do_check`,
`main`, `--rearm`), `ops/queries.py:answer_queries` 521 and 653, and
`runner.py:run_inspect` 5139-5140. In the tools, `de_dust_corpus.py`
(638 lines unrun), `repair_script_imports.py`, `ci_run_report.py` and
`mutation_floor.py` (no test runs any of their lines in process).
