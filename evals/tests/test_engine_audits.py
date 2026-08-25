"""Every fixture, through the engine, through the audits.

AGENTS.md 6: *"every report the engine produces must be run through
`evals/run_audits.py`, and a red audit blocks the change."* This is that rule
as a test. It is the gate that matters most in the repository, because it is
the only one that checks the engine's real output rather than a double someone
wrote by hand.

The arithmetic audit's whole-score stages are not run here: this phase computes
no score, and asserting a total it does not produce would be asserting nothing.
Its per-finding consistency stage *is* run, because points-per-status is
settled by `rubric.md` 3.1 and is exactly what this phase does decide.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVALS = os.path.join(REPO, "evals")
for path in (REPO, EVALS):
    if path not in sys.path:
        sys.path.insert(0, path)

from audits import audit_claim_scope, audit_fabrication, audit_negation  # noqa: E402
from audits.arithmetic_audit import _check_finding_points_consistency    # noqa: E402
from harness import report_for_fixture                                   # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(REPO, "evals/fixtures/*/*.pip.json")))


def load(path):
    with open(path) as handle:
        return json.load(handle)


def artifacts(path):
    relative = os.path.relpath(path, REPO)
    return (report_for_fixture(relative), load(path),
            load(path.replace("fixtures", "expected").replace(".pip.json",
                                                              ".expected.json")),
            relative)


class TestEngineOutputIsAuditClean(unittest.TestCase):
    def test_the_corpus_is_covered(self):
        self.assertGreaterEqual(len(FIXTURES), 21)

    def test_fabrication_audit(self):
        for path in FIXTURES:
            report, fixture, expectation, name = artifacts(path)
            result = audit_fabrication(report, fixture, expectation, artifact=name)
            self.assertTrue(result.ok, result.render())

    def test_negation_language_audit(self):
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            result = audit_negation(report, artifact=name)
            self.assertTrue(result.ok, result.render())

    def test_claim_scope_audit(self):
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            result = audit_claim_scope(report, artifact=name)
            self.assertTrue(result.ok, result.render())

    def test_finding_points_are_consistent_with_status(self):
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            violations = []
            for index, product in enumerate(report["products"]):
                _check_finding_points_consistency(
                    product, violations, product.get("product_id"),
                    "products[%d]" % index)
            self.assertEqual([v.as_dict() for v in violations], [], name)


class TestReportShape(unittest.TestCase):
    def test_every_finding_carries_the_prd_fields(self):
        """PRD 7.3's finding object, plus `determination` (D-026).

        `determination` is the one field P3.2 added, and it was added for a
        stated reason: PRD 9.5 requires an *(interpreted)* tag in the Markdown
        report, and the confidence value alone cannot carry it because a `low`
        check reports `low` on both arms (D-020). PRD 7.3 owes the schema this
        field.
        """
        expected = sorted(["finding_id", "check_id", "dimension", "scope", "status",
                           "severity", "confidence", "determination", "title",
                           "detail", "evidence", "points", "remediation"])
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            for product in report["products"]:
                for finding in product["findings"]:
                    self.assertEqual(sorted(finding), expected, name)
                    self.assertEqual(sorted(finding["scope"]), ["level", "ref"])
                    self.assertEqual(sorted(finding["points"]),
                                     ["earned", "max", "penalty"])

    def test_no_finding_is_emitted_without_evidence(self):
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            for product in report["products"]:
                for finding in product["findings"]:
                    self.assertTrue(finding["evidence"],
                                    "%s / %s" % (name, finding["check_id"]))

    def test_the_engine_reports_no_run_errors_on_the_corpus(self):
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            self.assertEqual(report["run"]["run_errors"], [], name)

    def test_no_score_is_reported_yet(self):
        """Aggregation is a later phase; a zeroed score would read as a result."""
        for path in FIXTURES:
            report, _, _, name = artifacts(path)
            for product in report["products"]:
                self.assertNotIn("score", product, name)

    def test_output_is_byte_identical_across_runs(self):
        for path in FIXTURES[:5]:
            relative = os.path.relpath(path, REPO)
            first = json.dumps(report_for_fixture(relative), sort_keys=True)
            second = json.dumps(report_for_fixture(relative), sort_keys=True)
            self.assertEqual(first, second, relative)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
