"""Build the "Wanting Document List / Matrix" Word (.docx) file.

* landscape A4, repeating header row, rows never split across pages
* bidders are split into blocks of ``BIDDERS_PER_TABLE`` columns so the page stays readable
* cell text is exactly "Submitted" / "Not Submitted" (green / red shading)
* Hindi text is rendered with a complex-script font (Mangal / Nirmala UI), so mixed
  English + Devanagari documents look right in Word and LibreOffice
* optional annexures: tender references and file-wise mapping per bidder
"""
from __future__ import annotations

import io
import re
from datetime import datetime

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .matching import MatchResult
from .models import MANDATORY, Requirement

BIDDERS_PER_TABLE = 7
GREEN_BG, GREEN_FG = "C6EFCE", RGBColor(0x00, 0x61, 0x00)
RED_BG, RED_FG = "FFC7CE", RGBColor(0x9C, 0x00, 0x06)
HEAD_BG = "1F3864"
SUB_BG = "D9E2F3"

_XML_BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

LABELS = {
    "title": ("Wanting Document List / Matrix - Technical Evaluation", "वांछित दस्तावेज़ सूची / मैट्रिक्स - तकनीकी मूल्यांकन"),
    "tender": ("Tender / Bid", "निविदा / बिड"),
    "date": ("Generated on", "तैयार किया गया"),
    "bidders": ("Bidders evaluated", "मूल्यांकित बिडर्स"),
    "docs": ("Documents wanted", "वांछित दस्तावेज़"),
    "legend": ("Green = Submitted, Red = Not Submitted", "हरा = Submitted, लाल = Not Submitted"),
    "sr": ("S.No.", "क्र.सं."),
    "doc": ("Wanting document", "वांछित दस्तावेज़"),
    "type": ("Type", "प्रकार"),
    "mand": ("Mandatory", "अनिवार्य"),
    "opt": ("If applicable", "यदि लागू"),
    "sub_total": ("Total Submitted", "कुल Submitted"),
    "nsub_total": ("Total Not Submitted", "कुल Not Submitted"),
    "mand_missing": ("Mandatory documents missing", "अनिवार्य दस्तावेज़ अनुपलब्ध"),
    "block": ("Bidders", "बिडर्स"),
    "annex_a": ("Annexure A - Tender reference of each wanting document", "अनुलग्नक A - प्रत्येक वांछित दस्तावेज़ का निविदा संदर्भ"),
    "category": ("Category", "श्रेणी"),
    "source": ("Source", "स्रोत"),
    "reference": ("Tender reference", "निविदा संदर्भ"),
    "annex_b": ("Annexure B - Submitted documents (file-wise mapping)", "अनुलग्नक B - प्रस्तुत दस्तावेज़ (फ़ाइल-वार मिलान)"),
    "file": ("Matched file(s)", "मिलान की गई फ़ाइल(ें)"),
    "basis": ("Match basis", "मिलान का आधार"),
    "note": ("Note: matching is automatic - please verify before final evaluation.",
             "नोट: मिलान स्वचालित है - अंतिम मूल्यांकन से पहले कृपया सत्यापित करें।"),
}


def _t(key: str, lang: str) -> str:
    en, hi = LABELS[key]
    if lang == "en":
        return en
    if lang == "hi":
        return hi
    return f"{en}\n{hi}" if key in ("sr", "doc", "type", "sub_total", "nsub_total", "mand_missing") else f"{en} / {hi}"


def clean(s: object) -> str:
    return _XML_BAD.sub("", str(s if s is not None else ""))


# ----------------------------------------------------------------- low level helpers
def _set_fonts(rpr_parent, western: str = "Calibri", complex_: str = "Mangal") -> None:
    rpr = rpr_parent.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for attr, val in (("w:ascii", western), ("w:hAnsi", western), ("w:cs", complex_), ("w:eastAsia", complex_)):
        rf.set(qn(attr), val)
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rpr.append(lang)
    lang.set(qn("w:val"), "en-IN")
    lang.set(qn("w:bidi"), "hi-IN")


def _style_run(run, size: float, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    for tag, val in (("w:szCs", str(int(size * 2))),):
        el = rpr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            rpr.append(el)
        el.set(qn("w:val"), val)
    if bold and rpr.find(qn("w:bCs")) is None:
        rpr.append(OxmlElement("w:bCs"))


def _shade(cell, hex_fill: str) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    for old in tcpr.findall(qn("w:shd")):
        tcpr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def _cell_text(cell, text: str, size: float = 9, bold: bool = False, color: RGBColor | None = None,
               align=None, bg: str | None = None) -> None:
    cell.text = ""
    lines = clean(text).split("\n")
    p = cell.paragraphs[0]
    for i, ln in enumerate(lines):
        if i:
            p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        if align is not None:
            p.alignment = align
        _style_run(p.add_run(ln), size, bold, color)
    if bg:
        _shade(cell, bg)


def _repeat_header(row) -> None:
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def _no_split(row) -> None:
    trpr = row._tr.get_or_add_trPr()
    trpr.append(OxmlElement("w:cantSplit"))


def _fixed_layout(table) -> None:
    tblpr = table._tbl.tblPr
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblpr.append(lay)


def _set_widths(table, widths_cm: list[float]) -> None:
    table.autofit = False
    _fixed_layout(table)
    for idx, w in enumerate(widths_cm):
        if idx < len(table.columns):
            table.columns[idx].width = Cm(w)      # <w:gridCol> - LibreOffice needs this
    for row in table.rows:
        for idx, w in enumerate(widths_cm):
            if idx < len(row.cells):
                row.cells[idx].width = Cm(w)


def _page_number_footer(section) -> None:
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    _style_run(run, 8)


def _heading(doc, text: str, size: float = 12, space_before: float = 10) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    _style_run(p.add_run(clean(text)), size, True, RGBColor(0x1F, 0x38, 0x64))


# --------------------------------------------------------------------------- builder
def build_matrix_docx(
    reqs: list[Requirement],
    result: MatchResult,
    *,
    tender_title: str = "",
    lang: str = "both",                 # en | hi | both  (labels)
    include_annex_a: bool = True,
    include_annex_b: bool = True,
) -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.2)
    sec.top_margin, sec.bottom_margin = Cm(1.4), Cm(1.4)
    usable = 29.7 - 2.4

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    _set_fonts(normal.element)
    _page_number_footer(sec)

    cp = doc.core_properties
    cp.title = "Wanting Document List / Matrix"
    cp.author = "Tender Matrix App"

    # ---- title block
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _style_run(p.add_run(clean(_t("title", "en") if lang == "en" else _t("title", "hi") if lang == "hi"
                                 else LABELS["title"][0] + "\n" + LABELS["title"][1])), 15, True, RGBColor(0x1F, 0x38, 0x64))
    meta = []
    if tender_title.strip():
        meta.append(f"{_t('tender', lang if lang != 'both' else 'both')}: {tender_title.strip()}")
    meta.append(f"{_t('date', 'both' if lang == 'both' else lang)}: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    meta.append(f"{_t('bidders', 'both' if lang == 'both' else lang)}: {len(result.bidders)}   |   "
                f"{_t('docs', 'both' if lang == 'both' else lang)}: {len(reqs)}")
    for m in meta:
        mp = doc.add_paragraph()
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        mp.paragraph_format.space_after = Pt(1)
        _style_run(mp.add_run(clean(m)), 9.5)
    lp = doc.add_paragraph()
    lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _style_run(lp.add_run(clean(_t("legend", "both" if lang == "both" else lang).replace("\n", "  |  "))), 8.5, False,
               RGBColor(0x59, 0x59, 0x59))

    bidders = result.bidders
    blocks = [bidders[i:i + BIDDERS_PER_TABLE] for i in range(0, max(len(bidders), 1), BIDDERS_PER_TABLE)] or [[]]

    for bi, block in enumerate(blocks):
        if len(blocks) > 1:
            _heading(doc, f"{_t('block', 'both' if lang == 'both' else lang)} {bi * BIDDERS_PER_TABLE + 1}"
                          f"-{bi * BIDDERS_PER_TABLE + len(block)}", 10.5, 8)
        _matrix_table(doc, reqs, result, block, usable, lang)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    _style_run(p.add_run(clean(_t("note", "both" if lang == "both" else lang).replace("\n", "  "))), 8, False,
               RGBColor(0x59, 0x59, 0x59))

    if include_annex_a:
        doc.add_page_break()
        _annex_a(doc, reqs, usable, lang)
    if include_annex_b:
        doc.add_page_break()
        _annex_b(doc, reqs, result, usable, lang)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _matrix_table(doc, reqs, result: MatchResult, block: list[str], usable: float, lang: str) -> None:
    n = len(block)
    fixed = [1.1, 8.2, 2.1]
    rest = usable - sum(fixed)
    bw = max(1.9, min(3.6, rest / max(n, 1)))
    widths = fixed + [bw] * n
    font = 9 if n <= 5 else 8

    table = doc.add_table(rows=1, cols=3 + n)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr = table.rows[0]
    heads = [_t("sr", lang), _t("doc", lang), _t("type", lang)] + list(block)
    for c, h in zip(hdr.cells, heads):
        _cell_text(c, h, font, True, RGBColor(0xFF, 0xFF, 0xFF), WD_ALIGN_PARAGRAPH.CENTER, HEAD_BG)
    _repeat_header(hdr)

    for i, r in enumerate(reqs, 1):
        row = table.add_row()
        _no_split(row)
        mand = _t("mand", lang) if r.mandatory == MANDATORY else _t("opt", lang)
        _cell_text(row.cells[0], str(i), font, align=WD_ALIGN_PARAGRAPH.CENTER)
        _cell_text(row.cells[1], r.name, font)
        _cell_text(row.cells[2], mand.replace("\n", " / "), font - 0.5, align=WD_ALIGN_PARAGRAPH.CENTER)
        for j, b in enumerate(block):
            ok = result.status(r.rid, b) == "Submitted"
            _cell_text(row.cells[3 + j], "Submitted" if ok else "Not Submitted", font, True,
                       GREEN_FG if ok else RED_FG, WD_ALIGN_PARAGRAPH.CENTER, GREEN_BG if ok else RED_BG)

    # summary rows
    def summary(label: str, values: list[str], bold_red: bool = False) -> None:
        row = table.add_row()
        _no_split(row)
        a = row.cells[0].merge(row.cells[2])
        _cell_text(a, label.replace("\n", " / "), font, True, bg=SUB_BG, align=WD_ALIGN_PARAGRAPH.RIGHT)
        for j, v in enumerate(values):
            _cell_text(row.cells[3 + j], v, font, True,
                       RED_FG if (bold_red and v not in ("0", "")) else None,
                       WD_ALIGN_PARAGRAPH.CENTER, SUB_BG)

    counts = [result.counts(b) for b in block]
    summary(_t("sub_total", lang), [str(c[0]) for c in counts])
    summary(_t("nsub_total", lang), [str(c[1]) for c in counts])
    summary(_t("mand_missing", lang), [str(c[2]) for c in counts], bold_red=True)
    _set_widths(table, widths)


def _annex_a(doc, reqs: list[Requirement], usable: float, lang: str) -> None:
    _heading(doc, _t("annex_a", "both" if lang == "both" else lang).replace("\n", " / "), 12, 0)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    heads = [_t("sr", lang), _t("doc", lang), _t("category", lang), _t("source", lang), _t("reference", lang)]
    for c, h in zip(table.rows[0].cells, heads):
        _cell_text(c, h, 9, True, RGBColor(0xFF, 0xFF, 0xFF), WD_ALIGN_PARAGRAPH.CENTER, HEAD_BG)
    _repeat_header(table.rows[0])
    for i, r in enumerate(reqs, 1):
        row = table.add_row()
        _no_split(row)
        _cell_text(row.cells[0], str(i), 8.5, align=WD_ALIGN_PARAGRAPH.CENTER)
        _cell_text(row.cells[1], r.name, 8.5)
        _cell_text(row.cells[2], r.category, 8.5)
        _cell_text(row.cells[3], r.source, 8.5)
        _cell_text(row.cells[4], r.reference[:600], 8)
    _set_widths(table, [1.1, 7.2, 3.4, 2.8, usable - 14.5])


def _annex_b(doc, reqs: list[Requirement], result: MatchResult, usable: float, lang: str) -> None:
    _heading(doc, _t("annex_b", "both" if lang == "both" else lang).replace("\n", " / "), 12, 0)
    for b in result.bidders:
        rows = []
        for i, r in enumerate(reqs, 1):
            ms = result.cells.get((r.rid, b), [])
            if ms:
                rows.append((i, r.name, "; ".join(m.rel for m in ms),
                             "; ".join(sorted({m.how.split(":")[0] for m in ms}))))
        _heading(doc, b, 10.5, 8)
        if not rows:
            continue
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        heads = [_t("sr", lang), _t("doc", lang), _t("file", lang), _t("basis", lang)]
        for c, h in zip(table.rows[0].cells, heads):
            _cell_text(c, h, 8.5, True, RGBColor(0xFF, 0xFF, 0xFF), WD_ALIGN_PARAGRAPH.CENTER, HEAD_BG)
        _repeat_header(table.rows[0])
        for i, name, files, basis in rows:
            row = table.add_row()
            _no_split(row)
            _cell_text(row.cells[0], str(i), 8, align=WD_ALIGN_PARAGRAPH.CENTER)
            _cell_text(row.cells[1], name, 8)
            _cell_text(row.cells[2], files, 8)
            _cell_text(row.cells[3], basis, 8)
        _set_widths(table, [1.1, 9.0, usable - 15.1, 5.0])
