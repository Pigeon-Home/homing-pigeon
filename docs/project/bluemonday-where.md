# Where the blueMonday work is

The working tree was clean when this was written. Everything
below is already on `main`. This file is the index.

The questions are `docs/use/questions.md`. The plan is
`docs/project/bluemonday.md`. The tool is
`runner/tools/bluemonday_corpus.py`. The corpus is
`runner/tests/bluemonday/<target>.jsonl`, and
`runner/tests/test_bluemonday_corpus.py` replays it.

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

Q74 does not copy the capture. The capture stays at
`docs/reports/live-2026-10-25/`. The seeds are invented ids
under the corpus secret.

Not started: the mutation survivors, and any further live
capture the conductor has not named.
