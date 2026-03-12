"""处理成绩删除流程和确认文案。"""

from __future__ import annotations

from ..constants import ALLOWED_DIFFICULTIES
from ..db.repositories import ArcaeaRepository
from ..models import DeleteConfirmSession, DeleteSession
from .chart_matcher import ChartMatcher


class DeleteScoreService:
    """处理成绩删除的查询、确认和输出文案。"""
    def __init__(self, repo: ArcaeaRepository, chart_matcher: ChartMatcher):
        """初始化删除服务依赖。"""
        self.repo = repo
        self.chart_matcher = chart_matcher

    def build_usage_text(self, detail: str | None = None) -> str:
        """生成删除命令的用法说明。"""
        lines = [
            "用法：/delete_score <难度> <曲名>",
            "例如：/delete_score BYD Testify",
            "也可以：/delete_score 123",
        ]
        if detail:
            lines.append(detail)
        return "\n".join(lines)

    def prepare_delete_by_chart_id(self, user_key: str, chart_id: int) -> tuple[DeleteSession | None, str]:
        """按 chart_id 准备删除确认信息。"""
        chart = self.repo.get_chart_by_id(chart_id)
        if not chart:
            return None, f"未找到 chart_id={chart_id} 对应的谱面。"

        user_row = self.repo.get_user_chart_best_row(user_key, chart_id)
        if not user_row:
            return None, f"你还没有 {chart['song_name']} [{chart['difficulty']}] 的记录。"

        confirm = self._build_confirm_session(user_row)
        return DeleteSession(confirm=confirm), self._format_confirm_text(confirm)

    def prepare_delete_by_name(self, user_key: str, difficulty: str, song_name: str) -> tuple[DeleteSession | None, str]:
        """按难度和曲名准备删除流程。"""
        difficulty = (difficulty or "").strip().upper()
        if difficulty not in ALLOWED_DIFFICULTIES:
            allowed = " | ".join(sorted(ALLOWED_DIFFICULTIES))
            return None, self.build_usage_text(f"难度仅支持：{allowed}")

        resolution = self.chart_matcher.resolve_chart(song_name_visible=song_name, difficulty=difficulty)
        chart = resolution.chart
        if chart:
            direct_session, direct_text = self.prepare_delete_by_chart_id(user_key, int(chart["chart_id"]))
            if direct_session is not None:
                return direct_session, direct_text

        candidate_sessions = self._collect_owned_candidates(user_key, resolution.candidates)
        if len(candidate_sessions) == 1:
            confirm = candidate_sessions[0]
            return DeleteSession(confirm=confirm), self._format_confirm_text(confirm)

        if candidate_sessions:
            session = DeleteSession(candidates=candidate_sessions)
            return session, self._format_candidate_selection_text(song_name, difficulty, candidate_sessions)

        if chart:
            return None, direct_text

        lines = [f"没有找到 {song_name} [{difficulty}] 对应的已录入谱面。"]
        if resolution.candidates:
            lines.append("")
            lines.append("以下是匹配到的谱面候选，但你没有它们的成绩记录：")
            for idx, row in enumerate(resolution.candidates, start=1):
                lines.append(
                    f"- {idx}. {row['song_name']} [{row['difficulty']}] | {row['pack_name']} | chart_id={row['chart_id']}"
                )
        return None, "\n".join(lines)

    def choose_candidate(self, session: DeleteSession, index: int) -> tuple[DeleteConfirmSession | None, str]:
        """在多候选删除场景下确认用户选择的谱面。"""
        candidates = session.candidates
        if not (1 <= index <= len(candidates)):
            return None, f"候选序号无效，请输入 1 到 {len(candidates)} 之间的数字。"

        confirm = candidates[index - 1]
        session.candidates = []
        session.confirm = confirm
        return confirm, self._format_confirm_text(confirm)

    def delete_confirmed(self, user_key: str, chart_id: int) -> str:
        """执行已经确认的删除操作。"""
        return self.delete_by_chart_id(user_key, chart_id)

    def delete_by_chart_id(self, user_key: str, chart_id: int) -> str:
        """直接按 chart_id 删除成绩。"""
        chart = self.repo.get_chart_by_id(chart_id)
        if not chart:
            return f"未找到 chart_id={chart_id} 对应的谱面。"

        user_row = self.repo.get_user_chart_best_row(user_key, chart_id)
        if not user_row:
            return f"你还没有 {chart['song_name']} [{chart['difficulty']}] 的记录。"

        result = self.repo.delete_user_chart(user_key, chart_id)
        return self._format_deleted_text(chart, user_row, result)

    def delete_by_name(self, user_key: str, difficulty: str, song_name: str) -> str:
        """按曲名流程删除成绩，并在需要时返回候选。"""
        session, text = self.prepare_delete_by_name(user_key, difficulty, song_name)
        if session is None:
            return text
        if session.confirm is None:
            return text
        return self.delete_confirmed(user_key, session.confirm.chart_id)

    def _collect_owned_candidates(self, user_key: str, rows) -> list[DeleteConfirmSession]:
        """从候选谱面中过滤出用户实际有成绩的项。"""
        candidates: list[DeleteConfirmSession] = []
        seen_chart_ids: set[int] = set()
        for row in rows:
            chart_id = int(row["chart_id"])
            if chart_id in seen_chart_ids:
                continue
            seen_chart_ids.add(chart_id)
            user_row = self.repo.get_user_chart_best_row(user_key, chart_id)
            if not user_row:
                continue
            candidates.append(self._build_confirm_session(user_row))
        return candidates

    @staticmethod
    def _build_confirm_session(user_row) -> DeleteConfirmSession:
        """把数据库行转换为删除确认会话对象。"""
        return DeleteConfirmSession(
            chart_id=int(user_row["chart_id"]),
            song_name=str(user_row["song_name"]),
            difficulty=str(user_row["difficulty"]),
            pack_name=str(user_row["pack_name"]),
            version_group=str(user_row["version_group"]),
            best_score=int(user_row["best_score"]),
            play_count=int(user_row["play_count"]),
        )

    def _format_candidate_selection_text(
        self,
        song_name: str,
        difficulty: str,
        candidates: list[DeleteConfirmSession],
    ) -> str:
        """生成删除候选列表文本。"""
        lines = [f"匹配到多个已录入候选，请回复序号选择要删除的谱面：", f"目标：{song_name} [{difficulty}]", ""]
        for idx, item in enumerate(candidates, start=1):
            lines.append(
                f"{idx}. {item.song_name} [{item.difficulty}] | {item.version_group} | {item.pack_name} | "
                f"最佳成绩={item.best_score} | 游玩次数={item.play_count} | chart_id={item.chart_id}"
            )
        lines.append("")
        lines.append("回复序号后会进入删除确认，也可以回复“取消”放弃。")
        return "\n".join(lines)

    def _format_confirm_text(self, session: DeleteConfirmSession) -> str:
        """生成删除前的确认提示文本。"""
        return (
            "即将删除以下谱面的成绩记录，请二次确认：\n"
            f"- 谱面：{session.song_name} [{session.difficulty}]\n"
            f"- 版本：{session.version_group} | {session.pack_name}\n"
            f"- 当前最佳成绩：{session.best_score}\n"
            f"- 当前游玩次数：{session.play_count}\n"
            "回复“确认”继续删除，回复“取消”终止操作。"
        )

    def _format_deleted_text(self, chart, user_row, result: dict) -> str:
        """生成删除完成后的结果文本。"""
        return (
            "已删除该谱面的成绩记录。\n"
            f"- 谱面：{chart['song_name']} [{chart['difficulty']}]\n"
            f"- 版本：{chart['version_group']} | {chart['pack_name']}\n"
            f"- 原最佳成绩：{int(user_row['best_score'])}\n"
            f"- 原游玩次数：{int(user_row['play_count'])}\n"
            f"- 删除 best 记录：{int(result.get('best_deleted', 0))}\n"
            f"- 删除历史记录：{int(result.get('history_deleted', 0))}"
        )
