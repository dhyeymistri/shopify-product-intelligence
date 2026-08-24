"""Unit tests for fact-token extraction.

The extractor decides what counts as a product-fact assertion. Two ways it can
be wrong, and both are tested here:

* too eager  -> honest framing prose gets flagged, and the audit becomes noise
  an implementer learns to ignore;
* too lax    -> a fabricated value slips through, and the gate is decorative.
"""

from __future__ import annotations

import unittest

from audits import factlex
from audits.factlex import (
    COMPATIBILITY, DIMENSION, MATERIAL, MODEL, SAFETY, SPEC, USECASE, extract,
)


def kinds(text):
    return sorted({t.kind for t in extract(text)})


def texts(text):
    return sorted(t.text for t in extract(text))


class TestDetectsFacts(unittest.TestCase):
    def test_quantities(self):
        self.assertIn(SPEC, kinds("Weighs 290 g."))
        self.assertIn(SPEC, kinds("Holds 50 ml."))
        self.assertIn(SPEC, kinds("Runs for 30 hours."))

    def test_percentages(self):
        self.assertIn(SPEC, kinds("Made of 60% cotton."))

    def test_dimension_triple_is_one_token_not_three(self):
        tokens = extract("Measures 80 x 45 x 90 cm.")
        dimensions = [t for t in tokens if t.kind == DIMENSION]
        self.assertEqual(len(dimensions), 1)
        self.assertEqual(dimensions[0].text, "80 x 45 x 90 cm")

    def test_standards_and_marks(self):
        for text in ("Certified to EN 1078.", "Meets ISO 12312.", "Rated IP67."):
            self.assertIn(SAFETY, kinds(text), text)

    def test_model_numbers(self):
        self.assertIn(MODEL, kinds("Model NG-4471B."))
        self.assertIn(MODEL, kinds("The WH-1000XM5 supports it."))

    def test_materials(self):
        self.assertIn(MATERIAL, kinds("A merino wool blend."))
        self.assertIn(MATERIAL, kinds("Solid oak frame."))

    def test_ingredients_count_as_material_assertions(self):
        self.assertIn(MATERIAL, kinds("Contains niacinamide."))

    def test_compatibility(self):
        self.assertIn(COMPATIBILITY, kinds("Works with iOS and Android."))
        self.assertIn(COMPATIBILITY, kinds("Charges over USB-C."))

    def test_safety_claims(self):
        self.assertIn(SAFETY, kinds("This item is BPA-free."))
        self.assertIn(SAFETY, kinds("Dermatologist tested."))

    def test_use_cases(self):
        self.assertIn(USECASE, kinds("Ideal for weekend camping trips."))
        self.assertIn(USECASE, kinds("Designed for competitive swimming."))


class TestIgnoresFraming(unittest.TestCase):
    """Honest report prose must produce no tokens at all."""

    FRAMING = [
        "Not stated in the supplied data.",
        "No composition value was found in the attributes or the description.",
        "What is the fabric composition, by percentage?",
        "Which size system do the sizes follow?",
        "Checked: attributes[material_composition], metafields.*",
        "APPAREL.MATERIAL_COMPOSITION - UNKNOWN - severity critical - confidence high",
        "Finding F-0003 relates to decision D-005 and criterion AC-I1.",
        "This attribute is not inheritable from the product.",
        "A basis is referenced.",
        "Two size variants are offered, but neither carries a measured fit range.",
    ]

    def test_no_false_positives(self):
        for text in self.FRAMING:
            self.assertEqual(extract(text), [], "false positive on %r" % text)

    def test_generic_nouns_are_not_material_claims(self):
        """Naming the category of thing is not asserting the thing."""
        for text in ("The fabric is not stated.", "No material was found.",
                     "Textile content is unknown.", "What is the shell construction?"):
            self.assertEqual(
                [t for t in extract(text) if t.kind == MATERIAL], [], text
            )

    def test_asking_about_certification_is_not_claiming_one(self):
        text = "Which safety standard is this helmet certified to?"
        self.assertEqual([t for t in extract(text) if t.kind == SAFETY], [], text)


class TestAllowlistIntegrity(unittest.TestCase):
    def test_allowlist_holds_no_product_values(self):
        factlex.assert_allowlist_has_no_values()

    def test_attribute_keys_are_allowlisted(self):
        """A report must be able to name the attribute it is asking for."""
        for key in ("material_composition", "safety_certification", "assembled_dimensions"):
            self.assertIn(key, factlex.ATTRIBUTE_KEYS)
            self.assertEqual(extract(key), [])

    def test_allowlisting_a_key_does_not_excuse_its_value(self):
        """The load-bearing distinction: naming != asserting."""
        self.assertEqual(extract("material_composition"), [])
        self.assertIn(MATERIAL, kinds("material_composition is cotton"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
