# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The AppContainer control in the Windows confinement backend.

The Win32 spawn cannot execute on this host, so the proof here
rides the platform neutral half of runner/guard/windows_confine.py:
the container name's shape (with the bookend family around it),
the capabilities structure with its empty capability set, the
attribute list construction, the recorded grant set, the
AppContainer trial's four checks and each named failure, the
job shape probe (the trial's second half) and each of its
named failures, the status string naming app_container only
when the trial passes,
and the floor's behavior unchanged when it does not.
"""
import os
import string
import subprocess
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from runner.guard import windows_confine as WC


class FakeProc:
    def __init__(self, out=b"", err=b"", returncode=0,
                 timeout=False):
        self._out = out
        self._err = err
        self.returncode = returncode
        self._timeout = timeout
        self.closed = False
        self.killed = False

    def communicate(self, timeout=None):
        if self._timeout:
            raise subprocess.TimeoutExpired("trial", timeout)
        return self._out, self._err

    def kill(self):
        self.killed = True

    def close(self):
        self.closed = True


def _spawn_returning(proc, calls=None):
    def _spawn(argv, cwd=None, env=None):
        if calls is not None:
            calls.append((argv, cwd))
        return proc
    return _spawn


_ALL_OK = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
           b"AC-OUTSIDE-WRITE-REFUSED\nAC-NETWORK-REFUSED\n"
           b"AC-TOKEN-APPCONTAINER\n")


class ContainerNameTests(unittest.TestCase):
    def test_fixed_name_is_valid(self):
        self.assertIsNone(
            WC.validate_app_container_name(WC.APP_CONTAINER_NAME))
        self.assertEqual(WC.APP_CONTAINER_NAME,
                         "pigeon-home.homing-pigeon.runner")

    def test_plain_shapes_are_valid(self):
        for name in ("a", "A1", "hp.runner", "hp_runner", "a" * 64,
                     "x" * 10 + "-" + "y" * 10):
            with self.subTest(name=name):
                self.assertIsNone(WC.validate_app_container_name(name))

    def test_empty_and_non_string_refused(self):
        for bad in ("", None, 7, b"hp", ["hp"]):
            with self.subTest(bad=bad):
                self.assertIsNotNone(WC.validate_app_container_name(bad))

    def test_too_long_refused(self):
        self.assertIsNotNone(
            WC.validate_app_container_name("a" * 65))
        self.assertIsNotNone(
            WC.validate_app_container_name("a" * 1000))

    def test_bookend_symbols_refused(self):
        # Every symbol on the keyboard, wrapped around a good
        # name at the front, the back, and both ends: only the
        # shape's own characters (dot, underscore, hyphen, in
        # their places) may survive, and a leading symbol never
        # does, because the name must start alphanumeric.
        base = "hp9"
        for ch in string.punctuation:
            for wrapped in (ch + base, base + ch, ch + base + ch):
                with self.subTest(wrapped=wrapped):
                    problem = WC.validate_app_container_name(wrapped)
                    if ch in "._-" and wrapped == base + ch:
                        self.assertIsNone(problem)
                    elif ch == "." and wrapped == ch + base:
                        self.assertIsNotNone(problem)
                    else:
                        self.assertIsNotNone(problem)

    def test_bookend_edge_characters_refused(self):
        base = "hp9"
        for ch in ("\x00", "\t", "\r", "\n", " ", "/", "\\", ":"):
            for wrapped in (ch + base, base + ch, ch + base + ch,
                            ch * 10 + base, base + ch * 10,
                            base[:1] + ch * 10 + base[1:]):
                with self.subTest(wrapped=repr(wrapped)):
                    self.assertIsNotNone(
                        WC.validate_app_container_name(wrapped))

    def test_symbol_only_and_whitespace_only_refused(self):
        for bad in ("-", ".", "_", "---", "...", "   ", "\t\n",
                    "!!!", "-hp", ".hp", "_hp"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(WC.validate_app_container_name(bad))

    def test_runs_of_ordinary_then_odd_refused(self):
        self.assertIsNotNone(WC.validate_app_container_name(
            "a" * 10 + ";"))
        self.assertIsNotNone(WC.validate_app_container_name(
            ";" * 10 + "a"))
        self.assertIsNotNone(WC.validate_app_container_name(
            "a" * 5 + ";" * 10 + "a" * 5))


class CapabilitiesTests(unittest.TestCase):
    def test_empty_capability_set(self):
        caps = WC.build_security_capabilities("S-1-15-2-123")
        self.assertEqual(caps["app_container_sid"], "S-1-15-2-123")
        self.assertEqual(caps["capabilities"], ())
        self.assertEqual(caps["capability_count"], 0)
        self.assertEqual(caps["reserved"], 0)

    def test_any_capability_is_an_error(self):
        for asked in (["internetClient"], ["S-1-15-3-1"],
                      ["internetClient", "picturesLibrary"]):
            with self.subTest(asked=asked):
                with self.assertRaises(ValueError):
                    WC.build_security_capabilities(
                        "S-1-15-2-123", capabilities=asked)

    def test_missing_sid_is_an_error(self):
        for bad in (None, ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    WC.build_security_capabilities(bad)

    def test_attribute_spec(self):
        caps = WC.build_security_capabilities("S-1-15-2-123")
        attr, payload = WC.proc_thread_attribute_spec(caps)
        self.assertEqual(
            attr, WC.PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES)
        self.assertEqual(attr, 0x00020009)
        self.assertIs(payload, caps)

    def test_attribute_spec_refuses_a_wide_capabilities_dict(self):
        wide = {"app_container_sid": "S-1-15-2-123",
                "capabilities": ("S-1-15-3-1",),
                "capability_count": 1, "reserved": 0}
        with self.assertRaises(ValueError):
            WC.proc_thread_attribute_spec(wide)
        with self.assertRaises(ValueError):
            WC.proc_thread_attribute_spec(None)
        with self.assertRaises(ValueError):
            WC.proc_thread_attribute_spec({})


class GrantSetTests(unittest.TestCase):
    def test_work_dir_full_and_reads_read_execute(self):
        grants = WC.app_container_grant_set(
            "/work", ["/ro/one", "/ro/two"])
        self.assertEqual(grants, [("/work", "read_write_execute"),
                                  ("/ro/one", "read_execute"),
                                  ("/ro/two", "read_execute"),
                                  ("/ro", "read_execute")])

    def test_only_the_named_paths_and_their_ancestors(self):
        # The Lane 8 shape (2026-11-21): the named paths, and
        # the ancestors a contained process must walk to reach
        # them, and nothing else. A relative work directory
        # names no ancestor and gains none.
        grants = WC.app_container_grant_set("/work")
        self.assertEqual(grants, [("/work", "read_write_execute")])
        self.assertNotIn("/etc", [p for p, _ in grants])
        grants = WC.app_container_grant_set("work")
        self.assertEqual(grants, [("work", "read_write_execute")])

    def test_ancestors_nearest_first_stopping_below_the_root(self):
        # The walk stops below the root of the drive or tree
        # and never names it (the 2026-11-23 residue fix): a
        # grant on the root is a grantor call on the one path
        # whose security write hung on the project's own rig,
        # and no contained process needs it, because every
        # ancestor below the root still stands in the set and
        # a host whose root names nothing the token holds
        # fails the trial and falls back to the floor.
        self.assertEqual(
            WC.app_container_ancestor_dirs("/a/b/c"),
            ["/a/b", "/a"])
        self.assertEqual(WC.app_container_ancestor_dirs("/a"),
                         [])
        self.assertEqual(WC.app_container_ancestor_dirs("a"), [])
        grants = WC.app_container_grant_set("/a/b/c")
        self.assertEqual(grants, [("/a/b/c", "read_write_execute"),
                                  ("/a/b", "read_execute"),
                                  ("/a", "read_execute")])

    def test_no_grant_set_ever_names_the_root(self):
        for work in ("/a", "/a/b", "/a/b/c/d", "/work"):
            with self.subTest(work=work):
                grants = WC.app_container_grant_set(
                    work, ["/ro/one", "/ro/two/deep"])
                self.assertNotIn("/", [p for p, _ in grants])
                self.assertNotIn(
                    "/", WC.app_container_ancestor_dirs(work))

    def test_duplicates_collapse_in_order(self):
        grants = WC.app_container_grant_set(
            "/work", ["/ro", "/ro", "/work", "/other", "/ro"])
        self.assertEqual(grants, [("/work", "read_write_execute"),
                                  ("/ro", "read_execute"),
                                  ("/other", "read_execute")])

    def test_empty_work_dir_is_an_error(self):
        for bad in ("", None, 7):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    WC.app_container_grant_set(bad)

    def test_empty_read_path_is_an_error(self):
        with self.assertRaises(ValueError):
            WC.app_container_grant_set("/work", [""])
        with self.assertRaises(ValueError):
            WC.app_container_grant_set("/work", [None])


class DaclSnapshotTests(unittest.TestCase):
    """The failed spawn's cleanup, as orchestration (the
    2026-11-23 residue fix).

    The rig diagnosis proved the cycle: a failed AppContainer
    spawn's cleanup edited grant entries back out one call per
    path, a call on this host can sit past its timeout, and
    the entry that survived on the interpreter's own directory
    broke every later floor trial at load. The cleanup now
    snapshots each granted path's DACL before the first grant
    stands and writes the snapshots back whole on failure.
    The OS calls are Windows only; what is pinned here is the
    orchestration the backend wires them through, plus the
    source shape of that wiring.
    """

    def test_snapshots_cover_every_path_in_order(self):
        seen = []

        def _snapshot(path):
            seen.append(path)
            return "D:SNAP(%s)" % path, None

        snapshots, problem = WC.take_dacl_snapshots(
            ["/a", "/b", "/c"], _snapshot)
        self.assertIsNone(problem)
        self.assertEqual(seen, ["/a", "/b", "/c"])
        self.assertEqual(snapshots, [("/a", "D:SNAP(/a)"),
                                     ("/b", "D:SNAP(/b)"),
                                     ("/c", "D:SNAP(/c)")])

    def test_a_path_that_cannot_be_snapshotted_grants_nothing(self):
        # All or nothing: the first snapshot problem answers
        # with no snapshots at all, so the caller grants
        # nothing it cannot put back whole.
        def _snapshot(path):
            if path == "/b":
                return None, "GetNamedSecurityInfoW(/b) failed: 5"
            return "D:SNAP(%s)" % path, None

        snapshots, problem = WC.take_dacl_snapshots(
            ["/a", "/b", "/c"], _snapshot)
        self.assertEqual(snapshots, [])
        self.assertIn("GetNamedSecurityInfoW(/b) failed: 5",
                      problem)

    def test_restore_writes_every_snapshot_back_in_reverse(self):
        written = []

        def _set_dacl(path, sddl):
            written.append((path, sddl))
            return None

        failed = WC.restore_dacl_snapshots(
            [("/a", "D:ONE"), ("/b", "D:TWO"), ("/c", "D:THREE")],
            _set_dacl)
        self.assertEqual(failed, [])
        self.assertEqual(written, [("/c", "D:THREE"),
                                   ("/b", "D:TWO"),
                                   ("/a", "D:ONE")])

    def test_restore_reports_the_paths_it_could_not_put_back(self):
        def _set_dacl(path, sddl):
            if path == "/b":
                return "SetNamedSecurityInfoW(/b) failed: 5"
            return None

        failed = WC.restore_dacl_snapshots(
            [("/a", "D:ONE"), ("/b", "D:TWO")], _set_dacl)
        self.assertEqual(failed, ["/b"])

    def test_spawn_snapshots_before_it_grants(self):
        # The wiring, pinned by source shape as the ACL
        # helper's inheritance shape is: the spawn takes its
        # grants through the snapshot carrying grant, and its
        # failure paths restore the snapshots instead of
        # editing entries back out.
        source = self._source()
        grant = source.index("def _grant_app_container_paths"
                             "_with_snapshots")
        body = source[grant:grant + 4000]
        self.assertLess(body.index("take_dacl_snapshots"),
                        body.index("_set_entries_in_acl"))
        self.assertIn("restore_dacl_snapshots", body)
        spawn = source.index(
            "def spawn_app_container_process(argv, cwd=None, "
            "env=None,")
        spawn_body = source[spawn:spawn + 12000]
        self.assertIn("_grant_app_container_paths_with_snapshots",
                      spawn_body)
        self.assertIn("_restore_failed_spawn_dacls", spawn_body)

    def _source(self):
        path = os.path.join(
            _REPO, "runner", "guard", "windows_confine.py")
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class AncestorWalkVariationsTests(unittest.TestCase):
    """The ancestor walk, shape by shape (the 2026-11-23
    residue fix, variation family).

    The one property every shape shares: the root of the
    drive or tree is never in the walk, so no grant set built
    from it can name the root. The shapes below pin the walk
    exactly where the arithmetic is plain, and pin the shared
    property where the spelling is odd.
    """

    def test_a_deep_chain_walks_every_level_but_the_root(self):
        self.assertEqual(
            WC.app_container_ancestor_dirs("/a/b/c/d/e/f/g/h"),
            ["/a/b/c/d/e/f/g", "/a/b/c/d/e/f", "/a/b/c/d/e",
             "/a/b/c/d", "/a/b/c", "/a/b", "/a"])

    def test_two_levels_have_one_ancestor(self):
        self.assertEqual(WC.app_container_ancestor_dirs("/a/b"),
                         ["/a"])

    def test_the_root_itself_has_no_ancestors(self):
        self.assertEqual(WC.app_container_ancestor_dirs("/"),
                         [])

    def test_an_empty_path_has_no_ancestors(self):
        self.assertEqual(WC.app_container_ancestor_dirs(""),
                         [])

    def test_relative_chains_stop_below_their_top(self):
        self.assertEqual(
            WC.app_container_ancestor_dirs("a/b/c"),
            ["a/b", "a"])
        self.assertEqual(WC.app_container_ancestor_dirs("a/b"),
                         ["a"])
        self.assertEqual(WC.app_container_ancestor_dirs("a"),
                         [])

    def test_a_trailing_separator_names_the_same_walk(self):
        self.assertEqual(
            WC.app_container_ancestor_dirs("/a/b/"),
            ["/a/b", "/a"])

    def test_odd_spellings_still_never_name_the_root(self):
        for path in ("/a//b/c", "/a/./b", "//a/b", "/a/b/.",
                     "/x//y//z", "/a/b/c/"):
            with self.subTest(path=path):
                self.assertNotIn(
                    "/", WC.app_container_ancestor_dirs(path))

    def test_no_generated_shape_names_the_root(self):
        parts = ["a", "bb", "ccc", "d d", "e.f", "g-h"]
        for depth in range(1, len(parts) + 1):
            path = "/" + "/".join(parts[:depth])
            with self.subTest(path=path):
                ancestors = WC.app_container_ancestor_dirs(path)
                self.assertNotIn("/", ancestors)
                self.assertEqual(len(ancestors), depth - 1)
                grants = WC.app_container_grant_set(
                    path, ["/ro/one", "/ro"])
                self.assertNotIn(
                    "/", [p for p, _ in grants])

    def test_a_top_level_read_path_contributes_no_ancestor(self):
        grants = WC.app_container_grant_set("/a/b", ["/ro"])
        self.assertEqual(
            grants, [("/a/b", "read_write_execute"),
                     ("/ro", "read_execute"),
                     ("/a", "read_execute")])

    def test_shared_ancestors_collapse_without_the_root(self):
        grants = WC.app_container_grant_set(
            "/deep/a/b/c", ["/deep/a/x", "/top"])
        self.assertEqual(
            grants, [("/deep/a/b/c", "read_write_execute"),
                     ("/deep/a/x", "read_execute"),
                     ("/top", "read_execute"),
                     ("/deep/a/b", "read_execute"),
                     ("/deep/a", "read_execute"),
                     ("/deep", "read_execute")])

    def test_the_work_dir_at_the_top_gains_no_ancestor(self):
        grants = WC.app_container_grant_set("/work", ["/ro"])
        self.assertEqual(
            grants, [("/work", "read_write_execute"),
                     ("/ro", "read_execute")])


class DaclSnapshotVariationsTests(unittest.TestCase):
    """The snapshot and restore orchestration, edge shapes
    (the 2026-11-23 residue fix, variation family)."""

    def test_no_paths_snapshot_to_nothing(self):
        def _snapshot(path):
            raise AssertionError("snapshot of nothing")

        snapshots, problem = WC.take_dacl_snapshots(
            [], _snapshot)
        self.assertEqual(snapshots, [])
        self.assertIsNone(problem)

    def test_a_first_path_failure_snapshots_nothing_later(self):
        seen = []

        def _snapshot(path):
            seen.append(path)
            return None, "read failed: 5"

        snapshots, problem = WC.take_dacl_snapshots(
            ["/a", "/b", "/c"], _snapshot)
        self.assertEqual(snapshots, [])
        self.assertEqual(seen, ["/a"])
        self.assertIn("read failed: 5", problem)

    def test_a_last_path_failure_discards_earlier_snapshots(self):
        def _snapshot(path):
            if path == "/c":
                return None, "read failed: 5"
            return "D:SNAP(%s)" % path, None

        snapshots, problem = WC.take_dacl_snapshots(
            ["/a", "/b", "/c"], _snapshot)
        self.assertEqual(snapshots, [])
        self.assertIsNotNone(problem)

    def test_duplicate_paths_are_snapshotted_per_occurrence(self):
        snapshots, problem = WC.take_dacl_snapshots(
            ["/a", "/a"],
            lambda path: ("D:SNAP(%s)" % path, None))
        self.assertIsNone(problem)
        self.assertEqual(snapshots, [("/a", "D:SNAP(/a)"),
                                     ("/a", "D:SNAP(/a)")])

    def test_sddl_is_carried_verbatim(self):
        odd = ["", "D:", "D:(A;;FA;;;SY)(A;;RX;;;BU)",
               "D:(A;;FR;;;S-1-15-2-1-2-3)", "x" * 4096,
               "D:(A;;FA;;;SY) trailing words"]
        for sddl in odd:
            with self.subTest(sddl=sddl[:20]):
                snapshots, problem = WC.take_dacl_snapshots(
                    ["/p"], lambda path: (sddl, None))
                self.assertIsNone(problem)
                self.assertEqual(snapshots, [("/p", sddl)])

    def test_restoring_nothing_fails_nothing(self):
        def _set_dacl(path, sddl):
            raise AssertionError("restore of nothing")

        self.assertEqual(
            WC.restore_dacl_snapshots([], _set_dacl), [])

    def test_restore_passes_each_sddl_verbatim(self):
        written = []

        def _set_dacl(path, sddl):
            written.append((path, sddl))
            return None

        pairs = [("/a", "D:(A;;FA;;;SY)"),
                 ("/b", ""), ("/c", "D:")]
        self.assertEqual(
            WC.restore_dacl_snapshots(pairs, _set_dacl), [])
        self.assertEqual(written, list(reversed(pairs)))

    def test_restore_reports_every_failure_in_attempt_order(self):
        def _set_dacl(path, sddl):
            return "write failed on %s" % path

        failed = WC.restore_dacl_snapshots(
            [("/a", "D:1"), ("/b", "D:2"), ("/c", "D:3")],
            _set_dacl)
        self.assertEqual(failed, ["/c", "/b", "/a"])

    def test_restore_continues_past_a_middle_failure(self):
        written = []

        def _set_dacl(path, sddl):
            written.append(path)
            if path == "/b":
                return "write failed: 5"
            return None

        failed = WC.restore_dacl_snapshots(
            [("/a", "D:1"), ("/b", "D:2"), ("/c", "D:3")],
            _set_dacl)
        self.assertEqual(failed, ["/b"])
        self.assertEqual(written, ["/c", "/b", "/a"])


class SessionGrantTests(unittest.TestCase):
    """The Lane 7 regression pin (2026-11-21): powershell.exe
    and whoami.exe died inside the container with exit
    -1073741502 (0xC0000142, STATUS_DLL_INIT_FAILED) and no
    output, while cmd.exe, findstr.exe and the Python
    interpreter ran. The rig bisection isolated the cause to
    the session objects: both failing targets import
    USER32.dll directly and the running ones do not, a
    library in that load set opens the creating session's
    window station and desktop while initializing, and the
    container SID held no grant on either. Granting both
    objects ran both targets; revoking both restored the
    failure; the least sufficient masks are the window
    station at 0x0102 (WINSTA_READATTRIBUTES plus
    WINSTA_ENUMERATE) and the desktop at 0x0001
    (DESKTOP_READOBJECTS). These tests pin the recorded
    grant plan and the spawn's use of it from the source, so
    they run on every host."""

    def test_plan_is_exactly_the_two_session_objects(self):
        self.assertEqual(
            WC.app_container_session_grant_set(),
            [("window_station", 0x0102), ("desktop", 0x0001)])

    def test_plan_matches_the_named_constants(self):
        plan = dict(WC.app_container_session_grant_set())
        self.assertEqual(plan["window_station"],
                         WC.WINDOW_STATION_CONTAINER_ACCESS)
        self.assertEqual(plan["desktop"],
                         WC.DESKTOP_CONTAINER_ACCESS)

    def test_window_station_mask_is_read_rights_only(self):
        mask = dict(WC.app_container_session_grant_set())[
            "window_station"]
        # WINSTA_READATTRIBUTES (0x0002) and WINSTA_ENUMERATE
        # (0x0100) are the whole mask: no ENUMDESKTOPS alone
        # (measured insufficient), no create window station,
        # no read screen, no clipboard, no switch rights.
        self.assertEqual(mask & ~0x0102, 0)
        self.assertTrue(mask & 0x0002)
        self.assertTrue(mask & 0x0100)

    def test_desktop_mask_is_readobjects_only(self):
        mask = dict(WC.app_container_session_grant_set())[
            "desktop"]
        self.assertEqual(mask, 0x0001)
        # None of DESKTOP_CREATEWINDOW (0x0002),
        # DESKTOP_WRITEOBJECTS (0x0080), DESKTOP_SWITCHDESKTOP
        # (0x0100) or any standard or generic right stands in
        # the mask.
        self.assertEqual(mask & ~0x0001, 0)

    def test_plan_carries_no_other_object(self):
        kinds = [kind for kind, mask
                 in WC.app_container_session_grant_set()]
        self.assertEqual(kinds, ["window_station", "desktop"])

    def test_plan_is_stable_across_calls(self):
        first = WC.app_container_session_grant_set()
        for _ in range(50):
            self.assertEqual(
                WC.app_container_session_grant_set(), first)

    def test_plan_is_a_fresh_list_each_call(self):
        plan = WC.app_container_session_grant_set()
        plan.append(("clipboard", 0xFFFF))
        self.assertEqual(
            WC.app_container_session_grant_set(),
            [("window_station", 0x0102), ("desktop", 0x0001)])

    def test_plan_entries_are_string_mask_pairs(self):
        for kind, mask in WC.app_container_session_grant_set():
            self.assertIsInstance(kind, str)
            self.assertIsInstance(mask, int)
            self.assertGreater(mask, 0)

    def _source(self):
        with open(WC.__file__, encoding="utf-8") as fh:
            return fh.read()

    def test_spawn_grants_the_session_objects(self):
        self.assertIn(
            "_grant_app_container_session_objects(sid)",
            self._source())

    def test_spawn_records_the_session_grants(self):
        self.assertIn(
            "proc.app_container_session_grants = session_grants",
            self._source())

    def test_close_revokes_the_session_grants(self):
        source = self._source()
        self.assertIn(
            "_remove_app_container_session_object_grants(\n"
            "                        _grant_sid, session_grants)",
            source)

    def test_failed_spawn_revokes_the_session_grants(self):
        source = self._source()
        self.assertIn(
            "_remove_app_container_session_object_grants(\n"
            "                        sid, session_grants)",
            source)

    def test_session_grants_use_the_handle_security_calls(self):
        source = self._source()
        self.assertIn("advapi32.GetSecurityInfo(", source)
        self.assertIn("advapi32.SetSecurityInfo(", source)
        self.assertIn("SE_WINDOW_OBJECT", source)

    def test_backend_session_grants_answer_matches(self):
        if WC.IS_WINDOWS_BACKEND:
            self.assertEqual(
                WC.app_container_session_grants(),
                WC.app_container_session_grant_set())
        else:
            self.assertEqual(WC.app_container_session_grants(),
                             [])


class TrialTests(unittest.TestCase):
    def test_all_four_checks_pass(self):
        proc = FakeProc(out=_ALL_OK)
        calls = []
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc, calls))
        self.assertIsNone(problem)
        self.assertTrue(proc.closed)
        argv, cwd = calls[0]
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(cwd, argv[3])

    def test_grant_gets_granted_paths_and_never_the_outside(self):
        seen = []

        def _grant(paths):
            seen.extend(paths)
            return None

        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=_ALL_OK)), grant=_grant)
        self.assertIsNone(problem)
        self.assertEqual(len(seen), 4)
        self.assertFalse(any("outside" in p for p in seen))

    def test_spawn_failure_is_named(self):
        def _spawn(argv, cwd=None, env=None):
            raise RuntimeError("CreateProcessW failed: 5")

        problem = WC.appcontainer_trial_problem(_spawn)
        self.assertIn("AppContainer trial spawn failed", problem)
        self.assertIn("CreateProcessW failed: 5", problem)

    def test_read_failure_is_named(self):
        proc = FakeProc(out=b"AC-READ-FAIL denied\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc))
        self.assertIn("could not read its granted staged file",
                      problem)

    def test_write_failure_is_named(self):
        proc = FakeProc(out=b"AC-READ-OK\nAC-WRITE-FAIL denied\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc))
        self.assertIn("could not write its work directory", problem)

    def test_outside_open_is_a_named_boundary_failure(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-OPEN\n"
               b"AC-OUTSIDE-WRITE-REFUSED\nAC-NETWORK-REFUSED\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("read outside its granted paths", problem)

    def test_outside_check_missing_is_named(self):
        out = b"AC-READ-OK\nAC-WRITE-OK\nAC-NETWORK-REFUSED\n"
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("outside the granted paths", problem)

    def test_network_open_is_a_named_boundary_failure(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
               b"AC-OUTSIDE-WRITE-REFUSED\nAC-NETWORK-OPEN\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("reached the network", problem)

    def test_network_check_missing_is_named(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
               b"AC-OUTSIDE-WRITE-REFUSED\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("network access being refused", problem)

    def test_timeout_is_named_and_kills(self):
        proc = FakeProc(timeout=True)
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc), timeout=3)
        self.assertIn("timed out after 3s", problem)
        self.assertTrue(proc.killed)

    def test_grant_problem_is_named(self):
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=_ALL_OK)),
            grant=lambda paths: "SetNamedSecurityInfoW failed: 5")
        self.assertIn("could not grant its staged tree", problem)
        self.assertIn("SetNamedSecurityInfoW failed: 5", problem)

    def test_grant_raising_is_named(self):
        def _grant(paths):
            raise OSError("no DACL")

        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=_ALL_OK)), grant=_grant)
        self.assertIn("could not grant its staged tree", problem)

    def test_outside_write_open_is_a_boundary_crossing(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
               b"AC-OUTSIDE-WRITE-OPEN\nAC-NETWORK-REFUSED\n"
               b"AC-TOKEN-APPCONTAINER\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("wrote outside its granted paths", problem)
        self.assertTrue(WC.app_container_boundary_crossing(problem))

    def test_token_parent_side_true_satisfies_the_check(self):
        # The Lane 6 addendum: inside the container the trial
        # program's ctypes import can fail to initialize, so
        # no token line is printed; the spawn's own process
        # object answers from the parent side instead.
        class ParentCheckedProc(FakeProc):
            def is_app_container_token(self):
                return True

        out = _ALL_OK.replace(b"AC-TOKEN-APPCONTAINER\n", b"")
        self.assertIsNone(WC.appcontainer_trial_problem(
            _spawn_returning(ParentCheckedProc(out=out))))

    def test_token_parent_side_false_is_named(self):
        class ParentCheckedProc(FakeProc):
            def is_app_container_token(self):
                return False

        out = _ALL_OK.replace(b"AC-TOKEN-APPCONTAINER\n", b"")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(ParentCheckedProc(out=out)))
        self.assertIn("could not read an AppContainer token",
                      problem)

    def test_token_parent_side_unreadable_is_named(self):
        class ParentCheckedProc(FakeProc):
            def is_app_container_token(self):
                return None

        out = _ALL_OK.replace(b"AC-TOKEN-APPCONTAINER\n", b"")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(ParentCheckedProc(out=out)))
        self.assertIn("could not read an AppContainer token",
                      problem)

    def test_token_plain_is_named(self):
        out = _ALL_OK.replace(b"AC-TOKEN-APPCONTAINER",
                              b"AC-TOKEN-PLAIN")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("not an AppContainer token", problem)

    def test_trial_program_carries_the_four_checks(self):
        for marker in ("AC-READ-OK", "AC-WRITE-OK",
                       "AC-OUTSIDE-REFUSED", "AC-NETWORK-REFUSED",
                       "AC-OUTSIDE-OPEN", "AC-NETWORK-OPEN",
                       "AC-OUTSIDE-WRITE-REFUSED",
                       "AC-OUTSIDE-WRITE-OPEN",
                       "AC-TOKEN-APPCONTAINER"):
            self.assertIn(marker, WC._AC_TRIAL_PROGRAM)


_JOB_ARGV = ["powershell", "-NoProfile", "-NonInteractive",
             "-Command", "Write-Output AC-JOBSHAPE-OK"]
_JOB_MARKER = "AC-JOBSHAPE-OK"


class JobShapeProbeTests(unittest.TestCase):
    """appcontainer_job_shape_problem through scripted spawn
    seams: the trial's second half. The field failure it pins
    (the Germany rig, 2026-11-22): the AppContainer trial
    passed with the host's Python interpreter while every
    powershell job died at load with exit -1073741502
    (0xC0000142, STATUS_DLL_INIT_FAILED) and empty output,
    because a .NET Framework program does not initialize
    inside a container token on that host. The probe exists
    so the verdict names that instead of engaging a control
    every job would fail inside."""

    def test_job_shape_runs_contained(self):
        proc = FakeProc(out=b"AC-JOBSHAPE-OK\r\n")
        calls = []
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc, calls), _JOB_ARGV,
            _JOB_MARKER)
        self.assertIsNone(problem)
        self.assertTrue(proc.closed)
        argv, cwd = calls[0]
        self.assertEqual(argv, _JOB_ARGV)
        self.assertEqual(argv[0], "powershell")
        self.assertTrue(os.path.isdir(cwd) is False)

    def test_measured_dll_init_failure_is_named(self):
        proc = FakeProc(out=b"", err=b"", returncode=-1073741502)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIn("could not run the job interpreter "
                      "powershell to completion", problem)
        self.assertIn("-1073741502", problem)

    def test_marker_with_nonzero_exit_is_named(self):
        proc = FakeProc(out=b"AC-JOBSHAPE-OK\n", returncode=1)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIn("printed the job shape marker", problem)
        self.assertIn("exited 1", problem)

    def test_exit_zero_without_the_marker_is_named(self):
        proc = FakeProc(out=b"PS-OK\n", returncode=0)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIn("could not run the job interpreter",
                      problem)

    def test_spawn_failure_is_named(self):
        def _spawn(argv, cwd=None, env=None):
            raise RuntimeError("CreateProcessW failed: 2")

        problem = WC.appcontainer_job_shape_problem(
            _spawn, _JOB_ARGV, _JOB_MARKER)
        self.assertIn("AppContainer job shape spawn failed",
                      problem)
        self.assertIn("CreateProcessW failed: 2", problem)

    def test_timeout_is_named_and_kills(self):
        proc = FakeProc(timeout=True)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER,
            timeout=3)
        self.assertIn("timed out after 3s", problem)
        self.assertIn("powershell", problem)
        self.assertTrue(proc.killed)
        self.assertTrue(proc.closed)

    def test_str_output_is_accepted(self):
        proc = FakeProc(out="AC-JOBSHAPE-OK\n")
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIsNone(problem)

    def test_none_returncode_with_marker_is_accepted(self):
        proc = FakeProc(out=b"AC-JOBSHAPE-OK\n", returncode=None)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIsNone(problem)

    def test_error_tail_is_named_in_the_problem(self):
        proc = FakeProc(out=b"", err=b"noise\nLAST-LINE\n",
                        returncode=5)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIn("LAST-LINE", problem)

    def test_marker_inside_a_longer_line_counts(self):
        proc = FakeProc(out=b"xx AC-JOBSHAPE-OK yy\n")
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIsNone(problem)

    def test_marker_bookended_by_symbols_counts(self):
        proc = FakeProc(out=b"---;;;AC-JOBSHAPE-OK;;;---\n")
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIsNone(problem)

    def test_marker_bookended_by_nul_bytes_counts(self):
        proc = FakeProc(out=b"\x00AC-JOBSHAPE-OK\x00\n")
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIsNone(problem)

    def test_symbol_only_output_is_named(self):
        proc = FakeProc(out=b"---;;;---\n", returncode=0)
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER)
        self.assertIn("could not run the job interpreter",
                      problem)

    def test_empty_argv_is_refused_before_any_spawn(self):
        calls = []
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(FakeProc(), calls), [], _JOB_MARKER)
        self.assertIn("needs a job interpreter argv", problem)
        self.assertEqual(calls, [])

    def test_none_argv_is_refused(self):
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(FakeProc()), None, _JOB_MARKER)
        self.assertIn("needs a job interpreter argv", problem)

    def test_non_string_argv_element_is_refused(self):
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(FakeProc()),
            ["powershell", 3], _JOB_MARKER)
        self.assertIn("needs a job interpreter argv", problem)

    def test_empty_marker_is_refused(self):
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(FakeProc()), _JOB_ARGV, "")
        self.assertIn("needs a job interpreter argv", problem)

    def test_non_string_marker_is_refused(self):
        for marker in (None, b"AC-JOBSHAPE-OK", 7):
            problem = WC.appcontainer_job_shape_problem(
                _spawn_returning(FakeProc()), _JOB_ARGV, marker)
            self.assertIn("needs a job interpreter argv",
                          problem)

    def test_tuple_argv_runs_like_a_list(self):
        proc = FakeProc(out=b"AC-JOBSHAPE-OK\n")
        problem = WC.appcontainer_job_shape_problem(
            _spawn_returning(proc), tuple(_JOB_ARGV),
            _JOB_MARKER)
        self.assertIsNone(problem)

    def test_no_job_shape_failure_is_a_boundary_crossing(self):
        variants = [
            FakeProc(out=b"", err=b"", returncode=-1073741502),
            FakeProc(out=b"AC-JOBSHAPE-OK\n", returncode=1),
            FakeProc(out=b"nothing\n", returncode=0),
            FakeProc(timeout=True),
        ]
        for proc in variants:
            problem = WC.appcontainer_job_shape_problem(
                _spawn_returning(proc), _JOB_ARGV, _JOB_MARKER,
                timeout=3)
            self.assertIsNotNone(problem)
            self.assertFalse(
                WC.app_container_boundary_crossing(problem),
                problem)
            self.assertIsNone(WC.confinement_gate_problem(
                None, problem), problem)

    def test_gate_still_refuses_a_crossing_with_the_probe(self):
        crossing = ("AppContainer boundary crossing: an "
                    "AppContainer process read outside its "
                    "granted paths")
        self.assertEqual(
            WC.confinement_gate_problem(None, crossing),
            crossing)


class JobShapeWiringTests(unittest.TestCase):
    """The verdict composition, pinned from the source so it
    runs on every host: windows_app_container_problem runs
    the interpreter trial first and the job shape probe only
    when the trial passed, and the probe's argv is the job
    interpreter in the job's own shape (bare name first, the
    flags exec builds), never a path around it."""

    def _source(self):
        with open(WC.__file__, encoding="utf-8") as fh:
            return fh.read()

    def _verdict_function(self):
        source = self._source()
        start = source.index("def windows_app_container_problem")
        end = source.index("def spawn_confined_process", start)
        return source[start:end]

    def test_probe_runs_after_a_passing_trial(self):
        body = self._verdict_function()
        trial_at = body.index("appcontainer_trial_problem(")
        guard_at = body.index("if problem is None:")
        probe_at = body.index("appcontainer_job_shape_problem(")
        self.assertLess(trial_at, guard_at)
        self.assertLess(guard_at, probe_at)

    def test_job_shape_argv_is_the_jobs_own_shape(self):
        source = self._source()
        self.assertIn('AC_JOB_SHAPE_MARKER = "AC-JOBSHAPE-OK"',
                      source)
        self.assertIn(
            '"powershell", "-NoProfile", "-NonInteractive",',
            source)
        self.assertIn(
            '"-Command", "Write-Output " + AC_JOB_SHAPE_MARKER',
            source)

    def test_probe_marker_matches_the_argv_marker(self):
        body = self._verdict_function()
        self.assertIn("list(AC_JOB_SHAPE_ARGV)", body)
        self.assertIn("AC_JOB_SHAPE_MARKER", body)


class ProfileAndGateTests(unittest.TestCase):
    def test_profile_creation_outcomes(self):
        self.assertEqual(WC.profile_creation_outcome(0), "created")
        self.assertEqual(
            WC.profile_creation_outcome(0x800700B7), "exists")
        self.assertEqual(
            WC.profile_creation_outcome(-2147024713), "exists")
        self.assertEqual(
            WC.profile_creation_outcome(0x80070005), "failed")

    def test_missing_mechanism_falls_back_but_crossing_refuses(self):
        self.assertIsNone(WC.confinement_gate_problem(
            None, "AppContainer trial spawn failed: x"))
        self.assertIsNone(WC.confinement_gate_problem(None, None))
        crossing = ("AppContainer boundary crossing: an "
                    "AppContainer process read outside its "
                    "granted paths")
        self.assertEqual(
            WC.confinement_gate_problem(None, crossing), crossing)
        self.assertEqual(
            WC.confinement_gate_problem("floor failed", crossing),
            "floor failed")
        self.assertFalse(WC.app_container_boundary_crossing(
            "AppContainer trial spawn failed: x"))
        self.assertFalse(WC.app_container_boundary_crossing(None))


class ProfileCallShapeTests(unittest.TestCase):
    """The Lane 6 regression pin (2026-11-21): the native
    CreateAppContainerProfile takes six parameters, the
    capabilities array, its DWORD count, and only then the
    SID out pointer. The binding this module shipped declared
    five, the count missing, so the call failed with
    E_INVALIDARG on every host, no profile ever stood, and
    every AppContainer CreateProcessW failed with
    ERROR_FILE_NOT_FOUND while derivation, being algorithmic,
    succeeded and hid the cause. These tests pin the shape
    from the source, so they run on every host, and from the
    live binding where the backend is real."""

    def _source(self):
        with open(WC.__file__, encoding="utf-8") as fh:
            return fh.read()

    def test_binding_declares_the_count_before_the_sid(self):
        self.assertIn(
            "userenv.CreateAppContainerProfile.argtypes = [\n"
            "        wintypes.LPCWSTR, wintypes.LPCWSTR, "
            "wintypes.LPCWSTR,\n"
            "        wintypes.LPVOID, wintypes.DWORD,\n"
            "        ctypes.POINTER(wintypes.LPVOID)]",
            self._source())

    def test_the_call_supplies_a_zero_count(self):
        self.assertIn(
            "userenv.CreateAppContainerProfile(\n"
            "            name, PROFILE_DISPLAY_NAME, "
            "PROFILE_DESCRIPTION,\n"
            "            None, 0, ctypes.byref(sid))",
            self._source())

    def test_no_five_argument_profile_call_remains(self):
        self.assertNotIn(
            "None, ctypes.byref(sid))", self._source())

    def test_a_failed_profile_outcome_is_named_not_discarded(self):
        source = self._source()
        self.assertIn('outcome == "failed"', source)
        self.assertIn(
            "CreateAppContainerProfile(%s) failed: ", source)
        self.assertIn(
            "the container profile does not stand", source)

    def test_spawn_grants_the_programs_own_directory(self):
        # The Lane 6 addendum: a container whose SID cannot
        # read the target program's directory dies at load
        # (STATUS_DLL_NOT_FOUND) before a line runs, so the
        # spawn grants that directory itself, recorded in the
        # grant set, ahead of any caller named read path.
        source = self._source()
        self.assertIn("exe_dir = os.path.dirname(argv[0])",
                      source)
        self.assertIn(
            "read_paths = (os.path.abspath(exe_dir),) \\",
            source)

    def test_a_failed_spawn_revokes_its_grants(self):
        # The Lane 6 third measurement: a container SID entry
        # left standing on a library file's DACL makes the
        # floor's restricted token fail at load, so a spawn
        # that fails after granting must clean up before the
        # failure travels, not leave the grant for a process
        # close that will never happen. The cleanup's shape
        # changed with the 2026-11-23 residue fix: the spawn
        # restores the DACL snapshots it took before granting
        # (the entry surgery this test once pinned is the
        # mechanism the rig diagnosis proved leaves the
        # residue), with the recorded revocation kept as the
        # fallback for a path the restore cannot put back.
        source = self._source()
        self.assertIn(
            "except Exception:\n"
            "                # A failed spawn puts back the "
            "grants it made",
            source)
        self.assertIn(
            "_restore_failed_spawn_dacls(\n"
            "                        snapshots, sid, grants)",
            source)
        self.assertIn(
            "remove_app_container_grants(\n"
            "                    sid, [(path, by_path[path])",
            source)

    def test_live_binding_carries_six_parameters(self):
        if not WC.IS_WINDOWS_BACKEND:
            self.skipTest(
                "the live userenv binding exists only on a "
                "Windows backend host")
        argtypes = WC.userenv.CreateAppContainerProfile.argtypes
        self.assertEqual(len(argtypes), 6)
        self.assertIs(argtypes[4], WC.wintypes.DWORD)


class StatusTests(unittest.TestCase):
    def test_floor_status_is_exact_and_unchanged(self):
        self.assertEqual(
            WC.STATUS_CONFINEMENT,
            "windows: job_object + restricted_token + "
            "low_integrity")
        self.assertEqual(WC.confinement_status(), WC.STATUS_CONFINEMENT)
        self.assertEqual(
            WC.confinement_status(False), WC.STATUS_CONFINEMENT)
        self.assertNotIn("app_container", WC.confinement_status())

    def test_extended_status_names_the_control(self):
        # The design's record string: the AppContainer spawn
        # replaces the restricted token, and low integrity is
        # not double named, so the proven string is its own
        # shape, not the floor string with a name appended.
        self.assertEqual(
            WC.confinement_status(True),
            "windows: job_object + appcontainer + no_network")
        self.assertEqual(
            WC.STATUS_APP_CONTAINER,
            "windows: job_object + appcontainer + no_network")
        self.assertEqual(
            WC.APP_CONTAINER_CONTROLS,
            ("job_object", "appcontainer", "no_network"))
        self.assertNotIn("restricted_token",
                         WC.confinement_status(True))
        self.assertNotIn("low_integrity",
                         WC.confinement_status(True))

    def test_status_follows_the_trial_verdict(self):
        self.assertEqual(
            WC.effective_confinement_status(None),
            WC.STATUS_APP_CONTAINER)
        for failure in ("an AppContainer process could not read "
                        "its granted staged file",
                        "AppContainer trial spawn failed: x"):
            with self.subTest(failure=failure):
                self.assertEqual(
                    WC.effective_confinement_status(failure),
                    WC.STATUS_CONFINEMENT)

    def test_floor_behavior_when_the_trial_fails(self):
        # The gate's floor probe on this host still answers the
        # Windows only problem (the stub backend), the floor
        # spawn still refuses off Windows, and no status the
        # floor path can produce names the new control.
        if not WC.IS_WINDOWS_BACKEND:
            self.assertEqual(
                WC.windows_confinement_problem(),
                "windows_confine is Windows-only")
            self.assertEqual(
                WC.windows_app_container_problem(),
                "windows_confine is Windows-only")
            with self.assertRaises(RuntimeError):
                WC.spawn_app_container_process(
                    ["x"], cwd="/work")
            with self.assertRaises(RuntimeError):
                WC.spawn_confined_process(["x"], cwd="/work")


class Lane8VerdictWiringTests(unittest.TestCase):
    """The Lane 8 regression pin (2026-11-21): in the rig
    battery's own start shape the audit named the floor for
    every job while the trial passed in other start shapes.
    The measurement (recorded in windows_confine.py's
    header) isolated two wiring facts this class pins: the
    spawn seam must consult the trial's verdict itself, not
    only a cache a gate call happened to populate, and the
    loader must hand the gate and the spawn one backend
    instance even though the module carries two import
    names. The grant shape half of the fix is pinned in
    GrantSetTests above.
    """

    def _source(self):
        with open(WC.__file__, encoding="utf-8") as fh:
            return fh.read()

    def test_spawn_seam_consults_the_verdict_itself(self):
        source = self._source()
        start = source.index(
            "def spawn_confined_process(argv, cwd=None, env=None):")
        body = source[start:start + 4000]
        # The verdict is computed through the trial when the
        # cache is empty: an empty cache is not a floor
        # verdict, and the seam may not read it as one.
        self.assertIn("windows_app_container_problem()", body)
        self.assertIn("_ac_trial_verdict[0] if _ac_trial_verdict",
                      body)

    def test_ancestor_grants_carry_no_inheritance(self):
        # An inheritable ancestor entry propagates into the
        # ancestor's existing children when the merged DACL
        # is written back, which would widen a walk to grant
        # into a grant on everything under the ancestor (the
        # Lane 8 fix's first battery run read exactly that
        # as a boundary crossing in the trial). The grant
        # loop must pass the ancestor entries with no
        # inheritance, and the ACL helper must be able to
        # express that.
        source = self._source()
        self.assertIn("inherit=path not in ancestors", source)
        self.assertIn("def _set_entries_in_acl(path, sid, mask, "
                      "mode, inherit=True):", source)

    def test_loader_registers_one_instance_under_both_names(self):
        from runner.ops import remediation_ops as REM
        mod = REM._windows_confine()
        self.assertIsNotNone(mod)
        self.assertIs(
            sys.modules.get("runner.guard.windows_confine"), mod)
        self.assertIs(
            sys.modules.get("guard.windows_confine"), mod)
        # And a later resolution through the loader is the
        # same instance the gate and the spawn both consult.
        self.assertIs(REM._windows_confine(), mod)


if __name__ == "__main__":
    unittest.main()
