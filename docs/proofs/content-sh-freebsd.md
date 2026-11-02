# FreeBSD sh, the parser half

The program was `/bin/sh` inside a FreeBSD 15.0-RELEASE-p13
guest. The guest is the one `freebsd.yml` already boots
(`vmactions/freebsd-vm`, release 15.0). The run is
https://github.com/Pigeon-Home/homing-pigeon/actions/runs/41387454749
. `freebsd-version` printed `15.0-RELEASE-p13` at
2026-11-02 04:16:32Z. The phase was
`HP_FREEBSD_SH=/bin/sh HP_FREEBSD_SYNTAX_ONLY=1`. That
asks `sh -n` only. `handle_mail` was not called.

Both tests passed, in 0.217 seconds, and the phase
printed `OK` at 04:17:14Z.

| Rung | What `/bin/sh -n` did |
|---|---|
| 49 characters | 3,269 scripts, each at most 49 bytes, accepted as one file |
| 5,000 | three different scripts, accepted |
| 50,000 | three different scripts, accepted |
| 500,000 | three different scripts, accepted |
| 1,048,576 | three different scripts, accepted |
| one byte over each of those | accepted, including 1,048,577 |

`sh -n` does not know `max_script_bytes`. Accepting
1,048,577 is what a parser does. The refusal of that
length, naming the cap, is the gate's, and it was
already recorded on the content series. It was not
asked again here.

The job that contained this phase later failed. The
suite reported 2 failures and 10 errors, among them a
missing `bash` and a missing `remediation` key. Those
are not this check. The parser phase had already
printed `OK`, and the log has no `freebsd sh` error.

A Linux machine still skips the test. dash was not
used. bash was not used. The earlier attempts to build
FreeBSD's `sh` on Linux, and to run it under
`qemu-x86_64`, are why the check lives in the guest.
