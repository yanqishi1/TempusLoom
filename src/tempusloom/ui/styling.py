# -*- coding: utf-8 -*-
"""
TempusLoom dark theme stylesheet.
Design tokens match the pencil.pen design file.
"""

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication


# ── colour tokens ─────────────────────────────────────────────────────────────
PRIMARY       = "#3370FF"
PRIMARY_HOVER = "#5B8FF9"
BG_APP        = "#181818"   # main window / grid area
BG_TOPBAR     = "#252525"   # navigation bar
BG_PANEL      = "#1e1e1e"   # sidebar & info panel
BG_ITEM       = "#2c2c2c"   # toolbar chips, search box
BG_ACTIVE     = "#1a3060"   # selected sidebar item, avatar
BORDER        = "#333333"   # separators / horizontal lines
BORDER_PANEL  = "#2d2d2d"   # panel edge borders
TEXT_PRIMARY  = "#e8e8e8"
TEXT_SECONDARY= "#aaaaaa"
TEXT_MUTED    = "#888888"
TEXT_DIM      = "#777777"
TEXT_WHITE    = "#ffffff"


STYLESHEET = f"""
/* ── global ───────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_APP};
    color: {TEXT_PRIMARY};
    font-family: "Inter", "PingFang SC", "Helvetica Neue", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
    border: none;
}}

/* ── scrollbar ────────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #444444;
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: #555555; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

/* ── top bar ──────────────────────────────────────────────────────────────── */
#topBar {{
    background-color: {BG_TOPBAR};
    border-bottom: 1px solid {BORDER};
}}

/* ── logo text ────────────────────────────────────────────────────────────── */
#logoText {{
    color: {TEXT_WHITE};
    font-size: 15px;
    font-weight: 700;
}}

/* ── mode switch ──────────────────────────────────────────────────────────── */
#modeSwitch {{
    background-color: #383838;
    border-radius: 6px;
    padding: 2px;
}}
#modeBtnActive {{
    background-color: {BG_ITEM};
    border-radius: 4px;
    color: {TEXT_WHITE};
    font-size: 12px;
    font-weight: 500;
    padding: 4px 12px;
}}
#modeBtnInactive {{
    background-color: transparent;
    color: {TEXT_MUTED};
    font-size: 12px;
    padding: 4px 12px;
}}
#modeBtnInactive:hover {{ color: {TEXT_PRIMARY}; }}

/* ── nav tabs ─────────────────────────────────────────────────────────────── */
#navTabActive {{
    color: {PRIMARY};
    font-size: 13px;
    font-weight: 500;
    border-bottom: 2px solid {PRIMARY};
    padding: 0 12px;
    background: transparent;
}}
#navTabInactive {{
    color: {TEXT_MUTED};
    font-size: 13px;
    background: transparent;
    padding: 0 12px;
    border-bottom: 2px solid transparent;
}}
#navTabInactive:hover {{ color: {TEXT_PRIMARY}; }}

/* ── search box ───────────────────────────────────────────────────────────── */
#searchBox {{
    background-color: {BG_ITEM};
    border-radius: 8px;
    color: {TEXT_DIM};
    font-size: 12px;
    padding: 0 10px;
    height: 32px;
}}
#searchBox:focus {{
    border: 1px solid {PRIMARY};
    color: {TEXT_PRIMARY};
}}

/* ── import button ────────────────────────────────────────────────────────── */
#importBtn {{
    background-color: {PRIMARY};
    color: {TEXT_WHITE};
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 14px;
}}
#importBtn:hover {{ background-color: {PRIMARY_HOVER}; }}
#importBtn:pressed {{ background-color: #2855cc; }}

/* ── sidebar ──────────────────────────────────────────────────────────────── */
#sidebar {{
    background-color: {BG_PANEL};
    border-right: 1px solid {BORDER_PANEL};
}}

#sideSection {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 4px 8px 2px 8px;
    background: transparent;
}}

#sideItemActive {{
    background-color: {BG_ACTIVE};
    border-radius: 6px;
    padding: 6px 8px;
}}
#sideItemActive:hover {{ background-color: #1d3870; }}

#sideItemInactive {{
    background-color: transparent;
    border-radius: 6px;
    padding: 6px 8px;
}}
#sideItemInactive:hover {{ background-color: #252525; }}

#sideItemTextActive {{
    color: {PRIMARY};
    font-size: 13px;
    font-weight: 500;
    background: transparent;
}}
#sideItemTextInactive {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
    background: transparent;
}}
#sideItemCount {{
    color: {TEXT_MUTED};
    font-size: 11px;
    background: transparent;
}}

/* ── grid toolbar ─────────────────────────────────────────────────────────── */
#gridToolbar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER_PANEL};
}}
#gridInfo {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 500;
    background: transparent;
}}
#toolChip {{
    background-color: {BG_ITEM};
    border-radius: 6px;
    color: {TEXT_SECONDARY};
    font-size: 12px;
    padding: 4px 10px;
}}
#toolChip:hover {{ background-color: #363636; }}

/* ── thumbnail grid ───────────────────────────────────────────────────────── */
#gridArea {{ background-color: {BG_APP}; }}
#thumbName {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}

/* ── info panel ───────────────────────────────────────────────────────────── */
#infoPanel {{
    background-color: {BG_PANEL};
    border-left: 1px solid {BORDER_PANEL};
}}
#infoTitle {{
    color: {TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}}
#infoLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
    background: transparent;
}}
#infoValue {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}}
#infoActTitle {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}

/* ── action buttons ───────────────────────────────────────────────────────── */
#actBtnPrimary {{
    background-color: {PRIMARY};
    color: {TEXT_WHITE};
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 0;
}}
#actBtnPrimary:hover {{ background-color: {PRIMARY_HOVER}; }}
#actBtnPrimary:pressed {{ background-color: #2855cc; }}

#actBtnSecondary {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    font-size: 13px;
    padding: 8px 0;
}}
#actBtnSecondary:hover {{ background-color: #252525; }}
#actBtnSecondary:pressed {{ background-color: #2a2a2a; }}

/* ── divider line ─────────────────────────────────────────────────────────── */
#divider {{
    background-color: {BORDER};
    max-height: 1px;
    min-height: 1px;
}}
#dividerV {{
    background-color: {BORDER};
    max-width: 1px;
    min-width: 1px;
}}
"""


def apply_dark_theme(app: QApplication) -> None:
    """Apply palette + stylesheet to *app*."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(BG_APP))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,            QColor(BG_PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_TOPBAR))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button,          QColor(BG_ITEM))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_WHITE))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
