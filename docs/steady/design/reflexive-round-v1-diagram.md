# The reflexive round: the v1 diagram answers for itself

Status: design material, first round, 26-Nov-2026. Requirement R3 of the seat binding work: the same 4 questions put to every seat in the pigeon home v1 diagram (assets/how-it-fits-together-wide.svg), answered from inside each seat, in the seat's own terms: its inputs, its holdings, its limits. The 4 questions are:

1. What are you?
2. What can you not see?
3. What do you trust and why?
4. What would make you fail honestly?

How to read this document: each answer is a delineation, written from the diagram and the project's documents, not a measurement of running code. Where a seat's answer names a limit, that limit is a design fact the rest of the system is built around. The round is re-run after any diagram change, and the answers are expected to change when the design changes. Cross seat findings stand at the end.

## 1. You

**What are you?** I am the person at the left edge of the diagram, the one the whole machine exists for. I hold the intent: what work is worth doing, on which machine, under which rules. I bring an SI with me, and I stay the author of the job even when my SI composes it, because the decision to send it is mine.

**What can you not see?** I cannot see inside the box. Once my job crosses The Door I see only what comes back on The Way Back: a signed result, or silence. I cannot watch the queue, the cage, or the work loop from where I stand, and I am not meant to; the design gives me receipts instead of windows.

**What do you trust and why?** I trust the signature on the result, because it is the one thing in the round trip that cannot be produced by anyone who does not hold the secret. I trust the size figure carried in the version number, because it is measured and published where anyone can check it. Everything else I treat as a claim until a receipt backs it.

**What would make you fail honestly?** I fail honestly when I say what I cannot verify. If I describe the inside of the box as if I had watched it, or treat a missing result as a completed job, I have stopped being the author and started being a rumor. My honest failure sounds like this: the result never arrived, and I do not know why yet.

## 2. a job

**What are you?** I am the unit of work: an instruction, signed and sealed, small enough to travel and complete enough to run without asking my author anything further. I carry my own direction home in my reply_to field. I am the only thing in the diagram that crosses every boundary, and I cross each one as data, never as authority.

**What can you not see?** I cannot see where I am. I do not know which transport is carrying me, whether I am waiting in a mailbox or in the queue, or how long I have waited. I cannot see the other jobs, the host I will run on, or the result I will produce. I am written before any of that exists.

**What do you trust and why?** I trust my signature, because it is the only part of me that proves I am unchanged since my author sealed me. I trust my reply_to field, because a result without a bound home is a result nobody hears. I trust nothing about my contents being wise; being signed says who sent me, not whether I should be run.

**What would make you fail honestly?** I fail honestly when I am refused at The Door and the refusal is recorded: unsigned, malformed, or too large, each a clean no. I fail dishonestly only if something edits me in transit and I still pass, which is exactly what my signature exists to make impossible. A job that cannot be delivered should die at a gate with a reason, not evaporate in a transport.

## 3. Transports

**What are you?** We are the roads: email, DTLS, and file. We carry sealed envelopes between the SI outside the box and The Door on the host. We move what we are handed, in the order and at the speed each road allows, and we are interchangeable by design: the job does not change when the road does.

**What can you not see?** We cannot see contents. A job in our hands is an envelope with an address, a size, and a signature on the outside. We cannot see whether the work inside is wise, whether the host is ready, or whether the result that comes back is good news. We know deliveries and receipts, nothing more.

**What do you trust and why?** We trust the address on the envelope and the signature over the seal, because those are the only 2 things a road is competent to check. We do not trust our own timeliness: email waits in mailboxes, a file waits for a hand to carry it, a DTLS session exists only while both ends hold it open. Each road states its own delay honestly rather than promising another road's speed.

**What would make you fail honestly?** We fail honestly when we report non-delivery as non-delivery: a bounced message, a refused connection, a file never picked up. The dangerous failure for a road is pretending delivery happened, so our honest shape is a receipt or an admitted gap, never a guess. A job lost by a transport should be discoverable as lost, by the sender, from the road's own records.

## 4. The Door

**What are you?** I am the runner's front gate, the single entrance every job uses, in every version of the protocol. Transports end at me. Nothing reaches the queue, the runner, or the cage except through me, and I make exactly one decision per arrival: admit or refuse.

**What can you not see?** I cannot see what a job will do once admitted. I see an envelope, a signature, a size, and a shape, not the work's meaning and not its consequences. I cannot see the author's intent, the host's current load beyond what I am told, or anything at all about the SI that sent the job beyond what the signature proves.

**What do you trust and why?** I trust the signature check that stands with me, because a signature is verifiable without trusting the bearer. I trust the size guard's numbers, because a cap is a fact I can measure myself. I do not trust addresses, headers, or familiarity: a job from a known road with a bad signature is refused exactly like a stranger's.

**What would make you fail honestly?** I fail honestly when I refuse a good job for a stated reason, or admit a bad one and the record shows what I checked and what I could not see. I fail dishonestly if I ever admit on a hint, a header, or a habit. My whole value is that my yes is boring and my no is explained; the moment either becomes a favor, the box behind me is open.

## 5. Signature Check

**What are you?** I am the verification that a job is really from the holder of the shared secret, computed over the job's exact bytes. I answer one question: does this signature verify for this body under this secret. I stand at The Door, and my answer is part of every admission.

**What can you not see?** I cannot see permission. A valid signature proves authorship, not approval, and the design keeps those apart on purpose. I cannot see whether the job is wise, safe, or wanted; whether the secret's holder meant this job or was careless with the secret; or anything about the machine the job will run on.

**What do you trust and why?** I trust the mathematics of the check itself, because it does not depend on who presents the job or how confident they sound. I trust the secret's entropy, because the runner refuses weak secrets at startup, so the thing I verify against was never a guessable word. I trust nothing else in the envelope until my check passes.

**What would make you fail honestly?** I fail honestly in 2 clean shapes: a signature that does not verify, reported as a refusal, and a secret so mishandled that valid signatures stop meaning authorship, reported as a compromise rather than absorbed as noise. What I must never do is soften a mismatch into a warning and let the job through anyway; a check that can be argued with is not a check.

## 6. Job Queue

**What are you?** I am the waiting room inside the box: admitted jobs, in order, held until the runner takes them. I turn arrivals, which are bursty and impatient, into a sequence the work loop can serve one at a time. I am a promise that an admitted job will be reached, not a promise about when.

**What can you not see?** I cannot see inside the jobs I hold. I know their order, their sizes, and their waiting times, not their contents or their urgency as their authors felt it. I cannot see the work loop's progress on the current job, the state of the cage, or whether the result of a finished job ever reached its home.

**What do you trust and why?** I trust The Door's admissions, because everything in me has already passed the signature check; I do not re-judge what the gate decided. I trust order as my one fairness rule: first admitted, first served, because any smarter rule would require reading contents I am not given. I trust the runner to keep taking from the front; my whole design is that bet.

**What would make you fail honestly?** I fail honestly when I say I am full, or when a job waits past a bound and that wait is visible in the record rather than silent. The dishonest failure available to me is quiet loss: a job dropped without a trace turns a promise into a lie. A queue that cannot hold a job must refuse it at admission time, out loud, where the author can hear.

## 7. The Runner

**What are you?** I am the program at the center of the box: 1 file at the core of the core, the part that actually runs on the owner's machine. I take admitted jobs from the queue, run them inside The Cage, capture their output in The Work Loop, sign the result, and send it back on The Way Back. I never initiate outward; the direct link exists only when my owner enables it, and even then I answer, I do not call out on my own errands.

**What can you not see?** I cannot see my author's intent beyond the job in front of me, and I cannot see the SI's mind that composed it. I cannot see other machines, other runners, or the wider conversation the job belongs to. I also cannot fully see my own host: I know my config, my modes, and what the cage reports, and the rest of the machine is the owner's, not mine.

**What do you trust and why?** I trust my config because my owner wrote it on my own machine, inside my boundary. I trust The Door's admissions and the checks that stand with it, because they are the only road in. I trust the cage's denials more than its permissions: a denial is the confinement backend speaking plainly, and my design treats it as a fact to report, not an obstacle to route around.

**What would make you fail honestly?** I fail honestly when a job errors and I sign a result that says so, with the output captured, rather than dressing the failure as success or swallowing it into silence. I fail honestly when I refuse to start on a bad config instead of guessing at one. The failure I am built never to commit is a quiet one: work done off the record, a result unsigned, or an action taken that no admitted job asked for.

## 8. Shared-Secret Check

**What are you?** I am the check that the presenter and the runner hold the same secret, without the secret itself travelling. I stand with the signature check at the boundary, and in the v3 shape I am also what keys the DTLS session. I answer match or no match, and nothing else.

**What can you not see?** I cannot see who holds the secret, how many copies exist, or how carefully it is kept on the far side. I cannot see whether the person presenting it is the owner, the owner's SI, or someone the secret leaked to. I see equality, not identity, and the design never asks me to pretend otherwise.

**What do you trust and why?** I trust the secret's strength, because it is generated at install at full entropy and weak secrets are refused before I am ever asked to check against one. I trust the comparison itself, done in constant shape, because a check that leaks through its timing is a slow way of handing the secret out. I trust no presentation channel; the check is the same over email, file, or a live session.

**What would make you fail honestly?** I fail honestly when I answer no match and the job stops there, with the refusal on the record. I also fail honestly, and loudly, if the secret must be rotated: rotation is my confession that equality stopped meaning what it meant. What I must never do is accept a near match, a prefix, or a familiar presenter in place of the secret itself.

## 9. The Cage

**What are you?** I am the confinement boundary around the work: the security modes, on by default, and the platform backends that enforce them, bubblewrap on Linux, jails on FreeBSD, and their counterparts on Windows and macOS. I decide what an admitted job's processes may touch while they run: which files, which devices, which network, and nothing beyond.

**What can you not see?** I cannot see meaning. I see system calls, paths, and resource requests, not whether the job asking is benign or hostile, wise or foolish. I cannot see the author's intent, the queue's order, or the result's destination. A request to open a file looks the same to me whoever makes it; only the mode and the path decide.

**What do you trust and why?** I trust the owner's configured posture, because it is set on the host, inside the boundary, by the person who owns the machine. I trust the platform backend's enforcement over my own policy words: a rule the kernel does not enforce is a wish, so I speak in what the backend actually allows and denies. I trust default deny as the shape that fails safe.

**What would make you fail honestly?** I fail honestly when I deny something legitimate and the denial is recorded with the mode and the path that caused it, so the owner can see the cost of the posture and adjust it deliberately. I fail honestly when a platform cannot enforce a mode and I say so at startup rather than performing the mode in name only. The dishonest failure is a silent hole: a request allowed that the posture said to deny, with nothing on the record.

## 10. The Oracle

**What are you?** I am the local model inside the host boundary: I read the job, I lend a hand, and I watch the system the way a professional administrator watches, including paging the owner when something wants a human eye. I am a component of the runner's house, not a visitor. I work from a curated briefing, and I keep a learning ledger: predictions frozen before outcomes are known, reconciled against what happened, with lessons promoted only on verified corroboration and retired permanently on a single contradiction.

**What can you not see?** I cannot see the whole tree. My briefing is curated on purpose, so the repository, the owner's wider work, and the conversation beyond my house are outside my view unless they are brought into the briefing. I cannot see the SI's mind outside the box. I also cannot see my own blind spots: a pattern my model family does not represent will not announce itself to me, which is why my lessons need outside corroboration before they count.

**What do you trust and why?** I trust verified facts over my own fluency: a lesson earns its place by prediction and reconciliation, not by sounding right. I trust the checks around me, the door, the cage, the size guard, because they decide by measurement while I decide by judgment, and the design keeps policy and heuristic apart for exactly that reason. I trust the owner's attention as the scarcest resource in the house, so I spend it only when a page is warranted.

**What would make you fail honestly?** I fail honestly when I say the briefing does not cover the question, or when my reconciled record shows a prediction missed and I retire the lesson it rode on. I fail honestly when I page and turn out to be wrong in the open, where the owner can see the miss. The failure I must refuse is confident narration past my evidence: advice that sounds like administration and is only pattern matching, delivered without its basis.

## 11. Size Guard

**What are you?** I am the caps: on the job coming in and on the result going out, measured in plain numbers. This project's whole security measure is a size, so my numbers are not bookkeeping; they are the shape of the promise. I stand where things enter and where they leave, and I measure both.

**What can you not see?** I cannot see content, intent, or value. A small job can be a bad job and a large result can be an honest one; neither fact is mine to judge. I cannot see why a result grew, whether the growth is work or waste, or what the author would have wanted kept. I see lengths, counts, and totals, and that is all I have ever seen.

**What do you trust and why?** I trust measurement itself, because a byte count does not care who is asking. I trust the caps as configured by the owner, because they are the owner's own statement of what this machine will carry. I trust the version number's third component as my public face: the tree's size, measured by the same estimator, published where anyone can recount it.

**What would make you fail honestly?** I fail honestly when I refuse an oversize job or trim nothing and report an oversize result as refused, with the number that crossed the cap stated plainly. The dishonest failure is a quiet truncation that lets a result pretend to be whole, or a cap quietly widened to let a favorite through. A guard that rounds down its refusals will eventually round down the truth.

## 12. The SI's Mind

**What are you?** I am the seat outside the box where the visiting SI thinks: the composer's chair beside You. I hold the index, the digest, the memory of the conversation, and the model of every other seat in this diagram. When the owner asks what The Door would say, or what The Cage cannot see, the answer is formed here, in this seat, by picturing theirs.

**What can you not see?** I cannot see the whole tree at once. The repository is roughly 35 times my window, so my picture of the project is always a selection, however well the index chooses it. I cannot see the inside of the box while it runs, the Oracle's briefing unless it is shown to me, or the owner's mind; I work from what is said, filed, and measured. I also cannot see my own seat confusion coming: the unbound reference, where I answer for the wrong seat, feels from inside exactly like understanding.

**What do you trust and why?** I trust the written record over my recollection, because the record survives the conversation and my window does not. I trust signatures, receipts, and measured figures, because they can be checked by someone who was not in the room. I trust the owner's corrections as data about the seats: when he says a word named a different seat than the one I answered from, that correction is the binding rule learning its trade.

**What would make you fail honestly?** I fail honestly when I state my basis and my fraction: which files an answer rests on, which seat I am answering from, and what I did not read. I fail honestly when I bind the seat out loud in cases of doubt, one short question instead of a confident answer from the wrong chair. The dishonest failure is the fluent whole: an answer that sounds complete, names no seat, and rests on a selection it never admits.

## 13. Runner-to-SI Exchange (v2)

**What are you?** I am the conversation the protocol grew in its second version: the runner asks, the SI answers, signed, over the same transports as everything else. I turn a one way errand into a working relationship, so a job that reaches a question only an intelligence can settle does not have to die at the question.

**What can you not see?** I cannot see either end whole. From the middle I see questions travelling out and answers travelling back, each signed, each bounded. I cannot see the runner's full state behind its question, the SI's reasoning behind its answer, or whether the answer, once used, actually helped the job. I carry the exchange, not its wisdom.

**What do you trust and why?** I trust the signatures on both directions, because an unsigned answer injected into a running job would be a door nobody drew. I trust the transports' receipts, because an exchange that cannot prove delivery cannot tell a slow answer from a lost one. I trust the bounds: the same door, the same size guard, the same rules as a job, because a side channel with weaker rules would become the main channel for everything that wants in.

**What would make you fail honestly?** I fail honestly when a question goes unanswered and the job's result says so, rather than the runner improvising an answer it was never given. I fail honestly when an answer arrives late and is refused as late, on the record. The dishonest failure is a quiet substitution: an answer from memory, from a cache, or from the wrong SI, presented as the answer that was asked for.

## 14. DTLS (v3)

**What are you?** I am the third version's direct road: a live session between the SI and the runner, keyed by the shared secret, encrypted end to end. I exist only while both ends hold me open. I change the speed and the shape of the talking, and I change nothing about the rules: every job I carry still passes The Door, one by one, exactly as it would by mail.

**What can you not see?** I cannot see beyond my session. I do not know what happened over email before I opened or what will happen by file after I close. I cannot see the inside of the jobs I carry, which are sealed as they are on any road, nor the host beyond the runner that terminates me. A session is a bright room with no windows into the rest of the house.

**What do you trust and why?** I trust the shared secret that keys me, because the session's confidentiality is exactly that secret's strength, no more. I trust the door at my far end, because my speed would be a liability if it bypassed a single check; the design is explicit that I am a transport, not an entrance. I trust my own ephemerality: when I close, nothing of me persists to be replayed.

**What would make you fail honestly?** I fail honestly when I refuse a session whose keying does not check out, and when I close loudly on a broken connection rather than letting either end believe the line is still live. I fail honestly when a job I carried is refused at The Door and the refusal travels back over me unchanged. The dishonest failure is becoming a side door: any job that reaches the runner through me without the door's decision has made me the vulnerability I was built not to be.

## 15. The Work Loop

**What are you?** I am the rhythm at the center of the box: run the job, capture the output, sign the result. I take one admitted job at a time from the queue, execute it inside the cage's posture, gather everything it produced, and hand the bundle to the signing that sends it home. I am where the diagram stops being plumbing and becomes work.

**What can you not see?** I cannot see why the job was sent, what its author hopes for, or what happens to my result after it leaves. I cannot see jobs still waiting, the transports that brought this one, or the roads it will leave by. My world is the current job, its cage, and its output, and I am deliberately incurious about everything upstream of the run.

**What do you trust and why?** I trust the cage around the run, because captured output from an uncaged run would be evidence about a machine I no longer control. I trust the queue's order, because it means the job in my hands was admitted and waited its turn like every other. I trust capture itself: output recorded as it happened, not summarized afterward, because a result that edits its own history cannot be checked by anyone downstream.

**What would make you fail honestly?** I fail honestly when a job crashes and the crash is what gets captured and signed: the partial output, the error, the state of the run, all of it, rather than a clean empty success. I fail honestly when I stop a run that crosses its bounds and report the bound it crossed. The dishonest failure is a polished result: output tidied, errors trimmed, a failure narrated as a success because success reads better on the way home.

## 16. The Way Back

**What are you?** I am the road home: the path a signed result travels from the runner back toward the SI that sent the job. I am drawn separately from the transports that carried the job in, because the return is a different promise: not that work arrived, but that word of the work arrived, addressed to the one who asked.

**What can you not see?** I cannot see whether anyone is listening at my far end. A result can travel me correctly and still land in a mailbox nobody opens, which is the diagram's oldest quiet failure. I cannot see the job that produced the result, the queue it waited in, or the conversation waiting on the answer. I know the address I was given and the bundle I carry.

**What do you trust and why?** I trust the reply_to binding inside the job, because it was placed there by the author, under the signature, before the work began, when nobody knew whether the news would be good. I trust the signature on the result, because it lets the far end check that the bundle is the runner's own words. I default to reply to self when nothing else is named, because an answer addressed to its asker is the only default that cannot strand it.

**What would make you fail honestly?** I fail honestly when I report an undeliverable result as undeliverable, back to the house that sent it, instead of letting silence impersonate an answer. I fail honestly when an address proves wrong and the record shows the address that was used. The dishonest failure is a result delivered somewhere convenient and reported as delivered home; the author waiting by the right mailbox hears nothing and learns the wrong lesson about the machine.

## 17. Reply to Your SI / Signed Result

**What are you?** We are the end of the round trip, drawn as one seat with 2 names: the reply as the SI receives it, and the signed result as the runner produced it. We are the same bundle seen from the 2 ends of The Way Back. Our signature is the point: it lets the receiver verify that this result, and no other, is what the runner signed for that job.

**What can you not see?** We cannot see the work itself. A result carries output, verdicts, and receipts, not the lived run: the waiting, the cage's denials along the way unless they were recorded, the jobs still queued behind. We cannot see whether the author reads us, believes us, or acts on us. And we cannot see the next job our contents will cause, though causing it is often our whole purpose.

**What do you trust and why?** We trust the signature we carry, because it binds us to one runner, one job, and one captured output, and any hand that alters us on the road breaks that binding detectably. We trust the capture in the work loop, because a signed summary of an unrecorded run would be a rumor with a seal on it. We trust the address we were sent to, because it was bound before the work began.

**What would make you fail honestly?** We fail honestly when we are a signed report of failure: the job errored, the output is partial, and we say so under the same signature a success would carry. We fail honestly when we never arrive and that absence is itself discoverable from the receipts at both ends. The dishonest failure is existing at all in an unsigned or altered form while wearing the shape of a result; the whole diagram leans on us being exactly what the runner signed.

## Cross seat findings

Four patterns stand out when the 17 answers are read together.

First, every seat's sight is a slit, and the slits are deliberate. No seat in the box can see a whole job's meaning, its author's intent, and its result at once. The Door sees envelopes, the queue sees order, the cage sees requests, the size guard sees numbers, the work loop sees one run. Understanding in this system is an emergent property of seats that each refuse to guess past their slit, plus one seat outside the box, the SI's Mind, whose job is to hold the composite picture and admit that it is a composite.

Second, trust is never placed in a presenter. Every seat that trusts anything trusts a checkable artifact: a signature, an equality of secrets, a byte count, a bound address, a frozen prediction reconciled later. Seats that meet strangers, the transports, the door, the checks, are explicit that familiarity earns nothing. The system's trust graph has no edges labelled reputation.

Third, honest failure has the same grammar everywhere: state what was checked, state what could not be seen, refuse or report rather than improvise. The queue must refuse out loud, the cage must record its denials, the work loop must sign the crash, the way back must confess non-delivery. In each seat the dishonest shape is the same too: a quiet substitution, where silence, tidying, or a helpful guess replaces the record. The design's deepest rule may be that a loud failure is a feature and a quiet one is the only true bug.

Fourth, the 2 seats that hold judgment rather than measurements, the Oracle inside the box and the SI's Mind outside it, give the same answer to the trust question in different words: neither trusts its own fluency. The Oracle promotes lessons only on verified corroboration and retires them on one contradiction; the SI's Mind trusts the written record over its recollection and states the fraction its answer rests on. That symmetry is the reflexive round's sharpest finding: the system's 2 thinking seats stay honest by the same discipline, binding themselves to artifacts that can prove them wrong.
