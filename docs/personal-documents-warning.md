# Personal-documents warning

When the runner starts, and when the installer is about to put it
on a machine, it looks at this computer and may print a loud
warning. The warning means the machine looks like somebody's own
computer with legal, tax, or medical papers on it. The author
recommends not installing Homing Pigeon there unless you are a
proficient system administrator.

The check is rudimentary on purpose. It is a speed bump, not a
classifier.

## What it looks at

- The home directory's own file and folder names, one level.
- `Documents`, `Desktop`, and `Downloads` inside that home, and
  two levels under those.
- The same three folders inside a home folder whose name starts
  with `OneDrive`. The rest of OneDrive is not walked.
- On Linux, the three paths in `~/.config/user-dirs.dirs`
  (`XDG_DOCUMENTS_DIR`, `XDG_DESKTOP_DIR`, `XDG_DOWNLOAD_DIR`),
  and only when the path stays inside the home directory.

A name matches when one of its pieces is a token such as `tax`,
`medical`, `hipaa`, `1099`, or `w2`, or a short phrase such as
`bank statement` or `social security`. Pieces are split on
punctuation, so `taxonomy` is not `tax` and `healthcheck` is not
a health record. `w-2` is glued back into `w2`.

It stops at the first match, and it stops after 2000 names even
if it has not matched. It does not follow symlinks.

## What it does not do

- It does not open any document. Contents, titles inside a PDF,
  and embedded metadata are never read.
- It does not read Windows recent-file lists, jump lists, the
  registry, browser history, or mail.
- It does not walk the whole disk, other users' homes, or hidden
  folders.
- It does not remember the name that matched, print it, write it
  down, or send it. The banner is fixed text. It always says
  legal, tax, or medical, even when only one of those matched,
  so the screen does not reveal which.
- The log line, when there is one, is the same idea: the check
  tripped, and no name was recorded.

Those are the privacy choices. A content scan or a recent-file
list would be a better detector and a worse thing to run, on a
machine, every time an agent starts. Filename and folder-name
hints are the same signal a filing cabinet uses, and they are
available from a directory listing.

## Why a miss stays quiet

If the home directory cannot be read, or nothing matches, there
is no warning. A warning that fires on every server is a warning
people stop reading. A quiet result does not mean the computer is
free of personal papers. A scan named `IMG_2044.pdf` will not
match. That is the limit of looking at names.

## How to skip it

`--ignore-personal-documents` on the runner skips the check for
that process. The same flag on the installer skips the warning
during install and writes the runner flag into the service
command, so a boot start stays quiet too.

The banner does not mention the flag. `--help` does. There is
no config key. A service installed without the flag keeps
warning.

## Where it runs

The runner prints it at startup, including a dry run, unless
`--ignore-personal-documents` was passed. The installer prints
it before it copies anything, unless that same flag was passed.
`--help`, `--version`, uninstall, `--check`, and `--logs` do
not print it.
