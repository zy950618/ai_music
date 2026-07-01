from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EmotionProfile, ExportFile, LyricSection, MusicCreationResult, MusicVersion, SongLyrics, SongSection, VersionLoopState


class ResultRepository:
    def __init__(self, workspace: Path | str = "runs") -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def list_results(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for result_path in sorted(self.workspace.glob("task_*/result.json"), reverse=True):
            with result_path.open("r", encoding="utf-8") as handle:
                result = json.load(handle)
            result["_result_path"] = str(result_path)
            results.append(result)
        return results

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        result_path = self.workspace / task_id / "result.json"
        if not result_path.exists():
            return None
        with result_path.open("r", encoding="utf-8") as handle:
            result = json.load(handle)
        result["_result_path"] = str(result_path)
        return result

    def save_result(self, result: dict[str, Any]) -> None:
        task_id = str(result["task_id"])
        result_path = self.workspace / task_id / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: value for key, value in result.items() if key != "_result_path"}
        with result_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def rework_history(self) -> dict[str, Any]:
        results = self.list_results()
        results_by_task_id = {result["task_id"]: result for result in results}
        seen: set[tuple[str, str, str, str]] = set()
        events: list[dict[str, Any]] = []
        for result in results:
            for event in result.get("rework_history", []):
                key = (
                    str(event.get("source_task_id", "")),
                    str(event.get("source_version_id", "")),
                    str(event.get("failure_code", "")),
                    str(event.get("created_task_id", "")),
                )
                if key in seen:
                    continue
                seen.add(key)
                source = results_by_task_id.get(str(event.get("source_task_id")), {})
                created = results_by_task_id.get(str(event.get("created_task_id")), {})
                created_version = _selected_version(created)
                enriched = dict(event)
                enriched.update(
                    {
                        "source_work_id": source.get("work_id"),
                        "created_work_id": created.get("work_id"),
                        "created_selected_version_id": created.get("selected_version_id"),
                        "created_score_total": created_version.get("score_total") if created_version else None,
                        "created_rights_status": created.get("rights_status"),
                        "created_result_path": created.get("_result_path"),
                    }
                )
                events.append(enriched)
        events.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {
            "events": events,
            "summary": {
                "total_events": len(events),
                "by_failure_code": _count_by(events, "failure_code"),
                "by_target_agent": _count_by(events, "target_agent"),
                "by_root_task": _count_by(events, "root_task_id"),
            },
        }


def _selected_version(result: dict[str, Any]) -> dict[str, Any] | None:
    selected_version_id = result.get("selected_version_id")
    for version in result.get("versions", []):
        if version.get("version_id") == selected_version_id:
            return version
    return None


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def result_from_dict(data: dict[str, Any]) -> MusicCreationResult:
    versions: list[MusicVersion] = []
    for version in data["versions"]:
        lyrics_data_raw = version.get("lyrics_data")
        lyrics_data = None
        if isinstance(lyrics_data_raw, dict):
            lyrics_data = SongLyrics(
                title=lyrics_data_raw["title"],
                language=lyrics_data_raw["language"],
                theme=lyrics_data_raw["theme"],
                hook=lyrics_data_raw["hook"],
                sections=[LyricSection(**section) for section in lyrics_data_raw.get("sections", [])],
                emotional_arc=lyrics_data_raw.get("emotional_arc", ""),
                imagery_keywords=lyrics_data_raw.get("imagery_keywords", []),
                rhyme_notes=lyrics_data_raw.get("rhyme_notes", []),
                singability_notes=lyrics_data_raw.get("singability_notes", []),
                safety_notes=lyrics_data_raw.get("safety_notes", []),
            )
        emotion_raw = version.get("emotion_profile")
        emotion_profile = EmotionProfile(**emotion_raw) if isinstance(emotion_raw, dict) else None
        loop_raw = version.get("loop_state")
        loop_state = VersionLoopState(**loop_raw) if isinstance(loop_raw, dict) else None
        versions.append(
            MusicVersion(
                version_id=version["version_id"],
                title=version["title"],
                status=version["status"],
                audio_source=version["audio_source"],
                duration_sec=version["duration_sec"],
                structure=[SongSection(**section) for section in version.get("structure", [])],
                prompt_snapshot=version["prompt_snapshot"],
                model_provider=version["model_provider"],
                model_name=version["model_name"],
                failure_codes=version.get("failure_codes", []),
                work_id=version.get("work_id", data.get("work_id", "")),
                parent_version_id=version.get("parent_version_id"),
                version_number=float(version.get("version_number", 1.0)),
                seed=version.get("seed"),
                generation_route=version.get("generation_route", {}),
                audio_path=version.get("audio_path"),
                download_url=version.get("download_url"),
                bpm=version.get("bpm"),
                key=version.get("key"),
                lyrics=version.get("lyrics"),
                lyrics_data=lyrics_data,
                lyric_translation=version.get("lyric_translation"),
                emotion_profile=emotion_profile,
                model_version=version.get("model_version"),
                audio_analysis=version.get("audio_analysis", {}),
                score_total=version.get("score_total"),
                score_breakdown=version.get("score_breakdown", {}),
                quality_report=version.get("quality_report", {}),
                loop_state=loop_state,
                export_files=[ExportFile(**export) for export in version.get("export_files", [])],
                createdAt=version.get("createdAt", ""),
                generatedAt=version.get("generatedAt", ""),
                updatedAt=version.get("updatedAt", ""),
                optimizedAt=version.get("optimizedAt"),
            )
        )
    return MusicCreationResult(
        task_id=data["task_id"],
        work_id=data["work_id"],
        brief=data["brief"],
        versions=versions,
        qa_summary=data["qa_summary"],
        rework_suggestions=data.get("rework_suggestions", []),
        rights_status=data["rights_status"],
        selected_version_id=data.get("selected_version_id"),
        request_data=data.get("request_data", {}),
        parent_task_id=data.get("parent_task_id"),
        rework_reason=data.get("rework_reason"),
        rework_root_task_id=data.get("rework_root_task_id"),
        rework_depth=int(data.get("rework_depth", 0)),
        rework_history=data.get("rework_history", []),
        createdAt=data.get("createdAt", ""),
        updatedAt=data.get("updatedAt", ""),
        lastGeneratedAt=data.get("lastGeneratedAt"),
    )
