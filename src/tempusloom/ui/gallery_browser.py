# -*- coding: utf-8 -*-
"""
TempusLoom – 图库浏览界面
Gallery browser window matching the pencil.pen design.
"""

from __future__ import annotations

import os
import sys
import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QObject, QThreadPool,
    QRunnable, QMutex, QTimer,
)
from PyQt6.QtGui import (
    QPixmap, QColor, QPainter, QBrush, QPen, QIcon,
    QLinearGradient, QFont, QFontDatabase, QPainterPath,
    QKeySequence, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QFileDialog,
    QSplitter, QLineEdit, QSizePolicy, QStackedWidget, QGridLayout,
    QGraphicsDropShadowEffect, QMenu, QInputDialog, QMessageBox,
)

from tempusloom.core import LibraryAsset, LibraryStore
from tempusloom.core.gallery_navigation import GalleryNavigator

# ── image file extensions ──────────────────────────────────────────────────────
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif",
    ".bmp", ".gif", ".heic", ".heif", ".raw", ".cr2", ".nef",
    ".arw", ".dng", ".orf", ".rw2", ".pef", ".srw",
}

# ── colours (from design file) ─────────────────────────────────────────────────
C_PRIMARY      = "#3370FF"
C_PRIMARY_H    = "#5B8FF9"
C_BG_APP       = "#181818"
C_BG_TOPBAR    = "#252525"
C_BG_PANEL     = "#1e1e1e"
C_BG_ITEM      = "#2c2c2c"
C_BG_ACTIVE    = "#1a3060"
C_BORDER       = "#333333"
C_BORDER_P     = "#2d2d2d"
C_TEXT_1       = "#e8e8e8"
C_TEXT_2       = "#aaaaaa"
C_TEXT_3       = "#888888"
C_TEXT_4       = "#777777"
C_WHITE        = "#ffffff"


# ── helper widgets ─────────────────────────────────────────────────────────────

class HLine(QFrame):
    """1 px horizontal divider."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("divider")
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class VLine(QFrame):
    """1 px vertical divider."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("dividerV")
        self.setFixedWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)


def _make_label(text: str, obj_name: str, parent=None) -> QLabel:
    lb = QLabel(text, parent)
    lb.setObjectName(obj_name)
    return lb


def _make_btn(text: str, obj_name: str, parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName(obj_name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return btn


def _make_chip(text: str, parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("toolChip")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return btn


def _logo_pixmap(size: int = 24) -> QPixmap:
    """Gradient blue logo icon."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor("#3370FF"))
    grad.setColorAt(1, QColor("#5B8FF9"))
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, 6, 6)
    p.fillPath(path, QBrush(grad))
    p.setPen(QColor(C_WHITE))
    p.setFont(QFont("Arial", max(size // 2, 8), QFont.Weight.Bold))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "T")
    p.end()
    return px


def _folder_icon(color: str = C_TEXT_4, size: int = 16) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidth(1)
    p.setPen(pen)
    # body
    body = QPainterPath()
    body.addRoundedRect(1, 5, size - 2, size - 7, 2, 2)
    # tab
    tab = QPainterPath()
    tab.addRoundedRect(1, 3, 6, 3, 1, 1)
    p.fillPath(body, QBrush(QColor(color)))
    p.fillPath(tab,  QBrush(QColor(color)))
    p.end()
    return px


def _tag_icon(color: str, size: int = 14) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    path = QPainterPath()
    # simple rounded-square tag
    path.addRoundedRect(1, 3, size - 4, size - 4, 2, 2)
    p.fillPath(path, QBrush(c))
    # hole
    p.setBrush(QBrush(QColor(C_BG_PANEL)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(size - 5, 2, 4, 4)
    p.end()
    return px


def _placeholder_thumb(width: int, height: int, index: int = 0) -> QPixmap:
    """Gradient placeholder when image cannot be loaded."""
    px = QPixmap(width, height)
    colours = [
        ("#2A4A7F", "#1A2F52"),
        ("#3B2A5A", "#231733"),
        ("#1E4A3A", "#122E24"),
        ("#4A3020", "#2E1D13"),
        ("#1A3A5A", "#0F2236"),
        ("#3A2040", "#221226"),
        ("#204A20", "#122C12"),
        ("#4A2020", "#2C1212"),
        ("#1A4040", "#0F2828"),
    ]
    c1, c2 = colours[index % len(colours)]
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0, QColor(c1))
    grad.setColorAt(1, QColor(c2))
    p = QPainter(px)
    p.fillRect(0, 0, width, height, QBrush(grad))
    p.end()
    return px


# ── async thumbnail loader ─────────────────────────────────────────────────────

class ThumbSignals(QObject):
    loaded = pyqtSignal(str, QPixmap)


class ThumbLoader(QRunnable):
    """Load & scale a single image thumbnail in a worker thread."""

    def __init__(self, path: str, width: int, height: int, index: int) -> None:
        super().__init__()
        self.path   = path
        self.width  = width
        self.height = height
        self.index  = index
        self.signals = ThumbSignals()

    def run(self) -> None:
        px = QPixmap(self.path)
        if px.isNull():
            px = _placeholder_thumb(self.width, self.height, self.index)
        else:
            px = px.scaled(
                self.width, self.height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # centre-crop to exact size
            if px.width() > self.width or px.height() > self.height:
                x = (px.width()  - self.width)  // 2
                y = (px.height() - self.height) // 2
                px = px.copy(x, y, self.width, self.height)
        self.signals.loaded.emit(self.path, px)


# ── thumbnail card ─────────────────────────────────────────────────────────────

class StarRatingWidget(QWidget):
    rating_changed = pyqtSignal(int)

    def __init__(self, rating: int = 0, *, interactive: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._rating = max(0, min(5, int(rating)))
        self._interactive = interactive
        self._buttons: list[QPushButton] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        for value in range(1, 6):
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _checked=False, v=value: self.set_rating(v, emit=True))
            self._buttons.append(btn)
            layout.addWidget(btn)
        self._refresh()

    def rating(self) -> int:
        return self._rating

    def set_rating(self, rating: int, *, emit: bool = False) -> None:
        self._rating = max(0, min(5, int(rating)))
        self._refresh()
        if emit and self._interactive:
            self.rating_changed.emit(self._rating)

    def _refresh(self) -> None:
        for index, btn in enumerate(self._buttons, start=1):
            active = index <= self._rating
            btn.setText("★" if active else "☆")
            btn.setStyleSheet(
                "QPushButton{background:transparent; border:none; "
                f"color:{'#FBBF24' if active else C_TEXT_4}; font-size:14px; padding:0;}}"
            )


class ThumbnailCard(QWidget):
    """Single thumbnail item: rounded image + filename label."""

    clicked = pyqtSignal(str)   # emits file path
    double_clicked = pyqtSignal(str)
    rating_changed = pyqtSignal(str, int)

    THUMB_H = 160

    def __init__(self, path: str, index: int, selected: bool = False,
                 rating: int = 0, missing: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.path     = path
        self.index    = index
        self._selected = selected
        self._rating = max(0, min(5, int(rating)))
        self._missing = missing
        self._pixmap: Optional[QPixmap] = None
        self._setup_ui()

    # ── build ──────────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.setLayout(layout)

        self._img_label = QLabel()
        self._img_label.setFixedHeight(self.THUMB_H)
        self._img_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet(
            f"border-radius: 8px; background: {C_BG_ITEM};"
        )
        layout.addWidget(self._img_label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        name = Path(self.path).name if self.path else f"IMG_{self.index:04d}.RAW"
        self._name_label = QLabel(("⚠ " if self._missing else "") + name)
        self._name_label.setObjectName("thumbName")
        row_layout.addWidget(self._name_label, 1)

        self._rating_widget = StarRatingWidget(self._rating)
        self._rating_widget.rating_changed.connect(lambda rating: self.rating_changed.emit(self.path, rating))
        row_layout.addWidget(self._rating_widget)
        layout.addWidget(row)

        # show placeholder immediately
        self._show_placeholder()
        self._update_border()

    # ── placeholder / real image ───────────────────────────────────────────────
    def _show_placeholder(self) -> None:
        px = _placeholder_thumb(200, self.THUMB_H, self.index)
        self._apply_pixmap(px)

    def _apply_pixmap(self, px: QPixmap) -> None:
        self._pixmap = px
        # draw rounded pixmap
        rounded = QPixmap(px.size())
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, rounded.width(), rounded.height(), 8, 8)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, px)
        painter.end()
        self._img_label.setPixmap(rounded)
        self._img_label.setFixedHeight(self.THUMB_H)

    def set_pixmap(self, px: QPixmap) -> None:
        """Called from main thread with the loaded pixmap."""
        w = self._img_label.width() or 200
        px = px.scaled(
            w, self.THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if px.width() > w or px.height() > self.THUMB_H:
            x = (px.width()  - w)            // 2
            y = (px.height() - self.THUMB_H) // 2
            px = px.copy(x, y, w, self.THUMB_H)
        self._apply_pixmap(px)

    # ── selection ──────────────────────────────────────────────────────────────
    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._update_border()

    def set_rating(self, rating: int) -> None:
        self._rating = max(0, min(5, int(rating)))
        self._rating_widget.set_rating(self._rating)

    def _update_border(self) -> None:
        border = f"2px solid {C_PRIMARY}" if self._selected else "none"
        self._img_label.setStyleSheet(
            f"border-radius: 8px; background: {C_BG_ITEM}; border: {border};"
        )

    # ── events ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, _event) -> None:       # noqa: N802
        self.clicked.emit(self.path)

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self.double_clicked.emit(self.path)

    def enterEvent(self, _event) -> None:            # noqa: N802
        if not self._selected:
            self._img_label.setStyleSheet(
                f"border-radius: 8px; background: {C_BG_ITEM};"
                f"border: 1px solid {C_BORDER};"
            )

    def leaveEvent(self, _event) -> None:            # noqa: N802
        self._update_border()


# ── top bar ────────────────────────────────────────────────────────────────────

class GalleryTopBar(QWidget):
    """Navigation bar at the very top (h=48)."""

    mode_switched = pyqtSignal(str)   # "gallery" | "editor"
    tab_changed   = pyqtSignal(str)   # "图库" | "最近" | "收藏"
    import_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(48)
        self._active_tab = "图库"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        # ── left group ─────────────────────────────────────────────────────────
        # logo
        logo_px = QLabel()
        logo_px.setPixmap(_logo_pixmap(24))
        logo_px.setFixedSize(24, 24)
        layout.addWidget(logo_px)
        layout.addSpacing(8)

        logo_txt = _make_label("TempusLoom", "logoText")
        layout.addWidget(logo_txt)
        layout.addSpacing(12)

        layout.addWidget(VLine())
        layout.addSpacing(12)

        # mode switch
        mode_frame = QWidget()
        mode_frame.setObjectName("modeSwitch")
        mode_frame.setFixedHeight(32)
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(0)

        self._btn_gallery = QPushButton("图库")
        self._btn_gallery.setObjectName("modeBtnActive")
        self._btn_gallery.setFixedHeight(28)
        self._btn_gallery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gallery.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_gallery.clicked.connect(lambda: self.mode_switched.emit("gallery"))

        self._btn_editor = QPushButton("编辑器")
        self._btn_editor.setObjectName("modeBtnInactive")
        self._btn_editor.setFixedHeight(28)
        self._btn_editor.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_editor.clicked.connect(lambda: self.mode_switched.emit("editor"))

        mode_layout.addWidget(self._btn_gallery)
        mode_layout.addWidget(self._btn_editor)
        layout.addWidget(mode_frame)
        layout.addSpacing(12)

        layout.addWidget(VLine())
        layout.addSpacing(4)

        # nav tabs
        self._nav_tabs: dict[str, QPushButton] = {}
        for name in ("图库", "最近", "收藏"):
            btn = QPushButton(name)
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda checked=False, n=name: self._on_tab(n))
            self._nav_tabs[name] = btn
            layout.addWidget(btn)
        self._update_nav_tabs()
        layout.addSpacing(8)

        # ── spacer ─────────────────────────────────────────────────────────────
        layout.addStretch()

        # ── right group ────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setObjectName("searchBox")
        self._search.setPlaceholderText("搜索图像...")
        self._search.setFixedSize(220, 32)
        layout.addWidget(self._search)
        layout.addSpacing(8)

        import_btn = _make_btn("  导入", "importBtn")
        import_btn.setFixedHeight(32)
        import_btn.clicked.connect(self.import_clicked.emit)
        layout.addWidget(import_btn)
        layout.addSpacing(8)

        # avatar circle
        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        av_px = QPixmap(28, 28)
        av_px.fill(Qt.GlobalColor.transparent)
        p = QPainter(av_px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(C_BG_ACTIVE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 28, 28)
        p.setPen(QColor(C_PRIMARY))
        p.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        p.drawText(av_px.rect(), Qt.AlignmentFlag.AlignCenter, "U")
        p.end()
        avatar.setPixmap(av_px)
        layout.addWidget(avatar)

    def _on_tab(self, name: str) -> None:
        self._active_tab = name
        self._update_nav_tabs()
        self.tab_changed.emit(name)

    def _update_nav_tabs(self) -> None:
        for name, btn in self._nav_tabs.items():
            if name == self._active_tab:
                btn.setObjectName("navTabActive")
            else:
                btn.setObjectName("navTabInactive")
            # force stylesheet re-apply
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    @property
    def search_text(self) -> str:
        return self._search.text()

    def connect_search(self, slot) -> None:
        self._search.textChanged.connect(slot)


# ── sidebar ────────────────────────────────────────────────────────────────────

class FolderItem(QWidget):
    """Single clickable sidebar row (folder or tag)."""

    clicked = pyqtSignal(str)

    def __init__(self, icon_px: QPixmap, name: str, count: str = "",
                 active: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._name   = name
        self._active = active
        self._setup_ui(icon_px, name, count)
        self._update_style()

    def _setup_ui(self, icon_px: QPixmap, name: str, count: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        icon_lb = QLabel()
        icon_lb.setPixmap(icon_px)
        icon_lb.setFixedSize(icon_px.size())
        icon_lb.setObjectName("transparent")
        layout.addWidget(icon_lb)

        self._name_lb = QLabel(name)
        self._name_lb.setObjectName("sideItemTextActive" if self._active else "sideItemTextInactive")
        layout.addWidget(self._name_lb)

        layout.addStretch()

        if count:
            cnt_lb = QLabel(count)
            cnt_lb.setObjectName("sideItemCount")
            layout.addWidget(cnt_lb)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _update_style(self) -> None:
        obj = "sideItemActive" if self._active else "sideItemInactive"
        self.setObjectName(obj)
        # re-polish
        self.style().unpolish(self)
        self.style().polish(self)
        # update child name label
        self._name_lb.setObjectName("sideItemTextActive" if self._active else "sideItemTextInactive")
        self._name_lb.style().unpolish(self._name_lb)
        self._name_lb.style().polish(self._name_lb)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_style()

    def mousePressEvent(self, _event) -> None:      # noqa: N802
        self.clicked.emit(self._name)


class GallerySidebar(QWidget):
    """Left sidebar: folder list + tags (w=200)."""

    folder_selected = pyqtSignal(str)

    _FOLDERS = [
        ("风景",   "24"),
        ("人像",   "18"),
        ("产品",   "12"),
        ("客户项目", "8"),
    ]
    _TAGS = [
        ("假日", "#22C55E"),
        ("工作", "#F59E0B"),
        ("旅行", "#6366F1"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        self._active_folder = "全部照片"
        self._folder_items: dict[str, FolderItem] = {}
        self._folder_list_layout: Optional[QVBoxLayout] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # ── folders ───────────────────────────────────────────────────────────
        layout.addWidget(_make_label("文件夹", "sideSection"))
        layout.addSpacing(4)

        folder_list = QWidget()
        self._folder_list_layout = QVBoxLayout(folder_list)
        self._folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_list_layout.setSpacing(4)
        layout.addWidget(folder_list)
        self.set_folders([("全部照片", "0")])

        layout.addSpacing(8)
        layout.addWidget(HLine())
        layout.addSpacing(8)

        # ── tags ──────────────────────────────────────────────────────────────
        layout.addWidget(_make_label("标签", "sideSection"))
        layout.addSpacing(4)

        for tag_name, tag_color in self._TAGS:
            item = FolderItem(
                _tag_icon(tag_color, 14), tag_name, active=False,
            )
            item.clicked.connect(self._on_folder_clicked)
            layout.addWidget(item)

        layout.addStretch()

    def _on_folder_clicked(self, name: str) -> None:
        # deactivate old
        if name in self._folder_items:
            old = self._folder_items.get(self._active_folder)
            if old:
                old.set_active(False)
            self._folder_items[name].set_active(True)
            self._active_folder = name
        self.folder_selected.emit(name)

    def set_folders(self, folders: list[tuple[str, str]]) -> None:
        """Dynamically rebuild folder list from real directory scan."""
        if self._folder_list_layout is None:
            return
        for item in self._folder_items.values():
            item.setParent(None)
        self._folder_items.clear()
        for name, count in folders:
            active = name == self._active_folder
            icon_color = C_PRIMARY if active else C_TEXT_4
            item = FolderItem(_folder_icon(icon_color, 16), name, count, active)
            item.clicked.connect(self._on_folder_clicked)
            self._folder_items[name] = item
            self._folder_list_layout.addWidget(item)
        if self._active_folder not in self._folder_items and self._folder_items:
            self._active_folder = next(iter(self._folder_items))
            self._folder_items[self._active_folder].set_active(True)


# ── grid toolbar ───────────────────────────────────────────────────────────────

class GridToolbar(QWidget):
    """Bar above the thumbnail grid (h=40)."""

    sort_clicked   = pyqtSignal()
    filter_clicked = pyqtSignal()
    view_clicked   = pyqtSignal()
    rating_filter_changed = pyqtSignal(str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridToolbar")
        self.setFixedHeight(40)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self._info_label = _make_label("风景  ·  24 张图片", "gridInfo")
        layout.addWidget(self._info_label)
        layout.addStretch()

        sort_btn   = _make_chip("排序 ▾")
        self._filter_btn = _make_chip("全部星级 ▾")
        view_btn   = _make_chip("⊞")
        sort_btn.clicked.connect(self.sort_clicked.emit)
        self._filter_btn.clicked.connect(self._open_filter_menu)
        view_btn.clicked.connect(self.view_clicked.emit)
        layout.addWidget(sort_btn)
        layout.addWidget(self._filter_btn)
        layout.addWidget(view_btn)

    def update_info(self, folder: str, count: int) -> None:
        self._info_label.setText(f"{folder}  ·  {count} 张图片")

    def set_rating_filter(self, mode: str, rating: int) -> None:
        if mode == "exact":
            self._filter_btn.setText(f"正好 {rating} 星 ▾")
        elif mode == "minimum" and rating > 0:
            self._filter_btn.setText(f"{rating} 星及以上 ▾")
        else:
            self._filter_btn.setText("全部星级 ▾")

    def _open_filter_menu(self) -> None:
        menu = QMenu(self)
        all_action = menu.addAction("全部星级")
        all_action.triggered.connect(lambda _checked=False: self.rating_filter_changed.emit("all", 0))
        minimum_menu = menu.addMenu("至少")
        for rating in range(1, 6):
            action = minimum_menu.addAction(f"{rating} 星及以上")
            action.triggered.connect(lambda _checked=False, r=rating: self.rating_filter_changed.emit("minimum", r))
        exact_menu = menu.addMenu("正好")
        for rating in range(0, 6):
            label = "0 星（未评级）" if rating == 0 else f"{rating} 星"
            action = exact_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, r=rating: self.rating_filter_changed.emit("exact", r))
        menu.exec(self._filter_btn.mapToGlobal(self._filter_btn.rect().bottomLeft()))


# ── info panel ─────────────────────────────────────────────────────────────────

class InfoPanel(QWidget):
    """Right panel: preview + EXIF + quick actions (w=260)."""

    open_in_editor = pyqtSignal(str)
    export_image   = pyqtSignal(str)
    rating_changed = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("infoPanel")
        self.setFixedWidth(260)
        self._current_path: str = ""
        self._rating = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # preview
        self._preview = QLabel()
        self._preview.setFixedHeight(160)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            f"border-radius: 8px; background: {C_BG_ITEM};"
        )
        layout.addWidget(self._preview)

        # file name
        self._title = _make_label("IMG_0123.RAW", "infoTitle")
        layout.addWidget(self._title)

        self._rating_widget = StarRatingWidget(0)
        self._rating_widget.rating_changed.connect(self.rating_changed.emit)
        layout.addWidget(self._rating_widget)

        # EXIF rows
        self._exif_widget = QWidget()
        exif_layout = QVBoxLayout(self._exif_widget)
        exif_layout.setContentsMargins(0, 0, 0, 0)
        exif_layout.setSpacing(8)
        self._exif_rows: list[tuple[QLabel, QLabel]] = []
        for key in ("尺寸", "拍摄日期", "相机", "光圈", "ISO", "焦距", "快门"):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            lbl_k = _make_label(key, "infoLabel")
            lbl_v = _make_label("—", "infoValue")
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(lbl_k)
            row_layout.addStretch()
            row_layout.addWidget(lbl_v)
            exif_layout.addWidget(row)
            self._exif_rows.append((lbl_k, lbl_v))
        layout.addWidget(self._exif_widget)

        layout.addWidget(HLine())

        # quick actions
        actions_widget = QWidget()
        act_layout = QVBoxLayout(actions_widget)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(8)

        act_layout.addWidget(_make_label("快捷操作", "infoActTitle"))

        self._btn_open = _make_btn("在编辑器打开", "actBtnPrimary")
        self._btn_open.setFixedHeight(36)
        self._btn_open.clicked.connect(lambda: self.open_in_editor.emit(self._current_path))
        act_layout.addWidget(self._btn_open)

        self._btn_export = _make_btn("导出...", "actBtnSecondary")
        self._btn_export.setFixedHeight(36)
        self._btn_export.clicked.connect(lambda: self.export_image.emit(self._current_path))
        act_layout.addWidget(self._btn_export)

        self._btn_more = _make_btn("后续处理...", "actBtnSecondary")
        self._btn_more.setFixedHeight(36)
        act_layout.addWidget(self._btn_more)

        layout.addWidget(actions_widget)
        layout.addStretch()

    # ── public api ─────────────────────────────────────────────────────────────
    def update_info(self, path: str, pixmap: Optional[QPixmap] = None, *, rating: int = 0) -> None:
        """Populate panel with metadata from *path*."""
        self._current_path = path
        self._rating = max(0, min(5, int(rating)))
        self._rating_widget.set_rating(self._rating)
        fname = Path(path).name if path else "—"
        self._title.setText(fname)

        # preview
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                228, 160,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            if scaled.width() > 228 or scaled.height() > 160:
                x = (scaled.width()  - 228) // 2
                y = (scaled.height() - 160) // 2
                scaled = scaled.copy(x, y, 228, 160)
            rounded = QPixmap(228, 160)
            rounded.fill(Qt.GlobalColor.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = QPainterPath()
            clip.addRoundedRect(0, 0, 228, 160, 8, 8)
            p.setClipPath(clip)
            p.drawPixmap(0, 0, scaled)
            p.end()
            self._preview.setPixmap(rounded)
        else:
            self._preview.clear()

        # EXIF via Pillow (optional)
        exif_values = self._read_exif(path)
        keys = ("尺寸", "拍摄日期", "相机", "光圈", "ISO", "焦距", "快门")
        defaults = {
            "尺寸":   "5472 × 3648 px",
            "拍摄日期": "2025-04-15",
            "相机":   "Canon EOS R5",
            "光圈":   "f/2.8",
            "ISO":   "100",
            "焦距":   "24 mm",
            "快门":   "1/125 s",
        }
        for (lbl_k, lbl_v), key in zip(self._exif_rows, keys):
            lbl_v.setText(exif_values.get(key, defaults.get(key, "—")))

    @staticmethod
    def _read_exif(path: str) -> dict[str, str]:
        """Try to read EXIF data with Pillow. Returns empty dict on failure."""
        result: dict[str, str] = {}
        if not path or not os.path.isfile(path):
            return result
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            img = Image.open(path)
            # dimensions
            result["尺寸"] = f"{img.width} × {img.height} px"
            raw = img._getexif()         # noqa: SLF001
            if not raw:
                return result
            tag_map = {v: k for k, v in TAGS.items()}
            exif = {TAGS.get(k, k): v for k, v in raw.items()}

            if "DateTimeOriginal" in exif:
                try:
                    dt = datetime.datetime.strptime(exif["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S")
                    result["拍摄日期"] = dt.strftime("%Y-%m-%d")
                except ValueError:
                    result["拍摄日期"] = str(exif["DateTimeOriginal"])
            if "Model" in exif:
                result["相机"] = str(exif["Model"]).strip()
            if "FNumber" in exif:
                fn = exif["FNumber"]
                try:
                    result["光圈"] = f"f/{float(fn):.1f}"
                except Exception:
                    result["光圈"] = str(fn)
            if "ISOSpeedRatings" in exif:
                result["ISO"] = str(exif["ISOSpeedRatings"])
            if "FocalLength" in exif:
                fl = exif["FocalLength"]
                try:
                    result["焦距"] = f"{float(fl):.0f} mm"
                except Exception:
                    result["焦距"] = str(fl)
            if "ExposureTime" in exif:
                et = exif["ExposureTime"]
                try:
                    fv = float(et)
                    if fv < 1:
                        result["快门"] = f"1/{round(1/fv)} s"
                    else:
                        result["快门"] = f"{fv:.1f} s"
                except Exception:
                    result["快门"] = str(et)
        except Exception:
            pass
        return result


# ── thumbnail grid ─────────────────────────────────────────────────────────────

class ThumbnailGrid(QScrollArea):
    """Scrollable 3-column masonry-style grid."""

    image_selected = pyqtSignal(str, QPixmap)   # path, pixmap
    image_activated = pyqtSignal(str)
    rating_changed = pyqtSignal(str, int)

    COLUMNS = 3

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridArea")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._cards: list[ThumbnailCard] = []
        self._selected_path: str = ""
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._assets_by_path: dict[str, LibraryAsset] = {}
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)

        self._container = QWidget()
        self._container.setObjectName("gridArea")
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setContentsMargins(16, 16, 16, 16)
        self._grid_layout.setSpacing(12)
        for col in range(self.COLUMNS):
            self._grid_layout.setColumnStretch(col, 1)
        self.setWidget(self._container)

    # ── loading ────────────────────────────────────────────────────────────────
    def load_images(self, paths: list[str]) -> None:
        self.load_assets([self._asset_from_path(path) for path in paths])

    def load_assets(self, assets: list[LibraryAsset]) -> None:
        # clear
        for card in self._cards:
            card.setParent(None)
        self._cards.clear()
        self._pixmap_cache.clear()
        self._assets_by_path = {asset.path: asset for asset in assets}

        if not assets:
            self._selected_path = ""
            return

        for idx, asset in enumerate(assets):
            row, col = divmod(idx, self.COLUMNS)
            selected = (idx == 0)
            card = ThumbnailCard(asset.path, idx, selected, rating=asset.rating, missing=asset.missing)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self.image_activated.emit)
            card.rating_changed.connect(self.rating_changed.emit)
            self._cards.append(card)
            self._grid_layout.addWidget(card, row, col)

        # select first
        if assets:
            self._selected_path = assets[0].path
            QTimer.singleShot(0, lambda: self.image_selected.emit(
                self._selected_path,
                self._pixmap_cache.get(self._selected_path, QPixmap()),
            ))

        # kick off async loading
        for idx, asset in enumerate(assets):
            loader = ThumbLoader(asset.path, 200, ThumbnailCard.THUMB_H, idx)
            loader.signals.loaded.connect(self._on_thumb_loaded)
            self._pool.start(loader)

    @staticmethod
    def _asset_from_path(path: str) -> LibraryAsset:
        file_path = Path(path)
        return LibraryAsset(
            id=path,
            path=path,
            file_name=file_path.name,
            folder_path=str(file_path.parent),
            extension=file_path.suffix.lower().lstrip("."),
            file_size=0,
            width=None,
            height=None,
            rating=0,
            missing=not file_path.is_file(),
            imported_at="",
            updated_at="",
        )

    def load_placeholders(self, count: int = 9,
                          names: Optional[list[str]] = None) -> None:
        """Show placeholder cards (no real file paths)."""
        fake_paths = [
            names[i] if names and i < len(names) else f"IMG_{i+123:04d}.RAW"
            for i in range(count)
        ]
        for card in self._cards:
            card.setParent(None)
        self._cards.clear()

        for idx, name in enumerate(fake_paths):
            row, col = divmod(idx, self.COLUMNS)
            selected = (idx == 0)
            card = ThumbnailCard("", idx, selected)
            card._name_label.setText(name)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self.image_activated.emit)
            self._cards.append(card)
            self._grid_layout.addWidget(card, row, col)

        if fake_paths:
            self._selected_path = fake_paths[0]
            QTimer.singleShot(0, lambda: self.image_selected.emit(
                self._selected_path, QPixmap()
            ))

    # ── slots ──────────────────────────────────────────────────────────────────
    def _on_card_clicked(self, path: str) -> None:
        for card in self._cards:
            card.set_selected(card.path == path or
                              (not path and card._name_label.text() == self._selected_path))
        self._selected_path = path
        self.image_selected.emit(path, self._pixmap_cache.get(path, QPixmap()))

    def selected_path(self) -> str:
        return self._selected_path

    def set_card_rating(self, path: str, rating: int) -> None:
        for card in self._cards:
            if card.path == path:
                card.set_rating(rating)
                break

    def select_path(self, path: str) -> None:
        if path:
            self._on_card_clicked(path)

    def _on_thumb_loaded(self, path: str, px: QPixmap) -> None:
        self._pixmap_cache[path] = px
        for card in self._cards:
            if card.path == path:
                card.set_pixmap(px)
                if path == self._selected_path:
                    self.image_selected.emit(path, px)
                break

    # ── filter ────────────────────────────────────────────────────────────────
    def filter_by_text(self, text: str) -> None:
        text = text.lower()
        for card in self._cards:
            name = Path(card.path).name.lower() if card.path else card._name_label.text().lower()
            card.setVisible(text in name if text else True)


class GalleryLoupeView(QWidget):
    """Large single-image browser view."""

    back_to_grid = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridArea")
        self._path = ""
        self._pixmap = QPixmap()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self._title = _make_label("—", "gridInfo")
        header_layout.addWidget(self._title)
        header_layout.addStretch()
        back_btn = _make_chip("返回网格")
        back_btn.clicked.connect(self.back_to_grid.emit)
        header_layout.addWidget(back_btn)
        layout.addWidget(header)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet(f"background:{C_BG_APP}; border-radius:8px;")
        self._image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._image, 1)

    def set_image(self, path: str, pixmap: QPixmap) -> None:
        self._path = path
        self._title.setText(Path(path).name if path else "—")
        self._pixmap = pixmap if pixmap and not pixmap.isNull() else QPixmap(path)
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._pixmap.isNull():
            self._image.clear()
            return
        available = self._image.size()
        scaled = self._pixmap.scaled(
            max(1, available.width()),
            max(1, available.height()),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image.setPixmap(scaled)


class Filmstrip(QWidget):
    """Bottom thumbnail strip for the current gallery result set."""

    image_selected = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridToolbar")
        self.setFixedHeight(104)
        self._buttons: dict[str, QPushButton] = {}
        self._selected_path = ""

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")
        outer.addWidget(scroll)

        self._content = QWidget()
        self._layout = QHBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        scroll.setWidget(self._content)

    def load_assets(self, assets: list[LibraryAsset], selected_path: str = "") -> None:
        for button in self._buttons.values():
            button.setParent(None)
        self._buttons.clear()
        self._selected_path = selected_path
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        for asset in assets:
            btn = QPushButton()
            btn.setFixedSize(88, 68)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setToolTip(asset.file_name)
            btn.clicked.connect(lambda _checked=False, p=asset.path: self.image_selected.emit(p))
            pixmap = QPixmap(asset.path)
            if pixmap.isNull():
                pixmap = _placeholder_thumb(88, 68, len(self._buttons))
            else:
                pixmap = pixmap.scaled(
                    88,
                    68,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                pixmap = pixmap.copy(max(0, (pixmap.width() - 88) // 2), max(0, (pixmap.height() - 68) // 2), 88, 68)
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(88, 68))
            self._buttons[asset.path] = btn
            self._layout.addWidget(btn)
        self._layout.addStretch()
        self.set_selected(selected_path)

    def set_selected(self, path: str) -> None:
        self._selected_path = path
        for button_path, button in self._buttons.items():
            border = f"2px solid {C_PRIMARY}" if button_path == path else f"1px solid {C_BORDER}"
            button.setStyleSheet(f"QPushButton{{background:{C_BG_ITEM}; border:{border}; border-radius:6px; padding:0;}}")


# ── main gallery window ────────────────────────────────────────────────────────

class GalleryBrowser(QWidget):
    """图库浏览界面 – embedded page inside TempusLoomWindow."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_dir: Optional[str] = None
        self._store: Optional[LibraryStore] = None
        self._assets: list[LibraryAsset] = []
        self._asset_by_path: dict[str, LibraryAsset] = {}
        self._active_folder_path: Optional[str] = None
        self._rating_filter_mode = "all"
        self._rating_filter_value = 0
        self._search_text = ""
        self._navigator = GalleryNavigator()
        self._current_pixmap = QPixmap()
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()

        # Load sample placeholders matching the design
        self._load_placeholders()

    # ── build ──────────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # content area
        content = QWidget()
        content.setObjectName("root")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        root_layout.addWidget(content, 1)

        # sidebar
        self._sidebar = GallerySidebar()
        content_layout.addWidget(self._sidebar)

        # grid area (toolbar + grid)
        grid_container = QWidget()
        grid_container.setObjectName("gridArea")
        grid_v = QVBoxLayout(grid_container)
        grid_v.setContentsMargins(0, 0, 0, 0)
        grid_v.setSpacing(0)

        self._grid_toolbar = GridToolbar()
        grid_v.addWidget(self._grid_toolbar)

        self._view_stack = QStackedWidget()
        self._grid = ThumbnailGrid()
        self._loupe = GalleryLoupeView()
        self._view_stack.addWidget(self._grid)
        self._view_stack.addWidget(self._loupe)
        grid_v.addWidget(self._view_stack, 1)

        self._filmstrip = Filmstrip()
        grid_v.addWidget(self._filmstrip)

        content_layout.addWidget(grid_container, 1)

        # info panel
        self._info_panel = InfoPanel()
        content_layout.addWidget(self._info_panel)

    def _connect_signals(self) -> None:
        self._sidebar.folder_selected.connect(self._on_folder_selected)
        self._grid.image_selected.connect(self._on_image_selected)
        self._grid.image_activated.connect(self._show_loupe_for_path)
        self._grid.rating_changed.connect(self._set_rating_for_path)
        self._grid_toolbar.rating_filter_changed.connect(self._set_rating_filter)
        self._info_panel.rating_changed.connect(self._set_rating_for_selected)
        self._loupe.back_to_grid.connect(self._show_grid)
        self._filmstrip.image_selected.connect(self._select_path)

    def _setup_shortcuts(self) -> None:
        for rating in range(0, 6):
            QShortcut(QKeySequence(str(rating)), self, lambda r=rating: self._set_rating_for_selected(r))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._select_previous_image)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._select_next_image)

    # ── public api for UnifiedTopBar ───────────────────────────────────────────
    def trigger_import(self) -> None:
        self._on_import()

    def trigger_tab(self, name: str) -> None:
        self._on_tab_changed(name)

    def filter_by_search(self, text: str) -> None:
        self._search_text = text
        self._reload_assets()

    def current_image_paths(self) -> list[str]:
        return [asset.path for asset in self._assets] if self._assets else []

    # ── initial data ───────────────────────────────────────────────────────────
    def _load_placeholders(self) -> None:
        names = [f"IMG_{i:04d}.RAW" for i in range(123, 132)]
        self._grid.load_placeholders(9, names)
        self._grid_toolbar.update_info("风景", 24)

    # ── slots ──────────────────────────────────────────────────────────────────
    def _on_import(self) -> None:
        menu = QMenu(self)
        create_action = menu.addAction("创建图库项目...")
        open_action = menu.addAction("打开图库项目...")
        menu.addSeparator()
        add_folder_action = menu.addAction("添加文件夹到图库...")
        add_images_action = menu.addAction("添加图片到图库...")
        action = menu.exec(self.mapToGlobal(self.rect().topRight()))
        if action == create_action:
            self._create_library_project()
        elif action == open_action:
            self._open_library_project()
        elif action == add_folder_action:
            self._add_folder_to_library()
        elif action == add_images_action:
            self._add_images_to_library()

    def _create_library_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择初始图片文件夹", str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        library_parent = QFileDialog.getExistingDirectory(self, "选择图库项目保存位置", str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not library_parent:
            return
        default_name = Path(folder).name or "TempusLoom Library"
        name, ok = QInputDialog.getText(self, "创建图库项目", "图库名称：", text=default_name)
        if not ok or not name.strip():
            return
        library_path = Path(library_parent) / f"{name.strip()}.tlibrary"
        try:
            self._store = LibraryStore.create(library_path, name.strip(), initial_folder=folder)
        except Exception as exc:
            QMessageBox.warning(self, "创建图库失败", str(exc))
            return
        self._current_dir = folder
        self._active_folder_path = None
        self._reload_assets()

    def _open_library_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "打开图库项目", str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        try:
            self._store = LibraryStore.open(folder)
        except Exception as exc:
            QMessageBox.warning(self, "打开图库失败", str(exc))
            return
        self._active_folder_path = None
        self._reload_assets()

    def _ensure_library(self) -> bool:
        if self._store is not None:
            return True
        QMessageBox.information(self, "请先创建图库", "请先创建或打开一个图库项目。")
        return False

    def _add_folder_to_library(self) -> None:
        if not self._ensure_library():
            return
        folder = QFileDialog.getExistingDirectory(self, "添加文件夹到图库", str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        result = self._store.add_folder(folder)
        self._active_folder_path = None
        self._reload_assets()
        QMessageBox.information(self, "导入完成", f"扫描 {result.scanned} 张，新增 {result.imported} 张，跳过 {result.skipped} 张。")

    def _add_images_to_library(self) -> None:
        if not self._ensure_library():
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "添加图片到图库",
            str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp)",
        )
        if not files:
            return
        result = self._store.add_images(files)
        self._reload_assets()
        QMessageBox.information(self, "导入完成", f"扫描 {result.scanned} 张，新增 {result.imported} 张，跳过 {result.skipped} 张。")

    def _on_tab_changed(self, tab: str) -> None:
        # placeholder – extend for real recent/favorites data
        pass

    def _on_folder_selected(self, name: str) -> None:
        if name == "全部照片":
            self._active_folder_path = None
        else:
            self._active_folder_path = name
        self._reload_assets()

    def _on_image_selected(self, path: str, pixmap: QPixmap) -> None:
        self._navigator.select(path)
        self._current_pixmap = pixmap
        asset = self._asset_by_path.get(path)
        self._info_panel.update_info(path, pixmap, rating=asset.rating if asset else 0)
        self._filmstrip.set_selected(path)
        if self._view_stack.currentWidget() == self._loupe:
            self._loupe.set_image(path, pixmap)

    def _set_rating_filter(self, mode: str, rating: int) -> None:
        if mode not in {"all", "minimum", "exact"}:
            mode = "all"
        self._rating_filter_mode = mode
        self._rating_filter_value = max(0, min(5, int(rating)))
        self._grid_toolbar.set_rating_filter(self._rating_filter_mode, self._rating_filter_value)
        self._reload_assets()

    def _set_rating_for_selected(self, rating: int) -> None:
        path = self._grid.selected_path()
        if path:
            self._set_rating_for_path(path, rating)

    def _set_rating_for_path(self, path: str, rating: int) -> None:
        if not self._store:
            return
        asset = self._asset_by_path.get(path)
        if not asset:
            return
        self._store.set_rating(asset.id, rating)
        self._grid.set_card_rating(path, rating)
        self._reload_assets(keep_selection=path)

    def _reload_assets(self, *, keep_selection: Optional[str] = None) -> None:
        if not self._store:
            self._load_placeholders()
            return
        exact_rating = self._rating_filter_value if self._rating_filter_mode == "exact" else None
        min_rating = self._rating_filter_value if self._rating_filter_mode == "minimum" else 0
        self._assets = self._store.query_images(
            min_rating=min_rating,
            exact_rating=exact_rating,
            search=self._search_text,
            folder_path=self._active_folder_path,
        )
        self._asset_by_path = {asset.path: asset for asset in self._assets}
        preferred = keep_selection or self._navigator.current_path
        selected_path = self._navigator.set_paths([asset.path for asset in self._assets], preferred_path=preferred)
        self._grid.load_assets(self._assets)
        self._filmstrip.load_assets(self._assets, selected_path=selected_path)
        if selected_path:
            self._grid.select_path(selected_path)
        label = Path(self._active_folder_path).name if self._active_folder_path else "全部照片"
        self._grid_toolbar.update_info(label, len(self._assets))
        folders = [("全部照片", str(len(self._store.query_images(include_missing=True))))]
        folders.extend((folder, str(count)) for folder, count in self._store.folder_counts())
        self._sidebar.set_folders(folders)

    def _select_path(self, path: str) -> None:
        if path in self._asset_by_path:
            self._navigator.select(path)
            self._grid.select_path(path)

    def _select_next_image(self) -> None:
        path = self._navigator.next_path()
        if path:
            self._select_path(path)

    def _select_previous_image(self) -> None:
        path = self._navigator.previous_path()
        if path:
            self._select_path(path)

    def _show_loupe_for_path(self, path: str) -> None:
        if path:
            self._select_path(path)
            self._loupe.set_image(path, self._current_pixmap)
            self._view_stack.setCurrentWidget(self._loupe)

    def _show_grid(self) -> None:
        self._view_stack.setCurrentWidget(self._grid)
