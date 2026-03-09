from __future__ import annotations


def _mai_plus_base(small_p: float) -> float:
    if small_p > 0.97:
        if small_p > 1:
            return 22.4 if small_p > 1.005 else 21.6
        return 20 + int((small_p - 0.97) / 0.01) * 0.4 + (0.4 if small_p > 0.995 else 0.0)
    if small_p > 0.8:
        if small_p > 0.94:
            return 16.8
        return 15.2 if small_p > 0.9 else 13.6
    if small_p > 0.6:
        if small_p > 0.75:
            return 12.0
        return 11.2 if small_p > 0.7 else 9.6
    return 8.0 if small_p > 0.5 else 5.0


def calc_mai_plus_value(constant: float, small_p: float) -> int:
    return int(float(constant) * 1.34 * _mai_plus_base(small_p) * min(small_p, 1.005))


def calc_mai_plus_contribution(mai_plus_rank: int, mai_plus_value: int) -> int:
    if mai_plus_rank <= 50:
        return int(mai_plus_value)
    return 0
