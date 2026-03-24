from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..theme import (
    ThemeSettings,
    basic_dark_theme,
    basic_light_theme,
    load_theme_settings,
    save_theme_settings,
)


class PersonalizationPage(QWidget):
    def __init__(
        self,
        *,
        on_theme_applied: Callable[[ThemeSettings], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_theme_applied = on_theme_applied
        self._fields: dict[str, QLineEdit] = {}
        self._swatches: dict[str, QPushButton] = {}
        self._settings = load_theme_settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        panel = QFrame(self)
        panel.setProperty("panel", True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 4, 14, 14)
        panel_layout.setSpacing(10)

        panel_layout.addWidget(QLabel("Personalization"))
        subtitle = QLabel(
            "Use presets or set base colors manually. Save writes theme.toml and applies immediately."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("PageSubtitle")
        panel_layout.addWidget(subtitle)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset"))
        self.preset_combo = QComboBox(panel)
        self.preset_combo.addItem("Basic Dark", userData="basic_dark")
        self.preset_combo.addItem("Basic Light", userData="basic_light")
        self.preset_combo.addItem("Custom", userData="custom")
        preset_row.addWidget(self.preset_combo, 1)
        self.apply_preset_button = QPushButton("Apply Preset")
        preset_row.addWidget(self.apply_preset_button)
        panel_layout.addLayout(preset_row)

        divider = QFrame(panel)
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setStyleSheet("background: transparent; border: none; border-top: 1px solid #334155;")
        panel_layout.addWidget(divider)

        form = QFormLayout()
        panel_layout.addLayout(form)
        self._add_color_row(form, "primary_bg", "Primary BG")
        self._add_color_row(form, "secondary_bg", "Secondary BG")
        self._add_color_row(form, "panel_bg", "Panel BG")
        self._add_color_row(form, "input_bg", "Input BG")
        self._add_color_row(form, "primary_text", "Primary Text")
        self._add_color_row(form, "secondary_text", "Secondary Text")
        self._add_color_row(form, "tertiary_text", "Tertiary Text")
        self._add_color_row(form, "accent", "Accent")
        self._add_color_row(form, "border", "Border")

        action_row = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.save_button = QPushButton("Save")
        self.reload_button = QPushButton("Reload")
        action_row.addWidget(self.apply_button)
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.reload_button)
        action_row.addStretch(1)
        panel_layout.addLayout(action_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        panel_layout.addWidget(self.status)

        root.addWidget(panel, 1)

        self.apply_preset_button.clicked.connect(self._apply_preset_clicked)
        self.apply_button.clicked.connect(self._apply_clicked)
        self.save_button.clicked.connect(self._save_clicked)
        self.reload_button.clicked.connect(self._reload_clicked)

        self._write_fields(self._settings)
        self._set_preset_combo(self._settings.preset)

    def _add_color_row(self, form: QFormLayout, key: str, label: str) -> None:
        field = QLineEdit(self)
        field.setPlaceholderText("#RRGGBB")
        pick = QPushButton("Pick", self)
        swatch = QPushButton(self)
        swatch.setFixedWidth(30)
        swatch.setToolTip("Open color picker")
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(swatch)
        row_layout.addWidget(field, 1)
        row_layout.addWidget(pick)
        form.addRow(label, row)
        self._fields[key] = field
        self._swatches[key] = swatch
        pick.clicked.connect(lambda *_args, k=key: self._pick_color(k))
        swatch.clicked.connect(lambda *_args, k=key: self._pick_color(k))
        field.textChanged.connect(lambda *_args, k=key: self._update_swatch(k))

    def _pick_color(self, key: str) -> None:
        field = self._fields.get(key)
        if field is None:
            return
        current = QColor(field.text().strip() or "#000000")
        picked = QColorDialog.getColor(current, self, "Pick Color")
        if picked.isValid():
            field.setText(picked.name().upper())
            self._update_swatch(key)

    def _apply_preset_clicked(self) -> None:
        preset = str(self.preset_combo.currentData() or "basic_dark")
        settings = self._preset_settings(preset)
        self._write_fields(settings)
        self._set_preset_combo(preset)
        self._apply_theme(settings)
        self.status.setText(f"Applied preset: {preset}")

    def _apply_clicked(self) -> None:
        settings = self._read_fields()
        if settings is None:
            return
        self._apply_theme(settings)
        self.status.setText("Applied custom theme preview.")

    def _save_clicked(self) -> None:
        settings = self._read_fields()
        if settings is None:
            return
        save_theme_settings(settings)
        self._apply_theme(settings)
        self.status.setText("Saved and applied theme.toml.")

    def _reload_clicked(self) -> None:
        self._settings = load_theme_settings()
        self._write_fields(self._settings)
        self._set_preset_combo(self._settings.preset)
        self._apply_theme(self._settings)
        self.status.setText("Reloaded theme from theme.toml.")

    def _read_fields(self) -> ThemeSettings | None:
        try:
            settings = ThemeSettings(
                preset=str(self.preset_combo.currentData() or "custom"),
                primary_bg=self._normalized_color("primary_bg"),
                secondary_bg=self._normalized_color("secondary_bg"),
                panel_bg=self._normalized_color("panel_bg"),
                input_bg=self._normalized_color("input_bg"),
                primary_text=self._normalized_color("primary_text"),
                secondary_text=self._normalized_color("secondary_text"),
                tertiary_text=self._normalized_color("tertiary_text"),
                accent=self._normalized_color("accent"),
                border=self._normalized_color("border"),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Color", str(exc))
            return None
        self._settings = settings
        return settings

    def _normalized_color(self, key: str) -> str:
        value = self._fields[key].text().strip()
        if not value:
            raise ValueError(f"{key} is empty.")
        if not value.startswith("#"):
            value = f"#{value}"
        if len(value) == 4:
            value = "#" + "".join(ch * 2 for ch in value[1:])
        if len(value) != 7:
            raise ValueError(f"{key} must be a hex color like #RRGGBB.")
        try:
            int(value[1:], 16)
        except ValueError as exc:
            raise ValueError(f"{key} must be a valid hex color.") from exc
        return value.upper()

    def _write_fields(self, settings: ThemeSettings) -> None:
        self._fields["primary_bg"].setText(settings.primary_bg)
        self._fields["secondary_bg"].setText(settings.secondary_bg)
        self._fields["panel_bg"].setText(settings.panel_bg)
        self._fields["input_bg"].setText(settings.input_bg)
        self._fields["primary_text"].setText(settings.primary_text)
        self._fields["secondary_text"].setText(settings.secondary_text)
        self._fields["tertiary_text"].setText(settings.tertiary_text)
        self._fields["accent"].setText(settings.accent)
        self._fields["border"].setText(settings.border)
        for key in self._fields:
            self._update_swatch(key)

    def _set_preset_combo(self, preset: str) -> None:
        index = self.preset_combo.findData(preset)
        if index < 0:
            index = self.preset_combo.findData("custom")
        self.preset_combo.setCurrentIndex(max(0, index))

    def _preset_settings(self, preset: str) -> ThemeSettings:
        if preset == "basic_light":
            return basic_light_theme()
        if preset == "basic_dark":
            return basic_dark_theme()
        return self._settings

    def _apply_theme(self, settings: ThemeSettings) -> None:
        if self._on_theme_applied is not None:
            self._on_theme_applied(settings)

    def _update_swatch(self, key: str) -> None:
        field = self._fields.get(key)
        swatch = self._swatches.get(key)
        if field is None or swatch is None:
            return
        raw = field.text().strip()
        color = raw if raw.startswith("#") else f"#{raw}" if raw else "#000000"
        if len(color) == 4:
            color = "#" + "".join(ch * 2 for ch in color[1:])
        qcolor = QColor(color)
        if not qcolor.isValid():
            qcolor = QColor("#000000")
        swatch.setStyleSheet(
            f"background: {qcolor.name().upper()}; border: 1px solid #64748B; border-radius: 6px;"
        )
