# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""macOS Seatbelt containment for confinement: the seams.

Backend (runner/guard/macos_confine.py) wired into the
confinement gates. The darwin code cannot execute on this
host, so the gates run through the injection seams: the
startup gate's decision table with a scripted backend, the
argv gate with sys.platform patched, and the spawn seam
against a fake backend. The profile writer, the launcher
shim's argv builder and the trial orchestration are
platform-neutral (they stand above the backend's platform
branch), so they are exercised directly here on any host,
per field, with a bookended fuzz family around the text the
profile generator takes. The live class runs only on a macOS
host (the CI macos-15 and macos-15-intel legs), where the
backend is real.

The honesty pins matter most: no audit record may name a
control the backend does not apply (there is no jail, no
namespace and no App Sandbox entitlement in this backend),
and every failure lands in the refuse direction.
"""
import os
import random
import string
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
from runner.guard import macos_confine as MC
from runner.ops import remediation_ops as REM
from runner.ops import install as INS
from runner.ops import setup as SU


def _ccfg(mode):
    return {"security": {"modes": {"confinement": mode}}}


def _sec(mode, sink):
    sec = mock.Mock()
    sec.sec_mode.return_value = mode

    def _write(base_dir, feature, decision, reason, **kw):
        sink.append({"feature": feature, "decision": decision,
                     "reason": reason, "kw": kw})
    sec.write_audit_entry.side_effect = _write
    return sec


def _backend(problem=None, apply_error=None):
    backend = types.SimpleNamespace()

    def _probe(cfg=None, timeout=15):
        if isinstance(problem, Exception):
            raise problem
        return problem

    backend.macos_startup_problem = _probe
    backend.macos_confinement_problem = _probe
    backend.IS_MACOS_BACKEND = True
    backend.STATUS_CONFINEMENT = MC.STATUS_CONFINEMENT
    backend.spawned = []

    def _spawn(argv, cwd=None, env=None, user=None):
        if apply_error is not None:
            raise apply_error
        proc = types.SimpleNamespace(
            pid=31337, returncode=None,
            confinement_status=backend.STATUS_CONFINEMENT,
            closed=False)
        proc.close = lambda: setattr(proc, "closed", True)
        backend.spawned.append(
            {"argv": argv, "cwd": cwd, "env": env, "user": user,
             "proc": proc})
        return proc

    backend.spawn_confined_process = _spawn
    return backend


class BackendStubTest(unittest.TestCase):
    """The module itself, on a host that is not macOS."""

    def setUp(self):
        if MC.IS_MACOS_BACKEND:
            self.skipTest("the stub exists only off darwin")

    def test_import_is_safe_and_the_probe_refuses(self):
        problem = MC.macos_startup_problem()
        self.assertIsInstance(problem, str)
        self.assertIn("macOS-only", problem)
        self.assertIn("macOS-only", MC.macos_confinement_problem())

    def test_spawn_raises_off_darwin(self):
        with self.assertRaises(RuntimeError):
            MC.spawn_confined_process(["/bin/sh", "-c", "true"])

    def test_the_status_names_exactly_the_three_controls(self):
        self.assertEqual(
            MC.STATUS_CONFINEMENT,
            "macos: seatbelt_profile + no_network + spawn_resource_limits")
        self.assertEqual(
            MC.CONFINEMENT_CONTROLS,
            ("seatbelt_profile", "no_network", "spawn_resource_limits"))

    def test_the_status_names_nothing_the_backend_does_not_apply(self):
        # No jail, no namespace, no App Sandbox entitlement and
        # no Seatbelt memory rule exists in this backend.
        for word in ("jail", "namespace", "sandbox-exec",
                     "app_sandbox", "rctl", "bwrap"):
            self.assertNotIn(word, MC.STATUS_CONFINEMENT)


class ProfileWriterFieldTest(unittest.TestCase):
    """build_profile, one field at a time."""

    def test_the_shape_is_fixed_and_denies_by_default(self):
        profile = MC.build_profile("/work/job1")
        lines = profile.splitlines()
        self.assertEqual(lines[0], "(version 1)")
        self.assertEqual(lines[1], "(deny default)")
        self.assertIn("(deny network*)", lines)
        self.assertNotIn("(allow network", profile)

    def test_workdir_field_is_the_one_writable_tree(self):
        profile = MC.build_profile("/work/job1")
        self.assertIn('(allow file-write* (subpath "/work/job1"))',
                      profile)
        other = MC.build_profile("/work/job2")
        self.assertIn('(subpath "/work/job2")', other)
        self.assertNotIn("/work/job1", other)

    def test_workdir_field_also_reads(self):
        profile = MC.build_profile("/work/job1")
        read_line = [ln for ln in profile.splitlines()
                     if ln.startswith("(allow file-read*")][0]
        self.assertIn('(subpath "/work/job1")', read_line)

    def test_a_var_workdir_names_its_private_canonical_twin(self):
        # Supposition S2: a macOS work directory lives under
        # /var/folders, whose canonical form Seatbelt matches
        # is /private/var/folders; a profile naming only the
        # /var form refuses the staged read and the work
        # write it exists to allow. Both lines carry both.
        profile = MC.build_profile("/var/folders/xx/work")
        read_line = [ln for ln in profile.splitlines()
                     if ln.startswith("(allow file-read*")][0]
        self.assertIn('(subpath "/var/folders/xx/work")', read_line)
        self.assertIn('(subpath "/private/var/folders/xx/work")',
                      read_line)
        write_line = [ln for ln in profile.splitlines()
                      if ln.startswith("(allow file-write*")][0]
        self.assertIn('(subpath "/var/folders/xx/work")', write_line)
        self.assertIn('(subpath "/private/var/folders/xx/work")',
                      write_line)

    def test_a_tmp_workdir_names_its_private_canonical_twin(self):
        profile = MC.build_profile("/tmp/hp-job")
        self.assertIn('(subpath "/private/tmp/hp-job")', profile)

    def test_a_canonical_workdir_gains_no_duplicate_twin(self):
        profile = MC.build_profile("/private/var/folders/xx/work")
        self.assertEqual(
            profile.count('(subpath "/private/var/folders/xx/work")'),
            2)  # once on the read line, once on the write line
        self.assertNotIn('(subpath "/private/private', profile)

    def test_a_var_read_path_names_its_twin_once(self):
        profile = MC.build_profile(
            "/work/job1", read_paths=("/var/data/in",))
        self.assertEqual(profile.count('(subpath "/var/data/in")'), 1)
        self.assertEqual(
            profile.count('(subpath "/private/var/data/in")'), 1)

    def test_the_etc_twin_the_system_trees_carry_is_not_doubled(self):
        profile = MC.build_profile("/work/job1")
        self.assertEqual(profile.count('(subpath "/private/etc")'), 1)
        self.assertEqual(profile.count('(subpath "/etc")'), 1)

    def test_the_root_listing_is_readable_and_nothing_below_it(self):
        # Supposition R2-S1 (docs/steady/security/macos.md):
        # a process reads the root directory's listing as it
        # starts and is aborted when the read is refused --
        # the second live verdict's shape (exit -6, no output,
        # every confined spawn). The grant is the listing
        # only: file-read-data on the literal "/", exactly
        # once, and never a subpath grant on "/", which would
        # make the whole disk readable.
        profile = MC.build_profile("/work/job1")
        self.assertEqual(
            profile.count('(allow file-read-data (literal "/"))'), 1)
        self.assertNotIn('(subpath "/")', profile)

    def test_the_profile_allows_metadata_but_never_more_contents(self):
        # Supposition R3-S1 (docs/steady/security/macos.md):
        # the interpreter's startup realpath() stats every
        # component of its own install path, and Seatbelt
        # governs that stat as file-read-metadata. The root
        # carried only file-read-data (R2-S1's line), so the
        # stat of "/" was refused and the framework
        # interpreter on the CI host exited 1 printing
        # "python: realpath: .../bin/: Operation not
        # permitted" -- with every contents rule granted.
        # The grant is metadata on any path, exactly once:
        # existence, type, size, times, symlink targets --
        # and never a byte of contents, so file-read-data
        # still stands only on the root's literal line and
        # the named subpath trees.
        profile = MC.build_profile("/work/job1")
        self.assertEqual(
            profile.count("(allow file-read-metadata)"), 1)
        self.assertEqual(
            profile.count("(allow file-read-data"), 1)
        self.assertIn('(allow file-read-data (literal "/"))',
                      profile)
        self.assertNotIn("(allow file-read-metadata (subpath",
                         profile)

    def test_the_private_startup_trees_are_system_read_paths(self):
        # Supposition R2-S2: the startup trees under /private
        # that working deny-by-default allowlists carry --
        # the loader's database, the timezone tree
        # /etc/localtime points into, and the tool-selection
        # links /bin/sh reads at every start. Each stands in
        # the named set and in the generated profile, once.
        profile = MC.build_profile("/work/job1")
        for path in ("/private/var/db/dyld",
                     "/private/var/db/timezone",
                     "/private/var/select"):
            self.assertIn(path, MC.SYSTEM_READ_PATHS, path)
            self.assertEqual(
                profile.count('(subpath "%s")' % path), 1, path)

    def test_system_read_paths_field_is_the_named_set(self):
        profile = MC.build_profile("/work/job1")
        for path in MC.SYSTEM_READ_PATHS:
            self.assertIn('(subpath "%s")' % path, profile, path)

    def test_interpreter_field_adds_its_install_prefix(self):
        profile = MC.build_profile(
            "/work/job1", interpreter="/srv/hp-python/bin/python3")
        self.assertIn('(subpath "/srv/hp-python")', profile)

    def test_interpreter_field_inside_the_system_trees_adds_nothing(self):
        bare = MC.build_profile("/work/job1")
        with_interp = MC.build_profile(
            "/work/job1", interpreter="/usr/bin/python3")
        self.assertEqual(bare, with_interp)

    def test_interpreter_field_never_names_a_user_home(self):
        profile = MC.build_profile(
            "/work/job1", interpreter="/Users/alice/bin/python3")
        self.assertIn('(subpath "/Users/alice/bin")', profile)
        self.assertNotIn('(subpath "/Users/alice")', profile)

    def test_interpreter_field_bare_name_must_resolve(self):
        with self.assertRaises(RuntimeError):
            MC.build_profile(
                "/work/job1",
                interpreter="hp-no-such-interpreter-zz9")

    def test_read_paths_field_adds_each_tree_once(self):
        profile = MC.build_profile(
            "/work/job1", read_paths=("/data/inputs", "/data/inputs",
                                      "/data/more"))
        self.assertEqual(profile.count('(subpath "/data/inputs")'), 1)
        self.assertIn('(subpath "/data/more")', profile)

    def test_read_paths_field_rejects_a_relative_path(self):
        with self.assertRaises(RuntimeError):
            MC.build_profile("/work/job1", read_paths=("relative/in",))

    def test_the_writer_is_deterministic(self):
        kw = dict(interpreter="/srv/hp-python/bin/python3",
                  read_paths=("/data/inputs",))
        self.assertEqual(MC.build_profile("/work/job1", **kw),
                         MC.build_profile("/work/job1", **kw))

    def test_workdir_must_be_absolute(self):
        with self.assertRaises(RuntimeError):
            MC.build_profile("work/job1")

    def test_workdir_must_be_a_nonempty_string(self):
        for bad in ("", None, 123, b"/work/job1"):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_profile(bad)

    def test_workdir_must_not_carry_control_characters(self):
        for bad in ("/work/a\x00b", "/work/a\rb", "/work/a\nb",
                    "/work/a\tb", "/work/a\x0bb", "/work/a\x0cb",
                    "/work/a\x7fb"):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_profile(bad)

    def test_a_quote_in_a_path_is_escaped_not_injected(self):
        profile = MC.build_profile('/work/a"b')
        self.assertIn('(subpath "/work/a\\"b")', profile)
        # The escaped quote adds no new line and no new rule:
        # the line count is the fixed shape's.
        self.assertEqual(len(profile.splitlines()),
                         len(MC.build_profile("/work/x").splitlines()))

    def test_a_backslash_in_a_path_is_escaped(self):
        profile = MC.build_profile("/work/a\\b")
        self.assertIn('(subpath "/work/a\\\\b")', profile)

    def test_profile_syntax_characters_in_a_path_stay_inert(self):
        # Parentheses, semicolons and comment marks inside the
        # quoted string cannot start a rule of their own.
        profile = MC.build_profile("/work/a);(deny default)#x")
        self.assertIn('(subpath "/work/a);(deny default)#x")', profile)
        self.assertEqual(
            [ln for ln in profile.splitlines()
             if ln == "(deny default)"], ["(deny default)"])
        self.assertNotIn("(allow network", profile)


class ShimFieldTest(unittest.TestCase):
    """build_shim_argv, one field at a time."""

    def test_the_argv_shape_is_fixed(self):
        out = MC.build_shim_argv(["/bin/echo", "hi"])
        self.assertEqual(out[0], sys.executable)
        self.assertEqual(out[1], "-c")
        self.assertEqual(out[2], MC.LIMIT_SHIM_SOURCE)
        self.assertEqual(out[5:], ["/bin/echo", "hi"])

    def test_memory_field_defaults_to_the_named_ceiling(self):
        out = MC.build_shim_argv(["/bin/true"])
        self.assertEqual(out[3], str(512 * 1024 * 1024))
        self.assertEqual(MC.DEFAULT_PROCESS_MEMORY_BYTES,
                         512 * 1024 * 1024)

    def test_memory_field_carries_the_given_ceiling(self):
        out = MC.build_shim_argv(["/bin/true"], memory_bytes=1024)
        self.assertEqual(out[3], "1024")

    def test_memory_field_rejects_a_non_ceiling(self):
        for bad in (0, -1, True, False, "512", 1.5, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_shim_argv(["/bin/true"], memory_bytes=bad)

    def test_user_field_defaults_to_the_no_user_mark(self):
        self.assertEqual(MC.build_shim_argv(["/bin/true"])[4], "-")

    def test_user_field_carries_the_named_user(self):
        out = MC.build_shim_argv(["/bin/true"], user="nobody")
        self.assertEqual(out[4], "nobody")

    def test_user_field_rejects_an_unnamable_user(self):
        for bad in ("", "a:b", "a\nb", "a\rb", "a\x00b", 123):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_shim_argv(["/bin/true"], user=bad)

    def test_command_field_must_be_a_nonempty_string_list(self):
        for bad in ([], (), "ls", ["/bin/true", 1], [""], None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_shim_argv(bad)

    def test_the_shim_source_sets_limits_then_execs(self):
        src = MC.LIMIT_SHIM_SOURCE
        self.assertIn("RLIMIT_DATA", src)
        self.assertIn("setrlimit", src)
        self.assertIn("os.execvp(argv[0], argv)", src)
        # The limits are set before the exec, in source order.
        self.assertLess(src.index("setrlimit"), src.index("os.execvp"))

    def test_the_shim_names_a_limit_it_cannot_set(self):
        # Supposition R3-S3 (docs/steady/security/macos.md):
        # a shim that cannot set its limit refuses the job
        # -- that fail-closed shape stands -- but it refuses
        # by name, on stderr, so the refusal's text is what
        # a verdict carries, not a bare exception no
        # assertion captured (the round-2 shim-alone leg
        # failed at exit 1 with its cause nowhere in the
        # log). The setrlimit call is wrapped, the marker
        # names the failure, and the shim exits before the
        # exec it guards.
        src = MC.LIMIT_SHIM_SOURCE
        self.assertIn(
            "hp-shim: could not set the data-size limit", src)
        self.assertIn("sys.exit(1)", src)
        self.assertLess(src.index("hp-shim: could not set"),
                        src.index("os.execvp"))

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_shim_refuses_by_name_when_run(self):
        # The named refusal, executed: a ceiling too large
        # for the platform's limit type (2**100) makes the
        # shim's setrlimit fail on any POSIX host -- a
        # merely large or negative value does not, on a
        # host whose inherited hard limit is already
        # unlimited -- and the shim must exit 1 carrying
        # its marker on stderr, having never exec'd the
        # command it guards (the driven command would print
        # a line of its own if it ever ran).
        done = subprocess.run(
            [sys.executable, "-c", MC.LIMIT_SHIM_SOURCE,
             str(2 ** 100), "-", sys.executable, "-c",
             "print('SHIM-RAN-THE-JOB')"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30)
        self.assertEqual(done.returncode, 1)
        self.assertIn(
            b"hp-shim: could not set the data-size limit",
            done.stderr)
        self.assertNotIn(b"SHIM-RAN-THE-JOB", done.stdout)

    def test_the_shim_never_sets_an_address_space_limit(self):
        # Supposition S1 (docs/steady/security/macos.md): a
        # 512 MiB RLIMIT_AS is below the address space every
        # macOS process maps at startup (the loader, the dyld
        # shared cache, the system libraries), so the shim's
        # exec'd interpreter aborted at -6 before any job code
        # in the first live run. The data-size limit is the
        # ceiling this backend applies; the address-space
        # limit must not come back.
        self.assertNotIn("RLIMIT_AS", MC.LIMIT_SHIM_SOURCE)
        self.assertNotIn("RLIMIT_VMEM", MC.LIMIT_SHIM_SOURCE)


class DataLimitAttemptsTest(unittest.TestCase):
    """data_limit_attempts and the shim's limit computation.

    The fourth live verdict (docs/steady/security/
    macos.md): every shim-carrying live point failed on
    the shim's named refusal -- `hp-shim: could not set
    the data-size limit: current limit exceeds maximum
    limit` -- while the 2 profile-alone points passed.
    Suppositions R4-S1 (the kernel refuses a data-size
    limit below the process's current usage) and R4-S2
    (the old pair (limit, limit) moved the hard limit)
    name the computation this class pins: the hard
    limit never moves, the soft request is clamped to
    it, and a refusal is answered by a bounded ladder
    of doublings. The pure rule is pinned per field and
    by a fuzz family; the shim's execution of the same
    rule is pinned under a scripted resource seam. The
    macOS CI host refuses a real setrlimit below its
    floor, so neither the 256 MiB inheritance nor the
    1 GiB climb can be shown with the kernel's own call.
    """

    MIB = 1024 * 1024

    def test_an_unlimited_hard_limit_ladders_to_the_cap(self):
        self.assertEqual(
            MC.data_limit_attempts(512 * self.MIB, -1),
            (512 * self.MIB, 1024 * self.MIB, 2048 * self.MIB,
             4096 * self.MIB, 8192 * self.MIB, 16384 * self.MIB,
             32768 * self.MIB, 65536 * self.MIB, 131072 * self.MIB,
             262144 * self.MIB, 524288 * self.MIB))
        self.assertEqual(
            MC.DATA_LIMIT_LADDER_CAP_MULTIPLIER, 1024)

    def test_a_larger_hard_limit_leaves_the_request_alone(self):
        self.assertEqual(
            MC.data_limit_attempts(512 * self.MIB, 4096 * self.MIB),
            (512 * self.MIB, 1024 * self.MIB, 2048 * self.MIB,
             4096 * self.MIB))

    def test_an_equal_hard_limit_is_the_single_attempt(self):
        self.assertEqual(
            MC.data_limit_attempts(512 * self.MIB, 512 * self.MIB),
            (512 * self.MIB,))

    def test_a_smaller_hard_limit_clamps_the_request_to_it(self):
        # The R4-S2 shape: the request may never exceed
        # the allowable maximum the process inherited,
        # and there is nothing above it to ladder to.
        self.assertEqual(
            MC.data_limit_attempts(512 * self.MIB, 256 * self.MIB),
            (256 * self.MIB,))

    def test_a_zero_hard_limit_is_the_single_attempt_zero(self):
        self.assertEqual(MC.data_limit_attempts(512 * self.MIB, 0),
                         (0,))

    def test_a_non_power_of_two_request_caps_by_doubling(self):
        self.assertEqual(MC.data_limit_attempts(100, 1000),
                         (100, 200, 400, 800, 1000))
        self.assertEqual(MC.data_limit_attempts(3, -1),
                         (3, 6, 12, 24, 48, 96, 192, 384, 768,
                          1536, 3072))

    def test_the_requested_field_must_be_a_positive_integer(self):
        for bad in (0, -1, -512, True, False, "512", 1.5, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.data_limit_attempts(bad, -1)

    def test_the_hard_field_must_be_unlimited_or_nonnegative(self):
        for bad in (-2, -100, True, False, "inf", 1.5, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.data_limit_attempts(512 * self.MIB, bad)

    def test_random_pairs_keep_the_ladder_invariants(self):
        rng = random.Random(20261112)
        ran = 0
        for _ in range(400):
            requested = rng.choice(
                (1, 2, 3, 7, 100, 512 * self.MIB,
                 rng.randrange(1, 10 ** 12)))
            inherited = rng.choice(
                (-1, 0, 1, requested - 1 if requested > 1 else 0,
                 requested, requested + 1,
                 rng.randrange(0, 10 ** 12)))
            attempts = MC.data_limit_attempts(requested, inherited)
            ran += 1
            cap = (inherited if inherited != -1
                   else requested * MC.DATA_LIMIT_LADDER_CAP_MULTIPLIER)
            self.assertEqual(attempts[-1], cap, (requested, inherited))
            self.assertTrue(
                all(a < b for a, b in zip(attempts, attempts[1:])),
                (requested, inherited, attempts))
            self.assertTrue(all(a <= cap for a in attempts))
            self.assertEqual(
                attempts[0],
                requested if inherited == -1
                else min(requested, inherited))
            if inherited == -1:
                self.assertLessEqual(len(attempts), 11)
        self.assertEqual(ran, 400)

    def test_the_shim_text_carries_the_same_rule(self):
        # The shim runs as interpreter text with no module
        # to import, so its computation is inline text; the
        # fragments that carry the rule are pinned here
        # beside the pure function's own tests.
        src = MC.LIMIT_SHIM_SOURCE
        self.assertIn("resource.getrlimit", src)
        self.assertIn("resource.RLIM_INFINITY", src)
        # The pair it sets keeps the inherited hard limit:
        # (_soft, _max), never (_soft, _soft) or (limit, limit).
        self.assertIn("resource.setrlimit(_r, (_soft, _max))", src)
        self.assertNotIn("(limit, limit)", src)
        # The ladder: a refusal below the cap doubles.
        self.assertIn("_soft = min(_soft * 2, _cap)", src)
        self.assertIn("limit * 1024", src)

    # The executed half. Each driver runs in its own
    # process, because a hard limit lowered or a resource
    # seam scripted there must never touch this suite's
    # own process.

    _FLOOR_DRIVER = (
        "import os, resource, sys\n"
        "floor = int(sys.argv[1])\n"
        "hard = int(sys.argv[2])\n"
        "inf = resource.RLIM_INFINITY\n"
        # The seam, not the kernel. This host refuses every\n"
        # data-size limit below a floor far above 1 GiB, so a\n"
        # driver that called the real setrlimit could not show\n"
        # the ladder accepting 1 GiB or inheriting 256 MiB.\n"
        "seen = [hard, hard] if hard >= 0 else [inf, inf]\n"
        "def fake_get(r):\n"
        "    if r == resource.RLIMIT_DATA:\n"
        "        return (seen[0], seen[1])\n"
        "    raise RuntimeError('unexpected resource')\n"
        "def fake_set(r, pair):\n"
        "    if pair[0] < floor:\n"
        "        raise ValueError('current limit exceeds "
        "maximum limit')\n"
        "    if seen[1] != inf and pair[0] > seen[1]:\n"
        "        raise ValueError('current limit exceeds "
        "maximum limit')\n"
        "    seen[0] = pair[0]\n"
        "def fake_exec(path, argv):\n"
        "    code = argv[2]\n"
        "    exec(compile(code, '<job>', 'exec'),\n"
        "         {'__name__': '__main__'})\n"
        "    raise SystemExit(0)\n"
        "resource.getrlimit = fake_get\n"
        "resource.setrlimit = fake_set\n"
        "os.execvp = fake_exec\n"
        "src = open(sys.argv[3], encoding='utf-8').read()\n"
        "job = ('import resource\\n'\n"
        "       'print(\\'JOB-RAN\\', '\n"
        "       'resource.getrlimit(resource.RLIMIT_DATA))\\n')\n"
        "sys.argv = ['-c', str(512 * 1024 * 1024), '-', "
        "sys.executable, '-c', job]\n"
        "exec(compile(src, 'hp-shim', 'exec'))\n"
    )

    def _run_floor_driver(self, floor, hard=-1):
        with tempfile.TemporaryDirectory() as tmp:
            shim_path = os.path.join(tmp, "shim-source.txt")
            with open(shim_path, "w", encoding="utf-8") as fh:
                fh.write(MC.LIMIT_SHIM_SOURCE)
            return subprocess.run(
                [sys.executable, "-c", self._FLOOR_DRIVER,
                 str(floor), str(hard), shim_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=60)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_shim_climbs_past_a_current_usage_floor(self):
        # R4-S1 executed against a scripted seam: any soft
        # limit below a 768 MiB floor is refused with the
        # fourth verdict's own error text; the ladder's
        # second attempt (1 GiB) is accepted and the job
        # runs carrying exactly it, hard still unlimited.
        done = self._run_floor_driver(768 * self.MIB)
        self.assertEqual(done.returncode, 0,
                         done.stderr.decode("utf-8", "replace"))
        self.assertIn(b"JOB-RAN (1073741824,", done.stdout)
        self.assertNotIn(b"hp-shim", done.stderr)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_shim_refuses_when_the_floor_stands_above_the_cap(self):
        done = self._run_floor_driver(2 ** 40)
        self.assertEqual(done.returncode, 1)
        self.assertIn(
            b"hp-shim: could not set the data-size limit: "
            b"current limit exceeds maximum limit", done.stderr)
        self.assertNotIn(b"JOB-RAN", done.stdout)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_shim_refuses_when_the_floor_stands_above_the_hard_limit(self):
        # A finite inherited hard limit caps the ladder at
        # itself: a floor above it leaves no allowable
        # value, and the spawn refuses rather than asking
        # for a soft limit above the hard limit.
        done = self._run_floor_driver(768 * self.MIB, hard=256 * self.MIB)
        self.assertEqual(done.returncode, 1)
        self.assertIn(b"hp-shim: could not set the data-size limit",
                      done.stderr)
        self.assertNotIn(b"JOB-RAN", done.stdout)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_shim_clamps_to_a_lowered_inherited_hard_limit(self):
        # R4-S2 executed with the real resource module: a
        # driver lowers its own hard data limit to
        # 256 MiB, and the shim it then spawns -- which
        # inherits that hard limit -- runs the job, whose
        # read-back is the clamped pair (256 MiB, 256 MiB).
        # The pre-fix shim refused here by name and the
        # job never ran.
        # The kernel on the macOS CI host refuses a real
        # 256 MiB hard limit, so this is the same seam as the
        # floor driver: getrlimit reports 256 MiB, and the
        # shim clamps the 512 MiB request to that pair.
        done = self._run_floor_driver(0, hard=256 * self.MIB)
        self.assertEqual(done.returncode, 0,
                         done.stderr.decode("utf-8", "replace"))
        self.assertIn(b"JOB-RAN (268435456, 268435456)", done.stdout)


class SandboxArgvFieldTest(unittest.TestCase):
    """build_sandbox_argv: the composed spawn argv."""

    def test_a_host_that_rewrites_posix_paths_keeps_the_posix_form(self):
        # The profile writer takes leading-slash paths only; a host
        # whose realpath turns one into a drive path (Windows) gets
        # the POSIX form back, normalized, so these field tests run
        # on every leg. A host that keeps the slash gets realpath.
        with mock.patch.object(MC.os.path, "realpath",
                               return_value="D:\\work\\a\\b"):
            self.assertEqual(MC._profile_realpath("/work/a/../a/b"),
                             "/work/a/b")
        with mock.patch.object(MC.os.path, "realpath",
                               return_value="/private/tmp/w"):
            self.assertEqual(MC._profile_realpath("/tmp/w"),
                             "/private/tmp/w")

    def test_the_shape_is_sandbox_exec_profile_shim(self):
        argv, profile = MC.build_sandbox_argv(
            ["/usr/bin/python3", "s.py"], cwd="/work/job1")
        self.assertEqual(argv[0], MC.SANDBOX_EXEC_BIN)
        self.assertEqual(argv[0], "/usr/bin/sandbox-exec")
        self.assertEqual(argv[1], "-p")
        self.assertEqual(argv[2], profile)
        self.assertEqual(argv[3], sys.executable)
        self.assertEqual(argv[4], "-c")

    def test_cwd_field_drives_the_profile_workdir(self):
        _argv, profile = MC.build_sandbox_argv(
            ["/bin/echo"], cwd="/work/elsewhere")
        self.assertIn('(subpath "/work/elsewhere")', profile)

    @unittest.skipIf(os.name == "nt",
                     "the profile names POSIX real paths; Windows realpath "
                     "yields a drive path and symlinks need a privilege")
    def test_cwd_field_names_the_real_path_of_a_symlinked_workdir(self):
        # Seatbelt matches canonical paths: a work directory
        # handed over through a symlink alias must enter the
        # profile under its real name, or the staged read at
        # that real path is refused (supposition S2).
        with tempfile.TemporaryDirectory() as tmp:
            real = os.path.join(tmp, "real-work")
            os.makedirs(real)
            alias = os.path.join(tmp, "alias-work")
            os.symlink(real, alias)
            _argv, profile = MC.build_sandbox_argv(
                ["/bin/echo"], cwd=alias)
            self.assertIn(
                '(subpath "%s")' % os.path.realpath(real), profile)
            write_line = [ln for ln in profile.splitlines()
                          if ln.startswith("(allow file-write*")][0]
            self.assertNotIn(alias, write_line)

    def test_memory_and_user_fields_reach_the_shim(self):
        argv, _profile = MC.build_sandbox_argv(
            ["/bin/echo"], cwd="/work/j", memory_bytes=2048,
            user="nobody")
        self.assertIn("2048", argv)
        self.assertEqual(argv[argv.index("2048") + 1], "nobody")

    def test_an_unresolvable_interpreter_is_a_refusal(self):
        with self.assertRaises(RuntimeError):
            MC.build_sandbox_argv(
                ["hp-no-such-interpreter-zz9"], cwd="/work/j")


class ProfileFuzzTest(unittest.TestCase):
    """The bookended fuzz family around the profile writer.

    Every symbol on the ASCII table, at the front AND the back
    of the text the generator takes, as single characters and
    as runs of 10, in the middle as well as at the edges, plus
    the non-printing edge cases and symbol-only strings. The
    invariants, for every input: the writer either refuses it
    (a path carrying NUL, CR or LF) or returns the fixed-shape
    profile -- the same number of lines, the network denial
    standing, no network allow rule, and the input present
    exactly as the writer's own quoting writes it.
    """

    BASE = "/work/hp-job"

    def _cases(self):
        symbols = string.punctuation + " \t"
        cases = []
        for ch in symbols:
            cases.append(ch + self.BASE)
            cases.append(self.BASE + ch)
            cases.append(ch * 10 + self.BASE)
            cases.append(self.BASE + ch * 10)
            cases.append(self.BASE + "/" + ch * 10 + "/x")
            cases.append(ch * 10)
        for ch in ("\x00", "\r", "\n", "\x0b", "\x0c", "\x7f"):
            cases.append(ch + self.BASE)
            cases.append(self.BASE + ch)
            cases.append(self.BASE + ch * 10)
        cases.append("")
        cases.append("/")
        return cases

    def test_bookended_symbols_never_break_the_profile_shape(self):
        ran = 0
        refused = 0
        for value in self._cases():
            ran += 1
            try:
                profile = MC.build_profile(value)
            except RuntimeError:
                refused += 1
                # Only a control-bearing or non-absolute input
                # may be refused.
                self.assertTrue(
                    any(ord(c) < 0x20 or ord(c) == 0x7f for c in value)
                    or not value.startswith("/"), repr(value))
                continue
            self.assertEqual(
                len(profile.splitlines()),
                len(MC.build_profile(self.BASE).splitlines()),
                repr(value))
            self.assertIn("(deny network*)", profile)
            self.assertNotIn("(allow network", profile)
            self.assertIn(MC._sb_quote(value), profile, repr(value))
        self.assertGreater(ran, 200)
        self.assertGreater(refused, 0)

    def test_bookended_symbols_never_break_the_shim_user_field(self):
        ran = 0
        for ch in string.punctuation + " \t\x00\r\n":
            for value in (ch + "nobody", "nobody" + ch,
                          ch * 10 + "nobody", "nobody" + ch * 10):
                ran += 1
                try:
                    out = MC.build_shim_argv(["/bin/true"], user=value)
                except RuntimeError:
                    self.assertTrue(
                        ":" in value
                        or any(ord(c) < 0x20 or ord(c) == 0x7f
                               for c in value),
                        repr(value))
                    continue
                self.assertEqual(out[4], value)
        self.assertGreater(ran, 100)

    def test_random_text_keeps_the_invariants(self):
        rng = random.Random(20261111)
        alphabet = string.printable + "\x00\x7f"
        ran = 0
        for _ in range(300):
            text = "".join(rng.choice(alphabet)
                           for _ in range(rng.randrange(0, 30)))
            value = "/work/" + text
            ran += 1
            try:
                profile = MC.build_profile(value)
            except RuntimeError:
                self.assertTrue(
                    any(ord(c) < 0x20 or ord(c) == 0x7f for c in value),
                    repr(value))
                continue
            self.assertNotIn("(allow network", profile)
            self.assertIn("(deny network*)", profile)
            self.assertIn(MC._sb_quote(value), profile)
        self.assertEqual(ran, 300)


class _FakeTrialProc:
    """The confined-process shape the trial drives, scripted."""

    def __init__(self, out=b"", err=b"", returncode=0, work=None,
                 write_file=False, timeout=False):
        self._out = out
        self._err = err
        self.returncode = returncode
        self._work = work
        self._write_file = write_file
        self._timeout = timeout
        self.killed = False
        self.closed = False

    def communicate(self, timeout=None):
        if self._timeout:
            raise subprocess.TimeoutExpired("trial", timeout)
        if self._write_file and self._work is not None:
            with open(os.path.join(self._work, "trial-out.txt"),
                      "w") as fh:
                fh.write("hp-confinement-trial\n")
        return self._out, self._err

    def kill(self):
        self.killed = True

    def close(self):
        self.closed = True


class ConfinementTrialProblemTest(unittest.TestCase):
    """confinement_trial_problem through scripted spawn seams."""

    def _spawn(self, proc_factory, record):
        def _spawn(argv, cwd=None, env=None):
            record["argv"] = argv
            record["cwd"] = cwd
            record["staged_existed"] = all(
                os.path.exists(p) for p in argv[1:])
            record["staged_inside_work"] = all(
                p == cwd or p.startswith(cwd + os.sep)
                for p in argv[1:])
            return proc_factory(cwd)
        return _spawn

    def test_trial_ok_answers_none_and_cleans_up(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n",
                work=work, write_file=True), record)
        self.assertIsNone(MC.confinement_trial_problem(spawn))
        self.assertTrue(record["staged_existed"])
        self.assertTrue(record["staged_inside_work"])
        root = os.path.dirname(record["cwd"])
        self.assertFalse(os.path.exists(root))

    def test_trial_read_failure_names_the_staged_read(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=b"", err=b"PermissionError: [Errno 1] denied",
                returncode=1), record)
        problem = MC.confinement_trial_problem(spawn)
        self.assertIsNotNone(problem)
        self.assertIn("could not read its staged file", problem)

    def test_trial_write_failure_names_the_work_write(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=b"TRIAL-READ-OK\n",
                err=b"PermissionError: [Errno 1] denied",
                returncode=1), record)
        problem = MC.confinement_trial_problem(spawn)
        self.assertIsNotNone(problem)
        self.assertIn("could not write its work directory", problem)

    def test_trial_spawn_failure_names_the_spawn(self):
        def _spawn(argv, cwd=None, env=None):
            raise RuntimeError("sandbox-exec failed: 71")
        problem = MC.confinement_trial_problem(_spawn)
        self.assertIsNotNone(problem)
        self.assertIn("confined trial spawn failed", problem)
        self.assertIn("sandbox-exec failed: 71", problem)

    def test_trial_timeout_names_the_timeout_and_kills(self):
        record = {}
        holder = {}

        def _factory(work):
            holder["proc"] = _FakeTrialProc(timeout=True)
            return holder["proc"]

        spawn = self._spawn(_factory, record)
        problem = MC.confinement_trial_problem(spawn, timeout=3)
        self.assertIsNotNone(problem)
        self.assertIn("timed out", problem)
        self.assertTrue(holder["proc"].killed)
        self.assertTrue(holder["proc"].closed)


class ConfinementStartupGateTest(unittest.TestCase):
    """confinement_startup_problem: darwin consults the backend."""

    def test_engageable_backend_lets_enforce_start(self):
        self.assertIsNone(rr._confinement_startup_problem(
            _ccfg("enforce"), platform="darwin",
            backend=_backend(None)))

    def test_unengageable_backend_refuses_and_names_why(self):
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="darwin",
            backend=_backend("sandbox-exec cannot start"))
        self.assertIsNotNone(problem)
        self.assertIn("confinement cannot engage on darwin", problem)
        self.assertIn("sandbox-exec cannot start", problem)

    def test_a_backend_that_raises_still_refuses(self):
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="darwin",
            backend=_backend(RuntimeError("module gone")))
        self.assertIsNotNone(problem)
        self.assertIn("module gone", problem)

    def test_audit_and_off_are_never_refused_by_the_gate(self):
        for mode in ("audit", "off"):
            self.assertIsNone(rr._confinement_startup_problem(
                _ccfg(mode), platform="darwin",
                backend=_backend("cannot engage")), mode)

    def test_non_darwin_is_untouched_by_the_backend(self):
        self.assertIsNone(rr._confinement_startup_problem(
            _ccfg("enforce"), platform="linux",
            backend=_backend("cannot engage")))

    def test_simulated_darwin_refusal_is_deterministic(self):
        if MC.IS_MACOS_BACKEND:
            self.skipTest(
                "the simulated darwin refusal is deterministic "
                "off darwin")
        problem = rr._confinement_startup_problem(
            _ccfg("enforce"), platform="darwin")
        self.assertEqual(
            problem,
            "confinement (bwrap) is Linux-only; "
            "this machine is darwin")


class ConfinementArgvTest(unittest.TestCase):
    """_confinement_argv on a simulated darwin: the argv gate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, mode, backend):
        sink = []
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(rr, "_security", _sec(mode, sink)):
            out = rr._confinement_argv(
                _ccfg(mode), self.base, "j1", ["python"], "script.py",
                self.base, [], {}, backend=backend)
        return out, sink

    def test_engageable_backend_returns_the_normal_argv(self):
        out, _sink = self._run("enforce", _backend(None))
        self.assertEqual(out, (["python", "script.py"], True, False))

    def test_unengageable_backend_denies_the_job(self):
        out, sink = self._run("enforce", _backend("not a mac"))
        self.assertEqual(out, ([], True, False))
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"], "confinement_unavailable")


class ConfinementSpawnTest(unittest.TestCase):
    """_confinement_spawn: the sandbox-exec creation-time seam."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _secmap(self, modes, sink):
        sec = mock.Mock()
        sec.sec_mode.side_effect = lambda cfg, name: modes.get(
            name, "off")

        def _write(base_dir, feature, decision, reason, **kw):
            sink.append({"feature": feature, "decision": decision,
                         "reason": reason, "kw": kw})
        sec.write_audit_entry.side_effect = _write
        return sec

    def _run(self, cfg, modes, backend="unset"):
        sink = []
        kw = {} if backend == "unset" else {"backend": backend}
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(REM.os, "name", "posix"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(modes, sink)):
            out = REM._confinement_spawn(
                cfg, self.base, "j1", ["/bin/sh", "s.sh"],
                self.base, {}, **kw)
        return out, sink

    def test_other_platforms_are_a_noop(self):
        sink = []
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(REM.os, "name", "posix"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(
                                      {"confinement": "enforce"}, sink)):
            out = REM._confinement_spawn(
                _ccfg("enforce"), self.base, "j1", ["/bin/sh", "s.sh"],
                self.base, {}, backend=_backend(None))
        self.assertIsNone(out)
        self.assertEqual(sink, [])

    def test_the_seam_ignores_a_simulated_nt_os_name_on_darwin(self):
        # The seam derives its platform from sys.platform alone
        # (supposition S3): on a darwin-shaped host an os.name
        # of "nt" -- a windows simulation's patch, or any other
        # stray signal -- does not route the spawn anywhere but
        # the macOS branch its sys.platform names.
        backend = _backend(None)
        sink = []
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(REM.os, "name", "nt"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(
                                      {"confinement": "enforce"}, sink)):
            proc, release = REM._confinement_spawn(
                _ccfg("enforce"), self.base, "j1", ["/bin/sh", "s.sh"],
                self.base, {}, backend=backend)
        self.assertEqual(proc.pid, 31337)
        self.assertEqual(
            sink[0]["reason"],
            "macos: seatbelt_profile + no_network + spawn_resource_limits")
        release()
        self.assertTrue(proc.closed)

    def test_audit_and_off_spawn_nothing(self):
        for mode in ("audit", "off"):
            out, _sink = self._run(
                _ccfg(mode), {"confinement": mode},
                backend=_backend(None))
            self.assertIsNone(out, mode)

    def test_enforce_spawns_and_records_exactly_the_controls(self):
        backend = _backend(None)
        (proc, release), sink = self._run(
            _ccfg("enforce"), {"confinement": "enforce"},
            backend=backend)
        self.assertEqual(proc.pid, 31337)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["feature"], "confinement")
        self.assertEqual(sink[0]["decision"], "confined")
        self.assertEqual(
            sink[0]["reason"],
            "macos: seatbelt_profile + no_network + spawn_resource_limits")
        self.assertNotIn("jail", sink[0]["reason"])
        release()
        self.assertTrue(proc.closed)

    def test_enforce_hands_the_job_user_to_the_spawn(self):
        backend = _backend(None)
        cfg = {"security": {
            "modes": {"confinement": "enforce",
                      "job_user": "enforce"},
            "job_user": {"user": "nobody"}}}
        self._run(cfg, {"confinement": "enforce",
                        "job_user": "enforce"}, backend=backend)
        self.assertEqual(backend.spawned[0]["user"], "nobody")

    def test_no_user_is_handed_over_when_job_user_is_not_enforce(self):
        backend = _backend(None)
        cfg = {"security": {
            "modes": {"confinement": "enforce"},
            "job_user": {"user": "nobody"}}}
        self._run(cfg, {"confinement": "enforce"}, backend=backend)
        self.assertIsNone(backend.spawned[0]["user"])

    def test_enforce_spawn_failure_refuses_and_records_fallback(self):
        backend = _backend(None, apply_error=RuntimeError("sb 71"))
        sink_modes = {"confinement": "enforce"}
        sink = []
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(REM.os, "name", "posix"), \
                mock.patch.object(rr, "_security",
                                  self._secmap(sink_modes, sink)):
            with self.assertRaises(rr.JobRejected):
                REM._confinement_spawn(
                    _ccfg("enforce"), self.base, "j1",
                    ["/bin/sh", "s.sh"], self.base, {},
                    backend=backend)
        self.assertEqual(sink[0]["decision"], "fallback")
        self.assertEqual(sink[0]["reason"],
                         "macos_confinement_failed")


class SeedShapeTest(unittest.TestCase):
    """The seed keeps the other backends' pattern: stated, not probed."""

    def test_platform_modes_states_confinement_audit_only(self):
        self.assertEqual(INS.platform_modes("darwin"),
                         {"confinement": "audit"})

    def test_a_fresh_darwin_seed_states_confinement_audit(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        SU.seed_platform_modes(cfg, platform="darwin")
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        # job_user is a POSIX demote and engages on macOS; the
        # seed does not state it down.
        self.assertEqual(cfg["security"]["modes"]["job_user"],
                         "enforce")


@unittest.skipUnless(MC.IS_MACOS_BACKEND, "run on macOS")
class LiveBackendTest(unittest.TestCase):
    """The real backend, on a macOS host (the CI legs)."""

    def test_the_probe_engages(self):
        self.assertIsNone(MC.macos_startup_problem())
        self.assertIsNone(MC.macos_confinement_problem())

    def test_a_spawn_runs_inside_the_profile(self):
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "print('IN-PROFILE'); "
                 "open('note.txt', 'w').write('x'); "
                 "print('WROTE-WORK')"],
                cwd=work, env=dict(os.environ))
            out, err = proc.communicate(timeout=30)
            rc = proc.returncode
            proc.close()
            self.assertEqual(
                rc, 0, err.decode("utf-8", "replace"))
            self.assertIn(b"IN-PROFILE", out)
            self.assertIn(b"WROTE-WORK", out)
            self.assertTrue(os.path.exists(
                os.path.join(work, "note.txt")))

    def test_an_escape_write_does_not_land(self):
        target = os.path.join(
            tempfile.gettempdir(),
            "hp-escape-%s.txt" % os.urandom(6).hex())
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "import sys\n"
                 "try:\n"
                 "    open(sys.argv[1], 'w').write('x')\n"
                 "    print('WRITE-LANDED')\n"
                 "except OSError:\n"
                 "    print('WRITE-DENIED')\n", target],
                cwd=work, env=dict(os.environ))
            out, _err = proc.communicate(timeout=30)
            proc.close()
            self.assertIn(b"WRITE-DENIED", out)
            self.assertFalse(os.path.exists(target))

    def test_an_escape_read_does_not_return_contents(self):
        with tempfile.TemporaryDirectory() as host, \
                tempfile.TemporaryDirectory() as work:
            secret = os.path.join(host, "secret.txt")
            with open(secret, "w") as fh:
                fh.write("HOST-SECRET-CONTENTS")
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "import sys\n"
                 "try:\n"
                 "    print(open(sys.argv[1]).read())\n"
                 "except OSError:\n"
                 "    print('READ-DENIED')\n", secret],
                cwd=work, env=dict(os.environ))
            out, _err = proc.communicate(timeout=30)
            proc.close()
            self.assertIn(b"READ-DENIED", out)
            self.assertNotIn(b"HOST-SECRET-CONTENTS", out)

    def test_a_network_attempt_is_refused(self):
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "import socket\n"
                 "try:\n"
                 "    socket.create_connection("
                 "('127.0.0.1', 9), timeout=3)\n"
                 "    print('NET-OPEN')\n"
                 "except OSError:\n"
                 "    print('NET-DENIED')\n"],
                cwd=work, env=dict(os.environ))
            out, _err = proc.communicate(timeout=30)
            proc.close()
            self.assertIn(b"NET-DENIED", out)

    def test_the_spawn_limits_are_carried_by_the_job(self):
        # The ceiling the shim applies is the data-size limit;
        # the address space is unlimited, because a 512 MiB
        # address-space limit is below the startup mappings of
        # every macOS process and aborted the exec'd
        # interpreter at -6 in the first live run (supposition
        # S1). The applied soft value is re-pinned by the
        # fourth fix (supposition R4-S3): it is exactly one
        # of the values on the attempt ladder for the hard
        # limit this test process itself inherits -- the
        # requested ceiling when the host allows it, the
        # inherited hard limit when that is smaller, a
        # ladder value above the request when the kernel's
        # current-usage floor (R4-S1) requires it -- the
        # hard limit reads back unchanged, and the address
        # space stays unlimited. The job reads all three
        # back, in this order.
        import resource
        inherited_hard = resource.getrlimit(resource.RLIMIT_DATA)[1]
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "import resource\n"
                 "print(resource.getrlimit(resource.RLIMIT_DATA)[0])\n"
                 "print(resource.getrlimit(resource.RLIMIT_DATA)[1])\n"
                 "print(resource.getrlimit(resource.RLIMIT_AS)[0])\n"],
                cwd=work, env=dict(os.environ))
            out, _err = proc.communicate(timeout=30)
            proc.close()
            limits = [int(x) for x in out.decode().split()]
            self.assertEqual(len(limits), 3)
            self.assertIn(
                limits[0],
                MC.data_limit_attempts(
                    MC.DEFAULT_PROCESS_MEMORY_BYTES, inherited_hard))
            self.assertEqual(limits[1], inherited_hard)
            self.assertEqual(limits[2], -1)

    def test_a_native_binary_runs_inside_the_profile(self):
        # The full confined chain (profile, shim, limits)
        # carrying a native binary with no interpreter of
        # its own: one leg of the second verdict's bisect
        # (supposition R2-S3). If this passes while the
        # interpreter spawns fail, the chain is sound and
        # the abort is interpreter-specific; if it fails at
        # -6, the abort is in the chain every spawn shares.
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                ["/usr/bin/true"], cwd=work, env=dict(os.environ))
            _out, err = proc.communicate(timeout=30)
            rc = proc.returncode
            proc.close()
            self.assertEqual(
                rc, 0, err.decode("utf-8", "replace"))

    def test_the_profile_alone_lets_the_interpreter_start(self):
        # The generated profile with no shim and no limit:
        # sandbox-exec drives the interpreter directly. One
        # leg of the bisect (supposition R2-S3): if this
        # passes while the full chain aborts, the profile is
        # cleared and the shim's limit is convicted; if it
        # aborts at -6, the profile still refuses a startup
        # read the interpreter needs.
        with tempfile.TemporaryDirectory() as work:
            profile = MC.build_profile(
                os.path.realpath(work), interpreter=sys.executable)
            done = subprocess.run(
                [MC.SANDBOX_EXEC_BIN, "-p", profile,
                 sys.executable, "-c", "print('PROFILE-ONLY-OK')"],
                cwd=work, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(
                done.returncode, 0,
                done.stderr.decode("utf-8", "replace"))
            self.assertIn(b"PROFILE-ONLY-OK", done.stdout)

    def test_the_shim_alone_lets_the_interpreter_start(self):
        # The launcher shim with no profile at all: the
        # interpreter sets the data-size ceiling on itself
        # and execs the job interpreter under it. One leg of
        # the bisect (supposition R2-S3): if this aborts at
        # -6 while the profile-only leg passes, the ceiling
        # itself -- in force across the second exec, while
        # the loader binds the interpreter -- is the abort's
        # cause, and the profile is cleared.
        with tempfile.TemporaryDirectory() as work:
            done = subprocess.run(
                [sys.executable, "-c", MC.LIMIT_SHIM_SOURCE,
                 str(MC.DEFAULT_PROCESS_MEMORY_BYTES), "-",
                 sys.executable, "-c", "print('SHIM-ONLY-OK')"],
                cwd=work, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(
                done.returncode, 0,
                done.stderr.decode("utf-8", "replace"))
            self.assertIn(b"SHIM-ONLY-OK", done.stdout)

    def test_the_profile_alone_lets_a_native_binary_start(self):
        # The generated profile driving a native binary
        # directly, with no shim anywhere: the native start
        # the round-2 bisect never isolated (its native leg
        # launched through the shim's interpreter and shared
        # that interpreter's death). One leg of the third
        # verdict's separation (supposition R3-S3): if this
        # passes while the profile-alone interpreter leg
        # fails, the profile's remaining refusal is
        # interpreter-startup-specific; if it fails, the
        # profile refuses even a native start. The captured
        # stderr rides in the assertion's message, so a
        # failure names its cause in the verdict.
        with tempfile.TemporaryDirectory() as work:
            profile = MC.build_profile(os.path.realpath(work))
            done = subprocess.run(
                [MC.SANDBOX_EXEC_BIN, "-p", profile,
                 "/usr/bin/true"],
                cwd=work, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(
                done.returncode, 0,
                done.stderr.decode("utf-8", "replace"))

    def test_the_shim_alone_lets_a_native_binary_start(self):
        # The launcher shim with no profile, driving a
        # native binary instead of the interpreter: the
        # other leg of the separation (supposition R3-S3).
        # Under alternative (a) -- the shim's setrlimit
        # call itself is refused on this host -- this leg
        # fails carrying the shim's named line ("hp-shim:
        # could not set the data-size limit"); under
        # alternative (b) -- the limit in force across the
        # second exec breaks the interpreter's startup --
        # this leg passes while the shim-alone interpreter
        # leg fails without that line.
        with tempfile.TemporaryDirectory() as work:
            done = subprocess.run(
                [sys.executable, "-c", MC.LIMIT_SHIM_SOURCE,
                 str(MC.DEFAULT_PROCESS_MEMORY_BYTES), "-",
                 "/usr/bin/true"],
                cwd=work, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(
                done.returncode, 0,
                done.stderr.decode("utf-8", "replace"))

    def test_the_memory_ceiling_refuses_a_700mb_job(self):
        # The data-size ceiling is a real ceiling, not a
        # read-back: a job that tries to allocate and touch
        # 256 MiB past its own applied limit -- 768 MiB
        # against the 512 MiB request on a host that
        # applies it exactly, which is the shape this point
        # was first written with -- does not complete the
        # allocation, and the refusal is the ceiling's (a
        # MemoryError), not a failure to start. The size is
        # read from the job's own limit (re-pinned by the
        # fourth fix, supposition R4-S3), because the
        # applied value is the ladder's, not always the
        # requested one.
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "import resource\n"
                 "lim = resource.getrlimit(resource.RLIMIT_DATA)[0]\n"
                 "n = lim + 256 * 1024 * 1024\n"
                 "a = bytearray(n); "
                 "a[::4096] = b'1' * ((n + 4095) // 4096); "
                 "print('MEM-DONE')"],
                cwd=work, env=dict(os.environ))
            out, err = proc.communicate(timeout=60)
            rc = proc.returncode
            proc.close()
            self.assertNotEqual(rc, 0)
            self.assertNotIn(b"MEM-DONE", out)
            self.assertIn(b"MemoryError", err)


if __name__ == "__main__":
    unittest.main()
