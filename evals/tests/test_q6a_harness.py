"""The Q-6a corpus and its diagnostic harness.

Two things are asserted here and they are different in kind:

* **the corpus is what it claims to be** -- twelve uncategorized products in
  both input formats, validating clean, with `VARIANT.ATTRIBUTE_COVERAGE`
  removed on the ground D-029 documents for each cardinality; and
* **the harness stays a tool** -- it computes no score of its own, `engine/`
  never imports it, and it does not produce or imply a Q-6a answer.

The second is the one worth having. A measurement tool that grows its own copy
of `rubric.md` 6.1 becomes a second scoring function nobody versioned, and it
would do so one convenience at a time.
"""

from __future__ import annotations

import glob
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
EVALS = os.path.join(REPO, "evals")
if EVALS not in sys.path:
    sys.path.insert(0, EVALS)

from audits.arithmetic_audit import _compute_expected_score   # noqa: E402
from engine import registry, validate                         # noqa: E402
from engine import rubric_data as R                           # noqa: E402
from engine.runner import run_product                         # noqa: E402
from engine.taxonomy_data import UNCATEGORIZED                # noqa: E402
from measure import q6a                                       # noqa: E402

CORPUS = q6a.corpus()


class TestTheCorpusIsWhatItClaims(unittest.TestCase):
    def test_it_holds_twelve_products(self):
        self.assertEqual(len(CORPUS), 12)

    def test_both_input_formats_are_represented(self):
        formats = sorted(set(fmt for _, fmt, _, _ in CORPUS))
        self.assertEqual(formats, ["pip_json", "shopify_csv"])
        self.assertEqual(sum(1 for _, f, _, _ in CORPUS if f == "shopify_csv"), 3)

    def test_every_product_classifies_uncategorized_without_an_override(self):
        """The measurement is meaningless if any fixture is silently classified.

        `taxonomy.md` 2 reads five signal paths; a single mapping term in a
        title would move a product into a category and out of the population
        Q-6a is about.
        """
        for fid, _, npr, source in CORPUS:
            result = run_product(npr, source)
            self.assertEqual(result.classification.assigned, UNCATEGORIZED, fid)
            self.assertEqual(result.classification.method, UNCATEGORIZED, fid)

    def test_no_fixture_carries_a_mapping_term(self):
        """Asserted against the vocabulary itself, not against the outcome."""
        from engine.classify import CATEGORY_MAP
        terms = sorted({t for _, terms in CATEGORY_MAP for t in terms})
        for fid, _, npr, _ in CORPUS:
            haystacks = [(npr.get("identity") or {}).get("title", {}).get("value"),
                         (npr.get("narrative") or {}).get("description_text", {}).get("value"),
                         (npr.get("identity") or {}).get("product_type", {}).get("value"),
                         (npr.get("identity") or {}).get("declared_category", {}).get("value")]
            haystacks += [t.get("value") for t in (npr.get("tags") or [])]
            for text in haystacks:
                if not text:
                    continue
                for term in terms:
                    self.assertNotIn(term, text.lower(), "%s: %r" % (fid, term))

    def test_every_product_validates_clean(self):
        for fid, _, npr, source in CORPUS:
            self.assertEqual(validate.validate_npr(npr), [], fid)
            self.assertEqual(validate.validate_provenance(npr, source), [], fid)

    def test_attribute_coverage_is_removed_for_its_documented_reason(self):
        """D-029 records two grounds and they are different facts about the
        record. A fixture that reported the wrong one would still score the
        same, which is exactly why it is asserted rather than assumed."""
        seen_single = seen_multi = 0
        for fid, _, npr, source in CORPUS:
            result = run_product(npr, source)
            found = [f for f in result.findings if f.check_id == q6a.AC_CHECK]
            self.assertEqual(len(found), 1, fid)
            self.assertEqual(found[0].status, "NOT_APPLICABLE", fid)
            if len(npr.get("variants") or []) > 1:
                self.assertIn("No category is assigned", found[0].detail, fid)
                seen_multi += 1
            else:
                self.assertIn("A single variant is supplied", found[0].detail, fid)
                seen_single += 1
        self.assertGreater(seen_single, 0)
        self.assertGreater(seen_multi, 0)

    def test_no_product_reports_a_run_error(self):
        for fid, _, npr, source in CORPUS:
            self.assertEqual(run_product(npr, source).ledger.run_errors, [], fid)

    def test_every_fixture_has_an_expectation(self):
        expected = set(os.path.basename(p).replace(".expected.json", "")
                       for p in glob.glob(os.path.join(
                           REPO, "evals/expected/uncategorized/*.expected.json")))
        self.assertEqual(sorted(expected), sorted(set(fid for fid, _, _, _ in CORPUS)))


class TestTheC2DerivationHolds(unittest.TestCase):
    """C2 = C1 + 2.50 is a derivation, so it is verified rather than trusted."""

    def test_the_override_differs_from_a_real_category_only_at_the_identity_check(self):
        checked = 0
        for fid, fmt, npr, source in CORPUS:
            if fmt != "pip_json":
                continue
            self.assertIsNone(q6a.verify_c2_invariant(npr, source), fid)
            checked += 1
        self.assertGreater(checked, 0)

    def test_the_credit_is_the_identity_checks_own_maximum(self):
        self.assertEqual(float(registry.get(q6a.IDENT_CHECK).max_points),
                         q6a.IDENT_CREDIT)


class TestTheHarnessIsNotScoringLogic(unittest.TestCase):
    def test_engine_never_imports_the_harness(self):
        """The one-way boundary, asserted over the source rather than by habit.

        Only import statements are read. A docstring mentioning the harness is
        documentation; an import of it would make a diagnostic tool part of the
        scoring path.
        """
        for path in sorted(glob.glob(os.path.join(REPO, "engine/*.py"))):
            with open(path, encoding="utf-8") as handle:
                imports = [line.strip() for line in handle
                           if line.lstrip().startswith(("import ", "from "))]
            for line in imports:
                self.assertNotIn("measure", line,
                                 "%s imports the diagnostic harness: %s"
                                 % (os.path.basename(path), line))
                self.assertNotIn("evals", line,
                                 "%s imports from evals: %s"
                                 % (os.path.basename(path), line))

    def test_it_computes_no_score_of_its_own(self):
        """Every normalized figure must come from the arithmetic audit.

        Recomputed here through the audit directly: if the harness had grown its
        own `raw_earned / raw_max`, the two would diverge the first time either
        changed.
        """
        for fid, _, npr, source in CORPUS:
            result = run_product(npr, source)
            expected, _p, _t, _d, _g, _c = _compute_expected_score(result.as_dict())
            self.assertAlmostEqual(q6a.measure(npr, source)["A"], expected, places=9,
                                   msg=fid)

    def test_it_writes_only_under_reports_diagnostics(self):
        self.assertTrue(q6a.OUT_DIR.endswith(os.path.join("reports", "diagnostics")),
                        q6a.OUT_DIR)

    def test_the_output_is_stamped_and_answers_nothing(self):
        rendered = q6a.render()
        self.assertIn(q6a.STAMP, rendered)
        self.assertIn("Q-6a is not answered here", rendered)
        self.assertIn("Option 3", rendered)

    def test_the_truncation_columns_are_reported_and_never_folded_in(self):
        """`d_D2_deferred` is an implementation gap, not a scoring effect.

        Folding it into a delta would report the one as the other, which is the
        specific confusion this corpus exists to avoid.
        """
        rendered = q6a.render()
        for column in ("d_D029", "d_D2_observed", "d_D2_deferred",
                       "d_rest_deferred", "d_IDENT"):
            self.assertIn(column, rendered)
        for fid, _, npr, source in CORPUS:
            row = q6a.measure(npr, source)
            # the headline is the two renormalized figures and nothing else
            self.assertAlmostEqual(row["A_to_C2"], row["A"] - row["C2"], places=9,
                                   msg=fid)
            self.assertGreaterEqual(row["d_D2_deferred"], 0.0, fid)

    def test_d029_is_zero_on_single_variant_products_and_positive_otherwise(self):
        """D-029 changes nothing where `NA_SINGLE_VARIANT` already removed the
        check, and can only ever be favourable against the reading it rejected."""
        for fid, _, npr, source in CORPUS:
            row = q6a.measure(npr, source)
            if row["multi"]:
                self.assertGreater(row["d_D029"], 0.0, fid)
            else:
                self.assertAlmostEqual(row["d_D029"], 0.0, places=9, msg=fid)


class TestTheComparabilityGuardFailsClosed(unittest.TestCase):
    """A future rubric version that decides more D2 predicates moves
    `d_D2_observed` and `d_D2_deferred` for that reason alone. The guard says so
    rather than letting the two runs be charted together."""

    def test_it_is_clean_at_the_pinned_version(self):
        self.assertEqual(q6a.comparability_guard(), [])
        self.assertEqual(R.RUBRIC_VERSION, q6a.PINNED_RUBRIC_VERSION)

    def test_the_pin_matches_the_registry(self):
        self.assertEqual(q6a.decidable_d2(), q6a.PINNED_DECIDABLE_D2)

    def test_a_changed_predicate_set_is_detected(self):
        original = q6a.PINNED_DECIDABLE_D2
        try:
            q6a.PINNED_DECIDABLE_D2 = original + ("APPAREL.FIT_AND_CUT",)
            problems = q6a.comparability_guard()
            self.assertTrue(problems)
            self.assertIn("decidable apparel D2 predicate set changed", problems[0])
        finally:
            q6a.PINNED_DECIDABLE_D2 = original

    def test_a_changed_rubric_version_is_detected(self):
        original = q6a.PINNED_RUBRIC_VERSION
        try:
            q6a.PINNED_RUBRIC_VERSION = "0.99"
            problems = q6a.comparability_guard()
            self.assertTrue(any("rubric_version" in p for p in problems))
        finally:
            q6a.PINNED_RUBRIC_VERSION = original


class TestTheCorpusInvariantsPass(unittest.TestCase):
    def test_the_harnesss_own_invariant_sweep_is_clean(self):
        self.assertEqual(q6a.invariants(), [])
