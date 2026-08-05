from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from korail_program import runtime


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_discovers_bundled_runtime_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ollama = root / "runtime" / "ollama" / "ollama"
            llama_server = root / "runtime" / "ollama" / "lib" / "ollama" / "llama-server"
            ffmpeg = root / "runtime" / "ffmpeg" / "bin" / "ffmpeg"
            ffprobe = root / "runtime" / "ffmpeg" / "bin" / "ffprobe"
            for executable in (ollama, llama_server, ffmpeg, ffprobe):
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"")

            with patch.object(runtime, "application_root", return_value=root):
                self.assertEqual(runtime.bundled_ollama_executable(), ollama)
                self.assertEqual(runtime.bundled_ollama_server_executable(), llama_server)
                self.assertTrue(runtime.bundled_ollama_runtime_ready())
                self.assertEqual(runtime.bundled_ffmpeg_executable(), ffmpeg)
                self.assertEqual(runtime.bundled_ffprobe_executable(), ffprobe)

    def test_app_uses_isolated_model_directory_and_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            with patch.object(runtime, "user_data_dir", return_value=data_dir):
                env = runtime.ollama_process_environment()

            self.assertEqual(env["OLLAMA_MODELS"], str(data_dir / "ollama" / "models"))
            self.assertEqual(env["OLLAMA_HOST"], "127.0.0.1:11435")
            self.assertEqual(env["OLLAMA_NO_CLOUD"], "1")

    def test_accepts_executable_only_macos_ollama_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ollama = root / "runtime" / "ollama" / "ollama"
            ollama.parent.mkdir(parents=True, exist_ok=True)
            ollama.write_bytes(b"")

            with (
                patch.object(runtime, "application_root", return_value=root),
                patch.object(runtime.os, "name", "posix"),
            ):
                self.assertEqual(runtime.bundled_ollama_executable(), ollama)
                self.assertTrue(runtime.bundled_ollama_runtime_ready())


if __name__ == "__main__":
    unittest.main()
