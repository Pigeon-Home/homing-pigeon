# VR.MD — The VR Oracle (v9)

**Status:** not in the runner. Nothing below is implemented. There
is no headset, no seat, and no 3D room. This file stays as the v9
sketch.
**Identity:** v9 is *be* where the Oracle thinks.

## 1. Vision

The flat dashboard (v9, not started) shows the Oracle's thinking on a
screen. The VR Oracle puts the operator inside it. Each job is a room
you walk through. The verdict is the lighting. Attestations hang on
the walls, framed. Budget burn is a meter on your wrist. The senses
are windows — look through one to see the sense window around the
event.

## 2. The Seat

The DRI sits in the seat. Sitting down acks the page — the cooldown
logic accepts posterior presence as acknowledgment. The seat has a
seatbelt. It engages on a hostile verdict and does not release until
all keys are rotated or the box is taken offline, whichever the
operator decides first.

When the DRI pages, the headset vibrates. Suit up, put it on, sit
down: the page deep-links straight into the 3D job room. There is no
loading screen. There is no time for a loading screen.

## 3. Interaction

- Approving a `pending_review` task: point at it. The task id is
  rendered in large letters on the far wall; pointing at each
  character in order types it. This is deliberately slower than
  typing, because approval should be.
- Tap-to-approve (roadmap §3.1) becomes a large lever. Pull for
  Approve, push for Deny. The lever resists slightly on Approve,
  in proportion to the fused risk score.
- Writing Oracle config keys: turn the dials on the config panel.
  The dials for `shared_secret`, `additional_secrets`, and the
  mailbox password are painted over. They do not turn.
- The Oracle never speaks. It is a local model and it knows its
  place. It communicates in lighting.

## 4. Architecture

- Loopback-bound, fail closed. The headset connects over loopback.
  A headset that is not on loopback is not your headset.
- Renderer: stdlib only, no new dependencies. The third dimension
  is implied.
- Parity rule: everything the VR Oracle does must be doable in the
  flat dashboard by standing up and looking away from the screen.
  The config file remains the source of truth; the seat is not.
- Motion sickness policy: fail closed. If the operator feels ill,
  the session ends immediately and the job under review is rejected
  as a safety measure. The Oracle respects this and does not take
  it personally.

## 5. Multiplayer

Arena mode (roadmap §6) becomes a shared space. Competing SIs appear
as ghosts. They cannot touch your levers. The scoreboard is a
trophy shelf.

## 6. Relationship to the other v9

The flat dashboard remains the fallback for operators without a
headset, and will follow when ready. All deep-links resolve in 3D
first; the 2D rendering is a courtesy.
