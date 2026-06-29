# Local MusicGen Runbook

## Do you still need a real API key?

No, not for a local model.

There are two valid generation routes:

- Local model route: no SaaS API key. You need a compatible Python runtime, PyTorch, AudioCraft, model weights, compute resources, disk cache, and a license that allows your intended use.
- External provider route: API endpoint and key are required. This is still useful when the provider has better vocals, commercial rights, higher throughput, or hosted GPUs.

The project supports both through `Generation Router`. Local MusicGen is wired through `local_command`, not through a hard-coded provider SDK.

## What was learned from upstream projects

The local adapter is based on official AudioCraft/MusicGen behavior:

- AudioCraft provides MusicGen inference and training code.
- AudioCraft recommends Python 3.9, PyTorch 2.1.0, and ffmpeg.
- AudioCraft stores model weights through Hugging Face cache paths.
- AudioCraft code is MIT, but the released model weights are CC-BY-NC 4.0.
- Hugging Face lists `facebook/musicgen-small` as a text-to-audio/music model and also marks the license as CC-BY-NC 4.0.

That license is the reason this default local config is for internal validation, not commercial delivery.

## Local host run

Install runtime dependencies in a Python 3.9 environment:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install 'torch==2.1.0'
python -m pip install -U audiocraft
```

Generate one internal validation task:

```powershell
python -m music_ai.cli create `
  --request examples\creation_request.json `
  --output runs\musicgen_local `
  --candidates 3 `
  --provider-config examples\generation_providers.musicgen_local.json `
  --preferred-provider musicgen_local_small
```

If the request needs vocals, this provider will be rejected because this adapter is configured as instrumental-only.

## Docker local model run

This builds a heavier image with Python 3.9, ffmpeg, PyTorch, and AudioCraft:

```powershell
docker compose -f docker-compose.musicgen-local.yml up --build
```

Open:

```text
http://127.0.0.1:8787
```

The first generation can be slow because model weights are downloaded into `./models`.

## Commercial delivery rule

Do not mark output from `facebook/musicgen-small` as commercial-ready using the default license config.

For revenue workflows, use one of these:

- A provider/model with explicit commercial-use rights.
- Your own trained or licensed model weights.
- A paid service whose terms allow your target platform and monetization model.

The existing rights gate should remain enabled: missing or non-commercial license blocks formal delivery but still allows internal preview/download.
