from __future__ import annotations

from ..constants import ALLOWED_DIFFICULTIES
from ..db.repositories import ArcaeaRepository
from ..services.metrics.arc import calc_arc_ptt, next_grade_gap, score_grade


class SummaryService:
    def __init__(self, repo: ArcaeaRepository):
        self.repo = repo

    def build_summary_text(self, user_key: str) -> str:
        rows = self.repo.get_user_chart_rows(user_key)
        if not rows:
            return "你还没有任何成绩记录。\n先发送 /import，然后发一张 Arcaea 结算截图。"

        total_charts = self.repo.get_total_chart_count()
        imported_count = len(rows)
        total_play_count = sum(int(row["play_count"]) for row in rows)
        overall_rate = imported_count / max(1, total_charts) * 100

        enriched: list[dict] = []
        for row in rows:
            best_score = int(row["best_score"])
            ptt = calc_arc_ptt(float(row["constant"]), best_score)
            next_grade, gap = next_grade_gap(best_score)
            enriched.append(
                {
                    "song_name": row["song_name"],
                    "pack_name": row["pack_name"],
                    "version_group": row["version_group"],
                    "version_text": row["version_text"],
                    "difficulty": row["difficulty"],
                    "level_text": row["level_text"],
                    "constant": float(row["constant"]),
                    "note_count": int(row["note_count"] or 0),
                    "best_score": best_score,
                    "play_count": int(row["play_count"]),
                    "ptt": ptt,
                    "grade": score_grade(best_score),
                    "next_grade": next_grade,
                    "gap": gap,
                }
            )

        enriched.sort(key=lambda item: (item["ptt"], item["best_score"]), reverse=True)
        top10 = enriched[:10]
        top30 = enriched[:30]
        top10_sum = sum(item["ptt"] for item in top10)
        next20_sum = sum(item["ptt"] for item in top30[10:])
        arc_max = top10_sum / 20 + next20_sum / 40
        b30_avg = sum(item["ptt"] for item in top30) / max(1, len(top30))
        top10_floor = top10[-1]["ptt"] if top10 else 0.0
        top30_floor = top30[-1]["ptt"] if top30 else 0.0
        total_note_count = sum(item["note_count"] for item in enriched)

        score_bucket_order = ["PM", "EX+", "EX", "AA", "<AA"]
        score_buckets = {key: 0 for key in score_bucket_order}
        for item in enriched:
            score_buckets[item["grade"]] = score_buckets.get(item["grade"], 0) + 1

        difficulty_order = [diff for diff in ["PST", "PRS", "FTR", "ETR", "BYD"] if diff in ALLOWED_DIFFICULTIES]
        difficulty_totals = self.repo.get_chart_counts_by_difficulty()
        difficulty_owned = {difficulty: 0 for difficulty in difficulty_order}
        difficulty_pm = {difficulty: 0 for difficulty in difficulty_order}
        for item in enriched:
            difficulty = item["difficulty"]
            difficulty_owned[difficulty] = difficulty_owned.get(difficulty, 0) + 1
            if item["grade"] == "PM":
                difficulty_pm[difficulty] = difficulty_pm.get(difficulty, 0) + 1

        version_totals = self.repo.get_chart_counts_by_version()
        version_owned: dict[str, int] = {}
        version_pm: dict[str, int] = {}
        for item in enriched:
            version_group = str(item["version_group"])
            version_owned[version_group] = version_owned.get(version_group, 0) + 1
            if item["grade"] == "PM":
                version_pm[version_group] = version_pm.get(version_group, 0) + 1

        next_up = [item for item in enriched if item["next_grade"] and item["gap"] > 0]
        next_up.sort(key=lambda item: (item["gap"], -item["best_score"]))

        lines: list[str] = []
        lines.append("Arcaea 成绩总结")
        lines.append("")
        lines.append(f"已录入谱面：{imported_count}/{total_charts}（{overall_rate:.1f}%）")
        lines.append(f"总游玩次数：{total_play_count}")
        lines.append(f"已录入总物量：{total_note_count}")
        lines.append(f"Best30 平均：{b30_avg:.3f}")
        lines.append(f"Arc Max（按当前已录入计算）：{arc_max:.3f}")
        if len(top30) < 30:
            lines.append(f"当前 B30 未满：{len(top30)}/30")
        lines.append(f"Top10 地板：{top10_floor:.3f}")
        lines.append(f"Top30 地板：{top30_floor:.3f}")

        lines.append("")
        lines.append("按难度完成率（录入/总数，PM）")
        for diff in difficulty_order:
            total = difficulty_totals.get(diff, 0)
            owned = difficulty_owned.get(diff, 0)
            pm = difficulty_pm.get(diff, 0)
            rate = owned / max(1, total) * 100 if total else 0.0
            lines.append(f"- {diff}: {owned}/{total}（{rate:.1f}%），PM {pm}")

        lines.append("")
        lines.append("分数段统计")
        for bucket in score_bucket_order:
            lines.append(f"- {bucket}: {score_buckets.get(bucket, 0)}")

        lines.append("")
        lines.append("版本组完成率（录入/总数，PM）")
        for version_group in sorted(version_totals.keys()):
            owned = version_owned.get(version_group, 0)
            total = version_totals[version_group]
            pm = version_pm.get(version_group, 0)
            rate = owned / max(1, total) * 100 if total else 0.0
            lines.append(f"- {version_group}: {owned}/{total}（{rate:.1f}%），PM {pm}")

        lines.append("")
        lines.append("最接近下一档（Top 10）")
        for idx, item in enumerate(next_up[:10], start=1):
            lines.append(
                f"No.{idx} {item['song_name']} [{item['difficulty']}] 距 {item['next_grade']} 还差 {item['gap']}"
            )
        if not next_up:
            lines.append("- 所有已录入谱面都已 PM。")

        lines.append("")
        lines.append("Top 10 PTT")
        for idx, item in enumerate(top10, start=1):
            lines.append(
                f"No.{idx} {item['song_name']} [{item['difficulty']}] {item['best_score']}  PTT {item['ptt']:.3f}"
            )

        lines.append("")
        lines.append("Top 30 PTT")
        for idx, item in enumerate(top30, start=1):
            lines.append(
                f"No.{idx} {item['song_name']} [{item['difficulty']}] {item['best_score']}  PTT {item['ptt']:.3f}"
            )

        return "\n".join(lines)
