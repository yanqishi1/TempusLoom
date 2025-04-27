#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Properties Panel
Panel for controlling properties of selected elements
"""

import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QSlider, QComboBox, QGroupBox,
    QSizePolicy, QGridLayout, QToolButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QFont

logger = logging.getLogger(__name__)


class SliderControl(QWidget):
    """Custom slider control with label and value display"""
    
    # Signal when value changes
    value_changed = pyqtSignal(str, int)  # name, value
    
    def __init__(self, name, label, min_value=0, max_value=100, value=50, parent=None):
        """Initialize slider control
        
        Args:
            name: Control name (used in signals)
            label: Display label
            min_value: Minimum value
            max_value: Maximum value
            value: Initial value
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        
        self._init_ui(label, value)
    
    def _init_ui(self, label, value):
        """Initialize UI components
        
        Args:
            label: Display label
            value: Initial value
        """
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        
        # Create label and value display
        self.label_layout = QHBoxLayout()
        self.label_layout.setContentsMargins(0, 0, 0, 0)
        self.label_layout.setSpacing(6)
        
        self.label = QLabel(label, self)
        self.label.setProperty("class", "slider-label")
        self.label_layout.addWidget(self.label)
        
        self.value_label = QLabel(str(value), self)
        self.value_label.setProperty("class", "slider-value")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label_layout.addWidget(self.value_label)
        
        self.layout.addLayout(self.label_layout)
        
        # Create slider
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setMinimum(self.min_value)
        self.slider.setMaximum(self.max_value)
        self.slider.setValue(value)
        self.slider.setProperty("class", "slider-track")
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        self.layout.addWidget(self.slider)
    
    def _on_slider_changed(self, value):
        """Handle slider value change
        
        Args:
            value: New slider value
        """
        self.value_label.setText(str(value))
        self.value_changed.emit(self.name, value)
    
    def set_value(self, value):
        """Set slider value
        
        Args:
            value: New value
        """
        self.slider.setValue(value)
    
    def get_value(self):
        """Get slider value
        
        Returns:
            int: Current value
        """
        return self.slider.value()


class PropertyGroup(QGroupBox):
    """Group of properties with a title"""
    
    def __init__(self, title, parent=None):
        """Initialize property group
        
        Args:
            title: Group title
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setTitle(title)
        self.setProperty("class", "property-group")
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 16, 12, 12)
        self.layout.setSpacing(10)
    
    def add_widget(self, widget):
        """Add widget to the group
        
        Args:
            widget: Widget to add
        """
        self.layout.addWidget(widget)
    
    def add_widgets(self, widgets):
        """Add multiple widgets to the group
        
        Args:
            widgets: List of widgets to add
        """
        for widget in widgets:
            self.layout.addWidget(widget)


class PropertiesPanel(QWidget):
    """Panel for controlling properties of selected elements"""
    
    def __init__(self, parent=None):
        """Initialize properties panel
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setObjectName("propertiesPanel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        
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
        self.scroll_layout.setSpacing(18)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)
        
        # Add properties sections
        self._add_layer_properties()
        self._add_mask_properties()
        self._add_adjustment_sliders()
        self._add_ai_tools()
    
    def _add_layer_properties(self):
        """Add layer properties section"""
        # Create section title
        self.layer_title = QLabel("图层属性", self)
        self.layer_title.setProperty("class", "section-title")
        font = self.layer_title.font()
        font.setPointSize(10)
        font.setBold(True)
        self.layer_title.setFont(font)
        
        self.scroll_layout.addWidget(self.layer_title)
        
        # Create layer info group
        self.layer_info_group = PropertyGroup("图层基本信息", self)
        
        # Layer name
        self.layer_name_layout = QHBoxLayout()
        self.layer_name_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_name_layout.setSpacing(6)
        
        self.layer_name_label = QLabel("名称:", self)
        self.layer_name_layout.addWidget(self.layer_name_label)
        
        self.layer_name_value = QLabel("调整图层", self)
        self.layer_name_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.layer_name_layout.addWidget(self.layer_name_value)
        
        name_widget = QWidget(self)
        name_widget.setLayout(self.layer_name_layout)
        self.layer_info_group.add_widget(name_widget)
        
        # Layer type
        self.layer_type_layout = QHBoxLayout()
        self.layer_type_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_type_layout.setSpacing(6)
        
        self.layer_type_label = QLabel("类型:", self)
        self.layer_type_layout.addWidget(self.layer_type_label)
        
        self.layer_type_value = QLabel("调整图层", self)
        self.layer_type_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.layer_type_layout.addWidget(self.layer_type_value)
        
        type_widget = QWidget(self)
        type_widget.setLayout(self.layer_type_layout)
        self.layer_info_group.add_widget(type_widget)
        
        # Layer opacity
        self.layer_opacity_layout = QHBoxLayout()
        self.layer_opacity_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_opacity_layout.setSpacing(6)
        
        self.layer_opacity_label = QLabel("透明度:", self)
        self.layer_opacity_layout.addWidget(self.layer_opacity_label)
        
        self.layer_opacity_value = QLabel("100%", self)
        self.layer_opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.layer_opacity_layout.addWidget(self.layer_opacity_value)
        
        opacity_widget = QWidget(self)
        opacity_widget.setLayout(self.layer_opacity_layout)
        self.layer_info_group.add_widget(opacity_widget)
        
        # Blend mode
        self.blend_mode_layout = QHBoxLayout()
        self.blend_mode_layout.setContentsMargins(0, 0, 0, 0)
        self.blend_mode_layout.setSpacing(6)
        
        self.blend_mode_label = QLabel("混合模式:", self)
        self.blend_mode_layout.addWidget(self.blend_mode_label)
        
        self.blend_mode_combo = QComboBox(self)
        self.blend_mode_combo.addItems([
            "正常", "溶解", "正片叠底", "屏幕", "叠加", "柔光", "强光", 
            "颜色减淡", "颜色加深", "线性减淡", "线性加深", "颜色", "亮度"
        ])
        self.blend_mode_layout.addWidget(self.blend_mode_combo)
        
        blend_mode_widget = QWidget(self)
        blend_mode_widget.setLayout(self.blend_mode_layout)
        self.layer_info_group.add_widget(blend_mode_widget)
        
        self.scroll_layout.addWidget(self.layer_info_group)
    
    def _add_mask_properties(self):
        """Add mask properties section"""
        # Create mask group
        self.mask_group = PropertyGroup("蒙版设置", self)
        
        # Mask controls
        self.mask_controls = QWidget(self)
        self.mask_controls.setProperty("class", "mask-controls")
        self.mask_controls_layout = QHBoxLayout(self.mask_controls)
        self.mask_controls_layout.setContentsMargins(8, 8, 8, 8)
        self.mask_controls_layout.setSpacing(8)
        
        # Mask preview
        self.mask_preview = QWidget(self)
        self.mask_preview.setFixedSize(32, 32)
        self.mask_preview.setProperty("class", "mask-preview")
        self.mask_controls_layout.addWidget(self.mask_preview)
        
        # Mask options
        self.mask_options = QWidget(self)
        self.mask_options_layout = QVBoxLayout(self.mask_options)
        self.mask_options_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_options_layout.setSpacing(6)
        
        # Mask mode selector
        self.mask_mode_widget = QWidget(self)
        self.mask_mode_layout = QHBoxLayout(self.mask_mode_widget)
        self.mask_mode_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_mode_layout.setSpacing(4)
        
        self.pixel_mask_button = QPushButton("像素蒙版", self)
        self.pixel_mask_button.setProperty("class", "mask-mode active")
        self.pixel_mask_button.setFixedHeight(24)
        self.mask_mode_layout.addWidget(self.pixel_mask_button)
        
        self.vector_mask_button = QPushButton("矢量蒙版", self)
        self.vector_mask_button.setProperty("class", "mask-mode")
        self.vector_mask_button.setFixedHeight(24)
        self.mask_mode_layout.addWidget(self.vector_mask_button)
        
        self.clipping_mask_button = QPushButton("剪贴蒙版", self)
        self.clipping_mask_button.setProperty("class", "mask-mode")
        self.clipping_mask_button.setFixedHeight(24)
        self.mask_mode_layout.addWidget(self.clipping_mask_button)
        
        self.mask_options_layout.addWidget(self.mask_mode_widget)
        
        # Mask opacity
        self.mask_opacity_widget = QWidget(self)
        self.mask_opacity_layout = QHBoxLayout(self.mask_opacity_widget)
        self.mask_opacity_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_opacity_layout.setSpacing(8)
        
        self.mask_opacity_label = QLabel("不透明度:", self)
        self.mask_opacity_layout.addWidget(self.mask_opacity_label)
        
        self.mask_opacity_slider = QWidget(self)
        self.mask_opacity_slider.setProperty("class", "mask-opacity-slider")
        self.mask_opacity_slider.setMinimumWidth(100)
        self.mask_opacity_slider.setFixedHeight(4)
        
        self.mask_opacity_fill = QWidget(self.mask_opacity_slider)
        self.mask_opacity_fill.setProperty("class", "mask-opacity-fill")
        self.mask_opacity_fill.setGeometry(0, 0, 75, 4)
        
        self.mask_opacity_handle = QWidget(self.mask_opacity_slider)
        self.mask_opacity_handle.setProperty("class", "mask-opacity-handle")
        self.mask_opacity_handle.setFixedSize(10, 10)
        self.mask_opacity_handle.move(70, -3)
        
        self.mask_opacity_layout.addWidget(self.mask_opacity_slider)
        
        self.mask_opacity_value = QLabel("75%", self)
        self.mask_opacity_layout.addWidget(self.mask_opacity_value)
        
        self.mask_options_layout.addWidget(self.mask_opacity_widget)
        
        self.mask_controls_layout.addWidget(self.mask_options)
        
        self.mask_group.add_widget(self.mask_controls)
        
        # Mask buttons
        self.mask_buttons = QWidget(self)
        self.mask_buttons_layout = QHBoxLayout(self.mask_buttons)
        self.mask_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_buttons_layout.setSpacing(10)
        
        self.add_mask_button = QPushButton("添加蒙版", self)
        self.add_mask_button.setProperty("class", "tool-button")
        self.mask_buttons_layout.addWidget(self.add_mask_button)
        
        self.edit_mask_button = QPushButton("编辑蒙版", self)
        self.edit_mask_button.setProperty("class", "tool-button")
        self.mask_buttons_layout.addWidget(self.edit_mask_button)
        
        self.mask_group.add_widget(self.mask_buttons)
        
        self.scroll_layout.addWidget(self.mask_group)
    
    def _add_adjustment_sliders(self):
        """Add adjustment sliders section"""
        # Create section title
        self.adjust_title = QLabel("调整面板", self)
        self.adjust_title.setProperty("class", "section-title")
        font = self.adjust_title.font()
        font.setPointSize(10)
        font.setBold(True)
        self.adjust_title.setFont(font)
        
        self.scroll_layout.addWidget(self.adjust_title)
        
        # Create exposure group
        self.exposure_group = PropertyGroup("", self)
        
        # Create sliders
        self.exposure_slider = SliderControl(
            name="exposure",
            label="曝光",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.exposure_slider.value_changed.connect(self._on_slider_value_changed)
        self.exposure_group.add_widget(self.exposure_slider)
        
        self.contrast_slider = SliderControl(
            name="contrast",
            label="对比度",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.contrast_slider.value_changed.connect(self._on_slider_value_changed)
        self.exposure_group.add_widget(self.contrast_slider)
        
        self.highlights_slider = SliderControl(
            name="highlights",
            label="高光",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.highlights_slider.value_changed.connect(self._on_slider_value_changed)
        self.exposure_group.add_widget(self.highlights_slider)
        
        self.shadows_slider = SliderControl(
            name="shadows",
            label="阴影",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.shadows_slider.value_changed.connect(self._on_slider_value_changed)
        self.exposure_group.add_widget(self.shadows_slider)
        
        self.scroll_layout.addWidget(self.exposure_group)
        
        # Create color group
        self.color_group = PropertyGroup("", self)
        
        # Create color sliders
        self.temperature_slider = SliderControl(
            name="temperature",
            label="色温",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.temperature_slider.value_changed.connect(self._on_slider_value_changed)
        self.color_group.add_widget(self.temperature_slider)
        
        self.saturation_slider = SliderControl(
            name="saturation",
            label="饱和度",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.saturation_slider.value_changed.connect(self._on_slider_value_changed)
        self.color_group.add_widget(self.saturation_slider)
        
        self.vibrance_slider = SliderControl(
            name="vibrance",
            label="自然饱和度",
            min_value=-100,
            max_value=100,
            value=0
        )
        self.vibrance_slider.value_changed.connect(self._on_slider_value_changed)
        self.color_group.add_widget(self.vibrance_slider)
        
        self.scroll_layout.addWidget(self.color_group)
    
    def _add_ai_tools(self):
        """Add AI tools section"""
        # Create AI tools group
        self.ai_group = PropertyGroup("AI辅助工具", self)
        self.ai_group.setProperty("class", "ai-tools")
        
        # Create buttons grid
        self.ai_buttons = QWidget(self)
        self.ai_buttons_layout = QGridLayout(self.ai_buttons)
        self.ai_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.ai_buttons_layout.setSpacing(10)
        
        # Create buttons
        self.enhance_button = QPushButton("自动增强", self)
        self.enhance_button.setProperty("class", "ai-button")
        self.ai_buttons_layout.addWidget(self.enhance_button, 0, 0)
        
        self.repair_button = QPushButton("智能修复", self)
        self.repair_button.setProperty("class", "ai-button")
        self.ai_buttons_layout.addWidget(self.repair_button, 0, 1)
        
        self.subject_button = QPushButton("主体识别", self)
        self.subject_button.setProperty("class", "ai-button")
        self.ai_buttons_layout.addWidget(self.subject_button, 1, 0)
        
        self.style_button = QPushButton("风格迁移", self)
        self.style_button.setProperty("class", "ai-button")
        self.ai_buttons_layout.addWidget(self.style_button, 1, 1)
        
        self.ai_group.add_widget(self.ai_buttons)
        
        self.scroll_layout.addWidget(self.ai_group)
        
        # Add a stretch to push everything to the top
        self.scroll_layout.addStretch(1)
    
    def _on_slider_value_changed(self, name, value):
        """Handle slider value changes
        
        Args:
            name: Slider name
            value: New value
        """
        logger.debug(f"Slider value changed: {name} -> {value}")
        # TODO: Handle slider value changes 