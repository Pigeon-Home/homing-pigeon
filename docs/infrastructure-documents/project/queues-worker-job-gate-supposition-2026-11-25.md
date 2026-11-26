<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

# The queues Worker job gate and the encrypted envelope: supposition

Written 2026-11-25, before the measurement below was run. The
conclusions section is appended after the measurement, in this
same place, and the change the numbers support follows it.

## What stands

The Anna pipe build lane of 2026-11-25 found, twice, in its
staging proof, that the shipped queues Worker refuses the
protocol's default encrypted job. The composer's queue posting
without the cleartext flag, the form that carries the job inside
an hp_enc envelope, came back with a 400 answer and the error
text "job_id mismatch between subject and body". The lane's
record stands in the Anna pipe design document and in the
build record outside this repository. The owner has ordered
the recommended fix landed.

The code reading agrees with the report. The job posting gate
in runner/cloud/queues-worker/src/index.js compares the signed
payload's job_id member against the subject's id, through a
reader that returns undefined when the member is absent, and
refuses whenever the two differ. An hp_enc envelope carries no
job_id member at the payload level, because the whole job,
job_id included, sits inside the encryption. The reader
therefore returns undefined for every encrypted job, undefined
differs from every subject id, and every encrypted job is
refused. The results route in the same file already carries
the correct treatment: it reads the payload's claimed id with
a reader that reports absence as absence, and it refuses only
when a claim is present and differs. Absent is not a claim.

## The supposition

The supposition, recorded before any measurement: posting a
correctly signed job whose payload is an hp_enc envelope to
the shipped Worker's job route returns 400 with the mismatch
error and stores nothing, while the same job in signed
cleartext with a matching job_id returns 202 and is stored.
Giving the job gate the results route's treatment will flip
exactly the first of those answers and no other: the encrypted
envelope will be accepted and stored under the subject's id,
a present claim that differs will still be refused, a present
claim that is not a string will still be refused, a matching
claim will still be accepted, and a payload with no job_id
member and no encryption will still be accepted, because
absence was never a claim on either route.

## The decision rule

If the measurement shows the encrypted refusal and the
cleartext acceptance exactly as supposed, the fix lands: the
job gate reads the payload's job_id claim the way the results
route reads its claims, and refuses only a present claim that
differs from the subject's id. A family of unit tests in the
Worker's own test suite pins the gate's answers across the
claim shapes: the encrypted envelope, the encrypted shape
beside a differing claim, the absent claim, the matching
claim, the differing claim, and the claims that are present
and not strings. If the measurement shows anything else, the
fix does not land on this supposition, and the evidence is
reported instead.

## Conclusions

(Appended after the measurement.)
