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
system, and finding F17: the runner held all that a job wrote.
The closing of F17 is held by test_v4_the_held_output.py. And
findings F18 and F19, open: the Oracle's run tool holds all
that a command writes, and the runner holds the whole diff of a
change job. And finding F20: the runner's watch is a bar on
the processes of a job's tree, 64 at a count, and it is
sampled.

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
from runner.tests import test_v4_the_folder as FOLDER  # noqa: E402
from runner.tests import test_v4_the_ladder as RUNGS  # noqa: E402

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

# The ladder of finding F17, as measured for the page before the
# reader had a bar: the bytes a job wrote, and how far the
# runner's memory at its highest stood above a runner whose job
# wrote nothing, in kilobytes. Plain letters, then a byte that
# is not text.
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


# The ladder of finding F18, as measured for the page: the bytes
# a command wrote through the Oracle's run tool, and how far the
# memory at its highest of the process that ran the tool stood
# above the same process running a command that wrote nothing,
# in kilobytes. Plain letters, then a byte that is not text.
TOOL_LADDER = {
    "a": ((14930352, 29408), (24157817, 47412), (39088169, 76656),
          (63245986, 123876)),
    "\\377": ((14930352, 58532), (24157817, 94460), (39088169, 152868),
              (63245986, 246960)),
}

TOOL = r"""
import json, re, sys, tempfile
sys.path.insert(0, %(root)r)
from runner import runner as RUNNER
size, byte = int(sys.argv[1]), sys.argv[2]
command = ":" if not size else (
    "head -c %%d /dev/zero | tr '\\0' '%%s'" %% (size, byte))
with tempfile.TemporaryDirectory() as folder:
    text = RUNNER._run_oracle_tool(
        "run", {"command": command, "timeout_sec": 60},
        base_dir=folder, cfg={}, tool_mode="full")
with open("/proc/self/status") as status:
    peak = int(re.search(r"VmHWM:\s+(\d+) kB", status.read()).group(1))
print(json.dumps({"peak": peak, "chars": len(text), "head": text[:7]}))
"""


def tool(size, byte="a"):
    """The Oracle's run tool and a command that writes `size`
    bytes and stops, in a process of its own: what that process's
    memory reached, in kilobytes, and what the tool handed back."""
    done = subprocess.run(
        [sys.executable, "-c", TOOL % {"root": ROOT}, str(size), byte],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return json.loads(done.stdout.decode("utf-8").strip().split("\n")[-1])


# The ladder of finding F19, as measured for the page: the random
# bytes written into a change job's tree after its commit, the
# bytes of the diff git made of them, and how far the memory at
# its highest of the process that read the diff stood above the
# same process with nothing written, in kilobytes.
DIFF_LADDER = ((14930352, 19243277, 38192), (24157817, 31136139, 61940),
               (39088169, 50379194, 100060), (63245986, 81515114, 161980))

DIFF = r"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, %(root)r)
from runner.ops import changes as CHANGES
size, kind = int(sys.argv[1]), sys.argv[2]
with tempfile.TemporaryDirectory() as work:
    src = os.path.join(work, CHANGES.SRC)
    os.makedirs(src)
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.test"]
            + list(args), cwd=src, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True)

    git("init", "-q")
    with open(os.path.join(src, "seed.txt"), "w") as handle:
        handle.write("seed\n")
    git("add", "seed.txt")
    git("commit", "-q", "-m", "seed")
    sha = git("rev-parse", "HEAD").stdout.decode().strip()
    if size:
        with open(os.path.join(src, "written.bin"), "wb") as handle:
            left = size
            while left:
                step = min(left, 1 << 20)
                handle.write(os.urandom(step) if kind == "random"
                             else bytes(step))
                left -= step
    CHANGES.write_result_diff(work, sha)
    diff = os.path.getsize(os.path.join(work, CHANGES.RESULT_DIFF))
with open("/proc/self/status") as status:
    peak = int(re.search(r"VmHWM:\s+(\d+) kB", status.read()).group(1))
print(json.dumps({"peak": peak, "diff": diff}))
"""


def diff_held(size, kind="random"):
    """The runner's own reading of a change job's diff, for a tree
    into which `size` bytes were written after the commit, in a
    process of its own: what that process's memory reached, in
    kilobytes, and the size of the diff."""
    done = subprocess.run(
        [sys.executable, "-c", DIFF % {"root": ROOT}, str(size), kind],
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

    def test_what_the_runner_holds_while_a_job_runs_has_a_bar_now(self):
        # Finding F17, closed: both streams come through a reader
        # with a bar, and the cut to the cap comes after it.
        text = source("runner", "ops", "exec.py")
        read = text.index("held = _runner()._held_for_job(max_out)")
        cut = text.index("stdout, trunc_out = stdout[:max_out], True")
        self.assertLess(read, cut)
        self.assertNotIn("proc.communicate(", text[read:cut])
        helpers = source("runner", "ops", "helpers.py")
        self.assertIn("    bound = 4 * chars + 4\n", helpers)
        self.assertIn("        room = self.keep - len(held)\n"
                      "        if room > 0:\n"
                      "            held += chunk[:room]\n", helpers)
        self.assertEqual(400004, RUNG.RUNNER.held_bound(100000))

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
    """The runner held all that a job wrote: 3 bytes of its own
    memory for each byte, 4 where the bytes are not text. With
    the bar it holds a fixed number."""

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
    def test_the_runner_s_memory_no_longer_grows_with_a_job_s_writing(
            self):
        # At step 36 of the series the runner held 43,412
        # kilobytes of text above its base, and 58,000 where the
        # bytes are not text. With the bar: under 4,000.
        base = held(0)
        self.assertEqual((0, "attested"), (base["exit"], base["view"]))
        size = 14930352
        for byte in ("a", "\\377"):
            got = held(size, byte)
            self.assertEqual((0, "attested"), (got["exit"], got["view"]))
            self.assertLess(got["peak"] - base["peak"], 4000, byte)
        # What the result carries is what it was.
        self.assertEqual(96, len(got["digest"]))


class FindingF19TheDiffOfAChangeJob(unittest.TestCase):
    """The runner holds the whole diff of a change job: 2.6 bytes
    of memory for each byte the run wrote into the tree that git
    cannot press. Open."""

    def test_the_diff_is_read_whole_and_written_afterwards(self):
        text = source("runner", "ops", "changes.py")
        read = text.index(
            '        r = subprocess.run(["git", "diff", "--binary", sha, '
            '"--"], cwd=src,\n'
            "                           capture_output=True, timeout=60)\n")
        write = text.index("            fh.write(data)\n")
        self.assertLess(read, write)

    def test_the_ladder_on_the_page(self):
        self.assertEqual(["2.62", "2.63", "2.62", "2.62"], [
            "%.2f" % (above * 1024 / size)
            for size, _diff, above in DIFF_LADDER])
        self.assertEqual([size for size, _above in LADDER["a"]],
                         [size for size, _diff, _above in DIFF_LADDER])
        page = MODELS._flat(PAGE)
        self.assertIn("## Finding F19: the diff of a change job is held "
                      "whole", page)
        for size, diff_bytes, above in DIFF_LADDER:
            self.assertIn("| %s | %s | %s | %.2f |" % (
                format(size, ","), format(diff_bytes, ","),
                format(above, ","), above * 1024 / size), page)
            # Random bytes come out of git 1.29 times as large.
            self.assertEqual("1.29", "%.2f" % (diff_bytes / size))
        for stated in ("Git has 60 seconds for it",
                       "made a diff of 79,428 bytes, and the runner held "
                       "1,092 kilobytes",
                       "It is filed, and not closed here."):
            self.assertIn(stated, page, stated)

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_the_runner_s_memory_grows_with_what_a_run_wrote(self):
        base = diff_held(0)
        self.assertEqual(0, base["diff"])
        size = 14930352
        got = diff_held(size)
        above = (got["peak"] - base["peak"]) * 1024
        self.assertTrue(2 * size <= above <= 3.5 * size, above / size)
        self.assertTrue(1.2 * size <= got["diff"] <= 1.4 * size,
                        got["diff"] / size)
        # Bytes that git presses small cost next to nothing.
        got = diff_held(size, "zero")
        self.assertLess(got["peak"] - base["peak"], 4000)
        self.assertLess(got["diff"], 100000)


class FindingF18TheOraclesRunTool(unittest.TestCase):
    """The Oracle's run tool holds all that a command writes: 2
    bytes of memory for each byte of text, or 3, and 4 where the
    bytes are not text, or 3. Open: the day it is closed, this
    class is turned as the class above was."""

    def test_the_tool_reads_all_and_cuts_afterwards(self):
        text = source("runner", "ops", "oracle_ops.py")
        tool_text = text[text.index('    if name == "run":'):]
        self.assertIn("        timeout = max(1, min(timeout, 120))\n",
                      tool_text)
        read = tool_text.index(
            "command, shell=True, capture_output=True,")
        cut = tool_text.index("        if len(blob) > 8000:\n")
        self.assertLess(read, cut)
        # The 2 streams are joined and stripped before the cut.
        self.assertIn(
            '        blob = (out + ("\\n" + err if err else "")).strip()\n',
            tool_text[read:cut])
        # The default mode allows the tool, and the code counts
        # the model as untrusted input.
        self.assertEqual("full", RUNG.RUNNER._oracle_tool_mode({}))
        self.assertIn("The model is untrusted input here", text)

    def test_the_ladder_on_the_page(self):
        self.assertEqual(
            (["2.02", "2.01", "2.01", "2.01"],
             ["4.01", "4.00", "4.00", "4.00"]),
            tuple(["%.2f" % (above * 1024 / size)
                   for size, above in TOOL_LADDER[byte]]
                  for byte in ("a", "\\377")))
        self.assertEqual([size for size, _above in LADDER["a"]],
                         [size for size, _above in TOOL_LADDER["a"]])
        page = MODELS._flat(PAGE)
        self.assertIn("## Finding F18: the Oracle's run tool reads the "
                      "same way", page)
        for (size, text_kb), (_size, other_kb) in zip(
                TOOL_LADDER["a"], TOOL_LADDER["\\377"]):
            self.assertIn("| %s | %s | %.2f | %s | %.2f |" % (
                format(size, ","), format(text_kb, ","),
                text_kb * 1024 / size, format(other_kb, ","),
                other_kb * 1024 / size), page)
        for stated in ("for up to 120 seconds",
                       "the first 8,000 characters",
                       "was 8,022 characters on every row",
                       "The first row of text read 43,900: 3 bytes for "
                       "each byte",
                       "It is filed, and not closed here."):
            self.assertIn(stated, page, stated)

    @unittest.skipUnless(
        LINUX, "the shells and the runner's memory are read on Linux")
    def test_the_tool_s_memory_grows_with_what_a_command_writes(self):
        base = tool(0)
        self.assertEqual("exit=0\n", base["head"])
        size = 14930352
        # For text the page has 2 bytes for each byte, and 3 in
        # 1 cell of a second sitting: the allocator's to say.
        # For bytes that are not text it has 4, and the server's
        # Linux leg read 2.99 on 2026-11-20: 3, a little short.
        for byte, least, most in (("a", 1.5, 3.5), ("\\377", 2.5, 5.5)):
            got = tool(size, byte)
            above = (got["peak"] - base["peak"]) * 1024
            self.assertTrue(least * size <= above <= most * size,
                            (byte, above / size))
            # What the tool hands back is under its cut all the
            # same: 8,000 characters, the exit line and the mark.
            self.assertEqual(("exit=0\n", 8022),
                             (got["head"], got["chars"]))


class FindingF20TheWatchIsABarOnProcesses(unittest.TestCase):
    """The runner's watch counts the processes of a job's tree
    when the job starts and once each second, and kills a tree
    of more than 64. A bar on every system, and a sampled 1."""

    WATCH = RUNG.RUNNER._remediation

    def asked_once(self, held, cfg=None):
        """The watch asked once of a tree of `held` processes:
        (the tree was killed, what the watch says of it)."""
        killed = []
        with tempfile.TemporaryDirectory() as folder:
            monitor = self.WATCH.JobMonitor(
                self.WATCH.settings(cfg or {}), "job-1", 1, folder,
                kill_fn=lambda extra=None: killed.append(1),
                sampler=lambda root: {pid: (0.0, None)
                                      for pid in range(1, held + 1)})
            monitor.sample_once()
        acted = monitor.outcome["acted"]
        said = acted and self.WATCH.divergence_text(acted["divergence"])
        return bool(killed), said

    def test_the_2_numbers_and_the_mode(self):
        watch = self.WATCH
        self.assertEqual(
            (64, 1.0, "deterministic"),
            (watch.DEFAULT_STORM_CEILING, watch.DEFAULT_SAMPLE_SEC,
             watch.DEFAULT_MODE))
        self.assertIn("process_storm", watch.TRIPWIRE_KINDS)
        set_up = watch.settings({})
        self.assertEqual((64, 1.0, "deterministic"),
                         (set_up["storm_ceiling"], set_up["sample_sec"],
                          set_up["mode"]))
        # Both numbers are the owner's to set.
        set_up = watch.settings({"remediation_storm_ceiling": 8,
                                 "remediation_sample_sec": 0.25})
        self.assertEqual((8, 0.25),
                         (set_up["storm_ceiling"], set_up["sample_sec"]))
        # No system has numbers of its own: they are read in 1
        # place.
        text = source("runner", "oracle", "remediation.py")
        self.assertEqual(1, text.count("DEFAULT_STORM_CEILING = "))
        self.assertEqual(1, text.count("DEFAULT_SAMPLE_SEC = "))
        # The watch counts first and waits after, so its first
        # count is at the job's start.
        loop = text[text.index("    def _run(self):"):
                    text.index("    def _error(self, e):")]
        self.assertLess(loop.index("self.sample_once()"),
                        loop.index('self._stop.wait(self._st["sample_sec"])'))

    def test_64_pass_and_65_are_killed(self):
        self.assertEqual((False, None), self.asked_once(64))
        killed, said = self.asked_once(65)
        self.assertTrue(killed)
        self.assertEqual("process_storm: job tree holds 65 processes, "
                         "past the ceiling of 64", said)
        self.assertEqual((False, None), self.asked_once(1))
        self.assertTrue(self.asked_once(1597)[0])
        # In the watch's off mode nothing is killed.
        self.assertEqual((False, None), self.asked_once(
            65, {"remediation_mode": "off"}))
        # And the owner's ceiling moves the bar.
        self.assertEqual((False, None), self.asked_once(
            65, {"remediation_storm_ceiling": 65}))

    def test_the_ladder_has_rows_that_are_such_a_tree(self):
        # 4 of the 40 rows the place suite runs are 1 pipeline of
        # 1,597 commands: more than 64 at once, by the page's
        # measure, for as long as the row runs.
        rows = [row for row in RUNGS.ladder_rows(17, families=20)
                if len(row[0]) in (55, 1597)]
        self.assertEqual(40, len(rows))
        wide = [atoms for atoms, joiners in rows
                if len(atoms) == 1597 and set(joiners) == {" | "}]
        self.assertEqual(4, len(wide))
        self.assertGreater(1597, 64)

    def test_no_pipeline_of_100_bytes_reaches_the_bar(self):
        # The shell takes 50 commands in 99 bytes, and 51 do not
        # fit in 100.
        self.assertEqual(99, len("|".join([":"] * 50)))
        self.assertGreater(len("|".join([":"] * 51)), 100)
        # M writes a pipe with a space on each side, and its
        # shortest atom is 1 byte: 25 commands in 100 bytes.
        self.assertIn(" | ", RUNG.JOINERS)
        self.assertEqual(":", min(RUNG.ATOMS, key=len))
        self.assertLessEqual(len(" | ".join([":"] * 25)), 100)
        self.assertGreater(len(" | ".join([":"] * 26)), 100)
        # M's 2 atoms that start a process of their own.
        own = [atom for atom in RUNG.ATOMS
               if atom.startswith("(")
               or "$(" in atom.replace("$((", "")]
        self.assertEqual(["echo $(:)", "(echo a)"], own)
        # With the shell, 51 processes at most: under the bar.
        self.assertLessEqual(50 + 1, self.WATCH.DEFAULT_STORM_CEILING)

    @unittest.skipUnless(
        LINUX, "the job's tree is counted on Linux here")
    def test_a_job_that_holds_70_is_killed_and_60_is_not(self):
        payload, job_id = RUNG.honest_job()
        result, _notes, _files = FOLDER.run(
            payload, job_id,
            "for i in $(seq 60); do sleep 3 & done; wait\n", "off")
        self.assertEqual((0, False), (result.get("exit_code"),
                                      "remediation" in result))
        result, notes, _files = FOLDER.run(
            payload, job_id,
            "for i in $(seq 70); do sleep 3 & done; wait\n", "off")
        self.assertEqual(-9, result.get("exit_code"))
        said = result.get("remediation") or {}
        self.assertEqual(("deterministic", "tripwire", "killed"),
                         (said.get("mode"), said.get("authority"),
                          said.get("act")))
        self.assertRegex(
            said.get("divergence", ""),
            r"^process_storm: job tree holds \d+ processes, past the "
            r"ceiling of 64$")
        # It did not run its 3 seconds out.
        self.assertLess(result.get("duration_sec"), 3)

    def test_the_page_states_the_finding(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "## Finding F20, stated before its measure: the watch is "
                "a bar on processes",
                "## F20 measured: a sampled bar at 64 processes",
                "| Processes, by the watch | 64 in the job's tree, the "
                "shell among them, at a count: the tree is killed.",
                "| Processes, by the confinement | no bar |",
                "At most 1,321 to 1,591 at once, on 12 runs.",
                "0 of 40 runs",
                "20 of 20",
                "64: 3 of 3, after 1.03 seconds.",
                "The shell takes 50 commands in 99 bytes. M writes 25 "
                "in 100, with its spaces.",
                "63 sleeps and the shell are 64, and pass.",
                "That row writes nothing.",
                "**It is sampled.**",
                "It asks for 2.5 now."):
            self.assertIn(stated, page, stated)


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
                "Finding F17, closed on this branch.",
                "Findings F18 and F19, open.",
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
