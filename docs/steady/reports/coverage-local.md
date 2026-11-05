# Local coverage run

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

Whole-suite regression pass on a two-core Linux box, Python
3.13, stdlib line monitor, statements only, October 2026;
hypothesis does not install here, so CI's coverage.yml figure
is the one of record. Before the edge tests landed: 3,565
tests, 319 missed of 30,323 (98.95%). After, main at 8540cc23:
3,621 tests, 254 missed (99.16%).
