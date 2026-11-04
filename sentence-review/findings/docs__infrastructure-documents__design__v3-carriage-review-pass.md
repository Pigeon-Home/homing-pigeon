# Findings — docs/infrastructure-documents/design/v3-carriage-review-pass.md

Source: docs/infrastructure-documents/design/v3-carriage-review-pass.md, reviewed at main c498f6fd.
Sentence units: 243. Flagged: 22. Categories: pre-release 190, post-release 53.

A review pass over the version 3 carriage: a decision at the top, where the draft stands, the 2 defects described and fixed, then editorial items, open work, the IETF side, ideas, and a closing sequence of what to do first. Inside each section the argument runs connected; the flags are the note's own labels and table structure standing where sentences should be, plus a few shards. Plan and recommendation units are categorized post-release; the review of what stands is pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Decision, 2 November, after this note landed." | pre-release | flagged | A dateline fragment ("Decision, 2 November…") with no verb; the decision's substance arrives in the units after it |
| 2 | "The two defects in section 1 are real…" | pre-release | flows |  |
| 3 | "A session hold is a sidecar beside the…" | pre-release | flows |  |
| 4 | "An expiry deletes only the holds whose result…" | pre-release | flows |  |
| 5 | "Section 10.3 of the local draft now says…" | pre-release | flows |  |
| 6 | "The tests are in `test_dtls_email_v3.py`." | pre-release | flows |  |
| 7 | "The rest of this note is not implemented." | pre-release | flows |  |
| 8 | "The media-type tree, the editorial sentences, the combination…" | pre-release | flows |  |
| 9 | "One sentence in section 5 named an internal…" | pre-release | flows |  |
| 10 | "Posted drafts -01 through -03 are not revised…" | pre-release | flows |  |
| 11 | "Read against `main` at `b75538d` (release 3.15.129), 02-NOV…" | pre-release | flows |  |
| 12 | "Section 1 is implemented; see the decision at…" | pre-release | flows |  |
| 13 | "The rest of this note is the list…" | pre-release | flows |  |
| 14 | "Section 2 is the rest of what this…" | pre-release | flows |  |
| 15 | "Section 3 is the work the two reviews…" | pre-release | flows |  |
| 16 | "Section 4 is the IETF side." | pre-release | flows |  |
| 17 | "Section 5 is a longer list of ideas…" | pre-release | flows |  |
| 18 | "Section 6 is what I would do first." | pre-release | flows |  |
| 19 | "The question this pass had to answer first…" | pre-release | flows |  |
| 20 | "Checked against the text at `b75538d`, not against…" | pre-release | flows |  |
| 21 | "Grok's 6:10pm peer review, items 1 to 8:…" | pre-release | flows |  |
| 22 | "Muse's 6:44pm pass landed them; I re-read each…" | pre-release | flows |  |
| 23 | "Grok's 7:10pm read-back, the four disagreements (the uncapped…" | pre-release | flows |  |
| 24 | "The version 3 module runs 70 tests green…" | pre-release | flows |  |
| 25 | "Grok's 7:40pm avenues: 2 (the session does not…" | pre-release | flows |  |
| 26 | "Avenue 1 is partly done (early data, `psk_ke`,…" | pre-release | flows |  |
| 27 | "Avenue 3 is partly done (the fallback choice…" | pre-release | flows |  |
| 28 | "Avenue 5, the lifetime table, is Section 3.4,…" | pre-release | flows |  |
| 29 | "Avenues 6 and 9 are Sections 3.5 and…" | pre-release | flows |  |
| 30 | "Grok's pass at `c3386c7` and `537eceb` took the…" | pre-release | flows |  |
| 31 | "Each one checked against the code." | pre-release | flows |  |
| 32 | "`PROTOCOL.md` links the local version 3 source (`2758cab`)." | pre-release | flows |  |
| 33 | "`docs/ietf/STATUS.md` has a version 3 section (`b75538d`)." | pre-release | flows |  |
| 34 | "Still outside the draft: the title/docname decision; idnits…" | pre-release | flows |  |
| 35 | "Plus everything in Sections 1 and 2 below." | pre-release | flows |  |
| 36 | "Both were found by reading `runner/transport_extensions/email/__main__.py` and then…" | pre-release | flows |  |
| 37 | "The transcript lines below are the runner's own…" | pre-release | flows |  |
| 38 | "Both are the downgrade Section 12 forbids by…" | pre-release | flows |  |
| 39 | "What the code does." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 40 | "The hold that keeps a session's result off…" | pre-release | flows |  |
| 41 | "It is written when a job is delivered…" | pre-release | flows |  |
| 42 | "Nothing writes it to disk." | pre-release | flows |  |
| 43 | "The result file it guards, `<ident>.result.txt` in the…" | pre-release | flows |  |
| 44 | "The hold does not." | pre-release | flows |  |
| 45 | "After the process restarts, `flush_results` finds the result,…" | pre-release | flows |  |
| 46 | "The demonstration: a session established, one signed job…" | pre-release | flows |  |
| 47 | "The same thing happens to a job that…" | pre-release | flows |  |
| 48 | "Why it is the forbidden case and not…" | pre-release | flows |  |
| 49 | "Section 9.4 was written in `fd83d58` and says…" | pre-release | flows |  |
| 50 | "The code keeps the hold in the process." | pre-release | flows |  |
| 51 | "A deploy, a crash, or the next release…" | pre-release | flows |  |
| 52 | "On this carriage a restart between a job's…" | pre-release | flows |  |
| 53 | "The fix, described." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 54 | "Make the hold as durable as the result…" | pre-release | flows |  |
| 55 | "At delivery, write a small sidecar next to…" | pre-release | flows |  |
| 56 | "When the core moves the job to done…" | pre-release | flows |  |
| 57 | "`_session_bound` and `_hold_owner` read the sidecars, not only…" | pre-release | flows |  |
| 58 | "Nothing secret goes in the sidecar: a connection…" | pre-release | flows |  |
| 59 | "Traffic keys stay where Section 16.1 puts them,…" | pre-release | flows |  |
| 60 | "The alternative, one JSON file per channel rewritten…" | pre-release | flows |  |
| 61 | "The tests, described." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 62 | "Three cells in `test_dtls_email_v3`: a result in the…" | pre-release | flows |  |
| 63 | "Each one asserts the count of ordinary mails,…" | pre-release | flows |  |
| 64 | "The draft, one sentence in Section 10.3, after…" | pre-release | flows |  |
| 65 | "The sentence is true today of the draft…" | pre-release | flows |  |
| 66 | "What the code does." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 67 | "`_expire_session_results` builds `held` from the result files in…" | pre-release | flows |  |
| 68 | "`still` is the set of idents that still…" | pre-release | flows |  |
| 69 | "A job that was delivered from a session…" | pre-release | flows |  |
| 70 | "The prune meant "forget the holds of the…" | pre-release | flows |  |
| 71 | "The demonstration: job B delivered and run, its…" | pre-release | flows |  |
| 72 | "The fix, described." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 73 | "Prune by the doomed idents, not by the…" | pre-release | flows |  |
| 74 | "With the sidecar of 1.1 in place the…" | pre-release | flows |  |
| 75 | "The existing expiry tests keep passing; one new…" | pre-release | flows |  |
| 76 | "No draft change: Section 10.3 already bounds the…" | pre-release | flows |  |
| 77 | "The 7:35pm card keeps the test runner un-restarted…" | pre-release | flows |  |
| 78 | "Both of those are now closed." | pre-release | flows |  |
| 79 | "The no-restart rule is load-bearing again, for 1.1:…" | pre-release | flows |  |
| 80 | "Either fix 1.1 and 1.2 before the window,…" | post-release | flows |  |
| 81 | "I would fix them first; the change is…" | post-release | flows |  |
| 82 | "Smaller, each with the change described." | pre-release | flagged | A lead-in fragment ("Smaller, each with the change described."); the smaller items arrive without a sentence to carry them |
| 83 | "Draft section numbers are the current text's." | pre-release | flows |  |
| 84 | "`application/hp-dtls3` is a subtype name in the standards…" | pre-release | flows |  |
| 85 | "RFC 6838 Section 3.1 reserves that tree for…" | pre-release | flows |  |
| 86 | "The two honest shapes are the unregistered tree,…" | pre-release | flows |  |
| 87 | "The personal tree, `application/prs.hp-dtls3`, is the same as…" | pre-release | flows |  |
| 88 | "My preference is the vendor tree, requested in…" | post-release | flows |  |
| 89 | "The string lives in `runner/wire/dtls_mailbox.py`, the tests, the…" | pre-release | flows |  |
| 90 | "Do not change it before the cold test;…" | post-release | flows |  |
| 91 | ""The 'SS' of this version's name for the…" | pre-release | flows |  |
| 92 | "The -01 revisions of versions 1 and 2…" | pre-release | flows |  |
| 93 | "Replace the clause with the sentence the 5:38pm…" | post-release | flows |  |
| 94 | "Section 16.1 says it; the profile section should…" | pre-release | flows |  |
| 95 | ""A deployment MUST NOT add a sender allowlist…" | pre-release | flows |  |
| 96 | "That is the 5:38pm review's split (a reasonable…" | pre-release | flows |  |
| 97 | "The first bullet says a fresh ClientHello costs…" | pre-release | flows |  |
| 98 | "Say "no session state" in the first bullet…" | post-release | flows |  |
| 99 | "The ticket table is in the server core's…" | pre-release | flows |  |
| 100 | "On this carriage a resumption may come days…" | pre-release | flows |  |
| 101 | "Add one sentence to Section 9.3: a responder…" | post-release | flows |  |
| 102 | "Do not persist the ticket key to make…" | post-release | flows |  |
| 103 | "The proof note should say "resumption across a…" | post-release | flows |  |
| 104 | "The rule that a later same-key session carrying…" | pre-release | flows |  |
| 105 | "With the real core, the repeated job reaches…" | pre-release | flows |  |
| 106 | "Confirm the core writes no refusal result for…" | pre-release | flows |  |
| 107 | "The test: the same-key cell of `fd83d58`, with…" | pre-release | flows |  |
| 108 | "`_is_client_hello` in `dtls_mailbox.py` returns true for a fragment…" | pre-release | flows |  |
| 109 | "The behavior matches the draft as Grok rewrote…" | pre-release | flows |  |
| 110 | "The name does not: Section 8.2 now says…" | pre-release | flows |  |
| 111 | "One line and one test." | pre-release | flagged | A verdict shard ("One line and one test."); no sentence shape and no hand-off |
| 112 | "Two small things." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence |
| 113 | "The prefix rule is prose only; add the…" | post-release | flows |  |
| 114 | "And `1*gap` is `1*(1*gap-char)`, a redundancy; write `gap`." | pre-release | flows |  |
| 115 | "Neither changes what any implementation does." | pre-release | flows |  |
| 116 | "Version 1's -03 writes small counts as words…" | pre-release | flows |  |
| 117 | "The RFC Editor normalizes this and a reviewer…" | pre-release | flows |  |
| 118 | "One pass, prose only: words for counts under…" | post-release | flows |  |
| 119 | "Not a blocker; do it with the submission…" | post-release | flows |  |
| 120 | "Sentences that are true of a local draft…" | pre-release | flows |  |
| 121 | "Put the list in `STATUS.md` now, as the…" | post-release | flows |  |
| 122 | "Version 2's -03 was posted to drop the…" | pre-release | flows |  |
| 123 | "Both forms are accepted by the datatracker and…" | pre-release | flows |  |
| 124 | "Pick one rule for all three drafts." | post-release | flows |  |
| 125 | "My preference: the reference block names the revision…" | pre-release | flows |  |
| 126 | "If version 1 goes to -04 before version…" | pre-release | flows |  |
| 127 | "`README.md` lists the version 1 and version 2…" | pre-release | flows |  |
| 128 | "`PROTOCOL.md` points "the technical protocol description" for versions…" | pre-release | flows |  |
| 129 | "Those are plain-markdown readable copies of the -00…" | pre-release | flows |  |
| 130 | "Decide what those two files are: a readable…" | post-release | flows |  |
| 131 | "Version 3 has no such copy; its `PROTOCOL.md`…" | pre-release | flows |  |
| 132 | "The 7:10pm note's matrix, each cell asserting the…" | pre-release | flows |  |
| 133 | "A typed part, a disclaimer in the text…" | pre-release | flows |  |
| 134 | "Expect one datagram, one answer, no second transfer." | pre-release | flows |  |
| 135 | "One `Re:` on a flight whose typed part…" | pre-release | flows |  |
| 136 | "Expect `dtls-invalid` (or not-a-flight), no session, no exception…" | pre-release | flows |  |
| 137 | "Early data spliced into a hello that is…" | pre-release | flows |  |
| 138 | "Expect the rejection to be a property of…" | pre-release | flows |  |
| 139 | "Two submitters, two keys, one ident, both sessions…" | pre-release | flows |  |
| 140 | "The `fd83d58` cell kills the first session; this…" | pre-release | flows |  |
| 141 | "The restart cells of Section 1.1." | pre-release | flows |  |
| 142 | "Avenue 1 of the 7:40pm note." | pre-release | flows |  |
| 143 | "Modes the shared engine can still perform that…" | pre-release | flows |  |
| 144 | "The ticket rule is the one with a…" | pre-release | flows |  |
| 145 | "Either version 1's -04 says what the code…" | post-release | flows |  |
| 146 | "I would let the text follow the code." | post-release | flows |  |
| 147 | "Avenue 2's second question." | pre-release | flows |  |
| 148 | "From `PROTOCOL.md` Section 14.1, marking which fields constrain…" | pre-release | flows |  |
| 149 | "| Field | Binds | Omissible by the…" | pre-release | flagged | A table header row — structure, not a sentence |
| 150 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 151 | "| `allowed_kinds` | `kind` | no | none…" | pre-release | flows |  |
| 152 | "| `allowed_interpreters` | the effective interpreter | yes…" | pre-release | flows |  |
| 153 | "| `max_timeout_sec` | the effective timeout | yes…" | pre-release | flows |  |
| 154 | "| `allowed_recipes` | `recipe` | no | none…" | pre-release | flows |  |
| 155 | "| `allowed_script_sha384` | the inline `script` | no…" | pre-release | flows |  |
| 156 | "| `allowed_env`, `denied_env`, `allow_dangerous_env` | env names |…" | pre-release | flows |  |
| 157 | "| `allowed_files`, `allow_file_urls` | staged file names and…" | pre-release | flows |  |
| 158 | "| `max_args`, `args_pattern` | args | yes |…" | pre-release | flows |  |
| 159 | "The two rows that bind a default are…" | pre-release | flows |  |
| 160 | "The deliverable is one sentence in Section 14.1…" | post-release | flows |  |
| 161 | "The signed preview the submitter sees does not…" | pre-release | flows |  |
| 162 | "Avenue 5, drafted here." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 163 | ""Path" is the lifetime the carriage's delay forces;…" | pre-release | flows |  |
| 164 | "| Row | Lifetime today | Lifetime the…" | pre-release | flagged | A table header row — structure, not a sentence |
| 165 | "|---|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 166 | "| `shared_secret`, additional secrets | configuration | indefinite…" | pre-release | flows |  |
| 167 | "| cookie key | file in the channel,…" | pre-release | flows |  |
| 168 | "| ticket table (responder) | process | a…" | pre-release | flows |  |
| 169 | "| resumption PSK (initiator) | the client object…" | pre-release | flows |  |
| 170 | "| handshake keys | the handshake | the…" | pre-release | flows |  |
| 171 | "| traffic keys | the session | the…" | pre-release | flows |  |
| 172 | "| mail session-id to connection-id binding | the…" | pre-release | flows |  |
| 173 | "| saved last flight and re-post flag |…" | pre-release | flows |  |
| 174 | "| digest cache | process (4096, FIFO) |…" | pre-release | flows |  |
| 175 | "| held results (files) | disk, 7 days…" | pre-release | flows |  |
| 176 | "| the hold map `_job_session` | process |…" | pre-release | flows |  |
| 177 | "| reply-to target sidecar | disk | until…" | pre-release | flows |  |
| 178 | "The table's one surprise is the hold map,…" | pre-release | flows |  |
| 179 | "Avenue 6." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 180 | "One test holds the rule that no field…" | pre-release | flows |  |
| 181 | "The inventory of what an observer learns is…" | pre-release | flows |  |
| 182 | "Avenue 3's question." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 183 | "The one-prefix rule is a hole cut on…" | pre-release | flows |  |
| 184 | "Record, from the live mailbox's history rather than…" | post-release | flows |  |
| 185 | "If none has, the stricter rule (refuse every…" | post-release | flows |  |
| 186 | "Either way the record goes in the proof…" | post-release | flows |  |
| 187 | "Still the one open decision." | pre-release | flagged | A verdict fragment ("Still the one open decision.") standing alone between sections |
| 188 | "Both reviews and the read-back say leave `draft-slutsky-homing-pigeon-v3-00`…" | pre-release | flows |  |
| 189 | "I agree, with one addition: the name follows…" | pre-release | flows |  |
| 190 | "If it is ever renamed, rename it as…" | post-release | flows |  |
| 191 | "The rendered `.txt`, `.html` and `.xml` beside the…" | pre-release | flows |  |
| 192 | "This matters twice: the cold test hands a…" | pre-release | flows |  |
| 193 | "Where it can run: not in the container…" | pre-release | flows |  |
| 194 | "The -01 renders and idnits runs were made…" | pre-release | flows |  |
| 195 | "The idnits that runs is `@ietf-tools/idnits` on npm…" | pre-release | flows |  |
| 196 | "What to commit: the three renders and `draft-slutsky-homing-pigeon-v3-00.idnits.txt`…" | post-release | flows |  |
| 197 | "The durable version: a GitHub Actions workflow that…" | post-release | flows |  |
| 198 | "Then a stale render is a red check…" | post-release | flows |  |
| 199 | "Still unproven on a real mailbox: the MIME…" | pre-release | flows |  |
| 200 | "The 7:35pm card pins its links to `22bfeedf`…" | pre-release | flows |  |
| 201 | "Re-pin to `v3.15.129` or later, because three rules…" | post-release | flows |  |
| 202 | "`runner/tests/test_ietf_draft_conformance.py` pins the sentences of version 1 that…" | pre-release | flows |  |
| 203 | "Version 3 has none." | pre-release | flows |  |
| 204 | "The same pattern, for the sentences this pass…" | pre-release | flagged | A sentence shard ("The same pattern, for the sentences this pass…"); the thought completes only in the next unit |
| 205 | "Cheap, and it is how the next edit…" | pre-release | flows |  |
| 206 | "The calendar." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 207 | "The IETF 127 cut-off for all drafts, including…" | pre-release | flows |  |
| 208 | "The submission tool stays closed from the cut-off…" | pre-release | flows |  |
| 209 | "Verify the reopening on the submit page that…" | post-release | flows |  |
| 210 | "What the upload needs." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 211 | "The `.xml` from the render (RFC 7991 vocabulary,…" | pre-release | flows |  |
| 212 | "A new document name is a new document…" | pre-release | flows |  |
| 213 | "After posting." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 214 | "The request to `rfc-ise@rfc-editor.org`, as for versions 1…" | pre-release | flows |  |
| 215 | "Version 1 is still published first; version 3's…" | pre-release | flows |  |
| 216 | "The edits of Section 2.10 go in before…" | pre-release | flows |  |
| 217 | "Two optional things." | pre-release | flagged | A section label standing as its own paragraph — structure, not a sentence; the prose it heads arrives in the next unit |
| 218 | "A courtesy note to the TLS working group's…" | post-release | flows |  |
| 219 | "And a restructure of Section 16 in the…" | post-release | flows |  |
| 220 | "Post version 3 the day the tool reopens,…" | post-release | flows |  |
| 221 | "Fix 1.1 and 1.2 before the cold test,…" | post-release | flows |  |
| 222 | "Run the cold test (First Light) against the…" | post-release | flows |  |
| 223 | "Turn the combination cells of 3.1 into the…" | post-release | flows |  |
| 224 | "The conformance pin of 3.10, so the draft…" | post-release | flows |  |
| 225 | "The lifetime table of 3.4 as a short…" | post-release | flows |  |
| 226 | "The policy-field sentence of 3.3 in `PROTOCOL.md` Section…" | post-release | flows |  |
| 227 | "The media type decision of 2.1, decided now…" | post-release | flows |  |
| 228 | "The render-and-idnits workflow of 3.8, so the renders…" | post-release | flows |  |
| 229 | "A live run of the MIME sender against…" | post-release | flows |  |
| 230 | "The `Re:` observation of 3.6 from the mailbox…" | post-release | flows |  |
| 231 | "The readable-copy decision of 2.13 for versions 1…" | post-release | flows |  |
| 232 | "One citation rule across the three drafts (2.11),…" | post-release | flows |  |
| 233 | "Version 1's -04, when there is a reason…" | post-release | flows |  |
| 234 | "The hybrid share revision, later and on its…" | post-release | flows |  |
| 235 | "A platform-card field for the discovery fact in…" | post-release | flows |  |
| 236 | "A `STATUS.md` line per expiry: the version 1…" | post-release | flows |  |
| 237 | "The -00 copies of versions 1 and 2…" | post-release | flows |  |
| 238 | "GitHub Discussions, which `STATUS.md` names as the review…" | post-release | flows |  |
| 239 | "Section 1.1 and 1.2, with the tests, in…" | post-release | flows |  |
| 240 | "Sections 2.2, 2.3, 2.4, 2.5 and 2.7: four…" | post-release | flows |  |
| 241 | "Re-render where the toolchain is, run idnits in…" | post-release | flows |  |
| 242 | "The README line (2.12) and the submission checklist…" | post-release | flows |  |
| 243 | "Then 3.1, 3.10, 3.5 and 3.3 in that…" | post-release | flows |  |
