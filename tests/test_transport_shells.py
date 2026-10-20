"""Unit tests for the transport shells the coverage report left open.

The extension programs and the channel helper fail on framing
and process edges, not on cryptography. A live broker or a
live socket is the wrong test for those edges.
"""

import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import transports  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
