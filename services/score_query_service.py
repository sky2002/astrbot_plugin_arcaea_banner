from __future__ import annotations

from ..constants import ALLOWED_DIFFICULTIES
from ..db.repositories import ArcaeaRepository
from ..services.aggregates.title_progress import LEGEND_THRESHOLD, SPIRIT_THRESHOLD, TRIBUTE_THRESHOLD
from ..services.metrics.arc import next_grade_gap, score_grade
from ..services.metrics.score_sheet import ScoreSheetService
from .chart_matcher import ChartMatcher


TIER_LABELS = {
    "Spirit": "Spirit 称号",
    "Tribute": "Tribute 称号",
    "Legend": "Legend 称号",
}

MATCH_METHOD_LABELS = {
    "exact": "精确匹配",
    "prefix": "前缀匹配",
    "fuzzy": "模糊匹配",
    "none": "未指定",
}


class ScoreQueryService:
    def __init__(self, repo: ArcaeaRepository, chart_matcher: ChartMatcher):
        self.repo = repo
        self.chart_matcher = chart_matcher
        self.score_sheet_service = ScoreSheetService()

    def build_usage_text(self, detail: str | None = None) -> str:
        lines = [
            "用法：/score <chart_id>",
            "或：/score <难度> <曲名>",
            "例如：/score 123",
            "例如：/score FTR Fracture Ray",
        ]
        if detail:
            lines.append(detail)
        return "\n".join(lines)

    def build_score_text(self, user_key: str, args: str) -> str:
        query = (args or "").strip()
        if not query:
            return self.build_usage_text()

        if query.isdigit():
            return self._build_by_chart_id(user_key, int(query))

        parts = query.split(maxsplit=1)
        if len(parts) < 2:
            return self.build_usage_text()

        difficulty = parts[0].strip().upper()
        song_name = parts[1].strip()
        if difficulty not in ALLOWED_DIFFICULTIES:
            allowed = " | ".join(sorted(ALLOWED_DIFFICULTIES))
            return self.build_usage_text(f"难度仅支持：{allowed}")

        resolution = self.chart_matcher.resolve_chart(song_name_visible=song_name, difficulty=difficulty)
        if resolution.chart is not None:
            return self._build_chart_text(
                user_key=user_key,
                chart=resolution.chart,
                query_name=song_name,
                match_method=resolution.match_method,
            )

        if resolution.candidates:
            return self._build_candidate_text(song_name=song_name, difficulty=difficulty, candidates=resolution.candidates)

        return f"没有找到谱面：{song_name} [{difficulty}]"

    def _build_by_chart_id(self, user_key: str, chart_id: int) -> str:
        chart = self.repo.get_chart_by_id(chart_id)
        if chart is None:
            return f"没有找到 chart_id 为 {chart_id} 的谱面。"
        return self._build_chart_text(user_key=user_key, chart=chart)

    def _build_chart_text(self, user_key: str, chart, query_name: str = "", match_method: str = "") -> str:
        chart_id = int(chart["chart_id"])
        user_row = self.repo.get_user_chart_best_row(user_key, chart_id)

        source_row = {
            "chart_id": chart_id,
            "song_name": str(chart["song_name"]),
            "pack_name": str(chart["pack_name"]),
            "version_group": str(chart["version_group"]),
            "version_text": str(chart["version_text"]),
            "difficulty": str(chart["difficulty"]),
            "level_text": str(chart["level_text"]),
            "constant": float(chart["constant"]),
            "note_count": int(chart["note_count"] or 0),
            "best_score": int(user_row["best_score"] if user_row is not None else 0),
            "play_count": int(user_row["play_count"] if user_row is not None else 0),
        }
        score_row = self.score_sheet_service.build_rows([source_row])[0]
        next_grade, next_gap = next_grade_gap(score_row.best_score)

        spirit_gap = max(0, SPIRIT_THRESHOLD - score_row.full_score_101)
        tribute_gap = max(0, TRIBUTE_THRESHOLD - score_row.full_score_101)
        legend_gap = max(0, LEGEND_THRESHOLD - score_row.best_score)

        lines: list[str] = []
        lines.append("单曲成绩")
        lines.append("")
        lines.append(f"{score_row.song_name} [{score_row.difficulty}]")
        lines.append(
            f"chart_id：{score_row.chart_id} | 等级：{score_row.level_text} | 定数：{score_row.constant:.1f} | 物量：{score_row.note_count}"
        )
        lines.append(f"曲包：{score_row.pack_name} | 版本组：{score_row.version_group}")

        if query_name and query_name != score_row.song_name and match_method:
            method_label = MATCH_METHOD_LABELS.get(match_method, match_method)
            lines.append(f"匹配结果：{query_name} -> {score_row.song_name}（{method_label}）")

        lines.append("")
        if user_row is None:
            lines.append("最佳成绩：未录入")
        else:
            lines.append(f"最佳成绩：{score_row.best_score}")
        lines.append(f"游玩次数：{score_row.play_count}")
        lines.append(f"评级：{score_grade(score_row.best_score)} | {score_row.score_status}")
        if next_grade is None:
            lines.append("已达到 PM。")
        else:
            lines.append(f"距离下一评级 {next_grade}：还差 {next_gap}")

        lines.append("")
        lines.append("分数换算：")
        lines.append(f"- 101 万满分：{score_row.full_score_101}")
        lines.append(f"- p+：{score_row.p_plus}")
        lines.append(f"- 潜力值：{score_row.arc_ptt:.3f}")
        lines.append(f"- mai 奖励分：{score_row.get_value:.3f} | {score_row.max_value:.3f}")
        lines.append(f"- mai：{score_row.mai_value}")
        lines.append(f"- mai+：{score_row.mai_plus_value}")
        lines.append(f"- chu：{score_row.chu_value:.3f}")
        lines.append(f"- rot：{score_row.rot_value:.3f}")
        lines.append(f"- para：{score_row.para_value:.2f}")
        lines.append(f"- 小 p：{score_row.small_p:.4f} | {score_row.small_p_grade}")

        lines.append("")
        lines.append("距离各称号目标：")
        lines.append(self._format_full_score_gap("Spirit", score_row.full_score_101, SPIRIT_THRESHOLD, spirit_gap))
        lines.append(self._format_full_score_gap("Tribute", score_row.full_score_101, TRIBUTE_THRESHOLD, tribute_gap))
        lines.append(self._format_score_gap("Legend", score_row.best_score, LEGEND_THRESHOLD, legend_gap))
        return "\n".join(lines)

    def _build_candidate_text(self, song_name: str, difficulty: str, candidates: list) -> str:
        lines = [f"模糊匹配结果：{song_name} [{difficulty}]", "", "可以尝试使用 /score <chart_id>："]
        for idx, row in enumerate(candidates, start=1):
            lines.append(
                f"- {idx}. {row['song_name']} [{row['difficulty']}] | {row['pack_name']} | chart_id={row['chart_id']}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_full_score_gap(label: str, current: int, target: int, gap: int) -> str:
        tier_label = TIER_LABELS[label]
        if gap <= 0:
            return f"- {tier_label}：已达成（101 万满分={current}）"
        return f"- {tier_label}：还差 {gap}（当前 101 万满分 {current} | 目标 {target}）"

    @staticmethod
    def _format_score_gap(label: str, current: int, target: int, gap: int) -> str:
        tier_label = TIER_LABELS[label]
        if gap <= 0:
            return f"- {tier_label}：已达成（原始分={current}）"
        return f"- {tier_label}：还差 {gap}（当前原始分 {current} | 目标 {target}）"
