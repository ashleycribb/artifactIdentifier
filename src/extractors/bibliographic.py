"""Bibliographic identifier and citation metadata extraction module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List, Optional

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
ARXIV_PATTERN = re.compile(
    r"\b(?:arXiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Za-z]{2})?/\d{7})\b",
    re.IGNORECASE,
)
ISBN_PATTERN = re.compile(r"\b(?:ISBN(?:-1[03])?:?\s*)?(?=[-0-9 ]{13}|[-0-9X ]{10}$)[0-9]{1,5}[- ]?[0-9]+[- ]?[0-9]+[- ]?[0-9X]\b")


@dataclass
class BibliographicResult:
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    isbn: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    all_dois: List[str] = field(default_factory=list)
    has_scholarly_metadata: bool = False


def extract_bibliographic_metadata(
    text: str,
    meta_tags: Optional[dict] = None,
    file_name: Optional[str] = None,
) -> BibliographicResult:
    """Extracts DOIs, arXiv IDs, and publisher metadata from text, HTML meta tags, or filenames."""
    dois: List[str] = []
    arxiv_id: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None

    # Check HTML meta tags first (highest precision)
    if meta_tags:
        for k, v in meta_tags.items():
            k_lower = k.lower()
            if "doi" in k_lower and isinstance(v, str):
                match = DOI_PATTERN.search(v)
                if match:
                    dois.append(match.group(0))
            elif "journal" in k_lower and isinstance(v, str):
                journal = v
            elif "publisher" in k_lower and isinstance(v, str):
                publisher = v
            elif "date" in k_lower or "year" in k_lower:
                year_match = re.search(r"\b(19\d\d|20\d\d)\b", str(v))
                if year_match:
                    year = int(year_match.group(1))

    # Check filename for arXiv IDs (e.g., arXiv-2607.02514v1.tar.gz)
    if file_name:
        fn_match = ARXIV_PATTERN.search(file_name)
        if fn_match:
            arxiv_id = fn_match.group(1) or fn_match.group(0)

    # Search in document text
    if text:
        text_dois = DOI_PATTERN.findall(text)
        for d in text_dois:
            # Clean trailing punctuation often caught in regex
            cleaned_doi = d.rstrip(".,;)>")
            if cleaned_doi not in dois:
                dois.append(cleaned_doi)

        if not arxiv_id:
            arxiv_match = ARXIV_PATTERN.search(text)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1) or arxiv_match.group(0)

    primary_doi = dois[0] if dois else None
    has_meta = bool(primary_doi or arxiv_id or journal or publisher)

    return BibliographicResult(
        doi=primary_doi,
        arxiv_id=arxiv_id,
        all_dois=dois,
        journal=journal,
        publisher=publisher,
        publication_year=year,
        has_scholarly_metadata=has_meta,
    )
