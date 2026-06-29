from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic HTTP music provider adapter for local_command routing")
    parser.add_argument("--output", required=True, help="Target audio file path to create")
    parser.add_argument("--duration-sec", required=True, type=int)
    parser.add_argument("--bpm", required=True, type=int)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--version-id", required=True)
    parser.add_argument("--key-index", required=True, type=int)
    parser.add_argument("--endpoint", default=os.environ.get("MUSIC_AI_PROVIDER_ENDPOINT"))
    parser.add_argument("--api-key", default=os.environ.get("MUSIC_AI_PROVIDER_API_KEY"))
    parser.add_argument("--timeout-sec", type=int, default=int(os.environ.get("MUSIC_AI_PROVIDER_TIMEOUT", "120")))
    parser.add_argument("--poll-interval-sec", type=float, default=float(os.environ.get("MUSIC_AI_PROVIDER_POLL_INTERVAL", "5")))
    args = parser.parse_args()

    if not args.endpoint:
        raise SystemExit("MUSIC_AI_PROVIDER_ENDPOINT or --endpoint is required")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "prompt": args.prompt,
        "duration_sec": args.duration_sec,
        "bpm": args.bpm,
        "version_id": args.version_id,
        "key_index": args.key_index,
        "output_format": output.suffix.lstrip(".") or "wav",
    }
    response = _request_json("POST", args.endpoint, payload, args.api_key, args.timeout_sec)
    final = _wait_for_audio_response(response, args.api_key, args.timeout_sec, args.poll_interval_sec)
    _write_audio(final, output, args.api_key, args.timeout_sec)
    print(json.dumps({"output": str(output), "bytes": output.stat().st_size}, ensure_ascii=False))


def _request_json(method: str, url: str, payload: dict[str, object] | None, api_key: str | None, timeout_sec: int) -> dict[str, object]:
    data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_sec) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"provider HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"provider request failed: {exc}") from exc
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("provider response must be a JSON object")
    return parsed


def _wait_for_audio_response(
    response: dict[str, object],
    api_key: str | None,
    timeout_sec: int,
    poll_interval_sec: float,
) -> dict[str, object]:
    if response.get("audio_url") or response.get("audio_base64"):
        return response
    status_url = response.get("status_url") or response.get("poll_url")
    if not status_url:
        raise RuntimeError("provider response must include audio_url, audio_base64, status_url, or poll_url")

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        status = _request_json("GET", str(status_url), None, api_key, timeout_sec)
        state = str(status.get("status") or status.get("state") or "").lower()
        if status.get("audio_url") or status.get("audio_base64"):
            return status
        if state in {"failed", "error", "canceled", "cancelled"}:
            raise RuntimeError(f"provider job failed: {json.dumps(status, ensure_ascii=False)}")
        time.sleep(poll_interval_sec)
    raise TimeoutError("provider job did not produce audio before timeout")


def _write_audio(response: dict[str, object], output: Path, api_key: str | None, timeout_sec: int) -> None:
    audio_base64 = response.get("audio_base64")
    if audio_base64:
        output.write_bytes(base64.b64decode(str(audio_base64)))
        return

    audio_url = response.get("audio_url")
    if not audio_url:
        raise RuntimeError("final provider response did not include audio_url or audio_base64")
    headers = {}
    if api_key and bool(response.get("audio_url_requires_auth", False)):
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(str(audio_url), headers=headers, method="GET")
    with urlopen(request, timeout=timeout_sec) as audio_response:
        output.write_bytes(audio_response.read())


if __name__ == "__main__":
    main()

