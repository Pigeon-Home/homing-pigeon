# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# Microsoft Store certification notes

Reviewer facing material for a Microsoft Store submission of
Homing Pigeon, prepared on 2026-11-23 with the route record
in docs/steady/design/app-stores-design.md. Nothing here is a
submission. The page collects, in one place, what a
certification reviewer needs in order to exercise the product
honestly: what the product does, how its jobs are
authenticated, how a reviewer sets up a disposable test
account, and how to stop and remove the service. The listing
itself will carry the short form of this material in its own
notes for certification field.

## What the product does

Homing Pigeon is a runner. It polls a mailbox the operator
gives it, accepts jobs that arrive there in a signed form,
carries each job out on the host with the host's own
interpreters, and sends a signed result back. Executing jobs
is the product's described functionality, stated plainly here
and to be stated just as plainly in the listing: a job is a
script the operator's own side signed, and the runner runs
nothing else. On Windows the runner is a machine level
service, started by a Scheduled Task named HomingPigeon that
runs as SYSTEM at startup. The install program laid down
beside the runner is its operator surface.

## How jobs are authenticated

Every job carries an HMAC signature made with a shared
secret that belongs to the installation. The runner accepts
nothing unsigned, in every mode it runs: an unsigned job, a
job signed with the wrong secret, and a job whose signature
does not verify are all refused, and the refusal is what the
sender receives. The secret is generated at setup time on
the operator's own machine and delivered to the operator's
mailbox in the install record the setup sends; it is a
signing string, not a login, and it never appears in the
listing or in this page. Signing proves the job came from
the holder of the installation's secret. What a signed job
may do is a separate question, answered by the runner's
posture and policy settings on the host, never by the
signature alone. Results are signed the same way, so the
sending side can verify that a result came from its runner.

## A disposable test account for the reviewer

Certification can exercise the whole round trip with
accounts created for the purpose and thrown away afterwards:

1. Create a fresh mailbox for the runner. A free mailbox
   from any provider works. It must be a mailbox of its own,
   never a personal inbox, because the runner reads jobs
   from it and writes its install record and results there.
2. Create a second mailbox for the sending side, or use any
   mailbox the reviewer already controls. This is the
   mailbox the results return to.
3. Install the product, then finish the setup in the config
   file the installer seeds under the machine's common
   application data folder, in the Homing Pigeon folder:
   the runner mailbox address, its app password, and the
   shared secret the setup generated. While the example
   placeholder values stand in that file, the installer
   registers and starts nothing, by design.
4. Run the installer again so the startup task registers,
   or start the runner in the foreground with the install
   program's console command. The install record arrives in
   the runner mailbox and carries the machine facts and the
   secret the runner expects.
5. Send a signed test job from the sending mailbox, signed
   with that secret, addressed to the runner mailbox, with
   the reply directed to the sending mailbox. A trivial job
   (print a line of text) is enough: the signed result
   returns to the sending mailbox, and the runner's check
   command reports the install's state on the host.
6. When the review ends, remove the service as the next
   section describes, then delete both mailboxes. Nothing
   about the test accounts needs to outlive the review.

## How to stop and remove the service

To stop the runner at once: end the HomingPigeon task in
Task Scheduler, or run the install program with its console
command in a terminal and interrupt it there; the console
run is in the foreground and stops with the terminal. The
install program's check command reports whether the task
and the runner are in place, and its logs command shows the
runner's own log.

To remove the service: run the product's uninstaller, which
deletes the startup task and the installed files, or run
the install program with its uninstall command, which
deletes the task and leaves the files and state in place.
The install program's wipe command goes further: it backs
the whole installation up into one zip and then removes
everything, config and state included. Short of the wipe,
the seeded config stays where it was seeded, so a later
reinstall picks the same setup up again.

## An open listing check: generative AI disclosure

The runner's Oracle can answer questions interactively, and
with a local model configured it can add model formed notes
to its work. Whether the submitted listing must carry a
generative AI content disclosure, and a way to report
inappropriate content, under the store policies in force at
submission time is an open check for the listing's author,
recorded here rather than settled: the policies move, the
listing has not been written yet, and the honest state of
the question is that it must be answered against the live
policy text on the day the listing is drafted. The product
facts the answer will rest on are the ones above: the model
is local to the operator's machine, the feature can be
turned off in the config, and its output reaches only the
operator's own mailbox.
