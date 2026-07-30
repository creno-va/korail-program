from __future__ import annotations

import unittest

from korail_program.core.event_merger import merge_judge_observations
from korail_program.core.models import JudgeObservation, RiskLevel, SectionMapping


def judge_observation(
    time_ms: int,
    risk_level: RiskLevel,
    *,
    video_id: int = 1,
) -> JudgeObservation:
    return JudgeObservation(
        video_id=video_id,
        video_time_ms=time_ms,
        has_tree=risk_level is not RiskLevel.NONE,
        bamboo_likely=0.8,
        near_catenary=risk_level.priority >= 2,
        risk_level=risk_level,
        bbox_hint=None,
        evidence=f"{risk_level.value} 위험 근거",
        needs_human_review=False,
    )


class EventMergerTests(unittest.TestCase):
    def test_merge_contiguous_risky_frames(self) -> None:
        observations = [
            judge_observation(754000, RiskLevel.HIGH),
            judge_observation(755000, RiskLevel.HIGH),
            judge_observation(756000, RiskLevel.MEDIUM),
        ]
        sections = [
            SectionMapping(
                video_id=1,
                start_time_ms=700000,
                end_time_ms=790000,
                section_start="밀양강교",
                section_end="청도경계",
                confidence=0.9,
            )
        ]

        events = merge_judge_observations(observations, sections)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].risk_level, RiskLevel.HIGH)
        self.assertEqual(events[0].section_start, "밀양강교")
        self.assertEqual(events[0].section_end, "청도경계")
        self.assertEqual(events[0].source_observation_count, 3)

    def test_skip_short_uncertain_event(self) -> None:
        observation = JudgeObservation(
            video_id=1,
            video_time_ms=1000,
            has_tree=True,
            bamboo_likely=0.5,
            near_catenary=True,
            risk_level=RiskLevel.MEDIUM,
            bbox_hint=None,
            evidence="지속성 애매 이벤트",
            needs_human_review=True,
        )

        events = merge_judge_observations([observation], [])

        self.assertEqual(events, [])

    def test_keeps_events_separated_by_video(self) -> None:
        observations = [
            judge_observation(1000, RiskLevel.HIGH, video_id=1),
            judge_observation(1000, RiskLevel.HIGH, video_id=2),
        ]
        sections = [
            SectionMapping(
                video_id=1,
                start_time_ms=0,
                end_time_ms=5000,
                section_start="video-1-start",
                section_end="video-1-end",
                confidence=0.9,
            ),
            SectionMapping(
                video_id=2,
                start_time_ms=0,
                end_time_ms=5000,
                section_start="video-2-start",
                section_end="video-2-end",
                confidence=0.9,
            ),
        ]

        events = merge_judge_observations(observations, sections)

        self.assertEqual([event.video_id for event in events], [1, 2])
        self.assertEqual(events[0].section_start, "video-1-start")
        self.assertEqual(events[1].section_start, "video-2-start")


if __name__ == "__main__":
    unittest.main()
