# Coverage findings

Homing Pigeon, main @ c48aece, after the coverage-seam tests in pull 76.
Measured 2026-10-16 with coverage.py 7.16.2.

```
python3 -m coverage run --source=runner -m unittest discover -s tests -t .
```

1005 tests, OK, 48.0 seconds under coverage.
Statements: 4714. Missed: 694. Covered: 85%.
`runner/__init__.py` is fully covered.

The previous measurement, main @ 2ab5383, was 80% (4695 statements, 956 missed, 945 tests). The seam tests added the 5 points. They did not touch the poll library, which was already high.

## File totals

| File | Before | After | Missed now |
|---|---:|---:|---:|
| runner/winlog.py | 32% | 32% | 23 |
| runner/oauth.py | 43% | 69% | 45 |
| runner/install.py | 57% | 74% | 114 |
| runner/setup.py | 76% | 85% | 31 |
| runner/runner.py | 84% | 87% | 366 |
| runner/senses.py | 87% | 87% | 34 |
| runner/review.py | 88% | 88% | 14 |
| runner/dri.py | 90% | 90% | 35 |
| runner/local_test.py | 58% | 90% | 18 |
| runner/resources.py | 91% | 91% | 14 |

## What the seam tests closed

These were the holes a person hits on first run. They are no longer empty.

| Location | Before | After |
|---|---:|---:|
| install.py `main` | 0% | 75% |
| install.py `ensure_shared_secret` | 0% | covered |
| setup.py `_mailbox_probe` | 0% | covered |
| oauth.py `_pkce` | 0% | covered |
| oauth.py `build_authorize_url`, `exchange_code` | not extracted | covered without binding port 8765 |
| runner.py `oracle_window` | 0% | covered |
| runner.py `connect_imap`, `connect_smtp` | 0% | covered with fake clients |
| local_test.py `answer_as_oracle` | 13% | covered |
| local_test.py `repl` | 0% | covered |
| local_test.py `browser_chat` | 8% | covered without starting open-webui |

`runner.py main` moved from 26% to 36%. The early exits are covered: bad worker count, missing config, bad config, `--oracle`, `--local-test`. The poll loop itself is still not entered from `main`.

## What is still open, on purpose

These shells talk to the real OS, a browser, a model download, or the Windows event log. The seam tests do not import them.

| Miss | Cover | Statements | Location |
|---:|---:|---:|---|
| 22 | 4% | 23 | oauth.py:207 `browser_consent` |
| 18 | 28% | 25 | winlog.py:34 `report_event` |
| 17 | 6% | 18 | install.py:528 `ensure_ollama_running` |
| 14 | 67% | 43 | install.py:552 `install_ollama_and_model` |
| 14 | 7% | 15 | oauth.py:233 `main` |
| 11 | 8% | 12 | install.py:279 `install_freebsd` |
| 9 | 10% | 10 | install.py:487 `_ollama_up` |
| 7 | 12% | 8 | install.py:230 `uninstall_linux` |

`browser_consent` still binds `127.0.0.1:8765` and calls `webbrowser.open`. The URL and the token exchange are tested beside it. The bind is the part that stays out.

Windows, FreeBSD, and macOS uninstall paths stay out for the same reason. A test that runs those scripts is not a unit test.

## Library surface, unchanged

The poll path was not the gap. It is still in the same band:

| Function | Cover |
|---|---:|
| `handle_mail` | 96% |
| `answer_queries` | 93% |
| `execute_job` | 89% |
| `poll_once` | 85% |
| `dri.py` | 90% |
| `resources.py` | 91% |
| `review.py` | 88% |
| `senses.py` | 87% |

The remaining misses inside those functions are the other side of a `try` that a negative test already holds. Another line there does not change what happens when a person starts the program.

## How to repeat

From the repo root, with coverage.py installed. It is a measurement tool, not a project dependency.

```
python3 -m coverage run --source=runner -m unittest discover -s tests -t .
python3 -m coverage report
```

Expect about 50 seconds. Do not treat 85% as a target. The number moves when the untested platform shells move, and those shells should stay untested until a machine of that OS runs them.
