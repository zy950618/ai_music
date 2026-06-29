from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from music_ai.audio import MAX_AMPLITUDE, SAMPLE_RATE, analyze_wav, generate_mock_wav, normalize_peak_wav, trim_silence_wav


class AudioAnalysisTest(unittest.TestCase):
    def test_analyze_mock_wav_reports_playable_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mock.wav"
            generate_mock_wav(path, duration_sec=2, bpm=100)

            report = analyze_wav(path)

            self.assertAlmostEqual(report["duration_sec"], 2, delta=0.01)
            self.assertEqual(report["sample_rate"], SAMPLE_RATE)
            self.assertEqual(report["channels"], 1)
            self.assertGreater(report["peak"], 0)
            self.assertGreater(report["rms"], 0)
            self.assertEqual(report["technical_flags"], [])

    def test_analyze_clipped_wav_flags_clipping_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "clipped.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(SAMPLE_RATE)
                sample = MAX_AMPLITUDE.to_bytes(2, "little", signed=True)
                handle.writeframes(sample * SAMPLE_RATE)

            report = analyze_wav(path)

            self.assertIn("CLIPPING_RISK", report["technical_flags"])
            self.assertGreater(report["clipping_ratio"], 0.9)

    def test_normalize_peak_wav_adjusts_peak_level(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.wav"
            target = Path(temp_dir) / "normalized.wav"
            generate_mock_wav(source, duration_sec=1, bpm=100)

            normalize_peak_wav(source, target, target_peak=0.5)
            report = analyze_wav(target)

            self.assertAlmostEqual(report["peak"], 0.5, delta=0.02)

    def test_trim_silence_wav_removes_leading_and_trailing_silence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "silence.wav"
            target = Path(temp_dir) / "trimmed.wav"
            with wave.open(str(source), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(SAMPLE_RATE)
                silence = (0).to_bytes(2, "little", signed=True) * SAMPLE_RATE
                tone = (1000).to_bytes(2, "little", signed=True) * SAMPLE_RATE
                handle.writeframes(silence + tone + silence)

            trim_silence_wav(source, target, threshold=0.005, padding_sec=0)

            self.assertAlmostEqual(analyze_wav(target)["duration_sec"], 1, delta=0.01)


if __name__ == "__main__":
    unittest.main()
