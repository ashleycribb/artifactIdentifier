"""Deterministic fast-path classification engine with sub-asset exclusion and LLM fallback."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.config import AppConfig, UserProfileConfig
from src.extractors.archive import inspect_archive, is_sub_asset_file
from src.extractors.author_matcher import (
    AuthorProfile,
    disambiguate_author_and_status,
)
from src.extractors.bibliographic import extract_bibliographic_metadata
from src.extractors.geometry import analyze_pdf_geometry
from src.extractors.text import extract_document_text
from src.fingerprint import compute_sha256
from src.classifier.llm_client import LLMClient

CANDIDATE_CLASSES = [
    "AcademicPaper",
    "AuthorDraft",
    "ResearchNote",
    "ConferencePoster",
    "ConferencePresentation",
    "SourcePackage",
    "NeedsReview",
]


class ClassificationEngine:
    """Core deterministic classification engine."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.llm_client = LLMClient(self.config.llm)
        self.author_profile = AuthorProfile(
            user_names=self.config.user_profile.author_names,
            orcids=self.config.user_profile.orcids,
            institutions=self.config.user_profile.institutions,
            collaborators=self.config.user_profile.collaborators,
        )

    def classify_file(
        self,
        file_path: str | Path,
        workspace_root: Optional[str | Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """Classifies a single file and produces a verified manifest dict.
        Returns None if file is excluded as a child sub-asset (e.g. figures/*.pdf).
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            return None

        # 1. Sub-asset exclusion check
        ws_root = Path(workspace_root).resolve() if workspace_root else path.parent
        if is_sub_asset_file(path, ws_root):
            # File is bound to parent manuscript package, excluded from standalone classification
            return None

        # 2. Cryptographic fingerprint
        sha256 = compute_sha256(path)
        byte_size = path.stat().st_size
        ext = path.suffix.lower()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 3. Rule 1: Compound Archive Introspection (.tar.gz, .zip)
        if path.name.lower().endswith((".tar.gz", ".tgz", ".zip")):
            arc_res = inspect_archive(path)
            if arc_res.is_valid:
                return self._build_manifest(
                    sha256=sha256,
                    file_path=str(path),
                    byte_size=byte_size,
                    last_scanned=now_iso,
                    assigned_class="SourcePackage",
                    confidence=0.98,
                    source="deterministic_rule",
                    rationale=arc_res.summary,
                    title=path.name,
                    authors=[],
                    doi=None,
                    page_count=None,
                    dimensions=None,
                    doc_format=arc_res.archive_format,
                )

        # 4. Extract Text & Structure
        text_res = extract_document_text(path, max_tokens=self.config.llm.max_tokens)

        # 5. Extract Bibliographic Identifiers
        bib_res = extract_bibliographic_metadata(
            text=text_res.text_snippet,
            meta_tags=text_res.meta_tags,
            file_name=path.name,
        )

        # 6. Rule 2: Layout & Geometry Analysis (Posters & Slides)
        geo_res = None
        dimensions_dict = None
        if ext == ".pdf":
            geo_res = analyze_pdf_geometry(path)
            if geo_res.dimension:
                dimensions_dict = {
                    "width": geo_res.dimension.width,
                    "height": geo_res.dimension.height,
                    "unit": geo_res.dimension.unit,
                }

            if geo_res.is_poster_candidate:
                return self._build_manifest(
                    sha256=sha256,
                    file_path=str(path),
                    byte_size=byte_size,
                    last_scanned=now_iso,
                    assigned_class="ConferencePoster",
                    confidence=0.95,
                    source="deterministic_rule",
                    rationale=f"Single-page large format layout: {geo_res.summary}",
                    title=text_res.title,
                    authors=text_res.authors,
                    doi=bib_res.doi,
                    page_count=1,
                    dimensions=dimensions_dict,
                    doc_format="pdf",
                )

            if geo_res.is_slide_deck_candidate:
                return self._build_manifest(
                    sha256=sha256,
                    file_path=str(path),
                    byte_size=byte_size,
                    last_scanned=now_iso,
                    assigned_class="ConferencePresentation",
                    confidence=0.95,
                    source="deterministic_rule",
                    rationale=f"Multi-page slide presentation layout ({geo_res.aspect_ratio_label})",
                    title=text_res.title,
                    authors=text_res.authors,
                    doi=bib_res.doi,
                    page_count=geo_res.dimension.page_count if geo_res.dimension else None,
                    dimensions=dimensions_dict,
                    doc_format="pdf",
                )

        if ext in (".pptx", ".ppt"):
            return self._build_manifest(
                sha256=sha256,
                file_path=str(path),
                byte_size=byte_size,
                last_scanned=now_iso,
                assigned_class="ConferencePresentation",
                confidence=0.98,
                source="deterministic_rule",
                rationale=f"Presentation slide deck format with {text_res.page_count or 0} slides",
                title=text_res.title,
                authors=text_res.authors,
                doi=bib_res.doi,
                page_count=text_res.page_count,
                dimensions=None,
                doc_format="pptx",
            )

        # 7. Rule 3: Author Disambiguation
        author_res = disambiguate_author_and_status(
            file_path=path,
            document_authors=text_res.authors,
            text_snippet=text_res.text_snippet,
            profile=self.author_profile,
            has_doi_or_publisher=bool(bib_res.doi or bib_res.has_scholarly_metadata),
        )

        # 8. Rule 4: Academic Paper vs Author Draft vs Research Note
        if bib_res.doi or (text_res.format == "html" and bib_res.has_scholarly_metadata):
            if not author_res.is_likely_draft:
                return self._build_manifest(
                    sha256=sha256,
                    file_path=str(path),
                    byte_size=byte_size,
                    last_scanned=now_iso,
                    assigned_class="AcademicPaper",
                    confidence=0.96,
                    source="deterministic_rule",
                    rationale=f"Scholarly publication with DOI {bib_res.doi or 'metadata'}",
                    title=text_res.title,
                    authors=text_res.authors,
                    doi=bib_res.doi,
                    page_count=text_res.page_count,
                    dimensions=dimensions_dict,
                    doc_format=text_res.format,
                )

        # Rule 5: Research Notes (Markdown / Text / short memo)
        note_cues = {"note", "meeting", "memo", "log", "summary", "todo", "agenda"}
        is_note_cue = any(nc in path.name.lower() or nc in (text_res.title or "").lower() for nc in note_cues)
        if ext in (".md", ".txt", ".org", ".rst") and (is_note_cue or not author_res.has_draft_markers):
            return self._build_manifest(
                sha256=sha256,
                file_path=str(path),
                byte_size=byte_size,
                last_scanned=now_iso,
                assigned_class="ResearchNote",
                confidence=0.92,
                source="deterministic_rule",
                rationale="Plaintext/markdown research notes without formal publication structure",
                title=text_res.title or path.name,
                authors=text_res.authors,
                doi=bib_res.doi,
                page_count=text_res.page_count,
                dimensions=dimensions_dict,
                doc_format=text_res.format,
            )

        if author_res.is_likely_draft or (author_res.is_user_authored and author_res.has_active_source):
            return self._build_manifest(
                sha256=sha256,
                file_path=str(path),
                byte_size=byte_size,
                last_scanned=now_iso,
                assigned_class="AuthorDraft",
                confidence=0.92,
                source="deterministic_rule",
                rationale=author_res.rationale,
                title=text_res.title,
                authors=text_res.authors,
                doi=bib_res.doi,
                page_count=text_res.page_count,
                dimensions=dimensions_dict,
                doc_format=text_res.format,
            )

        # 9. Fallback: LLM Fallback or NeedsReview
        if self.config.llm.allow_remote:
            pred = self.llm_client.classify_snippet(
                file_name=path.name,
                text_snippet=text_res.text_snippet,
                candidate_classes=CANDIDATE_CLASSES,
            )
            if pred and pred.confidence >= self.config.scanner.confidence_threshold:
                return self._build_manifest(
                    sha256=sha256,
                    file_path=str(path),
                    byte_size=byte_size,
                    last_scanned=now_iso,
                    assigned_class=pred.assigned_class,
                    confidence=pred.confidence,
                    source="llm_fallback",
                    rationale=pred.rationale,
                    title=text_res.title,
                    authors=text_res.authors,
                    doi=bib_res.doi,
                    page_count=text_res.page_count,
                    dimensions=dimensions_dict,
                    doc_format=text_res.format,
                )

        # Safe default when ambiguous: route to NeedsReview for human supervisory gate
        return self._build_manifest(
            sha256=sha256,
            file_path=str(path),
            byte_size=byte_size,
            last_scanned=now_iso,
            assigned_class="NeedsReview",
            confidence=0.50,
            source="deterministic_rule",
            rationale="Ambiguous document characteristics; routed to supervisory gate",
            title=text_res.title,
            authors=text_res.authors,
            doi=bib_res.doi,
            page_count=text_res.page_count,
            dimensions=dimensions_dict,
            doc_format=text_res.format,
        )

    def _build_manifest(
        self,
        sha256: str,
        file_path: str,
        byte_size: int,
        last_scanned: str,
        assigned_class: str,
        confidence: float,
        source: str,
        rationale: str,
        title: Optional[str],
        authors: List[str],
        doi: Optional[str],
        page_count: Optional[int],
        dimensions: Optional[Dict[str, Any]],
        doc_format: str,
    ) -> Dict[str, Any]:
        return {
            "fingerprint": {
                "sha256": sha256,
                "file_path": file_path,
                "byte_size": byte_size,
                "last_scanned": last_scanned,
            },
            # The agent only SUGGESTS a class. It becomes final only after a human
            # runs `s3a-agent confirm` or `s3a-agent override`.
            "classification": {
                "suggested_class": assigned_class,
                "confidence": round(confidence, 2),
                "source": source,
                "rationale": rationale,
            },
            "confirmation": {
                "status": "unconfirmed",
                "final_class": None,
                "confirmed_by": None,
                "confirmed_at": None,
                "notes": None,
            },
            "human_override": {
                "active": False,
                "original_class": None,
                "updated_by": None,
                "updated_at": None,
                "notes": None,
            },
            "attributes": {
                "title": title,
                "authors": authors,
                "doi": doi,
                "page_count": page_count,
                "dimensions": dimensions,
                "format": doc_format,
            },
        }
