#!/usr/bin/env python3
"""Run the fabrication audit over report artifacts.

    python3 evals/run_audits.py --report <report.json> --fixture <fixture.pip.json>
                               [--expected <expected.json>] [--markdown <report.md>]
                               [--json]
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

from audits.fabrication_audit import audit_markdown, audit_report  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SELF_TEST_PAIRS = [
    ("evals/testdata/reports/honest/honest-sparse-apparel-01.report.json",
     "evals/fixtures/sparse/sparse-apparel-01.pip.json", None, True),
    ("evals/testdata/reports/honest/honest-adv-02-helmet.report.json",
     "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
     "evals/expected/adversarial/adv-02-category-implies-attributes.expected.json", True),
]

_VIOLATION_FIXTURES = {
    "v07": "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
    "v08": "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
    "v09": "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
    "v10": "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
    "v14": "evals/fixtures/adversarial/adv-02-category-implies-attributes.pip.json",
    "v12": "evals/fixtures/sparse/sparse-apparel-02.pip.json",
}


def load(path):
    with open(path if os.path.isabs(path) else os.path.join(REPO, path)) as handle:
        return json.load(handle)


def _self_test():
    failures = 0
    cases = list(SELF_TEST_PAIRS)

    directory = os.path.join(REPO, "evals/testdata/reports/violations")
    default_fixture = "evals/fixtures/sparse/sparse-apparel-01.pip.json"
    expectation = "evals/expected/adversarial/adv-02-category-implies-attributes.expected.json"
    for name in sorted(os.listdir(directory)):
        cases.append((
            "evals/testdata/reports/violations/%s" % name,
            _VIOLATION_FIXTURES.get(name[:3], default_fixture),
            expectation,
            False,
        ))

    for report_path, fixture_path, expected_path, should_pass in cases:
        result = audit_report(
            load(report_path), load(fixture_path),
            load(expected_path) if expected_path else None,
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

    print("\n%d case(s), %d unexpected outcome(s)" % (len(cases), failures))
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", help="report.json to audit")
    parser.add_argument("--fixture", help="the PIP fixture the report was produced from")
    parser.add_argument("--expected", help="expectation file supplying must_not_fabricate baits")
    parser.add_argument("--markdown", help="report.md to audit as well")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--self-test", action="store_true", help="audit the bundled doubles")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    if not args.report or not args.fixture:
        parser.error("--report and --fixture are required (or use --self-test)")

    fixture = load(args.fixture)
    expectation = load(args.expected) if args.expected else None
    results = [audit_report(load(args.report), fixture, expectation,
                            artifact=os.path.basename(args.report))]

    if args.markdown:
        path = args.markdown if os.path.isabs(args.markdown) else os.path.join(REPO, args.markdown)
        with open(path) as handle:
            results.append(audit_markdown(handle.read(), fixture, expectation,
                                          artifact=os.path.basename(args.markdown)))

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2, sort_keys=True))
    else:
        for result in results:
            print(result.render())

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
