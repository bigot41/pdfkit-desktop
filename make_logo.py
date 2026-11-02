"""Draws logo.png and logo.ico. Run once: python make_logo.py"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen)

app = QGuiApplication([])
S = 512
img = QImage(S, S, QImage.Format_ARGB32)
img.fill(Qt.transparent)
qp = QPainter(img)
qp.setRenderHint(QPainter.Antialiasing)

# rounded-square background, indigo -> teal
bg = QLinearGradient(0, 0, S, S)
bg.setColorAt(0, QColor("#5B6CFF"))
bg.setColorAt(1, QColor("#1FB5B8"))
qp.setBrush(bg)
qp.setPen(Qt.NoPen)
qp.drawRoundedRect(QRectF(16, 16, S - 32, S - 32), 112, 112)

# white page with a folded corner
x, y, w, h, fold = 128, 84, 256, 344, 76
page = QPainterPath()
page.moveTo(x + 24, y)
page.lineTo(x + w - fold, y)
page.lineTo(x + w, y + fold)
page.lineTo(x + w, y + h - 24)
page.quadTo(x + w, y + h, x + w - 24, y + h)
page.lineTo(x + 24, y + h)
page.quadTo(x, y + h, x, y + h - 24)
page.lineTo(x, y + 24)
page.quadTo(x, y, x + 24, y)
qp.setBrush(QColor("#FFFFFF"))
qp.drawPath(page)
corner = QPainterPath()
corner.moveTo(x + w - fold, y)
corner.lineTo(x + w - fold, y + fold)
corner.lineTo(x + w, y + fold)
corner.closeSubpath()
qp.setBrush(QColor("#CFD6FF"))
qp.drawPath(corner)

# text lines + a yellow highlight swipe
qp.setBrush(QColor("#B9C1E6"))
for i, wd in enumerate((176, 176, 120)):
    qp.drawRoundedRect(QRectF(x + 40, y + 120 + i * 56, wd, 18), 9, 9)
qp.setBrush(QColor(255, 214, 10, 215))
qp.drawRoundedRect(QRectF(x + 28, y + 168, 200, 40), 12, 12)
qp.setBrush(QColor("#B9C1E6"))
qp.drawRoundedRect(QRectF(x + 40, y + 177, 176, 18), 9, 9)
qp.end()

img.save("logo.png")
img.scaled(256, 256, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).save("logo_256.png")
from PIL import Image
Image.open("logo.png").save("logo.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
