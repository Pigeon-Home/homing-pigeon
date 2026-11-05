# 3.14.43: from the blocked cut to the mirrors

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

Written 30-OCT 6:36PM PST. At 6:10PM, four full-matrix builds
on four 3.14.43 commits had each failed the Windows test leg at
run_tests_parallel.py in about two minutes, with no test named.
The cause, read from the log on the rig side: on b3800a18 the
parent died at 01:01:15Z inside proc.wait with
KeyboardInterrupt — a shard's console control event reached
the parent's process group. The fix, a9bd3dc2: on Windows each
shard starts with CREATE_NEW_PROCESS_GROUP, and the wait
catches KeyboardInterrupt, kills the shard tree, records the
result as interrupted, and prints the shard's log. Outcome:
the Windows leg went green, the cut shipped, and 3.14.43 stood
verified on every mirror before 7:00PM PST — the GitHub
release with 13 assets, SHA384SUMS with 12 entries all
verifying, PyPI's wheel and sdist, GHCR on the version tag and
latest, and the GitLab release with 13 asset links.
