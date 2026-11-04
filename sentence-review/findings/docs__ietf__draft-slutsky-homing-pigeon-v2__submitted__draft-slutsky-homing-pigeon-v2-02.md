# Findings — docs/ietf/draft-slutsky-homing-pigeon-v2/submitted/draft-slutsky-homing-pigeon-v2-02.md

Source: docs/ietf/draft-slutsky-homing-pigeon-v2/submitted/draft-slutsky-homing-pigeon-v2-02.md, reviewed at main ae711991.
Sentence units: 273. Flagged: 5. Categories: pre-release 273, post-release 0.

The frozen submitted v2 -02 text: YAML front matter, the abstract and middle markers, normative prose, an ASCII message figure, and references. The front-matter shards and section markers are the breaks; definition entries and figure lines flow by the format's design. All pre-release, a frozen record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "---" | pre-release | flagged | A document separator line standing as its own unit — structure, not a sentence |
| 2 | "title: "Homing Pigeon Message Protocol, Version 2: Determinations,…" | pre-release | flows |  |
| 3 | "ins: "A." | pre-release | flagged | A YAML front-matter shard (the author block) standing as its own unit — metadata, not a sentence |
| 4 | "Slutsky" name: "Andrew Slutsky" organization: "Independent" email: "slutsky5544@gmail.com"" | pre-release | flows |  |
| 5 | "normative: I-D.slutsky-homing-pigeon: title: "Homing Pigeon Message Protocol, Version…" | pre-release | flows |  |
| 6 | "name: "Andrew Slutsky" ins: "A." | pre-release | flagged | A YAML front-matter shard (the author name line) standing as its own unit — metadata, not a sentence |
| 7 | "Slutsky" date: 2026-10 seriesinfo: Internet-Draft: draft-slutsky-homing-pigeon-00" | pre-release | flows |  |
| 8 | "--- abstract" | pre-release | flagged | A section marker ("--- abstract") standing as its own unit — structure, not a sentence |
| 9 | "This document specifies version 2 of the Homing…" | pre-release | flows |  |
| 10 | "Version 2 is an addition to version 1…" | pre-release | flows |  |
| 11 | "The additions are a determination message, by which…" | pre-release | flows |  |
| 12 | "Version 2 is backwards compatible." | pre-release | flows |  |
| 13 | "A version 1 runner never sends a version…" | pre-release | flows |  |
| 14 | "A submitter that implements this document adapts to…" | pre-release | flows |  |
| 15 | "There is no version negotiation and no handshake;…" | pre-release | flows |  |
| 16 | "The deployment that motivates version 2 is the…" | pre-release | flows |  |
| 17 | "Version 1 leaves such a runner alone with…" | pre-release | flows |  |
| 18 | "Version 2 lets it ask." | pre-release | flows |  |
| 19 | "--- middle" | pre-release | flagged | A section marker ("--- middle") standing as its own unit — structure, not a sentence |
| 20 | "Version 1's core exchange is two messages: a…" | pre-release | flows |  |
| 21 | "The runner's decisions in version 1 are local:…" | pre-release | flows |  |
| 22 | "The result may carry the runner's opinion home…" | pre-release | flows |  |
| 23 | "Three gaps follow, and version 2 closes each…" | pre-release | flows |  |
| 24 | "The submitter cannot see the runner's expectation before…" | pre-release | flows |  |
| 25 | "A runner that expects a job to fail…" | pre-release | flows |  |
| 26 | "The determination message (Section 6) is that statement,…" | pre-release | flows |  |
| 27 | "A constrained runner cannot escalate." | pre-release | flows |  |
| 28 | "Where a full runner asks its local model…" | pre-release | flows |  |
| 29 | "The question message (Section 7) carries the question…" | pre-release | flows |  |
| 30 | "Each side plans from a partial picture." | pre-release | flows |  |
| 31 | "The submitter sees exit codes; the runner sees…" | pre-release | flows |  |
| 32 | "Context segments (Section 10) are the shared remedy:…" | pre-release | flows |  |
| 33 | "Every message in this document exists to move…" | pre-release | flows |  |
| 34 | "The figures in this document are normative in…" | pre-release | flows |  |
| 35 | "~~~ DECISION DECIDED BY ------------------- ------------------- admit or…" | pre-release | flows |  |
| 36 | "what the job will the runner, before probably…" | pre-release | flows |  |
| 37 | "a question the an enabled answerer, runner cannot…" | pre-release | flows |  |
| 38 | "the same question the runner, by its after…" | pre-release | flows |  |
| 39 | "what runs, finally the runner, always; no answer…" | pre-release | flows |  |
| 40 | "the next job the submitter, with the runner's…" | pre-release | flows |  |
| 41 | "Version 2 changes no version 1 message." | pre-release | flows |  |
| 42 | "A version 2 runner MUST accept version 1…" | pre-release | flows |  |
| 43 | "A version 2 message is sent only when…" | pre-release | flows |  |
| 44 | "A submitter that implements this document will routinely…" | pre-release | flows |  |
| 45 | "Realizing a runner does not support version 2…" | pre-release | flows |  |
| 46 | "The submitter adapts to the protocol version the…" | pre-release | flows |  |
| 47 | "~~~ Submitter (v2) Runner" | pre-release | flows |  |
| 48 | "| |" | pre-release | flows |  |
| 49 | "| job (v=1 object, as always) |" | pre-release | flows |  |
| 50 | "|--------------------------------->|" | pre-release | flows |  |
| 51 | "| |" | pre-release | flows |  |
| 52 | "| if the runner is v2 and |" | pre-release | flows |  |
| 53 | "| the operator enabled it: |" | pre-release | flows |  |
| 54 | "| |" | pre-release | flows |  |
| 55 | "| determination (v=2) |" | pre-release | flows |  |
| 56 | "|<---------------------------------|" | pre-release | flows |  |
| 57 | "| question (v=2) |" | pre-release | flows |  |
| 58 | "|<---------------------------------|" | pre-release | flows |  |
| 59 | "| answer (v=2) |" | pre-release | flows |  |
| 60 | "|--------------------------------->|" | pre-release | flows |  |
| 61 | "| |" | pre-release | flows |  |
| 62 | "| result (v=1 object, with |" | pre-release | flows |  |
| 63 | "| context segments attached) |" | pre-release | flows |  |
| 64 | "|<---------------------------------|" | pre-release | flows |  |
| 65 | "| |" | pre-release | flows |  |
| 66 | "| if the runner is v1: |" | pre-release | flows |  |
| 67 | "| none of the v2 lines |" | pre-release | flows |  |
| 68 | "| above ever happen, and |" | pre-release | flows |  |
| 69 | "| the exchange is exactly |" | pre-release | flows |  |
| 70 | "| the version 1 exchange. | ~~~" | pre-release | flows |  |
| 71 | "{::boilerplate bcp14-tagged}" | pre-release | flows |  |
| 72 | "The terms of draft-slutsky-homing-pigeon-00 {{I-D.slutsky-homing-pigeon}} apply: submitter, runner,…" | pre-release | flows |  |
| 73 | "This document adds:" | pre-release | flows |  |
| 74 | "Determination: the runner's pre-execution statement of what it…" | pre-release | flows |  |
| 75 | "A determination is an opinion, formed from the…" | pre-release | flows |  |
| 76 | "Question: a question the runner's local decision machinery…" | pre-release | flows |  |
| 77 | "The reference software asks only for an exec…" | pre-release | flows |  |
| 78 | "Answer: a signed reply to one question, identified…" | pre-release | flows |  |
| 79 | "The answerer is any holder of a shared…" | pre-release | flows |  |
| 80 | "It does not have to be the party…" | pre-release | flows |  |
| 81 | "One answer decides; a late or second answer…" | pre-release | flows |  |
| 82 | "An answer never admits a job and never…" | pre-release | flows |  |
| 83 | "Local default: the decision the runner makes when…" | pre-release | flows |  |
| 84 | "Every question has one; asking never leaves a…" | pre-release | flows |  |
| 85 | "Deadline: the time by which an answer must…" | pre-release | flows |  |
| 86 | "An answer that arrives after its deadline is…" | pre-release | flows |  |
| 87 | "Context segment: a signed, self-describing fragment of state…" | pre-release | flows |  |
| 88 | "Clean pass: a determination that the job is…" | pre-release | flows |  |
| 89 | "The runner's local policy defines the threshold precisely;…" | pre-release | flows |  |
| 90 | "~~~ Submitter Runner" | pre-release | flows |  |
| 91 | "| |" | pre-release | flows |  |
| 92 | "| 1. job (v1) |" | pre-release | flows |  |
| 93 | "|--------------------------------->| verify signature (v1 rules)" | pre-release | flows |  |
| 94 | "| | form the determination" | pre-release | flows |  |
| 95 | "| |" | pre-release | flows |  |
| 96 | "| 2. determination (v2) | ONLY if not…" | pre-release | flows |  |
| 97 | "|<---------------------------------| ONLY if enabled (Sec." | pre-release | flows |  |
| 98 | "11)" | pre-release | flows |  |
| 99 | "| |" | pre-release | flows |  |
| 100 | "| | a question arises the" | pre-release | flows |  |
| 101 | "| | runner cannot answer" | pre-release | flows |  |
| 102 | "| 3. question (v2) |" | pre-release | flows |  |
| 103 | "|<---------------------------------| deadline starts" | pre-release | flows |  |
| 104 | "| |" | pre-release | flows |  |
| 105 | "| 4. answer (v2) | if it arrives…" | pre-release | flows |  |
| 106 | "|--------------------------------->| it rides the result;" | pre-release | flows |  |
| 107 | "| | it does not change" | pre-release | flows |  |
| 108 | "| | what executes" | pre-release | flows |  |
| 109 | "| |" | pre-release | flows |  |
| 110 | "| | deadline passes with no" | pre-release | flows |  |
| 111 | "| | answer: local default" | pre-release | flows |  |
| 112 | "| |" | pre-release | flows |  |
| 113 | "| | execute (v1 rules)" | pre-release | flows |  |
| 114 | "| 5. result (v1 + segments) |" | pre-release | flows |  |
| 115 | "|<---------------------------------|" | pre-release | flows |  |
| 116 | "| | The numbers are the order of…" | pre-release | flows |  |
| 117 | "A version 2 message is a JSON object…" | pre-release | flows |  |
| 118 | "A receiver that does not implement this document…" | pre-release | flows |  |
| 119 | "Version 2 messages are addressed to the job's…" | pre-release | flows |  |
| 120 | "Every version 2 message names the job it…" | pre-release | flows |  |
| 121 | "Replay handling follows the seen-set discipline of version…" | pre-release | flows |  |
| 122 | "A receiver MUST hold `issued_at` to the same…" | pre-release | flows |  |
| 123 | "In the reference the identifier is recorded under…" | pre-release | flows |  |
| 124 | "A determination is the runner's statement, frozen before…" | pre-release | flows |  |
| 125 | "The reference software treats a missing plan, or…" | pre-release | flows |  |
| 126 | "A determination is an opinion." | pre-release | flows |  |
| 127 | "It does not refuse the job, and it…" | pre-release | flows |  |
| 128 | "~~~ plan has findings, or a repair?" | pre-release | flows |  |
| 129 | "| +-- no --> send nothing (clean pass)" | pre-release | flows |  |
| 130 | "| +-- yes, and version 2 is enabled…" | pre-release | flows |  |
| 131 | "11), and this process executes jobs" | pre-release | flows |  |
| 132 | "| +--> send one determination ~~~" | pre-release | flows |  |
| 133 | "A determination is a JSON object:" | pre-release | flows |  |
| 134 | "~~~ { "v": 2, "type": "determination", "job_id": "job-17",…" | pre-release | flows |  |
| 135 | "`v` is the integer 2." | pre-release | flows |  |
| 136 | "`type` is `determination`." | pre-release | flows |  |
| 137 | "`job_id` and `msg_id` are safe identifiers: 1 to…" | pre-release | flows |  |
| 138 | "The reference software forms `msg_id` as `d.` plus…" | pre-release | flows |  |
| 139 | "`issued_at` is UTC and ends with Z." | pre-release | flows |  |
| 140 | "`clean_pass` is false; a clean pass is expressed…" | pre-release | flows |  |
| 141 | "`expect` is `fail` when the plan has findings,…" | pre-release | flows |  |
| 142 | "Receivers also accept `proceed`." | pre-release | flows |  |
| 143 | "`why` is a string of 1 to 500…" | pre-release | flows |  |
| 144 | "It is data." | pre-release | flows |  |
| 145 | "It is not instructions, and a receiver MUST…" | pre-release | flows |  |
| 146 | "The subject is `[HOMING-PIGEON] determination <msg_id>`." | pre-release | flows |  |
| 147 | "The object is signed and encrypted as a…" | pre-release | flows |  |
| 148 | "A question is what a deterministic runner would…" | pre-release | flows |  |
| 149 | "The reference software sends one only when version…" | pre-release | flows |  |
| 150 | "Other deployments MAY ask on a wider set…" | pre-release | flows |  |
| 151 | "A question does not delay execution past its…" | pre-release | flows |  |
| 152 | "~~~ { "v": 2, "type": "question", "job_id": "job-17",…" | pre-release | flows |  |
| 153 | "`msg_id` in the reference software is `q.` plus…" | pre-release | flows |  |
| 154 | "`deadline_sec` is an integer from 0 to 30." | pre-release | flows |  |
| 155 | "`question` is a non-empty string of at most…" | pre-release | flows |  |
| 156 | "`local_default` is a non-empty string of at most…" | pre-release | flows |  |
| 157 | "The reference software uses `proceed`." | pre-release | flows |  |
| 158 | "The subject is `[HOMING-PIGEON] question <msg_id>`." | pre-release | flows |  |
| 159 | "Signing and encryption are as in Section 6,…" | pre-release | flows |  |
| 160 | "An answer replies to one question." | pre-release | flows |  |
| 161 | "The answerer is any holder of a shared…" | pre-release | flows |  |
| 162 | "The shared secret is the credential." | pre-release | flows |  |
| 163 | "The runner cannot tell, and does not need…" | pre-release | flows |  |
| 164 | "~~~ { "v": 2, "type": "answer", "job_id": "job-17",…" | pre-release | flows |  |
| 165 | "`question_id` is the question's `msg_id`." | pre-release | flows |  |
| 166 | "`msg_id` in the reference software is `a.` plus…" | pre-release | flows |  |
| 167 | "`answer` is a non-empty string of at most…" | pre-release | flows |  |
| 168 | "It is data." | pre-release | flows |  |
| 169 | "A runner MUST NOT execute it, and MUST…" | pre-release | flows |  |
| 170 | "The subject is `[HOMING-PIGEON] answer <msg_id>`." | pre-release | flows |  |
| 171 | "Signing and encryption are as in Section 6." | pre-release | flows |  |
| 172 | "One answer decides." | pre-release | flows |  |
| 173 | "The reference software records the first answer for…" | pre-release | flows |  |
| 174 | "A file that is not a readable answer…" | pre-release | flows |  |
| 175 | "A second answer, and any answer that arrives…" | pre-release | flows |  |
| 176 | "It does not reopen the job and it…" | pre-release | flows |  |
| 177 | "The runner sends the determination, if any, and…" | pre-release | flows |  |
| 178 | "The default in the reference software is 0,…" | pre-release | flows |  |
| 179 | "The cap is 30 seconds." | pre-release | flows |  |
| 180 | "~~~ question handed to the pipe" | pre-release | flows |  |
| 181 | "| +-- an answer is already filed, or…" | pre-release | flows |  |
| 182 | "| before the deadline" | pre-release | flows |  |
| 183 | "| |" | pre-release | flows |  |
| 184 | "| +--> one answer segment on the result" | pre-release | flows |  |
| 185 | "| +-- an answer arrives after the deadline" | pre-release | flows |  |
| 186 | "| |" | pre-release | flows |  |
| 187 | "| +--> the local default, and a late-answer" | pre-release | flows |  |
| 188 | "| segment beside it" | pre-release | flows |  |
| 189 | "| +-- no answer" | pre-release | flows |  |
| 190 | "| +--> the local default alone" | pre-release | flows |  |
| 191 | "Then the job runs, under version 1 rules,…" | pre-release | flows |  |
| 192 | "An answer is in time when it was…" | pre-release | flows |  |
| 193 | "Time waiting for the question file to leave…" | pre-release | flows |  |
| 194 | "The whole wait, pause included, still ends by…" | pre-release | flows |  |
| 195 | "A deadline of 0 does not pause." | pre-release | flows |  |
| 196 | "An answer observed while the wait is still…" | pre-release | flows |  |
| 197 | "The reference software, while it waits, files version…" | pre-release | flows |  |
| 198 | "On a transport channel the question is written…" | pre-release | flows |  |
| 199 | "No answer admits a job." | pre-release | flows |  |
| 200 | "The local default is a string carried on…" | pre-release | flows |  |
| 201 | "In the reference software it does not select…" | pre-release | flows |  |
| 202 | "A context segment is one fragment attached to…" | pre-release | flows |  |
| 203 | "Segments are how the determination, the answer, and…" | pre-release | flows |  |
| 204 | "~~~ { "seg_id": "32 lowercase hex characters", "by":…" | pre-release | flows |  |
| 205 | "`seg_id` is a fresh identifier, unique to this…" | pre-release | flows |  |
| 206 | "`by` and `kind` are strings of at most…" | pre-release | flows |  |
| 207 | "`text` is a string of at most 500…" | pre-release | flows |  |
| 208 | "Text is data." | pre-release | flows |  |
| 209 | "A receiver MUST NOT interpret a segment as…" | pre-release | flows |  |
| 210 | "The reference kinds are `determination`, `answer`, `local_default`, `late_answer`,…" | pre-release | flows |  |
| 211 | "A question MAY carry a `context` array of…" | pre-release | flows |  |
| 212 | "Text is data." | pre-release | flows |  |
| 213 | "The result they ride is a version 1…" | pre-release | flows |  |
| 214 | "`v` stays 1." | pre-release | flows |  |
| 215 | "`context` is the array of segments." | pre-release | flows |  |
| 216 | "A result with nothing to say omits the…" | pre-release | flows |  |
| 217 | "Version 2 is off until the operator turns…" | pre-release | flows |  |
| 218 | "The reference software reads four keys." | pre-release | flows |  |
| 219 | "The same two booleans are flags for one…" | pre-release | flows |  |
| 220 | "Absence of a flag does not write false…" | pre-release | flows |  |
| 221 | "~~~ who is this process?" | pre-release | flows |  |
| 222 | "| +-- protocol_v2 is true" | pre-release | flows |  |
| 223 | "| the runner may emit a determination and," | pre-release | flows |  |
| 224 | "| on a deterministic Oracle, a question" | pre-release | flows |  |
| 225 | "| +-- answer_only is true" | pre-release | flows |  |
| 226 | "| the process answers a question and does…" | pre-release | flows |  |
| 227 | "| execute any job, including a ping" | pre-release | flows |  |
| 228 | "| +-- neither version 2 messages are marked…" | pre-release | flows |  |
| 229 | "`answer_only` is the laptop that thinks for a…" | pre-release | flows |  |
| 230 | "It holds a shared secret the Pi already…" | pre-release | flows |  |
| 231 | "It does not run the Pi's job." | pre-release | flows |  |
| 232 | "The Pi does not learn a new role…" | pre-release | flows |  |
| 233 | "`v2_answerers`, when absent, means every key the runner…" | pre-release | flows |  |
| 234 | "When it is a list of key ids,…" | pre-release | flows |  |
| 235 | "A key id in that list may be…" | pre-release | flows |  |
| 236 | "Any other shape fails closed: nobody." | pre-release | flows |  |
| 237 | "`v2_answer_deadline_sec` is the question's deadline." | pre-release | flows |  |
| 238 | "Values outside 0..30 are clamped into that range." | pre-release | flows |  |
| 239 | "The default is 0." | pre-release | flows |  |
| 240 | "Version 2 messages use the bindings of version…" | pre-release | flows |  |
| 241 | "On the email binding the subject is `[HOMING-PIGEON]`…" | pre-release | flows |  |
| 242 | "A receiver dispatches on that type before it…" | pre-release | flows |  |
| 243 | "A subject that does not match the body's…" | pre-release | flows |  |
| 244 | "The signature and the encryption are the version…" | pre-release | flows |  |
| 245 | "The encryption's object identifier is the `msg_id` in…" | pre-release | flows |  |
| 246 | "Cleartext is refused wherever a cleartext job is…" | pre-release | flows |  |
| 247 | "A version 2 message is not a job." | pre-release | flows |  |
| 248 | "A job with `v` other than 1 is…" | pre-release | flows |  |
| 249 | "A process that has not enabled version 2…" | pre-release | flows |  |
| 250 | "A process that has enabled version 2 but…" | pre-release | flows |  |
| 251 | "An invalid question is still rejected and marked…" | pre-release | flows |  |
| 252 | "A determination is still marked seen." | pre-release | flows |  |
| 253 | "Version 2 extends trust along a line version…" | pre-release | flows |  |
| 254 | "The holder of a shared secret the runner…" | pre-release | flows |  |
| 255 | "The same holder, or another holder of a…" | pre-release | flows |  |
| 256 | "The operator chooses that set, and may narrow…" | pre-release | flows |  |
| 257 | "Enabling the feature is what makes the extension;…" | pre-release | flows |  |
| 258 | "An answer is not an authorization to run." | pre-release | flows |  |
| 259 | "The runner decides what runs, before and after…" | pre-release | flows |  |
| 260 | "Context text is data." | pre-release | flows |  |
| 261 | "A segment that says to run a different…" | pre-release | flows |  |
| 262 | "One answer decides, because two answerers would be…" | pre-release | flows |  |
| 263 | "The first answer filed wins." | pre-release | flows |  |
| 264 | "A later one cannot replace it and cannot…" | pre-release | flows |  |
| 265 | "The deadline is capped so a question cannot…" | pre-release | flows |  |
| 266 | "A deadline of 0 does not wait." | pre-release | flows |  |
| 267 | "Callers that need a live reply set a…" | pre-release | flows |  |
| 268 | "Answer-only mode is a refusal to execute." | pre-release | flows |  |
| 269 | "A process in that mode will not run…" | pre-release | flows |  |
| 270 | "This document defines no new IANA registry." | pre-release | flows |  |
| 271 | "The message types `determination`, `question`, and `answer`, and…" | pre-release | flows |  |
| 272 | "The version 1 message types are unchanged." | pre-release | flows |  |
| 273 | "--- back" | pre-release | flows |  |
