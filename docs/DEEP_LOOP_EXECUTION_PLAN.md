# AI音乐项目：深度推进执行计划（LOOP 第2轮）

## 1. 基础约束

- 目标：把“AI音乐创作平台”继续推进为“可生产AI音乐制作系统”，保留可配置授权，不变更为纯发布平台。
- 依据：
  - `docs/PROJECT_BASE_SKILLS.md`
  - `docs/LOOP_STATE_MACHINE.md`
  - `docs/QUALITY_ACCEPTANCE_SYSTEM.md`
  - `docs/AGENT_WORK_BREAKDOWN.md`
- 风险优先级：先保证闭环可验证（页面访问、任务链路、版本循环、rights+delivery、ops 一致性），再扩展算法深度。

## 2. 本轮执行状态（已完成）

1. 主页验收闭环  
   - 访问 `GET /`，必须能看到：
     - `tasks`（任务区）
     - `works`（作品库）
     - `scores`（评分中心）
     - `delivery`（发布中心）
     - `opsPanel`（运营/状态面板）
   - 结果：`tests/test_web_workbench.py::test_web_home_page_has_required_sections` 已覆盖。

2. LOOP状态回写可验证  
   - `/api/tasks` 返回每个版本 `loop_state`，包含：
     - `decision`
     - `next_agent`
     - `next_action`
     - `hard_gate_pass`
     - `score_total`
   - 结果：`tests/test_web_workbench.py::test_api_tasks_include_loop_state` 已覆盖。

3. API 一致性验收  
   - `/api/ops` 的聚合字段与 `/api/tasks` 计算结果一致：
     - `task_count`
     - `version_count`
     - `rights_status.{missing,configured,review_required}`
     - `quality.version_pass/fail`、`qa_pass_rate`
     - `next_agent_counts` 与版本循环目标一致
   - 结果：`tests/test_web_workbench.py::test_ops_report_consistent_with_tasks_and_versions` 已覆盖。

4. 核心链路回归
   - 任务创建 → 配置版权 → 生成发布包，链路保持可用。
   - 结果：`tests/test_web_workbench.py::test_create_list_and_configure_rights_api`。

## 3. 下一轮任务（持续Loop）

### Step A：创作与重构质量“可评分”升级
- 对每个作品版本建立“朗朗上口/旋律/受众匹配”分量化来源映射到 `score_breakdown`。
- 输出：质量维度可直接被 `quality_acceptance` 与 `ops` 报表读取。
- 验收：
  - `/api/tasks` 中版本 `score_breakdown` 包含 `catchy`, `melody`, `audience_fit`。
  - 低分触发 `loop_state.decision` 到重工流程（`rework_decide`）。

### Step B：受众与风格策略增强
- 建立风格路由规则，覆盖歌单场景：原唱改编/学习作词、古典、节点、BGM、短视频、游戏、影视等。
- 输出：`CreationEngine` 组合 prompt 时可按 audience/style 强化模型参数选择。
- 验收：
  - 同一 brief 在不同 style 下生成版本数量稳定（含 10+ 每日任务场景）。
  - `skills` 与 `agent` 的分工不发生越界修改。

### Step C：发布与授权闭环落地
- 完成“平台兼容发布包”配置化：
  - `platform_profile_id` 与授权条目从任务元数据注入 delivery。
  - 发布中心展示 `license_pack` 与 `delivery_package` 完整可下载。
- 验收：
  - `/api/tasks/{id}/delivery-package` 返回 `delivery_package` 成功后，发布中心可直接下载文件。

## 4. 长期运行规则（不要停）

- 每次变更都必须满足：
  1. 先更新或新增测试；
  2. `python -m unittest` 覆盖到相关路径；
  3. 通过验证后再进入下一步。
- 每日例行：
  - `POST /api/automation/daily`（10 个任务）
  - `GET /api/ops` + `GET /api/tasks` 做一致性检查
  - 对质量低于阈值版本触发重工队列。

## 5. 验收清单（本阶段）

- [ ] 网站入口 `/` 可打开，包含任务/作品/评分/发布四块。
- [ ] `GET /api/tasks` 带 `loop_state` 且字段完整。
- [ ] `GET /api/ops` 与 `GET /api/tasks` 一致性通过。
- [ ] `create -> configure-rights -> delivery-package` 端到端可运行。
- [ ] 回归测试通过（至少包含 web + automation + cli schedule 关键路径）。

