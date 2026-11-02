# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Setup

```bash
pip install -r requirements-dev.txt
pytest
python pdfkit.py
```

## Guidelines

- Keep it light and fast. Avoid new dependencies unless they earn their size, and do not add per-page widgets: pages are painted on one canvas.
- Run `pytest` before opening a pull request. Add a test for any bug you fix.
- Keep pull requests small and focused, and describe what you changed and why.
- By contributing you agree that your work is released under the AGPL-3.0, like the rest of the project.

## Ideas that would help

- In-place text editing of existing PDF text.
- Night mode that keeps annotation colours.
- Fill-in form fields and digital (certificate) signatures.
- macOS and Linux testing.
