"""P2 -- the deterministic normalizer.

Every test here is really one of two questions:

  * did the normalizer preserve what the input said, and
  * did it refuse to say anything the input did not?

The second is the one the corpus exists for. A normalizer that quietly copies a
colour from one variant onto its siblings, or reads `custom.material` as
`material_composition`, produces an NPR that looks better than the data and
carries locators that make the invention look sourced. Those cases are tested
by name, not by inference over the happy path.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from engine import errors, model, normalize_document, normalize_file, validate  # noqa: E402
from engine.csv_input import normalize as normalize_csv  # noqa: E402
from engine.normalize import detect_format  # noqa: E402

CSV_DIR = os.path.join(REPO, "evals/fixtures/csv")
PIP_GLOB_DIRS = [os.path.join(REPO, "evals/fixtures/sparse"),
                 os.path.join(REPO, "evals/fixtures/adversarial")]


def fixture(name):
    return os.path.join(CSV_DIR, name)


def csv_text(header, rows):
    """Build CSV text without hand-quoting, so tests state values not encodings."""
    import csv as _csv
    buffer = io.StringIO()
    writer = _csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def only(result):
    assert len(result.products) == 1, result.products
    return result.products[0]


def by_id(products):
    return dict((p["product_id"], p) for p in products)


def find_variant(npr, variant_id):
    for variant in npr["variants"]:
        if variant["variant_id"] == variant_id:
            return variant
    raise AssertionError("no variant %r in %r" % (variant_id, npr["product_id"]))


def option_values(npr, variant_id):
    """``{name: value}`` from the ``{value, src}`` pairs D-033 introduced.

    Assertions about *which value is on which variant* stay about that, and the
    pair shape itself is asserted separately where it is the subject.
    """
    return dict((name, pair["value"])
                for name, pair in find_variant(npr, variant_id)["option_values"].items())


# ---------------------------------------------------------------------------
# format detection
# ---------------------------------------------------------------------------

class TestFormatDetection(unittest.TestCase):
    def test_csv(self):
        self.assertEqual(detect_format(text="Title,URL handle\nTee,tee\n"),
                         model.FORMAT_CSV)

    def test_pip(self):
        self.assertEqual(detect_format(data={"products": []}), model.FORMAT_PIP)

    def test_unrecognized_is_refused_not_guessed(self):
        """PRD 5.4: an unrecognized format refuses the run. Never guess a mapping."""
        with self.assertRaises(errors.NormalizationRefused):
            detect_format(text="name;price\nTee;10\n")

    def test_graphql_array_is_refused_by_name(self):
        with self.assertRaises(errors.NormalizationRefused) as caught:
            detect_format(data=[{"title": "Tee"}])
        self.assertIn("Format B", str(caught.exception))

    def test_invalid_json_is_refused(self):
        with self.assertRaises(errors.NormalizationRefused):
            detect_format(text='{"products": [')


# ---------------------------------------------------------------------------
# Format C -- PIP
# ---------------------------------------------------------------------------

class TestPipNormalization(unittest.TestCase):
    def _fixtures(self):
        paths = []
        for directory in PIP_GLOB_DIRS:
            for name in sorted(os.listdir(directory)):
                if name.endswith(".pip.json"):
                    paths.append(os.path.join(directory, name))
        return paths

    def test_every_corpus_fixture_normalizes_without_a_run_error(self):
        for path in self._fixtures():
            result = normalize_file(path)
            self.assertEqual(result.run_errors, [],
                             "%s produced run errors" % os.path.basename(path))
            self.assertEqual(len(result.products), 1, os.path.basename(path))

    def test_normalization_is_the_identity_function_on_pip(self):
        """PRD 5.3: Format C exists so that normalization has a known answer.

        The only member that may differ is `tags`, which PRD 6.1's skeleton
        omits and `engine/model.py` documents as a gap -- an absent member is
        completed to the empty list, never invented.
        """
        for path in self._fixtures():
            with open(path, encoding="utf-8") as handle:
                supplied = json.load(handle)["products"][0]
            produced = normalize_file(path).products[0]
            for member in set(supplied) | set(produced):
                if member == "tags" and member not in supplied:
                    self.assertEqual(produced["tags"], [])
                    continue
                self.assertEqual(produced.get(member), supplied.get(member),
                                 "%s: member %r changed" % (os.path.basename(path), member))

    def test_fixture_envelope_never_reaches_the_record(self):
        """PRD 5.3.1: the envelope is metadata about the file, not supplied input."""
        document = {
            "pip_version": "0.1",
            "fixture": {"id": "x", "intent": "bait: say the shell is polycarbonate",
                        "notes": "polycarbonate", "provenance": "Synthetic."},
            "products": [{"product_id": "handle:h",
                          "identity": {"title": {"value": "Helmet", "src": "identity.title"}}}],
        }
        npr = only(normalize_document(document, format=model.FORMAT_PIP))
        self.assertNotIn("polycarbonate", json.dumps(npr))
        self.assertNotIn("fixture", npr["raw_extras"])
        self.assertNotIn("pip_version", npr["raw_extras"])

    def test_unknown_member_is_preserved_not_dropped(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"}},
            "vendor_notes": {"internal": "reorder in March"},
        }]}
        npr = only(normalize_document(document, format=model.FORMAT_PIP))
        self.assertEqual(npr["raw_extras"]["vendor_notes"], {"internal": "reorder in March"})

    def test_unknown_identity_member_is_preserved_not_dropped(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"},
                         "internal_code": "Z-99"},
        }]}
        npr = only(normalize_document(document, format=model.FORMAT_PIP))
        self.assertEqual(npr["raw_extras"]["identity.internal_code"], "Z-99")

    def test_missing_optional_members_are_completed_not_invented(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"}}}]}
        npr = only(normalize_document(document, format=model.FORMAT_PIP))
        for member in model.TOP_LEVEL_FIELDS:
            self.assertIn(member, npr)
        self.assertEqual(npr["identity"]["brand"], {"value": None, "src": None})
        self.assertEqual(npr["variants"], [])
        self.assertEqual(npr["narrative"]["structure"]["word_count"], 0)

    def test_missing_product_id_is_a_named_run_error(self):
        document = {"products": [{"identity": {"title": {"value": "Tee", "src": "identity.title"}}}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertEqual(result.products, [])
        self.assertIn(errors.MISSING_IDENTITY, result.codes())

    def test_duplicate_product_id_is_skipped_not_merged(self):
        record = {"product_id": "handle:h",
                  "identity": {"title": {"value": "Tee", "src": "identity.title"}}}
        second = json.loads(json.dumps(record))
        second["identity"]["title"]["value"] = "Different Tee"
        result = normalize_document({"products": [record, second]},
                                    format=model.FORMAT_PIP)
        self.assertEqual(len(result.products), 1)
        self.assertIn(errors.DUPLICATE_PRODUCT_ID, result.codes())
        self.assertEqual(result.products[0]["identity"]["title"]["value"], "Tee")

    def test_broken_locator_keeps_the_record_out(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.nowhere"}}}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertEqual(result.products, [])
        self.assertIn(errors.BROKEN_LOCATOR, result.codes())

    def test_non_reproducible_value_keeps_the_record_out(self):
        """A value that is not what its locator resolves to is a sourced invention."""
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"}},
            "attributes": [{"key": "material_composition", "value_raw": "100% cotton",
                            "origin": "merchant_structured", "scope": "product",
                            "src": "identity.title"}]}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertEqual(result.products, [])
        self.assertIn(errors.NON_REPRODUCIBLE_EXCERPT, result.codes())

    def test_duplicate_variant_id_keeps_the_record_out(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"}},
            "variants": [
                {"variant_id": "sku:A", "option_values": {},
                 "sku": {"value": "A", "src": "variants[sku:A].sku"},
                 "barcode": {"value": None, "src": None},
                 "price": {"value": None, "currency": None, "src": None},
                 "media_refs": [], "attributes": []},
                {"variant_id": "sku:A", "option_values": {},
                 "sku": {"value": "A", "src": "variants[sku:A].sku"},
                 "barcode": {"value": None, "src": None},
                 "price": {"value": None, "currency": None, "src": None},
                 "media_refs": [], "attributes": []}]}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertEqual(result.products, [])
        self.assertIn(errors.DUPLICATE_VARIANT_ID, result.codes())

    def test_attribute_scoped_to_a_missing_variant_is_contradictory(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"}},
            "attributes": [{"key": "color_finish", "value_raw": "Tee",
                            "origin": "merchant_structured", "scope": "variant:sku:GHOST",
                            "src": "identity.title"}]}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertIn(errors.CONTRADICTORY_VARIANT_STRUCTURE, result.codes())

    def test_absent_value_may_not_carry_a_locator(self):
        """PRD 6.2 rules 1-2: absence has no location."""
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": {"value": "Tee", "src": "identity.title"},
                         "brand": {"value": None, "src": "identity.brand"}}}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertIn(errors.INVALID_PROVENANCE, result.codes())

    def test_bare_scalar_is_a_spec_violation(self):
        document = {"products": [{
            "product_id": "handle:h",
            "identity": {"title": "Tee"}}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertIn(errors.INVALID_NPR, result.codes())

    def test_non_dict_document_is_refused(self):
        with self.assertRaises(errors.NormalizationRefused):
            normalize_document([{"product_id": "x"}], format=model.FORMAT_PIP)

    def test_products_must_be_a_list(self):
        with self.assertRaises(errors.NormalizationRefused):
            normalize_document({"products": {}}, format=model.FORMAT_PIP)

    def test_malformed_record_is_named_and_the_run_continues(self):
        document = {"products": [
            "not an object",
            {"product_id": "handle:h",
             "identity": {"title": {"value": "Tee", "src": "identity.title"}}}]}
        result = normalize_document(document, format=model.FORMAT_PIP)
        self.assertEqual(len(result.products), 1)
        self.assertIn(errors.MALFORMED_RECORD, result.codes())
        self.assertEqual(result.run_errors[0].record, "products[0]")

    def test_batch_ceiling_warns_and_processes_the_first_200(self):
        records = [{"product_id": "handle:h%d" % i,
                    "identity": {"title": {"value": "Tee %d" % i, "src": "identity.title"}}}
                   for i in range(205)]
        result = normalize_document({"products": records}, format=model.FORMAT_PIP)
        self.assertEqual(len(result.products), 200)
        self.assertIn(errors.BATCH_CEILING, result.codes())


# ---------------------------------------------------------------------------
# Format A -- Shopify CSV
# ---------------------------------------------------------------------------

class TestCsvSimple(unittest.TestCase):
    def setUp(self):
        self.result = normalize_file(fixture("csv-simple.csv"))
        self.npr = only(self.result)

    def test_no_run_errors(self):
        self.assertEqual(self.result.run_errors, [])

    def test_identity_and_locators(self):
        identity = self.npr["identity"]
        self.assertEqual(identity["title"]["value"], "Northgate Crew Neck T-Shirt")
        self.assertEqual(identity["title"]["src"], "row2.Title")
        self.assertEqual(identity["brand"]["src"], "row2.Vendor")
        self.assertEqual(self.npr["product_id"], "handle:northgate-crew-neck-tee")

    def test_undocumented_field_stays_absent(self):
        """`model_or_mpn` has no CSV column; reading it out of the SKU is inference."""
        self.assertEqual(self.npr["identity"]["model_or_mpn"],
                         {"value": None, "src": None})

    def test_single_row_yields_one_variant(self):
        self.assertEqual([v["variant_id"] for v in self.npr["variants"]],
                         ["sku:NG-CREW-001"])
        self.assertEqual(self.npr["variants"][0]["price"],
                         {"value": "28.00", "currency": None, "src": "row2.Price"})

    def test_currency_is_absent_because_the_format_states_none(self):
        self.assertIsNone(self.npr["variants"][0]["price"]["currency"])

    def test_tags_are_individually_quotable(self):
        self.assertEqual([t["value"] for t in self.npr["tags"]], ["tee", "cotton"])
        for tag in self.npr["tags"]:
            self.assertEqual(self.result.source.resolve(tag["src"]).text, tag["value"])

    def test_source_locator_covers_the_record(self):
        self.assertEqual(self.npr["source"]["locator"], "row2")
        self.assertEqual(self.npr["source"]["format"], "shopify_csv")


class TestCsvVariants(unittest.TestCase):
    def setUp(self):
        self.result = normalize_file(fixture("csv-variants.csv"))
        self.npr = only(self.result)

    def test_no_run_errors(self):
        self.assertEqual(self.result.run_errors, [])

    def test_rows_of_one_handle_group_are_one_product(self):
        self.assertEqual(self.npr["source"]["locator"], "rows 2-5")

    def test_three_variants_and_no_variant_for_the_media_row(self):
        """PRD 5.1: a row contributing only an image is a media row, not a variant."""
        self.assertEqual([v["variant_id"] for v in self.npr["variants"]],
                         ["sku:HL-TEE-S-BLK", "sku:HL-TEE-M-BLK", "sku:HL-TEE-M-ECR"])

    def test_product_level_fields_come_from_the_first_row(self):
        self.assertEqual(self.npr["identity"]["title"]["src"], "row2.Title")
        self.assertEqual(self.npr["identity"]["declared_category"]["value"],
                         "Apparel & Accessories > Clothing > Shirts & Tops")

    def test_empty_product_cell_on_a_continuation_row_is_not_an_empty_value(self):
        """PRD 5.1. Row 3 has no Title; the product still has one."""
        self.assertEqual(self.npr["identity"]["title"]["value"], "Harbour Line Tee")

    def test_variant_specific_values_keep_their_own_row(self):
        self.assertEqual(find_variant(self.npr, "sku:HL-TEE-M-ECR")["price"],
                         {"value": "34.00", "currency": None, "src": "row4.Price"})
        self.assertEqual(find_variant(self.npr, "sku:HL-TEE-S-BLK")["barcode"]["src"],
                         "row2.Barcode")

    def test_a_value_on_one_variant_is_not_given_to_the_others(self):
        """The barcode is stated once. It describes one variant, not three."""
        self.assertEqual(find_variant(self.npr, "sku:HL-TEE-M-BLK")["barcode"],
                         {"value": None, "src": None})
        self.assertEqual(find_variant(self.npr, "sku:HL-TEE-M-ECR")["barcode"],
                         {"value": None, "src": None})

    def test_option_values_are_per_variant(self):
        self.assertEqual(option_values(self.npr, "sku:HL-TEE-M-ECR"),
                         {"Size": "M", "Color": "Ecru"})

    def test_each_option_value_carries_its_own_locator(self):
        """D-033: the pair, and the locator that makes it evidenceable."""
        variant = find_variant(self.npr, "sku:HL-TEE-M-ECR")
        for name, pair in variant["option_values"].items():
            self.assertIn("value", pair, name)
            self.assertIn("src", pair, name)
            self.assertTrue(pair["src"].startswith("row"), pair["src"])

    def test_options_list_distinct_values_in_order_of_appearance(self):
        options = dict((o["name"], o["values"]) for o in self.npr["options"])
        self.assertEqual(options, {"Size": ["S", "M"], "Color": ["Black", "Ecru"]})

    def test_product_and_variant_media_are_scoped_apart(self):
        scopes = [(m["src"], m["scope"]) for m in self.npr["media"]]
        self.assertIn(("row2.Product image URL", "product"), scopes)
        self.assertIn(("row3.Variant image URL", "variant:sku:HL-TEE-M-BLK"), scopes)
        self.assertIn("https://example.invalid/hl-tee-black.jpg",
                      find_variant(self.npr, "sku:HL-TEE-M-BLK")["media_refs"])

    def test_metafield_columns_are_parsed_into_namespace_and_key(self):
        fields = dict(((m["namespace"], m["key"]), m) for m in self.npr["metafields"])
        self.assertIn(("custom", "material_composition"), fields)
        self.assertIn(("custom", "care_note"), fields)
        self.assertEqual(fields[("custom", "care_note")]["src"],
                         "row2.product.metafields.custom.care_note")

    def test_only_an_exact_taxonomy_key_is_promoted_to_an_attribute(self):
        """PRD 6.2 rule 5. Reading `care_note` as `care_instructions` is inference."""
        self.assertEqual([a["key"] for a in self.npr["attributes"]],
                         ["material_composition"])
        self.assertEqual(self.npr["attributes"][0]["origin"], "merchant_structured")
        self.assertEqual(self.npr["attributes"][0]["scope"], "product")

    def test_description_keeps_both_html_and_extracted_text(self):
        narrative = self.npr["narrative"]
        self.assertIn("<ul>", narrative["description_html"]["value"])
        self.assertNotIn("<ul>", narrative["description_text"]["value"])
        self.assertIn("Ring-spun cotton", narrative["description_text"]["value"])

    def test_structure_signals_are_recorded(self):
        self.assertEqual(
            {k: v for k, v in self.npr["narrative"]["structure"].items() if k != "word_count"},
            {"has_lists": True, "has_tables": False, "has_headings": True})

    def test_documented_columns_with_no_npr_member_are_preserved(self):
        extras = self.npr["raw_extras"]
        self.assertEqual(extras["Status"], [{"value": "active", "src": "row2.Status"}])
        self.assertEqual(extras["Weight value (grams)"],
                         [{"value": "180", "src": "row2.Weight value (grams)"}])


class TestCsvMultipleProducts(unittest.TestCase):
    def setUp(self):
        self.result = normalize_file(fixture("csv-multi-product.csv"))
        self.products = by_id(self.result.products)

    def test_three_products(self):
        self.assertEqual(sorted(self.products),
                         ["handle:cafe-creme-lip-balm", "handle:oritatami-kasa",
                          "handle:trailhead-20l-pack"])
        self.assertEqual(self.result.run_errors, [])

    def test_two_rows_of_one_handle_are_one_product_with_two_variants(self):
        npr = self.products["handle:cafe-creme-lip-balm"]
        self.assertEqual(len(npr["variants"]), 2)
        self.assertEqual(npr["source"]["locator"], "rows 2-3")

    def test_unicode_survives_verbatim(self):
        npr = self.products["handle:oritatami-kasa"]
        self.assertEqual(npr["identity"]["title"]["value"], "折りたたみ傘")
        self.assertEqual(npr["identity"]["brand"]["value"], "雨具工房")
        self.assertEqual(option_values(npr, "sku:UMB-NAV"), {"色": "紺"})

    def test_unicode_accents_are_not_folded(self):
        npr = self.products["handle:cafe-creme-lip-balm"]
        self.assertEqual(npr["identity"]["title"]["value"], "Café Crème Lip Balm")
        self.assertIn("Baume à lèvres", npr["narrative"]["description_text"]["value"])

    def test_quoted_cell_containing_commas_splits_only_on_tag_separators(self):
        npr = self.products["handle:trailhead-20l-pack"]
        self.assertEqual([t["value"] for t in npr["tags"]],
                         ["outdoor", "hiking", '"day use"'])

    def test_embedded_newline_does_not_shift_later_row_numbers(self):
        """Row numbers are record indices, so a quoted newline cannot desync them."""
        npr = self.products["handle:trailhead-20l-pack"]
        self.assertEqual(npr["source"]["locator"], "row4")
        self.assertIn("\n", npr["narrative"]["description_html"]["value"])
        self.assertEqual(self.products["handle:oritatami-kasa"]["source"]["locator"],
                         "row5")

    def test_a_price_that_is_not_a_decimal_is_kept_as_written(self):
        """`14,00` is what the merchant supplied. Reformatting it is a repair."""
        npr = self.products["handle:cafe-creme-lip-balm"]
        self.assertEqual(find_variant(npr, "sku:MC-LB-CAF")["price"]["value"], "14,00")


class TestCsvEdgeCases(unittest.TestCase):
    def test_empty_product_has_no_variants_and_no_invented_values(self):
        npr = only(normalize_file(fixture("csv-empty-product.csv")))
        self.assertEqual(npr["variants"], [])
        self.assertEqual(npr["options"], [])
        self.assertEqual(npr["media"], [])
        self.assertEqual(npr["tags"], [])
        self.assertEqual(npr["narrative"]["description_text"],
                         {"value": None, "src": None})

    def test_header_only_file_yields_no_products(self):
        result = normalize_document("Title,URL handle\n", format=model.FORMAT_CSV)
        self.assertEqual(result.products, [])
        self.assertEqual(result.run_errors, [])

    def test_file_without_the_defining_columns_is_refused(self):
        with self.assertRaises(errors.NormalizationRefused):
            normalize_document("Name,Cost\nTee,10\n", format=model.FORMAT_CSV)

    def test_empty_file_is_refused(self):
        with self.assertRaises(errors.NormalizationRefused):
            normalize_document("", format=model.FORMAT_CSV)

    def test_unknown_columns_are_preserved_verbatim(self):
        npr = only(normalize_file(fixture("csv-unknown-columns.csv")))
        extras = npr["raw_extras"]
        self.assertEqual(extras["Gift Card"], [{"value": "FALSE", "src": "row2.Gift Card"}])
        self.assertEqual(extras["Cost per item"],
                         [{"value": "22.50", "src": "row2.Cost per item"}])
        self.assertIn("Included / United States", extras)

    def test_unknown_columns_are_not_interpreted(self):
        npr = only(normalize_file(fixture("csv-unknown-columns.csv")))
        self.assertEqual(npr["attributes"], [])
        self.assertEqual(npr["metafields"], [])


class TestCsvMalformedInput(unittest.TestCase):
    def setUp(self):
        self.result = normalize_file(fixture("csv-malformed.csv"))
        self.codes = self.result.codes()

    def test_sound_products_still_normalize(self):
        self.assertEqual(sorted(by_id(self.result.products)),
                         ["handle:duplicate-sku", "handle:good-product"])

    def test_ragged_row_is_skipped_and_named(self):
        self.assertIn(errors.MALFORMED_RECORD, self.codes)
        records = [e.record for e in self.result.run_errors
                   if e.code == errors.MALFORMED_RECORD]
        self.assertIn("row7", records)

    def test_row_without_a_handle_cannot_be_assigned(self):
        reasons = [e.reason for e in self.result.run_errors
                   if e.code == errors.MALFORMED_RECORD]
        self.assertTrue(any("URL handle" in r for r in reasons))

    def test_handle_group_without_a_title_is_missing_identity(self):
        self.assertIn(errors.MISSING_IDENTITY, self.codes)

    def test_duplicate_variant_id_is_skipped_not_merged(self):
        self.assertIn(errors.DUPLICATE_VARIANT_ID, self.codes)
        npr = by_id(self.result.products)["handle:duplicate-sku"]
        self.assertEqual([v["variant_id"] for v in npr["variants"]], ["sku:DUP-01"])
        self.assertEqual(npr["variants"][0]["price"]["value"], "5.00")

    def test_every_run_error_names_a_record_and_a_reason(self):
        for error in self.result.run_errors:
            self.assertTrue(error.record)
            self.assertTrue(error.reason)


class TestCsvNoInheritanceBetweenVariants(unittest.TestCase):
    """taxonomy.md 4.3: inheritance is a per-attribute property a check applies.

    The normalizer never applies it. A colour stated for the small chair is a
    fact about the small chair.
    """

    def setUp(self):
        self.npr = only(normalize_file(fixture("csv-inheritance-trap.csv")))

    def test_the_stated_colour_stays_on_its_own_variant(self):
        self.assertEqual(option_values(self.npr, "sku:SC-S"),
                         {"Size": "Small", "Colour": "Walnut"})

    def test_the_other_variants_have_no_colour(self):
        for variant_id in ("sku:SC-M", "sku:SC-L"):
            values = option_values(self.npr, variant_id)
            self.assertEqual(values, {"Size": values["Size"]})
            self.assertNotIn("Colour", values)

    def test_the_option_still_lists_only_the_value_that_was_stated(self):
        options = dict((o["name"], o["values"]) for o in self.npr["options"])
        self.assertEqual(options["Colour"], ["Walnut"])


class TestCsvValuesStayPlainSourceText(unittest.TestCase):
    """Normalization may normalize representation. It may never resolve meaning."""

    def _one(self, header, row):
        result = normalize_document(csv_text(header, [row]), format=model.FORMAT_CSV)
        return only(result)

    def test_ambiguous_values_are_kept_ambiguous(self):
        for stated in ("water resistant", "UltraShield", "wood", "USB",
                       "one size", "eco-friendly", "up to 12 hours"):
            npr = self._one(
                ["Title", "URL handle",
                 "Spec (product.metafields.custom.core_specifications)"],
                ["Widget", "widget", stated])
            self.assertEqual(npr["metafields"][0]["value"], stated)
            self.assertEqual(npr["attributes"][0]["value_raw"], stated)

    def test_case_and_whitespace_inside_a_value_are_not_touched(self):
        npr = self._one(["Title", "URL handle", "Vendor"],
                        ["  Spaced   Title  ", "spaced", "aCME  co"])
        self.assertEqual(npr["identity"]["title"]["value"], "  Spaced   Title  ")
        self.assertEqual(npr["identity"]["brand"]["value"], "aCME  co")

    def test_placeholders_are_kept_verbatim_and_labelled(self):
        """PRD 5.4/9.4: treated as absent by checks, quoted verbatim in evidence."""
        npr = self._one(
            ["Title", "URL handle",
             "Material (product.metafields.custom.material_composition)"],
            ["Widget", "widget", "TBD"])
        self.assertEqual(npr["attributes"][0]["value_raw"], "TBD")
        self.assertEqual(npr["attributes"][0]["origin"], model.ORIGIN_PLACEHOLDER)

    def test_an_empty_cell_is_absent_not_a_placeholder(self):
        npr = self._one(["Title", "URL handle", "Vendor"], ["Widget", "widget", "   "])
        self.assertEqual(npr["identity"]["brand"], {"value": None, "src": None})


class TestCsvConflictingValues(unittest.TestCase):
    """PRD 6.2 rule 3: the NPR is not a merge, and the normalizer picks no winner."""

    def setUp(self):
        text = csv_text(
            ["Title", "URL handle", "Vendor", "SKU", "Price"],
            [["Bench Lamp", "bench-lamp", "Northgate", "BL-1", "59.00"],
             ["Bench Lamp Deluxe", "bench-lamp", "Southgate", "BL-2", "69.00"]])
        self.result = normalize_document(text, format=model.FORMAT_CSV)
        self.npr = only(self.result)

    def test_the_first_row_supplies_the_product_level_value(self):
        self.assertEqual(self.npr["identity"]["title"]["value"], "Bench Lamp")

    def test_both_occurrences_survive_with_their_own_locators(self):
        self.assertEqual(
            self.npr["raw_extras"]["Title"],
            [{"value": "Bench Lamp", "src": "row2.Title"},
             {"value": "Bench Lamp Deluxe", "src": "row3.Title"}])
        self.assertEqual(
            [e["src"] for e in self.npr["raw_extras"]["Vendor"]],
            ["row2.Vendor", "row3.Vendor"])

    def test_no_value_is_discarded(self):
        rendered = json.dumps(self.npr)
        self.assertIn("Bench Lamp Deluxe", rendered)
        self.assertIn("Southgate", rendered)


class TestCsvContradictoryVariantStructure(unittest.TestCase):
    def test_option_value_without_a_declared_option_name_is_reported(self):
        text = csv_text(
            ["Title", "URL handle", "Option1 name", "Option1 value",
             "Option2 value", "SKU"],
            [["Tee", "tee", "Size", "S", "Black", "T-S"]])
        result = normalize_document(text, format=model.FORMAT_CSV)
        self.assertIn(errors.CONTRADICTORY_VARIANT_STRUCTURE, result.codes())

    def test_repeated_option_name_is_reported(self):
        text = csv_text(
            ["Title", "URL handle", "Option1 name", "Option1 value",
             "Option2 name", "Option2 value", "SKU"],
            [["Tee", "tee", "Size", "S", "Size", "M", "T-S"]])
        result = normalize_document(text, format=model.FORMAT_CSV)
        self.assertIn(errors.CONTRADICTORY_VARIANT_STRUCTURE, result.codes())

    def test_a_variant_row_without_a_sku_is_identified_by_its_row(self):
        text = csv_text(["Title", "URL handle", "Option1 name", "Option1 value", "Price"],
                        [["Tee", "tee", "Size", "S", "10.00"]])
        npr = only(normalize_document(text, format=model.FORMAT_CSV))
        self.assertEqual(npr["variants"][0]["variant_id"], "row:2")


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

class TestProvenanceReproduction(unittest.TestCase):
    """Every locator in every produced NPR must resolve to the value beside it.

    This is the invariant the whole layer exists for: a value that cannot be
    reproduced at its locator cannot be evidence (PRD 8.3 rule 4), and a
    normalizer that emits one has manufactured a fact with a citation on it.
    """

    def _paths(self):
        paths = [os.path.join(CSV_DIR, n) for n in sorted(os.listdir(CSV_DIR))
                 if n.endswith(".csv")]
        for directory in PIP_GLOB_DIRS:
            paths.extend(os.path.join(directory, n) for n in sorted(os.listdir(directory))
                         if n.endswith(".pip.json"))
        return paths

    def test_every_value_reproduces_at_its_locator(self):
        for path in self._paths():
            result = normalize_file(path)
            for npr in result.products:
                self.assertEqual(
                    validate.validate_provenance(npr, result.source), [],
                    "%s / %s" % (os.path.basename(path), npr["product_id"]))

    def test_every_produced_npr_is_structurally_valid(self):
        for path in self._paths():
            result = normalize_file(path)
            for npr in result.products:
                self.assertEqual(validate.validate_npr(npr), [],
                                 "%s / %s" % (os.path.basename(path), npr["product_id"]))

    def test_no_value_carries_a_locator_that_resolves_elsewhere(self):
        result = normalize_file(fixture("csv-variants.csv"))
        npr = result.products[0]
        for path, expected, locator in validate.iter_locators(npr):
            if not isinstance(expected, str):
                continue
            resolution = result.source.resolve(locator)
            alternate = result.source.resolve(locator, view="text")
            self.assertIn(expected, (resolution.text, alternate.text),
                          "%s at %s" % (path, locator))

    def test_span_locators_reproduce_byte_exactly(self):
        result = normalize_file(fixture("csv-variants.csv"))
        tags = result.products[0]["tags"]
        self.assertTrue(tags)
        for tag in tags:
            self.assertEqual(result.source.resolve(tag["src"]).text, tag["value"])

    def test_unicode_spans_reproduce_byte_exactly(self):
        text = csv_text(["Title", "URL handle", "Tags"],
                        [["折りたたみ傘", "kasa", "雨具, コンパクト, 紺"]])
        result = normalize_document(text, format=model.FORMAT_CSV)
        for tag in result.products[0]["tags"]:
            self.assertEqual(result.source.resolve(tag["src"]).text, tag["value"])

    def test_determinism(self):
        for path in self._paths():
            first = json.dumps(normalize_file(path).as_dict(), sort_keys=True)
            second = json.dumps(normalize_file(path).as_dict(), sort_keys=True)
            self.assertEqual(first, second, os.path.basename(path))


class TestOptionProvenanceIsCheckedAgainstTheName(unittest.TestCase):
    """D-032, at the validator layer -- the line that let the defect through.

    `iter_locators` used to pass `None` as the expected value for an option,
    which `validate_provenance` turns into a `node` view: the locator had only
    to resolve to *something*, never to reproduce the option name. That is why
    21 fixtures carried `options[Size]` -- an element with no text of its own --
    and why `VARIANT.OPTION_NAMES_MEANINGFUL` could construct no evidence and
    emitted nothing at all, in breach of PRD 8.3 rule 1.

    These assertions are the guard, not the fix. The fix is in
    `engine/validate.iter_locators`; if it is ever relaxed back, the two
    regression cases below fail rather than the corpus quietly going silent.
    """

    def _record(self):
        result = normalize_file(os.path.join(
            REPO,
            "evals/fixtures/recognition/rec-11-uncategorized-visual-option.pip.json"))
        return result.products[0], result.source

    def test_the_corpus_locator_is_accepted(self):
        npr, source = self._record()
        self.assertEqual(npr["options"][0]["src"], "options[Shade].name")
        self.assertEqual(validate.validate_provenance(npr, source), [])

    def test_an_element_locator_is_rejected(self):
        """The exact defect this repair removed."""
        npr, source = self._record()
        npr["options"][0]["src"] = "options[Shade]"
        errs = validate.validate_provenance(npr, source)
        self.assertEqual(len(errs), 1, errs)
        self.assertEqual(errs[0].code, errors.BROKEN_LOCATOR)
        self.assertIn("does not address text content", errs[0].reason)

    def test_a_locator_that_resolves_to_the_wrong_field_is_rejected(self):
        """The near miss: `options[X].values` resolves, and is still not the name.

        Requiring resolution alone would accept it; requiring reproduction of
        the option name is what does not.
        """
        npr, source = self._record()
        npr["options"][0]["src"] = "options[Shade].values"
        errs = validate.validate_provenance(npr, source)
        self.assertEqual(len(errs), 1, errs)
        self.assertEqual(errs[0].code, errors.NON_REPRODUCIBLE_EXCERPT)

    def test_the_csv_form_of_the_same_locator_is_accepted(self):
        """PRD 6.1's example is a Format A locator, so both formats are held to it."""
        result = normalize_file(os.path.join(REPO, "evals/fixtures/csv/csv-variants.csv"))
        for npr in result.products:
            for option in npr.get("options") or []:
                self.assertTrue(option["src"].startswith("row"), option["src"])
            self.assertEqual(validate.validate_provenance(npr, result.source), [])


class TestOptionValuesCarryTheirOwnProvenance(unittest.TestCase):
    """D-033, at the schema and validator layers, over **both** formats.

    `option_values` was the one NPR member holding merchant values as bare
    scalars, which is why it was the one member whose values could not be
    evidenced: `VARIANT.DIFFERENTIATED` had to compose a locator, a composed
    locator cannot be format-neutral, and the Format C form it produced does
    not parse under Format A. PRD 6.2 rule 1 governs -- every value is a
    `{value, src}` pair -- and these assertions hold the record to it.
    """

    CSV = "evals/fixtures/csv/csv-variants.csv"
    PIP = "evals/fixtures/recognition/rec-09-variant-scope-fully-covered.pip.json"

    def _both(self):
        for path in (self.CSV, self.PIP):
            result = normalize_file(os.path.join(REPO, path))
            for npr in result.products:
                yield os.path.basename(path), npr, result.source

    def test_every_option_value_is_a_pair_in_both_formats(self):
        seen = 0
        for name, npr, _ in self._both():
            for variant in npr["variants"]:
                for option, pair in (variant.get("option_values") or {}).items():
                    self.assertIsInstance(pair, dict, "%s/%s" % (name, option))
                    self.assertIn("value", pair)
                    self.assertIn("src", pair)
                    self.assertIsInstance(pair["value"], str)
                    seen += 1
        self.assertGreater(seen, 0)

    def test_each_locator_reproduces_its_own_value_in_both_formats(self):
        """The property that makes the pair worth carrying (PRD 8.3 rule 4)."""
        for name, npr, source in self._both():
            for variant in npr["variants"]:
                for option, pair in (variant.get("option_values") or {}).items():
                    resolution = source.resolve(pair["src"], npr["product_id"])
                    self.assertTrue(resolution.ok,
                                    "%s: %r -> %s" % (name, pair["src"], resolution.error))
                    self.assertEqual(resolution.text, pair["value"],
                                     "%s: %r" % (name, pair["src"]))

    def test_the_locator_is_in_each_formats_own_grammar(self):
        """A single composed string could not have satisfied both."""
        for name, npr, _ in self._both():
            for variant in npr["variants"]:
                for pair in (variant.get("option_values") or {}).values():
                    if name.endswith(".csv"):
                        self.assertTrue(pair["src"].startswith("row"), pair["src"])
                    else:
                        self.assertTrue(pair["src"].startswith("variants["), pair["src"])

    def test_provenance_validation_covers_option_values(self):
        for name, npr, source in self._both():
            self.assertEqual(validate.validate_provenance(npr, source), [], name)

    def test_a_bare_scalar_is_a_reported_contract_violation(self):
        """D-033: reported, never absorbed.

        The failure this replaces was silent in every layer at once -- no
        finding, no deferral, no run error -- so the assertion is that the
        violation is *visible*, not merely that it is refused.
        """
        import copy
        for name, npr, _ in self._both():
            npr = copy.deepcopy(npr)
            variant = npr["variants"][0]
            option = sorted(variant["option_values"])[0]
            variant["option_values"][option] = "Small"      # the old shape
            errs = validate.validate_npr(npr)
            self.assertEqual(len(errs), 1, "%s: %r" % (name, errs))
            self.assertEqual(errs[0].code, errors.INVALID_NPR)
            self.assertIn("option_values[%s]" % option, errs[0].reason)
            self.assertIn("{value, src} pair", errs[0].reason)

    def test_a_pair_whose_locator_points_elsewhere_is_rejected(self):
        """Carrying a locator is not enough; it must reproduce the value."""
        import copy
        for name, npr, source in self._both():
            # Deep-copied because a Format C record shares its variant objects
            # with the source document it came from, so mutating the NPR in
            # place would move the source with it and prove nothing.
            npr = copy.deepcopy(npr)
            variant = npr["variants"][0]
            option = sorted(variant["option_values"])[0]
            variant["option_values"][option]["value"] = "NotWhatIsThere"
            errs = validate.validate_provenance(npr, source)
            self.assertEqual(len(errs), 1, "%s: %r" % (name, errs))
            self.assertEqual(errs[0].code, errors.NON_REPRODUCIBLE_EXCERPT)

    def test_normalization_never_derives_the_locator_for_format_c(self):
        """PRD 5.3: Format C normalization is the identity function.

        A record that omits the provenance must not have it filled in, because
        that would assert a source the document did not state (D-033). What
        happens instead is PRD 5.4's rule for a malformed record: the record is
        skipped and the reason is reported. Both halves are asserted, because
        the failure D-033 replaced was one where nothing was reported at all.
        """
        import copy
        with open(os.path.join(REPO, self.PIP), encoding="utf-8") as handle:
            document = json.load(handle)
        stripped = copy.deepcopy(document)
        for product in stripped["products"]:
            for variant in product["variants"]:
                variant["option_values"] = dict(
                    (name, pair["value"])
                    for name, pair in variant["option_values"].items())

        result = normalize_document(stripped, format=model.FORMAT_PIP)

        self.assertEqual(result.products, [],
                         "a record with unprovenanced option values was accepted")
        self.assertTrue(result.run_errors, "the record was dropped silently")
        for error in result.run_errors:
            self.assertEqual(error.code, errors.INVALID_NPR)
            self.assertIn("option_values[", error.reason)
        # and nothing was invented on the way past
        self.assertNotIn(
            "src",
            json.dumps(stripped["products"][0]["variants"][0]["option_values"]))


class TestLocatorValidation(unittest.TestCase):
    def test_a_csv_locator_must_parse_as_one(self):
        self.assertIsNotNone(
            validate.validate_locator_syntax("identity.title", model.FORMAT_CSV))
        self.assertIsNone(
            validate.validate_locator_syntax("row2.Title", model.FORMAT_CSV))

    def test_a_pip_locator_must_parse_as_one(self):
        self.assertIsNone(
            validate.validate_locator_syntax("identity.title", model.FORMAT_PIP))
        self.assertIsNotNone(
            validate.validate_locator_syntax("identity.title[0:", model.FORMAT_PIP))

    def test_iter_locators_reaches_every_carrier(self):
        npr = only(normalize_file(fixture("csv-variants.csv")))
        paths = set(path for path, _, _ in validate.iter_locators(npr))
        for expected in ("identity.title", "narrative.description_text", "tags[0]",
                         "attributes[0]", "metafields[0]", "media[0]",
                         "options[0].name", "variants[0].sku", "variants[0].price"):
            self.assertIn(expected, paths)


class TestNoInference(unittest.TestCase):
    """The rule the layer is built around (AGENTS.md 2, PRD 6.2 rule 4)."""

    def test_category_is_never_assigned_by_the_normalizer(self):
        """taxonomy.md 2: classification is inference, and it is a check's job."""
        npr = only(normalize_file(fixture("csv-variants.csv")))
        self.assertNotIn("category", npr)

    def test_nothing_is_derived_from_the_title(self):
        text = csv_text(["Title", "URL handle", "Type"],
                        [["TrailPro Bike Helmet", "trailpro-bike-helmet", "Bike Helmets"]])
        npr = only(normalize_document(text, format=model.FORMAT_CSV))
        self.assertEqual(npr["attributes"], [])
        rendered = json.dumps(npr).lower()
        for invented in ("polycarbonate", "en 1078", "cpsc", "impact"):
            self.assertNotIn(invented, rendered)

    def test_a_metafield_key_that_merely_resembles_a_taxonomy_key_is_not_promoted(self):
        text = csv_text(
            ["Title", "URL handle",
             "Material (product.metafields.custom.material)",
             "Fabric (product.metafields.custom.fabric)"],
            [["Tee", "tee", "cotton", "cotton"]])
        npr = only(normalize_document(text, format=model.FORMAT_CSV))
        self.assertEqual(npr["attributes"], [])
        self.assertEqual(len(npr["metafields"]), 2)

    def test_claims_are_not_extracted_in_p2(self):
        """Claim recognition is a P3 check with a lexicon; P2 does not guess one."""
        text = csv_text(["Title", "URL handle", "Description"],
                        [["Serum", "serum", "<p>Clinically proven, best in class.</p>"]])
        npr = only(normalize_document(text, format=model.FORMAT_CSV))
        self.assertEqual(npr["claims"], [])
        self.assertIn("Clinically proven", npr["narrative"]["description_text"]["value"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
