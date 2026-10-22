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

## After the rejection tests

Measured again the same day. 4442 tests, OK, 22 skipped,
370 seconds.

Statements: 16872. Missed: 962. Covered: 94.3%.
Branches: 91.3%. Together: 93.4%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| winlog.py | 88% | 100% | 0 |
| detection.py | 82% | 94% | 11 |
| extensions.py | 91% | 96% | 8 |
| learning.py | 84% | 88% | 48 |
| oauth.py | 85% | 89% | 24 |
| dri.py | 91% | 92% | 30 |

What this pass pins: a detection rule or plan that is not the
shape the checker expects; a baseline file that is not JSON;
a new job kind after the count has junk in it; a refresh and
a code exchange that come back as a non-object or without a
token; a DRI number that is not a number, including infinity;
a transport manifest with no entry, a huge argv item, or a
publisher that is two lines; a ledger that grows past 5000
lines and keeps the last 4000; the Windows event source
pointing at `EventCreate.exe` with types 7.

The extension programs are still 74% to 79%. That is the
floor until there is a real socket. `transports.py` is 84%
and `dtlsproto.py` is 88%, and both are still the handshake.

## After the channel and ledger tests

Measured again the same day. 4456 tests, OK, 22 skipped,
367 seconds.

Statements: 16872. Missed: 897. Covered: 94.7%.
Branches: 92.0%. Together: 93.9%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| learning.py | 88% | 96% | 16 |
| transports.py | 84% | 90% | 56 |
| oauth.py | 89% | 90% | 21 |
| dri.py | 92% | 93% | 27 |

What this pass pins: the learning switches take `yes` and
`off`, and a number that is not a number stays at the
default. Each feature kind (interpreter, tool, path,
pathshape) has a claim, and today's probe wins when it
disagrees. A torn ledger line and a record with no host are
skipped. A result id is taken from the job subject when the
channel has no hint, and a slash in that id is not a path. A
file that changes between the two reads is left in the inbox.
A result that does not land is not consumed, and a rollback
or an ack that raises is logged rather than stopping the
other message. A DTLS secret file is read, and an inline
secret wins over the file of the same key. `oauth`'s command
refuses a symlink config and a token with a newline.

`transports.py` is now 90%. What is left there is the child
process supervisor. `dtlsproto.py` is still the handshake,
at 88%. The extension programs are still 74% to 79%.

## After the supervisor tests

Measured again the same day. 4468 tests, OK, 22 skipped,
363 seconds.

Statements: 16872. Missed: 850. Covered: 95.0%.
Branches: 92.2%. Together: 94.2%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| transports.py | 90% | 96% | 24 |
| learning.py | 96% | 97% | 10 |
| oauth.py | 90% | 93% | 15 |

What this pass pins: a refresh that succeeds returns the
access token, and a token write that fails does not leave
the token in the config. A reconciliation that cannot be
written returns nothing, so learning does not block the
result. A candidate about a different tool is not scored.
A repeated feature is stored once. A broken extension
folder is logged and the shipped transport still starts. A
frozen build rewrites `-m` into `--transport-extension-module`.
A child that has been up for a minute has its restart count
cleared. An unreadable inbox does not hold startup. The log
pump skips a blank line, reopens a sidecar that closed under
it, and keeps draining when the log call or the pipe raises.
A process that will not die is killed, and a wait that runs
out returns false. The same config reuses one supervisor.
A symlink job and an oversize job are refused unread, and
an ack of a file that cannot be moved is logged.

`dtlsproto.py` is still the handshake, at 88%. The extension
programs are still 74% to 79%.

## After the profile refusal tests

Measured again the same day. 4479 tests, OK, 22 skipped,
367 seconds.

Statements: 16872. Missed: 811. Covered: 95.2%.
Branches: 92.6%. Together: 94.5%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| dtlsproto.py | 88% | 90% | 109 |
| transports.py | 96% | 98% | 11 |
| learning.py | 97% | 99% | 5 |

What this pass pins: an X25519 input that is not 32 octets,
and the all-zero shared secret from a zero point, which the
profile aborts. An extension block with a short header, an
overrun, or a duplicate type is refused by name. A key share
and a PSK extension that are cut short are refused. An empty
additional secret is not a name. A flight nobody answers for
60 seconds is abandoned. An application message past the cap
is refused, and a short one waits. A KeyUpdate of the wrong
shape is dropped; one that asks for a reply is answered and
ratchets both directions. A channel file that cannot be read
is refused. A child that cannot be started is logged and
stopped without a kill. An inbox that already has a job does
not hold startup. The log pump drops a poisoned line and a
sidecar that will not reopen. A ledger trim that cannot
replace the file leaves the old ledger in place.

What is left in `dtlsproto.py` is the rest of the two
handshake state machines, not the parsers. The extension
programs are still 74% to 79%.

## After the handshake refusal tests

Measured again the same day. 4489 tests, OK, 22 skipped,
370 seconds.

Statements: 16872. Missed: 734. Covered: 95.6%.
Branches: 93.4%. Together: 95.0%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| dtlsproto.py | 90% | 97% | 33 |

What this pass pins, through the real client and server
cores: a ServerHello that picks a foreign suite, a foreign
version, a foreign group, or that does not accept the PSK.
A HelloRetryRequest with no cookie. A Finished that does
not verify, which kills the client. A fatal alert in either
direction. Application data before our Finished. A
handshake fragment that is reassembled, and a second
EncryptedExtensions that is not added to the transcript
again. A greeting that is not JSON. A ClientHello whose
X25519 share is the zero point: the binder matches and the
server still drops the session it had started to register.
A first flight that is an alert, a fragment, a ServerHello,
or a malformed ClientHello. A replayed cookie-bearing
hello, answered with the same flight and no new keys. A
datagram that claims more bytes than it has. An empty
inner plaintext. A dead session and an expired ticket,
removed on the next tick.

Thirty-three statements remain in `dtlsproto.py`. Two of
them are the X25519 clamp, which forces the last swap bit
off, so that branch cannot run. The rest are a few server
checks a well-formed hello never reaches (an unknown
identity that still has a matching binder, a Finished that
fails on the server side). The extension programs are still
74% to 79%.

## After the server checks

Measured again the same day. 4492 tests, OK, 22 skipped,
368 seconds.

Statements: 16872. Missed: 712. Covered: 95.8%.
Branches: 93.6%. Together: 95.2%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| dtlsproto.py | 97% | 99% | 9 |

The previous pass asserted "an alert came back" and several
checks returned one before the line under test. The key
share in those hellos was two bytes short, so the parser
refused them first. This pass builds a share the parser
accepts, and checks the alert code.

What it pins: no PSK modes is a missing extension. No key
share, a key share that does not parse, and a group that is
not X25519 are illegal. No pre-shared key is a missing
extension. A PSK block that does not parse, or that names
no identity, is illegal. An identity the server does not
have is a handshake failure, and the log says so. An
expired resumption ticket falls through to the external
secret, and a binder longer than the hello is a decrypt
error. Application data before the session is up is
dropped. A client Finished that does not verify kills the
server session and sends an alert. A cookie extension
shorter than its length field is dropped, and a cookie of
the wrong size is ignored. A handshake header that claims
100 bytes and carries none does not parse. A second
Finished on a live session is ignored. A KeyUpdate on the
server is answered.

Nine statements remain. Two are the X25519 clamp, which
cannot run. The extension programs are still 74% to 79%.

## After the file-pipe refusals

Measured again the same day. 4498 tests, OK, 22 skipped,
364 seconds.

Statements: 16872. Missed: 683. Covered: 96.0%.
Branches: 93.7%. Together: 95.3%.

| File | Before this pass | After | Missed after |
|---|---:|---:|---:|
| transport_extensions/file/__main__.py | 79% | 99% | 2 |

The file pipe is a watched folder, so these do not need a
broker or a socket. A file that is not UTF-8 is refused and
the reason is written beside it. A file that disappears
between the listing and the stat is refused the same way.
A refusal whose note cannot be written still moves the job
into done/. A refusal that cannot move the job leaves the
file in the inbox. A result body with no trailing newline
gets one. A seen-mark that cannot be written is not fatal.
`main` with no channel directory returns 2. A pass that
throws is logged, and the loop sleeps instead of dying.

Two lines remain: the script entry, and the results scan
on a pass whose jobs scan already threw.








