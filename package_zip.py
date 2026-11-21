"""Build the output ZIP: <Bidder>/<NN>_<Requirement>__<original name>.pdf for every Submitted document."""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Callable

from .matching import MatchResult
from .models import Requirement
from .pdf_convert import convert_to_pdf
from .textutil import has_devanagari
from .utils import sanitize_filename


def short_req_name(name: str, max_len: int = 55) -> str:
    """'OEM / Manufacturer Authorization Certificate (MAF) / निर्माता ...' -> 'OEM - Manufacturer Authorization Certificate'"""
    segs = [s.strip() for s in name.split(" / ") if s.strip()] or [name]
    latin = [s for s in segs if not has_devanagari(s)]
    chosen = latin[:2] if latin else segs[:1]
    cleaned = []
    for s in chosen:
        s = re.sub(r"\s*\([^)]*\)", "", s).strip() or s
        cleaned.append(s)
    return sanitize_filename(" - ".join(cleaned), max_len)


def plan_entries(reqs: list[Requirement], result: MatchResult) -> list[dict]:
    """One dict per (bidder, requirement, file) that is Submitted."""
    entries = []
    for b in result.bidders:
        for i, r in enumerate(reqs, 1):
            for m in result.cells.get((r.rid, b), []):
                src = result.paths.get((b, m.rel))
                if src is None:
                    continue
                entries.append(dict(bidder=b, idx=i, rid=r.rid, req=r.name, rel=m.rel, src=src,
                                    score=m.score, how=m.how))
    return entries


def build_output_zip(
    reqs: list[Requirement],
    result: MatchResult,
    out_path: Path,
    work_dir: Path,
    extras: dict[str, bytes] | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> list[dict]:
    """Write the ZIP to ``out_path`` and return the entry list (also used for the preview table)."""
    entries = plan_entries(reqs, result)
    need_convert = sorted({e["src"] for e in entries if e["src"].suffix.lower() != ".pdf"}, key=str)
    conv: dict[Path, tuple[Path | None, str]] = {}
    if need_convert:
        if progress:
            progress(0.05, f"Converting {len(need_convert)} file(s) to PDF ...")
        conv = convert_to_pdf(
            need_convert, work_dir / "pdf_cache",
            progress=lambda d, t: progress(0.05 + 0.6 * d / max(t, 1), f"Converting to PDF {d}/{t}") if progress else None,
        )

    used: set[str] = set()
    folders: dict[str, str] = {}

    def folder_for(b: str) -> str:
        if b not in folders:
            base = sanitize_filename(b, 80)
            name, i = base, 2
            while name.lower() in {v.lower() for v in folders.values()}:
                name, i = f"{base} ({i})", i + 1
            folders[b] = name
        return folders[b]

    def arc_unique(arc: str) -> str:
        if arc.lower() not in used:
            used.add(arc.lower())
            return arc
        stem, dot, ext = arc.rpartition(".")
        i = 2
        while f"{stem} ({i}).{ext}".lower() in used:
            i += 1
        out = f"{stem} ({i}).{ext}"
        used.add(out.lower())
        return out

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as zf:
        n = max(len(entries), 1)
        for k, e in enumerate(entries):
            src: Path = e["src"]
            stem = sanitize_filename(src.stem, 70)
            prefix = f"{folder_for(e['bidder'])}/{e['idx']:02d}_{short_req_name(e['req'])}__{stem}"
            if src.suffix.lower() == ".pdf":
                pdf, method, note = src, "original pdf", ""
                arc = arc_unique(prefix + ".pdf")
            else:
                pdf, method = conv.get(src, (None, "failed"))
                if pdf is not None:
                    arc, note = arc_unique(prefix + ".pdf"), ""
                    if method == "reportlab-fallback":
                        note = "converted without LibreOffice - formatting simplified"
                else:
                    pdf = src
                    arc = arc_unique(prefix + src.suffix.lower())
                    note = "PDF conversion failed - original file included"
            try:
                zf.write(pdf, arc)
            except OSError as ex:
                note, arc = f"could not add file ({type(ex).__name__})", ""
            e.update(arc=arc, method=method, note=note)
            if progress and (k % 5 == 0 or k == len(entries) - 1):
                progress(0.65 + 0.3 * (k + 1) / n, f"Packing {k + 1}/{len(entries)}")

        zf.writestr(f"00_Match_Report.csv", _report_csv(reqs, result, entries))
        for name, data in (extras or {}).items():
            zf.writestr(name, data)
    if progress:
        progress(1.0, "Done")
    return entries


def _report_csv(reqs: list[Requirement], result: MatchResult, entries: list[dict]) -> bytes:
    by_cell: dict[tuple[str, str], list[dict]] = {}
    for e in entries:
        by_cell.setdefault((e["rid"], e["bidder"]), []).append(e)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Bidder", "S.No.", "Wanting document", "Type", "Status", "Uploaded file", "File in ZIP",
                "Score", "Match basis", "Conversion", "Note"])
    for b in result.bidders:
        for i, r in enumerate(reqs, 1):
            es = by_cell.get((r.rid, b), [])
            if not es:
                w.writerow([b, i, r.name, r.mandatory, "Not Submitted", "", "", "", "", "", ""])
            for e in es:
                w.writerow([b, i, r.name, r.mandatory, "Submitted", e["rel"], e.get("arc", ""), e["score"],
                            e["how"], e.get("method", ""), e.get("note", "")])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM -> Excel opens Hindi correctly
