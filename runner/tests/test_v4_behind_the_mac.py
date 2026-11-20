"""Behind the signature: whose text is it (finding F16).

docs/infrastructure-documents/proofs/v4-behind-the-mac.md states
the rule. The signature covers the body and nothing around it, so
the subject's id is a stranger's text until the gate has set it
against the body's id. C13 has its place: version, type and id
are checked first behind the signature, before anything else in
the body is acted on, and before any record names the job.

This module holds that on every run of the suite, 5 ways:

  the model      gate.tla, written here apart from the TLA+ file
                 and walked whole: every handling, in both orders
                 of the stretch, in every configuration. The
                 counts are the prediction for the checker.
  the gate       the real handle_mail on every arrival of the
                 stretch: its refusal is the model's, and nothing
                 it writes carries the subject's id unless the id
                 was bound.
  the labels     a walk of the gate's own source that gives every
                 name its label and follows it to every use.
  the ladder     a signed body under a stranger's envelope, each
                 text outside the signature grown on the series.
  the page       the figures above are the page's.
"""
import ast
import contextlib
import io
import itertools
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs")
PAGE = os.path.join(PROOFS, "v4-behind-the-mac.md")
GATE = os.path.join(PROOFS, "gate.tla")
MAIL_PY = os.path.join(ROOT, "runner", "ops", "mail.py")


# ---- The model: gate.tla, written apart and walked whole

BOOLS = ("panic", "rawOver", "isFreshJob", "signed", "innerMismatch",
         "encrypted", "audienceOk", "surrogate", "scriptOver",
         "versionOk", "typeOk", "idOk", "fresh", "policyOk",
         "constraintDenied", "sensor", "dryRun", "cancelled")
CLAIMS = ("free", "taken", "onRecord")

# The 5 checks between the signature and freshness. Binding first
# is the order that stands. The other is the order as it was.
STRETCH = {
    True: ("identity", "cleartext", "audience", "encodable", "script"),
    False: ("cleartext", "audience", "encodable", "script", "identity"),
}
BEFORE = ("panic", "raw size", "dispatch", "verification")
AFTER = ("freshness", "key policy", "constraints", "sensor", "review",
         "dry run", "claim", "record")

# What each check reads of the message. Every member is read at 1
# check, so a message's path is fixed by its members in this order.
READS = {
    "panic": ("panic",), "raw size": ("rawOver",),
    "dispatch": ("isFreshJob",),
    "verification": ("signed", "innerMismatch"),
    "identity": ("versionOk", "typeOk", "idOk"),
    "cleartext": ("encrypted",), "audience": ("audienceOk",),
    "encodable": ("surrogate",), "script": ("scriptOver",),
    "freshness": ("fresh",), "key policy": ("policyOk",),
    "constraints": ("constraintDenied",), "sensor": ("sensor",),
    "review": (), "dry run": ("dryRun",), "claim": ("claim",),
    "record": ("cancelled",),
}

CONFIGURATIONS = {
    "gateenforce.cfg": ("enforce", False),
    "gatedefault.cfg": ("off", False),
    "gateaudit.cfg": ("audit", False),
    "gatecleartext.cfg": ("enforce", True),
}


def checks(bind_first):
    return BEFORE + STRETCH[bind_first] + AFTER


def decide(check, m, flags, audience, cleartext):
    """1 step of the gate: (how the handling goes on, the flags
    after it). `flags` is (noted, named, read): the audit has a
    record, a record names the job, and the gate has acted on a
    member of the body other than its version, type and id."""
    noted, named, read = flags
    if check == "panic":
        return ("refuse" if m["panic"] else "pass"), flags
    if check == "raw size":
        return ("refuse" if m["rawOver"] else "pass"), flags
    if check == "dispatch":
        return ("pass" if m["isFreshJob"] else "refuse"), flags
    if check == "verification":
        good = m["signed"] and not m["innerMismatch"]
        return ("pass" if good else "refuse"), flags
    if check == "identity":
        good = m["versionOk"] and m["typeOk"] and m["idOk"]
        return ("pass" if good else "refuse"), flags
    if check == "cleartext":
        if not m["encrypted"] and not cleartext:
            return "refuse", flags
        if not m["encrypted"]:
            # The line that says a job arrived in clear text.
            return "pass", (noted, True, read)
        return "pass", flags
    if check == "audience":
        # The check reads the body's audience in every mode. A
        # mismatch is written into the security audit, with the
        # job's name, unless the feature is off.
        if audience == "enforce" and not m["audienceOk"]:
            return "refuse", (noted, True, True)
        if audience == "audit" and not m["audienceOk"]:
            return "pass", (True, True, True)
        return "pass", (noted, named, True)
    if check == "encodable":
        return ("refuse" if m["surrogate"] else "pass"), (noted, named, True)
    if check == "script":
        return ("refuse" if m["scriptOver"] else "pass"), (noted, named, True)
    if check == "freshness":
        return ("pass" if m["fresh"] else "refuse"), flags
    if check == "key policy":
        return ("pass" if m["policyOk"] else "refuse"), flags
    if check == "constraints":
        return ("refuse" if m["constraintDenied"] else "pass"), flags
    if check == "sensor":
        return ("sensor" if m["sensor"] else "pass"), flags
    if check == "review":
        return "pass", flags
    if check == "dry run":
        return ("dry" if m["dryRun"] else "pass"), flags
    if check == "claim":
        if m["claim"] == "taken":
            return "refuse", flags
        return ("resend" if m["claim"] == "onRecord" else "pass"), flags
    if check == "record":
        return ("refuse" if m["cancelled"] else "execute"), flags
    raise KeyError(check)


def clauses(m, audience, cleartext):
    """P1's clauses, as gate.tla's Clauses states them."""
    return (not m["panic"] and not m["rawOver"] and m["isFreshJob"]
            and m["signed"] and not m["innerMismatch"]
            and (m["encrypted"] or cleartext)
            and (audience != "enforce" or m["audienceOk"])
            and not m["surrogate"] and not m["scriptOver"]
            and m["versionOk"] and m["typeOk"] and m["idOk"]
            and m["fresh"] and m["policyOk"]
            and not m["constraintDenied"] and not m["sensor"]
            and not m["dryRun"] and m["claim"] == "free"
            and not m["cancelled"])


INVARIANTS = {
    # The 2 this page adds.
    "NamedByTheSignedId":
        lambda m, outcome, flags, mode: not flags[1] or m["idOk"],
    "OneVersionBeforeTheBody":
        lambda m, outcome, flags, mode:
            not flags[2] or (m["versionOk"] and m["typeOk"]),
    # P1's own, on a finished handling.
    "P1Inv":
        lambda m, outcome, flags, mode:
            outcome != "execute" or clauses(m, *mode),
    "NothingExecutes":
        lambda m, outcome, flags, mode: outcome != "execute",
}

# The members an invariant asks about before the gate reads them.
# The walk settles these at the start, so every state knows them.
ASKED_EARLY = ("versionOk", "typeOk", "idOk")


def walk(audience, cleartext, bind_first):
    """Every handling of the model, grouped by what the gate has
    read so far. A group stands for every message that agrees on
    the members read, so its weight is the count of those
    messages, and the weights add to the checker's own count of
    distinct states.

    Returns the counts, the finished handlings by outcome, and
    for each invariant the count of states that break it with the
    shortest path to 1 of them."""
    order = checks(bind_first)
    mode = (audience, cleartext)
    total_bools = len(BOOLS)
    distinct = 0
    finished = {}
    broken = {name: [0, None] for name in INVARIANTS}
    deepest = 0

    def weight(m):
        unread = total_bools - sum(1 for name in BOOLS if name in m)
        return (2 ** unread) * (1 if "claim" in m else len(CLAIMS))

    def ask(m, outcome, flags, path):
        for name, holds in INVARIANTS.items():
            if name in ("P1Inv", "NothingExecutes") and outcome is None:
                continue
            if not holds(m, outcome, flags, mode):
                broken[name][0] += weight(m)
                if broken[name][1] is None \
                        or len(path) < len(broken[name][1]):
                    broken[name][1] = list(path)

    def go(at, m, flags, path):
        nonlocal distinct, deepest
        distinct += weight(m)
        deepest = max(deepest, len(path))
        ask(m, None, flags, path)
        check = order[at]
        names = [name for name in READS[check] if name not in m]
        choices = [CLAIMS if name == "claim" else (True, False)
                   for name in names]
        for values in itertools.product(*choices):
            known = dict(m)
            known.update(zip(names, values))
            verdict, after = decide(check, known, flags, audience,
                                    cleartext)
            step = path + [(check, verdict)]
            if verdict == "pass":
                go(at + 1, known, after, step)
            else:
                distinct += weight(known)
                deepest = max(deepest, len(step))
                finished[verdict] = finished.get(verdict, 0) \
                    + weight(known)
                ask(known, verdict, after, step)

    for values in itertools.product((True, False),
                                    repeat=len(ASKED_EARLY)):
        go(0, dict(zip(ASKED_EARLY, values)), (False, False, False), [])
    return {"distinct": distinct,
            "generated": distinct + sum(finished.values()),
            "depth": deepest + 1,
            "finished": finished,
            "broken": {name: tuple(found)
                       for name, found in broken.items()}}


def every_message():
    for values in itertools.product((True, False), repeat=len(BOOLS)):
        m = dict(zip(BOOLS, values))
        for claim in CLAIMS:
            m["claim"] = claim
            yield m


def handling(m, audience, cleartext, bind_first):
    """1 message's handling, step by step: the states it passes
    through, as (check, verdict, flags)."""
    flags, states = (False, False, False), []
    for check in checks(bind_first):
        verdict, flags = decide(check, m, flags, audience, cleartext)
        states.append((check, verdict, flags))
        if verdict != "pass":
            break
    return states


class TheModelBindsFirst(unittest.TestCase):
    """gate.tla, walked whole in both orders of the stretch. The
    counts were this module's before the checker was run, and the
    checker's run gave the same."""

    @classmethod
    def setUpClass(cls):
        cls.walked = {
            (name, bind_first): walk(audience, cleartext, bind_first)
            for name, (audience, cleartext) in CONFIGURATIONS.items()
            for bind_first in (True, False)}

    def test_the_walk_is_every_message_taken_1_by_1(self):
        # The walk groups messages. Here 786,432 are taken singly,
        # in the configuration that turns every seam the stretch
        # has, and the 2 ways of counting agree in both orders.
        for bind_first in (True, False):
            distinct, finished = 0, {}
            broken = {"NamedByTheSignedId": 0,
                      "OneVersionBeforeTheBody": 0}
            for m in every_message():
                states = handling(m, "audit", True, bind_first)
                distinct += 1 + len(states)
                last = states[-1][1]
                finished[last] = finished.get(last, 0) + 1
                for _check, _verdict, flags in states:
                    if flags[1] and not m["idOk"]:
                        broken["NamedByTheSignedId"] += 1
                    if flags[2] and not (m["versionOk"] and m["typeOk"]):
                        broken["OneVersionBeforeTheBody"] += 1
            got = walk("audit", True, bind_first)
            self.assertEqual(786432, sum(finished.values()))
            self.assertEqual(distinct, got["distinct"], bind_first)
            self.assertEqual(finished, got["finished"], bind_first)
            for name, count in broken.items():
                self.assertEqual(count, got["broken"][name][0],
                                 (name, bind_first))

    def test_as_it_was_the_model_shows_the_finding(self):
        # B1. The order the code performed until 2026-11-19. A
        # record names a job whose id is not the body's, and the
        # body is read before its version is known. The second
        # column is the count of states that break the invariant,
        # the third the states on the shortest way to 1 of them.
        for name, invariant, states, shortest in (
                ("gateenforce.cfg", "NamedByTheSignedId", 3072, 7),
                ("gatedefault.cfg", "NamedByTheSignedId", 0, None),
                ("gateaudit.cfg", "NamedByTheSignedId", 8448, 7),
                ("gatecleartext.cfg", "NamedByTheSignedId", 20736, 6),
                ("gateenforce.cfg", "OneVersionBeforeTheBody", 17280, 7),
                ("gatedefault.cfg", "OneVersionBeforeTheBody", 25344, 7),
                ("gateaudit.cfg", "OneVersionBeforeTheBody", 25344, 7),
                ("gatecleartext.cfg", "OneVersionBeforeTheBody",
                 34560, 7)):
            count, path = self.walked[name, False]["broken"][invariant]
            self.assertEqual(states, count, (name, invariant))
            self.assertEqual(shortest, path and len(path) + 1,
                             (name, invariant))
        # The shortest of all: 5 steps, and the fifth is the line
        # for a job in clear text.
        _count, path = self.walked["gatecleartext.cfg", False][
            "broken"]["NamedByTheSignedId"]
        self.assertEqual(
            ["panic", "raw size", "dispatch", "verification", "cleartext"],
            [check for check, _verdict in path])

    def test_binding_first_the_2_invariants_hold_everywhere(self):
        # B2. No state of any configuration breaks either.
        for name in CONFIGURATIONS:
            broken = self.walked[name, True]["broken"]
            for invariant in ("NamedByTheSignedId",
                              "OneVersionBeforeTheBody", "P1Inv"):
                self.assertEqual((0, None), broken[invariant],
                                 (name, invariant))
            # The model still lets a good job through.
            self.assertGreater(broken["NothingExecutes"][0], 0, name)

    def test_the_same_messages_run_in_both_orders(self):
        # B2. The order changes which refusal a message gets. It
        # does not change which messages run, are resent, are a
        # dry run, or leave by the sensor branch.
        for name in CONFIGURATIONS:
            self.assertEqual(self.walked[name, False]["finished"],
                             self.walked[name, True]["finished"], name)
        self.assertEqual(
            {"execute": 1, "dry": 6, "resend": 2, "sensor": 12,
             "refuse": 786411},
            self.walked["gateenforce.cfg", True]["finished"])

    def test_the_counts_are_the_prediction_for_the_checker(self):
        # (distinct states, states generated, depth) as TLC prints
        # them. The first 3 rows as-it-was are the checker's own
        # record of the model before this change, in stage2.md.
        for name, bind_first, counts in (
                ("gateenforce.cfg", False, (2309000, 3095432, 18)),
                ("gatedefault.cfg", False, (2320144, 3106576, 18)),
                ("gateaudit.cfg", False, (2320144, 3106576, 18)),
                ("gateenforce.cfg", True, (2291720, 3078152, 18)),
                ("gatedefault.cfg", True, (2293264, 3079696, 18)),
                ("gateaudit.cfg", True, (2293264, 3079696, 18)),
                ("gatecleartext.cfg", True, (2294800, 3081232, 18))):
            got = self.walked[name, bind_first]
            self.assertEqual(
                counts,
                (got["distinct"], got["generated"], got["depth"]),
                (name, bind_first))

    def test_the_model_file_states_what_was_walked(self):
        model = MODELS._read(GATE)
        flat = " ".join(model.split())
        self.assertIn("CONSTANTS AudienceMode, AllowCleartext, BindFirst",
                      flat)
        for bind_first, words in (
                (True, "THEN"), (False, "ELSE")):
            self.assertIn("%s <<%s>>" % (words, ", ".join(
                '"%s"' % check for check in STRETCH[bind_first])), flat)
        self.assertIn("NamedByTheSignedId == named => m.idOk", flat)
        self.assertIn("OneVersionBeforeTheBody == "
                      "read => (m.versionOk /\\ m.typeOk)", flat)
        # Every member the walk reads is a member of the model's
        # message, and no other.
        members = set(BOOLS) | {"claim"}
        self.assertEqual(members, {
            line.split(":")[0].strip()
            for line in model.split("Messages == [")[1]
            .split("]")[0].splitlines() if ":" in line})

    def test_the_configurations_are_the_ones_walked(self):
        for name, (audience, cleartext) in CONFIGURATIONS.items():
            flat = " ".join(MODELS._read(
                os.path.join(PROOFS, name)).split())
            self.assertIn('AudienceMode = "%s"' % audience, flat, name)
            self.assertIn("AllowCleartext = %s"
                          % str(cleartext).upper(), flat, name)
            self.assertIn("BindFirst = TRUE", flat, name)
            checked = BIND.cfg_invariants(name)
            for invariant in ("P1Inv", "SensorInv", "NamedByTheSignedId",
                              "OneVersionBeforeTheBody"):
                self.assertIn(invariant, checked, name)
        # The witnesses turn the seam back, and each asks for the
        # 1 invariant it is there to break.
        for name, audience, cleartext, invariant in (
                ("gatewitnessunbound.cfg", "enforce", True,
                 "NamedByTheSignedId"),
                ("gatewitnessnamed.cfg", "audit", False,
                 "NamedByTheSignedId"),
                ("gatewitnessversion.cfg", "enforce", False,
                 "OneVersionBeforeTheBody")):
            flat = " ".join(MODELS._read(
                os.path.join(PROOFS, name)).split())
            self.assertIn("BindFirst = FALSE", flat, name)
            self.assertIn('AudienceMode = "%s"' % audience, flat, name)
            self.assertIn("AllowCleartext = %s"
                          % str(cleartext).upper(), flat, name)
            self.assertEqual([invariant], BIND.cfg_invariants(name), name)
            # And the walk says the checker must find it.
            form = next(key for key, value in CONFIGURATIONS.items()
                        if value == (audience, cleartext)) \
                if (audience, cleartext) in CONFIGURATIONS.values() \
                else None
            got = walk(audience, cleartext, False)["broken"][invariant]
            self.assertGreater(got[0], 0, (name, form))


# ---- The gate: the real handle_mail, on every arrival of the stretch

REFUSALS = {
    "version": "unsupported version/type",
    "identity": "job_id mismatch between subject and body",
    "cleartext": "cleartext job refused",
    "audience": "security policy (audience)",
    "script": "script exceeds max_script_bytes",
}


def ask(raw, allowed, cfg_extra=None, verbose=False):
    """1 arrival at the real gate, in a folder of its own: what
    ran, the log's lines, the mailbox's marks, and every byte the
    gate wrote under its folder."""
    executed, notes = [], []

    def execute(_cfg, job, _base):
        executed.append(job)
        return dict(DOOR._OK_RESULT)

    def send(_smtp, _cfg, _subject, _body, to=None):
        return None

    def note(msg, level="INFO"):
        notes.append(msg)

    with tempfile.TemporaryDirectory() as folder:
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": DOOR.SECRET, "base_dir": folder,
               "oracle_opinion_mode": "off"}
        cfg.update(cfg_extra or {})
        imap = DOOR._IMAP2()
        patches = [mock.patch.object(RUNNER, "execute_job", execute),
                   mock.patch.object(RUNNER, "send_mail", send),
                   mock.patch.object(RUNNER, "log", note)]
        if verbose:
            patches.append(mock.patch.object(RUNNER, "vlog", note))
        RUNNER._set_allow_cleartext_jobs(allowed)
        try:
            with contextlib.ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                stack.enter_context(
                    contextlib.redirect_stdout(io.StringIO()))
                RUNNER.handle_mail(
                    cfg, imap, DOOR._SMTP2(), 3, raw, folder, {},
                    RUNNER.build_secrets(cfg),
                    Namespace(dry_run=False, no_send=False), None)
        finally:
            RUNNER._set_allow_cleartext_jobs(False)
        written = b""
        for name in sorted(PRE.kept(folder)):
            with open(os.path.join(folder, name), "rb") as handle:
                written += handle.read()
    return Namespace(executed=executed, notes=notes,
                     marks=imap.store_calls, written=written)


def arrival(number, sealed, audience_ok, version_ok, type_ok, id_ok,
            subject_id=None, script="x" * 100):
    """1 mail for 1 way the checks of the stretch can pass or
    fail: (the mail, the subject's id, the body's id). The body
    is signed by the runner's own key in every case."""
    body_id = "stretch-%d" % number
    if subject_id is None:
        subject_id = body_id if id_ok else "another-%d" % number
    job = DOOR._job2(body_id, kind="exec", script=script,
                     aud="runner-1" if audience_ok else "runner-2")
    if not version_ok:
        job["v"] = 2
    if not type_ok:
        job["type"] = "query"
    body = RUNNER.sign_payload(job, DOOR.SECRET)
    if sealed:
        # Sealed under the subject's id, so the cipher's own
        # binding holds and the mail reaches the stretch.
        body = jobcrypto.encrypt_body(
            body, DOOR.SECRET, job_id=subject_id, key_id="",
            sign=RUNNER.sign_payload)
    return (PRE._mail("[HOMING-PIGEON] job %s" % subject_id, body),
            subject_id, body_id)


def settings(mode, script_over):
    return {"runner_id": "runner-1",
            "security": {"modes": {"audience": mode}},
            "max_script_bytes": 10 if script_over else 1048576}


def model_says(sealed, allowed, mode, audience_ok, script_over,
               version_ok, type_ok, id_ok):
    """What gate.tla, binding first, does with the message: the
    check that refuses it, or None when it runs."""
    m = {"encrypted": sealed, "audienceOk": audience_ok,
         "surrogate": False, "scriptOver": script_over,
         "versionOk": version_ok, "typeOk": type_ok, "idOk": id_ok}
    flags = (False, False, False)
    for check in STRETCH[True]:
        verdict, flags = decide(check, m, flags, mode, allowed)
        if verdict != "pass":
            if check == "identity":
                check = "identity" if (version_ok and type_ok) \
                    else "version"
            return check, flags
    return None, flags


class TheRealGateBindsFirst(unittest.TestCase):
    """B3 and B4. C13 in its place, on the code that runs."""

    def every_arrival(self):
        number = 0
        for allowed in (False, True):
            for mode in ("off", "audit", "enforce"):
                for flags in itertools.product((True, False), repeat=6):
                    number += 1
                    yield (number, allowed, mode) + flags

    def test_the_gate_s_refusal_is_the_model_s_on_every_arrival(self):
        # 6 members of the message, 3 modes of the audience, with
        # clear text allowed and not: 384 arrivals. On each the
        # real gate does what the model, binding first, does.
        asked = ran = 0
        refused = {}
        for (number, allowed, mode, sealed, audience_ok, script_over,
             version_ok, type_ok, id_ok) in self.every_arrival():
            raw, subject_id, _body_id = arrival(
                number, sealed, audience_ok, version_ok, type_ok, id_ok)
            out = ask(raw, allowed, settings(mode, script_over))
            where, _flags = model_says(
                sealed, allowed, mode, audience_ok, script_over,
                version_ok, type_ok, id_ok)
            case = (allowed, mode, sealed, audience_ok, script_over,
                    version_ok, type_ok, id_ok)
            asked += 1
            self.assertEqual(1, out.marks, case)
            if where is None:
                self.assertEqual(1, len(out.executed), (case, out.notes))
                ran += 1
                continue
            self.assertEqual([], out.executed, case)
            said = [line for line in out.notes
                    if line.startswith("rejecting seq 3: ")]
            self.assertEqual(1, len(said), (case, out.notes))
            self.assertIn(REFUSALS[where], said[0], case)
            refused[where] = refused.get(where, 0) + 1
        self.assertEqual(384, asked)
        # 1 in 8 passes the 3 of C13. Of those 48, the rest of the
        # stretch refuses 33 and lets 15 through.
        self.assertEqual(
            {"version": 288, "identity": 48, "cleartext": 12,
             "audience": 6, "script": 15},
            refused)
        self.assertEqual(15, ran)

    def test_no_record_names_a_job_by_an_id_that_is_not_bound(self):
        # The subject's id of a mail whose 2 ids differ is in the
        # gate's first line, cut, and in nothing else the gate
        # writes: no later line, no entry of the security audit,
        # no event, no file. The same for a body of another
        # version: its audience is never read, so the audit has
        # no entry for it.
        unbound = other_version = 0
        for (number, allowed, mode, sealed, audience_ok, script_over,
             version_ok, type_ok, id_ok) in self.every_arrival():
            if id_ok and version_ok and type_ok:
                continue
            raw, subject_id, body_id = arrival(
                number, sealed, audience_ok, version_ok, type_ok, id_ok)
            out = ask(raw, allowed, settings(mode, script_over),
                      verbose=True)
            case = (allowed, mode, sealed, audience_ok, script_over,
                    version_ok, type_ok, id_ok)
            self.assertNotIn(b"runner_id_mismatch", out.written, case)
            self.assertNotIn(b"audience", out.written, case)
            self.assertFalse(
                [line for line in out.notes if "clear text" in line], case)
            if not id_ok:
                unbound += 1
                self.assertIn("job %s submitted by" % subject_id,
                              out.notes[0], case)
                for line in out.notes[1:]:
                    self.assertNotIn(subject_id, line, case)
                self.assertNotIn(subject_id.encode(), out.written, case)
                self.assertNotIn(body_id.encode(), out.written, case)
            else:
                other_version += 1
        self.assertEqual((192, 144), (unbound, other_version))

    def test_c13_stands_first_behind_the_signature_in_the_source(self):
        # The place itself, read off handle_mail: the statement
        # that asks for the signature, and straight after it the
        # 2 statements of C13, each a refusal and a return.
        function = gate_function()
        at = next(place for place, node in enumerate(function.body)
                  if isinstance(node, ast.Try)
                  and "_verify_and_decrypt" in ast.unparse(node))
        version, identity = function.body[at + 1:at + 3]
        for node, test, why in (
                (version,
                 "not _runner()._version_ok(job.get('v')) "
                 "or job.get('type') != 'job'",
                 "unsupported version/type"),
                (identity, "job.get('job_id') != job_id",
                 "job_id mismatch between subject and body")):
            self.assertIsInstance(node, ast.If)
            self.assertEqual(test, ast.unparse(node.test))
            self.assertEqual("reject(%r)" % why,
                             ast.unparse(node.body[0]))
            self.assertIsInstance(node.body[1], ast.Return)
            self.assertEqual([], node.orelse)

    def test_c13_a_body_of_another_version_is_read_for_nothing_else(self):
        # Version 2 with a wrong audience under enforce and a
        # script over the cap, in clear text that is not allowed:
        # 4 refusals wait. The gate gives the version's.
        raw, _subject_id, _body_id = arrival(
            900, False, False, False, True, True)
        out = ask(raw, False, settings("enforce", True))
        self.assertEqual([], out.executed)
        self.assertEqual(["rejecting seq 3: unsupported version/type"],
                         [line for line in out.notes
                          if line.startswith("rejecting")])
        self.assertEqual(b"", out.written)

    def test_c13_a_body_under_another_subject_is_named_in_no_record(self):
        # The arrival of finding F16: this runner's signed body,
        # in clear text that is allowed, under a subject whose id
        # is 100,000 escape characters, with a wrong audience in
        # audit mode. As the code was, the id went whole into 1
        # line of the log and into the security audit.
        raw, subject_id, _body_id = arrival(
            901, False, False, True, True, False,
            subject_id="\x1b" * 100000)
        out = ask(raw, True, settings("audit", False), verbose=True)
        self.assertEqual([], out.executed)
        self.assertEqual(1, out.marks)
        self.assertEqual(
            "rejecting seq 3: job_id mismatch between subject and body",
            out.notes[-1])
        self.assertEqual(b"", out.written)
        self.assertLess(sum(len(line) for line in out.notes), 4096)
        for line in out.notes:
            self.assertNotIn("\x1b", line)

    def test_an_honest_job_s_lines_are_as_they_were(self):
        # B7. In clear text and sealed, the lines of a job as it
        # is sent, to the letter.
        for sealed, lines in (
                (False,
                 ["seq 3: job stretch-902 submitted by si@example.com "
                  "subject='[HOMING-PIGEON] job stretch-902'",
                  "job stretch-902: received in clear text (not "
                  "encrypted); accepted under --allow-cleartext",
                  "executing job stretch-902 (kind=exec)"]),
                (True,
                 ["seq 3: job stretch-902 submitted by si@example.com "
                  "subject='[HOMING-PIGEON] job stretch-902'",
                  "executing job stretch-902 (kind=exec)"])):
            raw, _subject_id, _body_id = arrival(
                902, sealed, True, True, True, True)
            out = ask(raw, True, settings("enforce", False))
            self.assertEqual(1, len(out.executed), sealed)
            self.assertEqual(lines, out.notes[:len(lines)], sealed)


def gate_function():
    with open(MAIL_PY, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "handle_mail")


# ---- The labels: a walk of the gate's own source

OWN, CUT, SIGNED, STRANGER = 0, 1, 2, 3
# A call that writes a text at a bounded length, whatever it is
# given. The first 3 are finding F12's.
BOUNDERS = ("_log_plain", "_log_quoted", "_log_reason")
# A call whose answer is a number or a yes or no.
ANSWERS = ("len", "int", "bool", "isinstance", "_sender_is_deep",
           "_version_ok", "_lone_surrogate", "audience_allows",
           "sec_mode", "sec_decide", "_cleartext_jobs_allowed", "fired")
# A call that writes a record: a line of the log, an entry of the
# security audit, an event.
RECORDS = ("log", "vlog", "_auth_reject_event", "_append_security_event",
           "sec_decide", "audience_allows", "write_audit_entry")


def called(node):
    """The last name of what a call calls."""
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else \
        func.id if isinstance(func, ast.Name) else ""


def free_names(node, hidden=()):
    """The names a piece of source reads, but for the arguments of
    a function defined inside it, which are that function's own."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        hidden = tuple(hidden) + tuple(arg.arg for arg in node.args.args)
    if isinstance(node, ast.ExceptHandler) and node.name:
        hidden = tuple(hidden) + (node.name,)
    if isinstance(node, ast.Name):
        if node.id not in hidden:
            yield node.id
        return
    for child in ast.iter_child_nodes(node):
        yield from free_names(child, hidden)


class Labels:
    """A walk of 1 function, in the order of its source. Each name
    has a label at each point: the runner's own, cut, signed, or a
    stranger's. A name made from other names has the highest of
    their labels. The walk follows a text through the function's
    own names. It does not follow it into the functions the gate
    calls: those are read as records, as answers, or as neither.

    It finds 3 things. `written`: a record that carries a text
    that is signed or a stranger's and is not cut. `used`: a
    stranger's name used behind the signature anywhere but in the
    test that binds it. `bound`: the line of that test."""

    def __init__(self, function, stranger=("raw",)):
        self.labels = {name: STRANGER for name in stranger}
        self.groups = {}
        self.behind = False
        self.signed_line = None
        self.bound = {}
        self.written = []
        self.used = []
        self.cutters = set(BOUNDERS)
        for node in function.body:
            self.statement(node)

    # -- what label an expression has

    def label(self, node):
        if node is None or isinstance(node, ast.Constant):
            return OWN
        if isinstance(node, ast.Name):
            return self.labels.get(node.id, OWN)
        if isinstance(node, ast.Call):
            name = called(node)
            if name in self.cutters:
                return CUT
            if name in ANSWERS:
                return OWN
            if name == "_verify_and_decrypt":
                return SIGNED
            parts = [self.label(arg) for arg in node.args]
            parts += [self.label(word.value) for word in node.keywords]
            if isinstance(node.func, ast.Attribute):
                parts.append(self.label(node.func.value))
            return max(parts, default=OWN)
        if isinstance(node, ast.Compare) or (
                isinstance(node, ast.UnaryOp)
                and isinstance(node.op, ast.Not)):
            return OWN
        return max((self.label(child)
                    for child in ast.iter_child_nodes(node)
                    if isinstance(child, ast.expr)), default=OWN)

    def raw_names(self, node, least):
        """The names in an expression whose label is `least` or
        higher, and that stand outside any call that cuts or
        answers."""
        if isinstance(node, ast.Call) and called(node) not in RECORDS \
                and (called(node) in self.cutters
                     or called(node) in ANSWERS):
            return
        if isinstance(node, ast.Name):
            if self.labels.get(node.id, OWN) >= least:
                yield node.id
            return
        for child in ast.iter_child_nodes(node):
            yield from self.raw_names(child, least)

    # -- what a statement does to the labels

    def give(self, target, label, group=None):
        if isinstance(target, ast.Name):
            self.labels[target.id] = label
            self.groups[target.id] = group or (target.id,)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names = tuple(item.id for item in target.elts
                          if isinstance(item, ast.Name))
            for item in target.elts:
                self.give(item, label, names)

    def look(self, node, skip=None):
        """Read 1 statement's own expressions for records and for
        uses of a stranger's name."""
        for call in [item for item in ast.walk(node)
                     if isinstance(item, ast.Call)]:
            if called(call) not in RECORDS:
                continue
            parts = list(call.args) + [word.value
                                       for word in call.keywords]
            for part in parts:
                for name in self.raw_names(part, SIGNED):
                    self.written.append(
                        (call.lineno, called(call), name,
                         self.labels[name], self.behind))
        if self.behind and node is not skip:
            for name in self.raw_names(node, STRANGER):
                self.used.append((node.lineno, name))

    def statement(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A function inside the gate. Its own arguments are
            # the runner's, but for the refusal's reason, which
            # is whatever the caller says.
            before = dict(self.labels)
            for arg in node.args.args:
                self.labels[arg.arg] = STRANGER \
                    if node.name == "reject" else OWN
            cut_first = False
            for inner in node.body:
                self.statement(inner)
                if node.name == "reject" and not cut_first:
                    cut_first = self.labels.get("why") == CUT
            if node.name == "reject" and cut_first \
                    and not any(line[1] in ("log", "vlog")
                                and line[2] == "why"
                                for line in self.written):
                self.cutters.add("reject")
            self.labels = before
            return
        if isinstance(node, ast.Assign):
            self.look(node)
            if isinstance(node.value, ast.Call) \
                    and called(node.value) == "_verify_and_decrypt":
                # (the body, the key's id, the secret, sealed)
                job, key_id, secret, sealed = node.targets[0].elts
                self.give(job, SIGNED)
                self.give(key_id, SIGNED)
                self.give(secret, OWN)
                self.give(sealed, OWN)
                return
            label = self.label(node.value)
            for target in node.targets:
                self.give(target, label)
            return
        if isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            self.look(node)
            self.give(node.target, self.label(node.value))
            return
        if isinstance(node, ast.If):
            binds = self.binding(node)
            self.look(node.test, skip=node.test if binds else None)
            # A name has the higher of the labels its 2 branches
            # give it.
            before = dict(self.labels)
            for inner in node.body:
                self.statement(inner)
            after_body, self.labels = self.labels, dict(before)
            for inner in node.orelse:
                self.statement(inner)
            for name, label in after_body.items():
                self.labels[name] = max(label, self.labels.get(name, OWN))
            for name in binds:
                for bound in self.groups.get(name, (name,)):
                    self.labels[bound] = SIGNED
                self.bound[name] = node.lineno
            return
        if isinstance(node, ast.Try):
            asks = "_verify_and_decrypt" in ast.unparse(node.body)
            # What is raised in the body may repeat any text the
            # body reads, so the name it is caught under has the
            # highest label of the names the body reads.
            highest = max((self.labels.get(name, OWN)
                           for inner in node.body
                           for name in free_names(inner)), default=OWN)
            for inner in node.body:
                self.statement(inner)
            for handler in node.handlers:
                if handler.name:
                    self.labels[handler.name] = highest
                for inner in handler.body:
                    self.statement(inner)
                # The name a handler catches under is gone when
                # the handler ends.
                self.labels.pop(handler.name, None)
            for inner in node.orelse + node.finalbody:
                self.statement(inner)
            if asks:
                self.behind = True
                self.signed_line = node.lineno
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self.look(node.iter)
            self.give(node.target, self.label(node.iter))
            for inner in node.body + node.orelse:
                self.statement(inner)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                self.look(item.context_expr)
                if item.optional_vars is not None:
                    self.give(item.optional_vars,
                              self.label(item.context_expr))
            for inner in node.body:
                self.statement(inner)
            return
        if isinstance(node, ast.While):
            self.look(node.test)
            for inner in node.body + node.orelse:
                self.statement(inner)
            return
        self.look(node)

    def binding(self, node):
        """The names an `if` binds: a stranger's name set against
        a signed text, where the 2 differing ends the handling."""
        test = node.test
        if not (self.behind and isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.NotEq)
                and node.body and isinstance(node.body[-1], ast.Return)):
            return []
        left, right = test.left, test.comparators[0]
        for a_name, other in ((left, right), (right, left)):
            if isinstance(a_name, ast.Name) \
                    and self.labels.get(a_name.id) == STRANGER \
                    and self.label(other) == SIGNED:
                return [a_name.id]
        return []


def as_it_was(function):
    """The gate's function with the 2 changes taken out, made
    from the source that stands: the check of C13 put back where
    it was, last of the stretch, and every cut of findings F12
    and F16 undone. Nothing else is touched."""
    import copy
    function = copy.deepcopy(function)
    body = function.body
    at = next(place for place, node in enumerate(body)
              if isinstance(node, ast.Try)
              and "_verify_and_decrypt" in ast.unparse(node))
    c13 = body[at + 1:at + 3]
    del body[at + 1:at + 3]
    was = next(place for place, node in enumerate(body)
               if isinstance(node, ast.Try) and "_fromiso" in ast.unparse(node))
    body[was:was] = c13

    class Uncut(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            return node.args[0] if called(node) in BOUNDERS else node

        def visit_Assign(self, node):
            # reject's `why = R._log_reason(why)` becomes nothing.
            if isinstance(node.value, ast.Call) \
                    and called(node.value) in BOUNDERS \
                    and ast.unparse(node.targets[0]) \
                    == ast.unparse(node.value.args[0]):
                return ast.Pass()
            self.generic_visit(node)
            return node

    return ast.fix_missing_locations(Uncut().visit(function))


class TheLabelsInTheSource(unittest.TestCase):
    """B5. The rule, read off the gate's own source on every run
    of the suite: a new line that writes a stranger's text, or
    uses the subject's id before it is bound, fails here by name."""

    @classmethod
    def setUpClass(cls):
        cls.function = gate_function()
        cls.now = Labels(cls.function)
        cls.was = Labels(as_it_was(cls.function))

    def test_the_walk_finds_the_signature_and_the_binding(self):
        body = self.function.body
        at = next(place for place, node in enumerate(body)
                  if isinstance(node, ast.Try)
                  and "_verify_and_decrypt" in ast.unparse(node))
        self.assertEqual(body[at].lineno, self.now.signed_line)
        # The id is bound by the second statement behind the
        # signature, and the seen key, made from the id, with it.
        self.assertEqual({"job_id": body[at + 2].lineno}, self.now.bound)
        self.assertEqual(("job_id", "skey"), self.now.groups["job_id"])
        # A refusal's reason is cut before it is written, so a
        # refusal may be handed any text.
        self.assertIn("reject", self.now.cutters)

    def test_no_record_carries_a_stranger_s_text_uncut(self):
        self.assertEqual([], [found for found in self.now.written
                              if found[3] == STRANGER])

    def test_behind_the_signature_a_stranger_s_name_only_binds(self):
        self.assertEqual([], self.now.used)

    def test_the_walk_finds_f16_and_f12_in_the_gate_as_it_was(self):
        # With nobody pointing at them. Behind the signature the
        # subject's id is used twice, and they are the 2 the audit
        # found: the line for a job in clear text, and the call
        # that writes the security audit.
        self.assertEqual(["job_id", "job_id"],
                         [name for _line, name in self.was.used])
        behind = [(sink, name) for _line, sink, name, label, behind
                  in self.was.written if label == STRANGER and behind]
        self.assertEqual([("log", "job_id"), ("audience_allows", "job_id")],
                         behind)
        # In front of the signature: finding F12, the first line's
        # 3 texts and the refusal's reason, in 2 lines.
        front = [(sink, name) for _line, sink, name, label, behind
                 in self.was.written if label == STRANGER and not behind]
        self.assertEqual(
            [("vlog", "why"), ("log", "why"), ("log", "job_id"),
             ("log", "shown_sender"), ("log", "subject")], front)
        self.assertNotIn("reject", self.was.cutters)

    def test_the_records_that_carry_a_signed_text_whole_are_counted(self):
        # Not a fault, and not nothing. Behind the binding the id
        # is the signer's, and a record may carry it whole: a
        # holder of the key writes those lines. The count is held
        # so that 1 more is a choice somebody made.
        signed = [found for found in self.now.written
                  if found[3] == SIGNED]
        self.assertEqual([], [found for found in signed if not found[4]])
        self.assertEqual(21, len({line for line, *_rest in signed}))
        runs = next(node.lineno for node in ast.walk(self.function)
                    if isinstance(node, ast.Call)
                    and called(node) == "execute_job")
        before_the_run = {line for line, _sink, name, _label, _behind
                          in signed if name == "job_id" and line < runs}
        self.assertEqual(15, len(before_the_run))


# ---- The ladder: a signed body under a stranger's envelope

def series(top):
    out = [0, 1]
    while len(out) <= top:
        out.append(out[-1] + out[-2])
    return out


def under(text, grown, number):
    """This runner's signed job in clear text, with 1 text outside
    the signature grown: (the mail, the body's id)."""
    body_id = "ladder-%d" % number
    job = DOOR._job2(body_id, kind="exec", script="echo")
    body = RUNNER.sign_payload(job, DOOR.SECRET)
    subject, sender = "[HOMING-PIGEON] job %s" % body_id, "si@example.com"
    if text == "the id":
        subject = "[HOMING-PIGEON] job %s" % grown
    elif text == "a word of the subject":
        subject = "[HOMING-PIGEON] %s job %s" % (grown, body_id)
    elif text == "the sender":
        sender = "%s@example.com" % grown
    elif text == "a note beside the signed object":
        body = grown + "\n" + body
    else:
        raise KeyError(text)
    return PRE._mail(subject, body, sender), body_id


class TheLadderBehindTheMac(unittest.TestCase):
    """B6. What finding F12's measure did not reach: the texts
    outside the signature, grown under a body the runner's own
    key signed."""

    STEPS = series(24)
    UNITS = ("A", "\x1b", "=?utf-8?q?A?=")

    def climb(self, text, unit):
        rows = []
        for step in range(1, 25):
            raw, body_id = under(text, unit * self.STEPS[step], step)
            out = ask(raw, True)
            rows.append(Namespace(
                step=step, size=len(unit) * self.STEPS[step],
                ran=[job["job_id"] for job in out.executed],
                marks=out.marks, lines=len(out.notes),
                logged=sum(len(line) for line in out.notes),
                raw=sum(line.count("\x1b") for line in out.notes),
                written=len(out.written), body_id=body_id,
                notes=out.notes))
        return rows

    def test_an_envelope_with_another_id_adds_the_same_2_lines(self):
        for unit in self.UNITS:
            rows = self.climb("the id", unit)
            self.assertEqual(46368 * len(unit), rows[-1].size)
            for row in rows:
                case = (unit, row.step)
                self.assertEqual([], row.ran, case)
                self.assertEqual(1, row.marks, case)
                self.assertEqual(2, row.lines, case)
                self.assertEqual(0, row.raw, case)
                self.assertEqual(0, row.written, case)
                self.assertLess(row.logged, PRE.LOG_BOUND, case)
                self.assertEqual(
                    "rejecting seq 3: job_id mismatch between subject "
                    "and body", row.notes[-1], case)
            # Past the bars the 2 lines are of 1 length, but for
            # the digits of the text's own length.
            past = [row.logged for row in rows if row.size > 5000]
            self.assertLessEqual(max(past) - min(past), 4, unit)

    def test_an_envelope_with_the_body_s_id_runs_the_same_job(self):
        for text in ("a word of the subject", "the sender",
                     "a note beside the signed object"):
            for unit in ("A", "\x1b") if text != \
                    "a note beside the signed object" else ("A", "\n"):
                rows = self.climb(text, unit)
                for row in rows:
                    case = (text, unit, row.step)
                    self.assertEqual([row.body_id], row.ran, case)
                    self.assertEqual(0, row.raw, case)
                    self.assertLess(row.logged, PRE.LOG_BOUND, case)
                # What the gate keeps of a job that ran does not
                # grow with the text outside the signature.
                past = [row.written for row in rows if row.size > 5000]
                self.assertLessEqual(max(past) - min(past), 8,
                                     (text, unit))
                past = [row.logged for row in rows if row.size > 5000]
                self.assertLessEqual(max(past) - min(past), 4,
                                     (text, unit))


class ThePageRecordsTheMeasure(unittest.TestCase):
    """The figures this module computes are the page's."""

    def test_the_page_states_what_was_walked_asked_and_climbed(self):
        page = MODELS._flat(PAGE)
        stated = []
        for name in CONFIGURATIONS:
            got = walk(*CONFIGURATIONS[name], True)
            stated.append("%s | %s |" % (format(got["distinct"], ","),
                                         format(got["generated"], ",")))
        was = {name: walk(*CONFIGURATIONS[name], False)
               for name in CONFIGURATIONS}
        stated += [
            "| `gateenforce.cfg` | 2,291,720 | 3,078,152 | hold |",
            "2,309,000, 2,320,144 and 2,320,144 distinct states",
            "Violated in 6 states | %s |" % format(
                was["gatecleartext.cfg"]["broken"][
                    "NamedByTheSignedId"][0], ","),
            "Violated in 7 states | %s |" % format(
                was["gateaudit.cfg"]["broken"][
                    "NamedByTheSignedId"][0], ","),
            "Violated in 7 states | %s |" % format(
                was["gateenforce.cfg"]["broken"][
                    "OneVersionBeforeTheBody"][0], ","),
            "%s of its states break" % format(
                was["gateenforce.cfg"]["broken"][
                    "NamedByTheSignedId"][0], ","),
            "%s states with the audience off" % format(
                was["gatedefault.cfg"]["broken"][
                    "OneVersionBeforeTheBody"][0], ","),
            "| `gateenforce.cfg` | 1 | 6 | 2 | 12 | 786,411 |",
            "| The other 3 | 2 | 12 | 4 | 24 | 786,390 |",
            "384 arrivals were then sent to the real gate",
            "| Refused for the version or the type | 288 |",
            "| Refused for the id | 48 |",
            "| Refused for clear text | 12 |",
            "| Refused for the audience | 6 |",
            "| Refused for the script's size | 15 |",
            "| Runs | 15 |",
            "336 of the 384",
            "| As it stands on main | 7 | 2 |",
            "| On this branch, binding first | 0 | 0 |",
            "21 lines of the gate write a signed text whole",
            "15 of them carry the id before the job is run",
            "9 ladders of 24 steps, 216 arrivals",
            "No row was added to the constraint inventory",
        ]
        for words in stated:
            self.assertIn(words, page, words)

    def test_the_rule_is_c13_s_and_the_protocol_s_own_sentence(self):
        page = MODELS._flat(PAGE)
        with open(os.path.join(ROOT, "PROTOCOL.md"),
                  encoding="utf-8") as handle:
            protocol = " ".join(handle.read().split())
        with open(os.path.join(PROOFS, "constraints.md"),
                  encoding="utf-8") as handle:
            constraints = " ".join(handle.read().split())
        sentence = ("checked once the signature has verified, before "
                    "anything else in the body is acted on")
        self.assertIn(sentence, page)
        self.assertIn(sentence, protocol)
        # The list around the sentence is in the order it gives:
        # the signature, then the version, then the audience.
        order = [protocol.index(words) for words in (
            "1. **Signature valid:**", "2. `v` is the JSON integer 1",
            "3. **Audience binding**",
            "4. The signed script is bounded by")]
        self.assertEqual(sorted(order), order)
        self.assertIn("These 3 MUST be checked first behind the "
                      "signature", constraints)
