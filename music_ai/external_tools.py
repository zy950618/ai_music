from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import ExternalToolEvaluation, LocalToolGate, ProviderBenchmarkResult, ResearchFixture, ResearchSource


LOCAL_TOOL_GATE_LABEL_ZH = "本地工具门禁"
LOCAL_QUOTA_GUARD_LABEL_ZH = "本地调用限制"
STATUS_LABELS_ZH = {
    "local_candidate": "本地候选",
    "analysis_skill": "分析技能",
    "audio_to_midi_skill": "音频转 MIDI 技能",
    "audio_analysis_skill": "音频特征分析技能",
    "midi_musicology_skill": "MIDI 乐理分析技能",
    "skill_template_only": "Skill 结构参考",
    "workflow_reference": "流程参考",
    "research_only": "仅研究",
    "reject": "拒绝接入",
}

EXTERNAL_ABSORPTION_LOOP = (
    {"key": "discover", "label_zh": "发现"},
    {"key": "verify_source", "label_zh": "验证来源"},
    {"key": "free_paid_gate", "label_zh": "免费/付费门禁"},
    {"key": "license_gate", "label_zh": "授权门禁"},
    {"key": "security_gate", "label_zh": "安全门禁"},
    {"key": "capability_probe", "label_zh": "能力探测"},
    {"key": "local_feasibility", "label_zh": "本地可行性"},
    {"key": "sandbox_fixture", "label_zh": "沙盒样例"},
    {"key": "qa_gate", "label_zh": "质量门禁"},
    {"key": "originality_gate", "label_zh": "原创性门禁"},
    {"key": "rights_gate", "label_zh": "权利门禁"},
    {"key": "decision", "label_zh": "接受/仅研究/拒绝接入"},
    {"key": "evidence_manifest", "label_zh": "证据清单"},
    {"key": "evolution_proposal", "label_zh": "进化提案"},
)

ALLOWED_OUTPUT_EXTENSIONS = (".wav", ".mp3", ".aac", ".midi", ".mid", ".stems", ".json", ".txt", ".md")
HARD_GATE_KEYS = {
    "originality_hard_gate",
    "rights_hard_gate",
    "licensed_model_gate",
    "voice_clone_policy",
    "delivery_package_integrity",
    "commercial_use_allowed",
    "paid_dependency",
    "requires_api_key",
    "captcha_bypass",
    "access_bypass",
    "retry_limits",
    "ai_disclosure_required",
    "reference_policy",
}


def _tool(
    tool_id: str,
    name: str,
    ui_label_zh: str,
    tool_category: str,
    accepted_level: str,
    integration_status: str,
    absorbed_features: list[str],
    optimization_lessons: list[str],
    strong_constraints: list[str],
    rights_risks: list[str],
    security_risks: list[str],
    integration_risks: list[str],
    source_url: str,
    paid_dependency: bool = False,
    requires_api_key: bool = False,
    commercial_use_allowed: bool = False,
    license_status: str = "needs_review",
) -> ExternalToolEvaluation:
    forced_research = paid_dependency or requires_api_key
    status = "research_only" if forced_research and integration_status != "reject" else integration_status
    enabled = not forced_research and status not in {"research_only", "reject"}
    blocked_reasons: list[str] = []
    if paid_dependency:
        blocked_reasons.append("paid_dependency")
    if requires_api_key:
        blocked_reasons.append("requires_api_key")
    if status == "research_only":
        blocked_reasons.append("research_only")
    if status == "reject":
        blocked_reasons.append("reject")
    return ExternalToolEvaluation(
        tool_id=tool_id,
        name=name,
        ui_label_zh=ui_label_zh,
        tool_category=tool_category,
        accepted_level=accepted_level,
        integration_status=status,
        absorbed_features=absorbed_features,
        optimization_lessons=optimization_lessons,
        strong_constraints=strong_constraints,
        rights_risks=rights_risks,
        security_risks=security_risks,
        integration_risks=integration_risks,
        source_url=source_url,
        paid_dependency=paid_dependency,
        requires_api_key=requires_api_key,
        enabled=enabled,
        production_enabled=False,
        commercial_use_allowed=commercial_use_allowed,
        license_status=license_status,
        local_quota_guard={"max_invocations_per_run": 0 if not enabled else 3, "timeout_sec": 0 if not enabled else 600},
        blocked_reasons=blocked_reasons,
    )


EXTERNAL_TOOL_EVALUATIONS: tuple[ExternalToolEvaluation, ...] = (
    _tool(
        "ace_step",
        "ACE-Step / ACE-Step 1.5",
        "ACE-Step 本地整歌候选",
        "full_song_generation",
        "P1",
        "local_candidate",
        ["整歌生成链路", "长结构控制", "提示词参数化"],
        ["把整歌候选作为离线 fixture，不直接升为交付成品", "把结构、情绪、歌词和 seed 写入审计记录"],
        ["仅允许本地/离线样例", "输出必须进入 QA、原创性和授权门禁"],
        ["模型许可证与权重来源需要复核", "不能推断可商用"],
        ["禁止下载未知权重", "禁止执行未审计脚本"],
        ["本地依赖重、运行环境需隔离"],
        "https://github.com/ace-step/ACE-Step",
    ),
    _tool(
        "yue",
        "YuE",
        "YuE 歌词成歌候选",
        "lyrics_to_song",
        "P1",
        "local_candidate",
        ["歌词到歌曲流程", "长歌词分段", "人声歌曲结构"],
        ["先验证歌词结构和可唱性，再进入本地样例", "歌词、hook、emotion profile 必须随输出保存"],
        ["不得复制真实歌词或声线", "不得直接把输出作为正式交付"],
        ["歌词与声线授权需人工复核", "模型许可证需复核"],
        ["禁止使用未授权人声克隆", "禁止导入不明来源 sample"],
        ["本地推理成本和依赖复杂度较高"],
        "https://github.com/multimodal-art-projection/YuE",
    ),
    _tool(
        "diffrhythm",
        "DiffRhythm",
        "DiffRhythm 快速候选生成",
        "candidate_generation",
        "P1",
        "local_candidate",
        ["快速生成候选", "节奏/旋律初稿参考"],
        ["只用于候选层 benchmark，不能绕过质量评分", "保留 prompt 和随机种子"],
        ["离线样例优先", "必须记录 checksum"],
        ["许可证与商用范围待复核"],
        ["禁止执行未审计下载脚本"],
        ["输出质量和结构稳定性需要离线基准测试"],
        "https://github.com/ASLP-lab/DiffRhythm",
    ),
    _tool(
        "audiocraft_musicgen_jasco",
        "AudioCraft / MusicGen / JASCO",
        "AudioCraft 音频生成研究",
        "audio_generation_research",
        "P2",
        "research_only",
        ["文本到音乐", "条件生成", "本地模型 adapter 思路"],
        ["默认只吸收 router/adapter 经验", "非商用权重不能进入正式交付"],
        ["许可证确认前仅研究", "不用于歌词成歌正式链路"],
        ["默认权重可能非商用", "provider 或权重许可证需复核"],
        ["模型文件来源需要校验"],
        ["本地 GPU、依赖和许可差异较大"],
        "https://github.com/facebookresearch/audiocraft",
        commercial_use_allowed=False,
        license_status="noncommercial_or_needs_review",
    ),
    _tool(
        "demucs",
        "Demucs",
        "Demucs 分轨分析",
        "stem_analysis",
        "P0",
        "analysis_skill",
        ["分轨分析", "stem QA", "混音问题定位"],
        ["作为分析技能，不把外部分轨结果当交付来源"],
        ["只处理项目内已有音频", "输出必须记录来源和 checksum"],
        ["输入音频权利必须已知"],
        ["禁止处理未知版权音频作为素材"],
        ["分轨输出不能绕过原创性和授权门禁"],
        "https://github.com/facebookresearch/demucs",
    ),
    _tool(
        "basic_pitch",
        "Basic Pitch",
        "Basic Pitch 音频转 MIDI",
        "audio_to_midi",
        "P0",
        "audio_to_midi_skill",
        ["音频转 MIDI", "旋律轮廓分析", "hook 位置辅助"],
        ["用于分析项目内音频，不作为旋律复制工具"],
        ["输入必须是授权或项目生成音频", "MIDI 输出需标注分析用途"],
        ["分析第三方歌曲会带来复制风险"],
        ["禁止用作复刻真实歌曲旋律"],
        ["多音轨识别准确度需 QA 复核"],
        "https://github.com/spotify/basic-pitch",
    ),
    _tool(
        "librosa",
        "librosa",
        "librosa 音频特征分析",
        "audio_analysis",
        "P0",
        "audio_analysis_skill",
        ["BPM、key、谱特征、响度辅助分析"],
        ["优先沉淀可复测的本地分析指标"],
        ["只分析本地已授权音频", "指标不能伪装成真实用户研究"],
        ["输入来源必须可追踪"],
        ["无直接外部安全调用风险"],
        ["不同版本指标可能漂移，需要记录版本"],
        "https://librosa.org/doc/latest/index.html",
    ),
    _tool(
        "pretty_midi_music21",
        "pretty_midi / music21",
        "MIDI 乐理分析",
        "midi_musicology",
        "P0",
        "midi_musicology_skill",
        ["MIDI 解析", "音域/和声/结构分析"],
        ["用于质量和可唱性分析", "把乐理结论写入 QA evidence"],
        ["输入 MIDI 来源必须合法", "不能复刻真实作品"],
        ["第三方 MIDI 版权需复核"],
        ["无网络调用，但需校验文件扩展和 checksum"],
        ["复杂乐理结论需要人工抽查"],
        "https://github.com/craffel/pretty-midi",
    ),
    _tool(
        "minimax_music_skill",
        "MiniMax Music Skill",
        "MiniMax 音乐 Skill 结构参考",
        "skill_template",
        "P0",
        "skill_template_only",
        ["结构化音乐 prompt", "控制字段分层", "模板化输入"],
        ["只吸收 Skill 结构，不调用 MiniMax API"],
        ["不能把平台能力当本地能力", "不得请求账号/API Key"],
        ["平台条款和输出权利不可推断"],
        ["禁止生产调用"],
        ["只能作为模板参考"],
        "https://github.com/minimaxir",
    ),
    _tool(
        "claude_ai_music_skills",
        "claude-ai-music-skills",
        "Claude 音乐制作 Skill 流程参考",
        "workflow_reference",
        "P0",
        "workflow_reference",
        ["音乐制作工作流", "QA 前置", "发布前检查"],
        ["吸收流程，不吸收分发平台方向"],
        ["不复制外部完整文本或样例音频"],
        ["来源内容许可证需复核"],
        ["禁止把参考工作流变成素材抓取"],
        ["流程需映射到本项目门禁"],
        "https://github.com/anthropics/skills",
    ),
    _tool(
        "google_lyria_3",
        "Google Lyria 3",
        "Google Lyria 研究资料",
        "provider_research",
        "research_only",
        "research_only",
        ["高质量音乐生成能力研究", "prompt/controls 设计参考"],
        ["只做研究记录，不作为当前进化方向"],
        ["需要 API/账号/额度时保持仅研究"],
        ["平台条款与商业权利不可推断"],
        ["禁止 API Key 调用"],
        ["闭源平台不可本地优先落地"],
        "https://deepmind.google/technologies/lyria/",
        paid_dependency=True,
        requires_api_key=True,
    ),
    _tool(
        "elevenlabs_mcp",
        "ElevenLabs MCP",
        "ElevenLabs MCP 研究资料",
        "mcp_research",
        "research_only",
        "research_only",
        ["MCP 能力描述", "音频 API workflow 参考"],
        ["只记录能力和风险，不连接账号"],
        ["API Key/账号依赖保持仅研究"],
        ["声音与平台授权需复核"],
        ["禁止真实账号调用"],
        ["MCP 连接不能进入生产链路"],
        "https://elevenlabs.io/docs",
        paid_dependency=True,
        requires_api_key=True,
    ),
    _tool(
        "replicate_mcp",
        "Replicate MCP",
        "Replicate MCP 研究资料",
        "mcp_research",
        "research_only",
        "research_only",
        ["多模型调用模式", "provider catalog 参考"],
        ["只吸收 registry/benchmark 设计，不调用 token"],
        ["API token 依赖保持仅研究"],
        ["模型各自许可证差异大"],
        ["禁止 token 调用"],
        ["不能把平台模型列表当本地能力"],
        "https://replicate.com/docs",
        paid_dependency=True,
        requires_api_key=True,
    ),
    _tool(
        "fal_ai_mcp",
        "fal.ai MCP",
        "fal.ai MCP 研究资料",
        "mcp_research",
        "research_only",
        "research_only",
        ["异步推理/队列模式", "provider benchmark 参考"],
        ["只吸收队列和审计模式，不调用 API"],
        ["API Key/额度依赖保持仅研究"],
        ["模型/输出商业授权需逐项复核"],
        ["禁止 API Key 调用"],
        ["平台执行不可本地优先"],
        "https://fal.ai/docs",
        paid_dependency=True,
        requires_api_key=True,
    ),
    _tool(
        "stable_audio_3",
        "Stable Audio 3",
        "Stable Audio 研究资料",
        "provider_research",
        "P2",
        "research_only",
        ["高质量音频生成研究", "prompt 参数和授权审计参考"],
        ["许可证/本地可行性确认前保持仅研究"],
        ["不得默认商用", "不得接入付费/API 平台"],
        ["平台条款与模型许可证需复核"],
        ["禁止未授权下载或调用"],
        ["本地可行性未验证"],
        "https://stability.ai/stable-audio",
        paid_dependency=True,
        requires_api_key=True,
    ),
    _tool(
        "unofficial_suno_captcha_bypass",
        "unofficial Suno API / CAPTCHA bypass projects",
        "拒绝接入",
        "access_bypass",
        "reject",
        "reject",
        ["反面样例：不吸收生产调用"],
        ["把验证码、登录、付费墙绕过作为硬拒绝信号"],
        ["禁止 unofficial provider 生产调用", "禁止绕过验证码/登录/付费墙"],
        ["授权不可确认", "输出权利不可追踪"],
        ["access_bypass_risk", "captcha_bypass_risk"],
        ["无法进入合法审计链路"],
        "",
    ),
)

RESEARCH_FIXTURES: tuple[ResearchFixture, ...] = tuple(
    ResearchFixture(
        fixture_id=f"fixture_{tool.tool_id}",
        tool_id=tool.tool_id,
        ui_label_zh=tool.ui_label_zh,
        source_url=tool.source_url,
        source_type="provider_docs" if tool.accepted_level == "research_only" else "github",
        audit_status="rejected" if tool.integration_status == "reject" else "needs_review",
        imported_to="model_registry" if tool.accepted_level in {"P0", "P1", "P2"} else "research_center",
        evidence_summary="Seed fixture only; no API calls, downloads, logins, or paid provider invocations were performed.",
        allowed_usage="research fixture and local gate evaluation only",
        risk_flags=list(dict.fromkeys(tool.rights_risks + tool.security_risks + tool.integration_risks)),
    )
    for tool in EXTERNAL_TOOL_EVALUATIONS
)


def external_tool_evaluations() -> tuple[ExternalToolEvaluation, ...]:
    return EXTERNAL_TOOL_EVALUATIONS


def research_fixtures() -> tuple[ResearchFixture, ...]:
    return RESEARCH_FIXTURES


def tool_by_id(tool_id: str) -> ExternalToolEvaluation:
    for tool in EXTERNAL_TOOL_EVALUATIONS:
        if tool.tool_id == tool_id:
            return tool
    raise KeyError(tool_id)


def evaluate_local_tool_gate(
    tool: ExternalToolEvaluation,
    allowlist: set[str] | list[str] | tuple[str, ...],
    local_quota_used: int = 0,
    max_invocations_per_run: int | None = None,
) -> LocalToolGate:
    allowlist_set = set(allowlist)
    local_quota_guard = dict(tool.local_quota_guard)
    if max_invocations_per_run is not None:
        local_quota_guard["max_invocations_per_run"] = max_invocations_per_run
    limit = local_quota_guard.get("max_invocations_per_run", 0)
    blocked_reasons: list[str] = []
    if tool.tool_id not in allowlist_set:
        blocked_reasons.append("not_in_allowlist")
    if tool.paid_dependency:
        blocked_reasons.append("paid_dependency")
    if tool.requires_api_key:
        blocked_reasons.append("requires_api_key")
    if tool.integration_status == "research_only":
        blocked_reasons.append("research_only")
    if tool.integration_status == "reject":
        blocked_reasons.append("reject")
    if local_quota_used >= limit:
        blocked_reasons.append("local_quota_guard_exceeded")
    return LocalToolGate(
        gate_id=f"gate_{tool.tool_id}",
        tool_id=tool.tool_id,
        ui_label_zh=LOCAL_TOOL_GATE_LABEL_ZH,
        allowlist=sorted(allowlist_set),
        local_quota_guard=local_quota_guard,
        allowed_extensions=list(ALLOWED_OUTPUT_EXTENSIONS),
        requires_checksum=True,
        offline_fixture_only=True,
        network_access_allowed=False,
        passed=not blocked_reasons,
        blocked_reasons=blocked_reasons,
    )


def validate_tool_output(path: Path | str, checksum: str | None, allowed_extensions: tuple[str, ...] = ALLOWED_OUTPUT_EXTENSIONS) -> dict[str, Any]:
    output_path = Path(path)
    reasons: list[str] = []
    if output_path.suffix.lower() not in allowed_extensions:
        reasons.append("extension_not_allowed")
    if not checksum:
        reasons.append("checksum_missing")
    elif output_path.exists():
        actual = hashlib.sha256(output_path.read_bytes()).hexdigest()
        if actual != checksum:
            reasons.append("checksum_mismatch")
    return {
        "passed": not reasons,
        "blocked_reasons": reasons,
        "allowed_extensions": list(allowed_extensions),
        "requires_checksum": True,
        "checksum": checksum,
    }


def offline_benchmark_fixture(tool_id: str, fixture_id: str) -> ProviderBenchmarkResult:
    return ProviderBenchmarkResult(
        benchmark_id=f"bench_{tool_id}_{fixture_id}",
        tool_id=tool_id,
        fixture_id=fixture_id,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        offline_fixture_only=True,
        metrics={"fixture_count": 1.0, "real_provider_calls": 0.0},
        notes="Offline fixture benchmark only; no provider invocation.",
    )


def delivery_gate_for_tool(tool: ExternalToolEvaluation) -> dict[str, Any]:
    blocked = (
        tool.integration_status in {"research_only", "reject"}
        or tool.paid_dependency
        or tool.requires_api_key
        or not tool.commercial_use_allowed
        or tool.license_status != "commercial_verified"
    )
    reasons = list(tool.blocked_reasons)
    if not tool.commercial_use_allowed:
        reasons.append("noncommercial_or_unverified")
    if tool.license_status != "commercial_verified":
        reasons.append("license_not_verified")
    return {
        "internal_master_allowed": tool.integration_status != "reject",
        "delivery_allowed": not blocked,
        "blocked_reasons": sorted(set(reasons)),
        "rights_status": "blocked" if blocked else "configured",
    }


def validate_prompt_optimizer_change(after: dict[str, Any]) -> dict[str, Any]:
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in HARD_GATE_KEYS:
                    found.append(key)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(after)
    return {"passed": not found, "blocked_reasons": sorted(set(found))}


def can_import_research_source_to_model_registry(source: ResearchSource) -> bool:
    return source.audit_status == "approved" and source.imported_to == "model_registry"


def can_import_research_fixture_to_model_registry(fixture: ResearchFixture) -> bool:
    return fixture.audit_status == "approved" and fixture.imported_to == "model_registry"


def absorption_summary() -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for tool in EXTERNAL_TOOL_EVALUATIONS:
        groups.setdefault(tool.accepted_level, []).append(tool.tool_id)
    return {
        "ui_labels": {
            "local_tool_gate": LOCAL_TOOL_GATE_LABEL_ZH,
            "local_quota_guard": LOCAL_QUOTA_GUARD_LABEL_ZH,
            "research_only": STATUS_LABELS_ZH["research_only"],
            "reject": STATUS_LABELS_ZH["reject"],
        },
        "loop": list(EXTERNAL_ABSORPTION_LOOP),
        "tools": [asdict(tool) for tool in EXTERNAL_TOOL_EVALUATIONS],
        "research_fixtures": [asdict(fixture) for fixture in RESEARCH_FIXTURES],
        "groups": groups,
    }
