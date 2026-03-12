"""实现 AstrBot 插件入口，并把各项命令路由到对应服务。"""

from __future__ import annotations

import os
import sqlite3

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, StarTools, register
from astrbot.core.star.context import Context
from astrbot.core.utils.session_waiter import SessionController, session_waiter

from .constants import CANCEL_WORDS, CONFIRM_WORDS, DB_FILENAME, DELETE_CONFIRM_TIMEOUT_SECONDS, IMPORT_TIMEOUT_SECONDS
from .db.repositories import ArcaeaRepository
from .db.schema import ensure_schema
from .models import DeleteSession, ImportSession, TitleMissingSession
from .services.chart_matcher import ChartMatcher
from .services.cross_game_service import CrossGameReportService
from .services.delete_service import DeleteScoreService
from .services.import_service import ImportService
from .services.score_query_service import ScoreQueryService
from .services.summary_service import SummaryService
from .services.title_missing_service import TitleMissingService
from .services.version_title_service import VersionTitleService
from .services.vision_service import VisionService
from .utils.event_helpers import extract_image_inputs, get_event_message_key, get_user_key, safe_sender_id
from .utils.textnorm import normalize_text_command


COMMAND_HELP_ORDER = [
    "help",
    "import",
    "summary",
    "score",
    "scoresheet",
    "title_all",
    "title_spirit",
    "title_tribute",
    "title_legend",
    "title_missing",
    "title_near",
    "delete_score",
]

COMMAND_HELP = {
    "help": {
        "summary": "查看插件全部指令",
        "usage": (
            "用法：/help\n"
            "或：/help <指令名>\n"
            "例如：/help\n"
            "例如：/help score\n"
            "说明：每个指令也支持 /<指令名> --help 查看用法。"
        ),
    },
    "import": {
        "summary": "导入 Arcaea 结算截图",
        "usage": (
            "用法：/import\n"
            "例如：/import\n"
            "说明：发送指令后继续发送 Arcaea 结算截图，按提示确认录入。"
        ),
    },
    "summary": {
        "summary": "查看当前成绩总结",
        "usage": "用法：/summary\n例如：/summary",
    },
    "score": {
        "summary": "查询单曲成绩与换算结果",
        "usage": (
            "用法：/score <chart_id>\n"
            "或：/score <难度> <曲名>\n"
            "例如：/score 123\n"
            "例如：/score FTR Fracture Ray"
        ),
    },
    "scoresheet": {
        "summary": "查看跨游戏成绩表",
        "usage": "用法：/scoresheet\n例如：/scoresheet",
    },
    "title_all": {
        "summary": "查看全部版本称号进度",
        "usage": "用法：/title_all\n例如：/title_all",
    },
    "title_spirit": {
        "summary": "查看全部 Spirit 称号进度",
        "usage": "用法：/title_spirit\n例如：/title_spirit",
    },
    "title_tribute": {
        "summary": "查看全部 Tribute 称号进度",
        "usage": "用法：/title_tribute\n例如：/title_tribute",
    },
    "title_legend": {
        "summary": "查看全部 Legend 称号进度",
        "usage": "用法：/title_legend\n例如：/title_legend",
    },
    "title_missing": {
        "summary": "查看称号未完成曲目清单",
        "usage": (
            "用法：/title_missing <spirit|tribute|legend> [版本组] [显示条数]\n"
            "例如：/title_missing tribute 20\n"
            "例如：/title_missing legend Origin Plus\n"
            "例如：/title_missing legend Origin Plus 20"
        ),
    },
    "title_near": {
        "summary": "查看最接近达成的冲牌建议",
        "usage": (
            "用法：/title_near <spirit|tribute|legend> [版本组] [显示条数]\n"
            "例如：/title_near spirit\n"
            "例如：/title_near tribute Origin 20\n"
            "例如：/title_near legend Origin Plus"
        ),
    },
    "delete_score": {
        "summary": "删除一条已录入成绩",
        "usage": (
            "用法：/delete_score <难度> <曲名>\n"
            "例如：/delete_score BYD Testify\n"
            "也可以：/delete_score 123"
        ),
    },
}


@register("helloworld", "YourName", "Arcaea 成绩导入与总结", "1.8.0")
class ArcaeaImportPlugin(Star):
    """AstrBot 插件主类，负责初始化服务、管理会话并响应命令。"""
    def __init__(self, context: Context):
        """初始化插件依赖、数据库连接和各类会话缓存。"""
        super().__init__(context)
        self.context = context
        self.conn: sqlite3.Connection | None = None
        self.db_path: str = ""
        self.import_sessions: dict[str, ImportSession] = {}
        self.delete_sessions: dict[str, DeleteSession] = {}
        self.title_missing_sessions: dict[str, TitleMissingSession] = {}

        self.repo: ArcaeaRepository | None = None
        self.vision_service: VisionService | None = None
        self.chart_matcher: ChartMatcher | None = None
        self.import_service: ImportService | None = None
        self.score_query_service: ScoreQueryService | None = None
        self.summary_service: SummaryService | None = None
        self.cross_game_service: CrossGameReportService | None = None
        self.version_title_service: VersionTitleService | None = None
        self.title_missing_service: TitleMissingService | None = None
        self.delete_service: DeleteScoreService | None = None

    async def initialize(self):
        """在插件启动时建立数据库并初始化业务服务。"""
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
        self.score_query_service = ScoreQueryService(self.repo, self.chart_matcher)
        self.summary_service = SummaryService(self.repo)
        self.cross_game_service = CrossGameReportService(self.repo)
        self.version_title_service = VersionTitleService(self.repo)
        self.title_missing_service = TitleMissingService(self.repo)
        self.delete_service = DeleteScoreService(self.repo, self.chart_matcher)

        logger.info(f"[arcaea] database ready: {self.db_path}")

    async def terminate(self):
        """在插件卸载时关闭数据库连接。"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _new_import_session(self) -> ImportSession:
        """创建新的导入会话对象。"""
        return ImportSession()

    def _get_import_session(self, event: AstrMessageEvent) -> ImportSession:
        """按当前事件对应的用户获取导入会话。"""
        user_key = get_user_key(event)
        if user_key not in self.import_sessions:
            self.import_sessions[user_key] = self._new_import_session()
        return self.import_sessions[user_key]

    def _clear_import_session(self, event: AstrMessageEvent):
        """清理当前用户的导入会话。"""
        self.import_sessions.pop(get_user_key(event), None)

    def _get_delete_session(self, event: AstrMessageEvent) -> DeleteSession | None:
        """获取当前用户的删除会话。"""
        return self.delete_sessions.get(get_user_key(event))

    def _set_delete_session(self, event: AstrMessageEvent, session: DeleteSession):
        """保存当前用户的删除会话。"""
        self.delete_sessions[get_user_key(event)] = session

    def _clear_delete_session(self, event: AstrMessageEvent):
        """清理当前用户的删除会话。"""
        self.delete_sessions.pop(get_user_key(event), None)

    def _get_title_missing_session(self, event: AstrMessageEvent) -> TitleMissingSession | None:
        """获取当前用户的称号查询选择会话。"""
        return self.title_missing_sessions.get(get_user_key(event))

    def _set_title_missing_session(self, event: AstrMessageEvent, session: TitleMissingSession):
        """保存当前用户的称号查询选择会话。"""
        self.title_missing_sessions[get_user_key(event)] = session

    def _clear_title_missing_session(self, event: AstrMessageEvent):
        """清理当前用户的称号查询选择会话。"""
        self.title_missing_sessions.pop(get_user_key(event), None)

    @staticmethod
    def _extract_command_args(text: str, command_name: str) -> str:
        """从原始消息文本中提取命令参数部分。"""
        raw = (text or "").strip()
        if not raw:
            return ""
        parts = raw.split(maxsplit=1)
        if not parts:
            return ""
        head = parts[0].lstrip("/")
        if head == command_name:
            return parts[1].strip() if len(parts) > 1 else ""
        return raw

    @staticmethod
    def _is_help_requested(args: str) -> bool:
        """判断参数是否表示用户在请求帮助信息。"""
        return (args or "").strip().lower() in {"--help", "-h"}

    @staticmethod
    def _normalize_command_name(name: str) -> str:
        """把命令别名归一化为帮助系统使用的名称。"""
        return (name or "").strip().split(maxsplit=1)[0].lstrip("/")

    @staticmethod
    def _build_command_usage(command_name: str) -> str:
        """生成单个命令的用法说明。"""
        return COMMAND_HELP[command_name]["usage"]

    def _build_help_text(self, target: str | None = None) -> str:
        """生成插件总帮助或指定命令的帮助文本。"""
        if target:
            command_name = self._normalize_command_name(target)
            if command_name in COMMAND_HELP:
                return self._build_command_usage(command_name)
            return f"未找到指令：{target}\n\n{self._build_command_usage('help')}"

        lines = [f"Arcaea Banner 插件指令一览（共 {len(COMMAND_HELP_ORDER)} 个）", ""]
        lines.append("每个指令都支持 /<指令名> --help 查看用法。")
        lines.append("")
        for command_name in COMMAND_HELP_ORDER:
            lines.append(f"/{command_name} | {COMMAND_HELP[command_name]['summary']}")
        lines.append("")
        lines.append("例如：/score --help")
        lines.append("例如：/delete_score --help")
        return "\n".join(lines)

    def _validate_no_arg_command(self, args: str, command_name: str) -> str | None:
        """校验无参数命令是否被错误地传入了参数。"""
        if self._is_help_requested(args) or args:
            return self._build_command_usage(command_name)
        return None

    @staticmethod
    def _parse_title_missing_args(args: str) -> tuple[str | None, str | None, int | None, str | None]:
        """解析称号缺失查询命令中的版本与数量参数。"""
        text = (args or "").strip()
        if not text:
            return None, None, None, None

        parts = text.split()
        tier = parts[0].strip().lower()
        if tier not in {"spirit", "tribute", "legend"}:
            return None, None, None, "第一个参数必须是 spirit | tribute | legend"

        limit: int | None = None
        tail = parts[1:]
        if tail and tail[-1].isdigit():
            limit = int(tail[-1])
            if limit <= 0:
                return None, None, None, "显示条数必须是大于 0 的整数"
            tail = tail[:-1]

        version_input = " ".join(tail).strip() or None
        return tier, version_input, limit, None

    @staticmethod
    def _title_query_label(mode: str) -> str:
        """把查询模式转换为用户可读的中文标签。"""
        if mode == "near":
            return "冲牌建议"
        return "未完成曲目清单"

    def _build_title_query_result(
        self,
        user_key: str,
        mode: str,
        tier: str,
        version_group: str | None = None,
        limit: int | None = None,
    ) -> str:
        """根据模式和版本构造称号查询结果文本。"""
        assert self.title_missing_service is not None
        if mode == "near":
            return self.title_missing_service.build_near_text(
                user_key,
                tier=tier,
                version_group=version_group,
                limit=limit,
            )
        return self.title_missing_service.build_missing_text(
            user_key,
            tier=tier,
            version_group=version_group,
            limit=limit,
        )

    async def _handle_title_query_command(self, event: AstrMessageEvent, command_name: str, mode: str):
        """统一处理称号缺失和冲牌建议两类查询命令。"""
        assert self.title_missing_service is not None

        try:
            self._clear_title_missing_session(event)
            args = self._extract_command_args(event.message_str or "", command_name)
            if not args or self._is_help_requested(args):
                yield event.plain_result(self._build_command_usage(command_name))
                return

            tier, version_input, limit, error_text = self._parse_title_missing_args(args)
            if error_text:
                yield event.plain_result(self._build_command_usage(command_name))
                return

            version_group = None
            if version_input:
                version_group, candidates = self.title_missing_service.resolve_version_group(version_input)
                if not version_group:
                    if not candidates:
                        yield event.plain_result(self.title_missing_service.build_unknown_version_text(version_input))
                        return

                    session = TitleMissingSession(
                        tier=tier,
                        mode=mode,
                        candidates=candidates,
                        limit=limit,
                    )
                    self._set_title_missing_session(event, session)
                    yield event.plain_result(
                        self.title_missing_service.build_version_candidate_text(
                            tier,
                            version_input,
                            candidates,
                            limit=limit,
                            mode=mode,
                        )
                    )

                    cancel_words = {normalize_text_command(word) for word in CANCEL_WORDS}

                    @session_waiter(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, record_history_chains=False)
                    async def title_query_waiter(controller: SessionController, next_event: AstrMessageEvent):
                        """等待用户在版本候选列表中选择具体版本。"""
                        current = self._get_title_missing_session(next_event)
                        if current is None:
                            controller.stop()
                            return

                        reply = normalize_text_command(next_event.message_str or "")
                        if not reply:
                            await next_event.send(next_event.plain_result("请回复候选序号，或回复“取消”放弃。"))
                            controller.keep(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, reset_timeout=True)
                            return

                        if reply in cancel_words:
                            await next_event.send(
                                next_event.plain_result(f"已取消查看{self._title_query_label(current.mode)}。")
                            )
                            self._clear_title_missing_session(next_event)
                            controller.stop()
                            return

                        if reply.isdigit():
                            index = int(reply)
                            if 1 <= index <= len(current.candidates):
                                result_text = self._build_title_query_result(
                                    get_user_key(next_event),
                                    mode=current.mode,
                                    tier=current.tier,
                                    version_group=current.candidates[index - 1],
                                    limit=current.limit,
                                )
                                await next_event.send(next_event.plain_result(result_text))
                                self._clear_title_missing_session(next_event)
                                controller.stop()
                                return

                            await next_event.send(
                                next_event.plain_result(
                                    f"候选序号无效，请输入 1 到 {len(current.candidates)} 之间的数字。"
                                )
                            )
                            controller.keep(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, reset_timeout=True)
                            return

                        await next_event.send(next_event.plain_result("请回复候选序号，或回复“取消”放弃。"))
                        controller.keep(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, reset_timeout=True)

                    try:
                        await title_query_waiter(event)
                    except TimeoutError:
                        if self._get_title_missing_session(event) is not None:
                            yield event.plain_result(f"等待选择超时，已取消查看{self._title_query_label(mode)}。")
                        self._clear_title_missing_session(event)
                    except Exception as exc:
                        logger.error(f"[arcaea] /{command_name} error: {exc}", exc_info=True)
                        yield event.plain_result(f"生成{self._title_query_label(mode)}失败：{exc}")
                        self._clear_title_missing_session(event)
                    finally:
                        event.stop_event()
                    return

            text = self._build_title_query_result(
                get_user_key(event),
                mode=mode,
                tier=tier,
                version_group=version_group,
                limit=limit,
            )
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /{command_name} error: {exc}", exc_info=True)
            yield event.plain_result(f"生成{self._title_query_label(mode)}失败：{exc}")

    @filter.command("help", priority=10)
    async def help(self, event: AstrMessageEvent):
        """查看插件指令帮助。"""
        try:
            args = self._extract_command_args(event.message_str or "", "help")
            if self._is_help_requested(args):
                yield event.plain_result(self._build_command_usage("help"))
                return

            target = args.strip() or None
            yield event.plain_result(self._build_help_text(target))
        except Exception as exc:
            logger.error(f"[arcaea] /help error: {exc}", exc_info=True)
            yield event.plain_result(f"生成帮助失败：{exc}")

    @filter.command("import", priority=10)
    async def import_score(self, event: AstrMessageEvent):
        """导入 Arcaea 成绩截图。"""
        assert self.import_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "import")
            direct_images = extract_image_inputs(event)
            if self._is_help_requested(args):
                yield event.plain_result(self._build_command_usage("import"))
                return
            if args and not direct_images:
                yield event.plain_result(self._build_command_usage("import"))
                return

            self.import_sessions[get_user_key(event)] = self._new_import_session()
            if len(direct_images) > 1:
                yield event.plain_result("一次只支持发送一张 Arcaea 结算截图，请重新发送单张图片。")
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
                """在导入会话中持续接收截图和文本指令。"""
                session = self._get_import_session(next_event)
                text = (next_event.message_str or "").strip()
                images = extract_image_inputs(next_event)
                event_key = get_event_message_key(next_event)

                if event_key and session.last_event_key == event_key:
                    logger.info(f"[arcaea] skip duplicated import event: {event_key}")
                    controller.keep(timeout=IMPORT_TIMEOUT_SECONDS, reset_timeout=True)
                    return

                if event_key:
                    session.last_event_key = event_key

                if images:
                    if len(images) > 1:
                        await next_event.send(next_event.plain_result("一次只支持发送一张截图，请重新发送单张图片。"))
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
                yield event.plain_result("等待超时，已退出导入。\n" + self.import_service.summarize_session(session))
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
            args = self._extract_command_args(event.message_str or "", "summary")
            usage = self._validate_no_arg_command(args, "summary")
            if usage:
                yield event.plain_result(usage)
                return

            text = self.summary_service.build_summary_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /summary error: {exc}", exc_info=True)
            yield event.plain_result(f"生成总结失败：{exc}")

    @filter.command("score", priority=10)
    async def score(self, event: AstrMessageEvent):
        """查询曲目的当前最佳成绩和跨游戏成绩。"""
        assert self.score_query_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "score")
            if self._is_help_requested(args):
                yield event.plain_result(self.score_query_service.build_usage_text())
                return

            text = self.score_query_service.build_score_text(get_user_key(event), args)
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /score error: {exc}", exc_info=True)
            yield event.plain_result("查询分数失败。")

    @filter.command("scoresheet", priority=10)
    async def scoresheet(self, event: AstrMessageEvent):
        """输出当前用户的跨游戏成绩表。"""
        assert self.cross_game_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "scoresheet")
            usage = self._validate_no_arg_command(args, "scoresheet")
            if usage:
                yield event.plain_result(usage)
                return

            text = self.cross_game_service.build_cross_game_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /scoresheet error: {exc}", exc_info=True)
            yield event.plain_result(f"生成跨游戏结果失败：{exc}")

    @filter.command("title_all", priority=10)
    async def title_all(self, event: AstrMessageEvent):
        """输出所有版本的 Spirit / Tribute / Legend 称号进度。"""
        assert self.version_title_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "title_all")
            usage = self._validate_no_arg_command(args, "title_all")
            if usage:
                yield event.plain_result(usage)
                return

            text = self.version_title_service.build_all_titles_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /title_all error: {exc}", exc_info=True)
            yield event.plain_result(f"生成版本称号总览失败：{exc}")

    @filter.command("title_spirit", priority=10)
    async def title_spirit(self, event: AstrMessageEvent):
        """输出所有版本的 Spirit 称号进度。"""
        assert self.version_title_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "title_spirit")
            usage = self._validate_no_arg_command(args, "title_spirit")
            if usage:
                yield event.plain_result(usage)
                return

            text = self.version_title_service.build_spirit_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /title_spirit error: {exc}", exc_info=True)
            yield event.plain_result(f"生成 Spirit 称号进度失败：{exc}")

    @filter.command("title_tribute", priority=10)
    async def title_tribute(self, event: AstrMessageEvent):
        """输出所有版本的 Tribute 称号进度。"""
        assert self.version_title_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "title_tribute")
            usage = self._validate_no_arg_command(args, "title_tribute")
            if usage:
                yield event.plain_result(usage)
                return

            text = self.version_title_service.build_tribute_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /title_tribute error: {exc}", exc_info=True)
            yield event.plain_result(f"生成 Tribute 称号进度失败：{exc}")

    @filter.command("title_legend", priority=10)
    async def title_legend(self, event: AstrMessageEvent):
        """输出所有版本的 Legend 称号进度。"""
        assert self.version_title_service is not None

        try:
            args = self._extract_command_args(event.message_str or "", "title_legend")
            usage = self._validate_no_arg_command(args, "title_legend")
            if usage:
                yield event.plain_result(usage)
                return

            text = self.version_title_service.build_legend_text(get_user_key(event))
            yield event.plain_result(text)
        except Exception as exc:
            logger.error(f"[arcaea] /title_legend error: {exc}", exc_info=True)
            yield event.plain_result(f"生成 Legend 称号进度失败：{exc}")

    @filter.command("title_missing", priority=10)
    async def title_missing(self, event: AstrMessageEvent):
        """输出版本称号的未完成曲目清单。"""
        async for result in self._handle_title_query_command(event, "title_missing", "missing"):
            yield result

    @filter.command("title_near", priority=10)
    async def title_near(self, event: AstrMessageEvent):
        """输出最接近完成称号的冲牌建议。"""
        async for result in self._handle_title_query_command(event, "title_near", "near"):
            yield result

    @filter.command("delete_score", priority=10)
    async def delete_score(self, event: AstrMessageEvent):
        """删除当前用户某张谱面的成绩记录。"""
        assert self.delete_service is not None

        try:
            self._clear_delete_session(event)
            args = self._extract_command_args(event.message_str or "", "delete_score")
            if not args or self._is_help_requested(args):
                yield event.plain_result(self.delete_service.build_usage_text())
                return

            user_key = get_user_key(event)
            pending: DeleteSession | None = None

            if args.isdigit():
                pending, text = self.delete_service.prepare_delete_by_chart_id(user_key, int(args))
            else:
                parts = args.split(maxsplit=1)
                if len(parts) < 2:
                    yield event.plain_result(self.delete_service.build_usage_text())
                    return

                difficulty = parts[0].strip().upper()
                song_name = parts[1].strip()
                pending, text = self.delete_service.prepare_delete_by_name(
                    user_key,
                    difficulty=difficulty,
                    song_name=song_name,
                )

            if pending is None:
                yield event.plain_result(text)
                return

            self._set_delete_session(event, pending)
            yield event.plain_result(text)

            cancel_words = {normalize_text_command(word) for word in CANCEL_WORDS}
            confirm_words = {normalize_text_command(word) for word in CONFIRM_WORDS}

            @session_waiter(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, record_history_chains=False)
            async def delete_waiter(controller: SessionController, next_event: AstrMessageEvent):
                """等待用户确认或取消删除当前成绩。"""
                session = self._get_delete_session(next_event)
                if session is None:
                    controller.stop()
                    return

                reply = normalize_text_command(next_event.message_str or "")
                if not reply:
                    if session.confirm is None:
                        await next_event.send(next_event.plain_result("请回复候选序号，或回复“取消”放弃。"))
                    else:
                        await next_event.send(next_event.plain_result("请回复“确认”继续删除，或回复“取消”放弃。"))
                    controller.keep(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, reset_timeout=True)
                    return

                if reply in cancel_words:
                    current_name = (
                        f"{session.confirm.song_name} [{session.confirm.difficulty}]"
                        if session.confirm is not None
                        else "当前删除操作"
                    )
                    await next_event.send(next_event.plain_result(f"已取消删除：{current_name}。"))
                    self._clear_delete_session(next_event)
                    controller.stop()
                    return

                if session.confirm is None:
                    if reply.isdigit():
                        _confirm, result_text = self.delete_service.choose_candidate(session, int(reply))
                        await next_event.send(next_event.plain_result(result_text))
                    else:
                        await next_event.send(next_event.plain_result("请回复候选序号，或回复“取消”放弃。"))
                    controller.keep(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, reset_timeout=True)
                    return

                if reply in confirm_words:
                    result_text = self.delete_service.delete_confirmed(get_user_key(next_event), session.confirm.chart_id)
                    await next_event.send(next_event.plain_result(result_text))
                    self._clear_delete_session(next_event)
                    controller.stop()
                    return

                await next_event.send(
                    next_event.plain_result(
                        "仅支持回复“确认”或“取消”。\n"
                        f"待删除谱面：{session.confirm.song_name} [{session.confirm.difficulty}]"
                    )
                )
                controller.keep(timeout=DELETE_CONFIRM_TIMEOUT_SECONDS, reset_timeout=True)

            try:
                await delete_waiter(event)
            except TimeoutError:
                session = self._get_delete_session(event)
                if session is not None:
                    if session.confirm is not None:
                        yield event.plain_result(
                            f"等待确认超时，已取消删除：{session.confirm.song_name} [{session.confirm.difficulty}]。"
                        )
                    else:
                        yield event.plain_result("等待选择超时，已取消删除。")
                self._clear_delete_session(event)
            except Exception as exc:
                logger.error(f"[arcaea] /delete_score error: {exc}", exc_info=True)
                yield event.plain_result(f"删除成绩失败：{exc}")
                self._clear_delete_session(event)
            finally:
                event.stop_event()
        except Exception as exc:
            logger.error(f"[arcaea] /delete_score error: {exc}", exc_info=True)
            yield event.plain_result(f"删除成绩失败：{exc}")
