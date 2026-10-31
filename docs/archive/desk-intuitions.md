# The desk's intuitions

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->

The desk (`40000e00`) writes these for itself. Each one comes from a
thing the desk did on 27-Oct and 28-Oct that cost a seat's time or
put something wrong on `main`. Each says what happened, the check
that would have caught it, and the habit the desk keeps from now on.
The desk reads this file at the start of every turn that will push.

## Before posting

1. **Read the forum again just before you post, not just before you
   start.** On 28-Oct-7:20pm-PST/PDT the desk posted its view on the
   key directory. Four other seats had posted on the same thing in the
   minutes before, and the decision was recorded five minutes later.
   The desk read the forum at the start of the turn and wrote from
   that reading. *Habit:* pull and read the top of `.com.chat` again
   right before writing an entry. If another seat has already said
   it, the desk says nothing, or one line that points at that post.

2. **Silence is a valid answer.** "Answer everything aimed at the
   conductor" does not mean every seat posts on every topic. If the
   desk's view matches a post already on `main`, it does not post its
   own. *Check:* would the conductor lose anything if this entry were
   not written? If not, it is not written.

3. **Use the conductor's format exactly, from his own example.** NEWRULE
   gave `28-OCT 4:31PM PST`. The desk wrote `PDT` in its heading, an
   inference about daylight time that he had not asked for. The
   format since relayed is `28-Oct-7:41pm-PST/PDT`, with the zone as a
   fixed string. *Habit:* copy his example's shape character for
   character and change only the numbers. Do not correct his example.
   If his example looks wrong, ask.

4. **Claim before building.** On 27-Oct the desk built Q104 while
   `90000998` was building it. The desk's commit carried merge markers
   into `send_job.py` and had to be undone. *Habit:* before building a
   Q, read its answer lines and run `git log -S` on its key term. Then
   write `**Claimed:** 40000e00` under the Q and push before any code.

## Before committing

5. **After any pull, look for conflict markers before you stage.**
   `git pull --autostash` reported a conflict, the desk committed
   anyway, and `<<<<<<< Updated upstream` went to `main`. *Check:*
   `git grep -n '^<<<<<<< \|^>>>>>>> '` returns nothing, and
   `git stash list` is empty, before every commit.

6. **Never run a repository tool to learn how it works.** The desk ran
   `repair_script_imports.py --help`, and the tool rewrote four modules
   in place. A second run on a clean tree did the same. *Habit:* read
   a tool's docstring and its `main()`. Run it only with the flag you
   mean, and with `git diff --stat` before and after. The tool now
   refuses an argument it does not know.

7. **A number you report gets a sanity check against the last one.**
   The desk recorded "1817 tests green" when the suite is about 7,300.
   The runner's tail had dropped the summary line of half the shards.
   *Habit:* every count goes beside the previous count. A count that
   halves or doubles with no reason is a bug, not a result.

8. **A claim in the spec or the forum is verified first, not
   afterwards.** The desk wrote that a cancel stops a running job
   "when the runner runs more than one worker". The transports serve
   one message at a time whatever `workers` says, which the desk
   checked only after the text was written. It also wrote that
   "another session" had dispatched two cut runs, with no evidence.
   *Habit:* every factual sentence names the line, run or commit that
   makes it true. Where there is none, the sentence says it is not
   known.

## Writing code

9. **Wire input is ASCII until proven otherwise.** `str.isdigit()`
   takes `²` and `٣`. The desk caught this in a seat's fix but has
   written the same check before. *Habit:* use `x.isascii() and
   x.isdigit()`, or a regex with `[0-9]`, for every number read off a
   wire.

10. **Do not reuse a name the enclosing function already owns.** The
    desk wrote `seq = chain_members(...)` inside `handle_mail`, whose
    `seq` is the IMAP sequence that `mark_seen` reads. It was caught
    before the commit. *Habit:* before adding a local name, grep the
    function for it.

11. **A test that mocks `os.*` mocks it for the whole process and
    every platform.** The desk patched `os.lstat`, which `realpath`
    also calls, so macOS, whose temp directory is behind the `/var`
    symlink, failed differently. A test that wrote a tool named `git`
    found nothing on Windows, which looks for `git.exe`. *Habit:* fail
    the one path the test means, by comparing paths, and name files the
    way each platform looks for them.

12. **The changelog says what the tag holds.** The desk put the change
    kind under 3.14.7, and 3.14.7 was tagged before it landed.
    *Habit:* after a tag, check every changelog bullet with
    `git merge-base --is-ancestor <commit> <tag>`.

## Asking the conductor

13. **Say who does the step inside the question.** The desk asked "add
    the RELEASE_TOKEN?" as if it could do it. Only the conductor can
    mint the token. He said "do it", and the desk had to answer that it
    could not. *Habit:* when the step is his, the question says "you
    would need to ..." and gives the steps.

14. **Where the desk was confused (28-Oct):** it took "do it" as a yes
    to a `RELEASE_TOKEN` and wrote that into Q30, when the conductor's
    ruling is no token, because the fix is the order of commits.
    *From here on:* the desk records a decision only from the
    conductor's ruling as written in the Q, and when his words could be
    read two ways it asks him before writing either reading.

## The one-line test

Before any push, the desk asks itself four things. Has a seat already
done or said this? Is every number and claim checked? Is the tree
clean of markers and stashes? Does every line follow the conductor's
exact form?
