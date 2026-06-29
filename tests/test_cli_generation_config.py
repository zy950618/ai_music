from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from music_ai.cli import build_engine, build_generation_router, create, schedule


class CliGenerationConfigTest(unittest.TestCase):
    def test_build_generation_router_reads_local_command_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "command.json"
            config_path.write_text(json.dumps(["python", "generate.py", "{output_path}"]), encoding="utf-8")
            args = argparse.Namespace(
                generation_provider="local_command",
                local_command_json=f"@{config_path}",
                model_name="file-config-model",
                model_version="1",
                generation_timeout=30,
            )

            router = build_generation_router(args)

            self.assertEqual(router.config.provider, "local_command")
            self.assertEqual(router.config.command, ("python", "generate.py", "{output_path}"))
            self.assertEqual(router.config.model_name, "file-config-model")

    def test_build_engine_reads_provider_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "providers.json"
            provider_path.write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "id": "mock_a",
                                "provider": "mock",
                                "model_name": "mock-a",
                                "model_version": "1",
                                "enabled": True,
                                "priority": 1,
                                "supported_modes": ["song"],
                                "supports_vocals": True,
                                "supports_instrumental": True,
                                "max_duration_sec": 60,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                provider_config=str(provider_path),
                preferred_provider=None,
                generation_provider=None,
                local_command_json="[]",
                model_name=None,
                model_version=None,
                generation_timeout=120,
            )

            engine = build_engine(temp_dir, args)

            self.assertIsNotNone(engine.provider_registry)
            self.assertEqual(engine.provider_registry.providers[0].id, "mock_a")

    def test_schedule_command_can_skip_before_scheduled_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                output=temp_dir,
                count=10,
                candidates=3,
                rework_limit=0,
                run_hour=9,
                run_minute=0,
                now="2026-06-26T08:00:00",
                provider_config=None,
                preferred_provider=None,
            )
            buffer = io.StringIO()

            with redirect_stdout(buffer):
                schedule(args)

            report = json.loads(buffer.getvalue())
            self.assertFalse(report["due"])
            self.assertEqual(report["skipped_reason"], "before_scheduled_time")
            self.assertEqual(len(list(Path(temp_dir).glob("task_*/result.json"))), 0)

    def test_create_command_writes_configurable_delivery_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "title": "cli delivery check",
                        "mode": "song",
                        "language": "zh",
                        "theme": "cli delivery metadata",
                        "mood": ["focused", "bright"],
                        "genre": ["pop"],
                        "audience": "internal makers",
                        "use_case": "cli delivery validation",
                        "duration_sec": 10,
                        "bpm": 110,
                        "key": "C",
                        "vocal_required": True,
                        "forbidden": ["real singer imitation"],
                        "export_formats": ["wav"],
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                request=str(request_path),
                output=temp_dir,
                candidates=3,
                configure_rights=True,
                package=True,
                platform_profile_id="creator_marketplace",
                export_profile="wav_stems_and_license",
                manual_approval_required=True,
                provider_config=None,
                preferred_provider=None,
                generation_provider=None,
                local_command_json="[]",
                model_name=None,
                model_version=None,
                generation_timeout=120,
            )
            buffer = io.StringIO()

            with redirect_stdout(buffer):
                create(args)

            summary = json.loads(buffer.getvalue())
            package_paths = [Path(path) for path in summary["downloadable_files"] if str(path).endswith("_delivery.zip")]
            self.assertEqual(len(package_paths), 1)
            with zipfile.ZipFile(package_paths[0]) as archive:
                metadata = json.loads(archive.read("metadata/metadata.json").decode("utf-8"))
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(metadata["rights"]["platform_profile_id"], "creator_marketplace")
            self.assertEqual(metadata["rights"]["export_profile"], "wav_stems_and_license")
            self.assertTrue(metadata["rights"]["manual_approval_required"])
            self.assertEqual(manifest["platform_profile_id"], "creator_marketplace")


if __name__ == "__main__":
    unittest.main()
