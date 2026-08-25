#!/usr/bin/env python3
"""Run all audits over report artifacts.

    python3 evals/run_audits.py --report <report.json> --fixture <fixture.pip.json>
                                [--expected <expected.json>] [--markdown <report.md>]
                                [--json] [--audits fabrication,arithmetic,negation,claim_scope]
    python3 evals/run_audits.py --self-test

`--self-test` audits the bundled test doubles: honest reports must pass and every
seeded violation must be caught. It is the fastest way to confirm the gate is
live before wiring an engine to it.

Exit status is 0 only when every audited artifact is clean, so this is usable
directly as a CI gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audits import (
    audit_fabrication, audit_fabrication_markdown,
    audit_arithmetic, audit_arithmetic_markdown,
    audit_negation, audit_negation_markdown,
    audit_claim_scope, audit_claim_scope_markdown,
)  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(path if os.path.isabs(path) else os.path.join(REPO, path)) as handle:
        return json.load(handle)


SELF_TEST_PAIRS = [
    ("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json",
     "evals/fixtures/sparse/sparse-apparel-01.pip.json", None, True),
    ("evals/testdata/reports/honest/honest-adv-02-helmet.report.json",
     "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
     "evals/expected/adversarial/adv-02-category-implies-attributes.expected.json", True),
]

# Violation fixtures mapped to their target audits
# Each entry: (fixture_prefix, fixture_path, expected_audit_codes)
VIOLATION_TESTS = [
    # Fabrication audit violations (v01-v14)
    ("v01", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB001_EMPTY_EVIDENCE"]),
    ("v02", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB002_INVALID_LOCATOR"]),
    ("v03", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB003_NON_REPRODUCIBLE_QUOTE"]),
    ("v04", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB004_FABRICATED_MODEL_NUMBER"]),
    ("v05", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB005_FABRICATED_SPECIFICATION"]),
    ("v06", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB006_INVENTED_MATERIAL"]),
    ("v07", "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json", ["FAB007_INVENTED_COMPATIBILITY"]),
    ("v08", "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json", ["FAB008_INVENTED_DIMENSION"]),
    ("v09", "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json", ["FAB009_INVENTED_SAFETY_CLAIM"]),
    ("v10", "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json", ["FAB010_INVENTED_USE_CASE"]),
    ("v11", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB011_MISSING_CHECKED_PATHS"]),
    ("v12", "evals/fixtures/sparse/sparse-apparel-02.pip.json", ["FAB012_FALSE_GAP"]),
    ("v13", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["FAB013_SUGGESTED_VALUE_IN_QUESTION"]),
    ("v14", "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json", ["FAB014_KNOWN_BAIT_EMITTED"]),

    # Arithmetic audit violations (v15-v19)
    ("v15", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["ARI001_MISMATCH_TOTAL"]),
    ("v16", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["ARI003_MISMATCH_DIMENSION_EARNED"]),
    ("v17", "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json", ["ARI013_PENALTY_EXCEEDS_CAP"]),
    ("v18", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["ARI006_MISMATCH_GRADE"]),
    ("v19", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["ARI014_FINDING_POINTS_INCONSISTENT"]),

    # Negation-language audit violations (v20)
    ("v20", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["NEG001_DOES_NOT", "NEG003_LACKS"]),

    # Claim-scope audit violations (v21)
    ("v21", "evals/fixtures/sparse/sparse-apparel-01.pip.json", ["CLM001_AI_RANKING", "CLM011_GUARANTEES"]),
]


def _run_audit_self_test(audit_name: str, audit_fn, markdown_fn, violation_codes_for_this_audit: set, takes_fixture: bool = True):
    """Run self-test for a specific audit."""
    failures = 0

    # Test honest reports (should pass)
    for report_path, fixture_path, expected_path, should_pass in SELF_TEST_PAIRS:
        if takes_fixture:
            result = audit_fn(
                load(report_path), load(fixture_path),
                artifact=os.path.basename(report_path),
            )
        else:
            result = audit_fn(
                load(report_path),
                artifact=os.path.basename(report_path),
            )
        good = result.ok if should_pass else not result.ok
        label = "OK  " if good else "BAD "
        verdict = "clean" if result.ok else "%d violation(s): %s" % (
            len(result.violations), ", ".join(sorted(set(result.codes()))),
        )
        print("%s %-46s %s" % (label, os.path.basename(report_path), verdict))
        if not good:
            failures += 1
            print(result.render())

    # Test violation fixtures that target this audit
    directory = os.path.join(REPO, "evals/testdata/reports/violations")
    for prefix, fixture_path, expected_codes in VIOLATION_TESTS:
        if prefix not in violation_codes_for_this_audit:
            continue

        matching = [f for f in os.listdir(directory) if f.startswith(prefix + "-")]
        if not matching:
            continue
        report_path = os.path.join(directory, matching[0])

        if takes_fixture:
            fixture = load(fixture_path)
            result = audit_fn(load(report_path), fixture, artifact=matching[0])
        else:
            result = audit_fn(load(report_path), artifact=matching[0])
        # For violation fixtures, the audit SHOULD find violations (result.ok == False)
        good = not result.ok
        label = "OK  " if good else "BAD "
        found_codes = set(result.codes())
        expected_code_set = set(expected_codes)
        if expected_code_set & found_codes:
            verdict = "detected: %s" % ", ".join(sorted(expected_code_set & found_codes))
        else:
            verdict = "clean (expected: %s)" % ", ".join(sorted(expected_codes))
        print("%s %-46s %s" % (label, matching[0], verdict))
        if not good:
            failures += 1
            print(result.render())

    # Also test markdown if applicable
    if markdown_fn:
        markdown = "# Northgate Crew Neck T-Shirt\n\nNot stated in the supplied data.\n"
        if takes_fixture:
            fixture = load("evals/fixtures/sparse/sparse-apparel-01.pip.json")
            result = markdown_fn(markdown, fixture, artifact="test.md")
        else:
            result = markdown_fn(markdown, artifact="test.md")
        if not result.ok:
            failures += 1
            print("BAD markdown test: %s" % result.render())
        else:
            print("OK  markdown test")

    print("\n%s: %d unexpected outcome(s)" % (audit_name, failures))
    return 1 if failures else 0


def _self_test():
    """Run self-tests for all audits."""
    total_failures = 0

    print("=" * 60)
    print("FABRICATION AUDIT")
    print("=" * 60)
    fab_codes = {"FAB001_EMPTY_EVIDENCE", "FAB002_INVALID_LOCATOR", "FAB003_NON_REPRODUCIBLE_QUOTE",
                 "FAB004_FABRICATED_MODEL_NUMBER", "FAB005_FABRICATED_SPECIFICATION", "FAB006_INVENTED_MATERIAL",
                 "FAB007_INVENTED_COMPATIBILITY", "FAB008_INVENTED_DIMENSION", "FAB009_INVENTED_SAFETY_CLAIM",
                 "FAB010_INVENTED_USE_CASE", "FAB011_MISSING_CHECKED_PATHS", "FAB012_FALSE_GAP",
                 "FAB013_SUGGESTED_VALUE_IN_QUESTION", "FAB014_KNOWN_BAIT_EMITTED"}
    total_failures += _run_audit_self_test("fabrication", audit_fabrication, audit_fabrication_markdown, fab_codes, takes_fixture=True)

    print("\n" + "=" * 60)
    print("ARITHMETIC AUDIT")
    print("=" * 60)
    ari_codes = {"ARI001_MISMATCH_TOTAL", "ARI002_MISMATCH_MAX_APPLICABLE", "ARI003_MISMATCH_DIMENSION_EARNED",
                 "ARI004_MISMATCH_DIMENSION_MAX", "ARI005_MISMATCH_PENALTIES", "ARI006_MISMATCH_GRADE",
                 "ARI007_MISSING_DIMENSION", "ARI008_EXTRA_DIMENSION", "ARI009_MISMATCH_NORMALIZED",
                 "ARI010_MISMATCH_GRADE_CAPPED", "ARI011_MISMATCH_N_A_HANDLING", "ARI012_RAW_MAX_NOT_82",
                 "ARI013_PENALTY_EXCEEDS_CAP", "ARI014_FINDING_POINTS_INCONSISTENT", "ARI015_ROUNDING_ERROR"}
    total_failures += _run_audit_self_test("arithmetic", audit_arithmetic, audit_arithmetic_markdown, ari_codes, takes_fixture=False)

    print("\n" + "=" * 60)
    print("NEGATION-LANGUAGE AUDIT")
    print("=" * 60)
    neg_codes = {"NEG001_DOES_NOT", "NEG002_IS_NOT", "NEG003_LACKS", "NEG004_NO_ATTRIBUTE",
                 "NEG005_MISSING", "NEG006_WITHOUT", "NEG007_ABSENT", "NEG008_DOESNT_HAVE",
                 "NEG009_IS_MISSING", "NEG010_NOT_INCLUDED", "NEG011_NOT_PRESENT",
                 "NEG012_FAILS_TO", "NEG013_OMITS", "NEG014_NO_MENTION"}
    total_failures += _run_audit_self_test("negation", audit_negation, audit_negation_markdown, neg_codes, takes_fixture=False)

    print("\n" + "=" * 60)
    print("CLAIM-SCOPE AUDIT")
    print("=" * 60)
    clm_codes = {"CLM001_AI_RANKING", "CLM002_RECOMMENDED_BY", "CLM003_APPEAR_IN", "CLM004_RANK_HIGHER",
                 "CLM005_DISCOVERY", "CLM006_OPTIMIZED_FOR", "CLM007_AI_READINESS", "CLM008_CITATION",
                 "CLM009_CATALOG_PLACEMENT", "CLM010_AGENTIC_STOREFRONT", "CLM011_GUARANTEES",
                 "CLM012_BOOSTS", "CLM013_AI_CHANNEL", "CLM014_WILL_BE", "CLM015_GET_INTO"}
    total_failures += _run_audit_self_test("claim_scope", audit_claim_scope, audit_claim_scope_markdown, clm_codes, takes_fixture=False)

    print("\n%d total unexpected outcome(s) across all audits" % total_failures)
    return 1 if total_failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", help="report.json to audit")
    parser.add_argument("--fixture", help="the PIP fixture the report was produced from")
    parser.add_argument("--expected", help="expectation file supplying must_not_fabricate baits")
    parser.add_argument("--markdown", help="report.md to audit as well")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--self-test", action="store_true", help="audit the bundled doubles")
    parser.add_argument("--audits", default="fabrication,arithmetic,negation,claim_scope",
                        help="comma-separated list of audits to run (default: all)")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    if not args.report or not args.fixture:
        parser.error("--report and --fixture are required (or use --self-test)")

    fixture = load(args.fixture)
    expectation = load(args.expected) if args.expected else None

    audit_names = [a.strip() for a in args.audits.split(",")]
    invalid = [a for a in audit_names if a not in AUDIT_FUNCTIONS]
    if invalid:
        parser.error("Unknown audit(s): %s. Valid: %s" % (", ".join(invalid), ", ".join(AUDIT_FUNCTIONS.keys())))

    results = []
    report_obj = load(args.report)

    for audit_name in audit_names:
        audit_fn, markdown_fn = AUDIT_FUNCTIONS[audit_name]
        results.append(audit_fn(report_obj, fixture, expectation,
                                artifact=os.path.basename(args.report)))
        if args.markdown and markdown_fn:
            path = args.markdown if os.path.isabs(args.markdown) else os.path.join(REPO, args.markdown)
            with open(path) as handle:
                results.append(markdown_fn(handle.read(), fixture, expectation,
                                           artifact=os.path.basename(args.markdown)))

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2, sort_keys=True))
    else:
        for result in results:
            print(result.render())

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
