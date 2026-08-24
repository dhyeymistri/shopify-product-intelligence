"""Locator parsing and resolution for the engine (PRD 8.2, 8.2.1).

These cover the engine's own resolver. `test_pip_locator.py` covers the audit's
independent implementation of the same grammar; the duplication is deliberate
(see `engine/locators.py`), so both suites exist and neither replaces the other.
"""

from __future__ import annotations

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from engine.locators import (  # noqa: E402
    LocatorError, csv_locator, parse_csv, parse_pip, resolve_pip,
)
from engine.sources import CsvSource  # noqa: E402

PRODUCT = {
    "product_id": "handle:tee",
    "identity": {"title": {"value": "Harbour Line Tee", "src": "identity.title"},
                 "brand": {"value": None, "src": None}},
    "narrative": {"description_text": {"value": "Ring-spun cotton", "src": "n"}},
    "attributes": [{"key": "material_composition", "value_raw": "100% cotton"}],
    "metafields": [{"namespace": "custom", "key": "material", "value": "cotton"}],
    "variants": [{"variant_id": "sku:HL-TEE-S", "option_values": {"Size": "S"},
                  "sku": {"value": "HL-TEE-S", "src": "s"}}],
    "options": [{"name": "Size", "values": ["S", "M"]}],
    "media": [{"url": "https://example.invalid/a.jpg", "alt": {"value": None, "src": None}}],
}


class TestParseCsv(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_csv("row12.Title"), (12, "Title", None))

    def test_span(self):
        self.assertEqual(parse_csv("row12.Description[3:9]"), (12, "Description", (3, 9)))

    def test_column_name_may_contain_spaces_and_parens(self):
        self.assertEqual(parse_csv("row2.Weight value (grams)"),
                         (2, "Weight value (grams)", None))

    def test_metafield_column_keeps_its_dots(self):
        self.assertEqual(parse_csv("row2.product.metafields.custom.material"),
                         (2, "product.metafields.custom.material", None))

    def test_round_trip(self):
        for locator in ("row2.Title", "row2.Tags[0:3]",
                        "row9.product.metafields.custom.care_note"):
            row, column, span = parse_csv(locator)
            self.assertEqual(csv_locator(row, column, span), locator)

    def test_rejects_non_csv_locator(self):
        self.assertRaises(LocatorError, parse_csv, "identity.title")

    def test_rejects_empty(self):
        self.assertRaises(LocatorError, parse_csv, "   ")

    def test_rejects_inverted_span(self):
        self.assertRaises(LocatorError, parse_csv, "row2.Title[9:3]")


class TestParsePip(unittest.TestCase):
    def test_selector_may_contain_dots(self):
        segments, _ = parse_pip("metafields[custom.material].value")
        self.assertEqual(segments[0], ("metafields", "custom.material"))

    def test_selector_may_contain_colons(self):
        segments, span = parse_pip("variants[sku:HL-TEE-S].sku")
        self.assertEqual(segments[0], ("variants", "sku:HL-TEE-S"))
        self.assertIsNone(span)

    def test_span_is_not_a_selector(self):
        _, span = parse_pip("narrative.description_text[0:9]")
        self.assertEqual(span, (0, 9))

    def test_unbalanced_bracket(self):
        self.assertRaises(LocatorError, parse_pip, "identity.title[0:3")


class TestResolvePip(unittest.TestCase):
    def test_value_pair(self):
        self.assertEqual(resolve_pip(PRODUCT, "identity.title").text, "Harbour Line Tee")

    def test_span(self):
        self.assertEqual(resolve_pip(PRODUCT, "identity.title[0:7]").text, "Harbour")

    def test_absent_resolves_to_absent_not_empty_string(self):
        resolution = resolve_pip(PRODUCT, "identity.brand")
        self.assertTrue(resolution.ok)
        self.assertIsNone(resolution.text)

    def test_span_over_absent_value_is_an_error(self):
        """PRD 8.2.1 rule 3: absent is not an empty string to slice."""
        self.assertFalse(resolve_pip(PRODUCT, "identity.brand[0:1]").ok)

    def test_span_past_end_is_an_error(self):
        self.assertFalse(resolve_pip(PRODUCT, "identity.title[0:999]").ok)

    def test_attribute_selector(self):
        self.assertEqual(
            resolve_pip(PRODUCT, "attributes[material_composition].value_raw").text,
            "100% cotton")

    def test_metafield_namespace_key_selector(self):
        self.assertEqual(resolve_pip(PRODUCT, "metafields[custom.material].value").text,
                         "cotton")

    def test_variant_option_value(self):
        self.assertEqual(
            resolve_pip(PRODUCT, "variants[sku:HL-TEE-S].option_values[Size]").text, "S")

    def test_positional_selector(self):
        self.assertEqual(resolve_pip(PRODUCT, "media[0].url").text,
                         "https://example.invalid/a.jpg")

    def test_unknown_field_fails_loudly(self):
        self.assertFalse(resolve_pip(PRODUCT, "identity.nope").ok)

    def test_selector_matching_nothing_fails_loudly(self):
        self.assertFalse(resolve_pip(PRODUCT, "variants[sku:NOPE].sku").ok)

    def test_node_without_text_needs_require_text_false(self):
        self.assertFalse(resolve_pip(PRODUCT, "options[Size]").ok)
        self.assertTrue(resolve_pip(PRODUCT, "options[Size]", require_text=False).ok)


class TestCsvSource(unittest.TestCase):
    def setUp(self):
        self.source = CsvSource(
            ["Title", "URL handle", "Description"],
            [(2, ["Tee", "tee", "<p>Ring-spun <b>cotton</b></p>"]),
             (3, ["", "tee", ""])],
            file="x.csv")

    def test_cell(self):
        self.assertEqual(self.source.resolve("row2.Title").text, "Tee")

    def test_empty_cell_is_absent(self):
        resolution = self.source.resolve("row3.Title")
        self.assertTrue(resolution.ok)
        self.assertIsNone(resolution.text)

    def test_span_uses_the_plain_text_extraction(self):
        """PRD 8.2: spans are offsets into the plain-text extraction."""
        self.assertEqual(self.source.resolve("row2.Description[0:16]").text,
                         "Ring-spun cotton")

    def test_raw_view_keeps_the_html(self):
        self.assertIn("<b>", self.source.resolve("row2.Description").text)

    def test_missing_row_fails_loudly(self):
        self.assertFalse(self.source.resolve("row99.Title").ok)

    def test_missing_column_fails_loudly(self):
        self.assertFalse(self.source.resolve("row2.Nope").ok)

    def test_record_locator(self):
        self.assertEqual(self.source.record_locator([2, 3, 4]), "rows 2-4")
        self.assertEqual(self.source.record_locator([7]), "row7")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
