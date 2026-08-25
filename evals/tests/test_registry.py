"""The check registry is a contract, so it is tested like one.

`registry.py` asserts its own invariants at import, which means a broken
registry cannot be loaded at all. These tests cover what an assertion cannot:
that the invariants are the *right* ones, that they actually fire, and -- the
part worth the most -- that no question the registry ships asserts a product
fact. A fabrication in a registry question is not one bad report; it is a
fabrication in every report that check ever emits.
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from audits import factlex                                   # noqa: E402
from audits.fabrication_audit import _EXAMPLE_FRAME_RE       # noqa: E402
from engine import registry, rubric_data as R, taxonomy_data as T  # noqa: E402
from engine import taxonomy_keys                             # noqa: E402


class TestPointTotals(unittest.TestCase):
    def test_earned_dimensions_sum_to_82(self):
        total = sum((Decimal(R.DIMENSION_MAX[d]) for d in R.EARNED_DIMENSIONS),
                    Decimal("0"))
        self.assertEqual(total, Decimal("82.0"))

    def test_every_earned_dimension_matches_its_checks(self):
        for dimension in R.EARNED_DIMENSIONS:
            if dimension == R.D2:
                continue
            total = sum((c.max_points for c in registry.ALL_CHECKS
                         if c.dimension == dimension), Decimal("0"))
            self.assertEqual(total, Decimal(R.DIMENSION_MAX[dimension]), dimension)

    def test_d2_is_22_for_every_category(self):
        for category in T.CATEGORIES:
            total = sum((c.max_points
                         for c in registry.d2_checks_for_category(category)),
                        Decimal("0"))
            self.assertLess(abs(total - Decimal("22.0")), Decimal("1e-20"), category)

    def test_d2_points_come_from_the_tier_pool(self):
        """taxonomy.md 4.1: even split within a tier, never a hidden weight."""
        for category in T.CATEGORIES:
            checks = registry.d2_checks_for_category(category)
            for tier, pool in T.TIER_POOLS.items():
                rows = [c for c in checks if c.tier == tier]
                self.assertTrue(rows, "%s tier %s" % (category, tier))
                expected = Decimal(pool) / Decimal(len(rows))
                for check in rows:
                    self.assertEqual(check.max_points, expected, check.check_id)

    def test_penalty_checks_carry_no_earned_points(self):
        for check in registry.ALL_CHECKS:
            if check.is_penalty:
                self.assertEqual(check.max_points, Decimal("0"), check.check_id)
                self.assertLessEqual(
                    check.penalty, Decimal(R.DIMENSION_MAX[check.dimension]),
                    check.check_id)
            else:
                self.assertEqual(check.penalty, Decimal("0"), check.check_id)


class TestIdentifiers(unittest.TestCase):
    def test_ids_are_unique_and_namespaced(self):
        seen = set()
        for check in registry.ALL_CHECKS:
            self.assertNotIn(check.check_id, seen)
            seen.add(check.check_id)
            self.assertIn(check.family, registry.FAMILIES, check.check_id)

    def test_d2_ids_encode_their_attribute_key(self):
        """The false-gap detector derives the key back out of the id."""
        from audits.fabrication_audit import _attribute_key_for
        for category in T.CATEGORIES:
            for check in registry.d2_checks_for_category(category):
                self.assertEqual(_attribute_key_for(check.check_id),
                                 check.attribute_key, check.check_id)

    def test_attribute_keys_match_the_taxonomy(self):
        for category in T.CATEGORIES:
            keys = tuple(a.key for a in T.attributes_for(category))
            self.assertEqual(sorted(keys),
                             sorted(taxonomy_keys.BY_CATEGORY[category]), category)


class TestGuardrails(unittest.TestCase):
    def test_low_confidence_never_punishes(self):
        """PRD 7.5 rule 2 -- the guardrail rubric.md 5.2 will not lower."""
        for check in registry.ALL_CHECKS:
            if check.confidence.recognized != "low":
                continue
            self.assertEqual(check.penalty, Decimal("0"), check.check_id)
            for status, severity in check.severity.items():
                self.assertIn(severity, ("minor", "info"),
                              "%s / %s" % (check.check_id, status))

    def test_a_low_confidence_check_stays_low_on_every_path(self):
        """Q-9 / D-020. `low` is about the subject matter, not the search.

        A check `rubric.md` fixes at `low` is one a reasonable reviewer could
        dispute -- whether a use case is specific enough, whether two
        attributes mean the same thing. Structural certainty about *where the
        tool looked* does not make that judgment less disputable, so the
        structural arm may not promote it to `high`. If it could, PRD 7.5
        rule 2's guardrail would detach from the check on exactly the path it
        most often takes.
        """
        for check in registry.ALL_CHECKS:
            if check.confidence.recognized == "low":
                self.assertEqual(check.confidence.structural, "low",
                                 check.check_id)

    def test_usecase_differentiation_is_low_on_both_arms(self):
        check = registry.get("USECASE.DIFFERENTIATION")
        self.assertEqual(check.confidence.recognized, "low")
        self.assertEqual(check.confidence.structural, "low")

    def test_a_structural_arm_never_exceeds_its_stated_confidence(self):
        order = {"low": 0, "medium": 1, "high": 2}
        for check in registry.ALL_CHECKS:
            if check.confidence.recognized != "low":
                continue
            self.assertLessEqual(order[check.confidence.structural],
                                 order[check.confidence.recognized],
                                 check.check_id)

    def test_partial_credit_is_a_registry_value(self):
        """rubric.md 3 carries it on the check record, so the registry owns it."""
        for check in registry.ALL_CHECKS:
            self.assertIsInstance(check.partial_credit, Decimal, check.check_id)
            self.assertGreaterEqual(check.partial_credit, Decimal("0"))
            self.assertLessEqual(check.partial_credit, Decimal("1"))

    def test_partial_credit_defaults_to_the_rubric_figure(self):
        self.assertEqual(registry.get("STRUCT.SEO_FIELDS_POPULATED").partial_credit,
                         Decimal(R.DEFAULT_PARTIAL_CREDIT))

    def test_no_check_computes_its_own_points(self):
        """Every earnable number traces to a registry field, not to check code."""
        import inspect
        from engine import checks as check_module
        source = inspect.getsource(check_module)
        for forbidden in ("max_points / 2", "max_points/2", "max_points * 0.5",
                          "Decimal(\"0.5\")"):
            self.assertNotIn(forbidden, source)

    def test_only_d6_may_emit_blocker(self):
        for check in registry.ALL_CHECKS:
            if check.dimension == R.D6:
                continue
            self.assertNotIn("blocker", check.severity.values(), check.check_id)

    def test_every_check_declares_where_it_looked_and_what_to_ask(self):
        for check in registry.ALL_CHECKS:
            self.assertTrue(check.checked_paths, check.check_id)
            self.assertTrue(check.question.strip(), check.check_id)

    def test_a_partial_condition_rules_out_structural_satisfaction(self):
        """A taxonomy row that can be PARTIAL cannot be decided by presence."""
        for category in T.CATEGORIES:
            for row in T.attributes_for(category):
                if not row.partial_if:
                    continue
                check = registry.get("%s.%s" % (T.FAMILY[category], row.key.upper()))
                self.assertFalse(check.structural_satisfaction, check.check_id)

    def test_the_structurally_decidable_attributes_are_declared(self):
        """The attributes a stated value alone satisfies, transcribed.

        These are exactly the `taxonomy.md` 5.x rows with an empty "PARTIAL if"
        cell and no conditional trigger: nothing about them needs a value to be
        read, only to be there. Pinning the list means widening it is a visible
        change to the specification's reading, not a quiet one.
        """
        expected = {
            "APPAREL.CLOSURE_AND_CONSTRUCTION", "APPAREL.COUNTRY_OF_ORIGIN",
            "BEAUTY.FORMULATION_FORMAT", "BEAUTY.SHELF_LIFE_OR_PAO",
            "BEAUTY.APPLICATION_TOOLS_INCLUDED",
            "ELEC.SOFTWARE_REQUIREMENTS", "ELEC.COLOR_FINISH",
            "HOME.ROOM_OR_PLACEMENT", "HOME.COLOR_FINISH",
            "HOME.PACKAGED_DIMENSIONS_WEIGHT",
            "SPORTS.DIMENSIONS_AND_WEIGHT", "SPORTS.INCLUDED_ACCESSORIES",
            "SPORTS.MAINTENANCE_REQUIREMENTS",
        }
        actual = set(c.check_id for c in registry.ALL_CHECKS
                     if c.dimension == R.D2 and c.structural_satisfaction)
        self.assertEqual(actual, expected)


class TestQuestionLint(unittest.TestCase):
    """PRD 7.6, applied to the registry rather than to the report.

    A question may name the information, the field, the unit, the format, or
    quote a supplied value. It may never introduce one. A registry string is
    supplied by nobody, so it must carry no fact token at all.
    """

    def _questions(self):
        return [(c.check_id, c.question) for c in registry.ALL_CHECKS]

    def test_no_question_contains_a_fact_token(self):
        for check_id, question in self._questions():
            tokens = factlex.extract(question)
            self.assertEqual(
                [t.text for t in tokens], [],
                "%s ships a fact token in its question: %r" % (check_id, question))

    def test_no_question_contains_an_example_frame(self):
        for check_id, question in self._questions():
            self.assertIsNone(
                _EXAMPLE_FRAME_RE.search(question),
                "%s uses an example frame: %r" % (check_id, question))

    def test_every_question_is_a_question(self):
        for check_id, question in self._questions():
            self.assertTrue(question.rstrip().endswith("?"), check_id)


class TestApplicability(unittest.TestCase):
    def test_category_selects_its_own_d2_set(self):
        for category in T.CATEGORIES:
            checks = registry.checks_for_category(category)
            families = set(c.family for c in checks if c.dimension == R.D2)
            self.assertEqual(families, {T.FAMILY[category]}, category)

    def test_uncategorized_removes_d2_entirely(self):
        """rubric.md 4/D2 and taxonomy.md 6 both put D2 at 0 with no category."""
        checks = registry.checks_for_category(T.UNCATEGORIZED)
        self.assertEqual([c for c in checks if c.dimension == R.D2], [])

    def test_non_d2_checks_apply_to_every_category(self):
        for category in list(T.CATEGORIES) + [T.UNCATEGORIZED]:
            checks = registry.checks_for_category(category)
            ids = set(c.check_id for c in checks)
            for check in registry.ALL_CHECKS:
                if check.dimension == R.D2:
                    continue
                self.assertIn(check.check_id, ids, category)


class TestSatisfactionIsThreeValued(unittest.TestCase):
    """PRE-4. A boolean cannot express "needs recognition we now have"."""

    def test_value_present_checks_need_no_predicate(self):
        for check in registry.ALL_CHECKS:
            if check.satisfies == T.VALUE_PRESENT:
                self.assertIs(check.satisfaction, registry.NO_PREDICATE,
                              check.check_id)

    def test_a_declared_predicate_with_no_evaluator_is_unimplemented(self):
        declared = [c for c in registry.ALL_CHECKS
                    if c.satisfies != T.VALUE_PRESENT]
        self.assertTrue(declared)
        for check in declared:
            if check.satisfies in registry.IMPLEMENTED_PREDICATES:
                continue
            self.assertIs(check.satisfaction, registry.UNIMPLEMENTED,
                          check.check_id)

    def test_a_check_with_no_evaluator_is_undecided_for_every_value(self):
        check = next(c for c in registry.ALL_CHECKS if not c.has_recognition
                     and c.satisfies != T.VALUE_PRESENT)
        for value in ("95% cotton", "", "varies"):
            self.assertIs(check.recognize(value), registry.UNDECIDED)

    def test_a_structural_check_recognizes_nothing(self):
        """A check that needs no recognition consults no predicate, and asking
        it returns the residue rather than a verdict nobody registered."""
        check = next(c for c in registry.ALL_CHECKS
                     if c.satisfies == T.VALUE_PRESENT)
        self.assertFalse(check.has_recognition)
        self.assertIs(check.recognize("anything"), registry.UNDECIDED)

    def test_the_satisfying_arm_is_tested_before_the_ambiguity_arm(self):
        """D-021's governing property, at the level of a single value: a value
        that satisfies may never be scored as merely ambiguous."""
        check = registry.get("APPAREL.MATERIAL_COMPOSITION")
        self.assertIs(check.recognize("60% cotton, 40% polyester"),
                      registry.SATISFIED)
        self.assertIs(check.recognize("cotton blend"), registry.AMBIGUOUS)
        self.assertIs(check.recognize("2-ply cotton"), registry.UNDECIDED)

    def test_structural_satisfaction_still_means_what_it_meant(self):
        """PRE-4 is behaviour-neutral: the boolean every check path reads is
        still exactly `satisfies == VALUE_PRESENT`."""
        for check in registry.ALL_CHECKS:
            self.assertEqual(check.structural_satisfaction,
                             check.satisfies == T.VALUE_PRESENT,
                             check.check_id)

    def test_an_implemented_evaluator_is_called_with_the_supplied_value(self):
        seen = []

        check = next(c for c in registry.ALL_CHECKS
                     if c.satisfies != T.VALUE_PRESENT
                     and c.satisfies not in registry.IMPLEMENTED_PREDICATES)
        original = dict(registry.IMPLEMENTED_PREDICATES)
        registry.IMPLEMENTED_PREDICATES[check.satisfies] = \
            lambda value: seen.append(value) or True
        try:
            self.assertIs(check.recognize("95% cotton"), registry.SATISFIED)
        finally:
            registry.IMPLEMENTED_PREDICATES.clear()
            registry.IMPLEMENTED_PREDICATES.update(original)
        self.assertEqual(seen, ["95% cotton"])
        self.assertIs(check.satisfaction, registry.UNIMPLEMENTED)


class TestImplementationMapInvariants(unittest.TestCase):
    """PRE-5. The invariants must be capable of failing, so each is tripped."""

    def _with_map(self, mapping):
        original = dict(registry.IMPLEMENTED_PREDICATES)
        registry.IMPLEMENTED_PREDICATES.clear()
        registry.IMPLEMENTED_PREDICATES.update(mapping)
        try:
            registry._invariants()
        finally:
            registry.IMPLEMENTED_PREDICATES.clear()
            registry.IMPLEMENTED_PREDICATES.update(original)

    def test_the_shipped_map_passes_its_own_invariants(self):
        self._with_map(dict(registry.IMPLEMENTED_PREDICATES))

    def test_every_implemented_predicate_is_declared_by_a_check(self):
        for predicate_id in registry.IMPLEMENTED_PREDICATES:
            self.assertIn(predicate_id, registry.RECOGNITION_PREDICATES)

    def test_an_orphan_predicate_fails_the_import_invariants(self):
        self.assertRaises(
            AssertionError, self._with_map,
            {"no_check_declares_this": lambda check, candidate: None})

    def test_a_non_callable_evaluator_fails_the_import_invariants(self):
        predicate_id = sorted(registry.RECOGNITION_PREDICATES)[0]
        self.assertRaises(AssertionError, self._with_map,
                          {predicate_id: "not callable"})

    def test_a_penalty_predicate_fails_the_import_invariants(self):
        """rubric.md 1.2: D6 and D7 are penalty exposure. A lexicon entry may
        never subtract points from a merchant, so the exclusion is structural
        rather than a habit in review."""
        penalty_predicates = set()
        for check in registry.ALL_CHECKS:
            if not check.is_penalty:
                continue
            for declared in (check.satisfies, check.partial_if,
                             check.conditional_trigger):
                if declared and declared != T.VALUE_PRESENT:
                    penalty_predicates.add(declared)
        self.assertTrue(penalty_predicates,
                        "no penalty check declares a predicate to exclude")
        for predicate_id in sorted(penalty_predicates):
            self.assertRaises(
                AssertionError, self._with_map,
                {predicate_id: lambda check, candidate: None})

    def test_no_shipped_predicate_belongs_to_a_penalty_check(self):
        for check in registry.ALL_CHECKS:
            if not check.is_penalty:
                continue
            for declared in (check.satisfies, check.partial_if,
                             check.conditional_trigger):
                self.assertNotIn(declared, registry.IMPLEMENTED_PREDICATES,
                                 check.check_id)


class TestVerdicts(unittest.TestCase):
    def test_a_verdict_is_not_a_rubric_status(self):
        """A predicate reports what it read; the check owns the arithmetic."""
        for verdict in registry.VERDICTS:
            self.assertNotIn(verdict, R.STATUSES)

    def test_the_three_verdicts_are_distinct_singletons(self):
        self.assertEqual(len(set(id(v) for v in registry.VERDICTS)), 3)



class TestRecognitionConfidenceCeiling(unittest.TestCase):
    """D-026. PRD 9.5 caps the recognition path at `medium`.

    The cap sits on the arm, not on the check: `rubric.md` 4's figure stays
    the check's stated confidence and the structural arm still reports it.
    """

    def test_no_check_can_report_high_by_recognition(self):
        for check in registry.ALL_CHECKS:
            self.assertIn(check.confidence.recognition_arm, ("medium", "low"),
                          check.check_id)

    def test_the_rubrics_own_figure_is_not_overridden(self):
        check = registry.get("TRUST.WARRANTY_OR_GUARANTEE")
        self.assertEqual(check.confidence.recognized, "high")
        self.assertEqual(check.confidence.structural, "high")
        self.assertEqual(check.confidence.recognition_arm, "medium")

    def test_a_medium_or_low_check_is_left_alone(self):
        for stated in ("medium", "low"):
            rule = registry.ConfidenceRule(stated)
            self.assertEqual(rule.recognition_arm, stated)

    def test_the_invariant_can_actually_fire(self):
        """A registry that could report `high` by recognition must not load."""
        original = registry.ConfidenceRule.RECOGNITION_CEILING
        registry.ConfidenceRule.RECOGNITION_CEILING = "high"
        try:
            self.assertEqual(
                registry.get("TRUST.WARRANTY_OR_GUARANTEE")
                .confidence.recognition_arm, "high")
            self.assertRaises(AssertionError, registry._invariants)
        finally:
            registry.ConfidenceRule.RECOGNITION_CEILING = original
        registry._invariants()


class TestTitleDistinguishingKeySet(unittest.TestCase):
    """D-024. The set is attribute *keys*, and it is closed."""

    def test_every_entry_is_a_taxonomy_attribute_key(self):
        from engine import lexicon, taxonomy_keys
        self.assertTrue(lexicon.IDENT_TITLE_DISTINGUISHING_KEYS)
        for key in lexicon.IDENT_TITLE_DISTINGUISHING_KEYS:
            self.assertTrue(taxonomy_keys.is_attribute_key(key), key)

    def test_no_entry_is_a_recognition_value(self):
        """A value here would be a product fact wearing a key's clothes."""
        from engine import lexicon
        self.assertEqual(
            lexicon.IDENT_TITLE_DISTINGUISHING_KEYS & lexicon.VALUE_SHAPED,
            frozenset())

    def test_the_count_kind_has_no_taxonomy_key_yet(self):
        """Recorded in D-024 so its absence is deliberate, not an oversight."""
        from engine import taxonomy_keys
        self.assertEqual(
            [k for k in taxonomy_keys.ATTRIBUTE_KEYS
             if "count" in k.split("_")], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
