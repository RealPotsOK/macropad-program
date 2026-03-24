from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def build_app_icon(*, size: int = 256) -> QIcon:
    pixmap = render_app_icon_pixmap(size=size)
    return QIcon(pixmap)


def render_app_icon_pixmap(*, size: int = 256) -> QPixmap:
    icon_path = _resolve_icon_png_path()
    if icon_path is not None:
        pixmap = QPixmap(str(icon_path))
        if not pixmap.isNull():
            edge = max(16, int(size))
            return pixmap.scaled(edge, edge, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _render_generated_icon(size=size)


def _resolve_icon_png_path() -> Path | None:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = Path(meipass)
        candidates.append(meipass_path / "assets" / "MP_Icon.png")
        candidates.append(meipass_path.parent / "assets" / "MP_Icon.png")

    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "assets" / "MP_Icon.png")
    exe_dir = Path(sys.executable).resolve().parent
    candidates.append(exe_dir / "assets" / "MP_Icon.png")
    candidates.append(exe_dir / "_internal" / "assets" / "MP_Icon.png")

    for path in candidates:
        if path.exists():
            return path
    return None


def _render_generated_icon(*, size: int = 256) -> QPixmap:
    edge = max(32, int(size))
    pixmap = QPixmap(edge, edge)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    rect = QRectF(6, 6, edge - 12, edge - 12)
    radius = edge * 0.22

    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#22C55E"))
    gradient.setColorAt(0.48, QColor("#0EA5E9"))
    gradient.setColorAt(1.0, QColor("#1D4ED8"))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(rect, radius, radius)

    glow = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.bottom()))
    glow.setColorAt(0.0, QColor(255, 255, 255, 55))
    glow.setColorAt(0.55, QColor(255, 255, 255, 12))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(glow)
    painter.drawRoundedRect(rect.adjusted(0, 0, 0, -rect.height() * 0.28), radius, radius)

    font = QFont("Segoe UI", max(14, int(edge * 0.36)))
    font.setWeight(QFont.Weight.Black)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0.5, edge * 0.01))

    path = QPainterPath()
    path.addText(QPointF(0.0, 0.0), font, "MP")
    bounds = path.boundingRect()
    target_rect = rect.adjusted(rect.width() * 0.06, rect.height() * 0.05, -rect.width() * 0.06, -rect.height() * 0.02)
    dx = target_rect.center().x() - bounds.center().x()
    dy = target_rect.center().y() - bounds.center().y()
    path = path.translated(dx, dy)

    painter.setBrush(QColor(7, 11, 24, 75))
    painter.translate(0, edge * 0.012)
    painter.drawPath(path)
    painter.translate(0, -edge * 0.012)

    painter.setPen(QPen(QColor(255, 255, 255, 35), max(1.0, edge * 0.012)))
    painter.setBrush(QColor("#F8FAFC"))
    painter.drawPath(path)

    painter.end()
    return pixmap


def render_app_icon_pxmap(*, size: int = 256) -> QPixmap:
    return render_app_icon_pixmap(size=size)
