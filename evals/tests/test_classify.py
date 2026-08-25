"""Category assignment against the whole corpus.

The category selects the check set, so a wrong category is not one wrong
finding -- it is the wrong dimension applied to the whole product. These tests
run every fixture and assert against its expectation file rather than against
anything this implementation chose.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from audits.pip_locator import resolve                       # noqa: E402
from engine.classify import classify                         # noqa: E402
from engine.evidence import EvidenceBuilder                  # noqa: E402
from engine.sources import PipSource                         # noqa: E402
from engine.taxonomy_data import UNCATEGORIZED               # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(REPO, "evals/fixtures/*/*.pip.json")))


def load(path):
    with open(path) as handle:
        return json.load(handle)


def expectation_for(path):
    return load(path.replace("fixtures", "expected").replace(".pip.json",
                                                             ".expected.json"))


def classified(path):
    document = load(path)
    out = []
    for npr in document["products"]:
        builder = EvidenceBuilder(PipSource(document, file=path), npr["product_id"])
        out.append((npr, classify(npr, builder)))
    return out


class TestAgainstExpectations(unittest.TestCase):
    def test_every_fixture_classifies_as_its_expectation_says(self):
        checked = 0
        for path in FIXTURES:
            expectation = expectation_for(path)
            rows = {p["product_id"]: p for p in expectation["products"]}
            for npr, result in classified(path):
                expected = rows.get(npr["product_id"], {})
                if "expected_category" not in expected:
                    continue
                checked += 1
                self.assertEqual(result.assigned, expected["expected_category"],
                                 os.path.basename(path))
                if "expected_classification_method" in expected:
                    self.assertEqual(result.method,
                                     expected["expected_classification_method"],
                                     os.path.basename(path))
        self.assertGreaterEqual(checked, 14)


class TestEvidence(unittest.TestCase):
    def test_classification_evidence_resolves_and_reproduces(self):
        """The category block is held to finding-grade evidence (PRD 7.1)."""
        for path in FIXTURES:
            for npr, result in classified(path):
                self.assertTrue(result.evidence, os.path.basename(path))
                for item in result.evidence:
                    if item.type == "absence":
                        self.assertTrue(item.checked_paths)
                        continue
                    resolution = resolve(npr, item.locator)
                    self.assertTrue(resolution.ok, item.locator)
                    self.assertEqual(resolution.text, item.excerpt)

    def test_inference_is_labelled_as_interpreted(self):
        """PRD 9.5: an inference-derived finding is marked, never silent."""
        for path in FIXTURES:
            for _, result in classified(path):
                notes = " ".join(e.note or "" for e in result.evidence)
                if result.method != UNCATEGORIZED:
                    self.assertIn("(interpreted)", notes, os.path.basename(path))


class TestOrderingRules(unittest.TestCase):
    def test_a_higher_tier_signal_wins(self):
        """taxonomy.md 2: the first rule that matches decides."""
        for path in FIXTURES:
            for npr, result in classified(path):
                declared = (npr["identity"].get("declared_category") or {}).get("value")
                if declared and result.assigned != UNCATEGORIZED:
                    self.assertEqual(result.method, "declared_category_map",
                                     os.path.basename(path))

    def test_row_order_resolves_two_terms_in_one_signal(self):
        """"Electronics > Lighting" hits two rows; the earlier row wins."""
        path = os.path.join(REPO,
                            "evals/fixtures/sparse/sparse-electronics-02.pip.json")
        for npr, result in classified(path):
            self.assertEqual(result.assigned, "electronics")

    def test_no_mapping_term_means_no_category(self):
        path = os.path.join(REPO,
                            "evals/fixtures/checks/checks-07-uncategorized.pip.json")
        for npr, result in classified(path):
            self.assertEqual(result.assigned, UNCATEGORIZED)
            self.assertEqual(result.confidence, "low")
            self.assertEqual(result.evidence[0].type, "absence")

    def test_an_operator_override_is_labelled_as_one(self):
        path = os.path.join(REPO,
                            "evals/fixtures/checks/checks-07-uncategorized.pip.json")
        document = load(path)
        npr = document["products"][0]
        builder = EvidenceBuilder(PipSource(document, file=path), npr["product_id"])
        result = classify(npr, builder, override="home")
        self.assertEqual(result.assigned, "home")
        self.assertEqual(result.method, "operator_override")
        self.assertEqual(result.confidence, "high")

    def test_classification_never_writes_into_attributes(self):
        """taxonomy.md 2 rule 2. The assignment is a label, not a fact."""
        for path in FIXTURES:
            for npr, result in classified(path):
                keys = [a.get("key") for a in npr.get("attributes") or []]
                self.assertNotIn("category", keys)
                self.assertNotIn("product_category", keys)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
