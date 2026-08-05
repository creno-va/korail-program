from __future__ import annotations

import unittest

from korail_program.judge.harness import build_task_payload, harness_for_model
from korail_program.judge.ollama_client import (
    build_ollama_chat_payload,
    extract_ollama_message_content,
)


class OllamaClientTests(unittest.TestCase):
    def test_qwen_harness_uses_deterministic_grounding_prompt(self) -> None:
        payload = build_task_payload(
            model="qwen3-vl:4b",
            task="judge",
            image_b64="aW1hZ2U=",
        )

        self.assertEqual(payload["model"], "qwen3-vl:4b")
        self.assertIsInstance(payload["format"], dict)
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["temperature"], 0.0)
        self.assertIn("Qwen visual grounding", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][1]["images"], ["aW1hZ2U="])

    def test_gemma4_harness_uses_family_sampling_parameters(self) -> None:
        payload = build_task_payload(
            model="gemma4:e4b",
            task="judge",
            image_b64="aW1hZ2U=",
        )

        self.assertEqual(harness_for_model("gemma4:e4b").family, "gemma4")
        self.assertEqual(payload["options"]["temperature"], 1.0)
        self.assertEqual(payload["options"]["top_p"], 0.95)
        self.assertIn("Gemma 4 instruction", payload["messages"][1]["content"])

    def test_each_catalog_size_gets_a_specialized_harness(self) -> None:
        tags = (
            "qwen3-vl:2b",
            "qwen3-vl:4b",
            "qwen3-vl:8b",
            "gemma4:e2b",
            "gemma4:e4b",
            "gemma4:12b",
        )

        suffixes = {harness_for_model(tag).judge_suffix for tag in tags}
        token_limits = {
            tag: harness_for_model(tag).options["num_predict"] for tag in tags
        }
        self.assertEqual(len(suffixes), len(tags))
        self.assertEqual(token_limits["qwen3-vl:2b"], 320)
        self.assertEqual(token_limits["gemma4:12b"], 512)

    def test_custom_payload_keeps_structured_image_request(self) -> None:
        payload = build_ollama_chat_payload(
            model="qwen3-vl:2b",
            prompt="custom prompt",
            image_b64="aW1hZ2U=",
            options={"temperature": 0.2},
        )

        self.assertEqual(payload["messages"][1]["content"], "custom prompt")
        self.assertEqual(payload["options"], {"temperature": 0.2})

    def test_extracts_chat_message_content(self) -> None:
        body = {"message": {"role": "assistant", "content": '{"risk_level":"low"}'}}

        self.assertEqual(extract_ollama_message_content(body), '{"risk_level":"low"}')


if __name__ == "__main__":
    unittest.main()
