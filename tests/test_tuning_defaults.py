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

    def test_prompt_keeps_visible_clearance_as_low_risk_watchlist(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("Green color by itself", JUDGE_SYSTEM_PROMPT)
        self.assertIn("specific trackside plant merits monitoring", prompt)

    def test_prompt_prefers_medium_for_uncertain_forward_corridor_clearance(self) -> None:
        prompt = build_frame_judge_prompt()

        self.assertIn("downgraded only because it is distant", JUDGE_SYSTEM_PROMPT)
        self.assertIn("Prefer medium at the medium/low boundary", prompt)
        self.assertIn("blur, distance, perspective or occlusion", prompt)


if __name__ == "__main__":
    unittest.main()
