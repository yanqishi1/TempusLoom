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
from tempusloom.ui.tabbed_panel import TabbedPanel
from tempusloom.ui.toolbar import Toolbar
from tempusloom.ui.styling import get_app_icon, get_menu_icons
from tempusloom.config import Config

class MainWindow(QMainWindow):
    """
    TempusLoom主窗口
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TempusLoom")
        
        # 设置主窗口尺寸
        desktop = QApplication.primaryScreen().availableGeometry()
        width = int(desktop.width() * 0.8)
        height = int(desktop.height() * 0.8)
        self.resize(width, height)
        
        # 设置应用图标
        # self.setWindowIcon(QIcon(":/icons/app.png"))
        
        # 初始化UI
        self._init_ui()
        
        # 加载样式表
        self._load_stylesheet()
        
        # 设置信号连接
        self._setup_connections()
    
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
        
        # Add the editor widget to the splitter
        self.content_splitter.addWidget(self.editor_widget)
        
        # Create tabbed panel (replacing separate properties and layers panels)
        self.tabbed_panel = TabbedPanel(self)
        self.content_splitter.addWidget(self.tabbed_panel)
        
        # Set initial sizes for the splitter (increase the last value to make tabbed panel wider and visible)
        self.content_splitter.setSizes([200, 600, 350])
        
        # Create status bar
        self._create_status_bar()
    
    def _load_stylesheet(self):
        """加载应用样式表"""
        style_file = os.path.join(os.path.dirname(__file__), '..', 'resources', 'style.qss')
        if os.path.exists(style_file):
            with open(style_file, 'r') as f:
                self.setStyleSheet(f.read())

    def _create_menu_bar(self):
        """创建菜单栏"""
        # 文件菜单
        self.file_menu = self.menuBar().addMenu("文件")
        
        # 新建动作
        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        self.file_menu.addAction(new_action)
        
        # 打开动作
        open_action = QAction("打开", self)
        open_action.setShortcut("Ctrl+O")
        self.file_menu.addAction(open_action)
        
        self.file_menu.addSeparator()
        
        # 保存动作
        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        self.file_menu.addAction(save_action)
        
        # 另存为动作
        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        self.file_menu.addAction(save_as_action)
        
        self.file_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = self.menuBar().addMenu("编辑")
        
        # 撤销动作
        undo_action = QAction("撤销", self)
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)
        
        # 重做动作
        redo_action = QAction("重做", self)
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        # 剪切动作
        cut_action = QAction("剪切", self)
        cut_action.setShortcut("Ctrl+X")
        edit_menu.addAction(cut_action)
        
        # 复制动作
        copy_action = QAction("复制", self)
        copy_action.setShortcut("Ctrl+C")
        edit_menu.addAction(copy_action)
        
        # 粘贴动作
        paste_action = QAction("粘贴", self)
        paste_action.setShortcut("Ctrl+V")
        edit_menu.addAction(paste_action)
        
        # 视图菜单
        self.view_menu = self.menuBar().addMenu("视图")
        
        # 放大动作
        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut("Ctrl++")
        self.view_menu.addAction(zoom_in_action)
        
        # 缩小动作
        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut("Ctrl+-")
        self.view_menu.addAction(zoom_out_action)
        
        # 适应窗口动作
        zoom_fit_action = QAction("适应窗口", self)
        zoom_fit_action.setShortcut("Ctrl+0")
        self.view_menu.addAction(zoom_fit_action)
        
        self.view_menu.addSeparator()
        
        # 显示网格动作
        show_grid_action = QAction("显示网格", self)
        show_grid_action.setCheckable(True)
        self.view_menu.addAction(show_grid_action)
        
        self.view_menu.addSeparator()
        
        # 面板菜单
        panels_menu = QMenu("面板", self)
        
        # 侧边栏显示/隐藏
        sidebar_action = QAction("侧边栏", self)
        sidebar_action.setCheckable(True)
        sidebar_action.setChecked(True)
        panels_menu.addAction(sidebar_action)
        
        # 选项卡面板显示/隐藏
        tabbed_panel_action = QAction("选项卡面板", self)
        tabbed_panel_action.setCheckable(True)
        tabbed_panel_action.setChecked(True)
        panels_menu.addAction(tabbed_panel_action)
        
        # 图层选项卡
        layers_tab_action = QAction("图层选项卡", self)
        layers_tab_action.setCheckable(True)
        layers_tab_action.setChecked(False)
        panels_menu.addAction(layers_tab_action)
        
        # 调整选项卡
        adjustments_tab_action = QAction("调整选项卡", self)
        adjustments_tab_action.setCheckable(True)
        adjustments_tab_action.setChecked(False)
        panels_menu.addAction(adjustments_tab_action)
        
        # AI工具选项卡
        ai_tools_tab_action = QAction("AI工具选项卡", self)
        ai_tools_tab_action.setCheckable(True)
        ai_tools_tab_action.setChecked(False)
        panels_menu.addAction(ai_tools_tab_action)
        
        # 蒙版选项卡
        mask_tab_action = QAction("蒙版选项卡", self)
        mask_tab_action.setCheckable(True)
        mask_tab_action.setChecked(False)
        panels_menu.addAction(mask_tab_action)
        
        # 工具栏显示/隐藏
        toolbar_action = QAction("工具栏", self)
        toolbar_action.setCheckable(True)
        toolbar_action.setChecked(True)
        panels_menu.addAction(toolbar_action)
        
        self.view_menu.addMenu(panels_menu)
        
        self.view_menu.addSeparator()
        
        # 全屏显示
        fullscreen_action = QAction("全屏", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        self.view_menu.addAction(fullscreen_action)
        
        # 帮助菜单
        help_menu = self.menuBar().addMenu("帮助")
        
        # 关于动作
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.statusBar().showMessage("就绪")
    
    def _setup_connections(self):
        """设置信号连接"""
        # 从视图菜单中获取面板菜单项
        panels_menu = self.view_menu.actions()[4].menu()  # 第五个操作是面板菜单
        
        # 获取特定的面板菜单项
        sidebar_action = panels_menu.actions()[0]  # 侧边栏
        tabbed_panel_action = panels_menu.actions()[1]  # 选项卡面板
        layers_tab_action = panels_menu.actions()[2]  # 图层选项卡
        adjustments_tab_action = panels_menu.actions()[3]  # 调整选项卡
        ai_tools_tab_action = panels_menu.actions()[4]  # AI工具选项卡
        mask_tab_action = panels_menu.actions()[5]  # 蒙版选项卡
        toolbar_action = panels_menu.actions()[6]  # 工具栏
        
        # 连接侧边栏显示/隐藏
        sidebar_action.triggered.connect(self._toggle_sidebar)
        
        # 连接选项卡面板显示/隐藏
        tabbed_panel_action.triggered.connect(self._toggle_tabbed_panel)
        
        # 连接特定选项卡的显示
        layers_tab_action.triggered.connect(lambda: self._show_specific_tab(0))  # 图层选项卡
        adjustments_tab_action.triggered.connect(lambda: self._show_specific_tab(1))  # 调整选项卡
        ai_tools_tab_action.triggered.connect(lambda: self._show_specific_tab(2))  # AI工具选项卡
        mask_tab_action.triggered.connect(lambda: self._show_specific_tab(3))  # 蒙版选项卡
        
        # 连接工具栏显示/隐藏
        toolbar_action.triggered.connect(self._toggle_toolbar)
        
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
        
        # Fullscreen toggle
        fullscreen_action = self.view_menu.actions()[7]  # Fullscreen
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
    
    def _toggle_panel_visibility(self, panel, visible):
        """切换面板可见性"""
        panel.setVisible(visible)
        
    def _toggle_sidebar(self, checked):
        """切换侧边栏显示/隐藏"""
        self.sidebar.setVisible(checked)
        
    def _toggle_tabbed_panel(self, checked):
        """切换选项卡面板显示/隐藏"""
        self.tabbed_panel.setVisible(checked)
        
    def _show_specific_tab(self, tab_index):
        """显示特定的选项卡并确保面板可见"""
        # 确保选项卡面板是可见的
        panels_menu = self.view_menu.actions()[4].menu()
        tabbed_panel_action = panels_menu.actions()[1]
        
        # 如果面板不可见，需要先使其可见
        if not self.tabbed_panel.isVisible():
            self.tabbed_panel.setVisible(True)
            tabbed_panel_action.setChecked(True)
        
        # 显示特定选项卡
        self.tabbed_panel.setCurrentIndex(tab_index)
        
        # 更新菜单项的状态
        layers_tab_action = panels_menu.actions()[2]
        adjustments_tab_action = panels_menu.actions()[3]
        ai_tools_tab_action = panels_menu.actions()[4]
        mask_tab_action = panels_menu.actions()[5]
        
        # 重置所有标签页的选中状态
        layers_tab_action.setChecked(tab_index == 0)
        adjustments_tab_action.setChecked(tab_index == 1)
        ai_tools_tab_action.setChecked(tab_index == 2)
        mask_tab_action.setChecked(tab_index == 3)
    
    def _toggle_toolbar(self, checked):
        """切换工具栏显示/隐藏"""
        self.toolbar.setVisible(checked)
        
    def _toggle_fullscreen(self):
        """切换全屏显示"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    # 帮助菜单相关方法
    def _on_about(self):
        """显示关于对话框"""
        # 实现关于对话框
    
    def _on_new_file(self):
        # Implementation of _on_new_file method
        pass
    
    def _on_open_file(self):
        # Implementation of _on_open_file method
        pass
    
    def _on_save_file(self):
        # Implementation of _on_save_file method
        pass
    
    def _on_save_as(self):
        # Implementation of _on_save_as method
        pass
    
    def _on_zoom(self, factor):
        # Implementation of _on_zoom method
        pass
    
    def _on_zoom_fit(self):
        # Implementation of _on_zoom_fit method
        pass
    
    def _on_zoom_reset(self):
        # Implementation of _on_zoom_reset method
        pass

    def _toggle_sidebar(self, checked):
        """切换侧边栏显示/隐藏"""
        self.sidebar.setVisible(checked)
        
    def _toggle_tabbed_panel(self, checked):
        """切换选项卡面板显示/隐藏"""
        self.tabbed_panel.setVisible(checked)
        
    def _show_specific_tab(self, index):
        """显示特定的选项卡并确保选项卡面板可见"""
        if index < self.tabbed_panel.count():
            self.tabbed_panel.setCurrentIndex(index)
            self.tabbed_panel.setVisible(True)
            
            # 更新菜单项状态
            panels_menu = self.view_menu.actions()[4].menu()
            tabbed_panel_action = panels_menu.actions()[1]
            tabbed_panel_action.setChecked(True)
            
    def _toggle_toolbar(self, checked):
        """切换工具栏显示/隐藏"""
        self.toolbar.setVisible(checked) 