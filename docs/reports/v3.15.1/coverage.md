# Coverage findings

This report belongs to package 3.15.1. The previous measurement
in the tree is [v3.13.62](../v3.13.62/coverage.md). No new tag
was cut for this measurement. It is main at a2e7f037, two commits
after the v3.15.1 tag. The gap list is [coverage-gaps.md](coverage-gaps.md).

## Current status

Measured 2026-11-01 with coverage.py 7.16.2, on Python 3.11.
Hypothesis 6.170.3 was installed. CI pins a newer hypothesis and
measures on Python 3.12. 8273 tests, 6 failures, 47 skipped.
1226 seconds.

Four of the failures are this environment, the same shape as the
3.13.62 note. The hostinfo campaign shape exited 127, a command
this box does not have. The ps probe answered false, because ps
is not installed here. Two tests wanted empty output and got a
warning instead: something on this box talked to the local signal
socket with no signature, and the live-mode shape and the
lab_results help text both printed that warning. The skips are
optional tools that are not installed here.

Two failures are the corpus, not a missing command. The local
inbox replay of seed `wrong_key` said the ingest saw 3 envelopes
and the inbox held 2 it could read. The board reader, replayed
twice, did not come back the same: the two digests differ. Both
are recorded here and not folded into the coverage number.

The run used .github/coveragerc: source is runner, tests and tools
are omitted, branches are on, and child processes were counted.
That is the same yardstick as the 3.13.62 report. The tree is
larger, 33197 statements against 30412, and more of it was not
run: 437 lines missed against 143.

| | Covered | Missed | Total |
|---|---:|---:|---:|
| Statements | 98.7% | 437 | 33197 |
| Branches | 96.4% | 472 | 13110 |
| Statements and branches | 98.0% | | |

The files at 99% and under, by statements:

| File | Covered | Missed |
|---|---:|---:|
| ops/oracle_server.py | 65.8% | 52 |
| ops/mail.py | 83.7% | 63 |
| ops/cancel.py | 90.0% | 16 |
| transport_extensions/nats/__main__.py | 92.3% | 21 |
| ops/changes.py | 92.5% | 8 |
| wire/verify.py | 93.7% | 46 |
| transport_extensions/queues/__main__.py | 94.5% | 17 |
| cloud/send_job.py | 95.5% | 44 |
| wire/oauth.py | 96.6% | 7 |
| transport_extensions/email/__main__.py | 96.9% | 5 |
| ops/startup.py | 96.9% | 5 |
| wire/platformcard.py | 97.1% | 2 |
| transport_extensions/channel.py | 97.4% | 4 |
| oracle/opinion.py | 97.4% | 8 |
| ops/poll.py | 97.9% | 2 |
| transport_extensions/dtls/__main__.py | 98.1% | 4 |
| ops/queries.py | 98.2% | 8 |
| cloud/send_dtls.py | 98.3% | 3 |
| oracle/senses.py | 98.4% | 5 |
| hosting/fly.py | 98.4% | 1 |
| runner.py | 98.4% | 62 |
| ops/exec.py | 98.5% | 7 |
| guard/security.py | 98.5% | 4 |
| oracle/dri.py | 99.0% | 4 |

runner.py is 98.4% (62 missed of 3946). In the 3.13.62 report it
was 99.7% (10 missed of 3702). The floor is ops/oracle_server.py
at 65.8%, then ops/mail.py at 83.7%. cloud/send_job.py is 95.5%
(44 missed of 986). In the 3.13.62 report that file was 93.8%.

## Text chart

Statement coverage, 40 cells, one cell is 2.5 points.

```
all              98.7  [#######################################.]
oracle_server    65.8  [##########################..............]
mail.py          83.7  [#################################.......]
cancel.py        90.0  [####################################....]
nats             92.3  [#####################################...]
changes.py       92.5  [#####################################...]
verify.py        93.7  [#####################################...]
queues           94.5  [######################################..]
send_job.py      95.5  [######################################..]
runner.py        98.4  [#######################################.]
```

The functions with the most never-executed lines are in coverage-gaps.md.
The largest is mail.py:handle_mail, 63 lines. Next are the oracle
server's do_GET (24) and do_POST (23), then _in_root_object_at in
send_job.py and verify.py, 22 lines each. The rest of the list is
eleven lines or fewer.
