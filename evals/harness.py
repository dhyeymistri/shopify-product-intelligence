"""Project engine output into the `report.json` shape the audits consume.

`report.json` assembly belongs to P4 (AGENTS.md 6). The audits, however, are
the definition of correctness for engine output and must run against real
engine output from the moment the engine produces findings -- otherwise the
gate is live only for hand-written doubles.

This module is the thin bridge that makes that possible. It is an eval-side
projection, not the report writer: it adds no assertion the ledger does not
already carry, and it deliberately emits **no `score` member**, because this
phase computes no score and a zeroed one would read as a computed result.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from engine import registry  # noqa: E402
from engine.runner import run_product  # noqa: E402
from engine.sources import PipSource  # noqa: E402
from engine.taxonomy_data import TAXONOMY_VERSION  # noqa: E402

REPORT_VERSION = "0.1"


def report_for(results, input_file, input_format="pip_json", run_id=None,
               run_errors=None):
    # type: (List[Any], str, str, Optional[str], Optional[List[dict]]) -> Dict[str, Any]
    """A `report.json` document carrying only what this phase produces."""
    errors = list(run_errors or [])
    for result in results:
        errors.extend(result.ledger.run_errors)
    return {
        "report_version": REPORT_VERSION,
        "run": {
            "run_id": run_id or "phase-p3-1",
            "started_at": None,
            "input": {"file": input_file, "format": input_format,
                      "products_in": len(results),
                      "products_audited": len(results)},
            "rubric_version": registry.REGISTRY_VERSION,
            "taxonomy_version": TAXONOMY_VERSION,
            "run_errors": errors,
        },
        "products": [result.as_dict() for result in results],
    }


def report_for_fixture(path, override=None):
    # type: (str, Optional[str]) -> Dict[str, Any]
    """Normalize a PIP fixture, run every check, and project the result."""
    full = path if os.path.isabs(path) else os.path.join(REPO, path)
    with open(full) as handle:
        document = json.load(handle)
    source = PipSource(document, file=path)
    results = [run_product(npr, source, override)
               for npr in document.get("products", [])]
    return report_for(results, path)


if __name__ == "__main__":  # pragma: no cover - manual inspection aid
    print(json.dumps(report_for_fixture(sys.argv[1]), indent=2))
