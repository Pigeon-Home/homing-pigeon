# Version 3 carriage: review pass after 3.15.129

Read against `main` at `b75538d` (release 3.15.129), 02-NOV 9:30PM PST.

Nothing in this note is implemented. It is the list of what I would
change, each described far enough to review without opening the code,
in the order I would do it. Section 1 is two defects I found and
demonstrated by running the carriage. Section 2 is the rest of what
this read turned up. Section 3 is the work the two reviews and the
revision passes left open, described. Section 4 is the IETF side.
Section 5 is a longer list of ideas toward the goals, in no particular
order. Section 6 is what I would do first.

## 0. Where the draft stands

The question this pass had to answer first was whether every comment
from the two reviews is in the draft. Checked against the text at
`b75538d`, not against the decision notes:

- Grok's 6:10pm peer review, items 1 to 8: all in the draft. Muse's
  6:44pm pass landed them; I re-read each one in the current text.
- Grok's 7:10pm read-back, the four disagreements (the uncapped
  re-post, the per-process cookie key, the fallback sentence, the
  collision send) and the orphaned `where:` list: all closed in
  `fd83d58`. The version 3 module runs 70 tests green on that tree.
- Grok's 7:40pm avenues: 2 (the session does not authorize or narrow
  a job; the key policy does), 4 (every unauthenticated action with
  its number), 7 (the send path keyed as the hold is) and 8 (the
  budget line in the same commit as the send) are closed. Avenue 1
  is partly done (early data, `psk_ke`, a fragmented first hello,
  tickets, the harness shape are each a refusal with a test); the
  rest of the mode inventory is Section 3.2. Avenue 3 is partly done
  (the fallback choice is written; the harness shape is fenced); the
  `Re:` observation is Section 3.6. Avenue 5, the lifetime table, is
  Section 3.4, and it has the sharpest row in this note. Avenues 6
  and 9 are Sections 3.5 and 3.1.
- Grok's pass at `c3386c7` and `537eceb` took the discovery fact
  (Section 4.3), the saved-flight bound (Section 16.4), the
  key-policy paragraph (Section 16.6), the retransmission sentence
  (Section 7.2), the fragmented-first-hello rule (Section 8.2), the
  harness-shape fence (Sections 5.1 and 8.1, with code and a test),
  and the ticket MUST. Each one checked against the code.
- `PROTOCOL.md` links the local version 3 source (`2758cab`).
  `docs/ietf/STATUS.md` has a version 3 section (`b75538d`).
- Still outside the draft: the title/docname decision; idnits on the
  version 3 text (not run; the tool is not reachable from the
  container this pass ran in); the rendered `.txt`, `.html` and
  `.xml`, which are older than the source; the combination tests;
  the live proofs. Plus everything in Sections 1 and 2 below.

## 1. Two downgrades the draft forbids and the code performs

Both were found by reading `runner/transport_extensions/email/__main__.py`
and then shown by running the repository's own `EmailPipe` fixture
(`EmailPipeIntegrationTest` in `runner/tests/test_dtls_email_v3.py`),
with no change to the tree. The transcript lines below are the
runner's own log lines from those runs. Both are the downgrade
Section 12 forbids by name, "a result bound to a session is never
downgraded to an ordinary mail result," and both would fire the cold
test's stop rule, "an ordinary `[HOMING-PIGEON] result` mail appears."

### 1.1 A restart of the email process sends every held session result as ordinary mail

What the code does. The hold that keeps a session's result off the
ordinary path is `EmailPipe._job_session`, a dictionary in memory,
keyed `(connection id, job ident)` with the PSK identity as the value.
It is written when a job is delivered from a session
(`_drain_dtls_apps`) and read by `_session_bound(ident)` in
`flush_results`. Nothing writes it to disk. The result file it
guards, `<ident>.result.txt` in the channel's outbox, is on disk and
survives a restart. The hold does not. After the process restarts,
`flush_results` finds the result, asks `_session_bound`, gets false,
and takes the ordinary branch: `_mailbox.send_mail(...)` to the
sidecar target or the mailbox address.

The demonstration: a session established, one signed job carried
inside it and run, its result in the outbox, then the pipe rebuilt on
the same channel directory (the test module's own `_rebuild_pipe`,
"nothing carried over in memory"), then one flush.

```
INFO: email transport: job v3-job-restart delivered from a DTLS session to the runner core
[INFO] result v3-job-restart delivered (attempt 1)
[demo 1] ordinary result mails sent after the restart: ['[HOMING-PIGEON] result v3-job-restart']
```

The same thing happens to a job that was delivered from a session,
was still running at the restart, and produces its result afterwards:
its hold is gone before its result exists.

Why it is the forbidden case and not a bounded loss. Section 9.4 was
written in `fd83d58` and says what a restart costs: attempts in
flight, and nothing else, "and a result held for such a session
follows Section 10.3." Section 10.3 says the held result waits,
bounded, for a later session under the same PSK identity, and "MUST
NOT be sent as an ordinary mail result." The draft promises the hold
survives the process. The code keeps the hold in the process. A
deploy, a crash, or the next release cut on a runner with one session
job in flight sends that job's result by the path the whole carriage
exists to avoid. On this carriage a restart between a job's delivery
and its result is not rare; the operational section's own numbers put
a slow handshake at hours.

The fix, described. Make the hold as durable as the result it guards,
and keep it beside the result. At delivery, write a small sidecar
next to the job file, `<ident>.session.txt` (the shape the
`<ident>.target.txt` sidecar already has for reply-to routing):
the connection id as hex, the PSK identity, and the delivery time.
When the core moves the job to done and the result appears in the
outbox, the sidecar follows the result as `_ack_sidecar` already
follows the target sidecar: acks are moves in this channel, and no
orphan is left. `_session_bound` and `_hold_owner` read the sidecars,
not only the dictionary; the constructor rebuilds `_job_session` and
`_result_wait_since` from the sidecars present in the inbox and the
outbox. Nothing secret goes in the sidecar: a connection id and a key
id are routing facts the mailbox already sees. Traffic keys stay
where Section 16.1 puts them, in the process, so a held result can
still only leave inside a new session the submitter opens under the
same identity (Section 10.3's recovery path), which is exactly the
path a durable hold makes work across a restart. The alternative, one
JSON file per channel rewritten on every change, is simpler to write
and harder to keep consistent with the file moves the channel already
does; the sidecar shape wins on consistency.

The tests, described. Three cells in `test_dtls_email_v3`: a result
in the outbox across a rebuild, asserting no ordinary result mail,
the file still in the outbox, and the result then answering a new
session under the same key that carries the ident again; a job
delivered but not yet run across a rebuild, asserting the same; and
the existing expiry test run across a rebuild, asserting the age
bound still applies to a hold the sidecar restored. Each one asserts
the count of ordinary mails, not only the final state.

The draft, one sentence in Section 10.3, after "the carriage
remembers": the hold is kept as the result is kept, in the
responder's own state and across a restart of the process, because a
hold that dies with the process would send the result by the ordinary
path on the next pass. The sentence is true today of the draft and
false of the code; after the fix it is true of both and the test
holds it.

### 1.2 One expiry wipes every hold that has no result file yet

What the code does. `_expire_session_results` builds `held` from the
result files in the outbox that have a hold, dooms the ones past the
age, count or byte bound, and then prunes the hold dictionary with:

```
still = {entry[2] for entry in remaining}
for key in list(self._job_session):
    if key[1] not in still:
        del self._job_session[key]
```

`still` is the set of idents that still have a held result file.
A job that was delivered from a session and has not produced its
result yet has a hold and no file, so its ident is not in `still`,
and its hold is deleted along with the doomed one. The prune meant
"forget the holds of the results I just dropped" and says "forget
every hold that is not a surviving file."

The demonstration: job B delivered and run, its result held; job A
delivered from the same session, not yet run; the session dies; B's
result ages past the bound; then A runs and its result is flushed.

```
WARN: email transport: session result for v3-job-B expired past its age bound; dropped, not sent
[demo 2] holds left after B expired: []
[demo 2] ordinary result mails sent for A: ['[HOMING-PIGEON] result v3-job-A']
```

The fix, described. Prune by the doomed idents, not by the survivors:
collect the idents of the files just dropped and delete only the keys
whose ident is in that set (and only the `_waiting_session` entries
for those idents). With the sidecar of 1.1 in place the sweep also
moves those idents' sidecars to done. The existing expiry tests keep
passing; one new test holds the rule: one expiry, one unrelated live
hold, the live hold survives and its result goes inside the session.
No draft change: Section 10.3 already bounds the hold per result.

### 1.3 What this means for the cold test

The 7:35pm card keeps the test runner un-restarted and sends each
flight once, so that neither of the two carriage bugs it named could
grade the run. Both of those are now closed. The no-restart rule is
load-bearing again, for 1.1: a restart during the window with the
clock job delivered and its result not yet flushed would produce an
ordinary result mail, which the card already names as a failed test.
Either fix 1.1 and 1.2 before the window, or keep the no-restart rule
and write in the retrospective that a restart with a held result is
one more thing the run did not prove. I would fix them first; the
change is small and the tests are the same shape as the ones already
in the module.

## 2. Other findings from this read

Smaller, each with the change described. Draft section numbers are
the current text's.

### 2.1 The media type's tree (decision needed before submission)

`application/hp-dtls3` is a subtype name in the standards tree. RFC
6838 Section 3.1 reserves that tree for types registered through the
IETF (IESG approval) or a recognized standards body; an independent
submission cannot register there, and an unregistered name there is
a nit every reviewer will raise. The two honest shapes are the
unregistered tree, `application/x.hp-dtls3` (Section 3.4: private
use, cannot ever be registered, no IANA action, which matches
Section 15 exactly), and the vendor tree,
`application/vnd.homing-pigeon.dtls3` (Section 3.2: registered by a
simple form, by anyone, with no IESG step; Section 15 would then
request that one registration and still no code point). The personal
tree, `application/prs.hp-dtls3`, is the same as the vendor tree for
an individual. My preference is the vendor tree, requested in
Section 15 at submission time, because the wire string then changes
once and never again; the `x.` form would change again the day the
type is registered. The string lives in `runner/wire/dtls_mailbox.py`,
the tests, the draft (Sections 5.2, 8.1, 15), and the cold-test card.
Do not change it before the cold test; change it in the submission
revision, with the registration template (RFC 6838 Section 5.6) as
the IANA considerations' second paragraph.

### 2.2 Section 4.1, the "SS" sentence

"The 'SS' of this version's name for the work, DTLS via email using
SS" is the project's working name inside the specification. The -01
revisions of versions 1 and 2 removed repository file names from
those drafts for the same reason. Replace the clause with the
sentence the 5:38pm review asked for at exactly that spot: the
shared secret is an authenticator and only an authenticator; it is
never the session key, which is derived from the ephemeral exchange
of every handshake. Section 16.1 says it; the profile section should
say it where the acronym is expanded, because "shared secret" is the
phrase that gets misread as the session key.

### 2.3 Section 16.3, filtering is not gating

"A deployment MUST NOT add a sender allowlist as a substitute gate"
is right and will be read as "you may not filter mail." Add one
sentence: a deployment MAY filter intake on any header it likes, as
a pre-filter that can only drop; passing such a filter grants nothing
the datagram did not already prove, and a DKIM or ARC pass is such a
filter. That is the 5:38pm review's split (a reasonable pre-filter, a
terrible gate) written down, and it keeps the version 1 property that
the email binding has no sender gate.

### 2.4 Section 16.4, "no state"

The first bullet says a fresh ClientHello costs the responder one
HelloRetryRequest mail "and no state." Since `fd83d58` a fresh hello
costs a saved-flight entry and a re-post flag, keyed by the synthetic
address, and a digest-cache entry; both are now listed and bounded
further down the same list. Say "no session state" in the first
bullet so the list does not contradict itself.

### 2.5 Sections 9.3 and 9.4, tickets die with the process

The ticket table is in the server core's memory, so a ticket issued
before a responder restart cannot resume after it; the initiator's
resumption attempt fails the binder and it falls back to a full
handshake under a fresh mail session-id, which is the right outcome
and is nowhere written. On this carriage a resumption may come days
after the ticket. Add one sentence to Section 9.3: a responder MAY
forget its tickets at a restart; a resumption offer the responder
does not recognize is answered as the profile answers an unknown PSK,
and the initiator proceeds with a full handshake. Do not persist the
ticket key to make resumption survive a restart; a stored ticket key
is a second long-lived secret in the archive, which is the thing
Section 9.3 was tightened against. The proof note should say
"resumption across a responder restart: not possible by design."

### 2.6 Section 10.3 with the real core, unverified

The rule that a later same-key session carrying the same ident is
answered by the held result, "the acceptance gate refuses the
repeated job as a replay; the held result is what answers it," is
proven at the pipe level only (the new tests do not run the core for
the repeated delivery). With the real core, the repeated job reaches
`process_transport_message`, whose seen-set skips it ("ingest: ...
skipped; already seen" in `runner/runner.py`). Confirm the core
writes no refusal result for a seen job; if it ever did, a second
`<ident>.result.txt` would land beside the held one, and the outbox
names results by ident alone. The test: the same-key cell of
`fd83d58`, with `_run_channel_core` run for the second delivery,
asserting exactly one result file and that the one sent into the new
session is the held one.

### 2.7 Section 8.2 and the classifier

`_is_client_hello` in `dtls_mailbox.py` returns true for a fragment
whose type is ClientHello, so a fragmented first hello is classified
`dtls-init` and fed to the core, where `DtlsServerCore.feed` refuses
it ("no service for fragmented first flights") with no answer and no
state. The behavior matches the draft as Grok rewrote it. The name
does not: Section 8.2 now says a fragmented first message "is not an
initialization" and "is malformed flight mail." Make the classifier
return false for fragments, so the datagram is `dtls-invalid`, the
carriage's own fail-closed log line names it, and the refusal does
not depend on the engine's. One line and one test.

### 2.8 Section 5.1, the ABNF

Two small things. The prefix rule is prose only; add the production,
`flight-mail-subject = [ prefix gap ] flight-subject` with
`prefix = "Re:" / "Fwd:"`, which RFC 5234 string literals already make
case-insensitive, and the sentence that at most one prefix is
accepted stays. And `1*gap` is `1*(1*gap-char)`, a redundancy; write
`gap`. Neither changes what any implementation does.

### 2.9 Number style, an editorial pass before submission

Version 1's -03 writes small counts as words 28 times and as digits
13; version 3 writes them as digits 55 times and as words 4 ("1
cipher suite," "2 bindings," "1st line," "2nd copy"). The RFC Editor
normalizes this and a reviewer notices it. One pass, prose only:
words for counts under ten in sentences, digits in grammar, limits,
field values and section numbers. Not a blocker; do it with the
submission edits.

### 2.10 The submission-time edit list

Sentences that are true of a local draft and become false the moment
it is posted, so they should be a checklist rather than remembered:
the header comment's `Status: LOCAL DRAFT -- UNSUBMITTED` block; the
abstract's last paragraph; Section 1.1 as a whole (rewrite to the
ordinary status text, which the renderer supplies); Section 5.2's
"this document is local and requests no media type registration"
(see 2.1); Section 15's "As a local, unsubmitted draft" paragraph;
the `date:` line; the version 1 reference's revision (2.11); and the
`STATUS.md` version 3 section. Put the list in `STATUS.md` now, as
the -00 edits, the way the -02 edits were listed there.

### 2.11 The version 1 citation, one rule across the drafts

Version 2's -03 was posted to drop the revision number from its
citations of version 1; version 3 pins `-03` in its reference block
because the 6:10pm review asked for it. Both forms are accepted by
the datatracker and by idnits. Pick one rule for all three drafts.
My preference: the reference block names the revision current on the
day of posting, prose never carries a revision, and the next revision
of each draft re-pins. If version 1 goes to -04 before version 3 is
posted (for instance to make tickets single-use as a requirement
there too, Section 3.2), re-pin.

### 2.12 README

`README.md` lists the version 1 and version 2 datatracker pages under
"IETF Internet-Drafts." Add the version 3 line beside them, pointing
at the local source and saying it is not yet submitted, the way
`PROTOCOL.md` now does.

### 2.13 The readable copies of versions 1 and 2 (not version 3)

`PROTOCOL.md` points "the technical protocol description" for
versions 1 and 2 at `docs/ietf/draft-homing-pigeon-00.md` and
`-v2-00.md`. Those are plain-markdown readable copies of the -00
submissions (their status text says "expires 3 May 2027," the -00
expiry); the posted drafts are at -03, and `test_ietf_draft_conformance.py`
pins its sentences against the -00 copy. Decide what those two files
are: a readable copy of the current posted revision, regenerated at
each posting, or retired in favor of the kramdown sources. Version 3
has no such copy; its `PROTOCOL.md` line points at the source, which
is the right choice until there is a posted revision.

## 3. Open work carried from the reviews, described

### 3.1 The combination cells

The 7:10pm note's matrix, each cell asserting the count of jobs and
the count of outbound mails, not only the final state:

1. A typed part, a disclaimer in the text part, the datagram
   segmented, the parts delivered reversed, and one part delivered
   twice. Expect one datagram, one answer, no second transfer.
2. One `Re:` on a flight whose typed part is quoted-printable. Expect
   `dtls-invalid` (or not-a-flight), no session, no exception from
   the prefix parser.
3. Early data spliced into a hello that is segmented and prefixed.
   Expect the rejection to be a property of the reassembled datagram:
   no HelloRetryRequest, no session, no reassembly left behind.
4. Two submitters, two keys, one ident, both sessions live when the
   result is ready. The `fd83d58` cell kills the first session; this
   one keeps it alive and asserts the result goes to the carrying
   session and nowhere else.
5. The restart cells of Section 1.1.

### 3.2 The engine-mode inventory

Avenue 1 of the 7:40pm note. Modes the shared engine can still
perform that the profile's prose forbids or does not mention, each
needing a refusal with a spliced-input test, or a sentence saying it
is allowed: a KeyUpdate inside a session (allowed by DTLS 1.3; say
whether the carriage accepts one, and that it changes no mail rule);
a second identity in the `pre_shared_key` extension (the profile has
one PSK; refuse, or take the first and ignore the rest, but say
which); a ClientHello with no `pre_shared_key` at all (a
certificate-shaped hello; refuse before the cookie, since there is no
binder to check); a ticket presented twice (tested); early data
(tested); `psk_ke` (tested); a fragmented first hello (tested in the
engine, Section 2.7 for the carriage). The ticket rule is the one
with a cross-draft cost: the engine consumes a ticket once on both
bindings, version 3 says MUST, version 1 says SHOULD. Either version
1's -04 says what the code does, or the code grows a per-binding
switch so the datagram binding can keep the SHOULD. I would let the
text follow the code.

### 3.3 The policy fields that bind an effective value

Avenue 2's second question. From `PROTOCOL.md` Section 14.1, marking
which fields constrain a value the job may omit, so the constraint
depends on the runner's defaults:

| Field | Binds | Omissible by the job | Default that fills it |
|---|---|---|---|
| `allowed_kinds` | `kind` | no | none |
| `allowed_interpreters` | the effective interpreter | yes | the configured default interpreter |
| `max_timeout_sec` | the effective timeout | yes | `default_timeout_sec`, 300 |
| `allowed_recipes` | `recipe` | no | none |
| `allowed_script_sha384` | the inline `script` | no (a `script_url` job is refused) | none |
| `allowed_env`, `denied_env`, `allow_dangerous_env` | env names | yes (no env is a valid job) | empty |
| `allowed_files`, `allow_file_urls` | staged file names and URLs | yes | empty |
| `max_args`, `args_pattern` | args | yes | empty |

The two rows that bind a default are the interpreter and the timeout.
The deliverable is one sentence in Section 14.1 saying so, and a test
per row: a job that omits the field, a policy that would refuse the
default, a refusal. The signed preview the submitter sees does not
show the defaults, which is why the sentence belongs in the protocol
page and not only in the code.

### 3.4 The secret and state lifetime table

Avenue 5, drafted here. "Path" is the lifetime the carriage's delay
forces; "keep" is whether a restart of the email process should
preserve it.

| Row | Lifetime today | Lifetime the path needs | Keep across restart | Note |
|---|---|---|---|---|
| `shared_secret`, additional secrets | configuration | indefinite | yes | unchanged |
| cookie key | file in the channel, 32 bytes, owner-only (`fd83d58`) | at least the attempt deadline, hours to days | yes | rotation abandons attempts in flight; rotate on operator action, never on a timer shorter than the deadline |
| ticket table (responder) | process | a resumption may come days later | no, by design | Section 2.5: say so |
| resumption PSK (initiator) | the client object | until used or expired | initiator's choice | a one-process client loses it |
| handshake keys | the handshake | the handshake | no | |
| traffic keys | the session | the session | never | Section 16.1 |
| mail session-id to connection-id binding | the session | the session | no | established sessions do not survive a restart |
| saved last flight and re-post flag | until evicted (4096, FIFO) or a new generation | the handshake window | no | after a restart a copy is a digest miss and the stateless path answers it: one mail, bounded |
| digest cache | process (4096, FIFO) | the handshake window | no | same |
| held results (files) | disk, 7 days / 64 / 16 MiB | the same | yes | already true |
| the hold map `_job_session` | process | at least the held-result TTL | yes, and it is not | Section 1.1 |
| reply-to target sidecar | disk | until the result leaves | yes | already true |

The table's one surprise is the hold map, which is why Section 1.1
is first in this note.

### 3.5 The observer-fields test

Avenue 6. One test holds the rule that no field a mailbox observer
can read is an input to the gate: a session carrying a job whose
envelope job id and whose subject job id disagree, asserting the id
inside the envelope is the one that runs and the subject's never
does. The inventory of what an observer learns is already stated in
Section 16.2 (session-id, transfer id, part numbers, `bytes=`, the
digest, timing, the existence of a typed part); the test is what
keeps a later change from wiring one of them into a decision.

### 3.6 The `Re:` and `Fwd:` observation

Avenue 3's question. The one-prefix rule is a hole cut on purpose for
mail agents that rewrite subjects. Record, from the live mailbox's
history rather than from imagination, whether any flight or job mail
has ever arrived with a prefix. If none has, the stricter rule
(refuse every prefix) is the better constraint and the hole closes;
if one has, the observation is the reason the hole stays. Either way
the record goes in the proof note.

### 3.7 Title and docname

Still the one open decision. Both reviews and the read-back say leave
`draft-slutsky-homing-pigeon-v3-00` for this revision: the abstract
and Section 10.1 carry the disambiguation, and a rename mid-revision
costs every link in the proof, the plan, the forum and now
`PROTOCOL.md`. I agree, with one addition: the name follows the
pattern the datatracker already has for this work (`-v2` is a
separate document there), so consistency argues for keeping it even
in the long run. If it is ever renamed, rename it as a binding of
version 1.

### 3.8 Render, idnits, and a drift check

The rendered `.txt`, `.html` and `.xml` beside the version 3 source
are older than the source, and idnits has not been run on it
(`STATUS.md` says both). This matters twice: the cold test hands a
cold reader the `.txt`, and the submission uploads the `.xml`.

Where it can run: not in the container this pass ran in, which cannot
resolve PyPI, RubyGems or the npm registry. The -01 renders and
idnits runs were made elsewhere on 1 November with kramdown-rfc
1.7.43, xml2rfc 3.35.0 and idnits 3.3.0, so that toolchain exists on
a machine this project uses; the same pipeline, the one named in the
draft's header comment, renders version 3. The idnits that runs is
`@ietf-tools/idnits` on npm (the JavaScript idnits3; `npx
@ietf-tools/idnits --mode submission --offline <file>`), not the
bare `idnits` name, which is why the earlier attempt 404ed.

What to commit: the three renders and `draft-slutsky-homing-pigeon-v3-00.idnits.txt`
beside them, as the other drafts have.

The durable version: a GitHub Actions workflow that installs the
three tools on a runner, renders every `docs/ietf/*.md` whose header
names the pipeline, diffs the result against the checked-in renders,
fails on drift, runs idnits in submission mode, and uploads the
report. Then a stale render is a red check instead of a sentence in
`STATUS.md`, and the idnits output is reproduced on every push rather
than copied in by hand.

### 3.9 Live proofs and the cold test's pin

Still unproven on a real mailbox: the MIME sender, a restart between
the HelloRetryRequest and the cookied hello (the cookie key now makes
this a pass rather than a fail), resumption, a second provider. The
7:35pm card pins its links to `22bfeedf` (3.15.127). Re-pin to
`v3.15.129` or later, because three rules a cold reader meets changed
after that pin (the typed-part fallback sentence, the re-post budget,
the harness-shape fence), and re-render first, because the card
hands the reader the `.txt`.

### 3.10 A conformance pin for version 3

`runner/tests/test_ietf_draft_conformance.py` pins the sentences of
version 1 that must not silently move. Version 3 has none. The same
pattern, for the sentences this pass and the reviews fought for: the
`psk_ke` ban, the single-use MUST, the no-downgrade list, the re-post
budget, the cookie-key paragraph, the hold rule of Section 10.3, the
"session does not authorize the job" paragraph, the pre-authentication
list. Cheap, and it is how the next edit to the draft is kept honest.

## 4. The IETF side, a few weeks out

- The calendar. The IETF 127 cut-off for all drafts, including -00,
  was 2 November 2026 at 23:59 UTC, and it has passed. The submission
  tool stays closed from the cut-off until the meeting opens; IETF
  127 runs 14 to 20 November, so the earliest posting of
  `draft-slutsky-homing-pigeon-v3-00` is about 14-NOV. Verify the
  reopening on the submit page that day rather than trusting the
  pattern; the important-dates pages list the cut-off and not the
  reopening.
- What the upload needs. The `.xml` from the render (RFC 7991
  vocabulary, which `v: 3` in the front matter already selects); the
  datatracker runs its own idnits and xml2rfc checks at upload, and
  the pre-run of Section 3.8 is what keeps that from being the first
  time anyone sees a finding. A new document name is a new document
  at -00; it expires 185 days after posting.
- After posting. The request to `rfc-ise@rfc-editor.org`, as for
  versions 1 and 2, naming version 3 as a companion to the two
  already in the ISE's queue. Version 1 is still published first;
  version 3's normative reference to it becomes the RFC number, the
  same dependency version 2 has.
- The edits of Section 2.10 go in before the render that is uploaded,
  and the media type decision of 2.1 with them.
- Two optional things. A courtesy note to the TLS working group's
  list asking for a read of the RFC 9147 Section 5.8.2 timer profile
  and the Section 5.2 / 5.8.1 retransmission reading would put real
  DTLS eyes on the two places this draft interprets that RFC; an
  independent submission can ask. And a restructure of Section 16 in
  the RFC 3552 shape (what is in scope, what is out, each deleted
  mode named as a deleted mode with its test) would make the security
  considerations read as the reviewers of that stream expect.

## 5. Ideas toward the goals, in no particular order

- Post version 3 the day the tool reopens, with the Section 2.10
  checklist done and idnits run, and send the ISE note the same day.
- Fix 1.1 and 1.2 before the cold test, so the no-restart rule in the
  card is a convenience and not a precondition.
- Run the cold test (First Light) against the re-rendered `.txt` at
  `v3.15.129` or later, and write the four things it does not prove
  into the retrospective before it runs, so the night is not cited
  as coverage it is not.
- Turn the combination cells of 3.1 into the carriage's own bank,
  the way de_aztec banks the corpus: a run record per cell, counts
  of jobs and mails as the assertions, committed as proof of work.
- The conformance pin of 3.10, so the draft cannot drift under a
  later edit.
- The lifetime table of 3.4 as a short section of the proof note,
  with the hold map row closed.
- The policy-field sentence of 3.3 in `PROTOCOL.md` Section 14.1 and
  its two tests.
- The media type decision of 2.1, decided now and changed in the
  submission revision.
- The render-and-idnits workflow of 3.8, so the renders can never
  again be older than the source without a red check.
- A live run of the MIME sender against the standing provider, with
  a deliberate restart between the HelloRetryRequest and the cookied
  hello now that the cookie key survives it, and a second provider if
  one is available; each run's log minute into the proof note.
- The `Re:` observation of 3.6 from the mailbox history, and the
  prefix rule tightened or kept on that evidence.
- The readable-copy decision of 2.13 for versions 1 and 2, and the
  conformance test re-pointed at whatever is decided.
- One citation rule across the three drafts (2.11), applied at the
  next revision of each.
- Version 1's -04, when there is a reason for one: tickets single-use
  as a requirement on the datagram binding too, if the text is to
  follow the code; the pinned citation; and nothing else that is not
  already on the list, since -04 is also what version 3 will cite.
- The hybrid share revision, later and on its own: `X25519MLKEM768`
  under the same `psk_dhe_ke` rule, with the segmentation and replay
  matrix rerun against the larger hello, in a revision whose only
  change is the group.
- A platform-card field for the discovery fact in the reference
  implementation, now that Section 4.3 allows it, with a test that
  the fact admits nothing.
- A `STATUS.md` line per expiry: the version 1 and version 2 -03
  revisions expire in May 2027; a revision of each is due before then
  regardless of the ISE's pace.
- The -00 copies of versions 1 and 2 in `docs/ietf/` left exactly as
  posted, as `STATUS.md` already rules; the readable copies are the
  only files that question touches.
- GitHub Discussions, which `STATUS.md` names as the review venue,
  given the version 3 draft as a thread when it is posted, so a
  reviewer who arrives from the datatracker has somewhere to write.

## 6. What I would do first, if told to go

1. Section 1.1 and 1.2, with the tests, in one commit, and the one
   sentence in Section 10.3.
2. Sections 2.2, 2.3, 2.4, 2.5 and 2.7: four draft sentences and one
   classifier line, each with its test where one applies.
3. Re-render where the toolchain is, run idnits in submission mode,
   commit the four files, and re-pin the cold-test card.
4. The README line (2.12) and the submission checklist in `STATUS.md`
   (2.10).
5. Then 3.1, 3.10, 3.5 and 3.3 in that order, each its own commit,
   and the release after that is Grok's.
