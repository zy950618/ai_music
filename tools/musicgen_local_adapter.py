from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Local MusicGen adapter for local_command routing")
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration-sec", required=True, type=int)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="facebook/musicgen-small")
    parser.add_argument("--device", default=None, help="Optional torch device, for example cuda or cpu")
    args = parser.parse_args()

    try:
        from audiocraft.data.audio import audio_write
        from audiocraft.models import MusicGen
    except ImportError as exc:
        raise SystemExit(
            "MusicGen local adapter requires optional dependencies. "
            "Install AudioCraft/PyTorch in the runtime image or host environment first."
        ) from exc

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    model = MusicGen.get_pretrained(args.model, device=args.device)
    model.set_generation_params(duration=args.duration_sec)
    wav = model.generate([args.prompt])[0].cpu()
    sample_rate = model.sample_rate
    stem = output.with_suffix("")
    audio_write(str(stem), wav, sample_rate, strategy="loudness", loudness_compressor=True)
    generated = stem.with_suffix(".wav")
    if generated != output:
        generated.replace(output)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
