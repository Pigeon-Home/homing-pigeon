# Live capture: the campaign rig, 2026-10-25

Real files from a live homing-pigeon system, captured for the
documentation examples (questions file Q36). The system is the
campaign rig: a Linux VM that ran the runner under the
connector-carried campaign from 2026-10-22 to 2026-10-24.

## The rig and the run

- Runner version: **3.12.51**, first start 2026-10-22 19:09,
  last start 2026-10-24; `runner.log` spans
  2026-10-22 19:09:02 to 2026-10-24 23:18:40.
- The campaign records (`campaign-results/loop-*.json`,
  19,227 files) span 2026-10-23 05:10 UTC to
  2026-10-24 23:18 UTC.
- Modes the rig ran, per the log's startup lines: the Oracle
  in **deterministic** mode (Pi Light; set by the
  `--oracle-mode deterministic` launch flag over the config's
  `llm` value), opinion latitude `repair`, per-job
  encryption on (every envelope below is an `hp_enc` body),
  max result view `attested`, judge `advisory`, confinement
  off. Transports: email in the first era, then **file only**
  after the mail-off order of 2026-10-23, which is the era
  almost everything here comes from.
- The reports in `audit-report.txt`,
  `audit-report-since-7d.txt`, and `posture.txt` were run on
  2026-10-25 with the current tree (3.12.70) against a
  staging copy of the rig's config pointed at a copy of its
  state; the rig itself was not restarted. Both audit
  reports are empty because this rig never wrote a
  `security-audit.jsonl` (see "Not present").
- `rig-facts.txt` holds the rig's `uname -a`,
  `python3 --version`, the runner's `--version`, and one
  `resources` line with its `resources-top` line from
  `runner/tools/rig_resources.py`.

## What was scrubbed

Per the owner's rule for this capture:

- Every email address became `runner@example.test` (the
  runner's mailbox) or `si@example.test` (any other role);
  24 replacements. Test addresses already in the corpus
  (`@example.com`) were left as they were.
- Host names became `rig`, user names `runner`, and
  `/home/hatch` became `/home/runner`.
- The shared secret and every credential value in the rig's
  configs were scanned for by exact match across the whole
  capture: **none appears in any captured file**, so no
  `<redacted>` substitution was needed. (The HMAC
  signatures and `hp_enc` ciphertexts in the envelopes stay:
  they reveal nothing without the secret.)
- Lines naming a person were to be dropped; none occurred.
- The CLI captures had the capture shell's own Python
  invocation warnings removed; the staging copy of the
  config was not itself captured.

**Owner: rotate the rig's shared secret before its next
run.** The signatures and ciphertexts in this folder were
made under that secret; this capture is posted on the
understanding that the secret is rotated.

## The cut in runner.log

`runner.log` is 25,265,682 bytes on the rig. Per the
capture rule it is included as the oldest 200 KB and the
newest 2 MB with a marker line at the cut saying how much
was omitted. There are no rotated backups on this rig.

## Not present

These files from the capture list were never written by
this rig, and are absent rather than empty:

- `oracle.log`, `oracle-briefs.jsonl`, `oracle-chat.jsonl`
  (the deterministic Oracle wrote no log or briefs file;
  the Oracle record this rig actually kept is
  `oracle-learning.jsonl`, included although it was not on
  the list).
- `security-audit.jsonl`, its rotation, and
  `security-audit-counts.json`.
- `board.json`, a senses alert store, and `retained/`.
- A v2 answers folder, and question / task-offer
  envelopes: protocol v2 was off on this rig, so of the
  six envelopes asked for, the four that exist are two
  job/result pairs (the connector-carried proof job of
  2026-10-22 and one campaign job), in `envelopes/`.
- `daemon.out`, the daemon's shell capture, was not on the
  list and is not included.

## The rest

- `transport-*.txt` are file-name listings of the transport
  channel trees (38,538 names in the campaign inbox's
  `done/`, 19,264 results in its outbox, and the smaller
  extension trees), as asked: names only.
- `campaign-results/` also holds the loop's records
  themselves, all of them.
- `mutation-survivors.txt` was regenerated from the D4
  mutation reproduction's own mutant records by
  `runner/tools/mutation_floor.py`: the five names are the
  provably equivalent survivors of `runner/guard/security.py`
  (561 of 566 mutants killed).
