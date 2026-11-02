"""Colours, stylesheet and drawn icons for PDFKit."""
from string import Template

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

LIGHT = dict(bg="#F4F5F8", panel="#FFFFFF", text="#1E2330", muted="#5F6778", border="#D9DDE6",
             accent="#4F63F0", accent_text="#FFFFFF", canvas="#E3E6EC", hover="#E9ECF6", paper="#FFFFFF")
DARK = dict(bg="#171A21", panel="#20242D", text="#E8EAF0", muted="#9AA3B5", border="#323846",
            accent="#8195FF", accent_text="#10131A", canvas="#0F1116", hover="#2A3040", paper="#FFFFFF")

QSS = Template("""
QWidget { color:$text; font-family:"Segoe UI"; font-size:10pt; }
QMainWindow, QDialog, QMessageBox, QInputDialog { background:$bg; }
QToolBar { background:$panel; border:0; border-bottom:1px solid $border; spacing:2px; padding:4px 8px; }
QToolBar::separator { background:$border; width:1px; margin:8px 6px; }
QToolButton { background:transparent; border:1px solid transparent; border-radius:8px; padding:4px 7px; color:$text; font-size:9pt; }
QToolButton:hover { background:$hover; }
QToolButton:checked { background:$accent; color:$accent_text; }
QToolButton:focus { border:1px solid $accent; }
QToolButton#swatch { padding:2px; }
QToolButton#swatch:checked { background:transparent; }
QTabWidget::pane { border:0; }
QTabBar { background:$panel; }
QTabBar::tab { background:transparent; padding:8px 16px; border:0; border-bottom:2px solid transparent; color:$muted; }
QTabBar::tab:selected { color:$text; border-bottom:2px solid $accent; }
QTabBar::tab:hover { background:$hover; }
QLineEdit { background:$bg; border:1px solid $border; border-radius:8px; padding:5px 10px; selection-background-color:$accent; selection-color:$accent_text; }
QLineEdit:focus { border:1px solid $accent; }
QPushButton { background:$panel; border:1px solid $border; border-radius:8px; padding:6px 16px; }
QPushButton:hover { background:$hover; }
QPushButton:focus { border:1px solid $accent; }
QPushButton#primary { background:$accent; color:$accent_text; border:0; padding:10px 28px; font-size:11pt; font-weight:600; }
QPushButton#primary:hover { background:$accent; }
QMenuBar { background:$panel; border-bottom:1px solid $border; }
QMenuBar::item { padding:5px 10px; background:transparent; border-radius:6px; }
QMenuBar::item:selected { background:$hover; }
QMenu { background:$panel; border:1px solid $border; padding:4px; }
QMenu::item { padding:6px 28px 6px 16px; border-radius:6px; }
QMenu::item:selected { background:$accent; color:$accent_text; }
QMenu::separator { height:1px; background:$border; margin:4px 8px; }
QStatusBar { background:$panel; color:$muted; border-top:1px solid $border; }
QStatusBar QLabel { color:$muted; }
QDockWidget { font-weight:600; }
QDockWidget::title { background:$panel; padding:8px; border-bottom:1px solid $border; }
QTreeWidget, QListWidget { background:$panel; border:0; outline:0; }
QListWidget { border:1px solid $border; border-radius:10px; padding:4px; }
QTreeWidget::item, QListWidget::item { padding:5px; border-radius:6px; }
QTreeWidget::item:selected, QListWidget::item:selected { background:$accent; color:$accent_text; }
QTreeWidget::item:hover, QListWidget::item:hover { background:$hover; }
QScrollBar:vertical { background:transparent; width:13px; margin:0; }
QScrollBar::handle:vertical { background:$border; border-radius:5px; min-height:36px; margin:2px; }
QScrollBar::handle:vertical:hover { background:$muted; }
QScrollBar:horizontal { background:transparent; height:13px; margin:0; }
QScrollBar::handle:horizontal { background:$border; border-radius:5px; min-width:36px; margin:2px; }
QScrollBar::handle:horizontal:hover { background:$muted; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
QToolTip { background:$panel; color:$text; border:1px solid $border; padding:4px 6px; }
QLabel#title { font-size:24pt; font-weight:700; }
QLabel#sub { color:$muted; font-size:11pt; }
QLabel#muted { color:$muted; }
""")


def stylesheet(t):
    return QSS.substitute(t)


def _pen(c, w=1.8):
    return QPen(QColor(c), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _poly(pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _draw(name, qp, c):
    """Icons are drawn on a 24x24 grid."""
    qp.setPen(_pen(c))
    qp.setBrush(Qt.NoBrush)
    if name == "open":
        qp.drawPolygon(_poly([(3, 6), (9, 6), (11, 8), (20, 8), (20, 18), (3, 18)]))
    elif name == "save":
        qp.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        qp.drawRect(QRectF(8, 4, 8, 5))
        qp.drawRect(QRectF(7, 13, 10, 7))
    elif name == "undo":
        p = QPainterPath()
        p.moveTo(19, 18)
        p.cubicTo(19, 10, 12, 8, 6, 10)
        qp.drawPath(p)
        qp.drawLine(6, 10, 10, 6)
        qp.drawLine(6, 10, 10, 14)
    elif name in ("zoomin", "zoomout", "search"):
        qp.drawEllipse(QRectF(4, 4, 12, 12))
        qp.drawLine(14, 14, 20, 20)
        if name != "search":
            qp.drawLine(7.5, 10, 12.5, 10)
        if name == "zoomin":
            qp.drawLine(10, 7.5, 10, 12.5)
    elif name == "fit":
        qp.drawLine(5, 12, 19, 12)
        qp.drawLine(5, 12, 8, 9)
        qp.drawLine(5, 12, 8, 15)
        qp.drawLine(19, 12, 16, 9)
        qp.drawLine(19, 12, 16, 15)
        qp.drawLine(3, 6, 3, 18)
        qp.drawLine(21, 6, 21, 18)
    elif name == "night":
        moon = QPainterPath()
        moon.addEllipse(QRectF(5, 4, 15, 16))
        cut = QPainterPath()
        cut.addEllipse(QRectF(10, 2, 14, 16))
        qp.setBrush(QColor(c))
        qp.drawPath(moon.subtracted(cut))
    elif name == "contents":
        for y in (7, 12, 17):
            qp.drawLine(9, y, 20, y)
            qp.drawPoint(5, y)
    elif name == "hand":
        qp.setBrush(QColor(c))
        qp.drawPolygon(_poly([(6, 3), (6, 19), (10, 15), (13, 21), (15.5, 20), (12.5, 14), (17.5, 14)]))
    elif name == "select":
        qp.drawLine(12, 4, 12, 20)
        qp.drawLine(9, 4, 15, 4)
        qp.drawLine(9, 20, 15, 20)
    elif name == "highlight":
        qp.drawPolygon(_poly([(14, 3), (20, 9), (11, 17), (6, 17), (6, 12)]))
        qp.setPen(_pen("#F5C518", 3.2))
        qp.drawLine(3, 21, 21, 21)
    elif name == "underline":
        p = QPainterPath()
        p.moveTo(7, 4)
        p.lineTo(7, 11)
        p.arcTo(QRectF(7, 7, 10, 8), 180, 180)
        p.lineTo(17, 4)
        qp.drawPath(p)
        qp.drawLine(5, 20, 19, 20)
    elif name == "strike":
        f = QFont("Segoe UI", 1)
        f.setPixelSize(17)
        f.setBold(True)
        qp.setFont(f)
        qp.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "S")
        qp.drawLine(3, 12, 21, 12)
    elif name == "note":
        qp.drawRoundedRect(QRectF(3, 4, 18, 13), 2, 2)
        qp.drawPolyline(_poly([(8, 17), (8, 21), (12, 17)]))
        qp.drawLine(7, 9, 17, 9)
        qp.drawLine(7, 12, 13, 12)
    elif name == "text":
        qp.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        qp.drawLine(8, 9, 16, 9)
        qp.drawLine(12, 9, 12, 16)
    elif name == "draw":
        p = QPainterPath()
        p.moveTo(3, 15)
        p.cubicTo(6, 4, 9, 4, 11, 12)
        p.cubicTo(13, 20, 17, 16, 21, 7)
        qp.drawPath(p)
    elif name == "box":
        qp.drawRoundedRect(QRectF(4, 6, 16, 12), 2, 2)
    elif name == "sign":
        p = QPainterPath()
        p.moveTo(3, 15)
        p.cubicTo(5, 5, 8, 5, 8, 12)
        p.cubicTo(8, 17, 11, 9, 13, 11)
        p.cubicTo(15, 13, 14, 15, 17, 14)
        p.lineTo(21, 12)
        qp.drawPath(p)
        qp.drawLine(3, 20, 21, 20)
    elif name == "erase":
        qp.save()
        qp.translate(12, 11)
        qp.rotate(-45)
        qp.drawRoundedRect(QRectF(-8, -4, 16, 8), 2, 2)
        qp.drawLine(0, -4, 0, 4)
        qp.restore()
        qp.drawLine(4, 21, 20, 21)


def _pix(name, c, size=24, dpr=3):
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    qp = QPainter(pm)
    qp.setRenderHint(QPainter.Antialiasing)
    _draw(name, qp, c)
    qp.end()
    return pm


def icon(name, t):
    """Normal colour when off, accent-contrast colour when the button is checked."""
    ic = QIcon()
    ic.addPixmap(_pix(name, t["text"]), QIcon.Normal, QIcon.Off)
    ic.addPixmap(_pix(name, t["accent_text"]), QIcon.Normal, QIcon.On)
    return ic


def swatch(rgb, t):
    col = QColor(*[int(x * 255) for x in rgb])
    ic = QIcon()
    for state, ring in ((QIcon.Off, False), (QIcon.On, True)):
        pm = QPixmap(72, 72)
        pm.setDevicePixelRatio(3)
        pm.fill(Qt.transparent)
        qp = QPainter(pm)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.setBrush(col)
        qp.setPen(_pen(t["border"], 1))
        qp.drawEllipse(QRectF(5, 5, 14, 14))
        if ring:
            qp.setBrush(Qt.NoBrush)
            qp.setPen(_pen(t["text"], 2))
            qp.drawEllipse(QRectF(2, 2, 20, 20))
        qp.end()
        ic.addPixmap(pm, QIcon.Normal, state)
    return ic
