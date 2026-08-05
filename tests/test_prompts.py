from __future__ import annotations

import unittest

from korail_program.judge.harness import harness_for_model
from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


class PromptTests(unittest.TestCase):
    def test_frame_judge_prompt_excludes_background_greenery(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("Green color by itself is not", JUDGE_SYSTEM_PROMPT)
        self.assertIn("Ignore continuous background scenery", prompt)
        self.assertIn("physical gap or overlap", prompt)

    def test_frame_judge_prompt_prefers_recall_for_uncertain_corridor(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("entire visible track corridor", JUDGE_SYSTEM_PROMPT)
        self.assertIn("Prefer medium at the medium/low boundary", prompt)
        self.assertIn("blur, distance, perspective or occlusion", prompt)
        self.assertIn(
            "actual image pixel coordinates", harness_for_model("qwen3-vl:4b").judge_suffix
        )


if __name__ == "__main__":
    unittest.main()
