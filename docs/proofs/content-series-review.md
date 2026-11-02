# The content-independence series: review and redo

This note reviews the content-independence series as landed (the records stage7.md through stage10.md and their test harnesses) and states the redo that is asked for. The verdict of the first-hand verification stands behind every point: the lower rungs hold as far as they go, and what follows is about how far that is.

## 1. A rung is missing entirely

The ladder runs: first rung, 500, 5,000, 50,000, 500,000, and the production cap. The series as landed covered the first rung, 50,000, 500,000, and the cap. The 5,000-character rung was skipped — not attempted, and not recorded as skipped. A ladder with a rung missing in the middle supports no claim that the rungs above rest on the ones below. The redo covers every rung, in order, with none missing.

## 2. The stage numbering collided with the ladder's

The series labeled its first-rung piece "Stage 7." On the ladder, Stage 7 is the 5,000-character rung. Two different pieces of work carried one stage name, and the records read as if the ladder's Stage 7 had been done when it had not. The redo names its pieces by rung and by subject, and does not reuse stage numbers for different work.

## 3. The Windows shell was never claimed — at any rung

Every record in the series states the same limit: PowerShell not claimed. The runner runs on Windows; jobs there carry PowerShell scripts, and the gate treats them exactly as it treats shell scripts. That is half the claim, and it is the half that was never touched. The redo covers both shells at every rung: scripts built from PowerShell's own constructs — pipelines, cmdlets, conditionals, loops, functions, grouping, expansions, redirection, quoting forms — syntax-checked with the real PowerShell parser and presented to the real gate, the same treatment bash received. If a rung cannot be covered in PowerShell, the record says so at that rung, in plain words, and says why.

## 4. The higher rungs were padded with a single building block

At 50,000 characters the set was three scripts. At 500,000 it was a chain of one repeated command a hundred thousand times, an echo of one long quoted run, and an echo of one repeated word. At the cap, the same shapes again. That tests whether the gate measures length correctly; it does not test content-independence, because almost no content is in it — one construct, stretched. The redo builds every rung's scripts from the full construct set: simple commands, pipelines, conjunction and fallback chains, separators, conditionals, loops, functions, grouping, expansions of every form, arithmetic, redirection, and all quoting forms — composed and nested, varied through the whole length of the script, so that reaching the rung's length takes real material and not repetition of a single piece.

## 5. The construction shape crashed the syntax checker, and the record claimed a clean pass

A script built as one single line of roughly two hundred nine thousand tiny commands makes the shell's own syntax checker crash under its normal memory limit. The gate was never involved; the checking tool died before it could give a verdict. Despite that, the top rung's record went in claiming its test file passed in full. It did not — three of its four tests passed, and the fourth never got a verdict from the checker at all. That failure has since been found independently, fixed on main by building the long chains one command per line, and recorded honestly. The redo uses the one-command-per-line shape everywhere, keeps every length exact, and a record claims only what its output actually showed. A crashed checker is recorded as a crashed checker.

## 6. What was produced is a sample; the ask is an enumeration

The standing challenge, written in thinking.md, is to generate scripts from the shell's building blocks systematically — the constructs a default system actually ships, combined the ways they can be combined — and to show the gate's verdict depends on length and never on which constructs were used. Twenty-two scripts at the first rung and three at each rung above it is a sample, and a thin one at the top. The redo moves toward the challenge instead of around it: at the smallest rung, generate over the construct set systematically — the constructs, their combinations, their nestings, the quoting variants — in the thousands, and at every rung state plainly how the set was generated and what part of the construct space it covers. Where a rung is still a sample, the record calls it a sample.

## The redo, in one paragraph

Every rung — first rung, 5,000, 50,000, 500,000, and the production cap — in both shells, built from the full construct set with varied material at full length, one command per line, syntax-checked with each shell's real parser, presented to the real gate, with a record per rung that states what was generated, how it was generated, what the gate did, what the checkers did, and what is not claimed. The existing records stay in place as history; the new series states that it supersedes them and why. Nothing in the redo counts as defended until it has been verified first-hand — that was true of the first series and it is true of this one.
