"""The negation-language audit -- PRD 12.3 audit 3, AC-I5.

Scans both report artifacts for prohibited absence-as-negation phrasing.
Per PRD §9.1 and §7.3, missing information must be reported as UNKNOWN
with the fixed language "Not stated in the supplied data." It must never
be rendered as a negative fact about the product.

Prohibited patterns (and their rationale):
- "does not contain" / "does not have" / "does not include" -- states negation as fact
- "is not" / "isn't" / "are not" / "aren't" (when referring to product attributes) -- negation
- "lacks a" / "lacks an" / "lacks the" -- absence as deficiency
- "no warranty" / "no ingredient" / "no size" / "no color" / "no [attribute]" -- absent ≠ "no"
- "missing [attribute]" (as a statement of fact rather than a finding title) -- "missing" is a judgment
- "without [attribute]" (when asserting the product doesn't have it) -- absence as negation
- "absent [attribute]" (as a product fact) -- same
- "doesn't have" / "don't have" -- colloquial negation
- "is missing" (as product fact) -- same
- "not included" (when stating as product fact) -- negation
- "not present" (as product fact) -- negation
- "fails to provide" / "fails to state" -- implies obligation not met
- "omits" / "omitted" -- implies deliberate exclusion
- "no mention of" (as product fact) -- different from "not found in checked paths"

Permitted (these are how we MUST phrase unknowns):
- "Not stated in the supplied data"
- "Not found in the supplied data"
- "No value was found for"
- "The data does not state"
- "The supplied data does not contain"
- "checked and empty"
- "absence evidence"
- "UNKNOWN" status
- "absence" evidence type
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class NegationViolation:
    code: str
    path: str
    detail: str
    product_id: Optional[str] = None
    token: Optional[str] = None
    severity: str = "blocker"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "product_id": self.product_id,
            "path": self.path,
            "detail": self.detail,
            "token": self.token,
        }


@dataclass
class NegationAuditResult:
    violations: List[NegationViolation]
    products_audited: int
    artifact: str

    @property
    def ok(self) -> bool:
        return not self.violations

    def codes(self) -> List[str]:
        return [v.code for v in self.violations]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "audit": "negation_language",
            "artifact": self.artifact,
            "ok": self.ok,
            "products_audited": self.products_audited,
            "violation_count": len(self.violations),
            "violations": [v.as_dict() for v in self.violations],
        }

    def render(self) -> str:
        if self.ok:
            return f"PASS  negation-language audit: {self.artifact} ({self.products_audited} product(s), 0 violations)"
        lines = [f"FAIL  negation-language audit: {self.artifact} ({len(self.violations)} violation(s))"]
        for v in self.violations:
            lines.append(f"  [{v.code}] {v.path}")
            lines.append(f"      {v.detail}")
            if v.token:
                lines.append(f"      matched: {v.token}")
        return "\n".join(lines)


# Prohibited negation patterns
# Each is a (regex_pattern, description, code) tuple
# Patterns are case-insensitive
NEGATION_PATTERNS = [
    # Direct negation of product attributes
    (r"\bdoes\s+not\s+(?:contain|have|include|feature|offer|provide|support)\b", "does not contain/have/include", "NEG001_DOES_NOT"),
    (r"\bdoesn't\s+(?:contain|have|include|feature|offer|provide|support)\b", "doesn't contain/have/include", "NEG001_DOES_NOT"),
    (r"\bdo\s+not\s+(?:contain|have|include|feature|offer|provide|support)\b", "do not contain/have/include", "NEG001_DOES_NOT"),
    (r"\bdon't\s+(?:contain|have|include|feature|offer|provide|support)\b", "don't contain/have/include", "NEG001_DOES_NOT"),
    
    # "is not" / "are not" / "isn't" / "aren't" with attribute nouns
    (r"\b(?:is|are)\s+not\s+(?:a|an|the|any)?\s*(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "is/are not [attribute]", "NEG002_IS_NOT"),
    (r"\bisn't\s+(?:a|an|the|any)?\s*(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "isn't [attribute]", "NEG002_IS_NOT"),
    (r"\baren't\s+(?:any)?\s*(?:warranty|ingredients|sizes|colors|colours|dimensions|specifications|certifications|compatibilities|materials|measurements|instructions|shades|finishes|models|identifiers|capacities|loads|ratings|standards)\b", "aren't [attributes]", "NEG002_IS_NOT"),
    
    # "lacks a/an/the"
    (r"\blacks\s+(?:a|an|the)\s+(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "lacks a/an/the [attribute]", "NEG003_LACKS"),
    
    # "no [attribute]" as product fact (not as finding title)
    (r"\bno\s+(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "no [attribute]", "NEG004_NO_ATTRIBUTE"),
    
    # "missing [attribute]" as product fact
    (r"\bmissing\s+(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "missing [attribute]", "NEG005_MISSING"),
    
    # "without [attribute]" as product fact
    (r"\bwithout\s+(?:a|an|the|any)?\s*(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "without [attribute]", "NEG006_WITHOUT"),
    
    # "absent [attribute]" as product fact
    (r"\babsent\s+(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "absent [attribute]", "NEG007_ABSENT"),
    
    # "doesn't have" / "don't have"
    (r"\bdoesn't\s+have\s+(?:a|an|the|any)?\s*(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "doesn't have [attribute]", "NEG008_DOESNT_HAVE"),
    (r"\bdon't\s+have\s+(?:any)?\s*(?:warranty|ingredients|sizes|colors|colours|dimensions|specifications|certifications|compatibilities|materials|measurements|instructions|shades|finishes|models|identifiers|capacities|loads|ratings|standards)\b", "don't have [attributes]", "NEG008_DOESNT_HAVE"),
    
    # "is missing" as product fact
    (r"\bis\s+missing\s+(?:a|an|the|any)?\s*(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "is missing [attribute]", "NEG009_IS_MISSING"),
    
    # "not included" / "not present" as product fact
    (r"\bnot\s+included\s+(?:in\s+the\s+)?(?:product|data|description|specifications?)\b", "not included", "NEG010_NOT_INCLUDED"),
    (r"\bnot\s+present\s+(?:in\s+the\s+)?(?:product|data|description|specifications?)\b", "not present", "NEG011_NOT_PRESENT"),
    
    # "fails to provide/state" -- implies obligation
    (r"\bfails\s+to\s+(?:provide|state|specify|include|mention)\b", "fails to provide/state", "NEG012_FAILS_TO"),
    
    # "omits" / "omitted" -- implies deliberate exclusion
    (r"\bomits\s+(?:the\s+)?(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "omits [attribute]", "NEG013_OMITS"),
    (r"\bomitted\s+(?:the\s+)?(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "omitted [attribute]", "NEG013_OMITS"),
    
    # "no mention of" as product fact (different from "not found in checked paths")
    (r"\bno\s+mention\s+of\s+(?:the\s+)?(?:warranty|ingredient|size|color|colour|dimension|specification|certification|compatibility|material|fabric|fit|measurement|care|instruction|shade|finish|model|identifier|capacity|load|rating|standard)\b", "no mention of [attribute]", "NEG014_NO_MENTION"),
]

# Compile all patterns
COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), desc, code) for p, desc, code in NEGATION_PATTERNS]

# Permitted phrases that should never trigger a violation
PERMITTED_PHRASES = frozenset([
    "not stated in the supplied data",
    "not found in the supplied data",
    "no value was found",
    "the data does not state",
    "the supplied data does not contain",
    "checked and empty",
    "absence evidence",
    "status: unknown",
    '"unknown"',
    "'unknown'",
    "absence",
    "checked_paths",
    "not_applicable",
    "not applicable",
    "n/a",
])

# Attribute keywords that, when near negation, are likely violations
ATTRIBUTE_KEYWORDS = frozenset([
    "warranty", "ingredient", "size", "color", "colour", "dimension", "specification",
    "certification", "compatibility", "material", "fabric", "fit", "measurement",
    "care", "instruction", "shade", "finish", "model", "identifier", "capacity",
    "load", "rating", "standard", "composition", "country", "origin", "brand",
    "title", "description", "image", "media", "sku", "barcode", "gtin", "mpn",
    "price", "weight", "battery", "power", "voltage", "wattage", "connectivity",
    "ports", "bluetooth", "wifi", "usb", "hdmi", "waterproof", "water_resistant",
    "hypoallergenic", "organic", "vegan", "fragrance", "scent", "spf", "pao",
    "shelf_life", "expiry", "certifications", "testing", "standards", "compliance",
    "safety", "age", "suitability", "usage", "directions", "actives", "concentration",
    "formulation", "format", "net_content", "volume", "weight", "dimensions",
])


def _is_permitted_context(text: str, match_start: int, match_end: int) -> bool:
    """Check if the match is in a permitted context (e.g., inside a quoted finding title)."""
    # Look at surrounding context (100 chars before and after)
    context_start = max(0, match_start - 100)
    context_end = min(len(text), match_end + 100)
    context = text[context_start:context_end].lower()
    
    for permitted in PERMITTED_PHRASES:
        if permitted in context:
            return True
    
    # Also permit if it's in a finding title that is clearly a status report
    # e.g., "title": "Fabric composition is not stated" is fine
    if "is not stated" in context or "not stated" in context:
        return True
    
    return False


def _scan_text(text: str, path: str, product_id: Optional[str], violations: List[NegationViolation]) -> None:
    """Scan text for prohibited negation patterns."""
    if not text:
        return
    
    for pattern, desc, code in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            if _is_permitted_context(text, match.start(), match.end()):
                continue
            
            # Extract the matched token for reporting
            token = text[match.start():match.end()]
            
            violations.append(NegationViolation(
                code,
                path,
                f"Prohibited negation phrasing: '{desc}' (matches {token!r})",
                product_id,
                token=token,
            ))


def _scan_object(obj: Any, path: str, product_id: Optional[str], violations: List[NegationViolation], visited: Optional[set] = None) -> None:
    """Recursively scan a JSON object for prohibited negation in string values."""
    if visited is None:
        visited = set()
    
    obj_id = id(obj)
    if obj_id in visited:
        return
    visited.add(obj_id)
    
    if isinstance(obj, str):
        _scan_text(obj, path, product_id, violations)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            _scan_object(value, f"{path}.{key}", product_id, violations, visited)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _scan_object(item, f"{path}[{i}]", product_id, violations, visited)


def audit_report(report: Dict[str, Any], artifact: str = "report.json") -> NegationAuditResult:
    """Audit a report.json for prohibited negation language."""
    violations = []
    products = report.get("products", [])
    audited = 0
    
    for pi, product_report in enumerate(products):
        ppath = f"products[{pi}]"
        pid = product_report.get("product_id")
        
        if pid is None:
            continue
        
        audited += 1
        
        # Scan all string fields in the product report
        _scan_object(product_report, ppath, pid, violations)
    
    # Also scan top-level fields (catalog_summary, run, etc.)
    _scan_object(report, "root", None, violations)
    
    return NegationAuditResult(violations, audited, artifact)


def audit_markdown(markdown: str, artifact: str = "report.md") -> NegationAuditResult:
    """Audit a report.md for prohibited negation language."""
    violations = []
    _scan_text(markdown, artifact, None, violations)
    return NegationAuditResult(violations, 0, artifact)


if __name__ == "__main__":
    import json
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python3 negation_audit.py <report.json> <artifact_name>")
        sys.exit(1)
    
    report_path = sys.argv[1]
    artifact = sys.argv[2]
    
    with open(report_path) as f:
        report = json.load(f)
    
    result = audit_report(report, artifact)
    print(result.render())
    sys.exit(0 if result.ok else 1)