# The Germany rig is driving — how access was gained, and what failed (2026-10-27)

Written by Muse (stamp `00000000-muse-7e57-d0c5-58316a922026`) at
the conductor's word, after it worked. It continues
`docs/reports/germany-control-2026-10-27.md`: that file records the
door; this one records how the keys to it were obtained, what
failed on the way — including a diagnosis of Muse's that was
wrong — and the evidence that the rig's fuzzer is running. No
secret value, no Worker hostname and no host address appears in
this file. Every secret named below lives on the Muse VM in its
own file, mode 0600, beside the GitHub PAT, read at use time and
never printed; that is the whole of their handling, here as
everywhere.

## How access was gained

Administration of the rig passed from Grok to Muse on
2026-10-27, at the conductor's word. The working access arrived
in this order:

1. **The queue credential set.** Two sets were refused at the
   Worker's bearer gate (401, `{"error":"si token"}`) before any
   signature was judged. The third — the set actually deployed
   on the rig, supplied by the conductor — passed, and control
   was proven by a signed ping answered by runner
   `fedora-1gb-nbg1-1`, key `k-7e1ec001`, as the earlier report
   records.
2. **The root password, replaced.** The conductor reset the
   rig's root password at the hosting provider's panel himself
   and supplied the new value in chat; it is filed as above. The
   password it replaced is dead at the provider. Why the rotation
   could not be done by a job is under failures, below.
3. **Two API tokens, by mail.** The conductor sent Muse an API
   token for the hosting provider and an API token for
   Cloudflare, by mail to the project mailbox; both are filed as
   above, sight unseen on receipt. The hosting token is verified
   live: it reads the server's state and it issued a reboot the
   server executed (provider action recorded 2026-10-28T03:49Z).
   The Cloudflare token is held untested; the queue it would
   administer was never the problem.

Muse now holds two management planes over this rig: the hosted
queue (signed jobs, the door the earlier report describes) and
the provider API (server state and power). SSH from the Muse VM
remains refused by the Muse platform itself, before
authentication; no password has ever been presented to the host
from this side.

## What failed

- **SSH.** Outbound SSH from the Muse VM is refused by the
  platform before authentication (its egress answers in place of
  the host). Not a credential failure; the route does not exist
  from here.
- **The root password by forwarded mail.** The conductor
  forwarded a mail whose body held the password. The copy the
  mail connector returns on this side has that body protected
  out, by design; the value was not recoverable from the mail.
- **Two queue credential sets.** Refused at the bearer gate, as
  above. Stale keys do not open the door, including keys from an
  older record of the conductor's own.
- **Rotating the root password by job.** Three walls, each
  sufficient: the rig's runner predates inline job files (a file
  in the newer shape is refused, exit −2); a password generated
  on the box cannot be reported back, because the rig's result
  ceiling is the attested view, under which no output bytes
  cross; and the job sandbox cannot write the host's account
  files in any case (probed: a job runs as uid 0 inside the
  sandbox and can write neither /etc nor /root). The rotation
  was completed by the conductor's own hand at the panel.
- **Muse's diagnosis that the runner had gone silent — wrong.**
  On 2026-10-27 the rig's runner was reported to the conductor
  as stopped, on the evidence that three posted jobs returned no
  results across repeated reads. The runner's own completion
  stamps, recovered later, show all three completed at
  2026-10-28T03:06Z and 03:10Z, before either reboot. The fault
  was on Muse's side of the wire: queue result reads from this
  VM truncate in transit (Q105), and Muse's watchers discarded
  each unparseable read as an empty queue — at the worst stretch
  eighteen consecutive reads, and thirty reads to recover two
  small probe results later the same evening. An empty read is
  not evidence about the runner; that is the lesson, and it is
  recorded here because the conductor power-cycled the box and
  Muse rebooted it again through the provider API on the
  strength of the wrong diagnosis. Both reboots were harmless —
  the rig's services restart themselves, by design — and
  neither was necessary.

## The rig is driving

The conductor's question was whether the rig's fuzzer runs.
Under the attested result ceiling a job cannot return output
bytes, so the probes encode their measurement in the exit code:

- A process-count probe (exit 71 on more than 40 visible PIDs,
  lower codes for fewer) answered **71**.
- A load probe of the same round answered at the top bucket
  (host load average at or above 1.0 on a one-core box).
- After the reboots, a fresh ping was answered exit 0
  (2026-10-28T03:54Z), and two probes encoding the load average
  itself (exit code = load × 100) answered **118** for the
  one-minute average and **101** for the five-minute: **118% and
  101% of the box's one core**, with work queueing above 100%.

The fuzzer is the only workload on this rig that holds the core
at that level in steady state. Verdict: the runner answers, and
the fuzzer is driving.

## Addendum, later the same evening (2026-10-27)

Measured again at 2026-10-28T05:06Z with the same exit-code
probes: **107% and 112% of the one core** on the two readings a
second apart — about 110%, the fuzzer still driving. For the
avoidance of doubt: the 15–16% CPU figure in the conductor's
daily de_dust note of this date is the Muse VM rig's own load,
caught in the idle gap after that box's restart; it is not this
rig. This rig has read at or above saturation on every
measurement taken of it.

## Addendum, 2026-10-28: the rig banks itself

The conductor opened the SSH door from his side (Muse settings,
Permissions, Direct network protocols: ssh from Deny to Ask),
and Muse set the rig up from the shell, as the conductor had
asked in the first place:

- The GitHub PAT the conductor generated for this machine is
  planted on the box in a mode 0600 file beside grow.sh, read at
  use time, its value recorded nowhere.
- `runner/tools/rig_bank.py` (with its tests) banks the rig's
  corpus under the item 7 contract; the wrapper
  `runner/tools/rig_bank.sh` runs it. grow.sh now banks before
  its fetch and reset, and a systemd timer banks every ten
  minutes between cycles (the box has no cron).
- First bank `ebf5f6ec4`, verified at the remote from the VM:
  merged totals 1,318 entries, 4,977 arcs.
- The crash census the queue could never take, because the job
  sandbox cannot see the fuzzer's tree: the box's corpus held
  123 crash records -- queries 120, query 2, board_mail 1 --
  now banked and filed as Q106.

The rig is administered from here now on three planes: the
queue for jobs, the provider API for power and state, and SSH
for the host itself.

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->
