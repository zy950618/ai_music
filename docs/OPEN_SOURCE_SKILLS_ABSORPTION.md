# 开源 AI 音乐项目 Skills 吸收方案

## 1. 目标

本文件把外部开源 AI 音乐项目的能力拆成可落地 Skills。目标不是复制别人的产品，而是吸收成熟能力，组合成本项目的音乐制作流水线。

吸收原则：

- 优先吸收工程能力、流程能力、分析能力和接口模式。
- 生成模型必须走项目内的质量、原创性、授权和交付门禁。
- 不把非商用权重、社区许可证权重、授权不清数据直接接入商用交付链路。
- 参考歌曲只能进入风格画像和结构分析，不能进入复制旋律、复制歌词、克隆真实歌手声线的链路。

## 2. 优先级定义

| 优先级 | 含义 | 第一阶段处理方式 |
|---|---|---|
| `P0` | 可直接支撑基础制作能力，许可和工程风险相对低 | 先纳入架构和数据模型 |
| `P1` | 生成能力价值高，但需要队列、算力、原创性和授权门禁 | 作为模型适配器试点 |
| `P2` | 适合研究、高级模式或借鉴设计，不宜直接进商用主链路 | 写入研发储备 |
| `P3` | 只观察，不进入当前实现 | 暂不接入 |

## 3. 项目能力吸收表

| 外部项目 | 可吸收 Skill | 适用环节 | 输入 | 输出 | 优先级 | 边界 |
|---|---|---|---|---|---|---|
| [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | 本地整歌生成、歌词/风格/时长/BPM/调式控制、编辑、LoRA 个性化 | 主生成、重绘、风格定制 | 歌词、风格 prompt、参考画像、时长、BPM、调式 | 候选音频、stem、歌词时间信息 | `P1` | 需要显存、队列和原创性检查；禁止真实歌手模仿和高相似参考复刻 |
| [YuE](https://github.com/multimodal-art-projection/YuE) | lyrics-to-song、长歌词成歌、主唱+伴奏一致性 | 有歌词歌曲、中文/多语种完整歌 | 歌词、风格、结构、可选上下文 | 完整歌曲候选 | `P1/P2` | 推理重，适合异步任务；必须做歌词版权、声线风险和旋律相似度检查 |
| [DiffRhythm](https://github.com/ASLP-lab/DiffRhythm) | 快速整歌 demo、纯音乐、续写、参考风格生成 | A/B 草稿、短视频 BGM、快速候选 | LRC/歌词、风格文本、参考 WAV | 1-5 分钟候选音频 | `P1` | 适合批量候选；训练/微调能力不要默认可用；参考音频只能用作风格约束 |
| [AudioCraft](https://github.com/facebookresearch/audiocraft) | 音频生成研究框架、EnCodec、MusicGen、JASCO、AudioSeal 组织方式 | 研究框架、tokenizer、模型服务设计 | 数据集、配置、文本、控制信号 | 生成模型、token、音频、水印 | `P2` | 代码与权重许可分开看；直接商用前必须核实每个权重许可证 |
| [MusicGen](https://github.com/facebookresearch/audiocraft) | 文本到音乐、旋律/chroma 引导、短 BGM 片段 | 灵感草稿、循环片段、旋律约束 | 文本、可选旋律音频 | 短音乐片段 | `P2` | 部分权重非商用，不直接进入商用交付 |
| [JASCO](https://github.com/facebookresearch/audiocraft) | 和弦、鼓组、旋律时间轴控制 | 可控编曲、约束生成思想 | 文本、和弦时间点、鼓/旋律控制 | 可控短音乐 | `P2` | 重点吸收“可控生成接口”，不要误用非商用权重 |
| [AudioSeal](https://github.com/facebookresearch/audioseal) | 音频水印、局部水印检测、溯源治理 | AI 声明、资产追踪、交付治理 | 音频 | 水印音频、检测结果 | `P0/P1` | 音乐成品需做音质 AB、压缩后鲁棒性测试 |
| [Stable Audio Tools](https://github.com/Stability-AI/stable-audio-tools) | 条件音频 diffusion、训练/推理、Gradio、inpaint 配置 | SFX/BGM 实验、私有素材训练研究 | prompt、训练配置、音频数据集 | 音频或模型 | `P2` | 代码和模型许可证分开；Stable Audio Open 权重商用需单独判断 |
| [Amphion](https://github.com/open-mmlab/Amphion) | 语音/歌声合成、VC/SVC、vocoder、评测框架 | 人声/歌声研究、声码器、评测 | 文本、音素、旋律、参考声线、配置 | 语音、歌声、转换音频、指标 | `P2` | 禁止未授权真实人声克隆；音乐 TTM 不作为首版主链路 |
| [Demucs](https://github.com/facebookresearch/demucs) | 音乐源分离、vocals/drums/bass/other stems | 参考分析、remix、数据清洗、分轨检查 | 音频 | vocals、drums、bass、other stems | `P0` | 分离 artifact 必须进入 QA；参考音频分轨不能被直接复制交付 |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | 音频转 MIDI、多音高转录、pitch bend | 哼唱/乐器录音转 MIDI、参考旋律分析、可编辑化 | 单乐器或干净 stem 音频 | MIDI、pitch bend | `P0` | 复杂混音先分轨再转录；转录结果只用于分析和原创改写 |
| [librosa](https://github.com/librosa/librosa) | BPM、beat、chroma、mel、MFCC、onset、HPSS、pitch/time shift | 音频分析、QA、可视化、预处理 | 音频 | 特征、节拍、频谱、调性辅助指标 | `P0` | 不作为版权结论或主观质量唯一依据 |
| [music21](https://github.com/cuthbertLab/music21) | 乐谱/符号音乐分析、和声、调性、MusicXML/MIDI | 乐理检查、和弦/旋律分析、乐谱导出 | MIDI、MusicXML、符号音符 | 调性、和声、乐谱结构 | `P0/P1` | 更适合符号层，不直接处理混音音频 |
| [Essentia](https://github.com/MTG/essentia) | 工业级音频描述符、key/onset/mood/similarity/classification | 音频标签、风格分析、检索、质量特征 | 音频 | spectral/temporal/tonal/high-level descriptors | `P1` | AGPL-3.0 合规风险高；需要独立服务、商业授权或替代方案 |
| [pretty_midi](https://github.com/craffel/pretty-midi) | MIDI 解析、编辑、转调、tempo/chroma、简单合成 | MIDI 清洗、结构编辑、导出前处理 | MIDI | notes、instruments、tempo、chroma、改写后 MIDI | `P0` | 复杂控制器事件可配合 mido/music21 |

## 4. Skills 目录

### 4.1 P0 基础设施 Skills

| Skill | 吸收来源 | 作用 | 首版落地 |
|---|---|---|---|
| `Audio Feature Analysis Skill` | librosa、Essentia 思路 | BPM、beat、key、chroma、onset、频谱、静音、响度辅助 | 先用 librosa 思路建数据字段；Essentia 等合规明确后再接 |
| `Stem Separation Skill` | Demucs | 分离人声、鼓、贝斯、其他 | 用于参考分析、QA、分轨交付检查 |
| `Audio To MIDI Skill` | Basic Pitch | 主旋律/乐器录音转 MIDI | 用于旋律可编辑化、参考分析、原创性检查 |
| `MIDI Editing Skill` | pretty_midi、music21 | MIDI 清洗、转调、结构分析、乐理规则 | 用于作曲、和声、旋律检查 |
| `Audio Watermark Skill` | AudioSeal | 生成音频水印和检测 | 用于 AI 生成声明和溯源治理 |
| `Delivery Metadata Skill` | 多项目通用 | 保存 prompt、seed、模型版本、授权字段 | 首版必须设计字段 |

### 4.2 P1 生成试点 Skills

| Skill | 吸收来源 | 作用 | 首版落地 |
|---|---|---|---|
| `Full Song Generation Skill` | ACE-Step、YuE、DiffRhythm | 生成完整歌曲候选 | 先做统一适配器，不绑定单一模型 |
| `Lyrics To Song Skill` | YuE、ACE-Step | 根据歌词生成成歌 | 只进入异步队列，必须过歌词和原创性检查 |
| `Instrumental BGM Skill` | DiffRhythm、ACE-Step | 纯音乐、短视频 BGM、游戏 BGM | 适合每日 10-20 条自动任务 |
| `Reference Style Transfer Skill` | YuE/ACE-Step/DiffRhythm 思路 | 从参考歌提取风格画像后生成原创 | 禁止复制旋律、歌词、声线 |
| `Music Continuation Skill` | YuE/DiffRhythm 思路 | 续写片段 | 仅对项目内已授权素材开放 |

### 4.3 P2 研发储备 Skills

| Skill | 吸收来源 | 作用 | 边界 |
|---|---|---|---|
| `Controllable Generation Skill` | JASCO | 和弦、鼓、旋律时间轴控制 | 先吸收接口设计和数据结构 |
| `Tokenizer Research Skill` | AudioCraft / EnCodec | 音频 token 化和模型服务设计 | 研发用途 |
| `Private Training Skill` | Stable Audio Tools、AudioCraft | 私有素材训练/微调 | 必须先解决数据授权 |
| `Vocal Research Skill` | Amphion | 歌声、人声、声码器、评测 | 禁止未授权声线克隆 |

## 5. 模型适配器设计

所有生成模型统一经过 `Generation Router`，禁止页面直接调用某个模型。

```ts
type GenerationRequest = {
  task_id: string;
  work_id: string;
  version_goal: string;
  mode: "full_song" | "instrumental" | "lyrics_to_song" | "continuation" | "edit" | "stem" | "midi";
  lyrics?: string;
  style_prompt: string;
  audience_profile: string;
  bpm?: number;
  key?: string;
  duration_sec: number;
  reference_profile_id?: string;
  hard_constraints: string[];
  forbidden_constraints: string[];
};
```

```ts
type GenerationResult = {
  provider: string;
  model_name: string;
  model_version: string;
  seed?: string;
  prompt_snapshot: string;
  audio_files: string[];
  stems?: string[];
  midi_files?: string[];
  logs: string[];
  license_notes: string[];
  risk_flags: string[];
};
```

## 6. 合规和授权门禁

生成结果进入交付前必须保存：

- 模型来源。
- 模型版本。
- 模型许可证或服务条款摘要。
- prompt 摘要。
- seed 或可复现参数。
- 参考素材摘要。
- 参考素材授权状态。
- 是否使用人声。
- 是否使用第三方 sample、loop、preset demo。
- AI 生成声明。
- 原创性检查结果。

不满足时：

- 可以留在作品库。
- 可以进入人工复核。
- 不能进入自动交付队列。

## 7. 第一阶段实际吸收范围

第一阶段不要求安装所有模型。先在网站和后端数据结构中预留这些能力：

- `Skill Registry`：记录每个 Skill 的来源、优先级、许可状态、是否启用。
- `Model Adapter Registry`：记录 ACE-Step、YuE、DiffRhythm 等适配器状态。
- `Audio Analysis Report`：记录 BPM、key、结构、响度、静音、clipping、loop 接缝。
- `MIDI Analysis Report`：记录音域、动机、重复、旋律轮廓、和声关系。
- `Rights Report`：记录原创性、参考相似、声线、采样、授权风险。

首版可以用 mock adapter 跑通流程，但字段必须按真实系统设计，避免后续推倒重来。
