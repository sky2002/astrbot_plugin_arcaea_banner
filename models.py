from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ChartRow = Any


@dataclass(slots=True)
class RecognizedResult:
    song_name_visible: str
    song_name_guess: str
    difficulty: str
    score: int


@dataclass(slots=True)
class ChartResolution:
    chart: ChartRow | None
    candidates: list[ChartRow] = field(default_factory=list)
    match_method: str = "none"
    matched_name: str = ""
    matched_name_source: str = "none"


@dataclass(slots=True)
class ImportProposal:
    recognized: RecognizedResult
    chart: ChartRow | None
    selected_chart: ChartRow | None
    candidates: list[ChartRow] = field(default_factory=list)
    match_method: str = "none"
    matched_name: str = ""
    matched_name_source: str = "none"
    force_choose: bool = False


@dataclass(slots=True)
class ImportSession:
    current: ImportProposal | None = None
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    processed: int = 0
    last_event_key: str = ""


@dataclass(slots=True)
class DeleteConfirmSession:
    chart_id: int
    song_name: str
    difficulty: str
    pack_name: str
    version_group: str
    best_score: int
    play_count: int


@dataclass(slots=True)
class DeleteSession:
    confirm: DeleteConfirmSession | None = None
    candidates: list[DeleteConfirmSession] = field(default_factory=list)


@dataclass(slots=True)
class TitleMissingSession:
    tier: str
    mode: str = "missing"
    candidates: list[str] = field(default_factory=list)
    limit: int | None = None


@dataclass(slots=True)
class ScoreSheetRow:
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
    version_group: str
    total: int
    spirit_remaining: int
    tribute_remaining: int
    legend_remaining: int

    @property
    def spirit_done(self) -> bool:
        return self.total > 0 and self.spirit_remaining == 0

    @property
    def tribute_done(self) -> bool:
        return self.total > 0 and self.tribute_remaining == 0

    @property
    def legend_done(self) -> bool:
        return self.total > 0 and self.legend_remaining == 0


@dataclass(slots=True)
class MissingChartEntry:
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
    version_group: str
    tier: str
    total_missing: int
    entries: list[MissingChartEntry] = field(default_factory=list)
