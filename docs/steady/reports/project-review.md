# Project review — homing-pigeon @ 3.13.60

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

A dated record, at the conductor's word (2026-10-26).
Baseline: main at 2642bb02 (version 3.13.60, 2026-10-26).
Headline findings: about 1,300 claims checked, about 1,180
held; the 118 that did not were 15 WRONG, 28 STALE, 6 BROKEN
COMMAND, 14 DEAD LINK, 24 MISLEADING, 31 NIT. Four findings
were in the code: an allowlisted key could run arbitrary
remote code (an allowlisted script plus a script_url passed;
fixed in ea3168e7); send_dtls.py sent cleartext by default
(fixed in ea3168e7); the wheel shipped the build tools and the
sense extensions (fixed in ea3168e7); main was red on a corpus
arc map committed out of order (fixed in 850a2d99).
