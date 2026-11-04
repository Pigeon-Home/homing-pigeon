# Coverage findings

This report belongs to package 3.12.65. The previous measurement is
[v3.12.61](../v3.12.61/coverage.md). No new tag was cut for this
measurement. It is main at dd89ba4. The gap list for this package
is [coverage-gaps.md](coverage-gaps.md).

## Current status

Measured 2026-10-25 with coverage.py 7.16.2, on Python 3.11.2.
Hypothesis 6.170.3 was installed. CI pins hypothesis 6.170.5.
5740 tests, 3 failures, 25 skipped. 511 seconds.

The failures are local to this machine, not a coverage hole:
`hostinfo` exited 127 (a command was not found), the pi-health
readings test saw a socket-signature warning on stdout, and the
file-and-nats supervised run did not deliver both transports
within 30 seconds. The skips are optional tools that are not
installed here.

| | Covered | Missed | Total |
|---|---:|---:|---:|
| Statements | 95.4% | 883 | 19369 |
| Branches | 93.0% | 551 | 7898 |
| Statements and branches | 94.7% | | |

`runner/tests/`, `runner/tools/`, and `runner/extensions/` are
left out of `--source`. The suite and the CI scripts are the
measurement, not the subject. The shipped extensions still do
not count. `runner/cloud/` does. Without those two files the
statement figure is 96.1% (735 missed of 18921)
and statements-and-branches is 95.4%.

The files still under 96%, by statements:

| File | Covered | Missed |
|---|---:|---:|
| cloud/send_dtls.py | 36.6% | 97 |
| transport_extensions/nats/__main__.py | 79.8% | 46 |
| transport_extensions/dtls/__main__.py | 81.5% | 33 |
| cloud/send_job.py | 82.7% | 51 |
| guard/defaulted.py | 87.0% | 7 |
| wire/platformcard.py | 88.6% | 5 |
| ops/extsources.py | 90.6% | 132 |
| oracle/resources.py | 92.8% | 14 |
| ops/auditreport.py | 93.5% | 15 |
| guard/security.py | 93.5% | 15 |
| guard/confval.py | 94.0% | 3 |
| wire/mailbox.py | 94.2% | 11 |
| oracle/detection.py | 94.3% | 10 |
| wire/oauth.py | 94.8% | 12 |
| wire/verify.py | 95.0% | 23 |
| oracle/dri.py | 95.1% | 20 |
| wire/board.py | 95.5% | 13 |
| guard/sandbox.py | 95.7% | 6 |
| runner.py | 95.8% | 269 |

`runner.py` is 95.8% (269 missed of 6412). The floor is
`cloud/send_dtls.py` at 36.6%. `cloud/send_job.py` rose from
69.5% in the 3.12.61 report to 82.7%. The socket and broker
programs are still the low end of the runner itself.
`guard/defaulted.py` is new on this chart, at 87.0%.

## Text chart

Statement coverage, 40 cells, one cell is 2.5 points.

```
all               95.4  [######################################..]

send_dtls.py      36.6  [###############.........................]
nats ext          79.8  [################################........]
dtls ext          81.5  [#################################.......]
send_job.py       82.7  [#################################.......]
defaulted.py      87.0  [###################################.....]
platformcard.py   88.6  [###################################.....]
extsources.py     90.6  [####################################....]
resources.py      92.8  [#####################################...]
auditreport.py    93.5  [#####################################...]
security.py       93.5  [#####################################...]
confval.py        94.0  [######################################..]
mailbox.py        94.2  [######################################..]
detection.py      94.3  [######################################..]
oauth.py          94.8  [######################################..]
verify.py         95.0  [######################################..]
dri.py            95.1  [######################################..]
board.py          95.5  [######################################..]
sandbox.py        95.7  [######################################..]
runner.py         95.8  [######################################..]
jobcrypto.py      96.1  [######################################..]
protocol_v2.py    96.3  [#######################################.]
senses.py         97.4  [#######################################.]
channel.py        98.0  [#######################################.]
review.py         98.1  [#######################################.]
learning.py       98.2  [#######################################.]
install.py        98.2  [#######################################.]
email ext         98.4  [#######################################.]
extensions.py     98.5  [#######################################.]
file ext          98.6  [#######################################.]
personal_docs.py  98.8  [########################################]
transports.py     98.9  [########################################]
dtlsproto.py      99.3  [########################################]
opinion.py        99.4  [########################################]
remediation.py    99.6  [########################################]
winlog.py        100.0  [########################################]
textutil.py      100.0  [########################################]
local_test.py    100.0  [########################################]
setup.py         100.0  [########################################]
posture.py       100.0  [########################################]
harness.py       100.0  [########################################]
```

`runner/__init__.py` and `runner/_version.py` are fully covered.
`harness.py`, `local_test.py`, `posture.py`, and `setup.py` are
fully covered.

## Against the v3.12.61 report

That report was 95.2% of 19260 statements, 932 missed. This tree
has 19369 statements and 883 missed. The statement
figure is 95.4%. Statements grew by 109.
Misses fell by 49.

## How to repeat

From the repo root. Use Python 3.11 or newer.

```
python3 -m pip install coverage hypothesis
python3 -m coverage run --branch --source=runner \
  --omit='*/runner/tests/*,*/runner/tools/*,*/runner/extensions/*' \
  -m unittest discover -s runner/tests -t .
python3 -m coverage report
```

Expect about nine minutes. The omit is required. The suite lives
inside `runner/`, and a run without it counts the tests as the
product.
