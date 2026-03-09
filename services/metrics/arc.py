from __future__ import annotations

from .helpers import clamp


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


def calc_get_value(constant: float, score: int, p_plus: int, note_count: int) -> float:
    if score <= 0 or note_count <= 0:
        return 0.0
    return float(constant) * (
        clamp(p_plus / note_count - 0.9, 0.0, 0.095)
        + 28.5 * clamp(score / 10_000_000 - 0.99, 0.0, 0.01)
    )


def calc_max_value(constant: float) -> float:
    return float(constant) * (
        clamp(1.0 - 0.9, 0.0, 0.095)
        + 28.5 * clamp(1.0 - 0.99, 0.0, 0.01)
    )


def calc_arc_contribution(arc_rank: int, arc_ptt: float) -> float:
    if arc_rank <= 10:
        return arc_ptt / 20
    if arc_rank <= 30:
        return arc_ptt / 40
    return 0.0


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
