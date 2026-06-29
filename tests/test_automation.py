from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from music_ai.automation import DailyAutomationScheduler, DailyAutomationService, DailyScheduleConfig
from music_ai.engine import CreationEngine
from music_ai.generation import GenerationProviderRegistry, GenerationProviderSpec
from music_ai.models import MusicCreationRequest
from music_ai.repository import ResultRepository


class AutomationTest(unittest.TestCase):
    def test_daily_batch_creates_ten_tasks_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = GenerationProviderRegistry(
                (
                    GenerationProviderSpec(
                        id="daily_mock",
                        provider="mock",
                        model_name="daily-mock-model",
                        model_version="1",
                        priority=1,
                    ),
                )
            )
            service = DailyAutomationService(temp_dir, provider_registry=registry)
            report = service.create_daily_batch(target_count=10, candidate_count=3)

            self.assertEqual(report["task_count"], 10)
            self.assertEqual(report["candidate_count"], 30)
            self.assertEqual(report["tasks"][0]["versions"][0]["model_name"], "daily-mock-model")
            self.assertEqual(report["provider_usage"], {"daily_mock": 30})
            self.assertEqual(report["route_summary"][0]["provider_id"], "daily_mock")
            self.assertEqual(report["route_summary"][0]["selection_reason"], "priority")
            self.assertEqual(report["style_distribution"]["modes"]["short_video"], 3)
            self.assertEqual(report["style_distribution"]["modes"]["film"], 2)
            self.assertEqual(report["style_distribution"]["vocal_required"], {"true": 3, "false": 7})
            self.assertIn("prompt_tags", report["route_summary"][0])
            self.assertGreaterEqual(report["average_score"], 80)
            report_files = list((Path(temp_dir) / "batches").glob("batch_*/daily_report.json"))
            self.assertEqual(len(report_files), 1)
            task_files = list(Path(temp_dir).glob("task_*/result.json"))
            self.assertEqual(len(task_files), 10)

    def test_daily_report_includes_existing_rework_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            request = MusicCreationRequest(
                title="daily queue seed",
                mode="short_video",
                language="zh",
                theme="daily report should see this failure",
                mood=["bright"],
                genre=["pop"],
                audience="internal",
                use_case="daily rework queue validation",
                duration_sec=8,
                bpm=120,
                key="C",
                vocal_required=True,
                forbidden=["real singer imitation"],
            )
            source = engine.create(request, candidate_count=3)

            service = DailyAutomationService(temp_dir)
            report = service.create_daily_batch(target_count=10, candidate_count=3)

            queued = [item for item in report["rework_queue"] if item["task_id"] == source.task_id]
            self.assertGreaterEqual(len(queued), 1)
            self.assertEqual(queued[0]["failure_code"], "STRUCTURE_TOO_SHORT")
            self.assertEqual(report["rework_budget"]["queued"], len(report["rework_queue"]))

    def test_rework_queue_generates_targeted_rework_for_clear_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            request = MusicCreationRequest(
                title="太短的测试曲",
                mode="short_video",
                language="zh",
                theme="需要返工的短片段",
                mood=["bright"],
                genre=["pop"],
                audience="internal",
                use_case="rework validation",
                duration_sec=8,
                bpm=120,
                key="C",
                vocal_required=True,
                forbidden=["real singer imitation"],
            )
            source = engine.create(request, candidate_count=3)
            self.assertTrue(any(version.failure_codes for version in source.versions))

            service = DailyAutomationService(temp_dir)
            queue = service.build_rework_queue()
            self.assertTrue(any(item.failure_code == "STRUCTURE_TOO_SHORT" for item in queue))

            report = service.run_rework_queue(limit=1)
            self.assertEqual(report["processed"], 1)
            self.assertEqual(len(report["created_reworks"]), 1)
            created = report["created_reworks"][0]
            self.assertEqual(created["parent_task_id"], source.task_id)
            self.assertEqual(created["rework_reason"], "STRUCTURE_TOO_SHORT")
            self.assertEqual(created["rework_depth"], 1)
            self.assertEqual(created["rework_root_task_id"], source.task_id)
            self.assertEqual(created["rework_history"][0]["source_task_id"], source.task_id)
            self.assertGreaterEqual(created["request_data"]["duration_sec"], 12)

            history = ResultRepository(temp_dir).rework_history()
            self.assertEqual(history["summary"]["total_events"], 1)
            self.assertEqual(history["events"][0]["source_task_id"], source.task_id)
            self.assertEqual(history["events"][0]["created_task_id"], created["task_id"])
            self.assertEqual(history["events"][0]["created_work_id"], created["work_id"])
            self.assertEqual(history["summary"]["by_failure_code"], {"STRUCTURE_TOO_SHORT": 1})

    def test_rework_queue_stops_after_two_attempts_for_same_source_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            request = MusicCreationRequest(
                title="short source",
                mode="short_video",
                language="zh",
                theme="short source needs rework",
                mood=["bright"],
                genre=["pop"],
                audience="internal",
                use_case="rework budget validation",
                duration_sec=8,
                bpm=120,
                key="C",
                vocal_required=True,
                forbidden=["real singer imitation"],
            )
            engine.create(request, candidate_count=3)
            service = DailyAutomationService(temp_dir)

            first = service.run_rework_queue(limit=1)
            second = service.run_rework_queue(limit=1)
            third = service.run_rework_queue(limit=1)

            self.assertEqual(len(first["created_reworks"]), 1)
            self.assertEqual(len(second["created_reworks"]), 1)
            self.assertEqual(len(third["created_reworks"]), 0)
            self.assertEqual(third["skipped"][0]["reason"], "version_rework_budget_exhausted")

    def test_rework_queue_blocks_when_task_depth_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            request = MusicCreationRequest(
                title="deep source",
                mode="short_video",
                language="zh",
                theme="deep source needs rework",
                mood=["bright"],
                genre=["pop"],
                audience="internal",
                use_case="rework depth validation",
                duration_sec=8,
                bpm=120,
                key="C",
                vocal_required=True,
                forbidden=["real singer imitation"],
            )
            source = engine.create(request, candidate_count=3)
            source.rework_depth = 3
            source.rework_root_task_id = "root_task"
            engine._write_result(Path(temp_dir) / source.task_id, source)

            service = DailyAutomationService(temp_dir)
            report = service.run_rework_queue(limit=1)

            self.assertEqual(len(report["created_reworks"]), 0)
            self.assertEqual(report["skipped"][0]["reason"], "task_rework_depth_exhausted")

    def test_rework_queue_stops_after_three_reworks_for_same_root_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = CreationEngine(temp_dir)
            request = MusicCreationRequest(
                title="root budget source",
                mode="short_video",
                language="zh",
                theme="root budget source needs rework",
                mood=["bright"],
                genre=["pop"],
                audience="internal",
                use_case="root rework budget validation",
                duration_sec=8,
                bpm=120,
                key="C",
                vocal_required=True,
                forbidden=["real singer imitation"],
            )
            engine.create(request, candidate_count=3)
            service = DailyAutomationService(temp_dir)

            first = service.run_rework_queue(limit=10)
            second = service.run_rework_queue(limit=1)

            self.assertEqual(len(first["created_reworks"]), 3)
            self.assertEqual(len(second["created_reworks"]), 0)
            self.assertEqual(second["skipped"][0]["reason"], "task_rework_budget_exhausted")

    def test_scheduler_runs_due_daily_batch_once_per_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scheduler = DailyAutomationScheduler(
                temp_dir,
                DailyScheduleConfig(target_count=10, candidate_count=3, rework_limit=0, run_hour=1, run_minute=30),
            )
            first = scheduler.run_due(datetime(2026, 6, 26, 1, 30))
            second = scheduler.run_due(datetime(2026, 6, 26, 12, 0))

            self.assertTrue(first["due"])
            self.assertEqual(first["daily_report"]["task_count"], 10)
            self.assertEqual(first["rework_report"]["processed"], 0)
            self.assertFalse(second["due"])
            self.assertEqual(second["skipped_reason"], "already_ran_today")
            state = json.loads((Path(temp_dir) / "scheduler" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["last_run_date"], "2026-06-26")
            self.assertEqual(len(list(Path(temp_dir).glob("task_*/result.json"))), 10)
            self.assertEqual(len(list((Path(temp_dir) / "scheduler" / "runs").glob("*.json"))), 2)

    def test_scheduler_skips_before_scheduled_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scheduler = DailyAutomationScheduler(
                temp_dir,
                DailyScheduleConfig(target_count=10, candidate_count=3, rework_limit=0, run_hour=9, run_minute=0),
            )
            report = scheduler.run_due(datetime(2026, 6, 26, 8, 59))

            self.assertFalse(report["due"])
            self.assertEqual(report["skipped_reason"], "before_scheduled_time")
            self.assertFalse((Path(temp_dir) / "scheduler" / "state.json").exists())
            self.assertEqual(len(list(Path(temp_dir).glob("task_*/result.json"))), 0)


if __name__ == "__main__":
    unittest.main()
