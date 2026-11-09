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
8. **The declined prompt.** One tool in the survey does offer
   the right protection -- a first-run question, "shall I keep
   my files out of git?" -- once, inside a wall of first-run
   text. The operator who answers no, or who never sees the
   question in a scripted run, has an unprotected full
   transcript at the root of the tree, and no second asking.
9. **The home sweep.** A dotfiles repository, or a "backup my
   setup" repository, commits the home directory wholesale --
   an agent's whole home folder in one push: its sign-in file,
   its key registry, its folder-trust grants, its transcripts.
   No single file was ever chosen; the folder was.
10. **The relocated home.** A vendor's own guidance suggests
    pointing an agent's home directory at a per-project
    location. Followed with the directory inside the tree, the
    advice moves the sign-in file and the transcripts inside
    the commit scope, gift-wrapped as a best practice.
11. **The pre-filled template.** Starter kits and project
    templates ship with the workspace configuration already
    filled in -- in one documented case, with the user's real
    backend tokens written into it automatically. The first
    commit, made before the user has changed anything,
    publishes the token.
12. **The share-for-help export.** A session is exported and
    the file dropped into the tree "for the issue report", or a
    transcript copied in to show a teammate. Helpfulness is the
    motive; the transcript's contents are the payload.
13. **The un-ignore trap.** A maintained template ignores a
    settings folder and then un-ignores the shareable files
    inside it by name. A hand broadens the un-ignore a little,
    and the secret-bearing sibling -- the MCP configuration
    beside the settings -- rides in with the shareable ones.
14. **The bridge.** An operator working through git-svn keeps
    two ignore systems that do not synchronise, and each
    direction of the bridge has its own quiet failure. The
    manual's own quick route for carrying the Subversion
    patterns across writes them into the git side's
    machine-local exclude -- the travelling list converted, by
    the documented command, into the local shape. A file
    committed on the git side crosses by `dcommit` into
    permanent Subversion revisions whatever the Subversion
    properties would have said. And the bridge's own mappings
    and configuration do not clone, so a fresh clone silently
    starts with neither the bridge nor whatever protection was
    hung on it, and nothing announces the loss.

A protection that depends on the operator noticing the file,
remembering the rule, or being an expert in source control is
not a protection against any of these shapes. The safeguards
have to fire at the boundary, before the commit or push, and
they have to be part of what ships -- travelling with the
project the way the failed exclude did not.

## 3. Other agents keep the same papers

The incident's file belongs to one product; the category does
not. A survey of the other agents a tree here might be worked
on with -- from each vendor's own documentation, and from
GitHub's maintained ignore templates, not from any account of
anyone's mistakes -- finds the same three ingredients in
nearly every tool:

1. **Approval memory is a file.** "Don't ask again" answers,
   auto-approve lists, trusted-folder grants and tool
   allowlists are persisted as JSON, TOML or YAML on disk,
   under names like `allow`, `autoApprove`, `allowedTools` and
   `terminalAllowlist` -- and allowlist entries can be the full
   command strings themselves.
2. **MCP configuration is the universal secret carrier.**
   Every tool surveyed configures its tool servers in a
   JSON-shaped file with `env` and `headers` maps, and every
   vendor's own examples show keys pasted into those maps. The
   filename varies; the shape does not.
3. **The shared/local split is two sibling files.** A settings
   file meant to be committed stands beside a local sibling
   that is not -- `settings.json` beside `settings.local.json`
   in two different vendors' layouts -- and the boundary
   between "the project's" and "mine" is one word in a
   filename, which a non-expert cannot be expected to see.

The survey, condensed (state written *inside* a project tree;
home-directory state is named where it is the notable part):

| Tool | Papers in the tree | Its own documentation's stance |
|---|---|---|
| Cursor | `.cursor/mcp.json`; `.cursor/permissions.json` (allowlist entries match full command strings); project rules | The per-repo permissions file is meant to be committed "so teammates inherit the same rules" -- content, not the path, is what needs guarding |
| GitHub Copilot | `.github/copilot/settings.json` beside `.github/copilot/settings.local.json`; home state in one directory, including `permissions-config.json` ("saved tool and directory permissions per project") and `providers.json` (the user's own keys) | The home directory's contents are enumerated plainly in the vendor's reference; the local sibling is the personal one |
| OpenAI Codex | Project `.codex/config.toml`, committable by design; home state includes `auth.json` (the sign-in), transcripts, approval policy | The vendor's guidance suggests a per-project agent home -- followed inside the tree, it relocates every home file into the commit scope (section 2, shape 10) |
| Gemini CLI | `.gemini/settings.json`, the documented team-shared file, its tool-server entries carrying `env` values; home state includes `trustedFolders.json` and local checkpoints | The shared file is committed on purpose; what needs guarding is what is pasted into it |
| Aider | The full transcript, `.aider.chat.history.md`, at the repository root by default, plus `.aider.env` and caches; the tool commits its own edits | The vendor ships the right default as a first-run offer to add `.aider*` to the project's `.gitignore` -- protection one keystroke from absent (shape 8) |
| Windsurf / Devin Desktop | Workspace rules and workflows, version-controlled by design | The vendor states its generated memories "are never committed to your repository"; the exposure is only what a user pastes into the shareable rules |
| Continue | A workspace folder of blocks; model blocks carry an `apiKey` field in plain YAML | The field waits in the documentation's own examples to be filled in -- in the workspace copy |
| Cline / Roo Code | `.cline/mcp.json`, `.roo/mcp.json` (project tool-server files, team-shareable by design); home state includes a providers file its docs describe as "API keys and model provider configuration" | The project MCP file is supposed to be shared, so a token pasted into it is published by the intended workflow, not against it |
| Amazon Q Developer | Workspace agent definitions carrying `allowedTools` trust grants and tool-server definitions together | The vendor's own walkthrough configures a database tool server with trusted tools in a workspace agent file |
| Kiro | `.kiro/settings/mcp.json` with per-server `autoApprove` arrays; the workspace folder is "project-specific, commit to git for team sharing" | Starter material can arrive with the workspace MCP file pre-filled (shape 11) |
| OpenCode | Project-root config that may carry a provider `apiKey` and a `permission` map; home state keeps credentials in `auth.json`, mode 600 | The safe path exists (`/connect` writes the home file); the mistake is typing the key into the project file instead |

Underneath them all sits the substrate: an editor's workspace
folder (`.vscode/`, with its own `mcp.json` beside the shareable
settings) and a project-system folder (`.idea/`, per-user state
inside a mostly shareable directory) -- the same shared/local
blur, a decade older than the agents.

**The correction the survey makes to a one-vendor mindset:**
for several of these tools the vendor *intends* the
configuration file to be shared. A path ban would fight the
vendor's own workflow. What protects the user inside the
intended workflow is a *content* rule: this file is yours to
share; these values -- a secret-shaped value in an `env` map, a
full command string in an allowlist -- are not. Section 4's
guard is specified in those terms.

The vendors also say the core of it as plainly as it can be
said, and this project's documents aim at the same plainness.
GitHub's guidance on removing sensitive data, the canonical
sentence of the whole subject:

> "Once you have pushed a commit to GitHub, you should
> consider any sensitive data in the commit compromised. If
> you have committed a password, you should change it. If you
> have committed a key, generate a new one."

Aider's changelog gives the whole rationale for a shipped
default in eleven words: "Create a `.gitignore` with `.aider*`
to prevent users from accidentally adding aider files to git."
And Cursor's ignore-file documentation hands the non-expert a
list to copy verbatim -- environment files, credentials files,
key files -- which is the form a shipped default should take:
names, not principles.

### The travel test, and the other version-control systems

Not every tree is a git tree, and the question the incident
turned on is the same in every system. Call it **the travel
test**: does the protection live in something that travels
with the project -- a committed file, a versioned property --
or only on one machine, in one user's configuration, where
the next machine and the next teammate never see it? The
incident's exclude failed the test. So do its twins:

- **Subversion** ships both shapes and its own book draws the
  line in the incident's terms: patterns in a user's runtime
  config (`global-ignores`) apply to operations "performed on a
  particular computer, or by a particular user of a computer",
  while the `svn:ignore` and `svn:global-ignores` *properties*
  are stored in the repository and bind everyone who checks the
  tree out. Both share git's hard rule: once an object is under
  version control, ignore mechanisms no longer apply to it. The
  system's credential cache (a per-user folder holding, where
  no OS store exists, passwords the client asked permission to
  keep unencrypted) is the home sweep's Subversion member.
- **git-svn** makes a user maintain two ignore systems that do
  not synchronise. The documented quick route from SVN
  properties appends them to `.git/info/exclude` -- the
  machine-local shape again, recommended by the manual. The
  other route manufactures `.gitignore` files that, once
  committed and sent back, land in the Subversion repository
  as files its own users never asked for. And `dcommit` is a
  publication boundary of exactly the same rank as `push`:
  whatever the git side committed, the SVN side keeps, as a
  permanent revision.
- **Mercurial** gets the default right: its ignore file is an
  ordinary committed file in the repository root, so the
  project list travels -- with its own non-expert trip hazard
  (the default pattern syntax is regexp, not glob). Its
  per-user ignore mechanism fails the travel test the same way
  the others' do, and its configuration can hold passwords in
  plain text in an `[auth]` section -- a content shape, not a
  filename.

One observation covers all three systems: in each, the
machine-local mechanism is the one with the friendliest name
("global"), and the one a setup guide reaches for first. Every
vendor ships both; every incident of this class comes from the
local one being mistaken for the travelling one.

So the pattern list is not welded to one system's filename.
Rendered for a Subversion tree, the shipped list belongs in an
`svn:global-ignores` property on the repository root (never in
a user config's `global-ignores` -- that is the local shape
wearing the same name). Rendered for Mercurial, it belongs in
a committed `.hgignore` under a `syntax: glob` header. Both
renderings ship as a template file in this drawer,
`agent-state-ignores.txt`, ready to apply, and a unit test
(`runner/tests/test_agent_state_ignore_renderings.py`) holds
the renderings and the git list in agreement, so the three
cannot drift apart quietly. The names are the git list's
names, without the path prefixes:

```text
settings.local.json   config.json           seen.json
board.json            oracle-chat.jsonl     oracle-briefs.jsonl
.aider.chat.history.md  .aider.input.history  .aider.llm.history
.aider.env            auth.json             providers.json
oauth_creds.json      trustedFolders.json   permissions-config.json
session-store.db      opencode.db           taskHistory.json
history.jsonl         events.jsonl          api_conversation_history.json
```

And one mutual rule, cheapest on the whole list: each system's
admin folder (`.git/`, `.svn/`, `.hg/`) is protected by its own
tool and by no other, so every system's ignore set names the
other two -- a folder carried across systems (a zip attached
to an issue, a parent folder added wholesale, a migration)
must not publish pristine stores, bridge mappings and
per-repository config. The shipped git list already carries
`.svn/` and `.hg/` for exactly this reason.

Two consequences shape what section 4 ships. First, the
protections are written against *categories and shapes* -- a
settings file under an agent's folder, an allow array in
staged JSON, a secret-shaped value sitting inside a saved
command -- not against one vendor's one filename, so a tree
worked on by a different agent, or by next year's agent, is
covered by the same rules. Second, a visiting system reading
this document should expect its own papers to be governed by
the deployment it is visiting: its approval memory and the
deployment's state are private-shelf material there, whatever
its home defaults say, and if the deployment has no rule for
them, that absence is worth saying to the operator out loud.

## 4. What this project ships against the class

Each piece below is in the framework's existing shapes, and
each is stated as it stands.

- **Ignore defaults that travel.** The repository's root
  `.gitignore` -- an existing root file, edited, not added --
  carries the agent-state shapes in two blocks. The first is
  this suite's own papers and the incident's file:
  `**/.claude/settings.local.json`, `**/config.json`,
  `seen.json`, `board.json`, `oracle-chat.jsonl`,
  `oracle-briefs.jsonl`, `outbox/`, `work/`, with a comment
  recording that the shared `.claude/settings.json` may be
  committed but must never hold a secret. The second block is
  the survey's: the generic local settings sibling, the
  transcript-keeping agent's root files, the home-state
  filenames that enter a tree only by a home sweep or a
  relocated agent home, transcript shapes generally, one
  editor family's per-user state, and the Subversion and
  Mercurial admin folders of section 3's mutual rule. The
  protection clones with the project, which is the property
  the incident's exclude lacked. A unit test
  (`runner/tests/test_gitignore_state_files.py`) pins both
  blocks and fails if a pattern is dropped; before the second
  block landed, every tracked file in the tree was checked
  against it and none matched. The same list rendered for
  Subversion and Mercurial ships as a template in this drawer
  (`agent-state-ignores.txt`, section 3), held in agreement
  with the git list by its own test.
- **A staged-content guard.** `runner/tools/approvalguard.py`
  is a shelter-shaped tool in the line of
  `runner/tools/nameguard.py`: standard library only, its
  forbidden shapes declared in code as a registry an operator
  may extend with a file of their own in the same format,
  invoked and never ambient. It scans what is *staged* -- the
  content a commit is about to carry -- and fails closed on
  three rule families: a staged path matching a declared shape
  (an agent's local settings file and its shared sibling, a
  deployment's `config.json`, the runner's state and chat-log
  filenames, its outbox and work folders); permission-grant
  state in staged JSON (allow arrays and saved command
  strings); and secret-shaped values -- inside those command
  strings specifically (credential assignments, passwords in
  URLs, password flags), the class the generic scanners missed
  in the incident, and known key formats anywhere in staged
  text. Its report follows the framework's split of existence
  from value: it names the file and the rule it tripped, and
  never prints the secret. Its rules speak of paths and
  content, never of one version-control system, so another
  system's staged area can feed the same scan; the front door
  shipped here reads the git index. Nothing wires the tool
  into a hook or into CI: like the name guard, wiring is a
  deliberate adoption step, taken by the operator, or by their
  agent at the operator's word.
- **A feature in the modes family.** The guard's behaviour is
  declared the way `privacy-design.md` section 2 requires: a
  named feature, `agent_state_guard`, under `security.modes`
  in `runner/guard/security.py` and stated in the shipped
  example config. Its semantics are
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
  material: handling rules for agent
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
  files as private-shelf material, under the doctrine that
  already governs the rest of the shelf: declare the spill,
  start containment at once, rotate first.
- **The design record, and the plain warning.** The category
  stands in the framework's own design record
  (`privacy-design.md`, section 8), with its configuration row
  among the surveyed models and its disposition against the
  framework's principles, and the staged guard recorded there
  as the first concrete form of the tree-wide value-confinement
  test that design queues. The operator-facing warning stands
  in the safeguards document
  (`docs/infrastructure-documents/security/safeguards.md`,
  section 5a), in plain language for a reader who does not
  know what an ignore file is: the agent keeps a memory of
  what you approved; that memory is private; the shipped
  protections keep it out of commits automatically; if one was
  ever committed, change the passwords and keys first.

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

The survey also recorded the guard's next extensions, which
are specified here so the record is complete, and are *not*
claimed as shipped: tool-server configuration as a category of
its own (any staged file named for it, and any staged JSON
carrying its top-level key, gets its `env` and `headers` maps
scanned wherever the file sits, including files designed to be
committed); grant state under its other names (`autoApprove`,
`allowedTools`, the allowlist keys, a `permission` map), with
allowlist entries scanned as the command strings they can be;
the same content shapes in TOML and YAML, where two vendors'
configuration lives; and staged areas beyond git's. That last
extension is specified as **the same guard's second front
door, not a second tool**: the guard's rules are already
written in terms of paths and content, never of one
version-control system, and its shipped front door reads the
git index; what a Subversion deployment adds is a front door
of its own -- a working copy's scheduled additions, fed to the
same scan as the same (path, content) pairs, at the pre-commit
moment -- plus content rules for a Mercurial `[auth]` password
line and a Subversion proxy password. What section 3 ships for
those systems today is the travelling half: the pattern list,
rendered as the template file in this drawer, for an
operator's own trees.

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
- For the survey in section 3, vendor documentation and
  official repositories only: Cursor's ignore-file, permissions
  and MCP references (cursor.com/docs); the Copilot CLI
  configuration-directory reference and the sensitive-data
  guidance (docs.github.com); GitHub's maintained ignore
  templates, including the VisualStudioCode and JetBrains
  globals (github.com/github/gitignore); OpenAI's Codex
  CLI/config/auth documentation (developers.openai.com);
  Gemini CLI configuration and checkpointing (the project's
  official repository and docs); Aider's configuration and
  options documentation and its changelog (aider.chat,
  github.com/Aider-AI/aider); Windsurf's Cascade memories
  documentation (docs.windsurf.com); Continue's configuration
  references (docs.continue.dev); Cline's and Roo Code's
  documentation (docs.cline.bot, docs.roocode.com); Amazon Q
  Developer's agent format, MCP and project-rules
  documentation (aws.github.io, docs.aws.amazon.com); Kiro's
  documentation (kiro.dev) and AWS's configuration
  walkthrough; OpenCode's config and providers documentation
  (opencode.ai); Microsoft's VS Code settings documentation
  (code.visualstudio.com).
- For the travel test: the Subversion Book, "Ignoring
  Unversioned Items" and the client credential-caching
  material (svnbook.red-bean.com); the git-svn manual
  (git-scm.com/docs/git-svn); Mercurial's configuration help
  (the `[ui] ignore` and `[auth]` sections).
- In this project: `privacy-design.md` and
  `privacy-fremont-research.md` (same drawer) for the framework
  this category extends; `personal-documents-warning.md` and
  `personal-documents-shelter.md` for the framework's first
  category; `SECURITY.md` for the spillage doctrine;
  `docs/steady/oracle/instructions.md` for the standing notes a
  visiting system reads.
