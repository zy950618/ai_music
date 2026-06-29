from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    layer: str
    purpose: str
    acceptance: tuple[str, ...]


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
    SkillDefinition("download_export", "asset", "Manage preview, master, loop, lyrics, metadata, and license-pack exports.", ("preview is available", "master is blocked until gates pass")),
    SkillDefinition("quality_acceptance", "qa", "Score musical quality, audience fit, originality risk, and delivery readiness.", ("subscores are inspectable", "failure codes are actionable")),
    SkillDefinition("loop_rework", "loop", "Map failure codes to targeted rework instead of blind regeneration.", ("owner agent is explicit", "retry budget is bounded")),
    SkillDefinition("originality_guard", "qa", "Flag lyric, melody, voice, sample, and reference-similarity risk.", ("risk is localized", "high risk is not auto-approved")),
    SkillDefinition("rights_configuration", "delivery", "Record owner, use scope, AI disclosure, source, and transfer terms.", ("rights fields are complete", "commercial use is explicit")),
    SkillDefinition("delivery_package", "delivery", "Assemble final files, reports, metadata, and license pack.", ("package is complete", "only unblocked versions are delivered")),
    SkillDefinition("daily_automation", "automation", "Create daily production batches and route failures.", ("10-20 tasks are created", "daily report is written")),
    SkillDefinition("ops_report", "automation", "Summarize production, failures, risk, cost, and next actions.", ("failure rates are visible", "next-day actions are explicit")),
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
    AgentDefinition("Generation Router", "generation", ("generation_router",), "Choose provider, prompt, parameters, budget, and fallback.", ("route is traceable",)),
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
    ReworkRule("ORIGINALITY_HIGH", "Originality Guard", "originality_guard", "block automatic rework until human review", ("theme", "use_case"), (), 0, False, True),
    ReworkRule("UNKNOWN_FAILURE", "Rework Orchestrator", "loop_rework", "inspect failure before retry", (), (), 0, False, True),
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
