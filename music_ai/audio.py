from __future__ import annotations

import hashlib
import math
import shutil
import wave
from array import array
from pathlib import Path
from typing import Any


SAMPLE_RATE = 44_100
SAMPLE_WIDTH = 2
CHANNELS = 1
MAX_AMPLITUDE = 32767
SYNTH_CHUNK_FRAMES = SAMPLE_RATE // 2


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mock_arrangement_metadata(
    duration_sec: float,
    bpm: int,
    key_index: int = 0,
    seed_text: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, object]:
    payload = payload or {}
    style = payload.get("style_strategy") if isinstance(payload.get("style_strategy"), dict) else {}
    candidate = payload.get("candidate_strategy") if isinstance(payload.get("candidate_strategy"), dict) else {}
    genres = [str(item) for item in style.get("genre", [])] if isinstance(style, dict) else []
    moods = [str(item) for item in style.get("mood", [])] if isinstance(style, dict) else []
    instruments = [str(item) for item in style.get("instruments", [])] if isinstance(style, dict) else []
    density = str(candidate.get("arrangement_density", "medium")) if isinstance(candidate, dict) else "medium"
    layers = [
        {"id": "drums", "ui_label_zh": "鼓组", "role": "kick/snare/hi-hat groove", "density": density},
        {"id": "bass", "ui_label_zh": "贝斯", "role": "root motion and low-end support", "density": density},
        {"id": "chords", "ui_label_zh": "和弦", "role": "triad pad and harmonic bed", "density": "medium"},
        {"id": "lead", "ui_label_zh": "主旋律", "role": "seeded motif contour", "density": "medium"},
        {"id": "pad_texture", "ui_label_zh": "氛围铺底", "role": "wide pad/noise texture", "density": "low"},
    ]
    if any("Piano" in item or "钢琴" in item for item in instruments + genres):
        layers.append({"id": "piano_arp", "ui_label_zh": "钢琴分解", "role": "soft arpeggio accent", "density": "low"})
    if any("Synth" in item or "EDM" in item or "电子" in item for item in instruments + genres):
        layers.append({"id": "synth_pulse", "ui_label_zh": "合成器脉冲", "role": "electronic rhythmic color", "density": density})
    if any("Cinematic" in item or "电影" in item or "影视" in item for item in instruments + genres):
        layers.append({"id": "cinematic_riser", "ui_label_zh": "影视推进", "role": "section lift and impact swell", "density": "low"})

    section_names = ["Intro", "Verse 1", "Pre-Chorus", "Chorus", "Verse 2", "Bridge", "Final Chorus", "Outro"]
    if duration_sec < 60:
        section_names = ["Intro", "A Theme", "B Lift", "Hook", "Outro"]
    step = float(duration_sec) / len(section_names)
    timeline = [
        {
            "name": name,
            "start_sec": round(index * step, 2),
            "end_sec": round((index + 1) * step, 2),
            "energy": round(0.35 + 0.55 * _section_energy(index, len(section_names)), 2),
        }
        for index, name in enumerate(section_names)
    ]
    return {
        "seed_basis": hashlib.sha256(f"{seed_text}|{bpm}|{key_index}".encode("utf-8")).hexdigest()[:16],
        "arrangement_layers": layers,
        "instrument_plan": {
            "genres": genres,
            "moods": moods,
            "requested_instruments": instruments,
            "core": ["鼓组", "贝斯", "和弦", "主旋律", "氛围铺底"],
            "density": density,
        },
        "section_timeline": timeline,
    }


def generate_mock_wav(
    path: Path,
    duration_sec: float,
    bpm: int,
    key_index: int = 0,
    seed_text: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{seed_text}|{bpm}|{key_index}".encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    payload = payload or {}
    style = payload.get("style_strategy") if isinstance(payload.get("style_strategy"), dict) else {}
    candidate = payload.get("candidate_strategy") if isinstance(payload.get("candidate_strategy"), dict) else {}
    genres = " ".join(str(item) for item in style.get("genre", [])) if isinstance(style, dict) else ""
    moods = " ".join(str(item) for item in style.get("mood", [])) if isinstance(style, dict) else ""
    instruments = " ".join(str(item) for item in style.get("instruments", [])) if isinstance(style, dict) else ""
    density = str(candidate.get("arrangement_density", "medium")) if isinstance(candidate, dict) else "medium"
    density_gain = {"light": 0.78, "medium": 0.92, "full": 1.08, "dense": 1.16}.get(density, 0.92)
    drum_gain = 1.2 if any(token in genres for token in ("EDM", "House", "Hip-Hop", "Trap", "Short Video")) else 0.9
    drum_gain *= 1.15 if any(token in moods for token in ("热血", "明亮", "期待", "重生感", "catchy")) else 1.0
    pad_gain = 1.25 if any(token in genres + moods + instruments for token in ("Ambient", "Meditation", "梦幻", "宁静", "Pad")) else 0.85
    piano_gain = 1.18 if any(token in genres + instruments for token in ("Piano", "钢琴", "Ballad")) else 0.55
    cinematic_gain = 1.18 if any(token in genres + moods for token in ("Cinematic", "Orchestral", "电影", "影视", "史诗")) else 0.65
    base = 110.0 * (2 ** ((key_index + seed % 7) / 12))
    beat_hz = max(1, bpm) / 60.0
    total_frames = int(duration_sec * SAMPLE_RATE)
    motifs = (
        (0, 2, 4, 7, 9, 7, 4, 2),
        (0, 3, 5, 7, 10, 7, 5, 3),
        (0, 2, 5, 9, 12, 9, 5, 2),
        (0, -2, 3, 7, 10, 7, 3, -2),
        (0, 4, 7, 11, 12, 9, 7, 4),
    )
    motif = motifs[seed % len(motifs)]
    progression = ((0, 4, 7), (-3, 0, 4), (-5, -1, 2), (-7, -3, 0))

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(CHANNELS)
        handle.setsampwidth(SAMPLE_WIDTH)
        handle.setframerate(SAMPLE_RATE)
        section_count = 8 if duration_sec >= 60 else 5
        section_frames = max(1, total_frames // section_count)
        bytes_per_frame = SAMPLE_WIDTH * CHANNELS
        written_frames = 0
        for section_index in range(section_count):
            remaining = total_frames - written_frames
            current_section_frames = remaining if section_index == section_count - 1 else min(section_frames, remaining)
            if current_section_frames <= 0:
                break
            chunk_frames = min(current_section_frames, SYNTH_CHUNK_FRAMES)
            chunk = array("h")
            for local_frame in range(chunk_frames):
                frame = written_frames + local_frame
                t = frame / SAMPLE_RATE
                beat_phase = (t * beat_hz) % 1.0
                beat_number = int(t * beat_hz)
                bar_number = beat_number // 4
                beat_in_bar = beat_number % 4
                section_pos = frame / max(1, total_frames - 1)
                section_energy = _section_energy(section_index, section_count)
                motif_shift = (section_index + seed % 3) % len(motif)
                beat_index = int(t * beat_hz * 2) % len(motif)
                note = motif[beat_index]
                if section_index in {3, 6}:
                    note += 12 if beat_index in {2, 4} else 0
                melody_freq = base * 2 * (2 ** ((note + motif_shift % 3) / 12))
                chord = progression[(bar_number + section_index) % len(progression)]
                chord_phase = 2 * math.pi * t
                chord_wave = sum(math.sin(chord_phase * base * (2 ** (interval / 12))) for interval in chord) / len(chord)
                bass_note = chord[0] - 12 + (0 if beat_in_bar < 2 else 7)
                bass_freq = base * (2 ** (bass_note / 12))
                bass = math.sin(2 * math.pi * bass_freq * t) * max(0.0, 1.0 - beat_phase * 1.8)
                kick_env = math.exp(-beat_phase * 14.0) if beat_in_bar in {0, 2} and beat_phase < 0.22 else 0.0
                kick = math.sin(2 * math.pi * (48 + 28 * (1 - beat_phase)) * t) * kick_env
                snare_env = math.exp(-beat_phase * 24.0) if beat_in_bar in {1, 3} and beat_phase < 0.18 else 0.0
                snare_noise = _noise(seed, frame) * snare_env
                hat_phase = (t * beat_hz * (4 if density in {"full", "dense"} else 2)) % 1.0
                hat = _noise(seed ^ 0xA5A5, frame) * (math.exp(-hat_phase * 28.0) if hat_phase < 0.18 else 0.0)
                lead_env = 0.35 + 0.65 * max(0.0, 1.0 - ((t * beat_hz * 2) % 1.0) * 2.0)
                lead = math.sin(2 * math.pi * melody_freq * t) * lead_env
                pad = 0.55 * chord_wave + 0.25 * math.sin(2 * math.pi * base / 4 * t + section_index)
                piano = math.sin(2 * math.pi * melody_freq * 2 * t) * max(0.0, 1.0 - beat_phase * 2.5) if piano_gain > 0.6 and ((beat_number + seed) % 2 == 0) else 0.0
                riser = math.sin(2 * math.pi * (base * 3 + 12 * section_pos) * t) * (section_pos ** 1.4)
                texture = _noise(seed ^ 0x5C5C, frame) * 0.12 + math.sin(2 * math.pi * 0.07 * t + key_index)
                intro_trim = 0.55 if section_index == 0 else 1.0
                bridge_trim = 0.72 if section_index == 5 else 1.0
                drums = (0.95 * kick + 0.35 * snare_noise + 0.16 * hat) * drum_gain * section_energy * bridge_trim
                melodic = 0.32 * lead + 0.36 * chord_wave + 0.24 * bass
                ambience = 0.16 * pad * pad_gain + 0.08 * piano * piano_gain + 0.07 * riser * cinematic_gain + 0.04 * texture
                sample = (drums + melodic + ambience) * density_gain * intro_trim
                sample *= 0.58 + 0.18 * math.sin(math.pi * section_pos)
                chunk.append(_clamp_sample(int(MAX_AMPLITUDE * 0.52 * sample)))
            chunk_bytes = chunk.tobytes()
            repeats = (current_section_frames * bytes_per_frame) // len(chunk_bytes)
            remainder = (current_section_frames * bytes_per_frame) % len(chunk_bytes)
            handle.writeframes(chunk_bytes * repeats + chunk_bytes[:remainder])
            written_frames += current_section_frames


def _section_energy(index: int, total: int) -> float:
    if total <= 1:
        return 1.0
    curve = (0.45, 0.62, 0.78, 1.0, 0.72, 0.55, 1.08, 0.5)
    return curve[index % len(curve)]


def _noise(seed: int, frame: int) -> float:
    value = (frame * 1103515245 + seed * 12345 + 0x9E3779B9) & 0xFFFFFFFF
    return ((value / 0xFFFFFFFF) * 2.0) - 1.0


def read_wav(path: Path) -> tuple[wave._wave_params, bytes]:
    with wave.open(str(path), "rb") as handle:
        params = handle.getparams()
        frames = handle.readframes(handle.getnframes())
    return params, frames


def write_wav(path: Path, params: wave._wave_params, frames: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setparams(params)
        handle.writeframes(frames)


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def analyze_wav(path: Path) -> dict[str, object]:
    params, frames = read_wav(path)
    duration_sec = params.nframes / params.framerate if params.framerate else 0.0
    report: dict[str, object] = {
        "path": str(path),
        "duration_sec": round(duration_sec, 3),
        "sample_rate": params.framerate,
        "channels": params.nchannels,
        "sample_width": params.sampwidth,
        "frame_count": params.nframes,
        "technical_flags": [],
    }
    if params.sampwidth != 2:
        report.update(
            {
                "peak": None,
                "peak_dbfs": None,
                "rms": None,
                "rms_dbfs": None,
                "estimated_lufs": None,
                "clipped_sample_count": None,
                "clipping_ratio": None,
                "leading_silence_sec": None,
                "trailing_silence_sec": None,
                "silence_ratio": None,
                "technical_flags": ["UNSUPPORTED_SAMPLE_WIDTH"],
            }
        )
        return report

    samples = array("h")
    samples.frombytes(frames)
    if not samples:
        report.update(
            {
                "peak": 0.0,
                "peak_dbfs": None,
                "rms": 0.0,
                "rms_dbfs": None,
                "estimated_lufs": None,
                "clipped_sample_count": 0,
                "clipping_ratio": 0.0,
                "leading_silence_sec": duration_sec,
                "trailing_silence_sec": duration_sec,
                "silence_ratio": 1.0,
                "technical_flags": ["EMPTY_AUDIO"],
            }
        )
        return report

    normalized = [abs(sample) / MAX_AMPLITUDE for sample in samples]
    peak = max(normalized)
    rms = math.sqrt(sum(value * value for value in normalized) / len(normalized))
    clipped_count = sum(1 for value in normalized if value >= 0.999)
    silence_threshold = 0.005
    silent_count = sum(1 for value in normalized if value <= silence_threshold)
    leading_silence_sec = _edge_silence_seconds(normalized, params.framerate * params.nchannels, silence_threshold, from_start=True)
    trailing_silence_sec = _edge_silence_seconds(normalized, params.framerate * params.nchannels, silence_threshold, from_start=False)
    flags: list[str] = []
    if peak >= 0.999:
        flags.append("CLIPPING_RISK")
    if rms == 0:
        flags.append("SILENT_AUDIO")
    if leading_silence_sec > max(1.0, duration_sec * 0.15):
        flags.append("LONG_LEADING_SILENCE")
    if trailing_silence_sec > max(1.0, duration_sec * 0.2):
        flags.append("LONG_TRAILING_SILENCE")
    if silent_count / len(normalized) > 0.5:
        flags.append("EXCESSIVE_SILENCE")

    report.update(
        {
            "peak": round(peak, 6),
            "peak_dbfs": _dbfs(peak),
            "rms": round(rms, 6),
            "rms_dbfs": _dbfs(rms),
            "estimated_lufs": _dbfs(rms),
            "clipped_sample_count": clipped_count,
            "clipping_ratio": round(clipped_count / len(normalized), 6),
            "leading_silence_sec": round(leading_silence_sec, 3),
            "trailing_silence_sec": round(trailing_silence_sec, 3),
            "silence_ratio": round(silent_count / len(normalized), 6),
            "technical_flags": flags,
        }
    )
    return report


def _dbfs(value: float) -> float | None:
    if value <= 0:
        return None
    return round(20 * math.log10(value), 2)


def _edge_silence_seconds(samples: list[float], samples_per_second: int, threshold: float, from_start: bool) -> float:
    iterable = samples if from_start else reversed(samples)
    silent_samples = 0
    for value in iterable:
        if value > threshold:
            break
        silent_samples += 1
    return silent_samples / samples_per_second if samples_per_second else 0.0


def trim_wav(source: Path, target: Path, start_sec: float, end_sec: float) -> None:
    params, frames = read_wav(source)
    bytes_per_frame = params.sampwidth * params.nchannels
    start = max(0, int(start_sec * params.framerate))
    end = max(start, int(end_sec * params.framerate))
    sliced = frames[start * bytes_per_frame : end * bytes_per_frame]
    write_wav(target, params, sliced)


def fade_wav(source: Path, target: Path, fade_in_sec: float = 0.0, fade_out_sec: float = 0.0) -> None:
    params, frames = read_wav(source)
    if params.sampwidth != 2 or params.nchannels != 1:
        shutil.copyfile(source, target)
        return

    total_frames = len(frames) // 2
    fade_in_frames = int(fade_in_sec * params.framerate)
    fade_out_frames = int(fade_out_sec * params.framerate)
    output = bytearray(frames)

    for index in range(total_frames):
        gain = 1.0
        if fade_in_frames and index < fade_in_frames:
            gain *= index / fade_in_frames
        if fade_out_frames and index >= total_frames - fade_out_frames:
            gain *= max(0.0, (total_frames - index) / fade_out_frames)
        if gain == 1.0:
            continue
        offset = index * 2
        sample = int.from_bytes(output[offset : offset + 2], "little", signed=True)
        sample = int(sample * gain)
        output[offset : offset + 2] = sample.to_bytes(2, "little", signed=True)

    write_wav(target, params, bytes(output))


def normalize_peak_wav(source: Path, target: Path, target_peak: float = 0.89) -> None:
    params, frames = read_wav(source)
    if params.sampwidth != 2 or params.nchannels != 1:
        shutil.copyfile(source, target)
        return

    samples = array("h")
    samples.frombytes(frames)
    if not samples:
        write_wav(target, params, frames)
        return
    peak = max(abs(sample) for sample in samples)
    if peak == 0:
        write_wav(target, params, frames)
        return

    target_peak = max(0.01, min(1.0, target_peak))
    gain = (MAX_AMPLITUDE * target_peak) / peak
    processed = array("h", (_clamp_sample(int(sample * gain)) for sample in samples))
    write_wav(target, params, processed.tobytes())


def trim_silence_wav(source: Path, target: Path, threshold: float = 0.005, padding_sec: float = 0.05) -> None:
    params, frames = read_wav(source)
    if params.sampwidth != 2 or params.nchannels != 1:
        shutil.copyfile(source, target)
        return

    samples = array("h")
    samples.frombytes(frames)
    if not samples:
        write_wav(target, params, frames)
        return

    absolute_threshold = int(MAX_AMPLITUDE * max(0.0, min(1.0, threshold)))
    start = 0
    end = len(samples)
    while start < end and abs(samples[start]) <= absolute_threshold:
        start += 1
    while end > start and abs(samples[end - 1]) <= absolute_threshold:
        end -= 1
    padding = int(max(0.0, padding_sec) * params.framerate * params.nchannels)
    start = max(0, start - padding)
    end = min(len(samples), end + padding)
    processed = samples[start:end]
    write_wav(target, params, processed.tobytes())


def _clamp_sample(value: int) -> int:
    return max(-MAX_AMPLITUDE, min(MAX_AMPLITUDE, value))


def loop_wav(source: Path, target: Path, target_duration_sec: float) -> None:
    params, frames = read_wav(source)
    bytes_per_frame = params.sampwidth * params.nchannels
    target_frames = int(target_duration_sec * params.framerate)
    if not frames:
        write_wav(target, params, frames)
        return

    repeated = bytearray()
    while len(repeated) < target_frames * bytes_per_frame:
        repeated.extend(frames)
    write_wav(target, params, bytes(repeated[: target_frames * bytes_per_frame]))
