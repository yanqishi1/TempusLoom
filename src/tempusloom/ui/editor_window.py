# -*- coding: utf-8 -*-
"""
TempusLoom – 主编辑界面
Main editor window matching the pencil.pen design (1440 × 900).
"""

from __future__ import annotations

import base64
import io
import json
import os
import math
import multiprocessing as mp
from copy import deepcopy
from pathlib import Path
from queue import Empty
from typing import Any, Callable, Optional

from PyQt6.QtCore import (
    Qt, QSize, QRectF, QPointF, QThread, QTimer, QObject, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QBrush, QPen,
    QPixmap, QFont, QLinearGradient, QRadialGradient, QWheelEvent,
    QMouseEvent, QKeySequence, QAction, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QScrollArea, QFrame, QFileDialog,
    QSizePolicy, QSlider, QComboBox, QMenu, QMenuBar,
    QStackedWidget, QSpacerItem, QDialog, QProgressBar,
    QPlainTextEdit, QLineEdit, QFormLayout, QDialogButtonBox,
)

from .editor_icons import icon_pixmap
from PIL import Image
from PIL.ImageQt import ImageQt
from tempusloom.core import LibraryProjectIndex, Mask, TLImage
from tempusloom.core.histogram_process import histogram_worker_main
from tempusloom.agent import (
    AgentModelConfig,
    AgentRequestContext,
    PROVIDER_PRESETS,
    TempusLoomColorAgent,
    load_agent_config,
    save_agent_config,
)


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


class ExportProgressDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出中")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowTitleHint, True)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._label = QLabel("准备导出…")
        self._label.setStyleSheet(f"color:{C_TEXT_1}; font-size:13px;")
        layout.addWidget(self._label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background:{C_BG_ITEM};
                border:1px solid {C_BORDER};
                border-radius:6px;
                color:{C_TEXT_1};
                text-align:center;
                min-height:18px;
            }}
            QProgressBar::chunk {{
                background:{C_PRIMARY};
                border-radius:5px;
            }}
            """
        )
        layout.addWidget(self._progress_bar)

        self.setStyleSheet(f"background:{C_BG_PANEL};")

    def update_progress(self, value: int, message: str) -> None:
        self._label.setText(message)
        self._progress_bar.setValue(max(0, min(100, value)))

    def reject(self) -> None:
        return


class ExportWorker(QObject):
    progress_changed = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, snapshot: dict[str, Any], export_path: str, export_format: str) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._export_path = export_path
        self._export_format = export_format

    def run(self) -> None:
        try:
            tl_image = TLImage.from_dict(self._snapshot)
            tl_image.render_to_path(
                self._export_path,
                format=self._export_format,
                progress_callback=self._emit_progress,
            )
            self.finished.emit(self._export_path)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _emit_progress(self, value: int, message: str) -> None:
        self.progress_changed.emit(value, message)


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

    def set_active_tool(self, name: str) -> None:
        for btn in self._buttons:
            if btn._icon_name != name:
                continue
            if btn.isChecked():
                self._active_name = name
                self.tool_changed.emit(name)
            else:
                btn.setChecked(True)
            return
        self._active_name = name
        for btn in self._buttons:
            if btn.isChecked():
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
        _NAMES["mask-linear"] = "Linear Mask"
        _NAMES["mask-radial"] = "Radial Mask"
        label = _NAMES.get(tool_name, tool_name)
        icon_name = "circle-dashed" if tool_name in {"mask-linear", "mask-radial"} else tool_name
        self._tool_icon_lbl.setPixmap(icon_pixmap(icon_name, 12, C_PRIMARY))
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
    color_picked = pyqtSignal(QColor)
    crop_confirmed = pyqtSignal(float, float, float, float)  # left, top, right, bottom (ratios)
    crop_cancelled = pyqtSignal()
    mask_preview_changed = pyqtSignal(dict)
    mask_create_finished = pyqtSignal(dict, str)
    mask_change_finished = pyqtSignal(dict, str)

    _MIN_ZOOM = 5
    _MAX_ZOOM = 800
    _MASK_OVERLAY_MAX_DIMENSION = 640

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG_CANVAS};")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self._edited_pixmap: Optional[QPixmap] = None
        self._original_pixmap: Optional[QPixmap] = None
        self._compare_mode = False
        self._zoom    = 75        # percent
        self._offset  = QPointF(0, 0)
        self._panning = False
        self._pan_start = QPointF()
        self._pan_offset_start = QPointF()
        self._show_grid  = False
        self._show_ruler = False
        self._active_tool = "mouse-pointer"

        # crop tool state
        self._crop_active = False
        self._crop_rect = QRectF()
        self._crop_drawing = False
        self._crop_drag_start = QPointF()
        self._crop_handle_size = 8
        self._crop_active_handle: Optional[str] = None
        self._original_image_size: Optional[tuple[int, int]] = None

        # gradient mask drawing state
        self._mask_drawing = False
        self._mask_drag_start = QPointF()
        self._mask_drag_current = QPointF()
        self._mask_overlay_state: dict[str, Any] = {}
        self._mask_overlay_visible = True
        self._mask_editing = False
        self._mask_active_handle: Optional[str] = None
        self._mask_edit_start_pos = QPointF()
        self._mask_edit_start_payload: dict[str, Any] = {}
        self._mask_overlay_cache_key: Optional[tuple[str, int, int]] = None
        self._mask_overlay_cache_pixmap: Optional[QPixmap] = None

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

        self._compare_btn = QPushButton(self)
        self._compare_btn.setFixedSize(36, 36)
        self._compare_btn.setIcon(_qicon("compare", 18, C_TEXT_1))
        self._compare_btn.setIconSize(QSize(18, 18))
        self._compare_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compare_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._compare_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; border:1px solid {C_BORDER}; border-radius:10px;}}"
            f"QPushButton:hover{{background:#343434;}}"
            f"QPushButton:pressed{{background:#3d3d3d;}}"
        )
        self._compare_btn.setToolTip("按住查看原图")
        self._compare_btn.pressed.connect(self._show_original_preview)
        self._compare_btn.released.connect(self._show_edited_preview)
        self._compare_btn.hide()

        # crop confirm / cancel buttons
        self._crop_confirm_btn = QPushButton(self)
        self._crop_confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._crop_confirm_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._crop_confirm_btn.setFixedHeight(28)
        self._crop_confirm_btn.setText("\u2713  确认")
        self._crop_confirm_btn.setStyleSheet(
            f"QPushButton{{background:{C_PRIMARY}; color:{C_WHITE}; border:none;"
            f"border-radius:4px; font-size:12px; padding:0 16px;}}"
            f"QPushButton:hover{{background:#5a8cff;}}"
            f"QPushButton:pressed{{background:#2a5ad4;}}"
        )
        self._crop_confirm_btn.clicked.connect(self._commit_crop)
        self._crop_confirm_btn.hide()

        self._crop_cancel_btn = QPushButton(self)
        self._crop_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._crop_cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._crop_cancel_btn.setFixedHeight(28)
        self._crop_cancel_btn.setText("\u2715  取消")
        self._crop_cancel_btn.setStyleSheet(
            f"QPushButton{{background:rgba(255,255,255,0.12); color:{C_TEXT_1};"
            f"border:1px solid rgba(255,255,255,0.15); border-radius:4px;"
            f"font-size:12px; padding:0 16px;}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.2);}}"
            f"QPushButton:pressed{{background:rgba(255,255,255,0.08);}}"
        )
        self._crop_cancel_btn.clicked.connect(self._cancel_crop)
        self._crop_cancel_btn.hide()

        self.setAcceptDrops(True)

    def set_tool(self, tool_name: str) -> None:
        if self._active_tool == "crop" and tool_name != "crop":
            self._clear_crop_overlay()
        if self._active_tool in {"mask-linear", "mask-radial"} and tool_name != self._active_tool:
            self._mask_drawing = False
            self._mask_editing = False
            self._mask_active_handle = None
        self._active_tool = tool_name
        if tool_name == "crop":
            self._init_crop_tool()
        if tool_name in {"mask-linear", "mask-radial"}:
            self.set_mask_overlay_visible(True)
        self._refresh_cursor()

    def _refresh_cursor(self) -> None:
        if self._panning:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self._active_tool == "crop":
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if self._active_tool == "pipette" and self._display_pixmap() is not None:
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if self._active_tool in {"mask-linear", "mask-radial"} and self._display_pixmap() is not None:
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_mask_overlay(self, mask_state: Optional[dict[str, Any]]) -> None:
        self._mask_overlay_state = dict(mask_state or {})
        self._invalidate_mask_overlay_cache()
        self.update()

    def set_mask_overlay_visible(self, visible: bool) -> None:
        if self._mask_overlay_visible == visible:
            return
        self._mask_overlay_visible = visible
        self.update()

    def _invalidate_mask_overlay_cache(self) -> None:
        self._mask_overlay_cache_key = None
        self._mask_overlay_cache_pixmap = None

    # ── crop helpers ──────────────────────────────────────────────────────────
    def set_original_image_size(self, width: int, height: int) -> None:
        self._original_image_size = (width, height)

    def _init_crop_tool(self) -> None:
        self._crop_drawing = False
        self._crop_active_handle = None
        rect = self._image_rect()
        if rect is None:
            self._crop_active = False
            return
        self._crop_active = True
        self._crop_rect = QRectF(rect)
        self.update()

    def _clear_crop_overlay(self) -> None:
        self._crop_active = False
        self._crop_drawing = False
        self._crop_rect = QRectF()
        self._crop_active_handle = None
        self._crop_confirm_btn.hide()
        self._crop_cancel_btn.hide()
        self.update()

    def _canvas_pos_to_crop_ratio(self, pos: QPointF) -> tuple[float, float]:
        rect = self._image_rect()
        if rect is None:
            return 0.0, 0.0
        rel_x = (pos.x() - rect.left()) / max(rect.width(), 1.0)
        rel_y = (pos.y() - rect.top()) / max(rect.height(), 1.0)
        return max(0.0, min(1.0, rel_x)), max(0.0, min(1.0, rel_y))

    def _crop_handles(self) -> dict[str, QRectF]:
        handles: dict[str, QRectF] = {}
        hs = self._crop_handle_size
        r = self._crop_rect
        # corner handles — larger hit target
        handles["top-left"] = QRectF(r.left() - hs, r.top() - hs, hs * 2, hs * 2)
        handles["top-right"] = QRectF(r.right() - hs, r.top() - hs, hs * 2, hs * 2)
        handles["bottom-left"] = QRectF(r.left() - hs, r.bottom() - hs, hs * 2, hs * 2)
        handles["bottom-right"] = QRectF(r.right() - hs, r.bottom() - hs, hs * 2, hs * 2)
        # edge midpoint handles
        mid_x = r.left() + r.width() / 2
        mid_y = r.top() + r.height() / 2
        handles["top"] = QRectF(mid_x - hs * 1.5, r.top() - hs, hs * 3, hs * 2)
        handles["bottom"] = QRectF(mid_x - hs * 1.5, r.bottom() - hs, hs * 3, hs * 2)
        handles["left"] = QRectF(r.left() - hs, mid_y - hs * 1.5, hs * 2, hs * 3)
        handles["right"] = QRectF(r.right() - hs, mid_y - hs * 1.5, hs * 2, hs * 3)
        return handles

    def _hit_test_crop_handle(self, pos: QPointF) -> Optional[str]:
        if not self._crop_active or self._crop_rect.isNull():
            return None
        for name, handle_rect in self._crop_handles().items():
            if handle_rect.contains(pos):
                return name
        return None

    def _cursor_for_crop_handle(self, handle: Optional[str]) -> Qt.CursorShape:
        _CURSOR_MAP: dict[str, Qt.CursorShape] = {
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
        }
        return _CURSOR_MAP.get(handle, Qt.CursorShape.CrossCursor)

    def _update_crop_rect_from_drag(self, current_pos: QPointF) -> None:
        img_rect = self._image_rect()
        if img_rect is None:
            return
        clamped_x = max(img_rect.left(), min(img_rect.right(), current_pos.x()))
        clamped_y = max(img_rect.top(), min(img_rect.bottom(), current_pos.y()))
        clamped = QPointF(clamped_x, clamped_y)
        if self._crop_active_handle is None:
            self._crop_rect = QRectF(self._crop_drag_start, clamped).normalized()
        else:
            r = QRectF(self._crop_rect)
            if "left" in self._crop_active_handle:
                r.setLeft(clamped.x())
            if "right" in self._crop_active_handle:
                r.setRight(clamped.x())
            if "top" in self._crop_active_handle:
                r.setTop(clamped.y())
            if "bottom" in self._crop_active_handle:
                r.setBottom(clamped.y())
            self._crop_rect = r.normalized()

    def _commit_crop(self) -> None:
        if self._crop_rect.isNull() or not self._crop_rect.isValid():
            return
        img_rect = self._image_rect()
        if img_rect is None:
            return
        left_r, top_r = self._canvas_pos_to_crop_ratio(self._crop_rect.topLeft())
        right_r, bottom_r = self._canvas_pos_to_crop_ratio(self._crop_rect.bottomRight())
        left_r = max(0.0, min(1.0, left_r))
        top_r = max(0.0, min(1.0, top_r))
        right_r = max(0.0, min(1.0, right_r))
        bottom_r = max(0.0, min(1.0, bottom_r))
        self.crop_confirmed.emit(left_r, top_r, right_r, bottom_r)
        self._clear_crop_overlay()

    def _cancel_crop(self) -> None:
        self.crop_cancelled.emit()
        self._clear_crop_overlay()

    def _display_pixmap(self) -> Optional[QPixmap]:
        if self._compare_mode and self._original_pixmap and not self._original_pixmap.isNull():
            return self._original_pixmap
        return self._edited_pixmap

    def _base_pixmap(self) -> Optional[QPixmap]:
        return self._edited_pixmap or self._display_pixmap()

    def _show_original_preview(self) -> None:
        if self._original_pixmap and not self._original_pixmap.isNull():
            self._compare_mode = True
            self.update()

    def _show_edited_preview(self) -> None:
        if self._compare_mode:
            self._compare_mode = False
            self.update()

    def _position_compare_button(self) -> None:
        margin = 16
        self._compare_btn.move(self.width() - self._compare_btn.width() - margin,
                               self.height() - self._compare_btn.height() - margin)

    def _position_crop_buttons(self) -> None:
        if (not self._crop_active or self._crop_drawing
                or self._crop_rect.isNull() or not self._crop_rect.isValid()):
            self._crop_confirm_btn.hide()
            self._crop_cancel_btn.hide()
            return
        gap = 8
        margin = 8
        confirm_w = self._crop_confirm_btn.sizeHint().width()
        cancel_w = self._crop_cancel_btn.sizeHint().width()
        total_w = confirm_w + gap + cancel_w
        x = int(self._crop_rect.right() - total_w - margin)
        y = int(self._crop_rect.bottom() + margin)
        self._crop_confirm_btn.move(x, y)
        self._crop_confirm_btn.setFixedWidth(confirm_w)
        self._crop_cancel_btn.move(x + confirm_w + gap, y)
        self._crop_cancel_btn.setFixedWidth(cancel_w)
        self._crop_confirm_btn.show()
        self._crop_cancel_btn.show()
        self._crop_confirm_btn.raise_()
        self._crop_cancel_btn.raise_()

    def _image_rect(self) -> Optional[QRectF]:
        px = self._display_pixmap()
        if px is None or px.isNull():
            return None
        width = px.width() * self._zoom / 100
        height = px.height() * self._zoom / 100
        return QRectF(self._offset.x(), self._offset.y(), width, height)

    def _canvas_pos_to_image_pos(self, pos: QPointF) -> Optional[tuple[int, int]]:
        px = self._display_pixmap()
        rect = self._image_rect()
        if px is None or rect is None or not rect.contains(pos):
            return None
        rel_x = (pos.x() - rect.left()) / max(rect.width(), 1.0)
        rel_y = (pos.y() - rect.top()) / max(rect.height(), 1.0)
        rel_x = max(0.0, min(0.999999, rel_x))
        rel_y = max(0.0, min(0.999999, rel_y))
        image_x = int(rel_x * px.width())
        image_y = int(rel_y * px.height())
        return image_x, image_y

    def _sample_color(self, pos: QPointF, radius: int = 2) -> Optional[QColor]:
        px = self._display_pixmap()
        image_pos = self._canvas_pos_to_image_pos(pos)
        if px is None or image_pos is None:
            return None
        image = px.toImage()
        x, y = image_pos
        red = 0.0
        green = 0.0
        blue = 0.0
        alpha = 0.0
        count = 0
        for yy in range(max(0, y - radius), min(image.height(), y + radius + 1)):
            for xx in range(max(0, x - radius), min(image.width(), x + radius + 1)):
                color = image.pixelColor(xx, yy)
                red += color.redF()
                green += color.greenF()
                blue += color.blueF()
                alpha += color.alphaF()
                count += 1
        if count <= 0:
            return None
        return QColor.fromRgbF(red / count, green / count, blue / count, alpha / count)

    # ── image loading ──────────────────────────────────────────────────────────
    def load_image(self, path: str) -> bool:
        px = QPixmap(path)
        if px.isNull():
            return False
        self.set_pixmaps(px, reset_view=True)
        return True

    def set_pixmaps(
        self,
        edited: QPixmap,
        original: Optional[QPixmap] = None,
        *,
        reset_view: bool = False,
    ) -> None:
        self._edited_pixmap = edited if not edited.isNull() else None
        self._original_pixmap = original if original and not original.isNull() else None
        self._compare_mode = False
        if self._edited_pixmap:
            self._placeholder.hide()
            self._compare_btn.setVisible(self._original_pixmap is not None)
            if reset_view:
                self._fit_to_window()
            else:
                self.update()
        else:
            self._compare_btn.hide()
        self._position_compare_button()
        self._refresh_cursor()

    def set_pixmap(self, px: QPixmap, *, reset_view: bool = False) -> None:
        self.set_pixmaps(px, reset_view=reset_view)

    def _fit_to_window(self) -> None:
        px = self._base_pixmap()
        if not px:
            return
        w, h = self.width(), self.height()
        if w < 10 or h < 10:
            return
        scale_w = (w - 40) / px.width()
        scale_h = (h - 40) / px.height()
        scale = min(scale_w, scale_h, 1.0)
        self._zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, int(scale * 100)))
        self._center_image()
        self.zoom_changed.emit(self._zoom)
        self.update()

    def _center_image(self) -> None:
        px = self._base_pixmap()
        if not px:
            return
        iw = px.width()  * self._zoom / 100
        ih = px.height() * self._zoom / 100
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

        px = self._display_pixmap()
        if px and not px.isNull():
            iw = px.width()  * self._zoom / 100
            ih = px.height() * self._zoom / 100
            dest = QRectF(self._offset.x(), self._offset.y(), iw, ih)

            # drop shadow
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(dest.adjusted(4, 4, 4, 4), 4, 4)
            p.fillPath(shadow_path, QBrush(QColor(0, 0, 0, 80)))

            # image with rounded corners
            clip = QPainterPath()
            clip.addRoundedRect(dest, 4, 4)
            p.setClipPath(clip)
            p.drawPixmap(dest.toRect(), px)
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

            # crop overlay
            if self._active_tool == "crop" and self._crop_active and not self._crop_rect.isNull():
                self._paint_crop_overlay(p, dest)
            if self._mask_overlay_visible and (self._active_tool in {"mask-linear", "mask-radial"} or self._mask_overlay_state):
                self._paint_mask_overlay(p, dest)
        p.end()
        self._position_crop_buttons()

    def _mask_payload_from_drag(self) -> Optional[dict[str, Any]]:
        rect = self._image_rect()
        if rect is None or not rect.isValid():
            return None
        start_x, start_y = self._canvas_pos_to_crop_ratio(self._mask_drag_start)
        end_x, end_y = self._canvas_pos_to_crop_ratio(self._mask_drag_current)

        if self._active_tool == "mask-linear":
            return {
                "type": "linear",
                "name": "Linear Gradient",
                "start": {"x": start_x, "y": start_y},
                "end": {"x": end_x, "y": end_y},
                "opacity": 1.0,
                "invert": False,
            }

        if self._active_tool == "mask-radial":
            radius_x = max(0.01, abs(end_x - start_x))
            radius_y = max(0.01, abs(end_y - start_y))
            return {
                "type": "radial",
                "name": "Radial Gradient",
                "center": {"x": start_x, "y": start_y},
                "radiusX": radius_x,
                "radiusY": radius_y,
                "rotation": 0.0,
                "feather": 0.6,
                "opacity": 1.0,
                "invert": False,
            }
        return None

    def _mask_payload_description(self, payload: dict[str, Any]) -> str:
        mask_type = str(payload.get("type", payload.get("mask_type", "mask"))).lower()
        if mask_type == "linear":
            return "蒙版 · 线性渐变"
        if mask_type == "radial":
            return "蒙版 · 径向渐变"
        return "蒙版"

    @staticmethod
    def _mask_state_type(mask_state: dict[str, Any]) -> str:
        return str(mask_state.get("type", mask_state.get("mask_type", ""))).lower().replace("_gradient", "")

    @staticmethod
    def _mask_state_point(mask_state: dict[str, Any], key: str, fallback_x: float, fallback_y: float) -> tuple[float, float]:
        nested = mask_state.get(key)
        if isinstance(nested, dict):
            return float(nested.get("x", fallback_x)), float(nested.get("y", fallback_y))
        return float(mask_state.get(f"{key}_x", mask_state.get(f"{key}X", fallback_x))), float(
            mask_state.get(f"{key}_y", mask_state.get(f"{key}Y", fallback_y))
        )

    def _mask_canvas_point(self, image_rect: QRectF, x_ratio: float, y_ratio: float) -> QPointF:
        return QPointF(
            image_rect.left() + image_rect.width() * max(0.0, min(1.0, x_ratio)),
            image_rect.top() + image_rect.height() * max(0.0, min(1.0, y_ratio)),
        )

    def _canvas_point_to_mask_ratio(self, image_rect: QRectF, pos: QPointF) -> tuple[float, float]:
        rel_x = (pos.x() - image_rect.left()) / max(image_rect.width(), 1.0)
        rel_y = (pos.y() - image_rect.top()) / max(image_rect.height(), 1.0)
        return max(0.0, min(1.0, rel_x)), max(0.0, min(1.0, rel_y))

    @staticmethod
    def _point_distance(a: QPointF, b: QPointF) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    @classmethod
    def _point_to_segment_distance(cls, point: QPointF, start: QPointF, end: QPointF) -> float:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        denom = dx * dx + dy * dy
        if denom <= 1e-6:
            return cls._point_distance(point, start)
        t = ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / denom
        t = max(0.0, min(1.0, t))
        closest = QPointF(start.x() + dx * t, start.y() + dy * t)
        return cls._point_distance(point, closest)

    @staticmethod
    def _rotate_point(x_value: float, y_value: float, angle_degrees: float) -> tuple[float, float]:
        angle = math.radians(angle_degrees)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return x_value * cos_a - y_value * sin_a, x_value * sin_a + y_value * cos_a

    def _mask_handle_points(self, mask_state: dict[str, Any], image_rect: QRectF) -> dict[str, QPointF]:
        mask_type = self._mask_state_type(mask_state)
        if mask_type == "linear":
            start = self._mask_state_point(mask_state, "start", 0.5, 0.0)
            end = self._mask_state_point(mask_state, "end", 0.5, 0.5)
            start_pt = self._mask_canvas_point(image_rect, *start)
            end_pt = self._mask_canvas_point(image_rect, *end)
            return {
                "linear-start": start_pt,
                "linear-end": end_pt,
                "linear-move": QPointF((start_pt.x() + end_pt.x()) / 2.0, (start_pt.y() + end_pt.y()) / 2.0),
            }
        if mask_type == "radial":
            center = self._mask_state_point(mask_state, "center", 0.5, 0.5)
            center_pt = self._mask_canvas_point(image_rect, *center)
            radius_x = float(mask_state.get("radiusX", mask_state.get("radius_x", 0.35))) * image_rect.width()
            radius_y = float(mask_state.get("radiusY", mask_state.get("radius_y", 0.35))) * image_rect.height()
            rotation = float(mask_state.get("rotation", 0.0))
            x_dx, x_dy = self._rotate_point(radius_x, 0.0, rotation)
            y_dx, y_dy = self._rotate_point(0.0, -radius_y, rotation)
            rotate_dx, rotate_dy = self._rotate_point(radius_x + 28.0, 0.0, rotation)
            return {
                "radial-center": center_pt,
                "radial-radius-x": QPointF(center_pt.x() + x_dx, center_pt.y() + x_dy),
                "radial-radius-y": QPointF(center_pt.x() + y_dx, center_pt.y() + y_dy),
                "radial-rotate": QPointF(center_pt.x() + rotate_dx, center_pt.y() + rotate_dy),
            }
        return {}

    def _hit_test_mask_handle(self, pos: QPointF) -> Optional[str]:
        image_rect = self._image_rect()
        if image_rect is None or not image_rect.isValid() or not self._mask_overlay_state:
            return None
        mask_type = self._mask_state_type(self._mask_overlay_state)
        handles = self._mask_handle_points(self._mask_overlay_state, image_rect)
        hit_radius = 10.0
        priority = (
            "radial-rotate",
            "radial-radius-x",
            "radial-radius-y",
            "radial-center",
            "linear-start",
            "linear-end",
            "linear-move",
        )
        for handle_name in priority:
            point = handles.get(handle_name)
            if point is not None and self._point_distance(pos, point) <= hit_radius:
                return handle_name

        if mask_type == "linear":
            start = handles.get("linear-start")
            end = handles.get("linear-end")
            if start is not None and end is not None and self._point_to_segment_distance(pos, start, end) <= hit_radius:
                return "linear-move"
        elif mask_type == "radial":
            center = handles.get("radial-center")
            if center is not None:
                radius_x = max(1.0, float(self._mask_overlay_state.get("radiusX", self._mask_overlay_state.get("radius_x", 0.35))) * image_rect.width())
                radius_y = max(1.0, float(self._mask_overlay_state.get("radiusY", self._mask_overlay_state.get("radius_y", 0.35))) * image_rect.height())
                rotation = math.radians(-float(self._mask_overlay_state.get("rotation", 0.0)))
                dx = pos.x() - center.x()
                dy = pos.y() - center.y()
                local_x = dx * math.cos(rotation) - dy * math.sin(rotation)
                local_y = dx * math.sin(rotation) + dy * math.cos(rotation)
                distance = math.sqrt((local_x / radius_x) ** 2 + (local_y / radius_y) ** 2)
                if abs(distance - 1.0) <= 0.08:
                    return "radial-radius-x" if abs(local_x / radius_x) >= abs(local_y / radius_y) else "radial-radius-y"
                if distance < 1.0:
                    return "radial-center"
        return None

    @staticmethod
    def _cursor_for_mask_handle(handle: Optional[str]) -> Qt.CursorShape:
        if handle is None:
            return Qt.CursorShape.ArrowCursor
        if handle.endswith("rotate"):
            return Qt.CursorShape.CrossCursor
        if handle.endswith("move") or handle.endswith("center"):
            return Qt.CursorShape.SizeAllCursor
        if handle.endswith("radius-x"):
            return Qt.CursorShape.SizeHorCursor
        if handle.endswith("radius-y"):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.CrossCursor

    def _update_mask_payload_from_edit(self, current_pos: QPointF) -> Optional[dict[str, Any]]:
        image_rect = self._image_rect()
        if image_rect is None or not image_rect.isValid() or not self._mask_active_handle:
            return None
        payload = deepcopy(self._mask_edit_start_payload)
        start_x, start_y = self._canvas_point_to_mask_ratio(image_rect, self._mask_edit_start_pos)
        current_x, current_y = self._canvas_point_to_mask_ratio(image_rect, current_pos)
        delta_x = current_x - start_x
        delta_y = current_y - start_y

        handle = self._mask_active_handle
        if handle == "linear-start":
            payload["start"] = {"x": current_x, "y": current_y}
        elif handle == "linear-end":
            payload["end"] = {"x": current_x, "y": current_y}
        elif handle == "linear-move":
            start = self._mask_state_point(self._mask_edit_start_payload, "start", 0.5, 0.0)
            end = self._mask_state_point(self._mask_edit_start_payload, "end", 0.5, 0.5)
            payload["start"] = {"x": max(0.0, min(1.0, start[0] + delta_x)), "y": max(0.0, min(1.0, start[1] + delta_y))}
            payload["end"] = {"x": max(0.0, min(1.0, end[0] + delta_x)), "y": max(0.0, min(1.0, end[1] + delta_y))}
        elif handle in {"radial-center", "radial-radius-x", "radial-radius-y", "radial-rotate"}:
            center = self._mask_state_point(self._mask_edit_start_payload, "center", 0.5, 0.5)
            center_pt = self._mask_canvas_point(image_rect, *center)
            if handle == "radial-center":
                payload["center"] = {"x": current_x, "y": current_y}
            elif handle == "radial-rotate":
                angle = math.degrees(math.atan2(current_pos.y() - center_pt.y(), current_pos.x() - center_pt.x()))
                payload["rotation"] = angle
            else:
                rotation = math.radians(-float(self._mask_edit_start_payload.get("rotation", 0.0)))
                dx = current_pos.x() - center_pt.x()
                dy = current_pos.y() - center_pt.y()
                local_x = dx * math.cos(rotation) - dy * math.sin(rotation)
                local_y = dx * math.sin(rotation) + dy * math.cos(rotation)
                if handle == "radial-radius-x":
                    payload["radiusX"] = max(0.01, min(2.0, abs(local_x) / max(image_rect.width(), 1.0)))
                else:
                    payload["radiusY"] = max(0.01, min(2.0, abs(local_y) / max(image_rect.height(), 1.0)))
        return payload

    def _paint_mask_overlay(self, p: QPainter, image_rect: QRectF) -> None:
        payload = self._mask_payload_from_drag() if self._mask_drawing else self._mask_overlay_state
        if not payload or not image_rect.isValid():
            return
        mask_type = self._mask_state_type(payload)
        self._paint_mask_influence_overlay(p, image_rect, payload)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(255, 255, 255, 190), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        if mask_type == "linear":
            start = self._mask_state_point(payload, "start", 0.5, 0.0)
            end = self._mask_state_point(payload, "end", 0.5, 0.5)
            start_pt = self._mask_canvas_point(image_rect, *start)
            end_pt = self._mask_canvas_point(image_rect, *end)
            dx = end_pt.x() - start_pt.x()
            dy = end_pt.y() - start_pt.y()
            length = math.hypot(dx, dy)
            p.drawLine(start_pt, end_pt)
            if length > 1e-3:
                nx = -dy / length
                ny = dx / length
                guide_len = max(image_rect.width(), image_rect.height())
                for point, color in ((start_pt, QColor(255, 255, 255, 150)), (end_pt, QColor(C_PRIMARY_H))):
                    p.setPen(QPen(color, 1.0))
                    p.drawLine(
                        QPointF(point.x() - nx * guide_len, point.y() - ny * guide_len),
                        QPointF(point.x() + nx * guide_len, point.y() + ny * guide_len),
                    )
            p.setPen(QPen(QColor(C_PRIMARY_H), 1.5))
            p.setBrush(QBrush(QColor(C_PRIMARY_H)))
            p.drawEllipse(start_pt, 4, 4)
            p.drawEllipse(end_pt, 4, 4)
            midpoint = QPointF((start_pt.x() + end_pt.x()) / 2.0, (start_pt.y() + end_pt.y()) / 2.0)
            p.setBrush(QBrush(QColor(255, 255, 255, 220)))
            p.drawEllipse(midpoint, 3.5, 3.5)
            return

        if mask_type == "radial":
            center = self._mask_state_point(payload, "center", 0.5, 0.5)
            center_pt = self._mask_canvas_point(image_rect, *center)
            radius_x = float(payload.get("radiusX", payload.get("radius_x", 0.35))) * image_rect.width()
            radius_y = float(payload.get("radiusY", payload.get("radius_y", 0.35))) * image_rect.height()
            rotation = float(payload.get("rotation", 0.0))
            handles = self._mask_handle_points(payload, image_rect)
            p.save()
            p.translate(center_pt)
            p.rotate(rotation)
            p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
            p.drawEllipse(QRectF(-radius_x, -radius_y, radius_x * 2.0, radius_y * 2.0))
            p.setPen(QPen(QColor(C_PRIMARY_H), 1.4))
            p.drawLine(QPointF(-radius_x, 0), QPointF(radius_x, 0))
            p.drawLine(QPointF(0, -radius_y), QPointF(0, radius_y))
            p.restore()
            radius_x_pt = handles.get("radial-radius-x")
            radius_y_pt = handles.get("radial-radius-y")
            rotate_pt = handles.get("radial-rotate")
            if radius_x_pt is not None:
                p.setPen(QPen(QColor(C_PRIMARY_H), 1.4))
                p.setBrush(QBrush(QColor(C_PRIMARY_H)))
                p.drawEllipse(radius_x_pt, 4, 4)
            if radius_y_pt is not None:
                p.setPen(QPen(QColor(C_PRIMARY_H), 1.4))
                p.setBrush(QBrush(QColor(C_PRIMARY_H)))
                p.drawEllipse(radius_y_pt, 4, 4)
            if rotate_pt is not None and radius_x_pt is not None:
                p.setPen(QPen(QColor(255, 255, 255, 150), 1.0, Qt.PenStyle.DashLine))
                p.drawLine(radius_x_pt, rotate_pt)
                p.setPen(QPen(QColor(255, 255, 255, 210), 1.4))
                p.setBrush(QBrush(QColor(255, 255, 255, 230)))
                p.drawEllipse(rotate_pt, 4.5, 4.5)
            p.setPen(QPen(QColor(C_PRIMARY_H), 1.5))
            p.setBrush(QBrush(QColor(C_PRIMARY_H)))
            p.drawEllipse(center_pt, 4, 4)

    def _paint_mask_influence_overlay(self, p: QPainter, image_rect: QRectF, payload: dict[str, Any]) -> None:
        mask = Mask.from_dict(payload)
        if mask is None:
            return
        px = self._display_pixmap()
        if px is not None and not px.isNull():
            width, height = px.width(), px.height()
        else:
            width = max(1, int(round(image_rect.width())))
            height = max(1, int(round(image_rect.height())))
        if width <= 0 or height <= 0:
            return
        longest_edge = max(width, height)
        if longest_edge > self._MASK_OVERLAY_MAX_DIMENSION:
            scale = self._MASK_OVERLAY_MAX_DIMENSION / float(longest_edge)
            width = max(1, int(round(width * scale)))
            height = max(1, int(round(height * scale)))

        try:
            payload_key = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        except TypeError:
            payload_key = repr(sorted(payload.items()))
        cache_key = (payload_key, width, height)
        if self._mask_overlay_cache_key == cache_key and self._mask_overlay_cache_pixmap is not None:
            overlay_px = self._mask_overlay_cache_pixmap
        else:
            mask_alpha = mask.to_pil((width, height))
            overlay_alpha = mask_alpha.point(lambda value: 0 if value <= 0 else min(150, int(value * 0.58)))
            overlay = Image.new("RGBA", (width, height), (255, 36, 36, 0))
            overlay.putalpha(overlay_alpha)
            overlay_px = QPixmap.fromImage(ImageQt(overlay))
            self._mask_overlay_cache_key = cache_key
            self._mask_overlay_cache_pixmap = overlay_px
        if overlay_px.isNull():
            return

        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(image_rect, 4, 4)
        p.setClipPath(clip)
        p.drawPixmap(image_rect.toRect(), overlay_px)
        p.restore()

    # ── crop overlay painting ──────────────────────────────────────────────────
    def _paint_crop_overlay(self, p: QPainter, image_rect: QRectF) -> None:
        if self._crop_rect.isNull() or not self._crop_rect.isValid():
            return
        if not image_rect.isValid():
            return
        crop = self._crop_rect.intersected(image_rect)
        if crop.isNull() or not crop.isValid():
            return
        if crop.width() < 2 or crop.height() < 2:
            return

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # dark overlay outside crop area
        overlay_color = QColor(0, 0, 0, 160)
        top_h = crop.top() - image_rect.top()
        if top_h > 0:
            p.fillRect(QRectF(image_rect.left(), image_rect.top(),
                              image_rect.width(), top_h), overlay_color)
        bot_h = image_rect.bottom() - crop.bottom()
        if bot_h > 0:
            p.fillRect(QRectF(image_rect.left(), crop.bottom(),
                              image_rect.width(), bot_h), overlay_color)
        left_w = crop.left() - image_rect.left()
        if left_w > 0:
            p.fillRect(QRectF(image_rect.left(), crop.top(),
                              left_w, crop.height()), overlay_color)
        right_w = image_rect.right() - crop.right()
        if right_w > 0:
            p.fillRect(QRectF(crop.right(), crop.top(),
                              right_w, crop.height()), overlay_color)

        # rule-of-thirds lines
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        third_w = crop.width() / 3.0
        third_h = crop.height() / 3.0
        for i in range(1, 3):
            x = crop.left() + i * third_w
            p.drawLine(QPointF(x, crop.top()), QPointF(x, crop.bottom()))
            y = crop.top() + i * third_h
            p.drawLine(QPointF(crop.left(), y), QPointF(crop.right(), y))

        # border
        p.setPen(QPen(QColor(255, 255, 255, 180), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(crop)

        # L-shaped corner brackets (like Lightroom)
        bracket_len = min(20.0, crop.width() / 4.0, crop.height() / 4.0)
        bracket_w = 2.5
        bracket_color = QColor(255, 255, 255, 230)
        p.setPen(QPen(bracket_color, bracket_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        corners = [
            (crop.topLeft(), QPointF(crop.left() + bracket_len, crop.top()), QPointF(crop.left(), crop.top() + bracket_len)),
            (crop.topRight(), QPointF(crop.right() - bracket_len, crop.top()), QPointF(crop.right(), crop.top() + bracket_len)),
            (crop.bottomLeft(), QPointF(crop.left() + bracket_len, crop.bottom()), QPointF(crop.left(), crop.bottom() - bracket_len)),
            (crop.bottomRight(), QPointF(crop.right() - bracket_len, crop.bottom()), QPointF(crop.right(), crop.bottom() - bracket_len)),
        ]
        for _corner, h_end, v_end in corners:
            p.drawLine(_corner, h_end)
            p.drawLine(_corner, v_end)

        # edge midpoint handles — small rounded rects
        handle_size = 5
        handle_color = QColor(255, 255, 255, 200)
        edge_handles = [
            QPointF(crop.left() + crop.width() / 2, crop.top()),       # top
            QPointF(crop.left() + crop.width() / 2, crop.bottom()),    # bottom
            QPointF(crop.left(), crop.top() + crop.height() / 2),      # left
            QPointF(crop.right(), crop.top() + crop.height() / 2),     # right
        ]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(handle_color)
        for pt in edge_handles:
            p.drawRoundedRect(QRectF(pt.x() - handle_size, pt.y() - handle_size / 2,
                                     handle_size * 2, handle_size), 2, 2)
        for pt in [edge_handles[2], edge_handles[3]]:
            p.drawRoundedRect(QRectF(pt.x() - handle_size / 2, pt.y() - handle_size,
                                     handle_size, handle_size * 2), 2, 2)

        # dimension label — pill-shaped badge
        left_r, top_r = self._canvas_pos_to_crop_ratio(self._crop_rect.topLeft())
        right_r, bottom_r = self._canvas_pos_to_crop_ratio(self._crop_rect.bottomRight())
        if self._original_image_size:
            orig_w, orig_h = self._original_image_size
        else:
            px = self._display_pixmap()
            orig_w = px.width() if px else 0
            orig_h = px.height() if px else 0
        crop_w = max(1, int((right_r - left_r) * orig_w))
        crop_h = max(1, int((bottom_r - top_r) * orig_h))
        label = f"{crop_w} \u00d7 {crop_h}"
        p.setFont(QFont("Arial", 10, QFont.Weight.Medium))
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(label) + 16
        text_h = fm.height() + 8
        badge_x = crop.left() + (crop.width() - text_w) / 2
        badge_y = crop.top() - text_h - 6
        if badge_y < image_rect.top():
            badge_y = crop.bottom() + 6
        badge_rect = QRectF(badge_x, badge_y, text_w, text_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 190))
        p.drawRoundedRect(badge_rect, text_h / 2, text_h / 2)
        p.setPen(QColor(255, 255, 255, 210))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label)

    # ── events ────────────────────────────────────────────────────────────────
    def resizeEvent(self, _event) -> None:             # noqa: N802
        self._position_compare_button()
        if self._base_pixmap():
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
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            mask_handle = self._hit_test_mask_handle(pos)
            if mask_handle is not None and self._active_tool != "crop":
                self._mask_editing = True
                self._mask_active_handle = mask_handle
                self._mask_edit_start_pos = pos
                self._mask_edit_start_payload = deepcopy(self._mask_overlay_state)
                event.accept()
                self.update()
                return
            if self._active_tool in {"mask-linear", "mask-radial"}:
                img_rect = self._image_rect()
                if img_rect and img_rect.contains(pos):
                    self._mask_drawing = True
                    self._mask_drag_start = pos
                    self._mask_drag_current = pos
                    event.accept()
                    self.update()
                    return
            if self._active_tool == "crop" and self._crop_active:
                handle = self._hit_test_crop_handle(pos)
                if handle:
                    self._crop_active_handle = handle
                    self._crop_drawing = True
                    self._crop_drag_start = pos
                    event.accept()
                    return
                else:
                    img_rect = self._image_rect()
                    if img_rect and img_rect.contains(pos):
                        self._crop_drawing = True
                        self._crop_active_handle = None
                        self._crop_drag_start = pos
                        self._crop_rect = QRectF(pos, pos)
                        event.accept()
                        return
            if self._active_tool == "pipette":
                color = self._sample_color(pos)
                if color is not None:
                    self.color_picked.emit(color)
                    event.accept()
                    return
        if (event.button() == Qt.MouseButton.MiddleButton or
                QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier):
            self._panning = True
            self._pan_start = event.position()
            self._pan_offset_start = QPointF(self._offset)
            self._refresh_cursor()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:    # noqa: N802
        pos = event.position()
        if self._mask_editing:
            payload = self._update_mask_payload_from_edit(pos)
            if payload is not None:
                self._mask_overlay_state = payload
                self._invalidate_mask_overlay_cache()
            self.update()
            return
        if self._mask_drawing and self._active_tool in {"mask-linear", "mask-radial"}:
            self._mask_drag_current = pos
            payload = self._mask_payload_from_drag()
            if payload is not None:
                self._mask_overlay_state = payload
                self._invalidate_mask_overlay_cache()
            self.update()
            return
        if self._crop_drawing and self._active_tool == "crop":
            self._update_crop_rect_from_drag(pos)
            self.update()
            return
        if self._active_tool == "crop" and self._crop_active and not self._crop_drawing:
            handle = self._hit_test_crop_handle(pos)
            self.setCursor(self._cursor_for_crop_handle(handle))
        elif self._mask_overlay_state and self._active_tool != "crop":
            self.setCursor(self._cursor_for_mask_handle(self._hit_test_mask_handle(pos)))
        elif not self._panning:
            self._refresh_cursor()
        if self._panning:
            delta = event.position() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None: # noqa: N802
        if self._mask_editing and event.button() == Qt.MouseButton.LeftButton:
            payload = self._update_mask_payload_from_edit(event.position())
            self._mask_editing = False
            self._mask_active_handle = None
            self._mask_edit_start_payload = {}
            if payload is not None:
                self._mask_overlay_state = payload
                self.mask_change_finished.emit(payload, self._mask_payload_description(payload))
            self._refresh_cursor()
            self.update()
            return
        if self._mask_drawing and event.button() == Qt.MouseButton.LeftButton:
            self._mask_drawing = False
            self._mask_drag_current = event.position()
            payload = self._mask_payload_from_drag()
            if payload is not None:
                self._mask_overlay_state = payload
                self.mask_create_finished.emit(payload, self._mask_payload_description(payload))
            self.update()
            return
        if self._crop_drawing and event.button() == Qt.MouseButton.LeftButton:
            self._crop_drawing = False
            self._crop_active_handle = None
            if self._crop_rect.width() < 10 or self._crop_rect.height() < 10:
                img_rect = self._image_rect()
                if img_rect:
                    self._crop_rect = QRectF(img_rect)
            self.update()
            return
        if self._panning:
            self._panning = False
            self._refresh_cursor()

    def mouseDoubleClickEvent(self, _event) -> None:         # noqa: N802
        self._fit_to_window()

    def keyPressEvent(self, event) -> None:                 # noqa: N802
        if self._active_tool == "crop" and self._crop_active:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._commit_crop()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_crop()
                event.accept()
                return
        super().keyPressEvent(event)

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


class ChatInputEdit(QPlainTextEdit):
    submit_requested = pyqtSignal()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class AIChatBox(QWidget):
    request_submitted = pyqtSignal(str)
    settings_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._busy = False
        self._latest_json_text = ""
        self.setFixedHeight(228)
        self.setStyleSheet(
            f"background:{C_BG_PANEL}; border-top:1px solid {C_BORDER};"
        )
        self._build()
        self.clear_conversation()

    def _build(self) -> None:
        lo = QVBoxLayout(self)
        lo.setContentsMargins(12, 10, 12, 10)
        lo.setSpacing(8)

        header = QWidget()
        header_lo = QHBoxLayout(header)
        header_lo.setContentsMargins(0, 0, 0, 0)
        header_lo.setSpacing(8)

        title = _lbl("AI 调色助手", C_TEXT_1, 13, QFont.Weight.Medium)
        self._status_lbl = _lbl("等待你的风格描述", C_TEXT_3, 11)
        self._context_lbl = _lbl("未附带图片", C_TEXT_4, 11)
        self._settings_btn = QPushButton("设置")
        self._settings_btn.setFixedHeight(26)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._settings_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:{C_TEXT_3}; border:none;"
            f"border-radius:6px; padding:0 10px; font-size:11px;}}"
            f"QPushButton:hover{{background:{C_BG_ITEM}; color:{C_TEXT_1};}}"
        )
        self._settings_btn.clicked.connect(self.settings_requested.emit)

        self._copy_btn = QPushButton("复制 JSON")
        self._copy_btn.setFixedHeight(26)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._copy_btn.setEnabled(False)
        self._copy_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_1}; border:none;"
            f"border-radius:6px; padding:0 10px; font-size:11px;}}"
            f"QPushButton:hover{{background:#343434;}}"
            f"QPushButton:disabled{{color:{C_TEXT_4}; background:#262626;}}"
        )
        self._copy_btn.clicked.connect(self._copy_latest_json)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setFixedHeight(26)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:{C_TEXT_3}; border:none;"
            f"border-radius:6px; padding:0 10px; font-size:11px;}}"
            f"QPushButton:hover{{background:{C_BG_ITEM}; color:{C_TEXT_1};}}"
        )
        self._clear_btn.clicked.connect(self.clear_conversation)

        header_lo.addWidget(title)
        header_lo.addWidget(self._status_lbl)
        header_lo.addStretch()
        header_lo.addWidget(self._context_lbl)
        header_lo.addWidget(self._settings_btn)
        header_lo.addWidget(self._copy_btn)
        header_lo.addWidget(self._clear_btn)
        lo.addWidget(header)

        self._thread_scroll = QScrollArea()
        self._thread_scroll.setWidgetResizable(True)
        self._thread_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._thread_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._thread_scroll.setStyleSheet("background:transparent; border:none;")

        self._thread_container = QWidget()
        self._thread_container.setStyleSheet("background:transparent;")
        self._thread_lo = QVBoxLayout(self._thread_container)
        self._thread_lo.setContentsMargins(0, 0, 0, 0)
        self._thread_lo.setSpacing(8)
        self._thread_lo.addStretch()
        self._thread_scroll.setWidget(self._thread_container)
        lo.addWidget(self._thread_scroll, 1)

        composer = QWidget()
        composer_lo = QHBoxLayout(composer)
        composer_lo.setContentsMargins(0, 0, 0, 0)
        composer_lo.setSpacing(8)

        self._input = ChatInputEdit()
        self._input.setPlaceholderText("描述你想要的风格，例如：偏暖胶片感、冷调电影风、日系通透…")
        self._input.setFixedHeight(56)
        self._input.setTabChangesFocus(True)
        self._input.setStyleSheet(
            f"QPlainTextEdit{{background:{C_BG_APP}; color:{C_TEXT_1};"
            f"border:1px solid {C_BORDER}; border-radius:8px; padding:8px;"
            f"selection-background-color:{C_PRIMARY}; font-size:12px;}}"
        )
        self._input.submit_requested.connect(self._submit)
        composer_lo.addWidget(self._input, 1)
        lo.addWidget(composer)

        footer = QWidget()
        footer_lo = QHBoxLayout(footer)
        footer_lo.setContentsMargins(0, 0, 0, 0)
        footer_lo.setSpacing(8)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("⚡ Full Auto")
        self._mode_combo.setCurrentIndex(0)
        self._mode_combo.setEnabled(False)
        self._mode_combo.setFixedHeight(32)
        self._mode_combo.setMinimumWidth(122)
        self._mode_combo.setStyleSheet(self._pill_combo_qss())

        self._model_btn = QPushButton("未配置模型")
        self._model_btn.setFixedHeight(32)
        self._model_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._model_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._model_btn.setStyleSheet(self._pill_button_qss(min_width=148))
        self._model_btn.clicked.connect(self.settings_requested.emit)

        self._effort_combo = QComboBox()
        self._effort_combo.addItems(["Low", "Medium", "High"])
        self._effort_combo.setCurrentText("High")
        self._effort_combo.setFixedHeight(32)
        self._effort_combo.setMinimumWidth(88)
        self._effort_combo.setStyleSheet(self._pill_combo_qss())

        self._send_btn = QPushButton()
        self._send_btn.setFixedSize(44, 32)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._send_btn.setIcon(_qicon("share", 16, C_WHITE))
        self._send_btn.setIconSize(QSize(16, 16))
        self._send_btn.setStyleSheet(
            f"QPushButton{{background:{C_PRIMARY}; color:{C_WHITE}; border:none;"
            f"border-radius:10px; font-size:12px; font-weight:600;}}"
            f"QPushButton:hover{{background:{C_PRIMARY_H};}}"
            f"QPushButton:pressed{{background:#285bd1;}}"
            f"QPushButton:disabled{{background:#2a3655; color:#96a5d6;}}"
        )
        self._send_btn.clicked.connect(self._submit)

        footer_lo.addWidget(self._mode_combo)
        footer_lo.addWidget(self._model_btn)
        footer_lo.addWidget(self._effort_combo)
        footer_lo.addStretch()
        footer_lo.addWidget(self._send_btn)
        lo.addWidget(footer)

    @staticmethod
    def _pill_combo_qss() -> str:
        return (
            f"QComboBox{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:10px; padding:0 12px; font-size:12px;}}"
            f"QComboBox:hover{{border-color:#444;}}"
            f"QComboBox::drop-down{{border:none; width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{C_BG_PANEL}; color:{C_TEXT_1};"
            f"selection-background-color:{C_BG_ACTIVE}; border:1px solid {C_BORDER};}}"
        )

    @staticmethod
    def _pill_button_qss(*, min_width: int) -> str:
        return (
            f"QPushButton{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:10px; padding:0 12px; min-width:{min_width}px; text-align:left; font-size:12px;}}"
            f"QPushButton:hover{{border-color:#444; background:#222;}}"
        )

    def clear_conversation(self) -> None:
        while self._thread_lo.count() > 1:
            item = self._thread_lo.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._latest_json_text = ""
        self._copy_btn.setEnabled(False)
        self.add_assistant_message(
            "已准备好。打开图片后，直接告诉我你想要的风格，我会返回一份可供调整面板接收的调色 JSON。"
        )

    def set_image_context(self, image_name: Optional[str]) -> None:
        if image_name:
            self._context_lbl.setText(f"已附带图片 · {image_name}")
        else:
            self._context_lbl.setText("未附带图片")

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        self._model_btn.setEnabled(not busy)
        self._settings_btn.setEnabled(not busy)
        self._status_lbl.setText("AI 正在生成调色 JSON…" if busy else "等待你的风格描述")

    def set_model_badge(self, text: str) -> None:
        self._model_btn.setText(text or "未配置模型")

    def set_latest_response_json(self, payload: dict[str, Any]) -> None:
        self._latest_json_text = json.dumps(payload, ensure_ascii=False, indent=2)
        self._copy_btn.setEnabled(True)

    def add_user_message(self, text: str) -> None:
        self._append_message("你", text, is_user=True)

    def add_assistant_message(self, text: str, json_text: Optional[str] = None) -> None:
        self._append_message("AI", text, is_user=False, json_text=json_text)

    def _submit(self) -> None:
        if self._busy:
            return
        prompt = self._input.toPlainText().strip()
        if not prompt:
            return
        self._input.clear()
        self.add_user_message(prompt)
        self.request_submitted.emit(prompt)

    def _copy_latest_json(self) -> None:
        if not self._latest_json_text:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._latest_json_text)
        self._status_lbl.setText("最近一次 JSON 已复制到剪贴板")

    def _append_message(
        self,
        role: str,
        text: str,
        *,
        is_user: bool,
        json_text: Optional[str] = None,
    ) -> None:
        row = QWidget()
        row_lo = QHBoxLayout(row)
        row_lo.setContentsMargins(0, 0, 0, 0)
        row_lo.setSpacing(0)

        bubble = QFrame()
        bubble.setMaximumWidth(720)
        bubble.setStyleSheet(
            f"background:{C_BG_ACTIVE if is_user else C_BG_ITEM};"
            f"border:1px solid {'#395dad' if is_user else C_BORDER};"
            f"border-radius:10px;"
        )
        bubble_lo = QVBoxLayout(bubble)
        bubble_lo.setContentsMargins(10, 8, 10, 8)
        bubble_lo.setSpacing(6)

        bubble_lo.addWidget(_lbl(role, C_PRIMARY if is_user else C_TEXT_2, 11, QFont.Weight.Medium))

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_lbl.setStyleSheet(f"color:{C_TEXT_1}; font-size:12px; background:transparent;")
        bubble_lo.addWidget(text_lbl)

        if json_text:
            json_lbl = QLabel(json_text)
            json_lbl.setWordWrap(True)
            json_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            json_font = QFont("Menlo", 11)
            json_font.setStyleHint(QFont.StyleHint.Monospace)
            json_lbl.setFont(json_font)
            json_lbl.setStyleSheet(
                f"background:{C_BG_APP}; color:{C_TEXT_1}; border-radius:8px;"
                f"padding:8px; border:1px solid {C_BORDER};"
            )
            bubble_lo.addWidget(json_lbl)

        if is_user:
            row_lo.addStretch()
            row_lo.addWidget(bubble)
        else:
            row_lo.addWidget(bubble)
            row_lo.addStretch()

        self._thread_lo.insertWidget(self._thread_lo.count() - 1, row)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._thread_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())


class AIAgentSettingsDialog(QDialog):
    _PROVIDER_MODELS = {
        "openai-compatible": ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"],
        "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "kimi": ["moonshot-v1-8k", "moonshot-v1-32k"],
        "glm": ["glm-4-flash", "glm-4-plus"],
    }

    def __init__(self, config: AgentModelConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Chatbox 设置")
        self.setModal(True)
        self.setFixedWidth(520)
        self.setStyleSheet(
            f"QDialog{{background:{C_BG_PANEL};}}"
            f"QLabel{{color:{C_TEXT_1}; font-size:12px;}}"
            f"QLineEdit{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:8px; padding:8px; font-size:12px;}}"
            f"QComboBox{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:8px; padding:8px; font-size:12px;}}"
            f"QComboBox::drop-down{{border:none; width:20px;}}"
            f"QDialogButtonBox QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_1}; border:none;"
            f"border-radius:8px; min-width:88px; min-height:32px; padding:0 12px;}}"
            f"QDialogButtonBox QPushButton:hover{{background:#343434;}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = _lbl("连接模型服务", C_TEXT_1, 15, QFont.Weight.Medium)
        desc = _lbl(
            "支持 OpenAI 兼容接口，也预置了 Claude / DeepSeek / Kimi / GLM 常见入口。"
            " 你也可以在选择提供商后继续手动修改 Base URL。",
            C_TEXT_3,
            11,
        )
        desc.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(desc)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._provider_box = QComboBox()
        for provider, preset in PROVIDER_PRESETS.items():
            self._provider_box.addItem(preset["label"], provider)

        self._base_url_edit = QLineEdit()
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")

        self._model_box = QComboBox()
        self._model_box.setEditable(True)

        form.addRow("服务提供商", self._provider_box)
        form.addRow("Base URL", self._base_url_edit)
        form.addRow("API Key", self._api_key_edit)
        form.addRow("模型", self._model_box)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._provider_box.currentIndexChanged.connect(self._on_provider_changed)
        self._load_from_config(config)

    def _load_from_config(self, config: AgentModelConfig) -> None:
        index = max(self._provider_box.findData(config.provider), 0)
        self._provider_box.blockSignals(True)
        self._provider_box.setCurrentIndex(index)
        self._provider_box.blockSignals(False)
        self._refresh_model_options(config.provider, config.model)
        self._base_url_edit.setText(config.base_url)
        self._api_key_edit.setText(config.api_key)
        self._model_box.setCurrentText(config.model)

    def _on_provider_changed(self) -> None:
        provider = str(self._provider_box.currentData())
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai-compatible"])
        self._base_url_edit.setText(preset["base_url"])
        self._refresh_model_options(provider, preset["model"])

    def _refresh_model_options(self, provider: str, selected: str) -> None:
        self._model_box.clear()
        self._model_box.addItems(self._PROVIDER_MODELS.get(provider, []))
        self._model_box.setCurrentText(selected)

    def selected_config(self, existing: AgentModelConfig) -> AgentModelConfig:
        return AgentModelConfig(
            provider=str(self._provider_box.currentData()),
            base_url=self._base_url_edit.text().strip(),
            api_key=self._api_key_edit.text().strip(),
            model=self._model_box.currentText().strip(),
            temperature=existing.temperature,
            max_tokens=existing.max_tokens,
            timeout_seconds=existing.timeout_seconds,
        )


class AgentRunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config: AgentModelConfig, request_payload: dict[str, Any]) -> None:
        super().__init__()
        self._config = config
        self._request_payload = request_payload

    def run(self) -> None:
        try:
            agent = TempusLoomColorAgent(self._config)
            context = AgentRequestContext(
                image=self._request_payload["image"],
                style_prompt=str(self._request_payload["style_prompt"]),
                current_adjust=dict(self._request_payload.get("current_adjust", {})),
                image_name=str(self._request_payload.get("image_name", "")),
            )
            self.finished.emit(agent.run_single_turn(context))
        except Exception as exc:
            self.failed.emit(str(exc))


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
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(name, layer_type, thumb_color, locked)
        self._update_style()

    def _build(self, name: str, layer_type: str,
               thumb_color: str, locked: bool) -> None:
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 0, 8, 0)
        lo.setSpacing(8)

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

        # thumbnail (28 × 28 square)
        self._thumb_lbl = QLabel()
        self._thumb_lbl.setPixmap(_layer_thumb_pixmap(thumb_color, layer_type, 28))
        self._thumb_lbl.setFixedSize(28, 28)
        self._thumb_lbl.setStyleSheet(
            f"border-radius:4px; border:{'1px solid ' + C_PRIMARY if self._active else 'none'};"
        )
        lo.addWidget(self._thumb_lbl)

        # name + type
        info_w = QWidget()
        info_w.setStyleSheet("background:transparent;")
        info_lo = QVBoxLayout(info_w)
        info_lo.setContentsMargins(0, 0, 0, 0)
        info_lo.setSpacing(0)
        n_color = C_WHITE if self._active else C_TEXT_1
        self._name_lbl = _lbl(name, n_color, 12, QFont.Weight.Medium)
        self._type_lbl = _lbl(layer_type, C_TEXT_3, 10)
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
            f"color:{n_color}; font-size:12px; font-weight:500; background:transparent;"
        )
        self._thumb_lbl.setStyleSheet(
            f"border-radius:4px; border:{'1px solid ' + C_PRIMARY if active else 'none'};"
        )
        self._refresh_eye()

    def layer_index(self) -> int:
        return self._index

    def _update_style(self) -> None:
        bg = C_BG_ACTIVE if self._active else "transparent"
        self.setStyleSheet(
            f"LayerRow{{background:{bg}; border-radius:6px;}}"
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
    """Paints an overlaid R/G/B histogram from image data."""
    _H = 96
    _BINS = 128

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self._H)
        self.setStyleSheet(
            f"background:{C_BG_ITEM}; border-radius:6px;"
        )
        self._r = [0.0] * self._BINS
        self._g = [0.0] * self._BINS
        self._b = [0.0] * self._BINS

    def set_histogram_data(self, histogram: Optional[dict[str, list[float]]]) -> None:
        histogram = histogram or {}
        self._r = list(histogram.get("red", self._r))[: self._BINS]
        self._g = list(histogram.get("green", self._g))[: self._BINS]
        self._b = list(histogram.get("blue", self._b))[: self._BINS]
        if len(self._r) < self._BINS:
            self._r.extend([0.0] * (self._BINS - len(self._r)))
        if len(self._g) < self._BINS:
            self._g.extend([0.0] * (self._BINS - len(self._g)))
        if len(self._b) < self._BINS:
            self._b.extend([0.0] * (self._BINS - len(self._b)))
        self.update()

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

        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        p.end()


class GradientSlider(QWidget):
    """Horizontal slider with a colour-gradient track and a white circle handle."""
    value_changed = pyqtSignal(int)
    value_committed = pyqtSignal(int)

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
        self._dragging = False
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int, *, emit_signal: bool = True) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.update()
            if emit_signal:
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
            self._dragging = True
            self.setValue(self._x_to_value(e.position().x()))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._x_to_value(e.position().x()))

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._dragging and e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setValue(self._x_to_value(e.position().x()))
            self.value_committed.emit(self._value)
        super().mouseReleaseEvent(e)


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
    """Interactive Lightroom-style point curve editor."""

    curve_changed = pyqtSignal(list)
    curve_change_finished = pyqtSignal(list)

    _PAD = 12
    _PT_R = 5
    _HIT_R = 11
    _GRID = 4
    _MAX_POINTS = 16

    def __init__(self, curve_color: str = "#ffffff", height: int = 160, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(curve_color)
        self.setFixedHeight(height)
        self.setMinimumWidth(60)
        self.setStyleSheet(f"background:{C_BG_ITEM}; border-radius:6px;")
        self._points: list[list[float]] = [[0.0, 0.0], [1.0, 1.0]]
        self._drag_idx = -1
        self.setCursor(Qt.CursorShape.CrossCursor)

    @classmethod
    def _default_points(cls) -> list[list[float]]:
        return [[0.0, 0.0], [1.0, 1.0]]

    @classmethod
    def _normalize_points(cls, points: Any) -> list[list[float]]:
        normalized: list[list[float]] = []
        if isinstance(points, list):
            for item in points:
                if isinstance(item, dict):
                    x_val = item.get("x")
                    y_val = item.get("y")
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    x_val, y_val = item[0], item[1]
                else:
                    continue
                try:
                    x = float(x_val)
                    y = float(y_val)
                except (TypeError, ValueError):
                    continue
                if x > 1.0 or y > 1.0:
                    x /= 255.0
                    y /= 255.0
                normalized.append([max(0.0, min(1.0, x)), max(0.0, min(1.0, y))])

        normalized.sort(key=lambda item: item[0])
        deduped: list[list[float]] = []
        for x, y in normalized:
            if deduped and abs(deduped[-1][0] - x) < 1e-6:
                deduped[-1][1] = y
            else:
                deduped.append([x, y])

        if not deduped or deduped[0][0] > 1e-6:
            deduped.insert(0, [0.0, 0.0])
        else:
            deduped[0][0] = 0.0
        if deduped[-1][0] < 1.0 - 1e-6:
            deduped.append([1.0, 1.0])
        else:
            deduped[-1][0] = 1.0

        if len(deduped) < 2:
            return cls._default_points()

        if len(deduped) > cls._MAX_POINTS:
            deduped = deduped[: cls._MAX_POINTS - 1] + [deduped[-1]]
            deduped[0][0] = 0.0
            deduped[-1][0] = 1.0
        return deduped

    @staticmethod
    def _compute_tangents(points: list[list[float]]) -> list[float]:
        count = len(points)
        if count < 2:
            return [0.0] * count
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        secants = []
        for index in range(count - 1):
            dx = max(xs[index + 1] - xs[index], 1e-6)
            secants.append((ys[index + 1] - ys[index]) / dx)

        tangents = [0.0] * count
        tangents[0] = secants[0]
        tangents[-1] = secants[-1]
        for index in range(1, count - 1):
            prev_secant = secants[index - 1]
            next_secant = secants[index]
            if prev_secant == 0.0 or next_secant == 0.0 or prev_secant * next_secant < 0.0:
                tangents[index] = 0.0
            else:
                tangents[index] = (prev_secant + next_secant) / 2.0

        for index, secant in enumerate(secants):
            if abs(secant) < 1e-6:
                tangents[index] = 0.0
                tangents[index + 1] = 0.0
                continue
            alpha = tangents[index] / secant
            beta = tangents[index + 1] / secant
            magnitude = alpha * alpha + beta * beta
            if magnitude > 9.0:
                scale = 3.0 / math.sqrt(magnitude)
                tangents[index] = scale * alpha * secant
                tangents[index + 1] = scale * beta * secant
        return tangents

    @classmethod
    def _sample_curve(cls, points: list[list[float]], sample_count: int = 160) -> list[tuple[float, float]]:
        normalized = cls._normalize_points(points)
        if len(normalized) < 2:
            return [(0.0, 0.0), (1.0, 1.0)]

        tangents = cls._compute_tangents(normalized)
        samples: list[tuple[float, float]] = []
        xs = [point[0] for point in normalized]
        sample_xs = [index / (sample_count - 1) for index in range(sample_count)]
        interval = 0
        for x in sample_xs:
            while interval < len(xs) - 2 and x > xs[interval + 1]:
                interval += 1
            x0, y0 = normalized[interval]
            x1, y1 = normalized[interval + 1]
            dx = max(x1 - x0, 1e-6)
            t = (x - x0) / dx if dx else 0.0
            t = max(0.0, min(1.0, t))
            h00 = 2.0 * t**3 - 3.0 * t**2 + 1.0
            h10 = t**3 - 2.0 * t**2 + t
            h01 = -2.0 * t**3 + 3.0 * t**2
            h11 = t**3 - t**2
            y = h00 * y0 + h10 * dx * tangents[interval] + h01 * y1 + h11 * dx * tangents[interval + 1]
            samples.append((x, max(0.0, min(1.0, y))))
        return samples

    def set_points(self, points: Any, *, emit_signal: bool = False) -> None:
        self._points = self._normalize_points(points)
        self.update()
        if emit_signal:
            self._emit_curve(committed=False)

    def points(self) -> list[dict[str, int]]:
        return [
            {"x": int(round(point[0] * 255.0)), "y": int(round(point[1] * 255.0))}
            for point in self._normalize_points(self._points)
        ]

    def _emit_curve(self, *, committed: bool) -> None:
        payload = self.points()
        if committed:
            self.curve_change_finished.emit(payload)
        else:
            self.curve_changed.emit(payload)

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

        sampled = [self._to_widget(nx, ny) for nx, ny in self._sample_curve(self._points)]
        if len(sampled) >= 2:
            path = QPainterPath()
            path.moveTo(sampled[0])
            for point in sampled[1:]:
                path.lineTo(point)
            curve_color = QColor(self._color)
            curve_color.setAlphaF(0.9)
            p.setPen(QPen(curve_color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # control points
        for i, (nx, ny) in enumerate(self._points):
            wp = self._to_widget(nx, ny)
            p.setBrush(QBrush(QColor(C_BG_PANEL)))
            point_color = QColor(self._color)
            point_color.setAlphaF(0.95 if 0 < i < len(self._points) - 1 else 0.85)
            p.setPen(QPen(point_color, 1.5))
            p.drawEllipse(wp, float(self._PT_R), float(self._PT_R))
        p.end()

    def _point_at(self, wx: float, wy: float) -> int:
        for index, (nx, ny) in enumerate(self._points):
            widget_point = self._to_widget(nx, ny)
            if abs(widget_point.x() - wx) <= self._HIT_R and abs(widget_point.y() - wy) <= self._HIT_R:
                return index
        return -1

    # ── interaction ───────────────────────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent) -> None:    # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        wx, wy = e.position().x(), e.position().y()
        hit_index = self._point_at(wx, wy)
        if hit_index >= 0:
            self._drag_idx = hit_index
            return
        if len(self._points) >= self._MAX_POINTS:
            return
        nx, ny = self._to_norm(wx, wy)
        insert_at = sum(1 for px, _ in self._points if px < nx)
        insert_at = max(1, min(len(self._points) - 1, insert_at))
        self._points.insert(insert_at, [nx, ny])
        self._drag_idx = insert_at
        self.update()
        self._emit_curve(committed=False)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:     # noqa: N802
        if self._drag_idx < 0:
            return
        i = self._drag_idx
        nx, ny = self._to_norm(e.position().x(), e.position().y())
        if i == 0:
            self._points[i] = [0.0, ny]
        elif i == len(self._points) - 1:
            self._points[i] = [1.0, ny]
        else:
            lo_x = self._points[i - 1][0] + 0.01
            hi_x = self._points[i + 1][0] - 0.01
            self._points[i] = [max(lo_x, min(hi_x, nx)), ny]
        self.update()
        self._emit_curve(committed=False)

    def mouseReleaseEvent(self, _e) -> None:              # noqa: N802
        if self._drag_idx >= 0:
            self._emit_curve(committed=True)
        self._drag_idx = -1

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:   # noqa: N802
        wx, wy = e.position().x(), e.position().y()
        hit_index = self._point_at(wx, wy)
        if 0 < hit_index < len(self._points) - 1:
            self._points.pop(hit_index)
            self.update()
            self._emit_curve(committed=True)


# ══════════════════════════════════════════════════════════════════════════════
# COLOR WHEEL  (颜色分级 section)
# ══════════════════════════════════════════════════════════════════════════════

class ColorWheelWidget(QWidget):
    """Circular hue-saturation wheel with a draggable colour dot."""

    color_changed = pyqtSignal(float, float)
    color_change_finished = pyqtSignal(float, float)

    _R = 52   # outer radius

    def __init__(self, radius: int = 52, parent=None) -> None:
        super().__init__(parent)
        self._R = max(18, int(radius))
        size = self._R * 2 + 4
        self.setFixedSize(size, size)
        self._hue = 0.0        # 0..360
        self._sat = 0.0        # 0..100  (distance from centre)
        self._dragging = False
        self._drag_mode = "free"
        self._drag_anchor_hue = 0.0
        self._drag_anchor_sat = 0.0
        self._drag_anchor_angle = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def hue(self) -> float:
        return self._hue

    def saturation(self) -> float:
        return self._sat

    def set_hs(self, hue: float, saturation: float, *, emit_signal: bool = True) -> None:
        self._hue = float(hue) % 360.0
        self._sat = max(0.0, min(100.0, float(saturation)))
        self.update()
        if emit_signal:
            self.color_changed.emit(self._hue, self._sat)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _centre(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _dot_pos(self) -> QPointF:
        cx, cy = self._centre().x(), self._centre().y()
        angle = math.radians(self._hue)
        r = (self._sat / 100.0) * self._R
        return QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle))

    def _angle_and_saturation_from_pos(self, pos: QPointF) -> tuple[float, float]:
        cx, cy = self._centre().x(), self._centre().y()
        dx, dy = pos.x() - cx, -(pos.y() - cy)
        dist = math.hypot(dx, dy)
        hue = math.degrees(math.atan2(dy, dx)) % 360.0
        saturation = min(100.0, (dist / max(self._R, 1.0)) * 100.0)
        return hue, saturation

    @staticmethod
    def _normalize_angle_delta(delta: float) -> float:
        return (delta + 180.0) % 360.0 - 180.0

    @staticmethod
    def _drag_mode_from_modifiers(modifiers: Qt.KeyboardModifier) -> str:
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return "radius"
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            return "rotate"
        return "free"

    def _sync_drag_mode_from_keyboard(self) -> None:
        if not self._dragging:
            return
        pos = QPointF(self.mapFromGlobal(QCursor.pos()))
        modifiers = QApplication.keyboardModifiers()
        mode = self._drag_mode_from_modifiers(modifiers)
        if mode != self._drag_mode:
            self._reset_drag_anchor(pos, modifiers)
        self.update()

    def _reset_drag_anchor(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        self._drag_mode = self._drag_mode_from_modifiers(modifiers)
        angle, _saturation = self._angle_and_saturation_from_pos(pos)
        self._drag_anchor_angle = angle
        self._drag_anchor_hue = self._hue
        self._drag_anchor_sat = self._sat

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

        if self._dragging and self._drag_mode != "free":
            dp = self._dot_pos()
            guide_col = QColor.fromHsvF(self._hue / 360.0, max(self._sat / 100.0, 0.08), 0.95)
            guide_col.setAlpha(230)
            p.setPen(QPen(guide_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(cx, dp)

        # dot
        dp = self._dot_pos()
        dot_col = QColor.fromHsvF(self._hue / 360.0, max(self._sat / 100.0, 0.01), 0.9)
        p.setBrush(QBrush(dot_col))
        p.setPen(QPen(QColor(C_WHITE), 1.5))
        p.drawEllipse(dp, 6.0, 6.0)
        p.end()

    # ── interaction ──────────────────────────────────────────────────────────
    def _update_from_pos(
        self,
        pos: QPointF,
        *,
        modifiers: Qt.KeyboardModifier,
        emit_signal: bool = True,
    ) -> None:
        mode = self._drag_mode_from_modifiers(modifiers)
        if self._dragging and mode != self._drag_mode:
            self._reset_drag_anchor(pos, modifiers)

        hue, saturation = self._angle_and_saturation_from_pos(pos)
        if mode == "rotate" and self._dragging:
            hue = self._drag_anchor_hue + self._normalize_angle_delta(hue - self._drag_anchor_angle)
            saturation = self._drag_anchor_sat
        elif mode == "radius" and self._dragging:
            hue = self._drag_anchor_hue

        self.set_hs(hue, saturation, emit_signal=emit_signal)

    def mousePressEvent(self, e: QMouseEvent) -> None:   # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._reset_drag_anchor(e.position(), e.modifiers())
            self._update_from_pos(e.position(), modifiers=e.modifiers())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:    # noqa: N802
        if self._dragging:
            self._update_from_pos(e.position(), modifiers=e.modifiers())

    def mouseReleaseEvent(self, _e) -> None:             # noqa: N802
        if self._dragging:
            self.color_change_finished.emit(self._hue, self._sat)
        self._dragging = False
        self._drag_mode = "free"
        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self._sync_drag_mode_from_keyboard()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        self._sync_drag_mode_from_keyboard()
        super().keyReleaseEvent(event)


class ThinSlider(QWidget):
    value_changed = pyqtSignal(int)
    value_committed = pyqtSignal(int)

    _H_PAD = 8
    _V_PAD = 8
    _HANDLE_R = 7

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        min_val: int = -100,
        max_val: int = 100,
        value: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._orientation = orientation
        self._min = min_val
        self._max = max_val
        self._value = max(self._min, min(self._max, value))
        self._dragging = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if self._orientation == Qt.Orientation.Horizontal:
            self.setFixedHeight(24)
            self.setMinimumWidth(60)
        else:
            self.setFixedWidth(22)
            self.setMinimumHeight(188)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int, *, emit_signal: bool = True) -> None:
        clamped = max(self._min, min(self._max, int(round(value))))
        if clamped != self._value:
            self._value = clamped
            self.update()
            if emit_signal:
                self.value_changed.emit(clamped)
        elif emit_signal:
            self.value_changed.emit(clamped)

    def _ratio(self) -> float:
        span = max(self._max - self._min, 1)
        return (self._value - self._min) / span

    def _handle_center(self) -> QPointF:
        ratio = self._ratio()
        if self._orientation == Qt.Orientation.Horizontal:
            x0 = float(self._H_PAD)
            x1 = float(self.width() - self._H_PAD)
            return QPointF(x0 + ratio * max(x1 - x0, 1.0), self.height() / 2)
        y0 = float(self._V_PAD)
        y1 = float(self.height() - self._V_PAD)
        return QPointF(self.width() / 2, y1 - ratio * max(y1 - y0, 1.0))

    def _pos_to_value(self, pos: QPointF) -> int:
        span = max(self._max - self._min, 1)
        if self._orientation == Qt.Orientation.Horizontal:
            x0 = float(self._H_PAD)
            x1 = float(self.width() - self._H_PAD)
            ratio = 0.0 if x1 <= x0 else (pos.x() - x0) / (x1 - x0)
        else:
            y0 = float(self._V_PAD)
            y1 = float(self.height() - self._V_PAD)
            ratio = 0.0 if y1 <= y0 else (y1 - pos.y()) / (y1 - y0)
        ratio = max(0.0, min(1.0, ratio))
        return int(round(self._min + ratio * span))

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._orientation == Qt.Orientation.Horizontal:
            y = self.height() / 2
            x0 = float(self._H_PAD)
            x1 = float(self.width() - self._H_PAD)
            pen = QPen(QColor("#474b55"), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
        else:
            x = self.width() / 2
            y0 = float(self._V_PAD)
            y1 = float(self.height() - self._V_PAD)
            track = QRectF(x - 8, y0, 16, max(y1 - y0, 1.0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#2b2f38"))
            p.drawRoundedRect(track, 8, 8)
            p.setBrush(QColor("#3b404b"))
            p.drawRoundedRect(QRectF(x - 2, y0 + 8, 4, max(y1 - y0 - 16, 1.0)), 2, 2)

        handle = self._handle_center()
        if self._orientation == Qt.Orientation.Horizontal:
            p.setBrush(QColor("#676d79"))
            p.setPen(QPen(QColor("#808692"), 1))
            p.drawEllipse(handle, self._HANDLE_R, self._HANDLE_R)
        else:
            handle_rect = QRectF(handle.x() - 8, handle.y() - 3, 16, 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#5f6470"))
            p.drawRoundedRect(handle_rect, 3, 3)

        p.end()

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self.setValue(self._pos_to_value(e.position()))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self.setValue(self._pos_to_value(e.position()))

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        if self._dragging:
            self.value_committed.emit(self._value)
        self._dragging = False


class ColorEditorWheelWidget(QWidget):
    color_changed = pyqtSignal(float, float)
    color_change_finished = pyqtSignal(float, float)

    def __init__(self, size: int = 258, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._outer_radius = (size / 2) - 14
        self._hue = 0.0
        self._saturation = 0.0
        self._dragging = False

    def hue(self) -> float:
        return self._hue

    def saturation(self) -> float:
        return self._saturation

    def set_hs(self, hue: float, saturation: float, *, emit_signal: bool = True) -> None:
        self._hue = float(hue) % 360.0
        self._saturation = max(0.0, min(100.0, float(saturation)))
        self.update()
        if emit_signal:
            self.color_changed.emit(self._hue, self._saturation)

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _radius(self) -> float:
        return self._outer_radius

    def _marker_pos(self) -> QPointF:
        center = self._center()
        angle = math.radians(self._hue)
        radius = self._radius() * (self._saturation / 100.0)
        return QPointF(
            center.x() + radius * math.cos(angle),
            center.y() - radius * math.sin(angle),
        )

    def _update_from_pos(self, pos: QPointF, *, emit_signal: bool = True) -> None:
        center = self._center()
        dx = pos.x() - center.x()
        dy = center.y() - pos.y()
        hue = math.degrees(math.atan2(dy, dx)) % 360.0
        saturation = min(100.0, (math.hypot(dx, dy) / max(self._radius(), 1.0)) * 100.0)
        self.set_hs(hue, saturation, emit_signal=emit_signal)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self._center()
        outer = self._radius()

        glow = QRadialGradient(center, outer + 8)
        glow.setColorAt(0.0, QColor(36, 40, 48, 80))
        glow.setColorAt(0.75, QColor(30, 33, 39, 35))
        glow.setColorAt(1.0, QColor(24, 26, 31, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(center, outer + 8, outer + 8)

        p.setBrush(QColor("#23262d"))
        p.setPen(QPen(QColor("#2f343d"), 2))
        p.drawEllipse(center, outer, outer)

        p.setPen(QPen(QColor("#2a2d35"), 1))
        p.drawEllipse(center, outer - 16, outer - 16)

        marker = self._marker_pos()
        p.setBrush(QColor.fromHsv(int(round(self._hue)) % 360, max(24, int(round(self._saturation * 2.55))), 220))
        p.setPen(QPen(QColor("#dfe3ea"), 1.4))
        p.drawEllipse(marker, 6.5, 6.5)

        p.end()

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._update_from_pos(e.position())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._update_from_pos(e.position())

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        if self._dragging:
            self.color_change_finished.emit(self._hue, self._saturation)
        self._dragging = False


class ColorEditorPreviewStrip(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self._input_color = QColor("#2d3139")
        self._output_color = QColor("#2d3139")

    def set_colors(self, input_color: QColor, output_color: QColor) -> None:
        self._input_color = QColor(input_color)
        self._output_color = QColor(output_color)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 4, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path, QColor("#242730"))

        clip_left = QPainterPath()
        clip_left.addRoundedRect(QRectF(rect.adjusted(0, 0, -rect.width() // 2, 0)), 4, 4)
        p.fillPath(clip_left, self._input_color)

        right_rect = QRectF(rect.x() + rect.width() / 2, rect.y(), rect.width() / 2, rect.height())
        p.fillRect(right_rect, self._output_color)
        p.setPen(QPen(QColor("#3c4049"), 1))
        p.drawLine(int(rect.center().x()), rect.top() + 3, int(rect.center().x()), rect.bottom() - 3)
        p.drawRoundedRect(QRectF(rect), 4, 4)
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ══════════════════════════════════════════════════════════════════════════════

class RightPanel(QWidget):
    """320 px right panel: panel tabs + layers content."""

    active_layer_changed = pyqtSignal(int)
    layer_visibility_changed = pyqtSignal(int, bool)
    layer_opacity_changed = pyqtSignal(int, float)
    layer_opacity_change_finished = pyqtSignal(int, float)
    adjust_section_changed = pyqtSignal(str, dict)
    adjust_section_change_finished = pyqtSignal(str, dict, str)
    mask_changed = pyqtSignal(dict)
    mask_change_finished = pyqtSignal(dict, str)
    mask_adjust_section_changed = pyqtSignal(str, dict)
    mask_adjust_section_change_finished = pyqtSignal(str, dict, str)
    mask_layer_selected = pyqtSignal(str)
    tool_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setStyleSheet(
            f"background:{C_BG_RIGHT};"
        )
        self._active_tab = "调整"
        self._active_layer = 0
        self._malayers: list = []
        self._layer_rows: list[LayerRow] = []
        self._layer_list_lo: Optional[QVBoxLayout] = None
        self._history_list_lo: Optional[QVBoxLayout] = None
        self._adjust_slider_meta: dict[GradientSlider, dict[str, Any]] = {}
        self._adjust_value_labels: dict[GradientSlider, QLabel] = {}
        self._curve_editors: dict[str, CurveEditor] = {}
        self._curve_editors_by_scope: dict[str, dict[str, CurveEditor]] = {}
        self._curve_btns_by_scope: dict[str, list[QPushButton]] = {}
        self._curve_editor_meta: dict[CurveEditor, dict[str, str]] = {}
        self._syncing_adjust_controls = False
        self._adjust_build_scope = "adjust"
        self._color_editor_wheel: Optional[ColorEditorWheelWidget] = None
        self._color_editor_wheels: dict[str, ColorEditorWheelWidget] = {}
        self._color_grading_wheels: dict[str, ColorWheelWidget] = {}
        self._color_grading_wheels_by_scope: dict[str, dict[str, ColorWheelWidget]] = {}
        self._color_grading_luminance_sliders: dict[str, ThinSlider] = {}
        self._color_grading_luminance_sliders_by_scope: dict[str, dict[str, ThinSlider]] = {}
        self._color_editor_preview: Optional[ColorEditorPreviewStrip] = None
        self._color_editor_previews: dict[str, ColorEditorPreviewStrip] = {}
        self._color_editor_input_hsl_label: Optional[QLabel] = None
        self._color_editor_input_hsl_labels: dict[str, QLabel] = {}
        self._color_editor_output_hsl_label: Optional[QLabel] = None
        self._color_editor_output_hsl_labels: dict[str, QLabel] = {}
        self._color_editor_lightness_slider: Optional[ThinSlider] = None
        self._color_editor_lightness_sliders: dict[str, ThinSlider] = {}
        self._color_editor_lightness_label: Optional[QLabel] = None
        self._color_editor_lightness_labels: dict[str, QLabel] = {}
        self._hsl_btns_by_scope: dict[str, dict[str, QPushButton]] = {}
        self._hsl_slider_groups_by_scope: dict[str, dict[str, QWidget]] = {}
        self._histogram_canvas: Optional[_HistogramCanvas] = None
        self._histogram_meta_labels: list[QLabel] = []
        self._histogram_format_badge: Optional[QLabel] = None
        self._mask_state: dict[str, Any] = {}
        self._syncing_mask_controls = False
        self._mask_tool_buttons: dict[str, QPushButton] = {}
        self._mask_invert_btn: Optional[QPushButton] = None
        self._mask_opacity_slider: Optional[QSlider] = None
        self._mask_feather_slider: Optional[QSlider] = None
        self._mask_opacity_label: Optional[QLabel] = None
        self._mask_feather_label: Optional[QLabel] = None
        self._mask_summary_label: Optional[QLabel] = None
        self._mask_layers: list = []
        self._active_mask_layer_id: Optional[str] = None
        self._mask_layer_list_lo: Optional[QVBoxLayout] = None
        self._mask_layer_buttons: dict[str, QPushButton] = {}
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

        self._stack.setCurrentIndex(1)
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
        self._opacity_slider.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._opacity_slider.sliderReleased.connect(self._on_opacity_change_finished)
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
        layer_list_lo.setSpacing(0)
        layer_list_lo.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layer_list_lo = layer_list_lo
        self.set_malayers([])

        lo.addWidget(layer_list_w, 1)

        # actions bar
        lo.addWidget(self._build_layer_actions())
        return w

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_lbl.setText(f"{value}%")
        self.layer_opacity_changed.emit(self._active_layer, value / 100.0)

    def _on_opacity_change_finished(self) -> None:
        self.layer_opacity_change_finished.emit(self._active_layer, self._opacity_slider.value() / 100.0)

    def _on_layer_selected(self, idx: int) -> None:
        for row in self._layer_rows:
            row.set_active(row.layer_index() == idx)
        self._active_layer = idx
        if 0 <= idx < len(self._malayers):
            self._opacity_slider.blockSignals(True)
            self._opacity_slider.setValue(int(getattr(self._malayers[idx], "opacity", 1.0) * 100))
            self._opacity_slider.blockSignals(False)
            self._opacity_lbl.setText(f"{self._opacity_slider.value()}%")
        self.active_layer_changed.emit(idx)

    def _on_layer_visibility(self, idx: int, visible: bool) -> None:
        self.layer_visibility_changed.emit(idx, visible)

    def set_malayers(self, malayers: list) -> None:
        if self._layer_list_lo is None:
            return
        self._malayers = list(malayers)
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
            self._opacity_lbl.setText("100%")
            self._active_layer = 0
            self.set_mask_layers([], self._active_mask_layer_id)
            return

        top_layer_index = len(malayers) - 1
        for idx in reversed(range(len(malayers))):
            malayer = malayers[idx]
            layer_type = getattr(malayer, "tab_id", getattr(malayer, "type_name", "layer"))
            row = LayerRow(idx, malayer.name, layer_type, "#404040", idx == top_layer_index, malayer.locked)
            row._eye_btn.setChecked(malayer.visible)
            row.selected.connect(self._on_layer_selected)
            row.visibility_toggled.connect(self._on_layer_visibility)
            self._layer_rows.append(row)
            self._layer_list_lo.addWidget(row)
        self._layer_list_lo.addStretch()

        self._active_layer = top_layer_index
        self._opacity_slider.blockSignals(True)
        self._opacity_slider.setValue(int(getattr(malayers[top_layer_index], "opacity", 1.0) * 100))
        self._opacity_slider.blockSignals(False)
        self._opacity_lbl.setText(f"{self._opacity_slider.value()}%")
        self.set_mask_layers(malayers, self._active_mask_layer_id)

    def set_mask_layers(self, mask_layers: list, active_layer_id: Optional[str] = None) -> None:
        self._mask_layers = [
            layer for layer in mask_layers
            if getattr(layer, "type_name", "") == "mask"
        ]
        layer_ids = {getattr(layer, "id", None) for layer in self._mask_layers}
        candidate_id = active_layer_id if active_layer_id is not None else self._active_mask_layer_id
        self._active_mask_layer_id = (
            candidate_id
            if candidate_id in layer_ids
            else getattr(self._mask_layers[-1], "id", None) if self._mask_layers else None
        )
        if self._mask_layer_list_lo is None:
            return

        while self._mask_layer_list_lo.count():
            item = self._mask_layer_list_lo.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._mask_layer_buttons.clear()

        if not self._mask_layers:
            placeholder = _lbl("暂无蒙版。选择线性或径向工具后在画布拖拽创建。", C_TEXT_4, 11)
            placeholder.setWordWrap(True)
            self._mask_layer_list_lo.addWidget(placeholder)
            return

        for layer in reversed(self._mask_layers):
            layer_id = str(getattr(layer, "id", ""))
            if not layer_id:
                continue
            button = self._build_mask_layer_button(layer)
            button.setChecked(layer_id == self._active_mask_layer_id)
            button.clicked.connect(lambda _=False, current_id=layer_id: self._on_mask_layer_selected(current_id))
            self._mask_layer_buttons[layer_id] = button
            self._mask_layer_list_lo.addWidget(button)

    def _build_mask_layer_button(self, layer: Any) -> QPushButton:
        mask = getattr(layer, "mask", None)
        mask_state = mask.to_dict() if mask is not None else {}
        type_label = self._mask_type_label(mask_state)
        opacity = int(round(float(mask_state.get("opacity", getattr(layer, "opacity", 1.0))) * 100))
        name = str(getattr(layer, "name", "") or type_label or "Mask")
        button = QPushButton(f"{name}\n{type_label} · {opacity}%")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setMinimumHeight(46)
        button.setToolTip("列表顶部的蒙版最后渲染")
        button.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_2}; border:1px solid transparent;"
            f"border-radius:6px; padding:6px 9px; font-size:11px; text-align:left;}}"
            f"QPushButton:hover{{background:#343434; color:{C_TEXT_1};}}"
            f"QPushButton:checked{{background:{C_BG_ACTIVE}; color:{C_PRIMARY_H}; border-color:{C_PRIMARY};}}"
        )
        return button

    def _on_mask_layer_selected(self, layer_id: str) -> None:
        self._active_mask_layer_id = layer_id
        for current_id, button in self._mask_layer_buttons.items():
            button.setChecked(current_id == layer_id)
        self.mask_layer_selected.emit(layer_id)

    def set_history_entries(self, entries: list[dict[str, Any]]) -> None:
        if self._history_list_lo is None:
            return
        while self._history_list_lo.count():
            item = self._history_list_lo.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not entries:
            self._history_list_lo.addWidget(_lbl("暂无历史记录", C_TEXT_4, 12))
            self._history_list_lo.addStretch()
            return

        for entry in entries:
            self._history_list_lo.addWidget(
                self._build_history_row(
                    "clock",
                    str(entry.get("description", "未命名操作")),
                    None,
                    bool(entry.get("active", False)),
                )
            )
        self._history_list_lo.addStretch()

    def set_edit_state(self, edit_state: dict[str, Any]) -> None:
        adjust_state = edit_state.get("adjust", {}) if isinstance(edit_state, dict) else {}
        self._set_adjust_controls_for_scope("adjust", adjust_state if isinstance(adjust_state, dict) else {})

    def set_mask_adjust_state(self, adjust_state: Optional[dict[str, Any]]) -> None:
        self._set_adjust_controls_for_scope("mask", adjust_state if isinstance(adjust_state, dict) else {})

    def _set_adjust_controls_for_scope(self, scope: str, adjust_state: dict[str, Any]) -> None:
        self._syncing_adjust_controls = True
        try:
            for slider, meta in self._adjust_slider_meta.items():
                if meta.get("scope", "adjust") != scope:
                    continue
                raw_value = self._read_nested_value(adjust_state, meta["state_path"])
                if raw_value is None:
                    continue
                slider_value = meta["to_slider"](raw_value)
                slider.setValue(int(round(slider_value)), emit_signal=False)
                self._adjust_value_labels[slider].setText(str(int(round(slider.value()))))
            for editor, meta in self._curve_editor_meta.items():
                if meta.get("scope", "adjust") != scope:
                    continue
                raw_value = self._read_nested_value(adjust_state, meta["state_path"])
                editor.set_points(raw_value if raw_value is not None else [{"x": 0, "y": 0}, {"x": 255, "y": 255}])
            color_editor_state = adjust_state.get("color_editor", {}) if isinstance(adjust_state, dict) else {}
            color_editor_wheel = self._color_editor_wheels.get(scope)
            if color_editor_wheel is not None and isinstance(color_editor_state, dict):
                color_editor_wheel.set_hs(
                    float(color_editor_state.get("hue", 0)),
                    float(color_editor_state.get("saturation", 0)),
                    emit_signal=False,
                )
            color_grading_state = adjust_state.get("color_grading", {}) if isinstance(adjust_state, dict) else {}
            if isinstance(color_grading_state, dict):
                for region, wheel in self._color_grading_wheels_by_scope.get(scope, {}).items():
                    wheel.set_hs(
                        float(color_grading_state.get(f"{region}_hue", 0)),
                        float(color_grading_state.get(f"{region}_saturation", 0)),
                        emit_signal=False,
                    )
                for region, slider in self._color_grading_luminance_sliders_by_scope.get(scope, {}).items():
                    slider.setValue(
                        int(round(float(color_grading_state.get(f"{region}_luminance", 0)))),
                        emit_signal=False,
                    )
        finally:
            self._syncing_adjust_controls = False
        self._refresh_color_editor_labels(scope)

    def set_histogram_data(self, histogram: Optional[dict[str, list[float]]]) -> None:
        if self._histogram_canvas is not None:
            self._histogram_canvas.set_histogram_data(histogram)

    def set_histogram_metadata(self, metadata: Optional[dict[str, Any]]) -> None:
        values = metadata or {}
        labels = [
            f"ISO {values.get('iso', '—')}",
            str(values.get("focal_length", "—")),
            str(values.get("aperture", "—")),
            str(values.get("exposure_time", "—")),
        ]
        for label_widget, text in zip(self._histogram_meta_labels, labels):
            label_widget.setText(text)
        if self._histogram_format_badge is not None:
            self._histogram_format_badge.setText(str(values.get("format", "IMG")))

    def _register_adjust_slider(
        self,
        slider: GradientSlider,
        value_label: QLabel,
        *,
        section: str,
        param_path: str,
        state_path: Optional[str] = None,
        display_label: str,
        to_model: Optional[Callable[[int], Any]] = None,
        to_slider: Optional[Callable[[Any], float]] = None,
    ) -> None:
        self._adjust_slider_meta[slider] = {
            "scope": self._adjust_build_scope,
            "section": section,
            "param_path": param_path,
            "state_path": state_path or f"{section}.{param_path}",
            "display_label": display_label,
            "to_model": to_model or (lambda value: value),
            "to_slider": to_slider or (lambda value: float(value)),
        }
        self._adjust_value_labels[slider] = value_label
        slider.value_changed.connect(lambda value, s=slider: self._on_adjust_slider_preview(s, value))
        slider.value_committed.connect(lambda value, s=slider: self._on_adjust_slider_commit(s, value))

    def _on_adjust_slider_preview(self, slider: GradientSlider, value: int) -> None:
        if self._syncing_adjust_controls:
            return
        self._emit_adjust_slider_change(slider, value, committed=False)

    def _on_adjust_slider_commit(self, slider: GradientSlider, value: int) -> None:
        if self._syncing_adjust_controls:
            return
        self._emit_adjust_slider_change(slider, value, committed=True)

    def _emit_adjust_slider_change(self, slider: GradientSlider, value: int, *, committed: bool) -> None:
        meta = self._adjust_slider_meta.get(slider)
        if meta is None:
            return
        payload = self._build_nested_payload(meta["param_path"], meta["to_model"](value))
        if meta.get("scope", "adjust") == "mask":
            if committed:
                self.mask_adjust_section_change_finished.emit(meta["section"], payload, meta["display_label"])
            else:
                self.mask_adjust_section_changed.emit(meta["section"], payload)
        elif committed:
            self.adjust_section_change_finished.emit(meta["section"], payload, meta["display_label"])
        else:
            self.adjust_section_changed.emit(meta["section"], payload)

    def _emit_curve_change(self, editor: CurveEditor, points: list[dict[str, int]], *, committed: bool) -> None:
        if self._syncing_adjust_controls:
            return
        meta = self._curve_editor_meta.get(editor)
        if meta is None:
            return
        payload = {meta["param_path"]: points}
        if meta.get("scope", "adjust") == "mask":
            if committed:
                self.mask_adjust_section_change_finished.emit("curves", payload, meta["display_label"])
            else:
                self.mask_adjust_section_changed.emit("curves", payload)
        elif committed:
            self.adjust_section_change_finished.emit("curves", payload, meta["display_label"])
        else:
            self.adjust_section_changed.emit("curves", payload)

    def _build_nested_payload(self, path: str, value: Any) -> dict[str, Any]:
        parts = path.split(".")
        payload: Any = value
        for part in reversed(parts):
            payload = {part: payload}
        return payload

    def _read_nested_value(self, mapping: dict[str, Any], path: str) -> Any:
        current: Any = mapping
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

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

    def _add_mask_slider_row(
        self,
        parent_lo: QVBoxLayout,
        label: str,
        value: int,
        callback: Optional[Callable[[int], None]] = None,
    ) -> tuple[QSlider, QLabel]:
        row = QWidget()
        row_lo = QHBoxLayout(row)
        row_lo.setContentsMargins(0, 0, 0, 0)
        row_lo.setSpacing(8)

        row_lo.addWidget(_lbl(label, C_TEXT_2, 11))

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(value)
        slider.setFixedHeight(18)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
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
        if callback is not None:
            slider.valueChanged.connect(callback)
        row_lo.addWidget(value_lbl)
        parent_lo.addWidget(row)
        return slider, value_lbl

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

        lo.addWidget(self._mask_title("Mask Tools"))
        lo.addWidget(self._mask_subtitle("Create linear or radial gradient masks by choosing a tool and dragging on the canvas."))

        tools = QWidget()
        tools_lo = QHBoxLayout(tools)
        tools_lo.setContentsMargins(0, 0, 0, 0)
        tools_lo.setSpacing(8)
        tool_defs = (
            ("linear", "Linear", "mask-linear", True),
            ("radial", "Radial", "mask-radial", True),
            ("brush", "Brush", "paintbrush", False),
            ("ai", "AI", "wand-2", False),
        )
        for key, text, tool_name, enabled in tool_defs:
            btn = self._build_mask_tool_button(text, active=False)
            btn.setEnabled(enabled)
            btn.setToolTip("Reserved for a later phase" if not enabled else "Drag on the canvas to create")
            if enabled:
                btn.clicked.connect(lambda _=False, k=key, t=tool_name: self._select_mask_tool(k, t))
            self._mask_tool_buttons[key] = btn
            tools_lo.addWidget(btn)
        lo.addWidget(tools)

        lo.addWidget(_hline())
        lo.addWidget(self._mask_title("蒙版列表"))
        lo.addWidget(self._mask_subtitle("顶部蒙版最后渲染，底部蒙版最先渲染。点击条目切换当前编辑蒙版。"))
        mask_list = QWidget()
        mask_list_lo = QVBoxLayout(mask_list)
        mask_list_lo.setContentsMargins(0, 0, 0, 0)
        mask_list_lo.setSpacing(6)
        self._mask_layer_list_lo = mask_list_lo
        self.set_mask_layers(self._mask_layers, self._active_mask_layer_id)
        lo.addWidget(mask_list)

        lo.addWidget(_hline())
        lo.addWidget(self._mask_title("Current Mask"))
        self._mask_summary_label = self._mask_subtitle("No mask yet. You can also pass JSON with a mask field.")
        lo.addWidget(self._mask_summary_label)

        param_box = QFrame()
        param_box.setStyleSheet(f"background:{C_BG_ITEM}; border-radius:8px;")
        param_lo = QVBoxLayout(param_box)
        param_lo.setContentsMargins(10, 10, 10, 10)
        param_lo.setSpacing(8)
        self._mask_opacity_slider, self._mask_opacity_label = self._add_mask_slider_row(
            param_lo, "Opacity", 100, callback=self._on_mask_opacity_changed
        )
        self._mask_opacity_slider.sliderReleased.connect(lambda: self._commit_current_mask("Mask opacity"))
        self._mask_feather_slider, self._mask_feather_label = self._add_mask_slider_row(
            param_lo, "Feather", 60, callback=self._on_mask_feather_changed
        )
        self._mask_feather_slider.sliderReleased.connect(lambda: self._commit_current_mask("Mask feather"))
        lo.addWidget(param_box)

        action_row = QWidget()
        action_lo = QHBoxLayout(action_row)
        action_lo.setContentsMargins(0, 4, 0, 0)
        action_lo.setSpacing(8)

        self._mask_invert_btn = QPushButton("Invert")
        self._mask_invert_btn.setCheckable(True)
        self._mask_invert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mask_invert_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mask_invert_btn.setFixedHeight(34)
        self._mask_invert_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:{C_TEXT_2}; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:0 14px; font-size:12px;}}"
            f"QPushButton:hover{{border-color:#4a4a4a; color:{C_TEXT_1};}}"
            f"QPushButton:checked{{background:{C_BG_ACTIVE}; color:{C_PRIMARY_H}; border-color:{C_PRIMARY};}}"
        )
        self._mask_invert_btn.clicked.connect(self._on_mask_invert_toggled)
        action_lo.addWidget(self._mask_invert_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        clear_btn.setFixedHeight(34)
        clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:#d66; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:0 14px; font-size:12px;}}"
            f"QPushButton:hover{{border-color:#6a3a3a; background:#2a1f1f;}}"
        )
        clear_btn.clicked.connect(self._clear_mask)
        action_lo.addWidget(clear_btn)
        action_lo.addStretch()
        lo.addWidget(action_row)

        lo.addWidget(_hline())
        lo.addWidget(self._mask_title("蒙版调色"))
        self._build_mask_adjust_content(lo)

        note_box = QFrame()
        note_box.setStyleSheet(f"background:{C_BG_ITEM}; border-radius:8px;")
        note_lo = QVBoxLayout(note_box)
        note_lo.setContentsMargins(10, 10, 10, 10)
        note_lo.setSpacing(4)
        note_lo.addWidget(_lbl("JSON API Example", C_TEXT_2, 11, QFont.Weight.Medium))
        example = (
            '{"mask":{"type":"linear","start":{"x":0.5,"y":0.0},'
            '"end":{"x":0.5,"y":0.45},"opacity":1.0}}'
        )
        example_lbl = _lbl(example, C_TEXT_4, 10)
        example_lbl.setWordWrap(True)
        note_lo.addWidget(example_lbl)
        note_lo.addWidget(_lbl("Brush and AI mask entries are reserved for future phases.", C_TEXT_4, 10))
        lo.addWidget(note_box)

        lo.addStretch()
        scroll.setWidget(body)
        return scroll

    def _build_mask_adjust_content(self, lo: QVBoxLayout) -> None:
        old_scope = self._adjust_build_scope
        self._adjust_build_scope = "mask"
        try:
            section_defs = [
                ("白平衡", True, self._build_wb_content),
                ("影调", False, self._build_tone_content),
                ("曲线", False, self._build_curves_content),
                ("HSL", False, self._build_hsl_content),
                ("色彩编辑器", False, self._build_color_editor_content),
                ("颜色分级", False, self._build_color_grading_content),
            ]
            for index, (title, expanded, builder) in enumerate(section_defs):
                if index > 0:
                    sep = QFrame()
                    sep.setFrameShape(QFrame.Shape.HLine)
                    sep.setFixedHeight(1)
                    sep.setStyleSheet(f"background:{C_BORDER_P}; border:none;")
                    lo.addWidget(sep)
                section = AdjustSection(title, expanded=expanded)
                builder(section.content_lo)
                lo.addWidget(section)
        finally:
            self._adjust_build_scope = old_scope

    def _select_mask_tool(self, key: str, tool_name: str) -> None:
        for button_key, button in self._mask_tool_buttons.items():
            button.setChecked(button_key == key)
        self.tool_requested.emit(tool_name)

    def _mask_type_label(self, mask_state: dict[str, Any]) -> str:
        mask_type = str(mask_state.get("type", mask_state.get("mask_type", ""))).lower()
        labels = {
            "linear": "Linear Gradient",
            "linear_gradient": "Linear Gradient",
            "radial": "Radial Gradient",
            "radial_gradient": "Radial Gradient",
            "image": "Image Mask",
            "full": "Full Mask",
        }
        return labels.get(mask_type, mask_type or "No Mask")

    def set_mask_state(self, mask_state: Optional[dict[str, Any]]) -> None:
        self._mask_state = dict(mask_state or {})
        self._syncing_mask_controls = True
        try:
            opacity = int(round(float(self._mask_state.get("opacity", 1.0)) * 100)) if self._mask_state else 100
            feather = int(round(float(self._mask_state.get("feather", 0.6)) * 100)) if self._mask_state else 60
            invert = bool(self._mask_state.get("invert", False)) if self._mask_state else False
            if self._mask_opacity_slider is not None:
                self._mask_opacity_slider.setValue(max(0, min(100, opacity)))
            if self._mask_feather_slider is not None:
                self._mask_feather_slider.setValue(max(0, min(100, feather)))
            if self._mask_invert_btn is not None:
                self._mask_invert_btn.setChecked(invert)
        finally:
            self._syncing_mask_controls = False
        self._refresh_mask_summary()

    def _refresh_mask_summary(self) -> None:
        if self._mask_summary_label is None:
            return
        if not self._mask_state:
            self._mask_summary_label.setText("No mask yet. Create one from the canvas or pass JSON with a mask field.")
            return
        self._mask_summary_label.setText(
            f"Current: {self._mask_type_label(self._mask_state)} · "
            f"Opacity {int(round(float(self._mask_state.get('opacity', 1.0)) * 100))}% · "
            f"Invert {'on' if self._mask_state.get('invert') else 'off'}"
        )

    def _update_mask_state(self, updates: dict[str, Any], *, committed: bool, description: str) -> None:
        if self._syncing_mask_controls:
            return
        next_state = dict(self._mask_state)
        next_state.update(updates)
        self._mask_state = next_state
        self._refresh_mask_summary()
        if committed:
            self.mask_change_finished.emit(next_state, description)
        else:
            self.mask_changed.emit(next_state)

    def apply_mask_state(self, mask_state: dict[str, Any], *, committed: bool = False, description: str = "Mask") -> None:
        self.set_mask_state(mask_state)
        if committed:
            self.mask_change_finished.emit(dict(self._mask_state), description)
        else:
            self.mask_changed.emit(dict(self._mask_state))

    def _on_mask_opacity_changed(self, value: int) -> None:
        self._update_mask_state(
            {"opacity": max(0.0, min(1.0, value / 100.0))},
            committed=False,
            description="Mask opacity",
        )

    def _on_mask_feather_changed(self, value: int) -> None:
        self._update_mask_state(
            {"feather": max(0.0, min(1.0, value / 100.0))},
            committed=False,
            description="Mask feather",
        )

    def _commit_current_mask(self, description: str) -> None:
        if self._syncing_mask_controls or not self._mask_state:
            return
        self.mask_change_finished.emit(dict(self._mask_state), description)

    def _on_mask_invert_toggled(self, checked: bool) -> None:
        self._update_mask_state({"invert": checked}, committed=True, description="Mask invert")

    def _clear_mask(self) -> None:
        self._mask_state = {}
        self._refresh_mask_summary()
        self.mask_change_finished.emit({}, "Clear mask")

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
        self._history_list_lo = lo
        self.set_history_entries([])
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
            ("曲线",      False, ""),
            ("HSL",       False, ""),
            ("色彩编辑器", False, ""),
            ("颜色分级",  False, ""),
            ("细节",      False, ""),
            ("镜头",      False, ""),
            ("透视矫正",  False, ""),
            ("颜色校准",  False, ""),
        ]
        _BUILDERS = {
            "白平衡":   self._build_wb_content,
            "影调":     self._build_tone_content,
            "曲线":     self._build_curves_content,
            "HSL":      self._build_hsl_content,
            "色彩编辑器": self._build_color_editor_content,
            "颜色分级": self._build_color_grading_content,
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

        self._histogram_canvas = _HistogramCanvas()
        lo.addWidget(self._histogram_canvas)

        exif_row = QWidget()
        exif_lo = QHBoxLayout(exif_row)
        exif_lo.setContentsMargins(2, 0, 2, 0)
        exif_lo.setSpacing(8)
        self._histogram_meta_labels = []
        for txt in ("ISO —", "—", "—", "—"):
            label = _lbl(txt, C_TEXT_4, 11)
            self._histogram_meta_labels.append(label)
            exif_lo.addWidget(label)

        self._histogram_format_badge = QLabel("IMG")
        self._histogram_format_badge.setStyleSheet(
            f"color:{C_TEXT_3}; background:{C_BG_ITEM}; font-size:10px;"
            "border-radius:3px; padding:1px 5px;"
        )
        exif_lo.addWidget(self._histogram_format_badge)
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
            section="white_balance",
            param_path="temperature",
            display_label="白平衡 · 色温",
            to_model=lambda value: int(6500 + value * 35),
            to_slider=lambda value: (float(value) - 6500.0) / 35.0,
        )
        # 色调: green → magenta
        self._add_gradient_slider_row(
            lo, "色调", 0, "#44bb44", "#cc44cc", -100, 100, 0,
            section="white_balance",
            param_path="tint",
            display_label="白平衡 · 色调",
        )

    def _add_gradient_slider_row(
        self, lo: QVBoxLayout,
        label: str, value: int,
        left_color: str, right_color: str,
        min_val: int, max_val: int, default: int,
        on_change=None,
        *,
        section: Optional[str] = None,
        param_path: Optional[str] = None,
        state_path: Optional[str] = None,
        display_label: Optional[str] = None,
        to_model: Optional[Callable[[int], Any]] = None,
        to_slider: Optional[Callable[[Any], float]] = None,
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
        slider.value_changed.connect(lambda v, lb=val_lbl: lb.setText(str(v)))
        row_lo.addWidget(slider)

        if section and param_path:
            self._register_adjust_slider(
                slider,
                val_lbl,
                section=section,
                param_path=param_path,
                state_path=state_path,
                display_label=display_label or label,
                to_model=to_model,
                to_slider=to_slider,
            )

        lo.addWidget(row)

    def _add_thin_slider_row(
        self,
        lo: QVBoxLayout,
        label: str,
        value: int,
        *,
        min_val: int = -100,
        max_val: int = 100,
        section: Optional[str] = None,
        param_path: Optional[str] = None,
        display_label: Optional[str] = None,
        on_change: Optional[Callable[[int], None]] = None,
    ) -> ThinSlider:
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        row_lo = QVBoxLayout(row)
        row_lo.setContentsMargins(0, 0, 0, 0)
        row_lo.setSpacing(4)

        top = QWidget()
        top_lo = QHBoxLayout(top)
        top_lo.setContentsMargins(0, 0, 0, 0)
        top_lo.setSpacing(0)
        top_lo.addWidget(_lbl(label, C_TEXT_2, 12))
        top_lo.addStretch()
        value_label = _lbl(str(value), C_TEXT_4, 11)
        top_lo.addWidget(value_label)
        row_lo.addWidget(top)

        slider = ThinSlider(Qt.Orientation.Horizontal, min_val, max_val, value)
        slider.value_changed.connect(lambda v, lb=value_label: lb.setText(str(v)))
        if on_change is not None:
            slider.value_changed.connect(on_change)
        if section and param_path:
            self._register_adjust_slider(
                slider,
                value_label,
                section=section,
                param_path=param_path,
                display_label=display_label or label,
            )
        row_lo.addWidget(slider)
        lo.addWidget(row)
        return slider

    def _format_color_editor_hsl(self, hue: float, saturation: int, lightness: int) -> str:
        return f"H:{int(round(hue)):03d}  S:{int(round(saturation)):02d}  L:{int(round(lightness)):03d}"

    def _color_editor_state_value(self, key: str, default: int = 0, scope: Optional[str] = None) -> int:
        target_scope = scope or self._adjust_build_scope
        for slider, meta in self._adjust_slider_meta.items():
            if (
                meta.get("scope", "adjust") == target_scope
                and meta.get("section") == "color_editor"
                and meta.get("param_path") == key
            ):
                try:
                    return int(round(slider.value()))
                except Exception:
                    return default
        return default

    def _refresh_color_editor_labels(self, scope: Optional[str] = None) -> None:
        target_scope = scope or self._adjust_build_scope
        color_editor_wheel = self._color_editor_wheels.get(target_scope)
        if color_editor_wheel is None:
            return
        hue = color_editor_wheel.hue()
        saturation = int(round(color_editor_wheel.saturation()))
        lightness = self._color_editor_state_value("lightness", scope=target_scope)
        hue_shift = self._color_editor_state_value("hue_shift", scope=target_scope)
        saturation_shift = self._color_editor_state_value("saturation_shift", scope=target_scope)
        luminance_shift = self._color_editor_state_value("luminance_shift", scope=target_scope)

        output_hue = (hue + hue_shift) % 360
        output_saturation = max(0, min(100, saturation + saturation_shift))
        output_lightness = max(-100, min(100, lightness + luminance_shift))

        input_label = self._color_editor_input_hsl_labels.get(target_scope)
        output_label = self._color_editor_output_hsl_labels.get(target_scope)
        if input_label is not None:
            input_label.setText(
                self._format_color_editor_hsl(hue, saturation, lightness)
            )
        if output_label is not None:
            output_label.setText(
                self._format_color_editor_hsl(output_hue, output_saturation, output_lightness)
            )

        preview = self._color_editor_previews.get(target_scope)
        if preview is not None:
            input_color = QColor.fromHsl(
                int(round(hue)) % 360,
                int(round(saturation * 2.55)),
                int(round((lightness + 100) / 200 * 255)),
            )
            output_color = QColor.fromHsl(
                int(round(output_hue)) % 360,
                int(round(output_saturation * 2.55)),
                int(round((output_lightness + 100) / 200 * 255)),
            )
            preview.set_colors(input_color, output_color)

    def _emit_color_editor_wheel_change(self, hue: float, saturation: float, *, committed: bool, scope: Optional[str] = None) -> None:
        target_scope = scope or self._adjust_build_scope
        self._refresh_color_editor_labels(target_scope)
        payload = {
            "hue": int(round(hue)) % 360,
            "saturation": int(round(saturation)),
        }
        if self._syncing_adjust_controls:
            return
        if target_scope == "mask":
            if committed:
                self.mask_adjust_section_change_finished.emit("color_editor", payload, "色彩编辑器 · 取样颜色")
            else:
                self.mask_adjust_section_changed.emit("color_editor", payload)
        elif committed:
            self.adjust_section_change_finished.emit("color_editor", payload, "色彩编辑器 · 取样颜色")
        else:
            self.adjust_section_changed.emit("color_editor", payload)

    def apply_color_editor_sample(self, color: QColor, *, committed: bool = True) -> None:
        target_scope = "mask" if self._active_tab == "蒙板" else "adjust"
        hue, saturation, lightness, _alpha = color.getHsl()
        hue_value = 0 if hue < 0 else int(hue)
        saturation_value = int(round((saturation / 255.0) * 100.0))
        lightness_value = int(round((lightness / 255.0) * 200.0 - 100.0))

        self._syncing_adjust_controls = True
        try:
            color_editor_wheel = self._color_editor_wheels.get(target_scope)
            lightness_slider = self._color_editor_lightness_sliders.get(target_scope)
            lightness_label = self._color_editor_lightness_labels.get(target_scope)
            if color_editor_wheel is not None:
                color_editor_wheel.set_hs(hue_value, saturation_value, emit_signal=False)
            if lightness_slider is not None:
                lightness_slider.setValue(lightness_value, emit_signal=False)
            if lightness_label is not None:
                lightness_label.setText(str(lightness_value))
        finally:
            self._syncing_adjust_controls = False

        self._refresh_color_editor_labels(target_scope)
        payload = {
            "hue": hue_value,
            "saturation": saturation_value,
            "lightness": lightness_value,
        }
        if target_scope == "mask":
            if committed:
                self.mask_adjust_section_change_finished.emit("color_editor", payload, "色彩编辑器 · 取样颜色")
            else:
                self.mask_adjust_section_changed.emit("color_editor", payload)
        elif committed:
            self.adjust_section_change_finished.emit("color_editor", payload, "色彩编辑器 · 取样颜色")
        else:
            self.adjust_section_changed.emit("color_editor", payload)

    def _build_color_editor_content(self, lo: QVBoxLayout) -> None:
        scope = self._adjust_build_scope
        pick_button = QPushButton("用吸管在照片中吸取颜色")
        pick_button.setIcon(_qicon("eyedropper", 14, C_TEXT_2))
        pick_button.setIconSize(QSize(14, 14))
        pick_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pick_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pick_button.setToolTip("启用吸管后，在照片上单击即可取样颜色")
        pick_button.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; color:{C_TEXT_2};"
            f"font-size:12px; text-align:left; padding:0;}}"
            f"QPushButton:hover{{color:{C_TEXT_1};}}"
            f"QPushButton:pressed{{color:{C_PRIMARY};}}"
        )
        pick_button.clicked.connect(lambda: self.tool_requested.emit("pipette"))
        lo.addWidget(pick_button, 0, Qt.AlignmentFlag.AlignLeft)
        lo.addSpacing(6)

        wheel_row = QWidget()
        wheel_lo = QHBoxLayout(wheel_row)
        wheel_lo.setContentsMargins(0, 0, 0, 0)
        wheel_lo.setSpacing(12)

        self._color_editor_wheel = ColorEditorWheelWidget(size=258)
        self._color_editor_wheels[scope] = self._color_editor_wheel
        self._color_editor_wheel.color_changed.connect(
            lambda hue, sat, current_scope=scope: self._emit_color_editor_wheel_change(hue, sat, committed=False, scope=current_scope)
        )
        self._color_editor_wheel.color_change_finished.connect(
            lambda hue, sat, current_scope=scope: self._emit_color_editor_wheel_change(hue, sat, committed=True, scope=current_scope)
        )
        wheel_lo.addWidget(self._color_editor_wheel, 1)

        lightness_col = QWidget()
        lightness_lo = QVBoxLayout(lightness_col)
        lightness_lo.setContentsMargins(0, 2, 0, 2)
        lightness_lo.setSpacing(8)
        lightness_lo.addStretch()
        lightness_label = _lbl("0", C_TEXT_4, 11)
        lightness_slider = ThinSlider(Qt.Orientation.Vertical, -100, 100, 0)
        lightness_slider.value_changed.connect(lambda v, lb=lightness_label: lb.setText(str(v)))
        lightness_slider.value_changed.connect(lambda _v, current_scope=scope: self._refresh_color_editor_labels(current_scope))
        lightness_lo.addWidget(lightness_slider, 0, Qt.AlignmentFlag.AlignHCenter)
        lightness_lo.addWidget(lightness_label, 0, Qt.AlignmentFlag.AlignHCenter)
        lightness_lo.addStretch()
        wheel_lo.addWidget(lightness_col, 0, Qt.AlignmentFlag.AlignVCenter)
        self._color_editor_lightness_slider = lightness_slider
        self._color_editor_lightness_label = lightness_label
        self._color_editor_lightness_sliders[scope] = lightness_slider
        self._color_editor_lightness_labels[scope] = lightness_label

        self._register_adjust_slider(
            lightness_slider,
            lightness_label,
            section="color_editor",
            param_path="lightness",
            display_label="色彩编辑器 · 明亮度",
        )
        wheel_lo.addStretch()
        lo.addWidget(wheel_row)

        self._color_editor_preview = ColorEditorPreviewStrip()
        self._color_editor_previews[scope] = self._color_editor_preview
        lo.addWidget(self._color_editor_preview)

        hsl_row = QWidget()
        hsl_lo = QHBoxLayout(hsl_row)
        hsl_lo.setContentsMargins(0, 0, 0, 0)
        hsl_lo.setSpacing(0)
        self._color_editor_input_hsl_label = _lbl("H:---  S:--  L:---", C_TEXT_4, 11)
        self._color_editor_output_hsl_label = _lbl("H:---  S:--  L:---", C_TEXT_4, 11)
        self._color_editor_input_hsl_labels[scope] = self._color_editor_input_hsl_label
        self._color_editor_output_hsl_labels[scope] = self._color_editor_output_hsl_label
        hsl_lo.addWidget(self._color_editor_input_hsl_label)
        hsl_lo.addStretch()
        hsl_lo.addWidget(self._color_editor_output_hsl_label)
        lo.addWidget(hsl_row)

        pair_row = QWidget()
        pair_lo = QHBoxLayout(pair_row)
        pair_lo.setContentsMargins(0, 4, 0, 0)
        pair_lo.setSpacing(8)

        pair_left = QWidget()
        pair_left_lo = QVBoxLayout(pair_left)
        pair_left_lo.setContentsMargins(0, 0, 0, 0)
        pair_left_lo.setSpacing(4)
        self._add_thin_slider_row(
            pair_left_lo,
            "色彩平滑",
            50,
            min_val=0,
            max_val=100,
            section="color_editor",
            param_path="color_smoothness",
            display_label="色彩编辑器 · 色彩平滑",
        )
        pair_lo.addWidget(pair_left, 1)

        link_btn = QPushButton("⇄")
        link_btn.setCheckable(True)
        link_btn.setChecked(True)
        link_btn.setFixedSize(30, 30)
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        link_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_3}; border:none; border-radius:6px; font-size:13px;}}"
            f"QPushButton:hover{{background:#363a42; color:{C_TEXT_1};}}"
            f"QPushButton:checked{{background:#3a3e47; color:{C_TEXT_1};}}"
        )
        pair_lo.addWidget(link_btn, 0, Qt.AlignmentFlag.AlignBottom)

        pair_right = QWidget()
        pair_right_lo = QVBoxLayout(pair_right)
        pair_right_lo.setContentsMargins(0, 0, 0, 0)
        pair_right_lo.setSpacing(4)
        self._add_thin_slider_row(
            pair_right_lo,
            "亮度平滑",
            50,
            min_val=0,
            max_val=100,
            section="color_editor",
            param_path="luminance_smoothness",
            display_label="色彩编辑器 · 亮度平滑",
        )
        pair_lo.addWidget(pair_right, 1)
        lo.addWidget(pair_row)

        self._add_thin_slider_row(
            lo,
            "色相偏移",
            0,
            section="color_editor",
            param_path="hue_shift",
            display_label="色彩编辑器 · 色相偏移",
            on_change=lambda _v, current_scope=scope: self._refresh_color_editor_labels(current_scope),
        )
        self._add_thin_slider_row(
            lo,
            "饱和度偏移",
            0,
            section="color_editor",
            param_path="saturation_shift",
            display_label="色彩编辑器 · 饱和度偏移",
            on_change=lambda _v, current_scope=scope: self._refresh_color_editor_labels(current_scope),
        )
        self._add_thin_slider_row(
            lo,
            "明亮度偏移",
            0,
            section="color_editor",
            param_path="luminance_shift",
            display_label="色彩编辑器 · 明亮度偏移",
            on_change=lambda _v, current_scope=scope: self._refresh_color_editor_labels(current_scope),
        )
        self._refresh_color_editor_labels(scope)

    # ── 影调 section ──────────────────────────────────────────────────────────

    def _build_tone_content(self, lo: QVBoxLayout) -> None:
        """Tone section: 曝光/对比度/亮度/高光/阴影/白色/黑色/清晰度/去雾/鲜艳度/饱和度."""
        _SLIDERS = [
            ("曝光",  0,   "#1a1a1a", "#ffffff", -200, 200, "exposure", lambda value: round(value / 100.0, 2), lambda value: float(value) * 100.0),
            ("对比度", 0,  "#1a1a1a", "#ffffff", -100, 100, "contrast", None, None),
            ("亮度",  0,   "#1a1a1a", "#f0f0f0", -100, 100, "brightness", None, None),
            ("高光",  0,   "#888888", "#ffffff", -100, 100, "highlights", None, None),
            ("阴影",  0,   "#000000", "#888888", -100, 100, "shadows", None, None),
            ("白色",  0,   "#666666", "#ffffff", -100, 100, "whites", None, None),
            ("黑色",  0,   "#000000", "#555555", -100, 100, "blacks", None, None),
            ("清晰度", 0, "#4a4a4a", "#f5f5f5", -100, 100, "clarity", None, None),
            ("去雾", 0,   "#5e5e5e", "#d9d9d9", -100, 100, "dehaze", None, None),
        ]
        for label, val, lc, rc, mn, mx, param_path, to_model, to_slider in _SLIDERS:
            self._add_gradient_slider_row(
                lo, label, val, lc, rc, mn, mx, 0,
                section="tone",
                param_path=param_path,
                display_label=f"影调 · {label}",
                to_model=to_model,
                to_slider=to_slider,
            )

        for label, lc, rc, param_path in [
            ("鲜艳度", "#5a5a5a", "#ffb347", "vibrance"),
            ("饱和度", "#5a5a5a", "#ff8a65", "saturation"),
        ]:
            self._add_gradient_slider_row(
                lo, label, 0, lc, rc, -100, 100, 0,
                section="hsl",
                param_path=param_path,
                display_label=f"影调 · {label}",
            )

    # ── 曲线 section ──────────────────────────────────────────────────────────

    def _build_curves_content(self, lo: QVBoxLayout) -> None:
        """Curves section: Lightroom-style point curve for RGB/R/G/B."""
        scope = self._adjust_build_scope
        btn_row = QWidget()
        btn_row.setStyleSheet("background:transparent;")
        btn_lo = QHBoxLayout(btn_row)
        btn_lo.setContentsMargins(0, 0, 0, 4)
        btn_lo.setSpacing(6)

        _CH_CIRCLES = [
            ("RGB", "#cccccc", "rgb_curve", True),
            ("R", "#ff2d3d", "red_curve", False),
            ("G", "#0fd328", "green_curve", False),
            ("B", "#2c82ea", "blue_curve", False),
        ]
        self._curve_btns: list[QPushButton] = []
        self._curve_btns_by_scope[scope] = self._curve_btns
        self._curve_editors_by_scope[scope] = {}

        for ch_label, ch_color, _curve_key, active in _CH_CIRCLES:
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
            b._adjust_scope = scope   # type: ignore[attr-defined]
            b.clicked.connect(lambda _, bn=b: self._on_curve_channel(bn))
            btn_lo.addWidget(b)
            self._curve_btns.append(b)

        btn_lo.addStretch()
        lo.addWidget(btn_row)

        for ch_label, ch_color, curve_key, active in _CH_CIRCLES:
            ed = CurveEditor(curve_color=ch_color, height=150)
            ed.setVisible(active)
            ed.curve_changed.connect(lambda points, editor=ed: self._emit_curve_change(editor, points, committed=False))
            ed.curve_change_finished.connect(lambda points, editor=ed: self._emit_curve_change(editor, points, committed=True))
            self._curve_editors[ch_label] = ed
            self._curve_editors_by_scope[scope][ch_label] = ed
            self._curve_editor_meta[ed] = {
                "scope": scope,
                "param_path": curve_key,
                "state_path": f"curves.{curve_key}",
                "display_label": f"曲线 · {ch_label}",
            }
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
        scope = getattr(clicked_btn, "_adjust_scope", "adjust")
        curve_btns = self._curve_btns_by_scope.get(scope, self._curve_btns)
        curve_editors = self._curve_editors_by_scope.get(scope, self._curve_editors)
        for b in curve_btns:
            active = (b is clicked_btn)
            b.setChecked(active)
            col = b._ch_color  # type: ignore[attr-defined]
            border = f"2px solid {C_WHITE}" if active else f"1px solid {C_BORDER}"
            b.setStyleSheet(
                f"QPushButton{{background:{col}; border-radius:11px; border:{border};}}"
                f"QPushButton:checked{{border:2px solid {C_WHITE};}}"
                f"QPushButton:hover{{border:2px solid #999999;}}"
            )
            curve_editors[b._ch_label].setVisible(active)   # type: ignore[attr-defined]

    # ── HSL section ───────────────────────────────────────────────────────────

    def _build_hsl_content(self, lo: QVBoxLayout) -> None:
        """HSL section: 色相/饱和度/明亮度 tab buttons + 8 gradient sliders."""
        scope = self._adjust_build_scope
        # sub-tab buttons
        tab_row = QWidget()
        tab_row.setStyleSheet("background:transparent;")
        tr_lo = QHBoxLayout(tab_row)
        tr_lo.setContentsMargins(0, 0, 0, 0)
        tr_lo.setSpacing(4)

        self._hsl_mode = "色相"
        self._hsl_btns: dict[str, QPushButton] = {}
        self._hsl_slider_groups: dict[str, QWidget] = {}
        self._hsl_btns_by_scope[scope] = self._hsl_btns
        self._hsl_slider_groups_by_scope[scope] = self._hsl_slider_groups

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
            b._adjust_scope = scope  # type: ignore[attr-defined]
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
            ("红色",  "red",     "#ff44aa", "#ff4444"),
            ("橙色",  "orange",  "#ff4400", "#ffaa00"),
            ("黄色",  "yellow",  "#ffaa00", "#aacc00"),
            ("绿色",  "green",   "#aacc00", "#00bbaa"),
            ("浅绿色", "aqua",    "#00bbaa", "#0088cc"),
            ("蓝色",  "blue",    "#0088cc", "#6655ff"),
            ("紫色",  "purple",  "#6655ff", "#cc44cc"),
            ("洋红色", "magenta", "#cc44cc", "#ff44aa"),
        ]
        mode_paths = {
            "色相": "hue",
            "饱和度": "saturation",
            "明亮度": "luminance",
        }

        for mode in _HSL_TABS:
            grp = QWidget()
            grp.setStyleSheet("background:transparent;")
            grp_lo = QVBoxLayout(grp)
            grp_lo.setContentsMargins(0, 0, 0, 0)
            grp_lo.setSpacing(6)
            for color_name, color_key, lc, rc in _COLORS:
                self._add_gradient_slider_row(
                    grp_lo, color_name, 0, lc, rc, -100, 100, 0,
                    section="hsl",
                    param_path=f"{color_key}.{mode_paths[mode]}",
                    display_label=f"HSL · {color_name} · {mode}",
                )
            grp.setVisible(mode == "色相")
            self._hsl_slider_groups[mode] = grp
            lo.addWidget(grp)

    def _on_hsl_mode(self, clicked_btn: QPushButton) -> None:
        scope = getattr(clicked_btn, "_adjust_scope", "adjust")
        hsl_btns = self._hsl_btns_by_scope.get(scope, self._hsl_btns)
        hsl_slider_groups = self._hsl_slider_groups_by_scope.get(scope, self._hsl_slider_groups)
        for mode, b in hsl_btns.items():
            active = (b is clicked_btn)
            b.setChecked(active)
            b.setStyleSheet(
                f"QPushButton{{background:{'#3a3a3a' if active else 'transparent'};"
                f"color:{C_TEXT_1 if active else C_TEXT_3};"
                f"border-radius:4px; border:none; font-size:12px; font-weight:{'500' if active else 'normal'};}}"
                f"QPushButton:hover{{color:{C_TEXT_1}; background:#333333;}}"
            )
            hsl_slider_groups[mode].setVisible(active)

    # ── 颜色分级 section ──────────────────────────────────────────────────────

    def _build_color_grading_content(self, lo: QVBoxLayout) -> None:
        """Color grading: sphere preset row + 3 color wheels with lum sliders."""
        scope = self._adjust_build_scope
        self._color_grading_wheels_by_scope[scope] = {}
        self._color_grading_luminance_sliders_by_scope[scope] = {}
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
        region_labels = {
            "midtones": "中间调",
            "shadows": "阴影",
            "highlights": "高光",
        }

        def _wheel_unit(label: str, region: str, wheel_r: int = 52) -> QWidget:
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
            lum = ThinSlider(Qt.Orientation.Vertical, -100, 100, 0)
            lum.setFixedHeight(max(86, wheel_r * 2 + 2))
            lum.value_changed.connect(
                lambda value, current_region=region, current_scope=scope: self._emit_color_grading_luminance_change(
                    current_region,
                    value,
                    committed=False,
                    scope=current_scope,
                )
            )
            lum.value_committed.connect(
                lambda value, current_region=region, current_scope=scope: self._emit_color_grading_luminance_change(
                    current_region,
                    value,
                    committed=True,
                    scope=current_scope,
                )
            )

            whl = ColorWheelWidget(radius=wheel_r)
            whl.color_changed.connect(
                lambda hue, sat, current_region=region, current_scope=scope: self._emit_color_grading_wheel_change(
                    current_region,
                    hue,
                    sat,
                    committed=False,
                    scope=current_scope,
                )
            )
            whl.color_change_finished.connect(
                lambda hue, sat, current_region=region, current_scope=scope: self._emit_color_grading_wheel_change(
                    current_region,
                    hue,
                    sat,
                    committed=True,
                    scope=current_scope,
                )
            )
            self._color_grading_wheels[region] = whl
            self._color_grading_luminance_sliders[region] = lum
            self._color_grading_wheels_by_scope[scope][region] = whl
            self._color_grading_luminance_sliders_by_scope[scope][region] = lum

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
        mid_h.addWidget(_wheel_unit(region_labels["midtones"], "midtones", wheel_r=50))
        mid_h.addStretch()
        lo.addWidget(mid_outer)
        lo.addSpacing(8)

        # shadows + highlights (smaller, side by side)
        small_row = QWidget()
        small_row.setStyleSheet("background:transparent;")
        sm_lo = QHBoxLayout(small_row)
        sm_lo.setContentsMargins(0, 0, 0, 0)
        sm_lo.setSpacing(8)
        sm_lo.addWidget(_wheel_unit(region_labels["shadows"], "shadows", wheel_r=36))
        sm_lo.addWidget(_wheel_unit(region_labels["highlights"], "highlights", wheel_r=36))
        lo.addWidget(small_row)

    def _emit_color_grading_wheel_change(
        self,
        region: str,
        hue: float,
        saturation: float,
        *,
        committed: bool,
        scope: Optional[str] = None,
    ) -> None:
        if self._syncing_adjust_controls:
            return
        target_scope = scope or self._adjust_build_scope
        region_label = {
            "midtones": "中间调",
            "shadows": "阴影",
            "highlights": "高光",
        }.get(region, region)
        payload = {
            f"{region}_hue": float(hue) % 360.0,
            f"{region}_saturation": max(0.0, min(100.0, float(saturation))),
        }
        if target_scope == "mask":
            if committed:
                self.mask_adjust_section_change_finished.emit("color_grading", payload, f"颜色分级 · {region_label} · 色轮")
            else:
                self.mask_adjust_section_changed.emit("color_grading", payload)
        elif committed:
            self.adjust_section_change_finished.emit("color_grading", payload, f"颜色分级 · {region_label} · 色轮")
        else:
            self.adjust_section_changed.emit("color_grading", payload)

    def _emit_color_grading_luminance_change(self, region: str, value: int, *, committed: bool, scope: Optional[str] = None) -> None:
        if self._syncing_adjust_controls:
            return
        target_scope = scope or self._adjust_build_scope
        region_label = {
            "midtones": "中间调",
            "shadows": "阴影",
            "highlights": "高光",
        }.get(region, region)
        payload = {f"{region}_luminance": int(value)}
        if target_scope == "mask":
            if committed:
                self.mask_adjust_section_change_finished.emit("color_grading", payload, f"颜色分级 · {region_label} · 明度")
            else:
                self.mask_adjust_section_changed.emit("color_grading", payload)
        elif committed:
            self.adjust_section_change_finished.emit("color_grading", payload, f"颜色分级 · {region_label} · 明度")
        else:
            self.adjust_section_changed.emit("color_grading", payload)

    # ── 细节 section ──────────────────────────────────────────────────────────

    def _build_detail_content(self, lo: QVBoxLayout) -> None:
        """Detail section: sharpening amount + denoise."""
        self._add_gradient_slider_row(
            lo, "锐化", 0, "#1a1a1a", "#ffffff", 0, 100, 0,
            section="detail",
            param_path="sharpen_amount",
            display_label="细节 · 锐化",
        )
        self._add_gradient_slider_row(
            lo, "去杂色", 0, "#1a1a1a", "#ffffff", 0, 100, 0,
            section="detail",
            param_path="luminance_noise",
            display_label="细节 · 去杂色",
        )

    # ── 镜头 section ──────────────────────────────────────────────────────────

    def _build_lens_content(self, lo: QVBoxLayout) -> None:
        """Lens correction: distortion, vignette, chromatic aberration."""
        for label, param_path, lc, rc in [
            ("扭曲校正", "distortion", "#1a1a1a", "#ffffff"),
            ("暗角", "vignette", "#000000", "#ffffff"),
            ("暗角中点", "vignette_midpoint", "#1a1a1a", "#ffffff"),
            ("色差", "chromatic_aberration", "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(
                lo, label, 0, lc, rc, -100, 100, 0,
                section="lens",
                param_path=param_path,
                state_path=f"geometry.{param_path}",
                display_label=f"镜头 · {label}",
            )

    # ── 透视矫正 section ──────────────────────────────────────────────────────

    def _build_perspective_content(self, lo: QVBoxLayout) -> None:
        """Perspective transform sliders."""
        for label, param_path, lc, rc, to_model, to_slider in [
            ("水平", "horizontal", "#1a1a1a", "#ffffff", None, None),
            ("垂直", "vertical", "#1a1a1a", "#ffffff", None, None),
            ("旋转", "rotation", "#1a1a1a", "#ffffff", None, None),
            ("缩放", "scale", "#1a1a1a", "#ffffff", lambda value: 100 + value, lambda value: float(value) - 100.0),
        ]:
            self._add_gradient_slider_row(
                lo, label, 0, lc, rc, -100, 100, 0,
                section="perspective",
                param_path=param_path,
                state_path=f"geometry.{param_path}",
                display_label=f"透视矫正 · {label}",
                to_model=to_model,
                to_slider=to_slider,
            )

    # ── 颜色校准 section ──────────────────────────────────────────────────────

    def _build_color_calibration_content(self, lo: QVBoxLayout) -> None:
        """Color calibration: per-channel hue/saturation."""
        for ch, prefix, hue_lc, hue_rc in [
            ("红色原色", "red_primary", "#ff44aa", "#ff4444"),
            ("绿色原色", "green_primary", "#aacc00", "#00bbaa"),
            ("蓝色原色", "blue_primary", "#0088cc", "#6655ff"),
        ]:
            lo.addWidget(_lbl(ch, C_TEXT_3, 11))
            self._add_gradient_slider_row(
                lo, "色相", 0, hue_lc, hue_rc, -100, 100, 0,
                section="calibration",
                param_path=f"{prefix}_hue",
                display_label=f"颜色校准 · {ch} · 色相",
            )
            self._add_gradient_slider_row(
                lo, "饱和度", 0, "#1a1a1a", "#ffffff", -100, 100, 0,
                section="calibration",
                param_path=f"{prefix}_sat",
                display_label=f"颜色校准 · {ch} · 饱和度",
            )
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
    _PREVIEW_REFRESH_INTERVAL_MS = 24
    _HISTOGRAM_REFRESH_INTERVAL_MS = 160
    _FIXED_PREVIEW_MAX_DIMENSION = 1024
    _HISTOGRAM_RENDER_MAX_DIMENSION = 480
    _EXPORT_FILTER_JPEG = "JPEG (*.jpg *.jpeg)"
    _EXPORT_FILTER_PNG = "PNG (*.png)"
    _EXPORT_FILTER_WEBP = "WebP (*.webp)"
    _EXPORT_FILTER_TIFF = "TIFF (*.tiff *.tif)"
    _EXPORT_FILTER_BMP = "BMP (*.bmp)"
    _EXPORT_FILTERS = ";;".join((
        _EXPORT_FILTER_JPEG,
        _EXPORT_FILTER_PNG,
        _EXPORT_FILTER_WEBP,
        _EXPORT_FILTER_TIFF,
        _EXPORT_FILTER_BMP,
    ))
    _EXPORT_FILTER_TO_EXTENSION = {
        _EXPORT_FILTER_JPEG: ".jpg",
        _EXPORT_FILTER_PNG: ".png",
        _EXPORT_FILTER_WEBP: ".webp",
        _EXPORT_FILTER_TIFF: ".tiff",
        _EXPORT_FILTER_BMP: ".bmp",
    }
    _EXPORT_EXTENSION_TO_FORMAT = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
        ".tif": "TIFF",
        ".tiff": "TIFF",
        ".bmp": "BMP",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._agent_config = load_agent_config()
        self._current_tlimage: Optional[TLImage] = None
        self._active_mask_layer_id: Optional[str] = None
        self._last_ai_request_payload: Optional[dict[str, Any]] = None
        self._last_ai_response_payload: Optional[dict[str, Any]] = None
        self._agent_thread: Optional[QThread] = None
        self._agent_worker: Optional[AgentRunWorker] = None
        self._pending_ai_prompt = ""
        self._export_thread: Optional[QThread] = None
        self._export_worker: Optional[ExportWorker] = None
        self._export_progress_dialog: Optional[ExportProgressDialog] = None
        self._pending_export_error: Optional[str] = None
        self._preview_refresh_timer = QTimer(self)
        self._preview_refresh_timer.setSingleShot(True)
        self._preview_refresh_timer.timeout.connect(self._flush_preview_refresh)
        self._histogram_refresh_timer = QTimer(self)
        self._histogram_refresh_timer.setSingleShot(True)
        self._histogram_refresh_timer.timeout.connect(self._flush_histogram_refresh)
        self._histogram_result_timer = QTimer(self)
        self._histogram_result_timer.timeout.connect(self._poll_histogram_results)
        self._histogram_context = mp.get_context("spawn")
        self._histogram_request_queue = self._histogram_context.Queue()
        self._histogram_result_queue = self._histogram_context.Queue()
        self._histogram_process = self._histogram_context.Process(
            target=histogram_worker_main,
            args=(self._histogram_request_queue, self._histogram_result_queue),
            kwargs={
                "render_dimension": self._HISTOGRAM_RENDER_MAX_DIMENSION,
                "histogram_dimension": self._HISTOGRAM_RENDER_MAX_DIMENSION,
            },
            daemon=True,
        )
        self._histogram_process.start()
        self._histogram_result_timer.start(40)
        self._histogram_job_id = 0
        self._latest_histogram_job_id = 0
        self._original_preview_cache_key: Optional[tuple[str, int]] = None
        self._original_preview_pixmap: Optional[QPixmap] = None
        self.setStyleSheet(f"background:{C_BG_APP};")
        self._build_ui()
        self._connect_signals()
        self._ai_chatbox.set_model_badge(self._agent_config.display_name())
        self._setup_shortcuts()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_histogram_process)

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
        self._ai_chatbox = AIChatBox()
        self._status_bar = EditorStatusBar()

        center_lo.addWidget(self._opts_bar)
        center_lo.addWidget(self._canvas, 1)
        center_lo.addWidget(self._ai_chatbox)
        center_lo.addWidget(self._status_bar)
        content_lo.addWidget(center, 1)

        # right panel
        self._right_panel = RightPanel()
        content_lo.addWidget(self._right_panel)

    # ── signals ───────────────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        self._tool_sidebar.tool_changed.connect(self._opts_bar.set_tool)
        self._tool_sidebar.tool_changed.connect(self._canvas.set_tool)
        self._right_panel.tool_requested.connect(self._tool_sidebar.set_active_tool)

        self._canvas.zoom_changed.connect(self._on_zoom_changed)
        self._canvas.color_picked.connect(self._on_canvas_color_picked)
        self._canvas.crop_confirmed.connect(self._on_crop_confirmed)
        self._canvas.crop_cancelled.connect(self._on_crop_cancelled)
        self._canvas.mask_preview_changed.connect(self._on_mask_changed)
        self._canvas.mask_create_finished.connect(self._on_mask_created)
        self._canvas.mask_change_finished.connect(self._on_mask_change_finished)
        self._status_bar.zoom_in_requested.connect(self._zoom_in)
        self._status_bar.zoom_out_requested.connect(self._zoom_out)
        self._ai_chatbox.request_submitted.connect(self._on_ai_chat_requested)
        self._ai_chatbox.settings_requested.connect(self._open_ai_settings_dialog)

        self._opts_bar.grid_toggled.connect(self._canvas.set_grid)
        self._opts_bar.ruler_toggled.connect(self._canvas.set_ruler)
        self._right_panel.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        self._right_panel.layer_opacity_changed.connect(self._on_layer_opacity_changed)
        self._right_panel.layer_opacity_change_finished.connect(self._on_layer_opacity_change_finished)
        self._right_panel.active_layer_changed.connect(self._on_active_layer_changed)
        self._right_panel.adjust_section_changed.connect(self._on_adjust_section_changed)
        self._right_panel.adjust_section_change_finished.connect(self._on_adjust_section_change_finished)
        self._right_panel.mask_changed.connect(self._on_mask_changed)
        self._right_panel.mask_change_finished.connect(self._on_mask_change_finished)
        self._right_panel.mask_adjust_section_changed.connect(self._on_mask_adjust_section_changed)
        self._right_panel.mask_adjust_section_change_finished.connect(self._on_mask_adjust_section_change_finished)
        self._right_panel.mask_layer_selected.connect(self._on_mask_layer_selected)

    def open_image(self, path: str) -> bool:
        try:
            persisted = LibraryProjectIndex().load_edit_state_for_asset_path(path)
            tl_image = TLImage.from_dict(persisted) if persisted else TLImage.open(path)
            if str(Path(tl_image.image_path).expanduser().resolve()) != str(Path(path).expanduser().resolve()):
                tl_image.image_path = path
            preview_max_dimension = self._preview_max_dimension()
            edited_image = tl_image.render_image(preview=True, max_dimension=preview_max_dimension)
            edited_pixmap = self._pil_to_pixmap(edited_image)
        except Exception:
            return False

        self._current_tlimage = tl_image
        self._active_mask_layer_id = None
        self._original_preview_cache_key = None
        self._original_preview_pixmap = None
        original_pixmap = self._get_original_preview_pixmap(tl_image, preview_max_dimension)
        self._canvas.set_pixmaps(edited_pixmap, original_pixmap, reset_view=True)
        self._canvas.set_original_image_size(*tl_image.image_size())
        self._ai_chatbox.set_image_context(Path(path).name)
        self._sync_right_panel_from_tlimage()
        self._right_panel.set_histogram_data(None)
        self._request_histogram_refresh(immediate=True)
        self.title_changed.emit(f"TempusLoom - {Path(path).name}")
        self._status_bar.set_image_info(*tl_image.image_size())
        return True

    def _persist_current_library_edit_state(self) -> None:
        if self._current_tlimage is None:
            return
        LibraryProjectIndex().save_edit_state_for_asset_path(
            self._current_tlimage.image_path,
            self._current_tlimage.to_dict(),
        )

    def _preview_max_dimension(self) -> int:
        return self._FIXED_PREVIEW_MAX_DIMENSION

    def _pil_to_pixmap(self, image) -> QPixmap:
        return QPixmap.fromImage(ImageQt(image))

    def _get_original_preview_pixmap(self, tl_image: TLImage, preview_max_dimension: int) -> QPixmap:
        cache_key = (tl_image.image_path, preview_max_dimension)
        if self._original_preview_cache_key != cache_key or self._original_preview_pixmap is None:
            self._original_preview_pixmap = self._pil_to_pixmap(
                tl_image.load_image(preview=True, max_dimension=preview_max_dimension)
            )
            self._original_preview_cache_key = cache_key
        return self._original_preview_pixmap

    def _render_original_to_pixmap(self, tl_image: TLImage) -> QPixmap:
        return self._pil_to_pixmap(
            tl_image.load_image(preview=True, max_dimension=self._preview_max_dimension())
        )

    def _render_tlimage_to_pixmap(self, tl_image: TLImage, *, preview: bool = True) -> QPixmap:
        return self._pil_to_pixmap(
            tl_image.render_image(preview=preview, max_dimension=self._preview_max_dimension() if preview else None)
        )

    def _apply_preview_to_canvas(self, *, reset_view: bool = False) -> None:
        if self._current_tlimage is None:
            return
        preview_max_dimension = self._preview_max_dimension()
        edited_image = self._current_tlimage.render_image(preview=True, max_dimension=preview_max_dimension)
        edited_pixmap = self._pil_to_pixmap(edited_image)
        original_pixmap = self._get_original_preview_pixmap(self._current_tlimage, preview_max_dimension)
        self._canvas.set_pixmaps(edited_pixmap, original_pixmap, reset_view=reset_view)
        self._status_bar.set_image_info(*self._current_tlimage.image_size())
        self._right_panel.set_histogram_metadata(self._current_tlimage.metadata)

    def _schedule_preview_refresh(self, *, immediate: bool = False) -> None:
        if immediate:
            if self._preview_refresh_timer.isActive():
                self._preview_refresh_timer.stop()
            self._flush_preview_refresh()
            return
        if not self._preview_refresh_timer.isActive():
            self._preview_refresh_timer.start(self._PREVIEW_REFRESH_INTERVAL_MS)

    def _flush_preview_refresh(self) -> None:
        self._apply_preview_to_canvas(reset_view=False)

    def _request_histogram_refresh(self, *, immediate: bool = False) -> None:
        if self._current_tlimage is None:
            return
        if immediate:
            if self._histogram_refresh_timer.isActive():
                self._histogram_refresh_timer.stop()
            self._flush_histogram_refresh()
            return
        self._histogram_refresh_timer.start(self._HISTOGRAM_REFRESH_INTERVAL_MS)

    def _flush_histogram_refresh(self) -> None:
        if self._current_tlimage is None:
            return
        self._histogram_job_id += 1
        self._latest_histogram_job_id = self._histogram_job_id
        self._clear_histogram_request_queue()
        self._histogram_request_queue.put(
            {
                "job_id": self._histogram_job_id,
                "snapshot": self._current_tlimage.to_dict(),
            }
        )

    def _clear_histogram_request_queue(self) -> None:
        while True:
            try:
                self._histogram_request_queue.get_nowait()
            except Empty:
                break

    def _poll_histogram_results(self) -> None:
        while True:
            try:
                result = self._histogram_result_queue.get_nowait()
            except Empty:
                break
            if int(result.get("job_id", 0)) != self._latest_histogram_job_id:
                continue
            histogram = result.get("histogram")
            if histogram is not None:
                self._right_panel.set_histogram_data(histogram)
            metadata = result.get("metadata")
            if isinstance(metadata, dict):
                self._right_panel.set_histogram_metadata(metadata)

    def _shutdown_histogram_process(self) -> None:
        process = getattr(self, "_histogram_process", None)
        if process is None:
            return
        if getattr(self, "_histogram_refresh_timer", None) is not None:
            self._histogram_refresh_timer.stop()
        if getattr(self, "_histogram_result_timer", None) is not None:
            self._histogram_result_timer.stop()
        if process.is_alive():
            self._histogram_request_queue.put({"type": "stop"})
            process.join(timeout=0.5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.5)
        self._histogram_process = None

    def _refresh_canvas_from_tlimage(self, *, sync_panel: bool = False) -> None:
        if self._current_tlimage is None:
            return
        self._apply_preview_to_canvas(reset_view=False)
        self._request_histogram_refresh(immediate=True)
        if sync_panel:
            self._sync_right_panel_from_tlimage()

    def _mask_layers(self) -> list:
        if self._current_tlimage is None:
            return []
        return [
            layer for layer in self._current_tlimage.malayers
            if getattr(layer, "type_name", "") == "mask"
        ]

    def _sync_right_panel_from_tlimage(self) -> None:
        if self._current_tlimage is None:
            return
        self._right_panel.set_malayers(self._current_tlimage.malayers)
        self._right_panel.set_edit_state(self._current_tlimage.edit_state)
        mask_layers = self._mask_layers()
        mask_layer_ids = {getattr(layer, "id", None) for layer in mask_layers}
        if self._active_mask_layer_id not in mask_layer_ids:
            self._active_mask_layer_id = getattr(mask_layers[-1], "id", None) if mask_layers else None
        mask_layer = self._current_tlimage.get_primary_mask_layer()
        active_mask_layer = (
            self._current_tlimage.get_malayer(self._active_mask_layer_id)
            if self._active_mask_layer_id
            else mask_layer
        )
        if active_mask_layer is not None and getattr(active_mask_layer, "type_name", "") == "mask":
            layer_mask = getattr(active_mask_layer, "mask", None)
            mask_state = layer_mask.to_dict() if layer_mask else {}
            mask_adjust_state = active_mask_layer.to_dict().get("payload", {})
        else:
            mask_state = self._current_tlimage.edit_state.get("mask", {})
            mask_adjust_state = {}
        self._right_panel.set_mask_state(mask_state if isinstance(mask_state, dict) else {})
        self._right_panel.set_mask_adjust_state(mask_adjust_state if isinstance(mask_adjust_state, dict) else {})
        self._right_panel.set_mask_layers(mask_layers, self._active_mask_layer_id)
        self._canvas.set_mask_overlay(mask_state if isinstance(mask_state, dict) else {})
        self._canvas.set_mask_overlay_visible(True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._right_panel.set_histogram_metadata(self._current_tlimage.metadata)

    def _setup_shortcuts(self) -> None:
        from PyQt6.QtGui import QShortcut
        QShortcut(QKeySequence.StandardKey.Undo, self, self._undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, self._redo)
        QShortcut(QKeySequence.StandardKey.Open, self, self._open_image)
        QShortcut(QKeySequence.StandardKey.Save, self, self._save_image)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, self._export_image)
        tool_shortcuts = {
            "V": "mouse-pointer",
            "C": "crop",
            "P": "pen-tool",
            "B": "paintbrush",
            "E": "eraser",
            "T": "type",
            "I": "pipette",
            "S": "stamp",
        }
        for key, tool_name in tool_shortcuts.items():
            QShortcut(
                QKeySequence(key),
                self,
                lambda tool_name=tool_name: self._tool_sidebar.set_active_tool(tool_name),
            )

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
        self._persist_current_library_edit_state()

    def _default_export_path(self) -> Path:
        if self._current_tlimage is None:
            return Path.home() / "Desktop" / "export.jpg"
        source_path = Path(self._current_tlimage.image_path)
        default_dir = source_path.parent if source_path.parent.exists() else (Path.home() / "Desktop")
        return default_dir / f"{source_path.stem}.jpg"

    def _normalize_export_target(self, path: str, selected_filter: str) -> tuple[str, str]:
        target = Path(path).expanduser()
        selected_extension = self._EXPORT_FILTER_TO_EXTENSION.get(selected_filter, ".jpg")
        suffix = target.suffix.lower()

        if suffix not in self._EXPORT_EXTENSION_TO_FORMAT:
            target = target.with_suffix(selected_extension)
            suffix = selected_extension

        export_format = self._EXPORT_EXTENSION_TO_FORMAT.get(suffix, "JPEG")
        return str(target), export_format

    def _sync_export_dialog_filename(self, dialog: QFileDialog, selected_filter: str) -> None:
        selected_files = dialog.selectedFiles()
        current_path = Path(selected_files[0]).expanduser() if selected_files else self._default_export_path()
        selected_extension = self._EXPORT_FILTER_TO_EXTENSION.get(selected_filter, ".jpg")
        dialog.selectFile(str(current_path.with_suffix(selected_extension)))

    def _start_export(self, export_path: str, export_format: str) -> None:
        if self._current_tlimage is None or self._export_thread is not None:
            return

        snapshot = self._current_tlimage.to_dict()
        self._pending_export_error = None
        self._export_progress_dialog = ExportProgressDialog(self.window())
        self._export_progress_dialog.update_progress(0, "准备导出…")
        self._export_progress_dialog.show()

        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)

        self._export_thread = QThread(self)
        self._export_worker = ExportWorker(snapshot, export_path, export_format)
        self._export_worker.moveToThread(self._export_thread)
        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.progress_changed.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.finished.connect(self._export_thread.quit)
        self._export_worker.failed.connect(self._export_thread.quit)
        self._export_worker.finished.connect(self._export_worker.deleteLater)
        self._export_worker.failed.connect(self._export_worker.deleteLater)
        self._export_thread.finished.connect(self._cleanup_export)
        self._export_thread.finished.connect(self._export_thread.deleteLater)
        self._export_thread.start()

    def _on_export_progress(self, value: int, message: str) -> None:
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.update_progress(value, message)

    def _on_export_finished(self, export_path: str) -> None:
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.update_progress(100, "导出完成")
        if self._current_tlimage is not None:
            LibraryProjectIndex().add_tag_for_asset_path(self._current_tlimage.image_path, "导出")

    def _on_export_failed(self, error_message: str) -> None:
        self._pending_export_error = error_message
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.update_progress(100, "导出失败")

    def _cleanup_export(self) -> None:
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.close()
            self._export_progress_dialog.deleteLater()
            self._export_progress_dialog = None
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self._export_worker = None
        self._export_thread = None
        if self._pending_export_error:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Failed", f"Unable to export image:\n\n{self._pending_export_error}")
            self._pending_export_error = None

    def _export_image(self) -> None:
        if self._current_tlimage is None or self._export_thread is not None:
            return
        default_path = self._default_export_path()
        dialog = QFileDialog(self, "Export Image", str(default_path.parent))
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilters([
            self._EXPORT_FILTER_JPEG,
            self._EXPORT_FILTER_PNG,
            self._EXPORT_FILTER_WEBP,
            self._EXPORT_FILTER_TIFF,
            self._EXPORT_FILTER_BMP,
        ])
        dialog.selectNameFilter(self._EXPORT_FILTER_JPEG)
        dialog.selectFile(default_path.name)
        dialog.filterSelected.connect(lambda name_filter: self._sync_export_dialog_filename(dialog, name_filter))

        if not dialog.exec():
            return

        selected_files = dialog.selectedFiles()
        if not selected_files:
            return

        export_path, export_format = self._normalize_export_target(
            selected_files[0],
            dialog.selectedNameFilter(),
        )
        self._start_export(export_path, export_format)

    def _undo(self) -> None:
        if self._current_tlimage is None:
            return
        if self._current_tlimage.undo():
            self._refresh_canvas_from_tlimage(sync_panel=True)
            self._persist_current_library_edit_state()

    def _redo(self) -> None:
        if self._current_tlimage is None:
            return
        if self._current_tlimage.redo():
            self._refresh_canvas_from_tlimage(sync_panel=True)
            self._persist_current_library_edit_state()

    def _on_layer_visibility_changed(self, idx: int, visible: bool) -> None:
        if self._current_tlimage is None or idx >= len(self._current_tlimage.malayers):
            return
        layer_name = self._current_tlimage.malayers[idx].name
        self._current_tlimage.update_layer_state(
            idx,
            visible=visible,
            record_history=True,
            description=f"图层 · {layer_name} · {'显示' if visible else '隐藏'}",
        )
        self._schedule_preview_refresh(immediate=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._persist_current_library_edit_state()

    def _on_layer_opacity_changed(self, idx: int, opacity: float) -> None:
        if self._current_tlimage is None or idx >= len(self._current_tlimage.malayers):
            return
        self._current_tlimage.update_layer_state(idx, opacity=opacity)
        self._schedule_preview_refresh()
        self._request_histogram_refresh()

    def _on_layer_opacity_change_finished(self, idx: int, opacity: float) -> None:
        if self._current_tlimage is None or idx >= len(self._current_tlimage.malayers):
            return
        layer_name = self._current_tlimage.malayers[idx].name
        self._current_tlimage.update_layer_state(
            idx,
            opacity=opacity,
            record_history=True,
            description=f"图层 · {layer_name} · 透明度 {int(round(opacity * 100))}%",
        )
        self._schedule_preview_refresh(immediate=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._persist_current_library_edit_state()

    def _on_active_layer_changed(self, idx: int) -> None:
        if self._current_tlimage is None or idx < 0 or idx >= len(self._current_tlimage.malayers):
            return
        layer = self._current_tlimage.malayers[idx]
        if getattr(layer, "type_name", "") != "mask":
            return
        self._active_mask_layer_id = layer.id
        mask = getattr(layer, "mask", None)
        mask_state = mask.to_dict() if mask else {}
        mask_adjust_state = layer.to_dict().get("payload", {})
        self._right_panel.set_mask_state(mask_state)
        self._right_panel.set_mask_adjust_state(mask_adjust_state if isinstance(mask_adjust_state, dict) else {})
        self._right_panel.set_mask_layers(self._mask_layers(), self._active_mask_layer_id)
        self._canvas.set_mask_overlay(mask_state)
        self._canvas.set_mask_overlay_visible(True)

    def _on_mask_layer_selected(self, layer_id: str) -> None:
        if self._current_tlimage is None:
            return
        layer = self._current_tlimage.get_malayer(layer_id)
        if layer is None or getattr(layer, "type_name", "") != "mask":
            return
        self._active_mask_layer_id = layer.id
        mask = getattr(layer, "mask", None)
        mask_state = mask.to_dict() if mask else {}
        mask_adjust_state = layer.to_dict().get("payload", {})
        self._right_panel.set_mask_layers(self._mask_layers(), self._active_mask_layer_id)
        self._right_panel.set_mask_state(mask_state)
        self._right_panel.set_mask_adjust_state(mask_adjust_state if isinstance(mask_adjust_state, dict) else {})
        self._canvas.set_mask_overlay(mask_state)
        self._canvas.set_mask_overlay_visible(True)

    def _on_adjust_section_changed(self, section: str, values: dict) -> None:
        if self._current_tlimage is None:
            return
        self._current_tlimage.preview_adjustment(section, values)
        self._schedule_preview_refresh()
        self._request_histogram_refresh()

    def _on_adjust_section_change_finished(self, section: str, values: dict, description: str) -> None:
        if self._current_tlimage is None:
            return
        self._current_tlimage.update_adjustment(section, values, record_history=True, description=description)
        self._schedule_preview_refresh(immediate=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._persist_current_library_edit_state()

    def _on_mask_created(self, values: dict, description: str) -> None:
        if self._current_tlimage is None or not values:
            return
        layer = self._current_tlimage.add_mask_layer(
            values,
            record_history=True,
            description=f"{description} · 新建",
        )
        self._active_mask_layer_id = layer.id
        mask_state = layer.mask.to_dict() if layer.mask else {}
        self._right_panel.set_malayers(self._current_tlimage.malayers)
        self._right_panel.set_mask_layers(self._mask_layers(), self._active_mask_layer_id)
        self._right_panel.set_mask_state(mask_state)
        self._right_panel.set_mask_adjust_state(layer.to_dict().get("payload", {}))
        self._canvas.set_mask_overlay(mask_state)
        self._canvas.set_mask_overlay_visible(True)
        self._schedule_preview_refresh(immediate=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._persist_current_library_edit_state()

    def _on_mask_changed(self, values: dict) -> None:
        if self._current_tlimage is None:
            return
        mask_values = values if values else None
        before_count = len(self._current_tlimage.malayers)
        if mask_values is None and self._active_mask_layer_id is None:
            self._current_tlimage.preview_mask(None)
            mask_state = {}
        else:
            layer = self._current_tlimage.preview_mask_layer(
                self._active_mask_layer_id,
                mask_values,
                create_if_missing=mask_values is not None,
            )
            if layer is not None:
                self._active_mask_layer_id = layer.id
                mask_state = layer.mask.to_dict() if layer.mask else {}
                self._right_panel.set_mask_adjust_state(layer.to_dict().get("payload", {}))
            else:
                mask_state = {}
        self._right_panel.set_mask_state(mask_state)
        self._canvas.set_mask_overlay(mask_state)
        self._canvas.set_mask_overlay_visible(True)
        if len(self._current_tlimage.malayers) != before_count:
            self._right_panel.set_malayers(self._current_tlimage.malayers)
        self._right_panel.set_mask_layers(self._mask_layers(), self._active_mask_layer_id)
        self._schedule_preview_refresh()
        self._request_histogram_refresh()

    def _on_mask_change_finished(self, values: dict, description: str) -> None:
        if self._current_tlimage is None:
            return
        mask_values = values if values else None
        before_count = len(self._current_tlimage.malayers)
        if mask_values is None and self._active_mask_layer_id is None:
            self._current_tlimage.update_mask(None, record_history=True, description=description)
            mask_state = {}
        else:
            layer = self._current_tlimage.update_mask_layer(
                self._active_mask_layer_id,
                mask_values,
                create_if_missing=mask_values is not None,
                record_history=True,
                description=description,
            )
            if layer is not None:
                self._active_mask_layer_id = layer.id
                mask_state = layer.mask.to_dict() if layer.mask else {}
                self._right_panel.set_mask_adjust_state(layer.to_dict().get("payload", {}))
            else:
                mask_state = {}
        self._right_panel.set_mask_state(mask_state if isinstance(mask_state, dict) else {})
        self._canvas.set_mask_overlay(mask_state if isinstance(mask_state, dict) else {})
        self._canvas.set_mask_overlay_visible(True)
        if len(self._current_tlimage.malayers) != before_count:
            self._right_panel.set_malayers(self._current_tlimage.malayers)
        self._right_panel.set_mask_layers(self._mask_layers(), self._active_mask_layer_id)
        self._schedule_preview_refresh(immediate=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._persist_current_library_edit_state()

    def _active_mask_layer(self) -> Optional[Any]:
        if self._current_tlimage is None:
            return None
        layer = self._current_tlimage.get_malayer(self._active_mask_layer_id) if self._active_mask_layer_id else None
        if layer is not None and getattr(layer, "type_name", "") == "mask":
            return layer
        mask_layers = self._mask_layers()
        layer = mask_layers[-1] if mask_layers else None
        if layer is not None:
            self._active_mask_layer_id = layer.id
        return layer

    def _on_mask_adjust_section_changed(self, section: str, values: dict) -> None:
        if self._current_tlimage is None:
            return
        layer = self._active_mask_layer()
        if layer is None:
            return
        self._canvas.set_mask_overlay_visible(False)
        self._current_tlimage.preview_mask_layer_adjustment(
            layer.id,
            section,
            values,
        )
        self._schedule_preview_refresh()

    def _on_mask_adjust_section_change_finished(self, section: str, values: dict, description: str) -> None:
        if self._current_tlimage is None:
            return
        layer = self._active_mask_layer()
        if layer is None:
            return
        self._canvas.set_mask_overlay_visible(False)
        mask = getattr(layer, "mask", None)
        mask_state = mask.to_dict() if mask else None
        self._current_tlimage.update_mask_layer(
            layer.id,
            mask_state,
            adjustment={section: values},
            create_if_missing=False,
            record_history=True,
            description=f"蒙版调色 · {description}",
        )
        self._right_panel.set_mask_adjust_state(layer.to_dict().get("payload", {}))
        self._schedule_preview_refresh(immediate=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._persist_current_library_edit_state()

    def _on_canvas_color_picked(self, color: QColor) -> None:
        if self._current_tlimage is None:
            return
        self._right_panel.apply_color_editor_sample(color, committed=True)
        self._tool_sidebar.set_active_tool("mouse-pointer")

    def _on_crop_confirmed(self, left_r: float, top_r: float, right_r: float, bottom_r: float) -> None:
        if self._current_tlimage is None:
            return
        self._current_tlimage.update_adjustment(
            "geometry",
            {"crop_left": left_r, "crop_top": top_r, "crop_right": right_r, "crop_bottom": bottom_r},
            record_history=True,
            description="裁剪",
        )
        self._apply_preview_to_canvas(reset_view=True)
        self._request_histogram_refresh(immediate=True)
        self._right_panel.set_history_entries(self._current_tlimage.history_entries())
        self._tool_sidebar.set_active_tool("mouse-pointer")
        self._persist_current_library_edit_state()

    def _on_crop_cancelled(self) -> None:
        self._tool_sidebar.set_active_tool("mouse-pointer")

    def _open_ai_settings_dialog(self) -> None:
        dialog = AIAgentSettingsDialog(self._agent_config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._agent_config = dialog.selected_config(self._agent_config)
        save_agent_config(self._agent_config)
        self._ai_chatbox.set_model_badge(self._agent_config.display_name())
        self._ai_chatbox.add_assistant_message(
            f"已保存模型配置：{self._agent_config.display_name()}"
        )

    def _on_ai_chat_requested(self, prompt: str) -> None:
        if not prompt.strip():
            return
        if self._current_tlimage is None:
            self._ai_chatbox.add_assistant_message(
                "请先打开一张图片，再描述你想要的风格。我会把压缩后的预览图和风格提示一起整理成请求。"
            )
            return
        if not self._agent_config.is_configured():
            self._ai_chatbox.add_assistant_message(
                "请先点击“设置”，填写 Base URL、API Key 和模型名称，然后再发起调色请求。"
            )
            self._open_ai_settings_dialog()
            return
        if self._agent_thread is not None:
            self._ai_chatbox.add_assistant_message("上一个请求还在处理中，请稍候。")
            return

        try:
            request_payload = self._build_ai_request_payload(prompt)
            self._last_ai_request_payload = request_payload
        except Exception as exc:
            self._ai_chatbox.add_assistant_message(f"生成调色 JSON 失败：{exc}")
            return

        self._pending_ai_prompt = prompt.strip()
        self._ai_chatbox.set_busy(True)
        self._agent_thread = QThread(self)
        self._agent_worker = AgentRunWorker(self._agent_config, request_payload)
        self._agent_worker.moveToThread(self._agent_thread)
        self._agent_thread.started.connect(self._agent_worker.run)
        self._agent_thread.finished.connect(self._agent_worker.deleteLater)
        self._agent_worker.finished.connect(self._on_ai_agent_finished)
        self._agent_worker.failed.connect(self._on_ai_agent_failed)
        self._agent_worker.finished.connect(self._cleanup_ai_agent_thread)
        self._agent_worker.failed.connect(self._cleanup_ai_agent_thread)
        self._agent_thread.start()

        image_meta = request_payload["image"]
        self._ai_chatbox.add_assistant_message(
            f"请求已发送：{image_meta['width']} × {image_meta['height']} 预览图，约 {image_meta['byte_size'] // 1024} KB。"
        )

    def _on_ai_agent_finished(self, result: object) -> None:
        self._ai_chatbox.set_busy(False)
        if not hasattr(result, "payload"):
            self._ai_chatbox.add_assistant_message("AI 返回结果格式异常。")
            return
        response_payload = result.payload
        self._last_ai_response_payload = response_payload
        self._ai_chatbox.set_latest_response_json(response_payload)

        applied = False
        apply_error = ""
        if self._current_tlimage is not None:
            try:
                self._current_tlimage.apply_agent_json_payload(
                    response_payload,
                    record_history=True,
                    description=f"AI 调色 · {self._pending_ai_prompt[:24]}",
                )
                self._refresh_canvas_from_tlimage(sync_panel=True)
                self._persist_current_library_edit_state()
                applied = True
            except Exception as exc:
                apply_error = str(exc)

        summary = f"{self._agent_config.display_name()} 已返回调色 JSON"
        if applied:
            summary += "，并已自动应用到当前图片。"
        elif apply_error:
            summary += f"，但应用失败：{apply_error}"
        self._ai_chatbox.add_assistant_message(
            summary,
            json.dumps(response_payload, ensure_ascii=False, indent=2),
        )

    def _on_ai_agent_failed(self, error: str) -> None:
        self._ai_chatbox.set_busy(False)
        self._ai_chatbox.add_assistant_message(f"调用模型失败：{error}")

    def _cleanup_ai_agent_thread(self, *_args) -> None:
        if self._agent_thread is not None:
            self._agent_thread.quit()
            self._agent_thread.wait(1000)
            self._agent_thread.deleteLater()
        self._agent_thread = None
        self._agent_worker = None

    def _build_ai_request_payload(self, prompt: str) -> dict[str, Any]:
        if self._current_tlimage is None:
            raise RuntimeError("No TLImage loaded")
        compressed = self._compress_current_preview_for_ai(self._current_tlimage)
        return {
            "image": compressed,
            "style_prompt": prompt,
            "current_adjust": self._current_tlimage.to_json_dict(),
            "image_name": Path(self._current_tlimage.image_path).name,
        }

    def _compress_current_preview_for_ai(self, tl_image: TLImage) -> dict[str, Any]:
        preview_image = tl_image.render_image(preview=True, max_dimension=self._preview_max_dimension())
        if preview_image.mode != "RGB":
            preview_image = preview_image.convert("RGB")

        buf = io.BytesIO()
        preview_image.save(buf, format="JPEG", quality=78, optimize=True)
        binary = buf.getvalue()
        return {
            "mime_type": "image/jpeg",
            "width": preview_image.width,
            "height": preview_image.height,
            "byte_size": len(binary),
            "base64": base64.b64encode(binary).decode("ascii"),
        }

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._export_thread is not None:
            event.ignore()
            return
        if self._agent_thread is not None:
            event.ignore()
            return
        self._shutdown_histogram_process()
        super().closeEvent(event)

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
