"""集中定义插件运行时使用的常量和命令关键词。"""

from __future__ import annotations

DB_FILENAME = "test.db"
VISION_PROVIDER_ID = ""  # 留空则优先使用当前会话 provider
DEFAULT_PLATFORM = "qq_official"
IMPORT_TIMEOUT_SECONDS = 180
DELETE_CONFIRM_TIMEOUT_SECONDS = 60

ALLOWED_DIFFICULTIES = {"PST", "PRS", "FTR", "ETR", "BYD"}

CONFIRM_WORDS = {"确认", "是", "yes", "y", "ok", "录入"}
SKIP_WORDS = {"跳过", "skip", "s"}
CHOOSE_WORDS = {"候选", "重选", "选择", "list", "ls"}
FINISH_WORDS = {"完成", "结束", "done", "finish"}
CANCEL_WORDS = {"取消", "退出", "cancel", "stop"}
