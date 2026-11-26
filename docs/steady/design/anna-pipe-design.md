<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->
# The Anna pipe and the Anna window: design

Design record for the Homing Pigeon app in Anna: how a typed
message in Anna becomes signed work on a runner, how the signed
result comes back, and how the app grows a real window a user can
open and work in. Written 2026-11-25 at the owner's direct order
that the design be represented in the repository and documented
verbosely. The research behind it was done the same day; the
build it describes was in progress when the first version of
this document landed and has since been built locally, and
section 17 states exactly what stands and what does not.

Related reading in this tree: `docs/steady/design/cs_canoe.md`
for the hosted service the bridge belongs to,
`docs/infrastructure-documents/extend/transports.md` for the
hosted queue transport this design rides on, `PROTOCOL.md`
sections 2, 3 and 9 for the bindings, the verification order and
the result views, and `docs/steady/sending.md` for the clock job,
the first live check this design repeats.

## Contents

1. Why this document exists
2. The app as it stands today
3. Why clicking the icon does nothing
4. How the app wakes today: the mention
5. Why Anna's own script running is not our runner
6. Design lineage: the ranked shapes and the choice
7. The pipe: shape of the whole thing
8. What already exists and ships
9. The bridge
10. The dispatch Executa
11. Route A end to end: the clock sentence
12. The window: Route B
13. The window design model: the Image app
14. Route C: Anna's agent carrying our protocol
15. Surfaces considered as the pipe, and why not
16. Honesty limits
17. Build state at the time of writing
18. Test plan
19. The sealed verdict: the demo beyond the clock
20. Open questions carried forward
21. Sources

## 1. Why this document exists

The owner opened his Anna dashboard, clicked the Homing Pigeon
icon, and nothing happened. He typed test words into the "Ask
Anna anything..." box and Anna's own agent answered, not our
app. Both observations are correct behaviour for the app as
submitted, and both miss the thing he actually wants, which he
stated plainly: type a message, have it somehow go to the
computer, and have the computer check its clock and answer.

This document records the design that makes that sentence true
without giving up any property the protocol exists for. It also
records the second thing he asked for once the first design
stood: make the app functional when it is opened, the way the
video and image apps in Anna are functional, with a window of
its own. The window design follows the model of Anna's Image
app, described from the owner's own photo of his dashboard in
section 13.

## 2. The app as it stands today

From the local preparation record and the publish record of
2026-11-20:

- The app stands in Anna's system as app_id 993, slug
  `homing-pigeon`, category developer-tools, under the project's
  developer account.
- On 2026-11-20 the working draft was pushed, the bundled
  Executa was registered, version 0.1.0 was cut and submitted for
  review. The status at that moment was pending_review, with
  0.1.0 pinned in that review round. Release waits on Anna's
  approval.
- The bundled Executa is a JSON-RPC 2.0 over stdio plugin in
  Python, standard library only, with three tools:
  - `runner_status` reports whether a Homing Pigeon runner is
    installed on the machine the user's Anna Agent runs on:
    config present, program found, version string. It is read
    only and never reads the config's contents.
  - `run_poll_cycle` starts that installed runner for one
    bounded poll cycle: the runner polls its mailbox, verifies
    signatures, runs signed jobs already waiting there, and
    sends signed results.
  - `runner_posture` returns the runner's read only posture
    report.
- The Executa package passed its 18 test suite locally and an
  end to end smoke test, including a read only `runner_status`
  against a real install on the build machine.

What cannot be stated today: whether Anna has since approved,
approved without publishing, or rejected 0.1.0. No local record
after 2026-11-20 carries a status, and settling it needs the
console or the status command under the owner's account
session. The dashboard icon in the owner's photo is consistent
with a developer side install of his own pending app. Nothing
in this design depends on the answer: a follow on version
carries the new shape either way.

Even at its best, today's app is a remote control for a runner
that must already be installed on the same machine as the
user's Anna Agent. It composes nothing, signs nothing and
dispatches nothing. Its own addendum says so honestly. The
dispatch surface the owner asked for does not exist yet.
Section 7 designs it.

## 3. Why clicking the icon does nothing

Two different kinds of app stand side by side on the dashboard,
and Anna's developer documentation draws the line exactly where
the owner's photos show it.

A window needs a `ui` section. The App UI Overview page states
that a schema 1 app is just a manifest plus a set of Executas,
and that moving the manifest to schema 2 or above and adding a
`ui` section is what graduates an app to the talk to the app,
run in a window form. A window opens only through the model
tools `open_app_view`, `update_app_view` and `close_app_view`,
and those tools are injected only when at least one mentioned
app declares `ui.views`. The video app on the dashboard ships a
static bundle and named views, so clicking it summons a real
window with its own workspace, forms and buttons.

Our submitted app declares no `ui` at all. The manifest cut as
version 0.1.0 is schema 4 with exactly one entry point,
`required_executas` naming the bundled `homing-pigeon` Executa,
plus a `system_prompt_addendum`. There is no bundle, no view,
nothing for a window manager to mount. Clicking the icon
therefore has no visible effect. This is not a breakage and not
a rejected build. It is the documented behaviour of a chat side
app, the same shape as the App Manifest page's own minimal
example.

## 4. How the app wakes today: the mention

The owner typed `test`, `test2`, `test3` into the "Ask Anna
anything..." box with no mention. Anna's own agent answered,
offering to record the words, use them as inputs, save them as
a memory or note, or ignore them. The App Manifest page
explains every part of that behaviour:

- Activation is by mention, per turn. Tool documentation is
  injected into the system prompt whenever the app is mentioned,
  and the addendum is appended to the assistant's system prompt
  when the user mentions the app. No mention, no injection: the
  turn belongs to Anna's general agent with its default kit,
  which is exactly the agent that answered.
- There is no keyword or intent routing to installed apps. No
  document describes any mechanism by which a plain typed
  message is routed to an app that was not mentioned. Typing
  "Homing Pigeon check the clock" as plain text would still
  reach only Anna's agent. The words would be conversation, not
  an invocation.
- The one partial exception is Skills: background skill cards
  trigger when intent matches. A Skill Executa is a recipe the
  agent consults and then executes with its own built in tools.
  It is prompt as code inside Anna's agent, not a pipe to our
  runner, and it carries none of the protocol's trust path. It
  is not a substitute for the mention and is not the routing
  mechanism for this app.

What makes a typed message invoke our app, concretely: the
user types `#homing-pigeon` in the message. For that turn the
platform injects our Executa's tool documentation and our
addendum into the system prompt, and the agent can call the
Executa's tools. That is the whole of the current activation
story. The window in section 12 gives the second route: a real
bundle window with its own text box and buttons, where no
mention is needed because the user is already inside the app.

## 5. Why Anna's own script running is not our runner

In the typing test, Anna's agent offered to run a script. That
offer comes from the host kit: the Platform Tools reference
lists `exec_run` and `exec_run_commands`, described as running
a shell command on the user's agent machine, risk group
destructive. In general chat, Anna's agent runs with the
inherit kit: every host kit tool plus every installed Executa.

That is not our runner and not our protocol, in four specific
ways:

1. No signature gate. The command is authorized by the chat
   session itself. There is no signed job, no verification
   order, no audience or freshness check. The dispatcher and
   the executor are the same party, so there is nothing to
   verify against.
2. No mailbox, no queue, no persistence. The command runs in
   the live session or not at all. Nothing is stored anywhere
   for a machine that is offline, asleep, or simply a different
   machine from the agent client.
3. No confinement story of ours, and no Oracle. Output returns
   raw to Anna's model. There is no attested ceiling: whatever
   the command prints, the model sees in full.
4. Wrong machine by default. The work lands on the machine the
   Anna Agent client happens to run on, not the computer the
   user installed their runner on, unless the two happen to
   coincide and are deliberately pinned.

## 6. Design lineage: the ranked shapes and the choice

This design did not start from a blank page. The preparation
work of 2026-11-20 produced a protocol fit study that ranked
four shapes, most honest first:

- Shape 5.1, the recommended one: the Anna app as front end,
  the hosted service as the bridge. The app bundles one Executa
  with three tools (dispatch a job, check on jobs, ask the
  Oracle). The Executa calls the hosted API with the user's
  per user credential, injected per invoke and never shown to
  the model. The hosted side holds the mailbox and the shared
  secret, composes and signs, collects and verifies results,
  applies the attested ceiling, and answers. The runner is the
  shipping product, unchanged. Every security property of the
  protocol remains in code we control. If Anna vanished
  tomorrow, the protocol would lose a storefront, not a limb.
- Shape 5.2: the self contained Executa with no hosted bridge.
  It holds the shared secret itself as a plugin credential,
  signs locally, and works through one mailbox shape. Honest
  and small, but secret custody moves into Anna's credential
  store, a third party vault. A good personal edition; a weaker
  foundation for customers.
- Shape 5.3: driving a locally installed runner through agent
  tools, using the protocol's watched folder binding. Ranked
  third: it needs Anna's local agent on the runner machine, its
  sessions cap at 24 hours, and signing still needs a local
  helper of ours, at which point the shape is 5.2 wearing a
  second hat. Section 14 returns to it.
- Shape 5.4: the protocol restated inside Anna with no
  separate runner. Every word of the protocol present and none
  of its substance. Not recommended, and never to be sold under
  the Homing Pigeon name.

A second preparation note weighed the two publish paths (a hand
corrected manifest in the console against the command line push
flow from a local project) and recommended the push flow, which
is the flow 0.1.0 shipped by and the flow any follow on version
uses.

The choice this document records: build shape 5.1, with one
substitution the research of 2026-11-25 established. Where the
fit study sketched a hosted HTTPS API still to be designed, the
project already ships the middle of the pipe: the hosted queue
transport. The queue Worker stands where the sketch put the
API, because the queue already exists, is tested, and was
proven live on 2026-10-27. Email, the protocol's default
binding, is demoted for this app: it stays the fallback
transport and can run beside the queue with the protocol
noticing nothing, but it is not in the Anna path at all. The
owner's direction is that email cannot be the Anna app's
default, and in this design it is not.


## 7. The pipe: shape of the whole thing

```
Anna chat (mention)  ──┐
                       ├──►  our Executa  ──HTTPS──►  hosted queue Worker
Anna window (bundle)  ──┘    (Anna side)                 (the bridge)
                                                             │ lease
                                                             ▼
                                         runner on the owner's machine
                                         (queues transport, unchanged
                                          protocol: verify, confine,
                                          execute once, sign result)
                                                             │ result
                                                             ▼
                             verified, view filtered result ◄── Worker
                                         │
             Executa returns the attested view only ──► Anna shows it
```

Every trust property stays where the protocol puts it. Signing
and verification happen in code we control. The queue Worker
checks the signature at the edge under the tenant's shared
secret, and the runner checks the signature again after
leasing; the transports document calls this the queue's two
gates. The shared secret never enters Anna: not the prompt
addendum, which the model can see; not bundle readable storage;
not a tool argument. Anna's side holds only a per user Canoe
credential, the queue's bearer credential for the sending side,
injected per invoke through the Executa credential channel the
model never sees. The runner's connection stays outbound only,
so the runner machine needs no inbound door. That property is
what made email attractive as a transport, and the queue keeps
it.

## 8. What already exists and ships

The middle of the pipe is built product, not plan:

- `runner/cloud/queues-worker/` is a Cloudflare Worker plus one
  Durable Object per tenant. Routes live under `/t/<tenant>/`
  and every call is bearer authorized. The sending side posts a
  job and gets 202 with the job id; duplicate, quota and bad
  signature answers are all specified. The runner leases jobs,
  renews leases, acks, and posts results. The sending side
  reads results back in pages and acks them. A dead letter list
  supports drop and requeue. Leases last 5 minutes by default
  and are renewed by the runner each pass; after 5 attempts a
  job dead letters. Tenant quotas, jobs per hour and bytes per
  day, are enforced at the edge. Its unit tests run under node.
- `runner/transport_extensions/queues/` is the runner side:
  it leases jobs, drops them in the channel inbox, posts
  results back, and acks only once the result is posted.
- `runner/cloud/send_job.py` already speaks this pipe from the
  sending side. Its queue form composes, signs and encrypts a
  job and posts it; encryption is AES-256-GCM under a key
  derived from the shared secret, and it is the default. Its
  results form reads results back, verifies each one, and acks
  only after verification.
- A live proof already stands. A one tenant deployment ran on
  2026-10-27: a stranger got 401 on the configured tenant and
  404 on any other, and a signed ping came back with exit 0 and
  an encrypted result. The report stands in
  `docs/steady/reports/queues-2026-10-27.md`.
- The hosted account layer's first slice exists as
  `runner/cloud/signup.py`: the address rule, the forwarding
  rule, the owner's approval gate and the signup page with its
  one box, with tests. Per the Canoe design notes, no host
  serves the page yet and the slice provisions no account.

What was missing, and is the actual build list: a deployed
staging Worker with a tenant for this test; the Anna side
dispatch Executa; a hosted signing step, because the sending
tool signs on its own machine with the secret in hand and the
secret cannot sit in an Anna plugin; result view filtering on
the return path; and the app version that wires it in, with
the window as its second half. Sections 9 to 12 take each in
turn.

## 9. The bridge

The bridge is the hosted signing endpoint of the build list,
and the concrete form of the Canoe component the fit study
described. It is one small hosted endpoint in front of the
Worker's job posting route. The Worker and the runner need no
changes at all.

Contract, as built in the staging form:

- `POST /dispatch` takes a plain intent, `{kind, script?,
  timeout_sec?}` where kind is `ping`, `clock` or `exec`, and
  returns `{job_id, state}`.
- `GET /jobs` lists the caller's jobs with their states and,
  where a result stands verified, their views.
- `GET /jobs/<id>` returns one job the same way.
- `POST /oracle` takes a job id and a declared query and
  returns the protocol's signed attestation for that job,
  filtered to the view.
- `GET /health` answers `{ok: true}`.

Trust shape, point by point:

- Callers authenticate with the per user Canoe credential as a
  bearer token. The tenant is resolved from the credential's
  SHA-256 hash, never from a client supplied field. A request
  with no credential is refused with 401 before anything else
  happens.
- The tenant's shared secret lives only on the bridge, server
  side. The bridge composes the canonical signed job from the
  plain intent and posts it to the Worker with the tenant's
  sending token, producing an envelope indistinguishable from
  a post made by the sending tool itself.
- Composition and signing reuse the repository's own sending
  code as a library, imported and called, never shelled out
  to. One code path signs, whether the caller is a person at a
  command line or the bridge answering Anna.
- On the return path the bridge reads results from the Worker,
  verifies each signature and decrypts with the same sending
  code, applies the result policy's view, caches the view, and
  acks the queue copy only after verification. The full
  verified payload is held in the bridge's own state, in a
  file with owner only permissions, solely so declared Oracle
  queries can be answered. It is never returned by the job
  routes. Only the view crosses back toward Anna.
- Views are chosen by job kind at composition time. Ping and
  clock jobs are composed with the full view: their whole
  output is a pong, or a clock reading the owner asked to see
  verbatim, and there is nothing else in them to protect. Exec
  jobs default to the attested view: exit code, success,
  duration, and the SHA-384 output digest that binds the view
  to the full output standing on the runner's disk, per
  PROTOCOL.md section 9.

## 10. The dispatch Executa

The new Anna side piece is a sibling Executa whose tools speak
HTTPS to the bridge exactly as the sending tool does. It
starts as a copy of the existing plugin, the same Python
JSON-RPC over stdio skeleton, with the subprocess tools
replaced by HTTPS calls. Three tools:

- `dispatch_job` takes a job kind, `ping`, `clock`, or `exec`
  with a script the user supplied, plus an optional timeout.
  It makes one HTTPS POST to the bridge endpoint with the
  injected Canoe credential and returns `{job_id, state:
  "queued"}` and nothing else. No result is promised
  synchronously, ever.
- `check_jobs` takes an optional job id. It reads the bridge's
  status and result routes, which read the Worker's results,
  verify signatures server side, apply the attested view, and
  return `{job_id, state, view}` per job. This is a deliberate
  user asked check, because nothing in Anna runs unattended;
  see section 16.
- `ask_oracle` forwards declared queries only, the same way.
  The bridge answers with the protocol's signed attestations,
  filtered to the view. Dispatch plus check is the proof;
  the Oracle tool can ship in the second cut.

Two rules bind the plugin's shape:

- One declared credential: the user's Canoe key, marked
  sensitive, injected per invoke in the credential context,
  never visible to the model. The plugin holds no shared
  secret, ever.
- Verbatim results ride the display block. `check_jobs`
  returns the clock reading and the verification verdict
  inside a `_display` block: text declared under the reserved
  `_display` key of a tool result is rendered by the Anna chat
  interface byte for byte, completely decoupled from model
  behaviour, while the model sees only a short preview and an
  instruction not to restate it. For a result whose entire
  value is the runner's own signed words, unparaphrased, this
  is the honest channel, and it costs a few lines in the
  plugin.

The app change that wires it in is a follow on version, 0.2.0,
of the existing app. The simplest publish is one plugin with
six tools: the existing three, which serve the same machine
case, plus the three dispatch tools. The addendum is rewritten
to teach the rhythm: jobs are asynchronous; dispatch returns a
job id; a result exists only when `check_jobs` returns one;
never invent a result, a status, or a clock reading. The
publish route is the documented one already used: validate,
push, cut, then submit for review on the owner's word each
time.

## 11. Route A end to end: the clock sentence

The smallest change that makes the owner's sentence true, step
by step:

1. The owner types `#homing-pigeon check the clock on my
   machine`.
2. The mention injects the tools. The agent calls
   `dispatch_job` with kind `clock`.
3. The bridge composes the canonical clock job, the script
   `date; date +%s` with no interpreter field, per the sending
   document's first live check. It signs the job and posts it
   to the Worker.
4. The runner leases the job on its next pass, verifies the
   signature, runs it under its confinement, and posts the
   signed result.
5. When the owner asks whether it came back, or in the same
   turn after a short wait as a second tool call, the agent
   calls `check_jobs`. That is a deliberate check, not a claim
   of push delivery.
6. The runner's date and epoch render verbatim in a display
   block, next to the bridge's verification verdict.
7. The owner compares the epoch against his own clock.
   Agreement within a second or two, plus the runner's poll
   interval, is the healthy signature the sending document
   specifies.

## 12. The window: Route B

For the experience of clicking the icon and having a big app
open, the app needs the `ui` section the current version
lacks:

- The manifest gains a bundle entry, `format: "static-spa"`, entry
  `index.html`, with the bridge origin declared in
  `external_origins`, and a views entry: one default view, for
  example `main`, titled Homing Pigeon. With views declared,
  the model's window tools exist and the dashboard can summon
  the window.
- The bundle is a static single page app. Today's bundle page
  is a static text page; it is replaced by a working one: a
  text box, a Check the clock button, a dispatch form and a
  job list, laid out on the model in section 13.
- The window drives the dispatch Executa directly through the
  Host API. The asynchronous invoke call returns a job id
  immediately; progress arrives as job events in the window
  and authoritative state through the job read call. The
  synchronous invoke channel caps at 90 seconds, which is why
  anything that waits on a runner belongs on the async
  channel, whose deadlines run up to 24 hours. In this design
  the Executa calls themselves are quick HTTPS round trips to
  the bridge; the async channel matters for long poll cycle
  style calls and for honest waiting.
- Two ways exist for the window to reach the bridge, both
  documented. Through the Executa, as above: the credential
  stays in the plugin's injected context and the bundle holds
  no key. Or the bundle fetches the bridge directly, because
  declared external origins are added automatically to the
  bundle's content security policy connect sources. The first
  way is the design: the bundle is the least trusted tier and
  should hold no credential at all. The second way remains
  useful for a read only status fetch if the bridge ever
  offers a public per job status address. Whether the bridge
  also needs cross origin headers for the app frame origin is
  still undocumented, which is one more reason to keep the
  bundle behind the Executa.
- The platform storage API, in the app's own scope with no
  declaration needed, is the right home for the window's small
  durable state: the user's linked tenant name and outstanding
  job ids, so the window reopens showing the same jobs. That
  store is a convenience store for handles, never for secrets
  or results.

Route B is a second cut, not the proof. Route A proves the
pipe; Route B dresses it. The owner's order of 2026-11-25
pulled the window into the same build, so the two now proceed
together, with the staging proof of the pipe still first in
the test order.

## 13. The window design model: the Image app

The owner photographed his Anna dashboard with the Image app
open and asked whether that surface could be the design model
for ours, and whether an interface of that shape can be used
to test the app once an interface exists. Both answers are
yes, and this section records the model so the window is built
to it.

What the photo shows, from the top, in order:

- The Anna dashboard in a browser, the Image app open full
  width under its title bar, with a Settings control at the
  top right.
- A left control panel. At its top, two tabs: Create and Edit.
  Under them a model picker, a dropdown reading "GPT Image 2
  (fal)" with an "Anna default" badge. Under that, a prompt
  box with the placeholder "Describe the image you want..." and
  a character counter. Under that, small Enhance and Describe
  helper actions. Under that, a reference images area inviting
  1 to 8 reference images "to keep a character, style or
  composition consistent", with an add tile.
- A right results pane, titled Library, with two filter
  dropdowns set to All and a search box reading "Search
  prompts...". The pane is empty, with a centred line of text:
  "No images yet. Describe one, pick a model, Image will paint
  it."
- Along the bottom, Anna's own dock of app icons: a grid
  launcher, music, a monitor, notes, video, our own H tile,
  and a people icon. The dock is Anna's chrome, not the app's,
  and our window needs nothing there.
- The whole surface is one dark theme, panels divided by soft
  borders, the working area wide and quiet.

Our window follows that model panel for panel:

- Left panel, control. Where the Image app puts its model
  picker, ours puts the job kind picker: Clock, Ping, Exec.
  Where it puts the prompt box, ours puts the intent box: the
  script for an exec job, or plain words for the named kinds,
  with the same generous box shape. The helper row carries the
  two honest helpers this app has: Check status, which runs
  `check_jobs`, and Ask the Oracle, which runs `ask_oracle`
  against the selected job. The reference images area becomes
  the runner card: the linked tenant, the runner's last known
  status from `runner_status` where a local runner exists, and
  whether a Canoe credential is present. The credential's value
  is never shown, only its presence.
- Right pane, the results library. Where the Image app lists
  pictures, ours lists jobs: each entry shows the job id, the
  kind, the state, and, when a verified result stands, the
  view: the clock reading verbatim for a clock job, the
  attested verdict for an exec job, with its exit code and
  output digest. The filter dropdowns filter by state and by
  kind; the search box searches job ids and kinds. The empty
  state line, in the same spirit as the model's: "No jobs yet.
  Pick a kind, write the intent, and the runner will answer
  with a signed result."
- Settings, top right, holds the link state: the tenant name,
  the bridge origin, and the credential presence indicator,
  plus the one fact the user must be able to read at a glance,
  that results shown here are verified before they are shown.
- Create and Edit tabs become Run and Review. Run is the
  dispatch form. Review is the library filtered to finished
  jobs, with the Oracle query box under the selected entry.

On testing: a window of this shape is a surface that can be
exercised the way a user exercises it. Under the documented
bundle test harness the window's tools are mocked, so the
layout, the form behaviour, the empty and filled library
states and the job event handling can all be tested before
anything is submitted. Once the window drives the real
Executa, the same surface becomes the end to end test the
owner asked for: press Check the clock in the window, watch
the job cross the pipe, and read the verbatim epoch in the
library entry. Section 18 folds that into the test plan.

## 14. Route C: Anna's agent carrying our protocol

The owner's original design question of 2026-11-20 was whether
Anna's own agent could carry the protocol. It maps to the host
kit: an app declares agent tools and opens sessions whose file
and exec tools execute, over Anna's internal RPC, on the
user's Anna Agent client machine. What the documentation
actually allows, checked fresh in the 2026-11-25 research:

- Declaration is consent, and the intersection is hard. The
  effective tool set is the requested set intersected with what
  the platform and the declaration allow. Undeclared host kit
  tools are silently dropped. There is no per tool user toggle.
- A fixed session pins the machine; the automatic mode does
  not. A fixed session binds to one of the user's registered
  Anna Agent clients, and the pinned client always overrides
  anything the model supplies, so an app can never aim side
  effects at an arbitrary machine. The automatic mode targets
  the user's default agent, which may be Anna's cloud machine,
  not the owner's.
- Session lifetimes are short: an idle time to live of 30
  minutes sliding, a hard cap of 24 hours, resumable by id.
  The cloud agent suspends after about 2 hours idle. Nothing
  here polls a mailbox while nobody is looking.
- The exec tool's semantics are a shell, not a protocol: one
  command or a sequence, real side effects, raw output back to
  the model. No signing, no verification, no confinement
  contract, no result policy.

The honest use of this route is the one the fit study ranked
as shape 5.3: a control panel for a runner installed on the
same machine as the user's local Anna Agent. A file write
drops an already signed job into the runner's watched folder
binding; a file read takes the signed result back; an exec
call health checks the runner. Even there, signing still needs
our code holding the secret locally, so the route collapses
into Route A plus a local shortcut. As a replacement for the
runner, in the strong sense of their runner carrying our
protocol, the documentation does not offer it: Anna's agent is
a session scoped shell and file hand, not a host for a long
lived, signature gated, confined executor. Recommendation: do
not build Route C as the pipe. Keep it in the back pocket for
a same machine edition.

## 15. Surfaces considered as the pipe, and why not

- Anna's internal messaging. Executas are reached over the
  platform's internal wiring and host kit tools ride it too,
  but that wiring runs between Anna's host and the user's Anna
  Agent. No document offers a developer an endpoint,
  credentials, or subject space of their own. Our protocol's
  own broker binding is a different thing entirely: a broker
  we control. Anna's wiring cannot carry our jobs; it can only
  carry Anna's calls to our Executa, which is exactly Route A.
- Plugin reverse calls. A plugin can borrow Anna's model,
  search, fetch, storage and upload through reverse calls.
  None of them moves a byte to a machine we choose. The
  plugin's own outbound HTTPS is the door, and Route A walks
  through it.
- Platform storage as a queue. The storage API is durable per
  user key value and object storage, and a plugin can read and
  write its scopes. In theory jobs could be left there for
  something to fetch, but nothing on our side can poll it
  without holding Anna credentials and becoming an Anna
  client, at which point it is a strictly worse queue than the
  Worker we already ship: no leases, no attempts, no dead
  letters, no edge signature gate. Its role in this design is
  the small one in section 12: handles and job ids for the
  window.
- Email as the pipe for this app. The email binding stays the
  protocol default and the fallback transport, and the queue
  and email can run side by side with the protocol noticing
  nothing. The owner's direction is that email cannot be the
  Anna app's default. In this design it is not in the Anna
  path at all.

## 16. Honesty limits

- Nothing in Anna runs unattended. No daemon, no scheduler, no
  inbound webhook, no event delivery to apps or plugins.
  Dispatch happens when a user asks. Results are fetched when
  a user asks, or when a still open window polls the job read
  call, which is the window asking, repeatedly, while it
  lives. Any copy that says Anna will notify the user when a
  job finishes is false, and the addendum must say the
  opposite.
- The attested ceiling holds only because our code is on the
  return path. Anything an Executa returns is visible to
  Anna's model; the display block mechanism hides text from
  paraphrase, not from the model contract, since the model
  still sees a preview. The ceiling holds because the bridge
  verifies and filters before returning, so the full output
  never crosses. Route C breaks this by construction, which is
  one more reason it is not the pipe.
- The runner is unchanged, and that is the point. It stays a
  separate install on the owner's machine, polling outbound
  only. Anna provides distribution, the chat and window
  surfaces, and the user's identity context. If Anna vanished
  tomorrow, the protocol would lose a storefront, not a limb.

## 17. Build state at the time of writing

Written 2026-11-25, late afternoon Pacific, from the build
tree itself, and corrected the same evening, when the build
lane finished. The first writing of this section said the
dispatch Executa folder and the bundle folder were still
empty and that no 0.2.0 manifest existed. That was true when
written and stopped being true within the hour, and this
section now states the finished build. The build lives
outside this repository, in the Anna preparation folder's
pipe-build tree, until its pieces are ready to land as
product. What stands:

- The bridge stands: one standard library Python file
  implementing the contract and trust shape of section 9,
  importing the repository's own sending code as a library.
  Its unit suite stands at 7 tests, all passing.
- The 0.2.0 app project stands: a schema 4 manifest with a
  `ui` section, its bundle entry naming the window, and three
  declared views, `main` as the default, `dispatch` and
  `results`; a rewritten system prompt addendum teaching the
  asynchronous rhythm of section 10; and the app listing
  carried over unchanged.
- The dispatch Executa stands, at version 0.2.0, as one
  plugin with 6 tools: the original 3 local tools,
  `runner_status`, `run_poll_cycle` and `runner_posture`,
  plus the 3 dispatch tools of section 10, `dispatch_job`,
  `check_jobs` and `ask_oracle`. Its own manifest is
  regenerated from its describe output. Its suite stands at
  28 tests, all passing, including the checks that the plugin
  holds no signing code and no shared secret, and that the
  Canoe credential never appears in any return value.
- The window bundle stands: one static single page app in
  the project tree, built to the model of section 13, driving
  the Executa through the Host API's asynchronous invoke and
  job read calls only. It holds no credential and never
  fetches the bridge. 10 static tests pin its layout and its
  trust contract, all passing.
- The staging harness stands: a local server that runs the
  shipped queue Worker code on loopback, a tenant minting
  script, the staging tenant configuration, and the proof
  script that drives the whole staging pass and writes its
  results to a machine readable file.
- The staging runner is a test double, and its limits are
  stated in its own header: it speaks the queues transport the
  way the real runner's extension does, opens each job with
  the repository's own verify and decrypt code, executes
  without confinement, and posts a signed, encrypted result
  composed with the same code. It exists so the local staging
  proof can exercise the whole pipe before a real runner is
  pointed at staging. It is never to run outside staging: no
  confinement, no Oracle, no signature gate beyond the sending
  code's verify. The real runner is the product; the double
  has the protocol's wire shape only.
- The staging proof, at its latest run, passes all 15 of its
  checks. In groups:
  - Gate checks: a stranger with no token gets 401 on the
    tenant; an unknown tenant gets 404; the bridge refuses a
    request with no credential with 401; and a job carrying an
    encrypted finding is refused by the Worker's own gate, the
    check that stands in for the class of malformed envelopes
    the edge must never lease.
  - The 2026-10-27 ping proof, repeated: a ping composed by the
    sending tool queues, the staging runner leases, executes
    and posts, and the sending tool reads the result back and
    verifies it.
  - Dispatch checks: a clock job and an exec job dispatched
    through the bridge with the Canoe credential both return
    202 with queued state and job ids.
  - Completion checks: both jobs run to done on the staging
    runner.
  - View checks: the clock job's view is full and verbatim,
    carrying the runner side date line and the epoch seconds
    exactly as the job printed them; the exec job's view is
    attested, verified true, with exit code 0, and the marker
    string planted in the exec job's output does not appear in
    it; the attested view's output digest binds the full
    output, checked by recomputing the digest over the output
    the runner actually produced.
  - Oracle checks: a signed attestation answering the declared
    exit_zero query verifies under the tenant secret with the
    answer true; and a grep query under the attested view is
    refused, in words: grep queries are refused under the
    attested view.

What does not stand yet, stated just as plainly:

- The staging proof ran on loopback, on one machine, with the
  test double standing in for the runner. Pointing a real
  runner configuration at staging, with the queues transport
  only, is steps 2 and 3 of the test plan below and remains
  ahead. The double proves the wire and the bridge; it does
  not prove the product's confinement or its Oracle.
- One finding against shipped code stands open. The shipped
  queue Worker's job posting gate refuses the protocol's
  default encrypted envelope: the gate compares the body's
  `job_id` against the subject id, and an encrypted envelope
  carries no `job_id` member to read, so the answer is a 400
  naming a job_id mismatch between subject and body. The
  staging proof pins that refusal as a passing finding check,
  the gate check in the proof groups above. The recommended
  fix stands as a recommendation, not a landing: give the job
  posting gate the results route's treatment, where an absent
  payload id is not a claim and the subject id binds an
  encrypted envelope, while a present and different `job_id`
  stays a refusal. Until that fix lands in this repository,
  the bridge composes signed cleartext jobs, and a runner
  serving this pipe must be started allowing cleartext.
  Results remain encrypted either way. This is a staging
  posture, not the intended production one.
- Nothing has been pushed to Anna, and nothing has been
  submitted. The 0.2.0 project stands built and tested
  locally only. Its manifest was checked against the
  documented schema by the bundle tests; the Anna command
  line validation has not been run, because that tool was not
  installed in the build lane. The staging Worker has not
  been deployed for real, and the bridge is not yet hosted at
  the origin the manifest declares. The owner's console steps
  in section 18 are untouched.

The standing verification requirement, set by the owner on
2026-11-25, governs how all of this gets reported: once any
pipe piece is built, Muse runs the end to end proof herself,
the clock job through the new pipe against a real runner, and
verifies the signed result returns and matches, inspecting the
raw Executa returns to prove nothing beyond the attested view
crosses to Anna, before anything is reported as working. A
piece that has not passed that proof is reported as built, not
as working. The staging proof above is the bridge half of that
verification, and the plugin and the bundle now stand built
and unit tested on the Anna side of it. The full verification,
against a real runner and then once against production Anna
with the owner watching, remains ahead, and this document
will be updated when it stands.

## 18. Test plan

### 18.1 The smallest proof run

Preconditions that already stand: the Worker code, the runner
queues extension, the sending tool's queue support, a live one
tenant queue proof from 2026-10-27, the existing Executa's 18
tests, and a real runner install on the build machine.

1. Stage the bridge. Deploy the queues Worker to a staging
   deployment and create one tenant for the test: tenant name,
   sending and runner token hashes, the tenant shared secret,
   default quota. Stand up the signing endpoint of section 9
   in front of it, holding the tenant secret server side, with
   one test Canoe credential issued for the owner's account.
   The staging harness of section 17 stands in for this step
   on loopback until the deployed form is wanted.
2. Point a real runner at it. A test runner config on a test
   machine with the queues transport only and the staging
   tenant address set, token in the config. Start it and
   confirm from its log that it leases. Empty queue answers
   are 204s; conclude nothing from a read that did not finish.
3. Pipe smoke test without Anna. From the command line, the
   sending tool's queue ping and results round trip, the
   2026-10-27 proof repeated against the staging tenant, so
   any later failure is Anna side by elimination. The staging
   proof of section 17 already covers this step against the
   test double.
4. Build the dispatch tools into the Executa. Add the three
   tools of section 10 to the project plugin, credential
   declared, unit tests beside the existing 18: dispatch posts
   the right intent shape to a stub bridge; check returns only
   the view the stub bridge returns; no secret string appears
   in any argument, log, or return, checked by a source and
   fixture grep in the same style as the existing no shell
   source check.
5. Local Anna harness. Run the development harness against the
   project with the new tools; drive the clock sentence in the
   harness; watch the job cross: bridge log, Worker queue
   depth, runner log showing leased, verified, executed, and
   the result posted.
6. Muse's verification, the standing requirement of section
   17. Muse herself, not the owner, confirms all of: the
   returned epoch matches her own clock within a second or
   two plus the poll interval; the result's signature verified
   on the bridge, the verdict the bridge returns and not the
   model's say so; the raw Executa return, captured from the
   harness, contains the attested view and the display block
   and nothing else, no full output beyond the view, no
   secret, no token, no config content; and the same
   inspection repeated on the chat surface path as on the
   window path, once the window stands, driving the window's
   own Check the clock control for that pass. Only then is the
   pipe working.
7. Then, and only then, the owner's console steps of section
   18.3 put the new version in front of the real Anna, and
   step 6 is repeated once against production Anna with the
   owner watching, using his own runner.

### 18.2 Failure cases to run in the same pass

- A job with a corrupted signature posted straight at the
  Worker: refused at the edge, never leased.
- Checking jobs before the runner has run: an honest queued,
  no result yet, never an invented time.
- Runner stopped: dispatch still queues; check reports queued
  with its age; the dead letter path after 5 lease attempts is
  exercised by letting one job's leases lapse.
- A result whose view is attested: the full output stays on
  the runner's disk; the Anna side return is inspected for
  leakage with a script whose output contains a marker string
  that must not cross. The staging proof already runs this
  case against the bridge; it runs again against the real
  runner in step 6.

### 18.3 What only the owner can do

- Settle the 0.1.0 status with one look: the console's My Apps
  page, or the status command under his account session.
- Approve any new submission: push and cut are preparatory;
  submit for review and any later release are his explicit
  word each time, as they were for 0.1.0.
- Paste his Canoe credential once into the Executa's
  credential settings in Anna. By design this is a user held
  secret the model never sees, so it cannot be entered for
  him.
- Decide the same machine question if Route C is ever wanted:
  which machine runs his local Anna Agent. Not needed for
  Route A or B.

### 18.4 What Muse can build locally, without him

In order, each independently testable: the dispatch Executa
skeleton with stub bridge tests and display blocks; the bridge
implementation against the staging Worker, substantially
standing per section 17; the endpoint contract written down
as the contract both sides code against; the bundle window of
sections 12 and 13, developed and tested under the
development harness and the bundle test harness with mocked
tools; the 0.2.0 manifest and addendum, validated locally with
the same schema package the server uses; and the staging
tenant, the test runner config, and the whole verification
pass of step 6. None of it needs a console login, a
submission, or the owner's hand. His hand enters at section
18.3, after the proof stands locally.

## 19. The sealed verdict: the demo beyond the clock

A test suite run whose output never leaves the machine. From
Anna chat: run the suite on my machine and tell me only
whether it passed. The dispatch Executa sends an exec job, the
project's own test command on the runner's checkout, with the
result policy at its default, attested. The runner runs the
full suite under its confinement: minutes of output, failures,
file paths, all of it staying on the runner's disk. The bridge
returns exactly the attested view: a signed attestation that
the suite passed or failed, the exit code, the duration, and
the output digest that binds the view to the output it
summarizes. Anna renders the verdict verbatim in a display
block. Then the follow up that makes it a demo rather than a
trick: how many tests ran, a declared Oracle query, answered
as a signed attestation counted from the real output, again
without the output crossing.

Why this is the right neat thing: it is the one capability no
other app on the dashboard can honestly offer. The media apps
generate on Anna's machines; the general agent's shell runs
and reads everything. Only this pipe can say: the work ran on
my computer, here is a signed proof of the outcome, and the
details never left my desk. Every word of that sentence is
checkable in the proof run of section 18, including the
leakage inspection with the marker string. It also demos the
whole pipe in one gesture: mention, dispatch, queue, lease,
confinement, signed result, attested view, verbatim display.

## 20. Open questions carried forward

From the protocol fit study, the ones this design touches,
with their status after the 2026-11-25 pass:

- Cross origin headers for bundle fetch: unresolved in the
  documentation. Route B avoids depending on it by driving
  the Executa instead of fetching from the bundle.
- Async jobs against cloud agent sleep: still open, and it
  matters only if the Executa runs on the user's cloud agent.
  The dispatch calls are short HTTPS round trips, so the
  exposure is small, but a long poll cycle call on a sleeping
  cloud agent remains a known soft spot.
- Hub review policy for a user pasted API key credential:
  still open. The dispatch Executa takes exactly such a
  credential. Worth one forum question before 0.2.0 is cut.
- Google scope set and non HTTPS egress: no longer on the
  critical path. The recommended pipe needs neither a named
  mail provider nor raw network egress from the plugin. They matter only to the
  self contained shape 5.2, which this design does not build.
- New from the 2026-11-25 pass: whether a developer's own
  dashboard install of a pending review app is expected
  behaviour or a console quirk. It affects nothing in the
  design. It is noted only because the owner's photo shows the
  icon present while the last recorded status is pending
  review.

## 21. Sources

Anna developer documentation, read fresh on 2026-11-25:
Developer Hub landing page; App Manifest; App UI Manifest;
App UI Overview; App Side LLM and Agent API; Platform Tools
reference; Host API reference; Display Blocks. Plus the
2026-11-20 documentation pass recorded in the preparation
folder: architecture and lifecycle, concepts, Executa
lifecycle, credentials, authorization, storage, app bundling,
publishing, versioning, and the official forum.

Local preparation folder: the protocol fit study, the Executa
build record, the path recommendation, the review packet, the
open questions list, the listing and image records, the two
manifests, and the project tree with the 0.1.0 Executa. The
research report of 2026-11-25, "The Anna pipe: why the Homing
Pigeon icon does nothing, and how a typed message reaches a
runner", is the immediate source of sections 2 to 11 and 14 to
20; this document restates it in repository form, adds the
window design model of section 13, and adds the build state of
section 17.

Project sources in this tree: PROTOCOL.md sections 2, 3 and
9; `docs/steady/sending.md`, the first live check;
`docs/steady/design/cs_canoe.md`;
`docs/infrastructure-documents/extend/transports.md`, the
hosted pipe section; `runner/cloud/queues-worker/`;
`runner/cloud/send_job.py`; `runner/cloud/signup.py`;
`docs/steady/reports/queues-2026-10-27.md`.
