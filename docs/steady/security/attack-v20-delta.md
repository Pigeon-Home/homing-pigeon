# MITRE ATT&CK v20 delta: Oracle detection coverage

MITRE ATT&CK v20 was released on 2026-10-13. This page is a
delta audit only: it maps the six v20 changes that touch an
AI-agent runner against the detection evidence the Oracle
already has, and states plainly where there is none. It is not
a full ATT&CK mapping of the runner, and it changes no runtime
behaviour: no detection rule, sense, or alert output is added,
renamed, or relabelled by this audit.

## The detection evidence this audit rests on

The Oracle's detection surface is `runner/oracle/detection.py`.
Its rule set, complete, is:

- `suspicious_interpreter` (T1059): the job's interpreter is
  `python2`, `perl`, or `ruby`.
- `encoded_command` (T1027): the job's script contains one of
  the substrings `base64`, `eval(`, or `exec(`.
- `high_output` (T1041): the job's stdout is longer than
  100,000 characters.

Alongside the rules, the same module carries three helpers:

- `check_plan_budget`: an explicit multi-step plan is bounded
  by step count and summed timeout.
- `baseline_anomaly`: a job result is flagged
  `output_size_anomaly` when its output is more than 10 times
  the median of recent output sizes, and `new_job_kind` when a
  job kind appears for the first time after more than 20 jobs
  have been seen.
- `tag_alert`: an ATT&CK technique ID is attached to an alert.

No existing rule in this set targets any of the v20 AI
techniques below. Every coverage call in the table follows
from that fact and from the further evidence named per row.

## The delta, row by row

| Technique | Coverage | Evidence and gap |
|---|---|---|
| T1699 Direct Prompt Injection (Execution) | Blind spot | No detection targets instructions typed into the Oracle's own interface. That interface is owner-side and signature-gated: a barrier that keeps other parties out, which is prevention, not detection of an injection attempt. |
| T1698 Indirect Prompt Injection (Execution) | Partial | The `encoded_command` rule (T1027) in `runner/oracle/detection.py` screens job payloads, and the intake fuzz suite (`runner/tests/test_oracle_intake_fuzz.py`) exercises an instruction-override wrapper around a denied payload through the sensor and extension intake, with the denial standing; unsigned content cannot reach execution. Gap: no rule flags instruction-shaped text in read content, such as mail bodies, files, or tool output. |
| T1700 AI-Enabled Exfiltration (Exfiltration; DET0927) | Partial | The `high_output` rule (T1041, stdout over 100,000 characters) and `baseline_anomaly` (output over 10 times the median) watch the job-result channel, which is the runner's sanctioned outbound path. Gap: no detection watches the Oracle's own tool calls for data movement. |
| T1608.007 Stage Capabilities: AI Result Poisoning (Resource Development; DET0922) | Blind spot | No detection ingests or vets AI-search or retrieval results. External material brought in by an extension is declared-source only and gated by the disclosure rule, `disclosure()` in `runner/ops/extsources.py`: a gate on whether material is provided, not a check that the material has not been poisoned. ATT&CK's own DET0922 likewise notes that no target-side analytic exists for this technique. |
| T1685.007 Disable or Modify Tools: Impair Autonomous Defenses (Defense Impairment) | Partial | The intake fuzz suite exercises exactly this shape, an instruction telling the Oracle not to fail a malicious job, with the denial standing, and structurally an Oracle opinion cannot widen a policy denial (`runner/tests/test_oracle_no_widening.py`). Gap: no detection alerts on impairment attempts themselves; an attempt that fails is not itself an alert. |
| T1195.001 Supply Chain Compromise: Compromise Software Dependencies and Development Tools, revised from version 1.3 to version 2.0 | Blind spot | The revision now covers IDE and coding-agent configuration and instruction files, including `.vscode/tasks.json`, `SKILL.md`, rules files, and `.mcp.json`. A search of `runner/` and `docs/` for `tasks.json`, `SKILL.md`, `.mcp.json`, `cursorrules`, and `.vscode` returns zero matches: nothing in the runner reads, watches, or checks that file class. The scan of files a job produces checks them for credential-store references, which is a different file class and a different purpose, and is not coverage here. |

## Reading the calls

A blind spot means there is no detection to point at, not that
the surface is unguarded: two of the three blind spots sit
behind a preventive gate (the signature-gated owner interface
for T1699, the disclosure gate for T1608.007), and the third
(T1195.001) is a file class the runner does not consume at all.

Partial means a neighbouring control already catches part of
the shape, for a neighbouring technique, and the gap column
in the table names the part it does not reach: instruction
shaped text in read content (T1698), the Oracle's own tool
calls as a data path (T1700), and alerting on a failed
impairment attempt itself (T1685.007).

Closing any of these gaps is a separate decision from this
audit. Until a rule exists, the honest statement is the one in
the table: the v20 AI techniques are not what the current
detection set looks for.
