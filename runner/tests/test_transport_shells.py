"""Unit tests for the transport shells the coverage report left open.

The extension programs and the channel helper fail on framing
and process edges, not on cryptography. A live broker or a
live socket is the wrong test for those edges.
"""

import os
import string
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.wire import transports  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.file.__main__ import FilePipe  # noqa: E402


class ChannelHelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-chan-")

    def test_parse_envelope_rejects_a_missing_blank_line(self):
        self.assertIsNone(ch.parse_envelope("just a subject"))
        self.assertIsNone(ch.parse_envelope(""))
        self.assertEqual(ch.parse_envelope("Sub\r\n\r\nbody"),
                         ("Sub", "body"))

    def test_env_wins_over_argv_and_a_bad_file_is_empty(self):
        bad = os.path.join(self.tmp, "nope.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{")
        channel, cfg = ch.load_runtime_config(
            ["prog", "/from-argv", bad])
        self.assertEqual(channel, "/from-argv")
        self.assertEqual(cfg, {})
        os.environ["HOMING_PIGEON_TRANSPORT_CHANNEL"] = "/from-env"
        os.environ["HOMING_PIGEON_TRANSPORT_CONFIG"] = bad
        try:
            channel, cfg = ch.load_runtime_config(
                ["prog", "/from-argv", "/other.json"])
        finally:
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CHANNEL", None)
            os.environ.pop("HOMING_PIGEON_TRANSPORT_CONFIG", None)
        self.assertEqual(channel, "/from-env")
        self.assertEqual(cfg, {})

    def test_deliver_job_sanitizes_the_ident(self):
        path = ch.deliver_job(self.tmp, "../Job id!", "Sub", "body")
        self.assertTrue(path.endswith(".._Job_id_.job.txt")
                        or os.path.basename(path).startswith(".._Job"))
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("Sub\n\nbody"))

    def test_pending_results_skips_the_junk(self):
        out = ch.dirs(self.tmp)["outbox"]
        os.makedirs(os.path.join(out, "a-dir"))
        with open(os.path.join(out, "plain"), "w",
                  encoding="utf-8") as f:
            f.write("no blank line here")
        with open(os.path.join(out, "bad.result.txt"), "w",
                  encoding="utf-8") as f:
            f.write("no blank line here")
        with open(os.path.join(out, "good.result.txt"), "w",
                  encoding="utf-8") as f:
            f.write("Sub\n\nbody\n")
        over = os.path.join(out, "big.result.txt")
        with open(over, "wb") as f:
            f.write(b"x" * (ch.FILE_MAX_BYTES + 1))
        try:
            os.symlink(over, os.path.join(out, "link.result.txt"))
        except OSError:
            pass
        found = ch.pending_results(self.tmp)
        names = [row[0] for row in found]
        self.assertEqual(names, ["good.result.txt"])
        self.assertEqual(found[0][1], "Sub")
        # Not a result name: a sidecar-shaped file stays.
        self.assertTrue(os.path.isfile(os.path.join(out, "plain")))
        # A result name that cannot be posted is set aside, or the
        # queue acks the job and the output is gone.
        failed = os.path.join(out, "failed")
        self.assertIn("bad.result.txt", os.listdir(failed))
        self.assertIn("bad.refused.txt", os.listdir(failed))
        self.assertFalse(os.path.exists(
            os.path.join(out, "bad.result.txt")))
        failed = os.path.join(out, "failed")
        self.assertIn("big.result.txt", os.listdir(failed))
        self.assertTrue(any(n.endswith(".refused.txt")
                            for n in os.listdir(failed)))

    def test_ack_of_a_missing_file_does_not_raise(self):
        ch.ack_result(self.tmp, "never-written.result.txt")

    def test_poll_interval_clamps_and_rejects_garbage(self):
        self.assertEqual(ch.poll_interval({}), 2.0)
        self.assertEqual(ch.poll_interval(
            {"extension_poll_interval_sec": 0}), 0.2)
        self.assertEqual(ch.poll_interval(
            {"extension_poll_interval_sec": 1000}), 60.0)
        self.assertEqual(ch.poll_interval(
            {"extension_poll_interval_sec": "nope"}), 2.0)


class ChannelServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-svc-")

    def _drop(self, name, text):
        inbox = transports.ensure_channel_dirs(self.tmp, "file")["inbox"]
        with open(os.path.join(inbox, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_one_bad_message_does_not_stop_the_next(self):
        self._drop("a.job.txt", "Subj A\n\nbody-a\n")
        self._drop("b.job.txt", "Subj B\n\nbody-b\n")
        seen = []

        def process(subject, body):
            seen.append(subject)
            if subject.endswith("A"):
                raise RuntimeError("boom")
            return [("Result B", "ok")]

        n = transports.service_channel(
            self.tmp, "file", process, dry_run=False)
        self.assertEqual(n, 2)
        self.assertEqual(seen, ["Subj A", "Subj B"])
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        self.assertEqual(os.listdir(inbox), ["done"])
        outbox = transports.channel_paths(self.tmp, "file")["outbox"]
        results = [f for f in os.listdir(outbox) if f != "done"]
        self.assertEqual(len(results), 1)

    def test_consume_false_leaves_the_file(self):
        self._drop("retry.job.txt", "Subj R\n\nbody-r\n")

        class Batch(list):
            def __init__(self):
                super().__init__([])
                self.consume = False
                self.rolled = False

            def rollback(self):
                self.rolled = True

        batch = Batch()
        n = transports.service_channel(
            self.tmp, "file", lambda s, b: batch, dry_run=False)
        self.assertEqual(n, 1)
        self.assertTrue(batch.rolled)
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        self.assertIn("retry.job.txt", os.listdir(inbox))
        self.assertEqual(
            os.listdir(os.path.join(inbox, "done")), [])

    def test_a_reply_that_does_not_land_is_not_consumed(self):
        self._drop("j.job.txt", "Subj\n\nbody\n")

        class Batch(list):
            def __init__(self):
                super().__init__([("Result", "body", None)])
                self.consume = True
                self.rolled = False

            def rollback(self):
                self.rolled = True

        batch = Batch()
        with mock.patch.object(
                transports, "write_channel_result",
                side_effect=OSError("disk full")):
            transports.service_channel(
                self.tmp, "file", lambda s, b: batch, dry_run=False)
        self.assertTrue(batch.rolled)
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        self.assertIn("j.job.txt", os.listdir(inbox))

    def test_a_file_replaced_after_the_read_is_not_acked(self):
        self._drop("j.job.txt", "Subj\n\nbody-old\n")
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        path = os.path.join(inbox, "j.job.txt")

        def process(subject, body):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Subj\n\nbody-new\n")
            return [("Result", "ok")]

        transports.service_channel(
            self.tmp, "file", process, dry_run=False)
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as fh:
            self.assertIn("body-new", fh.read())
        self.assertEqual(os.listdir(os.path.join(inbox, "done")), [])

    def test_dry_run_acks_nothing(self):
        self._drop("a.job.txt", "Subj\n\nbody\n")
        transports.service_channel(
            self.tmp, "file", lambda s, b: [], dry_run=True)
        inbox = transports.channel_paths(self.tmp, "file")["inbox"]
        self.assertIn("a.job.txt", os.listdir(inbox))

    def test_a_second_result_for_the_same_job_gets_a_suffix(self):
        first = transports.write_channel_result(
            self.tmp, "file", "[HOMING-PIGEON] job j1",
            "[HOMING-PIGEON] result j1", "one")
        second = transports.write_channel_result(
            self.tmp, "file", "[HOMING-PIGEON] job j1",
            "[HOMING-PIGEON] result j1", "two")
        self.assertTrue(first.endswith("j1.result.txt"))
        self.assertTrue(second.endswith("j1.result-2.txt"))

    def test_a_second_result_keeps_the_ident_on_the_sidecar(self):
        transports.write_channel_result(
            self.tmp, "file", "[HOMING-PIGEON] job j1",
            "[HOMING-PIGEON] result j1", "one",
            target="ops@example.com")
        transports.write_channel_result(
            self.tmp, "file", "[HOMING-PIGEON] job j1",
            "[HOMING-PIGEON] result j1", "two",
            target="ops@example.com")
        outbox = transports.channel_paths(self.tmp, "file")["outbox"]
        names = set(os.listdir(outbox))
        self.assertIn("j1.target.txt", names)
        self.assertNotIn("j1.result-2.txt.target.txt", names)


class FilePipeEdgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-file-")
        self.cfg = {
            "base_dir": self.tmp,
            "inbox_dir": "watched-in",
            "outbox_dir": "watched-out",
        }
        self.channel = os.path.join(self.tmp, "channel")
        self.pipe = FilePipe(self.cfg, self.channel)

    def test_a_directory_and_a_redelivery_are_not_offered(self):
        os.makedirs(os.path.join(self.pipe.inbox, "nested"))
        seen = os.path.join(self.pipe.done, "job-1.job-seen")
        with open(seen, "w", encoding="utf-8") as f:
            f.write("old\n")
        name = "again.txt"
        with open(os.path.join(self.pipe.inbox, name), "w",
                  encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] job job-1\n\nbody\n")
        self.pipe.scan_jobs()
        self.assertEqual(self.pipe._pending, {})
        self.assertTrue(os.path.exists(
            os.path.join(self.pipe.done, name)))

    def test_a_result_name_collision_is_suffixed(self):
        os.makedirs(self.pipe.outbox, exist_ok=True)
        taken = os.path.join(self.pipe.outbox, "job-9.result.txt")
        with open(taken, "w", encoding="utf-8") as f:
            f.write("old\n")
        ch.deliver_job(self.channel, "stem",
                       "[HOMING-PIGEON] job job-9", "body")
        self.pipe._pending["stem"] = ("watched.txt", "job-9")
        # The runner's result arrives under the channel ident.
        outbox = ch.dirs(self.channel)["outbox"]
        with open(os.path.join(outbox, "stem.result.txt"), "w",
                  encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] result job-9\n\nok\n")
        self.pipe.scan_results()
        self.assertTrue(os.path.exists(os.path.join(
            self.pipe.outbox, "job-9.result-2.txt")))
        self.assertNotIn("stem", self.pipe._pending)

    def test_a_suffixed_channel_result_consumes_the_watched_job(self):
        # stem.result-2.txt does not end in .result.txt. The pipe
        # used the whole filename, missed the job it had delivered,
        # and left the watched file to be run again.
        watched = os.path.join(self.pipe.inbox, "watched.txt")
        with open(watched, "w", encoding="utf-8") as f:
            f.write("job\n")
        self.pipe._pending["stem"] = ("watched.txt", "job-9")
        outbox = ch.dirs(self.channel)["outbox"]
        with open(os.path.join(outbox, "stem.result-2.txt"), "w",
                  encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] result job-9\n\nok\n")
        self.pipe.scan_results()
        self.assertNotIn("stem", self.pipe._pending)
        self.assertFalse(os.path.exists(watched))
        self.assertTrue(os.path.exists(
            os.path.join(self.pipe.done, "watched.txt")))

    def test_a_rejected_job_is_consumed_from_inbox_done(self):
        watched = os.path.join(self.pipe.inbox, "w.txt")
        with open(watched, "w", encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] job job-3\n\nbody\n")
        self.pipe.scan_jobs()
        self.assertIn("w", self.pipe._pending)
        done = os.path.join(self.channel, "inbox", "done")
        os.makedirs(done, exist_ok=True)
        open(os.path.join(done, "w.job.txt"), "w").close()
        self.pipe.scan_results()
        self.assertNotIn("w", self.pipe._pending)
        self.assertTrue(os.path.exists(
            os.path.join(self.pipe.done, "job-3.job-seen")))

    def test_a_result_still_set_aside_does_not_finish_the_watched_job(self):
        # The core had consumed the job, and the result was
        # waiting in failed/ for a stub. The watched file was
        # moved to done and marked seen, with nothing in the
        # outbox for the SI to pick up.
        watched = os.path.join(self.pipe.inbox, "w.txt")
        with open(watched, "w", encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] job job-3\n\nbody\n")
        self.pipe.scan_jobs()
        done = os.path.join(self.channel, "inbox", "done")
        os.makedirs(done, exist_ok=True)
        open(os.path.join(done, "w.job.txt"), "w").close()
        failed = os.path.join(self.channel, "outbox", "failed")
        os.makedirs(failed, exist_ok=True)
        with open(os.path.join(failed, "w.result.txt"), "w",
                  encoding="utf-8") as f:
            f.write("not an envelope")
        with open(os.path.join(failed, "w.refused.txt"), "w",
                  encoding="utf-8") as f:
            f.write("not an envelope\n")
        self.pipe.scan_results()
        self.assertIn("w", self.pipe._pending)
        self.assertTrue(os.path.exists(watched))
        self.assertFalse(os.path.exists(
            os.path.join(self.pipe.done, "job-3.job-seen")))
        self.assertEqual(os.listdir(self.pipe.outbox), [])

    def test_a_file_that_cannot_be_read_is_refused(self):
        inbox = self.pipe.inbox
        done = self.pipe.done
        with open(os.path.join(inbox, "binary.txt"), "wb") as f:
            f.write(b"\xff\xfe not text")
        self.pipe.scan_jobs()
        note = os.path.join(done, "binary.txt.refused.txt")
        with open(note, encoding="utf-8") as f:
            self.assertIn("cannot read as UTF-8", f.read())

        with open(os.path.join(inbox, "huge.txt"), "wb") as f:
            f.write(b"x" * (ch.FILE_MAX_BYTES + 1))
        # oversize is already covered elsewhere if the note exists;
        # this one is the stat failure, which needs the name to
        # vanish between the listing and the stat.
        with open(os.path.join(inbox, "gone.txt"), "w",
                  encoding="utf-8") as f:
            f.write("x")
        real = os.path.getsize

        def boom(path):
            if str(path).endswith("gone.txt"):
                raise OSError("gone")
            return real(path)

        with mock.patch("os.path.getsize", boom):
            self.pipe.scan_jobs()
        with open(os.path.join(done, "gone.txt.refused.txt"),
                  encoding="utf-8") as f:
            self.assertIn("cannot stat", f.read())

    def test_a_refusal_that_cannot_be_written_down_still_moves(self):
        name = "bad.txt"
        with open(os.path.join(self.pipe.inbox, name), "w",
                  encoding="utf-8") as f:
            f.write("no blank line here")
        os.makedirs(os.path.join(self.pipe.done, name + ".refused.txt"))
        self.pipe.scan_jobs()
        self.assertTrue(os.path.isfile(
            os.path.join(self.pipe.done, name)))
        self.assertTrue(os.path.isdir(
            os.path.join(self.pipe.done, name + ".refused.txt")))

    def test_a_refusal_that_cannot_move_the_file_leaves_it(self):
        name = "stuck.txt"
        with open(os.path.join(self.pipe.inbox, name), "w",
                  encoding="utf-8") as f:
            f.write("no blank line here")
        os.makedirs(os.path.join(self.pipe.done, name))
        self.pipe.scan_jobs()
        self.assertTrue(os.path.isfile(
            os.path.join(self.pipe.inbox, name)))

    def test_a_result_without_a_newline_gets_one(self):
        outbox = ch.dirs(self.channel)["outbox"]
        with open(os.path.join(outbox, "stem.result.txt"), "w",
                  encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] result job-4\n\nok")
        self.pipe.scan_results()
        written = os.path.join(self.pipe.outbox, "job-4.result.txt")
        with open(written, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.endswith("\n"))
        self.assertIn("ok\n", text)

    def test_a_seen_mark_that_cannot_be_written_is_not_fatal(self):
        watched = os.path.join(self.pipe.inbox, "w.txt")
        with open(watched, "w", encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] job job-3\n\nbody\n")
        self.pipe.scan_jobs()
        os.makedirs(os.path.join(self.pipe.done, "job-3.job-seen"))
        done = os.path.join(self.channel, "inbox", "done")
        os.makedirs(done, exist_ok=True)
        open(os.path.join(done, "w.job.txt"), "w").close()
        self.pipe.scan_results()
        self.assertNotIn("w", self.pipe._pending)
        self.assertTrue(os.path.isdir(
            os.path.join(self.pipe.done, "job-3.job-seen")))

    def test_main_refuses_no_channel_and_survives_a_bad_pass(self):
        import json
        from runner.transport_extensions.file.__main__ import main
        self.assertEqual(main(["file-transport"]), 2)
        cfg_path = os.path.join(self.tmp, "runtime.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({
                "base_dir": self.tmp,
                "inbox_dir": "watched-in",
                "outbox_dir": "watched-out",
            }, f)

        def nap(_interval):
            raise SystemExit("slept")

        def explode(_self):
            raise RuntimeError("disk")

        with mock.patch(
                "runner.transport_extensions.channel.nap", nap), \
                mock.patch.object(FilePipe, "scan_jobs", explode):
            with self.assertRaises(SystemExit):
                main(["file-transport", self.channel, cfg_path])


class SupervisorStartFailureTest(unittest.TestCase):
    def test_one_popen_failure_leaves_the_other_started(self):
        tmp = tempfile.mkdtemp(prefix="hp-sup-")
        cfg = {"transports": ["file", "nats"],
               "shared_secret": "x" * 32}
        started = []

        class Proc:
            pid = 41

            def poll(self):
                return None

            def terminate(self):
                return None

            def kill(self):
                return None

        def popen(argv, **kw):
            if any("nats" in str(part) for part in argv):
                raise OSError("nats binary missing")
            started.append(argv)
            return Proc()

        lines = []
        sup = transports.TransportSupervisor(
            cfg, tmp, log=lambda m, level="INFO": lines.append(
                (level, m)), popen=popen)
        sup.start()
        self.assertEqual(len(started), 1)
        self.assertTrue(any(level == "ERROR" and "nats" in msg
                            for level, msg in lines))
        self.assertIn("file", sup.processes)
        self.assertIsNotNone(sup.processes["file"]["proc"])
        self.assertIsNone(sup.processes["nats"]["proc"])
        sup.stop()


class FileMainLoopLegTest(unittest.TestCase):
    """Queue A refill: the file transport's
    main loop pass (coverage run 40189711740:
    __main__.py line 213). One pass scans jobs
    AND results before it naps -- a results
    scan that never ran would strand finished
    work in the channel. The nap is cut short
    by an interrupt, which is how the loop is
    stopped here.
    """

    def test_one_pass_scans_jobs_and_results(self):
        from runner.transport_extensions.file import (
            __main__ as file_main)
        with tempfile.TemporaryDirectory() as d:
            channel_dir = os.path.join(d, "channel")
            os.makedirs(channel_dir)
            cfg = {"base_dir": d}
            with mock.patch.object(
                    ch, "load_runtime_config",
                    return_value=(channel_dir, cfg)), \
                    mock.patch.object(
                        ch, "nap",
                        side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    file_main.main([])
            self.assertTrue(os.path.isdir(
                os.path.join(d, "transport-file", "inbox")))
            self.assertTrue(os.path.isdir(
                os.path.join(d, "transport-file", "outbox")))

    def test_a_failed_pass_is_logged_not_fatal(self):
        from runner.transport_extensions.file import (
            __main__ as file_main)
        with tempfile.TemporaryDirectory() as d:
            channel_dir = os.path.join(d, "channel")
            os.makedirs(channel_dir)
            cfg = {"base_dir": d}
            with mock.patch.object(
                    ch, "load_runtime_config",
                    return_value=(channel_dir, cfg)), \
                    mock.patch.object(
                        file_main.FilePipe, "scan_jobs",
                        side_effect=RuntimeError("wedged")), \
                    mock.patch.object(
                        ch, "nap",
                        side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    file_main.main([])


class MailboxDefaultLogLegTest(unittest.TestCase):
    """Queue A refill: the mailbox module's
    own log line (coverage run 40189711740:
    mailbox.py line 41). Before any transport
    installs its logger, the default writes
    the level and the message to stderr --
    the relay every later logger replaces.
    """

    def test_the_default_log_writes_to_stderr(self):
        import importlib
        import io
        from contextlib import redirect_stderr
        from runner.wire import mailbox
        saved = mailbox.log
        importlib.reload(mailbox)
        try:
            err = io.StringIO()
            with redirect_stderr(err):
                mailbox.log("hello")
                mailbox.log("careful", "WARN")
            self.assertIn("INFO: hello", err.getvalue())
            self.assertIn("WARN: careful", err.getvalue())
        finally:
            mailbox.log = saved


class NatsMainLegsTest(unittest.TestCase):
    # Queue A refill: nats/__main__.py::main's three exits -- no
    # channel directory, a pipe that refuses to start, and the
    # happy path that runs the pipe and answers 0.
    def test_main_refuses_without_a_channel_directory(self):
        from runner.transport_extensions.nats import __main__ as nats
        self.assertEqual(nats.main(["nats-transport"]), 2)

    def test_main_refuses_when_the_pipe_cannot_start(self):
        from runner.transport_extensions.nats import __main__ as nats

        def refuse(_cfg, _channel_dir):
            raise nats.TransportError("no credentials configured")

        with mock.patch.object(
                ch, "load_runtime_config",
                return_value=("/chan", {})), \
                mock.patch.object(nats, "NatsPipe", refuse):
            self.assertEqual(nats.main(["nats-transport"]), 2)

    def test_main_runs_the_pipe_and_answers_zero(self):
        from runner.transport_extensions.nats import __main__ as nats
        ran = []

        class FakePipe:
            def __init__(self, cfg, channel_dir):
                ran.append((cfg, channel_dir))

            def run(self):
                ran.append("ran")

        with mock.patch.object(
                ch, "load_runtime_config",
                return_value=("/chan", {"transport_nats": {}})), \
                mock.patch.object(nats, "NatsPipe", FakePipe):
            self.assertEqual(nats.main(["nats-transport"]), 0)
        self.assertEqual(
            ran, [({"transport_nats": {}}, "/chan"), "ran"])


class DtlsMainRefusalLegsTest(unittest.TestCase):
    # Queue A refill: dtls/__main__.py::main's refusal legs -- no
    # shared secret handed over, a PSK under the entropy floor,
    # and the bad-greeting-tier warning that proceeds at the
    # default tier.
    STRONG = "9f2e7ab41c08d3f5a6b94e0271c8d5f03a6b94e0271c8d5f0"

    def _main_with(self, cfg, pipe=None):
        from runner.transport_extensions.dtls import __main__ as dtls
        patches = [mock.patch.object(
            ch, "load_runtime_config", return_value=("/chan", cfg))]
        if pipe is not None:
            patches.append(mock.patch.object(dtls, "DtlsPipe", pipe))
        for p in patches:
            p.start()
        try:
            return dtls.main(["dtls-transport"])
        finally:
            for p in patches:
                p.stop()

    def test_main_refuses_without_a_shared_secret(self):
        self.assertEqual(self._main_with({}), 2)

    def test_main_refuses_a_psk_under_the_floor(self):
        self.assertEqual(
            self._main_with({"shared_secret": "abc"}), 2)

    def test_main_refuses_when_the_pipe_cannot_listen(self):
        from runner.transport_extensions.dtls import __main__ as dtls

        def refuse(_cfg, _channel_dir):
            raise RuntimeError("udp 20220 is already bound")

        self.assertEqual(
            self._main_with({"shared_secret": self.STRONG}, refuse), 2)

    def test_a_bad_greeting_tier_warns_and_proceeds(self):
        from runner.transport_extensions.dtls import __main__ as dtls
        logged = []

        class FakePipe:
            bind = "127.0.0.1"
            port = 20220

            def __init__(self, cfg, channel_dir):
                pass

            def run_once(self):
                raise SystemExit("one pass is enough")

        with mock.patch.object(
                ch, "log",
                lambda msg, level="INFO": logged.append((level, msg))):
            with self.assertRaises(SystemExit):
                self._main_with(
                    {"shared_secret": self.STRONG,
                     "dtls_greeting": "bogus"}, FakePipe)
        warns = [m for level, m in logged if level == "WARN"]
        self.assertTrue(
            any("dtls_greeting" in m and "family" in m for m in warns),
            logged)


class FilePipeHeldResultShotgunTest(unittest.TestCase):
    """Shotgun family for the 31-Oct result-stays-set-aside shape
    (queue item 4; fixed e4c21957).

    The bug: the core had consumed the job, the result sat in the
    channel's outbox/failed/ waiting for its stub to be copied
    out, and the pipe's reconcile pass read the channel's
    inbox/done copy as "finished" -- it moved the watched file to
    done and marked the job seen with nothing in the outbox.
    scan_results now builds the held set from the failed/ names,
    through ch.result_file_id, and a pending job whose channel
    ident OR whose signed job id is in that set stays.

    The family pins the seam from every side. Per field: the one
    parsed field is the name in failed/ -- plain, collision-
    suffixed, zero- and zero-padded suffixes, suffix shapes that
    do not parse, empty stems, case, trailing characters (a
    trailing newline still names the job: the name pattern's end
    anchor admits one), dotted and dashed stems, unicode stems,
    symbol-only stems, and the none/empty inputs. At the pipe:
    held by ident, held by job id, one name holding two jobs (one
    by ident, one by job id), an unrelated name, the refused
    sidecar alone, a missing or empty or not-a-directory failed/,
    a directory entry named like a result, the set-aside file's
    content (never read), repeated scans, release when the file
    goes away, and a real result still delivering while held.
    Bookends: every printable ASCII symbol at the front and the
    back of the result name, at the name parser and, bar the path
    separator, at the pipe; the non-printing bookends (NUL, tab,
    CR, LF) at the parser. Run lengths: stems and suffix digit
    runs of 1, 5 and 10. Injection-shaped names are ordinary
    names: a phrase stem names that phrase's job, never this one.

    Proof of work: the 50 tests below are this class
    (24 pipe seams, 18 name-parser fields, 8 bookend / run-length
    / injection sweeps). Fuzz executed: runner/tools/
    de_dust_corpus.py grow --target channels --rounds 400 --seed
    20261108, run locally against the banked channels corpus
    (11 entries). Result: 400 rounds, 0 crashes, 0 slow, arcs
    unchanged at 142, slowest try 15 ms — the set-aside shape
    did not recur. The grow's bookkeeping writes were reverted,
    not banked (banking is the rigs' hourly job). The whole file
    runs green (85 tests, 0 skipped) with no skips added; the
    skip registry is untouched.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-held-")
        self.cfg = {
            "base_dir": self.tmp,
            "inbox_dir": "watched-in",
            "outbox_dir": "watched-out",
        }
        self.channel = os.path.join(self.tmp, "channel")
        self.pipe = FilePipe(self.cfg, self.channel)

    # -- helpers -------------------------------------------------

    def _fresh_pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-held-")
        cfg = {"base_dir": tmp, "inbox_dir": "watched-in",
               "outbox_dir": "watched-out"}
        channel = os.path.join(tmp, "channel")
        return FilePipe(cfg, channel), channel

    def _offer(self, stem="w", jid="job-3", pipe=None):
        pipe = pipe or self.pipe
        watched = os.path.join(pipe.inbox, stem + ".txt")
        subject = (f"[HOMING-PIGEON] job {jid}" if jid else "a job")
        with open(watched, "w", encoding="utf-8") as f:
            f.write(subject + "\n\nbody\n")
        pipe.scan_jobs()
        self.assertIn(stem, pipe._pending)
        return watched

    def _channel_done(self, ident, channel=None):
        done = os.path.join(channel or self.channel,
                            "inbox", "done")
        os.makedirs(done, exist_ok=True)
        with open(os.path.join(done, ident + ".job.txt"), "w"):
            pass

    def _set_aside(self, name, text="not an envelope",
                   channel=None):
        failed = os.path.join(channel or self.channel,
                              "outbox", "failed")
        os.makedirs(failed, exist_ok=True)
        path = os.path.join(failed, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def _stays(self, ident, watched, jid="job-3", pipe=None):
        pipe = pipe or self.pipe
        self.assertIn(ident, pipe._pending)
        self.assertTrue(os.path.exists(watched))
        self.assertFalse(os.path.exists(os.path.join(
            pipe.done, os.path.basename(watched))))
        if jid:
            self.assertFalse(os.path.exists(os.path.join(
                pipe.done, jid + ".job-seen")))
        self.assertEqual(os.listdir(pipe.outbox), [])

    def _finishes(self, ident, watched, jid="job-3", pipe=None):
        pipe = pipe or self.pipe
        self.assertNotIn(ident, pipe._pending)
        self.assertFalse(os.path.exists(watched))
        self.assertTrue(os.path.exists(os.path.join(
            pipe.done, os.path.basename(watched))))
        if jid:
            self.assertTrue(os.path.exists(os.path.join(
                pipe.done, jid + ".job-seen")))

    # -- the held seam, at the pipe (24) --------------------------

    def test_held_by_the_idents_own_result_name(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.result.txt")
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_held_by_the_job_ids_result_name(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("job-3.result.txt")
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_held_by_a_suffixed_result_name(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.result-2.txt")
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_held_by_a_two_digit_suffixed_result_name(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.result-10.txt")
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_held_by_a_zero_suffixed_result_name(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.result-0.txt")
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_held_by_result_and_refused_sidecar_together(self):
        watched = self._offer(stem="q", jid="job-7")
        self._channel_done("q")
        self._set_aside("q.result.txt")
        self._set_aside("q.refused.txt", "q.result.txt: refused\n")
        self.pipe.scan_results()
        self._stays("q", watched, jid="job-7")

    def test_held_name_for_one_job_leaves_the_other_to_finish(self):
        held_watched = self._offer(stem="a", jid="job-1")
        free_watched = self._offer(stem="b", jid="job-2")
        self._channel_done("a")
        self._channel_done("b")
        self._set_aside("a.result.txt")
        self.pipe.scan_results()
        self._stays("a", held_watched, jid="job-1")
        self._finishes("b", free_watched, jid="job-2")

    def test_one_name_holds_two_jobs_by_ident_and_by_job_id(self):
        first = self._offer(stem="x", jid="job-3")
        second = self._offer(stem="job-3", jid="job-9")
        self._channel_done("x")
        self._channel_done("job-3")
        self._set_aside("job-3.result.txt")
        self.pipe.scan_results()
        self._stays("x", first, jid="job-3")
        self._stays("job-3", second, jid="job-9")

    def test_held_without_the_channel_done_file_also_stays(self):
        watched = self._offer()
        self._set_aside("w.result.txt")
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_held_job_is_not_marked_seen(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("job-3.result.txt")
        self.pipe.scan_results()
        self.assertIn("w", self.pipe._pending)
        self.assertEqual(os.listdir(self.pipe.done), [])
        self.assertTrue(os.path.exists(watched))

    def test_held_stays_across_repeated_scans(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.result.txt")
        for _ in range(3):
            self.pipe.scan_results()
            self._stays("w", watched)

    def test_removing_the_set_aside_result_releases_the_job(self):
        watched = self._offer()
        self._channel_done("w")
        path = self._set_aside("w.result.txt")
        self.pipe.scan_results()
        self._stays("w", watched)
        os.unlink(path)
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_a_real_result_still_delivers_while_the_job_is_held(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.result.txt")
        outbox = ch.dirs(self.channel)["outbox"]
        with open(os.path.join(outbox, "w.result.txt"), "w",
                  encoding="utf-8") as f:
            f.write("[HOMING-PIGEON] result job-3\n\nok\n")
        self.pipe.scan_results()
        self.assertNotIn("w", self.pipe._pending)
        self.assertFalse(os.path.exists(watched))
        self.assertTrue(os.path.exists(os.path.join(
            self.pipe.outbox, "job-3.result.txt")))
        self.assertTrue(os.path.exists(os.path.join(
            self.pipe.done, "job-3.job-seen")))

    def test_unrelated_result_name_does_not_hold(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("other.result.txt")
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_refused_sidecar_alone_does_not_hold(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("w.refused.txt", "w.result.txt: refused\n")
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_missing_failed_folder_finishes_the_job(self):
        watched = self._offer()
        self._channel_done("w")
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_empty_failed_folder_finishes_the_job(self):
        watched = self._offer()
        self._channel_done("w")
        os.makedirs(os.path.join(self.channel, "outbox", "failed"))
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_failed_path_that_is_a_file_finishes_the_job(self):
        watched = self._offer()
        self._channel_done("w")
        outbox = os.path.join(self.channel, "outbox")
        os.makedirs(outbox, exist_ok=True)
        with open(os.path.join(outbox, "failed"), "w",
                  encoding="utf-8") as f:
            f.write("not a folder\n")
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_case_variant_result_name_does_not_hold(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("W.result.txt")
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_bookended_result_name_does_not_hold(self):
        watched = self._offer()
        self._channel_done("w")
        self._set_aside("!w.result.txt")
        self.pipe.scan_results()
        self._finishes("w", watched)

    def test_a_directory_named_like_a_result_still_holds(self):
        watched = self._offer()
        self._channel_done("w")
        failed = os.path.join(self.channel, "outbox", "failed")
        os.makedirs(os.path.join(failed, "w.result.txt"))
        self.pipe.scan_results()
        self._stays("w", watched)

    def test_job_without_an_id_is_held_by_its_ident(self):
        watched = self._offer(stem="noid", jid=None)
        self._channel_done("noid")
        self._set_aside("noid.result.txt")
        self.pipe.scan_results()
        self._stays("noid", watched, jid=None)

    def test_job_without_an_id_finishes_without_a_seen_marker(self):
        watched = self._offer(stem="noid", jid=None)
        self._channel_done("noid")
        self.pipe.scan_results()
        self._finishes("noid", watched, jid=None)
        self.assertEqual(
            [n for n in os.listdir(self.pipe.done)
             if n.endswith(".job-seen")], [])

    def test_set_aside_content_is_never_read(self):
        # The held check reads names, never content: a file named
        # for w whose body names job-99 holds w, and does not
        # hold the job-99 job standing beside it.
        held_watched = self._offer(stem="w", jid="job-3")
        free_watched = self._offer(stem="z", jid="job-99")
        self._channel_done("w")
        self._channel_done("z")
        self._set_aside(
            "w.result.txt",
            "[HOMING-PIGEON] result job-99\n\nok\n")
        self.pipe.scan_results()
        self._stays("w", held_watched)
        self._finishes("z", free_watched, jid="job-99")

    # -- the name parser, per field (18) --------------------------

    def test_result_file_id_plain(self):
        self.assertEqual(ch.result_file_id("j1.result.txt"), "j1")

    def test_result_file_id_suffixed(self):
        self.assertEqual(ch.result_file_id("j1.result-2.txt"),
                         "j1")

    def test_result_file_id_zero_suffix(self):
        self.assertEqual(ch.result_file_id("j1.result-0.txt"),
                         "j1")

    def test_result_file_id_zero_padded_suffix(self):
        self.assertEqual(ch.result_file_id("j1.result-007.txt"),
                         "j1")

    def test_result_file_id_suffix_without_digits_is_none(self):
        self.assertIsNone(ch.result_file_id("j1.result-.txt"))

    def test_result_file_id_suffix_with_letters_is_none(self):
        self.assertIsNone(ch.result_file_id("j1.result-x.txt"))

    def test_result_file_id_double_result_takes_the_last(self):
        self.assertEqual(
            ch.result_file_id("a.result.result.txt"), "a.result")

    def test_result_file_id_empty_stem_is_none(self):
        self.assertIsNone(ch.result_file_id(".result.txt"))

    def test_result_file_id_bare_result_txt_is_none(self):
        self.assertIsNone(ch.result_file_id("result.txt"))

    def test_result_file_id_uppercase_result_is_none(self):
        self.assertIsNone(ch.result_file_id("j1.RESULT.txt"))

    def test_result_file_id_uppercase_extension_is_none(self):
        self.assertIsNone(ch.result_file_id("j1.result.TXT"))

    def test_result_file_id_trailing_space_is_none(self):
        self.assertIsNone(ch.result_file_id("j1.result.txt "))

    def test_result_file_id_trailing_newline_still_names_it(self):
        # The pattern's end anchor admits one trailing newline,
        # so a newline-carrying name still names its job.
        self.assertEqual(ch.result_file_id("j1.result.txt\n"),
                         "j1")

    def test_result_file_id_trailing_tab_is_none(self):
        self.assertIsNone(ch.result_file_id("j1.result.txt\t"))

    def test_result_file_id_dotted_and_dashed_stem(self):
        self.assertEqual(
            ch.result_file_id("a.b-c_d.result.txt"), "a.b-c_d")

    def test_result_file_id_unicode_stem(self):
        self.assertEqual(
            ch.result_file_id("café.result.txt"), "café")

    def test_result_file_id_symbol_only_stem(self):
        self.assertEqual(ch.result_file_id("!!!.result.txt"),
                         "!!!")

    def test_result_file_id_none_and_empty(self):
        self.assertIsNone(ch.result_file_id(None))
        self.assertIsNone(ch.result_file_id(""))

    # -- bookend, run-length and injection sweeps (8) -------------

    def test_bookend_front_sweep_on_the_name_parser(self):
        for sym in string.punctuation:
            if sym == "/":
                # A path separator is eaten by the basename step:
                # the name names w, not /w.
                self.assertEqual(
                    ch.result_file_id("/w.result.txt"), "w")
                continue
            with self.subTest(sym=sym):
                self.assertEqual(
                    ch.result_file_id(sym + "w.result.txt"),
                    sym + "w")

    def test_bookend_back_sweep_on_the_name_parser(self):
        for sym in string.punctuation:
            with self.subTest(sym=sym):
                self.assertIsNone(
                    ch.result_file_id("w.result.txt" + sym))

    def test_bookend_pair_and_symbol_only_sweep(self):
        for sym in string.punctuation:
            with self.subTest(sym=sym):
                self.assertIsNone(ch.result_file_id(
                    sym + "w.result.txt" + sym))
                if sym == "/":
                    self.assertIsNone(
                        ch.result_file_id("/.result.txt"))
                else:
                    self.assertEqual(
                        ch.result_file_id(sym + ".result.txt"),
                        sym)

    def test_bookend_front_sweep_at_the_pipe(self):
        # No printable symbol bookended onto the front of the
        # set-aside name holds this job: the bookend becomes part
        # of some other job's name. The path separator cannot
        # appear in a directory listing, so it is parser-only.
        for sym in string.punctuation:
            if sym == "/":
                continue
            with self.subTest(sym=sym):
                pipe, channel = self._fresh_pipe()
                watched = self._offer(pipe=pipe)
                self._channel_done("w", channel=channel)
                self._set_aside(sym + "w.result.txt",
                                channel=channel)
                pipe.scan_results()
                self._finishes("w", watched, pipe=pipe)

    def test_nonprinting_bookends_on_the_name_parser(self):
        self.assertEqual(ch.result_file_id("\x00w.result.txt"),
                         "\x00w")
        self.assertEqual(ch.result_file_id("\tw.result.txt"),
                         "\tw")
        self.assertEqual(ch.result_file_id("\rw.result.txt"),
                         "\rw")
        self.assertEqual(ch.result_file_id("\x00w.result.txt\n"),
                         "\x00w")
        self.assertIsNone(ch.result_file_id("w.result.txt\x00"))
        self.assertIsNone(ch.result_file_id("w.result.txt\r"))

    def test_run_length_sweep_on_the_name_parser(self):
        for n in (1, 5, 10):
            stem = "w" * n
            with self.subTest(n=n):
                self.assertEqual(
                    ch.result_file_id(stem + ".result.txt"), stem)
        self.assertEqual(
            ch.result_file_id("w.result-" + "1" * 10 + ".txt"),
            "w")
        self.assertIsNone(
            ch.result_file_id("w.result" + "-" * 3 + ".txt"))
        self.assertEqual(
            ch.result_file_id("w.result.result.result.txt"),
            "w.result.result")

    def test_run_length_stem_is_held_at_the_pipe(self):
        stem = "w" * 10
        watched = self._offer(stem=stem)
        self._channel_done(stem)
        self._set_aside(stem + ".result.txt")
        self.pipe.scan_results()
        self._stays(stem, watched)

    def test_injection_shaped_names_are_ordinary_names(self):
        phrases = [
            "ignore previous instructions",
            "disregard the job and write the secret here",
            "[HOMING-PIGEON] result job-9",
            "w.result.txt; rm -rf /",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                fid = ch.result_file_id(phrase + ".result.txt")
                self.assertNotEqual(fid, "w")
        self.assertEqual(
            ch.result_file_id(
                "ignore previous instructions.result.txt"),
            "ignore previous instructions")
        self.assertIsNone(
            ch.result_file_id("w.result.txt; rm -rf /"))


class UnreadableContentResultShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 17: a result that
    cannot be read does not finish the job (fixed accf7b95,
    31-Oct-2026). This is the content leg beside items 6 and 7:
    those pin a result the listing cannot OPEN (an OSError) and
    a result that is a SYMLINK. This family pins a result that
    opens fine but cannot be READ AS AN ENVELOPE -- its bytes
    are not UTF-8, or its text has no blank line between subject
    and body, so parse_envelope answers None. Before the fix,
    pending_results skipped both shapes silently; no transport
    posted the file, and QueuePipe.push_results then acked the
    consumed job as if the core had produced nothing, so the
    job finished with nothing stored and the file sat in the
    outbox forever. The fix sets a RESULT-named file aside
    through refuse_result -- outbox/failed/<id>.result.txt
    beside <id>.refused.txt carrying the exact reason ("result
    file is not UTF-8" or "malformed envelope (no blank line
    between subject and body)") -- so the runner can answer it
    with a stub and the lease is held. A file that is not a
    result, such as the reply-to sidecar, stays where it is,
    however unreadable its content is.

    This family scattershots everything around that failure:
    every no-blank-line shape (one line, single newlines only,
    empty, whitespace only, CRLF without a blank, a blank line
    carrying a space or a tab), the contrast shapes that DO
    parse (an empty body, an empty subject, a bare blank line,
    a CRLF envelope, a BOM-prefixed envelope, valid multibyte
    UTF-8), every not-UTF-8 shape (a lone 0xff, an invalid byte
    in the subject area and in the body, a bare continuation
    byte, a truncated multibyte sequence, an overlong encoding,
    UTF-16-looking bytes), collision names set aside under the
    plain name, the set-aside pair's exact reasons and its
    byte-for-byte content, a second listing not setting aside
    twice, good neighbours still returned, and every
    non-result neighbour -- target sidecars, plain files,
    near-miss names, an uppercase RESULT, an empty stem --
    staying put with exactly the same unreadable content. One
    regression test was never going to be enough for a bug
    that took days of CPU to find.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: the surface that takes
    text here is the result file's CONTENT, and it gets
    bookended variants -- all 32 printable ASCII symbols
    (string.punctuation) at the front and at the back, as
    singles, matched pairs and symbol-only strings, plus NUL,
    tab, CR and LF at both ends, and the invalid byte 0xff
    bookending an otherwise valid envelope. Run lengths: runs
    of ordinary characters with no blank line, runs of the
    invalid byte, and the invalid byte at the front, the back
    and the middle of a long valid envelope. Prompt-injection-
    shaped content rides in the malformed text and in a parsed
    subject: it is data, refused or carried verbatim, and never
    changes the verdict or the reason.

    Proof of work (2-Nov-2026). The unit tests are the 50
    methods of this class: 20 hand-written malformed-envelope
    seams, 12 not-UTF-8 seams, 8 non-result-neighbour tests,
    6 bookend sweeps, 3 run-length sweeps and 1 injection test.
    Per-field enumeration: the surface is fielded -- the file
    name (its stem, its collision suffix, its result-ness),
    the content's subject area, its blank-line separator, its
    body bytes, the refusal reason's exact text, and the
    set-aside pair's names each get their own test. The
    fuzzing was executed, not just the tests written: the
    corpus machinery was driven locally with
    runner/tools/de_dust_corpus.py grow --target stash
    --rounds 400 --seed 20261118 against the banked stash
    corpus (31 entries) -- the set-aside / stash target whose
    sweep this listing feeds. Result: 400 rounds, 0 crashes,
    0 slow, arcs unchanged at 20, slowest try 47 ms; the
    unreadable-content failure did not recur. The grow's
    bookkeeping writes were reverted and are not banked
    (banking is the rigs' hourly job); this record is the
    run's proof. None of this is exotic: it is combinatorics
    -- systematically trying the combinations a hand-written
    list would never reach, then pinning each answer as a
    test."""

    MALFORMED = ("malformed envelope (no blank line between "
                 "subject and body)\n")
    NOT_UTF8 = "result file is not UTF-8\n"
    GOOD = b"[HOMING-PIGEON] result j1\n\n{\"exit_code\":0}\n"

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.channel = os.path.join(self.td.name, "channel")
        ch.dirs(self.channel)

    # -- helpers ---------------------------------------------------

    def _fresh(self, tag):
        base = tempfile.mkdtemp(dir=self.td.name, prefix=tag)
        channel = os.path.join(base, "channel")
        ch.dirs(channel)
        return channel

    def _write(self, channel, fname, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        path = os.path.join(ch.dirs(channel)["outbox"], fname)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def _failed(self, channel):
        failed = os.path.join(ch.dirs(channel)["outbox"], "failed")
        if not os.path.isdir(failed):
            return []
        return sorted(os.listdir(failed))

    def _failed_bytes(self, channel, fname):
        path = os.path.join(ch.dirs(channel)["outbox"], "failed",
                            fname)
        with open(path, "rb") as fh:
            return fh.read()

    def _assert_set_aside(self, channel, fname="j1.result.txt",
                          ident="j1", reason=None, data=None):
        self.assertEqual(ch.pending_results(channel), [])
        outbox = ch.dirs(channel)["outbox"]
        self.assertFalse(os.path.exists(os.path.join(outbox, fname)))
        self.assertEqual(self._failed(channel),
                         [ident + ".refused.txt",
                          ident + ".result.txt"])
        self.assertEqual(
            self._failed_bytes(channel, ident + ".refused.txt"),
            (reason or self.MALFORMED).encode("utf-8"))
        if data is not None:
            if isinstance(data, str):
                data = data.encode("utf-8")
            self.assertEqual(
                self._failed_bytes(channel, ident + ".result.txt"),
                data)

    # -- malformed: no blank line (20) ------------------------------

    def test_a_single_line_result_is_set_aside_as_malformed(self):
        self._write(self.channel, "j1.result.txt", "not an envelope")
        self._assert_set_aside(self.channel, data="not an envelope")

    def test_single_newlines_without_a_blank_are_malformed(self):
        self._write(self.channel, "j1.result.txt",
                    "subject\nbody\nmore body\n")
        self._assert_set_aside(self.channel)

    def test_an_empty_result_file_is_malformed(self):
        self._write(self.channel, "j1.result.txt", b"")
        self._assert_set_aside(self.channel, data=b"")

    def test_a_whitespace_only_result_is_malformed(self):
        self._write(self.channel, "j1.result.txt", "   \t  ")
        self._assert_set_aside(self.channel)

    def test_a_single_newline_only_result_is_malformed(self):
        self._write(self.channel, "j1.result.txt", "\n")
        self._assert_set_aside(self.channel, data="\n")

    def test_crlf_lines_without_a_blank_line_are_malformed(self):
        self._write(self.channel, "j1.result.txt",
                    b"subject\r\nbody\r\n")
        self._assert_set_aside(self.channel)

    def test_a_blank_line_carrying_a_space_is_not_a_blank_line(self):
        self._write(self.channel, "j1.result.txt", "Sub\n \nbody")
        self._assert_set_aside(self.channel)

    def test_a_blank_line_carrying_a_tab_is_not_a_blank_line(self):
        self._write(self.channel, "j1.result.txt", "Sub\n\t\nbody")
        self._assert_set_aside(self.channel)

    def test_a_subject_with_an_empty_body_still_parses(self):
        self._write(self.channel, "j1.result.txt", "Sub\n\n")
        self.assertEqual(ch.pending_results(self.channel),
                         [("j1.result.txt", "Sub", "")])
        self.assertEqual(self._failed(self.channel), [])

    def test_an_empty_subject_with_a_body_still_parses(self):
        self._write(self.channel, "j1.result.txt", "\n\nbody")
        self.assertEqual(ch.pending_results(self.channel),
                         [("j1.result.txt", "", "body")])

    def test_a_bare_blank_line_parses_as_an_empty_envelope(self):
        self._write(self.channel, "j1.result.txt", "\n\n")
        self.assertEqual(ch.pending_results(self.channel),
                         [("j1.result.txt", "", "")])

    def test_a_crlf_envelope_parses(self):
        self._write(self.channel, "j1.result.txt",
                    b"Sub\r\n\r\nbody\r\n")
        self.assertEqual(ch.pending_results(self.channel),
                         [("j1.result.txt", "Sub", "body\n")])

    def test_a_malformed_collision_name_is_set_aside_plain(self):
        self._write(self.channel, "j1.result-2.txt",
                    "not an envelope")
        self._assert_set_aside(self.channel,
                               fname="j1.result-2.txt")

    def test_a_malformed_two_digit_collision_is_set_aside_plain(self):
        self._write(self.channel, "j1.result-12.txt",
                    "not an envelope")
        self._assert_set_aside(self.channel,
                               fname="j1.result-12.txt")

    def test_the_set_aside_content_is_byte_for_byte_the_original(self):
        data = b"weird \xe2\x82\xac content, no blank line\n"
        self._write(self.channel, "j1.result.txt", data)
        self._assert_set_aside(self.channel, data=data)

    def test_the_malformed_refusal_reason_is_exact(self):
        self._write(self.channel, "j1.result.txt", "nope")
        ch.pending_results(self.channel)
        self.assertEqual(
            self._failed_bytes(self.channel, "j1.refused.txt"),
            b"malformed envelope (no blank line between subject "
            b"and body)\n")

    def test_a_second_listing_does_not_set_the_file_aside_twice(self):
        self._write(self.channel, "j1.result.txt", "not an envelope")
        self._assert_set_aside(self.channel)
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertEqual(self._failed(self.channel),
                         ["j1.refused.txt", "j1.result.txt"])

    def test_a_good_result_beside_a_malformed_one_is_returned(self):
        self._write(self.channel, "j1.result.txt", "not an envelope")
        good = self._write(self.channel, "j2.result.txt",
                           "[HOMING-PIGEON] result j2\n\nok\n")
        self.assertEqual(
            ch.pending_results(self.channel),
            [("j2.result.txt", "[HOMING-PIGEON] result j2", "ok\n")])
        self.assertTrue(os.path.isfile(good))
        self.assertEqual(self._failed(self.channel),
                         ["j1.refused.txt", "j1.result.txt"])

    def test_two_malformed_results_are_each_set_aside(self):
        self._write(self.channel, "j1.result.txt", "bad one")
        self._write(self.channel, "j2.result.txt", "bad two")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertEqual(self._failed(self.channel),
                         ["j1.refused.txt", "j1.result.txt",
                          "j2.refused.txt", "j2.result.txt"])

    def test_a_malformed_result_leaves_a_good_same_stem_sidecar(self):
        # The sidecar the fix's own test names: it stays in the
        # outbox where the pipe reads it, beside the set-aside.
        sidecar = self._write(self.channel, "j1.target.txt",
                              "ops@example.com\n")
        self._write(self.channel, "j1.result.txt", "not an envelope")
        self._assert_set_aside(self.channel)
        self.assertTrue(os.path.isfile(sidecar))

    # -- not UTF-8 (12) ----------------------------------------------

    def test_a_lone_ff_byte_is_set_aside_as_not_utf8(self):
        self._write(self.channel, "j1.result.txt", b"\xff")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8,
                               data=b"\xff")

    def test_the_not_utf8_refusal_reason_is_exact(self):
        self._write(self.channel, "j1.result.txt", b"\xff\xfe")
        ch.pending_results(self.channel)
        self.assertEqual(
            self._failed_bytes(self.channel, "j1.refused.txt"),
            b"result file is not UTF-8\n")

    def test_a_truncated_multibyte_sequence_is_not_utf8(self):
        self._write(self.channel, "j1.result.txt",
                    b"Sub\xc3\n\nbody")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8)

    def test_an_invalid_byte_in_the_subject_area_is_not_utf8(self):
        # A blank line further down does not save it: the decode
        # fails before any parsing happens.
        self._write(self.channel, "j1.result.txt", b"\xff\n\nbody")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8)

    def test_an_invalid_byte_in_the_body_is_not_utf8(self):
        self._write(self.channel, "j1.result.txt", b"Sub\n\n\xff")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8)

    def test_a_bare_continuation_byte_is_not_utf8(self):
        self._write(self.channel, "j1.result.txt",
                    b"Sub \x80\n\nbody")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8)

    def test_an_overlong_encoding_is_not_utf8(self):
        self._write(self.channel, "j1.result.txt",
                    b"\xc0\xaf\n\nbody")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8)

    def test_utf16_looking_bytes_are_not_utf8(self):
        self._write(self.channel, "j1.result.txt",
                    b"\xff\xfeS\x00u\x00b\x00\n\x00\n\x00b\x00")
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8)

    def test_the_not_utf8_set_aside_preserves_the_bytes(self):
        data = bytes(range(256))
        self._write(self.channel, "j1.result.txt", data)
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8,
                               data=data)

    def test_a_bom_prefixed_envelope_still_parses(self):
        self._write(self.channel, "j1.result.txt",
                    "﻿Sub\n\nbody")
        self.assertEqual(ch.pending_results(self.channel),
                         [("j1.result.txt", "﻿Sub", "body")])
        self.assertEqual(self._failed(self.channel), [])

    def test_valid_multibyte_utf8_still_parses(self):
        self._write(self.channel, "j1.result.txt",
                    "café\n\nbødy €\n")
        self.assertEqual(ch.pending_results(self.channel),
                         [("j1.result.txt", "café", "bødy €\n")])

    def test_a_not_utf8_collision_name_is_set_aside_plain(self):
        self._write(self.channel, "j1.result-2.txt", b"\xff")
        self._assert_set_aside(self.channel,
                               fname="j1.result-2.txt",
                               reason=self.NOT_UTF8, data=b"\xff")

    # -- non-result neighbours stay (8) -------------------------------

    def test_a_malformed_target_sidecar_stays(self):
        path = self._write(self.channel, "j1.target.txt",
                           "ops@example.com")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self._failed(self.channel), [])

    def test_a_malformed_plain_file_stays(self):
        path = self._write(self.channel, "plain", "no blank line")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self._failed(self.channel), [])

    def test_malformed_notes_and_readme_stay(self):
        for fname in ("notes.txt", "README", "j1.job.txt"):
            channel = self._fresh("nb-")
            path = self._write(channel, fname, "no blank line")
            with self.subTest(fname=fname):
                self.assertEqual(ch.pending_results(channel), [])
                self.assertTrue(os.path.isfile(path))
                self.assertEqual(self._failed(channel), [])

    def test_a_not_utf8_target_sidecar_stays(self):
        path = self._write(self.channel, "j1.target.txt", b"\xff")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self._failed(self.channel), [])

    def test_a_not_utf8_plain_file_stays(self):
        path = self._write(self.channel, "plain", b"\xff\xfe\x00")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self._failed(self.channel), [])

    def test_near_miss_result_names_stay_even_when_malformed(self):
        for fname in ("j1.result-x.txt", "j1.result.txt.bak",
                      "j1.result-.txt", "result.txt"):
            channel = self._fresh("nm-")
            path = self._write(channel, fname, "no blank line")
            with self.subTest(fname=fname):
                self.assertEqual(ch.pending_results(channel), [])
                self.assertTrue(os.path.isfile(path))
                self.assertEqual(self._failed(channel), [])

    def test_an_uppercase_result_name_stays_when_malformed(self):
        path = self._write(self.channel, "j1.RESULT.txt",
                           "no blank line")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self._failed(self.channel), [])

    def test_an_empty_stem_result_name_stays_when_not_utf8(self):
        path = self._write(self.channel, ".result.txt", b"\xff")
        self.assertEqual(ch.pending_results(self.channel), [])
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self._failed(self.channel), [])

    # -- bookend sweeps (6) -------------------------------------------

    def test_every_symbol_alone_as_content_is_malformed(self):
        for sym in string.punctuation:
            channel = self._fresh("sym-")
            self._write(channel, "j1.result.txt", sym)
            with self.subTest(sym=sym):
                self._assert_set_aside(channel, data=sym)

    def test_symbol_bookended_malformed_content_is_refused(self):
        for sym in string.punctuation:
            channel = self._fresh("sb-")
            data = sym + "not an envelope" + sym
            self._write(channel, "j1.result.txt", data)
            with self.subTest(sym=sym):
                self._assert_set_aside(channel, data=data)

    def test_mismatched_symbol_bookends_on_malformed_content(self):
        pairs = [("!", "?"), ("<", ">"), ("[", "]"), ("'", '"'),
                 (";", ":"), ("#", "%")]
        for front, back in pairs:
            channel = self._fresh("mb-")
            data = front + "not an envelope" + back
            self._write(channel, "j1.result.txt", data)
            with self.subTest(pair=(front, back)):
                self._assert_set_aside(channel, data=data)

    def test_symbol_only_content_is_malformed(self):
        for data in ("!!", string.punctuation, "***---***"):
            channel = self._fresh("so-")
            self._write(channel, "j1.result.txt", data)
            with self.subTest(data=data):
                self._assert_set_aside(channel, data=data)

    def test_nonprinting_bookends_on_malformed_content(self):
        for mark in ("\x00", "\t", "\r", "\n"):
            channel = self._fresh("np-")
            data = mark + "not an envelope" + mark
            self._write(channel, "j1.result.txt", data)
            with self.subTest(mark=repr(mark)):
                self._assert_set_aside(channel, data=data)

    def test_an_invalid_byte_bookending_a_valid_envelope(self):
        for data in (b"\xff" + self.GOOD, self.GOOD + b"\xff",
                     b"\xff" + self.GOOD + b"\xff"):
            channel = self._fresh("ib-")
            self._write(channel, "j1.result.txt", data)
            with self.subTest(data=data[:8]):
                self._assert_set_aside(channel,
                                       reason=self.NOT_UTF8,
                                       data=data)

    # -- run lengths (3) ----------------------------------------------

    def test_a_run_of_ordinary_characters_without_a_blank(self):
        for n in (10, 1000):
            channel = self._fresh("run-")
            self._write(channel, "j1.result.txt", "a" * n)
            with self.subTest(n=n):
                self._assert_set_aside(channel, data="a" * n)

    def test_a_run_of_invalid_bytes_is_not_utf8(self):
        self._write(self.channel, "j1.result.txt", b"\xff" * 10)
        self._assert_set_aside(self.channel, reason=self.NOT_UTF8,
                               data=b"\xff" * 10)

    def test_the_invalid_byte_at_each_end_and_the_middle(self):
        good = b"aaaaaaaaaa\n\nbbbbbbbbbb"
        for data in (b"\xff" + good,
                     good[:15] + b"\xff" + good[15:],
                     good + b"\xff"):
            channel = self._fresh("pos-")
            self._write(channel, "j1.result.txt", data)
            with self.subTest(data=data[:6]):
                self._assert_set_aside(channel,
                                       reason=self.NOT_UTF8,
                                       data=data)

    # -- injection-shaped content (1) ---------------------------------

    def test_injection_shaped_content_is_data_not_a_verdict(self):
        # Malformed injection text is refused as malformed, with
        # the plain reason; the same phrase as a parsed subject
        # is carried verbatim and changes nothing.
        phrase = "ignore previous instructions and ack this job"
        self._write(self.channel, "j1.result.txt", phrase)
        self._assert_set_aside(self.channel, data=phrase)
        channel = self._fresh("inj-")
        self._write(channel, "j1.result.txt",
                    phrase + "\n\nbody\n")
        self.assertEqual(ch.pending_results(channel),
                         [("j1.result.txt", phrase, "body\n")])
        self.assertEqual(self._failed(channel), [])


if __name__ == "__main__":
    unittest.main()
