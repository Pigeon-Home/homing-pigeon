# Trim list for the -02 sources

Read against `draft-slutsky-homing-pigeon-02.md` and
`draft-slutsky-homing-pigeon-v2-02.md` as they stand in the
tree. No cut was made. A name that is the protocol's own
(the draft title, the PSK identity `homing-pigeon`, the
info string `homing-pigeon job-encryption v1`) is not on
this list. `PROTOCOL.md` is not named in either source.
No path into the repository is named. No GitHub URL is
named.

## Version 1

- **Introduction.** "The reference implementation speaks
  version 1, and it implements the bindings this document
  specifies." That sentence is about one program, not about
  a conforming implementation.
- **Transport binding.** "the reference implementation
  enables it by default" — the email binding being the one
  a particular program turns on. The rest of the paragraph
  is a conformance rule.
- **NATS subjects.** `homing-pigeon.jobs` and
  `homing-pigeon.results.<job_id>` are introduced as "the
  reference default." The shape (a jobs subject, a per-job
  results subject) is the binding. The particular strings
  are that program's choice.
- **Key selection.** "The reference software does so" — a
  fingerprint used as a key name. The fingerprint formula
  itself is specified. The sentence that one program uses
  it is not.
- **IANA considerations.** UDP 20220, "a LOCAL default of
  the reference implementation, not a registered
  assignment." The port number is that program's default.
- **Platform disclosure.** "This is the reference default"
  on the `family` tier. `python_version` names the runtime
  of that program; a protocol-general field would not have
  to be a Python version. "The reference implementation
  includes the platform disclosure in the handshake in
  exactly this form" describes one program's behavior. The
  extension rules above that sentence are the specification.
- **DTLS security.** "the reference sender applies it by
  default and offers `--cleartext`." The flag is a command
  of one program.

## Version 2

- **Context segments.** The example of a question's context
  names "platform, machine, Python, and the device-tree
  model." Python and the device-tree model are facts of one
  deployment, offered as if they were the segment's subject
  matter.
- **Enablement.** "The reference software reads four keys"
  and the flags `--protocol-v2` and `--answer-only`, and
  the config name `protocol_v2`. Those are one program's
  switches. The rule that version 2 is off until an
  operator turns it on is the specification. The names of
  the switches are not.
