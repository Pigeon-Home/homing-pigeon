#!/usr/bin/env python3
"""Signup on our own site: the first slice of the future first
option (docs/steady/design/cs_canoe.md, "A first option, future:
signup on our own site").

What stands here is the record and the rules, nothing live:

- The address rule: a customer signs up with their Google
  address, and the local part of that address becomes their
  Pigeon Home address (name@gmail.com is reachable as
  name@pigeon-home.ai once approved).
- The forwarding rule: mail to an approved customer's Pigeon
  Home address forwards to the Gmail they signed up with.
- The approval gate: a signup waits as pending until the
  owner approves it by hand. Nothing forwards, and no address
  is live, before that approval. The owner is customer
  number 1 by signing up first and approving himself.
- The page: one box for the Google address and the Google
  sign in button, as it will stand at pigeon-home.ai/signup.

This module opens no sockets, speaks to no Google endpoint,
sends no mail and provisions no account. The host that serves
the page and runs the sign in flow wires it up later. The
store is a JSON file written atomically, in the shape of the
hosting inventory's, so the gate's state survives a restart.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from runner.guard import atomicio as _atomicio
except ImportError:  # run by path: the one writer of a state file
    import importlib.util
    _io_path = os.path.join(_RUNNER_DIR, "guard", "atomicio.py")
    _io_spec = importlib.util.spec_from_file_location(
        "hp_atomicio", _io_path)
    if _io_spec is None or _io_spec.loader is None:
        raise ImportError("runner/guard/atomicio.py not loadable")
    _atomicio = importlib.util.module_from_spec(_io_spec)
    _io_spec.loader.exec_module(_atomicio)

PIGEON_DOMAIN = "pigeon-home.ai"
SIGNUP_PATH = "/signup"
GMAIL_DOMAINS = ("gmail.com", "googlemail.com")

PENDING = "pending"
APPROVED = "approved"
REFUSED = "refused"

_LOCAL_PART = re.compile(r"^[a-z0-9][a-z0-9._%+-]*$")


class SignupError(ValueError):
    """A signup, an approval or an address broke the rules."""


def normalize_gmail(address):
    """The canonical form of a customer's Google address.

    Case folds and surrounding space goes. Anything that is
    not a Gmail address is refused, because the address is
    the identity the whole option hangs on.
    """
    if not isinstance(address, str):
        raise SignupError("a Google address is required")
    candidate = address.strip().lower()
    if candidate.count("@") != 1:
        raise SignupError("not an email address: %r" % (address,))
    local, domain = candidate.split("@")
    if domain not in GMAIL_DOMAINS:
        raise SignupError("not a Gmail address: %r" % (address,))
    if not _LOCAL_PART.match(local) or local.endswith("."):
        raise SignupError("a Gmail address this is not: %r" % (address,))
    return candidate


def pigeon_address(gmail):
    """The Pigeon Home address a Gmail signs up into."""
    local = normalize_gmail(gmail).split("@")[0]
    return "%s@%s" % (local, PIGEON_DOMAIN)


def _now():
    return datetime.now(timezone.utc).isoformat()


class SignupBook:
    """The signup record: who signed up, in what order, and
    who the owner has approved. One JSON file, written
    atomically; a missing file is an empty book."""

    def __init__(self, path):
        self.path = path
        self.records = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.records = list(data.get("signups", []))

    def _save(self):
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        _atomicio.write_json(self.path, {"signups": self.records},
                             indent=2, newline=True)

    def _find(self, gmail):
        for record in self.records:
            if record["gmail"] == gmail:
                return record
        return None

    def signup(self, gmail):
        """Take a signup. Signing up twice is the same signup:
        the record, its number and its state stand as they
        are, so a second visit never renumbers a customer or
        reopens a gate the owner has already settled."""
        gmail = normalize_gmail(gmail)
        found = self._find(gmail)
        if found is not None:
            return found
        record = {
            "number": len(self.records) + 1,
            "gmail": gmail,
            "pigeon_address": pigeon_address(gmail),
            "state": PENDING,
            "signed_up_at": _now(),
        }
        self.records.append(record)
        self._save()
        return record

    def _gate(self, gmail, state):
        gmail = normalize_gmail(gmail)
        record = self._find(gmail)
        if record is None:
            raise SignupError("no signup stands for %r" % (gmail,))
        record["state"] = state
        self._save()
        return record

    def approve(self, gmail):
        """The owner's hand on the gate: this customer is in."""
        return self._gate(gmail, APPROVED)

    def refuse(self, gmail):
        """The owner's hand on the gate: this one is not."""
        return self._gate(gmail, REFUSED)

    def record_for(self, gmail):
        """The record a Gmail holds, or None if it never
        signed up."""
        return self._find(normalize_gmail(gmail))

    def customers(self):
        """Every record, in customer number order."""
        return sorted(self.records, key=lambda r: r["number"])

    def forwarding_target(self, address):
        """Where mail to a Pigeon Home address goes: the
        customer's Gmail, once the owner has approved the
        signup; nowhere before that, and nowhere for an
        address nobody holds."""
        if not isinstance(address, str):
            return None
        wanted = address.strip().lower()
        for record in self.records:
            if record["pigeon_address"] == wanted:
                if record["state"] == APPROVED:
                    return record["gmail"]
                return None
        return None


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<title>Sign up: Pigeon Home</title></head>
<body>
<h1>Pigeon Home</h1>
<p>Sign up with your Google address. Your Gmail becomes your
Pigeon Home address: mail to it forwards to your Gmail once
the owner has approved your signup.</p>
<form method="post" action="/signup">
<label>Your Google address
<input type="email" name="gmail" required>
</label>
<button type="submit">Sign in with Google</button>
</form>
<p>{message}</p>
</body>
</html>
"""


def signup_page(message=""):
    """The signup page: one box, the Google sign in button."""
    return _PAGE.format(message=message)


def handle_signup(book, form):
    """Take one posted signup form. Returns (status, page):
    200 with the customer's number and the gate's word when
    the signup stands, 400 with the refusal on the page when
    the address is not a Gmail."""
    try:
        record = book.signup(form.get("gmail", ""))
    except SignupError as exc:
        return 400, signup_page("That address will not do: %s" % (exc,))
    message = (
        "You are customer number %d. Your address %s is yours "
        "once the owner approves your signup; until then it "
        "forwards nowhere." % (record["number"],
                               record["pigeon_address"]))
    return 200, signup_page(message)
