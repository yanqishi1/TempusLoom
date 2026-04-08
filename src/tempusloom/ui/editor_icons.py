# -*- coding: utf-8 -*-
"""
Lightweight icon renderer – no external dependencies.
Each icon is drawn with QPainter geometric primitives,
approximating the lucide icon set used in the design.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, QSizeF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush,
    QPixmap, QFont, QPolygonF,
)
from PyQt6.QtWidgets import QApplication


def icon_pixmap(name: str, size: int, color: str) -> QPixmap:
    """Return a *size*×*size* QPixmap with icon *name* drawn in *color*.

    HiDPI-aware: backing store is created at physical pixel size and
    devicePixelRatio is set so Qt displays it at the correct logical size.
    """
    app = QApplication.instance()
    ratio = app.primaryScreen().devicePixelRatio() if app and app.primaryScreen() else 1.0
    px_size = int(size * ratio)
    px = QPixmap(px_size, px_size)
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setWidthF(max(1.2, size / 14))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    _DRAW.get(name, _draw_unknown)(p, size)
    p.end()
    return px


# ── individual draw functions ──────────────────────────────────────────────────

def _draw_unknown(p: QPainter, s: int) -> None:
    m = s * 0.15
    p.drawEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))


def _draw_mouse_pointer(p: QPainter, s: int) -> None:
    """↖ arrow cursor."""
    pts = QPolygonF([
        QPointF(s * 0.15, s * 0.10),
        QPointF(s * 0.15, s * 0.78),
        QPointF(s * 0.32, s * 0.58),
        QPointF(s * 0.50, s * 0.84),
        QPointF(s * 0.60, s * 0.78),
        QPointF(s * 0.42, s * 0.52),
        QPointF(s * 0.67, s * 0.52),
    ])
    path = QPainterPath()
    path.addPolygon(pts)
    path.closeSubpath()
    old_brush = p.brush()
    p.setBrush(QBrush(p.pen().color()))
    p.drawPath(path)
    p.setBrush(old_brush)


def _draw_crop(p: QPainter, s: int) -> None:
    m = s * 0.20
    o = s * 0.08
    # vertical left
    p.drawLine(QPointF(m, o), QPointF(m, s - m))
    # horizontal bottom
    p.drawLine(QPointF(o, s - m), QPointF(s - o, s - m))
    # corner pieces
    p.drawLine(QPointF(s - m, m), QPointF(s - m, s - m))
    p.drawLine(QPointF(m, m), QPointF(s - o, m))


def _draw_pen_tool(p: QPainter, s: int) -> None:
    path = QPainterPath()
    path.moveTo(s * 0.5,  s * 0.1)
    path.cubicTo(s * 0.9, s * 0.3, s * 0.9, s * 0.7, s * 0.5, s * 0.85)
    path.cubicTo(s * 0.1, s * 0.7, s * 0.1, s * 0.3, s * 0.5, s * 0.1)
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.5, s * 0.85), QPointF(s * 0.5, s * 0.95))


def _draw_paintbrush(p: QPainter, s: int) -> None:
    # handle
    p.drawLine(QPointF(s * 0.72, s * 0.10), QPointF(s * 0.28, s * 0.54))
    # bristle tip
    path = QPainterPath()
    path.addEllipse(QRectF(s * 0.12, s * 0.60, s * 0.30, s * 0.32))
    p.drawPath(path)


def _draw_eraser(p: QPainter, s: int) -> None:
    m = s * 0.15
    # body
    path = QPainterPath()
    path.addRoundedRect(QRectF(m, s * 0.35, s - 2 * m, s * 0.35), 3, 3)
    p.drawPath(path)
    # ground line
    p.drawLine(QPointF(m, s * 0.82), QPointF(s - m, s * 0.82))


def _draw_type(p: QPainter, s: int) -> None:
    font = QFont("Inter", int(s * 0.6), QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "T")


def _draw_pipette(p: QPainter, s: int) -> None:
    # tip
    path = QPainterPath()
    path.moveTo(s * 0.22, s * 0.85)
    path.lineTo(s * 0.15, s * 0.70)
    path.lineTo(s * 0.50, s * 0.38)
    p.drawPath(path)
    # body
    p.drawLine(QPointF(s * 0.50, s * 0.38), QPointF(s * 0.72, s * 0.18))
    # cap circle
    p.drawEllipse(QRectF(s * 0.60, s * 0.10, s * 0.28, s * 0.28))


def _draw_wand(p: QPainter, s: int) -> None:
    p.drawLine(QPointF(s * 0.80, s * 0.20), QPointF(s * 0.20, s * 0.80))
    # sparkles
    for cx, cy, r in ((0.75, 0.12, 0.07), (0.88, 0.28, 0.05), (0.60, 0.08, 0.04)):
        p.drawEllipse(QRectF((cx - r) * s, (cy - r) * s, 2 * r * s, 2 * r * s))


def _draw_stamp(p: QPainter, s: int) -> None:
    # handle
    path = QPainterPath()
    path.addRoundedRect(QRectF(s * 0.30, s * 0.10, s * 0.40, s * 0.30), 3, 3)
    p.drawPath(path)
    # base
    path2 = QPainterPath()
    path2.addRoundedRect(QRectF(s * 0.15, s * 0.48, s * 0.70, s * 0.28), 3, 3)
    p.drawPath(path2)
    p.drawLine(QPointF(s * 0.15, s * 0.80), QPointF(s * 0.85, s * 0.80))


def _draw_undo(p: QPainter, s: int) -> None:
    path = QPainterPath()
    path.moveTo(s * 0.45, s * 0.20)
    path.arcTo(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 90, 270)
    p.drawPath(path)
    # arrow head
    tip = QPointF(s * 0.45, s * 0.20)
    p.drawLine(tip, QPointF(s * 0.25, s * 0.20))
    p.drawLine(QPointF(s * 0.25, s * 0.20), QPointF(s * 0.32, s * 0.10))
    p.drawLine(QPointF(s * 0.25, s * 0.20), QPointF(s * 0.32, s * 0.32))


def _draw_redo(p: QPainter, s: int) -> None:
    path = QPainterPath()
    path.moveTo(s * 0.55, s * 0.20)
    path.arcTo(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 90, -270)
    p.drawPath(path)
    tip = QPointF(s * 0.55, s * 0.20)
    p.drawLine(tip, QPointF(s * 0.75, s * 0.20))
    p.drawLine(QPointF(s * 0.75, s * 0.20), QPointF(s * 0.68, s * 0.10))
    p.drawLine(QPointF(s * 0.75, s * 0.20), QPointF(s * 0.68, s * 0.32))


def _draw_save(p: QPainter, s: int) -> None:
    m = s * 0.12
    path = QPainterPath()
    path.addRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 3, 3)
    p.drawPath(path)
    # inner rect (data area)
    p.drawRect(QRectF(s * 0.30, s * 0.52, s * 0.40, s * 0.30))
    # top notch
    p.drawRect(QRectF(s * 0.30, s * 0.12, s * 0.32, s * 0.24))


def _draw_share(p: QPainter, s: int) -> None:
    cx = s * 0.5
    # arrow shaft + head
    p.drawLine(QPointF(cx, s * 0.60), QPointF(cx, s * 0.18))
    p.drawLine(QPointF(cx, s * 0.18), QPointF(s * 0.30, s * 0.38))
    p.drawLine(QPointF(cx, s * 0.18), QPointF(s * 0.70, s * 0.38))
    # tray
    p.drawLine(QPointF(s * 0.20, s * 0.70), QPointF(s * 0.20, s * 0.88))
    p.drawLine(QPointF(s * 0.20, s * 0.88), QPointF(s * 0.80, s * 0.88))
    p.drawLine(QPointF(s * 0.80, s * 0.88), QPointF(s * 0.80, s * 0.70))


def _draw_eye(p: QPainter, s: int) -> None:
    path = QPainterPath()
    path.moveTo(s * 0.10, s * 0.50)
    path.cubicTo(s * 0.30, s * 0.20, s * 0.70, s * 0.20, s * 0.90, s * 0.50)
    path.cubicTo(s * 0.70, s * 0.80, s * 0.30, s * 0.80, s * 0.10, s * 0.50)
    p.drawPath(path)
    p.drawEllipse(QRectF(s * 0.37, s * 0.37, s * 0.26, s * 0.26))


def _draw_lock(p: QPainter, s: int) -> None:
    # shackle
    path = QPainterPath()
    path.moveTo(s * 0.30, s * 0.48)
    path.lineTo(s * 0.30, s * 0.30)
    path.arcTo(QRectF(s * 0.28, s * 0.14, s * 0.44, s * 0.36), 180, -180)
    path.lineTo(s * 0.72, s * 0.48)
    p.drawPath(path)
    # body
    path2 = QPainterPath()
    path2.addRoundedRect(QRectF(s * 0.18, s * 0.48, s * 0.64, s * 0.40), 3, 3)
    p.drawPath(path2)


def _draw_plus(p: QPainter, s: int) -> None:
    m = s * 0.20
    cx = s / 2
    p.drawLine(QPointF(cx, m), QPointF(cx, s - m))
    p.drawLine(QPointF(m, cx), QPointF(s - m, cx))


def _draw_folder_plus(p: QPainter, s: int) -> None:
    m = s * 0.10
    # folder body
    path = QPainterPath()
    path.addRoundedRect(QRectF(m, s * 0.32, s - 2 * m, s * 0.56), 2, 2)
    p.drawPath(path)
    # tab
    p.drawRoundedRect(QRectF(m, s * 0.20, s * 0.35, s * 0.16), 2, 2)
    # plus
    cx, cy, r = s * 0.60, s * 0.59, s * 0.14
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))


def _draw_trash(p: QPainter, s: int) -> None:
    m = s * 0.18
    # lid
    p.drawLine(QPointF(m, s * 0.26), QPointF(s - m, s * 0.26))
    p.drawLine(QPointF(s * 0.38, s * 0.14), QPointF(s * 0.62, s * 0.14))
    # body
    path = QPainterPath()
    path.addRoundedRect(QRectF(s * 0.24, s * 0.34, s * 0.52, s * 0.52), 2, 2)
    p.drawPath(path)
    # lines
    cx = s / 2
    p.drawLine(QPointF(cx, s * 0.42), QPointF(cx, s * 0.78))
    p.drawLine(QPointF(s * 0.36, s * 0.42), QPointF(s * 0.36, s * 0.78))
    p.drawLine(QPointF(s * 0.64, s * 0.42), QPointF(s * 0.64, s * 0.78))


def _draw_circle_dashed(p: QPainter, s: int) -> None:
    pen = QPen(p.pen())
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    m = s * 0.15
    p.drawEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))


def _draw_arrow_up(p: QPainter, s: int) -> None:
    cx = s / 2
    p.drawLine(QPointF(cx, s * 0.82), QPointF(cx, s * 0.20))
    p.drawLine(QPointF(cx, s * 0.20), QPointF(s * 0.30, s * 0.46))
    p.drawLine(QPointF(cx, s * 0.20), QPointF(s * 0.70, s * 0.46))


def _draw_arrow_down(p: QPainter, s: int) -> None:
    cx = s / 2
    p.drawLine(QPointF(cx, s * 0.18), QPointF(cx, s * 0.80))
    p.drawLine(QPointF(cx, s * 0.80), QPointF(s * 0.30, s * 0.54))
    p.drawLine(QPointF(cx, s * 0.80), QPointF(s * 0.70, s * 0.54))


def _draw_more_horizontal(p: QPainter, s: int) -> None:
    cy = s / 2
    for cx in (s * 0.22, s * 0.50, s * 0.78):
        r = s * 0.07
        p.setBrush(QBrush(p.pen().color()))
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _draw_grid(p: QPainter, s: int) -> None:
    m = s * 0.15
    step = (s - 2 * m) / 3
    for i in range(4):
        x = m + i * step
        p.drawLine(QPointF(x, m), QPointF(x, s - m))
        p.drawLine(QPointF(m, x), QPointF(s - m, x))


def _draw_ruler(p: QPainter, s: int) -> None:
    m = s * 0.12
    path = QPainterPath()
    path.addRoundedRect(QRectF(m, s * 0.35, s - 2 * m, s * 0.30), 2, 2)
    p.drawPath(path)
    tick_y = s * 0.43
    for i in range(6):
        x = m + (s - 2 * m) * i / 5
        h = s * 0.14 if i % 2 == 0 else s * 0.08
        p.drawLine(QPointF(x, tick_y), QPointF(x, tick_y + h))


def _draw_chevron_down(p: QPainter, s: int) -> None:
    m = s * 0.22
    cy = s * 0.42
    p.drawLine(QPointF(m, cy), QPointF(s / 2, cy + s * 0.22))
    p.drawLine(QPointF(s / 2, cy + s * 0.22), QPointF(s - m, cy))


def _draw_user(p: QPainter, s: int) -> None:
    # head
    p.drawEllipse(QRectF(s * 0.30, s * 0.10, s * 0.40, s * 0.36))
    # shoulders arc
    path = QPainterPath()
    path.moveTo(s * 0.08, s * 0.92)
    path.cubicTo(s * 0.08, s * 0.62, s * 0.92, s * 0.62, s * 0.92, s * 0.92)
    p.drawPath(path)


def _draw_minus(p: QPainter, s: int) -> None:
    m = s * 0.20
    cy = s / 2
    p.drawLine(QPointF(m, cy), QPointF(s - m, cy))


def _draw_search(p: QPainter, s: int) -> None:
    r = s * 0.32
    cx, cy = s * 0.38, s * 0.38
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    p.drawLine(QPointF(cx + r * 0.72, cy + r * 0.72),
               QPointF(s * 0.85, s * 0.85))


def _draw_upload(p: QPainter, s: int) -> None:
    _draw_share(p, s)


def _draw_tag(p: QPainter, s: int) -> None:
    path = QPainterPath()
    path.moveTo(s * 0.16, s * 0.16)
    path.lineTo(s * 0.54, s * 0.16)
    path.lineTo(s * 0.86, s * 0.50)
    path.lineTo(s * 0.54, s * 0.84)
    path.lineTo(s * 0.16, s * 0.84)
    path.closeSubpath()
    p.drawPath(path)
    # hole
    p.drawEllipse(QRectF(s * 0.24, s * 0.40, s * 0.16, s * 0.16))


def _draw_folder(p: QPainter, s: int) -> None:
    m = s * 0.10
    path = QPainterPath()
    path.addRoundedRect(QRectF(m, s * 0.32, s - 2 * m, s * 0.56), 2, 2)
    p.drawPath(path)
    p.drawRoundedRect(QRectF(m, s * 0.20, s * 0.35, s * 0.16), 2, 2)


def _draw_chevron_right(p: QPainter, s: int) -> None:
    m = s * 0.22
    cx = s * 0.42
    p.drawLine(QPointF(cx, m), QPointF(cx + s * 0.22, s / 2))
    p.drawLine(QPointF(cx + s * 0.22, s / 2), QPointF(cx, s - m))


def _draw_rotate_ccw(p: QPainter, s: int) -> None:
    """Counter-clockwise circular reset arrow."""
    path = QPainterPath()
    path.moveTo(s * 0.28, s * 0.22)
    path.arcTo(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64), 120, 270)
    p.drawPath(path)
    # arrowhead at start
    tip = QPointF(s * 0.28, s * 0.22)
    p.drawLine(tip, QPointF(s * 0.12, s * 0.24))
    p.drawLine(tip, QPointF(s * 0.30, s * 0.08))


def _draw_sparkles(p: QPainter, s: int) -> None:
    """Four-point star / sparkle icon."""
    import math
    cx, cy = s * 0.50, s * 0.50
    outer, inner = s * 0.40, s * 0.16
    pts = []
    for i in range(8):
        r = outer if i % 2 == 0 else inner
        a = math.radians(i * 45 - 90)
        pts.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
    path = QPainterPath()
    path.moveTo(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    path.closeSubpath()
    old_brush = p.brush()
    p.setBrush(QBrush(p.pen().color()))
    p.drawPath(path)
    p.setBrush(old_brush)


def _draw_crosshair(p: QPainter, s: int) -> None:
    cx, cy, r, gap = s / 2, s / 2, s * 0.38, s * 0.12
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    m = s * 0.08
    p.drawLine(QPointF(m, cy), QPointF(cx - gap, cy))
    p.drawLine(QPointF(cx + gap, cy), QPointF(s - m, cy))
    p.drawLine(QPointF(cx, m), QPointF(cx, cy - gap))
    p.drawLine(QPointF(cx, cy + gap), QPointF(cx, s - m))


def _draw_trending_up(p: QPainter, s: int) -> None:
    m = s * 0.15
    # rising line
    p.drawLine(QPointF(m, s - m), QPointF(s * 0.42, s * 0.45))
    p.drawLine(QPointF(s * 0.42, s * 0.45), QPointF(s * 0.62, s * 0.65))
    p.drawLine(QPointF(s * 0.62, s * 0.65), QPointF(s - m, m))
    # arrowhead
    p.drawLine(QPointF(s - m, m), QPointF(s - m, s * 0.38))
    p.drawLine(QPointF(s - m, m), QPointF(s * 0.62, m))


def _draw_sliders_horizontal(p: QPainter, s: int) -> None:
    m = s * 0.12
    for y, hx in ((s * 0.30, s * 0.35), (s * 0.50, s * 0.60), (s * 0.70, s * 0.45)):
        p.drawLine(QPointF(m, y), QPointF(s - m, y))
        r = s * 0.07
        p.setBrush(QBrush(p.pen().color()))
        p.drawEllipse(QRectF(hx - r, y - r, 2 * r, 2 * r))
        p.setBrush(Qt.BrushStyle.NoBrush)


def _draw_layers(p: QPainter, s: int) -> None:
    m = s * 0.12
    for i, y in enumerate((s * 0.28, s * 0.50, s * 0.72)):
        w = s - 2 * m - i * s * 0.06
        x = m + i * s * 0.03
        p.drawRoundedRect(QRectF(x, y - s * 0.08, w, s * 0.14), 2, 2)


def _draw_clock(p: QPainter, s: int) -> None:
    cx, cy, r = s / 2, s / 2, s * 0.40
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy - r * 0.60))
    p.drawLine(QPointF(cx, cy), QPointF(cx + r * 0.45, cy + r * 0.30))


def _draw_circle_half_stroke(p: QPainter, s: int) -> None:
    import math as _math
    cx, cy, r = s / 2, s / 2, s * 0.38
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    # filled left half
    half = QPainterPath()
    half.moveTo(cx, cy - r)
    half.arcTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), 90, 180)
    half.closeSubpath()
    old_brush = p.brush()
    p.setBrush(QBrush(p.pen().color()))
    p.drawPath(half)
    p.setBrush(old_brush)


def _draw_image(p: QPainter, s: int) -> None:
    m = s * 0.14
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    p.drawRoundedRect(rect, 2, 2)
    p.drawEllipse(QRectF(s * 0.26, s * 0.28, s * 0.12, s * 0.12))
    path = QPainterPath()
    path.moveTo(s * 0.26, s * 0.72)
    path.lineTo(s * 0.46, s * 0.52)
    path.lineTo(s * 0.58, s * 0.62)
    path.lineTo(s * 0.74, s * 0.44)
    p.drawPath(path)


def _draw_sun_medium(p: QPainter, s: int) -> None:
    cx, cy, r = s / 2, s / 2, s * 0.18
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    inner = s * 0.30
    outer = s * 0.42
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0), (0.7, -0.7), (0.7, 0.7), (-0.7, 0.7), (-0.7, -0.7)):
        p.drawLine(
            QPointF(cx + dx * inner, cy + dy * inner),
            QPointF(cx + dx * outer, cy + dy * outer),
        )


def _draw_thermometer(p: QPainter, s: int) -> None:
    bulb_r = s * 0.16
    stem_x = s * 0.50
    p.drawLine(QPointF(stem_x, s * 0.20), QPointF(stem_x, s * 0.64))
    p.drawEllipse(QRectF(stem_x - bulb_r, s * 0.62, bulb_r * 2, bulb_r * 2))
    path = QPainterPath()
    path.moveTo(s * 0.38, s * 0.24)
    path.arcTo(QRectF(s * 0.38, s * 0.14, s * 0.24, s * 0.20), 180, -180)
    path.lineTo(s * 0.62, s * 0.62)
    p.drawPath(path)


def _draw_droplet(p: QPainter, s: int) -> None:
    path = QPainterPath()
    path.moveTo(s * 0.50, s * 0.14)
    path.cubicTo(s * 0.68, s * 0.32, s * 0.80, s * 0.48, s * 0.80, s * 0.62)
    path.cubicTo(s * 0.80, s * 0.82, s * 0.66, s * 0.90, s * 0.50, s * 0.90)
    path.cubicTo(s * 0.34, s * 0.90, s * 0.20, s * 0.82, s * 0.20, s * 0.62)
    path.cubicTo(s * 0.20, s * 0.48, s * 0.32, s * 0.32, s * 0.50, s * 0.14)
    p.drawPath(path)


def _draw_compare(p: QPainter, s: int) -> None:
    outer = QPainterPath()
    outer.addRoundedRect(QRectF(s * 0.18, s * 0.14, s * 0.64, s * 0.72), 3, 3)
    p.drawPath(outer)
    p.drawLine(QPointF(s * 0.50, s * 0.18), QPointF(s * 0.50, s * 0.82))
    p.drawLine(QPointF(s * 0.32, s * 0.28), QPointF(s * 0.32, s * 0.72))
    p.drawLine(QPointF(s * 0.68, s * 0.28), QPointF(s * 0.68, s * 0.72))


# ── dispatch table ─────────────────────────────────────────────────────────────
_DRAW = {
    "mouse-pointer":   _draw_mouse_pointer,
    "cursor":          _draw_mouse_pointer,
    "crop":            _draw_crop,
    "pen-tool":        _draw_pen_tool,
    "paintbrush":      _draw_paintbrush,
    "eraser":          _draw_eraser,
    "type":            _draw_type,
    "pipette":         _draw_pipette,
    "eyedropper":      _draw_pipette,
    "wand-2":          _draw_wand,
    "stamp":           _draw_stamp,
    "undo-2":          _draw_undo,
    "undo":            _draw_undo,
    "redo-2":          _draw_redo,
    "redo":            _draw_redo,
    "save":            _draw_save,
    "share":           _draw_share,
    "eye":             _draw_eye,
    "lock":            _draw_lock,
    "plus":            _draw_plus,
    "folder-plus":     _draw_folder_plus,
    "trash-2":         _draw_trash,
    "trash":           _draw_trash,
    "circle-dashed":   _draw_circle_dashed,
    "arrow-up":        _draw_arrow_up,
    "arrow-down":      _draw_arrow_down,
    "more-horizontal": _draw_more_horizontal,
    "grid-3x3":        _draw_grid,
    "ruler":           _draw_ruler,
    "chevron-down":         _draw_chevron_down,
    "chevron-right":        _draw_chevron_right,
    "user":                 _draw_user,
    "minus":                _draw_minus,
    "search":               _draw_search,
    "upload":               _draw_upload,
    "tag":                  _draw_tag,
    "folder":               _draw_folder,
    "rotate-ccw":           _draw_rotate_ccw,
    "sparkles":             _draw_sparkles,
    "star":                 _draw_sparkles,
    "crosshair":            _draw_crosshair,
    "trending-up":          _draw_trending_up,
    "sliders-horizontal":   _draw_sliders_horizontal,
    "layers":               _draw_layers,
    "clock":                _draw_clock,
    "circle-half-stroke":   _draw_circle_half_stroke,
    "image":                _draw_image,
    "sun-medium":           _draw_sun_medium,
    "thermometer":          _draw_thermometer,
    "droplet":              _draw_droplet,
    "compare":              _draw_compare,
}
