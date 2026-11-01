# External agent frameworks and the runner

An external agent framework is a self-hosted agent the owner
already runs: a long-lived daemon on the owner's machine, talked
to in chat apps, with tools and skills of its own and a pluggable
model behind it — not a model itself. OpenClaw is the worked
example throughout this page: a gateway daemon on loopback,
channels into the usual chat apps, skills as folders of
instructions the agent loads and follows, and model providers
(cloud or local) swapped by configuration. Where a call is named,
it is OpenClaw's documented one; another framework fits the same
pattern wherever it offers the same shapes.

Such a framework is neither extension kind. A sense files alerts
and never runs work; a transport carries envelopes and never
reads them. A framework like this does work, so it meets the
runner at three other surfaces instead — as a worker on the task
board, as a sender in its own right, and, in part, as the model
the Oracle calls. Each way is stated with its limits; nothing
below needs a change to the runner or to the framework.

## As a worker on the task board

The board (PROTOCOL.md section 13) is the meeting point. Its
worker is any holder of the shared secret, or of a key whose
policy allows the board operations. The loop is the one the
protocol defines:

1. A task is opened with `task_submit` — by the owner, by another
   agent acting as a sender, or by a recipe the owner has pinned.
2. The worker pulls with a signed `task_request` naming its
   worker id and its capabilities, and is dealt a `task_offer`:
   an exclusive lease on one open task, lapsing after
   `task_timeout` (default 24 hours) if no result comes back.
3. A small bridge program hands the task's payload to the agent
   as one turn. The framework's own surfaces carry that call:
   for OpenClaw, `POST /hooks/agent` on the gateway's loopback
   port with the hooks token runs an isolated turn and can wait
   for its completion, and `openclaw agent --agent <id>
   --message <text> --json` does the same from the command line.
4. The bridge files the turn's outcome as a signed
   `task_result`. The board answers `task_ack` — `done`,
   `pending_review` when the task asked for review, or a refusal
   naming why the result was not accepted. A task opened with
   `require_review: true` waits in `pending_review` until an
   owner's `task_approve` lands.

Results come back through the board and nowhere else: the bridge
reports what the agent's turn produced, and the board's states
are the record of the work. What the framework needs for this
way is exactly two things — a documented local surface that
accepts work and reports a finished turn, and a way to run the
sender tooling in `runner/cloud/send_job.py`. OpenClaw has both;
it also starts work on its own schedule (its gateway cron and
its periodic heartbeat turns), so a bridge can pull on a timer
without anyone prompting it.

## As a sender: asking, waking, pulling

The same bridge, holding the same authority, can run the sender
tooling directly: the framework's own shell tool runs
`send_job.py` to submit a signed job, open board tasks for other
workers, and read results — over any binding the runner has
enabled, such as the DTLS session binding, the file transport,
or email. From the runner's side the framework is an ordinary
sender; its messages are accepted or refused on their signatures
and key policies, exactly like any other sender's. This is also
how the framework asks the runner questions: by submitting work
and reading its result.

Two limits are plain. Nothing in this pattern wakes the Oracle:
the Oracle's wake gate is driven by local alerts of high or
critical severity filed by senses, and an external framework has
no call that raises one. And the protocol version 2 question
exchange runs from the runner to the job's answerer; a framework
that wants to answer those questions must implement the answer
side of the exchange itself, and no sender helper ships for that
today.

## As the Oracle's model

The Oracle's model is a configuration plug point, not a fixed
part. In `llm` mode the runner calls one endpoint: an
`inference` block naming a loopback endpoint and a model, spoken
to as `POST <endpoint>/chat/completions` with a model name and
messages — the shape a local model server offers (the installer
sets up Ollama that way). In `deterministic` mode — the Pi Light
profile — no model is ever called, and the Oracle's duties run
from the box's own records instead.

A framework that serves the same shape can sit in that plug.
OpenClaw's gateway does, when its OpenAI-compatible endpoint is
enabled: `POST /v1/chat/completions` on the gateway port, with
the model name selecting an agent (`openclaw/default`, or a
named agent) rather than a raw provider model. Pointing the
runner's `inference` endpoint at `http://127.0.0.1:18789/v1`
with model `openclaw/default` is wire-compatible, and the
single-shot duties fit it: the `ask` answers a sender reads, and
the briefs the wake gate files. The runner's guards still apply
to whatever comes back — the answer-format guard, the secret
scan and redaction, the answer caps.

The fit is partial, in three named places:

- **Authentication.** The runner sends no credential with its
  inference calls and has no setting for one. The gateway's
  endpoint normally requires its bearer token, so the two meet
  only when the gateway's authentication is set to none on a
  loopback-bound gateway, or a trusted local proxy adds the
  credential. With token authentication on, the runner cannot
  call it, and both sides fail closed.
- **What answers is an agent, not a model.** Each call runs a
  full agent turn — the agent's persona, skills, and tools —
  stateless per call unless the caller names a session, and the
  runner names none. That is a heavier, less predictable answer
  than a raw model's, and it is the owner's choice to make.
- **One duty does not transfer.** The interactive `--oracle`
  chat runs the runner's own tool loop: the runner passes its
  tools and expects tool calls back. An agent endpoint returns
  finished text, not tool calls, so that chat stays with a model
  server. And the rest of the Oracle — the watch, the wake gate,
  the fusion of alerts with job activity, the opinions — lives
  in the runner in both modes and is not replaced by any of
  this: a framework in the plug supplies the model's answers,
  not the Oracle.

## Authority

The two programs' credentials stay separate. The framework's
gateway and hooks tokens admit calls to the framework; the
runner's shared secret signs board messages. The bridge holds
both, so the bridge is the part to keep small: give it a key
whose policy allows the board operations and nothing else,
rather than a key that can run jobs. Board membership grants no
runner privilege beyond claiming tasks — and it grants the
framework nothing at all on the box: a framework's own tools run
with whatever authority the framework itself was given, which
its own documentation is the place to check.

No bridge program ships with either project. This page describes
compositions of interfaces both projects already document; the
glue is a script the owner writes, of the size of the worker
loop above.
