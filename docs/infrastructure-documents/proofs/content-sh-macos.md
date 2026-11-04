# macOS sh, at the same rungs

The runner does not have a macOS interpreter of its own.
`platform_interpreter` returns `sh` on every system that is
not Windows. On macOS that program is bash 3.2.57, and
because the file is named `sh` it runs in POSIX mode. The
login shell is zsh. The runner does not invoke zsh. This
record is about `sh`.

The Linux content series used GNU bash 5. That is a
different parser. These checks used upstream bash 3.2.57,
started with `--posix`. Apple's patches are not in that
binary. The grammar of bash 3.2 is the grammar of macOS
`/bin/sh`. The binary was built here because this machine
is Linux. The test looks for `HP_MACOS_SH` and then
`/tmp/macos-sh`, and it checks the version string. Where
neither exists, the tests skip and say so. They do not
treat bash 5 as the Mac shell.

## The scripts

The catalog is POSIX constructs: simple commands, `&&`
and `||` and `;` and a pipe, `if`, `for`, a function
written `f(){ ...; }`, quoting, parameter and command
and arithmetic expansion, a redirection, a group. No
brace expansion. No `function` keyword.

At 49 characters the set is generated, not listed: every
atom, every pair, and every triple of the short atoms.
That is 3,269 scripts. Each is at most 49 characters. `bash 3.2.57 --posix -n`
accepted the set as one file. `handle_mail` admitted
every one. A sample of twenty longer than one byte was
refused at a one-byte cap, and `:` was admitted. The cap
sample is a sample. The admission is the whole set.

At 5,000, 50,000, 500,000, and 1,048,576 the scripts are
the catalog cycled, one command per line, three different
starts, plus one script one character past the rung. The
parser accepted each, exit code 0. No checker crashed.
`handle_mail` admitted every script inside the byte cap,
including one character past 5,000, 50,000, and 500,000,
because those numbers are not limits in the code. A
script of 1,048,577 bytes was refused, and the refusal
named `max_script_bytes` and the number 1048577.

The harness is `runner/tests/test_proof_sh_macos.py`. The
scripts were syntax-checked, not executed.

## What this does not say

This is not zsh. This is not Apple's patched bash, and
the record says so. The 49-character set is the
combinations of this atom list, not every string. The
longer rungs are the catalog repeated. The ladder models
in stages 1 to 10 do not contain an operating system.
There was nothing in them to re-check for macOS.
