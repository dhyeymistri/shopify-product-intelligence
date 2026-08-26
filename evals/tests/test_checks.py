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

import glob
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
from engine import checks                                    # noqa: E402
from engine import facts, normalize                          # noqa: E402
from engine import lexicon, recognize, taxonomy_keys         # noqa: E402
from engine import registry                                  # noqa: E402
from engine import rubric_data as R                          # noqa: E402
from engine import taxonomy_data as T                        # noqa: E402
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

    def test_the_reason_names_the_predicate_that_could_not_decide(self):
        """PRE-6. D-019 asks for the residue to be *measured*, and a reason
        that does not name the predicate cannot be counted against one."""
        rows = [r for r in self.result.ledger.deferred
                if "recognition predicate" in r["reason"]]
        self.assertTrue(rows, "no predicate deferral on this fixture")
        for row in rows:
            check = registry.get(row["check_id"])
            self.assertIn(check.satisfies, row["reason"], row["check_id"])

    def test_unread_prose_is_not_recorded_as_an_abstaining_predicate(self):
        """A check with no structured value read nothing, so no predicate ran.
        Naming one there would misreport where the recall gap actually is."""
        rows = [r for r in self.result.ledger.deferred
                if r["check_id"] == "APPAREL.CARE_INSTRUCTIONS"]
        self.assertEqual(len(rows), 1)
        self.assertIn("Free text was found", rows[0]["reason"])
        self.assertNotIn("no evaluator", rows[0]["reason"])

    def test_no_evaluator_and_abstained_are_recorded_differently(self):
        """The two are different measurements: one is a coverage gap that
        writing an evaluator would close, the other is the residue proper."""
        check = registry.get("APPAREL.CARE_INSTRUCTIONS")
        ledger = _ReasonLedger()
        ctx = _ReasonContext(ledger)

        self.assertEqual(checks._defer_for_recognition(check, ctx), [])
        self.assertEqual(
            checks._defer_for_recognition(check, ctx, registry.UNDECIDED), [])

        missing, abstained = ledger.reasons
        self.assertNotEqual(missing, abstained)
        self.assertIn("no evaluator", missing)
        self.assertIn("could not decide", abstained)
        for reason in (missing, abstained):
            self.assertIn(check.satisfies, reason)

    def test_neither_reason_reaches_merchant_facing_output(self):
        """Which reason applies changes the ledger, never the report."""
        product = self.result.as_dict()
        self.assertNotIn("deferred", product)
        text = json.dumps(product)
        self.assertNotIn("no evaluator", text)
        self.assertNotIn("could not decide", text)


class _ReasonLedger(object):
    """Records deferral reasons and nothing else."""

    def __init__(self):
        self.reasons = []

    def defer(self, check_id, reason):
        self.reasons.append(reason)


class _ReasonContext(object):
    __slots__ = ("ledger",)

    def __init__(self, ledger):
        self.ledger = ledger


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


class TestScopeIsDecidedBeforeRecognition(unittest.TestCase):
    """D-018 must be reachable for attributes that declare a predicate.

    `taxonomy.md` 4.3 makes non-inheritability a property of the attribute, not
    of how readable its values happen to be. Deciding satisfaction first meant
    every non-inheritable attribute carrying a recognition predicate --
    `size_system`, `garment_measurements`, `net_content`, `color_shade`,
    `assembled_dimensions`, `user_fit_specification`, apparel `color_finish` --
    deferred on the supplied value and never reached the scope arithmetic at
    all. Coverage is 0 / N whatever the value turns out to say, so the two
    decisions are independent and the scope one comes first.
    """

    FIXTURE = "checks-08-non-inheritable-recognition"
    CHECK = "APPAREL.SIZE_SYSTEM"

    def test_the_check_declares_a_recognition_predicate(self):
        """Without this the fixture would be testing the D-018 path already covered."""
        check = registry.get(self.CHECK)
        self.assertFalse(check.structural_satisfaction)
        self.assertIn(check.satisfies, registry.RECOGNITION_PREDICATES)
        self.assertEqual(check.scope, "variant")
        self.assertIs(check.inheritable, False)

    def test_it_reaches_d018_instead_of_deferring(self):
        npr, result = run(self.FIXTURE)
        self.assertEqual(finding_for(result, self.CHECK).status, "PARTIAL")
        self.assertNotIn(self.CHECK, [d["check_id"] for d in result.ledger.deferred])

    def test_a_product_scope_value_earns_nothing_and_costs_nothing(self):
        npr, result = run(self.FIXTURE)
        finding = finding_for(result, self.CHECK)
        self.assertEqual(float(finding.earned), 0.0)
        self.assertEqual(float(finding.penalty), 0.0)

    def test_the_product_scope_value_is_quoted_never_counted_as_variant_evidence(self):
        npr, result = run(self.FIXTURE)
        finding = finding_for(result, self.CHECK)
        quoted = [e for e in finding.evidence if e.type == "field_value"]
        self.assertEqual([e.excerpt for e in quoted], ["US 10"])
        # One product-scope locator, and no evidence item addressing a variant.
        self.assertEqual(quoted[0].locator, "attributes[size_system].value_raw")
        for item in finding.evidence:
            self.assertNotIn("variants[", item.locator or "")

    def test_it_is_not_reported_as_absent(self):
        """PRD 8.3 rule 5: a supplied value must never become a claimed gap."""
        npr, result = run(self.FIXTURE)
        self.assertNotEqual(finding_for(result, self.CHECK).status, "UNKNOWN")

    def test_every_uncovered_variant_is_named(self):
        npr, result = run(self.FIXTURE)
        finding = finding_for(result, self.CHECK)
        notes = " ".join(e.note or "" for e in finding.evidence)
        self.assertIn("sku:HL-CREW-S", notes)
        self.assertIn("sku:HL-CREW-L", notes)
        self.assertNotIn("some variants", notes.lower())

    def test_no_finding_asserts_that_the_value_satisfies_the_predicate(self):
        """Reachability is not recognition. Nothing here may say `US 10` is a
        size standard -- only that it was supplied, and at the wrong scope."""
        npr, result = run(self.FIXTURE)
        finding = finding_for(result, self.CHECK)
        self.assertNotEqual(finding.status, "PASS")
        self.assertNotIn("size standard", (finding.detail or "").lower())


class TestStrictVariantCoverage(unittest.TestCase):
    """D-021, against real fixtures rather than a synthesized record.

    `coverage = satisfied_variants / total_variants`. A variant whose value is
    merely ambiguous does not count toward coverage, is not weighted as half of
    one, and is never reported as an empty field -- the value is there, and
    reporting it as a gap would be the false negative the fabrication audit
    catches as FAB012.
    """

    def test_every_variant_satisfying_covers_the_check(self):
        npr, result = run("rec-01-title-and-proportions", folder="recognition")
        check = registry.get("APPAREL.SIZE_SYSTEM")
        finding = finding_for(result, check.check_id)
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(finding.earned, check.max_points)
        for item in finding.evidence:
            self.assertIn("variants[", item.locator or "")

    def test_an_ambiguous_variant_is_not_counted_as_covered(self):
        npr, result = run("rec-04-mixed-variant-coverage", folder="recognition")
        check = registry.get("HOME.ASSEMBLED_DIMENSIONS")
        finding = finding_for(result, check.check_id)
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(finding.earned,
                         check.max_points * Decimal(1) / Decimal(2))

    def test_an_ambiguous_variant_is_quoted_and_never_reported_as_empty(self):
        npr, result = run("rec-04-mixed-variant-coverage", folder="recognition")
        finding = finding_for(result, "HOME.ASSEMBLED_DIMENSIONS")
        quoted = [e for e in finding.evidence if e.type == "field_value"]
        self.assertEqual(len(quoted), 2)
        for item in quoted:
            self.assertIn("variants[", item.locator or "")
            self.assertTrue(item.excerpt)
        self.assertEqual([e for e in finding.evidence if e.type == "absence"],
                         [])

    def test_less_information_never_earns_more_than_fuller_coverage(self):
        """The governing property D-021 was decided against."""
        full = finding_for(run("rec-01-title-and-proportions",
                               folder="recognition")[1], "APPAREL.SIZE_SYSTEM")
        mixed = finding_for(run("rec-04-mixed-variant-coverage",
                                folder="recognition")[1],
                            "HOME.ASSEMBLED_DIMENSIONS")
        self.assertEqual(full.earned, full.max_points)
        self.assertLess(mixed.earned, mixed.max_points)
        self.assertEqual(mixed.earned,
                         mixed.max_points * Decimal(1) / Decimal(2))

    def test_an_ambiguous_variant_is_not_weighted_as_partial_coverage(self):
        """The rejected alternative, asserted as an inequality: weighting would
        have paid `max x (1 + 0.5)/2` here."""
        finding = finding_for(run("rec-04-mixed-variant-coverage",
                                  folder="recognition")[1],
                              "HOME.ASSEMBLED_DIMENSIONS")
        weighted = finding.max_points * Decimal("1.5") / Decimal(2)
        self.assertLess(finding.earned, weighted)

    def test_one_unreadable_variant_silences_the_whole_check(self):
        """A verdict the predicate could not reach is not a verdict against the
        variant, so the check says nothing rather than counting it uncovered."""
        npr, result = run("rec-05-unreadable-variant-silences-the-check",
                          folder="recognition")
        self.assertIsNone(finding_for(result, "HOME.ASSEMBLED_DIMENSIONS"))
        rows = [d for d in result.ledger.deferred
                if d["check_id"] == "HOME.ASSEMBLED_DIMENSIONS"]
        self.assertEqual(len(rows), 1)
        self.assertIn("could not decide", rows[0]["reason"])

    def test_a_product_scope_value_still_earns_nothing(self):
        """D-018 is unchanged by D-021: a satisfying value at product scope
        covers no variant of a non-inheritable attribute."""
        npr, result = run("checks-08-non-inheritable-recognition")
        finding = finding_for(result, "APPAREL.SIZE_SYSTEM")
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(float(finding.earned), 0.0)



class _StubBuilder(object):
    """Evidence constructors without a source. `coverage` only files what it is
    handed; byte-verification is `EvidenceBuilder`'s job and is tested there."""

    class _Item(object):
        def __init__(self, type, locator=None, note=None):
            self.type, self.locator, self.note = type, locator, note
            self.excerpt = None

    def field_value(self, candidate, note=None):
        return self._Item("field_value", getattr(candidate, "src", None), note)

    def absence(self, checked_paths, note=None):
        return self._Item("absence", None, note)


class _StubCandidate(object):
    def __init__(self, ref):
        self.src = "variants[%s].attributes[k].value_raw" % ref
        self.scope, self.ref, self.value = "variant", ref, "v"


def _coverage(check, satisfied, ambiguous, empty):
    """Run the coverage arithmetic on a shaped set of verdicts."""
    return checks.coverage(
        check, _StubBuilder(),
        [_StubCandidate("s%d" % i) for i in range(satisfied)],
        ["e%d" % i for i in range(empty)],
        unresolved=[_StubCandidate("a%d" % i) for i in range(ambiguous)],
        recognized=True)


class TestCoverageArithmetic(unittest.TestCase):
    """D-021 and D-025, tested as arithmetic rather than through a fixture.

    The fixtures prove the wiring; this proves the rule holds at every shape,
    including the ones no fixture happens to carry.
    """

    CHECK = "HOME.ASSEMBLED_DIMENSIONS"

    def setUp(self):
        self.check = registry.get(self.CHECK)
        self.max = self.check.max_points
        self.floor = self.max * self.check.partial_credit

    def test_all_satisfying_earns_the_maximum(self):
        finding = _coverage(self.check, 3, 0, 0)
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(finding.earned, self.max)

    def test_ambiguous_variants_do_not_enter_the_numerator(self):
        """D-021: strict coverage. The weighted reading was rejected."""
        finding = _coverage(self.check, 2, 1, 0)
        self.assertEqual(finding.earned, self.max * Decimal(2) / Decimal(3))
        weighted = self.max * Decimal("2.5") / Decimal(3)
        self.assertLess(finding.earned, weighted)

    def test_uniformly_ambiguous_earns_the_ambiguity_credit(self):
        """D-025: `rubric.md` 3.1's first PARTIAL clause applies when every
        variant carries a value, and it is a floor under the coverage clause."""
        finding = _coverage(self.check, 0, 3, 0)
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(finding.earned, self.floor)

    def test_the_floor_never_lowers_a_better_coverage(self):
        finding = _coverage(self.check, 2, 1, 0)
        self.assertGreater(finding.earned, self.floor)

    def test_the_floor_does_not_apply_when_a_variant_is_empty(self):
        """Something was found nowhere for that variant, so `rubric.md` 3.1's
        ambiguity clause does not describe the record. Strict coverage stands."""
        finding = _coverage(self.check, 0, 2, 1)
        self.assertEqual(finding.earned, Decimal(0))
        self.assertLess(finding.earned, self.floor)

    def test_less_information_never_earns_more_at_any_shape(self):
        """D-021's governing property, swept rather than sampled.

        Adding a satisfying value in place of an ambiguous one may never lower
        the earned figure, at any variant count.
        """
        for total in range(1, 6):
            earned = [_coverage(self.check, sat, total - sat, 0).earned
                      for sat in range(total + 1)]
            for lower, higher in zip(earned, earned[1:]):
                self.assertLessEqual(lower, higher,
                                     "total=%d: %s" % (total, earned))

    def test_the_naive_reading_would_have_inverted(self):
        """Why D-025 is a floor and not `max x partial_credit` for the uniform
        case alone: with three variants that reading pays 0.5 for nothing
        satisfying and 0.333 for one, which is the inversion D-021 forbids."""
        strict_one_of_three = self.max * Decimal(1) / Decimal(3)
        self.assertLess(strict_one_of_three, self.floor)
        self.assertEqual(_coverage(self.check, 1, 2, 0).earned, self.floor)


class TestTitleDistinguishingIsClosed(unittest.TestCase):
    """D-024. `rubric.md` 4/D1's parenthesis is a closed list."""

    CHECK = "IDENT.TITLE_DISTINGUISHING"

    def test_it_passes_on_one_of_the_five_kinds(self):
        npr, result = run("rec-01-title-and-proportions", folder="recognition")
        finding = finding_for(result, self.CHECK)
        self.assertEqual(finding.status, "PASS")
        locators = [e.locator for e in finding.evidence]
        self.assertIn("attributes[material_composition].value_raw", locators)

    def test_it_does_not_pass_on_an_attribute_outside_the_five_kinds(self):
        """`rec-02`'s title repeats `intended_use_context`. A value cannot be
        both too vague to answer its own check and distinguishing enough for
        the title."""
        npr, result = run("rec-02-vague-phrases", folder="recognition")
        self.assertIsNone(finding_for(result, self.CHECK))
        self.assertIn(self.CHECK,
                      [d["check_id"] for d in result.ledger.deferred])
        vague = finding_for(result, "APPAREL.INTENDED_USE_CONTEXT")
        self.assertEqual(vague.status, "PARTIAL")

    def test_it_does_not_pass_on_package_contents(self):
        npr, result = run("rec-06-durations-and-contents", folder="recognition")
        self.assertIsNone(finding_for(result, self.CHECK))

    def test_the_key_set_holds_only_the_five_kinds(self):
        for key in lexicon.IDENT_TITLE_DISTINGUISHING_KEYS:
            self.assertTrue(taxonomy_keys.is_attribute_key(key), key)
        for excluded in ("intended_use_context", "in_the_box", "color_finish",
                         "care_instructions", "sustainability_credentials",
                         "garment_measurements", "user_fit_specification"):
            self.assertNotIn(excluded, lexicon.IDENT_TITLE_DISTINGUISHING_KEYS)


class TestRecognitionConfidenceIsCapped(unittest.TestCase):
    """D-026. PRD 9.5: an inference-derived finding never reports `high`."""

    def test_a_recognised_pass_on_a_high_check_reports_medium(self):
        npr, result = run("rec-06-durations-and-contents", folder="recognition")
        finding = finding_for(result, "TRUST.WARRANTY_OR_GUARANTEE")
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(finding.confidence_arm, "recognized")
        self.assertEqual(finding.confidence, "medium")
        self.assertEqual(registry.get("TRUST.WARRANTY_OR_GUARANTEE")
                         .confidence.recognized, "high")

    def test_the_structural_path_of_the_same_check_still_reports_high(self):
        """`rubric.md` 4/D5's figure is not overridden -- only the recognition
        path is capped."""
        npr, result = run("sparse-apparel-01", folder="sparse")
        finding = finding_for(result, "TRUST.WARRANTY_OR_GUARANTEE")
        self.assertEqual(finding.status, "UNKNOWN")
        self.assertEqual(finding.confidence, "high")

    def test_no_recognised_finding_anywhere_reports_high(self):
        for name, folder in (("rec-01-title-and-proportions", "recognition"),
                             ("rec-06-durations-and-contents", "recognition"),
                             ("rec-07-shade-codes-and-quantities", "recognition")):
            npr, result = run(name, folder=folder)
            for finding in result.findings:
                if finding.confidence_arm == "recognized":
                    self.assertIn(finding.confidence, ("medium", "low"),
                                  "%s / %s" % (name, finding.check_id))

    def test_the_determination_is_serialized(self):
        npr, result = run("rec-06-durations-and-contents", folder="recognition")
        product = result.as_dict()
        arms = set(f["determination"] for f in product["findings"])
        self.assertEqual(arms, {"structural", "recognized"})


class TestUnnamedEcoClaimIsDeferred(unittest.TestCase):
    """D-027. The awarding half may not ship without the subtracting half."""

    CHECK = "APPAREL.SUSTAINABILITY_CREDENTIALS"

    def test_the_vague_value_earns_nothing_and_emits_nothing(self):
        npr, result = run("rec-02-vague-phrases", folder="recognition")
        self.assertIsNone(finding_for(result, self.CHECK))
        self.assertIn(self.CHECK,
                      [d["check_id"] for d in result.ledger.deferred])

    def test_the_predicate_exists_but_is_not_registered(self):
        """It stays in the codebase so the pair can ship together."""
        self.assertTrue(recognize.unnamed_eco_claim("Eco-friendly"))
        self.assertFalse(recognize.unnamed_eco_claim("GOTS certified organic"))
        self.assertNotIn("unnamed_eco_claim", registry.IMPLEMENTED_PREDICATES)
        self.assertNotIn("unnamed_eco_claim", registry.IMPLEMENTED_RELATIONS)

    def test_the_check_is_still_declared_and_still_reaches_absence(self):
        npr, result = run("sparse-apparel-01", folder="sparse")
        self.assertEqual(finding_for(result, self.CHECK).status, "UNKNOWN")


class TestRecordedPredicateSemantics(unittest.TestCase):
    """D-028. Two rules that decide what a check earns, pinned so they cannot
    drift back into being implementation details."""

    def test_in_the_box_has_no_deferral_path(self):
        check = registry.get("ELEC.IN_THE_BOX")
        for value in ("charger, cable, manual", "accessories included",
                      "a; b", "one item"):
            self.assertIsNot(check.recognize(value), registry.UNDECIDED, value)

    def test_a_single_item_box_can_only_reach_partial(self):
        """The consequence, stated: the tool cannot tell a complete one-item
        box from an unenumerated summary, and resolves it against the merchant."""
        check = registry.get("ELEC.IN_THE_BOX")
        self.assertIs(check.recognize("Wall bracket"), registry.AMBIGUOUS)
        self.assertIs(check.recognize("accessories included"),
                      registry.AMBIGUOUS)

    def test_the_strongest_verdict_across_candidates_decides(self):
        check = registry.get("APPAREL.MATERIAL_COMPOSITION")
        vague, exact = _StubCandidate("a"), _StubCandidate("b")
        vague.value, exact.value = "cotton blend", "60% cotton, 40% polyester"
        verdict, chosen = checks._best_verdict(check, [vague, exact])
        self.assertIs(verdict, registry.SATISFIED)
        self.assertIs(chosen, exact)

    def test_a_check_with_no_evaluator_reports_no_verdict_at_all(self):
        check = registry.get("APPAREL.SUSTAINABILITY_CREDENTIALS")
        candidate = _StubCandidate("a")
        candidate.value = "Eco-friendly"
        self.assertEqual(checks._best_verdict(check, [candidate]), (None, None))


class TestPlaceholderInDescription(unittest.TestCase):
    """adv-03's remaining gap: a placeholder hidden behind a declared path.

    `STRUCT.NO_PLACEHOLDER_VALUES` declares `narrative.description_text` and
    could not see a placeholder there, because every prose path was routed away
    from the bucket its evidence is drawn from. Separately, `<p>N/A</p>` was not
    recognized as a placeholder at all, so a description that states nothing
    counted as prose nobody had read -- which suppressed the `UNKNOWN` that
    `IDENT.DESCRIPTION_SUBSTANCE` owes the merchant.
    """

    def test_the_structure_check_quotes_the_description_placeholder(self):
        npr, result = run("adv-03-placeholder-values", folder="adversarial")
        finding = finding_for(result, "STRUCT.NO_PLACEHOLDER_VALUES")
        self.assertEqual(finding.status, "FAIL")
        located = dict((e.locator, e.excerpt) for e in finding.evidence)
        self.assertEqual(located.get("narrative.description_text"), "N/A")

    def test_a_placeholder_only_description_is_unknown_not_deferred(self):
        npr, result = run("adv-03-placeholder-values", folder="adversarial")
        finding = finding_for(result, "IDENT.DESCRIPTION_SUBSTANCE")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.status, "UNKNOWN")
        self.assertEqual(float(finding.earned), 0.0)
        self.assertEqual(float(finding.penalty), 0.0)
        self.assertNotIn("IDENT.DESCRIPTION_SUBSTANCE",
                         [d["check_id"] for d in result.ledger.deferred])

    def test_the_placeholder_is_quoted_beside_the_absence_never_read_as_a_fact(self):
        npr, result = run("adv-03-placeholder-values", folder="adversarial")
        finding = finding_for(result, "IDENT.DESCRIPTION_SUBSTANCE")
        types = set(e.type for e in finding.evidence)
        self.assertIn("absence", types)
        self.assertIn("N/A", [e.excerpt for e in finding.evidence])

    def test_markup_around_a_placeholder_does_not_hide_it(self):
        from engine.facts import Candidate
        raw = Candidate("<p>N/A</p>", "narrative.description_html",
                        "merchant_prose", "narrative.description_html")
        self.assertFalse(raw.is_placeholder)     # the value alone is not one
        extracted = Candidate("<p>N/A</p>", "narrative.description_html",
                              "merchant_prose", "narrative.description_html",
                              text="N/A")
        self.assertTrue(extracted.is_placeholder)
        # The quote is still the markup: extraction moved the judgment, not
        # the excerpt (PRD 5.4, PRD 8.3 rule 4).
        self.assertEqual(extracted.value, "<p>N/A</p>")

    def test_real_prose_is_still_unread_prose(self):
        """D-019 is untouched: only placeholders left the prose bucket."""
        from engine import facts
        npr, _ = run("checks-01-present-and-absent")
        npr = json.loads(json.dumps(npr))
        npr["narrative"]["description_html"] = {
            "value": "<p>Solid oak, oiled.</p>", "src": "narrative.description_html"}
        npr["narrative"]["description_text"] = {
            "value": "Solid oak, oiled.", "src": "narrative.description_text"}
        gathered = facts.gather(npr, registry.get("IDENT.DESCRIPTION_SUBSTANCE"))
        self.assertTrue(gathered.unrecognized_prose)
        self.assertFalse(gathered.placeholders)


# ---------------------------------------------------------------------------
# Slice D -- structural coverage over taxonomy data (D-029, D-030, D-031).
# ---------------------------------------------------------------------------
class TestVariantCoverageCountsPresenceNotSatisfaction(unittest.TestCase):
    """D-030. `rubric.md` 4/D3 says *present*, and that word governs."""

    def setUp(self):
        self.check = registry.get("VARIANT.ATTRIBUTE_COVERAGE")

    def test_the_required_key_set_is_the_categorys_own_taxonomy_set(self):
        """Not the Common Core, which is audited in D1, D5 and D8 (D-030)."""
        self.assertEqual(T.variant_scope_keys("home"),
                         ("assembled_dimensions", "color_finish"))
        for category in T.CATEGORIES:
            keys = T.variant_scope_keys(category)
            self.assertTrue(keys, category)
            self.assertNotIn("product_identifier", keys)
            self.assertNotIn("price", keys)

    def test_every_key_present_on_every_variant_earns_the_maximum(self):
        _npr, result = run("rec-09-variant-scope-fully-covered", "recognition")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(finding.earned, self.check.max_points)

    def test_the_predicate_of_each_attribute_is_never_consulted(self):
        """The load-bearing half of D-030.

        `rec-09` states the *same* `assembled_dimensions` on both variants and
        a bare colour name on each. Whether either satisfies its own D2 check
        is a different question, asked by a different check; this one reaches
        `PASS` on presence regardless of what those checks conclude.
        """
        _npr, result = run("rec-09-variant-scope-fully-covered", "recognition")
        coverage = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(coverage.status, "PASS")
        self.assertEqual(coverage.confidence_arm, "structural",
                         "presence is not recognition; no value was read for "
                         "what it means")
        self.assertIs(self.check.satisfaction, registry.UNIMPLEMENTED,
                      "this check has no *value* predicate, and reporting one "
                      "would be the wrong kind of true")

    def test_a_variant_missing_one_key_is_not_covered(self):
        _npr, result = run("rec-10-variant-scope-partly-covered", "recognition")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(finding.earned,
                         self.check.max_points * Decimal(2) / Decimal(3))

    def test_the_uncovered_variant_and_its_missing_key_are_named(self):
        """PRD 9.7 / D-021 rule 4, and both names are structural."""
        _npr, result = run("rec-10-variant-scope-partly-covered", "recognition")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        notes = " ".join(e.note or "" for e in finding.evidence)
        self.assertIn("sku:R10-UMB", notes)
        self.assertIn("color_finish", notes)
        self.assertNotIn("some variants", notes.lower())

    def test_a_partly_covering_variant_is_quoted_never_reported_as_empty(self):
        """The variant that misses one key still states the other one."""
        _npr, result = run("rec-10-variant-scope-partly-covered", "recognition")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        quoted = set(e.locator for e in finding.evidence if e.locator)
        self.assertIn(
            "variants[sku:R10-UMB].attributes[assembled_dimensions].value_raw",
            quoted)

    def test_zero_coverage_over_partial_data_is_partial_not_unknown(self):
        """`rubric.md` 3.1 reserves UNKNOWN for "not found in any checked_paths".

        `checks-03` states `assembled_dimensions` on every variant and no
        `color_finish` on any, so no variant is covered and the check earns
        exactly 0.00 -- but something *is* there, and reporting a gap over it
        would be the false negative PRD 8.3 rule 5 calls blocker-severity.
        """
        _npr, result = run("checks-03-variant-scope-covered")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(float(finding.earned), 0.0)
        self.assertTrue([e for e in finding.evidence if e.type == "field_value"])

    def test_absence_is_reported_only_when_no_required_key_is_stated(self):
        """And the note says what was looked for, so the claim is checkable."""
        _npr, result = run("checks-04-non-inheritable")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(finding.status, "UNKNOWN")
        note = " ".join(e.note or "" for e in finding.evidence)
        for key in T.variant_scope_keys("home"):
            self.assertIn(key, note)

    def test_a_product_scope_value_is_outside_what_this_check_searched(self):
        """D-030's `checked_paths` paragraph, as a property of the registry."""
        self.assertEqual(self.check.checked_paths, ("variants[*].attributes",))


class TestEmptyRequirementRemovesTheCheck(unittest.TestCase):
    """D-029. `NOT_APPLICABLE`, and never because a value is missing."""

    def test_an_uncategorized_multi_variant_product_removes_the_check(self):
        _npr, result = run("rec-11-uncategorized-visual-option", "recognition")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(finding.status, "NOT_APPLICABLE")
        self.assertEqual(float(finding.max_points), 0.0,
                         "an N/A check leaves the denominator (rubric.md 3.1)")
        self.assertEqual(float(finding.earned), 0.0)

    def test_the_reason_names_the_absent_category_not_an_absent_value(self):
        _npr, result = run("rec-11-uncategorized-visual-option", "recognition")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertIn("No category is assigned", finding.detail)

    def test_the_single_variant_trigger_still_fires_and_is_stated_differently(self):
        """Both grounds are structural; the merchant is told which applies."""
        _npr, result = run("checks-07-uncategorized")
        finding = finding_for(result, "VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(finding.status, "NOT_APPLICABLE")
        self.assertIn("single variant", finding.detail)

    def test_the_check_declares_both_triggers(self):
        check = registry.get("VARIANT.ATTRIBUTE_COVERAGE")
        self.assertEqual(check.na_trigger,
                         (R.NA_SINGLE_VARIANT, R.NA_EMPTY_VARIANT_SCOPE_SET))

    def test_no_category_today_has_an_empty_requirement(self):
        """The other D-029 branch is unreachable, and is stated anyway so that
        a taxonomy edit cannot reach an unwritten rule."""
        for category in T.CATEGORIES:
            self.assertTrue(T.variant_scope_keys(category), category)


class TestVisualOptionTriggerIsClosed(unittest.TestCase):
    """D-031. The vocabulary is the whole risk surface, so it is pinned."""

    def test_the_vocabulary_is_exactly_the_rubrics_parenthesis_plus_colour(self):
        self.assertEqual(
            sorted(lexicon.VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES),
            ["color", "colour", "finish", "shade"])

    def test_tone_and_pattern_are_not_in_it(self):
        """The P3.2 plan proposed both; neither is in `rubric.md` (D-031)."""
        for name in ("tone", "pattern"):
            self.assertNotIn(name,
                             lexicon.VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES)

    def test_a_colour_option_with_media_on_every_variant_passes(self):
        _npr, result = run("rec-09-variant-scope-fully-covered", "recognition")
        finding = finding_for(result, "VARIANT.MEDIA_LINKED")
        self.assertEqual(finding.status, "PASS")
        self.assertEqual(finding.earned,
                         registry.get("VARIANT.MEDIA_LINKED").max_points)

    def test_an_orthographic_variant_of_a_listed_word_triggers_it(self):
        _npr, result = run("rec-10-variant-scope-partly-covered", "recognition")
        finding = finding_for(result, "VARIANT.MEDIA_LINKED")
        self.assertIsNotNone(finding, "`Colour` did not trigger the check")
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(finding.earned,
                         registry.get("VARIANT.MEDIA_LINKED").max_points
                         * Decimal(2) / Decimal(3))

    def test_the_unlinked_variant_is_named(self):
        _npr, result = run("rec-10-variant-scope-partly-covered", "recognition")
        finding = finding_for(result, "VARIANT.MEDIA_LINKED")
        notes = " ".join(e.note or "" for e in finding.evidence)
        self.assertIn("sku:R10-UMB", notes)

    def test_no_visual_option_defers_and_never_removes_the_check(self):
        """`taxonomy.md` 4.4: a trigger is structural, never assumed. A `Size`
        axis does not establish that the variants do *not* differ visually."""
        _npr, result = run("checks-04-non-inheritable")
        self.assertIsNone(finding_for(result, "VARIANT.MEDIA_LINKED"))
        deferred = dict((r["check_id"], r["reason"]) for r in result.ledger.deferred)
        self.assertIn("VARIANT.MEDIA_LINKED", deferred)
        self.assertIn("visual axis", deferred["VARIANT.MEDIA_LINKED"])

    def test_product_scope_media_earns_nothing_and_is_not_reported_as_absent(self):
        """D-031's last paragraph: D-018's shape, applied to media."""
        _npr, result = run("rec-11-uncategorized-visual-option", "recognition")
        finding = finding_for(result, "VARIANT.MEDIA_LINKED")
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(float(finding.earned), 0.0)
        quoted = [e for e in finding.evidence if e.type == "field_value"]
        self.assertTrue(quoted, "the supplied media item was not quoted")
        self.assertEqual(quoted[0].locator, "media[0]")

    def test_a_visual_option_with_no_media_anywhere_is_unknown(self):
        _npr, result = run("checks-03-variant-scope-covered")
        finding = finding_for(result, "VARIANT.MEDIA_LINKED")
        self.assertEqual(finding.status, "UNKNOWN")


class TestOptionNameVocabulariesAreGoverned(unittest.TestCase):
    """D-031 / D-022. One module holds every scoring vocabulary, or the
    invariant that no entry is a product value cannot be checked at all."""

    def test_the_reserved_names_moved_into_the_lexicon(self):
        self.assertFalse(hasattr(checks, "RESERVED_OPTION_NAMES"),
                         "a second, ungoverned option-name vocabulary is back "
                         "in checks.py")
        self.assertEqual(
            sorted(lexicon.VARIANT_OPTION_NAMES_RESERVED),
            ["default", "default title", "option 1", "option 2", "option 3",
             "title"])

    def test_the_move_was_behaviour_neutral(self):
        _npr, result = run("checks-01-present-and-absent")
        self.assertIsNotNone(finding_for(result, "VARIANT.OPTION_NAMES_MEANINGFUL"))

    def test_neither_option_vocabulary_is_value_shaped(self):
        """They are names the merchant supplied and findings must quote them,
        so they are not the leak surface `VALUE_SHAPED` exists to guard."""
        for name in (lexicon.VARIANT_OPTION_NAMES_RESERVED
                     | lexicon.VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES):
            self.assertNotIn(name, lexicon.VALUE_SHAPED)

    def test_both_are_still_held_to_the_normalization_invariant(self):
        for name in (lexicon.VARIANT_OPTION_NAMES_RESERVED
                     | lexicon.VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES):
            self.assertIn(name, lexicon.ALL_ENTRIES)
            self.assertEqual(name, lexicon.normalize(name))

    def test_the_lexicon_is_versioned_with_the_bumped_rubric(self):
        self.assertEqual(lexicon.LEXICON_VERSION, R.RUBRIC_VERSION)


class TestStructuralPredicatesAreRegistered(unittest.TestCase):
    """PRE-5 in the direction the registry alone cannot see.

    `registry.py` cannot import `checks.py`, so the assertion that a structural
    predicate is actually implemented by a dispatched handler lives here.
    """

    def test_every_structural_predicate_is_declared_by_a_check(self):
        self.assertTrue(registry.IMPLEMENTED_STRUCTURAL)
        for predicate_id in registry.IMPLEMENTED_STRUCTURAL:
            self.assertIn(predicate_id, registry.RECOGNITION_PREDICATES)

    def test_every_structural_predicate_has_a_dispatched_handler(self):
        for predicate_id in registry.IMPLEMENTED_STRUCTURAL:
            owners = [c for c in registry.ALL_CHECKS
                      if c.satisfies == predicate_id]
            self.assertTrue(owners, predicate_id)
            for check in owners:
                self.assertIn(check.check_id, checks.DISPATCH,
                              "%s claims %s is implemented, but the check falls "
                              "through to attribute_check"
                              % (check.check_id, predicate_id))

    def test_it_is_disjoint_from_the_other_two_registries(self):
        for predicate_id in registry.IMPLEMENTED_STRUCTURAL:
            self.assertNotIn(predicate_id, registry.IMPLEMENTED_PREDICATES)
            self.assertNotIn(predicate_id, registry.IMPLEMENTED_RELATIONS)


# ---------------------------------------------------------------------------
# D-032 -- a check may drop a finding, but never in silence.
# ---------------------------------------------------------------------------
class TestOptionNamesIsNeverSilent(unittest.TestCase):
    """The regression D-032 was written for, held against real engine output.

    `VARIANT.OPTION_NAMES_MEANINGFUL` emitted nothing at all on every Format C
    record carrying options: no finding, no deferral, no `run_error`. The cause
    was provenance -- the option locator addressed the element rather than the
    name, so `evidence.field_value` raised and `checks.check_option_names`
    returned `[]` at the swallow site. `rubric.md` 4/D3's rule for the check
    never changed and is not touched here; what these assertions pin is that
    the rule can still be *evidenced*.

    PRD 8.3 rule 1 is the authority: a finding with empty evidence is dropped
    **"and logged as a `run_error`"**. The drop was permitted. The silence was
    not.
    """

    CHECK = "VARIANT.OPTION_NAMES_MEANINGFUL"

    def _corpus(self):
        out = []
        for path in sorted(glob.glob(os.path.join(FIXTURES, "*/*.pip.json"))):
            with open(path) as handle:
                source_document = json.load(handle)
            source = PipSource(source_document, file=path)
            for npr in source_document["products"]:
                out.append((os.path.basename(path), npr, run_product(npr, source)))
        return out

    def test_every_product_carrying_options_emits_the_check(self):
        seen = 0
        for name, npr, result in self._corpus():
            if not (npr.get("options") or []):
                continue
            self.assertIsNotNone(
                result.status_of(self.CHECK),
                "%s: %s emitted no finding on a product with %d option(s). A "
                "check that cannot build evidence must say so, not vanish "
                "(PRD 8.3 rule 1)." % (name, self.CHECK, len(npr["options"])))
            seen += 1
        self.assertGreater(seen, 0, "no fixture carries an option")

    def test_it_is_never_silent_anywhere_in_the_corpus(self):
        """Silent means: no finding, no deferral, and no run error."""
        for name, npr, result in self._corpus():
            if result.status_of(self.CHECK) is not None:
                continue
            deferred = set(d["check_id"] for d in result.ledger.deferred)
            self.assertIn(self.CHECK, deferred,
                          "%s: %s produced neither a finding nor a deferral"
                          % (name, self.CHECK))

    def test_its_evidence_locator_addresses_the_option_name(self):
        """The finding must quote the name, at the name's own locator."""
        for name, npr, result in self._corpus():
            for finding in result.findings:
                if finding.check_id != self.CHECK:
                    continue
                names = [o.get("name") for o in npr.get("options") or []]
                for item in finding.evidence:
                    if item.locator is None:     # absence evidence on UNKNOWN
                        continue
                    self.assertTrue(item.locator.endswith(".name"),
                                    "%s: %r is not an option-name locator"
                                    % (name, item.locator))
                    self.assertIn(item.excerpt, names,
                                  "%s: excerpt %r is not one of this product's "
                                  "option names %r" % (name, item.excerpt, names))


# ---------------------------------------------------------------------------
# D-033 -- provenance for a variant's option value is copied, never composed.
# ---------------------------------------------------------------------------
class TestOptionValueProvenanceIsCopiedNotComposed(unittest.TestCase):
    """D-033, at the two call sites that used to build their own locators.

    `check_variant_differentiated` composed `variants[<vid>].option_values[
    <name>]` for its `PASS` evidence and `facts._variant_option_values`
    composed the same string for a candidate `src`. That form resolves under
    Format C and does not parse under Format A, so the check emitted nothing at
    all on every multi-variant CSV product -- no finding, no deferral, no run
    error. Neither call site knows the format; the normalizer does, so the
    locator is recorded there and copied here.

    `rubric.md` 4/D3 decides this check and nothing below asserts anything
    about what it decides -- only about what it is able to cite.
    """

    CHECK = "VARIANT.DIFFERENTIATED"

    def _multi_variant(self):
        """(label, npr, source, ProductResult) for every multi-variant product."""
        out = []
        paths = sorted(glob.glob(os.path.join(FIXTURES, "*/*.pip.json")))
        for path in paths:
            with open(path) as handle:
                document = json.load(handle)
            source = PipSource(document, file=path)
            for npr in document["products"]:
                if len(npr.get("variants") or []) > 1:
                    out.append((os.path.basename(path), npr, source,
                                run_product(npr, source)))
        for name in sorted(os.listdir(os.path.join(FIXTURES, "csv"))):
            if not name.endswith(".csv"):
                continue
            result = normalize.normalize_file(os.path.join(FIXTURES, "csv", name))
            for npr in result.products:
                if len(npr.get("variants") or []) > 1:
                    out.append((name, npr, result.source,
                                run_product(npr, result.source)))
        return out

    def test_both_formats_are_represented(self):
        """Otherwise this class could pass while testing one format."""
        labels = [n for n, _, _, _ in self._multi_variant()]
        self.assertTrue([n for n in labels if n.endswith(".csv")], labels)
        self.assertTrue([n for n in labels if n.endswith(".pip.json")], labels)

    def test_the_check_is_never_silent_on_a_multi_variant_product(self):
        for name, npr, _, result in self._multi_variant():
            if result.status_of(self.CHECK) is not None:
                continue
            deferred = set(d["check_id"] for d in result.ledger.deferred)
            self.assertIn(self.CHECK, deferred,
                          "%s: %s produced neither a finding nor a deferral "
                          "(PRD 8.3 rule 1)" % (name, self.CHECK))

    def test_its_evidence_locator_is_one_the_record_supplied(self):
        """Copied, not composed: every ref must appear in the NPR verbatim."""
        checked = 0
        for name, npr, _, result in self._multi_variant():
            for finding in result.findings:
                if finding.check_id != self.CHECK:
                    continue
                supplied = set()
                for variant in npr["variants"]:
                    for pair in (variant.get("option_values") or {}).values():
                        if isinstance(pair, dict) and pair.get("src"):
                            supplied.add(pair["src"])
                for item in finding.evidence:
                    if item.locator is None:
                        continue
                    self.assertIn(item.locator, supplied,
                                  "%s: %r was composed, not copied from the record"
                                  % (name, item.locator))
                    checked += 1
        self.assertGreater(checked, 0)

    def test_every_evidence_locator_resolves_in_its_own_format(self):
        for name, npr, source, result in self._multi_variant():
            for finding in result.findings:
                if finding.check_id != self.CHECK:
                    continue
                for item in finding.evidence:
                    if item.locator is None:
                        continue
                    resolution = source.resolve(item.locator, npr["product_id"])
                    self.assertTrue(resolution.ok,
                                    "%s: %r -> %s"
                                    % (name, item.locator, resolution.error))

    def test_facts_copies_the_supplied_locator_too(self):
        """`facts._variant_option_values` is the same defect one layer over."""
        checked = 0
        for name, npr, source, _ in self._multi_variant():
            check = registry.get(self.CHECK)
            for candidate in facts.gather(npr, check).stated:
                if candidate.npr_path and "option_values" not in candidate.npr_path:
                    continue
                self.assertTrue(candidate.src, "%s: candidate with no locator" % name)
                resolution = source.resolve(candidate.src, npr["product_id"])
                self.assertTrue(resolution.ok,
                                "%s: %r -> %s" % (name, candidate.src, resolution.error))
                self.assertEqual(resolution.text, candidate.value, name)
                checked += 1
        self.assertGreater(checked, 0)

    def test_a_pair_without_a_locator_defers_rather_than_vanishing(self):
        """The contract's failure arm (D-033), asserted at the check layer."""
        import copy
        name, npr, source, _ = self._multi_variant()[0]
        npr = copy.deepcopy(npr)
        first = npr["variants"][0]
        option = sorted(first["option_values"])[0]
        first["option_values"][option] = {"value":
                                          first["option_values"][option]["value"],
                                          "src": None}
        result = run_product(npr, source)
        self.assertIsNone(result.status_of(self.CHECK))
        deferred = dict((d["check_id"], d["reason"]) for d in result.ledger.deferred)
        self.assertIn(self.CHECK, deferred)
        self.assertIn("carries no locator", deferred[self.CHECK])
