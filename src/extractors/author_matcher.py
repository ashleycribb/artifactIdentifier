"""Author identity matcher and publication status disambiguation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import time
from typing import List, Optional, Set


@dataclass
class AuthorProfile:
    user_names: List[str] = field(default_factory=list)
    orcids: List[str] = field(default_factory=list)
    institutions: List[str] = field(default_factory=list)
    collaborators: List[str] = field(default_factory=list)


@dataclass
class AuthorDisambiguationResult:
    is_user_authored: bool
    matched_names: List[str] = field(default_factory=list)
    is_likely_draft: bool = False
    has_active_source: bool = False
    has_draft_markers: bool = False
    rationale: str = ""


DRAFT_CUE_WORDS = {
    "draft",
    "preliminary",
    "under review",
    "to appear",
    "work in progress",
    "confidential",
    "internal report",
    "manuscript",
    "working paper",
}


def normalize_name(name: str) -> str:
    """Normalizes a person name for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def disambiguate_author_and_status(
    file_path: str | Path,
    document_authors: List[str],
    text_snippet: str,
    profile: Optional[AuthorProfile] = None,
    has_doi_or_publisher: bool = False,
) -> AuthorDisambiguationResult:
    """Disambiguates whether a document was written by the user and separates past published works from active drafts."""
    path = Path(file_path).resolve()
    matched: List[str] = []
    is_user = False

    if profile and profile.user_names:
        norm_targets: Set[str] = {normalize_name(n) for n in profile.user_names if n.strip()}
        for a in document_authors:
            norm_a = normalize_name(a)
            if any(target in norm_a or norm_a in target for target in norm_targets if len(target) > 3):
                matched.append(a)
                is_user = True

        # Check text snippet if not found in explicit authors
        if not is_user:
            norm_text = text_snippet.lower()
            for u in profile.user_names:
                if len(u) > 3 and u.lower() in norm_text:
                    matched.append(u)
                    is_user = True

    # Check for active editable source files in the same directory (e.g. main.tex, draft.docx)
    has_active_source = False
    parent = path.parent
    stem = path.stem.lower()

    active_exts = {".tex", ".docx", ".org", ".md"}
    for sibling in parent.glob(f"{stem}.*"):
        if sibling.suffix.lower() in active_exts and sibling != path:
            has_active_source = True
            break

    # If compiling latex project
    if (parent / "main.tex").exists() or (parent / "paper.tex").exists():
        has_active_source = True

    # Check draft markers in text or filename
    has_draft_markers = False
    combined_cues = (path.name + " " + text_snippet[:2000]).lower()
    for cue in DRAFT_CUE_WORDS:
        if cue in combined_cues:
            has_draft_markers = True
            break

    # Check recent modification time (< 30 days)
    is_recent = False
    try:
        mtime = path.stat().st_mtime
        if (time.time() - mtime) < (30 * 86400):
            is_recent = True
    except Exception:
        pass

    # Decision logic:
    # A file is ONLY an AuthorDraft if it has active sources, draft markers, or is recent WITHOUT a published DOI.
    # If the user authored it, but it has a DOI and NO active source, it is a published AcademicPaper.
    is_likely_draft = False
    rationale_parts = []

    if is_user:
        rationale_parts.append(f"Authored by user (matches: {', '.join(matched)})")
        if has_doi_or_publisher and not has_active_source and not has_draft_markers:
            is_likely_draft = False
            rationale_parts.append("Has registered DOI/publisher and no local source: classified as published paper")
        elif has_active_source or has_draft_markers:
            is_likely_draft = True
            rationale_parts.append("Has local source files or draft markers: classified as active draft")
        elif is_recent and not has_doi_or_publisher and path.suffix.lower() in (".tex", ".docx"):
            is_likely_draft = True
            rationale_parts.append("Recent manuscript without DOI: classified as active draft")
    else:
        if has_draft_markers and has_active_source:
            is_likely_draft = True
            rationale_parts.append("Has draft cues and editable source files")

    return AuthorDisambiguationResult(
        is_user_authored=is_user,
        matched_names=matched,
        is_likely_draft=is_likely_draft,
        has_active_source=has_active_source,
        has_draft_markers=has_draft_markers,
        rationale="; ".join(rationale_parts) or "Standard literature",
    )
