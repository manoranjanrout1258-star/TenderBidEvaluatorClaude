"""Rule-based (offline, free) analysis of tender text -> list of required documents.

The same paragraph scanner is also used to pre-select the relevant parts of a long
tender before it is sent to the AI mode (see llm.py).

How it works
------------
1. Every tender file (PDF/DOCX/XLSX) is split into *paragraphs*; table rows and list
   items are kept as separate paragraphs.
2. Headings such as "Documents required", "Eligibility criteria", "आवश्यक दस्तावेज़" open a
   *window* - the following ~60 paragraphs are treated as a documents list.
3. A paragraph yields a requirement when it mentions a known document type (catalog.py)
   in a *requirement context* (inside a window / list item / table row / near a verb such
   as "submit", "enclose", "प्रस्तुत"), or when it is an "Annexure / Form / प्रपत्र" heading.
4. Corrigendum files are scanned with the same rules; requirements that only appear
   there are marked "Corrigendum", and deletion wording ("stands deleted", "हटा दिया")
   switches a requirement off for the user to verify.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .catalog import CATALOG, CATEGORIES, CatalogItem
from .extract import DocText
from .models import MANDATORY, OPTIONAL, Requirement
from .textutil import TextView, devanagari_ratio, normalize_text, significant_tokens

WINDOW_LEN = 60


# ------------------------------------------------------------------ regex helpers
def _en(words: list[str]) -> str:
    return r"\b(?:" + "|".join(words) + r")\b"


def _hi(phrases: list[str]) -> str:
    return "(?:" + "|".join(re.escape(normalize_text(p)) for p in phrases) + ")"


def _rx(en: list[str], hi: list[str]) -> re.Pattern:
    return re.compile(_en(en) + "|" + _hi(hi))


SECTION_RE = _rx(
    [
        r"documents? required", r"required documents?", r"documents? to be (?:submitted|uploaded|furnished|enclosed|attached|produced)",
        r"documents? (?:for|in support of)", r"list of documents", r"documentary evidence", r"documents? check ?list",
        r"eligibility criteria", r"qualification criteria", r"pre qualification", r"technical (?:bid )?(?:evaluation|qualification|eligibility)",
        r"enclosures?", r"supporting documents?", r"following documents?", r"documents? to be",
        r"(?:bidder|tenderer|firm|vendor|contractor) (?:shall|should|must|has to|have to) (?:submit|upload|furnish|enclose|attach)",
        r"check ?list", r"eligibility conditions?", r"eligibility requirements?", r"qualifying criteria", r"minimum eligibility",
        r"essential documents?", r"mandatory documents?", r"documents? accompanying", r"accompanied by",
    ],
    [
        "आवश्यक दस्तावेज", "अपेक्षित दस्तावेज", "दस्तावेजों की सूची", "प्रस्तुत किए जाने वाले", "प्रस्तुत किये जाने वाले",
        "संलग्न किए जाने", "संलग्न किये जाने", "पात्रता मानदंड", "पात्रता मापदंड", "पात्रता शर्त", "पात्रता की शर्त",
        "योग्यता मानदंड", "योग्यता मापदंड", "तकनीकी मूल्यांकन", "तकनीकी पात्रता", "निम्नलिखित दस्तावेज", "संलग्नक",
        "जांच सूची", "चेकलिस्ट", "दस्तावेजी साक्ष्य", "अनिवार्य दस्तावेज", "सहायक दस्तावेज", "आवश्यक प्रपत्र",
    ],
)

STOP_RE = _rx(
    [r"payment terms", r"scope of work", r"price bid", r"financial bid", r"opening of bids?", r"bid opening",
     r"evaluation of financial", r"liquidated damages", r"force majeure", r"termination", r"general conditions",
     r"special conditions"],
    ["भुगतान की शर्तें", "कार्य का दायरा", "कार्य क्षेत्र", "वित्तीय बिड", "मूल्य बिड", "निविदा खोलना", "विशेष शर्तें", "सामान्य शर्तें"],
)

CUE_RE = _rx(
    [r"submit\w*", r"furnish\w*", r"enclos\w*", r"attach\w*", r"upload\w*", r"documentary", r"evidence", r"proof",
     r"copy", r"copies", r"certificate\w*", r"attested", r"notari[sz]ed", r"must have", r"should have", r"shall have",
     r"must possess", r"should possess", r"needs? to have", r"required", r"require\w*", r"mandatory", r"accompan\w*",
     r"annexure", r"along with", r"valid"],
    ["प्रस्तुत", "संलग्न", "जमा", "अपलोड", "प्रतिलिपि", "प्रमाण", "सत्यापित", "अनिवार्य", "आवश्यक", "देना होगा",
     "देनी होगी", "होना चाहिए", "होनी चाहिए", "साक्ष्य", "नोटरी", "शपथ", "वैध"],
)
VERB_RE = _rx([r"submit\w*", r"furnish\w*", r"enclos\w*", r"attach\w*", r"upload\w*", r"produce"],
              ["प्रस्तुत", "संलग्न", "अपलोड", "जमा"])

DOCISH_RE = _rx(
    [r"copy", r"copies", r"certificates?", r"documents?", r"proof", r"letter", r"statement", r"undertaking", r"declaration",
     r"affidavit", r"licen[cs]es?", r"registration", r"reports?", r"deed", r"agreement", r"forms?", r"annexure", r"format",
     r"receipt", r"evidence", r"attested", r"authori[sz]ation", r"power of attorney", r"balance sheet", r"returns?",
     r"list of", r"details of", r"cv", r"catalog\w*", r"brochure", r"datasheet", r"plan", r"policy", r"invoice", r"orders?",
     r"resolution", r"mandate", r"cheque", r"profile", r"schedule", r"chart", r"drawing", r"clearance", r"noc", r"photograph"],
    ["प्रमाण", "दस्तावेज", "प्रति", "पत्र", "घोषणा", "शपथ", "लाइसेंस", "पंजीकरण", "पंजीयन", "रिपोर्ट", "विलेख", "समझौता",
     "रसीद", "साक्ष्य", "सूची", "विवरण", "प्रपत्र", "अनुबंध", "आदेश", "चेक", "प्रोफाइल", "नक्शा"],
)

OPT_RE = _rx(
    [r"if applicable", r"as applicable", r"wherever applicable", r"optional", r"if any", r"if available",
     r"whichever is applicable", r"in case applicable"],
    ["यदि लागू", "जहां लागू", "वैकल्पिक", "यदि कोई", "यदि उपलब्ध", "लागू होने पर"],
)
DEL_RE = _rx(
    [r"stands? (?:deleted|omitted|removed|withdrawn|cancelled|waived)", r"(?:is|are) (?:hereby )?(?:deleted|omitted|removed|waived)",
     r"deleted", r"omitted", r"no longer (?:required|mandatory)", r"not required", r"need not", r"waived"],
    ["हटा दिया", "हटाया", "हटा", "विलोपित", "निरस्त", "आवश्यक नहीं", "अपेक्षित नहीं", "अनिवार्य नहीं", "समाप्त"],
)
ADD_RE = _rx(
    [r"added", r"inserted?", r"substitut\w*", r"replaced", r"shall read", r"may be read", r"to read as", r"modified", r"amended"],
    ["जोड़", "जोड", "प्रतिस्थापित", "संशोधित", "पढ़ा जाए", "पढ़ें", "पढ़ा जाये"],
)

LEADIN_RE = _rx(
    [r"(?:above|below|following|listed|mentioned|aforesaid) (?:\w+ )?documents?", r"documents? (?:listed|mentioned|given)"],
    ["उपरोक्त दस्तावेज", "निम्नलिखित दस्तावेज", "उक्त दस्तावेज"],
)

LIST_RE = re.compile(
    r"^\s*(?:\(?\d{1,3}[.)]|\d{1,2}(?:\.\d{1,2}){1,3}\.?|\(?[a-zA-Z][.)]|\(?(?:[ivxIVX]{1,5})[.)]|[-•●▪◦■□➢➤✓✔→*]|"
    r"[०-९]{1,3}[.)]|\(?[अ-ह][.)])\s+"
)

ANNEX_A = re.compile(
    r"^\s*(?P<label>annexure|annex|appendix|form|format|schedule|proforma|attachment|exhibit|अनुलग्नक|परिशिष्ट|प्रपत्र|अनुसूची|फॉर्म|फार्म|प्रारूप)"
    r"\s*[-–—.:]?\s*(?P<num>[A-Za-z0-9]{1,6}(?:[-./][A-Za-z0-9]{1,4})?)?"
    r"\s*[:\-–—.)]\s*(?P<title>\S.{5,200})$",
    re.IGNORECASE,
)
ANNEX_B = re.compile(
    r"^\s*(?P<label>annexure|annex|appendix|form|format|proforma|अनुलग्नक|परिशिष्ट|प्रपत्र|प्रारूप)"
    r"[\s\-–—.:]*(?P<num>(?:[0-9]{1,3}|[IVXivx]{1,5}|[A-Za-z])(?:[-./][A-Za-z0-9]{1,4})?)"
    r"\s+(?P<title>[A-Zऀ-ॿ].{5,200})$",
)
STRONG_LABELS = {"annexure", "annex", "appendix", "proforma", "format", "form", "अनुलग्नक", "परिशिष्ट", "प्रपत्र", "प्रारूप", "फॉर्म", "फार्म"}


# ------------------------------------------------------------------ data classes
@dataclass
class TenderDoc:
    name: str
    doc: DocText
    corr: bool = False


@dataclass
class Para:
    text: str
    src: str
    page: int | None
    corr: bool
    order: int
    table_row: bool = False
    list_item: bool = False


@dataclass
class Scan:
    para: Para
    in_window: bool
    head: bool
    cue: bool
    hits: list          # [(CatalogItem, phrase)]
    annex: tuple | None  # (label, num, title)
    deletion: bool
    optional: bool


# ------------------------------------------------------------------ paragraphs
def _titleish(line: str) -> bool:
    words = line.split()
    if not words or len(words) > 9:
        return False
    caps = sum(1 for w in words if w[:1].isalpha() and w[:1].isupper())
    alpha = sum(1 for w in words if w[:1].isalpha())
    return alpha > 0 and caps >= 0.6 * alpha


def _standalone(line: str) -> bool:
    if len(line) > 90 or line.endswith((",", ";", ".", "।")):
        return False
    if line.endswith(":") or line.isupper() or LIST_RE.match(line):
        return True
    if devanagari_ratio(line) > 0.5 and len(line) <= 60:
        return True
    return _titleish(line)


def paragraphs_from_text(text: str, src: str, page: int | None, corr: bool, start: int,
                         join_lines: bool = True) -> list[Para]:
    """Split text into paragraphs. ``join_lines`` re-joins wrapped lines (PDF); DOCX/XLSX
    lines are already complete paragraphs/rows and are kept apart."""
    out: list[Para] = []
    buf: list[str] = []
    flags = {"row": False, "item": False}
    prev_standalone = False

    def flush():
        if buf:
            t = " ".join(buf).strip()
            if t:
                out.append(Para(t, src, page, corr, start + len(out), flags["row"], flags["item"]))
            buf.clear()

    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            flush()
            prev_standalone = False
            continue
        is_row = " | " in line
        is_item = bool(LIST_RE.match(line)) and not is_row
        is_annex = _annex(line) is not None
        if (not join_lines) or is_row or is_item or is_annex or prev_standalone \
                or (buf and buf[-1][-1:] in ".;:।?!"):
            flush()
        if not buf:
            flags["row"], flags["item"] = is_row, is_item
        buf.append(line)
        prev_standalone = is_row or is_annex or _standalone(line)
    flush()
    return out


def build_paragraphs(docs: list[TenderDoc]) -> list[Para]:
    paras: list[Para] = []
    for td in docs:
        pages = td.doc.pages or []
        paged = td.doc.ext == ".pdf"
        for i, ptxt in enumerate(pages):
            paras.extend(paragraphs_from_text(ptxt, td.name, i + 1 if paged else None, td.corr, len(paras),
                                              join_lines=paged))
    return paras


# ------------------------------------------------------------------ scanning
def _clean_title(title: str) -> str:
    t = re.sub(r"[\s.·…_\-]{3,}\s*\d{0,4}\s*$", "", title).strip()
    return t.strip(" :-–—.")


def _annex(text: str):
    if len(text) > 240:
        return None
    m = ANNEX_A.match(text) or ANNEX_B.match(text)
    if not m:
        return None
    title = _clean_title(m.group("title"))
    words = title.split()
    low = title.lower()
    if len(title) < 6 or len(words) < 2 or len(words) > 20:
        return None
    if title.startswith("(") or re.search(r"\b(as per|refer|see |vide|clause|page no)\b", low):
        return None
    label = m.group("label")
    num = (m.groupdict().get("num") or "").strip()
    return label, num, title


def scan_paragraphs(paras: list[Para]) -> list[Scan]:
    scans: list[Scan] = []
    window = 0
    for p in paras:
        n = normalize_text(p.text)
        if len(n) < 3:
            continue
        short = len(p.text) <= 160
        head = bool(SECTION_RE.search(n)) and (short or p.text.rstrip().endswith(":"))
        stop = (not head) and len(p.text) <= 100 and bool(STOP_RE.search(n))
        if stop:
            window = 0
        in_window = window > 0 or head or p.corr
        if head:
            window = WINDOW_LEN
        elif window > 0:
            window -= 1
        view = TextView(n, normalized=True)
        hits = []
        for item in CATALOG.values():
            ph = item.find(view)
            if ph:
                hits.append((item, ph))
        scans.append(Scan(
            para=p, in_window=in_window, head=head, cue=bool(CUE_RE.search(n)), hits=hits,
            annex=_annex(p.text),
            deletion=p.corr and bool(DEL_RE.search(n)) and not ADD_RE.search(n),
            optional=bool(OPT_RE.search(n)),
        ))
    return scans


def relevant_scans(scans: list[Scan]) -> list[Scan]:
    """Paragraphs worth sending to an LLM: windows, cues + doc words, hits, annexures, all corrigendum."""
    keep = []
    for s in scans:
        p = s.para
        if p.corr or s.head or s.annex or s.hits or (s.in_window and (p.list_item or p.table_row)) \
                or (s.cue and DOCISH_RE.search(normalize_text(p.text))):
            keep.append(s)
    return keep


# ------------------------------------------------------------------ requirement building
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
          "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20}
_ROMAN_INV = {v: k for k, v in _ROMAN.items()}
_LABEL_EN = {"अनुलग्नक": "annexure", "परिशिष्ट": "appendix", "प्रपत्र": "form", "अनुसूची": "schedule",
             "फॉर्म": "form", "फार्म": "form", "प्रारूप": "format"}


def label_keywords(label: str, num: str) -> list[str]:
    """'Annexure','III' -> ['annexure iii','annexure 3','annex 3', ...]"""
    if not num:
        return []
    lab = label.strip().lower()
    labs = {lab, _LABEL_EN.get(lab, lab)}
    if "annexure" in labs:
        labs.add("annex")
    nums = {normalize_text(num)}
    low = num.lower()
    if low in _ROMAN:
        nums.add(str(_ROMAN[low]))
    elif low.isdigit() and int(low) in _ROMAN_INV:
        nums.add(_ROMAN_INV[int(low)])
    return [f"{l} {n}" for l in sorted(labs) for n in sorted(nums) if n]


def _snippet(text: str, phrase: str | None = None, width: int = 170) -> str:
    t = " ".join(text.split())
    if len(t) <= width:
        return t
    start = 0
    if phrase:
        idx = t.lower().find(phrase.lower())
        if idx > 40:
            start = max(0, idx - 40)
    s = t[start : start + width].strip()
    return ("…" if start else "") + s + "…"


def _ref(p: Para, phrase: str | None = None, extra: str = "") -> str:
    where = p.src + (f" p.{p.page}" if p.page else "")
    return f"{where}: {_snippet(p.text, phrase)}" + (f" ({extra})" if extra else "")


_LEAD_RE = re.compile(
    r"^(?:(?:the\s+)?(?:bidder|tenderer|firm|vendor|contractor|bidders)\s+(?:shall|should|must|has to|have to|will)\s+"
    r"(?:submit|furnish|upload|enclose|attach|provide|produce)\s+(?:the\s+)?|"
    r"(?:self[\s-]*)?(?:attested\s+)?(?:copy|copies)\s+of\s+(?:the\s+)?)", re.IGNORECASE)


def clean_item_text(text: str, max_len: int = 150) -> str:
    t = " ".join(text.split())
    t = LIST_RE.sub("", t, count=1).strip()
    t = _LEAD_RE.sub("", t).strip(" :;-–—.,")
    t = re.split(r"(?<=[a-zऀ-ॿ\)])[.;।]\s", t, maxsplit=1)[0].strip()
    if len(t) > max_len:
        cut = t[:max_len].rsplit(" ", 1)[0]
        t = cut + "…"
    return t[:1].upper() + t[1:] if t else t


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass
class _Ev:
    scan: Scan
    phrase: str
    ctx: str      # window | cue | annex
    extra: str = ""


def build_requirements(scans: list[Scan], name_lang: str = "both", ui_lang: str = "en") -> list[Requirement]:
    ev: dict[str, list[_Ev]] = defaultdict(list)
    dels: dict[str, list[Scan]] = defaultdict(list)
    generic: list[dict] = []

    for s in scans:
        p = s.para
        if s.head:
            if s.hits:  # e.g. heading "Experience Certificate"
                for item, ph in s.hits:
                    ev[item.id].append(_Ev(s, ph, "window"))
            continue

        if s.deletion and s.hits:
            for item, _ in s.hits:
                dels[item.id].append(s)
            continue

        if s.annex:
            label, num, title = s.annex
            tview = TextView(title)
            a_hits = [(it, it.find(tview)) for it in CATALOG.values() if it.find(tview)]
            if a_hits:
                for it, ph in a_hits:
                    ev[it.id].append(_Ev(s, ph, "annex", f"{label.title()} {num}".strip()))
            else:
                generic.append(dict(
                    name=(f"{label.title()} {num}: " if num else f"{label.title()}: ") + title,
                    core=title, label=label, num=num, scan=s,
                    conf="High" if label.lower() in STRONG_LABELS else "Medium", kind="annex"))
            continue

        ctx_ok = s.in_window or s.cue or p.table_row or p.list_item
        if s.hits:
            if ctx_ok:
                ctx = "window" if (s.in_window or p.table_row or p.list_item) else "cue"
                for item, ph in s.hits:
                    ev[item.id].append(_Ev(s, ph, ctx))
            continue

        # no catalog hit -> generic list item
        n = normalize_text(p.text)
        if not (8 <= len(p.text) <= 300) or not DOCISH_RE.search(n):
            continue
        if s.in_window and (p.list_item or p.table_row):
            row_text = p.text
            if p.table_row:
                cells = [c.strip() for c in p.text.split(" | ")]
                if cells and re.fullmatch(r"[\d.()a-zA-Z०-९]{1,6}", cells[0] or ""):
                    cells = cells[1:]
                if not cells or re.search(r"\b(s\.? ?no|sr\.? ?no|description|particulars|remarks|document name)\b", normalize_text(cells[0])) \
                        or normalize_text(cells[0]) in ("क्र सं", "विवरण", "क्रमांक", "दस्तावेज"):
                    continue
                row_text = max(cells[:2], key=len)
            generic.append(dict(name=clean_item_text(row_text), core=clean_item_text(row_text), label="", num="",
                                scan=s, conf="High" if p.table_row or p.list_item else "Medium", kind="list"))
        elif s.cue and VERB_RE.search(n) and len(p.text) <= 260 and not LEADIN_RE.search(n) \
                and not p.text.rstrip().endswith(":"):
            generic.append(dict(name=clean_item_text(p.text), core=clean_item_text(p.text), label="", num="",
                                scan=s, conf="Low", kind="cue"))

    reqs: list[Requirement] = []

    # ---- catalog based
    for cid, evs in ev.items():
        item = CATALOG[cid]
        high = any(e.ctx in ("window", "annex") for e in evs)
        n_cue = sum(e.ctx == "cue" for e in evs)
        conf = "High" if high else ("Medium" if n_cue >= 2 else "Low")
        corr_ev = [e for e in evs if e.scan.para.corr]
        base_ev = [e for e in evs if not e.scan.para.corr]
        source = "Tender + Corrigendum" if corr_ev and base_ev else ("Corrigendum" if corr_ev else "Tender")
        mandatory = OPTIONAL if all(e.scan.optional for e in evs) else MANDATORY
        best = sorted(evs, key=lambda e: (e.ctx != "annex", e.ctx != "window"))[0]
        refs = [_ref(best.scan.para, best.phrase, best.extra)]
        for e in evs:
            if e is not best and e.scan.para.src != best.scan.para.src:
                refs.append(_ref(e.scan.para, e.phrase, e.extra))
                break
        note, include = "", conf in ("High", "Medium")
        if cid in dels and not corr_ev:
            note, include = "Corrigendum may DELETE / waive this - please verify", False
        name = {"en": item.en, "hi": item.hi}.get(name_lang, f"{item.en} / {item.hi}")
        reqs.append(Requirement(
            rid="", name=name, mandatory=mandatory, category=item.category_label(ui_lang),
            reference="  ‖  ".join(refs), source=source, confidence=conf, include=include,
            keywords=list(item.keywords), cat_id=item.id, name_en=item.en, name_hi=item.hi,
            note=note, pos=(min(e.scan.para.order for e in evs),),
        ))

    # ---- generic items (deduplicated)
    kept: list[tuple[set[str], Requirement]] = []
    for g in sorted(generic, key=lambda g: g["scan"].para.order):
        key = set(significant_tokens(g["core"], 2))
        if not key:
            continue
        dup = next((r for k, r in kept if _jaccard(k, key) >= 0.8), None)
        s = g["scan"]
        if dup is not None:
            if s.para.corr and "Corrigendum" not in dup.source:
                dup.source = "Tender + Corrigendum"
            continue
        kws = [g["core"]] + label_keywords(g["label"], g["num"])
        r = Requirement(
            rid="", name=g["name"], mandatory=OPTIONAL if s.optional else MANDATORY,
            category=CATEGORIES["declaration"][1 if ui_lang == "hi" else 0] if g["kind"] == "annex"
            else CATEGORIES["other"][1 if ui_lang == "hi" else 0],
            reference=_ref(s.para), source="Corrigendum" if s.para.corr else "Tender",
            confidence=g["conf"], include=g["conf"] in ("High", "Medium"),
            keywords=kws, cat_id="", pos=(s.para.order,),
        )
        kept.append((key, r))
        reqs.append(r)

    # cap noisy low-confidence generics
    lows = [r for r in reqs if r.confidence == "Low" and not r.cat_id]
    for r in lows[40:]:
        reqs.remove(r)

    reqs.sort(key=lambda r: r.pos)
    for i, r in enumerate(reqs, 1):
        r.rid = f"R{i:03d}"
    return reqs


def analyze_rule_based(docs: list[TenderDoc], name_lang: str = "both", ui_lang: str = "en") -> list[Requirement]:
    paras = build_paragraphs(docs)
    scans = scan_paragraphs(paras)
    return build_requirements(scans, name_lang=name_lang, ui_lang=ui_lang)
