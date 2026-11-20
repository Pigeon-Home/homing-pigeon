#!/usr/bin/env python3
"""Tests for the signup slice of the future first option
(runner/cloud/signup.py): the address rule, the approval gate,
the forwarding rule and the page.

No test touches a network, a mailbox or a real account: the
book lives in a temp folder throughout, and the owner in
these tests is a fixture address, customer number 1 by
signing up first, exactly as the design has it.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import signup as SG  # noqa: E402

OWNER = "owner.person@gmail.com"
SECOND = "second.person@gmail.com"


class AddressRuleTest(unittest.TestCase):
    def test_gmail_becomes_the_pigeon_address(self):
        self.assertEqual("owner.person@pigeon-home.ai",
                         SG.pigeon_address(OWNER))

    def test_the_address_is_normalized(self):
        self.assertEqual(OWNER, SG.normalize_gmail(
            "  Owner.Person@Gmail.COM "))

    def test_googlemail_signs_up_too(self):
        self.assertEqual("a@pigeon-home.ai",
                         SG.pigeon_address("a@googlemail.com"))

    def test_a_foreign_domain_is_refused(self):
        for address in ("a@example.com", "a@pigeon-home.ai",
                        "a@gmail.com.evil.example"):
            with self.assertRaises(SG.SignupError):
                SG.normalize_gmail(address)

    def test_malformed_addresses_are_refused(self):
        for address in ("", "no-at-sign", "a@@gmail.com",
                        "@gmail.com", "a b@gmail.com",
                        ".a@gmail.com", "a.@gmail.com", None):
            with self.assertRaises(SG.SignupError):
                SG.normalize_gmail(address)


class BookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "signups.json")
        self.book = SG.SignupBook(self.path)

    def test_first_signup_is_customer_1_and_pending(self):
        record = self.book.signup(OWNER)
        self.assertEqual(1, record["number"])
        self.assertEqual(SG.PENDING, record["state"])
        self.assertEqual("owner.person@pigeon-home.ai",
                         record["pigeon_address"])

    def test_numbers_grow_in_signup_order(self):
        self.book.signup(OWNER)
        record = self.book.signup(SECOND)
        self.assertEqual(2, record["number"])
        self.assertEqual([1, 2], [r["number"]
                                  for r in self.book.customers()])

    def test_signing_up_twice_is_one_signup(self):
        first = self.book.signup(OWNER)
        again = self.book.signup(OWNER.upper())
        self.assertEqual(first["number"], again["number"])
        self.assertEqual(1, len(self.book.customers()))

    def test_a_repeat_signup_keeps_the_gate_as_settled(self):
        self.book.signup(OWNER)
        self.book.approve(OWNER)
        again = self.book.signup(OWNER)
        self.assertEqual(SG.APPROVED, again["state"])

    def test_pending_forwards_nowhere(self):
        self.book.signup(OWNER)
        self.assertIsNone(self.book.forwarding_target(
            "owner.person@pigeon-home.ai"))

    def test_approved_forwards_to_the_gmail(self):
        self.book.signup(OWNER)
        self.book.approve(OWNER)
        self.assertEqual(OWNER, self.book.forwarding_target(
            "owner.person@pigeon-home.ai"))

    def test_refused_forwards_nowhere(self):
        self.book.signup(OWNER)
        self.book.approve(OWNER)
        self.book.refuse(OWNER)
        self.assertIsNone(self.book.forwarding_target(
            "owner.person@pigeon-home.ai"))

    def test_the_gate_only_moves_records_that_stand(self):
        with self.assertRaises(SG.SignupError):
            self.book.approve(SECOND)
        with self.assertRaises(SG.SignupError):
            self.book.refuse(SECOND)

    def test_an_unknown_address_forwards_nowhere(self):
        self.assertIsNone(self.book.forwarding_target(
            "ghost@pigeon-home.ai"))
        self.assertIsNone(self.book.forwarding_target(None))

    def test_the_book_survives_a_reload(self):
        self.book.signup(OWNER)
        self.book.approve(OWNER)
        reopened = SG.SignupBook(self.path)
        record = reopened.record_for(OWNER)
        self.assertEqual(SG.APPROVED, record["state"])
        self.assertEqual(OWNER, reopened.forwarding_target(
            "owner.person@pigeon-home.ai"))

    def test_the_owner_is_customer_1_by_signing_up_first(self):
        record = self.book.signup(OWNER)
        self.book.approve(OWNER)
        self.assertEqual(1, record["number"])
        self.assertEqual(OWNER, self.book.forwarding_target(
            record["pigeon_address"]))


class SaveShapeTest(unittest.TestCase):
    """The book's save goes through the one atomic writer
    (runner/guard/atomicio.py): the pin in test_atomicio failed
    the first slice for hand-rolling its temp file, and these
    tests hold the shape the helper leaves on disk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "signups.json")
        self.book = SG.SignupBook(self.path)

    def test_the_saved_file_is_indented_json_with_a_trailing_newline(self):
        self.book.signup(OWNER)
        with open(self.path, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.endswith("\n"))
        self.assertIn('\n  "signups": [', text)
        import json
        self.assertEqual(OWNER, json.loads(text)["signups"][0]["gmail"])

    def test_a_save_leaves_no_temp_file_behind(self):
        self.book.signup(OWNER)
        self.book.signup(SECOND)
        self.assertEqual(["signups.json"], sorted(os.listdir(self.tmp.name)))

    def test_a_save_into_a_nested_folder_creates_it(self):
        deep = os.path.join(self.tmp.name, "a", "b", "signups.json")
        book = SG.SignupBook(deep)
        book.signup(OWNER)
        self.assertTrue(os.path.exists(deep))
        self.assertEqual(OWNER, SG.SignupBook(deep).record_for(OWNER)["gmail"])

    def test_every_state_change_is_saved(self):
        self.book.signup(OWNER)
        self.book.approve(OWNER)
        self.assertEqual(SG.APPROVED,
                         SG.SignupBook(self.path).record_for(OWNER)["state"])
        self.book.refuse(OWNER)
        self.assertEqual(SG.REFUSED,
                         SG.SignupBook(self.path).record_for(OWNER)["state"])


class PageTest(unittest.TestCase):
    def test_the_page_has_one_box_and_the_google_sign_in(self):
        page = SG.signup_page()
        self.assertEqual(1, page.count("<input"))
        self.assertIn('name="gmail"', page)
        self.assertIn("Sign in with Google", page)
        self.assertIn('action="/signup"', page)

    def test_the_handler_takes_a_signup(self):
        with tempfile.TemporaryDirectory() as folder:
            book = SG.SignupBook(os.path.join(folder, "s.json"))
            status, page = SG.handle_signup(book, {"gmail": OWNER})
            self.assertEqual(200, status)
            self.assertIn("customer number 1", page)
            record = book.record_for(OWNER)
            self.assertEqual(SG.PENDING, record["state"])

    def test_the_handler_refuses_a_bad_address(self):
        with tempfile.TemporaryDirectory() as folder:
            book = SG.SignupBook(os.path.join(folder, "s.json"))
            status, _page = SG.handle_signup(
                book, {"gmail": "a@example.com"})
            self.assertEqual(400, status)
            self.assertEqual([], book.customers())

    def test_the_handler_refuses_an_empty_form(self):
        with tempfile.TemporaryDirectory() as folder:
            book = SG.SignupBook(os.path.join(folder, "s.json"))
            status, _page = SG.handle_signup(book, {})
            self.assertEqual(400, status)
            self.assertEqual([], book.customers())


if __name__ == "__main__":
    unittest.main()
