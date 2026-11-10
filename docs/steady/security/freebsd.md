# FreeBSD hardening notes

The runner installs on FreeBSD from the same tree as everywhere
else (`install.py` writes a cron `@reboot` entry for the node).
This page is about the one mechanism FreeBSD needed a backend
for: confinement.

## Confinement on FreeBSD

There is no bwrap on FreeBSD, and the FreeBSD confinement
backend is a jail, not a namespace sandbox. What it applies, at
`enforce`, is named exactly in every audit and startup record:

```
freebsd: jail + no_network + spawn_resource_limits
```

Each job runs inside a freshly created jail(8) whose root is a
per-job skeleton. The host's `/usr`, `/usr/local`, `/bin`,
`/lib`, `/libexec`
and `/sbin` are mounted read-only (nullfs) into that root; the
job's work directory is mounted at `/work` and is the only
writable mount; `/tmp` is a fresh tmpfs; `/dev` is the jail
devfs under ruleset 4, which exposes only the handful of device
nodes a job needs. The jail is created with `ip4=disable` and
`ip6=disable`, so the job has no network at all, loopback
included. The memory ceiling is applied at spawn: the job's
command runs under `limits(1)` with the virtual-memory and
data-size limits both set to 512 MiB per process. The jail
exists before the job's first process starts (the job is
started inside it with `jexec(8)`), so the job never runs a
line unconfined, and the jail is removed when the job's
process exits.

When `job_user` is also at `enforce` with a user named, that
user is handed to the spawn and applied inside the jail
(`jexec -u`, resolved in the host's user database): the
POSIX `setuid` demote cannot ride a spawn
that replaces the process creation, so the demote happens at
the jail door instead, the same shape as the Windows backend's
creation-time token. On its own (confinement at `audit` or
`off`), `job_user` on FreeBSD is the ordinary POSIX demote,
which engages as it does on Linux.

What this does not provide, plainly:

- The memory ceiling is a per-process resource limit applied
  at spawn (`setrlimit` via `limits(1)`), not an `rctl(8)`
  rule. RACCT/RCTL is present but disabled on the project's
  FreeBSD node (`kern.racct.enable=0`, a boot tunable), so
  rctl cannot deny anything there. The record names
  `spawn_resource_limits` for exactly that reason; on a host
  with RACCT enabled, an rctl-backed ceiling is a future pass,
  and it will change the status string when it lands, not
  before.
- Capsicum is not used. Capability mode is entered in-process
  by the confined program itself; the runner starts arbitrary
  job interpreters that know nothing of it, so it does not fit
  the launcher shape. The jail is the boundary instead.
- The job runs as root inside its jail unless `job_user`
  hands the spawn a user. Jail root is not host root: the
  jailed process cannot see the host filesystem outside the
  mounts above, and the jail defaults deny mounting, raw
  sockets and System V IPC inside it. But root inside a jail
  is still root over everything mounted writable there, which
  is the job's own work directory and nothing else — keep
  jobs' outputs inside it.

At `enforce` the startup gate probes the backend — a
throwaway skeleton, its nullfs mounts, a throwaway jail
created and removed, and a `true` run inside it under the
spawn limits — and refuses to start when the probe fails,
naming why. A job whose own jail cannot be created or mounted
is refused at job time the same way; there is no path on
which a job runs unconfined under `enforce`.

## The mode a FreeBSD config states

A fresh FreeBSD install writes `security.modes.confinement`
into `config.json` at `audit`, stated in the file. The reason
is the Windows one: the installer and the setup wizard write
the seed without running the backend probe on that machine,
and stating `enforce` sight-unseen risks a first-start refusal
on a machine where the jail cannot engage (the backend needs
root, `jail(8)`, and `mount_nullfs`). The operator steps the
mode up to `enforce` deliberately, and the startup gate then
verifies the probe on that machine. At `audit`, jobs run
unconfined and the audit log records what the mode would have
done. `job_user` is not stated down: the POSIX demote engages
on FreeBSD as it does on Linux.

## Supposition, recorded before the field test

Recorded 2026-11-10, before the backend's first field test on
the fleet FreeBSD node (FreeBSD 14.5-RELEASE), mirroring the
record the Windows backend carried into its own field test:

Before this backend, confinement at `enforce` on FreeBSD
refused at startup ("confinement (bwrap) is Linux-only; this
machine is freebsd14") and the platform seed stated the mode
at `audit` because there was no backend behind it. The
supposition is that, with the backend landed, on the node:

- the startup probe returns None and the runner starts with
  every security mode at `enforce`;
- each exec job's audit record names exactly "freebsd: jail +
  no_network + spawn_resource_limits";
- an escape write to a host path outside the work mount does
  not land — the path does not exist inside the jail root;
- an escape read of a host file does not return its contents,
  for the same reason (this is stronger than the Windows
  backend, which has no namespace isolation);
- a job that tries to commit 700 MiB is refused by the
  512 MiB spawn limit;
- the rest of the 17-step rig battery (startup, build stamp,
  clock, compute, file write and read inside the workspace,
  attested ping, tampered and wrong-audience refusals, result
  verification, production install untouched) behaves as it
  did in the baseline run at the seeded posture.

## Conclusions from the field test

The field test ran on the fleet node (FreeBSD 14.5-RELEASE)
on 2026-11-10: the full 17-step rig battery at every
security mode `enforce`, superseding the baseline run at
the seeded posture for the confinement steps. Every step
passed, 17 of 17:

- the startup probe engaged and the runner started with
  every security mode at `enforce`;
- each exec job's audit record named exactly "freebsd: jail
  + no_network + spawn_resource_limits";
- the escape write did not land and the escape read did not
  return the host file's contents — the jail root holds
  neither path, which is stronger than the Windows backend's
  outcome, as supposed;
- the 700 MiB job was refused by the 512 MiB spawn limit
  (its interpreter's allocation failed; a live unit test
  asserts the MemoryError, so the refusal is the ceiling's
  and not a job that never started);
- the production install stood untouched throughout —
  config, runner and crontab hashes identical before and
  after, and no process ran under the installed config.

The supposition's shape held. The field test also found 3
defects the local tests had not, each fixed and landed
before the passing run:

- a nullfs mount cycle: `/usr/local` sits on the same
  filesystem as `/usr` on the node, and mounting both was
  refused ("Resource deadlock avoided"). A mount whose
  source lives on the same filesystem as an ancestor
  already mounted is now skipped — the child tree is
  visible through the ancestor's mount; a child that is
  its own filesystem still mounts for real.
- the demoted spawn: `jexec -U` resolves the user in the
  jail's user database, which the skeleton cannot serve;
  the spawn now uses `-u`, resolved in the host's user
  database — the account the job_user seam named. The
  jail root is also traversable by the job user (a
  root-run spawn had masked its 0700 default), and the
  spawn passes the job's working directory (`-d /work`),
  the in-jail form of the host spawn's cwd.
- the loader hints: the dynamic loader's hints live in
  `/var/run` on FreeBSD, and the skeleton had no `/var`;
  binaries linked against `/usr/local` libraries (the
  pkg-installed python3 is the standing case) failed to
  load inside the jail while `/bin` tools ran. The
  skeleton carries a copy of the hints file, nothing
  else of `/var`.

The backend's live unit tests run on the node itself
(probe, argv translation, in-jail spawn, demote, local
binary, memory ceiling): 6 of 6. What this backend does
not do stands as written above: no rctl rule, no Capsicum,
no per-job CPU or process-count limit, no separate network
namespace with connectivity.
