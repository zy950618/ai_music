# LOOP 状态机与返工决策树

## 1. 定义

这里的 `LOOP` 指音乐制作闭环状态机，不是单指 BGM 的无缝循环点。`loop 接缝不自然` 只是 QA 失败原因之一。

核心目标：

- 每天自动创建 10-20 条制作任务。
- 每条任务生成 3-5 个候选版本。
- 每个候选都经过音频 QA、音乐性 QA、原创性 QA。
- 低分候选按失败原因返工。
- 不把“低分”简单等同于“重新生成”。
- 授权、版权、声线、系统异常不自动硬过。

## 2. 核心规则

- 最小返工单位是 `version`，不是整条任务。
- 任何返工必须有 `failure_code + evidence + targeted_action + retry_budget`。
- 没有明确失败原因时，不进入 `REWORKING`，进入 `HUMAN_REVIEW_REQUIRED` 或 `REJECTED`。
- 只有生成瑕疵、局部断裂、文件损坏、模型输出错段等原因允许局部或候选级重生。
- 版权高风险、授权缺失、系统异常、连续同因失败、审美冲突不自动通过。
- 每次返工必须声明 `preserve_fields` 和 `mutable_fields`，避免把已通过部分洗掉。

## 3. 主状态机

```text
CREATED
  -> BRIEF_READY
  -> COMPOSITION_READY
  -> GENERATING
  -> VERSIONS_READY
  -> AUDIO_QA_PASS
  -> MUSIC_QA_PASS
  -> ORIGINALITY_PASS
  -> SELECTED
  -> MIXING
  -> MASTERED
  -> FINAL_QA_PASS
  -> STORED
  -> DELIVERY_PACKAGE_READY
```

失败与返工支路：

```text
VERSIONS_READY
  -> AUDIO_QA_FAIL / MUSIC_QA_FAIL / ORIGINALITY_REWORK
  -> REWORK_PENDING
  -> REWORKING
  -> VERSIONS_READY
```

人工复核支路：

```text
ORIGINALITY_HIGH_RISK / UNKNOWN_FAILURE / REWORK_LIMIT_REACHED / SYSTEM_BLOCKED
  -> HUMAN_REVIEW_REQUIRED
  -> HUMAN_APPROVED / REBRIEF / REJECTED
```

交付阻断支路：

```text
STORED
  -> DELIVERY_AUTH_CHECK
  -> DELIVERY_BLOCKED / DELIVERY_PACKAGE_READY
```

## 4. 阶段规则

| 阶段 | 通过条件 | 常见失败原因 | 下一步动作 | 重试 | 人工介入 |
|---|---|---|---|---:|---|
| `CREATED` | 今日任务数 10-20；风格、用途、受众、优先级完整 | 配额冲突、库存目标缺失、重复任务 | 重算任务池 | 1 | 今日目标冲突 |
| `BRIEF_READY` | brief 有风格、BPM、key、结构、时长、受众、硬门槛 | brief 模糊、互相矛盾、参考歌风险高 | 重写 brief 或移除风险参考 | 1 | 真实歌曲/歌手强模仿 |
| `COMPOSITION_READY` | 歌词、旋律、和声、编曲方案完整；可唱性初筛通过 | 歌词不可唱、hook 弱、结构缺段、风格跑偏 | 只改对应方案 | 每类 1 | 主题/品牌/审美方向冲突 |
| `GENERATING` | 生成 3-5 个候选；音频、prompt、seed、模型版本完整 | 超时、空文件、时长错、模型失败 | 补生成缺失候选 | 系统 2，候选 1 | 模型连续不可用或成本超限 |
| `VERSIONS_READY` | 每个候选有关联任务、版本号、文件、元数据 | 版本孤立、文件缺失、元数据缺失 | 补齐资产或废弃该候选 | 1 | 数据链路异常 |
| `AUDIO_QA_PASS` | 硬性音频门槛通过 | 爆音、削波、静音、断裂、响度异常、loop 接缝差 | 按音频原因返工 | 见失败表 | 同类故障跨候选大量出现 |
| `MUSIC_QA_PASS` | 总分 >=80 且核心子项过线 | hook 弱、旋律差、结构散、编曲空/满、歌词差、受众不匹配 | 改对应上游 | 1-2 | 评审分歧大 |
| `ORIGINALITY_PASS` | 原创风险低或可接受中低风险 | 旋律/歌词/声线/参考相似度风险 | 中风险定向改写，高风险人工 | 中风险 1 | 高风险必须人工 |
| `SELECTED` | 至少 1 个候选通过，选最高综合收益版本 | 无候选达标 | 返工或任务终止 | 受全局限制 | 全版本失败但任务仍有价值 |
| `MIXING` | 人声/主旋律/低频/动态平衡；分轨可用 | 人声埋、低频浑、动态差、层次乱 | 只重做混音 | 2 | 缺分轨或源文件不可修 |
| `MASTERED` | 母带响度、峰值、格式符合用途 | 过压、刺耳、响度不达标 | 重做母带 | 2 | 母带反复破坏听感 |
| `FINAL_QA_PASS` | 硬门槛全过；总分 >=82；资产完整 | 最终爆音、导出缺失、授权缺失、元数据缺失 | 技术补救；授权阻断交付 | 技术 1 | 授权、版权、声明缺失 |
| `STORED` | 作品、版本、QA、返工、prompt、seed 入库 | 资产记录不完整 | 补资产记录 | 1 | 数据不可追溯 |
| `DELIVERY_PACKAGE_READY` | 授权主体、使用范围、AI 声明、导出规格完整 | 授权缺失、范围不明、平台连接异常 | `DELIVERY_BLOCKED`，不返工音乐 | 0 | 必须人工处理授权/账号 |

## 5. 硬性门槛

任何一项失败，都不能进入交付：

| 门槛 | 阈值 |
|---|---|
| 文件可解码 | 音频能完整解码；无空文件；时长不为 0 |
| 时长 | 与 brief 目标偏差不超过 `±10%`；短 loop/BGM 按小节数校验 |
| 爆音/削波 | 不允许明显数字削波；最终母带 true peak `<= -1.0 dBTP` |
| 静音/断裂 | 非设计性静音 `>0.5s` 或 dropout `>0.2s` 直接失败 |
| 响度 | 按用途配置；默认预览版 integrated LUFS 在目标 `±2 LU` 内 |
| loop 接缝 | loop 类资产首尾节拍对齐；接缝无 click/pop；首尾能量差 `<=3 dB` |
| 歌词安全 | 无明显侵权歌词、敏感不可授权内容、真实作品核心句复用 |
| 声线风险 | 不得明确模仿真实歌手、真实歌曲或可识别旋律 |
| 原创风险 | 高相似度风险直接阻断，不能自动通过 |
| 交付完整性 | master、preview、必要分轨、元数据、QA、授权字段齐全 |
| 授权配置 | 授权未完成时可以入库，但不能进入自动交付队列 |

## 6. 评分阈值

| 维度 | 权重 | 最低线 |
|---|---:|---:|
| 听感与音频质量 | 15 | 12 |
| 旋律质量 | 20 | 14 |
| 朗朗上口 | 15 | 10 |
| 结构完整度 | 10 | 7 |
| 编曲与音色 | 10 | 7 |
| 歌词与可唱性 | 10 | 7 |
| 受众匹配 | 10 | 7 |
| 原创与安全 | 5 | 4 |
| 制作交付完整性 | 5 | 4 |

决策：

- `90-100`：优先入库，可作为高质量样本。
- `80-89`：通过；若子项低于最低线，仍要定向返工。
- `75-79`：自动返工，优先修最高权重失败项。
- `70-74`：只在失败原因清晰且预算允许时返工，否则 `REBRIEF` 或 `REJECTED`。
- `<70`：不盲目重生。若是 brief 错，重开 brief；若是生成坏，最多补一个候选；否则废弃。
- 硬门槛失败：无论总分多少，都不能通过。

纯音乐任务中，`歌词与可唱性` 不空打满分；这 10 分按 brief 配置重分配到 `旋律、结构、编曲、受众匹配`。

## 7. 返工决策树

```text
1. 是否系统异常？
   是 -> 系统重试，仍失败则 HUMAN_REVIEW_REQUIRED
   否 -> 继续

2. 是否硬性门槛失败？
   是 -> 按 hard_gate_failure_code 处理
        版权/声线/高相似度 -> HUMAN_REVIEW_REQUIRED 或 REJECTED
        文件/导出/元数据 -> 补文件或重导出
        爆音/响度 -> 混音/母带返工
        静音/断裂/生成瑕疵 -> 局部重生或替换候选
   否 -> 继续

3. 总分是否 >=80 且核心子项过线？
   是 -> SELECTED 或进入下一 QA
   否 -> 继续

4. 分数是否在 70-79？
   是 -> 找 Top 1-2 个失败原因，生成定向 rework brief
        若原因不清 -> HUMAN_REVIEW_REQUIRED
   否 -> 继续

5. 分数 <70？
   brief 矛盾 -> REBRIEF，一次
   生成瑕疵 -> 补生成一个候选
   音乐性整体失败 -> REJECTED，不重复同 prompt 重生

6. 同一 failure_code 是否已经失败 2 次？
   是 -> HUMAN_REVIEW_REQUIRED 或 REJECTED
   否 -> REWORK_PENDING -> REWORKING
```

## 8. 失败原因到返工动作

| failure_code | 证据 | 返工动作 | 保留 | 上限 |
|---|---|---|---|---:|
| `AUDIO_CLIPPING` | 峰值、削波、刺耳 | 降增益、重混、重母带 | 旋律、歌词、结构 | 2 |
| `AUDIO_DROPOUT` | 静音、断裂、坏段 | 只重生坏段或替换该候选 | brief、曲式、好段落 | 2 |
| `BAD_DURATION` | 时长偏差超阈值 | 重新约束结构/小节数后补生成 | 风格、hook 目标 | 1 |
| `HOOK_WEAK` | hook 晚、弱、不可记 | 重写副歌动机，提前高潮 | 歌词主题、风格 | 2 |
| `MELODY_UNSINGABLE` | 音域过宽、大跳密 | 缩小音域、简化节奏 | 核心情绪、结构 | 2 |
| `LYRIC_UNSINGABLE` | 字多、重音错、押韵差 | 改字数、重排重音、改押韵 | 主题、核心句 | 2 |
| `STYLE_DRIFT` | BPM/乐器/情绪偏离 | 回到 brief 强约束 prompt 和编曲 | 可用旋律/歌词 | 1 |
| `ARRANGEMENT_EMPTY` | 层次薄、推进弱 | 加低频、节奏层、过门 | 主旋律、歌词 | 2 |
| `ARRANGEMENT_OVERFULL` | 层太多、主次乱 | 减层、突出主旋律/人声 | hook、结构 | 2 |
| `VOCAL_BAD` | 咬字差、音域不适 | 换音域/人声参数；必要时纯音乐版 | 歌词和旋律意图 | 2 |
| `LOOP_SEAM_BAD` | 首尾突兀、click/pop | 重做尾部、crossfade、循环点 | 主体 90% 内容 | 2 |
| `AUDIENCE_MISMATCH` | 场景不符 | 调整能量、音色、节奏密度 | 基本风格 | 1 |
| `ORIGINALITY_MEDIUM` | 中等相似风险 | 改旋律轮廓、节奏型、核心句 | 情绪和用途 | 1 |
| `ORIGINALITY_HIGH` | 高相似或声线模仿 | 不自动返工；人工/废弃 | 无 | 0 |
| `METADATA_MISSING` | 元数据/授权字段缺 | 补数据，不重生音乐 | 全部音频 | 1 |
| `UNKNOWN_FAILURE` | 只有低分无原因 | 禁止返工，人工复核 | 无 | 0 |

## 9. 重试规则

- 单版本自动返工最多 2 次。
- 单任务自动返工最多 3 轮。
- 同一 `failure_code` 在同一版本出现第 2 次后，不再自动尝试第 3 次。
- 同一 `failure_code` 出现在同任务超过 60% 候选时，说明上游 brief、编曲或 prompt 有问题，不能继续候选级重生。
- 系统或模型调用失败最多重试 2 次；之后挂起任务，不消耗音乐返工次数。
- 每次返工只能修改 `mutable_fields`，必须声明 `preserve_fields`。

## 10. 人工介入条件

- 原创、版权、声线高风险。
- 授权主体、使用范围、AI 声明、账号连接不完整。
- 失败原因无法归类。
- 同一原因连续失败。
- 多个评审器评分差异 `>20` 分，或机器高分但文字评语明显负面。
- 任务分数低于 70，但业务仍要求保留方向。
- 当日异常率超过阈值，需要暂停流水线。
- 用户或客户指定的审美、品牌判断无法由规则决定。

## 11. 每日产能控制

默认配额：

```text
每日新任务目标：15 条，允许范围 10-20
每任务初始候选：4 个，允许范围 3-5
初始生成预算：约 60 个候选/日
返工生成预算：总生成预算的 30%-35%
紧急保留预算：10%
单日总生成任务上限：由模型额度/成本/并发共同决定
```

计算方式：

```text
generation_budget = min(模型日额度, 成本预算 / 单次平均成本, 并发能力 * 日可用批次数)
rework_budget = floor(generation_budget * 0.30)
new_task_budget = generation_budget - rework_budget - emergency_reserve
new_task_count = clamp(10, 20, floor(new_task_budget / 初始候选数))
```

产能闸门：

- `AUDIO_QA_FAIL` 首批超过 35%：暂停新生成，先查模型参数、prompt、母带链。
- `ORIGINALITY_HIGH` 超过 5% 候选或 2 个任务：暂停参考歌链路。
- 同一失败原因占当天失败数 `>25%`：归为系统性问题，优先修上游。
- 返工预算在早上 06:00 前消耗 `>80%`：只返工 75-79 分且原因清晰的版本。
- 人工复核 backlog `>10` 或最老超过 24h：暂停新增高风险任务。
- 成本/额度达到 90%：停止新生成，只允许 QA、混音、母带、入库、授权补全。
- 交付授权缺失不占音乐返工预算，只进入 `DELIVERY_BLOCKED`。

## 12. 必存字段

```ts
type VersionLoopState = {
  state: string;
  score_total: number;
  score_breakdown: Record<string, number>;
  hard_gate_results: Record<string, boolean>;
  failure_codes: string[];
  root_cause: string;
  rework_round_count: number;
  version_rework_count: number;
  parent_version_id?: string;
  rework_brief?: string;
  preserve_fields: string[];
  mutable_fields: string[];
  next_agent: string;
  manual_review_reason?: string;
  capacity_bucket: "new_generation" | "rework" | "emergency" | "blocked";
};
```

这些字段保证系统不是看到低分就重生，而是先判断失败层级，再决定改词、改曲、改编曲、改混音、补元数据、人工复核，还是直接废弃。
