# AI 音乐制作项目

本项目目标是实现可长期自动运行的 AI 音乐制作系统。当前方向是音乐创作、剪辑、质量验收、返工、下载和授权交付，不是音乐分发平台。

## 当前能力

- 创建 AI 音乐制作任务。
- 生成结构化 brief。
- 每个任务生成 3-5 个候选版本。
- 生成可播放、可下载的 mock WAV 音频。
- 注册外部 AI 音乐下载 URL，并进入同一套作品库、QA、授权流程。
- 基础剪辑：trim、fade、loop。
- 基础处理：peak normalize、silence trim。
- 导出 preview、master、short cut、loop、license pack。
- 授权缺失时阻断 master 正式交付，授权配置后解除阻断。
- 授权完成后生成交付包 ZIP，包含 master、preview、license pack、metadata、acceptance report、manifest、lyrics。
- 分项质量验收：音频质量、旋律、朗朗上口、结构、编曲、歌词可唱性、受众匹配、原创安全、交付准备。
- WAV 音频分析：采样率、峰值、RMS、估算 LUFS、剪辑风险、首尾静音、静音比例。
- Skills/Agent 注册表：17 个基础 Skills、26 个生产 Agent、LOOP 返工规则。
- Generation Router：支持默认 mock 生成和 `local_command` 本地模型/脚本适配，生成结果统一进入 QA、授权和交付流程。
- Provider 能力表：用 JSON 描述生成器支持的类型、人声/纯音乐能力、最大时长、优先级和本地命令。
- 生成路由解释：每个候选记录 `generation_route.selection`，包含选中 provider、选择原因和候选 provider 评估。
- 每日自动生成 10-20 条任务，每条 3-5 个候选，并生成日报。
- 自动返工队列根据 failure code 定向回流到责任 Agent。
- LOOP 预算控制：同一源版本最多自动返工 2 次，同一根任务最多自动返工 3 次，返工历史写入结果和日报。

## 常用命令

```powershell
python -m music_ai.cli demo --output runs\demo --duration 20
python -m music_ai.cli demo --output runs\demo_rights --duration 12 --configure-rights
python -m music_ai.cli create --request examples\creation_request.json --output runs\from_json --candidates 3
python -m music_ai.cli import-url --request examples\creation_request.json --url https://example.test/generated.wav --duration 42 --output runs\external
python -m music_ai.cli daily --output runs\daily --count 10 --candidates 3
python -m music_ai.cli schedule --output runs\daily --count 10 --candidates 3 --rework-limit 5 --run-hour 1 --run-minute 30
python -m music_ai.cli rework --output runs\daily --limit 5
python -m music_ai.cli skills
python -m music_ai.cli create --request examples\creation_request.json --output runs\delivery --candidates 3 --configure-rights --package
python -m music_ai.cli package --output runs\delivery --task-id <task_id>
```

本地模型/脚本生成入口：

```powershell
python -m music_ai.cli create --request examples\creation_request.json --output runs\local_model --candidates 3 --generation-provider local_command --local-command-json "@local_command.json" --model-name my-local-model --model-version v1
```

`local_command.json` 是 JSON 数组，支持占位符：

```json
["python", "my_generator.py", "{output_path}", "{duration_sec}", "{bpm}"]
```

本地命令必须把音频写到 `{output_path}`。生成后的音频不会直接交付，会继续进入音频分析、质量评分、授权和交付包流程。

Provider 能力表入口：

```powershell
python -m music_ai.cli create --request examples\creation_request.json --output runs\provider_config --candidates 3 --provider-config examples\generation_providers.json
python -m music_ai.cli daily --output runs\provider_daily --count 10 --candidates 3 --provider-config examples\generation_providers.json
```

本地 MusicGen 验证入口：

```powershell
python -m music_ai.cli create --request examples\creation_request.json --output runs\musicgen_local --candidates 3 --provider-config examples\generation_providers.musicgen_local.json --preferred-provider musicgen_local_small
```

`facebook/musicgen-small` 默认配置只用于内部验证。它不需要 SaaS API Key，但需要本地 AudioCraft/PyTorch/模型权重，并且模型权重许可证不是默认商用交付许可证。

真实 SaaS/API 入口：

```powershell
$env:MUSIC_AI_PROVIDER_ENDPOINT="https://your-provider-or-bridge.example/generate"
$env:MUSIC_AI_PROVIDER_API_KEY="your-key"
python -m music_ai.cli create --request examples\creation_request.json --output runs\real_provider --candidates 3 --provider-config examples\generation_providers.real_http.json --preferred-provider real_http_music_provider
```

能力表字段包括：

- `id`
- `provider`
- `model_name`
- `model_version`
- `enabled`
- `priority`
- `supported_modes`
- `supports_vocals`
- `supports_instrumental`
- `max_duration_sec`
- `command`
- `timeout_sec`

每日自动化日报会输出：

- `provider_usage`
- `route_summary`
- `rework_budget`

用于判断每天实际用了哪些生成器、选择原因是什么、是否存在 provider 能力不匹配。

## 本地工作台

```powershell
python -m music_ai.web --host 127.0.0.1 --port 8787 --workspace runs\web
```

打开：

```text
http://127.0.0.1:8787
```

工作台包含四个核心区：

- 每日任务
- 作品库
- 评分中心
- 交付与授权

侧边栏可手动创建任务，也可触发“自动生成10条”和“处理返工”。这些动作调用创作引擎和自动化服务，不是发布平台功能。

## API

- `GET /api/tasks`
- `GET /api/rework-history`
- `GET /api/skills`
- `POST /api/create`
- `POST /api/import-url`
- `POST /api/automation/daily`
- `POST /api/automation/rework`
- `POST /api/tasks/{task_id}/configure-rights`
- `POST /api/tasks/{task_id}/delivery-package`

## Docker

轻量 mock/工作台：

```powershell
docker compose up --build
```

真实 SaaS/API：

```powershell
docker compose -f docker-compose.real-provider.yml up --build
```

本地 MusicGen：

```powershell
docker compose -f docker-compose.musicgen-local.yml up --build
```

本地 MusicGen 镜像会安装 AudioCraft/PyTorch，并把模型缓存挂载到 `models`。首次生成会下载权重，耗时和显存/内存取决于机器。

## 测试

```powershell
python -m unittest discover -s tests
```

当前验收要求：

- 网站可打开。
- 能看到每日任务、作品库、评分中心、交付与授权。
- 自动任务能生成 10 条任务、30 个候选。
- 每个候选有总分、分项评分和质量报告。
- 授权缺失不触发音乐返工，只阻断正式交付。
- 授权完整后可以生成可下载交付包 ZIP。
- Skills/Agent/LOOP 规则可通过 CLI 和 Web API 查询。

## 项目规则

- 执行规则见 [AGENTS.md](AGENTS.md)。
- 基础 Skills 见 [docs/PROJECT_BASE_SKILLS.md](docs/PROJECT_BASE_SKILLS.md)。
- 创作引擎规格见 [docs/AI_CREATION_ENGINE_SPEC.md](docs/AI_CREATION_ENGINE_SPEC.md)。
