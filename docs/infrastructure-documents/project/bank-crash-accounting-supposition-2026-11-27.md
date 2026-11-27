# Bank crash accounting: supposition

Written 2026-11-27, before the measurements below were run. The
conclusions section is appended after the measurements, in this
same place, and the change the numbers support follows it.

## What stands

Germany bank 77 (landed 2026-11-27) states in its commit
message: "Crashes filed in this bank: 7244." The banks before
it filed 0. The review question the number raises is plain: are
the 7,244 distinct findings, or repeated echoes of crash
families already on file? The bank's own message cannot answer
it today, because the figure it prints is not a count of filed
records at all.

## How the number is made today

`runner/tools/rig_bank.py` builds the figure in `commit_message`
and again in `ledger_block` as the sum of the `crashes`
counters of the bank's new run records. A run record's counter
is `len(session.crashes)` in `runner/tools/de_dust_corpus.py`:
every crashing child the session ran, counted each time it ran,
including the same input crashing again in a later round. The
grow files a crash only when its id is new (`_record_crashes`
skips a record whose id is already known), so the corpus's
`<target>.crashes.jsonl` files grow by distinct findings only.
The bank merge counts those distinct additions per file in its
report and then never prints them. The one number the bank does
print is the event sum, under the word "filed".

A second mixing sits beside it: the merge report's `crashes`
key holds additions from `.crashes.jsonl` files and from
`.slow.jsonl` files together, so even the unprinted count cannot
separate a crash finding from a slow finding.

## The suppositions

S1. Bank 77's 7,244 is the event sum over its 4,664 new run
records, and the same commit added no lines to any
`<target>.crashes.jsonl` file, so the distinct new crash
findings bank 77 filed number 0 and every one of the 7,244
events re-hit a record already on file. Checked by summing the
`crashes` counters of the run records the bank commit added and
by reading that commit's per-file line counts.

S2. The fix the numbers support, if S1 holds: the bank states
both numbers wherever it reports crashes, in the commit message
and in the ledger block. Distinct crash records filed, counted
from the merge over `.crashes.jsonl` files only, with slow
records counted apart. Crash events, the run counter sum,
stated as events. The subject line carries the filed count,
because the subject is what gets read in the commits list.

S3. The corpus replay cost, raised in the same review: the
combined de_dust and rig bank suites now run past 600 seconds
on a loaded box. The supposition is that the wall time is the
replay itself, each committed entry run against its reader,
once on the host surface and once on the simulated Windows
surface, and that repeated parsing of the corpus files inside
one test process is a minority share, under 15 percent of the
total. Checked by timing the family module by module and by
timing a parse-only pass over the same files. If the parse
share comes out large instead, a load cache in the tool is the
change the numbers support. If it comes out small, the numbers
support no structural change to the suite: the cost is the
contract work, and the honest move is to record that here and
size review timeouts to it.
