#!/usr/bin/env python3
"""Pins for the IETF draft's conformance and security-properties text.

The draft (docs/ietf/draft-homing-pigeon-00.md) states the protocol's
conformance rule in Section 5: one version, conformance per binding,
the email binding mandatory for a runner, object authentication
REQUIRED on every binding, and confidentiality REQUIRED as a property
that a binding may satisfy itself (the DTLS binding, Section 19.4) or
carry through the per-job encryption of Section 16 (email, NATS),
with the file binding stating its local-policy case. These tests pin
that each statement is present in the section that owns it, so a
future edit cannot silently drop or move one.
"""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

DRAFT = os.path.join(REPO, "docs", "ietf", "draft-homing-pigeon-00.md")


def _sections(text):
    """Map a section heading line to the text under it, up to the
    next heading of the same or a higher level."""
    parts = re.split(r"(?m)^(#{1,3} .*)$", text)
    out = {}
    for i in range(1, len(parts), 2):
        out[parts[i].strip()] = _flat(parts[i + 1])
    return out


def _flat(text):
    return re.sub(r"\s+", " ", text)


class DraftConformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRAFT, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.sec = _sections(cls.text)

    def test_one_version_and_no_version_2(self):
        versions = self.sec["### Versions in this document"]
        self.assertIn("there is no version 2", versions)

    def test_section_5_conformance_no_mti_binding(self):
        sec5 = self.sec["## 5. Transport Binding"]
        self.assertIn("Conformance is per binding", sec5)
        self.assertIn("no binding is mandatory to implement", sec5)
        self.assertIn("offers at least one binding", sec5)
        self.assertNotIn("MUST offer the email binding", sec5)

    def test_authentication_attaches_to_the_object(self):
        sec5 = self.sec["## 5. Transport Binding"]
        self.assertIn("authentication of the object", sec5)
        self.assertIn("attaches to the object, never to the transport",
                      sec5)

    def test_confidentiality_attaches_to_the_property(self):
        sec5 = self.sec["## 5. Transport Binding"]
        self.assertIn("attaches to the property, not to a mechanism",
                      sec5)
        self.assertIn(
            "the per-job encryption of Section 16 is then OPTIONAL "
            "on that binding", sec5)

    def test_email_binding_states_its_case(self):
        sec5 = self.sec["## 5. Transport Binding"]
        self.assertIn(
            "the confidentiality property is carried by the per-job "
            "encryption of Section 16", sec5)

    def test_file_binding_states_its_case(self):
        sec51 = self.sec["### 5.1. The File Binding"]
        self.assertIn("this binding provides neither itself", sec51)
        self.assertIn("a local policy decision", sec51)

    def test_nats_binding_states_its_case(self):
        sec52 = self.sec["### 5.2. The NATS Binding"]
        self.assertIn("broker authentication satisfies neither", sec52)
        self.assertIn(
            "the confidentiality property is carried by the per-job "
            "encryption of Section 16", sec52)

    def test_section_16_receiver_required_sender_floats(self):
        sec16 = self.sec["## 16. Per-Job Encryption"]
        self.assertIn("Receiver support is REQUIRED on every binding",
                      sec16)
        self.assertIn(
            "Sender application is OPTIONAL on a binding that itself "
            "provides the confidentiality property", sec16)

    def test_dtls_binding_satisfies_confidentiality_itself(self):
        sec194 = self.sec["### 19.4. Composition with Per-Job Encryption"]
        self.assertIn(
            "This binding provides the confidentiality property of "
            "Section 5 itself", sec194)
        self.assertIn("is therefore OPTIONAL", sec194)
        self.assertIn(
            "The session's authentication of its peer does not "
            "substitute for the object signature", sec194)

    def test_section_10_names_a_secret_by_fingerprint(self):
        sec = self.sec["### 10.1. Fingerprint names"]
        self.assertIn("homing-pigeon key id v1", sec)
        self.assertIn("MUST NOT select the default secret", sec)
        self.assertIn("not a PSK identity", sec)
        result = self.sec["## 13. Result Message"]
        self.assertIn("default secret's fingerprint", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
