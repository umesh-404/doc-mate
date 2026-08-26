"""Summary quality evaluation harness.

Turns the per-summary grounding signal into a reportable benchmark across the
three axes clinical-summarisation research evaluates on — **faithfulness**
(no hallucination), **completeness** (no omission), **conciseness** (readable in
under a minute, PROJECT.md section 2).

Everything here is deterministic and offline: the scorers are lexical/numeric,
need no LLM provider or network, and therefore produce identical numbers in
stub mode and in provider mode. See :mod:`app.eval.metrics` for the exact
definitions.
"""

from app.eval.metrics import (
    EVAL_METHOD,
    OVERALL_WEIGHTS,
    score_completeness,
    score_conciseness,
    score_faithfulness,
    score_summary,
)

__all__ = [
    "EVAL_METHOD",
    "OVERALL_WEIGHTS",
    "score_completeness",
    "score_conciseness",
    "score_faithfulness",
    "score_summary",
]
