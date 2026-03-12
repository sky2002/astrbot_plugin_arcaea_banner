"""生成称号缺失清单和冲牌建议文本。"""

from __future__ import annotations

from ..db.repositories import ArcaeaRepository
from ..models import MissingChartEntry
from ..utils.textnorm import compact, name_match_score
from .aggregates.title_missing import TitleMissingAggregateService
from .aggregates.title_progress import VERSION_GROUP_ORDER
from .metrics.score_sheet import ScoreSheetService


DEFAULT_PREVIEW_LIMIT = 12

TIER_LABELS = {
    "spirit": "Spirit \u79f0\u53f7",
    "tribute": "Tribute \u79f0\u53f7",
    "legend": "Legend \u79f0\u53f7",
}

THRESHOLD_HINTS = {
    "spirit": "101 \u4e07\u6ee1\u5206 >= 1000000",
    "tribute": "101 \u4e07\u6ee1\u5206 >= 1007500",
    "legend": "\u539f\u59cb\u5206 >= 10000000",
}

QUERY_LABELS = {
    "missing": "\u672a\u5b8c\u6210\u6e05\u5355",
    "near": "\u51b2\u724c\u5efa\u8bae",
}


class TitleMissingService:
    """生成称号缺失清单和冲牌建议文本。"""
    def __init__(self, repo: ArcaeaRepository):
        """初始化称号缺失服务依赖。"""
        self.repo = repo
        self.score_sheet_service = ScoreSheetService()
        self.aggregate_service = TitleMissingAggregateService()

    def parse_version_group(self, version_text: str) -> str | None:
        """解析用户输入并返回唯一确定的版本组。"""
        resolved, _candidates = self.resolve_version_group(version_text)
        return resolved

    def resolve_version_group(self, version_text: str) -> tuple[str | None, list[str]]:
        """解析版本文本并返回命中的版本或候选列表。"""
        target = compact(version_text)
        if not target:
            return None, []

        known_versions = self.get_known_versions()

        exact_matches = [name for name in known_versions if compact(name) == target]
        if len(exact_matches) == 1:
            return exact_matches[0], []

        prefix_matches = [name for name in known_versions if compact(name).startswith(target)]
        if len(prefix_matches) == 1:
            return prefix_matches[0], []
        if len(prefix_matches) > 1:
            return None, prefix_matches[:5]

        scored = sorted(
            ((name_match_score(target, name), name) for name in known_versions),
            key=lambda item: item[0],
            reverse=True,
        )
        candidate_names = [name for score, name in scored if score >= 0.55][:5]
        if len(candidate_names) == 1:
            return candidate_names[0], []
        if len(candidate_names) > 1:
            return None, candidate_names
        return None, []

    def get_known_versions(self) -> list[str]:
        """返回当前支持识别的版本组名称。"""
        known_versions = list(VERSION_GROUP_ORDER)
        known_versions.extend(
            sorted(name for name in self.repo.get_chart_counts_by_version().keys() if name not in VERSION_GROUP_ORDER)
        )
        return known_versions

    def build_version_candidate_text(
        self,
        tier: str,
        version_input: str,
        candidates: list[str],
        limit: int | None = None,
        mode: str = "missing",
    ) -> str:
        """生成版本输入存在歧义时的候选提示文本。"""
        tier_label = TIER_LABELS[tier]
        query_label = QUERY_LABELS.get(mode, QUERY_LABELS["missing"])

        lines = [
            f"\u5339\u914d\u5230\u591a\u4e2a\u7248\u672c\u7ec4\uff0c\u8bf7\u56de\u590d\u5e8f\u53f7\u9009\u62e9\u8981\u67e5\u770b\u7684 {tier_label}{query_label}\uff1a",
            f"\u8f93\u5165\u5185\u5bb9\uff1a{version_input}",
        ]
        if limit is not None:
            lines.append(f"\u663e\u793a\u6761\u6570\uff1a\u524d {limit} \u6761")
        lines.append("")
        for idx, name in enumerate(candidates, start=1):
            lines.append(f"{idx}. {name}")
        lines.append("")
        lines.append("\u56de\u590d\u5e8f\u53f7\u540e\u4f1a\u8f93\u51fa\u5bf9\u5e94\u7ed3\u679c\uff0c\u4e5f\u53ef\u4ee5\u56de\u590d\u201c\u53d6\u6d88\u201d\u653e\u5f03\u3002")
        return "\n".join(lines)

    def build_unknown_version_text(self, version_input: str) -> str:
        """生成无法识别版本输入时的提示文本。"""
        known_versions = ", ".join(self.get_known_versions())
        return (
            f"\u672a\u8bc6\u522b\u7684\u7248\u672c\u7ec4\uff1a{version_input}\n"
            f"\u5f53\u524d\u53ef\u7528\u7248\u672c\u7ec4\uff1a{known_versions}"
        )

    def build_missing_text(
        self,
        user_key: str,
        tier: str,
        version_group: str | None = None,
        limit: int | None = None,
    ) -> str:
        """生成指定称号的未完成谱面清单。"""
        rows = self._load_all_chart_rows(user_key)
        if not rows:
            return "\u66f2\u5e93\u4e3a\u7a7a\uff0c\u65e0\u6cd5\u751f\u6210\u672a\u5b8c\u6210\u66f2\u76ee\u6e05\u5355\u3002"

        score_rows = self.score_sheet_service.build_rows(rows)
        groups = self.aggregate_service.build(score_rows, tier=tier, version_filter=version_group)
        tier_label = TIER_LABELS[tier]
        threshold_hint = THRESHOLD_HINTS[tier]

        if version_group:
            return self._build_single_group_text(
                tier=tier,
                tier_label=tier_label,
                threshold_hint=threshold_hint,
                version_group=version_group,
                groups=groups,
                limit=limit,
            )

        if not groups:
            return f"\u5168\u66f2\u5e93\u7684 {tier_label} \u5df2\u5168\u90e8\u5b8c\u6210\u3002"

        lines = [f"\u672a\u5b8c\u6210\u66f2\u76ee\u6e05\u5355 - {tier_label}", "", f"\u5224\u5b9a\u6761\u4ef6\uff1a{threshold_hint}", ""]
        total_missing = sum(group.total_missing for group in groups)
        lines.append(f"\u5168\u66f2\u5e93\u672a\u5b8c\u6210\uff1a{total_missing} \u5f20")
        lines.append("")

        if limit is None:
            self._append_default_preview(lines, groups, tier)
        else:
            self._append_limited_preview(lines, groups, tier, limit, total_missing)
        return "\n".join(lines).rstrip()

    def build_near_text(
        self,
        user_key: str,
        tier: str,
        version_group: str | None = None,
        limit: int | None = None,
    ) -> str:
        """生成指定称号的冲牌建议列表。"""
        rows = self._load_all_chart_rows(user_key)
        if not rows:
            return "\u66f2\u5e93\u4e3a\u7a7a\uff0c\u65e0\u6cd5\u751f\u6210\u51b2\u724c\u5efa\u8bae\u3002"

        score_rows = self.score_sheet_service.build_rows(rows)
        groups = self.aggregate_service.build(score_rows, tier=tier, version_filter=version_group)
        tier_label = TIER_LABELS[tier]
        threshold_hint = THRESHOLD_HINTS[tier]

        entries = [entry for group in groups for entry in group.entries]
        if not entries:
            if version_group:
                return f"{version_group} \u7684 {tier_label} \u5df2\u5168\u90e8\u5b8c\u6210\u3002"
            return f"\u5168\u66f2\u5e93\u7684 {tier_label} \u5df2\u5168\u90e8\u5b8c\u6210\u3002"

        ordered_entries = sorted(
            entries,
            key=lambda item: (item.remaining_gap, item.song_name.lower(), item.difficulty, item.version_group.lower()),
        )
        display_limit = limit if limit is not None else DEFAULT_PREVIEW_LIMIT
        display_entries = ordered_entries[:display_limit]
        hidden = len(ordered_entries) - len(display_entries)
        show_version_group = version_group is None

        lines = [f"\u51b2\u724c\u5efa\u8bae - {tier_label}", ""]
        lines.append(f"\u8303\u56f4\uff1a{version_group or '\u5168\u66f2\u5e93'}")
        lines.append(f"\u5224\u5b9a\u6761\u4ef6\uff1a{threshold_hint}")
        lines.append(
            "\u6392\u5e8f\u65b9\u5f0f\uff1a\u6309\u79bb\u76ee\u6807\u5dee\u503c\u4ece\u5c0f\u5230\u5927\uff0c\u8d8a\u9760\u524d\u8d8a\u63a5\u8fd1\u8fbe\u6210\u3002"
        )
        lines.append(
            f"\u5f53\u524d\u5c55\u793a\uff1a\u524d {len(display_entries)} \u6761\uff08\u5171 {len(ordered_entries)} \u6761\u672a\u5b8c\u6210\uff09"
        )
        lines.append("")

        for idx, entry in enumerate(display_entries, start=1):
            lines.append(self._format_near_entry(idx, entry, tier, show_version_group=show_version_group))

        if hidden > 0:
            lines.append("")
            if version_group:
                lines.append(
                    f"\u8fd8\u6709 {hidden} \u5f20\u672a\u663e\u793a\uff0c\u53ef\u4f7f\u7528 /title_near {tier} {version_group} <\u66f4\u5927\u7684\u6570\u91cf> \u67e5\u770b\u66f4\u591a\u3002"
                )
            else:
                lines.append(
                    f"\u8fd8\u6709 {hidden} \u5f20\u672a\u663e\u793a\uff0c\u53ef\u4f7f\u7528 /title_near {tier} <\u66f4\u5927\u7684\u6570\u91cf> \u67e5\u770b\u66f4\u591a\uff0c\u6216\u6307\u5b9a\u7248\u672c\u7ec4\u7f29\u5c0f\u8303\u56f4\u3002"
                )

        lines.append("")
        if version_group:
            lines.append(
                f"\u5982\u9700\u67e5\u770b\u5b8c\u6574\u672a\u5b8c\u6210\u6e05\u5355\uff0c\u53ef\u4f7f\u7528 /title_missing {tier} {version_group}"
            )
        else:
            lines.append(f"\u5982\u9700\u67e5\u770b\u5b8c\u6574\u672a\u5b8c\u6210\u6e05\u5355\uff0c\u53ef\u4f7f\u7528 /title_missing {tier}")
        return "\n".join(lines).rstrip()

    def _build_single_group_text(
        self,
        tier: str,
        tier_label: str,
        threshold_hint: str,
        version_group: str,
        groups: list,
        limit: int | None,
    ) -> str:
        """生成单个版本组的缺失谱面展示文本。"""
        if not groups:
            return f"{version_group} \u7684 {tier_label} \u5df2\u5168\u90e8\u5b8c\u6210\u3002"

        group = groups[0]
        display_limit = limit if limit is not None else group.total_missing
        display_entries = group.entries[:display_limit]
        hidden = group.total_missing - len(display_entries)

        lines = [f"\u672a\u5b8c\u6210\u66f2\u76ee\u6e05\u5355 - {tier_label} | {version_group}", "", f"\u5224\u5b9a\u6761\u4ef6\uff1a{threshold_hint}"]
        lines.append(f"\u672a\u5b8c\u6210\u6570\u91cf\uff1a{group.total_missing} \u5f20")
        if limit is not None:
            lines.append(f"\u5f53\u524d\u5c55\u793a\uff1a\u524d {len(display_entries)} \u6761")
        lines.append("")
        for idx, entry in enumerate(display_entries, start=1):
            lines.append(self._format_entry(idx, entry, tier))
        if hidden > 0:
            lines.append("")
            lines.append(f"\u8fd8\u6709 {hidden} \u5f20\u672a\u663e\u793a\uff0c\u53ef\u4f7f\u7528\u66f4\u5927\u7684\u6570\u91cf\u91cd\u65b0\u67e5\u8be2\u3002")
        return "\n".join(lines)

    def _append_default_preview(self, lines: list[str], groups: list, tier: str):
        """按默认预览规则向输出中追加缺失谱面。"""
        for group in groups:
            lines.append(f"{group.version_group}\uff1a\u8fd8\u5dee {group.total_missing} \u5f20")
            preview_entries = group.entries[:DEFAULT_PREVIEW_LIMIT]
            for idx, entry in enumerate(preview_entries, start=1):
                lines.append(f"- \u7b2c {idx} \u6761\uff1a{self._format_entry_body(entry, tier)}")
            hidden = group.total_missing - len(preview_entries)
            if hidden > 0:
                lines.append(
                    f"- \u8fd8\u6709 {hidden} \u5f20\u672a\u663e\u793a\uff0c\u4f7f\u7528 /title_missing {tier} {group.version_group} \u67e5\u770b\u5b8c\u6574\u6e05\u5355"
                )
            lines.append("")

    def _append_limited_preview(self, lines: list[str], groups: list, tier: str, limit: int, total_missing: int):
        """按限制数量向输出中追加缺失谱面。"""
        remaining = limit
        shown_total = 0
        for group in groups:
            if remaining <= 0:
                break
            preview_entries = group.entries[:remaining]
            if not preview_entries:
                continue

            lines.append(f"{group.version_group}\uff1a\u8fd8\u5dee {group.total_missing} \u5f20")
            for idx, entry in enumerate(preview_entries, start=1):
                lines.append(f"- \u7b2c {shown_total + idx} \u6761\uff1a{self._format_entry_body(entry, tier)}")
            shown = len(preview_entries)
            shown_total += shown
            remaining -= shown
            lines.append("")

        hidden_total = total_missing - shown_total
        if hidden_total > 0:
            lines.append(f"\u5f53\u524d\u4ec5\u5c55\u793a\u524d {shown_total} \u6761\uff0c\u5269\u4f59 {hidden_total} \u5f20\u672a\u663e\u793a\u3002")
            lines.append(
                f"\u53ef\u4f7f\u7528 /title_missing {tier} <\u66f4\u5927\u7684\u6570\u91cf> \u67e5\u770b\u66f4\u591a\uff0c\u6216\u6307\u5b9a\u7248\u672c\u7ec4\u67e5\u770b\u5b8c\u6574\u6e05\u5355\u3002"
            )

    def _format_entry(self, idx: int, entry: MissingChartEntry, tier: str) -> str:
        """格式化缺失清单中的单条谱面文本。"""
        return f"\u7b2c {idx} \u6761\uff1a{self._format_entry_body(entry, tier)}"

    def _format_entry_body(self, entry: MissingChartEntry, tier: str) -> str:
        """格式化缺失清单条目的主体内容。"""
        if tier in {"spirit", "tribute"}:
            return (
                f"{entry.song_name} [{entry.difficulty}] "
                f"\u5f53\u524d 101 \u4e07\u6ee1\u5206 {entry.full_score_101}\uff0c"
                f"\u79bb\u76ee\u6807\u8fd8\u5dee {entry.remaining_gap}\uff08\u539f\u59cb\u5206 {entry.best_score}\uff09"
            )
        return (
            f"{entry.song_name} [{entry.difficulty}] "
            f"\u5f53\u524d\u539f\u59cb\u5206 {entry.best_score}\uff0c"
            f"\u79bb\u76ee\u6807\u8fd8\u5dee {entry.remaining_gap}"
        )

    def _format_near_entry(self, idx: int, entry: MissingChartEntry, tier: str, show_version_group: bool) -> str:
        """格式化冲牌建议中的单条谱面文本。"""
        return f"{idx}. {self._format_near_entry_body(entry, tier, show_version_group=show_version_group)}"

    def _format_near_entry_body(self, entry: MissingChartEntry, tier: str, show_version_group: bool) -> str:
        """格式化冲牌建议条目的主体内容。"""
        prefix = f"{entry.version_group} | " if show_version_group else ""
        if tier in {"spirit", "tribute"}:
            return (
                f"{prefix}{entry.song_name} [{entry.difficulty}]\uff1a"
                f"\u79bb\u76ee\u6807\u8fd8\u5dee {entry.remaining_gap}"
                f"\uff08\u5f53\u524d 101 \u4e07\u6ee1\u5206 {entry.full_score_101}\uff0c\u539f\u59cb\u5206 {entry.best_score}\uff09"
            )
        return (
            f"{prefix}{entry.song_name} [{entry.difficulty}]\uff1a"
            f"\u79bb\u76ee\u6807\u8fd8\u5dee {entry.remaining_gap}"
            f"\uff08\u5f53\u524d\u539f\u59cb\u5206 {entry.best_score}\uff09"
        )

    def _load_all_chart_rows(self, user_key: str) -> list[dict]:
        """加载包含用户成绩的全谱面数据。"""
        rows = self.repo.get_all_chart_rows_with_user_scores(user_key)
        source_rows: list[dict] = []
        for row in rows:
            source_rows.append(
                {
                    "chart_id": int(row["chart_id"]),
                    "song_name": str(row["song_name"]),
                    "pack_name": str(row["pack_name"]),
                    "version_group": str(row["version_group"]),
                    "version_text": str(row["version_text"]),
                    "difficulty": str(row["difficulty"]),
                    "level_text": str(row["level_text"]),
                    "constant": float(row["constant"]),
                    "note_count": int(row["note_count"] or 0),
                    "best_score": int(row["best_score"] or 0),
                    "play_count": int(row["play_count"] or 0),
                }
            )
        return source_rows
