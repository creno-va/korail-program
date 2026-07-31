from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from korail_program import runtime


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_discovers_bundled_ffmpeg_runtime_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ffmpeg = root / "runtime" / "ffmpeg" / "bin" / "ffmpeg"
            ffprobe = root / "runtime" / "ffmpeg" / "bin" / "ffprobe"
            for executable in (ffmpeg, ffprobe):
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"")

            with patch.object(runtime, "application_root", return_value=root):
                self.assertEqual(runtime.bundled_ffmpeg_executable(), ffmpeg)
                self.assertEqual(runtime.bundled_ffprobe_executable(), ffprobe)


if __name__ == "__main__":
    unittest.main()
