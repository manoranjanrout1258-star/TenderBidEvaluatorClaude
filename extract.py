"""Text extraction from PDF / DOCX / XLSX / DOC / XLS / images (with optional OCR)."""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .office import convert_batch, find_soffice


@dataclass
class ExtractOptions:
    max_pages: int = 60          # PDF pages to read
    max_chars: int = 400_000     # cap per document
    ocr: bool = False
    ocr_lang: str = "eng+hin"
    ocr_pages: int = 3           # pages OCR-ed for scanned PDFs
    min_chars_per_page: int = 25  # below this a PDF is treated as scanned


@dataclass
class DocText:
    path: Path
    ext: str
    pages: list[str] = field(default_factory=list)   # PDF: one entry per page; others: single entry
    n_pages: int | None = None
    method: str = "text"          # text | ocr | none | error
    warning: str = ""

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    @property
    def title_text(self) -> str:
        t = self.pages[0] if self.pages else ""
        return t[:900]


# ------------------------------------------------------------------ OCR helpers

_OCR_LANGS: str | None = None


def tesseract_available() -> bool:
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401
        return True
    except Exception:
        return False


def ocr_lang_string(preferred: str = "eng+hin") -> str:
    """Pick the OCR languages that are really installed."""
    global _OCR_LANGS
    if _OCR_LANGS is None:
        try:
            import pytesseract

            have = set(pytesseract.get_languages(config=""))
        except Exception:
            have = set()
        want = [l for l in preferred.split("+") if l in have]
        _OCR_LANGS = "+".join(want) if want else ("eng" if "eng" in have else "")
    return _OCR_LANGS


def _ocr_image(img, lang: str) -> str:
    import pytesseract

    return pytesseract.image_to_string(img, lang=lang or "eng", timeout=90)


# ---------------------------------------------------------------------- PDF


def _pdf_pages_pdfium(path: Path, max_pages: int) -> tuple[list[str], int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        n = len(pdf)
        out: list[str] = []
        for i in range(min(n, max_pages)):
            page = pdf[i]
            tp = page.get_textpage()
            try:
                out.append((tp.get_text_range() or "").replace("\r\n", "\n").replace("\r", "\n"))
            finally:
                tp.close()
                page.close()
        return out, n
    finally:
        pdf.close()


def _pdf_pages_pypdf(path: Path, max_pages: int) -> tuple[list[str], int]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass
    n = len(reader.pages)
    out = []
    for i in range(min(n, max_pages)):
        try:
            out.append(reader.pages[i].extract_text() or "")
        except Exception:
            out.append("")
    return out, n


def _pdf_ocr(path: Path, opts: ExtractOptions) -> list[str]:
    import pypdfium2 as pdfium

    lang = ocr_lang_string(opts.ocr_lang)
    pdf = pdfium.PdfDocument(str(path))
    out: list[str] = []
    try:
        for i in range(min(len(pdf), opts.ocr_pages)):
            page = pdf[i]
            try:
                img = page.render(scale=2.2).to_pil()
                out.append(_ocr_image(img, lang))
            finally:
                page.close()
    finally:
        pdf.close()
    return out


def extract_pdf(path: Path, opts: ExtractOptions) -> DocText:
    doc = DocText(path=path, ext=".pdf")
    pages: list[str] = []
    n_total = None
    last_err = ""
    for fn in (_pdf_pages_pdfium, _pdf_pages_pypdf):
        try:
            pages, n_total = fn(path, opts.max_pages)
            last_err = ""
            break
        except ImportError as e:
            last_err = str(e)
        except Exception as e:  # corrupt / encrypted
            last_err = f"{type(e).__name__}: {e}"
    if last_err and not pages:
        doc.method, doc.warning = "error", f"PDF unreadable ({last_err[:120]})"
        return doc

    doc.n_pages = n_total
    total_chars = sum(len(p.strip()) for p in pages)
    scanned = not pages or total_chars < opts.min_chars_per_page * max(1, min(len(pages), 3))
    if scanned:
        if opts.ocr and tesseract_available():
            try:
                pages = _pdf_ocr(path, opts)
                doc.method = "ocr"
                if sum(len(x.strip()) for x in pages) < 10:
                    doc.method, doc.warning = "none", "scanned PDF - OCR found no text"
            except Exception as e:
                doc.method, doc.warning = "none", f"OCR failed ({type(e).__name__})"
        else:
            doc.method, doc.warning = "none", "scanned PDF / no text layer (enable OCR)"
    doc.pages = _cap_pages(pages, opts.max_chars)
    return doc


def _cap_pages(pages: list[str], max_chars: int) -> list[str]:
    out, used = [], 0
    for p in pages:
        if used >= max_chars:
            break
        out.append(p[: max_chars - used])
        used += len(out[-1])
    return out


# --------------------------------------------------------------------- DOCX


def _dedupe_cells(cells: list[str]) -> list[str]:
    out: list[str] = []
    for c in cells:
        if not out or out[-1] != c:
            out.append(c)
    return out


def _table_rows(table) -> list[list[str]]:
    rows = []
    for row in table.rows:
        cells = []
        for c in row.cells:
            t = " ".join(c.text.split())
            cells.append(t)
        cells = _dedupe_cells([c for c in cells])
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def docx_blocks(path: Path) -> list[tuple[str, object]]:
    """Ordered blocks: ('p', text) or ('t', [[cell,...], ...])."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    blocks: list[tuple[str, object]] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(child, doc).text.strip()
            if t:
                blocks.append(("p", t))
        elif tag == "tbl":
            rows = _table_rows(Table(child, doc))
            if rows:
                blocks.append(("t", rows))
    return blocks


def extract_docx(path: Path, opts: ExtractOptions) -> DocText:
    doc = DocText(path=path, ext=".docx")
    try:
        lines: list[str] = []
        for kind, val in docx_blocks(path):
            if kind == "p":
                lines.append(str(val))
            else:
                for row in val:  # type: ignore[union-attr]
                    lines.append(" | ".join(row))
        text = "\n".join(lines)
        if len(text.strip()) < 40:  # maybe text boxes only
            from docx import Document

            d = Document(str(path))
            ts = [t.text for t in d.element.body.iter() if t.tag.endswith("}t") and t.text]
            text = text + "\n" + " ".join(ts)
        doc.pages = [text[: opts.max_chars]]
    except Exception as e:
        doc.method, doc.warning = "error", f"DOCX unreadable ({type(e).__name__})"
    return doc


# --------------------------------------------------------------------- XLSX


def extract_xlsx(path: Path, opts: ExtractOptions, max_rows: int = 3000, max_sheets: int = 40) -> DocText:
    doc = DocText(path=path, ext=path.suffix.lower())
    try:
        from openpyxl import load_workbook

        wb = load_workbook(str(path), read_only=True, data_only=True)
        lines: list[str] = []
        try:
            for ws in wb.worksheets[:max_sheets]:
                lines.append(f"[Sheet] {ws.title}")
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i >= max_rows:
                        break
                    vals = [str(v).strip() for v in row if v not in (None, "")]
                    if vals:
                        lines.append(" | ".join(vals))
        finally:
            wb.close()
        doc.pages = ["\n".join(lines)[: opts.max_chars]]
    except Exception as e:
        doc.method, doc.warning = "error", f"XLSX unreadable ({type(e).__name__})"
    return doc


# ------------------------------------------------------------------- legacy


def extract_legacy(path: Path, opts: ExtractOptions) -> DocText:
    """.doc / .xls -> convert with LibreOffice first (if available)."""
    ext = path.suffix.lower()
    fmt = "docx" if ext == ".doc" else "xlsx"
    if not find_soffice():
        return DocText(path=path, ext=ext, method="none",
                       warning=f"{ext} needs LibreOffice to be read (filename-only matching)")
    with tempfile.TemporaryDirectory(prefix="legacy_") as td:
        res = convert_batch([path], Path(td), fmt, batch_size=1, per_file_timeout=60)
        out = res.get(path)
        if not out:
            return DocText(path=path, ext=ext, method="none", warning=f"{ext} conversion failed")
        d = extract_docx(out, opts) if fmt == "docx" else extract_xlsx(out, opts)
        d.path, d.ext = path, ext
        return d


# ------------------------------------------------------------------- images


def extract_image(path: Path, opts: ExtractOptions) -> DocText:
    doc = DocText(path=path, ext=path.suffix.lower(), method="none",
                  warning="image file (enable OCR to read text)")
    if opts.ocr and tesseract_available():
        try:
            from PIL import Image

            with Image.open(path) as im:
                im.load()
                doc.pages = [_ocr_image(im.convert("RGB"), ocr_lang_string(opts.ocr_lang))]
            doc.method, doc.warning = "ocr", ""
        except Exception as e:
            doc.warning = f"OCR failed ({type(e).__name__})"
    return doc


# ----------------------------------------------------------------- dispatcher


def extract_any(path: Path, opts: ExtractOptions | None = None) -> DocText:
    opts = opts or ExtractOptions()
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return extract_pdf(path, opts)
        if ext == ".docx":
            return extract_docx(path, opts)
        if ext in (".xlsx", ".xlsm"):
            return extract_xlsx(path, opts)
        if ext in (".doc", ".xls"):
            return extract_legacy(path, opts)
        if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"):
            return extract_image(path, opts)
    except Exception as e:  # never let one bad file stop the whole run
        return DocText(path=path, ext=ext, method="error", warning=f"{type(e).__name__}: {e}"[:150])
    return DocText(path=path, ext=ext, method="none", warning="unsupported type")
