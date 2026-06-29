from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class LocalMusicGenAdapterTest(unittest.TestCase):
    def test_help_does_not_require_optional_musicgen_dependencies(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/musicgen_local_adapter.py", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Local MusicGen adapter", completed.stdout)


if __name__ == "__main__":
    unittest.main()
