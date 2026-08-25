"""What the check layer concludes, and -- more importantly -- what it refuses to.

Each test here maps to one line of the specification that is easy to violate by
accident and expensive to violate in production:

* absence never becomes negation, and never becomes a penalty (PRD 9.1, D-003);
* `FAIL` needs something present to be wrong (`rubric.md` 3.1);
* a contradiction is reported with both values and no winner (PRD 9.2);
* a non-inheritable attribute is not satisfied by a product-level value, and
  is not reported as absent either (PRD 9.7, PRD 8.3 rule 5);
* a question never supplies the value it is asking for (PRD 7.6).
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

from audits import factlex                                   # noqa: E402
from audits.pip_locator import resolve                       # noqa: E402
from engine import registry                                  # noqa: E402
from engine.runner import run_product                        # noqa: E402
from engine.sources import PipSource                         # noqa: E402

FIXTURES = os.path.join(REPO, "evals/fixtures")


def run(name, folder="checks"):
    path = os.path.join(FIXTURES, folder, "%s.pip.json" % name)
    with open(path) as handle:
        document = json.load(handle)
    npr = document["products"][0]
    return npr, run_product(npr, PipSource(document, file=path))


def finding_for(result, check_id):
    for finding in result.findings:
        if finding.check_id == check_id:
            return finding
    return None


class TestPresence(unittest.TestCase):
    def test_a_clearly_stated_attribute_passes(self):
        npr, result = run("checks-01-present-and-absent")
        finding = finding_for(result, "HOME.ROOM_OR_PLACEMENT")
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(finding.earned, registry.get("HOME.ROOM_OR_PLACEMENT").max_points)
        self.assertEqual(finding.confidence, "high")
        self.assertIsNone(finding.remediation)

    def test_a_product_level_attribute_is_scoped_to_the_product(self):
        npr, result = run("checks-01-present-and-absent")
        finding = finding_for(result, "HOME.ROOM_OR_PLACEMENT")
        self.assertEqual(finding.scope_level, "product")
        self.assertIsNone(finding.scope_ref)

    def test_evidence_reproduces_at_its_locator(self):
        """The locator is copied from the record, so it must resolve there."""
        npr, result = run("checks-01-present-and-absent")
        for finding in result.findings:
            for item in finding.evidence:
                if item.type == "absence":
                    continue
                resolution = resolve(npr, item.locator)
                self.assertTrue(resolution.ok,
                                "%s: %s" % (finding.check_id, item.locator))
                self.assertEqual(resolution.text, item.excerpt, finding.check_id)


class TestAbsence(unittest.TestCase):
    def test_a_genuinely_absent_attribute_is_unknown(self):
        npr, result = run("checks-01-present-and-absent")
        finding = finding_for(result, "HOME.CARE_AND_CLEANING")
        self.assertEqual(finding.status, "UNKNOWN")

    def test_absence_evidence_enumerates_checked_paths(self):
        npr, result = run("checks-01-present-and-absent")
        for finding in result.findings:
            if finding.status != "UNKNOWN":
                continue
            absences = [e for e in finding.evidence if e.type == "absence"]
            self.assertTrue(absences, finding.check_id)
            for item in absences:
                self.assertTrue(item.checked_paths, finding.check_id)

    def test_checked_paths_are_the_paths_the_check_declared(self):
        npr, result = run("checks-01-present-and-absent")
        finding = finding_for(result, "HOME.CARE_AND_CLEANING")
        item = finding.evidence[0]
        self.assertEqual(tuple(item.checked_paths),
                         registry.get("HOME.CARE_AND_CLEANING").checked_paths)

    def test_unknown_earns_nothing_and_costs_nothing(self):
        """D-003. The rule the whole product is built on."""
        for name in ("checks-01-present-and-absent", "checks-06-duplicate-identifier",
                     "checks-07-uncategorized"):
            npr, result = run(name)
            for finding in result.findings:
                if finding.status != "UNKNOWN":
                    continue
                self.assertEqual(float(finding.earned), 0.0, finding.check_id)
                self.assertEqual(float(finding.penalty), 0.0, finding.check_id)

    def test_no_finding_reaches_fail_on_an_absent_value(self):
        npr, result = run("checks-01-present-and-absent")
        self.assertEqual([f.check_id for f in result.findings if f.status == "FAIL"],
                         [])


class TestConflict(unittest.TestCase):
    def setUp(self):
        self.npr, self.result = run("checks-02-conflicting-values")

    def test_two_disagreeing_values_produce_one_d6_finding(self):
        finding = finding_for(self.result, "CONFLICT.CATEGORICAL")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.status, "FAIL")
        self.assertEqual(float(finding.penalty), 3.0)

    def test_both_locations_are_cited_separately(self):
        finding = finding_for(self.result, "CONFLICT.CATEGORICAL")
        locators = sorted(e.locator for e in finding.evidence)
        self.assertEqual(len(locators), 2)
        self.assertEqual(locators,
                         ["attributes[room_or_placement].value_raw",
                          "metafields[custom.room_or_placement].value"])

    def test_no_winner_is_chosen(self):
        """PRD 9.2. Both supplied values survive into the question, unranked."""
        finding = finding_for(self.result, "CONFLICT.CATEGORICAL")
        question = finding.remediation.question
        self.assertIn('"Kitchen"', question)
        self.assertIn('"Garage"', question)
        for word in ("correct value is", "should be", "we recommend", "instead of"):
            self.assertNotIn(word, question.lower())

    def test_the_conflicted_attribute_is_zeroed_as_well(self):
        """D-012: a contradiction costs the attribute and carries a penalty."""
        finding = finding_for(self.result, "HOME.ROOM_OR_PLACEMENT")
        self.assertEqual(finding.status, "FAIL")
        self.assertEqual(float(finding.earned), 0.0)
        self.assertEqual(float(finding.penalty), 0.0)

    def test_the_conflict_severity_is_not_blocker_for_a_plain_attribute(self):
        finding = finding_for(self.result, "CONFLICT.CATEGORICAL")
        self.assertEqual(finding.severity, "critical")

    def test_a_refinement_is_not_a_conflict(self):
        """"cotton" inside "100% cotton" is one value at two precisions."""
        from engine.checks import _conflict_kind
        self.assertIsNone(_conflict_kind(["cotton", "100% cotton"]))
        self.assertIsNone(_conflict_kind(["50 ml", "50 ml"]))
        self.assertEqual(_conflict_kind(["50 ml", "75 ml"]), "CONFLICT.NUMERIC")
        self.assertEqual(_conflict_kind(["Kitchen", "Garage"]),
                         "CONFLICT.CATEGORICAL")


class TestUnitRestatement(unittest.TestCase):
    """A value restated in another unit is not a contradiction.

    `rubric.md` 4/D6 rule 4 makes under-detection the required failure
    direction for the two mechanisms that subtract points, so a pair the tool
    cannot compare must produce nothing at all. Before this was fixed, a
    multi-token unit fell out of the numeric parser and reached the categorical
    branch, where "50 ml" and "1.7 fl oz" looked like two incompatible strings
    and cost the merchant three points.
    """

    def setUp(self):
        from engine.checks import _conflict_kind, _numeric
        self.kind = _conflict_kind
        self.numeric = _numeric

    def test_a_multi_token_unit_parses_as_a_unit(self):
        self.assertEqual(self.numeric("1.7 fl oz"), (Decimal("1.7"), "floz"))
        self.assertEqual(self.numeric("12 fl. oz."), (Decimal("12"), "floz"))
        self.assertEqual(self.numeric("50 ml"), (Decimal("50"), "ml"))
        self.assertEqual(self.numeric("50ml"), (Decimal("50"), "ml"))

    def test_the_same_unit_spelled_differently_is_the_same_unit(self):
        self.assertIsNone(self.kind(["1.7 fl oz", "1.7 floz"]))
        self.assertIsNone(self.kind(["1.7 fl oz", "1.7 fl. oz."]))

    def test_different_units_produce_no_conflict_at_all(self):
        for pair in (["50 ml", "1.7 fl oz"], ["1 m", "100 cm"],
                     ["500 g", "1.1 lb"], ["50 ml", "1.7 fl. oz."]):
            self.assertIsNone(self.kind(pair), pair)

    def test_no_conversion_is_performed_in_either_direction(self):
        """Different units are incomparable, not equal.

        The tool holds no table saying a millilitre relates to a fluid ounce,
        and a wrong conversion would be as much a fabrication as a wrong value.
        Two values in different units are simply not compared.
        """
        self.assertIsNone(self.kind(["50 ml", "999 fl oz"]))
        self.assertIsNone(self.kind(["1 m", "7 cm"]))

    def test_the_same_unit_still_conflicts(self):
        """The fix must not blunt detection where comparison is possible."""
        self.assertEqual(self.kind(["1.7 fl oz", "3.4 fl oz"]),
                         "CONFLICT.NUMERIC")
        self.assertEqual(self.kind(["50 ml", "75 ml"]), "CONFLICT.NUMERIC")
        self.assertIsNone(self.kind(["50 ml", "50.5 ml"]))

    def test_a_dimension_triple_is_not_read_as_a_number_with_a_unit(self):
        self.assertIsNone(self.numeric("2 x 3 cm"))
        self.assertIsNone(self.numeric("80 x 24 x 9 cm"))


class TestPresentAndWrong(unittest.TestCase):
    def test_duplicate_identifiers_fail_with_both_quoted(self):
        npr, result = run("checks-06-duplicate-identifier")
        finding = finding_for(result, "VARIANT.IDENTIFIER_UNIQUE")
        self.assertEqual(finding.status, "FAIL")
        self.assertEqual(len(finding.evidence), 2)
        self.assertEqual(finding.severity, "critical")
        self.assertEqual(float(finding.earned), 0.0)

    def test_a_placeholder_is_absent_for_its_attribute_and_wrong_for_structure(self):
        """PRD 9.4 and adv-03's whole reason for existing."""
        npr, result = run("adv-03-placeholder-values", folder="adversarial")
        self.assertEqual(finding_for(result, "IDENT.BRAND_PRESENT").status, "UNKNOWN")
        placeholder = finding_for(result, "STRUCT.NO_PLACEHOLDER_VALUES")
        self.assertEqual(placeholder.status, "FAIL")
        self.assertTrue(len(placeholder.evidence) >= 2)

    def test_the_quoted_placeholder_travels_with_the_unknown(self):
        npr, result = run("adv-03-placeholder-values", folder="adversarial")
        finding = finding_for(result, "IDENT.BRAND_PRESENT")
        excerpts = [e.excerpt for e in finding.evidence if e.excerpt]
        self.assertIn("TBD", excerpts)


class TestScopeAndInheritance(unittest.TestCase):
    def test_a_variant_scope_attribute_covered_everywhere_passes(self):
        npr, result = run("checks-03-variant-scope-covered")
        finding = finding_for(result, "HOME.COLOR_FINISH")
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(len(finding.evidence), 2)

    def test_partial_coverage_names_the_uncovered_variant(self):
        npr, result = run("checks-05-variant-partial")
        finding = finding_for(result, "HOME.COLOR_FINISH")
        self.assertEqual(finding.status, "PARTIAL")
        notes = " ".join(e.note or "" for e in finding.evidence)
        self.assertIn("sku:LG-TRAY-S", notes)
        self.assertNotIn("some variants", notes.lower())
        self.assertEqual(float(finding.earned),
                         float(registry.get("HOME.COLOR_FINISH").max_points) / 2)

    def test_a_non_inheritable_attribute_is_not_satisfied_at_product_scope(self):
        npr, result = run("checks-04-non-inheritable")
        finding = finding_for(result, "HOME.COLOR_FINISH")
        self.assertEqual(finding.status, "PARTIAL")

    def test_a_product_scope_value_earns_nothing_for_a_variant_requirement(self):
        """D-018. `covered / total` is 0 / N, so the arithmetic gives zero.

        Half credit here would pay for per-variant data the record does not
        hold -- the exact appearance of coverage that `taxonomy.md` 4.3 marks
        these attributes non-inheritable to prevent.
        """
        npr, result = run("checks-04-non-inheritable")
        finding = finding_for(result, "HOME.COLOR_FINISH")
        self.assertEqual(float(finding.earned), 0.0)
        self.assertEqual(float(finding.penalty), 0.0)

    def test_a_non_inheritable_attribute_is_not_reported_as_absent_either(self):
        """PRD 8.3 rule 5: a supplied value must never become a claimed gap."""
        npr, result = run("checks-04-non-inheritable")
        finding = finding_for(result, "HOME.COLOR_FINISH")
        self.assertNotEqual(finding.status, "UNKNOWN")
        self.assertIn("Assorted", [e.excerpt for e in finding.evidence])

    def test_the_uncovered_variants_are_named_not_summarised(self):
        npr, result = run("checks-04-non-inheritable")
        finding = finding_for(result, "HOME.COLOR_FINISH")
        notes = " ".join(e.note or "" for e in finding.evidence)
        self.assertIn("sku:LG-BASKET-S", notes)
        self.assertIn("sku:LG-BASKET-L", notes)
        self.assertNotIn("some variants", notes.lower())


class TestApplicability(unittest.TestCase):
    def test_only_the_assigned_category_s_attributes_are_checked(self):
        npr, result = run("checks-01-present-and-absent")
        self.assertEqual(result.classification.assigned, "home")
        families = set(f.check_id.split(".")[0] for f in result.findings
                       if f.dimension == "D2_category_attributes")
        self.assertEqual(families, {"HOME"})

    def test_no_category_means_no_category_specific_check_runs(self):
        npr, result = run("checks-07-uncategorized")
        self.assertEqual(result.classification.assigned, "uncategorized")
        self.assertEqual([f for f in result.findings
                          if f.dimension == "D2_category_attributes"], [])
        self.assertIn("D2_category_attributes",
                      [d["check_id"] for d in result.ledger.deferred])

    def test_a_single_variant_removes_the_multi_variant_checks(self):
        npr, result = run("checks-01-present-and-absent")
        finding = finding_for(result, "VARIANT.DIFFERENTIATED")
        self.assertEqual(finding.status, "NOT_APPLICABLE")
        self.assertEqual(float(finding.max_points), 0.0)

    def test_not_applicable_is_never_used_for_missing_information(self):
        """PRD 10.3 names this conflation as the scoring failure to avoid."""
        for name in ("checks-01-present-and-absent", "checks-03-variant-scope-covered",
                     "checks-06-duplicate-identifier"):
            npr, result = run(name)
            for finding in result.findings:
                if finding.status != "NOT_APPLICABLE":
                    continue
                self.assertIn("structural trigger", finding.detail)


class TestRemediation(unittest.TestCase):
    def test_an_unknown_asks_a_question_and_supplies_no_value(self):
        npr, result = run("checks-01-present-and-absent")
        finding = finding_for(result, "HOME.CARE_AND_CLEANING")
        self.assertEqual(finding.remediation.type, "question")
        self.assertEqual(finding.remediation.question,
                         registry.get("HOME.CARE_AND_CLEANING").question)
        self.assertIn("Do not generate a value", finding.remediation.note)

    def test_no_question_introduces_a_fact_token_of_its_own(self):
        """A conflict question may quote the data; it may introduce nothing."""
        for name in ("checks-01-present-and-absent", "checks-02-conflicting-values",
                     "checks-05-variant-partial", "checks-06-duplicate-identifier"):
            npr, result = run(name)
            supplied = json.dumps(npr).lower()
            for finding in result.findings:
                if not finding.remediation:
                    continue
                for token in factlex.extract(finding.remediation.question):
                    self.assertIn(token.text.lower(), supplied,
                                  "%s: %r" % (finding.check_id, token.text))

    def test_a_passing_check_asks_for_nothing(self):
        npr, result = run("checks-03-variant-scope-covered")
        for finding in result.findings:
            if finding.status == "PASS":
                self.assertIsNone(finding.remediation, finding.check_id)


class TestProseDeferral(unittest.TestCase):
    """D-019. What the engine does when it cannot read the prose.

    The rule has two halves and both matter. It must not infer the fact, and
    it must not report the attribute as absent -- because a description that
    has not been read might well state it, and claiming a gap there would be a
    false negative of the kind PRD 8.3 rule 5 calls blocker-severity.
    """

    def setUp(self):
        self.npr, self.result = run("sparse-apparel-02", folder="sparse")

    def test_a_deferred_check_emits_no_finding_at_all(self):
        deferred = set(d["check_id"] for d in self.result.ledger.deferred)
        self.assertIn("APPAREL.CARE_INSTRUCTIONS", deferred)
        self.assertIsNone(finding_for(self.result, "APPAREL.CARE_INSTRUCTIONS"))

    def test_a_deferred_check_never_reports_the_attribute_as_absent(self):
        emitted = set(f.check_id for f in self.result.findings)
        for row in self.result.ledger.deferred:
            self.assertNotIn(row["check_id"], emitted, row["check_id"])

    def test_a_deferred_check_reaches_no_merchant_facing_output(self):
        deferred = set(d["check_id"] for d in self.result.ledger.deferred)
        product = self.result.as_dict()
        attributes = set(row["attribute"] for row in product["unknowns"])
        for check_id in deferred:
            if "." not in check_id:
                continue
            self.assertNotIn(check_id.split(".", 1)[1].lower(), attributes)

    def test_a_deferred_check_costs_the_product_nothing(self):
        for finding in self.result.findings:
            self.assertEqual(float(finding.penalty), 0.0, finding.check_id)

    def test_absence_is_still_decided_where_nothing_was_found(self):
        """Deferral is not a blanket. With no prose, UNKNOWN is still reached."""
        npr, result = run("sparse-apparel-01", folder="sparse")
        self.assertEqual(finding_for(result, "APPAREL.CARE_INSTRUCTIONS").status,
                         "UNKNOWN")


class TestConfidence(unittest.TestCase):
    def test_a_low_confidence_check_emits_low_not_high(self):
        """Q-9 / D-020, at the point where it reaches a report."""
        npr, result = run("sparse-apparel-01", folder="sparse")
        for check_id in ("USECASE.DIFFERENTIATION", "USECASE.COMPLEMENTARY_CONTEXT"):
            finding = finding_for(result, check_id)
            self.assertIsNotNone(finding, check_id)
            self.assertEqual(finding.confidence, "low", check_id)

    def test_a_low_confidence_finding_carries_no_penalty_and_stays_minor(self):
        """PRD 7.5 rule 2, enforced on emitted output and not only on the table."""
        for name, folder in (("sparse-apparel-01", "sparse"),
                             ("checks-02-conflicting-values", "checks")):
            npr, result = run(name, folder=folder)
            for finding in result.findings:
                if finding.confidence != "low":
                    continue
                self.assertEqual(float(finding.penalty), 0.0, finding.check_id)
                self.assertIn(finding.severity, ("minor", "info"),
                              finding.check_id)

    def test_a_structural_absence_on_a_medium_check_is_still_high(self):
        """The honest report double uses `high` on a D2 absence; so do we."""
        npr, result = run("sparse-apparel-01", folder="sparse")
        finding = finding_for(result, "APPAREL.MATERIAL_COMPOSITION")
        self.assertEqual(finding.confidence, "high")

    def test_confidence_comes_from_the_registry_not_the_run(self):
        npr, result = run("sparse-apparel-01", folder="sparse")
        for finding in result.findings:
            check = registry.get(finding.check_id)
            self.assertIn(finding.confidence,
                          (check.confidence.structural, check.confidence.recognized),
                          finding.check_id)


class TestDeterminism(unittest.TestCase):
    def test_the_same_input_produces_the_same_report_twice(self):
        first = run("checks-02-conflicting-values")[1].as_dict()
        second = run("checks-02-conflicting-values")[1].as_dict()
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
