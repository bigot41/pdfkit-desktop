# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Setup

```bash
pip install -r requirements-dev.txt
pytest
python pdfkit.py
```

## Guidelines

- Keep it light and fast. Avoid new dependencies unless they earn their size, and do not add per-page widgets: pages are painted on one canvas. Editing belongs in PdfCraft, not here.
- Run `pytest` before opening a pull request. Add a test for any bug you fix.
- Keep pull requests small and focused, and describe what you changed and why.
- By contributing you agree that your work is released under the AGPL-3.0, like the rest of the project.

## Ideas that would help

- Faster page counting for very long EPUBs.
- Text selection that follows the lines of text.
- macOS and Linux testing.
