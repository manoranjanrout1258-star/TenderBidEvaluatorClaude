"""End-to-end tests on synthetic English / Hindi / Hinglish data.  Run:  python -m pytest -q tests"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from docx import Document  # noqa: E402
from pypdf import PdfReader  # noqa: E402

import make_sample_data  # noqa: E402
from tendermatrix.bidders import unpack_bidders, unpack_tender  # noqa: E402
from tendermatrix.docx_report import build_matrix_docx  # noqa: E402
from tendermatrix.extract import ExtractOptions, extract_any, tesseract_available  # noqa: E402
from tendermatrix.llm import analyze_with_llm, parse_json  # noqa: E402
from tendermatrix.matching import build_vocab, compile_specs, match_all  # noqa: E402
from tendermatrix.models import df_to_reqs, reqs_to_df  # noqa: E402
from tendermatrix.package_zip import build_output_zip  # noqa: E402
from tendermatrix.pipeline import analyze_tender, index_bidder_set  # noqa: E402
from tendermatrix.tender_analysis import build_paragraphs, scan_paragraphs  # noqa: E402
from tendermatrix.utils import new_workspace, safe_extract_zip  # noqa: E402


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("sample")
    make_sample_data.build(out)
    ws = new_workspace("test_t")
    ts = unpack_tender([out / "tender" / "Tender_Package.zip"], ws)
    outcome = analyze_tender(ts.files, ocr=False)
    reqs = [r for r in outcome.reqs if r.include]
    bws = new_workspace("test_b")
    bs = unpack_bidders(sorted((out / "bidders").glob("*.zip")), bws, "auto")
    specs = compile_specs(reqs)
    feats = index_bidder_set(bs, build_vocab(specs), ocr=True)
    res = match_all(feats, specs, 0.6)
    return dict(ts=ts, outcome=outcome, reqs=reqs, bs=bs, res=res, bws=bws, feats=feats)


def rid_of(world, cat_id):
    return next(r.rid for r in world["reqs"] if r.cat_id == cat_id)


# ------------------------------------------------------------------ tender
def test_corrigendum_detected(world):
    corr = [f.path.name for f in world["ts"].files if f.corrigendum]
    assert corr == ["Corrigendum_1.docx"]


def test_tender_requirements(world):
    allr = {r.cat_id or r.name: r for r in world["outcome"].reqs}
    for cid in ("tender_fee", "emd", "pan", "gst_reg", "itr", "balance_sheet", "turnover", "experience", "oem_auth",
                "poa", "affidavit", "tech_spec", "solvency", "labour_licence", "esic"):
        assert cid in allr and allr[cid].include, cid
    # Hindi-only clauses were understood
    assert "श्रम लाइसेंस" in allr["labour_licence"].reference
    # corrigendum: ISO deleted -> off, MSME added -> corrigendum source
    assert not allr["iso"].include and "Corrigendum" in allr["iso"].note
    assert allr["msme"].source == "Corrigendum" and allr["msme"].mandatory == "If applicable"
    # annexure without catalog entry becomes its own row with label keywords
    annex = next(r for r in world["outcome"].reqs if r.name.startswith("Annexure III"))
    assert "annexure 3" in annex.keywords


def test_dataframe_roundtrip(world):
    df = reqs_to_df(world["outcome"].reqs)
    back = df_to_reqs(df)
    assert [r.rid for r in back] == [r.rid for r in world["reqs"]]
    df.loc[len(df)] = [True, None, "My own document", "Mandatory", "", "", "", "", "my doc; mera dastavez", ""]
    assert df_to_reqs(df)[-1].name == "My own document" and df_to_reqs(df)[-1].rid.startswith("U")


# ---------------------------------------------------------------- bidders
def test_bidder_detection(world):
    bs = world["bs"]
    assert set(bs.bidders) == {"ABC Constructions Pvt Ltd", "XYZ Traders", "Hindi Udyog"}
    assert len(bs.bidders["XYZ Traders"]) == 10          # wrapper folder removed, nested zip expanded
    names = [f.name for f in bs.bidders["ABC Constructions Pvt Ltd"]]
    assert "Thumbs.db" not in names and not any(n.startswith("._") for n in names)


# ---------------------------------------------------------------- matching
@pytest.mark.parametrize("cid,bidder,expected", [
    ("pan", "ABC Constructions Pvt Ltd", "Submitted"),
    ("pan", "Hindi Udyog", "Submitted"),                 # Hindi file name
    ("pan", "XYZ Traders", "Submitted"),
    ("experience", "ABC Constructions Pvt Ltd", "Submitted"),   # file 'scan0007.pdf' -> found through first-page text
    ("experience", "XYZ Traders", "Submitted"),                 # 'completion_cert.pdf' inside nested zip
    ("poa", "XYZ Traders", "Submitted"),                 # Hinglish 'mukhtarnama'
    ("affidavit", "XYZ Traders", "Submitted"),           # Hinglish 'shapath patra'
    ("labour_licence", "ABC Constructions Pvt Ltd", "Submitted"),  # Hindi first-page text, English file name
    ("esic", "Hindi Udyog", "Submitted"),
    ("solvency", "ABC Constructions Pvt Ltd", "Not Submitted"),
    ("itr", "XYZ Traders", "Not Submitted"),
    ("oem_auth", "Hindi Udyog", "Not Submitted"),
    ("signed_tender", "ABC Constructions Pvt Ltd", "Not Submitted"),
])
def test_status(world, cid, bidder, expected):
    assert world["res"].status(rid_of(world, cid), bidder) == expected


def test_gst_returns_not_confused_with_registration():
    from tendermatrix.catalog import CATALOG
    from tendermatrix.textutil import TextView
    v = TextView("GST Returns 2023.pdf")
    assert CATALOG["gst_returns"].find(v) and not CATALOG["gst_reg"].find(v)


def test_typo_in_filename_still_matches(world, tmp_path):
    from tendermatrix.extract import DocText
    from tendermatrix.matching import build_feat, score_pair
    specs = compile_specs([r for r in world["reqs"] if r.cat_id == "experience"])
    vocab = build_vocab(specs)
    ft = build_feat("b", tmp_path / "x.pdf", "Experiance Ceritificate.pdf", DocText(tmp_path / "x.pdf", ".pdf", pages=[""]), vocab)
    assert score_pair(specs[0], ft)[0] >= 0.6


def test_manual_override(world):
    res = world["res"]
    rid = rid_of(world, "solvency")
    b = "ABC Constructions Pvt Ltd"
    some = next(iter(rel for (bb, rel) in res.paths if bb == b))
    res.set_manual(rid, b, [some])
    assert res.status(rid, b) == "Submitted"
    res.set_manual(rid, b, [])
    assert res.status(rid, b) == "Not Submitted"


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")
def test_ocr_reads_scanned_pdf(world):
    f = next(p for p in world["bs"].bidders["Hindi Udyog"] if p.name == "scan_net.pdf")
    assert "NET WORTH" in extract_any(f, ExtractOptions(ocr=True)).text.upper()
    assert extract_any(f, ExtractOptions(ocr=False)).method == "none"


# ------------------------------------------------------------------ outputs
def test_docx_output(world):
    data = build_matrix_docx(world["reqs"], world["res"], tender_title="Test / परीक्षण", lang="both")
    p = ROOT / "tests" / "_matrix.docx"
    p.write_bytes(data)
    try:
        d = Document(str(p))
    finally:
        p.unlink()
    t = d.tables[0]
    assert len(t.rows) == 1 + len(world["reqs"]) + 3          # header + docs + 3 summary rows
    cells = {c.text for row in t.rows[1:1 + len(world["reqs"])] for c in row.cells[3:]}
    assert cells == {"Submitted", "Not Submitted"}
    full = "\n".join(c.text for row in t.rows for c in row.cells)
    assert "निविदा दस्तावेज़ शुल्क" in full
    assert "परीक्षण" in "\n".join(p_.text for p_ in d.paragraphs)


def test_zip_output(world, tmp_path):
    out = tmp_path / "o.zip"
    ent = build_output_zip(world["reqs"], world["res"], out, tmp_path, extras={"00_matrix.docx": b"x"})
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert len(names) == len({n.lower() for n in names})
        pdfs = [n for n in names if n.endswith(".pdf")]
        assert len(pdfs) == len(ent) and "00_Match_Report.csv" in names
        for n in pdfs:
            assert len(PdfReader(__import__("io").BytesIO(z.read(n))).pages) >= 1
        assert any(n.startswith("Hindi Udyog/") and "निविदा" in n for n in names)
        report = z.read("00_Match_Report.csv").decode("utf-8-sig")
        assert "Not Submitted" in report and "Submitted" in report
    # DOCX / XLSX sources really were converted
    assert any(e["method"] in ("libreoffice", "reportlab-fallback") for e in ent)


# ------------------------------------------------------------------ safety
def test_zip_slip_and_cp437(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../../escape.txt", "x")
        zf.writestr("/abs/evil.txt", "x")
        zf.writestr("ok/fine.pdf", "x")
        zf.writestr("A" * 15 + ".pdf", "x")      # placeholder, patched below to raw UTF-8 bytes WITHOUT the UTF-8 flag
    z.write_bytes(z.read_bytes().replace(b"A" * 15 + b".pdf", "अनुभव.pdf".encode("utf-8")))   # same byte length (19)
    dest = tmp_path / "dest"
    rep = safe_extract_zip(z, dest)
    assert not (tmp_path / "escape.txt").exists() and not Path("/abs/evil.txt").exists()
    got = {p.name for p in rep.files}
    assert "fine.pdf" in got and "अनुभव.pdf" in got
    assert rep.warnings


def test_zip_bomb_limit(tmp_path, monkeypatch):
    import tendermatrix.utils as u
    z = tmp_path / "big.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.pdf", b"0" * 3_000_000)
    rep = safe_extract_zip(z, tmp_path / "d", budget=[1_000_000])
    assert any("limit" in w for w in rep.warnings)


# ------------------------------------------------------------------ AI mode (mocked client)
class _Blk:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Blk(text)]


class FakeClient:
    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), 0
        self.messages = self

    def create(self, **kw):
        assert kw["model"] and kw["messages"][0]["role"] == "user"
        self.calls += 1
        return _Resp(self.payloads.pop(0))


def test_llm_mode_with_fake_client(world):
    docs = world["ts"].files
    from tendermatrix.pipeline import read_tender_docs
    scans = scan_paragraphs(build_paragraphs(read_tender_docs(docs, False)))
    payload = "```json\n" + json.dumps({"requirements": [
        {"name_en": "PAN Card", "name_hi": "पैन कार्ड", "category": "Tax & Statutory", "mandatory": True, "status": "active",
         "source": "tender", "reference": "cl 1(d)", "aliases": ["pan", "pan card", "पैन"]},
        {"name_en": "ISO 9001 certificate", "name_hi": "आईएसओ प्रमाणपत्र", "category": "Quality & Compliance", "mandatory": True,
         "status": "deleted", "source": "corrigendum", "reference": "Corr 1", "aliases": ["iso 9001"]},
        {"name_en": "Site photographs", "name_hi": "", "category": "weird", "mandatory": False, "status": "active", "source": "tender",
         "reference": "x", "aliases": ["site photo"]},
    ]}) + "\n```"
    client = FakeClient([payload, payload])   # extraction + consolidation (if multi-chunk)
    reqs = analyze_with_llm(scans, client, "claude-sonnet-5-5")
    assert [r.name for r in reqs][0] == "PAN Card / पैन कार्ड"
    assert reqs[0].cat_id == "pan" and reqs[1].include is False and reqs[2].mandatory == "If applicable"
    assert reqs[2].category == "Other"


def test_parse_json_variants():
    assert parse_json('x {"requirements": []} y') == {"requirements": []}
    assert parse_json('[{"name_en": "a"}]') == {"requirements": [{"name_en": "a"}]}
    with pytest.raises(Exception):
        parse_json("no json here")
