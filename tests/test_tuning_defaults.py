from __future__ import annotations

import unittest

from korail_program.analysis.batch import BatchAnalysisConfig
from korail_program.cli import build_parser
from korail_program.config import DEFAULT_ANALYSIS_INTERVAL_SEC
from korail_program.core.models import RiskLevel
from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


class TuningDefaultsTests(unittest.TestCase):
    def test_default_interval_is_fifteen_seconds(self) -> None:
        self.assertEqual(DEFAULT_ANALYSIS_INTERVAL_SEC, 15.0)

    def test_batch_default_report_threshold_includes_low_risk(self) -> None:
        field = BatchAnalysisConfig.__dataclass_fields__["min_report_risk"]

        self.assertEqual(field.default, RiskLevel.LOW)

    def test_cli_defaults_match_gui_tuning(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["analyze-videos"])

        self.assertEqual(args.interval_sec, 15.0)
        self.assertEqual(RiskLevel.coerce(args.min_report_risk), RiskLevel.LOW)

    def test_prompt_keeps_uncertain_nearby_vegetation_as_watchlist(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("use 낮음 as a watchlist", JUDGE_SYSTEM_PROMPT)
        self.assertIn("Use 낮음, not 없음", prompt)

    def test_prompt_prefers_medium_for_uncertain_forward_corridor_clearance(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("Prefer recall at the 중간/낮음 boundary", JUDGE_SYSTEM_PROMPT)
        self.assertIn("distance, perspective, blur, or partial occlusion", prompt)
        self.assertIn("keep 중간 and set needs_human_review=true", prompt)


if __name__ == "__main__":
    unittest.main()
