"""根据分数表结果计算各称号仍缺少的谱面列表。"""

from __future__ import annotations

from ...models import MissingChartEntry, MissingChartGroup, ScoreSheetRow
from .title_progress import (
    LEGEND_THRESHOLD,
    SPIRIT_THRESHOLD,
    TRIBUTE_THRESHOLD,
    VERSION_GROUP_ORDER,
)


class TitleMissingAggregateService:
    """根据分数表结果聚合称号缺失谱面。"""
    def build(
        self,
        rows: list[ScoreSheetRow],
        tier: str,
        version_filter: str | None = None,
    ) -> list[MissingChartGroup]:
        """按版本组整理指定称号仍未完成的谱面。"""
        grouped: dict[str, list[MissingChartEntry]] = {}
        normalized_filter = (version_filter or "").strip()

        for row in rows:
            entry = self._build_entry(row, tier)
            if entry is None:
                continue
            if normalized_filter and row.version_group != normalized_filter:
                continue
            grouped.setdefault(row.version_group, []).append(entry)

        ordered_versions = [name for name in VERSION_GROUP_ORDER if name in grouped]
        ordered_versions.extend(sorted(name for name in grouped if name not in VERSION_GROUP_ORDER))

        groups: list[MissingChartGroup] = []
        for version_group in ordered_versions:
            entries = sorted(
                grouped[version_group],
                key=lambda item: (item.remaining_gap, item.song_name.lower(), item.difficulty),
            )
            groups.append(
                MissingChartGroup(
                    version_group=version_group,
                    tier=tier,
                    total_missing=len(entries),
                    entries=entries,
                )
            )
        return groups

    def _build_entry(self, row: ScoreSheetRow, tier: str) -> MissingChartEntry | None:
        """把单条分数表记录转换为缺失谱面条目。"""
        if tier == "spirit":
            target_value = SPIRIT_THRESHOLD
            current_value = row.full_score_101
        elif tier == "tribute":
            target_value = TRIBUTE_THRESHOLD
            current_value = row.full_score_101
        elif tier == "legend":
            target_value = LEGEND_THRESHOLD
            current_value = row.best_score
        else:
            raise ValueError(f"未知 tier: {tier}")

        remaining_gap = max(0, target_value - int(current_value))
        if remaining_gap <= 0:
            return None

        return MissingChartEntry(
            chart_id=row.chart_id,
            song_name=row.song_name,
            difficulty=row.difficulty,
            version_group=row.version_group,
            best_score=row.best_score,
            full_score_101=row.full_score_101,
            remaining_gap=remaining_gap,
            target_value=target_value,
        )
