from __future__ import annotations


def calc_para_value(constant: float, score_101: int) -> float:
    if score_101 > 1_009_000:
        return float(constant) * 10 + 7 + 3 * ((score_101 - 1_009_000) / 1000) ** 1.35
    if score_101 > 1_000_000:
        return (score_101 - 1_000_000) / 1500 + float(constant) * 10
    penalty = int((1_010_000 - score_101) / 10_000) if score_101 > 950_000 else 6
    return 10 * float(constant) * (score_101 / 1_000_000) ** 1.5 - penalty


def calc_para_contribution(para_rank: int, para_value: float) -> float:
    if para_value < 0:
        return 0.0
    if para_rank <= 50:
        return para_value * 1.18 * 1.25 / 50
    return 0.0
