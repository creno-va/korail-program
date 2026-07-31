"""Custom GPT API settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from korail_program.app.widgets import ActionButton, StatusChip
from korail_program.config import DEFAULT_OPENAI_BASE_URL
from korail_program.judge.openai_client import OpenAIApiError, test_openai_connection
from korail_program.model_catalog import (
    MODEL_OPTIONS,
    ModelOption,
    SystemProfile,
    recommend_model,
    system_profile_label,
)


class ModelSettingsDialog(QDialog):
    settings_saved = Signal(str, str)

    def __init__(
        self,
        *,
        current_model: str,
        api_key: str,
        profile: SystemProfile,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_model = current_model
        self.profile = profile
        self.recommended = recommend_model(profile)
        self.setWindowTitle("GPT API 설정")
        self.setMinimumSize(660, 600)
        self._build_ui(api_key=api_key)

    def _build_ui(self, *, api_key: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("GPT API 설정")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(StatusChip(system_profile_label(self.profile), "neutral"))
        root.addLayout(header)

        api_card = QFrame()
        api_card.setObjectName("ModelCard")
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(16, 16, 16, 16)
        api_layout.setSpacing(12)

        api_top = QHBoxLayout()
        api_title = QLabel("API key")
        api_title.setObjectName("CardTitle")
        self.model_value_label = QLabel(self.current_model)
        self.model_value_label.setObjectName("Tiny")
        api_top.addWidget(api_title)
        api_top.addStretch(1)
        api_top.addWidget(StatusChip(self.current_model, "primary"))

        self.api_key_input = QLineEdit()
        self.api_key_input.setObjectName("TokenInput")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("OPENAI_API_KEY 또는 sk-... 키를 입력하세요")
        self.api_key_input.setText(api_key)

        api_help = QLabel(
            "저장한 키는 이 PC의 앱 설정 파일에만 보관되며 릴리즈나 리포트에는 기록되지 않습니다."
        )
        api_help.setObjectName("Tiny")
        api_help.setWordWrap(True)

        api_layout.addLayout(api_top)
        api_layout.addWidget(self.api_key_input)
        api_layout.addWidget(api_help)
        root.addWidget(api_card)

        scroll = QScrollArea()
        scroll.setObjectName("CardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("CardListContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        for option in MODEL_OPTIONS:
            content_layout.addWidget(self._model_card(option))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        close_button = ActionButton("닫기", icon_name="close")
        close_button.clicked.connect(self.reject)
        test_button = ActionButton("연결 테스트", icon_name="lan-connect")
        test_button.clicked.connect(self._test_connection)
        save_button = ActionButton("저장", icon_name="content-save-outline", tone="primary")
        save_button.clicked.connect(self._save)
        footer.addStretch(1)
        footer.addWidget(close_button)
        footer.addWidget(test_button)
        footer.addWidget(save_button)
        root.addLayout(footer)

    def _model_card(self, option: ModelOption) -> QFrame:
        card = QFrame()
        card.setObjectName("ModelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        name = QLabel(option.name)
        name.setObjectName("CardTitle")
        top.addWidget(name)
        top.addWidget(StatusChip(option.tier, "neutral"))
        if option.tag == self.recommended.tag:
            top.addWidget(StatusChip("기본 추천", "success"))
        if option.tag == self.current_model:
            top.addWidget(StatusChip("선택됨", "primary"))
        top.addStretch(1)

        meta = QLabel(f"{option.tag} / {option.size_label}")
        meta.setObjectName("Tiny")
        description = QLabel(option.description)
        description.setObjectName("PanelText")
        description.setWordWrap(True)

        actions = QHBoxLayout()
        actions.addStretch(1)
        select_button = ActionButton("선택", icon_name="check")
        select_button.clicked.connect(lambda tag=option.tag: self._select(tag))
        actions.addWidget(select_button)

        layout.addLayout(top)
        layout.addWidget(meta)
        layout.addWidget(description)
        layout.addLayout(actions)
        return card

    def _select(self, tag: str) -> None:
        self.current_model = tag
        self.model_value_label.setText(tag)

    def _save(self) -> None:
        self.settings_saved.emit(self.current_model, self.api_key_input.text().strip())
        self.accept()

    def _test_connection(self) -> None:
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API key 필요", "OpenAI API key를 먼저 입력하세요.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            test_openai_connection(
                base_url=DEFAULT_OPENAI_BASE_URL,
                api_key=api_key,
                model=self.current_model,
            )
        except OpenAIApiError as exc:
            QMessageBox.warning(self, "연결 실패", str(exc))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "연결 실패", str(exc))
        else:
            QMessageBox.information(
                self,
                "연결 성공",
                f"OpenAI API key와 {self.current_model} 모델 접근을 확인했습니다.",
            )
        finally:
            QApplication.restoreOverrideCursor()
