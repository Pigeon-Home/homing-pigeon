# Findings — docs/steady/sending.md

Source: docs/steady/sending.md, reviewed at main 5544befc.
Sentence units: 103. Flagged: 5. Categories: pre-release 103, post-release 0.

The sender's manual: platform first, the clock job, the rules of thumb earned live, the remote upgrade in its 2 halves, and the sender's options. The prose is procedural and connected; the flags are the units that stand outside the sentence flow.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The runner is SI-agnostic: anything that can send…" | pre-release | flows |  |
| 2 | "The SI needs the `shared_secret` string from your…" | pre-release | flows |  |
| 3 | "Then:" | pre-release | flagged | A 1-word lead-in ("Then:") with no sentence shape; the steps it announces arrive as separate items |
| 4 | "A job's script is written for the runner's…" | pre-release | flows |  |
| 5 | "So before sending anything, establish which platform the…" | pre-release | flows |  |
| 6 | "**Guess from context when you can.** The machine…" | pre-release | flows |  |
| 7 | "**When nothing gives it away,** the common cases…" | pre-release | flows |  |
| 8 | "Treat that as a starting guess, not a…" | pre-release | flows |  |
| 9 | "**When you do not know, ask the owner**…" | pre-release | flows |  |
| 10 | "One question up front is cheaper than a…" | pre-release | flows |  |
| 11 | "Once a runner has answered anything, its platform…" | pre-release | flows |  |
| 12 | "Write it down; do not ask twice." | pre-release | flows |  |
| 13 | "The standard first job to a new runner…" | pre-release | flows |  |
| 14 | "The runner runs it on its platform default,…" | pre-release | flows |  |
| 15 | "Compare the epoch with your own clock: a…" | pre-release | flows |  |
| 16 | "Do not name the interpreter by an absolute…" | pre-release | flows |  |
| 17 | "`--interpreter '["/bin/sh"]'` looks harmless and is not: the…" | pre-release | flows |  |
| 18 | "Omit `--interpreter` and let the runner use its…" | pre-release | flows |  |
| 19 | "This was learned live on 31 Oct 2026:…" | pre-release | flows |  |
| 20 | "Once the clock reads true, the natural next…" | pre-release | flows |  |
| 21 | "This example ran live on a fresh Windows…" | pre-release | flows |  |
| 22 | "Three rules of thumb, all earned the same…" | pre-release | flows |  |
| 23 | "**Assume a bare machine.** The runner's executable carries…" | pre-release | flows |  |
| 24 | "The job brings what it needs: here a…" | pre-release | flows |  |
| 25 | "**Declare what your tools carry.** The runner scans…" | pre-release | flows |  |
| 26 | "The portable git's sample ssh client configuration names…" | pre-release | flows |  |
| 27 | "The script declares the three paths in its…" | pre-release | flows |  |
| 28 | "Before sending a new job shape, rehearse it:…" | pre-release | flows |  |
| 29 | "**Produce only what the job needs.** A full…" | pre-release | flows |  |
| 30 | "The job checks out sparsely — only the…" | pre-release | flows |  |
| 31 | "The credential for the push travels as a…" | pre-release | flows |  |
| 32 | "Sent with no interpreter field (PowerShell is the…" | pre-release | flows |  |
| 33 | "A runner can be upgraded remotely by anyone…" | pre-release | flows |  |
| 34 | "The procedure is a part of the software…" | pre-release | flows |  |
| 35 | "It was first run end to end on…" | pre-release | flows |  |
| 36 | "It has two halves, because a confined job…" | pre-release | flows |  |
| 37 | "**The job half (the secret-holder's side).** Send one…" | pre-release | flows |  |
| 38 | "The runner itself downloads its input files before…" | pre-release | flows |  |
| 39 | "The tarball is about 91 MB; the runner's…" | pre-release | flows |  |
| 40 | "The job's script then checks the tarball against…" | pre-release | flows |  |
| 41 | "`set -eu` matters: without it a failed download…" | pre-release | flows |  |
| 42 | "**The host half (installed once by the owner).**…" | pre-release | flagged | A bold label standing alone as its own paragraph; the host half's first sentence arrives in the next unit with no hand-off |
| 43 | "The timer runs the applier every minute (the…" | pre-release | flows |  |
| 44 | "The applier finds the newest triggered payload, fetches…" | pre-release | flows |  |
| 45 | "The outcome is written to `outcome.txt` in the…" | pre-release | flows |  |
| 46 | "Four things the first run earned, all handled…" | pre-release | flows |  |
| 47 | "The installer for a box that runs the…" | pre-release | flows |  |
| 48 | "The frozen installer leaks its bundled OpenSSL into…" | pre-release | flows |  |
| 49 | "The applier puts small wrapper scripts for `systemctl`…" | pre-release | flows |  |
| 50 | "Give the installer a disk-backed TMPDIR (the applier…" | pre-release | flows |  |
| 51 | "A small or full /tmp breaks it twice:…" | pre-release | flows |  |
| 52 | "A /tmp full of old rig debris (450…" | pre-release | flows |  |
| 53 | "The installer re-stamps the config's profile (it applied…" | pre-release | flows |  |
| 54 | "The applier records the profile before the install…" | pre-release | flows |  |
| 55 | "A remote upgrade also re-arms the box's panic…" | pre-release | flows |  |
| 56 | "One thing the applier leaves in place after…" | pre-release | flows |  |
| 57 | "The applier writes a systemd drop-in naming the…" | pre-release | flows |  |
| 58 | "Proof it worked, in order: the applier's `outcome.txt`…" | pre-release | flows |  |
| 59 | "**The upgrade key.** The everyday shared secret can…" | pre-release | flows |  |
| 60 | "PROTOCOL.md section 14 lets a runner hold additional…" | pre-release | flows |  |
| 61 | "The standing arrangement for upgrades is a key…" | pre-release | flows |  |
| 62 | "The sender keeps the pair in its keyring…" | pre-release | flows |  |
| 63 | "The policy fences the key to the one…" | pre-release | flows |  |
| 64 | "Rotating the key is a config edit: add…" | pre-release | flows |  |
| 65 | "When the staging script changes, its digest in…" | pre-release | flows |  |
| 66 | "The upgrade key is platform-independent — it is…" | pre-release | flows |  |
| 67 | "**Platforms.** The contract is the same everywhere: the…" | pre-release | flows |  |
| 68 | "Stopping first is not optional: a running runner…" | pre-release | flows |  |
| 69 | "What differs per platform is only the service…" | pre-release | flows |  |
| 70 | "| Platform | Runner runs as | Applier…" | pre-release | flagged | A table header row — structure, not a sentence |
| 71 | "|---|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 72 | "| Linux (systemd) | systemd service | `hp-remote-upgrade-apply`…" | pre-release | flows |  |
| 73 | "| Windows | Scheduled Task `HomingPigeon` | `hp-remote-upgrade-apply.ps1`…" | pre-release | flows |  |
| 74 | "| macOS | launchd agent `com.homing-pigeon.runner` | `hp-remote-upgrade-apply-macos.sh`…" | pre-release | flows |  |
| 75 | "Platform notes:" | pre-release | flagged | A label fragment ("Platform notes:") standing alone; the notes after it arrive without a hand-off |
| 76 | "The staging script is shell on Linux and…" | pre-release | flows |  |
| 77 | "On Linux the applier writes the CA-bundle drop-in…" | pre-release | flows |  |
| 78 | "Windows and macOS runners use their platform stores…" | pre-release | flows |  |
| 79 | "The sums check uses `sha384sum` on Linux, `shasum…" | pre-release | flows |  |
| 80 | "`--arg` and `--env KEY=value` are repeatable." | pre-release | flows |  |
| 81 | "`--script-url URL` sends the script by link instead…" | pre-release | flows |  |
| 82 | "`--aud RUNNER_ID` sets the job's `runner_id` audience claim,…" | pre-release | flows |  |
| 83 | "Two more subcommands drive the task board (PROTOCOL.md…" | pre-release | flows |  |
| 84 | "Both take `--reply-to` so the ack or the…" | pre-release | flows |  |
| 85 | "Every subcommand takes `--keyring PATH` to read secrets…" | pre-release | flows |  |
| 86 | "On a runner whose owner caps the view…" | pre-release | flows |  |
| 87 | "A query is `attest:PREDICATE`, `tail` or `tail:N`, `grep:PATTERN`,…" | pre-release | flows |  |
| 88 | "Under `summary` and `attested` the runner refuses `grep`…" | pre-release | flows |  |
| 89 | "A job can carry its files in its…" | pre-release | flows |  |
| 90 | "`--inline-file NAME=PATH` puts a local file in the…" | pre-release | flows |  |
| 91 | "Both are repeatable, with at most 8 outputs,…" | pre-release | flows |  |
| 92 | "Three kinds run work the runner owner has…" | pre-release | flows |  |
| 93 | "A recipe or change job brings no script,…" | pre-release | flows |  |
| 94 | "A cancel is answered with a signed `cancel_ack`…" | pre-release | flows |  |
| 95 | "Or paste the string to your SI in…" | pre-release | flows |  |
| 96 | "Large files are uploaded to cloud storage first;…" | pre-release | flows |  |
| 97 | "Verify a result body (results are encrypted by…" | pre-release | flows |  |
| 98 | "The `--job-id` can be left off only for…" | pre-release | flows |  |
| 99 | "`--outputs-dir DIR` writes the result's output files there,…" | pre-release | flows |  |
| 100 | "`--chain FILE` holds each result against the ones…" | pre-release | flows |  |
| 101 | "Every result carries `result_seq` and the digest of…" | pre-release | flows |  |
| 102 | "On a runner whose `pong_platform` is `standard` or…" | pre-release | flows |  |
| 103 | "Two results with the same value ran on…" | pre-release | flows |  |
