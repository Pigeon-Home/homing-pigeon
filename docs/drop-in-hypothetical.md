# Hypothetical: dropping the runner in after you already have a process

This is a hypothetical for the runner's own tests. It is not an
exploit, not a jailbreak, and not a submission to anyone's bounty
program. Nothing here disables a protection, escapes a sandbox, or
describes a vulnerability. The assumption, stated so the tests have
something to stand on, is that the person running them is an
authorized researcher who already has a process. The only question
the runner is allowed to answer is: given that process, can a copy
of this Python program start inside a directory that process can
already write, and still do its nominal job.

Nominal means all of the following, and nothing more.

- A signed job runs, under the Python that is already running.
- A job with a bad signature produces no result.
- State is written only in the directory the runner was given.
- No service is installed, and nothing listens.

## The stages

The stages are where a researcher might already be. They are not
steps to get from one to the next.

1. No process yet. There is nothing to drop in. This is not a
   runner problem, and there is no test that pretends otherwise.

2. A process that cannot execute a program, and has no Python.
   An application sandbox on a phone is this stage. So is a
   television. The installer already refuses it (`can_exec` is
   false). A refusal is the nominal result. A green run here
   would be a lie.

3. A userland process on a machine the researcher is allowed to
   use, with the system protections still on, and one directory
   they can already write. This is the drop. The runner is the
   Python tree or the frozen binary, copied into that directory
   and started from it. It does not install itself, and it does
   not need the rest of the disk.

4. That same directory, with the surroundings stripped the way a
   research shell often is: no home directory, a PATH that contains
   only the interpreter already in hand, standard input closed, no
   bash. Still nominal. The job's interpreter is that Python, not
   a shell the box may not have.

Stages 3 and 4 are what `tests/test_drop_in.py` runs. Stage 2 is
asserted there as a refusal. The CI leg `drop-in-stripped` runs
the same tests inside a container whose root filesystem is
read-only and whose only writable scratch is a tmpfs, with the
stage-4 surroundings applied. That is the proof of work. It is
a Linux container, not an Apple device, and it does not claim to
be one.
