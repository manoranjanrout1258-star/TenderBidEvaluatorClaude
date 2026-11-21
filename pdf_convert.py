"""Convert submitted documents to PDF.

Order of preference:
  DOCX/DOC/XLSX/XLS/XLSM  ->  LibreOffice (best fidelity, Hindi OK)  ->  ReportLab text fallback
  JPG/PNG/TIFF/BMP        ->  Pillow
  PDF                     ->  used as is (never passes through this module)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape

from .extract import docx_blocks
from .office import convert_batch, find_soffice
from .utils import IMG_EXTS, unique_path

OFFICE_EXTS = {".docx", ".doc", ".xlsx", ".xls", ".xlsm"}

_FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
_FONT_NAME: str | None = None


def _fallback_font() -> str:
    global _FONT_NAME
    if _FONT_NAME is None:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        _FONT_NAME = "Helvetica"
        for fp in _FONT_PATHS:
            if Path(fp).exists():
                try:
                    pdfmetrics.registerFont(TTFont("TMFallback", fp))
                    _FONT_NAME = "TMFallback"
                    break
                except Exception:
                    continue
    return _FONT_NAME


def image_to_pdf(src: Path, dst: Path) -> None:
    from PIL import Image

    with Image.open(src) as im:
        im.load()
        rgb = im.convert("RGB")
        rgb.save(dst, "PDF", resolution=150.0)


def docx_to_pdf_fallback(src: Path, dst: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = _fallback_font()
    body = ParagraphStyle("b", fontName=font, fontSize=10, leading=14)
    small = ParagraphStyle("s", fontName=font, fontSize=8.5, leading=11)
    story = []
    for kind, val in docx_blocks(src):
        if kind == "p":
            story += [Paragraph(escape(str(val)), body), Spacer(1, 4)]
        else:
            rows = val  # type: ignore[assignment]
            width = max(len(r) for r in rows)
            data = [[Paragraph(escape(c), small) for c in (r + [""] * (width - len(r)))] for r in rows]
            t = Table(data)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 6)]
    if not story:
        story = [Paragraph("(empty document)", body)]
    SimpleDocTemplate(str(dst), pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40).build(story)


def xlsx_to_pdf_fallback(src: Path, dst: Path, max_rows: int = 300) -> None:
    from openpyxl import load_workbook
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = _fallback_font()
    small = ParagraphStyle("s", fontName=font, fontSize=7.5, leading=9.5)
    head = ParagraphStyle("h", fontName=font, fontSize=11, leading=14)
    wb = load_workbook(str(src), read_only=True, data_only=True)
    story = []
    try:
        for ws in wb.worksheets[:20]:
            story.append(Paragraph(escape(ws.title), head))
            story.append(Spacer(1, 4))
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= max_rows:
                    break
                vals = ["" if v is None else str(v)[:200] for v in row][:14]
                if any(vals):
                    rows.append(vals)
            if rows:
                width = max(len(r) for r in rows)
                data = [[Paragraph(escape(c), small) for c in (r + [""] * (width - len(r)))] for r in rows]
                t = Table(data, repeatRows=1)
                t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(t)
            story.append(PageBreak())
    finally:
        wb.close()
    if not story:
        story = [Paragraph("(empty workbook)", head)]
    SimpleDocTemplate(str(dst), pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=30,
                      bottomMargin=30).build(story)


def convert_to_pdf(
    files: list[Path],
    work_dir: Path,
    progress: Callable[[int, int], None] | None = None,
) -> dict[Path, tuple[Path | None, str]]:
    """Return {source: (pdf_path | None, method)}. Never raises for a single bad file."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out: dict[Path, tuple[Path | None, str]] = {}
    total = len(files)
    done = 0

    office = [f for f in files if f.suffix.lower() in OFFICE_EXTS]
    images = [f for f in files if f.suffix.lower() in IMG_EXTS]

    for f in images:
        dst = unique_path(work_dir / f"{f.stem}.pdf")
        try:
            image_to_pdf(f, dst)
            out[f] = (dst, "pillow")
        except Exception:
            out[f] = (None, "failed")
        done += 1
        if progress:
            progress(done, total)

    if office:
        def _p(d, t):
            if progress:
                progress(done + d, total)

        lo = convert_batch(office, work_dir, "pdf", progress=_p) if find_soffice() else {}
        for f in office:
            if f in lo:
                out[f] = (lo[f], "libreoffice")
                continue
            dst = unique_path(work_dir / f"{f.stem}.pdf")
            try:
                ext = f.suffix.lower()
                if ext == ".docx":
                    docx_to_pdf_fallback(f, dst)
                elif ext in (".xlsx", ".xlsm"):
                    xlsx_to_pdf_fallback(f, dst)
                else:
                    raise RuntimeError("legacy format needs LibreOffice")
                out[f] = (dst, "reportlab-fallback")
            except Exception:
                out[f] = (None, "failed")
        done += len(office)
        if progress:
            progress(done, total)
    return out
