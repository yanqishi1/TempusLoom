#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Image Area
Main image editing area
"""

import os
import logging
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, 
    QSizePolicy, QFrame, QGraphicsView, QGraphicsScene,
    QHBoxLayout, QPushButton, QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPixmap, QImage, QColor, QPen, QBrush, 
    QTransform, QWheelEvent, QMouseEvent
)

logger = logging.getLogger(__name__)


class ImageCanvas(QGraphicsView):
    """Canvas for displaying and editing images"""
    
    # Signals
    zoom_changed = pyqtSignal(float)  # zoom_level
    
    def __init__(self, parent=None):
        """Initialize image canvas
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Initialize variables
        self.current_image = None
        self.zoom_level = 1.0
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        
        # Set up scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Set view properties
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.horizontalScrollBar().setStyleSheet("""
            QScrollBar:horizontal {
                height: 12px;
                background: rgba(30, 30, 50, 0.6);
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 0.2);
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                width: 12px;
                background: rgba(30, 30, 50, 0.6);
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 始终居中显示内容
        
        # Create checkerboard background
        self._create_background()
    
    def _create_background(self):
        """Create checkerboard background for transparent images"""
        # Create a transparent background
        self.scene.setBackgroundBrush(QColor(30, 30, 50))
    
    def resizeEvent(self, event):
        """处理视图大小改变事件，确保图片居中
        
        Args:
            event: 大小改变事件
        """
        super().resizeEvent(event)
        if self.current_image:
            self.centerImage()
            
    def centerImage(self):
        """确保图片居中显示"""
        if not self.current_image:
            return
            
        # 获取场景的矩形区域
        scene_rect = self.scene.itemsBoundingRect()
        
        # 只有在图片小于或等于视图大小时才进行居中
        # 如果图片大于视图，则设置合适的滚动区域但不强制居中
        view_rect = self.viewport().rect()
        transform = self.transform()
        
        # 计算变换后的图片尺寸
        transformed_width = scene_rect.width() * transform.m11()
        transformed_height = scene_rect.height() * transform.m22()
        
        # 如果变换后的图片尺寸小于视图，则居中显示
        if transformed_width <= view_rect.width() and transformed_height <= view_rect.height():
            # 将场景矩形居中到视图
            self.setSceneRect(scene_rect)
            self.centerOn(scene_rect.center())
        else:
            # 图片较大时，设置合适的场景矩形和滚动区域
            self.setSceneRect(scene_rect)
            # 不强制居中，让用户可以自由滚动查看
    
    def load_image(self, image_path):
        """Load an image into the canvas
        
        Args:
            image_path: Path to the image file
            
        Returns:
            bool: True if image was loaded successfully
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return False
        
        # Load image
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            logger.error(f"Failed to load image: {image_path}")
            return False
        
        # Clear previous image
        self.scene.clear()
        
        # Save image
        self.current_image = pixmap
        
        # Add image to scene
        self.image_item = self.scene.addPixmap(pixmap)
        self.image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        
        # Reset view
        self.reset_view()
        
        # 确保图片居中
        self.centerImage()
        
        logger.info(f"Image loaded: {image_path}")
        
        # Emit image info for status bar
        self._update_image_info()
        
        return True
    
    def reset_view(self):
        """Reset view to fit image in window"""
        if not self.current_image:
            return
        
        # Fit image in view
        self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
        # Update zoom level
        transform = self.transform()
        self.zoom_level = transform.m11()  # horizontal scale factor
        
        # 确保图片居中
        self.centerImage()
        
        # Emit zoom level
        self.zoom_changed.emit(self.zoom_level * 100)
    
    def _update_image_info(self):
        """Update image information"""
        if not self.current_image:
            return
        
        # Get image info
        width = self.current_image.width()
        height = self.current_image.height()
        
        # Emit info
        logger.debug(f"Image info: {width}x{height}")
    
    def wheelEvent(self, event):
        """Handle wheel events for zooming
        
        Args:
            event: Wheel event
        """
        if not self.current_image:
            return
        
        # 保存当前鼠标位置为缩放中心
        old_pos = self.mapToScene(event.position().toPoint())
        
        # Calculate zoom factor based on wheel delta
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
        
        # Apply zoom
        self.scale(zoom_factor, zoom_factor)
        
        # Update zoom level
        transform = self.transform()
        self.zoom_level = transform.m11()  # horizontal scale factor
        
        # 重新定位场景，让鼠标下的点不变
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
        # 检查图片是否超出视图范围，调整滚动区域
        scene_rect = self.scene.itemsBoundingRect()
        view_rect = self.viewport().rect()
        transformed_width = scene_rect.width() * self.zoom_level
        transformed_height = scene_rect.height() * self.zoom_level
        
        # 设置合适的场景矩形
        self.setSceneRect(scene_rect)
        
        # 如果图片比视图小，确保居中显示
        if transformed_width <= view_rect.width() and transformed_height <= view_rect.height():
            self.centerImage()
        else:
            # 否则确保图片在视图范围内可见，并保持鼠标下的点不变
            self.ensureVisible(QRectF(new_pos.x(), new_pos.y(), 1, 1), 0, 0)
        
        # Emit zoom level (as percentage)
        self.zoom_changed.emit(self.zoom_level * 100)
        
        # Accept event
        event.accept()
    
    def showEvent(self, event):
        """显示事件处理
        
        Args:
            event: 显示事件
        """
        super().showEvent(event)
        # 确保首次显示时图片居中
        if self.current_image:
            self.centerImage()
    
    def resetTransform(self):
        """重写resetTransform方法，确保在重置变换后图片居中"""
        super().resetTransform()
        # 重置后图片居中
        if self.current_image:
            self.centerImage()
    
    def mousePressEvent(self, event):
        """Handle mouse press events for panning
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.MiddleButton or \
           (event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.AltModifier):
            # Start panning (中键或Alt+左键)
            self.panning = True
            self.pan_start_x = event.position().x()
            self.pan_start_y = event.position().y()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for panning
        
        Args:
            event: Mouse event
        """
        if self.panning:
            # Calculate movement
            delta_x = event.position().x() - self.pan_start_x
            delta_y = event.position().y() - self.pan_start_y
            
            # Update pan start position
            self.pan_start_x = event.position().x()
            self.pan_start_y = event.position().y()
            
            # Perform pan using translate instead of scrollbars
            # This is more responsive and works better with the view's transform
            self.translate(delta_x, delta_y)
            
            # 确保场景矩形正确设置
            self.setSceneRect(self.scene.itemsBoundingRect())
            
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for panning
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.MiddleButton or \
           (event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.AltModifier):
            # Stop panning
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """Handle key press events
        
        Args:
            event: Key event
        """
        if event.key() == Qt.Key.Key_Space:
            # Toggle panning mode
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            event.accept()
        elif event.key() == Qt.Key.Key_F:
            # Fit to view
            self.reset_view()
            event.accept()
        elif event.key() == Qt.Key.Key_1:
            # 100% zoom
            self.resetTransform()
            self.zoom_level = 1.0
            self.zoom_changed.emit(self.zoom_level * 100)
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def setZoomLevel(self, percent):
        """设置特定百分比的缩放级别
        
        Args:
            percent: 百分比缩放级别 (100表示原始大小)
        """
        if not self.current_image:
            return
            
        # 保存当前视图中心点在场景中的位置
        old_center = self.mapToScene(self.viewport().rect().center())
        
        # 计算缩放因子
        factor = percent / 100.0
        
        # 重置并应用特定缩放
        self.resetTransform()
        self.scale(factor, factor)
        
        # 更新缩放级别
        self.zoom_level = factor
        
        # 根据图片大小决定是否居中或设置滚动区域
        view_rect = self.viewport().rect()
        scene_rect = self.scene.itemsBoundingRect()
        transformed_width = scene_rect.width() * factor
        transformed_height = scene_rect.height() * factor
        
        # 图片缩放后小于视图大小，居中显示
        if transformed_width <= view_rect.width() and transformed_height <= view_rect.height():
            self.centerImage()
        else:
            # 图片较大时，恢复之前的中心位置并设置滚动区域
            self.setSceneRect(scene_rect)
            self.centerOn(old_center)
        
        # 发出缩放变化信号
        self.zoom_changed.emit(percent)


class ImageArea(QWidget):
    """Main image editing area"""
    
    def __init__(self, parent=None):
        """Initialize image area
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setObjectName("imageArea")
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components"""
        # Create main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 创建缩放控制面板
        self.zoom_panel = QWidget(self)
        self.zoom_panel.setObjectName("zoomPanel")
        self.zoom_panel.setMaximumHeight(40)
        self.zoom_panel.setStyleSheet("""
            #zoomPanel {
                background-color: rgba(30, 30, 50, 0.6);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QSpinBox {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
                min-width: 80px;
            }
        """)
        
        # 缩放面板布局
        self.zoom_layout = QHBoxLayout(self.zoom_panel)
        self.zoom_layout.setContentsMargins(8, 4, 8, 4)
        self.zoom_layout.setSpacing(6)
        
        # 缩小按钮
        self.zoom_out_btn = QPushButton("-", self.zoom_panel)
        self.zoom_out_btn.setMinimumSize(30, 24)
        self.zoom_out_btn.setToolTip("缩小")
        self.zoom_out_btn.clicked.connect(self._on_zoom_out)
        self.zoom_layout.addWidget(self.zoom_out_btn)
        
        # 缩放百分比输入框
        self.zoom_spin = QSpinBox(self.zoom_panel)
        self.zoom_spin.setRange(10, 1000)  # 10% 到 1000%
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # 隐藏上下箭头
        self.zoom_spin.editingFinished.connect(self._on_zoom_spin_changed)
        self.zoom_layout.addWidget(self.zoom_spin)
        
        # 放大按钮
        self.zoom_in_btn = QPushButton("+", self.zoom_panel)
        self.zoom_in_btn.setMinimumSize(30, 24)
        self.zoom_in_btn.setToolTip("放大")
        self.zoom_in_btn.clicked.connect(self._on_zoom_in)
        self.zoom_layout.addWidget(self.zoom_in_btn)
        
        # 预设缩放下拉框
        self.zoom_presets = QComboBox(self.zoom_panel)
        self.zoom_presets.addItem("自适应")
        self.zoom_presets.addItem("25%")
        self.zoom_presets.addItem("50%")
        self.zoom_presets.addItem("75%")
        self.zoom_presets.addItem("100%")
        self.zoom_presets.addItem("150%")
        self.zoom_presets.addItem("200%")
        self.zoom_presets.addItem("300%")
        self.zoom_presets.currentTextChanged.connect(self._on_zoom_preset_changed)
        self.zoom_layout.addWidget(self.zoom_presets)
        
        # 添加弹性空间，使控件靠左对齐
        self.zoom_layout.addStretch(1)
        
        # Create image canvas
        self.canvas = ImageCanvas(self)
        
        # 添加控件到主布局
        self.layout.addWidget(self.canvas)
        self.layout.addWidget(self.zoom_panel)
        
        # Connect signals
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
    
    def load_image(self, image_path):
        """Load image into the area
        
        Args:
            image_path: Path to the image file
            
        Returns:
            bool: True if image was loaded successfully
        """
        return self.canvas.load_image(image_path)
    
    def _on_zoom_changed(self, zoom_level):
        """Handle zoom level changes
        
        Args:
            zoom_level: Zoom level as percentage
        """
        # 更新缩放输入框的值
        self.zoom_spin.setValue(int(zoom_level))
        
        if hasattr(self.parent(), "zoom_info_label"):
            self.parent().zoom_info_label.setText(f"缩放: {zoom_level:.0f}%")
        
        logger.debug(f"Zoom level: {zoom_level:.0f}%")
    
    def _on_zoom_in(self):
        """放大按钮点击事件"""
        if self.canvas.current_image:
            current_zoom = self.zoom_spin.value()
            new_zoom = min(current_zoom * 1.25, 1000)  # 每次放大25%，最大1000%
            self.canvas.setZoomLevel(new_zoom)
    
    def _on_zoom_out(self):
        """缩小按钮点击事件"""
        if self.canvas.current_image:
            current_zoom = self.zoom_spin.value()
            new_zoom = max(current_zoom * 0.8, 10)  # 每次缩小20%，最小10%
            self.canvas.setZoomLevel(new_zoom)
    
    def _on_zoom_spin_changed(self):
        """缩放百分比输入框值改变事件"""
        if self.canvas.current_image:
            new_zoom = self.zoom_spin.value()
            self.canvas.setZoomLevel(new_zoom)
    
    def _on_zoom_preset_changed(self, text):
        """缩放预设下拉框值改变事件"""
        if not self.canvas.current_image:
            return
            
        if text == "自适应":
            self.canvas.reset_view()
        else:
            # 解析百分比值
            try:
                percent = int(text.replace("%", ""))
                self.canvas.setZoomLevel(percent)
            except ValueError:
                pass 