"""Embedded video playback widget for the analysis workspace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
)

from korail_program.app.widgets import ActionButton
from korail_program.core.timecode import format_timecode


class VideoPlayer(QFrame):
    """Small media player with play/pause and seek controls."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("VideoPlayer")
        self.source_path: Path | None = None

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.7)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget()
        self.video_widget.setObjectName("VideoSurface")
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.player.setVideoOutput(self.video_widget)

        self.placeholder = QLabel("왼쪽에서 영상을 선택하세요")
        self.placeholder.setObjectName("VideoPlaceholder")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)

        display = QFrame()
        display.setObjectName("VideoDisplay")
        self.surface_stack = QStackedLayout(display)
        self.surface_stack.setContentsMargins(0, 0, 0, 0)
        self.surface_stack.addWidget(self.video_widget)
        self.surface_stack.addWidget(self.placeholder)
        self.surface_stack.setCurrentWidget(self.placeholder)

        self.play_button = ActionButton(
            "재생",
            icon_name="play-circle-outline",
            tone="overlay",
            small=True,
        )
        self.play_button.clicked.connect(self.toggle_playback)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setObjectName("VideoSeekSlider")
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self.player.setPosition)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("VideoTimeLabel")

        self.controls_overlay = QFrame()
        self.controls_overlay.setObjectName("VideoControlsOverlay")
        controls = QVBoxLayout(self.controls_overlay)
        controls.setContentsMargins(14, 8, 14, 8)
        controls.setSpacing(3)
        controls.addWidget(self.seek_slider)

        playback_row = QHBoxLayout()
        playback_row.setContentsMargins(0, 0, 0, 0)
        playback_row.setSpacing(8)
        playback_row.addWidget(self.play_button)
        playback_row.addWidget(self.time_label)
        playback_row.addStretch(1)
        controls.addLayout(playback_row)
        self.controls_overlay.hide()

        surface = QFrame()
        surface.setObjectName("VideoSurfaceFrame")
        surface.setMinimumHeight(360)
        surface_layout = QGridLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)
        surface_layout.addWidget(display, 0, 0)
        surface_layout.addWidget(
            self.controls_overlay,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignBottom,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(surface, stretch=1)

        self.player.positionChanged.connect(self._update_position)
        self.player.durationChanged.connect(self._update_duration)
        self.player.playbackStateChanged.connect(self._sync_play_button)
        self.player.errorOccurred.connect(self._handle_error)
        self.play_button.setEnabled(False)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.controls_overlay.show()
        self.controls_overlay.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.controls_overlay.hide()
        super().leaveEvent(event)

    def set_video(self, path: Path) -> None:
        normalized = path.resolve()
        if normalized == self.source_path:
            return
        self.player.stop()
        self.source_path = normalized
        self.placeholder.setText("영상을 불러오는 중입니다…")
        self.surface_stack.setCurrentWidget(self.video_widget)
        self.player.setSource(QUrl.fromLocalFile(str(normalized)))
        self.play_button.setEnabled(True)
        self.seek_slider.setValue(0)
        self._sync_play_button(self.player.playbackState())

    def clear(self) -> None:
        self.player.stop()
        self.player.setSource(QUrl())
        self.source_path = None
        self.seek_slider.setRange(0, 0)
        self.time_label.setText("00:00 / 00:00")
        self.placeholder.setText("왼쪽에서 영상을 선택하세요")
        self.surface_stack.setCurrentWidget(self.placeholder)
        self.play_button.setEnabled(False)
        self._sync_play_button(QMediaPlayer.PlaybackState.StoppedState)

    def toggle_playback(self) -> None:
        if self.source_path is None:
            return
        if self.player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek(self, position_ms: int) -> None:
        if self.source_path is None:
            return
        self.player.setPosition(max(0, position_ms))

    def _update_position(self, position_ms: int) -> None:
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position_ms)
        self._update_time_label(position_ms, self.player.duration())

    def _update_duration(self, duration_ms: int) -> None:
        self.seek_slider.setRange(0, max(0, duration_ms))
        self._update_time_label(self.player.position(), duration_ms)

    def _update_time_label(self, position_ms: int, duration_ms: int) -> None:
        current = format_timecode(max(0, position_ms))
        duration = format_timecode(max(0, duration_ms))
        self.time_label.setText(f"{current} / {duration}")

    def _sync_play_button(self, state: QMediaPlayer.PlaybackState) -> None:
        if state is QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("일시정지")
            self.play_button.set_icon("pause-circle-outline")
            return
        self.play_button.setText("재생")
        self.play_button.set_icon("play-circle-outline")

    def _handle_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        self.placeholder.setText(f"영상을 재생할 수 없습니다.\n{message}")
        self.surface_stack.setCurrentWidget(self.placeholder)
