# The folder: one atom that writes, and where it may write

The 22 atoms keep no state. None of them writes a file. The
owner's next atoms are the ones that write inside the job's
folder, and those are what bring confinement into the proof.
This page adds one such atom, and it does not add it to the
22. The grammar of the rung is unchanged. No new constraint.

One turn of the motor, `v4-the-motor.md`.

## The atom

`printf x > kept`

It writes one file, `kept`, in the job's folder, and the file
holds the byte `x`. It sets nothing, and it writes nowhere
else.

## Where it may write

This is C18, already defined. When confinement is enforce and
the sandbox can engage, the job's folder is the only writable
mount. `/tmp` inside the sandbox is a tmpfs, not the host's
`/tmp`. A job names no mount and no flag.

The default mode is enforce. Where the sandbox cannot engage,
the job is refused. It is not run on the host instead.

## What was asked

One corpus job, its script replaced, through the real gate and
the real execution.

- **Inside, enforce, where the sandbox engages.** The atom
  runs. `kept` is in the job's folder and holds `x`. The
  runner returns exit code 0. The log says the job was
  sandboxed.
- **Outside, enforce, where the sandbox engages.**
  `printf y > /tmp/<a host path>` does not create that file
  on the host.
- **Outside, off.** The same script does create the file on
  the host. That is the difference the default is there to
  make. The test removes the file.
- **The join, enforce.** The writer is still not one of the
  22. It was asked after all 22, joined on with `; `. The
  row's result is M's, at `/work`, and `kept` holds `x`.
  The same row, then a write to a host path, does not
  create that file.
- **Enforce, where the sandbox cannot engage.** The job is
  refused, and nothing is written.

`runner/tests/test_v4_the_folder.py` holds this on every
suite run. The 22 atoms are not changed, and the count of
their closure is not changed. The default cap stays
1,048,576.
