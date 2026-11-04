# The steady folder

Status: a proposal, shown on the DRU branch. Main is unchanged.

## The problem

The tree holds 232 markdown files, and finding the 1 file to edit
means hunting through folders to reach it. The working set is
small: the documents edited by hand, day to day, can nearly be
counted on 1 hand — `future.md` chief among them, and it sat 2
folders deep in `docs/project/`. Everything else is library:
needed, referenced, and rarely opened. A library does not need to
stand in the doorway.

## The rule

1. Placement is decided by timestamps read from main's history,
   never from a branch — branches rewrite times. A commit counts
   as use only when it touches a document individually; a bulk
   sweep that touches everything at once counts for nothing. A
   file with no individual touch in 5 days shelves to
   `docs/steady/`, flat, under its own name: steady holds no
   folders, so a topic folder can never stand in 2 places at
   once. 1 file, 1 home.
2. Editing a steady file for real work moves it back out in the
   same change. Steady is a shelf, not an archive: nothing there
   is frozen, retired, or less true. It is simply not in the way.
3. Exempt: the root front door (README.md, PROTOCOL.md,
   AGENTS.md, and the other root files — the face of the
   repository), the markdown that lives with code under `runner/`
   (it travels with what it describes), and `.github/`.
4. A file the project edits by hand every day rises to the top of
   `docs/`. `future.md` now sits at `docs/FUTURE.md`, the only
   file at the top, and the living pointers to it were updated
   in the same pass. Historical records keep the paths they were
   written with. The file at the top of `docs/` is uppercase;
   every file inside the 4 folders is lowercase, as the project's
   convention dictates. The changelog works for a living — every
   release writes in it — so it stands at the top of
   `infrastructure-documents/` as `changelog.md`; contributing is nobody's
   working file, so it shelves in `steady/`.

## The top of docs/

The top level of `docs/` holds 4 folders, and the working files
beside them:

- `archive/` — the frozen record; left where it is for now.
- `ietf/` — the drafts, 1 folder per draft.
- `infrastructure-documents/` — everything else, each folder keeping its
  name and its shape underneath.
- `steady/` — the shelf, per the rule above.

The file at the top is the working set: FUTURE.md. Opening
`docs/` is 1 short list — nothing in it needs a scroll to find.

## What the rule did today

Measured from git history on main, 2026-11-04, counting only
individual touches (a commit touching more than 40 documents at
once is a sweep, not use):

- Of the general documents, 58 markdown files were touched
  individually within the last 5 days, and 91 have never been
  touched individually at all — sweep commits are the only hands
  that have reached them.
- A strict 5-day clock over raw timestamps would have shelved
  nothing: a bulk pass on 2026-11-01 touched every archive file
  in the same minute. That is why the clock reads individual
  touches only.
- The placement then ran over all 288 files under `docs/` on
  this branch: 125 files shelved flat into `docs/steady/`, 95
  warm files stand in `docs/infrastructure-documents/` in their topic
  folders, and oracle — the folder that stood in both places —
  now stands in exactly 1.

## Checking what is due for the shelf

Read the times from main, newest first, and take each file's
first individual touch, skipping sweep commits:

```
git log --format='COMMIT %cI' --name-only main -- docs/
```

Any file under `docs/` whose first individual touch is more
than 5 days old — or which has none — is due to shelve flat in
`docs/steady/`, and any steady file being edited is due to move
back out into its topic folder in `docs/infrastructure-documents/`.

## What landing this on main would still need

- A link-repair pass: relative links between documents shift
  when a file is shelved or raised. This branch updated the
  living pointers to `future.md`; the rest of the web of links
  is checked as part of landing, not before.
- The guard registries on main name document paths (the
  DocDriftGuard rows among them); a shelved file's rows move
  with it.
- The doc-edit release watch keys on any `*.md` path wherever
  it sits, so it needs no change.
