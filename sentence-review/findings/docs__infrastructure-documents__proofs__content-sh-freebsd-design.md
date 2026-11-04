# Findings — docs/infrastructure-documents/proofs/content-sh-freebsd-design.md

Source: docs/infrastructure-documents/proofs/content-sh-freebsd-design.md, reviewed at main 553181d8.
Sentence units: 41. Flagged: 0. Categories: pre-release 41, post-release 0.

A short design note for the FreeBSD sh content check: what it tests, the 3 imperative design rules (complete imperative sentences, and they flow as a set), what it does not add. Nothing is flagged. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The check has two halves, and they do…" | pre-release | flows |  |
| 2 | "The parser half asks whether FreeBSD's `/bin/sh` accepts…" | pre-release | flows |  |
| 3 | "That program is the only thing that can…" | pre-release | flows |  |
| 4 | "The gate half asks whether the script's text…" | pre-release | flows |  |
| 5 | "The gate does not parse the script." | pre-release | flows |  |
| 6 | "It measures the bytes, checks the signature, the…" | pre-release | flows |  |
| 7 | "That half has already been run, on these…" | pre-release | flows |  |
| 8 | "Running it again inside a FreeBSD VM would…" | pre-release | flows |  |
| 9 | "It is not a test of the shell." | pre-release | flows |  |
| 10 | "`qemu-x86_64` runs Linux binaries." | pre-release | flows |  |
| 11 | "FreeBSD binaries use FreeBSD system calls." | pre-release | flows |  |
| 12 | "That emulator cannot host `/bin/sh`." | pre-release | flows |  |
| 13 | "Building `bin/sh` on Linux was also refused: the…" | pre-release | flows |  |
| 14 | "A Linux-linked build would be the grammar against…" | pre-release | flows |  |
| 15 | "A full virtual machine is a different kind…" | pre-release | flows |  |
| 16 | "The guest kernel is FreeBSD, and `/bin/sh` inside…" | pre-release | flows |  |
| 17 | "The repo already boots that guest." | pre-release | flows |  |
| 18 | "`.github/workflows/freebsd.yml` starts FreeBSD 15.0 with `vmactions/freebsd-vm` on a…" | pre-release | flows |  |
| 19 | "The file says so: a signal, not a…" | pre-release | flows |  |
| 20 | "The platform matrix boots the same action for…" | pre-release | flows |  |
| 21 | "It does not syntax-check the content-series scripts." | pre-release | flows |  |
| 22 | "Emulate the guest." | pre-release | flows |  |
| 23 | "Use the real shell." | pre-release | flows |  |
| 24 | "Do not emulate the gate." | pre-release | flows |  |
| 25 | "One new phase inside the existing `freebsd.yml` run,…" | pre-release | flows |  |
| 26 | "`HP_FREEBSD_SYNTAX_ONLY=1` is the switch, and the phase is…" | pre-release | flows |  |
| 27 | "The guest reported on 2026-11-02." | pre-release | flows |  |
| 28 | "The counts are in `content-sh-freebsd.md`." | pre-release | flows |  |
| 29 | "A skip on a Linux machine remains a…" | pre-release | flows |  |
| 30 | "The result is a log line from the…" | pre-release | flows |  |
| 31 | "That log is the record of the parser…" | pre-release | flows |  |
| 32 | "It is not written into this tree by…" | pre-release | flows |  |
| 33 | "A person copies the counts into `content-sh-freebsd.md` after…" | pre-release | flows |  |
| 34 | "Until that copy happens, the skip on a…" | pre-release | flows |  |
| 35 | "What this does not add:" | pre-release | flows |  |
| 36 | "No second VM, and no FreeBSD on the…" | pre-release | flows |  |
| 37 | "The workflow's own rule stands." | pre-release | flows |  |
| 38 | "No dash, no bash `--posix`, and no Linux-linked…" | pre-release | flows |  |
| 39 | "No re-run of `handle_mail` inside the guest for…" | pre-release | flows |  |
| 40 | "No claim about zsh, or about a shell…" | pre-release | flows |  |
| 41 | "The interpreter the runner calls on FreeBSD is…" | pre-release | flows |  |
