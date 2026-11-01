# Stage 5 — first slice

Stage 5's own definition of done is a test for every clause of
every checked property, plus a one-line mutation in a scratch
copy that the family catches. This file records the first slice
only. The stage is not done.

The tests are `runner/tests/test_proof_conformance.py`. They
call `handle_mail`. They do not stand in for it.

- A signature-valid cleartext job, with cleartext refused, does
  not execute, and the job id is not put in the seen set. The
  message is rejected. The id stays free, so the same job sent
  again, encrypted, is not burned.
- A body with no signature does not execute, and does not
  consume the id.
- A job whose result is already on record is answered from the
  record and does not execute. The id is recorded, because the
  resend is the delivery of the one run.
- An execution job whose interpreter is absent is repaired to
  the platform default, and that repaired interpreter is sent
  back through the key policy. When the policy allows only the
  interpreter that was absent, the repaired job is refused and
  nothing executes. This is stage 3's finding F2, pinned on the
  real path rather than on a patched plan.

Four tests. They pass. The clause-by-clause family, the
audience modes, the caps at either side, and the scratch-copy
mutation check are still ahead.
