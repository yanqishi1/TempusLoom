#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Sidebar
Sidebar panel with navigation and modules
"""

import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QFont

logger = logging.getLogger(__name__)


class SidebarButton(QPushButton):
    """Custom button for sidebar items"""
    
    def __init__(self, text, parent=None, icon=None):
        """Initialize sidebar button
        
        Args:
            text: Button text
            parent: Parent widget
            icon: Button icon
        """
        super().__init__(text, parent)
        
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setProperty("class", "module-item")
        
        if icon:
            self.setIcon(QIcon(icon))
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(36)
    
    def enterEvent(self, event):
        """Handle mouse enter event"""
        if not self.isChecked():
            self.setProperty("hover", True)
            self.style().polish(self)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave event"""
        self.setProperty("hover", False)
        self.style().polish(self)
        super().leaveEvent(event)


class SidebarSection(QWidget):
    """Section in the sidebar with title and items"""
    
    def __init__(self, title, parent=None):
        """Initialize sidebar section
        
        Args:
            title: Section title
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 10, 0, 5)
        self.layout.setSpacing(6)
        
        # Create title label
        self.title_label = QLabel(title, self)
        self.title_label.setProperty("class", "section-title")
        font = self.title_label.font()
        font.setPointSize(10)
        font.setBold(True)
        self.title_label.setFont(font)
        
        self.layout.addWidget(self.title_label)
        
        # Create buttons container
        self.buttons_container = QWidget(self)
        self.buttons_layout = QVBoxLayout(self.buttons_container)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setSpacing(2)
        
        self.layout.addWidget(self.buttons_container)
    
    def add_button(self, text, icon=None, on_click=None):
        """Add button to the section
        
        Args:
            text: Button text
            icon: Button icon
            on_click: Click handler
            
        Returns:
            SidebarButton: The created button
        """
        button = SidebarButton(text, self, icon)
        
        if on_click:
            button.clicked.connect(on_click)
        
        self.buttons_layout.addWidget(button)
        return button


class Sidebar(QWidget):
    """Sidebar panel with sections and modules"""
    
    # Signals
    module_selected = pyqtSignal(str, str)  # section_name, module_name
    
    def __init__(self, parent=None):
        """Initialize sidebar
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setObjectName("sidebar")
        self.setMinimumWidth(240)
        self.setMaximumWidth(300)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components"""
        # Create main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create scroll area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create scroll content widget
        self.scroll_content = QWidget(self.scroll_area)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(18, 18, 18, 18)
        self.scroll_layout.setSpacing(15)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)
        
        # Add sections
        self._add_sections()
    
    def _add_sections(self):
        """Add sections to the sidebar"""
        # Gallery section
        self.gallery_section = SidebarSection("图库浏览", self)
        self.favorites_button = self.gallery_section.add_button("收藏夹", on_click=lambda: self._on_module_click("gallery", "favorites"))
        self.recent_button = self.gallery_section.add_button("最近文件", on_click=lambda: self._on_module_click("gallery", "recent"))
        self.folders_button = self.gallery_section.add_button("文件夹结构", on_click=lambda: self._on_module_click("gallery", "folders"))
        self.smart_button = self.gallery_section.add_button("智能收藏", on_click=lambda: self._on_module_click("gallery", "smart"))
        self.tags_button = self.gallery_section.add_button("标签管理", on_click=lambda: self._on_module_click("gallery", "tags"))
        
        self.scroll_layout.addWidget(self.gallery_section)
        
        # Import/Export section
        self.io_section = SidebarSection("导入/导出", self)
        self.import_button = self.io_section.add_button("导入工具", on_click=lambda: self._on_module_click("io", "import"))
        self.export_button = self.io_section.add_button("批量导出", on_click=lambda: self._on_module_click("io", "export"))
        
        self.scroll_layout.addWidget(self.io_section)
        
        # AI Assistant section
        self.ai_section = SidebarSection("AI助手", self)
        self.ai_enhance_button = self.ai_section.add_button("智能增强", on_click=lambda: self._on_module_click("ai", "enhance"))
        self.ai_edit_button = self.ai_section.add_button("AI辅助编辑", on_click=lambda: self._on_module_click("ai", "edit"))
        
        self.scroll_layout.addWidget(self.ai_section)
        
        # Add stretch to push sections to the top
        self.scroll_layout.addStretch(1)
        
        # Set initial selection
        self.favorites_button.setChecked(True)
    
    def _on_module_click(self, section, module):
        """Handle module button click
        
        Args:
            section: Section name
            module: Module name
        """
        logger.debug(f"Module selected: {section}/{module}")
        self.module_selected.emit(section, module) 