# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
# Windows installer hardening: supposition and conclusions

This page records the supposition, the change, and the
conclusions for hardening the draft Microsoft Store route A
installer at packaging/windows/homing-pigeon.iss. The review
that prompted the work is Grok's project review of
2026-11-23, forwarded to the Muse seat by email that day.
The route itself stands in
docs/steady/design/app-stores-design.md. The script stays a
draft and stays unsigned: no signing certificate exists, and
none is faked here.

## Supposition, written before the change

S1, stable config home. The draft seeds config.json inside
the versioned program folder, so an upgrade strands an edited
config in the previous version's folder. Prediction: moving
the seeded config to one fixed location that no version
number enters, {commonappdata}\Homing Pigeon\config.json,
with its folder restricted to administrators and SYSTEM,
makes an upgrade unable to strand the config, because the
path the task reads no longer changes with the version. The
seed keeps onlyifdoesntexist and uninsneveruninstall, so an
existing config is never overwritten and never removed by an
uninstall. Configs already seeded by the draft shape in a
versioned folder get an explicit note telling the operator
to copy the file once by hand; the installer does no silent
migration.

S2, setup gate. The draft registers and starts the
HomingPigeon startup task at once, against a config that
still carries the example's placeholder values (the mailbox
password "paste-app-password-here-in-plaintext", the shared
secret "generate-with-openssl-rand-hex-32", and the example
mailbox user). Prediction: gating both task entries in the
[Run] section on an Inno Setup Check function that reads the
stable config and refuses while any known placeholder string
stands in it means a fresh install with an unfinished config
registers nothing and starts nothing, while a completed
config registers and starts the same task the install
program registers. A wizard page shown before installation
makes the SYSTEM account choice and its consequences visible
in plain words, and a closing message names the unfinished
case and tells the operator to edit the config and run the
installer again.

S3, certification notes. No page in the tree yet gives a
store reviewer the material certification asks for: how jobs
arrive authenticated, how a reviewer builds a disposable
test account, and how to stop and remove the service.
Prediction: a new page in this folder,
docs/steady/design/microsoft-certification-notes.md,
covering those three subjects from the install program's own
operator surface (the --check, --console, --logs,
--uninstall and --wipe commands) closes that gap without
touching the listing itself. The generative AI disclosure
question the review raised is stated on that page as an open
listing check, not as a settled answer, because the listing
has not been written yet.

S4, the MSIX identity note. The draft manifest at
packaging/msix/Package.appxmanifest carries placeholder
identity values, and no honest values exist to put in their
place: Partner Center issues the identity name, the
publisher, and the publisher display name only when the
product name is reserved in the owner's account, and that
reservation has not happened. The seller identifier on file
for the account is a Partner Center seller identifier; it is
not a field the manifest carries, and the account name is
not an issued publisher value. Prediction: the placeholders
stay exactly as they are, and what changes is the record: a
dated note in the manifest header and a matching paragraph
in docs/steady/design/app-stores-design.md stating what was
checked, what the seller identifier is and is not, and that
the values remain pending the name reservation.

## Conclusions

Written after the change, against the supposition above.

S1 held. The seeded config now lands in
{commonappdata}\Homing Pigeon with onlyifdoesntexist and
uninsneveruninstall kept, a [Dirs] entry restricts that
folder to administrators and SYSTEM, and the task command
points --config at the fixed path. No version number enters
the path, so an upgrade cannot strand an edited config in a
previous version's folder. The legacy note stands in the
script header: an install from the earlier draft shape holds
its config in a versioned folder, and its operator copies
that file once by hand. No silent migration was added.

S2 held. Both [Run] entries carry Check: ConfigIsSetUp, and
the [Code] function of that name reads the stable config and
refuses while any of the three placeholder strings stands in
it: the mailbox password, the shared secret, and the example
mailbox user. The wizard gained a page, shown before
installation, that names the SYSTEM account, the highest run
level, the at boot start, and the right the runner then has.
CurStepChanged adds the closing message for the unfinished
case, naming the config path and the rerun step. Under the
silent install flags the page is skipped by Inno Setup
itself, and the gate still applies, which is the shape the
route's silent requirement wants.

S3 held. docs/steady/design/microsoft-certification-notes.md
now carries the reviewer material: the authenticated job
path, a six step disposable test account recipe, stop and
remove through the install program's own commands and the
uninstaller, and the generative AI disclosure question
stated as an open listing check with the product facts it
will be answered from.

S4 held. The manifest placeholders are unchanged, character
for character, and the dated note stands in the manifest
header with the matching paragraph in
docs/steady/design/app-stores-design.md: the seller
identifier is a Partner Center seller identifier and not a
field the manifest carries, the account name is not an
issued publisher value, and the identity values remain
pending the product name reservation.

Proof of work: the pins in runner/tests/test_windows_installer.py
and runner/tests/test_store_packaging.py were written first
and read red against the draft shape (10 failures), then
green after the change. What this proof cannot reach is
stated plainly: nothing here compiles the installer, because
Inno Setup runs on Windows and this work ran on Linux, and
nothing is signed, because no signing certificate exists.
The script stays marked DRAFT and UNSIGNED, and both of
those remain owner steps on the route, exactly as the design
notes record.
