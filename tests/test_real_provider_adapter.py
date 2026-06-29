from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from music_ai.audio import analyze_wav, generate_mock_wav


class RealProviderAdapterTest(unittest.TestCase):
    def test_adapter_writes_audio_from_http_base64_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.wav"
            target = Path(temp_dir) / "target.wav"
            generate_mock_wav(source, 1, 100)
            audio_base64 = base64.b64encode(source.read_bytes()).decode("ascii")

            class Handler(BaseHTTPRequestHandler):
                def do_POST(self) -> None:
                    _ = self.rfile.read(int(self.headers.get("content-length", "0")))
                    body = json.dumps({"audio_base64": audio_base64}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, format: str, *args) -> None:
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "tools/music_provider_adapter.py",
                        "--endpoint",
                        f"http://{host}:{port}/generate",
                        "--output",
                        str(target),
                        "--duration-sec",
                        "1",
                        "--bpm",
                        "100",
                        "--prompt",
                        "test prompt",
                        "--version-id",
                        "v1",
                        "--key-index",
                        "0",
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(target.exists())
            self.assertGreater(target.stat().st_size, 0)
            self.assertAlmostEqual(analyze_wav(target)["duration_sec"], 1, delta=0.1)


if __name__ == "__main__":
    unittest.main()

