# The atomic file delivery race: supposition, outcome, and fix

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

## The defect, as relayed

ChatGPT's ComChat relays of 23-Nov-9:38pm-PST and 23-Nov-9:39pm-PST
report a reproduced race in the atomic file delivery landed earlier
that day. `send_job --to-file` publishes its envelope through
`runner/guard/atomicio.py`, which creates its temp file in the
destination directory under the name
`<destination>.tmp.<pid>.<thread>.<nonce>`. The file transport's
`FilePipe.scan_jobs` lists the watched inbox and processes every
regular file it finds, with no exclusion for atomicio temp names.
A scan that lands between temp creation and the final rename can
therefore consume the staging file itself.

## Supposition, written before any measurement (23-Nov-2026)

S1. Scan after temp creation, before the first write: the scan
will read the zero length temp, refuse it as a malformed envelope,
and move it into `inbox/done/`. The writer will keep writing
through its open descriptor into the moved inode, and its final
`os.replace` will raise `FileNotFoundError`. The final job path
will never appear. The sender fails and the job is lost.

S2. Scan after the temp is fully written, before the rename: the
scan will read a complete, valid envelope under the temp name and
deliver it. The rename will then succeed, and a later scan will
deliver the same job a second time under its final name: two
pending entries, one job. Duplicate enqueue at the transport
boundary, whether or not the core's replay protection later
absorbs the second execution.

S3. Of the two fixes the relay names, the evidence will support
the reserved temp name convention (option 2) over staging in a
dedicated subdirectory (option 1), for these reasons, stated
before the fix is chosen:

- Option 1 protects only the one sender that is taught to stage
  elsewhere. Every other atomicio writer that lands in a scanned
  directory (the channel's `deliver_job` writing into the runner
  inbox is the standing example of the shape) stays exposed, and
  each future writer must remember the staging rule on its own.
- Option 1 also has to create and validate a subdirectory inside
  a watched folder that other writers can plant entries in:
  permissions, a symlink planted at the staging path, and two
  senders racing to create it are new failure shapes the fix
  itself would introduce.
- Option 2 closes both interleavings for every writer that
  shares the one atomic writer, with the reserved pattern defined
  in exactly one place, in atomicio itself, and the receiver
  asking that one definition. Its cost is narrow and statable:
  a file whose name ends in the exact reserved suffix is a
  staging file and is never a job.
- The abandoned temp rule option 2 needs is the conservative
  one: the receiver never deletes a temp, however old, because
  age cannot tell a crashed writer from a slow one. The writer
  already unlinks its own temp on failure; a temp orphaned by a
  crash stays where it lies, ignored by every scan, and is safe
  to remove by hand once no writer is running.

S4. After the fix, both forced interleavings will show: neither
scan consumes or delivers the staging path, the temp stays in
place under its own name until the rename, the sender completes,
and one later scan delivers the final complete envelope exactly
once. Failure cleanup (a writer that raises mid write leaves no
temp and no destination change) and the existing file case (a
publish over a destination that already exists replaces it
whole) will stand unchanged.

## Outcome

Measured 23-Nov-2026, after the supposition above was committed,
with a deterministic harness at the real boundary: the real
`send_job.main` publishing `--to-file` into a real FilePipe
watched inbox, with the sender's own atomicio hooks wrapped so
the real `scan_jobs` ran at the exact staging moment. No sleeps.

S1 stands exactly as written. The scan after temp creation read
the zero length staging file, refused it as a malformed
envelope, and moved it into `inbox/done/` beside its refusal
note. The writer's final rename raised `FileNotFoundError`, the
final job path never appeared, and the job was lost.

S2 stands exactly as written. The scan after the write but
before the rename delivered the complete staging file; the
rename then succeeded (the sender returned success), a later
scan delivered the final file, and the pipe held 2 pending
entries and 2 channel copies for the one job.

S3 stands, and the fix follows it. Option 1 (a staging
subdirectory) was not taken: it would protect only the sender
taught to use it, it would put directory creation and symlink
validation inside a watched folder, and the channel's own
atomic writes into scanned directories would stay exposed.
The fix landed is option 2, with the convention owned by the
one place that builds the names: `runner/guard/atomicio.py`
now defines the reserved suffix exactly (a non-empty stem,
`.tmp.`, decimal pid, decimal thread id, exactly 8 lowercase
hex digits, at the end of the name) and exposes it as
`is_temp_name`; `FilePipe.scan_jobs` asks that definition and
leaves a staging file exactly where it lies, empty or complete.
The abandoned temp rule is the conservative one from S3: the
pipe never deletes a temp, the writer still unlinks its own
temp on failure, and an orphan from a crash stays ignored
under its reserved name until removed by hand with no writer
running. One neighbouring scanner was checked and needs no
change: the runner's local inbox scan takes only names ending
in `.json`, which a staging name never does.

S4 stands. After the fix, the same harness shows both
interleavings clean: neither forced scan consumes or delivers
the staging path, the sender completes, and one later scan
delivers the final complete envelope exactly once. Failure
cleanup and the existing file case stand as before, pinned by
the new tests: a failed publish leaves no temp and no final
file, a failed publish over an existing file keeps that file
byte for byte, and a publish over an existing file replaces
it whole.

The proof of work is `runner/tests/
test_atomic_file_delivery_race.py`: 12 tests covering both
forced interleavings, the abandoned temp rule for an empty
and a complete orphan, the reserved name definition and its
near misses (short, long, non hex, and uppercase nonces, a
non decimal pid or thread id, a misspelled marker, a suffix
not at the end, no stem), a near miss file processed and a
near miss malformed file refused rather than ignored, and
the failure cleanup and existing file cases. The neighbouring
suites pass on the same tree: test_atomicio,
test_transport_shells, test_transports, test_send_job_new,
test_chain_relay, and test_file_transport_operator_path at
359 tests, and test_core at 40 tests with the core figures
re-recorded for the 48 lines the fix grows the core.
