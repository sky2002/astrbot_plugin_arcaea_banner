"""提供 Chunithm 对应的换算公式。"""

from __future__ import annotations


def calc_chu_value(constant: float, score_101: int) -> float:
    """根据定数和 101 分计算 Chunithm 值。"""
    inner = min(
        2.0,
        max(
            (score_101 - 975_000) / 25_000,
            (score_101 - 1_000_000) / 10_000 + 1,
            (score_101 - 1_005_000) / 5_000 + 1.5,
        ),
    ) + max(0.0, (score_101 - 1_007_500) / 10_000)
    return max(0.0, float(constant) + min(2.15, inner) + 1.0)


def calc_chu_contribution(chu_rank: int, chu_value: float) -> float:
    """根据 Chu 排名计算该谱面的贡献值。"""
    if chu_rank <= 50:
        return chu_value * 1.23 / 50
    return 0.0
