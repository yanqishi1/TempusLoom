#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TempusLoom – application entry point.

Architecture
────────────
TempusLoomWindow (QMainWindow)
  ├── UnifiedTopBar (QWidget, h=48, never animated)
  │     ├── [shared]  logo · divider · mode-switch
  │     ├── middle_stack  idx-0: gallery nav-tabs  │  idx-1: editor menu items
  │     ├── stretch
  │     └── right_stack   idx-0: search+import+avatar  │  idx-1: undo/redo+save+export+avatar
  └── content_stack (QStackedWidget, cross-fades)
        ├── idx-0  GalleryBrowser  (content only, no topbar)
        └── idx-1  MainEditorWindow (content only, no topbar)

Cross-fade: fade-out 160 ms (InCubic) → swap page → fade-in 220 ms (OutCubic)
The topbar is outside the stacked widget so it is NEVER part of the animation.

Usage:
    python src/main.py            # start on gallery screen (default)
    python src/main.py --editor   # start on editor screen
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtCore import (
    Qt, QSize, QPointF, QPropertyAnimation, QEasingCurve, QAbstractAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QBrush, QPen,
    QPixmap, QFont, QLinearGradient, QShortcut, QKeySequence, QIcon,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QSizePolicy, QGraphicsOpacityEffect, QMenu,
)

from tempusloom.ui.styling        import apply_dark_theme
from tempusloom.ui.gallery_browser import GalleryBrowser
from tempusloom.ui.editor_window   import MainEditorWindow
from tempusloom.ui.editor_icons    import icon_pixmap


# ── design tokens (must match styling.py) ─────────────────────────────────────
C_PRIMARY    = "#3370FF"
C_PRIMARY_H  = "#5B8FF9"
C_BG_APP     = "#181818"
C_BG_TOPBAR  = "#252525"
C_BG_PANEL   = "#1e1e1e"
C_BG_ITEM    = "#2c2c2c"
C_BG_ACTIVE  = "#1a3060"
C_BORDER     = "#333333"
C_TEXT_1     = "#e8e8e8"
C_TEXT_2     = "#aaaaaa"
C_TEXT_3     = "#888888"
C_TEXT_4     = "#777777"
C_WHITE      = "#ffffff"

# ── animation parameters ───────────────────────────────────────────────────────
_FADE_OUT_MS = 160
_FADE_IN_MS  = 220
_EASE_OUT    = QEasingCurve.Type.InCubic
_EASE_IN     = QEasingCurve.Type.OutCubic

_PAGE_GALLERY = 0
_PAGE_EDITOR  = 1


# ── tiny helpers ───────────────────────────────────────────────────────────────

def _logo_pixmap(size: int = 24) -> QPixmap:
    px = QPixmap(size, size)
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
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "T")
    p.end()
    return px


def _avatar_pixmap(size: int = 28) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(C_BG_ACTIVE)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.drawPixmap(7, 7, icon_pixmap("user", 14, "#6366F1"))
    p.end()
    return px


def _vline() -> QFrame:
    line = QFrame()
    line.setFixedWidth(1)
    line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    line.setStyleSheet(f"background:{C_BORDER}; border:none;")
    return line


def _qicon(name: str, size: int, color: str) -> QIcon:
    return QIcon(icon_pixmap(name, size, color))


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED TOP BAR
# ══════════════════════════════════════════════════════════════════════════════

class UnifiedTopBar(QWidget):
    """
    Single 48 px navigation bar shared by both modes.

    Structure
    ─────────
    [logo | divider | mode-switch] [middle_stack] ──stretch── [right_stack]

    middle_stack  idx-0: gallery nav-tabs (图库 / 最近 / 收藏)
                  idx-1: editor  menus   (文件 / 编辑 / 视图 / 插件)

    right_stack   idx-0: search-box + import-btn + avatar
                  idx-1: undo + redo | save + export + avatar
    """

    # ── signals ───────────────────────────────────────────────────────────────
    mode_switched          = pyqtSignal(str)   # "gallery" | "editor"

    gallery_tab_changed    = pyqtSignal(str)   # "图库" | "最近" | "收藏"
    gallery_import_clicked = pyqtSignal()
    gallery_search_changed = pyqtSignal(str)

    editor_open_requested  = pyqtSignal()
    editor_save_requested  = pyqtSignal()
    editor_export_requested = pyqtSignal()
    editor_undo_requested  = pyqtSignal()
    editor_redo_requested  = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(48)
        self._mode = "gallery"
        self._active_gallery_tab = "图库"
        self._build()

    # ── construction ──────────────────────────────────────────────────────────
    def _build(self) -> None:
        lo = QHBoxLayout(self)
        lo.setContentsMargins(16, 0, 0, 0)
        lo.setSpacing(0)

        # ── left permanent section ────────────────────────────────────────────
        logo_icon = QLabel()
        logo_icon.setPixmap(_logo_pixmap(24))
        logo_icon.setFixedSize(24, 24)
        lo.addWidget(logo_icon)
        lo.addSpacing(8)

        logo_txt = QLabel("TempusLoom")
        logo_txt.setObjectName("logoText")
        lo.addWidget(logo_txt)
        lo.addSpacing(12)

        lo.addWidget(_vline())
        lo.addSpacing(12)

        # mode switch pill
        mode_frame = QWidget()
        mode_frame.setObjectName("modeSwitch")
        mode_frame.setFixedHeight(32)
        mode_lo = QHBoxLayout(mode_frame)
        mode_lo.setContentsMargins(2, 2, 2, 2)
        mode_lo.setSpacing(0)

        self._btn_gallery = QPushButton("图库")
        self._btn_gallery.setFixedHeight(28)
        self._btn_gallery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gallery.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_gallery.clicked.connect(lambda: self._on_mode_clicked("gallery"))

        self._btn_editor = QPushButton("编辑器")
        self._btn_editor.setFixedHeight(28)
        self._btn_editor.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_editor.clicked.connect(lambda: self._on_mode_clicked("editor"))

        mode_lo.addWidget(self._btn_gallery)
        mode_lo.addWidget(self._btn_editor)
        lo.addWidget(mode_frame)
        lo.addSpacing(12)

        lo.addWidget(_vline())
        lo.addSpacing(4)

        # ── middle stack (tabs vs menu items) ─────────────────────────────────
        self._middle_stack = QStackedWidget()
        self._middle_stack.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        # idx-0 : gallery nav tabs
        gallery_tabs_w = self._build_gallery_tabs()
        # idx-1 : editor menu items
        editor_menus_w = self._build_editor_menus()
        self._middle_stack.addWidget(gallery_tabs_w)   # 0
        self._middle_stack.addWidget(editor_menus_w)   # 1
        lo.addWidget(self._middle_stack)

        # ── stretch ───────────────────────────────────────────────────────────
        lo.addStretch()

        # ── right stack (search+import  vs  undo/redo+save+export) ────────────
        self._right_stack = QStackedWidget()
        self._right_stack.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        gallery_right_w = self._build_gallery_right()
        editor_right_w  = self._build_editor_right()
        self._right_stack.addWidget(gallery_right_w)   # 0
        self._right_stack.addWidget(editor_right_w)    # 1
        # 320px fixed-width wrapper — aligns exactly with the 320px RightPanel below
        right_wrapper = QWidget()
        right_wrapper.setFixedWidth(320)
        rw_lo = QHBoxLayout(right_wrapper)
        rw_lo.setContentsMargins(0, 0, 16, 0)   # 16px right padding (replaces removed outer margin)
        rw_lo.setSpacing(0)
        rw_lo.addStretch()
        rw_lo.addWidget(self._right_stack)
        rw_lo.addSpacing(8)
        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        avatar.setPixmap(_avatar_pixmap(28))
        rw_lo.addWidget(avatar)
        lo.addWidget(right_wrapper)

        # apply initial mode styling
        self._refresh_mode_buttons()

    # ── middle idx-0 : gallery nav tabs ───────────────────────────────────────
    def _build_gallery_tabs(self) -> QWidget:
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        self._gallery_tabs: dict[str, QPushButton] = {}
        for name in ("图库", "最近", "收藏"):
            btn = QPushButton(name)
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _, n=name: self._on_gallery_tab(n))
            self._gallery_tabs[name] = btn
            lo.addWidget(btn)

        self._refresh_gallery_tabs()
        return w

    # ── middle idx-1 : editor menu items ──────────────────────────────────────
    def _build_editor_menus(self) -> QWidget:
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        for text in ("文件", "编辑", "视图", "插件"):
            btn = QPushButton(text)
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setObjectName("navTabInactive")
            if text == "文件":
                btn.clicked.connect(self._show_file_menu)
            lo.addWidget(btn)

        return w

    # ── right idx-0 : gallery search + import ─────────────────────────────────
    def _build_gallery_right(self) -> QWidget:
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(8)

        self._search_box = QLineEdit()
        self._search_box.setObjectName("searchBox")
        self._search_box.setPlaceholderText("搜索图像...")
        self._search_box.setFixedSize(220, 32)
        self._search_box.textChanged.connect(self.gallery_search_changed.emit)
        lo.addWidget(self._search_box)

        import_btn = QPushButton("  导入")
        import_btn.setObjectName("importBtn")
        import_btn.setFixedHeight(32)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        import_btn.clicked.connect(self.gallery_import_clicked.emit)
        lo.addWidget(import_btn)

        return w

    # ── right idx-1 : editor controls ─────────────────────────────────────────
    def _build_editor_right(self) -> QWidget:
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(2)

        # undo / redo
        undo_btn = self._icon_btn("undo-2", 16, 32, C_TEXT_4, tip="撤销  Ctrl+Z")
        undo_btn.clicked.connect(self.editor_undo_requested.emit)
        redo_btn = self._icon_btn("redo-2", 16, 32, C_TEXT_4, tip="重做  Ctrl+Y")
        redo_btn.clicked.connect(self.editor_redo_requested.emit)
        lo.addWidget(undo_btn)
        lo.addWidget(redo_btn)
        lo.addSpacing(6)
        lo.addWidget(_vline())
        lo.addSpacing(6)

        # save
        save_btn = QPushButton()
        save_btn.setFixedHeight(32)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        save_btn.setStyleSheet(
            f"QPushButton{{background:{C_BG_ITEM}; color:{C_TEXT_2}; border-radius:6px;"
            f"border:none; padding:0 14px; font-size:13px;}}"
            f"QPushButton:hover{{background:#383838;}}"
        )
        save_btn.clicked.connect(self.editor_save_requested.emit)
        save_lo = QHBoxLayout(save_btn)
        save_lo.setContentsMargins(14, 0, 14, 0)
        save_lo.setSpacing(6)
        s_icon = QLabel()
        s_icon.setPixmap(icon_pixmap("save", 14, C_TEXT_3))
        s_icon.setFixedSize(14, 14)
        s_lbl = QLabel("保存")
        s_lbl.setStyleSheet(f"color:{C_TEXT_2}; font-size:13px; background:transparent;")
        save_lo.addWidget(s_icon)
        save_lo.addWidget(s_lbl)
        lo.addWidget(save_btn)
        lo.addSpacing(8)

        # export
        exp_btn = QPushButton()
        exp_btn.setFixedHeight(32)
        exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        exp_btn.setStyleSheet(
            f"QPushButton{{background:{C_PRIMARY}; border-radius:6px; border:none; padding:0 14px;}}"
            f"QPushButton:hover{{background:{C_PRIMARY_H};}}"
            f"QPushButton:pressed{{background:#2855cc;}}"
        )
        exp_btn.clicked.connect(self.editor_export_requested.emit)
        exp_lo = QHBoxLayout(exp_btn)
        exp_lo.setContentsMargins(14, 0, 14, 0)
        exp_lo.setSpacing(6)
        e_icon = QLabel()
        e_icon.setPixmap(icon_pixmap("share", 14, C_BG_PANEL))
        e_icon.setFixedSize(14, 14)
        e_lbl = QLabel("导出")
        e_lbl.setStyleSheet(f"color:{C_WHITE}; font-size:13px; font-weight:500; background:transparent;")
        exp_lo.addWidget(e_icon)
        exp_lo.addWidget(e_lbl)
        lo.addWidget(exp_btn)

        return w

    # ── icon button helper ─────────────────────────────────────────────────────
    @staticmethod
    def _icon_btn(icon_name: str, icon_size: int, btn_size: int,
                  color: str, tip: str = "") -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(btn_size, btn_size)
        btn.setIcon(_qicon(icon_name, icon_size, color))
        btn.setIconSize(QSize(icon_size, icon_size))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setToolTip(tip)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent; border-radius:6px; border:none;}}"
            f"QPushButton:hover{{background:{C_BG_ITEM};}}"
            f"QPushButton:pressed{{background:#3a3a3a;}}"
        )
        return btn

    # ── file menu (editor) ────────────────────────────────────────────────────
    def _show_file_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C_BG_PANEL}; color:{C_TEXT_1};"
            f"border:1px solid {C_BORDER}; border-radius:6px; padding:4px;}}"
            f"QMenu::item{{padding:6px 20px; border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C_BG_ACTIVE}; color:{C_PRIMARY};}}"
            f"QMenu::separator{{background:{C_BORDER}; height:1px; margin:4px 8px;}}"
        )
        menu.addAction("打开图像…").triggered.connect(self.editor_open_requested.emit)
        menu.addSeparator()
        menu.addAction("保存").triggered.connect(self.editor_save_requested.emit)
        menu.addAction("另存为…")
        menu.addSeparator()
        menu.addAction("导出…").triggered.connect(self.editor_export_requested.emit)
        # show below topbar
        menu.exec(self.mapToGlobal(QPointF(0, 48).toPoint()))

    # ── internal tab / mode handlers ──────────────────────────────────────────
    def _on_gallery_tab(self, name: str) -> None:
        self._active_gallery_tab = name
        self._refresh_gallery_tabs()
        self.gallery_tab_changed.emit(name)

    def _on_mode_clicked(self, mode: str) -> None:
        if mode != self._mode:
            self.mode_switched.emit(mode)

    # ── public api ────────────────────────────────────────────────────────────
    def set_mode(self, mode: str) -> None:
        """Switch topbar to *mode* instantly (no animation)."""
        self._mode = mode
        idx = _PAGE_GALLERY if mode == "gallery" else _PAGE_EDITOR
        self._middle_stack.setCurrentIndex(idx)
        self._right_stack.setCurrentIndex(idx)
        self._refresh_mode_buttons()

    # ── style refresh ─────────────────────────────────────────────────────────
    def _refresh_mode_buttons(self) -> None:
        if self._mode == "gallery":
            self._btn_gallery.setObjectName("modeBtnActive")
            self._btn_editor.setObjectName("modeBtnInactive")
        else:
            self._btn_gallery.setObjectName("modeBtnInactive")
            self._btn_editor.setObjectName("modeBtnActive")
        for btn in (self._btn_gallery, self._btn_editor):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _refresh_gallery_tabs(self) -> None:
        for name, btn in self._gallery_tabs.items():
            obj = "navTabActive" if name == self._active_gallery_tab else "navTabInactive"
            btn.setObjectName(obj)
            btn.style().unpolish(btn)
            btn.style().polish(btn)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class TempusLoomWindow(QMainWindow):
    """
    Outer shell.  The UnifiedTopBar is always visible; only the content
    area below it participates in the cross-fade page transition.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TempusLoom")
        self.resize(1440, 900)
        self.setMinimumSize(900, 600)

        # ── build layout ───────────────────────────────────────────────────────
        root = QWidget()
        root_lo = QVBoxLayout(root)
        root_lo.setContentsMargins(0, 0, 0, 0)
        root_lo.setSpacing(0)
        self.setCentralWidget(root)

        # permanent top bar
        self._topbar = UnifiedTopBar()
        root_lo.addWidget(self._topbar)

        # content pages
        self._gallery = GalleryBrowser()
        self._editor  = MainEditorWindow()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._gallery)   # index 0
        self._stack.addWidget(self._editor)    # index 1
        root_lo.addWidget(self._stack, 1)

        # opacity effect applied only to the content stack
        self._effect = QGraphicsOpacityEffect(self._stack)
        self._effect.setOpacity(1.0)
        self._stack.setGraphicsEffect(self._effect)

        # ── animation state ────────────────────────────────────────────────────
        self._animating   = False
        self._pending_idx: int | None = None

        # ── wire signals ───────────────────────────────────────────────────────
        self._wire_signals()
        self._setup_global_shortcuts()

    # ── signal wiring ──────────────────────────────────────────────────────────
    def _wire_signals(self) -> None:
        tb = self._topbar

        # mode switch → animate content + update topbar instantly
        tb.mode_switched.connect(self._on_mode)

        # gallery-specific
        tb.gallery_import_clicked.connect(self._gallery.trigger_import)
        tb.gallery_tab_changed.connect(self._gallery.trigger_tab)
        tb.gallery_search_changed.connect(self._gallery.filter_by_search)

        # editor-specific
        tb.editor_open_requested.connect(self._editor._open_image)
        tb.editor_save_requested.connect(self._editor._save_image)
        tb.editor_export_requested.connect(self._editor._export_image)
        tb.editor_undo_requested.connect(self._editor._undo)
        tb.editor_redo_requested.connect(self._editor._redo)

        # editor title propagation
        self._editor.title_changed.connect(self.setWindowTitle)

        # gallery "open in editor" → switch to editor page
        self._gallery._info_panel.open_in_editor.connect(self._on_open_in_editor)

    # ── public api ─────────────────────────────────────────────────────────────
    def show_gallery(self) -> None:
        self._switch_to(_PAGE_GALLERY)

    def show_editor(self) -> None:
        self._switch_to(_PAGE_EDITOR)

    # ── mode handler ───────────────────────────────────────────────────────────
    def _on_mode(self, mode: str) -> None:
        idx = _PAGE_GALLERY if mode == "gallery" else _PAGE_EDITOR
        self._topbar.set_mode(mode)          # instant topbar update
        self._switch_to(idx)                 # animated content swap

    def _on_open_in_editor(self, path: str) -> None:
        if path:
            self._editor._canvas.load_image(path)
        self._on_mode("editor")

    # ── cross-fade ─────────────────────────────────────────────────────────────
    def _switch_to(self, idx: int) -> None:
        """Cross-fade the content stack to page *idx*."""
        if self._stack.currentIndex() == idx and not self._animating:
            return

        if self._animating:
            self._pending_idx = idx
            return

        self._animating   = True
        self._pending_idx = None

        # phase 1 – fade out
        fade_out = QPropertyAnimation(self._effect, b"opacity", self)
        fade_out.setDuration(_FADE_OUT_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(_EASE_OUT)

        def _after_fade_out() -> None:
            self._stack.setCurrentIndex(idx)
            self._update_window_title(idx)

            # phase 2 – fade in
            fade_in = QPropertyAnimation(self._effect, b"opacity", self)
            fade_in.setDuration(_FADE_IN_MS)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(_EASE_IN)

            def _after_fade_in() -> None:
                self._animating = False
                if self._pending_idx is not None:
                    pending, self._pending_idx = self._pending_idx, None
                    self._switch_to(pending)

            fade_in.finished.connect(_after_fade_in)
            fade_in.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        fade_out.finished.connect(_after_fade_out)
        fade_out.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _update_window_title(self, idx: int) -> None:
        titles = {
            _PAGE_GALLERY: "TempusLoom – 图库",
            _PAGE_EDITOR:  "TempusLoom – 编辑器",
        }
        self.setWindowTitle(titles.get(idx, "TempusLoom"))

    def _setup_global_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+1"), self,
                  lambda: self._on_mode("gallery"))
        QShortcut(QKeySequence("Ctrl+2"), self,
                  lambda: self._on_mode("editor"))


# ── entry ───────────────────────────────────────────────────────────────────────

def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("TempusLoom")
    app.setOrganizationName("TempusLoom")
    apply_dark_theme(app)

    window = TempusLoomWindow()

    start_mode = "editor" if "--editor" in sys.argv else "gallery"
    start_idx  = _PAGE_EDITOR if start_mode == "editor" else _PAGE_GALLERY
    window._stack.setCurrentIndex(start_idx)
    window._topbar.set_mode(start_mode)
    window._update_window_title(start_idx)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
