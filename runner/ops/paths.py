"""Path-finding helper.

Extracted from runner.py.
"""
import os


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore

def _script_path_findings(script, base_dir=None, job_id=None):
    """(path, reason) pairs for sensitive references in a script.

    A reference is a whitespace/shell-delimited token that is an
    absolute path (POSIX, ~/, or a Windows drive path, possibly the
    value side of a --flag=value). Findings: a credential store or
    key material anywhere; a path under a user home directory; a
    path under /etc/; and any other absolute path outside the
    ordinary system prefixes -- /tmp staging included. Paths
    inside the job's own workspace (or the runner's state
    directory) are its own business and never findings. Capped
    at 3, in script order.
    """
    R = _runner()
    if not isinstance(script, str) or not script:
        return []
    workspace = ""
    if isinstance(base_dir, str) and base_dir and job_id:
        workspace = os.path.join(base_dir, "work", job_id)
    findings = []
    seen = set()
    tokens = []
    cur = ""
    for ch in script:
        if ch in R._PATH_SPLITTERS:
            if cur:
                tokens.append(cur)
                cur = ""
        else:
            cur += ch
    if cur:
        tokens.append(cur)
    for token in tokens:
        if "=" in token:
            token = token.rsplit("=", 1)[-1]
        token = token.rstrip(",;:")
        is_path = (
            (token.startswith("/") and len(token) > 1)
            or token.startswith("~/")
            or (len(token) > 2 and token[1] == ":"
                and token[2] in "\\/")
        )
        if not is_path:
            continue
        norm = token.replace("\\", "/")
        low = norm.lower()
        if workspace and (norm == workspace.replace("\\", "/")
                          or norm.startswith(
                              workspace.replace("\\", "/") + "/")):
            continue
        if isinstance(base_dir, str) and base_dir:
            base_norm = base_dir.replace("\\", "/").rstrip("/")
            if norm == base_norm or norm.startswith(base_norm + "/"):
                continue
        reason = None
        if any(marker in low for marker in R._SENSITIVE_MARKERS):
            reason = "a credential store or key material"
        elif (norm.startswith("/home/") and norm.count("/") >= 3) \
                or norm.startswith("/Users/") \
                or norm.startswith("~/") \
                or "/users/" in low and low.index("/users/") <= 3:
            reason = "a file under a user home directory, outside " \
                     "the job's own workspace"
        elif norm.startswith("/etc/"):
            reason = "a system configuration file, outside the " \
                     "job's own workspace"
        elif norm.startswith(R._ORDINARY_PREFIXES) \
                or ":/windows/" in low or ":/program files" in low:
            continue
        else:
            reason = "a file outside the job's own workspace"
        if token in seen:
            continue
        seen.add(token)
        findings.append((token, reason))
        if len(findings) >= 3:
            break
    return findings
