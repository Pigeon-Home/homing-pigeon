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

Filled in after the change lands, in this same place.
