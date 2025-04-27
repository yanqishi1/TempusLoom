#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Toolbar
Main toolbar for the application
"""

import os
import logging
from PyQt6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtCore import Qt, QSize

logger = logging.getLogger(__name__)


class Toolbar(QToolBar):
    """Main toolbar for TempusLoom"""
    
    def __init__(self, parent=None):
        """Initialize the toolbar
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setObjectName("mainToolbar")
        self.setMovable(False)
        self.setIconSize(QSize(24, 24))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        # Create the toolbar
        self._create_tools()
    
    def _create_tools(self):
        """Create toolbar tools"""
        # Selection tool
        self.select_tool = self._create_tool_button(
            name="select",
            text="选择",
            icon="select.png",
            checkable=True,
            tooltip="选择工具 (V)"
        )
        self.select_tool.setChecked(True)
        self.addWidget(self.select_tool)
        
        # Crop tool
        self.crop_tool = self._create_tool_button(
            name="crop",
            text="裁剪",
            icon="crop.png",
            checkable=True,
            tooltip="裁剪工具 (C)"
        )
        self.addWidget(self.crop_tool)
        
        # Brush tool
        self.brush_tool = self._create_tool_button(
            name="brush",
            text="画笔",
            icon="brush.png",
            checkable=True,
            tooltip="画笔工具 (B)"
        )
        self.addWidget(self.brush_tool)
        
        # Gradient tool
        self.gradient_tool = self._create_tool_button(
            name="gradient",
            text="渐变",
            icon="gradient.png",
            checkable=True,
            tooltip="渐变工具 (G)"
        )
        self.addWidget(self.gradient_tool)
        
        # Eraser tool
        self.eraser_tool = self._create_tool_button(
            name="eraser",
            text="橡皮擦",
            icon="eraser.png",
            checkable=True,
            tooltip="橡皮擦工具 (E)"
        )
        self.addWidget(self.eraser_tool)
        
        # Text tool
        self.text_tool = self._create_tool_button(
            name="text",
            text="文字",
            icon="text.png",
            checkable=True,
            tooltip="文字工具 (T)"
        )
        self.addWidget(self.text_tool)
        
        # Clone tool
        self.clone_tool = self._create_tool_button(
            name="clone",
            text="克隆工具",
            icon="clone.png",
            checkable=True,
            tooltip="克隆工具 (S)"
        )
        self.addWidget(self.clone_tool)
        
        # Heal tool
        self.heal_tool = self._create_tool_button(
            name="heal",
            text="修复工具",
            icon="heal.png",
            checkable=True,
            tooltip="修复工具 (H)"
        )
        self.addWidget(self.heal_tool)
        
        # View toggle
        self.view_toggle = self._create_tool_button(
            name="view",
            text="切换视图",
            icon="view.png",
            checkable=True,
            tooltip="切换视图 (Z)"
        )
        self.addWidget(self.view_toggle)
        
        # Add a spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)
        
        # Create mask button
        self.create_mask_button = self._create_tool_button(
            name="create_mask",
            text="创建蒙版",
            icon="mask.png",
            tooltip="创建图层蒙版 (Shift+M)"
        )
        self.addWidget(self.create_mask_button)
        
        # Adjustment layer button
        self.adjust_layer_button = self._create_tool_button(
            name="adjust_layer",
            text="调整图层",
            icon="adjustment.png",
            tooltip="创建调整图层 (Shift+A)"
        )
        self.addWidget(self.adjust_layer_button)
        
        # Connect the buttons
        self._connect_tools()
    
    def _create_tool_button(self, name, text, icon=None, checkable=False, tooltip=None):
        """Create a tool button
        
        Args:
            name: Tool name
            text: Tool text
            icon: Icon file name
            checkable: Whether the button is checkable
            tooltip: Tooltip text
            
        Returns:
            QToolButton: The created button
        """
        button = QToolButton(self)
        button.setObjectName(f"{name}_tool")
        button.setText(text)
        
        if icon:
            # TODO: Replace with actual icon loading
            button.setIcon(self._get_icon(icon))
        
        if tooltip:
            button.setToolTip(tooltip)
        
        if checkable:
            button.setCheckable(True)
            button.setAutoExclusive(True)
        
        return button
    
    def _get_icon(self, icon_name):
        """Get an icon from the resources
        
        Args:
            icon_name: Icon file name
            
        Returns:
            QIcon: The loaded icon
        """
        # TODO: Implement actual icon loading
        # For now, return a default icon
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        return QIcon(pixmap)
    
    def _connect_tools(self):
        """Connect tool signals to slots"""
        # TODO: Connect to actual handler methods
        tools = [
            self.select_tool,
            self.crop_tool,
            self.brush_tool,
            self.gradient_tool,
            self.eraser_tool,
            self.text_tool,
            self.clone_tool,
            self.heal_tool,
            self.view_toggle
        ]
        
        for tool in tools:
            tool.toggled.connect(self._on_tool_toggled)
        
        self.create_mask_button.clicked.connect(self._on_create_mask)
        self.adjust_layer_button.clicked.connect(self._on_create_adjustment)
    
    def _on_tool_toggled(self, checked):
        """Handle tool toggled event
        
        Args:
            checked: Whether the tool is checked
        """
        if not checked:
            return
        
        sender = self.sender()
        if sender:
            tool_name = sender.objectName().replace('_tool', '')
            logger.debug(f"Tool selected: {tool_name}")
            # TODO: Emit signal for tool change
    
    def _on_create_mask(self):
        """Handle create mask button clicked"""
        logger.debug("Create mask button clicked")
        # TODO: Emit signal for create mask
    
    def _on_create_adjustment(self):
        """Handle create adjustment layer button clicked"""
        logger.debug("Create adjustment layer button clicked")
        # TODO: Emit signal for create adjustment layer 