from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    layer: str
    purpose: str
    acceptance: tuple[str, ...]
    source: str = "project"
    priority: str = "P0"
    license_status: str = "internal_project"
    enabled: bool = True
    ui_label_zh: str = ""
    integration_status: str = "active"


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    phase: str
    primary_skill_ids: tuple[str, ...]
    responsibility: str
    handoff_acceptance: tuple[str, ...]


@dataclass(frozen=True)
class ReworkRule:
    failure_code: str
    target_agent: str
    skill_id: str
    action: str
    preserve_fields: tuple[str, ...]
    mutable_fields: tuple[str, ...]
    retry_budget: int
    auto_rework_allowed: bool = True
    requires_human_review: bool = False
    delivery_block_only: bool = False


PONYTAIL_SOURCE_URL = "https://github.com/DietrichGebert/ponytail"
PONYTAIL_SOURCE_VERSION = "4.8.3"
PONYTAIL_SOURCE_COMMIT = "c4d1925ae9b76a1b641877328209ad25cfeb5ef2"
PONYTAIL_SOURCE = f"{PONYTAIL_SOURCE_URL}@{PONYTAIL_SOURCE_VERSION}+{PONYTAIL_SOURCE_COMMIT}"
PONYTAIL_LICENSE_STATUS = "MIT"


PONYTAIL_SKILLS: tuple[SkillDefinition, ...] = (
    SkillDefinition(
        "ponytail",
        "execution",
        "Apply the YAGNI, existing-code, stdlib, native-platform, and minimum-code ladder before implementation.",
        ("real flow is inspected before edits", "non-trivial logic leaves one runnable check"),
        source=PONYTAIL_SOURCE,
        license_status=PONYTAIL_LICENSE_STATUS,
    ),
    SkillDefinition(
        "ponytail-review",
        "governance",
        "Review diffs only for over-engineering and identify what can be deleted or replaced.",
        ("findings are deletion-oriented", "correctness review remains separate"),
        source=PONYTAIL_SOURCE,
        license_status=PONYTAIL_LICENSE_STATUS,
    ),
    SkillDefinition(
        "ponytail-audit",
        "governance",
        "Audit the whole repository for unnecessary complexity, wrappers, dependencies, and speculative abstractions.",
        ("findings are ranked by simplification value", "no fixes are applied by the audit"),
        source=PONYTAIL_SOURCE,
        license_status=PONYTAIL_LICENSE_STATUS,
    ),
    SkillDefinition(
        "ponytail-debt",
        "governance",
        "Collect deliberate `ponytail:` shortcuts into a ledger so known ceilings have revisit triggers.",
        ("shortcut markers are traceable", "markers without triggers are flagged"),
        source=PONYTAIL_SOURCE,
        license_status=PONYTAIL_LICENSE_STATUS,
    ),
    SkillDefinition(
        "ponytail-gain",
        "governance",
        "Expose the published ponytail benchmark scoreboard without inventing per-repository savings.",
        ("benchmark numbers are source-scoped", "no live repo savings are fabricated"),
        source=PONYTAIL_SOURCE,
        license_status=PONYTAIL_LICENSE_STATUS,
    ),
    SkillDefinition(
        "ponytail-help",
        "governance",
        "Document ponytail modes, commands, boundaries, and deactivation.",
        ("usage is discoverable", "mode changes are not applied by help output"),
        source=PONYTAIL_SOURCE,
        license_status=PONYTAIL_LICENSE_STATUS,
    ),
)


PONYTAIL_SKILL_IDS = tuple(skill.id for skill in PONYTAIL_SKILLS)


EXTERNAL_ABSORPTION_SKILLS: tuple[SkillDefinition, ...] = (
    SkillDefinition(
        "external_tool_research",
        "research",
        "Record external AI music tools as source-backed research fixtures before any integration.",
        ("source evidence is stored", "paid and API-key tools remain research-only"),
        source="external_absorption_gate",
        ui_label_zh="外部工具研究",
        integration_status="local_first",
    ),
    SkillDefinition(
        "provider_capability_probe",
        "research",
        "Probe provider capabilities through offline fixtures and documented metadata only.",
        ("no real provider call is made", "capability claims have fixture evidence"),
        source="external_absorption_gate",
        ui_label_zh="生成器能力探测",
        integration_status="offline_fixture_only",
    ),
    SkillDefinition(
        "local_tool_gate",
        "governance",
        "Gate local tool use with allowlists, output validation, and local_quota_guard.",
        ("tool is allowlisted", "local_quota_guard is enforced", "outputs have checksums"),
        source="external_absorption_gate",
        ui_label_zh="本地工具门禁",
        integration_status="local_first",
    ),
    SkillDefinition(
        "tool_invocation_audit",
        "governance",
        "Audit every local tool invocation without exposing secrets or commands in the UI.",
        ("audit log records inputs and outputs", "secrets are not displayed"),
        source="external_absorption_gate",
        ui_label_zh="工具调用审计",
        integration_status="local_first",
    ),
    SkillDefinition(
        "prompt_template_optimizer",
        "creation",
        "Optimize prompt templates without changing originality, rights, voice, or delivery hard gates.",
        ("hard gates are preserved", "prompt changes are traceable"),
        source="external_absorption_gate",
        ui_label_zh="Prompt 模板优化",
        integration_status="local_first",
    ),
    SkillDefinition(
        "lyrics_to_song_adapter",
        "generation",
        "Adapt lyrics, emotion profile, and structure into a local fixture-ready song payload.",
        ("lyrics and hook are preserved", "adapter remains fixture-only until licensed"),
        source="external_absorption_gate",
        ui_label_zh="歌词成歌适配",
        integration_status="offline_fixture_only",
    ),
    SkillDefinition(
        "licensed_model_gate",
        "delivery",
        "Block delivery when model license, commercial scope, or source provenance is incomplete.",
        ("noncommercial models block delivery", "complete master remains internal only"),
        source="external_absorption_gate",
        ui_label_zh="模型授权门禁",
        integration_status="local_first",
    ),
    SkillDefinition(
        "offline_provider_benchmark_runner",
        "qa",
        "Run provider benchmarks against offline fixtures only.",
        ("benchmark has fixture id", "real provider call count is zero"),
        source="external_absorption_gate",
        ui_label_zh="离线生成器基准测试",
        integration_status="offline_fixture_only",
    ),
    SkillDefinition(
        "free_local_model_registry",
        "catalog",
        "Catalog free local model candidates without enabling paid or API-key providers.",
        ("paid dependencies are disabled", "API-key tools are research-only"),
        source="external_absorption_gate",
        ui_label_zh="免费本地模型注册表",
        integration_status="local_first",
    ),
    SkillDefinition(
        "research_fixture_importer",
        "research",
        "Import approved research fixtures into the local model registry only after audit approval.",
        ("pending fixtures are not imported", "approved imports keep evidence refs"),
        source="external_absorption_gate",
        ui_label_zh="研究样例导入器",
        integration_status="local_first",
    ),
)


EXTERNAL_ABSORPTION_SKILL_IDS = tuple(skill.id for skill in EXTERNAL_ABSORPTION_SKILLS)


FOUNDATION_SKILLS: tuple[SkillDefinition, ...] = (
    SkillDefinition("creation_brief", "creation", "Turn user intent into a structured music brief.", ("brief is explicit", "downstream agents can use it directly")),
    SkillDefinition("lyric_writing", "creation", "Write or revise lyrics and hooks.", ("lyrics are singable", "lyrics do not copy protected lyrics")),
    SkillDefinition("melody_composition", "creation", "Create motif, hook, and section melodies.", ("hook exists", "melody fits vocal range and audience")),
    SkillDefinition("harmony_composition", "creation", "Create chord movement and harmonic tension.", ("harmony supports melody", "style fit is clear")),
    SkillDefinition("arrangement", "creation", "Plan structure, energy curve, instrumentation, and sections.", ("sections are clear", "duration target is respected")),
    SkillDefinition("generation_router", "generation", "Route every generation through a traceable provider plan.", ("provider is recorded", "prompt and version are recorded")),
    SkillDefinition("candidate_generation", "generation", "Create 3-5 traceable candidates for each task.", ("candidate files or URLs exist", "at least one candidate is playable or downloadable")),
    SkillDefinition("audio_editing", "editing", "Render trim, fade, loop, and version variants.", ("edit decision is stored", "rendered file is downloadable")),
    SkillDefinition("audio_processing", "editing", "Normalize, limit, trim silence, convert format, and write metadata.", ("output is playable", "no clipping is introduced")),
    SkillDefinition("download_export", "asset", "Manage master, loop, lyrics, metadata, and license-pack exports.", ("complete master is available", "master delivery is blocked until gates pass")),
    SkillDefinition("quality_acceptance", "qa", "Score musical quality, audience fit, originality risk, and delivery readiness.", ("subscores are inspectable", "failure codes are actionable")),
    SkillDefinition("loop_rework", "loop", "Map failure codes to targeted rework instead of blind regeneration.", ("owner agent is explicit", "retry budget is bounded")),
    SkillDefinition("originality_guard", "qa", "Flag lyric, melody, voice, sample, and reference-similarity risk.", ("risk is localized", "high risk is not auto-approved")),
    SkillDefinition("rights_configuration", "delivery", "Record owner, use scope, AI disclosure, source, and transfer terms.", ("rights fields are complete", "commercial use is explicit")),
    SkillDefinition("delivery_package", "delivery", "Assemble final files, reports, metadata, and license pack.", ("package is complete", "only unblocked versions are delivered")),
    SkillDefinition("daily_automation", "automation", "Create daily production batches and route failures.", ("10-20 tasks are created", "daily report is written")),
    SkillDefinition("ops_report", "automation", "Summarize production, failures, risk, cost, and next actions.", ("failure rates are visible", "next-day actions are explicit")),
    *PONYTAIL_SKILLS,
    *EXTERNAL_ABSORPTION_SKILLS,
)


AGENTS: tuple[AgentDefinition, ...] = (
    AgentDefinition("Daily Production Planner", "plan", ("daily_automation",), "Create the daily 10-20 task plan.", ("task count and styles are explicit",)),
    AgentDefinition("Brief Parser", "brief", ("creation_brief",), "Convert intent into hard music constraints.", ("duration, mode, audience, forbidden items are present",)),
    AgentDefinition("Style Researcher", "brief", ("creation_brief",), "Describe style rhythm, harmony, timbre, and forbidden directions.", ("style report can guide creation",)),
    AgentDefinition("Audience Profiler", "brief", ("quality_acceptance",), "Define listener expectations and fit criteria.", ("audience criteria can be scored",)),
    AgentDefinition("Creative Director", "brief", ("creation_brief",), "Align theme, emotional arc, and creative direction.", ("direction does not override the brief",)),
    AgentDefinition("Lyric Writer", "lyrics", ("lyric_writing",), "Create lyric draft and hooks.", ("sections and hook are marked",)),
    AgentDefinition("Lyric Editor", "lyrics", ("lyric_writing", "originality_guard"), "Check meaning, rhyme, singability, and lyric risk.", ("lyrics are singable and risk-marked",)),
    AgentDefinition("Melody Composer", "composition", ("melody_composition",), "Create motif, hook, and section melodies.", ("hook and range are documented",)),
    AgentDefinition("Harmony Composer", "composition", ("harmony_composition",), "Design chord progressions and harmonic motion.", ("harmony supports melody",)),
    AgentDefinition("Rhythm Designer", "composition", ("arrangement",), "Design groove, BPM feel, and rhythmic pattern.", ("rhythm supports target scene",)),
    AgentDefinition("Structure Arranger", "arrangement", ("arrangement",), "Assemble sections and timing.", ("song form and timestamps are clear",)),
    AgentDefinition("Arrangement Producer", "arrangement", ("arrangement",), "Plan instruments, layers, transitions, and stem intent.", ("arrangement has main and support layers",)),
    AgentDefinition("Sound Designer", "arrangement", ("arrangement", "rights_configuration"), "Choose traceable sounds, synths, and samples.", ("sound sources are traceable",)),
    AgentDefinition("Vocal Designer", "arrangement", ("melody_composition", "originality_guard"), "Plan voice range, delivery, harmony, and adlibs.", ("no real singer cloning risk is introduced",)),
    AgentDefinition("Generation Router", "generation", ("generation_router",), "Choose provider, prompt, parameters, local quota guard, and fallback.", ("route is traceable",)),
    AgentDefinition("Generation Executor", "generation", ("candidate_generation",), "Generate audio candidates and logs.", ("files or URLs are stored",)),
    AgentDefinition("Audio Analyzer", "qa", ("audio_processing", "quality_acceptance"), "Measure duration, peaks, BPM, key, silence, and technical issues.", ("metrics are inspectable",)),
    AgentDefinition("Originality Guard", "qa", ("originality_guard",), "Check lyric, melody, structure, voice, and sample similarity risk.", ("risk flags have evidence",)),
    AgentDefinition("Music Quality Judge", "qa", ("quality_acceptance",), "Score quality, catchiness, structure, audience fit, and readiness.", ("scores produce pass or rework",)),
    AgentDefinition("Rework Orchestrator", "loop", ("loop_rework",), "Route clear failures back to the owner agent with retry limits.", ("failure owner and budget are explicit",)),
    AgentDefinition("Mix Engineer", "editing", ("audio_processing",), "Balance loudness, EQ, space, and dynamics.", ("mix does not rewrite the song",)),
    AgentDefinition("Mastering Engineer", "editing", ("audio_processing", "download_export"), "Render final loudness and format variants.", ("master specs are met",)),
    AgentDefinition("Catalog Manager", "asset", ("download_export",), "Archive metadata, versions, prompts, and files.", ("asset can be searched and restored",)),
    AgentDefinition("Rights Configurator", "delivery", ("rights_configuration",), "Record model, material, voice, lyric, and usage rights.", ("rights are explicit",)),
    AgentDefinition("Delivery Packager", "delivery", ("delivery_package",), "Assemble final package after QA and rights gates.", ("blocked assets are excluded",)),
    AgentDefinition("Ops Reporter", "automation", ("ops_report",), "Report capacity, failures, risk, and next actions.", ("daily health is visible",)),
)


REWORK_RULES: tuple[ReworkRule, ...] = (
    ReworkRule("BAD_DURATION", "Structure Arranger", "arrangement", "adjust section lengths and regenerate candidate", ("theme", "genre"), ("duration_sec",), 1),
    ReworkRule("LYRIC_MISSING", "Lyric Writer", "lyric_writing", "create singable lyrics before regeneration", ("theme", "mode"), ("lyrics_input",), 1),
    ReworkRule("STRUCTURE_TOO_SHORT", "Brief Parser", "creation_brief", "increase duration and clarify structure", ("theme", "genre"), ("duration_sec",), 1),
    ReworkRule("ORIGINALITY_REVIEW_REQUIRED", "Originality Guard", "originality_guard", "review reference risk before delivery", ("theme", "use_case"), ("reference_profile_id",), 1),
    ReworkRule("WEAK_HOOK", "Melody Composer", "melody_composition", "strengthen the hook and motif repetition", ("theme", "genre", "lyrics_input"), ("bpm", "key"), 1),
    ReworkRule("AUDIENCE_MISMATCH", "Audience Profiler", "quality_acceptance", "restate listener standard and adapt the creation brief", ("theme", "use_case"), ("audience", "mood"), 1),
    ReworkRule("TECHNICAL_AUDIO_FAIL", "Audio Analyzer", "audio_processing", "inspect source audio and route to processing or regeneration", ("version_id",), ("audio_processing_plan",), 1),
    ReworkRule("DUPLICATE_CANDIDATE", "Generation Router", "candidate_generation", "regenerate duplicate candidate with unique seed, prompt, and audio artifact", ("theme", "lyrics", "structure", "emotion_profile"), ("seed", "prompt_snapshot", "generation_route", "audio_path", "export_files"), 1),
    ReworkRule("LYRIC_TOO_SHORT", "Lyric Writer", "lyric_writing", "expand lyrics to full song sections", ("theme", "emotion_profile"), ("lyrics_input",), 1),
    ReworkRule("LYRIC_NO_HOOK", "Lyric Writer", "lyric_writing", "write an explicit hook line", ("theme", "genre"), ("lyrics_input",), 1),
    ReworkRule("LYRIC_NO_CHORUS", "Lyric Writer", "lyric_writing", "add chorus sections", ("theme", "genre"), ("lyrics_input",), 1),
    ReworkRule("LYRIC_NO_BRIDGE", "Lyric Writer", "lyric_writing", "add a bridge section", ("theme", "genre"), ("lyrics_input",), 1),
    ReworkRule("LYRIC_NO_FINAL_CHORUS", "Lyric Writer", "lyric_writing", "add an intensified final chorus", ("theme", "genre"), ("lyrics_input",), 1),
    ReworkRule("LYRIC_UNSINGABLE", "Lyric Editor", "lyric_writing", "repair line length, stress, and breath points", ("theme", "hook"), ("lyrics_input",), 1),
    ReworkRule("EMOTION_MISMATCH", "Lyric Emotion Agent", "quality_acceptance", "realign emotion arc and imagery", ("theme", "category"), ("mood", "lyrics_input"), 1),
    ReworkRule("ORIGINALITY_HIGH", "Originality Guard", "originality_guard", "block automatic rework until human review", ("theme", "use_case"), (), 0, False, True),
    ReworkRule("UNKNOWN_FAILURE", "Rework Orchestrator", "loop_rework", "inspect failure before retry", (), (), 0, False, True),
    ReworkRule("METADATA_MISSING", "Catalog Manager", "download_export", "repair metadata only; do not regenerate music", ("task_id", "work_id", "version_id"), ("metadata",), 0, False, False, True),
    ReworkRule("RIGHTS_MISSING", "Rights Configurator", "rights_configuration", "configure rights; do not regenerate music", ("task_id", "work_id"), ("rights_configuration",), 0, False, False, True),
)


CORE_GATE_SKILL_IDS = (
    "generation_router",
    "quality_acceptance",
    "loop_rework",
    "originality_guard",
    "rights_configuration",
    "download_export",
)


def get_rework_rule(failure_code: str) -> ReworkRule | None:
    for rule in REWORK_RULES:
        if rule.failure_code == failure_code:
            return rule
    return None


def foundation_skill_ids() -> set[str]:
    return {skill.id for skill in FOUNDATION_SKILLS}


def agent_names() -> set[str]:
    return {agent.name for agent in AGENTS}


def skills_snapshot() -> dict[str, object]:
    return {
        "foundation_skills": [asdict(skill) for skill in FOUNDATION_SKILLS],
        "agents": [asdict(agent) for agent in AGENTS],
        "rework_rules": [asdict(rule) for rule in REWORK_RULES],
        "core_gate_skill_ids": list(CORE_GATE_SKILL_IDS),
    }
