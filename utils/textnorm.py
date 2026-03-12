"""提供文本归一化、JSON 提取和名称匹配辅助函数。"""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher


def compact(text: str) -> str:
    """对文本做归一化、去空白和小写处理。"""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.strip().lower()
    text = re.sub(r"\s+", "", text)
    return text


def normalize_text_command(text: str) -> str:
    """把用户命令文本归一化为便于比较的形式。"""
    return compact(text)


def extract_json(text: str) -> dict:
    """从模型返回文本中提取 JSON 对象。"""
    text = (text or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    raise ValueError(f"无法解析 JSON: {text}")


def normalize_title(text: str) -> str:
    """把曲名归一化为适合匹配的形式。"""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.strip().lower()
    text = re.sub(r"\s+", "", text)
    text = text.replace("・", "")
    text = text.replace("·", "")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("～", "~")
    text = text.replace("　", "")
    text = re.sub(r"^[\[\]【】()（）<>〈〉『』「」]+", "", text)
    text = re.sub(r"[\[\]【】()（）<>〈〉『』「」]+$", "", text)
    return text


def common_prefix_len(a: str, b: str) -> int:
    """计算两个字符串的公共前缀长度。"""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def name_match_score(target: str, candidate: str) -> float:
    """为目标曲名和候选曲名计算相似度分数。"""
    target_c = compact(target)
    cand_c = compact(candidate)
    if not target_c or not cand_c:
        return 0.0

    seq = SequenceMatcher(None, target_c, cand_c).ratio()
    prefix_len = common_prefix_len(target_c, cand_c)
    prefix_ratio = prefix_len / max(1, len(cand_c))
    target_ratio = prefix_len / max(1, len(target_c))

    bonus = 0.0
    if cand_c.startswith(target_c) and len(target_c) >= 3:
        bonus += 0.18
    if target_c in cand_c or cand_c in target_c:
        bonus += 0.06

    return seq * 0.62 + prefix_ratio * 0.23 + target_ratio * 0.09 + bonus


def is_reasonable_prefix_match(target: str, candidate: str) -> bool:
    """判断候选曲名是否可接受为前缀匹配。"""
    target_c = compact(target)
    cand_c = compact(candidate)
    if not target_c or not cand_c:
        return False
    if not cand_c.startswith(target_c):
        return False
    if len(target_c) < 3:
        return False
    return len(target_c) >= max(3, int(len(cand_c) * 0.4))
