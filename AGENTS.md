# AI 音乐制作项目执行规则

## 1. 项目目标

本项目要实现一个可长期自动运行的 AI 音乐制作系统。

最终结果必须具备：

- AI 音乐创作：歌词、旋律、和声、结构、编曲生成。
- 候选版本生成。
- 音乐下载。
- 剪辑：截取、淡入淡出、循环点处理。
- 基础音频处理。
- 质量评分。
- LOOP 定向返工。
- 作品库。
- 授权配置。
- 交付包导出。

本项目不是音乐分发平台，不做社区、推荐流、公开播放广场、点赞评论、粉丝关系和榜单。

## 2. 长期执行原则

- 不停留在计划层；文档完成后继续进入实现。
- 先实现 AI 音乐创作引擎，再实现网站工作台。
- 每一步必须有验收标准。
- 每一轮工作都应推进当前阶段的可运行能力。
- 默认持续执行到目标完成；只有遇到真实阻塞、危险操作、授权缺失或用户改变方向时才停下来说明。
- 不为了看起来完整而扩展无关功能。
- 不把授权缺失、版权风险、声线风险自动硬过。

## 3. 基础 Skills

项目基础 Skills 以 [docs/PROJECT_BASE_SKILLS.md](docs/PROJECT_BASE_SKILLS.md) 和 `music_ai/skills.py` 为准。

必须长期保留的基础 Skills：

- `creation_brief`
- `lyric_writing`
- `melody_composition`
- `harmony_composition`
- `arrangement`
- `generation_router`
- `candidate_generation`
- `audio_editing`
- `audio_processing`
- `download_export`
- `quality_acceptance`
- `loop_rework`
- `originality_guard`
- `rights_configuration`
- `delivery_package`
- `daily_automation`
- `ops_report`

核心门禁 Skills：

- `generation_router`
- `quality_acceptance`
- `loop_rework`
- `originality_guard`
- `rights_configuration`
- `download_export`

## 4. 当前阶段顺序

执行阶段以 [docs/PHASED_EXECUTION_PLAN.md](docs/PHASED_EXECUTION_PLAN.md) 为准。当前优先级：

1. `Phase 1`: AI 创作引擎 MVP。
2. `Phase 2`: 网站工作台 MVP。
3. `Phase 3`: Mock 自动制作流水线。
4. `Phase 4`: 音频/MIDI 分析基础。
5. `Phase 5`: 真实模型适配。
6. `Phase 6`: 质量返工闭环。
7. `Phase 7`: 授权交付闭环。
8. `Phase 8`: 运营优化。

## 5. 第一阶段验收

第一阶段不是网站页面验收，而是 AI 音乐创作引擎验收。

必须通过：

- 能创建音乐创作任务。
- 能生成结构化 brief。
- 能生成歌词或纯音乐结构。
- 能生成 3-5 个候选版本记录。
- 至少一个候选有可播放音频或下载 URL。
- 能下载生成音频。
- 能做基础剪辑：截取、淡入淡出、循环点、导出版。
- 能看到评分和返工建议。
- 能看到分项质量报告：旋律、朗朗上口、结构、受众、原创安全、交付准备等。
- 授权缺失时阻断正式交付，但不阻断内部试听下载。

## 6. LOOP 规则

- 低分不等于重生。
- 返工必须有 `failure_code`、证据、责任 Agent、保留字段、可变字段和重试预算。
- 同一版本自动返工最多 2 次。
- 同一任务自动返工最多 3 轮。
- 高原创风险、授权缺失、真实声线风险必须人工复核或阻断。
- 授权缺失不返工音乐，只进入 `DELIVERY_BLOCKED`。

## 7. 实现约束

- 优先使用项目已有文档中的数据模型和状态机。
- 先做可运行的最小闭环，再接真实模型。
- 真实模型统一经过 `Generation Router`。
- 外部下载音乐统一进入作品库、QA、授权和交付流程。
- 不直接把外部生成结果当成可交付成品。
- 不复制真实歌曲旋律、歌词或歌手声线。

## 8. 验证要求

每次实现后至少执行对应阶段的校验：

- 能运行的命令必须运行。
- 能生成的文件必须检查。
- 能打开的网站必须打开或提供本地地址。
- 如果测试、构建或运行失败，必须说明失败原因和下一步处理。

## 9. 参考文档

- [docs/PROJECT_DOCS_INDEX.md](docs/PROJECT_DOCS_INDEX.md)
- [docs/AI_CREATION_ENGINE_SPEC.md](docs/AI_CREATION_ENGINE_SPEC.md)
- [docs/OPEN_SOURCE_SKILLS_ABSORPTION.md](docs/OPEN_SOURCE_SKILLS_ABSORPTION.md)
- [docs/AGENT_WORK_BREAKDOWN.md](docs/AGENT_WORK_BREAKDOWN.md)
- [docs/LOOP_STATE_MACHINE.md](docs/LOOP_STATE_MACHINE.md)
- [docs/QUALITY_ACCEPTANCE_SYSTEM.md](docs/QUALITY_ACCEPTANCE_SYSTEM.md)
- [docs/PHASED_EXECUTION_PLAN.md](docs/PHASED_EXECUTION_PLAN.md)
