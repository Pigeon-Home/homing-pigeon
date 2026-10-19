"""Seams the suite walked past: job-user drop, transport cycle,
remediation close-out, agent tool rounds, and the firewall snapshot.

Nothing here talks to a mailbox, a model, or a real firewall.
"""

import json
import os
import signal
import sys
import tempfile
import types
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr


def _cfg_file(base, body):
    path = os.path.join(base, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    return path


class JobUserTest(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.skipTest("job_user is Unix-only")
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.work = os.path.join(self.base, "work", "job-1")
        os.makedirs(self.work)
        open(os.path.join(self.work, "a.sh"), "w").close()

    def tearDown(self):
        self.tmp.cleanup()

    def _face(self):
        face = mock.Mock()
        face.euid.return_value = 0
        face.getpwnam.return_value = types.SimpleNamespace(
            pw_uid=7, pw_gid=8, pw_name="jobber")
        face.walk.side_effect = os.walk
        face.realpath.side_effect = os.path.realpath
        face.dirname.side_effect = os.path.dirname
        face.stat.side_effect = os.stat
        face.chown.return_value = None
        face.chmod.return_value = None
        return face

    def _sec(self, mode="enforce"):
        sec = mock.Mock()
        sec.sec_mode.return_value = mode
        return sec

    def test_off_audit_and_a_missing_user_do_not_demote(self):
        cfg = {"security": {"job_user": {"user": "jobber"}}}
        with mock.patch.object(rr, "_security", self._sec("off")):
            self.assertIsNone(rr._job_user_preexec(
                cfg, self.base, "j", self.work))
        sec = self._sec("audit")
        with mock.patch.object(rr, "_security", sec):
            self.assertIsNone(rr._job_user_preexec(
                cfg, self.base, "j", self.work))
        sec.write_audit_entry.assert_called()
        sec.write_audit_entry.side_effect = OSError("full")
        with mock.patch.object(rr, "_security", sec):
            self.assertIsNone(rr._job_user_preexec(
                cfg, self.base, "j", self.work))
        bare = {"security": {}}
        with mock.patch.object(rr, "_security", self._sec("enforce")):
            self.assertIsNone(rr._job_user_preexec(
                bare, self.base, "j", self.work))

    def test_no_security_module_and_windows_return_none(self):
        with mock.patch.object(rr, "_security", None):
            self.assertIsNone(rr._job_user_preexec(
                {}, self.base, "j", self.work))
        with mock.patch.object(rr.os, "name", "nt"), \
                mock.patch.object(rr, "_security", self._sec()):
            self.assertIsNone(rr._job_user_preexec(
                {}, self.base, "j", self.work))

    def test_a_non_root_caller_and_an_unknown_user_fall_back(self):
        cfg = {"security": {"job_user": {"user": "jobber"}}}
        face = self._face()
        face.euid.return_value = 1000
        with mock.patch.object(rr, "_security", self._sec()):
            self.assertIsNone(rr._job_user_preexec(
                cfg, self.base, "j", self.work, face=face))
        face.euid.return_value = 0
        face.getpwnam.side_effect = KeyError("jobber")
        with mock.patch.object(rr, "_security", self._sec()):
            self.assertIsNone(rr._job_user_preexec(
                cfg, self.base, "j", self.work, face=face))

    def test_a_chown_failure_falls_back_and_a_success_demotes(self):
        cfg = {"security": {"job_user": {"user": "jobber"}}}
        face = self._face()
        face.chown.side_effect = OSError("nope")
        with mock.patch.object(rr, "_security", self._sec()):
            self.assertIsNone(rr._job_user_preexec(
                cfg, self.base, "j", self.work, face=face))
        face.chown.side_effect = None
        face.initgroups.side_effect = OSError("groups")
        with mock.patch.object(rr, "_security", self._sec()):
            fn = rr._job_user_preexec(
                cfg, self.base, "j", self.work, face=face)
        self.assertTrue(callable(fn))
        fn()
        face.setgid.assert_called_once_with(8)
        face.setuid.assert_called_once_with(7)

    def test_a_parent_that_cannot_be_stat_stops_the_walk(self):
        cfg = {"security": {"job_user": {"user": "jobber"}}}
        face = self._face()
        real_stat = os.stat

        def stat(path):
            if path == os.path.dirname(self.base):
                raise OSError("gone")
            return real_stat(path)

        face.stat.side_effect = stat
        with mock.patch.object(rr, "_security", self._sec()):
            fn = rr._job_user_preexec(
                cfg, self.base, "j", self.work, face=face)
        self.assertTrue(callable(fn))


class FinishRemediationTest(unittest.TestCase):
    def _monitor(self, outcome):
        mon = mock.Mock()
        mon.outcome = outcome
        mon._envelope_note = "note"
        return mon

    def _patch_rem(self, qdir):
        rem = rr._remediation
        return [
            mock.patch.object(rem, "received_digest", return_value="d"),
            mock.patch.object(rem, "divergence_text", return_value="storm"),
            mock.patch.object(rem, "quarantine_job", return_value=qdir),
            mock.patch.object(rem, "av_referral",
                              return_value=("clean", "ok")),
            mock.patch.object(rem, "result_member",
                              side_effect=lambda *a: {"act": a[3]}),
            mock.patch.object(rem, "enforce_quarantine_bounds"),
        ]

    def test_nothing_acted_returns_none_and_off_only_pages(self):
        mon = self._monitor({
            "divergences": [], "oracle": [], "acted": None})
        self.assertIsNone(rr._finish_remediation(
            {}, {"mode": "enforce"}, mon, {}, "j", "/w", "/b", "/w/a.sh"))
        mon.final_scan.side_effect = RuntimeError("scan")
        mon.outcome = {
            "divergences": [],
            "page": {"kind": "storm"},
            "oracle": [{"decision": "abstain",
                        "divergence": "x", "reason": "r"}],
            "acted": None,
        }
        self.assertIsNone(rr._finish_remediation(
            {}, {"mode": "off"}, mon, {}, "j", "/w", "/b", "/w/a.sh"))

    def test_a_sigkill_is_killed_and_a_tripwire_is_quarantined(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = os.path.join(tmp.name, "work")
        os.makedirs(work)
        script = os.path.join(work, "a.sh")
        open(script, "w").close()
        qdir = os.path.join(tmp.name, "q")
        os.makedirs(os.path.join(qdir, "work"))
        proc = mock.Mock(returncode=-getattr(signal, "SIGKILL", 9))
        mon = self._monitor({
            "divergences": [{"tripwire": False}],
            "oracle": [],
            "acted": {"authority": "oracle", "divergence": {"k": 1}},
            "suspects": ["out.bin"],
        })
        for p in self._patch_rem(qdir):
            p.start()
            self.addCleanup(p.stop)
        member = rr._finish_remediation(
            {}, {"mode": "enforce"}, mon, {}, "j", work, tmp.name,
            script, proc=proc)
        self.assertEqual(member, {"act": "killed"})
        mon.outcome["acted"] = None
        mon.outcome["divergences"] = [{"tripwire": True, "k": 2}]
        proc.returncode = 0
        with mock.patch.object(os.path, "relpath",
                               side_effect=ValueError("cross")):
            member = rr._finish_remediation(
                {}, {"mode": "enforce"}, mon, {}, "j", work, tmp.name,
                script, proc=proc)
        self.assertEqual(member["act"], "quarantined")

    def test_a_failed_quarantine_still_refers_the_workdir(self):
        if os.name == "nt":
            self.skipTest("quarantine path differs on Windows")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = os.path.join(tmp.name, "work")
        os.makedirs(work)
        script = os.path.join(work, "a.sh")
        open(script, "w").close()
        proc = mock.Mock(returncode=0)
        mon = self._monitor({
            "divergences": [],
            "oracle": [{"decision": "spare",
                        "divergence": "", "reason": ""}],
            "acted": {"authority": "tripwire", "divergence": {"k": 1}},
            "suspects": ["out.bin"],
        })
        for p in self._patch_rem(None):
            p.start()
            self.addCleanup(p.stop)
        member = rr._finish_remediation(
            {}, {"mode": "enforce"}, mon, {}, "j", work, tmp.name,
            script, proc=proc)
        self.assertEqual(member["act"], "quarantined")


class TransportCycleTest(unittest.TestCase):
    """The core services each enabled transport extension's channel
    (transports.service_channel); one bad channel never fails the
    others, and dry-run is handed through to the channel."""

    def test_a_failing_channel_is_isolated_from_the_others(self):
        calls = []

        def service(base_dir, name, process, log=None, dry_run=False):
            calls.append((name, dry_run))
            if name == "dead":
                raise RuntimeError("down")
            return 1

        opts = types.SimpleNamespace(dry_run=False)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "seen.json")
        with mock.patch.object(rr._transports, "service_channel",
                               side_effect=service), \
                mock.patch.object(rr, "log") as log:
            rr._service_transports(
                {}, tmp.name, {}, path,
                ["dead", "flaky", "file"], {}, {}, opts)
        self.assertEqual([n for n, _ in calls], ["dead", "flaky", "file"])
        self.assertTrue(all(d is False for _, d in calls))
        warned = " ".join(str(c.args[0]) for c in log.call_args_list)
        self.assertIn("dead transport: channel service failed", warned)
        self.assertTrue(os.path.isfile(path))

    def test_the_channel_process_hook_runs_the_mail_core(self):
        seen_process = []

        def service(base_dir, name, process, log=None, dry_run=False):
            seen_process.append(process("s", "b"))
            return 1

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(rr._transports, "service_channel",
                               side_effect=service), \
                mock.patch.object(
                    rr, "process_transport_message",
                    return_value=[("re", "body")]) as ptm:
            rr._service_transports(
                {}, tmp.name, {}, os.path.join(tmp.name, "seen.json"),
                ["file"], {}, {}, None)
        self.assertEqual(seen_process, [[("re", "body")]])
        ptm.assert_called_once()

    def test_dry_run_is_handed_to_the_channel_and_seen_is_capped(self):
        opts = types.SimpleNamespace(dry_run=True)
        seen = {str(i): 1 for i in range(rr.SEEN_CAP + 3)}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "seen.json")
        with mock.patch.object(rr._transports, "service_channel",
                               return_value=0) as svc:
            rr._service_transports(
                {}, tmp.name, seen, path, ["file"], {}, {}, opts)
        self.assertTrue(svc.call_args.kwargs["dry_run"])
        self.assertEqual(len(seen), rr.SEEN_CAP)
        self.assertTrue(os.path.isfile(path))


class AgentRoundTest(unittest.TestCase):
    def _cfg(self):
        return {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
                "timeout_sec": 5, "agent_wall_clock_sec": 30}

    def test_a_wire_tool_call_then_an_answer(self):
        calls = [
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "c1",
                "function": {"name": "read_file",
                             "arguments": "{\"path\": \"a\"}"},
            }]},
            {"role": "assistant", "content": "all quiet"},
        ]
        with mock.patch.object(rr, "_inference_chat", side_effect=calls), \
                mock.patch.object(rr, "_run_oracle_tool",
                                  return_value="hi"):
            ans = rr.ask_model_agent(self._cfg(), "status?", "out", 200)
        self.assertEqual(ans.get("answer"), "all quiet")
        self.assertEqual(ans.get("tool_rounds"), 1)

    def test_a_content_embedded_call_is_replayed_as_chat(self):
        calls = [
            {"role": "assistant", "content":
                '{"name": "list_dir", "parameters": {"path": "."}}'},
            {"role": "assistant", "content": "listed"},
        ]
        seen = []

        def chat(cfg, messages, tools, opener, timeout):
            seen.append(list(messages))
            return calls.pop(0)

        with mock.patch.object(rr, "_inference_chat", side_effect=chat), \
                mock.patch.object(rr, "_run_oracle_tool", return_value=""):
            ans = rr.ask_model_agent(self._cfg(), "list it", "", 200)
        self.assertEqual(ans.get("answer"), "listed")
        roles = [m.get("role") for m in seen[-1]]
        self.assertIn("user", roles)
        self.assertNotIn("tool", roles)

    def test_an_action_that_comes_back_as_prose_is_reasked_once(self):
        calls = [
            {"role": "assistant", "content": "I would delete it"},
            {"role": "assistant", "content": "blocked: no path"},
        ]
        with mock.patch.object(rr, "_inference_chat", side_effect=calls):
            ans = rr.ask_model_agent(
                self._cfg(), "delete the leftover", "", 200)
        self.assertIn("blocked", ans.get("answer") or "")

    def test_a_broken_model_and_a_non_dict_reply_are_inference_errors(self):
        with mock.patch.object(
                rr, "_inference_chat",
                return_value={"role": "error", "content": ""}):
            ans = rr.ask_model_agent(self._cfg(), "q", "", 200)
        self.assertEqual(ans["rejected"], "inference_error")
        self.assertIn("did not answer", ans["detail"])
        with mock.patch.object(rr, "_inference_chat", return_value="nope"):
            ans = rr.ask_model_agent(self._cfg(), "q", "", 200)
        self.assertEqual(ans["rejected"], "inference_error")

    def test_the_wall_clock_forces_a_final_answer(self):
        cfg = self._cfg()
        cfg["agent_wall_clock_sec"] = 1
        calls = [
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "c1",
                "function": {"name": "run",
                             "arguments": {"command": "true"}},
            }]},
            {"role": "error", "content": "cold"},
        ]
        times = iter([0.0, 100.0])
        with mock.patch.object(rr.time, "monotonic",
                               side_effect=lambda: next(times)), \
                mock.patch.object(rr, "_inference_chat",
                                  side_effect=calls), \
                mock.patch.object(rr, "_run_oracle_tool",
                                  return_value="ok"):
            ans = rr.ask_model_agent(cfg, "look", "", 200)
        self.assertEqual(ans["rejected"], "inference_error")
        self.assertEqual(ans["detail"], "cold")

    def test_the_round_budget_rejects_a_model_that_never_answers(self):
        tool = {"role": "assistant", "content": "", "tool_calls": [{
            "id": "c1",
            "function": {"name": "run",
                         "arguments": {"command": "true"}},
        }]}
        with mock.patch.object(rr, "_inference_chat", return_value=tool), \
                mock.patch.object(rr, "_run_oracle_tool",
                                  return_value="ok"):
            ans = rr.ask_model_agent(self._cfg(), "look", "", 200)
        self.assertEqual(ans["rejected"], "tool_budget")

    def test_junk_tool_calls_are_skipped_and_a_note_is_logged(self):
        msg = {"tool_calls": [
            "nope",
            {"function": "nope"},
            {"id": "", "function": {"name": 3, "arguments": "[1]"}},
            {"function": {"name": "read_file", "arguments": "{"}},
        ], "content": "plain"}
        out = rr._parse_tool_calls(msg)
        self.assertTrue(out)
        self.assertEqual(out[0][1], "")
        note = rr._unparsed_tool_note(
            '{"name": "read_file", "arguments": nope}')
        self.assertIn("read_file", note)
        self.assertEqual(rr._unparsed_tool_note("plain answer"), "")

    def test_trim_drops_the_oldest_tool_pair(self):
        huge = "x" * (rr._ORACLE_AGENT_CONTEXT_CHARS + 10)
        messages = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": huge},
            {"role": "tool", "content": "r"},
            {"role": "assistant", "content": "later"},
            {"role": "user", "content": "more"},
        ]
        trimmed = rr._agent_trim(messages)
        self.assertNotIn(huge, [m.get("content") for m in trimmed])
        self.assertEqual(rr._agent_trim(messages[:3]), messages[:3])


class ChatAndPolicyTest(unittest.TestCase):
    def test_recent_chat_keeps_asks_and_drops_junk(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "oracle-chat.jsonl")
        rows = [
            "not json",
            json.dumps({"event": "open"}),
            json.dumps({"event": "ask", "question": "", "answer": ""}),
            json.dumps({"event": "ask", "question": "q1", "answer": 3}),
            json.dumps({"event": "ask", "question": "q2", "answer": "a2"}),
        ]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
        text = rr.recent_chat(tmp.name, turns=2, max_chars=20)
        self.assertIn("q2", text)
        self.assertEqual(rr.recent_chat(tmp.name, turns=0), "")
        self.assertIn("q2", rr.recent_chat(tmp.name, turns="nope"))
        self.assertEqual(rr.recent_chat(tmp.name, max_chars=0), "")
        self.assertEqual(rr.recent_chat("/no/such", turns=1), "")
        self.assertEqual(rr.recent_chat(None), "")

    def test_a_bad_args_pattern_is_a_config_error(self):
        with self.assertRaises(RuntimeError):
            rr.build_key_policies({"key_policies": {"k": {
                "args_pattern": ""}}})
        with self.assertRaises(RuntimeError):
            rr.build_key_policies({"key_policies": {"k": {
                "args_pattern": "("}}})
        real = rr.time.time
        calls = {"n": 0}

        def clock():
            calls["n"] += 1
            if calls["n"] == 1:
                return 0.0
            if calls["n"] == 2:
                return 5.0
            return real()

        with mock.patch.object(rr.time, "time", side_effect=clock):
            with self.assertRaises(RuntimeError) as ctx:
                rr.build_key_policies({"key_policies": {"k": {
                    "args_pattern": "a+"}}})
        self.assertIn("backtrack", str(ctx.exception))

    def test_tool_paths_refuse_a_null_and_accept_no_base(self):
        self.assertFalse(rr._tool_stays_inside("a\x00b", "/tmp"))
        self.assertTrue(rr._tool_stays_inside("/etc/hostname", ""))
        with mock.patch.object(rr.os.path, "realpath",
                               side_effect=OSError("loop")):
            self.assertFalse(rr._tool_stays_inside("a", "/tmp"))
        self.assertEqual(rr._bundled_doc_path(""), "")
        self.assertTrue(rr._bundled_doc_path("PROTOCOL.md").endswith(
            "PROTOCOL.md"))
        docs = tempfile.TemporaryDirectory()
        self.addCleanup(docs.cleanup)
        bundled = os.path.join(docs.name, "pigeon-docs")
        os.makedirs(bundled)
        open(os.path.join(bundled, "NOTE.md"), "w").close()
        with mock.patch.object(rr.sys, "frozen", True, create=True), \
                mock.patch.object(rr.sys, "_MEIPASS", docs.name,
                                  create=True):
            found = rr._bundled_doc_path("NOTE.md")
            self.assertTrue(found.endswith(
                os.path.join("pigeon-docs", "NOTE.md")))
            self.assertEqual(rr._bundled_doc_path("missing-doc.md"), "")

    def test_read_and_write_and_run_failures_stay_strings(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        open(os.path.join(tmp.name, "a.txt"), "w").close()
        os.mkdir(os.path.join(tmp.name, "sub"))
        with mock.patch.object(rr.os.path, "isdir", side_effect=OSError):
            listed = rr._run_oracle_tool(
                "list_dir", {"path": "."}, tmp.name)
        self.assertIn("a.txt", listed)
        self.assertNotIn("sub/", listed)
        with mock.patch.object(rr.os, "open", side_effect=OSError("ro")):
            wrote = rr._run_oracle_tool(
                "write_file", {"path": "b.txt", "content": "z"},
                tmp.name)
        self.assertTrue(wrote.startswith("error: cannot write"))
        with mock.patch.object(
                rr.subprocess, "run",
                side_effect=rr.subprocess.TimeoutExpired("cmd", 1)):
            timed = rr._run_oracle_tool(
                "run", {"command": "sleep 9", "timeout_sec": True},
                tmp.name)
        self.assertIn("timed out", timed)
        with mock.patch.object(rr.subprocess, "run",
                               side_effect=OSError("no")):
            ran = rr._run_oracle_tool(
                "run", {"command": "true"}, tmp.name)
        self.assertTrue(ran.startswith("error: cannot run"))

    def test_release_without_the_module_is_an_error(self):
        from runner import setup
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = _cfg_file(tmp.name, {
            "shared_secret": "x" * 32, "base_dir": tmp.name})
        with mock.patch.object(setup, "is_tty", return_value=False), \
                mock.patch.object(rr, "_remediation", None), \
                mock.patch.object(sys, "argv", [
                    "runner", "--config", path,
                    "--remediation-release", "job-1"]):
            code = rr.main()
        self.assertEqual(code, 2)


class PostureParseTest(unittest.TestCase):
    def test_netsh_ufw_iptables_and_macos_parsers(self):
        self.assertIsNone(rr._parse_netsh_profiles(""))
        self.assertIsNone(rr._parse_netsh_profiles("no profiles"))
        text = ("Domain Profile Settings:\n"
                "State                         ON\n"
                "Private Profile Settings:\n"
                "State                         OFF\n")
        got = rr._parse_netsh_profiles(text)
        self.assertIn("Domain=ON", got)
        self.assertIn("T1562.004", got)
        self.assertEqual(rr._parse_ufw("Status: active"),
                         "firewall: linux ufw=active")
        self.assertIn("inactive", rr._parse_ufw("Status: inactive"))
        self.assertIsNone(rr._parse_ufw(3))
        self.assertIsNone(rr._parse_iptables_policy(""))
        self.assertIsNone(rr._parse_iptables_policy("-A INPUT -j ACCEPT"))
        drop = rr._parse_iptables_policy("-P INPUT DROP\n-P OUTPUT ACCEPT")
        self.assertNotIn("T1562.004", drop)
        open_pol = rr._parse_iptables_policy("-P INPUT ACCEPT")
        self.assertIn("T1562.004", open_pol)
        self.assertIn("off", rr._parse_socketfilterfw("State = 0"))
        self.assertIn(
            "=on", rr._parse_socketfilterfw("Firewall is enabled"))
        self.assertIsNone(rr._parse_socketfilterfw("huh"))
        self.assertIsNone(rr._parse_defender_query("no state here"))
        self.assertIn("running", rr._parse_defender_query(
            "STATE              : 4  RUNNING"))
        self.assertIn("T1562.001", rr._parse_defender_query(
            "STATE              : 1  STOPPED"))

    def test_firewall_and_av_watches_baseline_then_change(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(
                rr, "_firewall_posture",
                return_value="firewall: linux ufw=active"):
            first = rr._firewall_watch(tmp.name)
            second = rr._firewall_watch(tmp.name)
            bare = rr._firewall_watch("")
        self.assertIn("baseline", first)
        self.assertNotIn("changed", second)
        self.assertEqual(bare, "firewall: linux ufw=active")
        with mock.patch.object(
                rr, "_firewall_posture",
                return_value="firewall: linux ufw=inactive [T1562.004]"), \
                mock.patch.object(rr, "_file_watch_alert"):
            changed = rr._firewall_watch(tmp.name)
        self.assertIn("changed", changed)
        with mock.patch.object(rr, "_firewall_posture", return_value=None):
            self.assertIsNone(rr._firewall_watch(tmp.name))
        with mock.patch.object(
                rr, "_av_posture",
                return_value="av: clamav signatures current"):
            base = rr._av_watch(tmp.name)
            same = rr._av_watch(tmp.name)
        self.assertIn("baseline", base)
        self.assertNotIn("changed", same)
        stale = "av: clamav signatures stale (9d) [T1562.001]"
        with mock.patch.object(rr, "_av_posture", return_value=stale), \
                mock.patch.object(rr, "_file_watch_alert"):
            flipped = rr._av_watch(tmp.name)
            self.assertEqual(rr._av_watch(None), stale)
        self.assertIn("changed", flipped)

    def test_a_command_that_fails_is_none_and_a_symlink_posture_is_ignored(self):
        with mock.patch.object(rr.subprocess, "run",
                               side_effect=OSError("no")):
            self.assertIsNone(rr._run_text(["true"]))
        proc = mock.Mock(returncode=1, stdout="x")
        with mock.patch.object(rr.subprocess, "run", return_value=proc):
            self.assertIsNone(rr._run_text(["true"]))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        link = os.path.join(tmp.name, "link")
        os.symlink(os.path.join(tmp.name, "nope"), link)
        self.assertIsNone(rr._read_posture_line(link))
        junk = os.path.join(tmp.name, "j.json")
        with open(junk, "w", encoding="utf-8") as fh:
            fh.write("{")
        self.assertIsNone(rr._read_posture_line(junk))
        plain = os.path.join(tmp.name, "p.json")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write('{"other": 1}')
        self.assertIsNone(rr._read_posture_line(plain))


if __name__ == "__main__":
    unittest.main()
