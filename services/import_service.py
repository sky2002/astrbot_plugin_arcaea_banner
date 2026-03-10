from __future__ import annotations

import re
import sqlite3

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

from ..constants import ALLOWED_DIFFICULTIES, CANCEL_WORDS, CHOOSE_WORDS, CONFIRM_WORDS, FINISH_WORDS, SKIP_WORDS
from ..db.repositories import ArcaeaRepository
from ..models import ImportProposal, ImportSession
from ..services.chart_matcher import ChartMatcher
from ..services.metrics.arc import calc_arc_ptt
from ..services.vision_service import VisionService
from ..utils.textnorm import normalize_text_command, normalize_title


class ImportService:
    def __init__(self, repo: ArcaeaRepository, vision_service: VisionService, chart_matcher: ChartMatcher):
        self.repo = repo
        self.vision_service = vision_service
        self.chart_matcher = chart_matcher
        self.confirm_words = {normalize_text_command(word) for word in CONFIRM_WORDS}
        self.skip_words = {normalize_text_command(word) for word in SKIP_WORDS}
        self.choose_words = {normalize_text_command(word) for word in CHOOSE_WORDS}
        self.finish_words = {normalize_text_command(word) for word in FINISH_WORDS}
        self.cancel_words = {normalize_text_command(word) for word in CANCEL_WORDS}

    @staticmethod
    def chart_display_name(chart: sqlite3.Row) -> str:
        song_name = str(chart["song_name"])
        alias_name = str(chart["matched_alias_name"] or "").strip() if "matched_alias_name" in chart.keys() else ""
        if alias_name and normalize_title(alias_name) != normalize_title(song_name):
            return f"{song_name}（{alias_name}）"
        return song_name

    @classmethod
    def format_chart_line(cls, chart: sqlite3.Row) -> str:
        note_suffix = f" | 物量 {int(chart['note_count'])}" if "note_count" in chart.keys() and chart["note_count"] is not None else ""
        return (
            f"{cls.chart_display_name(chart)} [{chart['difficulty']}] | {chart['pack_name']} | "
            f"定数 {chart['constant']}{note_suffix}"
        )

    @staticmethod
    def summarize_session(session: ImportSession) -> str:
        pending = 1 if session.current else 0
        return (
            f"本次导入结束：已录入 {session.saved} 张，"
            f"跳过 {session.skipped} 张，失败 {session.failed} 张，"
            f"未处理 {pending} 张。"
        )

    async def build_import_proposal(self, event: AstrMessageEvent, image_input: str) -> tuple[ImportProposal | None, str | None]:
        try:
            recognized = await self.vision_service.recognize_single_result(event, image_input)
            logger.info(f"[arcaea] recognized = {recognized}")

            if (
                not (recognized.song_name_visible or recognized.song_name_guess)
                or recognized.difficulty not in ALLOWED_DIFFICULTIES
                or recognized.score <= 0
                or recognized.note_count <= 0
            ):
                return None, "识别失败：未能得到有效的曲名/难度/分数/物量。"

            resolved = self.chart_matcher.resolve_chart(
                song_name_visible=recognized.song_name_visible,
                difficulty=recognized.difficulty,
                song_name_guess=recognized.song_name_guess,
                note_count=recognized.note_count,
            )

            proposal = ImportProposal(
                recognized=recognized,
                chart=resolved.chart,
                selected_chart=resolved.chart,
                candidates=resolved.candidates,
                match_method=resolved.match_method,
                matched_name=resolved.matched_name,
                matched_name_source=resolved.matched_name_source,
                used_note_count=resolved.used_note_count,
                matched_note_count=resolved.matched_note_count,
                force_choose=resolved.chart is None,
            )
            return proposal, None
        except Exception as exc:
            logger.error(f"[arcaea] build proposal failed: {exc}", exc_info=True)
            return None, f"导入失败：{exc}"

    @classmethod
    def render_candidates(cls, proposal: ImportProposal) -> list[str]:
        lines = ["候选谱面："]
        for idx, row in enumerate(proposal.candidates, start=1):
            lines.append(f"{idx}. {cls.format_chart_line(row)}")
        return lines

    @staticmethod
    def format_match_method(proposal: ImportProposal) -> str:
        method_labels = {
            "exact": "精确匹配",
            "prefix": "前缀匹配",
            "fuzzy": "模糊匹配",
            "note_exact": "物量 + 精确匹配",
            "note_prefix": "物量 + 前缀匹配",
            "note_fuzzy": "物量 + 模糊匹配",
            "note_only": "物量匹配",
            "none": "候选选择",
        }
        return method_labels.get(proposal.match_method, proposal.match_method)

    def render_current_proposal(self, session: ImportSession) -> str:
        proposal = session.current
        if not proposal:
            return "当前没有待确认项目。请发送一张截图，或发送“完成”结束。"

        rec = proposal.recognized
        lines: list[str] = []
        lines.append("待确认导入")
        lines.append(f"识别曲名（可见）：{rec.song_name_visible or '（空）'}")
        if rec.song_name_guess:
            lines.append(f"识别曲名（推测官方名）：{rec.song_name_guess}")
        lines.append(f"识别难度：{rec.difficulty or '（空）'}")
        lines.append(f"识别分数：{rec.score or 0}")
        lines.append(f"识别物量：{rec.note_count or 0}")

        selected = proposal.selected_chart
        if selected and not proposal.force_choose:
            lines.append(f"匹配结果：{self.format_chart_line(selected)}")
            lines.append(f"匹配方式：{self.format_match_method(proposal)}")

            matched_name = proposal.matched_name or ""
            matched_name_source = proposal.matched_name_source
            if matched_name:
                source_text = {"visible": "截图可见标题", "guess": "模型推测官方名"}.get(
                    matched_name_source,
                    matched_name_source,
                )
                basis = f"{source_text} -> {matched_name}"
                if proposal.used_note_count and proposal.matched_note_count > 0:
                    basis += f" | 物量 {proposal.matched_note_count}"
                lines.append(f"匹配依据：{basis}")
            elif proposal.used_note_count and proposal.matched_note_count > 0:
                lines.append(f"匹配依据：物量 {proposal.matched_note_count}")

            lines.append("回复“确认”录入，“候选”查看候选，“跳过”忽略，或发送“完成”结束本次导入。")
            return "\n".join(lines)

        if proposal.candidates:
            lines.extend(self.render_candidates(proposal))
            if proposal.used_note_count and proposal.matched_note_count > 0:
                lines.append(f"已使用物量 {proposal.matched_note_count} 参与匹配。")
                lines.append("物量匹配后仍有多个结果，已返回全部候选。回复候选序号将直接录入，或回复“跳过”“完成”。")
            else:
                lines.append("未自动确定谱面。回复候选序号将直接录入，或回复“跳过”“完成”。")
        else:
            lines.append("没有找到可用候选。请回复“跳过”，或重新发送更清晰的单张截图。")
        return "\n".join(lines)

    def commit_selected_proposal(self, user_key: str, sender_id: str, session: ImportSession) -> str:
        proposal = session.current
        if not proposal:
            return "当前没有待确认项目。"

        chart = proposal.selected_chart or proposal.chart
        if not chart:
            return "当前项目还没有选定谱面，请先选择候选序号。"

        score = int(proposal.recognized.score)
        result = self.repo.upsert_score(user_key=user_key, sender_id=sender_id, chart_id=int(chart["chart_id"]), score=score, source="image")
        ptt = calc_arc_ptt(float(chart["constant"]), int(result["new_best"]))

        if result["old_best"] and result["new_best"] > result["old_best"]:
            improved = f"best {result['old_best']} -> {result['new_best']}"
        elif result["old_best"] and result["new_best"] == result["old_best"]:
            improved = f"best 未提升，当前 best {result['new_best']}"
        else:
            improved = "首次录入"

        session.saved += 1
        session.processed += 1
        session.current = None

        lines = [
            f"已录入：{self.chart_display_name(chart)} [{chart['difficulty']}] | {chart['pack_name']}",
            f"分数：{score}（{improved}）",
            f"游玩次数：{result['play_count']} | 定数：{chart['constant']} | PTT：{ptt:.3f}",
        ]
        if "note_count" in chart.keys() and chart["note_count"] is not None:
            lines.append(f"物量：{int(chart['note_count'])}")
        lines.extend([
            "",
            "当前没有待确认项目。可继续发送下一张截图，或发送“完成”结束。",
        ])
        return "\n".join(lines)

    async def append_image_to_session(self, event: AstrMessageEvent, session: ImportSession, image_input: str) -> str:
        if session.current:
            return "当前已有待确认项目。请先回复“确认”“候选”或“跳过”，再发送下一张截图。"

        proposal, notice = await self.build_import_proposal(event, image_input)
        if not proposal:
            session.failed += 1
            session.processed += 1
            return notice or "没有可处理的识别结果。请发送更清晰的结算截图。"

        session.current = proposal
        return self.render_current_proposal(session)

    async def handle_import_text(
        self,
        event: AstrMessageEvent,
        session: ImportSession,
        user_key: str,
        sender_id: str,
    ) -> tuple[str, bool]:
        raw_text = (event.message_str or "").strip()
        cmd = normalize_text_command(raw_text)

        if cmd in self.cancel_words:
            summary = self.summarize_session(session)
            return f"已取消导入。\n{summary}", True

        if cmd in self.finish_words:
            summary = self.summarize_session(session)
            return summary, True

        current = session.current
        if not current:
            return "当前没有待确认项目。请发送一张截图，或发送“完成”结束。", False

        if cmd in self.skip_words:
            session.skipped += 1
            session.processed += 1
            session.current = None
            return "已跳过当前项目。可继续发送下一张截图，或发送“完成”结束。", False

        if cmd in self.choose_words:
            current.force_choose = True
            return self.render_current_proposal(session), False

        if cmd in self.confirm_words:
            if current.selected_chart or current.chart:
                return self.commit_selected_proposal(user_key=user_key, sender_id=sender_id, session=session), False
            current.force_choose = True
            return self.render_current_proposal(session), False

        match = re.fullmatch(r"\d+", cmd)
        if match:
            index = int(cmd)
            candidates = current.candidates
            if 1 <= index <= len(candidates):
                current.selected_chart = candidates[index - 1]
                current.force_choose = False
                return self.commit_selected_proposal(user_key=user_key, sender_id=sender_id, session=session), False
            return f"候选序号无效，请输入 1 到 {len(candidates)} 之间的数字。", False

        return "请回复“确认”“候选”“跳过”“完成”，或直接发送候选序号。", False
