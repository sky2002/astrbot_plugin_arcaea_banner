"""封装视觉模型选择和截图识别流程。"""

from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.exceptions import ProviderNotFoundError
from astrbot.core.star.context import Context

from ..constants import VISION_PROVIDER_ID
from ..models import RecognizedResult
from ..utils.textnorm import extract_json


class VisionService:
    """负责挑选可用视觉模型并解析截图识别结果。"""
    def __init__(self, context: Context, preferred_provider_id: str = VISION_PROVIDER_ID):
        """初始化视觉识别服务配置。"""
        self.context = context
        self.preferred_provider_id = preferred_provider_id

    async def pick_provider_id(self, event: AstrMessageEvent) -> str | None:
        """按优先级挑选当前会话可用的视觉模型提供者。"""
        if self.preferred_provider_id and self.preferred_provider_id.strip():
            pid = self.preferred_provider_id.strip()
            prov = self.context.get_provider_by_id(provider_id=pid)
            if prov:
                logger.info(f"[arcaea] use VISION_PROVIDER_ID = {pid}")
                return pid
            logger.warning(f"[arcaea] VISION_PROVIDER_ID not found: {pid}")

        try:
            curr_id = await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
            if curr_id:
                logger.info(f"[arcaea] current session provider = {curr_id}")
                return curr_id
        except ProviderNotFoundError:
            logger.warning("[arcaea] current session provider not found")
        except Exception as exc:
            logger.warning(f"[arcaea] failed to get current session provider: {exc}")

        all_providers = self.context.get_all_providers() or []
        provider_ids = [getattr(p, "id", None) for p in all_providers if getattr(p, "id", None)]
        logger.info(f"[arcaea] available providers = {provider_ids}")
        for provider in all_providers:
            pid = getattr(provider, "id", None)
            if pid:
                logger.info(f"[arcaea] fallback provider = {pid}")
                return pid
        return None

    async def recognize_single_result(self, event: AstrMessageEvent, image_input: str) -> RecognizedResult:
        """调用视觉模型识别单张结算图并解析结构化结果。"""
        provider_id = await self.pick_provider_id(event)
        if not provider_id:
            raise RuntimeError("没有可用 provider。请检查当前启用的配置文件里是否真的加载了模型。")

        prompt = """
请从这张 Arcaea 单曲结算截图中提取信息，并且只输出 JSON，不要输出解释，不要输出 Markdown。

格式严格如下：
{
  "song_name_visible": "",
  "song_name_guess": "",
  "difficulty": "",
  "score": 0,
  "pure_count": 0,
  "far_count": 0,
  "lost_count": 0
}

识别重点：
1. 曲名优先读取截图中上部偏中央、玩家名下方那条深色横条里的标题文字。这是最重要的信息来源。
2. 即使该标题被角色、装饰或特效遮挡了一部分，也要优先根据这条标题区域里仍然可见的字符去判断曲名。
3. 明确忽略左侧曲绘封面上的所有文字，也忽略 TRACK COMPLETE、玩家名、分数区、奖励区、按钮区等其他区域的文字。

字段要求：
1. song_name_visible 填写你从中上部标题条中实际辨认出的曲名文本；如果标题有局部遮挡，可以基于同一标题条里剩余可见字符做谨慎补全，但不要参考左侧曲绘文字。
2. 如果你能判断这首歌在 Arcaea 曲库里的常用官方标题，请填写到 song_name_guess；否则留空。
3. difficulty 只能是 PST / PRS / FTR / ETR / BYD 之一。
4. score 只能输出纯数字整数，例如 9976543。
5. 不要输出 pack_name，因为结算图里没有可靠的曲包信息。
6. pure_count，far_count，lost_count填写你从中下部辨认出的pure，far，lost数量。只能输出纯数字正整数。只输出pure，far，lost右侧的第一个整数。
""".strip()

        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
            image_urls=[image_input],
        )

        raw_text = (llm_resp.completion_text or "").strip()
        logger.info(f"[arcaea] vision raw response = {raw_text}")
        data = extract_json(raw_text)

        legacy_song_name = str(data.get("song_name", "") or "").strip()
        song_name_visible = str(data.get("song_name_visible", "") or "").strip()
        song_name_guess = str(data.get("song_name_guess", "") or "").strip()
        if not song_name_visible and legacy_song_name:
            song_name_visible = legacy_song_name
        if not song_name_guess and legacy_song_name:
            song_name_guess = legacy_song_name

        difficulty = str(data.get("difficulty", "") or "").strip().upper()

        score_raw = data.get("score", 0)
        try:
            score = int(score_raw)
        except Exception:
            score = 0

        pure_raw = data.get("pure_count", 0)
        try:
            pure_count = int(pure_raw)
        except Exception:
            pure_count = 0

        far_raw = data.get("far_count", 0)
        try:
            far_count = int(far_raw)
        except Exception:
            far_count = 0

        lost_raw = data.get("lost_count", 0)
        try:
            lost_count = int(lost_raw)
        except Exception:
            lost_count = 0

        total_note_count = pure_count + far_count + lost_count    

        return RecognizedResult(
            song_name_visible=song_name_visible,
            song_name_guess=song_name_guess,
            difficulty=difficulty,
            score=score,
            note_count=total_note_count,
        )
