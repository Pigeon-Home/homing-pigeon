"""Scripts for the macOS and FreeBSD shells.

The runner invokes `sh` on both of those systems
(`platform_interpreter`). They are not the same program.
macOS `/bin/sh` is bash 3.2, in POSIX mode because it is
named sh. FreeBSD `/bin/sh` is FreeBSD's own shell. The
catalog here is the constructs both of those modes share:
no brace expansion, no keyword `function`, one command
per line once a script is longer than one line.
"""
import os

from runner.tests.proof_content_build import compose

ATOMS = (
    "true", ":", "pwd", "echo a", "echo b", "echo c", "printf x",
    "echo ok", "echo 'a'", 'echo "a"', "echo 'a b'", 'echo "x y"',
    "echo $HOME", "echo ${HOME}", "echo $((1))", "echo $(true)",
    "echo $((1+2))", "(echo a)", "echo a > /dev/null",
    "if true; then echo a; fi", "for i in a; do echo $i; done",
    "f(){ echo a; }; f",
)
JOINERS = (" && ", " || ", "; ", " | ")
BOUND = 49


def enumerate49():
    out = set(ATOMS)
    short = [a for a in ATOMS if len(a) <= 8]
    for a in ATOMS:
        for b in ATOMS:
            for joiner in JOINERS:
                script = a + joiner + b
                if len(script) <= BOUND:
                    out.add(script)
    for a in short:
        for b in short:
            for c in short:
                script = a + "; " + b + "; " + c
                if len(script) <= BOUND:
                    out.add(script)
    return sorted(out)


def at_length(n, start):
    return compose(n, ATOMS, start, "echo '", "'")


def macos_sh():
    for candidate in (os.environ.get("HP_MACOS_SH"), "/tmp/macos-sh"):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def freebsd_sh():
    for candidate in (os.environ.get("HP_FREEBSD_SH"), "/tmp/freebsd-sh"):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None
