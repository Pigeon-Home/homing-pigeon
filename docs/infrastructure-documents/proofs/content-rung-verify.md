# Content redo — first-hand verification, rung by rung

This record is a separate first-hand verification of the
content redo (`content-rung-49.md`, `content-rung-5000.md`,
`content-rung-50000.md`, `content-rung-500000.md`,
`content-rung-cap.md`), carried out on 7-Nov-2026 after the
redo landed. Nothing here is taken from the redo records'
own Verification sections. Every pass below was run by the
verifier, on the machines named, and a skip is recorded as
a skip, never as a pass.

## A naming note, before the table

The proof ladder names 500 as a rung (the stage 6 raise,
P1(500), `stage6-rung500.md`). The redo series as landed
has no 500-character content rung: its first content rung
is 49. So 500 was built and checked here for the first
time as a content rung, with the redo's own builder
(`runner/tests/proof_content_build.py`) and a new harness
in the same shape as the other rungs,
`runner/tests/test_proof_content_rung500.py`. The redo's
own first rung, 49, is also re-checked below, as an extra
row, so no rung of either naming is left unexamined.

## The table

Digit counts are character counts. The scripts are ASCII,
so at the cap the character count and the byte count are
the same number.

| Rung | bash (this VM) | Windows PowerShell (Germany rig) |
|---|---|---|
| 500 | 500 — first-hand pass | 500 — parser pass, gate leg open |
| 5,000 | 5,000 — first-hand pass | 5,000 — parser pass, gate leg open |
| 50,000 | 50,000 — first-hand pass | 50,000 — parser pass, gate leg open |
| 500,000 | 500,000 — first-hand pass | 500,000 — parser pass, gate leg open |
| 1,048,576 (cap) | 1,048,576 — first-hand pass | 1,048,576 — parser pass, gate leg open |
| 49 (extra row) | 49 and under — first-hand pass | 49 and under — not run on Windows, open |

## bash column — how it was run

On this VM (GNU bash 5.2.21, Python 3.12.3), in a scratch
clone of current main, the redo harnesses were re-run
module by module:

- `test_proof_content_rung500.py` (new, this verification):
  4 tests — lengths and variety, `bash -n`, and the gate
  legs passed; the PowerShell leg skipped because pwsh is
  not installed on this VM, and that skip is not counted
  as a pass for any PowerShell claim.
- `test_proof_content_rung5000.py`: the bash tests passed
  (lengths 5,000 and 5,001, `bash -n` exit code 0, the gate
  admitted every bash text, a cap of 100 bytes refused
  every 5,000-character text naming `max_script_bytes`);
  the PowerShell leg skipped, pwsh not installed.
- `test_proof_content_rung50000.py`: the bash tests passed
  on the same terms at 50,000 and 50,001; the PowerShell
  leg skipped, pwsh not installed.
- `test_proof_content_rung500000.py`: lengths and variety
  passed, `bash -n` passed, and the gate test was re-run
  on its own and passed at 500,000 and 500,001, with the
  100-byte cap refusing naming `max_script_bytes`. That
  single gate test took 861 seconds wall clock on this
  machine while many other suites were running on it; the
  length of the run is recorded, and it is not a failure.
  The PowerShell leg skipped, pwsh not installed.
- `test_proof_content_rung_cap.py`: the bash tests passed
  in a 974-second run — lengths exactly 1,048,576 bytes,
  `bash -n` accepted every bash script including the one
  at 1,048,577, and the gate at its default cap admitted
  every script of exactly 1,048,576 and refused the
  1,048,577 script naming `max_script_bytes` and the
  number 1048577. The PowerShell leg skipped, pwsh not
  installed.
- `test_proof_content_build.py`: 9 tests passed — the
  builder produces the same scripts as its reference at
  every rung, including exact lengths of 500, 500,000,
  1,048,576 and 1,048,577.
- `test_proof_content_rung49.py` (the extra row): the
  bash tests passed in a 727-second run — the generated
  set is 3,682 scripts, each at most 49 characters,
  `bash -n` accepted the whole set as one file, the gate
  admitted every one of the 3,682 scripts, and a 1-byte
  cap refused a 20-script sample naming
  `max_script_bytes` while still admitting `:`. The
  PowerShell leg skipped, pwsh not installed; the
  511-script PowerShell survivor set was not re-run on
  this VM or on Windows in this verification.

In total the redo harnesses re-run here are 35 tests:
29 passed, 6 skipped — every skip the pwsh leg of a
rung, with the registered reason that the PowerShell
half of that rung was not run — and none failed.

The gate in every case is the real `handle_mail` on
current main. The scripts were syntax-checked with
`bash -n`, not executed.

## Windows PowerShell column — how it was run, and what is open

The only real Windows available is a production runner
rig (Windows Server 2022, Windows PowerShell 5.1.20348.1,
Desktop edition; no pwsh installed). It runs release
3.15.17.137, not current main. A few short, light
invocations were made over SSH, in a scratch folder that
was deleted afterwards; no scheduled task on the rig was
stopped, restarted, or disturbed, and nothing was
installed on it.

For each rung, a small PowerShell script on the rig built
the redo's PowerShell catalog script at that rung —
the same 16-construct catalog and the same compose
algorithm as `proof_content_build.py`, generated on the
rig, so no large payload travelled to it — and parsed it
with the real Windows PowerShell parser,
`[System.Management.Automation.Language.Parser]::ParseInput`.
The results, verbatim in substance:

- 500: len=500, lines=24, distinct=16, parse_errors=0
- 5,000: len=5000, lines=233, distinct=16, parse_errors=0
- 50,000: len=50000, lines=2326, distinct=16, parse_errors=0
- 500,000: len=500000, lines=23256, distinct=16, parse_errors=0
- 1,048,576: len=1048576, lines=48771, distinct=16, parse_errors=0
- 1,048,577 (past the cap): len=1048577, lines=48771,
  distinct=16, parse_errors=0

The line counts match the Python builder's scripts at
start 0 exactly, rung for rung (the builder's scripts have
one more distinct line, the pad line), so the texts the
Windows parser accepted are the redo's own scripts, built
by the same algorithm from the same catalog.

What this does NOT close: the gate leg on Windows. Presenting
these scripts to `handle_mail` on the rig would require
current-main runner code on a production rig that runs
release 3.15.17.137; upgrading or installing on that rig
was not part of this verification, and moving the large
payloads through its production lanes is more than a light
invocation. The PowerShell gate legs in the redo harnesses
also did not run on this VM: pwsh is not installed here,
every one of those legs skipped, and a local pwsh would in
any case be a Linux build, not real Windows PowerShell.
So at every rung the Windows PowerShell column stands as:
parser leg, first-hand pass; full rung (parser plus gate
on Windows), not run, OPEN, for the reasons above. No rung
is closed on the bash result, and none is closed on the
Linux pwsh result, which does not exist.

The 49-character PowerShell set (511 survivors) was not
re-run on Windows at all: its harness generates and parses
the set in one Linux pwsh process, and no equivalent light
invocation was attempted on the rig. That row is open.

## What this does not say

This verification covers the redo's content series at the
rungs in the table. It does not re-check the TLA model
rungs (`stage6-rung500.md`, `stage7-5000.md` and above),
the macOS or FreeBSD shell records, or any rung in a shell
not named here.
