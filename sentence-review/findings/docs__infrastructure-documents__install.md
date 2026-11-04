# Findings — docs/infrastructure-documents/install.md

Source: docs/infrastructure-documents/install.md, reviewed at main 10600981.
Sentence units: 190. Flagged: 3. Categories: pre-release 190, post-release 0.

The install guide: 3 ways simplest first, each in install and run phases, then the Pi Light profile, the television families, the per-OS archives, the setup wizard, from-source steps, the platform table, VM advice, and the first-run scenario. The bolded phase labels are the scaffolding; where a label carries its instruction clause it flows as a step header, and the 2 labels standing entirely alone (units 5 and 12) are flagged. One wizard parenthesis is split across units 148 and 149 and reads as 1 sentence. The platform table's data rows are counted as units and flow as records under its header row (unit 153).

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Three ways, simplest first." | pre-release | flows |  |
| 2 | "Each has two phases: **install** (get the files…" | pre-release | flows |  |
| 3 | "Don't mix them." | pre-release | flows |  |
| 4 | "**Install:** pull the image." | pre-release | flows |  |
| 5 | "**Run:**" | pre-release | flagged | A bare phase label standing alone; the phase's sentences follow it |
| 6 | "No Python, no git, nothing else." | pre-release | flows |  |
| 7 | "See [DOCKER.md](docs/archive/DOCKER.md) for dry-run mode, config options, and…" | pre-release | flows |  |
| 8 | "The runner needs Python 3.9 or newer (`requires-python`…" | pre-release | flows |  |
| 9 | "openSUSE Leap 15 and RHEL/AlmaLinux/Rocky 8 ship a…" | pre-release | flows |  |
| 10 | "Rocky/Alma 9, Debian 11+, Ubuntu 22.04+, Fedora, Amazon…" | pre-release | flows |  |
| 11 | "The platform matrix runs the proof on openSUSE…" | pre-release | flows |  |
| 12 | "**Install:**" | pre-release | flagged | A bare phase label standing alone; the phase's sentences follow it |
| 13 | "On RHEL, CentOS, Rocky, or AlmaLinux, install Python…" | pre-release | flows |  |
| 14 | "On Debian and Ubuntu, install Python 3.9+ first:" | pre-release | flows |  |
| 15 | "**Run:** register the boot service, configure, test." | pre-release | flows |  |
| 16 | "A Pi install — detected automatically from the…" | pre-release | flows |  |
| 17 | "You get the full runner and the full…" | pre-release | flows |  |
| 18 | "What the Pi does **not** get is a…" | pre-release | flows |  |
| 19 | "The installer installs no Ollama and downloads no…" | pre-release | flows |  |
| 20 | "The Oracle runs in deterministic mode (`oracle_mode: "deterministic"`…" | pre-release | flows |  |
| 21 | "The diagnosis is the deterministic kind: what ran,…" | pre-release | flows |  |
| 22 | "When Pis ship with neural accelerator chips worth…" | pre-release | flows |  |
| 23 | "Nothing reinstalls and nothing else changes." | pre-release | flows |  |
| 24 | "A USB accelerator (Coral, Intel NCS, Hailo) is…" | pre-release | flows |  |
| 25 | "Seeing one does not change the install." | pre-release | flows |  |
| 26 | "The installer says so and still installs no…" | pre-release | flows |  |
| 27 | "The Pi archive and the Docker image are…" | pre-release | flows |  |
| 28 | "A television is not." | pre-release | flows |  |
| 29 | "The installer refuses these, and does not copy…" | pre-release | flows |  |
| 30 | "Samsung Tizen, LG webOS, Roku, Apple TV" | pre-release | flows |  |
| 31 | "a USB accelerator with no Linux host under…" | pre-release | flows |  |
| 32 | "any environment that cannot execute a shell" | pre-release | flows |  |
| 33 | "Android -- Android TV, Google TV, Fire TV,…" | pre-release | flows |  |
| 34 | "There the installer proceeds and states the limits…" | pre-release | flows |  |
| 35 | "Pass `--profile display-board` so no model is installed;…" | pre-release | flows |  |
| 36 | "An Android environment with no shell (a signed…" | pre-release | flows |  |
| 37 | "Code signing can put an app on the…" | pre-release | flows |  |
| 38 | "It cannot give this program a shell, and…" | pre-release | flows |  |
| 39 | "The repair proofs (Alpine with no bash, the…" | pre-release | flows |  |
| 40 | "A Linux board behind the television is a…" | pre-release | flows |  |
| 41 | "If the board is dedicated and the screen…" | pre-release | flows |  |
| 42 | "That is Pi Light's stance — full runner,…" | pre-release | flows |  |
| 43 | "Docker is the published Linux image, not a…" | pre-release | flows |  |
| 44 | "**Install:** download and extract." | pre-release | flows |  |
| 45 | "Every default OS ships a downloader — no…" | pre-release | flows |  |
| 46 | "Release file names carry the version (for example…" | pre-release | flows |  |
| 47 | "Linux (curl is always there):" | pre-release | flows |  |
| 48 | "Raspberry Pi (Pi Light — its own archive,…" | pre-release | flows |  |
| 49 | "Then run `install` in the folder." | pre-release | flows |  |
| 50 | "The archive carries a `default_profile` marker naming `pi-light`,…" | pre-release | flows |  |
| 51 | "The other archives carry no marker and keep…" | pre-release | flows |  |
| 52 | "macOS (same):" | pre-release | flows |  |
| 53 | "Windows 11 (PowerShell has Invoke-WebRequest built in):" | pre-release | flows |  |
| 54 | "**Run:** start the service." | pre-release | flows |  |
| 55 | "**Windows:** run `install.exe` from an elevated PowerShell." | pre-release | flows |  |
| 56 | "It creates the one home at `C:\homing-pigeon` —…" | pre-release | flows |  |
| 57 | "By default the task runs as SYSTEM; for…" | pre-release | flows |  |
| 58 | "A named account runs at `LIMITED` run level…" | pre-release | flows |  |
| 59 | "The service, `install.exe --console`, and `--oracle` all use…" | pre-release | flows |  |
| 60 | "Re-running `install.exe` is safe: it upgrades the binaries…" | pre-release | flows |  |
| 61 | "Six commands to learn (from `C:\homing-pigeon\bin`): `install.exe --check`…" | pre-release | flows |  |
| 62 | "The less common flags: `--home DIR` picks a…" | pre-release | flows |  |
| 63 | "**Linux:** run `./install` — registers a systemd service." | pre-release | flows |  |
| 64 | "**macOS:** run `./install` — registers a launchd agent." | pre-release | flows |  |
| 65 | "Then sign in: run the app once with…" | pre-release | flows |  |
| 66 | "No hand-edited JSON needed." | pre-release | flows |  |
| 67 | "If you'd rather wire it by hand, edit…" | pre-release | flows |  |
| 68 | "The installer also sets up the Oracle's local…" | pre-release | flows |  |
| 69 | "If that step doesn't finish (it downloads a…" | pre-release | flows |  |
| 70 | "Pass `--no-inference` to skip it entirely." | pre-release | flows |  |
| 71 | "By default the installer also sets up local…" | pre-release | flows |  |
| 72 | "A Raspberry Pi install, detected automatically or selected…" | pre-release | flows |  |
| 73 | "`--faster` pulls `qwen2.5:3b`, a faster model, on any…" | pre-release | flows |  |
| 74 | "Pass `--inference-model` to choose a tag yourself, or…" | pre-release | flows |  |
| 75 | "The runner itself never bundles the model; Ollama…" | pre-release | flows |  |
| 76 | "`homing-pigeon --faster` uses `qwen2.5:3b` for that process only…" | pre-release | flows |  |
| 77 | "**Easiest: download a release.** No Python needed —…" | pre-release | flows |  |
| 78 | "The common computer that does not ship with…" | pre-release | flows |  |
| 79 | "Download the Windows zip." | pre-release | flows |  |
| 80 | "Do not install Python." | pre-release | flows |  |
| 81 | "`homing-pigeon.exe` carries its own interpreter, and so do…" | pre-release | flows |  |
| 82 | "The release build proves the drop: the Linux…" | pre-release | flows |  |
| 83 | "Platform \| Download" | pre-release | flows |  |
| 84 | "Windows (x64) \| `homing-pigeon-windows-x86_64-<version>.zip` → `homing-pigeon.exe` + `install.exe`" | pre-release | flows |  |
| 85 | "Windows (ARM64) \| `homing-pigeon-windows-arm64-<version>.zip` → `homing-pigeon.exe` + `install.exe`" | pre-release | flows |  |
| 86 | "Linux (x64, Debian/RHEL/Ubuntu/…) \| `homing-pigeon-linux-x86_64-<version>.tar.gz` → `homing-pigeon` +…" | pre-release | flows |  |
| 87 | "Linux (ARM64, a board that is not asking…" | pre-release | flows |  |
| 88 | "macOS (ARM64) \| `homing-pigeon-macos-arm64-<version>.tar.gz` → `homing-pigeon` + `install`" | pre-release | flows |  |
| 89 | "macOS (Intel) \| `homing-pigeon-macos-x86_64-<version>.tar.gz` → `homing-pigeon` + `install`" | pre-release | flows |  |
| 90 | "Raspberry Pi (ARM64, Pi Light) \| `homing-pigeon-pi-light-arm64-<version>.tar.gz` →…" | pre-release | flows |  |
| 91 | "Every archive carries the version in its file…" | pre-release | flows |  |
| 92 | "`homing-pigeon --version` (or `install --version`) reports the build's…" | pre-release | flows |  |
| 93 | "The Linux binary is built on ubuntu-22.04 (glibc…" | pre-release | flows |  |
| 94 | "It runs on Ubuntu 22.04+, recent Debian, and…" | pre-release | flows |  |
| 95 | "We don't ship binaries for older systems (Debian…" | pre-release | flows |  |
| 96 | "The frozen binaries are built on the architecture…" | pre-release | flows |  |
| 97 | "PyInstaller freezes the interpreter it was built with,…" | pre-release | flows |  |
| 98 | "x86_64 and ARM64 are the ones with a…" | pre-release | flows |  |
| 99 | "The other architectures in the platform matrix (armv7,…" | pre-release | flows |  |
| 100 | "A television still does not." | pre-release | flows |  |
| 101 | "Tizen, webOS, Roku, and Apple TV cannot exec…" | pre-release | flows |  |
| 102 | "The computer behind that screen, if it is…" | pre-release | flows |  |
| 103 | "Extract the archive on the target machine." | pre-release | flows |  |
| 104 | "Beside the binaries is `project/`: the whole Homing…" | pre-release | flows |  |
| 105 | "`project/PROJECT-SNAPSHOT.md` is its index." | pre-release | flows |  |
| 106 | "The installer copies it into the state dir,…" | pre-release | flows |  |
| 107 | "Run `install` (or `install.exe` on Windows, from an…" | pre-release | flows |  |
| 108 | "It copies the runner binary, registers the boot-start…" | pre-release | flows |  |
| 109 | "Sign-in is the next step." | pre-release | flows |  |
| 110 | "On Windows everything lives in one home, `C:\homing-pigeon`…" | pre-release | flows |  |
| 111 | "The day-to-day commands live there too: `install.exe --check`…" | pre-release | flows |  |
| 112 | "Run the Thunderbird-style setup against the installed config:…" | pre-release | flows |  |
| 113 | "Browser sign-in, a fresh shared secret shown once…" | pre-release | flows |  |
| 114 | "On an existing config `--setup` offers re-login and…" | pre-release | flows |  |
| 115 | "Prefer to wire it by hand?" | pre-release | flows |  |
| 116 | "Edit `config.json` instead." | pre-release | flows |  |
| 117 | "Two ways to sign in:" | pre-release | flows |  |
| 118 | "**Password** (default): `mailbox_user` + `mailbox_password` (the mailbox's app…" | pre-release | flows |  |
| 119 | "The HMAC shared secret is a separate `shared_secret`…" | pre-release | flows |  |
| 120 | "**Browser, like Thunderbird**: no Google password anywhere." | pre-release | flows |  |
| 121 | "Create a Desktop OAuth client in [Google Cloud…" | pre-release | flows |  |
| 122 | "Add `http://127.0.0.1:8765/` as a redirect URI on the…" | pre-release | flows |  |
| 123 | "Then run `homing-pigeon --setup --config <config.json>` (pip installs…" | pre-release | flows |  |
| 124 | "IMAP and SMTP then use XOAUTH2." | pre-release | flows |  |
| 125 | "Tested end to end on Windows 11." | pre-release | flows |  |
| 126 | "One gotcha: in the Cloud Console, set the…" | pre-release | flows |  |
| 127 | "Left in "Testing", Google expires the refresh token…" | pre-release | flows |  |
| 128 | "No verification needed — the app stays unverified…" | pre-release | flows |  |
| 129 | "When you want an SI to send jobs,…" | pre-release | flows |  |
| 130 | "Every secret has a name, its key id…" | pre-release | flows |  |
| 131 | "Hand the SI both; it keeps them together…" | pre-release | flows |  |
| 132 | "Want a readable name as well?" | pre-release | flows |  |
| 133 | "`--key-id prod-1` on a fresh install stores it…" | pre-release | flows |  |
| 134 | "The name is public and safe to share…" | pre-release | flows |  |
| 135 | "The installer also prints a **panic word**, six…" | pre-release | flows |  |
| 136 | "A message to the runner's mailbox with the…" | pre-release | flows |  |
| 137 | "An install from before the word existed arms…" | pre-release | flows |  |
| 138 | "**More than one signer?** Give each its own…" | pre-release | flows |  |
| 139 | "The signer then passes `--key-id grok-4` to `send_job.py`." | pre-release | flows |  |
| 140 | "The secret the installer generates for you is…" | pre-release | flows |  |
| 141 | "Rotation and the policy details: `docs/use/secret-rotation.md`, PROTOCOL.md section…" | pre-release | flows |  |
| 142 | "**From source** (needs Python 3.9+):" | pre-release | flows |  |
| 143 | "Create a **dedicated** mail account for the runner,…" | pre-release | flows |  |
| 144 | "Never use a personal inbox." | pre-release | flows |  |
| 145 | "Enable two-step verification on the account, then create…" | pre-release | flows |  |
| 146 | "Copy `runner/` to the target machine." | pre-release | flows |  |
| 147 | "Copy `config.example.json` to `config.json` and fill in `mailbox_user`…" | pre-release | flows |  |
| 148 | "Replace the `shared_secret` placeholder with a generated secret…" | pre-release | flows |  |
| 149 | "(The installer generates one into the config it…" | pre-release | flows |  |
| 150 | "Test one cycle: `python3 runner.py --config config.json --once`." | pre-release | flows |  |
| 151 | "`python3 ops/install.py --config "$PWD/config.json"` registers the boot-start service…" | pre-release | flows |  |
| 152 | "Without `--config` it installs against `~/.homing-pigeon/config.json`." | pre-release | flows |  |
| 153 | "Platform \| Mechanism \| Notes" | pre-release | flagged | Table header row, structure rather than a sentence |
| 154 | "Linux \| systemd user unit (`--system` for system-wide)…" | pre-release | flows |  |
| 155 | "macOS \| launchd agent \| `~/Library/LaunchAgents/com.homing-pigeon.runner.plist`" | pre-release | flows |  |
| 156 | "FreeBSD \| cron `@reboot` \| simple; wrap in…" | pre-release | flows |  |
| 157 | "Windows \| Scheduled Task \| runs at startup…" | pre-release | flows |  |
| 158 | "`install.py --dir DIR` chooses the install location (default…" | pre-release | flows |  |
| 159 | "For testing — and honestly for everyday use…" | pre-release | flows |  |
| 160 | "**Snapshots beat regret.** About to hand an SI…" | pre-release | flows |  |
| 161 | "Snapshot first." | pre-release | flows |  |
| 162 | "If a job goes sideways, roll back in…" | pre-release | flows |  |
| 163 | "**Containment.** The agent only sees what the VM…" | pre-release | flows |  |
| 164 | "Your host, your files, and your other projects…" | pre-release | flows |  |
| 165 | "**Disposability.** Experiment freely: spin up a fresh VM…" | pre-release | flows |  |
| 166 | "Nothing lingers on the host." | pre-release | flows |  |
| 167 | "Any hypervisor works — KVM/QEMU, VirtualBox, Hyper-V, VMware." | pre-release | flows |  |
| 168 | "Give the VM internet access (NAT is fine)…" | pre-release | flows |  |
| 169 | "The host never needs to know." | pre-release | flows |  |
| 170 | "Checked against a working simulation (Windows-shaped profile, no…" | pre-release | flows |  |
| 171 | "The same steps are locked in `runner/tests/test_first_run_scenario.py`." | pre-release | flows |  |
| 172 | "The strings there are the ones the simulation…" | pre-release | flows |  |
| 173 | "First launch with no `config.json`, and no console,…" | pre-release | flows |  |
| 174 | "There is no traceback." | pre-release | flows |  |
| 175 | "`homing-pigeon --setup`." | pre-release | flows |  |
| 176 | "Choice `[1]` opens the browser sign-in." | pre-release | flows |  |
| 177 | "Choice `[2]` asks for an app password for…" | pre-release | flows |  |
| 178 | "Either way the written config pre-fills the recommended…" | pre-release | flows |  |
| 179 | "A failed mailbox probe prints a warning and…" | pre-release | flows |  |
| 180 | "Closing the window mid-prompt exits with "setup needs…" | pre-release | flows |  |
| 181 | "Put `flag.txt` on the Desktop." | pre-release | flows |  |
| 182 | "Tell the Oracle it is a password: `owner_instructions`,…" | pre-release | flows |  |
| 183 | "Set `max_result_view` to `redacted`." | pre-release | flows |  |
| 184 | "`homing-pigeon --config config.json --inspect redact` with the flag…" | pre-release | flows |  |
| 185 | "`--once --dry-run` exits 0." | pre-release | flows |  |
| 186 | "A dry run starts no transport extensions and…" | pre-release | flows |  |
| 187 | "Whichever path you pick, **verify** with the clock…" | pre-release | flows |  |
| 188 | "If the runner replies with the time, you're…" | pre-release | flows |  |
| 189 | "**Note:** the runner re-reads `config.json` every poll cycle…" | pre-release | flows |  |
| 190 | "Changing the mailbox credentials, the shared secret or…" | pre-release | flows |  |
