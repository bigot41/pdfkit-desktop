# Builds dist\PDFKit\PDFKit.exe (folder build: starts much faster than --onefile).
pyinstaller --noconfirm --onedir --windowed --name PDFKit --icon logo.ico --add-data "logo.png;." `
  --exclude-module numpy --exclude-module PIL --exclude-module tkinter `
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
  --exclude-module PySide6.QtPdf --exclude-module PySide6.QtSvg --exclude-module PySide6.QtOpenGL pdfkit.py
# Software OpenGL fallback is not used by this app and is 20 MB.
Remove-Item dist\PDFKit\_internal\PySide6\opengl32sw.dll -ErrorAction SilentlyContinue
