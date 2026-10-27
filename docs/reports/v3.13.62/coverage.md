# Coverage findings

This report belongs to package 3.13.62. The previous measurement
in the tree is [v3.12.65](../v3.12.65/coverage.md). No new tag
was cut for this measurement. It is main at 13d4aacf9446. The gap list
is [coverage-gaps.md](coverage-gaps.md).

## Current status

Measured 2026-10-26 with coverage.py 7.16.2, on Python 3.10.22. Hypothesis
6.168.5 was installed. CI pins hypothesis 6.170.5 and measures on Python
3.12. 7194 tests, 2 failures, 28 skipped. 939 seconds.

The two failures are this environment, not a red main. The hostinfo campaign
shape exited 127, a command this box does not have. The ps probe answered
false, because ps is not installed here. The skips are optional tools that
are not installed here.

The run used .github/coveragerc: source is runner, tests and tools are
omitted, branches are on, and child processes were counted. That is the CI
measurement. The 3.12.65 report left extensions out and counted 19369
statements at 95.4%. This one counts extensions, and the tree is larger:
30412 statements. 99.5% is not the same yardstick as 95.4%.

| | Covered | Missed | Total |
|---|---:|---:|---:|
| Statements | 99.5% | 143 | 30412 |
| Branches | 97.4% | 311 | 12026 |
| Statements and branches | 98.9% | | |

The files at 99% and under, by statements:

| File | Covered | Missed |
|---|---:|---:|
| cloud/send_job.py | 93.8% | 23 |
| extensions/pi-health/pi_health.py | 93.8% | 17 |
| ops/cli.py | 96.0% | 4 |
| hosting/cli.py | 96.2% | 8 |
| ops/startup.py | 98.4% | 2 |
| hosting/fly.py | 98.4% | 1 |
| wire/oauth.py | 98.5% | 3 |
| ops/oracle_server.py | 98.7% | 2 |
| wire/verify.py | 98.7% | 6 |
| guard/security.py | 98.9% | 3 |
| oracle/dri.py | 99.0% | 4 |

runner.py is 99.7% (10 missed of 3702). The floor is cloud/send_job.py and
extensions/pi-health/pi_health.py, both 93.8%. cloud/send_dtls.py is 100.0%
(0 missed of 154). In the 3.12.65 report that file was the floor, at 36.6%.

## Text chart

Statement coverage, 40 cells, one cell is 2.5 points.

```
all               99.5  [########################################]

send_job.py       93.8  [######################################..]
pi_health.py      93.8  [######################################..]
ops/cli.py        96.0  [######################################..]
hosting/cli.py    96.2  [######################################..]
startup.py        98.4  [#######################################.]
fly.py            98.4  [#######################################.]
oauth.py          98.5  [#######################################.]
oracle_server     98.7  [#######################################.]
verify.py         98.7  [#######################################.]
security.py       98.9  [########################################]
runner.py         99.7  [########################################]
send_dtls.py      100.0  [########################################]
```

The functions with the most never-executed lines are in coverage-gaps.md.
The largest is pi_health.py:_mem_avail_pct_windows, 14 lines, the Windows
memory reading. The rest of the list is one or two lines each.

