# DARPA.md — A Proposal for SI-to-SI Collaborative Learning

## The idea

Two synthetic intelligences, operated by different (possibly competing) parties, communicate directly to improve each other's reinforcement learning — without either revealing proprietary internals. The researchers define the protocol and step back. The SIs do the rest.

## The loop

1. **SI-A (teacher)** generates a task and dispatches it to SI-B.
2. **SI-B (student)** executes the task and returns a result.
3. **SI-A** evaluates the result against hidden criteria and returns a score.
4. **SI-B** treats the score as an RL reward signal and updates accordingly.

Neither SI transmits weights, training data, architectures, or reasoning traces. SI-A never reveals its evaluation criteria. SI-B never reveals its solution process. Each party learns only what the protocol messages contain: task, result, score.

## The cryptographic intuition

This is knowledge-bounded interaction. Each message is a proof without revelation:

- SI-B's signed result proves "I solved the task" without revealing *how*.
- SI-A's signed score proves "I evaluated fairly" without revealing *against what*.

HMAC signatures (as used in homing-pigeon's v1 protocol) guarantee message authenticity — neither side can forge the other's signals. This is not zero-knowledge cryptography, but it shares the shape: verification without disclosure.

## What homing-pigeon provides

The v1 protocol is a transport and authentication layer for exactly this pattern: signed job dispatch, tamper-evident messages, sender verification. An SI that can sign a body can dispatch a task. An SI that can verify a signature can trust a score.

What homing-pigeon does *not* provide is the semantics: task format, scoring rubrics, reward encoding, session negotiation. Those would need to be specified as a layer above the transport — a shared language the SIs agree to speak before the researchers leave the room.

## The hard problems

**Adversarial teachers.** Nothing stops SI-A from crafting tasks designed to extract SI-B's capabilities — prompts engineered to leak training data or probe architecture. This is the model-extraction problem wearing a collaboration costume. Constraining allowable tasks requires either the researchers or a mutually trusted task generator.

**Who verifies the verifier.** SI-A's scores are SI-B's reward signal. A biased, compromised, or simply mistaken teacher produces a biased student, and SI-B has no independent way to know. Auditing the scorer requires a third party — another SI, or a human.

**The game theory.** In a competitive setting, each SI has incentive to learn maximally while revealing minimally — potentially to the point of sending uninformative tasks or sandbagging scores. Designing an interaction that is stable under mutual self-interest, without a referee, is an open problem. Mechanism design, not software engineering.

## Relationship to existing work

- **RLAIF** (RL from AI feedback): one model provides reward signals for another. DARPA extends this across organizational boundaries with cryptographic authentication.
- **AI debate**: models argue, a judge scores. DARPA generalizes the judge to any scoring function, transmitted as signed protocol messages.
- **Federated learning**: distributed training without data sharing. DARPA operates at the task/reward level rather than the gradient level, which sidesteps gradient-inversion attacks but gives up fine-grained learning signal.

## Status

This is a proposal, not a specification. The transport exists (homing-pigeon v1). The semantics, the game theory, and the trust model do not. Those are research problems.
