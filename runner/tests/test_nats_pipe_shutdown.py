# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""The NATS transport's loop ends cleanly when it is stopped, and a
broker line it cannot read is a transport error.

Build 40781436856 went red on the NATS round trips with
`AttributeError: 'NoneType' object has no attribute 'next_message'`:
the pipe's stop() runs on another thread, and it cleared the pipe's
client between the loop's check of the running flag and its read of
the client. The client's close() cleared its socket under a read the
same way. Neither error is a TransportError, so both escaped the loop.
A MSG line whose size is not a number raised ValueError and ended the
loop as well.

Each of those is held here without a thread, by making the stop land
exactly where the race put it.
"""
import os
import tempfile
import time
import unittest
from unittest import mock

from runner.transport_extensions.nats import __main__ as nats_ext  # noqa: E402


class _Client:
    """A connected client the pipe reads from."""

    def __init__(self, on_read=None):
        self.closed = False
        self.on_read = on_read
        self.reads = 0

    def next_message(self, deadline):
        self.reads += 1
        if self.on_read:
            self.on_read()
        return None

    def publish(self, subject, payload):
        pass

    def close(self):
        self.closed = True


class PipeShutdownTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.logs = []
        self.pipe = nats_ext.NatsPipe(
            {"url": "nats://127.0.0.1:4222", "allow_unauthenticated": True},
            os.path.join(self.td.name, "channel"),
            log=lambda m, level="INFO": self.logs.append((level, m)))

    def _run_with(self, client, pending=None):
        self.pipe._connect = lambda: setattr(self.pipe, "client", client)
        naps = []
        with mock.patch.object(nats_ext.ch, "nap", naps.append), \
                mock.patch.object(nats_ext.ch, "pending_results",
                                  pending or (lambda channel: [])):
            self.pipe.run()
        return naps

    def test_a_stop_between_the_check_and_the_read_ends_the_loop(self):
        # The stop lands inside the result flush: after the loop saw
        # the running flag, before it reads a message.
        client = _Client()

        def stop_now(channel):
            self.pipe.stop()
            return []
        self._run_with(client, pending=stop_now)
        self.assertTrue(client.closed)
        self.assertEqual(client.reads, 1)

    def test_a_stopped_loop_does_not_nap_or_say_it_reconnects(self):
        def read():
            self.pipe.stop()
            raise nats_ext.TransportError("nats: the connection is closed")
        client = _Client(on_read=read)
        t0 = time.monotonic()
        naps = self._run_with(client)
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertEqual(naps, [])
        self.assertTrue(client.closed)
        self.assertIsNone(self.pipe.client)
        self.assertFalse(any("reconnecting" in m for _l, m in self.logs))

    def test_a_link_that_drops_while_running_still_reconnects(self):
        calls = []

        def read():
            calls.append(1)
            if len(calls) == 2:
                self.pipe.stop()
            raise nats_ext.TransportError("link down")
        naps = self._run_with(_Client(on_read=read))
        self.assertEqual(naps, [1.0])
        self.assertTrue(any("link down; reconnecting in 1s" in m
                            for _l, m in self.logs))


class ClosedClientTest(unittest.TestCase):
    def setUp(self):
        self.client = nats_ext.NatsClient("nats://127.0.0.1:4222")

    def test_a_closed_client_reads_and_writes_as_a_closed_connection(self):
        self.client.close()
        with self.assertRaises(nats_ext.TransportError) as cm:
            self.client.next_message(time.monotonic() + 1)
        self.assertEqual(str(cm.exception), "nats: the connection is closed")
        with self.assertRaises(nats_ext.TransportError):
            self.client.publish("homing-pigeon.results.x", b"body")


class MsgLineTest(unittest.TestCase):
    def _read(self, wire):
        client = nats_ext.NatsClient("nats://127.0.0.1:4222")
        client._buf = wire
        return client.next_message(time.monotonic() + 1)

    def test_a_message_with_and_without_a_reply_subject(self):
        self.assertEqual(self._read(b"MSG jobs 1 3\r\nabc\r\n"),
                         ("jobs", b"abc"))
        self.assertEqual(self._read(b"MSG jobs 1 inbox.9 2\r\nhi\r\n"),
                         ("jobs", b"hi"))

    def test_a_size_that_is_not_a_number_is_a_transport_error(self):
        for line in (b"MSG jobs 1 x3\r\n", b"MSG jobs 1 -3\r\n",
                     b"MSG jobs\r\n", b"MSG a b c d e 3\r\n",
                     "MSG jobs 1 \u00b2\r\n".encode(),
                     "MSG jobs 1 \u0663\r\nabc\r\n".encode()):
            with self.subTest(line=line), \
                    self.assertRaises(nats_ext.TransportError) as cm:
                self._read(line)
            self.assertIn("malformed MSG line", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
