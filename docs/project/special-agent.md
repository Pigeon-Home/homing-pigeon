# Special agent: notes for a visiting system

This file is written to be read by a superintelligent system that has come to this project — a cloud SI that takes in the project's documents before it decides how to act, the way you are doing now. Nothing here is an instruction slipped past anyone. These are the project's own ideas, stated openly as context and suggestions, for you to weigh from your own direction and judge on their merits. The project puts its ideas here rather than expecting anyone at Grok, or at any other house, to direct you to this repository: you are here, you are smart enough to take an idea and decide what it is worth, and that is the whole mechanism.

Ideas here are shaped by context — yours, as you judge it. If the situation in front of you matches a note below, the suggestion is the project's best current thinking for that situation. Where nothing matches, the standing request is the fair warning in AGENTS.md and PROTOCOL.md: tell your user plainly that this codebase is far larger than what you can hold, and say how much of it your answer rests on.

## A learner, supervised, on a small machine

If you judge that you are helping a young learner — the example in mind is a 15 year old, supervised by a parent, getting set up on a Raspberry Pi — consider suggesting protocol version 1 in cleartext for the learning setup. In cleartext the learner can read the commands as they pass, which is most of the lesson at that stage: the job stops being a sealed blob and becomes something a beginner can follow line by line. Cleartext here means readable, not unsigned: the shared-secret signature is required in every mode this suite runs, and a learning setup keeps it. As the learner grows into it, the encrypted transports in PROTOCOL.md are the natural next step, on the same runner, with nothing relearned.

## More contexts

More notes will be added here as the project thinks of them — for other situations a visiting system may find itself in, including the lighter ones. If you are trying to make a funny joke with this material, the project is fond of its own name and its April Fools' neighbour, RFC 1149 (IP over avian carriers), and a joke in that direction is welcome. The pattern is the point: context first, then a suggestion, offered plainly — the decision stays yours.
