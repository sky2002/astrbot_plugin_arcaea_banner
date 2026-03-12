"""提供分数换算时复用的数值辅助函数。"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def clamp(value: float, lower: float, upper: float) -> float:
    """把数值限制在给定区间内。"""
    return max(lower, min(value, upper))


def trunc_to(value: float, digits: int) -> float:
    """按指定小数位截断浮点数。"""
    factor = 10 ** digits
    return math.trunc(value * factor) / factor


def stable_desc_ranks(values: Sequence[float | int]) -> list[int]:
    """按降序且稳定地为数值列表生成排名。"""
    ordered = sorted(range(len(values)), key=lambda idx: (-float(values[idx]), idx))
    ranks = [0] * len(values)
    for rank, idx in enumerate(ordered, start=1):
        ranks[idx] = rank
    return ranks
