# How scripts run

Jobs carry a `script` (or `script_url`) plus an optional `interpreter`
list, e.g. `["bash"]` or `["pwsh", "-File"]`. The runner writes the
script to the job's work dir and runs `<interpreter...> script <args...>`.
Defaults: PowerShell on Windows, `sh` elsewhere; override per-install
with `default_interpreter` in config.json, per-job with `interpreter`
in the job (`send_job.py new --interpreter '["bash"]'`).

**Ask before you guess.** A `ping` job's result carries a platform
card at the tier the owner set (`pong_platform`, default `family`):
the OS family, the default interpreter, and the protocol versions
the runner speaks. Ping first and the interpreter-mismatch class of
failure never happens; the same card rides the DTLS greeting.
PROTOCOL.md section 3.2.
