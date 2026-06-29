# 长期 LOOP 运行补充验收

本补充只覆盖当前已落地的长期返工追踪能力，作为基础 Skills 和 Agent LOOP 的运行证据。

## 已实现验收点

- `python -m music_ai.cli schedule ...` 能作为每日自动化调度入口，到点后自动生成每日批次并处理返工。
- 调度状态写入 `scheduler/state.json`，同一自然日重复调用会跳过，避免重复刷批次。
- 每次调度检查都会写入 `scheduler/runs/*.json`，无论执行还是跳过都留下验收记录。
- `GET /api/rework-history` 能返回全部自动返工事件。
- 每条返工事件包含源任务、源版本、失败原因、负责 Agent、目标 Skill、新任务、根任务、返工深度、创建时间。
- 返工历史会补充新任务的作品 ID、选中版本、评分、授权状态和结果文件路径。
- 历史聚合会对同一条继承链中的重复事件去重，避免多代返工把同一个事件重复统计。
- 每日任务页会显示返工事件总数和最近 12 条返工历史。

## 运行验收命令

```powershell
python -m py_compile music_ai\repository.py music_ai\web.py
python -m py_compile music_ai\automation.py music_ai\cli.py
python -m unittest tests.test_automation.AutomationTest.test_scheduler_runs_due_daily_batch_once_per_day
python -m unittest tests.test_automation.AutomationTest.test_scheduler_skips_before_scheduled_time
python -m unittest tests.test_cli_generation_config.CliGenerationConfigTest.test_schedule_command_can_skip_before_scheduled_time
python -m unittest tests.test_automation.AutomationTest.test_rework_queue_generates_targeted_rework_for_clear_failures
python -m unittest tests.test_web_workbench.WebWorkbenchTest.test_daily_automation_api_creates_batch
```

## 长期运行意义

这个能力用于回答长期自动化生产中的三个问题：

- 哪个候选版本失败了。
- 哪个 Agent 和 Skill 接手返工。
- 返工后的新任务是否产生了更高质量、可授权、可交付的作品。
