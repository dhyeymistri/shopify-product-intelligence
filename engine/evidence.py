"""Evidence constructors that verify before they return.

Every constructor here resolves its locator against the **supplied input** and
asserts that the excerpt it is about to record is byte-reproducible there. A
failure raises; the caller drops the finding and logs a run error.

That is the difference between evidence and a claim about evidence. PRD 8.3
rule 4 makes a non-reproducible quote invalid, and `FAB003` exists to catch one
after the fact -- but a report that never contained one is better than a report
that is caught containing one, so the check is done at construction.

Two rules the constructors enforce structurally:

* **Excerpts are sliced from the source, never copied from the NPR.** The NPR's
  value and the input's text agree because P2 proved they do, but proving it
  again at the point of quotation is what makes byte-exactness hold by
  construction rather than by trust.
* **Locators are copied, never composed from parts.** A check hands over the
  `src` the normalizer already validated. Only an explicit character span may
  be composed onto it, and that composition is verified like anything else.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from .findings import (ABSENCE, DERIVED, EXTERNAL_REFERENCE, FIELD_VALUE, QUOTE,
                       Evidence, EvidenceError)


class EvidenceBuilder(object):
    """Builds verified evidence for one product against its own source."""

    def __init__(self, source, product_id):
        # type: (Any, Optional[str]) -> None
        self.source = source
        self.product_id = product_id

    # -- verification ----------------------------------------------------
    def resolve(self, locator):
        # type: (str) -> str
        """The text the input holds at `locator`, or raise."""
        resolution = self.source.resolve(locator, self.product_id)
        if not resolution.ok:
            raise EvidenceError("locator %r does not resolve: %s"
                                % (locator, resolution.error))
        if resolution.text is None:
            raise EvidenceError("locator %r resolves to an absent value" % (locator,))
        return resolution.text

    def _verified(self, type, locator, note=None):
        # type: (str, str, Optional[str]) -> Evidence
        excerpt = self.resolve(locator)
        return Evidence(type, locator=locator, excerpt=excerpt, note=note)

    # -- constructors ----------------------------------------------------
    def field_value(self, candidate, note=None):
        # type: (Any, Optional[str]) -> Evidence
        """The whole value of a structured field (PRD 8.1)."""
        if not candidate.src:
            raise EvidenceError("candidate at %s carries no locator"
                                % candidate.npr_path)
        evidence = self._verified(FIELD_VALUE, candidate.src, note)
        if evidence.excerpt != candidate.value:
            raise EvidenceError(
                "value at %r is %r, but the record holds %r"
                % (candidate.src, evidence.excerpt, candidate.value))
        return evidence

    def quote(self, locator, note=None):
        # type: (str, Optional[str]) -> Evidence
        """A verbatim span of free text, sliced from the source itself."""
        return self._verified(QUOTE, locator, note)

    def span(self, locator, start, end, note=None):
        # type: (str, int, int, Optional[str]) -> Evidence
        """Compose a character span onto an existing locator, then verify it.

        Valid in both locator grammars (PRD 8.2): a span is the final bracket
        group either way.
        """
        return self.quote("%s[%d:%d]" % (locator, start, end), note)

    def absence(self, checked_paths, note=None):
        # type: (Sequence[str], Optional[str]) -> Evidence
        """The evidence *is* the search (PRD 8.1).

        `checked_paths` is the same tuple the check declared and the gatherer
        walked, so it cannot claim to have looked somewhere it did not.
        """
        return Evidence(ABSENCE, checked_paths=tuple(checked_paths), note=note)

    def derived(self, refs, operation):
        # type: (Sequence[str], str) -> Evidence
        """A computed comparison over other evidence (PRD 8.1).

        Requires at least two referenced items and a stated operation; the
        locator is the first referenced item so the reader has an anchor.
        """
        if len(refs) < 2:
            raise EvidenceError("derived evidence references at least two items")
        return Evidence(DERIVED, locator=refs[0],
                        excerpt=self.resolve(refs[0]),
                        note="%s; references: %s" % (operation, ", ".join(refs)))

    def external_reference(self, candidate):
        # type: (Any) -> Evidence
        """A pointer the data *mentions*. Recorded, never fetched (PRD 8.1)."""
        evidence = self.field_value(candidate)
        return Evidence(EXTERNAL_REFERENCE, locator=evidence.locator,
                        excerpt=evidence.excerpt,
                        note="Recorded as mentioned in the supplied data. "
                             "Not fetched and not verified.")
