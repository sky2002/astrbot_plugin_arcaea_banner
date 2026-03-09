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


def get_event_message_key(event: AstrMessageEvent) -> str:
    message_obj = getattr(event, "message_obj", None)
    for attr in ("message_id", "msg_id", "id"):
        value = getattr(message_obj, attr, None)
        if value not in (None, ""):
            return str(value)

    raw = getattr(message_obj, "raw_message", None)
    if isinstance(raw, dict):
        for key in ("message_id", "msg_id", "id", "messageId"):
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)

        for key in ("header", "event", "message"):
            value = raw.get(key)
            if isinstance(value, dict):
                for nested_key in ("message_id", "msg_id", "id", "messageId"):
                    nested_value = value.get(nested_key)
                    if nested_value not in (None, ""):
                        return str(nested_value)

    return ""


def extract_image_inputs(event: AstrMessageEvent) -> list[str]:
    image_inputs: list[str] = []
    seen: set[str] = set()
    for seg in getattr(event.message_obj, "message", []) or []:
        is_image = isinstance(seg, Comp.Image) or type(seg).__name__ == "Image"
        if not is_image:
            continue

        url = getattr(seg, "url", None)
        if isinstance(url, str) and url.strip():
            normalized = url.strip()
            if normalized not in seen:
                seen.add(normalized)
                image_inputs.append(normalized)
            continue

        file_val = getattr(seg, "file", None)
        if isinstance(file_val, str) and file_val.strip():
            file_val = file_val.strip()
            if file_val.startswith(("http://", "https://", "base64://", "file://")):
                if file_val not in seen:
                    seen.add(file_val)
                    image_inputs.append(file_val)
                continue
            if os.path.exists(file_val):
                if file_val not in seen:
                    seen.add(file_val)
                    image_inputs.append(file_val)
                continue

        path_val = getattr(seg, "path", None)
        if isinstance(path_val, str) and path_val.strip():
            path_val = path_val.strip()
            if path_val.startswith(("http://", "https://", "base64://", "file://")):
                if path_val not in seen:
                    seen.add(path_val)
                    image_inputs.append(path_val)
                continue
            if os.path.exists(path_val):
                if path_val not in seen:
                    seen.add(path_val)
                    image_inputs.append(path_val)
                continue

    logger.info(f"[arcaea] extracted image inputs = {image_inputs}")
    return image_inputs
