#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - UI Styling
Styling utilities for the application UI
"""

import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QPixmap, QPainter, QBrush, QIcon, QPen, QFont
from PyQt6.QtCore import Qt, QRect

logger = logging.getLogger(__name__)


# Color palette definitions
DARK_PALETTE = {
    'primary': '#4361ee',
    'primary_light': '#4895ef',
    'primary_dark': '#3a0ca3',
    'secondary': '#4cc9f0',
    'accent': '#f72585',
    'dark': '#151526',
    'dark_medium': '#1f1f3a',
    'dark_light': '#292952',
    'light': '#f8f9fa',
    'gray_100': '#f3f4f6',
    'gray_200': '#e5e7eb',
    'gray_300': '#d1d5db',
    'gray_400': '#9ca3af',
    'gray_500': '#6b7280',
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
}

LIGHT_PALETTE = {
    'primary': '#4361ee',
    'primary_light': '#4895ef',
    'primary_dark': '#3a0ca3',
    'secondary': '#4cc9f0',
    'accent': '#f72585',
    'dark': '#27293d',
    'dark_medium': '#323252',
    'dark_light': '#3a3a64',
    'light': '#ffffff',
    'gray_100': '#f3f4f6',
    'gray_200': '#e5e7eb',
    'gray_300': '#d1d5db',
    'gray_400': '#9ca3af',
    'gray_500': '#6b7280',
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
}


def apply_style(app, theme='dark'):
    """Apply application-wide styling
    
    Args:
        app: QApplication instance
        theme: 'dark' or 'light'
    """
    logger.info(f"Applying {theme} theme")
    
    if theme.lower() == 'dark':
        _apply_dark_theme(app)
    else:
        _apply_light_theme(app)
    
    # Apply stylesheet
    app.setStyleSheet(_get_stylesheet(theme))


def _apply_dark_theme(app):
    """Apply dark theme palette"""
    palette = QPalette()
    
    # Set window and base colors
    palette.setColor(QPalette.ColorRole.Window, QColor(DARK_PALETTE['dark']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(DARK_PALETTE['light']))
    palette.setColor(QPalette.ColorRole.Base, QColor(DARK_PALETTE['dark_medium']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(DARK_PALETTE['dark_light']))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(DARK_PALETTE['dark']))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(DARK_PALETTE['light']))
    
    # Set text colors
    palette.setColor(QPalette.ColorRole.Text, QColor(DARK_PALETTE['light']))
    palette.setColor(QPalette.ColorRole.Button, QColor(DARK_PALETTE['dark_medium']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(DARK_PALETTE['light']))
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    
    # Set highlight colors
    palette.setColor(QPalette.ColorRole.Highlight, QColor(DARK_PALETTE['primary']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(DARK_PALETTE['light']))
    
    # Set disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(DARK_PALETTE['gray_500']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(DARK_PALETTE['gray_500']))
    
    # Apply palette
    app.setPalette(palette)


def _apply_light_theme(app):
    """Apply light theme palette"""
    palette = QPalette()
    
    # Set window and base colors
    palette.setColor(QPalette.ColorRole.Window, QColor(LIGHT_PALETTE['light']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(LIGHT_PALETTE['dark']))
    palette.setColor(QPalette.ColorRole.Base, QColor(LIGHT_PALETTE['gray_100']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(LIGHT_PALETTE['gray_200']))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(LIGHT_PALETTE['light']))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(LIGHT_PALETTE['dark']))
    
    # Set text colors
    palette.setColor(QPalette.ColorRole.Text, QColor(LIGHT_PALETTE['dark']))
    palette.setColor(QPalette.ColorRole.Button, QColor(LIGHT_PALETTE['gray_200']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(LIGHT_PALETTE['dark']))
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    
    # Set highlight colors
    palette.setColor(QPalette.ColorRole.Highlight, QColor(LIGHT_PALETTE['primary']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(LIGHT_PALETTE['light']))
    
    # Set disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(LIGHT_PALETTE['gray_400']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(LIGHT_PALETTE['gray_400']))
    
    # Apply palette
    app.setPalette(palette)


def _get_stylesheet(theme):
    """Get the stylesheet for the given theme
    
    Args:
        theme: 'dark' or 'light'
    
    Returns:
        str: CSS stylesheet
    """
    palette = DARK_PALETTE if theme.lower() == 'dark' else LIGHT_PALETTE
    
    return f"""
    /* QWidget */
    QWidget {{
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        font-size: 10pt;
    }}
    
    /* QMainWindow */
    QMainWindow {{
        background-color: {palette['dark']};
    }}
    
    /* QMenuBar */
    QMenuBar {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                  stop:0 {palette['dark']}, 
                                  stop:1 {palette['dark_medium']});
        color: {palette['light']};
        padding: 4px;
        spacing: 2px;
    }}
    
    QMenuBar::item {{
        background: transparent;
        padding: 6px 12px;
        border-radius: 4px;
    }}
    
    QMenuBar::item:selected {{
        background-color: rgba(255, 255, 255, 0.1);
    }}
    
    QMenuBar::item:pressed {{
        background-color: rgba(255, 255, 255, 0.15);
    }}
    
    /* QMenu */
    QMenu {{
        background-color: {palette['dark_medium']};
        color: {palette['light']};
        border: 1px solid {palette['dark_light']};
        border-radius: 4px;
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 6px 16px 6px 24px;
        border-radius: 2px;
    }}
    
    QMenu::item:selected {{
        background-color: rgba(255, 255, 255, 0.1);
    }}
    
    QMenu::separator {{
        height: 1px;
        background-color: {palette['dark_light']};
        margin: 4px 8px;
    }}
    
    /* QToolBar */
    QToolBar {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                  stop:0 {palette['dark_medium']}, 
                                  stop:1 {palette['dark_light']});
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        spacing: 6px;
        padding: 6px;
    }}
    
    QToolBar::separator {{
        width: 1px;
        background-color: rgba(255, 255, 255, 0.1);
        margin: 0 6px;
    }}
    
    QToolButton {{
        background-color: rgba(255, 255, 255, 0.08);
        color: {palette['light']};
        border-radius: 6px;
        padding: 4px;
        margin: 0 1px;
    }}
    
    QToolButton:hover {{
        background-color: rgba(255, 255, 255, 0.15);
    }}
    
    QToolButton:pressed {{
        background-color: rgba(255, 255, 255, 0.2);
    }}
    
    QToolButton:checked {{
        background-color: {palette['primary']};
    }}
    
    /* QStatusBar */
    QStatusBar {{
        background-color: {palette['dark']};
        color: {palette['gray_400']};
        border-top: 1px solid {palette['dark_medium']};
    }}
    
    QStatusBar::item {{
        border: none;
    }}
    
    /* QSplitter */
    QSplitter::handle {{
        background-color: {palette['dark_medium']};
        width: 1px;
        height: 1px;
    }}
    
    QSplitter::handle:hover {{
        background-color: {palette['primary']};
    }}
    
    /* QScrollBar */
    QScrollBar:vertical {{
        border: none;
        background-color: {palette['dark_medium']};
        width: 10px;
        margin: 0px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {palette['dark_light']};
        border-radius: 5px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {palette['gray_500']};
    }}
    
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        border: none;
        background-color: {palette['dark_medium']};
        height: 10px;
        margin: 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {palette['dark_light']};
        border-radius: 5px;
        min-width: 20px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {palette['gray_500']};
    }}
    
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* QTabWidget and QTabBar */
    QTabWidget::pane {{
        border: 1px solid {palette['dark_light']};
        background-color: {palette['dark_medium']};
        border-radius: 4px;
    }}
    
    QTabBar::tab {{
        background-color: {palette['dark']};
        color: {palette['gray_400']};
        padding: 8px 16px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {palette['dark_medium']};
        color: {palette['light']};
    }}
    
    QTabBar::tab:hover {{
        background-color: {palette['dark_light']};
    }}
    
    /* QPushButton */
    QPushButton {{
        background-color: {palette['primary']};
        color: {palette['light']};
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
    }}
    
    QPushButton:hover {{
        background-color: {palette['primary_light']};
    }}
    
    QPushButton:pressed {{
        background-color: {palette['primary_dark']};
    }}
    
    QPushButton:disabled {{
        background-color: {palette['dark_light']};
        color: {palette['gray_500']};
    }}
    
    /* QComboBox */
    QComboBox {{
        background-color: {palette['dark_medium']};
        color: {palette['light']};
        border: 1px solid {palette['dark_light']};
        border-radius: 4px;
        padding: 6px 12px;
        min-width: 6em;
    }}
    
    QComboBox:hover {{
        border: 1px solid {palette['gray_500']};
    }}
    
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 16px;
        border-left: none;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {palette['dark_medium']};
        color: {palette['light']};
        border: 1px solid {palette['dark_light']};
        selection-background-color: {palette['primary']};
        selection-color: {palette['light']};
        outline: none;
    }}
    
    /* QSlider */
    QSlider::groove:horizontal {{
        border: none;
        height: 4px;
        background-color: {palette['dark_light']};
        border-radius: 2px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {palette['primary']};
        border: 2px solid {palette['light']};
        width: 14px;
        margin: -6px 0;
        border-radius: 8px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: {palette['primary_light']};
    }}
    
    /* QLineEdit */
    QLineEdit {{
        background-color: {palette['dark_medium']};
        color: {palette['light']};
        border: 1px solid {palette['dark_light']};
        border-radius: 4px;
        padding: 6px 12px;
    }}
    
    QLineEdit:hover {{
        border: 1px solid {palette['gray_500']};
    }}
    
    QLineEdit:focus {{
        border: 1px solid {palette['primary']};
    }}
    
    /* QCheckBox */
    QCheckBox {{
        color: {palette['light']};
        spacing: 8px;
    }}
    
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid {palette['gray_500']};
    }}
    
    QCheckBox::indicator:unchecked {{
        background-color: {palette['dark_medium']};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {palette['primary']};
        border: 1px solid {palette['primary']};
    }}
    
    /* QRadioButton */
    QRadioButton {{
        color: {palette['light']};
        spacing: 8px;
    }}
    
    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 9px;
        border: 1px solid {palette['gray_500']};
    }}
    
    QRadioButton::indicator:unchecked {{
        background-color: {palette['dark_medium']};
    }}
    
    QRadioButton::indicator:checked {{
        background-color: {palette['primary']};
        border: 1px solid {palette['primary']};
    }}
    """ 

def get_app_icon():
    """Get the application icon
    
    Returns:
        QIcon: Application icon
    """
    # Create a simple icon for the application
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor('#4361ee'))
    
    # Create a painter to draw on the pixmap
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw a stylized 'TL' for TempusLoom
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor('#ffffff')))
    
    # Draw 'T' shape
    painter.drawRect(8, 6, 4, 20)
    painter.drawRect(8, 6, 16, 4)
    
    # Draw 'L' shape
    painter.drawRect(20, 14, 4, 12)
    painter.drawRect(20, 22, 8, 4)
    
    painter.end()
    
    return QIcon(pixmap)

def get_menu_icons():
    """Get a dictionary of icons for menus
    
    Returns:
        dict: Dictionary of QIcon objects
    """
    icons = {}
    
    # File menu icons
    icons['new'] = _create_simple_icon('N', '#10b981')
    icons['open'] = _create_simple_icon('O', '#4361ee')
    icons['save'] = _create_simple_icon('S', '#4cc9f0')
    icons['saveas'] = _create_simple_icon('A', '#3a0ca3')
    icons['export'] = _create_simple_icon('E', '#f72585')
    icons['print'] = _create_simple_icon('P', '#f59e0b')
    icons['exit'] = _create_simple_icon('X', '#ef4444')
    
    # Edit menu icons
    icons['undo'] = _create_simple_icon('U', '#4361ee')
    icons['redo'] = _create_simple_icon('R', '#4361ee')
    icons['cut'] = _create_simple_icon('X', '#ef4444')
    icons['copy'] = _create_simple_icon('C', '#4cc9f0')
    icons['paste'] = _create_simple_icon('V', '#10b981')
    icons['select_all'] = _create_simple_icon('A', '#4361ee')
    icons['deselect'] = _create_simple_icon('D', '#f59e0b')
    icons['preferences'] = _create_simple_icon('P', '#f72585')
    
    # View menu icons
    icons['zoom_in'] = _create_simple_icon('+', '#10b981')
    icons['zoom_out'] = _create_simple_icon('-', '#10b981')
    icons['zoom_fit'] = _create_simple_icon('F', '#4cc9f0')
    icons['zoom_100'] = _create_simple_icon('1', '#4cc9f0')
    icons['fullscreen'] = _create_simple_icon('F', '#f72585')
    
    # Tool icons
    icons['select'] = _create_simple_icon('S', '#4361ee')
    icons['crop'] = _create_simple_icon('C', '#4cc9f0')
    icons['brush'] = _create_simple_icon('B', '#10b981')
    icons['eraser'] = _create_simple_icon('E', '#f59e0b')
    icons['text'] = _create_simple_icon('T', '#f72585')
    icons['transform'] = _create_simple_icon('T', '#3a0ca3')
    
    return icons

def _create_simple_icon(letter, color_hex):
    """Create a simple colored icon with a letter
    
    Args:
        letter: Single letter to display
        color_hex: Hex color for the background
    
    Returns:
        QIcon: Simple icon
    """
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw background circle
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(color_hex)))
    painter.drawEllipse(0, 0, 16, 16)
    
    # Draw letter
    painter.setPen(QPen(QColor('#ffffff')))
    font = QFont("Arial", 9, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRect(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, letter)
    
    painter.end()
    
    return QIcon(pixmap) 