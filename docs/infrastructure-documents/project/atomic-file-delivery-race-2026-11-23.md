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

(To be filled in after the reproduction and the fix, in this
same place, against the suppositions above.)
