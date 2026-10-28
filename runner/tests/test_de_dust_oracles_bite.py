# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""The de_dust mail oracles bite: each contract check fires on a
handler that breaks it.

The corpus replay proves the runner meets every oracle's contract,
which means no test ever saw an oracle fire. A check whose condition
was miswritten would pass the same replay and wave real bugs through
the campaign. Here each mail oracle (version 2 mail, query mail,
board mail) is run on a seed it accepts, with the handler wrapped so
it runs for real and then breaks exactly one promise: it raises, it
answers False, it marks the message twice, it sends two replies, it
answers the copy, it addresses or names the reply wrongly, it leaves
or keeps a question against the switches, it forgets or over-records
what it acted on, its board in memory drifts from the file. Each
must end in a Crash of the right kind that says what broke.
"""
import copy
import unittest
from email.message import EmailMessage
from unittest import mock

from runner.tools import de_dust_corpus as B  # noqa: E402


def _seed(seeds, name):
    for s in seeds:
        if s["from"] == "seed:" + name:
            return copy.deepcopy(s)
    raise AssertionError("no seed named %s" % name)


def _reply(to="someone@example.test", subject="[HOMING-PIGEON] answer a.x"):
    m = EmailMessage()
    m["To"] = to
    m["Subject"] = subject
    return m


def _retag(msg, header, value):
    del msg[header]
    msg[header] = value


class _OracleCase(unittest.TestCase):
    """Run one oracle on one seed with its handler wrapped."""

    module = name = check = seeds = None
    IMAP, SMTP, ATTEMPT = 1, 2, 3

    def _run(self, seed, handler):
        entry = _seed(self.seeds(), seed)
        with mock.patch.object(self.module, self.name, handler):
            return B._with_rig(lambda: self.check(entry))

    def _after(self, breaks, attempts=(1, 2)):
        """The real handler, then `breaks(args, got)` on the attempts
        named; returns what `breaks` returns."""
        real = getattr(self.module, self.name)

        def handler(*args):
            got = real(*args)
            if args[self.ATTEMPT] in attempts:
                return breaks(args, got)
            return got
        return handler

    def assertBites(self, seed, handler, kind, words):
        with self.assertRaises(B.Crash) as cm:
            self._run(seed, handler)
        self.assertEqual(cm.exception.kind, kind, str(cm.exception))
        self.assertIn(words, cm.exception.detail)

    def _common(self, seed, what):
        """The checks every mail oracle makes on every attempt."""
        def raising(*_a):
            raise RuntimeError("handler fell over")

        self.assertEqual(self._run(seed, getattr(self.module, self.name)),
                         "accepted")
        self.assertBites(seed, raising, "exception",
                         "%s raised RuntimeError: handler fell over" % what)
        self.assertBites(seed, self._after(lambda a, g: False), "contract",
                         "%s answered False" % what)
        self.assertBites(seed, self._after(
            lambda a, g: (a[self.IMAP].marked.append(("1", "+FLAGS", "x")),
                          g)[1], attempts=(1,)),
            "contract", "the message was marked 2 times under dry False")
        self.assertBites(seed, self._after(
            lambda a, g: (a[self.SMTP].sent.append(_reply()), g)[1],
            attempts=(1,)), "contract", "2 replies went out")


class V2MailOracleTest(_OracleCase):
    module, name = B.HA, "handle_v2_mail"
    check = staticmethod(B.check_v2_mail)
    seeds = staticmethod(B.seeds_v2_mail)

    def test_the_checks_every_attempt_makes(self):
        self._common("question", "handle_v2_mail")

    def test_the_copy_is_not_answered_again(self):
        self.assertBites("question", self._after(
            lambda a, g: (a[self.SMTP].sent.append(_reply()), g)[1],
            attempts=(2,)), "contract", "a copy of the message was answered "
                                        "again")

    def test_the_answer_goes_to_the_mailbox_under_its_own_subject(self):
        self.assertBites("question", self._after(
            lambda a, g: (_retag(a[self.SMTP].sent[0], "To",
                                 "elsewhere@example.test"), g)[1],
            attempts=(1,)), "provenance",
            "the answer is addressed to 'elsewhere@example.test'")
        self.assertBites("question", self._after(
            lambda a, g: (_retag(a[self.SMTP].sent[0], "Subject",
                                 "[HOMING-PIGEON] result x"), g)[1],
            attempts=(1,)), "contract",
            "the answer's subject is '[HOMING-PIGEON] result x'")

    def test_only_a_question_gets_an_answer(self):
        self.assertBites("determination", self._after(
            lambda a, g: (a[self.SMTP].sent.append(_reply()), g)[1],
            attempts=(1,)), "contract", "a determination got a reply")

    def test_leaving_follows_the_switches(self):
        def leave_anyway(args, got):
            B.R._v2_leave_unseen()
            return got
        self.assertBites("question", self._after(leave_anyway, (1,)),
                         "contract", "a question was left for another "
                                     "reader by a process that answers")
        real = B.HA.handle_v2_mail

        def never_leave(*args):
            with mock.patch.object(B.R, "_v2_leave_unseen",
                                   lambda *_a: None):
                return real(*args)
        self.assertBites("question_answer_only_off", never_leave, "contract",
                         "a question the process does not answer was not "
                         "left for another reader")

    def test_the_replay_cache_holds_exactly_what_was_acted_on(self):
        self.assertBites("question", self._after(
            lambda a, g: (a[-1].__setitem__("v2:other", 1), g)[1], (2,)),
            "contract", "the replay cache holds ['v2:other', "
                        "'v2:q.bm-job-0001']")
        self.assertBites("question", self._after(
            lambda a, g: (a[-1].clear(), g)[1], (2,)), "contract",
            "the replay cache on disk holds ['v2:q.bm-job-0001'] for a "
            "message not acted on")


class QueryMailOracleTest(_OracleCase):
    module, name = B.QU, "handle_query_mail"
    check = staticmethod(B.check_query)
    seeds = staticmethod(B.seeds_query)

    def test_the_checks_every_attempt_makes(self):
        self._common("happy", "handle_query_mail")

    def test_the_copy_is_not_answered_again(self):
        self.assertBites("happy", self._after(
            lambda a, g: (a[self.SMTP].sent.append(_reply()), g)[1],
            attempts=(2,)), "contract", "a copy of the query was answered "
                                        "again")

    def test_the_reply_goes_to_the_mailbox_under_its_own_subject(self):
        self.assertBites("happy", self._after(
            lambda a, g: (_retag(a[self.SMTP].sent[0], "To",
                                 "elsewhere@example.test"), g)[1],
            attempts=(1,)), "provenance",
            "the reply is addressed to 'elsewhere@example.test'")
        self.assertBites("happy", self._after(
            lambda a, g: (_retag(a[self.SMTP].sent[0], "Subject",
                                 "[HOMING-PIGEON] result x"), g)[1],
            attempts=(1,)), "contract", "the reply's subject is")


class BoardMailOracleTest(_OracleCase):
    module, name = B.ST, "handle_board_mail"
    check = staticmethod(B.check_board_mail)
    seeds = staticmethod(B.seeds_board_mail)
    BOARD = 6

    def test_the_checks_every_attempt_makes(self):
        self._common("submit", "handle_board_mail")

    def test_the_reply_goes_where_the_message_said_under_a_board_subject(self):
        self.assertBites("submit", self._after(
            lambda a, g: (_retag(a[self.SMTP].sent[0], "To",
                                 "elsewhere@example.test"), g)[1],
            attempts=(1,)), "provenance",
            "the reply is addressed to 'elsewhere@example.test'")
        self.assertBites("submit", self._after(
            lambda a, g: (_retag(a[self.SMTP].sent[0], "Subject",
                                 "[HOMING-PIGEON] result x"), g)[1],
            attempts=(1,)), "contract", "the reply's subject is")

    def test_the_board_in_memory_is_the_board_on_disk(self):
        def drift(args, got):
            args[self.BOARD].tasks["ghost"] = {"state": "open"}
            return got
        self.assertBites("submit", self._after(drift, (1,)), "roundtrip",
                         "the board file does not read back as the board "
                         "in memory")


if __name__ == "__main__":
    unittest.main()
