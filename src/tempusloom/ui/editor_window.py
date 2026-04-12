# -*- coding: utf-8 -*-
"""
TempusLoom – 主编辑界面
Main editor window matching the pencil.pen design (1440 × 900).
"""

from __future__ import annotations

import os
import math
import multiprocessing as mp
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
)

from .editor_icons import icon_pixmap
from PIL.ImageQt import ImageQt
from tempusloom.core import TLImage
from tempusloom.core.histogram_process import histogram_worker_main


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
    color_picked = pyqtSignal(QColor)

    _MIN_ZOOM = 5
    _MAX_ZOOM = 800

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
        self.setAcceptDrops(True)

    def set_tool(self, tool_name: str) -> None:
        self._active_tool = tool_name
        self._refresh_cursor()

    def _refresh_cursor(self) -> None:
        if self._panning:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self._active_tool == "pipette" and self._display_pixmap() is not None:
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        self.setCursor(Qt.CursorShape.ArrowCursor)

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
        p.end()

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
        if event.button() == Qt.MouseButton.LeftButton and self._active_tool == "pipette":
            color = self._sample_color(event.position())
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
        if self._panning:
            delta = event.position() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None: # noqa: N802
        if self._panning:
            self._panning = False
            self._refresh_cursor()

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
        self._curve_editor_meta: dict[CurveEditor, dict[str, str]] = {}
        self._syncing_adjust_controls = False
        self._color_editor_wheel: Optional[ColorEditorWheelWidget] = None
        self._color_grading_wheels: dict[str, ColorWheelWidget] = {}
        self._color_grading_luminance_sliders: dict[str, ThinSlider] = {}
        self._color_editor_preview: Optional[ColorEditorPreviewStrip] = None
        self._color_editor_input_hsl_label: Optional[QLabel] = None
        self._color_editor_output_hsl_label: Optional[QLabel] = None
        self._color_editor_lightness_slider: Optional[ThinSlider] = None
        self._color_editor_lightness_label: Optional[QLabel] = None
        self._histogram_canvas: Optional[_HistogramCanvas] = None
        self._histogram_meta_labels: list[QLabel] = []
        self._histogram_format_badge: Optional[QLabel] = None
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

    def _on_opacity_change_finished(self) -> None:
        self.layer_opacity_change_finished.emit(self._active_layer, self._opacity_slider.value() / 100.0)

    def _on_layer_selected(self, idx: int) -> None:
        for i, row in enumerate(self._layer_rows):
            row.set_active(i == idx)
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
        self._opacity_lbl.setText(f"{self._opacity_slider.value()}%")

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
        self._syncing_adjust_controls = True
        try:
            for slider, meta in self._adjust_slider_meta.items():
                raw_value = self._read_nested_value(adjust_state, meta["state_path"])
                if raw_value is None:
                    continue
                slider_value = meta["to_slider"](raw_value)
                slider.setValue(int(round(slider_value)), emit_signal=False)
                self._adjust_value_labels[slider].setText(str(int(round(slider.value()))))
            for editor, meta in self._curve_editor_meta.items():
                raw_value = self._read_nested_value(adjust_state, meta["state_path"])
                editor.set_points(raw_value if raw_value is not None else [{"x": 0, "y": 0}, {"x": 255, "y": 255}])
            color_editor_state = adjust_state.get("color_editor", {}) if isinstance(adjust_state, dict) else {}
            if self._color_editor_wheel is not None and isinstance(color_editor_state, dict):
                self._color_editor_wheel.set_hs(
                    float(color_editor_state.get("hue", 0)),
                    float(color_editor_state.get("saturation", 0)),
                    emit_signal=False,
                )
            color_grading_state = adjust_state.get("color_grading", {}) if isinstance(adjust_state, dict) else {}
            if isinstance(color_grading_state, dict):
                for region, wheel in self._color_grading_wheels.items():
                    wheel.set_hs(
                        float(color_grading_state.get(f"{region}_hue", 0)),
                        float(color_grading_state.get(f"{region}_saturation", 0)),
                        emit_signal=False,
                    )
                for region, slider in self._color_grading_luminance_sliders.items():
                    slider.setValue(
                        int(round(float(color_grading_state.get(f"{region}_luminance", 0)))),
                        emit_signal=False,
                    )
        finally:
            self._syncing_adjust_controls = False
        self._refresh_color_editor_labels()

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
        display_label: str,
        to_model: Optional[Callable[[int], Any]] = None,
        to_slider: Optional[Callable[[Any], float]] = None,
    ) -> None:
        self._adjust_slider_meta[slider] = {
            "section": section,
            "param_path": param_path,
            "state_path": f"{section}.{param_path}",
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
        if committed:
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
        if committed:
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

    def _color_editor_state_value(self, key: str, default: int = 0) -> int:
        for slider, meta in self._adjust_slider_meta.items():
            if meta.get("section") == "color_editor" and meta.get("param_path") == key:
                try:
                    return int(round(slider.value()))
                except Exception:
                    return default
        return default

    def _refresh_color_editor_labels(self) -> None:
        if self._color_editor_wheel is None:
            return
        hue = self._color_editor_wheel.hue()
        saturation = int(round(self._color_editor_wheel.saturation()))
        lightness = self._color_editor_state_value("lightness")
        hue_shift = self._color_editor_state_value("hue_shift")
        saturation_shift = self._color_editor_state_value("saturation_shift")
        luminance_shift = self._color_editor_state_value("luminance_shift")

        output_hue = (hue + hue_shift) % 360
        output_saturation = max(0, min(100, saturation + saturation_shift))
        output_lightness = max(-100, min(100, lightness + luminance_shift))

        if self._color_editor_input_hsl_label is not None:
            self._color_editor_input_hsl_label.setText(
                self._format_color_editor_hsl(hue, saturation, lightness)
            )
        if self._color_editor_output_hsl_label is not None:
            self._color_editor_output_hsl_label.setText(
                self._format_color_editor_hsl(output_hue, output_saturation, output_lightness)
            )

        if self._color_editor_preview is not None:
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
            self._color_editor_preview.set_colors(input_color, output_color)

    def _emit_color_editor_wheel_change(self, hue: float, saturation: float, *, committed: bool) -> None:
        self._refresh_color_editor_labels()
        payload = {
            "hue": int(round(hue)) % 360,
            "saturation": int(round(saturation)),
        }
        if self._syncing_adjust_controls:
            return
        if committed:
            self.adjust_section_change_finished.emit("color_editor", payload, "色彩编辑器 · 取样颜色")
        else:
            self.adjust_section_changed.emit("color_editor", payload)

    def apply_color_editor_sample(self, color: QColor, *, committed: bool = True) -> None:
        hue, saturation, lightness, _alpha = color.getHsl()
        hue_value = 0 if hue < 0 else int(hue)
        saturation_value = int(round((saturation / 255.0) * 100.0))
        lightness_value = int(round((lightness / 255.0) * 200.0 - 100.0))

        self._syncing_adjust_controls = True
        try:
            if self._color_editor_wheel is not None:
                self._color_editor_wheel.set_hs(hue_value, saturation_value, emit_signal=False)
            if self._color_editor_lightness_slider is not None:
                self._color_editor_lightness_slider.setValue(lightness_value, emit_signal=False)
            if self._color_editor_lightness_label is not None:
                self._color_editor_lightness_label.setText(str(lightness_value))
        finally:
            self._syncing_adjust_controls = False

        self._refresh_color_editor_labels()
        payload = {
            "hue": hue_value,
            "saturation": saturation_value,
            "lightness": lightness_value,
        }
        if committed:
            self.adjust_section_change_finished.emit("color_editor", payload, "色彩编辑器 · 取样颜色")
        else:
            self.adjust_section_changed.emit("color_editor", payload)

    def _build_color_editor_content(self, lo: QVBoxLayout) -> None:
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
        self._color_editor_wheel.color_changed.connect(
            lambda hue, sat: self._emit_color_editor_wheel_change(hue, sat, committed=False)
        )
        self._color_editor_wheel.color_change_finished.connect(
            lambda hue, sat: self._emit_color_editor_wheel_change(hue, sat, committed=True)
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
        lightness_slider.value_changed.connect(lambda _v: self._refresh_color_editor_labels())
        lightness_lo.addWidget(lightness_slider, 0, Qt.AlignmentFlag.AlignHCenter)
        lightness_lo.addWidget(lightness_label, 0, Qt.AlignmentFlag.AlignHCenter)
        lightness_lo.addStretch()
        wheel_lo.addWidget(lightness_col, 0, Qt.AlignmentFlag.AlignVCenter)
        self._color_editor_lightness_slider = lightness_slider
        self._color_editor_lightness_label = lightness_label

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
        lo.addWidget(self._color_editor_preview)

        hsl_row = QWidget()
        hsl_lo = QHBoxLayout(hsl_row)
        hsl_lo.setContentsMargins(0, 0, 0, 0)
        hsl_lo.setSpacing(0)
        self._color_editor_input_hsl_label = _lbl("H:---  S:--  L:---", C_TEXT_4, 11)
        self._color_editor_output_hsl_label = _lbl("H:---  S:--  L:---", C_TEXT_4, 11)
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
            on_change=lambda _v: self._refresh_color_editor_labels(),
        )
        self._add_thin_slider_row(
            lo,
            "饱和度偏移",
            0,
            section="color_editor",
            param_path="saturation_shift",
            display_label="色彩编辑器 · 饱和度偏移",
            on_change=lambda _v: self._refresh_color_editor_labels(),
        )
        self._add_thin_slider_row(
            lo,
            "明亮度偏移",
            0,
            section="color_editor",
            param_path="luminance_shift",
            display_label="色彩编辑器 · 明亮度偏移",
            on_change=lambda _v: self._refresh_color_editor_labels(),
        )
        self._refresh_color_editor_labels()

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
            self._curve_editor_meta[ed] = {
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
                lambda value, current_region=region: self._emit_color_grading_luminance_change(
                    current_region,
                    value,
                    committed=False,
                )
            )
            lum.value_committed.connect(
                lambda value, current_region=region: self._emit_color_grading_luminance_change(
                    current_region,
                    value,
                    committed=True,
                )
            )

            whl = ColorWheelWidget(radius=wheel_r)
            whl.color_changed.connect(
                lambda hue, sat, current_region=region: self._emit_color_grading_wheel_change(
                    current_region,
                    hue,
                    sat,
                    committed=False,
                )
            )
            whl.color_change_finished.connect(
                lambda hue, sat, current_region=region: self._emit_color_grading_wheel_change(
                    current_region,
                    hue,
                    sat,
                    committed=True,
                )
            )
            self._color_grading_wheels[region] = whl
            self._color_grading_luminance_sliders[region] = lum

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
    ) -> None:
        if self._syncing_adjust_controls:
            return
        region_label = {
            "midtones": "中间调",
            "shadows": "阴影",
            "highlights": "高光",
        }.get(region, region)
        payload = {
            f"{region}_hue": float(hue) % 360.0,
            f"{region}_saturation": max(0.0, min(100.0, float(saturation))),
        }
        if committed:
            self.adjust_section_change_finished.emit("color_grading", payload, f"颜色分级 · {region_label} · 色轮")
        else:
            self.adjust_section_changed.emit("color_grading", payload)

    def _emit_color_grading_luminance_change(self, region: str, value: int, *, committed: bool) -> None:
        if self._syncing_adjust_controls:
            return
        region_label = {
            "midtones": "中间调",
            "shadows": "阴影",
            "highlights": "高光",
        }.get(region, region)
        payload = {f"{region}_luminance": int(value)}
        if committed:
            self.adjust_section_change_finished.emit("color_grading", payload, f"颜色分级 · {region_label} · 明度")
        else:
            self.adjust_section_changed.emit("color_grading", payload)

    # ── 细节 section ──────────────────────────────────────────────────────────

    def _build_detail_content(self, lo: QVBoxLayout) -> None:
        """Detail section: sharpening + noise reduction."""
        lo.addWidget(_lbl("锐化", C_TEXT_3, 11))
        for label, param_path, lc, rc in [
            ("数量", "sharpen_amount", "#1a1a1a", "#ffffff"),
            ("半径", "sharpen_radius", "#1a1a1a", "#ffffff"),
            ("细节", "sharpen_threshold", "#1a1a1a", "#ffffff"),
            ("蒙版", "mask", "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(
                lo, label, 0, lc, rc, 0, 100, 0,
                section="detail",
                param_path=param_path,
                display_label=f"细节 · {label}",
            )
        lo.addSpacing(4)
        lo.addWidget(_lbl("降噪", C_TEXT_3, 11))
        for label, param_path, lc, rc in [
            ("明亮度", "luminance_noise", "#1a1a1a", "#ffffff"),
            ("明亮度细节", "luminance_detail", "#1a1a1a", "#ffffff"),
            ("颜色", "color_noise", "#1a1a1a", "#ffffff"),
        ]:
            self._add_gradient_slider_row(
                lo, label, 0, lc, rc, 0, 100, 0,
                section="detail",
                param_path=param_path,
                display_label=f"降噪 · {label}",
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
        self._current_tlimage: Optional[TLImage] = None
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
        self._tool_sidebar.tool_changed.connect(self._canvas.set_tool)
        self._right_panel.tool_requested.connect(self._tool_sidebar.set_active_tool)

        self._canvas.zoom_changed.connect(self._on_zoom_changed)
        self._canvas.color_picked.connect(self._on_canvas_color_picked)
        self._status_bar.zoom_in_requested.connect(self._zoom_in)
        self._status_bar.zoom_out_requested.connect(self._zoom_out)

        self._opts_bar.grid_toggled.connect(self._canvas.set_grid)
        self._opts_bar.ruler_toggled.connect(self._canvas.set_ruler)
        self._right_panel.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        self._right_panel.layer_opacity_changed.connect(self._on_layer_opacity_changed)
        self._right_panel.layer_opacity_change_finished.connect(self._on_layer_opacity_change_finished)
        self._right_panel.adjust_section_changed.connect(self._on_adjust_section_changed)
        self._right_panel.adjust_section_change_finished.connect(self._on_adjust_section_change_finished)

    def open_image(self, path: str) -> bool:
        try:
            tl_image = TLImage.open(path)
            preview_max_dimension = self._preview_max_dimension()
            edited_image = tl_image.render_image(preview=True, max_dimension=preview_max_dimension)
            edited_pixmap = self._pil_to_pixmap(edited_image)
        except Exception:
            return False

        self._current_tlimage = tl_image
        self._original_preview_cache_key = None
        self._original_preview_pixmap = None
        original_pixmap = self._get_original_preview_pixmap(tl_image, preview_max_dimension)
        self._canvas.set_pixmaps(edited_pixmap, original_pixmap, reset_view=True)
        self._sync_right_panel_from_tlimage()
        self._right_panel.set_histogram_data(None)
        self._request_histogram_refresh(immediate=True)
        self.title_changed.emit(f"TempusLoom - {Path(path).name}")
        self._status_bar.set_image_info(*tl_image.image_size())
        return True

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

    def _sync_right_panel_from_tlimage(self) -> None:
        if self._current_tlimage is None:
            return
        self._right_panel.set_malayers(self._current_tlimage.malayers)
        self._right_panel.set_edit_state(self._current_tlimage.edit_state)
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
        pass

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

    def _redo(self) -> None:
        if self._current_tlimage is None:
            return
        if self._current_tlimage.redo():
            self._refresh_canvas_from_tlimage(sync_panel=True)

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

    def _on_canvas_color_picked(self, color: QColor) -> None:
        if self._current_tlimage is None:
            return
        self._right_panel.apply_color_editor_sample(color, committed=True)
        self._tool_sidebar.set_active_tool("mouse-pointer")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._export_thread is not None:
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
