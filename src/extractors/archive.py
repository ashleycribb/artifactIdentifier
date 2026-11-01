"""Compound archive inspector and sub-asset exclusion filter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tarfile
from typing import List, Optional
import zipfile


@dataclass
class ArchiveInspectionResult:
    is_valid: bool
    archive_format: str
    member_count: int
    root_manuscript: Optional[str] = None
    asset_files: List[str] = field(default_factory=list)
    has_latex: bool = False
    has_scholarly_html: bool = False
    summary: str = ""


ROOT_MANUSCRIPT_CANDIDATES = {
    "main.tex",
    "ms.tex",
    "paper.tex",
    "article.tex",
    "index.html",
    "manuscript.md",
    "document.tex",
}

SUB_ASSET_DIR_NAMES = {
    "figures",
    "figs",
    "images",
    "plots",
    "macros",
    "styles",
    "data",
}


def inspect_archive(path: str | Path) -> ArchiveInspectionResult:
    """Introspects a compressed tarball or zip package to detect research root manuscripts and assets."""
    archive_path = Path(path)
    if not archive_path.is_file():
        return ArchiveInspectionResult(
            is_valid=False,
            archive_format="unknown",
            member_count=0,
            summary="Archive file not found",
        )

    ext = archive_path.name.lower()
    if ext.endswith((".tar.gz", ".tgz")):
        return _inspect_tar_gz(archive_path)
    elif ext.endswith(".zip"):
        return _inspect_zip(archive_path)
    else:
        return ArchiveInspectionResult(
            is_valid=False,
            archive_format="unsupported",
            member_count=0,
            summary=f"Unsupported archive format: {archive_path.suffix}",
        )


def _inspect_tar_gz(path: Path) -> ArchiveInspectionResult:
    try:
        with tarfile.open(path, "r:gz") as tar:
            members = tar.getnames()
            return _analyze_members(members, "tar.gz")
    except Exception as e:
        return ArchiveInspectionResult(
            is_valid=False,
            archive_format="tar.gz",
            member_count=0,
            summary=f"Failed to read tar.gz: {e}",
        )


def _inspect_zip(path: Path) -> ArchiveInspectionResult:
    try:
        with zipfile.ZipFile(path, "r") as z:
            members = z.namelist()
            return _analyze_members(members, "zip")
    except Exception as e:
        return ArchiveInspectionResult(
            is_valid=False,
            archive_format="zip",
            member_count=0,
            summary=f"Failed to read zip: {e}",
        )


def _analyze_members(members: List[str], fmt: str) -> ArchiveInspectionResult:
    root_ms: Optional[str] = None
    asset_files: List[str] = []
    has_latex = False
    has_scholarly_html = False

    for m in members:
        p = Path(m)
        name_lower = p.name.lower()
        if name_lower.endswith(".tex"):
            has_latex = True
        elif name_lower.endswith((".html", ".htm")):
            has_scholarly_html = True

        if name_lower in ROOT_MANUSCRIPT_CANDIDATES and root_ms is None:
            root_ms = m

        parts = [part.lower() for part in p.parts]
        if any(d in parts for d in SUB_ASSET_DIR_NAMES):
            asset_files.append(m)

    summary = (
        f"Compound package ({fmt}) containing {len(members)} files. "
        f"Root manuscript: {root_ms or 'None'}. "
        f"Sub-assets: {len(asset_files)}."
    )

    return ArchiveInspectionResult(
        is_valid=True,
        archive_format=fmt,
        member_count=len(members),
        root_manuscript=root_ms,
        asset_files=asset_files,
        has_latex=has_latex,
        has_scholarly_html=has_scholarly_html,
        summary=summary,
    )


def is_sub_asset_file(path: str | Path, workspace_root: Optional[str | Path] = None) -> bool:
    """Determines whether a file is an embedded figure or sub-asset of a parent manuscript package."""
    file_path = Path(path).resolve()
    parts = [part.lower() for part in file_path.parts]

    # If the file resides directly inside a directory named figures, images, etc.
    if any(asset_dir in parts[:-1] for asset_dir in SUB_ASSET_DIR_NAMES):
        # Check if parent or ancestor contains a manuscript root
        parent = file_path.parent
        ws = Path(workspace_root).resolve() if workspace_root else None

        current = parent
        while current and (ws is None or ws in current.parents or current == ws):
            for candidate in ROOT_MANUSCRIPT_CANDIDATES:
                if (current / candidate).exists():
                    return True
            if current == current.parent:
                break
            current = current.parent
        # Even without explicit root file in tree, if parent directory name is in sub-assets:
        if file_path.parent.name.lower() in SUB_ASSET_DIR_NAMES:
            return True

    return False
