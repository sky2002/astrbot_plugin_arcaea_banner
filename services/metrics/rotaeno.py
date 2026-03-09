from __future__ import annotations


def calc_rot_value(constant: float, score_101: int) -> float:
    bonus_a = min(
        3.4,
        max(
            (score_101 - 950_000) / 30_000,
            (score_101 - 980_000) / 20_000 + 1,
            (score_101 - 1_000_000) / 10_000 + 2,
            (score_101 - 1_004_000) / 4_000 + 2.4,
        ),
    )
    bonus_b = max(
        0.0,
        (score_101 - 1_008_000) / 10_000,
        (score_101 - 1_009_000) / 5_000 + 0.1,
    )
    bonus_c = 0.05 if score_101 == 1_010_000 else 0.0
    return float(constant) + bonus_a + bonus_b + bonus_c


def calc_rot_contribution(rot_rank: int, rot_value: float) -> float:
    if rot_value < 0:
        return 0.0
    if rot_rank <= 10:
        base = rot_value * 0.06
    elif rot_rank <= 20:
        base = rot_value * 0.02
    elif rot_rank <= 40:
        base = rot_value * 0.01
    else:
        base = 0.0
    return base * 1.08 * 1.1
