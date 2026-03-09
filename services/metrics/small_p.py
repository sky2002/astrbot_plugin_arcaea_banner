from __future__ import annotations


def calc_small_p(note_count: int, p_plus: int) -> float:
    if note_count <= 0:
        return 0.0
    ratio = p_plus / note_count
    if ratio > 0.9:
        if ratio < 0.995:
            return (ratio - 0.9) / 0.095 * 0.105 + 0.9
        return (ratio - 0.995) + 1.005
    return ratio


def calc_small_p_grade(small_p: float) -> str:
    if small_p < 0.8:
        if small_p < 0.6:
            return "D" if small_p < 0.5 else "C"
        if small_p < 0.7:
            return "B"
        return "BB" if small_p < 0.75 else "BBB"

    if small_p < 0.97:
        if small_p < 0.94:
            return "A" if small_p < 0.9 else "AA"
        return "AAA"

    if small_p < 0.995:
        if small_p < 0.99:
            return "S" if small_p < 0.98 else "S+"
        return "SS"

    if small_p < 1:
        return "SS+"
    if small_p < 1.005:
        return "SSS"
    return "SSS+"
