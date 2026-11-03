# Builds dist\PDFKit\PDFKit.exe (folder build: starts much faster than --onefile) and trims it.
$ErrorActionPreference = "Stop"
$exclude = "numpy","PIL","tkinter","PySide6.QtNetwork","PySide6.QtQml","PySide6.QtQuick","PySide6.QtPdf",
           "PySide6.QtSvg","PySide6.QtOpenGL","ssl","_ssl","sqlite3","unittest","pydoc","doctest","xmlrpc",
           "http","ftplib","smtplib","asyncio","multiprocessing","curses","lib2to3","distutils"
$exArgs = $exclude | ForEach-Object { "--exclude-module"; $_ }
pyinstaller --noconfirm --onedir --windowed --name PDFKit --icon logo.ico --add-data "logo.png;." @exArgs pdfkit.py

# Parts of Qt this app never loads.
$qt = "dist\PDFKit\_internal\PySide6"
$trim = "opengl32sw.dll","Qt6Network.dll","Qt6Svg.dll","translations","plugins\iconengines","plugins\imageformats",
        "plugins\generic","plugins\platforms\qdirect2d.dll","plugins\platforms\qminimal.dll",
        "plugins\platforms\qoffscreen.dll"
foreach ($t in $trim) { Remove-Item (Join-Path $qt $t) -Recurse -Force -ErrorAction SilentlyContinue }
# Pulled in by PyInstaller hooks but never used when reading documents.
foreach ($t in "lxml","fontTools","libcrypto-3.dll") {
    Remove-Item "dist\PDFKit\_internal\$t" -Recurse -Force -ErrorAction SilentlyContinue
}
"{0:N0} MB" -f ((Get-ChildItem dist\PDFKit -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
