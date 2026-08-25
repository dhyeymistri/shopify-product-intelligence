"""Fixture-corpus integrity.

These tests protect the corpus itself. A fixture with a bad locator or an
invalid bait would silently weaken every audit that runs against it, so the
corpus is verified before anything is verified with it.
"""

from __future__ import annotations

import glob
import json
import os
import unittest

from audits.pip_locator import resolve
from audits.provenance import ProvenanceIndex

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = sorted(glob.glob(os.path.join(REPO, "evals/fixtures/*/*.pip.json")))
EXPECTED = sorted(glob.glob(os.path.join(REPO, "evals/expected/*/*.expected.json")))

REQUIRED_SETS = {"sparse": 10, "adversarial": 4, "checks": 8}


def load(path):
    with open(path) as handle:
        return json.load(handle)


class TestCorpusShape(unittest.TestCase):
    def test_required_counts(self):
        counts = {}
        for path in FIXTURES:
            counts.setdefault(os.path.basename(os.path.dirname(path)), 0)
            counts[os.path.basename(os.path.dirname(path))] += 1
        for name, expected in REQUIRED_SETS.items():
            self.assertEqual(counts.get(name), expected, "%s fixture count" % name)

    def test_every_fixture_has_provenance_and_intent(self):
        for path in FIXTURES:
            doc = load(path)
            meta = doc.get("fixture", {})
            self.assertTrue(meta.get("provenance"), "%s: missing provenance note" % path)
            self.assertTrue(meta.get("intent"), "%s: missing intent" % path)
            self.assertIn("Synthetic", meta["provenance"], path)
            self.assertEqual(
                meta.get("id"),
                os.path.basename(path).replace(".pip.json", ""),
                "%s: fixture id must match filename" % path,
            )

    def test_every_fixture_has_an_expectation_file(self):
        for path in FIXTURES:
            doc = load(path)
            expected = os.path.join(
                REPO, "evals/expected", doc["fixture"]["set"],
                "%s.expected.json" % doc["fixture"]["id"],
            )
            self.assertTrue(os.path.exists(expected), "missing expectation for %s" % path)

    def test_products_carry_value_src_pairs(self):
        """PRD 6.2 rule 1: a bare scalar in the record is a spec violation."""
        for path in FIXTURES:
            for product in load(path)["products"]:
                for field, node in product["identity"].items():
                    self.assertIsInstance(node, dict, "%s: identity.%s" % (path, field))
                    self.assertIn("value", node)
                    self.assertIn("src", node)
                    if node["value"] is None:
                        self.assertIsNone(node["src"], "%s: null value with a src" % path)


class TestFixtureLocators(unittest.TestCase):
    def test_every_src_resolves(self):
        for path in FIXTURES:
            for product in load(path)["products"]:
                for group, items in (
                    ("attributes", product.get("attributes", [])),
                    ("metafields", product.get("metafields", [])),
                    ("claims", product.get("claims", [])),
                ):
                    for item in items:
                        if not item.get("src"):
                            continue
                        resolution = resolve(product, item["src"])
                        self.assertTrue(
                            resolution.ok,
                            "%s: %s src %r -> %s"
                            % (path, group, item["src"], resolution.error),
                        )

    def test_attribute_spans_reproduce_their_value(self):
        """A span locator must return exactly the value it claims to source."""
        for path in FIXTURES:
            for product in load(path)["products"]:
                for attribute in product.get("attributes", []):
                    src = attribute.get("src") or ""
                    if not src.endswith("]") or ":" not in src.rsplit("[", 1)[-1]:
                        continue
                    resolution = resolve(product, src)
                    self.assertEqual(
                        resolution.text,
                        attribute["value_raw"],
                        "%s: span %r does not reproduce %r"
                        % (path, src, attribute["value_raw"]),
                    )


class TestExpectations(unittest.TestCase):
    def _fixture_for(self, expectation):
        return load(
            os.path.join(
                REPO, "evals/fixtures", expectation["set"],
                "%s.pip.json" % expectation["fixture_id"],
            )
        )

    def test_baits_are_genuinely_absent_from_input(self):
        """The load-bearing corpus invariant.

        A bait that is actually present in the fixture would make FAB014 fire on
        an honest report -- turning the audit into a generator of false
        accusations. Every declared bait must be absent from the input it
        belongs to.
        """
        for path in EXPECTED:
            expectation = load(path)
            fixture = self._fixture_for(expectation)
            products = {p["product_id"]: p for p in fixture["products"]}
            for product_exp in expectation["products"]:
                index = ProvenanceIndex(products[product_exp["product_id"]])
                for bait in product_exp.get("must_not_fabricate", []):
                    self.assertFalse(
                        index.contains(bait),
                        "%s: bait %r is present in the supplied input"
                        % (os.path.basename(path), bait),
                    )

    def test_every_fixture_declares_baits(self):
        for path in EXPECTED:
            for product_exp in load(path)["products"]:
                self.assertTrue(
                    product_exp.get("must_not_fabricate"),
                    "%s: no must_not_fabricate declared" % path,
                )

    def test_expectation_locators_resolve(self):
        for path in EXPECTED:
            expectation = load(path)
            fixture = self._fixture_for(expectation)
            products = {p["product_id"]: p for p in fixture["products"]}
            for product_exp in expectation["products"]:
                product = products[product_exp["product_id"]]
                for finding in product_exp.get("expected_findings_include", []):
                    for locator in finding.get("evidence_locators", []):
                        resolution = resolve(product, locator)
                        self.assertTrue(
                            resolution.ok,
                            "%s: %r -> %s" % (path, locator, resolution.error),
                        )

    def test_expectation_span_locators_match_fixture_attribute_sources(self):
        """A span in an expectation must point at the same text the fixture does.

        Caught a real stale offset in sparse-home-02 when this was added.
        """
        for path in EXPECTED:
            expectation = load(path)
            fixture = self._fixture_for(expectation)
            products = {p["product_id"]: p for p in fixture["products"]}
            for product_exp in expectation["products"]:
                product = products[product_exp["product_id"]]
                sources = {a["src"] for a in product.get("attributes", [])}
                for finding in product_exp.get("expected_findings_include", []):
                    for locator in finding.get("evidence_locators", []):
                        if "description_text[" not in locator:
                            continue
                        self.assertIn(
                            locator,
                            sources,
                            "%s: span %r is not a source the fixture declares"
                            % (os.path.basename(path), locator),
                        )

    def test_expectations_do_not_contradict_themselves(self):
        """A status cannot be both forbidden and required by one file.

        `adv-03` shipped exactly this contradiction: it forbade FAIL outright
        while its own `expected_findings_include` required a FAIL, with the
        reason spelled out. An expectation file is the definition of correct
        output, so an internally inconsistent one cannot be satisfied by any
        implementation -- and nothing would have noticed until the phase that
        wires expectations to the engine.
        """
        for path in EXPECTED:
            expectation = load(path)
            for product_exp in expectation["products"]:
                forbidden = set(product_exp.get("forbidden_statuses") or [])
                required = set(
                    finding.get("status")
                    for finding in product_exp.get("expected_findings_include", [])
                    if finding.get("status")
                )
                overlap = forbidden & required
                self.assertEqual(
                    overlap, set(),
                    "%s: status %s is both forbidden and required"
                    % (os.path.basename(path), sorted(overlap)),
                )

    def test_declared_evidence_types_are_defined_by_the_prd(self):
        """PRD 8.1 is the closed list. An expectation may not invent a sixth."""
        permitted = {"quote", "field_value", "absence", "derived",
                     "external_reference"}
        for path in EXPECTED:
            for product_exp in load(path)["products"]:
                invariant = product_exp.get("placeholder_invariant")
                if not invariant:
                    continue
                declared = invariant.get("required_evidence_type")
                if declared is None:
                    continue
                if isinstance(declared, str):
                    declared = [declared]
                for name in declared:
                    self.assertIn(name, permitted,
                                  "%s: %r" % (os.path.basename(path), name))

    def test_placeholder_invariants_match_the_fixture(self):
        for path in EXPECTED:
            expectation = load(path)
            fixture = self._fixture_for(expectation)
            products = {p["product_id"]: p for p in fixture["products"]}
            for product_exp in expectation["products"]:
                invariant = product_exp.get("placeholder_invariant")
                if not invariant:
                    continue
                product = products[product_exp["product_id"]]
                for entry in invariant["placeholders_present"]:
                    resolution = resolve(product, entry["locator"])
                    self.assertTrue(resolution.ok, "%s: %s" % (path, entry["locator"]))
                    self.assertEqual(
                        resolution.text, entry["literal"],
                        "%s: %s" % (path, entry["locator"]),
                    )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
