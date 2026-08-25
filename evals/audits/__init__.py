"""Eval-side audits for Shopify Product Intelligence.

These modules verify report artifacts. They are NOT the product's audit engine
(normalizer / checks / scoring), which is phase P2-P3 and is not built yet.
"""

from .fabrication_audit import audit_report as audit_fabrication, audit_markdown as audit_fabrication_markdown
from .arithmetic_audit import audit_report as audit_arithmetic, audit_markdown as audit_arithmetic_markdown
from .negation_audit import audit_report as audit_negation, audit_markdown as audit_negation_markdown
from .claim_scope_audit import audit_report as audit_claim_scope, audit_markdown as audit_claim_scope_markdown

__all__ = [
    "audit_fabrication",
    "audit_fabrication_markdown",
    "audit_arithmetic",
    "audit_arithmetic_markdown",
    "audit_negation",
    "audit_negation_markdown",
    "audit_claim_scope",
    "audit_claim_scope_markdown",
]
