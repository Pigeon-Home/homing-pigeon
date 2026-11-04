# Findings — docs/steady/use/use-runbook.md

Source: docs/steady/use/use-runbook.md, reviewed at main cbb52068.
Sentence units: 220. Flagged: 8. Categories: pre-release 219, post-release 1.

The code blocks the steps name are structure and are not units; each type-this step is completed by the block that follows it in the source.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This book explains every job in tiny steps." | pre-release | flows |  |
| 2 | "You do not need to know anything." | pre-release | flows |  |
| 3 | "Just read one step, do it, then read…" | pre-release | flows |  |
| 4 | "Words you will see:" | pre-release | flows |  |
| 5 | "**Terminal** — the black box where you type…" | pre-release | flows |  |
| 6 | "On Mac it's called Terminal." | pre-release | flows |  |
| 7 | "On Windows it's called PowerShell." | pre-release | flows |  |
| 8 | "On Linux it's called Terminal." | pre-release | flows |  |
| 9 | "**Command** — one line of text you type…" | pre-release | flows |  |
| 10 | "**Press Enter** — push the big Enter key…" | pre-release | flows |  |
| 11 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 12 | "You need a tool called **git**." | pre-release | flows |  |
| 13 | "It carries code back and forth." | pre-release | flows |  |
| 14 | "Open your web browser." | pre-release | flows |  |
| 15 | "Go to **git-scm.com**." | pre-release | flows |  |
| 16 | "Click the big **Download** button." | pre-release | flows |  |
| 17 | "Open the file it downloads." | pre-release | flows |  |
| 18 | "Keep clicking **Next** until it is done." | pre-release | flows |  |
| 19 | "The normal choices are fine." | pre-release | flows |  |
| 20 | "To check it worked: open the black box,…" | pre-release | flows |  |
| 21 | "If it prints a version number, you did…" | pre-release | flows |  |
| 22 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 23 | "Open the black box." | pre-release | flows |  |
| 24 | "Type this exactly, then press Enter:" | pre-release | flows |  |
| 25 | "Wait until it finishes." | pre-release | flows |  |
| 26 | "It makes a new folder called `homing-pigeon`." | pre-release | flows |  |
| 27 | "Type this, then press Enter:" | pre-release | flows |  |
| 28 | "You are now standing inside the project folder." | pre-release | flows |  |
| 29 | "Every command below assumes you are here." | pre-release | flows |  |
| 30 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 31 | "Do this whenever you change files and want…" | pre-release | flows |  |
| 32 | "**Step 1 — put your changes in a…" | pre-release | flows |  |
| 33 | "Nothing much prints." | pre-release | flows |  |
| 34 | "That is normal." | pre-release | flows |  |
| 35 | "**Step 2 — write a label for the…" | pre-release | flows |  |
| 36 | "Change the words inside the quotes to say…" | pre-release | flows |  |
| 37 | "Example: `git commit -m "fixed a typo in…" | pre-release | flows |  |
| 38 | "**Step 3 — mail the box to GitHub.**…" | pre-release | flows |  |
| 39 | "The first time, it asks for a username…" | pre-release | flows |  |
| 40 | "Username: your GitHub username." | pre-release | flows |  |
| 41 | "Password: **not** your real password." | pre-release | flows |  |
| 42 | "GitHub wants a special token instead." | pre-release | flows |  |
| 43 | "Here is how to make one:" | pre-release | flows |  |
| 44 | "Go to **github.com** and log in." | pre-release | flows |  |
| 45 | "Click your picture (top right) → **Settings**." | pre-release | flows |  |
| 46 | "Scroll all the way down, click **Developer settings**." | pre-release | flows |  |
| 47 | "Click **Personal access tokens** → **Tokens (classic)**." | pre-release | flows |  |
| 48 | "Click **Generate new token** → **Generate new token…" | pre-release | flows |  |
| 49 | "Give it a name like `my-laptop`." | pre-release | flows |  |
| 50 | "Check the box called **repo**." | pre-release | flows |  |
| 51 | "Scroll down, click **Generate token**." | pre-release | flows |  |
| 52 | "Copy the long code it shows you. **Copy…" | pre-release | flows |  |
| 53 | "Paste that code as the password." | pre-release | flows |  |
| 54 | "Your computer remembers it after the first time." | pre-release | flows |  |
| 55 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 56 | "GitHub has robots that build the Windows/Mac/Linux install…" | pre-release | flows |  |
| 57 | "You start them by making a **release**." | pre-release | flows |  |
| 58 | "All point and click:" | pre-release | flows |  |
| 59 | "Go to **github.com/Pigeon-Home/homing-pigeon**." | pre-release | flows |  |
| 60 | "On the right side, click **Releases**." | pre-release | flows |  |
| 61 | "Click the **Draft a new release** button." | pre-release | flows |  |
| 62 | "Click **Choose a tag**, then type the tag…" | pre-release | flows |  |
| 63 | "Type a title like `Version X.Y.Z`." | pre-release | flows |  |
| 64 | "The number is the one in `pyproject.toml`, not…" | pre-release | flows |  |
| 65 | "Click the big green **Publish release** button." | pre-release | flows |  |
| 66 | "Now click the **Actions** tab at the top." | pre-release | flows |  |
| 67 | "You will see the robots working." | pre-release | flows |  |
| 68 | "It typically takes about 20 minutes." | pre-release | flows |  |
| 69 | "When they finish, go back to **Releases**." | pre-release | flows |  |
| 70 | "Your version is there with files to download…" | pre-release | flows |  |
| 71 | "`homing-pigeon-windows-x86_64-.zip` and `-windows-arm64-` — for Windows computers" | pre-release | flows |  |
| 72 | "`homing-pigeon-linux-x86_64-.tar.gz` and `-linux-arm64-` — for Linux computers" | pre-release | flows |  |
| 73 | "`homing-pigeon-macos-arm64-.tar.gz` and `-macos-x86_64-` — for Mac computers" | pre-release | flows |  |
| 74 | "`homing-pigeon-pi-light-arm64-.tar.gz` — for Raspberry Pi (Pi Light)" | pre-release | flows |  |
| 75 | "The release also carries the Python wheel and…" | pre-release | flows |  |
| 76 | "Every install archive above carries the same snapshot…" | pre-release | flows |  |
| 77 | "The next release uses the next number." | pre-release | flows |  |
| 78 | "Bigger number = newer." | pre-release | flows |  |
| 79 | "Do not reuse a tag that already exists." | pre-release | flows |  |
| 80 | "**From a terminal instead of clicking:** with the…" | pre-release | flows |  |
| 81 | "It tags `v` on the head of main…" | pre-release | flows |  |
| 82 | "Watch the Actions tab as in step 7." | pre-release | flows |  |
| 83 | "After the robots finish, the Python packages go…" | pre-release | flows |  |
| 84 | "(The project page is https://pypi.org/project/pigeon-home-runner/.)" | pre-release | flows |  |
| 85 | "The Docker image goes up automatically too: every…" | pre-release | flows |  |
| 86 | "You can also trigger a manual build from…" | pre-release | flows |  |
| 87 | "Every release also carries its own proof: a…" | pre-release | flows |  |
| 88 | "To check a download against all of it,…" | pre-release | flows |  |
| 89 | "**Releasing through your SI instead:** say "tag and…" | pre-release | flows |  |
| 90 | "That one sentence is the whole instruction set." | pre-release | flows |  |
| 91 | "The SI bumps the version in the four…" | pre-release | flows |  |
| 92 | "A later commit on main is not that…" | pre-release | flows |  |
| 93 | "It watches the tag build through `release`, `pypi-publish`,…" | pre-release | flows |  |
| 94 | "Mutation does not run on a tag." | pre-release | flows |  |
| 95 | "The image workflow still starts when the tag…" | pre-release | flows |  |
| 96 | "A version whose tests fail can already have…" | pre-release | flows |  |
| 97 | "Holding the image until `release` succeeds is not…" | post-release | flows |  |
| 98 | "It then checks every outlet by name --…" | pre-release | flows |  |
| 99 | "You get one report when all of it…" | pre-release | flows |  |
| 100 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 101 | "This is the computer that will do the…" | pre-release | flows |  |
| 102 | "Download the right file from **Releases** (see Job…" | pre-release | flows |  |
| 103 | "Unzip it." | pre-release | flows |  |
| 104 | "(Double-click it." | pre-release | flows |  |
| 105 | "That is unzipping.)" | pre-release | flows |  |
| 106 | "Three things in it matter: `homing-pigeon`, `install`, and…" | pre-release | flows |  |
| 107 | "Make a copy of `config.example.json` and name the…" | pre-release | flows |  |
| 108 | "(Copy, paste, rename.)" | pre-release | flows |  |
| 109 | "Open `config.json` in Notepad (Windows) or TextEdit (Mac)." | pre-release | flows |  |
| 110 | "Fill in these lines:" | pre-release | flows |  |
| 111 | "`mailbox_user` — the email address you made just…" | pre-release | flows |  |
| 112 | "`mailbox_password` — the app password for that account." | pre-release | flows |  |
| 113 | "`shared_secret` — a long random string (generate one:…" | pre-release | flows |  |
| 114 | "This is the HMAC signing key, separate from…" | pre-release | flows |  |
| 115 | "You'll paste the same string to your SI…" | pre-release | flows |  |
| 116 | "How to get an app password:" | pre-release | flows |  |
| 117 | "Log into the runner's mail account." | pre-release | flows |  |
| 118 | "Go to **myaccount.google.com** → **Security**." | pre-release | flows |  |
| 119 | "Turn on **2-Step Verification** (Google makes you do…" | pre-release | flows |  |
| 120 | "Go back to Security, click **App passwords**." | pre-release | flows |  |
| 121 | "Make one, copy the code it gives you." | pre-release | flows |  |
| 122 | "That code goes in `mailbox_password`." | pre-release | flows |  |
| 123 | "Save the file and close it." | pre-release | flows |  |
| 124 | "Run the installer:" | pre-release | flows |  |
| 125 | "Windows: right-click `install.exe` and run it as administrator." | pre-release | flows |  |
| 126 | "(A plain double-click is refused: creating `C:\homing-pigeon` needs…" | pre-release | flows |  |
| 127 | "Mac/Linux: open the black box in this folder,…" | pre-release | flows |  |
| 128 | "Done." | pre-release | flows |  |
| 129 | "The runner now starts by itself every time…" | pre-release | flows |  |
| 130 | "It checks the mailbox for jobs again and…" | pre-release | flows |  |
| 131 | "On Windows, the installer keeps everything in one…" | pre-release | flows |  |
| 132 | "Five things to remember, all run from `C:\homing-pigeon\bin`:" | pre-release | flows |  |
| 133 | "`install.exe --check` — the doctor." | pre-release | flows |  |
| 134 | "It looks at the whole install and tells…" | pre-release | flows |  |
| 135 | "`install.exe --console` — stops the background runner and…" | pre-release | flows |  |
| 136 | "When you stop it (Ctrl+C), the background runner…" | pre-release | flows |  |
| 137 | "`install.exe --oracle` — opens the chat with the…" | pre-release | flows |  |
| 138 | "`install.exe --logs` — shows the end of the…" | pre-release | flows |  |
| 139 | "Add `--follow` to keep watching it live." | pre-release | flows |  |
| 140 | "`install.exe --wipe` — the big red button." | pre-release | flows |  |
| 141 | "Copies everything into one backup file first, then…" | pre-release | flows |  |
| 142 | "To test it once without installing, type this…" | pre-release | flows |  |
| 143 | "It checks the mailbox one time and then…" | pre-release | flows |  |
| 144 | "Watch what it prints." | pre-release | flows |  |
| 145 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 146 | "You need two things: the **shared secret** (the…" | pre-release | flows |  |
| 147 | "The easiest way is to paste the secret…" | pre-release | flows |  |
| 148 | "If you want to do it by hand…" | pre-release | flows |  |
| 149 | "Open the black box inside the project folder…" | pre-release | flows |  |
| 150 | "To say hello (a ping), type this, press…" | pre-release | flows |  |
| 151 | "It prints three things: a subject line, an…" | pre-release | flows |  |
| 152 | "Copy **all** of it." | pre-release | flows |  |
| 153 | "Open the runner's mailbox (webmail or a mail…" | pre-release | flows |  |
| 154 | "Write a new email:" | pre-release | flows |  |
| 155 | "**To:** the runner's own email address." | pre-release | flows |  |
| 156 | "**Subject:** paste the subject line." | pre-release | flows |  |
| 157 | "**Body:** paste the big block of text." | pre-release | flows |  |
| 158 | "Send it." | pre-release | flows |  |
| 159 | "Typically within a minute or two, a reply…" | pre-release | flows |  |
| 160 | "For a ping, the result says `pong` —…" | pre-release | flows |  |
| 161 | "Jobs and results are encrypted by default, so…" | pre-release | flows |  |
| 162 | "If this SI has its own key (see…" | pre-release | flows |  |
| 163 | "To run a script instead of a ping:" | pre-release | flows |  |
| 164 | "Same steps: copy what it prints, paste into…" | pre-release | flows |  |
| 165 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 166 | "When a new SI comes out and you…" | pre-release | flows |  |
| 167 | "If it can read the clock, the whole…" | pre-release | flows |  |
| 168 | "Copy this, fill in your own email and…" | pre-release | flows |  |
| 169 | "All items in one prompt, as it contains…" | pre-release | flows |  |
| 170 | "A follow-up prompt, or a long runbook the…" | pre-release | flows |  |
| 171 | "So doing it this way can make it…" | pre-release | flows |  |
| 172 | "If it replies with the correct date and…" | pre-release | flows |  |
| 173 | "If nothing comes back, the SI failed somewhere:…" | pre-release | flows |  |
| 174 | "The clock does not lie." | pre-release | flows |  |
| 175 | "The job runs as the runner's user and…" | pre-release | flows |  |
| 176 | "There is no narrower result view, no judge,…" | pre-release | flows |  |
| 177 | "The message is `"v": 1`." | pre-release | flows |  |
| 178 | "Leave the result policy off." | pre-release | flows |  |
| 179 | "A current install does not start that way.…" | pre-release | flows |  |
| 180 | "That profile sets `max_result_view` to `attested` and `judge`…" | pre-release | flows |  |
| 181 | "A Raspberry Pi gets `pi-light`, which does the…" | pre-release | flows |  |
| 182 | "Install, or re-apply, like this:" | pre-release | flows |  |
| 183 | "On a config that already exists, set these…" | pre-release | flows |  |
| 184 | "Leave the mailbox and `shared_secret` alone." | pre-release | flows |  |
| 185 | "Also leave every `security.modes` value at `off`, leave…" | pre-release | flows |  |
| 186 | "The clock job itself must be a normal…" | pre-release | flows |  |
| 187 | "Omit `interpreter` unless you know the machine." | pre-release | flows |  |
| 188 | "Windows prints the clock with `Get-Date`." | pre-release | flows |  |
| 189 | "Everywhere else, `date` is enough." | pre-release | flows |  |
| 190 | "What you still get, because the Oracle code…" | pre-release | flows |  |
| 191 | "Those fields do not hide `stdout`." | pre-release | flows |  |
| 192 | "With the keys above, `stdout` is the clock,…" | pre-release | flows |  |
| 193 | "There is no flag that deletes the Oracle." | pre-release | flows |  |
| 194 | "(horizontal rule)" | pre-release | flagged | Horizontal rule; structure, not a sentence |
| 195 | "**"command not found"** — you are probably not…" | pre-release | flows |  |
| 196 | "Type `cd homing-pigeon` and try again." | pre-release | flows |  |
| 197 | "**Push asks for a password forever** — see…" | pre-release | flows |  |
| 198 | "Use a token, not your real password." | pre-release | flows |  |
| 199 | "**The runner says "bad signature"** — the secret…" | pre-release | flows |  |
| 200 | "Copy it again, carefully." | pre-release | flows |  |
| 201 | "**Nothing happens after sending a job message** —…" | pre-release | flows |  |
| 202 | "Any sender address works (the address is never…" | pre-release | flows |  |
| 203 | "**The robots (Actions) show a red X** —…" | pre-release | flows |  |
| 204 | "It usually says exactly what went wrong." | pre-release | flows |  |
| 205 | "**Do not force `["sh"]` or `["bash"]` on Windows.**…" | pre-release | flows |  |
| 206 | "Either way you did not get what you…" | pre-release | flows |  |
| 207 | "Prefer **omitting `--interpreter`** so the runner uses its…" | pre-release | flows |  |
| 208 | "For a simple clock check on Windows use…" | pre-release | flows |  |
| 209 | "If you must specify an interpreter, use one…" | pre-release | flows |  |
| 210 | "A shared test job must not require a…" | pre-release | flows |  |
| 211 | "Real log lines, envelopes, and posture output from…" | pre-release | flows |  |
| 212 | "The capture itself (scrubbed) is `docs/reports/live-2026-10-25/`; read it…" | pre-release | flows |  |
| 213 | "Result emails are sent **to the runner's own…" | pre-release | flows |  |
| 214 | "The address must live inside the signed body;…" | pre-release | flows |  |
| 215 | "They do not automatically appear in the cloud…" | pre-release | flows |  |
| 216 | "To see them from the SI side you…" | pre-release | flows |  |
| 217 | "set `reply_to` on the job so the result…" | pre-release | flows |  |
| 218 | "forward the result message to the connected account,…" | pre-release | flows |  |
| 219 | "have the runner configured so results are delivered…" | pre-release | flows |  |
| 220 | "check the runner's console/logs for the outbound result." | pre-release | flows |  |
