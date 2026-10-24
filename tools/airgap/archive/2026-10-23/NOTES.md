# Author airgap. Start analysis of LLM tools.

| Tool | Record |
|---|---|
| `tools/airgap/sweep.py` | Case list. `slow` names qwen2.5:3b. `default` names qwen3:1.7b. |
| `tools/airgap/cases/echo_one.py` | Ten short questions. No project context. |
| `tools/airgap/candidates.py` | 39 long strings from the five flag321 files. No string printed. No reply printed. |
| `tools/airgap/candidates-slow.txt` | 12 of those strings. Cutoff 90 seconds. |
| `tools/airgap/batches.py` | Three sittings: `fast`, `each`, `rest`. |
| `tools/airgap/run.cmd` | `fast`, or the sitting named on the command line. |
| `tools/airgap/interesting.example/OVERVIEW.py` | Held cases of 1000 characters or fewer. Shortest first. 1801 cases. |

`ok` — process exit 0. On a string pass, the model stops. The reply is not read.

`problem fail` — process exit non-zero.

`problem timeout` — the cutoff. `fast` and `rest` use 120 seconds. `each` uses 60 minutes.

`held` — a file that does not pass. A later run of the same sitting does not retry it.

## Records

String pass, qwen2.5:3b, no token cap. 39 strings. Cutoff 30 seconds: 27 stop, 12 do not. Cutoff 90 seconds: those 12 stop. Slowest: `test_flag321_long_scripts.py#1` at 83.9 seconds.

`fast` — 225 files, 3,636 tests. 146 ok. 79 held. Cutoff: `tests/test_install_edges.py`, `tests/test_posture.py`.

`each` — 15 files. 11 ok. 4 held: `tests/test_doc_default_divergences.py`, `tests/test_linux_platform.py`, `tests/test_oracle_intake_fuzz.py`, `tests/test_job_fuzz.py`. `tests/test_campaign_loop_cycles.py` is 0 seconds where `sh` is absent.

`rest` — 9 files. 9 ok. 0 held.

`judge_job` in enforce, and `validate_candidate`, are in `denylist-exact.txt`.
