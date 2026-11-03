"""PDFKit: a fast, light reader for PDFs, e-books and images.

Editing is handed to PdfCraft (Ctrl+E), which converts any format to PDF first.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from bisect import bisect_right
from collections import OrderedDict

import pymupdf as fitz
from PySide6.QtCore import QRect, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QGuiApplication, QIcon, QImage,
                           QKeySequence, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import theme

GAP, MARGIN, PADX = 10, 8, 16  # between pages / above first and below last / left-right
CACHE_PAGES = 16
EXTS = "pdf epub mobi fb2 xps oxps cbz svg txt jpg jpeg png bmp gif tif tiff webp"
FILTER = "Documents (%s);;All files (*)" % " ".join("*." + e for e in EXTS.split())
MOVE, COPY = range(2)
HINTS = {MOVE: "Drag to move around. In books, Left and Right arrows turn pages.",
         COPY: "Drag over text to copy it."}
SHORTCUTS = [
    ("Open", "Ctrl+O"),
    ("Edit this file in PdfCraft (any format)", "Ctrl+E"),
    ("Find, next, previous", "Ctrl+F, F3, Shift+F3"),
    ("Zoom in / out / fit width", "Ctrl+= / Ctrl+- / Ctrl+0  (or Ctrl+mouse wheel)"),
    ("Bigger / smaller book text", "Ctrl+Shift+= / Ctrl+Shift+-"),
    ("Night mode", "Ctrl+D"),
    ("Contents panel", "F9"),
    ("Go to page", "Ctrl+G"),
    ("Next / previous page (books)", "Right / Left arrow"),
    ("Scroll a screen", "Space / Shift+Space"),
    ("Move tool / Copy text tool", "V / T"),
]


def resource(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), name)


def pos_key(path):
    return "pos/" + hashlib.md5(os.path.abspath(path).lower().encode()).hexdigest()


def pdfcraft_path():
    """PdfCraft (a separate PDF editor) if it is installed where we expect it, else None."""
    for p in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "PdfCraft", "pdfcraft.exe"),
              shutil.which("pdfcraft")):
        if p and os.path.exists(p):
            return p
    return None


def pdf_for_editing(path):
    """A PDF copy of any supported file, saved next to the original and reused if it exists."""
    if path.lower().endswith(".pdf"):
        return path
    out = os.path.splitext(path)[0] + " (PDF).pdf"
    if not os.path.exists(out):
        with fitz.open(path) as d:
            if d.is_reflowable:
                d.layout(width=560, height=800, fontsize=12)
            fitz.open("pdf", d.convert_to_pdf()).save(out, garbage=3, deflate=True)
    return out


def open_in_pdfcraft(path):
    """Convert if needed, then hand the PDF to PdfCraft. Returns an error message or None."""
    exe = pdfcraft_path()
    if not exe:
        return "PdfCraft isn't installed. Put it in %LOCALAPPDATA%\\Programs\\PdfCraft (github.com/storytold/pdfcraft)."
    try:
        subprocess.Popen([exe, pdf_for_editing(path)])
    except Exception as e:
        return f"Couldn't open it in PdfCraft: {e}"
    return None


class Canvas(QWidget):
    """One widget paints every visible page. No per-page widgets, so zoom and scroll stay cheap."""

    def __init__(self, view):
        super().__init__()
        self.v = view
        self.drag = None  # [page, QPoint, QPoint] in canvas coordinates
        self.pan = None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        v, p = self.v, e.position().toPoint()
        v.setFocus()
        if v.tool == MOVE:
            self.pan = (e.globalPosition().toPoint(), v.horizontalScrollBar().value(),
                        v.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor)
        else:
            i = v.page_at(p)
            if i is not None:
                self.drag = [i, p, p]

    def mouseMoveEvent(self, e):
        v = self.v
        if self.pan:
            g0, hx, vy = self.pan
            d = e.globalPosition().toPoint() - g0
            v.horizontalScrollBar().setValue(hx - d.x())
            v.verticalScrollBar().setValue(vy - d.y())
        elif self.drag:
            self.drag[2] = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        v = self.v
        if self.pan:
            self.pan = None
            self.setCursor(v.tool_cursor())
        elif self.drag:
            i, a, b = self.drag
            self.drag = None
            self.update()
            v.copy_text(i, QRect(a - v.origin(i), b - v.origin(i)).normalized())

    def paintEvent(self, e):
        v, t = self.v, self.v.win.theme
        qp = QPainter(self)
        qp.fillRect(e.rect(), QColor(t["canvas"]))
        lo, hi = v.visible(e.rect().top(), e.rect().bottom())
        paper = QColor(theme.DARK["page_bg"]) if v.dark else QColor("white")
        for i in range(lo, hi):
            r = v.page_rect(i)
            if not r.intersects(e.rect()):
                continue
            qp.fillRect(r.adjusted(-1, -1, 1, 1), QColor(t["border"]))
            qp.fillRect(r, paper)
            qp.drawPixmap(r, v.pixmap(i))
            if v.hit and v.hit[0] == i:
                c = QColor(t["accent"])
                c.setAlpha(90)
                qp.setBrush(c)
                qp.setPen(Qt.NoPen)
                for h in v.hit[1]:
                    qp.drawRect(QRectF(r.x() + h.x0 * v.s, r.y() + h.y0 * v.s, h.width * v.s, h.height * v.s))
        if self.drag:
            c = QColor(t["accent"])
            qp.setPen(QPen(c, 1))
            c.setAlpha(50)
            qp.setBrush(c)
            qp.drawRect(QRect(self.drag[1], self.drag[2]).normalized())


class DocView(QScrollArea):
    def __init__(self, path, doc, win):
        super().__init__()
        self.path, self.doc, self.win = path, doc, win
        self.reflow = doc.is_reflowable
        saved = json.loads(win.settings.value(pos_key(path), "[0, 12]"))
        self.start_page, self.fontsize = saved[0], saved[1]
        self.dark, self.tool = win.dark, win.tool
        self.q, self.hp, self.hi, self.hl, self.hit = None, 0, 0, None, None
        self.cache = OrderedDict()  # page -> ((scale, dark), QPixmap)
        self.fit, self.zoom, self.s = True, 1.0, 1.0
        self.sizes, self.tops, self.hs, self.ws, self.xs = [], [], [], [], []
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # constant width: no resize feedback loop
        self.setFocusPolicy(Qt.StrongFocus)
        self.verticalScrollBar().setSingleStep(60)
        self.canvas = Canvas(self)
        self.canvas.setCursor(self.tool_cursor())
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

    def tool_cursor(self):
        return Qt.OpenHandCursor if self.tool == MOVE else Qt.IBeamCursor

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

    def page_rect(self, i):
        return QRect(self.xs[i], self.tops[i], self.ws[i], self.hs[i])

    def origin(self, i):
        return self.page_rect(i).topLeft()

    def visible(self, y0, y1):
        return max(0, bisect_right(self.tops, y0) - 1), bisect_right(self.tops, y1)

    def page_at(self, p):
        i = bisect_right(self.tops, p.y()) - 1
        return i if i >= 0 and self.page_rect(i).contains(p) else None

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
    def render(self, i):
        s, dpr = self.s, self.devicePixelRatioF()
        pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(s * dpr, s * dpr), alpha=False)
        if self.dark:
            pix.tint_with(theme.DARK["page_ink"], theme.DARK["page_bg"])
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

    def set_tool(self, t):
        self.tool = t
        self.canvas.setCursor(self.tool_cursor())

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

    # ---- text ----
    def copy_text(self, pno, qr):
        if qr.width() < 4 or qr.height() < 4:
            return
        s = self.s
        r = fitz.Rect(qr.left() / s, qr.top() / s, qr.right() / s, qr.bottom() / s)
        text = self.doc[pno].get_text("text", clip=r).strip()
        if text:
            QGuiApplication.clipboard().setText(text)
        self.win.say(f"Copied {len(text)} characters" if text else "No text there")

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


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFKit")
        self.setWindowIcon(QIcon(resource("logo.png")))
        self.resize(1200, 860)
        self.settings = QSettings("PDFKit", os.environ.get("PDFKIT_PROFILE", "PDFKit"))
        self.dark = self.settings.value("dark", "0") == "1"
        self.theme = theme.DARK if self.dark else theme.LIGHT
        self.tool = MOVE
        self.icons = {}  # QAction -> icon name (rebuilt when the theme changes)

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
        self.set_tool(MOVE)
        self.refresh_stack()

    # ---- welcome screen ----
    def build_welcome(self):
        w = QWidget()
        outer = QHBoxLayout(w)
        outer.setAlignment(Qt.AlignCenter)
        left = QVBoxLayout()
        left.setSpacing(10)
        title = QLabel("PDFKit")
        title.setObjectName("title")
        sub = QLabel("A fast, light reader for PDFs, e-books and images.")
        sub.setObjectName("sub")
        btn = QPushButton("Open a file")
        btn.setObjectName("primary")
        btn.setDefault(True)
        btn.clicked.connect(self.open_dialog)
        hint = QLabel("Or drop a file here. Ctrl+O also works.")
        hint.setObjectName("muted")
        for x in (title, sub):
            left.addWidget(x)
        left.addSpacing(8)
        left.addWidget(btn, 0, Qt.AlignLeft)
        left.addWidget(hint)
        left.addStretch(1)
        right = QVBoxLayout()
        self.recent_lbl = QLabel("Recent files")
        self.recent_lbl.setObjectName("muted")
        self.recent_list = QListWidget()
        self.recent_list.setFixedWidth(380)
        self.recent_list.itemActivated.connect(lambda it: self.open(it.data(Qt.UserRole)))
        self.recent_list.itemClicked.connect(lambda it: self.open(it.data(Qt.UserRole)))
        right.addWidget(self.recent_lbl)
        right.addWidget(self.recent_list)
        right.addStretch(1)
        box = QWidget()
        row = QHBoxLayout(box)
        row.setSpacing(64)
        row.addLayout(left)
        row.addLayout(right)
        box.setFixedHeight(300)
        outer.addWidget(box, 0, Qt.AlignCenter)
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
            self.recent_list.addItem(os.path.basename(p))
            item = self.recent_list.item(self.recent_list.count() - 1)
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
        n = self.recent_list.count()
        self.recent_list.setFixedHeight(min(220, 34 * n + 12))
        self.recent_lbl.setVisible(n > 0)
        self.recent_list.setVisible(n > 0)

    # ---- theme ----
    def apply_theme(self):
        self.theme = theme.DARK if self.dark else theme.LIGHT
        QApplication.instance().setStyleSheet(theme.stylesheet(self.theme))
        for a, name in self.icons.items():
            a.setIcon(theme.icon(name, self.theme))
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_dark(self.dark)

    def toggle_dark(self):
        self.dark = self.dark_act.isChecked()
        self.apply_theme()

    # ---- helpers ----
    def cur(self):
        return self.tabs.currentWidget()

    def say(self, msg):
        self.statusBar().showMessage(msg, 5000)

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
        edit_a = self.act(m, "Edit in PdfCraft", self.edit_in_pdfcraft, "Ctrl+E", icon="edit",
                          tip="Edit this file in PdfCraft. Books and images are converted to PDF first  (Ctrl+E)")
        m.addSeparator()
        self.act(m, "Close tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W")
        self.act(m, "Quit", self.close, "Ctrl+Q")

        e = self.menuBar().addMenu("&Edit")
        self.act(e, "Find", self.focus_find, "Ctrl+F")
        self.act(e, "Find next", lambda: self.do_find(1), "F3")
        self.act(e, "Find previous", lambda: self.do_find(-1), "Shift+F3")
        grp = QActionGroup(self)
        tool_acts = []
        for tid, label, ic, key in ((MOVE, "Move", "hand", "V"), (COPY, "Copy text", "select", "T")):
            a = self.act(e, label, lambda tid=tid: self.set_tool(tid), key, True, icon=ic,
                         tip=f"{label}  ({key}): {HINTS[tid]}")
            grp.addAction(a)
            tool_acts.append(a)
        tool_acts[0].setChecked(True)

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

        h = self.menuBar().addMenu("&Help")
        self.act(h, "Keyboard shortcuts", self.show_shortcuts, "F1")

        bar = QToolBar("Main", movable=False)
        bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(bar)
        bar.addAction(open_a)
        bar.addSeparator()
        for a in (out_a, fit_a, in_a):
            bar.addAction(a)
        bar.addSeparator()
        for a in tool_acts:
            bar.addAction(a)
        bar.addSeparator()
        for a in (self.dark_act, toc_a):
            bar.addAction(a)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)
        self.find_box = QLineEdit(placeholderText="Find in document  (Ctrl+F)")
        self.find_box.setClearButtonEnabled(True)
        self.find_box.setMinimumWidth(240)
        self.find_box.setAccessibleName("Find in document")
        self.find_box.returnPressed.connect(lambda: self.do_find(1))
        self.icons[self.find_box.addAction(QIcon(), QLineEdit.LeadingPosition)] = "search"
        bar.addWidget(self.find_box)
        bar.addSeparator()
        bar.addAction(edit_a)

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
            return
        v.save_position()
        self.tabs.removeTab(i)
        v.verticalScrollBar().valueChanged.disconnect()
        v.doc.close()
        v.deleteLater()
        self.refresh_stack()

    def closeEvent(self, e):
        self.settings.setValue("dark", "1" if self.dark else "0")
        while self.tabs.count():
            self.close_tab(0)

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

    def set_tool(self, t):
        self.tool = t
        self.hint.setText(HINTS[t])
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tool(t)

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

    def edit_in_pdfcraft(self):
        v = self.cur()
        if not v:
            return
        self.say("Opening in PdfCraft...")
        err = open_in_pdfcraft(v.path)
        if err:
            QMessageBox.information(self, "PDFKit", err)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--pdfcraft":  # used by the Explorer right-click entry
        err = open_in_pdfcraft(os.path.abspath(args[1]))
        if err and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, err, "PDFKit", 0x40)
        sys.exit(1 if err else 0)
    if sys.platform == "win32":
        try:  # own taskbar identity so our icon shows instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PDFKit.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource("logo.png")))
    w = Main()
    w.show()
    # open files after the window is up, so the app feels instant even for huge books
    for f in args:
        if os.path.isfile(f):
            QTimer.singleShot(0, lambda f=f: w.open(f))
    sys.exit(app.exec())
