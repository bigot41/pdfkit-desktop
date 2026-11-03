# PDFKit

A fast, light desktop reader for PDFs, e-books and images. Windows-first, built with Python, [PySide6](https://doc.qt.io/qtforpython-6/) and [PyMuPDF](https://pymupdf.readthedocs.io/).

PDFKit only reads. When you want to edit, `Ctrl+E` hands the file to [PdfCraft](https://github.com/storytold/pdfcraft), a full PDF editor. EPUBs and other formats are converted to PDF first, so editing works on any file PDFKit can open.

![PDFKit in light mode](docs/screenshot-light.png)

## Features

- **Reads** PDF, EPUB, MOBI, FB2, XPS, CBZ, SVG, TXT and common image formats, in tabs.
- **Fast.** One canvas draws only the pages on screen. Zoom redraws in a few milliseconds, and a 689-page EPUB opens and scrolls without lag. The window is up in about half a second.
- **Books:** adjustable text size, contents panel (`F9`), arrow keys turn pages, and it remembers your page and text size per file.
- **Search** with highlighted hits, **copy text** by dragging, and a night mode that tints pages to soft dark colours instead of pure black.
- **Edit in PdfCraft** for any format (`Ctrl+E`).
- Keyboard friendly: every action is in the menus with a shortcut (`F1` lists them) and has a tooltip.

![PDFKit in night mode](docs/screenshot-dark.png)

## Run from source

```bash
pip install -r requirements.txt
python pdfkit.py [file ...]
```

Needs Python 3.10 or newer.

## Build a Windows app

```powershell
pip install -r requirements-dev.txt
./build.ps1          # produces dist\PDFKit\PDFKit.exe
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Known limitations

- It reads and copies text only. Annotating, signing and page tools were removed to keep the app small. Use PdfCraft for that.
- Edit in PdfCraft needs PdfCraft in `%LOCALAPPDATA%\Programs\PdfCraft` (or on your PATH).
- Only tested on Windows 11. It has not been tested with a screen reader.

## Contributing

Pull requests and issues are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[AGPL-3.0](LICENSE). PDFKit uses PyMuPDF, which is AGPL-3.0, so PDFKit is released under the same terms.
