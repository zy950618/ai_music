from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PRODUCT_MIN_DURATION_SEC = 180
PRODUCT_MAX_DURATION_SEC = 300


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

RightsStatus = Literal["missing", "configured", "review_required", "blocked"]

CATEGORY_OPTIONS = [
    "爱情", "失恋", "暗恋", "亲情", "友情", "孤独", "治愈", "励志", "热血", "城市夜晚",
    "校园青春", "旅行", "国风", "赛博朋克", "电影感", "节日", "婚礼", "儿童", "商业广告",
    "短视频爆款", "游戏配乐", "冥想放松", "说唱表达", "社会观察", "企业宣传", "影视预告",
    "学习工作", "睡眠白噪", "运动健身",
]

GENRE_OPTIONS = [
    "Pop", "Mandarin Pop", "R&B", "Soul", "Rock", "Folk", "EDM", "House", "Future Bass",
    "Synthwave", "City Pop", "Hip-Hop", "Trap", "Lo-fi", "Country", "Jazz Pop", "Cinematic",
    "Orchestral", "Piano Ballad", "Acoustic", "国风", "古风", "民乐融合", "游戏音乐",
    "影视配乐", "儿童歌", "Ambient", "Meditation", "Corporate", "Short Video BGM",
]

EMOTION_OPTIONS = [
    "喜悦", "悲伤", "遗憾", "释然", "心动", "孤独", "治愈", "热血", "希望", "压抑",
    "梦幻", "紧张", "史诗", "温柔", "怀念", "愤怒", "恐惧", "惊喜", "信任", "期待",
    "宁静", "浪漫", "黑暗", "明亮", "松弛", "坚定", "破碎感", "重生感",
]

SCENE_OPTIONS = [
    "夜晚", "雨天", "城市街道", "地铁", "校园", "毕业", "旅行", "公路", "海边", "婚礼",
    "广告", "短视频", "游戏战斗", "游戏主城", "电影预告", "短剧转场", "直播背景", "学习",
    "办公", "睡眠", "冥想", "健身", "企业宣传", "产品发布", "儿童陪伴", "节日庆祝",
]

INSTRUMENT_OPTIONS = [
    "钢琴", "木吉他", "电吉他", "贝斯", "鼓组", "808", "弦乐", "合成器", "Pad", "古筝",
    "笛子", "二胡", "琵琶", "管弦乐", "铜管", "合唱", "钟琴", "打击乐", "环境音",
    "白噪", "FX", "采样切片",
]

VOCAL_TYPE_OPTIONS = [
    "男声", "女声", "童声", "合唱", "说唱", "低语", "沙哑", "空灵", "高亢", "温暖",
    "磁性", "清亮", "厚重", "无人声",
]

LANGUAGE_OPTIONS = ["zh", "en", "ja", "ko", "none"]


@dataclass
class LyricSection:
    name: str
    lines: list[str]
    role: str


@dataclass
class SongLyrics:
    title: str
    language: str
    theme: str
    hook: str
    sections: list[LyricSection]
    emotional_arc: str
    imagery_keywords: list[str]
    rhyme_notes: list[str]
    singability_notes: list[str]
    safety_notes: list[str]


@dataclass
class EmotionProfile:
    primaryEmotion: str
    secondaryEmotions: list[str]
    valence: float
    arousal: float
    intensity: float
    tension: float
    release: float
    resonanceKeywords: list[str]
    imageryKeywords: list[str]
    vocalDirection: str
    arrangementDirection: str


@dataclass
class VersionLoopState:
    state: str
    decision: str
    score_total: int
    score_breakdown: dict[str, int]
    hard_gate_results: dict[str, bool]
    failure_codes: list[str]
    root_cause: str
    evidence: list[str]
    rework_round_count: int
    version_rework_count: int
    preserve_fields: list[str]
    mutable_fields: list[str]
    responsible_agent: str
    next_agent: str
    next_action: str
    retry_budget: int
    capacity_bucket: str
    parent_version_id: str | None = None
    rework_brief: str | None = None
    manual_review_reason: str | None = None


@dataclass
class EvolutionSignal:
    signal_id: str
    created_at: str
    source: str
    metric: str
    value: int | float | str
    severity: str
    evidence_refs: list[str]
    threshold: int | float | str | None = None


@dataclass
class EvolutionPolicyProposal:
    proposal_id: str
    created_at: str
    target: str
    before: dict[str, Any]
    after: dict[str, Any]
    expected_effect: str
    risk_flags: list[str]
    requires_human_approval: bool
    approval_status: str
    rollback_plan: list[str]
    status: str


@dataclass
class EvolutionExperiment:
    experiment_id: str
    proposal_id: str
    started_at: str
    control_group: str
    treatment_group: str
    metrics: dict[str, float]
    result: str
    evidence_refs: list[str]
    ended_at: str | None = None


@dataclass
class ResearchSource:
    source_id: str
    source_url: str
    source_title: str
    source_type: str
    fetched_at: str
    credibility: str
    evidence_summary: str
    allowed_usage: str
    risk_flags: list[str]
    audit_status: str
    published_at: str | None = None
    author: str | None = None
    imported_to: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    review_notes: str = ""


@dataclass
class ExternalToolEvaluation:
    tool_id: str
    name: str
    ui_label_zh: str
    tool_category: str
    accepted_level: str
    integration_status: str
    absorbed_features: list[str]
    optimization_lessons: list[str]
    strong_constraints: list[str]
    rights_risks: list[str]
    security_risks: list[str]
    integration_risks: list[str]
    source_url: str = ""
    paid_dependency: bool = False
    requires_api_key: bool = False
    enabled: bool = False
    production_enabled: bool = False
    commercial_use_allowed: bool = False
    license_status: str = "needs_review"
    local_quota_guard: dict[str, int] = field(default_factory=dict)
    blocked_reasons: list[str] = field(default_factory=list)


@dataclass
class LocalToolGate:
    gate_id: str
    tool_id: str
    ui_label_zh: str
    allowlist: list[str]
    local_quota_guard: dict[str, int]
    allowed_extensions: list[str]
    requires_checksum: bool
    offline_fixture_only: bool
    network_access_allowed: bool
    passed: bool
    blocked_reasons: list[str] = field(default_factory=list)


@dataclass
class ProviderBenchmarkResult:
    benchmark_id: str
    tool_id: str
    fixture_id: str
    created_at: str
    offline_fixture_only: bool
    metrics: dict[str, float]
    output_path: str | None = None
    checksum: str | None = None
    notes: str = ""


@dataclass
class ResearchFixture:
    fixture_id: str
    tool_id: str
    ui_label_zh: str
    source_url: str
    source_type: str
    audit_status: str
    imported_to: str
    evidence_summary: str
    allowed_usage: str
    risk_flags: list[str]


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
    category: str | None = None
    categories: list[str] = field(default_factory=list)
    emotions: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    scenes: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    vocal_types: list[str] = field(default_factory=list)
    bpm: int | None = None
    key: str | None = None
    lyrics_input: str | None = None
    voice_profile: str | None = None
    reference_profile_id: str | None = None
    workspace_id: str = "workspace_guest"
    sound_design: dict[str, Any] = field(default_factory=dict)
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
    work_id: str = ""
    parent_version_id: str | None = None
    version_number: float = 1.0
    seed: str | int | None = None
    generation_route: dict[str, Any] = field(default_factory=dict)
    audio_path: str | None = None
    download_url: str | None = None
    bpm: int | None = None
    key: str | None = None
    lyrics: str | None = None
    lyrics_data: SongLyrics | None = None
    lyric_translation: str | None = None
    emotion_profile: EmotionProfile | None = None
    model_version: str | None = None
    audio_analysis: dict[str, Any] = field(default_factory=dict)
    score_total: int | None = None
    score_breakdown: dict[str, int] = field(default_factory=dict)
    quality_report: dict[str, Any] = field(default_factory=dict)
    loop_state: VersionLoopState | None = None
    export_files: list[ExportFile] = field(default_factory=list)
    edit_decisions: list[EditDecision] = field(default_factory=list)
    createdAt: str = ""
    generatedAt: str = ""
    updatedAt: str = ""
    optimizedAt: str | None = None


@dataclass
class MusicCreationResult:
    task_id: str
    work_id: str
    brief: str
    versions: list[MusicVersion]
    qa_summary: str
    rework_suggestions: list[str]
    rights_status: RightsStatus
    selected_version_id: str | None = None
    request_data: dict[str, Any] = field(default_factory=dict)
    parent_task_id: str | None = None
    rework_reason: str | None = None
    rework_root_task_id: str | None = None
    rework_depth: int = 0
    rework_history: list[dict[str, Any]] = field(default_factory=list)
    createdAt: str = ""
    updatedAt: str = ""
    lastGeneratedAt: str | None = None

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
    sample_sources: list[str] = field(default_factory=list)
    vocal_identity_policy: str = "no_unlicensed_real_voice_clone"
    export_allowed: bool = True
    transfer_allowed: bool = False
    adaptation_allowed: bool = False
    platform_profile_id: str | None = None
    export_profile: str = "wav_master_license"
    manual_approval_required: bool = False
    reference_sources: list[str] = field(default_factory=list)
    license_evidence_refs: list[str] = field(default_factory=list)
    source_integrity_evidence_refs: list[str] = field(default_factory=list)
    rights_approval_status: str = "pending"
    source_integrity_approval_status: str = "pending"
    approved_by: str | None = None
    approved_at: str | None = None
    risk_notes: list[str] = field(default_factory=list)
    notes: str = ""
