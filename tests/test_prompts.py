from __future__ import annotations

import unittest

from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


class PromptTests(unittest.TestCase):
    def test_frame_judge_prompt_excludes_background_greenery(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("Do not raise risk for green pixels alone", prompt)
        self.assertIn("background mountains", prompt)
        self.assertIn("distant forest", prompt)
        self.assertIn("downgrade", prompt)
        self.assertIn("distant forest, or mountains", JUDGE_SYSTEM_PROMPT)

    def test_frame_judge_prompt_is_sensitive_to_distant_corridor_vegetation(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("sparse samples", prompt)
        self.assertIn("must not be treated as safe", prompt)
        self.assertIn("At the 중간/낮음 boundary, choose 중간", prompt)
        self.assertIn("Do not require contact or a large foreground appearance", prompt)
        self.assertIn("Camera distance alone is never", JUDGE_SYSTEM_PROMPT)
        self.assertIn("safe clearance gap cannot be confirmed", JUDGE_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
