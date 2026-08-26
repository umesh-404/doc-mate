"""Summary quality benchmark — CLI report.

Evaluates every patient's latest generated summary on the three axes the
clinical-summarisation literature uses (faithfulness / completeness /
conciseness) and prints a report. Fully deterministic and offline: no LLM
provider, no network, identical output in stub and provider mode.

Run from the ``backend/`` directory, after migrations + seed::

    python -m scripts.run_eval

Options::

    python -m scripts.run_eval --misses    # also list every missed fact and
                                           # every unsupported summary line
"""

from __future__ import annotations

import argparse
import sys

from app.db.session import get_sessionmaker
from app.eval.runner import aggregate, evaluate_all

_HEADER = (
    f"{'Patient':<28}{'Faith':>8}{'Compl':>8}{'Concis':>8}{'Overall':>9}"
    f"{'Unsup':>7}{'Missed':>8}"
)


def _fmt(value: float | None) -> str:
    return "  n/a" if value is None else f"{value:.2f}"


def _detail_counts(row) -> tuple[int, int]:
    details = row.details or {}
    unsupported = (details.get("faithfulness") or {}).get("unsupported_count", 0)
    missed = (details.get("completeness") or {}).get("missed_count", 0)
    return unsupported, missed


def _print_misses(name: str, row) -> None:
    details = row.details or {}
    unsupported = (details.get("faithfulness") or {}).get("unsupported", [])
    missed = (details.get("completeness") or {}).get("missed", [])
    if not unsupported and not missed:
        return
    print(f"\n  {name}")
    for item in unsupported:
        print(f"    [unsupported] {item.get('text')}")
        print(f"                  reason: {item.get('reason')}")
    for fact in missed:
        value = " ".join(
            str(p) for p in (fact.get("value"), fact.get("unit")) if p
        )
        suffix = f" = {value}" if value else ""
        print(
            f"    [omitted]     {fact.get('kind')}: {fact.get('label')}{suffix}"
            f"  ({fact.get('reason_important')})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark generated patient summaries (deterministic)."
    )
    parser.add_argument(
        "--misses",
        action="store_true",
        help="list every unsupported summary line and every omitted fact",
    )
    args = parser.parse_args()

    session = get_sessionmaker()()
    try:
        results = evaluate_all(session)
    finally:
        session.close()

    agg = aggregate(results)

    print()
    print("Doc-mate summary quality benchmark")
    print(f"method: {agg['method']}  |  summaries evaluated: {agg['summary_count']}")
    print()

    if not results:
        print("No patient has a generated summary yet — nothing to evaluate.")
        print("Generate summaries first (e.g. python -m scripts.seed_demo).")
        return 0

    print(_HEADER)
    print("-" * len(_HEADER))
    for r in results:
        row = r["eval"]
        unsupported, missed = _detail_counts(row)
        name = str(r["patient_name"])[:27]
        print(
            f"{name:<28}{_fmt(row.faithfulness):>8}{_fmt(row.completeness):>8}"
            f"{_fmt(row.conciseness):>8}{_fmt(row.overall):>9}"
            f"{unsupported:>7}{missed:>8}"
        )
    print("-" * len(_HEADER))
    means = agg["means"]
    print(
        f"{'MEAN':<28}{_fmt(means['faithfulness']):>8}"
        f"{_fmt(means['completeness']):>8}{_fmt(means['conciseness']):>8}"
        f"{_fmt(means['overall']):>9}"
        f"{agg['unsupported_item_count']:>7}{agg['missed_fact_count']:>8}"
    )
    print()
    print(
        f"unsupported summary lines (hallucination risk): "
        f"{agg['unsupported_item_count']}"
    )
    print(f"important facts omitted (omission risk):       {agg['missed_fact_count']}")
    print()
    print(
        "Scoring: faithfulness = supported/graded items (lexical + numeric "
        "match vs cited source); completeness = surfaced/important facts "
        "(allergies, conditions, verified meds, abnormal or most-recent labs); "
        "conciseness = covered facts per 100 words, capped at 6/100; "
        "overall = 0.50/0.30/0.20 weighted. Deterministic lexical proxy — not "
        "human or NLI evaluation."
    )

    if args.misses:
        print("\nDetail")
        for r in results:
            _print_misses(str(r["patient_name"]), r["eval"])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
