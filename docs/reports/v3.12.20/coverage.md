# Coverage findings

This report belongs to package 3.12.20. The previous measurement is
[v3.11.1](../v3.11.1/coverage.md). No new tag was cut for this
measurement. The tree measured is main at baddf66 (`Update FAQs.md`).
The package version in that tree is 3.12.20.

## Text chart

Statement coverage, 40 cells, one cell is 2.5 points.

```
all             93.4  [#####################################...]

dtls ext         74.2  [##############################..........]
email ext        74.4  [##############################..........]
nats ext         77.5  [###############################.........]
protocol_v2.py   78.7  [###############################.........]
file ext         78.9  [################################........]
detection.py     82.3  [#################################.......]
transports.py    83.7  [#################################.......]
learning.py      84.1  [##################################......]
oauth.py         85.4  [##################################......]
personal_docs.py  85.5  [##################################......]
dtlsproto.py     87.6  [###################################.....]
winlog.py        88.2  [###################################.....]
extensions.py    91.1  [####################################....]
dri.py           91.4  [#####################################...]
resources.py     92.5  [#####################################...]
auditreport.py   93.5  [#####################################...]
security.py      93.5  [#####################################...]
mailbox.py       94.1  [######################################..]
senses.py        94.9  [######################################..]
runner.py        95.1  [######################################..]
jobcrypto.py     96.1  [######################################..]
channel.py       96.6  [#######################################.]
install.py       98.7  [#######################################.]
sandbox.py       99.1  [########################################]
opinion.py       99.4  [########################################]
review.py        99.4  [########################################]
remediation.py   99.6  [########################################]
harness.py      100.0  [########################################]
local_test.py   100.0  [########################################]
posture.py      100.0  [########################################]
setup.py        100.0  [########################################]
```

`runner/__init__.py` and `runner/_version.py` are one or two
statements each and fully covered. They are not on the chart.
`channel.py` is `transport_extensions/channel.py`. The four `ext`
rows are the transport extension programs (`dtls`, `email`, `file`,
`nats`).

Measured 2026-10-22 with coverage.py 7.16.2, on Python 3.11.2.
Hypothesis 6.170.3 was installed, which is what CI does.

```
python3 -m coverage run --branch --source=runner -m unittest discover -s tests -t .
```

4401 tests, OK, 22 skipped, 370 seconds under coverage.
The skips are optional tools that were not installed here.

Statements: 16872. Missed: 1107. Covered: 15765. Covered: 93.4%.
Branches: 6840. Covered: 6163 (90.1%). Missing: 677, of which
583 are only partly taken.
Statement and branch together, the number `coverage report`
prints: 92.5%.

The 93.4% is statement coverage, the same kind of number as the
94.2% in the v3.11.1 report. That report's together figure was
93.1%. This run's together figure is 92.5%.

## Against 19 October

The v3.11.1 report was 94.2% (15326 statements, 890 missed,
3979 tests). Covered statements went from 14436 to 15765.
The tree grew by 1546 statements. Misses rose by 217.
The percent fell by 0.8 points. The new code is covered, and
a few files that were nearly full grew holes.

| File | 19 Oct | Now | Missed now |
|---|---:|---:|---:|
| channel.py | 68% | 97% | 3 |
| dtlsproto.py | 83% | 88% | 135 |
| runner.py | 97% | 95% | 340 |
| install.py | 99.9% | 98.7% | 23 |
| transports.py | 83% | 84% | 88 |
| learning.py | 82% | 84% | 62 |
| detection.py | 82% | 82% | 32 |
| oauth.py | 85% | 85% | 31 |
| winlog.py | 88% | 88% | 4 |
| dri.py | 91% | 91% | 34 |

`channel.py` was the bottom of the last chart (28 missed).
Three statements remain.

`dtlsproto.py` was the largest hole (177 missed). It is 135
now. The handshake is still the body of what is left.

`runner.py` grew from 6343 statements and 175 missed to 6908
statements and 340 missed. The percent fell from 97.2 to 95.1.
The new misses sit in the paths added since 3.11.1, not in
the old core.

`install.py` grew with host classification. Twenty-three
statements missed. The ones that matter are the USB sysfs
scan, which this machine does not have, and the import
fallback if `personal_docs` cannot be loaded. The scan is
covered when the facts are passed in. The sysfs walk itself
is not.

`harness.py`, `posture.py`, `local_test.py`, and `setup.py`
are still fully covered. `remediation.py` missed 3.
`sandbox.py` missed 1. Both were 100% on 19 October.

## What is new, and still open

| File | Now | Missed |
|---|---:|---:|
| protocol_v2.py | 79% | 75 |
| personal_docs.py | 86% | 25 |
| dtls extension | 74% | 42 |
| email extension | 74% | 32 |
| nats extension | 78% | 47 |
| file extension | 79% | 30 |

`protocol_v2.py` was not on the last chart. Seventy-five
statements missed, the lowest file that is part of the
runner rather than a supervised extension. The misses are
the long job-id digest, the overflow answer file
(`.more.jsonl`), and the read errors around it. The happy
path of a normal-length id is covered. Two ids that differ
only past the old 120-character cut are not.

`personal_docs.py` is the install-time warning. Twenty-five
statements missed. They are the XDG `user-dirs.dirs` parser,
a symlink, a directory that will not scan, and the depth
cap. The ordinary home scan is covered. A relocated
Documents folder, and a folder that leaves home, are not.

The four extension programs are still the low end, for the
same reason as last time. They are processes the runner
supervises. A unit test that stands up a live NATS or a
live DTLS peer is the wrong fix for the parts that only
fail on a real socket.

`jobcrypto.py` still misses seven statements. That is not
the hole.

## How to repeat

From the repo root, with coverage.py installed. It is a
measurement tool, not a project dependency. Install hypothesis
first if you want the property tests; CI does. Use Python 3.11
or newer. `tomllib` is not on 3.10, and a 3.10 run errors
tests before it finishes.

```
python3 -m pip install coverage hypothesis
python3 -m coverage run --branch --source=runner -m unittest discover -s tests -t .
python3 -m coverage report
```

Expect about six minutes. Do not treat 93.4% as a target.
The number moved because `runner.py` grew and `protocol_v2.py`
is only partly walked. The hole worth a test is the v2
long-id and overflow-answer path, and the XDG branch of the
personal-documents warning. Not another point on the old core,
and not the extension programs.

## After the edge tests

Measured again the same day, same command, after tests for
the two holes named above. 4425 tests, OK, 22 skipped,
363 seconds.

Statements: 16872. Missed: 1038. Covered: 15834. Covered: 93.8%.
Branches: 90.7%. Together: 92.9%.

| File | Before | After | Missed after |
|---|---:|---:|---:|
| protocol_v2.py | 79% | 95% | 18 |
| personal_docs.py | 86% | 96% | 7 |

What the new tests actually pin: two job ids that share a
109-character prefix and differ after it do not share a
question slot; a ninth late answer and a repeated one are
dropped; a junk line in the late file is skipped; a slot
that is not an answer does not keep the answer; an answer
already on disk ends the outbox wait. The warning now pins
a phrase (`bank-statement`, `health_records`), `node_modules`
and a dotfile, the 2000-entry cap, an XDG file full of
comments and a path that leaves home, and a folder that
will not scan.

What is left in those two files is the crash-recovery race
in the answer publish, and `is_dir` raising. Those are not
the next hole. The extension programs are still 74% to 79%.

