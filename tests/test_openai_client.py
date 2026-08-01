from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from korail_program.judge.openai_client import (
    build_openai_responses_payload,
    encode_image_data_url,
    extract_openai_output_text,
)
from korail_program.judge.openai_client import (
    test_openai_connection as verify_openai_connection,
)
from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


class OpenAIClientTests(unittest.TestCase):
    def test_build_openai_responses_payload(self) -> None:
        payload = build_openai_responses_payload(
            model="gpt-5.6-terra",
            system_prompt=JUDGE_SYSTEM_PROMPT,
            prompt=build_frame_judge_prompt(route_hint="경부선 상행"),
            image_data_url="data:image/jpeg;base64,abc123",
            image_detail="original",
            reasoning_effort="none",
            temperature=None,
            max_output_tokens=900,
        )

        self.assertEqual(payload["model"], "gpt-5.6-terra")
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["max_output_tokens"], 900)
        self.assertEqual(payload["reasoning"], {"effort": "none"})
        self.assertEqual(payload["text"], {"format": {"type": "json_object"}})
        messages = payload["input"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["content"][1]["type"], "input_image")
        self.assertEqual(messages[1]["content"][1]["image_url"], "data:image/jpeg;base64,abc123")
        self.assertEqual(messages[1]["content"][1]["detail"], "original")
        self.assertIn("경부선 상행", messages[1]["content"][0]["text"])

    def test_extract_openai_output_text(self) -> None:
        body = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"risk_level":"low"}'}],
                }
            ]
        }

        self.assertEqual(extract_openai_output_text(body), '{"risk_level":"low"}')

    def test_legacy_model_payload_skips_reasoning(self) -> None:
        payload = build_openai_responses_payload(
            model="gpt-4.1-mini",
            system_prompt="system",
            prompt="prompt",
            image_data_url="data:image/jpeg;base64,abc123",
            image_detail="original",
            reasoning_effort="low",
            temperature=0.0,
            max_output_tokens=900,
        )

        self.assertNotIn("reasoning", payload)
        self.assertEqual(payload["temperature"], 0.0)
        self.assertEqual(payload["input"][1]["content"][1]["detail"], "high")

    def test_encode_image_data_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "image.jpg"
            image_path.write_bytes(b"abc")

            self.assertEqual(encode_image_data_url(image_path), "data:image/jpeg;base64,YWJj")

    def test_openai_connection_uses_selected_model_endpoint(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return b'{"id":"gpt-5.6-terra"}'

        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
            body = verify_openai_connection(
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                model="gpt-5.6-terra",
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(body["id"], "gpt-5.6-terra")
        self.assertEqual(request.full_url, "https://api.openai.com/v1/models/gpt-5.6-terra")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")


if __name__ == "__main__":
    unittest.main()
