from __future__ import annotations

import hashlib
import math
import shutil
import wave
from array import array
from pathlib import Path


SAMPLE_RATE = 44_100
SAMPLE_WIDTH = 2
CHANNELS = 1
MAX_AMPLITUDE = 32767


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_mock_wav(path: Path, duration_sec: float, bpm: int, key_index: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = 220.0 * (2 ** (key_index / 12))
    beat_hz = bpm / 60.0
    frames = int(duration_sec * SAMPLE_RATE)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(CHANNELS)
        handle.setsampwidth(SAMPLE_WIDTH)
        handle.setframerate(SAMPLE_RATE)
        data = bytearray()
        for frame in range(frames):
            t = frame / SAMPLE_RATE
            envelope = 0.55 + 0.35 * math.sin(2 * math.pi * beat_hz * t)
            melody = math.sin(2 * math.pi * base * t)
            harmony = 0.45 * math.sin(2 * math.pi * base * 1.5 * t)
            sub = 0.25 * math.sin(2 * math.pi * base / 2 * t)
            sample = int(MAX_AMPLITUDE * 0.28 * envelope * (melody + harmony + sub) / 1.7)
            data.extend(sample.to_bytes(2, byteorder="little", signed=True))
        handle.writeframes(bytes(data))


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
