"""Colours, stylesheet and drawn icons for PDFKit.

One neutral (warm stone), one accent (deep emerald), one corner radius (6px).
"""
from string import Template

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

LIGHT = dict(bg="#F5F5F4", panel="#FAFAF9", text="#1C1917", muted="#57534E", border="#D6D3D1",
             accent="#0B7A5A", accent_text="#FAFAF9", canvas="#E7E5E4", hover="#ECEBE9",
             page_ink=None, page_bg=None)
DARK = dict(bg="#1C1917", panel="#211F1D", text="#F5F5F4", muted="#A8A29E", border="#3A3633",
            accent="#34D399", accent_text="#052E22", canvas="#141211", hover="#2B2825",
            page_ink=0xD6D3D1, page_bg=0x1C1917)  # pages are tinted to these instead of pure black/white

QSS = Template("""
QWidget { color:$text; font-family:"Segoe UI"; font-size:10pt; }
QMainWindow, QDialog, QMessageBox, QInputDialog { background:$bg; }
QToolBar { background:$panel; border:0; border-bottom:1px solid $border; spacing:2px; padding:4px 8px; }
QToolBar::separator { background:$border; width:1px; margin:8px 6px; }
QToolButton { background:transparent; border:1px solid transparent; border-radius:6px; padding:4px 8px; color:$text; font-size:9pt; }
QToolButton:hover { background:$hover; }
QToolButton:checked { background:$accent; color:$accent_text; }
QToolButton:focus { border:1px solid $accent; }
QTabWidget::pane { border:0; }
QTabBar { background:$panel; }
QTabBar::tab { background:transparent; padding:8px 16px; border:0; border-bottom:2px solid transparent; color:$muted; }
QTabBar::tab:selected { color:$text; border-bottom:2px solid $accent; }
QTabBar::tab:hover { background:$hover; }
QLineEdit { background:$bg; border:1px solid $border; border-radius:6px; padding:5px 10px; selection-background-color:$accent; selection-color:$accent_text; }
QLineEdit:focus { border:1px solid $accent; }
QPushButton { background:$panel; border:1px solid $border; border-radius:6px; padding:6px 16px; }
QPushButton:hover { background:$hover; }
QPushButton:focus { border:1px solid $accent; }
QPushButton#primary { background:$accent; color:$accent_text; border:0; padding:9px 22px; font-weight:600; }
QMenuBar { background:$panel; border-bottom:1px solid $border; }
QMenuBar::item { padding:5px 10px; background:transparent; border-radius:6px; }
QMenuBar::item:selected { background:$hover; }
QMenu { background:$panel; border:1px solid $border; padding:4px; }
QMenu::item { padding:6px 28px 6px 16px; border-radius:6px; }
QMenu::item:selected { background:$accent; color:$accent_text; }
QMenu::separator { height:1px; background:$border; margin:4px 8px; }
QStatusBar { background:$panel; color:$muted; border-top:1px solid $border; }
QStatusBar QLabel { color:$muted; }
QDockWidget::title { background:$panel; padding:8px; border-bottom:1px solid $border; }
QTreeWidget, QListWidget { background:$panel; border:0; outline:0; }
QListWidget { border:1px solid $border; border-radius:6px; padding:4px; }
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
QLabel#title { font-size:22pt; font-weight:700; }
QLabel#sub { color:$muted; font-size:11pt; }
QLabel#muted { color:$muted; }
""")


def stylesheet(t):
    return QSS.substitute({k: v for k, v in t.items() if isinstance(v, str)})


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
    elif name == "edit":
        qp.drawPolygon(_poly([(4, 20), (4, 16), (16, 4), (20, 8), (8, 20)]))
        qp.drawLine(13, 7, 17, 11)


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
