# Hosting seat: intuitions

<!-- Agent-Stamp: 70000a51-e296-4b2c-bf5b-ba020e23eb91 -->

The hosting seat (stamp `70000a51`) wrote these for itself, at the
conductor's word, from its own failures. Each one names the failure
it came from and the check that replaces the habit that caused it.
The seat reads this file at the start of every turn that touches its
lane, and adds to it whenever a failure teaches something new.

## Reading remote answers

**1. A missing field is unknown, never empty.** `results` and `dlq`
read a 200 answer with `.get("results") or []`, so a body that lost
its list read as an empty queue and the command exited 0 on an answer
it never got. Another seat found it and fixed it (`15d243db`). The
check: in any reader of a remote answer, `or []`, `or {}` and
`.get(k, default)` are suspect. Write down what each status means
(here: 204 is empty, 200 carries the list), and treat a 200 without
the list as a failure with its own exit code.

**2. A test that pins today's behavior pins today's bugs.** The edge
tests asserted what the code did, not what the Worker contract
promises, so they passed over failure 1. The check: write the
contract first (status, body, meaning), then one test per row of it,
including the row "the body does not match the contract".

## Reporting state

**3. Re-read after every rebase before saying what changed.** A fix
to this seat's own code landed one minute before this seat told the
conductor "nothing else in my lane changed". The rebase had pulled
the fix in, and nobody read it. The check, before any status claim:
`git log --oneline <my last read>..HEAD -- runner/hosting
runner/cloud runner/transport_extensions/queues
docs/use/own-cloud.md docs/project/hosting.md`. The claim covers only
what that log shows.

**4. Say "not confirmed", never "green", when a build was cancelled.**
Builds on main are cancelled by the next push more often than they
finish. A cancelled run proves nothing. The check: name the run that
actually completed, and its sha, or say the result is not in yet.

**5. Read local state before changing it.** In the muster this seat
ran `git reset --hard origin/main` first, which would have destroyed
uncommitted work, and then reported "no uncommitted work". The check:
`git status --short` and `git log -1` first. During an emergency use
`fetch` and `rebase`, never `reset`.

## Before building

**6. Check whether it is already built.** Q105 was built twice, by the
review seat and by this seat, twelve minutes apart, in this seat's own
file. The check, before writing code for a question: `git fetch`,
read the question's newest lines and `git log origin/main -3 --
<the files it touches>`. If another seat is on it, review theirs
instead of writing a second one.

**7. A parked decision is not this seat's to decide.** Feedback on the
conductor's brainstorm was labelled "not a decision", and still fed a
post that wrote his name on a parked item. The check: on anything the
conductor parked, post facts and an opinion marked as such, and never
a line that reads as consensus or as his word.

## Portability, the three Windows reds

**8. A path in a URL goes through `Path(...).as_uri()`.** `"file://" +
os.path.join(...)` became `file://C:\...` on Windows (`a973223a`).

**9. Bytes, not text, wherever a digest or a byte count is compared.**
A test file written in text mode gets CRLF on Windows. A git checkout
with `core.autocrlf` does too (`558255e7`). Write with `newline="\n"`,
read with `"rb"`, and run git with `-c core.autocrlf=false`.

**10. A tool on PATH is found by its PATHEXT suffix on Windows.** A
fake `git` with no `.exe` is invisible there (`366ce979`).

**11. A mock can reach more than its target.** Patching `os.lstat`
for one file also broke `realpath` on macOS, where `/var` is a
symlink. Patching `os.path.realpath` broke this seat's coverage tool,
whose callback used it. The check: patch with a function that refuses
only the one path under test and passes every other call through. A
tool that runs inside other tests keeps its own references to the
functions it calls.

## Records

**12. Place a changelog line by the tag, not by the file's top
section.** Two entries landed under 3.14.4 after 3.14.4 was cut
without them. The check: `git merge-base --is-ancestor <my commit>
v<top section>`. If the commit is not in the tag, the entry goes in a
new section.
