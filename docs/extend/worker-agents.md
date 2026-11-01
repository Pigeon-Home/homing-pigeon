# Worker agents: an external agent on the task board

A worker agent is a program that does work, not one that only
reports or carries. It is neither extension kind: a sense files
alerts and never runs work, and a transport carries envelopes and
never reads them. A worker agent meets the runner at the task board
(PROTOCOL.md section 13) instead, and the pattern below needs no
change to the runner and no change to the agent.

The pattern fits any agent program with two properties:

- it accepts work through a documented local surface — a command, an
  HTTP endpoint on loopback, or a gateway protocol of its own — and
  reports the outcome of a finished turn;
- it, or a small bridge program beside it, can run shell commands,
  so it can drive the sender tooling in `runner/cloud/send_job.py`.

A conversational agent with tools and skills of its own is the
worked example throughout; OpenClaw is the current one, and its
concrete calls are named where the pattern needs one.

## The agent as a worker

The board's worker is any holder of the shared secret, or of a key
whose policy allows the board operations. The loop is the one the
protocol defines:

1. A task is opened with `task_submit` — by the owner, by another
   agent acting as a sender, or by a recipe the owner has pinned.
2. The worker pulls with a signed `task_request` naming its worker
   id and its capabilities, and is dealt a `task_offer`: an
   exclusive lease on one open task, lapsing after `task_timeout`
   (default 24 hours) if no result comes back.
3. The bridge hands the task's payload to the agent as one turn.
   For OpenClaw that is one documented call: `POST /hooks/agent` on
   the gateway's loopback port with the hooks token, which runs an
   isolated turn and can wait for its completion, or the equivalent
   `openclaw agent --agent <id> --message <text> --json` command.
4. The bridge files the turn's outcome as a signed `task_result`.
   The board answers `task_ack` — `done`, `pending_review` when the
   task asked for review, or a refusal naming why the result was
   not accepted. A task opened with `require_review: true` waits in
   `pending_review` until an owner's `task_approve` lands.

Results come back through the board and nowhere else: the bridge
reports what the agent's turn produced, and the board's states are
the record of the work.

## The agent as a sender

The same bridge, holding the same authority, can also run the
sender tooling directly: the agent's own shell tool runs
`send_job.py` to submit a signed job, open board tasks for other
workers, and read results — over any binding the runner has
enabled, such as the DTLS session binding, the file transport, or
email. From the runner's side the agent is an ordinary sender; its
messages are accepted or refused on their signatures and key
policies, exactly like any other sender's.

Two limits are plain. Nothing in this pattern wakes the Oracle:
the Oracle's wake gate is driven by local alerts of high or
critical severity filed by senses, and an external agent has no
call that raises one. The agent asks the runner questions the way
any sender does, by submitting work and reading its result. And
the protocol version 2 question exchange runs from the runner to
the job's answerer; an agent that wants to answer those questions
must implement the answer side of the exchange itself, and no
sender helper ships for that today.

## Authority

The two programs' credentials stay separate. The agent's gateway
and hooks tokens admit calls to the agent; the runner's shared
secret signs board messages. The bridge holds both, so the bridge
is the part to keep small: give it a key whose policy allows the
board operations and nothing else, rather than a key that can run
jobs. Board membership grants no runner privilege beyond claiming
tasks — and it grants the agent nothing at all on the box: an
agent's own tools run with whatever authority the agent itself was
given, which its own documentation is the place to check.

No bridge program ships with either project. This page describes a
composition of interfaces both projects already document; the
glue is a script the owner writes, of the size of the worker loop
above.
