"""LibreOffice (soffice) helpers - used for DOCX/XLSX -> PDF and DOC/XLS -> DOCX/XLSX."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .utils import unique_path

_SOFFICE: str | None = None


def find_soffice() -> str | None:
    global _SOFFICE
    if _SOFFICE is None:
        _SOFFICE = shutil.which("soffice") or shutil.which("libreoffice") or ""
    return _SOFFICE or None


def _run(cmd: list[str], timeout: int, env: dict) -> None:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, env=env
    )
    try:
        proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        proc.communicate()


def _convert_chunk(
    soffice: str, chunk: list[Path], out_dir: Path, fmt: str, timeout: int
) -> dict[Path, Path]:
    ext = fmt.split(":")[0]
    results: dict[Path, Path] = {}
    with tempfile.TemporaryDirectory(prefix="lo_in_") as tin, tempfile.TemporaryDirectory(
        prefix="lo_prof_"
    ) as prof, tempfile.TemporaryDirectory(prefix="lo_out_") as tout:
        mapping: dict[str, Path] = {}
        links: list[str] = []
        for j, f in enumerate(chunk):
            link = Path(tin) / f"{j:05d}{f.suffix.lower()}"
            try:
                os.link(f, link)
            except OSError:
                shutil.copy2(f, link)
            mapping[link.stem] = f
            links.append(str(link))
        cmd = [
            soffice,
            f"-env:UserInstallation={Path(prof).as_uri()}",
            "--headless", "--norestore", "--nologo", "--nolockcheck",
            "--convert-to", fmt, "--outdir", tout, *links,
        ]
        env = {**os.environ, "HOME": prof}
        _run(cmd, timeout, env)
        for out in Path(tout).glob(f"*.{ext}"):
            src = mapping.get(out.stem)
            if src is not None:
                dest = unique_path(out_dir / f"{src.stem}.{ext}")
                shutil.move(str(out), dest)
                results[src] = dest
    return results


def convert_batch(
    files: list[Path],
    out_dir: Path,
    fmt: str,
    *,
    batch_size: int = 20,
    per_file_timeout: int = 90,
    progress: Callable[[int, int], None] | None = None,
) -> dict[Path, Path]:
    """Convert many files with as few soffice launches as possible.

    Files that fail inside a batch are retried one by one, so one broken file
    cannot spoil its neighbours. Returns {source: converted}; missing = failed.
    """
    soffice = find_soffice()
    if not soffice or not files:
        return {}
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[Path, Path] = {}
    total = len(files)
    done = 0
    for i in range(0, total, batch_size):
        chunk = files[i : i + batch_size]
        try:
            results.update(
                _convert_chunk(soffice, chunk, out_dir, fmt, per_file_timeout * len(chunk) + 60)
            )
        except Exception:
            pass
        if len(chunk) > 1:
            for f in chunk:
                if f not in results:
                    try:
                        results.update(_convert_chunk(soffice, [f], out_dir, fmt, per_file_timeout + 30))
                    except Exception:
                        pass
        done += len(chunk)
        if progress:
            progress(done, total)
    return results
