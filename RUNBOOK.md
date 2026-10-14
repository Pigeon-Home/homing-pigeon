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
4. Click **Choose a tag**, then type `v1.0.0` and click
   **Create new tag: v1.0.0**.
5. Type a title like `Version 1.0.0`.
6. Click the big green **Publish release** button.
7. Now click the **Actions** tab at the top. You will see the robots
   working. It takes about 10 minutes.
8. When they finish, go back to **Releases**. Your version is there
   with files to download:
   - `homing-pigeon-windows-x86_64.zip` — for Windows computers
   - `homing-pigeon-linux-x86_64.tar.gz` — for Linux computers
   - `homing-pigeon-macos-arm64.tar.gz` — for Mac computers

For the next version, do the same thing with `v1.2.1`, then `v1.2.2`,
and so on. Bigger number = newer.

After the robots finish, the Python packages go to PyPI too: the
release engineer builds the wheel and sdist (`python -m build`) and
uploads them (`twine upload`), so `pip install pigeon-home` gets the
new version. (The project page is
https://pypi.org/project/pigeon-home/.)

---

## Job 5: Put the runner on a computer

This is the computer that will do the work (your home machine, an
office machine, or a virtual machine — see the README for why a
virtual machine is a good idea).

1. Download the right file from **Releases** (see Job 4).
2. Unzip it. (Double-click it. That is unzipping.)
3. You will see three things: `homing-pigeon`, `install`, and
   `config.example.json`.
4. Make a copy of `config.example.json` and name the copy
   `config.json`. (Copy, paste, rename.)
5. Open `config.json` in Notepad (Windows) or TextEdit (Mac).
   Fill in these two lines:
   - `mailbox_user` — the Gmail address you made just for the runner.
   - `mailbox_password` — the app password for that Gmail account.
   
   How to get an app password:
   1. Log into the runner's Gmail account.
   2. Go to **myaccount.google.com** → **Security**.
   3. Turn on **2-Step Verification** (Google makes you do this first).
   4. Go back to Security, click **App passwords**.
   5. Make one, copy the code it gives you. That code goes in
      `mailbox_password`.
   
   Save the file and close it.
6. Run the installer:
   - Windows: double-click `install.exe`.
   - Mac/Linux: open the black box in this folder, type `./install`,
     press Enter.
7. Done. The runner now starts by itself every time the computer
   turns on. It checks the mailbox for jobs again and again.

To test it once without installing, type this in the black box:

```
./homing-pigeon --config config.json --once
```

It checks the mailbox one time and then stops. Watch what it prints.

---

## Job 6: Send a job to the runner

You need two things: the **secret string** (it is the same as the app
password from Job 5) and a way to send email as the runner's Gmail
account. The easiest way is to just paste the secret string to your
SI in chat and tell it what you want done — it writes the email,
signs it, and sends it for you.

If you want to do it by hand with the helper script:

1. Open the black box inside the project folder (see Job 2).
2. To say hello (a ping), type this, press Enter:

```
python3 cloud/send_job.py new --kind ping --secret PASTE_YOUR_SECRET_HERE
```

3. It prints three things: a subject line, an empty line, and a big
   block of text. Copy **all** of it.
4. Open Gmail, logged in as the runner's account. Write a new email:
   - **To:** the runner's own Gmail address.
   - **Subject:** paste the subject line.
   - **Body:** paste the big block of text.
   - Send it.
5. Within a minute or two, a reply email arrives with the result.
   For a ping, the result says `pong`.

To run a script instead of a ping:

```
python3 cloud/send_job.py new --kind exec --script-file myscript.sh --interpreter '["bash"]' --secret PASTE_YOUR_SECRET_HERE
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
project: https://github.com/Pigeon-Home/homing-pigeon
Use my email connector to send emails.
Send emails to YOUR_RUNNER_EMAIL@gmail.com
The shared secret for authentication in the protocol is "YOUR_SECRET_STRING"
Do a test routine to see if this all works, execute a runbook with the job of displaying the value of the system clock and show me the value here.
```

If it replies with the correct date and time from the runner's
machine, it passed. If nothing comes back, the SI failed somewhere:
wrong signature, wrong subject, wrong address. The clock does not
lie.

---

## If something goes wrong

- **"command not found"** — you are probably not in the project
  folder. Type `cd homing-pigeon` and try again.
- **Push asks for a password forever** — see Job 3, Step 3. Use a
  token, not your real password.
- **The runner says "bad signature"** — the secret string has a typo.
  Copy it again, carefully.
- **Nothing happens after sending a job email** — check that the
  runner computer is turned on, and that the email was sent from
  the runner's own Gmail address (not your personal one).
- **The robots (Actions) show a red X** — click the X, click the
  failed job, read the red text at the bottom. It usually says
  exactly what went wrong.
