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


def test_parse_pages():
    assert pdfkit.parse_pages("1-2, 5, 4-", 5) == [0, 1, 4, 3, 4]
    with pytest.raises(ValueError):
        pdfkit.parse_pages("9", 5)


def test_highlight_undo_save(app, tmp_path):
    f = str(tmp_path / "a.pdf")
    make_pdf(f)
    w = pdfkit.Main([f])
    v = w.cur()
    w.set_tool(pdfkit.HIGHLIGHT)
    s = v.s
    v.finish_rect(0, QRect(int(60 * s), int(75 * s), int(250 * s), int(40 * s)))
    assert len(list(v.doc[0].annots())) == 1 and v.dirty
    assert w.save(v) and not v.dirty
    assert len(list(pymupdf.open(f)[0].annots())) == 1
    v.undo()
    assert len(list(v.doc[0].annots())) == 0


def test_large_book_only_renders_visible_pages(app, tmp_path):
    """Regression: opening a long document used to render every page at once and freeze."""
    f = str(tmp_path / "big.pdf")
    make_pdf(f, pages=400)
    w = pdfkit.Main([f])
    v = w.cur()
    app.processEvents()
    assert len(v.cache) <= pdfkit.CACHE_PAGES


def test_reflow_font_size_changes_page_count(app, tmp_path):
    f = tmp_path / "book.txt"
    f.write_text("lorem ipsum dolor sit amet\n" * 600)
    w = pdfkit.Main([str(f)])
    v = w.cur()
    before = len(v.doc)
    v.set_font(4)
    assert len(v.doc) > before


def test_zoom_keeps_page(app, tmp_path):
    f = str(tmp_path / "z.pdf")
    make_pdf(f, pages=20)
    w = pdfkit.Main([f])
    w.show()  # scrolling needs a laid-out window
    app.processEvents()
    v = w.cur()
    v.goto(10)
    app.processEvents()
    assert v.current_page() == 10
    v.set_zoom(1.5)
    app.processEvents()
    assert v.current_page() == 10


def test_pdf_for_editing_converts_books(tmp_path):
    f = tmp_path / "book.txt"
    f.write_text("lorem ipsum dolor sit amet\n" * 300)
    out = pdfkit.pdf_for_editing(str(f))
    assert out.endswith("book (PDF).pdf") and len(pymupdf.open(out)) > 1
    make_pdf(str(tmp_path / "a.pdf"))
    assert pdfkit.pdf_for_editing(str(tmp_path / "a.pdf")) == str(tmp_path / "a.pdf")
