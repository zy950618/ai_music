# Real Provider and Docker Runbook

## What "real provider through Generation Router" means

The production engine does not hard-code one music model.

It routes each creation job through `Generation Router`, which can call:

- `mock`: internal deterministic WAV generator for validation.
- `local_command`: any external command that writes an audio file to `{output_path}`.

The real-world integration path is:

```text
CreationEngine
  -> Generation Router
  -> local_command
  -> tools/music_provider_adapter.py
  -> your real AI music API or local inference server
  -> output WAV file
  -> audio analysis
  -> quality scoring
  -> LOOP rework
  -> rights configuration
  -> delivery package
```

This keeps real model integration separate from QA, LOOP, authorization, and delivery.

## What you need to provide

For a real SaaS/API provider:

- Provider account.
- API endpoint that can generate music from prompt/duration/BPM.
- API key or token.
- Confirmation that the provider license allows your target use.
- Expected response format, or a small bridge service that adapts the provider response to this project contract.

For a local model:

- A local command or server that can generate audio.
- The command must write the final audio file to `{output_path}`.
- The generated file should be WAV if possible.
- No SaaS API key is required, but the runtime still needs model weights, dependencies, compute resources, and a license that allows the intended use.

## Generic HTTP provider contract

`tools/music_provider_adapter.py` sends:

```json
{
  "prompt": "generation prompt",
  "duration_sec": 30,
  "bpm": 120,
  "version_id": "v1_xxxxxx",
  "key_index": 0,
  "output_format": "wav"
}
```

The provider or bridge can return one of these:

```json
{"audio_url": "https://.../result.wav"}
```

```json
{"audio_base64": "UklGR..."}
```

```json
{"status_url": "https://.../jobs/123"}
```

If a `status_url` or `poll_url` is returned, the adapter polls until the status response includes `audio_url` or `audio_base64`.

## Local run with real provider adapter

PowerShell:

```powershell
$env:MUSIC_AI_PROVIDER_ENDPOINT="https://your-provider-or-bridge.example/generate"
$env:MUSIC_AI_PROVIDER_API_KEY="your-key"
python -m music_ai.cli create `
  --request examples\creation_request.json `
  --output runs\real_provider `
  --candidates 3 `
  --provider-config examples\generation_providers.real_http.json `
  --preferred-provider real_http_music_provider
```

## Docker mock deployment

```powershell
docker compose up --build
```

Open:

```text
http://127.0.0.1:8787
```

## Docker real-provider deployment

PowerShell:

```powershell
$env:MUSIC_AI_PROVIDER_ENDPOINT="https://your-provider-or-bridge.example/generate"
$env:MUSIC_AI_PROVIDER_API_KEY="your-key"
docker compose -f docker-compose.real-provider.yml up --build
```

Open:

```text
http://127.0.0.1:8787
```

## Docker local MusicGen deployment

This route uses local AudioCraft/MusicGen through `tools/musicgen_local_adapter.py`.

```powershell
docker compose -f docker-compose.musicgen-local.yml up --build
```

Open:

```text
http://127.0.0.1:8787
```

This does not require a SaaS API key. It does require a larger Python/PyTorch/AudioCraft image and model weight download into `./models`.

For CLI validation:

```powershell
python -m music_ai.cli create `
  --request examples\creation_request.json `
  --output runs\musicgen_local `
  --candidates 3 `
  --provider-config examples\generation_providers.musicgen_local.json `
  --preferred-provider musicgen_local_small
```

The default `facebook/musicgen-small` provider is configured as instrumental-only and internal-validation-only because its released model weights are not a default commercial delivery license.

## What is already real versus still pending

Already implemented:

- Real provider adapter contract.
- Local MusicGen adapter config and Docker deployment template.
- Local-command routing.
- Docker web deployment.
- Docker real-provider deployment template.
- Audio analysis, scoring, LOOP, manual rework, rights, and delivery after generation.

Still requires your provider-specific decision:

- Which model/provider to use.
- Whether the provider supports vocals, stems, duration, and commercial rights.
- The provider endpoint and API key.
- Any provider-specific polling or output conversion differences not covered by the generic contract.
