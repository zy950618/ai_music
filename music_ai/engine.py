from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .audio import analyze_wav, checksum_file, duration, fade_wav, loop_wav, normalize_peak_wav, trim_silence_wav, trim_wav
from .generation import GenerationJob, GenerationProviderRegistry, GenerationRouter
from .models import (
    EditDecision,
    ExportFile,
    MusicCreationRequest,
    MusicCreationResult,
    MusicVersion,
    RightsConfiguration,
    SongSection,
)
from .quality import evaluate_version


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

        brief = self._build_brief(request)
        structure = self._build_structure(request.duration_sec, request.vocal_required)
        lyrics = self._build_lyrics(request) if request.vocal_required else None
        bpm = request.bpm or self._default_bpm(request)
        key = request.key or "C"
        generation_router, selection_trace = self._router_for_request(request)
        style_strategy = self._style_strategy(request)

        versions: list[MusicVersion] = []
        for index in range(candidate_count):
            version_id = f"v{index + 1}_{uuid.uuid4().hex[:6]}"
            audio_path = audio_dir / f"{version_id}.wav"
            prompt = self._build_prompt(request, brief, index + 1)
            artifact = generation_router.generate(
                GenerationJob(
                    version_id=version_id,
                    prompt=prompt,
                    target_path=audio_path,
                    duration_sec=request.duration_sec,
                    bpm=bpm + index * 2,
                    key_index=index,
                )
            )
            if not artifact.audio_path:
                raise ValueError("generation artifact must provide a local audio path")
            route_log = dict(artifact.route_log)
            route_log["selection"] = selection_trace
            route_log["style_strategy"] = style_strategy
            version = MusicVersion(
                version_id=version_id,
                title=f"{request.title or request.theme} - candidate {index + 1}",
                status="generated",
                audio_source=artifact.audio_source,
                audio_path=artifact.audio_path,
                duration_sec=duration(audio_path),
                audio_analysis=analyze_wav(audio_path),
                bpm=bpm + index * 2,
                key=key,
                lyrics=lyrics,
                structure=structure,
                prompt_snapshot=prompt,
                model_provider=artifact.model_provider,
                model_name=artifact.model_name,
                model_version=artifact.model_version,
                generation_route=route_log,
                failure_codes=[],
            )
            self._create_default_exports(version, audio_path, export_dir)
            self._score_version(version, request)
            versions.append(version)

        selected = max(versions, key=lambda item: item.score_total or 0)
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
        result = self.create(request, candidate_count=candidate_count)
        version = result.versions[0]
        version.audio_source = "external_download_url"
        version.download_url = download_url
        version.audio_path = None
        version.duration_sec = duration_sec
        version.audio_analysis = {
            "duration_sec": duration_sec,
            "technical_flags": ["EXTERNAL_AUDIO_NOT_ANALYZED"],
            "source": "external_download_url",
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
        return self._export_file(version.version_id, "preview", target_path)

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
        with license_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
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
                    "notes": rights.notes,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

        for version in result.versions:
            for export in version.export_files:
                if export.kind == "master" and export.blocked_reason == "rights_status_missing":
                    export.ready = True
                    export.blocked_reason = None
            version.export_files.append(self._export_file(version.version_id, "license_pack", license_path))

        result.rights_status = "configured"
        result.qa_summary = f"{result.qa_summary} Rights configured; master exports are ready."
        self._write_result(work_dir, result)
        return result

    def create_delivery_package(self, result: MusicCreationResult, selected_version_id: str | None = None) -> ExportFile:
        if result.rights_status != "configured":
            raise ValueError("rights must be configured before creating a delivery package")

        version_id = selected_version_id or result.selected_version_id
        version = next((item for item in result.versions if item.version_id == version_id), None)
        if version is None:
            raise ValueError("selected version not found")

        master = self._ready_export(version, "master")
        license_pack = self._ready_export(version, "license_pack")
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
        with Path(license_pack.path or "").open("r", encoding="utf-8") as handle:
            rights_metadata = json.load(handle)

        metadata = {
            "task_id": result.task_id,
            "work_id": result.work_id,
            "version_id": version.version_id,
            "title": version.title,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "brief": result.brief,
            "model_provider": version.model_provider,
            "model_name": version.model_name,
            "model_version": version.model_version,
            "prompt_snapshot": version.prompt_snapshot,
            "rights_status": result.rights_status,
            "rights": rights_metadata,
            "generation_route": version.generation_route,
            "score_total": version.score_total,
            "score_breakdown": version.score_breakdown,
            "audio_analysis": version.audio_analysis,
        }
        acceptance = {
            "qa_summary": result.qa_summary,
            "quality_report": version.quality_report,
            "failure_codes": version.failure_codes,
            "rework_suggestions": result.rework_suggestions,
            "delivery_decision": "ready",
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
        if version.lyrics:
            lyrics_path.write_text(version.lyrics, encoding="utf-8")

        package_entries: list[tuple[Path, str]] = [
            (Path(master.path or ""), f"audio/master{Path(master.path or '').suffix}"),
            (Path(license_pack.path or ""), "rights/license_pack.json"),
            (metadata_path, "metadata/metadata.json"),
            (acceptance_path, "reports/acceptance_report.json"),
        ]
        preview = self._ready_export(version, "preview")
        if preview and preview.path:
            package_entries.append((Path(preview.path), f"audio/preview{Path(preview.path).suffix}"))
        if version.lyrics:
            package_entries.append((lyrics_path, "lyrics/lyrics.txt"))

        manifest = {
            "package_type": "ai_music_delivery_package",
            "task_id": result.task_id,
            "work_id": result.work_id,
            "version_id": version.version_id,
            "platform_profile_id": rights_metadata.get("platform_profile_id"),
            "export_profile": rights_metadata.get("export_profile"),
            "manual_approval_required": rights_metadata.get("manual_approval_required", False),
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

    def _build_brief(self, request: MusicCreationRequest) -> str:
        vocals = "with vocal melody and lyrics" if request.vocal_required else "instrumental only"
        return (
            f"Create a {request.duration_sec}s {', '.join(request.genre)} {request.mode} for {request.use_case}. "
            f"Theme: {request.theme}. Mood: {', '.join(request.mood)}. Audience: {request.audience}. "
            f"Mode: {vocals}. Avoid: {', '.join(request.forbidden) or 'none'}."
        )

    def _build_structure(self, duration_sec: int, vocal_required: bool) -> list[SongSection]:
        if vocal_required:
            names = ["intro", "verse", "pre", "chorus", "outro"]
        else:
            names = ["intro", "A theme", "B lift", "climax", "loop outro"]
        step = duration_sec / len(names)
        return [
            SongSection(name=name, start_sec=round(index * step, 2), end_sec=round((index + 1) * step, 2), goal=f"{name} development")
            for index, name in enumerate(names)
        ]

    def _build_lyrics(self, request: MusicCreationRequest) -> str:
        if request.lyrics_input:
            return request.lyrics_input
        hook = request.title or request.theme
        return "\n".join(
            [
                "[Verse]",
                f"沿着{request.theme}的光慢慢靠近",
                "把心跳写进今晚的风景",
                "[Chorus]",
                f"{hook}，让旋律记住你",
                f"{hook}，在每一次回响里",
            ]
        )

    def _default_bpm(self, request: MusicCreationRequest) -> int:
        if request.mode in {"loop", "bgm", "lofi"}:
            return 82
        if request.mode in {"short_video", "game"}:
            return 124
        if "classical" in request.genre:
            return 72
        return 104

    def _build_prompt(self, request: MusicCreationRequest, brief: str, number: int) -> str:
        density = ["clean arrangement", "strong hook", "more rhythmic motion", "wider cinematic texture", "minimal loop"][number - 1]
        tags = ", ".join(self._style_strategy(request)["prompt_tags"])
        return f"{brief} Candidate {number}: {density}. Strategy: {tags}. Keep it original and avoid protected song or singer imitation."

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
        return {
            "mode": request.mode,
            "genre": list(request.genre),
            "audience": request.audience,
            "use_case": request.use_case,
            "prompt_tags": tags,
            "target_bpm": request.bpm or self._default_bpm(request),
            "target_duration_sec": request.duration_sec,
            "reference_policy": "analyze style only; do not copy melody, lyrics, arrangement identity, or real singer voice",
        }

    def _create_default_exports(self, version: MusicVersion, audio_path: Path, export_dir: Path) -> None:
        preview_path = export_dir / f"{version.version_id}_preview.wav"
        master_path = export_dir / f"{version.version_id}_master.wav"
        shutil.copyfile(audio_path, preview_path)
        shutil.copyfile(audio_path, master_path)
        version.export_files.extend(
            [
                self._export_file(version.version_id, "preview", preview_path),
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

    def _router_for_request(self, request: MusicCreationRequest) -> tuple[GenerationRouter, dict[str, object]]:
        if self.provider_registry is None:
            return self.generation_router, {
                "selected_provider_id": "env_or_direct",
                "selected_provider": self.generation_router.config.provider,
                "selected_model_name": self.generation_router.config.model_name,
                "selected_model_version": self.generation_router.config.model_version,
                "selection_reason": "direct_router",
                "preferred_provider_id": None,
                "request_mode": request.mode,
                "request_vocal_required": request.vocal_required,
                "request_duration_sec": request.duration_sec,
                "evaluations": [],
            }
        provider, trace = self.provider_registry.select_with_trace(request, preferred_provider_id=self.preferred_provider_id)
        return GenerationRouter(provider.to_route_config()), trace
