"""The invariant recognition must not break, pinned before recognition exists.

P3.2 will implement deterministic recognition predicates. `decisions.md` D-019
fixes what a check does when it cannot read a value -- it says nothing -- and
the phase that starts reading values is exactly the phase that could quietly
turn that silence into an assertion. So the contract is written down first,
while there is a known-good state to pin it against:

> **Recognition may convert an existing deferral into `PASS` or `PARTIAL`.
> It may do nothing else.**

Concretely, implementing a predicate must never introduce:

* a `FAIL` -- `rubric.md` 3.1 reserves it for something present being wrong,
  and satisfaction answers a different question entirely;
* a penalty -- D6 and D7 are the only two mechanisms that subtract, and no
  satisfaction predicate routes to either (D-003);
* fabricated evidence -- every excerpt stays byte-reproducible at a locator
  that resolves (PRD 8.3 rule 4);
* an unsupported absence claim -- a value that was found may never be reported
  as a gap (PRD 8.3 rule 5, `FAB012`);
* product-level evidence counted as variant evidence -- `taxonomy.md` 4.3 and
  D-018 make a product-scope value cover zero variants of a non-inheritable
  attribute, whatever the value says.

Two of these -- fabricated evidence and unsupported absence -- are already
enforced against real engine output by `test_engine_audits.py`, which runs the
fabrication audit over every fixture. They are named here as part of the
contract and asserted there; this module does not re-implement them, and
nothing here relaxes them.

**These tests are not maintenance.** A diff in the pinned baseline is a
recognition predicate that has introduced absence, a defect or a penalty, and
the predicate is what is wrong.
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

from engine import normalize, registry                       # noqa: E402
from engine import rubric_data as R                          # noqa: E402
from engine.runner import run_result                         # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(REPO, "evals/fixtures/*/*.pip.json")))
BASELINE = os.path.join(REPO, "evals/expected/monotonicity_baseline.json")

#: The statuses a recognition predicate is allowed to produce. Anything else it
#: produces is a defect in the predicate, not a new baseline.
RECOGNITION_MAY_PRODUCE = frozenset(["PASS", "PARTIAL"])


def load(path):
    with open(path) as handle:
        return json.load(handle)


def audited():
    """(key, ProductResult) for every product in the corpus."""
    out = []
    for path in FIXTURES:
        result = normalize.normalize_file(path)
        for product in run_result(result):
            key = "%s::%s" % (os.path.basename(path).replace(".pip.json", ""),
                              product.product_id)
            out.append((key, product))
    return out


CORPUS = audited()


class TestPinnedBaseline(unittest.TestCase):
    """The three sets and the one number recognition must leave alone."""

    def setUp(self):
        self.baseline = load(BASELINE)["products"]

    def test_every_product_is_pinned(self):
        self.assertEqual(sorted(self.baseline), sorted(k for k, _ in CORPUS),
                         "a fixture was added or removed without pinning it")

    def test_the_unknown_set_is_unchanged(self):
        for key, product in CORPUS:
            actual = sorted(f.check_id for f in product.findings
                            if f.status == R.UNKNOWN)
            self.assertEqual(actual, self.baseline[key]["unknown"],
                             "%s: recognition may not add or remove an UNKNOWN. "
                             "A predicate that concludes absence where a value "
                             "was found is a false gap (PRD 8.3 rule 5)." % key)

    def test_the_fail_set_is_unchanged(self):
        for key, product in CORPUS:
            actual = sorted(f.check_id for f in product.findings
                            if f.status == R.FAIL)
            self.assertEqual(actual, self.baseline[key]["fail"],
                             "%s: recognition may not introduce a FAIL. "
                             "`rubric.md` 3.1 needs something present to be "
                             "wrong, which satisfaction does not decide." % key)

    def test_the_not_applicable_set_is_unchanged(self):
        for key, product in CORPUS:
            actual = sorted(f.check_id for f in product.findings
                            if f.status == R.NOT_APPLICABLE)
            self.assertEqual(actual, self.baseline[key]["not_applicable"],
                             "%s: recognition may not remove a check from the "
                             "denominator. A missing value is UNKNOWN, never "
                             "N/A (PRD 10.3)." % key)

    def test_the_penalty_total_is_unchanged(self):
        for key, product in CORPUS:
            actual = sum((f.penalty for f in product.findings), Decimal("0"))
            self.assertEqual(str(actual), self.baseline[key]["penalty_total"],
                             "%s: recognition may not subtract points." % key)


class TestPenaltiesStayWhereTheSpecPutsThem(unittest.TestCase):
    def test_only_a_penalty_dimension_check_ever_carries_a_penalty(self):
        for key, product in CORPUS:
            for finding in product.findings:
                if finding.penalty:
                    self.assertIn(finding.dimension, R.PENALTY_DIMENSIONS,
                                  "%s / %s" % (key, finding.check_id))

    def test_a_penalty_only_ever_accompanies_a_fail(self):
        for key, product in CORPUS:
            for finding in product.findings:
                if finding.penalty:
                    self.assertEqual(finding.status, R.FAIL,
                                     "%s / %s" % (key, finding.check_id))

    def test_unknown_costs_nothing_anywhere_in_the_corpus(self):
        """D-003, and it is not amendable by a rubric version bump."""
        for key, product in CORPUS:
            for finding in product.findings:
                if finding.status == R.UNKNOWN:
                    self.assertEqual(float(finding.penalty), 0.0)
                    self.assertEqual(float(finding.earned), 0.0)


class TestFailNeverRestsOnAbsence(unittest.TestCase):
    def test_every_fail_quotes_something_that_is_actually_there(self):
        """`rubric.md` 3.1's most important line, as an assertion over output.

        A `FAIL` supported only by absence evidence is absence dressed as a
        defect, which is the one thing the status boundary exists to prevent.
        """
        seen = 0
        for key, product in CORPUS:
            for finding in product.findings:
                if finding.status != R.FAIL:
                    continue
                seen += 1
                quoted = [e for e in finding.evidence if e.type != "absence"]
                self.assertTrue(quoted,
                                "%s / %s: FAIL with only absence evidence"
                                % (key, finding.check_id))
                for item in quoted:
                    self.assertTrue(item.excerpt,
                                    "%s / %s: FAIL evidence with no excerpt"
                                    % (key, finding.check_id))
        self.assertTrue(seen, "no FAIL in the corpus; this test proved nothing")


class TestProductEvidenceIsNeverVariantEvidence(unittest.TestCase):
    """D-018, as a property of every finding rather than of one fixture."""

    @staticmethod
    def non_inheritable_variant_checks():
        return [c for c in registry.ALL_CHECKS
                if c.scope == "variant" and c.inheritable is False]

    def test_the_rule_has_checks_to_apply_to(self):
        self.assertTrue(self.non_inheritable_variant_checks())

    def test_a_non_inheritable_check_earns_only_from_variant_locators(self):
        ids = set(c.check_id for c in self.non_inheritable_variant_checks())
        for key, product in CORPUS:
            for finding in product.findings:
                if finding.check_id not in ids or not finding.earned:
                    continue
                quoted = [e for e in finding.evidence if e.type == "field_value"]
                self.assertTrue(quoted, "%s / %s" % (key, finding.check_id))
                for item in quoted:
                    self.assertIn("variants[", item.locator or "",
                                  "%s / %s: earned points from a locator that "
                                  "does not address a variant. A product-scope "
                                  "value covers no variant of a non-inheritable "
                                  "attribute (taxonomy.md 4.3, D-018)."
                                  % (key, finding.check_id))

    def test_a_product_scope_value_at_variant_scope_earns_exactly_zero(self):
        """The D-018 finding shape: PARTIAL, zero earned, value quoted.

        `UNKNOWN` is excluded rather than overlooked. An `UNKNOWN` also quotes
        product-scope `field_value` evidence when a placeholder occupies the
        field (PRD 9.4 requires the literal to be shown), and that is a
        different and already-correct shape: nothing was stated, so there is no
        coverage question to get wrong. It earns zero by definition, which
        `TestPenaltiesStayWhereTheSpecPutsThem` asserts separately.
        """
        ids = set(c.check_id for c in self.non_inheritable_variant_checks())
        seen = 0
        for key, product in CORPUS:
            for finding in product.findings:
                if finding.check_id not in ids or finding.status == R.UNKNOWN:
                    continue
                quoted = [e for e in finding.evidence if e.type == "field_value"]
                if not quoted or any("variants[" in (e.locator or "") for e in quoted):
                    continue
                seen += 1
                self.assertEqual(finding.status, R.PARTIAL,
                                 "%s / %s" % (key, finding.check_id))
                self.assertEqual(float(finding.earned), 0.0,
                                 "%s / %s" % (key, finding.check_id))
                self.assertEqual(float(finding.penalty), 0.0)
        self.assertTrue(seen, "no D-018 finding in the corpus; this test "
                              "proved nothing")

    def test_uncovered_variants_are_named_individually(self):
        """PRD 9.7: never 'some variants'."""
        for key, product in CORPUS:
            for finding in product.findings:
                notes = " ".join(e.note or "" for e in finding.evidence)
                self.assertNotIn("some variants", notes.lower(),
                                 "%s / %s" % (key, finding.check_id))


class TestNoRecognitionPredicateIsImplementedYet(unittest.TestCase):
    """The precondition this whole module was written ahead of.

    When P3.2 lands, this test is the one that legitimately changes -- and the
    ones above are the ones that must not.
    """

    def test_the_declared_predicate_set_is_intact(self):
        self.assertEqual(len(registry.RECOGNITION_PREDICATES), 116)

    def test_no_check_decides_satisfaction_by_recognition_yet(self):
        for check in registry.ALL_CHECKS:
            if check.structural_satisfaction:
                continue
            self.assertIn(check.satisfies, registry.RECOGNITION_PREDICATES,
                          "%s declares an unregistered predicate" % check.check_id)

    def test_no_penalty_dimension_check_may_gain_a_satisfaction_predicate(self):
        """D6 and D7 fire on defects, never on a satisfaction verdict. If a
        predicate is ever wired to one, it can subtract points, and the whole
        guarantee above is gone."""
        for check in registry.ALL_CHECKS:
            if check.dimension in R.PENALTY_DIMENSIONS:
                self.assertEqual(float(check.max_points), 0.0, check.check_id)

    def test_every_deferral_carries_a_reason(self):
        for key, product in CORPUS:
            for row in product.ledger.deferred:
                self.assertTrue(row.get("reason"), "%s / %s" % (key, row))

    def test_a_deferred_check_emits_no_finding(self):
        """D-019 rule 3: nothing about a deferred check reaches output."""
        for key, product in CORPUS:
            deferred = set(row["check_id"] for row in product.ledger.deferred)
            emitted = set(f.check_id for f in product.findings)
            self.assertEqual(deferred & emitted, set(),
                             "%s: a check both deferred and emitted" % key)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
