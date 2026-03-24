from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class MainWindowUiMixin:
    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        header = QFrame(root)
        header.setProperty("panel", True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(10)

        title_block = QVBoxLayout()
        app_title = QLabel("MacroPad Controller")
        app_title.setObjectName("AppTitle")
        app_subtitle = QLabel("Qt Widgets controller shell")
        app_subtitle.setObjectName("AppSubtitle")
        title_block.addWidget(app_title)
        title_block.addWidget(app_subtitle)

        self._port_combo = QComboBox()
        self._port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._port_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._port_combo.setMinimumContentsLength(10)
        self._port_combo.setMinimumWidth(70)
        self._hint_edit = QLineEdit()
        self._hint_edit.setPlaceholderText("Hint substring, e.g. Curiosity / Microchip")
        self._hint_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hint_edit.setMinimumWidth(70)
        self._baud_spin = QSpinBox()
        self._baud_spin.setRange(300, 1_000_000)
        self._baud_spin.setMaximumWidth(110)
        self._profile_spin = QSpinBox()
        self._profile_spin.setRange(1, 10)
        self._profile_spin.setMaximumWidth(72)
        self._audio_output_combo = QComboBox()
        self._audio_output_combo.setMinimumWidth(200)
        self._audio_output_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._audio_output_refresh_button = QPushButton("Refresh Audio")
        self._audio_output_refresh_button.setMaximumWidth(120)
        self._auto_connect_check = QCheckBox("Auto connect")
        self._learn_mode_check = QCheckBox("Learn mode")
        self._state_label = self._pill("State: disconnected")
        self._connect_toggle_button = QPushButton("Connect")
        self._exit_button = QPushButton("Exit")

        summary_row.addLayout(title_block, 0)
        summary_row.addWidget(QLabel("Port"))
        summary_row.addWidget(self._port_combo, 1)
        summary_row.addWidget(QLabel("Hint"))
        summary_row.addWidget(self._hint_edit, 1)
        summary_row.addWidget(QLabel("Baud"))
        summary_row.addWidget(self._baud_spin)
        summary_row.addWidget(QLabel("Profile"))
        summary_row.addWidget(self._profile_spin)
        summary_row.addWidget(QLabel("Audio Out"))
        summary_row.addWidget(self._audio_output_combo, 1)
        summary_row.addWidget(self._audio_output_refresh_button)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addWidget(self._auto_connect_check)
        actions_row.addWidget(self._learn_mode_check)
        actions_row.addStretch(1)
        actions_row.addWidget(self._state_label, 0, Qt.AlignmentFlag.AlignRight)
        actions_row.addWidget(self._connect_toggle_button)
        actions_row.addWidget(self._exit_button)
        self._header_collapse_button = QToolButton(header)
        self._header_collapse_button.setObjectName("HeaderCollapseButton")
        self._header_collapse_button.setAutoRaise(True)
        self._header_collapse_button.setCursor(Qt.PointingHandCursor)
        self._header_collapse_button.setText("▴")
        self._header_collapse_button.setToolTip("Collapse connection bar")
        self._header_collapse_button.setFixedSize(28, 18)
        self._header_collapse_button.clicked.connect(self._toggle_header_panel)
        actions_row.addWidget(self._header_collapse_button)

        header_layout.addLayout(summary_row)
        header_layout.addLayout(actions_row)
        self._header_panel = header
        self._header_expanded = True

        self._header_toggle_row = QFrame(root)
        self._header_toggle_row.setObjectName("HeaderToggleRow")
        self._header_toggle_row.setFixedHeight(14)
        toggle_layout = QHBoxLayout(self._header_toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)
        toggle_layout.addStretch(1)
        self._header_reopen_button = QToolButton(self._header_toggle_row)
        self._header_reopen_button.setObjectName("HeaderToggleButton")
        self._header_reopen_button.setAutoRaise(True)
        self._header_reopen_button.setCursor(Qt.PointingHandCursor)
        self._header_reopen_button.setText("▾")
        self._header_reopen_button.setToolTip("Expand connection bar")
        self._header_reopen_button.setFixedSize(28, 12)
        self._header_reopen_button.clicked.connect(self._toggle_header_panel)
        toggle_layout.addWidget(self._header_reopen_button, 0, Qt.AlignmentFlag.AlignHCenter)
        toggle_layout.addStretch(1)
        self._header_toggle_row.setStyleSheet(
            """
            QFrame#HeaderToggleRow {
                background: transparent;
                border-top: 1px solid rgba(127, 127, 127, 0.45);
            }
            QToolButton#HeaderToggleButton {
                border: none;
                background: transparent;
                padding: 0;
            }
            QToolButton#HeaderToggleButton:hover {
                color: #38BDF8;
            }
            """
        )

        content = QFrame(root)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self._nav = QListWidget(content)
        self._nav.setObjectName("SideNav")
        self._nav.setFixedWidth(140)
        self._nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav.addItems(["Controller", "Scripts", "Profiles", "Personalization", "Stats", "Setup"])
        self._nav.currentRowChanged.connect(self._on_nav_changed)

        self._stack = QStackedWidget(content)
        self.controller_page = self._controller_page_cls(self.controller)
        self.scripts_page = self._scripts_page_cls(self.controller)
        self.profiles_page = self._profiles_page_cls(self.controller)
        self.setup_page = self._setup_page_cls(self.controller)
        self.personalization_page = self._personalization_page_cls(on_theme_applied=self._apply_theme_settings)
        self.stats_page = self._stats_page_cls(self.controller)
        self._stack.addWidget(self.controller_page)
        self._stack.addWidget(self.scripts_page)
        self._stack.addWidget(self.profiles_page)
        self._stack.addWidget(self.personalization_page)
        self._stack.addWidget(self.stats_page)
        self._stack.addWidget(self.setup_page)
        content_layout.addWidget(self._nav, 0)
        content_layout.addWidget(self._stack, 1)

        root_layout.addWidget(header, 0)
        root_layout.addWidget(self._header_toggle_row, 0)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        self._status_message = QLabel()
        self._status_message.setObjectName("StatusMessage")
        self._hidden_label = QLabel("Visible startup")
        self._hidden_label.setObjectName("StatusPill")
        status.addWidget(self._status_message, 1)
        status.addPermanentWidget(self._hidden_label)

        self._connect_toggle_button.clicked.connect(self._on_connect_toggle_clicked)
        self._exit_button.clicked.connect(self.request_exit)
        self._port_combo.currentIndexChanged.connect(self._on_port_changed)
        self._hint_edit.textChanged.connect(self._on_hint_changed)
        self._baud_spin.valueChanged.connect(self._on_baud_changed)
        self._profile_spin.valueChanged.connect(self._on_profile_changed)
        self._audio_output_combo.currentIndexChanged.connect(self._on_audio_output_changed)
        self._audio_output_refresh_button.clicked.connect(self._refresh_audio_outputs)
        self._auto_connect_check.toggled.connect(self._on_auto_connect_toggled)
        self._learn_mode_check.toggled.connect(self._on_header_learn_mode_toggled)

        learn_changed = getattr(self.controller_page, "learnModeChanged", None)
        if learn_changed is not None and hasattr(learn_changed, "connect"):
            learn_changed.connect(self._on_page_learn_mode_toggled)
        self._set_header_panel_expanded(True)

    def _toggle_header_panel(self) -> None:
        self._set_header_panel_expanded(not bool(getattr(self, "_header_expanded", True)))

    def _set_header_panel_expanded(self, expanded: bool) -> None:
        expanded_value = bool(expanded)
        self._header_expanded = expanded_value
        if hasattr(self, "_header_panel"):
            self._header_panel.setVisible(expanded_value)
        if hasattr(self, "_header_toggle_row"):
            self._header_toggle_row.setVisible(not expanded_value)
        if hasattr(self, "_header_collapse_button"):
            self._header_collapse_button.setVisible(expanded_value)
            self._header_collapse_button.setText("▴")
            self._header_collapse_button.setToolTip("Collapse connection bar")
        if hasattr(self, "_header_reopen_button"):
            self._header_reopen_button.setText("▾")
            self._header_reopen_button.setToolTip("Expand connection bar")

    def _on_nav_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
