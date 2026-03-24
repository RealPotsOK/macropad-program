from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ..platform import resolve_app_paths

THEME_FILE_NAME = "theme.toml"

# Compatibility constants used by some widgets.
BORDER_MUTED = "#243044"
BORDER_SELECTED = "#38BDF8"


@dataclass(slots=True)
class ThemeSettings:
    preset: str = "basic_dark"
    primary_bg: str = "#0C111B"
    secondary_bg: str = "#111827"
    panel_bg: str = "#111827"
    input_bg: str = "#101826"
    primary_text: str = "#EDF2F7"
    secondary_text: str = "#9FB0C7"
    tertiary_text: str = "#C7D2E0"
    accent: str = "#38BDF8"
    border: str = "#243044"


def basic_dark_theme() -> ThemeSettings:
    return ThemeSettings()


def basic_light_theme() -> ThemeSettings:
    return ThemeSettings(
        preset="basic_light",
        primary_bg="#F3F6FC",
        secondary_bg="#FFFFFF",
        panel_bg="#FFFFFF",
        input_bg="#EEF2F9",
        primary_text="#0F172A",
        secondary_text="#475569",
        tertiary_text="#334155",
        accent="#2563EB",
        border="#CBD5E1",
    )


def theme_path() -> Path:
    paths = resolve_app_paths()
    paths.data_root.mkdir(parents=True, exist_ok=True)
    return paths.data_root / THEME_FILE_NAME


def load_theme_settings(path: Path | None = None) -> ThemeSettings:
    target = path or theme_path()
    if not target.exists():
        settings = basic_dark_theme()
        save_theme_settings(settings, path=target)
        return settings

    try:
        with target.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return basic_dark_theme()

    if not isinstance(raw, dict):
        return basic_dark_theme()

    defaults = basic_dark_theme()
    return ThemeSettings(
        preset=_normalize_preset(raw.get("preset", defaults.preset)),
        primary_bg=_normalize_hex(raw.get("primary_bg"), defaults.primary_bg),
        secondary_bg=_normalize_hex(raw.get("secondary_bg"), defaults.secondary_bg),
        panel_bg=_normalize_hex(raw.get("panel_bg"), defaults.panel_bg),
        input_bg=_normalize_hex(raw.get("input_bg"), defaults.input_bg),
        primary_text=_normalize_hex(raw.get("primary_text"), defaults.primary_text),
        secondary_text=_normalize_hex(raw.get("secondary_text"), defaults.secondary_text),
        tertiary_text=_normalize_hex(raw.get("tertiary_text"), defaults.tertiary_text),
        accent=_normalize_hex(raw.get("accent"), defaults.accent),
        border=_normalize_hex(raw.get("border"), defaults.border),
    )


def save_theme_settings(settings: ThemeSettings, *, path: Path | None = None) -> Path:
    target = path or theme_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = ThemeSettings(
        preset=_normalize_preset(settings.preset),
        primary_bg=_normalize_hex(settings.primary_bg, basic_dark_theme().primary_bg),
        secondary_bg=_normalize_hex(settings.secondary_bg, basic_dark_theme().secondary_bg),
        panel_bg=_normalize_hex(settings.panel_bg, basic_dark_theme().panel_bg),
        input_bg=_normalize_hex(settings.input_bg, basic_dark_theme().input_bg),
        primary_text=_normalize_hex(settings.primary_text, basic_dark_theme().primary_text),
        secondary_text=_normalize_hex(settings.secondary_text, basic_dark_theme().secondary_text),
        tertiary_text=_normalize_hex(settings.tertiary_text, basic_dark_theme().tertiary_text),
        accent=_normalize_hex(settings.accent, basic_dark_theme().accent),
        border=_normalize_hex(settings.border, basic_dark_theme().border),
    )
    target.write_text(
        "\n".join(
            [
                f'preset = "{normalized.preset}"',
                f'primary_bg = "{normalized.primary_bg}"',
                f'secondary_bg = "{normalized.secondary_bg}"',
                f'panel_bg = "{normalized.panel_bg}"',
                f'input_bg = "{normalized.input_bg}"',
                f'primary_text = "{normalized.primary_text}"',
                f'secondary_text = "{normalized.secondary_text}"',
                f'tertiary_text = "{normalized.tertiary_text}"',
                f'accent = "{normalized.accent}"',
                f'border = "{normalized.border}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


def apply_theme(app: QApplication, settings: ThemeSettings) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(settings.primary_bg))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(settings.primary_text))
    palette.setColor(QPalette.ColorRole.Base, QColor(settings.input_bg))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(settings.secondary_bg))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(settings.secondary_bg))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(settings.primary_text))
    palette.setColor(QPalette.ColorRole.Text, QColor(settings.primary_text))
    palette.setColor(QPalette.ColorRole.Button, QColor(settings.secondary_bg))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(settings.primary_text))
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(settings.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(settings.primary_bg))
    app.setPalette(palette)
    app.setStyleSheet(
        f"""
        QWidget {{
            background: {settings.primary_bg};
            color: {settings.primary_text};
        }}
        QLabel, QCheckBox, QRadioButton, QGroupBox {{
            background: transparent;
        }}
        QMainWindow {{
            background: {settings.primary_bg};
        }}
        QFrame[panel="true"] {{
            background: {settings.panel_bg};
            border: 1px solid {settings.border};
            border-radius: 12px;
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget, QTableWidget, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {settings.input_bg};
            color: {settings.primary_text};
            border: 1px solid {settings.border};
            border-radius: 8px;
            padding: 6px 8px;
            selection-background-color: {settings.accent};
        }}
        QComboBox QAbstractItemView {{
            background: {settings.input_bg};
            color: {settings.primary_text};
            border: 1px solid {settings.border};
            selection-background-color: {settings.accent};
        }}
        QPushButton {{
            background: {settings.secondary_bg};
            color: {settings.primary_text};
            border: 1px solid {settings.border};
            border-radius: 9px;
            padding: 7px 12px;
        }}
        QPushButton:hover {{
            border-color: {settings.accent};
        }}
        QListWidget {{
            background: {settings.input_bg};
            border: 1px solid {settings.border};
            border-radius: 12px;
            padding: 6px;
        }}
        QListWidget::item {{
            min-height: 34px;
            padding: 8px 10px;
            border-radius: 8px;
            color: {settings.primary_text};
        }}
        QListWidget::item:selected {{
            background: {settings.accent};
            color: {settings.primary_bg};
        }}
        QListWidget#SideNav {{
            background: {settings.secondary_bg};
            border: 1px solid {settings.border};
            border-radius: 14px;
            padding: 8px;
            font-size: 11pt;
        }}
        QListWidget#SideNav::item {{
            min-height: 40px;
            padding: 10px 12px;
            margin: 2px 0;
            border-radius: 10px;
            color: {settings.secondary_text};
        }}
        QListWidget#SideNav::item:hover {{
            background: {settings.input_bg};
            color: {settings.primary_text};
        }}
        QListWidget#SideNav::item:selected {{
            background: {settings.accent};
            color: {settings.primary_bg};
        }}
        QMenu {{
            background: {settings.secondary_bg};
            color: {settings.primary_text};
            border: 1px solid {settings.border};
        }}
        QMenu::item:selected {{
            background: {settings.accent};
            color: {settings.primary_bg};
        }}
        QToolTip {{
            background: {settings.secondary_bg};
            color: {settings.primary_text};
            border: 1px solid {settings.border};
        }}
        QWidget#SetupPage QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {settings.primary_text};
            border-radius: 4px;
            background: {settings.input_bg};
        }}
        QWidget#SetupPage QCheckBox::indicator:checked {{
            border: 1px solid {settings.primary_text};
            background: {settings.accent};
        }}
        QWidget#SetupPage QCheckBox::indicator:unchecked {{
            border: 1px solid {settings.primary_text};
            background: transparent;
        }}
        QWidget#SetupVirtualGrid {{
            background: {settings.input_bg};
            border: 1px solid {settings.border};
            border-radius: 10px;
        }}
        QLabel#AppSubtitle, QLabel#PageSubtitle {{
            color: {settings.secondary_text};
        }}
        QLabel#Pill, QLabel#StatusPill {{
            background: {settings.secondary_bg};
            border: 1px solid {settings.border};
            color: {settings.tertiary_text};
            border-radius: 999px;
            padding: 6px 10px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {settings.secondary_bg};
            min-height: 28px;
            border-radius: 6px;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 12px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: {settings.secondary_bg};
            min-width: 28px;
            border-radius: 6px;
        }}
        QFrame#AudioVolumeRow {{
            background: transparent;
            border: none;
        }}
        QLabel#AudioVolumeLabel {{
            background: transparent;
            color: {settings.secondary_text};
        }}
        QSlider#AudioVolumeSlider::groove:horizontal {{
            height: 6px;
            background: {settings.input_bg};
            border: 1px solid {settings.border};
            border-radius: 3px;
        }}
        QSlider#AudioVolumeSlider::sub-page:horizontal {{
            background: {settings.accent};
            border: 1px solid {settings.accent};
            border-radius: 3px;
        }}
        QSlider#AudioVolumeSlider::add-page:horizontal {{
            background: {settings.input_bg};
            border: 1px solid {settings.border};
            border-radius: 3px;
        }}
        QSlider#AudioVolumeSlider::handle:horizontal {{
            width: 14px;
            margin: -5px 0;
            background: {settings.primary_text};
            border: 1px solid {settings.border};
            border-radius: 7px;
        }}
        QSlider#AudioVolumeSlider::handle:horizontal:hover {{
            border: 1px solid {settings.accent};
        }}
        """
    )


def apply_saved_theme(app: QApplication) -> ThemeSettings:
    settings = load_theme_settings()
    apply_theme(app, settings)
    return settings


def apply_dark_theme(app: QApplication) -> None:
    apply_theme(app, basic_dark_theme())


def scale_app_fonts(app: QApplication, zoom_percent: int) -> None:
    zoom = max(70, min(100, int(zoom_percent)))
    font = app.font()
    base = font.pointSizeF()
    if base <= 0:
        base = 9.0
    font.setPointSizeF(base * (zoom / 100.0))
    app.setFont(font)


def _normalize_preset(value: object) -> str:
    text = str(value or "custom").strip().lower()
    if text in {"basic_dark", "dark"}:
        return "basic_dark"
    if text in {"basic_light", "light"}:
        return "basic_light"
    return "custom"


def _normalize_hex(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) == 4:
        text = "#" + "".join(ch * 2 for ch in text[1:])
    if len(text) != 7:
        return fallback
    try:
        int(text[1:], 16)
    except ValueError:
        return fallback
    return text.upper()
