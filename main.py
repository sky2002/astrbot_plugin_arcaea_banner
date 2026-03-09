from __future__ import annotations

import os
import sqlite3

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, register, StarTools
from astrbot.core.star.context import Context
from astrbot.core.utils.session_waiter import SessionController, session_waiter

from .constants import DB_FILENAME, IMPORT_TIMEOUT_SECONDS
from .db.repositories import ArcaeaRepository
from .db.schema import ensure_schema
from .models import ImportSession
from .services.chart_matcher import ChartMatcher
from .services.import_service import ImportService
from .services.summary_service import SummaryService
from .services.vision_service import VisionService
from .utils.event_helpers import extract_image_inputs, get_user_key, safe_sender_id


@register("helloworld", "YourName", "Arcaea 成绩导入与总结", "1.6.0")
class ArcaeaImportPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        self.conn: sqlite3.Connection | None = None
        self.db_path: str = ""
        self.import_sessions: dict[str, ImportSession] = {}

        self.repo: ArcaeaRepository | None = None
        self.vision_service: VisionService | None = None
        self.chart_matcher: ChartMatcher | None = None
        self.import_service: ImportService | None = None
        self.summary_service: SummaryService | None = None

    async def initialize(self):
        data_dir = StarTools.get_data_dir()
        self.db_path = os.path.join(data_dir, DB_FILENAME)

        if not os.path.exists(self.db_path):
            logger.warning(f"[arcaea] 数据库不存在: {self.db_path}")

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

        self.repo = ArcaeaRepository(self.conn)
        self.vision_service = VisionService(self.context)
        self.chart_matcher = ChartMatcher(self.repo)
        self.import_service = ImportService(self.repo, self.vision_service, self.chart_matcher)
        self.summary_service = SummaryService(self.repo)

        logger.info(f"[arcaea] database ready: {self.db_path}")

    async def terminate(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _new_import_session(self) -> ImportSession:
        return ImportSession()

    def _get_import_session(self, event: AstrMessageEvent) -> ImportSession:
        user_key = get_user_key(event)
        if user_key not in self.import_sessions:
            self.import_sessions[user_key] = self._new_import_session()
        return self.import_sessions[user_key]

    def _clear_import_session(self, event: AstrMessageEvent):
        self.import_sessions.pop(get_user_key(event), None)

    @filter.command("import", priority=10)
    async def import_score(self, event: AstrMessageEvent):
        """导入 Arcaea 成绩截图。"""
        assert self.import_service is not None

        try:
            self.import_sessions[get_user_key(event)] = self._new_import_session()

            direct_images = extract_image_inputs(event)
            if len(direct_images) > 1:
                yield event.plain_result("一次只能发送一张 Arcaea 结算截图。请重新发送单张图片。")
            elif len(direct_images) == 1:
                session = self._get_import_session(event)
                result_text = await self.import_service.append_image_to_session(event, session, direct_images[0])
                yield event.plain_result(
                    result_text + "\n\n可继续发送下一张截图，发送“完成”结束，发送“取消”放弃。"
                )
            else:
                yield event.plain_result(
                    "请发送一张 Arcaea 结算截图。\n"
                    "识别后会先确认再录入。\n"
                    "发送“完成”结束，发送“取消”放弃。"
                )

            @session_waiter(timeout=IMPORT_TIMEOUT_SECONDS, record_history_chains=False)
            async def import_waiter(controller: SessionController, next_event: AstrMessageEvent):
                session = self._get_import_session(next_event)
                text = (next_event.message_str or "").strip()
                images = extract_image_inputs(next_event)

                if images:
                    if len(images) > 1:
                        await next_event.send(next_event.plain_result("一次只能发送一张截图。请重新发送单张图片。"))
                        controller.keep(timeout=IMPORT_TIMEOUT_SECONDS, reset_timeout=True)
                        return
                    await next_event.send(next_event.plain_result("正在识别，请稍候..."))
                    result_text = await self.import_service.append_image_to_session(next_event, session, images[0])
                    await next_event.send(next_event.plain_result(result_text))
                    controller.keep(timeout=IMPORT_TIMEOUT_SECONDS, reset_timeout=True)
                    return

                if not text:
                    await next_event.send(next_event.plain_result("请发送截图，或回复“确认”“候选”“跳过”“完成”。"))
                    controller.keep(timeout=IMPORT_TIMEOUT_SECONDS, reset_timeout=True)
                    return

                result_text, should_stop = await self.import_service.handle_import_text(
                    next_event,
                    session,
                    user_key=get_user_key(next_event),
                    sender_id=safe_sender_id(next_event) or get_user_key(next_event),
                )
                await next_event.send(next_event.plain_result(result_text))

                if should_stop:
                    self._clear_import_session(next_event)
                    controller.stop()
                else:
                    controller.keep(timeout=IMPORT_TIMEOUT_SECONDS, reset_timeout=True)

            try:
                await import_waiter(event)
            except TimeoutError:
                session = self._get_import_session(event)
                yield event.plain_result(
                    "等待超时，已退出导入。\n" + self.import_service.summarize_session(session)
                )
                self._clear_import_session(event)
            except Exception as exc:
                logger.error(f"[arcaea] /import error: {exc}", exc_info=True)
                yield event.plain_result(f"导入失败：{exc}")
                self._clear_import_session(event)
            finally:
                event.stop_event()

        except Exception as exc:
            logger.error(f"[arcaea] /import outer error: {exc}", exc_info=True)
            self._clear_import_session(event)
            yield event.plain_result(f"导入失败：{exc}")

    @filter.command("summary", priority=10)
    async def summary(self, event: AstrMessageEvent):
        """查看当前用户的成绩总结。"""
        assert self.summary_service is not None

        try:
            text = self.summary_service.build_summary_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /summary error: {exc}", exc_info=True)
            yield event.plain_result(f"生成总结失败：{exc}")
