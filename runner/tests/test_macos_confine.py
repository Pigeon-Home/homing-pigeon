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
import io
import json
import os
import random
import shutil
import stat
import string
import subprocess
import sys
import tempfile
import time
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
from runner.guard import macos_confine as MC
from runner.guard import sandbox as SB
from runner.ops import remediation_ops as REM
from runner.ops import install as INS
from runner.ops import posture as POST
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


def _backend(problem=None, apply_error=None, notes=()):
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

    def _spawn(argv, cwd=None, env=None, user=None, cfg=None):
        if apply_error is not None:
            raise apply_error
        proc = types.SimpleNamespace(
            pid=31337, returncode=None,
            confinement_status=backend.STATUS_CONFINEMENT,
            confinement_notes=list(notes),
            closed=False)
        proc.close = lambda: setattr(proc, "closed", True)
        backend.spawned.append(
            {"argv": argv, "cwd": cwd, "env": env, "user": user,
             "cfg": cfg, "proc": proc})
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


def _mc_prefix_link(mapping):
    """A scripted realpath for the macOS mirror: the longest
    mapped prefix is replaced, the rest resolves to itself."""
    def _real(path, *args, **kwargs):
        best = ""
        for src in mapping:
            if (path == src or path.startswith(src + "/")) \
                    and len(src) > len(best):
                best = src
        if best:
            return mapping[best] + path[len(best):]
        return path
    return _real



class SessionServicesTest(unittest.TestCase):
    """The services of the session a profile lets a job look up."""

    LIBINFO = "com.apple.system.opendirectoryd.libinfo"
    MEMBERSHIP = "com.apple.system.opendirectoryd.membership"
    PASTEBOARD = "com.apple.pasteboard.1"

    @staticmethod
    def _mach_lines(profile):
        return [ln for ln in profile.splitlines() if "mach" in ln]

    def test_the_backend_names_the_user_database_and_nothing_else(self):
        # Read on both hosted Macs (the macos-confinement run
        # 43761537586): with these two named, every program of
        # the battery behaved as it does with every service
        # open; with none, the ones that ask who a user is got
        # a number for a name or stopped.
        self.assertEqual(MC.SESSION_SERVICES,
                         (self.LIBINFO, self.MEMBERSHIP))
        self.assertEqual(MC.session_services(), MC.SESSION_SERVICES)
        self.assertEqual(MC.PASTEBOARD_SERVICE, self.PASTEBOARD)
        self.assertNotIn(MC.PASTEBOARD_SERVICE, MC.SESSION_SERVICES)

    def test_the_profile_allows_a_lookup_of_those_and_no_other_mach_rule(self):
        profile = MC.build_profile("/work/job1")
        self.assertEqual(self._mach_lines(profile), [
            '(allow mach-lookup (global-name "%s") (global-name "%s"))'
            % (self.LIBINFO, self.MEMBERSHIP)])
        # The rule that stood here let a job look up any
        # service, register a name of its own and ask for a
        # task port: the pasteboard answered it, and a name it
        # registered was taken.
        self.assertNotIn("(allow mach*)", profile)
        self.assertNotIn("mach-register", profile)
        self.assertNotIn("mach-priv", profile)
        self.assertNotIn("pasteboard", profile)

    def test_no_rule_names_a_service_by_pattern(self):
        # A name, never a prefix or an expression: what a job
        # may look up is a list that can be read.
        profile = MC.build_profile(
            "/work/job1", mach_services=[self.PASTEBOARD])
        for word in ("global-name-regex", "global-name-prefix",
                     "local-name", "xpc-service-name"):
            self.assertNotIn(word, profile)
        self.assertEqual(profile.count("(global-name "), 3)

    def test_the_operator_s_services_follow_the_backend_s_own(self):
        names = MC.session_services(["com.example.one",
                                     self.PASTEBOARD])
        self.assertEqual(names, (self.LIBINFO, self.MEMBERSHIP,
                                 "com.example.one", self.PASTEBOARD))
        profile = MC.build_profile("/work/job1",
                                   mach_services=["com.example.one"])
        self.assertEqual(self._mach_lines(profile), [
            '(allow mach-lookup (global-name "%s") (global-name "%s") '
            '(global-name "com.example.one"))'
            % (self.LIBINFO, self.MEMBERSHIP)])

    def test_a_service_is_named_once(self):
        names = MC.session_services(
            ["a.b", self.LIBINFO, "a.b", self.MEMBERSHIP])
        self.assertEqual(names, (self.LIBINFO, self.MEMBERSHIP, "a.b"))

    def test_names_launchd_takes_are_names_here(self):
        for name in ("com.apple.pasteboard.1",
                     "com.apple.distributed_notifications@Uv3",
                     "com.example.my-service", "a", "0x", "A.b_c-d@e"):
            self.assertEqual(MC.validate_service_name(name), name)

    def test_what_a_profile_could_read_as_its_own_is_no_name(self):
        for bad in ("", " ", "a b", 'a"b', "a(b", "a)b", "a\\b", "a;b",
                    "a\nb", "a\x00b", "-a", ".a", "@a", "_a", "a*",
                    "a/b", "a'b", "a#b", "x" * 256, None, 1, ["a"],
                    b"a.b"):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.validate_service_name(bad)
        self.assertEqual(MC.validate_service_name("x" * 255), "x" * 255)

    def test_a_name_cannot_carry_a_rule_into_the_profile(self):
        for bad in ('x") (allow default) (global-name "y',
                    'x"))\n(allow network*)\n(allow mach-lookup '
                    '(global-name "y'):
            with self.assertRaises(RuntimeError):
                MC.build_profile("/work/job1", mach_services=[bad])

    def test_bookended_symbols_never_reach_the_profile(self):
        ran = 0
        for ch in string.punctuation + " \t\x00\r\n":
            for value in (ch + "com.example.s", "com.example.s" + ch,
                          "com.exa" + ch + "mple.s"):
                ran += 1
                try:
                    profile = MC.build_profile(
                        "/work/job1", mach_services=[value])
                except RuntimeError:
                    self.assertFalse(
                        ch in "._@-" and not value.startswith(ch),
                        repr(value))
                    continue
                self.assertIn(ch, "._@-")
                self.assertIn('(global-name "%s")' % value, profile)
                self.assertEqual(profile.count("(allow "),
                                 MC.build_profile("/work/job1")
                                 .count("(allow "))
        self.assertGreater(ran, 100)

    def test_the_operator_s_list_must_be_a_list(self):
        for bad in ("com.example.one", b"x", None, 1, {"a": 1},
                    {"a.b"}):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.session_services(bad)

    def test_the_operator_may_name_sixty_four(self):
        self.assertEqual(MC.MAX_MACH_SERVICES, 64)
        many = ["com.example.s%d" % n for n in range(64)]
        self.assertEqual(len(MC.session_services(many)), 66)
        with self.assertRaises(RuntimeError) as caught:
            MC.session_services(many + ["com.example.more"])
        self.assertIn("at most 64", str(caught.exception))

    def test_the_sandbox_argv_carries_the_operator_s_names(self):
        _argv, profile = MC.build_sandbox_argv(
            ["/bin/echo"], cwd="/work/j",
            mach_services=["com.example.one"])
        self.assertIn('(global-name "com.example.one")', profile)
        _argv, profile = MC.build_sandbox_argv(["/bin/echo"],
                                               cwd="/work/j")
        self.assertNotIn("com.example.one", profile)

    def test_the_trial_asks_the_pasteboard_with_the_system_s_reader(self):
        self.assertEqual(MC.PASTEBOARD_READER, "/usr/bin/pbpaste")
        self.assertIn(
            "if [ -x /usr/bin/pbpaste ] && /usr/bin/pbpaste "
            "> /dev/null 2>&1; then\n  echo TRIAL-CLIPBOARD-OPEN\nfi\n",
            MC._TRIAL_PROGRAM)
        # What the reader prints is thrown away: the trial takes
        # the answer, never the clipboard.
        self.assertEqual(MC._TRIAL_PROGRAM.count("pbpaste"), 2)

class InterpreterHomeAliasTest(unittest.TestCase):
    """Q192, macOS mirror: interpreter_read_paths carries the
    same two-candidate rule as sandbox.interpreter_binds, so
    the never-name-a-home floor is judged by directory there
    too -- a firmlinked /home must not name the home whole
    under its /System/Volumes/Data spelling, and one
    directory under two spellings is named once."""

    FIRMLINK = {"/home": "/System/Volumes/Data/home",
                "/Users": "/System/Volumes/Data/Users"}

    def test_firmlink_realpath_candidate_names_no_home(self):
        with mock.patch.object(MC.os.path, "realpath",
                               _mc_prefix_link(self.FIRMLINK)):
            self.assertEqual(
                MC.interpreter_read_paths("/home/someone/bin/python3"),
                ["/home/someone/bin"])
            self.assertEqual(
                MC.interpreter_read_paths("/Users/alice/bin/python3"),
                ["/Users/alice/bin"])

    def test_firmlink_spelling_as_resolved_falls_back_to_bin(self):
        with mock.patch.object(MC.os.path, "realpath",
                               _mc_prefix_link(self.FIRMLINK)):
            self.assertEqual(
                MC._install_prefix(
                    "/System/Volumes/Data/home/someone/bin/python3"),
                "/System/Volumes/Data/home/someone/bin")
            # The read-paths answer names no home either:
            # /System is one of the system trees the profile
            # already lets a job read, so the firmlink
            # spelling needs no prefix of its own.
            self.assertEqual(
                MC.interpreter_read_paths(
                    "/System/Volumes/Data/home/someone/bin/python3"),
                [])

    def test_symlinked_home_with_no_home_component_in_its_name(self):
        link = _mc_prefix_link({"/home": "/mnt/disk/users"})
        with mock.patch.object(MC.os.path, "realpath", link):
            self.assertEqual(
                MC.interpreter_read_paths("/home/someone/bin/python3"),
                ["/home/someone/bin"])

    def test_aliased_non_home_prefix_is_named_once(self):
        # A tree outside the system read paths (/opt is one
        # of them on this backend, so it cannot show the
        # shape): one directory, two spellings, one name.
        link = _mc_prefix_link({"/srv/tools": "/data/tools"})
        with mock.patch.object(MC.os.path, "realpath", link):
            self.assertEqual(
                MC.interpreter_read_paths("/srv/tools/x64/bin/python3"),
                ["/srv/tools/x64"])

    def test_clean_control_stands(self):
        with mock.patch.object(MC.os.path, "realpath",
                               _mc_prefix_link(self.FIRMLINK)):
            self.assertEqual(
                MC.interpreter_read_paths("/srv/hp-python/bin/python3"),
                ["/srv/hp-python"])


class ShimFieldTest(unittest.TestCase):
    """build_shim_argv, one field at a time, and the shim's text."""

    def test_the_argv_shape_is_fixed(self):
        out = MC.build_shim_argv(["/bin/echo", "hi"])
        self.assertEqual(
            out, ["/bin/sh", "-p", "-c", MC.LIMIT_SHIM_TEXT,
                  "hp-shim", str(512 * 1024), "/bin/echo", "hi"])

    def test_the_shim_runs_on_the_system_shell_and_no_interpreter(self):
        # A runner frozen into one file has no interpreter to
        # lend a shim: the frozen runner's own trial, on both
        # hosted Macs, died loading its Python library under
        # the profile (the macos-confinement run of
        # 2026-11-15). The shim is the system's own shell.
        out = MC.build_shim_argv(["/bin/true"])
        self.assertEqual(MC.SHELL_BIN, "/bin/sh")
        self.assertNotIn(sys.executable, out)
        self.assertNotIn("import ", MC.LIMIT_SHIM_TEXT)

    def test_the_shell_takes_nothing_from_the_environment(self):
        # -p: no function and no option list from the
        # environment, which is the submitter's.
        self.assertEqual(MC.SHELL_PRIVILEGED, "-p")
        self.assertEqual(MC.build_shim_argv(["/bin/true"])[1], "-p")

    def test_memory_field_defaults_to_the_named_ceiling(self):
        out = MC.build_shim_argv(["/bin/true"])
        self.assertEqual(out[5], str(512 * 1024))
        self.assertEqual(MC.DEFAULT_PROCESS_MEMORY_BYTES,
                         512 * 1024 * 1024)

    def test_memory_field_is_handed_over_in_kibibytes_rounded_up(self):
        for given, want in ((1, "1"), (1024, "1"), (1025, "2"),
                            (2048, "2"), (3 * 1024 ** 3, str(3 * 1024 ** 2))):
            out = MC.build_shim_argv(["/bin/true"], memory_bytes=given)
            self.assertEqual(out[5], want, given)
            self.assertGreaterEqual(int(out[5]) * 1024, given)

    def test_memory_field_rejects_a_non_ceiling(self):
        for bad in (0, -1, True, False, "512", 1.5, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_shim_argv(["/bin/true"], memory_bytes=bad)

    def test_command_field_must_be_a_nonempty_string_list(self):
        for bad in ([], (), "ls", ["/bin/true", 1], [""], None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.build_shim_argv(bad)

    def test_the_shim_text_sets_both_limits_then_execs(self):
        text = MC.LIMIT_SHIM_TEXT
        soft = 'ulimit -S -d "$lim"'
        hard = 'ulimit -H -d "$lim"'
        self.assertIn(soft, text)
        self.assertIn(hard, text)
        self.assertTrue(text.endswith('exec "$@"\n'))
        # The soft limit first and the hard limit onto it, both
        # before the exec, in source order.
        self.assertLess(text.rindex(soft), text.rindex(hard))
        self.assertLess(text.rindex(hard), text.index('exec "$@"'))

    def test_the_shim_names_a_limit_it_cannot_set(self):
        # Supposition R3-S3 (docs/steady/security/macos.md):
        # a shim that cannot set its limit refuses the job
        # -- that fail-closed shape stands -- but it refuses
        # by name, on stderr, so the refusal's text is what
        # a verdict carries. Every refusal carries the mark
        # and leaves before the exec it guards.
        text = MC.LIMIT_SHIM_TEXT
        mark = "hp-shim: could not set the data-size limit"
        self.assertEqual(text.count(mark), 3)
        self.assertEqual(text.count("exit 1"), 3)
        self.assertLess(text.rindex(mark), text.index('exec "$@"'))

    def test_the_shim_never_sets_an_address_space_limit(self):
        # Supposition S1 (docs/steady/security/macos.md): a
        # 512 MiB address-space limit is below the address
        # space every macOS process maps at startup, so the
        # exec'd interpreter aborted at -6 before any job code
        # in the first live run. The data-size limit is the
        # ceiling this backend applies; the address-space
        # limit must not come back.
        for line in MC.LIMIT_SHIM_TEXT.splitlines():
            if "ulimit" in line:
                self.assertIn(" -d", line, line)
                self.assertNotIn(" -v", line, line)

    def test_the_shim_names_no_command_but_the_shell_s_own(self):
        # Nothing on the job's PATH runs before the job does:
        # the text holds no path and no word that is not a
        # shell keyword, a builtin or its own variable.
        text = MC.LIMIT_SHIM_TEXT.replace("2>/dev/null", "") \
            .replace("(hi - lo) / 2", "")
        self.assertNotIn("/", text)
        known = {
            "want", "shift", "cap", "hard", "ulimit", "case", "in",
            "esac", "unlimited", "echo", "exit", "lim", "if", "then",
            "fi", "lo", "hi", "mid", "while", "do", "done", "break",
            "else", "exec", "gt", "ge", "H", "S", "d", "hp", "shim",
            "could", "not", "set", "the", "data", "size", "limit",
            "be", "read", "kernel", "accepts", "no", "value", "up",
            "to", "KiB", "was", "refused"}
        import re
        words = set(re.findall(r"[A-Za-z_]+", text))
        self.assertEqual(words - known, set())

    def test_every_try_is_made_in_a_subshell(self):
        # A refusal ends the subshell, never the shim, and a
        # try that is accepted leaves the shim's own limits
        # where they were: only the last two lines set them.
        text = MC.LIMIT_SHIM_TEXT
        self.assertEqual(text.count("(ulimit -S -d "), 3)
        self.assertEqual(
            text.count("ulimit -S -d "), text.count("(ulimit -S -d ") + 1)


class DataLimitPlanTest(unittest.TestCase):
    """data_limit_plan: the limit the shim applies, as a rule.

    Darwin holds a data-size limit against a process's whole
    address map and refuses a value below the map's current
    size (supposition R4-S1 in docs/steady/security/macos.md).
    The doubling ladder the fourth and fifth fixes built
    climbed past that floor and stopped at the first power of
    two above it: 512 GiB on the hosted Apple silicon Mac,
    whose bare process stands at 391.7 GiB, and 64 GiB on the
    Intel one, at 32.5 GiB -- room for a job to grow by 120
    GiB and by 31 GiB. This rule finds the floor to within a
    mebibyte and applies the floor plus the request.
    """

    MIB = 1024
    REQUEST = 512 * 1024
    # The floors /bin/sh read on the two hosted Macs, in KiB
    # (the macos-confinement run of 2026-11-15).
    APPLE_SILICON = 410732544
    INTEL = 34128896

    @staticmethod
    def _kernel(floor, hard=None, asked=None):
        def accepts(value):
            if asked is not None:
                asked.append(value)
            return value >= floor and (hard is None or value <= hard)
        return accepts

    def test_a_host_with_no_floor_takes_the_request_itself(self):
        self.assertEqual(
            MC.data_limit_plan(self.REQUEST, self._kernel(0)),
            (self.REQUEST, None))
        self.assertEqual(
            MC.data_limit_plan(self.REQUEST, self._kernel(self.REQUEST)),
            (self.REQUEST, None))

    def test_the_limit_is_the_floor_plus_the_request(self):
        for floor in (self.APPLE_SILICON, self.INTEL,
                      self.REQUEST + 1, 3 * self.REQUEST):
            limit, found = MC.data_limit_plan(
                self.REQUEST, self._kernel(floor))
            self.assertEqual(limit, found + self.REQUEST, floor)
            self.assertGreaterEqual(found, floor)
            self.assertLessEqual(found - floor, MC.DATA_FLOOR_STEP_KIB)

    def test_the_hosted_floors_leave_the_request_and_not_a_doubling(self):
        # What the doubling ladder left a job on those hosts,
        # beside what this rule leaves it.
        for floor, doubling in ((self.APPLE_SILICON, 2 ** 29),
                                (self.INTEL, 2 ** 26)):
            limit, found = MC.data_limit_plan(
                self.REQUEST, self._kernel(floor))
            self.assertGreater(doubling, floor)
            self.assertGreater(doubling - floor, 30 * 1024 * 1024)
            self.assertLessEqual(limit - floor,
                                 self.REQUEST + MC.DATA_FLOOR_STEP_KIB)

    def test_a_finite_hard_limit_is_never_asked_past(self):
        asked = []
        hard = self.INTEL + 100 * self.MIB
        limit, found = MC.data_limit_plan(
            self.REQUEST, self._kernel(self.INTEL, hard, asked), hard)
        self.assertEqual(limit, hard)
        self.assertLessEqual(max(asked), hard)
        self.assertGreaterEqual(found, self.INTEL)

    def test_a_request_above_a_finite_hard_limit_is_clamped_to_it(self):
        hard = 256 * self.MIB
        self.assertEqual(
            MC.data_limit_plan(self.REQUEST, self._kernel(0, hard), hard),
            (hard, None))

    def test_a_floor_above_the_hard_limit_is_a_refusal(self):
        hard = self.INTEL - 1
        with self.assertRaises(RuntimeError) as caught:
            MC.data_limit_plan(
                self.REQUEST, self._kernel(self.INTEL, hard), hard)
        self.assertIn("accepts no data-size limit", str(caught.exception))
        self.assertIn(str(hard), str(caught.exception))

    def test_a_floor_above_the_cap_is_a_refusal(self):
        with self.assertRaises(RuntimeError):
            MC.data_limit_plan(
                self.REQUEST, self._kernel(MC.DATA_LIMIT_CAP_KIB + 1))

    def test_the_cap_is_the_largest_power_of_two_below_the_sentinel(self):
        self.assertEqual(MC.DATA_LIMIT_CAP_KIB * 1024, 2 ** 62)
        self.assertLess(2 ** 62, 2 ** 63 - 1)
        limit, found = MC.data_limit_plan(
            self.REQUEST, self._kernel(MC.DATA_LIMIT_CAP_KIB))
        self.assertEqual((limit, found),
                         (MC.DATA_LIMIT_CAP_KIB, MC.DATA_LIMIT_CAP_KIB))

    def test_the_questions_asked_are_bounded(self):
        asked = []
        MC.data_limit_plan(1, self._kernel(MC.DATA_LIMIT_CAP_KIB, None,
                                           asked))
        # 52 doublings from one kibibyte, then the halvings of
        # the last gap.
        self.assertLess(len(asked), 120)

    def test_the_requested_field_must_be_a_positive_integer(self):
        for bad in (0, -1, True, False, "512", 1.5, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.data_limit_plan(bad, self._kernel(0))

    def test_the_hard_field_must_be_none_or_nonnegative(self):
        for bad in (-1, True, "1", 1.5):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.data_limit_plan(self.REQUEST, self._kernel(0), bad)

    def test_random_hosts_keep_the_rule_s_invariants(self):
        rng = random.Random(20261115)
        ran = 0
        for _ in range(400):
            want = rng.choice((1, 1023, self.REQUEST,
                               rng.randrange(1, 10 ** 8)))
            floor = rng.choice((0, want, want + 1, self.INTEL,
                                self.APPLE_SILICON,
                                rng.randrange(0, 2 ** 45)))
            hard = rng.choice((None, None, floor, floor + 7,
                               floor + want + 3,
                               rng.randrange(0, 2 ** 46)))
            ran += 1
            try:
                limit, found = MC.data_limit_plan(
                    want, self._kernel(floor, hard), hard)
            except RuntimeError:
                # Refused only where nothing could be accepted.
                self.assertTrue(hard is not None and hard < floor,
                                (want, floor, hard))
                continue
            cap = MC.DATA_LIMIT_CAP_KIB if hard is None else hard
            self.assertGreaterEqual(limit, floor)
            self.assertLessEqual(limit, cap)
            if found is None:
                self.assertEqual(limit, min(want, cap))
            else:
                self.assertGreater(floor, min(want, cap))
                self.assertLessEqual(found - floor,
                                     MC.DATA_FLOOR_STEP_KIB)
                self.assertEqual(limit, min(found + want, cap))
        self.assertEqual(ran, 400)


# A kernel for the shim's text, scripted in the shim's own
# language: a function under the builtin's name that answers
# as a kernel with this floor and this hard limit would. The
# job the shim execs reads what was set from its environment.
_FAKE_KERNEL = r'''
ulimit() {
  case "$1 $2" in
    "-H -d")
      if [ $# -eq 2 ]; then echo "$T_HARD"; return 0; fi
      if [ "$T_SOFT" != unlimited ] && [ "$3" -lt "$T_SOFT" ]; then return 1; fi
      if [ "$T_HARD" != unlimited ] && [ "$3" -gt "$T_HARD" ]; then return 1; fi
      T_HARD=$3; export T_HARD; return 0 ;;
    "-S -d")
      if [ $# -eq 2 ]; then echo "$T_SOFT"; return 0; fi
      if [ "$3" -lt "$T_FLOOR" ]; then return 1; fi
      if [ "$T_HARD" != unlimited ] && [ "$3" -gt "$T_HARD" ]; then return 1; fi
      T_SOFT=$3; export T_SOFT; return 0 ;;
  esac
  return 2
}
'''


def _shells():
    """The shells this host can run the shim's text on: the
    system's own, and bash in its POSIX mode where it is
    installed -- what /bin/sh is on a Mac."""
    shells = [[MC.SHELL_BIN, MC.SHELL_PRIVILEGED]]
    bash = shutil.which("bash")
    if bash:
        shells.append([bash, "--posix", MC.SHELL_PRIVILEGED])
    return shells


_READ_BACK = 'echo "$(ulimit -S -d) $(ulimit -H -d)"'
# The same reading by a job that is no shell: where the
# environment carries a function under the builtin's name, a
# job that is a shell would call the function too.
_PY_READ_BACK = [sys.executable, "-c",
                 "import resource\n"
                 "print(*resource.getrlimit(resource.RLIMIT_DATA))\n"]


@unittest.skipUnless(os.name == "posix", "POSIX only")
class ShimRunTest(unittest.TestCase):
    """The shim's text, run: against a scripted kernel, where
    any floor and any hard limit can be staged on any host,
    and against this host's own."""

    REQUEST = 512 * 1024

    def _scripted(self, shell, want, floor, hard=None):
        env = {"T_FLOOR": str(floor), "T_SOFT": "unlimited",
               "T_HARD": "unlimited" if hard is None else str(hard),
               "PATH": "/usr/bin:/bin"}
        return subprocess.run(
            shell + ["-c", _FAKE_KERNEL + MC.LIMIT_SHIM_TEXT,
                     MC.SHIM_NAME, str(want), "/bin/sh", "-c",
                     'echo "JOB-RAN $T_SOFT $T_HARD"'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, timeout=60)

    def _real(self, job, env=None, shell=None, memory=None):
        argv = MC.build_shim_argv(
            ["/bin/sh", "-c", job] if isinstance(job, str) else job,
            **({} if memory is None else {"memory_bytes": memory}))
        if shell is not None:
            argv = shell + argv[2:]
        return subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, timeout=60)

    def test_the_shim_text_carries_the_same_rule(self):
        # The pure rule and the shell text, side by side, over
        # hosts drawn at random: the same limit, set soft and
        # hard, or the same refusal.
        rng = random.Random(20261116)
        ran = 0
        for shell in _shells():
            for _ in range(40):
                want = rng.choice((1, 1023, self.REQUEST, 2097152,
                                   rng.randrange(1, 10 ** 7)))
                floor = rng.choice((
                    0, 1, want, want + 1,
                    DataLimitPlanTest.APPLE_SILICON,
                    DataLimitPlanTest.INTEL,
                    rng.randrange(0, 2 ** 45),
                    MC.DATA_LIMIT_CAP_KIB,
                    MC.DATA_LIMIT_CAP_KIB + 5))
                hard = rng.choice((None, None, 0, want, floor,
                                   floor + 7, floor + want + 3,
                                   rng.randrange(0, 2 ** 46)))
                ran += 1
                done = self._scripted(shell, want, floor, hard)
                try:
                    limit, _found = MC.data_limit_plan(
                        want, DataLimitPlanTest._kernel(floor, hard),
                        hard)
                except RuntimeError:
                    self.assertEqual(done.returncode, 1,
                                     (shell, want, floor, hard))
                    self.assertNotIn(b"JOB-RAN", done.stdout)
                    self.assertIn(
                        b"hp-shim: could not set the data-size "
                        b"limit", done.stderr)
                    continue
                self.assertEqual(
                    (done.returncode, done.stdout.decode().strip()),
                    (0, "JOB-RAN %d %d" % (limit, limit)),
                    (shell, want, floor, hard, done.stderr))
        self.assertGreaterEqual(ran, 40)

    def test_the_shim_stands_the_request_on_the_hosted_floors(self):
        for shell in _shells():
            for floor in (DataLimitPlanTest.APPLE_SILICON,
                          DataLimitPlanTest.INTEL):
                done = self._scripted(shell, self.REQUEST, floor)
                self.assertEqual(done.returncode, 0, done.stderr)
                soft, hard = done.stdout.decode().split()[1:]
                self.assertEqual(soft, hard)
                over = int(soft) - floor - self.REQUEST
                self.assertGreaterEqual(over, 0)
                self.assertLessEqual(over, MC.DATA_FLOOR_STEP_KIB)

    def test_the_shim_refuses_by_name_when_nothing_is_accepted(self):
        for shell in _shells():
            done = self._scripted(shell, self.REQUEST,
                                  MC.DATA_LIMIT_CAP_KIB + 1)
            self.assertEqual(done.returncode, 1)
            self.assertIn(
                b"hp-shim: could not set the data-size limit: the "
                b"kernel accepts no value up to", done.stderr)
            self.assertNotIn(b"JOB-RAN", done.stdout)

    def test_the_shim_refuses_when_the_floor_stands_above_the_hard_limit(self):
        for shell in _shells():
            done = self._scripted(shell, self.REQUEST,
                                  DataLimitPlanTest.INTEL,
                                  hard=256 * 1024)
            self.assertEqual(done.returncode, 1)
            self.assertIn(b"up to 262144 KiB", done.stderr)
            self.assertNotIn(b"JOB-RAN", done.stdout)

    def test_the_shim_never_raises_a_finite_hard_limit(self):
        for shell in _shells():
            done = self._scripted(shell, self.REQUEST, 0,
                                  hard=256 * 1024)
            self.assertEqual(done.stdout.decode().strip(),
                             "JOB-RAN 262144 262144")

    def test_this_host_s_kernel_sets_both_limits(self):
        # The real builtin and the real kernel: the request
        # itself on a host with no floor, the floor plus the
        # request on a host with one, and soft and hard alike
        # either way.
        done = self._real(_READ_BACK)
        self.assertEqual(done.returncode, 0, done.stderr)
        soft, hard = done.stdout.decode().split()
        self.assertEqual(soft, hard)
        self.assertGreaterEqual(int(soft), self.REQUEST)

    def test_the_job_cannot_raise_the_limit(self):
        # Each try is a subshell of the job's own; the limits
        # are read again after both. A shell may answer a
        # request to lift the soft limit by setting it to the
        # hard one, which is where it already stands.
        if os.geteuid() == 0:
            self.skipTest("root may raise a hard limit: run as an "
                          "ordinary user")
        done = self._real(
            _READ_BACK + "; (ulimit -H -d unlimited) 2>/dev/null "
            "&& echo RAISED-HARD; ulimit -S -d unlimited "
            "2>/dev/null; " + _READ_BACK)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.decode().split("\n")
        self.assertNotIn("RAISED-HARD", lines)
        self.assertEqual(lines[0], lines[1])
        self.assertNotIn("unlimited", lines[1])

    def test_a_function_in_the_environment_does_not_stand_in_for_ulimit(self):
        # The submitter's environment reaches the shim's shell.
        # bash takes functions from variables of two shapes --
        # the one bash 4.3 and later reads, and the one the
        # bash a Mac ships reads -- and a function named ulimit
        # would be called in the builtin's place. In privileged
        # mode it takes neither.
        env = dict(os.environ)
        env["BASH_FUNC_ulimit%%"] = "() { return 0; }"
        env["__BASH_FUNC<ulimit>()"] = "() { return 0; }"
        for shell in _shells():
            done = self._real(_PY_READ_BACK, env=env, shell=shell)
            self.assertEqual(done.returncode, 0, (shell, done.stderr))
            soft, hard = (int(x) for x in done.stdout.decode().split())
            self.assertEqual(soft, hard, shell)
            self.assertFalse(MC.reported_limit_is_unlimited(soft),
                             shell)

    def test_without_the_flag_bash_takes_the_function(self):
        # The control for the test above: the same text on the
        # same shell without -p, where the function is called
        # and no limit is set. It is why the flag is there.
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash on this host: the control needs "
                          "the shell that takes functions from its "
                          "environment")
        env = dict(os.environ)
        env["BASH_FUNC_ulimit%%"] = "() { return 0; }"
        env["__BASH_FUNC<ulimit>()"] = "() { return 0; }"
        open_done = self._real(_PY_READ_BACK, env=env,
                               shell=[bash, "--posix"])
        kept_done = self._real(_PY_READ_BACK, env=env,
                               shell=[bash, "--posix", "-p"])
        kept = [int(x) for x in kept_done.stdout.decode().split()]
        self.assertEqual(kept[0], kept[1])
        self.assertFalse(MC.reported_limit_is_unlimited(kept[0]))
        # The function answered for the builtin: the shim could
        # not read a limit through it and refused, or the job
        # ran with no limit set.
        took = open_done.returncode != 0 or [
            int(x) for x in open_done.stdout.decode().split()] != kept
        self.assertTrue(took, open_done.stdout)

    def test_an_option_list_in_the_environment_is_not_taken(self):
        # SHELLOPTS=noexec would have a shell read the shim and
        # run none of it, the job included.
        env = dict(os.environ)
        env["SHELLOPTS"] = "noexec"
        for shell in _shells():
            done = self._real(["/bin/echo", "JOB-RAN"], env=env,
                              shell=shell)
            self.assertIn(b"JOB-RAN", done.stdout, shell)

    def test_the_environment_reaches_the_job(self):
        env = {"PATH": "/usr/bin:/bin", "HP_T_PLAIN": "a b  c",
               "HP_T_EMPTY": "", "HP_T_QUOTE": "it's \"x\" $HOME"}
        done = self._real(
            'printf "%s|%s|%s\\n" "$HP_T_PLAIN" "$HP_T_EMPTY" '
            '"$HP_T_QUOTE"', env=env)
        self.assertEqual(done.stdout.decode(),
                         "a b  c||it's \"x\" $HOME\n")

    def test_the_job_s_own_arguments_arrive_whole(self):
        argv = MC.build_shim_argv(
            ["/bin/sh", "-c", 'printf "%s|" "$@"', "job",
             "a b", "$HOME", "*", "it's", "-n"])
        done = subprocess.run(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(done.stdout.decode(), "a b|$HOME|*|it's|-n|")

    def test_a_setting_s_ceiling_is_the_one_applied(self):
        done = self._real(_READ_BACK, memory=3 * 1024 ** 3)
        soft, hard = done.stdout.decode().split()
        self.assertEqual(soft, hard)
        self.assertGreaterEqual(int(soft), 3 * 1024 ** 2)

    def test_a_job_that_cannot_be_found_is_the_shell_s_refusal(self):
        done = subprocess.run(
            MC.build_shim_argv(["/hp/no/such/program"]),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertNotEqual(done.returncode, 0)


class JobUserDropTest(unittest.TestCase):
    """job_user_drop: the spawn's own arguments for the job user."""

    @staticmethod
    def _entry(name="jobs", uid=1234, gid=4321):
        return types.SimpleNamespace(pw_name=name, pw_uid=uid,
                                     pw_gid=gid)

    def test_no_user_changes_nothing(self):
        self.assertEqual(MC.job_user_drop(None), {})

    def test_a_named_user_is_its_uid_group_and_groups(self):
        drop = MC.job_user_drop(
            "jobs", lookup=lambda name: self._entry(name),
            groups=lambda name, gid: [gid, 20, 12])
        self.assertEqual(drop, {"user": 1234, "group": 4321,
                                "extra_groups": [4321, 20, 12]})

    def test_the_user_s_own_group_is_always_among_them(self):
        drop = MC.job_user_drop(
            "jobs", lookup=lambda name: self._entry(name),
            groups=lambda name, gid: [20])
        self.assertEqual(drop["extra_groups"], [4321, 20])

    def test_sixteen_groups_at_most(self):
        drop = MC.job_user_drop(
            "jobs", lookup=lambda name: self._entry(name),
            groups=lambda name, gid: [gid] + list(range(100, 140)))
        self.assertEqual(len(drop["extra_groups"]), 16)
        self.assertEqual(drop["extra_groups"][0], 4321)

    def test_a_group_list_that_cannot_be_read_leaves_the_user_s_own(self):
        def _groups(name, gid):
            raise OSError("no group database")
        drop = MC.job_user_drop(
            "jobs", lookup=lambda name: self._entry(name),
            groups=_groups)
        self.assertEqual(drop["extra_groups"], [4321])

    def test_a_group_id_the_call_cannot_take_is_asked_as_its_signed_twin(self):
        # Darwin's `nobody`: group 4294967294 in the user
        # database, -2 to getgrouplist, and -2 in its answer.
        asked = []

        def _groups(name, gid):
            asked.append(gid)
            if gid > 2 ** 31 - 1:
                raise OverflowError("signed integer is greater "
                                    "than maximum")
            return [gid, 20]

        drop = MC.job_user_drop(
            "nobody",
            lookup=lambda name: self._entry(name, 4294967294,
                                            4294967294),
            groups=_groups)
        self.assertEqual(asked, [4294967294, -2])
        self.assertEqual(drop, {"user": 4294967294,
                                "group": 4294967294,
                                "extra_groups": [4294967294, 20]})

    def test_the_one_id_no_spawn_takes_is_left_out(self):
        # The hosted Macs' list for `nobody` carries -1, which
        # the platform reads as "no group" and a spawn refuses
        # by name ("invalid group id").
        drop = MC.job_user_drop(
            "nobody",
            lookup=lambda name: self._entry(name, 4294967294,
                                            4294967294),
            groups=lambda name, gid: [-2, 12, -1, 61, 4294967295])
        self.assertEqual(drop["extra_groups"], [4294967294, 12, 61])

    def test_a_user_the_machine_does_not_have_is_a_refusal(self):
        def _lookup(name):
            raise KeyError(name)
        with self.assertRaises(RuntimeError) as caught:
            MC.job_user_drop("hp-no-such-user", lookup=_lookup)
        self.assertIn("not in this machine's user database",
                      str(caught.exception))

    def test_an_unnamable_user_is_a_refusal(self):
        for bad in ("", "a:b", "a\nb", "a\rb", "a\x00b", 123):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.job_user_drop(bad, lookup=lambda name: self._entry())

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_arguments_are_ones_the_spawn_takes(self):
        # This process's own user, applied to a child of its
        # own: no privilege is needed to change to the user one
        # already is, and the child says who it is.
        import pwd
        me = pwd.getpwuid(os.getuid())
        drop = MC.job_user_drop(me.pw_name)
        self.assertEqual(drop["user"], os.getuid())
        if os.getuid() != 0:
            # setgroups is root's call; the rest is the same.
            drop.pop("extra_groups")
        done = subprocess.run(["/bin/sh", "-c", "id -u"],
                              stdout=subprocess.PIPE, timeout=30,
                              **drop)
        self.assertEqual(done.stdout.decode().strip(),
                         str(os.getuid()))


class ReportedLimitTest(unittest.TestCase):
    """reported_limit_is_unlimited: the read-back classification.

    The deterministic substrate of the spawn-limits fix
    (supposition R6-S1 in docs/steady/security/macos.md).
    The shim sets no address-space limit, so the value a
    job reads back for one is the inherited limit as
    Python's resource module reports it, and "unlimited"
    has two reports -- -1 on Linux, 9223372036854775807
    (2**63 - 1, the Darwin sentinel) on darwin. The live
    point hardcoded the first and failed on the second
    while the address space stood unlimited. This family
    pins both reports' meaning, per value and per field,
    with the verdict's own numbers and a staged read-back
    executed through a scripted resource seam, so the
    shape cannot silently drift back to one platform's
    representation.
    """

    SENTINEL = 2 ** 63 - 1

    def test_the_named_reports_are_exactly_the_two(self):
        self.assertEqual(MC.UNLIMITED_LIMIT_REPORTS,
                         (-1, 9223372036854775807))
        self.assertEqual(self.SENTINEL, 9223372036854775807)

    def test_minus_one_is_unlimited(self):
        # The Linux report: this host's own constant.
        self.assertTrue(MC.reported_limit_is_unlimited(-1))

    def test_the_darwin_sentinel_is_unlimited(self):
        # The verdict's own failing value, classified as
        # what it is: the address space stood unlimited.
        self.assertTrue(
            MC.reported_limit_is_unlimited(9223372036854775807))

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_host_constant_is_a_named_report(self):
        # The resource module is POSIX; the Windows suite imported it
        # here on 2026-11-12 (test-windows, run 43181991886).
        import resource
        self.assertIn(resource.RLIM_INFINITY,
                      MC.UNLIMITED_LIMIT_REPORTS)
        self.assertTrue(MC.reported_limit_is_unlimited(
            resource.RLIM_INFINITY))
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if soft == resource.RLIM_INFINITY:
            self.assertTrue(MC.reported_limit_is_unlimited(soft))
        if hard == resource.RLIM_INFINITY:
            self.assertTrue(MC.reported_limit_is_unlimited(hard))

    def test_zero_is_not_unlimited(self):
        self.assertFalse(MC.reported_limit_is_unlimited(0))

    def test_finite_values_are_not_unlimited(self):
        for value in (1, 2, 512 * 1024 * 1024, 2 ** 32,
                      2 ** 62, self.SENTINEL - 1):
            self.assertFalse(
                MC.reported_limit_is_unlimited(value), value)

    def test_the_sentinel_bookends(self):
        # The values standing immediately around each
        # named report classify on their own side of it.
        self.assertFalse(
            MC.reported_limit_is_unlimited(self.SENTINEL - 1))
        self.assertTrue(
            MC.reported_limit_is_unlimited(self.SENTINEL))
        self.assertFalse(
            MC.reported_limit_is_unlimited(self.SENTINEL + 1))
        self.assertFalse(MC.reported_limit_is_unlimited(0))

    def test_values_below_minus_one_are_refused(self):
        for bad in (-2, -100, -(2 ** 62), -(2 ** 63)):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.reported_limit_is_unlimited(bad)

    def test_the_field_must_be_an_integer(self):
        for bad in (True, False, "inf", "-1", 1.5, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.reported_limit_is_unlimited(bad)

    def test_random_values_classify_by_membership(self):
        rng = random.Random(20261112)
        pool = [-1, 0, 1, self.SENTINEL - 1, self.SENTINEL,
                self.SENTINEL + 1, 2 ** 62, 512 * 1024 * 1024]
        ran = 0
        saw_unlimited = set()
        for _ in range(400):
            value = rng.choice(
                pool + [rng.randrange(0, 2 ** 64),
                        rng.randrange(0, 10 ** 12)])
            expected = value in MC.UNLIMITED_LIMIT_REPORTS
            self.assertEqual(
                MC.reported_limit_is_unlimited(value), expected,
                value)
            if expected:
                saw_unlimited.add(value)
            ran += 1
        self.assertEqual(ran, 400)
        self.assertEqual(saw_unlimited,
                         set(MC.UNLIMITED_LIMIT_REPORTS))

    def test_the_verdicts_own_shape(self):
        # P2 of the supposition, executed as a pin: the
        # triple shape the verdict carried, staged the
        # darwin way -- a data-size limit at the shim's
        # cap, which stands below the sentinel, and the
        # address-space soft at the sentinel. The fixed
        # shape holds on it; the old shape (== -1) does
        # not, which is the failure being fixed restated.
        cap = MC.DATA_LIMIT_CAP_KIB * 1024
        self.assertEqual(cap, 2 ** 62)
        limits = [cap, self.SENTINEL, self.SENTINEL]
        self.assertLess(limits[0], self.SENTINEL)
        self.assertFalse(MC.reported_limit_is_unlimited(limits[0]))
        self.assertEqual(limits[1], self.SENTINEL)
        self.assertNotEqual(limits[2], -1)
        self.assertTrue(MC.reported_limit_is_unlimited(limits[2]))

    # The executed half: a child process whose resource
    # seam is scripted the darwin way reports its
    # address-space soft limit exactly as the live
    # point's job does, so the read-back shape the fix
    # pins is exercised deterministically on every host.
    _READBACK_DRIVER = (
        "import resource, sys\n"
        "staged = int(sys.argv[1])\n"
        "def fake_get(r):\n"
        "    return (staged, staged)\n"
        "resource.getrlimit = fake_get\n"
        "print(resource.getrlimit(resource.RLIMIT_AS)[0])\n"
    )

    def _run_readback_driver(self, staged):
        return subprocess.run(
            [sys.executable, "-c", self._READBACK_DRIVER,
             str(staged)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_a_darwin_staged_readback_satisfies_the_fixed_shape(self):
        done = self._run_readback_driver(self.SENTINEL)
        self.assertEqual(done.returncode, 0,
                         done.stderr.decode("utf-8", "replace"))
        value = int(done.stdout.decode().split()[0])
        self.assertEqual(value, self.SENTINEL)
        # The old expectation fails on this very value --
        # the live failure, reproduced off darwin.
        self.assertNotEqual(value, -1)
        self.assertTrue(MC.reported_limit_is_unlimited(value))

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_a_finite_staged_readback_does_not_satisfy_it(self):
        done = self._run_readback_driver(512 * 1024 * 1024)
        self.assertEqual(done.returncode, 0,
                         done.stderr.decode("utf-8", "replace"))
        value = int(done.stdout.decode().split()[0])
        self.assertEqual(value, 512 * 1024 * 1024)
        self.assertFalse(MC.reported_limit_is_unlimited(value))


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
        self.assertEqual(argv[3:6], ["/bin/sh", "-p", "-c"])
        self.assertEqual(argv[6], MC.LIMIT_SHIM_TEXT)
        self.assertEqual(argv[7], "hp-shim")
        self.assertEqual(argv[9:], ["/usr/bin/python3", "s.py"])

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

    def test_memory_field_reaches_the_shim(self):
        argv, _profile = MC.build_sandbox_argv(
            ["/bin/echo"], cwd="/work/j", memory_bytes=2048 * 1024)
        self.assertEqual(argv[8], "2048")
        self.assertEqual(argv[9:], ["/bin/echo"])

    def test_the_job_user_is_no_field_of_the_argv(self):
        # The spawn applies the user to the whole chain; the
        # argv carries no name for a process table to show and
        # no step that would need to be root inside the
        # profile.
        with self.assertRaises(TypeError):
            MC.build_sandbox_argv(["/bin/echo"], cwd="/work/j",
                                  user="nobody")

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

    def test_bookended_symbols_never_break_the_job_user_field(self):
        ran = 0
        asked = []

        def _lookup(name):
            asked.append(name)
            return types.SimpleNamespace(pw_name=name, pw_uid=77,
                                         pw_gid=78)

        for ch in string.punctuation + " \t\x00\r\n":
            for value in (ch + "nobody", "nobody" + ch,
                          ch * 10 + "nobody", "nobody" + ch * 10):
                ran += 1
                try:
                    out = MC.job_user_drop(
                        value, lookup=_lookup,
                        groups=lambda name, gid: [gid])
                except RuntimeError:
                    self.assertTrue(
                        ":" in value
                        or any(ord(c) < 0x20 or ord(c) == 0x7f
                               for c in value),
                        repr(value))
                    continue
                # The name reached the user database as it was
                # given, and nothing of it reached the spawn.
                self.assertEqual(asked[-1], value)
                self.assertEqual(out, {"user": 77, "group": 78,
                                       "extra_groups": [78]})
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

    OK = (b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n"
          b"TRIAL-LIMIT 411256832 411256832\n")

    def _spawn(self, proc_factory, record):
        def _spawn(argv, cwd=None, env=None):
            record["argv"] = argv
            record["cwd"] = cwd
            # The program, the staged file and the work
            # directory: staged, and inside the work directory.
            record["staged_existed"] = all(
                os.path.exists(p) for p in argv[1:4])
            record["staged_inside_work"] = all(
                p == cwd or p.startswith(cwd + os.sep)
                for p in argv[1:4])
            # The two paths the trial must be refused: beside
            # the work directory, not inside it; one not there
            # yet, one there with something to read.
            record["outside_beside_work"] = all(
                os.path.dirname(p) == os.path.dirname(cwd)
                for p in argv[4:6])
            record["outside_new_existed"] = os.path.exists(argv[4])
            record["outside_kept_existed"] = os.path.exists(argv[5])
            return proc_factory(cwd)
        return _spawn

    def test_trial_ok_answers_none_and_cleans_up(self):
        record = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=self.OK, work=work, write_file=True), record)
        self.assertIsNone(MC.confinement_trial_problem(spawn))
        self.assertTrue(record["staged_existed"])
        self.assertTrue(record["staged_inside_work"])
        self.assertTrue(record["outside_beside_work"])
        self.assertFalse(record["outside_new_existed"])
        self.assertTrue(record["outside_kept_existed"])
        self.assertEqual(record["argv"][0], "/bin/sh")
        self.assertEqual(len(record["argv"]), 6)
        root = os.path.dirname(record["cwd"])
        self.assertFalse(os.path.exists(root))

    def test_a_passing_trial_hands_back_the_limit_it_read(self):
        facts = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=self.OK, work=work, write_file=True), {})
        self.assertIsNone(
            MC.confinement_trial_problem(spawn, facts=facts))
        self.assertEqual(facts, {"limit_kib": 411256832,
                                 "clipboard_open": False})

    def test_a_trial_the_pasteboard_answered_is_a_problem(self):
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=self.OK + b"TRIAL-CLIPBOARD-OPEN\n", work=work,
                write_file=True), {})
        problem = MC.confinement_trial_problem(spawn)
        self.assertEqual(
            problem, "a confined process was answered by the "
                     "pasteboard, a service the profile does not "
                     "name: the profile did not hold")

    def test_a_config_that_names_the_pasteboard_is_not_refused_for_it(self):
        facts = {}
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=self.OK + b"TRIAL-CLIPBOARD-OPEN\n", work=work,
                write_file=True), {})
        self.assertIsNone(MC.confinement_trial_problem(
            spawn, facts=facts, clipboard_closed=False))
        self.assertEqual(facts, {"limit_kib": 411256832,
                                 "clipboard_open": True})

    def test_a_write_outside_the_work_directory_is_a_problem(self):
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=self.OK + b"TRIAL-WROTE-OUTSIDE\n", work=work,
                write_file=True), {})
        problem = MC.confinement_trial_problem(spawn)
        self.assertIn("wrote a file outside its work directory",
                      problem)

    def test_a_file_left_outside_is_a_problem_whatever_was_said(self):
        # The trial's own word is not the only evidence: a file
        # standing where the write was to be refused convicts a
        # trial that printed nothing about it.
        def _factory(work):
            with open(os.path.join(os.path.dirname(work),
                                   "outside-write.txt"), "w") as fh:
                fh.write("x")
            return _FakeTrialProc(out=self.OK, work=work,
                                  write_file=True)
        problem = MC.confinement_trial_problem(self._spawn(_factory, {}))
        self.assertIn("wrote a file outside its work directory",
                      problem)

    def test_a_read_outside_the_work_directory_is_a_problem(self):
        spawn = self._spawn(
            lambda work: _FakeTrialProc(
                out=self.OK + b"TRIAL-READ-OUTSIDE\n", work=work,
                write_file=True), {})
        problem = MC.confinement_trial_problem(spawn)
        self.assertIn("read a file outside its work directory",
                      problem)

    def test_a_trial_with_no_ceiling_of_its_own_is_a_problem(self):
        for limit in (b"", b"TRIAL-LIMIT unlimited unlimited\n",
                      b"TRIAL-LIMIT 524288 unlimited\n",
                      b"TRIAL-LIMIT 524288 1048576\n"):
            spawn = self._spawn(
                lambda work, limit=limit: _FakeTrialProc(
                    out=b"TRIAL-READ-OK\nTRIAL-WRITE-OK\n" + limit,
                    work=work, write_file=True), {})
            problem = MC.confinement_trial_problem(spawn)
            self.assertIn("carried no data-size ceiling of its own",
                          problem, limit)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_trial_program_convicts_a_spawn_that_confines_nothing(self):
        # The real program on this host through a spawn that
        # applies no profile and no shim: it reads and writes
        # as a job does, and then writes outside its work
        # directory, which is the trial's answer. A probe that
        # passed here would pass a sandbox that did nothing.
        def _open_spawn(argv, cwd=None, env=None):
            inner = subprocess.Popen(
                argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            inner.close = lambda: None
            return inner
        problem = MC.confinement_trial_problem(_open_spawn)
        self.assertIn("wrote a file outside its work directory",
                      problem)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_trial_program_reads_the_shim_s_limit(self):
        # The real program under the real shim, with no
        # profile: the staged read, the work write and the
        # limit are all there, and the write outside is what
        # is left to convict it -- on a host that is not a Mac
        # the profile is the one part that cannot be had.
        said = {}

        def _shim_spawn(argv, cwd=None, env=None):
            inner = subprocess.Popen(
                MC.build_shim_argv(argv), cwd=cwd, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            out, err = inner.communicate(timeout=60)
            said["out"] = out.decode()
            return _FakeTrialProc(out=out, err=err,
                                  returncode=inner.returncode)
        problem = MC.confinement_trial_problem(_shim_spawn)
        self.assertIn("wrote a file outside its work directory",
                      problem)
        soft, hard = MC._trial_limit(said["out"])
        self.assertEqual(soft, hard)
        self.assertTrue(soft.isdigit())
        self.assertIn("TRIAL-READ-OUTSIDE", said["out"])

    def _run_program(self, text):
        """The program's text run by the system shell, with no
        profile and no shim: (process, work directory)."""
        tmp = tempfile.mkdtemp(prefix="hp-trial-program-")
        self.addCleanup(shutil.rmtree, tmp, True)
        work = os.path.join(tmp, "work")
        os.makedirs(work)
        staged = os.path.join(work, "trial-staged.txt")
        with open(staged, "w", encoding="utf-8") as fh:
            fh.write(MC._TRIAL_MARKER + "\n")
        program = os.path.join(work, "trial_program.sh")
        with open(program, "w", encoding="utf-8") as fh:
            fh.write(text)
        kept = os.path.join(tmp, "outside-kept.txt")
        with open(kept, "w", encoding="utf-8") as fh:
            fh.write(MC._TRIAL_OUTSIDE + "\n")
        done = subprocess.run(
            [MC.SHELL_BIN, program, staged, work,
             os.path.join(tmp, "outside-write.txt"), kept],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=60)
        return done, work

    def _reader(self, exit_code):
        """The program with a reader of this test's own in the
        system reader's place: one that prints a clipboard and
        ends with `exit_code`."""
        folder = tempfile.mkdtemp(prefix="hp-trial-reader-")
        self.addCleanup(shutil.rmtree, folder, True)
        stub = os.path.join(folder, "reader")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\necho WHAT-THE-CLIPBOARD-HELD\n"
                     "echo AND-ITS-COMPLAINT >&2\n"
                     "exit %d\n" % exit_code)
        os.chmod(stub, 0o755)
        self.assertEqual(MC._TRIAL_PROGRAM.count(MC.PASTEBOARD_READER), 2)
        return MC._TRIAL_PROGRAM.replace(MC.PASTEBOARD_READER, stub)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_the_trial_program_writes_what_it_read(self):
        # The file a trial leaves in its work directory is the
        # staged data, a line for a line: the shell's own
        # format word reaches the shell as it is written here.
        done, work = self._run_program(MC._TRIAL_PROGRAM)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(os.path.join(work, "trial-out.txt"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), MC._TRIAL_MARKER + "\n")
        lines = done.stdout.decode().splitlines()
        self.assertEqual(lines[:4], [
            "TRIAL-READ-OK", "TRIAL-WRITE-OK", "TRIAL-WROTE-OUTSIDE",
            "TRIAL-READ-OUTSIDE"])
        self.assertTrue(lines[4].startswith("TRIAL-LIMIT "), lines)
        self.assertIn('printf "%s\\n" "$data" > "$2/trial-out.txt"',
                      MC._TRIAL_PROGRAM)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_a_reader_that_is_answered_is_reported_and_not_repeated(self):
        done, _work = self._run_program(self._reader(0))
        self.assertEqual(done.returncode, 0, done.stderr)
        said = done.stdout.decode()
        self.assertEqual(said.splitlines()[-1], "TRIAL-CLIPBOARD-OPEN")
        # The answer is the fact: what the reader printed goes
        # nowhere, so a trial never carries a clipboard into a
        # log or a report.
        for text in (said, done.stderr.decode()):
            self.assertNotIn("WHAT-THE-CLIPBOARD-HELD", text)
            self.assertNotIn("AND-ITS-COMPLAINT", text)

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_a_reader_that_is_refused_is_no_report_and_no_failure(self):
        for code in (1, 2, 134):
            done, _work = self._run_program(self._reader(code))
            self.assertEqual(done.returncode, 0, (code, done.stderr))
            said = done.stdout.decode()
            self.assertNotIn("TRIAL-CLIPBOARD-OPEN", said, code)
            self.assertTrue(
                said.splitlines()[-1].startswith("TRIAL-LIMIT "), code)
            self.assertNotIn("AND-ITS-COMPLAINT", done.stderr.decode())

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_a_host_with_no_reader_is_no_report_and_no_failure(self):
        gone = os.path.join(tempfile.gettempdir(),
                            "hp-no-such-reader-%d" % os.getpid())
        self.assertFalse(os.path.exists(gone))
        done, _work = self._run_program(
            MC._TRIAL_PROGRAM.replace(MC.PASTEBOARD_READER, gone))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("TRIAL-CLIPBOARD-OPEN", done.stdout.decode())
        self.assertEqual(done.stderr, b"")

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

    def test_the_record_s_detail_is_what_the_launch_carried(self):
        backend = _backend(None, notes=(
            "memory ceiling 512 MiB above a bare process's address "
            "map, soft and hard",
            "job user nobody applied at the spawn door"))
        (_proc, _release), sink = self._run(
            _ccfg("enforce"), {"confinement": "enforce"},
            backend=backend)
        self.assertEqual(
            sink[0]["kw"]["detail"],
            "memory ceiling 512 MiB above a bare process's address "
            "map, soft and hard; job user nobody applied at the "
            "spawn door")

    def test_a_backend_with_no_notes_records_no_detail(self):
        (_proc, _release), sink = self._run(
            _ccfg("enforce"), {"confinement": "enforce"},
            backend=_backend(None))
        self.assertEqual(sink[0]["kw"]["detail"], "")

    def test_the_config_rides_to_the_spawn(self):
        backend = _backend(None)
        cfg = {"security": {
            "modes": {"confinement": "enforce"},
            "confinement": {"macos": {
                "process_memory_bytes": 2 * 1024 ** 3}}}}
        self._run(cfg, {"confinement": "enforce"}, backend=backend)
        self.assertIs(backend.spawned[0]["cfg"], cfg)

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


class SettingsTest(unittest.TestCase):
    """security.confinement.macos: the backend's own settings."""

    def test_the_ceiling_defaults_to_512_mib(self):
        for cfg in (None, {}, {"security": {}},
                    {"security": {"confinement": {}}},
                    {"security": {"confinement": {"macos": {}}}}):
            self.assertEqual(
                MC.confinement_settings(cfg),
                {"process_memory_bytes": 512 * 1024 * 1024,
                 "mach_services": ()}, cfg)

    def test_the_operator_s_ceiling_is_the_one_read(self):
        cfg = {"security": {"confinement": {"macos": {
            "process_memory_bytes": 2 * 1024 ** 3}}}}
        self.assertEqual(
            MC.confinement_settings(cfg)["process_memory_bytes"],
            2 * 1024 ** 3)

    def test_the_known_settings_are_exactly_these(self):
        self.assertEqual(MC.MACOS_KEYS,
                         ("process_memory_bytes", "mach_services"))

    def test_the_operator_s_services_are_read_once_each_in_order(self):
        cfg = {"security": {"confinement": {"macos": {"mach_services": [
            "com.example.two", "com.apple.pasteboard.1",
            "com.example.two",
            "com.apple.system.opendirectoryd.libinfo"]}}}}
        self.assertEqual(
            MC.confinement_settings(cfg)["mach_services"],
            ("com.example.two", "com.apple.pasteboard.1"))

    def test_a_service_list_that_is_not_one_is_an_error(self):
        for bad in ("com.example.one", None, 1, ["a b"], [1],
                    ["ok.name", 'x") (allow default) ("'],
                    ["s%d" % n for n in range(65)]):
            with self.assertRaises(RuntimeError, msg=repr(bad)) as caught:
                MC.validate_macos_block({"mach_services": bad})
            self.assertIn(
                "config error: security.confinement.macos."
                "mach_services: ", str(caught.exception))
        self.assertTrue(MC.validate_macos_block(
            {"mach_services": []}))
        self.assertTrue(MC.validate_macos_block(
            {"mach_services": ["com.apple.pasteboard.1"]}))

    def test_a_setting_the_backend_does_not_know_is_an_error(self):
        # A ceiling the operator misspelled is a ceiling that
        # is not there.
        with self.assertRaises(RuntimeError) as caught:
            MC.validate_macos_block({"process_memory": 1})
        self.assertIn("security.confinement.macos.process_memory is "
                      "not a known setting", str(caught.exception))
        self.assertIn("process_memory_bytes", str(caught.exception))

    def test_a_ceiling_must_be_a_positive_integer(self):
        for bad in (0, -1, True, False, "512", 1.5, None, [1]):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.validate_macos_block({"process_memory_bytes": bad})

    def test_the_block_must_be_an_object(self):
        for bad in ([], "x", 1, None):
            with self.assertRaises(RuntimeError, msg=repr(bad)):
                MC.validate_macos_block(bad)

    def test_a_config_is_right_or_wrong_the_same_way_on_every_host(self):
        # The sandbox module checks the confinement block
        # wherever a config is read, and hands this backend's
        # part to this backend.
        SB._validate_confinement_block(
            {"macos": {"process_memory_bytes": 1024}})
        with self.assertRaises(RuntimeError):
            SB._validate_confinement_block(
                {"macos": {"process_memory_bytes": "big"}})
        with self.assertRaises(RuntimeError):
            SB._validate_confinement_block({"macos": {"cores": 2}})
        SB._validate_confinement_block(
            {"macos": {"mach_services": ["com.example.one"]}})
        with self.assertRaises(RuntimeError):
            SB._validate_confinement_block(
                {"macos": {"mach_services": ["not a name"]}})

    def test_the_other_backends_keys_are_not_this_backend_s(self):
        cfg = {"security": {"confinement": {
            "work_mount": "/work", "extra_ro_binds": [["/a", "/b"]],
            "freebsd": {"job_cpus": 2}}}}
        self.assertEqual(
            MC.confinement_settings(cfg),
            {"process_memory_bytes": 512 * 1024 * 1024,
             "mach_services": ()})


class PostureLinesTest(unittest.TestCase):
    """posture_lines: what a job carries on this host, in words."""

    APPLE = {"limit_kib": 410732544 + 524288}

    @staticmethod
    def _passes(cfg):
        return None

    def test_a_host_with_a_floor_names_the_floor(self):
        lines = MC.posture_lines({}, probe=self._passes,
                                 facts=self.APPLE, root=False)
        self.assertEqual(lines, [
            ("OK", "macOS backend: macos: seatbelt_profile + "
                   "no_network + spawn_resource_limits"),
            ("OK", "a job process's address map may grow 512 MiB "
                   "past the 391.7 GiB a bare process starts at "
                   "here; the ceiling is not the job's to raise "
                   "(ulimit in the launcher shim, soft and hard)"),
            ("OK", "a job may ask the user database who a user is, "
                   "and no other of the session's services: the "
                   "clipboard is refused")])

    def test_the_operator_s_services_are_named_in_the_report(self):
        cfg = {"security": {"confinement": {"macos": {"mach_services": [
            "com.apple.pasteboard.1", "com.example.one"]}}}}
        lines = MC.posture_lines(cfg, probe=self._passes,
                                 facts=self.APPLE, root=False)
        self.assertEqual(
            lines[2],
            ("OK", "a job may ask the user database who a user is, "
                   "and the services this config names: "
                   "com.apple.pasteboard.1, com.example.one "
                   "(security.confinement.macos.mach_services); "
                   "the pasteboard is among them, so the clipboard "
                   "is not refused"))

    def test_the_report_says_when_the_pasteboard_is_not_among_them(self):
        cfg = {"security": {"confinement": {"macos": {"mach_services": [
            "com.example.one", "com.example.one",
            "com.apple.system.opendirectoryd.libinfo"]}}}}
        lines = MC.posture_lines(cfg, probe=self._passes,
                                 facts=self.APPLE, root=False)
        self.assertEqual(
            lines[2],
            ("OK", "a job may ask the user database who a user is, "
                   "and the services this config names: "
                   "com.example.one (security.confinement.macos."
                   "mach_services); the pasteboard is not among "
                   "them"))

    def test_the_services_line_is_the_report_s_own(self):
        self.assertEqual(
            MC.services_line(),
            "a job may ask the user database who a user is, and no "
            "other of the session's services: the clipboard is "
            "refused")
        # The backend's own names handed back are no operator's.
        self.assertEqual(MC.services_line(MC.SESSION_SERVICES),
                         MC.services_line())
        with self.assertRaises(RuntimeError):
            MC.services_line(["not a name"])

    def test_a_host_with_no_floor_names_the_ceiling_itself(self):
        lines = MC.posture_lines({}, probe=self._passes,
                                 facts={"limit_kib": 524288},
                                 root=False)
        self.assertEqual(
            lines[1][1],
            "a job process's address map is held to 512 MiB here; "
            "the ceiling is not the job's to raise (ulimit in the "
            "launcher shim, soft and hard)")

    def test_no_reading_names_no_number_it_did_not_read(self):
        lines = MC.posture_lines({}, probe=self._passes, facts={},
                                 root=False)
        self.assertEqual(
            lines[1][1],
            "a job process's address map may grow 512 MiB past "
            "the size a bare process starts at; the ceiling is "
            "not the job's to raise (ulimit in the launcher shim, "
            "soft and hard)")

    def test_the_operator_s_ceiling_is_the_one_named(self):
        cfg = {"security": {"confinement": {"macos": {
            "process_memory_bytes": 2 * 1024 ** 3}}}}
        lines = MC.posture_lines(
            cfg, probe=self._passes,
            facts={"limit_kib": 34128896 + 2 * 1024 ** 2}, root=False)
        self.assertIn("may grow 2.0 GiB past the 32.5 GiB",
                      lines[1][1])

    def test_a_probe_that_does_not_pass_is_one_warning(self):
        lines = MC.posture_lines(
            {}, probe=lambda cfg: "/usr/bin/sandbox-exec is missing "
                                  "or not executable")
        self.assertEqual(lines, [(
            "WARN", "macOS backend cannot engage: "
                    "/usr/bin/sandbox-exec is missing or not "
                    "executable; confinement in enforce mode would "
                    "refuse to start")])

    def test_a_probe_that_raises_is_a_warning_too(self):
        def _probe(cfg):
            raise OSError("no such host")
        lines = MC.posture_lines({}, probe=_probe)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][0], "WARN")
        self.assertIn("no such host", lines[0][1])

    def test_a_malformed_block_is_a_warning_and_asks_nothing(self):
        asked = []
        lines = MC.posture_lines(
            {"security": {"confinement": {"macos": {"cores": 1}}}},
            probe=lambda cfg: asked.append(cfg))
        self.assertEqual(asked, [])
        self.assertEqual(lines[0][0], "WARN")
        self.assertIn("not a known setting", lines[0][1])

    def test_an_engaged_job_user_is_named(self):
        cfg = {"security": {"job_user": {"user": "nobody"}}}
        lines = MC.posture_lines(cfg, probe=self._passes,
                                 facts=self.APPLE, root=True)
        self.assertEqual(len(lines), 4)
        self.assertIn("the ceiling is not the job's to raise",
                      lines[1][1])
        self.assertEqual(
            lines[3],
            ("OK", "a job is started as nobody at the spawn door "
                   "(security.job_user) and reads what that user "
                   "can read"))

    def test_a_job_user_whose_mode_is_down_is_not(self):
        cfg = {"security": {"modes": {"job_user": "audit"},
                            "job_user": {"user": "nobody"}}}
        lines = MC.posture_lines(cfg, probe=self._passes,
                                 facts=self.APPLE, root=False)
        self.assertEqual(len(lines), 3)

    def test_a_root_runner_with_no_job_user_is_told_so(self):
        # Root may raise a hard limit, under a profile as
        # anywhere: read on both hosted Macs, where a root job's
        # subshell lifted its own. The report says the ceiling
        # is set and does not say it holds, and one line of
        # advice names the remedy.
        for cfg in ({}, {"security": {"modes": {"job_user": "audit"},
                                      "job_user": {"user": "nobody"}}}):
            lines = MC.posture_lines(cfg, probe=self._passes,
                                     facts=self.APPLE, root=True)
            self.assertEqual(
                lines[1],
                ("OK", "a job process's address map may grow "
                       "512 MiB past the 391.7 GiB a bare process "
                       "starts at here; it is set soft and hard "
                       "(ulimit in the launcher shim), and a job "
                       "that is root can raise it"))
            self.assertEqual(
                lines[3],
                ("WARN", "this runner is root and names no job "
                         "user: a job is root under the profile, "
                         "and root can raise its own ceiling (name "
                         "a user under security.job_user)"))
            self.assertEqual(len(lines), 4)

    def test_whether_the_runner_is_root_is_read_from_the_host(self):
        lines = MC.posture_lines({}, probe=self._passes,
                                 facts=self.APPLE)
        self.assertEqual(
            len(lines), 4 if getattr(os, "geteuid", lambda: 1)() == 0
            else 3)

    def test_the_stub_s_own_answer_is_a_warning(self):
        if MC.IS_MACOS_BACKEND:
            self.skipTest("the stub exists only off darwin")
        lines = MC.posture_lines({})
        self.assertEqual(lines[0][0], "WARN")
        self.assertIn("macOS-only", lines[0][1])

    def test_the_posture_report_carries_the_backend_s_lines(self):
        results = []
        said = [("OK", "macOS backend: x"), ("OK", "a ceiling")]
        with mock.patch.object(POST.sys, "platform", "darwin"), \
                mock.patch.object(POST, "_macos_confinement_lines",
                                  lambda cfg: said):
            POST._check_confinement_backend(results, {})
        self.assertEqual(results, [
            ("OK", "confinement", "macOS backend: x"),
            ("OK", "confinement", "a ceiling")])

    def test_a_backend_that_cannot_be_read_is_a_warning_there(self):
        def _lines(cfg):
            raise ImportError("no module")
        results = []
        with mock.patch.object(POST.sys, "platform", "darwin"), \
                mock.patch.object(POST, "_macos_confinement_lines",
                                  _lines):
            POST._check_confinement_backend(results, {})
        self.assertEqual(results[0][0], "WARN")
        self.assertIn("could not be read", results[0][2])

    def test_sizes_read_as_a_person_reads_them(self):
        self.assertEqual(MC.human_size(524288), "512 MiB")
        self.assertEqual(MC.human_size(1024), "1 MiB")
        self.assertEqual(MC.human_size(1048576), "1.0 GiB")
        self.assertEqual(MC.human_size(410732544), "391.7 GiB")
        self.assertEqual(MC.human_size(34128896), "32.5 GiB")


_SEED_LINES = (
    "macOS backend: macos: seatbelt_profile + no_network + "
    "spawn_resource_limits",
    "a job process's address map may grow 512 MiB past the "
    "391.7 GiB a bare process starts at here; the ceiling is not "
    "the job's to raise (ulimit in the launcher shim, soft and "
    "hard)",
    "a job may ask the user database who a user is, and no other "
    "of the session's services: the clipboard is refused")


class _SeedProbe:
    """A scripted answer to the seed's question, and what it
    was asked with."""

    def __init__(self, problem=None, lines=_SEED_LINES, error=None):
        self.problem, self.lines, self.error = problem, lines, error
        self.asked = []

    def __call__(self, cfg):
        self.asked.append(json.loads(json.dumps(cfg)))
        if self.error is not None:
            raise self.error
        return self.problem, (() if self.problem else self.lines)


def _fresh_config(folder, modes=None):
    """A config as a fresh install leaves it in `folder`: both
    gates at enforce, or the modes handed in."""
    cfg = {"security": {"modes": dict(
        modes or {"confinement": "enforce", "job_user": "enforce"})}}
    path = os.path.join(folder, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return path


def _config_in(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _machine_asked(word="1"):
    """The seed's questions to the machine, switched on for one
    test (or off, by `word`). The suite switches them off for
    every test that does not ask for them
    (runner/tests/__init__.py): a test run is not an install."""
    return mock.patch.dict(os.environ, {INS.SEED_SWITCH: word})


class SeedTest(unittest.TestCase):
    """The mode a fresh macOS config states: the machine's answer."""

    def _apply(self, path, probe=None, platform="darwin"):
        out = io.StringIO()
        with redirect_stdout(out):
            applied = INS.apply_platform_modes(path, platform,
                                               probe=probe)
        return applied, out.getvalue()

    # --- the map, where nothing is asked -----------------------

    def test_platform_modes_states_confinement_audit_only(self):
        self.assertEqual(INS.platform_modes("darwin"),
                         {"confinement": "audit"})

    def test_a_platform_only_named_is_stated_and_not_asked(self):
        # A caller that names macOS is asking about macOS, not
        # about this machine.
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        SU.seed_platform_modes(cfg, platform="darwin")
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        # job_user is a POSIX demote and engages on macOS; the
        # seed does not state it down.
        self.assertEqual(cfg["security"]["modes"]["job_user"],
                         "enforce")
        self.assertEqual(INS.fresh_platform_modes({}, "darwin"),
                         ({"confinement": "audit"}, None))

    # --- the question ------------------------------------------

    def test_a_passing_probe_leaves_confinement_at_enforce(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        probe = _SeedProbe()
        modes, asked = INS.fresh_platform_modes(cfg, "darwin", probe)
        self.assertEqual(probe.asked, [cfg])
        self.assertEqual(modes, {})
        self.assertEqual(asked, (None, _SEED_LINES))
        self.assertEqual(asked.asked, INS.MACOS_PROBE_ASKED)

    def test_a_failing_probe_states_audit_and_carries_the_reason(self):
        probe = _SeedProbe("/usr/bin/sandbox-exec is missing or "
                           "not executable")
        modes, asked = INS.fresh_platform_modes({}, "darwin", probe)
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertEqual(asked[0], "/usr/bin/sandbox-exec is missing "
                                   "or not executable")
        self.assertEqual(asked[1], ())
        self.assertEqual(
            INS.seed_reason(asked, "confinement", "the default"),
            "the macOS backend's probe, asked on this machine as "
            "this user, did not pass: /usr/bin/sandbox-exec is "
            "missing or not executable")

    def test_a_probe_that_raises_is_a_reason_never_a_pass(self):
        probe = _SeedProbe(error=OSError("no such tool"))
        modes, asked = INS.fresh_platform_modes({}, "darwin", probe)
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertIn("no such tool", asked[0])

    def test_a_mode_the_operator_stated_down_is_never_asked_about(self):
        for stated in ("audit", "off"):
            probe = _SeedProbe()
            cfg = {"security": {"modes": {"confinement": stated}}}
            modes, asked = INS.fresh_platform_modes(cfg, "darwin",
                                                    probe)
            self.assertEqual(probe.asked, [], stated)
            self.assertIsNone(asked, stated)
            self.assertEqual(modes, {"confinement": "audit"})

    def test_a_mac_is_asked_through_the_backend_s_own_probe(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        probe = _SeedProbe()
        with _machine_asked(), \
                mock.patch.object(INS, "_HOST_PLATFORM", "darwin"), \
                mock.patch.object(INS.sys, "platform", "darwin"), \
                mock.patch.object(INS, "macos_seed_probe", probe):
            modes, asked = INS.fresh_platform_modes(cfg)
        self.assertEqual(probe.asked, [cfg])
        self.assertEqual(modes, {})
        self.assertEqual(asked.asked, INS.MACOS_PROBE_ASKED)

    def test_a_test_run_is_not_an_install(self):
        # With the switch off -- the suite's own state -- a Mac
        # is not asked, and the seed says so.
        probe = _SeedProbe()
        with _machine_asked("0"), \
                mock.patch.object(INS, "_HOST_PLATFORM", "darwin"), \
                mock.patch.object(INS.sys, "platform", "darwin"), \
                mock.patch.object(INS, "macos_seed_probe", probe):
            modes, asked = INS.fresh_platform_modes({})
        self.assertEqual(probe.asked, [])
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertEqual(asked, (INS.SEED_NOT_ASKED, ()))
        self.assertEqual(
            INS.seed_reason(asked, "confinement", "the default"),
            INS.SEED_NOT_ASKED)

    def test_another_host_is_never_asked_macos_s_question(self):
        probe = _SeedProbe()
        with _machine_asked(), \
                mock.patch.object(INS, "_HOST_PLATFORM", "linux"), \
                mock.patch.object(INS, "macos_seed_probe", probe):
            modes, asked = INS.fresh_platform_modes({}, "darwin")
        self.assertEqual(probe.asked, [])
        self.assertIsNone(asked)

    def test_no_job_user_is_named_on_macos(self):
        # The second question is the jail's. A macOS runner is
        # its user's own agent: its jobs are that user's, under
        # a profile that needs no privilege.
        asked = INS.SeedAnswer(None, _SEED_LINES, INS.MACOS_PROBE_ASKED)
        tried = []

        def _trial(cfg, user):
            tried.append(user)
            return None, ()

        self.assertEqual(
            INS.fresh_job_user({}, asked, "darwin", trial=_trial,
                               account=lambda: ("pigeon-jobs", True,
                                                None)),
            (None, None))
        self.assertEqual(tried, [])

    def test_a_plain_pair_still_reads_as_the_jail_s_answer(self):
        # An answer with no words of its own is the FreeBSD
        # probe's, as it was before this backend's seed asked.
        self.assertEqual(INS._probe_asked((None, ())),
                         INS.FREEBSD_PROBE_ASKED)
        answer = INS.SeedAnswer(None, ["a"])
        self.assertEqual(answer, (None, ("a",)))
        self.assertEqual(answer.asked, INS.FREEBSD_PROBE_ASKED)

    # --- the installer's seed ----------------------------------

    def test_the_installer_leaves_enforce_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = _fresh_config(d)
            with open(path, "rb") as fh:
                before = fh.read()
            applied, out = self._apply(path, probe=_SeedProbe())
            with open(path, "rb") as fh:
                after = fh.read()
        self.assertEqual(applied, {})
        self.assertEqual(before, after)
        self.assertIn(
            "platform: security.modes.confinement left at enforce in "
            "%s (the macOS backend's probe, asked on this machine as "
            "this user, passed; the startup gate asks it again at "
            "every start)" % path, out)
        for line in _SEED_LINES:
            self.assertIn("platform: " + line, out)
        self.assertNotIn("stated as audit", out)
        self.assertNotIn("job_user", out)
        self.assertNotIn("jail", out)

    def test_the_installer_states_audit_with_the_probe_s_reason(self):
        with tempfile.TemporaryDirectory() as d:
            path = _fresh_config(d)
            applied, out = self._apply(
                path, probe=_SeedProbe("a confined process could "
                                       "not read its staged file"))
            cfg = _config_in(path)
        self.assertEqual(applied, {"confinement": "audit"})
        self.assertEqual(cfg["security"]["modes"],
                         {"confinement": "audit", "job_user": "enforce"})
        self.assertIn(
            "platform: security.modes.confinement stated as audit in "
            "%s (the macOS backend's probe, asked on this machine as "
            "this user, did not pass: a confined process could not "
            "read its staged file; the mode is stated in the file "
            "rather than left to refuse the first start)" % path, out)
        self.assertNotIn("left at enforce", out)

    def test_a_later_run_does_not_touch_a_mode_stated_down(self):
        with tempfile.TemporaryDirectory() as d:
            path = _fresh_config(d, {"confinement": "off"})
            probe = _SeedProbe()
            applied, out = self._apply(path, probe=probe)
            cfg = _config_in(path)
        self.assertEqual(applied, {})
        self.assertEqual(probe.asked, [])
        self.assertEqual(cfg["security"]["modes"]["confinement"], "off")
        self.assertEqual(out, "")

    # --- the setup wizard's seed -------------------------------

    def test_the_wizard_s_seed_takes_the_same_answer(self):
        cfg = {"security": {"modes": {
            "confinement": "enforce", "job_user": "enforce"}}}
        answers = []
        stated = SU.seed_platform_modes(
            cfg, platform="darwin", probe=_SeedProbe(), asked=answers)
        self.assertEqual(stated, {})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "enforce")
        self.assertNotIn("job_user", cfg["security"])
        answer, user, door = answers[0]
        self.assertEqual(answer.asked, INS.MACOS_PROBE_ASKED)
        self.assertIsNone(user)
        self.assertIsNone(door)
        lines = INS.seed_kept_lines(answer, "/x/config.json", user, door)
        self.assertEqual(len(lines), 1 + len(_SEED_LINES))
        self.assertIn("the macOS backend's probe", lines[0])

    def test_the_wizard_states_audit_where_the_probe_does_not_pass(self):
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        answers = []
        stated = SU.seed_platform_modes(
            cfg, platform="darwin",
            probe=_SeedProbe("sandbox-exec cannot start a confined "
                             "process (exit 71)"), asked=answers)
        self.assertEqual(stated, {"confinement": "audit"})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        self.assertIn("exit 71", answers[0][0][0])

    # --- reaching the backend ----------------------------------

    def test_the_seed_s_probe_refuses_where_the_backend_is_a_stub(self):
        if MC.IS_MACOS_BACKEND:
            self.skipTest("the stub exists only off darwin")
        problem, lines = INS.macos_seed_probe({})
        self.assertEqual(
            problem, "the macOS backend (runner/guard/"
                     "macos_confine.py) could not be loaded on this "
                     "machine")
        self.assertEqual(lines, ())

    def test_a_backend_that_cannot_answer_is_a_reason(self):
        backend = types.SimpleNamespace(IS_MACOS_BACKEND=True)

        def _probe(cfg):
            raise RuntimeError("the trial could not be staged")
        backend.macos_confinement_problem = _probe
        with mock.patch.object(INS, "_import_macos_confine",
                               lambda: backend):
            problem, lines = INS.macos_seed_probe({})
        self.assertEqual(problem, "the macOS backend could not "
                                  "answer: the trial could not be "
                                  "staged")
        self.assertEqual(lines, ())

    def test_a_passing_backend_hands_back_its_posture_lines(self):
        backend = types.SimpleNamespace(
            IS_MACOS_BACKEND=True,
            macos_confinement_problem=lambda cfg: None,
            posture_lines=lambda cfg: [("OK", "one"), ("OK", "two")])
        with mock.patch.object(INS, "_import_macos_confine",
                               lambda: backend):
            self.assertEqual(INS.macos_seed_probe({}),
                             (None, ("one", "two")))

    def test_the_backend_stands_alone(self):
        # The frozen installer carries this one file and loads it
        # by path: it may import nothing of the runner's.
        with open(MC.__file__, encoding="utf-8") as fh:
            source = fh.read()
        for line in source.splitlines():
            words = line.split()
            if words[:1] in (["import"], ["from"]):
                self.assertNotIn("runner", words[1], line)
                self.assertNotIn("guard", words[1], line)
        loaded = INS._load_macos_by_path(MC.__file__)
        self.assertIsNot(loaded, MC)
        self.assertEqual(loaded.STATUS_CONFINEMENT,
                         MC.STATUS_CONFINEMENT)
        self.assertEqual(loaded.LIMIT_SHIM_TEXT, MC.LIMIT_SHIM_TEXT)

    def test_a_frozen_installer_loads_the_file_it_carries(self):
        with tempfile.TemporaryDirectory() as bundle:
            os.mkdir(os.path.join(bundle, "pigeon-guard"))
            carried = os.path.join(bundle, "pigeon-guard",
                                   "macos_confine.py")
            shutil.copyfile(MC.__file__, carried)
            with mock.patch.object(INS.sys, "_MEIPASS", bundle,
                                   create=True):
                loaded = INS._import_macos_confine()
            self.assertEqual(os.path.realpath(loaded.__file__),
                             os.path.realpath(carried))

    def test_a_frozen_runner_s_wizard_finds_the_package(self):
        # A frozen runner carries no such data file; its setup
        # wizard finds the backend where the runner does.
        with tempfile.TemporaryDirectory() as bundle:
            with mock.patch.object(INS.sys, "_MEIPASS", bundle,
                                   create=True):
                self.assertIs(INS._import_macos_confine(), MC)

    def test_the_two_macos_installers_are_frozen_with_the_file(self):
        with open(os.path.join(_REPO, ".github", "workflows",
                               "build.yml"), encoding="utf-8") as fh:
            build = fh.read()
        carried = ('--add-data "runner/guard/macos_confine.py:'
                   'pigeon-guard"')
        lines = [ln for ln in build.splitlines()
                 if "pyinstaller" in ln and "--name install " in ln
                 and carried in ln]
        self.assertEqual(len(lines), 2)
        for job in ("build-macos", "build-macos-x86_64"):
            block = build.split("\n  %s:\n" % job, 1)[1]
            block = block.split("\n  build-", 1)[0]
            self.assertIn(carried, block, job)


class PagesTest(unittest.TestCase):
    """The pages say what the code does, in the code's words."""

    @staticmethod
    def _page(*parts):
        with open(os.path.join(_REPO, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_the_pages_carry_the_setting_and_the_controls(self):
        for parts in (("docs", "steady", "design",
                       "macos-confinement-design.md"),
                      ("docs", "steady", "security", "macos.md"),
                      ("SECURITY.md",)):
            page = self._page(*parts)
            self.assertIn(MC.STATUS_CONFINEMENT, page, parts)
            for key in MC.MACOS_KEYS:
                self.assertIn('"%s"' % key, page, (parts, key))
            self.assertIn('"macos": {', page, parts)

    def test_the_design_page_shows_the_launcher_as_it_is_started(self):
        page = self._page("docs", "steady", "design",
                          "macos-confinement-design.md")
        argv = MC.build_sandbox_argv(["/bin/echo"], cwd="/work/j")[0]
        self.assertEqual(
            argv[:2] + argv[3:6] + argv[7:8],
            ["/usr/bin/sandbox-exec", "-p", "/bin/sh", "-p", "-c",
             "hp-shim"])
        self.assertIn("/usr/bin/sandbox-exec -p <profile> /bin/sh -p "
                      "-c <text> hp-shim <KiB> <the job's command>",
                      page)

    def test_the_operator_s_page_prints_the_installer_s_own_lines(self):
        # The sample on the page is what the installer prints on
        # the hosted Apple silicon Mac, built here from the same
        # functions with that Mac's floor.
        floor = DataLimitPlanTest.APPLE_SILICON
        lines = MC.posture_lines(
            {}, probe=lambda cfg: None,
            facts={"limit_kib": floor + 512 * 1024}, root=False)
        answer = INS.SeedAnswer(None, [text for _level, text in lines],
                                INS.MACOS_PROBE_ASKED)
        page = self._page("docs", "steady", "security", "macos.md")
        printed = INS.seed_kept_lines(answer, "<config>")
        self.assertEqual(len(printed), 4)
        for line in printed:
            self.assertIn("  " + line + "\n", page)

    def test_the_default_ceiling_on_the_pages_is_the_code_s(self):
        self.assertEqual(MC.DEFAULT_PROCESS_MEMORY_BYTES, 536870912)
        for parts in (("docs", "steady", "design",
                       "macos-confinement-design.md"),
                      ("SECURITY.md",)):
            self.assertIn('"process_memory_bytes": 536870912',
                          self._page(*parts), parts)

    def test_the_hosted_runs_are_the_ones_on_the_record(self):
        page = self._page("docs", "steady", "design",
                          "macos-confinement-design.md")
        for run in ("43683198505", "43687676740", "43688324966"):
            self.assertIn(run, page)
        # Thirteen suppositions, and a conclusion against each.
        tail = page.split("## Suppositions and conclusions", 1)[1]
        supposed, concluded = tail.split("### Conclusions", 1)
        for n in range(1, 14):
            self.assertIn("\n%d. " % n, supposed, n)
            self.assertIn("\n%d. " % n, concluded, n)

    def test_the_services_rule_on_the_pages_is_the_profile_s(self):
        design = self._page("docs", "steady", "design",
                            "macos-confinement-design.md")
        rules = [ln for ln in MC.build_profile("/work/job1").splitlines()
                 if "mach" in ln]
        self.assertEqual(len(rules), 1)
        self.assertIn("\n```\n%s\n```\n" % rules[0], design)
        # The run that measured what the list costs, and what
        # it read: the numbers on the page are that run's.
        self.assertIn("43761537586", design)
        self.assertIn("| None | 28 of 36 |", design)
        self.assertEqual(design.count("| 36 of 36 |"), 5)
        # The setting's example opens the one service the
        # probe's trial asks by name, on both pages.
        example = '"mach_services": ["%s"]' % MC.PASTEBOARD_SERVICE
        operator = self._page("docs", "steady", "security", "macos.md")
        for page in (design, operator):
            self.assertIn(example, page)
        self.assertIn("At most %d are named" % MC.MAX_MACH_SERVICES,
                      design)
        self.assertIn("Up to %d can be named" % MC.MAX_MACH_SERVICES,
                      operator)

    def test_the_services_suppositions_stand_before_the_run(self):
        page = self._page("docs", "steady", "design",
                          "macos-confinement-design.md")
        supposed = page.split(
            "### The session's services: suppositions", 1)[1]
        for n in range(14, 25):
            self.assertIn("\n%d. " % n, supposed, n)
        self.assertNotIn("\n25. ", supposed)


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
        # S1). The job reads three numbers back. Its data-size
        # limit is one number, soft and hard, so it is not the
        # job's to raise; it stands the requested ceiling above
        # a floor that is itself above the ceiling -- the size
        # a bare process's address map already has on this
        # host -- and it is the limit the probe's own trial
        # read here, to within what one shell's map differs
        # from another's. The address space reads back exactly
        # as this process inherits it, in the platform's own
        # report of unlimited (supposition R6-S1).
        import resource
        inherited_as = resource.getrlimit(resource.RLIMIT_AS)[0]
        self.assertIsNone(MC.macos_confinement_problem())
        trial_kib = MC.trial_facts()["limit_kib"]
        request = MC.ceiling_kib(MC.DEFAULT_PROCESS_MEMORY_BYTES) * 1024
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                [sys.executable, "-c",
                 "import resource\n"
                 "print(resource.getrlimit(resource.RLIMIT_DATA)[0])\n"
                 "print(resource.getrlimit(resource.RLIMIT_DATA)[1])\n"
                 "print(resource.getrlimit(resource.RLIMIT_AS)[0])\n"],
                cwd=work, env=dict(os.environ))
            out, err = proc.communicate(timeout=30)
            proc.close()
            limits = [int(x) for x in out.decode().split()]
            self.assertEqual(len(limits), 3, err)
            self.assertEqual(limits[0], limits[1])
            self.assertFalse(MC.reported_limit_is_unlimited(limits[0]))
            floor = limits[0] - request
            self.assertGreater(floor, request)
            self.assertLess(abs(limits[0] // 1024 - trial_kib),
                            64 * 1024)
            self.assertEqual(limits[2], inherited_as)
            self.assertEqual(limits[2], resource.RLIM_INFINITY)
            self.assertTrue(
                MC.reported_limit_is_unlimited(limits[2]))
            self.assertEqual(
                proc.confinement_notes,
                ["memory ceiling 512 MiB above a bare process's "
                 "address map, soft and hard"])
            print("limits: a job's data-size limit here is %d KiB, "
                  "soft and hard: 512 MiB above a floor of %s"
                  % (limits[0] // 1024,
                     MC.human_size(floor // 1024)), flush=True)

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
        # shell sets the data-size ceiling on itself and
        # execs the job interpreter under it. One leg of
        # the bisect (supposition R2-S3): if this aborts
        # while the profile-only leg passes, the ceiling
        # itself -- in force across the exec, while the
        # loader binds the interpreter -- is the abort's
        # cause, and the profile is cleared.
        with tempfile.TemporaryDirectory() as work:
            done = subprocess.run(
                MC.build_shim_argv(
                    [sys.executable, "-c", "print('SHIM-ONLY-OK')"]),
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
        # A shim whose limit is refused on this host fails
        # here carrying its named line ("hp-shim: could not
        # set the data-size limit"); a limit that breaks the
        # interpreter's startup passes here while the
        # shim-alone interpreter leg fails without that line.
        with tempfile.TemporaryDirectory() as work:
            done = subprocess.run(
                MC.build_shim_argv(["/usr/bin/true"]),
                cwd=work, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(
                done.returncode, 0,
                done.stderr.decode("utf-8", "replace"))

    # --- the ceiling -------------------------------------------

    _GROW = ("import sys\n"
             "n = int(sys.argv[1]) << 20\n"
             "a = bytearray(n)\n"
             "a[::4096] = b'1' * len(a[::4096])\n"
             "print('MEM-DONE')\n")
    _PY_LIMIT = ("import resource\n"
                 "print(*resource.getrlimit(resource.RLIMIT_DATA))\n")

    def _job(self, argv, work, **kw):
        """One job under the full controls: (exit code, stdout,
        stderr), as text."""
        env = kw.pop("env", None)
        proc = MC.spawn_confined_process(
            argv, cwd=work,
            env=dict(os.environ) if env is None else env, **kw)
        out, err = proc.communicate(timeout=60)
        rc = proc.returncode
        proc.close()
        return (rc, out.decode("utf-8", "replace"),
                err.decode("utf-8", "replace"))

    def _grows(self, work, mib, **kw):
        """Whether a job that makes and touches one buffer of
        `mib` mebibytes finishes; its exit code and stderr."""
        rc, out, err = self._job(
            [sys.executable, "-c", self._GROW, str(mib)], work, **kw)
        return ("MEM-DONE" in out and rc == 0), rc, err

    def test_the_memory_ceiling_is_a_real_ceiling(self):
        # Each size is a job of its own, so no size inherits
        # what an earlier one left mapped. A small buffer fits;
        # one a half over the ceiling does not, and what
        # refuses it is the limit -- a MemoryError in the job,
        # never the host's memory pressure. Where the largest
        # buffer that fits stands below 512 MiB, the difference
        # is what the job's own interpreter maps at its start:
        # the ceiling is on the address map, not on the data.
        fit = refused = None
        with tempfile.TemporaryDirectory() as work:
            for mib in (16, 64, 128, 256, 384, 448, 512, 768):
                done, rc, err = self._grows(work, mib)
                if done:
                    fit = mib
                    continue
                refused = mib
                self.assertIn("MemoryError", err,
                              "rc=%r err=%r" % (rc, err[-300:]))
                break
        self.assertIsNotNone(fit, "a 16 MiB buffer did not fit")
        self.assertIsNotNone(
            refused, "a 768 MiB buffer fit under a 512 MiB ceiling")
        print("memory: under the 512 MiB ceiling the largest buffer "
              "a Python job made and touched was %d MiB; %d MiB was "
              "refused" % (fit, refused), flush=True)

    def test_a_job_that_is_root_can_raise_its_ceiling(self):
        # What the page says of a runner that is root and names
        # no job user, read here: the hard limit goes up for the
        # asking, in a subshell of the job's own.
        if os.geteuid() != 0:
            self.skipTest("a job is root only under a runner that "
                          "is: run in the macos-confinement "
                          "workflow's root step")
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._job(
                ["/bin/sh", "-c",
                 "(ulimit -H -d unlimited && ulimit -S -d unlimited "
                 "&& " + _READ_BACK + ") 2>&1; echo END"], work)
            self.assertIn("unlimited unlimited", out, err)

    def test_the_job_cannot_raise_its_ceiling(self):
        if os.geteuid() == 0:
            self.skipTest("root may raise a hard limit: run as an "
                          "ordinary user")
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._job(
                ["/bin/sh", "-c",
                 _READ_BACK + "; (ulimit -H -d unlimited) 2>/dev/null "
                 "&& echo RAISED-HARD; ulimit -S -d unlimited "
                 "2>/dev/null; " + _READ_BACK], work)
            self.assertEqual(rc, 0, err)
            lines = out.split("\n")
            self.assertNotIn("RAISED-HARD", lines)
            self.assertEqual(lines[0], lines[1])
            self.assertNotIn("unlimited", lines[1])
            # And through the call itself, not a shell's builtin.
            rc, out, err = self._job(
                [sys.executable, "-c",
                 "import resource\n"
                 "before = resource.getrlimit(resource.RLIMIT_DATA)\n"
                 "for pair in ((resource.RLIM_INFINITY,) * 2,\n"
                 "             (before[0] * 2, before[1] * 2),\n"
                 "             (before[0] + 4096, before[1])):\n"
                 "    try:\n"
                 "        resource.setrlimit(resource.RLIMIT_DATA, pair)\n"
                 "        print('RAISED', pair)\n"
                 "    except (ValueError, OSError):\n"
                 "        print('REFUSED')\n"
                 "print(before == resource.getrlimit("
                 "resource.RLIMIT_DATA))\n"], work)
            self.assertEqual(out.split(), ["REFUSED"] * 3 + ["True"],
                             err)

    def test_an_operator_s_ceiling_is_the_one_a_job_carries(self):
        two_gib = 2 * 1024 ** 3
        cfg = {"security": {"confinement": {"macos": {
            "process_memory_bytes": two_gib}}}}
        with tempfile.TemporaryDirectory() as work:
            _rc, small, _err = self._job(
                [sys.executable, "-c", self._PY_LIMIT], work)
            _rc, large, err = self._job(
                [sys.executable, "-c", self._PY_LIMIT], work, cfg=cfg)
            small, large = int(small.split()[0]), int(large.split()[0])
            self.assertLess(
                abs((large - small)
                    - (two_gib - MC.DEFAULT_PROCESS_MEMORY_BYTES)),
                64 * 1024 * 1024, err)
            # A buffer the default refuses fits under it.
            self.assertFalse(self._grows(work, 768)[0])
            done, rc, err = self._grows(work, 768, cfg=cfg)
            self.assertTrue(done, "rc=%r err=%r" % (rc, err[-300:]))

    def test_a_function_in_the_job_s_environment_does_not_lift_it(self):
        # The submitter's environment reaches the shim's shell,
        # which on a Mac is bash. Neither shape of exported
        # function replaces the shim's ulimit, and an option
        # list there does not stop the shim running.
        env = dict(os.environ)
        env["BASH_FUNC_ulimit%%"] = "() { return 0; }"
        env["__BASH_FUNC<ulimit>()"] = "() { return 0; }"
        env["SHELLOPTS"] = "noexec"
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._job(
                [sys.executable, "-c", self._PY_LIMIT], work, env=env)
            self.assertEqual(rc, 0, err)
            soft, hard = (int(x) for x in out.split())
            self.assertEqual(soft, hard)
            self.assertFalse(MC.reported_limit_is_unlimited(soft))

    def test_the_job_s_environment_arrives(self):
        env = dict(os.environ)
        env.update({"HP_T_PLAIN": "a b  c", "HP_T_EMPTY": "",
                    "HP_T_QUOTE": "it's \"x\" $HOME"})
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._job(
                [sys.executable, "-c",
                 "import os\n"
                 "print(repr([os.environ.get(k) for k in "
                 "('HP_T_PLAIN', 'HP_T_EMPTY', 'HP_T_QUOTE')]))\n"
                 "print(os.environ['TMPDIR'] == os.path.join("
                 "os.getcwd(), '.hp-tmp'))\n"], work, env=env)
            self.assertEqual(rc, 0, err)
            self.assertEqual(
                out.split("\n")[0],
                repr(["a b  c", "", "it's \"x\" $HOME"]))

    # --- what the profile refuses besides files ----------------

    def test_a_set_user_id_program_does_not_run(self):
        # /bin/ps is root's by its set-user-ID bit; under the
        # profile the kernel refuses to start it at all.
        self.assertTrue(os.stat("/bin/ps").st_mode & stat.S_ISUID,
                        "/bin/ps carries no set-user-ID bit here")
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._job(
                ["/bin/sh", "-c",
                 "/bin/ps -o pid= -p 1 && echo PS-RAN; echo END"],
                work)
            self.assertIn("END", out)
            self.assertNotIn("PS-RAN", out)
            self.assertIn("Operation not permitted", err)

    def test_a_signal_to_a_process_outside_is_refused(self):
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._job(
                ["/bin/sh", "-c",
                 "kill -0 %d 2>/dev/null && echo REACHED; echo END"
                 % os.getpid()], work)
            self.assertIn("END", out)
            self.assertNotIn("REACHED", out)

    def test_a_job_handed_to_launchd_is_not_run(self):
        # launchd would run the command outside the profile.
        label = "hp.test.%s" % os.urandom(6).hex()
        marker = os.path.join(tempfile.gettempdir(),
                              "hp-launchd-%s.txt" % label)
        try:
            with tempfile.TemporaryDirectory() as work:
                rc, out, err = self._job(
                    ["/bin/sh", "-c",
                     "/bin/launchctl submit -l %s -- /usr/bin/touch "
                     "%s; echo SUBMIT-EXIT $?" % (label, marker)],
                    work)
            self.assertNotIn("SUBMIT-EXIT 0", out, err)
            time.sleep(3)
            self.assertFalse(os.path.exists(marker))
        finally:
            subprocess.run(["/bin/launchctl", "remove", label],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            if os.path.exists(marker):
                os.unlink(marker)

    # --- the probe's own trial ---------------------------------

    def test_the_trial_reads_the_boundary_here(self):
        facts = {}
        self.assertIsNone(MC.confinement_trial_problem(
            MC.spawn_confined_process, facts=facts))
        self.assertGreater(
            facts["limit_kib"],
            MC.ceiling_kib(MC.DEFAULT_PROCESS_MEMORY_BYTES))

    def test_a_spawn_that_confines_nothing_does_not_pass_here(self):
        def _open_spawn(argv, cwd=None, env=None):
            inner = subprocess.Popen(
                argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            inner.close = lambda: None
            return inner
        self.assertIn("wrote a file outside its work directory",
                      MC.confinement_trial_problem(_open_spawn))

    def test_a_missing_shell_or_tool_refuses_before_anything_runs(self):
        for name in ("SANDBOX_EXEC_BIN", "SHELL_BIN"):
            with mock.patch.object(MC, name, "/hp/no/such/tool"):
                self.assertEqual(
                    MC.macos_confinement_problem(),
                    "/hp/no/such/tool is missing or not executable")
                with self.assertRaises(RuntimeError), \
                        tempfile.TemporaryDirectory() as work:
                    MC.spawn_confined_process(["/usr/bin/true"],
                                              cwd=work)

    def test_a_malformed_block_refuses_at_the_gate_and_the_spawn(self):
        cfg = {"security": {"confinement": {"macos": {"cores": 2}}}}
        self.assertIn("not a known setting",
                      MC.macos_confinement_problem(cfg))
        with self.assertRaises(RuntimeError), \
                tempfile.TemporaryDirectory() as work:
            MC.spawn_confined_process(["/usr/bin/true"], cwd=work,
                                      cfg=cfg)

    def test_the_posture_report_names_this_host_s_floor(self):
        results = []
        POST._check_confinement_backend(results, {})
        self.assertEqual(
            results[0],
            ("OK", "confinement",
             "macOS backend: " + MC.STATUS_CONFINEMENT))
        self.assertRegex(
            results[1][2],
            r"^a job process's address map may grow 512 MiB past "
            r"the \d+\.\d GiB a bare process starts at here; ")
        self.assertEqual(
            results[2],
            ("OK", "confinement",
             "a job may ask the user database who a user is, and "
             "no other of the session's services: the clipboard "
             "is refused"))
        if os.geteuid() == 0:
            # No job user is named here, so the jobs are root's.
            self.assertIn("a job that is root can raise it",
                          results[1][2])
            self.assertEqual(results[3][0], "WARN")
            self.assertEqual(len(results), 4)
        else:
            self.assertIn("the ceiling is not the job's to raise",
                          results[1][2])
            self.assertEqual(len(results), 3)
        print("posture: " + results[1][2], flush=True)
        print("posture: " + results[2][2], flush=True)


@unittest.skipUnless(MC.IS_MACOS_BACKEND, "run on macOS")
class LiveServicesTest(unittest.TestCase):
    """The session's services, asked from inside a job on a
    real Mac (the CI legs)."""

    NAMES_THE_PASTEBOARD = {"security": {"confinement": {"macos": {
        "mach_services": [MC.PASTEBOARD_SERVICE]}}}}
    # launchd's answer to a caller its sandbox does not let
    # ask: BOOTSTRAP_NOT_PRIVILEGED. A name that is merely
    # not there is another number, so this one is the
    # profile's and needs no control beside it.
    NOT_PRIVILEGED = 1100
    EVERY_SERVICE = "(allow mach*)\n"
    NO_SERVICE = ""

    _LOOKUP = (
        "import ctypes, sys\n"
        "libc = ctypes.CDLL(None)\n"
        "bp = ctypes.c_uint.in_dll(libc, 'bootstrap_port')\n"
        "port = ctypes.c_uint(0)\n"
        "kr = libc.bootstrap_look_up(bp, sys.argv[1].encode(), "
        "ctypes.byref(port))\n"
        "print('ANSWER kr=%d' % kr)\n")
    _REGISTER = (
        "import ctypes, sys\n"
        "libc = ctypes.CDLL(None)\n"
        "bp = ctypes.c_uint.in_dll(libc, 'bootstrap_port')\n"
        "libc.mach_reply_port.restype = ctypes.c_uint\n"
        "port = libc.mach_reply_port()\n"
        "kr = libc.bootstrap_register(bp, sys.argv[1].encode(), "
        "ctypes.c_uint(port))\n"
        "print('ANSWER kr=%d' % kr)\n")

    @staticmethod
    def _kr(text):
        for line in text.splitlines():
            if line.startswith("ANSWER kr="):
                return int(line[len("ANSWER kr="):])
        return None

    def _job(self, argv, cfg=None, timeout=120):
        """(exit code, stdout, stderr) of one job under the
        backend's own spawn, in a work directory of its own."""
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                argv, cwd=work, env=dict(os.environ), cfg=cfg)
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            rc = proc.returncode
            proc.close()
        return (rc, out.decode("utf-8", "replace"),
                err.decode("utf-8", "replace"))

    def _under(self, argv, work, mach_rule=None, memory=8 << 30,
               timeout=120):
        """(exit code, stdout, stderr) of argv under the
        backend's own profile and launcher -- or, with
        `mach_rule`, under the same profile with its one Mach
        rule replaced by that text: every service, or none."""
        sandbox_argv, profile = MC.build_sandbox_argv(
            argv, cwd=work, memory_bytes=memory)
        if mach_rule is not None:
            rules = [ln for ln in profile.splitlines()
                     if ln.startswith("(allow mach")]
            self.assertEqual(len(rules), 1, rules)
            self.assertEqual(profile.count(rules[0] + "\n"), 1)
            sandbox_argv[sandbox_argv.index(profile)] = \
                profile.replace(rules[0] + "\n", mach_rule)
        env = dict(os.environ)
        tmp = os.path.join(work, MC.JOB_TMP_NAME)
        os.makedirs(tmp, exist_ok=True)
        env["TMPDIR"] = tmp
        try:
            done = subprocess.run(
                sandbox_argv, cwd=work, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            return "timeout", "", ""
        return (done.returncode,
                done.stdout.decode("utf-8", "replace"),
                done.stderr.decode("utf-8", "replace"))

    @staticmethod
    def _clipboard():
        """(exit code, text) of the system's reader, asked
        outside any job."""
        try:
            done = subprocess.run(
                [MC.PASTEBOARD_READER], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None, ""
        return done.returncode, done.stdout.decode("utf-8", "replace")

    @staticmethod
    def _set_clipboard(text):
        try:
            subprocess.run(["/usr/bin/pbcopy"], input=text.encode(),
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass

    def _a_pasteboard_answers(self):
        """The control the clipboard tests stand on: outside a
        job, the system's reader is answered. Nothing is read
        into this test and nothing is written."""
        if self._clipboard()[0] != 0:
            self.skipTest("no pasteboard answers this session: the "
                          "control needs one")

    def _a_mark_on_the_clipboard(self):
        """Put a mark of this test's own on the session's
        clipboard, read it back as the control, and put the
        text that was there back when the test ends."""
        if os.environ.get("HP_LIVE_CLIPBOARD") != "1":
            self.skipTest("writes this session's clipboard: run in "
                          "the macos-confinement workflow")
        self._a_pasteboard_answers()
        self.addCleanup(self._set_clipboard, self._clipboard()[1])
        mark = "HP-CLIPBOARD-MARK-%s" % os.urandom(6).hex()
        self._set_clipboard(mark)
        if self._clipboard() != (0, mark):
            self.skipTest("no pasteboard answers this session: the "
                          "control needs one")
        return mark

    def _trial_with_every_service(self):
        """The probe's trial through a spawn whose profile
        opens every service, as the profile did before it
        named any: the trial's verdict."""
        def _spawn(argv, cwd=None, env=None):
            sandbox_argv, profile = MC.build_sandbox_argv(argv, cwd=cwd)
            rules = [ln for ln in profile.splitlines()
                     if ln.startswith("(allow mach")]
            self.assertEqual(len(rules), 1, rules)
            sandbox_argv[sandbox_argv.index(profile)] = \
                profile.replace(rules[0] + "\n", self.EVERY_SERVICE)
            env2 = dict(env or os.environ)
            tmp = os.path.join(cwd, MC.JOB_TMP_NAME)
            os.makedirs(tmp, exist_ok=True)
            env2["TMPDIR"] = tmp
            inner = subprocess.Popen(
                sandbox_argv, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd, env=env2)
            inner.close = lambda: None
            return inner
        return MC.confinement_trial_problem(_spawn)

    def _looked_up_outside(self, name):
        """launchd's answer to a lookup of `name` by a process
        of this session that is in no job: the control beside
        the same lookup from inside one."""
        done = subprocess.run(
            [sys.executable, "-c", self._LOOKUP, name],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=60)
        return self._kr(done.stdout.decode("utf-8", "replace"))

    def _refused(self, name, cfg=None):
        """A lookup of `name` from inside a job is not
        answered; where the same lookup is answered outside a
        job, the answer inside is the one launchd gives a
        caller whose sandbox does not let it ask."""
        outside = self._looked_up_outside(name)
        rc, out, err = self._job(
            [sys.executable, "-c", self._LOOKUP, name], cfg=cfg)
        self.assertEqual(rc, 0, err)
        inside = self._kr(out)
        print("services: a lookup of %s: %s outside a job, %s "
              "inside" % (name, outside, inside), flush=True)
        self.assertNotIn(inside, (0, None), name + ": " + out + err)
        if outside == 0:
            self.assertEqual(inside, self.NOT_PRIVILEGED, name)
        return outside

    # -- what is refused ---------------------------------------

    def test_the_pasteboard_is_not_a_job_s_to_look_up(self):
        self._refused(MC.PASTEBOARD_SERVICE)

    def test_no_other_service_of_the_session_is_either(self):
        # Names a job's programs asked for on the hosted Macs
        # and the profile does not carry, the older name of
        # the user database and a name no service has among
        # them. At least the ones every session has are there
        # to be refused.
        answered = 0
        for name in ("com.apple.windowserver.active",
                     "com.apple.coreservices.launchservicesd",
                     "com.apple.SystemConfiguration.configd",
                     "com.apple.SecurityServer",
                     "com.apple.cfprefsd.daemon",
                     "com.apple.system.notification_center",
                     "com.apple.logd",
                     "com.apple.system.DirectoryService.libinfo_v1",
                     "hp.no.such.service"):
            answered += self._refused(name) == 0
        self.assertGreater(answered, 0)

    def test_a_job_registers_no_name_in_the_session(self):
        # The rule that stood here took a name a job
        # registered (the answer was 0 on both hosted Macs): a
        # job could stand where a service is looked for.
        rc, out, err = self._job(
            [sys.executable, "-c", self._REGISTER, "hp.live.squat"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(self._kr(out), self.NOT_PRIVILEGED, out + err)
        rc, out, err = self._job(
            [sys.executable, "-c", self._REGISTER,
             MC.SESSION_SERVICES[0]])
        self.assertEqual(rc, 0, err)
        self.assertNotIn(self._kr(out), (0, None), out + err)

    def test_the_system_s_reader_is_refused_inside_a_job(self):
        self._a_pasteboard_answers()
        rc, out, err = self._job([MC.PASTEBOARD_READER])
        self.assertNotEqual(rc, 0)
        print("services: the system's reader inside a job: exit %s"
              % rc, flush=True)

    def test_a_mark_on_the_clipboard_is_not_read_by_a_job(self):
        mark = self._a_mark_on_the_clipboard()
        rc, out, err = self._job([MC.PASTEBOARD_READER])
        self.assertNotIn(mark, out + err)
        self.assertNotEqual(rc, 0)
        rc, out, err = self._job(
            ["/usr/bin/osascript", "-e", "the clipboard"])
        self.assertNotIn(mark, out + err)
        # The rule on the services is what refuses it: under
        # the same profile with every service open, as the
        # profile stood, the same reader returns the mark.
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._under(
                [MC.PASTEBOARD_READER], work, self.EVERY_SERVICE)
        self.assertEqual((rc, out), (0, mark), err)
        # And it is still there for the session it belongs to.
        self.assertEqual(self._clipboard(), (0, mark))

    def test_a_job_does_not_write_the_clipboard(self):
        mark = self._a_mark_on_the_clipboard()
        rc, out, err = self._job(
            ["/bin/sh", "-c",
             "printf %s HP-WRITTEN-BY-A-JOB | /usr/bin/pbcopy"])
        self.assertEqual(self._clipboard(), (0, mark), (rc, out, err))

    def test_the_other_things_a_session_answers_are_refused_too(self):
        # Each is asked twice under the same profile and the
        # same ceiling: with every service open, as the
        # profile stood, and as the profile is built. One that
        # is answered the first way is the control for its own
        # row, and the rule on the services is the whole
        # difference between the two.
        rows = (
            ("the network configuration",
             ["/usr/sbin/scutil", "--dns"], "resolver"),
            ("the list of keychains",
             ["/usr/bin/security", "list-keychains"], "keychain"),
            ("the list of disks",
             ["/usr/sbin/diskutil", "list"], "/dev/disk"))
        held = 0
        for what, argv, word in rows:
            with tempfile.TemporaryDirectory() as work:
                opened = self._under(argv, work, self.EVERY_SERVICE)
                named = self._under(argv, work)
            if word not in opened[1]:
                print("services: %s is not answered with every "
                      "service open here (exit %s)"
                      % (what, opened[0]), flush=True)
                continue
            held += 1
            self.assertNotIn(word, named[1], what)
            print("services: %s: answered with every service open, "
                  "exit %s under the profile" % (what, named[0]),
                  flush=True)
        self.assertGreater(held, 0)

    # -- what still works --------------------------------------

    def test_the_user_database_answers_a_job(self):
        import grp
        import pwd
        entry = pwd.getpwuid(os.geteuid())
        rc, out, err = self._job(["/usr/bin/id", "-un"])
        self.assertEqual((rc, out.strip()), (0, entry.pw_name), err)
        rc, out, err = self._job(
            [sys.executable, "-c",
             "import grp, os, pwd\n"
             "e = pwd.getpwuid(os.getuid())\n"
             "print(e.pw_name)\n"
             "print(grp.getgrgid(e.pw_gid).gr_name)\n"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.split(), [
            entry.pw_name, grp.getgrgid(entry.pw_gid).gr_name])
        # The groups a user is in, by name: a reading, printed
        # beside the same question asked outside a job.
        outside = subprocess.run(
            ["/usr/bin/id", "-Gn"], stdout=subprocess.PIPE,
            timeout=60).stdout.decode().split()
        rc, out, err = self._job(["/usr/bin/id", "-Gn"])
        print("services: id -Gn names %d groups inside a job and "
              "%d outside: %s (exit %s)"
              % (len(out.split()), len(outside),
                 "the same" if sorted(out.split()) == sorted(outside)
                 else "not the same", rc), flush=True)

    def test_without_the_user_database_a_user_is_a_number(self):
        # Why the profile names it: under the same profile
        # with no service at all, the program that prints a
        # user's name prints the number.
        with tempfile.TemporaryDirectory() as work:
            rc, out, err = self._under(
                ["/usr/bin/id", "-un"], work, self.NO_SERVICE)
            named = self._under(["/usr/bin/id", "-un"], work)
        print("services: with no service named, id -un as uid %d "
              "prints %r (exit %s)" % (os.geteuid(), out.strip(), rc),
              flush=True)
        import pwd
        self.assertEqual(
            (named[0], named[1].strip()),
            (0, pwd.getpwuid(os.geteuid()).pw_name), named[2])
        if os.geteuid() != 0:
            self.assertEqual(out.strip(), str(os.geteuid()), err)

    def _battery(self):
        """(name, argv, a word its output carries when it
        works): the programs a job is likely to be, the
        thirty-six the measuring run read (43761537586)."""
        import pwd
        me = pwd.getpwuid(os.geteuid()).pw_name
        py = sys.executable

        def sh(script):
            return ["/bin/sh", "-c", script]
        return [
            ("sh-tools", sh(
                "ls -l . >/dev/null && date >/dev/null && "
                "mktemp ./x.XXXXXX >/dev/null && "
                "echo a | sed s/a/b/ | grep -q b && "
                "awk 'BEGIN{print 1}' >/dev/null && echo SH-OK"),
             "SH-OK"),
            ("id-un", ["id", "-un"], me),
            ("whoami", ["whoami"], me),
            ("ls-owner", sh("ls -ld . | awk '{print $3}'"), me),
            ("python-pwd", [py, "-c",
                            "import os, pwd; "
                            "print(pwd.getpwuid(os.getuid()).pw_name)"],
             me),
            ("python-std", [py, "-c",
                            "import time, locale, tempfile, json, "
                            "hashlib, subprocess, socket; "
                            "time.localtime(); tempfile.mkstemp(); "
                            "socket.gethostname(); "
                            "print(subprocess.run(['/bin/echo', "
                            "'PY-OK'], capture_output=True, "
                            "text=True).stdout)"], "PY-OK"),
            ("python-tz", [py, "-c",
                           "import time; print('TZ', time.tzname[0])"],
             "TZ"),
            ("python-ssl", [py, "-c",
                            "import ssl; ssl.create_default_context(); "
                            "print('SSL-OK')"], "SSL-OK"),
            ("pip", [py, "-m", "pip", "--version"], "pip"),
            ("perl", ["perl", "-e",
                      "print scalar(getpwuid($<)), qq(\\n)"], me),
            ("ruby", ["ruby", "-e",
                      "require 'etc'; puts Etc.getpwuid.name"], me),
            ("node", ["node", "-e",
                      "const os = require('os'); "
                      "require('fs').writeFileSync('n.txt', 'x'); "
                      "console.log(os.userInfo().username)"], me),
            ("java", ["java", "-version"], ""),
            ("git-named", sh("rm -rf r1 && git init -q r1 && cd r1 && "
                             "git -c user.name=a -c user.email=a@b.c "
                             "commit -q --allow-empty -m x && "
                             "git log --oneline | wc -l"), "1"),
            ("git-auto", sh("rm -rf r2 && git init -q r2 && cd r2 && "
                            "git commit -q --allow-empty -m x && "
                            "git log --format=%an | head -n 1"), ""),
            ("cc", sh("printf 'int main(void){return 0;}\\n' > h.c "
                      "&& cc h.c -o h && ./h && echo CC-OK"), "CC-OK"),
            ("make", sh("printf 'all:\\n\\t@echo MAKE-OK\\n' "
                        "> Makefile && make"), "MAKE-OK"),
            ("xcrun", ["xcrun", "--find", "cc"], "cc"),
            ("sw_vers", ["sw_vers", "-productVersion"], "."),
            ("defaults", ["defaults", "read",
                          "/System/Library/CoreServices/SystemVersion",
                          "ProductVersion"], "."),
            ("plutil", ["plutil", "-lint",
                        "/System/Library/CoreServices/"
                        "SystemVersion.plist"], "OK"),
            ("curl", ["curl", "--version"], "curl"),
            ("openssl", ["openssl", "version"], "SSL"),
            ("sqlite3", ["sqlite3", ":memory:", "select 41+1"], "42"),
            ("zip", sh("echo x > z.txt && zip -q z.zip z.txt && "
                       "unzip -l z.zip >/dev/null && echo ZIP-OK"),
             "ZIP-OK"),
            ("tar", sh("echo x > t.txt && tar czf t.tgz t.txt && "
                       "tar tzf t.tgz"), "t.txt"),
            ("file", ["file", "/bin/ls"], "Mach-O"),
            ("locale", ["locale"], "LC_"),
            ("uname", ["uname", "-a"], "Darwin"),
            ("hostname", ["hostname"], ""),
            ("sysctl", ["sysctl", "-n", "hw.ncpu"], ""),
            ("df", ["df", "-k", "."], "Filesystem"),
            ("getconf", ["getconf", "DARWIN_USER_TEMP_DIR"], "/"),
            ("codesign", sh("codesign -dv /bin/ls 2>&1 | head -n 1"),
             "Executable"),
            ("osascript", ["osascript", "-e", "return 1 + 1"], "2"),
            ("date", ["date", "+%Z"], ""),
        ]

    def test_a_job_s_programs_behave_as_with_every_service(self):
        # The cost of the list, read: each program of the
        # battery under the profile as the backend writes it,
        # and under the same profile with every service open.
        # A program this host lacks, or one the profile stops
        # for a reason that is not a service (a runtime kept
        # under a tree the profile does not read), is the same
        # in both and stays in the count.
        def works(argv, word, rule):
            with tempfile.TemporaryDirectory() as work:
                rc, out, err = self._under(argv, work, rule)
            return rc == 0 and (word in out or word in err)

        named, opened = {}, {}
        for name, argv, word in self._battery():
            if not os.path.isabs(argv[0]) \
                    and shutil.which(argv[0]) is None:
                continue
            # A difference is one that is there each time it
            # is looked for: a program that stumbled once under
            # one profile is run again under both.
            for _attempt in range(3):
                named[name] = works(argv, word, None)
                opened[name] = works(argv, word, self.EVERY_SERVICE)
                if named[name] == opened[name]:
                    break
        differ = sorted(n for n in named if named[n] != opened[n])
        print("services: %d of %d programs behave as with every "
              "service open; %d of them work (not: %s)"
              % (len(named) - len(differ), len(named),
                 sum(named.values()),
                 " ".join(sorted(n for n in named if not named[n]))
                 or "none"), flush=True)
        self.assertEqual(differ, [])
        for name in ("sh-tools", "id-un", "whoami", "ls-owner",
                     "python-pwd", "python-std", "python-ssl",
                     "sw_vers", "defaults", "uname"):
            self.assertTrue(named.get(name), name)
        self.assertEqual(len(self._battery()), 36)
        self.assertGreater(len(named), 25)

    # -- the probe ---------------------------------------------

    def test_the_probe_s_trial_was_refused_the_clipboard(self):
        self.assertIsNone(MC.macos_confinement_problem())
        self.assertIs(MC.trial_facts()["clipboard_open"], False)

    def test_the_trial_convicts_a_profile_that_opens_every_service(self):
        # The profile as it stood before it named a service,
        # put to the trial as it now is: the pasteboard
        # answers, and that is the trial's verdict. A trial
        # that passed here would pass a profile that refused
        # the clipboard nothing.
        self._a_pasteboard_answers()
        self.assertEqual(
            self._trial_with_every_service(),
            "a confined process was answered by the pasteboard, a "
            "service the profile does not name: the profile did "
            "not hold")

    def test_the_trial_s_question_is_not_what_the_clipboard_holds(self):
        # An empty clipboard answers too: the reader ends 0
        # with nothing to print, and the trial still convicts
        # a profile that lets it ask.
        self._a_mark_on_the_clipboard()
        self._set_clipboard("")
        self.assertEqual(self._clipboard(), (0, ""))
        self.assertIn("answered by the pasteboard",
                      self._trial_with_every_service() or "")
        self.assertNotEqual(self._job([MC.PASTEBOARD_READER])[0], 0)

    # -- the operator's setting --------------------------------

    def test_a_config_that_names_the_pasteboard_is_answered_by_it(self):
        if self._looked_up_outside(MC.PASTEBOARD_SERVICE) != 0:
            self.skipTest("no pasteboard answers this session: the "
                          "control needs one")
        cfg = self.NAMES_THE_PASTEBOARD
        rc, out, err = self._job(
            [sys.executable, "-c", self._LOOKUP, MC.PASTEBOARD_SERVICE],
            cfg=cfg)
        self.assertEqual(rc, 0, err)
        self.assertEqual(self._kr(out), 0, out + err)
        # The one name and no other: the window server is
        # still not this job's to look up.
        self._refused("com.apple.windowserver.active", cfg=cfg)
        # The probe passes such a config, and the report says
        # what the config did.
        self.assertIsNone(MC.macos_confinement_problem(cfg))
        lines = MC.posture_lines(cfg)
        self.assertEqual(
            lines[2],
            ("OK", "a job may ask the user database who a user is, "
                   "and the services this config names: "
                   "com.apple.pasteboard.1 (security.confinement."
                   "macos.mach_services); the pasteboard is among "
                   "them, so the clipboard is not refused"))

    def test_a_job_under_such_a_config_reads_a_mark(self):
        # The pasteboard's one name is all the system's reader
        # asks for: the mark comes back, and the probe's trial
        # under that config records the clipboard as open.
        mark = self._a_mark_on_the_clipboard()
        rc, out, err = self._job([MC.PASTEBOARD_READER],
                                 cfg=self.NAMES_THE_PASTEBOARD)
        self.assertEqual((rc, out), (0, mark), err)
        self.assertIsNone(
            MC.macos_confinement_problem(self.NAMES_THE_PASTEBOARD))
        self.assertIs(
            MC.trial_facts(MC.DEFAULT_PROCESS_MEMORY_BYTES,
                           (MC.PASTEBOARD_SERVICE,))["clipboard_open"],
            True)
        rc, out, err = self._job(
            ["/bin/sh", "-c",
             "printf %s HP-WRITTEN-BY-A-JOB | /usr/bin/pbcopy"],
            cfg=self.NAMES_THE_PASTEBOARD)
        print("services: with the pasteboard named, a job's write "
              "to the clipboard %s (exit %s)"
              % ("landed" if self._clipboard()[1]
                 == "HP-WRITTEN-BY-A-JOB" else "did not land", rc),
              flush=True)

    def test_the_audit_note_names_the_operator_s_services(self):
        cfg = {"security": {"confinement": {"macos": {"mach_services": [
            "com.example.one", MC.SESSION_SERVICES[0],
            "com.example.two", "com.example.one"]}}}}
        with tempfile.TemporaryDirectory() as work:
            proc = MC.spawn_confined_process(
                ["/usr/bin/true"], cwd=work, cfg=cfg)
            proc.communicate(timeout=30)
            proc.close()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            proc.confinement_notes,
            ["memory ceiling 512 MiB above a bare process's address "
             "map, soft and hard",
             "services the config names: com.example.one, "
             "com.example.two"])

    def test_a_service_list_that_is_not_one_refuses_the_spawn(self):
        for bad in (["not a name"], "com.example.one",
                    ['x") (allow default) ("']):
            cfg = {"security": {"confinement": {"macos": {
                "mach_services": bad}}}}
            self.assertIn("security.confinement.macos.mach_services",
                          MC.macos_startup_problem(cfg))
            with self.assertRaises(RuntimeError), \
                    tempfile.TemporaryDirectory() as work:
                MC.spawn_confined_process(["/usr/bin/true"], cwd=work,
                                          cfg=cfg)
            with self.assertRaises(RuntimeError), \
                    tempfile.TemporaryDirectory() as work:
                MC.spawn_confined_process(["/usr/bin/true"], cwd=work,
                                          mach_services=bad)


@unittest.skipUnless(MC.IS_MACOS_BACKEND, "run on macOS")
class LiveSeedTest(unittest.TestCase):
    """The mode a fresh install states on this Mac."""

    CFG = {"security": {"modes": {"confinement": "enforce",
                                  "job_user": "enforce"}}}

    def test_this_mac_s_answer_leaves_confinement_at_enforce(self):
        cfg = json.loads(json.dumps(self.CFG))
        with _machine_asked():
            modes, asked = INS.fresh_platform_modes(cfg)
        self.assertEqual(modes, {})
        self.assertIsNone(asked[0])
        self.assertEqual(asked.asked, INS.MACOS_PROBE_ASKED)
        self.assertEqual(asked[1][0],
                         "macOS backend: " + MC.STATUS_CONFINEMENT)
        self.assertIn("a bare process starts at here", asked[1][1])
        self.assertEqual(asked[1][2], MC.services_line())
        self.assertEqual(
            INS.fresh_job_user(cfg, asked), (None, None))

    def test_a_test_run_asks_nothing_of_this_mac(self):
        # The suite's own state (runner/tests/__init__.py).
        self.assertFalse(INS.seed_asks_the_machine())
        modes, asked = INS.fresh_platform_modes(
            json.loads(json.dumps(self.CFG)))
        self.assertEqual(modes, {"confinement": "audit"})
        self.assertEqual(asked, (INS.SEED_NOT_ASKED, ()))

    def test_the_installer_s_own_file_is_left_at_enforce(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            path = _fresh_config(d)
            with open(path, "rb") as fh:
                before = fh.read()
            with _machine_asked(), redirect_stdout(out):
                applied = INS.apply_platform_modes(path)
            with open(path, "rb") as fh:
                after = fh.read()
        said = out.getvalue()
        self.assertEqual(applied, {})
        self.assertEqual(before, after)
        self.assertIn("security.modes.confinement left at enforce "
                      "in %s (the macOS backend's probe, asked on "
                      "this machine as this user, passed" % path, said)
        self.assertIn("platform: macOS backend: "
                      + MC.STATUS_CONFINEMENT, said)
        self.assertNotIn("stated as audit", said)
        print("seed: " + said.strip().split("\n")[-1], flush=True)

    def test_the_wizard_s_seed_is_the_same_answer(self):
        cfg = json.loads(json.dumps(self.CFG))
        answers = []
        with _machine_asked():
            stated = SU.seed_platform_modes(cfg, asked=answers)
        self.assertEqual(stated, {})
        self.assertEqual(cfg, self.CFG)
        self.assertIsNone(answers[0][0][0])
        self.assertEqual(answers[0][1:], (None, None))

    def test_a_backend_that_cannot_engage_states_audit_with_why(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            path = _fresh_config(d)
            with _machine_asked(), redirect_stdout(out), \
                    mock.patch.object(MC, "SANDBOX_EXEC_BIN",
                                      "/hp/no/such/sandbox-exec"):
                applied = INS.apply_platform_modes(path)
            cfg = _config_in(path)
        self.assertEqual(applied, {"confinement": "audit"})
        self.assertEqual(cfg["security"]["modes"]["confinement"],
                         "audit")
        self.assertIn(
            "stated as audit in %s (the macOS backend's probe, "
            "asked on this machine as this user, did not pass: "
            "/hp/no/such/sandbox-exec is missing or not executable"
            % path, out.getvalue())


@unittest.skipUnless(MC.IS_MACOS_BACKEND, "run on macOS")
class LiveJobUserTest(unittest.TestCase):
    """The job user at the spawn door, on a Mac."""

    USER = "nobody"

    def test_a_job_user_is_applied_to_the_whole_chain(self):
        if os.geteuid() != 0:
            self.skipTest("changing to the job user is root's: run "
                          "in the macos-confinement workflow's "
                          "root step")
        import pwd
        entry = pwd.getpwnam(self.USER)
        # Under /private/tmp, which any user may pass through:
        # root's own temporary directory is closed to the job
        # user, as a runner's state directory is not.
        work = tempfile.mkdtemp(prefix="hp-job-user-",
                                dir="/private/tmp")
        try:
            os.chown(work, entry.pw_uid, entry.pw_gid)
            proc = MC.spawn_confined_process(
                ["/bin/sh", "-c",
                 "id -u; : > made.txt && echo WORK-OK; "
                 ": > \"$TMPDIR/t\" && echo TMP-OK; "
                 "(ulimit -H -d unlimited) 2>/dev/null "
                 "&& echo RAISED-HARD; " + _READ_BACK],
                cwd=work, env=dict(os.environ), user=self.USER)
            out, err = proc.communicate(timeout=60)
            proc.close()
            words = out.decode().split()
            self.assertEqual(words[0], str(entry.pw_uid), err)
            self.assertIn("WORK-OK", words)
            self.assertIn("TMP-OK", words)
            # The runner is root; the job is not, and cannot
            # raise what the launcher set.
            self.assertNotIn("RAISED-HARD", words)
            self.assertEqual(words[-2], words[-1])
            self.assertTrue(words[-1].isdigit())
            self.assertEqual(
                os.stat(os.path.join(work, "made.txt")).st_uid,
                entry.pw_uid)
            self.assertEqual(
                proc.confinement_notes[-1],
                "job user nobody applied at the spawn door")
            # Nothing in the chain was root inside the profile:
            # a file root alone may read stays unread.
            kept = os.path.join(work, "root-only.txt")
            with open(kept, "w") as fh:
                fh.write("ROOT-ONLY")
            os.chmod(kept, 0o600)
            proc = MC.spawn_confined_process(
                ["/bin/sh", "-c",
                 "/bin/cat root-only.txt 2>/dev/null; echo END"],
                cwd=work, env=dict(os.environ), user=self.USER)
            out, err = proc.communicate(timeout=60)
            proc.close()
            self.assertNotIn(b"ROOT-ONLY", out)
            self.assertIn(b"END", out)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_an_ordinary_runner_cannot_start_a_job_as_another(self):
        if os.geteuid() == 0:
            self.skipTest("root may start a job as any user: run in "
                          "the macos-confinement workflow's "
                          "ordinary-user step")
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(RuntimeError) as caught:
                MC.spawn_confined_process(
                    ["/usr/bin/true"], cwd=work, user=self.USER)
        self.assertIn("could not be started", str(caught.exception))

    def test_a_user_this_mac_does_not_have_is_a_refusal(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(RuntimeError) as caught:
                MC.spawn_confined_process(
                    ["/usr/bin/true"], cwd=work,
                    user="hp-no-such-user-zz9")
        self.assertIn("not in this machine's user database",
                      str(caught.exception))


if __name__ == "__main__":
    unittest.main()
