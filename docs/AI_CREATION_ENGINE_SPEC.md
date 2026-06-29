# AI 音乐创作引擎 MVP 规格

## 1. 定位

AI 音乐创作引擎是本项目的第一优先级。网站只是承载它的工作台。

第一阶段必须证明系统能完成：

- 输入创作需求。
- 生成歌词、旋律、和声、结构、编曲 prompt。
- 生成或接入可下载音乐文件。
- 对音乐做剪辑、截取、淡入淡出、循环点处理。
- 做基础音频处理和导出。
- 保存版本、评分、返工原因和授权状态。

如果没有真实模型，第一版也必须有 `mock / adapter` 创作链路，让后续能无缝替换为 ACE-Step、YuE、DiffRhythm 或外部生成服务。

## 2. 第一阶段验收口径

第一阶段不以“网站页面齐不齐”为核心验收，而以“创作链路能不能跑通”为核心验收。

必须通过：

- 能创建一条音乐创作任务。
- 能生成结构化创作 brief。
- 能生成歌词或纯音乐结构。
- 能生成 3-5 个候选版本记录。
- 每个候选有音频文件路径或外部下载 URL。
- 能下载生成音乐。
- 能做至少 4 类剪辑处理：截取、拼接/片段组合、淡入淡出、循环点处理。
- 能导出 `preview` 和 `master` 两类文件记录。
- 能给每个版本生成评分和失败原因。
- 能生成返工 brief。

## 3. 创作链路

```text
用户需求
  -> Brief Parser
  -> Style Researcher
  -> Audience Profiler
  -> Lyric Writer / Instrumental Planner
  -> Melody Composer
  -> Harmony Composer
  -> Structure Arranger
  -> Arrangement Producer
  -> Generation Router
  -> Generation Executor
  -> Audio Editor
  -> Audio Processor
  -> Quality Judge
  -> Rework Orchestrator
  -> Asset Exporter
```

## 4. 创作输入

```ts
type MusicCreationRequest = {
  title?: string;
  mode: "song" | "instrumental" | "bgm" | "loop" | "short_video" | "children" | "classical" | "game" | "film";
  language?: "zh" | "en" | "ja" | "ko" | "none";
  theme: string;
  mood: string[];
  genre: string[];
  audience: string;
  use_case: string;
  duration_sec: number;
  bpm?: number;
  key?: string;
  vocal_required: boolean;
  lyrics_input?: string;
  reference_profile_id?: string;
  forbidden: string[];
  export_formats: Array<"wav" | "mp3" | "aac" | "midi" | "stems">;
};
```

## 5. 创作输出

```ts
type MusicCreationResult = {
  task_id: string;
  work_id: string;
  versions: MusicVersion[];
  selected_version_id?: string;
  qa_summary: string;
  rework_suggestions: string[];
  rights_status: "missing" | "configured" | "review_required" | "blocked";
};

type MusicVersion = {
  version_id: string;
  title: string;
  status: "generated" | "edited" | "processed" | "qa_pass" | "qa_fail" | "selected" | "rework";
  audio_source: "local_file" | "external_download_url" | "mock_file";
  audio_path?: string;
  download_url?: string;
  duration_sec: number;
  bpm?: number;
  key?: string;
  lyrics?: string;
  structure: SongSection[];
  prompt_snapshot: string;
  model_provider: string;
  model_name: string;
  model_version?: string;
  score_total?: number;
  failure_codes: string[];
  export_files: ExportFile[];
};
```

## 6. 生成方式

第一版支持三种生成来源，统一由 `Generation Router` 管理：

| 来源 | 作用 | 是否第一阶段可用 |
|---|---|---|
| `mock_file` | 无模型时生成占位音频和完整版本记录 | 必须支持 |
| `external_download_url` | 外部 AI 音乐服务已经生成，可下载 URL 导入系统 | 必须支持 |
| `local_model_adapter` | ACE-Step、YuE、DiffRhythm 等本地或远程模型 | 预留接口，逐步接入 |

要求：

- 页面和后端不直接耦合某个模型。
- 外部下载 URL 导入后，也必须进入 QA、授权和交付流程。
- 本地文件和外部下载文件统一落入作品库。

## 7. AI 怎么创作

### 7.1 歌词型歌曲

```text
主题/受众/风格
  -> 歌词结构：verse / pre / chorus / bridge / outro
  -> hook 句
  -> 押韵和重音检查
  -> 旋律动机设计
  -> 和弦走向
  -> 编曲结构
  -> 生成音频
```

输出：

- 歌词。
- 主 hook。
- BPM、key。
- 段落结构。
- prompt。
- 3-5 个候选音频。

### 7.2 纯音乐 / BGM

```text
用途/场景/情绪
  -> 结构：intro / A / B / climax / loop outro
  -> 主旋律或主题动机
  -> 和声和低频运动
  -> 鼓组和节奏密度
  -> 音色和空间
  -> 生成音频
```

输出：

- 主题动机说明。
- 段落时间轴。
- loop 点。
- 15s / 30s / 60s / full 版本。

### 7.3 参考风格创作

```text
参考音频
  -> 分轨/特征分析
  -> BPM / key / energy / structure / instrument profile
  -> 风格画像
  -> 禁止复制旋律、歌词、声线
  -> 原创 brief
  -> 生成候选
```

输出只能是原创作品，不能复制参考歌。

## 8. AI 怎么剪辑

`Audio Editor` 负责非破坏式剪辑，所有操作保存为 edit decision list。

```ts
type EditDecision = {
  id: string;
  version_id: string;
  operation: "trim" | "split" | "join" | "fade_in" | "fade_out" | "crossfade" | "loop" | "normalize" | "render_variant";
  start_sec?: number;
  end_sec?: number;
  params: Record<string, unknown>;
};
```

首版必须支持：

| 操作 | 作用 | 验收 |
|---|---|---|
| `trim` | 截取 15s / 30s / 60s / 自定义片段 | 输出片段时长正确 |
| `fade_in` | 开头淡入 | 无突兀 click |
| `fade_out` | 结尾淡出 | 尾音不截断 |
| `crossfade` | 两段拼接过渡 | 接缝不突兀 |
| `loop` | 制作循环版本 | 首尾节拍对齐，无 click/pop |
| `render_variant` | 导出短版、长版、预览版 | 文件可下载 |

## 9. AI 怎么处理音频

`Audio Processor` 负责基础音频处理。

首版处理能力：

| 能力 | 作用 | 验收 |
|---|---|---|
| loudness normalize | 统一预览响度 | LUFS 在目标范围 |
| peak limit | 防止削波 | true peak 不超过阈值 |
| silence trim | 去除异常静音 | 不误删音乐尾音 |
| format convert | WAV/MP3/AAC 导出 | 文件可播放可下载 |
| stem attach | 关联分轨文件 | 作品库能看到 stem 状态 |
| metadata write | 写入 BPM、key、版本、AI 声明 | 交付包可读取 |

后续处理能力：

- 分轨。
- 人声提取。
- 音频转 MIDI。
- 调性分析。
- 结构自动分段。
- 相似度检测。
- 水印嵌入。

## 10. 下载与导出

音乐是可以下载的生成物，系统必须把下载作为创作交付的一部分。

```ts
type ExportFile = {
  id: string;
  version_id: string;
  kind: "preview" | "master" | "short_cut" | "loop" | "instrumental" | "stems" | "midi" | "lyrics" | "license_pack";
  format: "wav" | "mp3" | "aac" | "zip" | "mid" | "txt" | "json";
  path?: string;
  download_url?: string;
  size_bytes?: number;
  checksum?: string;
  ready: boolean;
  blocked_reason?: string;
};
```

下载规则：

- `preview` 可以在授权未完成时下载给内部试听。
- `master` 必须通过最终 QA。
- `license_pack` 未完成时，不能显示为正式可交付。
- 外部下载 URL 必须被导入、记录来源、生成 checksum，再进入作品库。

## 11. 第一版技术落地建议

为了尽快跑通创作，不一开始卡在大模型安装：

1. 实现 `Creation Engine` 的数据模型和服务接口。
2. 实现 `mock_file`：生成可播放的简单占位音频或导入已有下载音频。
3. 实现 `external_download_url`：把外部 AI 音乐生成结果下载/登记到作品库。
4. 实现基础剪辑和导出记录。
5. 实现 QA 评分 mock。
6. 再接 ACE-Step / YuE / DiffRhythm 适配器。

## 12. 第一阶段最小成功标准

- [ ] 创建音乐创作任务。
- [ ] 生成结构化 brief。
- [ ] 生成歌词或纯音乐结构。
- [ ] 生成 3-5 个候选版本记录。
- [ ] 至少一个候选有可播放音频或下载 URL。
- [ ] 能生成 15s、30s、full 三种导出记录。
- [ ] 能执行 trim、fade、loop、render variant 的剪辑记录。
- [ ] 能下载生成音频。
- [ ] 能看到评分和返工建议。
- [ ] 授权缺失时阻断正式交付，但不阻断内部试听下载。
