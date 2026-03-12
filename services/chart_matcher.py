"""根据曲名、别名和物量信息匹配谱面。"""

from __future__ import annotations

import sqlite3

from ..constants import ALLOWED_DIFFICULTIES
from ..db.repositories import ArcaeaRepository
from ..models import ChartResolution
from ..utils.textnorm import compact, is_reasonable_prefix_match, name_match_score, normalize_title


class ChartMatcher:
    """封装曲名、别名和物量驱动的谱面匹配逻辑。"""
    def __init__(self, repo: ArcaeaRepository):
        """初始化谱面匹配器并绑定数据仓储。"""
        self.repo = repo

    @staticmethod
    def _filter_rows_by_note_count(rows: list[sqlite3.Row], note_count: int = 0) -> list[sqlite3.Row]:
        """按物量过滤候选谱面列表。"""
        if note_count <= 0:
            return list(rows)
        return [row for row in rows if int(row["note_count"] or 0) == note_count]

    @staticmethod
    def _filter_alias_rows_by_chart_ids(alias_rows: list[sqlite3.Row], chart_ids: set[int]) -> list[sqlite3.Row]:
        """把别名候选限制在指定谱面集合内。"""
        return [row for row in alias_rows if int(row["chart_id"]) in chart_ids]

    @staticmethod
    def _sort_rows(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
        """按稳定顺序整理候选谱面列表。"""
        return sorted(
            rows,
            key=lambda row: (
                str(row["song_name"]).lower(),
                str(row["pack_name"]).lower(),
                str(row["difficulty"]).lower(),
                int(row["chart_id"]),
            ),
        )

    def _find_chart_by_alias_in_rows(
        self,
        song_name: str,
        difficulty: str,
        alias_rows: list[sqlite3.Row],
        pack_name: str = "",
    ) -> sqlite3.Row | None:
        """在候选谱面中通过别名匹配目标曲名。"""
        difficulty = (difficulty or "").strip().upper()
        target = normalize_title(song_name)

        if not target or difficulty not in ALLOWED_DIFFICULTIES:
            return None

        rows = [row for row in alias_rows if normalize_title(str(row["matched_alias_name"] or "")) == target]
        if len(rows) == 1:
            return rows[0]

        if len(rows) > 1 and pack_name:
            pack_target = normalize_title(pack_name)
            filtered = [row for row in rows if normalize_title(row["pack_name"]) == pack_target]
            if len(filtered) == 1:
                return filtered[0]
        return None

    def find_chart_by_alias(
        self,
        song_name: str,
        difficulty: str,
        pack_name: str = "",
        note_count: int = 0,
    ) -> sqlite3.Row | None:
        """直接通过别名表为曲名和难度查找谱面。"""
        difficulty = (difficulty or "").strip().upper()
        target = normalize_title(song_name)

        if not target or difficulty not in ALLOWED_DIFFICULTIES:
            return None

        rows = self.repo.find_alias_rows_by_norm(difficulty=difficulty, alias_norm=target)
        rows = self._filter_rows_by_note_count(rows, note_count)
        if len(rows) == 1:
            return rows[0]

        if len(rows) > 1 and pack_name:
            pack_target = normalize_title(pack_name)
            filtered = [row for row in rows if normalize_title(row["pack_name"]) == pack_target]
            if len(filtered) == 1:
                return filtered[0]
        return None

    def _find_chart_in_rows(
        self,
        song_name: str,
        difficulty: str,
        base_rows: list[sqlite3.Row],
        alias_rows: list[sqlite3.Row],
        pack_name: str = "",
    ) -> sqlite3.Row | None:
        """在候选谱面中执行精确、前缀和模糊匹配。"""
        chart = self._find_chart_by_alias_in_rows(song_name, difficulty, alias_rows, pack_name)
        if chart:
            return chart

        difficulty = (difficulty or "").strip().upper()
        song_name = (song_name or "").strip()
        pack_name = (pack_name or "").strip()

        if not song_name or difficulty not in ALLOWED_DIFFICULTIES:
            return None

        if pack_name:
            rows = [row for row in base_rows if row["song_name"] == song_name and row["pack_name"] == pack_name]
            if len(rows) == 1:
                return rows[0]

        rows = [row for row in base_rows if row["song_name"] == song_name]
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            return None

        target = compact(song_name)

        exact_compact = [row for row in base_rows if compact(row["song_name"]) == target]
        if len(exact_compact) == 1:
            return exact_compact[0]
        if len(exact_compact) > 1:
            if pack_name:
                pack_target = compact(pack_name)
                filtered = [row for row in exact_compact if compact(row["pack_name"]) == pack_target]
                if len(filtered) == 1:
                    return filtered[0]
            return None

        prefix_matches = [row for row in base_rows if is_reasonable_prefix_match(song_name, row["song_name"])]
        if len(prefix_matches) == 1:
            return prefix_matches[0]
        if len(prefix_matches) > 1 and pack_name:
            pack_target = compact(pack_name)
            filtered = [row for row in prefix_matches if compact(row["pack_name"]) == pack_target]
            if len(filtered) == 1:
                return filtered[0]

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in base_rows:
            score = name_match_score(song_name, row["song_name"])
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and scored[0][0] >= 0.93:
            top = scored[0][1]
            same_name_rows = [row for row in base_rows if row["song_name"] == top["song_name"]]
            if len(same_name_rows) == 1:
                return top

        return None

    def find_chart(
        self,
        song_name: str,
        difficulty: str,
        pack_name: str = "",
        note_count: int = 0,
    ) -> sqlite3.Row | None:
        """根据曲名、难度和可选物量查找单个谱面。"""
        difficulty = (difficulty or "").strip().upper()
        if difficulty not in ALLOWED_DIFFICULTIES:
            return None

        base_rows = self._filter_rows_by_note_count(self.repo.get_charts_by_difficulty(difficulty), note_count)
        chart_ids = {int(row["chart_id"]) for row in base_rows}
        alias_rows = self._filter_alias_rows_by_chart_ids(self.repo.get_alias_rows_by_difficulty(difficulty), chart_ids)
        return self._find_chart_in_rows(song_name, difficulty, base_rows, alias_rows, pack_name)

    def _find_chart_candidates_in_rows(
        self,
        song_name: str,
        difficulty: str,
        base_rows: list[sqlite3.Row],
        alias_rows: list[sqlite3.Row],
        limit: int | None = 5,
    ) -> list[sqlite3.Row]:
        """在候选谱面中找出可展示的模糊匹配候选。"""
        difficulty = (difficulty or "").strip().upper()
        target = normalize_title(song_name)
        if difficulty not in ALLOWED_DIFFICULTIES:
            return []
        if not target:
            ranked_rows = self._sort_rows(base_rows)
            return ranked_rows if limit is None else ranked_rows[:limit]

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
        rows = [row for _score, row in ranked]
        return rows if limit is None else rows[:limit]

    def find_chart_candidates(
        self,
        song_name: str,
        difficulty: str,
        limit: int | None = 5,
        note_count: int = 0,
    ) -> list[sqlite3.Row]:
        """根据曲名和难度生成候选谱面列表。"""
        difficulty = (difficulty or "").strip().upper()
        if difficulty not in ALLOWED_DIFFICULTIES:
            return []

        base_rows = self._filter_rows_by_note_count(self.repo.get_charts_by_difficulty(difficulty), note_count)
        chart_ids = {int(row["chart_id"]) for row in base_rows}
        alias_rows = self._filter_alias_rows_by_chart_ids(self.repo.get_alias_rows_by_difficulty(difficulty), chart_ids)
        return self._find_chart_candidates_in_rows(song_name, difficulty, base_rows, alias_rows, limit)

    def _resolve_from_inputs(
        self,
        inputs: list[tuple[str, str]],
        difficulty: str,
        base_rows: list[sqlite3.Row],
        alias_rows: list[sqlite3.Row],
        candidate_limit: int | None,
    ) -> ChartResolution:
        """按可见曲名、模型猜测曲名和物量依次尝试解析谱面。"""
        for name_input, name_source in inputs:
            chart = self._find_chart_in_rows(name_input, difficulty, base_rows, alias_rows)
            if chart:
                candidates = self._find_chart_candidates_in_rows(
                    name_input,
                    difficulty,
                    base_rows,
                    alias_rows,
                    limit=candidate_limit,
                )
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
            rows = self._find_chart_candidates_in_rows(
                name_input,
                difficulty,
                base_rows,
                alias_rows,
                limit=candidate_limit,
            )
            for row in rows:
                chart_id = int(row["chart_id"])
                if chart_id in seen_chart_ids:
                    continue
                seen_chart_ids.add(chart_id)
                merged_candidates.append(row)
                if candidate_limit is not None and len(merged_candidates) >= candidate_limit:
                    break
            if candidate_limit is not None and len(merged_candidates) >= candidate_limit:
                break

        return ChartResolution(
            chart=None,
            candidates=merged_candidates,
            match_method="none",
            matched_name=inputs[0][0] if inputs else "",
            matched_name_source=inputs[0][1] if inputs else "none",
        )

    def resolve_chart(
        self,
        song_name_visible: str,
        difficulty: str,
        song_name_guess: str = "",
        note_count: int = 0,
    ) -> ChartResolution:
        """统一返回谱面解析结果、候选和匹配依据。"""
        difficulty = (difficulty or "").strip().upper()
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

        if difficulty not in ALLOWED_DIFFICULTIES:
            return ChartResolution(
                chart=None,
                candidates=[],
                match_method="none",
                matched_name=song_name_visible or song_name_guess,
                matched_name_source="visible" if song_name_visible else ("guess" if song_name_guess else "none"),
            )

        base_rows = self.repo.get_charts_by_difficulty(difficulty)
        alias_rows = self.repo.get_alias_rows_by_difficulty(difficulty)

        title_resolution = self._resolve_from_inputs(inputs, difficulty, base_rows, alias_rows, candidate_limit=5)
        if title_resolution.chart is not None and title_resolution.match_method in {"exact", "prefix"}:
            return title_resolution

        if note_count > 0:
            note_rows = self._filter_rows_by_note_count(base_rows, note_count)
            if note_rows:
                note_chart_ids = {int(row["chart_id"]) for row in note_rows}
                note_alias_rows = self._filter_alias_rows_by_chart_ids(alias_rows, note_chart_ids)
                note_resolution = self._resolve_from_inputs(
                    inputs,
                    difficulty,
                    note_rows,
                    note_alias_rows,
                    candidate_limit=None,
                )
                if note_resolution.chart is not None:
                    note_resolution.used_note_count = True
                    note_resolution.matched_note_count = note_count
                    note_resolution.match_method = f"note_{note_resolution.match_method}"
                    return note_resolution

                if len(note_rows) == 1:
                    only_row = note_rows[0]
                    return ChartResolution(
                        chart=only_row,
                        candidates=[only_row],
                        match_method="note_only",
                        matched_name=inputs[0][0] if inputs else "",
                        matched_name_source=inputs[0][1] if inputs else "none",
                        used_note_count=True,
                        matched_note_count=note_count,
                    )

                note_candidates = note_resolution.candidates or self._sort_rows(note_rows)
                return ChartResolution(
                    chart=None,
                    candidates=note_candidates,
                    match_method="none",
                    matched_name=note_resolution.matched_name,
                    matched_name_source=note_resolution.matched_name_source,
                    used_note_count=True,
                    matched_note_count=note_count,
                )

        return title_resolution
