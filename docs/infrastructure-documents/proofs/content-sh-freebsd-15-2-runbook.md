# FreeBSD 15.2 sh: the bare-machine runbook

This runbook runs the 15.2 shell harness
(`runner/tests/test_proof_sh_freebsd_15_2.py`) on a real
FreeBSD 15.2 machine and records the result in
`content-sh-freebsd-15-2.md`. It assumes a bare machine:
nothing is taken as already installed, and every step
installs what it needs itself, in the open. A step that
works only because something happened to be on the
machine already is a broken step; if a run leans on a
tool this runbook did not install, the run is not the
runbook's run and the record must say what was actually
there.

The target is one program: the base-system `/bin/sh` of
FreeBSD 15.2 (BETA1 builds began on 2026-11-06; the
release schedule is
https://www.freebsd.org/releases/15.2R/schedule/).
No other shell answers in its place -- not the 15.0
shell, not dash, not bash, not a Linux-linked build of
the sources. The split is the one
`content-sh-freebsd-design.md` settled: the guest's own
shell is the parser and the executor; the gate is not
asked again.

## 1. Get a bare 15.2 machine

Take the official 15.2-BETA1 installer image or VM image
for the machine's architecture from the FreeBSD download
page (https://www.freebsd.org/where/), check it against
the published checksums, and install or boot it the
ordinary way. A virtual machine is fine: the guest
kernel is FreeBSD, so the guest's `/bin/sh` is the
base-system binary. An emulator that runs Linux
binaries is not fine; it cannot host this shell.

Finish the install with an ordinary user account as
well as root, and reboot into the installed system.
Everything below happens in the installed system, not
the installer.

## 2. Prove the release before anything else

```sh
freebsd-version
uname -a
```

The first line must be a bare 15.2 string (for example
`15.2-BETA1`). If it says anything else -- 15.0, 15.1,
14.x -- stop. That machine's shell is a different
release's program; it answers under
`content-sh-freebsd.md`, not here, and no result from
it goes in the 15.2 record.

## 3. Network, in the open

The steps below fetch packages and the repository, so
the machine needs a network with working DNS. On a
machine installed with DHCP (the installer's usual
choice) this is already configured. Check, do not
assume:

```sh
ping -c 1 pkg.freebsd.org
```

If that fails, configure the interface and resolver
with `bsdconfig networking` (or by hand in
`/etc/rc.conf` and `/etc/resolv.conf`) until it
answers. Do not proceed on a cached or offline
substitute and call it this run.

## 4. Install every tool the run needs

A bare base system ships only the `pkg` bootstrap, not
the tools. Bootstrap it and install the full list in
one place:

```sh
su -
export ASSUME_ALWAYS_YES=yes
pkg bootstrap -f
pkg update -f
pkg install -y git ca_root_nss
```

Python is the one flavor question, the same one
`freebsd.yml` answers for 15.0: the repository carries
one Python flavor's packages, and which one is the
release's business. Take whichever flavor installs,
and remember the interpreter's name:

```sh
PY=""
for v in 313 312 311; do
  if pkg install -y "python$v"; then
    PY="python3.${v#3}"; break
  fi
done
[ -n "$PY" ] || { echo "no python flavor installs"; exit 1; }
[ -x /usr/local/bin/python3 ] || ln -s "/usr/local/bin/$PY" /usr/local/bin/python3
"$PY" -c "import sys; print(sys.version)"
```

The harness needs nothing beyond the standard library:
it imports the series builders
(`runner/tests/proof_sh_build.py`,
`runner/tests/proof_content_build.py`) and the standard
library only. No hypothesis, no node, no test-runner
package. If a later version of the harness grows a
dependency, this step is where it gets installed, by
name, before the run.

Still as root, make the unprivileged user the run
belongs to (the runner is not run as root in service,
and this proof follows the same rule `freebsd.yml`
uses):

```sh
pw useradd runner -m -s /bin/sh
exit
```

## 5. Get the tree, as that user

```sh
su -l runner
cd ~
git clone https://github.com/Pigeon-Home/homing-pigeon.git hp-15-2
cd hp-15-2
git log -1 --oneline
```

Write the commit hash down; the record names the tree
the shell was asked about.

## 6. Run the harness

The suite's fake binaries and scratch live under
TMPDIR, and TMPDIR must be executable, so it lives in
the user's home, not in a possibly-noexec `/tmp` (the
lesson `freebsd.yml` carries). The harness is told
which shell and which release it is judging, in the
open:

```sh
mkdir -p ~/tmp
export TMPDIR=~/tmp
export HP_FREEBSD_15_2_SH=/bin/sh
export HP_FREEBSD_15_2_RELEASE="$(freebsd-version)"
"$PY" -m unittest runner.tests.test_proof_sh_freebsd_15_2 -v \
  > ~/freebsd-sh-15-2.log 2>&1
echo "exit: $?"
tail -n 20 ~/freebsd-sh-15-2.log
```

(On the login shell above, `$PY` is root's shell
variable from step 4 and does not survive `su -l`;
set it again here from step 4's printed version --
`PY=python3.13`, or whichever flavor installed -- or
call plain `python3`, which step 4 linked.)

What a real run looks like: the target and catalog
tests pass, and the six shell tests run -- the release
test, the parser rungs, the execution rungs -- and pass
or fail on their own lines. Any of the six reporting
`skipped` means the shell or the release gate refused,
and the run is a non-result for the record: a skip is
not a pass, whatever the final line says.

## 7. Record the run

Copy into `content-sh-freebsd-15-2.md`, replacing its
first-run section:

- the `freebsd-version` line, exactly as printed;
- the tree's commit hash from step 5;
- the harness's own summary line (tests run, failures,
  errors, skips, and the time it took);
- any failing test's name and its first error lines,
  if there were failures.

Then state, in the record's own words, the one fact the
record exists for: a real FreeBSD 15.2 `/bin/sh` ran
this harness, or it did not. Nothing softer. A run on
any other machine, under any other shell, or on any
other release is recorded as what it was, under its own
record, and never copied here as a 15.2 result.

## The other way a guest has run here

The 15.0 record was made inside the guest
`.github/workflows/freebsd.yml` boots on a Linux runner
(`vmactions/freebsd-vm`), with the parser phase ahead
of the roster. That workflow still pins release 15.0.
Pointing the same action at a 15.2 image, where the
action offers one, and adding this harness as a phase
is a fair way to get a guest when no bare machine is at
hand -- the guest's shell is still the real program --
but it is a change to that workflow, made on its own
merits, and until it is made the bare machine above is
the way this harness runs.
