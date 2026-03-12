"""生成各版本称号进度统计文本。"""

from __future__ import annotations

from ..db.repositories import ArcaeaRepository
from ..models import VersionTitleProgress
from .aggregates.title_progress import TitleProgressAggregateService
from .metrics.score_sheet import ScoreSheetService


TIER_LABELS = {
    "spirit": "Spirit",
    "tribute": "Tribute",
    "legend": "Legend",
}

THRESHOLD_HINTS = {
    "spirit": "101 万满分 >= 1000000",
    "tribute": "101 万满分 >= 1007500",
    "legend": "原始分 >= 10000000",
}

PROGRESS_BAR_WIDTH = 10


class VersionTitleService:
    """生成版本称号进度与总览文本。"""
    def __init__(self, repo: ArcaeaRepository):
        """初始化版本称号服务依赖。"""
        self.repo = repo
        self.score_sheet_service = ScoreSheetService()
        self.title_progress_service = TitleProgressAggregateService()

    def build_all_titles_text(self, user_key: str) -> str:
        """生成所有称号在各版本组的总览文本。"""
        rows = self._load_all_chart_rows(user_key)
        if not rows:
            return "曲库为空，无法计算版本称号进度。"

        score_rows = self.score_sheet_service.build_rows(rows)
        version_rows, overall = self.title_progress_service.build(score_rows)
        count_width = max(
            len(self._progress_text(row, tier))
            for row in [*version_rows, overall]
            for tier in TIER_LABELS
        )

        lines: list[str] = ["版本称号进度", ""]
        for index, row in enumerate(version_rows):
            if index > 0:
                lines.append("")
            lines.extend(self._format_overview_row(row, count_width))

        lines.append("")
        lines.extend(self._format_overview_row(overall, count_width, title="全曲库"))
        return "\n".join(lines)

    def build_spirit_text(self, user_key: str) -> str:
        """生成 Spirit 称号进度文本。"""
        return self._build_single_tier_text(user_key=user_key, tier="spirit")

    def build_tribute_text(self, user_key: str) -> str:
        """生成 Tribute 称号进度文本。"""
        return self._build_single_tier_text(user_key=user_key, tier="tribute")

    def build_legend_text(self, user_key: str) -> str:
        """生成 Legend 称号进度文本。"""
        return self._build_single_tier_text(user_key=user_key, tier="legend")

    def _build_single_tier_text(self, user_key: str, tier: str) -> str:
        """生成单个称号在各版本组的进度文本。"""
        rows = self._load_all_chart_rows(user_key)
        if not rows:
            return "曲库为空，无法计算版本称号进度。"

        score_rows = self.score_sheet_service.build_rows(rows)
        version_rows, overall = self.title_progress_service.build(score_rows)

        tier_label = TIER_LABELS[tier]
        threshold_hint = THRESHOLD_HINTS[tier]
        count_width = max(len(self._progress_text(row, tier)) for row in [*version_rows, overall])

        lines: list[str] = [f"版本称号进度 - {tier_label}", "", f"判定条件：{threshold_hint}", ""]
        for row in version_rows:
            lines.append(self._format_single_tier_row(row, tier, count_width))

        lines.append("")
        lines.append(self._format_single_tier_row(overall, tier, count_width, overall=True))
        return "\n".join(lines)

    def _format_overview_row(
        self,
        row: VersionTitleProgress,
        count_width: int,
        title: str | None = None,
    ) -> list[str]:
        """格式化总览模式下单个版本组的一行文本。"""
        lines = [title or row.version_group]
        for tier in ("spirit", "tribute", "legend"):
            lines.append(self._format_tier_progress_line(row, tier, count_width))
        return lines

    def _format_tier_progress_line(self, row: VersionTitleProgress, tier: str, count_width: int) -> str:
        """格式化单个称号的进度说明。"""
        label = TIER_LABELS[tier]
        progress_text = self._progress_text(row, tier)
        bar = self._build_progress_bar(self._done_count(row, tier), row.total)
        return f"{label:<8} {progress_text:>{count_width}}  {bar}"

    def _format_single_tier_row(
        self,
        row: VersionTitleProgress,
        tier: str,
        count_width: int,
        overall: bool = False,
    ) -> str:
        """格式化单称号模式下单个版本组的一行文本。"""
        label = "全曲库" if overall else row.version_group
        progress_text = self._progress_text(row, tier)
        bar = self._build_progress_bar(self._done_count(row, tier), row.total)
        return f"{label}：{progress_text:>{count_width}}  {bar}"

    def _progress_text(self, row: VersionTitleProgress, tier: str) -> str:
        """把完成数和总数转换为统一的进度文本。"""
        return f"{self._done_count(row, tier)} | {row.total}"

    def _done_count(self, row: VersionTitleProgress, tier: str) -> int:
        """计算指定称号在某个版本组中已完成的数量。"""
        if tier == "spirit":
            return row.total - row.spirit_remaining
        if tier == "tribute":
            return row.total - row.tribute_remaining
        return row.total - row.legend_remaining

    def _build_progress_bar(self, done: int, total: int) -> str:
        """根据完成进度生成文本进度条。"""
        if total <= 0:
            filled = 0
        elif done >= total:
            filled = PROGRESS_BAR_WIDTH
        else:
            filled = int(done * PROGRESS_BAR_WIDTH / total)
            if done > 0 and filled == 0:
                filled = 1
        return f"[{'#' * filled}{'.' * (PROGRESS_BAR_WIDTH - filled)}]"

    def _load_all_chart_rows(self, user_key: str) -> list[dict]:
        """加载全曲库及用户成绩数据。"""
        rows = self.repo.get_all_chart_rows_with_user_scores(user_key)
        source_rows: list[dict] = []
        for row in rows:
            source_rows.append(
                {
                    "chart_id": int(row["chart_id"]),
                    "song_name": str(row["song_name"]),
                    "pack_name": str(row["pack_name"]),
                    "version_group": str(row["version_group"]),
                    "version_text": str(row["version_text"]),
                    "difficulty": str(row["difficulty"]),
                    "level_text": str(row["level_text"]),
                    "constant": float(row["constant"]),
                    "note_count": int(row["note_count"] or 0),
                    "best_score": int(row["best_score"] or 0),
                    "play_count": int(row["play_count"] or 0),
                }
            )
        return source_rows
