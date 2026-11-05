# Runbook: get runner.py under 10,000 lines

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

Status: done. The series of 2026-10-25 took runner/runner.py
from 11,205 lines to 5,362, moving the pieces into runner/ops/;
it shipped in 3.12.74 after a repair of how the extracted
modules load (Q52-Q55 in docs/steady/seats/questions.md).
Extraction only, no behavior change; its rules bind any
further extraction.
