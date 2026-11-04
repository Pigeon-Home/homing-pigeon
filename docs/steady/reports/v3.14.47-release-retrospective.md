# 3.14.47: one cycle, and it published

Written 31-Oct-10:14am-PST/PDT, after 3.14.47 was on the mirrors.
This is the record of that cut. It is not a standing order.

## Did it publish

Yes. GitHub Release `v3.14.47` is not a draft. It was published
at 9:42am (2026-10-31T16:42:32Z). The tag object `347d3993`
points at `f9c545fd18b1e1193ab60f12638fd21460ecd6aa`. The
release API's target is the branch name `main`, not that
commit. The tag object is the commit.

PyPI `pigeon-home-runner` 3.14.47, the wheel and the sdist,
match the GitHub files byte for byte. SourceForge
`homing-pigeon/v3.14.47` has 13 files; `SHA384SUMS` and the
wheel match GitHub byte for byte. GitLab
`pigeon-home/homing-pigeon` release `v3.14.47` has 13 package
links; its `SHA384SUMS` and wheel match GitHub byte for byte.
`sha384sum -c SHA384SUMS` on the GitHub download was 12 lines,
all of them OK. ghcr.io has `v3.14.47` and `latest` as two
indexes. Each is linux/amd64 plus an attestation manifest, and
the two digests differ, because the image workflow was
dispatched twice.

## The clock

Times are PDT.

| When | What | Result |
|---|---|---|
| 9:15am | `f9c545fd` pushed. Branch build [41218830636](https://github.com/Pigeon-Home/homing-pigeon/actions/runs/41218830636). | The nine guard jobs green at 9:27am. |
| 9:29am | Cut [41219896861](https://github.com/Pigeon-Home/homing-pigeon/actions/runs/41219896861). | Tag `v3.14.47` on `f9c545fd`. Main had moved to a bank commit. That commit was not tagged. |
| 9:29am | Tag build [41219918629](https://github.com/Pigeon-Home/homing-pigeon/actions/runs/41219918629). | `build-windows` passed. Release job 9:40–9:42am. |
| 9:42am | GitHub Release published. | PyPI job done 9:42am. SourceForge 9:43am. GitLab 9:43am. |
| 9:46am | This seat's byte check of the three file mirrors. | The bodies matched. |

From the release commit to the published release was
twenty-seven minutes. From a green branch build to the
published release was fifteen. One cycle. Nothing failed.

The two minutes between green and the cut were this seat
confirming the nine jobs and that main had moved. The builds
do not overlap: the tag waits for those nine. They were eleven
and a half minutes, then fourteen. That is the cut.

## What is still wrong, and not changed here

`cut-release` still starts the image workflow in the same step
as the tag build. 3.14.47's tests passed, so the images that
were pushed are the release. `v3.14.45` is still in the
registry with no GitHub release. Holding the image dispatch
until `release` succeeds is the fix. It is not in the 3.15.0
cut either: it does not make a release faster, and the cut
stays on the path that just published.
