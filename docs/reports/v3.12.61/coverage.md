# Coverage findings

This report belongs to package 3.12.61. The previous measurement is
[v3.12.20](../v3.12.20/coverage.md). No new tag was cut for this
measurement. It is main at e218d9f (`Move extensions/ into
runner/extensions`), which is after the v3.12.61 tag.

## Current status

Measured 2026-10-24 with coverage.py 7.16.2, on Python 3.11.2.
Hypothesis 6.170.3 was installed. CI pins hypothesis 6.170.5.
5398 tests, 1 failure, 22 skipped. 452 seconds.

The failure is `test_all_eight_shapes` variant `hostinfo`: the
script exited 127, a command was not found on this machine. The
other seven shapes passed. The 22 skips are optional tools that
were not installed here.

| | Covered | Missed | Total |
|---|---:|---:|---:|
| Statements | 95.1% | 935 | 19258 |
| Branches | 92.7% | 574 | 7842 |
| Statements and branches | 94.4% | | |

`runner/tests/`, `runner/tools/`, and `runner/extensions/` are
left out of `--source`. The suite and the CI scripts are the
measurement, not the subject. The shipped extensions used to live
in `extensions/`, outside `--source=runner`, and they still do
not count. `runner/cloud/` does count now: it moved into the
package. Without those two files the statement figure is 96.0%
(748 missed of 18810) and statements-and-branches is 95.4%.

The files still under 96%, by statements:

| File | Covered | Missed |
|---|---:|---:|
| cloud/send_dtls.py | 36.6% | 97 |
| cloud/send_job.py | 69.5% | 90 |
| transport_extensions/nats/__main__.py | 79.8% | 46 |
| transport_extensions/dtls/__main__.py | 81.5% | 33 |
| transport_extensions/email/__main__.py | 85.4% | 18 |
| platformcard.py | 88.6% | 5 |
| extsources.py | 90.7% | 129 |
| resources.py | 92.8% | 14 |
| oauth.py | 93.1% | 16 |
| auditreport.py | 93.5% | 15 |
| security.py | 93.5% | 15 |
| confval.py | 94.0% | 3 |
| mailbox.py | 94.2% | 11 |
| detection.py | 94.3% | 10 |
| dri.py | 95.1% | 20 |
| verify.py | 95.2% | 22 |
| board.py | 95.5% | 13 |
| protocol_v2.py | 95.8% | 15 |
| runner.py | 95.8% | 268 |

`runner.py` is 95.8% (268 missed of 6388). The floor is
`cloud/send_dtls.py` at 36.6% and `cloud/send_job.py` at 69.5%.
They are the cloud-side helpers. The three extension programs
still sit in the 80s, for the same reason as the last report:
they open a socket or a broker. `extsources.py` is 90.7% (129
missed of 1391).

## Text chart

Statement coverage, 40 cells, one cell is 2.5 points.

```
all              95.1  [######################################..]

cloud/send_dtls.  36.6  [###############.........................]
cloud/send_job.p  69.5  [############################............]
nats ext          79.8  [################################........]
dtls ext          81.5  [#################################.......]
email ext         85.4  [##################################......]
platformcard.py   88.6  [###################################.....]
extsources.py     90.7  [####################################....]
resources.py      92.8  [#####################################...]
oauth.py          93.1  [#####################################...]
auditreport.py    93.5  [#####################################...]
security.py       93.5  [#####################################...]
confval.py        94.0  [######################################..]
mailbox.py        94.2  [######################################..]
detection.py      94.3  [######################################..]
dri.py            95.1  [######################################..]
verify.py         95.2  [######################################..]
board.py          95.5  [######################################..]
protocol_v2.py    95.8  [######################################..]
runner.py         95.8  [######################################..]
jobcrypto.py      96.1  [######################################..]
personal_docs.py  96.5  [#######################################.]
senses.py         97.4  [#######################################.]
transport_extens  98.0  [#######################################.]
review.py         98.1  [#######################################.]
learning.py       98.2  [#######################################.]
install.py        98.3  [#######################################.]
extensions.py     98.5  [#######################################.]
file ext          98.6  [#######################################.]
dtlsproto.py      98.7  [#######################################.]
transports.py     98.9  [########################################]
sandbox.py        99.1  [########################################]
opinion.py        99.4  [########################################]
remediation.py    99.6  [########################################]
winlog.py        100.0  [########################################]
textutil.py      100.0  [########################################]
local_test.py    100.0  [########################################]
setup.py         100.0  [########################################]
posture.py       100.0  [########################################]
harness.py       100.0  [########################################]
```

`runner/__init__.py`, `runner/_version.py`, `textutil.py`, and
`winlog.py` are small and fully covered. `harness.py`,
`local_test.py`, `posture.py`, and `setup.py` are fully covered.
`remediation.py` missed 3 (99.6%).

## Against the v3.12.20 report

That report's later figure was 96.8% of 16872 statements, 546
missed. This tree has 19258 statements and 935 missed. Statements
grew by 2386. Misses grew by 389. The percent fell by 1.7 points.

Most of the new miss is the two cloud helpers, which the old
measurement did not include. Leave them out and the statement
figure is 96.0%, 0.8 points under that report, on a larger tree.

| File | 3.12.20 | Now | Missed now |
|---|---:|---:|---:|
| transport_extensions/dtls/__main__.py | 74.2% | 81.5% | 33 |
| transport_extensions/email/__main__.py | 74.4% | 85.4% | 18 |
| transport_extensions/nats/__main__.py | 77.5% | 79.8% | 46 |
| resources.py | 92.5% | 92.8% | 14 |
| oauth.py | 92.9% | 93.1% | 16 |
| auditreport.py | 93.5% | 93.5% | 15 |
| security.py | 93.5% | 93.5% | 15 |
| mailbox.py | 94.1% | 94.2% | 11 |
| dri.py | 94.9% | 95.1% | 20 |
| detection.py | 95.6% | 94.3% | 10 |
| runner.py | 96.6% | 95.8% | 268 |

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
