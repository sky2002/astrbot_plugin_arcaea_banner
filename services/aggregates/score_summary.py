from __future__ import annotations

from ...models import ScoreSheetAggregate, ScoreSheetRow
from ..metrics.score_sheet import ScoreSheetService


class CrossGameSummaryService:
    def __init__(self):
        self.score_sheet_service = ScoreSheetService()

    def build(
        self,
        source_rows: list[dict],
        total_max_source_rows: list[dict] | None = None,
    ) -> tuple[list[ScoreSheetRow], ScoreSheetAggregate]:
        rows = self.score_sheet_service.build_rows(source_rows)
        total_max_override = None
        if total_max_source_rows is not None:
            total_max_override = self.score_sheet_service.calc_total_max_value(total_max_source_rows)
        aggregate = self.score_sheet_service.build_aggregate(rows, total_max_override=total_max_override)
        return rows, aggregate
