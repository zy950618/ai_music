from __future__ import annotations

import json
import hashlib
import shutil
import uuid
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .audio import analyze_wav, checksum_file, duration, fade_wav, loop_wav, normalize_peak_wav, trim_silence_wav, trim_wav
from .generation import GenerationJob, GenerationProviderRegistry, GenerationRouter
from .models import (
    EmotionProfile,
    EditDecision,
    ExportFile,
    LyricSection,
    MusicCreationRequest,
    MusicCreationResult,
    MusicVersion,
    PRODUCT_MAX_DURATION_SEC,
    PRODUCT_MIN_DURATION_SEC,
    RightsConfiguration,
    SongLyrics,
    SongSection,
    VersionLoopState,
)
from .quality import evaluate_version
from .skills import get_rework_rule


class CreationEngine:
    """Phase 1 creation engine: create, edit, process, score, and export music assets."""

    def __init__(
        self,
        workspace: Path | str = "runs",
        generation_router: GenerationRouter | None = None,
        provider_registry: GenerationProviderRegistry | None = None,
        preferred_provider_id: str | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.generation_router = generation_router or GenerationRouter.from_env()
        self.provider_registry = provider_registry
        self.preferred_provider_id = preferred_provider_id

    def create(self, request: MusicCreationRequest, candidate_count: int = 3) -> MusicCreationResult:
        if not 3 <= candidate_count <= 5:
            raise ValueError("candidate_count must be between 3 and 5")

        task_id = f"task_{uuid.uuid4().hex[:10]}"
        work_id = f"work_{uuid.uuid4().hex[:10]}"
        work_dir = self.workspace / task_id
        audio_dir = work_dir / "audio"
        export_dir = work_dir / "exports"
        audio_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)
        created_at = self._now()

        full_duration_sec = self._full_duration_sec(request)
        brief = self._build_brief(request)
        structure = self._build_structure(full_duration_sec, request.vocal_required)
        emotion_profile = self._build_emotion_profile(request)
        lyrics, lyric_translation, lyrics_data = (
            self._build_lyric_assets(request, emotion_profile) if request.vocal_required else (None, None, None)
        )
        bpm = request.bpm or self._default_bpm(request)
        key = request.key or "C"
        generation_routes = self._generation_routes_for_request(request)
        style_strategy = self._style_strategy(request)

        versions: list[MusicVersion] = []
        for index in range(candidate_count):
            version_id = f"v{index + 1}_{uuid.uuid4().hex[:6]}"
            audio_path = audio_dir / f"{version_id}.wav"
            candidate_strategy = self._candidate_strategy(index + 1)
            prompt = self._build_prompt(request, brief, index + 1, candidate_strategy)
            seed = self._seed_for(task_id, work_id, version_id, index + 1, request)
            payload = self._generation_payload(
                request=request,
                brief=brief,
                prompt=prompt,
                structure=structure,
                lyrics_data=lyrics_data,
                emotion_profile=emotion_profile,
                style_strategy=style_strategy,
                candidate_strategy=candidate_strategy,
                seed=seed,
                bpm=bpm + index * 2,
                key=key,
            )
            artifact, selection_trace = self._generate_with_fallback(
                generation_routes,
                GenerationJob(
                    version_id=version_id,
                    prompt=prompt,
                    target_path=audio_path,
                    duration_sec=full_duration_sec,
                    bpm=bpm + index * 2,
                    key_index=index,
                    seed=seed,
                    payload=payload,
                ),
            )
            if not artifact.audio_path:
                raise ValueError("generation artifact must provide a local audio path")
            route_log = dict(artifact.route_log)
            route_log["selection"] = selection_trace
            route_log["style_strategy"] = style_strategy
            route_log["seed"] = seed
            route_log["candidate_strategy"] = candidate_strategy
            route_log["duration_sec"] = full_duration_sec
            route_log["full_duration_sec"] = full_duration_sec
            route_log.setdefault(
                "arrangement_layers",
                [
                    {"id": "drums", "ui_label_zh": "鼓组"},
                    {"id": "bass", "ui_label_zh": "贝斯"},
                    {"id": "chords", "ui_label_zh": "和弦"},
                    {"id": "lead", "ui_label_zh": "主旋律"},
                    {"id": "pad_texture", "ui_label_zh": "氛围铺底"},
                ],
            )
            route_log.setdefault(
                "instrument_plan",
                {
                    "genres": list(request.genre),
                    "moods": self._selected_emotions(request),
                    "requested_instruments": list(request.instruments),
                    "core": ["鼓组", "贝斯", "和弦", "主旋律", "氛围铺底"],
                },
            )
            route_log.setdefault("section_timeline", [asdict(section) for section in structure])
            generated_at = self._now()
            version = MusicVersion(
                version_id=version_id,
                title=f"{request.title or request.theme} - 候选 {index + 1}（{candidate_strategy['variation_type_zh']}）",
                status="generated",
                audio_source=artifact.audio_source,
                work_id=work_id,
                version_number=float(index + 1),
                seed=seed,
                audio_path=artifact.audio_path,
                duration_sec=duration(audio_path),
                audio_analysis=analyze_wav(audio_path),
                bpm=bpm + index * 2,
                key=key,
                lyrics=lyrics,
                lyrics_data=lyrics_data,
                lyric_translation=lyric_translation,
                emotion_profile=emotion_profile,
                structure=structure,
                prompt_snapshot=prompt,
                model_provider=artifact.model_provider,
                model_name=artifact.model_name,
                model_version=artifact.model_version,
                generation_route=route_log,
                failure_codes=[],
                createdAt=created_at,
                generatedAt=generated_at,
                updatedAt=generated_at,
            )
            self._create_default_exports(version, audio_path, export_dir)
            self._score_version(version, request)
            self._create_metadata_exports(version, export_dir)
            versions.append(version)

        self._mark_duplicate_candidates(versions)
        eligible_versions = [version for version in versions if not version.failure_codes] or versions
        selected = max(eligible_versions, key=lambda item: item.score_total or 0)
        if not selected.failure_codes:
            selected.status = "selected"
        result = MusicCreationResult(
            task_id=task_id,
            work_id=work_id,
            brief=brief,
            versions=versions,
            selected_version_id=selected.version_id,
            qa_summary=self._qa_summary(versions),
            rework_suggestions=self._rework_suggestions(versions),
            rights_status="missing",
            request_data=asdict(request),
            createdAt=created_at,
            updatedAt=self._now(),
            lastGeneratedAt=max(version.generatedAt for version in versions),
        )
        self._write_result(work_dir, result)
        return result

    def import_external_download(
        self,
        request: MusicCreationRequest,
        download_url: str,
        duration_sec: float,
        candidate_count: int = 3,
    ) -> MusicCreationResult:
        self._validate_product_duration(int(duration_sec))
        result = self.create(request, candidate_count=candidate_count)
        version = result.versions[0]
        version.audio_source = "external_download_url"
        version.download_url = download_url
        version.audio_path = None
        version.duration_sec = duration_sec
        version.updatedAt = self._now()
        version.audio_analysis = {
            "duration_sec": duration_sec,
            "technical_flags": ["EXTERNAL_AUDIO_NOT_ANALYZED"],
            "source": "external_download_url",
            "source_url": download_url,
            "source_integrity_status": "not_verified",
        }
        version.export_files.insert(
            0,
            ExportFile(
                id=f"export_{uuid.uuid4().hex[:8]}",
                version_id=version.version_id,
                kind="source_download",
                format="url",
                download_url=download_url,
                ready=True,
            ),
        )
        self._score_version(version, request)
        for candidate in result.versions:
            if candidate.status == "selected":
                candidate.status = "qa_fail" if candidate.failure_codes else "qa_pass"
        selected = max(result.versions, key=lambda item: item.score_total or 0)
        selected.status = "selected"
        result.selected_version_id = selected.version_id
        result.qa_summary = self._qa_summary(result.versions)
        result.rework_suggestions = self._rework_suggestions(result.versions)
        result.updatedAt = self._now()
        result.lastGeneratedAt = max((candidate.generatedAt for candidate in result.versions if candidate.generatedAt), default=result.lastGeneratedAt)
        work_dir = self.workspace / result.task_id
        self._write_result(work_dir, result)
        return result

    def render_trim(self, version: MusicVersion, start_sec: float, end_sec: float, target: Path | str) -> ExportFile:
        if not version.audio_path:
            raise ValueError("trim requires a local audio file")
        target_path = Path(target)
        trim_wav(Path(version.audio_path), target_path, start_sec, end_sec)
        decision = EditDecision(
            id=f"edit_{uuid.uuid4().hex[:8]}",
            version_id=version.version_id,
            operation="trim",
            start_sec=start_sec,
            end_sec=end_sec,
        )
        version.edit_decisions.append(decision)
        return self._export_file(version.version_id, "short_cut", target_path)

    def render_fade(self, version: MusicVersion, fade_in_sec: float, fade_out_sec: float, target: Path | str) -> ExportFile:
        if not version.audio_path:
            raise ValueError("fade requires a local audio file")
        target_path = Path(target)
        fade_wav(Path(version.audio_path), target_path, fade_in_sec=fade_in_sec, fade_out_sec=fade_out_sec)
        version.edit_decisions.append(
            EditDecision(
                id=f"edit_{uuid.uuid4().hex[:8]}",
                version_id=version.version_id,
                operation="fade_in_out",
                params={"fade_in_sec": fade_in_sec, "fade_out_sec": fade_out_sec},
            )
        )
        return self._export_file(version.version_id, "master", target_path)

    def render_loop(self, version: MusicVersion, target_duration_sec: float, target: Path | str) -> ExportFile:
        if not version.audio_path:
            raise ValueError("loop requires a local audio file")
        target_path = Path(target)
        loop_wav(Path(version.audio_path), target_path, target_duration_sec)
        version.edit_decisions.append(
            EditDecision(
                id=f"edit_{uuid.uuid4().hex[:8]}",
                version_id=version.version_id,
                operation="loop",
                params={"target_duration_sec": target_duration_sec},
            )
        )
        return self._export_file(version.version_id, "loop", target_path)

    def render_normalized(self, version: MusicVersion, target: Path | str, target_peak: float = 0.89) -> ExportFile:
        if not version.audio_path:
            raise ValueError("normalize requires a local audio file")
        target_path = Path(target)
        normalize_peak_wav(Path(version.audio_path), target_path, target_peak=target_peak)
        version.edit_decisions.append(
            EditDecision(
                id=f"edit_{uuid.uuid4().hex[:8]}",
                version_id=version.version_id,
                operation="normalize_peak",
                params={"target_peak": target_peak, "analysis": analyze_wav(target_path)},
            )
        )
        return self._export_file(version.version_id, "normalized", target_path)

    def render_silence_trimmed(
        self,
        version: MusicVersion,
        target: Path | str,
        threshold: float = 0.005,
        padding_sec: float = 0.05,
    ) -> ExportFile:
        if not version.audio_path:
            raise ValueError("silence trim requires a local audio file")
        target_path = Path(target)
        trim_silence_wav(Path(version.audio_path), target_path, threshold=threshold, padding_sec=padding_sec)
        version.edit_decisions.append(
            EditDecision(
                id=f"edit_{uuid.uuid4().hex[:8]}",
                version_id=version.version_id,
                operation="trim_silence",
                params={"threshold": threshold, "padding_sec": padding_sec, "analysis": analyze_wav(target_path)},
            )
        )
        return self._export_file(version.version_id, "silence_trimmed", target_path)

    def configure_rights(self, result: MusicCreationResult, rights: RightsConfiguration) -> MusicCreationResult:
        work_dir = self.workspace / result.task_id
        license_dir = work_dir / "exports"
        license_dir.mkdir(parents=True, exist_ok=True)
        license_path = license_dir / "license_pack.json"
        rights_complete = self._rights_complete(rights)
        rights_metadata: dict[str, object] = {
            "task_id": result.task_id,
            "work_id": result.work_id,
            "rights_owner": rights.rights_owner,
            "usage_scope": rights.usage_scope,
            "territory": rights.territory,
            "duration": rights.duration,
            "ai_disclosure": rights.ai_disclosure,
            "model_license": rights.model_license,
            "commercial_use_allowed": rights.commercial_use_allowed,
            "transfer_allowed": rights.transfer_allowed,
            "adaptation_allowed": rights.adaptation_allowed,
            "platform_profile_id": rights.platform_profile_id,
            "export_profile": rights.export_profile,
            "manual_approval_required": rights.manual_approval_required,
            "reference_sources": rights.reference_sources,
            "license_evidence_refs": rights.license_evidence_refs,
            "source_integrity_evidence_refs": rights.source_integrity_evidence_refs,
            "rights_approval_status": rights.rights_approval_status,
            "source_integrity_approval_status": rights.source_integrity_approval_status,
            "approved_by": rights.approved_by,
            "approved_at": rights.approved_at,
            "sample_sources": rights.sample_sources,
            "vocal_identity_policy": rights.vocal_identity_policy,
            "export_allowed": rights.export_allowed,
            "rights_completeness": {
                "complete": rights_complete,
                "required_fields": {
                    "rights_owner": bool(str(rights.rights_owner).strip()),
                    "usage_scope": bool(str(rights.usage_scope).strip()),
                    "territory": bool(str(rights.territory).strip()),
                    "duration": bool(str(rights.duration).strip()),
                    "ai_disclosure": bool(str(rights.ai_disclosure).strip()),
                    "model_license": bool(str(rights.model_license).strip()),
                    "platform_profile_id": bool(str(rights.platform_profile_id).strip()),
                    "export_profile": bool(str(rights.export_profile).strip()),
                },
            },
            "delivery_evidence_approval": {
                "license_evidence_refs_present": bool(rights.license_evidence_refs),
                "source_integrity_evidence_refs_present": bool(rights.source_integrity_evidence_refs),
                "rights_approval_status": rights.rights_approval_status,
                "source_integrity_approval_status": rights.source_integrity_approval_status,
            },
            "risk_notes": rights.risk_notes,
            "notes": rights.notes,
        }
        rights_metadata["delivery_hard_gates"] = {
            version.version_id: self._version_delivery_hard_gates(version, rights_metadata)
            for version in result.versions
        }
        with license_path.open("w", encoding="utf-8") as handle:
            json.dump(rights_metadata, handle, ensure_ascii=False, indent=2)

        rights_can_export = rights_complete and rights.export_allowed and rights.commercial_use_allowed and not rights.manual_approval_required
        for version in result.versions:
            hard_gates = self._version_delivery_hard_gates(version, rights_metadata)
            can_formally_export = rights_can_export and hard_gates["provider_license_gate"]["passed"] and hard_gates["source_integrity_gate"]["passed"]
            blocked_reason = None if can_formally_export else self._delivery_block_reason_from_gates(hard_gates, "rights_review_required")
            for export in version.export_files:
                if export.kind == "master":
                    export.ready = can_formally_export
                    export.blocked_reason = blocked_reason
            version.export_files = [export for export in version.export_files if export.kind != "license_pack"]
            version.export_files.append(self._export_file(version.version_id, "license_pack", license_path))
            version.updatedAt = self._now()

        if not rights.export_allowed:
            result.rights_status = "blocked"
        elif not rights_complete or not rights_can_export:
            result.rights_status = "review_required"
        else:
            result.rights_status = "configured"
        result.updatedAt = self._now()
        if result.rights_status == "configured":
            result.qa_summary = f"{result.qa_summary} Rights configured; provider/source gates still decide formal master readiness."
        else:
            result.qa_summary = f"{result.qa_summary} Rights recorded but formal delivery remains blocked: {result.rights_status}."
        self._write_result(work_dir, result)
        return result

    def _rights_complete(self, rights: RightsConfiguration) -> bool:
        required = (
            rights.rights_owner,
            rights.usage_scope,
            rights.territory,
            rights.duration,
            rights.ai_disclosure,
            rights.model_license,
            rights.platform_profile_id,
            rights.export_profile,
        )
        return all(bool(str(value).strip()) for value in required)

    def create_delivery_package(self, result: MusicCreationResult, selected_version_id: str | None = None) -> ExportFile:
        if result.rights_status != "configured":
            raise ValueError("rights must be configured before creating a delivery package")

        version_id = selected_version_id or result.selected_version_id
        version = next((item for item in result.versions if item.version_id == version_id), None)
        if version is None:
            raise ValueError("selected version not found")
        if version.failure_codes:
            raise ValueError(f"selected version has unresolved failure codes: {', '.join(version.failure_codes)}")
        license_pack = self._ready_export(version, "license_pack")
        rights_metadata: dict[str, object] = {}
        if license_pack and license_pack.path:
            with Path(license_pack.path).open("r", encoding="utf-8") as handle:
                rights_metadata = json.load(handle)
        hard_gates = self._version_delivery_hard_gates(version, rights_metadata)
        if not hard_gates["provider_license_gate"]["passed"] or not hard_gates["source_integrity_gate"]["passed"]:
            raise ValueError(f"delivery hard gate failed: {self._delivery_block_reason_from_gates(hard_gates, 'delivery_hard_gate_failed')}")

        master = self._ready_export(version, "master")
        if master is None:
            raise ValueError("master export is not ready")
        if license_pack is None:
            raise ValueError("license pack is not ready")

        work_dir = self.workspace / result.task_id
        package_dir = work_dir / "exports" / "delivery_package"
        package_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = package_dir / "metadata.json"
        acceptance_path = package_dir / "acceptance_report.json"
        lyrics_path = package_dir / "lyrics.txt"
        manifest_path = package_dir / "manifest.json"
        zip_path = work_dir / "exports" / f"{result.work_id}_{version.version_id}_delivery.zip"
        gate_results = self._delivery_gate_results(result, version, rights_metadata, master, license_pack)

        metadata = {
            "task_id": result.task_id,
            "work_id": result.work_id,
            "version_id": version.version_id,
            "version_number": version.version_number,
            "title": version.title,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "generatedAt": version.generatedAt,
            "optimizedAt": version.optimizedAt,
            "brief": result.brief,
            "model_provider": version.model_provider,
            "model_name": version.model_name,
            "model_version": version.model_version,
            "prompt_snapshot": version.prompt_snapshot,
            "rights_status": result.rights_status,
            "rights": rights_metadata,
            "generation_route": version.generation_route,
            "seed": version.seed,
            "emotion_profile": asdict(version.emotion_profile) if version.emotion_profile else None,
            "score_total": version.score_total,
            "score_breakdown": version.score_breakdown,
            "audio_analysis": version.audio_analysis,
            "delivery_gates": gate_results,
        }
        acceptance = {
            "qa_summary": result.qa_summary,
            "quality_report": version.quality_report,
            "failure_codes": version.failure_codes,
            "rework_suggestions": result.rework_suggestions,
            "gate_results": gate_results,
            "delivery_decision": "ready",
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
        if version.lyrics:
            lyrics_text = version.lyrics
            if version.lyric_translation:
                translation = version.lyric_translation
                if translation.startswith("[中文翻译]"):
                    lyrics_text = f"{lyrics_text}\n\n{translation}"
                else:
                    lyrics_text = f"{lyrics_text}\n\n[中文翻译]\n{translation}"
            lyrics_path.write_text(lyrics_text, encoding="utf-8")

        package_entries: list[tuple[Path, str]] = [
            (Path(master.path or ""), f"audio/master{Path(master.path or '').suffix}"),
            (Path(license_pack.path or ""), "rights/license_pack.json"),
            (metadata_path, "metadata/metadata.json"),
            (acceptance_path, "reports/acceptance_report.json"),
        ]
        if version.lyrics:
            package_entries.append((lyrics_path, "lyrics/lyrics.txt"))

        manifest = {
            "package_type": "ai_music_delivery_package",
            "task_id": result.task_id,
            "work_id": result.work_id,
            "version_id": version.version_id,
            "generatedAt": version.generatedAt,
            "optimizedAt": version.optimizedAt,
            "platform_profile_id": rights_metadata.get("platform_profile_id"),
            "export_profile": rights_metadata.get("export_profile"),
            "manual_approval_required": rights_metadata.get("manual_approval_required", False),
            "delivery_gates": gate_results,
            "entries": [
                {
                    "archive_path": archive_path,
                    "source_path": str(source_path),
                    "size_bytes": source_path.stat().st_size,
                    "checksum": checksum_file(source_path),
                }
                for source_path, archive_path in package_entries
            ],
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        package_entries.append((manifest_path, "manifest.json"))

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source_path, archive_path in package_entries:
                if not source_path.exists():
                    raise ValueError(f"delivery source file missing: {source_path}")
                archive.write(source_path, archive_path)

        export = self._export_file(version.version_id, "delivery_package", zip_path)
        version.export_files.append(export)
        self._write_result(work_dir, result)
        return export

    def _delivery_gate_results(
        self,
        result: MusicCreationResult,
        version: MusicVersion,
        rights_metadata: dict[str, object],
        master: ExportFile,
        license_pack: ExportFile,
    ) -> dict[str, object]:
        rights_completeness = rights_metadata.get("rights_completeness")
        rights_complete = bool(rights_completeness.get("complete")) if isinstance(rights_completeness, dict) else False
        hard_gates = self._version_delivery_hard_gates(version, rights_metadata)
        return {
            "quality_gate": {
                "passed": not version.failure_codes and (version.score_total or 0) >= 80,
                "score_total": version.score_total,
                "failure_codes": list(version.failure_codes),
            },
            "rights_gate": {
                "passed": result.rights_status == "configured" and rights_complete,
                "rights_status": result.rights_status,
                "rights_complete": rights_complete,
                "manual_approval_required": bool(rights_metadata.get("manual_approval_required", False)),
                "commercial_use_allowed": bool(rights_metadata.get("commercial_use_allowed", False)),
                "export_allowed": bool(rights_metadata.get("export_allowed", False)),
            },
            "originality_gate": {
                "passed": "ORIGINALITY_HIGH" not in version.failure_codes,
                "failure_codes": [code for code in version.failure_codes if "ORIGINALITY" in code],
            },
            "integrity_gate": {
                "passed": bool(
                    master.ready
                    and master.path
                    and license_pack.ready
                    and license_pack.path
                    and hard_gates["provider_license_gate"]["passed"]
                    and hard_gates["source_integrity_gate"]["passed"]
                ),
                "master_ready": master.ready,
                "license_pack_ready": license_pack.ready,
                "audio_source": version.audio_source,
            },
            "provider_license_gate": hard_gates["provider_license_gate"],
            "source_integrity_gate": hard_gates["source_integrity_gate"],
        }

    def _version_delivery_hard_gates(self, version: MusicVersion, rights_metadata: dict[str, object] | None = None) -> dict[str, dict[str, object]]:
        rights_metadata = rights_metadata or {}
        selection = (version.generation_route or {}).get("selection") or {}
        risk_flags = list(selection.get("selected_risk_flags") or [])
        license_scope = str(selection.get("selected_license_scope") or "unknown")
        production_enabled = bool(selection.get("selected_production_enabled", False))
        commercial_allowed = bool(selection.get("selected_commercial_use_allowed", False))
        integration_status = str(selection.get("selected_integration_status") or "unknown")
        provider_license_evidence_refs = list(selection.get("selected_license_evidence_refs") or [])
        rights_license_evidence_refs = list(rights_metadata.get("license_evidence_refs") or [])
        rights_approval_status = str(rights_metadata.get("rights_approval_status") or "pending")
        provider_reasons: list[str] = []
        if version.audio_source == "mock_file":
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
        source_checksum = self._audio_checksum_for_duplicate_check(version)
        source_integrity_status = str((version.audio_analysis or {}).get("source_integrity_status") or "local_file")
        source_integrity_evidence_refs = list(rights_metadata.get("source_integrity_evidence_refs") or [])
        source_integrity_approval_status = str(rights_metadata.get("source_integrity_approval_status") or "pending")
        if version.audio_source == "external_download_url":
            source_download = next((item for item in version.export_files if item.kind == "source_download"), None)
            if source_download is None or not source_download.checksum:
                source_reasons.append("source_checksum_missing")
            if source_integrity_status != "verified":
                source_reasons.append("source_integrity_not_verified")
        elif version.audio_source in {"mock_file", "local_command_file", "local_file"}:
            if not source_checksum:
                source_reasons.append("source_checksum_missing")
        else:
            source_reasons.append(f"unsupported_audio_source_{version.audio_source}")
        if version.audio_source != "mock_file":
            if not source_integrity_evidence_refs:
                source_reasons.append("source_integrity_evidence_missing")
            if source_integrity_approval_status != "approved":
                source_reasons.append("source_integrity_not_approved")

        return {
            "provider_license_gate": {
                "passed": not provider_reasons,
                "reasons": provider_reasons,
                "provider_id": selection.get("selected_provider_id"),
                "provider": selection.get("selected_provider") or version.model_provider,
                "model_name": selection.get("selected_model_name") or version.model_name,
                "model_version": selection.get("selected_model_version") or version.model_version,
                "license_scope": license_scope,
                "commercial_use_allowed": commercial_allowed,
                "production_enabled": production_enabled,
                "provider_license_evidence_refs": provider_license_evidence_refs,
                "rights_license_evidence_refs": rights_license_evidence_refs,
                "rights_approval_status": rights_approval_status,
                "risk_flags": risk_flags,
                "integration_status": integration_status,
            },
            "source_integrity_gate": {
                "passed": not source_reasons,
                "reasons": source_reasons,
                "audio_source": version.audio_source,
                "download_url": version.download_url,
                "source_integrity_status": source_integrity_status,
                "source_integrity_evidence_refs": source_integrity_evidence_refs,
                "source_integrity_approval_status": source_integrity_approval_status,
                "source_checksum": source_checksum,
            },
        }

    def _delivery_block_reason_from_gates(self, gates: dict[str, dict[str, object]], fallback: str) -> str:
        provider_reasons = gates.get("provider_license_gate", {}).get("reasons", [])
        if "mock_file_internal_validation" in provider_reasons:
            return "mock_file_internal_validation"
        for gate_name in ("source_integrity_gate", "provider_license_gate"):
            gate = gates.get(gate_name, {})
            reasons = gate.get("reasons", [])
            if reasons:
                return str(reasons[0])
        return fallback

    def _build_brief(self, request: MusicCreationRequest) -> str:
        vocals = f"人声：{self._voice_label(request.voice_profile)}" if request.vocal_required else "纯音乐"
        language = self._language_label(request.language)
        categories = self._label_list(self._selected_categories(request), lambda value: value)
        scenes = self._label_list(request.scenes, lambda value: value)
        instruments = self._label_list(request.instruments, lambda value: value)
        vocal_types = self._label_list(request.vocal_types, lambda value: value)
        return (
            f"创作一首 {request.duration_sec} 秒的{language}{self._mode_label(request.mode)}，用途：{request.use_case}。"
            f"主题：{request.theme}。情绪：{self._label_list(request.mood, self._mood_label)}。风格：{self._label_list(request.genre, self._genre_label)}。"
            f"分类：{categories}。场景：{scenes}。乐器：{instruments}。人声类型：{vocal_types}。"
            f"受众：{request.audience}。{vocals}。禁止：{', '.join(request.forbidden) or '无'}。"
        )

    def _build_structure(self, duration_sec: int, vocal_required: bool) -> list[SongSection]:
        if vocal_required:
            names = ["intro", "verse 1", "pre chorus", "chorus", "verse 2", "pre chorus", "chorus", "bridge", "final chorus", "outro"]
        elif duration_sec >= 90:
            names = ["intro", "A theme", "A variation", "B lift", "breakdown", "climax", "loop outro"]
        else:
            names = ["intro", "A theme", "B lift", "climax", "loop outro"]
        step = duration_sec / len(names)
        return [
            SongSection(name=name, start_sec=round(index * step, 2), end_sec=round((index + 1) * step, 2), goal=f"{name} development")
            for index, name in enumerate(names)
        ]

    def _build_lyric_assets(self, request: MusicCreationRequest, emotion_profile: EmotionProfile) -> tuple[str, str | None, SongLyrics]:
        if request.lyrics_input:
            translation = self._build_translation_for_supplied_lyrics(request) if request.language == "en" else None
            lyrics_data = self._lyrics_data_from_supplied_text(request, request.lyrics_input, emotion_profile)
            return request.lyrics_input, translation, lyrics_data
        hook = self._hook_line(request)
        imagery = emotion_profile.imageryKeywords[:4] or ["窗边灯光", "旧街角", "清晨风", "没有寄出的信"]
        category = request.category or "情绪叙事"
        arc = f"{category}从{emotion_profile.primaryEmotion}出发，经过克制、抬升、转折，最终抵达{emotion_profile.release:.2f}释放感。"
        if request.language == "en":
            theme_en = self._english_phrase(request.theme)
            hook_en = self._english_phrase(hook)
            sections = [
                LyricSection("Intro", [f"I leave a light on for {theme_en}", "Soft keys open up the room", "One slow breath becomes a doorway", "Morning waits beyond the blue"], "set scene"),
                LyricSection("Verse 1", [f"In {theme_en}, I keep walking through the rain", f"{imagery[0]} keeps glowing where I used to call your name", "Every scar becomes a rhythm, every breath becomes a line", f"{imagery[1]} fades behind me, but the road is mine"], "restrained detail"),
                LyricSection("Pre-Chorus", ["I do not hide the weight I carry in the dark", "I turn it into fire, I turn it into spark", "The silence starts to loosen every chain", "I hear my heartbeat learning how to change"], "lift tension"),
                LyricSection("Chorus", [f"{hook_en}, I am still standing here", f"{hook_en}, singing louder through the fear", "I let the broken echo disappear", "I choose the sky that finally becomes clear"], "main hook"),
                LyricSection("Verse 2", [f"{imagery[2]} moves across the window frame", "I stop counting all the ways I tried to stay", "There is no message waiting in my hand", "Only new steps drawing lines across the sand"], "new evidence"),
                LyricSection("Pre-Chorus", ["I do not need the past to answer me tonight", "I fold the ache into a quiet kind of light", "The door behind me closes without blame", "The song inside me rises just the same"], "second lift"),
                LyricSection("Chorus", [f"{hook_en}, I am still standing here", f"{hook_en}, singing louder through the fear", "I let the broken echo disappear", "I choose the sky that finally becomes clear"], "repeat hook"),
                LyricSection("Bridge", ["If the night gets heavy, I will hold the line", f"{imagery[3]} turns into a sign", "I give back every shadow I once wore", "I am not waiting at that door anymore"], "turning point"),
                LyricSection("Final Chorus", [f"{hook_en}, now the dawn is near", f"{hook_en}, I can sing it clear", "The final note is brighter than the pain", "I walk away and learn my name again"], "release"),
                LyricSection("Outro", ["No more waiting by the phone", "No more living half alone", "One last breath, the night is through", "I keep the morning, not the wound"], "close"),
            ]
            lyrics_data = SongLyrics(
                title=request.title or request.theme,
                language=request.language,
                theme=request.theme,
                hook=hook_en,
                sections=sections,
                emotional_arc=arc,
                imagery_keywords=imagery,
                rhyme_notes=["keep end vowels open for chorus lift", "use near rhyme without copying existing lyrics"],
                singability_notes=["short chorus lines support breath control", "bridge lowers density before final chorus"],
                safety_notes=["original lyric template", "no real song lyric reuse", "no singer imitation"],
            )
            translation = "\n".join(
                [
                    "[中文翻译]",
                    f"这首歌围绕“{request.theme}”，hook 为“{hook}”。",
                    f"情绪弧线：{arc}",
                ]
            )
            return self._flatten_lyrics(lyrics_data), translation, lyrics_data
        sections = [
            LyricSection("Intro", [f"{imagery[0]}轻轻亮起", "我把夜色放慢呼吸", "旧日回声退到远处", "新的旋律开始落地"], "铺陈画面"),
            LyricSection("Verse 1", [f"把{request.theme}藏进清晨的影子里", f"{imagery[1]}还记得我沉默的消息", "有人在回忆里反复练习失去", "我把每次停顿都写成继续"], "克制回忆"),
            LyricSection("Pre-Chorus", ["风吹过肩膀，我没有退回原地", "把每一道伤口，都交给节拍回应", "那些说不出口的名字慢慢安静", "心跳在黑暗里替我重新校音"], "情绪上升"),
            LyricSection("Chorus", [f"{hook}，我还在继续", f"{hook}，把苦难唱成勇气", "不再等一条迟来的消息", "我把昨天轻轻还给雨季"], "主 hook"),
            LyricSection("Verse 2", [f"{imagery[2]}穿过没关紧的窗", "我学会把空房间整理成远方", "旧照片不再替谁留着位置", "沉默也能开出新的光"], "细节推进"),
            LyricSection("Pre-Chorus", ["我不再向过往借一点回声", "也不让遗憾替未来作证", "把眼泪调成更温柔的音色", "让副歌在胸口慢慢升温"], "二次抬升"),
            LyricSection("Chorus", [f"{hook}，我还在继续", f"{hook}，把苦难唱成勇气", "不再等一条迟来的消息", "我把昨天轻轻还给雨季"], "副歌复现"),
            LyricSection("Bridge", [f"{imagery[3]}终于被风吹开", "我承认爱过，也承认离开", "若黑夜太长，就让心跳作证", "走到天亮之前，我先成为自己的灯"], "转折"),
            LyricSection("Final Chorus", [f"{hook}，我终于更清醒", f"{hook}，让回忆退到风里", "这一次我不再原地等你", "我把自己唱回新的生命"], "释放增强"),
            LyricSection("Outro", ["雨停以后街灯还亮", "我把名字写回手掌", "没有谁再替我决定方向", "最后一拍，留给远方"], "收束"),
        ]
        lyrics_data = SongLyrics(
            title=request.title or request.theme,
            language=request.language,
            theme=request.theme,
            hook=hook,
            sections=sections,
            emotional_arc=arc,
            imagery_keywords=imagery,
            rhyme_notes=["副歌保留相近尾音，便于重复记忆", "主歌使用叙事长短句交替"],
            singability_notes=["副歌短句适合落在强拍", "Bridge 降低字密度后进入 Final Chorus"],
            safety_notes=["原创模板生成", "不复写真实歌词", "不指定真实歌手声线"],
        )
        return self._flatten_lyrics(lyrics_data), None, lyrics_data

    def _build_translation_for_supplied_lyrics(self, request: MusicCreationRequest) -> str:
        return "\n".join(
            [
                "[中文翻译说明]",
                f"这首英文歌词围绕主题“{request.theme}”创作。",
                "逐句译文需要人工校对；当前系统会保留英文原词，并在交付包中标注中文主题译文。",
            ]
        )

    def _lyrics_data_from_supplied_text(
        self, request: MusicCreationRequest, lyrics: str, emotion_profile: EmotionProfile
    ) -> SongLyrics:
        lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
        sections: list[LyricSection] = []
        current_name = "Lyrics"
        current_lines: list[str] = []
        for line in lines:
            if line.startswith("[") and line.endswith("]"):
                if current_lines:
                    sections.append(LyricSection(current_name, current_lines, "supplied"))
                current_name = line.strip("[]")
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections.append(LyricSection(current_name, current_lines, "supplied"))
        if not sections:
            sections.append(LyricSection("Lyrics", lines or [request.theme], "supplied"))
        return SongLyrics(
            title=request.title or request.theme,
            language=request.language,
            theme=request.theme,
            hook=request.title or request.theme,
            sections=sections,
            emotional_arc=f"用户提供歌词，系统按{emotion_profile.primaryEmotion}方向保留并进入 QA。",
            imagery_keywords=emotion_profile.imageryKeywords,
            rhyme_notes=["supplied lyrics require human rhyme review"],
            singability_notes=["supplied lyrics require stress and breath review"],
            safety_notes=["supplied lyrics must pass copyright and safety review"],
        )

    def _flatten_lyrics(self, lyrics_data: SongLyrics) -> str:
        lines: list[str] = []
        for section in lyrics_data.sections:
            lines.append(f"[{section.name}]")
            lines.extend(section.lines)
        lines.extend(
            [
                "",
                f"[Hook] {lyrics_data.hook}",
                f"[Emotional Arc] {lyrics_data.emotional_arc}",
                f"[Imagery] {'、'.join(lyrics_data.imagery_keywords)}",
                f"[Singability] {'；'.join(lyrics_data.singability_notes)}",
            ]
        )
        return "\n".join(lines)

    def _build_emotion_profile(self, request: MusicCreationRequest) -> EmotionProfile:
        categories = self._selected_categories(request)
        emotions = self._selected_emotions(request)
        category_key = categories[0] if categories else (request.mode or "song")
        category = category_key.lower()
        mood_text = " ".join(emotions).lower()
        base = {
            "失恋": ("释然", -0.35, 0.38, ["凌晨消息", "旧照片", "空房间", "雨停后的街"]),
            "healing": ("治愈", 0.35, 0.32, ["窗边灯光", "温水杯", "清晨风", "慢慢打开的门"]),
            "children": ("喜悦", 0.62, 0.58, ["彩色气球", "小小操场", "糖纸亮光", "拍手节奏"]),
            "game": ("冒险", 0.2, 0.72, ["地图边界", "像素星光", "远处城门", "跳动徽章"]),
            "film": ("张力", -0.08, 0.64, ["走廊灯影", "雨夜窗面", "远处警笛", "未说出口的信"]),
            "bgm": ("平静", 0.28, 0.24, ["书页边缘", "低声钟摆", "浅色房间", "稳定脉冲"]),
            "song": ("希望", 0.22, 0.48, ["窗边灯光", "旧街角", "清晨风", "没有寄出的信"]),
        }
        primary, valence, arousal, imagery = base.get(category, base.get(category_key, base["song"]))
        if "sad" in mood_text or "悲" in mood_text or "遗憾" in mood_text:
            valence -= 0.25
            primary = "悲伤"
        if "hope" in mood_text or "释然" in mood_text or "治愈" in mood_text or "uplifting" in mood_text:
            valence += 0.22
            primary = "释然" if primary == "悲伤" else primary
        if "energetic" in mood_text or "热血" in mood_text or "catchy" in mood_text:
            arousal += 0.18
        if request.genre:
            imagery = imagery[:3] + [f"{self._genre_label(request.genre[0])}段落光影"]
        if request.scenes:
            imagery = (imagery + [f"{request.scenes[0]}里的细节"])[:4]
        if "热血" in mood_text or "史诗" in mood_text:
            primary = "热血" if "热血" in mood_text else "史诗"
            arousal += 0.12
        if "宁静" in mood_text or "松弛" in mood_text:
            arousal -= 0.12
            primary = "宁静"
        valence = max(-1.0, min(1.0, valence))
        arousal = max(0.0, min(1.0, arousal))
        secondary = [self._mood_label(mood) for mood in emotions[:6]]
        vocal_text = "、".join(request.vocal_types) or self._voice_label(request.voice_profile)
        arrangement_parts = list(request.genre[:3]) + list(request.instruments[:3]) + list(request.scenes[:2])
        return EmotionProfile(
            primaryEmotion=primary,
            secondaryEmotions=secondary,
            valence=round(valence, 2),
            arousal=round(arousal, 2),
            intensity=round(min(1.0, 0.55 + len(emotions) * 0.06), 2),
            tension=round(max(0.0, 0.48 + (-valence * 0.25)), 2),
            release=round(max(0.1, min(1.0, 0.55 + valence * 0.25 + arousal * 0.15)), 2),
            resonanceKeywords=[request.theme, request.audience, request.use_case, *categories[:2], *request.scenes[:2]],
            imageryKeywords=imagery,
            vocalDirection=vocal_text if request.vocal_required else "instrumental lead motif",
            arrangementDirection=f"{self._mode_label(request.mode)} with {', '.join(arrangement_parts) or 'balanced'} arrangement; emotion {primary}",
        )

    def _hook_line(self, request: MusicCreationRequest) -> str:
        theme = request.theme
        if "失恋" in self._selected_categories(request) and all(word in theme for word in ("放下", "等待", "消息")):
            return "我终于把你，还给昨天"
        return request.title or request.theme

    def _seed_for(self, task_id: str, work_id: str, version_id: str, number: int, request: MusicCreationRequest) -> str:
        raw = f"{task_id}|{work_id}|{version_id}|{number}|{request.theme}|{request.mode}"
        return uuid.uuid5(uuid.NAMESPACE_URL, raw).hex[:16]

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _full_duration_sec(self, request: MusicCreationRequest) -> int:
        requested = int(request.duration_sec or PRODUCT_MIN_DURATION_SEC)
        self._validate_product_duration(requested)
        return requested

    def _validate_product_duration(self, duration_sec: int) -> None:
        if not PRODUCT_MIN_DURATION_SEC <= int(duration_sec) <= PRODUCT_MAX_DURATION_SEC:
            raise ValueError(
                f"duration_sec must be a complete product between {PRODUCT_MIN_DURATION_SEC} and {PRODUCT_MAX_DURATION_SEC} seconds"
            )

    def _selected_categories(self, request: MusicCreationRequest) -> list[str]:
        values = list(getattr(request, "categories", []) or [])
        if request.category and request.category not in values:
            values.insert(0, request.category)
        return values

    def _selected_emotions(self, request: MusicCreationRequest) -> list[str]:
        values = list(getattr(request, "emotions", []) or [])
        for mood in request.mood:
            if mood not in values:
                values.append(mood)
        return values

    def _selected_languages(self, request: MusicCreationRequest) -> list[str]:
        values = list(getattr(request, "languages", []) or [])
        if request.language and request.language not in values:
            values.insert(0, request.language)
        return values

    def _candidate_strategy(self, number: int) -> dict[str, object]:
        strategies = [
            ("strong_drums", "更强鼓组版", ["drums", "bass", "energy_curve"], "full", "early chorus", "intro lift, chorus peak, final peak"),
            ("piano_ballad", "更钢琴抒情版", ["piano", "chords", "vocal_space"], "light", "chorus", "soft verse, broad final chorus"),
            ("electronic_texture", "更电子氛围版", ["synth_pulse", "pad_texture", "drum_grid"], "medium", "pre-chorus lift", "steady pulse, bright hook"),
            ("cinematic_build", "更影视铺陈版", ["strings", "riser", "section_timeline"], "dense", "final chorus", "slow build, bridge drop, final swell"),
            ("short_video_hook", "更短视频抓耳版", ["lead_motif", "hook_position", "drum_density"], "full", "first 15 seconds", "fast hook, compact peaks"),
        ]
        key, label, changed, density, hook_position, energy_curve = strategies[(number - 1) % len(strategies)]
        return {
            "candidate_index": number,
            "variation_type": key,
            "variation_type_zh": label,
            "changed_fields": changed,
            "arrangement_density": density,
            "hook_position": hook_position,
            "energy_curve": energy_curve,
        }

    def _default_bpm(self, request: MusicCreationRequest) -> int:
        if request.mode in {"loop", "bgm", "lofi"}:
            return 82
        if request.mode in {"short_video", "game"}:
            return 124
        if "classical" in request.genre:
            return 72
        return 104

    def _build_prompt(
        self,
        request: MusicCreationRequest,
        brief: str,
        number: int,
        candidate_strategy: dict[str, object] | None = None,
    ) -> str:
        candidate_strategy = candidate_strategy or self._candidate_strategy(number)
        density = ["clean arrangement", "strong hook", "more rhythmic motion", "wider cinematic texture", "minimal loop"][number - 1]
        style_strategy = self._style_strategy(request)
        tags = ", ".join(style_strategy["prompt_tags"])
        emotion = self._build_emotion_profile(request)
        imagery = ", ".join(emotion.imageryKeywords[:3])
        voice = self._voice_label(request.voice_profile)
        language_instruction = "English lyrics with Chinese translation metadata." if request.language == "en" else "Chinese lyrics when vocals are required."
        return (
            f"{brief} Candidate {number}: {density}; variation {candidate_strategy['variation_type_zh']}. Strategy: {tags}. Voice profile: {voice}. "
            f"Emotion profile: {emotion.primaryEmotion}, valence {emotion.valence}, arousal {emotion.arousal}; imagery: {imagery}. "
            f"Hook line: {self._hook_line(request)}. {language_instruction} Keep the theme central: {request.theme}. "
            "Keep it original and avoid protected song or singer imitation."
        )

    def _style_strategy(self, request: MusicCreationRequest) -> dict[str, object]:
        mode_tags = {
            "song": ("chorus lift", "singable title hook", "verse-to-chorus contrast"),
            "instrumental": ("lead motif", "dynamic contour", "clear arrangement layers"),
            "bgm": ("low-distraction loop", "stable pulse", "clean texture"),
            "loop": ("seamless tail", "repeating motif", "steady groove"),
            "short_video": ("first-three-second hook", "fast emotional signal", "memorable motif"),
            "children": ("small vocal range", "short phrases", "positive repeat"),
            "classical": ("motif development", "balanced dynamics", "clear form"),
            "game": ("loopable structure", "recognizable motif", "low fatigue"),
            "film": ("emotion arc", "scene-friendly dynamics", "transition points"),
        }
        tags = list(mode_tags.get(request.mode, mode_tags["song"]))
        if request.vocal_required:
            tags.append("vocal phrasing")
        else:
            tags.append("instrumental focus")
        categories = self._selected_categories(request)
        emotions = self._selected_emotions(request)
        languages = self._selected_languages(request)
        tags.extend(f"category:{category}" for category in categories)
        tags.extend(f"mood:{self._mood_label(mood)}" for mood in emotions)
        tags.extend(f"genre:{self._genre_label(genre)}" for genre in request.genre)
        tags.extend(f"scene:{scene}" for scene in request.scenes)
        tags.extend(f"instrument:{instrument}" for instrument in request.instruments)
        tags.extend(f"vocal:{vocal_type}" for vocal_type in request.vocal_types)
        tags.extend(f"language:{language}" for language in languages)
        return {
            "mode": request.mode,
            "category": request.category,
            "categories": categories,
            "genre": list(request.genre),
            "mood": list(request.mood),
            "emotions": emotions,
            "scenes": list(request.scenes),
            "instruments": list(request.instruments),
            "vocal_types": list(request.vocal_types),
            "languages": languages,
            "audience": request.audience,
            "use_case": request.use_case,
            "language": request.language,
            "voice_profile": request.voice_profile or "warm_male",
            "voice_label": self._voice_label(request.voice_profile),
            "prompt_tags": tags,
            "target_bpm": request.bpm or self._default_bpm(request),
            "target_duration_sec": request.duration_sec,
            "melody_plan": self._melody_plan(request),
            "harmony_plan": self._harmony_plan(request),
            "arrangement_plan": self._arrangement_plan(request),
            "reference_policy": "analyze style only; do not copy melody, lyrics, arrangement identity, or real singer voice",
        }

    def _melody_plan(self, request: MusicCreationRequest) -> dict[str, object]:
        return {
            "hook_position": "Chorus",
            "range": "comfortable vocal range" if request.vocal_required else "lead motif range",
            "contour": "verse restraint, chorus lift, final chorus release",
            "bpm": request.bpm or self._default_bpm(request),
        }

    def _harmony_plan(self, request: MusicCreationRequest) -> dict[str, object]:
        return {
            "key": request.key or "C",
            "progression_role": "minor-to-major release" if "失恋" in self._selected_categories(request) else "stable emotional support",
            "tension_release": "pre-chorus tension resolves into chorus",
        }

    def _arrangement_plan(self, request: MusicCreationRequest) -> dict[str, object]:
        return {
            "core_layers": list(request.instruments or request.genre or ["piano", "soft drums", "bass"]),
            "energy_arc": "intro sparse, chorus fuller, bridge stripped, final chorus widest",
            "vocal_direction": self._voice_label(request.voice_profile) if request.vocal_required else "instrumental lead motif",
        }

    def _mode_label(self, mode: str) -> str:
        return {
            "song": "歌曲",
            "instrumental": "纯音乐",
            "bgm": "背景音乐",
            "loop": "循环音乐",
            "short_video": "短视频音乐",
            "children": "儿童歌曲",
            "classical": "古典主题",
            "game": "游戏音乐",
            "film": "影视配乐",
        }.get(mode, mode)

    def _language_label(self, language: str) -> str:
        return {"zh": "中文", "en": "英文", "ja": "日文", "ko": "韩文", "none": ""}.get(language, language)

    def _voice_label(self, voice_profile: str | None) -> str:
        return {
            "warm_male": "温暖男声",
            "deep_male": "低沉男声",
            "clear_female": "清亮女声",
            "soft_female": "柔和女声",
            "youth": "少年感人声",
            "choir": "合唱人声",
            "narrative": "叙事型人声",
        }.get(voice_profile or "warm_male", voice_profile or "温暖男声")

    def _genre_label(self, genre: str) -> str:
        return {
            "pop": "流行",
            "electronic": "电子",
            "folk": "民谣",
            "rock": "摇滚",
            "r&b": "R&B",
            "cinematic": "影视感",
            "lo-fi": "Lo-fi",
            "chinese": "国风",
        }.get(genre, genre)

    def _mood_label(self, mood: str) -> str:
        return {
            "warm": "温暖",
            "hopeful": "有希望",
            "catchy": "抓耳",
            "resilient": "坚韧",
            "narrative": "叙事",
            "calm": "平静",
            "dark": "沉重",
            "uplifting": "向上",
            "emotional": "情绪化",
            "hook_forward": "强化记忆点",
            "audience_fit": "受众校准",
        }.get(mood, mood)

    def _label_list(self, values: list[str], labeler) -> str:
        return "、".join(labeler(value) for value in values) or "无"

    def _english_phrase(self, text: str) -> str:
        phrase = text.strip() or "this story"
        replacements = (
            ("一个", ""),
            ("成年男性", "a grown man"),
            ("男人", "a man"),
            ("男性", "man"),
            ("生活", "life"),
            ("苦难", "hardship"),
            ("城市夜晚", "city night"),
            ("夜晚", "night"),
            ("希望", "hope"),
            ("重新开始", "starting again"),
            ("和", " and "),
            ("与", " and "),
            ("的", " "),
        )
        for source, target in replacements:
            phrase = phrase.replace(source, target)
        phrase = " ".join(phrase.split()).strip(" ，,。")
        if any(ord(char) > 127 for char in phrase):
            return f"the story of {text}"
        return phrase or "this story"

    def _create_default_exports(self, version: MusicVersion, audio_path: Path, export_dir: Path) -> None:
        master_path = export_dir / f"{version.version_id}_master.wav"
        shutil.copyfile(audio_path, master_path)
        version.generation_route["full_export"] = {
            "kind": "master",
            "label_zh": f"完整版 {self._format_duration(version.duration_sec)}",
            "duration_sec": round(duration(master_path), 3),
            "checksum": checksum_file(master_path),
        }
        version.export_files.extend(
            [
                ExportFile(
                    id=f"export_{uuid.uuid4().hex[:8]}",
                    version_id=version.version_id,
                    kind="master",
                    format="wav",
                    path=str(master_path),
                    size_bytes=master_path.stat().st_size,
                    checksum=checksum_file(master_path),
                    ready=False,
                    blocked_reason="rights_status_missing",
                ),
            ]
        )

    def _format_duration(self, seconds: float) -> str:
        whole = max(0, int(round(seconds)))
        return f"{whole // 60}:{whole % 60:02d}"

    def _create_metadata_exports(self, version: MusicVersion, export_dir: Path) -> None:
        metadata_path = export_dir / f"{version.version_id}_metadata.json"
        metadata = {
            "version_id": version.version_id,
            "work_id": version.work_id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "title": version.title,
            "createdAt": version.createdAt,
            "generatedAt": version.generatedAt,
            "updatedAt": version.updatedAt,
            "optimizedAt": version.optimizedAt,
            "model_provider": version.model_provider,
            "model_name": version.model_name,
            "model_version": version.model_version,
            "seed": version.seed,
            "prompt_snapshot": version.prompt_snapshot,
            "emotion_profile": asdict(version.emotion_profile) if version.emotion_profile else None,
            "score_total": version.score_total,
            "failure_codes": version.failure_codes,
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        version.export_files.append(self._export_file(version.version_id, "metadata", metadata_path))
        if version.lyrics:
            lyrics_path = export_dir / f"{version.version_id}_lyrics.txt"
            lyrics_path.write_text(version.lyrics, encoding="utf-8")
            version.export_files.append(self._export_file(version.version_id, "lyrics", lyrics_path))

    def _export_file(self, version_id: str, kind: str, path: Path) -> ExportFile:
        return ExportFile(
            id=f"export_{uuid.uuid4().hex[:8]}",
            version_id=version_id,
            kind=kind,
            format=path.suffix.lstrip(".") or "wav",
            path=str(path),
            size_bytes=path.stat().st_size,
            checksum=checksum_file(path),
            ready=True,
        )

    def _ready_export(self, version: MusicVersion, kind: str) -> ExportFile | None:
        for export in version.export_files:
            if export.kind == kind and export.ready and export.path and Path(export.path).exists():
                return export
        return None

    def _score_version(self, version: MusicVersion, request: MusicCreationRequest) -> None:
        report = evaluate_version(version, request)
        version.score_total = int(report["total"])
        breakdown = {item["id"]: int(item["score"]) for item in report["dimensions"]}
        breakdown["melody"] = breakdown["melody_quality"]
        breakdown["catchy"] = breakdown["catchiness"]
        version.score_breakdown = breakdown
        version.quality_report = report
        version.failure_codes = list(report["failure_codes"])
        if version.failure_codes:
            version.status = "qa_fail"
        else:
            version.status = "qa_pass"
        version.loop_state = self._loop_state_for(version, report)
        version.updatedAt = self._now()

    def _mark_duplicate_candidates(self, versions: list[MusicVersion]) -> None:
        seen: dict[str, dict[str, str]] = {"seed": {}, "prompt_hash": {}, "audio_checksum": {}}
        for version in versions:
            prompt_hash = str(version.generation_route.get("prompt_hash") or hashlib.sha256(version.prompt_snapshot.encode("utf-8")).hexdigest())
            audio_checksum = self._audio_checksum_for_duplicate_check(version)
            checks = {
                "seed": str(version.seed or ""),
                "prompt_hash": prompt_hash,
                "audio_checksum": audio_checksum,
            }
            duplicate_evidence: list[str] = []
            for field, value in checks.items():
                if not value:
                    continue
                previous = seen[field].get(value)
                if previous:
                    duplicate_evidence.append(f"duplicate_{field}={value}; duplicate_with={previous}")
                else:
                    seen[field][value] = version.version_id
            if duplicate_evidence:
                self._append_failure_code(version, "DUPLICATE_CANDIDATE", duplicate_evidence)

    def _audio_checksum_for_duplicate_check(self, version: MusicVersion) -> str:
        if version.audio_path and Path(version.audio_path).exists():
            return checksum_file(Path(version.audio_path))
        for export in version.export_files:
            if export.kind in {"master", "source_download"} and export.checksum:
                return export.checksum
        return ""

    def _append_failure_code(self, version: MusicVersion, failure_code: str, evidence: list[str]) -> None:
        if failure_code not in version.failure_codes:
            version.failure_codes.append(failure_code)
        report = dict(version.quality_report or {})
        report_failures = list(report.get("failure_codes", []))
        if failure_code not in report_failures:
            report_failures.append(failure_code)
        report["failure_codes"] = report_failures
        rework_targets = list(report.get("rework_targets", []))
        rework_targets.append(
            {
                "failure_code": failure_code,
                "agent": "Generation Router",
                "action": "regenerate duplicate candidate with unique seed, prompt, and audio artifact",
            }
        )
        report["rework_targets"] = rework_targets
        version.quality_report = report
        version.status = "qa_fail"
        version.score_total = min(version.score_total or 0, 60)
        version.loop_state = self._loop_state_for(version, report)
        version.loop_state.evidence.extend(evidence)
        version.updatedAt = self._now()

    def _loop_state_for(self, version: MusicVersion, report: dict[str, object]) -> VersionLoopState:
        failure_codes = list(version.failure_codes)
        first_failure = failure_codes[0] if failure_codes else None
        rule = get_rework_rule(first_failure) if first_failure else None
        hard_gate_results = {
            "audio_decodable": bool(version.audio_path or version.download_url),
            "complete_lyrics": bool(not version.lyrics_data or self._lyrics_complete(version.lyrics_data)),
            "no_unresolved_failures": not failure_codes,
        }
        if rule:
            decision = "human_review" if rule.requires_human_review else "rework"
            if rule.delivery_block_only:
                decision = "delivery_blocked"
            capacity = "blocked" if rule.requires_human_review or rule.delivery_block_only else "rework"
            responsible = rule.target_agent
            next_action = rule.action
            preserve = list(rule.preserve_fields)
            mutable = list(rule.mutable_fields)
            retry_budget = rule.retry_budget
        elif first_failure:
            decision = "human_review"
            capacity = "blocked"
            responsible = "Rework Orchestrator"
            next_action = "inspect failure before retry"
            preserve = []
            mutable = []
            retry_budget = 0
        else:
            decision = "pass"
            capacity = "new_generation"
            responsible = "Music Quality Judge"
            next_action = "configure rights before delivery"
            preserve = ["theme", "lyrics", "structure", "prompt_snapshot"]
            mutable = []
            retry_budget = 0
        evidence = [
            f"score_total={version.score_total}",
            f"failure_codes={','.join(failure_codes) if failure_codes else 'none'}",
        ]
        return VersionLoopState(
            state=version.status,
            decision=decision,
            score_total=version.score_total or 0,
            score_breakdown=dict(version.score_breakdown),
            hard_gate_results=hard_gate_results,
            failure_codes=failure_codes,
            root_cause=first_failure or "quality_pass",
            evidence=evidence,
            rework_round_count=0,
            version_rework_count=0,
            parent_version_id=version.parent_version_id,
            rework_brief=next_action if first_failure else None,
            preserve_fields=preserve,
            mutable_fields=mutable,
            responsible_agent=responsible,
            next_agent=responsible,
            next_action=next_action,
            retry_budget=retry_budget,
            capacity_bucket=capacity,
            manual_review_reason=next_action if decision == "human_review" else None,
        )

    def _lyrics_complete(self, lyrics: SongLyrics) -> bool:
        section_names = {section.name.lower() for section in lyrics.sections}
        line_count = sum(len(section.lines) for section in lyrics.sections)
        return (
            bool(lyrics.hook)
            and any("chorus" in name for name in section_names)
            and "bridge" in section_names
            and "final chorus" in section_names
            and line_count >= 30
        )

    def _qa_summary(self, versions: list[MusicVersion]) -> str:
        best = max(version.score_total or 0 for version in versions)
        return f"{len(versions)} candidates generated. Best score: {best}. Formal master export blocked until rights are configured."

    def _rework_suggestions(self, versions: list[MusicVersion]) -> list[str]:
        suggestions: list[str] = []
        for version in versions:
            for failure in version.failure_codes:
                if failure == "BAD_DURATION":
                    suggestions.append(f"{version.version_id}: adjust section lengths and regenerate candidate.")
                elif failure == "ORIGINALITY_REVIEW_REQUIRED":
                    suggestions.append(f"{version.version_id}: run originality review before delivery.")
                else:
                    suggestions.append(f"{version.version_id}: inspect {failure}.")
        return suggestions or ["No immediate musical rework needed; configure rights before formal delivery."]

    def _write_result(self, work_dir: Path, result: MusicCreationResult) -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        with (work_dir / "result.json").open("w", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)

    def _generation_routes_for_request(self, request: MusicCreationRequest) -> tuple[tuple[GenerationRouter, dict[str, object]], ...]:
        if self.provider_registry is None:
            return ((self.generation_router, {
                "selected_provider_id": "env_or_direct",
                "selected_provider": self.generation_router.config.provider,
                "selected_model_name": self.generation_router.config.model_name,
                "selected_model_version": self.generation_router.config.model_version,
                "selected_adapter_type": self.generation_router.config.provider,
                "selected_license_scope": "unknown",
                "selected_commercial_use_allowed": False,
                "selected_requires_api_key": False,
                "selected_risk_flags": [],
                "selected_integration_status": "unknown",
                "selected_paid_dependency": False,
                "selected_production_enabled": False,
                "selected_license_evidence_refs": [],
                "selection_reason": "direct_router",
                "preferred_provider_id": None,
                "request_mode": request.mode,
                "request_vocal_required": request.vocal_required,
                "request_duration_sec": request.duration_sec,
                "evaluations": [],
            }),)
        return tuple(
            (GenerationRouter(provider.to_route_config()), trace)
            for provider, trace in self.provider_registry.selectable_providers(request, preferred_provider_id=self.preferred_provider_id)
        )

    def _generate_with_fallback(
        self,
        routes: tuple[tuple[GenerationRouter, dict[str, object]], ...],
        job: GenerationJob,
    ):
        failures: list[dict[str, object]] = []
        for router, trace in routes:
            try:
                artifact = router.generate(job)
            except Exception as exc:
                failures.append(
                    {
                        "provider_id": trace.get("selected_provider_id"),
                        "provider": trace.get("selected_provider"),
                        "model_name": trace.get("selected_model_name"),
                        "error": str(exc),
                    }
                )
                continue
            selected_trace = dict(trace)
            selected_trace["fallback_failures"] = failures
            selected_trace["fallback_used"] = bool(failures)
            return artifact, selected_trace
        raise RuntimeError(f"all generation providers failed: {failures}")

    def _generation_payload(
        self,
        request: MusicCreationRequest,
        brief: str,
        prompt: str,
        structure: list[SongSection],
        lyrics_data: SongLyrics | None,
        emotion_profile: EmotionProfile,
        style_strategy: dict[str, object],
        candidate_strategy: dict[str, object],
        seed: str,
        bpm: int,
        key: str,
    ) -> dict[str, object]:
        return {
            "brief": brief,
            "prompt_text": prompt,
            "request": asdict(request),
            "lyrics": asdict(lyrics_data) if lyrics_data else None,
            "emotion_profile": asdict(emotion_profile),
            "structure": [asdict(section) for section in structure],
            "style_strategy": style_strategy,
            "candidate_strategy": candidate_strategy,
            "seed": seed,
            "bpm": bpm,
            "key": key,
            "hard_constraints": {
                "no_real_song_copying": True,
                "no_real_singer_imitation": True,
                "must_pass_qa_before_delivery": True,
                "must_pass_rights_before_delivery": True,
            },
            "forbidden_constraints": list(request.forbidden),
            "reference_policy": style_strategy.get("reference_policy"),
        }
