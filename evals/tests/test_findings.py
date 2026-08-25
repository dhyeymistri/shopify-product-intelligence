"""The finding contract, and the gate that guards it.

PRD 8.3 rule 1 calls the evidence gate structural. That word is the whole test
file: a gate that lives only at render time does not protect the layer where
findings are made, so these tests exercise it where the finding is created.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from engine.evidence import EvidenceBuilder                       # noqa: E402
from engine.findings import (ABSENCE, DO_NOT_GENERATE, Evidence,  # noqa: E402
                             EvidenceError, Finding, FindingLedger, NOT_STATED,
                             Remediation)
from engine.sources import PipSource                              # noqa: E402

FIXTURE = os.path.join(REPO, "evals/fixtures/sparse/sparse-apparel-01.pip.json")


def _finding(check_id="IDENT.BRAND_PRESENT", dimension="D1_identity",
             evidence=(), status="UNKNOWN", **kw):
    return Finding(check_id=check_id, dimension=dimension, status=status,
                   severity="major", confidence="high", title="t", detail="d",
                   evidence=list(evidence), earned=Decimal("0"),
                   max_points=Decimal("2.0"), penalty=Decimal("0"), **kw)


class TestEvidenceObject(unittest.TestCase):
    def test_absence_without_checked_paths_cannot_be_constructed(self):
        with self.assertRaises(EvidenceError):
            Evidence(ABSENCE)

    def test_quote_without_a_locator_cannot_be_constructed(self):
        with self.assertRaises(EvidenceError):
            Evidence("quote", excerpt="x")

    def test_field_value_without_an_excerpt_cannot_be_constructed(self):
        with self.assertRaises(EvidenceError):
            Evidence("field_value", locator="identity.brand")

    def test_absence_carries_no_locator(self):
        with self.assertRaises(EvidenceError):
            Evidence(ABSENCE, locator="identity.brand",
                     checked_paths=("identity.brand",))

    def test_shape_matches_the_prd(self):
        item = Evidence(ABSENCE, checked_paths=("identity.brand",))
        self.assertEqual(sorted(item.as_dict()),
                         ["checked_paths", "excerpt", "locator", "note", "type"])


class TestEvidenceBuilder(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE) as handle:
            self.document = json.load(handle)
        self.npr = self.document["products"][0]
        self.builder = EvidenceBuilder(PipSource(self.document),
                                       self.npr["product_id"])

    def test_a_locator_that_does_not_resolve_is_refused(self):
        with self.assertRaises(EvidenceError):
            self.builder.quote("identity.nonexistent")

    def test_a_span_past_the_end_of_a_value_is_refused(self):
        with self.assertRaises(EvidenceError):
            self.builder.span("identity.title", 0, 9999)

    def test_an_excerpt_is_sliced_from_the_source(self):
        item = self.builder.span("identity.title", 10, 27)
        self.assertEqual(item.excerpt, "Crew Neck T-Shirt")
        self.assertEqual(item.locator, "identity.title[10:27]")

    def test_derived_evidence_needs_two_references(self):
        with self.assertRaises(EvidenceError):
            self.builder.derived(["identity.title"], "one thing")


class TestEvidenceGate(unittest.TestCase):
    def test_a_finding_without_evidence_is_dropped_and_logged(self):
        ledger = FindingLedger("p1")
        self.assertFalse(ledger.add(_finding()))
        self.assertEqual(ledger.findings, [])
        self.assertEqual(ledger.run_errors[0]["code"], "CHECK.EVIDENCE_GATE")

    def test_a_finding_with_evidence_is_admitted(self):
        ledger = FindingLedger("p1")
        item = Evidence(ABSENCE, checked_paths=("identity.brand",))
        self.assertTrue(ledger.add(_finding(evidence=[item])))
        self.assertEqual(len(ledger.findings), 1)


class TestDeterministicOrdering(unittest.TestCase):
    def _ledger(self, order):
        ledger = FindingLedger("p1")
        item = Evidence(ABSENCE, checked_paths=("identity.brand",))
        for check_id, dimension in order:
            ledger.add(_finding(check_id=check_id, dimension=dimension,
                                evidence=[item]))
        return ledger.seal()

    def test_ids_follow_the_sort_not_the_insertion_order(self):
        rows = [("STRUCT.MEDIA_ALT_TEXT", "D8_structure"),
                ("IDENT.BRAND_PRESENT", "D1_identity"),
                ("APPAREL.SIZE_SYSTEM", "D2_category_attributes")]
        forward = self._ledger(rows)
        backward = self._ledger(list(reversed(rows)))
        self.assertEqual([f.check_id for f in forward.findings],
                         [f.check_id for f in backward.findings])
        self.assertEqual([f.finding_id for f in forward.findings],
                         ["F-0001", "F-0002", "F-0003"])
        self.assertEqual(forward.findings[0].check_id, "IDENT.BRAND_PRESENT")


class TestDerivedMembers(unittest.TestCase):
    def _ledger(self):
        ledger = FindingLedger("p1")
        item = Evidence(ABSENCE, checked_paths=("attributes[care_instructions]",))
        finding = _finding(check_id="APPAREL.CARE_INSTRUCTIONS",
                           dimension="D2_category_attributes", evidence=[item])
        finding.remediation = Remediation("question", "What are the care "
                                          "instructions for this garment?",
                                          "attributes[care_instructions]",
                                          DO_NOT_GENERATE)
        ledger.add(finding)
        return ledger.seal()

    def test_unknowns_carry_the_paths_that_were_searched(self):
        row = self._ledger().unknowns()[0]
        self.assertEqual(row["attribute"], "care_instructions")
        self.assertEqual(row["checked_paths"], ["attributes[care_instructions]"])
        self.assertTrue(row["question"])

    def test_questions_rank_by_points_recoverable(self):
        row = self._ledger().questions_for_merchant()[0]
        self.assertEqual(row["priority"], 1)
        self.assertEqual(row["unlocks_points"], 2.0)
        self.assertEqual(row["related_findings"], ["F-0001"])

    def test_the_fixed_absence_language_is_a_constant(self):
        self.assertEqual(NOT_STATED, "Not stated in the supplied data.")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
