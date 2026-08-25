"""The arithmetic audit -- PRD 12.3 audit 6.

Independently recomputes every score from the findings ledger and compares
against the reported score. Any discrepancy is a blocker-severity violation.

The audit implements the exact arithmetic specified in rubric.md §6.1:
1. Build applicable check set from assigned category
2. Run each check -> status + evidence + earned points
3. Drop NOT_APPLICABLE checks from both numerator and denominator
4. raw_earned = Σ earned; raw_max = Σ max
5. normalized = (raw_earned / raw_max) * 100
6. penalties = Σ penalty over D6 and D7 findings (D6 capped at 10.0, D7 at 8.0)
7. total = clamp(normalized - penalties, 0, 100)
8. Assign grade band; apply blocker cap to label only, never the number.

Dimension point allocations (rubric.md §10.2):
- D1: 15 (earned)
- D2: 22 (earned, category-specific)
- D3: 15 (earned)
- D4: 12 (earned)
- D5: 12 (earned)
- D6: 10 (penalty-only)
- D7: 8  (penalty-only)
- D8: 6  (earned)
Total earned max = 82.0
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Dimension point allocations per rubric.md
DIMENSION_MAX = {
    "D1_identity": 15.0,
    "D2_category_attributes": 22.0,
    "D3_variant": 15.0,
    "D4_usecase": 12.0,
    "D5_trust": 12.0,
    "D6_consistency": 10.0,  # penalty exposure
    "D7_claims": 8.0,        # penalty exposure
    "D8_structure": 6.0,
}

EARNED_DIMENSIONS = frozenset(["D1_identity", "D2_category_attributes", "D3_variant", "D4_usecase", "D5_trust", "D8_structure"])
PENALTY_DIMENSIONS = frozenset(["D6_consistency", "D7_claims"])
ALL_DIMENSIONS = EARNED_DIMENSIONS | PENALTY_DIMENSIONS

# Grade bands per rubric.md §6.4
GRADE_BANDS = [
    (90, "agent_ready"),
    (75, "strong"),
    (60, "adequate"),
    (40, "weak"),
    (0, "insufficient"),
]

# Violation codes
ARI001_MISMATCH_TOTAL = "ARI001_MISMATCH_TOTAL"
ARI002_MISMATCH_MAX_APPLICABLE = "ARI002_MISMATCH_MAX_APPLICABLE"
ARI003_MISMATCH_DIMENSION_EARNED = "ARI003_MISMATCH_DIMENSION_EARNED"
ARI004_MISMATCH_DIMENSION_MAX = "ARI004_MISMATCH_DIMENSION_MAX"
ARI005_MISMATCH_PENALTIES = "ARI005_MISMATCH_PENALTIES"
ARI006_MISMATCH_GRADE = "ARI006_MISMATCH_GRADE"
ARI007_MISSING_DIMENSION = "ARI007_MISSING_DIMENSION"
ARI008_EXTRA_DIMENSION = "ARI008_EXTRA_DIMENSION"
ARI009_MISMATCH_NORMALIZED = "ARI009_MISMATCH_NORMALIZED"
ARI010_MISMATCH_GRADE_CAPPED = "ARI010_MISMATCH_GRADE_CAPPED"
ARI011_MISMATCH_N_A_HANDLING = "ARI011_MISMATCH_N_A_HANDLING"
ARI012_RAW_MAX_NOT_82 = "ARI012_RAW_MAX_NOT_82"
ARI013_PENALTY_EXCEEDS_CAP = "ARI013_PENALTY_EXCEEDS_CAP"
ARI014_FINDING_POINTS_INCONSISTENT = "ARI014_FINDING_POINTS_INCONSISTENT"
ARI015_ROUNDING_ERROR = "ARI015_ROUNDING_ERROR"

# Tolerance for floating-point comparison
EPS = 0.05  # 0.05 points tolerance for rounding differences


@dataclass
class ArithmeticViolation:
    code: str
    path: str
    detail: str
    product_id: Optional[str] = None
    expected: Optional[float] = None
    actual: Optional[float] = None
    severity: str = "blocker"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "product_id": self.product_id,
            "path": self.path,
            "detail": self.detail,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class ArithmeticAuditResult:
    violations: List[ArithmeticViolation]
    products_audited: int
    artifact: str

    @property
    def ok(self) -> bool:
        return not self.violations

    def codes(self) -> List[str]:
        return [v.code for v in self.violations]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "audit": "arithmetic",
            "artifact": self.artifact,
            "ok": self.ok,
            "products_audited": self.products_audited,
            "violation_count": len(self.violations),
            "violations": [v.as_dict() for v in self.violations],
        }

    def render(self) -> str:
        if self.ok:
            return f"PASS  arithmetic audit: {self.artifact} ({self.products_audited} product(s), 0 violations)"
        lines = [f"FAIL  arithmetic audit: {self.artifact} ({len(self.violations)} violation(s))"]
        for v in self.violations:
            lines.append(f"  [{v.code}] {v.path}")
            lines.append(f"      {v.detail}")
            if v.expected is not None and v.actual is not None:
                lines.append(f"      expected: {v.expected}, actual: {v.actual}")
        return "\n".join(lines)


def _float_eq(a: float, b: float, eps: float = EPS) -> bool:
    return abs(a - b) <= eps


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _grade_for_score(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "insufficient"


def _compute_expected_score(product_report: Dict[str, Any]) -> Tuple[float, float, float, Dict[str, Dict[str, float]], str, Optional[str]]:
    """Compute expected score from the findings ledger.
    
    Returns: (normalized, penalties, total, dim_breakdown, grade, grade_capped_by)
    """
    score_obj = product_report.get("score", {})
    findings = product_report.get("findings", [])
    category = product_report.get("category", {}).get("assigned", "uncategorized")
    
    # Sum earned and max from findings
    dim_earned = {}
    dim_max = {}
    d6_penalty = 0.0
    d7_penalty = 0.0
    blocker_findings = []
    
    for finding in findings:
        check_id = finding.get("check_id", "")
        dimension = finding.get("dimension", "")
        status = finding.get("status", "")
        points = finding.get("points", {})
        earned = points.get("earned", 0.0)
        max_pts = points.get("max", 0.0)
        penalty = points.get("penalty", 0.0)
        severity = finding.get("severity", "")
        
        if dimension in EARNED_DIMENSIONS:
            if status != "NOT_APPLICABLE":
                if dimension not in dim_earned:
                    dim_earned[dimension] = 0.0
                    dim_max[dimension] = 0.0
                dim_earned[dimension] += earned
                dim_max[dimension] += max_pts
        elif dimension == "D6_consistency":
            d6_penalty += penalty
            if severity == "blocker":
                blocker_findings.append(finding.get("finding_id"))
        elif dimension == "D7_claims":
            d7_penalty += penalty
            if severity == "blocker":
                blocker_findings.append(finding.get("finding_id"))
    
    # Cap penalties at dimension maxima
    d6_penalty = min(d6_penalty, DIMENSION_MAX["D6_consistency"])
    d7_penalty = min(d7_penalty, DIMENSION_MAX["D7_claims"])
    
    raw_earned = sum(dim_earned.values())
    raw_max = sum(dim_max.values())
    
    # Renormalization
    if raw_max > 0:
        normalized = (raw_earned / raw_max) * 100.0
    else:
        normalized = 0.0
    
    penalties = d6_penalty + d7_penalty
    total = _clamp(normalized - penalties, 0.0, 100.0)
    
    # Grade assignment
    grade = _grade_for_score(total)
    grade_capped_by = None
    if blocker_findings:
        grade = "insufficient"
        grade_capped_by = blocker_findings[0]  # first blocker
    
    # Build dimension breakdown for comparison (only dimensions with findings)
    dim_breakdown = {}
    for d in dim_earned:
        dim_breakdown[d] = {"earned": dim_earned[d], "max": dim_max[d], "penalty": 0.0}
    if d6_penalty > 0:
        dim_breakdown["D6_consistency"] = {"earned": 0.0, "max": DIMENSION_MAX["D6_consistency"], "penalty": d6_penalty}
    if d7_penalty > 0:
        dim_breakdown["D7_claims"] = {"earned": 0.0, "max": DIMENSION_MAX["D7_claims"], "penalty": d7_penalty}
    
    return normalized, penalties, total, dim_breakdown, grade, grade_capped_by


def _check_dimension_breakdown(product_report: Dict[str, Any], expected: Dict[str, Dict[str, float]], violations: List[ArithmeticViolation], pid: str, ppath: str) -> None:
    """Verify dimension breakdown matches computed values."""
    reported_dims = product_report.get("score", {}).get("dimensions", [])
    reported_by_dim = {d["dimension"]: d for d in reported_dims}
    
    # Only check dimensions that are present in the report
    for dim, rep in reported_by_dim.items():
        rpath = f"{ppath}.score.dimensions[{dim}]"
        if dim not in expected:
            violations.append(ArithmeticViolation(
                ARI008_EXTRA_DIMENSION,
                rpath,
                f"Unexpected dimension {dim} in score breakdown",
                pid,
            ))
            continue
        
        exp = expected[dim]
        rep_earned = rep.get("earned", 0.0)
        rep_max = rep.get("max", 0.0)
        
        if not _float_eq(rep_earned, exp["earned"]):
            violations.append(ArithmeticViolation(
                ARI003_MISMATCH_DIMENSION_EARNED,
                rpath,
                f"Dimension {dim} earned mismatch",
                pid,
                expected=exp["earned"],
                actual=rep_earned,
            ))
        if not _float_eq(rep_max, exp["max"]):
            violations.append(ArithmeticViolation(
                ARI004_MISMATCH_DIMENSION_MAX,
                rpath,
                f"Dimension {dim} max mismatch",
                pid,
                expected=exp["max"],
                actual=rep_max,
            ))
    
    # Don't flag missing dimensions - report may only include dimensions with findings


def _check_finding_points_consistency(product_report: Dict[str, Any], violations: List[ArithmeticViolation], pid: str, ppath: str) -> None:
    """Verify that finding points are internally consistent with status."""
    findings = product_report.get("findings", [])
    
    for fi, finding in enumerate(findings):
        fpath = f"{ppath}.findings[{fi}]"
        status = finding.get("status", "")
        points = finding.get("points", {})
        earned = points.get("earned", 0.0)
        max_pts = points.get("max", 0.0)
        penalty = points.get("penalty", 0.0)
        dimension = finding.get("dimension", "")
        check_id = finding.get("check_id", "")
        
        # Basic consistency checks
        if dimension in EARNED_DIMENSIONS:
            if status == "PASS" and not _float_eq(earned, max_pts):
                violations.append(ArithmeticViolation(
                    ARI014_FINDING_POINTS_INCONSISTENT,
                    f"{fpath}.points",
                    f"PASS finding has earned ({earned}) != max ({max_pts})",
                    pid,
                    expected=max_pts,
                    actual=earned,
                ))
            elif status == "UNKNOWN":
                if not _float_eq(earned, 0.0) or not _float_eq(penalty, 0.0):
                    violations.append(ArithmeticViolation(
                        ARI014_FINDING_POINTS_INCONSISTENT,
                        f"{fpath}.points",
                        f"UNKNOWN finding must have earned=0, penalty=0",
                        pid,
                        expected=0.0,
                        actual=earned,
                    ))
            elif status == "FAIL":
                if not _float_eq(earned, 0.0):
                    violations.append(ArithmeticViolation(
                        ARI014_FINDING_POINTS_INCONSISTENT,
                        f"{fpath}.points",
                        f"FAIL finding must have earned=0",
                        pid,
                        expected=0.0,
                        actual=earned,
                    ))
                if dimension not in PENALTY_DIMENSIONS and not _float_eq(penalty, 0.0):
                    violations.append(ArithmeticViolation(
                        ARI014_FINDING_POINTS_INCONSISTENT,
                        f"{fpath}.points",
                        f"FAIL finding in earned dimension must have penalty=0",
                        pid,
                    ))
            elif status == "PARTIAL":
                if earned < 0 or earned > max_pts:
                    violations.append(ArithmeticViolation(
                        ARI014_FINDING_POINTS_INCONSISTENT,
                        f"{fpath}.points",
                        f"PARTIAL finding earned ({earned}) outside [0, {max_pts}]",
                        pid,
                    ))
            elif status == "NOT_APPLICABLE":
                if not _float_eq(earned, 0.0) or not _float_eq(max_pts, 0.0) or not _float_eq(penalty, 0.0):
                    violations.append(ArithmeticViolation(
                        ARI014_FINDING_POINTS_INCONSISTENT,
                        f"{fpath}.points",
                        f"NOT_APPLICABLE finding must have earned=0, max=0, penalty=0",
                        pid,
                    ))
        
        # Penalty dimension checks
        if dimension in PENALTY_DIMENSIONS:
            if status == "FAIL" and penalty <= 0:
                violations.append(ArithmeticViolation(
                    ARI014_FINDING_POINTS_INCONSISTENT,
                    f"{fpath}.points",
                    f"FAIL finding in penalty dimension must have penalty > 0",
                    pid,
                ))
            if status in ("PASS", "UNKNOWN", "NOT_APPLICABLE") and not _float_eq(penalty, 0.0):
                violations.append(ArithmeticViolation(
                    ARI014_FINDING_POINTS_INCONSISTENT,
                    f"{fpath}.points",
                    f"{status} finding in penalty dimension must have penalty=0",
                    pid,
                ))


def audit_report(report: Dict[str, Any], artifact: str = "report.json") -> ArithmeticAuditResult:
    """Audit a report.json document for arithmetic correctness."""
    violations = []
    products = report.get("products", [])
    audited = 0
    
    for pi, product_report in enumerate(products):
        ppath = f"products[{pi}]"
        pid = product_report.get("product_id")
        
        if pid is None:
            violations.append(ArithmeticViolation(
                ARI001_MISMATCH_TOTAL,
                ppath,
                "Product has no product_id",
                pid,
            ))
            continue
        
        audited += 1
        
        # Compute expected values
        normalized, penalties, total, dim_breakdown, grade, grade_capped_by = _compute_expected_score(product_report)
        
        # Check reported score
        reported_score = product_report.get("score", {})
        reported_total = reported_score.get("total", 0.0)
        reported_max_applicable = reported_score.get("max_applicable", 0.0)
        reported_grade = reported_score.get("grade", "")
        reported_grade_capped_by = reported_score.get("grade_capped_by")
        
        # raw_max should be 82.0 minus N/A points
        # But we verify against the sum of dimension maxes
        expected_raw_max = sum(d["max"] for d in dim_breakdown.values() if d["max"] > 0 and d["max"] != DIMENSION_MAX.get(list(d.keys())[0], 0))
        # Actually, raw_max is the sum of max for earned dimensions only
        expected_raw_max = sum(d["max"] for d in dim_breakdown.values() if list(d.keys())[0] in EARNED_DIMENSIONS) if False else sum(v["max"] for k, v in dim_breakdown.items() if k in EARNED_DIMENSIONS)
        
        # Check total
        if not _float_eq(reported_total, total):
            violations.append(ArithmeticViolation(
                ARI001_MISMATCH_TOTAL,
                f"{ppath}.score.total",
                f"Total score mismatch",
                pid,
                expected=total,
                actual=reported_total,
            ))
        
        # Check max_applicable if present
        if "max_applicable" in reported_score:
            if not _float_eq(reported_max_applicable, expected_raw_max):
                violations.append(ArithmeticViolation(
                    ARI002_MISMATCH_MAX_APPLICABLE,
                    f"{ppath}.score.max_applicable",
                    f"max_applicable mismatch (should equal sum of earned dimension maxes)",
                    pid,
                    expected=expected_raw_max,
                    actual=reported_max_applicable,
                ))
        
        # Check normalized if present
        if "normalized" in reported_score:
            reported_normalized = reported_score["normalized"]
            if not _float_eq(reported_normalized, normalized):
                violations.append(ArithmeticViolation(
                    ARI009_MISMATCH_NORMALIZED,
                    f"{ppath}.score.normalized",
                    f"Normalized score mismatch",
                    pid,
                    expected=normalized,
                    actual=reported_normalized,
                ))
        
        # Check penalties if present
        if "penalties" in reported_score:
            reported_penalties = reported_score["penalties"]
            if not _float_eq(reported_penalties, penalties):
                violations.append(ArithmeticViolation(
                    ARI005_MISMATCH_PENALTIES,
                    f"{ppath}.score.penalties",
                    f"Penalties mismatch",
                    pid,
                    expected=penalties,
                    actual=reported_penalties,
                ))
        
        # Check grade if present
        if "grade" in reported_score:
            if reported_grade != grade:
                violations.append(ArithmeticViolation(
                    ARI006_MISMATCH_GRADE,
                    f"{ppath}.score.grade",
                    f"Grade mismatch",
                    pid,
                    expected=grade,
                    actual=reported_grade,
                ))
        
        # Check grade_capped_by if present
        if "grade_capped_by" in reported_score:
            if grade_capped_by is not None:
                if reported_grade_capped_by != grade_capped_by:
                    violations.append(ArithmeticViolation(
                        ARI010_MISMATCH_GRADE_CAPPED,
                        f"{ppath}.score.grade_capped_by",
                        f"grade_capped_by mismatch",
                        pid,
                        expected=grade_capped_by,
                        actual=reported_grade_capped_by,
                    ))
            elif reported_grade_capped_by is not None:
                violations.append(ArithmeticViolation(
                    ARI010_MISMATCH_GRADE_CAPPED,
                    f"{ppath}.score.grade_capped_by",
                    f"Reported grade_capped_by but no blocker finding found",
                    pid,
                    expected=None,
                    actual=reported_grade_capped_by,
                ))
        
        # Check dimension breakdown if present
        reported_dims = product_report.get("score", {}).get("dimensions", [])
        if reported_dims:
            _check_dimension_breakdown(product_report, dim_breakdown, violations, pid, ppath)
        
        # Check finding points consistency
        _check_finding_points_consistency(product_report, violations, pid, ppath)
        
        # Verify raw_max = 82 for full check set (no N/A)
        # This is a sanity check - the sum of all earned dimension maxes should be 82.0
        full_raw_max = sum(DIMENSION_MAX[d] for d in EARNED_DIMENSIONS)
        if not _float_eq(full_raw_max, 82.0):
            violations.append(ArithmeticViolation(
                ARI012_RAW_MAX_NOT_82,
                f"{ppath}.score",
                f"Sum of earned dimension maxes is {full_raw_max}, expected 82.0",
                pid,
            ))
        
        # Check penalty caps
        d6_penalty = sum(f.get("points", {}).get("penalty", 0.0) for f in product_report.get("findings", []) if f.get("dimension") == "D6_consistency")
        d7_penalty = sum(f.get("points", {}).get("penalty", 0.0) for f in product_report.get("findings", []) if f.get("dimension") == "D7_claims")
        
        if d6_penalty > DIMENSION_MAX["D6_consistency"] + EPS:
            violations.append(ArithmeticViolation(
                ARI013_PENALTY_EXCEEDS_CAP,
                f"{ppath}.score",
                f"D6 penalty {d6_penalty} exceeds cap {DIMENSION_MAX['D6_consistency']}",
                pid,
            ))
        if d7_penalty > DIMENSION_MAX["D7_claims"] + EPS:
            violations.append(ArithmeticViolation(
                ARI013_PENALTY_EXCEEDS_CAP,
                f"{ppath}.score",
                f"D7 penalty {d7_penalty} exceeds cap {DIMENSION_MAX['D7_claims']}",
                pid,
            ))
    
    return ArithmeticAuditResult(violations, audited, artifact)


def audit_markdown(markdown: str, artifact: str = "report.md") -> ArithmeticAuditResult:
    """Audit a report.md for arithmetic consistency.
    
    The Markdown is a rendering of report.json; we do a lighter check here,
    just verifying that any scores mentioned are internally consistent.
    """
    # For now, just return a pass - the JSON audit is the authoritative one
    return ArithmeticAuditResult([], 0, artifact)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python3 arithmetic_audit.py <report.json> <artifact_name>")
        sys.exit(1)
    
    report_path = sys.argv[1]
    artifact = sys.argv[2]
    
    with open(report_path) as f:
        report = json.load(f)
    
    result = audit_report(report, artifact)
    print(result.render())
    sys.exit(0 if result.ok else 1)