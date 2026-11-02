# FreeBSD sh: what emulation is for

The check has two halves, and they do not need the same
machine.

The parser half asks whether FreeBSD's `/bin/sh` accepts
the script. That program is the only thing that can
answer. bash, bash in POSIX mode, and dash are different
programs, and a pass from any of them is not this check.

The gate half asks whether the script's text changes
`handle_mail`'s decision. The gate does not parse the
script. It measures the bytes, checks the signature, the
audience, and the caps, and then either calls
`execute_job` or refuses. That half has already been run,
on these same texts, in the content series. Running it
again inside a FreeBSD VM would be a test of
CPython-on-FreeBSD, which is what `freebsd.yml` already
does with the suite. It is not a test of the shell.

## What was researched

`qemu-x86_64` runs Linux binaries. FreeBSD binaries use
FreeBSD system calls. That emulator cannot host
`/bin/sh`. Building `bin/sh` on Linux was also refused:
the build is the FreeBSD base system (`bsd.prog.mk`,
libedit unless `NO_HISTORY` is set, and other base
tools). A Linux-linked build would be the grammar
against glibc, a third program, and it is not the
proposal.

A full virtual machine is a different kind of emulation.
The guest kernel is FreeBSD, and `/bin/sh` inside it is
the base-system binary. The repo already boots that
guest. `.github/workflows/freebsd.yml` starts FreeBSD
15.0 with `vmactions/freebsd-vm` on a Linux runner,
weekly and on dispatch, and not on the release path. The
file says so: a signal, not a gate. The platform matrix
boots the same action for `vm-freebsd-14` and runs
`platform_proof.sh`, which proves a signed job runs
under the platform interpreter. It does not syntax-check
the content-series scripts.

## The design

Emulate the guest. Use the real shell. Do not emulate
the gate.

One new phase inside the existing `freebsd.yml` run, after
the guest is up and before the suite, so a parser failure
is not buried under the suite's annotations:

```
HP_FREEBSD_SH=/bin/sh HP_FREEBSD_SYNTAX_ONLY=1 \
  python3 -m unittest runner.tests.test_proof_sh_freebsd
```

`HP_FREEBSD_SYNTAX_ONLY` does not exist yet. The test
today also drives `handle_mail`. The phase wants the
parser only: `sh -n` on the 49-character set and on one
script at each longer rung, one command per line, and on
one script of 1048577 bytes. A non-zero status from
`sh -n` fails the phase. A crash of `sh -n` is recorded
as a crash, not as a pass. The gate is not called.

The result is a log line from the guest: the `sh` version
(`freebsd-version` is already printed), the counts, and
the exit codes. That log is the record of the parser
half. It is not written into this tree by the VM. A
person copies the counts into `content-sh-freebsd.md`
after reading them, the same way the other rungs were
recorded. Until that copy happens, the skip on a Linux
machine remains a skip.

What this does not add:

- No second VM, and no FreeBSD on the push path. The
  workflow's own rule stands.
- No dash, no bash `--posix`, and no Linux-linked port
  of the sources.
- No re-run of `handle_mail` inside the guest for this
  question.
- No claim about zsh, or about a shell the owner
  installed from ports. The interpreter the runner calls
  on FreeBSD is `/bin/sh`.
