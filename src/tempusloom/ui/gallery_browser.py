# -*- coding: utf-8 -*-
"""
TempusLoom – 图库浏览界面
Gallery browser window matching the pencil.pen design.
"""

from __future__ import annotations

import os
import sys
import datetime
from datetime import datetime as DateTime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QObject, QThreadPool,
    QRunnable, QMutex, QTimer,
)
from PyQt6.QtGui import (
    QPixmap, QColor, QPainter, QBrush, QPen, QIcon,
    QLinearGradient, QFont, QFontDatabase, QPainterPath,
    QKeySequence, QShortcut, QImage, QFileSystemModel,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QFileDialog,
    QSplitter, QLineEdit, QSizePolicy, QStackedWidget, QGridLayout,
    QGraphicsDropShadowEffect, QMenu, QInputDialog, QMessageBox,
    QDialog, QDialogButtonBox, QProgressDialog, QSpinBox, QMenuBar,
    QTreeView, QComboBox,
)

from tempusloom.core import (
    LibraryAsset,
    LibraryProject,
    LibraryProjectIndex,
    LibraryStore,
    TempusLoomSettings,
    ThumbnailProgress,
)
from tempusloom.core.gallery_navigation import (
    GalleryNavigator,
    gallery_tab_shows_project_browser,
    neighboring_paths,
    split_gallery_import_paths,
)
from PIL import Image, ImageOps

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

def gallery_loupe_layout_order() -> list[str]:
    return ["toolbar", "view_stack", "action_bar", "filmstrip"]


def gallery_loupe_uses_embedded_rating_row() -> bool:
    return False


def gallery_thumbnail_frame_size() -> tuple[int, int]:
    return (180, 180)


def gallery_thumbnail_grid_spacing() -> tuple[int, int]:
    return (28, 28)


def gallery_thumbnail_grid_columns(available_width: int) -> int:
    margin = 28 * 2
    spacing = gallery_thumbnail_grid_spacing()[0]
    card_width = gallery_thumbnail_frame_size()[0]
    usable_width = max(0, int(available_width) - margin)
    return max(1, (usable_width + spacing) // (card_width + spacing))


def gallery_view_after_asset_reload(current_view: str, selected_path: str = "") -> str:
    return "loupe" if current_view == "loupe" and selected_path else "grid"


def sidebar_item_value(name: str, value: Optional[str] = None, active: bool = False) -> str:
    del active
    return value if value is not None else name


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


def _remove_widget(widget: Optional[QWidget]) -> None:
    if widget is None:
        return
    parent = widget.parentWidget()
    if parent and parent.layout():
        parent.layout().removeWidget(widget)
    widget.hide()
    widget.deleteLater()


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


def _format_project_time(value: str) -> str:
    if not value:
        return "未知时间"
    try:
        parsed = DateTime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%Y.%m.%d %H:%M")


def _load_oriented_pixmap(path: str) -> QPixmap:
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGBA")
            data = image.tobytes("raw", "RGBA")
            qimage = QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qimage.copy())
    except Exception:
        return QPixmap(path)


# ── async thumbnail loader ─────────────────────────────────────────────────────

class ThumbSignals(QObject):
    loaded = pyqtSignal(str, QPixmap)


class ThumbLoader(QRunnable):
    """Load & scale a single image thumbnail in a worker thread."""

    def __init__(self, path: str, width: int, height: int, index: int, cache_path: str = "") -> None:
        super().__init__()
        self.path   = path
        self.width  = width
        self.height = height
        self.index  = index
        self.cache_path = cache_path
        self.signals = ThumbSignals()

    def run(self) -> None:
        px = QPixmap(self.cache_path) if self.cache_path else QPixmap()
        if px.isNull():
            px = _load_oriented_pixmap(self.path)
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


class ThumbnailPreparationSignals(QObject):
    progress = pyqtSignal(object)
    finished = pyqtSignal(object)


class ThumbnailPreparationWorker(QRunnable):
    """Prepare persistent thumbnails for one library without blocking the UI."""

    def __init__(self, library_path: str) -> None:
        super().__init__()
        self.library_path = library_path
        self.signals = ThumbnailPreparationSignals()

    def run(self) -> None:
        store = LibraryStore.open(self.library_path)
        try:
            result = store.ensure_thumbnail_cache(self.signals.progress.emit)
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.finished.emit(exc)
        finally:
            store.close()


class ThumbnailCleanupWorker(QRunnable):
    """Delete thumbnail caches for libraries that have not been opened recently."""

    def __init__(self, index_path: str, retention_days: int) -> None:
        super().__init__()
        self.index_path = index_path
        self.retention_days = retention_days

    def run(self) -> None:
        index = LibraryProjectIndex(self.index_path)
        try:
            index.prune_stale_thumbnail_caches(self.retention_days)
        finally:
            index.close()


class FullImageLoader(QRunnable):
    """Load an original-resolution pixmap for loupe browsing."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.signals = ThumbSignals()

    def run(self) -> None:
        self.signals.loaded.emit(self.path, _load_oriented_pixmap(self.path))


class GallerySettingsDialog(QDialog):
    """App-level gallery settings."""

    def __init__(self, settings: TempusLoomSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("图库设置")
        self.setModal(True)
        self.setFixedWidth(560)
        self.setStyleSheet(
            f"QDialog{{background:{C_BG_PANEL};}}"
            f"QLabel{{color:{C_TEXT_1}; font-size:12px;}}"
            f"QLineEdit{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:8px;}}"
            f"QSpinBox{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:8px;}}"
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_1}; border:none; border-radius:6px;"
            f"padding:8px 12px;}}"
            f"QPushButton:hover{{background:#383838;}}"
            f"QDialogButtonBox QPushButton{{min-width:84px;}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = _make_label("图库项目保存位置", "thumbName")
        title.setStyleSheet(f"color:{C_TEXT_1}; font-size:15px; font-weight:700;")
        layout.addWidget(title)

        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        self._path_edit = QLineEdit(str(settings.project_root))
        browse_btn = QPushButton("选择...")
        browse_btn.clicked.connect(self._browse_project_root)
        path_layout.addWidget(self._path_edit, 1)
        path_layout.addWidget(browse_btn)
        layout.addWidget(path_row)

        hint = _make_label("切换保存位置时，会迁移旧目录下的图库项目和索引记录。", "gridInfo")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{C_TEXT_3};")
        layout.addWidget(hint)

        retention_title = _make_label("缩略图缓存", "thumbName")
        retention_title.setStyleSheet(f"color:{C_TEXT_1}; font-size:15px; font-weight:700; margin-top:8px;")
        layout.addWidget(retention_title)

        retention_row = QWidget()
        retention_layout = QHBoxLayout(retention_row)
        retention_layout.setContentsMargins(0, 0, 0, 0)
        retention_layout.setSpacing(8)
        retention_layout.addWidget(_make_label("自动清理超过", "gridInfo"))
        self._retention_spin = QSpinBox()
        self._retention_spin.setRange(1, 365)
        self._retention_spin.setValue(settings.thumbnail_cache_retention_days)
        retention_layout.addWidget(self._retention_spin)
        retention_layout.addWidget(_make_label("天未打开图库的缩略图缓存", "gridInfo"), 1)
        layout.addWidget(retention_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_project_root(self) -> Path:
        return Path(self._path_edit.text()).expanduser().resolve()

    def selected_retention_days(self) -> int:
        return int(self._retention_spin.value())

    def _browse_project_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择图库项目保存位置", self._path_edit.text(), QFileDialog.Option.ShowDirsOnly)
        if folder:
            self._path_edit.setText(folder)


class GalleryImportPickerDialog(QDialog):
    """Pick image files and folders in one dialog for quick gallery imports."""

    def __init__(self, start_dir: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加图片或文件夹到图库")
        self.setModal(True)
        self.resize(760, 520)
        self.setStyleSheet(
            f"QDialog{{background:{C_BG_PANEL};}}"
            f"QTreeView{{background:{C_BG_APP}; color:{C_TEXT_1}; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:4px;}}"
            f"QTreeView::item:selected{{background:{C_BG_ACTIVE}; color:{C_TEXT_1};}}"
            f"QLabel{{color:{C_TEXT_2};}}"
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_1}; border:none; border-radius:6px;"
            f"padding:8px 12px;}}"
            f"QPushButton:hover{{background:#383838;}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = _make_label("选择一个或多个图片文件，也可以直接选择文件夹。", "gridInfo")
        layout.addWidget(hint)

        self._model = QFileSystemModel(self)
        self._model.setRootPath(str(start_dir))
        self._model.setNameFilters(["*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.webp", "*.bmp"])
        self._model.setNameFilterDisables(False)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(str(start_dir)))
        self._tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self._tree.setAnimated(False)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for column in range(1, 4):
            self._tree.hideColumn(column)
        layout.addWidget(self._tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Open)
        open_btn = buttons.button(QDialogButtonBox.StandardButton.Open)
        if open_btn:
            open_btn.setText("添加")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_paths(self) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()
        for index in self._tree.selectionModel().selectedRows(0):
            path = self._model.filePath(index)
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
        return paths


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

    THUMB_W, THUMB_H = gallery_thumbnail_frame_size()
    CARD_W = THUMB_W

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
        self.setFixedWidth(self.CARD_W)
        self._setup_ui()

    # ── build ──────────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.setLayout(layout)

        self._img_label = QLabel()
        self._img_label.setFixedSize(self.THUMB_W, self.THUMB_H)
        self._img_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet(
            f"border-radius: 8px; background: {C_BG_ITEM};"
        )
        layout.addWidget(self._img_label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        name = Path(self.path).name if self.path else "未命名图片"
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
        px = _placeholder_thumb(self.THUMB_W, self.THUMB_H, self.index)
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
        self._img_label.setFixedSize(self.THUMB_W, self.THUMB_H)

    def set_pixmap(self, px: QPixmap) -> None:
        """Called from main thread with the loaded pixmap."""
        px = px.scaled(
            self.THUMB_W,
            self.THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if px.width() > self.THUMB_W or px.height() > self.THUMB_H:
            x = (px.width()  - self.THUMB_W) // 2
            y = (px.height() - self.THUMB_H) // 2
            px = px.copy(x, y, self.THUMB_W, self.THUMB_H)
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


class AddThumbnailCard(QWidget):
    """Grid entry for adding images or folders to the active library."""

    clicked = pyqtSignal()
    THUMB_W = ThumbnailCard.THUMB_W
    THUMB_H = ThumbnailCard.THUMB_H
    CARD_W = ThumbnailCard.CARD_W

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(self.CARD_W)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        plus = QLabel("+")
        plus.setFixedSize(self.THUMB_W, self.THUMB_H)
        plus.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setStyleSheet(
            f"border:1px dashed {C_BORDER}; border-radius:8px; background:{C_BG_ITEM};"
            f"color:{C_TEXT_3}; font-size:48px; font-weight:200;"
        )
        layout.addWidget(plus)

        label = _make_label("添加图片", "thumbName")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        self.clicked.emit()


class LibraryProjectCard(QWidget):
    """Single local library project shown on the gallery start page."""

    opened = pyqtSignal(str)
    menu_requested = pyqtSignal(str, object)
    CARD_W = 260
    CARD_H = 260
    COVER_W = 260
    COVER_H = 168

    def __init__(self, project: LibraryProject, index: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._project = project
        self._index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setStyleSheet(
            f"QWidget{{background:#23272d; border:1px solid {C_BORDER}; border-radius:4px;}}"
            f"QWidget:hover{{border:1px solid {C_PRIMARY};}}"
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._cover = QLabel()
        self._cover.setFixedSize(self.COVER_W, self.COVER_H)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setStyleSheet("border:none; border-radius:0; background:#0d0d0d;")
        layout.addWidget(self._cover)

        body = QWidget()
        body.setStyleSheet("background:transparent; border:none;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 12)
        body_layout.setSpacing(4)

        title = _make_label(self._project.name, "thumbName")
        title.setStyleSheet(f"background:transparent; border:none; color:{C_TEXT_1}; font-size:14px; font-weight:700;")
        body_layout.addWidget(title)

        created = _make_label(f"创建于{_format_project_time(self._project.created_at)}", "gridInfo")
        created.setStyleSheet(f"background:transparent; border:none; color:{C_TEXT_3}; font-size:12px;")
        body_layout.addWidget(created)

        updated = _make_label(f"更新于{_format_project_time(self._project.updated_at)}", "gridInfo")
        updated.setStyleSheet(f"background:transparent; border:none; color:{C_TEXT_3}; font-size:12px;")
        body_layout.addWidget(updated)

        body_layout.addStretch()
        layout.addWidget(body, 1)

        self._set_cover()

    def _set_cover(self) -> None:
        cover_paths = list(self._project.cover_paths) or ([self._project.cover_path] if self._project.cover_path else [])
        canvas = QPixmap(self.COVER_W, self.COVER_H)
        canvas.fill(QColor("#0d0d0d"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not cover_paths:
            painter.drawPixmap(0, 0, _placeholder_thumb(self.COVER_W, self.COVER_H, self._index))
        else:
            for slot, rect in enumerate(self._cover_rects(len(cover_paths))):
                pixmap = _load_oriented_pixmap(cover_paths[slot])
                if pixmap.isNull():
                    pixmap = _placeholder_thumb(rect.width(), rect.height(), self._index + slot)
                else:
                    pixmap = pixmap.scaled(
                        rect.width(),
                        rect.height(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    pixmap = pixmap.copy(
                        max(0, (pixmap.width() - rect.width()) // 2),
                        max(0, (pixmap.height() - rect.height()) // 2),
                        rect.width(),
                        rect.height(),
                    )
                painter.drawPixmap(rect, pixmap)

        badge = f"共{self._project.image_count}张"
        metrics = painter.fontMetrics()
        badge_w = metrics.horizontalAdvance(badge) + 18
        badge_h = 24
        badge_x = 10
        badge_y = self.COVER_H - badge_h - 10
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRect(badge_x, badge_y, badge_w, badge_h)
        painter.setPen(QColor(C_TEXT_1))
        painter.drawText(badge_x + 9, badge_y, badge_w - 18, badge_h, Qt.AlignmentFlag.AlignVCenter, badge)
        painter.end()
        self._cover.setPixmap(canvas)

    def _cover_rects(self, count: int) -> list:
        if count <= 1:
            return [self._cover.rect()]
        if count == 2:
            half = self.COVER_W // 2
            return [
                self._cover.rect().adjusted(0, 0, -half, 0),
                self._cover.rect().adjusted(half, 0, 0, 0),
            ]
        left_w = int(self.COVER_W * 0.62)
        right_w = self.COVER_W - left_w
        if count == 3:
            return [
                self._cover.rect().adjusted(0, 0, -right_w, 0),
                self._cover.rect().adjusted(left_w, 0, 0, -(self.COVER_H // 2)),
                self._cover.rect().adjusted(left_w, self.COVER_H // 2, 0, 0),
            ]
        return [
            self._cover.rect().adjusted(0, 0, -right_w, 0),
            self._cover.rect().adjusted(left_w, 0, 0, -(self.COVER_H * 2 // 3)),
            self._cover.rect().adjusted(left_w, self.COVER_H // 3, 0, -(self.COVER_H // 3)),
            self._cover.rect().adjusted(left_w, self.COVER_H * 2 // 3, 0, 0),
        ]

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.RightButton
            or event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.menu_requested.emit(self._project.library_path, event.globalPosition().toPoint())
            return
        self.opened.emit(self._project.library_path)

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self.opened.emit(self._project.library_path)


class NewLibraryProjectCard(QWidget):
    """Create-library entry shown before registered library projects."""

    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(LibraryProjectCard.CARD_W, LibraryProjectCard.CARD_H)
        self.setStyleSheet(
            f"QWidget{{background:#0d0d0d; border:1px solid #3a3a3a; border-radius:4px;}}"
            f"QWidget:hover{{border:1px solid {C_PRIMARY};}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        plus = QLabel("+")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setStyleSheet("background:transparent; border:none; color:#8a8a8a; font-size:56px; font-weight:200;")
        layout.addWidget(plus)

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        self.clicked.emit()


class LibraryProjectGrid(QScrollArea):
    """Start page listing local library projects."""

    create_requested = pyqtSignal()
    project_opened = pyqtSignal(str)
    project_menu_requested = pyqtSignal(str, object)

    COLUMNS = 5

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridArea")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cards: list[LibraryProjectCard] = []

        self._container = QWidget()
        self._container.setObjectName("gridArea")
        self._layout = QGridLayout(self._container)
        self._layout.setContentsMargins(28, 20, 28, 20)
        self._layout.setHorizontalSpacing(18)
        self._layout.setVerticalSpacing(18)
        for col in range(self.COLUMNS):
            self._layout.setColumnMinimumWidth(col, LibraryProjectCard.CARD_W)
            self._layout.setColumnStretch(col, 0)
        self._layout.setColumnStretch(self.COLUMNS, 1)
        self._layout.setRowStretch(999, 1)
        self.setWidget(self._container)

    def load_projects(self, projects: list[LibraryProject]) -> None:
        self._clear()

        create_card = NewLibraryProjectCard()
        create_card.clicked.connect(self.create_requested.emit)
        self._layout.addWidget(create_card, 0, 0)

        for idx, project in enumerate(projects):
            row, col = divmod(idx + 1, self.COLUMNS)
            card = LibraryProjectCard(project, idx)
            card.opened.connect(self.project_opened.emit)
            card.menu_requested.connect(self.project_menu_requested.emit)
            self._cards.append(card)
            self._layout.addWidget(card, row, col)
        last_row = len(projects) // self.COLUMNS
        self._layout.setRowStretch(last_row + 1, 1)

    def _clear(self) -> None:
        for card in self._cards:
            _remove_widget(card)
        self._cards.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()


# ── top bar ────────────────────────────────────────────────────────────────────

class GalleryTopBar(QWidget):
    """Navigation bar at the very top (h=48)."""

    mode_switched = pyqtSignal(str)   # "gallery" | "editor"
    tab_changed   = pyqtSignal(str)   # "图库" | "最近" | "收藏"
    create_library_requested = pyqtSignal()
    open_library_requested = pyqtSignal()
    add_folder_requested = pyqtSignal()
    add_images_requested = pyqtSignal()
    settings_requested = pyqtSignal()

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

        layout.addWidget(self._build_file_menubar())

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
        self._search.setFixedSize(260, 32)
        layout.addWidget(self._search)
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

    def _build_file_menubar(self) -> QMenuBar:
        menubar = QMenuBar()
        menubar.setNativeMenuBar(False)
        menubar.setFixedHeight(48)
        menubar.setStyleSheet(
            f"QMenuBar{{background:transparent; color:{C_TEXT_4}; padding:0;}}"
            f"QMenuBar::item{{background:transparent; padding:16px 12px;}}"
            f"QMenuBar::item:selected{{color:{C_TEXT_1}; background:transparent;}}"
        )
        menu = menubar.addMenu("文件")
        menu.setStyleSheet(
            f"QMenu{{background:{C_BG_PANEL}; color:{C_TEXT_1};"
            f"border:1px solid {C_BORDER}; border-radius:6px; padding:4px;}}"
            f"QMenu::item{{padding:6px 20px; border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C_BG_ACTIVE}; color:{C_PRIMARY};}}"
            f"QMenu::separator{{background:{C_BORDER}; height:1px; margin:4px 8px;}}"
        )
        actions = [
            ("创建图库项目...", self.create_library_requested),
            ("打开图库项目...", self.open_library_requested),
            (None, None),
            ("添加文件夹到图库...", self.add_folder_requested),
            ("添加图片到图库...", self.add_images_requested),
            (None, None),
            ("图库设置...", self.settings_requested),
        ]
        for text, signal in actions:
            if text is None:
                menu.addSeparator()
                continue
            action = menu.addAction(text)
            action.triggered.connect(signal.emit)
        return menubar

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
                 value: Optional[str] = None,
                 active: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._name   = name
        self._value = sidebar_item_value(name, value=value, active=active)
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
        self.clicked.emit(self._value)


class GallerySidebar(QWidget):
    """Left sidebar: library list + tags (w=200)."""

    folder_selected = pyqtSignal(str)
    tag_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        self._active_library_path = ""
        self._active_tag = ""
        self._library_items: dict[str, FolderItem] = {}
        self._tag_items: dict[str, FolderItem] = {}
        self._library_list_layout: Optional[QVBoxLayout] = None
        self._tag_list_layout: Optional[QVBoxLayout] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        layout.addWidget(_make_label("图库", "sideSection"))
        layout.addSpacing(4)

        library_list = QWidget()
        self._library_list_layout = QVBoxLayout(library_list)
        self._library_list_layout.setContentsMargins(0, 0, 0, 0)
        self._library_list_layout.setSpacing(4)
        layout.addWidget(library_list)

        layout.addSpacing(8)
        layout.addWidget(HLine())
        layout.addSpacing(8)

        layout.addWidget(_make_label("标签", "sideSection"))
        layout.addSpacing(4)

        tag_list = QWidget()
        self._tag_list_layout = QVBoxLayout(tag_list)
        self._tag_list_layout.setContentsMargins(0, 0, 0, 0)
        self._tag_list_layout.setSpacing(4)
        layout.addWidget(tag_list)

        layout.addStretch()

    def _on_library_clicked(self, library_path: str) -> None:
        old = self._library_items.get(self._active_library_path)
        if old:
            old.set_active(False)
        self._active_library_path = library_path
        if library_path in self._library_items:
            self._library_items[library_path].set_active(True)
        self.folder_selected.emit(library_path)

    def _on_tag_clicked(self, name: str) -> None:
        old = self._tag_items.get(self._active_tag)
        if old:
            old.set_active(False)
        self._active_tag = name
        if name in self._tag_items:
            self._tag_items[name].set_active(True)
        self.tag_selected.emit(name)

    def set_libraries(self, projects: list[LibraryProject], active_library_path: str = "") -> None:
        if self._library_list_layout is None:
            return
        for item in self._library_items.values():
            _remove_widget(item)
        self._library_items.clear()
        self._active_library_path = active_library_path
        for project in projects:
            active = project.library_path == active_library_path
            icon_color = C_PRIMARY if active else C_TEXT_4
            item = FolderItem(
                _folder_icon(icon_color, 16),
                project.name,
                str(project.image_count),
                value=project.library_path,
                active=active,
            )
            item.clicked.connect(self._on_library_clicked)
            self._library_items[project.library_path] = item
            self._library_list_layout.addWidget(item)

    def set_tags(self, tags: list[tuple[str, str]]) -> None:
        if self._tag_list_layout is None:
            return
        for item in self._tag_items.values():
            _remove_widget(item)
        self._tag_items.clear()
        for name, count in tags:
            active = name == self._active_tag
            icon_color = C_PRIMARY if active else C_TEXT_4
            item = FolderItem(_tag_icon(icon_color, 14), name, count, active=active)
            item.clicked.connect(self._on_tag_clicked)
            self._tag_items[name] = item
            self._tag_list_layout.addWidget(item)
        if self._active_tag not in self._tag_items:
            self._active_tag = ""


# ── grid toolbar ───────────────────────────────────────────────────────────────

class GridToolbar(QWidget):
    """Bar above the thumbnail grid (h=40)."""

    sort_clicked   = pyqtSignal()
    filter_clicked = pyqtSignal()
    view_clicked   = pyqtSignal()
    rating_filter_changed = pyqtSignal(str, int)
    back_to_projects_clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridToolbar")
        self.setFixedHeight(40)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self._info_label = _make_label("图库项目  ·  0 张图片", "gridInfo")
        layout.addWidget(self._info_label)
        layout.addStretch()

        self._back_btn = _make_chip("返回所有图库")
        self._back_btn.clicked.connect(self.back_to_projects_clicked.emit)
        self._back_btn.hide()
        sort_btn   = _make_chip("排序 ▾")
        self._filter_btn = _make_chip("全部星级 ▾")
        view_btn   = _make_chip("⊞")
        sort_btn.clicked.connect(self.sort_clicked.emit)
        self._filter_btn.clicked.connect(self._open_filter_menu)
        view_btn.clicked.connect(self.view_clicked.emit)
        layout.addWidget(self._back_btn)
        layout.addWidget(sort_btn)
        layout.addWidget(self._filter_btn)
        layout.addWidget(view_btn)

    def update_info(self, folder: str, count: int) -> None:
        self._info_label.setText(f"{folder}  ·  {count} 张图片")

    def set_info_text(self, text: str) -> None:
        self._info_label.setText(text)

    def set_project_browser_mode(self, is_project_browser: bool) -> None:
        self._back_btn.setVisible(not is_project_browser)

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
    tags_changed = pyqtSignal(list)
    tag_selected = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("infoPanel")
        self.setFixedWidth(260)
        self._current_path: str = ""
        self._rating = 0
        self._updating_tags = False
        self._global_tag_items: dict[str, FolderItem] = {}
        self._global_tag_layout: Optional[QVBoxLayout] = None
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
        self._title = _make_label("—", "infoTitle")
        layout.addWidget(self._title)

        self._rating_widget = StarRatingWidget(0)
        self._rating_widget.rating_changed.connect(self.rating_changed.emit)
        layout.addWidget(self._rating_widget)

        layout.addWidget(_make_label("标签", "infoLabel"))
        self._tag_edit = QLineEdit()
        self._tag_edit.setObjectName("searchBox")
        self._tag_edit.setPlaceholderText("输入标签，用逗号分隔")
        self._tag_edit.editingFinished.connect(self._emit_tags_changed)
        layout.addWidget(self._tag_edit)

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

        layout.addWidget(_make_label("按标签浏览", "infoActTitle"))
        self._global_tag_widget = QWidget()
        self._global_tag_layout = QVBoxLayout(self._global_tag_widget)
        self._global_tag_layout.setContentsMargins(0, 0, 0, 0)
        self._global_tag_layout.setSpacing(4)
        layout.addWidget(self._global_tag_widget)

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
    def update_info(
        self,
        path: str,
        pixmap: Optional[QPixmap] = None,
        *,
        rating: int = 0,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Populate panel with metadata from *path*."""
        self._current_path = path
        self._rating = max(0, min(5, int(rating)))
        self._rating_widget.set_rating(self._rating)
        self._updating_tags = True
        self._tag_edit.setText("，".join(tags or []))
        self._updating_tags = False
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
            "尺寸":   "—",
            "拍摄日期": "—",
            "相机":   "—",
            "光圈":   "—",
            "ISO":   "—",
            "焦距":   "—",
            "快门":   "—",
        }
        for (lbl_k, lbl_v), key in zip(self._exif_rows, keys):
            lbl_v.setText(exif_values.get(key, defaults.get(key, "—")))

    def set_global_tags(self, tags: list[tuple[str, str]], active_tag: str = "") -> None:
        if self._global_tag_layout is None:
            return
        for item in self._global_tag_items.values():
            _remove_widget(item)
        self._global_tag_items.clear()
        for name, count in tags:
            active = name == active_tag
            icon_color = C_PRIMARY if active else C_TEXT_4
            item = FolderItem(_tag_icon(icon_color, 14), name, count, active=active)
            item.clicked.connect(self.tag_selected.emit)
            self._global_tag_items[name] = item
            self._global_tag_layout.addWidget(item)
        self._global_tag_widget.setVisible(bool(tags))

    def _emit_tags_changed(self) -> None:
        if self._updating_tags:
            return
        text = self._tag_edit.text()
        tags: list[str] = []
        seen: set[str] = set()
        for chunk in text.replace("，", ",").split(","):
            name = chunk.strip()
            if name and name not in seen:
                seen.add(name)
                tags.append(name)
        self.tags_changed.emit(tags)

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
    """Scrollable responsive thumbnail grid."""

    image_selected = pyqtSignal(str, QPixmap)   # path, pixmap
    image_activated = pyqtSignal(str)
    rating_changed = pyqtSignal(str, int)
    add_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridArea")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._cards: list[ThumbnailCard] = []
        self._add_card: Optional[AddThumbnailCard] = None
        self._selected_path: str = ""
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._assets_by_path: dict[str, LibraryAsset] = {}
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)
        self._thumbnail_paths: dict[str, str] = {}
        self._columns = 1

        self._container = QWidget()
        self._container.setObjectName("gridArea")
        self._grid_layout = QGridLayout(self._container)
        horizontal_gap, vertical_gap = gallery_thumbnail_grid_spacing()
        self._grid_layout.setContentsMargins(28, 28, 28, 28)
        self._grid_layout.setHorizontalSpacing(horizontal_gap)
        self._grid_layout.setVerticalSpacing(vertical_gap)
        self.setWidget(self._container)
        self._update_columns()

    # ── loading ────────────────────────────────────────────────────────────────
    def load_images(self, paths: list[str]) -> None:
        self.load_assets([self._asset_from_path(path) for path in paths])

    def load_assets(self, assets: list[LibraryAsset], thumbnail_paths: Optional[dict[str, str]] = None) -> None:
        # clear
        for card in self._cards:
            _remove_widget(card)
        self._cards.clear()
        if self._add_card:
            _remove_widget(self._add_card)
            self._add_card = None
        self._pixmap_cache.clear()
        self._thumbnail_paths = thumbnail_paths or {}
        self._assets_by_path = {asset.path: asset for asset in assets}
        self._update_columns()

        self._add_card = AddThumbnailCard(self._container)
        self._add_card.clicked.connect(lambda: self.add_requested.emit(self._add_card))
        self._grid_layout.addWidget(self._add_card, 0, 0)

        if not assets:
            self._selected_path = ""
            return

        for idx, asset in enumerate(assets):
            row, col = divmod(idx + 1, self._columns)
            selected = (idx == 0)
            card = ThumbnailCard(asset.path, idx, selected, rating=asset.rating, missing=asset.missing, parent=self._container)
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
            loader = ThumbLoader(
                asset.path,
                ThumbnailCard.THUMB_W,
                ThumbnailCard.THUMB_H,
                idx,
                self._thumbnail_paths.get(asset.path, ""),
            )
            loader.signals.loaded.connect(self._on_thumb_loaded)
            self._pool.start(loader)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._update_columns():
            self._relayout_cards()

    def _update_columns(self) -> bool:
        width = self.viewport().width() or self.width()
        columns = gallery_thumbnail_grid_columns(width)
        if columns == self._columns:
            return False
        old_columns = self._columns
        self._columns = columns
        self._configure_columns(max(old_columns, columns))
        return True

    def _configure_columns(self, previous_columns: int = 0) -> None:
        for col in range(max(previous_columns + 1, self._columns + 2)):
            if col < self._columns:
                self._grid_layout.setColumnMinimumWidth(col, ThumbnailCard.CARD_W)
                self._grid_layout.setColumnStretch(col, 0)
            elif col == self._columns:
                self._grid_layout.setColumnMinimumWidth(col, 0)
                self._grid_layout.setColumnStretch(col, 1)
            else:
                self._grid_layout.setColumnMinimumWidth(col, 0)
                self._grid_layout.setColumnStretch(col, 0)

    def _relayout_cards(self) -> None:
        if self._add_card:
            self._grid_layout.addWidget(self._add_card, 0, 0)
        for idx, card in enumerate(self._cards):
            row, col = divmod(idx + 1, self._columns)
            self._grid_layout.addWidget(card, row, col)

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

    def set_image(self, path: str, pixmap: Optional[QPixmap] = None) -> None:
        self._path = path
        self._title.setText(Path(path).name if path else "—")
        source = pixmap if pixmap and not pixmap.isNull() else _load_oriented_pixmap(path)
        self._pixmap = source
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
    add_requested = pyqtSignal(object)

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

    def load_assets(
        self,
        assets: list[LibraryAsset],
        selected_path: str = "",
        thumbnail_paths: Optional[dict[str, str]] = None,
        show_add_slot: bool = True,
    ) -> None:
        for button in self._buttons.values():
            button.setParent(None)
        self._buttons.clear()
        self._selected_path = selected_path
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        thumbnail_paths = thumbnail_paths or {}
        for asset in assets:
            btn = QPushButton()
            btn.setFixedSize(88, 68)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setToolTip(asset.file_name)
            btn.clicked.connect(lambda _checked=False, p=asset.path: self.image_selected.emit(p))
            pixmap = QPixmap(thumbnail_paths.get(asset.path, ""))
            if pixmap.isNull():
                pixmap = _load_oriented_pixmap(asset.path)
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
        if show_add_slot:
            add_btn = QPushButton("+")
            add_btn.setFixedSize(88, 68)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            add_btn.setToolTip("添加图片或文件夹到图库")
            add_btn.clicked.connect(lambda _checked=False: self.add_requested.emit(add_btn))
            add_btn.setStyleSheet(
                f"QPushButton{{background:{C_BG_ITEM}; border:1px dashed {C_BORDER};"
                f"border-radius:6px; color:{C_TEXT_3}; font-size:28px; padding:0;}}"
                f"QPushButton:hover{{border-color:{C_PRIMARY}; color:{C_TEXT_1};}}"
            )
            self._layout.addWidget(add_btn)
        self._layout.addStretch()
        self.set_selected(selected_path)

    def set_selected(self, path: str) -> None:
        self._selected_path = path
        for button_path, button in self._buttons.items():
            border = f"2px solid {C_PRIMARY}" if button_path == path else f"1px solid {C_BORDER}"
            button.setStyleSheet(f"QPushButton{{background:{C_BG_ITEM}; border:{border}; border-radius:6px; padding:0;}}")


class GalleryActionBar(QWidget):
    """Loupe-mode controls for rating, tags, and filtering."""

    rating_changed = pyqtSignal(int)
    tags_changed = pyqtSignal(list)
    rating_filter_changed = pyqtSignal(str, int)
    tag_filter_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gridToolbar")
        self.setFixedHeight(46)
        self._updating_tags = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        layout.addWidget(_make_label("评分", "gridInfo"))
        self._rating_widget = StarRatingWidget(0)
        self._rating_widget.rating_changed.connect(self.rating_changed.emit)
        layout.addWidget(self._rating_widget)

        layout.addWidget(_make_label("标签", "gridInfo"))
        self._tag_edit = QLineEdit()
        self._tag_edit.setObjectName("searchBox")
        self._tag_edit.setPlaceholderText("输入标签，用逗号分隔")
        self._tag_edit.setFixedWidth(220)
        self._tag_edit.editingFinished.connect(self._emit_tags_changed)
        layout.addWidget(self._tag_edit)

        layout.addStretch()

        self._rating_filter_btn = _make_chip("全部星级 ▾")
        self._rating_filter_btn.clicked.connect(self._open_rating_filter_menu)
        layout.addWidget(self._rating_filter_btn)

        self._tag_filter = QComboBox()
        self._tag_filter.setFixedWidth(160)
        self._tag_filter.setStyleSheet(
            f"QComboBox{{background:{C_BG_ITEM}; color:{C_TEXT_2}; border:none;"
            f"border-radius:6px; padding:4px 8px;}}"
        )
        self._tag_filter.currentIndexChanged.connect(self._emit_tag_filter_changed)
        layout.addWidget(self._tag_filter)

    def set_current_metadata(self, rating: int, tags: list[str]) -> None:
        self._rating_widget.set_rating(rating)
        self._updating_tags = True
        self._tag_edit.setText("，".join(tags))
        self._updating_tags = False

    def set_rating_filter(self, mode: str, rating: int) -> None:
        if mode == "exact":
            self._rating_filter_btn.setText(f"正好 {rating} 星 ▾")
        elif mode == "minimum" and rating > 0:
            self._rating_filter_btn.setText(f"{rating} 星及以上 ▾")
        else:
            self._rating_filter_btn.setText("全部星级 ▾")

    def set_tag_options(self, tags: list[tuple[str, str]], active_tag: str = "") -> None:
        self._tag_filter.blockSignals(True)
        self._tag_filter.clear()
        self._tag_filter.addItem("全部标签", "")
        for name, count in tags:
            self._tag_filter.addItem(f"{name} ({count})", name)
        index = self._tag_filter.findData(active_tag)
        self._tag_filter.setCurrentIndex(index if index >= 0 else 0)
        self._tag_filter.blockSignals(False)

    def _emit_tags_changed(self) -> None:
        if self._updating_tags:
            return
        tags: list[str] = []
        seen: set[str] = set()
        for chunk in self._tag_edit.text().replace("，", ",").split(","):
            name = chunk.strip()
            if name and name not in seen:
                seen.add(name)
                tags.append(name)
        self.tags_changed.emit(tags)

    def _emit_tag_filter_changed(self) -> None:
        self.tag_filter_changed.emit(str(self._tag_filter.currentData() or ""))

    def _open_rating_filter_menu(self) -> None:
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
        menu.exec(self._rating_filter_btn.mapToGlobal(self._rating_filter_btn.rect().bottomLeft()))


# ── main gallery window ────────────────────────────────────────────────────────

class GalleryBrowser(QWidget):
    """图库浏览界面 – embedded page inside TempusLoomWindow."""

    LOUPE_PREFETCH_RADIUS = 2
    LOUPE_CACHE_LIMIT = 7

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_dir: Optional[str] = None
        self._store: Optional[LibraryStore] = None
        self._settings = TempusLoomSettings()
        self._project_index = LibraryProjectIndex()
        self._assets: list[LibraryAsset] = []
        self._asset_by_path: dict[str, LibraryAsset] = {}
        self._thumbnail_paths: dict[str, str] = {}
        self._active_folder_path: Optional[str] = None
        self._active_tag: str = ""
        self._rating_filter_mode = "all"
        self._rating_filter_value = 0
        self._search_text = ""
        self._navigator = GalleryNavigator()
        self._current_pixmap = QPixmap()
        self._full_pixmap_cache: dict[str, QPixmap] = {}
        self._full_pixmap_loading: set[str] = set()
        self._full_image_pool = QThreadPool()
        self._full_image_pool.setMaxThreadCount(2)
        self._background_pool = QThreadPool()
        self._background_pool.setMaxThreadCount(1)
        self._thumbnail_progress: Optional[QProgressDialog] = None
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._start_thumbnail_cache_cleanup()
        self._load_library_projects()

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
        self._project_grid = LibraryProjectGrid()
        self._grid = ThumbnailGrid()
        self._loupe = GalleryLoupeView()
        self._view_stack.addWidget(self._project_grid)
        self._view_stack.addWidget(self._grid)
        self._view_stack.addWidget(self._loupe)
        grid_v.addWidget(self._view_stack, 1)

        self._gallery_action_bar = GalleryActionBar()
        self._gallery_action_bar.hide()
        grid_v.addWidget(self._gallery_action_bar)

        self._filmstrip = Filmstrip()
        grid_v.addWidget(self._filmstrip)

        content_layout.addWidget(grid_container, 1)

        # info panel
        self._info_panel = InfoPanel()
        content_layout.addWidget(self._info_panel)

    def _connect_signals(self) -> None:
        self._project_grid.create_requested.connect(self._create_library_project)
        self._project_grid.project_opened.connect(self._open_registered_library)
        self._project_grid.project_menu_requested.connect(self._open_project_context_menu)
        self._sidebar.folder_selected.connect(self._on_folder_selected)
        self._sidebar.tag_selected.connect(self._on_tag_selected)
        self._info_panel.tag_selected.connect(self._on_tag_selected)
        self._grid.image_selected.connect(self._on_image_selected)
        self._grid.image_activated.connect(self._show_loupe_for_path)
        self._grid.rating_changed.connect(self._set_rating_for_path)
        self._grid.add_requested.connect(self._show_add_to_current_library_menu)
        self._grid_toolbar.back_to_projects_clicked.connect(self._load_library_projects)
        self._grid_toolbar.rating_filter_changed.connect(self._set_rating_filter)
        self._gallery_action_bar.rating_changed.connect(self._set_rating_for_selected)
        self._gallery_action_bar.tags_changed.connect(self._set_tags_for_selected)
        self._gallery_action_bar.rating_filter_changed.connect(self._set_rating_filter)
        self._gallery_action_bar.tag_filter_changed.connect(self._set_tag_filter)
        self._info_panel.rating_changed.connect(self._set_rating_for_selected)
        self._info_panel.tags_changed.connect(self._set_tags_for_selected)
        self._loupe.back_to_grid.connect(self._show_grid)
        self._filmstrip.image_selected.connect(self._select_path)
        self._filmstrip.add_requested.connect(self._show_add_to_current_library_menu)

    def _setup_shortcuts(self) -> None:
        for rating in range(0, 6):
            QShortcut(QKeySequence(str(rating)), self, lambda r=rating: self._set_rating_for_selected(r))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._select_previous_image)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._select_next_image)

    # ── public api for UnifiedTopBar ───────────────────────────────────────────
    def trigger_import(self) -> None:
        self._on_import()

    def create_library_project(self) -> None:
        self._create_library_project()

    def open_library_project(self) -> None:
        self._open_library_project()

    def add_folder_to_library(self) -> None:
        self._add_folder_to_library()

    def add_images_to_library(self) -> None:
        self._add_images_to_library()

    def open_gallery_settings(self) -> None:
        self._open_gallery_settings()

    def trigger_tab(self, name: str) -> None:
        self._on_tab_changed(name)

    def filter_by_search(self, text: str) -> None:
        self._search_text = text
        self._reload_assets()

    def current_image_paths(self) -> list[str]:
        return [asset.path for asset in self._assets] if self._assets else []

    # ── initial data ───────────────────────────────────────────────────────────
    def _load_library_projects(self) -> None:
        projects = self._project_index.list_projects()
        self._store = None
        self._assets = []
        self._asset_by_path = {}
        self._thumbnail_paths = {}
        self._navigator.set_paths([])
        self._full_pixmap_cache.clear()
        self._full_pixmap_loading.clear()
        self._project_grid.load_projects(projects)
        self._filmstrip.load_assets([], show_add_slot=False)
        self._sidebar.set_libraries(projects, "")
        tag_counts = [(name, str(count)) for name, count in self._project_index.global_tag_counts()]
        self._sidebar.set_tags(tag_counts)
        self._info_panel.set_global_tags(tag_counts, self._active_tag)
        self._grid_toolbar.set_info_text(f"图库项目  ·  {len(projects)} 个图库")
        self._grid_toolbar.set_project_browser_mode(True)
        self._gallery_action_bar.hide()
        self._view_stack.setCurrentWidget(self._project_grid)

    # ── slots ──────────────────────────────────────────────────────────────────
    def _on_import(self) -> None:
        menu = QMenu(self)
        create_action = menu.addAction("创建图库项目...")
        open_action = menu.addAction("打开图库项目...")
        menu.addSeparator()
        add_folder_action = menu.addAction("添加文件夹到图库...")
        add_images_action = menu.addAction("添加图片到图库...")
        menu.addSeparator()
        settings_action = menu.addAction("图库设置...")
        action = menu.exec(self.mapToGlobal(self.rect().topRight()))
        if action == create_action:
            self._create_library_project()
        elif action == open_action:
            self._open_library_project()
        elif action == add_folder_action:
            self._add_folder_to_library()
        elif action == add_images_action:
            self._add_images_to_library()
        elif action == settings_action:
            self._open_gallery_settings()

    def _create_library_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择初始图片文件夹", str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        default_name = Path(folder).name or "TempusLoom Library"
        name, ok = QInputDialog.getText(self, "创建图库项目", "图库名称：", text=default_name)
        if not ok or not name.strip():
            return
        library_path = self._settings.library_path_for_name(name.strip())
        try:
            self._store = LibraryStore.create(library_path, name.strip(), initial_folder=folder)
            self._project_index.register_library(self._store.library_path)
            self._prepare_thumbnails_for_current_library()
        except Exception as exc:
            QMessageBox.warning(self, "创建图库失败", str(exc))
            return
        self._current_dir = folder
        self._active_folder_path = None
        self._reload_assets()

    def _open_project_context_menu(self, library_path: str, global_pos) -> None:
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除图库")
        action = menu.exec(global_pos)
        if action == rename_action:
            self._rename_library_project(library_path)
        elif action == delete_action:
            self._delete_library_project(library_path)

    def _rename_library_project(self, library_path: str) -> None:
        try:
            store = LibraryStore.open(library_path)
            current_name = store.project_summary().name
        except Exception as exc:
            QMessageBox.warning(self, "重命名失败", str(exc))
            return
        name, ok = QInputDialog.getText(self, "重命名图库", "图库名称：", text=current_name)
        if not ok or not name.strip():
            store.close()
            return
        try:
            store.rename_project(name.strip())
        except Exception as exc:
            QMessageBox.warning(self, "重命名失败", str(exc))
        finally:
            store.close()
        self._load_library_projects()

    def _delete_library_project(self, library_path: str) -> None:
        result = QMessageBox.question(
            self,
            "删除图库",
            "从图库列表中移除这个图库项目？磁盘上的图库文件夹不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self._project_index.unregister_library(library_path)
        self._load_library_projects()

    def _open_library_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "打开图库项目", str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        try:
            self._store = LibraryStore.open(folder)
            self._project_index.register_library(self._store.library_path)
            self._prepare_thumbnails_for_current_library()
        except Exception as exc:
            QMessageBox.warning(self, "打开图库失败", str(exc))
            return
        self._active_folder_path = None
        self._reload_assets()

    def _open_registered_library(self, library_path: str) -> None:
        try:
            self._store = LibraryStore.open(library_path)
            self._project_index.register_library(self._store.library_path)
            self._prepare_thumbnails_for_current_library()
        except Exception as exc:
            QMessageBox.warning(self, "打开图库失败", str(exc))
            self._load_library_projects()
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
        self._prepare_thumbnails_for_current_library()
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
        self._prepare_thumbnails_for_current_library()
        self._reload_assets()
        QMessageBox.information(self, "导入完成", f"扫描 {result.scanned} 张，新增 {result.imported} 张，跳过 {result.skipped} 张。")

    def _show_add_to_current_library_menu(self, anchor) -> None:
        if not self._ensure_library():
            return
        dialog = GalleryImportPickerDialog(Path.home(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        files, folders = split_gallery_import_paths(dialog.selected_paths())
        if not files and not folders:
            return
        imported = skipped = scanned = 0
        for folder in folders:
            result = self._store.add_folder(folder)
            scanned += result.scanned
            imported += result.imported
            skipped += result.skipped
        if files:
            result = self._store.add_images(files)
            scanned += result.scanned
            imported += result.imported
            skipped += result.skipped
        self._prepare_thumbnails_for_current_library()
        self._active_folder_path = None
        self._reload_assets()
        QMessageBox.information(self, "导入完成", f"扫描 {scanned} 张，新增 {imported} 张，跳过 {skipped} 张。")

    def _on_tab_changed(self, tab: str) -> None:
        if gallery_tab_shows_project_browser(tab):
            self._load_library_projects()

    def _on_folder_selected(self, name: str) -> None:
        if name:
            self._open_registered_library(name)
            return
        self._active_folder_path = None
        self._active_tag = ""
        self._reload_assets()

    def _on_tag_selected(self, tag: str) -> None:
        self._active_tag = tag
        self._active_folder_path = None
        self._reload_assets()

    def _on_image_selected(self, path: str, pixmap: QPixmap) -> None:
        self._navigator.select(path)
        self._current_pixmap = pixmap
        asset = self._asset_by_path.get(path)
        tags = self._asset_tags_for_path(path)
        self._info_panel.update_info(path, pixmap, rating=asset.rating if asset else 0, tags=tags)
        self._gallery_action_bar.set_current_metadata(asset.rating if asset else 0, tags)
        self._filmstrip.set_selected(path)
        if self._view_stack.currentWidget() == self._loupe:
            self._show_loupe_image(path)

    def _set_rating_filter(self, mode: str, rating: int) -> None:
        if mode not in {"all", "minimum", "exact"}:
            mode = "all"
        self._rating_filter_mode = mode
        self._rating_filter_value = max(0, min(5, int(rating)))
        self._grid_toolbar.set_rating_filter(self._rating_filter_mode, self._rating_filter_value)
        self._gallery_action_bar.set_rating_filter(self._rating_filter_mode, self._rating_filter_value)
        self._reload_assets()

    def _set_rating_for_selected(self, rating: int) -> None:
        path = self._navigator.current_path or self._grid.selected_path()
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

    def _set_tags_for_selected(self, tags: list[str]) -> None:
        path = self._navigator.current_path or self._grid.selected_path()
        if not path:
            return
        store, asset, should_close = self._store_and_asset_for_path(path)
        if not store or not asset:
            return
        try:
            store.set_asset_tags(asset.id, tags)
        finally:
            if should_close:
                store.close()
        self._reload_assets(keep_selection=path)

    def _set_tag_filter(self, tag: str) -> None:
        self._active_tag = tag
        self._active_folder_path = None
        self._reload_assets()

    def _reload_assets(self, *, keep_selection: Optional[str] = None) -> None:
        if not self._store:
            self._load_library_projects()
            return
        current_view = "loupe" if self._view_stack.currentWidget() == self._loupe else "grid"
        exact_rating = self._rating_filter_value if self._rating_filter_mode == "exact" else None
        min_rating = self._rating_filter_value if self._rating_filter_mode == "minimum" else 0
        if self._active_tag:
            self._assets = self._project_index.query_images_by_tag(self._active_tag)
            if exact_rating is not None:
                self._assets = [asset for asset in self._assets if asset.rating == exact_rating]
            elif min_rating > 0:
                self._assets = [asset for asset in self._assets if asset.rating >= min_rating]
            if self._search_text:
                needle = self._search_text.lower()
                self._assets = [asset for asset in self._assets if needle in asset.file_name.lower()]
            label = f"标签：{self._active_tag}"
        else:
            self._assets = self._store.query_images(
                min_rating=min_rating,
                exact_rating=exact_rating,
                search=self._search_text,
                folder_path=self._active_folder_path,
            )
            label = self._store.project_summary().name if self._store else "图库"
        self._asset_by_path = {asset.path: asset for asset in self._assets}
        self._thumbnail_paths = self._cached_thumbnail_paths(self._assets)
        self._prune_full_pixmap_cache()
        preferred = keep_selection or self._navigator.current_path
        selected_path = self._navigator.set_paths([asset.path for asset in self._assets], preferred_path=preferred)
        self._grid.load_assets(self._assets, thumbnail_paths=self._thumbnail_paths)
        self._filmstrip.load_assets(self._assets, selected_path=selected_path, thumbnail_paths=self._thumbnail_paths)
        next_view = gallery_view_after_asset_reload(current_view, selected_path)
        self._gallery_action_bar.setVisible(next_view == "loupe")
        self._view_stack.setCurrentWidget(self._loupe if next_view == "loupe" else self._grid)
        if selected_path:
            self._grid.select_path(selected_path)
            if next_view == "loupe":
                self._show_loupe_image(selected_path)
        self._grid_toolbar.update_info(label, len(self._assets))
        self._grid_toolbar.set_project_browser_mode(False)
        self._gallery_action_bar.set_rating_filter(self._rating_filter_mode, self._rating_filter_value)
        self._sidebar.set_libraries(self._project_index.list_projects(), str(self._store.library_path))
        tag_counts = [(name, str(count)) for name, count in self._project_index.global_tag_counts()]
        self._sidebar.set_tags(tag_counts)
        self._info_panel.set_global_tags(tag_counts, self._active_tag)
        self._gallery_action_bar.set_tag_options(tag_counts, self._active_tag)

    def _store_and_asset_for_path(self, path: str) -> tuple[Optional[LibraryStore], Optional[LibraryAsset], bool]:
        if self._store:
            asset = self._store.get_asset_by_path(path)
            if asset:
                return self._store, asset, False
        for project in self._project_index.list_projects():
            try:
                store = LibraryStore.open(project.library_path)
            except Exception:
                continue
            asset = store.get_asset_by_path(path)
            if asset:
                return store, asset, True
            store.close()
        return None, None, False

    def _cached_thumbnail_paths(self, assets: list[LibraryAsset]) -> dict[str, str]:
        if not self._store:
            return {}
        paths: dict[str, str] = {}
        for asset in assets:
            thumb_path = self._store.thumbnail_path_for_asset(asset)
            if thumb_path.is_file():
                paths[asset.path] = str(thumb_path)
        return paths

    def _prepare_thumbnails_for_current_library(self) -> None:
        if not self._store:
            return
        assets = self._store.query_images(include_missing=False)
        if not assets:
            return
        missing = [
            asset for asset in assets
            if not self._store.thumbnail_path_for_asset(asset).is_file()
        ]
        if not missing:
            return
        self._thumbnail_progress = QProgressDialog("正在准备图库缩略图...", "后台继续", 0, len(assets), self)
        self._thumbnail_progress.setWindowTitle("准备图库")
        self._thumbnail_progress.setWindowModality(Qt.WindowModality.NonModal)
        self._thumbnail_progress.setMinimumDuration(0)
        self._thumbnail_progress.setValue(0)
        worker = ThumbnailPreparationWorker(str(self._store.library_path))
        worker.signals.progress.connect(self._on_thumbnail_prepare_progress)
        worker.signals.finished.connect(self._on_thumbnail_prepare_finished)
        self._background_pool.start(worker)

    def _on_thumbnail_prepare_progress(self, progress: ThumbnailProgress) -> None:
        if not self._thumbnail_progress:
            return
        self._thumbnail_progress.setMaximum(progress.total)
        self._thumbnail_progress.setValue(progress.done)
        self._thumbnail_progress.setLabelText(
            f"正在准备图库缩略图... {progress.done}/{progress.total}"
        )

    def _on_thumbnail_prepare_finished(self, result) -> None:
        if self._thumbnail_progress:
            self._thumbnail_progress.setValue(self._thumbnail_progress.maximum())
            self._thumbnail_progress.close()
            self._thumbnail_progress = None
        if isinstance(result, Exception):
            QMessageBox.warning(self, "准备缩略图失败", str(result))
            return
        if self._store:
            self._thumbnail_paths = self._cached_thumbnail_paths(self._assets)
            self._reload_assets(keep_selection=self._navigator.current_path)

    def _start_thumbnail_cache_cleanup(self) -> None:
        worker = ThumbnailCleanupWorker(str(self._project_index.index_path), self._settings.thumbnail_cache_retention_days)
        self._background_pool.start(worker)

    def _open_gallery_settings(self) -> None:
        dialog = GallerySettingsDialog(self._settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        old_root = self._settings.project_root
        new_root = dialog.selected_project_root()
        try:
            if old_root != new_root:
                self._settings.migrate_project_root(new_root)
                self._project_index.close()
                self._project_index = LibraryProjectIndex(self._settings.index_path)
            self._settings.set_thumbnail_cache_retention_days(dialog.selected_retention_days())
        except Exception as exc:
            QMessageBox.warning(self, "保存图库设置失败", str(exc))
            return
        self._load_library_projects()

    def _asset_tags_for_path(self, path: str) -> list[str]:
        store, asset, should_close = self._store_and_asset_for_path(path)
        if not store or not asset:
            return []
        try:
            return store.asset_tags(asset.id)
        finally:
            if should_close:
                store.close()

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

    def _show_loupe_image(self, path: str) -> None:
        cached = self._full_pixmap_cache.get(path)
        if cached and not cached.isNull():
            self._loupe.set_image(path, cached)
        else:
            self._loupe.set_image(path, QPixmap(path))
        self._prefetch_loupe_neighbors(path)

    def _prefetch_loupe_neighbors(self, path: str) -> None:
        targets = neighboring_paths(
            [asset.path for asset in self._assets],
            path,
            radius=self.LOUPE_PREFETCH_RADIUS,
        )
        for target in targets:
            if target in self._full_pixmap_cache or target in self._full_pixmap_loading:
                continue
            self._full_pixmap_loading.add(target)
            loader = FullImageLoader(target)
            loader.signals.loaded.connect(self._on_full_pixmap_loaded)
            self._full_image_pool.start(loader)
        self._prune_full_pixmap_cache(keep_paths=targets)

    def _on_full_pixmap_loaded(self, path: str, pixmap: QPixmap) -> None:
        self._full_pixmap_loading.discard(path)
        if pixmap.isNull():
            return
        self._full_pixmap_cache[path] = pixmap
        if self._view_stack.currentWidget() == self._loupe and self._navigator.current_path == path:
            self._loupe.set_image(path, pixmap)
        self._prune_full_pixmap_cache()

    def _prune_full_pixmap_cache(self, keep_paths: Optional[list[str]] = None) -> None:
        valid_paths = {asset.path for asset in self._assets}
        keep = set(keep_paths or neighboring_paths(
            [asset.path for asset in self._assets],
            self._navigator.current_path,
            radius=self.LOUPE_PREFETCH_RADIUS,
        ))
        for cached_path in list(self._full_pixmap_cache):
            if cached_path not in valid_paths:
                self._full_pixmap_cache.pop(cached_path, None)
        if len(self._full_pixmap_cache) <= self.LOUPE_CACHE_LIMIT:
            return
        for cached_path in list(self._full_pixmap_cache):
            if cached_path in keep:
                continue
            self._full_pixmap_cache.pop(cached_path, None)
            if len(self._full_pixmap_cache) <= self.LOUPE_CACHE_LIMIT:
                break

    def _show_loupe_for_path(self, path: str) -> None:
        if path:
            self._select_path(path)
            self._gallery_action_bar.show()
            self._view_stack.setCurrentWidget(self._loupe)
            self._show_loupe_image(path)

    def _show_grid(self) -> None:
        self._gallery_action_bar.hide()
        self._view_stack.setCurrentWidget(self._grid)
