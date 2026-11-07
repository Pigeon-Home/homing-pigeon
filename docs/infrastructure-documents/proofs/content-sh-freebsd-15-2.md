# FreeBSD 15.2 sh: the harness and its first run

The harness is `runner/tests/test_proof_sh_freebsd_15_2.py`.
It aims the content series at the FreeBSD 15.2 shell --
the base-system `/bin/sh` of a release whose BETA1
builds began on 2026-11-06. It carries the 15.0 file's
parser rungs (the 49-character set of 3,269 scripts,
then 5,000, 50,000, 500,000, and the production cap of
1,048,576, each with one byte over) and adds execution
rungs the 15.0 record did not ask for: the first rung
run whole, a set of atoms with pinned output, and the
5,000 rung run with its output discarded. The gate is
not asked again; that split is
`content-sh-freebsd-design.md`'s and it still holds.

The harness refuses substitutes in two places, not
one. The binary is taken from `HP_FREEBSD_15_2_SH`,
`HP_FREEBSD_SH`, or `/tmp/freebsd-sh-15.2`, or -- on a
FreeBSD host only -- `/bin/sh`; on any other host
`/bin/sh` is never taken, because there it is some
other program (on Linux, dash). And the release must
be a bare 15.2 string (`15.2-BETA1` and its kin), read
from `HP_FREEBSD_15_2_RELEASE`, `freebsd-version`, or
`uname -r` on a FreeBSD host. A shell from any other
release skips with that reason stated, so an older
guest cannot answer for 15.2 by accident. The
bare-machine procedure that produces a real run is
`content-sh-freebsd-15-2-runbook.md`.

## The first run

No real FreeBSD shell ran this harness.

The first run was made on 2026-11-07 on a Linux
machine (Ubuntu 24.04.5 LTS, kernel 7.0.0-43-generic),
and what it proves is the harness's shape, nothing
about FreeBSD. Before the run, the machine was checked
for a way to give the harness a real 15.2 shell
tonight, and every check came back empty:

| Check | Outcome |
|---|---|
| Host system | Linux; there is no FreeBSD machine in the fleet (the other machines are Linux and Windows) |
| `/bin/sh` on this machine | a symlink to dash -- a different program, and not used |
| `qemu-system-x86_64`, `qemu-x86_64`, `qemu-x86_64-static` | none installed; and qemu-user runs Linux binaries, not FreeBSD ones, as the 15.0 attempts already established |
| `bhyve`, `VBoxManage`, `virsh`, `freebsd-version` | none installed |
| A FreeBSD installer or VM image already on the machine | none found in the workspace's VM folders |
| The way the 15.0 guest ran (commit d7731c16) | a GitHub-hosted VM in `freebsd.yml`, pinned to release 15.0 -- not a machine available to this run, and not the 15.2 target in any case |

No image was downloaded to improvise one: a guest
built in a hurry, from an unverified image, would be
its own unrecorded procedure, and the runbook is the
recorded one.

The run itself:

```text
python3 -m unittest runner.tests.test_proof_sh_freebsd_15_2 -v
Ran 11 tests
OK (skipped=6)
```

- 5 tests passed: the target-shape tests. They pin the
  bare-15.2 release strings (and the refusal of 15.0,
  15.1, 14.3, 15.20, and of prose offered as release
  evidence), the series catalog (3,269 scripts, each at
  most 49 bytes; every rung built to its exact length),
  and the finder rule that a non-FreeBSD host never
  offers its own `/bin/sh`.
- 6 tests skipped, every one with the same reason:
  "FreeBSD sh is not on this machine. Its sources are
  the FreeBSD base system and do not build with the
  Linux toolchain here, and qemu-user runs Linux
  binaries, not FreeBSD ones. dash was not used in its
  place". The six are the release test, both parser
  tests, and all three execution tests. None of them
  ran. A skip is not a pass.
- The second skip gate -- a present shell on the wrong
  release -- did not fire here, because no shell was
  present at all. It is pinned by the target-shape
  tests' release cases and by its registration, and it
  fires on any FreeBSD machine that is not 15.2.

Nothing in this record claims FreeBSD 15.2's `/bin/sh`
accepted, parsed, or executed a single script. The
parser and execution counts are still owed, by a real
15.2 machine, run by the runbook. Until that run is
recorded here, this file is the honest state of the
15.2 shell check: the harness stands ready, and it has
not been run.
