# FreeBSD sh was not run

The runner invokes `sh` on FreeBSD, the same call it
makes on macOS and on Linux. FreeBSD's `/bin/sh` is not
bash. It is FreeBSD's shell, in the base system. A check
that uses bash, including bash in POSIX mode, is not a
check of that program. dash is an Almquist shell too, and
it was not used as a substitute. The two have diverged.

## What was tried

The current `bin/sh` sources were fetched from the
FreeBSD tree. They are not a portable program. The build
is `bsd.prog.mk`. It links libedit and pulls in other
base-system tools (`kill`, `test`, `printf`). That build
does not run on the Linux toolchain here.

`qemu-x86_64-static` was unpacked and it runs. It runs
Linux binaries. A FreeBSD ELF uses FreeBSD system calls,
and that qemu does not translate them. A FreeBSD base
image would not have executed.

## What the test does instead

`runner/tests/test_proof_sh_freebsd.py` holds the same
rungs as the macOS file: the 49-character set, then
5,000, 50,000, 500,000, and the production cap, one
command per line. It runs only when `HP_FREEBSD_SH` or
`/tmp/freebsd-sh` is a real binary. On this machine the
tests skip, and the skip says dash was not used in its
place. A skip is not a pass. Nothing in this record
claims FreeBSD sh accepted a script, and nothing claims
the gate was shown a FreeBSD-parsed script.

The ladder models in stages 1 to 10 do not contain an
operating system. There was nothing in them to re-check
for FreeBSD. The platform difference is this shell, and
this shell was not run.
