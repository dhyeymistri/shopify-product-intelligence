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

#: Format C fixtures. `FIXTURES` keeps its name and its meaning: the tests that
#: read an NPR-shaped document -- envelope, `{value, src}` pairs, PIP locators --
#: are Format C tests and stay that way.
FIXTURES = sorted(glob.glob(os.path.join(REPO, "evals/fixtures/*/*.pip.json")))
PIP_FIXTURES = FIXTURES

#: `evals/fixtures/csv/` is normalizer input (PRD 5.1), not a scored corpus set:
#: it has no expectations and is not in `REQUIRED_SETS`. A Format A fixture that
#: belongs to a scored set lives in that set's directory beside its Format C
#: siblings, because a set is defined by what it measures and not by its format.
NORMALIZER_ONLY_DIRS = {"csv"}
CSV_FIXTURES = sorted(
    path for path in glob.glob(os.path.join(REPO, "evals/fixtures/*/*.csv"))
    if os.path.basename(os.path.dirname(path)) not in NORMALIZER_ONLY_DIRS)

ALL_FIXTURES = sorted(PIP_FIXTURES + CSV_FIXTURES)
EXPECTED = sorted(glob.glob(os.path.join(REPO, "evals/expected/*/*.expected.json")))

REQUIRED_SETS = {"sparse": 10, "adversarial": 4, "checks": 9,
                 "recognition": 24, "uncategorized": 12}

#: Expectation formats (PRD 12.2). An expectation that omits `format` addresses
#: a Format C fixture, which is why the 33 that predate this are unchanged.
FORMAT_PIP = "pip_json"
FORMAT_CSV = "shopify_csv"


def load(path):
    with open(path) as handle:
        return json.load(handle)


def fixture_format(expectation):
    return expectation.get("format", FORMAT_PIP)


def fixture_path(expectation):
    ext = ".csv" if fixture_format(expectation) == FORMAT_CSV else ".pip.json"
    return os.path.join(REPO, "evals/fixtures", expectation["set"],
                        expectation["fixture_id"] + ext)


class TestCorpusShape(unittest.TestCase):
    def test_required_counts(self):
        counts = {}
        for path in ALL_FIXTURES:
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

    def test_every_csv_fixture_has_an_expectation_file(self):
        """Format A carries no envelope, so the set and id come from the path."""
        by_path = dict((fixture_path(load(p)), p) for p in EXPECTED)
        for path in CSV_FIXTURES:
            self.assertIn(path, by_path, "missing expectation for %s" % path)

    def test_every_csv_fixture_declares_provenance_in_its_expectation(self):
        """PRD 12.1 requires a provenance note on every fixture. A Format A file
        has nowhere to put one -- there is no envelope -- so its expectation
        carries it, and this is the assertion that keeps that from being
        forgotten rather than merely permitted."""
        for path in EXPECTED:
            expectation = load(path)
            if fixture_format(expectation) != FORMAT_CSV:
                continue
            provenance = expectation.get("provenance")
            self.assertTrue(provenance, "%s: missing provenance" % path)
            self.assertIn("Synthetic", provenance, path)

    def test_every_expectation_names_a_fixture_that_exists(self):
        for path in EXPECTED:
            expectation = load(path)
            self.assertTrue(os.path.exists(fixture_path(expectation)),
                            "%s: names a fixture that does not exist" % path)

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
                    # `options` was omitted here until D-032, and that omission
                    # is how 21 fixtures carried an option locator addressing
                    # the element rather than the name.
                    ("options", product.get("options", [])),
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

    def test_option_src_reproduces_the_option_name(self):
        """D-032, at the corpus layer.

        PRD 6.1's own NPR example locates an option at its **name**
        (``"src": "row12.Option1 name"``) and PRD 6.2 rule 1 requires a ``src``
        to resolve back to the value beside it. Resolving is not enough: an
        element locator such as ``options[Size]`` resolves to a node, carries
        no text of its own, and therefore cannot be quoted -- which is what
        silently suppressed `VARIANT.OPTION_NAMES_MEANINGFUL` on every Format C
        record with options. The assertion is equality with the name, so
        neither the element locator nor a near miss like
        ``options[Size].values`` can come back.
        """
        checked = 0
        for path in FIXTURES:
            for product in load(path)["products"]:
                for option in product.get("options", []):
                    src = option.get("src")
                    self.assertTrue(
                        src, "%s: option %r carries no src" % (path, option.get("name")))
                    resolution = resolve(product, src)
                    self.assertTrue(
                        resolution.ok,
                        "%s: option src %r -> %s" % (path, src, resolution.error))
                    self.assertEqual(
                        resolution.text, option.get("name"),
                        "%s: option src %r resolves to %r, not the option name %r; "
                        "a value that cannot be reproduced at its locator cannot "
                        "be evidenced (PRD 8.3 rule 4)"
                        % (path, src, resolution.text, option.get("name")))
                    checked += 1
        self.assertGreater(checked, 0, "no option carried a src to check")

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
        """The Format C document an expectation addresses.

        Format A has no NPR-shaped document to return, so the tests that read
        one skip it explicitly via :meth:`_is_csv` rather than being handed an
        empty stand-in they could pass over in silence.
        """
        return load(fixture_path(expectation))

    @staticmethod
    def _is_csv(expectation):
        return fixture_format(expectation) == FORMAT_CSV

    @staticmethod
    def _csv_text(expectation):
        with open(fixture_path(expectation), encoding="utf-8") as handle:
            return handle.read()

    def test_baits_are_genuinely_absent_from_input(self):
        """The load-bearing corpus invariant.

        A bait that is actually present in the fixture would make FAB014 fire on
        an honest report -- turning the audit into a generator of false
        accusations. Every declared bait must be absent from the input it
        belongs to.
        """
        for path in EXPECTED:
            expectation = load(path)
            if self._is_csv(expectation):
                # The supplied input *is* the file, so containment is checked
                # against its text. That is stricter than walking an NPR: it
                # also catches a bait sitting in a column the normalizer drops.
                text = self._csv_text(expectation).lower()
                for product_exp in expectation["products"]:
                    for bait in product_exp.get("must_not_fabricate", []):
                        self.assertNotIn(
                            bait.lower(), text,
                            "%s: bait %r is present in the supplied input"
                            % (os.path.basename(path), bait))
                continue
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
            if self._is_csv(expectation):
                continue    # PIP-grammar resolver; Format A locators are row<N>.<Column>
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
            if self._is_csv(expectation):
                continue    # PIP-grammar resolver; Format A locators are row<N>.<Column>
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
            if self._is_csv(expectation):
                continue    # PIP-grammar resolver; Format A locators are row<N>.<Column>
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
