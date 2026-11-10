# The 3.16 rev: preparation plan for the official release

Dated 2026-11-09. Preparation only: this plan cuts nothing.
No version carrier in the tree moves until the gate in
section 4 is green and the cut is made in the order section 2
sets out. The wording of the release notes for the official
release is not decided; this plan calls it the official
release throughout and settles nothing about the notes.

## 1. What the rev is, and what already supports it

The rev takes the standing release line from 3.15 to 3.16:
the first release cut on the 3.16 line is the official
release — the release that presents the project as done,
secure by default, with its documentation fully updated.
Releases after it stay on the 3.16 line under the standing
odometer rules until a later line is deliberately cut.

The machinery already supports the move; no version code
changes are needed:

- `runner/ops/version4.py` takes `--minor N` on its `next`
  command. A minor above the standing line restarts the
  counter at 1 and carries the measured token figure; the
  major is carried through unchanged; a minor below the
  standing line is refused.
- The behaviour is pinned at the function level in
  `runner/tests/test_version4.py` (a minor increase restarts
  the counter; a minor increase outside the measure window
  takes the fresh figure; the same minor is not a restart; a
  decrease is rejected; the major never moves).
- The CLI seam the ship flow calls is pinned by 4 tests added
  with this plan (`test_next_command_minor_bump_*` and
  neighbours in the same file): the bump through `main()`,
  the bump taking the fresh figure under `--fresh`, the
  same-minor flag as a no-op, and a decrease refused at the
  CLI.
- Probe, run against the standing tree before this plan was
  written: with a cached figure of 20 the `next` command
  prints the 16 line at counter 1 when `--minor 16` is
  passed, and the next counter on the 15 line when it is
  not. The flag is passed exactly once, at this cut; later
  cuts read the standing version from the tree and stay on
  the new line without it.

## 2. The ordered change map

The cut follows the freeze order the release procedure
already states (docs/steady/use/use-runbook.md, Job 4):
measure first, the statistics write as the last content
commit before the release commit.

1. **Gate check.** Section 4's gate is green, including the
   Gate 5 sign-off over the candidate (section 4, last
   item). Nothing below starts before it.
2. **Fresh uncached recount.** On the tree being shipped,
   `python3 runner/ops/version4.py next <standing version>
   --fresh --minor 16` produces the target version, of the
   shape 3.16.<fresh millions>.1. The figure is the recount
   taken at this cut, never a reused one (the standing rule
   for every cut), and the counter restarts at 1 because the
   minor increased.
3. **Statistics write — the last content commit.**
   `python3 runner/tools/refresh_figures.py --write`
   rewrites the facts block in
   docs/infrastructure-documents/project/statistics.md and
   every marked figure slot in the evergreen docs from the
   fresh measure. The record's basis prose is reviewed by
   hand in the same pass; its header names the line the
   measured head belongs to, and that reference moves from
   the 3.15 line to the 3.16 line in this pass, so the
   record never describes the new line's measure as the old
   line's.
4. **The release commit — one commit, 6 files.**
   - `pyproject.toml`: `version` set to the target.
   - `runner/_version.py`: `__version__` set to the target.
   - `runner/ops/install.py`: `__version__` set to the
     target.
   - `runner/tests/test_install_edges.py`: the pinned
     `__version__` expectation set to the target.
   - `runner/tests/test_version4.py`: the standing-version
     test's minor assertion moves from 15 to 16. It reads
     `pyproject.toml`, so it moves in this commit and no
     other: earlier leaves it asserting a line the tree is
     not on, later leaves the build red between the bump and
     the fix.
   - `docs/infrastructure-documents/changelog.md`: the new
     entry at the top, under the target version.
   The commit is made in the ship flow's standing form (its
   subject, its author, its no-reply release address) — this
   plan changes none of that.
5. **The tag.** The annotated tag for the target version is
   placed on the release commit. Tags are protected and
   never move; a defect is fixed forward under the next
   counter, as standing practice already holds.
6. **The publish legs.** The tag build runs the standing
   pipeline unchanged: build.yml produces the GitHub release
   (neither draft nor prerelease, held by
   `runner/tests/test_release_channel_polish.py`), the PyPI
   upload — the first upload carrying the Production/Stable
   development-status classifier, since published release
   metadata is immutable and the classifier set on the 3.15
   line's uploads cannot be rewritten — the SourceForge
   step (its tag ordering keys the 3.16 line above every
   3.15 tag, so the default-download marking follows the
   new release), and the GitLab release; docker.yml
   publishes the image and moves its latest tag.
7. **Verification.** The standing stamp check: the wheel,
   the sdist and the platform tarball re-downloaded and
   matched against the release's sums; the release's asset
   set complete; the GHCR latest tag resolving to the new
   release's digest; the release line reported once.

## 3. What the rev breaks or contradicts, and the fix each needs

- **`runner/tests/test_version4.py`, the standing-version
  test** asserts the minor is 15, with the comment that the
  minor is the 15 line. Breaks the moment the bump lands.
  Fix: scheduled inside the release commit (section 2,
  step 4). Until the rev executes it stays at 15 on purpose.
- **`runner/tests/test_install_edges.py`** pins the full
  standing version string. It moves in every release commit
  by standing practice; listed here so the rev's commit is
  checked against all 4 carriers, not 3.
- **`runner/ops/version4.py`, module docstring** describes
  the minor with the parenthetical "(the 15 in 3.15.x)".
  The sentence after it already states the rule (the minor
  moves only when a release is deliberately cut on a new
  minor line), so the docstring stays true in substance; the
  parenthetical names the old line as the example. Fix: in
  the release commit or the statistics pass, the
  parenthetical is reviewed and updated to name the current
  line, so the next reader is not handed a stale example.
- **`docs/infrastructure-documents/project/statistics.md`,
  header prose** names the measured head as the head from
  which the current release of the 3.15 line was cut. Fix:
  the hand review in step 3 of section 2.
- **`docs/checklist.txt`, first line** reads "soon rev 4.x".
  The file is the conductor's own and is not touched by
  this plan or by the rev. **The tension, flagged and not
  resolved:** the standing scheme as recorded for this
  project holds the minor at 15 for as long as the line
  serves, with the next deliberate move after the 15 line
  named as 4.0. Cutting 3.16 inserts a minor line that
  record does not name. The same checklist records
  "non-beta", which the official release satisfies on
  either number. Whether the official release is numbered
  3.16 or the line holds at 3.15 until 4.0 is the
  conductor's decision; this plan prepares the 3.16 path so
  the decision can be taken with the costs in front of it,
  and the rev does not execute until it is taken.
- **Checked and clear** (fixed historical inputs, not
  standing-version reads; no fix needed):
  `runner/tests/test_upgrade_proof.py` and
  `runner/tests/test_sourceforge_vkey.py` pin cross-scheme
  tag ordering with 3.15-line tags as data;
  `runner/tests/test_release_gate.py` uses an older release
  as fixture data; `runner/tests/test_release_channel_polish.py`
  records a dated channel audit of the standing release in
  its docstring, true as written. The release procedure in
  the use runbook describes the scheme generically ("the
  minor is the release line") and needs no change. The
  figure slots in AGENTS.md and PROTOCOL.md carry no
  version. The IETF drawer's status concerns the drafts'
  own revisions, not the product version.
  `runner/tests/test_doc_version_rot.py` bars the standing
  version string from evergreen docs; this plan carries no
  standing version string, and the rev's commits keep it
  that way.

## 4. The gate

The rev executes only when all 4 preparation lanes have
landed on main:

a. **Secure by default, finished.** The phase-2 fix list in
   the defaults record is closed test-first: no silent
   fail-open downgrade survives, and any downgrade that
   remains is loud, audited, and documented as such.
b. **The documentation sweep.** Every documentation file in
   the tree inventoried and either cleared or edited, with
   the coverage provable from the sweep's own report, so the
   official release's documents nowhere present the project
   as not ready.
c. **The readiness checklist and the fresh dormant-code
   audit.** The checklist stands in the tree, and the
   statistics record's non-latent figure rests on a fresh
   audit rather than the 2026-11-03 audit it currently
   carries.
d. **The channel polish.** The distribution channels
   present a full release: the PyPI classifier reads
   Production/Stable, the SourceForge development status
   reads Production/Stable, the GitHub latest release is
   neither draft nor prerelease, and the GHCR latest tag
   resolves to the current release. (Landed ahead of this
   plan: the classifier commit stands at the head this plan
   was written on, and the channel audit it records is the
   evidence for this item.)

And, as for any release, **Gate 5** (release-gate.md): the
conductor's checklist worked over the candidate and the
sign-off signed. The signature is a person's; it is not
delegated, and the rev waits for it like every other cut.

## 5. State at writing, and what remains

At the writing of this plan: item (d) of the gate has
landed; items (a), (b) and (c) are in flight. The machinery
probe in section 1 has run, and the CLI pinning tests stand
committed with this plan. What remains before the bump can
be executed:

1. The 3 in-flight gate items land on main.
2. The conductor's decision on the checklist tension in
   section 3.
3. The Gate 5 sign-off over the candidate the trains
   produce.
4. The cut itself, in the order section 2 sets out.

After the cut, the trains run on the 3.16 line with no
further machinery change: the counter increments, the token
figure follows the standing odometer and hold rules, and
the freeze order (measure first, statistics write last) is
unchanged.
