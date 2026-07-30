from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from korail_program import runtime


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_discovers_bundled_unix_runtime_layout(self) -> None:
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

    def test_discovers_ollama_app_resource_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            resources = root / "runtime" / "ollama" / "Ollama.app" / "Contents" / "Resources"
            ollama = resources / "ollama"
            llama_server = resources / "lib" / "ollama" / "llama-server"
            for executable in (ollama, llama_server):
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"")

            with patch.object(runtime, "application_root", return_value=root):
                self.assertEqual(runtime.bundled_ollama_executable(), ollama)
                self.assertEqual(runtime.bundled_ollama_server_executable(), llama_server)
                self.assertTrue(runtime.bundled_ollama_runtime_ready())

    def test_accepts_macos_ollama_executable_without_server_layout(self) -> None:
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
