"""组合分数表服务并生成跨游戏汇总所需的数据结构。"""

from __future__ import annotations

from ...models import ScoreSheetAggregate, ScoreSheetRow
from ..metrics.score_sheet import ScoreSheetService


class CrossGameSummaryService:
    """封装跨游戏分数表的构建流程。"""
    def __init__(self):
        """初始化分数表构建服务。"""
        self.score_sheet_service = ScoreSheetService()

    def build(
        self,
        source_rows: list[dict],
        total_max_source_rows: list[dict] | None = None,
    ) -> tuple[list[ScoreSheetRow], ScoreSheetAggregate]:
        """根据原始成绩行生成分数表行和汇总数据。"""
        rows = self.score_sheet_service.build_rows(source_rows)
        total_max_override = None
        if total_max_source_rows is not None:
            total_max_override = self.score_sheet_service.calc_total_max_value(total_max_source_rows)
        aggregate = self.score_sheet_service.build_aggregate(rows, total_max_override=total_max_override)
        return rows, aggregate
