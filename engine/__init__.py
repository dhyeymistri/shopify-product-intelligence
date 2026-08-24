"""The product engine.

P2 scope: the deterministic normalizer. Input (PIP JSON / Shopify product CSV)
-> Normalized Product Record (PRD 6.1), with locators that resolve back to the
supplied input (PRD 8.2).

Nothing here infers a product fact. See AGENTS.md 2 and PRD 6.2 rule 4.
"""

from .normalize import (  # noqa: F401
    NPR_VERSION,
    NormalizationResult,
    detect_format,
    normalize_document,
    normalize_file,
)
