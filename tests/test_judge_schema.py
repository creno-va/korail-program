from __future__ import annotations

import unittest

from korail_program.core.models import RiskLevel
from korail_program.judge.schema import judge_observation_from_text, parse_judge_json


class JudgeSchemaTests(unittest.TestCase):
    def test_parse_fenced_json(self) -> None:
        payload = parse_judge_json(
            """```json
            {"risk_level": "상", "has_tree": true}
            ```"""
        )
        self.assertEqual(payload["risk_level"], "상")

    def test_judge_observation_from_text(self) -> None:
        observation = judge_observation_from_text(
            video_id=1,
            video_time_ms=754000,
            text="""
            {
              "has_tree": true,
              "bamboo_likely": 0.82,
              "near_catenary": true,
              "risk_level": "상",
              "bbox_hint": [920, 180, 1240, 620],
              "evidence": "우측 전차선로 주변에 수목이 근접해 보임",
              "needs_human_review": false
            }
            """,
        )
        self.assertEqual(observation.risk_level, RiskLevel.HIGH)
        self.assertEqual(observation.bbox_hint, (920, 180, 1240, 620))
        self.assertFalse(observation.needs_human_review)


if __name__ == "__main__":
    unittest.main()

