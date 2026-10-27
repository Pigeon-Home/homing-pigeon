# Where the de_dust work is

The working tree was clean when this was written. Everything
below is already on `main`. This file is the index.

The questions are `docs/use/questions.md`. The plan is
`docs/project/de_dust.md`. The tool is
`runner/tools/de_dust_corpus.py`. The corpus is
`runner/tests/de_dust/<target>.jsonl`, and
`runner/tests/test_de_dust_corpus.py` replays it.

| Q | What | Commit |
|---|------|--------|
| Q65 | the mail path, the seventh target | [`7b896b6f2474`](https://github.com/Pigeon-Home/homing-pigeon/commit/7b896b6f2474) |
| Q66 | the DTLS target | [`4ad13c89b827`](https://github.com/Pigeon-Home/homing-pigeon/commit/4ad13c89b827) |
| Q67 | the board target | [`1db7e3dcd04f`](https://github.com/Pigeon-Home/homing-pigeon/commit/1db7e3dcd04f) |
| Q68 | the channel target | [`286639879108`](https://github.com/Pigeon-Home/homing-pigeon/commit/286639879108) |
| Q69 | the manifest target | [`594e93ab582f`](https://github.com/Pigeon-Home/homing-pigeon/commit/594e93ab582f) |
| Q70 | the sequence contract on `local` | [`edaad0d414fd`](https://github.com/Pigeon-Home/homing-pigeon/commit/edaad0d414fd) |
| Q71 | the corpus agrees on the Windows surface | [`5eb5ee562147`](https://github.com/Pigeon-Home/homing-pigeon/commit/5eb5ee562147) |
| Q72 | the grammar dictionary from the IETF drafts | [`4d500a349c1e`](https://github.com/Pigeon-Home/homing-pigeon/commit/4d500a349c1e) |
| Q73 | 20,000 rounds under that dictionary | [`9eb315ab6de5`](https://github.com/Pigeon-Home/homing-pigeon/commit/9eb315ab6de5) |
| Q74 | the posted capture's shape, rebuilt | [`6d627fe0d414`](https://github.com/Pigeon-Home/homing-pigeon/commit/6d627fe0d414) |
| Q75 | one steered grow of the four live mutators | [`0345e65eee8f`](https://github.com/Pigeon-Home/homing-pigeon/commit/0345e65eee8f) |
| Q76 | the same four again | [`7e6166fcdf01`](https://github.com/Pigeon-Home/homing-pigeon/commit/7e6166fcdf01) |
| Q77 | a third grow of the live mutators | [`f5113b67772c`](https://github.com/Pigeon-Home/homing-pigeon/commit/f5113b67772c) |
| Q78 | a non-finite priority on disk poisoned save | [`880071d4e4f7`](https://github.com/Pigeon-Home/homing-pigeon/commit/880071d4e4f7) |
| Q79 | a non-finite float under any other key | [`94c99d9283b8`](https://github.com/Pigeon-Home/homing-pigeon/commit/94c99d9283b8) |
| Q80 | local, the grow the crash cut off | [`f2388fb98f8e`](https://github.com/Pigeon-Home/homing-pigeon/commit/f2388fb98f8e) |
| Q81 | the two that were still live | [`303ab2790ac2`](https://github.com/Pigeon-Home/homing-pigeon/commit/303ab2790ac2) |
| Q82 | local, again | [`59d27db0216b`](https://github.com/Pigeon-Home/homing-pigeon/commit/59d27db0216b) |
| Q83 | local, a third time | [`33ec38e489ca`](https://github.com/Pigeon-Home/homing-pigeon/commit/33ec38e489ca) |

Q77 through Q83 were checked as ancestors of `main` on
2026-10-26. Each id above is that commit. The working tree was
clean. Nothing in this table was still waiting on a later commit.

Q74 does not copy the capture. The capture stays at
`docs/reports/live-2026-10-25/`. The seeds are invented ids
under the corpus secret.

The desk's lane in the same days, under the same plan:

| What | Commit |
|------|--------|
| the board under the sequence contract (`board_ops`), three board findings fixed | [`661ad958`](https://github.com/Pigeon-Home/homing-pigeon/commit/661ad958) |
| the channel inbox under the sequence contract (`inbox`) | [`e8ed200f`](https://github.com/Pigeon-Home/homing-pigeon/commit/e8ed200f) |
| the local inbox under the sequence contract (`local_inbox`), a directory named `.json` left alone | [`34bc052f`](https://github.com/Pigeon-Home/homing-pigeon/commit/34bc052f) |
| the provenance contract on the verifiers; a result subject is one line | [`3c97ec0f`](https://github.com/Pigeon-Home/homing-pigeon/commit/3c97ec0f) |
| the generated grammar dictionary (`grammar.json`) | [`01aa1ffe`](https://github.com/Pigeon-Home/homing-pigeon/commit/01aa1ffe) |
| steered grows, the archive, the learning dictionary, the recovery seeds (Muse's four) | [`5b15a9fb`](https://github.com/Pigeon-Home/homing-pigeon/commit/5b15a9fb) |
| the mutation survivors (`runner/tools/de_dust_survivors.py`, `survivors.json`) | [`27837979`](https://github.com/Pigeon-Home/homing-pigeon/commit/27837979) |
| the survivors' seeds, the `secret` target | [`b0524bfb`](https://github.com/Pigeon-Home/homing-pigeon/commit/b0524bfb), [`5e981e21`](https://github.com/Pigeon-Home/homing-pigeon/commit/5e981e21), [`d6a87250`](https://github.com/Pigeon-Home/homing-pigeon/commit/d6a87250), [`6a6410cd`](https://github.com/Pigeon-Home/homing-pigeon/commit/6a6410cd), [`564efb9b`](https://github.com/Pigeon-Home/homing-pigeon/commit/564efb9b) |

Not started: any further live capture the conductor has not
named (phase 5).
