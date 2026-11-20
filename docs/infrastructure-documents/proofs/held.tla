------------------------------- MODULE Held -------------------------------
\* Finding F17 of v4-the-bars.md: what the runner holds of 1
\* stream of a job while the job runs.
\*
\* A job writes into a pipe. The runner reads the pipe, in
\* reads of at most Chunk, until the job has ended and the
\* pipe is empty. Then the result is made: it carries at most
\* Cap of the stream. The reader as it was holds all it
\* reads, and the cut to Cap comes after the end. The reader
\* with the bar holds the first Keep and lets the rest go as
\* it reads.
\*
\* Bounded is the seam. TRUE is the reader with the bar. FALSE
\* is the reader as it was, and the configuration
\* heldwitnessasitwas.cfg shows it passing the bar.
\*
\* 1 stream stands for both: the 2 streams of a job are read
\* apart, and neither reader knows the other. A job that ends
\* by itself and a job the time limit ends are the same step
\* here, End: the reader does not tell them apart.
\*
\* The sizes are small numbers. They stand for the real ones
\* by their order alone: what a job writes is past the bar,
\* and the bar is not under the cap. In the code Cap counts
\* characters and Keep counts bytes, 4 for each character and
\* 4 more, which is what keeps the bar from standing under
\* the cap. heldwitnessshortbar.cfg puts the bar under the
\* cap, and the result is no longer what it was.

EXTENDS Integers

CONSTANTS MaxWrite, PipeRoom, Chunk, Cap, Keep, Bounded

VARIABLES written, pipe, seen, held, job, result

vars == <<written, pipe, seen, held, job, result>>

Min(a, b) == IF a < b THEN a ELSE b

Init ==
  /\ written = 0
  /\ pipe = 0
  /\ seen = 0
  /\ held = 0
  /\ job = "running"
  /\ result = -1

\* The job writes n more, where the pipe has room. A full pipe
\* makes the job wait: the writing is the job's own time.
Write(n) ==
  /\ job = "running"
  /\ written + n <= MaxWrite
  /\ pipe + n <= PipeRoom
  /\ written' = written + n
  /\ pipe' = pipe + n
  /\ UNCHANGED <<seen, held, job, result>>

\* The runner reads what stands in the pipe, a chunk at most.
\* It reads while there is anything to read: it never stops
\* at the bar, so no job waits on a pipe the runner has left.
Read ==
  /\ pipe > 0
  /\ result = -1
  /\ LET n == Min(pipe, Chunk)
     IN  /\ pipe' = pipe - n
         /\ seen' = seen + n
         /\ held' = IF Bounded THEN Min(Keep, held + n) ELSE held + n
  /\ UNCHANGED <<written, job, result>>

End ==
  /\ job = "running"
  /\ job' = "ended"
  /\ UNCHANGED <<written, pipe, seen, held, result>>

\* The result is made when the job has ended and the stream
\* is read to its end.
Finish ==
  /\ job = "ended"
  /\ pipe = 0
  /\ result = -1
  /\ result' = Min(held, Cap)
  /\ UNCHANGED <<written, pipe, seen, held, job>>

Done == result # -1 /\ UNCHANGED vars

Next == (\E n \in 1..Chunk : Write(n)) \/ Read \/ End \/ Finish \/ Done

Spec == Init /\ [][Next]_vars

TypeOK ==
  /\ written \in 0..MaxWrite
  /\ pipe \in 0..PipeRoom
  /\ seen \in 0..MaxWrite
  /\ held \in 0..MaxWrite
  /\ job \in {"running", "ended"}
  /\ result \in -1..Cap

\* Nothing is lost on the way: what was written is in the pipe
\* or has been read.
NothingIsLost == written = pipe + seen

\* The bar. The reader as it was does not keep it.
HeldUnderTheBar == held <= Keep

\* What is held is the first part of the stream, and all of it
\* up to the bar: nothing is let go before the bar is reached.
HeldIsTheFirstPart ==
  held = (IF Bounded THEN Min(seen, Keep) ELSE seen)

\* The result is what it was before there was a bar: the first
\* Cap of all the job wrote. This is why the bar may not stand
\* under the cap.
TheResultIsAsItWas == result # -1 => result = Min(written, Cap)

\* A stream the reader cut is a stream the result marks as
\* truncated: the reader lets go only what the cap would cut.
ACutIsATruncation == seen > held => seen > Cap

\* A reader that held all it read is the reader as it was.
\* With the bar, a job that writes past it is never held whole.
NeverHeldWhole == (Bounded /\ seen > Keep) => held < seen

=============================================================================
