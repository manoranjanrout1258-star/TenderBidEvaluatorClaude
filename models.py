"""Data models shared by the analysis, matching and output modules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

MANDATORY = "Mandatory"
OPTIONAL = "If applicable"

# columns kept in the editable requirement table (internal names are always English)
REQ_COLUMNS = [
    "include", "rid", "name", "mandatory", "category", "reference",
    "source", "confidence", "keywords", "cat_id",
]


@dataclass
class Requirement:
    rid: str
    name: str
    mandatory: str = MANDATORY
    category: str = ""
    reference: str = ""
    source: str = "Tender"          # Tender | Corrigendum | Tender + Corrigendum
    confidence: str = "High"        # High | Medium | Low
    include: bool = True
    keywords: list[str] = field(default_factory=list)
    cat_id: str = ""
    name_en: str = ""
    name_hi: str = ""
    note: str = ""
    pos: tuple = (0, 0, 0)


def split_keywords(s: object) -> list[str]:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return []
    parts = re.split(r"[;|\n,]+", str(s))
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def reqs_to_df(reqs: list[Requirement]) -> pd.DataFrame:
    rows = []
    for r in reqs:
        rows.append({
            "include": bool(r.include),
            "rid": r.rid,
            "name": r.name,
            "mandatory": r.mandatory,
            "category": r.category,
            "reference": r.reference + (f"  [{r.note}]" if r.note else ""),
            "source": r.source,
            "confidence": r.confidence,
            "keywords": "; ".join(r.keywords),
            "cat_id": r.cat_id,
        })
    return pd.DataFrame(rows, columns=REQ_COLUMNS)


def df_to_reqs(df: pd.DataFrame, only_included: bool = True) -> list[Requirement]:
    reqs: list[Requirement] = []
    n_new = 0
    for _, row in df.iterrows():
        name = str(row.get("name") or "").strip()
        if not name or name.lower() == "nan":
            continue
        inc = row.get("include")
        inc = True if inc is None or (isinstance(inc, float) and pd.isna(inc)) else bool(inc)
        if only_included and not inc:
            continue
        rid = str(row.get("rid") or "").strip()
        if not rid or rid.lower() == "nan":
            n_new += 1
            rid = f"U{n_new:03d}"
        mand = str(row.get("mandatory") or MANDATORY)
        if mand not in (MANDATORY, OPTIONAL):
            mand = MANDATORY
        def s(k):
            v = row.get(k)
            return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        reqs.append(Requirement(
            rid=rid, name=name, mandatory=mand, category=s("category"),
            reference=s("reference"), source=s("source") or "Tender",
            confidence=s("confidence") or "High", include=inc,
            keywords=split_keywords(row.get("keywords")), cat_id=s("cat_id"),
        ))
    return reqs
