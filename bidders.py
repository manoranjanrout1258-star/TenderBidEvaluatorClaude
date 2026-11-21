"""Turn uploaded files / ZIP archives into (a) tender files and (b) bidder -> files maps."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .textutil import normalize_text
from .utils import (
    SUPPORTED_EXTS, ExtractReport, list_files, safe_extract_zip, sanitize_filename,
    split_supported, unique_path,
)

CORR_RE = re.compile(
    r"corrigend|addend|amendment|amended|shuddhi|शुद्धिपत्र|शुद्धि पत्र|संशोधन|संशोधित|revised notice|corr[\s_-]?\d",
    re.IGNORECASE,
)

MODES = ("auto", "zip_per_bidder", "folder_per_bidder")

_CATEGORY_WORDS = {
    "technical", "tech", "financial", "fin", "commercial", "experience", "certificate", "certificates", "document",
    "documents", "docs", "annexure", "annexures", "form", "forms", "statutory", "eligibility", "legal", "registration",
    "emd", "fee", "price", "bid", "boq", "drawings", "specification", "specifications", "compliance", "tax", "bank",
    "pan", "gst", "part", "volume", "vol", "cover", "envelope", "section", "appendix", "tender", "qualification",
    "तकनीकी", "वित्तीय", "दस्तावेज", "प्रमाण", "अनुलग्नक", "प्रपत्र", "पात्रता", "अनुभव", "वाणिज्यिक",
}


@dataclass
class TenderFile:
    path: Path
    rel: str
    corrigendum: bool
    size: int


@dataclass
class TenderSet:
    files: list[TenderFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


@dataclass
class BidderSet:
    root: Path
    bidders: dict[str, list[Path]] = field(default_factory=dict)
    roots: dict[str, Path] = field(default_factory=dict)       # bidder -> folder its files live under
    warnings: list[str] = field(default_factory=list)
    unsupported: dict[str, list[str]] = field(default_factory=dict)
    modes: dict[str, str] = field(default_factory=dict)        # bidder -> how it was detected


def is_corrigendum(rel: str) -> bool:
    return bool(CORR_RE.search(rel))


# --------------------------------------------------------------------------- tender
def unpack_tender(saved: list[Path], root: Path) -> TenderSet:
    ts = TenderSet()
    for i, p in enumerate(saved):
        if p.suffix.lower() == ".zip":
            dest = root / f"{i + 1:02d}_{sanitize_filename(p.stem, 60)}"
            rep = safe_extract_zip(p, dest)
            ts.warnings.extend(rep.warnings)
            base = dest
        else:
            dest = root / f"{i + 1:02d}_files"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, unique_path(dest / p.name))
            base = dest
        files = list_files(base)
        ok, bad = split_supported(files)
        ts.unsupported.extend(f.name for f in bad)
        for f in ok:
            rel = f.relative_to(root).as_posix()
            ts.files.append(TenderFile(f, rel, is_corrigendum(rel), f.stat().st_size))
    return ts


# -------------------------------------------------------------------------- bidders
def _unwrap(d: Path) -> Path:
    """Descend while the folder holds exactly one sub-folder and nothing else."""
    while True:
        entries = [e for e in d.iterdir() if not e.name.startswith(".")]
        if len(entries) == 1 and entries[0].is_dir():
            d = entries[0]
        else:
            return d


def _looks_like_category(name: str) -> bool:
    toks = set(normalize_text(name).split())
    return bool(toks & _CATEGORY_WORDS)


def _clean_name(stem: str) -> str:
    n = re.sub(r"[_]+", " ", stem)
    n = re.sub(r"\s+", " ", n).strip(" -.")
    return n or "Bidder"


def _unique_name(name: str, taken: dict) -> str:
    if name not in taken:
        return name
    i = 2
    while f"{name} ({i})" in taken:
        i += 1
    return f"{name} ({i})"


def _add(bs: BidderSet, name: str, folder: Path, how: str) -> None:
    files = list_files(folder)
    ok, bad = split_supported(files)
    if not ok and not bad:
        bs.warnings.append(f"'{name}': no files found")
        return
    name = _unique_name(name, bs.bidders)
    bs.bidders[name] = ok
    bs.roots[name] = folder
    bs.modes[name] = how
    if bad:
        bs.unsupported[name] = [f.name for f in bad]


def unpack_bidders(saved: list[Path], root: Path, mode: str = "auto") -> BidderSet:
    """
    mode:
      zip_per_bidder    every uploaded ZIP is one bidder (name = ZIP file name)
      folder_per_bidder every top-level folder inside a ZIP is one bidder
      auto              decide per ZIP: nested ZIPs / several bidder-like folders -> folders, else one bidder
    Loose (non-ZIP) uploads are grouped into one bidder called "Loose files".
    """
    bs = BidderSet(root=root)
    loose: list[Path] = []
    for i, p in enumerate(saved):
        if p.suffix.lower() != ".zip":
            loose.append(p)
            continue
        dest = root / f"{i + 1:02d}_{sanitize_filename(p.stem, 60)}"
        rep: ExtractReport = safe_extract_zip(p, dest)
        bs.warnings.extend(rep.warnings)
        top = _unwrap(dest)
        stem_name = _clean_name(p.stem)

        use_folders = False
        if mode == "folder_per_bidder":
            use_folders = True
        elif mode == "auto":
            subdirs = [e for e in top.iterdir() if e.is_dir()]
            root_files = [e for e in top.iterdir() if e.is_file()]
            nested_dirs = [d for d in rep.zip_dirs if d.parent == top]
            if len(nested_dirs) >= 2:
                use_folders = True
            elif len(subdirs) >= 2 and len(root_files) <= 1 and not all(_looks_like_category(d.name) for d in subdirs) \
                    and not any(_looks_like_category(d.name) for d in subdirs):
                use_folders = True

        if use_folders:
            subdirs = sorted([e for e in top.iterdir() if e.is_dir()], key=lambda e: e.name.lower())
            for d in subdirs:
                _add(bs, _clean_name(d.name), d, f"folder in {p.name}")
            root_files = [e for e in top.iterdir() if e.is_file() and e.suffix.lower() in SUPPORTED_EXTS]
            if root_files:
                _add_loose(bs, f"{stem_name} (root files)", top, root_files, f"root files of {p.name}")
        else:
            _add(bs, stem_name, top, f"ZIP {p.name}")

    if loose:
        d = root / "loose_files"
        d.mkdir(parents=True, exist_ok=True)
        copies = []
        for f in loose:
            t = unique_path(d / f.name)
            shutil.copy2(f, t)
            copies.append(t)
        ok = [c for c in copies if c.suffix.lower() in SUPPORTED_EXTS]
        if ok:
            name = _unique_name("Loose files", bs.bidders)
            bs.bidders[name], bs.roots[name], bs.modes[name] = ok, d, "uploaded files"
    return bs


def _add_loose(bs: BidderSet, name: str, folder: Path, files: list[Path], how: str) -> None:
    name = _unique_name(name, bs.bidders)
    bs.bidders[name], bs.roots[name], bs.modes[name] = files, folder, how


def rename_bidders(bs: BidderSet, new_names: dict[str, str]) -> BidderSet:
    """Return a copy of ``bs`` with user-edited display names (old -> new), names kept unique."""
    out = BidderSet(root=bs.root, warnings=list(bs.warnings))
    for old, files in bs.bidders.items():
        new = (new_names.get(old) or old).strip() or old
        new = _unique_name(new, out.bidders)
        out.bidders[new], out.roots[new], out.modes[new] = files, bs.roots[old], bs.modes[old]
        if old in bs.unsupported:
            out.unsupported[new] = bs.unsupported[old]
    return out
