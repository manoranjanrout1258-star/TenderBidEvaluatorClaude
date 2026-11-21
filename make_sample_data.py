"""Generate a synthetic tender package + 3 bidder ZIPs (English / Hindi / Hinglish) for testing.

    python tests/make_sample_data.py  <output_dir>

Creates:
    <out>/tender/Tender_Package.zip          (tender docx + NIT pdf + corrigendum docx)
    <out>/bidders/ABC Constructions Pvt Ltd.zip
    <out>/bidders/XYZ Traders.zip            (single wrapper folder, Hinglish file names)
    <out>/bidders/Hindi Udyog.zip            (Hindi file names, scanned PDF)
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT = None


def _font() -> str:
    global _FONT
    if _FONT is None:
        for f in FONT_CANDIDATES:
            if Path(f).exists():
                pdfmetrics.registerFont(TTFont("SampleFont", f))
                _FONT = "SampleFont"
                break
        else:
            _FONT = "Helvetica"
    return _FONT


def make_pdf(lines: list[str], pages: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for pg in range(pages):
        c.setFont(_font(), 13)
        y = 800
        for ln in lines if pg == 0 else [f"Page {pg + 1} continuation of the document"]:
            c.drawString(50, y, ln)
            y -= 20
        c.showPage()
    c.save()
    return buf.getvalue()


def make_scanned_pdf(text: str) -> bytes:
    """An image-only PDF (no text layer) containing `text` -> needs OCR."""
    img = Image.new("RGB", (1240, 400), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 54)
    except Exception:
        f = ImageFont.load_default()
    d.text((60, 140), text, fill="black", font=f)
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150)
    return buf.getvalue()


def make_blank_scanned_pdf() -> bytes:
    img = Image.new("RGB", (800, 300), "white")
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=100)
    return buf.getvalue()


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=len(table), cols=len(table[0]))
        for i, row in enumerate(table):
            for j, v in enumerate(row):
                t.cell(i, j).text = v
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_xlsx(rows: list[list[str]], title: str = "Sheet1") -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = title
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------- tender
TENDER_PARAS = [
    "NOTICE INVITING TENDER",
    "Tender No: PWD/ELEC/2026/045 - Supply and installation of LED street lights",
    "1. Eligibility Criteria",
    "The bidder should fulfil the following conditions and must submit the documents listed below:",
    "(a) Tender document fee of Rs. 1,000 by DD or online payment.",
    "(b) EMD of Rs. 50,000 (Earnest Money Deposit) in the form of DD or Bank Guarantee.",
    "(c) Certificate of Incorporation / Partnership Deed / registration of firm.",
    "(d) PAN card and GST registration certificate.",
    "(e) Income Tax Returns for the last three years.",
    "(f) Audited balance sheet and Profit & Loss account for last 3 financial years.",
    "(g) Annual turnover certificate of minimum Rs. 2 crore (CA certified).",
    "(h) Experience certificate of similar works completed in last 5 years.",
    "(i) Valid ISO 9001 certificate.",
    "(j) OEM / manufacturer authorization form (MAF) for quoted products.",
    "(k) Power of Attorney / authorised signatory letter.",
    "(l) Affidavit on stamp paper that the firm is not blacklisted.",
    "(m) Technical specification compliance sheet and product datasheet.",
    "(n) Bank solvency certificate.",
    "(o) Details of service centre in the state.",
    "(p) Signed and stamped copy of this tender document and corrigendum.",
    "2. Payment Terms",
    "Payment shall be made within 30 days of receipt of invoice. GST extra as applicable.",
    "3. General Conditions",
    "Arbitration will be as per the Arbitration and Conciliation Act.",
    "ANNEXURES",
    "Annexure-I: Bidder Information Form",
    "Annexure-II: Declaration regarding non blacklisting",
    "Annexure-III: Undertaking for delivery of material within schedule",
    "पात्रता मानदंड (Hindi)",
    "बोलीदाता को निम्नलिखित दस्तावेज़ प्रस्तुत करने होंगे:",
    "(1) अनुभव प्रमाण पत्र की प्रति",
    "(2) श्रम लाइसेंस की प्रति",
    "(3) ईएसआईसी पंजीकरण प्रमाण पत्र",
]

NIT_PDF_LINES = [
    "NIT - PWD Electrical Division",
    "The tender fee must be paid; submit proof of payment along with the bid.",
    "Bidders are requested to upload scanned copy of the above documents.",
]

CORRIGENDUM_PARAS = [
    "CORRIGENDUM No. 1 to Tender No. PWD/ELEC/2026/045",
    "Clause 1(i) regarding ISO 9001 certificate stands deleted.",
    "A new clause is added: Bidders shall submit MSME / Udyam registration certificate (if applicable).",
    "All other terms and conditions remain unchanged. Last date of submission is extended.",
]


def build(out: Path) -> None:
    (out / "tender").mkdir(parents=True, exist_ok=True)
    (out / "bidders").mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out / "tender" / "Tender_Package.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Tender_Document.docx", make_docx(TENDER_PARAS))
        z.writestr("NIT_Notice.pdf", make_pdf(NIT_PDF_LINES))
        z.writestr("Corrigendum_1.docx", make_docx(CORRIGENDUM_PARAS))

    # ----- bidder 1: English, many docs, scanned names, folder, junk files
    with zipfile.ZipFile(out / "bidders" / "ABC Constructions Pvt Ltd.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("01_Tender_Fee_Receipt.pdf", make_pdf(["Receipt", "Tender document fee paid Rs 1000"]))
        z.writestr("EMD_DD_copy.pdf", make_pdf(["Demand Draft No 123456", "Earnest Money Deposit Rs 50000"]))
        z.writestr("Certificate of Incorporation.pdf", make_pdf(["Certificate of Incorporation", "Registrar of Companies"]))
        z.writestr("PAN.pdf", make_pdf(["INCOME TAX DEPARTMENT", "Permanent Account Number Card ABCDE1234F"]))
        z.writestr("GST Registration Certificate.pdf", make_pdf(["Form GST REG-06", "Registration Certificate GSTIN 22ABCDE1234F1Z5"]))
        z.writestr("ITR_2022-23.pdf", make_pdf(["Income Tax Return Acknowledgement AY 2022-23"]))
        z.writestr("ITR_2023-24.pdf", make_pdf(["Income Tax Return Acknowledgement AY 2023-24"]))
        z.writestr("Balance Sheet 3 years.pdf", make_pdf(["Audited Balance Sheet and Profit and Loss Account"], pages=3))
        z.writestr("CA_Turnover.pdf", make_pdf(["To whomsoever it may concern", "Annual Turnover Certificate (CA certified)"]))
        z.writestr("scan0007.pdf", make_pdf(["EXPERIENCE CERTIFICATE", "Work of similar nature completed satisfactorily"]))
        z.writestr("Labour.pdf", make_pdf(["श्रम लाइसेंस", "ठेकेदार श्रम अधिनियम के अंतर्गत"]))
        z.writestr("OEM_Authorization.docx", make_docx(["OEM Authorization Letter", "We authorise M/s ABC to quote our products."]))
        z.writestr("Power_of_Attorney.docx", make_docx(["POWER OF ATTORNEY", "Mr. A is authorised to sign the bid."]))
        z.writestr("Affidavit_not_blacklisted.pdf", make_pdf(["AFFIDAVIT", "The firm has not been blacklisted by any department."]))
        z.writestr("Tech_Compliance.xlsx", make_xlsx([["Item", "Specification", "Compliance"], ["LED 60W", "As per tender", "Yes"]],
                                                      title="Technical Specification Compliance"))
        z.writestr("datasheet_led.pdf", make_pdf(["LED Street Light - Product Datasheet"]))
        z.writestr("Annexures/Annexure-I Bidder Information.docx", make_docx(["Bidder Information Form", "Name: ABC"]))
        z.writestr("Annexures/Annexure-II Declaration non blacklisting.pdf", make_pdf(["Declaration regarding non blacklisting"]))
        z.writestr("Annexures/Annexure-III.pdf", make_pdf(["Undertaking for delivery of material within schedule"]))
        z.writestr("__MACOSX/._01_Tender_Fee_Receipt.pdf", b"junk")
        z.writestr("Thumbs.db", b"junk")

    # ----- bidder 2: wrapper folder + Hinglish names + nested zip
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as nz:
        nz.writestr("completion_cert.pdf", make_pdf(["Work Completion Certificate", "Supply and installation completed"]))
        nz.writestr("work_order_1.pdf", make_pdf(["Work Order No 45/2023"]))
    with zipfile.ZipFile(out / "bidders" / "XYZ Traders.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("XYZ Traders/pan_card.pdf", make_pdf(["PAN Card"]))
        z.writestr("XYZ Traders/gst.pdf", make_pdf(["GST certificate"]))
        z.writestr("XYZ Traders/shapath_patra.pdf", make_pdf(["Shapath Patra", "Firm is not blacklisted"]))
        z.writestr("XYZ Traders/mukhtarnama.docx", make_docx(["Mukhtarnama (Power of Attorney)"]))
        z.writestr("XYZ Traders/tender fee.pdf", make_pdf(["Tender fee receipt"]))
        z.writestr("XYZ Traders/EMD.pdf", make_pdf(["EMD receipt"]))
        z.writestr("XYZ Traders/Annual_Report_2023.pdf", make_pdf(["Audited Financial Statements - Balance Sheet"]))
        z.writestr("XYZ Traders/random_notes.pdf", make_pdf(["Some internal notes about lunch"]))
        z.writestr("XYZ Traders/past_work.zip", nested.getvalue())

    # ----- bidder 3: Hindi names, scanned pdfs
    with zipfile.ZipFile(out / "bidders" / "Hindi Udyog.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("निविदा शुल्क रसीद.pdf", make_pdf(["निविदा शुल्क जमा रसीद"]))
        z.writestr("अग्रिम राशि (EMD).pdf", make_pdf(["बयाना राशि डिमांड ड्राफ्ट"]))
        z.writestr("पैन कार्ड.pdf", make_pdf(["स्थायी खाता संख्या"]))
        z.writestr("जीएसटी प्रमाण पत्र.pdf", make_pdf(["जीएसटी पंजीकरण प्रमाण पत्र"]))
        z.writestr("अनुभव प्रमाण पत्र.pdf", make_pdf(["अनुभव प्रमाण पत्र", "कार्य पूर्णता प्रमाण पत्र"]))
        z.writestr("ईएसआईसी पंजीकरण.pdf", make_pdf(["कर्मचारी राज्य बीमा निगम पंजीकरण"]))
        z.writestr("श्रम लाइसेंस.pdf", make_pdf(["श्रम लाइसेंस"]))
        z.writestr("बैलेंस शीट.pdf", make_pdf(["तुलन पत्र एवं लाभ हानि खाता"]))
        z.writestr("scan001.pdf", make_blank_scanned_pdf())
        z.writestr("scan_net.pdf", make_scanned_pdf("NET WORTH CERTIFICATE"))


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_data")
    build(target)
    print("sample data written to", target.resolve())
