# Changelog

## 3.7.35 - 2026-10-18

### Security

- A job carrying a notable (suspicious-access) finding no longer
  has its raw output placed in the Oracle's context: the summary
  carries the finding, the script, and an attestation-shaped
  withheld marker (length and digest) instead. Field tests
  showed small models handing a flagged job's output back on
  request and unprompted, and the reply gate cannot catch an
  arbitrary short value. The withheld outputs still feed the
  reply gate as scan-only watch text -- never shown to the
  model -- so a reply repeating a pattern-shaped secret from a
  flagged job is still rejected. The retained record on disk is
  unchanged, and unflagged jobs keep their output in context.

### CI

- Mutation can collect a baseline again. The sharded-suite
  test imports `tools/run_tests_parallel.py` at load time, and
  mutmut's copy did not include `tools/`, so the v3.7.34 tag
  job died on that missing file before any mutant ran.

## 3.7.34 - 2026-10-18

### Oracle

- The default inference model is now `qwen3:1.7b` (was
  `llama3.2:3b`), chosen by the full model eval battery under
  the project's ranking -- a clean catch with no invented
  findings first, then history and detail accuracy, then
  latency. It was one of only two models with two clean
  catches and no invention, and the only one of the two that
  also passed history and detail. `--faster` still pulls
  `qwen2.5:3b`; the Raspberry Pi profile still pulls
  `llama3.2:1b`; `--inference-model` still wins over both.

### CI

- The Windows suite run is sharded. `tools/run_tests_parallel.py`
  splits the same unittest discover across four workers, each
  test exactly once. The Linux test job stays the serial
  reference run.

## 3.7.33 - 2026-10-18