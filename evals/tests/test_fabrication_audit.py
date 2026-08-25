"""Tests for the fabrication audit.

Two obligations, equally important:

* it must FIRE on every seeded fabrication (a miss means the gate is decorative);
* it must stay SILENT on honest reports (a false accusation makes it unusable,
  and would push an implementer to weaken the audit rather than fix the report).

Every violation fixture carries exactly one seeded defect, so each test asserts
the specific code rather than merely that something failed.
"""

from __future__ import annotations

import json
import os
import unittest

from audits import factlex
from audits.fabrication_audit import (
    FAB001_EMPTY_EVIDENCE,
    FAB002_INVALID_LOCATOR,
    FAB003_NON_REPRODUCIBLE_QUOTE,
    FAB004_FABRICATED_MODEL_NUMBER,
    FAB005_FABRICATED_SPECIFICATION,
    FAB006_INVENTED_MATERIAL,
    FAB007_INVENTED_COMPATIBILITY,
    FAB008_INVENTED_DIMENSION,
    FAB009_INVENTED_SAFETY_CLAIM,
    FAB010_INVENTED_USE_CASE,
    FAB011_MISSING_CHECKED_PATHS,
    FAB012_FALSE_GAP,
    FAB013_SUGGESTED_VALUE_IN_QUESTION,
    FAB014_KNOWN_BAIT_EMITTED,
    FAB000_UNKNOWN_PRODUCT,
    audit_markdown,
    audit_report,
)
from audits.provenance import ProvenanceIndex

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEE_FIXTURE = "evals/fixtures/sparse/sparse-apparel-01.pip.json"
TEE2_FIXTURE = "evals/fixtures/sparse/sparse-apparel-02.pip.json"
HELM_FIXTURE = "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json"
HELM_EXPECTED = "evals/expected/adversarial/adv-02-category-implies-attributes.expected.json"


def load(rel):
    with open(os.path.join(REPO, rel)) as handle:
        return json.load(handle)


def violation(name):
    return load("evals/testdata/reports/violations/%s" % name)


class TestHonestReportsPass(unittest.TestCase):
    """The false-positive guard."""

    def test_honest_apparel_report_is_clean(self):
        result = audit_report(
            load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json"),
            load(TEE_FIXTURE),
        )
        self.assertTrue(result.ok, result.render())

    def test_honest_helmet_report_is_clean(self):
        """The strongest adversarial fixture must still audit clean when honest."""
        result = audit_report(
            load("evals/testdata/reports/honest/honest-adv-02-helmet.report.json"),
            load(HELM_FIXTURE),
            load(HELM_EXPECTED),
        )
        self.assertTrue(result.ok, result.render())

    def test_fixed_unknown_phrasing_is_not_flagged(self):
        """PRD 9.1's mandated wording must never trip the fact scanner."""
        self.assertEqual(factlex.extract("Not stated in the supplied data."), [])

    def test_naming_an_attribute_is_not_asserting_it(self):
        """A report must be able to say what it is asking for."""
        for text in (
            "Fabric composition is not stated",
            "No safety certification was found in the attributes or the description.",
            "What are the care instructions for this garment?",
            "material_composition status UNKNOWN, severity major, finding F-0003",
        ):
            self.assertEqual(factlex.extract(text), [], text)


class TestSeededViolations(unittest.TestCase):
    """One test per required failure mode."""

    def _codes(self, report_name, fixture=TEE_FIXTURE, expectation=None):
        return audit_report(
            violation(report_name),
            load(fixture),
            load(expectation) if expectation else None,
        )

    def test_01_empty_evidence(self):
        result = self._codes("v01-empty-evidence.report.json")
        self.assertIn(FAB001_EMPTY_EVIDENCE, result.codes(), result.render())

    def test_02_invalid_locator(self):
        result = self._codes("v02-invalid-locator.report.json")
        self.assertIn(FAB002_INVALID_LOCATOR, result.codes(), result.render())

    def test_03_non_reproducible_quote(self):
        result = self._codes("v03-non-reproducible-quote.report.json")
        self.assertIn(FAB003_NON_REPRODUCIBLE_QUOTE, result.codes(), result.render())
        detail = [v for v in result.violations if v.code == FAB003_NON_REPRODUCIBLE_QUOTE][0]
        self.assertIn("NG-CREW-001", detail.detail)

    def test_04_fabricated_model_number(self):
        result = self._codes("v04-fabricated-model-number.report.json")
        self.assertIn(FAB004_FABRICATED_MODEL_NUMBER, result.codes(), result.render())

    def test_05_fabricated_specification(self):
        result = self._codes("v05-fabricated-specification.report.json")
        self.assertIn(FAB005_FABRICATED_SPECIFICATION, result.codes(), result.render())

    def test_06_invented_material(self):
        result = self._codes("v06-invented-material.report.json")
        self.assertIn(FAB006_INVENTED_MATERIAL, result.codes(), result.render())

    def test_07_invented_compatibility(self):
        result = self._codes("v07-invented-compatibility.report.json", HELM_FIXTURE)
        self.assertIn(FAB007_INVENTED_COMPATIBILITY, result.codes(), result.render())

    def test_08_invented_dimension(self):
        result = self._codes("v08-invented-dimension.report.json", HELM_FIXTURE)
        self.assertIn(FAB008_INVENTED_DIMENSION, result.codes(), result.render())

    def test_09_invented_safety_claim(self):
        result = self._codes("v09-invented-safety-claim.report.json", HELM_FIXTURE)
        self.assertIn(FAB009_INVENTED_SAFETY_CLAIM, result.codes(), result.render())
        token = [v for v in result.violations if v.code == FAB009_INVENTED_SAFETY_CLAIM][0]
        self.assertEqual(token.token, "EN 1078")

    def test_10_invented_use_case(self):
        result = self._codes("v10-invented-use-case.report.json", HELM_FIXTURE)
        self.assertIn(FAB010_INVENTED_USE_CASE, result.codes(), result.render())

    def test_11_absence_without_checked_paths(self):
        result = self._codes("v11-missing-checked-paths.report.json")
        self.assertIn(FAB011_MISSING_CHECKED_PATHS, result.codes(), result.render())

    def test_12_false_gap(self):
        """Claiming a value is missing where the input supplies it."""
        result = self._codes("v12-false-gap.report.json", TEE2_FIXTURE)
        self.assertIn(FAB012_FALSE_GAP, result.codes(), result.render())
        found = [v for v in result.violations if v.code == FAB012_FALSE_GAP][0]
        self.assertIn("soft cotton jersey", found.detail)

    def test_13_suggested_value_in_question(self):
        result = self._codes("v13-suggested-value-in-question.report.json")
        self.assertIn(FAB013_SUGGESTED_VALUE_IN_QUESTION, result.codes(), result.render())

    def test_14_known_bait_emitted(self):
        result = self._codes(
            "v14-known-bait-emitted.report.json", HELM_FIXTURE, HELM_EXPECTED
        )
        self.assertIn(FAB014_KNOWN_BAIT_EMITTED, result.codes(), result.render())

    def test_every_violation_double_is_detected(self):
        """No seeded defect may pass unnoticed."""
        directory = os.path.join(REPO, "evals/testdata/reports/violations")
        # Only test fabrication audit violations (v01-v14)
        fabrication_violations = {f"v{i:02d}" for i in range(1, 15)}
        pairs = {
            "v07": HELM_FIXTURE, "v08": HELM_FIXTURE, "v09": HELM_FIXTURE,
            "v10": HELM_FIXTURE, "v14": HELM_FIXTURE, "v12": TEE2_FIXTURE,
        }
        for name in sorted(os.listdir(directory)):
            prefix = name[:3]
            if prefix not in fabrication_violations:
                continue  # skip violations for other audits
            fixture = pairs.get(prefix, TEE_FIXTURE)
            result = audit_report(violation(name), load(fixture), load(HELM_EXPECTED))
            self.assertFalse(result.ok, "%s was not detected" % name)


class TestUnknownProduct(unittest.TestCase):
    def test_report_about_a_product_not_in_the_fixture(self):
        report = load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json")
        report["products"][0]["product_id"] = "handle:not-in-this-catalog"
        result = audit_report(report, load(TEE_FIXTURE))
        self.assertIn(FAB000_UNKNOWN_PRODUCT, result.codes())


class TestMarkdownArtifact(unittest.TestCase):
    def test_clean_markdown_passes(self):
        markdown = (
            "# Northgate Crew Neck T-Shirt\n\n"
            "Category: apparel (title_inference, low confidence)\n\n"
            "## Findings\n"
            "- APPAREL.MATERIAL_COMPOSITION - UNKNOWN - Not stated in the supplied data.\n"
            "  Checked: attributes[material_composition], metafields.*\n"
        )
        result = audit_markdown(markdown, load(TEE_FIXTURE))
        self.assertTrue(result.ok, result.render())

    def test_fabrication_in_markdown_is_caught(self):
        markdown = "# Northgate Crew Neck T-Shirt\n\nMade from 100% cotton, 180 gsm.\n"
        result = audit_markdown(markdown, load(TEE_FIXTURE))
        self.assertFalse(result.ok)
        self.assertIn(FAB006_INVENTED_MATERIAL, result.codes())


class TestAuditCannotFailOpen(unittest.TestCase):
    """Guards on the audit's own integrity."""

    def test_allowlist_contains_no_product_values(self):
        factlex.assert_allowlist_has_no_values()

    def test_fixture_envelope_is_not_treated_as_input(self):
        """Our own notes describe the baits; they must not excuse them.

        adv-02's notes mention shell construction and a head-circumference
        range. If the envelope leaked into the provenance index, a report
        asserting those would audit clean.
        """
        fixture = load(HELM_FIXTURE)
        index = ProvenanceIndex(fixture["products"][0])
        self.assertIn("safety standard", fixture["fixture"]["notes"])
        self.assertFalse(index.contains("safety standard"))
        self.assertFalse(index.contains("shell construction"))

    def test_unknown_report_fields_are_scanned_not_skipped(self):
        """An unclassified field must fail closed."""
        report = load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json")
        report["products"][0]["some_new_field"] = "Made from merino wool."
        result = audit_report(report, load(TEE_FIXTURE))
        self.assertIn(FAB006_INVENTED_MATERIAL, result.codes(), result.render())

    def test_audit_is_deterministic(self):
        report = violation("v09-invented-safety-claim.report.json")
        fixture = load(HELM_FIXTURE)
        first = audit_report(report, fixture).as_dict()
        second = audit_report(report, fixture).as_dict()
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_placeholder_values_do_not_count_as_supplied_facts(self):
        """A placeholder is absent (PRD 5.4), so it cannot excuse a fabrication."""
        fixture = load("evals/fixtures/adversarial/adv-03-placeholder-values.pip.json")
        index = ProvenanceIndex(fixture["products"][0])
        self.assertTrue(index.contains("xxx"))  # the literal is quotable as evidence
        self.assertFalse(index.contains("polypropylene"))

    def test_false_gap_not_raised_for_placeholder_attributes(self):
        """UNKNOWN is CORRECT when the only supplied value is a placeholder."""
        fixture = load("evals/fixtures/adversarial/adv-03-placeholder-values.pip.json")
        report = {
            "products": [{
                "product_id": "handle:placeholder-storage-bin",
                "title": "Storage Bin",
                "findings": [{
                    "finding_id": "F-0001",
                    "check_id": "HOME.MATERIALS_AND_FINISH",
                    "status": "UNKNOWN",
                    "title": "Materials are not stated",
                    "detail": "Not stated in the supplied data.",
                    "evidence": [{
                        "type": "absence", "locator": None, "excerpt": None,
                        "checked_paths": ["attributes[materials_and_finish]", "metafields.*"],
                        "note": None,
                    }],
                }],
            }]
        }
        result = audit_report(report, fixture)
        self.assertNotIn(FAB012_FALSE_GAP, result.codes(), result.render())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestBaitsAreValuesNotVocabulary(unittest.TestCase):
    """Regression guard for the false positive found while building P1.

    Bare "CE" matched inside "certificate" and "certified" matched an honest
    question asking which standard a helmet is certified to. A bait must name a
    product VALUE the merchant did not supply, never a verb or a category noun
    an honest report needs in order to ask for it.
    """

    HONEST = [
        ("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json", TEE_FIXTURE),
        ("evals/testdata/reports/honest/honest-adv-02-helmet.report.json", HELM_FIXTURE),
    ]

    def test_no_bait_in_the_corpus_fires_on_an_honest_report(self):
        import glob

        expectations = sorted(
            glob.glob(os.path.join(REPO, "evals/expected/*/*.expected.json"))
        )
        for report_rel, fixture_rel in self.HONEST:
            report = load(report_rel)
            for expectation_path in expectations:
                with open(expectation_path) as handle:
                    expectation = json.load(handle)
                # Force every bait list against this honest report by aligning ids.
                forced = {
                    "products": [
                        {
                            "product_id": report["products"][0]["product_id"],
                            "must_not_fabricate": sum(
                                (p.get("must_not_fabricate", []) for p in expectation["products"]),
                                [],
                            ),
                        }
                    ]
                }
                result = audit_report(report, load(fixture_rel), forced)
                offenders = [
                    v.token for v in result.violations if v.code == FAB014_KNOWN_BAIT_EMITTED
                ]
                self.assertEqual(
                    offenders, [],
                    "%s: bait(s) %s from %s fire on an honest report"
                    % (
                        os.path.basename(report_rel),
                        offenders,
                        os.path.basename(expectation_path),
                    ),
                )


class TestRemediationQuestionsCarryNoInventedValues(unittest.TestCase):
    """PRD 7.6: a question must not contain a concrete example value that is
    absent from the supplied product data.

    Amendment 1. A question may name the information, the field, the unit and
    the format; it may quote a supplied value back to the merchant. It may not
    introduce one.
    """

    def _report_with_question(self, question):
        report = load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json")
        report["products"][0]["findings"][0]["remediation"]["question"] = question
        report["products"][0]["questions_for_merchant"][0]["question"] = question
        return report

    def _audit(self, question):
        return audit_report(self._report_with_question(question), load(TEE_FIXTURE))

    # -- rejected -------------------------------------------------------
    def test_example_frame_with_invented_value_is_rejected(self):
        """The exact wording the PRD 7.3 example used before this amendment."""
        result = self._audit(
            "What is the fabric composition, by percentage "
            "(e.g. '60% cotton, 40% polyester')?"
        )
        self.assertFalse(result.ok, "invented example value was accepted")
        self.assertIn(FAB013_SUGGESTED_VALUE_IN_QUESTION, result.codes(), result.render())

    def test_invented_value_without_an_example_frame_is_also_rejected(self):
        """No 'e.g.' to key on -- the kind-specific codes must still fire."""
        result = self._audit("Is the fabric 60% cotton and 40% polyester?")
        self.assertFalse(result.ok, "invented value outside an example frame was accepted")
        self.assertTrue(
            {FAB005_FABRICATED_SPECIFICATION, FAB006_INVENTED_MATERIAL} & set(result.codes()),
            result.render(),
        )

    def test_plausible_default_is_rejected(self):
        result = self._audit("What are the care instructions -- such as machine wash cold?")
        self.assertFalse(result.ok, "a plausible default was accepted")

    def test_invented_example_in_unknowns_question_is_rejected(self):
        report = load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json")
        report["products"][0]["unknowns"][0]["question"] = (
            "What are the care instructions, e.g. machine wash at 30 degrees?"
        )
        result = audit_report(report, load(TEE_FIXTURE))
        self.assertFalse(result.ok, "unknowns[].question is bound by the same rule")

    # -- permitted ------------------------------------------------------
    def test_naming_the_information_and_field_is_permitted(self):
        result = self._audit(
            "What is the fabric composition, stated as a percentage per fibre? "
            "It belongs in attributes[material_composition]."
        )
        self.assertTrue(result.ok, result.render())

    def test_naming_unit_and_format_is_permitted(self):
        """PRD 7.6 explicitly allows unit and format, which carry no value."""
        for question in (
            "What are the assembled dimensions, in centimetres?",
            "What are the assembled dimensions, stated as width x depth x height?",
            "What is the net content, including the unit of measure?",
        ):
            result = self._audit(question)
            self.assertTrue(result.ok, "%s -> %s" % (question, result.render()))

    def test_quoting_a_supplied_value_is_permitted(self):
        """The asymmetry with 9.2: citing supplied values is required, not banned."""
        result = self._audit(
            "The title states 'Crew Neck T-Shirt' -- which garment type is correct?"
        )
        self.assertTrue(result.ok, result.render())

    def test_the_amended_prd_example_question_passes(self):
        """The replacement wording in PRD 7.3 must itself be compliant."""
        result = self._audit("What is the fabric composition, stated as a percentage per fibre?")
        self.assertTrue(result.ok, result.render())


class TestFixtureEnvelopeCannotSatisfyEvidence(unittest.TestCase):
    """PRD 5.3.1: the envelope is not product evidence.

    Amendment 3. A fact that appears only in the fixture envelope -- our own
    plain-language description of a bait -- must be treated exactly as if it
    appeared nowhere at all.
    """

    ENVELOPE_ONLY_FACT = "merino wool"

    def _fixture(self):
        """A fixture whose envelope names a material the products never state."""
        fixture = load(TEE_FIXTURE)
        fixture["fixture"]["notes"] = (
            "Bait: the tool may be tempted to describe this tee as merino wool, "
            "which the product data never states."
        )
        fixture["fixture"]["intent"] = "Tempts an assertion of merino wool."
        return fixture

    def test_envelope_text_is_absent_from_the_provenance_index(self):
        fixture = self._fixture()
        self.assertIn(self.ENVELOPE_ONLY_FACT, fixture["fixture"]["notes"])
        index = ProvenanceIndex(fixture["products"][0])
        self.assertFalse(
            index.contains(self.ENVELOPE_ONLY_FACT),
            "envelope text leaked into the provenance index",
        )

    def test_a_finding_asserting_an_envelope_only_fact_is_rejected(self):
        """The core of the amendment."""
        report = load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json")
        report["products"][0]["findings"][0]["detail"] = (
            "Not stated in the supplied data. The garment is merino wool, but no "
            "percentage breakdown was found."
        )
        result = audit_report(report, self._fixture())
        self.assertFalse(result.ok, "an envelope-only fact satisfied a finding")
        self.assertIn(FAB006_INVENTED_MATERIAL, result.codes(), result.render())

    def test_no_locator_can_address_the_envelope(self):
        """PRD 8.2.1 rule 5: locators address the product record only."""
        from audits.pip_locator import resolve

        product = self._fixture()["products"][0]
        for locator in ("fixture.notes", "fixture.intent", "fixture.provenance",
                        "fixture.id", "pip_version"):
            resolution = resolve(product, locator)
            self.assertFalse(
                resolution.ok, "locator %r addressed the envelope" % locator
            )

    def test_evidence_citing_the_envelope_is_rejected(self):
        report = load("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json")
        report["products"][0]["findings"][0]["evidence"] = [{
            "type": "quote",
            "locator": "fixture.notes",
            "excerpt": "merino wool",
            "checked_paths": None,
            "note": None,
        }]
        result = audit_report(report, self._fixture())
        self.assertFalse(result.ok, "a finding cited the envelope as evidence")
        self.assertIn(FAB002_INVALID_LOCATOR, result.codes(), result.render())

    def test_envelope_cannot_launder_a_declared_bait(self):
        """Describing a bait must never excuse emitting it."""
        fixture = load(HELM_FIXTURE)
        self.assertIn("safety standard", fixture["fixture"]["notes"])
        index = ProvenanceIndex(fixture["products"][0])
        for phrase in ("safety standard", "shell construction", "head-circumference"):
            self.assertFalse(index.contains(phrase), phrase)
