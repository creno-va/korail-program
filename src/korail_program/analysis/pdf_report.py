"""Printable PDF report with one suspicious frame per page."""

from __future__ import annotations

from datetime import datetime
from html import escape
from importlib import resources
from pathlib import Path
from unicodedata import normalize

from korail_program.core.event_merger import format_section_label
from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel
from korail_program.core.timecode import format_timecode

_FONT_REGULAR = "PretendardGOV-PDF-Regular"
_FONT_SEMIBOLD = "PretendardGOV-PDF-SemiBold"


def write_pdf_report(
    *,
    output_dir: Path,
    video_count: int,
    sampled_frame_count: int,
    suspicious_records: list[dict[str, object]],
    events: list[AnalysisEvent],
    failures: list[dict[str, object]],
    video_titles: list[str] | None = None,
) -> Path:
    """Write a cover followed by one page for every suspicious frame."""

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - dependency is part of packaged app
        raise RuntimeError(
            "PDF 리포트 생성에 reportlab이 필요합니다. 앱을 다시 설치해 주세요."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "report.pdf"
    _register_fonts()

    document = canvas.Canvas(str(pdf_path), pagesize=A4, pageCompression=1)
    document.setTitle("지장수목 의심 프레임 분석 리포트")
    document.setAuthor("전차선로 지장수목 분석")
    document.setCreator("Korail Analyzer")
    document.setSubject("영상 기반 전차선로 지장수목 분석 결과")

    normalized_titles = _video_titles(video_titles, suspicious_records)
    _draw_cover_page(
        document,
        video_titles=normalized_titles,
        video_count=video_count,
        sampled_frame_count=sampled_frame_count,
        suspicious_frame_count=len(suspicious_records),
        events=events,
        failure_count=len(failures),
    )
    document.showPage()

    total_pages = len(suspicious_records)
    if suspicious_records:
        for page_number, record in enumerate(suspicious_records, start=1):
            _draw_frame_page(
                document,
                record=record,
                events=events,
                page_number=page_number,
                total_pages=total_pages,
                video_count=video_count,
                sampled_frame_count=sampled_frame_count,
                failure_count=len(failures),
            )
            document.showPage()
    else:
        _draw_empty_page(
            document,
            video_count=video_count,
            sampled_frame_count=sampled_frame_count,
            event_count=len(events),
            failure_count=len(failures),
        )
        document.showPage()

    document.save()
    return pdf_path


def _register_fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_root = resources.files("korail_program.assets.fonts")
    font_files = {
        _FONT_REGULAR: "PretendardGOV-Regular.ttf",
        _FONT_SEMIBOLD: "PretendardGOV-SemiBold.ttf",
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name, file_name in font_files.items():
        if font_name in registered:
            continue
        with resources.as_file(font_root.joinpath(file_name)) as font_path:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def _draw_cover_page(
    document,
    *,
    video_titles: list[str],
    video_count: int,
    sampled_frame_count: int,
    suspicious_frame_count: int,
    events: list[AnalysisEvent],
    failure_count: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    page_width, page_height = A4
    margin = 20 * mm
    content_width = page_width - (margin * 2)

    document.setFillColor(HexColor("#3182f6"))
    document.roundRect(margin, page_height - (28 * mm), 18 * mm, 3 * mm, 1.5 * mm, fill=1, stroke=0)

    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 26)
    document.drawString(margin, page_height - (50 * mm), "전차선로 지장수목")
    document.drawString(margin, page_height - (62 * mm), "분석 리포트")

    document.setFillColor(HexColor("#6b7684"))
    document.setFont(_FONT_REGULAR, 11)
    document.drawString(
        margin,
        page_height - (74 * mm),
        "영상 프레임 분석 결과와 OCR 기반 추정 구간을 정리한 보고서입니다.",
    )
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    document.setFont(_FONT_REGULAR, 9)
    document.drawString(margin, page_height - (83 * mm), f"생성 일시  {generated_at}")

    metrics = (
        ("분석 영상", f"{video_count}개"),
        ("샘플 프레임", f"{sampled_frame_count}개"),
        ("의심 프레임", f"{suspicious_frame_count}개"),
        ("탐지 이벤트", f"{len(events)}건"),
    )
    metric_gap = 4 * mm
    metric_width = (content_width - metric_gap) / 2
    for index, (label, value) in enumerate(metrics):
        row, column = divmod(index, 2)
        _draw_metric_tile(
            document,
            x=margin + (column * (metric_width + metric_gap)),
            y=page_height - ((112 + (row * 27)) * mm),
            width=metric_width,
            label=label,
            value=value,
        )

    document.setFillColor(HexColor("#333d4b"))
    document.setFont(_FONT_SEMIBOLD, 11)
    document.drawString(margin, 142 * mm, "분석 영상")
    _draw_cover_list(
        document,
        values=video_titles or ["영상 정보 없음"],
        x=margin,
        top_y=134 * mm,
        width=content_width,
        max_items=4,
    )

    section_labels = list(
        dict.fromkeys(
            format_section_label(event.section_start, event.section_end) for event in events
        )
    )
    document.setFillColor(HexColor("#333d4b"))
    document.setFont(_FONT_SEMIBOLD, 11)
    document.drawString(margin, 84 * mm, "OCR 추정 구간")
    _draw_cover_list(
        document,
        values=section_labels or ["구간 미확인"],
        x=margin,
        top_y=76 * mm,
        width=content_width,
        max_items=3,
    )

    document.setFillColor(HexColor("#8b95a1"))
    document.setFont(_FONT_REGULAR, 8)
    document.drawString(
        margin,
        17 * mm,
        f"처리 실패 {failure_count}건  ·  구간 정보는 영상 OCR 관측을 기반으로 한 추정값입니다.",
    )


def _draw_metric_tile(
    document,
    *,
    x: float,
    y: float,
    width: float,
    label: str,
    value: str,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    document.setFillColor(HexColor("#f2f4f6"))
    document.roundRect(x, y, width, 22 * mm, 7, fill=1, stroke=0)
    document.setFillColor(HexColor("#6b7684"))
    document.setFont(_FONT_REGULAR, 9)
    document.drawString(x + (5 * mm), y + (14 * mm), label)
    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 16)
    document.drawString(x + (5 * mm), y + (5 * mm), value)


def _draw_cover_list(
    document,
    *,
    values: list[str],
    x: float,
    top_y: float,
    width: float,
    max_items: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    visible = values[:max_items]
    if len(values) > max_items:
        visible.append(f"외 {len(values) - max_items}개")
    for index, value in enumerate(visible):
        y = top_y - (index * 9 * mm)
        document.setFillColor(HexColor("#3182f6"))
        document.circle(x + (1.5 * mm), y + (1.3 * mm), 1.2 * mm, fill=1, stroke=0)
        document.setFillColor(HexColor("#4e5968"))
        document.setFont(_FONT_REGULAR, 10)
        document.drawString(
            x + (6 * mm),
            y,
            _fit_text(
                _normalize_pdf_text(value),
                font_name=_FONT_REGULAR,
                font_size=10,
                max_width=width - (6 * mm),
            ),
        )


def _draw_frame_page(
    document,
    *,
    record: dict[str, object],
    events: list[AnalysisEvent],
    page_number: int,
    total_pages: int,
    video_count: int,
    sampled_frame_count: int,
    failure_count: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader

    page_width, page_height = A4
    margin = 15 * mm
    content_width = page_width - (margin * 2)

    observation = record.get("observation")
    if not isinstance(observation, JudgeObservation):
        raise TypeError("PDF frame record requires a JudgeObservation")
    event = _matching_event(events, observation)
    video_name = _fit_text(
        _normalize_pdf_text(record.get("video_name", "영상")),
        font_name=_FONT_SEMIBOLD,
        font_size=11,
        max_width=100 * mm,
    )

    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 18)
    document.drawString(margin, page_height - (18 * mm), "지장수목 의심 프레임")

    page_text = f"{page_number} / {total_pages}"
    document.setFont(_FONT_REGULAR, 9)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawRightString(page_width - margin, page_height - (17.5 * mm), page_text)

    meta_y = page_height - (25 * mm)
    _draw_label_value(
        document,
        x=margin,
        y=meta_y,
        label="영상 파일",
        value=video_name,
        max_width=100 * mm,
    )
    time_text = format_timecode(observation.video_time_ms)
    _draw_label_value(
        document,
        x=margin + (112 * mm),
        y=meta_y,
        label="재생 시점",
        value=time_text,
    )
    document.setFont(_FONT_REGULAR, 9)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawRightString(page_width - margin, meta_y, "위험도")
    _draw_risk_chip(
        document,
        risk_level=observation.risk_level,
        right_x=page_width - margin,
        center_y=meta_y - (5 * mm),
    )

    image_x = margin
    image_y = 138 * mm
    image_width = content_width
    image_height = 112 * mm
    document.setFillColor(HexColor("#f2f4f6"))
    document.roundRect(image_x, image_y, image_width, image_height, 8, fill=1, stroke=0)

    capture_path = Path(str(record.get("capture_path") or record.get("frame_path") or ""))
    try:
        image = ImageReader(str(capture_path))
        source_width, source_height = image.getSize()
        scale = min(image_width / source_width, image_height / source_height)
        draw_width = source_width * scale
        draw_height = source_height * scale
        document.drawImage(
            image,
            image_x + ((image_width - draw_width) / 2),
            image_y + ((image_height - draw_height) / 2),
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:  # noqa: BLE001
        document.setFont(_FONT_REGULAR, 10)
        document.setFillColor(HexColor("#8b95a1"))
        document.drawCentredString(
            page_width / 2,
            image_y + (image_height / 2),
            "캡처 이미지를 불러올 수 없습니다.",
        )

    section = (
        format_section_label(event.section_start, event.section_end)
        if event is not None
        else "구간 미확인"
    )
    review_status = event.review_status.value if event is not None else "미확인"
    detail_y = 124 * mm
    _draw_label_value(
        document,
        x=margin,
        y=detail_y,
        label="OCR 추정 구간",
        value=section,
        max_width=118 * mm,
    )
    _draw_label_value(
        document,
        x=page_width - margin - (48 * mm),
        y=detail_y,
        label="검수 상태",
        value=review_status,
    )

    document.setFont(_FONT_SEMIBOLD, 10)
    document.setFillColor(HexColor("#333d4b"))
    document.drawString(margin, 108 * mm, "판단 근거")
    _draw_paragraph(
        document,
        text=observation.evidence or "판단 근거 없음",
        x=margin,
        top_y=101 * mm,
        width=content_width,
        max_height=54 * mm,
    )

    footer_text = (
        f"분석 영상 {video_count}개  ·  샘플 프레임 {sampled_frame_count}개"
        f"  ·  의심 프레임 {total_pages}개  ·  처리 실패 {failure_count}건"
    )
    document.setFont(_FONT_REGULAR, 8)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawString(margin, 14 * mm, footer_text)


def _draw_empty_page(
    document,
    *,
    video_count: int,
    sampled_frame_count: int,
    event_count: int,
    failure_count: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    page_width, page_height = A4
    margin = 20 * mm
    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 20)
    document.drawString(margin, page_height - (24 * mm), "지장수목 분석 리포트")

    document.setFillColor(HexColor("#f2f4f6"))
    document.roundRect(
        margin,
        page_height - (108 * mm),
        page_width - (margin * 2),
        58 * mm,
        10,
        fill=1,
        stroke=0,
    )
    document.setFillColor(HexColor("#333d4b"))
    document.setFont(_FONT_SEMIBOLD, 14)
    document.drawCentredString(
        page_width / 2,
        page_height - (76 * mm),
        "의심 프레임이 없습니다.",
    )
    summary = (
        f"분석 영상 {video_count}개  ·  샘플 프레임 {sampled_frame_count}개  ·  "
        f"이벤트 {event_count}건  ·  처리 실패 {failure_count}건"
    )
    document.setFont(_FONT_REGULAR, 10)
    document.setFillColor(HexColor("#6b7684"))
    document.drawCentredString(page_width / 2, page_height - (88 * mm), summary)


def _draw_risk_chip(document, *, risk_level: RiskLevel, right_x: float, center_y: float) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth

    background, foreground = {
        RiskLevel.HIGH: ("#feecef", "#d33b4c"),
        RiskLevel.MEDIUM: ("#fff4e5", "#b25d00"),
        RiskLevel.LOW: ("#e8f8f2", "#008f6a"),
        RiskLevel.NONE: ("#f2f4f6", "#6b7684"),
    }[risk_level]
    text = risk_level.value
    chip_width = stringWidth(text, _FONT_SEMIBOLD, 9) + (7 * mm)
    chip_height = 7 * mm
    chip_x = right_x - chip_width
    chip_y = center_y - (chip_height / 2)
    document.setFillColor(HexColor(background))
    document.roundRect(chip_x, chip_y, chip_width, chip_height, chip_height / 2, fill=1, stroke=0)
    document.setFillColor(HexColor(foreground))
    document.setFont(_FONT_SEMIBOLD, 9)
    document.drawCentredString(chip_x + (chip_width / 2), chip_y + (2.2 * mm), text)


def _draw_label_value(
    document,
    *,
    x: float,
    y: float,
    label: str,
    value: str,
    max_width: float | None = None,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    document.setFont(_FONT_REGULAR, 9)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawString(x, y, label)
    document.setFont(_FONT_SEMIBOLD, 10)
    document.setFillColor(HexColor("#333d4b"))
    normalized_value = _normalize_pdf_text(value)
    fitted_value = (
        _fit_text(
            normalized_value,
            font_name=_FONT_SEMIBOLD,
            font_size=10,
            max_width=max_width,
        )
        if max_width is not None
        else normalized_value
    )
    document.drawString(x, y - (6 * mm), fitted_value)


def _draw_paragraph(
    document,
    *,
    text: str,
    x: float,
    top_y: float,
    width: float,
    max_height: float,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    normalized_text = _normalize_pdf_text(text).strip()
    if len(normalized_text) > 420:
        normalized_text = normalized_text[:419].rstrip() + "…"
    normalized_text = "<br/>".join(escape(line) for line in normalized_text.splitlines())
    paragraph = Paragraph(
        normalized_text,
        ParagraphStyle(
            "FrameEvidence",
            fontName=_FONT_REGULAR,
            fontSize=10,
            leading=16,
            textColor=HexColor("#4e5968"),
            splitLongWords=True,
            spaceAfter=0,
        ),
    )
    _, paragraph_height = paragraph.wrap(width, max_height)
    paragraph.drawOn(document, x, top_y - min(paragraph_height, max_height))


def _matching_event(
    events: list[AnalysisEvent], observation: JudgeObservation
) -> AnalysisEvent | None:
    return next(
        (
            event
            for event in events
            if event.video_id == observation.video_id
            and event.start_time_ms <= observation.video_time_ms <= event.end_time_ms
        ),
        None,
    )


def _video_titles(
    video_titles: list[str] | None,
    suspicious_records: list[dict[str, object]],
) -> list[str]:
    candidates: list[object] = list(video_titles or [])
    if not candidates:
        candidates.extend(record.get("video_name") for record in suspicious_records)
    normalized_titles = [_normalize_pdf_text(value).strip() for value in candidates]
    return list(dict.fromkeys(title for title in normalized_titles if title))


def _normalize_pdf_text(value: object) -> str:
    if isinstance(value, bytes):
        for encoding in ("utf-8", "cp949", "latin-1"):
            try:
                return normalize("NFC", value.decode(encoding))
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace")

    text = normalize("NFC", str(value or ""))
    if text and not any("가" <= character <= "힣" for character in text):
        try:
            repaired = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        else:
            if any("가" <= character <= "힣" for character in repaired):
                text = repaired
    return text


def _fit_text(text: str, *, font_name: str, font_size: float, max_width: float) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = _normalize_pdf_text(text)
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    ellipsis = "…"
    available = max_width - stringWidth(ellipsis, font_name, font_size)
    fitted: list[str] = []
    for character in text:
        candidate = "".join((*fitted, character))
        if stringWidth(candidate, font_name, font_size) > available:
            break
        fitted.append(character)
    return "".join(fitted).rstrip() + ellipsis
