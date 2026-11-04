# Findings — docs/infrastructure-documents/reports/falkenstein-rig-2026-10-31.md

Source: docs/infrastructure-documents/reports/falkenstein-rig-2026-10-31.md, reviewed at main e4747940.
Sentence units: 183. Flagged: 1. Categories: pre-release 183, post-release 0.

The Germany rig's dossier: what the machine is and costs, what it is for, the setup order it follows (runner first, everything after that a job, off email), and the setup record step by step — Windows installed, SSH access, the runner running, the first job, the first repository commit, the watchdog's first firing. Fact items and narrative prose alternate, each section's items answering the heading idea the prose before them states. The stamp comment (unit 1) is the only non-sentence.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "A new fleet machine, created 31 Oct 2026:…" | pre-release | flows |  |
| 3 | "Facts are read from the provider's API at…" | pre-release | flows |  |
| 4 | "This report is kept current as the seat…" | pre-release | flows |  |
| 5 | "Provider: **Hetzner Cloud**." | pre-release | flows |  |
| 6 | "Data center: **Falkenstein, Germany** (location `fsn1`)." | pre-release | flows |  |
| 7 | "The machine is referred to as **the Germany…" | pre-release | flows |  |
| 8 | "Server name: `falkenstein-win-1`; server id **173851141**; created 2026-10-31." | pre-release | flows |  |
| 9 | "(A first machine of the same name and…" | pre-release | flows |  |
| 10 | "Public IPv4: **2.28.30.118**." | pre-release | flows |  |
| 11 | "Type: **CX43** — 8 vCPU (shared), 16 GB…" | pre-release | flows |  |
| 12 | "The size was chosen for cores and memory,…" | pre-release | flows |  |
| 13 | "Cost: **$20.63 per month** — the EUR 18.49…" | pre-release | flows |  |
| 14 | "Billed hourly up to the monthly cap, so…" | pre-release | flows |  |
| 15 | "Bootstrap image: Debian 12, present only so the…" | pre-release | flows |  |
| 16 | "The bootstrap root password was reset through the…" | pre-release | flows |  |
| 17 | "The fleet's Windows seat." | pre-release | flows |  |
| 18 | "Two jobs:" | pre-release | flows |  |
| 19 | "Prove the Windows half of the suite live…" | pre-release | flows |  |
| 20 | "Fuzzing capacity on the platform the other rigs…" | pre-release | flows |  |
| 21 | "San Francisco is not retired: the droplet is…" | pre-release | flows |  |
| 22 | "A standing order for every new system, first…" | pre-release | flows |  |
| 23 | "**The runner is installed first.** Nothing else is…" | pre-release | flows |  |
| 24 | "**Every step after that is a job.** Configuration,…" | pre-release | flows |  |
| 25 | "Nothing is placed by hand." | pre-release | flows |  |
| 26 | "**This machine stays off email.** No mailbox, no…" | pre-release | flows |  |
| 27 | "Jobs are submitted locally: an operator connects by…" | pre-release | flows |  |
| 28 | "Windows itself is installed from Hetzner's own ISO…" | pre-release | flows |  |
| 29 | "Windows Server runs under its evaluation terms until…" | pre-release | flows |  |
| 30 | "**Assume a bare machine.** No procedure for this…" | pre-release | flows |  |
| 31 | "Every step installs what it needs, in the…" | pre-release | flows |  |
| 32 | "A procedure that works only because something happened…" | pre-release | flows |  |
| 33 | "The first repository job below follows the rule:…" | pre-release | flows |  |
| 34 | "**Windows installed.** Windows Server 2022 Standard (Server Core),…" | pre-release | flows |  |
| 35 | "The install ISO has been detached, so a…" | pre-release | flows |  |
| 36 | "**Access is SSH.** The OpenSSH server is installed,…" | pre-release | flows |  |
| 37 | "PowerShell remoting (WinRM) does not work from the…" | pre-release | flows |  |
| 38 | "The web console's typing drops shift states intermittently,…" | pre-release | flows |  |
| 39 | "**The runner is installed and running.** Homing Pigeon…" | pre-release | flows |  |
| 40 | "The installer's doctor check passes: 18 passed, 0…" | pre-release | flows |  |
| 41 | "**Off email, as ordered.** The runner's transports are…" | pre-release | flows |  |
| 42 | "The install's default email transport was replaced before…" | pre-release | flows |  |
| 43 | "The machine's shared secret and full runner configuration…" | pre-release | flows |  |
| 44 | "**First job proven end to end.** A signed…" | pre-release | flows |  |
| 45 | "The result's signature verified on the operating VM." | pre-release | flows |  |
| 46 | "The local submission route of the setup order…" | pre-release | flows |  |
| 47 | "**First repository commit from this machine.** A job…" | pre-release | flows |  |
| 48 | "The GitHub credential travelled inside the signed job…" | pre-release | flows |  |
| 49 | "**The watchdog fired on the first attempt, as…" | pre-release | flows |  |
| 50 | "Eleven seconds into the first attempt it killed…" | pre-release | flows |  |
| 51 | "The second attempt declared the three key paths…" | pre-release | flows |  |
| 52 | "Lessons for any job that fetches tools: a…" | pre-release | flows |  |
| 53 | "The whole job was rehearsed before sending against…" | pre-release | flows |  |
| 54 | "**Every security setting turned on (31 Oct 2026,…" | pre-release | flows |  |
| 55 | "The Oracle stays deterministic — no local model…" | pre-release | flows |  |
| 56 | "Two findings came straight out of the attempt:" | pre-release | flows |  |
| 57 | "**Confinement cannot enforce on Windows, and the runner…" | pre-release | flows |  |
| 58 | "Refusing to start; fix the sandbox, or set…" | pre-release | flows |  |
| 59 | "That is Decision 1 behaving as designed —…" | pre-release | flows |  |
| 60 | "Confinement was set to `audit` — the strongest…" | pre-release | flows |  |
| 61 | "**Audience enforcement turns unaddressed jobs away.** The first…" | pre-release | flows |  |
| 62 | "With audience enforcing, a job must be addressed…" | pre-release | flows |  |
| 63 | "Resent addressed, both passed: a clock job returning…" | pre-release | flows |  |
| 64 | "**A divergence to chase: `job_user` enforces in name…" | pre-release | flows |  |
| 65 | "Where confinement refused a setting it cannot honor,…" | pre-release | flows |  |
| 66 | "On Linux the mode runs jobs as another…" | pre-release | flows |  |
| 67 | "This needs either an implementation or the same…" | pre-release | flows |  |
| 68 | "**A bug found on the way, recorded here.**…" | pre-release | flows |  |
| 69 | "On this email-free machine the service waited forever…" | pre-release | flows |  |
| 70 | "prompt: no log written, no channels created, no…" | pre-release | flows |  |
| 71 | "The machine carries an inert placeholder mailbox user…" | pre-release | flows |  |
| 72 | "The fix (the gate skips when email is…" | pre-release | flows |  |
| 73 | "**Output shapes, and a script encoding bug (1…" | pre-release | flows |  |
| 74 | "Large output (2,000 numbered lines) round-tripped exact in…" | pre-release | flows |  |
| 75 | "Non-ASCII output built at run time from code…" | pre-release | flows |  |
| 76 | "The output pipeline is sound." | pre-release | flows |  |
| 77 | "The fifth shape failed: a PowerShell script holding…" | pre-release | flows |  |
| 78 | "The runner stages every script as UTF-8 with…" | pre-release | flows |  |
| 79 | "The fix stages a `.ps1` with the UTF-8…" | pre-release | flows |  |
| 80 | "It is pinned by a new test family…" | pre-release | flows |  |
| 81 | "The fix has since landed on main as…" | pre-release | flows |  |
| 82 | "One scope note stays open: a script fetched…" | pre-release | flows |  |
| 83 | "**The Oracle on Windows, and a console encoding…" | pre-release | flows |  |
| 84 | "The first (c5ef73a1) declared five queries in its…" | pre-release | flows |  |
| 85 | "Attest answered true for exit_zero; senses answered with…" | pre-release | flows |  |
| 86 | "All five answers are the designed ones." | pre-release | flows |  |
| 87 | "The job's own read-back confirmed the posture: oracle_mode…" | pre-release | flows |  |
| 88 | "The second job (75563043) ran the installed binary's…" | pre-release | flows |  |
| 89 | "The ask round trip worked at the record…" | pre-release | flows |  |
| 90 | "No model took part." | pre-release | flows |  |
| 91 | "But the answer never reached the screen: printing…" | pre-release | flows |  |
| 92 | "The records carry characters the Windows console's cp1252…" | pre-release | flows |  |
| 93 | "The loopback window does not have the fault:…" | pre-release | flows |  |
| 94 | "The fix makes the terminal chat's default printer…" | pre-release | flows |  |
| 95 | "It is pinned by a new test family…" | pre-release | flows |  |
| 96 | "The fix sits in a held commit and…" | pre-release | flows |  |
| 97 | "**The repo suites under the box's own Python…" | pre-release | flows |  |
| 98 | "Two shape notes from the run: the checkout…" | pre-release | flows |  |
| 99 | "The job finished exit 0 and its signed…" | pre-release | flows |  |
| 100 | "How much work does a remote upgrade throw…" | pre-release | flows |  |
| 101 | "The question decides how often the rigs should…" | pre-release | flows |  |
| 102 | "The supposition below was written down and committed…" | pre-release | flows |  |
| 103 | "Supposition, recorded before measuring: a remote upgrade swaps…" | pre-release | flows |  |
| 104 | "The fuzzing grow runs as its own processes…" | pre-release | flows |  |
| 105 | "The runner itself is down only while the…" | pre-release | flows |  |
| 106 | "The only work an upgrade can throw away…" | pre-release | flows |  |
| 107 | "Predicted measurement: runner pause under one minute, fuzzing…" | pre-release | flows |  |
| 108 | "The upgrade key half of the test landed…" | pre-release | flows |  |
| 109 | "The upgrade secret and its key policy are…" | pre-release | flows |  |
| 110 | "The negative test behaved exactly as designed: a…" | pre-release | flows |  |
| 111 | "The upgrade itself could not be run, so…" | pre-release | flows |  |
| 112 | "The host half of the procedure — the…" | pre-release | flows |  |
| 113 | "Installing it was held for the owner's word…" | pre-release | flows |  |
| 114 | "Until an applier is in place, a staged…" | pre-release | flows |  |
| 115 | "Two smaller facts were measured on the way,…" | pre-release | flows |  |
| 116 | "A plain restart of the runner on this…" | pre-release | flows |  |
| 117 | "The grow never noticed the restart." | pre-release | flows |  |
| 118 | "Its loop process and both lanes' processes hold…" | pre-release | flows |  |
| 119 | "That is direct evidence for the supposition's mechanism…" | pre-release | flows |  |
| 120 | "Verdict on the supposition: untested as written, with…" | pre-release | flows |  |
| 121 | "The claim that an upgrade throws away no…" | pre-release | flows |  |
| 122 | "The runner-pause prediction (under a minute) sits comfortably…" | pre-release | flows |  |
| 123 | "Work thrown away by that restart: no fuzzing…" | pre-release | flows |  |
| 124 | "Cadence consequence: the number the cadence decision waits…" | pre-release | flows |  |
| 125 | "The standing rule — an upgrade every two…" | pre-release | flows |  |
| 126 | "The standing upgrade automation stops at the same…" | pre-release | flows |  |
| 127 | "A standing hourly watch (germany-remote-upgrade-watch) now records that…" | pre-release | flows |  |
| 128 | "The owner's word for installing the applier and…" | pre-release | flows |  |
| 129 | "The measurement itself cannot start yet, for a…" | pre-release | flows |  |
| 130 | "A staging script that names this rig's Windows…" | pre-release | flows |  |
| 131 | "Until the policy is re-pinned to a Windows…" | pre-release | flows |  |
| 132 | "The applier install remains held as well, as…" | pre-release | flows |  |
| 133 | "No cadence change follows from this addendum; the…" | pre-release | flows |  |
| 134 | "The word to force the upgrade through was…" | pre-release | flows |  |
| 135 | "The re-pin came first." | pre-release | flows |  |
| 136 | "A Windows staging script was written for this…" | pre-release | flows |  |
| 137 | "The upgrade secret itself did not change." | pre-release | flows |  |
| 138 | "The runner was restarted on the re-pinned policy,…" | pre-release | flows |  |
| 139 | "Two things the run exposed on the way,…" | pre-release | flows |  |
| 140 | "Stopping the HomingPigeon task does not stop the…" | pre-release | flows |  |
| 141 | "The frozen runner's processes detach and survive the…" | pre-release | flows |  |
| 142 | "The first negative test of this run was…" | pre-release | flows |  |
| 143 | "All sets were killed and a single set…" | pre-release | flows |  |
| 144 | "Any future restart on this rig must kill…" | pre-release | flows |  |
| 145 | "With the placeholder mailbox values removed, the 3.15.0…" | pre-release | flows |  |
| 146 | "The inert placeholder values were restored from the…" | pre-release | flows |  |
| 147 | "The applier was installed at C:\ProgramData\homing-pigeon\hp-remote-upgrade-apply.ps1, fired every…" | pre-release | flows |  |
| 148 | "The installed copy differs from the kit file…" | pre-release | flows |  |
| 149 | "The second of those is a defect in…" | pre-release | flows |  |
| 150 | "Kit defect, found live (attempt 1): the applier…" | pre-release | flows |  |
| 151 | "The release asset is served as application/octet-stream, so…" | pre-release | flows |  |
| 152 | "Outcome: "FAILED: no sums line for homing-pigeon-windows-x86_64-3.15.33.zip", written…" | pre-release | flows |  |
| 153 | "Kit defect, found live (attempt 2): the stop…" | pre-release | flows |  |
| 154 | "Outcome: "FAILED: the installer failed (runner restarted on…" | pre-release | flows |  |
| 155 | "The installed applier now force-kills leftover runner processes…" | pre-release | flows |  |
| 156 | "Both defects are fixed in the kit at…" | pre-release | flows |  |
| 157 | "The measured upgrade (attempt 3, staging job 0015d70f,…" | pre-release | flows |  |
| 158 | "The stop-to-start window inside the cycle is under…" | pre-release | flows |  |
| 159 | "A post-upgrade addressed clock job (5ae2b3b7) returned exit" | pre-release | flows |  |
| 160 | "The grow did not notice: its supervisor process…" | pre-release | flows |  |
| 161 | "start time it had at 14:36, the lane…" | pre-release | flows |  |
| 162 | "Work thrown away by the upgrade: none that…" | pre-release | flows |  |
| 163 | "Cadence consequence: the measured pause is under a…" | pre-release | flows |  |
| 164 | "Final state: the placeholder mailbox values were removed…" | pre-release | flows |  |
| 165 | "One runner set is alive on 3.15.33; a…" | pre-release | flows |  |
| 166 | "The config carries job_user at audit, transports ["file"],…" | pre-release | flows |  |
| 167 | "The box was rebooted through the Hetzner API…" | pre-release | flows |  |
| 168 | "One finding in the reboot itself: the API's…" | pre-release | flows |  |
| 169 | "The API's reset action (665281851081072) did reboot it:…" | pre-release | flows |  |
| 170 | "A soft reboot through the API is not…" | pre-release | flows |  |
| 171 | "The HomingPigeon task auto-started on its boot trigger…" | pre-release | flows |  |
| 172 | "The grow task auto-started the same way." | pre-release | flows |  |
| 173 | "An addressed clock job sent after the reboot…" | pre-release | flows |  |
| 174 | "The file transport refused the envelope once on…" | pre-release | flows |  |
| 175 | "With this run the twelve-scenario Windows queue is…" | pre-release | flows |  |
| 176 | "The `job_user` divergence on Windows (see the enforcement…" | pre-release | flows |  |
| 177 | "The Windows remote-upgrade applier: installed and proven live…" | pre-release | flows |  |
| 178 | "The two kit defects it exposed — the…" | pre-release | flows |  |
| 179 | "Windows scenario runs: complete — all twelve items…" | pre-release | flows |  |
| 180 | "San Francisco is not retired: the droplet is…" | pre-release | flows |  |
| 181 | "This section was appended on the Germany rig…" | pre-release | flows |  |
| 182 | "The commit carrying this text is that commit." | pre-release | flows |  |
| 183 | "The job brought its own portable git, per…" | pre-release | flows |  |
