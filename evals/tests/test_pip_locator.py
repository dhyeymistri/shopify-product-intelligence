"""Unit tests for PIP locator parsing and resolution."""

from __future__ import annotations

import json
import os
import unittest

from audits.pip_locator import LocatorError, parse, resolve

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def product(rel, index=0):
    with open(os.path.join(REPO, rel)) as handle:
        return json.load(handle)["products"][index]


TEE = "evals/fixtures/sparse/sparse-apparel-01.pip.json"
TEE2 = "evals/fixtures/sparse/sparse-apparel-02.pip.json"
BIN = "evals/fixtures/adversarial/adv-03-placeholder-values.pip.json"


class TestParse(unittest.TestCase):
    def test_plain_path(self):
        self.assertEqual(parse("identity.title"), ([("identity", None), ("title", None)], None))

    def test_span_is_not_a_selector(self):
        segments, span = parse("narrative.description_text[27:45]")
        self.assertEqual(span, (27, 45))
        self.assertEqual(segments[-1], ("description_text", None))

    def test_selector_may_contain_dots(self):
        """metafields[custom.material] must survive segment splitting."""
        segments, _ = parse("metafields[custom.material].value")
        self.assertEqual(segments[0], ("metafields", "custom.material"))

    def test_selector_may_contain_colons(self):
        segments, span = parse("variants[sku:NG-CREW-001].sku")
        self.assertEqual(segments[0], ("variants", "sku:NG-CREW-001"))
        self.assertIsNone(span)

    def test_rejects_empty_and_unbalanced(self):
        for bad in ("", "   ", "identity.title[0:5"):
            self.assertRaises(LocatorError, parse, bad)

    def test_rejects_inverted_span(self):
        self.assertRaises(LocatorError, parse, "identity.title[9:2]")


class TestResolve(unittest.TestCase):
    def test_value_src_pair_resolves_to_its_value(self):
        self.assertEqual(
            resolve(product(TEE), "identity.title").text, "Northgate Crew Neck T-Shirt"
        )

    def test_span_slices_the_value(self):
        self.assertEqual(resolve(product(TEE), "identity.title[10:27]").text, "Crew Neck T-Shirt")

    def test_variant_selector(self):
        self.assertEqual(
            resolve(product(TEE), "variants[sku:NG-CREW-001].sku").text, "NG-CREW-001"
        )

    def test_option_values_dict_selector(self):
        self.assertEqual(
            resolve(product(TEE2), "variants[sku:HL-TEE-M].option_values[Size]").text, "M"
        )

    def test_metafield_namespace_key_selector(self):
        self.assertEqual(
            resolve(product(BIN), "metafields[custom.capacity].value").text, "N/A"
        )

    def test_attribute_key_selector(self):
        self.assertEqual(
            resolve(product(TEE2), "attributes[material_composition].value_raw").text,
            "soft cotton jersey",
        )

    def test_absent_value_resolves_to_none_not_empty_string(self):
        """PRD 6.2 rule 2: null means absent and is never coerced."""
        resolution = resolve(product(TEE), "identity.model_or_mpn")
        self.assertTrue(resolution.ok)
        self.assertIsNone(resolution.text)

    def test_missing_field_fails_with_a_reason(self):
        resolution = resolve(product(TEE), "identity.vendor_name")
        self.assertFalse(resolution.ok)
        self.assertIn("no such field", resolution.error)

    def test_unmatched_selector_fails(self):
        resolution = resolve(product(TEE), "variants[sku:DOES-NOT-EXIST].sku")
        self.assertFalse(resolution.ok)
        self.assertIn("matched nothing", resolution.error)

    def test_span_beyond_value_length_fails(self):
        resolution = resolve(product(TEE), "identity.title[0:9999]")
        self.assertFalse(resolution.ok)
        self.assertIn("exceeds value length", resolution.error)

    def test_span_on_absent_value_fails(self):
        resolution = resolve(product(TEE), "identity.model_or_mpn[0:4]")
        self.assertFalse(resolution.ok)
        self.assertIn("absent", resolution.error)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
