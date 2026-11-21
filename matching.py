"""Match bidder files against the wanting-document list.

A requirement is satisfied for a bidder ("Submitted") when at least one of the bidder's
files scores >= threshold. Score sources, strongest first:

* file / folder name contains a requirement phrase           (0.85 - 0.92)
* first-page text of the file contains a requirement phrase   (0.78 - 0.85)
* weak (generic) phrases in the name / first page            (0.50 - 0.58 -> "possible", review manually)
* keyword coverage for user-written or Annexure requirements (up to 0.90)
* phrase somewhere in the body text                           (max 0.55 -> "possible" only)

File names are fuzzy-corrected against the keyword vocabulary, so typing mistakes such
as "experiance" or "certficate" still match. Hindi phrases are compared with spelling
variants unified and (for longer phrases) with spaces ignored.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .catalog import CATALOG
from .extract import DocText, ExtractOptions, extract_any
from .models import MANDATORY, Requirement
from .textutil import TextView, normalize_text, significant_tokens

try:  # optional speed-up
    from rapidfuzz.fuzz import ratio as _rf_ratio

    def _sim(a: str, b: str) -> float:
        return _rf_ratio(a, b) / 100.0
except Exception:  # pragma: no cover - fallback path
    from difflib import SequenceMatcher

    def _sim(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

BODY_CHARS = 60_000
MAX_FILES_PER_CELL = 12
CAND_MIN = 0.35


# --------------------------------------------------------------------- data classes
@dataclass
class FileFeat:
    bidder: str
    path: Path
    rel: str
    name_view: TextView
    name_tokens: frozenset
    title_view: TextView
    title_tokens: frozenset
    body_view: TextView
    method: str = "text"
    warning: str = ""

    @property
    def readable(self) -> bool:
        return self.method in ("text", "ocr")


@dataclass
class ReqSpec:
    rid: str
    name: str
    mandatory: str
    phrases: list[str]
    weak: list[str]
    excl: list[str]
    sig: list[str]


@dataclass
class Match:
    rel: str
    score: float
    how: str
    manual: bool = False


@dataclass
class MatchResult:
    bidders: list[str]
    specs: list[ReqSpec]
    threshold: float
    cells: dict[tuple[str, str], list[Match]] = field(default_factory=dict)
    cands: dict[tuple[str, str], list[Match]] = field(default_factory=dict)
    unmatched: dict[str, list[str]] = field(default_factory=dict)
    paths: dict[tuple[str, str], Path] = field(default_factory=dict)   # (bidder, rel) -> file
    unreadable: dict[str, list[str]] = field(default_factory=dict)

    def status(self, rid: str, bidder: str) -> str:
        return "Submitted" if self.cells.get((rid, bidder)) else "Not Submitted"

    def counts(self, bidder: str) -> tuple[int, int, int]:
        """(submitted, not_submitted, mandatory_missing)"""
        sub = nsub = miss = 0
        for sp in self.specs:
            if self.status(sp.rid, bidder) == "Submitted":
                sub += 1
            else:
                nsub += 1
                if sp.mandatory == MANDATORY:
                    miss += 1
        return sub, nsub, miss

    def set_manual(self, rid: str, bidder: str, rels: list[str]) -> None:
        if rels:
            self.cells[(rid, bidder)] = [Match(r, 1.0, "manual selection", True) for r in rels]
        else:
            self.cells.pop((rid, bidder), None)
        self.recompute_unmatched()

    def recompute_unmatched(self) -> None:
        used: dict[str, set[str]] = defaultdict(set)
        for (rid, b), ms in self.cells.items():
            for m in ms:
                used[b].add(m.rel)
        for b in self.bidders:
            allrels = [rel for (bb, rel) in self.paths if bb == b]
            self.unmatched[b] = [r for r in allrels if r not in used[b]]


# ------------------------------------------------------------------------- vocab
class FuzzyVocab:
    """Map slightly misspelt Latin words to the nearest keyword word."""

    def __init__(self, words):
        self.words = {w for w in words if len(w) >= 5 and w.isascii()}
        self.buckets: dict[tuple[str, int], list[str]] = defaultdict(list)
        for w in self.words:
            self.buckets[(w[0], len(w))].append(w)
        self._cache: dict[str, str] = {}

    def canon(self, tok: str) -> str:
        if tok in self._cache:
            return self._cache[tok]
        out = tok
        if len(tok) >= 5 and tok.isascii() and tok not in self.words:
            best, best_r = None, 0.0
            for dl in (-2, -1, 0, 1, 2):
                for cand in self.buckets.get((tok[0], len(tok) + dl), ()):
                    r = _sim(tok, cand)
                    if r > best_r:
                        best, best_r = cand, r
            if best is not None and best_r >= 0.85:
                out = best
        self._cache[tok] = out
        return out


def build_vocab(specs: list[ReqSpec]) -> FuzzyVocab:
    words: set[str] = set()
    for sp in specs:
        for ph in sp.phrases + sp.weak:
            words.update(ph.split())
    return FuzzyVocab(words)


# ------------------------------------------------------------------ compile specs
def _name_segments(name: str) -> list[str]:
    import re

    segs = re.split(r"\s+/\s+|\s*\|\s*|[()\[\]:]|\s+[-–—]\s+", name)
    out = []
    for sgm in segs:
        n = normalize_text(sgm)
        toks = n.split()
        if len(toks) >= 2 or (len(toks) == 1 and len(toks[0]) >= 4):
            if len(toks) <= 10:
                out.append(n)
    return out


def compile_specs(reqs: list[Requirement]) -> list[ReqSpec]:
    specs: list[ReqSpec] = []
    for r in reqs:
        item = CATALOG.get(r.cat_id) if r.cat_id else None
        kws = list(dict.fromkeys(n for n in (normalize_text(k) for k in r.keywords) if n))
        weak: list[str] = []
        excl: list[str] = []
        sig: list[str] = []
        if item is not None:
            if not kws:
                kws = list(item.strong)
            weak, excl = list(item.weak), list(item.excl)
        else:
            for ph in _name_segments(r.name):
                if ph not in kws:
                    kws.append(ph)
            sig = significant_tokens(r.name)
            if len(sig) > 8:
                sig = sig[:8]
        specs.append(ReqSpec(r.rid, r.name, r.mandatory, kws, weak, excl, sig))
    return specs


# ---------------------------------------------------------------------- indexing
def build_feat(bidder: str, path: Path, rel: str, doc: DocText, vocab: FuzzyVocab | None) -> FileFeat:
    stem_rel = rel.rsplit(".", 1)[0] if "." in rel else rel
    name_norm = normalize_text(stem_rel)
    toks = name_norm.split()
    if vocab is not None:
        toks = [vocab.canon(t) for t in toks]
    name_view = TextView(" ".join(toks), normalized=True)
    title = doc.title_text
    title_norm = normalize_text(title)
    body_norm = normalize_text(doc.text[: BODY_CHARS * 2])[:BODY_CHARS]
    ttoks = title_norm.split()
    if vocab is not None:
        ttoks = [vocab.canon(t) for t in ttoks[:150]]
    return FileFeat(
        bidder=bidder, path=path, rel=rel,
        name_view=name_view, name_tokens=frozenset(toks),
        title_view=TextView(title_norm, normalized=True), title_tokens=frozenset(ttoks),
        body_view=TextView(body_norm, normalized=True),
        method=doc.method, warning=doc.warning,
    )


def index_bidders(
    bidders: dict[str, list[Path]],
    roots: dict[str, Path],
    opts: ExtractOptions,
    vocab: FuzzyVocab | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, list[FileFeat]]:
    total = sum(len(v) for v in bidders.values())
    done = 0
    out: dict[str, list[FileFeat]] = {}
    for b, files in bidders.items():
        feats = []
        root = roots[b]
        for f in files:
            try:
                rel = f.relative_to(root).as_posix()
            except ValueError:
                rel = f.name
            doc = extract_any(f, opts)
            feats.append(build_feat(b, f, rel, doc, vocab))
            done += 1
            if progress:
                progress(done, total, f"{b}: {f.name}")
        out[b] = feats
    return out


def refeat(feats: dict[str, list[FileFeat]], vocab: FuzzyVocab) -> None:
    """Re-canonicalise file-name tokens after the keyword vocabulary changed."""
    for fl in feats.values():
        for ft in fl:
            toks = [vocab.canon(t) for t in ft.name_view.norm.split()]
            ft.name_view = TextView(" ".join(toks), normalized=True)
            ft.name_tokens = frozenset(toks)


# ----------------------------------------------------------------------- scoring
def _strength(ph: str) -> str:
    return "long" if (" " in ph or len(ph) >= 6) else "short"


def score_pair(spec: ReqSpec, ft: FileFeat) -> tuple[float, str]:
    nv = ft.name_view.without(spec.excl) if spec.excl else ft.name_view
    tv = ft.title_view.without(spec.excl) if spec.excl else ft.title_view
    bv = ft.body_view.without(spec.excl) if spec.excl else ft.body_view

    best, how = 0.0, ""
    name_s = title_s = body_s = 0.0

    def upd(cur: float, new: float, label: str):
        nonlocal how, best
        if new > cur:
            cur = new
        if new > best:
            best, how = new, label
        return cur

    for ph in spec.phrases:
        st = _strength(ph)
        if nv.has(ph):
            name_s = upd(name_s, 0.92 if st == "long" else 0.85, f"file name: '{ph}'")
        if tv.has(ph):
            title_s = upd(title_s, 0.85 if st == "long" else 0.78, f"first page: '{ph}'")
        else:
            n = bv.count(ph)
            if n:
                if " " in ph:
                    sc = min(0.55, 0.30 + 0.08 * n)
                elif st == "long":
                    sc = min(0.50, 0.25 + 0.07 * n)
                else:
                    sc = min(0.40, 0.20 + 0.05 * n)
                body_s = upd(body_s, sc, f"text body: '{ph}' x{n}")
    for ph in spec.weak:
        if nv.has(ph):
            name_s = upd(name_s, 0.58, f"file name (generic): '{ph}'")
        elif tv.has(ph):
            title_s = upd(title_s, 0.50, f"first page (generic): '{ph}'")

    if spec.sig:
        n_sig = len(spec.sig)
        sset = set(spec.sig)
        cov_n = len(sset & ft.name_tokens) / n_sig
        cov_t = len(sset & ft.title_tokens) / n_sig
        if n_sig >= 2:
            if cov_n >= 0.75:
                name_s = upd(name_s, 0.55 + 0.35 * cov_n, f"file name keywords {cov_n:.0%}")
            if cov_t >= 0.75:
                title_s = upd(title_s, 0.50 + 0.30 * cov_t, f"first page keywords {cov_t:.0%}")
        else:
            if cov_n >= 1:
                name_s = upd(name_s, 0.70, f"file name keyword '{spec.sig[0]}'")
            if cov_t >= 1:
                title_s = upd(title_s, 0.60, f"first page keyword '{spec.sig[0]}'")

    if name_s and (title_s or body_s):
        best = min(1.0, best + 0.05)
    return best, how


def match_all(
    feats: dict[str, list[FileFeat]],
    specs: list[ReqSpec],
    threshold: float = 0.6,
    progress: Callable[[int, int], None] | None = None,
) -> MatchResult:
    bidders = list(feats.keys())
    res = MatchResult(bidders=bidders, specs=specs, threshold=threshold)
    total = sum(len(v) for v in feats.values())
    done = 0
    for b in bidders:
        used: set[str] = set()
        unreadable: list[str] = []
        per_req: dict[str, list[Match]] = defaultdict(list)
        per_cand: dict[str, list[Match]] = defaultdict(list)
        for ft in feats[b]:
            res.paths[(b, ft.rel)] = ft.path
            if not ft.readable:
                unreadable.append(ft.rel)
            for sp in specs:
                sc, how = score_pair(sp, ft)
                if sc >= threshold:
                    per_req[sp.rid].append(Match(ft.rel, round(sc, 3), how))
                    used.add(ft.rel)
                elif sc >= CAND_MIN:
                    per_cand[sp.rid].append(Match(ft.rel, round(sc, 3), how))
            done += 1
            if progress and done % 20 == 0:
                progress(done, total)
        for rid, ms in per_req.items():
            ms.sort(key=lambda m: -m.score)
            res.cells[(rid, b)] = ms[:MAX_FILES_PER_CELL]
        for rid, ms in per_cand.items():
            ms.sort(key=lambda m: -m.score)
            res.cands[(rid, b)] = ms[:5]
        res.unmatched[b] = [ft.rel for ft in feats[b] if ft.rel not in used]
        res.unreadable[b] = unreadable
    if progress:
        progress(total, total)
    return res
