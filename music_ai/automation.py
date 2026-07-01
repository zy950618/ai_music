from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import CreationEngine
from .external_tools import HARD_GATE_KEYS, validate_prompt_optimizer_change
from .generation import GenerationProviderRegistry
from .models import EvolutionPolicyProposal, EvolutionSignal, MusicCreationRequest, MusicCreationResult
from .repository import ResultRepository
from .skills import get_rework_rule


@dataclass
class ReworkItem:
    task_id: str
    work_id: str
    version_id: str
    failure_code: str
    target_agent: str
    skill_id: str
    action: str
    preserve_fields: list[str]
    mutable_fields: list[str]
    retry_budget: int
    auto_rework_allowed: bool
    requires_human_review: bool
    delivery_block_only: bool
    source_rework_count: int = 0
    root_rework_depth: int = 0
    root_rework_count: int = 0
    blocked_reason: str | None = None


@dataclass
class DailyScheduleConfig:
    target_count: int = 10
    candidate_count: int = 3
    rework_limit: int = 5
    run_hour: int = 0
    run_minute: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.run_hour <= 23:
            raise ValueError("run_hour must be between 0 and 23")
        if not 0 <= self.run_minute <= 59:
            raise ValueError("run_minute must be between 0 and 59")


class DailyAutomationService:
    def __init__(
        self,
        workspace: Path | str = "runs",
        provider_registry: GenerationProviderRegistry | None = None,
        preferred_provider_id: str | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.engine = CreationEngine(self.workspace, provider_registry=provider_registry, preferred_provider_id=preferred_provider_id)
        self.repository = ResultRepository(self.workspace)

    def create_daily_batch(self, target_count: int = 10, candidate_count: int = 3) -> dict[str, Any]:
        if not 10 <= target_count <= 20:
            raise ValueError("target_count must be between 10 and 20")
        if not 3 <= candidate_count <= 5:
            raise ValueError("candidate_count must be between 3 and 5")

        batch_id = f"batch_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        requests = self._daily_requests(target_count)
        results: list[MusicCreationResult] = []
        for request in requests:
            results.append(self.engine.create(request, candidate_count=candidate_count))

        report = self._build_report(batch_id, results)
        report_path = self.workspace / "batches" / batch_id / "daily_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        return report

    def build_rework_queue(self) -> list[ReworkItem]:
        queue: list[ReworkItem] = []
        for result in self.repository.list_results():
            for version in result.get("versions", []):
                for failure in version.get("failure_codes", []):
                    item = self._rework_item(result, version, failure)
                    if item:
                        queue.append(item)
        return queue

    def run_rework_queue(self, limit: int = 5) -> dict[str, Any]:
        queue = self.build_rework_queue()[:limit]
        created: list[MusicCreationResult] = []
        skipped: list[dict[str, str]] = []
        root_counts: dict[str, int] = {}
        for item in queue:
            source = self.repository.get_result(item.task_id)
            if not source or not source.get("request_data"):
                skipped.append({"task_id": item.task_id, "reason": "missing_request_data"})
                continue
            root_task_id = source.get("rework_root_task_id") or item.task_id
            current_root_count = root_counts.get(root_task_id, self._root_rework_count(root_task_id))
            if item.delivery_block_only:
                skipped.append({"task_id": item.task_id, "reason": "delivery_block_only"})
                continue
            if not item.auto_rework_allowed or item.requires_human_review:
                skipped.append({"task_id": item.task_id, "reason": "requires_human_review"})
                continue
            if current_root_count >= 3:
                skipped.append({"task_id": item.task_id, "version_id": item.version_id, "reason": "task_rework_budget_exhausted"})
                continue
            if item.blocked_reason:
                skipped.append({"task_id": item.task_id, "version_id": item.version_id, "reason": item.blocked_reason})
                continue
            request = MusicCreationRequest(**source["request_data"])
            adjusted = self._adjust_request(request, item.failure_code)
            result = self.engine.create(adjusted, candidate_count=3)
            result.parent_task_id = item.task_id
            result.rework_reason = item.failure_code
            result.rework_root_task_id = root_task_id
            result.rework_depth = int(source.get("rework_depth", 0)) + 1
            optimized_at = datetime.now().isoformat(timespec="seconds")
            for child_version in result.versions:
                child_version.parent_version_id = item.version_id
                child_version.optimizedAt = optimized_at
                child_version.updatedAt = optimized_at
                if child_version.loop_state:
                    child_version.loop_state.parent_version_id = item.version_id
            result.rework_history = list(source.get("rework_history", []))
            result.rework_history.append(
                {
                    "source_task_id": item.task_id,
                    "source_version_id": item.version_id,
                    "failure_code": item.failure_code,
                    "target_agent": item.target_agent,
                    "skill_id": item.skill_id,
                    "created_task_id": result.task_id,
                    "root_task_id": result.rework_root_task_id,
                    "rework_depth": result.rework_depth,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            self.engine._write_result(self.workspace / result.task_id, result)
            created.append(result)
            root_counts[root_task_id] = current_root_count + 1

        report = {
            "created_reworks": [result.to_dict() for result in created],
            "skipped": skipped,
            "processed": len(queue),
        }
        report_path = self.workspace / "rework_reports" / f"rework_{uuid.uuid4().hex[:8]}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        return report

    def run_manual_rework(
        self,
        task_id: str,
        version_id: str | None = None,
        failure_code: str = "WEAK_HOOK",
        notes: str = "",
    ) -> dict[str, Any]:
        source = self.repository.get_result(task_id)
        if not source or not source.get("request_data"):
            return {"created_reworks": [], "skipped": [{"task_id": task_id, "reason": "missing_request_data"}], "processed": 0}
        version = self._select_version(source, version_id)
        if version is None:
            return {"created_reworks": [], "skipped": [{"task_id": task_id, "reason": "version_not_found"}], "processed": 0}
        item = self._rework_item(source, version, failure_code)
        if item is None:
            return {"created_reworks": [], "skipped": [{"task_id": task_id, "version_id": version["version_id"], "reason": "unknown_failure_code"}], "processed": 0}
        if item.delivery_block_only:
            return {"created_reworks": [], "skipped": [{"task_id": task_id, "version_id": version["version_id"], "reason": "delivery_block_only"}], "processed": 1}
        if not item.auto_rework_allowed or item.requires_human_review:
            return {"created_reworks": [], "skipped": [{"task_id": task_id, "version_id": version["version_id"], "reason": "requires_human_review"}], "processed": 1}
        if item.blocked_reason:
            return {"created_reworks": [], "skipped": [{"task_id": task_id, "version_id": version["version_id"], "reason": item.blocked_reason}], "processed": 1}

        request = MusicCreationRequest(**source["request_data"])
        adjusted = self._adjust_request(request, failure_code)
        result = self.engine.create(adjusted, candidate_count=3)
        root_task_id = source.get("rework_root_task_id") or task_id
        result.parent_task_id = task_id
        result.rework_reason = failure_code
        result.rework_root_task_id = root_task_id
        result.rework_depth = int(source.get("rework_depth", 0)) + 1
        optimized_at = datetime.now().isoformat(timespec="seconds")
        for child_version in result.versions:
            child_version.parent_version_id = version["version_id"]
            child_version.optimizedAt = optimized_at
            child_version.updatedAt = optimized_at
            if child_version.loop_state:
                child_version.loop_state.parent_version_id = version["version_id"]
        result.rework_history = list(source.get("rework_history", []))
        result.rework_history.append(
            {
                "source_task_id": task_id,
                "source_version_id": version["version_id"],
                "failure_code": failure_code,
                "target_agent": item.target_agent,
                "skill_id": item.skill_id,
                "created_task_id": result.task_id,
                "root_task_id": result.rework_root_task_id,
                "rework_depth": result.rework_depth,
                "manual": True,
                "notes": notes,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self.engine._write_result(self.workspace / result.task_id, result)
        report = {"created_reworks": [result.to_dict()], "skipped": [], "processed": 1}
        report_path = self.workspace / "rework_reports" / f"manual_rework_{uuid.uuid4().hex[:8]}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        return report

    def build_evolution_signals(self, report: dict[str, Any]) -> list[EvolutionSignal]:
        created_at = datetime.now().isoformat(timespec="seconds")
        signals: list[EvolutionSignal] = []
        candidate_count = int(report.get("candidate_count") or 0)
        qa_fail_count = int(report.get("qa_fail_count") or 0)
        if candidate_count and qa_fail_count / candidate_count > 0.35:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="qa",
                    metric="qa_fail_rate",
                    value=round(qa_fail_count / candidate_count, 4),
                    threshold=0.35,
                    severity="warning",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        for failure_code, count in report.get("failure_counts", {}).items():
            if candidate_count and int(count) / candidate_count > 0.25:
                signals.append(
                    EvolutionSignal(
                        signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                        created_at=created_at,
                        source="rework",
                        metric=f"failure_code:{failure_code}",
                        value=int(count),
                        threshold="25_percent_of_candidates",
                        severity="warning",
                        evidence_refs=[str(report.get("batch_id") or "daily_report")],
                    )
                )
        provider_failure_rate = report.get("provider_failure_rate")
        if provider_failure_rate is not None and float(provider_failure_rate) > 0.15:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="provider",
                    metric="provider_failure_rate",
                    value=round(float(provider_failure_rate), 4),
                    threshold=0.15,
                    severity="warning",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        rework_success_rate = report.get("rework_success_rate")
        if rework_success_rate is not None and float(rework_success_rate) < 0.40:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="rework",
                    metric="rework_success_rate",
                    value=round(float(rework_success_rate), 4),
                    threshold=0.40,
                    severity="warning",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        rights_block_rate = report.get("rights_block_rate")
        if rights_block_rate is None:
            rights_missing_count = int(report.get("rights_missing_count") or 0)
            task_count = int(report.get("task_count") or 0)
            rights_block_rate = rights_missing_count / task_count if task_count else None
        if rights_block_rate is not None and float(rights_block_rate) > 0.20:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="rights",
                    metric="rights_block_rate",
                    value=round(float(rights_block_rate), 4),
                    threshold=0.20,
                    severity="warning",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        originality_high_count = int(report.get("originality_high_count") or 0)
        if candidate_count and originality_high_count / candidate_count > 0.05:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="qa",
                    metric="originality_high_rate",
                    value=round(originality_high_count / candidate_count, 4),
                    threshold=0.05,
                    severity="critical",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        human_review_backlog = int(report.get("human_review_backlog") or 0)
        if human_review_backlog > 10:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="ops",
                    metric="human_review_backlog",
                    value=human_review_backlog,
                    threshold=10,
                    severity="warning",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        quota_usage_rate = report.get("quota_usage_rate")
        if quota_usage_rate is not None and float(quota_usage_rate) >= 0.90:
            signals.append(
                EvolutionSignal(
                    signal_id=f"signal_{uuid.uuid4().hex[:8]}",
                    created_at=created_at,
                    source="ops",
                    metric="quota_usage_rate",
                    value=round(float(quota_usage_rate), 4),
                    threshold=0.90,
                    severity="critical",
                    evidence_refs=[str(report.get("batch_id") or "daily_report")],
                )
            )
        return signals

    def propose_evolution_policies(self, signals: list[EvolutionSignal]) -> list[EvolutionPolicyProposal]:
        proposals: list[EvolutionPolicyProposal] = []
        for signal in signals:
            target = "generation_router" if signal.metric == "qa_fail_rate" else "rework_rules"
            after = {"reduce_blind_generation": True, "investigate_metric": signal.metric}
            proposals.append(self._policy_proposal(target, {"current_metric": signal.metric}, after, [signal.signal_id]))
        return proposals

    def _policy_proposal(
        self,
        target: str,
        before: dict[str, Any],
        after: dict[str, Any],
        evidence_refs: list[str],
    ) -> EvolutionPolicyProposal:
        risk_flags: list[str] = []
        status = "proposed"
        approval_status = "required"
        gate_validation = validate_prompt_optimizer_change(after)
        if target in HARD_GATE_KEYS or not gate_validation["passed"]:
            risk_flags.append("hard_gate_override_rejected")
            risk_flags.extend(str(reason) for reason in gate_validation["blocked_reasons"])
            status = "rejected"
            approval_status = "rejected"
        return EvolutionPolicyProposal(
            proposal_id=f"proposal_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now().isoformat(timespec="seconds"),
            target=target,
            before=before,
            after=after,
            expected_effect="reduce repeated production failures without weakening hard gates",
            risk_flags=risk_flags,
            requires_human_approval=True,
            approval_status=approval_status,
            rollback_plan=["restore previous policy snapshot", "keep version and QA history unchanged"],
            status=status,
        )

    def latest_daily_reports(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for path in sorted((self.workspace / "batches").glob("batch_*/daily_report.json"), reverse=True):
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            data["_path"] = str(path)
            reports.append(data)
        return reports

    def _daily_requests(self, count: int) -> list[MusicCreationRequest]:
        templates = [
            ("短视频完整歌", "适合短视频使用的城市流行电子完整作品", "short_video", ["pop", "electronic"], ["catchy", "bright"], 180, True),
            ("学习 Lo-fi", "适合夜间学习的低干扰完整作品", "bgm", ["lo-fi"], ["calm", "focused"], 180, False),
            ("游戏配乐", "轻快独立游戏地图完整配乐", "game", ["chiptune", "orchestral"], ["playful", "loopable"], 180, False),
            ("国风配乐", "温柔国风剧情完整配乐", "film", ["chinese", "cinematic"], ["gentle", "nostalgic"], 180, False),
            ("儿童歌曲", "简单正向的儿童旋律完整歌曲", "children", ["children", "pop"], ["simple", "happy"], 180, True),
            ("广告 BGM", "干净积极的产品展示完整音乐", "short_video", ["corporate", "pop"], ["clean", "uplifting"], 180, False),
            ("R&B 夜色", "夜晚情绪化 R&B 完整歌曲", "song", ["r&b", "soul"], ["smooth", "warm"], 180, True),
            ("电子运动", "运动剪辑用电子律动完整作品", "short_video", ["edm"], ["energetic", "driving"], 180, False),
            ("钢琴主题", "古典感钢琴完整主题", "classical", ["classical", "piano"], ["elegant", "clear"], 180, False),
            ("影视铺垫", "短剧转折前的情绪完整配乐", "film", ["cinematic"], ["tense", "emotional"], 180, False),
        ]
        requests: list[MusicCreationRequest] = []
        for index in range(count):
            name, theme, mode, genre, mood, duration, vocal = templates[index % len(templates)]
            requests.append(
                MusicCreationRequest(
                    title=f"{name} {index + 1}",
                    mode=mode,  # type: ignore[arg-type]
                    language="zh" if vocal else "none",
                    theme=theme,
                    mood=mood,
                    genre=genre,
                    audience="AI music production users",
                    use_case="daily automated production",
                    duration_sec=duration,
                    bpm=None,
                    key="C",
                    vocal_required=vocal,
                    forbidden=["真实歌手模仿", "复制已有歌曲旋律"],
                    export_formats=["wav"],
                )
            )
        return requests

    def _build_report(self, batch_id: str, results: list[MusicCreationResult]) -> dict[str, Any]:
        all_versions = [version for result in results for version in result.versions]
        failures: dict[str, int] = {}
        for version in all_versions:
            for failure in version.failure_codes:
                failures[failure] = failures.get(failure, 0) + 1
        qa_pass = sum(1 for version in all_versions if (version.score_total or 0) >= 80 and not version.failure_codes)
        report = {
            "batch_id": batch_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "task_count": len(results),
            "candidate_count": len(all_versions),
            "qa_pass_count": qa_pass,
            "qa_fail_count": len(all_versions) - qa_pass,
            "rights_missing_count": sum(1 for result in results if result.rights_status == "missing"),
            "rights_status_counts": self._rights_status_counts(results),
            "average_score": round(sum(version.score_total or 0 for version in all_versions) / max(1, len(all_versions)), 2),
            "failure_counts": failures,
            "loop_state_counts": self._loop_state_counts(all_versions),
            "provider_usage": self._provider_usage(all_versions),
            "style_distribution": self._style_distribution(results),
            "route_summary": self._route_summary(all_versions),
            "tasks": [result.to_dict() for result in results],
            "rework_queue": [asdict(item) for item in self.build_rework_queue()],
            "rework_budget": self._rework_budget_summary(),
        }
        signals = self.build_evolution_signals(report)
        report["evolution_signals"] = [asdict(signal) for signal in signals]
        report["evolution_policy_proposals"] = [asdict(proposal) for proposal in self.propose_evolution_policies(signals)]
        return report

    def _rights_status_counts(self, results: list[MusicCreationResult]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in results:
            counts[result.rights_status] = counts.get(result.rights_status, 0) + 1
        return counts

    def _loop_state_counts(self, versions: list[Any]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for version in versions:
            decision = version.loop_state.decision if version.loop_state else "missing"
            counts[decision] = counts.get(decision, 0) + 1
        return counts

    def _provider_usage(self, versions: list[Any]) -> dict[str, int]:
        usage: dict[str, int] = {}
        for version in versions:
            selection = version.generation_route.get("selection", {})
            key = str(selection.get("selected_provider_id") or version.generation_route.get("provider") or version.model_name)
            usage[key] = usage.get(key, 0) + 1
        return usage

    def _route_summary(self, versions: list[Any]) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for version in versions:
            selection = version.generation_route.get("selection", {})
            summary.append(
                {
                    "version_id": version.version_id,
                    "provider_id": selection.get("selected_provider_id"),
                    "provider": selection.get("selected_provider") or version.generation_route.get("provider"),
                    "model_name": selection.get("selected_model_name") or version.model_name,
                    "selection_reason": selection.get("selection_reason"),
                    "mode": selection.get("request_mode"),
                    "vocal_required": selection.get("request_vocal_required"),
                    "prompt_tags": version.generation_route.get("style_strategy", {}).get("prompt_tags", []),
                }
            )
        return summary

    def _style_distribution(self, results: list[MusicCreationResult]) -> dict[str, Any]:
        modes: dict[str, int] = {}
        genres: dict[str, int] = {}
        vocal_required = {"true": 0, "false": 0}
        for result in results:
            request_data = result.request_data
            mode = str(request_data.get("mode") or "unknown")
            modes[mode] = modes.get(mode, 0) + 1
            vocal_key = "true" if request_data.get("vocal_required") else "false"
            vocal_required[vocal_key] += 1
            for genre in request_data.get("genre", []):
                key = str(genre)
                genres[key] = genres.get(key, 0) + 1
        return {"modes": modes, "genres": genres, "vocal_required": vocal_required}

    def _select_version(self, result: dict[str, Any], version_id: str | None) -> dict[str, Any] | None:
        selected_id = version_id or result.get("selected_version_id")
        for version in result.get("versions", []):
            if version.get("version_id") == selected_id:
                return version
        return None

    def _rework_item(self, result: dict[str, Any], version: dict[str, Any], failure: str) -> ReworkItem | None:
        rule = get_rework_rule(failure)
        if rule is None:
            return None
        source_count = self._source_rework_count(result["task_id"], version["version_id"], failure)
        root_task_id = result.get("rework_root_task_id") or result["task_id"]
        root_count = self._root_rework_count(root_task_id)
        root_depth = int(result.get("rework_depth", 0))
        blocked_reason = None
        if root_count >= 3:
            blocked_reason = "task_rework_budget_exhausted"
        elif source_count >= 2:
            blocked_reason = "version_rework_budget_exhausted"
        elif root_depth >= 3:
            blocked_reason = "task_rework_depth_exhausted"
        return ReworkItem(
            task_id=result["task_id"],
            work_id=result["work_id"],
            version_id=version["version_id"],
            failure_code=failure,
            target_agent=rule.target_agent,
            skill_id=rule.skill_id,
            action=rule.action,
            preserve_fields=list(rule.preserve_fields),
            mutable_fields=list(rule.mutable_fields),
            retry_budget=rule.retry_budget,
            auto_rework_allowed=rule.auto_rework_allowed,
            requires_human_review=rule.requires_human_review,
            delivery_block_only=rule.delivery_block_only,
            source_rework_count=source_count,
            root_rework_depth=root_depth,
            root_rework_count=root_count,
            blocked_reason=blocked_reason,
        )

    def _source_rework_count(self, task_id: str, version_id: str, failure_code: str) -> int:
        count = 0
        for result in self.repository.list_results():
            for event in result.get("rework_history", []):
                if (
                    event.get("source_task_id") == task_id
                    and event.get("source_version_id") == version_id
                    and event.get("failure_code") == failure_code
                ):
                    count += 1
        return count

    def _root_rework_count(self, root_task_id: str) -> int:
        count = 0
        for result in self.repository.list_results():
            if result.get("rework_root_task_id") == root_task_id:
                count += 1
        return count

    def _rework_budget_summary(self) -> dict[str, int]:
        queue = self.build_rework_queue()
        return {
            "queued": len(queue),
            "blocked": sum(1 for item in queue if item.blocked_reason),
            "auto_allowed": sum(1 for item in queue if item.auto_rework_allowed and not item.requires_human_review and not item.delivery_block_only and not item.blocked_reason),
            "root_budget_exhausted": sum(1 for item in queue if item.blocked_reason == "task_rework_budget_exhausted"),
            "version_budget_exhausted": sum(1 for item in queue if item.blocked_reason == "version_rework_budget_exhausted"),
        }

    def _adjust_request(self, request: MusicCreationRequest, failure: str) -> MusicCreationRequest:
        data = request.__dict__.copy()
        if failure in {"BAD_DURATION", "STRUCTURE_TOO_SHORT"}:
            data["duration_sec"] = min(300, max(180, int(request.duration_sec) + 30))
        elif failure == "LYRIC_MISSING":
            data["lyrics_input"] = data.get("lyrics_input") or f"[Chorus]\n{request.theme}，让旋律重新开始"
            data["vocal_required"] = True
        elif failure == "ORIGINALITY_REVIEW_REQUIRED":
            data["reference_profile_id"] = None
            data["forbidden"] = list(set(request.forbidden + ["参考旋律复刻", "参考声线模仿"]))
        if failure == "WEAK_HOOK":
            data["mood"] = list(dict.fromkeys(list(request.mood) + ["hook_forward", "catchy"]))
            data["bpm"] = max(108, int(request.bpm or 108))
            data["duration_sec"] = max(180, int(request.duration_sec))
        elif failure == "AUDIENCE_MISMATCH":
            data["audience"] = f"{request.audience}; refined for stronger target-listener fit"
            data["mood"] = list(dict.fromkeys(list(request.mood) + ["audience_fit"]))
        return MusicCreationRequest(**data)


class DailyAutomationScheduler:
    def __init__(
        self,
        workspace: Path | str = "runs",
        config: DailyScheduleConfig | None = None,
        provider_registry: GenerationProviderRegistry | None = None,
        preferred_provider_id: str | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.config = config or DailyScheduleConfig()
        self.service = DailyAutomationService(
            self.workspace,
            provider_registry=provider_registry,
            preferred_provider_id=preferred_provider_id,
        )
        self.state_path = self.workspace / "scheduler" / "state.json"

    def run_due(self, now: datetime | None = None) -> dict[str, Any]:
        checked_at = now or datetime.now()
        state = self._load_state()
        run_date = checked_at.date().isoformat()
        due, skipped_reason = self._is_due(checked_at, state)
        report: dict[str, Any] = {
            "scheduler_run_id": f"schedule_{checked_at.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            "checked_at": checked_at.isoformat(timespec="seconds"),
            "scheduled_time": f"{self.config.run_hour:02d}:{self.config.run_minute:02d}",
            "due": due,
            "skipped_reason": skipped_reason,
            "config": asdict(self.config),
        }
        if due:
            daily_report = self.service.create_daily_batch(
                target_count=self.config.target_count,
                candidate_count=self.config.candidate_count,
            )
            rework_report = self.service.run_rework_queue(limit=self.config.rework_limit)
            state.update(
                {
                    "last_run_date": run_date,
                    "last_scheduler_run_id": report["scheduler_run_id"],
                    "last_batch_id": daily_report["batch_id"],
                    "last_checked_at": report["checked_at"],
                }
            )
            self._write_state(state)
            report.update(
                {
                    "daily_report": daily_report,
                    "rework_report": rework_report,
                    "rework_history_summary": self.service.repository.rework_history()["summary"],
                }
            )
        self._write_run_report(report)
        return report

    def _is_due(self, now: datetime, state: dict[str, Any]) -> tuple[bool, str | None]:
        if (now.hour, now.minute) < (self.config.run_hour, self.config.run_minute):
            return False, "before_scheduled_time"
        if state.get("last_run_date") == now.date().isoformat():
            return False, "already_ran_today"
        return True, None

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        with self.state_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _write_run_report(self, report: dict[str, Any]) -> None:
        report_path = self.workspace / "scheduler" / "runs" / f"{report['scheduler_run_id']}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
