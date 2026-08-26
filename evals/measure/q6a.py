"""Q-6a diagnostic harness -- **measurement infrastructure, not scoring**.

Q-6a asks whether `uncategorized` products end up deflated or flattered in
aggregate once D2's 22 points (`taxonomy.md` 2 rule 3) and
`VARIANT.ATTRIBUTE_COVERAGE`'s 3.0 (D-029) are both removed and the total is
renormalized (`rubric.md` 6.3). **This module does not answer it.** Option 3 is
the standing decision: build and validate the corpus now, and defer the
conclusion until the apparel D2 predicates are implemented and P4 aggregate
scoring exists. Everything printed here is diagnostic.

Three properties keep this a tool rather than a scoring path:

* **It computes nothing.** Every figure comes from
  `audits.arithmetic_audit._compute_expected_score`, which implements
  `rubric.md` 6.1 independently of the engine and is already the corpus's
  arithmetic authority. Re-deriving `raw_earned / raw_max` here would create a
  third implementation, and the one thing worse than two is three.
* **`engine/` never imports it.** Asserted by `test_q6a_harness`.
* **It writes only to `reports/diagnostics/`**, never to `report.json`.

The four baselines (approved, and defined once here so the diagnostic and any
later answer cannot drift apart):

    A   the record as it is: `uncategorized`, current scoring function.
    C0  A with the 3.00 `VARIANT.ATTRIBUTE_COVERAGE` removed by D-029 restored
        to the denominator, earning 0 -- the reading D-029 rejected. Identical
        to A on a single-variant product, where `NA_SINGLE_VARIANT` removes the
        check anyway and D-029 changes nothing.
    C1  the same record under `operator_override="apparel"`. The record is
        byte-identical; only the assigned category differs.
    C2  C1 plus 2.50 earned, the credit `IDENT.PRODUCT_TYPE_OR_CATEGORY` pays
        when a category is actually set. Derived rather than built as twin
        fixtures, and **verified per product** rather than assumed: see
        `verify_c2_invariant`.

What the columns mean, and why they are never added together:

    d_D029          A - C0.  The 3.00 alone. Zero on a single-variant product.
    d_D2_observed   the movement contributed by D2 checks that actually emitted
                    under C1 and therefore carry a maximum in the denominator.
    d_D2_deferred   D2 maximum that is **absent** from the counterfactual
                    denominator because the check deferred. This is a
                    truncation figure, not a delta, and folding it into any of
                    the others would report an implementation gap as a scoring
                    effect. It is reported even once every D2 predicate lands,
                    at which point it should read 0.00.
    d_rest_deferred the same truncation outside D2. Supplying prose defers D4
                    and D5 the same way supplying attributes defers D2, so the
                    remainder's denominator shrinks with density too. Reported
                    for the same reason and kept equally separate.
    d_IDENT         the flat 2.50 between C1 and C2.
    A -> C2         the headline comparison, printed beside its decomposition
                    and never without it.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
EVALS = os.path.join(REPO, "evals")
if EVALS not in sys.path:
    sys.path.insert(0, EVALS)

from audits.arithmetic_audit import _compute_expected_score   # noqa: E402
from engine import normalize, registry                        # noqa: E402
from engine import validate                                   # noqa: E402
from engine.runner import run_product                         # noqa: E402
from engine.sources import PipSource                          # noqa: E402
from engine.taxonomy_data import UNCATEGORIZED                # noqa: E402

STAMP = "diagnostic only — Q-6a deferred under Option 3"

CORPUS = os.path.join(REPO, "evals/fixtures/uncategorized")
OUT_DIR = os.path.join(REPO, "reports/diagnostics")

#: The counterfactual category, fixed by the approved design.
COUNTERFACTUAL = "apparel"

#: The credit `IDENT.PRODUCT_TYPE_OR_CATEGORY` pays once a category is set.
IDENT_CREDIT = 2.50
IDENT_CHECK = "IDENT.PRODUCT_TYPE_OR_CATEGORY"
AC_CHECK = "VARIANT.ATTRIBUTE_COVERAGE"
D2 = "D2_category_attributes"

#: Fail-closed guard (approved requirement 16). A measurement taken against one
#: set of decidable apparel D2 predicates is not comparable with one taken
#: against another, and the difference is invisible in the numbers. The expected
#: set is pinned here with the rubric version it was pinned at; a mismatch is
#: reported, never absorbed.
PINNED_RUBRIC_VERSION = "0.9"
PINNED_DECIDABLE_D2 = (
    "APPAREL.CARE_INSTRUCTIONS",
    "APPAREL.CLOSURE_AND_CONSTRUCTION",
    "APPAREL.COUNTRY_OF_ORIGIN",
    "APPAREL.INTENDED_USE_CONTEXT",
    "APPAREL.MATERIAL_COMPOSITION",
    "APPAREL.SIZE_SYSTEM",
)


def decidable_d2(category=COUNTERFACTUAL):
    # type: (str) -> Tuple[str, ...]
    return tuple(sorted(c.check_id for c in registry.d2_checks_for_category(category)
                        if str(c.satisfaction) != "UNIMPLEMENTED"))


def comparability_guard():
    # type: () -> List[str]
    """Reasons this run is not comparable with the pinned one. Empty is good."""
    problems = []
    from engine import rubric_data as R
    if R.RUBRIC_VERSION != PINNED_RUBRIC_VERSION:
        problems.append(
            "rubric_version is %s, pinned at %s: figures from the two are not "
            "comparable and must not be charted together"
            % (R.RUBRIC_VERSION, PINNED_RUBRIC_VERSION))
    actual = decidable_d2()
    if actual != PINNED_DECIDABLE_D2:
        gained = sorted(set(actual) - set(PINNED_DECIDABLE_D2))
        lost = sorted(set(PINNED_DECIDABLE_D2) - set(actual))
        problems.append(
            "the decidable apparel D2 predicate set changed (gained %s, lost "
            "%s): d_D2_observed and d_D2_deferred move for that reason alone, "
            "so this run is a new baseline and not a continuation"
            % (gained or "nothing", lost or "nothing"))
    return problems


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def corpus():
    # type: () -> List[Tuple[str, str, dict, Any]]
    """(fixture_id, format, npr, source) for every product in the Q-6a corpus."""
    out = []
    for name in sorted(os.listdir(CORPUS)):
        path = os.path.join(CORPUS, name)
        if name.endswith(".pip.json"):
            fid, fmt = name[:-len(".pip.json")], "pip_json"
        elif name.endswith(".csv"):
            fid, fmt = name[:-len(".csv")], "shopify_csv"
        else:
            continue
        result = normalize.normalize_file(path)
        for npr in result.products:
            out.append((fid, fmt, npr, result.source))
    return out


# ---------------------------------------------------------------------------
# the four baselines
# ---------------------------------------------------------------------------
def _normalized(result):
    # type: (Any) -> float
    """`rubric.md` 6.1 steps 3-5, computed by the arithmetic audit and not here."""
    normalized, _penalties, _total, _dims, _grade, _cap = _compute_expected_score(
        result.as_dict())
    return normalized


def _earned_and_max(result):
    # type: (Any) -> Tuple[float, float]
    earned = max_points = 0.0
    for finding in result.findings:
        if finding.status == "NOT_APPLICABLE":
            continue
        if registry.get(finding.check_id) and registry.get(finding.check_id).is_penalty:
            continue
        earned += float(finding.earned)
        max_points += float(finding.max_points)
    return earned, max_points


def _renormalize(earned, max_points):
    # type: (float, float) -> float
    return (earned / max_points * 100.0) if max_points else 0.0


def measure(npr, source):
    # type: (dict, Any) -> Dict[str, Any]
    """Every figure for one product. Computes no score of its own."""
    a_result = run_product(npr, source)
    c1_result = run_product(npr, source, override=COUNTERFACTUAL)

    a_earned, a_max = _earned_and_max(a_result)
    c1_earned, c1_max = _earned_and_max(c1_result)

    multi = len(npr.get("variants") or []) > 1
    ac = [f for f in a_result.findings if f.check_id == AC_CHECK]
    ac_status = ac[0].status if ac else None
    ac_reason = ac[0].detail if ac else None

    # C0: the reading D-029 rejected -- the check keeps its 3.00 and earns 0.
    ac_check = registry.get(AC_CHECK)
    ac_max = float(ac_check.max_points) if ac_check else 0.0
    c0_max = a_max + ac_max if multi else a_max

    # D2 under the counterfactual: what emitted, and what deferred away.
    d2_emitted_max = sum(float(f.max_points) for f in c1_result.findings
                         if f.dimension == D2 and f.status != "NOT_APPLICABLE")
    d2_emitted_earned = sum(float(f.earned) for f in c1_result.findings
                            if f.dimension == D2 and f.status != "NOT_APPLICABLE")
    d2_deferred_max = 0.0
    rest_deferred_max = 0.0
    for entry in c1_result.ledger.deferred:
        check = registry.get(entry["check_id"])
        if check is None or check.is_penalty:
            continue
        if check.dimension == D2:
            d2_deferred_max += float(check.max_points)
        else:
            rest_deferred_max += float(check.max_points)

    a_norm = _normalized(a_result)
    c0_norm = _renormalize(a_earned, c0_max)
    c1_norm = _normalized(c1_result)
    c2_norm = _renormalize(c1_earned + IDENT_CREDIT, c1_max)

    # d_D2_observed isolates the D2 block by removing it from C1 and comparing.
    without_d2 = _renormalize(c1_earned - d2_emitted_earned, c1_max - d2_emitted_max)

    return {
        "product_id": npr.get("product_id"),
        "variants": len(npr.get("variants") or []),
        "multi": multi,
        "assigned": a_result.classification.assigned,
        "ac_status": ac_status,
        "ac_reason": ac_reason,
        "A_earned": a_earned, "A_max": a_max, "A": a_norm,
        "C0": c0_norm, "C1": c1_norm,
        "C2_earned": c1_earned + IDENT_CREDIT, "C2_max": c1_max, "C2": c2_norm,
        "d_D029": a_norm - c0_norm,
        "d_D2_observed": c1_norm - without_d2,
        "d_D2_deferred": d2_deferred_max,
        "d_rest_deferred": rest_deferred_max,
        "d_IDENT": c2_norm - c1_norm,
        "A_to_C2": a_norm - c2_norm,
    }


# ---------------------------------------------------------------------------
# invariants (approved requirement 10)
# ---------------------------------------------------------------------------
def verify_c2_invariant(npr, source):
    # type: (dict, Any) -> Optional[str]
    """C2 = C1 + 2.50 only if the override differs from a real category in
    exactly one scored check. Verified per product rather than assumed, because
    the whole derivation rests on it (approved requirement 8)."""
    import copy
    c1 = run_product(npr, source, override=COUNTERFACTUAL)

    twin = copy.deepcopy(npr)
    twin["identity"]["declared_category"] = {
        "value": "Apparel & Accessories > Clothing",
        "src": "identity.declared_category"}
    twin_source = PipSource(
        {"products": [twin]}, file="<q6a-c2-invariant-probe>")
    tw = run_product(twin, twin_source)
    if tw.classification.assigned != COUNTERFACTUAL:
        return "the twin did not classify as %s" % COUNTERFACTUAL

    def ledger(result):
        return dict((f.check_id, (f.status, str(f.earned), str(f.max_points)))
                    for f in result.findings)

    left, right = ledger(c1), ledger(tw)
    differing = sorted(k for k in set(left) | set(right) if left.get(k) != right.get(k))
    if differing != [IDENT_CHECK]:
        return "override and a real category differ in %s, not only %s" % (
            differing, IDENT_CHECK)
    delta = float(right[IDENT_CHECK][1]) - float(left[IDENT_CHECK][1])
    if abs(delta - IDENT_CREDIT) > 1e-9:
        return "the identity credit is %.2f, not %.2f" % (delta, IDENT_CREDIT)
    if right[IDENT_CHECK][2] != left[IDENT_CHECK][2]:
        return "the identity check's maximum moved, so the denominator is not held"
    return None


def invariants():
    # type: () -> List[str]
    """Everything approved requirement 10 asks the harness to detect."""
    problems = []
    rows = corpus()
    formats = set(fmt for _, fmt, _, _ in rows)
    if len(rows) != 12:
        problems.append("expected 12 products in the Q-6a corpus, found %d" % len(rows))
    if formats != {"pip_json", "shopify_csv"}:
        problems.append("both formats must be represented, found %s" % sorted(formats))

    for fid, fmt, npr, source in rows:
        result = run_product(npr, source)
        if result.classification.assigned != UNCATEGORIZED:
            problems.append("%s: classified %s, not uncategorized"
                            % (fid, result.classification.assigned))
        for error in validate.validate_npr(npr) + validate.validate_provenance(npr, source):
            problems.append("%s: %s %s" % (fid, error.code, error.reason))
        if result.ledger.run_errors:
            problems.append("%s: run errors %s" % (fid, result.ledger.run_errors))

        ac = [f for f in result.findings if f.check_id == AC_CHECK]
        if not ac:
            problems.append("%s: %s emitted nothing" % (fid, AC_CHECK))
        elif ac[0].status != "NOT_APPLICABLE":
            problems.append("%s: %s is %s, not NOT_APPLICABLE" % (fid, AC_CHECK, ac[0].status))
        else:
            multi = len(npr.get("variants") or []) > 1
            reason = ac[0].detail or ""
            wanted = "No category is assigned" if multi else "A single variant is supplied"
            if wanted not in reason:
                problems.append(
                    "%s: %s is removed for the wrong documented reason (%d variant(s)): %r"
                    % (fid, AC_CHECK, len(npr.get("variants") or []), reason))

        if fmt == "pip_json":
            failure = verify_c2_invariant(npr, source)
            if failure:
                problems.append("%s: C2 invariant -- %s" % (fid, failure))
    return problems


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def render():
    # type: () -> str
    from engine import rubric_data as R
    lines = []
    add = lines.append
    add("# Q-6a diagnostic")
    add("")
    add("**%s.**" % STAMP)
    add("")
    add("Q-6a is not answered here and no figure below should be read as an "
        "answer. The apparel D2 predicate set is only partly implemented, so the "
        "counterfactual denominator is truncated by an amount that varies with "
        "attribute density -- the very axis Q-6a turns on. `d_D2_deferred` is "
        "that truncation, reported separately and never folded into a delta.")
    add("")
    add("- rubric_version: `%s`" % R.RUBRIC_VERSION)
    add("- counterfactual category: `%s`" % COUNTERFACTUAL)
    add("- decidable apparel D2 checks: %s"
        % ", ".join("`%s`" % c for c in decidable_d2()))
    add("")

    guard = comparability_guard()
    add("## Comparability guard")
    add("")
    if guard:
        add("**NOT COMPARABLE with the pinned baseline.**")
        add("")
        for problem in guard:
            add("- %s" % problem)
    else:
        add("Comparable with the pinned baseline: rubric version and decidable "
            "apparel D2 predicate set both match.")
    add("")

    problems = invariants()
    add("## Corpus invariants")
    add("")
    if problems:
        add("**%d problem(s):**" % len(problems))
        add("")
        for problem in problems:
            add("- %s" % problem)
    else:
        add("All 12 products: uncategorized, validating clean, both formats "
            "present, `%s` removed for its documented reason, and the C2 "
            "identity-only invariant holding." % AC_CHECK)
    add("")

    add("## Per product")
    add("")
    add("| fixture | fmt | var | A | C0 | C1 | C2 | d_D029 | d_D2_observed | "
        "d_D2_deferred | d_rest_deferred | d_IDENT | A→C2 |")
    add("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: |")
    rows = []
    for fid, fmt, npr, source in corpus():
        row = measure(npr, source)
        row["fixture"], row["format"] = fid, fmt
        rows.append(row)
        add("| `%s` | %s | %d | %.2f | %.2f | %.2f | %.2f | %+.2f | %+.2f | "
            "%.2f | %.2f | %+.2f | %+.2f |"
            % (fid, "C" if fmt == "pip_json" else "A", row["variants"],
               row["A"], row["C0"], row["C1"], row["C2"], row["d_D029"],
               row["d_D2_observed"], row["d_D2_deferred"], row["d_rest_deferred"],
               row["d_IDENT"], row["A_to_C2"]))
    add("")
    add("`d_D2_deferred` and `d_rest_deferred` are denominator **truncation** in "
        "points, not deltas on the 0-100 scale. They are listed beside the deltas "
        "so the reader can see how much of the counterfactual was never observed; "
        "they are never added to anything.")
    add("")

    add("## Aggregate, by format")
    add("")
    add("| format | n | mean A | mean C2 | mean A→C2 | mean d_D029 | "
        "mean d_D2_deferred |")
    add("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for fmt in ("pip_json", "shopify_csv"):
        group = [r for r in rows if r["format"] == fmt]
        if not group:
            continue
        n = len(group)
        add("| %s | %d | %.2f | %.2f | %+.2f | %+.2f | %.2f |"
            % (fmt, n,
               sum(r["A"] for r in group) / n,
               sum(r["C2"] for r in group) / n,
               sum(r["A_to_C2"] for r in group) / n,
               sum(r["d_D029"] for r in group) / n,
               sum(r["d_D2_deferred"] for r in group) / n))
    add("")
    add("These aggregates describe the corpus as it stands at rubric_version "
        "`%s`. They are not a Q-6a result: Option 3 defers that conclusion until "
        "the apparel D2 predicates are implemented and P4 aggregate scoring "
        "exists." % R.RUBRIC_VERSION)
    add("")
    add("_%s_" % STAMP)
    return "\n".join(lines) + "\n"


def write(out_dir=OUT_DIR):
    # type: (str) -> str
    from engine import rubric_data as R
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, "q6a-%s.md" % R.RUBRIC_VERSION)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render())
    return path


if __name__ == "__main__":
    print(write())
