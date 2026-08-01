"""HTML and Markdown report generation for batch video analysis."""

from __future__ import annotations

from html import escape
from pathlib import Path

from korail_program.core.event_merger import format_section_label
from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel
from korail_program.core.timecode import format_timecode


def write_reports(
    *,
    output_dir: Path,
    video_count: int,
    sampled_frame_count: int,
    suspicious_records: list[dict[str, object]],
    events: list[AnalysisEvent],
    failures: list[dict[str, object]],
    video_titles: list[str] | None = None,
    ocr_observation_count: int = 0,
    failure_summary: str | None = None,
) -> tuple[Path, Path, Path]:
    markdown_path = output_dir / "report.md"
    html_path = output_dir / "report.html"
    markdown_path.write_text(
        build_markdown_report(
            video_count=video_count,
            sampled_frame_count=sampled_frame_count,
            ocr_observation_count=ocr_observation_count,
            suspicious_records=suspicious_records,
            events=events,
            failures=failures,
            failure_summary=failure_summary,
        )
        + "\n",
        encoding="utf-8",
    )
    html_path.write_text(
        build_html_report(
            video_count=video_count,
            sampled_frame_count=sampled_frame_count,
            ocr_observation_count=ocr_observation_count,
            suspicious_records=suspicious_records,
            events=events,
            failures=failures,
            output_dir=output_dir,
            failure_summary=failure_summary,
        )
        + "\n",
        encoding="utf-8",
    )
    from korail_program.analysis.pdf_report import write_pdf_report

    pdf_path = write_pdf_report(
        output_dir=output_dir,
        video_count=video_count,
        sampled_frame_count=sampled_frame_count,
        suspicious_records=suspicious_records,
        events=events,
        failures=failures,
        video_titles=video_titles,
    )
    return markdown_path, html_path, pdf_path


def build_markdown_report(
    *,
    video_count: int,
    sampled_frame_count: int,
    suspicious_records: list[dict[str, object]],
    events: list[AnalysisEvent],
    failures: list[dict[str, object]],
    ocr_observation_count: int = 0,
    failure_summary: str | None = None,
) -> str:
    lines = [
        "# 지장수목 의심 프레임 분석 리포트",
        "",
        f"- 분석 영상: {video_count}개",
        f"- VQA 샘플 프레임: {sampled_frame_count}개",
        f"- OCR 역명 관측: {ocr_observation_count}개",
        f"- 의심 캡처: {len(suspicious_records)}개",
        f"- 병합 이벤트: {len(events)}건",
        f"- 처리 실패: {len(failures)}건",
        "",
    ]
    if failure_summary:
        lines.extend(["## 처리 상태", "", failure_summary, ""])

    lines.extend(
        [
            "## 이벤트 요약",
            "",
        ]
    )
    if not events:
        lines.append(
            "모델 호출 실패로 이벤트를 생성하지 못했습니다."
            if failure_summary
            else "분석 완료: 기준 위험도에 걸리는 의심 이벤트가 없습니다."
        )
    else:
        lines.extend(
            [
                "| 위험도 | 시작 | 종료 | 요약 | 캡처 |",
                "| --- | --- | --- | --- | ---: |",
            ]
        )
        for event in events:
            lines.append(
                "| "
                f"{event.risk_level.value} | "
                f"{format_timecode(event.start_time_ms)} | "
                f"{format_timecode(event.end_time_ms)} | "
                f"{format_section_label(event.section_start, event.section_end)}: "
                f"{event.summary} | "
                f"{event.capture_count} |"
            )

    lines.extend(["", "## 의심 프레임", ""])
    if not suspicious_records:
        lines.append("의심 프레임이 없습니다.")
    else:
        for record in suspicious_records:
            observation = record["observation"]
            assert isinstance(observation, JudgeObservation)
            capture = str(record.get("capture_path") or record["frame_path"])
            lines.extend(
                [
                    f"### {record['video_name']} / {format_timecode(observation.video_time_ms)}",
                    "",
                    f"- 위험도: {observation.risk_level.value}",
                    f"- 근거: {observation.evidence or '-'}",
                    f"- 캡처: `{capture}`",
                    "",
                ]
            )

    if failures:
        lines.extend(["", "## 처리 실패", ""])
        for failure in failures:
            lines.append(
                f"- {failure.get('video_name', '-')} / "
                f"{failure.get('frame_path', '-')}: {failure.get('error', '-')}"
            )

    return "\n".join(lines)


def build_html_report(
    *,
    video_count: int,
    sampled_frame_count: int,
    suspicious_records: list[dict[str, object]],
    events: list[AnalysisEvent],
    failures: list[dict[str, object]],
    output_dir: Path,
    ocr_observation_count: int = 0,
    failure_summary: str | None = None,
) -> str:
    event_rows = "\n".join(_event_row(event) for event in events)
    if not event_rows:
        empty_message = (
            "모델 호출 실패로 이벤트를 생성하지 못했습니다."
            if failure_summary
            else "분석 완료: 기준 위험도에 걸리는 의심 이벤트가 없습니다."
        )
        event_rows = f'<tr><td colspan="6" class="muted">{escape(empty_message)}</td></tr>'

    cards = "\n".join(_frame_card(record, output_dir=output_dir) for record in suspicious_records)
    if not cards:
        cards = '<p class="muted">의심 프레임이 없습니다.</p>'

    failure_summary_block = ""
    if failure_summary:
        failure_summary_block = (
            '<section class="notice error">'
            "<h2>처리 상태</h2>"
            f"<p>{escape(failure_summary)}</p>"
            "</section>"
        )

    failure_block = ""
    if failures:
        failure_items = "\n".join(
            "<li>"
            f"{escape(str(item.get('video_name', '-')))} / "
            f"{escape(str(item.get('frame_path', '-')))}: "
            f"{escape(str(item.get('error', '-')))}"
            "</li>"
            for item in failures
        )
        failure_block = f"<section><h2>처리 실패</h2><ul>{failure_items}</ul></section>"

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>지장수목 의심 프레임 분석 리포트</title>
  <style>
    body {{
      margin: 0;
      background: #f7f7f8;
      color: #202124;
      font-family: -apple-system, BlinkMacSystemFont, "Pretendard GOV", "Pretendard",
        "Malgun Gothic", sans-serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    h2 {{ margin: 28px 0 12px; font-size: 18px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin: 20px 0 28px;
    }}
    .metric, .frame-card {{
      background: #fff;
      border-radius: 8px;
      padding: 14px;
    }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 22px; }}
    table {{
      width: 100%; border-collapse: collapse; background: #fff;
      border-radius: 8px; overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px; border-bottom: 1px solid #eef0f2;
      text-align: left; vertical-align: top;
    }}
    th {{ background: #f1f2f4; font-weight: 700; }}
    .frames {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;
    }}
    .frame-card img {{ width: 100%; border-radius: 6px; background: #f1f2f4; }}
    .muted {{ color: #70757a; }}
    .chip {{
      display: inline-block; border-radius: 999px; padding: 2px 9px;
      font-size: 12px; font-weight: 700;
    }}
    .risk-high {{ background: #f8d7da; color: #842029; }}
    .risk-medium {{ background: #fff0cc; color: #7a4f00; }}
    .risk-low {{ background: #dff3e8; color: #0f5132; }}
    .notice {{
      border-radius: 8px;
      padding: 14px;
      margin: 0 0 20px;
      background: #fff0cc;
      color: #7a4f00;
    }}
    .notice.error {{ background: #f8d7da; color: #842029; }}
  </style>
</head>
<body>
<main>
  <h1>지장수목 의심 프레임 분석 리포트</h1>
  <p class="muted">샘플링된 영상 프레임을 GPT vision VQA로 판정한 결과입니다.</p>
  {failure_summary_block}
  <section class="summary">
    <div class="metric">분석 영상<strong>{video_count}</strong></div>
    <div class="metric">VQA 샘플 프레임<strong>{sampled_frame_count}</strong></div>
    <div class="metric">OCR 역명 관측<strong>{ocr_observation_count}</strong></div>
    <div class="metric">의심 캡처<strong>{len(suspicious_records)}</strong></div>
    <div class="metric">병합 이벤트<strong>{len(events)}</strong></div>
    <div class="metric">처리 실패<strong>{len(failures)}</strong></div>
  </section>
  <section>
    <h2>이벤트 요약</h2>
    <table>
      <thead><tr><th>위험도</th><th>시작</th><th>종료</th><th>구간</th><th>요약</th><th>캡처</th></tr></thead>
      <tbody>{event_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>의심 프레임</h2>
    <div class="frames">{cards}</div>
  </section>
  {failure_block}
</main>
</body>
</html>"""


def _event_row(event: AnalysisEvent) -> str:
    return (
        "<tr>"
        f"<td>{_risk_chip(event.risk_level)}</td>"
        f"<td>{format_timecode(event.start_time_ms)}</td>"
        f"<td>{format_timecode(event.end_time_ms)}</td>"
        f"<td>{escape(format_section_label(event.section_start, event.section_end))}</td>"
        f"<td>{escape(event.summary)}</td>"
        f"<td>{event.capture_count}</td>"
        "</tr>"
    )


def _frame_card(record: dict[str, object], *, output_dir: Path) -> str:
    observation = record["observation"]
    assert isinstance(observation, JudgeObservation)
    capture_path = Path(str(record.get("capture_path") or record["frame_path"]))
    image_src = escape(capture_path.relative_to(output_dir).as_posix())
    return (
        '<article class="frame-card">'
        f'<img src="{image_src}" alt="candidate frame">'
        f"<h3>{escape(str(record['video_name']))}</h3>"
        f'<p class="muted">{format_timecode(observation.video_time_ms)}</p>'
        f"<p>{_risk_chip(observation.risk_level)}</p>"
        f"<p>{escape(observation.evidence or '-')}</p>"
        "</article>"
    )


def _risk_chip(risk_level: RiskLevel) -> str:
    css = {
        RiskLevel.HIGH: "risk-high",
        RiskLevel.MEDIUM: "risk-medium",
        RiskLevel.LOW: "risk-low",
        RiskLevel.NONE: "",
    }[risk_level]
    return f'<span class="chip {css}">{escape(risk_level.value)}</span>'
