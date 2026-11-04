# Findings — docs/ietf/draft-slutsky-homing-pigeon-v2/source/draft-homing-pigeon-v2-00.md

Source: docs/ietf/draft-slutsky-homing-pigeon-v2/source/draft-homing-pigeon-v2-00.md, reviewed at main ae711991.
Sentence units: 187. Flagged: 1. Categories: pre-release 187, post-release 0.

The living v2 draft source: abstract, introduction, the determination and question messages, field definitions, and security considerations in normative prose. Definition-list entries and figure lines are fragments by the format's design and flow as such; 1 separator line stands alone. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Homing Pigeon Message Protocol, Version 2: Determinations, Questions,…" | pre-release | flows |  |
| 2 | "Workgroup: Individual Intended status: Informational Expires: 3 May…" | pre-release | flows |  |
| 3 | "This document specifies version 2 of the Homing…" | pre-release | flows |  |
| 4 | "Version 2 is an addition to version 1…" | pre-release | flows |  |
| 5 | "The additions are a determination message, by which…" | pre-release | flows |  |
| 6 | "Version 2 is backwards compatible." | pre-release | flows |  |
| 7 | "A version 1 runner never sends a version…" | pre-release | flows |  |
| 8 | "A submitter that implements this document adapts to…" | pre-release | flows |  |
| 9 | "There is no version negotiation and no handshake;…" | pre-release | flows |  |
| 10 | "The deployment that motivates version 2 is the…" | pre-release | flows |  |
| 11 | "Version 1 leaves such a runner alone with…" | pre-release | flows |  |
| 12 | "Version 2 lets it ask." | pre-release | flows |  |
| 13 | "This Internet-Draft is submitted in full conformance with…" | pre-release | flows |  |
| 14 | "Internet-Drafts are working documents of the Internet Engineering…" | pre-release | flows |  |
| 15 | "Note that other groups may also distribute working…" | pre-release | flows |  |
| 16 | "The list of current Internet-Drafts is at https://datatracker.ietf.org/drafts/current/." | pre-release | flows |  |
| 17 | "Internet-Drafts are draft documents valid for a maximum…" | pre-release | flows |  |
| 18 | "It is inappropriate to use Internet-Drafts as reference…" | pre-release | flows |  |
| 19 | "This Internet-Draft will expire on 3 May 2027." | pre-release | flows |  |
| 20 | "Version 1's core exchange is two messages: a…" | pre-release | flows |  |
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
| 34 | "Version 2 changes no version 1 message." | pre-release | flows |  |
| 35 | "A version 2 runner MUST accept version 1…" | pre-release | flows |  |
| 36 | "A version 2 message is sent only when…" | pre-release | flows |  |
| 37 | "A submitter that implements this document will routinely…" | pre-release | flows |  |
| 38 | "Realizing a runner does not support version 2…" | pre-release | flows |  |
| 39 | "The submitter adapts to the protocol version the…" | pre-release | flows |  |
| 40 | "The key words "MUST", "MUST NOT", "REQUIRED", "SHALL",…" | pre-release | flows |  |
| 41 | "The terms of draft-slutsky-homing-pigeon-00 apply: submitter, runner, binding,…" | pre-release | flows |  |
| 42 | "This document adds:" | pre-release | flows |  |
| 43 | "Determination: the runner's pre-execution statement of what it…" | pre-release | flows |  |
| 44 | "A determination is an opinion, formed from the…" | pre-release | flows |  |
| 45 | "Question: a question the runner's local decision machinery…" | pre-release | flows |  |
| 46 | "The reference software asks only for an exec…" | pre-release | flows |  |
| 47 | "Answer: a signed reply to one question, identified…" | pre-release | flows |  |
| 48 | "The answerer is any holder of a shared…" | pre-release | flows |  |
| 49 | "It does not have to be the party…" | pre-release | flows |  |
| 50 | "One answer decides; a late or second answer…" | pre-release | flows |  |
| 51 | "An answer never admits a job and never…" | pre-release | flows |  |
| 52 | "Local default: the decision the runner makes when…" | pre-release | flows |  |
| 53 | "Every question has one; asking never leaves a…" | pre-release | flows |  |
| 54 | "Deadline: the time by which an answer must…" | pre-release | flows |  |
| 55 | "An answer that arrives after its deadline is…" | pre-release | flows |  |
| 56 | "Context segment: a signed, self-describing fragment of state…" | pre-release | flows |  |
| 57 | "Clean pass: a determination that the job is…" | pre-release | flows |  |
| 58 | "The runner's local policy defines the threshold precisely;…" | pre-release | flows |  |
| 59 | "A version 2 message is a JSON object…" | pre-release | flows |  |
| 60 | "A receiver that does not implement this document…" | pre-release | flows |  |
| 61 | "Version 2 messages are addressed to the job's…" | pre-release | flows |  |
| 62 | "Where a deployment's bindings make that address and…" | pre-release | flows |  |
| 63 | "Every version 2 message names the job it…" | pre-release | flows |  |
| 64 | "Replay handling follows the seen-set discipline of version…" | pre-release | flows |  |
| 65 | "A receiver MUST hold `issued_at` to the same…" | pre-release | flows |  |
| 66 | "In the reference the identifier is recorded under…" | pre-release | flows |  |
| 67 | "---" | pre-release | flagged | A document separator line standing as its own unit — structure, not a sentence |
| 68 | "A determination is the runner's statement, frozen before…" | pre-release | flows |  |
| 69 | "The reference software treats a missing plan, or…" | pre-release | flows |  |
| 70 | "A determination is an opinion." | pre-release | flows |  |
| 71 | "It does not refuse the job, and it…" | pre-release | flows |  |
| 72 | "A determination is a JSON object:" | pre-release | flows |  |
| 73 | "`v` is the integer 2." | pre-release | flows |  |
| 74 | "`type` is `determination`." | pre-release | flows |  |
| 75 | "`job_id` and `msg_id` are safe identifiers: 1 to…" | pre-release | flows |  |
| 76 | "The reference software forms `msg_id` as `d.` plus…" | pre-release | flows |  |
| 77 | "`issued_at` is UTC and ends with Z." | pre-release | flows |  |
| 78 | "`clean_pass` is false; a clean pass is expressed…" | pre-release | flows |  |
| 79 | "`expect` is `fail` when the plan has findings,…" | pre-release | flows |  |
| 80 | "Receivers also accept `proceed`." | pre-release | flows |  |
| 81 | "`why` is a string of 1 to 500…" | pre-release | flows |  |
| 82 | "It is data." | pre-release | flows |  |
| 83 | "It is not instructions, and a receiver MUST…" | pre-release | flows |  |
| 84 | "The subject is `[HOMING-PIGEON] determination <msg_id>`." | pre-release | flows |  |
| 85 | "The object is signed and encrypted as a…" | pre-release | flows |  |
| 86 | "A question is what a deterministic runner would…" | pre-release | flows |  |
| 87 | "The reference software sends one only when version…" | pre-release | flows |  |
| 88 | "Other deployments MAY ask on a wider set…" | pre-release | flows |  |
| 89 | "A question does not delay execution past its…" | pre-release | flows |  |
| 90 | "`msg_id` in the reference software is `q.` plus…" | pre-release | flows |  |
| 91 | "`deadline_sec` is an integer from 0 to 30." | pre-release | flows |  |
| 92 | "`question` is a non-empty string of at most…" | pre-release | flows |  |
| 93 | "`local_default` is a non-empty string of at most…" | pre-release | flows |  |
| 94 | "The reference software uses `proceed`." | pre-release | flows |  |
| 95 | "The subject is `[HOMING-PIGEON] question <msg_id>`." | pre-release | flows |  |
| 96 | "Signing and encryption are as in Section 6,…" | pre-release | flows |  |
| 97 | "An answer replies to one question." | pre-release | flows |  |
| 98 | "The answerer is any holder of a shared…" | pre-release | flows |  |
| 99 | "The shared secret is the credential." | pre-release | flows |  |
| 100 | "The runner cannot tell, and does not need…" | pre-release | flows |  |
| 101 | "`question_id` is the question's `msg_id`." | pre-release | flows |  |
| 102 | "`msg_id` in the reference software is `a.` plus…" | pre-release | flows |  |
| 103 | "`answer` is a non-empty string of at most…" | pre-release | flows |  |
| 104 | "It is data." | pre-release | flows |  |
| 105 | "A runner MUST NOT execute it, and MUST…" | pre-release | flows |  |
| 106 | "The subject is `[HOMING-PIGEON] answer <msg_id>`." | pre-release | flows |  |
| 107 | "Signing and encryption are as in Section 6." | pre-release | flows |  |
| 108 | "One answer decides." | pre-release | flows |  |
| 109 | "The reference software records the first answer for…" | pre-release | flows |  |
| 110 | "A file that is not a readable answer…" | pre-release | flows |  |
| 111 | "A second answer, and any answer that arrives…" | pre-release | flows |  |
| 112 | "It does not reopen the job and it…" | pre-release | flows |  |
| 113 | "The runner sends the determination, if any, and…" | pre-release | flows |  |
| 114 | "The default in the reference software is 0,…" | pre-release | flows |  |
| 115 | "The cap is 30 seconds." | pre-release | flows |  |
| 116 | "An answer is in time when it was…" | pre-release | flows |  |
| 117 | "Time waiting for the question file to leave…" | pre-release | flows |  |
| 118 | "The whole wait, pause included, still ends by…" | pre-release | flows |  |
| 119 | "A deadline of 0 does not pause." | pre-release | flows |  |
| 120 | "An answer observed while the wait is still…" | pre-release | flows |  |
| 121 | "The reference software, while it waits, files version…" | pre-release | flows |  |
| 122 | "On a transport channel the question is written…" | pre-release | flows |  |
| 123 | "No answer admits a job." | pre-release | flows |  |
| 124 | "The local default is a string carried on…" | pre-release | flows |  |
| 125 | "In the reference software it does not select…" | pre-release | flows |  |
| 126 | "A context segment is one fragment attached to…" | pre-release | flows |  |
| 127 | "Segments are how the determination, the answer, and…" | pre-release | flows |  |
| 128 | "`seg_id` is a fresh identifier, unique to this…" | pre-release | flows |  |
| 129 | "`by` and `kind` are strings of at most…" | pre-release | flows |  |
| 130 | "`text` is a string of at most 500…" | pre-release | flows |  |
| 131 | "Text is data." | pre-release | flows |  |
| 132 | "A receiver MUST NOT interpret a segment as…" | pre-release | flows |  |
| 133 | "The reference kinds are `determination`, `answer`, `local_default`, `late_answer`,…" | pre-release | flows |  |
| 134 | "A question MAY carry a `context` array of…" | pre-release | flows |  |
| 135 | "Text is data." | pre-release | flows |  |
| 136 | "The result they ride is a version 1…" | pre-release | flows |  |
| 137 | "`v` stays 1." | pre-release | flows |  |
| 138 | "`context` is the array of segments." | pre-release | flows |  |
| 139 | "A result with nothing to say omits the…" | pre-release | flows |  |
| 140 | "Version 2 is off until the operator turns…" | pre-release | flows |  |
| 141 | "The reference software reads four keys." | pre-release | flows |  |
| 142 | "The same two booleans are flags for one…" | pre-release | flows |  |
| 143 | "Absence of a flag does not write false…" | pre-release | flows |  |
| 144 | "`answer_only` is the laptop that thinks for a…" | pre-release | flows |  |
| 145 | "It holds a shared secret the Pi already…" | pre-release | flows |  |
| 146 | "It does not run the Pi's job." | pre-release | flows |  |
| 147 | "The Pi does not learn a new role…" | pre-release | flows |  |
| 148 | "`v2_answerers`, when absent, means every key the runner…" | pre-release | flows |  |
| 149 | "When it is a list of key ids,…" | pre-release | flows |  |
| 150 | "A key id in that list may be…" | pre-release | flows |  |
| 151 | "Any other shape fails closed: nobody." | pre-release | flows |  |
| 152 | "`v2_answer_deadline_sec` is the question's deadline." | pre-release | flows |  |
| 153 | "Values outside 0..30 are clamped into that range." | pre-release | flows |  |
| 154 | "The default is 0." | pre-release | flows |  |
| 155 | "Version 2 messages use the bindings of version…" | pre-release | flows |  |
| 156 | "On the email binding the subject is `[HOMING-PIGEON]`…" | pre-release | flows |  |
| 157 | "A receiver dispatches on that type before it…" | pre-release | flows |  |
| 158 | "A subject that does not match the body's…" | pre-release | flows |  |
| 159 | "The signature and the encryption are the version…" | pre-release | flows |  |
| 160 | "The encryption's object identifier is the `msg_id` in…" | pre-release | flows |  |
| 161 | "Cleartext is refused wherever a cleartext job is…" | pre-release | flows |  |
| 162 | "A version 2 message is not a job." | pre-release | flows |  |
| 163 | "A job with `v` other than 1 is…" | pre-release | flows |  |
| 164 | "A process that has not enabled version 2…" | pre-release | flows |  |
| 165 | "A process that has enabled version 2 but…" | pre-release | flows |  |
| 166 | "An invalid question is still rejected and marked…" | pre-release | flows |  |
| 167 | "A determination is still marked seen." | pre-release | flows |  |
| 168 | "Version 2 extends trust along a line version…" | pre-release | flows |  |
| 169 | "The holder of a shared secret the runner…" | pre-release | flows |  |
| 170 | "The same holder, or another holder of a…" | pre-release | flows |  |
| 171 | "The operator chooses that set, and may narrow…" | pre-release | flows |  |
| 172 | "Enabling the feature is what makes the extension;…" | pre-release | flows |  |
| 173 | "An answer is not an authorization to run." | pre-release | flows |  |
| 174 | "The runner decides what runs, before and after…" | pre-release | flows |  |
| 175 | "Context text is data." | pre-release | flows |  |
| 176 | "A segment that says to run a different…" | pre-release | flows |  |
| 177 | "One answer decides, because two answerers would be…" | pre-release | flows |  |
| 178 | "The first answer filed wins." | pre-release | flows |  |
| 179 | "A later one cannot replace it and cannot…" | pre-release | flows |  |
| 180 | "The deadline is capped so a question cannot…" | pre-release | flows |  |
| 181 | "A deadline of 0 does not wait." | pre-release | flows |  |
| 182 | "Callers that need a live reply set a…" | pre-release | flows |  |
| 183 | "Answer-only mode is a refusal to execute." | pre-release | flows |  |
| 184 | "A process in that mode will not run…" | pre-release | flows |  |
| 185 | "This document defines no new IANA registry." | pre-release | flows |  |
| 186 | "The message types `determination`, `question`, and `answer`, and…" | pre-release | flows |  |
| 187 | "The version 1 message types are unchanged." | pre-release | flows |  |
