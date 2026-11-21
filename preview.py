"""Preview helpers: HTML matrix, PDF page images, DOCX -> page images."""
from __future__ import annotations

import io
import tempfile
from html import escape
from pathlib import Path

from .matching import MatchResult
from .models import MANDATORY, Requirement
from .office import convert_batch, find_soffice


def matrix_df(reqs: list[Requirement], result: MatchResult):
    """Plain table version of the matrix (fallback / copy-paste friendly)."""
    import pandas as pd

    rows = []
    for i, r in enumerate(reqs, 1):
        row = {"S.No.": i, "Wanting document": r.name, "Type": r.mandatory}
        for b in result.bidders:
            row[b] = result.status(r.rid, b)
        rows.append(row)
    return pd.DataFrame(rows)


def matrix_html(reqs: list[Requirement], result: MatchResult, lang: str = "en", max_height: int = 560) -> str:
    sr, doc, typ = ("क्र.सं.", "वांछित दस्तावेज़", "प्रकार") if lang == "hi" else ("S.No.", "Wanting document", "Type")
    mand, opt = ("अनिवार्य", "यदि लागू") if lang == "hi" else ("Mandatory", "If applicable")
    css = (
        "<style>.tm-wrap{overflow:auto;max-height:%dpx;border:1px solid #bbb;border-radius:6px}"
        ".tm{border-collapse:collapse;width:100%%;font-size:13px}"
        ".tm th{position:sticky;top:0;background:#1F3864;color:#fff;padding:6px 8px;border:1px solid #999;z-index:2}"
        ".tm td{padding:5px 8px;border:1px solid #ccc;vertical-align:top}"
        ".tm td.ok{background:#C6EFCE;color:#006100;font-weight:600;text-align:center}"
        ".tm td.no{background:#FFC7CE;color:#9C0006;font-weight:600;text-align:center}"
        ".tm tr.sum td{background:#D9E2F3;font-weight:700}.tm td.c{text-align:center}</style>" % max_height
    )
    h = [css, '<div class="tm-wrap"><table class="tm"><thead><tr>']
    h.append(f"<th>{sr}</th><th>{doc}</th><th>{typ}</th>")
    for b in result.bidders:
        h.append(f"<th>{escape(b)}</th>")
    h.append("</tr></thead><tbody>")
    for i, r in enumerate(reqs, 1):
        h.append(f'<tr><td class="c">{i}</td><td>{escape(r.name)}</td><td class="c">{mand if r.mandatory == MANDATORY else opt}</td>')
        for b in result.bidders:
            ok = result.status(r.rid, b) == "Submitted"
            h.append(f'<td class="{"ok" if ok else "no"}">{"Submitted" if ok else "Not Submitted"}</td>')
        h.append("</tr>")
    labels = [("Total Submitted", 0), ("Total Not Submitted", 1), ("Mandatory missing", 2)]
    if lang == "hi":
        labels = [("कुल Submitted", 0), ("कुल Not Submitted", 1), ("अनिवार्य अनुपलब्ध", 2)]
    for label, k in labels:
        h.append(f'<tr class="sum"><td colspan="3" style="text-align:right">{label}</td>')
        for b in result.bidders:
            h.append(f'<td class="c">{result.counts(b)[k]}</td>')
        h.append("</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


def render_pdf_pages(src: Path | bytes, first: int = 0, count: int = 3, scale: float = 1.3) -> tuple[list[bytes], int]:
    """Return (PNG bytes for pages [first, first+count), total pages)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(src) if isinstance(src, Path) else src)
    try:
        total = len(pdf)
        imgs: list[bytes] = []
        for i in range(first, min(total, first + count)):
            page = pdf[i]
            try:
                pil = page.render(scale=scale).to_pil()
                buf = io.BytesIO()
                pil.save(buf, "PNG")
                imgs.append(buf.getvalue())
            finally:
                page.close()
        return imgs, total
    finally:
        pdf.close()


def docx_preview_images(docx_bytes: bytes, count: int = 3, scale: float = 1.2) -> tuple[list[bytes], int] | None:
    """Render the first pages of a DOCX through LibreOffice. None when LibreOffice is unavailable."""
    if not find_soffice():
        return None
    with tempfile.TemporaryDirectory(prefix="docx_prev_") as td:
        src = Path(td) / "matrix.docx"
        src.write_bytes(docx_bytes)
        res = convert_batch([src], Path(td) / "out", "pdf", batch_size=1, per_file_timeout=120)
        pdf = res.get(src)
        if not pdf:
            return None
        return render_pdf_pages(pdf, 0, count, scale)
