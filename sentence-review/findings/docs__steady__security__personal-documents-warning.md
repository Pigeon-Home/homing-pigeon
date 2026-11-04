# Findings — docs/steady/security/personal-documents-warning.md

Source: docs/steady/security/personal-documents-warning.md, reviewed at main cbb52068.
Sentence units: 40. Flagged: 0. Categories: pre-release 40, post-release 0.

A behaviour note for the personal-documents warning: what it means, what the check looks at, what it refuses to do, why a miss stays quiet, how to skip it, and where it runs. The chaining is exemplary — the does-not list answers the looks-at list item by item, and the short closers (units 34 to 37) each hand off cleanly. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "When the runner starts, and when the installer…" | pre-release | flows |  |
| 2 | "The warning means the machine looks like somebody's…" | pre-release | flows |  |
| 3 | "The author recommends not installing Homing Pigeon there…" | pre-release | flows |  |
| 4 | "The check is rudimentary on purpose." | pre-release | flows |  |
| 5 | "It is a speed bump, not a classifier." | pre-release | flows |  |
| 6 | "The home directory's own file and folder names,…" | pre-release | flows |  |
| 7 | "`Documents`, `Desktop`, and `Downloads` inside that home, and…" | pre-release | flows |  |
| 8 | "The same three folders inside a home folder…" | pre-release | flows |  |
| 9 | "The rest of OneDrive is not walked." | pre-release | flows |  |
| 10 | "On Linux, the three paths in `~/.config/user-dirs.dirs` (`XDG_DOCUMENTS_DIR`,…" | pre-release | flows |  |
| 11 | "A name matches when one of its pieces…" | pre-release | flows |  |
| 12 | "Pieces are split on punctuation, so `taxonomy` is…" | pre-release | flows |  |
| 13 | "`w-2` is glued back into `w2`." | pre-release | flows |  |
| 14 | "It stops at the first match, and it…" | pre-release | flows |  |
| 15 | "It does not follow symlinks." | pre-release | flows |  |
| 16 | "It does not open any document." | pre-release | flows |  |
| 17 | "Contents, titles inside a PDF, and embedded metadata…" | pre-release | flows |  |
| 18 | "It does not read Windows recent-file lists, jump…" | pre-release | flows |  |
| 19 | "It does not walk the whole disk, other…" | pre-release | flows |  |
| 20 | "It does not remember the name that matched,…" | pre-release | flows |  |
| 21 | "The banner is fixed text: "this computer looks…" | pre-release | flows |  |
| 22 | "It never names the category that matched, so…" | pre-release | flows |  |
| 23 | "The log line, when there is one, is…" | pre-release | flows |  |
| 24 | "Those are the privacy choices." | pre-release | flows |  |
| 25 | "A content scan or a recent-file list would…" | pre-release | flows |  |
| 26 | "Filename and folder-name hints are the same signal…" | pre-release | flows |  |
| 27 | "If the home directory cannot be read, or…" | pre-release | flows |  |
| 28 | "A warning that fires on every server is…" | pre-release | flows |  |
| 29 | "A quiet result does not mean the computer…" | pre-release | flows |  |
| 30 | "A scan named `IMG_2044.pdf` will not match." | pre-release | flows |  |
| 31 | "That is the limit of looking at names." | pre-release | flows |  |
| 32 | "`--ignore-personal-documents` on the runner skips the check for…" | pre-release | flows |  |
| 33 | "The same flag on the installer skips the…" | pre-release | flows |  |
| 34 | "The banner does not mention the flag." | pre-release | flows |  |
| 35 | "`--help` does." | pre-release | flows |  |
| 36 | "There is no config key." | pre-release | flows |  |
| 37 | "A service installed without the flag keeps warning." | pre-release | flows |  |
| 38 | "The runner prints it at startup, including a…" | pre-release | flows |  |
| 39 | "The installer prints it before it copies anything,…" | pre-release | flows |  |
| 40 | "`--help`, `--version`, uninstall, `--check`, and `--logs` do not…" | pre-release | flows |  |
