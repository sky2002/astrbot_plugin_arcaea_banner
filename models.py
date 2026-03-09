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
