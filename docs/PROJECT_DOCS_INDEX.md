# AI 音乐制作系统文档索引

## 1. 阅读顺序

1. [AI_MUSIC_PRODUCTION_PLAN.md](AI_MUSIC_PRODUCTION_PLAN.md)  
   总体定位：这是 AI 音乐制作系统，不是音乐分发平台。

2. [OPEN_SOURCE_SKILLS_ABSORPTION.md](OPEN_SOURCE_SKILLS_ABSORPTION.md)  
   外部开源项目 Skills 吸收：ACE-Step、YuE、DiffRhythm、AudioCraft、Demucs、Basic Pitch、librosa、music21 等。

3. [PROJECT_BASE_SKILLS.md](PROJECT_BASE_SKILLS.md)  
   项目长期基础 Skills：创作、生成、编辑、处理、验收、LOOP、授权、交付、自动化。

4. [AGENT_WORK_BREAKDOWN.md](AGENT_WORK_BREAKDOWN.md)  
   26 个细颗粒 Agent 的职责、输入、输出、禁止事项和交接验收。

5. [LOOP_STATE_MACHINE.md](LOOP_STATE_MACHINE.md)  
   制作 LOOP、状态机、返工决策树、失败原因、重试限制和每日产能闸门。

6. [QUALITY_ACCEPTANCE_SYSTEM.md](QUALITY_ACCEPTANCE_SYSTEM.md)  
   好音乐、朗朗上口、旋律、歌词、编曲、混音母带、受众、授权和网站 MVP 验收。

7. [AI_CREATION_ENGINE_SPEC.md](AI_CREATION_ENGINE_SPEC.md)  
   第一阶段创作引擎：AI 怎么创作、怎么剪辑、怎么处理、怎么下载。

8. [IMPLEMENTATION_AND_VALIDATION.md](IMPLEMENTATION_AND_VALIDATION.md)  
   网站工作台 MVP 分步实现与校验。

9. [PHASED_EXECUTION_PLAN.md](PHASED_EXECUTION_PLAN.md)  
   从创作引擎、网站、mock 自动任务、音频分析、模型适配、返工闭环到授权交付的阶段计划。

10. [REAL_PROVIDER_AND_DOCKER_RUNBOOK.md](REAL_PROVIDER_AND_DOCKER_RUNBOOK.md)  
    真实 SaaS/API provider、HTTP bridge、Docker 部署和本地/远程生成边界。

11. [LOCAL_MODEL_MUSICGEN_RUNBOOK.md](LOCAL_MODEL_MUSICGEN_RUNBOOK.md)  
    本地 MusicGen 模型接入：不需要 SaaS API Key，但需要 AudioCraft/PyTorch、模型权重、算力和许可证检查。

## 2. 当前项目边界

本项目做：

- AI 音乐制作。
- 自动每日制作任务。
- 多 Agent 协作。
- 多版本候选。
- LOOP 返工。
- 质量验收。
- 原创性和授权门禁。
- 作品库。
- 交付包。
- 授权配置。
- 可选外部平台连接配置。
- 长期基础 Skills。

本项目不做：

- 音乐分发平台。
- 音乐社区。
- 公开播放广场。
- 推荐流。
- 点赞评论。
- 粉丝关系。
- 未授权歌手克隆。
- 真实歌曲复刻。

## 3. 第一阶段验收

第一阶段先验收 AI 音乐创作引擎 MVP：

- 能创建音乐创作任务。
- 能生成结构化 brief。
- 能生成歌词或纯音乐结构。
- 能生成 3-5 个候选版本记录。
- 至少一个候选有可播放音频或下载 URL。
- 能下载生成音频。
- 能做基础剪辑：截取、淡入淡出、循环点、导出版。
- 能看到评分和返工建议。
- 授权缺失时阻断正式交付，但不阻断内部试听下载。

网站工作台验收是第二阶段：

- 网站能打开。
- 能看到每日任务。
- 能看到作品库。
- 能看到评分中心。
- 能看到交付与授权中心。
- 页面内容体现音乐制作流程。
- 交付与授权中心只做导出包、授权配置、文件规格、元数据、AI 声明和可选平台连接配置。

## 4. 关键执行原则

- 低分不等于重生。
- 返工必须按失败原因回流责任 Agent。
- 授权缺失不返工音乐，只阻断交付。
- 原创高风险不自动通过。
- 参考歌曲只能做风格画像，不能复制旋律、歌词或声线。
- 模型接入必须经过 `Generation Router`。
- 交付包必须经过最终 QA 和授权配置。
- 后续实现必须遵守项目根目录 [../AGENTS.md](../AGENTS.md)。

## 5. 当前代码入口

Phase 1 创作引擎 MVP 已开始落地：

- [../music_ai/engine.py](../music_ai/engine.py)：创作引擎核心。
- [../music_ai/audio.py](../music_ai/audio.py)：mock WAV 生成和基础剪辑处理。
- [../music_ai/models.py](../music_ai/models.py)：创作任务、候选版本、导出文件等数据模型。
- [../music_ai/cli.py](../music_ai/cli.py)：命令行 demo。
- [../music_ai/automation.py](../music_ai/automation.py)：每日自动制作批次、产能报告、返工队列。
- [../music_ai/web.py](../music_ai/web.py)：本地网站工作台和 API。
- [../tools/music_provider_adapter.py](../tools/music_provider_adapter.py)：真实 HTTP provider bridge。
- [../tools/musicgen_local_adapter.py](../tools/musicgen_local_adapter.py)：本地 AudioCraft/MusicGen adapter。
- [../tests/test_creation_engine.py](../tests/test_creation_engine.py)：Phase 1 验证测试。
- [../tests/test_web_workbench.py](../tests/test_web_workbench.py)：工作台 API 验证测试。

Demo 命令：

```powershell
python -m music_ai.cli demo --output runs\demo --duration 20
```

从 JSON 请求创建：

```powershell
python -m music_ai.cli create --request examples\creation_request.json --output runs\from_json --candidates 3
```

注册外部 AI 音乐下载 URL：

```powershell
python -m music_ai.cli import-url --request examples\creation_request.json --url https://example.test/generated.wav --duration 42 --output runs\external
```

每日自动生产：

```powershell
python -m music_ai.cli daily --output runs\daily --count 10 --candidates 3
```

处理返工队列：

```powershell
python -m music_ai.cli rework --output runs\daily --limit 5
```

测试命令：

```powershell
python -m unittest discover -s tests
```

工作台命令：

```powershell
python -m music_ai.web --host 127.0.0.1 --port 8787 --workspace runs\web
```
