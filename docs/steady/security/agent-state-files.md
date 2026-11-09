# Agent state files: approval memory is private-shelf material

This document states what an agent's state files are, how they
come to be published by accident, and what this suite ships so
that the accident does not happen here. It is written for two
readers: the operator who is not an expert in source control
and would never notice a file going into a commit, and the
visiting system that keeps state of its own inside a tree and
is asked to treat that state the way this project treats it.

The document stands inside the privacy design
(`privacy-design.md`, same drawer). That design's rule holds
here unchanged: privacy behaviour is declared configuration,
in the family of the config security modes, and a category of
material is handled by being *declared*, *sheltered* out of a
publication's scope, and *warned about* under the warning's own
rules -- names only, a fixed banner, nothing kept, nothing
sent. Personal documents are the framework's first category.
Agent state files are its second: **the agent's papers**, the
counterpart of the operator's papers, and private-shelf
material for the same reason. The spillage doctrine in
`SECURITY.md` names the failure this document exists to
prevent; this document is the category's record.

## 1. The incident that named the category

In November 2026, researchers at Apiiro published a study of a
file most of its owners had never looked at:
`.claude/settings.local.json`, the project-local settings file
of the Claude Code agent. When that agent asks permission to
run a shell command and the user chooses "Yes, and don't ask
again", the approval is saved in that file as an `allow` rule
-- the vendor's own settings documentation says so in those
words. When the approved thing was one exact command, the rule
that persists is the command string itself, word for word.
Commands that touch a database or an API commonly carry the
credential inline -- a connection string, a password flag, a
token -- because the command cannot run without it. The secret
is therefore in the file, in plain text, as a side effect of a
convenience.

The file was meant to stay local, and the product did try to
keep it out of git: the first time it writes the file in a
repository that does not already ignore it, it adds the
pattern to the developer's *global* git excludes file. That
protection failed at scale, for four structural reasons:

1. **It does not travel.** The pattern lives on one machine, in
   the developer's global excludes. It is never added to the
   project's own `.gitignore`, so a clone on another machine, a
   new teammate, or a CI checkout has no protection at all.
2. **Tracked files are immune to ignore rules.** Once the file
   has been committed once, git keeps tracking it; an exclude
   written later never applies.
3. **Timing gaps.** A folder that becomes a repository later,
   or a settings file created by hand before the agent first
   writes it, is unprotected.
4. **The agent itself carried it in.** In 539 of the 1,105
   leaking repositories the researchers traced, a commit
   co-authored by the agent had changed the file -- the tool
   that wrote the secret also carried it across the boundary in
   about half the traced cases.

The measured scale (GitHub data collected 1--3 November 2026):
104,185 public copies of the file in 103,617 repositories;
1,122 of them (1.1%) holding at least one real secret -- 1,379
distinct secrets on default branches. Counting git history,
the shared project settings file, and agent chat transcripts
saved in repositories: 2,539 real secrets across 1,994
repositories and 63 organisations. In half the leaking
repositories the file had been sitting there for at least 217
days. Deleting the file does not undo any of it: older
versions stay in git history, and 211 forks of 74 repositories
carried the same secrets. That is why the response to this
class of accident is **rotate first, clean up second** -- a
credential in a public copy must be treated as public, and
changing it is the only move that reaches history and forks.

Two limits of the study belong in the record. The researchers
did not test any credential, so "real secret" means a key in a
recognisable format or a password beside a public host, not a
confirmed-live credential; one company they notified confirmed
its key had been live. And the standard secret scanners were
partly blind here: of the 1,122 files, 215 were flagged by
neither of the two widely used scanners, usually because the
secret is a password typed inside a command, not a key in a
format a scanner recognises. A guard for this category has to
look at *where a value sits* -- inside a saved command, inside
an approval rule -- not only at what the value looks like.

The vendor's head of the product, answering publicly on
7 November 2026, said the team had not historically done secret
scrubbing and was "looking into what we can do to prevent
this", naming auto-mode detection and basic secret scanning as
approaches to prototype. Reports of the verbatim-storage
mechanism itself had been on the product's public tracker
since August 2025, unanswered, and closed by an automated bot
as inactive in the days before the study ran. No shipped fix
existed when this document was written.

The lesson, in one line: **persistence of approvals is a
secrets-handling decision, not a user-interface decision.** A
convenience feature persisted verbatim user-approved content
into a project-shaped file, and the only thing keeping that
file private was a machine-local exclude that does not travel
with the project.

## 2. The general class, and how a non-expert trips over it

An agent that works inside a tree keeps state. Across tools
the shapes differ; the categories do not:

- **Approval memory.** The record of what the user approved --
  allow rules, saved commands, "don't ask again" grants. This
  is the incident's category, and the most dangerous one,
  because a saved command can carry the secret it needed.
- **Agent configuration.** Project-level and local settings,
  per-tool rule files, key policies. The shared member of this
  pair is often committed *on purpose*, which makes it the
  natural place for a secret to be pasted "just for now".
- **Session transcripts.** The chat log of an agent session,
  saved beside the work. Everything the session saw is in it,
  including anything pasted into the conversation.
- **Deployment configuration and run state.** This suite's own
  members: the deployment `config.json` (shared secret, mailbox
  credentials, per-key material), and the state files a run
  leaves behind -- `seen.json`, `board.json`,
  `oracle-chat.jsonl`, `oracle-briefs.jsonl`, the `outbox/`
  folder, the `work/` folder. Job bodies belong here too: a
  job's script can embed a credential exactly as a shell
  command did in the incident.

All of it is the agent's papers. It records what the operator
runs, what they approved, and whom they talked to, and some of
it carries live credentials. None of it is written for a
reader, and none of it belongs on the public shelf.

The accident that publishes it is almost never a decision. It
is one of a small set of shapes, each one a thing a careful
non-expert does without any reason to suspect it:

1. **The exclude lives on the machine, not in the project.**
   The operator's own setup looks protected -- the file never
   shows as untracked on *their* machine -- so nothing prompts
   a second thought when the tree is cloned elsewhere or a
   teammate commits.
2. **"Add everything" staging.** An editor's stage-all button,
   or `git add .` typed as a reflex, sweeps up every untracked
   file in the tree, state files included. Nobody reviews a
   list of hundreds of names line by line.
3. **The state folder sits inside the tree.** The agent writes
   its `.claude/` folder, or a runner writes its state, into
   the working directory by default. What is inside the fence
   is what gets committed; the operator never chose the
   location.
4. **Configuration copied as an example.** A working config is
   copied to make a template, or a shared settings file is
   committed deliberately with a real value still in it,
   because the file's purpose is to be shared and the value
   looks like part of the furniture.
5. **Transcripts saved beside the work.** Saving the session
   "for the record" into the project folder feels like good
   housekeeping. It is publishing the session.
6. **Deletion mistaken for cleanup.** The file is removed in a
   later commit and the matter feels closed, while every
   earlier version remains in history and in any fork. The
   secret is still public; only the reminder is gone.
7. **The agent commits.** An agent asked to commit the work
   commits the tree it sees, including its own state files --
   the incident's shape 4 above, and the shape this project's
   own contributors are in. A rule that only a human reads does
   not bind the hand that is actually committing.

A protection that depends on the operator noticing the file,
remembering the rule, or being an expert in source control is
not a protection against any of these shapes. The safeguards
have to fire at the boundary, before the commit or push, and
they have to be part of what ships -- travelling with the
project the way the failed exclude did not.

## 3. Other agents keep the same papers

The incident's file belongs to one product; the category does
not. Every agent that asks for approvals, loads project rules,
or keeps a session writes state in the same categories as
section 2 -- an approval memory under its own name, settings
split between a shared file and a local one, transcripts under
its own folder. The names differ; the shelf it belongs on does
not. Vendors' own documentation says as much, in their own
words: local settings files are described as not meant to be
committed, and the remedies vendors publish are the project's
`.gitignore`, not a machine-local list.

Two consequences shape what section 4 ships. First, the
protections are written against *categories and shapes* -- a
settings file under an agent's folder, an allow array in staged
JSON, a secret-shaped value sitting inside a saved command --
not against one vendor's one filename, so a tree worked on by
a different agent, or by next year's agent, is covered by the
same rules. Second, a visiting system reading this document
should expect its own papers to be governed by the deployment
it is visiting: its approval memory and the deployment's state
are private-shelf material there, whatever its home defaults
say, and if the deployment has no rule for them, that absence
is worth saying to the operator out loud.

## 4. What this project ships against the class

Each piece below is in the framework's existing shapes, and
each is stated as it stands; where a piece is landing in the
same pass as this document, the sentence says so, and the
record is corrected when the pass closes.

- **Ignore defaults that travel.** The repository's root
  `.gitignore` -- an existing root file, edited, not added --
  carries the agent-state shapes: `**/.claude/settings.local.json`,
  `**/config.json`, `seen.json`, `board.json`,
  `oracle-chat.jsonl`, `oracle-briefs.jsonl`, `outbox/`,
  `work/`, with a comment recording that the shared
  `.claude/settings.json` may be committed but must never hold
  a secret. The protection now clones with the project, which
  is the property the incident's exclude lacked. A unit test
  (`runner/tests/test_gitignore_state_files.py`) pins the list
  and fails if a pattern is dropped. Landing in the same pass
  as this document.
- **A staged-content guard.** `runner/tools/approvalguard.py`
  (landing in the same pass) is a shelter-shaped tool in the
  line of `runner/tools/nameguard.py`: standard library only,
  its forbidden shapes declared in code, invoked and never
  ambient. It scans what is *staged* -- the content a commit is
  about to carry -- and fails closed on three rule families:
  a staged path matching an agent-config or permission shape;
  permission-grant state in staged JSON (allow arrays, saved
  command strings); and secret-shaped values inside those
  command strings specifically, the class the generic scanners
  missed in the incident. Its report follows the framework's
  split of existence from value: it names the file and the rule
  it tripped, and never prints the secret. Two hook lines
  (pre-commit, pre-push) in this drawer's operator documents
  are the whole wiring; like the name guard, the tool is not
  wired into the project's own push path by default -- wiring
  is a deliberate adoption step, taken by the operator, or by
  their agent at the operator's word.
- **A feature in the modes family.** The guard's behaviour is
  declared the way `privacy-design.md` section 2 requires: a
  named feature, `agent_state_guard`, under `security.modes`
  in `runner/guard/security.py` and stated in the shipped
  example config (landing in the same pass). Its semantics are
  the family's semantics for an operator-invoked behaviour:
  `off` refuses -- the guard does not run; `audit` shows what
  would be stopped and stops nothing; `enforce` lets the guard
  stop the commit or push. It defaults to `enforce` and is
  refused when misspelled. The postures engage it or quiet it
  exactly as their configuration says: under *just run it* the
  run stays carefree, and under *eyes open* and *lockdown* this
  category is treated as a major concern.
- **The standing note to visiting systems.** The Oracle's
  instructions (`docs/steady/oracle/instructions.md`) carry a
  standing note, beside the disclosure-posture and doors
  material (landing in the same pass): handling rules for agent
  permission and configuration files belong in every
  deployment; a visiting system treats its own approval memory
  and the deployment's config and state files as private-shelf
  material, never carried across a publication boundary, and
  says so to its operator when no such rule exists. The
  safeguards questions in `AGENTS.md` gain the matching question
  for the reader who arrives there first: where does your own
  approval memory live, and does it live inside a tree that
  gets published?
- **The category named in the spillage doctrine.**
  `SECURITY.md`'s spillage section names agent permission
  files as private-shelf material (landing in the same pass),
  under the doctrine that already governs the rest of the
  shelf: declare the spill, start containment at once, rotate
  first.

What this does not do, stated plainly. Ignore rules do not
untrack a file that is already tracked; an operator who finds
a state file already in their history has a rotation to do,
not a pattern to add. The guard scans staged content when it
is invoked; it is a boundary check, not a daemon, and an
operator who never wires the hook is relying on the ignore
defaults and their own invocation. And the tree-wide
value-confinement test queued in `privacy-design.md` section 6
is still queued in its general form: the staged guard is its
first concrete form, at the one boundary where publication
actually happens, not the whole of it.

## 5. Questions worth carrying to your operator

The safeguards above are a floor, shaped for this suite's own
state files. Every deployment keeps papers of its own, and the
right handling rules for them are the operator's to design.
These questions are offered the way this project's other
safeguards questions are offered: plainly, with the reasoning
attached, for the operator to answer in their own
documentation.

- Where does your agent's approval memory live -- the exact
  file, on the exact machine -- and does the tree it lives in
  ever get published? If you cannot name the file, the boundary
  cannot be checked.
- Which of your ignore rules live in the project, where they
  travel with every clone, and which live only on your machine?
  A rule that does not travel is a rule for one laptop.
- If your agent committed the whole tree tonight, what would
  stop its own state files at the boundary -- a rule, a scan, a
  test -- or only its care? Care is not a control, and the
  incident's numbers say the agent's hand is the one that
  carries the file in about half the time.
- Where in your files could a secret sit *inside* something
  else -- a saved command, an approval rule, a pasted
  transcript -- where a scanner looking for key shapes would
  not recognise it? That is the class the standard tools
  missed; is anything of yours looking for it?
- A state file of yours crossed last year and was deleted in
  the next commit. Is it gone? Walk the history and the forks
  before you answer, and if the answer is no, is rotation the
  first step written down where a tired operator will find it
  at the worst moment?
- When you take up a new agent, who reads its documentation
  for where its state lives *before* its first run inside a
  published tree -- and where is what they learn written, so
  the next new agent starts from the record instead of from
  the incident?

## 6. Sources

- Apiiro (Shmulik Cohen, Matan Giladi), "Coding Agents Are
  Leaking Your Secrets to GitHub", 5 November 2026, updated
  8 November 2026:
  https://apiiro.com/blog/coding-agents-leaking-secrets-github-dont-ask-again/
- The Hacker News, "Claude Code's 'Don't Ask Again' File
  Exposes Passwords and Keys in 1,122 Public Copies on
  GitHub", November 2026:
  https://thehackernews.com/2026/11/claude-codes-dont-ask-again-file.html
- Slashdot, the same story, 8 November 2026 (it.slashdot.org).
- Anthropic, Claude Code documentation, "Settings files and
  precedence" -- the `allow` rule and the global-excludes
  behaviour, in the vendor's words:
  https://code.claude.com/docs/en/settings
- Hacker News discussion, 7 November 2026 -- the product head's
  response: https://news.ycombinator.com/item?id=50407882
- The product's public tracker, issues from August 2025 onward
  reporting verbatim credential storage in approved commands,
  as catalogued by Apiiro.
- In this project: `privacy-design.md` and
  `privacy-fremont-research.md` (same drawer) for the framework
  this category extends; `personal-documents-warning.md` and
  `personal-documents-shelter.md` for the framework's first
  category; `SECURITY.md` for the spillage doctrine;
  `docs/steady/oracle/instructions.md` for the standing notes a
  visiting system reads.
