from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .automation import DailyAutomationScheduler, DailyAutomationService
from .engine import CreationEngine
from .external_tools import absorption_summary
from .generation import GenerationProviderRegistry
from .models import MusicCreationRequest, ResearchSource, RightsConfiguration
from .repository import ResultRepository, result_from_dict
from .skills import get_rework_rule, skills_snapshot


STATIC_DIR = Path(__file__).resolve().parent / "static"
WORKBENCH_HTML_PATH = STATIC_DIR / "workbench.html"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit_event(action: str, actor: str = "workbench", **details: Any) -> dict[str, Any]:
    return {
        "audit_id": f"audit_{uuid.uuid4().hex[:10]}",
        "createdAt": _utc_now_iso(),
        "action": action,
        "actor": actor,
        "details": details,
    }


def render_workbench_html() -> str:
    return WORKBENCH_HTML_PATH.read_text(encoding="utf-8")


def _version_loop_state(task: dict[str, Any], version: dict[str, Any]) -> dict[str, Any]:
    version_id = version.get("version_id")
    failure_codes = version.get("failure_codes", [])
    handoffs: list[dict[str, Any]] = []

    for failure_code in failure_codes:
        rule = get_rework_rule(failure_code)
        if rule is None:
            handoffs.append(
                {
                    "failure_code": failure_code,
                    "target_agent": "Rework Orchestrator",
                    "target_skill": "loop_rework",
                    "action": "inspect and define a repair plan",
                    "auto_rework_allowed": False,
                    "requires_human_review": True,
                    "delivery_block_only": False,
                }
            )
            continue
        handoffs.append(
            {
                "failure_code": failure_code,
                "target_agent": rule.target_agent,
                "target_skill": rule.skill_id,
                "action": rule.action,
                "auto_rework_allowed": rule.auto_rework_allowed,
                "requires_human_review": rule.requires_human_review,
                "delivery_block_only": rule.delivery_block_only,
                "preserve_fields": list(rule.preserve_fields),
                "mutable_fields": list(rule.mutable_fields),
                "retry_budget": rule.retry_budget,
            }
        )

    if handoffs:
        primary = handoffs[0]
        loop_stage = "human_review_required" if primary["requires_human_review"] else "auto_rework"
        if primary["delivery_block_only"] and task.get("rights_status") == "missing":
            loop_stage = "rights_blocked"
            next_agent = "Rights Configurator"
            next_action = "configure rights before delivery"
        else:
            next_agent = primary["target_agent"]
            next_action = primary["action"]
    elif task.get("rights_status") == "missing":
        loop_stage = "delivery_blocked"
        next_agent = "Rights Configurator"
        next_action = "configure rights package first"
    elif version.get("status") == "qa_fail":
        loop_stage = "rework_decide"
        next_agent = "Rework Orchestrator"
        next_action = "decide targeted rework"
    else:
        loop_stage = "ready_for_packaging"
        next_agent = "Delivery Packager"
        next_action = "create delivery package after final QA"

    hard_gate_pass = version.get("status") == "qa_pass" and not failure_codes
    return {
        "version_id": version_id,
        "failure_codes": failure_codes,
        "rework_targets": handoffs,
        "next_agent": next_agent,
        "next_action": next_action,
        "decision": loop_stage,
        "hard_gate_pass": bool(hard_gate_pass),
        "score_total": version.get("score_total"),
    }


def _decorate_task(task: dict[str, Any]) -> dict[str, Any]:
    task_copy = dict(task)
    versions = []
    for version in task_copy.get("versions", []):
        version_copy = dict(version)
        version_copy["loop_state"] = _version_loop_state(task_copy, version_copy)
        versions.append(version_copy)
    task_copy["versions"] = versions
    return task_copy


def _ops_report(workspace: Path, repository: ResultRepository, scheduler: DailyAutomationScheduler, automation: DailyAutomationService) -> dict[str, Any]:
    tasks = repository.list_results()
    decorated = [_decorate_task(task) for task in tasks]
    version_count = sum(len(task.get("versions", [])) for task in tasks)
    fail_count = sum(1 for task in decorated for version in task.get("versions", []) if (version.get("score_total") or 0) < 80 or version.get("failure_codes"))
    pass_count = max(0, version_count - fail_count)
    failure_counter: Counter[str] = Counter()
    agent_counter: Counter[str] = Counter()
    provider_counter: Counter[str] = Counter()
    provider_fail_counter: Counter[str] = Counter()
    lyric_failure_codes = {
        "LYRIC_TOO_SHORT",
        "LYRIC_NO_HOOK",
        "LYRIC_NO_CHORUS",
        "LYRIC_NO_BRIDGE",
        "LYRIC_NO_FINAL_CHORUS",
        "LYRIC_UNSINGABLE",
    }
    emotion_failure_codes = {"EMOTION_MISMATCH"}
    lyric_failure_counter: Counter[str] = Counter()
    emotion_failure_counter: Counter[str] = Counter()
    score_values: list[int] = []
    today = datetime.now().date().isoformat()
    tasks_created_today = 0
    versions_generated_today = 0
    for task in decorated:
        if str(task.get("createdAt") or "").startswith(today):
            tasks_created_today += 1
        for version in task.get("versions", []):
            score = int(version.get("score_total") or 0)
            score_values.append(score)
            if str(version.get("generatedAt") or "").startswith(today):
                versions_generated_today += 1
            provider = str(version.get("model_provider") or "unknown")
            provider_counter[provider] += 1
            if score < 80 or version.get("failure_codes"):
                provider_fail_counter[provider] += 1
            for failure_code in version.get("failure_codes", []):
                failure_counter[str(failure_code)] += 1
                if failure_code in lyric_failure_codes:
                    lyric_failure_counter[str(failure_code)] += 1
                if failure_code in emotion_failure_codes:
                    emotion_failure_counter[str(failure_code)] += 1
            next_agent = (version.get("loop_state") or {}).get("next_agent")
            if next_agent:
                agent_counter[next_agent] += 1

    rework_queue = automation.build_rework_queue()
    rework_queue_summary = automation._rework_budget_summary()
    rework_history = ResultRepository(workspace).rework_history()
    rework_events = rework_history["events"]
    rework_success = sum(1 for event in rework_events if (event.get("created_score_total") or 0) >= 80)
    latest_daily = [_compact_daily_report(report) for report in automation.latest_daily_reports()[:1]]
    scheduler_state_path = workspace / "scheduler" / "state.json"
    scheduler_state: dict[str, Any] = {}
    if scheduler_state_path.exists():
        with scheduler_state_path.open("r", encoding="utf-8") as handle:
            scheduler_state = json.load(handle)
    rights_missing = sum(1 for task in tasks if task.get("rights_status") == "missing")
    rights_configured = sum(1 for task in tasks if task.get("rights_status") == "configured")
    rights_review_required = sum(1 for task in tasks if task.get("rights_status") == "review_required")
    rights_blocked_status = sum(1 for task in tasks if task.get("rights_status") == "blocked")
    rights_blocked = rights_missing + rights_review_required + rights_blocked_status
    delivery_package_count = sum(
        1
        for task in decorated
        for version in task.get("versions", [])
        for export in version.get("export_files", [])
        if export.get("kind") == "delivery_package" and export.get("ready")
    )
    provider_success_rates = {
        provider: round((count - provider_fail_counter.get(provider, 0)) / count * 100, 2)
        for provider, count in provider_counter.items()
        if count
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "task_count": len(tasks),
        "version_count": version_count,
        "rights_status": {
            "missing": rights_missing,
            "configured": rights_configured,
            "review_required": rights_review_required,
            "blocked": rights_blocked_status,
            "blocked_total": rights_blocked,
            "blocked_rate": round(rights_blocked / len(tasks) * 100, 2) if tasks else 0.0,
        },
        "quality": {
            "version_pass": pass_count,
            "version_fail": fail_count,
            "qa_pass_rate": round(pass_count / version_count * 100, 2) if version_count else 0.0,
            "qa_fail_rate": round(fail_count / version_count * 100, 2) if version_count else 0.0,
            "average_score": round(sum(score_values) / len(score_values), 2) if score_values else 0.0,
            "failure_counts": dict(failure_counter.most_common()),
            "lyric_failure_counts": dict(lyric_failure_counter.most_common()),
            "lyric_failure_rate": round(sum(lyric_failure_counter.values()) / version_count * 100, 2) if version_count else 0.0,
            "emotion_failure_counts": dict(emotion_failure_counter.most_common()),
            "emotion_failure_rate": round(sum(emotion_failure_counter.values()) / version_count * 100, 2) if version_count else 0.0,
            "next_agent_counts": dict(agent_counter.most_common()),
        },
        "provider": {
            "usage": dict(provider_counter.most_common()),
            "failures": dict(provider_fail_counter.most_common()),
            "success_rates": provider_success_rates,
        },
        "rework": {
            "total_events": rework_history["summary"]["total_events"],
            "queued": len(rework_queue),
            "success_count": rework_success,
            "success_rate": round(rework_success / len(rework_events) * 100, 2) if rework_events else 0.0,
            "rework_budget_summary": rework_queue_summary,
        },
        "delivery": {
            "ready_package_count": delivery_package_count,
            "ready_package_rate": round(delivery_package_count / len(tasks) * 100, 2) if tasks else 0.0,
        },
        "research": _research_ops_summary(_load_research_sources(workspace)),
        "daily_capacity": {
            "tasks_created_today": tasks_created_today,
            "versions_generated_today": versions_generated_today,
            "latest_batch_count": len(latest_daily),
        },
        "latest_daily_reports": latest_daily,
        "scheduler_state": scheduler_state,
    }


def _ops_evolution_response(workspace: Path, repository: ResultRepository, scheduler: DailyAutomationScheduler, automation: DailyAutomationService) -> dict[str, Any]:
    ops = _ops_report(workspace, repository, scheduler, automation)
    state = _load_evolution_state(workspace)
    signals = _evolution_signals_from_ops(ops)
    proposals = _evolution_proposals_from_signals(signals, state)
    experiments = _evolution_experiments_from_proposals(proposals, state)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ops_report": ops,
        "signals": signals,
        "proposals": proposals,
        "experiments": experiments,
        "audit_log": state.get("audit_log", []),
        "protected_targets": [
            "originality_hard_gate",
            "rights_hard_gate",
            "retry_limits",
            "delivery_package_integrity",
            "ai_disclosure_required",
        ],
        "allowed_targets": [
            "brief",
            "style_strategy",
            "generation_router",
            "lyrics_quality",
            "quality_weights",
            "rework_rules",
            "provider_selection",
            "admin_filters",
        ],
    }


def _handle_evolution_action(workspace: Path, payload: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    state = _load_evolution_state(workspace)
    action = str(payload.get("action") or "")
    proposal_id = str(payload.get("proposal_id") or "")
    experiment_id = str(payload.get("experiment_id") or "")
    now = datetime.now().isoformat(timespec="seconds")
    current_proposals = {proposal["proposal_id"]: proposal for proposal in current.get("proposals", [])}
    current_experiments = {experiment["experiment_id"]: experiment for experiment in current.get("experiments", [])}
    if action in {"approve_proposal", "reject_proposal"}:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        if proposal_id not in current_proposals:
            raise ValueError("proposal_id is not active")
        status = "approved" if action == "approve_proposal" else "rejected"
        approval_status = "approved" if action == "approve_proposal" else "rejected"
        state.setdefault("proposals", {})[proposal_id] = {
            "status": status,
            "approval_status": approval_status,
            "updated_at": now,
        }
    elif action in {"promote_experiment", "rollback_experiment"}:
        if not experiment_id or not proposal_id:
            raise ValueError("proposal_id and experiment_id are required")
        experiment = current_experiments.get(experiment_id)
        if experiment is None:
            raise ValueError("experiment_id is not active")
        if experiment.get("proposal_id") != proposal_id:
            raise ValueError("experiment_id does not match proposal_id")
        proposal_state = state.get("proposals", {}).get(proposal_id, {})
        if action == "promote_experiment" and proposal_state.get("status") != "approved":
            raise ValueError("proposal must be approved before promote")
        result = "promote" if action == "promote_experiment" else "rollback"
        proposal_status = "applied" if action == "promote_experiment" else "rolled_back"
        state.setdefault("experiments", {})[experiment_id] = {
            "result": result,
            "ended_at": now,
            "updated_at": now,
        }
        state.setdefault("proposals", {})[proposal_id] = {
            "status": proposal_status,
            "approval_status": "approved",
            "updated_at": now,
        }
    else:
        raise ValueError("unsupported evolution action")
    state.setdefault("audit_log", []).append(
        {
            "audit_id": f"audit_{uuid.uuid4().hex[:8]}",
            "created_at": now,
            "action": action,
            "proposal_id": proposal_id or None,
            "experiment_id": experiment_id or None,
            "actor": "codex_round8",
        }
    )
    _save_evolution_state(workspace, state)
    return state


def _evolution_signals_from_ops(ops: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    quality = ops.get("quality", {})
    rights = ops.get("rights_status", {})
    rework = ops.get("rework", {})
    provider = ops.get("provider", {})
    version_count = int(ops.get("version_count") or 0)
    qa_fail_rate = float(quality.get("qa_fail_rate") or 0.0) / 100
    if version_count and qa_fail_rate > 0.35:
        signals.append(_signal("qa", "qa_fail_rate", round(qa_fail_rate, 4), 0.35, "warning", ["ops_report"]))
    for failure_code, count in quality.get("failure_counts", {}).items():
        if version_count and int(count) / version_count > 0.25:
            signals.append(_signal("rework", f"failure_code:{failure_code}", int(count), "25_percent_of_versions", "warning", ["ops_report"]))
    if version_count and float(quality.get("lyric_failure_rate") or 0.0) > 25:
        signals.append(_signal("qa", "lyric_failure_rate", quality.get("lyric_failure_rate"), 25, "warning", ["ops_report"]))
    if version_count and float(quality.get("emotion_failure_rate") or 0.0) > 25:
        signals.append(_signal("qa", "emotion_failure_rate", quality.get("emotion_failure_rate"), 25, "warning", ["ops_report"]))
    for provider_name, count in provider.get("usage", {}).items():
        if not count:
            continue
        fail_rate = (provider.get("failures", {}).get(provider_name, 0) / count)
        if fail_rate > 0.15:
            signals.append(_signal("provider", f"provider_fail_rate:{provider_name}", round(fail_rate, 4), 0.15, "warning", ["ops_report"]))
    if int(ops.get("task_count") or 0) and float(rights.get("blocked_rate") or 0.0) > 20:
        signals.append(_signal("rights", "rights_block_rate", rights.get("blocked_rate"), 20, "warning", ["ops_report"]))
    if int(rework.get("total_events") or 0) and float(rework.get("success_rate") or 0.0) < 40:
        signals.append(_signal("rework", "rework_success_rate", rework.get("success_rate"), 40, "warning", ["rework_history"]))
    research = ops.get("research", {})
    for risk_flag, count in research.get("risk_flag_counts", {}).items():
        if int(count) > 0:
            signals.append(_signal("research", f"research_risk_flag:{risk_flag}", int(count), "nonzero_review_risk", "info", ["research_sources"]))
    originality_high = int(quality.get("failure_counts", {}).get("ORIGINALITY_HIGH") or 0)
    if version_count and originality_high / version_count > 0.05:
        signals.append(_signal("qa", "originality_high_rate", round(originality_high / version_count, 4), 0.05, "critical", ["ops_report"]))
    return signals


def _signal(source: str, metric: str, value: Any, threshold: Any, severity: str, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "signal_id": f"signal_{_stable_id(source + ':' + metric)}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "severity": severity,
        "evidence_refs": evidence_refs,
    }


def _evolution_proposals_from_signals(signals: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    overrides = state.get("proposals", {})
    for signal in signals:
        metric = str(signal["metric"])
        target = "generation_router"
        after: dict[str, Any] = {"investigate_metric": metric, "reduce_blind_generation": True}
        if metric in {"lyric_failure_rate"}:
            target = "lyrics_quality"
            after = {"increase_lyric_editor_priority": True, "require_section_coverage_check": True}
        elif metric in {"emotion_failure_rate"}:
            target = "style_strategy"
            after = {"strengthen_emotion_profile_prompting": True, "preserve_theme_category": True}
        elif metric.startswith("failure_code:") or metric == "rework_success_rate":
            target = "rework_rules"
            after = {"increase_rebrief_priority": True, "reduce_auto_rework_when_low_success": metric == "rework_success_rate"}
        elif metric.startswith("provider_fail_rate:"):
            target = "provider_selection"
            after = {"lower_provider_weight": metric.split(":", 1)[1], "enable_fallback_first": True}
        elif metric == "rights_block_rate":
            target = "admin_filters"
            after = {"prioritize_rights_completion": True, "default_filter": "rights_blocked"}
        elif metric.startswith("research_risk_flag:"):
            target = "admin_filters"
            after = {"prioritize_research_review": metric.split(":", 1)[1], "default_filter": "research_needs_review"}
        elif metric == "originality_high_rate":
            target = "style_strategy"
            after = {"pause_reference_style_chain": True, "require_human_review": True}
        proposal_id = f"proposal_{_stable_id(signal['signal_id'] + ':' + target)}"
        status_data = overrides.get(proposal_id, {})
        proposals.append(
            {
                "proposal_id": proposal_id,
                "created_at": signal["created_at"],
                "target": target,
                "before": {"metric": metric, "value": signal["value"]},
                "after": after,
                "expected_effect": "reduce repeated production failures without weakening hard gates",
                "risk_flags": [],
                "requires_human_approval": True,
                "approval_status": status_data.get("approval_status", "required"),
                "rollback_plan": ["restore previous policy snapshot", "keep version and QA history unchanged"],
                "status": status_data.get("status", "proposed"),
                "evidence_refs": [signal["signal_id"]],
            }
        )
    return proposals


def _evolution_experiments_from_proposals(proposals: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []
    overrides = state.get("experiments", {})
    for proposal in proposals:
        experiment_id = f"experiment_{_stable_id(proposal['proposal_id'])}"
        status_data = overrides.get(experiment_id, {})
        experiments.append(
            {
                "experiment_id": experiment_id,
                "proposal_id": proposal["proposal_id"],
                "started_at": proposal["created_at"],
                "ended_at": status_data.get("ended_at"),
                "control_group": "current_policy",
                "treatment_group": f"{proposal['target']}_proposal",
                "metrics": {"sample_size": 0.0, "expected_risk_reduction": 0.1},
                "result": status_data.get("result", "running"),
                "evidence_refs": proposal["evidence_refs"],
            }
        )
    return experiments


def _load_evolution_state(workspace: Path) -> dict[str, Any]:
    path = workspace / "ops" / "evolution_state.json"
    if not path.exists():
        return {"proposals": {}, "experiments": {}, "audit_log": []}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_evolution_state(workspace: Path, state: dict[str, Any]) -> None:
    path = workspace / "ops" / "evolution_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def _stable_id(value: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, value).hex[:10]


def _research_ops_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    risk_flags: Counter[str] = Counter()
    imported_to: Counter[str] = Counter()
    for source in sources:
        target = source.get("imported_to")
        if target:
            imported_to[str(target)] += 1
        for flag in source.get("risk_flags", []):
            risk_flags[str(flag)] += 1
    return {
        "total": len(sources),
        "by_type": dict(Counter(str(source.get("source_type") or "unknown") for source in sources).most_common()),
        "by_credibility": dict(Counter(str(source.get("credibility") or "unknown") for source in sources).most_common()),
        "by_audit_status": dict(Counter(str(source.get("audit_status") or "unknown") for source in sources).most_common()),
        "by_imported_to": dict(imported_to.most_common()),
        "risk_flag_counts": dict(risk_flags.most_common()),
    }


def _integration_status_label_zh(status: str) -> str:
    return {
        "local_candidate": "本地候选",
        "research_only": "仅研究",
        "reject": "拒绝接入",
    }.get(status, status)


def _system_models_response(engine: CreationEngine, repository: ResultRepository, provider_config_path: str | None) -> dict[str, Any]:
    provider_usage = _provider_usage_from_results(repository.list_results())
    if engine.provider_registry is None:
        config = engine.generation_router.config
        providers = [
            {
                "id": "env_or_direct",
                "provider": config.provider,
                "model_name": config.model_name,
                "model_version": config.model_version,
                "enabled": True,
                "priority": 100,
                "supported_modes": ["song", "instrumental", "bgm", "loop", "short_video", "children", "classical", "game", "film"],
                "supports_vocals": True,
                "supports_instrumental": True,
                "max_duration_sec": 600,
                "timeout_sec": config.timeout_sec,
                "adapter_type": config.provider,
                "requires_api_key": False,
                "license_scope": "unknown",
                "commercial_use_allowed": False,
                "risk_flags": [],
                "integration_status": "local_candidate",
                "integration_status_label_zh": "本地候选",
                "paid_dependency": False,
                "production_enabled": False,
                "license_evidence_refs": [],
                "command_configured": bool(config.command),
                "notes": "Direct router mode; use --provider-config for a provider registry.",
                "usage": provider_usage.get(config.provider, {}),
            }
        ]
        mode = "direct_router"
    else:
        providers = []
        for provider in engine.provider_registry.providers:
            providers.append(
                {
                    "id": provider.id,
                    "provider": provider.provider,
                    "model_name": provider.model_name,
                    "model_version": provider.model_version,
                    "enabled": provider.enabled,
                    "priority": provider.priority,
                    "supported_modes": list(provider.supported_modes),
                    "supports_vocals": provider.supports_vocals,
                    "supports_instrumental": provider.supports_instrumental,
                    "max_duration_sec": provider.max_duration_sec,
                    "timeout_sec": provider.timeout_sec,
                    "adapter_type": provider.adapter_type,
                    "requires_api_key": provider.requires_api_key,
                    "license_scope": provider.license_scope,
                    "commercial_use_allowed": provider.commercial_use_allowed,
                    "risk_flags": list(provider.risk_flags),
                    "integration_status": provider.integration_status,
                    "integration_status_label_zh": _integration_status_label_zh(provider.integration_status),
                    "paid_dependency": provider.paid_dependency,
                    "production_enabled": provider.production_enabled,
                    "license_evidence_refs": list(provider.license_evidence_refs),
                    "command_configured": bool(provider.command),
                    "notes": provider.notes,
                    "usage": provider_usage.get(provider.provider, {}),
                }
            )
        mode = "provider_registry"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "provider_config_path": provider_config_path,
        "preferred_provider_id": engine.preferred_provider_id,
        "providers": providers,
        "secret_policy": "API keys and environment secrets are not exposed by this endpoint.",
    }


def _provider_usage_from_results(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    usage: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    for task in tasks:
        for version in task.get("versions", []):
            selection = (version.get("generation_route") or {}).get("selection") or {}
            provider = str(selection.get("selected_provider") or version.get("model_provider") or "unknown")
            usage[provider] += 1
            if (version.get("score_total") or 0) < 80 or version.get("failure_codes"):
                failures[provider] += 1
    return {
        provider: {
            "version_count": count,
            "failure_count": failures.get(provider, 0),
            "success_rate": round((count - failures.get(provider, 0)) / count * 100, 2) if count else 0.0,
        }
        for provider, count in usage.items()
    }


def _compact_daily_report(report: dict[str, Any]) -> dict[str, Any]:
    compact = {key: value for key, value in report.items() if key not in {"tasks", "rework_queue"}}
    compact["task_ids"] = [task.get("task_id") for task in report.get("tasks", [])]
    compact["rework_queue_count"] = len(report.get("rework_queue", []))
    return compact


def _quality_reviews_response(repository: ResultRepository, params: dict[str, list[str]]) -> dict[str, Any]:
    reviews = [
        _quality_review_item(task, version)
        for task in [_decorate_task(item) for item in repository.list_results()]
        for version in task.get("versions", [])
    ]
    filtered = [item for item in reviews if _quality_review_matches(item, params)]
    sort_key, sort_reverse = _quality_sort(params)
    filtered.sort(key=lambda item: _work_sort_value(item, sort_key), reverse=sort_reverse)
    page = max(1, _int_param(params, "page", 1))
    page_size = min(100, max(1, _int_param(params, "page_size", 20)))
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": filtered[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "page_count": (total + page_size - 1) // page_size if total else 0,
        },
        "summary": {
            "version_count": len(reviews),
            "filtered_count": total,
            "failure_counts": dict(Counter(code for item in filtered for code in item["failure_codes"]).most_common()),
            "decision_counts": dict(Counter(str(item.get("loop_decision") or "unknown") for item in filtered).most_common()),
        },
    }


def _quality_review_item(task: dict[str, Any], version: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "work_id": task.get("work_id"),
        "version_id": version.get("version_id"),
        "title": version.get("title"),
        "status": version.get("status"),
        "rights_status": task.get("rights_status"),
        "generatedAt": version.get("generatedAt"),
        "score_total": version.get("score_total"),
        "score_breakdown": version.get("score_breakdown", {}),
        "dimensions": (version.get("quality_report") or {}).get("dimensions", []),
        "failure_codes": version.get("failure_codes", []),
        "loop_state": version.get("loop_state", {}),
        "loop_decision": (version.get("loop_state") or {}).get("decision"),
        "next_agent": (version.get("loop_state") or {}).get("next_agent"),
        "next_action": (version.get("loop_state") or {}).get("next_action"),
        "rework_targets": (version.get("loop_state") or {}).get("rework_targets", []),
    }


def _quality_review_matches(item: dict[str, Any], params: dict[str, list[str]]) -> bool:
    for key in ("status", "rights_status", "loop_decision", "next_agent"):
        requested = _multi_param(params, key)
        if requested and str(item.get(key)) not in requested:
            return False
    failure_codes = _multi_param(params, "failure_code")
    if failure_codes and not set(failure_codes).intersection(item.get("failure_codes", [])):
        return False
    score_min = _first_param(params, "score_min")
    score_max = _first_param(params, "score_max")
    score = item.get("score_total")
    if score_min and (score is None or float(score) < float(score_min)):
        return False
    if score_max and (score is None or float(score) > float(score_max)):
        return False
    return _date_in_range(item.get("generatedAt"), _first_param(params, "generated_from"), _first_param(params, "generated_to"))


def _quality_sort(params: dict[str, list[str]]) -> tuple[str, bool]:
    raw = _first_param(params, "sort") or "score_total:asc"
    field, _, direction = raw.partition(":")
    allowed = {"score_total", "generatedAt", "status", "rights_status", "loop_decision", "title"}
    field = field if field in allowed else "score_total"
    return field, direction.lower() != "asc"


def _loop_rework_center_response(repository: ResultRepository, automation: DailyAutomationService) -> dict[str, Any]:
    queue = automation.build_rework_queue()
    history = repository.rework_history()
    return {
        "queue": [asdict(item) for item in queue],
        "queue_count": len(queue),
        "history": history,
        "budget": automation._rework_budget_summary(),
        "failure_counts": dict(Counter(item.failure_code for item in queue).most_common()),
        "next_agent_counts": dict(Counter(item.target_agent for item in queue).most_common()),
    }


def _delivery_rights_response(repository: ResultRepository) -> dict[str, Any]:
    items = [_delivery_rights_item(_decorate_task(task)) for task in repository.list_results()]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "by_rights_status": dict(Counter(item["rights_status"] for item in items).most_common()),
            "ready_for_delivery": sum(1 for item in items if item["delivery_ready"]),
            "blocked": sum(1 for item in items if not item["delivery_ready"]),
        },
    }


def _delivery_packages_response(repository: ResultRepository) -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    for task in [_decorate_task(item) for item in repository.list_results()]:
        selected = _selected_version_dict(task) or {}
        for export in selected.get("export_files", []):
            if export.get("kind") == "delivery_package":
                packages.append(
                    {
                        "task_id": task.get("task_id"),
                        "work_id": task.get("work_id"),
                        "version_id": selected.get("version_id"),
                        "generatedAt": selected.get("generatedAt"),
                        "path": export.get("path"),
                        "checksum": export.get("checksum"),
                        "ready": bool(export.get("ready")),
                        "rights_status": task.get("rights_status"),
                        "score_total": selected.get("score_total"),
                    }
                )
    return {
        "items": packages,
        "summary": {
            "total": len(packages),
            "ready": sum(1 for item in packages if item["ready"]),
        },
    }


def _delivery_rights_item(task: dict[str, Any]) -> dict[str, Any]:
    selected = _selected_version_dict(task) or {}
    exports = selected.get("export_files", [])
    master = next((item for item in exports if item.get("kind") == "master"), {})
    license_pack = next((item for item in exports if item.get("kind") == "license_pack"), {})
    delivery_package = next((item for item in exports if item.get("kind") == "delivery_package"), {})
    license_metadata = _read_json_file(license_pack.get("path")) if license_pack.get("path") else {}
    rights_completeness = license_metadata.get("rights_completeness") if isinstance(license_metadata, dict) else {}
    required_fields = rights_completeness.get("required_fields", {}) if isinstance(rights_completeness, dict) else {}
    hard_gates = _ui_delivery_hard_gates(selected, license_metadata)
    provider_ready = bool(hard_gates["provider_license_gate"]["passed"])
    source_ready = bool(hard_gates["source_integrity_gate"]["passed"])
    delivery_ready = (
        task.get("rights_status") == "configured"
        and bool(master.get("ready"))
        and bool(license_pack.get("ready"))
        and provider_ready
        and source_ready
        and not selected.get("failure_codes")
    )
    return {
        "task_id": task.get("task_id"),
        "work_id": task.get("work_id"),
        "version_id": selected.get("version_id"),
        "title": selected.get("title"),
        "rights_status": task.get("rights_status"),
        "rights_complete": bool(rights_completeness.get("complete")) if isinstance(rights_completeness, dict) else False,
        "required_fields": required_fields,
        "master_ready": bool(master.get("ready")),
        "license_pack_ready": bool(license_pack.get("ready")),
        "provider_license_ready": provider_ready,
        "source_integrity_ready": source_ready,
        "provider_license_gate": hard_gates["provider_license_gate"],
        "source_integrity_gate": hard_gates["source_integrity_gate"],
        "delivery_package_ready": bool(delivery_package.get("ready")),
        "delivery_ready": delivery_ready,
        "blocked_reason": None if delivery_ready else _delivery_block_reason(task, selected, master, license_pack, hard_gates),
        "platform_profile_id": license_metadata.get("platform_profile_id") if isinstance(license_metadata, dict) else None,
        "export_profile": license_metadata.get("export_profile") if isinstance(license_metadata, dict) else None,
    }


def _delivery_block_reason(
    task: dict[str, Any],
    selected: dict[str, Any],
    master: dict[str, Any],
    license_pack: dict[str, Any],
    hard_gates: dict[str, dict[str, Any]] | None = None,
) -> str:
    if selected.get("failure_codes"):
        return "quality_failure"
    if task.get("rights_status") != "configured":
        return f"rights_status_{task.get('rights_status')}"
    hard_gates = hard_gates or _ui_delivery_hard_gates(selected, {})
    for gate_name in ("source_integrity_gate", "provider_license_gate"):
        reasons = hard_gates.get(gate_name, {}).get("reasons", [])
        if reasons:
            return str(reasons[0])
    if not master.get("ready"):
        return str(master.get("blocked_reason") or "master_not_ready")
    if not license_pack.get("ready"):
        return "license_pack_not_ready"
    return "delivery_package_not_created"


def _ui_delivery_hard_gates(selected: dict[str, Any], license_metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    version_id = selected.get("version_id")
    stored = license_metadata.get("delivery_hard_gates") if isinstance(license_metadata, dict) else None
    if isinstance(stored, dict) and version_id in stored:
        return stored[version_id]
    selection = (selected.get("generation_route") or {}).get("selection") or {}
    risk_flags = list(selection.get("selected_risk_flags") or [])
    license_scope = str(selection.get("selected_license_scope") or "unknown")
    production_enabled = bool(selection.get("selected_production_enabled", False))
    commercial_allowed = bool(selection.get("selected_commercial_use_allowed", False))
    integration_status = str(selection.get("selected_integration_status") or "unknown")
    provider_license_evidence_refs = list(selection.get("selected_license_evidence_refs") or [])
    rights_license_evidence_refs = list(license_metadata.get("license_evidence_refs") or []) if isinstance(license_metadata, dict) else []
    rights_approval_status = str(license_metadata.get("rights_approval_status") or "pending") if isinstance(license_metadata, dict) else "pending"
    provider_reasons: list[str] = []
    if selected.get("audio_source") == "mock_file":
        provider_reasons.append("mock_file_internal_validation")
    if not production_enabled:
        provider_reasons.append("provider_not_production_enabled")
    if not commercial_allowed:
        provider_reasons.append("provider_commercial_use_not_allowed")
    if license_scope in {"unknown", "internal_validation", "provider_terms_required", ""}:
        provider_reasons.append("provider_license_not_verified")
    if not provider_license_evidence_refs:
        provider_reasons.append("provider_license_evidence_missing")
    if not rights_license_evidence_refs:
        provider_reasons.append("rights_license_evidence_missing")
    if rights_approval_status != "approved":
        provider_reasons.append("rights_license_not_approved")
    if integration_status in {"research_only", "reject"}:
        provider_reasons.append(f"integration_status_{integration_status}")
    provider_reasons.extend(f"risk_flag_{flag}" for flag in risk_flags)
    source_reasons: list[str] = []
    source_integrity_status = str((selected.get("audio_analysis") or {}).get("source_integrity_status") or "local_file")
    source_integrity_evidence_refs = list(license_metadata.get("source_integrity_evidence_refs") or []) if isinstance(license_metadata, dict) else []
    source_integrity_approval_status = str(license_metadata.get("source_integrity_approval_status") or "pending") if isinstance(license_metadata, dict) else "pending"
    if selected.get("audio_source") == "external_download_url":
        source_download = next((item for item in selected.get("export_files", []) if item.get("kind") == "source_download"), None)
        if source_download is None or not source_download.get("checksum"):
            source_reasons.append("source_checksum_missing")
        if source_integrity_status != "verified":
            source_reasons.append("source_integrity_not_verified")
    if selected.get("audio_source") != "mock_file":
        if not source_integrity_evidence_refs:
            source_reasons.append("source_integrity_evidence_missing")
        if source_integrity_approval_status != "approved":
            source_reasons.append("source_integrity_not_approved")
    return {
        "provider_license_gate": {
            "passed": not provider_reasons,
            "reasons": provider_reasons,
            "license_scope": license_scope,
            "commercial_use_allowed": commercial_allowed,
            "production_enabled": production_enabled,
            "risk_flags": risk_flags,
            "integration_status": integration_status,
            "provider_license_evidence_refs": provider_license_evidence_refs,
            "rights_license_evidence_refs": rights_license_evidence_refs,
            "rights_approval_status": rights_approval_status,
        },
        "source_integrity_gate": {
            "passed": not source_reasons,
            "reasons": source_reasons,
            "audio_source": selected.get("audio_source"),
            "source_integrity_status": source_integrity_status,
            "source_integrity_evidence_refs": source_integrity_evidence_refs,
            "source_integrity_approval_status": source_integrity_approval_status,
        },
    }


def _read_json_file(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {}
    with candidate.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _evidence_manifest_response(workspace: Path) -> dict[str, Any]:
    manifest_path = Path("docs/evidence/CODEX_LOOP_EVIDENCE.md")
    if not manifest_path.exists():
        return {"path": str(manifest_path), "exists": False, "rounds": [], "latest_round": None}
    text = manifest_path.read_text(encoding="utf-8")
    rounds: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith("## Round "):
            if current:
                rounds.append(current)
            current = {"title": line[3:], "objective": "", "command_results": [], "acceptance": []}
            continue
        if current is None:
            continue
        if line.startswith("- `") or line.startswith("- Full") or line.startswith("- Round"):
            current["command_results"].append(line[2:])
        if line.startswith("- ["):
            current["acceptance"].append(line)
        if not current["objective"] and line and not line.startswith("#") and not line.startswith("```"):
            current["objective"] = line
    if current:
        rounds.append(current)
    return {
        "path": str(manifest_path),
        "exists": True,
        "round_count": len(rounds),
        "latest_round": rounds[-1] if rounds else None,
        "rounds": rounds,
        "workspace": str(workspace),
    }


def _research_sources_response(workspace: Path, params: dict[str, list[str]]) -> dict[str, Any]:
    sources = _load_research_sources(workspace)
    filtered = [source for source in sources if _research_source_matches(source, params)]
    page = max(1, _int_param(params, "page", 1))
    page_size = min(100, max(1, _int_param(params, "page_size", 20)))
    total = len(filtered)
    start = (page - 1) * page_size
    return {
        "items": filtered[start : start + page_size],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "page_count": (total + page_size - 1) // page_size if total else 0,
        },
        "summary": {
            "by_type": dict(Counter(item.get("source_type") for item in filtered).most_common()),
            "by_credibility": dict(Counter(item.get("credibility") for item in filtered).most_common()),
            "by_audit_status": dict(Counter(item.get("audit_status") for item in filtered).most_common()),
        },
    }


def _create_research_source(workspace: Path, payload: dict[str, Any]) -> ResearchSource:
    source = ResearchSource(
        source_id=f"rs_{uuid.uuid4().hex[:10]}",
        source_url=str(payload["source_url"]),
        source_title=str(payload["source_title"]),
        source_type=str(payload["source_type"]),
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        published_at=payload.get("published_at"),
        author=payload.get("author"),
        credibility=str(payload.get("credibility") or "unknown"),
        evidence_summary=_safe_research_summary(str(payload.get("evidence_summary") or "")),
        allowed_usage=str(payload.get("allowed_usage") or "summary only; human review required before import"),
        risk_flags=list(payload.get("risk_flags", [])),
        imported_to=payload.get("imported_to"),
        audit_status=str(payload.get("audit_status") or "pending"),
    )
    sources = _load_research_sources(workspace)
    sources.append(asdict(source))
    _save_research_sources(workspace, sources)
    return source


def _approve_research_source(workspace: Path, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    sources = _load_research_sources(workspace)
    allowed_status = {"approved", "rejected", "needs_review", "pending"}
    requested_status = str(payload.get("audit_status") or "approved")
    if requested_status not in allowed_status:
        raise ValueError("unsupported audit_status")
    for source in sources:
        if source.get("source_id") != source_id:
            continue
        source["audit_status"] = requested_status
        source["approved_by"] = payload.get("approved_by") or payload.get("reviewer") or "local_reviewer"
        source["approved_at"] = datetime.now().isoformat(timespec="seconds")
        source["review_notes"] = str(payload.get("review_notes") or "")
        _save_research_sources(workspace, sources)
        return source
    raise ValueError("research source not found")


def _delivery_evidence_response(workspace: Path) -> dict[str, Any]:
    sources = _load_research_sources(workspace)
    approved = [source for source in sources if source.get("audit_status") == "approved"]
    return {
        "items": approved,
        "summary": {
            "approved_total": len(approved),
            "license_evidence": [
                source["source_id"]
                for source in approved
                if source.get("source_type") == "license" or source.get("imported_to") == "rights_library"
            ],
            "source_integrity_evidence": [
                source["source_id"]
                for source in approved
                if source.get("source_type") in {"provider_docs", "license", "dataset"}
                or source.get("imported_to") in {"rights_library", "model_registry"}
            ],
        },
    }


def _require_approved_evidence_refs(workspace: Path, refs: list[str], label: str) -> list[str]:
    if not refs:
        raise ValueError(f"{label} evidence refs required")
    sources = {str(source.get("source_id")): source for source in _load_research_sources(workspace)}
    approved_refs: list[str] = []
    for ref in refs:
        source = sources.get(str(ref))
        if source is None:
            raise ValueError(f"{label} evidence ref not found: {ref}")
        if source.get("audit_status") != "approved":
            raise ValueError(f"{label} evidence ref is not approved: {ref}")
        approved_refs.append(str(ref))
    return approved_refs


def _safe_research_summary(summary: str) -> str:
    if len(summary) > 1200:
        raise ValueError("research evidence_summary must be a short summary, not copied source content")
    blocked_markers = ("[Verse", "[Chorus", "完整歌词", "full lyrics", "download audio")
    if any(marker.lower() in summary.lower() for marker in blocked_markers):
        raise ValueError("research source cannot store full lyrics or downloaded audio content")
    return summary


def _research_source_matches(source: dict[str, Any], params: dict[str, list[str]]) -> bool:
    for key in ("source_type", "credibility", "imported_to", "audit_status"):
        requested = _multi_param(params, key)
        if requested and str(source.get(key)) not in requested:
            return False
    q = _first_param(params, "q")
    if q:
        haystack = " ".join(str(source.get(key) or "") for key in ("source_url", "source_title", "evidence_summary")).lower()
        if q.lower() not in haystack:
            return False
    return True


def _load_research_sources(workspace: Path) -> list[dict[str, Any]]:
    path = _research_sources_path(workspace)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_research_sources(workspace: Path, sources: list[dict[str, Any]]) -> None:
    path = _research_sources_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sources, handle, ensure_ascii=False, indent=2)


def _research_sources_path(workspace: Path) -> Path:
    return workspace / "research" / "sources.json"


def _work_library_response(repository: ResultRepository, params: dict[str, list[str]]) -> dict[str, Any]:
    items = [_work_item(_decorate_task(task)) for task in repository.list_results()]
    filtered = [item for item in items if _work_matches(item, params)]
    sort_key, sort_reverse = _work_sort(params)
    filtered.sort(key=lambda item: _work_sort_value(item, sort_key), reverse=sort_reverse)
    page = max(1, _int_param(params, "page", 1))
    page_size = min(100, max(1, _int_param(params, "page_size", 20)))
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": filtered[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "page_count": (total + page_size - 1) // page_size if total else 0,
        },
        "sort": {"field": sort_key, "direction": "desc" if sort_reverse else "asc"},
        "filters": {key: values for key, values in params.items() if values},
    }


def _work_detail(repository: ResultRepository, work_id: str) -> dict[str, Any] | None:
    for task in repository.list_results():
        if task.get("work_id") == work_id:
            decorated = _decorate_task(task)
            item = _work_item(decorated)
            all_versions = decorated.get("versions", [])
            item["versions"] = [version for version in all_versions if not version.get("isDeleted") and not version.get("archivedAt")]
            item["version_history"] = all_versions
            item["version_tree"] = _version_tree(all_versions)
            item["brief"] = decorated.get("brief")
            item["request_data"] = decorated.get("request_data", {})
            item["rework_history"] = decorated.get("rework_history", [])
            item["audit_log"] = decorated.get("audit_log", [])
            return item
    return None


def _work_versions(repository: ResultRepository, work_id: str) -> dict[str, Any] | None:
    detail = _work_detail(repository, work_id)
    if detail is None:
        return None
    return {
        "work_id": work_id,
        "task_id": detail["task_id"],
        "selected_version_id": detail["selected_version_id"],
        "versions": detail["versions"],
        "version_tree": detail["version_tree"],
    }


def _work_item(task: dict[str, Any]) -> dict[str, Any]:
    versions = task.get("versions", [])
    active_versions = [version for version in versions if not version.get("isDeleted") and not version.get("archivedAt")]
    selected = _selected_version_dict(task)
    if selected and (selected.get("isDeleted") or selected.get("archivedAt")):
        selected = None
    selected = selected or (active_versions[0] if active_versions else (versions[0] if versions else {}))
    request_data = task.get("request_data", {})
    export_files = selected.get("export_files", []) if selected else []
    return {
        "task_id": task.get("task_id"),
        "work_id": task.get("work_id"),
        "workspace_id": request_data.get("workspace_id") or "workspace_guest",
        "title": request_data.get("title") or request_data.get("theme") or selected.get("title"),
        "theme": request_data.get("theme"),
        "category": request_data.get("category"),
        "categories": request_data.get("categories", []) or ([request_data.get("category")] if request_data.get("category") else []),
        "genre": request_data.get("genre", []),
        "mood": request_data.get("mood", []),
        "emotions": request_data.get("emotions", []) or request_data.get("mood", []),
        "scenes": request_data.get("scenes", []),
        "instruments": request_data.get("instruments", []),
        "vocal_types": request_data.get("vocal_types", []),
        "language": request_data.get("language"),
        "languages": request_data.get("languages", []) or ([request_data.get("language")] if request_data.get("language") else []),
        "mode": request_data.get("mode"),
        "full_duration_sec": (selected.get("generation_route", {}) or {}).get("full_duration_sec") or selected.get("duration_sec"),
        "audio_checksum": _audio_checksum_from_version(selected),
        "prompt_hash": (selected.get("generation_route", {}) or {}).get("prompt_hash"),
        "rights_status": task.get("rights_status"),
        "status": selected.get("status"),
        "score_total": selected.get("score_total"),
        "failure_codes": selected.get("failure_codes", []),
        "generatedAt": selected.get("generatedAt"),
        "updatedAt": selected.get("updatedAt") or task.get("updatedAt"),
        "createdAt": task.get("createdAt"),
        "lastGeneratedAt": task.get("lastGeneratedAt"),
        "selected_version_id": selected.get("version_id") or task.get("selected_version_id"),
        "version_count": len(active_versions),
        "total_version_count": len(versions),
        "versions": [_compact_version(version, selected.get("version_id")) for version in active_versions],
        "model_provider": selected.get("model_provider"),
        "model_name": selected.get("model_name"),
        "provider_id": (selected.get("generation_route", {}).get("selection", {}) or {}).get("selected_provider_id"),
        "loop_decision": (selected.get("loop_state") or {}).get("decision"),
        "delivery_blocked_reason": _delivery_blocked_reason(export_files),
        "delivery_status": _delivery_status(task, selected, export_files),
        "selected_version": selected,
        "isDeleted": bool(task.get("isDeleted")),
        "deletedAt": task.get("deletedAt"),
        "archivedAt": task.get("archivedAt"),
        "deleteReason": task.get("deleteReason"),
        "deletedBy": task.get("deletedBy"),
        "lifecycle_status": _lifecycle_status(task),
        "audit_count": len(task.get("audit_log", [])),
    }


def _compact_version(version: dict[str, Any], selected_version_id: str | None = None) -> dict[str, Any]:
    route = version.get("generation_route") or {}
    strategy = route.get("candidate_strategy") or {}
    return {
        "version_id": version.get("version_id"),
        "version_number": version.get("version_number"),
        "title": strategy.get("variation_type_zh") or version.get("title"),
        "status": version.get("status"),
        "score_total": version.get("score_total"),
        "duration_sec": version.get("duration_sec"),
        "seed": version.get("seed"),
        "prompt_hash": route.get("prompt_hash"),
        "candidate_strategy": strategy,
        "generatedAt": version.get("generatedAt"),
        "is_selected": version.get("version_id") == selected_version_id,
        "isDeleted": bool(version.get("isDeleted")),
        "archivedAt": version.get("archivedAt"),
        "failure_codes": version.get("failure_codes", []),
        "loop_decision": (version.get("loop_state") or {}).get("decision"),
        "master_path": next((item.get("path") for item in version.get("export_files", []) if item.get("kind") == "master" and item.get("path")), None),
    }


def _lifecycle_status(task: dict[str, Any]) -> str:
    if task.get("isDeleted") or task.get("deletedAt"):
        return "deleted"
    if task.get("archivedAt"):
        return "archived"
    return "active"


def _selected_version_dict(task: dict[str, Any]) -> dict[str, Any] | None:
    selected_version_id = task.get("selected_version_id")
    for version in task.get("versions", []):
        if version.get("version_id") == selected_version_id:
            return version
    return None


def _version_tree(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "version_id": version.get("version_id"),
            "parent_version_id": version.get("parent_version_id"),
            "version_number": version.get("version_number"),
            "generatedAt": version.get("generatedAt"),
            "optimizedAt": version.get("optimizedAt"),
            "status": version.get("status"),
            "score_total": version.get("score_total"),
        }
        for version in versions
    ]


def _delivery_blocked_reason(export_files: list[dict[str, Any]]) -> str | None:
    for export in export_files:
        if export.get("kind") == "master" and export.get("blocked_reason"):
            return str(export.get("blocked_reason"))
    return None


def _delivery_status(task: dict[str, Any], version: dict[str, Any], export_files: list[dict[str, Any]]) -> str:
    if _delivery_blocked_reason(export_files):
        return "blocked"
    if task.get("rights_status") != "configured":
        return "needs_rights"
    if version.get("audio_source") == "mock_file":
        return "blocked"
    return "ready"


def _audio_checksum_from_version(version: dict[str, Any]) -> str | None:
    for export in version.get("export_files", []):
        if export.get("kind") in {"master", "source_download"} and export.get("checksum"):
            return str(export.get("checksum"))
    return None


def _work_matches(item: dict[str, Any], params: dict[str, list[str]]) -> bool:
    lifecycle = _first_param(params, "lifecycle") or _first_param(params, "deleted_filter")
    include_deleted = (_first_param(params, "include_deleted") or "").lower() in {"1", "true", "yes"}
    item_lifecycle = str(item.get("lifecycle_status") or "active")
    if lifecycle:
        if lifecycle != item_lifecycle:
            return False
    elif not include_deleted and item_lifecycle != "active":
        return False
    q = _first_param(params, "q")
    if q:
        haystack = " ".join(
            str(value or "")
            for value in (
                item.get("work_id"),
                item.get("task_id"),
                item.get("title"),
                item.get("theme"),
                item.get("selected_version_id"),
                item.get("selected_version", {}).get("prompt_snapshot"),
            )
        ).lower()
        if q.lower() not in haystack:
            return False
    list_filters = {
        "categories": item.get("categories", []),
        "category": item.get("categories", []),
        "genre": item.get("genre", []),
        "mood": item.get("mood", []),
        "emotions": item.get("emotions", []),
        "scenes": item.get("scenes", []),
        "instruments": item.get("instruments", []),
        "vocal_types": item.get("vocal_types", []),
        "languages": item.get("languages", []),
    }
    for key, values in list_filters.items():
        requested = _multi_param(params, key)
        if requested and not set(requested).intersection(str(value) for value in values):
            return False
    exact_filters = {
        "language": item.get("language"),
        "mode": item.get("mode"),
        "status": item.get("status"),
        "rights_status": item.get("rights_status"),
        "delivery_status": item.get("delivery_status"),
        "workspace_id": item.get("workspace_id"),
        "provider": item.get("model_provider"),
        "model": item.get("model_name"),
        "lifecycle_status": item_lifecycle,
    }
    for key, value in exact_filters.items():
        requested = _multi_param(params, key)
        if requested and str(value) not in requested:
            return False
    score_min = _first_param(params, "score_min") or _first_param(params, "min_score")
    score_max = _first_param(params, "score_max") or _first_param(params, "max_score")
    score = item.get("score_total")
    if score_min and (score is None or float(score) < float(score_min)):
        return False
    if score_max and (score is None or float(score) > float(score_max)):
        return False
    if not _date_in_range(item.get("generatedAt"), _first_param(params, "generated_from"), _first_param(params, "generated_to")):
        return False
    if not _date_in_range(item.get("updatedAt"), _first_param(params, "updated_from"), _first_param(params, "updated_to")):
        return False
    if _first_param(params, "has_lyrics") in {"true", "1"} and not (item.get("selected_version") or {}).get("lyrics"):
        return False
    if _first_param(params, "has_audio") in {"true", "1"} and not (item.get("selected_version") or {}).get("audio_path"):
        return False
    return True


def _work_sort(params: dict[str, list[str]]) -> tuple[str, bool]:
    raw = _first_param(params, "sort") or "generatedAt:desc"
    field, _, direction = raw.partition(":")
    allowed = {"generatedAt", "updatedAt", "createdAt", "score_total", "title", "rights_status", "status"}
    field = field if field in allowed else "generatedAt"
    return field, direction.lower() != "asc"


def _work_sort_value(item: dict[str, Any], field: str) -> Any:
    value = item.get(field)
    if field == "score_total":
        return float(value or 0)
    return str(value or "")


def _date_in_range(value: str | None, start: str | None, end: str | None) -> bool:
    if start and (not value or value < start):
        return False
    if end and (not value or value > end):
        return False
    return True


def _first_param(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key) or []
    return values[0] if values and values[0] != "" else None


def _multi_param(params: dict[str, list[str]], key: str) -> list[str]:
    values: list[str] = []
    for raw in params.get(key, []):
        values.extend(part.strip() for part in raw.split(",") if part.strip())
    return values


def _int_param(params: dict[str, list[str]], key: str, default: int) -> int:
    raw = _first_param(params, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _find_result_by_work_id(repository: ResultRepository, work_id: str) -> dict[str, Any] | None:
    for result in repository.list_results():
        if result.get("work_id") == work_id:
            return result
    return None


def _find_result_by_version_id(repository: ResultRepository, version_id: str) -> dict[str, Any] | None:
    for result in repository.list_results():
        if any(version.get("version_id") == version_id for version in result.get("versions", [])):
            return result
    return None


def _save_lifecycle_change(
    repository: ResultRepository,
    result: dict[str, Any],
    action: str,
    reason: str = "",
    actor: str = "workbench",
) -> dict[str, Any]:
    now = _utc_now_iso()
    result["updatedAt"] = now
    if action == "archive":
        result["archivedAt"] = now
        result["isDeleted"] = False
        result.pop("deletedAt", None)
    elif action == "delete":
        result["deletedAt"] = now
        result["isDeleted"] = True
    elif action == "restore":
        result["isDeleted"] = False
        result.pop("deletedAt", None)
        result.pop("archivedAt", None)
    result["deleteReason"] = reason or result.get("deleteReason") or ""
    result["deletedBy"] = actor
    result.setdefault("audit_log", []).append(
        _audit_event(
            f"work_{action}",
            actor=actor,
            work_id=result.get("work_id"),
            task_id=result.get("task_id"),
            reason=reason,
        )
    )
    repository.save_result(result)
    return _work_item(_decorate_task(result))


def _save_task_archive(repository: ResultRepository, result: dict[str, Any], reason: str = "", actor: str = "workbench") -> dict[str, Any]:
    return _save_lifecycle_change(repository, result, "archive", reason=reason, actor=actor)


def _save_version_lifecycle_change(
    repository: ResultRepository,
    result: dict[str, Any],
    version_id: str,
    action: str,
    reason: str = "",
    actor: str = "workbench",
) -> dict[str, Any]:
    now = _utc_now_iso()
    matched = False
    for version in result.get("versions", []):
        if version.get("version_id") != version_id:
            continue
        matched = True
        version["updatedAt"] = now
        if action == "archive":
            version["archivedAt"] = now
            version["isDeleted"] = False
        elif action == "delete":
            version["deletedAt"] = now
            version["isDeleted"] = True
        elif action == "restore":
            version["isDeleted"] = False
            version.pop("deletedAt", None)
            version.pop("archivedAt", None)
        break
    if not matched:
        raise ValueError("version not found")
    active_versions = [version for version in result.get("versions", []) if not version.get("isDeleted") and not version.get("archivedAt")]
    if result.get("selected_version_id") == version_id and active_versions:
        result["selected_version_id"] = max(active_versions, key=lambda item: item.get("score_total") or 0).get("version_id")
    result["updatedAt"] = now
    result.setdefault("audit_log", []).append(
        _audit_event(
            f"version_{action}",
            actor=actor,
            work_id=result.get("work_id"),
            task_id=result.get("task_id"),
            version_id=version_id,
            reason=reason,
        )
    )
    repository.save_result(result)
    return _work_item(_decorate_task(result))


def _select_version(repository: ResultRepository, result: dict[str, Any], version_id: str, actor: str = "workbench") -> dict[str, Any]:
    if not any(version.get("version_id") == version_id and not version.get("isDeleted") and not version.get("archivedAt") for version in result.get("versions", [])):
        raise ValueError("active version not found")
    result["selected_version_id"] = version_id
    result["updatedAt"] = _utc_now_iso()
    result.setdefault("audit_log", []).append(
        _audit_event(
            "version_select",
            actor=actor,
            work_id=result.get("work_id"),
            task_id=result.get("task_id"),
            version_id=version_id,
        )
    )
    repository.save_result(result)
    return _work_item(_decorate_task(result))


def make_handler(
    workspace: Path | str,
    provider_registry: GenerationProviderRegistry | None = None,
    preferred_provider_id: str | None = None,
    provider_config_path: str | None = None,
):
    workspace_path = Path(workspace)
    engine = CreationEngine(workspace_path, provider_registry=provider_registry, preferred_provider_id=preferred_provider_id)
    repository = ResultRepository(workspace_path)
    automation = DailyAutomationService(workspace_path, provider_registry=provider_registry, preferred_provider_id=preferred_provider_id)
    scheduler = DailyAutomationScheduler(workspace_path, provider_registry=provider_registry, preferred_provider_id=preferred_provider_id)
    jobs_lock = threading.Lock()
    generation_jobs: dict[str, dict[str, Any]] = {}

    def _status_label_zh(status: str) -> str:
        return {
            "queued": "排队中",
            "running": "生成中",
            "completed": "已完成",
            "failed": "失败",
        }.get(status, status)

    def _job_snapshot(job: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(job)
        snapshot["status_label_zh"] = _status_label_zh(str(snapshot.get("status", "")))
        return snapshot

    def _enqueue_generation_job(payload: dict[str, Any], candidate_count: int = 3) -> dict[str, Any]:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = _utc_now_iso()
        job = {
            "job_id": job_id,
            "job_type": "music_generation",
            "job_type_label_zh": "音乐后台生成",
            "status": "queued",
            "status_label_zh": "排队中",
            "createdAt": now,
            "updatedAt": now,
            "startedAt": None,
            "finishedAt": None,
            "request_data": payload,
            "result": None,
            "error": None,
        }
        with jobs_lock:
            generation_jobs[job_id] = job
            queued_snapshot = _job_snapshot(job)

        def _run() -> None:
            started = _utc_now_iso()
            with jobs_lock:
                generation_jobs[job_id]["status"] = "running"
                generation_jobs[job_id]["status_label_zh"] = "生成中"
                generation_jobs[job_id]["startedAt"] = started
                generation_jobs[job_id]["updatedAt"] = started
            try:
                request = MusicCreationRequest(**payload)
                result = engine.create(request, candidate_count=candidate_count).to_dict()
                finished = _utc_now_iso()
                with jobs_lock:
                    generation_jobs[job_id].update(
                        {
                            "status": "completed",
                            "status_label_zh": "已完成",
                            "finishedAt": finished,
                            "updatedAt": finished,
                            "task_id": result.get("task_id"),
                            "work_id": result.get("work_id"),
                            "version_count": len(result.get("versions", [])),
                            "result": result,
                        }
                    )
            except Exception as exc:  # pragma: no cover - covered by API failure shape
                finished = _utc_now_iso()
                with jobs_lock:
                    generation_jobs[job_id].update(
                        {
                            "status": "failed",
                            "status_label_zh": "失败",
                            "finishedAt": finished,
                            "updatedAt": finished,
                            "error": str(exc),
                        }
                    )

        threading.Thread(target=_run, daemon=True).start()
        return queued_snapshot

    class MusicWorkbenchHandler(BaseHTTPRequestHandler):
        server_version = "MusicWorkbench/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(render_workbench_html())
            elif parsed.path.startswith("/static/"):
                self._send_static_file(parsed.path.removeprefix("/static/"))
            elif parsed.path == "/api/jobs":
                with jobs_lock:
                    jobs = [_job_snapshot(job) for job in generation_jobs.values()]
                jobs.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
                self._send_json({"items": jobs, "total": len(jobs)})
            elif parsed.path.startswith("/api/jobs/"):
                job_id = unquote(parsed.path.strip("/").split("/")[2])
                with jobs_lock:
                    job = generation_jobs.get(job_id)
                    payload = _job_snapshot(job) if job else None
                if payload is None:
                    self.send_error(404, "job not found")
                    return
                self._send_json(payload)
            elif parsed.path == "/api/tasks":
                tasks = [_decorate_task(task) for task in repository.list_results()]
                self._send_json(tasks)
            elif parsed.path == "/api/works":
                self._send_json(_work_library_response(repository, parse_qs(parsed.query)))
            elif parsed.path.startswith("/api/works/"):
                parts = parsed.path.strip("/").split("/")
                work_id = unquote(parts[2]) if len(parts) >= 3 else ""
                if len(parts) == 4 and parts[3] == "versions":
                    payload = _work_versions(repository, work_id)
                else:
                    payload = _work_detail(repository, work_id)
                if payload is None:
                    self.send_error(404, "work not found")
                    return
                self._send_json(payload)
            elif parsed.path == "/api/rework-history":
                self._send_json(repository.rework_history())
            elif parsed.path == "/api/skills":
                self._send_json(skills_snapshot())
            elif parsed.path == "/api/system/models":
                self._send_json(_system_models_response(engine, repository, provider_config_path))
            elif parsed.path == "/api/external-tools":
                self._send_json(absorption_summary())
            elif parsed.path == "/api/ops":
                self._send_json(_ops_report(workspace_path, repository, scheduler, automation))
            elif parsed.path == "/api/ops/evolution":
                self._send_json(_ops_evolution_response(workspace_path, repository, scheduler, automation))
            elif parsed.path == "/api/quality/reviews":
                self._send_json(_quality_reviews_response(repository, parse_qs(parsed.query)))
            elif parsed.path == "/api/loop/rework":
                self._send_json(_loop_rework_center_response(repository, automation))
            elif parsed.path == "/api/evidence/manifest":
                self._send_json(_evidence_manifest_response(workspace_path))
            elif parsed.path == "/api/delivery/rights":
                self._send_json(_delivery_rights_response(repository))
            elif parsed.path == "/api/delivery/packages":
                self._send_json(_delivery_packages_response(repository))
            elif parsed.path == "/api/delivery/evidence":
                self._send_json(_delivery_evidence_response(workspace_path))
            elif parsed.path == "/api/research/sources":
                self._send_json(_research_sources_response(workspace_path, parse_qs(parsed.query)))
            elif parsed.path == "/files":
                params = parse_qs(parsed.query)
                self._send_file(params.get("path", [""])[0])
            else:
                self.send_error(404, "not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/create":
                    raw_payload = self._read_json()
                    candidate_count = _candidate_count_from_payload(raw_payload)
                    payload = _normalize_creation_payload(raw_payload)
                    request = MusicCreationRequest(**payload)
                    result = engine.create(request, candidate_count=candidate_count)
                    self._send_json(result.to_dict(), status=201)
                elif parsed.path == "/api/create-async":
                    raw_payload = self._read_json()
                    candidate_count = _candidate_count_from_payload(raw_payload)
                    payload = _normalize_creation_payload(raw_payload)
                    job = _enqueue_generation_job(payload, candidate_count=candidate_count)
                    self._send_json(job, status=202)
                elif parsed.path == "/api/import-url":
                    payload = self._read_json()
                    candidate_count = _candidate_count_from_payload(payload.get("request", {}))
                    request = MusicCreationRequest(**_normalize_creation_payload(payload["request"]))
                    result = engine.import_external_download(
                        request,
                        download_url=payload["url"],
                        duration_sec=float(payload["duration_sec"]),
                        candidate_count=candidate_count,
                    )
                    self._send_json(result.to_dict(), status=201)
                elif parsed.path == "/api/automation/daily":
                    report = automation.create_daily_batch(target_count=10, candidate_count=3)
                    self._send_json(_compact_daily_report(report), status=201)
                elif parsed.path == "/api/automation/rework":
                    report = automation.run_rework_queue(limit=5)
                    self._send_json(report, status=201)
                elif parsed.path == "/api/research/sources":
                    source = _create_research_source(workspace_path, self._read_json())
                    self._send_json(asdict(source), status=201)
                elif parsed.path.startswith("/api/research/sources/") and parsed.path.endswith("/approval"):
                    source_id = parsed.path.split("/")[4]
                    source = _approve_research_source(workspace_path, source_id, self._read_json())
                    self._send_json(source, status=201)
                elif parsed.path == "/api/ops/evolution":
                    current = _ops_evolution_response(workspace_path, repository, scheduler, automation)
                    state = _handle_evolution_action(workspace_path, self._read_json(), current)
                    self._send_json(state, status=201)
                elif parsed.path == "/api/works/bulk-archive":
                    payload = self._read_json()
                    items = []
                    for work_id in payload.get("work_ids", []):
                        result = _find_result_by_work_id(repository, str(work_id))
                        if result is not None:
                            items.append(_save_lifecycle_change(repository, result, "archive", str(payload.get("reason") or "批量归档")))
                    self._send_json({"items": items, "updated_count": len(items)}, status=201)
                elif parsed.path == "/api/works/bulk-restore":
                    payload = self._read_json()
                    items = []
                    for work_id in payload.get("work_ids", []):
                        result = _find_result_by_work_id(repository, str(work_id))
                        if result is not None:
                            items.append(_save_lifecycle_change(repository, result, "restore", str(payload.get("reason") or "批量恢复")))
                    self._send_json({"items": items, "updated_count": len(items)}, status=201)
                elif parsed.path.startswith("/api/works/") and parsed.path.endswith("/archive"):
                    work_id = unquote(parsed.path.strip("/").split("/")[2])
                    result = _find_result_by_work_id(repository, work_id)
                    if result is None:
                        self.send_error(404, "work not found")
                        return
                    payload = self._read_json()
                    item = _save_lifecycle_change(repository, result, "archive", str(payload.get("reason") or "用户归档"))
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/works/") and parsed.path.endswith("/restore"):
                    work_id = unquote(parsed.path.strip("/").split("/")[2])
                    result = _find_result_by_work_id(repository, work_id)
                    if result is None:
                        self.send_error(404, "work not found")
                        return
                    payload = self._read_json()
                    item = _save_lifecycle_change(repository, result, "restore", str(payload.get("reason") or "用户恢复"))
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/works/") and parsed.path.endswith("/delete"):
                    work_id = unquote(parsed.path.strip("/").split("/")[2])
                    result = _find_result_by_work_id(repository, work_id)
                    if result is None:
                        self.send_error(404, "work not found")
                        return
                    payload = self._read_json()
                    item = _save_lifecycle_change(repository, result, "delete", str(payload.get("reason") or "用户软删除"))
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/versions/") and parsed.path.endswith("/archive"):
                    version_id = unquote(parsed.path.strip("/").split("/")[2])
                    result = _find_result_by_version_id(repository, version_id)
                    if result is None:
                        self.send_error(404, "version not found")
                        return
                    payload = self._read_json()
                    item = _save_version_lifecycle_change(repository, result, version_id, "archive", str(payload.get("reason") or "候选归档"))
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/versions/") and parsed.path.endswith("/restore"):
                    version_id = unquote(parsed.path.strip("/").split("/")[2])
                    result = _find_result_by_version_id(repository, version_id)
                    if result is None:
                        self.send_error(404, "version not found")
                        return
                    payload = self._read_json()
                    item = _save_version_lifecycle_change(repository, result, version_id, "restore", str(payload.get("reason") or "候选恢复"))
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/versions/") and parsed.path.endswith("/select"):
                    version_id = unquote(parsed.path.strip("/").split("/")[2])
                    result = _find_result_by_version_id(repository, version_id)
                    if result is None:
                        self.send_error(404, "version not found")
                        return
                    item = _select_version(repository, result, version_id)
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/archive"):
                    task_id = parsed.path.split("/")[3]
                    result = repository.get_result(task_id)
                    if result is None:
                        self.send_error(404, "task not found")
                        return
                    payload = self._read_json()
                    item = _save_task_archive(repository, result, str(payload.get("reason") or "任务归档"))
                    self._send_json(item, status=201)
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/manual-rework"):
                    task_id = parsed.path.split("/")[3]
                    payload = self._read_json()
                    report = automation.run_manual_rework(
                        task_id=task_id,
                        version_id=payload.get("version_id"),
                        failure_code=payload.get("failure_code") or "WEAK_HOOK",
                        notes=payload.get("notes") or "",
                    )
                    self._send_json(report, status=201)
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/configure-rights"):
                    task_id = parsed.path.split("/")[3]
                    result = repository.get_result(task_id)
                    if result is None:
                        self.send_error(404, "task not found")
                        return
                    payload = self._read_json()
                    configured = _configure_rights_from_dict(engine, result, payload, workspace_path)
                    stored = repository.get_result(task_id) or configured.to_dict()
                    stored.setdefault("audit_log", []).append(
                        _audit_event(
                            "rights_configure",
                            actor=str(payload.get("approved_by") or "workbench"),
                            work_id=stored.get("work_id"),
                            task_id=task_id,
                            rights_status=stored.get("rights_status"),
                            manual_approval_required=bool(payload.get("manual_approval_required", False)),
                        )
                    )
                    repository.save_result(stored)
                    self._send_json(stored)
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/delivery-package"):
                    task_id = parsed.path.split("/")[3]
                    result = repository.get_result(task_id)
                    if result is None:
                        self.send_error(404, "task not found")
                        return
                    restored = result_from_dict(result)
                    export = engine.create_delivery_package(restored)
                    self._send_json({"task_id": restored.task_id, "version_id": export.version_id, "delivery_package": export.path}, status=201)
                else:
                    self.send_error(404, "not found")
            except Exception as exc:
                self.send_error(400, str(exc))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8") or "{}")

        def _send_json(self, payload: Any, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, html: str) -> None:
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_static_file(self, raw_path: str) -> None:
            requested = Path(unquote(raw_path))
            if requested.is_absolute() or ".." in requested.parts:
                self.send_error(403, "static path forbidden")
                return
            resolved = (STATIC_DIR / requested).resolve()
            if not str(resolved).startswith(str(STATIC_DIR.resolve())):
                self.send_error(403, "static path forbidden")
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(404, "static file not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            data = resolved.read_bytes()
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, raw_path: str) -> None:
            if not raw_path:
                self.send_error(400, "path required")
                return
            candidate = Path(unquote(raw_path))
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            resolved = candidate.resolve()
            cwd = Path.cwd().resolve()
            workspace_resolved = workspace_path.resolve()
            if not (str(resolved).startswith(str(cwd)) or str(resolved).startswith(str(workspace_resolved))):
                self.send_error(403, "path outside workspace")
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(404, "file not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            data = resolved.read_bytes()
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return MusicWorkbenchHandler


def _configure_rights_from_dict(
    engine: CreationEngine,
    result: dict[str, Any],
    payload: dict[str, Any] | None = None,
    workspace: Path | None = None,
):
    payload = payload or {}
    restored = result_from_dict(result)
    license_evidence_refs = list(payload.get("license_evidence_refs") or [])
    source_integrity_evidence_refs = list(payload.get("source_integrity_evidence_refs") or [])
    if workspace is not None:
        license_evidence_refs = _require_approved_evidence_refs(workspace, license_evidence_refs, "license")
        source_integrity_evidence_refs = _require_approved_evidence_refs(workspace, source_integrity_evidence_refs, "source integrity")
    return engine.configure_rights(
        restored,
        RightsConfiguration(
            rights_owner=str(payload.get("rights_owner") or "内部 AI 音乐实验室"),
            usage_scope=str(payload.get("usage_scope") or "内部完整版本制作验证"),
            territory=str(payload.get("territory") or "全球"),
            duration=str(payload.get("duration") or "长期"),
            ai_disclosure=str(payload.get("ai_disclosure") or "由 AI 音乐制作系统生成，并经过人工提示、质检和授权门禁。"),
            model_license=str(payload.get("model_license") or "本地 mock 验证音频；正式交付前必须替换为已验证模型授权。"),
            commercial_use_allowed=bool(payload.get("commercial_use_allowed", True)),
            export_allowed=bool(payload.get("export_allowed", True)),
            platform_profile_id=payload.get("platform_profile_id") or "internal_export",
            export_profile=payload.get("export_profile") or "wav_master_license",
            manual_approval_required=bool(payload.get("manual_approval_required", False)),
            reference_sources=list(payload.get("reference_sources", [])),
            license_evidence_refs=license_evidence_refs,
            source_integrity_evidence_refs=source_integrity_evidence_refs,
            rights_approval_status=str(payload.get("rights_approval_status") or "approved"),
            source_integrity_approval_status=str(payload.get("source_integrity_approval_status") or "approved"),
            approved_by=payload.get("approved_by") or "local_reviewer",
            approved_at=payload.get("approved_at") or datetime.now().isoformat(timespec="seconds"),
            notes=str(payload.get("notes") or "工作台内联授权配置。"),
        ),
    )


def _normalize_creation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("candidate_count", None)
    normalized.pop("export_kind", None)
    if "vocalTypes" in normalized and "vocal_types" not in normalized:
        normalized["vocal_types"] = normalized.pop("vocalTypes")
    for key in ("genre", "mood", "categories", "emotions", "languages", "scenes", "instruments", "vocal_types", "forbidden", "export_formats"):
        value = normalized.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            normalized[key] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            normalized[key] = list(value)
    categories = normalized.get("categories") or []
    if categories and not normalized.get("category"):
        normalized["category"] = categories[0]
    languages = normalized.get("languages") or []
    if languages and not normalized.get("language"):
        normalized["language"] = languages[0]
    emotions = normalized.get("emotions") or []
    if emotions and not normalized.get("mood"):
        normalized["mood"] = emotions
    return normalized


def _candidate_count_from_payload(payload: dict[str, Any] | None) -> int:
    if not payload:
        return 3
    try:
        value = int(payload.get("candidate_count", 3))
    except (TypeError, ValueError):
        value = 3
    return min(5, max(3, value))


def run_server(
    host: str,
    port: int,
    workspace: Path | str,
    provider_registry: GenerationProviderRegistry | None = None,
    preferred_provider_id: str | None = None,
    provider_config_path: str | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(
            workspace,
            provider_registry=provider_registry,
            preferred_provider_id=preferred_provider_id,
            provider_config_path=provider_config_path,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="AI music production workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--workspace", default="runs\\web")
    parser.add_argument("--provider-config", default=None, help="Provider capability config JSON")
    parser.add_argument("--preferred-provider", default=None, help="Provider id to force from provider config if it can handle the request")
    args = parser.parse_args()
    provider_registry = GenerationProviderRegistry.from_file(args.provider_config) if args.provider_config else None
    server = run_server(
        args.host,
        args.port,
        args.workspace,
        provider_registry=provider_registry,
        preferred_provider_id=args.preferred_provider,
        provider_config_path=args.provider_config,
    )
    print(f"AI music workbench running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
