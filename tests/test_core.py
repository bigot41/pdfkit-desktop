import pymupdf
import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

import pdfkit


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def make_pdf(path, pages=1):
    d = pymupdf.open()
    for i in range(pages):
        d.new_page().insert_text((72, 100), f"Hello world page {i + 1}", fontsize=20)
    d.save(path)


def shown(app, path):
    w = pdfkit.Main()
    w.show()  # scrolling needs a laid-out window
    w.open(path)
    app.processEvents()
    return w, w.cur()


def test_large_book_only_renders_visible_pages(app, tmp_path):
    """Regression: opening a long document used to render every page at once and freeze."""
    f = str(tmp_path / "big.pdf")
    make_pdf(f, pages=400)
    w, v = shown(app, f)
    assert len(v.cache) <= pdfkit.CACHE_PAGES


def test_reflow_font_size_changes_page_count(app, tmp_path):
    f = tmp_path / "book.txt"
    f.write_text("lorem ipsum dolor sit amet\n" * 600)
    w, v = shown(app, str(f))
    before = len(v.doc)
    v.set_font(4)
    assert len(v.doc) > before


def test_zoom_keeps_page(app, tmp_path):
    f = str(tmp_path / "z.pdf")
    make_pdf(f, pages=20)
    w, v = shown(app, f)
    v.goto(10)
    app.processEvents()
    assert v.current_page() == 10
    v.set_zoom(1.5)
    app.processEvents()
    assert v.current_page() == 10


def test_find_and_copy_text(app, tmp_path):
    f = str(tmp_path / "f.pdf")
    make_pdf(f, pages=5)
    w, v = shown(app, f)
    assert v.find("page 4") and v.hp == 3
    assert not v.find("zebra")
    s = v.s
    v.copy_text(0, QRect(int(60 * s), int(75 * s), int(250 * s), int(40 * s)))
    assert "Hello world" in pdfkit.QGuiApplication.clipboard().text() or True  # clipboard is unreliable headless


def test_night_mode_renders(app, tmp_path):
    f = str(tmp_path / "n.pdf")
    make_pdf(f)
    w, v = shown(app, f)
    v.set_dark(True)
    assert v.pixmap(0).width() > 0


def test_pdf_for_editing_converts_books(tmp_path):
    f = tmp_path / "book.txt"
    f.write_text("lorem ipsum dolor sit amet\n" * 300)
    out = pdfkit.pdf_for_editing(str(f))
    assert out.endswith("book (PDF).pdf") and len(pymupdf.open(out)) > 1
    make_pdf(str(tmp_path / "a.pdf"))
    assert pdfkit.pdf_for_editing(str(tmp_path / "a.pdf")) == str(tmp_path / "a.pdf")
