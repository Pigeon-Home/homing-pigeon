# Personal-documents shelter

The personal-documents warning (see
`personal-documents-warning.md`) says a machine looks like it
holds somebody's important papers, and recommends not running
the runner there. The shelter is the other answer to the same
situation, for a machine the operator means to use anyway: an
old virtual machine that once held tax papers, a family computer
that also runs jobs. Run by hand, the shelter gathers the
documents the warning would trip on into one folder on the
Desktop, out of the scattered places a job might meet them,
under the operator's own hand.

## What it does

The shelter uses the warning check's own name scan and watched
folders (home Documents, Desktop and Downloads, the paper
folders inside a OneDrive folder, and XDG-relocated folders).
An item whose name matches -- a tax folder, a passport scan, a
bank statement -- is moved into the shelter folder:

    Desktop/Sheltered Documents/<watched folder>/<item>

A folder whose name matches moves whole, with everything in it.
The shelter folder is created readable only by its owner, and
carries a marker file. The warning check treats a folder as the
shelter only when the marker is present with its exact text: a
folder that merely has the shelter's name is still scanned like
any other folder. After a sheltering, the gathered documents are
out of the check's scope, and the warning is quiet.

Nothing is deleted, and nothing is overwritten. A name that is
already taken inside the shelter gets a numbered suffix. The
only record is a manifest inside the shelter folder itself,
naming where each item came from; it stays on the operator's
machine, and nothing the shelter sees is logged or sent
anywhere.

## The modes

The shelter is gated by the config security mode for the
feature `personal_docs_shelter`, in the family's usual shape:

| Mode | What the tool may do |
|------|----------------------|
| `off` | Refuses to plan or apply. |
| `audit` | Plans only. `--apply` prints the plan and moves nothing. |
| `enforce` | `--apply` moves the planned items. Planning stays the default. |

Nothing runs at startup. The mode gates what the tool may do
when the operator runs it; the operator's `--apply` is what
moves files. A config that does not set the feature gets the
family default, `enforce`.

## Running it

Plan first (the default; changes nothing):

    python -m runner.oracle.personal_docs_shelter --config config.json

Shelter:

    python -m runner.oracle.personal_docs_shelter --config config.json --apply

Put everything back:

    python -m runner.oracle.personal_docs_shelter --config config.json --restore

Restore never overwrites: if an item's original place is
occupied again, that item stays in the shelter, still recorded
in the manifest, and the tool reports it. The manifest is
validated before anything moves -- a manifest that is malformed,
points outside the shelter, or points outside the home
directory stops the run with nothing moved.

## What it never does

- It never runs on its own. No startup path calls it.
- It never deletes a document, and never overwrites one.
- It never opens a document. Like the warning check, it reads
  names only.
- It never leaves the machine. The manifest lives inside the
  shelter folder; names are printed only on the operator's own
  terminal.
- It does not decide whether the runner should be installed.
  The warning's advice stands; the shelter is for the operator
  who has decided, and wants the papers gathered first.
