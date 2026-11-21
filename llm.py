"""Optional AI mode: let Claude read the (relevant parts of the) tender and list the documents.

* The tender is first reduced to the relevant paragraphs with the same scanner the
  offline mode uses (document lists, eligibility clauses, annexure headings, all
  corrigendum text), then split into chunks of ~60k characters.
* Each chunk is analysed separately, a final "consolidation" call merges duplicates and
  applies corrigendum changes (deleted / modified clauses).
* Any failure raises ``LLMError`` - the caller falls back to the offline rules.

The API key is read from Streamlit secrets (``ANTHROPIC_API_KEY``) or typed in the sidebar;
it is never written to disk.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from .catalog import CATALOG, CATEGORIES
from .models import MANDATORY, OPTIONAL, Requirement
from .tender_analysis import Scan, relevant_scans
from .textutil import TextView

DEFAULT_MODEL = "claude-sonnet-5-5"
CHUNK_CHARS = 60_000
MAX_CHUNKS = 12
MAX_PARA_CHARS = 700


class LLMError(Exception):
    pass


SYSTEM = (
    "You are a senior public-procurement officer in India (GeM, CPWD, state e-procurement, PSU tenders). "
    "Tender text may be in English, Hindi (Devanagari) or a mix. You prepare the checklist an evaluation "
    "committee uses to judge the TECHNICAL / ELIGIBILITY bids of bidders. You answer with strict JSON only."
)

SCHEMA_HINT = """{"requirements":[{
  "name_en": "concise English name of the document",
  "name_hi": "same name in Hindi (Devanagari)",
  "category": "one of: %s",
  "mandatory": true,
  "status": "active | deleted",
  "source": "tender | corrigendum",
  "reference": "clause no. / page and file name, <= 120 chars",
  "aliases": ["6-15 short phrases (English, Hindi, Hinglish spellings) likely to appear in the FILE NAME or TITLE of the bidder's document"]
}]}""" % ", ".join(v[0] for v in CATEGORIES.values())

EXTRACT_PROMPT = """Below are extracts of a tender. Every paragraph is tagged [file p.page] and paragraphs from a
CORRIGENDUM / amendment are tagged CORRIGENDUM.

List every DOCUMENT, certificate, form, proof or statement a bidder must submit with the technical / eligibility bid.

Rules
- One entry per distinct document. If a condition is stated (e.g. "turnover of Rs 2 crore"), list the document that proves it
  (e.g. "Annual turnover certificate, CA certified"), not the condition itself.
- Include forms / annexures / formats the bidder must fill and sign.
- Exclude: price / financial bid items, post-award documents (performance guarantee, agreement), bid dates, general clauses.
- mandatory=false only when the tender says "if applicable / optional".
- A corrigendum that deletes or waives a document -> status "deleted"; one that adds -> source "corrigendum".
- Do not invent documents that are not in the text.

Return ONLY JSON in this shape:
%s

TENDER EXTRACTS
%s"""

CONSOLIDATE_PROMPT = """Here are document requirements extracted chunk by chunk from one tender (JSON).
Merge duplicates (the same document asked in several clauses), apply corrigendum changes (drop entries whose final status is
"deleted"; keep a document that a corrigendum re-adds), union the aliases (max 20 per entry), keep name_en / name_hi
short and clear, and order the list logically: fees & security, legal & registration, tax & statutory, financial capacity,
experience, technical, declarations & forms, other.
Return ONLY JSON in the same shape:
%s

INPUT
%s"""


# ------------------------------------------------------------------ helpers
def make_chunks(scans: list[Scan], chunk_chars: int = CHUNK_CHARS, max_chunks: int = MAX_CHUNKS) -> list[str]:
    keep = relevant_scans(scans)

    def line(s: Scan) -> str:
        p = s.para
        tag = f"[{p.src}{' p.' + str(p.page) if p.page else ''}]" + (" CORRIGENDUM" if p.corr else "")
        return f"{tag} {p.text[:MAX_PARA_CHARS]}"

    def pack(lines: list[str]) -> list[str]:
        chunks, cur, size = [], [], 0
        for ln in lines:
            if size + len(ln) > chunk_chars and cur:
                chunks.append("\n".join(cur))
                cur, size = [], 0
            cur.append(ln)
            size += len(ln) + 1
        if cur:
            chunks.append("\n".join(cur))
        return chunks

    base = pack([line(s) for s in keep if not s.para.corr])
    corr = pack([line(s) for s in keep if s.para.corr])
    room = max(1, max_chunks - len(corr))
    return base[:room] + corr


def parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    def _wrap(obj):
        if isinstance(obj, list):
            return {"requirements": obj}
        if isinstance(obj, dict):
            return obj
        raise ValueError("unexpected JSON type")

    try:
        return _wrap(json.loads(t))
    except Exception:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        try:
            return _wrap(json.loads(t[a : b + 1]))
        except Exception:
            pass
    a, b = t.find("["), t.rfind("]")
    if a != -1 and b > a:
        try:
            return {"requirements": json.loads(t[a : b + 1])}
        except Exception:
            pass
    raise LLMError("The AI answer was not valid JSON")


def _reply_text(resp) -> str:
    parts = []
    for blk in getattr(resp, "content", []) or []:
        if getattr(blk, "type", "") == "text":
            parts.append(getattr(blk, "text", ""))
    return "".join(parts)


def _call(client, model: str, prompt: str, max_tokens: int = 8000) -> dict:
    last: Exception | None = None
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=SYSTEM,
                messages=[{"role": "user", "content": prompt if attempt == 0 else
                           prompt + "\n\nIMPORTANT: reply with valid JSON only, no commentary."}],
            )
            return parse_json(_reply_text(resp))
        except LLMError as e:
            last = e
        except Exception as e:  # network, auth, rate limit ...
            raise LLMError(f"{type(e).__name__}: {str(e)[:200]}") from e
    raise last or LLMError("AI call failed")


def make_client(api_key: str):
    try:
        import anthropic
    except ImportError as e:
        raise LLMError("The 'anthropic' package is not installed") from e
    return anthropic.Anthropic(api_key=api_key)


def _category_key(label: str) -> str:
    low = (label or "").strip().lower()
    for key, (en, hi) in CATEGORIES.items():
        if low in (en.lower(), hi.lower(), key):
            return key
    for key, (en, _) in CATEGORIES.items():
        if low and (low in en.lower() or en.lower() in low):
            return key
    return "other"


def _to_requirements(items: list[dict], name_lang: str, ui_lang: str) -> list[Requirement]:
    reqs: list[Requirement] = []
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        en = str(it.get("name_en") or "").strip()
        hi = str(it.get("name_hi") or "").strip()
        if not (en or hi):
            continue
        key = (en or hi).lower()
        if key in seen:
            continue
        seen.add(key)
        aliases = [str(a).strip() for a in (it.get("aliases") or []) if str(a).strip()]
        deleted = str(it.get("status", "active")).lower().startswith("del")
        src = str(it.get("source", "tender")).lower()

        # link to the catalog when it is an unambiguous hit (re-uses exclusion / weak aliases)
        view = TextView(" ".join([en, hi]))
        hits = [c for c in CATALOG.values() if c.find(view)]
        cat_id = hits[0].id if len(hits) == 1 else ""
        keywords = list(dict.fromkeys(aliases + ([en] if en else []) + ([hi] if hi else [])))
        if cat_id:
            keywords = list(dict.fromkeys(keywords + list(CATALOG[cat_id].keywords)))

        if name_lang == "en":
            name = en or hi
        elif name_lang == "hi":
            name = hi or en
        else:
            name = f"{en} / {hi}" if en and hi else (en or hi)
        ckey = _category_key(str(it.get("category", "")))
        mand = it.get("mandatory", True)
        reqs.append(Requirement(
            rid="", name=name, mandatory=MANDATORY if mand in (True, "true", "True", 1) else OPTIONAL,
            category=CATEGORIES[ckey][1 if ui_lang == "hi" else 0],
            reference=str(it.get("reference") or "")[:200],
            source="Corrigendum" if src.startswith("corr") else "Tender",
            confidence="AI", include=not deleted, keywords=keywords, cat_id=cat_id,
            name_en=en, name_hi=hi,
            note="Deleted / waived by corrigendum (AI) - verify" if deleted else "",
            pos=(len(reqs),),
        ))
    for i, r in enumerate(reqs, 1):
        r.rid = f"R{i:03d}"
    return reqs


def analyze_with_llm(
    scans: list[Scan],
    client,
    model: str = DEFAULT_MODEL,
    name_lang: str = "both",
    ui_lang: str = "en",
    progress: Callable[[float, str], None] | None = None,
) -> list[Requirement]:
    chunks = make_chunks(scans)
    if not chunks:
        raise LLMError("No relevant tender text was found to analyse")
    collected: list[dict] = []
    for i, ch in enumerate(chunks):
        if progress:
            progress(0.1 + 0.7 * i / len(chunks), f"AI reading part {i + 1}/{len(chunks)}")
        data = _call(client, model, EXTRACT_PROMPT % (SCHEMA_HINT, ch))
        items = data.get("requirements") or []
        if isinstance(items, list):
            collected.extend(x for x in items if isinstance(x, dict))
    if not collected:
        raise LLMError("The AI returned no requirements")

    final = collected
    if len(chunks) > 1 or any(str(c.get("status", "")).lower().startswith("del") for c in collected):
        if progress:
            progress(0.85, "AI merging duplicates / applying corrigendum")
        try:
            data = _call(client, model, CONSOLIDATE_PROMPT % (SCHEMA_HINT, json.dumps(collected, ensure_ascii=False)),
                         max_tokens=12000)
            merged = data.get("requirements")
            if isinstance(merged, list) and merged:
                final = merged
        except LLMError:
            pass  # keep the un-merged list; names are de-duplicated below
    return _to_requirements(final, name_lang, ui_lang)
