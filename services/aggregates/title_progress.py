"""根据分数表结果统计各版本称号进度。"""

from __future__ import annotations

from ...models import ScoreSheetRow, VersionTitleProgress

VERSION_GROUP_ORDER = [
    "Origin",
    "Origin Plus",
    "Air",
    "Air Plus",
    "Star",
    "Star Plus",
    "Amazon",
]

SPIRIT_THRESHOLD = 1_000_000
TRIBUTE_THRESHOLD = 1_007_500
LEGEND_THRESHOLD = 10_000_000


class TitleProgressAggregateService:
    """统计各版本组在不同称号上的完成进度。"""
    def build(self, rows: list[ScoreSheetRow]) -> tuple[list[VersionTitleProgress], VersionTitleProgress]:
        """汇总全部版本组以及总览进度。"""
        grouped: dict[str, list[ScoreSheetRow]] = {}
        for row in rows:
            grouped.setdefault(str(row.version_group), []).append(row)

        ordered_versions = [name for name in VERSION_GROUP_ORDER if name in grouped]
        ordered_versions.extend(sorted(name for name in grouped if name not in VERSION_GROUP_ORDER))

        progress_rows = [self._build_single(name, grouped[name]) for name in ordered_versions]
        overall = self._build_single("Arcaea", rows)
        return progress_rows, overall

    def _build_single(self, version_group: str, rows: list[ScoreSheetRow]) -> VersionTitleProgress:
        """为单个版本组计算称号剩余数量。"""
        total = len(rows)
        spirit_remaining = sum(1 for row in rows if row.full_score_101 < SPIRIT_THRESHOLD)
        tribute_remaining = sum(1 for row in rows if row.full_score_101 < TRIBUTE_THRESHOLD)
        legend_remaining = sum(1 for row in rows if row.best_score < LEGEND_THRESHOLD)
        return VersionTitleProgress(
            version_group=version_group,
            total=total,
            spirit_remaining=spirit_remaining,
            tribute_remaining=tribute_remaining,
            legend_remaining=legend_remaining,
        )
