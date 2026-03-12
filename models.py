"""定义插件内部共享的数据模型和聚合结果结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ChartRow = Any


@dataclass(slots=True)
class RecognizedResult:
    """保存视觉识别出的单张结算图核心结果。"""
    song_name_visible: str
    song_name_guess: str
    difficulty: str
    score: int
    note_count: int


@dataclass(slots=True)
class ChartResolution:
    """保存谱面匹配过程的结果和候选信息。"""
    chart: ChartRow | None
    candidates: list[ChartRow] = field(default_factory=list)
    match_method: str = "none"
    matched_name: str = ""
    matched_name_source: str = "none"
    used_note_count: bool = False
    matched_note_count: int = 0


@dataclass(slots=True)
class ImportProposal:
    """表示一张截图当前待确认的导入提案。"""
    recognized: RecognizedResult
    chart: ChartRow | None
    selected_chart: ChartRow | None
    candidates: list[ChartRow] = field(default_factory=list)
    match_method: str = "none"
    matched_name: str = ""
    matched_name_source: str = "none"
    used_note_count: bool = False
    matched_note_count: int = 0
    force_choose: bool = False


@dataclass(slots=True)
class ImportSession:
    """记录一次批量导入会话的进度和当前待处理项。"""
    current: ImportProposal | None = None
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    processed: int = 0
    last_event_key: str = ""


@dataclass(slots=True)
class DeleteConfirmSession:
    """保存待删除成绩的确认信息。"""
    chart_id: int
    song_name: str
    difficulty: str
    pack_name: str
    version_group: str
    best_score: int
    play_count: int


@dataclass(slots=True)
class DeleteSession:
    """记录删除流程中的确认项或候选项。"""
    confirm: DeleteConfirmSession | None = None
    candidates: list[DeleteConfirmSession] = field(default_factory=list)


@dataclass(slots=True)
class TitleMissingSession:
    """保存称号查询中等待用户选择的版本候选。"""
    tier: str
    mode: str = "missing"
    candidates: list[str] = field(default_factory=list)
    limit: int | None = None


@dataclass(slots=True)
class ScoreSheetRow:
    """表示单张谱面在跨游戏分数表中的完整换算结果。"""
    chart_id: int
    song_name: str
    pack_name: str
    version_group: str
    version_text: str
    difficulty: str
    level_text: str
    constant: float
    note_count: int
    best_score: int
    play_count: int
    full_score_101: int = 0
    p_plus: int = 0
    arc_ptt: float = 0.0
    arc_rank: int = 0
    get_value: float = 0.0
    max_value: float = 0.0
    arc_contribution: float = 0.0
    mai_value: int = 0
    mai_rank: int = 0
    mai_contribution: int = 0
    chu_value: float = 0.0
    chu_rank: int = 0
    chu_contribution: float = 0.0
    rot_value: float = 0.0
    rot_rank: int = 0
    rot_contribution: float = 0.0
    para_value: float = 0.0
    para_rank: int = 0
    para_contribution: float = 0.0
    score_status: str = "0"
    small_p: float = 0.0
    small_p_grade: str = "D"
    mai_plus_value: int = 0
    mai_plus_rank: int = 0
    mai_plus_contribution: int = 0


@dataclass(slots=True)
class ScoreSheetAggregate:
    """汇总跨游戏分数表的总分和统计指标。"""
    total_play_count: int = 0
    arc_total: float = 0.0
    arc_raw_sum: float = 0.0
    total_get: float = 0.0
    total_max: float = 0.0
    get_ratio: float = 0.0
    mai_base_total: int = 0
    mai_bonus: int = 0
    mai_total: int = 0
    mai_plus_total: int = 0
    chu_total: float = 0.0
    rot_total: float = 0.0
    para_total: float = 0.0
    para_raw_sum: float = 0.0
    para_fraction_points: int = 0


@dataclass(slots=True)
class VersionTitleProgress:
    """表示单个版本组的称号完成进度。"""
    version_group: str
    total: int
    spirit_remaining: int
    tribute_remaining: int
    legend_remaining: int

    @property
    def spirit_done(self) -> bool:
        """判断 Spirit 称号是否已经完成。"""
        return self.total > 0 and self.spirit_remaining == 0

    @property
    def tribute_done(self) -> bool:
        """判断 Tribute 称号是否已经完成。"""
        return self.total > 0 and self.tribute_remaining == 0

    @property
    def legend_done(self) -> bool:
        """判断 Legend 称号是否已经完成。"""
        return self.total > 0 and self.legend_remaining == 0


@dataclass(slots=True)
class MissingChartEntry:
    """表示某个称号目标下仍未完成的一张谱面。"""
    chart_id: int
    song_name: str
    difficulty: str
    version_group: str
    best_score: int
    full_score_101: int
    remaining_gap: int
    target_value: int


@dataclass(slots=True)
class MissingChartGroup:
    """按版本组归类保存未完成谱面列表。"""
    version_group: str
    tier: str
    total_missing: int
    entries: list[MissingChartEntry] = field(default_factory=list)
