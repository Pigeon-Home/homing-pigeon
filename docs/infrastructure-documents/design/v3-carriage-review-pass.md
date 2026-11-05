# Version 3 carriage: review pass after 3.15.129

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

Decision, 2 November, after this note landed. The two defects
in section 1 are real and they are fixed. A session hold is a
sidecar beside the job (<ident>.session.txt), read back when
the email process starts, so a restart does not send the result
as ordinary mail. An expiry deletes only the holds whose result
files it just dropped, so a job that has not produced a result
yet keeps its hold. Section 10.3 of the local draft now says
the hold is kept across a restart. The tests are in
test_dtls_email_v3.py.

The defects, as found: (1) the hold lived in the email process
while the result file survived it, so a restart sent every held
session result as ordinary mail; (2) one expiry pruned every
hold that was not a surviving result file, wiping the holds of
jobs that had produced no result yet. The rest of the note was
not implemented; the standing record of the v3 carriage is now
the v3 sentence review.
