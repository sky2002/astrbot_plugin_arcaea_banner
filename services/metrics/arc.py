from __future__ import annotations


def calc_arc_ptt(constant: float, score: int) -> float:
    if not score:
        return 0.0
    return max(
        0.0,
        min(
            2.0,
            max(
                (score - 9_500_000) / 300_000,
                (score - 9_800_000) / 200_000 + 1,
            ),
        ) + float(constant),
    )


def score_grade(score: int) -> str:
    if score >= 10_000_000:
        return "PM"
    if score >= 9_900_000:
        return "EX+"
    if score >= 9_800_000:
        return "EX"
    if score >= 9_500_000:
        return "AA"
    return "<AA"


def next_grade_gap(score: int) -> tuple[str | None, int]:
    milestones = [
        ("AA", 9_500_000),
        ("EX", 9_800_000),
        ("EX+", 9_900_000),
        ("PM", 10_000_000),
    ]
    for label, target in milestones:
        if score < target:
            return label, target - score
    return None, 0
