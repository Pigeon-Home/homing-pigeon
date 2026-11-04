# Homing Pigeon Runbook

This book explains every job in tiny steps. You do not need to know
anything. Just read one step, do it, then read the next step.

Words you will see:
- **Terminal** — the black box where you type commands. On Mac it's
  called Terminal. On Windows it's called PowerShell. On Linux it's
  called Terminal.
- **Command** — one line of text you type into the black box.
- **Press Enter** — push the big Enter key after typing a command.

---

## Job 1: Put the tools on your computer (do this one time)

You need a tool called **git**. It carries code back and forth.

1. Open your web browser.
2. Go to **git-scm.com**.
3. Click the big **Download** button.
4. Open the file it downloads.
5. Keep clicking **Next** until it is done. The normal choices are fine.

To check it worked: open the black box, type `git --version`,
press Enter. If it prints a version number, you did it.

---

## Job 2: Copy the project onto your computer (do this one time)

1. Open the black box.
2. Type this exactly, then press Enter:

```
git clone https://github.com/Pigeon-Home/homing-pigeon.git
```

3. Wait until it finishes. It makes a new folder called
   `homing-pigeon`.
4. Type this, then press Enter:

```
cd homing-pigeon
```

You are now standing inside the project folder. Every command below
assumes you are here.

---

## Job 3: Send your changes up to GitHub

Do this whenever you change files and want GitHub to have them.

**Step 1 — put your changes in a box.** Type this, press Enter:

```
git add -A
```

Nothing much prints. That is normal.

**Step 2 — write a label for the box.** Type this, press Enter.
Change the words inside the quotes to say what you did:

```
git commit -m "describe what you changed"
```

Example: `git commit -m "fixed a typo in the readme"`.

**Step 3 — mail the box to GitHub.** Type this, press Enter:

```
git push
```

The first time, it asks for a username and password.
- Username: your GitHub username.
- Password: **not** your real password. GitHub wants a special
  token instead. Here is how to make one:
  1. Go to **github.com** and log in.
  2. Click your picture (top right) → **Settings**.
  3. Scroll all the way down, click **Developer settings**.
  4. Click **Personal access tokens** → **Tokens (classic)**.
  5. Click **Generate new token** → **Generate new token (classic)**.
  6. Give it a name like `my-laptop`. Check the box called **repo**.
  7. Scroll down, click **Generate token**.
  8. Copy the long code it shows you. **Copy it now** — you will
     never see it again.
  9. Paste that code as the password.

Your computer remembers it after the first time.

---

## Job 4: Make the robots build the install files

GitHub has robots that build the Windows/Mac/Linux install files for
you. You start them by making a **release**. All point and click:

1. Go to **github.com/Pigeon-Home/homing-pigeon**.
2. On the right side, click **Releases**.
3. Click the **Draft a new release** button.
4. Click **Choose a tag**, then type the tag you are cutting, such as
   `vX.Y.Z`, and click **Create new tag**.
5. Type a title like `Version X.Y.Z`. The number is the one in
   `pyproject.toml`, not a guess.
6. Click the big green **Publish release** button.
7. Now click the **Actions** tab at the top. You will see the robots
   working. It typically takes about 20 minutes.
8. When they finish, go back to **Releases**. Your version is there
   with files to download (each file and folder name carries that
   same number):
   - `homing-pigeon-windows-x86_64-<version>.zip` and `-windows-arm64-` — for Windows computers
   - `homing-pigeon-linux-x86_64-<version>.tar.gz` and `-linux-arm64-` — for Linux computers
   - `homing-pigeon-macos-arm64-<version>.tar.gz` and `-macos-x86_64-` — for Mac computers
   - `homing-pigeon-pi-light-arm64-<version>.tar.gz` — for Raspberry Pi (Pi Light)

   The release also carries the Python wheel and source
   distribution, `SHA384SUMS`, the SBOM, the build-provenance
   record, and `homing-pigeon-project-<version>.tar.gz` -- the
   whole project (every file, the full history, and this build's
   CI facts and test results). Every install archive above carries
   the same snapshot as its `project/` folder.

The next release uses the next number. Bigger number = newer.
Do not reuse a tag that already exists.

**From a terminal instead of clicking:** with the version already
bumped on main and its build green, `gh workflow run cut-release.yml`
does steps 3 through 6 for you. It tags `v<version>` on the head of
main (or on `-f sha=<commit>`), refuses if the tag exists, the
version carriers disagree, or any build job on that commit is not
green, then starts the same pipeline a tag push would. Watch the
Actions tab as in step 7.

After the robots finish, the Python packages go to PyPI automatically:
the release workflow publishes them via trusted publishing (no tokens),
so `pip install pigeon-home-runner` gets the new version. (The project
page is https://pypi.org/project/pigeon-home-runner/.)

The Docker image goes up automatically too: every version tag builds
and pushes `ghcr.io/pigeon-home/homing-pigeon` with the version tag
and `latest`. You can also trigger a manual build from the Actions tab
("Publish Docker image") any time.

Every release also carries its own proof: a `SHA384SUMS` over all
the files, a build attestation tying the set to the tag build, an
SBOM, and a `BUILD-PROVENANCE.json` stamped inside each archive.
To check a download against all of it, on any outlet, see
`docs/security/verification.md`.

**Releasing through your SI instead:** say "tag and publish
everything." That one sentence is the whole instruction set. The SI
bumps the version in the four places it lives, runs the version
test and the doc-drift guard before pushing, waits until the nine
guard jobs on that commit are green (`test` and the eight
`build-*` jobs; `test-macos` is not one of them), and tags that
commit as soon as they are. A later commit on main is not that
commit; the tag is the full sha. It watches the tag build through
`release`, `pypi-publish`, `sourceforge` and `gitlab`. Mutation
does not run on a tag. The image workflow still starts when the
tag is cut, before that build finishes. A version whose tests
fail can already have an image (`v3.14.45`). Holding the image
until `release` succeeds is not done yet. It then checks every
outlet by name -- GitHub Release, PyPI, Docker, SourceForge,
GitLab -- before reporting. You get one report when all of it
is confirmed, or one report naming the exact outlet that failed.

---

## Job 5: Put the runner on a computer

This is the computer that will do the work (your home machine, an
office machine, or a virtual machine — see the README for why a
virtual machine is a good idea).

1. Download the right file from **Releases** (see Job 4).
2. Unzip it. (Double-click it. That is unzipping.)
3. Three things in it matter: `homing-pigeon`, `install`, and
   `config.example.json` (on Windows the first two names end
   in `.exe`).
4. Make a copy of `config.example.json` and name the copy
   `config.json`. (Copy, paste, rename.)
5. Open `config.json` in Notepad (Windows) or TextEdit (Mac).
   Fill in these lines:
   - `mailbox_user` — the email address you made just for the runner.
   - `mailbox_password` — the app password for that account.
   - `shared_secret` — a long random string (generate one: `openssl rand -hex 32`).
     This is the HMAC signing key, separate from the mailbox password. You'll
     paste the same string to your SI when you want it to send jobs.

   How to get an app password:
   1. Log into the runner's mail account.
   2. Go to **myaccount.google.com** → **Security**.
   3. Turn on **2-Step Verification** (Google makes you do this first).
   4. Go back to Security, click **App passwords**.
   5. Make one, copy the code it gives you. That code goes in
      `mailbox_password`.
   
   Save the file and close it.
6. Run the installer:
   - Windows: right-click `install.exe` and run it as
     administrator. (A plain double-click is refused: creating
     `C:\homing-pigeon` needs elevation.)
   - Mac/Linux: open the black box in this folder, type `./install`,
     press Enter.
7. Done. The runner now starts by itself every time the computer
   turns on. It checks the mailbox for jobs again and again.

On Windows, the installer keeps everything in one place:
`C:\homing-pigeon` — the programs (`bin/`), the settings
(`config.json`), the memory of past jobs (`state/`), and a receipt
saying what version is installed. Five things to remember, all run
from `C:\homing-pigeon\bin`:
- `install.exe --check` — the doctor. It looks at the whole install
  and tells you in plain words what is wrong, if anything.
- `install.exe --console` — stops the background runner and runs it
  in your window instead, so you can watch what it does live. When
  you stop it (Ctrl+C), the background runner starts again by itself.
- `install.exe --oracle` — opens the chat with the Oracle.
- `install.exe --logs` — shows the end of the runner's log.
  Add `--follow` to keep watching it live.
- `install.exe --wipe` — the big red button. Copies everything into
  one backup file first, then removes the lot.

To test it once without installing, type this in the black box:

```
./homing-pigeon --config config.json --once
```

It checks the mailbox one time and then stops. Watch what it prints.

---

## Job 6: Send a job to the runner

You need two things: the **shared secret** (the `shared_secret` string
from `config.json` in Job 5 — not the app password) and a way to send
email to the runner's mailbox. The easiest way is to paste
the secret string to your SI in chat and tell it what you want done —
it writes the email, signs it, and sends it for you.

If you want to do it by hand with the helper script:

1. Open the black box inside the project folder (see Job 2).
2. To say hello (a ping), type this, press Enter:

```
python3 runner/cloud/send_job.py new --kind ping --secret PASTE_YOUR_SECRET_HERE
```

3. It prints three things: a subject line, an empty line, and a big
   block of text. Copy **all** of it.
4. Open the runner's mailbox (webmail or a mail app), logged in as the
   runner's account. Write a new email:
   - **To:** the runner's own email address.
   - **Subject:** paste the subject line.
   - **Body:** paste the big block of text.
   - Send it.
5. Typically within a minute or two, a reply email arrives with the
   result — the wait rides on the runner's poll interval and your
   mail provider's delivery time.
   For a ping, the result says `pong` — once decrypted. Jobs and
   results are encrypted by default, so the reply shows an
   envelope, not the word; read it with
   `python3 runner/cloud/send_job.py verify --secret <the-string> --job-id <id> result.txt`.

If this SI has its own key (see INSTALL.md step 6), add
`--key-id <its-id>` and sign with that key's secret instead of
`shared_secret`.

To run a script instead of a ping:

```
python3 runner/cloud/send_job.py new --kind exec --script-file myscript.sh --interpreter '["bash"]' --secret PASTE_YOUR_SECRET_HERE
```

Same steps: copy what it prints, paste into an email, send.

---

## Job 7: Test a new cloud SI with the clock check

When a new SI comes out and you want to know if it can actually
*operate* the runner (not just talk about it), give it this prompt.
If it can read the clock, the whole chain works: the SI read the
protocol, signed a valid job, sent it, and read the result.

Copy this, fill in your own email and secret, and paste it to the
new SI:

```
Send an email to YOUR_RUNNER_EMAIL
Use this protocol: https://github.com/Pigeon-Home/homing-pigeon/blob/main/PROTOCOL.md
The shared secret for authentication in the protocol is "YOUR_SECRET_STRING"
Execute a job which obtains the value of the system clock and show me the value here.
```

All items in one prompt, as it contains a shared secret. A follow-up
prompt, or a long runbook the SI iterates over, may be a new context.
So doing it this way can make it go faster, depending on cloud SI.

If it replies with the correct date and time from the runner's
machine, it passed. If nothing comes back, the SI failed somewhere:
wrong signature, wrong subject, wrong address. The clock does not
lie.

### Run that same clock check with the full output

The job runs as the runner's user and the full stdout comes back.
There is no narrower result view, no judge, and no local model.
The message is `"v": 1`. Leave the result policy off.

A current install does not start that way. `install.py` applies the
`password-only` profile unless you pass `--no-profile`. That profile
sets `max_result_view` to `attested` and `judge` to `advisory`, so
the clock string never comes back. A Raspberry Pi gets
`pi-light`, which does the same and pulls no model at all — its
Oracle runs deterministically.

Install, or re-apply, like this:

```
python3 runner/ops/install.py --no-profile --no-inference
```

On a config that already exists, set these keys. Leave the mailbox
and `shared_secret` alone.

```json
{
  "max_result_view": "full",
  "judge": "off",
  "workspace_root": "",
  "owner_instructions": "",
  "inference": {"endpoint": "", "model": ""},
  "dri": {"enabled": false},
  "resources": {"enabled": false}
}
```

Also leave every `security.modes` value at `off`, leave `sensors`
disabled, and do not start the runner with `--oracle`.

The clock job itself must be a normal exec: `"v": 1`, `"type":
"job"`, `"kind": "exec"`, a script that prints the date, and no
`result_policy`, no `queries`, and no `key_id`. Omit `interpreter`
unless you know the machine. Windows prints the clock with
`Get-Date`. Everywhere else, `date` is enough.

What you still get, because the Oracle code is unconditional: the
result carries `view` (`full`) and `output_digest`, and it may carry
a `review` note. Those fields do not hide `stdout`. With the keys
above, `stdout` is the clock, the job is not blocked, nothing is
paged, and no model is called. There is no flag that deletes the Oracle.

---

## If something goes wrong

- **"command not found"** — you are probably not in the project
  folder. Type `cd homing-pigeon` and try again.
- **Push asks for a password forever** — see Job 3, Step 3. Use a
  token, not your real password.
- **The runner says "bad signature"** — the secret string has a typo.
  Copy it again, carefully.
- **Nothing happens after sending a job message** — check that the
  runner computer is turned on, and that the job was signed with the
  right secret. Any sender address works (the address is never
  checked; the signature and the runner's own admission checks
  are); a "bad signature" rejection means the secret didn't match.
- **The robots (Actions) show a red X** — click the X, click the
  failed job, read the red text at the bottom. It usually says
  exactly what went wrong.

### Platform notes for scripts (especially clock / hello-world tests)

- **Do not force `["sh"]` or `["bash"]` on Windows.** At the default `repair` latitude the runner swaps in the platform default when the script's shape fits it and says so in the result's `oracle_opinion`; below `repair`, under `oracle_opinion_repair: refuse`, or for a bash-shaped script it rejects the job with `cannot start interpreter: [WinError 2] The system cannot find the file specified`. Either way you did not get what you asked for.
- Prefer **omitting `--interpreter`** so the runner uses its platform default: PowerShell on Windows, `sh` elsewhere. For a simple clock check on Windows use a script that contains `Get-Date` (or `date` if you know the default shell supports it).
- If you must specify an interpreter, use one that exists on the target machine (e.g. `["powershell", "-File"]` or `["pwsh", "-File"]` on Windows).
- A shared test job must not require a marker or binary that only one platform has.

### What a live run looks like

Real log lines, envelopes, and posture output from a running
system are in [live-examples.md](live-examples.md), with what
19,227 jobs on a test box came to. The capture itself
(scrubbed) is `docs/reports/live-2026-10-25/`; read it with
`python3 runner/tools/live_capture.py`.

### Where results go

Result emails are sent **to the runner's own mailbox** (the account in `mailbox_user`) — unless the signed job sets `reply_to`, in which case the result goes to that address instead (e.g. `send_job.py new --reply-to you@example.com`). The address must live inside the signed body; the email's `From` header is never trusted for this. They do not automatically appear in the cloud SI's connected mail account. To see them from the SI side you must either:
- set `reply_to` on the job so the result is emailed straight to you, or
- forward the result message to the connected account, or
- have the runner configured so results are delivered somewhere the SI can read, or
- check the runner's console/logs for the outbound result.

