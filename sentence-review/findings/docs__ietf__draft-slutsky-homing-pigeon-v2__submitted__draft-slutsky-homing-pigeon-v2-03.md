# Findings — docs/ietf/draft-slutsky-homing-pigeon-v2/submitted/draft-slutsky-homing-pigeon-v2-03.md

Source: docs/ietf/draft-slutsky-homing-pigeon-v2/submitted/draft-slutsky-homing-pigeon-v2-03.md, reviewed at main 47232c1a.
Sentence units: 260. Flagged: 6. Categories: pre-release 260, post-release 0.

A frozen submitted Internet-Draft, the version 2 companion at its -03 revision: specification prose in RFC order, the same shape as its -00 with the revision's deltas. The prose is definitional and chains by section; the field tables sit inside the prose that introduces them. The non-sentences are the 6 table header rows (units 47, 86, 170, 173, 210, 213); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "title: "Homing Pigeon Message Protocol, Version 2: Determinations,…" | pre-release | flows |  |
| 2 | "ins: "A." | pre-release | flows |  |
| 3 | "Slutsky" name: "Andrew Slutsky" organization: "Independent" email: "slutsky5544@gmail.com"" | pre-release | flows |  |
| 4 | "normative: I-D.slutsky-homing-pigeon: title: "Homing Pigeon Message Protocol, Version…" | pre-release | flows |  |
| 5 | "name: "Andrew Slutsky" ins: "A." | pre-release | flows |  |
| 6 | "Slutsky" date: 2026-10 seriesinfo: Internet-Draft: draft-slutsky-homing-pigeon" | pre-release | flows |  |
| 7 | "--- abstract" | pre-release | flows |  |
| 8 | "This document specifies version 2 of the Homing…" | pre-release | flows |  |
| 9 | "Version 2 is an addition to version 1…" | pre-release | flows |  |
| 10 | "The additions are a determination message, by which…" | pre-release | flows |  |
| 11 | "Version 2 is backwards compatible." | pre-release | flows |  |
| 12 | "A version 1 runner never sends a version…" | pre-release | flows |  |
| 13 | "A submitter that implements this document adapts to…" | pre-release | flows |  |
| 14 | "There is no version negotiation and no handshake;…" | pre-release | flows |  |
| 15 | "The deployment that motivates version 2 is the…" | pre-release | flows |  |
| 16 | "Version 1 leaves such a runner alone with…" | pre-release | flows |  |
| 17 | "Version 2 lets it ask." | pre-release | flows |  |
| 18 | "--- middle" | pre-release | flows |  |
| 19 | "Version 1's core exchange is two messages: a…" | pre-release | flows |  |
| 20 | "The runner's decisions in version 1 are local:…" | pre-release | flows |  |
| 21 | "The result may carry the runner's opinion home…" | pre-release | flows |  |
| 22 | "Three gaps follow, and version 2 closes each…" | pre-release | flows |  |
| 23 | "The submitter cannot see the runner's expectation before…" | pre-release | flows |  |
| 24 | "A runner that expects a job to fail…" | pre-release | flows |  |
| 25 | "The determination message (Section 6) is that statement,…" | pre-release | flows |  |
| 26 | "A constrained runner cannot escalate." | pre-release | flows |  |
| 27 | "Where a full runner asks its local model…" | pre-release | flows |  |
| 28 | "The question message (Section 7) carries the question…" | pre-release | flows |  |
| 29 | "Each side plans from a partial picture." | pre-release | flows |  |
| 30 | "The submitter sees exit codes; the runner sees…" | pre-release | flows |  |
| 31 | "Context segments (Section 10) are the shared remedy:…" | pre-release | flows |  |
| 32 | "Every message in this document exists to move…" | pre-release | flows |  |
| 33 | "The figures in this document are normative in…" | pre-release | flows |  |
| 34 | "~~~ DECISION DECIDED BY ------------------- ------------------- admit or…" | pre-release | flows |  |
| 35 | "what the job will the runner, before probably…" | pre-release | flows |  |
| 36 | "a question the an enabled answerer, runner cannot…" | pre-release | flows |  |
| 37 | "the same question the runner, by its after…" | pre-release | flows |  |
| 38 | "what runs, finally the runner, always; no answer…" | pre-release | flows |  |
| 39 | "the next job the submitter, with the runner's…" | pre-release | flows |  |
| 40 | "Version 2 changes no version 1 message." | pre-release | flows |  |
| 41 | "A version 2 runner MUST accept version 1…" | pre-release | flows |  |
| 42 | "A version 2 message is sent only when…" | pre-release | flows |  |
| 43 | "A submitter that implements this document will routinely…" | pre-release | flows |  |
| 44 | "Realizing a runner does not support version 2…" | pre-release | flows |  |
| 45 | "The submitter adapts to the protocol version the…" | pre-release | flows |  |
| 46 | "~~~ Submitter (v2) Runner" | pre-release | flows |  |
| 47 | "job (v=1 object, as always)" | pre-release | flagged | Table header row, structure rather than a sentence |
| 48 | "--------------------------------->" | pre-release | flows |  |
| 49 | "if the runner is v2 and" | pre-release | flows |  |
| 50 | "the operator enabled it:" | pre-release | flows |  |
| 51 | "determination (v=2)" | pre-release | flows |  |
| 52 | "<---------------------------------" | pre-release | flows |  |
| 53 | "question (v=2)" | pre-release | flows |  |
| 54 | "<---------------------------------" | pre-release | flows |  |
| 55 | "answer (v=2)" | pre-release | flows |  |
| 56 | "--------------------------------->" | pre-release | flows |  |
| 57 | "result (v=1 object, with" | pre-release | flows |  |
| 58 | "context segments attached)" | pre-release | flows |  |
| 59 | "<---------------------------------" | pre-release | flows |  |
| 60 | "if the runner is v1:" | pre-release | flows |  |
| 61 | "none of the v2 lines" | pre-release | flows |  |
| 62 | "above ever happen, and" | pre-release | flows |  |
| 63 | "the exchange is exactly" | pre-release | flows |  |
| 64 | "the version 1 exchange." | pre-release | flows |  |
| 65 | "~~~" | pre-release | flows |  |
| 66 | "{::boilerplate bcp14-tagged}" | pre-release | flows |  |
| 67 | "The terms of draft-slutsky-homing-pigeon {{I-D.slutsky-homing-pigeon}} apply: submitter, runner,…" | pre-release | flows |  |
| 68 | "This document adds:" | pre-release | flows |  |
| 69 | "Determination: the runner's pre-execution statement of what it…" | pre-release | flows |  |
| 70 | "A determination is an opinion, formed from the…" | pre-release | flows |  |
| 71 | "Question: a question the runner's local decision machinery…" | pre-release | flows |  |
| 72 | "The reference software asks only for an exec…" | pre-release | flows |  |
| 73 | "Answer: a signed reply to one question, identified…" | pre-release | flows |  |
| 74 | "The answerer is any holder of a shared…" | pre-release | flows |  |
| 75 | "It does not have to be the party…" | pre-release | flows |  |
| 76 | "One answer decides; a late or second answer…" | pre-release | flows |  |
| 77 | "An answer never admits a job and never…" | pre-release | flows |  |
| 78 | "Local default: the decision the runner makes when…" | pre-release | flows |  |
| 79 | "Every question has one; asking never leaves a…" | pre-release | flows |  |
| 80 | "Deadline: the time by which an answer must…" | pre-release | flows |  |
| 81 | "An answer that arrives after its deadline is…" | pre-release | flows |  |
| 82 | "Context segment: a signed, self-describing fragment of state…" | pre-release | flows |  |
| 83 | "Clean pass: a determination that the job is…" | pre-release | flows |  |
| 84 | "The runner's local policy defines the threshold precisely;…" | pre-release | flows |  |
| 85 | "~~~ Submitter Runner" | pre-release | flows |  |
| 86 | "1. job (v1)" | pre-release | flagged | Table header row, structure rather than a sentence |
| 87 | "---------------------------------> \| verify signature (v1 rules)" | pre-release | flows |  |
| 88 | "\| form the determination" | pre-release | flows |  |
| 89 | "2. determination (v2) \| ONLY if not a…" | pre-release | flows |  |
| 90 | "<--------------------------------- \| ONLY if enabled (Sec. 11)" | pre-release | flows |  |
| 91 | "\| a question arises the" | pre-release | flows |  |
| 92 | "\| runner cannot answer" | pre-release | flows |  |
| 93 | "3. question (v2)" | pre-release | flows |  |
| 94 | "<--------------------------------- \| deadline starts" | pre-release | flows |  |
| 95 | "4. answer (v2) \| if it arrives in…" | pre-release | flows |  |
| 96 | "---------------------------------> \| it rides the result;" | pre-release | flows |  |
| 97 | "\| it does not change" | pre-release | flows |  |
| 98 | "\| what executes" | pre-release | flows |  |
| 99 | "\| deadline passes with no" | pre-release | flows |  |
| 100 | "\| answer: local default" | pre-release | flows |  |
| 101 | "\| execute (v1 rules)" | pre-release | flows |  |
| 102 | "5. result (v1 + segments)" | pre-release | flows |  |
| 103 | "<---------------------------------" | pre-release | flows |  |
| 104 | "The numbers are the order of first transmission,…" | pre-release | flows |  |
| 105 | "~~~" | pre-release | flows |  |
| 106 | "A version 2 message is a JSON object…" | pre-release | flows |  |
| 107 | "A receiver that does not implement this document…" | pre-release | flows |  |
| 108 | "Version 2 messages are addressed to the job's…" | pre-release | flows |  |
| 109 | "Every version 2 message names the job it…" | pre-release | flows |  |
| 110 | "Replay handling follows the seen-set discipline of version…" | pre-release | flows |  |
| 111 | "A receiver MUST hold `issued_at` to the same…" | pre-release | flows |  |
| 112 | "In the reference the identifier is recorded under…" | pre-release | flows |  |
| 113 | "A determination is the runner's statement, frozen before…" | pre-release | flows |  |
| 114 | "The reference software treats a missing plan, or…" | pre-release | flows |  |
| 115 | "A determination is an opinion." | pre-release | flows |  |
| 116 | "It does not refuse the job, and it…" | pre-release | flows |  |
| 117 | "~~~ plan has findings, or a repair?" | pre-release | flows |  |
| 118 | "+-- no --> send nothing (clean pass)" | pre-release | flows |  |
| 119 | "+-- yes, and version 2 is enabled (Sec.…" | pre-release | flows |  |
| 120 | "+--> send one determination ~~~" | pre-release | flows |  |
| 121 | "A determination is a JSON object:" | pre-release | flows |  |
| 122 | "~~~ { "v": 2, "type": "determination", "job_id": "job-17",…" | pre-release | flows |  |
| 123 | "`v` is the integer 2." | pre-release | flows |  |
| 124 | "`type` is `determination`." | pre-release | flows |  |
| 125 | "`job_id` and `msg_id` are safe identifiers: 1 to…" | pre-release | flows |  |
| 126 | "The reference software forms `msg_id` as `d.` plus…" | pre-release | flows |  |
| 127 | "`issued_at` is UTC and ends with Z." | pre-release | flows |  |
| 128 | "`clean_pass` is false; a clean pass is expressed…" | pre-release | flows |  |
| 129 | "`expect` is `fail` when the plan has findings,…" | pre-release | flows |  |
| 130 | "Receivers also accept `proceed`." | pre-release | flows |  |
| 131 | "`why` is a string of 1 to 500…" | pre-release | flows |  |
| 132 | "It is data." | pre-release | flows |  |
| 133 | "It is not instructions, and a receiver MUST…" | pre-release | flows |  |
| 134 | "The subject is `[HOMING-PIGEON] determination <msg_id>`." | pre-release | flows |  |
| 135 | "The object is signed and encrypted as a…" | pre-release | flows |  |
| 136 | "A question is what a deterministic runner would…" | pre-release | flows |  |
| 137 | "The reference software sends one only when version…" | pre-release | flows |  |
| 138 | "Other deployments MAY ask on a wider set…" | pre-release | flows |  |
| 139 | "A question does not delay execution past its…" | pre-release | flows |  |
| 140 | "~~~ { "v": 2, "type": "question", "job_id": "job-17",…" | pre-release | flows |  |
| 141 | "`msg_id` in the reference software is `q.` plus…" | pre-release | flows |  |
| 142 | "`deadline_sec` is an integer from 0 to 30." | pre-release | flows |  |
| 143 | "`question` is a non-empty string of at most…" | pre-release | flows |  |
| 144 | "`local_default` is a non-empty string of at most…" | pre-release | flows |  |
| 145 | "The reference software uses `proceed`." | pre-release | flows |  |
| 146 | "The subject is `[HOMING-PIGEON] question <msg_id>`." | pre-release | flows |  |
| 147 | "Signing and encryption are as in Section 6,…" | pre-release | flows |  |
| 148 | "An answer replies to one question." | pre-release | flows |  |
| 149 | "The answerer is any holder of a shared…" | pre-release | flows |  |
| 150 | "The shared secret is the credential." | pre-release | flows |  |
| 151 | "The runner cannot tell, and does not need…" | pre-release | flows |  |
| 152 | "~~~ { "v": 2, "type": "answer", "job_id": "job-17",…" | pre-release | flows |  |
| 153 | "`question_id` is the question's `msg_id`." | pre-release | flows |  |
| 154 | "`msg_id` in the reference software is `a.` plus…" | pre-release | flows |  |
| 155 | "`answer` is a non-empty string of at most…" | pre-release | flows |  |
| 156 | "It is data." | pre-release | flows |  |
| 157 | "A runner MUST NOT execute it, and MUST…" | pre-release | flows |  |
| 158 | "The subject is `[HOMING-PIGEON] answer <msg_id>`." | pre-release | flows |  |
| 159 | "Signing and encryption are as in Section 6." | pre-release | flows |  |
| 160 | "One answer decides." | pre-release | flows |  |
| 161 | "The reference software records the first answer for…" | pre-release | flows |  |
| 162 | "A file that is not a readable answer…" | pre-release | flows |  |
| 163 | "A second answer, and any answer that arrives…" | pre-release | flows |  |
| 164 | "It does not reopen the job and it…" | pre-release | flows |  |
| 165 | "The runner sends the determination, if any, and…" | pre-release | flows |  |
| 166 | "The default in the reference software is 0,…" | pre-release | flows |  |
| 167 | "The cap is 30 seconds." | pre-release | flows |  |
| 168 | "~~~ question handed to the pipe" | pre-release | flows |  |
| 169 | "+-- an answer is already filed, or arrives" | pre-release | flows |  |
| 170 | "before the deadline" | pre-release | flagged | Table header row, structure rather than a sentence |
| 171 | "+--> one answer segment on the result" | pre-release | flows |  |
| 172 | "+-- an answer arrives after the deadline" | pre-release | flows |  |
| 173 | "+--> the local default, and a late-answer" | pre-release | flagged | Table header row, structure rather than a sentence |
| 174 | "segment beside it" | pre-release | flows |  |
| 175 | "+-- no answer" | pre-release | flows |  |
| 176 | "+--> the local default alone" | pre-release | flows |  |
| 177 | "Then the job runs, under version 1 rules,…" | pre-release | flows |  |
| 178 | "~~~" | pre-release | flows |  |
| 179 | "An answer is in time when it was…" | pre-release | flows |  |
| 180 | "Time waiting for the question file to leave…" | pre-release | flows |  |
| 181 | "The whole wait, pause included, still ends by…" | pre-release | flows |  |
| 182 | "A deadline of 0 does not pause." | pre-release | flows |  |
| 183 | "An answer observed while the wait is still…" | pre-release | flows |  |
| 184 | "The reference software, while it waits, files version…" | pre-release | flows |  |
| 185 | "On a transport channel the question is written…" | pre-release | flows |  |
| 186 | "No answer admits a job." | pre-release | flows |  |
| 187 | "The local default is a string carried on…" | pre-release | flows |  |
| 188 | "In the reference software it does not select…" | pre-release | flows |  |
| 189 | "A context segment is one fragment attached to…" | pre-release | flows |  |
| 190 | "Segments are how the determination, the answer, and…" | pre-release | flows |  |
| 191 | "~~~ { "seg_id": "32 lowercase hex characters", "by":…" | pre-release | flows |  |
| 192 | "`seg_id` is a fresh identifier, unique to this…" | pre-release | flows |  |
| 193 | "`by` and `kind` are strings of at most…" | pre-release | flows |  |
| 194 | "`text` is a string of at most 500…" | pre-release | flows |  |
| 195 | "Text is data." | pre-release | flows |  |
| 196 | "A receiver MUST NOT interpret a segment as…" | pre-release | flows |  |
| 197 | "The reference kinds are `determination`, `answer`, `local_default`, `late_answer`,…" | pre-release | flows |  |
| 198 | "A question MAY carry a `context` array of…" | pre-release | flows |  |
| 199 | "Text is data." | pre-release | flows |  |
| 200 | "The result they ride is a version 1…" | pre-release | flows |  |
| 201 | "`v` stays 1." | pre-release | flows |  |
| 202 | "`context` is the array of segments." | pre-release | flows |  |
| 203 | "A result with nothing to say omits the…" | pre-release | flows |  |
| 204 | "Version 2 is off until the operator turns…" | pre-release | flows |  |
| 205 | "The reference software reads four keys." | pre-release | flows |  |
| 206 | "The same two booleans are flags for one…" | pre-release | flows |  |
| 207 | "Absence of a flag does not write false…" | pre-release | flows |  |
| 208 | "~~~ who is this process?" | pre-release | flows |  |
| 209 | "+-- protocol_v2 is true" | pre-release | flows |  |
| 210 | "the runner may emit a determination and," | pre-release | flagged | Table header row, structure rather than a sentence |
| 211 | "on a deterministic Oracle, a question" | pre-release | flows |  |
| 212 | "+-- answer_only is true" | pre-release | flows |  |
| 213 | "the process answers a question and does not" | pre-release | flagged | Table header row, structure rather than a sentence |
| 214 | "execute any job, including a ping" | pre-release | flows |  |
| 215 | "+-- neither version 2 messages are marked seen…" | pre-release | flows |  |
| 216 | "`answer_only` is the laptop that thinks for a…" | pre-release | flows |  |
| 217 | "It holds a shared secret the Pi already…" | pre-release | flows |  |
| 218 | "It does not run the Pi's job." | pre-release | flows |  |
| 219 | "The Pi does not learn a new role…" | pre-release | flows |  |
| 220 | "`v2_answerers`, when absent, means every key the runner…" | pre-release | flows |  |
| 221 | "When it is a list of key ids,…" | pre-release | flows |  |
| 222 | "A key id in that list may be…" | pre-release | flows |  |
| 223 | "Any other shape fails closed: nobody." | pre-release | flows |  |
| 224 | "`v2_answer_deadline_sec` is the question's deadline." | pre-release | flows |  |
| 225 | "Values outside 0..30 are clamped into that range." | pre-release | flows |  |
| 226 | "The default is 0." | pre-release | flows |  |
| 227 | "Version 2 messages use the bindings of version…" | pre-release | flows |  |
| 228 | "On the email binding the subject is `[HOMING-PIGEON]`…" | pre-release | flows |  |
| 229 | "A receiver dispatches on that type before it…" | pre-release | flows |  |
| 230 | "A subject that does not match the body's…" | pre-release | flows |  |
| 231 | "The signature and the encryption are the version…" | pre-release | flows |  |
| 232 | "The encryption's object identifier is the `msg_id` in…" | pre-release | flows |  |
| 233 | "Cleartext is refused wherever a cleartext job is…" | pre-release | flows |  |
| 234 | "A version 2 message is not a job." | pre-release | flows |  |
| 235 | "A job with `v` other than 1 is…" | pre-release | flows |  |
| 236 | "A process that has not enabled version 2…" | pre-release | flows |  |
| 237 | "A process that has enabled version 2 but…" | pre-release | flows |  |
| 238 | "An invalid question is still rejected and marked…" | pre-release | flows |  |
| 239 | "A determination is still marked seen." | pre-release | flows |  |
| 240 | "Version 2 extends trust along a line version…" | pre-release | flows |  |
| 241 | "The holder of a shared secret the runner…" | pre-release | flows |  |
| 242 | "The same holder, or another holder of a…" | pre-release | flows |  |
| 243 | "The operator chooses that set, and may narrow…" | pre-release | flows |  |
| 244 | "Enabling the feature is what makes the extension;…" | pre-release | flows |  |
| 245 | "An answer is not an authorization to run." | pre-release | flows |  |
| 246 | "The runner decides what runs, before and after…" | pre-release | flows |  |
| 247 | "Context text is data." | pre-release | flows |  |
| 248 | "A segment that says to run a different…" | pre-release | flows |  |
| 249 | "One answer decides, because two answerers would be…" | pre-release | flows |  |
| 250 | "The first answer filed wins." | pre-release | flows |  |
| 251 | "A later one cannot replace it and cannot…" | pre-release | flows |  |
| 252 | "The deadline is capped so a question cannot…" | pre-release | flows |  |
| 253 | "A deadline of 0 does not wait." | pre-release | flows |  |
| 254 | "Callers that need a live reply set a…" | pre-release | flows |  |
| 255 | "Answer-only mode is a refusal to execute." | pre-release | flows |  |
| 256 | "A process in that mode will not run…" | pre-release | flows |  |
| 257 | "This document defines no new IANA registry." | pre-release | flows |  |
| 258 | "The message types `determination`, `question`, and `answer`, and…" | pre-release | flows |  |
| 259 | "The version 1 message types are unchanged." | pre-release | flows |  |
| 260 | "--- back" | pre-release | flows |  |
