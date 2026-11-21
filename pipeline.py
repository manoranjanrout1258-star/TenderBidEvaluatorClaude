"""High-level steps used by the Streamlit UI (kept free of any Streamlit import so they can be tested)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .bidders import BidderSet, TenderFile
from .extract import ExtractOptions, extract_any
from .llm import DEFAULT_MODEL, LLMError, analyze_with_llm, make_client
from .matching import FileFeat, FuzzyVocab, index_bidders
from .models import Requirement
from .tender_analysis import TenderDoc, build_paragraphs, build_requirements, scan_paragraphs

Progress = Callable[[float, str], None]


@dataclass
class AnalysisOutcome:
    reqs: list[Requirement]
    mode: str                                  # rules | ai
    warnings: list[str] = field(default_factory=list)
    n_docs: int = 0
    unreadable: list[str] = field(default_factory=list)


def read_tender_docs(files: list[TenderFile], ocr: bool, progress: Progress | None = None) -> list[TenderDoc]:
    opts = ExtractOptions(max_pages=400, max_chars=1_500_000, ocr=ocr, ocr_pages=25)
    docs: list[TenderDoc] = []
    for i, tf in enumerate(files):
        if progress:
            progress(0.05 + 0.45 * i / max(len(files), 1), f"Reading {tf.path.name}")
        docs.append(TenderDoc(name=tf.path.name, doc=extract_any(tf.path, opts), corr=tf.corrigendum))
    # main tender first, corrigendum last (so corrigendum-only requirements come last)
    docs.sort(key=lambda d: d.corr)
    return docs


def analyze_tender(
    files: list[TenderFile],
    *,
    use_ai: bool = False,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    ocr: bool = False,
    name_lang: str = "both",
    ui_lang: str = "en",
    progress: Progress | None = None,
    client=None,
) -> AnalysisOutcome:
    docs = read_tender_docs(files, ocr, progress)
    out = AnalysisOutcome(reqs=[], mode="rules", n_docs=len(docs))
    for d in docs:
        if d.doc.method in ("none", "error"):
            out.unreadable.append(f"{d.name}: {d.doc.warning}")
    if progress:
        progress(0.55, "Scanning tender text ...")
    scans = scan_paragraphs(build_paragraphs(docs))
    if not scans:
        out.warnings.append("No readable text found in the tender files (scanned PDFs? enable OCR in the sidebar).")

    if use_ai and (api_key or client is not None):
        try:
            client = client or make_client(api_key)
            out.reqs = analyze_with_llm(scans, client, model, name_lang, ui_lang, progress)
            out.mode = "ai"
        except LLMError as e:
            out.warnings.append(f"AI mode failed ({e}); offline rules were used instead.")
    if not out.reqs:
        out.reqs = build_requirements(scans, name_lang=name_lang, ui_lang=ui_lang)
    if progress:
        progress(1.0, "Done")
    return out


def index_bidder_set(
    bs: BidderSet,
    vocab: FuzzyVocab | None,
    ocr: bool,
    progress: Callable[[float, str], None] | None = None,
) -> dict[str, list[FileFeat]]:
    opts = ExtractOptions(max_pages=60, ocr=ocr, ocr_pages=3)
    return index_bidders(
        bs.bidders, bs.roots, opts, vocab,
        progress=(lambda d, t, m: progress(d / max(t, 1), m)) if progress else None,
    )
