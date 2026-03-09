from __future__ import annotations

import sqlite3

from ..constants import ALLOWED_DIFFICULTIES
from ..db.repositories import ArcaeaRepository
from ..models import ChartResolution
from ..utils.textnorm import compact, is_reasonable_prefix_match, name_match_score, normalize_title


class ChartMatcher:
    def __init__(self, repo: ArcaeaRepository):
        self.repo = repo

    def find_chart_by_alias(self, song_name: str, difficulty: str, pack_name: str = "") -> sqlite3.Row | None:
        difficulty = (difficulty or "").strip().upper()
        target = normalize_title(song_name)

        if not target or difficulty not in ALLOWED_DIFFICULTIES:
            return None

        rows = self.repo.find_alias_rows_by_norm(difficulty=difficulty, alias_norm=target)
        if len(rows) == 1:
            return rows[0]

        if len(rows) > 1 and pack_name:
            pack_target = normalize_title(pack_name)
            filtered = [row for row in rows if normalize_title(row["pack_name"]) == pack_target]
            if len(filtered) == 1:
                return filtered[0]
        return None

    def find_chart(self, song_name: str, difficulty: str, pack_name: str = "") -> sqlite3.Row | None:
        chart = self.find_chart_by_alias(song_name, difficulty, pack_name)
        if chart:
            return chart

        difficulty = (difficulty or "").strip().upper()
        song_name = (song_name or "").strip()
        pack_name = (pack_name or "").strip()

        if not song_name or difficulty not in ALLOWED_DIFFICULTIES:
            return None

        if pack_name:
            rows = self.repo.find_exact_charts(song_name=song_name, difficulty=difficulty, pack_name=pack_name)
            if len(rows) == 1:
                return rows[0]

        rows = self.repo.find_exact_charts(song_name=song_name, difficulty=difficulty)
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            return None

        candidates = self.repo.get_charts_by_difficulty(difficulty)
        target = compact(song_name)

        exact_compact = [row for row in candidates if compact(row["song_name"]) == target]
        if len(exact_compact) == 1:
            return exact_compact[0]
        if len(exact_compact) > 1:
            if pack_name:
                pack_target = compact(pack_name)
                filtered = [row for row in exact_compact if compact(row["pack_name"]) == pack_target]
                if len(filtered) == 1:
                    return filtered[0]
            return None

        prefix_matches = [row for row in candidates if is_reasonable_prefix_match(song_name, row["song_name"])]
        if len(prefix_matches) == 1:
            return prefix_matches[0]
        if len(prefix_matches) > 1 and pack_name:
            pack_target = compact(pack_name)
            filtered = [row for row in prefix_matches if compact(row["pack_name"]) == pack_target]
            if len(filtered) == 1:
                return filtered[0]

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in candidates:
            score = name_match_score(song_name, row["song_name"])
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and scored[0][0] >= 0.93:
            top = scored[0][1]
            same_name_rows = self.repo.find_exact_charts(song_name=top["song_name"], difficulty=difficulty)
            if len(same_name_rows) == 1:
                return top

        return None

    def find_chart_candidates(self, song_name: str, difficulty: str, limit: int = 5) -> list[sqlite3.Row]:
        difficulty = (difficulty or "").strip().upper()
        target = normalize_title(song_name)
        if not target or difficulty not in ALLOWED_DIFFICULTIES:
            return []

        base_rows = self.repo.get_charts_by_difficulty(difficulty)
        alias_rows = self.repo.get_alias_rows_by_difficulty(difficulty)

        scored: dict[int, tuple[float, sqlite3.Row]] = {}
        for row in base_rows:
            score = name_match_score(target, row["song_name"])
            chart_id = int(row["chart_id"])
            old = scored.get(chart_id)
            if old is None or score > old[0]:
                scored[chart_id] = (score, row)

        for row in alias_rows:
            alias_score = name_match_score(target, row["matched_alias_name"]) * float(row["matched_alias_weight"] or 1.0)
            chart_id = int(row["chart_id"])
            old = scored.get(chart_id)
            if old is None or alias_score > old[0]:
                scored[chart_id] = (alias_score, row)

        ranked = sorted(scored.values(), key=lambda item: item[0], reverse=True)
        return [row for _score, row in ranked[:limit]]

    def resolve_chart(self, song_name_visible: str, difficulty: str, song_name_guess: str = "") -> ChartResolution:
        inputs: list[tuple[str, str]] = []
        seen_names: set[str] = set()
        for value, source in ((song_name_visible, "visible"), (song_name_guess, "guess")):
            value = (value or "").strip()
            if not value:
                continue
            norm = normalize_title(value)
            if not norm or norm in seen_names:
                continue
            seen_names.add(norm)
            inputs.append((value, source))

        for name_input, name_source in inputs:
            chart = self.find_chart(name_input, difficulty)
            if chart:
                candidates = self.find_chart_candidates(name_input, difficulty, limit=5)
                normalized_input = normalize_title(name_input)
                normalized_chart = normalize_title(chart["song_name"])
                if normalized_input == normalized_chart:
                    match_method = "exact"
                elif is_reasonable_prefix_match(name_input, chart["song_name"]):
                    match_method = "prefix"
                else:
                    match_method = "fuzzy"

                return ChartResolution(
                    chart=chart,
                    candidates=candidates,
                    match_method=match_method,
                    matched_name=name_input,
                    matched_name_source=name_source,
                )

        merged_candidates: list[sqlite3.Row] = []
        seen_chart_ids: set[int] = set()
        for name_input, _name_source in inputs:
            for row in self.find_chart_candidates(name_input, difficulty, limit=5):
                chart_id = int(row["chart_id"])
                if chart_id in seen_chart_ids:
                    continue
                seen_chart_ids.add(chart_id)
                merged_candidates.append(row)
                if len(merged_candidates) >= 5:
                    break
            if len(merged_candidates) >= 5:
                break

        return ChartResolution(
            chart=None,
            candidates=merged_candidates,
            match_method="none",
            matched_name=song_name_visible or song_name_guess,
            matched_name_source="visible" if song_name_visible else ("guess" if song_name_guess else "none"),
        )
