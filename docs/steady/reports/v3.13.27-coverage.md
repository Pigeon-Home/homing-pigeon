# Coverage findings

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

This report belongs to package 3.13.27, copied forward from the
3.13.21 edition at Platinum cycle 2; the previous measurement is
[v3.13.21](../v3.13.21/coverage.md). The narrative below is the
baseline edition's, carried unchanged; what each cycle measured
is in the Platinum log at the end, and the current gap list is
[coverage-gaps.md](coverage-gaps.md), refreshed every cycle. It
began as main at 933dbf4b, the day the runner line reduction, the
hosting control plane and the hosted queue landed, and it is the
baseline for **Project Platinum**, the coverage-guided fuzzing
campaign the owner opened on 2026-10-25 (Q59;
`docs/project/campaign-standing-orders.md`, queue P).

## Current status

Two measurements, because the measuring box and CI differ.

**CI, coverage.py** (`coverage.yml`, run 40261270767 on c122691d,
3.13.5; statements and branches, child processes counted, tests and
tools omitted):

| Platform | Covered | Never executed |
|---|---:|---:|
| Linux | 97.9% | 428 statements |
| Windows | 96.8% | 715 statements |

**This report's box, statement coverage** (the stdlib tracer on
Python 3.13.16; `coverage` does not install here, so these figures
count statements only, not branches, and are higher for it):

| | Covered | Missed | Total |
|---|---:|---:|---:|
| Statements, `runner/` without the shipped extensions | 98.5% | 311 | 20901 |
| Statements, `runner/` with the extensions | 98.8% | 356 | 28986 |

5023 tests ran in 9 shards. The failures were the hypothesis-backed
modules, which this box cannot install, and the parallel runner's
own self-test fixture; they are not coverage holes, and CI runs
them.

## The trend

| Package | Statements | Covered | Missed |
|---|---:|---:|---:|
| v3.7.22 | 8697 | 85.5% | 1259 |
| v3.7.30 | 9441 | 91.8% | 778 |
| v3.11.1 | 15326 | 94.2% | 890 |
| v3.12.20 | 16872 | 96.8% | 546 |
| v3.12.61 | 19260 | 95.2% | 932 |
| v3.12.65 | 19369 | 95.4% | 883 |
| 3.13.8 (CI, Linux) | about 20400 | 97.9% | 428 |

The package has more than doubled since v3.7.22 and the missed
count has dropped by two thirds. The dip at v3.12.61 was the
hosting and queue code landing ahead of its tests; the campaign
closed most of it in the four days since.

## Where the gaps are

By area, on this box (statements):

| Area | Statements | Covered |
|---|---:|---:|
| `runner/extensions` | 8085 | 99.4% |
| `runner/ops` | 8051 | 99.5% |
| `runner/runner.py` | 3523 | 98.0% |
| `runner/wire` | 3300 | 98.1% |
| `runner/oracle` | 2793 | 99.5% |
| `runner/guard` | 953 | 99.0% |
| `runner/transport_extensions` | 920 | 98.2% |
| `runner/hosting` | 881 | 89.9% |
| `runner/cloud` | 480 | 97.9% |

The files under 96%:

| File | Covered | Missed | Statements |
|---|---:|---:|---:|
| `hosting/httpdoor.py` | 55.3% | 21 | 47 |
| `ops/live.py` | 77.8% | 2 | 9 |
| `hosting/cli.py` | 83.3% | 34 | 204 |
| `hosting/billing.py` | 92.2% | 13 | 166 |
| `ops/oracle_page.py` | 92.9% | 1 | 14 |
| `hosting/base.py` | 93.6% | 5 | 78 |
| `transport_extensions/queues/__main__.py` | 93.7% | 10 | 158 |
| `extensions/pi-health/pi_health.py` | 94.2% | 15 | 260 |
| `hosting/inventory.py` | 94.7% | 4 | 75 |
| `ops/cli.py` | 94.8% | 5 | 96 |
| `hosting/fly.py` | 95.0% | 3 | 60 |
| `hosting/hetzner.py` | 95.7% | 2 | 47 |
| `ops/startup.py` | 95.8% | 5 | 118 |

`runner/hosting` is the one area below 95%, and it is the newest
code: the control-plane tests drive the command functions through a
recorded-exchange player, so the argv entry point and the real HTTP
client never ran. Both are closed in this package (below).
`ops/live.py`'s two lines are the host-imported-first fallback of
the shared runner lookup, a path neither the suite nor a script
takes. `pi_health.py`'s lines are its Windows memory reader, run on
the Windows map.

## What the gaps are, by kind

`runner/tools/coverage_targets.py` reads every gap against the AST
and names what would reach it. On this box, among functions with two
or more missing statements:

| Class | Functions | Meaning, and what Platinum does with it |
|---|---:|---|
| `logic` | 30 | the main flow never ran: a property test or fuzz seed aimed at the function's arguments |
| `guard` | 13 | one early refusal: one adversarial input |
| `except` | 7 | a handler: the guarded call made to fail (an unreadable file, a refused socket) |
| `platform` | 2 | the other OS's code: covered there, recorded, skipped |
| `shadowed` | 0 | a def rebound later: dead code, filed to Claude (one was found and removed in this package: `_transports_arg`) |

The largest `logic` gaps after the hosting pair: `_sweep_channel_refusals`
(9 lines, the refusal-note and unsignable-stub arms),
`_RecordSealer.open` and `_split_records` in `wire/dtlsproto.py`
(9 and 6, malformed-record arms the DTLS fuzz module reaches when
hypothesis is installed), `handle_stripe_event` (5, the
no-tenant and unpaid-session refusals), `handle_query_mail` and
`handle_board_mail` (5 each, their rejection arms), and
`protocol_v2.platform_facts` (5).

## Closed in this package

- `runner/tests/test_hosting_cli_main.py`: `homing-pigeon-host`
  through `main()` for every subcommand, and every exit code it
  maps (2 bad blob, 3 auth, 4 rate limited, 5 provider, 6
  isolation). `cli.py` goes from 83.3% to the low lines being the
  `cmd_status` empty-inventory branch.
- `runner/tests/test_hosting_httpdoor.py`: the real `UrllibHttp`
  against a loopback server: JSON, text and byte bodies, a 4xx and
  a 5xx as responses, a refused connection as `TransportError`.
  It found one defect: a malformed URL raised `ValueError` from
  `Request()` outside the `try`, escaping the client's contract;
  fixed in the same commit.
- The dead `_transports_arg` in runner.py, which coverage had
  reported for a week as 12 of 19 lines never executed, was a def
  shadowed by cli.py's copy. Removed, with a guard
  (`RunnerHasNoShadowedDefs`) so the shape cannot return.

## Platinum log

One row per cycle, appended by the campaign (Q59). Statements and
branches are coverage.py's on the rig, Linux; the delta is against
the previous row.

| Cycle | Commit | Statements | Branches | Tests landed | Crashes filed | Resources |
|---|---|---:|---:|---:|---:|---|
| 0 (baseline) | 933dbf4b | 97.9% (CI) | see CI | 2 modules | 0 | this box |
| 1 | db3bcc46 | 99.1% | 97.0% | 2 modules, 17 tests | 1 (Q60) | this box, 58% cpu, 31 min wall, under-driven (single-process measure) |
| 2 | 57f419d3 | 99.3% | 97.1% | 5 modules, 28 tests | 1 (Q61) | this box, 48% cpu, 28 min wall, under-driven (single-process measure) |

## Reproducing

CI's way, with coverage.py:

```sh
pip install -c .github/requirements-ci.txt hypothesis coverage
site=$(python -c "import site; print(site.getsitepackages()[-1])")
echo "import coverage; coverage.process_startup()" > "$site/hp-coverage.pth"
export COVERAGE_PROCESS_START=$PWD/.github/coveragerc
python -m coverage run --rcfile=.github/coveragerc -m unittest discover -s runner/tests -t .
python -m coverage combine --rcfile=.github/coveragerc -q
python -m coverage json --rcfile=.github/coveragerc -q -o coverage.json
python runner/tools/coverage_targets.py coverage.json            # the ranked gaps
python runner/tools/coverage_gaps.py coverage.json --out gaps.md  # the CI gap list
```

With more examples per property test, for a fuzzing hour:

```sh
HP_PLATINUM_EXAMPLES=2000 python -m coverage run --rcfile=.github/coveragerc \
    -m unittest runner.tests.test_properties runner.tests.test_oracle_intake_fuzz \
    runner.tests.test_dtls_fuzz
```
