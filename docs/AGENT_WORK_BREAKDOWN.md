# 多 Agent 细颗粒分工

## 1. 分工原则

本项目的 Agent 分工以音乐制作流水线为边界，不以平台运营为边界。

统一原则：

- `Brief` 是最高创作约束，任何 Agent 不能私自改变用户需求。
- 返工只回流到责任环节，不全链路盲目重做。
- 混音和母带不承担作词、作曲、编曲返工职责。
- 授权配置和原创性检查是硬门禁，不是可选建议。
- 每个 Agent 输出必须可追踪、可复核、可交接。

## 2. 统一交接格式

每个 Agent 输出都必须包含：

```ts
type AgentHandoff = {
  project_id: string;
  task_id: string;
  work_id?: string;
  version_id?: string;
  agent_name: string;
  input_refs: string[];
  decisions: string[];
  risk_flags: string[];
  status: "pass" | "needs_rework" | "blocked";
  output_files: string[];
  output_data: Record<string, unknown>;
  next_agent: string;
  acceptance_notes: string[];
  uncertainty_notes: string[];
};
```

禁止：

- 没有证据就输出通过。
- 把“不确定”写成“已解决”。
- 覆盖其他 Agent 的历史版本。
- 直接把未授权素材送入交付包。

## 3. Agent 总表

| # | Agent | 职责 | 输入 | 输出 | 禁止事项 | 交接验收 |
|---:|---|---|---|---|---|---|
| 1 | `Daily Production Planner` | 生成每日生产计划、优先级、配额、依赖关系 | 项目池、库存缺口、算力预算、昨日日报 | 今日 10-20 条制作任务 | 不得压缩 QA；不得改变用户需求 | 每个任务有目标、风格、用途、受众、验收标准 |
| 2 | `Brief Parser` | 把用户需求转成结构化 brief | 用户描述、参考材料、授权限制 | 风格、BPM、key、结构、时长、受众、硬门槛 | 不得补造硬需求 | 作词、作曲、编曲、生成都可直接使用 |
| 3 | `Style Researcher` | 研究目标风格的节奏、和声、音色、结构 | brief、风格标签、参考画像 | 风格报告和禁用方向 | 不得输出可抄袭旋律 | 报告能转成创作约束 |
| 4 | `Audience Profiler` | 定义受众、场景、情绪需求和接受边界 | brief、用途、地区语言、历史评分 | 受众画像 | 不得编造平台数据 | 能指导歌词、hook、时长、音色强度 |
| 5 | `Creative Director` | 统一主题、叙事角度、情绪线 | brief、风格报告、受众画像 | 创意方向、关键词、禁用方向 | 不得越过 brief 创造新产品方向 | 词曲编曲都对齐同一创意 |
| 6 | `Lyric Writer` | 生成歌词、标题、hook 文案 | 创意方向、语言、结构、押韵要求 | 歌词版本、段落结构、hook 标注 | 不得复写现有歌词 | 歌词主题一致、无明显侵权 |
| 7 | `Lyric Editor` | 检查语义、押韵、重音、可唱性、风险 | 歌词草稿、brief、受众画像 | 通过版歌词、修改建议、风险标记 | 不得改成另一个主题 | 每句歌词可落拍，敏感风险已标注 |
| 8 | `Melody Composer` | 创作主旋律、副歌 hook、段落旋律 | brief、歌词、BPM、key、风格报告 | MIDI、音符序列、旋律说明 | 不得模仿参考曲可识别旋律 | 旋律覆盖歌词重音，可唱，有 hook |
| 9 | `Harmony Composer` | 设计和弦、转调、张力解决 | 旋律、风格报告、情绪线 | 和弦表、MIDI、段落和声说明 | 不得让和声压过主旋律 | 与旋律无冲突，风格匹配 |
| 10 | `Rhythm Designer` | 设计鼓组、groove、切分、BPM 细节 | brief、风格、受众 | 鼓 MIDI、节奏模板、律动参数 | 不得盲目堆复杂节奏 | 节奏支持目标场景 |
| 11 | `Structure Arranger` | 安排 intro、verse、pre、chorus、bridge、outro | 歌词、旋律、和声、节奏 | song form、时间轴、能量曲线 | 不得任意改时长 | 段落清楚，高潮位置合理 |
| 12 | `Arrangement Producer` | 组合乐器层、动态、过门、铺底 | 结构、旋律、和声、节奏、风格 | 编曲 session、stem 规划、乐器清单 | 不得把 demo 堆成满编 | 主次清楚，频段不拥挤 |
| 13 | `Sound Designer` | 选择/设计 synth、鼓、bass、texture、采样 | 编曲、风格报告、授权库 | 音色预设、采样清单、替代方案 | 不得使用授权不明采样 | 音色来源可追踪 |
| 14 | `Vocal Designer` | 规划人声类型、音域、唱法、和声、adlib | 歌词、旋律、受众、风格 | 人声方案、音域、和声层 | 不得克隆未授权真实声音 | 音域可唱，身份和授权合规 |
| 15 | `Generation Router` | 选择模型、参数、重试策略 | 创作输出、模型能力表、预算 | 模型调用计划、prompt、参数、fallback | 不得绕过授权限制 | 每次调用有目的、成本、预期产物 |
| 16 | `Generation Executor` | 调用模型生成 demo、stem、人声、伴奏 | 路由计划、prompt、MIDI、歌词 | 音频、stem、日志、失败原因 | 不得私自改目标 | 文件命名规范，版本可回溯 |
| 17 | `Audio Analyzer` | 分析响度、BPM、key、频谱、相位、噪声、结构 | 音频、stem、目标规格 | 技术分析报告 | 不得用主观好听替代指标 | 指标可量化 |
| 18 | `Originality Guard` | 检查旋律、歌词、结构、声线、音色相似风险 | 歌词、MIDI、音频、参考画像 | 相似度报告、风险等级、片段定位 | 不得宣称绝对原创 | 风险定位到小节/歌词行/时间码 |
| 19 | `Music Quality Judge` | 综合评价音乐质量和 brief 符合度 | 音频、brief、分析报告、原创性报告 | 分项评分、总分、返工建议 | 不得用总分掩盖硬伤 | 评分能触发通过或返工 |
| 20 | `Rework Orchestrator` | 根据失败原因决定返工路径 | 评分、原创性、音频分析 | 返工单、责任 Agent、停止条件 | 不得无限返工 | 每条返工有范围、保留字段、验收条件 |
| 21 | `Mix Engineer` | 平衡音量、EQ、压缩、空间、自动化 | 通过 QA 的 stems | 混音版、stem mix、混音说明 | 不得重写歌曲 | 主旋律/人声清晰，低频稳定 |
| 22 | `Mastering Engineer` | 输出最终响度、动态、格式 | 混音版、用途规格 | Master WAV/MP3、不同规格版本 | 不得用母带掩盖混音问题 | LUFS、True Peak、采样率、位深达标 |
| 23 | `Catalog Manager` | 归档资产、元数据、版本、报告 | 最终音频、歌词、授权、QA | 资产库记录、版本树、标签 | 不得入库来源不明资产 | 可检索、可追踪、可恢复 |
| 24 | `Rights Configurator` | 记录模型、采样、人声、歌词、客户使用权 | 音色清单、模型日志、合同、素材来源 | 授权配置表、使用范围、限制条款 | 不得给法律结论；不得默认可商用 | 每个资产有来源、权利范围、风险备注 |
| 25 | `Delivery Packager` | 组装交付文件 | master、stems、歌词、授权表、封面/元数据 | 交付包目录或 ZIP | 不得交付未通过版本 | 包结构完整，命名清楚 |
| 26 | `Ops Reporter` | 汇总生产、失败、成本、质量、风险 | 全链路日志、任务状态、模型调用、QA | 日报、异常清单、明日建议 | 不得粉饰失败 | 能看出产能、质量趋势、风险和待处理事项 |

## 4. 推荐流水线

```text
Daily Production Planner
  -> Brief Parser
  -> Style Researcher + Audience Profiler
  -> Creative Director
  -> Lyric Writer
  -> Lyric Editor
  -> Melody Composer
  -> Harmony Composer
  -> Rhythm Designer
  -> Structure Arranger
  -> Arrangement Producer
  -> Sound Designer
  -> Vocal Designer
  -> Generation Router
  -> Generation Executor
  -> Audio Analyzer
  -> Originality Guard
  -> Music Quality Judge
  -> Rework Orchestrator
  -> Mix Engineer
  -> Mastering Engineer
  -> Catalog Manager
  -> Rights Configurator
  -> Delivery Packager
  -> Ops Reporter
```

并行节点：

- `Style Researcher` 和 `Audience Profiler` 可以并行。
- `Melody Composer`、`Harmony Composer`、`Rhythm Designer` 可在初稿阶段并行，但必须由 `Structure Arranger` 汇总。
- `Audio Analyzer`、`Originality Guard`、`Music Quality Judge` 可在候选生成后并行，但最终决策由 `Rework Orchestrator` 汇总。

## 5. 返工责任映射

| 失败原因 | 回流 Agent | 不应回流 |
|---|---|---|
| brief 模糊或互相矛盾 | `Brief Parser` | 不应直接重生音频 |
| 风格跑偏 | `Style Researcher`、`Arrangement Producer`、`Generation Router` | 不应只做母带 |
| 受众不匹配 | `Audience Profiler`、`Creative Director` | 不应只改标题 |
| 歌词不可唱 | `Lyric Editor` | 不应重做混音 |
| hook 弱 | `Melody Composer`、`Lyric Writer` | 不应重做母带 |
| 和声冲突 | `Harmony Composer` | 不应替换模型 |
| 节奏不稳 | `Rhythm Designer` | 不应改授权 |
| 编曲空洞或太满 | `Arrangement Producer`、`Sound Designer` | 不应重写歌词 |
| 人声咬字或音域问题 | `Vocal Designer` | 不应改版权配置 |
| 爆音、削波、低频浑 | `Mix Engineer`、`Mastering Engineer` | 不应重写歌曲 |
| 旋律/歌词相似风险 | `Originality Guard`、`Melody Composer`、`Lyric Writer` | 不应人工硬过 |
| 授权缺失 | `Rights Configurator` | 不应重新生成音乐 |
| 文件缺失或交付包不完整 | `Catalog Manager`、`Delivery Packager` | 不应改曲 |

## 6. 首版页面如何体现 Agent

第一阶段网站不需要真的启动 26 个独立进程，但页面和数据结构要能展示 Agent 状态。

`每日任务` 页面显示：

- 当前阶段。
- 下一个 Agent。
- 失败原因。
- 返工次数。
- 是否需要人工复核。

`作品库` 页面显示：

- 作品版本树。
- 每个版本由哪个 Agent 生成。
- prompt、seed、模型版本。
- 当前授权状态。

`评分中心` 页面显示：

- 哪个 Agent 给出评分。
- 哪个维度失败。
- 返工应回流到哪个 Agent。

`交付与授权中心` 页面显示：

- 授权配置 Agent 状态。
- 交付包 Agent 状态。
- 缺失字段。
- 阻断原因。

## 7. 成功标准

该分工设计通过的标准：

- 每个生产阶段都有明确责任 Agent。
- 每个 Agent 有输入、输出、禁止事项、交接验收。
- 任何失败都能映射到责任 Agent。
- 授权问题不会被音乐返工掩盖。
- 混音母带不会替上游创作背锅。
- 交付包不会绕过原创性和授权检查。
