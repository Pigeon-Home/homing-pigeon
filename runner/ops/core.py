# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Core: the production runner, named as a set of files.

"Core" is a project feature with a fixed meaning: the stripped
production-runner code set — the code that runs, with no unit
tests, no test harnesses and nothing superfluous. When project
talk says "test core in this way", the set under test is the
set named here.

The set was first assembled on 2026-11-04 for a big-window
review (the Gemini conformance pass): the tree was cut down to
the runner alone so the whole of it fit 1 model window beside
the documentation. As assembled it held 133 files, zipped to
701,403 bytes, and the reviewing model's own counter (Gemini
countTokens) measured it at 619,845 tokens.

3 of those 133 files were the suite's own runners —
runner/tools/run_tests_parallel.py, run_tests_shuffled.py and
run_tests_windows_sim.py. Each exists only to run the unit
tests; none of them is runner code, and the definition of core
(no test harnesses) leaves them out. CORE_FILES below is
therefore the canonical list, at 130 files. This module itself
is not in the list either: the list names the set as assembled
for the 2026-11-04 pass, and this module is the tooling that
carries the list, written after that pass.

The token figures stay distinct and named, here and in the
CLI output:

- GEMINI_COUNT_TOKENS (619,845) is the Gemini countTokens
  measure of the set as assembled (133 files), 2026-11-04.
- The project estimator (runner/ops/version4.py's
  count_text_tokens) counts the canonical 130-file list; the
  CLI prints its figure live. The estimator is not a BPE
  tokenizer, and the 2 figures are not interchangeable: the
  same estimator counts the as-assembled 133-file set at
  574,048, not 619,845.

Lines are counted live the same way, never recorded for the
canonical list: the as-assembled set runs to 54,427 lines,
48,981 of them non-blank (AS_ASSEMBLED_LINES and
AS_ASSEMBLED_NONBLANK_LINES below), and the CLI prints the
canonical list's own line count beside its token counts.

The headline inside those numbers: the runner proper,
runner/runner.py itself, is 6,578 lines; the core around it
is the rest. The as-assembled set's per-part line counts are
recorded in AS_ASSEMBLED_PART_LINES below; the CLI computes
and prints the canonical list's per-part counts live, and
the 2 breakdowns differ in exactly 1 part — runner/tools,
where the 3 excluded suite runners account for 784 lines.

Everything except main is a pure function of the tree at a
root. The zip build is deterministic — entries in list order,
a fixed timestamp (1980-01-01, the zip epoch), a fixed
compression level — so 2 builds of the same tree are
byte-identical. A listed file missing under the root is an
error (FileNotFoundError), never a silent skip: the list is
canonical, and drift between the list and the tree is a defect
to surface, not to paper over.

The CLI:

    python3 runner/ops/core.py [--root .]
        Print the core's file count, its line count (with the
        runner proper's own count and the per-part breakdown),
        its zip size in bytes and its token counts: the
        estimator's live count of the canonical list, and the
        recorded Gemini count of the set as assembled.

    python3 runner/ops/core.py build OUT.zip [--root .]
        Write the deterministic zip to OUT.zip, then print the
        same figures.
"""

import io
import os
import sys
import zipfile
from typing import List, Optional, Sequence, Tuple

try:
    from . import version4  # package: runner.ops.core
except ImportError:  # plain script: python3 runner/ops/core.py
    import version4  # noqa: F401  (sibling module, on sys.path)

# The set as assembled for the 2026-11-04 big-window pass, and
# the reviewing model's own measure of it. Recorded constants:
# they describe that pass, not the canonical list below.
AS_ASSEMBLED_FILES = 133
AS_ASSEMBLED_ZIP_BYTES = 701403
AS_ASSEMBLED_LINES = 54427
AS_ASSEMBLED_NONBLANK_LINES = 48981
# The as-assembled set's lines, part by part; the parts sum
# to AS_ASSEMBLED_LINES. A part is a folder under runner/, or
# a file standing directly under runner/ as its own part.
AS_ASSEMBLED_PART_LINES = {
    "runner/ops": 16880,
    "runner/tools": 8650,
    "runner/wire": 8250,
    "runner/runner.py": 6578,
    "runner/oracle": 4987,
    "runner/transport_extensions": 2771,
    "runner/guard": 2580,
    "runner/cloud": 1998,
    "runner/hosting": 1700,
    "runner/__init__.py": 23,
    "runner/_version.py": 10,
}
GEMINI_COUNT_TOKENS = 619845
GEMINI_COUNT_DATE = "2026-11-04"

# The canonical core: the as-assembled set minus the 3 suite
# runners named in the module docstring. Sorted, duplicate-free,
# every path under runner/. Pinned by runner/tests/test_core.py.
CORE_FILES = (
    "runner/__init__.py",
    "runner/_version.py",
    "runner/cloud/__init__.py",
    "runner/cloud/send_dtls.py",
    "runner/cloud/send_job.py",
    "runner/guard/__init__.py",
    "runner/guard/atomicio.py",
    "runner/guard/confval.py",
    "runner/guard/defaulted.py",
    "runner/guard/extreview.py",
    "runner/guard/filenames.py",
    "runner/guard/panic.py",
    "runner/guard/sandbox.py",
    "runner/guard/security.py",
    "runner/guard/textutil.py",
    "runner/hosting/__init__.py",
    "runner/hosting/base.py",
    "runner/hosting/billing.py",
    "runner/hosting/bootstrap.py",
    "runner/hosting/cli.py",
    "runner/hosting/digitalocean.py",
    "runner/hosting/fly.py",
    "runner/hosting/github_actions.py",
    "runner/hosting/hetzner.py",
    "runner/hosting/httpdoor.py",
    "runner/hosting/inventory.py",
    "runner/ops/__init__.py",
    "runner/ops/attest.py",
    "runner/ops/auditreport.py",
    "runner/ops/av.py",
    "runner/ops/cancel.py",
    "runner/ops/changes.py",
    "runner/ops/cli.py",
    "runner/ops/context.py",
    "runner/ops/exec.py",
    "runner/ops/extensions.py",
    "runner/ops/extsources.py",
    "runner/ops/firewall.py",
    "runner/ops/handlers.py",
    "runner/ops/harness.py",
    "runner/ops/helpers.py",
    "runner/ops/install.py",
    "runner/ops/live.py",
    "runner/ops/local_test.py",
    "runner/ops/mail.py",
    "runner/ops/main.py",
    "runner/ops/misc.py",
    "runner/ops/oracle_ops.py",
    "runner/ops/oracle_page.py",
    "runner/ops/oracle_server.py",
    "runner/ops/oracle_tools.py",
    "runner/ops/paths.py",
    "runner/ops/policy.py",
    "runner/ops/poll.py",
    "runner/ops/posture.py",
    "runner/ops/queries.py",
    "runner/ops/recipes.py",
    "runner/ops/remediation_ops.py",
    "runner/ops/sensors.py",
    "runner/ops/setup.py",
    "runner/ops/startup.py",
    "runner/ops/tables.py",
    "runner/ops/version4.py",
    "runner/ops/watch.py",
    "runner/ops/windows.py",
    "runner/ops/winlog.py",
    "runner/oracle/__init__.py",
    "runner/oracle/detection.py",
    "runner/oracle/dri.py",
    "runner/oracle/learning.py",
    "runner/oracle/opinion.py",
    "runner/oracle/personal_docs.py",
    "runner/oracle/remediation.py",
    "runner/oracle/resources.py",
    "runner/oracle/review.py",
    "runner/oracle/senses.py",
    "runner/runner.py",
    "runner/tools/ci_run_report.py",
    "runner/tools/ci_scope.py",
    "runner/tools/coverage_gaps.py",
    "runner/tools/coverage_one.py",
    "runner/tools/coverage_targets.py",
    "runner/tools/fetch_upstream.py",
    "runner/tools/first_ping.py",
    "runner/tools/linecov.py",
    "runner/tools/live_capture.py",
    "runner/tools/make_sbom.py",
    "runner/tools/make_snapshot.py",
    "runner/tools/mutation_floor.py",
    "runner/tools/pin_extension_sources.py",
    "runner/tools/platform_plan.py",
    "runner/tools/regression_guard.py",
    "runner/tools/regression_pass.py",
    "runner/tools/repair_script_imports.py",
    "runner/tools/rig_bank.py",
    "runner/tools/rig_resources.py",
    "runner/tools/skip_guard.py",
    "runner/tools/soak.py",
    "runner/tools/stamp_audit.py",
    "runner/tools/stamp_provenance.py",
    "runner/tools/stdlib_coverage.py",
    "runner/tools/suite_wall_clock.py",
    "runner/tools/switch_proofs.py",
    "runner/tools/upgrade_proof.py",
    "runner/tools/windows_surface.py",
    "runner/transport_extensions/__init__.py",
    "runner/transport_extensions/channel.py",
    "runner/transport_extensions/dtls/__init__.py",
    "runner/transport_extensions/dtls/__main__.py",
    "runner/transport_extensions/email/__init__.py",
    "runner/transport_extensions/email/__main__.py",
    "runner/transport_extensions/file/__init__.py",
    "runner/transport_extensions/file/__main__.py",
    "runner/transport_extensions/nats/__init__.py",
    "runner/transport_extensions/nats/__main__.py",
    "runner/transport_extensions/queues/__init__.py",
    "runner/transport_extensions/queues/__main__.py",
    "runner/wire/__init__.py",
    "runner/wire/board.py",
    "runner/wire/dtls_mailbox.py",
    "runner/wire/dtlsproto.py",
    "runner/wire/jobcrypto.py",
    "runner/wire/mailbox.py",
    "runner/wire/mlkem.py",
    "runner/wire/oauth.py",
    "runner/wire/platformcard.py",
    "runner/wire/protocol_v2.py",
    "runner/wire/subject.py",
    "runner/wire/transports.py",
    "runner/wire/verify.py",
)

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_ZIP_COMPRESSLEVEL = 9


def _read_core_file(root: str, name: str) -> bytes:
    """One listed file's bytes; a missing file is an error."""
    path = os.path.join(root, name)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        raise FileNotFoundError(
            "core file missing under %r: %s" % (root, name))


def core_zip_bytes(root: str,
                   files: Sequence[str] = CORE_FILES) -> bytes:
    """The deterministic zip of the core files under root.

    Entries are written in the order of `files` (the canonical
    list is sorted), each with the fixed zip-epoch timestamp,
    so 2 builds over the same tree are byte-identical.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w",
                         compression=zipfile.ZIP_DEFLATED,
                         compresslevel=_ZIP_COMPRESSLEVEL) as zf:
        for name in files:
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o600 << 16
            zf.writestr(info, _read_core_file(root, name),
                        compresslevel=_ZIP_COMPRESSLEVEL)
    return buffer.getvalue()


def build_core_zip(root: str, out_path: str,
                   files: Sequence[str] = CORE_FILES) -> int:
    """Write the deterministic core zip to out_path; return its size."""
    data = core_zip_bytes(root, files)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return len(data)


def measure_core_tokens(root: str,
                        files: Sequence[str] = CORE_FILES) -> int:
    """The project estimator's token count of the core under root.

    Sums runner/ops/version4.py's count_text_tokens over the
    listed files — the estimator, not a BPE tokenizer; see the
    module docstring for the recorded Gemini count and why the
    2 figures are kept distinct.
    """
    total = 0
    for name in files:
        data = _read_core_file(root, name)
        total += version4.count_text_tokens(data.decode("utf-8", "replace"))
    return total


def measure_core_lines(root: str,
                       files: Sequence[str] = CORE_FILES
                       ) -> Tuple[int, int]:
    """(total lines, non-blank lines) of the core under root.

    Counted live over the listed files, so the figure stays
    honest as the set changes; the recorded as-assembled
    figures are the constants above. A line is non-blank when
    it holds more than whitespace.
    """
    total = 0
    nonblank = 0
    for name in files:
        data = _read_core_file(root, name)
        lines = data.decode("utf-8", "replace").splitlines()
        total += len(lines)
        nonblank += sum(1 for line in lines if line.strip())
    return (total, nonblank)


def _part_of(name: str) -> str:
    """A core file's part: its folder under runner/, or the file
    itself when it stands directly under runner/."""
    rest = name[len("runner/"):]
    if "/" in rest:
        return "runner/" + rest.split("/")[0]
    return name


def measure_core_lines_by_part(root: str,
                               files: Sequence[str] = CORE_FILES
                               ) -> dict:
    """Line counts of the core under root, part by part.

    Computed live over the listed files, like the other
    measures; the recorded as-assembled breakdown is
    AS_ASSEMBLED_PART_LINES above. The parts sum to
    measure_core_lines' total.
    """
    parts = {}
    for name in files:
        data = _read_core_file(root, name)
        count = len(data.decode("utf-8", "replace").splitlines())
        part = _part_of(name)
        parts[part] = parts.get(part, 0) + count
    return parts


def _figures(root: str) -> List[str]:
    """The CLI's report lines for the tree at root."""
    zip_bytes = len(core_zip_bytes(root))
    total_lines, nonblank_lines = measure_core_lines(root)
    parts = measure_core_lines_by_part(root)
    lines = [
        "core files: %d" % (len(CORE_FILES),),
        "core lines: %d (%d non-blank)" % (total_lines, nonblank_lines),
        "core lines in runner/runner.py: %d"
        % (parts.get("runner/runner.py", 0),),
        "core lines by part:",
    ]
    for part in sorted(parts, key=lambda p: (-parts[p], p)):
        lines.append("  %s: %d" % (part, parts[part]))
    lines += [
        "core zip bytes: %d" % (zip_bytes,),
        "core tokens (project estimator): %d"
        % (measure_core_tokens(root),),
        "core tokens (Gemini countTokens, %s): %d"
        % (GEMINI_COUNT_DATE, GEMINI_COUNT_TOKENS),
    ]
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: print the core's figures; `build` also writes the zip."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = "."
    out = None
    positional = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--root" and i + 1 < len(args):
            root = args[i + 1]
            i += 2
        else:
            positional.append(arg)
            i += 1
    if positional:
        if positional[0] == "build" and len(positional) == 2:
            out = positional[1]
        else:
            print("usage: core.py [--root .] | build OUT.zip [--root .]",
                  file=sys.stderr)
            return 2
    try:
        if out is not None:
            build_core_zip(root, out)
        lines = _figures(root)
    except FileNotFoundError as exc:
        print("core.py: %s" % (exc,), file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
