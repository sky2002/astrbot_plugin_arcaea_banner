from __future__ import annotations

import ast
import os

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
import astrbot.api.message_components as Comp


def safe_sender_id(event: AstrMessageEvent) -> str:
    try:
        sid = event.get_sender_id()
        if sid:
            return str(sid)
    except Exception:
        pass

    raw = getattr(event.message_obj, "raw_message", None)
    if isinstance(raw, dict):
        author = raw.get("author")
        if isinstance(author, dict):
            return str(author.get("user_openid", "") or "")
        if isinstance(author, str):
            try:
                author_obj = ast.literal_eval(author)
                if isinstance(author_obj, dict):
                    return str(author_obj.get("user_openid", "") or "")
            except Exception:
                pass
    return ""


def get_user_key(event: AstrMessageEvent) -> str:
    sid = safe_sender_id(event) or event.unified_msg_origin or "unknown"
    return str(sid)


def extract_image_inputs(event: AstrMessageEvent) -> list[str]:
    image_inputs: list[str] = []
    for seg in getattr(event.message_obj, "message", []) or []:
        is_image = isinstance(seg, Comp.Image) or type(seg).__name__ == "Image"
        if not is_image:
            continue

        url = getattr(seg, "url", None)
        if isinstance(url, str) and url.strip():
            image_inputs.append(url.strip())
            continue

        file_val = getattr(seg, "file", None)
        if isinstance(file_val, str) and file_val.strip():
            file_val = file_val.strip()
            if file_val.startswith(("http://", "https://", "base64://", "file://")):
                image_inputs.append(file_val)
                continue
            if os.path.exists(file_val):
                image_inputs.append(file_val)
                continue

        path_val = getattr(seg, "path", None)
        if isinstance(path_val, str) and path_val.strip():
            path_val = path_val.strip()
            if path_val.startswith(("http://", "https://", "base64://", "file://")):
                image_inputs.append(path_val)
                continue
            if os.path.exists(path_val):
                image_inputs.append(path_val)
                continue

    logger.info(f"[arcaea] extracted image inputs = {image_inputs}")
    return image_inputs
