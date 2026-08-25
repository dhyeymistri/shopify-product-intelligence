"""The recognition lexicon, and the one way it could fail open.

D-022 puts every phrase set, unit spelling and controlled vocabulary in one
module versioned with `rubric.md`. Two properties make that safe, and neither
is self-evident from reading the module:

* **No entry is a product value.** A lexicon describes the *shape* of an
  answer. The moment an entry is a measurement, a proportion or a fact, the
  tool is carrying a product fact it can emit.
* **No entry reaches merchant-facing output.** The merchant's own value is
  quoted verbatim as evidence and that is legitimate; the tool's vocabulary
  for judging it is not, and a report that repeats a lexicon phrase back as
  though it were the merchant's is a fabrication with a locator attached.

The second is asserted over real engine output for the whole corpus, in
`title`, `detail` and evidence `note` -- the text this phase generates. The
registry's `question` strings are excluded: they were authored in P3.1 and are
already linted against the fabrication audit's fact lexicon by
`test_registry.py`, and several of them legitimately contain a category word
that also appears in a phrase set (`"Which sport or activity is this for?"`).
"""

from __future__ import annotations

import glob
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from engine import lexicon, normalize, recognize                # noqa: E402
from engine import registry, rubric_data as R                   # noqa: E402
from engine.runner import run_result                            # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(REPO, "evals/fixtures/*/*.pip.json")))


def corpus():
    out = []
    for path in FIXTURES:
        for product in run_result(normalize.normalize_file(path)):
            out.append((os.path.basename(path), product))
    return out


CORPUS = corpus()


class TestVersioning(unittest.TestCase):
    def test_the_lexicon_is_versioned_with_the_rubric(self):
        self.assertEqual(lexicon.LEXICON_VERSION, R.RUBRIC_VERSION)

    def test_drift_is_a_load_failure_rather_than_a_silent_change(self):
        original = R.RUBRIC_VERSION
        R.RUBRIC_VERSION = "999.0"
        try:
            self.assertRaises(AssertionError, self._reimport)
        finally:
            R.RUBRIC_VERSION = original
            self._reimport()

    @staticmethod
    def _reimport():
        import importlib
        importlib.reload(lexicon)


class TestNoEntryIsAProductValue(unittest.TestCase):
    def test_the_import_time_assertion_holds(self):
        lexicon.assert_no_product_values()

    def test_no_value_shaped_entry_carries_a_digit(self):
        for entry in lexicon.VALUE_SHAPED:
            self.assertIsNone(re.search(r"\d", entry), entry)

    def test_every_entry_is_already_normalized(self):
        for entry in lexicon.ALL_ENTRIES:
            self.assertEqual(entry, lexicon.normalize(entry))
            self.assertTrue(entry.strip())

    def test_the_assertion_can_actually_fail(self):
        original = lexicon.VALUE_SHAPED
        lexicon.VALUE_SHAPED = frozenset(["60% cotton"])
        try:
            self.assertRaises(AssertionError, lexicon.assert_no_product_values)
        finally:
            lexicon.VALUE_SHAPED = original

    def test_the_module_holds_no_table_relating_one_term_to_another(self):
        """D-006: a conversion table is the shortest path from no world
        knowledge to some world knowledge, so the module exposes no mapping."""
        for name, value in vars(lexicon).items():
            if name.startswith("_"):
                continue
            self.assertNotIsInstance(value, dict, name)


class TestNormalization(unittest.TestCase):
    def test_case_whitespace_and_one_trailing_stop_are_formatting_only(self):
        for raw in ("Everyday", "  everyday  ", "every\tday", "everyday.",
                    "Everyday!"):
            self.assertIn(lexicon.normalize(raw),
                          ("everyday", "every day"))

    def test_normalization_never_changes_what_a_value_says(self):
        self.assertEqual(lexicon.normalize("60% Cotton"), "60% cotton")
        self.assertEqual(lexicon.normalize("N-24"), "n-24")


class TestMembershipIsWholeValue(unittest.TestCase):
    """Substring matching is prohibited: a phrase inside a sentence is not the
    same fact as a value that *is* the phrase."""

    def test_the_exact_phrase_matches(self):
        check = registry.get("APPAREL.INTENDED_USE_CONTEXT")
        self.assertIs(check.recognize("Everyday"), registry.AMBIGUOUS)

    def test_the_phrase_inside_a_sentence_does_not(self):
        check = registry.get("APPAREL.INTENDED_USE_CONTEXT")
        self.assertIs(check.recognize("Cut for everyday wear and layering"),
                      registry.UNDECIDED)


class TestNoLexiconLeak(unittest.TestCase):
    """The one way this module could fail open."""

    @staticmethod
    def _generated_text(product):
        out = []
        for finding in product.findings:
            out.append(finding.title or "")
            out.append(finding.detail or "")
            for item in finding.evidence:
                out.append(item.note or "")
        return " ".join(out)

    def test_no_value_shaped_entry_appears_in_generated_report_text(self):
        # Entries of one or two characters are size abbreviations (`s`, `xl`).
        # Word-boundary matching cannot tell those from ordinary prose, so
        # they are covered by the whole-string assertion below instead.
        patterns = [(entry, re.compile(r"(?<!\w)%s(?!\w)" % re.escape(entry)))
                    for entry in sorted(lexicon.VALUE_SHAPED)
                    if len(entry) >= 3]
        for name, product in CORPUS:
            text = self._generated_text(product).lower()
            for entry, pattern in patterns:
                self.assertIsNone(pattern.search(text),
                                  "%s: lexicon entry %r reached generated "
                                  "report text" % (name, entry))

    def test_no_short_entry_is_ever_a_whole_generated_string(self):
        short = set(e for e in lexicon.VALUE_SHAPED if len(e) < 3)
        self.assertTrue(short, "no short entries; this test proved nothing")
        for name, product in CORPUS:
            for finding in product.findings:
                fragments = [finding.title, finding.detail]
                fragments += [e.note for e in finding.evidence]
                for fragment in fragments:
                    if fragment:
                        self.assertNotIn(fragment.strip().lower(), short,
                                         "%s: %r" % (name, fragment))

    def test_the_leak_detector_can_actually_fire(self):
        pattern = re.compile(r"(?<!\w)%s(?!\w)"
                             % re.escape(sorted(lexicon.VALUE_SHAPED)[0]))
        self.assertIsNotNone(pattern.search(sorted(lexicon.VALUE_SHAPED)[0]))

    def test_the_merchants_own_value_is_still_quoted(self):
        """Excerpts are exempt and must be: the whole point of a `PARTIAL` on
        a vague value is that the merchant sees what they supplied."""
        excerpts = []
        for name, product in CORPUS:
            for finding in product.findings:
                for item in finding.evidence:
                    if item.excerpt:
                        excerpts.append(item.excerpt.lower())
        self.assertIn("everyday", excerpts)


class TestPredicatesReadStructuredValuesOnly(unittest.TestCase):
    """D-019, asserted by instrumenting the evaluator rather than by reading
    the code. A predicate that ever sees prose has bypassed the gate that keeps
    the tool from inferring a fact out of a description."""

    def test_no_predicate_is_ever_handed_a_prose_value(self):
        seen = []
        original = dict(registry.IMPLEMENTED_PREDICATES)
        for key, fn in original.items():
            registry.IMPLEMENTED_PREDICATES[key] = \
                (lambda f: lambda value: seen.append(value) or f(value))(fn)
        try:
            instrumented = corpus()
        finally:
            registry.IMPLEMENTED_PREDICATES.clear()
            registry.IMPLEMENTED_PREDICATES.update(original)
        self.assertTrue(seen, "no predicate ran; this test proved nothing")

        prose = set()
        for path in FIXTURES:
            result = normalize.normalize_file(path)
            for npr in result.products:
                narrative = npr.get("narrative") or {}
                for field in ("description_text", "description_html",
                              "seo_title", "seo_description"):
                    value = (narrative.get(field) or {}).get("value")
                    if value:
                        prose.add(value)
        self.assertTrue(prose, "no prose in the corpus; this proved nothing")
        for value in seen:
            self.assertIsInstance(value, str)
            self.assertNotIn(value, prose,
                             "a prose field reached a recognition predicate")
        del instrumented


class TestEveryImplementedPredicateHasAnOwningCheck(unittest.TestCase):
    def test_every_value_predicate_is_declared_by_a_check(self):
        declared = set()
        for check in registry.ALL_CHECKS:
            declared.update(x for x in (check.satisfies, check.partial_if)
                            if x)
        for predicate_id in recognize.VALUE_PREDICATES:
            self.assertIn(predicate_id, declared, predicate_id)

    def test_every_relation_is_declared_by_a_check(self):
        declared = set(c.satisfies for c in registry.ALL_CHECKS)
        for predicate_id in recognize.RELATION_PREDICATES:
            self.assertIn(predicate_id, declared, predicate_id)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
