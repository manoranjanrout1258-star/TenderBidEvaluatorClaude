"""File-system helpers: safe ZIP extraction, upload saving, sizes."""
from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

DOC_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xlsm", ".xls"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
SUPPORTED_EXTS = DOC_EXTS | IMG_EXTS

_JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}

MAX_UNCOMPRESSED_BYTES = 4 * 1024 ** 3     # zip-bomb protection (total, all nested zips)
MAX_FILES_PER_ZIP = 30_000
MAX_NEST_DEPTH = 3


def human_size(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def sanitize_filename(name: str, max_len: int = 150) -> str:
    """Make a string safe to use as a single path component (keeps Hindi etc.)."""
    name = unicodedata.normalize("NFC", str(name))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = "file"
    if len(name) > max_len:
        stem, ext = os.path.splitext(name)
        ext = ext[:10]
        name = stem[: max_len - len(ext)].rstrip(" .") + ext
    return name


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    stem, suf = p.stem, p.suffix
    i = 2
    while True:
        cand = p.with_name(f"{stem} ({i}){suf}")
        if not cand.exists():
            return cand
        i += 1


def new_workspace(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"tm_{prefix}_"))


def remove_tree(p: Path | str | None) -> None:
    if p:
        shutil.rmtree(p, ignore_errors=True)


def save_upload(uploaded, dest_dir: Path) -> Path:
    """Stream a Streamlit UploadedFile (or any file-like with .name) to disk."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(dest_dir / sanitize_filename(uploaded.name))
    try:
        uploaded.seek(0)
    except Exception:
        pass
    with open(target, "wb") as f:
        shutil.copyfileobj(uploaded, f, 1024 * 1024)
    return target


# --------------------------------------------------------------------------- ZIP


class ZipLimitError(Exception):
    pass


@dataclass
class ExtractReport:
    files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    zip_dirs: list[Path] = field(default_factory=list)   # dirs created from nested zips
    bytes_written: int = 0


def _decode_name(info: zipfile.ZipInfo) -> str:
    """Windows zips with Hindi names often lack the UTF-8 flag -> cp437 mojibake."""
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        return name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def _is_junk(parts: list[str]) -> bool:
    if parts[0] == "__MACOSX":
        return True
    last = parts[-1]
    low = last.lower()
    return low in _JUNK_NAMES or low.startswith("._") or low.startswith("~$")


def safe_extract_zip(
    zip_path: Path,
    dest: Path,
    report: ExtractReport | None = None,
    *,
    recurse: bool = True,
    depth: int = 0,
    budget: list[int] | None = None,
) -> ExtractReport:
    """Extract ``zip_path`` into ``dest`` defensively.

    * blocks path traversal ("../", absolute paths) and symlinks
    * limits total extracted bytes / number of files (zip bombs)
    * skips macOS / Windows junk files
    * fixes non-UTF-8 (cp437) file names
    * optionally recurses into nested .zip files (extracted to a folder named
      after the nested zip; the folder is recorded in ``report.zip_dirs``)
    """
    report = report if report is not None else ExtractReport()
    budget = budget if budget is not None else [MAX_UNCOMPRESSED_BYTES]
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()

    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        report.warnings.append(f"{zip_path.name}: not a valid ZIP file ({e})")
        return report

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES_PER_ZIP:
            report.warnings.append(
                f"{zip_path.name}: {len(infos)} entries, only the first {MAX_FILES_PER_ZIP} are read"
            )
            infos = infos[:MAX_FILES_PER_ZIP]

        nested: list[Path] = []
        for info in infos:
            if info.is_dir():
                continue
            name = _decode_name(info).replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts or ".." in parts or name.startswith("/"):
                report.warnings.append(f"{zip_path.name}: unsafe path skipped: {name!r}")
                continue
            if _is_junk(parts):
                continue
            if (info.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                report.warnings.append(f"{zip_path.name}: symlink skipped: {name!r}")
                continue
            if info.flag_bits & 0x1:
                report.warnings.append(f"{zip_path.name}: password-protected file skipped: {name!r}")
                continue

            parts = [sanitize_filename(p) for p in parts]
            target = unique_path(dest.joinpath(*parts))
            try:
                if not str(target.resolve()).startswith(str(dest_resolved) + os.sep):
                    report.warnings.append(f"{zip_path.name}: path escape blocked: {name!r}")
                    continue
            except OSError:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)

            try:
                with zf.open(info) as src, open(target, "wb") as out:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        budget[0] -= len(chunk)
                        if budget[0] < 0:
                            raise ZipLimitError("uncompressed size limit exceeded")
                        report.bytes_written += len(chunk)
                        out.write(chunk)
            except ZipLimitError:
                target.unlink(missing_ok=True)
                report.warnings.append(
                    f"{zip_path.name}: extraction stopped, uncompressed size limit exceeded"
                )
                break
            except (RuntimeError, zipfile.BadZipFile, NotImplementedError, zlib.error, OSError) as e:
                target.unlink(missing_ok=True)
                report.warnings.append(f"{zip_path.name}: cannot read {name!r} ({type(e).__name__})")
                continue

            if target.suffix.lower() == ".zip":
                nested.append(target)
            else:
                report.files.append(target)

    for nz in nested:
        if recurse and depth < MAX_NEST_DEPTH:
            nd = unique_path(nz.with_suffix(""))
            before = len(report.files)
            safe_extract_zip(nz, nd, report, recurse=True, depth=depth + 1, budget=budget)
            report.zip_dirs.append(nd)
            nz.unlink(missing_ok=True)
            if len(report.files) == before and not any(nd.iterdir()):
                report.warnings.append(f"{nz.name}: nested ZIP is empty")
        else:
            report.files.append(nz)
    return report


def list_files(root: Path) -> list[Path]:
    """All regular files below root, junk removed, sorted (natural order)."""
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            rel_parts = list(p.relative_to(root).parts)
            if _is_junk(rel_parts):
                continue
            out.append(p)
    return sorted(out, key=lambda p: natural_key(str(p.relative_to(root))))


def split_supported(files: list[Path]) -> tuple[list[Path], list[Path]]:
    ok = [f for f in files if f.suffix.lower() in SUPPORTED_EXTS]
    bad = [f for f in files if f.suffix.lower() not in SUPPORTED_EXTS]
    return ok, bad


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def rel_posix(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.name
