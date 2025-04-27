#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Tabbed Panel
选项卡式侧边面板，整合图层、调整、AI工具和蒙版功能
"""

import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QSlider, QComboBox, QGroupBox,
    QSizePolicy, QGridLayout, QToolButton, QTabWidget,
    QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPen, QPainter

from tempusloom.ui.layers_panel import LayerItem, LayersPanel
from tempusloom.ui.properties_panel import SliderControl, PropertyGroup

logger = logging.getLogger(__name__)


class LayersTab(QWidget):
    """图层选项卡，整合图层列表和图层属性"""
    
    def __init__(self, parent=None):
        """初始化图层选项卡"""
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 创建图层列表区域
        self.layers_list = LayersPanel(self)
        
        # 创建图层属性区域
        self.layer_properties = QWidget(self)
        self.properties_layout = QVBoxLayout(self.layer_properties)
        self.properties_layout.setContentsMargins(12, 12, 12, 12)
        self.properties_layout.setSpacing(12)
        
        # 添加图层属性标题
        self.properties_title = QLabel("图层属性", self.layer_properties)
        self.properties_title.setProperty("class", "section-title")
        font = self.properties_title.font()
        font.setPointSize(10)
        font.setBold(True)
        self.properties_title.setFont(font)
        self.properties_layout.addWidget(self.properties_title)
        
        # 添加图层基本信息组
        self.layer_info_group = PropertyGroup("图层信息", self.layer_properties)
        
        # 图层名称
        self.name_layout = QHBoxLayout()
        self.name_layout.setContentsMargins(0, 0, 0, 0)
        self.name_layout.setSpacing(6)
        
        self.name_label = QLabel("名称:", self.layer_properties)
        self.name_layout.addWidget(self.name_label)
        
        self.name_value = QLabel("图层 1", self.layer_properties)
        self.name_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.name_layout.addWidget(self.name_value)
        
        name_widget = QWidget(self.layer_properties)
        name_widget.setLayout(self.name_layout)
        self.layer_info_group.add_widget(name_widget)
        
        # 图层类型
        self.type_layout = QHBoxLayout()
        self.type_layout.setContentsMargins(0, 0, 0, 0)
        self.type_layout.setSpacing(6)
        
        self.type_label = QLabel("类型:", self.layer_properties)
        self.type_layout.addWidget(self.type_label)
        
        self.type_value = QLabel("图像图层", self.layer_properties)
        self.type_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.type_layout.addWidget(self.type_value)
        
        type_widget = QWidget(self.layer_properties)
        type_widget.setLayout(self.type_layout)
        self.layer_info_group.add_widget(type_widget)
        
        # 图层透明度
        self.opacity_layout = QHBoxLayout()
        self.opacity_layout.setContentsMargins(0, 0, 0, 0)
        self.opacity_layout.setSpacing(6)
        
        self.opacity_slider = SliderControl("opacity", "透明度", 0, 100, 100, self.layer_properties)
        self.layer_info_group.add_widget(self.opacity_slider)
        
        # 混合模式
        self.blend_mode_layout = QHBoxLayout()
        self.blend_mode_layout.setContentsMargins(0, 0, 0, 0)
        self.blend_mode_layout.setSpacing(6)
        
        self.blend_mode_label = QLabel("混合模式:", self.layer_properties)
        self.blend_mode_layout.addWidget(self.blend_mode_label)
        
        self.blend_mode_combo = QComboBox(self.layer_properties)
        self.blend_mode_combo.addItems([
            "正常", "溶解", "正片叠底", "屏幕", "叠加", "柔光", "强光", 
            "颜色减淡", "颜色加深", "线性减淡", "线性加深", "颜色", "亮度"
        ])
        self.blend_mode_layout.addWidget(self.blend_mode_combo)
        
        blend_mode_widget = QWidget(self.layer_properties)
        blend_mode_widget.setLayout(self.blend_mode_layout)
        self.layer_info_group.add_widget(blend_mode_widget)
        
        self.properties_layout.addWidget(self.layer_info_group)
        self.properties_layout.addStretch(1)
        
        # 将图层列表和属性区域添加到主布局
        self.layout.addWidget(self.layers_list, 1)
        self.layout.addWidget(self.layer_properties, 2)


class AdjustmentsTab(QScrollArea):
    """调整选项卡，包含各种图像调整工具"""
    
    # 调整值改变信号
    adjustment_changed = pyqtSignal(str, float)  # name, value
    
    def __init__(self, parent=None):
        """初始化调整选项卡"""
        super().__init__(parent)
        
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建内容区域
        self.content_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(18, 18, 18, 18)
        self.content_layout.setSpacing(18)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self.content_widget)
        
        # 添加基本调整组
        self._add_basic_adjustments()
        
        # 添加颜色调整组
        self._add_color_adjustments()
        
        # 添加色调直方图调整组
        self._add_tone_adjustments()
    
    def _add_basic_adjustments(self):
        """添加基本调整选项"""
        # 创建基本调整组
        self.basic_group = PropertyGroup("基本调整", self.content_widget)
        
        # 亮度滑块
        self.brightness_slider = SliderControl("brightness", "亮度", -100, 100, 0, self.basic_group)
        self.brightness_slider.value_changed.connect(self._on_adjustment_changed)
        self.basic_group.add_widget(self.brightness_slider)
        
        # 对比度滑块
        self.contrast_slider = SliderControl("contrast", "对比度", -100, 100, 0, self.basic_group)
        self.contrast_slider.value_changed.connect(self._on_adjustment_changed)
        self.basic_group.add_widget(self.contrast_slider)
        
        # 饱和度滑块
        self.saturation_slider = SliderControl("saturation", "饱和度", -100, 100, 0, self.basic_group)
        self.saturation_slider.value_changed.connect(self._on_adjustment_changed)
        self.basic_group.add_widget(self.saturation_slider)
        
        # 清晰度滑块
        self.clarity_slider = SliderControl("clarity", "清晰度", 0, 100, 0, self.basic_group)
        self.clarity_slider.value_changed.connect(self._on_adjustment_changed)
        self.basic_group.add_widget(self.clarity_slider)
        
        # 曝光滑块
        self.exposure_slider = SliderControl("exposure", "曝光", -100, 100, 0, self.basic_group)
        self.exposure_slider.value_changed.connect(self._on_adjustment_changed)
        self.basic_group.add_widget(self.exposure_slider)
        
        self.content_layout.addWidget(self.basic_group)
    
    def _add_color_adjustments(self):
        """添加颜色调整选项"""
        # 创建颜色调整组
        self.color_group = PropertyGroup("颜色调整", self.content_widget)
        
        # 色温滑块
        self.temperature_slider = SliderControl("temperature", "色温", -100, 100, 0, self.color_group)
        self.temperature_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.temperature_slider)
        
        # 色调滑块
        self.tint_slider = SliderControl("tint", "色调", -100, 100, 0, self.color_group)
        self.tint_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.tint_slider)
        
        # 黑色点滑块
        self.blacks_slider = SliderControl("blacks", "黑色点", -100, 100, 0, self.color_group)
        self.blacks_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.blacks_slider)
        
        # 白色点滑块
        self.whites_slider = SliderControl("whites", "白色点", -100, 100, 0, self.color_group)
        self.whites_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.whites_slider)
        
        # HLS颜色调整小标题
        self.hls_title = QLabel("HLS颜色调整", self.color_group)
        self.hls_title.setProperty("class", "subsection-title")
        font = self.hls_title.font()
        font.setPointSize(9)
        font.setBold(True)
        self.hls_title.setFont(font)
        self.color_group.add_widget(self.hls_title)
        
        # 色相滑块
        self.hue_slider = SliderControl("hue", "色相", -180, 180, 0, self.color_group)
        self.hue_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.hue_slider)
        
        # 亮度滑块
        self.lightness_slider = SliderControl("lightness", "亮度", -100, 100, 0, self.color_group)
        self.lightness_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.lightness_slider)
        
        # 饱和度滑块
        self.hls_saturation_slider = SliderControl("hls_saturation", "饱和度", -100, 100, 0, self.color_group)
        self.hls_saturation_slider.value_changed.connect(self._on_adjustment_changed)
        self.color_group.add_widget(self.hls_saturation_slider)
        
        self.content_layout.addWidget(self.color_group)
    
    def _add_tone_adjustments(self):
        """添加色调直方图调整选项"""
        # 创建色调调整组
        self.tone_group = PropertyGroup("色调直方图", self.content_widget)
        
        # 添加直方图显示区域
        self.histogram_widget = QWidget(self.tone_group)
        self.histogram_widget.setMinimumHeight(100)
        self.histogram_widget.setMaximumHeight(100)
        self.histogram_widget.setStyleSheet("background-color: #292952; border-radius: 4px;")
        self.tone_group.add_widget(self.histogram_widget)
        
        # 阴影调整滑块
        self.shadows_slider = SliderControl("shadows", "阴影", -100, 100, 0, self.tone_group)
        self.shadows_slider.value_changed.connect(self._on_adjustment_changed)
        self.tone_group.add_widget(self.shadows_slider)
        
        # 中间调调整滑块
        self.midtones_slider = SliderControl("midtones", "中间调", -100, 100, 0, self.tone_group)
        self.midtones_slider.value_changed.connect(self._on_adjustment_changed)
        self.tone_group.add_widget(self.midtones_slider)
        
        # 高光调整滑块
        self.highlights_slider = SliderControl("highlights", "高光", -100, 100, 0, self.tone_group)
        self.highlights_slider.value_changed.connect(self._on_adjustment_changed)
        self.tone_group.add_widget(self.highlights_slider)
        
        self.content_layout.addWidget(self.tone_group)
    
    def _on_adjustment_changed(self, name, value):
        """处理调整值变化
        
        Args:
            name: 调整项名称
            value: 新值
        """
        # 发出调整变化信号
        self.adjustment_changed.emit(name, value)
        logger.debug(f"调整值变化: {name} -> {value}")


class AiToolsTab(QScrollArea):
    """AI辅助工具选项卡"""
    
    # AI工具执行信号
    ai_tool_executed = pyqtSignal(str, dict)  # tool_name, params
    
    def __init__(self, parent=None):
        """初始化AI工具选项卡"""
        super().__init__(parent)
        
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建内容区域
        self.content_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(18, 18, 18, 18)
        self.content_layout.setSpacing(18)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self.content_widget)
        
        # 添加AI增强组
        self._add_enhancement_tools()
        
        # 添加AI内容工具组
        self._add_content_tools()
        
        # 添加AI风格工具组
        self._add_style_tools()
    
    def _add_enhancement_tools(self):
        """添加AI增强工具"""
        # 创建AI增强工具组
        self.enhancement_group = PropertyGroup("图像增强", self.content_widget)
        
        # 自动增强按钮
        self.auto_enhance_button = QPushButton("自动增强", self.enhancement_group)
        self.auto_enhance_button.setMinimumHeight(36)
        self.auto_enhance_button.clicked.connect(lambda: self._on_ai_tool_selected("auto_enhance"))
        self.enhancement_group.add_widget(self.auto_enhance_button)
        
        # 智能修复按钮
        self.smart_repair_button = QPushButton("智能修复", self.enhancement_group)
        self.smart_repair_button.setMinimumHeight(36)
        self.smart_repair_button.clicked.connect(lambda: self._on_ai_tool_selected("smart_repair"))
        self.enhancement_group.add_widget(self.smart_repair_button)
        
        # 提升画质按钮
        self.upscale_button = QPushButton("提升画质", self.enhancement_group)
        self.upscale_button.setMinimumHeight(36)
        self.upscale_button.clicked.connect(lambda: self._on_ai_tool_selected("upscale"))
        self.enhancement_group.add_widget(self.upscale_button)
        
        # 降噪按钮
        self.denoise_button = QPushButton("降噪处理", self.enhancement_group)
        self.denoise_button.setMinimumHeight(36)
        self.denoise_button.clicked.connect(lambda: self._on_ai_tool_selected("denoise"))
        self.enhancement_group.add_widget(self.denoise_button)
        
        self.content_layout.addWidget(self.enhancement_group)
    
    def _add_content_tools(self):
        """添加AI内容工具"""
        # 创建AI内容工具组
        self.content_group = PropertyGroup("内容处理", self.content_widget)
        
        # 内容移除按钮
        self.remove_object_button = QPushButton("内容移除", self.content_group)
        self.remove_object_button.setMinimumHeight(36)
        self.remove_object_button.clicked.connect(lambda: self._on_ai_tool_selected("remove_object"))
        self.content_group.add_widget(self.remove_object_button)
        
        # 背景替换按钮
        self.replace_bg_button = QPushButton("背景替换", self.content_group)
        self.replace_bg_button.setMinimumHeight(36)
        self.replace_bg_button.clicked.connect(lambda: self._on_ai_tool_selected("replace_background"))
        self.content_group.add_widget(self.replace_bg_button)
        
        # 智能扩展按钮
        self.expand_image_button = QPushButton("智能扩展", self.content_group)
        self.expand_image_button.setMinimumHeight(36)
        self.expand_image_button.clicked.connect(lambda: self._on_ai_tool_selected("expand_image"))
        self.content_group.add_widget(self.expand_image_button)
        
        self.content_layout.addWidget(self.content_group)
    
    def _add_style_tools(self):
        """添加AI风格工具"""
        # 创建AI风格工具组
        self.style_group = PropertyGroup("风格转换", self.content_widget)
        
        # 风格迁移按钮
        self.style_transfer_button = QPushButton("风格迁移", self.style_group)
        self.style_transfer_button.setMinimumHeight(36)
        self.style_transfer_button.clicked.connect(lambda: self._on_ai_tool_selected("style_transfer"))
        self.style_group.add_widget(self.style_transfer_button)
        
        # 数字绘画按钮
        self.digital_art_button = QPushButton("数字绘画", self.style_group)
        self.digital_art_button.setMinimumHeight(36)
        self.digital_art_button.clicked.connect(lambda: self._on_ai_tool_selected("digital_art"))
        self.style_group.add_widget(self.digital_art_button)
        
        # 漫画风格按钮
        self.comic_style_button = QPushButton("漫画风格", self.style_group)
        self.comic_style_button.setMinimumHeight(36)
        self.comic_style_button.clicked.connect(lambda: self._on_ai_tool_selected("comic_style"))
        self.style_group.add_widget(self.comic_style_button)
        
        # 油画风格按钮
        self.oil_painting_button = QPushButton("油画风格", self.style_group)
        self.oil_painting_button.setMinimumHeight(36)
        self.oil_painting_button.clicked.connect(lambda: self._on_ai_tool_selected("oil_painting"))
        self.style_group.add_widget(self.oil_painting_button)
        
        self.content_layout.addWidget(self.style_group)
    
    def _on_ai_tool_selected(self, tool_name, params=None):
        """处理AI工具选择
        
        Args:
            tool_name: 工具名称
            params: 工具参数
        """
        # 发出AI工具执行信号
        self.ai_tool_executed.emit(tool_name, params or {})
        logger.debug(f"AI工具执行: {tool_name} -> {params}")


class MaskTab(QScrollArea):
    """蒙版工具选项卡"""
    
    # 蒙版操作信号
    mask_operation = pyqtSignal(str, dict)  # operation, params
    
    def __init__(self, parent=None):
        """初始化蒙版工具选项卡"""
        super().__init__(parent)
        
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建内容区域
        self.content_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(18, 18, 18, 18)
        self.content_layout.setSpacing(18)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self.content_widget)
        
        # 添加蒙版工具组
        self._add_mask_tools()
        
        # 添加蒙版属性组
        self._add_mask_properties()
        
        # 添加智能选择组
        self._add_smart_selection()
    
    def _add_mask_tools(self):
        """添加蒙版工具"""
        # 创建蒙版工具组
        self.mask_tools_group = PropertyGroup("蒙版工具", self.content_widget)
        
        # 创建工具按钮布局
        tools_layout = QGridLayout()
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(8)
        
        # 添加画笔按钮
        self.brush_button = QToolButton()
        self.brush_button.setText("画笔")
        self.brush_button.setMinimumSize(60, 60)
        self.brush_button.setCheckable(True)
        self.brush_button.clicked.connect(lambda checked: self._on_mask_tool_selected("brush", checked))
        tools_layout.addWidget(self.brush_button, 0, 0)
        
        # 添加橡皮擦按钮
        self.eraser_button = QToolButton()
        self.eraser_button.setText("橡皮擦")
        self.eraser_button.setMinimumSize(60, 60)
        self.eraser_button.setCheckable(True)
        self.eraser_button.clicked.connect(lambda checked: self._on_mask_tool_selected("eraser", checked))
        tools_layout.addWidget(self.eraser_button, 0, 1)
        
        # 添加选择按钮
        self.select_button = QToolButton()
        self.select_button.setText("选择")
        self.select_button.setMinimumSize(60, 60)
        self.select_button.setCheckable(True)
        self.select_button.clicked.connect(lambda checked: self._on_mask_tool_selected("select", checked))
        tools_layout.addWidget(self.select_button, 0, 2)
        
        # 添加魔棒按钮
        self.magic_wand_button = QToolButton()
        self.magic_wand_button.setText("魔棒")
        self.magic_wand_button.setMinimumSize(60, 60)
        self.magic_wand_button.setCheckable(True)
        self.magic_wand_button.clicked.connect(lambda checked: self._on_mask_tool_selected("magic_wand", checked))
        tools_layout.addWidget(self.magic_wand_button, 1, 0)
        
        # 添加填充按钮
        self.fill_button = QToolButton()
        self.fill_button.setText("填充")
        self.fill_button.setMinimumSize(60, 60)
        self.fill_button.setCheckable(True)
        self.fill_button.clicked.connect(lambda checked: self._on_mask_tool_selected("fill", checked))
        tools_layout.addWidget(self.fill_button, 1, 1)
        
        # 添加反转按钮
        self.invert_button = QToolButton()
        self.invert_button.setText("反转")
        self.invert_button.setMinimumSize(60, 60)
        self.invert_button.clicked.connect(lambda: self._on_mask_operation("invert"))
        tools_layout.addWidget(self.invert_button, 1, 2)
        
        tools_widget = QWidget()
        tools_widget.setLayout(tools_layout)
        self.mask_tools_group.add_widget(tools_widget)
        
        self.content_layout.addWidget(self.mask_tools_group)
    
    def _add_mask_properties(self):
        """添加蒙版属性"""
        # 创建蒙版属性组
        self.mask_props_group = PropertyGroup("蒙版属性", self.content_widget)
        
        # 添加画笔大小滑块
        self.brush_size_slider = SliderControl("brush_size", "画笔大小", 1, 100, 20, self.mask_props_group)
        self.brush_size_slider.value_changed.connect(lambda name, value: self._on_mask_property_changed("brush_size", value))
        self.mask_props_group.add_widget(self.brush_size_slider)
        
        # 添加画笔硬度滑块
        self.brush_hardness_slider = SliderControl("brush_hardness", "画笔硬度", 0, 100, 80, self.mask_props_group)
        self.brush_hardness_slider.value_changed.connect(lambda name, value: self._on_mask_property_changed("brush_hardness", value))
        self.mask_props_group.add_widget(self.brush_hardness_slider)
        
        # 添加容差滑块
        self.tolerance_slider = SliderControl("tolerance", "容差", 0, 100, 20, self.mask_props_group)
        self.tolerance_slider.value_changed.connect(lambda name, value: self._on_mask_property_changed("tolerance", value))
        self.mask_props_group.add_widget(self.tolerance_slider)
        
        # 添加羽化滑块
        self.feather_slider = SliderControl("feather", "羽化", 0, 100, 0, self.mask_props_group)
        self.feather_slider.value_changed.connect(lambda name, value: self._on_mask_property_changed("feather", value))
        self.mask_props_group.add_widget(self.feather_slider)
        
        self.content_layout.addWidget(self.mask_props_group)
    
    def _add_smart_selection(self):
        """添加智能选择组"""
        # 创建智能选择组
        self.smart_selection_group = PropertyGroup("智能选择", self.content_widget)
        
        # 添加主体选择按钮
        self.select_subject_button = QPushButton("选择主体", self.smart_selection_group)
        self.select_subject_button.setMinimumHeight(36)
        self.select_subject_button.clicked.connect(lambda: self._on_mask_operation("select_subject"))
        self.smart_selection_group.add_widget(self.select_subject_button)
        
        # 添加天空选择按钮
        self.select_sky_button = QPushButton("选择天空", self.smart_selection_group)
        self.select_sky_button.setMinimumHeight(36)
        self.select_sky_button.clicked.connect(lambda: self._on_mask_operation("select_sky"))
        self.smart_selection_group.add_widget(self.select_sky_button)
        
        # 添加背景选择按钮
        self.select_background_button = QPushButton("选择背景", self.smart_selection_group)
        self.select_background_button.setMinimumHeight(36)
        self.select_background_button.clicked.connect(lambda: self._on_mask_operation("select_background"))
        self.smart_selection_group.add_widget(self.select_background_button)
        
        self.content_layout.addWidget(self.smart_selection_group)
    
    def _on_mask_tool_selected(self, tool_name, checked):
        """处理蒙版工具选择
        
        Args:
            tool_name: 工具名称
            checked: 是否选中
        """
        # 如果选中一个工具，取消选中其他工具
        if checked:
            tool_buttons = [
                self.brush_button, self.eraser_button, self.select_button,
                self.magic_wand_button, self.fill_button
            ]
            
            for button in tool_buttons:
                if button != self.sender():
                    button.setChecked(False)
            
            # 发出选择工具信号
            self.mask_operation.emit("select_tool", {"tool": tool_name})
        else:
            # 如果取消选中，则不选择任何工具
            self.mask_operation.emit("select_tool", {"tool": None})
        
        logger.debug(f"蒙版工具选择: {tool_name} -> {checked}")
    
    def _on_mask_property_changed(self, property_name, value):
        """处理蒙版属性变化
        
        Args:
            property_name: 属性名称
            value: 新值
        """
        # 发出属性变化信号
        self.mask_operation.emit("property_changed", {"property": property_name, "value": value})
        logger.debug(f"蒙版属性变化: {property_name} -> {value}")
    
    def _on_mask_operation(self, operation, params=None):
        """处理蒙版操作
        
        Args:
            operation: 操作名称
            params: 操作参数
        """
        # 发出操作信号
        self.mask_operation.emit(operation, params or {})
        logger.debug(f"蒙版操作: {operation} -> {params}")


class TabbedPanel(QWidget):
    """选项卡式面板，整合图层、调整、AI工具和蒙版功能"""
    
    def __init__(self, parent=None):
        """初始化选项卡面板"""
        super().__init__(parent)
        
        self.setObjectName("tabbedPanel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 创建选项卡组件
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1f1f3a;
            }
            QTabBar::tab {
                background-color: #151526;
                color: #9ca3af;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1f1f3a;
                color: #ffffff;
                border-bottom: 2px solid #4361ee;
            }
            QTabBar::tab:hover:!selected {
                background-color: #292952;
                color: #d1d5db;
            }
        """)
        
        # 创建各选项卡
        self.layers_tab = LayersTab(self)
        self.adjustments_tab = AdjustmentsTab(self)
        self.ai_tools_tab = AiToolsTab(self)
        self.mask_tab = MaskTab(self)
        
        # 添加选项卡
        self.tabs.addTab(self.layers_tab, "图层")
        self.tabs.addTab(self.adjustments_tab, "调整")
        self.tabs.addTab(self.ai_tools_tab, "AI工具")
        self.tabs.addTab(self.mask_tab, "蒙版")
        
        # 将选项卡控件添加到主布局
        self.layout.addWidget(self.tabs) 