from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import MusicCreationRequest, MusicVersion


@dataclass(frozen=True)
class AudienceStandard:
    profile: str
    likes: tuple[str, ...]
    avoid: tuple[str, ...]


AUDIENCE_STANDARDS: dict[str, AudienceStandard] = {
    "short_video": AudienceStandard(
        profile="Short-video listeners",
        likes=("clear first-three-second hook", "strong rhythm", "simple repeatable motif", "fast emotional signal"),
        avoid=("long intro", "unclear drop", "over-complex lyric idea"),
    ),
    "bgm": AudienceStandard(
        profile="Background music users",
        likes=("stable loop feel", "low distraction", "clean texture", "consistent energy"),
        avoid=("busy vocal", "sudden loud transition", "dominant lead line"),
    ),
    "game": AudienceStandard(
        profile="Game loop listeners",
        likes=("loopable structure", "recognizable motif", "steady pulse", "low fatigue over repetition"),
        avoid=("hard ending", "unstable tempo", "too much vocal focus"),
    ),
    "film": AudienceStandard(
        profile="Film and short-drama editors",
        likes=("clear emotion arc", "scene-friendly dynamics", "space for dialogue", "usable transition points"),
        avoid=("overcrowded mix", "random energy jump", "lyric distraction"),
    ),
    "children": AudienceStandard(
        profile="Children and family listeners",
        likes=("small vocal range", "short phrases", "positive hook", "simple rhythm"),
        avoid=("dark theme", "wide interval jumps", "complex metaphor"),
    ),
    "classical": AudienceStandard(
        profile="Classical and instrumental listeners",
        likes=("coherent motif development", "balanced dynamics", "clear form", "expressive phrasing"),
        avoid=("random loop repetition", "thin harmony", "unresolved climax"),
    ),
    "song": AudienceStandard(
        profile="General song listeners",
        likes=("memorable chorus", "singable lyric rhythm", "clear verse-to-chorus lift", "repeatable title hook"),
        avoid=("flat chorus", "crowded phrasing", "unclear theme"),
    ),
}


def evaluate_version(version: MusicVersion, request: MusicCreationRequest) -> dict[str, Any]:
    standard = AUDIENCE_STANDARDS.get(request.mode, AUDIENCE_STANDARDS["song"])
    dimensions = [
        _dimension("audio_quality", "Audio quality", _audio_quality(version), "Playable file, clean duration, no obvious technical block."),
        _dimension("melody_quality", "Melody quality", _melody_quality(version, request), "Clear motif or hook that fits the requested style."),
        _dimension("catchiness", "Catchiness", _catchiness(version, request), "Repeatable, easy-to-remember phrase or rhythm."),
        _dimension("structure_integrity", "Structure integrity", _structure_integrity(version, request), "Sections are complete and timing matches the target use."),
        _dimension("arrangement_fit", "Arrangement fit", _arrangement_fit(version, request), "Instrumentation and density match genre, mood, and use case."),
        _dimension("lyric_singability", "Lyric singability", _lyric_singability(version, request), "Lyrics can be sung naturally when vocals are required."),
        _dimension("audience_fit", "Audience fit", _audience_fit(version, request, standard), "Matches the target listener's liking and usage context."),
        _dimension("originality_safety", "Originality safety", _originality_safety(request), "Avoids protected melody, lyric, voice, and reference-copy risk."),
        _dimension("delivery_readiness", "Delivery readiness", _delivery_readiness(version), "Complete master or source is available and exports are traceable."),
    ]
    weights = {
        "audio_quality": 10,
        "melody_quality": 16,
        "catchiness": 15,
        "structure_integrity": 12,
        "arrangement_fit": 10,
        "lyric_singability": 10,
        "audience_fit": 12,
        "originality_safety": 10,
        "delivery_readiness": 5,
    }
    total = round(sum(item["score"] * weights[item["id"]] for item in dimensions) / sum(weights.values()))
    failure_codes = _failure_codes(dimensions, version, request)
    return {
        "total": max(0, min(100, total)),
        "dimensions": dimensions,
        "audience_standard": {
            "profile": standard.profile,
            "likes": list(standard.likes),
            "avoid": list(standard.avoid),
        },
        "audio_analysis": version.audio_analysis,
        "failure_codes": failure_codes,
        "rework_targets": _rework_targets(failure_codes),
    }


def _dimension(id: str, label: str, score: int, standard: str) -> dict[str, Any]:
    return {"id": id, "label": label, "score": max(0, min(100, score)), "standard": standard}


def _audio_quality(version: MusicVersion) -> int:
    if not version.audio_path and not version.download_url:
        return 35
    if version.duration_sec <= 0:
        return 30
    analysis = version.audio_analysis or {}
    flags = set(analysis.get("technical_flags", []))
    if flags & {"EMPTY_AUDIO", "SILENT_AUDIO", "UNSUPPORTED_SAMPLE_WIDTH"}:
        return 35
    if "EXTERNAL_AUDIO_NOT_ANALYZED" in flags:
        return 72

    score = 88
    if "CLIPPING_RISK" in flags:
        score -= 22
    if "EXCESSIVE_SILENCE" in flags:
        score -= 25
    if "LONG_LEADING_SILENCE" in flags:
        score -= 8
    if "LONG_TRAILING_SILENCE" in flags:
        score -= 6

    peak_dbfs = analysis.get("peak_dbfs")
    rms_dbfs = analysis.get("rms_dbfs")
    if isinstance(peak_dbfs, (int, float)) and peak_dbfs > -0.1:
        score -= 8
    if isinstance(rms_dbfs, (int, float)):
        if rms_dbfs < -35:
            score -= 12
        elif rms_dbfs > -8:
            score -= 8
    return score


def _melody_quality(version: MusicVersion, request: MusicCreationRequest) -> int:
    score = 82
    if request.vocal_required:
        score += 4
    if request.mode in {"short_video", "children", "song"}:
        score += 3
    if request.reference_profile_id:
        score -= 5
    return score


def _catchiness(version: MusicVersion, request: MusicCreationRequest) -> int:
    score = 80
    if request.mode in {"short_video", "children", "song"}:
        score += 7
    if request.bpm and 88 <= request.bpm <= 132:
        score += 3
    if request.duration_sec > 45 and request.mode == "short_video":
        score -= 12
    if version.lyrics and (request.title or request.theme) in version.lyrics:
        score += 3
    return score


def _structure_integrity(version: MusicVersion, request: MusicCreationRequest) -> int:
    score = 86
    if len(version.structure) < 4:
        score -= 18
    if abs(version.duration_sec - request.duration_sec) > max(1, request.duration_sec * 0.1):
        score -= 25
    if request.duration_sec < 10:
        score -= 8
    return score


def _arrangement_fit(version: MusicVersion, request: MusicCreationRequest) -> int:
    score = 84
    if "classical" in request.genre or request.mode == "classical":
        score += 2
    if request.mode in {"bgm", "loop", "game"} and request.vocal_required:
        score -= 8
    return score


def _lyric_singability(version: MusicVersion, request: MusicCreationRequest) -> int:
    if not request.vocal_required:
        return 86
    if version.lyrics_data:
        section_names = {section.name.lower() for section in version.lyrics_data.sections}
        line_count = sum(len(section.lines) for section in version.lyrics_data.sections)
        score = 88
        if not version.lyrics_data.hook:
            score -= 28
        if not any("chorus" in name for name in section_names):
            score -= 24
        if "bridge" not in section_names:
            score -= 14
        if "final chorus" not in section_names:
            score -= 12
        if line_count < 30:
            score -= 18
        if not version.lyrics_data.imagery_keywords:
            score -= 8
        if not version.lyrics_data.singability_notes:
            score -= 8
        return score
    if not version.lyrics:
        return 40
    lines = [line for line in version.lyrics.splitlines() if line and not line.startswith("[")]
    if len(lines) < 2:
        return 62
    return 84


def _audience_fit(version: MusicVersion, request: MusicCreationRequest, standard: AudienceStandard) -> int:
    score = 82
    audience_text = f"{request.audience} {request.use_case}".lower()
    if request.mode in audience_text:
        score += 2
    if request.mode == "short_video" and request.duration_sec <= 30:
        score += 5
    if request.mode in {"bgm", "game", "loop"} and request.duration_sec >= 20:
        score += 3
    if request.mode == "children" and request.vocal_required:
        score += 4
    if request.mode == "film" and request.vocal_required:
        score -= 6
    return score


def _originality_safety(request: MusicCreationRequest) -> int:
    score = 90
    if request.reference_profile_id:
        score -= 18
    forbidden_text = " ".join(request.forbidden).lower()
    if "copy" in forbidden_text or "imitation" in forbidden_text:
        score += 3
    return score


def _delivery_readiness(version: MusicVersion) -> int:
    ready_exports = [item for item in version.export_files if item.ready and (item.path or item.download_url)]
    if ready_exports:
        return 86
    if version.download_url:
        return 76
    return 45


def _failure_codes(dimensions: list[dict[str, Any]], version: MusicVersion, request: MusicCreationRequest) -> list[str]:
    scores = {item["id"]: item["score"] for item in dimensions}
    failures: list[str] = []
    if abs(version.duration_sec - request.duration_sec) > max(1, request.duration_sec * 0.1):
        failures.append("BAD_DURATION")
    if request.vocal_required and not version.lyrics:
        failures.append("LYRIC_MISSING")
    if request.vocal_required and version.lyrics_data:
        lyric_failures = _lyric_failure_codes(version)
        failures.extend(code for code in lyric_failures if code not in failures)
    if request.reference_profile_id:
        failures.append("ORIGINALITY_REVIEW_REQUIRED")
    if request.duration_sec < 10:
        failures.append("STRUCTURE_TOO_SHORT")
    if scores["catchiness"] < 75:
        failures.append("WEAK_HOOK")
    if scores["audience_fit"] < 72:
        failures.append("AUDIENCE_MISMATCH")
    if scores["audio_quality"] < 70:
        failures.append("TECHNICAL_AUDIO_FAIL")
    flags = set((version.audio_analysis or {}).get("technical_flags", []))
    if flags & {"CLIPPING_RISK", "EMPTY_AUDIO", "SILENT_AUDIO", "UNSUPPORTED_SAMPLE_WIDTH", "EXCESSIVE_SILENCE"}:
        if "TECHNICAL_AUDIO_FAIL" not in failures:
            failures.append("TECHNICAL_AUDIO_FAIL")
    return failures


def _lyric_failure_codes(version: MusicVersion) -> list[str]:
    lyrics = version.lyrics_data
    if lyrics is None:
        return []
    section_names = {section.name.lower() for section in lyrics.sections}
    line_count = sum(len(section.lines) for section in lyrics.sections)
    failures: list[str] = []
    if line_count < 30:
        failures.append("LYRIC_TOO_SHORT")
    if not lyrics.hook:
        failures.append("LYRIC_NO_HOOK")
    if not any("chorus" in name for name in section_names):
        failures.append("LYRIC_NO_CHORUS")
    if "bridge" not in section_names:
        failures.append("LYRIC_NO_BRIDGE")
    if "final chorus" not in section_names:
        failures.append("LYRIC_NO_FINAL_CHORUS")
    if not lyrics.emotional_arc or not lyrics.imagery_keywords:
        failures.append("EMOTION_MISMATCH")
    if not lyrics.singability_notes:
        failures.append("LYRIC_UNSINGABLE")
    return failures


def _rework_targets(failure_codes: list[str]) -> list[dict[str, str]]:
    targets = {
        "BAD_DURATION": ("Structure Arranger", "adjust section timing"),
        "LYRIC_MISSING": ("Lyric Writer", "write lyrics before regeneration"),
        "STRUCTURE_TOO_SHORT": ("Brief Parser", "increase duration and clarify sections"),
        "ORIGINALITY_REVIEW_REQUIRED": ("Originality Guard", "review reference risk"),
        "WEAK_HOOK": ("Melody Composer", "strengthen hook and motif repetition"),
        "AUDIENCE_MISMATCH": ("Audience Profiler", "restate listener standard and adapt brief"),
        "TECHNICAL_AUDIO_FAIL": ("Audio Analyzer", "inspect source audio and regenerate or process"),
        "DUPLICATE_CANDIDATE": ("Generation Router", "regenerate duplicate candidate with unique seed, prompt, and audio artifact"),
        "LYRIC_TOO_SHORT": ("Lyric Writer", "expand lyric sections before generation"),
        "LYRIC_NO_HOOK": ("Lyric Writer", "write an explicit hook line"),
        "LYRIC_NO_CHORUS": ("Lyric Writer", "add chorus sections"),
        "LYRIC_NO_BRIDGE": ("Lyric Writer", "add a bridge section"),
        "LYRIC_NO_FINAL_CHORUS": ("Lyric Writer", "add an intensified final chorus"),
        "LYRIC_UNSINGABLE": ("Lyric Editor", "repair line length, stress, and breath points"),
        "EMOTION_MISMATCH": ("Lyric Emotion Agent", "realign emotion arc and imagery"),
    }
    return [{"failure_code": code, "agent": targets[code][0], "action": targets[code][1]} for code in failure_codes if code in targets]
