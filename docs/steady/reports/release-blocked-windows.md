# 3.14.43: the cut is blocked on the Windows test leg

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

Written 30-OCT 6:10PM PST; a record of findings, not a fix.
Version 3.14.43 stood on main with no tag: cut-release.yml's
guard found no 3.14.43 commit with a green, non-cancelled
build-windows check run, and the one build that ran the full
matrix to completion on a 3.14.43 commit failed in the Windows
test leg. The last green build-windows was 74cfa3f4, the commit
v3.14.42 was cut from, at 30-OCT 12:29PM PST. Corpus-only
pushes skip the matrix, so they can never satisfy the guard.
The cause, the fix and the cut are in release.md.
