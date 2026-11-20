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
  row `pwd; printf x`, and every step of M. A step is the
  shortest row that reaches one of M's 4 states, then one
  joiner and one atom. There are 352. Each result is M's,
  with the folder set to `/work` and `HOME` set to the
  host's.
- **The long rows, enforce.** Not only the short steps. Rows
  drawn from all 22 atoms and all 4 joiners, each as likely
  as any other of its length, the same rows on every run:
  8 of 50 characters, 8 of 500, and 4 of 5,000. Each result
  is M's, at `/work`. Each cuts back into the atoms and the
  joiners it was built from, in the one way the grammar
  allows.
- **The ladder, enforce.** The shell's ladder was measured
  with confinement off. The first 20 families, `true` joined
  to `true`, to `:`, to `pwd` and to `false`, in each of the
  5 ways, were run again under enforce. Step 10 is 55 atoms
  and step 17 is 1,597. 40 rows. Each result is M's, at
  `/work`. 0 differences.
- **Off.** Every atom is M's with the host folder. The 19 atoms
  that do not read the place have the same result as under
  enforce. `pwd` does not: it prints the host folder. The two
  `HOME` atoms do, because `HOME` is passed in either way.
- **Enforce, where the sandbox cannot engage.** The job is
  refused.

`runner/tests/test_v4_the_place.py` holds this on every suite
run. The 22 atoms are not changed. The default cap stays
1,048,576.
