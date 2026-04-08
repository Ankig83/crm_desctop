from __future__ import annotations

from pathlib import Path


def export_quote_pdf(path: Path, text: str) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("Для экспорта PDF установите reportlab (pip install reportlab).") from e

    font_name = "Helvetica"
    # reportlab core fonts don't support Cyrillic; try common Windows fonts.
    for font_path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/tahoma.ttf"):
        p = Path(font_path)
        if p.is_file():
            pdfmetrics.registerFont(TTFont("CRMFont", str(p)))
            font_name = "CRMFont"
            break

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=A4)
    width, height = A4
    margin = 36
    y = height - margin
    c.setFont(font_name, 10)

    for raw in text.splitlines() or [""]:
        line = raw.replace("\t", "    ")
        if y < margin:
            c.showPage()
            c.setFont(font_name, 10)
            y = height - margin
        c.drawString(margin, y, line[:200])
        y -= 14
    c.save()
