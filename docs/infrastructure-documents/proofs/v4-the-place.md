# The place: where the machine stands when confinement is on

The proof at a bound ran with confinement off. The default is
enforce. Three of the 22 atoms read the place the job runs:
`pwd`, `echo $HOME` and `echo ${HOME}`. Off, `pwd` prints the
host path of the job's folder. On, it does not. This page says
what the place is when confinement is on. It adds no atom and
no constraint.

## The place

Under enforce, when the sandbox engages, the machine M is the
same machine. The folder it is given is the work mount, `/work`,
not the host path. That mount is C18's: the job's folder is
bound there, and the job's current directory is that mount.

`HOME` is the `HOME` the runner passes in. The runner removes
its own secrets and passes the rest, and `HOME` is in the rest.
Inside the sandbox it is the host's `HOME`.

The other 19 atoms do not read the place. Their results are
the same on or off.

## What was asked

One corpus job, through the real gate and the real execution.
All 22 atoms were run, on and off.

- **Enforce, where the sandbox engages.** Every atom, and the
  row `pwd; printf x`. Each result is M's, with the folder set
  to `/work` and `HOME` set to the host's.
- **Off.** Every atom is M's with the host folder. The 19 atoms
  that do not read the place have the same result as under
  enforce. `pwd` does not: it prints the host folder. The two
  `HOME` atoms do, because `HOME` is passed in either way.
- **Enforce, where the sandbox cannot engage.** The job is
  refused.

`runner/tests/test_v4_the_place.py` holds this on every suite
run. The 22 atoms are not changed. The default cap stays
1,048,576.
