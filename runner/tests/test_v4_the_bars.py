#!/usr/bin/env python3
"""The bars: what a job can use, and what stops it.

docs/infrastructure-documents/proofs/v4-the-bars.md takes the small
case, scripts of at most 100 bytes, and asks what is solved there.
Its answer: the whole language of the shell is present at 100
bytes, so no cap on a script's size is a bar on what a job uses.
What is solved is the list of quantities a job can use, each with
the bar that stops it, and that list has no size in it.

This module holds the page's census of the shell's constructs,
the 5 quantities with the shortest script that asks for each
without end, the bars as the running code sets them on each
system, and finding F17: the runner holds all that a job writes.

No script that asks without end is handed to a shell here, not
even to a shell's syntax check. Each of them is built only of
constructs the census reads in a form that does nothing.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_at_a_bound as RUNG  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-bars.md")
LINUX = sys.platform.startswith("linux")
OWN = "bash's own"

# The shell's constructs: (family, name, a short script that holds
# the construct and does nothing, a pattern that finds the
# construct in a text). The families are the sections of the
# shell's grammar in POSIX, and bash's additions.
CONSTRUCTS = (
    ("quoting", "a backslash", ": \\a", r"\\"),
    ("quoting", "single quotes", ": 'a'", r"'"),
    ("quoting", "double quotes", ': "a"', r'"'),
    ("expansion", "a tilde", ": ~", r"~"),
    ("expansion", "a parameter", ": $a",
     r"\$(?:[A-Za-z_]\w*|\{[A-Za-z_]\w*\})"),
    ("expansion", "a parameter with an operator", ": ${a:-b}",
     r"\$\{\w+[:#%?+=-]"),
    ("expansion", "a special parameter", ": $?", r"\$[?$!#@*0-9-]"),
    ("expansion", "a command substitution", ": $(:)", r"\$\((?!\()"),
    ("expansion", "backquotes", ": `:`", r"`"),
    ("expansion", "arithmetic", ": $((1))", r"\$\(\("),
    ("expansion", "a pattern for file names", ": *", r"[*?\[]"),
    ("redirection", "input", ": <f", r"(?<!<)<(?![<&>(])"),
    ("redirection", "output", ": >f", r"(?<![>&<])>(?![>&|(])"),
    ("redirection", "output over a guard", ": >|f", r">\|"),
    ("redirection", "appended output", ": >>f", r">>"),
    ("redirection", "a here-document", ":<<a\na", r"(?<!<)<<(?!<)"),
    ("redirection", "a copied input", ": <&0", r"<&"),
    ("redirection", "a copied output", ": >&2", r">&"),
    ("redirection", "reading and writing", ": <>f", r"<>"),
    ("simple command", "a command", ":", r"\w|:"),
    ("simple command", "an assignment", "a=b",
     r"(?:^|[;&|\s])[A-Za-z_]\w*="),
    ("pipeline", "a pipe", ":|:", r"(?<!\|)\|(?![|&])"),
    ("pipeline", "a negation", "! :", r"(?:^|[;&|(]\s*)!\s"),
    ("list", "and", ":&&:", r"&&"),
    ("list", "or", ":||:", r"\|\|"),
    ("list", "a sequence", ":;:", r";(?!;)"),
    ("list", "an asynchronous command", ":&",
     r"(?<![&>|<])&(?![&>])"),
    ("compound command", "a subshell", "(:)", r"(?<![$(<>=\w])\((?![()])"),
    ("compound command", "a group", "{ :;}", r"\{\s"),
    ("compound command", "for", "for i do :;done", r"\bfor\b"),
    ("compound command", "case", "case a in esac", r"\bcase\b"),
    ("compound command", "if", "if :;then :;fi", r"\bif\b"),
    ("compound command", "while", "while :;do :;done", r"\bwhile\b"),
    ("compound command", "until", "until :;do :;done", r"\buntil\b"),
    ("function", "a function", "f(){ :;}", r"\w\(\)"),
    ("special built-in", "break", "break", r"\bbreak\b"),
    ("special built-in", "colon", ":", r"(?:^|[\s;&|(]):(?:$|[\s;&|)])"),
    ("special built-in", "continue", "continue", r"\bcontinue\b"),
    ("special built-in", "dot", ". f", r"(?:^|[;&|(]\s*)\.\s"),
    ("special built-in", "eval", "eval :", r"\beval\b"),
    ("special built-in", "exec", "exec :", r"\bexec\b"),
    ("special built-in", "exit", "exit", r"\bexit\b"),
    ("special built-in", "export", "export a", r"\bexport\b"),
    ("special built-in", "readonly", "readonly a", r"\breadonly\b"),
    ("special built-in", "return", "return", r"\breturn\b"),
    ("special built-in", "set", "set a", r"\bset\b"),
    ("special built-in", "shift", "shift", r"\bshift\b"),
    ("special built-in", "times", "times", r"\btimes\b"),
    ("special built-in", "trap", "trap : 0", r"\btrap\b"),
    ("special built-in", "unset", "unset a", r"\bunset\b"),
    (OWN, "a brace expansion", ": {a,b}", r"\{[^}\s]*,[^}\s]*\}"),
    (OWN, "a test in double brackets", "[[ a ]]", r"\[\["),
    (OWN, "arithmetic as a command", "((1))", r"(?<!\$)\(\("),
    (OWN, "an array", "a=(b)", r"=\("),
    (OWN, "a process substitution", ": <(:)", r"[<>]\("),
    (OWN, "a here-string", ": <<<a", r"<<<"),
    (OWN, "the word function", "function f { :;}", r"\bfunction\b"),
    (OWN, "select", "select i do :;done", r"\bselect\b"),
    (OWN, "for with 3 expressions", "for((;;));do :;done",
     r"\bfor\s*\(\("),
    (OWN, "a coprocess", "coproc :", r"\bcoproc\b"),
    (OWN, "the word time", "time :", r"\btime\b"),
)

# What the machine M is built of: the constructs its 22 atoms and
# 4 joiners use.
USED_BY_M = (
    "single quotes", "double quotes", "a parameter",
    "a command substitution", "arithmetic", "output", "a command",
    "a pipe", "and", "or", "a sequence", "a subshell", "if", "colon",
    "a brace expansion")

# The 5 quantities: (quantity, the shortest script this seat found
# that asks for it without end, the constructs it is built of).
# None of these is handed to a shell in this module.
QUANTITIES = (
    ("time", "while :;do :;done",
     ("while", "colon", "a sequence", "a command")),
    ("output", "yes", ("a command",)),
    ("processes", "f(){ f|f&};f",
     ("a function", "a group", "a pipe", "an asynchronous command",
      "a sequence", "a command")),
    ("memory", ": $(yes)", ("colon", "a command substitution",
                           "a command")),
    ("disk", "yes>f", ("a command", "output")),
)

# The ladder of finding F17, as measured for the page: the bytes
# a job wrote, and how far the runner's memory at its highest
# stood above a runner whose job wrote nothing, in kilobytes.
# Plain letters, then a byte that is not text.
LADDER = {
    "a": ((14930352, 43412), (24157817, 70488), (39088169, 114216),
          (63245986, 185632)),
    "\\377": ((14930352, 58000), (24157817, 94240), (39088169, 152504),
              (63245986, 246772)),
}

HELD = r"""
import json, re, sys
sys.path.insert(0, %(root)r)
from runner.tests import test_v4_at_a_bound as RUNG
size, byte = int(sys.argv[1]), sys.argv[2]
payload, job_id = RUNG.honest_job()
script = ":" if not size else (
    "head -c %%d /dev/zero | tr '\\0' '%%s'" %% (size, byte))
got, _where = RUNG.ask_the_runner(
    payload, job_id, script, extra=dict(RUNG.OFF))
with open("/proc/self/status") as status:
    peak = int(re.search(r"VmHWM:\s+(\d+) kB", status.read()).group(1))
print(json.dumps({
    "peak": peak, "exit": got.get("exit_code"), "view": got.get("view"),
    "digest": got.get("output_digest")}))
"""


def held(size, byte="a"):
    """1 job that writes `size` bytes and stops, through the real
    gate and the real execution, in a runner of its own: what
    that runner's memory reached, in kilobytes, and the result.
    The reading is the kernel's high-water mark of the process
    (VmHWM), which starts again when the runner starts."""
    done = subprocess.run(
        [sys.executable, "-c", HELD % {"root": ROOT}, str(size), byte],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return json.loads(done.stdout.decode("utf-8").strip().split("\n")[-1])


def reads(shell, script):
    """Whether the shell's syntax check accepts the script. The
    check reads; it runs nothing."""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "s")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(script)
        done = subprocess.run(
            [shell, "-n", path], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30)
    return done.returncode == 0


def source(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


class TheWholeLanguageAt100Bytes(unittest.TestCase):
    """Every construct has a short script, so 100 bytes hold any
    5 of them together."""

    def test_the_texts_of_100_bytes_cannot_be_listed(self):
        self.assertEqual(241, len(str(256 ** 100)))

    def test_the_census_is_61_constructs_in_10_families(self):
        self.assertEqual(61, len(CONSTRUCTS))
        self.assertEqual(61, len({name for _f, name, _s, _p in CONSTRUCTS}))
        families = []
        for family, _name, _script, _pattern in CONSTRUCTS:
            if family not in families:
                families.append(family)
        self.assertEqual(
            ["quoting", "expansion", "redirection", "simple command",
             "pipeline", "list", "compound command", "function",
             "special built-in", OWN], families)
        counts = [sum(1 for row in CONSTRUCTS if row[0] == family)
                  for family in families]
        self.assertEqual([3, 8, 8, 2, 2, 4, 7, 1, 15, 11], counts)
        # 50 are POSIX's, 11 are bash's additions.
        self.assertEqual(50, sum(counts[:-1]))

    def test_each_script_holds_its_construct(self):
        for _family, name, script, pattern in CONSTRUCTS:
            self.assertTrue(re.search(pattern, script), name)

    def test_no_construct_needs_more_than_19_bytes(self):
        sizes = sorted((len(script.encode("utf-8")), name)
                       for _f, name, script, _p in CONSTRUCTS)
        self.assertEqual((19, "for with 3 expressions"), sizes[-1])
        self.assertEqual(
            [18, 17, 17, 16], [size for size, _name in sizes[-5:-1]][::-1])
        # The longest in POSIX's own grammar: 17 bytes.
        self.assertEqual(17, max(
            len(script) for family, _n, script, _p in CONSTRUCTS
            if family != OWN))
        # Any 5 constructs, each on a line of its own, fit in 100
        # bytes. Not any 6.
        longest = [size for size, _name in sizes]
        self.assertEqual(91, sum(longest[-5:]) + 4)
        self.assertLessEqual(sum(longest[-5:]) + 4, 100)
        self.assertEqual(107, sum(longest[-6:]) + 5)

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_bash_reads_every_script_and_dash_reads_posix_s(self):
        for family, name, script, _pattern in CONSTRUCTS:
            self.assertTrue(reads("bash", script), name)
            if family != OWN:
                self.assertTrue(reads("dash", script), name)
        # And 2 that are not scripts, so the check is seen to refuse.
        self.assertFalse(reads("bash", "if :;then"))
        self.assertFalse(reads("dash", "(:"))

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_the_5_longest_are_read_together(self):
        longest = sorted(
            (script for _f, _n, script, _p in CONSTRUCTS),
            key=lambda script: (len(script), script))[-5:]
        together = "\n".join(longest)
        self.assertEqual(91, len(together))
        self.assertTrue(reads("bash", together))

    def test_the_machine_m_uses_15_of_the_61(self):
        texts = tuple(RUNG.ATOMS) + tuple(RUNG.JOINERS)
        self.assertEqual((22, 4), (len(RUNG.ATOMS), len(RUNG.JOINERS)))
        used = tuple(name for _f, name, _s, pattern in CONSTRUCTS
                     if any(re.search(pattern, text) for text in texts))
        self.assertEqual(sorted(USED_BY_M), sorted(used))
        self.assertEqual(15, len(used))
        # No loop, no function and no asynchronous command is in
        # M: nothing in it repeats.
        for absent in ("while", "until", "for", "a function",
                       "an asynchronous command", "eval", "dot"):
            self.assertNotIn(absent, used)


class NoCapOnSizeIsABar(unittest.TestCase):
    """For each quantity a script of at most 17 bytes asks for it
    without end."""

    def test_the_5_scripts_and_their_sizes(self):
        self.assertEqual(
            [("time", 17), ("output", 3), ("processes", 12),
             ("memory", 8), ("disk", 5)],
            [(quantity, len(script)) for quantity, script, _b in QUANTITIES])
        self.assertEqual(45, sum(len(s) for _q, s, _b in QUANTITIES))

    def test_each_is_built_only_of_constructs_the_census_reads(self):
        patterns = {name: pattern for _f, name, _s, pattern in CONSTRUCTS}
        for quantity, script, built_of in QUANTITIES:
            for name in built_of:
                self.assertTrue(re.search(patterns[name], script),
                                (quantity, name))
            found = sorted(name for name, pattern in patterns.items()
                           if re.search(pattern, script))
            self.assertEqual(sorted(built_of), found, quantity)

    def test_the_script_s_own_cap_admits_all_5_at_any_setting(self):
        # The gate's bound on a script is a count of bytes. All 5
        # pass a bound of 17, and so they pass 100, 5,000 and the
        # default.
        payload, job_id = RUNG.honest_job()
        for _quantity, script, _built in QUANTITIES:
            for cap in (17, 100, 5000, 1048576):
                went, _notes = RUNG.admitted(payload, job_id, script, cap)
                self.assertTrue(went, (script, cap))
        went, _notes = RUNG.admitted(
            payload, job_id, QUANTITIES[0][1], 16)
        self.assertFalse(went)

    def test_a_reading_of_the_text_is_not_a_bar(self):
        # The judge is the runner's optional reading of a job's
        # text, and the protocol calls it a judgment and not a
        # proof. It names 1 spelling of the script that forks
        # without end. The 12 bytes above are another spelling.
        # Nothing is run: the judge reads.
        runner = RUNG.RUNNER
        known = ":(){ :|:& };:"
        verdict, reasons = runner.judge_job(
            {"judge": "enforce"}, {"script": known})
        self.assertEqual(("fail", ["denylist: " + known]),
                         (verdict, reasons))
        verdict, reasons = runner.judge_job(
            {"judge": "enforce"}, {"script": QUANTITIES[2][1]})
        self.assertEqual(("pass", []), (verdict, reasons))


class TheBarsAsTheCodeSetsThem(unittest.TestCase):
    """The table of bars on the page, read from the running code."""

    def test_time_has_a_bar_on_every_system(self):
        text = source("runner", "ops", "exec.py")
        self.assertIn("timeout = min(max(timeout, 1), 3600)", text)
        self.assertEqual(300, RUNG.RUNNER._default_timeout_sec({}))
        # The job's own figure comes first, and the owner's is
        # used where the job names none: a default, and not a
        # ceiling.
        self.assertIn(
            'timeout = int(job.get("timeout_sec") or '
            '_runner()._default_timeout_sec(cfg))', text)
        # A key's policy may cap that key's jobs: C14.
        self.assertIn('"max_timeout_sec"',
                      source("runner", "wire", "verify.py"))

    def test_the_constraint_spec_names_1_of_these_bars_in_part(self):
        spec = source("docs", "infrastructure-documents", "proofs",
                      "constraints.md")
        self.assertIn("the timeout it\n  can ask for", spec)
        for word in ("max_output_bytes", "process_memory_bytes",
                     "job_processes", "tmp_bytes", "rctl", "Job Object",
                     "ulimit"):
            self.assertNotIn(word, spec, word)
        self.assertNotIn("3600 seconds", spec.replace(
            "untouched for at least 3600 seconds", ""))

    def test_what_a_result_carries_has_a_bar(self):
        text = source("runner", "ops", "exec.py")
        self.assertIn(
            'max_out = _confval.integer(cfg.get("max_output_bytes"), '
            '100000, lo=1)', text)

    def test_what_the_runner_holds_while_a_job_runs_has_none(self):
        # The whole of both streams is read, and cut afterwards.
        text = source("runner", "ops", "exec.py")
        read = text.index("outs, errs = proc.communicate(timeout=timeout)")
        cut = text.index("stdout, trunc_out = stdout[:max_out], True")
        self.assertLess(read, cut)
        between = text[read:cut]
        self.assertIn('outs.decode("utf-8", errors="replace")', between)
        self.assertNotIn("max_out", between.replace(
            "if len(stdout) > max_out:", ""))

    def test_the_linux_sandbox_sets_no_bar_on_the_other_3(self):
        text = source("runner", "guard", "sandbox.py")
        for word in ("setrlimit", "RLIMIT", "prlimit", "ulimit", "cgroup",
                     "pids.max", "memory.max", "size="):
            self.assertNotIn(word, text, word)
        self.assertIn('"--tmpfs", "/tmp"', text)

    def test_the_other_3_systems_each_set_some(self):
        mib = 1024 * 1024
        freebsd = source("runner", "guard", "freebsd_confine.py")
        for line in ("DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024",
                     "DEFAULT_TMP_BYTES = 512 * 1024 * 1024",
                     "DEFAULT_JOB_MEMORY_BYTES = 2 * 1024 * 1024 * 1024",
                     "DEFAULT_JOB_PROCESSES = 256",
                     "DEFAULT_JOB_USER_PROCESSES = 256",
                     '"jail:%s:maxproc:deny=%d"',
                     '"jail:%s:vmemoryuse:deny=%d"'):
            self.assertIn(line, freebsd, line)
        macos = source("runner", "guard", "macos_confine.py")
        self.assertIn("DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024",
                      macos)
        windows = source("runner", "guard", "windows_confine.py")
        self.assertIn("DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024",
                      windows)
        self.assertIn("info.JobMemoryLimit = int(memory_bytes)", windows)
        # A count of processes is in the structure and is not set.
        self.assertIn('("ActiveProcessLimit", wintypes.DWORD)', windows)
        self.assertNotIn("JOB_OBJECT_LIMIT_ACTIVE_PROCESS", windows)
        self.assertEqual(536870912, 512 * mib)

    def test_no_system_sets_a_bar_on_the_folder_a_job_writes(self):
        for name in ("sandbox.py", "freebsd_confine.py",
                     "macos_confine.py", "windows_confine.py"):
            text = source("runner", "guard", name)
            for word in ("quota", "RLIMIT_FSIZE", "filesize"):
                self.assertNotIn(word, text, (name, word))


class FindingF17TheHeldOutput(unittest.TestCase):
    """The runner holds all that a job writes: 3 bytes of its own
    memory for each byte, 4 where the bytes are not text."""

    def test_the_ladder_on_the_page(self):
        for byte, low, high in (("a", 2.95, 3.05), ("\\377", 3.95, 4.05)):
            shares = [above * 1024 / size for size, above in LADDER[byte]]
            self.assertEqual(shares, sorted(shares), byte)
            self.assertTrue(low <= shares[0] and shares[-1] <= high,
                            (byte, shares))
        self.assertEqual(
            (["2.98", "2.99", "2.99", "3.01"],
             ["3.98", "3.99", "4.00", "4.00"]),
            tuple(["%.2f" % (above * 1024 / size)
                   for size, above in LADDER[byte]]
                  for byte in ("a", "\\377")))
        # The series: steps 36 to 39.
        series = [0, 1]
        while len(series) < 40:
            series.append(series[-1] + series[-2])
        self.assertEqual(series[36:40],
                         [size for size, _above in LADDER["a"]])

    def test_at_the_time_limit(self):
        # A writer here wrote 851 megabytes a second. At 3 bytes
        # held for each, a runner's memory is asked for 2.6
        # gigabytes a second. A job may name 3,600 seconds.
        self.assertEqual("2.6", "%.1f" % (851 * 3 / 1000))
        self.assertEqual("3.1", "%.1f" % (8000 / (851 * 3)))
        self.assertEqual(255, round(851 * 300 / 1000))

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_the_runner_s_memory_grows_with_what_a_job_writes(self):
        base = held(0)
        self.assertEqual((0, "attested"), (base["exit"], base["view"]))
        size = 14930352
        for byte, least, most in (("a", 2, 4), ("\\377", 3, 6)):
            got = held(size, byte)
            self.assertEqual((0, "attested"), (got["exit"], got["view"]))
            above = (got["peak"] - base["peak"]) * 1024
            self.assertTrue(least * size <= above <= most * size,
                            (byte, above / size))
        # What the result carries is under its bar all the same.
        self.assertEqual(96, len(got["digest"]))


class ThePageRecordsTheBars(unittest.TestCase):
    """The figures this module holds are the page's."""

    def test_the_page_states_the_census_the_scripts_and_the_bars(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "61 constructs",
                "None needs more than 19 bytes",
                "any 5 of them fit in 100 bytes together",
                "The machine M uses 15 of the 61",
                "| All | 61 | 19 | 15 |",
                "| Time | `while :;do :;done` | 17 |",
                "| Output | `yes` | 3 |",
                "| Processes | `f(){ f\\|f&};f` | 12 |",
                "| Memory | `: $(yes)` | 8 |",
                "| Disk | `yes>f` | 5 |",
                "| 63,245,986 | 185,632 | 3.01 | 246,772 | 4.00 |",
                "| 14,930,352 | 43,412 | 2.98 | 58,000 | 3.98 |",
                "Finding F17",
                "These are candidates."):
            self.assertIn(stated, page, stated)

    def test_every_family_s_row_is_on_the_page(self):
        page = MODELS._flat(PAGE)
        used = set(USED_BY_M)
        families = []
        for family, _n, _s, _p in CONSTRUCTS:
            if family not in families:
                families.append(family)
        for family in families:
            rows = [row for row in CONSTRUCTS if row[0] == family]
            longest = max(len(row[2]) for row in rows)
            in_m = sum(1 for row in rows if row[1] in used)
            label = family[0].upper() + family[1:]
            stated = "| %s | %d | %d | %d |" % (
                label, len(rows), longest, in_m)
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
