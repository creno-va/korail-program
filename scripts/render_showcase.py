"""Render reproducible portfolio screenshots from the real Qt interface."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from korail_program.app.fonts import configure_app_font
from korail_program.app.main_window import MainWindow
from korail_program.app.widgets import EventCard


def _render(window: MainWindow, target: Path, app: QApplication) -> None:
    app.processEvents()
    if not window.grab().save(str(target)):
        raise RuntimeError(f"Failed to save screenshot: {target}")


def _populate_videos(window: MainWindow, root: Path) -> list[Path]:
    videos = [
        root / "경부선_서울-대전_전차선로_점검.mp4",
        root / "호남선_익산-정읍_주행영상.mp4",
        root / "중앙선_제천-원주_점검.mp4",
    ]
    for index, path in enumerate(videos, start=1):
        path.write_bytes(b"0" * (index * 1024 * 1024))

    window.video_player.set_video = lambda _path: None  # type: ignore[method-assign]
    window.add_video_files(videos)
    return list(window._analysis_cards)


def _prepare_home(window: MainWindow) -> None:
    window.home_page.set_progress(68, "primary")
    window.home_page.set_analysis_action(
        text="분석 정지",
        icon="stop-circle-outline",
        tone="error",
        tooltip="현재 분석 중지",
        enabled=True,
    )


def _prepare_detail(window: MainWindow, videos: list[Path], scene_path: Path) -> None:
    selected = videos[0]
    window._show_detail_page()
    window._selected_video_path = selected
    window.selected_video_title.setText(selected.name)
    window.selected_video_meta.setText("1.0 MB · 경부선 서울–대전 구간 · 2026-07-31 14:20")

    states = (
        (videos[0], "완료", "success", "분석 완료", 100),
        (videos[1], "완료", "success", "분석 완료", 100),
        (videos[2], "대기", "neutral", "분석 대기", 0),
    )
    for path, status, tone, stage, progress in states:
        card = window._analysis_cards[path]
        card.set_state(status, tone, stage, progress)
        card.set_finished()

    window.session_chip.setText("분석 완료")
    window.session_chip.set_tone("success")
    window._set_analysis_progress(100, "success")
    window.analysis_stage_label.setText("리포트 생성 완료 · 탐지 프레임 3건")
    window.event_count_chip.setText("3건")
    window.event_count_chip.set_tone("success")
    for key, value in {
        "processed": "1,248",
        "suspicious": "7",
        "events": "3",
        "failures": "0",
    }.items():
        window.stat_values[key].setText(value)

    events = (
        {
            "start_time_ms": 81_000,
            "end_time_ms": 89_000,
            "frame_time_ms": 84_000,
            "risk_level": "높음",
            "section_start": "서울",
            "section_end": "영등포",
            "summary": "우측 수목 가지가 전차선 가동 범위에 근접해 즉시 현장 확인이 필요합니다.",
            "review_status": "우선 검수",
        },
        {
            "start_time_ms": 164_000,
            "end_time_ms": 172_000,
            "frame_time_ms": 168_000,
            "risk_level": "중간",
            "section_start": "영등포",
            "section_end": "수원",
            "summary": "선로 우측 수관이 급전선 방향으로 성장해 예방 전정 검토가 필요합니다.",
            "review_status": "검수 대기",
        },
        {
            "start_time_ms": 248_000,
            "end_time_ms": 256_000,
            "frame_time_ms": 252_000,
            "risk_level": "낮음",
            "section_start": "수원",
            "section_end": "평택",
            "summary": "측면 식생이 시설 한계 바깥에 있으나 추후 성장 여부를 관찰해야 합니다.",
            "review_status": "검수 대기",
        },
    )
    window.events_list.clear_cards()
    window._event_payloads.clear()
    for index, payload in enumerate(events, start=1):
        window._event_payloads[index] = payload
        window.events_list.add_card(
            index,
            EventCard(payload, video_name=selected.name, capture_path=scene_path),
        )

    window.video_player.source_path = selected
    window.events_list.select_key(1)

    scene = QPixmap(str(scene_path))
    window.video_player.surface_stack.setCurrentWidget(window.video_player.placeholder)
    window.video_player.placeholder.setText("")
    window.video_player.placeholder.setPixmap(
        scene.scaled(
            window.video_player.placeholder.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
    )
    window.video_player.play_button.setEnabled(True)
    window.video_player.seek_slider.setRange(0, 360_000)
    window.video_player.seek_slider.setValue(84_000)
    window.video_player.time_label.setText("01:24 / 06:00")
    window.video_player.controls_overlay.show()
    window.video_player.controls_overlay.raise_()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scene", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    configure_app_font(app)
    with tempfile.TemporaryDirectory(prefix="korail-showcase-") as tmp_dir:
        window = MainWindow()
        window.resize(1480, 920)
        window.show()
        videos = _populate_videos(window, Path(tmp_dir))
        _prepare_home(window)
        _render(window, args.output_dir / "korail-main-page.png", app)
        _prepare_detail(window, videos, args.scene)
        _render(window, args.output_dir / "korail-detail-page.png", app)
        window.close()


if __name__ == "__main__":
    main()
