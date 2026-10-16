# Threat model — an honest review

*Adapted from an external "review" by Claude.*

Homing Pigeon lets a cloud SI run code on your machine easily, which
is both its whole appeal and its whole problem. Anyone holding the
shared secret effectively owns the box the agent runner is installed
on, and since a cloud system can't be trusted never to send a
destructive job, the project assumes every job could be one.

For anything serious, existing tools already do this better: SSH with
scoped keys, CI runners, containers, or a proper agent sandbox. Still,
configuring those repeatedly for every provider and chat interface is
cumbersome, and this cuts through that noise.

The Oracle, backed by a local model such as Llama, reviews jobs and
their results. The operating system can carry the rest of the load,
with SELinux or AppArmor, locked-down users, containers, filesystem
ACLs, and role-based keys that could feed back into the Oracle and
limit what a bad or even malicious job can touch.

It could even work as a marketable service.

## What this means in practice

- The signature is the sole authentication gate. Guard the shared
  secret like a root password, because that is what it is.
- Run the agent as a locked-down user, on a throwaway account, on a
  box you can wipe. The README's security notes are not boilerplate.
- The Oracle reviews and attests. It does not contain a job unless
  you turn on Linux bubblewrap (`security.modes.confinement` set to
  `enforce`, and `bwrap` installed). That switch is off by default.
  A VM, a locked-down user, and the OS policy still do the real
  containment. AppArmor and SELinux profiles live under `hardening/`
  and are opt-in. They are not installed for you.
- Every new sense, transport, and job kind added to this project
  widens the blast radius. `docs/roadmap-spec.md` is exciting and
  dangerous in exactly equal measure; build the gates (§3) before
  the hands (§1.3).
