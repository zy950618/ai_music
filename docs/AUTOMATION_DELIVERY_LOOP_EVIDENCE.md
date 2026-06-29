# Automation, Delivery, and Rework Evidence - 2026-06-29

This document records the current implementation evidence for the long-running production loop.

## Daily automation style distribution

- `DailyAutomationService.create_daily_batch()` now includes `style_distribution`.
- The report records:
  - `modes`
  - `genres`
  - `vocal_required`
- `route_summary` now includes `prompt_tags` from each version's `style_strategy`.
- Verification:
  - `tests.test_automation.AutomationTest.test_daily_batch_creates_ten_tasks_and_report`

## Daily report rework queue visibility

- Daily reports include the current `rework_queue` and `rework_budget`.
- Existing failed versions are visible after a daily batch, so operations can see what the next rework loop will process.
- Verification:
  - `tests.test_automation.AutomationTest.test_daily_report_includes_existing_rework_queue`

## Configurable delivery profile

- Web `POST /api/tasks/{task_id}/configure-rights` accepts optional JSON fields:
  - `platform_profile_id`
  - `export_profile`
  - `manual_approval_required`
  - `reference_sources`
- CLI `demo`, `create`, and `import-url` support:
  - `--platform-profile-id`
  - `--export-profile`
  - `--manual-approval-required`
- These values are written into:
  - `license_pack.json`
  - delivery `metadata/metadata.json`
  - delivery `manifest.json`
- Verification:
  - `tests.test_web_workbench.WebWorkbenchTest.test_create_list_and_configure_rights_api`
  - `tests.test_cli_generation_config.CliGenerationConfigTest.test_create_command_writes_configurable_delivery_metadata`

## Runtime workbench check

- Local workbench is running at `http://127.0.0.1:8788/`.
- PID file: `.cache/music-web-8788.pid`.
- Runtime check:
  - HTTP 200
  - `tasks` section present
  - `works` section present
  - `scores` section present
  - `delivery` section present

