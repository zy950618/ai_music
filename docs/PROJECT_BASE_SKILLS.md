# 项目基础 Skills

## 1. 定位

本文件定义 AI 音乐制作项目长期使用的基础 Skills。所有后续实现、Agent 分工、自动任务、LOOP、验收和交付，都必须以这些 Skills 为基础。

这些 Skills 是项目能力层，不是一次性文档。后续代码实现应逐步把它们落成模块、服务、任务、页面和测试。

## 2. Skill 分层

| 层级 | Skills | 目标 |
|---|---|---|
| 创作层 | Brief、作词、旋律、和声、结构、编曲、音色、人声 | 生成音乐内容 |
| 生成层 | 模型路由、候选生成、外部下载导入 | 产出音频版本 |
| 编辑处理层 | 剪辑、淡入淡出、循环点、响度、格式转换 | 把音频变成可用作品 |
| 验收层 | 音频 QA、音乐性评分、受众评分、原创性检查 | 判断是否可入库和返工 |
| LOOP 层 | 失败原因、返工 brief、责任 Agent、重试预算 | 自动迭代到合格 |
| 资产层 | 作品库、版本树、prompt、seed、模型日志、下载文件 | 可追踪、可恢复 |
| 授权交付层 | 授权配置、AI 声明、交付包、导出规格 | 可安全交付 |
| 自动化层 | 每日任务、产能控制、日报、异常队列 | 长期自动运行 |

## 3. 基础 Skills 清单

### 3.1 `Creation Brief Skill`

职责：

- 把用户输入转成结构化音乐创作 brief。
- 明确风格、受众、用途、时长、BPM、key、语言、是否人声。
- 写明禁止项和硬性验收门槛。

输入：

- 用户需求。
- 参考风格画像。
- 授权限制。

输出：

- `MusicCreationRequest`。
- `hard_constraints`。
- `forbidden_constraints`。

验收：

- brief 不互相矛盾。
- 下游能直接使用。

### 3.2 `Lyric Writing Skill`

职责：

- 写词、改词、生成 hook 句。
- 检查押韵、语感、重音和可唱性。

输出：

- verse / pre / chorus / bridge / outro。
- hook 标注。
- 可唱性说明。

禁止：

- 复写真实歌词。
- 使用未授权品牌、人物或敏感内容。

### 3.3 `Melody Composition Skill`

职责：

- 生成主旋律、副歌动机、段落旋律。
- 控制音域、重复、动机变化和可唱性。

输出：

- MIDI 或符号旋律。
- 旋律轮廓说明。
- hook 位置。

验收：

- 主 hook 可识别。
- 音域适合目标受众。
- 强拍和歌词重音不冲突。

### 3.4 `Harmony Composition Skill`

职责：

- 生成和弦走向、转调、张力和解决。
- 匹配风格和情绪线。

输出：

- 和弦表。
- 和声 MIDI。
- 段落和声说明。

### 3.5 `Arrangement Skill`

职责：

- 设计 intro、verse、chorus、bridge、outro。
- 规划鼓、贝斯、主旋律、铺底、过门、音色层。
- 生成短版、完整版、循环版结构。

输出：

- song form。
- 能量曲线。
- stem 规划。
- 编曲 prompt。

### 3.6 `Generation Router Skill`

职责：

- 统一管理生成来源。
- 支持 `mock_file`、`external_download_url`、`local_model_adapter`。
- 后续接 ACE-Step、YuE、DiffRhythm。

要求：

- 页面不能直接调用模型。
- 每个结果必须记录模型、prompt、seed、版本。
- 外部下载音乐也必须进入 QA 和授权流程。

### 3.7 `Candidate Generation Skill`

职责：

- 每个任务生成 3-5 个候选版本。
- 保存音频路径或下载 URL。
- 保存生成日志。

验收：

- 候选版本可追踪。
- 至少一个候选可播放或可下载。

### 3.8 `Audio Editing Skill`

职责：

- 非破坏式剪辑。
- 保存 edit decision list。

首版必须支持：

- `trim`
- `fade_in`
- `fade_out`
- `crossfade`
- `loop`
- `render_variant`

验收：

- 能生成 15s、30s、full、loop 版本记录。
- 文件可下载。

### 3.9 `Audio Processing Skill`

职责：

- loudness normalize。
- peak limit。
- silence trim。
- format convert。
- metadata write。
- stem attach。

验收：

- 输出可播放。
- 不削波。
- 不误删尾音。
- 元数据完整。

### 3.10 `Download Export Skill`

职责：

- 管理 preview、master、short cut、loop、lyrics、metadata、license pack。
- 管理本地文件和外部下载 URL。

规则：

- `preview` 可用于内部试听。
- `master` 必须通过最终 QA。
- 授权不完整不能进入正式交付。

### 3.11 `Quality Acceptance Skill`

职责：

- 对每个版本评分。
- 生成硬门槛结果和加权评分。

评分维度：

- 听感与音频质量。
- 旋律质量。
- 朗朗上口。
- 结构完整度。
- 编曲与音色。
- 歌词与可唱性。
- 受众匹配。
- 原创与安全。
- 制作交付完整性。

### 3.12 `Loop Rework Skill`

职责：

- 根据 `failure_code` 生成定向返工 brief。
- 指定责任 Agent。
- 指定保留字段和可变字段。
- 控制重试预算。

规则：

- 低分不等于重生。
- `UNKNOWN_FAILURE` 不自动返工。
- `ORIGINALITY_HIGH` 不自动返工。
- `METADATA_MISSING` 只补元数据，不重生音乐。

### 3.13 `Originality Guard Skill`

职责：

- 检查旋律、歌词、声线、采样、参考相似度风险。

禁止：

- 宣称绝对原创。
- 只查歌词不查旋律。
- 高风险自动通过。

### 3.14 `Rights Configuration Skill`

职责：

- 配置授权主体。
- 配置使用范围。
- 配置 AI 声明。
- 配置模型和素材来源。
- 配置是否可商用、是否可转授权、是否可改编。

规则：

- 授权缺失可以入库，但不能正式交付。
- 授权缺失不触发音乐返工，只触发 `DELIVERY_BLOCKED`。

### 3.15 `Delivery Package Skill`

职责：

- 生成交付包。
- 包含 master、preview、instrumental、stems、lyrics、metadata、license pack、acceptance report。

验收：

- 文件完整。
- 命名清楚。
- 版本一致。
- 授权完整。

### 3.16 `Daily Automation Skill`

职责：

- 每天创建 10-20 条音乐制作任务。
- 每条生成 3-5 个候选。
- 根据质量和预算决定返工。

产能规则：

- 首批 `AUDIO_QA_FAIL` 超过 35%，暂停新生成。
- `ORIGINALITY_HIGH` 超过 5% 候选，暂停参考歌链路。
- 返工预算早上 06:00 前消耗超过 80%，只返工 75-79 分且原因清晰的版本。

### 3.17 `Ops Report Skill`

职责：

- 每日汇总任务数、候选数、入库数、废弃数、人工复核数、失败原因、成本、明日建议。

验收：

- 能看出系统是否健康。
- 能看出哪个 Skill 或 Agent 失败率高。
- 能指导次日任务权重。

## 4. 长期运行方式

长期运行不是无限随机生成，而是按阶段推进：

```text
Phase 1: 创作引擎
  -> Phase 2: 网站工作台
  -> Phase 3: Mock 自动流水线
  -> Phase 4: 音频/MIDI 分析
  -> Phase 5: 真实模型适配
  -> Phase 6: 质量返工闭环
  -> Phase 7: 授权交付闭环
  -> Phase 8: 运营优化
```

每个阶段都必须：

- 有可运行产物。
- 有验收清单。
- 有失败处理。
- 有下一阶段输入。

## 5. 当前最优先实现

当前应立即进入 `Phase 1: AI 创作引擎 MVP`。

实现顺序：

1. 创建项目代码骨架。
2. 定义数据模型。
3. 实现创作任务创建。
4. 实现 brief 生成。
5. 实现 mock 候选版本。
6. 实现外部下载 URL 导入。
7. 实现基础剪辑记录。
8. 实现导出文件记录。
9. 实现评分和返工建议。
10. 实现授权阻断规则。

## 6. 成功标准

基础 Skills 设置完成后，后续任何实现都不能绕过：

- `Generation Router`
- `Quality Acceptance Skill`
- `Loop Rework Skill`
- `Originality Guard Skill`
- `Rights Configuration Skill`
- `Download Export Skill`

这六个 Skill 是项目核心门禁。
