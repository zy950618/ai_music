# 分阶段实现与校验计划

## 1. 总路线

本项目按“先创作引擎，再网站承载，再自动化，再优化质量”的顺序推进。

第一步不是做音乐分发平台，也不只是做网站页面。第一步必须先实现 AI 音乐创作引擎 MVP：能创建创作任务、生成候选版本、接收或生成可下载音频、做基础剪辑处理、导出文件记录，并进入 QA 和返工链路。

不建议第一步直接训练或安装所有 AI 音乐模型。首要目标是先把创作链路和模型适配接口跑通：没有真实模型时用 `mock_file` 或 `external_download_url`，后续再替换为 ACE-Step、YuE、DiffRhythm 等真实适配器。

## 2. 阶段总览

| 阶段 | 目标 | 关键产物 | 通过条件 |
|---|---|---|---|
| Phase 0 | 文档和架构冻结 | Skills、Agent、LOOP、验收、数据模型 | 文档完整，职责和验收清楚 |
| Phase 1 | AI 创作引擎 MVP | 创作任务、brief、候选版本、音频下载、剪辑、导出记录 | 能生成或导入可下载音乐，并保存版本 |
| Phase 2 | 网站工作台 MVP | 每日任务、作品库、评分中心、交付与授权中心 | 网站能打开，四个工作区可见 |
| Phase 3 | Mock 自动制作流水线 | 每日 10-20 条任务、3-5 候选、状态流转 | 不接真实模型也能跑通 LOOP |
| Phase 4 | 音频/MIDI 分析基础 | 分轨、转 MIDI、BPM/key/结构/响度分析 | QA 报告可生成 |
| Phase 5 | 真实模型适配 | ACE-Step / YuE / DiffRhythm 适配器 | 异步生成候选并入库 |
| Phase 6 | 质量返工闭环 | 定向返工、失败原因、产能闸门 | 低分版本能按原因返工 |
| Phase 7 | 授权交付闭环 | 授权配置、交付包、导出规格 | 授权完整才可交付 |
| Phase 8 | 运营优化 | 日报、通过率、失败原因、模型成本 | 能自动调整次日任务权重 |

## 3. Phase 0: 文档和架构冻结

实施：

- 完成开源 Skills 吸收表。
- 完成项目基础 Skills。
- 完成多 Agent 分工。
- 完成 LOOP 状态机。
- 完成质量/受众/授权验收体系。
- 完成数据模型草案。

校验：

- 每个外部项目有吸收方式和风险边界。
- 每个 Agent 有输入、输出、禁止事项、交接验收。
- 每个失败原因能映射到责任 Agent。
- 每个验收项有通过线或阻断条件。

对应文档：

- [OPEN_SOURCE_SKILLS_ABSORPTION.md](OPEN_SOURCE_SKILLS_ABSORPTION.md)
- [PROJECT_BASE_SKILLS.md](PROJECT_BASE_SKILLS.md)
- [AGENT_WORK_BREAKDOWN.md](AGENT_WORK_BREAKDOWN.md)
- [LOOP_STATE_MACHINE.md](LOOP_STATE_MACHINE.md)
- [QUALITY_ACCEPTANCE_SYSTEM.md](QUALITY_ACCEPTANCE_SYSTEM.md)
- [AI_CREATION_ENGINE_SPEC.md](AI_CREATION_ENGINE_SPEC.md)

## 4. Phase 1: AI 创作引擎 MVP

实施：

- 建立音乐创作任务数据模型。
- 建立 `Generation Router`，统一管理 `mock_file`、`external_download_url`、`local_model_adapter`。
- 建立歌词型歌曲和纯音乐/BGM 两条创作链路。
- 生成 3-5 个候选版本记录。
- 支持外部 AI 音乐下载 URL 导入。
- 支持生成音频文件或占位音频文件。
- 支持基础剪辑记录：trim、fade in、fade out、crossfade、loop、render variant。
- 支持导出记录：preview、master、short cut、loop、lyrics、metadata。
- 每个版本进入 QA 和返工链路。

校验：

- 能创建一条音乐创作任务。
- 能生成结构化 brief。
- 能生成歌词或纯音乐结构。
- 能生成 3-5 个候选版本记录。
- 至少一个候选有本地音频路径或外部下载 URL。
- 能下载生成音乐。
- 能生成 15s、30s、full 三种导出记录。
- 能保存评分、失败原因和返工 brief。
- 授权缺失时阻断正式交付，但不阻断内部试听下载。

对应文档：

- [AI_CREATION_ENGINE_SPEC.md](AI_CREATION_ENGINE_SPEC.md)

## 5. Phase 2: 网站工作台 MVP

实施：

- 建立前端应用。
- 建立统一布局和导航。
- 建立 mock 数据。
- 实现四个工作区。

工作区：

- 每日任务。
- 作品库。
- 评分中心。
- 交付与授权中心。

校验：

- 网站能打开。
- 页面不白屏。
- 四个入口可见。
- 点击入口不会 404。
- 页面内容围绕音乐制作，不是音乐分发平台。
- 交付与授权中心表达导出包、授权配置、AI 声明和可选连接配置。

建议命令：

```powershell
npm install
npm run dev
npm run build
```

如配置了 lint、typecheck、test：

```powershell
npm run lint
npm run typecheck
npm test
```

## 6. Phase 3: Mock 自动制作流水线

实施：

- 每天自动生成 10-20 条 mock 制作任务。
- 每条任务生成 3-5 个 mock 候选版本。
- 候选版本带 prompt、seed、模型名、状态、评分。
- 状态按 `LOOP_STATE_MACHINE.md` 流转。
- 低分版本生成返工单。

校验：

- 每日任务页面能看到至少 10 条任务。
- 每个任务能看到版本数量。
- 每个版本能看到状态和评分。
- 评分中心能看到失败原因。
- 返工单能指向责任 Agent。
- 授权缺失不触发音乐返工，而进入交付阻断。

## 7. Phase 4: 音频/MIDI 分析基础

实施：

- 接入或预留 `librosa` 风格分析。
- 接入或预留 `Basic Pitch` 音频转 MIDI。
- 接入或预留 `Demucs` 分轨。
- 接入或预留 `pretty_midi` / `music21` MIDI 分析。

第一版可以先做适配器接口和 mock 报告：

```ts
type AudioAnalysisReport = {
  duration_sec: number;
  bpm?: number;
  key?: string;
  loudness_lufs?: number;
  true_peak_db?: number;
  clipping_detected: boolean;
  silence_ranges: Array<[number, number]>;
  loop_seam_score?: number;
  structure_markers: string[];
};
```

校验：

- 上传或 mock 音频能生成 QA 报告。
- 报告能驱动 `AUDIO_QA_PASS` 或 `AUDIO_QA_FAIL`。
- 报告字段能在评分中心展示。

## 8. Phase 5: 真实模型适配

实施：

- 建立 `Generation Router`。
- 为 ACE-Step、YuE、DiffRhythm 预留适配器。
- 生成任务必须异步执行。
- 生成结果必须保存模型版本、prompt、seed、日志。

校验：

- 页面不直接调用模型。
- 模型失败不会丢任务。
- 成功结果进入作品库。
- 所有生成结果先进入 QA，不直接进入交付。

模型接入优先级：

1. `ACE-Step`：整歌、本地、编辑能力试点。
2. `DiffRhythm`：快速 demo、纯音乐和短视频 BGM。
3. `YuE`：歌词成歌和完整人声歌曲。

## 9. Phase 6: 质量返工闭环

实施：

- 实现 `failure_code`。
- 实现返工次数限制。
- 实现 `preserve_fields` 和 `mutable_fields`。
- 实现定向返工 brief。
- 实现人工复核状态。

校验：

- `HOOK_WEAK` 回流旋律/歌词，不回流母带。
- `AUDIO_CLIPPING` 回流混音/母带，不重写歌曲。
- `ORIGINALITY_HIGH` 进入人工复核或废弃，不自动通过。
- `METADATA_MISSING` 只补元数据，不重生音乐。
- 同一版本自动返工不超过 2 次。
- 同一任务自动返工不超过 3 轮。

## 10. Phase 7: 授权交付闭环

实施：

- 建立授权配置表。
- 建立交付包结构。
- 建立导出规格。
- 建立 AI 声明字段。
- 建立可选平台连接配置，但不做音乐平台。

交付包内容：

- Master WAV。
- MP3/AAC 预览。
- Instrumental。
- Vocal acapella，如有。
- Stems。
- Lyrics。
- MIDI 或工程文件，如有。
- Metadata。
- License pack。
- Acceptance report。

校验：

- 授权主体缺失时不能交付。
- 使用范围缺失时不能交付。
- AI 声明缺失时不能交付。
- 高原创风险不能交付。
- 交付包文件不完整不能交付。

## 11. Phase 8: 运营优化

实施：

- 每日自动日报。
- 通过率统计。
- 失败原因统计。
- 模型成本统计。
- 返工成功率统计。
- 明日任务权重建议。

校验：

- 能看到今天创建任务数。
- 能看到候选数。
- 能看到入库数。
- 能看到废弃数。
- 能看到人工待审数。
- 能看到 Top 失败原因。
- 能看到明日建议减少/增加的风格。

## 12. 第一阶段必须完成的验收清单

- [ ] 能创建音乐创作任务。
- [ ] 能生成结构化 brief。
- [ ] 能生成歌词或纯音乐结构。
- [ ] 能生成 3-5 个候选版本记录。
- [ ] 至少一个候选有可播放音频或下载 URL。
- [ ] 能下载生成音频。
- [ ] 能生成 15s、30s、full 三种导出记录。
- [ ] 能执行 trim、fade、loop、render variant 的剪辑记录。
- [ ] 能看到评分和返工建议。
- [ ] 授权缺失时阻断正式交付，但不阻断内部试听下载。

## 13. 网站工作台验收清单

- [ ] 网站能打开。
- [ ] 能看到每日任务。
- [ ] 能看到作品库。
- [ ] 能看到评分中心。
- [ ] 能看到交付与授权中心。
- [ ] 每日任务至少展示 10 条音乐制作任务样例。
- [ ] 作品库展示版本、阶段、评分和授权状态。
- [ ] 评分中心展示硬门槛、分项评分、失败原因和返工建议。
- [ ] 交付与授权中心展示授权主体、使用范围、AI 声明、导出规格和阻断原因。
- [ ] 页面没有音乐社区、推荐流、歌单平台、点赞评论、粉丝关系。
- [ ] 构建命令通过。

## 14. 不做事项

第一阶段不做：

- 音乐分发平台。
- 社区。
- 用户主页。
- 推荐流。
- 点赞评论。
- 榜单。
- 粉丝关系。
- 自动商业发行。
- 未授权歌手克隆。
- 参考歌曲复刻。

## 15. 成功口径

这个项目的第一阶段成功，就是证明系统能创作和处理音乐，而不是只有页面：

- 能创建音乐创作任务。
- 能生成或导入可下载音乐。
- 能做基础剪辑和导出。
- 能保存候选版本。
- 能评分和返工。
- 能阻断未授权正式交付。
- 后续网站只是把这些能力可视化、可操作化。
