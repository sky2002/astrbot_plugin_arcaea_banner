"""生成跨游戏分数表文本报告。"""

from __future__ import annotations

from ..db.repositories import ArcaeaRepository
from ..models import ScoreSheetRow
from .aggregates.score_summary import CrossGameSummaryService


class CrossGameReportService:
    """生成跨游戏分数表文本报告。"""
    def __init__(self, repo: ArcaeaRepository):
        """初始化跨游戏报告服务。"""
        self.repo = repo
        self.cross_game_summary = CrossGameSummaryService()

    def build_cross_game_text(self, user_key: str) -> str:
        """为指定用户生成跨游戏分数表结果文本。"""
        source_rows = self._load_user_rows(user_key)
        if not source_rows:
            return "你还没有任何成绩记录。\n先发送 /import，然后发一张 Arcaea 结算截图。"

        all_chart_rows = self._load_all_chart_rows()
        score_rows, aggregate = self.cross_game_summary.build(source_rows, total_max_source_rows=all_chart_rows)
        imported_count = len(score_rows)
        total_chart_count = self.repo.get_total_chart_count()
        total_note_count = sum(row.note_count for row in score_rows)
        total_play_count = sum(row.play_count for row in score_rows)

        lines: list[str] = []
        lines.append("跨游戏分数表结果")
        lines.append("")
        lines.append(f"说明：以下换算基于当前已录入成绩，共 {imported_count} | {total_chart_count} 张谱面。")
        lines.append(f"总游玩次数：{total_play_count}")
        lines.append(f"已录入总物量：{total_note_count}")
        lines.append("")
        lines.append("总表")
        lines.append(f"- Arc：{aggregate.arc_total:.2f}")
        lines.append(f"- mai：{aggregate.mai_total}（底分 {aggregate.mai_base_total} + 完成度加成 {aggregate.mai_bonus}）")
        lines.append(f"- mai+：{aggregate.mai_plus_total}")
        lines.append(f"- chu：{aggregate.chu_total:.2f}")
        lines.append(f"- rot：{aggregate.rot_total:.3f}")
        lines.append(f"- para：{aggregate.para_total:.2f}（小数余量 {aggregate.para_fraction_points} | 10000）")
        lines.append(f"- GET | MAX：{aggregate.total_get:.3f} | {aggregate.total_max:.3f}")
        lines.append(f"- 完成度倍率：{aggregate.get_ratio:.4f}")

        self._append_top_rows(
            lines,
            "Arc 前 5",
            sorted(score_rows, key=lambda row: (row.arc_ptt, row.best_score), reverse=True)[:5],
            lambda row: f"PTT {row.arc_ptt:.3f}",
        )
        self._append_top_rows(
            lines,
            "mai 前 5",
            sorted(score_rows, key=lambda row: (row.mai_value, row.best_score), reverse=True)[:5],
            lambda row: str(row.mai_value),
        )
        self._append_top_rows(
            lines,
            "mai+ 前 5",
            sorted(score_rows, key=lambda row: (row.mai_plus_value, row.best_score), reverse=True)[:5],
            lambda row: str(row.mai_plus_value),
        )
        self._append_top_rows(
            lines,
            "chu 前 5",
            sorted(score_rows, key=lambda row: (row.chu_value, row.best_score), reverse=True)[:5],
            lambda row: f"{row.chu_value:.3f}",
        )
        self._append_top_rows(
            lines,
            "rot 前 5",
            sorted(score_rows, key=lambda row: (row.rot_value, row.best_score), reverse=True)[:5],
            lambda row: f"{row.rot_value:.3f}",
        )
        self._append_top_rows(
            lines,
            "para 前 5",
            sorted(score_rows, key=lambda row: (row.para_value, row.best_score), reverse=True)[:5],
            lambda row: f"{row.para_value:.3f}",
        )
        self._append_top_rows(
            lines,
            "小 p 前 5",
            sorted(score_rows, key=lambda row: (row.small_p, row.best_score), reverse=True)[:5],
            lambda row: f"{row.small_p:.4f} | {row.small_p_grade}",
        )

        return "\n".join(lines)

    def _append_top_rows(
        self,
        lines: list[str],
        title: str,
        rows: list[ScoreSheetRow],
        value_formatter,
    ):
        """把各游戏 Top 成绩追加到输出文本中。"""
        lines.append("")
        lines.append(title)
        if not rows:
            lines.append("- 暂无数据")
            return
        for idx, row in enumerate(rows, start=1):
            lines.append(f"第 {idx} 名：{row.song_name} [{row.difficulty}] {row.best_score} | {value_formatter(row)}")

    def _load_user_rows(self, user_key: str) -> list[dict]:
        """加载用户已录入成绩并转换为字典结构。"""
        rows = self.repo.get_user_chart_rows(user_key)
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

    def _load_all_chart_rows(self) -> list[dict]:
        """加载全曲库数据供总上限计算使用。"""
        rows = self.repo.get_all_chart_rows()
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
                    "best_score": 0,
                    "play_count": 0,
                }
            )
        return source_rows
