from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from korail_program.judge.gemma_client import build_ollama_chat_payload, encode_image_base64
from korail_program.judge.prompts import build_frame_judge_prompt


class GemmaClientTests(unittest.TestCase):
    def test_build_ollama_chat_payload(self) -> None:
        payload = build_ollama_chat_payload(
            model="gemma3:4b",
            prompt=build_frame_judge_prompt(route_hint="경부선 상행"),
            image_b64="abc123",
        )

        self.assertEqual(payload["model"], "gemma3:4b")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        messages = payload["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["images"], ["abc123"])
        self.assertIn("경부선 상행", messages[1]["content"])

    def test_encode_image_base64(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "image.bin"
            image_path.write_bytes(b"abc")

            self.assertEqual(encode_image_base64(image_path), "YWJj")


if __name__ == "__main__":
    unittest.main()
