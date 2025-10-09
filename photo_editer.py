import sys
import cv2
import numpy as np
import copy
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QColor, QCursor, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QLabel, QSlider, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QFileDialog, QFrame, QMessageBox, QGroupBox, QScrollArea, QShortcut,
    QProgressDialog
)


# ---------- 图像调整函数 ----------
def adjust_exposure(image, ev):
    """调整曝光"""
    return np.clip(image * (2 ** ev), 0, 1)


def adjust_shadow(image, value):
    """调整阴影"""
    mask = np.clip(1 - image * 2, 0, 1)
    return np.clip(image + mask * (value / 100.0), 0, 1)


def adjust_highlight(image, value):
    """调整高光"""
    mask = np.clip(image * 2 - 1, 0, 1)
    return np.clip(image - mask * (value / 100.0), 0, 1)


def adjust_contrast(image, value):
    """调整对比度"""
    factor = (259 * (value + 255)) / (255 * (259 - value))
    return np.clip(factor * (image - 0.5) + 0.5, 0, 1)


def adjust_whites(image, value):
    """调整白色"""
    # 主要影响高光区域
    mask = np.power(image, 0.5)  # 更平滑的过渡
    adjustment = value / 100.0
    return np.clip(image + mask * adjustment, 0, 1)


def adjust_blacks(image, value):
    """调整黑色"""
    # 主要影响阴影区域
    mask = 1 - np.power(image, 0.5)  # 反向遮罩
    adjustment = value / 100.0
    return np.clip(image + mask * adjustment, 0, 1)


def adjust_brightness(image, value):
    """调整亮度"""
    # 转换到HSV色彩空间
    hsv = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] + value * 2.55, 0, 255)  # value范围-100到100
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return rgb.astype(np.float32) / 255.0


def adjust_saturation(image, value):
    """调整饱和度"""
    # 转换到HSV色彩空间
    hsv = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1 + value / 100.0), 0, 255)
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return rgb.astype(np.float32) / 255.0


def adjust_hue(image, value):
    """调整色相"""
    # 转换到HSV色彩空间
    hsv = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    # 色相是循环的，范围0-180（OpenCV中）
    hsv[:, :, 0] = (hsv[:, :, 0] + value) % 180
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return rgb.astype(np.float32) / 255.0


def adjust_hsl_by_color(image, hsl_adjustments):
    """
    按颜色调整HSL
    hsl_adjustments: 字典，包含每个颜色的调整值
    格式: {
        'red': {'hue': 0, 'saturation': 0, 'luminance': 0},
        'orange': {...}, ...
    }
    """
    if not any(hsl_adjustments.values()):
        return image
    
    # 转换到HSV色彩空间
    img_uint8 = (image * 255).astype(np.uint8)
    hsv = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
    
    # 定义颜色范围（色相范围，OpenCV中H范围是0-180）
    color_ranges = {
        'red': [(0, 10), (170, 180)],      # 红色跨越0度
        'orange': [(10, 25)],               # 橙色
        'yellow': [(25, 40)],               # 黄色
        'green': [(40, 80)],                # 绿色
        'cyan': [(80, 100)],                # 青色/淡绿色
        'blue': [(100, 130)],               # 蓝色
        'purple': [(130, 150)],             # 紫色
        'magenta': [(150, 170)]             # 品红
    }
    
    result_hsv = hsv.copy()
    
    for color_name, adjustments in hsl_adjustments.items():
        if color_name not in color_ranges:
            continue
        
        hue_shift = adjustments.get('hue', 0)
        sat_shift = adjustments.get('saturation', 0)
        lum_shift = adjustments.get('luminance', 0)
        
        if hue_shift == 0 and sat_shift == 0 and lum_shift == 0:
            continue
        
        # 创建颜色遮罩
        mask = np.zeros(hsv.shape[:2], dtype=np.float32)
        
        for hue_range in color_ranges[color_name]:
            h_min, h_max = hue_range
            # 创建该颜色范围的遮罩
            temp_mask = ((hsv[:, :, 0] >= h_min) & (hsv[:, :, 0] <= h_max)).astype(np.float32)
            
            # 使用高斯模糊创建平滑过渡
            temp_mask = cv2.GaussianBlur(temp_mask, (15, 15), 5)
            mask = np.maximum(mask, temp_mask)
        
        # 应用调整
        if hue_shift != 0:
            # 色相偏移
            result_hsv[:, :, 0] = (result_hsv[:, :, 0] + hue_shift * mask) % 180
        
        if sat_shift != 0:
            # 饱和度调整
            sat_factor = 1 + (sat_shift / 100.0)
            result_hsv[:, :, 1] = np.clip(
                result_hsv[:, :, 1] * (1 + (sat_factor - 1) * mask),
                0, 255
            )
        
        if lum_shift != 0:
            # 亮度调整
            result_hsv[:, :, 2] = np.clip(
                result_hsv[:, :, 2] + lum_shift * 2.55 * mask,
                0, 255
            )
    
    # 转换回RGB
    result_rgb = cv2.cvtColor(result_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return result_rgb.astype(np.float32) / 255.0


def adjust_vibrance(image, value):
    """调整鲜艳度（智能饱和度调整）"""
    # 计算每个像素的饱和度
    max_rgb = np.max(image, axis=2)
    min_rgb = np.min(image, axis=2)
    saturation = (max_rgb - min_rgb) / (max_rgb + 1e-8)
    
    # 对低饱和度区域应用更强的调整
    mask = 1 - saturation
    factor = 1 + (value / 100.0) * mask[:, :, np.newaxis]
    
    # 转换到HSV并调整
    hsv = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor[:, :, 0], 0, 255)
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return rgb.astype(np.float32) / 255.0


def adjust_color_temperature(image, kelvin):
    """调整色温"""
    t = kelvin / 100
    if t <= 66:
        r = 255
        g = np.clip(99.47 * np.log(t) - 161.12, 0, 255)
        b = np.clip(138.52 * np.log(t - 10) - 305.04, 0, 255) if t > 10 else 0
    else:
        r = np.clip(329.70 * ((t - 60) ** -0.133), 0, 255)
        g = np.clip(288.12 * ((t - 60) ** -0.0755), 0, 255)
        b = 255
    wb = np.array([r, g, b]) / 255.0
    return np.clip(image * wb, 0, 1)


def adjust_clarity(image, value):
    """
    调整清晰度 - 增强中频细节
    通过拉普拉斯金字塔实现局部对比度增强
    """
    if value == 0:
        return image
    
    # 转换为uint8格式
    img_uint8 = (image * 255).astype(np.uint8)
    
    # 使用高斯模糊创建低频图像
    sigma = 3.0
    low_freq = cv2.GaussianBlur(img_uint8, (0, 0), sigma)
    
    # 提取中频细节（原图 - 低频）
    mid_freq = cv2.subtract(img_uint8, low_freq)
    
    # 根据value调整中频强度
    strength = value / 100.0
    enhanced = cv2.addWeighted(img_uint8, 1.0, mid_freq, strength * 2, 0)
    
    return np.clip(enhanced.astype(np.float32) / 255.0, 0, 1)


def adjust_texture(image, value):
    """
    调整纹理 - 增强高频细节
    主要影响小尺度纹理和细节
    """
    if value == 0:
        return image
    
    # 转换为uint8格式
    img_uint8 = (image * 255).astype(np.uint8)
    
    # 使用小半径高斯模糊
    sigma = 1.0
    blurred = cv2.GaussianBlur(img_uint8, (0, 0), sigma)
    
    # 提取高频细节
    detail = cv2.subtract(img_uint8, blurred)
    
    # 根据value调整细节强度
    strength = value / 100.0
    enhanced = cv2.addWeighted(img_uint8, 1.0, detail, strength * 3, 0)
    
    return np.clip(enhanced.astype(np.float32) / 255.0, 0, 1)


def adjust_dehaze(image, value):
    """
    去朦胧 - 暗通道去雾算法的简化版本
    增强对比度并恢复色彩饱和度
    """
    if value == 0:
        return image
    
    # 转换为uint8格式
    img_uint8 = (image * 255).astype(np.uint8)
    
    # 计算强度
    strength = value / 100.0
    
    # 方法1: 增强对比度
    # 计算每个像素的最小值通道（暗通道）
    dark_channel = np.min(img_uint8, axis=2)
    
    # 估计大气光值
    flat_dark = dark_channel.flatten()
    num_pixels = len(flat_dark)
    num_brightest = int(num_pixels * 0.001)
    brightest_indices = np.argpartition(flat_dark, -num_brightest)[-num_brightest:]
    atmospheric_light = np.mean(img_uint8.reshape(-1, 3)[brightest_indices], axis=0)
    
    # 去雾处理
    atmospheric_light = np.maximum(atmospheric_light, 1)  # 避免除零
    transmission = 1 - 0.95 * dark_channel / np.max(dark_channel)
    transmission = np.maximum(transmission, 0.1)  # 保留最小透射率
    
    # 应用去雾
    result = np.zeros_like(img_uint8, dtype=np.float32)
    for i in range(3):
        result[:, :, i] = (img_uint8[:, :, i] - atmospheric_light[i]) / transmission + atmospheric_light[i]
    
    # 混合原图和去雾结果
    dehazed = img_uint8.astype(np.float32) * (1 - strength) + result * strength
    
    # 额外增强饱和度
    hsv = cv2.cvtColor(np.clip(dehazed, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1 + strength * 0.3), 0, 255)
    result_rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    
    return np.clip(result_rgb.astype(np.float32) / 255.0, 0, 1)


def apply_curve(image, curve_points):
    """
    应用曲线调整
    curve_points: 字典，包含 'rgb', 'red', 'green', 'blue' 四个通道的控制点
    每个通道的控制点格式: [(x1, y1), (x2, y2), ...], x和y范围都是0-255
    """
    img_uint8 = (image * 255).astype(np.uint8)
    result = img_uint8.copy()
    
    # 先应用RGB曲线（亮度曲线）
    if curve_points.get('rgb') and len(curve_points['rgb']) > 0:
        # 创建查找表
        lut = create_curve_lut(curve_points['rgb'])
        # 应用到所有通道
        for i in range(3):
            result[:, :, i] = cv2.LUT(result[:, :, i], lut)
    
    # 然后分别应用RGB各通道曲线
    for i, channel in enumerate(['red', 'green', 'blue']):
        if curve_points.get(channel) and len(curve_points[channel]) > 0:
            lut = create_curve_lut(curve_points[channel])
            result[:, :, i] = cv2.LUT(result[:, :, i], lut)
    
    return result.astype(np.float32) / 255.0


def create_curve_lut(control_points):
    """
    根据控制点创建256位查找表
    使用三次样条插值实现平滑曲线
    """
    # 确保有起点和终点
    points = sorted(control_points, key=lambda p: p[0])
    
    # 如果没有起点，添加(0,0)
    if len(points) == 0 or points[0][0] > 0:
        points.insert(0, (0, 0))
    
    # 如果没有终点，添加(255,255)
    if len(points) == 0 or points[-1][0] < 255:
        points.append((255, 255))
    
    # 提取x和y坐标
    x_points = np.array([p[0] for p in points])
    y_points = np.array([p[1] for p in points])
    
    # 根据控制点数量选择插值方法
    from scipy import interpolate
    
    if len(points) < 4:
        # 控制点少于4个时使用线性插值
        f = interpolate.interp1d(x_points, y_points, kind='linear', 
                                 fill_value='extrapolate')
    else:
        # 控制点足够时使用三次样条插值
        try:
            f = interpolate.interp1d(x_points, y_points, kind='cubic', 
                                     fill_value='extrapolate')
        except:
            # 如果三次插值失败，回退到线性插值
            f = interpolate.interp1d(x_points, y_points, kind='linear', 
                                     fill_value='extrapolate')
    
    # 创建查找表
    x_new = np.arange(256)
    y_new = f(x_new)
    
    # 限制在0-255范围内
    y_new = np.clip(y_new, 0, 255).astype(np.uint8)
    
    return y_new


# ---------- 参数历史管理器 ----------
class ParameterHistory:
    def __init__(self, max_history=50):
        self.history = []
        self.current_index = -1
        self.max_history = max_history
    
    def add_state(self, params):
        """添加新的参数状态"""
        # 如果当前不在历史末尾，删除后面的历史
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # 添加新状态
        self.history.append(copy.deepcopy(params))
        self.current_index += 1
        
        # 限制历史长度
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.current_index -= 1
    
    def can_undo(self):
        """是否可以撤销"""
        return self.current_index > 0
    
    def can_redo(self):
        """是否可以重做"""
        return self.current_index < len(self.history) - 1
    
    def undo(self):
        """撤销到上一个状态"""
        if self.can_undo():
            self.current_index -= 1
            return copy.deepcopy(self.history[self.current_index])
        return None
    
    def redo(self):
        """重做到下一个状态"""
        if self.can_redo():
            self.current_index += 1
            return copy.deepcopy(self.history[self.current_index])
        return None
    
    def clear(self):
        """清空历史"""
        self.history.clear()
        self.current_index = -1


# ---------- 曲线编辑器组件 ----------
class CurveEditorWidget(QWidget):
    curve_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setFixedSize(450, 500)
        
        # 当前通道
        self.current_channel = 'rgb'  # 'rgb', 'red', 'green', 'blue'
        
        # 每个通道的控制点 - 使用更平滑的数据结构
        # 格式: [(x, y), ...] 其中x和y都在0-255范围
        self.curve_points = {
            'rgb': [(0, 0), (255, 255)],  # 默认包含起点和终点
            'red': [(0, 0), (255, 255)],
            'green': [(0, 0), (255, 255)],
            'blue': [(0, 0), (255, 255)]
        }
        
        # 拖动相关
        self.dragging_point = None
        self.hovering_point = None
        self.is_dragging_curve = False
        self.last_drag_pos = None
        
        # 直方图数据
        self.histogram_data = None
        
        # 通道颜色
        self.channel_colors = {
            'rgb': QColor(200, 200, 200),
            'red': QColor(255, 100, 100),
            'green': QColor(100, 255, 100),
            'blue': QColor(100, 150, 255)
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 顶部控制栏
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        
        # 标题
        title = QLabel("色调曲线")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        top_bar.addWidget(title)
        
        top_bar.addStretch()
        
        # 复位按钮（小型）
        self.reset_btn = QPushButton("复位")
        self.reset_btn.clicked.connect(self.reset_current_curve)
        self.reset_btn.setFixedSize(50, 24)
        self.reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        top_bar.addWidget(self.reset_btn)
        
        # 通道选择圆点按钮
        self.channel_buttons = {}
        channel_defs = [
            ('rgb', '#C8C8C8', '灰色（RGB）'),
            ('red', '#FF6464', '红色'),
            ('green', '#64FF64', '绿色'),
            ('blue', '#6496FF', '蓝色')
        ]
        
        for channel, color, tooltip in channel_defs:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setCheckable(True)
            btn.setChecked(channel == 'rgb')
            btn.setToolTip(tooltip)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, ch=channel: self.select_channel(ch))
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: 2px solid #555;
                    border-radius: 10px;
                }}
                QPushButton:checked {{
                    border: 3px solid white;
                }}
                QPushButton:hover {{
                    border: 2px solid #888;
                }}
            """)
            
            self.channel_buttons[channel] = btn
            top_bar.addWidget(btn)
        
        main_layout.addLayout(top_bar)
        
        # 输入/输出标签（稍后在paintEvent中绘制曲线区域）
        
        self.setMouseTracking(True)
    
    def select_channel(self, channel):
        """选择通道"""
        self.current_channel = channel
        for ch, btn in self.channel_buttons.items():
            btn.setChecked(ch == channel)
        self.update()
    
    def reset_current_curve(self):
        """重置当前通道的曲线"""
        self.curve_points[self.current_channel] = [(0, 0), (255, 255)]
        self.curve_changed.emit()
        self.update()
    
    def reset_all_curves(self):
        """重置所有曲线"""
        for channel in self.curve_points:
            self.curve_points[channel] = [(0, 0), (255, 255)]
        self.curve_changed.emit()
        self.update()
    
    def set_histogram(self, image):
        """设置直方图数据"""
        if image is None:
            self.histogram_data = None
            return
        
        # 转换为0-255范围
        img_uint8 = (image * 255).astype(np.uint8)
        
        # 计算每个通道的直方图
        self.histogram_data = {
            'red': cv2.calcHist([img_uint8], [0], None, [256], [0, 256]).flatten(),
            'green': cv2.calcHist([img_uint8], [1], None, [256], [0, 256]).flatten(),
            'blue': cv2.calcHist([img_uint8], [2], None, [256], [0, 256]).flatten(),
        }
        
        # 计算亮度直方图
        gray = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY)
        self.histogram_data['rgb'] = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        
        self.update()
    
    def paintEvent(self, event):
        """绘制曲线编辑器 - 专业风格（带直方图背景）"""
        from PyQt5.QtGui import QPainter, QPen, QBrush, QFont, QPolygonF
        from PyQt5.QtCore import QPointF, QRectF, Qt
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘图区域
        margin_left = 35
        margin_right = 15
        margin_top = 50
        margin_bottom = 40
        
        width = self.width() - margin_left - margin_right
        height = self.height() - margin_top - margin_bottom
        
        # 背景 - 深色
        painter.fillRect(margin_left, margin_top, width, height, QColor(35, 35, 35))
        
        # 绘制直方图（如果有数据）
        if self.histogram_data and self.current_channel in self.histogram_data:
            self.draw_histogram(painter, margin_left, margin_top, width, height)
        
        # 网格 - 更精细的4x4网格
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        for i in range(1, 4):
            x = margin_left + i * width / 4
            y = margin_top + i * height / 4
            painter.drawLine(int(x), margin_top, int(x), margin_top + height)
            painter.drawLine(margin_left, int(y), margin_left + width, int(y))
        
        # 对角线（默认曲线）- 虚线
        pen = QPen(QColor(90, 90, 90), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(margin_left, margin_top + height, margin_left + width, margin_top)
        
        # 边框
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawRect(margin_left, margin_top, width, height)
        
        # 绘制曲线
        color = self.channel_colors[self.current_channel]
        self.draw_curve(painter, self.current_channel, color, margin_left, width, height, margin_top)
        
        # 绘制控制点
        points = self.curve_points[self.current_channel]
        for i, point in enumerate(points):
            x = margin_left + point[0] * width / 255
            y = margin_top + height - point[1] * height / 255
            
            # 跳过起点和终点（不可移动）
            if i == 0 or i == len(points) - 1:
                # 起点和终点用小圆点表示
                painter.setBrush(QBrush(QColor(120, 120, 120)))
                painter.setPen(QPen(QColor(80, 80, 80), 1))
                painter.drawEllipse(QPointF(x, y), 3, 3)
            else:
                # 普通控制点
                if self.hovering_point == i or self.dragging_point == i:
                    # 悬停或拖动时放大
                    painter.setBrush(QBrush(color.lighter(130)))
                    painter.setPen(QPen(Qt.white, 2))
                    painter.drawEllipse(QPointF(x, y), 7, 7)
                else:
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(Qt.white, 1.5))
                    painter.drawEllipse(QPointF(x, y), 5, 5)
        
        # 绘制输入/输出标签
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(QRectF(margin_left, margin_top + height + 5, width / 2, 30),
                        Qt.AlignLeft | Qt.AlignTop, "输入：")
        painter.drawText(QRectF(margin_left + width / 2, margin_top + height + 5, width / 2, 30),
                        Qt.AlignRight | Qt.AlignTop, "输出：")
        
        # 绘制坐标提示
        if self.hovering_point is not None and self.hovering_point < len(points):
            point = points[self.hovering_point]
            # 显示输入/输出值
            hint_text = f"输入:{point[0]} → 输出:{point[1]}"
            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(QRectF(margin_left, margin_top - 25, width, 20), 
                           Qt.AlignCenter, hint_text)
    
    def draw_histogram(self, painter, margin_left, margin_top, width, height):
        """绘制直方图背景"""
        if not self.histogram_data:
            return
        
        hist = self.histogram_data[self.current_channel]
        max_val = np.max(hist)
        
        if max_val == 0:
            return
        
        # 归一化直方图
        hist_norm = hist / max_val
        
        # 绘制直方图条
        if self.current_channel == 'rgb':
            # 灰色直方图
            for i in range(256):
                h = hist_norm[i] * height * 0.6  # 限制高度为60%
                x = margin_left + i * width / 255
                painter.fillRect(int(x), int(margin_top + height - h), 
                               max(2, int(width / 255)), int(h),
                               QColor(120, 120, 120, 80))
        else:
            # 彩色直方图
            color_map = {
                'red': QColor(255, 100, 100, 100),
                'green': QColor(100, 255, 100, 100),
                'blue': QColor(100, 150, 255, 100)
            }
            hist_color = color_map.get(self.current_channel, QColor(150, 150, 150, 80))
            
            for i in range(256):
                h = hist_norm[i] * height * 0.6
                x = margin_left + i * width / 255
                painter.fillRect(int(x), int(margin_top + height - h), 
                               max(2, int(width / 255)), int(h),
                               hist_color)
    
    def draw_curve(self, painter, channel, color, margin, width, height, y_offset):
        """绘制曲线"""
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QPainterPath, QPen
        
        points = self.curve_points[channel]
        if len(points) == 0:
            return
        
        # 创建查找表
        try:
            lut = create_curve_lut(points)
        except:
            return
        
        # 绘制曲线
        painter.setPen(QPen(color, 2))
        path = QPainterPath()
        
        first = True
        for x in range(256):
            y = lut[x]
            px = margin + x * width / 255
            py = y_offset + height - y * height / 255
            
            if first:
                path.moveTo(px, py)
                first = False
            else:
                path.lineTo(px, py)
        
        painter.drawPath(path)
    
    def mousePressEvent(self, event):
        """鼠标按下 - 专业风格交互"""
        if event.button() == Qt.LeftButton:
            margin_left = 35
            margin_right = 15
            margin_top = 50
            margin_bottom = 40
            width = self.width() - margin_left - margin_right
            height = self.height() - margin_top - margin_bottom
            y_offset = margin_top
            
            x = event.x()
            y = event.y()
            
            # 检查是否在曲线区域内
            if not (margin_left <= x <= margin_left + width and y_offset <= y <= y_offset + height):
                return
            
            # 检查是否点击了控制点
            points = self.curve_points[self.current_channel]
            for i, point in enumerate(points):
                px = margin_left + point[0] * width / 255
                py = y_offset + height - point[1] * height / 255
                
                if abs(x - px) < 12 and abs(y - py) < 12:
                    # 不允许拖动起点和终点
                    if i != 0 and i != len(points) - 1:
                        self.dragging_point = i
                        return
            
            # 在曲线上点击，添加新控制点
            curve_x = int((x - margin_left) * 255 / width)
            curve_y = int((y_offset + height - y) * 255 / height)
            curve_x = np.clip(curve_x, 0, 255)
            curve_y = np.clip(curve_y, 0, 255)
            
            # 不允许在起点和终点位置添加
            if curve_x > 0 and curve_x < 255:
                # 检查是否已经有相同x坐标的点
                existing_x = [p[0] for p in points]
                if curve_x not in existing_x:
                    points.append((curve_x, curve_y))
                    points.sort(key=lambda p: p[0])
                    self.dragging_point = points.index((curve_x, curve_y))
                    self.curve_changed.emit()
                    self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动 - 更新悬停状态和拖动"""
        margin_left = 35
        margin_right = 15
        margin_top = 50
        margin_bottom = 40
        width = self.width() - margin_left - margin_right
        height = self.height() - margin_top - margin_bottom
        y_offset = margin_top
        
        x = event.x()
        y = event.y()
        
        # 拖动控制点
        if self.dragging_point is not None:
            points = self.curve_points[self.current_channel]
            
            # 计算新位置
            curve_y = int((y_offset + height - y) * 255 / height)
            curve_y = np.clip(curve_y, 0, 255)
            
            # 获取当前点的x坐标（不改变x）
            old_point = points[self.dragging_point]
            curve_x = old_point[0]
            
            # 限制Y值不能超出相邻点太多（保持曲线平滑）
            if self.dragging_point > 0:
                prev_y = points[self.dragging_point - 1][1]
                if curve_y < prev_y - 100:
                    curve_y = prev_y - 100
            if self.dragging_point < len(points) - 1:
                next_y = points[self.dragging_point + 1][1]
                if curve_y > next_y + 100:
                    curve_y = next_y + 100
            
            points[self.dragging_point] = (curve_x, curve_y)
            self.curve_changed.emit()
            self.update()
        else:
            # 更新悬停状态
            old_hovering = self.hovering_point
            self.hovering_point = None
            
            if margin_left <= x <= margin_left + width and y_offset <= y <= y_offset + height:
                points = self.curve_points[self.current_channel]
                for i, point in enumerate(points):
                    px = margin_left + point[0] * width / 255
                    py = y_offset + height - point[1] * height / 255
                    
                    if abs(x - px) < 12 and abs(y - py) < 12:
                        self.hovering_point = i
                        self.setCursor(Qt.PointingHandCursor)
                        break
                
                if self.hovering_point is None:
                    self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            
            if old_hovering != self.hovering_point:
                self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        self.dragging_point = None
    
    def mouseDoubleClickEvent(self, event):
        """双击删除控制点 - 不能删除起点和终点"""
        if event.button() == Qt.LeftButton:
            margin_left = 35
            margin_right = 15
            margin_top = 50
            margin_bottom = 40
            width = self.width() - margin_left - margin_right
            height = self.height() - margin_top - margin_bottom
            y_offset = margin_top
            
            x = event.x()
            y = event.y()
            
            points = self.curve_points[self.current_channel]
            for i, point in enumerate(points):
                px = margin_left + point[0] * width / 255
                py = y_offset + height - point[1] * height / 255
                
                if abs(x - px) < 12 and abs(y - py) < 12:
                    # 不允许删除起点和终点
                    if i != 0 and i != len(points) - 1:
                        points.pop(i)
                        self.curve_changed.emit()
                        self.update()
                    return
    
    def leaveEvent(self, event):
        """鼠标离开widget"""
        self.hovering_point = None
        self.setCursor(Qt.ArrowCursor)
        self.update()


# ---------- 直方图组件 ----------
class HistogramWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(300, 200)
        
        # 创建matplotlib图形
        self.figure = Figure(figsize=(3, 2), dpi=100, facecolor='#2b2b2b')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self)
        
        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # 初始化空直方图
        self.update_histogram(None)
    
    def update_histogram(self, image):
        """更新直方图显示"""
        self.figure.clear()
        
        if image is None:
            # 显示空直方图
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, '无图片', ha='center', va='center', 
                   transform=ax.transAxes, color='white', fontsize=12)
            ax.set_facecolor('#2b2b2b')
            ax.tick_params(colors='white')
        else:
            # 计算RGB直方图
            ax = self.figure.add_subplot(111)
            
            # 转换为0-255范围
            img_uint8 = (image * 255).astype(np.uint8)
            
            # 计算每个通道的直方图
            colors = ['red', 'green', 'blue']
            for i, color in enumerate(colors):
                hist = cv2.calcHist([img_uint8], [i], None, [256], [0, 256])
                ax.plot(hist, color=color, alpha=0.7, linewidth=1)
            
            # 计算亮度直方图
            gray = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY)
            hist_gray = cv2.calcHist([gray], [0], None, [256], [0, 256])
            ax.plot(hist_gray, color='white', alpha=0.5, linewidth=1)
            
            # 设置样式
            ax.set_facecolor('#2b2b2b')
            ax.set_xlim([0, 255])
            ax.set_ylim([0, np.max(hist_gray) * 1.1])
            ax.tick_params(colors='white', labelsize=8)
            ax.spines['bottom'].set_color('white')
            ax.spines['top'].set_color('white')
            ax.spines['right'].set_color('white')
            ax.spines['left'].set_color('white')
            
            # 添加网格
            ax.grid(True, alpha=0.3, color='white')
            
        self.figure.tight_layout()
        self.canvas.draw()


# ---------- HSL颜色调整组件（Tab风格） ----------
class HSLColorAdjustment(QWidget):
    """HSL分色调整组件 - Tab切换风格"""
    hsl_changed = pyqtSignal(str, str, int)  # color_name, adjustment_type, value
    
    def __init__(self):
        super().__init__()
        
        # 当前选中的颜色
        self.current_color = 'red'
        
        # 颜色定义（颜色key, 显示名称, 颜色代码）
        self.colors = [
            ('red', '红色', '#FF5050'),
            ('orange', '橙色', '#FFA500'),
            ('yellow', '黄色', '#FFD700'),
            ('green', '绿色', '#50C878'),
            ('cyan', '青色', '#40E0D0'),
            ('blue', '蓝色', '#5090FF'),
            ('purple', '紫色', '#A060FF'),
            ('magenta', '品红', '#FF50D0')
        ]
        
        # 存储所有滑块
        self.sliders = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # 颜色选择器区域
        color_selector_layout = QHBoxLayout()
        color_selector_layout.setSpacing(8)
        
        self.color_buttons = {}
        for color_key, color_name, color_code in self.colors:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setToolTip(color_name)
            btn.clicked.connect(lambda checked, ck=color_key: self.select_color(ck))
            
            # 设置按钮样式
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_code};
                    border: 2px solid #555;
                    border-radius: 12px;
                }}
                QPushButton:hover {{
                    border: 2px solid #888;
                }}
                QPushButton:checked {{
                    border: 3px solid white;
                }}
            """)
            btn.setCheckable(True)
            
            self.color_buttons[color_key] = btn
            color_selector_layout.addWidget(btn)
        
        # 默认选中红色
        self.color_buttons['red'].setChecked(True)
        
        color_selector_layout.addStretch()
        main_layout.addLayout(color_selector_layout)
        
        # 创建所有颜色的滑块组（但只显示当前选中的）
        self.slider_container = QWidget()
        self.slider_layout = QVBoxLayout(self.slider_container)
        self.slider_layout.setContentsMargins(0, 10, 0, 0)
        self.slider_layout.setSpacing(8)
        
        self.color_sliders_widgets = {}
        
        for color_key, color_name, _ in self.colors:
            widget = self.create_color_sliders(color_key, color_name)
            self.color_sliders_widgets[color_key] = widget
            self.slider_layout.addWidget(widget)
            # 默认隐藏所有，只显示红色
            widget.setVisible(color_key == 'red')
        
        main_layout.addWidget(self.slider_container)
        main_layout.addStretch()
    
    def create_color_sliders(self, color_key, color_name):
        """创建单个颜色的滑块组"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 色相滑块
        hue_label = QLabel("色相: 0")
        hue_label.setStyleSheet("color: white; font-weight: bold;")
        hue_slider = self.create_slider(-30, 30, 0)
        hue_slider.valueChanged.connect(
            lambda v, ck=color_key, l=hue_label: self.on_slider_change(ck, 'hue', v, l)
        )
        
        # 饱和度滑块
        sat_label = QLabel("饱和度: 0")
        sat_label.setStyleSheet("color: white; font-weight: bold;")
        sat_slider = self.create_slider(-100, 100, 0)
        sat_slider.valueChanged.connect(
            lambda v, ck=color_key, l=sat_label: self.on_slider_change(ck, 'saturation', v, l)
        )
        
        # 明亮度滑块
        lum_label = QLabel("明亮度: 0")
        lum_label.setStyleSheet("color: white; font-weight: bold;")
        lum_slider = self.create_slider(-100, 100, 0)
        lum_slider.valueChanged.connect(
            lambda v, ck=color_key, l=lum_label: self.on_slider_change(ck, 'luminance', v, l)
        )
        
        # 添加到布局
        layout.addWidget(hue_label)
        layout.addWidget(hue_slider)
        layout.addWidget(sat_label)
        layout.addWidget(sat_slider)
        layout.addWidget(lum_label)
        layout.addWidget(lum_slider)
        
        # 保存滑块引用
        self.sliders[color_key] = {
            'hue': (hue_slider, hue_label),
            'saturation': (sat_slider, sat_label),
            'luminance': (lum_slider, lum_label)
        }
        
        return widget
    
    def create_slider(self, min_val, max_val, default_val):
        """创建滑块"""
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4b4b4, stop:1 #8f8f8f);
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d4d4d4, stop:1 #afafaf);
            }
        """)
        return slider
    
    def select_color(self, color_key):
        """选择颜色"""
        # 更新按钮选中状态
        for key, btn in self.color_buttons.items():
            btn.setChecked(key == color_key)
        
        # 显示/隐藏对应的滑块组
        for key, widget in self.color_sliders_widgets.items():
            widget.setVisible(key == color_key)
        
        self.current_color = color_key
    
    def on_slider_change(self, color_key, adj_type, value, label):
        """滑块变化"""
        label_names = {'hue': '色相', 'saturation': '饱和度', 'luminance': '明亮度'}
        label.setText(f"{label_names[adj_type]}: {value}")
        self.hsl_changed.emit(color_key, adj_type, value)
    
    def reset_all(self):
        """重置所有滑块"""
        for color_key in self.sliders:
            for adj_type in ['hue', 'saturation', 'luminance']:
                slider, _ = self.sliders[color_key][adj_type]
                slider.setValue(0)
    
    def set_values(self, hsl_colors):
        """设置滑块值"""
        for color_key, values in hsl_colors.items():
            if color_key in self.sliders:
                for adj_type, value in values.items():
                    if adj_type in self.sliders[color_key]:
                        slider, label = self.sliders[color_key][adj_type]
                        slider.setValue(value)


# ---------- 可点击的图片标签 ----------
class ClickableImageLabel(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, text=""):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files and files[0].lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            self.parent().load_image_from_path(files[0])


# ---------- 渲染器 ----------
class Renderer:
    def __init__(self, image, preview_max_size=1080):
        # 保存原始图像（用于最终导出）
        self.original_image = image.astype(np.float32) / 255.0
        self.original_shape = image.shape
        
        # 创建预览图像（缩小尺寸以提高性能）
        h, w = image.shape[:2]
        max_dim = max(h, w)
        
        if max_dim > preview_max_size:
            # 需要缩放
            scale = preview_max_size / max_dim
            new_w = int(w * scale)
            new_h = int(h * scale)
            preview_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            self.base_image = preview_image.astype(np.float32) / 255.0
            self.is_preview = True
            self.preview_scale = scale
        else:
            # 不需要缩放
            self.base_image = self.original_image
            self.is_preview = False
            self.preview_scale = 1.0
        
        self.params = {
            "exposure": 0.0,
            "contrast": 0,
            "highlight": 0,
            "shadow": 0,
            "whites": 0,
            "blacks": 0,
            "clarity": 0,
            "texture": 0,
            "dehaze": 0,
            "brightness": 0,
            "saturation": 0,
            "hue": 0,
            "vibrance": 0,
            "temperature": 6500,
            "hsl_colors": {
                'red': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'orange': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'yellow': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'green': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'cyan': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'blue': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'purple': {'hue': 0, 'saturation': 0, 'luminance': 0},
                'magenta': {'hue': 0, 'saturation': 0, 'luminance': 0}
            },
            "curves": {
                'rgb': [],
                'red': [],
                'green': [],
                'blue': []
            }
        }

    def render(self, use_original=False):
        """按照专业调色软件的处理顺序渲染图像"""
        img = (self.original_image if use_original else self.base_image).copy()
        
        # 1. 基础曝光调整
        img = adjust_exposure(img, self.params["exposure"])
        
        # 2. 对比度调整
        if self.params["contrast"] != 0:
            img = adjust_contrast(img, self.params["contrast"])
        
        # 3. 高光和阴影调整
        if self.params["highlight"] != 0:
            img = adjust_highlight(img, self.params["highlight"])
        if self.params["shadow"] != 0:
            img = adjust_shadow(img, self.params["shadow"])
        
        # 4. 白色和黑色调整
        if self.params["whites"] != 0:
            img = adjust_whites(img, self.params["whites"])
        if self.params["blacks"] != 0:
            img = adjust_blacks(img, self.params["blacks"])
        
        # 5. 曲线调整（在其他调整之后，细节增强之前）
        has_curves = any(len(self.params["curves"][ch]) > 0 for ch in ['rgb', 'red', 'green', 'blue'])
        if has_curves:
            img = apply_curve(img, self.params["curves"])
        
        # 6. 去朦胧（在细节增强前进行）
        if self.params["dehaze"] != 0:
            img = adjust_dehaze(img, self.params["dehaze"])
        
        # 7. 细节增强
        if self.params["clarity"] != 0:
            img = adjust_clarity(img, self.params["clarity"])
        if self.params["texture"] != 0:
            img = adjust_texture(img, self.params["texture"])
        
        # 8. 色彩调整
        if self.params["brightness"] != 0:
            img = adjust_brightness(img, self.params["brightness"])
        if self.params["saturation"] != 0:
            img = adjust_saturation(img, self.params["saturation"])
        if self.params["hue"] != 0:
            img = adjust_hue(img, self.params["hue"])
        if self.params["vibrance"] != 0:
            img = adjust_vibrance(img, self.params["vibrance"])
        
        # 9. HSL分色调整
        if any(any(v.values()) for v in self.params["hsl_colors"].values()):
            img = adjust_hsl_by_color(img, self.params["hsl_colors"])
        
        # 10. 色温调整（最后进行）
        if self.params["temperature"] != 6500:
            img = adjust_color_temperature(img, self.params["temperature"])
        
        return np.clip(img, 0, 1)
    
    def get_rendered_uint8(self, use_original=False):
        """返回渲染后的uint8格式图像，用于保存"""
        rendered = self.render(use_original=use_original)
        return (rendered * 255).astype(np.uint8)


# ---------- 主窗口 ----------
class PhotoEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易修图器 - PyQt5 + OpenCV")
        self.resize(1400, 800)
        self.setMinimumSize(1000, 600)

        # 设置应用图标和样式
        self.setup_ui()

        # 定时器实现实时刷新
        self.timer = QTimer()
        self.timer.setInterval(30)  # 提高刷新率
        self.timer.timeout.connect(self.update_preview)
        self.timer.start()

        self.renderer = None
        self.need_update = False
        self.current_file_path = None
        
        # 参数历史管理
        self.param_history = ParameterHistory()
        self.is_applying_history = False  # 防止历史操作时重复记录
        
        # 设置快捷键
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """设置快捷键"""
        # 撤销快捷键 Ctrl+Z
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo_action)
        
        # 重做快捷键 Ctrl+Y
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.redo_shortcut.activated.connect(self.redo_action)

    def setup_ui(self):
        """设置用户界面"""
        # 图像显示区域
        self.image_label = ClickableImageLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setStyleSheet("""
            ClickableImageLabel {
                background-color: #2b2b2b;
                border: 2px dashed #555;
                border-radius: 10px;
                color: #ccc;
                font-size: 18px;
                font-weight: bold;
            }
            ClickableImageLabel:hover {
                border-color: #777;
                background-color: #333;
            }
        """)
        self.image_label.setText("点击此处打开图片\n或拖拽图片到此处\n\n支持格式: JPG, PNG, BMP, TIFF")
        self.image_label.clicked.connect(self.open_image)

        # 直方图组件
        self.histogram_widget = HistogramWidget()
        
        # 曲线编辑器组件
        self.curve_editor = CurveEditorWidget()
        self.curve_editor.curve_changed.connect(self.on_curve_changed)
        
        # 创建图像、直方图和曲线的容器
        image_container = QVBoxLayout()
        image_container.addWidget(self.image_label, 3)
        
        # 直方图和曲线编辑器水平排列
        tools_layout = QHBoxLayout()
        tools_layout.addWidget(self.histogram_widget)
        tools_layout.addWidget(self.curve_editor)
        
        image_container.addLayout(tools_layout, 2)
        
        image_widget = QWidget()
        image_widget.setLayout(image_container)

        # 控制面板
        self.setup_control_panel()
        
        # 创建滚动区域包装控制面板
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.control_panel)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(350)
        scroll_area.setMaximumWidth(400)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #555;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #888;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #aaa;
            }
        """)

        # 主布局
        main_layout = QHBoxLayout()
        main_layout.addWidget(image_widget, 3)
        main_layout.addWidget(scroll_area, 1)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)

    def setup_control_panel(self):
        """设置控制面板"""
        self.control_panel = QFrame()
        self.control_panel.setFrameStyle(QFrame.StyledPanel)
        self.control_panel.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.control_panel)
        
        # 文件操作组
        file_group = QGroupBox("文件操作")
        file_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        file_layout = QVBoxLayout(file_group)
        
        self.open_button = QPushButton("📁 打开图片")
        self.open_button.setStyleSheet(self.get_button_style())
        self.open_button.clicked.connect(self.open_image)
        
        self.save_button = QPushButton("💾 保存图片")
        self.save_button.setStyleSheet(self.get_button_style())
        self.save_button.clicked.connect(self.save_image)
        self.save_button.setEnabled(False)
        
        self.reset_button = QPushButton("🔄 重置参数")
        self.reset_button.setStyleSheet(self.get_button_style())
        self.reset_button.clicked.connect(self.reset_params)
        self.reset_button.setEnabled(False)
        
        self.undo_button = QPushButton("↶ 撤销 (Ctrl+Z)")
        self.undo_button.setStyleSheet(self.get_button_style())
        self.undo_button.clicked.connect(self.undo_action)
        self.undo_button.setEnabled(False)
        
        self.redo_button = QPushButton("↷ 重做 (Ctrl+Y)")
        self.redo_button.setStyleSheet(self.get_button_style())
        self.redo_button.clicked.connect(self.redo_action)
        self.redo_button.setEnabled(False)
        
        file_layout.addWidget(self.open_button)
        file_layout.addWidget(self.save_button)
        file_layout.addWidget(self.reset_button)
        file_layout.addWidget(self.undo_button)
        file_layout.addWidget(self.redo_button)
        
        # 基础调整组
        basic_group = QGroupBox("基础调整")
        basic_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        basic_layout = QVBoxLayout(basic_group)
        
        # 曝光滑块
        self.exposure_label = QLabel("曝光 (EV): 0.0")
        self.exposure_label.setStyleSheet("color: white; font-weight: bold;")
        self.exposure_slider = self.create_slider(-20, 20, 0, self.on_exposure_change)
        
        # 对比度滑块
        self.contrast_label = QLabel("对比度: 0")
        self.contrast_label.setStyleSheet("color: white; font-weight: bold;")
        self.contrast_slider = self.create_slider(-100, 100, 0, self.on_contrast_change)
        
        # 高光滑块
        self.highlight_label = QLabel("高光: 0")
        self.highlight_label.setStyleSheet("color: white; font-weight: bold;")
        self.highlight_slider = self.create_slider(-100, 100, 0, self.on_highlight_change)
        
        # 阴影滑块
        self.shadow_label = QLabel("阴影: 0")
        self.shadow_label.setStyleSheet("color: white; font-weight: bold;")
        self.shadow_slider = self.create_slider(-100, 100, 0, self.on_shadow_change)
        
        # 白色滑块
        self.whites_label = QLabel("白色: 0")
        self.whites_label.setStyleSheet("color: white; font-weight: bold;")
        self.whites_slider = self.create_slider(-100, 100, 0, self.on_whites_change)
        
        # 黑色滑块
        self.blacks_label = QLabel("黑色: 0")
        self.blacks_label.setStyleSheet("color: white; font-weight: bold;")
        self.blacks_slider = self.create_slider(-100, 100, 0, self.on_blacks_change)
        
        # 添加基础调整到布局
        for label, slider in [(self.exposure_label, self.exposure_slider),
                             (self.contrast_label, self.contrast_slider),
                             (self.highlight_label, self.highlight_slider),
                             (self.shadow_label, self.shadow_slider),
                             (self.whites_label, self.whites_slider),
                             (self.blacks_label, self.blacks_slider)]:
            basic_layout.addWidget(label)
            basic_layout.addWidget(slider)
            basic_layout.addSpacing(5)
        
        # 细节调整组
        detail_group = QGroupBox("细节调整")
        detail_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        detail_layout = QVBoxLayout(detail_group)
        
        # 清晰度滑块
        self.clarity_label = QLabel("清晰度: 0")
        self.clarity_label.setStyleSheet("color: white; font-weight: bold;")
        self.clarity_slider = self.create_slider(-100, 100, 0, self.on_clarity_change)
        
        # 纹理滑块
        self.texture_label = QLabel("纹理: 0")
        self.texture_label.setStyleSheet("color: white; font-weight: bold;")
        self.texture_slider = self.create_slider(-100, 100, 0, self.on_texture_change)
        
        # 去朦胧滑块
        self.dehaze_label = QLabel("去朦胧: 0")
        self.dehaze_label.setStyleSheet("color: white; font-weight: bold;")
        self.dehaze_slider = self.create_slider(-100, 100, 0, self.on_dehaze_change)
        
        # 添加细节调整到布局
        for label, slider in [(self.clarity_label, self.clarity_slider),
                             (self.texture_label, self.texture_slider),
                             (self.dehaze_label, self.dehaze_slider)]:
            detail_layout.addWidget(label)
            detail_layout.addWidget(slider)
            detail_layout.addSpacing(5)
        
        # 色彩调整组
        color_group = QGroupBox("色彩调整")
        color_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        color_layout = QVBoxLayout(color_group)
        
        # 亮度滑块
        self.brightness_label = QLabel("亮度: 0")
        self.brightness_label.setStyleSheet("color: white; font-weight: bold;")
        self.brightness_slider = self.create_slider(-100, 100, 0, self.on_brightness_change)
        
        # 饱和度滑块
        self.saturation_label = QLabel("饱和度: 0")
        self.saturation_label.setStyleSheet("color: white; font-weight: bold;")
        self.saturation_slider = self.create_slider(-100, 100, 0, self.on_saturation_change)
        
        # 色相滑块
        self.hue_label = QLabel("色相: 0")
        self.hue_label.setStyleSheet("color: white; font-weight: bold;")
        self.hue_slider = self.create_slider(-180, 180, 0, self.on_hue_change)
        
        # 鲜艳度滑块
        self.vibrance_label = QLabel("鲜艳度: 0")
        self.vibrance_label.setStyleSheet("color: white; font-weight: bold;")
        self.vibrance_slider = self.create_slider(-100, 100, 0, self.on_vibrance_change)
        
        # 色温滑块
        self.temp_label = QLabel("色温(K): 6500")
        self.temp_label.setStyleSheet("color: white; font-weight: bold;")
        self.temp_slider = self.create_slider(3500, 9500, 6500, self.on_temp_change)
        
        # 添加色彩调整到布局
        for label, slider in [(self.brightness_label, self.brightness_slider),
                             (self.saturation_label, self.saturation_slider),
                             (self.hue_label, self.hue_slider),
                             (self.vibrance_label, self.vibrance_slider),
                             (self.temp_label, self.temp_slider)]:
            color_layout.addWidget(label)
            color_layout.addWidget(slider)
            color_layout.addSpacing(5)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #555; margin: 10px 0;")
        color_layout.addWidget(separator)
        
        # HSL颜色调整标题
        hsl_title = QLabel("调整：颜色")
        hsl_title.setStyleSheet("color: white; font-weight: bold; font-size: 12px; margin-top: 5px;")
        color_layout.addWidget(hsl_title)
        
        # HSL颜色调整组件
        self.hsl_adjustment = HSLColorAdjustment()
        self.hsl_adjustment.hsl_changed.connect(self.on_hsl_changed)
        color_layout.addWidget(self.hsl_adjustment)
        
        # 主控制面板布局
        layout.addWidget(file_group)
        layout.addWidget(basic_group)
        layout.addWidget(detail_group)
        layout.addWidget(color_group)
        layout.addStretch()

    def create_slider(self, min_val, max_val, default_val, callback):
        """创建样式化的滑块"""
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.valueChanged.connect(callback)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4b4b4, stop:1 #8f8f8f);
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d4d4d4, stop:1 #afafaf);
            }
        """)
        return slider

    def get_button_style(self):
        """获取按钮样式"""
        return """
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2968a3;
            }
            QPushButton:disabled {
                background-color: #666;
                color: #999;
            }
        """

    # ---------- 文件操作 ----------
    def open_image(self):
        """打开图片文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", 
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff);;所有文件 (*)"
        )
        if file_path:
            self.load_image_from_path(file_path)

    def load_image_from_path(self, file_path):
        """从文件路径加载图片（支持中文路径）"""
        try:
            # 使用numpy读取文件以支持中文路径
            with open(file_path, 'rb') as f:
                file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            
            # 使用cv2.imdecode解码图片
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            if img is None:
                QMessageBox.warning(self, "错误", f"无法打开图片文件：{file_path}")
                return
            
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.renderer = Renderer(img)
            self.current_file_path = file_path
            self.need_update = True

            # 清空历史并添加初始状态
            self.param_history.clear()
            self.param_history.add_state(self.renderer.params)
            
            # 启用控制按钮
            self.save_button.setEnabled(True)
            self.reset_button.setEnabled(True)
            self.update_history_buttons()
            
            # 更新窗口标题，显示预览信息
            import os
            filename = os.path.basename(file_path)
            if self.renderer.is_preview:
                preview_info = f" [预览: {int(self.renderer.preview_scale * 100)}%]"
            else:
                preview_info = ""
            self.setWindowTitle(f"简易修图器 - {filename}{preview_info}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时出错：{str(e)}")

    def save_image(self):
        """保存处理后的图片（支持中文路径，使用原图渲染）"""
        if not self.renderer:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "", 
            "JPEG (*.jpg);;PNG (*.png);;BMP (*.bmp);;TIFF (*.tiff)"
        )
        
        if file_path:
            # 创建进度对话框
            progress = QProgressDialog("正在处理原图并保存...", "取消", 0, 100, self)
            progress.setWindowTitle("导出图片")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)  # 立即显示
            progress.setValue(0)
            QApplication.processEvents()
            
            try:
                # 步骤1: 使用原图渲染 (70%)
                progress.setLabelText("正在使用原图渲染处理效果...")
                progress.setValue(10)
                QApplication.processEvents()
                
                # 使用原图渲染
                processed_img = self.renderer.get_rendered_uint8(use_original=True)
                
                progress.setValue(70)
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    return
                
                # 步骤2: 转换颜色空间 (80%)
                progress.setLabelText("正在转换颜色空间...")
                progress.setValue(75)
                QApplication.processEvents()
                
                # 转换为BGR格式用于保存
                processed_img_bgr = cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR)
                
                progress.setValue(80)
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    return
                
                # 步骤3: 编码图片 (90%)
                progress.setLabelText("正在编码图片...")
                progress.setValue(85)
                QApplication.processEvents()
                
                # 使用cv2.imencode编码后保存，以支持中文路径
                # 根据文件扩展名确定编码格式
                ext = file_path.lower().split('.')[-1]
                if ext == 'jpg' or ext == 'jpeg':
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
                    success, encoded_img = cv2.imencode('.jpg', processed_img_bgr, encode_param)
                elif ext == 'png':
                    encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
                    success, encoded_img = cv2.imencode('.png', processed_img_bgr, encode_param)
                elif ext == 'bmp':
                    success, encoded_img = cv2.imencode('.bmp', processed_img_bgr)
                elif ext == 'tiff' or ext == 'tif':
                    success, encoded_img = cv2.imencode('.tiff', processed_img_bgr)
                else:
                    # 默认使用JPEG
                    success, encoded_img = cv2.imencode('.jpg', processed_img_bgr)
                
                progress.setValue(90)
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    return
                
                # 步骤4: 写入文件 (100%)
                progress.setLabelText("正在保存文件...")
                progress.setValue(95)
                QApplication.processEvents()
                
                if success:
                    # 写入文件
                    with open(file_path, 'wb') as f:
                        f.write(encoded_img.tobytes())
                    
                    progress.setValue(100)
                    QApplication.processEvents()
                    
                    # 显示图片尺寸信息
                    h, w = processed_img.shape[:2]
                    size_mb = len(encoded_img.tobytes()) / (1024 * 1024)
                    QMessageBox.information(
                        self, "成功", 
                        f"图片已保存到：{file_path}\n\n"
                        f"尺寸: {w} x {h} 像素\n"
                        f"文件大小: {size_mb:.2f} MB"
                    )
                else:
                    QMessageBox.critical(self, "错误", "图片编码失败")
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存图片时出错：{str(e)}")
            finally:
                progress.close()

    def reset_params(self):
        """重置所有参数"""
        if not self.renderer:
            return
            
        # 重置所有滑块值
        self.exposure_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.highlight_slider.setValue(0)
        self.shadow_slider.setValue(0)
        self.whites_slider.setValue(0)
        self.blacks_slider.setValue(0)
        self.clarity_slider.setValue(0)
        self.texture_slider.setValue(0)
        self.dehaze_slider.setValue(0)
        self.brightness_slider.setValue(0)
        self.saturation_slider.setValue(0)
        self.hue_slider.setValue(0)
        self.vibrance_slider.setValue(0)
        self.temp_slider.setValue(6500)
        
        # 重置曲线
        self.curve_editor.reset_all_curves()
        
        # 重置HSL颜色调整
        self.hsl_adjustment.reset_all()
        
        # 这会自动触发参数更新

    def update_history_buttons(self):
        """更新撤销/重做按钮状态"""
        self.undo_button.setEnabled(self.param_history.can_undo())
        self.redo_button.setEnabled(self.param_history.can_redo())

    def undo_action(self):
        """撤销操作"""
        if not self.renderer:
            return
            
        params = self.param_history.undo()
        if params:
            self.is_applying_history = True
            self.apply_params_to_ui(params)
            self.renderer.params = params
            self.need_update = True
            self.update_history_buttons()
            self.is_applying_history = False

    def redo_action(self):
        """重做操作"""
        if not self.renderer:
            return
            
        params = self.param_history.redo()
        if params:
            self.is_applying_history = True
            self.apply_params_to_ui(params)
            self.renderer.params = params
            self.need_update = True
            self.update_history_buttons()
            self.is_applying_history = False

    def apply_params_to_ui(self, params):
        """将参数应用到UI滑块"""
        self.exposure_slider.setValue(int(params["exposure"] * 10))
        self.contrast_slider.setValue(params["contrast"])
        self.highlight_slider.setValue(params["highlight"])
        self.shadow_slider.setValue(params["shadow"])
        self.whites_slider.setValue(params["whites"])
        self.blacks_slider.setValue(params["blacks"])
        self.clarity_slider.setValue(params["clarity"])
        self.texture_slider.setValue(params["texture"])
        self.dehaze_slider.setValue(params["dehaze"])
        self.brightness_slider.setValue(params.get("brightness", 0))
        self.saturation_slider.setValue(params["saturation"])
        self.hue_slider.setValue(params.get("hue", 0))
        self.vibrance_slider.setValue(params["vibrance"])
        self.temp_slider.setValue(params["temperature"])
        
        # 应用曲线参数
        if "curves" in params:
            self.curve_editor.curve_points = copy.deepcopy(params["curves"])
            self.curve_editor.update()
        
        # 应用HSL参数
        if "hsl_colors" in params:
            self.hsl_adjustment.set_values(params["hsl_colors"])

    def add_to_history(self):
        """添加当前参数到历史"""
        if not self.is_applying_history and self.renderer:
            self.param_history.add_state(self.renderer.params)
            self.update_history_buttons()

    # ---------- 滑块回调函数 ----------
    def on_exposure_change(self):
        """曝光滑块变化"""
        if not self.renderer:
            return
        value = self.exposure_slider.value() / 10.0
        self.renderer.params["exposure"] = value
        self.exposure_label.setText(f"曝光 (EV): {value:.1f}")
        self.need_update = True
        self.add_to_history()

    def on_contrast_change(self):
        """对比度滑块变化"""
        if not self.renderer:
            return
        value = self.contrast_slider.value()
        self.renderer.params["contrast"] = value
        self.contrast_label.setText(f"对比度: {value}")
        self.need_update = True
        self.add_to_history()

    def on_highlight_change(self):
        """高光滑块变化"""
        if not self.renderer:
            return
        value = self.highlight_slider.value()
        self.renderer.params["highlight"] = value
        self.highlight_label.setText(f"高光: {value}")
        self.need_update = True
        self.add_to_history()

    def on_shadow_change(self):
        """阴影滑块变化"""
        if not self.renderer:
            return
        value = self.shadow_slider.value()
        self.renderer.params["shadow"] = value
        self.shadow_label.setText(f"阴影: {value}")
        self.need_update = True
        self.add_to_history()

    def on_whites_change(self):
        """白色滑块变化"""
        if not self.renderer:
            return
        value = self.whites_slider.value()
        self.renderer.params["whites"] = value
        self.whites_label.setText(f"白色: {value}")
        self.need_update = True
        self.add_to_history()

    def on_blacks_change(self):
        """黑色滑块变化"""
        if not self.renderer:
            return
        value = self.blacks_slider.value()
        self.renderer.params["blacks"] = value
        self.blacks_label.setText(f"黑色: {value}")
        self.need_update = True
        self.add_to_history()

    def on_clarity_change(self):
        """清晰度滑块变化"""
        if not self.renderer:
            return
        value = self.clarity_slider.value()
        self.renderer.params["clarity"] = value
        self.clarity_label.setText(f"清晰度: {value}")
        self.need_update = True
        self.add_to_history()

    def on_texture_change(self):
        """纹理滑块变化"""
        if not self.renderer:
            return
        value = self.texture_slider.value()
        self.renderer.params["texture"] = value
        self.texture_label.setText(f"纹理: {value}")
        self.need_update = True
        self.add_to_history()

    def on_dehaze_change(self):
        """去朦胧滑块变化"""
        if not self.renderer:
            return
        value = self.dehaze_slider.value()
        self.renderer.params["dehaze"] = value
        self.dehaze_label.setText(f"去朦胧: {value}")
        self.need_update = True
        self.add_to_history()

    def on_brightness_change(self):
        """亮度滑块变化"""
        if not self.renderer:
            return
        value = self.brightness_slider.value()
        self.renderer.params["brightness"] = value
        self.brightness_label.setText(f"亮度: {value}")
        self.need_update = True
        self.add_to_history()

    def on_saturation_change(self):
        """饱和度滑块变化"""
        if not self.renderer:
            return
        value = self.saturation_slider.value()
        self.renderer.params["saturation"] = value
        self.saturation_label.setText(f"饱和度: {value}")
        self.need_update = True
        self.add_to_history()

    def on_hue_change(self):
        """色相滑块变化"""
        if not self.renderer:
            return
        value = self.hue_slider.value()
        self.renderer.params["hue"] = value
        self.hue_label.setText(f"色相: {value}")
        self.need_update = True
        self.add_to_history()

    def on_vibrance_change(self):
        """鲜艳度滑块变化"""
        if not self.renderer:
            return
        value = self.vibrance_slider.value()
        self.renderer.params["vibrance"] = value
        self.vibrance_label.setText(f"鲜艳度: {value}")
        self.need_update = True
        self.add_to_history()

    def on_temp_change(self):
        """色温滑块变化"""
        if not self.renderer:
            return
        value = self.temp_slider.value()
        self.renderer.params["temperature"] = value
        self.temp_label.setText(f"色温(K): {value}")
        self.need_update = True
        self.add_to_history()

    def on_curve_changed(self):
        """曲线变化"""
        if not self.renderer:
            return
        # 更新渲染器的曲线参数
        self.renderer.params["curves"] = copy.deepcopy(self.curve_editor.curve_points)
        self.need_update = True
        self.add_to_history()
    
    def on_hsl_changed(self, color_name, adj_type, value):
        """HSL分色调整变化"""
        if not self.renderer:
            return
        self.renderer.params["hsl_colors"][color_name][adj_type] = value
        self.need_update = True
        self.add_to_history()

    # ---------- 渲染更新 ----------
    def update_preview(self):
        """更新图片预览"""
        if self.renderer and self.need_update:
            try:
                img = self.renderer.render()
                h, w, _ = img.shape

                # 转换为QImage
                qimg = QImage((img * 255).astype(np.uint8), w, h, w * 3, QImage.Format_RGB888)

                # 缩放以适应显示区域
                pix = QPixmap.fromImage(qimg).scaled(
                    self.image_label.width() - 20,
                    self.image_label.height() - 20,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                self.image_label.setPixmap(pix)
                
                # 更新直方图
                self.histogram_widget.update_histogram(img)
                
                # 更新曲线编辑器的直方图背景
                self.curve_editor.set_histogram(img)
                
                self.need_update = False
                
            except Exception as e:
                print(f"更新预览时出错: {e}")

    def resizeEvent(self, event):
        """窗口大小改变时重新渲染图片"""
        super().resizeEvent(event)
        if self.renderer:
            self.need_update = True


# ---------- 主程序 ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: white;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QGroupBox {
            font-size: 14px;
            font-weight: bold;
            border: 2px solid #555;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
    """)
    
    # 创建并显示主窗口
    win = PhotoEditor()
    win.show()
    
    # 运行应用程序
    sys.exit(app.exec_())
