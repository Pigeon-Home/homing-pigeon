# Coverage findings

This report belongs to package 3.12.61. The previous measurement is
[v3.12.20](../v3.12.20/coverage.md). No new tag was cut for this
measurement. It is main at 891bbd8. The runner modules sit in
`oracle/`, `wire/`, `guard/`, and `ops/`.

## Current status

Measured 2026-10-24 with coverage.py 7.16.2, on Python 3.11.2.
Hypothesis 6.170.3 was installed. CI pins hypothesis 6.170.5.
5426 tests, 1 failure, 22 skipped. 453 seconds.

The failure is `test_all_eight_shapes` variant `hostinfo`: the
script exited 127, a command was not found on this machine. The
other seven shapes passed. The 22 skips are optional tools that
were not installed here.

| | Covered | Missed | Total |
|---|---:|---:|---:|
| Statements | 95.2% | 932 | 19260 |
| Branches | 92.7% | 573 | 7842 |
| Statements and branches | 94.4% | | |

`runner/tests/`, `runner/tools/`, and `runner/extensions/` are
left out of `--source`. The suite and the CI scripts are the
measurement, not the subject. The shipped extensions used to live
in `extensions/`, outside `--source=runner`, and they still do
not count. `runner/cloud/` does count. Without those two files
the statement figure is 96.0% (745 missed of 18812)
and statements-and-branches is 95.4%.

The files still under 96%, by statements:

| File | Covered | Missed |
|---|---:|---:|
| cloud/send_dtls.py | 36.6% | 97 |
| cloud/send_job.py | 69.5% | 90 |
| transport_extensions/nats/__main__.py | 79.8% | 46 |
| transport_extensions/dtls/__main__.py | 81.5% | 33 |
| transport_extensions/email/__main__.py | 85.4% | 18 |
| wire/platformcard.py | 88.6% | 5 |
| ops/extsources.py | 90.7% | 129 |
| oracle/resources.py | 92.8% | 14 |
| ops/auditreport.py | 93.5% | 15 |
| guard/security.py | 93.5% | 15 |
| guard/confval.py | 94.0% | 3 |
| wire/mailbox.py | 94.2% | 11 |
| oracle/detection.py | 94.3% | 10 |
| wire/oauth.py | 94.4% | 13 |
| wire/verify.py | 95.0% | 23 |
| oracle/dri.py | 95.1% | 20 |
| wire/board.py | 95.5% | 13 |
| wire/protocol_v2.py | 95.8% | 15 |
| runner.py | 95.8% | 271 |

`runner.py` is 95.8% (271 missed of 6388).
The floor is the two cloud helpers. The transport programs that
open a socket or a broker are still the low end of the runner
itself.

## Text chart

Statement coverage, 40 cells, one cell is 2.5 points.

```
all              95.2  [######################################..]

send_dtls.py      36.6  [###############.........................]
send_job.py       69.5  [############################............]
nats ext          79.8  [################################........]
dtls ext          81.5  [#################################.......]
email ext         85.4  [##################################......]
platformcard.py   88.6  [###################################.....]
extsources.py     90.7  [####################################....]
resources.py      92.8  [#####################################...]
auditreport.py    93.5  [#####################################...]
security.py       93.5  [#####################################...]
confval.py        94.0  [######################################..]
mailbox.py        94.2  [######################################..]
detection.py      94.3  [######################################..]
oauth.py          94.4  [######################################..]
verify.py         95.0  [######################################..]
dri.py            95.1  [######################################..]
board.py          95.5  [######################################..]
protocol_v2.py    95.8  [######################################..]
runner.py         95.8  [######################################..]
jobcrypto.py      96.1  [######################################..]
personal_docs.py  96.5  [#######################################.]
senses.py         97.4  [#######################################.]
channel.py        98.0  [#######################################.]
review.py         98.1  [#######################################.]
learning.py       98.2  [#######################################.]
install.py        98.2  [#######################################.]
extensions.py     98.5  [#######################################.]
file ext          98.6  [#######################################.]
transports.py     98.9  [########################################]
sandbox.py        99.1  [########################################]
dtlsproto.py      99.3  [########################################]
opinion.py        99.4  [########################################]
remediation.py    99.6  [########################################]
harness.py       100.0  [########################################]
local_test.py    100.0  [########################################]
posture.py       100.0  [########################################]
setup.py         100.0  [########################################]
textutil.py      100.0  [########################################]
winlog.py        100.0  [########################################]
```

`runner/__init__.py` and `runner/_version.py` are one or two
statements and fully covered. So are `harness.py`, `local_test.py`,
`posture.py`, and `setup.py`, under `ops/`.

## Against the v3.12.20 report

That report's later figure was 96.8% of 16872 statements, 546
missed. This tree has 19260 statements and 932 missed.
The percent is 95.2.

The two cloud helpers were not in that measurement. They live in
the package now, and they are most of the new miss. The rest of
the tree is the same kind of number as that report.

## How to repeat

From the repo root, with coverage.py installed. It is a
measurement tool, not a project dependency. Install hypothesis
first if you want the property tests; CI does. Use Python 3.11
or newer.

```
python3 -m pip install coverage hypothesis
python3 -m coverage run --branch --source=runner \
  --omit='*/runner/tests/*,*/runner/tools/*,*/runner/extensions/*' \
  -m unittest discover -s runner/tests -t .
python3 -m coverage report
```

Expect about eight minutes. The omit is required. The suite now
lives inside `runner/`, and a run without it counts the tests as
the product.
