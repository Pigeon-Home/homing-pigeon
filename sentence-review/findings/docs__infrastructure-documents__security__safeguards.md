# Findings — docs/infrastructure-documents/security/safeguards.md

Source: docs/infrastructure-documents/security/safeguards.md, reviewed at main 1767fff7.
Sentence units: 101. Flagged: 3. Categories: pre-release 101, post-release 0.

The safeguards catalogue: what the runner defends, layer by layer. Declarative security prose throughout; the breaks are 3 bare cross-reference lines standing where sentences should be. All pre-release: the safeguards described are the shipped posture.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "How to run homing-pigeon without getting burned." | pre-release | flows |  |
| 2 | "This is the *operational* companion to [SECURITY.md](../../SECURITY.md): that…" | pre-release | flows |  |
| 3 | "The runner executes **arbitrary code** as the user…" | pre-release | flows |  |
| 4 | "There is no confirmation prompt." | pre-release | flows |  |
| 5 | "A sandbox exists only where Linux bubblewrap can…" | pre-release | flows |  |
| 6 | "Where `bwrap` cannot engage, the runner refuses to…" | pre-release | flows |  |
| 7 | "The shared secret (a dedicated high-entropy string, by…" | pre-release | flows |  |
| 8 | "Anyone who can sign a job message owns…" | pre-release | flows |  |
| 9 | "Email is the control plane." | pre-release | flows |  |
| 10 | "Whoever can sign a job message is the…" | pre-release | flows |  |
| 11 | "There is no second factor on a job." | pre-release | flows |  |
| 12 | "If any of that makes you uncomfortable, good…" | pre-release | flows |  |
| 13 | "Set it up right and the risk is…" | pre-release | flows |  |
| 14 | "Do all of these before the first job:" | pre-release | flows |  |
| 15 | "**Dedicated mailbox account.** `you-runner@example.com`, never your personal inbox." | pre-release | flows |  |
| 16 | "Nothing personal should ever be reachable from this…" | pre-release | flows |  |
| 17 | "**2-Step Verification + app password.** In the default…" | pre-release | flows |  |
| 18 | "Never the account password. (The alternative is `"auth":…" | pre-release | flows |  |
| 19 | "**Disposable machine.** A Raspberry Pi, a VM, a…" | pre-release | flows |  |
| 20 | "See "Containment" below." | pre-release | flagged | A bare cross-reference ("See "Containment" below.") standing as its own unit — a pointer, not a sentence |
| 21 | "**Guard the secret like a password.** It lives…" | pre-release | flows |  |
| 22 | "When you share it with your SI, paste…" | pre-release | flows |  |
| 23 | "Remember: anyone who can read your SI chat…" | pre-release | flows |  |
| 24 | "Defense in depth, cheapest first:" | pre-release | flows |  |
| 25 | "**Run it in a VM.** Snapshot before you…" | pre-release | flows |  |
| 26 | "If a job goes sideways, roll back in…" | pre-release | flows |  |
| 27 | "The guest boundary contains everything a signed job…" | pre-release | flows |  |
| 28 | "**Don't run as root unless you mean it.**…" | pre-release | flows |  |
| 29 | "Note the exception: on **Windows the Scheduled Task…" | pre-release | flows |  |
| 30 | "`install.exe --run-as pigeon` (or another dedicated account) runs…" | pre-release | flows |  |
| 31 | "If the machine matters to you, prefer a…" | pre-release | flows |  |
| 32 | "The installer takes the convenient path; the safe…" | pre-release | flows |  |
| 33 | "**Execution confinement (shipped).** Two checks." | pre-release | flows |  |
| 34 | "Set `workspace_root` and the Oracle attests that the…" | pre-release | flows |  |
| 35 | "That one is a snapshot, not a sandbox." | pre-release | flows |  |
| 36 | "See PROTOCOL.md §9.4." | pre-release | flagged | A bare cross-reference ("See PROTOCOL.md §9.4.") standing as its own unit — a pointer, not a sentence |
| 37 | "On Linux, `security.modes.confinement` set to `enforce` runs the…" | pre-release | flows |  |
| 38 | "Off by default." | pre-release | flows |  |
| 39 | "Under `enforce` a sandbox that cannot engage (no…" | pre-release | flows |  |
| 40 | "Inside the sandbox the job sees `/usr`, its…" | pre-release | flows |  |
| 41 | "See SECURITY.md." | pre-release | flagged | A bare cross-reference ("See SECURITY.md.") standing as its own unit — a pointer, not a sentence |
| 42 | "The workdir the sandbox binds is its real…" | pre-release | flows |  |
| 43 | "On Windows, where there is no sandbox, those…" | pre-release | flows |  |
| 44 | "A `full` view sends stdout and stderr back…" | pre-release | flows |  |
| 45 | "If your jobs touch anything sensitive, that's the…" | pre-release | flows |  |
| 46 | "The Oracle — implemented, specified in PROTOCOL.md —…" | pre-release | flows |  |
| 47 | "**Result policies.** `full` / `redacted` / `summary` /…" | pre-release | flows |  |
| 48 | "The SI gets answers, not raw output." | pre-release | flows |  |
| 49 | "**The ceiling is yours.** `max_result_view` lives in *your*…" | pre-release | flows |  |
| 50 | "No job can widen disclosure past it —…" | pre-release | flows |  |
| 51 | "**Privacy budget.** Each job gets a fixed number…" | pre-release | flows |  |
| 52 | "Rate limiting slows probing; the budget stops it." | pre-release | flows |  |
| 53 | "**Read the logs.** `runner.log` in the install dir…" | pre-release | flows |  |
| 54 | "A job you didn't send is a five-alarm…" | pre-release | flows |  |
| 55 | "**Keep the runner updated.** New releases fix real…" | pre-release | flows |  |
| 56 | "Check the releases page when you think of…" | pre-release | flows |  |
| 57 | "**Rotate the shared secret every 90 days.** Add…" | pre-release | flows |  |
| 58 | "The steps are `docs/use/secret-rotation.md`." | pre-release | flows |  |
| 59 | "Do not overwrite `shared_secret` in place for a…" | pre-release | flows |  |
| 60 | "A leak is different: replace the secret now…" | pre-release | flows |  |
| 61 | "**Prune the mailbox.** The runner marks processed mail…" | pre-release | flows |  |
| 62 | "Delete them periodically — they're signed, but they…" | pre-release | flows |  |
| 63 | "**Know what the box reaches out for.** The…" | pre-release | flows |  |
| 64 | "One more thing can leave the box: with…" | pre-release | flows |  |
| 65 | "The request pattern says which extensions are installed." | pre-release | flows |  |
| 66 | "On a box whose posture is "nothing leaves…" | pre-release | flows |  |
| 67 | "Material nothing pins is never fetched unless you…" | pre-release | flows |  |
| 68 | "Don't point the runner at a mailbox anyone…" | pre-release | flows |  |
| 69 | "Don't reuse the runner's mailbox for anything else." | pre-release | flows |  |
| 70 | "It's not an email account; it's a control…" | pre-release | flows |  |
| 71 | "Don't run jobs you don't understand on machines…" | pre-release | flows |  |
| 72 | "The SI writes the script; you own the…" | pre-release | flows |  |
| 73 | "Don't assume TLS means private." | pre-release | flows |  |
| 74 | "Transport TLS encrypts email in transit, but the…" | pre-release | flows |  |
| 75 | "The Oracle (§4) exists precisely because "the SI"…" | pre-release | flows |  |
| 76 | "The board (PROTOCOL.md section 13) is always on…" | pre-release | flows |  |
| 77 | "Tighten in this order, when you have a…" | pre-release | flows |  |
| 78 | "**`task_timeout`** (default 86400): a claim lapses after this…" | pre-release | flows |  |
| 79 | "Shorter for quick jobs so a crashed worker…" | pre-release | flows |  |
| 80 | "**`worker_allowlist`**: name the `worker_id`s that may pull." | pre-release | flows |  |
| 81 | "Empty means anyone with the secret." | pre-release | flows |  |
| 82 | "**`worker_compartments`** on tasks that carry `compartments`: a task…" | pre-release | flows |  |
| 83 | "A policy, not a proof — a worker…" | pre-release | flows |  |
| 84 | "**`require_review: true`**: finished tasks park in `pending_review` until…" | pre-release | flows |  |
| 85 | "Use it when a result changes something you…" | pre-release | flows |  |
| 86 | "**`dag_mode: enforce`** when a task's `requires[]` must be…" | pre-release | flows |  |
| 87 | "**One key per worker** (`additional_secrets` + a `key_policies`…" | pre-release | flows |  |
| 88 | "Watch it with `homing-pigeon --inspect board` (state counts…" | pre-release | flows |  |
| 89 | "**Secret leaked or suspected leaked:**" | pre-release | flows |  |
| 90 | "Revoke the mailbox credential *now* (Google Account →…" | pre-release | flows |  |
| 91 | "Without mailbox access the runner can't receive jobs…" | pre-release | flows |  |
| 92 | "Generate a fresh shared secret (`openssl rand -hex…" | pre-release | flows |  |
| 93 | "Paste the new string to your SI." | pre-release | flows |  |
| 94 | "Check `runner.log` and the mailbox for jobs you…" | pre-release | flows |  |
| 95 | "**Machine compromised or suspected:**" | pre-release | flows |  |
| 96 | "Stop the runner (uninstall the service)." | pre-release | flows |  |
| 97 | "Revert the VM snapshot — or wipe and…" | pre-release | flows |  |
| 98 | "Rotate the secret as above (assume it was…" | pre-release | flows |  |
| 99 | "Review what the jobs touched before you revert." | pre-release | flows |  |
| 100 | "**You see a job you didn't send in…" | pre-release | flows |  |
| 101 | "Then figure out how the secret leaked —…" | pre-release | flows |  |
