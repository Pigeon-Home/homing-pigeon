"""Loud warning when this machine looks like a personal computer.

The decisions, and why, are in docs/security/personal-documents-warning.md.
This module never opens a document, never keeps a name it saw, and
never sends anything. A hit prints one fixed banner and returns.
"""

import os
import sys

# Names we will look at, then stop. A home directory can be huge.
# Two thousand entries is enough to notice a tax or medical folder
# and small enough to finish immediately.
_ENTRY_CAP = 2000

# Documents/Taxes/2024-return.pdf is depth 2. Deeper than that is
# a tree, not a folder of papers, and we do not walk it.
_DEPTH = 2

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "venv", ".venv", "__pycache__",
    "site-packages", "dist-packages",
})

# Whole tokens only. "taxonomy" is not "tax", "healthcheck" is not
# "health". Short or common words are phrases below, not tokens.
_TOKENS = frozenset({
    "hipaa", "hippa", "diagnosis", "diagnoses", "prescription",
    "prescriptions", "pathology", "radiology", "subpoena",
    "affidavit", "mortgage", "paystub", "paystubs", "passport",
    "w2", "1099", "1040", "1098", "medical", "medicine",
    "taxes", "tax", "legal", "insurance", "attorney", "lawyer",
    "counsel", "clinic", "hospital", "patient", "lawsuit",
    "deposition", "notary", "testament", "contract", "contracts",
})

_PHRASES = (
    ("health", "record"),
    ("health", "records"),
    ("medical", "record"),
    ("medical", "records"),
    ("bank", "statement"),
    ("bank", "statements"),
    ("tax", "return"),
    ("tax", "returns"),
    ("income", "tax"),
    ("social", "security"),
    ("power", "of", "attorney"),
    ("birth", "certificate"),
    ("drivers", "license"),
    ("driver", "license"),
    ("living", "will"),
    ("last", "will"),
    ("life", "insurance"),
    ("health", "insurance"),
    ("explanation", "of", "benefits"),
)

_XDG_KEYS = (
    "XDG_DOCUMENTS_DIR",
    "XDG_DESKTOP_DIR",
    "XDG_DOWNLOAD_DIR",
)

_WATCHED = ("documents", "desktop", "downloads")


def _banner():
    """Fixed text. The same words every time, so the banner cannot
    reveal which name matched."""
    width = 66
    rows = [
        "",
        " #     #    #    ######  #     # # #     #  ####",
        " #  #  #   # #   #     # ##    # # ##    # #    #",
        " #  #  #  #   #  #     # # #   # # # #   # #",
        " #  #  # #     # ######  #  #  # # #  #  # #  ###",
        " #  #  # ####### #   #   #   # # # #   # # #    #",
        " #  #  # #     # #    #  #    ## # #    ## #    #",
        "  ## ##  #     # #     # #     # # #     #  ####",
        "",
        " THIS COMPUTER LOOKS LIKE IT HOLDS IMPORTANT DOCUMENTS.",
        "",
        " The author of Homing Pigeon strongly recommends that you",
        " do NOT install or run this here unless you are a",
        " proficient system administrator.",
        "",
        " This check looked only at file and folder names in your",
        " home Documents, Desktop, and Downloads. It did not open",
        " any file. It did not keep or send any name.",
        "",
    ]
    bar = "*" * (width + 4)
    body = [bar]
    for row in rows:
        body.append("* " + row.ljust(width) + " *")
    body.append(bar)
    return "\n".join(body)


BANNER = _banner()


def _tokens(name):
    """Alphanumeric pieces of a file or folder name, extension off."""
    stem = name
    _base, ext = os.path.splitext(name)
    if ext and 1 < len(ext) <= 8 and ext[1:].isalnum():
        stem = _base
    parts = []
    cur = []
    for ch in stem.lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            parts.append("".join(cur))
            cur = []
    if cur:
        parts.append("".join(cur))
    return parts


def _sensitive(name):
    parts = _tokens(name)
    if any(part in _TOKENS for part in parts):
        return True
    # "w-2.pdf" splits into w, 2. Glue a single letter to the
    # digits that follow it so the form number still matches.
    glued = []
    i = 0
    while i < len(parts):
        nxt = i + 1
        if (len(parts[i]) == 1 and parts[i].isalpha()
                and nxt < len(parts) and parts[nxt].isdigit()):
            glued.append(parts[i] + parts[nxt])
            i += 2
            continue
        glued.append(parts[i])
        i += 1
    if any(part in _TOKENS for part in glued):
        return True
    for phrase in _PHRASES:
        n = len(phrase)
        for i in range(len(parts) - n + 1):
            if tuple(parts[i:i + n]) == phrase:
                return True
    return False


class _Budget:
    def __init__(self):
        self.n = 0

    def take(self):
        self.n += 1
        return self.n > _ENTRY_CAP


def _under_home(home, path):
    try:
        home_real = os.path.realpath(home)
        real = os.path.realpath(path)
        return os.path.commonpath([home_real, real]) == home_real
    except (OSError, ValueError):
        return False


def _xdg_dirs(home):
    """Optional. Only the three XDG folder paths, and only when
    they stay inside the home directory. A relocated Documents
    folder is still the papers folder; a path that leaves home
    is not our business."""
    path = os.path.join(home, ".config", "user-dirs.dirs")
    try:
        if os.path.islink(path) or os.path.getsize(path) > 16384:
            return []
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read(16384)
    except OSError:
        return []
    found = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key not in _XDG_KEYS:
            continue
        val = val.strip().strip('"').strip("'")
        val = val.replace("${HOME}", home).replace("$HOME", home)
        if not os.path.isabs(val) or os.path.islink(val):
            continue
        if not _under_home(home, val) or not os.path.isdir(val):
            continue
        found.append(os.path.realpath(val))
    return found


def _walk(root, depth, budget):
    if depth > _DEPTH:
        return False
    try:
        entries = os.scandir(root)
    except OSError:
        return False
    with entries:
        for ent in entries:
            if budget.take():
                return False
            if ent.name.startswith(".") or ent.name.lower() in _SKIP_DIRS:
                continue
            try:
                if ent.is_symlink():
                    continue
                is_dir = ent.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if _sensitive(ent.name):
                return True
            if is_dir and depth < _DEPTH:
                if _walk(ent.path, depth + 1, budget):
                    return True
    return False


def personal_documents_present(home=None):
    """True when a shallow name scan of the home papers folders
    hits a legal, tax, or medical token.

    Returns False when the home is missing, unreadable, or simply
    has no such name. Unknown is quiet on purpose: a warning that
    fires on every server gets ignored on the machine that matters.
    """
    if not home:
        home = os.path.expanduser("~")
    if not isinstance(home, str) or not home or not os.path.isdir(home):
        return False
    budget = _Budget()
    try:
        with os.scandir(home) as scan:
            top = list(scan)
    except OSError:
        return False
    watched = []
    for ent in top:
        if budget.take():
            return False
        if ent.name.startswith("."):
            continue
        try:
            if ent.is_symlink():
                continue
            is_dir = ent.is_dir(follow_symlinks=False)
        except OSError:
            continue
        if _sensitive(ent.name):
            return True
        low = ent.name.lower()
        if is_dir and low in _WATCHED:
            watched.append(ent.path)
        elif is_dir and low.startswith("onedrive"):
            # The cloud folder itself is photos and mail too.
            # Only the paper folders inside it are in scope.
            for child in ("Documents", "Desktop", "Downloads"):
                watched.append(os.path.join(ent.path, child))
    for extra in _xdg_dirs(home):
        watched.append(extra)
    seen = set()
    for root in watched:
        real = os.path.realpath(root) if os.path.isdir(root) else ""
        if not real or real in seen or not _under_home(home, real):
            continue
        if os.path.islink(root):
            continue
        seen.add(real)
        if _walk(real, 0, budget):
            return True
    return False


def warn_if_personal_documents(home=None, stream=None):
    """Print the banner when the check trips. Never raises.

    The banner is the whole report. Callers must not log a path.
    """
    try:
        hit = personal_documents_present(home)
    except Exception:
        return False
    if not hit:
        return False
    print(BANNER, file=stream or sys.stderr, flush=True)
    return True
