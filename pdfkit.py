import hashlib
import json
import os
import sys
from bisect import bisect_right
from collections import OrderedDict

import pymupdf as fitz
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QGuiApplication, QIcon, QImage,
                           QKeySequence, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QDialog, QDockWidget, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import theme

GAP, MARGIN, PADX = 10, 8, 16  # between pages / above first and below last / left-right
CACHE_PAGES = 16
EXTS = "pdf epub mobi fb2 xps oxps cbz svg txt jpg jpeg png bmp gif tif tiff webp"
FILTER = "Documents (%s);;All files (*)" % " ".join("*." + e for e in EXTS.split())
SIG_PATH = os.path.join(os.environ.get("APPDATA", "."), "PDFKit", "signature.png")
COLORS = {"Yellow": (1, .92, .2), "Green": (.45, .9, .45), "Pink": (1, .55, .75),
          "Blue": (.45, .7, 1), "Red": (.9, .15, .15), "Black": (0, 0, 0)}
HAND, SELECT, HIGHLIGHT, UNDERLINE, STRIKE, NOTE, TEXT, DRAW, RECT, SIGN, ERASE = range(11)
TOOLS = [  # id, label, icon, shortcut, hint
    (HAND, "Move", "hand", "V", "Drag to move around. In books, Left/Right arrows turn pages."),
    (SELECT, "Copy text", "select", "T", "Drag over text to copy it."),
    (HIGHLIGHT, "Highlight", "highlight", "H", "Drag across text to highlight it."),
    (UNDERLINE, "Underline", "underline", "U", "Drag across text to underline it."),
    (STRIKE, "Strike", "strike", "K", "Drag across text to strike it out."),
    (NOTE, "Note", "note", "N", "Click where you want a note."),
    (TEXT, "Text", "text", "X", "Drag a box, then type your text."),
    (DRAW, "Draw", "draw", "D", "Press and draw freely."),
    (RECT, "Box", "box", "R", "Drag to draw a box."),
    (SIGN, "Sign", "sign", "G", "Click where the signature goes. The first time, you draw it."),
    (ERASE, "Erase", "erase", "E", "Click an annotation to remove it."),
]
CURSORS = {HAND: Qt.OpenHandCursor, SELECT: Qt.IBeamCursor}


def resource(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), name)


def parse_pages(text, count):
    """'1-3, 5, 8-' -> zero-based page indexes (order kept)."""
    out = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out += range(int(a or 1) - 1, int(b or count))
        else:
            out.append(int(part) - 1)
    if any(i < 0 or i >= count for i in out):
        raise ValueError("page out of range")
    return out


def pos_key(path):
    return "pos/" + hashlib.md5(os.path.abspath(path).lower().encode()).hexdigest()


class Canvas(QWidget):
    """One widget paints every visible page. No per-page widgets, so zoom and scroll stay cheap."""

    def __init__(self, view):
        super().__init__()
        self.v = view
        self.drag = None   # [page, QPoint, QPoint] in canvas coordinates
        self.path = []     # ink points in canvas coordinates
        self.ink_page = 0
        self.pan = None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        v, p = self.v, e.position().toPoint()
        v.setFocus()
        if v.tool == HAND:
            self.pan = (e.globalPosition().toPoint(), v.horizontalScrollBar().value(),
                        v.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor)
            return
        i = v.page_at(p)
        if i is None:
            return
        if v.tool in (NOTE, SIGN, ERASE):
            v.click(i, v.local(i, p))
        elif v.tool == DRAW:
            self.path, self.ink_page = [p], i
        else:
            self.drag = [i, p, p]

    def mouseMoveEvent(self, e):
        v = self.v
        if self.pan:
            g0, hx, vy = self.pan
            d = e.globalPosition().toPoint() - g0
            v.horizontalScrollBar().setValue(hx - d.x())
            v.verticalScrollBar().setValue(vy - d.y())
        elif self.path:
            self.path.append(e.position().toPoint())
            self.update()
        elif self.drag:
            self.drag[2] = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        v = self.v
        if self.pan:
            self.pan = None
            self.setCursor(CURSORS.get(v.tool, Qt.CrossCursor))
        elif self.path:
            pts, i, self.path = self.path, self.ink_page, []
            self.update()
            v.finish_ink(i, [v.local(i, p) for p in pts])
        elif self.drag:
            i, a, b = self.drag
            self.drag = None
            self.update()
            qr = QRect(v.local(i, a), v.local(i, b)).normalized()
            v.finish_rect(i, qr & QRect(0, 0, v.ws[i], v.hs[i]))

    def paintEvent(self, e):
        v, t = self.v, self.v.win.theme
        qp = QPainter(self)
        qp.fillRect(e.rect(), QColor(t["canvas"]))
        lo, hi = v.visible(e.rect().top(), e.rect().bottom())
        for i in range(lo, hi):
            r = v.page_rect(i)
            if not r.intersects(e.rect()):
                continue
            qp.fillRect(r.adjusted(-1, -1, 1, 1), QColor(t["border"]))
            qp.fillRect(r, QColor(t["paper"]))
            qp.drawPixmap(r, v.pixmap(i))
            if v.hit and v.hit[0] == i:
                qp.setBrush(QColor(255, 140, 0, 95))
                qp.setPen(Qt.NoPen)
                for h in v.hit[1]:
                    qp.drawRect(QRectF(r.x() + h.x0 * v.s, r.y() + h.y0 * v.s, h.width * v.s, h.height * v.s))
        if self.drag:
            qp.setPen(QPen(QColor(t["accent"]), 1))
            c = QColor(t["accent"])
            c.setAlpha(50)
            qp.setBrush(c)
            qp.drawRect(QRect(self.drag[1], self.drag[2]).normalized())
        if self.path:
            qp.setBrush(Qt.NoBrush)
            qp.setPen(QPen(QColor(*[int(x * 255) for x in v.win.color()]), 2))
            qp.drawPolyline([QPointF(p) for p in self.path])


class DocView(QScrollArea):
    def __init__(self, path, doc, win):
        super().__init__()
        self.path, self.doc, self.win = path, doc, win
        self.reflow = doc.is_reflowable
        saved = json.loads(win.settings.value(pos_key(path), "[0, 12]"))
        self.start_page, self.fontsize = saved[0], saved[1]
        self.dark, self.tool = win.dark, win.tool
        self.undo_stack, self.dirty = [], False
        self.q, self.hp, self.hi, self.hl, self.hit = None, 0, 0, None, None
        self.cache = OrderedDict()  # page -> ((scale, dark), QPixmap)
        self.fit, self.zoom, self.s = True, 1.0, 1.0
        self.sizes, self.tops, self.hs, self.ws, self.xs = [], [], [], [], []
        self._pdf = None
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # constant width: no resize feedback loop
        self.setFocusPolicy(Qt.StrongFocus)
        self.verticalScrollBar().setSingleStep(60)
        self.canvas = Canvas(self)
        self.canvas.setCursor(CURSORS.get(self.tool, Qt.CrossCursor))
        self.setWidget(self.canvas)
        self.crisp = QTimer(self, singleShot=True, interval=60)
        self.crisp.timeout.connect(self.make_crisp)
        self.idle = QTimer(self, singleShot=True, interval=100)
        self.idle.timeout.connect(self.prefetch)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        if self.reflow:
            self.doc.layout(width=560, height=800, fontsize=self.fontsize)
        self.measure()
        QTimer.singleShot(0, lambda: self.goto(self.start_page))

    # ---- geometry ----
    def measure(self):
        self.sizes = [(p.rect.width, p.rect.height) for p in self.doc]
        self.cache.clear()
        self.layout_pages()

    def layout_pages(self):
        vpw = self.width() - self.verticalScrollBar().sizeHint().width() - 2 * self.frameWidth()
        maxw = max(w for w, _ in self.sizes)
        if self.fit:
            s = (vpw - 2 * PADX) / maxw
            if self.reflow:
                s = min(s, 1.6)  # keep book lines a readable length
        else:
            s = self.zoom
        self.s = min(8.0, max(0.1, s))
        self.ws = [int(w * self.s) for w, _ in self.sizes]
        self.hs = [int(h * self.s) for _, h in self.sizes]
        self.tops, y = [], MARGIN
        for h in self.hs:
            self.tops.append(y)
            y += h + GAP
        cw = max(vpw, max(self.ws) + 2 * PADX)
        self.xs = [(cw - w) // 2 for w in self.ws]
        self.canvas.resize(cw, y - GAP + MARGIN)
        self.canvas.update()

    def anchored(self, fn):
        """Run fn (which changes layout) and keep the same spot of the same page on screen."""
        n = self.current_page()
        frac = (self.verticalScrollBar().value() - self.tops[n]) / max(1, self.hs[n]) if self.tops else 0
        fn()
        self.verticalScrollBar().setValue(int(self.tops[n] + frac * self.hs[n]))
        self.crisp.start()

    def scale(self):
        return self.s

    def page_rect(self, i):
        return QRect(self.xs[i], self.tops[i], self.ws[i], self.hs[i])

    def visible(self, y0, y1):
        return max(0, bisect_right(self.tops, y0) - 1), bisect_right(self.tops, y1)

    def page_at(self, p):
        i = bisect_right(self.tops, p.y()) - 1
        return i if i >= 0 and self.page_rect(i).contains(p) else None

    def local(self, i, p):
        return QPoint(p.x() - self.xs[i], p.y() - self.tops[i])

    def current_page(self):
        mid = self.verticalScrollBar().value() + self.viewport().height() // 3
        return max(0, bisect_right(self.tops, mid) - 1)

    def goto(self, n):
        if 0 <= n < len(self.tops):
            self.verticalScrollBar().setValue(self.tops[n] - 4)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.sizes:
            self.anchored(self.layout_pages)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.set_zoom(1.1 ** (e.angleDelta().y() / 120))
            e.accept()
        else:
            super().wheelEvent(e)

    def keyPressEvent(self, e):
        k, bar = e.key(), self.verticalScrollBar()
        if k == Qt.Key_Space:
            step = int(self.viewport().height() * 0.9)
            bar.setValue(bar.value() + (-step if e.modifiers() & Qt.ShiftModifier else step))
        elif k in (Qt.Key_Left, Qt.Key_Right) and self.horizontalScrollBar().maximum() == 0:
            self.goto(self.current_page() + (1 if k == Qt.Key_Right else -1))
        elif k == Qt.Key_Escape and self.hit:
            self.hit = None
            self.canvas.update()
        else:
            super().keyPressEvent(e)

    # ---- rendering ----
    def pdf(self):
        if self.doc.is_pdf:
            return self.doc
        if self._pdf is None:
            self._pdf = fitz.open("pdf", self.doc.convert_to_pdf())
        return self._pdf

    def render(self, i):
        s, dpr = self.s, self.devicePixelRatioF()
        pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(s * dpr, s * dpr), alpha=False)
        if self.dark:
            pix.invert_irect(pix.irect)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        self.cache[i] = ((s, self.dark), pm)
        self.cache.move_to_end(i)
        while len(self.cache) > CACHE_PAGES:
            self.cache.popitem(last=False)
        return pm

    def pixmap(self, i):
        ent = self.cache.get(i)
        if ent and ent[0] == (self.s, self.dark):
            return ent[1]
        if ent:  # wrong zoom: show it stretched now, redraw sharp a moment later
            self.crisp.start()
            return ent[1]
        return self.render(i)

    def make_crisp(self):
        lo, hi = self.visible(*self.view_span())
        for i in range(lo, hi):
            ent = self.cache.get(i)
            if not ent or ent[0] != (self.s, self.dark):
                self.render(i)
        self.canvas.update()

    def view_span(self):
        y = self.verticalScrollBar().value()
        return y, y + self.viewport().height()

    def on_scroll(self):
        self.idle.start()
        if self.win.cur() is self:
            self.win.update_status()

    def prefetch(self):
        lo, hi = self.visible(*self.view_span())
        for i in (hi, lo - 1):
            if 0 <= i < len(self.hs):
                ent = self.cache.get(i)
                if not ent or ent[0] != (self.s, self.dark):
                    self.render(i)

    def refresh_page(self, n):
        self.cache.pop(n, None)
        self.canvas.update()

    # ---- view controls ----
    def set_zoom(self, factor):
        self.zoom = min(8.0, max(0.1, self.s * factor))
        self.fit = False
        self.anchored(self.layout_pages)
        self.win.update_status()

    def fit_width(self):
        self.fit = True
        self.anchored(self.layout_pages)
        self.win.update_status()

    def set_dark(self, on):
        self.dark = on
        self.cache.clear()
        self.canvas.update()

    def set_font(self, delta):
        if not self.reflow:
            return
        new = min(40, max(6, self.fontsize + delta))
        if new == self.fontsize:
            return
        mark = self.doc.make_bookmark(self.doc.location_from_page_number(self.current_page()))
        self.fontsize = new
        self.doc.layout(width=560, height=800, fontsize=new)
        n = self.doc.page_number_from_location(self.doc.find_bookmark(mark))
        self.measure()
        self.goto(n)
        self.win.update_status()

    def save_position(self):
        self.win.settings.setValue(pos_key(self.path), json.dumps([self.current_page(), self.fontsize]))

    # ---- search ----
    def find(self, text, step=1):
        if not text:
            return False
        if text != self.q:
            self.q, self.hp, self.hl = text, self.current_page(), None
        n = len(self.doc)
        for _ in range(n + 1):
            if self.hl is None:
                self.hl = self.doc[self.hp].search_for(text)
                self.hi = -1 if step > 0 else len(self.hl)
            j = self.hi + step
            if 0 <= j < len(self.hl):
                self.hi = j
                self.hit = (self.hp, self.hl)
                y = self.tops[self.hp] + int(self.hl[j].y0 * self.s)
                self.verticalScrollBar().setValue(y - self.viewport().height() // 3)
                self.canvas.update()
                return True
            self.hp, self.hl = (self.hp + step) % n, None
        return False

    # ---- annotation tools ----
    def set_tool(self, t):
        self.tool = t
        self.canvas.setCursor(CURSORS.get(t, Qt.CrossCursor))

    def pt(self, p):
        return fitz.Point(p.x() / self.s, p.y() / self.s)

    def pdf_only(self):
        if self.doc.is_pdf:
            return True
        self.win.say("Annotating needs a PDF. Use File > Convert to PDF first.")
        return False

    def record(self, pno, annot):
        if annot is None:
            self.win.say("Nothing to mark there.")
            return
        self.undo_stack.append((pno, annot.xref))
        self.dirty = True
        self.win.mark_dirty(self)
        self.refresh_page(pno)

    def undo(self):
        if not self.undo_stack:
            self.win.say("Nothing to undo.")
            return
        pno, xref = self.undo_stack.pop()
        page = self.doc[pno]
        a = page.load_annot(xref)
        if a:
            page.delete_annot(a)
        self.dirty = True
        self.win.mark_dirty(self)
        self.refresh_page(pno)

    def click(self, pno, p):
        if not self.pdf_only():
            return
        page, pt, color = self.doc[pno], self.pt(p), self.win.color()
        if self.tool == NOTE:
            text, ok = QInputDialog.getMultiLineText(self, "Note", "Note text:")
            if ok and text.strip():
                a = page.add_text_annot(pt, text)
                a.set_colors(stroke=color)
                a.update()
                self.record(pno, a)
        elif self.tool == SIGN:
            path = self.win.signature_path()
            if path:
                pm = fitz.Pixmap(path)
                w = 150
                h = w * pm.height / pm.width
                r = fitz.Rect(pt.x - w / 2, pt.y - h / 2, pt.x + w / 2, pt.y + h / 2)
                self.record(pno, page.add_stamp_annot(r, stamp=path))
        elif self.tool == ERASE:
            hit = [a for a in page.annots() if a.rect.contains(pt)]
            if hit:
                page.delete_annot(hit[-1])
                self.dirty = True
                self.win.mark_dirty(self)
                self.refresh_page(pno)

    def finish_ink(self, pno, pts):
        if not self.pdf_only() or len(pts) < 2:
            return
        a = self.doc[pno].add_ink_annot([[(self.pt(p).x, self.pt(p).y) for p in pts]])
        a.set_colors(stroke=self.win.color())
        a.set_border(width=2)
        a.update()
        self.record(pno, a)

    def finish_rect(self, pno, qr):
        s = self.s
        r = fitz.Rect(qr.left() / s, qr.top() / s, qr.right() / s, qr.bottom() / s)
        tiny = qr.width() < 4 or qr.height() < 4
        page, color = self.doc[pno], self.win.color()
        if self.tool == SELECT:
            if not tiny:
                text = page.get_text("text", clip=r).strip()
                QGuiApplication.clipboard().setText(text)
                self.win.say(f"Copied {len(text)} characters" if text else "No text there")
            return
        if not self.pdf_only():
            return
        if self.tool in (HIGHLIGHT, UNDERLINE, STRIKE):
            if tiny:
                return
            add = {HIGHLIGHT: page.add_highlight_annot, UNDERLINE: page.add_underline_annot,
                   STRIKE: page.add_strikeout_annot}[self.tool]
            a = add(clip=r)
            if a:
                a.set_colors(stroke=color)
                a.update()
            self.record(pno, a)
        elif self.tool == RECT:
            if tiny:
                return
            a = page.add_rect_annot(r)
            a.set_colors(stroke=color)
            a.set_border(width=1.5)
            a.update()
            self.record(pno, a)
        elif self.tool == TEXT:
            if tiny:
                r = fitz.Rect(r.x0, r.y0, r.x0 + 200, r.y0 + 40)
            text, ok = QInputDialog.getMultiLineText(self, "Text box", "Text:")
            if ok and text.strip():
                self.record(pno, page.add_freetext_annot(r, text, fontsize=12, text_color=color))


class SigPad(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(500, 180)
        self.strokes, self.cur = [], None

    def mousePressEvent(self, e):
        self.cur = [e.position().toPoint()]
        self.strokes.append(self.cur)

    def mouseMoveEvent(self, e):
        if self.cur:
            self.cur.append(e.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, e):
        self.cur = None

    def draw(self, qp, k=1):
        qp.setPen(QPen(QColor(10, 20, 80), 3 * k, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for s in self.strokes:
            qp.drawPolyline([QPointF(p.x() * k, p.y() * k) for p in s])

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), Qt.white)
        qp.setPen(QPen(QColor(200, 200, 200), 1))
        qp.drawLine(20, 140, 480, 140)
        self.draw(qp)

    def image(self):
        img = QImage(1000, 360, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        qp = QPainter(img)
        qp.setRenderHint(QPainter.Antialiasing)
        self.draw(qp, 2)
        qp.end()
        pts = [p for s in self.strokes for p in s]
        box = QRect(QPoint(min(p.x() for p in pts) * 2, min(p.y() for p in pts) * 2),
                    QPoint(max(p.x() for p in pts) * 2, max(p.y() for p in pts) * 2))
        return img.copy(box.adjusted(-8, -8, 8, 8))


class SigDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Draw your signature")
        self.pad = SigPad()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Sign with your mouse or pen. You only do this once."))
        lay.addWidget(self.pad)
        row = QHBoxLayout()
        for text, fn, name in (("Clear", self.clear, ""), ("Cancel", self.reject, ""), ("Save", self.save, "primary")):
            b = QPushButton(text)
            if name:
                b.setObjectName(name)
                b.setDefault(True)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)

    def clear(self):
        self.pad.strokes = []
        self.pad.update()

    def save(self):
        if self.pad.strokes:
            os.makedirs(os.path.dirname(SIG_PATH), exist_ok=True)
            self.pad.image().save(SIG_PATH)
            self.accept()


SHORTCUTS = [
    ("Open / Save / Save as", "Ctrl+O / Ctrl+S / Ctrl+Shift+S"),
    ("Undo last annotation", "Ctrl+Z"),
    ("Find, next, previous", "Ctrl+F, F3, Shift+F3"),
    ("Zoom in / out / fit width", "Ctrl+= / Ctrl+- / Ctrl+0  (or Ctrl+mouse wheel)"),
    ("Bigger / smaller book text", "Ctrl+Shift+= / Ctrl+Shift+-"),
    ("Night mode", "Ctrl+D"),
    ("Contents panel", "F9"),
    ("Go to page", "Ctrl+G"),
    ("Next / previous page (books)", "Right / Left arrow"),
    ("Scroll a screen", "Space / Shift+Space"),
    ("Tools", "V Move  T Copy text  H Highlight  U Underline  K Strike  N Note  X Text  D Draw  R Box  G Sign  E Erase"),
]


class Main(QMainWindow):
    def __init__(self, files):
        super().__init__()
        self.setWindowTitle("PDFKit")
        self.setWindowIcon(QIcon(resource("logo.png")))
        self.resize(1200, 860)
        self.settings = QSettings("PDFKit", "PDFKit")
        self.dark = self.settings.value("dark", "0") == "1"
        self.theme = theme.DARK if self.dark else theme.LIGHT
        self.tool, self.colors = HAND, {"mark": "Yellow", "pen": "Red"}
        self.icons = {}  # QAction -> icon name (rebuilt when the theme changes)
        self.swatches = {}

        self.tabs = QTabWidget(tabsClosable=True, movable=True, documentMode=True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_welcome())
        self.stack.addWidget(self.tabs)
        self.setCentralWidget(self.stack)
        self.setAcceptDrops(True)

        self.hint = QLabel()
        self.page_lbl = QLabel()
        self.statusBar().addWidget(self.hint, 1)
        self.statusBar().addPermanentWidget(self.page_lbl)
        self.toc = QTreeWidget(headerHidden=True)
        self.toc.itemClicked.connect(lambda it: self.cur() and self.cur().goto(it.data(0, Qt.UserRole)))
        self.dock = QDockWidget("Contents", self)
        self.dock.setWidget(self.toc)
        self.dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        self.dock.hide()

        self.menus()
        self.apply_theme()
        self.set_tool(HAND)
        for f in files:
            self.open(f)
        self.refresh_stack()

    # ---- welcome screen ----
    def build_welcome(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(QPixmap(resource("logo.png")).scaled(112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        title = QLabel("PDFKit")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("Read, mark up and sign PDFs, books and images.")
        sub.setObjectName("sub")
        sub.setAlignment(Qt.AlignCenter)
        btn = QPushButton("Open a file")
        btn.setObjectName("primary")
        btn.setDefault(True)
        btn.clicked.connect(self.open_dialog)
        drop = QLabel("or drop a file anywhere in this window  (Ctrl+O)")
        drop.setObjectName("muted")
        drop.setAlignment(Qt.AlignCenter)
        self.recent_lbl = QLabel("Recent")
        self.recent_lbl.setObjectName("muted")
        self.recent_list = QListWidget()
        self.recent_list.setFixedWidth(460)
        self.recent_list.setMaximumHeight(190)
        self.recent_list.itemActivated.connect(lambda it: self.open(it.data(Qt.UserRole)))
        self.recent_list.itemClicked.connect(lambda it: self.open(it.data(Qt.UserRole)))
        for x in (logo, title, sub):
            lay.addWidget(x)
        lay.addSpacing(10)
        lay.addWidget(btn, 0, Qt.AlignCenter)
        lay.addWidget(drop)
        lay.addSpacing(18)
        lay.addWidget(self.recent_lbl, 0, Qt.AlignCenter)
        lay.addWidget(self.recent_list, 0, Qt.AlignCenter)
        return w

    def refresh_stack(self):
        self.stack.setCurrentIndex(1 if self.tabs.count() else 0)
        self.fill_recent()
        if not self.tabs.count():
            self.setWindowTitle("PDFKit")
            self.page_lbl.setText("")

    def recent(self):
        return [p for p in json.loads(self.settings.value("recent", "[]")) if os.path.exists(p)]

    def add_recent(self, path):
        r = [p for p in self.recent() if p != path]
        self.settings.setValue("recent", json.dumps(([path] + r)[:8]))

    def fill_recent(self):
        self.recent_list.clear()
        for p in self.recent():
            it = self.recent_list.addItem(os.path.basename(p))
            item = self.recent_list.item(self.recent_list.count() - 1)
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
        has = self.recent_list.count() > 0
        self.recent_list.setFixedHeight(min(190, 34 * self.recent_list.count() + 12))
        self.recent_lbl.setVisible(has)
        self.recent_list.setVisible(has)

    # ---- theme ----
    def apply_theme(self):
        self.theme = theme.DARK if self.dark else theme.LIGHT
        QApplication.instance().setStyleSheet(theme.stylesheet(self.theme))
        for a, name in self.icons.items():
            a.setIcon(theme.icon(name, self.theme))
        for cname, a in self.swatches.items():
            a.setIcon(theme.swatch(COLORS[cname], self.theme))
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_dark(self.dark)
            self.tabs.widget(i).canvas.update()

    def toggle_dark(self):
        self.dark = self.dark_act.isChecked()
        self.apply_theme()

    # ---- helpers ----
    def cur(self):
        return self.tabs.currentWidget()

    def say(self, msg):
        self.statusBar().showMessage(msg, 5000)

    def kind(self):
        return "mark" if self.tool in (HIGHLIGHT, UNDERLINE, STRIKE) else "pen"

    def color(self):
        """Highlighters and pens remember separate colours (yellow ink on white is unreadable)."""
        return COLORS[self.colors[self.kind()]]

    def act(self, menu, text, fn, key=None, checkable=False, icon=None, tip=None):
        a = QAction(text, self)
        a.setCheckable(checkable)
        a.triggered.connect(lambda *_: fn())
        if key:
            a.setShortcut(QKeySequence(key))
        a.setToolTip(tip or (f"{text}  ({key})" if key else text))
        if icon:
            self.icons[a] = icon
        if menu is not None:
            menu.addAction(a)
        return a

    def menus(self):
        m = self.menuBar().addMenu("&File")
        open_a = self.act(m, "Open...", self.open_dialog, "Ctrl+O", icon="open", tip="Open a file  (Ctrl+O)")
        self.recent_menu = m.addMenu("Open recent")
        self.recent_menu.aboutToShow.connect(self.fill_recent_menu)
        save_a = self.act(m, "Save", self.save, "Ctrl+S", icon="save", tip="Save changes into this file  (Ctrl+S)")
        self.act(m, "Save as...", self.save_as_current, "Ctrl+Shift+S")
        self.act(m, "Convert to PDF (to annotate)...", self.convert)
        m.addSeparator()
        self.act(m, "Close tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W")
        self.act(m, "Quit", self.close, "Ctrl+Q")

        e = self.menuBar().addMenu("&Edit")
        undo_a = self.act(e, "Undo", lambda: self.cur() and self.cur().undo(), "Ctrl+Z", icon="undo",
                          tip="Undo the last annotation  (Ctrl+Z)")
        self.act(e, "Find", self.focus_find, "Ctrl+F")
        self.act(e, "Find next", lambda: self.do_find(1), "F3")
        self.act(e, "Find previous", lambda: self.do_find(-1), "Shift+F3")

        v = self.menuBar().addMenu("&View")
        out_a = self.act(v, "Zoom out", lambda: self.cur() and self.cur().set_zoom(1 / 1.25), "Ctrl+-", icon="zoomout")
        fit_a = self.act(v, "Fit width", lambda: self.cur() and self.cur().fit_width(), "Ctrl+0", icon="fit")
        in_a = self.act(v, "Zoom in", lambda: self.cur() and self.cur().set_zoom(1.25), "Ctrl+=", icon="zoomin")
        self.act(v, "Bigger text (books)", lambda: self.cur() and self.cur().set_font(1), "Ctrl+Shift+=")
        self.act(v, "Smaller text (books)", lambda: self.cur() and self.cur().set_font(-1), "Ctrl+Shift+-")
        self.dark_act = self.act(v, "Night mode", self.toggle_dark, "Ctrl+D", True, icon="night",
                                 tip="Night mode  (Ctrl+D)")
        self.dark_act.setChecked(self.dark)
        toc_a = self.act(v, "Contents", lambda: self.dock.setVisible(not self.dock.isVisible()), "F9",
                         icon="contents", tip="Show the table of contents  (F9)")
        self.act(v, "Go to page...", self.goto, "Ctrl+G")

        t = self.menuBar().addMenu("&Tools")
        grp = QActionGroup(self)
        tool_acts = []
        for tid, label, ic, key, hint in TOOLS:
            a = self.act(t, label, lambda tid=tid: self.set_tool(tid), key, True, icon=ic,
                         tip=f"{label}  ({key}) - {hint}")
            grp.addAction(a)
            tool_acts.append(a)
            if tid == HAND:
                a.setChecked(True)
        t.addSeparator()
        cm = t.addMenu("Colour")
        cgrp = QActionGroup(self)
        for cname in COLORS:
            a = self.act(cm, cname, lambda cname=cname: self.set_color(cname), checkable=True,
                         tip=f"{cname} (colour for the current tool)")
            cgrp.addAction(a)
            self.swatches[cname] = a
        self.act(t, "Draw new signature...", self.new_signature)
        self.act(t, "Import signature image...", self.import_signature)

        p = self.menuBar().addMenu("&Pages")
        for text, fn in (("Merge files...", self.merge), ("Split into single pages...", self.split),
                         ("Extract pages...", self.extract), ("Delete pages...", self.delete),
                         ("Rotate pages...", self.rotate), ("Reorder pages...", self.reorder),
                         ("Compress (save copy)...", self.compress)):
            self.act(p, text, fn)

        h = self.menuBar().addMenu("&Help")
        self.act(h, "Keyboard shortcuts", self.show_shortcuts, "F1")

        # top toolbar: files, view, search
        bar = QToolBar("Main", movable=False)
        bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(bar)
        for a in (open_a, save_a, undo_a):
            bar.addAction(a)
        bar.addSeparator()
        for a in (out_a, fit_a, in_a):
            bar.addAction(a)
        bar.addSeparator()
        for a in (self.dark_act, toc_a):
            bar.addAction(a)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)
        self.find_box = QLineEdit(placeholderText="Find in document  (Ctrl+F)")
        self.find_box.setClearButtonEnabled(True)
        self.find_box.setMinimumWidth(260)
        self.find_box.setAccessibleName("Find in document")
        self.find_box.returnPressed.connect(lambda: self.do_find(1))
        self.icons[self.find_box.addAction(QIcon(), QLineEdit.LeadingPosition)] = "search"
        bar.addWidget(self.find_box)

        # second row: tools and colours
        self.addToolBarBreak()
        tb = QToolBar("Tools", movable=False)
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(tb)
        for i, a in enumerate(tool_acts):
            tb.addAction(a)
            if i in (1, 4, 8):
                tb.addSeparator()
        tb.addSeparator()
        for cname, a in self.swatches.items():
            tb.addAction(a)
            tb.widgetForAction(a).setObjectName("swatch")
            tb.widgetForAction(a).setToolButtonStyle(Qt.ToolButtonIconOnly)

    def fill_recent_menu(self):
        self.recent_menu.clear()
        rec = self.recent()
        for p in rec:
            a = self.recent_menu.addAction(os.path.basename(p))
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, p=p: self.open(p))
        if not rec:
            self.recent_menu.addAction("(none yet)").setEnabled(False)

    def show_shortcuts(self):
        rows = "".join(f"<tr><td style='padding:3px 14px 3px 0'><b>{a}</b></td><td>{b}</td></tr>" for a, b in SHORTCUTS)
        QMessageBox.information(self, "Keyboard shortcuts", f"<table>{rows}</table>")

    # ---- tabs / files ----
    def open(self, path):
        path = os.path.abspath(path)
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).path == path:
                self.tabs.setCurrentIndex(i)
                return
        try:
            doc = fitz.open(path)
            while doc.needs_pass:
                pw, ok = QInputDialog.getText(self, "Password", f"{os.path.basename(path)} is locked:",
                                              QLineEdit.Password)
                if not ok:
                    return
                doc.authenticate(pw)
            v = DocView(path, doc, self)
        except Exception as e:
            QMessageBox.warning(self, "PDFKit", f"Can't open {os.path.basename(path)}\n\n{e}")
            return
        self.add_recent(path)
        self.tabs.setCurrentIndex(self.tabs.addTab(v, os.path.basename(path)))
        self.refresh_stack()
        v.setFocus()

    def open_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open", "", FILTER)
        for f in files:
            self.open(f)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.open(u.toLocalFile())

    def close_tab(self, i):
        v = self.tabs.widget(i)
        if v is None:
            return True
        if v.dirty:
            r = QMessageBox.question(self, "PDFKit", f"Save changes to {os.path.basename(v.path)}?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel or (r == QMessageBox.Save and not self.save(v)):
                return False
        v.save_position()
        self.tabs.removeTab(i)
        v.verticalScrollBar().valueChanged.disconnect()
        v.doc.close()
        v.deleteLater()
        self.refresh_stack()
        return True

    def closeEvent(self, e):
        self.settings.setValue("dark", "1" if self.dark else "0")
        while self.tabs.count():
            if not self.close_tab(0):
                e.ignore()
                return

    def tab_changed(self):
        v = self.cur()
        self.toc.clear()
        if v:
            for lvl, title, page in v.doc.get_toc(simple=True):
                it = QTreeWidgetItem([("    " * (lvl - 1)) + title])
                it.setData(0, Qt.UserRole, max(0, page - 1))
                self.toc.addTopLevelItem(it)
            self.setWindowTitle(f"{os.path.basename(v.path)} - PDFKit")
            self.update_status()

    def update_status(self):
        v = self.cur()
        if v:
            z = f"   |   text size {v.fontsize}" if v.reflow else ""
            self.page_lbl.setText(f"Page {v.current_page() + 1} of {len(v.doc)}   |   {v.s * 100:.0f}%{z}")

    def mark_dirty(self, v):
        self.tabs.setTabText(self.tabs.indexOf(v), os.path.basename(v.path) + (" *" if v.dirty else ""))

    def set_tool(self, t):
        self.tool = t
        self.hint.setText(next(x[4] for x in TOOLS if x[0] == t))
        self.swatches[self.colors[self.kind()]].setChecked(True)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tool(t)

    def set_color(self, name):
        self.colors[self.kind()] = name
        self.say(f"{name} {'highlighter' if self.kind() == 'mark' else 'pen'}")

    def focus_find(self):
        self.find_box.setFocus()
        self.find_box.selectAll()

    def do_find(self, step):
        v = self.cur()
        if v and self.find_box.text() and not v.find(self.find_box.text(), step):
            self.say("Not found")

    def goto(self):
        v = self.cur()
        if v:
            n, ok = QInputDialog.getInt(self, "Go to page", "Page:", v.current_page() + 1, 1, len(v.doc))
            if ok:
                v.goto(n - 1)

    # ---- save ----
    def save(self, v=None):
        v = v if isinstance(v, DocView) else self.cur()
        if not v:
            return False
        if v.doc.is_pdf and v.doc.can_save_incrementally():
            try:
                v.doc.saveIncr()
                v.dirty = False
                self.mark_dirty(v)
                self.say("Saved")
                return True
            except Exception:
                pass
        return self.save_as_current(v)

    def save_as_current(self, v=None):
        v = v if isinstance(v, DocView) else self.cur()
        if not v:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Save as", "", "PDF (*.pdf)")
        if not path:
            return False
        v.pdf().save(path, garbage=3, deflate=True)
        if v.doc.is_pdf:
            v.path, v.dirty = os.path.abspath(path), False
            self.tabs.setTabText(self.tabs.indexOf(v), os.path.basename(path))
        else:
            self.open(path)
        self.say(f"Saved {path}")
        return True

    def convert(self):
        v = self.cur()
        if v and not v.doc.is_pdf:
            self.save_as_current(v)
        elif v:
            self.say("Already a PDF")

    def new_out(self, doc, title="Save as"):
        path, _ = QFileDialog.getSaveFileName(self, title, "", "PDF (*.pdf)")
        if path:
            doc.save(path, garbage=3, deflate=True)
            self.say(f"Saved {path}")
            self.open(path)

    # ---- signature ----
    def signature_path(self):
        if not os.path.exists(SIG_PATH):
            self.new_signature()
        return SIG_PATH if os.path.exists(SIG_PATH) else None

    def new_signature(self):
        SigDialog(self).exec()

    def import_signature(self):
        f, _ = QFileDialog.getOpenFileName(self, "Signature image (PNG with transparent background is best)",
                                           "", "Images (*.png *.jpg *.jpeg)")
        if f:
            os.makedirs(os.path.dirname(SIG_PATH), exist_ok=True)
            QImage(f).save(SIG_PATH)

    # ---- page tools ----
    def need(self):
        if not self.cur():
            QMessageBox.information(self, "PDFKit", "Open a file first.")
        return self.cur()

    def ask_pages(self, v, title, default="1"):
        text, ok = QInputDialog.getText(
            self, title, f"Pages (1-{len(v.doc)}), e.g. 1-3, 5, 8-", text=default)
        if not ok:
            return None
        try:
            return parse_pages(text, len(v.doc))
        except Exception as e:
            QMessageBox.warning(self, "PDFKit", f"Bad page list: {e}")
            return None

    def build_from(self, v, pages):
        o = fitz.open()
        for i in pages:
            o.insert_pdf(v.pdf(), from_page=i, to_page=i)
        return o

    def merge(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Pick files to merge (in order)", "", FILTER)
        if len(files) < 2:
            return
        out = fitz.open()
        for f in files:
            with fitz.open(f) as d:
                out.insert_pdf(d if d.is_pdf else fitz.open("pdf", d.convert_to_pdf()))
        self.new_out(out, "Save merged PDF")

    def split(self):
        v = self.need()
        folder = v and QFileDialog.getExistingDirectory(self, "Save pages into folder")
        if not folder:
            return
        base = os.path.splitext(os.path.basename(v.path))[0]
        for i in range(len(v.doc)):
            self.build_from(v, [i]).save(f"{folder}/{base}_p{i + 1}.pdf")
        self.say(f"Wrote {len(v.doc)} files to {folder}")

    def extract(self):
        v = self.need()
        pages = v and self.ask_pages(v, "Extract pages")
        if pages:
            self.new_out(self.build_from(v, pages), "Save extracted pages")

    def delete(self):
        v = self.need()
        pages = v and self.ask_pages(v, "Delete pages")
        if pages:
            keep = [i for i in range(len(v.doc)) if i not in set(pages)]
            if not keep:
                QMessageBox.warning(self, "PDFKit", "That would delete every page.")
                return
            self.new_out(self.build_from(v, keep), "Save without those pages")

    def rotate(self):
        v = self.need()
        pages = v and self.ask_pages(v, "Rotate pages", f"1-{len(v.doc)}")
        if not pages:
            return
        deg, ok = QInputDialog.getItem(self, "Rotate", "Degrees clockwise:", ["90", "180", "270"], 0, False)
        if ok:
            o = fitz.open("pdf", v.pdf().tobytes())
            for i in pages:
                o[i].set_rotation((o[i].rotation + int(deg)) % 360)
            self.new_out(o, "Save rotated PDF")

    def reorder(self):
        v = self.need()
        if not v:
            return
        default = ",".join(str(i + 1) for i in range(len(v.doc)))
        pages = self.ask_pages(v, "New page order (any order, repeats allowed)", default)
        if pages:
            self.new_out(self.build_from(v, pages), "Save reordered PDF")

    def compress(self):
        v = self.need()
        if v:
            self.new_out(fitz.open("pdf", v.pdf().tobytes()), "Save compressed copy")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:  # own taskbar identity so our icon shows instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PDFKit.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource("logo.png")))
    w = Main([a for a in sys.argv[1:] if os.path.isfile(a)])
    w.show()
    sys.exit(app.exec())
