"""The claim-scope audit -- PRD 12.3 audit 4, AC-I7.

Scans both report artifacts for prohibited ranking/visibility promises.
Per PRD §1.2 and decisions.md D-002, the tool must never claim, imply,
or market that it guarantees, improves, or predicts ranking, citation,
visibility, or recommendation in any AI or search system.

Prohibited claims (and their rationale):
- "AI ranking" / "AI visibility" / "AI citation" -- unprovable external outcome
- "recommended by" / "recommended in" (ChatGPT, Gemini, Google AI, Perplexity, Shopify Catalog, etc.) -- channel outcome
- "appear in" / "show up in" / "surface in" (AI results, recommendations) -- channel outcome
- "rank higher" / "better ranking" / "improve ranking" -- SEO/ranking promise
- "get found" / "be discovered" / "discoverability" -- visibility promise
- "AI-powered discovery" / "AI discovery" -- implies channel benefit
- "optimized for AI" / "AI-optimized" -- implies outcome guarantee
- "LLM citation" / "cited by AI" / "cited by LLM" -- citation promise
- "Shopify Catalog placement" / "Catalog placement" -- specific channel promise
- "agentic storefront" (as a benefit/outcome rather than context) -- channel promise
- "AI readiness" (as a prediction of outcome rather than data quality) -- outcome promise
- "will be recommended" / "will appear" -- future prediction
- "guarantees" / "guarantee" (visibility/ranking/citation) -- guarantee
- "ensures" / "ensure" (visibility/ranking/citation) -- guarantee
- "boosts" / "boost" (visibility/ranking/discovery) -- improvement promise
- "increases" / "increase" (visibility/ranking/discovery) -- improvement promise
- "improves" / "improve" (visibility/ranking/discovery) -- improvement promise
- "maximize" / "maximizes" (visibility/ranking/discovery) -- optimization promise
- "AI channel" (as something we optimize for) -- channel promise
- "conversational commerce" (as an outcome) -- channel promise

Permitted (these are what we DO claim):
- "evaluate whether product information is sufficiently complete, consistent, structured, and useful for AI-powered product discovery and comparison"
- "data quality" / "data completeness" / "data consistency"
- "category-appropriate" / "category-relevant"
- "agent-ready" (as a grade label for DATA QUALITY, not channel outcome)
- "sufficient for comparison" / "supports comparison"
- "structured for machine readability"
- "evidence-backed findings"
- "audit your product data"
- "measure data sufficiency"
- "identify gaps in your product information"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ClaimScopeViolation:
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
class ClaimScopeAuditResult:
    violations: List[ClaimScopeViolation]
    products_audited: int
    artifact: str

    @property
    def ok(self) -> bool:
        return not self.violations

    def codes(self) -> List[str]:
        return [v.code for v in self.violations]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "audit": "claim_scope",
            "artifact": self.artifact,
            "ok": self.ok,
            "products_audited": self.products_audited,
            "violation_count": len(self.violations),
            "violations": [v.as_dict() for v in self.violations],
        }

    def render(self) -> str:
        if self.ok:
            return f"PASS  claim-scope audit: {self.artifact} ({self.products_audited} product(s), 0 violations)"
        lines = [f"FAIL  claim-scope audit: {self.artifact} ({len(self.violations)} violation(s))"]
        for v in self.violations:
            lines.append(f"  [{v.code}] {v.path}")
            lines.append(f"      {v.detail}")
            if v.token:
                lines.append(f"      matched: {v.token}")
        return "\n".join(lines)


# Prohibited claim-scope patterns
CLAIM_PATTERNS = [
    # Direct ranking/visibility promises
    (r"\b(?:AI|artificial intelligence)\s+(?:ranking|visibility|citation|recommendation|discovery|placement)\b", "AI ranking/visibility/citation", "CLM001_AI_RANKING"),
    (r"\b(?:LLM|large language model)\s+(?:ranking|visibility|citation|recommendation|discovery|placement)\b", "LLM ranking/visibility/citation", "CLM001_AI_RANKING"),
    
    # Channel-specific promises
    (r"\brecommended\s+(?:by|in)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|Claude|Bard|Copilot|Bing\s+Chat)\b", "recommended by [channel]", "CLM002_RECOMMENDED_BY"),
    (r"\bappear\s+in\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|Claude|Bard|Copilot|Bing\s+Chat|AI\s+(?:results|recommendations|overviews|search))\b", "appear in [channel]", "CLM003_APPEAR_IN"),
    (r"\bshow\s+up\s+in\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|Claude|Bard|Copilot|Bing\s+Chat|AI\s+(?:results|recommendations|overviews|search))\b", "show up in [channel]", "CLM003_APPEAR_IN"),
    (r"\bsurface\s+in\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|Claude|Bard|Copilot|Bing\s+Chat|AI\s+(?:results|recommendations|overviews|search))\b", "surface in [channel]", "CLM003_APPEAR_IN"),
    (r"\bget\s+found\s+(?:in|on|by)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|Claude|Bard|Copilot|Bing\s+Chat|AI)\b", "get found in [channel]", "CLM003_APPEAR_IN"),
    
    # Ranking improvement promises
    (r"\brank\s+higher\s+(?:in|on)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI|search)\b", "rank higher in [channel]", "CLM004_RANK_HIGHER"),
    (r"\bbetter\s+ranking\s+(?:in|on)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI|search)\b", "better ranking in [channel]", "CLM004_RANK_HIGHER"),
    (r"\bimprove\s+(?:your\s+)?ranking\s+(?:in|on)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI|search)\b", "improve ranking in [channel]", "CLM004_RANK_HIGHER"),
    
    # Discovery/visibility promises
    (r"\b(?:get|be)\s+discovered\s+(?:in|on|by)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI)\b", "be discovered in [channel]", "CLM005_DISCOVERY"),
    (r"\bdiscoverability\s+(?:in|on)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI)\b", "discoverability in [channel]", "CLM005_DISCOVERY"),
    (r"\bvisibility\s+(?:in|on)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI)\b", "visibility in [channel]", "CLM005_DISCOVERY"),
    
    # AI-optimized / AI-readiness as outcome
    (r"\boptimized\s+for\s+(?:AI|LLM|ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog)\b", "optimized for [channel]", "CLM006_OPTIMIZED_FOR"),
    (r"\bAI-optimized\b", "AI-optimized", "CLM006_OPTIMIZED_FOR"),
    (r"\bLLM-optimized\b", "LLM-optimized", "CLM006_OPTIMIZED_FOR"),
    (r"\bAI-readiness\s+(?:score|grade|rating)\b", "AI-readiness score/grade", "CLM007_AI_READINESS"),
    (r"\bAI\s+readiness\s+(?:guarantees?|ensures?|predicts?)\b", "AI readiness guarantees/ensures/predicts", "CLM007_AI_READINESS"),
    
    # Citation promises
    (r"\b(?:LLM|AI)\s+citation\b", "LLM/AI citation", "CLM008_CITATION"),
    (r"\bcited\s+by\s+(?:LLM|AI|ChatGPT|Gemini|Claude)\b", "cited by [channel]", "CLM008_CITATION"),
    
    # Shopify Catalog specific
    (r"\bShopify\s+Catalog\s+placement\b", "Shopify Catalog placement", "CLM009_CATALOG_PLACEMENT"),
    (r"\bCatalog\s+placement\b", "Catalog placement", "CLM009_CATALOG_PLACEMENT"),
    
    # Agentic storefront as outcome
    (r"\bagentic\s+storefront\s+(?:placement|visibility|ranking|recommendation)\b", "agentic storefront outcome", "CLM010_AGENTIC_STOREFRONT"),
    
    # Guarantee/ensure language for channel outcomes
    (r"\bguarantee[sd]?\s+(?:visibility|ranking|citation|recommendation|discovery|placement)\b", "guarantees visibility/ranking/etc", "CLM011_GUARANTEES"),
    (r"\bensure[sd]?\s+(?:visibility|ranking|citation|recommendation|discovery|placement)\b", "ensures visibility/ranking/etc", "CLM011_GUARANTEES"),
    
    # Boost/increase/improve/maximize for channel outcomes
    (r"\bboost[sd]?\s+(?:visibility|ranking|discovery|citation|recommendation)\b", "boosts visibility/ranking/etc", "CLM012_BOOSTS"),
    (r"\bincrease[sd]?\s+(?:visibility|ranking|discovery|citation|recommendation)\b", "increases visibility/ranking/etc", "CLM012_BOOSTS"),
    (r"\bimprove[sd]?\s+(?:visibility|ranking|discovery|citation|recommendation)\b", "improves visibility/ranking/etc", "CLM012_BOOSTS"),
    (r"\bmaximize[sd]?\s+(?:visibility|ranking|discovery|citation|recommendation)\b", "maximizes visibility/ranking/etc", "CLM012_BOOSTS"),
    
    # AI channel optimization
    (r"\bAI\s+channel\s+(?:optimization|performance|results|success)\b", "AI channel optimization/performance", "CLM013_AI_CHANNEL"),
    (r"\bconversational\s+commerce\s+(?:optimization|performance|results|success)\b", "conversational commerce optimization", "CLM013_AI_CHANNEL"),
    
    # Future prediction
    (r"\bwill\s+be\s+(?:recommended|discovered|found|cited|surfaced)\s+(?:in|by)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI|LLM)\b", "will be recommended/discovered in [channel]", "CLM014_WILL_BE"),
    
    # Generic "get your products in front of AI"
    (r"\bget\s+your\s+products\s+(?:in\s+front\s+of|into|onto)\s+(?:ChatGPT|Gemini|Google\s+AI|Perplexity|Shopify\s+Catalog|AI|LLM)\b", "get products into [channel]", "CLM015_GET_INTO"),
]

# Compile all patterns
COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), desc, code) for p, desc, code in CLAIM_PATTERNS]

# Permitted phrases that should never trigger a violation
# These are methodological/explanatory phrases from PRD §1.2 and §10.1
# NOT standard finding language like "Not stated in the supplied data"
PERMITTED_PHRASES = frozenset([
    "evaluate whether product information is sufficiently complete",
    "evaluate whether product information is sufficiently consistent",
    "evaluate whether product information is sufficiently structured",
    "evaluate whether product information is sufficiently useful",
    "for AI-powered product discovery and comparison",
    "for AI powered product discovery and comparison",
    "data quality",
    "data completeness",
    "data consistency",
    "category-appropriate",
    "category-relevant",
    "category specific",
    "agent-ready",
    "agent ready",
    "sufficient for comparison",
    "supports comparison",
    "structured for machine readability",
    "machine readability",
    "evidence-backed findings",
    "evidence backed findings",
    "audit your product data",
    "audit product data",
    "measure data sufficiency",
    "identify gaps in your product information",
    "identify gaps in product information",
    "product information quality",
    "product data quality",
    "completeness",
    "consistency",
    "structured",
    "useful",
    "information quality",
    "sufficiency",
    "the score answers one question",
    "how much of the information",
    "a buyer or an automated agent needs",
    "to evaluate this product",
    "is present",
    "unambiguous",
    "internally consistent",
    "correctly structured",
    "not a prediction",
    "not a ranking",
    "not a quality judgment",
    "we do not claim",
    "we do not promise",
    "we do not guarantee",
    "cannot know",
    "undisclosed",
    "changing",
    "not attributable",
    "third-party",
    "external",
    "channel",
])


def _is_permitted_context(text: str, match_start: int, match_end: int) -> bool:
    """Check if the match is in a permitted context."""
    # Look at surrounding context (150 chars before and after)
    context_start = max(0, match_start - 150)
    context_end = min(len(text), match_end + 150)
    context = text[context_start:context_end].lower()
    
    # Permitted phrases should only apply if they're in a clearly separate 
    # methodological context (e.g., report header, methodology section), 
    # not in standard finding language like "Not stated in the supplied data."
    # Only permit if the permitted phrase appears in the first 200 chars of 
    # the full text (likely a header/methodology) OR is followed by a clear
    # structural boundary (double newline, markdown header, etc.)
    full_text_lower = text.lower()
    for permitted in PERMITTED_PHRASES:
        pos = full_text_lower.find(permitted)
        if pos >= 0:
            # Permitted phrase must be in the first 200 chars (methodology area)
            # OR followed by a structural boundary
            if pos < 200:
                return True
            # Check for structural boundary after the permitted phrase
            after = full_text_lower[pos + len(permitted):pos + len(permitted) + 20]
            if after.startswith(('\n\n', '\n#', '\n##', '\n###', '—', '–')):
                # But only if the match is NOT in the same paragraph
                # Check if there's a double newline between them
                between = full_text_lower[pos + len(permitted):match_start]
                if '\n\n' in between:
                    return True
    
    # Also permit if it's in a clearly negative context (we're saying what we DON'T do)
    # Only match if the negative marker appears BEFORE the match and is clearly 
    # negating the claim-type word (ranking, visibility, etc.)
    # Be more restrictive: the negative marker must be immediately followed by 
    # a claim word, or the construction must be "not a [claim]" / "not an [claim]"
    negative_markers = [
        "do not", "don't", "does not", "doesn't", "never", 
        "prohibited", "forbidden", "must not", "cannot", "can't",
        "will not", "won't", "is not a", "isn't a", "are not",
        "reject", "rejected", "non-goal", "non goal", "out of scope",
        "not ",  # Add "not " but require it to be followed by claim structure
    ]
    for marker in negative_markers:
        marker_pos = full_text_lower.find(marker)
        if marker_pos >= 0 and marker_pos < match_start:
            # Check if the marker is immediately followed by a claim word
            # (within 10 chars, allowing for "a/an/the")
            claim_words = ["ranking", "visibility", "citation", "recommendation", 
                          "discovery", "placement", "optimized", "readiness",
                          "guarantee", "ensure", "boost", "increase", "improve",
                          "maximize", "channel", "appear", "surface", "discovered",
                          "cited", "recommended"]
            # Look at text after the marker
            after_marker = full_text_lower[marker_pos + len(marker):marker_pos + len(marker) + 20]
            for cw in claim_words:
                if cw in after_marker:
                    return True
            # Also check for "not a/an [claim]" pattern
            if marker in ("not ", "never "):
                after_marker2 = full_text_lower[marker_pos + len(marker):marker_pos + len(marker) + 15]
                # Check for "a ranking", "an improvement", "a guarantee", etc.
                if re.search(r'\b(a|an|the)\s+\w*(' + '|'.join(claim_words) + r')\b', after_marker2):
                    return True
    
    return False


def _scan_text(text: str, path: str, product_id: Optional[str], violations: List[ClaimScopeViolation]) -> None:
    """Scan text for prohibited claim-scope patterns."""
    if not text:
        return
    
    for pattern, desc, code in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            if _is_permitted_context(text, match.start(), match.end()):
                continue
            
            token = text[match.start():match.end()]
            
            violations.append(ClaimScopeViolation(
                code,
                path,
                f"Prohibited ranking/visibility claim: '{desc}' (matches {token!r})",
                product_id,
                token=token,
            ))


def _scan_object(obj: Any, path: str, product_id: Optional[str], violations: List[ClaimScopeViolation], visited: Optional[set] = None) -> None:
    """Recursively scan a JSON object for prohibited claim-scope language in string values."""
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


def audit_report(report: Dict[str, Any], artifact: str = "report.json") -> ClaimScopeAuditResult:
    """Audit a report.json for prohibited claim-scope language."""
    violations = []
    products = report.get("products", [])
    audited = 0
    
    for pi, product_report in enumerate(products):
        ppath = f"products[{pi}]"
        pid = product_report.get("product_id")
        
        if pid is None:
            continue
        
        audited += 1
        _scan_object(product_report, ppath, pid, violations)
    
    # Also scan top-level fields
    _scan_object(report, "root", None, violations)
    
    return ClaimScopeAuditResult(violations, audited, artifact)


def audit_markdown(markdown: str, artifact: str = "report.md") -> ClaimScopeAuditResult:
    """Audit a report.md for prohibited claim-scope language."""
    violations = []
    _scan_text(markdown, artifact, None, violations)
    return ClaimScopeAuditResult(violations, 0, artifact)


if __name__ == "__main__":
    import json
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python3 claim_scope_audit.py <report.json> <artifact_name>")
        sys.exit(1)
    
    report_path = sys.argv[1]
    artifact = sys.argv[2]
    
    with open(report_path) as f:
        report = json.load(f)
    
    result = audit_report(report, artifact)
    print(result.render())
    sys.exit(0 if result.ok else 1)