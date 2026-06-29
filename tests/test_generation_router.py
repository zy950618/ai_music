from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from music_ai.generation import GenerationJob, GenerationProviderRegistry, GenerationProviderSpec, GenerationRouteConfig, GenerationRouter
from music_ai.models import MusicCreationRequest


class GenerationRouterTest(unittest.TestCase):
    def make_request(self, mode: str = "song", vocal_required: bool = True, duration_sec: int = 30) -> MusicCreationRequest:
        return MusicCreationRequest(
            title="router test",
            mode=mode,  # type: ignore[arg-type]
            language="zh",
            theme="router validation",
            mood=["clear"],
            genre=["pop"],
            audience="internal",
            use_case="generation routing validation",
            duration_sec=duration_sec,
            vocal_required=vocal_required,
        )

    def test_mock_router_generates_local_wav_and_route_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "mock.wav"
            router = GenerationRouter(GenerationRouteConfig(provider="mock"))

            artifact = router.generate(
                GenerationJob(
                    version_id="v1",
                    prompt="make a hook",
                    target_path=target,
                    duration_sec=1,
                    bpm=100,
                    key_index=0,
                )
            )

            self.assertEqual(artifact.audio_source, "mock_file")
            self.assertTrue(target.exists())
            self.assertEqual(artifact.route_log["provider"], "mock")

    def test_local_command_router_runs_command_and_records_route_log(self) -> None:
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
            target = Path(temp_dir) / "local.wav"
            router = GenerationRouter(
                GenerationRouteConfig(
                    provider="local_command",
                    model_name="local-test-model",
                    model_version="test-1",
                    command=(sys.executable, str(script), "{output_path}", "{duration_sec}", "{bpm}"),
                    timeout_sec=30,
                )
            )

            artifact = router.generate(
                GenerationJob(
                    version_id="v1",
                    prompt="make a hook",
                    target_path=target,
                    duration_sec=1,
                    bpm=100,
                    key_index=0,
                )
            )

            self.assertEqual(artifact.audio_source, "local_command_file")
            self.assertEqual(artifact.model_name, "local-test-model")
            self.assertTrue(target.exists())
            self.assertEqual(artifact.route_log["provider"], "local_command")

    def test_provider_registry_selects_highest_priority_capable_provider(self) -> None:
        registry = GenerationProviderRegistry(
            (
                GenerationProviderSpec(
                    id="instrumental_only",
                    provider="mock",
                    model_name="instrumental",
                    model_version="1",
                    priority=1,
                    supported_modes=("bgm",),
                    supports_vocals=False,
                    supports_instrumental=True,
                ),
                GenerationProviderSpec(
                    id="fallback",
                    provider="mock",
                    model_name="fallback",
                    model_version="1",
                    priority=100,
                ),
            )
        )

        bgm_provider = registry.select(self.make_request(mode="bgm", vocal_required=False))
        song_provider = registry.select(self.make_request(mode="song", vocal_required=True))

        self.assertEqual(bgm_provider.id, "instrumental_only")
        self.assertEqual(song_provider.id, "fallback")

        selected, trace = registry.select_with_trace(self.make_request(mode="bgm", vocal_required=False))
        self.assertEqual(selected.id, "instrumental_only")
        self.assertEqual(trace["selection_reason"], "priority")
        self.assertEqual(trace["selected_provider_id"], "instrumental_only")
        self.assertTrue(any(item["id"] == "fallback" and item["can_handle"] for item in trace["evaluations"]))

    def test_provider_registry_rejects_preferred_provider_that_cannot_handle_request(self) -> None:
        registry = GenerationProviderRegistry(
            (
                GenerationProviderSpec(
                    id="short_only",
                    provider="mock",
                    model_name="short",
                    model_version="1",
                    max_duration_sec=10,
                ),
            )
        )

        with self.assertRaises(ValueError):
            registry.select(self.make_request(duration_sec=30), preferred_provider_id="short_only")


if __name__ == "__main__":
    unittest.main()
