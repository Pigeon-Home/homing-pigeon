"""Fuzz and edge pins on the signup slice
(runner/cloud/signup.py).

test_cloud_signup.py pins the address rule, the gate and the
forwarding rule on well-shaped inputs. This file runs the
project's bookend family over the address surface — every
ASCII symbol, plus NUL, tab, CR and LF, wrapped front and
back, in runs and in the middle — and pins the book's load
and lookup edges the first file does not reach: a file whose
records stand out of order, a file with no signups key, a
forwarding lookup in the wrong case, and a posted form whose
value is not a string at all.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import signup as SG  # noqa: E402

GOOD = "a.b@gmail.com"
SYMBOLS = [chr(c) for c in range(33, 127)
           if not chr(c).isalnum()]
EDGES = ["\x00", "\t", "\r", "\n"]


class AddressBookendTest(unittest.TestCase):
    """The one normalization the address rule allows is the
    strip of surrounding whitespace; every other bookend is
    part of the address, and an address carrying one is
    refused."""

    def test_whitespace_bookends_normalize(self):
        for mark in (" ", "\t", "\r", "\n", "\r\n", " \t "):
            self.assertEqual(GOOD, SG.normalize_gmail(
                mark + GOOD + mark), repr(mark))

    def test_symbol_bookends_refuse(self):
        for mark in SYMBOLS:
            for candidate in (mark + GOOD, GOOD + mark,
                              mark + GOOD + mark):
                with self.assertRaises(SG.SignupError,
                                       msg=repr(candidate)):
                    SG.normalize_gmail(candidate)

    def test_nul_bookends_refuse(self):
        for candidate in ("\x00" + GOOD, GOOD + "\x00",
                          "\x00" + GOOD + "\x00"):
            with self.assertRaises(SG.SignupError,
                                   msg=repr(candidate)):
                SG.normalize_gmail(candidate)

    def test_runs_of_symbols_refuse(self):
        for candidate in (";" * 10 + GOOD, GOOD + ";" * 10,
                          ";" * 10 + GOOD + ";" * 10,
                          "-" * 10 + GOOD + "-" * 10):
            with self.assertRaises(SG.SignupError,
                                   msg=repr(candidate)):
                SG.normalize_gmail(candidate)

    def test_a_run_of_ordinary_characters_then_an_odd_one(self):
        # Ten ordinary characters and then the odd one, at the
        # front, the back and in the middle of the local part.
        for candidate in ("aaaaaaaaaa;@gmail.com",
                          ";aaaaaaaaaa@gmail.com",
                          "aaaaa;aaaaa@gmail.com",
                          "aaaaaaaaaa@gmail.com;",
                          "aaaaaaaaaa@gmail;.com"):
            with self.assertRaises(SG.SignupError,
                                   msg=repr(candidate)):
                SG.normalize_gmail(candidate)

    def test_symbol_only_and_edge_only_addresses_refuse(self):
        for candidate in (";;;@gmail.com", "\x00@gmail.com",
                          "\x00", ";;;", "\t\r\n", "@",
                          "a@b@gmail.com", "a@@gmail.com"):
            with self.assertRaises(SG.SignupError,
                                   msg=repr(candidate)):
                SG.normalize_gmail(candidate)

    def test_the_domain_takes_no_bookends_either(self):
        for candidate in ("a@;gmail.com", "a@gmail.com;",
                          "a@ gmail.com", "a@gmail .com",
                          "a@gmail.com\x00"):
            with self.assertRaises(SG.SignupError,
                                   msg=repr(candidate)):
                SG.normalize_gmail(candidate)

    def test_non_string_addresses_refuse(self):
        for candidate in (None, 42, 3.5, b"a.b@gmail.com",
                          ["a.b@gmail.com"], {"a": 1}):
            with self.assertRaises(SG.SignupError,
                                   msg=repr(candidate)):
                SG.normalize_gmail(candidate)


class BookLoadEdgeTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "signups.json")

    def _write(self, payload):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_customers_come_out_in_number_order(self):
        # The file is the record, and a file whose records
        # stand out of order still reads back in customer
        # number order.
        def record(number, gmail):
            return {"number": number, "gmail": gmail,
                    "pigeon_address":
                        gmail.split("@")[0] + "@pigeon-home.ai",
                    "state": SG.PENDING,
                    "signed_up_at": "2026-11-20T00:00:00+00:00"}
        self._write({"signups": [record(2, "b@gmail.com"),
                                 record(1, "a@gmail.com"),
                                 record(3, "c@gmail.com")]})
        book = SG.SignupBook(self.path)
        self.assertEqual([1, 2, 3],
                         [r["number"] for r in book.customers()])

    def test_a_file_with_no_signups_key_is_an_empty_book(self):
        self._write({"something_else": []})
        book = SG.SignupBook(self.path)
        self.assertEqual([], book.customers())
        record = book.signup("a@gmail.com")
        self.assertEqual(1, record["number"])

    def test_record_for_an_unknown_gmail_is_none(self):
        book = SG.SignupBook(self.path)
        book.signup(GOOD)
        self.assertIsNone(book.record_for("ghost@gmail.com"))

    def test_forwarding_lookup_ignores_case_and_space(self):
        book = SG.SignupBook(self.path)
        book.signup("Owner.Person@gmail.com")
        book.approve("owner.person@gmail.com")
        self.assertEqual(
            "owner.person@gmail.com",
            book.forwarding_target("  OWNER.PERSON@PIGEON-HOME.AI "))

    def test_forwarding_to_a_non_string_is_nowhere(self):
        book = SG.SignupBook(self.path)
        for address in (None, 42, b"a@pigeon-home.ai"):
            self.assertIsNone(book.forwarding_target(address))


class HandlerEdgeTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.book = SG.SignupBook(
            os.path.join(self.tmp.name, "signups.json"))

    def test_a_non_string_form_value_is_refused(self):
        for value in (None, 42, ["a.b@gmail.com"], {"x": 1}):
            status, _page = SG.handle_signup(
                self.book, {"gmail": value})
            self.assertEqual(400, status, repr(value))
        self.assertEqual([], self.book.customers())

    def test_a_bookended_form_value_is_refused(self):
        for value in (";a.b@gmail.com;", "\x00a.b@gmail.com",
                      "a.b@gmail.com\x00"):
            status, _page = SG.handle_signup(
                self.book, {"gmail": value})
            self.assertEqual(400, status, repr(value))
        self.assertEqual([], self.book.customers())

    def test_a_whitespace_bookended_form_value_signs_up(self):
        status, _page = SG.handle_signup(
            self.book, {"gmail": "  a.b@gmail.com\t"})
        self.assertEqual(200, status)
        self.assertIsNotNone(self.book.record_for(GOOD))

    def test_the_page_carries_a_braced_message_verbatim(self):
        # The message rides into the page as a value, never as
        # a format string: braces and percent signs in it come
        # through whole.
        page = SG.signup_page("100% {sure} about it")
        self.assertIn("100% {sure} about it", page)


if __name__ == "__main__":
    unittest.main()
