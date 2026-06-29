from __future__ import annotations

import tempfile
import sys
import textwrap
import unittest
import zipfile
import json
from pathlib import Path

from music_ai.audio import duration
from music_ai.engine import CreationEngine
from music_ai.generation import GenerationRouteConfig, GenerationRouter
from music_ai.models import MusicCreationRequest, RightsConfiguration


class CreationEngineTest(unittest.TestCase):
    def make_request(self) -> MusicCreationRequest:
        return MusicCreationRequest(
            title="测试歌曲",
            mode="song",
            language="zh",
            theme="夏夜里的新开始",
            mood=["bright", "catchy"],
            genre=["pop"],
            audience="short video creators",
            use_case="phase 1 validation",
            duration_sec=12,
            bpm=108,
            key="C",
            vocal_required=True,
            forbidden=["real singer imitation"],
        )

    def test_create_generates_candidates_downloads_analysis_and_blocks_master_without_rights(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            result = engine.create(self.make_request(), candidate_count=3)

            self.assertEqual(len(result.versions), 3)
            self.assertEqual(result.rights_status, "missing")
            self.assertTrue(result.selected_version_id)
            for version in result.versions:
                self.assertIsNotNone(version.audio_path)
                self.assertTrue(Path(version.audio_path or "").exists())
                self.assertGreaterEqual(version.score_total or 0, 80)
                self.assertEqual(version.audio_analysis["sample_rate"], 44100)
                self.assertIn("peak_dbfs", version.audio_analysis)
                self.assertEqual(version.generation_route["provider"], "mock")
                self.assertEqual(version.generation_route["selection"]["selection_reason"], "direct_router")
                self.assertEqual(version.generation_route["style_strategy"]["mode"], "song")
                self.assertIn("prompt_tags", version.generation_route["style_strategy"])
                self.assertIn("melody", version.score_breakdown)
                self.assertIn("catchy", version.score_breakdown)
                self.assertIn("catchiness", version.score_breakdown)
                self.assertIn("audience_fit", version.score_breakdown)
                self.assertIn("audio_analysis", version.quality_report)
                self.assertIn("audience_standard", version.quality_report)
                preview = [item for item in version.export_files if item.kind == "preview"]
                master = [item for item in version.export_files if item.kind == "master"]
                self.assertTrue(preview and preview[0].ready)
                self.assertTrue(master and not master[0].ready)
                self.assertEqual(master[0].blocked_reason, "rights_status_missing")

            result_file = Path(temp_dir) / result.task_id / "result.json"
            self.assertTrue(result_file.exists())

    def test_editing_renders_trim_fade_and_loop_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            result = engine.create(self.make_request(), candidate_count=3)
            selected = next(version for version in result.versions if version.version_id == result.selected_version_id)
            export_dir = Path(temp_dir) / result.task_id / "exports"

            trim_export = engine.render_trim(selected, 0, 5, export_dir / "trim.wav")
            fade_export = engine.render_fade(selected, 0.25, 0.25, export_dir / "fade.wav")
            loop_export = engine.render_loop(selected, 8, export_dir / "loop.wav")
            normalized_export = engine.render_normalized(selected, export_dir / "normalized.wav", target_peak=0.5)
            silence_trimmed_export = engine.render_silence_trimmed(selected, export_dir / "silence_trimmed.wav")

            self.assertTrue(Path(trim_export.path or "").exists())
            self.assertTrue(Path(fade_export.path or "").exists())
            self.assertTrue(Path(loop_export.path or "").exists())
            self.assertTrue(Path(normalized_export.path or "").exists())
            self.assertTrue(Path(silence_trimmed_export.path or "").exists())
            self.assertAlmostEqual(duration(Path(trim_export.path or "")), 5, delta=0.1)
            self.assertAlmostEqual(duration(Path(loop_export.path or "")), 8, delta=0.1)
            self.assertGreaterEqual(len(selected.edit_decisions), 5)
            self.assertTrue(any(decision.operation == "normalize_peak" for decision in selected.edit_decisions))
            self.assertTrue(any(decision.operation == "trim_silence" for decision in selected.edit_decisions))

    def test_external_download_url_is_registered_as_candidate_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            result = engine.import_external_download(
                self.make_request(),
                download_url="https://example.test/generated.wav",
                duration_sec=42,
            )
            version = result.versions[0]
            self.assertEqual(version.audio_source, "external_download_url")
            self.assertEqual(version.download_url, "https://example.test/generated.wav")
            self.assertEqual(version.duration_sec, 42)
            self.assertIn("EXTERNAL_AUDIO_NOT_ANALYZED", version.audio_analysis["technical_flags"])
            self.assertIn("audio_quality", version.score_breakdown)
            self.assertTrue(any(item.kind == "source_download" and item.ready for item in version.export_files))

    def test_create_can_use_local_command_generation_router(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(temp_dir) / "generate.py"
            script.write_text(
                textwrap.dedent(
                    """
                    import sys
                    from pathlib import Path
                    from music_ai.audio import generate_mock_wav
                    generate_mock_wav(Path(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]))
                    """
                ),
                encoding="utf-8",
            )
            router = GenerationRouter(
                GenerationRouteConfig(
                    provider="local_command",
                    model_name="local-engine-test",
                    model_version="test-1",
                    command=(sys.executable, str(script), "{output_path}", "{duration_sec}", "{bpm}"),
                    timeout_sec=30,
                )
            )
            engine = CreationEngine(temp_dir, generation_router=router)

            result = engine.create(self.make_request(), candidate_count=3)

            self.assertEqual(len(result.versions), 3)
            self.assertTrue(all(version.audio_source == "local_command_file" for version in result.versions))
            self.assertTrue(all(version.model_name == "local-engine-test" for version in result.versions))
            self.assertTrue(all(version.generation_route["provider"] == "local_command" for version in result.versions))
            self.assertTrue(all(version.generation_route["selection"]["selection_reason"] == "direct_router" for version in result.versions))

    def test_configure_rights_unblocks_master_and_creates_license_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            result = engine.create(self.make_request(), candidate_count=3)
            result = engine.configure_rights(
                result,
                RightsConfiguration(
                    rights_owner="Test Owner",
                    usage_scope="internal validation",
                    territory="worldwide",
                    duration="perpetual",
                    ai_disclosure="AI generated with human QA.",
                    model_license="mock generator",
                    commercial_use_allowed=False,
                    platform_profile_id="internal_export",
                    export_profile="wav_master_preview_license",
                    manual_approval_required=False,
                ),
            )

            self.assertEqual(result.rights_status, "configured")
            for version in result.versions:
                master = [item for item in version.export_files if item.kind == "master"]
                license_pack = [item for item in version.export_files if item.kind == "license_pack"]
                self.assertTrue(master and master[0].ready)
                self.assertIsNone(master[0].blocked_reason)
                self.assertTrue(license_pack and license_pack[0].ready)
                self.assertTrue(Path(license_pack[0].path or "").exists())

    def test_delivery_package_requires_rights_and_contains_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            result = engine.create(self.make_request(), candidate_count=3)
            with self.assertRaises(ValueError):
                engine.create_delivery_package(result)

            result = engine.configure_rights(
                result,
                RightsConfiguration(
                    rights_owner="Test Owner",
                    usage_scope="internal validation",
                    territory="worldwide",
                    duration="perpetual",
                    ai_disclosure="AI generated with human QA.",
                    model_license="mock generator",
                    commercial_use_allowed=False,
                    platform_profile_id="internal_export",
                    export_profile="wav_master_preview_license",
                    manual_approval_required=False,
                ),
            )

            export = engine.create_delivery_package(result)

            self.assertEqual(export.kind, "delivery_package")
            self.assertTrue(export.ready)
            package_path = Path(export.path or "")
            self.assertTrue(package_path.exists())
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
                metadata = json.loads(archive.read("metadata/metadata.json").decode("utf-8"))
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertIn("manifest.json", names)
            self.assertIn("rights/license_pack.json", names)
            self.assertIn("metadata/metadata.json", names)
            self.assertIn("reports/acceptance_report.json", names)
            self.assertTrue(any(name.startswith("audio/master") for name in names))
            self.assertEqual(metadata["rights"]["platform_profile_id"], "internal_export")
            self.assertEqual(metadata["rights"]["export_profile"], "wav_master_preview_license")
            self.assertEqual(metadata["generation_route"]["style_strategy"]["mode"], "song")
            self.assertEqual(manifest["platform_profile_id"], "internal_export")


if __name__ == "__main__":
    unittest.main()
