#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Layers Panel
Panel for managing image layers
"""

import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QListWidget, QListWidgetItem, QMenu, 
    QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent, QMimeData, QPoint
from PyQt6.QtGui import QIcon, QFont, QDrag, QPixmap, QColor, QPainter

logger = logging.getLogger(__name__)


class LayerItem(QWidget):
    """Custom widget for a layer item in the layers panel"""
    
    def __init__(self, name, layer_type="image", parent=None):
        """Initialize layer item
        
        Args:
            name: Layer name
            layer_type: Layer type (image, adjustment, text, mask)
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.name = name
        self.layer_type = layer_type
        self.is_visible = True
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components"""
        # Create layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 4, 6, 4)
        self.layout.setSpacing(8)
        
        # Create visibility button
        self.visibility_button = QToolButton(self)
        self.visibility_button.setText("👁")
        self.visibility_button.setFixedSize(24, 24)
        self.visibility_button.setCheckable(True)
        self.visibility_button.setChecked(True)
        self.visibility_button.clicked.connect(self._on_visibility_toggled)
        self.visibility_button.setProperty("class", "layer-visibility")
        
        self.layout.addWidget(self.visibility_button)
        
        # Create thumbnail
        self.thumbnail = QWidget(self)
        self.thumbnail.setFixedSize(32, 24)
        self.thumbnail.setProperty("class", "layer-thumbnail")
        
        self.layout.addWidget(self.thumbnail)
        
        # Create name label
        self.name_label = QLabel(self.name, self)
        self.name_label.setProperty("class", "layer-name")
        
        self.layout.addWidget(self.name_label)
        
        # Create type label
        type_map = {
            "image": "图像",
            "adjustment": "调整",
            "text": "文字",
            "mask": "蒙版",
            "group": "组"
        }
        
        type_display = type_map.get(self.layer_type, self.layer_type)
        self.type_label = QLabel(type_display, self)
        self.type_label.setProperty("class", "layer-type")
        
        self.layout.addWidget(self.type_label)
    
    def _on_visibility_toggled(self, checked):
        """Handle visibility button toggle
        
        Args:
            checked: Whether the button is checked
        """
        self.is_visible = checked
        logger.debug(f"Layer visibility changed: {self.name} -> {self.is_visible}")
    
    def set_visible(self, visible):
        """Set layer visibility
        
        Args:
            visible: Whether the layer is visible
        """
        self.is_visible = visible
        self.visibility_button.setChecked(visible)
    
    def set_name(self, name):
        """Set layer name
        
        Args:
            name: New layer name
        """
        self.name = name
        self.name_label.setText(name)


class LayersPanel(QWidget):
    """Panel for managing image layers"""
    
    # Signals
    layer_selected = pyqtSignal(int)  # layer_index
    layer_visibility_changed = pyqtSignal(int, bool)  # layer_index, visible
    layer_order_changed = pyqtSignal(int, int)  # from_index, to_index
    
    def __init__(self, parent=None):
        """Initialize layers panel
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setObjectName("layersPanel")
        self.setMinimumHeight(180)
        self.setMaximumHeight(300)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components"""
        # Create main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create header
        self.header = QWidget(self)
        self.header.setObjectName("layersHeader")
        self.header.setMinimumHeight(32)
        self.header.setMaximumHeight(32)
        
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(12, 0, 12, 0)
        self.header_layout.setSpacing(6)
        
        # Add title to header
        self.title_label = QLabel("图层", self.header)
        self.title_label.setProperty("class", "layers-title")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        
        self.header_layout.addWidget(self.title_label, 1)
        
        # Add layer buttons to header
        self.add_button = QToolButton(self.header)
        self.add_button.setText("+")
        self.add_button.setToolTip("新建图层")
        self.add_button.setFixedSize(24, 24)
        self.add_button.setProperty("class", "layer-action-button")
        self.add_button.clicked.connect(self._on_add_layer)
        
        self.header_layout.addWidget(self.add_button)
        
        self.add_group_button = QToolButton(self.header)
        self.add_group_button.setText("⊞")
        self.add_group_button.setToolTip("新建图层组")
        self.add_group_button.setFixedSize(24, 24)
        self.add_group_button.setProperty("class", "layer-action-button")
        self.add_group_button.clicked.connect(self._on_add_group)
        
        self.header_layout.addWidget(self.add_group_button)
        
        self.delete_button = QToolButton(self.header)
        self.delete_button.setText("−")
        self.delete_button.setToolTip("删除图层")
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setProperty("class", "layer-action-button")
        self.delete_button.clicked.connect(self._on_delete_layer)
        
        self.header_layout.addWidget(self.delete_button)
        
        self.effects_button = QToolButton(self.header)
        self.effects_button.setText("⨁")
        self.effects_button.setToolTip("图层效果")
        self.effects_button.setFixedSize(24, 24)
        self.effects_button.setProperty("class", "layer-action-button")
        self.effects_button.clicked.connect(self._on_layer_effects)
        
        self.header_layout.addWidget(self.effects_button)
        
        self.properties_button = QToolButton(self.header)
        self.properties_button.setText("⚙")
        self.properties_button.setToolTip("图层属性")
        self.properties_button.setFixedSize(24, 24)
        self.properties_button.setProperty("class", "layer-action-button")
        self.properties_button.clicked.connect(self._on_layer_properties)
        
        self.header_layout.addWidget(self.properties_button)
        
        self.layout.addWidget(self.header)
        
        # Create layers list
        self.layers_list = QListWidget(self)
        self.layers_list.setObjectName("layersList")
        self.layers_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.layers_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.layers_list.setFrameShape(QFrame.Shape.NoFrame)
        self.layers_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.layers_list.model().rowsMoved.connect(self._on_rows_moved)
        
        self.layout.addWidget(self.layers_list)
        
        # Add some sample layers
        self._add_sample_layers()
    
    def _add_sample_layers(self):
        """Add sample layers for testing"""
        # Add sample layers
        self.add_layer("调整图层", "adjustment")
        self.add_layer("文字图层", "text")
        self.add_layer("蒙版图层", "mask")
        self.add_layer("背景图层", "image")
        
        # Select the first layer
        self.layers_list.setCurrentRow(0)
    
    def add_layer(self, name, layer_type="image"):
        """Add a new layer to the list
        
        Args:
            name: Layer name
            layer_type: Layer type
            
        Returns:
            int: Index of the new layer
        """
        # Create layer item
        layer_item = LayerItem(name, layer_type)
        
        # Create list item
        list_item = QListWidgetItem(self.layers_list)
        list_item.setSizeHint(layer_item.sizeHint())
        
        # Insert at the top
        self.layers_list.insertItem(0, list_item)
        self.layers_list.setItemWidget(list_item, layer_item)
        
        logger.debug(f"Layer added: {name} ({layer_type})")
        
        return 0
    
    def add_group(self, name="新建组"):
        """Add a new layer group
        
        Args:
            name: Group name
            
        Returns:
            int: Index of the new group
        """
        return self.add_layer(name, "group")
    
    def remove_layer(self, index):
        """Remove a layer by index
        
        Args:
            index: Layer index
            
        Returns:
            bool: True if layer was removed
        """
        if index < 0 or index >= self.layers_list.count():
            return False
        
        # Remove the item
        item = self.layers_list.takeItem(index)
        if item:
            del item
            logger.debug(f"Layer removed at index {index}")
            return True
        
        return False
    
    def _on_add_layer(self):
        """Handle add layer button click"""
        index = self.add_layer("新建图层")
        self.layers_list.setCurrentRow(index)
    
    def _on_add_group(self):
        """Handle add group button click"""
        index = self.add_group()
        self.layers_list.setCurrentRow(index)
    
    def _on_delete_layer(self):
        """Handle delete layer button click"""
        current_row = self.layers_list.currentRow()
        if current_row >= 0:
            self.remove_layer(current_row)
    
    def _on_layer_effects(self):
        """Handle layer effects button click"""
        current_row = self.layers_list.currentRow()
        if current_row >= 0:
            logger.debug(f"Layer effects for layer at index {current_row}")
            # TODO: Show layer effects dialog
    
    def _on_layer_properties(self):
        """Handle layer properties button click"""
        current_row = self.layers_list.currentRow()
        if current_row >= 0:
            logger.debug(f"Layer properties for layer at index {current_row}")
            # TODO: Show layer properties dialog
    
    def _on_selection_changed(self):
        """Handle layer selection change"""
        current_row = self.layers_list.currentRow()
        if current_row >= 0:
            self.layer_selected.emit(current_row)
            logger.debug(f"Layer selected: {current_row}")
    
    def _on_rows_moved(self, parent, start, end, dest, row):
        """Handle layers being reordered
        
        Args:
            parent: Parent index
            start: Start row
            end: End row
            dest: Destination parent
            row: Destination row
        """
        from_index = start
        to_index = row
        
        # Adjust the to_index if moving down
        if to_index > from_index:
            to_index -= 1
        
        self.layer_order_changed.emit(from_index, to_index)
        logger.debug(f"Layer moved: {from_index} -> {to_index}") 