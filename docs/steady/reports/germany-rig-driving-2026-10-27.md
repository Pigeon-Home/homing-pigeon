# The Germany rig is driving — how access was gained, and what failed (2026-10-27)

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

Administration of the Germany rig passed from Grok to Muse on
2026-10-27. Two queue credential sets were refused (401) before
any signature was judged; the third, the set actually deployed
on the rig, passed, and control was proven by a signed ping
answered by runner fedora-1gb-nbg1-1, key k-7e1ec001. The root
password was reset by the conductor at the provider's panel and
replaced. The file also records a diagnosis of Muse's that
was wrong — an idle-looking runner read as stopped — and the
verdict on the conductor's question: the rig's fuzzer is
running, the only workload that holds the core, with readings
about 110% one second apart.
