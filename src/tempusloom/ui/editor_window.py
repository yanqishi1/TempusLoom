# -*- coding: utf-8 -*-
"""
TempusLoom – 主编辑界面
Main editor window matching the pencil.pen design (1440 × 900).
"""

from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QSize, QRectF, QPointF, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QBrush, QPen,
    QPixmap, QFont, QLinearGradient, QWheelEvent,
    QMouseEvent, QKeySequence, QAction,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QScrollArea, QFrame, QFileDialog,
    QSizePolicy, QSlider, QComboBox, QMenu, QMenuBar,
    QStackedWidget, QSpacerItem,
)

from .editor_icons import icon_pixmap
from PIL.ImageQt import ImageQt
from tempusloom.core import TLImage


# ── design tokens ──────────────────────────────────────────────────────────────
C_PRIMARY   = "#3370FF"
C_PRIMARY_H = "#5B8FF9"
C_BG_APP    = "#181818"
C_BG_TOPBAR = "#252525"
C_BG_PANEL  = "#1e1e1e"
C_BG_ITEM   = "#2c2c2c"
C_BG_ACTIVE = "#1a3060"
C_BG_RIGHT  = "#222222"
C_BG_CANVAS = "#141414"
C_BORDER    = "#333333"
C_BORDER_P  = "#2d2d2d"
C_TEXT_1    = "#e8e8e8"
C_TEXT_2    = "#aaaaaa"
C_TEXT_3    = "#888888"
C_TEXT_4    = "#777777"
C_WHITE     = "#ffffff"
C_ICON_ACT  = C_PRIMARY
C_ICON_DEF  = C_TEXT_4


# ── tiny helpers ───────────────────────────────────────────────────────────────

def _lbl(text: str, color: str = C_TEXT_3, size: int = 12,
         weight: QFont.Weight = QFont.Weight.Normal) -> QLabel:
    lb = QLabel(text)
    lb.setStyleSheet(f"color:{color}; font-size:{size}px; background:transparent;")
    if weight != QFont.Weight.Normal:
        font = lb.font()
        font.setWeight(weight)
        lb.setFont(font)
    return lb


def _icon_btn(icon_name: str, icon_size: int = 16, btn_size: int = 32,
              color: str = C_ICON_DEF, radius: int = 6,
              bg: str = "transparent") -> QPushButton:
    """Square icon-only button."""
    btn = QPushButton()
    btn.setFixedSize(btn_size, btn_size)
    btn.setIcon(_qicon(icon_name, icon_size, color))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setStyleSheet(
        f"QPushButton{{background:{bg};border-radius:{radius}px;border:none;}}"
        f"QPushButton:hover{{background:{C_BG_ITEM};}}"
        f"QPushButton:pressed{{background:#3a3a3a;}}"
    )
    return btn


def _qicon(icon_name: str, size: int, color: str):
    from PyQt6.QtGui import QIcon
    return QIcon(icon_pixmap(icon_name, size, color))


def _logo_pixmap(size: int = 24) -> QPixmap:
    app = QApplication.instance()
    ratio = app.primaryScreen().devicePixelRatio() if app and app.primaryScreen() else 1.0
    px_size = int(size * ratio)
    px = QPixmap(px_size, px_size)
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(C_PRIMARY))
    grad.setColorAt(1, QColor(C_PRIMARY_H))
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, 6, 6)
    p.fillPath(path, QBrush(grad))
    p.setPen(QColor(C_WHITE))
    p.setFont(QFont("Arial", max(size // 2, 8), QFont.Weight.Bold))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "T")
    p.end()
    return px


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{C_BORDER}; border:none;")
    return line


def _vline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedWidth(1)
    line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    line.setStyleSheet(f"background:{C_BORDER}; border:none;")
    return line


# ══════════════════════════════════════════════════════════════════════════════
# TOP NAV BAR
# ══════════════════════════════════════════════════════════════════════════════

class EditorTopBar(QWidget):
    """48 px navigation bar: logo · mode-switch · menus · undo/redo · save/export."""

    mode_switched   = pyqtSignal(str)   # "gallery" | "editor"
    undo_requested  = pyqtSignal()
    redo_requested  = pyqtSignal()
    save_requested  = pyqtSignal()
    export_requested = pyqtSignal()
    open_requested  = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"background:{C_BG_TOPBAR}; "
            f"border-bottom: 1px solid {C_BORDER};"
        )
        self._build()

    def _build(self) -> None:
        lo = QHBoxLayout(self)
        lo.setContentsMargins(16, 0, 16, 0)
        lo.setSpacing(0)

        # logo
        logo_icon = QLabel()
        logo_icon.setPixmap(_logo_pixmap(24))
        logo_icon.setFixedSize(24, 24)
        lo.addWidget(logo_icon)
        lo.addSpacing(8)
        logo_txt = _lbl("TempusLoom", C_WHITE, 15)
        logo_txt.setStyleSheet(
            f"color:{C_WHITE}; font-size:15px; font-weight:700; background:transparent;"
        )
        lo.addWidget(logo_txt)
        lo.addSpacing(12)
        lo.addWidget(_vline())
        lo.addSpacing(8)

        # mode switch
        mode_w = QWidget()
        mode_w.setFixedHeight(32)
        mode_w.setStyleSheet(
            f"background:#383838; border-radius:6px;"
        )
        mode_lo = QHBoxLayout(mode_w)
        mode_lo.setContentsMargins(2, 2, 2, 2)
        mode_lo.setSpacing(0)

        self._btn_gallery = QPushButton("图库")
        self._btn_gallery.setFixedHeight(28)
        self._btn_gallery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gallery.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_gallery.setStyleSheet(
            f"background:transparent; color:{C_TEXT_3}; font-size:12px;"
            f"border-radius:4px; border:none; padding:0 12px;"
            f"QPushButton:hover{{color:{C_TEXT_1};}}"
        )
        self._btn_gallery.clicked.connect(lambda: self.mode_switched.emit("gallery"))

        self._btn_editor = QPushButton("编辑器")
        self._btn_editor.setFixedHeight(28)
        self._btn_editor.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_editor.setStyleSheet(
            f"background:{C_BG_PANEL}; color:{C_PRIMARY}; font-size:12px; font-weight:500;"
            f"border-radius:4px; border:none; padding:0 12px;"
        )
        self._btn_editor.clicked.connect(lambda: self.mode_switched.emit("editor"))

        mode_lo.addWidget(self._btn_gallery)
        mode_lo.addWidget(self._btn_editor)
        lo.addWidget(mode_w)
        lo.addSpacing(8)
        lo.addWidget(_vline())
        lo.addSpacing(4)

        # menu items
        for text in ("文件", "编辑", "视图", "插件"):
            btn = QPushButton(text)
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(
                f"background:transparent; color:{C_TEXT_2}; font-size:13px;"
                f"border:none; padding:0 12px;"
                f"QPushButton:hover{{color:{C_TEXT_1}; background:rgba(255,255,255,0.05);}}"
            )
            if text == "文件":
                btn.clicked.connect(self._show_file_menu)
            lo.addWidget(btn)

        lo.addStretch()

        # undo / redo
        self._undo_btn = _icon_btn("undo-2", 16, 32, C_TEXT_4)
        self._undo_btn.setToolTip("撤销  Ctrl+Z")
        self._undo_btn.clicked.connect(self.undo_requested.emit)
        self._redo_btn = _icon_btn("redo-2", 16, 32, C_TEXT_4)
        self._redo_btn.setToolTip("重做  Ctrl+Y")
        self._redo_btn.clicked.connect(self.redo_requested.emit)
        lo.addWidget(self._undo_btn)
        lo.addSpacing(2)
        lo.addWidget(self._redo_btn)
        lo.addSpacing(8)
        lo.addWidget(_vline())
        lo.addSpacing(8)

        # save
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(32)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        save_btn.setIcon(_qicon("save", 14, C_TEXT_2))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; border-radius:6px; border:none;"
            f"color:{C_TEXT_2}; font-size:13px; padding:0 14px;}}"
            f"QPushButton:hover{{background:#383838;}}"
            f"QPushButton:pressed{{background:#3a3a3a;}}"
        )
        save_btn.clicked.connect(self.save_requested.emit)
        lo.addWidget(save_btn)
        lo.addSpacing(8)

        # export
        export_btn = QPushButton("导出")
        export_btn.setFixedHeight(32)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        export_btn.setIcon(_qicon("share", 14, C_TEXT_2))
        export_btn.setIconSize(QSize(14, 14))
        export_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; border-radius:6px; border:none;"
            f"color:{C_TEXT_2}; font-size:13px; padding:0 14px;}}"
            f"QPushButton:hover{{background:#383838;}}"
            f"QPushButton:pressed{{background:#3a3a3a;}}"
        )
        export_btn.clicked.connect(self.export_requested.emit)
        lo.addWidget(export_btn)
        lo.addSpacing(8)

        # avatar
        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        av_px = QPixmap(28, 28)
        av_px.fill(Qt.GlobalColor.transparent)
        p = QPainter(av_px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(C_BG_ACTIVE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 28, 28)
        p.drawPixmap(7, 7, icon_pixmap("user", 14, "#6366F1"))
        p.end()
        avatar.setPixmap(av_px)
        lo.addWidget(avatar)

    def _show_file_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C_BG_PANEL}; color:{C_TEXT_1};"
            f"border:1px solid {C_BORDER}; border-radius:6px; padding:4px;}}"
            f"QMenu::item{{padding:6px 20px; border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C_BG_ACTIVE}; color:{C_PRIMARY};}}"
            f"QMenu::separator{{background:{C_BORDER}; height:1px; margin:4px 8px;}}"
        )
        menu.addAction("打开图像…").triggered.connect(self.open_requested.emit)
        menu.addSeparator()
        menu.addAction("保存").triggered.connect(self.save_requested.emit)
        menu.addAction("另存为…")
        menu.addSeparator()
        menu.addAction("导出…").triggered.connect(self.export_requested.emit)
        menu.exec(self.mapToGlobal(QPointF(0, 48).toPoint()))


# ══════════════════════════════════════════════════════════════════════════════
# LEFT TOOL SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

class ToolButton(QPushButton):
    """40×40 tool button that knows its active state."""

    def __init__(self, icon_name: str, tooltip: str,
                 active: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._active = active
        self.setFixedSize(40, 40)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._update_appearance()
        self.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool) -> None:
        self._active = checked
        self._update_appearance()

    def _update_appearance(self) -> None:
        color = C_ICON_ACT if self._active else C_ICON_DEF
        bg    = C_BG_ACTIVE if self._active else "transparent"
        self.setIcon(_qicon(self._icon_name, 18, color))
        self.setIconSize(QSize(18, 18))
        self.setStyleSheet(
            f"QPushButton{{background:{bg}; border-radius:8px; border:none;}}"
            f"QPushButton:hover{{background:{'#1d3870' if self._active else C_BG_ITEM};}}"
            f"QPushButton:checked{{background:{C_BG_ACTIVE};}}"
        )


class ToolSidebar(QWidget):
    """48 px wide vertical tool strip on the left."""

    tool_changed = pyqtSignal(str)

    _TOOLS = [
        ("mouse-pointer", "选择  V"),
        ("crop",          "裁剪  C"),
        ("pen-tool",      "钢笔  P"),
        ("paintbrush",    "画笔  B"),
        ("eraser",        "橡皮擦  E"),
        ("type",          "文字  T"),
        ("pipette",       "吸管  I"),
    ]
    _AI_TOOLS = [
        ("wand-2", "智能魔棒"),
        ("stamp",  "仿制图章  S"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(
            f"background:{C_BG_PANEL}; border-right:1px solid {C_BORDER_P};"
        )
        self._buttons: list[ToolButton] = []
        self._active_name = "mouse-pointer"
        self._build()

    def _build(self) -> None:
        lo = QVBoxLayout(self)
        lo.setContentsMargins(4, 8, 4, 8)
        lo.setSpacing(2)

        for icon_name, tip in self._TOOLS:
            btn = ToolButton(icon_name, tip, active=(icon_name == self._active_name))
            btn.toggled.connect(lambda checked, n=icon_name: self._on_tool(n, checked))
            lo.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append(btn)

        # separator
        sep = QFrame()
        sep.setFixedSize(24, 1)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none;")
        lo.addSpacing(4)
        lo.addWidget(sep, alignment=Qt.AlignmentFlag.AlignHCenter)
        lo.addSpacing(4)

        for icon_name, tip in self._AI_TOOLS:
            btn = ToolButton(icon_name, tip, active=False)
            btn.toggled.connect(lambda checked, n=icon_name: self._on_tool(n, checked))
            lo.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append(btn)

        lo.addStretch()

    def _on_tool(self, name: str, checked: bool) -> None:
        if not checked:
            return
        self._active_name = name
        for btn in self._buttons:
            if btn._icon_name != name and btn.isChecked():
                btn.setChecked(False)
        self.tool_changed.emit(name)

    @property
    def active_tool(self) -> str:
        return self._active_name


# ══════════════════════════════════════════════════════════════════════════════
# TOOL OPTIONS BAR
# ══════════════════════════════════════════════════════════════════════════════

class ToolOptionsBar(QWidget):
    """40 px bar between top-nav and canvas: active tool + zoom + grid + ruler."""

    grid_toggled  = pyqtSignal(bool)
    ruler_toggled = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"background:{C_BG_TOPBAR}; border-bottom:1px solid {C_BORDER};"
        )
        self._grid_on  = False
        self._ruler_on = False
        self._build()

    def _build(self) -> None:
        lo = QHBoxLayout(self)
        lo.setContentsMargins(12, 0, 12, 0)
        lo.setSpacing(8)

        # active tool chip
        chip_w = QWidget()
        chip_w.setFixedHeight(28)
        chip_w.setStyleSheet(
            f"background:{C_BG_ACTIVE}; border-radius:6px;"
        )
        chip_lo = QHBoxLayout(chip_w)
        chip_lo.setContentsMargins(10, 0, 10, 0)
        chip_lo.setSpacing(4)
        self._tool_icon_lbl = QLabel()
        self._tool_icon_lbl.setPixmap(icon_pixmap("mouse-pointer", 12, C_PRIMARY))
        self._tool_icon_lbl.setFixedSize(12, 12)
        self._tool_name_lbl = _lbl("选择", C_PRIMARY, 12, QFont.Weight.Medium)
        chip_lo.addWidget(self._tool_icon_lbl)
        chip_lo.addWidget(self._tool_name_lbl)
        lo.addWidget(chip_w)

        lo.addWidget(_vline())

        self._zoom_lbl  = _lbl("缩放: 75%",  C_TEXT_3, 12)
        self._rot_lbl   = _lbl("旋转: 0°",   C_TEXT_3, 12)
        lo.addWidget(self._zoom_lbl)
        lo.addWidget(self._rot_lbl)
        lo.addWidget(_vline())

        # grid
        self._grid_btn = self._toggle_opt(
            "grid-3x3", "网格", self._on_grid_toggle
        )
        lo.addWidget(self._grid_btn)

        # ruler
        self._ruler_btn = self._toggle_opt(
            "ruler", "标尺", self._on_ruler_toggle
        )
        lo.addWidget(self._ruler_btn)
        lo.addStretch()

    def _toggle_opt(self, icon_name: str, text: str, slot) -> QWidget:
        w = QPushButton()
        w.setFixedHeight(28)
        w.setCheckable(True)
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        w.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; border-radius:4px;"
            f"color:{C_TEXT_3}; font-size:12px; padding:0 8px;}}"
            f"QPushButton:hover{{color:{C_TEXT_1}; background:rgba(255,255,255,0.05);}}"
            f"QPushButton:checked{{color:{C_PRIMARY};}}"
        )
        inner = QHBoxLayout(w)
        inner.setContentsMargins(8, 0, 8, 0)
        inner.setSpacing(4)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap(icon_name, 14, C_TEXT_4))
        icon_lbl.setFixedSize(14, 14)
        inner.addWidget(icon_lbl)
        inner.addWidget(_lbl(text, C_TEXT_3, 12))
        w.toggled.connect(slot)
        return w

    def _on_grid_toggle(self, on: bool) -> None:
        self._grid_on = on
        self.grid_toggled.emit(on)

    def _on_ruler_toggle(self, on: bool) -> None:
        self._ruler_on = on
        self.ruler_toggled.emit(on)

    def set_tool(self, tool_name: str) -> None:
        _NAMES = {
            "mouse-pointer": "选择",
            "crop":          "裁剪",
            "pen-tool":      "钢笔",
            "paintbrush":    "画笔",
            "eraser":        "橡皮擦",
            "type":          "文字",
            "pipette":       "吸管",
            "wand-2":        "魔棒",
            "stamp":         "图章",
        }
        label = _NAMES.get(tool_name, tool_name)
        self._tool_icon_lbl.setPixmap(icon_pixmap(tool_name, 12, C_PRIMARY))
        self._tool_name_lbl.setText(label)

    def set_zoom(self, pct: int) -> None:
        self._zoom_lbl.setText(f"缩放: {pct}%")


# ══════════════════════════════════════════════════════════════════════════════
# CANVAS AREA
# ══════════════════════════════════════════════════════════════════════════════

class CanvasArea(QWidget):
    """
    Centre canvas: shows the opened image centred on a dark background.
    Supports:
      - Ctrl+scroll  zoom in/out
      - Middle-drag / Space+drag to pan
      - Fit-to-window on double-click
    """

    zoom_changed = pyqtSignal(int)   # zoom % (e.g. 75)

    _MIN_ZOOM = 5
    _MAX_ZOOM = 800

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG_CANVAS};")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self._pixmap:  Optional[QPixmap] = None
        self._zoom    = 75        # percent
        self._offset  = QPointF(0, 0)
        self._panning = False
        self._pan_start = QPointF()
        self._pan_offset_start = QPointF()
        self._show_grid  = False
        self._show_ruler = False

        # placeholder label
        self._placeholder = QLabel(
            "打开图像以开始编辑\n\n"
            "文件  →  打开图像…\n"
            "或将文件拖入窗口"
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color:{C_TEXT_3}; font-size:13px; background:transparent;"
        )
        placeholder_lo = QVBoxLayout(self)
        placeholder_lo.addWidget(self._placeholder)
        self.setAcceptDrops(True)

    # ── image loading ──────────────────────────────────────────────────────────
    def load_image(self, path: str) -> bool:
        px = QPixmap(path)
        if px.isNull():
            return False
        self._pixmap = px
        self._placeholder.hide()
        self._fit_to_window()
        return True

    def set_pixmap(self, px: QPixmap) -> None:
        self._pixmap = px
        if not px.isNull():
            self._placeholder.hide()
            self._fit_to_window()

    def _fit_to_window(self) -> None:
        if not self._pixmap:
            return
        w, h = self.width(), self.height()
        if w < 10 or h < 10:
            return
        scale_w = (w - 40) / self._pixmap.width()
        scale_h = (h - 40) / self._pixmap.height()
        scale = min(scale_w, scale_h, 1.0)
        self._zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, int(scale * 100)))
        self._center_image()
        self.zoom_changed.emit(self._zoom)
        self.update()

    def _center_image(self) -> None:
        if not self._pixmap:
            return
        iw = self._pixmap.width()  * self._zoom / 100
        ih = self._pixmap.height() * self._zoom / 100
        self._offset = QPointF(
            (self.width()  - iw) / 2,
            (self.height() - ih) / 2,
        )

    # ── view toggles ───────────────────────────────────────────────────────────
    def set_grid(self, on: bool) -> None:
        self._show_grid = on
        self.update()

    def set_ruler(self, on: bool) -> None:
        self._show_ruler = on
        self.update()

    # ── painting ───────────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:              # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._pixmap and not self._pixmap.isNull():
            iw = self._pixmap.width()  * self._zoom / 100
            ih = self._pixmap.height() * self._zoom / 100
            dest = QRectF(self._offset.x(), self._offset.y(), iw, ih)

            # drop shadow
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(dest.adjusted(4, 4, 4, 4), 4, 4)
            p.fillPath(shadow_path, QBrush(QColor(0, 0, 0, 80)))

            # image with rounded corners
            clip = QPainterPath()
            clip.addRoundedRect(dest, 4, 4)
            p.setClipPath(clip)
            p.drawPixmap(dest.toRect(), self._pixmap)
            p.setClipping(False)

            # grid overlay
            if self._show_grid:
                p.setPen(QPen(QColor(255, 255, 255, 30), 1))
                step = max(20, int(50 * self._zoom / 100))
                x = self._offset.x()
                while x < dest.right():
                    p.drawLine(QPointF(x, dest.top()), QPointF(x, dest.bottom()))
                    x += step
                y = self._offset.y()
                while y < dest.bottom():
                    p.drawLine(QPointF(dest.left(), y), QPointF(dest.right(), y))
                    y += step
        p.end()

    # ── events ────────────────────────────────────────────────────────────────
    def resizeEvent(self, _event) -> None:             # noqa: N802
        if self._pixmap:
            self._fit_to_window()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.10 if delta > 0 else 0.91
            new_zoom = int(self._zoom * factor)
            new_zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, new_zoom))
            if new_zoom != self._zoom:
                # zoom around cursor
                pos = event.position()
                ratio = new_zoom / self._zoom
                self._offset = QPointF(
                    pos.x() - (pos.x() - self._offset.x()) * ratio,
                    pos.y() - (pos.y() - self._offset.y()) * ratio,
                )
                self._zoom = new_zoom
                self.zoom_changed.emit(self._zoom)
                self.update()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:   # noqa: N802
        if (event.button() == Qt.MouseButton.MiddleButton or
                QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier):
            self._panning = True
            self._pan_start = event.position()
            self._pan_offset_start = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:    # noqa: N802
        if self._panning:
            delta = event.position() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None: # noqa: N802
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, _event) -> None:         # noqa: N802
        self._fit_to_window()

    # ── drag-drop ─────────────────────────────────────────────────────────────
    def dragEnterEvent(self, event) -> None:           # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:                # noqa: N802
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.load_image(path)
                break


# ══════════════════════════════════════════════════════════════════════════════
# STATUS BAR (BOTTOM STRIP)
# ══════════════════════════════════════════════════════════════════════════════

class EditorStatusBar(QWidget):
    """28 px status strip: file info left, zoom controls right."""

    zoom_in_requested  = pyqtSignal()
    zoom_out_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(f"background:{C_BG_PANEL}; border:none;")
        self._build()

    def _build(self) -> None:
        lo = QHBoxLayout(self)
        lo.setContentsMargins(12, 0, 12, 0)
        lo.setSpacing(12)

        self._info_lbl = _lbl("RGB | 300dpi | 24位", C_TEXT_3, 11)
        lo.addWidget(self._info_lbl)
        lo.addWidget(_lbl("|", "#bbbbbb", 11))
        self._size_lbl = _lbl("—", C_TEXT_3, 11)
        lo.addWidget(self._size_lbl)
        lo.addStretch()

        # zoom controls
        zoom_out = QPushButton()
        zoom_out.setFixedSize(16, 16)
        zoom_out.setStyleSheet("background:transparent; border:none;")
        zoom_out.setIcon(_qicon("minus", 12, C_TEXT_3))
        zoom_out.setIconSize(QSize(12, 12))
        zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        zoom_out.clicked.connect(self.zoom_out_requested.emit)

        self._zoom_lbl = _lbl("75%", C_TEXT_3, 11, QFont.Weight.Medium)
        self._zoom_lbl.setFixedWidth(38)
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        zoom_in = QPushButton()
        zoom_in.setFixedSize(16, 16)
        zoom_in.setStyleSheet("background:transparent; border:none;")
        zoom_in.setIcon(_qicon("plus", 12, C_TEXT_3))
        zoom_in.setIconSize(QSize(12, 12))
        zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        zoom_in.clicked.connect(self.zoom_in_requested.emit)

        lo.addWidget(zoom_out)
        lo.addWidget(self._zoom_lbl)
        lo.addWidget(zoom_in)

    def set_zoom(self, pct: int) -> None:
        self._zoom_lbl.setText(f"{pct}%")

    def set_image_info(self, width: int, height: int) -> None:
        self._size_lbl.setText(f"{width} × {height} px")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER ROW
# ══════════════════════════════════════════════════════════════════════════════

def _layer_thumb_pixmap(color: str, layer_type: str, size: int = 34) -> QPixmap:
    """HiDPI-aware square thumbnail for a layer row.
    Draws type-specific icons: 'T' for text layers, outline rect for mask layers.
    """
    app = QApplication.instance()
    ratio = app.primaryScreen().devicePixelRatio() if app and app.primaryScreen() else 1.0
    px_size = int(size * ratio)
    px = QPixmap(px_size, px_size)
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # rounded background fill
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), 4, 4)
    p.setClipPath(clip)
    p.fillRect(QRectF(0, 0, size, size), QColor(color))
    # type-specific overlay
    if layer_type == "文字":
        p.setPen(QColor(C_TEXT_1))
        p.setFont(QFont("Arial", max(int(size * 0.52), 8), QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "T")
    elif layer_type == "蒙版":
        pen = QPen(QColor(C_TEXT_2))
        pen.setWidthF(max(1.0, size / 22.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        m = size * 0.22
        p.drawRoundedRect(QRectF(m, m, size - 2 * m, size - 2 * m), 2, 2)
    p.end()
    return px


class LayerRow(QWidget):
    """Single layer entry in the layers list."""

    selected = pyqtSignal(int)
    visibility_toggled = pyqtSignal(int, bool)

    def __init__(self, index: int, name: str, layer_type: str,
                 thumb_color: str, active: bool = False,
                 locked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._index      = index
        self._active     = active
        self._visible    = True
        self._locked     = locked
        self.setFixedHeight(46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(name, layer_type, thumb_color, locked)
        self._update_style()

    def _build(self, name: str, layer_type: str,
               thumb_color: str, locked: bool) -> None:
        lo = QHBoxLayout(self)
        lo.setContentsMargins(10, 0, 10, 0)
        lo.setSpacing(10)

        # eye icon (16 × 16)
        self._eye_btn = QPushButton()
        self._eye_btn.setFixedSize(16, 16)
        self._eye_btn.setStyleSheet("background:transparent; border:none;")
        self._eye_btn.setCheckable(True)
        self._eye_btn.setChecked(True)
        self._eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eye_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._eye_btn.toggled.connect(self._on_eye_toggled)
        self._refresh_eye()
        lo.addWidget(self._eye_btn)

        # thumbnail (34 × 34 square)
        self._thumb_lbl = QLabel()
        self._thumb_lbl.setPixmap(_layer_thumb_pixmap(thumb_color, layer_type, 34))
        self._thumb_lbl.setFixedSize(34, 34)
        self._thumb_lbl.setStyleSheet(
            f"border-radius:4px; border:{'1px solid ' + C_PRIMARY if self._active else 'none'};"
        )
        lo.addWidget(self._thumb_lbl)

        # name + type
        info_w = QWidget()
        info_w.setStyleSheet("background:transparent;")
        info_lo = QVBoxLayout(info_w)
        info_lo.setContentsMargins(0, 0, 0, 0)
        info_lo.setSpacing(2)
        n_color = C_WHITE if self._active else C_TEXT_1
        self._name_lbl = _lbl(name, n_color, 13, QFont.Weight.Medium)
        self._type_lbl = _lbl(layer_type, C_TEXT_3, 11)
        info_lo.addWidget(self._name_lbl)
        info_lo.addWidget(self._type_lbl)
        lo.addWidget(info_w, 1)

        # lock
        if locked:
            lock_lbl = QLabel()
            lock_lbl.setPixmap(icon_pixmap("lock", 13, "#555555"))
            lock_lbl.setFixedSize(13, 13)
            lock_lbl.setStyleSheet("background:transparent;")
            lo.addWidget(lock_lbl)

    def _on_eye_toggled(self, visible: bool) -> None:
        self._visible = visible
        self._refresh_eye()
        self.visibility_toggled.emit(self._index, visible)

    def _refresh_eye(self) -> None:
        color = (C_TEXT_2 if self._active else C_TEXT_4) if self._visible else "#444444"
        self._eye_btn.setIcon(_qicon("eye", 16, color))
        self._eye_btn.setIconSize(QSize(16, 16))

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_style()
        n_color = C_WHITE if active else C_TEXT_1
        self._name_lbl.setStyleSheet(
            f"color:{n_color}; font-size:13px; font-weight:500; background:transparent;"
        )
        self._thumb_lbl.setStyleSheet(
            f"border-radius:4px; border:{'1px solid ' + C_PRIMARY if active else 'none'};"
        )
        self._refresh_eye()

    def _update_style(self) -> None:
        bg = C_BG_ACTIVE if self._active else "transparent"
        self.setStyleSheet(
            f"LayerRow{{background:{bg}; border-radius:8px;}}"
            f"LayerRow:hover{{background:{'#1d3870' if self._active else '#2a2a2a'};}}"
        )

    def mousePressEvent(self, _event) -> None:       # noqa: N802
        self.selected.emit(self._index)


# ── Adjustment-panel helpers ────────────────────────────────────────────────

class _ClickableHeader(QWidget):
    """QWidget that emits `clicked` on left-mouse-press.
    Used as the section header of AdjustSection so that child action-buttons
    can consume their own clicks without triggering the collapse toggle.
    """
    clicked = pyqtSignal()

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class _HistogramCanvas(QWidget):
    """Paints a realistic R/G/B stacked-bar histogram."""
    _H = 96

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self._H)
        self.setStyleSheet(
            f"background:{C_BG_ITEM}; border-radius:6px;"
        )
        # pre-bake pseudo-histogram data (128 bins, realistic distribution)
        import random
        rng = random.Random(42)
        bins = 128

        def _make_channel(peak1, peak2, spread):
            data = []
            for i in range(bins):
                t = i / (bins - 1)
                v = (math.exp(-0.5 * ((t - peak1) / spread) ** 2) * 0.7 +
                     math.exp(-0.5 * ((t - peak2) / spread) ** 2) * 0.4 +
                     rng.uniform(0, 0.08))
                data.append(v)
            # normalise
            mx = max(data) or 1.0
            return [x / mx for x in data]

        self._r = _make_channel(0.25, 0.72, 0.12)
        self._g = _make_channel(0.35, 0.68, 0.13)
        self._b = _make_channel(0.20, 0.60, 0.14)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        pad_t, pad_b = 6, 4
        draw_h = H - pad_t - pad_b
        bins = len(self._r)

        channels = [
            (self._r, QColor(255,  80,  80, 100)),
            (self._g, QColor( 60, 200,  80, 100)),
            (self._b, QColor( 60, 130, 255, 110)),
        ]
        for data, col in channels:
            path = QPainterPath()
            path.moveTo(0, H - pad_b)
            for i, v in enumerate(data):
                x = i / (bins - 1) * W
                y = pad_t + (1.0 - v) * draw_h
                path.lineTo(x, y)
            path.lineTo(W, H - pad_b)
            path.closeSubpath()
            p.fillPath(path, QBrush(col))

        # subtle top border line
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.end()


class GradientSlider(QWidget):
    """Horizontal slider with a colour-gradient track and a white circle handle."""
    value_changed = pyqtSignal(int)

    _TRACK_H = 8
    _HANDLE_R = 7
    _PAD = 10          # horizontal padding so handle doesn't clip

    def __init__(self,
                 left_color: str, right_color: str,
                 min_val: int = -100, max_val: int = 100,
                 value: int = 0,
                 parent=None) -> None:
        super().__init__(parent)
        self._left  = QColor(left_color)
        self._right = QColor(right_color)
        self._min   = min_val
        self._max   = max_val
        self._value = value
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.update()
            self.value_changed.emit(v)

    # ── geometry helpers ──────────────────────────────────────────────────────
    def _track_info(self):
        """Return (x0, y_center, track_width)."""
        x0 = self._PAD
        x1 = self.width() - self._PAD
        return x0, self.height() // 2, max(x1 - x0, 1)

    def _handle_x(self) -> float:
        x0, _, tw = self._track_info()
        ratio = (self._value - self._min) / (self._max - self._min)
        return x0 + ratio * tw

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x0, y_c, tw = self._track_info()
        th = self._TRACK_H

        grad = QLinearGradient(x0, 0, x0 + tw, 0)
        grad.setColorAt(0.0, self._left)
        grad.setColorAt(1.0, self._right)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(
            QRectF(x0, y_c - th / 2, tw, th), th / 2, th / 2
        )

        hx = self._handle_x()
        r  = float(self._HANDLE_R)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(QPen(QColor("#aaaaaa"), 1.2))
        p.drawEllipse(QPointF(hx, float(y_c)), r, r)
        p.end()

    # ── mouse interaction ─────────────────────────────────────────────────────
    def _x_to_value(self, x: float) -> int:
        x0, _, tw = self._track_info()
        ratio = max(0.0, min(1.0, (x - x0) / tw))
        return round(self._min + ratio * (self._max - self._min))

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._x_to_value(e.position().x()))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._x_to_value(e.position().x()))


class AdjustSection(QWidget):
    """Collapsible section used in the 调整 panel.

    Parameters
    ----------
    title:    section label shown in the header row
    expanded: whether content starts visible
    badge:    optional short badge string ("", "", …)
    """

    def __init__(self, title: str, *,
                 expanded: bool = False,
                 badge: str = "",
                 parent=None) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self.setStyleSheet("background:transparent;")

        root_lo = QVBoxLayout(self)
        root_lo.setContentsMargins(0, 0, 0, 0)
        root_lo.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = _ClickableHeader(self)
        hdr.setFixedHeight(36)
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.setStyleSheet(
            "background:transparent; border:none;"
            "_ClickableHeader:hover{background:rgba(255,255,255,0.03);}"
        )
        hdr_lo = QHBoxLayout(hdr)
        hdr_lo.setContentsMargins(12, 0, 8, 0)
        hdr_lo.setSpacing(6)

        # collapse arrow
        self._arrow_lbl = QLabel()
        self._arrow_lbl.setFixedSize(12, 12)
        self._arrow_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hdr_lo.addWidget(self._arrow_lbl)

        # title label
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{C_TEXT_1}; font-size:13px; font-weight:500;"
            "background:transparent;"
        )
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hdr_lo.addWidget(title_lbl)

        # optional badge
        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setStyleSheet(
                f"color:#ffffff; background:{C_PRIMARY}; font-size:9px;"
                "border-radius:3px; padding:1px 4px;"
            )
            badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            hdr_lo.addWidget(badge_lbl)

        hdr_lo.addStretch()

        # ── right icon buttons ────────────────────────────────────────────────
        _btn_ss = (
            "QPushButton{background:transparent; border:none;}"
            "QPushButton:hover{background:#333333; border-radius:4px;}"
        )

        reset_btn = QPushButton()
        reset_btn.setFixedSize(22, 22)
        reset_btn.setToolTip("重置")
        reset_btn.setIcon(_qicon("rotate-ccw", 12, C_TEXT_4))
        reset_btn.setIconSize(QSize(12, 12))
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reset_btn.setStyleSheet(_btn_ss)
        hdr_lo.addWidget(reset_btn)

        pin_btn = QPushButton()
        pin_btn.setFixedSize(22, 22)
        pin_btn.setToolTip("智能调整")
        pin_btn.setIcon(_qicon("sparkles", 12, C_TEXT_4))
        pin_btn.setIconSize(QSize(12, 12))
        pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pin_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pin_btn.setStyleSheet(_btn_ss)
        hdr_lo.addWidget(pin_btn)

        hdr.clicked.connect(self._toggle)
        root_lo.addWidget(hdr)

        # ── content area ──────────────────────────────────────────────────────
        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self.content_lo = QVBoxLayout(self._content)
        self.content_lo.setContentsMargins(12, 4, 12, 12)
        self.content_lo.setSpacing(10)
        root_lo.addWidget(self._content)

        self._update_arrow()
        self._content.setVisible(expanded)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_arrow()

    def _update_arrow(self) -> None:
        icon_name = "chevron-down" if self._expanded else "chevron-right"
        self._arrow_lbl.setPixmap(icon_pixmap(icon_name, 12, C_TEXT_3))


# ══════════════════════════════════════════════════════════════════════════════
# CURVE EDITOR
# ══════════════════════════════════════════════════════════════════════════════

class CurveEditor(QWidget):
    """Simple interactive tone-curve editor (drag-point curve)."""

    _PAD    = 12
    _PT_R   = 5     # point radius
    _GRID   = 4     # grid divisions

    def __init__(self, curve_color: str = "#ffffff",
                 height: int = 160, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(curve_color)
        self.setFixedHeight(height)
        self.setMinimumWidth(60)
        self.setStyleSheet(f"background:{C_BG_ITEM}; border-radius:6px;")
        # anchor + editable midpoint
        self._points: list[list[float]] = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
        self._drag_idx: int = -1
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── geometry ──────────────────────────────────────────────────────────────
    def _inner(self) -> QRectF:
        p = self._PAD
        return QRectF(p, p, self.width() - 2 * p, self.height() - 2 * p)

    def _to_widget(self, nx: float, ny: float) -> QPointF:
        r = self._inner()
        return QPointF(r.left() + nx * r.width(),
                       r.bottom() - ny * r.height())

    def _to_norm(self, wx: float, wy: float):
        r = self._inner()
        nx = (wx - r.left()) / r.width()
        ny = (r.bottom() - wy) / r.height()
        return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:        # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._inner()

        # grid lines
        grid_pen = QPen(QColor(255, 255, 255, 18), 1)
        p.setPen(grid_pen)
        for i in range(1, self._GRID):
            t = i / self._GRID
            x = r.left() + t * r.width()
            y = r.top()  + t * r.height()
            p.drawLine(QPointF(x, r.top()),    QPointF(x, r.bottom()))
            p.drawLine(QPointF(r.left(), y),   QPointF(r.right(), y))

        # diagonal baseline
        p.setPen(QPen(QColor(255, 255, 255, 30), 1, Qt.PenStyle.DashLine))
        p.drawLine(self._to_widget(0, 0), self._to_widget(1, 1))

        # curve (Catmull-Rom through points)
        pts = [self._to_widget(nx, ny) for nx, ny in self._points]
        if len(pts) >= 2:
            path = QPainterPath()
            path.moveTo(pts[0])
            if len(pts) == 2:
                path.lineTo(pts[1])
            else:
                # simple cubic through 3 control points
                path.cubicTo(
                    QPointF((pts[0].x() + pts[1].x()) / 2, pts[0].y()),
                    QPointF((pts[0].x() + pts[1].x()) / 2, pts[1].y()),
                    pts[1],
                )
                path.cubicTo(
                    QPointF((pts[1].x() + pts[2].x()) / 2, pts[1].y()),
                    QPointF((pts[1].x() + pts[2].x()) / 2, pts[2].y()),
                    pts[2],
                )
            curve_color = QColor(self._color)
            curve_color.setAlphaF(0.9)
            p.setPen(QPen(curve_color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # control points
        for i, (nx, ny) in enumerate(self._points):
            if i == 0 or i == len(self._points) - 1:
                continue  # don't draw anchors
            wp = self._to_widget(nx, ny)
            p.setBrush(QBrush(QColor(C_BG_PANEL)))
            p.setPen(QPen(self._color, 1.5))
            p.drawEllipse(wp, float(self._PT_R), float(self._PT_R))
        p.end()

    # ── interaction ───────────────────────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent) -> None:    # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        wx, wy = e.position().x(), e.position().y()
        for i, (nx, ny) in enumerate(self._points):
            wp = self._to_widget(nx, ny)
            if abs(wp.x() - wx) < 10 and abs(wp.y() - wy) < 10:
                self._drag_idx = i
                return
        # add new point
        nx, ny = self._to_norm(wx, wy)
        insert_at = sum(1 for px, _ in self._points if px < nx)
        self._points.insert(insert_at, [nx, ny])
        self._drag_idx = insert_at
        self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:     # noqa: N802
        if self._drag_idx < 0:
            return
        i = self._drag_idx
        nx, ny = self._to_norm(e.position().x(), e.position().y())
        # clamp between neighbours
        lo_x = self._points[i - 1][0] + 0.01 if i > 0 else 0.0
        hi_x = self._points[i + 1][0] - 0.01 if i < len(self._points) - 1 else 1.0
        self._points[i] = [max(lo_x, min(hi_x, nx)), ny]
        self.update()

    def mouseReleaseEvent(self, _e) -> None:              # noqa: N802
        self._drag_idx = -1

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:   # noqa: N802
        # remove an editable point on double-click
        wx, wy = e.position().x(), e.position().y()
        for i in range(len(self._points) - 1, 0, -1):
            if i == len(self._points) - 1:
                continue
            nx, ny = self._points[i]
            wp = self._to_widget(nx, ny)
            if abs(wp.x() - wx) < 10 and abs(wp.y() - wy) < 10:
                self._points.pop(i)
                self.update()
                return


# ══════════════════════════════════════════════════════════════════════════════
# COLOR WHEEL  (颜色分级 section)
# ══════════════════════════════════════════════════════════════════════════════

class ColorWheelWidget(QWidget):
    """Circular hue-saturation wheel with a draggable colour dot."""

    _R = 52   # outer radius

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        size = self._R * 2 + 4
        self.setFixedSize(size, size)
        self._hue = 0.0        # 0..360
        self._sat = 0.0        # 0..1  (distance from centre)
        self._dragging = False

    # ── helpers ──────────────────────────────────────────────────────────────
    def _centre(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _dot_pos(self) -> QPointF:
        cx, cy = self._centre().x(), self._centre().y()
        angle = math.radians(self._hue)
        r = self._sat * self._R
        return QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle))

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:         # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self._centre()
        R  = float(self._R)

        # draw a conical-gradient "wheel" ring
        for deg in range(360):
            col = QColor.fromHsvF(deg / 360.0, 1.0, 0.85)
            col.setAlphaF(0.9)
            pen = QPen(col, 2)
            p.setPen(pen)
            a0 = math.radians(deg)
            a1 = math.radians(deg + 1)
            p.drawLine(
                QPointF(cx.x() + R * math.cos(a0), cx.y() - R * math.sin(a0)),
                QPointF(cx.x() + (R + 2) * math.cos(a0), cx.y() - (R + 2) * math.sin(a0)),
            )
        # white-to-transparent radial fill inside wheel
        grad = QLinearGradient(cx.x() - R, cx.y(), cx.x() + R, cx.y())
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        # darker inner circle background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C_BG_ITEM)))
        p.drawEllipse(cx, R - 1.0, R - 1.0)

        # ring border
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx, R + 1.0, R + 1.0)

        # cross-hair at centre
        p.setPen(QPen(QColor(C_TEXT_4), 1))
        p.drawLine(QPointF(cx.x() - 5, cx.y()), QPointF(cx.x() + 5, cx.y()))
        p.drawLine(QPointF(cx.x(), cx.y() - 5), QPointF(cx.x(), cx.y() + 5))

        # dot
        dp = self._dot_pos()
        dot_col = QColor.fromHsvF(self._hue / 360.0, max(self._sat, 0.01), 0.9)
        p.setBrush(QBrush(dot_col))
        p.setPen(QPen(QColor(C_WHITE), 1.5))
        p.drawEllipse(dp, 6.0, 6.0)
        p.end()

    # ── interaction ──────────────────────────────────────────────────────────
    def _update_from_pos(self, pos: QPointF) -> None:
        cx, cy = self._centre().x(), self._centre().y()
        dx, dy = pos.x() - cx, -(pos.y() - cy)
        dist = math.hypot(dx, dy)
        self._sat = min(1.0, dist / self._R)
        self._hue = math.degrees(math.atan2(dy, dx)) % 360
        self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:   # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._update_from_pos(e.position())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:    # noqa: N802
        if self._dragging:
            self._update_from_pos(e.position())

    def mouseReleaseEvent(self, _e) -> None:             # noqa: N802
        self._dragging = False


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ══════════════════════════════════════════════════════════════════════════════

class RightPanel(QWidget):
    """320 px right panel: panel tabs + layers content."""

    active_layer_changed = pyqtSignal(int)
    layer_visibility_changed = pyqtSignal(int, bool)
    layer_opacity_changed = pyqtSignal(int, float)
    adjust_section_changed = pyqtSignal(str, dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setStyleSheet(
            f"background:{C_BG_RIGHT};"
        )
        self._active_tab = "蒙板"
        self._active_layer = 0
        self._layer_rows: list[LayerRow] = []
        self._layer_list_lo: Optional[QVBoxLayout] = None
        self._build()

    def _build(self) -> None:
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # ── tabs ──────────────────────────────────────────────────────────────
        tab_bar = self._build_tab_bar()
        lo.addWidget(tab_bar)

        # ── stacked content ───────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")

        self._layers_widget = self._build_layers_content()
        self._adjust_widget = self._build_adjust_content()
        self._ai_widget     = self._build_placeholder("AI 助手", "智能增强、降噪、抠图…")
        self._history_widget= self._build_history_content()
        self._portrait_widget=self._build_placeholder("人像",    "皮肤磨皮、五官修整…")
        self._preset_widget = self._build_placeholder("预设",    "常用修图模板与风格预设…")
        self._mask_widget   = self._build_mask_content()

        for w in (self._layers_widget, self._adjust_widget,
                  self._ai_widget, self._history_widget,
                  self._portrait_widget, self._preset_widget,
                  self._mask_widget):
            self._stack.addWidget(w)

        self._stack.setCurrentIndex(6)
        lo.addWidget(self._stack, 1)

    # ── tab bar ───────────────────────────────────────────────────────────────

    # icon name mapped to each tab label
    _TAB_DEFS: list[tuple[str, str]] = [
        ("调整", "sliders-horizontal"),
        ("蒙板", "circle-dashed"),
        ("图层", "layers"),
        ("AI",   "wand-2"),
        ("历史", "clock"),
        ("人像", "user"),
        ("预设", "bookmark"),
    ]

    def _build_tab_bar(self) -> QWidget:
        # Flat underline-style tab bar (36 px height)
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background:{C_BG_RIGHT}; border-bottom:1px solid {C_BORDER_P};"
        )
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(4, 0, 4, 0)
        lo.setSpacing(0)

        self._tab_buttons: dict[str, QPushButton] = {}
        for tab, icon_name in self._TAB_DEFS:
            btn = QPushButton(tab)
            btn.setCheckable(True)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _, t=tab: self._on_tab(t))

            # stash icon name for potential future use
            btn._tab_icon_name = icon_name  # type: ignore[attr-defined]

            self._tab_buttons[tab] = btn
            lo.addWidget(btn)

        self._refresh_tabs()
        return bar

    def _on_tab(self, tab: str) -> None:
        self._active_tab = tab
        self._refresh_tabs()
        tab_order = ["调整", "蒙板", "图层", "AI", "历史", "人像", "预设"]
        idx = tab_order.index(tab) if tab in tab_order else 0
        stack_map = {"图层": 0, "调整": 1, "AI": 2, "历史": 3, "人像": 4, "预设": 5, "蒙板": 6}
        self._stack.setCurrentIndex(stack_map.get(tab, 0))

    def _refresh_tabs(self) -> None:
        for tab, btn in self._tab_buttons.items():
            active = (tab == self._active_tab)
            btn.setChecked(active)
            text_color = C_PRIMARY if active else C_TEXT_3
            # Active tab: blue text + blue 2px bottom border; inactive: transparent
            if active:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent; border:none;"
                    f"border-bottom:2px solid {C_PRIMARY};"
                    f"color:{text_color}; font-size:12px; font-weight:500;"
                    f"padding:0 2px;}}"
                    f"QPushButton:hover{{color:{C_PRIMARY};}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent; border:none;"
                    f"border-bottom:2px solid transparent;"
                    f"color:{text_color}; font-size:12px;"
                    f"padding:0 2px;}}"
                    f"QPushButton:hover{{color:{C_TEXT_1}; border-bottom:2px solid {C_BORDER};}}"
                )

    # ── layers panel content ──────────────────────────────────────────────────
    def _build_layers_content(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(w)
        lo.setContentsMargins(12, 12, 12, 0)
        lo.setSpacing(12)

        # blend mode row
        blend_row = QWidget()
        blend_lo = QHBoxLayout(blend_row)
        blend_lo.setContentsMargins(0, 0, 0, 0)
        blend_lo.setSpacing(8)
        blend_lo.addWidget(_lbl("混合", C_TEXT_3, 12))

        blend_sel = QWidget()
        blend_sel.setFixedHeight(28)
        blend_sel.setStyleSheet(
            f"background:{C_BG_PANEL}; border-radius:6px;"
            f"border:1px solid {C_BORDER};"
        )
        blend_sel_lo = QHBoxLayout(blend_sel)
        blend_sel_lo.setContentsMargins(8, 0, 8, 0)
        blend_sel_lo.setSpacing(0)
        blend_sel_lo.addWidget(_lbl("正常", C_TEXT_1, 12))
        blend_sel_lo.addStretch()
        chev_lbl = QLabel()
        chev_lbl.setPixmap(icon_pixmap("chevron-down", 12, C_TEXT_4))
        chev_lbl.setFixedSize(12, 12)
        blend_sel_lo.addWidget(chev_lbl)
        blend_lo.addWidget(blend_sel, 1)
        lo.addWidget(blend_row)

        # opacity row
        opacity_row = QWidget()
        op_lo = QHBoxLayout(opacity_row)
        op_lo.setContentsMargins(0, 0, 0, 0)
        op_lo.setSpacing(8)
        op_lo.addWidget(_lbl("透明度", C_TEXT_3, 12))

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setFixedHeight(4)
        self._opacity_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{background:{C_BG_ITEM};"
            f"height:4px; border-radius:2px;}}"
            f"QSlider::sub-page:horizontal{{background:{C_PRIMARY};"
            f"height:4px; border-radius:2px;}}"
            f"QSlider::handle:horizontal{{background:{C_BG_PANEL};"
            f"border:2px solid {C_PRIMARY}; width:12px; height:12px;"
            f"border-radius:6px; margin:-4px 0;}}"
        )
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        op_lo.addWidget(self._opacity_slider, 1)

        self._opacity_lbl = _lbl("100%", C_TEXT_1, 12, QFont.Weight.Medium)
        self._opacity_lbl.setFixedWidth(34)
        op_lo.addWidget(self._opacity_lbl)
        lo.addWidget(opacity_row)

        lo.addWidget(_hline())

        # layer list
        layer_list_w = QWidget()
        layer_list_lo = QVBoxLayout(layer_list_w)
        layer_list_lo.setContentsMargins(0, 0, 0, 0)
        layer_list_lo.setSpacing(2)
        self._layer_list_lo = layer_list_lo
        self.set_malayers([])

        lo.addWidget(layer_list_w, 1)

        # actions bar
        lo.addWidget(self._build_layer_actions())
        return w

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_lbl.setText(f"{value}%")
        self.layer_opacity_changed.emit(self._active_layer, value / 100.0)

    def _on_layer_selected(self, idx: int) -> None:
        for i, row in enumerate(self._layer_rows):
            row.set_active(i == idx)
        self._active_layer = idx
        self.active_layer_changed.emit(idx)

    def _on_layer_visibility(self, idx: int, visible: bool) -> None:
        self.layer_visibility_changed.emit(idx, visible)

    def set_malayers(self, malayers: list) -> None:
        if self._layer_list_lo is None:
            return
        while self._layer_list_lo.count():
            item = self._layer_list_lo.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._layer_rows.clear()

        if not malayers:
            placeholder = _lbl("No layers", C_TEXT_4, 12)
            placeholder.setFixedHeight(36)
            self._layer_list_lo.addWidget(placeholder)
            self._opacity_slider.blockSignals(True)
            self._opacity_slider.setValue(100)
            self._opacity_slider.blockSignals(False)
            self._active_layer = 0
            return

        for idx, malayer in enumerate(malayers):
            layer_type = getattr(malayer, "tab_id", getattr(malayer, "type_name", "layer"))
            row = LayerRow(idx, malayer.name, layer_type, "#404040", idx == 0, malayer.locked)
            row._eye_btn.setChecked(malayer.visible)
            row.selected.connect(self._on_layer_selected)
            row.visibility_toggled.connect(self._on_layer_visibility)
            self._layer_rows.append(row)
            self._layer_list_lo.addWidget(row)

        self._active_layer = 0
        self._opacity_slider.blockSignals(True)
        self._opacity_slider.setValue(int(getattr(malayers[0], "opacity", 1.0) * 100))
        self._opacity_slider.blockSignals(False)

    def _build_layer_actions(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"border-top:1px solid {C_BORDER}; background:transparent;")
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(4, 0, 4, 0)
        lo.setSpacing(4)
        lo.addStretch()

        for icon_name, tip in (
            ("plus",          "新建图层"),
            ("folder-plus",   "新建组"),
            ("trash-2",       "删除图层"),
            ("circle-dashed", "添加蒙板"),
            ("arrow-up",      "上移图层"),
            ("arrow-down",    "下移图层"),
            ("more-horizontal","更多"),
        ):
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setIcon(_qicon(icon_name, 14, "#999999"))
            btn.setIconSize(QSize(14, 14))
            btn.setStyleSheet(
                f"background:{C_BG_PANEL}; border:1px solid {C_BORDER};"
                f"border-radius:6px;"
                f"QPushButton:hover{{background:#2a2a2a; border-color:#444;}}"
            )
            lo.addWidget(btn)

        lo.addStretch()
        return bar

    def _build_placeholder(self, title: str, desc: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(w)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(_lbl(title, C_TEXT_1, 14, QFont.Weight.Medium),
                     alignment=Qt.AlignmentFlag.AlignCenter)
        lo.addSpacing(8)
        lo.addWidget(_lbl(desc, C_TEXT_3, 12),
                     alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    def _mask_title(self, text: str) -> QLabel:
        return _lbl(text, C_TEXT_1, 13, QFont.Weight.Medium)

    def _mask_subtitle(self, text: str) -> QLabel:
        lbl = _lbl(text, C_TEXT_3, 11)
        lbl.setWordWrap(True)
        return lbl

    def _build_mask_tool_button(self, text: str, *, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(58, 52)
        btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_RIGHT}; color:{C_TEXT_3};"
            f"border:1px solid {C_BORDER}; border-radius:8px; font-size:10px;"
            f"padding-top:18px; padding-bottom:8px; text-align:center;}}"
            f"QPushButton:hover{{border-color:#4a4a4a; color:{C_TEXT_2};}}"
            f"QPushButton:checked{{background:{C_BG_ACTIVE}; color:{C_PRIMARY_H};"
            f"border:1px solid {C_PRIMARY};}}"
        )
        return btn

    def _build_mask_chip(self, text: str, *, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setMinimumHeight(28)
        btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_2}; border:none;"
            f"border-radius:14px; padding:0 12px; font-size:11px;}}"
            f"QPushButton:hover{{background:#363636; color:{C_TEXT_1};}}"
            f"QPushButton:checked{{background:{C_BG_ACTIVE}; color:{C_PRIMARY_H};"
            f"border:1px solid {C_PRIMARY}; padding:0 11px;}}"
        )
        return btn

    def _add_mask_slider_row(self, parent_lo: QVBoxLayout, label: str, value: int) -> None:
        row = QWidget()
        row_lo = QHBoxLayout(row)
        row_lo.setContentsMargins(0, 0, 0, 0)
        row_lo.setSpacing(8)

        row_lo.addWidget(_lbl(label, C_TEXT_2, 11))

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(value)
        slider.setFixedHeight(18)
        slider.setStyleSheet(
            f"QSlider::groove:horizontal{{background:{C_BG_ITEM}; height:4px; border-radius:2px;}}"
            f"QSlider::sub-page:horizontal{{background:{C_PRIMARY}; height:4px; border-radius:2px;}}"
            f"QSlider::add-page:horizontal{{background:{C_BG_ITEM}; height:4px; border-radius:2px;}}"
            f"QSlider::handle:horizontal{{background:{C_BG_PANEL}; border:2px solid {C_PRIMARY};"
            f"width:10px; height:10px; border-radius:5px; margin:-4px 0;}}"
        )
        row_lo.addWidget(slider, 1)

        value_lbl = _lbl(str(value), C_TEXT_2, 11)
        value_lbl.setFixedWidth(24)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda v, lb=value_lbl: lb.setText(str(v)))
        row_lo.addWidget(value_lbl)
        parent_lo.addWidget(row)

    def _build_mask_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent; border:none;}}"
            f"QScrollBar:vertical{{background:transparent; width:8px; margin:8px 0;}}"
            f"QScrollBar::handle:vertical{{background:#3a3a3a; border-radius:4px; min-height:24px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
            f"QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{{background:transparent;}}"
        )

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(body)
        lo.setContentsMargins(14, 14, 14, 16)
        lo.setSpacing(12)

        lo.addWidget(self._mask_title("蒙板工具"))
        tools = QWidget()
        tools_lo = QHBoxLayout(tools)
        tools_lo.setContentsMargins(0, 0, 0, 0)
        tools_lo.setSpacing(8)
        for text, active in (("画笔", True), ("线性渐变", False), ("径向渐变", False), ("智能识别", False)):
            tools_lo.addWidget(self._build_mask_tool_button(text, active=active))
        lo.addWidget(tools)

        lo.addWidget(_hline())
        lo.addWidget(self._mask_title("智能识别"))
        lo.addWidget(self._mask_subtitle("点击选择要识别的区域"))

        lo.addWidget(_lbl("场景", C_TEXT_2, 12, QFont.Weight.Medium))
        scene_row = QWidget()
        scene_lo = QHBoxLayout(scene_row)
        scene_lo.setContentsMargins(0, 0, 0, 0)
        scene_lo.setSpacing(8)
        for text, active in (("背景", False), ("天空", False), ("建筑", False)):
            scene_lo.addWidget(self._build_mask_chip(text, active=active))
        scene_lo.addStretch()
        lo.addWidget(scene_row)

        lo.addWidget(_lbl("生物", C_TEXT_2, 12, QFont.Weight.Medium))
        bio_row = QWidget()
        bio_lo = QHBoxLayout(bio_row)
        bio_lo.setContentsMargins(0, 0, 0, 0)
        bio_lo.setSpacing(8)
        for text, active in (("人物", True), ("鸟", False), ("动物", False)):
            bio_lo.addWidget(self._build_mask_chip(text, active=active))
        bio_lo.addStretch()
        lo.addWidget(bio_row)

        person_box = QFrame()
        person_box.setStyleSheet(f"background:{C_BG_ITEM}; border-radius:8px;")
        person_lo = QVBoxLayout(person_box)
        person_lo.setContentsMargins(10, 10, 10, 10)
        person_lo.setSpacing(8)
        person_lo.addWidget(_lbl("人物细分", C_TEXT_3, 11))

        fine_row1 = QWidget()
        fine_row1_lo = QHBoxLayout(fine_row1)
        fine_row1_lo.setContentsMargins(0, 0, 0, 0)
        fine_row1_lo.setSpacing(8)
        for text, active in (("全身", True), ("皮肤", False), ("衣服", False)):
            fine_row1_lo.addWidget(self._build_mask_chip(text, active=active))
        fine_row1_lo.addStretch()
        person_lo.addWidget(fine_row1)

        fine_row2 = QWidget()
        fine_row2_lo = QHBoxLayout(fine_row2)
        fine_row2_lo.setContentsMargins(0, 0, 0, 0)
        fine_row2_lo.setSpacing(8)
        for text in ("面部皮肤", "身体皮肤", "头发", "眼睛", "嘴唇"):
            fine_row2_lo.addWidget(self._build_mask_chip(text))
        person_lo.addWidget(fine_row2)
        lo.addWidget(person_box)

        lo.addWidget(_hline())
        lo.addWidget(self._mask_title("画笔设置"))
        self._add_mask_slider_row(lo, "大小", 50)
        self._add_mask_slider_row(lo, "羽化", 20)
        self._add_mask_slider_row(lo, "流量", 75)
        self._add_mask_slider_row(lo, "不透明", 100)

        header_row = QWidget()
        header_lo = QHBoxLayout(header_row)
        header_lo.setContentsMargins(0, 0, 0, 0)
        header_lo.setSpacing(8)
        header_lo.addWidget(self._mask_title("已创建蒙板"))
        header_lo.addStretch()
        header_lo.addWidget(_lbl("3", C_TEXT_3, 12))
        lo.addWidget(header_row)

        for text, active in (("画笔蒙板 1", True), ("人物-全身", False), ("径向渐变 1", False)):
            item = QPushButton(text)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            item.setFixedHeight(36)
            item.setStyleSheet(
                f"QPushButton{{text-align:left; padding:0 14px; border-radius:8px;"
                f"background:{C_BG_ACTIVE if active else C_BG_RIGHT};"
                f"color:{C_PRIMARY_H if active else C_TEXT_2}; border:1px solid "
                f"{C_PRIMARY if active else C_BORDER}; font-size:12px;}}"
                f"QPushButton:hover{{border-color:{C_PRIMARY if active else '#4a4a4a'};}}"
            )
            lo.addWidget(item)

        action_row = QWidget()
        action_lo = QHBoxLayout(action_row)
        action_lo.setContentsMargins(0, 4, 0, 0)
        action_lo.setSpacing(8)

        add_btn = QPushButton("+ 新建蒙板")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(
            f"QPushButton{{background:{C_PRIMARY}; color:#ffffff; border:none; border-radius:6px;"
            f"padding:0 16px; font-size:12px; font-weight:500;}}"
            f"QPushButton:hover{{background:{C_PRIMARY_H};}}"
        )
        action_lo.addWidget(add_btn, 1)

        invert_btn = QPushButton("反选")
        invert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        invert_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        invert_btn.setFixedHeight(34)
        invert_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:{C_TEXT_2}; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:0 14px; font-size:12px;}}"
            f"QPushButton:hover{{border-color:#4a4a4a; color:{C_TEXT_1};}}"
        )
        action_lo.addWidget(invert_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        delete_btn.setFixedHeight(34)
        delete_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:#d66; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:0 14px; font-size:12px;}}"
            f"QPushButton:hover{{border-color:#6a3a3a; background:#2a1f1f;}}"
        )
        action_lo.addWidget(delete_btn)
        lo.addWidget(action_row)

        note_box = QFrame()
        note_box.setStyleSheet(f"background:{C_BG_ITEM}; border-radius:8px;")
        note_lo = QVBoxLayout(note_box)
        note_lo.setContentsMargins(10, 10, 10, 10)
        note_lo.setSpacing(4)
        note_lo.addWidget(_lbl("蒙板使用说明", C_TEXT_2, 11, QFont.Weight.Medium))
        for line in (
            "• 画板相当于在图层中创建一个编辑范围",
            "• 选中区域可使用【调整】中的所有功能",
            "• 支持多个蒙板叠加编辑",
        ):
            note_lo.addWidget(_lbl(line, C_TEXT_4, 10))
        lo.addWidget(note_box)

        lo.addStretch()
        scroll.setWidget(body)
        return scroll

    def _build_history_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent; border:none;}}"
            f"QScrollBar:vertical{{background:transparent; width:8px; margin:8px 0;}}"
            f"QScrollBar::handle:vertical{{background:#3a3a3a; border-radius:4px; min-height:24px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
            f"QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{{background:transparent;}}"
        )

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(body)
        lo.setContentsMargins(16, 18, 16, 16)
        lo.setSpacing(10)

        history_items = [
            ("image", "原始状态", None, False),
            ("sun-medium", "调整曝光 +0.5", None, False),
            ("circle-half-stroke", "调整对比度 +10", None, False),
            ("thermometer", "调整色温 -5", None, False),
            ("droplet", "调整饱和度 +8", None, False),
            ("circle-dashed", "添加蒙版", None, False),
            ("sparkles", "AI 自动增强", "Just now", True),
        ]
        for icon_name, text, meta, active in history_items:
            lo.addWidget(self._build_history_row(icon_name, text, meta, active))

        lo.addStretch()
        scroll.setWidget(body)
        return scroll

    def _build_history_row(
        self,
        icon_name: str,
        text: str,
        meta: Optional[str] = None,
        active: bool = False,
    ) -> QWidget:
        row = QWidget()
        row.setFixedHeight(42 if active else 34)
        row.setStyleSheet(
            f"background:{C_BG_ACTIVE if active else 'transparent'};"
            f"border-radius:{8 if active else 6}px;"
        )

        lo = QHBoxLayout(row)
        lo.setContentsMargins(12 if active else 8, 0, 12 if active else 8, 0)
        lo.setSpacing(10)

        icon_lbl = QLabel()
        icon_color = C_PRIMARY if active else C_TEXT_4
        icon_size = 16 if active else 15
        icon_lbl.setPixmap(icon_pixmap(icon_name, icon_size, icon_color))
        icon_lbl.setFixedSize(18, 18)
        lo.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        text_color = C_PRIMARY if active else C_TEXT_2
        weight = QFont.Weight.Medium if active else QFont.Weight.Normal
        lo.addWidget(_lbl(text, text_color, 12, weight), 0, Qt.AlignmentFlag.AlignVCenter)

        if meta:
            lo.addSpacing(2)
            lo.addWidget(_lbl(meta, C_TEXT_2, 11), 0, Qt.AlignmentFlag.AlignVCenter)

        lo.addStretch()
        return row

    # ── 调整 tab ──────────────────────────────────────────────────────────────

    def _build_adjust_content(self) -> QScrollArea:
        """Scrollable 调整 (Adjustments) panel: histogram + collapsible sections."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent; border:none;}"
            "QScrollArea > QWidget{background:transparent; border:none;}"
            "QScrollBar:vertical{background:transparent; width:4px; border:none; border-radius:2px;}"
            "QScrollBar::groove:vertical{background:transparent; border:none; width:4px;}"
            f"QScrollBar::handle:vertical{{background:{C_BORDER}; border:none; border-radius:2px; min-height:20px;}}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0; border:none;}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical{background:transparent; border:none;}"
        )

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(inner)
        lo.setContentsMargins(0, 8, 0, 16)
        lo.setSpacing(0)

        # histogram + EXIF bar
        hist_wrap = QWidget()
        hist_lo = QVBoxLayout(hist_wrap)
        hist_lo.setContentsMargins(8, 0, 8, 0)
        hist_lo.setSpacing(0)
        hist_lo.addWidget(self._build_histogram_bar())
        lo.addWidget(hist_wrap)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER_P}; border:none;")
        lo.addWidget(sep)

        # collapsible sections
        _SECTIONS = [
            ("白平衡",    True,  ""),
            ("影调",      False, ""),
            ("色阶",      False, ""),
            ("曲线",      False, ""),
            ("HSL",       False, ""),
            ("色彩编辑器", False, ""),
            ("颜色分级",  False, ""),
            ("可选颜色",  False, ""),
            ("细节",      False, ""),
            ("镜头",      False, ""),
            ("透视矫正",  False, ""),
            ("颜色校准",  False, ""),
        ]
        _BUILDERS = {
            "白平衡":   self._build_wb_content,
            "影调":     self._build_tone_content,
            "色阶":     self._build_levels_content,
            "曲线":     self._build_curves_content,
            "HSL":      self._build_hsl_content,
            "颜色分级": self._build_color_grading_content,
            "可选颜色": self._build_selective_color_content,
            "细节":     self._build_detail_content,
            "镜头":     self._build_lens_content,
            "透视矫正": self._build_perspective_content,
            "颜色校准": self._build_color_calibration_content,
        }
        for i, (title, expanded, badge) in enumerate(_SECTIONS):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{C_BORDER_P}; border:none;")
                lo.addWidget(sep)
            sec = AdjustSection(title, expanded=expanded, badge=badge)
            builder = _BUILDERS.get(title)
            if builder:
                builder(sec.content_lo)
            lo.addWidget(sec)

        lo.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_histogram_bar(self) -> QWidget:
        """Histogram canvas with EXIF info row below it."""
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 4)
        lo.setSpacing(4)

        lo.addWidget(_HistogramCanvas())

        exif_row = QWidget()
        exif_lo = QHBoxLayout(exif_row)
        exif_lo.setContentsMargins(2, 0, 2, 0)
        exif_lo.setSpacing(8)
        for txt in ("ISO 100", "129mm", "F/2.8", "1/200s"):
            exif_lo.addWidget(_lbl(txt, C_TEXT_4, 11))

        jpg_lbl = QLabel("JPG")
        jpg_lbl.setStyleSheet(
            f"color:{C_TEXT_3}; background:{C_BG_ITEM}; font-size:10px;"
            "border-radius:3px; padding:1px 5px;"
        )
        exif_lo.addWidget(jpg_lbl)
        exif_lo.addStretch()
        lo.addWidget(exif_row)
        return w

    def _build_wb_content(self, lo: QVBoxLayout) -> None:
        """White-balance section body: preset dropdown + 色温 + 色调 sliders."""
        # preset dropdown row
        preset_row = QWidget()
        preset_row.setStyleSheet("background:transparent;")
        p_lo = QHBoxLayout(preset_row)
        p_lo.setContentsMargins(0, 0, 0, 0)
        p_lo.setSpacing(6)
        p_lo.addWidget(_lbl("白平衡", C_TEXT_3, 12))

        dd = QWidget()
        dd.setFixedHeight(26)
        dd.setStyleSheet(
            f"background:{C_BG_ITEM}; border-radius:5px; border:1px solid {C_BORDER};"
        )
        dd_lo = QHBoxLayout(dd)
        dd_lo.setContentsMargins(8, 0, 6, 0)
        dd_lo.setSpacing(0)
        dd_lo.addWidget(_lbl("自定义", C_TEXT_1, 12))
        dd_lo.addStretch()
        chev = QLabel()
        chev.setPixmap(icon_pixmap("chevron-down", 10, C_TEXT_4))
        chev.setFixedSize(10, 10)
        dd_lo.addWidget(chev)
        p_lo.addWidget(dd, 1)
        lo.addWidget(preset_row)

        lo.addSpacing(4)

        # 色温: cool (blue-purple) → warm (yellow)
        self._add_gradient_slider_row(
            lo, "色温", 0, "#9988ff", "#ffcc44", -100, 100, 0,
            on_change=lambda value: self.adjust_section_changed.emit(
                "white_balance", {"temperature": value}
            ),
        )
        # 色调: green → magenta
        self._add_gradient_slider_row(
            lo, "色调", 0, "#44bb44", "#cc44cc", -100, 100, 0,
            on_change=lambda value: self.adjust_section_changed.emit(
                "white_balance", {"tint": value}
            ),
        )

    def _add_gradient_slider_row(
        self, lo: QVBoxLayout,
        label: str, value: int,
        left_color: str, right_color: str,
        min_val: int, max_val: int, default: int,
        on_change=None,
    ) -> None:
        """Append a labelled GradientSlider row to *lo*."""
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        row_lo = QVBoxLayout(row)
        row_lo.setContentsMargins(0, 0, 0, 0)
        row_lo.setSpacing(2)

        # label + current value
        top = QWidget()
        top.setStyleSheet("background:transparent;")
        top_lo = QHBoxLayout(top)
        top_lo.setContentsMargins(0, 0, 0, 0)
        top_lo.setSpacing(0)
        top_lo.addWidget(_lbl(label, C_TEXT_2, 12))
        top_lo.addStretch()
        val_lbl = _lbl(str(value), C_TEXT_4, 11)
        top_lo.addWidget(val_lbl)
        row_lo.addWidget(top)

        slider = GradientSlider(left_color, right_color, min_val, max_val, value)
        def _handle_value_changed(v: int, lb=val_lbl, cb=on_change) -> None:
            lb.setText(str(v))
            if cb is not None:
                cb(v)

        slider.value_changed.connect(_handle_value_changed)
        row_lo.addWidget(slider)

        lo.addWidget(row)

    # ── 影调 section ──────────────────────────────────────────────────────────

    def _build_tone_content(self, lo: QVBoxLayout) -> None:
        """Tone section: 曝光/对比度/亮度/高光/阴影/白色/黑色."""
        _SLIDERS = [
            ("曝光",  0,   "#1a1a1a", "#ffffff", -200, 200),
            ("对比度", 0,  "#1a1a1a", "#ffffff", -100, 100),
            ("亮度",  0,   "#1a1a1a", "#f0f0f0", -100, 100),
            ("高光",  0,   "#888888", "#ffffff", -100, 100),
            ("阴影",  0,   "#000000", "#888888", -100, 100),
            ("白色",  0,   "#666666", "#ffffff", -100, 100),
            ("黑色",  0,   "#000000", "#555555", -100, 100),
        ]
        for label, val, lc, rc, mn, mx in _SLIDERS:
            self._add_gradient_slider_row(lo, label, val, lc, rc, mn, mx, 0)

    # ── 色阶 section ──────────────────────────────────────────────────────────

    def _build_levels_content(self, lo: QVBoxLayout) -> None:
        """Levels section: input/output black-white point sliders."""
        lo.addWidget(_lbl("输入色阶", C_TEXT_3, 11))
        self._add_gradient_slider_row(
            lo, "暗部", 0, "#000000", "#ffffff", 0, 255, 0
        )
        self._add_gradient_slider_row(
            lo, "亮部", 255, "#000000", "#ffffff", 0, 255, 255
        )
        lo.addSpacing(4)
        lo.addWidget(_lbl("输出色阶", C_TEXT_3, 11))
        self._add_gradient_slider_row(
            lo, "暗部", 0, "#000000", "#ffffff", 0, 255, 0
        )
        self._add_gradient_slider_row(
            lo, "亮部", 255, "#000000", "#ffffff", 0, 255, 255
        )

    # ── 曲线 section ──────────────────────────────────────────────────────────

    def _build_curves_content(self, lo: QVBoxLayout) -> None:
        """Curves section: circle-style channel selector + interactive curve editor."""
        btn_row = QWidget()
        btn_row.setStyleSheet("background:transparent;")
        btn_lo = QHBoxLayout(btn_row)
        btn_lo.setContentsMargins(0, 0, 0, 4)
        btn_lo.setSpacing(6)

        # S-curve preset icon (left icon button)
        s_btn = QPushButton()
        s_btn.setFixedSize(28, 28)
        s_btn.setToolTip("S 曲线")
        s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        s_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        s_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; border-radius:6px; border:1px solid {C_BORDER};}}"
            f"QPushButton:hover{{background:#3a3a3a; border-color:#555;}}"
        )
        s_btn.setIcon(_qicon("trending-up", 14, C_TEXT_3))
        s_btn.setIconSize(QSize(14, 14))
        btn_lo.addWidget(s_btn)

        # Circle channel buttons: composite, white, red, green, blue
        _CH_CIRCLES = [
            ("RGB", "#cccccc", True),
            ("亮度", "#ffffff", False),
            ("R",   "#ff4444", False),
            ("G",   "#44cc44", False),
            ("B",   "#4488ff", False),
        ]
        self._curve_btns: list[QPushButton] = []
        self._curve_editors: dict[str, CurveEditor] = {}

        for ch_label, ch_color, active in _CH_CIRCLES:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setCheckable(True)
            b.setChecked(active)
            b.setToolTip(ch_label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            border = f"2px solid {C_WHITE}" if active else f"1px solid {C_BORDER}"
            b.setStyleSheet(
                f"QPushButton{{background:{ch_color}; border-radius:11px; border:{border};}}"
                f"QPushButton:checked{{border:2px solid {C_WHITE};}}"
                f"QPushButton:hover{{border:2px solid #999999;}}"
            )
            b._ch_label = ch_label   # type: ignore[attr-defined]
            b._ch_color = ch_color   # type: ignore[attr-defined]
            b.clicked.connect(lambda _, bn=b: self._on_curve_channel(bn))
            btn_lo.addWidget(b)
            self._curve_btns.append(b)

        btn_lo.addStretch()
        # auto-adjust icon
        auto_btn = QPushButton()
        auto_btn.setFixedSize(24, 24)
        auto_btn.setToolTip("自动调整")
        auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_btn.setStyleSheet(
            "QPushButton{background:transparent; border:none;}"
            "QPushButton:hover{background:#333; border-radius:4px;}"
        )
        auto_btn.setIcon(_qicon("crosshair", 13, C_TEXT_4))
        auto_btn.setIconSize(QSize(13, 13))
        btn_lo.addWidget(auto_btn)
        lo.addWidget(btn_row)

        # curve editors (stacked, show/hide by channel)
        _CH_EDITORS = [
            ("RGB", "#cccccc", True),
            ("亮度", "#ffffff", False),
            ("R",   "#ff4444", False),
            ("G",   "#44cc44", False),
            ("B",   "#4488ff", False),
        ]
        for ch_label, ch_color, active in _CH_EDITORS:
            ed = CurveEditor(curve_color=ch_color, height=150)
            ed.setVisible(active)
            self._curve_editors[ch_label] = ed
            lo.addWidget(ed)

        # axis labels
        label_row = QWidget()
        label_row.setStyleSheet("background:transparent;")
        lr_lo = QHBoxLayout(label_row)
        lr_lo.setContentsMargins(4, 2, 4, 0)
        lr_lo.setSpacing(0)
        lr_lo.addWidget(_lbl("阴影", C_TEXT_4, 10))
        lr_lo.addStretch()
        lr_lo.addWidget(_lbl("中间调", C_TEXT_4, 10))
        lr_lo.addStretch()
        lr_lo.addWidget(_lbl("高光", C_TEXT_4, 10))
        lo.addWidget(label_row)

    def _on_curve_channel(self, clicked_btn: QPushButton) -> None:
        for b in self._curve_btns:
            active = (b is clicked_btn)
            b.setChecked(active)
            col = b._ch_color  # type: ignore[attr-defined]
            border = f"2px solid {C_WHITE}" if active else f"1px solid {C_BORDER}"
            b.setStyleSheet(
                f"QPushButton{{background:{col}; border-radius:11px; border:{border};}}"
                f"QPushButton:checked{{border:2px solid {C_WHITE};}}"
                f"QPushButton:hover{{border:2px solid #999999;}}"
            )
            self._curve_editors[b._ch_label].setVisible(active)   # type: ignore[attr-defined]

    # ── HSL section ───────────────────────────────────────────────────────────

    def _build_hsl_content(self, lo: QVBoxLayout) -> None:
        """HSL section: 色相/饱和度/明亮度 tab buttons + 8 gradient sliders."""
        # sub-tab buttons
        tab_row = QWidget()
        tab_row.setStyleSheet("background:transparent;")
        tr_lo = QHBoxLayout(tab_row)
        tr_lo.setContentsMargins(0, 0, 0, 0)
        tr_lo.setSpacing(4)

        self._hsl_mode = "色相"
        self._hsl_btns: dict[str, QPushButton] = {}
        self._hsl_slider_groups: dict[str, QWidget] = {}

        # pill-container row: [色相] [饱和度] [明亮度] + target icon
        pill_w = QWidget()
        pill_w.setFixedHeight(30)
        pill_w.setStyleSheet(
            f"background:{C_BG_ITEM}; border-radius:6px;"
        )
        pill_lo = QHBoxLayout(pill_w)
        pill_lo.setContentsMargins(2, 2, 2, 2)
        pill_lo.setSpacing(0)

        _HSL_TABS = ["色相", "饱和度", "明亮度"]
        for mode in _HSL_TABS:
            b = QPushButton(mode)
            b.setCheckable(True)
            b.setChecked(mode == "色相")
            b.setFixedHeight(26)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            active = (mode == "色相")
            b.setStyleSheet(
                f"QPushButton{{background:{'#3a3a3a' if active else 'transparent'};"
                f"color:{C_TEXT_1 if active else C_TEXT_3};"
                f"border-radius:4px; border:none; font-size:12px; font-weight:{'500' if active else 'normal'};}}"
                f"QPushButton:hover{{color:{C_TEXT_1}; background:#333333;}}"
            )
            b._hsl_mode = mode  # type: ignore[attr-defined]
            b.clicked.connect(lambda _, bn=b: self._on_hsl_mode(bn))
            pill_lo.addWidget(b)
            self._hsl_btns[mode] = b

        tr_lo.addWidget(pill_w, 1)
        tr_lo.addSpacing(6)

        # target icon button (right side)
        tgt_btn = QPushButton()
        tgt_btn.setFixedSize(26, 26)
        tgt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tgt_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tgt_btn.setToolTip("目标调整工具")
        tgt_btn.setStyleSheet(
            "QPushButton{background:transparent; border:none;}"
            "QPushButton:hover{background:#333; border-radius:4px;}"
        )
        tgt_btn.setIcon(_qicon("crosshair", 14, C_TEXT_4))
        tgt_btn.setIconSize(QSize(14, 14))
        tr_lo.addWidget(tgt_btn)

        lo.addWidget(tab_row)
        lo.addSpacing(4)

        _COLORS = [
            ("红色",  "#ff44aa", "#ff4444"),
            ("橙色",  "#ff4400", "#ffaa00"),
            ("黄色",  "#ffaa00", "#aacc00"),
            ("绿色",  "#aacc00", "#00bbaa"),
            ("浅绿色","#00bbaa", "#0088cc"),
            ("蓝色",  "#0088cc", "#6655ff"),
            ("紫色",  "#6655ff", "#cc44cc"),
            ("洋红色","#cc44cc", "#ff44aa"),
        ]

        for mode in _HSL_TABS:
            grp = QWidget()
            grp.setStyleSheet("background:transparent;")
            grp_lo = QVBoxLayout(grp)
            grp_lo.setContentsMargins(0, 0, 0, 0)
            grp_lo.setSpacing(6)
            for color_name, lc, rc in _COLORS:
                self._add_gradient_slider_row(grp_lo, color_name, 0, lc, rc, -100, 100, 0)
            grp.setVisible(mode == "色相")
            self._hsl_slider_groups[mode] = grp
            lo.addWidget(grp)

    def _on_hsl_mode(self, clicked_btn: QPushButton) -> None:
        for mode, b in self._hsl_btns.items():
            active = (b is clicked_btn)
            b.setChecked(active)
            b.setStyleSheet(
                f"QPushButton{{background:{'#3a3a3a' if active else 'transparent'};"
                f"color:{C_TEXT_1 if active else C_TEXT_3};"
                f"border-radius:4px; border:none; font-size:12px; font-weight:{'500' if active else 'normal'};}}"
                f"QPushButton:hover{{color:{C_TEXT_1}; background:#333333;}}"
            )
            self._hsl_slider_groups[mode].setVisible(active)

    # ── 颜色分级 section ──────────────────────────────────────────────────────

    def _build_color_grading_content(self, lo: QVBoxLayout) -> None:
        """Color grading: sphere preset row + 3 color wheels with lum sliders."""
        # ── preset sphere row ─────────────────────────────────────────────────
        presets_row = QWidget()
        presets_row.setStyleSheet("background:transparent;")
        pr_lo = QHBoxLayout(presets_row)
        pr_lo.setContentsMargins(0, 0, 0, 4)
        pr_lo.setSpacing(8)

        # 4 sphere dots (all / shadows / midtones / highlights)
        _SPHERE_DEFS = [
            ("#5533bb", "#9966ff", True),   # all  – purple-ish
            ("#444444", "#888888", False),  # shadows
            ("#888888", "#aaaaaa", False),  # midtones
            ("#aaaaaa", "#dddddd", False),  # highlights
        ]
        for dark_c, light_c, active in _SPHERE_DEFS:
            dot = QLabel()
            dot.setFixedSize(26, 26)
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            px = QPixmap(26, 26)
            px.fill(Qt.GlobalColor.transparent)
            pp = QPainter(px)
            pp.setRenderHint(QPainter.RenderHint.Antialiasing)
            grad = QLinearGradient(4, 4, 22, 22)
            grad.setColorAt(0.0, QColor(light_c))
            grad.setColorAt(1.0, QColor(dark_c))
            pp.setBrush(QBrush(grad))
            border_pen = QPen(QColor(C_PRIMARY if active else C_BORDER), 1.5)
            pp.setPen(border_pen)
            pp.drawEllipse(2, 2, 22, 22)
            pp.end()
            dot.setPixmap(px)
            pr_lo.addWidget(dot)

        # half-circle / split icon
        half_lbl = QLabel()
        half_lbl.setFixedSize(26, 26)
        half_px = QPixmap(26, 26)
        half_px.fill(Qt.GlobalColor.transparent)
        hp = QPainter(half_px)
        hp.setRenderHint(QPainter.RenderHint.Antialiasing)
        hp.setPen(QPen(QColor(C_TEXT_4), 1.5))
        hp.setBrush(Qt.BrushStyle.NoBrush)
        hp.drawEllipse(3, 3, 20, 20)
        hp.setBrush(QBrush(QColor(C_TEXT_4)))
        path_half = QPainterPath()
        path_half.moveTo(13, 3)
        path_half.arcTo(3, 3, 20, 20, 90, 180)
        path_half.closeSubpath()
        hp.fillPath(path_half, QBrush(QColor(C_TEXT_4)))
        hp.end()
        half_lbl.setPixmap(half_px)
        pr_lo.addWidget(half_lbl)

        pr_lo.addStretch()
        lo.addWidget(presets_row)
        lo.addSpacing(4)

        # ── helper: wheel + lum slider unit ──────────────────────────────────
        def _wheel_unit(label: str, wheel_r: int = 52) -> QWidget:
            """A labelled color wheel with a vertical luminance slider on its left."""
            w = QWidget()
            w.setStyleSheet("background:transparent;")
            w_lo = QVBoxLayout(w)
            w_lo.setContentsMargins(0, 0, 0, 0)
            w_lo.setSpacing(3)
            w_lo.addWidget(
                _lbl(label, C_TEXT_3, 11),
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            r_lo = QHBoxLayout(row)
            r_lo.setContentsMargins(0, 0, 0, 0)
            r_lo.setSpacing(4)

            # left luminance slider (vertical)
            lum = QSlider(Qt.Orientation.Vertical)
            lum.setRange(-100, 100)
            lum.setValue(0)
            lum.setFixedWidth(14)
            lum.setStyleSheet(
                f"QSlider::groove:vertical{{background:{C_BG_ITEM}; width:4px; border-radius:2px;}}"
                f"QSlider::handle:vertical{{background:{C_TEXT_4}; width:10px; height:10px;"
                f"border-radius:5px; margin:-3px 0; left:-3px;}}"
            )

            whl = ColorWheelWidget()
            whl._R = wheel_r  # type: ignore[attr-defined]
            sz = wheel_r * 2 + 4
            whl.setFixedSize(sz, sz)

            r_lo.addWidget(lum, alignment=Qt.AlignmentFlag.AlignVCenter)
            r_lo.addWidget(whl, alignment=Qt.AlignmentFlag.AlignVCenter)
            r_lo.addStretch()
            w_lo.addWidget(row)
            return w

        # midtone (large, centred)
        mid_outer = QWidget()
        mid_outer.setStyleSheet("background:transparent;")
        mid_h = QHBoxLayout(mid_outer)
        mid_h.setContentsMargins(0, 0, 0, 0)
        mid_h.addStretch()
        mid_h.addWidget(_wheel_unit("中间调", wheel_r=50))
        mid_h.addStretch()
        lo.addWidget(mid_outer)
        lo.addSpacing(8)

        # shadows + highlights (smaller, side by side)
        small_row = QWidget()
        small_row.setStyleSheet("background:transparent;")
        sm_lo = QHBoxLayout(small_row)
        sm_lo.setContentsMargins(0, 0, 0, 0)
        sm_lo.setSpacing(8)
        sm_lo.addWidget(_wheel_unit("阴影", wheel_r=36))
        sm_lo.addWidget(_wheel_unit("高光", wheel_r=36))
        lo.addWidget(small_row)

    # ── 可选颜色 section ──────────────────────────────────────────────────────

    def _build_selective_color_content(self, lo: QVBoxLayout) -> None:
        """Selective color: color picker + CMYK sliders."""
        # color selector dropdown
        sel_row = QWidget()
        sel_row.setStyleSheet("background:transparent;")
        sr_lo = QHBoxLayout(sel_row)
        sr_lo.setContentsMargins(0, 0, 0, 0)
        sr_lo.setSpacing(6)
        sr_lo.addWidget(_lbl("颜色", C_TEXT_3, 12))

        dd = QWidget()
        dd.setFixedHeight(26)
        dd.setStyleSheet(
            f"background:{C_BG_ITEM}; border-radius:5px; border:1px solid {C_BORDER};"
        )
        dd_lo = QHBoxLayout(dd)
        dd_lo.setContentsMargins(8, 0, 6, 0)
        dd_lo.setSpacing(0)
        dd_lo.addWidget(_lbl("红色", C_TEXT_1, 12))
        dd_lo.addStretch()
        chev = QLabel()
        chev.setPixmap(icon_pixmap("chevron-down", 10, C_TEXT_4))
        chev.setFixedSize(10, 10)
        dd_lo.addWidget(chev)
        sr_lo.addWidget(dd, 1)
        lo.addWidget(sel_row)
        lo.addSpacing(4)

        for label, lc, rc in [
            ("青色",   "#00bbcc", "#ff4444"),
            ("洋红色", "#cc00aa", "#00cc44"),
            ("黄色",   "#0044cc", "#ffee00"),
            ("黑色",   "#ffffff", "#000000"),
        ]:
            self._add_gradient_slider_row(lo, label, 0, lc, rc, -100, 100, 0)

    # ── 细节 section ──────────────────────────────────────────────────────────

    def _build_detail_content(self, lo: QVBoxLayout) -> None:
        """Detail section: sharpening + noise reduction."""
        lo.addWidget(_lbl("锐化", C_TEXT_3, 11))
        for label, lc, rc in [
            ("数量",   "#1a1a1a", "#ffffff"),
            ("半径",   "#1a1a1a", "#ffffff"),
            ("细节",   "#1a1a1a", "#ffffff"),
            ("蒙版",   "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(lo, label, 0, lc, rc, 0, 100, 0)
        lo.addSpacing(4)
        lo.addWidget(_lbl("降噪", C_TEXT_3, 11))
        for label, lc, rc in [
            ("明亮度",   "#1a1a1a", "#ffffff"),
            ("明亮度细节", "#1a1a1a", "#ffffff"),
            ("颜色",     "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(lo, label, 0, lc, rc, 0, 100, 0)

    # ── 镜头 section ──────────────────────────────────────────────────────────

    def _build_lens_content(self, lo: QVBoxLayout) -> None:
        """Lens correction: distortion, vignette, chromatic aberration."""
        for label, lc, rc in [
            ("扭曲校正", "#1a1a1a", "#ffffff"),
            ("暗角",     "#000000", "#ffffff"),
            ("暗角中点", "#1a1a1a", "#ffffff"),
            ("色差",     "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(lo, label, 0, lc, rc, -100, 100, 0)

    # ── 透视矫正 section ──────────────────────────────────────────────────────

    def _build_perspective_content(self, lo: QVBoxLayout) -> None:
        """Perspective transform sliders."""
        for label, lc, rc in [
            ("水平",   "#1a1a1a", "#ffffff"),
            ("垂直",   "#1a1a1a", "#ffffff"),
            ("旋转",   "#1a1a1a", "#ffffff"),
            ("缩放",   "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(lo, label, 0, lc, rc, -100, 100, 0)

    # ── 颜色校准 section ──────────────────────────────────────────────────────

    def _build_color_calibration_content(self, lo: QVBoxLayout) -> None:
        """Color calibration: per-channel hue/saturation."""
        for ch, hue_lc, hue_rc in [
            ("红色原色", "#ff44aa", "#ff4444"),
            ("绿色原色", "#aacc00", "#00bbaa"),
            ("蓝色原色", "#0088cc", "#6655ff"),
        ]:
            lo.addWidget(_lbl(ch, C_TEXT_3, 11))
            self._add_gradient_slider_row(lo, "色相",  0, hue_lc,   hue_rc,   -100, 100, 0)
            self._add_gradient_slider_row(lo, "饱和度", 0, "#1a1a1a", "#ffffff", -100, 100, 0)
            lo.addSpacing(2)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN EDITOR WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class MainEditorWindow(QWidget):
    """
    主编辑界面 – embedded page inside TempusLoomWindow.
    Layout:
        ┌─────────────────────── EditorTopBar (h=48) ──────────────────────────┐
        │ ToolSidebar │ ToolOptionsBar + CanvasArea + StatusBar │ RightPanel   │
        │  (w=48)     │         (fills remaining width)          │  (w=320)    │
        └─────────────────────────────────────────────────────────────────────┘
    """

    title_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_tlimage: Optional[TLImage] = None
        self._adjust_preview_timer = QTimer(self)
        self._adjust_preview_timer.setSingleShot(True)
        self._adjust_preview_timer.setInterval(33)
        self._adjust_preview_timer.timeout.connect(self._refresh_canvas_from_tlimage)
        self.setStyleSheet(f"background:{C_BG_APP};")
        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()

    # ── build ─────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root_lo = QVBoxLayout(self)
        root_lo.setContentsMargins(0, 0, 0, 0)
        root_lo.setSpacing(0)

        # main content row
        content = QWidget()
        content.setStyleSheet(f"background:{C_BG_APP};")
        content_lo = QHBoxLayout(content)
        content_lo.setContentsMargins(0, 0, 0, 0)
        content_lo.setSpacing(0)
        root_lo.addWidget(content, 1)

        # left tools
        self._tool_sidebar = ToolSidebar()
        content_lo.addWidget(self._tool_sidebar)

        # center workspace
        center = QWidget()
        center.setStyleSheet(f"background:{C_BG_APP};")
        center_lo = QVBoxLayout(center)
        center_lo.setContentsMargins(0, 0, 0, 0)
        center_lo.setSpacing(0)

        self._opts_bar   = ToolOptionsBar()
        self._canvas     = CanvasArea()
        self._status_bar = EditorStatusBar()

        center_lo.addWidget(self._opts_bar)
        center_lo.addWidget(self._canvas, 1)
        center_lo.addWidget(self._status_bar)
        content_lo.addWidget(center, 1)

        # right panel
        self._right_panel = RightPanel()
        content_lo.addWidget(self._right_panel)

    # ── signals ───────────────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        self._tool_sidebar.tool_changed.connect(self._opts_bar.set_tool)

        self._canvas.zoom_changed.connect(self._on_zoom_changed)
        self._status_bar.zoom_in_requested.connect(self._zoom_in)
        self._status_bar.zoom_out_requested.connect(self._zoom_out)

        self._opts_bar.grid_toggled.connect(self._canvas.set_grid)
        self._opts_bar.ruler_toggled.connect(self._canvas.set_ruler)
        self._right_panel.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        self._right_panel.layer_opacity_changed.connect(self._on_layer_opacity_changed)
        self._right_panel.adjust_section_changed.connect(self._on_adjust_section_changed)

    def open_image(self, path: str) -> bool:
        try:
            tl_image = TLImage.open(path)
            pixmap = self._render_tlimage_to_pixmap(tl_image)
        except Exception:
            return False

        self._adjust_preview_timer.stop()
        self._current_tlimage = tl_image
        self._canvas.set_pixmap(pixmap)
        self._right_panel.set_malayers(tl_image.malayers)
        self.title_changed.emit(f"TempusLoom - {Path(path).name}")
        width, height = tl_image.get_image_size()
        self._status_bar.set_image_info(width, height)
        return True

    def _render_tlimage_to_pixmap(self, tl_image: TLImage) -> QPixmap:
        return QPixmap.fromImage(ImageQt(tl_image.render(preview=True)))

    def _refresh_canvas_from_tlimage(self) -> None:
        if self._current_tlimage is None:
            return
        pixmap = self._render_tlimage_to_pixmap(self._current_tlimage)
        self._canvas.set_pixmap(pixmap)
        width, height = self._current_tlimage.get_image_size()
        self._status_bar.set_image_info(width, height)

    def _setup_shortcuts(self) -> None:
        from PyQt6.QtGui import QShortcut
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_image)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_image)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, self._export_image)

    # action handlers
    def _open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image",
            str(Path.home() / "Pictures"),
            "Images (*.jpg *.jpeg *.png *.webp *.tiff *.tif *.bmp *.heic *.raw *.cr2 *.nef *.arw *.dng);;All Files (*)",
        )
        if not path:
            return
        if self.open_image(path):
            return
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Open Failed", f"Unsupported or broken image file:\n{path}")

    def _save_image(self) -> None:
        pass

    def _export_image(self) -> None:
        if self._current_tlimage is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Image",
            str(Path.home() / "Desktop" / "export.jpg"),
            "JPEG (*.jpg *.jpeg);;PNG (*.png);;WebP (*.webp);;TIFF (*.tiff)",
        )
        if path:
            self._current_tlimage.render_to_path(path)

    def _undo(self) -> None:
        pass   # hook into editing history

    def _redo(self) -> None:
        pass   # hook into editing history

    def _on_layer_visibility_changed(self, idx: int, visible: bool) -> None:
        if self._current_tlimage is None or idx >= len(self._current_tlimage.malayers):
            return
        self._current_tlimage.malayers[idx].visible = visible
        self._refresh_canvas_from_tlimage()

    def _on_layer_opacity_changed(self, idx: int, opacity: float) -> None:
        if self._current_tlimage is None or idx >= len(self._current_tlimage.malayers):
            return
        self._current_tlimage.malayers[idx].opacity = opacity
        self._refresh_canvas_from_tlimage()

    def _on_adjust_section_changed(self, section: str, values: dict) -> None:
        if self._current_tlimage is None:
            return
        layer = self._current_tlimage.get_primary_malayer_for_tab("adjust")
        if layer is None or not hasattr(layer, "update_section"):
            return
        layer.update_section(section, **values)
        self._adjust_preview_timer.start()

    def _on_zoom_changed(self, pct: int) -> None:
        self._opts_bar.set_zoom(pct)
        self._status_bar.set_zoom(pct)

    def _zoom_in(self) -> None:
        self._canvas._zoom = min(CanvasArea._MAX_ZOOM,
                                 int(self._canvas._zoom * 1.25))
        self._canvas._center_image()
        self._canvas.zoom_changed.emit(self._canvas._zoom)
        self._canvas.update()

    def _zoom_out(self) -> None:
        self._canvas._zoom = max(CanvasArea._MIN_ZOOM,
                                 int(self._canvas._zoom * 0.80))
        self._canvas._center_image()
        self._canvas.zoom_changed.emit(self._canvas._zoom)
        self._canvas.update()
