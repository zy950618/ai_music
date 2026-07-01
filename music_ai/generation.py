from __future__ import annotations

import json
import os
import subprocess
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .audio import generate_mock_wav, mock_arrangement_metadata
from .models import MusicCreationRequest


@dataclass(frozen=True)
class GenerationRouteConfig:
    provider: str = "mock"
    model_name: str = "mock_sine_arranger"
    model_version: str = "0.1.0"
    command: tuple[str, ...] = field(default_factory=tuple)
    timeout_sec: int = 120


@dataclass(frozen=True)
class GenerationProviderSpec:
    id: str
    provider: str
    model_name: str
    model_version: str
    enabled: bool = True
    priority: int = 100
    supported_modes: tuple[str, ...] = ("song", "instrumental", "bgm", "loop", "short_video", "children", "classical", "game", "film")
    supports_vocals: bool = True
    supports_instrumental: bool = True
    max_duration_sec: int = 600
    command: tuple[str, ...] = field(default_factory=tuple)
    timeout_sec: int = 120
    adapter_type: str = "mock_file"
    requires_api_key: bool = False
    license_scope: str = "internal_validation"
    commercial_use_allowed: bool = False
    risk_flags: tuple[str, ...] = field(default_factory=tuple)
    integration_status: str = "local_candidate"
    paid_dependency: bool = False
    production_enabled: bool = False
    license_evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def can_handle(self, request: MusicCreationRequest) -> bool:
        return not self.rejection_reasons(request)

    def rejection_reasons(self, request: MusicCreationRequest) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.enabled:
            reasons.append("disabled")
        if request.mode not in self.supported_modes:
            reasons.append("unsupported_mode")
        if request.vocal_required and not self.supports_vocals:
            reasons.append("vocals_not_supported")
        if not request.vocal_required and not self.supports_instrumental:
            reasons.append("instrumental_not_supported")
        if request.duration_sec > self.max_duration_sec:
            reasons.append("duration_too_long")
        if self.provider == "local_command" and not self.command:
            reasons.append("command_missing")
        if self.paid_dependency:
            reasons.append("paid_dependency")
        if self.integration_status == "research_only":
            reasons.append("research_only")
        if self.integration_status == "reject":
            reasons.append("reject")
        if self.requires_api_key and not os.environ.get("MUSIC_AI_PROVIDER_API_KEY"):
            reasons.append("api_key_missing")
        return tuple(reasons)

    def to_route_config(self) -> GenerationRouteConfig:
        return GenerationRouteConfig(
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
            command=self.command,
            timeout_sec=self.timeout_sec,
        )


class GenerationProviderRegistry:
    def __init__(self, providers: tuple[GenerationProviderSpec, ...] | None = None) -> None:
        self.providers = providers or default_provider_specs()

    @classmethod
    def from_file(cls, path: Path | str) -> "GenerationProviderRegistry":
        with Path(path).open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        providers = []
        for item in data.get("providers", []):
            providers.append(
                GenerationProviderSpec(
                    id=item["id"],
                    provider=item["provider"],
                    model_name=item["model_name"],
                    model_version=item.get("model_version", "unknown"),
                    enabled=item.get("enabled", True),
                    priority=int(item.get("priority", 100)),
                    supported_modes=tuple(item.get("supported_modes", [])) or GenerationProviderSpec.supported_modes,
                    supports_vocals=bool(item.get("supports_vocals", True)),
                    supports_instrumental=bool(item.get("supports_instrumental", True)),
                    max_duration_sec=int(item.get("max_duration_sec", 600)),
                    command=tuple(item.get("command", [])),
                    timeout_sec=int(item.get("timeout_sec", 120)),
                    adapter_type=item.get("adapter_type", "mock_file"),
                    requires_api_key=bool(item.get("requires_api_key", False)),
                    license_scope=item.get("license_scope", "internal_validation"),
                    commercial_use_allowed=bool(item.get("commercial_use_allowed", False)),
                    risk_flags=tuple(item.get("risk_flags", [])),
                    integration_status=item.get("integration_status", "local_candidate"),
                    paid_dependency=bool(item.get("paid_dependency", False)),
                    production_enabled=bool(item.get("production_enabled", False)),
                    license_evidence_refs=tuple(item.get("license_evidence_refs", [])),
                    notes=item.get("notes", ""),
                )
            )
        return cls(tuple(providers))

    def select(self, request: MusicCreationRequest, preferred_provider_id: str | None = None) -> GenerationProviderSpec:
        provider, _ = self.select_with_trace(request, preferred_provider_id=preferred_provider_id)
        return provider

    def select_with_trace(
        self, request: MusicCreationRequest, preferred_provider_id: str | None = None
    ) -> tuple[GenerationProviderSpec, dict[str, object]]:
        evaluations = []
        for provider in self.providers:
            reasons = provider.rejection_reasons(request)
            evaluations.append(
                {
                    "id": provider.id,
                    "provider": provider.provider,
                    "model_name": provider.model_name,
                    "priority": provider.priority,
                    "can_handle": not reasons,
                    "rejection_reasons": list(reasons),
                    "integration_status": provider.integration_status,
                    "paid_dependency": provider.paid_dependency,
                }
            )
        candidates = [provider for provider in self.providers if provider.can_handle(request)]
        if preferred_provider_id:
            for provider in candidates:
                if provider.id == preferred_provider_id:
                    return provider, self._selection_trace(request, provider, evaluations, preferred_provider_id, "preferred_provider")
            raise ValueError(f"preferred provider cannot handle request: {preferred_provider_id}")
        if not candidates:
            raise ValueError(f"no generation provider can handle mode={request.mode} vocal_required={request.vocal_required}")
        selected = sorted(candidates, key=lambda provider: provider.priority)[0]
        return selected, self._selection_trace(request, selected, evaluations, preferred_provider_id, "priority")

    def selectable_providers(self, request: MusicCreationRequest, preferred_provider_id: str | None = None) -> tuple[tuple[GenerationProviderSpec, dict[str, object]], ...]:
        selected, trace = self.select_with_trace(request, preferred_provider_id=preferred_provider_id)
        if preferred_provider_id:
            return ((selected, trace),)
        routes: list[tuple[GenerationProviderSpec, dict[str, object]]] = [(selected, trace)]
        for provider in sorted((item for item in self.providers if item.can_handle(request) and item.id != selected.id), key=lambda item: item.priority):
            routes.append((provider, self._selection_trace(request, provider, trace["evaluations"], preferred_provider_id, "fallback_priority")))
        return tuple(routes)

    def _selection_trace(
        self,
        request: MusicCreationRequest,
        selected: GenerationProviderSpec,
        evaluations: list[dict[str, object]],
        preferred_provider_id: str | None,
        reason: str,
    ) -> dict[str, object]:
        return {
            "selected_provider_id": selected.id,
            "selected_provider": selected.provider,
            "selected_model_name": selected.model_name,
            "selected_model_version": selected.model_version,
            "selected_adapter_type": selected.adapter_type,
            "selected_license_scope": selected.license_scope,
            "selected_commercial_use_allowed": selected.commercial_use_allowed,
            "selected_requires_api_key": selected.requires_api_key,
            "selected_risk_flags": list(selected.risk_flags),
            "selected_integration_status": selected.integration_status,
            "selected_paid_dependency": selected.paid_dependency,
            "selected_production_enabled": selected.production_enabled,
            "selected_license_evidence_refs": list(selected.license_evidence_refs),
            "selection_reason": reason,
            "preferred_provider_id": preferred_provider_id,
            "request_mode": request.mode,
            "request_vocal_required": request.vocal_required,
            "request_duration_sec": request.duration_sec,
            "evaluations": evaluations,
        }

    def snapshot(self) -> dict[str, object]:
        return {"providers": [provider.__dict__ for provider in self.providers]}


def default_provider_specs() -> tuple[GenerationProviderSpec, ...]:
    return (
        GenerationProviderSpec(
            id="mock_default",
            provider="mock",
            model_name="mock_sine_arranger",
            model_version="0.1.0",
            priority=100,
            notes="Deterministic internal generator used for development and validation.",
        ),
    )


@dataclass(frozen=True)
class GenerationJob:
    version_id: str
    prompt: str
    target_path: Path
    duration_sec: int
    bpm: int
    key_index: int
    seed: str | int | None = None
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationArtifact:
    audio_source: str
    audio_path: str | None
    download_url: str | None
    model_provider: str
    model_name: str
    model_version: str
    route_log: dict[str, object]


class GenerationRouter:
    def __init__(self, config: GenerationRouteConfig | None = None) -> None:
        self.config = config or GenerationRouteConfig()

    @classmethod
    def from_env(cls) -> "GenerationRouter":
        provider = os.environ.get("MUSIC_AI_GENERATION_PROVIDER", "mock")
        command_raw = os.environ.get("MUSIC_AI_LOCAL_COMMAND", "[]")
        try:
            command = tuple(json.loads(command_raw))
        except json.JSONDecodeError:
            command = ()
        return cls(
            GenerationRouteConfig(
                provider=provider,
                model_name=os.environ.get("MUSIC_AI_MODEL_NAME", "mock_sine_arranger" if provider == "mock" else provider),
                model_version=os.environ.get("MUSIC_AI_MODEL_VERSION", "0.1.0"),
                command=command,
                timeout_sec=int(os.environ.get("MUSIC_AI_GENERATION_TIMEOUT", "120")),
            )
        )

    def generate(self, job: GenerationJob) -> GenerationArtifact:
        if self.config.provider == "mock":
            return self._generate_mock(job)
        if self.config.provider == "local_command":
            return self._generate_local_command(job)
        raise ValueError(f"unsupported generation provider: {self.config.provider}")

    def _generate_mock(self, job: GenerationJob) -> GenerationArtifact:
        seed_text = str(job.seed) if job.seed is not None else job.prompt
        generate_mock_wav(
            job.target_path,
            job.duration_sec,
            job.bpm,
            key_index=job.key_index,
            seed_text=seed_text,
            payload=job.payload,
        )
        payload_hash = self._payload_hash(job)
        arrangement = mock_arrangement_metadata(
            job.duration_sec,
            job.bpm,
            key_index=job.key_index,
            seed_text=seed_text,
            payload=job.payload,
        )
        return GenerationArtifact(
            audio_source="mock_file",
            audio_path=str(job.target_path),
            download_url=None,
            model_provider="internal",
            model_name=self.config.model_name,
            model_version=self.config.model_version,
            route_log={
                "provider": "mock",
                "version_id": job.version_id,
                "target_path": str(job.target_path),
                "duration_sec": job.duration_sec,
                "bpm": job.bpm,
                "key_index": job.key_index,
                "seed": job.seed,
                "prompt_hash": hashlib.sha256(job.prompt.encode("utf-8")).hexdigest(),
                "arrangement_layers": arrangement["arrangement_layers"],
                "instrument_plan": arrangement["instrument_plan"],
                "section_timeline": arrangement["section_timeline"],
                "full_duration_sec": job.duration_sec,
                "payload_schema_version": "generation_payload_v1",
                "outbound_payload_hash": payload_hash,
            },
        )

    def _generate_local_command(self, job: GenerationJob) -> GenerationArtifact:
        if not self.config.command:
            raise ValueError("local_command provider requires MUSIC_AI_LOCAL_COMMAND or explicit command config")
        payload_path = job.target_path.with_suffix(".generation_payload.json")
        payload = self._payload_for_job(job)
        payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        command = tuple(self._format_arg(arg, job) for arg in self.config.command)
        env = os.environ.copy()
        cwd = str(Path.cwd())
        env["PYTHONPATH"] = cwd if not env.get("PYTHONPATH") else f"{cwd}{os.pathsep}{env['PYTHONPATH']}"
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.config.timeout_sec, check=False, env=env)
        if completed.returncode != 0:
            raise RuntimeError(f"local generation command failed: {completed.stderr.strip() or completed.stdout.strip()}")
        if not job.target_path.exists():
            raise RuntimeError(f"local generation command did not create output file: {job.target_path}")
        return GenerationArtifact(
            audio_source="local_command_file",
            audio_path=str(job.target_path),
            download_url=None,
            model_provider="local_command",
            model_name=self.config.model_name,
            model_version=self.config.model_version,
            route_log={
                "provider": "local_command",
                "version_id": job.version_id,
                "target_path": str(job.target_path),
                "duration_sec": job.duration_sec,
                "bpm": job.bpm,
                "seed": job.seed,
                "prompt_hash": hashlib.sha256(job.prompt.encode("utf-8")).hexdigest(),
                "payload_schema_version": "generation_payload_v1",
                "outbound_payload_hash": self._payload_hash(job),
                "outbound_payload_path": str(payload_path),
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-500:],
                "stderr_tail": completed.stderr[-500:],
            },
        )

    def _format_arg(self, arg: str, job: GenerationJob) -> str:
        return arg.format(
            output_path=str(job.target_path),
            duration_sec=job.duration_sec,
            bpm=job.bpm,
            prompt=job.prompt,
            payload_path=str(job.target_path.with_suffix(".generation_payload.json")),
            version_id=job.version_id,
            key_index=job.key_index,
        )

    def _payload_for_job(self, job: GenerationJob) -> dict[str, object]:
        payload = {
            "schema_version": "generation_payload_v1",
            "version_id": job.version_id,
            "prompt_text": job.prompt,
            "duration_sec": job.duration_sec,
            "bpm": job.bpm,
            "key_index": job.key_index,
            "seed": job.seed,
            "output_format": job.target_path.suffix.lstrip(".") or "wav",
        }
        payload.update(job.payload)
        return payload

    def _payload_hash(self, job: GenerationJob) -> str:
        raw = json.dumps(self._payload_for_job(job), ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
