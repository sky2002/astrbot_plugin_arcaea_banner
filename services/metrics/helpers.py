from __future__ import annotations

import math
from typing import Iterable, Sequence


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def trunc_to(value: float, digits: int) -> float:
    factor = 10 ** digits
    return math.trunc(value * factor) / factor


def stable_desc_ranks(values: Sequence[float | int]) -> list[int]:
    ordered = sorted(range(len(values)), key=lambda idx: (-float(values[idx]), idx))
    ranks = [0] * len(values)
    for rank, idx in enumerate(ordered, start=1):
        ranks[idx] = rank
    return ranks
