"""提供 maimai 指标和 101 分的换算公式。"""

from __future__ import annotations


def calc_p_plus(score: int, note_count: int) -> int:
    """根据原始分和物量反推 p+。"""
    if score <= 0 or note_count <= 0:
        return 0
    step = 5_000_000 / note_count
    return int(score - int(step * int(score / step)))


def calc_full_score_101(score: int, p_plus: int, note_count: int) -> int:
    """把原始分、p+ 和物量换算为 101 分。"""
    if score <= 0 or note_count <= 0:
        return 0
    return int((score - p_plus) / 10 + (p_plus / note_count) * 10000)


def _mai_multiplier(score_101: int) -> float:
    """根据 101 分选择 maimai 使用的倍率。"""
    if score_101 > 1_000_000:
        if score_101 > 1_007_500:
            if score_101 > 1_009_000:
                return 14.0
            return 13.5
        return 12.5 + int((score_101 - 1_000_000) / 2000) / 4
    if score_101 > 970_000:
        return 8.5 + int((score_101 - 970_000) / 10_000)
    if score_101 > 900_000:
        if score_101 > 950_000:
            return 7.5
        if score_101 > 925_000:
            return 7.0
        return 6.0
    if score_101 > 800_000:
        return 5.0
    return 4.0


def calc_mai_value(constant: float, score: int, score_101: int, p_plus: int, note_count: int) -> int:
    """根据定数和成绩计算 maimai 数值。"""
    if score <= 0 or note_count <= 0:
        return 0
    score_bonus = 1.06 if score > 10_000_000 else 1.0
    p_ratio = p_plus / note_count
    return int(
        score_bonus
        * float(constant)
        * (1.2 + p_ratio * 0.05)
        * min(score_101 / 800_000, 1.0)
        * _mai_multiplier(score_101)
    )


def calc_mai_contribution(mai_rank: int, mai_value: int) -> int:
    """根据 mai 排名计算贡献值。"""
    if mai_rank <= 40:
        return int(mai_value)
    return 0
