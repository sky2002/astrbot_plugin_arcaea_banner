"""把原始成绩行转换为跨游戏分数表行和汇总结果。"""

from __future__ import annotations

from ...models import ScoreSheetAggregate, ScoreSheetRow
from .arc import calc_arc_contribution, calc_arc_ptt, calc_get_value, calc_max_value
from .chunithm import calc_chu_contribution, calc_chu_value
from .helpers import stable_desc_ranks, trunc_to
from .maimai import calc_full_score_101, calc_mai_contribution, calc_mai_value, calc_p_plus
from .mai_plus import calc_mai_plus_contribution, calc_mai_plus_value
from .paradigm import calc_para_contribution, calc_para_value
from .rotaeno import calc_rot_contribution, calc_rot_value
from .small_p import calc_small_p, calc_small_p_grade


class ScoreSheetService:
    """负责生成跨游戏分数表的单谱面行和汇总统计。"""
    def build_rows(self, source_rows: list[dict]) -> list[ScoreSheetRow]:
        """把原始成绩记录转换为带换算结果的分数表行。"""
        rows: list[ScoreSheetRow] = []
        ordered_source_rows = sorted(source_rows, key=lambda row: int(row.get("chart_id", 0)))

        for row in ordered_source_rows:
            constant = float(row["constant"])
            best_score = int(row["best_score"])
            note_count = int(row.get("note_count") or 0)
            play_count = int(row.get("play_count") or 0)

            p_plus = calc_p_plus(best_score, note_count)
            full_score_101 = calc_full_score_101(best_score, p_plus, note_count)
            arc_ptt = calc_arc_ptt(constant, best_score)
            get_value = calc_get_value(constant, best_score, p_plus, note_count)
            max_value = calc_max_value(constant)
            mai_value = calc_mai_value(constant, best_score, full_score_101, p_plus, note_count)
            chu_value = calc_chu_value(constant, full_score_101)
            rot_value = calc_rot_value(constant, full_score_101)
            para_value = calc_para_value(constant, full_score_101)
            small_p = calc_small_p(note_count, p_plus)
            small_p_grade = calc_small_p_grade(small_p)
            mai_plus_value = calc_mai_plus_value(constant, small_p)

            score_status = "0"
            if best_score > 0:
                if full_score_101 > 1_000_000:
                    score_status = "Pure Memory" if best_score > 10_000_000 else "Infinity"
                else:
                    score_status = "Clean"

            rows.append(
                ScoreSheetRow(
                    chart_id=int(row["chart_id"]),
                    song_name=str(row["song_name"]),
                    pack_name=str(row["pack_name"]),
                    version_group=str(row["version_group"]),
                    version_text=str(row["version_text"]),
                    difficulty=str(row["difficulty"]),
                    level_text=str(row["level_text"]),
                    constant=constant,
                    note_count=note_count,
                    best_score=best_score,
                    play_count=play_count,
                    full_score_101=full_score_101,
                    p_plus=p_plus,
                    arc_ptt=arc_ptt,
                    get_value=get_value,
                    max_value=max_value,
                    mai_value=mai_value,
                    chu_value=chu_value,
                    rot_value=rot_value,
                    para_value=para_value,
                    score_status=score_status,
                    small_p=small_p,
                    small_p_grade=small_p_grade,
                    mai_plus_value=mai_plus_value,
                )
            )

        self._apply_ranks_and_contributions(rows)
        return rows

    def calc_total_max_value(self, source_rows: list[dict]) -> float:
        """计算给定谱面集合的 MAX 总值。"""
        return sum(calc_max_value(float(row["constant"])) for row in source_rows)

    def build_aggregate(
        self,
        rows: list[ScoreSheetRow],
        total_max_override: float | None = None,
    ) -> ScoreSheetAggregate:
        """根据分数表行生成整体统计结果。"""
        arc_raw_sum = sum(row.arc_contribution for row in rows)
        total_get = sum(row.get_value for row in rows)
        total_max = total_max_override if total_max_override is not None else sum(row.max_value for row in rows)
        get_ratio = min(1.01, (total_get / total_max) * 1.01) if total_max > 0 else 0.0
        mai_base_total = sum(row.mai_contribution for row in rows)
        mai_bonus = int(get_ratio * 2100)
        para_raw_sum = sum(row.para_contribution for row in rows)

        return ScoreSheetAggregate(
            total_play_count=sum(row.play_count for row in rows),
            arc_total=trunc_to(arc_raw_sum, 2),
            arc_raw_sum=arc_raw_sum,
            total_get=total_get,
            total_max=total_max,
            get_ratio=get_ratio,
            mai_base_total=mai_base_total,
            mai_bonus=mai_bonus,
            mai_total=mai_base_total + mai_bonus,
            mai_plus_total=sum(row.mai_plus_contribution for row in rows),
            chu_total=round(sum(row.chu_contribution for row in rows), 2),
            rot_total=round(sum(row.rot_contribution for row in rows), 3),
            para_total=trunc_to(para_raw_sum, 2),
            para_raw_sum=para_raw_sum,
            para_fraction_points=int((para_raw_sum - trunc_to(para_raw_sum, 2)) * 10_000),
        )

    def _apply_ranks_and_contributions(self, rows: list[ScoreSheetRow]):
        """为分数表行补充各游戏排名和贡献值。"""
        if not rows:
            return

        arc_ranks = stable_desc_ranks([row.arc_ptt for row in rows])
        mai_ranks = stable_desc_ranks([row.mai_value for row in rows])
        chu_ranks = stable_desc_ranks([row.chu_value for row in rows])
        rot_ranks = stable_desc_ranks([row.rot_value for row in rows])
        para_ranks = stable_desc_ranks([row.para_value for row in rows])
        mai_plus_ranks = stable_desc_ranks([row.mai_plus_value for row in rows])

        for idx, row in enumerate(rows):
            row.arc_rank = arc_ranks[idx]
            row.arc_contribution = calc_arc_contribution(row.arc_rank, row.arc_ptt)

            row.mai_rank = mai_ranks[idx]
            row.mai_contribution = calc_mai_contribution(row.mai_rank, row.mai_value)

            row.chu_rank = chu_ranks[idx]
            row.chu_contribution = calc_chu_contribution(row.chu_rank, row.chu_value)

            row.rot_rank = rot_ranks[idx]
            row.rot_contribution = calc_rot_contribution(row.rot_rank, row.rot_value)

            row.para_rank = para_ranks[idx]
            row.para_contribution = calc_para_contribution(row.para_rank, row.para_value)

            row.mai_plus_rank = mai_plus_ranks[idx]
            row.mai_plus_contribution = calc_mai_plus_contribution(row.mai_plus_rank, row.mai_plus_value)
