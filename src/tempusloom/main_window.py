#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Main Window
The primary application window implementing the UI design
"""

import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSplitter, QMenu, QMenuBar, QStatusBar, QToolBar, QDockWidget, 
    QApplication, QFileDialog
)
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, QMimeData, QUrl
from PyQt6.QtGui import QAction, QIcon, QPixmap, QFont, QFontDatabase, QImage

from tempusloom.ui.sidebar import Sidebar
from tempusloom.ui.image_area import ImageArea
from tempusloom.ui.properties_panel import PropertiesPanel
from tempusloom.ui.layers_panel import LayersPanel
from tempusloom.ui.toolbar import Toolbar
from tempusloom.ui.styling import get_app_icon, get_menu_icons
from tempusloom.config import Config


class MainWindow(QMainWindow):
    """Main application window for TempusLoom"""
    
    def __init__(self, config=None):
        """Initialize the main window"""
        super().__init__()
        
        self.config = config or Config()
        self.settings = QSettings()
        
        # Set window properties
        self.setWindowTitle("TempusLoom")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(get_app_icon())
        
        # Track current zoom level
        self.current_zoom = 100
        
        # Track current file
        self.current_file_path = None
        
        # Recent files list
        self.recent_files = []
        self._load_recent_files()
        
        # Load icons
        self.icons = get_menu_icons()
        
        # Initialize UI
        self._init_ui()
        self._setup_connections()
        self._restore_state()
    
    def _init_ui(self):
        """Initialize the user interface"""
        # 允许接受拖放
        self.setAcceptDrops(True)
        
        # Set application font
        font_id = QFontDatabase.addApplicationFont(":/fonts/Inter-Regular.ttf")
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            font = QFont(font_family, 10)
        else:
            # Fallback to system font
            font = QFont("Segoe UI", 10)
        QApplication.setFont(font)
        
        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create toolbar
        self.toolbar = Toolbar(self)
        self.addToolBar(self.toolbar)
        
        # Create main content layout
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.content_splitter)
        
        # Create sidebar
        self.sidebar = Sidebar(self)
        self.content_splitter.addWidget(self.sidebar)
        
        # Create central editor area
        self.editor_widget = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_widget)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(0)
        
        # Create image area
        self.image_area = ImageArea(self)
        self.editor_layout.addWidget(self.image_area)
        
        # Create layers panel
        self.layers_panel = LayersPanel(self)
        self.editor_layout.addWidget(self.layers_panel)
        
        # Add the editor widget to the splitter
        self.content_splitter.addWidget(self.editor_widget)
        
        # Create properties panel
        self.properties_panel = PropertiesPanel(self)
        self.content_splitter.addWidget(self.properties_panel)
        
        # Set initial sizes for the splitter
        self.content_splitter.setSizes([240, 800, 300])
        
        # Create status bar
        self._create_status_bar()
    
    def _create_menu_bar(self):
        """Create the application menu bar"""
        self.menu_bar = self.menuBar()
        
        # Set menu bar styling
        self.menu_bar.setFont(QFont("Segoe UI", 10))
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #1f1f3a;
                color: #ffffff;
                padding: 4px;
                spacing: 6px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QMenuBar::item:pressed {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QMenu {
                background-color: #292952;
                color: #ffffff;
                border: 1px solid #323252;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 28px 6px 24px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QMenu::separator {
                height: 1px;
                background-color: #323252;
                margin: 4px 8px;
            }
            QMenu::icon {
                margin-left: 8px;
            }
        """)
        
        # File menu
        self.file_menu = self.menu_bar.addMenu("文件")
        
        new_action = QAction(self.icons.get('new'), "新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.setStatusTip("创建一个新文件")
        self.file_menu.addAction(new_action)
        
        open_action = QAction(self.icons.get('open'), "打开", self)
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("打开一个已有文件")
        self.file_menu.addAction(open_action)
        
        # Recent files submenu
        self.recent_menu = QMenu("最近文件", self)
        self.recent_menu.setIcon(QIcon())
        self.file_menu.addMenu(self.recent_menu)
        self._update_recent_files_menu()
        
        self.file_menu.addSeparator()
        
        save_action = QAction(self.icons.get('save'), "保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setStatusTip("保存当前文件")
        self.file_menu.addAction(save_action)
        
        save_as_action = QAction(self.icons.get('saveas'), "另存为", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.setStatusTip("将当前文件另存为新文件")
        self.file_menu.addAction(save_as_action)
        
        export_action = QAction(self.icons.get('export'), "导出", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setStatusTip("导出为其他格式")
        self.file_menu.addAction(export_action)
        
        # Export submenu
        self.export_menu = QMenu("导出为", self)
        self.export_menu.setIcon(QIcon())
        self.file_menu.addMenu(self.export_menu)
        
        export_jpg = QAction("JPG格式", self)
        self.export_menu.addAction(export_jpg)
        
        export_png = QAction("PNG格式", self)
        self.export_menu.addAction(export_png)
        
        export_tiff = QAction("TIFF格式", self)
        self.export_menu.addAction(export_tiff)
        
        export_pdf = QAction("PDF格式", self)
        self.export_menu.addAction(export_pdf)
        
        self.file_menu.addSeparator()
        
        print_action = QAction(self.icons.get('print'), "打印", self)
        print_action.setShortcut("Ctrl+P")
        print_action.setStatusTip("打印当前图像")
        self.file_menu.addAction(print_action)
        
        self.file_menu.addSeparator()
        
        exit_action = QAction(self.icons.get('exit'), "退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        exit_action.setStatusTip("退出应用程序")
        self.file_menu.addAction(exit_action)
        
        # Edit menu
        self.edit_menu = self.menu_bar.addMenu("编辑")
        
        undo_action = QAction(self.icons.get('undo'), "撤销", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.setStatusTip("撤销上一步操作")
        self.edit_menu.addAction(undo_action)
        
        redo_action = QAction(self.icons.get('redo'), "重做", self)
        redo_action.setShortcut("Ctrl+Shift+Z")
        redo_action.setStatusTip("重做上一步操作")
        self.edit_menu.addAction(redo_action)
        
        self.edit_menu.addSeparator()
        
        cut_action = QAction(self.icons.get('cut'), "剪切", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.setStatusTip("剪切所选内容")
        self.edit_menu.addAction(cut_action)
        
        copy_action = QAction(self.icons.get('copy'), "复制", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.setStatusTip("复制所选内容")
        self.edit_menu.addAction(copy_action)
        
        paste_action = QAction(self.icons.get('paste'), "粘贴", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.setStatusTip("粘贴剪贴板内容")
        self.edit_menu.addAction(paste_action)
        
        self.edit_menu.addSeparator()
        
        select_all_action = QAction(self.icons.get('select_all'), "全选", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.setStatusTip("选择所有内容")
        self.edit_menu.addAction(select_all_action)
        
        deselect_action = QAction(self.icons.get('deselect'), "取消选择", self)
        deselect_action.setShortcut("Ctrl+D")
        deselect_action.setStatusTip("取消所有选择")
        self.edit_menu.addAction(deselect_action)
        
        self.edit_menu.addSeparator()
        
        preferences_action = QAction(self.icons.get('preferences'), "首选项", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.setStatusTip("打开首选项设置")
        self.edit_menu.addAction(preferences_action)
        
        # View menu
        self.view_menu = self.menu_bar.addMenu("视图")
        
        zoom_in_action = QAction(self.icons.get('zoom_in'), "放大", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.setStatusTip("放大视图")
        self.view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction(self.icons.get('zoom_out'), "缩小", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.setStatusTip("缩小视图")
        self.view_menu.addAction(zoom_out_action)
        
        zoom_fit_action = QAction(self.icons.get('zoom_fit'), "适合窗口", self)
        zoom_fit_action.setShortcut("Ctrl+0")
        zoom_fit_action.setStatusTip("缩放以适合窗口")
        self.view_menu.addAction(zoom_fit_action)
        
        zoom_100_action = QAction(self.icons.get('zoom_100'), "实际大小", self)
        zoom_100_action.setShortcut("Ctrl+1")
        zoom_100_action.setStatusTip("以100%比例显示")
        self.view_menu.addAction(zoom_100_action)
        
        self.view_menu.addSeparator()
        
        # Panels submenu
        self.panels_menu = QMenu("面板", self)
        self.panels_menu.setIcon(QIcon())
        self.view_menu.addMenu(self.panels_menu)
        
        sidebar_action = QAction("侧边栏", self)
        sidebar_action.setCheckable(True)
        sidebar_action.setChecked(True)
        self.panels_menu.addAction(sidebar_action)
        
        layers_action = QAction("图层面板", self)
        layers_action.setCheckable(True)
        layers_action.setChecked(True)
        self.panels_menu.addAction(layers_action)
        
        properties_action = QAction("属性面板", self)
        properties_action.setCheckable(True)
        properties_action.setChecked(True)
        self.panels_menu.addAction(properties_action)
        
        toolbar_action = QAction("工具栏", self)
        toolbar_action.setCheckable(True)
        toolbar_action.setChecked(True)
        self.panels_menu.addAction(toolbar_action)
        
        self.view_menu.addSeparator()
        
        fullscreen_action = QAction(self.icons.get('fullscreen'), "全屏模式", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        fullscreen_action.setStatusTip("切换全屏模式")
        self.view_menu.addAction(fullscreen_action)
        
        # Tools menu
        self.tools_menu = self.menu_bar.addMenu("工具")
        
        selection_tool_action = QAction(self.icons.get('select'), "选择工具", self)
        selection_tool_action.setShortcut("S")
        self.tools_menu.addAction(selection_tool_action)
        
        crop_tool_action = QAction(self.icons.get('crop'), "裁剪工具", self)
        crop_tool_action.setShortcut("C")
        self.tools_menu.addAction(crop_tool_action)
        
        brush_tool_action = QAction(self.icons.get('brush'), "笔刷工具", self)
        brush_tool_action.setShortcut("B")
        self.tools_menu.addAction(brush_tool_action)
        
        eraser_tool_action = QAction(self.icons.get('eraser'), "橡皮擦工具", self)
        eraser_tool_action.setShortcut("E")
        self.tools_menu.addAction(eraser_tool_action)
        
        text_tool_action = QAction(self.icons.get('text'), "文本工具", self)
        text_tool_action.setShortcut("T")
        self.tools_menu.addAction(text_tool_action)
        
        self.tools_menu.addSeparator()
        
        transform_tool_action = QAction(self.icons.get('transform'), "变换工具", self)
        transform_tool_action.setShortcut("Ctrl+T")
        self.tools_menu.addAction(transform_tool_action)
        
        # Adjust menu
        self.adjust_menu = self.menu_bar.addMenu("调整")
        
        brightness_contrast_action = QAction(QIcon(), "亮度/对比度", self)
        self.adjust_menu.addAction(brightness_contrast_action)
        
        hue_saturation_action = QAction(QIcon(), "色相/饱和度", self)
        self.adjust_menu.addAction(hue_saturation_action)
        
        color_balance_action = QAction(QIcon(), "色彩平衡", self)
        self.adjust_menu.addAction(color_balance_action)
        
        levels_action = QAction(QIcon(), "色阶", self)
        self.adjust_menu.addAction(levels_action)
        
        curves_action = QAction(QIcon(), "曲线", self)
        self.adjust_menu.addAction(curves_action)
        
        exposure_action = QAction(QIcon(), "曝光", self)
        self.adjust_menu.addAction(exposure_action)
        
        # Filter menu
        self.filter_menu = self.menu_bar.addMenu("滤镜")
        
        sharpen_action = QAction(QIcon(), "锐化", self)
        self.filter_menu.addAction(sharpen_action)
        
        blur_action = QAction(QIcon(), "模糊", self)
        self.filter_menu.addAction(blur_action)
        
        noise_action = QAction(QIcon(), "噪点", self)
        self.filter_menu.addAction(noise_action)
        
        # Filter submenus
        artistic_menu = QMenu("艺术效果", self)
        artistic_menu.setIcon(QIcon())
        self.filter_menu.addMenu(artistic_menu)
        
        sketch_action = QAction(QIcon(), "素描", self)
        artistic_menu.addAction(sketch_action)
        
        watercolor_action = QAction(QIcon(), "水彩", self)
        artistic_menu.addAction(watercolor_action)
        
        oil_painting_action = QAction(QIcon(), "油画", self)
        artistic_menu.addAction(oil_painting_action)
        
        # AI Tools menu
        self.ai_menu = self.menu_bar.addMenu("AI工具")
        
        auto_enhance_action = QAction(QIcon(), "自动增强", self)
        self.ai_menu.addAction(auto_enhance_action)
        
        smart_repair_action = QAction(QIcon(), "智能修复", self)
        self.ai_menu.addAction(smart_repair_action)
        
        object_removal_action = QAction(QIcon(), "对象移除", self)
        self.ai_menu.addAction(object_removal_action)
        
        background_replacement_action = QAction(QIcon(), "背景替换", self)
        self.ai_menu.addAction(background_replacement_action)
        
        style_transfer_action = QAction(QIcon(), "风格迁移", self)
        self.ai_menu.addAction(style_transfer_action)
        
        # Plugins menu
        self.plugins_menu = self.menu_bar.addMenu("插件")
        
        manage_plugins_action = QAction(QIcon(), "管理插件", self)
        self.plugins_menu.addAction(manage_plugins_action)
        
        self.plugins_menu.addSeparator()
        
        # Help menu
        self.help_menu = self.menu_bar.addMenu("帮助")
        
        documentation_action = QAction(QIcon(), "文档", self)
        documentation_action.setShortcut("F1")
        self.help_menu.addAction(documentation_action)
        
        tutorials_action = QAction(QIcon(), "教程", self)
        self.help_menu.addAction(tutorials_action)
        
        check_updates_action = QAction(QIcon(), "检查更新", self)
        self.help_menu.addAction(check_updates_action)
        
        self.help_menu.addSeparator()
        
        about_action = QAction(QIcon(), "关于 TempusLoom", self)
        self.help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add image info to status bar
        self.image_info_label = QLabel("图像信息: ")
        self.status_bar.addWidget(self.image_info_label)
        
        # Add zoom info to status bar
        self.zoom_info_label = QLabel("缩放: 100%")
        self.status_bar.addPermanentWidget(self.zoom_info_label)
    
    def _setup_connections(self):
        """Set up signal-slot connections"""
        # Connect menu actions
        # File menu connections
        self.file_menu.actions()[0].triggered.connect(self._on_new_file)  # New
        self.file_menu.actions()[1].triggered.connect(self._on_open_file)  # Open
        self.file_menu.actions()[4].triggered.connect(self._on_save_file)  # Save
        self.file_menu.actions()[5].triggered.connect(self._on_save_as)    # Save As
        
        # View menu connections
        zoom_in_action = self.view_menu.actions()[0]  # Zoom in
        zoom_in_action.triggered.connect(lambda: self._on_zoom(1.1))
        
        zoom_out_action = self.view_menu.actions()[1]  # Zoom out
        zoom_out_action.triggered.connect(lambda: self._on_zoom(0.9))
        
        zoom_fit_action = self.view_menu.actions()[2]  # Zoom to fit
        zoom_fit_action.triggered.connect(self._on_zoom_fit)
        
        zoom_100_action = self.view_menu.actions()[3]  # Zoom 100%
        zoom_100_action.triggered.connect(self._on_zoom_reset)
        
        # Toggle panel visibility
        panels_menu = self.view_menu.actions()[5].menu()  # Panels submenu
        
        sidebar_action = panels_menu.actions()[0]  # Sidebar
        sidebar_action.triggered.connect(lambda checked: self._toggle_panel_visibility(self.sidebar, checked))
        
        layers_action = panels_menu.actions()[1]  # Layers panel
        layers_action.triggered.connect(lambda checked: self._toggle_panel_visibility(self.layers_panel, checked))
        
        properties_action = panels_menu.actions()[2]  # Properties panel
        properties_action.triggered.connect(lambda checked: self._toggle_panel_visibility(self.properties_panel, checked))
        
        toolbar_action = panels_menu.actions()[3]  # Toolbar
        toolbar_action.triggered.connect(lambda checked: self._toggle_panel_visibility(self.toolbar, checked))
        
        # Fullscreen toggle
        fullscreen_action = self.view_menu.actions()[7]  # Fullscreen
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        
        # Connect signals from various components
        pass

    def _on_new_file(self):
        """Handler for creating a new file"""
        self.statusBar().showMessage("创建新文件", 3000)
        # TODO: Implement new file creation
        
    def _on_open_file(self):
        """Handler for opening a file"""
        file_filter = "图像文件 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;所有文件 (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开图像文件", "", file_filter
        )
        
        if file_path:
            self.statusBar().showMessage(f"正在打开文件: {file_path}", 3000)
            
            # 加载图像到图像区域
            if self.image_area.load_image(file_path):
                # 更新当前文件路径
                self.current_file_path = file_path
                # 更新窗口标题
                self.setWindowTitle(f"TempusLoom - {os.path.basename(file_path)}")
                # 添加到最近文件
                self._add_to_recent_files(file_path)
                # 更新图像信息
                self._update_image_info(file_path)
            else:
                self.statusBar().showMessage(f"无法加载图像: {file_path}", 3000)
        
    def _on_save_file(self):
        """Handler for saving a file"""
        # If no file is currently open/set, call save as
        # TODO: Check if a file is already open and has a path
        self._on_save_as()
        
    def _on_save_as(self):
        """Handler for saving a file as"""
        file_filter = "PNG (*.png);;JPEG (*.jpg *.jpeg);;TIFF (*.tif *.tiff);;BMP (*.bmp)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "保存图像文件", "", file_filter
        )
        
        if file_path:
            self.statusBar().showMessage(f"正在保存文件: {file_path}", 3000)
            # TODO: Implement actual file saving
            # self._save_image(file_path)

    def _on_zoom(self, factor):
        """Handle zoom in/out
        
        Args:
            factor: Zoom factor (>1 to zoom in, <1 to zoom out)
        """
        if hasattr(self.image_area.canvas, 'scale'):
            # 直接在画布上应用缩放
            self.image_area.canvas.scale(factor, factor)
            
            # 更新缩放级别
            transform = self.image_area.canvas.transform()
            zoom_level = transform.m11() * 100  # 横向缩放因子(转换为百分比)
            
            # 更新显示
            self.current_zoom = zoom_level
            self.zoom_info_label.setText(f"缩放: {int(zoom_level)}%")
            self.statusBar().showMessage(f"缩放级别: {int(zoom_level)}%", 3000)
        
    def _on_zoom_fit(self):
        """Zoom to fit image to window"""
        if hasattr(self.image_area.canvas, 'reset_view'):
            # 调用画布的适合视图方法
            self.image_area.canvas.reset_view()
            
            # 更新当前缩放级别
            transform = self.image_area.canvas.transform()
            zoom_level = transform.m11() * 100
            self.current_zoom = zoom_level
            
            self.zoom_info_label.setText(f"缩放: 适合窗口")
            self.statusBar().showMessage("缩放适合窗口", 3000)
        
    def _on_zoom_reset(self):
        """Reset zoom to 100%"""
        if hasattr(self.image_area.canvas, 'resetTransform'):
            # 重置缩放为100%
            self.image_area.canvas.resetTransform()
            
            # 更新当前缩放级别
            self.current_zoom = 100
            self.zoom_info_label.setText("缩放: 100%")
            self.statusBar().showMessage("缩放重置为 100%", 3000)
        
    def _toggle_panel_visibility(self, panel, visible):
        """Toggle the visibility of a panel
        
        Args:
            panel: Panel widget to toggle
            visible: Whether to show or hide
        """
        panel.setVisible(visible)
        self.statusBar().showMessage(f"面板已{'显示' if visible else '隐藏'}", 3000)
        
    def _toggle_fullscreen(self, fullscreen):
        """Toggle fullscreen mode
        
        Args:
            fullscreen: Whether to enter or exit fullscreen
        """
        if fullscreen:
            self.showFullScreen()
            self.statusBar().showMessage("进入全屏模式", 3000)
        else:
            self.showNormal()
            self.statusBar().showMessage("退出全屏模式", 3000)
    
    def _restore_state(self):
        """Restore window state from settings"""
        # Restore window geometry
        geometry = self.settings.value("mainwindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Restore window state
        state = self.settings.value("mainwindow/state")
        if state:
            self.restoreState(state)
        
        # Restore splitter sizes
        splitter_sizes = self.settings.value("mainwindow/splitter_sizes")
        if splitter_sizes:
            self.content_splitter.setSizes(splitter_sizes)
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Save window geometry and state
        self.settings.setValue("mainwindow/geometry", self.saveGeometry())
        self.settings.setValue("mainwindow/state", self.saveState())
        self.settings.setValue("mainwindow/splitter_sizes", self.content_splitter.sizes())
        
        # Accept the event
        event.accept()

    def _load_recent_files(self):
        """Load recent files from settings"""
        recent_files = self.settings.value("recent_files", [])
        if recent_files:
            self.recent_files = recent_files[:10]  # Keep only the 10 most recent files
        
    def _update_recent_files_menu(self):
        """Update the recent files menu"""
        # Clear existing menu items
        self.recent_menu.clear()
        
        if not self.recent_files:
            no_recent = QAction("无最近文件", self)
            no_recent.setEnabled(False)
            self.recent_menu.addAction(no_recent)
            return
        
        # Add recent files to menu
        for file_path in self.recent_files:
            action = QAction(os.path.basename(file_path), self)
            action.setData(file_path)
            action.setStatusTip(file_path)
            action.triggered.connect(self._open_recent_file)
            self.recent_menu.addAction(action)
        
        # Add separator and clear action
        self.recent_menu.addSeparator()
        clear_action = QAction("清除最近文件", self)
        clear_action.triggered.connect(self._clear_recent_files)
        self.recent_menu.addAction(clear_action)
        
    def _add_to_recent_files(self, file_path):
        """Add a file to the recent files list
        
        Args:
            file_path: Path to the file
        """
        # Remove if already exists
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        
        # Add to the beginning of the list
        self.recent_files.insert(0, file_path)
        
        # Keep only the 10 most recent
        self.recent_files = self.recent_files[:10]
        
        # Save to settings
        self.settings.setValue("recent_files", self.recent_files)
        
        # Update the menu
        self._update_recent_files_menu()
        
    def _open_recent_file(self):
        """Open a file from the recent files menu"""
        action = self.sender()
        if action:
            file_path = action.data()
            if os.path.exists(file_path):
                self.statusBar().showMessage(f"正在打开文件: {file_path}", 3000)
                
                # 加载图像
                if self.image_area.load_image(file_path):
                    # 更新当前文件路径
                    self.current_file_path = file_path
                    # 更新窗口标题
                    self.setWindowTitle(f"TempusLoom - {os.path.basename(file_path)}")
                    # 更新图像信息
                    self._update_image_info(file_path)
                else:
                    self.statusBar().showMessage(f"无法加载图像: {file_path}", 3000)
            else:
                # Remove from recent files if the file doesn't exist
                self.statusBar().showMessage(f"文件不存在: {file_path}", 3000)
                self.recent_files.remove(file_path)
                self.settings.setValue("recent_files", self.recent_files)
                self._update_recent_files_menu()
            
    def _clear_recent_files(self):
        """Clear the recent files list"""
        self.recent_files = []
        self.settings.setValue("recent_files", self.recent_files)
        self._update_recent_files_menu()
        self.statusBar().showMessage("最近文件已清除", 3000)

    def _update_image_info(self, file_path):
        """更新图像信息
        
        Args:
            file_path: 图像文件路径
        """
        # 获取图像信息
        image = QImage(file_path)
        if not image.isNull():
            width = image.width()
            height = image.height()
            depth = image.depth()
            size_kb = os.path.getsize(file_path) / 1024
            
            # 更新状态栏信息
            self.image_info_label.setText(f"图像信息: {width}x{height} 像素, {depth}位, {size_kb:.1f} KB")

    def dragEnterEvent(self, event):
        """处理拖动进入事件
        
        Args:
            event: 拖动事件
        """
        # 检查是否为文件URL
        if event.mimeData().hasUrls():
            # 获取拖动的URLs
            urls = event.mimeData().urls()
            # 检查是否有URL，以及第一个URL是否为本地文件
            if urls and urls[0].isLocalFile():
                # 获取文件路径
                file_path = urls[0].toLocalFile()
                # 检查文件类型
                ext = os.path.splitext(file_path)[1].lower()
                # 检查是否为支持的图像文件
                if ext in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp']:
                    event.acceptProposedAction()
                    return
        
        # 如果不是图像文件，拒绝拖放
        event.ignore()

    def dropEvent(self, event):
        """处理拖放事件
        
        Args:
            event: 拖放事件
        """
        # 获取拖放的URLs
        urls = event.mimeData().urls()
        if urls:
            # 获取第一个文件路径（只处理单个文件）
            file_path = urls[0].toLocalFile()
            # 尝试加载图像
            if self.image_area.load_image(file_path):
                # 更新当前文件路径
                self.current_file_path = file_path
                # 更新窗口标题
                self.setWindowTitle(f"TempusLoom - {os.path.basename(file_path)}")
                # 添加到最近文件
                self._add_to_recent_files(file_path)
                # 更新图像信息
                self._update_image_info(file_path)
                # 显示状态信息
                self.statusBar().showMessage(f"图像已加载: {file_path}", 3000)
            else:
                self.statusBar().showMessage(f"无法加载图像: {file_path}", 3000)
        
        # 接受拖放操作
        event.acceptProposedAction() 