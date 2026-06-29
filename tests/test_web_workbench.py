from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from music_ai.web import run_server


class WebWorkbenchTest(unittest.TestCase):
    request_timeout_sec = 120

    def test_create_list_and_configure_rights_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                payload = {
                    "title": "unit test creation",
                    "mode": "song",
                    "language": "zh",
                    "theme": "quality-focused synthetic song",
                    "mood": ["focused", "bright"],
                    "genre": ["pop"],
                    "audience": "internal makers",
                    "use_case": "web workbench validation",
                    "duration_sec": 8,
                    "bpm": 100,
                    "key": "C",
                    "vocal_required": True,
                    "forbidden": ["real singer imitation"],
                    "export_formats": ["wav"],
                }
                created = self.post_json(f"{base}/api/create", payload)
                self.assertEqual(len(created["versions"]), 3)

                tasks = self.get_json(f"{base}/api/tasks")
                self.assertEqual(len(tasks), 1)
                task_id = tasks[0]["task_id"]
                self.assertEqual(tasks[0]["rights_status"], "missing")

                configured = self.post_json(
                    f"{base}/api/tasks/{task_id}/configure-rights",
                    {"platform_profile_id": "creator_marketplace", "export_profile": "wav_stems_and_license"},
                )
                self.assertEqual(configured["rights_status"], "configured")
                selected = next(version for version in configured["versions"] if version["version_id"] == configured["selected_version_id"])
                self.assertTrue(any(item["kind"] == "master" and item["ready"] for item in selected["export_files"]))
                self.assertTrue(any(item["kind"] == "license_pack" and item["ready"] for item in selected["export_files"]))

                packaged = self.post_json(f"{base}/api/tasks/{task_id}/delivery-package", {})
                self.assertIn("delivery_package", packaged)
                with zipfile.ZipFile(Path(packaged["delivery_package"])) as archive:
                    metadata = json.loads(archive.read("metadata/metadata.json").decode("utf-8"))
                    manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                self.assertEqual(metadata["rights"]["platform_profile_id"], "creator_marketplace")
                self.assertEqual(metadata["rights"]["export_profile"], "wav_stems_and_license")
                self.assertEqual(metadata["generation_route"]["style_strategy"]["mode"], "song")
                self.assertEqual(manifest["platform_profile_id"], "creator_marketplace")
                tasks_after_package = self.get_json(f"{base}/api/tasks")
                packaged_version = next(
                    version
                    for version in tasks_after_package[0]["versions"]
                    if version["version_id"] == tasks_after_package[0]["selected_version_id"]
                )
                self.assertTrue(any(item["kind"] == "delivery_package" and item["ready"] for item in packaged_version["export_files"]))
            finally:
                server.shutdown()
                server.server_close()

    def test_daily_automation_api_creates_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                report = self.post_json(f"{base}/api/automation/daily", {})
                self.assertEqual(report["task_count"], 10)
                self.assertEqual(report["candidate_count"], 30)
                tasks = self.get_json(f"{base}/api/tasks")
                self.assertEqual(len(tasks), 10)
                history = self.get_json(f"{base}/api/rework-history")
                self.assertEqual(history["summary"]["total_events"], 0)
            finally:
                server.shutdown()
                server.server_close()

    def test_skills_api_exposes_foundation_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                skills = self.get_json(f"{base}/api/skills")
                self.assertEqual(len(skills["foundation_skills"]), 17)
                self.assertEqual(len(skills["agents"]), 26)
                self.assertIn("quality_acceptance", skills["core_gate_skill_ids"])
            finally:
                server.shutdown()
                server.server_close()

    def test_web_home_page_has_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                html = self.get_text(f"{base}/")
                self.assertIn('id="tasks"', html)
                self.assertIn('id="works"', html)
                self.assertIn('id="scores"', html)
                self.assertIn('id="delivery"', html)
                self.assertIn('id="opsPanel"', html)
                self.assertIn('data-tab="tasks"', html)
                self.assertIn("configureRights(", html)
                self.assertIn("createDeliveryPackage(", html)
                self.assertIn("manualRework(", html)
            finally:
                server.shutdown()
                server.server_close()

    def test_api_tasks_include_loop_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                payload = {
                    "title": "loop check task",
                    "mode": "song",
                    "language": "zh",
                    "theme": "loop-check prompt",
                    "mood": ["bright", "modern"],
                    "genre": ["pop"],
                    "audience": "quality reviewers",
                    "use_case": "loop acceptance",
                    "duration_sec": 10,
                    "bpm": 120,
                    "key": "G",
                    "vocal_required": True,
                    "forbidden": ["mimic real singer"],
                    "export_formats": ["wav"],
                }
                self.post_json(f"{base}/api/create", payload)
                tasks = self.get_json(f"{base}/api/tasks")
                self.assertEqual(len(tasks), 1)
                self.assertGreaterEqual(len(tasks[0]["versions"]), 1)

                for version in tasks[0]["versions"]:
                    self.assertIn("loop_state", version)
                    loop_state = version["loop_state"]
                    self.assertIn("decision", loop_state)
                    self.assertIn("next_agent", loop_state)
                    self.assertIn("next_action", loop_state)
                    self.assertIn("hard_gate_pass", loop_state)
                    self.assertIn("score_total", loop_state)
                    self.assertIn(
                        loop_state["decision"],
                        {"human_review_required", "auto_rework", "rights_blocked", "delivery_blocked", "rework_decide", "ready_for_packaging"},
                    )
                    self.assertIsInstance(loop_state["hard_gate_pass"], bool)
            finally:
                server.shutdown()
                server.server_close()

    def test_failed_version_loop_state_routes_to_owner_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                payload = {
                    "title": "short failed loop task",
                    "mode": "song",
                    "language": "zh",
                    "theme": "too short to pass structure",
                    "mood": ["bright"],
                    "genre": ["pop"],
                    "audience": "quality reviewers",
                    "use_case": "loop handoff validation",
                    "duration_sec": 8,
                    "bpm": 118,
                    "key": "C",
                    "vocal_required": True,
                    "forbidden": ["mimic real singer"],
                    "export_formats": ["wav"],
                }
                self.post_json(f"{base}/api/create", payload)
                tasks = self.get_json(f"{base}/api/tasks")
                failed_versions = [version for version in tasks[0]["versions"] if "STRUCTURE_TOO_SHORT" in version["failure_codes"]]
                self.assertGreaterEqual(len(failed_versions), 1)

                loop_state = failed_versions[0]["loop_state"]
                self.assertEqual(loop_state["decision"], "auto_rework")
                self.assertEqual(loop_state["next_agent"], "Brief Parser")
                self.assertEqual(loop_state["next_action"], "increase duration and clarify structure")
                self.assertEqual(loop_state["rework_targets"][0]["target_skill"], "creation_brief")
                self.assertEqual(loop_state["rework_targets"][0]["retry_budget"], 1)
            finally:
                server.shutdown()
                server.server_close()

    def test_manual_version_rework_api_creates_optimized_child_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                payload = {
                    "title": "manual optimize source",
                    "mode": "song",
                    "language": "zh",
                    "theme": "manual optimization source",
                    "mood": ["bright"],
                    "genre": ["pop"],
                    "audience": "quality reviewers",
                    "use_case": "manual optimization validation",
                    "duration_sec": 12,
                    "bpm": 100,
                    "key": "C",
                    "vocal_required": True,
                    "forbidden": ["mimic real singer"],
                    "export_formats": ["wav"],
                }
                self.post_json(f"{base}/api/create", payload)
                tasks = self.get_json(f"{base}/api/tasks")
                source = tasks[0]
                version_id = source["selected_version_id"]

                report = self.post_json(
                    f"{base}/api/tasks/{source['task_id']}/manual-rework",
                    {"version_id": version_id, "failure_code": "WEAK_HOOK", "notes": "make the hook more immediate"},
                )

                self.assertEqual(report["processed"], 1)
                self.assertEqual(len(report["created_reworks"]), 1)
                created = report["created_reworks"][0]
                self.assertEqual(created["parent_task_id"], source["task_id"])
                self.assertEqual(created["rework_reason"], "WEAK_HOOK")
                self.assertEqual(created["rework_depth"], 1)
                self.assertEqual(created["rework_history"][0]["manual"], True)
                self.assertEqual(created["rework_history"][0]["notes"], "make the hook more immediate")
                self.assertIn("hook_forward", created["request_data"]["mood"])
                self.assertGreaterEqual(created["request_data"]["bpm"], 108)

                tasks_after = self.get_json(f"{base}/api/tasks")
                self.assertEqual(len(tasks_after), 2)
            finally:
                server.shutdown()
                server.server_close()

    def test_ops_report_consistent_with_tasks_and_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = run_server("127.0.0.1", 0, temp_dir)
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                self.post_json(f"{base}/api/automation/daily", {})
                tasks = self.get_json(f"{base}/api/tasks")
                ops = self.get_json(f"{base}/api/ops")

                self.assertEqual(ops["task_count"], len(tasks))
                self.assertEqual(ops["version_count"], sum(len(task["versions"]) for task in tasks))
                self.assertEqual(ops["rights_status"]["missing"], sum(1 for task in tasks if task["rights_status"] == "missing"))
                self.assertEqual(ops["rights_status"]["configured"], sum(1 for task in tasks if task["rights_status"] == "configured"))
                self.assertEqual(
                    ops["rights_status"]["review_required"],
                    sum(1 for task in tasks if task["rights_status"] not in {"missing", "configured"}),
                )

                quality_fail = sum(
                    1
                    for task in tasks
                    for version in task["versions"]
                    if (version.get("score_total") or 0) < 80 or version.get("failure_codes")
                )
                version_count = sum(len(task["versions"]) for task in tasks)
                version_pass = max(0, version_count - quality_fail)
                expected_rate = round(version_pass / version_count * 100, 2) if version_count else 0.0
                self.assertEqual(ops["quality"]["version_fail"], quality_fail)
                self.assertEqual(ops["quality"]["version_pass"], version_pass)
                self.assertAlmostEqual(ops["quality"]["qa_pass_rate"], expected_rate, places=2)

                task_next_agents = [version.get("loop_state", {}).get("next_agent") for task in tasks for version in task["versions"]]
                for agent in [agent for agent in task_next_agents if agent]:
                    self.assertIn(agent, ops["quality"]["next_agent_counts"])
            finally:
                server.shutdown()
                server.server_close()

    def get_json(self, url: str):
        with urlopen(url, timeout=self.request_timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_text(self, url: str) -> str:
        with urlopen(url, timeout=self.request_timeout_sec) as response:
            return response.read().decode("utf-8")

    def post_json(self, url: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=self.request_timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
