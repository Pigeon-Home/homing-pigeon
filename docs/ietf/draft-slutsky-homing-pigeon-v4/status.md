# Version 4 — draft-slutsky-homing-pigeon-v4

- Working draft: -00, dated 2026-11-18. NOT POSTED. The author
  posts drafts himself; nothing in this folder has been
  submitted to the datatracker, and there is no `submitted/`
  set.
- `source/` holds the draft and its local renders (text, XML,
  HTML), rendered with kramdown-rfc and xml2rfc from the .md
  source.
- The draft binds versions 1, 2 and 3 to the provable model:
  the constraint inventory C1 to C31, the properties P1 to
  P13, their TLA+ models and TLC verdicts, the general
  statement G and its model, and the findings
  F1 to F9, all of which live on the proofs shelf in
  `docs/infrastructure-documents/proofs/`.
- Fresh idnits check 2026-11-18, submission mode, on the text
  and the XML: nit-free, 0 errors, 0 warnings, 0 comments.
  The run stands in the `.idnits.txt` beside the source.
- Every named value in the draft is pinned against the code
  and the working papers by `runner/tests/test_v4_draft.py`.
