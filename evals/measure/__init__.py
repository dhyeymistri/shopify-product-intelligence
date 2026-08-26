"""Diagnostic measurement tools. Never imported by ``engine/``.

Nothing here computes a score. `q6a.py` reads a finding ledger the engine
produced and hands it to `evals/audits/arithmetic_audit`, which is the only
implementation of `rubric.md` 6.1 in this repository outside the engine itself.
A second implementation living here would be a second scoring function.
"""
