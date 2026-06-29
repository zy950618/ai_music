from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


CreationMode = Literal[
    "song",
    "instrumental",
    "bgm",
    "loop",
    "short_video",
    "children",
    "classical",
    "game",
    "film",
]


@dataclass
class MusicCreationRequest:
    theme: str
    mood: list[str]
    genre: list[str]
    audience: str
    use_case: str
    duration_sec: int
    vocal_required: bool
    title: str | None = None
    mode: CreationMode = "song"
    language: str = "zh"
    bpm: int | None = None
    key: str | None = None
    lyrics_input: str | None = None
    reference_profile_id: str | None = None
    forbidden: list[str] = field(default_factory=list)
    export_formats: list[str] = field(default_factory=lambda: ["wav"])


@dataclass
class SongSection:
    name: str
    start_sec: float
    end_sec: float
    goal: str


@dataclass
class EditDecision:
    id: str
    version_id: str
    operation: str
    start_sec: float | None = None
    end_sec: float | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportFile:
    id: str
    version_id: str
    kind: str
    format: str
    path: str | None = None
    download_url: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    ready: bool = False
    blocked_reason: str | None = None


@dataclass
class MusicVersion:
    version_id: str
    title: str
    status: str
    audio_source: str
    duration_sec: float
    structure: list[SongSection]
    prompt_snapshot: str
    model_provider: str
    model_name: str
    failure_codes: list[str]
    generation_route: dict[str, Any] = field(default_factory=dict)
    audio_path: str | None = None
    download_url: str | None = None
    bpm: int | None = None
    key: str | None = None
    lyrics: str | None = None
    model_version: str | None = None
    audio_analysis: dict[str, Any] = field(default_factory=dict)
    score_total: int | None = None
    score_breakdown: dict[str, int] = field(default_factory=dict)
    quality_report: dict[str, Any] = field(default_factory=dict)
    export_files: list[ExportFile] = field(default_factory=list)
    edit_decisions: list[EditDecision] = field(default_factory=list)


@dataclass
class MusicCreationResult:
    task_id: str
    work_id: str
    brief: str
    versions: list[MusicVersion]
    qa_summary: str
    rework_suggestions: list[str]
    rights_status: str
    selected_version_id: str | None = None
    request_data: dict[str, Any] = field(default_factory=dict)
    parent_task_id: str | None = None
    rework_reason: str | None = None
    rework_root_task_id: str | None = None
    rework_depth: int = 0
    rework_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RightsConfiguration:
    rights_owner: str
    usage_scope: str
    territory: str
    duration: str
    ai_disclosure: str
    model_license: str
    commercial_use_allowed: bool
    transfer_allowed: bool = False
    adaptation_allowed: bool = False
    platform_profile_id: str | None = None
    export_profile: str = "wav_master_preview_license"
    manual_approval_required: bool = False
    reference_sources: list[str] = field(default_factory=list)
    notes: str = ""
